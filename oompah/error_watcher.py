"""Error watcher: intercepts backend errors and creates tracker tasks for tracking.

Provides two mechanisms for detecting errors:

1. **Python logging handler** — ``ErrorWatcher.install_log_handler()``
   hooks into Python's ``logging`` system to catch ERROR+ records from the
   oompah backend and create tasks automatically.

2. **Log file watcher** — ``LogFileWatcher`` monitors an external log file
   for error lines and feeds them to an ``ErrorWatcher``.  Any project can
   use this by setting a ``log_path`` on its :class:`~oompah.models.Project`.

Task creation goes through the :class:`~oompah.tracker.TrackerProtocol`.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass

from watchfiles import awatch

from oompah.statuses import is_terminal_status
from oompah.tracker import TrackerProtocol

logger = logging.getLogger(__name__)

# Don't create tasks for the same error more than once within this window.
_DEDUP_WINDOW_SECONDS = 3600  # 1 hour

# Max number of fingerprints to keep in memory (LRU-ish eviction).
_MAX_FINGERPRINTS = 500


@dataclass
class _ErrorRecord:
    """Tracks when we last created a task for a given error fingerprint.

    ``task_id`` and ``issue_id`` are populated when ``report_error`` is
    called with an ``issue_id``; they let the orchestrator auto-close the
    task when the originating issue's retry path succeeds.
    """
    fingerprint: str
    last_created: float = 0.0
    task_id: str | None = None
    issue_id: str | None = None


# Window during which a retry-success can auto-close a previously filed
# error task. Tasks older than this stay open for operator inspection.
# inspect manually).
_AUTO_CLOSE_WINDOW_SECONDS = 1800  # 30 minutes

# After report_error fires for a fingerprint, we wait at least this long
# before allowing auto-close on it.  Without this guard, a successful
# retry on issue A could close a task whose same-fingerprint failure is
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
        self._handler: _TaskLoggingHandler | None = None

    def install_log_handler(self, logger_name: str = "oompah") -> None:
        """Install a logging handler that creates tasks for ERROR+ log records."""
        root = logging.getLogger(logger_name)
        self._handler = _TaskLoggingHandler(self)
        self._handler.setLevel(logging.ERROR)
        root.addHandler(self._handler)

    def uninstall_log_handler(self, logger_name: str = "oompah") -> None:
        """Remove the logging handler."""
        if self._handler:
            logging.getLogger(logger_name).removeHandler(self._handler)
            self._handler = None

    def _tracker_identity(self) -> tuple[str, str | None, str | None]:
        """Return ``(kind, owner, repo)`` for the underlying tracker backend."""
        owner = getattr(self._tracker, "owner", None)
        repo = getattr(self._tracker, "repo", None)
        if owner and repo:
            return ("github_issues", str(owner), str(repo))
        return (type(self._tracker).__name__.lower(), None, None)

    def _tracker_label(self) -> str:
        """Return a human-readable identifier for the underlying tracker backend.

        Uses duck-typing to detect GitHub Issues (owner/repo attributes
        present); falls back to the class name for unrecognised adapters.

        Avoids importing ``github_tracker`` directly to prevent circular
        dependencies; the duck-type check is sufficient and forward-
        compatible with future third-party adapters that expose the same
        ``owner``/``repo`` interface.
        """
        kind, owner, repo = self._tracker_identity()
        if kind == "github_issues" and owner and repo:
            return f"github_issues:{owner}/{repo}"
        return kind

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
        """Report an error and create a task if not a duplicate.

        Args:
            source: Where the error came from (e.g. "backend", "frontend").
            message: Short error summary (used for title + fingerprinting).
            detail: Longer description / stack trace.
            priority: Task priority (0=critical, 4=backlog). Default 2.
            issue_id: Optional id of the issue whose run triggered this
                error. When supplied, the watcher links the resulting
                task to the issue so :meth:`auto_close_for_issue` can
                close it once the issue's retry path succeeds.
            error_class: Optional explicit error classification (e.g.
                ``"connection_refused"``). When given,
                deduplication collapses *all* reports with the same class
                to a single task within the dedup window — regardless of
                the exact message text, project, or subcommand. Use this
                for known operational/infra failure modes that fan out
                across many call sites.

        Returns:
            The task identifier if one was created, None if deduplicated.
        """
        fp = self._fingerprint(source, message, error_class=error_class)

        now = time.monotonic()
        record = self._seen.get(fp)
        if record and (now - record.last_created) < _DEDUP_WINDOW_SECONDS:
            # Refresh last_created so the recent-error guard in
            # auto_close_for_issue treats this fingerprint as still
            # actively firing.  Also remember the originating issue if
            # the previous record didn't have one (so subsequent
            # success can auto-close the existing task).
            record.last_created = now
            if issue_id and not record.issue_id:
                record.issue_id = issue_id
            return None

        # Evict old entries if we're at capacity
        if len(self._seen) >= _MAX_FINGERPRINTS:
            self._evict_oldest()

        existing_id = self._find_existing_error_task(fp)
        if existing_id:
            self._seen[fp] = _ErrorRecord(
                fingerprint=fp,
                last_created=now,
                task_id=existing_id,
                issue_id=issue_id,
            )
            self._comment_on_duplicate_error(
                existing_id,
                source,
                message,
                issue_id=issue_id,
            )
            logger.info(
                "Deduplicated error task for [%s] %s against existing %s",
                source, message[:80], existing_id,
            )
            return None

        # Create the task
        title = f"[{source}] {message}"
        if len(title) > 200:
            title = title[:197] + "..."

        # Build a structured description that passes validate_issue() for the
        # bug issue type.  Includes intake-validator-required sections
        # (Problem, Steps to Reproduce, Actual Behavior, Expected Behavior,
        # Acceptance Criteria) plus diagnostic metadata for deduplication.
        description = self._build_structured_description(
            source, message, fp,
            detail=detail,
            error_class=error_class,
            issue_id=issue_id,
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
            logger.debug("Failed to create error task: %s", exc)
            return None

        self._seen[fp] = _ErrorRecord(
            fingerprint=fp,
            last_created=now,
            task_id=issue.identifier,
            issue_id=issue_id,
        )
        logger.info(
            "Created error task %s for [%s] %s%s",
            issue.identifier, source, message[:80],
            f" (issue={issue_id})" if issue_id else "",
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
        """Auto-close every error task linked to ``issue_id``.

        Called by the orchestrator after a worker run finishes
        successfully *via the retry path* (attempt > 0).  Each matching
        record's task is closed with a "retry succeeded; transient"
        reason and popped from ``_seen`` so that a future error with
        the same fingerprint will create a fresh task.

        Records are skipped if:

        * ``last_created`` is older than ``max_age_seconds`` — the
          task is too stale to be plausibly the same incident.
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
                resolution comment posted on each closed task.
            max_age_seconds: age cutoff (default 30 min).
            quiet_seconds: minimum time since the most recent
                fingerprint hit before auto-close is allowed (default
                60 s).

        Returns:
            List of task identifiers that were auto-closed.
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
            if not record.task_id:
                # No task was ever filed for this record; nothing to close.
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

            task_id = record.task_id
            comment_body = (
                "Auto-closed by error_watcher: the originating issue "
                f"({ident}) recovered via retry."
            )
            if resolution_link:
                comment_body += f" Resolution: {resolution_link}"
            try:
                # Post a comment first so the audit trail survives close.
                # TASK-461.6 AC #2: the comment is posted to the task's
                # own tracker (self._tracker), which is the same backend
                # that created the task.  This guarantees that auto-close
                # comments on error tasks always route to the source-task
                # backend, even when the triggering issue lives in a
                # different tracker.
                try:
                    self._tracker.add_comment(task_id, comment_body)
                except Exception as exc:  # pragma: no cover - best effort
                    logger.debug(
                        "Could not post resolution comment on %s: %s",
                        task_id, exc,
                    )
                self._tracker.close_issue(
                    task_id,
                    reason="retry succeeded; transient (auto-closed by error_watcher)",
                )
                logger.info(
                    "Auto-closed transient error task %s (issue=%s resolved)",
                    task_id, ident,
                )
                closed.append(task_id)
            except Exception as exc:
                logger.warning(
                    "Failed to auto-close error task %s for issue %s: %s",
                    task_id, ident, exc,
                )
                continue
            # Drop the record so a fresh occurrence of the same
            # fingerprint will produce a new task.
            self._seen.pop(fp, None)

        return closed

    def _build_structured_description(
        self,
        source: str,
        message: str,
        fp: str,
        *,
        detail: str | None = None,
        error_class: str | None = None,
        issue_id: str | None = None,
    ) -> str:
        """Build a structured bug description that passes ``validate_issue()``.

        Generates the five markdown sections required by the intake validator
        for bug-type issues (Problem, Steps to Reproduce, Actual Behavior,
        Expected Behavior, Acceptance Criteria) and appends the standard
        diagnostic metadata footer.

        The generated text is intentionally generic — it is derived entirely
        from available runtime context (source, message, detail, error_class,
        project_id, tracker identity) without any LLM call.  An operator or
        agent may subsequently refine the content, but the task will pass
        ``validate_issue()`` without manual editing.
        """
        project_id = self._project_id or "global"
        tracker_kind, tracker_owner, tracker_repo = self._tracker_identity()
        tracker_label = self._tracker_label()
        class_note = f" (error class: `{error_class}`)" if error_class else ""

        parts: list[str] = []

        # ------------------------------------------------------------------ #
        # 1. Problem
        # ------------------------------------------------------------------ #
        parts.append("## Problem\n")
        parts.append(
            f"Oompah detected a backend error{class_note} from `{source}`:\n\n"
            f"> {message}\n"
        )
        if detail and detail != message:
            _cap = 2000
            detail_body = detail[:_cap]
            if len(detail) > _cap:
                detail_body += "\n…(truncated)"
            parts.append(f"\n**Error detail:**\n\n```\n{detail_body}\n```\n")

        # ------------------------------------------------------------------ #
        # 2. Steps to Reproduce
        # ------------------------------------------------------------------ #
        parts.append("\n## Steps to Reproduce\n")
        parts.append(f"1. Run oompah with `{source}` active.\n")
        if project_id != "global":
            parts.append(
                f"2. Let oompah operate on the `{project_id}` project "
                f"(tracker: `{tracker_label}`).\n"
            )
        else:
            parts.append(
                "2. Let oompah execute the operation that involves "
                f"`{source}` (tracker: `{tracker_label}`).\n"
            )
        parts.append(
            "3. Observe that the error is captured by `error_watcher` "
            "and auto-filed as this task.\n"
        )

        # ------------------------------------------------------------------ #
        # 3. Actual Behavior
        # ------------------------------------------------------------------ #
        parts.append("\n## Actual Behavior\n")
        parts.append(
            f"An error occurs in `{source}` and is recorded by oompah's "
            f"`error_watcher`:\n\n> {message}\n"
        )

        # ------------------------------------------------------------------ #
        # 4. Expected Behavior
        # ------------------------------------------------------------------ #
        parts.append("\n## Expected Behavior\n")
        parts.append(
            f"The operation in `{source}` should complete successfully, "
            "or degrade gracefully with a clear actionable message. "
            "No unhandled error should be auto-filed as a task during "
            "normal operation.\n"
        )

        # ------------------------------------------------------------------ #
        # 5. Acceptance Criteria
        # ------------------------------------------------------------------ #
        parts.append("\n## Acceptance Criteria\n")
        parts.append(
            f"- The error from `{source}` no longer occurs, or is handled "
            "gracefully so `error_watcher` is not triggered.\n"
            "- The root cause is identified and resolved, or documented as "
            "a known acceptable failure with explicit handling.\n"
            "- No regression: other error types continue to be reported "
            "correctly by `error_watcher`.\n"
        )

        # ------------------------------------------------------------------ #
        # Diagnostic metadata footer
        # ------------------------------------------------------------------ #
        meta_lines = [
            "\n---",
            "*Auto-filed by oompah error_watcher*",
            f"- source_project: {project_id}",
            f"- tracker: {tracker_label}",
            f"- tracker_kind: {tracker_kind}",
            f"- fingerprint: {fp}",
            f"- dedup_fingerprint: {fp}",
        ]
        if tracker_owner:
            meta_lines.append(f"- tracker_owner: {tracker_owner}")
        if tracker_repo:
            meta_lines.append(f"- tracker_repo: {tracker_repo}")
        if issue_id:
            meta_lines.append(f"- source_issue: {issue_id}")
        if error_class:
            meta_lines.append(f"- error_class: {error_class}")

        return "".join(parts) + "\n".join(meta_lines)

    def _find_existing_error_task(self, fp: str) -> str | None:
        """Return a non-terminal auto-filed task already tracking ``fp``.

        The in-memory dedup table prevents bursts within one process. This
        tracker scan prevents a restart or a second watcher from creating a
        duplicate task for the same durable error_watcher fingerprint.
        """
        try:
            issues = list(self._tracker.fetch_all_issues())
        except Exception as exc:
            logger.debug("Failed to scan existing error tasks: %s", exc)
            return None

        needle = f"dedup_fingerprint: {fp}"
        for issue in issues:
            if is_terminal_status(getattr(issue, "state", None)):
                continue
            description = str(getattr(issue, "description", "") or "")
            if needle in description:
                return str(getattr(issue, "identifier", "") or "")
        return None

    def _comment_on_duplicate_error(
        self,
        identifier: str,
        source: str,
        message: str,
        *,
        issue_id: str | None = None,
    ) -> None:
        """Best-effort audit trail for a duplicate error occurrence."""
        if not identifier:
            return
        comment = (
            "Duplicate error_watcher occurrence suppressed; this task already "
            f"tracks the same dedup fingerprint.\n\nSource: `{source}`\n\n"
            f"Message: {message}"
        )
        if issue_id:
            comment += f"\n\nSource issue: `{issue_id}`"
        try:
            self._tracker.add_comment(identifier, comment, author="oompah")
        except Exception as exc:
            logger.debug(
                "Could not comment on duplicate error task %s: %s",
                identifier, exc,
            )

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
          of source, message, or project. This is the
          operator's escape hatch for transient infra failures that fan out
          across many call sites in seconds.

        - **Free-form** (no class): normalize the message by stripping
          parts that vary across operationally-identical errors —
          timestamps, hex addresses, UUIDs, project names, task-style
          identifiers, large numbers — then hash.

        Trade-off: broader fingerprints risk lumping unrelated errors into
        one task. The free-form normalization stays conservative; for the
        cases where a *single* root cause is known, the
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


class _TaskLoggingHandler(logging.Handler):
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
            # "issue_id": <id>})`` to tie the resulting task to the
            # issue whose run produced the error.  This lets the
            # orchestrator auto-close the task on retry success.
            issue_id = getattr(record, "issue_id", None)
            # Call sites can also pass an explicit class via
            # ``logger.error("...", extra={"error_class": "project_fetch_failed"})``
            # to collapse fan-out failures (e.g. one Dolt slowdown that
            # produces N project-fetch errors) into a single task.
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
    """Return a task priority (0-4) for a detected log level."""
    return _LEVEL_PRIORITY.get(level, 2)


def _extract_message(line: str) -> str:
    """Extract the meaningful message portion from a log line.

    Strips common prefixes (timestamps, log-level tags) so the error
    message used for task titles and fingerprinting is clean.
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
    deduplication and task creation.

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
                tasks are created in the correct project.
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
