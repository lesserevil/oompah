"""Async backlog refresh manager for Release Delivery candidate discovery (OOMPAH-251).

Provides a per-(project_id, branch) background refresh model so that the
GET /release-delivery/backlog endpoint can return immediately with a cached
result while discovery runs asynchronously.

Design
------
- One :class:`BacklogRefreshJob` is maintained per ``(project_id, branch)`` key.
- The job runs :meth:`~oompah.release_delivery_backlog.ItemBacklogService.get_backlog`
  in a background asyncio task via ``asyncio.to_thread``.
- The last completed :class:`~oompah.release_delivery_backlog.BacklogResult` is
  retained so callers can serve stale data while a refresh is in progress.
- Progress is tracked at coarse phases emitted by the backlog service via the
  optional ``progress_callback`` parameter.
- :class:`BacklogRefreshManager` is thread-safe (uses :class:`threading.Lock`
  for state mutations) and safe for concurrent asyncio tasks.

Phases (in order)
-----------------
1. ``pending``   — job created, not yet started.
2. ``loading_merged`` — fetching Merged issue list from the tracker.
3. ``resolving_commits`` — resolving source commits per merged issue (git/SCM).
4. ``comparing_ancestry`` — batch ancestry check against the release branch.
5. ``preparing_rows``  — fetching titles and building item rows.
6. ``diagnostics`` — computing tracker_only flags for unassociated commits.
7. ``complete``  — job finished successfully; result is cached.
8. ``failed``    — job raised an exception; previous result retained if any.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from oompah.release_delivery_backlog import BacklogResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Suggested phases in execution order.  Exposed so tests can import them.
PHASES = (
    "pending",
    "loading_merged",
    "resolving_commits",
    "comparing_ancestry",
    "preparing_rows",
    "diagnostics",
    "complete",
    "failed",
)

#: Default TTL (seconds) before a completed result triggers a new refresh.
DEFAULT_RESULT_TTL_S: float = 300.0  # 5 minutes


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class RefreshStatus:
    """Observable state of one backlog refresh job.

    Attributes:
        phase: Current phase name (see :data:`PHASES`).
        completed: Number of items/steps completed within the current phase.
        total: Total items/steps in the current phase, or ``None`` when unknown.
        elapsed_s: Seconds since the job started.
        error: Human-readable error description, set when ``phase == "failed"``.
        has_result: ``True`` when a cached result is available (may be stale).
        result_completed_at: Monotonic timestamp when the last result was
            produced, or ``None`` when no result has been cached yet.
    """

    phase: str = "pending"
    completed: int = 0
    total: int | None = None
    elapsed_s: float = 0.0
    error: str | None = None
    has_result: bool = False
    result_completed_at: float | None = None

    def to_dict(self) -> dict:
        """Serialise to a JSON-friendly dict."""
        d: dict = {
            "phase": self.phase,
            "completed": self.completed,
            "elapsed_s": round(self.elapsed_s, 3),
            "has_result": self.has_result,
        }
        if self.total is not None:
            d["total"] = self.total
        if self.error is not None:
            d["error"] = self.error
        return d


# ---------------------------------------------------------------------------
# Internal job object
# ---------------------------------------------------------------------------


class _RefreshJob:
    """Internal mutable state for one refresh job.

    All attribute reads/writes must happen under the manager's ``_lock``.
    """

    def __init__(self, *, has_result: bool = False) -> None:
        self.phase: str = "pending"
        self.completed: int = 0
        self.total: int | None = None
        self.started_at: float = time.monotonic()
        self.error: str | None = None
        self.result: BacklogResult | None = None
        self.result_completed_at: float | None = None
        self.task: asyncio.Task | None = None
        self._has_result: bool = has_result

    def get_status(self, *, lock: threading.Lock) -> RefreshStatus:
        with lock:
            elapsed = time.monotonic() - self.started_at
            return RefreshStatus(
                phase=self.phase,
                completed=self.completed,
                total=self.total,
                elapsed_s=elapsed,
                error=self.error,
                has_result=self._has_result,
                result_completed_at=self.result_completed_at,
            )

    def is_running(self) -> bool:
        """True when the asyncio task is active (not None and not done)."""
        return self.task is not None and not self.task.done()


# ---------------------------------------------------------------------------
# BacklogRefreshManager
# ---------------------------------------------------------------------------


class BacklogRefreshManager:
    """Per-(project_id, branch) background refresh job manager.

    Usage::

        manager = BacklogRefreshManager()

        # In an async HTTP handler:
        status, cached = await manager.get_or_start(
            project_id, branch,
            service=item_backlog_service,
            tracker=tracker,
        )
        if cached is not None:
            return serve_cached(cached, filter=..., query=...)
        else:
            return serve_empty_with_status(status)

    Thread safety
    -------------
    All state mutations use :attr:`_lock` (a :class:`threading.Lock`) so the
    class is safe from both async event-loop tasks and ``asyncio.to_thread``
    workers.

    Args:
        result_ttl_s: Seconds after which a completed result is considered
            stale and triggers a new refresh on the next GET request.
            Set to ``0`` to disable TTL-based auto-refresh.
    """

    def __init__(self, *, result_ttl_s: float = DEFAULT_RESULT_TTL_S) -> None:
        self._jobs: dict[tuple[str, str], _RefreshJob] = {}
        # RLock (reentrant lock) is required because get_status() acquires
        # the lock and is sometimes called while the caller already holds it
        # (e.g. from within get_or_start()'s locked section).
        self._lock = threading.RLock()
        self._result_ttl_s = result_ttl_s

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    def get_status(self, project_id: str, branch: str) -> RefreshStatus | None:
        """Return the current :class:`RefreshStatus` for the given key, or ``None``.

        This method is synchronous and safe to call from any thread or async context.
        """
        key = (project_id, branch)
        with self._lock:
            job = self._jobs.get(key)
        if job is None:
            return None
        return job.get_status(lock=self._lock)

    def get_cached_result(self, project_id: str, branch: str) -> BacklogResult | None:
        """Return the last completed :class:`BacklogResult`, or ``None``.

        The result is retained even when a new refresh is running (stale-while-revalidate).
        """
        key = (project_id, branch)
        with self._lock:
            job = self._jobs.get(key)
            if job is None:
                return None
            return job.result

    def is_running(self, project_id: str, branch: str) -> bool:
        """Return ``True`` when a refresh job is currently active."""
        key = (project_id, branch)
        with self._lock:
            job = self._jobs.get(key)
            if job is None:
                return False
            return job.is_running()

    async def get_or_start(
        self,
        project_id: str,
        branch: str,
        *,
        service: Any,
        filter: str = "all",
        query: str | None = None,
        tracker: Any | None = None,
    ) -> tuple[RefreshStatus, BacklogResult | None]:
        """Return cached result and start a background refresh if one isn't running.

        When a completed result exists AND is within the TTL, no new refresh is
        started.  When the result is stale (or absent), a new refresh task is
        created and the last result (if any) is returned immediately so the
        caller can serve stale data to the client.

        Args:
            project_id: Project identifier (cache key component).
            branch: Release branch name (cache key component).
            service: :class:`~oompah.release_delivery_backlog.ItemBacklogService`
                instance to run discovery.
            filter: Passed to ``service.get_backlog`` (default: ``"all"`` so
                the cached result is filter-agnostic and filtered at read time).
            query: Passed to ``service.get_backlog``.
            tracker: Passed to ``service.get_backlog``.

        Returns:
            ``(status, cached_result)`` tuple.  ``cached_result`` is ``None``
            when no completed result exists yet.
        """
        key = (project_id, branch)

        with self._lock:
            job = self._jobs.get(key)
            cached_result = job.result if job is not None else None
            has_cached = cached_result is not None

            if job is not None and job.is_running():
                # Already running — return current status + cached result
                return job.get_status(lock=self._lock), cached_result

            # Decide whether to start a refresh:
            # - No job ever ran → always start
            # - Previous job failed → start fresh
            # - Previous job completed but result is stale → start fresh
            should_start = (
                job is None
                or job.phase == "failed"
                or (
                    job.phase == "complete"
                    and self._result_ttl_s > 0
                    and job.result_completed_at is not None
                    and (time.monotonic() - job.result_completed_at) > self._result_ttl_s
                )
            )
            if not should_start:
                # Result is fresh — return it directly without starting a new job
                return job.get_status(lock=self._lock), cached_result  # type: ignore[union-attr]

            # Create a new job, carrying over any existing result
            new_job = _RefreshJob(has_result=has_cached)
            new_job.result = cached_result
            new_job.result_completed_at = job.result_completed_at if job else None
            self._jobs[key] = new_job

        # Start the async task outside the lock
        task = asyncio.create_task(
            self._run(key, new_job, service=service, filter=filter, query=query, tracker=tracker),
            name=f"backlog-refresh-{project_id}-{branch}",
        )
        with self._lock:
            new_job.task = task

        logger.debug(
            "BacklogRefreshManager: started refresh for %s/%s",
            project_id,
            branch,
        )
        return new_job.get_status(lock=self._lock), cached_result

    async def trigger_refresh(
        self,
        project_id: str,
        branch: str,
        *,
        service: Any,
        filter: str = "all",
        query: str | None = None,
        tracker: Any | None = None,
    ) -> RefreshStatus:
        """Force a new refresh, cancelling any in-flight job.

        This is the ``POST /backlog/refresh`` handler path.  Any in-progress
        job is cancelled and a new one started.  The last completed result is
        preserved so stale data can still be served while the new job runs.

        Args:
            project_id: Project identifier.
            branch: Release branch name.
            service: :class:`~oompah.release_delivery_backlog.ItemBacklogService`.
            filter: Passed to ``service.get_backlog``.
            query: Passed to ``service.get_backlog``.
            tracker: Passed to ``service.get_backlog``.

        Returns:
            :class:`RefreshStatus` for the newly started job (phase ``"pending"``).
        """
        key = (project_id, branch)

        # Cancel the existing task if running
        with self._lock:
            existing = self._jobs.get(key)

        if existing is not None and existing.is_running() and existing.task is not None:
            existing.task.cancel()
            try:
                await existing.task
            except (asyncio.CancelledError, Exception):
                pass

        with self._lock:
            old = self._jobs.get(key)
            cached_result = old.result if old is not None else None
            has_cached = cached_result is not None
            result_completed_at = old.result_completed_at if old is not None else None

            new_job = _RefreshJob(has_result=has_cached)
            new_job.result = cached_result
            new_job.result_completed_at = result_completed_at
            self._jobs[key] = new_job

        task = asyncio.create_task(
            self._run(key, new_job, service=service, filter=filter, query=query, tracker=tracker),
            name=f"backlog-refresh-{project_id}-{branch}",
        )
        with self._lock:
            new_job.task = task

        logger.debug(
            "BacklogRefreshManager: triggered manual refresh for %s/%s",
            project_id,
            branch,
        )
        return new_job.get_status(lock=self._lock)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _run(
        self,
        key: tuple[str, str],
        job: _RefreshJob,
        *,
        service: Any,
        filter: str,
        query: str | None,
        tracker: Any | None,
    ) -> None:
        """Background task: run the synchronous backlog service and emit progress."""

        def _progress(phase: str, completed: int, total: int | None) -> None:
            with self._lock:
                job.phase = phase
                job.completed = completed
                job.total = total

        try:
            with self._lock:
                job.phase = "loading_merged"

            result = await asyncio.to_thread(
                service.get_backlog,
                selected_branch=key[1],
                filter="all",  # Always cache the unfiltered result; filter applied at read time
                query=query,
                tracker=tracker,
                progress_callback=_progress,
            )

            with self._lock:
                job.result = result
                job.result_completed_at = time.monotonic()
                job.phase = "complete"
                job.completed = 0
                job.total = None
                job.error = None
                job._has_result = True

            logger.debug(
                "BacklogRefreshManager: refresh complete for %s/%s — %d items",
                key[0],
                key[1],
                len(result.items),
            )

        except asyncio.CancelledError:
            with self._lock:
                job.phase = "failed"
                job.error = "refresh cancelled"
            raise

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "BacklogRefreshManager: refresh failed for %s/%s: %s",
                key[0],
                key[1],
                exc,
                exc_info=True,
            )
            with self._lock:
                job.phase = "failed"
                job.error = str(exc)
                # Preserve _has_result so callers know stale data is available
