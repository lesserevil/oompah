"""Error watcher: intercepts backend errors and creates beads for tracking.

Provides two mechanisms for detecting errors:

1. **Python logging handler** — ``ErrorWatcher.install_log_handler()``
   hooks into Python's ``logging`` system to catch ERROR+ records from the
   oompah backend and create beads automatically.

2. **Log file watcher** — ``LogFileWatcher`` monitors an external log file
   for error lines and feeds them to an ``ErrorWatcher``.  Any project can
   use this by setting a ``log_path`` on its :class:`~oompah.models.Project`.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oompah.tracker import BeadsTracker

logger = logging.getLogger(__name__)

# Don't create beads for the same error more than once within this window.
_DEDUP_WINDOW_SECONDS = 3600  # 1 hour

# Max number of fingerprints to keep in memory (LRU-ish eviction).
_MAX_FINGERPRINTS = 500


@dataclass
class _ErrorRecord:
    """Tracks when we last created a bead for a given error fingerprint."""
    fingerprint: str
    last_created: float = 0.0


class ErrorWatcher:
    """Watches for errors and creates beads to track them.

    Hooks into Python's logging system via a custom handler. Also accepts
    explicit error reports (e.g. from a frontend error endpoint).
    """

    def __init__(self, tracker: BeadsTracker, project_id: str | None = None):
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
    ) -> str | None:
        """Report an error and create a bead if not a duplicate.

        Args:
            source: Where the error came from (e.g. "backend", "frontend").
            message: Short error summary (used for title + fingerprinting).
            detail: Longer description / stack trace.
            priority: Bead priority (0=critical, 4=backlog). Default 2.

        Returns:
            The bead identifier if one was created, None if deduplicated.
        """
        fp = self._fingerprint(source, message)

        now = time.monotonic()
        record = self._seen.get(fp)
        if record and (now - record.last_created) < _DEDUP_WINDOW_SECONDS:
            return None

        # Evict old entries if we're at capacity
        if len(self._seen) >= _MAX_FINGERPRINTS:
            self._evict_oldest()

        # Create the bead
        title = f"[{source}] {message}"
        if len(title) > 200:
            title = title[:197] + "..."

        description = detail or message

        try:
            issue = self._tracker.create_issue(
                title=title,
                issue_type="bug",
                description=description,
                priority=priority,
                initial_status="deferred",
            )
            self._seen[fp] = _ErrorRecord(fingerprint=fp, last_created=now)
            logger.info(
                "Created error bead %s for [%s] %s",
                issue.identifier, source, message[:80],
            )
            return issue.identifier
        except Exception as exc:
            # Don't let error tracking errors cascade
            logger.debug("Failed to create error bead: %s", exc)
            return None

    def _fingerprint(self, source: str, message: str) -> str:
        """Create a stable fingerprint for deduplication.

        Strips variable parts (timestamps, IDs, memory addresses) to group
        similar errors together.
        """
        import re
        # Normalize: lowercase, strip hex addresses, UUIDs, timestamps, numbers
        normalized = message.lower()
        normalized = re.sub(r"0x[0-9a-f]+", "<addr>", normalized)
        normalized = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "<uuid>", normalized,
        )
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "<ts>", normalized)
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
            self._watcher.report_error(
                source=source,
                message=message,
                detail=detail,
                priority=priority,
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

    Tails the log file asynchronously, scanning new lines for error-level
    messages.  When one is found, it calls ``error_watcher.report_error()``
    which handles deduplication and bead creation.

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
        poll_interval: float = 2.0,
    ):
        self._log_path = log_path
        self._error_watcher = error_watcher
        self._source_name = source_name
        self._poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None
        # Track file position so we only process new lines.
        self._file_offset: int = 0
        self._inode: int | None = None

    @property
    def log_path(self) -> str:
        return self._log_path

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start watching the log file (runs until ``stop()`` is called)."""
        self._running = True
        logger.info("LogFileWatcher started path=%s source=%s", self._log_path, self._source_name)

        # Seek to end of file if it exists, so we only catch new errors.
        self._seek_to_end()

        while self._running:
            try:
                self._poll_file()
            except Exception as exc:
                logger.debug("LogFileWatcher poll error path=%s: %s", self._log_path, exc)
            await asyncio.sleep(self._poll_interval)

        logger.info("LogFileWatcher stopped path=%s", self._log_path)

    def stop(self) -> None:
        """Signal the watcher to stop on its next poll cycle."""
        self._running = False

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
