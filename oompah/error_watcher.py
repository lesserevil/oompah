"""Error watcher: intercepts backend errors and creates beads for tracking."""

from __future__ import annotations

import hashlib
import logging
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
