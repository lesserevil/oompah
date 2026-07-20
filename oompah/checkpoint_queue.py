"""Checkpoint coalescing queue for state-branch task mutations (OOMPAH-257).

Reduces Git commit volume by buffering multiple in-memory task mutations and
flushing them as a single atomic commit after a debounce window, rather than
committing once per mutation.

Design reference: plans/state-branch-design.md § 5 (Checkpoint coalescing policy)
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CheckpointQueue:
    """Single-writer debounced checkpoint queue for state-branch task mutations.

    Coalesces multiple in-process task mutations into one atomic git commit by
    buffering them during a configurable debounce window.  A hard max-delay
    deadline ensures that pending mutations are flushed even under continuous
    write activity (bounding worst-case data loss to ``max_delay_ms``
    milliseconds).

    Thread-safe.  All public methods may be called from any thread.

    Timer threads call ``_timer_flush()`` which wraps ``flush()`` in exception
    handling so a flush failure does not crash the timer daemon thread.

    Parameters
    ----------
    debounce_ms:
        Milliseconds to wait for additional mutations before flushing.
        The timer is reset on each ``schedule()`` call.  Default: 5000 ms.
    max_delay_ms:
        Maximum milliseconds a pending mutation can wait before a forced flush
        occurs, regardless of ongoing write activity.
        Must be >= ``debounce_ms`` + 1000; auto-corrected with an error log if
        not (design § 5.2).  Default: 30000 ms.
    flush_fn:
        Zero-argument callable that commits and pushes all pending in-memory
        mutations.  Called from the flush path (either the debounce timer, the
        max-delay timer, or a mandatory-flush caller).  Must be idempotent when
        there is nothing to commit (e.g. no staged changes → no-op commit).
    _clock:
        Monotonic clock function (default: ``time.monotonic``).  Injected for
        testing.
    _timer_factory:
        Timer constructor with the same signature as ``threading.Timer``
        (default: ``threading.Timer``).  Injected for testing.
    """

    def __init__(
        self,
        *,
        debounce_ms: int = 5000,
        max_delay_ms: int = 30000,
        flush_fn: Callable[[], None],
        _clock: Callable[[], float] | None = None,
        _timer_factory: Callable[..., Any] | None = None,
    ) -> None:
        # Validate and auto-correct constraint from design § 5.2.
        if max_delay_ms < debounce_ms + 1000:
            corrected = debounce_ms + 1000
            logger.error(
                "state_branch_checkpoint_max_delay_ms (%d ms) must be >= "
                "state_branch_checkpoint_debounce_ms (%d ms) + 1000; "
                "auto-correcting to %d ms (see plans/state-branch-design.md § 5.2)",
                max_delay_ms,
                debounce_ms,
                corrected,
            )
            max_delay_ms = corrected

        self._debounce_ms = debounce_ms
        self._max_delay_ms = max_delay_ms
        self._flush_fn = flush_fn
        self._clock: Callable[[], float] = _clock if _clock is not None else time.monotonic
        self._timer_factory: Callable[..., Any] = (
            _timer_factory if _timer_factory is not None else threading.Timer
        )

        self._lock = threading.RLock()
        self._pending: int = 0
        self._debounce_timer: Any | None = None  # threading.Timer instance
        self._max_delay_timer: Any | None = None  # threading.Timer instance
        self._first_pending_at: float | None = None
        self._last_push_at: str | None = None
        self._push_failures: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def schedule(self) -> None:
        """Register one pending mutation and (re-)schedule the debounce flush.

        Increments the pending-mutation counter.  Starts the max-delay timer on
        the first pending mutation; resets the debounce timer on every call.
        """
        with self._lock:
            self._pending += 1
            now = self._clock()

            if self._first_pending_at is None:
                # First mutation in this window — start the hard deadline timer.
                self._first_pending_at = now
                max_timer = self._timer_factory(
                    self._max_delay_ms / 1000.0,
                    self._timer_flush,
                    args=("max_delay",),
                )
                max_timer.daemon = True  # type: ignore[attr-defined]
                max_timer.start()
                self._max_delay_timer = max_timer

            # Reset debounce timer on every new mutation.
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            debounce_timer = self._timer_factory(
                self._debounce_ms / 1000.0,
                self._timer_flush,
                args=("debounce",),
            )
            debounce_timer.daemon = True  # type: ignore[attr-defined]
            debounce_timer.start()
            self._debounce_timer = debounce_timer

        logger.debug(
            "Checkpoint scheduled: %d pending mutation(s); "
            "debounce=%.1fs max_delay=%.1fs",
            self._pending,
            self._debounce_ms / 1000.0,
            self._max_delay_ms / 1000.0,
        )

    def flush(self, *, reason: str) -> int:
        """Flush all pending mutations immediately.

        Cancels both timers, resets the pending counter, and calls ``flush_fn``
        to commit+push.  Thread-safe.  Idempotent — returns 0 immediately when
        there are no pending mutations.

        Parameters
        ----------
        reason:
            Human-readable reason string logged at DEBUG level and used in
            the commit message when available (e.g. ``"terminal_status"``,
            ``"human_edit"``, ``"shutdown"``, ``"debounce"``, ``"max_delay"``).

        Returns
        -------
        int
            Number of mutations that were flushed.  Zero when there was nothing
            pending (idempotent call).
        """
        with self._lock:
            count = self._pending
            if count == 0:
                return 0

            # Cancel both timers while holding the lock.
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None
            if self._max_delay_timer is not None:
                self._max_delay_timer.cancel()
                self._max_delay_timer = None

            self._pending = 0
            self._first_pending_at = None

        # Run the flush function OUTSIDE the _lock to avoid nested-lock
        # deadlocks with OompahMarkdownTracker._write_lock.
        try:
            logger.debug(
                "Checkpoint flushing %d mutation(s) (reason=%s)", count, reason
            )
            self._flush_fn()
            self._last_push_at = datetime.now(timezone.utc).isoformat()
            logger.debug(
                "Checkpoint flushed: %d mutation(s) committed (reason=%s)",
                count,
                reason,
            )
            return count
        except Exception:
            self._push_failures += 1
            logger.exception(
                "Checkpoint flush FAILED (reason=%s); push_failures=%d",
                reason,
                self._push_failures,
            )
            raise

    def shutdown(self) -> None:
        """Flush any pending mutations and cancel timers for graceful shutdown."""
        # flush() is idempotent — safe even if pending == 0.
        self.flush(reason="shutdown")

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def pending_mutations(self) -> int:
        """Number of mutations waiting in the buffer for the next flush."""
        with self._lock:
            return self._pending

    @property
    def last_push_at(self) -> str | None:
        """ISO-8601 timestamp of the last successful flush, or None."""
        return self._last_push_at

    @property
    def push_failures(self) -> int:
        """Count of flush/push errors since this instance was created."""
        return self._push_failures

    def get_observability_dict(self, *, branch: str) -> dict[str, Any]:
        """Return the per-project ``state_branch`` block for GET /api/v1/state.

        Example output (design § 5.7)::

            {
                "branch": "oompah/state/proj-14849f1b",
                "last_push_at": "2026-07-20T16:00:00Z",
                "pending_mutations": 0,
                "push_failures": 0,
                "alert": null,
            }
        """
        return {
            "branch": branch,
            "last_push_at": self._last_push_at,
            "pending_mutations": self.pending_mutations,
            "push_failures": self._push_failures,
            "alert": "push_failed" if self._push_failures > 0 else None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _timer_flush(self, reason: str) -> None:
        """Callback invoked by timer daemon threads.

        Wraps ``flush()`` so that exceptions do not crash the timer thread.
        """
        try:
            self.flush(reason=reason)
        except Exception:
            # Already logged in flush() — silently swallow here so the timer
            # thread terminates cleanly.
            pass
