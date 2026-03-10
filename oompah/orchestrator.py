"""Orchestrator: polling, dispatch, reconciliation, and retry management."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from oompah.agent import AgentError, AgentEvent, AgentSession
from oompah.api_agent import AgentActivity, ApiAgentSession
from oompah.config import ServiceConfig, WorkflowError, load_workflow, validate_dispatch_config
from oompah.events import EventBus, EventType
from oompah.models import (
    AgentProfile,
    AgentTotals,
    BlockerRef,
    Issue,
    LiveSession,
    OrchestratorState,
    RetryEntry,
    RunningEntry,
)
from oompah.focus import analyze_completed_issue, save_suggestion, select_focus
from oompah.prompt import PromptError, build_continuation_prompt, render_prompt
from oompah.projects import ProjectError, ProjectStore
from oompah.providers import ProviderStore
from oompah.scm import detect_provider, extract_repo_slug
from oompah.tracker import BeadsTracker, TrackerError
from oompah.workspace import WorkspaceError, WorkspaceManager

import json
import os

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_STATE_PATH = ".oompah/service_state.json"


class DispatchEventType(str, Enum):
    """Types of events that drive the event-driven dispatch loop.

    Using ``str`` as the base allows direct use as dict keys and logging.
    """

    # A worker completed, failed, or hit a terminal state — re-evaluate dispatch
    WORKER_EXIT = "worker_exit"
    # An external caller (API, user action) requested an immediate refresh
    REFRESH_REQUESTED = "refresh_requested"
    # A retry timer fired — re-evaluate the specific issue
    RETRY_FIRED = "retry_fired"
    # Safety-net: periodic full sync to catch anything missed
    FULL_SYNC = "full_sync"


@dataclass
class DispatchEvent:
    """A single event driving the orchestrator's dispatch loop.

    Attributes:
        event_type: What happened.
        issue_id: The specific issue affected, if any (may be None for global events).
        payload: Optional extra context (e.g., exit reason for WORKER_EXIT).
    """

    event_type: DispatchEventType
    issue_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class Orchestrator:
    """Owns the poll tick, dispatch decisions, and in-memory runtime state."""

    def __init__(self, config: ServiceConfig, workflow_path: str,
                 provider_store: ProviderStore | None = None,
                 project_store: ProjectStore | None = None,
                 state_path: str | None = None):
        self.config = config
        self.workflow_path = workflow_path
        self.provider_store = provider_store or ProviderStore()
        self.project_store = project_store or ProjectStore()
        self._state_path = state_path or DEFAULT_SERVICE_STATE_PATH
        self.state = OrchestratorState(
            poll_interval_ms=config.poll_interval_ms,
            max_concurrent_agents=config.max_concurrent_agents,
        )
        # Legacy single tracker (used when no projects configured)
        self.tracker = BeadsTracker(
            active_states=config.tracker_active_states,
            terminal_states=config.tracker_terminal_states,
        )
        # Per-project trackers, keyed by project_id
        self._project_trackers: dict[str, BeadsTracker] = {}
        self.workspace_mgr = WorkspaceManager(
            workspace_root=config.workspace_root,
            hooks={
                "after_create": config.hooks_after_create,
                "before_run": config.hooks_before_run,
                "after_run": config.hooks_after_run,
                "before_remove": config.hooks_before_remove,
            },
            hooks_timeout_ms=config.hooks_timeout_ms,
        )
        self._prompt_template: str = ""
        self._tick_task: asyncio.Task | None = None
        self._stopping = False
        # Bug fix: load persisted paused state from disk so it survives
        # service restarts. Previously _paused was always initialized to False.
        self._paused = self._load_paused_state()
        self._restart_requested = False
        self._alerts: list[dict[str, str]] = []  # {"level": "warning", "message": "..."}
        self._rate_limit_until: float = 0.0  # epoch time until which dispatch is paused
        # EventBus: typed pub/sub for internal event-driven communication.
        # The legacy _observers/_state_only_observers/_activity_observers lists
        # are kept for backward compatibility with server.py, but internally
        # the EventBus is the canonical dispatch mechanism.
        self.event_bus: EventBus = EventBus()
        self._observers: list[Any] = []
        self._state_only_observers: list[Any] = []
        self._activity_observers: list[Any] = []
        self._refresh_requested = asyncio.Event()
        # Event-driven dispatch queue: all events that should wake the
        # dispatch loop are posted here.  The loop blocks on this queue
        # instead of sleeping for poll_interval_ms on every cycle.
        self._dispatch_queue: asyncio.Queue[DispatchEvent] = asyncio.Queue()
        # Timestamp (monotonic) of the last full _tick() run.
        # Updated after each _tick() call so _full_sync_due() can determine
        # when the next safety-net full sync should fire and to support
        # logging the safety-net message when the interval elapses.
        self._last_full_sync: float = 0.0
        # Dedicated thread pool for tick operations so they don't compete
        # with agent tool-execution threads on the default pool.
        self._tick_pool = ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="tick"
        )
        # Watchdog state
        self._last_watchdog_run: float = 0.0
        self._watchdog_interval_s: float = 300.0  # 5 minutes
        self._last_candidates: list[Issue] = []
        self._orphan_reset_counts: dict[str, int] = {}
        self._yolo_limbo_ticks: dict[str, int] = {}

    def _load_state(self) -> dict:
        """Load persisted service state from disk."""
        if not os.path.exists(self._state_path):
            return {}
        try:
            with open(self._state_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load service state from %s: %s", self._state_path, exc)
            return {}

    def _load_paused_state(self) -> bool:
        """Load persisted paused state from disk. Returns False if not found."""
        return bool(self._load_state().get("paused", False))

    def _save_state(self, **updates: object) -> None:
        """Persist service state to disk, merging with existing state."""
        try:
            data = self._load_state()
            data.update(updates)
            os.makedirs(os.path.dirname(self._state_path) or ".", exist_ok=True)
            with open(self._state_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as exc:
            logger.warning("Failed to save service state to %s: %s", self._state_path, exc)

    def _save_paused_state(self) -> None:
        """Persist paused state to disk."""
        self._save_state(paused=self._paused)

    def reload_config(self, config: ServiceConfig, prompt_template: str) -> None:
        """Apply new config and prompt template from workflow reload."""
        self.config = config
        self._prompt_template = prompt_template
        self.state.poll_interval_ms = config.poll_interval_ms
        self.state.max_concurrent_agents = config.max_concurrent_agents
        self.tracker = BeadsTracker(
            active_states=config.tracker_active_states,
            terminal_states=config.tracker_terminal_states,
        )
        # Clear cached per-project trackers so they pick up new state config
        self._project_trackers.clear()
        self.workspace_mgr = WorkspaceManager(
            workspace_root=config.workspace_root,
            hooks={
                "after_create": config.hooks_after_create,
                "before_run": config.hooks_before_run,
                "after_run": config.hooks_after_run,
                "before_remove": config.hooks_before_remove,
            },
            hooks_timeout_ms=config.hooks_timeout_ms,
        )
        # Reset last full sync so the new full_sync_interval_ms takes effect
        # immediately rather than waiting for the old interval to expire.
        self._last_full_sync = 0.0
        logger.info("Config reloaded poll_interval_ms=%d full_sync_interval_ms=%d max_agents=%d",
                     config.poll_interval_ms, config.full_sync_interval_ms,
                     config.max_concurrent_agents)

    def set_prompt_template(self, template: str) -> None:
        self._prompt_template = template

    def pause(self) -> None:
        """Pause: stop all running agents and prevent new dispatches."""
        self._paused = True
        self._save_paused_state()
        # Terminate all running agents (keep workspaces for resume)
        asyncio.ensure_future(self._terminate_all_running())
        logger.info("Orchestrator paused — all agents stopped")
        self.event_bus.emit(EventType.ORCHESTRATOR_PAUSED, {})
        self._notify_observers()

    async def _terminate_all_running(self) -> None:
        """Terminate all running agents without cleaning workspaces."""
        for issue_id in list(self.state.running.keys()):
            await self._terminate_running(issue_id, cleanup_workspace=False)
        self._notify_observers()

    def unpause(self) -> None:
        """Resume dispatching — agents will be re-dispatched on next tick."""
        self._paused = False
        self._save_paused_state()
        logger.info("Orchestrator unpaused")
        # Post a REFRESH_REQUESTED event so the dispatch loop wakes immediately.
        # Also set the legacy event for any code that still awaits it.
        self._refresh_requested.set()
        self._post_event(DispatchEvent(
            event_type=DispatchEventType.REFRESH_REQUESTED,
            payload={"reason": "unpaused"},
        ))
        self.event_bus.emit(EventType.ORCHESTRATOR_RESUMED, {})
        self._notify_observers()

    async def graceful_restart(self, drain_timeout_s: float = 60) -> None:
        """Drain running agents and restart the process.

        1. Pause dispatch (no new agents)
        2. Wait up to drain_timeout_s for running agents to finish
        3. Save any still-running issue IDs for re-dispatch after restart
        4. Signal the main loop to stop (which triggers os.execv in __main__)
        """
        logger.info("Graceful restart requested (drain_timeout=%.0fs)", drain_timeout_s)
        self._paused = True
        self._notify_observers()

        # Wait for running agents to drain
        deadline = time.monotonic() + drain_timeout_s
        while self.state.running and time.monotonic() < deadline:
            remaining = len(self.state.running)
            logger.info("Draining: %d agent(s) still running, %.0fs remaining",
                        remaining, deadline - time.monotonic())
            await asyncio.sleep(2)

        # Save issue IDs of anything still running for re-dispatch
        restart_issues = []
        for issue_id, entry in self.state.running.items():
            restart_issues.append({
                "issue_id": issue_id,
                "identifier": entry.issue.identifier if entry.issue else issue_id,
                "project_id": entry.issue.project_id if entry.issue else None,
            })

        if restart_issues:
            logger.info("Saving %d undrained issue(s) for re-dispatch after restart",
                        len(restart_issues))

        self._save_state(
            paused=False,
            restart_issues=restart_issues,
        )

        # Signal the main loop to stop and restart
        self._restart_requested = True
        self._stopping = True

    @property
    def wants_restart(self) -> bool:
        return self._restart_requested

    def _tracker_for_project(self, project_id: str) -> BeadsTracker:
        """Get or create a BeadsTracker for a project."""
        if project_id in self._project_trackers:
            return self._project_trackers[project_id]
        project = self.project_store.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        tracker = BeadsTracker(
            active_states=self.config.tracker_active_states,
            terminal_states=self.config.tracker_terminal_states,
            cwd=project.repo_path,
        )
        self._project_trackers[project_id] = tracker
        return tracker

    def _tracker_for_issue(self, issue: Issue) -> BeadsTracker:
        """Get the appropriate tracker for an issue (project-specific or legacy)."""
        if issue.project_id:
            return self._tracker_for_project(issue.project_id)
        return self.tracker

    @property
    def is_paused(self) -> bool:
        return self._paused

    def request_refresh(self) -> None:
        """Request an immediate poll+reconciliation cycle."""
        self._refresh_requested.set()
        self._post_event(DispatchEvent(
            event_type=DispatchEventType.REFRESH_REQUESTED,
            payload={"reason": "api_request"},
        ))

    async def startup_cleanup(self) -> None:
        """Remove workspaces/worktrees for issues in terminal states."""
        projects = self.project_store.list_all()
        if projects:
            for project in projects:
                try:
                    tracker = self._tracker_for_project(project.id)
                    terminal_issues = tracker.fetch_issues_by_states(
                        self.config.tracker_terminal_states
                    )
                    for issue in terminal_issues:
                        try:
                            self.project_store.remove_worktree(project.id, issue.identifier)
                            logger.info("Cleaned terminal worktree project=%s issue=%s",
                                        project.name, issue.identifier)
                        except Exception as exc:
                            logger.warning("Failed to clean worktree project=%s issue=%s error=%s",
                                           project.name, issue.identifier, exc)
                except (TrackerError, ProjectError) as exc:
                    logger.warning("Startup cleanup failed for project %s: %s", project.name, exc)
        else:
            try:
                terminal_issues = self.tracker.fetch_issues_by_states(
                    self.config.tracker_terminal_states
                )
                for issue in terminal_issues:
                    try:
                        self.workspace_mgr.remove_workspace(issue.identifier)
                        logger.info("Cleaned terminal workspace issue_identifier=%s",
                                    issue.identifier)
                    except Exception as exc:
                        logger.warning("Failed to clean workspace issue_identifier=%s error=%s",
                                       issue.identifier, exc)
            except TrackerError as exc:
                logger.warning("Startup terminal cleanup failed: %s", exc)

    async def _recover_restart_issues(self) -> None:
        """Re-dispatch issues that were running when a graceful restart happened."""
        state = self._load_state()
        restart_issues = state.get("restart_issues", [])
        if not restart_issues:
            return

        # Clear the restart_issues from state immediately
        self._save_state(restart_issues=[])

        logger.info("Recovering %d issue(s) from graceful restart", len(restart_issues))
        for entry in restart_issues:
            issue_id = entry.get("issue_id")
            identifier = entry.get("identifier", issue_id)
            project_id = entry.get("project_id")
            if not issue_id:
                continue
            try:
                if project_id:
                    tracker = self._tracker_for_project(project_id)
                else:
                    tracker = self.tracker
                # Re-open the issue so it gets picked up on the next tick
                tracker.update_issue(identifier, status="open")
                logger.info("Marked %s as open for re-dispatch after restart", identifier)
            except (TrackerError, ProjectError) as exc:
                logger.warning("Failed to recover issue %s: %s", identifier, exc)

    def _full_sync_due(self) -> bool:
        """Return True if a safety-net full sync is due.

        A full sync is due when:
        - No full sync has ever run (startup, ``_last_full_sync == 0.0``), OR
        - More than ``full_sync_interval_ms`` milliseconds have elapsed since
          the last full sync.
        """
        if self._last_full_sync == 0.0:
            return True
        elapsed_ms = (time.monotonic() - self._last_full_sync) * 1000
        return elapsed_ms >= self.config.full_sync_interval_ms

    def _post_event(self, event: DispatchEvent) -> None:
        """Put an event onto the dispatch queue (thread-safe, non-blocking).

        Callers that run from the event loop can call this directly.
        Callers from threads should use asyncio.get_event_loop().call_soon_threadsafe
        if they need to post from outside the loop (rare — most callers are async).
        """
        try:
            self._dispatch_queue.put_nowait(event)
        except asyncio.QueueFull:
            # The queue is unbounded, so this should never happen in practice.
            logger.warning("Dispatch queue unexpectedly full; dropping event %s", event.event_type)

    async def _full_sync_loop(self) -> None:
        """Background task: post FULL_SYNC events at the configured safety-net interval.

        This replaces the old poll_interval_ms sleep — a full _tick() is still
        run periodically, but at a much longer cadence (full_sync_interval_ms,
        default 5 min) as a consistency safety net rather than the primary
        dispatch mechanism.
        """
        while not self._stopping:
            interval_s = self.config.full_sync_interval_ms / 1000.0
            await asyncio.sleep(interval_s)
            if not self._stopping:
                self._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))

    async def run(self) -> None:
        """Main event loop: event-driven dispatch with a periodic full-sync safety net.

        The loop blocks on the internal dispatch queue instead of sleeping for
        poll_interval_ms.  Events are posted by:

        - ``_on_worker_exit()`` when a worker finishes or fails
        - ``request_refresh()`` for API/user-triggered refreshes
        - ``unpause()`` to restart dispatch after a pause
        - ``_on_retry_timer()`` when a retry timer fires
        - ``_full_sync_loop()`` for the periodic safety-net full sync

        A full ``_tick()`` (world scan) is run for FULL_SYNC events and for the
        initial startup tick.  For WORKER_EXIT and REFRESH_REQUESTED events,
        ``_tick()`` is also run because it's the simplest correct behavior
        (targeted optimisations can be layered on top later without changing
        the loop contract).
        """
        await self.startup_cleanup()
        await self._recover_restart_issues()
        full_sync_interval_s = self.config.full_sync_interval_ms / 1000.0
        logger.info(
            "Orchestrator starting event-driven loop "
            "full_sync_interval_ms=%d (safety-net poll_interval_ms=%d kept for compat)",
            self.config.full_sync_interval_ms,
            self.state.poll_interval_ms,
        )

        # Start the safety-net full-sync background task.
        full_sync_task = asyncio.create_task(
            self._full_sync_loop(), name="full-sync-loop"
        )

        async def _run_tick() -> None:
            """Run _tick() and update _last_full_sync afterwards."""
            if self._full_sync_due() and self._last_full_sync != 0.0:
                logger.info(
                    "Safety-net full sync triggered (%.0fs since last full sync, interval=%.0fs)",
                    (time.monotonic() - self._last_full_sync),
                    self.config.full_sync_interval_ms / 1000,
                )
            await self._tick()
            self._last_full_sync = time.monotonic()

        try:
            # Run an initial tick on startup to catch anything already pending.
            await _run_tick()

            while not self._stopping:
                try:
                    event = await self._dispatch_queue.get()
                except asyncio.CancelledError:
                    break

                if self._stopping:
                    break

                logger.debug("Dispatch loop received event: %s issue_id=%s",
                             event.event_type, event.issue_id)

                # All current event types result in a full _tick().
                # Future optimisations can add targeted handlers per event type
                # (e.g. only reconcile on WORKER_EXIT) without changing this
                # loop's structure.
                await _run_tick()

        finally:
            full_sync_task.cancel()
            try:
                await full_sync_task
            except (asyncio.CancelledError, Exception):
                pass

    async def stop(self) -> None:
        """Gracefully stop the orchestrator."""
        self._stopping = True
        # Terminate all running agents
        for issue_id, entry in list(self.state.running.items()):
            await self._terminate_running(issue_id, cleanup_workspace=False)
        # Cancel retry timers
        for issue_id, retry in list(self.state.retry_attempts.items()):
            if retry.timer_handle and not retry.timer_handle.cancelled():
                retry.timer_handle.cancel()
        logger.info("Orchestrator stopped")

    async def _tick(self) -> None:
        """One poll-and-dispatch cycle.

        Delegates to targeted handlers:
        1. _handle_reconcile()        — stall detection + tracker state refresh
        2. _handle_review_check()     — forge API: reviews + merged branches
        3. _handle_dispatch_needed()  — candidates fetch, blocker resolution, dispatch
        4. _handle_yolo_review()      — YOLO merge actions, auto-archive, merged-labeling
        5. _handle_auto_update()      — git pull + restart when idle
        """
        t0 = time.monotonic()

        # 1. Reconcile running agents against tracker
        await self._handle_reconcile()
        t1 = time.monotonic()

        # 2. Validate config before doing any expensive work
        errors = validate_dispatch_config(self.config)
        if errors:
            logger.error("Dispatch validation failed: %s", "; ".join(errors))
            self._notify_observers()
            return

        # 3. Fetch forge state (reviews + merged branches) — populates caches
        await self._handle_review_check()
        t2 = time.monotonic()

        # 4. Fetch candidates and dispatch eligible issues
        t3_start = time.monotonic()
        await self._handle_dispatch_needed()
        t3 = time.monotonic()

        # 5. YOLO actions, auto-archive, merged-labeling (uses cached forge state)
        yolo_ms, archive_ms, merged_ms = await self._handle_yolo_review()
        t4 = time.monotonic()

        # 5b. Watchdog: detect and fix stuck issues (periodic, lightweight)
        self._maybe_run_watchdog()

        total_ms = (t4 - t0) * 1000
        if total_ms > 2000:
            logger.warning(
                "Slow tick: %.0fms (reconcile=%.0f reviews=%.0f dispatch=%.0f "
                "yolo=%.0f archive=%.0f merged=%.0f)",
                total_ms,
                (t1 - t0) * 1000,
                (t2 - t1) * 1000,
                (t3 - t3_start) * 1000,
                yolo_ms, archive_ms, merged_ms,
            )

        self._notify_observers()

        # 6. Auto-update when idle (no agents, no retries)
        await self._handle_auto_update()

    async def _handle_reconcile(self) -> None:
        """Reconcile running agents: stall detection + tracker state refresh.

        This handler runs every tick. It checks for stalled agents and
        refreshes the tracker state for all running issues.
        """
        await self._reconcile()

    async def _handle_review_check(self) -> None:
        """Fetch forge state: open reviews and merged branches.

        Populates ``_reviews_cache``, ``_unmerged_review_branches``, and
        ``_merged_branches`` used by dispatch gating and YOLO actions.
        """
        self._reviews_cache = {}  # reset per tick — shared by PR branches + YOLO
        loop = asyncio.get_event_loop()
        reviews_task = loop.run_in_executor(self._tick_pool, self._fetch_all_reviews)
        merged_task = loop.run_in_executor(self._tick_pool, self._fetch_all_merged_branches)
        reviews_by_project, merged_branches = await asyncio.gather(
            reviews_task, merged_task
        )
        self._reviews_cache = reviews_by_project
        self._merged_branches = merged_branches
        # Derive unmerged review branches from cached reviews
        self._unmerged_review_branches = {
            r.source_branch
            for reviews in reviews_by_project.values()
            for r in reviews
            if r.source_branch
        }

    async def _handle_dispatch_needed(self) -> None:
        """Fetch candidates, resolve blockers, and dispatch eligible issues."""
        self._blocker_state_cache = {}  # reset per fetch cycle
        loop = asyncio.get_event_loop()

        # Fetch candidates from all trackers in parallel
        candidates = await loop.run_in_executor(
            self._tick_pool, self._fetch_all_candidates
        )
        self._last_candidates = candidates

        # Pre-resolve blocker states in thread (internally parallel)
        await loop.run_in_executor(
            self._tick_pool, self._pre_resolve_blockers, candidates
        )

        # Sort and dispatch regular (non-epic) issues
        sorted_issues = self._sort_for_dispatch(candidates)
        for issue in sorted_issues:
            if self._available_slots() <= 0:
                break
            if self._should_dispatch(issue):
                await self._dispatch(issue, attempt=None)

        # Dispatch epic planning agents for open epics without children
        epics_to_plan = await loop.run_in_executor(
            self._tick_pool, self._plan_open_epics, candidates
        )
        for epic in epics_to_plan:
            if self._available_slots() <= 0:
                break
            await self._dispatch(epic, attempt=None)

        # Auto-close epics whose children are all done
        await asyncio.get_event_loop().run_in_executor(
            self._tick_pool, self._auto_close_completed_epics, candidates
        )

        # Reset orphaned in_progress issues (no agent, no retry)
        self._reset_orphaned_in_progress(candidates)

    async def _handle_yolo_review(self) -> tuple[float, float, float]:
        """Run YOLO merge actions, auto-archive, and merged-issue labeling.

        Uses the forge state cached by ``_handle_review_check()`` to avoid
        redundant API calls within the same tick.

        Returns timing tuple (yolo_ms, archive_ms, merged_ms) for telemetry.
        """
        loop = asyncio.get_event_loop()

        def _timed_yolo():
            t = time.monotonic()
            self._yolo_review_actions_sync()
            return (time.monotonic() - t) * 1000

        def _timed_archive():
            t = time.monotonic()
            self._auto_archive()
            return (time.monotonic() - t) * 1000

        def _timed_merged_labels():
            t = time.monotonic()
            self._label_merged_issues()
            return (time.monotonic() - t) * 1000

        yolo_ms, archive_ms, merged_ms = await asyncio.gather(
            loop.run_in_executor(self._tick_pool, _timed_yolo),
            loop.run_in_executor(self._tick_pool, _timed_archive),
            loop.run_in_executor(self._tick_pool, _timed_merged_labels),
        )
        return yolo_ms, archive_ms, merged_ms

    async def _handle_auto_update(self) -> None:
        """Trigger git auto-update when the orchestrator is idle.

        Idle means no agents are running and no retries are pending.
        """
        if not self.state.running and not self.state.retry_attempts:
            await asyncio.get_event_loop().run_in_executor(
                self._tick_pool, self._check_auto_update
            )

    def _check_auto_update(self) -> None:
        """Pull new code and restart if idle and remote has changes."""
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=repo_dir, capture_output=True, text=True, timeout=30,
            )
            result = subprocess.run(
                ["git", "rev-list", "HEAD..origin/main", "--count"],
                cwd=repo_dir, capture_output=True, text=True, timeout=10,
            )
            count = int(result.stdout.strip()) if result.returncode == 0 else 0
            if count == 0:
                # Clear any previous auto-update alert
                self._alerts = [a for a in self._alerts if a.get("source") != "auto_update"]
                return

            logger.info("Auto-update: %d new commit(s) on origin/main, pulling and restarting", count)
            pull = subprocess.run(
                ["git", "pull", "--ff-only", "origin", "main"],
                cwd=repo_dir, capture_output=True, text=True, timeout=60,
            )
            if pull.returncode != 0:
                msg = f"Auto-update failed: git pull returned error — {pull.stderr.strip()[:200]}"
                logger.warning("Auto-update: git pull failed: %s", pull.stderr.strip()[:200])
                # Replace any existing auto-update alert
                self._alerts = [a for a in self._alerts if a.get("source") != "auto_update"]
                self._alerts.append({"level": "warning", "source": "auto_update", "message": msg})
                return

            # Trigger graceful restart
            self._restart_requested = True
            self._stopping = True
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            msg = f"Auto-update failed: {exc}"
            logger.debug("Auto-update check failed: %s", exc)
            self._alerts = [a for a in self._alerts if a.get("source") != "auto_update"]
            self._alerts.append({"level": "warning", "source": "auto_update", "message": msg})

    def _fetch_all_candidates(self) -> list[Issue]:
        """Fetch candidate issues from all configured projects (parallel)."""
        projects = self.project_store.list_all()
        if not projects:
            # No projects configured — use legacy tracker
            try:
                return self.tracker.fetch_candidate_issues()
            except TrackerError as exc:
                logger.error("Tracker fetch failed: %s", exc)
                return []

        def _fetch_for_project(project) -> list[Issue]:
            try:
                tracker = self._tracker_for_project(project.id)
                issues = tracker.fetch_candidate_issues()
                for issue in issues:
                    issue.project_id = project.id
                return issues
            except (TrackerError, ProjectError) as exc:
                logger.error("Fetch failed for project %s: %s", project.name, exc)
                return []

        all_candidates: list[Issue] = []
        with ThreadPoolExecutor(max_workers=min(len(projects), 4)) as pool:
            for issues in pool.map(_fetch_for_project, projects):
                all_candidates.extend(issues)
        return all_candidates

    def _available_slots(self) -> int:
        return max(self.state.max_concurrent_agents - len(self.state.running), 0)

    def _per_state_available(self, state: str) -> bool:
        normalized = state.strip().lower()
        limit = self.config.max_concurrent_agents_by_state.get(normalized)
        if limit is None:
            return True
        count = sum(
            1
            for e in self.state.running.values()
            if e.issue.state.strip().lower() == normalized
        )
        return count < limit

    def _project_has_open_review(self, project_id: str | None) -> bool:
        """Return True if the project has at least one open MR/PR.

        Used to serialize dispatch: don't start a new agent for a project
        that already has an open review waiting to merge, which would create
        a second in-flight MR that could conflict with the first.

        Only applies to projects (issues with a project_id). For legacy
        issues without a project, this check is skipped.
        """
        if not project_id:
            return False
        reviews_cache = getattr(self, "_reviews_cache", {})
        project_reviews = reviews_cache.get(project_id, [])
        # Any non-draft open review counts as "in flight"
        return any(not r.draft for r in project_reviews)

    def _should_dispatch_epic(self, issue: Issue) -> bool:
        """Check whether an epic should be dispatched for planning.

        An epic is dispatchable for planning when:
        - It is in an active state (open)
        - It has no existing children (hasn't been planned yet)
        - It is not already running, claimed, retrying, or completed
        - Standard guards (paused, budget, slots) pass
        """
        if self._paused:
            return False
        if self._is_rate_limited():
            return False
        if issue.issue_type != "epic":
            return False
        if "human-only" in issue.labels:
            return False
        if not issue.id or not issue.identifier or not issue.title or not issue.state:
            return False
        state_norm = issue.state.strip().lower()
        if state_norm not in [s.strip().lower() for s in self.config.tracker_active_states]:
            return False
        if state_norm in [s.strip().lower() for s in self.config.tracker_terminal_states]:
            return False
        if issue.id in self.state.running:
            return False
        if issue.id in self.state.claimed:
            return False
        if issue.id in self.state.retry_attempts:
            return False
        if issue.id in self.state.completed:
            return False
        if self._available_slots() <= 0:
            return False
        if not self._check_budget():
            return False
        # Check if epic already has children — if so, it's already been planned
        children = self._fetch_epic_children(issue)
        if children:
            return False
        return True

    def _fetch_epic_children(self, epic: Issue) -> list[Issue]:
        """Fetch existing child issues for an epic.

        Returns a list of child issues, or empty if none exist or on error.
        """
        try:
            tracker = self._tracker_for_issue(epic)
            return tracker.fetch_children(epic.id)
        except Exception as exc:
            logger.debug("Failed to fetch children for epic %s: %s", epic.identifier, exc)
            return []

    def _auto_close_completed_epics(self, candidates: list[Issue]) -> None:
        """Auto-close epics whose children are all in terminal states.

        Scans deferred/open epics that have children; if every child is
        in a terminal state, the epic is closed automatically.
        """
        terminal_norms = {s.strip().lower() for s in self.config.tracker_terminal_states}
        active_norms = {s.strip().lower() for s in self.config.tracker_active_states}
        non_terminal = active_norms | {"deferred", "in_progress"}

        for issue in candidates:
            if issue.issue_type != "epic":
                continue
            state_norm = issue.state.strip().lower()
            if state_norm in terminal_norms:
                continue  # already closed

            children = self._fetch_epic_children(issue)
            if not children:
                continue  # no children — nothing to roll up

            all_terminal = all(
                c.state.strip().lower() in terminal_norms for c in children
            )
            if all_terminal:
                try:
                    tracker = self._tracker_for_issue(issue)
                    tracker.close_issue(issue.identifier)
                    logger.info(
                        "Auto-closed epic %s — all %d children in terminal state",
                        issue.identifier,
                        len(children),
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to auto-close epic %s: %s", issue.identifier, exc
                    )

    def _plan_open_epics(self, candidates: list[Issue]) -> list[Issue]:
        """Identify open epics that need planning and return them for dispatch.

        An epic needs planning if it's in an active state and has no children.
        """
        epics_to_plan: list[Issue] = []
        for issue in candidates:
            if issue.issue_type != "epic":
                continue
            if self._should_dispatch_epic(issue):
                epics_to_plan.append(issue)
        return epics_to_plan

    def _should_dispatch(self, issue: Issue) -> bool:
        def _reject(reason: str) -> bool:
            # Track consecutive rejections for stuck-issue detection
            key = issue.id
            prev_reason, count = self.state.reject_streak.get(key, ("", 0))
            if reason == prev_reason:
                count += 1
            else:
                count = 1
            self.state.reject_streak[key] = (reason, count)
            if count >= 10 and count % 10 == 0:
                logger.warning("Stuck issue %s: rejected %d consecutive ticks (%s)",
                               issue.identifier, count, reason)
            else:
                logger.debug("Dispatch reject %s: %s", issue.identifier, reason)
            return False
        if self._paused:
            return _reject("paused")
        if not issue.id or not issue.identifier or not issue.title or not issue.state:
            return _reject("missing_fields")
        # Never dispatch epics via normal dispatch — they are planned
        # separately by _plan_open_epics / _should_dispatch_epic
        if issue.issue_type == "epic":
            return _reject("epic")
        # Never dispatch issues that are waiting for a human answer
        if "asking_question" in issue.labels:
            return _reject("asking_question")
        # Never dispatch issues reserved for human action (e.g. capability requests)
        if "human-only" in issue.labels:
            return _reject("human-only")
        # Never dispatch issues that have been decomposed into children
        if "decomposed" in issue.labels:
            return _reject("decomposed")
        state_norm = issue.state.strip().lower()
        if state_norm not in [s.strip().lower() for s in self.config.tracker_active_states]:
            return _reject(f"inactive_state={state_norm}")
        if state_norm in [s.strip().lower() for s in self.config.tracker_terminal_states]:
            return _reject(f"terminal_state={state_norm}")
        if issue.id in self.state.running:
            return _reject("running")
        if issue.id in self.state.claimed:
            return _reject("claimed")
        if issue.id in self.state.retry_attempts:
            return _reject("retry_pending")
        if issue.id in self.state.completed:
            return _reject("completed")
        is_p0 = issue.priority is not None and issue.priority == 0
        if not is_p0:
            if self._available_slots() <= 0:
                return _reject("no_slots")
            if not self._per_state_available(issue.state):
                return _reject("per_state_limit")
        # Blocker rule for "open"/"todo" state
        if state_norm in ("open", "todo"):
            terminal_norms = {s.strip().lower() for s in self.config.tracker_terminal_states}
            for blocker in issue.blocked_by:
                blocker_state = (blocker.state or "").strip().lower()
                # If blocker state is unknown, look it up
                if not blocker_state and blocker.id:
                    resolved = self._resolve_blocker_state(blocker, issue)
                    blocker_state = resolved
                if blocker_state not in terminal_norms:
                    # Blocker not yet closed — still blocked
                    return _reject(f"blocker={blocker.id} state={blocker_state}")
                if self._blocker_has_unmerged_pr(blocker):
                    # Blocker is closed but PR hasn't merged — still blocked
                    return _reject(f"blocker={blocker.id} unmerged_review")
        # Serialize MR/PR fixes by project: if a project already has an open
        # review (PR/MR), don't dispatch another agent to that project until the
        # existing review is merged. This prevents multiple simultaneous merges
        # from conflicting with each other (each merge changes the target branch).
        # P0 issues bypass this check to ensure critical fixes are never blocked.
        if not is_p0 and self._project_has_open_review(issue.project_id):
            return _reject("open_review")
        # Budget circuit breaker
        if not self._check_budget():
            if not self.state.budget_exceeded:
                self.state.budget_exceeded = True
                logger.warning("Budget limit exceeded (%.2f/%.2f), halting dispatch",
                             self.state.agent_totals.estimated_cost, self.config.budget_limit)
            return _reject("budget_exceeded")
        return True

    def _pre_resolve_blockers(self, candidates: list[Issue]) -> None:
        """Pre-resolve unknown blocker states into the cache (blocking, runs in thread).

        Batches all unknown blockers into parallel bd show calls.
        """
        # Collect all unique blocker IDs that need resolution
        to_resolve: dict[str, list[tuple[BlockerRef, Issue]]] = {}
        for issue in candidates:
            for blocker in issue.blocked_by:
                blocker_state = (blocker.state or "").strip().lower()
                if not blocker_state and blocker.id:
                    to_resolve.setdefault(blocker.id, []).append((blocker, issue))

        if not to_resolve:
            return

        # Resolve all unknown blockers in parallel
        def _resolve_one(bid: str) -> tuple[str, str]:
            # Pick any issue to find the right tracker
            blocker, issue = to_resolve[bid][0]
            try:
                tracker = self._tracker_for_issue(issue)
                detail = tracker.fetch_issue_detail(bid)
                if detail:
                    return (bid, detail.state)
            except Exception:
                pass
            return (bid, "")

        cache = getattr(self, "_blocker_state_cache", {})
        with ThreadPoolExecutor(max_workers=min(len(to_resolve), 4)) as pool:
            for bid, state in pool.map(_resolve_one, to_resolve.keys()):
                cache[bid] = state
                # Update all blocker refs that reference this ID
                for blocker, _ in to_resolve[bid]:
                    blocker.state = state
        self._blocker_state_cache = cache

    def _fetch_all_reviews(self) -> dict[str, list]:
        """Fetch open reviews for all projects in parallel.

        Returns a dict of project_id -> list[ReviewRequest], cached for the
        entire tick so list_open_reviews is called at most once per project.
        """
        projects = self.project_store.list_all()
        if not projects:
            return {}

        def _fetch_for_project(project) -> tuple[str, list]:
            provider = detect_provider(project.repo_url)
            if not provider:
                return (project.id, [])
            slug = extract_repo_slug(project.repo_url)
            try:
                reviews = provider.list_open_reviews(slug)
                return (project.id, reviews)
            except Exception as exc:
                logger.debug("Failed to fetch open reviews for %s: %s", project.name, exc)
                return (project.id, [])

        result: dict[str, list] = {}
        with ThreadPoolExecutor(max_workers=min(len(projects), 4)) as pool:
            for pid, reviews in pool.map(_fetch_for_project, projects):
                result[pid] = reviews
        return result

    def _fetch_all_merged_branches(self) -> set[str]:
        """Fetch merged PR/MR branch names across all projects."""
        projects = self.project_store.list_all()
        if not projects:
            return set()

        def _fetch_for_project(project) -> set[str]:
            provider = detect_provider(project.repo_url)
            if not provider:
                return set()
            slug = extract_repo_slug(project.repo_url)
            try:
                return provider.list_merged_branches(slug)
            except Exception as exc:
                logger.debug("Failed to fetch merged branches for %s: %s", project.name, exc)
                return set()

        result: set[str] = set()
        with ThreadPoolExecutor(max_workers=min(len(projects), 4)) as pool:
            for branches in pool.map(_fetch_for_project, projects):
                result |= branches
        return result

    def _reset_orphaned_in_progress(self, candidates: list[Issue]) -> None:
        """Reset in_progress issues back to open if no agent is attached.

        An issue is orphaned if it's in_progress but has no running agent
        and no pending retry. This prevents issues from getting stuck.
        """
        running_ids = set(self.state.running.keys())
        retry_ids = set(self.state.retry_attempts.keys())
        claimed_ids = self.state.claimed
        completed_ids = self.state.completed

        for issue in candidates:
            if issue.state.strip().lower() != "in_progress":
                continue
            if issue.id in running_ids or issue.id in retry_ids:
                continue
            if issue.id in claimed_ids or issue.id in completed_ids:
                continue
            # Orphaned — reset to open
            try:
                project_id = issue.project_id
                tracker = self._tracker_for_project(project_id) if project_id else self.tracker
                tracker.update_issue(issue.identifier, status="open")
                self._orphan_reset_counts[issue.id] = self._orphan_reset_counts.get(issue.id, 0) + 1
                logger.info("Reset orphaned in_progress issue %s to open (no agent attached, count=%d)",
                            issue.identifier, self._orphan_reset_counts[issue.id])
            except Exception as exc:
                logger.debug("Failed to reset orphaned issue %s: %s", issue.identifier, exc)

    # ------------------------------------------------------------------
    # Watchdog: periodic health checks for stuck issues
    # ------------------------------------------------------------------

    def _maybe_run_watchdog(self) -> None:
        """Run watchdog if enough time has elapsed since last run."""
        now = time.monotonic()
        if now - self._last_watchdog_run < self._watchdog_interval_s:
            return
        self._last_watchdog_run = now
        self._watchdog_check()

    def _watchdog_check(self) -> None:
        """Run all watchdog sub-checks."""
        t0 = time.monotonic()
        fixed = 0
        fixed += self._watchdog_stale_completed()
        fixed += self._watchdog_orphan_loops()
        fixed += self._watchdog_stuck_open()
        fixed += self._watchdog_yolo_limbo()
        elapsed_ms = (time.monotonic() - t0) * 1000
        if fixed > 0:
            logger.info("Watchdog: fixed %d issues (%.0fms)", fixed, elapsed_ms)

    def _watchdog_stale_completed(self) -> int:
        """Clear issues stuck in the completed set despite being active in tracker."""
        active_norms = {s.strip().lower() for s in self.config.tracker_active_states}
        stale = []
        for issue in self._last_candidates:
            if issue.id in self.state.completed:
                state_norm = issue.state.strip().lower()
                if state_norm in active_norms:
                    stale.append(issue)
        for issue in stale:
            self.state.completed.discard(issue.id)
            logger.warning("Watchdog: cleared stale completed entry for %s "
                           "(tracker state=%s)", issue.identifier, issue.state)
        return len(stale)

    def _watchdog_orphan_loops(self) -> int:
        """Alert on issues that keep bouncing back to in_progress without an agent."""
        for issue_id, count in list(self._orphan_reset_counts.items()):
            if count >= 3:
                identifier = issue_id
                for c in self._last_candidates:
                    if c.id == issue_id:
                        identifier = c.identifier
                        break
                logger.warning("Watchdog: issue %s reset from in_progress %d times "
                               "— possible state loop", identifier, count)
                self._orphan_reset_counts[issue_id] = 0
        return 0

    def _watchdog_stuck_open(self) -> int:
        """Fix issues stuck on stale unmerged_review blockers."""
        fixed = 0
        open_branches = getattr(self, "_unmerged_review_branches", set())
        for issue_id, (reason, count) in list(self.state.reject_streak.items()):
            if count < 10:
                continue
            identifier = issue_id
            for c in self._last_candidates:
                if c.id == issue_id:
                    identifier = c.identifier
                    break
            if "unmerged_review" in reason:
                # Extract blocker id and check if its branch still exists
                parts = reason.split()
                blocker_part = [p for p in parts if p.startswith("blocker=")]
                if blocker_part:
                    blocker_id = blocker_part[0].split("=", 1)[1]
                    # Check if blocker_id matches any open branch
                    has_branch = any(blocker_id in b for b in open_branches)
                    if not has_branch:
                        logger.warning("Watchdog: clearing stale unmerged_review block "
                                       "on %s (blocker %s has no open review after %d ticks)",
                                       identifier, blocker_id, count)
                        cache = getattr(self, "_blocker_state_cache", {})
                        cache.pop(blocker_id, None)
                        del self.state.reject_streak[issue_id]
                        fixed += 1
                        continue
        return fixed

    def _watchdog_yolo_limbo(self) -> int:
        """Detect YOLO MRs in limbo (no action condition matched)."""
        reviews_cache = getattr(self, "_reviews_cache", {})
        current_limbo: set[str] = set()
        fixed = 0
        for project in self.project_store.list_all():
            if not project.yolo:
                continue
            provider = detect_provider(project.repo_url)
            if not provider:
                continue
            slug = extract_repo_slug(project.repo_url)
            for review in reviews_cache.get(project.id, []):
                if review.draft:
                    continue
                key = f"{project.id}:{review.id}"
                would_act = (
                    review.has_conflicts
                    or review.ci_status == "failed"
                    or (review.ci_status == "passed" and not review.needs_rebase)
                )
                if would_act:
                    continue
                current_limbo.add(key)
                self._yolo_limbo_ticks[key] = self._yolo_limbo_ticks.get(key, 0) + 1
                tick_count = self._yolo_limbo_ticks[key]
                if tick_count >= 3:
                    if review.ci_status == "passed" and review.needs_rebase:
                        logger.warning("Watchdog: YOLO limbo MR #%s on %s needs rebase "
                                       "(CI passed, %d cycles). Dispatching conflict agent.",
                                       review.id, project.name, tick_count)
                        try:
                            self._yolo_notify_conflict(project, provider, slug, review.id)
                            fixed += 1
                        except Exception as exc:
                            logger.warning("Watchdog: conflict notify failed for %s #%s: %s",
                                           project.name, review.id, exc)
                    else:
                        logger.warning("Watchdog: YOLO limbo MR #%s on %s — "
                                       "ci=%r rebase=%s (%d cycles)",
                                       review.id, project.name, review.ci_status,
                                       review.needs_rebase, tick_count)
        # Clear resolved limbo entries
        for key in list(self._yolo_limbo_ticks):
            if key not in current_limbo:
                del self._yolo_limbo_ticks[key]
        return fixed

    def _ensure_review_exists(self, entry: RunningEntry, project_id: str | None) -> None:
        """Create a review (PR/MR) if the agent pushed a branch but none exists."""
        if not project_id:
            return
        project = self.project_store.get(project_id)
        if not project or not project.repo_url:
            return
        provider = detect_provider(project.repo_url)
        if not provider:
            return
        slug = extract_repo_slug(project.repo_url)
        branch = entry.identifier  # branch is named after the issue
        # Check if a review already exists for this branch
        reviews = getattr(self, "_reviews_cache", {}).get(project_id, [])
        for r in reviews:
            if r.source_branch == branch:
                return  # review already exists
        # Create the review
        try:
            title = f"{entry.identifier}: {entry.issue.title}" if entry.issue else entry.identifier
            result = provider.create_review(slug, title, branch)
            if result:
                logger.info("Auto-created review for %s on %s (review #%s)",
                            entry.identifier, project.name, result.id)
            else:
                logger.warning("Failed to create review for %s on %s",
                               entry.identifier, project.name)
        except Exception as exc:
            logger.warning("Error creating review for %s: %s", entry.identifier, exc)

    def _label_merged_issues(self) -> None:
        """Label closed issues whose branch has been merged."""
        merged = getattr(self, "_merged_branches", set())
        if not merged:
            return

        for project in self.project_store.list_all():
            tracker = self._tracker_for_project(project.id)
            try:
                closed_issues = tracker.fetch_issues_by_states(
                    self.config.tracker_terminal_states
                )
            except TrackerError:
                continue
            for issue in closed_issues:
                if "merged" in issue.labels or "archive:yes" in issue.labels:
                    continue
                # Branch name is typically the issue identifier
                branch = issue.branch_name or issue.identifier
                if branch in merged:
                    try:
                        tracker.add_label(issue.identifier, "merged")
                        logger.info("Labelled %s as merged (branch %s)", issue.identifier, branch)
                    except TrackerError as exc:
                        logger.debug("Failed to label %s as merged: %s", issue.identifier, exc)

    def _yolo_review_actions_sync(self) -> None:
        """Auto-manage reviews for projects with YOLO enabled.

        Uses the per-tick _reviews_cache populated by _fetch_all_reviews
        to avoid redundant API calls.

        For each open PR/MR on a YOLO project:
        - CI passed + mergeable → merge it
        - Has merge conflicts → trigger conflict resolution
        - CI failed → re-file ticket to fix tests

        **Serialization**: only one action is taken per project per tick.
        This prevents multiple simultaneous merges from conflicting with each
        other — each merge changes the target branch, so subsequent PRs must
        be rebased before they can merge cleanly.
        """
        reviews_cache = getattr(self, "_reviews_cache", {})
        for project in self.project_store.list_all():
            if not project.yolo:
                continue
            provider = detect_provider(project.repo_url)
            if not provider:
                continue
            slug = extract_repo_slug(project.repo_url)
            reviews = reviews_cache.get(project.id, [])

            for review in reviews:
                if review.draft:
                    continue
                review_id = review.id

                if review.has_conflicts:
                    # Always dispatch a merge-conflict agent — never rely on
                    # server-side rebase, which reports false success on GitLab.
                    logger.info("YOLO: conflicts on %s review #%s — dispatching conflict agent",
                                project.name, review_id)
                    self._yolo_notify_conflict(project, provider, slug, review_id)
                    continue

                if review.ci_status == "failed":
                    # Auto-retry: re-file the ticket to fix tests.
                    # Act on this one and stop for this project.
                    logger.info("YOLO: auto-retrying failed CI on %s MR #%s",
                                project.name, review_id)
                    self._yolo_retry_ci(project, review)
                    # Serialization: only one action per project per tick.
                    break

                if review.ci_status == "passed" and not review.needs_rebase:
                    # Auto-merge — act on this one and stop for this project.
                    # Merging one PR changes the target branch; subsequent PRs
                    # must rebase before they can be merged cleanly.
                    logger.info("YOLO: auto-merging %s MR #%s",
                                project.name, review_id)
                    success, msg = provider.merge_review(slug, review_id)
                    if success:
                        logger.info("YOLO: merged %s MR #%s", project.name, review_id)
                    else:
                        logger.warning("YOLO: merge failed for %s MR #%s: %s",
                                       project.name, review_id, msg)
                    # Serialization: only one action per project per tick.
                    break

    def _yolo_notify_conflict(self, project, provider, slug: str, review_id: str) -> None:
        """Notify the bead about a merge conflict (YOLO mode)."""
        try:
            review = provider.get_review(slug, review_id)
            if not review:
                return
            source_branch = review.source_branch
            target_branch = review.target_branch
            if not source_branch:
                return
            tracker = self._tracker_for_project(project.id)
            issue = tracker.fetch_issue_detail(source_branch)
            if not issue:
                return
            # Don't re-notify if already open/in_progress with merge-conflict label,
            # but ensure we clear the completed set so it can be re-dispatched.
            state_lower = issue.state.strip().lower()
            if state_lower in ("open", "in_progress") and "merge-conflict" in issue.labels:
                self.state.completed.discard(issue.id)
                return
            comment_text = (
                f"YOLO: Merge conflict detected on MR #{review_id}. "
                f"Rebase onto {target_branch} and resolve conflicts."
            )
            tracker.add_comment(issue.identifier, comment_text, author="oompah")
            try:
                tracker.update_issue(issue.identifier, **{"add-label": "merge-conflict"})
            except Exception:
                pass
            terminal = {s.lower() for s in self.config.tracker_terminal_states}
            if state_lower in terminal:
                tracker.reopen_issue(issue.identifier)
                tracker.update_issue(issue.identifier, priority="0")
                self.state.completed.discard(issue.id)
                logger.info("YOLO: reopened %s as P0 for conflict resolution", issue.identifier)
        except Exception as exc:
            logger.warning("YOLO: conflict notification failed for MR #%s: %s", review_id, exc)

    def _yolo_retry_ci(self, project, review) -> None:
        """Re-file a ticket to fix failed CI tests (YOLO mode)."""
        try:
            source_branch = review.source_branch
            if not source_branch:
                return
            tracker = self._tracker_for_project(project.id)
            issue = tracker.fetch_issue_detail(source_branch)
            if not issue:
                return
            # Don't re-file if already open/in_progress with ci-fix label
            state_lower = issue.state.strip().lower()
            if state_lower in ("open", "in_progress") and "ci-fix" in issue.labels:
                return
            tracker.update_issue(issue.identifier, status="open", priority="0")
            tracker.add_label(issue.identifier, "ci-fix")
            tracker.add_comment(
                issue.identifier,
                f"YOLO: CI tests failed on MR #{review.id}. "
                "Fix the failing tests so this MR can merge. "
                "Do NOT rewrite the feature — only fix test failures. "
                "IMPORTANT: Paths in CI logs are not trustworthy. "
                "Run tests locally to get accurate paths and errors.",
                author="oompah",
            )
            self.state.completed.discard(issue.id)
            logger.info("YOLO: re-filed %s as P0 ci-fix", issue.identifier)
        except Exception as exc:
            logger.warning("YOLO: CI retry failed for branch %s: %s", review.source_branch, exc)

    def _resolve_blocker_state(self, blocker: BlockerRef, issue: Issue) -> str:
        """Look up a blocker's current state, using a per-tick cache."""
        cache = getattr(self, "_blocker_state_cache", {})
        bid = blocker.id or ""
        if bid in cache:
            blocker.state = cache[bid]
            return cache[bid].strip().lower()
        try:
            tracker = self._tracker_for_issue(issue)
            detail = tracker.fetch_issue_detail(bid)
            if detail:
                state = detail.state
                cache[bid] = state
                self._blocker_state_cache = cache
                blocker.state = state
                return state.strip().lower()
        except Exception:
            pass
        cache[bid] = ""
        self._blocker_state_cache = cache
        return ""

    def _blocker_has_unmerged_pr(self, blocker: BlockerRef) -> bool:
        """Check if a closed blocker still has an unmerged PR/MR.

        A blocker is considered unmerged ONLY if it has an open PR/MR.
        If the branch has been merged OR has no open PR, it's not blocking.
        """
        blocker_id = blocker.identifier or blocker.id or ""
        if not blocker_id:
            return False

        # If the branch still has an open PR, it's definitely unmerged
        open_branches = getattr(self, "_unmerged_review_branches", set())
        if blocker_id in open_branches:
            return True

        # No open PR — either merged or never had one. Don't block.
        return False

        # No merged data available — fall back to permissive (allow dispatch)
        return False

    def _sort_for_dispatch(self, issues: list[Issue]) -> list[Issue]:
        def sort_key(issue: Issue):
            pri = issue.priority if issue.priority is not None else 999
            created = issue.created_at or datetime.max.replace(tzinfo=timezone.utc)
            return (pri, created, issue.identifier)
        return sorted(issues, key=sort_key)

    def _match_agent_profile(self, issue: Issue) -> AgentProfile | None:
        """Select the best agent profile for an issue based on matching rules.

        Matching priority:
        1. Issue type match (e.g., bug -> specific profile)
        2. Keyword match in title/description
        3. Priority range match
        4. First profile with no constraints (default fallback)
        """
        profiles = self.config.agent_profiles
        if not profiles:
            return None

        title_lower = (issue.title or "").lower()
        desc_lower = (issue.description or "").lower()
        text = f"{title_lower} {desc_lower}"

        best = None
        best_score = -1

        for profile in profiles:
            score = 0

            # Issue type match
            if profile.issue_types:
                if issue.issue_type in profile.issue_types:
                    score += 10
                else:
                    continue  # type specified but doesn't match — skip

            # Keyword match
            if profile.keywords:
                matched = sum(1 for kw in profile.keywords if kw.lower() in text)
                if matched > 0:
                    score += matched * 5
                else:
                    if not profile.issue_types:
                        continue  # keywords specified but none matched and no type match

            # Priority range
            if profile.min_priority is not None or profile.max_priority is not None:
                pri = issue.priority if issue.priority is not None else 2
                if profile.min_priority is not None and pri < profile.min_priority:
                    continue
                if profile.max_priority is not None and pri > profile.max_priority:
                    continue
                score += 3

            # Default fallback (no constraints)
            if not profile.issue_types and not profile.keywords and profile.min_priority is None and profile.max_priority is None:
                score = 0  # lowest priority, but valid

            if score > best_score:
                best_score = score
                best = profile

        return best

    def _get_profile_by_name(self, name: str) -> AgentProfile | None:
        """Look up an agent profile by name."""
        for p in self.config.agent_profiles:
            if p.name == name:
                return p
        return None

    # Profile hierarchy for escalation (weakest to strongest).
    # Profiles not listed here won't be escalated to.
    _PROFILE_HIERARCHY = ["default", "quick", "standard", "deep"]

    def _escalate_profile(self, current_profile: AgentProfile | None,
                          issue: Issue) -> AgentProfile | None:
        """Return the next higher profile for an issue that keeps stalling.

        Escalation follows _PROFILE_HIERARCHY. Returns None if already at the
        top or if no higher profile exists in the config.
        """
        if not current_profile:
            return None

        hierarchy = self._PROFILE_HIERARCHY
        try:
            idx = hierarchy.index(current_profile.name)
        except ValueError:
            return None  # profile not in hierarchy, no escalation

        # Walk up the hierarchy looking for the next configured profile
        for higher_name in hierarchy[idx + 1:]:
            higher = self._get_profile_by_name(higher_name)
            if higher:
                return higher
        return None

    def _resolve_provider(self, profile: AgentProfile):
        """Resolve the provider for a profile, falling back to the default."""
        if profile.provider_id:
            return self.provider_store.get(profile.provider_id)
        return self.provider_store.get_default()

    def _resolve_model(self, profile: AgentProfile, provider) -> str | None:
        """Resolve the model name from a profile and provider."""
        model = None
        if profile.model_role and provider.model_roles:
            model = provider.model_roles.get(profile.model_role)
        if not model:
            model = profile.model or provider.default_model or (provider.models[0] if provider.models else None)
        return model

    def _estimate_cost(self, profile: AgentProfile, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a session based on provider model costs, falling back to profile rates."""
        cost_in = profile.cost_per_1k_input
        cost_out = profile.cost_per_1k_output
        # Resolve costs from provider if available
        provider = self._resolve_provider(profile)
        if provider:
            if provider.model_costs:
                model = self._resolve_model(profile, provider)
                if model:
                    pc_in, pc_out = provider.get_model_costs(model)
                    if pc_in or pc_out:
                        cost_in, cost_out = pc_in, pc_out
        return (input_tokens / 1000.0) * cost_in + \
               (output_tokens / 1000.0) * cost_out

    def _check_budget(self) -> bool:
        """Return True if within budget, False if budget exceeded."""
        if self.config.budget_limit <= 0:
            return True  # no budget limit set
        return self.state.agent_totals.estimated_cost < self.config.budget_limit

    def _post_comment(self, identifier: str, text: str, author: str = "oompah",
                      project_id: str | None = None) -> None:
        """Post a comment on an issue (best-effort, non-blocking)."""
        try:
            tracker = self._tracker_for_project(project_id) if project_id else self.tracker
            tracker.add_comment(identifier, text, author=author)
        except Exception as exc:
            logger.debug("Failed to post comment on %s: %s", identifier, exc)

    def _clear_handoff_labels(self, issue: Issue) -> None:
        """Remove any needs:* handoff labels after focus has been selected."""
        if not issue.labels:
            return
        handoff_labels = [l for l in issue.labels if l.startswith("needs:")]
        if not handoff_labels:
            return
        try:
            tracker = self._tracker_for_issue(issue)
            for label in handoff_labels:
                tracker.remove_label(issue.identifier, label)
                logger.info("Cleared handoff label %s from %s", label, issue.identifier)
        except Exception as exc:
            logger.debug("Failed to clear handoff labels on %s: %s", issue.identifier, exc)

    async def _dispatch(self, issue: Issue, attempt: int | None,
                        override_profile: str | None = None) -> None:
        """Dispatch a worker for an issue."""
        self.state.reject_streak.pop(issue.id, None)
        # Use escalated profile if provided, otherwise match normally
        if override_profile:
            profile = self._get_profile_by_name(override_profile)
            if not profile:
                profile = self._match_agent_profile(issue)
        else:
            profile = self._match_agent_profile(issue)
        profile_name = profile.name if profile else "default"

        logger.info(
            "Dispatching issue_id=%s issue_identifier=%s attempt=%s agent_profile=%s",
            issue.id,
            issue.identifier,
            attempt,
            profile_name,
        )
        self.state.claimed.add(issue.id)

        # Move issue to in_progress (in thread to avoid blocking event loop)
        try:
            tracker = self._tracker_for_issue(issue)
            await asyncio.get_event_loop().run_in_executor(
                self._tick_pool,
                lambda: tracker.update_issue(issue.identifier, status="in_progress"),
            )
        except Exception as exc:
            logger.warning("Failed to set in_progress for %s: %s — aborting dispatch", issue.identifier, exc)
            self.state.claimed.discard(issue.id)
            return

        # Remove from retry if present
        retry = self.state.retry_attempts.pop(issue.id, None)
        if retry and retry.timer_handle and not retry.timer_handle.done():
            retry.timer_handle.cancel()

        now = datetime.now(timezone.utc)
        worker_task = asyncio.create_task(
            self._run_worker(issue, attempt, profile),
            name=f"worker-{issue.identifier}",
        )

        self.state.running[issue.id] = RunningEntry(
            worker_task=worker_task,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=attempt or 0,
            started_at=now,
            agent_profile_name=profile_name,
        )

        # Post dispatch comment in thread to avoid blocking event loop
        comment = (f"Retrying (attempt #{attempt}, agent: {profile_name})"
                   if attempt and attempt > 1
                   else f"Agent dispatched (profile: {profile_name})")
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            self._tick_pool,
            lambda: self._post_comment(issue.identifier, comment,
                                       project_id=issue.project_id),
        )  # fire-and-forget, don't await

        # Emit agent dispatched event on EventBus
        self.event_bus.emit(EventType.AGENT_DISPATCHED, {
            "issue_id": issue.id,
            "identifier": issue.identifier,
            "profile": profile_name,
            "attempt": attempt,
        })
        self._notify_observers()

    async def _run_worker(self, issue: Issue, attempt: int | None, profile: AgentProfile | None = None) -> None:
        """Worker: create workspace, build prompt, run agent turns."""
        # Route to API agent if a provider can be resolved
        if profile:
            provider = self._resolve_provider(profile)
            if provider:
                await self._run_api_worker(issue, attempt, profile, provider)
                return

        await self._run_cli_worker(issue, attempt, profile)

    async def _run_api_worker(self, issue: Issue, attempt: int | None, profile: AgentProfile, provider) -> None:
        """Worker using the OpenAI-compatible API agent."""
        exit_reason = "normal"
        error_msg = None
        max_turns = profile.max_turns if profile.max_turns else self.config.max_turns
        # Resolve model: role lookup → explicit model → provider default
        model = self._resolve_model(profile, provider)
        if not model:
            raise ValueError(f"No model resolved for profile {profile.name!r} with provider {provider.name}")
        if profile.model_role and provider.model_roles and profile.model_role not in provider.model_roles:
            logger.error("Model role %r not defined in provider %s (available roles: %s)",
                         profile.model_role, provider.name, ", ".join(provider.model_roles))
            raise ValueError(f"Model role {profile.model_role!r} not defined in provider {provider.name}")
        if provider.models and model not in provider.models:
            logger.error("Model %s not available in provider %s (available: %s)",
                         model, provider.name, ", ".join(provider.models))
            raise ValueError(f"Model {model} not available in provider {provider.name}")

        try:
            # Run blocking setup work in thread to avoid blocking event loop
            def _setup_worker():
                # Create workspace
                if issue.project_id:
                    wp = self.project_store.create_worktree(
                        issue.project_id, issue.identifier)
                else:
                    workspace = self.workspace_mgr.create_for_issue(issue.identifier)
                    wp = workspace.path
                    self.workspace_mgr.run_before_run(wp)

                # Select focus
                focus = select_focus(issue)
                logger.info("Issue %s assigned focus: %s (%s)",
                            issue.identifier, focus.name, focus.role)
                self._post_comment(issue.identifier, f"Focus: {focus.role}",
                                   project_id=issue.project_id)
                self._clear_handoff_labels(issue)

                # Fetch comments and memories
                try:
                    tracker = self._tracker_for_issue(issue)
                    comments = tracker.fetch_comments(issue.identifier)
                except Exception:
                    comments = []
                try:
                    memories = tracker.fetch_memories()
                except Exception:
                    memories = {}

                # Build prompt
                prompt = render_prompt(
                    self._prompt_template, issue, attempt,
                    comments=comments, focus_text=focus.render(),
                    workspace_path=wp, memories=memories,
                )
                return wp, focus, prompt

            loop = asyncio.get_event_loop()
            workspace_path, focus, prompt = await loop.run_in_executor(
                self._tick_pool, _setup_worker
            )

            # Store focus on running entry for dashboard display
            running_entry = self.state.running.get(issue.id)
            if running_entry:
                running_entry.focus_name = focus.name
                running_entry.focus_role = focus.role

            session = ApiAgentSession(
                base_url=provider.base_url,
                api_key=provider.api_key,
                model=model,
                workspace_path=workspace_path,
                max_turns=max_turns,
                stall_turns=self.config.stall_turns,
                system_prompt="You are an autonomous coding agent. Use the provided tools to complete the task.",
            )

            # Update running entry with minimal session info
            if issue.id in self.state.running:
                self.state.running[issue.id].session = LiveSession(
                    session_id=f"api-{provider.name}-{model}",
                    thread_id="api",
                    turn_id="0",
                    agent_pid=None,
                    last_event="api_started",
                    last_timestamp=datetime.now(timezone.utc),
                    last_message=f"Using {provider.name}/{model}",
                )

            def _on_activity(activity_entry: AgentActivity) -> None:
                if issue.id in self.state.running:
                    self.state.running[issue.id].activity_log.append(activity_entry)
                    if self.state.running[issue.id].session:
                        self.state.running[issue.id].session.last_message = activity_entry.summary[:200]
                        self.state.running[issue.id].session.last_event = activity_entry.kind
                        self.state.running[issue.id].session.last_timestamp = datetime.now(timezone.utc)
                    # Broadcast activity entry to WS clients
                    self._notify_activity(issue.identifier, activity_entry)
                    # Only broadcast state (lightweight), not issues (expensive)
                    # Issues are only re-fetched on state changes (dispatch, close, etc.)
                    self._notify_state_only()

            def _is_cancelled() -> bool:
                """Check if this issue has been closed or removed from running."""
                if issue.id not in self.state.running:
                    return True
                try:
                    tracker = self._tracker_for_issue(issue)
                    refreshed = tracker.fetch_issue_states_by_ids([issue.id])
                    if refreshed:
                        state = refreshed[0].state.strip().lower()
                        terminal = {s.strip().lower() for s in self.config.tracker_terminal_states}
                        if state in terminal:
                            return True
                except Exception:
                    pass
                return False

            result = await session.run_task(prompt, on_activity=_on_activity,
                                            is_cancelled=_is_cancelled)

            # Update session with final token counts
            if issue.id in self.state.running and self.state.running[issue.id].session:
                s = self.state.running[issue.id].session
                s.input_tokens = result.input_tokens
                s.output_tokens = result.output_tokens
                s.total_tokens = result.total_tokens
                s.turn_count = result.turns
                s.last_message = result.last_message[:200]
                s.last_event = f"api_{result.status}"

            if result.status == "ask_question":
                exit_reason = "ask_question"
                error_msg = result.question
                logger.info("API agent asked a question on %s: %s",
                            issue.identifier, result.question)
            elif result.status == "rate_limited":
                exit_reason = "rate_limited"
                error_msg = result.error or "Rate limited by API"
                logger.warning("API agent rate limited on %s: %s", issue.identifier, error_msg)
            elif result.status == "failed":
                exit_reason = "abnormal"
                error_msg = result.error or "API agent failed"
            elif result.status == "max_turns":
                exit_reason = "max_turns"
                logger.info("API agent reached max turns for %s", issue.identifier)
            elif result.status == "stalled":
                exit_reason = "stalled"
                error_msg = result.error
                logger.info("API agent stalled on %s: %s", issue.identifier, error_msg)

        except Exception as exc:
            exit_reason = "abnormal"
            error_msg = str(exc)
            logger.exception("API worker failed issue_id=%s", issue.id)
        finally:
            if not issue.project_id:
                try:
                    wp = self.workspace_mgr.workspace_path_for(issue.identifier)
                    self.workspace_mgr.run_after_run(wp)
                except Exception:
                    pass
            await self._on_worker_exit(issue.id, exit_reason, error_msg)

    async def _run_cli_worker(self, issue: Issue, attempt: int | None, profile: AgentProfile | None = None) -> None:
        """Worker using CLI subprocess (original behavior)."""
        exit_reason = "normal"
        error_msg = None
        agent_command = profile.command if profile else self.config.agent_command
        max_turns = profile.max_turns if profile and profile.max_turns else self.config.max_turns

        try:
            # Create workspace: use project worktree if available, else legacy
            if issue.project_id:
                workspace_path = self.project_store.create_worktree(
                    issue.project_id, issue.identifier)
            else:
                workspace = self.workspace_mgr.create_for_issue(issue.identifier)
                workspace_path = workspace.path
                self.workspace_mgr.run_before_run(workspace_path)

            # Start agent session
            session = AgentSession(
                command=agent_command,
                workspace_path=workspace_path,
                read_timeout_ms=self.config.read_timeout_ms,
                turn_timeout_ms=self.config.turn_timeout_ms,
            )
            await session.start()

            try:
                await session.initialize()
                await session.start_thread()

                # Update running entry with session info
                if issue.id in self.state.running:
                    self.state.running[issue.id].session = LiveSession(
                        session_id=session.session_id or "",
                        thread_id=session.thread_id or "",
                        turn_id=session.turn_id or "",
                        agent_pid=session.pid,
                        last_event=None,
                        last_timestamp=None,
                        last_message="",
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        last_reported_input_tokens=0,
                        last_reported_output_tokens=0,
                        last_reported_total_tokens=0,
                        turn_count=0,
                    )

                current_issue = issue

                # Select focus tailored to this issue
                cli_focus = select_focus(issue)
                logger.info("Issue %s assigned focus: %s (%s)", issue.identifier, cli_focus.name, cli_focus.role)
                self._post_comment(issue.identifier, f"Focus: {cli_focus.role}",
                                   project_id=issue.project_id)
                # Clean up handoff labels after focus selection
                self._clear_handoff_labels(issue)
                # Store focus on running entry for dashboard display
                cli_running = self.state.running.get(issue.id)
                if cli_running:
                    cli_running.focus_name = cli_focus.name
                    cli_running.focus_role = cli_focus.role

                # Fetch existing comments and memories to kick-start agent context
                try:
                    tracker = self._tracker_for_issue(issue)
                    cli_comments = tracker.fetch_comments(issue.identifier)
                except Exception:
                    cli_comments = []
                try:
                    cli_memories = tracker.fetch_memories()
                except Exception:
                    cli_memories = {}

                for turn_number in range(1, max_turns + 1):
                    # Build prompt
                    if turn_number == 1:
                        prompt = render_prompt(
                            self._prompt_template, current_issue, attempt,
                            comments=cli_comments, focus_text=cli_focus.render(),
                            workspace_path=workspace_path, memories=cli_memories,
                        )
                    else:
                        prompt = build_continuation_prompt(
                            current_issue, turn_number, max_turns
                        )

                    # Start and stream turn
                    await session.start_turn(
                        prompt=prompt,
                        issue_identifier=current_issue.identifier,
                        issue_title=current_issue.title,
                    )

                    if issue.id in self.state.running and self.state.running[issue.id].session:
                        self.state.running[issue.id].session.turn_count = turn_number
                        self.state.running[issue.id].session.turn_id = session.turn_id or ""
                        self.state.running[issue.id].session.session_id = session.session_id or ""

                    def _on_event(event: AgentEvent) -> None:
                        self._handle_agent_event(issue.id, event)

                    status = await session.stream_turn(on_event=_on_event)

                    if status != "succeeded":
                        exit_reason = "abnormal"
                        error_msg = f"Turn ended with status: {status}"
                        break

                    # Re-check issue state for continuation
                    try:
                        tracker = self._tracker_for_issue(issue)
                        refreshed = tracker.fetch_issue_states_by_ids([issue.id])
                        if refreshed:
                            current_issue = refreshed[0]
                            current_issue.project_id = issue.project_id
                    except TrackerError:
                        break

                    active_norms = {s.strip().lower() for s in self.config.tracker_active_states}
                    if current_issue.state.strip().lower() not in active_norms:
                        break
                else:
                    # Loop completed without break — all turns used up
                    active_norms = {s.strip().lower() for s in self.config.tracker_active_states}
                    if current_issue.state.strip().lower() in active_norms:
                        exit_reason = "max_turns"
                        logger.info("CLI agent reached max turns for %s", issue.identifier)

            finally:
                await session.stop()

        except (WorkspaceError, AgentError, PromptError) as exc:
            exit_reason = "abnormal"
            error_msg = str(exc)
            logger.error(
                "Worker failed issue_id=%s issue_identifier=%s error=%s",
                issue.id,
                issue.identifier,
                exc,
            )
        except Exception as exc:
            exit_reason = "abnormal"
            error_msg = str(exc)
            logger.exception(
                "Worker unexpected error issue_id=%s issue_identifier=%s",
                issue.id,
                issue.identifier,
            )
        finally:
            if not issue.project_id:
                try:
                    wp = self.workspace_mgr.workspace_path_for(issue.identifier)
                    self.workspace_mgr.run_after_run(wp)
                except Exception:
                    pass

            # Report exit to orchestrator
            await self._on_worker_exit(issue.id, exit_reason, error_msg)

    def _handle_agent_event(self, issue_id: str, event: AgentEvent) -> None:
        """Update running entry with agent event data."""
        entry = self.state.running.get(issue_id)
        if not entry or not entry.session:
            return

        entry.session.last_event = event.event
        entry.session.last_timestamp = datetime.fromtimestamp(
            event.timestamp, tz=timezone.utc
        )
        entry.session.last_message = event.payload.get("message", "")
        entry.session.agent_pid = event.agent_pid

        # Update token counts from absolute totals
        if event.usage:
            new_input = event.usage.get("input_tokens", 0)
            new_output = event.usage.get("output_tokens", 0)
            new_total = event.usage.get("total_tokens", 0)

            # Track deltas for aggregate totals
            if new_total > 0:
                delta_input = max(0, new_input - entry.session.last_reported_input_tokens)
                delta_output = max(0, new_output - entry.session.last_reported_output_tokens)
                delta_total = max(0, new_total - entry.session.last_reported_total_tokens)

                entry.session.input_tokens += delta_input
                entry.session.output_tokens += delta_output
                entry.session.total_tokens += delta_total

                entry.session.last_reported_input_tokens = new_input
                entry.session.last_reported_output_tokens = new_output
                entry.session.last_reported_total_tokens = new_total

        # Update rate limits if present
        rate_limits = event.payload.get("rate_limits")
        if rate_limits:
            self.state.rate_limits = rate_limits

    async def _on_worker_exit(
        self, issue_id: str, reason: str, error: str | None
    ) -> None:
        """Handle worker completion."""
        entry = self.state.running.pop(issue_id, None)
        if not entry:
            return

        # Add runtime seconds to totals
        elapsed = (datetime.now(timezone.utc) - entry.started_at).total_seconds()
        self.state.agent_totals.seconds_running += elapsed

        # Add token totals and estimate cost
        if entry.session:
            self.state.agent_totals.input_tokens += entry.session.input_tokens
            self.state.agent_totals.output_tokens += entry.session.output_tokens
            self.state.agent_totals.total_tokens += entry.session.total_tokens

            # Estimate cost from agent profile
            profile = self._get_profile_by_name(entry.agent_profile_name)
            if profile:
                cost = self._estimate_cost(profile, entry.session.input_tokens, entry.session.output_tokens)
                self.state.agent_totals.estimated_cost += cost
                self.state.cost_by_profile[entry.agent_profile_name] = \
                    self.state.cost_by_profile.get(entry.agent_profile_name, 0.0) + cost

                # Reset circuit breaker if we're back under budget
                if self.state.budget_exceeded and self._check_budget():
                    self.state.budget_exceeded = False

        tokens_str = ""
        if entry.session and entry.session.total_tokens > 0:
            tokens_str = f" ({entry.session.total_tokens} tokens)"

        project_id = entry.issue.project_id if entry.issue else None

        if reason == "ask_question":
            # Agent asked a question — post it, label the issue, move to open
            self.state.claimed.discard(issue_id)
            self.state.stall_counts.pop(issue_id, None)
            question_text = error or "Agent has a question (no text provided)"
            self._post_comment(
                entry.identifier,
                f"🤚 **Question from agent:**\n\n{question_text}",
                project_id=project_id,
            )
            try:
                tracker = self._tracker_for_project(project_id) if project_id else self.tracker
                tracker.add_label(entry.identifier, "asking_question")
                tracker.update_issue(entry.identifier, status="open")
            except Exception as exc:
                logger.warning("Failed to set asking_question state for %s: %s",
                               entry.identifier, exc)
            logger.info(
                "Worker asked question issue_id=%s issue_identifier=%s",
                issue_id,
                entry.identifier,
            )
            self._notify_observers()
            return

        if reason == "normal":
            _exit_event = EventType.AGENT_COMPLETED
        elif reason in ("max_turns", "stalled"):
            _exit_event = EventType.AGENT_STALLED if reason == "stalled" else EventType.AGENT_MAX_TURNS
        else:
            _exit_event = EventType.AGENT_FAILED

        if reason == "normal":
            self.state.claimed.discard(issue_id)
            self.state.stall_counts.pop(issue_id, None)
            self._post_comment(
                entry.identifier,
                f"Agent completed successfully in {elapsed:.0f}s{tokens_str}",
                project_id=project_id,
            )
            logger.info(
                "Worker completed normally issue_id=%s issue_identifier=%s",
                issue_id,
                entry.identifier,
            )
            # Check if the agent actually closed the issue
            try:
                tracker = self._tracker_for_project(project_id) if project_id else self.tracker
                current = tracker.fetch_issue_detail(entry.identifier)
                terminal = {s.strip().lower() for s in self.config.tracker_terminal_states}
                if current and current.state.strip().lower() not in terminal:
                    # Merge-conflict agents just rebase — closure happens when
                    # YOLO merges the MR.  Don't count these toward the reopen
                    # limit; just mark completed and let YOLO handle the rest.
                    current_labels = {l.lower() for l in (current.labels or [])}
                    if "merge-conflict" in current_labels:
                        logger.info("Merge-conflict agent completed for %s — "
                                    "closing, awaiting YOLO merge",
                                    entry.identifier)
                        # Close the issue — the agent resolved the conflict.
                        # YOLO will reopen it if new conflicts arise.
                        try:
                            tracker.update_issue(entry.identifier,
                                                 **{"remove-label": "merge-conflict"})
                        except Exception:
                            pass
                        tracker.close_issue(entry.identifier)
                        self.state.completed.add(issue_id)
                        self.state.reopen_counts.pop(issue_id, None)
                    else:
                        # Track how many times this issue completed without closing
                        reopen_count = self.state.reopen_counts.get(issue_id, 0) + 1
                        self.state.reopen_counts[issue_id] = reopen_count
                        max_reopens = 3
                        if reopen_count >= max_reopens:
                            # Stop re-dispatching — agent can't close this issue
                            logger.warning(
                                "Agent completed without closing %s %d times — giving up (marking deferred)",
                                entry.identifier, reopen_count)
                            self._post_comment(
                                entry.identifier,
                                f"Agent completed {reopen_count} times without closing this issue. "
                                f"Deferring — needs human attention.",
                                project_id=project_id,
                            )
                            tracker.update_issue(entry.identifier, status="deferred")
                            self.state.completed.add(issue_id)
                        else:
                            # Reset to open for retry with backoff
                            tracker.update_issue(entry.identifier, status="open")
                            logger.info("Agent completed without closing %s — reset to open (%d/%d)",
                                        entry.identifier, reopen_count, max_reopens)
                else:
                    self.state.completed.add(issue_id)
                    self.state.reopen_counts.pop(issue_id, None)
                    # Auto-create review if agent pushed a branch
                    self._ensure_review_exists(entry, project_id)
            except Exception:
                self.state.completed.add(issue_id)
            # Analyze completed work against foci library
            self._analyze_focus_fit(entry.issue, project_id)
        elif reason == "rate_limited":
            # Global cooldown — stop dispatching new agents for a while
            cooldown_s = 120  # 2 minutes
            self._rate_limit_until = time.time() + cooldown_s
            self._alerts = [a for a in self._alerts if a.get("source") != "rate_limit"]
            self._alerts.append({
                "level": "warning",
                "source": "rate_limit",
                "message": f"Rate limited by API — pausing dispatch for {cooldown_s}s",
            })
            next_attempt = (entry.retry_attempt or 0) + 1
            delay = max(cooldown_s * 1000, self._backoff_delay(next_attempt))
            self._post_comment(
                entry.identifier,
                f"Rate limited by API. Pausing all dispatch for {cooldown_s}s. "
                f"Retrying in {delay // 1000}s (attempt #{next_attempt})",
                project_id=project_id,
            )
            self._schedule_retry(
                issue_id,
                attempt=next_attempt,
                identifier=entry.identifier,
                delay_ms=delay,
                error=error,
            )
            logger.warning(
                "Rate limited — pausing dispatch for %ds. issue_id=%s retrying_in_ms=%d",
                cooldown_s, issue_id, delay,
            )
        elif reason in ("max_turns", "stalled"):
            next_attempt = (entry.retry_attempt or 0) + 1
            delay = self._backoff_delay(next_attempt)

            # Check if we should decompose instead of retrying
            if self._should_decompose(entry.issue, next_attempt):
                asyncio.ensure_future(self._trigger_decomposition(
                    issue_id, entry, next_attempt, project_id,
                ))
                logger.info(
                    "Triggering auto-decomposition for %s after %d attempts",
                    entry.identifier, next_attempt,
                )
            else:
                # Track stall/failure count for escalation
                escalated = None
                if reason == "stalled":
                    self.state.stall_counts[issue_id] = self.state.stall_counts.get(issue_id, 0) + 1
                    stall_count = self.state.stall_counts[issue_id]

                # Escalate on both stalled and max_turns once threshold is met
                if next_attempt >= self.config.escalate_after_attempts:
                    current_profile = self._get_profile_by_name(entry.agent_profile_name)
                    escalated = self._escalate_profile(current_profile, entry.issue)

                if escalated:
                    if reason == "stalled":
                        msg = (f"Agent stalled {self.state.stall_counts.get(issue_id, 1)} time(s) ({elapsed:.0f}s{tokens_str}). "
                               f"Escalating from '{entry.agent_profile_name}' to '{escalated.name}'. "
                               f"Retrying in {delay // 1000}s (attempt #{next_attempt})")
                    else:
                        msg = (f"Agent hit turn limit ({elapsed:.0f}s{tokens_str}). "
                               f"Escalating from '{entry.agent_profile_name}' to '{escalated.name}'. "
                               f"Retrying in {delay // 1000}s (attempt #{next_attempt})")
                    logger.info("Escalating issue %s from profile %s to %s (attempt=%d, reason=%s)",
                                entry.identifier, entry.agent_profile_name, escalated.name, next_attempt, reason)
                elif reason == "stalled":
                    msg = (f"Agent stalled — no productive actions (writes/commands) "
                           f"for {self.config.stall_turns} consecutive turns "
                           f"({elapsed:.0f}s{tokens_str}). "
                           f"Retrying in {delay // 1000}s (attempt #{next_attempt})")
                else:
                    msg = (f"Agent hit safety turn limit ({elapsed:.0f}s{tokens_str}). "
                           f"Retrying in {delay // 1000}s (attempt #{next_attempt})")
                self._post_comment(entry.identifier, msg, project_id=project_id)
                self._schedule_retry(
                    issue_id,
                    attempt=next_attempt,
                    identifier=entry.identifier,
                    delay_ms=delay,
                    error=error or reason,
                    escalated_profile=escalated.name if escalated else None,
                )
                logger.info(
                    "Worker %s issue_id=%s issue_identifier=%s retrying_in_ms=%d",
                    reason,
                    issue_id,
                    entry.identifier,
                    delay,
                )
        else:
            # Check if the failure is actually a rate limit (e.g. from CLI agent)
            error_lower = (error or "").lower()
            is_rate_limit = any(s in error_lower for s in ("429", "rate limit", "too many requests", "overloaded"))
            if is_rate_limit:
                cooldown_s = 120
                self._rate_limit_until = time.time() + cooldown_s
                self._alerts = [a for a in self._alerts if a.get("source") != "rate_limit"]
                self._alerts.append({
                    "level": "warning",
                    "source": "rate_limit",
                    "message": f"Rate limited by API — pausing dispatch for {cooldown_s}s",
                })

            next_attempt = (entry.retry_attempt or 0) + 1
            base_delay = self._backoff_delay(next_attempt)
            delay = max(120_000, base_delay) if is_rate_limit else base_delay
            self._post_comment(
                entry.identifier,
                f"Agent failed: {error or 'unknown error'}. Retrying in {delay // 1000}s (attempt #{next_attempt})",
                project_id=project_id,
            )
            self._schedule_retry(
                issue_id,
                attempt=next_attempt,
                identifier=entry.identifier,
                delay_ms=delay,
                error=error,
            )
            logger.warning(
                "Worker failed issue_id=%s issue_identifier=%s error=%s retrying_in_ms=%d",
                issue_id,
                entry.identifier,
                error,
                delay,
            )

        # Emit the agent lifecycle event on the EventBus
        self.event_bus.emit(_exit_event, {
            "issue_id": issue_id,
            "identifier": entry.identifier,
            "reason": reason,
            "error": error,
            "elapsed_s": elapsed,
        })
        self._notify_observers()
        # Wake the dispatch loop so it can pick up the next candidate immediately.
        self._post_event(DispatchEvent(
            event_type=DispatchEventType.WORKER_EXIT,
            issue_id=issue_id,
            payload={"reason": reason},
        ))

    def _is_rate_limited(self) -> bool:
        """Check if we're in a rate-limit cooldown period."""
        if self._rate_limit_until <= 0:
            return False
        if time.time() >= self._rate_limit_until:
            # Cooldown expired — clear alert
            self._rate_limit_until = 0.0
            self._alerts = [a for a in self._alerts if a.get("source") != "rate_limit"]
            return False
        return True

    # ------------------------------------------------------------------
    # Auto-decomposition
    # ------------------------------------------------------------------

    def _should_decompose(self, issue: Issue, next_attempt: int) -> bool:
        """Check whether an issue should be auto-decomposed instead of retried."""
        if next_attempt < self.config.decompose_after_attempts:
            return False
        if "decomposed" in issue.labels or "no-decompose" in issue.labels:
            return False
        if issue.parent_id:
            return False  # don't decompose children — they're already decomposed pieces
        if self.state.decompose_attempts.get(issue.id, 0) > 0:
            return False  # already tried decomposing this one
        return True

    _DECOMPOSE_PROMPT = """\
You are a task decomposition planner. An autonomous coding agent has tried \
to complete the following issue {attempt} time(s) but keeps running out of \
turns or stalling. The issue is too large or complex for a single agent session.

## Original Issue
- Identifier: {identifier}
- Title: {title}
- Type: {issue_type}
- Description: {description}

## Failure History
{comments}

## Available Agent Specialisations
Each child task can be routed to a specialist via a focus hint:
{foci}

## Instructions
1. Analyse the failure comments to understand what went wrong and where the agent got stuck.
2. Break the issue into 2-5 smaller, independently actionable sub-tasks.
3. Each sub-task must be completable in a single agent session (~20 tool calls).
4. Assign a focus_hint to route each sub-task to the right specialist.
5. If sub-tasks must be done in order, express that with depends_on (indices into the tasks array).
6. Preserve the intent of the original issue — the union of all sub-tasks should fully resolve it.

Return ONLY a JSON object (no markdown fences, no commentary):
{{
  "analysis": "Brief explanation of why the original task is too complex",
  "tasks": [
    {{
      "title": "Short descriptive title",
      "description": "Detailed description with enough context to work independently",
      "focus_hint": "one of: bugfix, feature, refactor, frontend, docs, test, security, devops, chore",
      "priority": 2,
      "depends_on": []
    }}
  ]
}}
"""

    def _build_decomposition_prompt(self, issue: Issue, comments: list[dict], attempt: int) -> str:
        """Build the prompt for the decomposition planner."""
        from oompah.focus import BUILTIN_FOCI
        foci_text = "\n".join(f"- {f.name}: {f.role}" for f in BUILTIN_FOCI
                              if f.name not in ("epic_planner", "merge_conflict"))
        comments_text = "\n".join(
            f"- {c.get('author', '?')} ({c.get('created_at', '?')}): {c.get('text', '')}"
            for c in (comments or [])
        ) or "(no comments)"
        return self._DECOMPOSE_PROMPT.format(
            attempt=attempt,
            identifier=issue.identifier,
            title=issue.title,
            issue_type=issue.issue_type,
            description=issue.description or "(no description)",
            comments=comments_text,
            foci=foci_text,
        )

    async def _trigger_decomposition(
        self, issue_id: str, entry: RunningEntry, attempt: int, project_id: str | None
    ) -> None:
        """Attempt to decompose an issue into smaller child tasks."""
        issue = entry.issue
        self.state.decompose_attempts[issue_id] = self.state.decompose_attempts.get(issue_id, 0) + 1

        self._post_comment(
            entry.identifier,
            f"Issue has failed {attempt} time(s). Attempting auto-decomposition into smaller tasks.",
            project_id=project_id,
        )

        try:
            # Fetch comments for context
            tracker = self._tracker_for_issue(issue)
            comments = tracker.fetch_comments(entry.identifier)

            # Build prompt
            prompt = self._build_decomposition_prompt(issue, comments, attempt)

            # Resolve provider and model (use fast role for planning)
            provider = self.provider_store.get_default()
            if not provider:
                raise RuntimeError("No provider configured for decomposition")
            model = (provider.model_roles or {}).get("fast") or provider.default_model
            if not model and provider.models:
                model = provider.models[0]
            if not model:
                raise RuntimeError("No model available for decomposition")

            # Make API call (single turn, no tools)
            from oompah.api_agent import _build_ssl_context, _http_post
            ssl_ctx = _build_ssl_context()
            url = f"{provider.base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {provider.api_key}",
            }
            payload = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a task decomposition planner. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            }).encode()

            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                self._tick_pool, _http_post, url, headers, payload, ssl_ctx
            )

            # Parse response
            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            # Strip markdown fences if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            plan = json.loads(content)
            tasks = plan.get("tasks", [])
            if not tasks or not isinstance(tasks, list):
                raise ValueError("Planner returned no tasks")
            if len(tasks) > 8:
                tasks = tasks[:8]  # cap at 8 children

            # Validate and create children
            await self._execute_decomposition(issue, tasks, tracker, project_id)

            analysis = plan.get("analysis", "")
            self._post_comment(
                entry.identifier,
                f"Decomposed into {len(tasks)} sub-tasks. {analysis}",
                project_id=project_id,
            )
            logger.info("Decomposed %s into %d sub-tasks", entry.identifier, len(tasks))

            # Clean up state for the original issue
            self.state.claimed.discard(issue_id)
            self.state.stall_counts.pop(issue_id, None)

        except Exception as exc:
            logger.warning(
                "Auto-decomposition failed for %s: %s", entry.identifier, exc
            )
            self._post_comment(
                entry.identifier,
                f"Auto-decomposition failed: {exc}. Falling back to normal retry.",
                project_id=project_id,
            )
            # Fall back to normal retry
            delay = self._backoff_delay(attempt)
            self._schedule_retry(
                issue_id,
                attempt=attempt,
                identifier=entry.identifier,
                delay_ms=delay,
                error=str(exc),
            )

    async def _execute_decomposition(
        self, parent_issue: Issue, tasks: list[dict], tracker: BeadsTracker, project_id: str | None
    ) -> None:
        """Create child issues from a decomposition plan."""
        created: list[Issue] = []

        for task in tasks:
            title = task.get("title", "Untitled sub-task")
            description = task.get("description", "")
            priority = task.get("priority", parent_issue.priority or 2)
            if not isinstance(priority, int) or priority < 0 or priority > 4:
                priority = 2

            child = tracker.create_issue(
                title=title,
                issue_type="task",
                description=description,
                priority=priority,
                initial_status="open",
            )
            created.append(child)

            # Link as parent-child
            tracker.add_parent_child(child.identifier, parent_issue.identifier)

            # Add focus hint label
            focus_hint = task.get("focus_hint", "")
            if focus_hint:
                try:
                    tracker.add_label(child.identifier, f"needs:{focus_hint}")
                except Exception:
                    pass

        # Add inter-task dependencies
        for i, task in enumerate(tasks):
            for dep_idx in task.get("depends_on", []):
                if isinstance(dep_idx, int) and 0 <= dep_idx < len(created) and dep_idx != i:
                    try:
                        tracker.add_dependency(
                            created[i].identifier, created[dep_idx].identifier
                        )
                    except Exception:
                        pass

        # Label the original issue as decomposed and move to deferred
        try:
            tracker.add_label(parent_issue.identifier, "decomposed")
        except Exception:
            pass
        try:
            tracker.update_issue(parent_issue.identifier, status="deferred")
        except Exception:
            pass

    def _backoff_delay(self, attempt: int) -> int:
        """Compute exponential backoff delay."""
        delay = min(10000 * (2 ** (attempt - 1)), self.config.max_retry_backoff_ms)
        return delay

    def _schedule_retry(
        self,
        issue_id: str,
        attempt: int,
        identifier: str,
        delay_ms: int,
        error: str | None,
        escalated_profile: str | None = None,
    ) -> None:
        """Schedule a retry timer for an issue."""
        # Cancel existing retry
        existing = self.state.retry_attempts.pop(issue_id, None)
        if existing and existing.timer_handle and not existing.timer_handle.done():
            existing.timer_handle.cancel()

        due_at_ms = time.monotonic() * 1000 + delay_ms

        loop = asyncio.get_event_loop()
        timer = loop.call_later(
            delay_ms / 1000.0,
            lambda: asyncio.create_task(self._on_retry_timer(issue_id)),
        )

        self.state.retry_attempts[issue_id] = RetryEntry(
            issue_id=issue_id,
            identifier=identifier,
            attempt=attempt,
            due_at_ms=due_at_ms,
            timer_handle=timer,
            error=error,
            escalated_profile=escalated_profile,
        )
        # Emit retry scheduled event on EventBus
        self.event_bus.emit(EventType.ISSUE_RETRY_SCHEDULED, {
            "issue_id": issue_id,
            "identifier": identifier,
            "attempt": attempt,
            "delay_ms": delay_ms,
            "error": error,
        })

    async def _on_retry_timer(self, issue_id: str) -> None:
        """Handle retry timer expiration.

        Posts a RETRY_FIRED event to wake the dispatch loop, then immediately
        dispatches the issue (same as before) so retries are still prompt.
        The event also ensures the main loop runs a _tick() to catch any other
        work that may have appeared while the timer was pending.
        """
        retry = self.state.retry_attempts.pop(issue_id, None)
        if not retry:
            return

        # Wake the dispatch loop — even if we handle dispatch directly below,
        # the loop should run a tick to pick up any other work that appeared.
        self._post_event(DispatchEvent(
            event_type=DispatchEventType.RETRY_FIRED,
            issue_id=issue_id,
        ))

        try:
            candidates = self._fetch_all_candidates()
        except (TrackerError, ProjectError):
            # Requeue
            self._schedule_retry(
                issue_id,
                retry.attempt + 1,
                retry.identifier,
                self._backoff_delay(retry.attempt + 1),
                "retry poll failed",
            )
            return

        issue = next((i for i in candidates if i.id == issue_id), None)
        if issue is None:
            # Issue no longer active, release claim
            self.state.claimed.discard(issue_id)
            logger.info("Retry released claim issue_id=%s (no longer candidate)", issue_id)
            return

        if self._available_slots() <= 0:
            self._schedule_retry(
                issue_id,
                retry.attempt + 1,
                issue.identifier,
                self._backoff_delay(retry.attempt + 1),
                "no available orchestrator slots",
            )
            return

        await self._dispatch(issue, attempt=retry.attempt,
                             override_profile=retry.escalated_profile)

    def _fetch_running_states(self, by_project: dict) -> dict[str, Issue]:
        """Fetch current states for running issues (blocking, runs in thread).

        Parallelizes across projects; each project's tracker already
        parallelizes individual bd show calls internally.
        """
        if not by_project:
            return {}

        def _fetch_for_project(item: tuple) -> list[tuple[str | None, Issue]]:
            pid, ids = item
            try:
                tracker = self._tracker_for_project(pid) if pid else self.tracker
                refreshed = tracker.fetch_issue_states_by_ids(ids)
                return [(pid, issue) for issue in refreshed]
            except (TrackerError, ProjectError):
                logger.debug("Reconciliation refresh failed for project %s", pid)
                return []

        refreshed_map: dict[str, Issue] = {}
        with ThreadPoolExecutor(max_workers=min(len(by_project), 4)) as pool:
            for results in pool.map(_fetch_for_project, by_project.items()):
                for pid, issue in results:
                    issue.project_id = pid
                    refreshed_map[issue.id] = issue
        return refreshed_map

    async def _reconcile(self) -> None:
        """Reconcile running issues: stall detection + tracker state refresh."""
        # Part A: Stall detection
        if self.config.stall_timeout_ms > 0:
            now_mono = time.monotonic()
            for issue_id, entry in list(self.state.running.items()):
                last_ts = None
                if entry.session and entry.session.last_timestamp:
                    last_ts = entry.session.last_timestamp.timestamp()
                else:
                    last_ts = entry.started_at.timestamp()

                elapsed_ms = (time.time() - last_ts) * 1000
                if elapsed_ms > self.config.stall_timeout_ms:
                    logger.warning(
                        "Stall detected issue_id=%s issue_identifier=%s elapsed_ms=%.0f",
                        issue_id,
                        entry.identifier,
                        elapsed_ms,
                    )
                    await self._terminate_running(issue_id, cleanup_workspace=False)
                    next_attempt = (entry.retry_attempt or 0) + 1
                    self._schedule_retry(
                        issue_id,
                        next_attempt,
                        entry.identifier,
                        self._backoff_delay(next_attempt),
                        "stall timeout",
                    )

        # Part B: Tracker state refresh
        running_ids = list(self.state.running.keys())
        if not running_ids:
            return

        # Group running issues by project for targeted tracker queries
        by_project: dict[str | None, list[str]] = {}
        for issue_id, entry in self.state.running.items():
            pid = entry.issue.project_id if entry.issue else None
            by_project.setdefault(pid, []).append(issue_id)

        # Run blocking tracker queries in dedicated tick pool
        loop = asyncio.get_event_loop()
        refreshed_map = await loop.run_in_executor(
            self._tick_pool, self._fetch_running_states, by_project
        )
        terminal_norms = {s.strip().lower() for s in self.config.tracker_terminal_states}
        active_norms = {s.strip().lower() for s in self.config.tracker_active_states}

        for issue_id in running_ids:
            if issue_id not in self.state.running:
                continue
            issue = refreshed_map.get(issue_id)
            if not issue:
                continue

            state_norm = issue.state.strip().lower()
            if state_norm == "in_progress":
                # Still in progress — update issue snapshot
                self.state.running[issue_id].issue = issue
            elif state_norm in terminal_norms:
                logger.info(
                    "Reconcile: terminal state issue_id=%s state=%s",
                    issue_id,
                    issue.state,
                )
                await self._terminate_running(issue_id, cleanup_workspace=True)
            else:
                # Moved out of in_progress (to open, deferred, etc.) — stop agent
                logger.warning(
                    "Reconcile: no longer in_progress issue_id=%s state=%s — terminating agent",
                    issue_id,
                    issue.state,
                )
                running_entry = self.state.running.get(issue_id)
                await self._terminate_running(issue_id, cleanup_workspace=False)
                # If state reverted to an active state (e.g. open), mark as claimed
                # with a cooldown to prevent immediate re-dispatch loops
                if state_norm in active_norms and running_entry:
                    reopen_count = self.state.reopen_counts.get(issue_id, 0) + 1
                    self.state.reopen_counts[issue_id] = reopen_count
                    if reopen_count >= 3:
                        logger.warning(
                            "Reconcile: issue %s reverted to %s %d times — marking completed to stop loop",
                            running_entry.identifier, state_norm, reopen_count)
                        self.state.completed.add(issue_id)
                    else:
                        delay = self._backoff_delay(reopen_count)
                        logger.info(
                            "Reconcile: scheduling retry for %s in %dms (%d/3)",
                            running_entry.identifier, delay, reopen_count)
                        self._schedule_retry(
                            issue_id,
                            attempt=reopen_count,
                            identifier=running_entry.identifier,
                            delay_ms=delay,
                            error=f"state reverted to {state_norm}",
                        )

    _ARCHIVE_DAYS = 7

    def _analyze_focus_fit(self, issue: Issue, project_id: str | None) -> None:
        """Analyze a completed issue's work against existing foci.

        If no focus covers the work well, saves a suggestion for a new one.
        """
        try:
            tracker = self._tracker_for_issue(issue)
            comments = tracker.fetch_comments(issue.identifier)
        except Exception:
            return

        suggestion = analyze_completed_issue(issue, comments)
        if suggestion:
            save_suggestion(suggestion)
            logger.info(
                "Focus suggestion created for %s: '%s' (%s)",
                issue.identifier, suggestion.suggested_name, suggestion.suggested_role,
            )

    def _auto_archive(self) -> None:
        """Archive closed issues older than _ARCHIVE_DAYS days."""
        now = datetime.now(timezone.utc)
        projects = self.project_store.list_all()

        trackers: list[tuple[str | None, BeadsTracker]] = []
        if projects:
            for project in projects:
                try:
                    trackers.append((project.id, self._tracker_for_project(project.id)))
                except (ProjectError, TrackerError):
                    pass
        else:
            trackers.append((None, self.tracker))

        for pid, tracker in trackers:
            try:
                closed = tracker.fetch_issues_by_states(self.config.tracker_terminal_states)
                for issue in closed:
                    if tracker.is_archived(issue):
                        continue
                    if issue.closed_at and (now - issue.closed_at).days >= self._ARCHIVE_DAYS:
                        try:
                            tracker.archive_issue(issue.identifier)
                            logger.info("Auto-archived issue %s (closed %d days ago)",
                                        issue.identifier, (now - issue.closed_at).days)
                        except TrackerError as exc:
                            logger.debug("Failed to archive %s: %s", issue.identifier, exc)
            except (TrackerError, ProjectError) as exc:
                logger.debug("Auto-archive fetch failed for project %s: %s", pid, exc)

    async def _terminate_running(
        self, issue_id: str, cleanup_workspace: bool
    ) -> None:
        """Terminate a running worker and optionally clean its workspace."""
        entry = self.state.running.pop(issue_id, None)
        if not entry:
            return

        # Cancel the worker task
        if entry.worker_task and not entry.worker_task.done():
            entry.worker_task.cancel()
            try:
                await entry.worker_task
            except (asyncio.CancelledError, Exception):
                pass

        # Add runtime to totals
        elapsed = (datetime.now(timezone.utc) - entry.started_at).total_seconds()
        self.state.agent_totals.seconds_running += elapsed
        if entry.session:
            self.state.agent_totals.input_tokens += entry.session.input_tokens
            self.state.agent_totals.output_tokens += entry.session.output_tokens
            self.state.agent_totals.total_tokens += entry.session.total_tokens

        self.state.claimed.discard(issue_id)

        if cleanup_workspace:
            project_id = entry.issue.project_id if entry.issue else None
            try:
                if project_id:
                    self.project_store.remove_worktree(project_id, entry.identifier)
                else:
                    self.workspace_mgr.remove_workspace(entry.identifier)
            except Exception as exc:
                logger.warning(
                    "Workspace cleanup failed issue_identifier=%s error=%s",
                    entry.identifier,
                    exc,
                )

        logger.info(
            "Terminated running issue_id=%s issue_identifier=%s cleanup=%s",
            issue_id,
            entry.identifier,
            cleanup_workspace,
        )

    def get_snapshot(self) -> dict[str, Any]:
        """Return a snapshot of the current orchestrator state for the API."""
        now = datetime.now(timezone.utc)

        running_rows = []
        live_seconds = 0.0
        for issue_id, entry in self.state.running.items():
            elapsed = (now - entry.started_at).total_seconds()
            live_seconds += elapsed
            row: dict[str, Any] = {
                "issue_id": issue_id,
                "issue_identifier": entry.identifier,
                "project_id": entry.issue.project_id if entry.issue else None,
                "state": entry.issue.state,
                "started_at": entry.started_at.isoformat(),
                "agent_profile": entry.agent_profile_name,
                "focus_name": entry.focus_name,
                "focus_role": entry.focus_role,
                "turn_count": 0,
                "session_id": None,
                "last_event": None,
                "last_message": "",
                "last_event_at": None,
                "tokens": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            }
            if entry.session:
                row["session_id"] = entry.session.session_id
                row["turn_count"] = entry.session.turn_count
                row["last_event"] = entry.session.last_event
                row["last_message"] = entry.session.last_message
                row["last_event_at"] = (
                    entry.session.last_timestamp.isoformat()
                    if entry.session.last_timestamp
                    else None
                )
                row["tokens"] = {
                    "input_tokens": entry.session.input_tokens,
                    "output_tokens": entry.session.output_tokens,
                    "total_tokens": entry.session.total_tokens,
                }
            running_rows.append(row)

        retry_rows = []
        for issue_id, retry in self.state.retry_attempts.items():
            due_dt = datetime.fromtimestamp(
                retry.due_at_ms / 1000.0, tz=timezone.utc
            )
            retry_rows.append(
                {
                    "issue_id": issue_id,
                    "issue_identifier": retry.identifier,
                    "attempt": retry.attempt,
                    "due_at": due_dt.isoformat(),
                    "error": retry.error,
                }
            )

        totals = self.state.agent_totals
        return {
            "generated_at": now.isoformat(),
            "paused": self._paused,
            "counts": {
                "running": len(running_rows),
                "retrying": len(retry_rows),
            },
            "running": running_rows,
            "retrying": retry_rows,
            "agent_totals": {
                "input_tokens": totals.input_tokens,
                "output_tokens": totals.output_tokens,
                "total_tokens": totals.total_tokens,
                "seconds_running": totals.seconds_running + live_seconds,
                "estimated_cost": totals.estimated_cost,
            },
            "cost_by_profile": dict(self.state.cost_by_profile),
            "budget": {
                "limit": self.config.budget_limit,
                "spent": totals.estimated_cost,
                "exceeded": self.state.budget_exceeded,
            },
            "agent_profiles": [
                {
                    "name": p.name,
                    "command": p.command,
                    "provider_id": p.provider_id or (dp.id if (dp := self.provider_store.get_default()) else None),
                    "model": p.model,
                    "model_role": p.model_role,
                }
                for p in self.config.agent_profiles
            ],
            "rate_limits": self.state.rate_limits,
            "projects": [p.to_dict() for p in self.project_store.list_all()],
            "alerts": list(self._alerts),
        }

    def get_issue_detail(self, issue_identifier: str) -> dict[str, Any] | None:
        """Return detailed state for a specific issue."""
        # Search running
        for issue_id, entry in self.state.running.items():
            if entry.identifier == issue_identifier:
                snapshot_entry = None
                if entry.session:
                    snapshot_entry = {
                        "session_id": entry.session.session_id,
                        "turn_count": entry.session.turn_count,
                        "state": entry.issue.state,
                        "started_at": entry.started_at.isoformat(),
                        "last_event": entry.session.last_event,
                        "last_message": entry.session.last_message,
                        "last_event_at": (
                            entry.session.last_timestamp.isoformat()
                            if entry.session.last_timestamp
                            else None
                        ),
                        "tokens": {
                            "input_tokens": entry.session.input_tokens,
                            "output_tokens": entry.session.output_tokens,
                            "total_tokens": entry.session.total_tokens,
                        },
                    }
                return {
                    "issue_identifier": entry.identifier,
                    "issue_id": issue_id,
                    "status": "running",
                    "workspace": {
                        "path": self.workspace_mgr.workspace_path_for(entry.identifier),
                    },
                    "running": snapshot_entry,
                    "retry": None,
                }

        # Search retry queue
        for issue_id, retry in self.state.retry_attempts.items():
            if retry.identifier == issue_identifier:
                due_dt = datetime.fromtimestamp(
                    retry.due_at_ms / 1000.0, tz=timezone.utc
                )
                return {
                    "issue_identifier": retry.identifier,
                    "issue_id": issue_id,
                    "status": "retrying",
                    "workspace": {
                        "path": self.workspace_mgr.workspace_path_for(retry.identifier),
                    },
                    "running": None,
                    "retry": {
                        "attempt": retry.attempt,
                        "due_at": due_dt.isoformat(),
                        "error": retry.error,
                    },
                }

        return None

    def _notify_observers(self) -> None:
        """Notify any registered observers of state changes (includes issues refresh).

        Emits EventType.ORCHESTRATOR_TICK on the EventBus (authoritative) and
        also calls legacy _observers callbacks for backward compatibility.
        """
        snapshot = self.get_snapshot()
        # EventBus (authoritative)
        self.event_bus.emit(EventType.ORCHESTRATOR_TICK, {"snapshot": snapshot})
        # Legacy observer lists (backward compat)
        for observer in self._observers:
            try:
                observer(snapshot)
            except Exception:
                pass

    def _notify_state_only(self) -> None:
        """Notify observers with state only (no issues refresh).

        Used for agent activity updates where issue data hasn't changed.
        Emits EventType.STATE_UPDATED on the EventBus and calls legacy
        _state_only_observers callbacks for backward compatibility.
        """
        snapshot = self.get_snapshot()
        # EventBus (authoritative)
        self.event_bus.emit(EventType.STATE_UPDATED, {"snapshot": snapshot})
        # Legacy observer lists (backward compat)
        for observer in self._state_only_observers:
            try:
                observer(snapshot)
            except Exception:
                pass

    def _notify_activity(self, identifier: str, entry: Any) -> None:
        """Notify observers of a specific agent activity entry.

        Emits EventType.AGENT_ACTIVITY on the EventBus and calls legacy
        _activity_observers callbacks for backward compatibility.
        """
        payload = {
            "identifier": identifier,
            "entry": entry.to_dict() if hasattr(entry, "to_dict") else str(entry),
        }
        # EventBus (authoritative)
        self.event_bus.emit(EventType.AGENT_ACTIVITY, payload)
        # Legacy observer lists (backward compat)
        for observer in self._activity_observers:
            try:
                observer(identifier, entry)
            except Exception:
                pass
