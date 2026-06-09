"""Error watcher: intercepts backend errors and creates tracker tasks for tracking.

Provides two mechanisms for detecting errors:

1. **Python logging handler** — ``ErrorWatcher.install_log_handler()``
   hooks into Python's ``logging`` system to catch ERROR+ records from the
   oompah backend and create tasks automatically.

2. **Log file watcher** — ``LogFileWatcher`` monitors an external log file
   for error lines and feeds them to an ``ErrorWatcher``.  Any project can
   use this by setting a ``log_path`` on its :class:`~oompah.models.Project`.

Task creation goes through the :class:`~oompah.tracker.TrackerProtocol` so any
configured tracker backend (Backlog.md, GitHub Issues, etc.) is supported.
The :func:`_persist_error_task_to_git` helper is the only Backlog.md-specific
path; it is guarded by an ``isinstance(tracker, BacklogMdTracker)`` check.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from watchfiles import awatch

from oompah.tracker import BacklogMdTracker, TrackerProtocol

logger = logging.getLogger(__name__)

# Don't create tasks for the same error more than once within this window.
_DEDUP_WINDOW_SECONDS = 3600  # 1 hour

# Max number of fingerprints to keep in memory (LRU-ish eviction).
_MAX_FINGERPRINTS = 500
_GIT_PUBLISH_TIMEOUT_SECONDS = 30
_GIT_AUTHOR_NAME = "oompah"
_GIT_AUTHOR_EMAIL = "lesserevil@users.noreply.github.com"
_COMMIT_TRAILER = (
    "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
    "Co-authored-by: oompah <lesserevil@users.noreply.github.com>"
)
_GIT_PUBLISH_LOCKS: dict[Path, threading.Lock] = {}
_GIT_PUBLISH_LOCKS_GUARD = threading.Lock()


def _git_publish_lock(repo_root: Path) -> threading.Lock:
    with _GIT_PUBLISH_LOCKS_GUARD:
        lock = _GIT_PUBLISH_LOCKS.get(repo_root)
        if lock is None:
            lock = threading.Lock()
            _GIT_PUBLISH_LOCKS[repo_root] = lock
        return lock


def _run_git(
    repo_root: Path,
    args: list[str],
    *,
    timeout: float = _GIT_PUBLISH_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _redact_git_output(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"https://([^/\s:@]+):([^@\s]+)@", r"https://\1:<redacted>@", text)
    text = re.sub(r"gh[pousr]_[A-Za-z0-9_]+", "<redacted-token>", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "<redacted-token>", text)
    return text[:500]


def _git_toplevel(path: Path) -> Path | None:
    result = _run_git(path, ["rev-parse", "--show-toplevel"], timeout=5)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    if not value:
        return None
    return Path(value).resolve()


def _persist_error_task_to_git(
    tracker: TrackerProtocol,
    identifier: str,
) -> bool:
    """Commit and push the Backlog.md file for an ErrorWatcher-created task.

    This is a Backlog.md-specific operation; for other tracker backends it is
    a no-op.  Returns True only when a commit was created and pushed.  All
    failures are best-effort and reported to the logger by the caller.
    """
    if not isinstance(tracker, BacklogMdTracker):
        return False

    task_path = tracker.task_file_path(identifier)
    if not task_path:
        logger.debug("ErrorWatcher task %s has no Backlog.md file to commit", identifier)
        return False

    repo_root = _git_toplevel(tracker.root_path)
    if not repo_root:
        logger.debug(
            "ErrorWatcher task %s not committed: %s is not a git repository",
            identifier,
            tracker.root_path,
        )
        return False

    task_path = task_path.resolve()
    try:
        rel_path = task_path.relative_to(repo_root)
    except ValueError:
        logger.debug(
            "ErrorWatcher task %s not committed: task path %s is outside git repo %s",
            identifier,
            task_path,
            repo_root,
        )
        return False

    with _git_publish_lock(repo_root):
        add = _run_git(repo_root, ["add", "--", str(rel_path)])
        if add.returncode != 0:
            logger.warning(
                "ErrorWatcher task %s git add failed: %s",
                identifier,
                _redact_git_output(add.stderr or add.stdout),
            )
            return False

        diff = _run_git(repo_root, ["diff", "--cached", "--quiet", "--", str(rel_path)])
        if diff.returncode == 0:
            logger.debug("ErrorWatcher task %s had no staged git changes", identifier)
            return False
        if diff.returncode != 1:
            logger.warning(
                "ErrorWatcher task %s staged diff check failed: %s",
                identifier,
                _redact_git_output(diff.stderr or diff.stdout),
            )
            return False

        commit = _run_git(
            repo_root,
            [
                "-c",
                f"user.name={_GIT_AUTHOR_NAME}",
                "-c",
                f"user.email={_GIT_AUTHOR_EMAIL}",
                "commit",
                "--only",
                "-m",
                f"Record ErrorWatcher task {identifier}",
                "-m",
                _COMMIT_TRAILER,
                "--",
                str(rel_path),
            ],
        )
        if commit.returncode != 0:
            logger.warning(
                "ErrorWatcher task %s git commit failed: %s",
                identifier,
                _redact_git_output(commit.stderr or commit.stdout),
            )
            return False

        push = _run_git(repo_root, ["push"])
        if push.returncode != 0:
            logger.warning(
                "ErrorWatcher task %s git push failed after local commit: %s",
                identifier,
                _redact_git_output(push.stderr or push.stdout),
            )
            return False

    logger.info("Committed and pushed ErrorWatcher task %s", identifier)
    return True


@dataclass
class _ErrorRecord:
    """Tracks when we last created a bead for a given error fingerprint.

    ``bead_id`` and ``issue_id`` are populated when ``report_error`` is
    called with an ``issue_id``; they let the orchestrator auto-close the
    task when the originating issue's retry path succeeds.
    """
    fingerprint: str
    last_created: float = 0.0
    bead_id: str | None = None
    issue_id: str | None = None


# Window during which a retry-success can auto-close a previously filed
# error task. Tasks older than this stay open for operator inspection.
# inspect manually).
_AUTO_CLOSE_WINDOW_SECONDS = 1800  # 30 minutes

# After report_error fires for a fingerprint, we wait at least this long
# before allowing auto-close on it.  Without this guard, a successful
# retry on issue A could close a bead whose same-fingerprint failure is
# still actively firing on issue B.
_AUTO_CLOSE_QUIET_SECONDS = 60


class ErrorWatcher:
    """Watches for errors and creates tracker tasks to track them.

    Hooks into Python's logging system via a custom handler. Also accepts
    explicit error reports (e.g. from a frontend error endpoint).  Works
    with any :class:`~oompah.tracker.TrackerProtocol` backend.
    """

    def __init__(self, tracker: TrackerProtocol, project_id: str | None = None):
        self._tracker = tracker
        self._project_id = project_id
        self._seen: dict[str, _ErrorRecord] = {}
        self._handler: _BeadLoggingHandler | None = None

    def install_log_handler(self, logger_name: str = "oompah") -> None:
        """Install a logging handler that creates beads for ERROR+ log records."""
        root = logging.getLogger(logger_name)
        self._handler = _BeadLoggingHandler(self)
        self._handler.setLevel(logging.ERROR)
        root.addHandler(self._handler)

    def uninstall_log_handler(self, logger_name: str = "oompah") -> None:
        """Remove the logging handler."""
        if self._handler:
            logging.getLogger(logger_name).removeHandler(self._handler)
            self._handler = None

    def report_error(
        self,
        source: str,
        message: str,
        *,
        detail: str | None = None,
        priority: int = 2,
        issue_id: str | None = None,
        error_class: str | None = None,
    ) -> str | None:
        """Report an error and create a bead if not a duplicate.

        Args:
            source: Where the error came from (e.g. "backend", "frontend").
            message: Short error summary (used for title + fingerprinting).
            detail: Longer description / stack trace.
            priority: Bead priority (0=critical, 4=backlog). Default 2.
            issue_id: Optional id of the issue whose run triggered this
                error. When supplied, the watcher links the resulting
                bead to the issue so :meth:`auto_close_for_issue` can
                close it once the issue's retry path succeeds.
            error_class: Optional explicit error classification (e.g.
                ``"bd_timeout"``, ``"connection_refused"``). When given,
                deduplication collapses *all* reports with the same class
                to a single bead within the dedup window — regardless of
                the exact message text, project, or subcommand. Use this
                for known operational/infra failure modes that fan out
                across many call sites.

        Returns:
            The bead identifier if one was created, None if deduplicated.
        """
        fp = self._fingerprint(source, message, error_class=error_class)

        now = time.monotonic()
        record = self._seen.get(fp)
        if record and (now - record.last_created) < _DEDUP_WINDOW_SECONDS:
            # Refresh last_created so the recent-error guard in
            # auto_close_for_issue treats this fingerprint as still
            # actively firing.  Also remember the originating issue if
            # the previous record didn't have one (so subsequent
            # success can auto-close the existing bead).
            record.last_created = now
            if issue_id and not record.issue_id:
                record.issue_id = issue_id
            return None

        # Evict old entries if we're at capacity
        if len(self._seen) >= _MAX_FINGERPRINTS:
            self._evict_oldest()

        # Create the bead
        title = f"[{source}] {message}"
        if len(title) > 200:
            title = title[:197] + "..."

        # Description still carries the full message + caller-supplied
        # detail so the operator can diagnose even when the fingerprint
        # was collapsed via error_class.
        description = detail or message
        if error_class:
            description = (
                f"error_class={error_class}\n\n"
                f"Triggering message: {message}\n\n"
                f"{description}"
            )

        try:
            issue = self._tracker.create_issue(
                title=title,
                issue_type="bug",
                description=description,
                priority=priority,
                initial_status="deferred",
            )
        except Exception as exc:
            # Don't let error tracking errors cascade
            logger.debug("Failed to create error bead: %s", exc)
            return None

        self._seen[fp] = _ErrorRecord(
            fingerprint=fp,
            last_created=now,
            bead_id=issue.identifier,
            issue_id=issue_id,
        )
        logger.info(
            "Created error bead %s for [%s] %s%s",
            issue.identifier, source, message[:80],
            f" (issue={issue_id})" if issue_id else "",
        )
        try:
            _persist_error_task_to_git(self._tracker, issue.identifier)
        except Exception as exc:  # noqa: BLE001 - persistence must not cascade
            logger.warning(
                "ErrorWatcher task %s git persistence failed: %s",
                issue.identifier,
                exc,
            )
        return issue.identifier

    def auto_close_for_issue(
        self,
        issue_id: str,
        *,
        issue_identifier: str | None = None,
        resolution_link: str | None = None,
        max_age_seconds: float = _AUTO_CLOSE_WINDOW_SECONDS,
        quiet_seconds: float = _AUTO_CLOSE_QUIET_SECONDS,
    ) -> list[str]:
        """Auto-close every error bead linked to ``issue_id``.

        Called by the orchestrator after a worker run finishes
        successfully *via the retry path* (attempt > 0).  Each matching
        record's bead is closed with a "retry succeeded; transient"
        reason and popped from ``_seen`` so that a future error with
        the same fingerprint will create a fresh bead.

        Records are skipped if:

        * ``last_created`` is older than ``max_age_seconds`` — the
          bead is too stale to be plausibly the same incident.
        * ``last_created`` is younger than ``quiet_seconds`` — the
          fingerprint is still actively firing (likely on another
          issue), so closing it would be premature.

        Args:
            issue_id: id of the originating issue that just succeeded.
            issue_identifier: human-readable identifier (e.g.
                ``oompah-zlz_2-hp2``) used for log messages and
                resolution comments.  Falls back to ``issue_id``.
            resolution_link: optional URL or identifier of the
                successful run / commit / PR; mentioned in the
                resolution comment posted on each closed bead.
            max_age_seconds: age cutoff (default 30 min).
            quiet_seconds: minimum time since the most recent
                fingerprint hit before auto-close is allowed (default
                60 s).

        Returns:
            List of bead identifiers that were auto-closed.
        """
        if not issue_id:
            return []

        now = time.monotonic()
        closed: list[str] = []
        ident = issue_identifier or issue_id

        # Snapshot keys first because we mutate _seen inside the loop.
        for fp in list(self._seen.keys()):
            record = self._seen.get(fp)
            if record is None or record.issue_id != issue_id:
                continue
            if not record.bead_id:
                # No bead was ever filed for this record; nothing to close.
                continue
            age = now - record.last_created
            if age > max_age_seconds:
                continue
            if age < quiet_seconds:
                # Fingerprint is still fresh — likely still firing on
                # another issue.  Skip this round; if the same issue
                # exits successfully again later (or the operator
                # intervenes), the dedup window will have moved on.
                continue

            bead_id = record.bead_id
            comment_body = (
                "Auto-closed by error_watcher: the originating issue "
                f"({ident}) recovered via retry."
            )
            if resolution_link:
                comment_body += f" Resolution: {resolution_link}"
            try:
                # Post a comment first so the audit trail survives close.
                try:
                    self._tracker.add_comment(bead_id, comment_body)
                except Exception as exc:  # pragma: no cover - best effort
                    logger.debug(
                        "Could not post resolution comment on %s: %s",
                        bead_id, exc,
                    )
                self._tracker.close_issue(
                    bead_id,
                    reason="retry succeeded; transient (auto-closed by error_watcher)",
                )
                logger.info(
                    "Auto-closed transient error bead %s (issue=%s resolved)",
                    bead_id, ident,
                )
                closed.append(bead_id)
            except Exception as exc:
                logger.warning(
                    "Failed to auto-close error bead %s for issue %s: %s",
                    bead_id, ident, exc,
                )
                continue
            # Drop the record so a fresh occurrence of the same
            # fingerprint will produce a new task.
            self._seen.pop(fp, None)

        return closed

    def _fingerprint(
        self,
        source: str,
        message: str,
        *,
        error_class: str | None = None,
    ) -> str:
        """Create a stable fingerprint for deduplication.

        Two paths:

        - **Explicit class** (``error_class`` given): the fingerprint hashes
          ``class=<error_class>`` alone, so every report with the same
          class collapses to one task within the dedup window — regardless
          of source, message, project, or Backlog subcommand. This is the
          operator's escape hatch for transient infra failures that fan out
          across many call sites in seconds.

        - **Free-form** (no class): normalize the message by stripping
          parts that vary across operationally-identical errors —
          timestamps, hex addresses, UUIDs, project names, Backlog command
          args, task-style identifiers, large numbers — then hash.

        Trade-off: broader fingerprints risk lumping unrelated errors into
        one task. The free-form normalization stays conservative; for the
        cases where a *single* root cause is known (e.g. Backlog timeouts), the
        caller opts in with ``error_class`` rather than us guessing from
        message text.
        """
        if error_class:
            raw = f"class={error_class}"
            return hashlib.sha256(raw.encode()).hexdigest()[:16]

        import re
        # Normalize: lowercase, strip hex addresses, UUIDs, timestamps, numbers
        normalized = message.lower()
        normalized = re.sub(r"0x[0-9a-f]+", "<addr>", normalized)
        normalized = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "<uuid>", normalized,
        )
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}[t ]\d{2}:\d{2}:\d{2}", "<ts>", normalized)

        # Strip "for project <name>" — operationally irrelevant which
        # project a fan-out failure happened in. Project names are
        # alphanumeric with optional ._- separators.
        normalized = re.sub(
            r"\bfor project [a-z0-9._-]+",
            "for project <project>",
            normalized,
        )

        # Strip quoted identifiers ("oompah-zlz_2-16h", 'TASK-42'). Keep
        # the quotes themselves so the message shape is preserved.
        normalized = re.sub(
            r"(['\"])[a-z][a-z0-9_]*(?:-[a-z0-9_]+)+\1",
            r"\1<id>\1",
            normalized,
        )

        # Collapse Backlog command invocations:
        # "backlog task list --plain" -> "backlog task list",
        # "backlog task view TASK-42" -> "backlog task view".
        # Keeps the command family + verb; drops everything after.
        normalized = re.sub(
            r"\bbacklog\s+([a-z][a-z0-9_-]*)\s+([a-z][a-z0-9_-]*)(?:\s+\S[^\n]*)?",
            r"backlog \1 \2",
            normalized,
        )

        # Tightened identifier normalization: catches task-style IDs
        # like "oompah-zlz_2-16h", "oompah-zlz_2-aup". Requires 2+ dash
        # segments to avoid eating ordinary hyphenated English words
        # ("for-loop", "non-empty", "use-case").
        normalized = re.sub(
            r"\b[a-z][a-z0-9_]*(?:-[a-z0-9_]+){2,}\b",
            "<id>",
            normalized,
        )

        normalized = re.sub(r"\b\d{4,}\b", "<num>", normalized)
        raw = f"{source}:{normalized}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _evict_oldest(self) -> None:
        """Remove the oldest half of fingerprint records."""
        by_age = sorted(self._seen.values(), key=lambda r: r.last_created)
        to_remove = by_age[: len(by_age) // 2]
        for r in to_remove:
            self._seen.pop(r.fingerprint, None)


class _BeadLoggingHandler(logging.Handler):
    """Logging handler that forwards ERROR+ records to the ErrorWatcher."""

    def __init__(self, watcher: ErrorWatcher):
        super().__init__()
        self._watcher = watcher

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            detail = message
            if record.exc_info and record.exc_info[1]:
                import traceback
                detail += "\n\n" + "".join(
                    traceback.format_exception(*record.exc_info)
                )
            # Use module name as more specific source
            source = f"backend:{record.module}"
            priority = 1 if record.levelno >= logging.CRITICAL else 2
            # Callers may attach context via ``logger.error(..., extra={
            # "issue_id": <id>})`` to tie the resulting bead to the
            # issue whose run produced the error.  This lets the
            # orchestrator auto-close the bead on retry success.
            issue_id = getattr(record, "issue_id", None)
            # Call sites can also pass an explicit class via
            # ``logger.error("...", extra={"error_class": "bd_failed"})``
            # to collapse fan-out failures (e.g. one Dolt slowdown that
            # produces N project-fetch errors) into a single bead.
            error_class = getattr(record, "error_class", None)
            self._watcher.report_error(
                source=source,
                message=message,
                detail=detail,
                priority=priority,
                issue_id=issue_id,
                error_class=error_class,
            )
        except Exception:
            # Never let handler errors propagate
            pass


# ---------------------------------------------------------------------------
# Log file patterns for detecting errors
# ---------------------------------------------------------------------------

# Matches common log-level keywords at ERROR or above.
# Handles formats like:
#   2024-01-01 12:00:00 ERROR ...
#   [ERROR] ...
#   ERROR: ...
#   level=error ...
_ERROR_LINE_RE = re.compile(
    r"(?i)\b(ERROR|CRITICAL|FATAL|SEVERE)\b"
)

# Priority mapping based on log level keywords.
_LEVEL_PRIORITY: dict[str, int] = {
    "critical": 1,
    "fatal": 1,
    "severe": 1,
    "error": 2,
}


def _detect_error_level(line: str) -> str | None:
    """Return the error level keyword if the line looks like an error, else None."""
    m = _ERROR_LINE_RE.search(line)
    if m:
        return m.group(1).lower()
    return None


def _priority_for_level(level: str) -> int:
    """Return a bead priority (0-4) for a detected log level."""
    return _LEVEL_PRIORITY.get(level, 2)


def _extract_message(line: str) -> str:
    """Extract the meaningful message portion from a log line.

    Strips common prefixes (timestamps, log-level tags) so the error
    message used for bead titles and fingerprinting is clean.
    """
    # Strip leading timestamp (ISO-8601 or common syslog-style)
    stripped = re.sub(
        r"^\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}[.,]?\d*\s*", "", line
    )
    # Strip leading log level keyword and punctuation
    stripped = re.sub(
        r"^[\[\(]?\s*(?:ERROR|CRITICAL|FATAL|SEVERE)\s*[\]\)]?\s*[:|-]?\s*",
        "", stripped, flags=re.IGNORECASE,
    )
    # Strip leading logger name (e.g. "com.example.Foo - ")
    stripped = re.sub(r"^[\w.]+\s*[-:]\s*", "", stripped)
    return stripped.strip() or line.strip()


class LogFileWatcher:
    """Watches an external log file and reports errors to an ErrorWatcher.

    Tails the log file using event-driven file-system notifications (via
    ``watchfiles``), scanning new lines for error-level messages.  When one
    is found, it calls ``error_watcher.report_error()`` which handles
    deduplication and bead creation.

    If the log file does not yet exist, the watcher monitors the parent
    directory until the file is created, then switches to watching the file
    directly.  This avoids any polling loop.

    Usage::

        watcher = LogFileWatcher(
            log_path="/var/log/myapp/error.log",
            error_watcher=error_watcher,
            source_name="myapp",
        )
        task = asyncio.create_task(watcher.start())
        # ... later ...
        watcher.stop()
        await task
    """

    def __init__(
        self,
        log_path: str,
        error_watcher: ErrorWatcher,
        source_name: str = "logfile",
    ):
        self._log_path = log_path
        self._error_watcher = error_watcher
        self._source_name = source_name
        self._running = False
        self._stop_event: asyncio.Event | None = None
        # Track file position so we only process new lines.
        self._file_offset: int = 0
        self._inode: int | None = None

    @property
    def log_path(self) -> str:
        return self._log_path

    @property
    def is_running(self) -> bool:
        return self._running

    def _watch_path(self) -> str:
        """Return the path to watch: the log file itself, or its parent dir.

        When the log file does not yet exist, we watch its parent directory
        and apply a filter so we only react to events on the target file.
        """
        if os.path.exists(self._log_path):
            return self._log_path
        parent = os.path.dirname(os.path.abspath(self._log_path))
        return parent if parent else "."

    def _make_watch_filter(self):
        """Return a ``watchfiles`` filter that matches only the target log file.

        Used when watching the parent directory so that unrelated changes
        (other files in the same directory) do not trigger spurious reads.
        """
        abs_log = os.path.abspath(self._log_path)

        def _filter(change, path: str) -> bool:  # type: ignore[override]
            return os.path.abspath(path) == abs_log

        return _filter

    async def start(self) -> None:
        """Start watching the log file (runs until ``stop()`` is called)."""
        self._running = True
        self._stop_event = asyncio.Event()
        logger.info(
            "LogFileWatcher started path=%s source=%s",
            self._log_path, self._source_name,
        )

        # Seek to end of file if it exists, so we only catch new errors.
        self._seek_to_end()

        try:
            await self._watch_loop()
        except asyncio.CancelledError:
            pass

        self._running = False
        logger.info("LogFileWatcher stopped path=%s", self._log_path)

    async def _watch_loop(self) -> None:
        """Event-driven inner loop using watchfiles.awatch().

        Watches the log file (or its parent directory when the file does not
        yet exist) and calls ``_poll_file()`` whenever a change is detected.
        The loop restarts automatically when the watch target changes (e.g.
        the file is created after we started watching the parent dir, or
        after a log rotation changes the inode).
        """
        assert self._stop_event is not None  # set by start()

        while not self._stop_event.is_set():
            watch_target = self._watch_path()
            watching_parent = watch_target != self._log_path

            try:
                watch_kwargs: dict = {
                    "stop_event": self._stop_event,
                    "recursive": False,
                }
                if watching_parent:
                    # Only react to events on the specific log file
                    watch_kwargs["watch_filter"] = self._make_watch_filter()

                async for _changes in awatch(watch_target, **watch_kwargs):
                    try:
                        self._poll_file()
                    except Exception as exc:
                        logger.debug(
                            "LogFileWatcher read error path=%s: %s",
                            self._log_path, exc,
                        )

                    # If we were watching the parent and the file now exists,
                    # restart the loop so we watch the file directly.
                    if watching_parent and os.path.exists(self._log_path):
                        break

                    if self._stop_event.is_set():
                        break

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # watchfiles can raise if the watch target disappears.
                # Back off briefly so we don't spin hard, then retry.
                logger.debug(
                    "LogFileWatcher watch error path=%s: %s",
                    self._log_path, exc,
                )
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    pass

    def stop(self) -> None:
        """Signal the watcher to stop at the next file-system event."""
        self._running = False
        if self._stop_event is not None:
            self._stop_event.set()

    def _seek_to_end(self) -> None:
        """Move the file offset to the end of the current file."""
        try:
            stat = os.stat(self._log_path)
            self._file_offset = stat.st_size
            self._inode = stat.st_ino
        except FileNotFoundError:
            self._file_offset = 0
            self._inode = None
        except OSError:
            self._file_offset = 0
            self._inode = None

    def _poll_file(self) -> None:
        """Read new lines from the log file and check for errors."""
        if not os.path.isfile(self._log_path):
            return

        try:
            stat = os.stat(self._log_path)
        except OSError:
            return

        # Detect log rotation (inode changed or file truncated).
        if self._inode is not None and stat.st_ino != self._inode:
            # File was rotated — start reading from beginning of new file.
            self._file_offset = 0
            self._inode = stat.st_ino
        elif stat.st_size < self._file_offset:
            # File was truncated — reset offset.
            self._file_offset = 0

        if stat.st_size <= self._file_offset:
            return  # No new data.

        try:
            with open(self._log_path, "r", errors="replace") as f:
                f.seek(self._file_offset)
                new_data = f.read()
                self._file_offset = f.tell()
                self._inode = stat.st_ino
        except OSError:
            return

        for line in new_data.splitlines():
            line = line.strip()
            if not line:
                continue
            level = _detect_error_level(line)
            if level:
                message = _extract_message(line)
                priority = _priority_for_level(level)
                self._error_watcher.report_error(
                    source=f"log:{self._source_name}",
                    message=message,
                    detail=line,
                    priority=priority,
                )


class ProjectLogWatcherManager:
    """Manages LogFileWatcher instances for all projects with a ``log_path``.

    Call ``sync_watchers(projects)`` whenever the project list may have
    changed (e.g. on each orchestrator tick or after project CRUD).  It
    starts watchers for new projects, stops watchers for removed projects,
    and updates watchers whose log_path changed.
    """

    def __init__(self, error_watcher_factory):
        """
        Args:
            error_watcher_factory: Callable ``(project_id) -> ErrorWatcher``
                that returns the ErrorWatcher for a given project. The
                manager calls this to get project-specific watchers so
                beads are created in the correct project.
        """
        self._error_watcher_factory = error_watcher_factory
        # project_id -> (LogFileWatcher, asyncio.Task)
        self._watchers: dict[str, tuple[LogFileWatcher, asyncio.Task]] = {}

    def sync_watchers(self, projects: list) -> None:
        """Synchronize running watchers with the current project list.

        Starts new watchers, stops removed ones, restarts changed ones.
        Each *project* must have ``id``, ``name``, and ``log_path`` attributes.
        """
        desired: dict[str, tuple[str, str]] = {}  # project_id -> (log_path, name)
        for project in projects:
            if project.log_path:
                desired[project.id] = (project.log_path, project.name)

        # Stop watchers for projects that no longer need one.
        for pid in list(self._watchers):
            if pid not in desired:
                self._stop_watcher(pid)
            elif self._watchers[pid][0].log_path != desired[pid][0]:
                # log_path changed — restart.
                self._stop_watcher(pid)

        # Start watchers for new / restarted projects.
        for pid, (log_path, name) in desired.items():
            if pid not in self._watchers:
                self._start_watcher(pid, log_path, name)

    def stop_all(self) -> None:
        """Stop all running watchers."""
        for pid in list(self._watchers):
            self._stop_watcher(pid)

    def _start_watcher(self, project_id: str, log_path: str, source_name: str) -> None:
        error_watcher = self._error_watcher_factory(project_id)
        watcher = LogFileWatcher(
            log_path=log_path,
            error_watcher=error_watcher,
            source_name=source_name,
        )
        task = asyncio.ensure_future(watcher.start())
        self._watchers[project_id] = (watcher, task)
        logger.info(
            "Started log file watcher project=%s path=%s",
            project_id, log_path,
        )

    def _stop_watcher(self, project_id: str) -> None:
        entry = self._watchers.pop(project_id, None)
        if entry:
            watcher, task = entry
            watcher.stop()
            task.cancel()
            logger.info("Stopped log file watcher project=%s", project_id)
