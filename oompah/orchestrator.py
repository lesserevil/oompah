"""Orchestrator: polling, dispatch, reconciliation, and retry management."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from enum import Enum
from typing import Any

from oompah.agent import AgentError, AgentEvent, AgentSession
from oompah.agent_profile_store import AgentProfileStore
from oompah.api_agent import AgentActivity, ApiAgentSession
from oompah.completion_verifier import VerifierResult, verify_completion
from oompah.config import ServiceConfig, WorkflowError, load_workflow, validate_dispatch_config
from oompah.dolt_sync import (
    DoltSyncResult,
    DoltSyncState,
    get_or_create_state as _dolt_get_or_create_state,
    summarize_for_alerts as _dolt_summarize_for_alerts,
    sync_project_dolt,
)
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
from oompah.focus import (
    analyze_completed_issue, load_foci, save_suggestion, select_focus,
    select_focus_async,
)
from oompah.prompt import PromptError, build_continuation_prompt, render_prompt
from oompah.projects import ProjectError, ProjectStore
from oompah.providers import ProviderStore
from oompah.roles import RoleStore
from oompah.scm import detect_provider, extract_repo_slug
from oompah.error_watcher import ErrorWatcher
from oompah.tracker import (
    BeadsTracker,
    TrackerError,
    TrackerNotConfiguredError,
    TrackerTimeoutError,
)
from oompah.workspace import WorkspaceError, WorkspaceManager
from oompah.yolo_watchdog import (
    CoverageRecord,
    WatchdogPattern,
    YoloActionRecord,
    is_already_mergeable_error,
    count_consecutive_already_mergeable,
    make_action_history,
    make_coverage_history,
    run_all_detectors,
    D4_ALREADY_MERGEABLE_THRESHOLD,
)

import json
import os

logger = logging.getLogger(__name__)


def _error_class_for_tracker_exc(exc: BaseException) -> str:
    """Classify a tracker/project exception for error_watcher dedup.

    Returned values match the documented classes used by the error
    watcher fingerprint:
      - "bd_timeout"           — TrackerTimeoutError (subprocess timeout)
      - "tracker_not_configured" — TrackerNotConfiguredError (no DB)
      - "bd_failed"            — generic TrackerError
      - "project_error"        — ProjectError fallback

    The returned class collapses every report with the same class to one
    bead in the dedup window, regardless of which project/subcommand
    surfaced the failure.
    """
    if isinstance(exc, TrackerTimeoutError):
        return "bd_timeout"
    if isinstance(exc, TrackerNotConfiguredError):
        return "tracker_not_configured"
    if isinstance(exc, TrackerError):
        return "bd_failed"
    return "project_error"

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


# ---------------------------------------------------------------------------
# YOLO merge-failure classification (oompah-zlz_2-btf.2)
#
# When ``enable_auto_merge`` (queue mode) or ``merge_review`` (direct mode)
# returns ``(False, msg)``, we need to decide what to do. The previous
# behavior dispatched a P0 conflict-resolution agent for ANY failure, which
# is wrong for repo-configuration errors (e.g. the GitHub repo-level
# "Allow auto-merge" toggle is disabled): no amount of code changes on the
# branch will fix that. Spinning up an agent for those is pure waste.
#
# We classify into three buckets:
#   - "config":    operator-action errors (repo settings). Log + surface
#                  to dashboard, do NOT dispatch an agent.
#   - "conflict":  real merge conflict on the branch. Dispatch as before.
#   - "transient": rate limits, 5xx, network blips. Log a warning and
#                  retry next cycle. Don't dispatch.
# ---------------------------------------------------------------------------

# Substrings whose presence in the SCM error message indicates a repo-level
# configuration problem the operator must fix. Lower-case; matched
# case-insensitively against the message body.
_REPO_CONFIG_ERROR_SUBSTRINGS: tuple[str, ...] = (
    "auto-merge not allowed",
    "auto-merge is not enabled",
    "auto merge is not allowed",
    "set allow_auto_merge=true",
    "allow_auto_merge",
    "auto_merge_method",
    "branch protection",
    "required status checks are not satisfied",  # branch protection blocking
    "required reviews are not satisfied",
    "merge commits are not allowed",
    "squash merging is not allowed",
    "rebase merging is not allowed",
)

# Substrings indicating a real merge conflict on the branch (agent-action).
_CONFLICT_ERROR_SUBSTRINGS: tuple[str, ...] = (
    "merge conflict",
    "not mergeable",
    "merge conflicts",
    "has conflicts",
    "branch is not up to date",  # not strictly a conflict, but agent-fixable
)


def _classify_yolo_merge_error(msg: str) -> str:
    """Classify a failure message from enable_auto_merge / merge_review.

    Returns one of:
        "config"    — repo configuration error (operator must fix)
        "conflict"  — merge conflict (dispatch resolution agent)
        "transient" — anything else (rate limit, transient API error)

    Classification is intentionally substring-based and conservative.
    Unknown errors fall into "transient" so we err on the side of
    NOT spawning a doomed agent. If a new GitHub error surfaces a real
    conflict but isn't matched here, the consequence is one extra retry
    next tick — far cheaper than a misclassified agent dispatch.
    """
    if not msg:
        return "transient"
    haystack = msg.lower()

    # Config errors first — explicit repo-settings keywords win over
    # anything else (e.g. "auto-merge not allowed" doesn't mean conflict).
    for needle in _REPO_CONFIG_ERROR_SUBSTRINGS:
        if needle in haystack:
            return "config"

    # 404 from the GitHub auto-merge endpoint with auto-merge keywords:
    # the feature isn't enabled on the repo. Same root cause as config.
    if "404" in haystack and ("auto-merge" in haystack or "auto_merge" in haystack):
        return "config"

    for needle in _CONFLICT_ERROR_SUBSTRINGS:
        if needle in haystack:
            return "conflict"

    return "transient"


def _yolo_error_fingerprint(project_id: str, msg: str) -> str:
    """Stable fingerprint of (project_id, normalized error message).

    Used to deduplicate identical repo-config errors across ticks so the
    log shows one line per (project, error) pair instead of one per tick
    per affected PR. Normalization strips runs of whitespace and lower-
    cases the message.
    """
    import hashlib
    normalized = " ".join((msg or "").lower().split())
    return hashlib.sha1(f"{project_id}|{normalized}".encode("utf-8")).hexdigest()[:12]


class Orchestrator:
    """Owns the poll tick, dispatch decisions, and in-memory runtime state."""

    def __init__(self, config: ServiceConfig, workflow_path: str,
                 provider_store: ProviderStore | None = None,
                 project_store: ProjectStore | None = None,
                 agent_profile_store: AgentProfileStore | None = None,
                 role_store: RoleStore | None = None,
                 state_path: str | None = None):
        self.config = config
        self.workflow_path = workflow_path
        self.provider_store = provider_store or ProviderStore()
        self.project_store = project_store or ProjectStore()
        # Agent profile store: owns ``.oompah/agent_profiles.json``.
        # When None, reuse a fresh AgentProfileStore that points at the
        # default path (no seed). The bootstrap path in __main__.py
        # creates a properly-seeded store and passes it in. UI-driven
        # CRUD writes go through this store and trigger reload_config()
        # on the orchestrator (oompah-zlz_2-xaj).
        self.agent_profile_store = agent_profile_store or AgentProfileStore()
        # Role store: owns ``.oompah/roles.json``. Maps role_name →
        # (provider_id, model). When populated, takes priority over
        # the legacy profile.provider_id/profile.model resolution path
        # (see _resolve_provider / _resolve_model). See epic xau7.
        self.role_store = role_store or RoleStore(
            provider_store=self.provider_store,
        )
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
        self._restore_budget_state()
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
        # Dolt sync watchdog state (oompah-zlz_2-5ms2). One entry per
        # project, populated lazily on first sync. The watchdog runs on
        # every full-sync tick (full_sync_interval_ms, default 120s) and
        # pushes/pulls bd dolt state so agent edits propagate to the
        # configured upstream.
        self._dolt_sync_state: dict[str, DoltSyncState] = {}
        self._dolt_sync_last_results: dict[str, DoltSyncResult] = {}
        # Monotonic time of the last dolt sync — gates the watchdog to
        # the full-sync interval. Distinct from _last_full_sync (which is
        # updated every tick) so the dolt sync only fires on the slow
        # cadence regardless of how many event-driven ticks happen.
        self._last_dolt_sync_monotonic: float = 0.0
        self._last_candidates: list[Issue] = []
        self._orphan_reset_counts: dict[str, int] = {}
        self._yolo_limbo_ticks: dict[str, int] = {}
        # YOLO repo-config errors: keyed by (project_id, review_id) →
        # {"msg": str, "fingerprint": str}. Surfaced in reviews_summary
        # and the /api/v1/reviews payload; cleared when the review
        # disappears from the cache. (oompah-zlz_2-btf.2)
        self._yolo_repo_config_errors: dict[tuple[str, str], dict[str, str]] = {}
        # De-dup table for already-logged repo-config error fingerprints
        # so identical errors don't spam the log every tick. Keyed on the
        # fingerprint string. (oompah-zlz_2-btf.2)
        self._logged_repo_config_fingerprints: set[str] = set()
        # YOLO orphan-branch recovery beads: keyed by
        # (project_id, review_id_str, kind) where kind in
        # {"merge-conflict", "ci-fix"} → bead identifier created as the
        # manual-recovery hook for a PR whose source branch doesn't
        # match any existing bead. Used for idempotency so the YOLO
        # loop doesn't file a fresh duplicate bead every tick for the
        # same orphan PR. Cleared when the review leaves the cache.
        # (oompah-zlz_2-975)
        self._yolo_orphan_recovery_beads: dict[tuple[str, str, str], str] = {}
        # YOLO watchdog state (oompah-zlz_2-jg4) — see oompah/yolo_watchdog.py.
        # _yolo_action_history: bounded deque of YoloActionRecord — every
        # YOLO action attempt (success or failure) is appended here so
        # detectors can scan for recurring patterns.
        self._yolo_action_history = make_action_history()
        # _yolo_coverage_history: bounded deque of CoverageRecord — one
        # entry per (tick, project) capturing how many reviews the loop
        # considered vs how many were available, for D2's starvation
        # detector.
        self._yolo_coverage_history = make_coverage_history()
        # _yolo_watchdog_filed: idempotency map. Keyed on
        # WatchdogPattern.pattern_key → identifier of the filed bead.
        # Cleared per (project, review) when the PR's situation
        # resolves (action succeeds or PR closes).
        self._yolo_watchdog_filed: dict[str, str] = {}
        # _yolo_watchdog_d2_warned: per-project set of pattern_keys
        # we've already logged a D2 WARNING for in the current run of
        # consecutive starved ticks. Cleared as soon as a project has a
        # tick with full coverage. Prevents log spam on persistent
        # starvation.
        self._yolo_watchdog_d2_warned: set[str] = set()
        # _yolo_tick_counter: monotonic per-process counter, incremented
        # once per _yolo_review_actions_sync call. Detectors use this
        # to determine "consecutive ticks" semantics.
        self._yolo_tick_counter: int = 0
        # _yolo_already_mergeable_switched: set of (project_id, review_id)
        # for which the orchestrator has switched from enable_auto_merge
        # to direct merge_review (D4 strategy switch). Cleared when the
        # PR resolves (success or no longer in cache).
        self._yolo_already_mergeable_switched: set[tuple[str, str]] = set()
        # Merged-branches cache: persists across ticks, invalidated by webhooks
        self._merged_branches_dirty: bool = True  # start dirty to force first fetch

        # Completion verifier (oompah-zlz_2-y0ns): tracks how many times
        # the verifier has rejected a particular issue's close. After
        # MAX rejections (3) we fail open and let the close stick so a
        # bad verifier prompt or pathological case can't pin an issue
        # forever. Keyed by issue.id (not identifier — id is the stable
        # primary key across reopen).
        self._verifier_reject_counts: dict[str, int] = {}

        # Pending agent-profile swap (oompah-zlz_2-mif). When the API-path
        # AgentProfileStore writes a profile, it queues a fresh list here
        # via :meth:`replace_agent_profiles`. The next ``_tick()`` applies
        # the swap to ``self.config.agent_profiles`` at a quiescent point so
        # mid-poll iterations of the profile list aren't disrupted. ``None``
        # means "no pending swap". A threading.Lock guards write/read pairs
        # against HTTP threads racing with the dispatch loop.
        self._pending_agent_profiles: list[AgentProfile] | None = None
        self._pending_profiles_lock: threading.Lock = threading.Lock()

        # Error watcher registry (oompah-zlz_2-0nc): keyed by project_id
        # (or ``None`` for the global / unscoped watcher).  Populated by
        # :meth:`register_error_watcher` from server.py during startup.
        # The orchestrator calls
        # ``ErrorWatcher.auto_close_for_issue(...)`` on the matching
        # watcher when a worker run finishes successfully via the retry
        # path so that previously filed transient-error beads can close
        # themselves automatically.
        self._error_watchers: dict[str | None, ErrorWatcher] = {}

        # Surface the agent.profiles drift alert (oompah-zlz_2-hye) so
        # the dashboard shows a banner whenever WORKFLOW.md still has a
        # stale agent.profiles block that disagrees with the persisted
        # store. Same channel as auto-update warnings.
        self._arm_profile_drift_alert()

    def _arm_profile_drift_alert(self) -> None:
        """Add or clear the profile-drift alert based on config state.

        Idempotent — call once at __init__ and again on every
        reload_config, so a fresh WORKFLOW.md edit either raises or
        silences the dashboard banner without restart.
        """
        # Always drop any previously-armed drift alert before re-checking.
        self._alerts = [
            a for a in self._alerts if a.get("source") != "profile_drift"
        ]
        if getattr(self.config, "agent_profiles_drift", False):
            self._alerts.append({
                "level": "warning",
                "source": "profile_drift",
                "message": (
                    "WORKFLOW.md agent.profiles block detected and "
                    "differs from persisted profile store — using the "
                    "persisted store. Delete the agent.profiles "
                    "section from WORKFLOW.md to clear this warning."
                ),
            })

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

    def _restore_budget_state(self) -> None:
        """Restore persisted budget spend + window markers on startup.

        If the persisted window has lapsed (the next calendar boundary
        after ``persisted_start`` is at-or-before now) by the time we
        boot, drop the spend (the new process opens a fresh window).
        If the persisted window kind doesn't match the current config
        (operator changed ``budget_window`` between runs), also drop.
        Otherwise carry spend and window_start forward — that's the
        whole point of persistence.
        """
        data = self._load_state()
        persisted_cost = float(data.get("estimated_cost", 0) or 0)
        persisted_start = float(data.get("budget_window_start", 0) or 0)
        persisted_kind = str(data.get("budget_window_kind", "") or "")

        if persisted_start <= 0 or persisted_kind != self.config.budget_window:
            # Either no prior state, or operator switched the window kind.
            return

        now = time.time()
        next_boundary = self._next_budget_boundary(persisted_start)
        if now >= next_boundary:
            # Old window already lapsed before we booted — start fresh.
            return

        self.state.agent_totals.estimated_cost = persisted_cost
        self.state.budget_window_start = persisted_start
        self.state.budget_window_kind = persisted_kind
        if persisted_cost > 0:
            elapsed = now - persisted_start
            remaining = next_boundary - now
            logger.info(
                "Restored budget spend: $%.4f within %s window "
                "(%.0fs elapsed, %.0fs until next boundary)",
                persisted_cost, persisted_kind, elapsed, remaining,
            )

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
        """Apply new config and prompt template from workflow reload.

        Also refreshes the agent profile store and re-seeds
        ``config.agent_profiles`` from it, so a write through
        ``/api/v1/agent-profiles`` takes effect on the next dispatch
        without requiring a WORKFLOW.md edit (oompah-zlz_2-xaj).
        """
        self.config = config
        # Reload the agent profile store from disk and overwrite
        # config.agent_profiles with what the JSON store has, so:
        #  - WORKFLOW.md changes still take effect (config carries fresh
        #    workflow profiles when JSON store is empty);
        #  - JSON store CRUD takes effect after a reload_config() call
        #    (the API handler writes to the store, then calls reload).
        # Skip when the JSON file is missing AND the config has profiles
        # (WORKFLOW.md-only legacy mode).
        try:
            self.agent_profile_store._load()
            store_profiles = self.agent_profile_store.list_all()
            if store_profiles:
                self.config.agent_profiles = store_profiles
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "reload_config: agent profile store reload failed: %s", exc
            )
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
       # File-watcher reload supersedes any pending API-path profile swap —
        # the new ServiceConfig already carries the authoritative profile list.
        with self._pending_profiles_lock:
            self._pending_agent_profiles = None
        # Re-arm the profile-drift alert against the freshly-loaded
        # config so a WORKFLOW.md edit (or a UI write that resolved
        # the drift) updates the dashboard banner immediately
        # (oompah-zlz_2-hye).
        self._arm_profile_drift_alert()
        logger.info("Config reloaded poll_interval_ms=%d full_sync_interval_ms=%d max_agents=%d",
                     config.poll_interval_ms, config.full_sync_interval_ms,
                     config.max_concurrent_agents)

    def replace_agent_profiles(
        self,
        profiles: list[AgentProfile],
        source: str = "api",
    ) -> None:
        """Schedule a partial config reload that swaps only the agent_profiles list.

        Called by AgentProfileStore (or any future caller) when profiles change
        through a non-WORKFLOW.md path. The swap is queued under a lock and
        applied at the next quiescent point — the start of the next ``_tick()``
        — so a tick already in flight observes a single consistent profile list
        end-to-end.

        Logs every swap so API-driven reloads show up in the operator log
        alongside file-watcher reloads.

        In-flight running agents keep their existing profile (the swap only
        affects the NEXT dispatch). Out of scope: hot-swap of running agents.

        Thread-safe — safe to call from HTTP request handlers (which run in
        the asyncio event loop alongside the dispatch tick).
        """
        # Normalize / defensive copy so the caller can't mutate the queued
        # list out from under us between queue and apply.
        snapshot = list(profiles)
        with self._pending_profiles_lock:
            self._pending_agent_profiles = snapshot
        logger.info(
            "Agent profiles reload queued (source=%s, count=%d) — "
            "applies at next tick",
            source, len(snapshot),
        )
        # Wake the dispatch loop so the swap takes effect immediately rather
        # than waiting for the next safety-net full-sync. The loop will call
        # _apply_pending_agent_profiles() at the start of _tick().
        self._post_event(DispatchEvent(
            event_type=DispatchEventType.REFRESH_REQUESTED,
            payload={"reason": f"agent_profiles_reload:{source}"},
        ))

    def _apply_pending_agent_profiles(self) -> bool:
        """Apply a queued profile swap to ``self.config.agent_profiles``.

        Called at the start of every ``_tick()`` (a quiescent point — the
        dispatch loop is single-threaded so no caller is currently iterating
        ``self.config.agent_profiles``). Returns True iff a swap was applied.

        The previous-tick profile list is logged when the swap is applied so
        the operator log shows a clear before/after just like a workflow
        reload.
        """
        with self._pending_profiles_lock:
            pending = self._pending_agent_profiles
            self._pending_agent_profiles = None
        if pending is None:
            return False
        before_names = [p.name for p in self.config.agent_profiles]
        after_names = [p.name for p in pending]
        # Atomic re-assignment of the list attribute (Python guarantees a
        # single-instruction store for attribute writes).
        self.config.agent_profiles = pending
        logger.info(
            "Agent profiles reloaded: before=%s after=%s",
            before_names, after_names,
        )
        # Surface the change to dashboard observers so the budget/profiles
        # snapshot refreshes without waiting for the next tick to publish.
        self._notify_observers()
        return True

    def set_prompt_template(self, template: str) -> None:
        self._prompt_template = template

    def pause(self) -> None:
        """Pause: stop all running agents, cancel pending retries, and
        prevent new dispatches. Agents that were running are terminated;
        retry timers that were scheduled are cancelled. Without this,
        a retry timer fires while paused, bypasses the dispatch loop's
        paused check (which only guards _should_dispatch, not _dispatch
        itself), and re-dispatches an issue against the user's intent.
        """
        self._paused = True
        self._save_paused_state()
        # Cancel pending retries — they bypass _should_dispatch and would
        # otherwise re-dispatch while paused.
        for retry_iid, retry in list(self.state.retry_attempts.items()):
            if retry.timer_handle and not retry.timer_handle.cancelled():
                retry.timer_handle.cancel()
            self.state.retry_attempts.pop(retry_iid, None)
            self.state.claimed.discard(retry_iid)
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
        # Capture whether the user had explicitly paused before this call.
        # We pause internally for the drain regardless, but on the new boot
        # we should respect the user's pre-existing intent — overwriting
        # paused=False unconditionally would silently undo a user-set pause.
        was_user_paused = self._paused
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

        # Preserve user's explicit pause across the restart; otherwise
        # come up unpaused so the saved restart_issues can re-dispatch.
        self._save_state(
            paused=was_user_paused,
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

    # ------------------------------------------------------------------
    # Error watcher integration (oompah-zlz_2-0nc)
    # ------------------------------------------------------------------
    def register_error_watcher(
        self, watcher: ErrorWatcher, project_id: str | None = None
    ) -> None:
        """Register an :class:`ErrorWatcher` so the orchestrator can
        ask it to auto-close transient error beads.

        ``project_id=None`` registers the global / unscoped watcher (the
        one that handles ``logger.error`` records emitted from the
        orchestrator itself and any project-less log file).  Project-
        scoped watchers are registered with their project's id.

        Idempotent: re-registering replaces the previous reference.
        """
        self._error_watchers[project_id] = watcher

    def _error_watchers_for_project(
        self, project_id: str | None
    ) -> list[ErrorWatcher]:
        """Return the watchers that may have observed errors from a
        given project's worker run.

        We always include the unscoped (``None``) watcher because
        ``oompah.orchestrator`` itself logs errors through it; if a
        project-specific watcher is also registered, it gets included
        as well.  Order: project-scoped first so logs read naturally.
        """
        watchers: list[ErrorWatcher] = []
        if project_id and project_id in self._error_watchers:
            watchers.append(self._error_watchers[project_id])
        if None in self._error_watchers:
            watchers.append(self._error_watchers[None])
        return watchers

    def _auto_close_transient_errors_for_entry(
        self, entry: RunningEntry
    ) -> None:
        """Best-effort auto-close of error beads tied to ``entry.issue``.

        Called from ``_on_worker_exit`` when ``reason == "normal"`` and
        the run was retry-driven (``retry_attempt > 0``).  Errors
        during auto-close are swallowed and logged so they never block
        the worker-exit path.
        """
        if not entry.issue or not entry.issue.id:
            return
        project_id = entry.issue.project_id
        for watcher in self._error_watchers_for_project(project_id):
            try:
                closed = watcher.auto_close_for_issue(
                    entry.issue.id,
                    issue_identifier=entry.identifier,
                )
                if closed:
                    logger.info(
                        "Auto-closed %d transient error bead(s) for %s: %s",
                        len(closed), entry.identifier, ", ".join(closed),
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(
                    "auto_close_for_issue failed for %s: %s",
                    entry.identifier, exc,
                )

    @property
    def is_paused(self) -> bool:
        return self._paused

    def invalidate_merged_branches(self) -> None:
        """Mark the merged-branches cache as stale (called by webhook handler)."""
        self._merged_branches_dirty = True

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
        # One-shot diagnostic: announce ACP-mode profiles so operators
        # know the budget gate doesn't apply to them. Mirrors the
        # existing rate-limit / budget startup logging.
        acp_profiles = [
            p.name for p in self.config.agent_profiles
            if (p.mode or "auto").lower() == "acp"
        ]
        if acp_profiles:
            logger.info(
                "ACP profiles bypass budget tracking — calls are billed against "
                "the active claude subscription, not by token. Profiles: %s",
                ", ".join(acp_profiles),
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

        # 0. Apply any pending profile swap queued via replace_agent_profiles().
        # Done at the very start of the tick so every step below sees a single
        # consistent profile list — mirrors the file-watcher reload semantics.
        self._apply_pending_agent_profiles()

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

        # 5a. Dolt sync watchdog (oompah-zlz_2-5ms2). Pushes/pulls bd dolt
        # state to/from the configured upstream so agent edits propagate
        # across machines. Gated to the full-sync interval (no-op on
        # event-driven ticks). All subprocesses are time-bound; failures
        # are recorded into _dolt_sync_state and surface as alerts.
        dolt_ms = await self._handle_dolt_sync()
        t4b = time.monotonic()

        # 5b. Watchdog: detect and fix stuck issues (periodic, lightweight).
        # Offloaded to the tick thread pool to keep the event loop unblocked —
        # the four sub-checks iterate _last_candidates and may issue bd CLI
        # calls per stuck issue, which can block 200ms-2s. Safe because
        # watchdog runs after all other tick handlers have settled, so the
        # shared mutable state it reads (state.completed, _orphan_reset_counts,
        # _last_candidates) is not being concurrently written.
        await asyncio.get_event_loop().run_in_executor(
            self._tick_pool, self._maybe_run_watchdog
        )

        total_ms = (t4b - t0) * 1000
        if total_ms > 2000:
            logger.warning(
                "Slow tick: %.0fms (reconcile=%.0f reviews=%.0f dispatch=%.0f "
                "yolo=%.0f archive=%.0f merged=%.0f dolt_sync=%.0f)",
                total_ms,
                (t1 - t0) * 1000,
                (t2 - t1) * 1000,
                (t3 - t3_start) * 1000,
                yolo_ms, archive_ms, merged_ms, dolt_ms,
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

        Merged branches are cached across ticks and only re-fetched when
        ``_merged_branches_dirty`` is set (by webhooks or first tick).
        """
        self._reviews_cache = {}  # reset per tick — shared by PR branches + YOLO
        loop = asyncio.get_event_loop()
        reviews_task = loop.run_in_executor(self._tick_pool, self._fetch_all_reviews)

        if self._merged_branches_dirty:
            merged_task = loop.run_in_executor(self._tick_pool, self._fetch_all_merged_branches)
            reviews_by_project, merged_branches = await asyncio.gather(
                reviews_task, merged_task
            )
            self._merged_branches = merged_branches
            self._merged_branches_dirty = False
        else:
            reviews_by_project = await reviews_task

        self._reviews_cache = reviews_by_project
        # Derive unmerged review branches from cached reviews
        self._unmerged_review_branches = {
            r.source_branch
            for reviews in reviews_by_project.values()
            for r in reviews
            if r.source_branch
        }
        logger.debug("Unmerged review branches: %s", sorted(self._unmerged_review_branches))

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

        # Run the entire sort + filter pass in a worker thread so the bd
        # CLI calls inside _should_dispatch (label/blocker resolution at
        # ~150ms each) don't block uvicorn's event loop. Returns the
        # final ordered list of issues that passed _should_dispatch; the
        # async loop below only yields once per actual dispatch — no sync
        # work between yields. See bead oompah-zlz_2-nvr.
        ready = await loop.run_in_executor(
            self._tick_pool, self._select_dispatchable, candidates
        )
        for issue in ready:
            if self._available_slots() <= 0:
                break
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
        await loop.run_in_executor(
            self._tick_pool, self._auto_close_completed_epics, candidates
        )

        # Open the epic→main PR for stacked/shared epics whose children
        # are all closed. Cheap — only walks ``candidates`` plus a fetch
        # of children per active epic. Only acts on epics where the
        # project's epic_strategy is 'stacked' or 'shared'; flat is a
        # no-op (today's behavior).
        await loop.run_in_executor(
            self._tick_pool, self._open_epic_main_prs, candidates
        )

        # Reset orphaned in_progress issues (no agent, no retry).
        # Runs in the executor because orphan detection issues bd update
        # calls — keeping it inline would re-introduce the very same
        # event-loop blocking this bead is fixing.
        await loop.run_in_executor(
            self._tick_pool, self._reset_orphaned_in_progress, candidates
        )

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

    def _dolt_sync_due(self) -> bool:
        """Return True if the dolt sync should fire this tick.

        Gates the watchdog to the full-sync interval. Returns True on
        the very first tick (``_last_dolt_sync_monotonic == 0``) so
        operators don't have to wait one full interval after restart.
        """
        if self._last_dolt_sync_monotonic == 0.0:
            return True
        elapsed_ms = (
            time.monotonic() - self._last_dolt_sync_monotonic
        ) * 1000
        return elapsed_ms >= self.config.full_sync_interval_ms

    async def _handle_dolt_sync(self) -> float:
        """Push/pull bd dolt state for every project (full-sync only).

        Runs as a step in the full-sync tick (oompah-zlz_2-5ms2). Per
        project, pulls then pushes via :func:`sync_project_dolt`. All
        subprocesses are time-bound and run in the tick thread pool so
        a slow remote can't wedge the event loop.

        Returns elapsed milliseconds for inclusion in the slow-tick log
        (0 if the watchdog was skipped this tick because the interval
        hasn't elapsed yet).
        """
        if not self._dolt_sync_due():
            return 0.0
        t0 = time.monotonic()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._tick_pool, self._dolt_sync_all_sync)
        self._last_dolt_sync_monotonic = time.monotonic()
        return (time.monotonic() - t0) * 1000

    def _dolt_sync_all_sync(self) -> None:
        """Synchronous worker: iterate projects and call :func:`sync_project_dolt`.

        Updates ``self._dolt_sync_state`` and ``self._dolt_sync_last_results``
        in place. Merges any divergent/repeated-failure alerts into
        ``self._alerts`` so the dashboard banner surfaces them.
        """
        projects = self.project_store.list_all()
        if not projects:
            return
        interval_s = max(self.config.full_sync_interval_ms / 1000.0, 1.0)
        results: dict[str, DoltSyncResult] = {}
        for project in projects:
            try:
                state = _dolt_get_or_create_state(self._dolt_sync_state, project.id)
                result = sync_project_dolt(
                    project, state, full_sync_interval_s=interval_s,
                )
                results[project.id] = result
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "Dolt sync raised unexpectedly for %s: %s",
                    project.name, exc,
                )
        self._dolt_sync_last_results = results

        # Refresh alerts. Drop any prior dolt_sync entries, then re-add
        # for currently-problematic projects. Same idempotent pattern as
        # _arm_profile_drift_alert / auto_update alert handling.
        self._alerts = [
            a for a in self._alerts if a.get("source") != "dolt_sync"
        ]
        projects_by_id = {p.id: p for p in projects}
        for entry in _dolt_summarize_for_alerts(self._dolt_sync_state, projects_by_id):
            self._alerts.append(entry)

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
            # --autostash handles the routine case where ``bd`` has
            # written to .beads/issues.jsonl since the last commit.
            # Without it, ``--ff-only`` refuses with "Your local changes
            # would be overwritten by merge" and surfaces a UI alert
            # every poll. --ff-only still refuses if origin has actually
            # diverged (i.e. real merge required).
            pull = subprocess.run(
                ["git", "pull", "--ff-only", "--autostash", "origin", "main"],
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
            except TrackerNotConfiguredError:
                # Already logged at WARNING in tracker._run_bd; treat as
                # an empty backlog this tick.
                return []
            except TrackerTimeoutError as exc:
                # Transient — log at WARNING so the error_watcher does
                # not auto-file a duplicate bug bead every tick.
                logger.warning("Tracker fetch timed out: %s", exc)
                return []
            except TrackerError as exc:
                logger.error(
                    "Tracker fetch failed: %s", exc,
                    extra={"error_class": _error_class_for_tracker_exc(exc)},
                )
                return []

        def _fetch_for_project(project) -> list[Issue]:
            try:
                tracker = self._tracker_for_project(project.id)
                issues = tracker.fetch_candidate_issues()
                for issue in issues:
                    issue.project_id = project.id
                return issues
            except TrackerNotConfiguredError:
                # Project's tracker isn't initialized — environmental.
                # Already warned in _run_bd; skip this project for the tick.
                return []
            except TrackerTimeoutError as exc:
                # Transient — log at WARNING so the error_watcher does
                # not auto-file a duplicate bug bead every tick.
                logger.warning(
                    "Fetch timed out for project %s: %s", project.name, exc,
                )
                return []
            except (TrackerError, ProjectError) as exc:
                logger.error(
                    "Fetch failed for project %s: %s", project.name, exc,
                    extra={"error_class": _error_class_for_tracker_exc(exc)},
                )
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

    def is_webhook_healthy(self, project_id: str | None) -> bool:
        """Return True if the project's webhook channel is healthy.

        A project is considered webhook-healthy when the most recent webhook
        delivery was received within the last 150 seconds (~2.5 minutes).
        When healthy, forge polling for that project can be skipped because
        webhooks serve as the primary signal for state changes.

        When the timestamp is absent or stale, the polling loop falls back
        to the periodic full-sync cadence as a safety net.
        """
        if not project_id:
            return False
        project = self.project_store.get(project_id)
        if not project:
            return False
        ts = project.last_webhook_received_at
        # Guard against non-datetime types (e.g. MagicMock in tests).
        if not ts or not isinstance(ts, datetime):
            return False
        # Treat timezone-naive datetimes as UTC to allow comparison.
        # This is safe because webhook timestamps from the database are
        # always stored as UTC (server.py normalises them), so a naive
        # value signals corrupted / misconfigured data — still better
        # than crashing with a TypeError.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        # Fall back to polling if delivery is older than 150 seconds
        age = datetime.now(timezone.utc) - ts
        return age.total_seconds() <= 150

    def _count_open_reviews(self, project_id: str | None) -> int:
        """Return the number of non-draft open MRs/PRs for a project.

        Uses the per-tick reviews cache populated by ``_handle_review_check``.
        Returns 0 for legacy issues that have no project_id.
        """
        if not project_id:
            return 0
        reviews_cache = getattr(self, "_reviews_cache", {})
        project_reviews = reviews_cache.get(project_id, [])
        return sum(1 for r in project_reviews if not r.draft)

    def _epic_in_flight_count(self, parent_id: str) -> int:
        """Number of running OR claimed children that share ``parent_id``.

        Used by the shared-mode dispatch gate to enforce serial child
        dispatch within a single epic worktree. Counts any
        running/claimed child whose ``parent_id`` matches the given
        epic identifier — the orchestrator already keeps these in
        ``state.running`` and ``state.claimed`` (the ID half).

        Returns 0 when the parent_id is empty.
        """
        if not parent_id:
            return 0
        n = 0
        for entry in self.state.running.values():
            other = entry.issue
            if other and (other.parent_id or "") == parent_id:
                n += 1
        return n

    def _project_max_in_flight(self, project_id: str | None) -> int:
        """Return the configured in-flight PR limit for a project.

        Falls back to 1 (original single-in-flight behavior) when the
        project is unknown or has no explicit override set.
        """
        if not project_id:
            return 1
        project = self.project_store.get(project_id)
        if project is None:
            return 1
        raw = getattr(project, "max_in_flight_prs", 1)
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 1

    def _is_project_paused(self, project_id: str | None) -> bool:
        """Return True when the project has been individually paused.

        Composes with the global ``_paused`` flag in ``_should_dispatch``:
        a request is dispatchable only if NEITHER the global nor the
        project's pause is set. Returns False for unknown project ids
        and for legacy issues that have no project_id.
        """
        if not project_id:
            return False
        project = self.project_store.get(project_id)
        if project is None:
            return False
        return bool(getattr(project, "paused", False))

    def _project_has_open_review(self, project_id: str | None) -> bool:
        """Return True if the project is at or above its in-flight PR cap.

        Thin compatibility wrapper around ``_count_open_reviews`` and
        ``_project_max_in_flight``. Retained so callers (tests, subclasses)
        that reference the old name continue to work unchanged.
        """
        return self._count_open_reviews(project_id) >= self._project_max_in_flight(project_id)

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
        # Per-project pause also blocks epic planning for that project.
        if self._is_project_paused(issue.project_id):
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

    def _project_epic_strategy(self, project_id: str | None) -> str:
        """Return the project's epic_strategy ('flat'/'stacked'/'shared').

        Falls back to 'flat' (today's behavior) when the project is
        unknown or the field is missing — so legacy projects.json
        without the field continue to work unchanged.
        """
        if not project_id:
            return "flat"
        project = self.project_store.get(project_id)
        if not project:
            return "flat"
        strategy = (getattr(project, "epic_strategy", None) or "flat").strip().lower()
        if strategy not in ("flat", "stacked", "shared"):
            return "flat"
        return strategy

    def _resolve_parent_epic(self, issue: Issue) -> Issue | None:
        """Resolve a child issue's parent epic, or None when this issue has
        no parent or the parent is not an epic.

        Used by the stacked/shared epic_strategy paths to pick the epic
        branch name (stacked) or shared worktree (shared). Returns None
        for top-level issues (parent_id is None) and for issues whose
        parent is not type=epic (we only special-case epic→child).
        """
        parent_id = (issue.parent_id or "").strip()
        if not parent_id:
            return None
        try:
            tracker = self._tracker_for_issue(issue)
            parent = tracker.fetch_issue_detail(parent_id)
        except Exception as exc:
            logger.debug(
                "Failed to fetch parent epic %s for child %s: %s",
                parent_id, issue.identifier, exc,
            )
            return None
        if not parent:
            return None
        if (parent.issue_type or "").strip().lower() != "epic":
            return None
        # Carry the project_id over from the child for downstream
        # consumers that rely on it (the parent record may have it set
        # already, but be defensive).
        if not parent.project_id and issue.project_id:
            parent.project_id = issue.project_id
        return parent

    def _create_workspace_for_issue(
        self, issue: Issue,
    ) -> tuple[str, Issue | None]:
        """Resolve and create the workspace path used to dispatch ``issue``.

        Returns ``(workspace_path, epic_for_shared_mode)``. The second
        element is non-None only when the project's epic_strategy is
        'shared' AND the issue is a child of an epic — in which case
        callers know to commit/push on the shared epic branch instead
        of the per-bead branch.

        Fall-through behavior:
        - epic_strategy='flat': always per-bead worktree (today's
          behavior).
        - epic_strategy='stacked': per-bead worktree (children PR
          against the epic branch, but each agent still gets its own
          working copy).
        - epic_strategy='shared': children of an epic share the epic's
          worktree; non-children fall back to per-bead.

        The shared-mode epic worktree is created via
        ``project_store.create_epic_worktree``, which is idempotent
        (does NOT hard-reset existing in-flight work).
        """
        if not issue.project_id:
            workspace = self.workspace_mgr.create_for_issue(issue.identifier)
            self.workspace_mgr.run_before_run(workspace.path)
            return workspace.path, None

        strategy = self._project_epic_strategy(issue.project_id)
        if strategy == "shared":
            parent_epic = self._resolve_parent_epic(issue)
            if parent_epic is not None:
                wp = self.project_store.create_epic_worktree(
                    issue.project_id, parent_epic.identifier,
                )
                return wp, parent_epic

        wp = self.project_store.create_worktree(
            issue.project_id, issue.identifier,
        )
        return wp, None

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

    def _open_epic_main_prs(self, candidates: list[Issue]) -> int:
        """Open epic completion PRs for stacked/shared epics whose children are
        all closed.

        Walks ``candidates`` looking for active epics on a project whose
        ``epic_strategy`` is 'stacked' or 'shared'. For each such epic:

        * If it has no children, skip (nothing has been done — wait for
          the planner).
        * If any child is NOT in a terminal state (open, in_progress,
          deferred, blocked, ...), skip — mid-flight children DELAY the
          push (acceptance criteria explicit edge case).
        * If a PR with source ``epic-<identifier>`` already exists, skip
          — idempotent.
        * Otherwise: push the epic branch and open a single
          source=``epic-<identifier>`` PR targeting the resolved branch:

          - For top-level epics (no parent epic, or non-shared strategy):
            targets ``project.branch`` (typically ``main``).
          - For nested epics in ``shared`` mode (the epic itself has a
            parent epic): targets the parent epic's branch. This creates
            a multi-level merge chain where child epic B's PR targets
            parent A's branch; A's PR targets main only when ALL of A's
            direct children (including sub-epic B) are terminal.

        Returns the number of PRs opened.
        """
        terminal_norms = {
            s.strip().lower() for s in self.config.tracker_terminal_states
        }
        opened = 0
        for issue in candidates:
            if issue.issue_type != "epic":
                continue
            state_norm = (issue.state or "").strip().lower()
            if state_norm in terminal_norms:
                continue  # epic itself is closed; closing logic owns this
            project_id = issue.project_id
            if not project_id:
                continue
            strategy = self._project_epic_strategy(project_id)
            if strategy not in ("stacked", "shared"):
                continue

            children = self._fetch_epic_children(issue)
            if not children:
                continue  # nothing to roll up yet

            # All children must be in a terminal state. open / in_progress /
            # deferred / blocked all DELAY the push (per the acceptance
            # criteria). This intentionally treats deferred or blocked as
            # incomplete — operator action required to advance them.
            all_terminal = all(
                (c.state or "").strip().lower() in terminal_norms
                for c in children
            )
            if not all_terminal:
                continue

            project = self.project_store.get(project_id)
            if not project or not project.repo_url:
                continue
            provider = detect_provider(
                project.repo_url, access_token=project.access_token,
            )
            if provider is None:
                continue
            slug = extract_repo_slug(project.repo_url)
            epic_branch = self.project_store.epic_branch_name(issue.identifier)

            # Idempotency: if a review already exists with this source
            # branch, do nothing.
            reviews = getattr(self, "_reviews_cache", {}).get(project_id, [])
            already_open = any(
                r.source_branch == epic_branch and not r.draft for r in reviews
            )
            if already_open:
                continue

            # Push the epic branch from the shared epic worktree (shared
            # mode) or from the project's main repo path (stacked mode —
            # children's PRs already pushed their commits to the epic
            # branch on the remote).
            try:
                self._push_epic_branch(project, issue.identifier)
            except Exception as exc:
                logger.warning(
                    "Failed to push epic branch %s for epic %s: %s",
                    epic_branch, issue.identifier, exc,
                )
                continue

            # Resolve the target branch: for nested epics in shared mode,
            # the child epic's PR targets its parent's branch rather than main.
            # For top-level epics (or non-shared strategies), targets project.branch.
            target_branch = self._resolve_epic_target_branch(issue, project)

            title = (
                f"{issue.identifier}: {issue.title}"
                if issue.title else f"Epic {issue.identifier}"
            )
            description = issue.description or ""
            try:
                result = provider.create_review(
                    slug, title, epic_branch,
                    target_branch=target_branch,
                    description=description,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to create epic PR for %s on %s (target=%s): %s",
                    issue.identifier, project.name, target_branch, exc,
                )
                continue

            if result is None:
                logger.warning(
                    "Failed to create epic PR for %s on %s (target=%s) "
                    "(provider returned None)",
                    issue.identifier, project.name, target_branch,
                )
                continue

            logger.info(
                "Opened epic PR for %s on %s (review #%s, source=%s, target=%s)",
                issue.identifier, project.name, result.id, epic_branch, target_branch,
            )
            opened += 1
        return opened

    def _resolve_epic_target_branch(self, epic: Issue, project) -> str:
        """Resolve the target branch for an epic's completion PR.

        For nested epics in ``shared`` mode: if ``epic`` has a parent epic P,
        the completion PR should target P's branch (``epic-<P.identifier>``)
        rather than ``main``. This gives Linux-kernel-style multi-level merge
        trains where each sub-epic lands on its parent's branch before the
        top-level epic lands on main.

        For all other cases (top-level epic, non-shared mode, or no parent
        epic), the PR targets ``project.branch`` (typically ``main``).

        Only fires for ``epic_strategy='shared'`` — stacked mode is handled
        differently (per-child PRs already target the parent's branch
        directly, no "completion PR" intermediary is needed).
        """
        strategy = self._project_epic_strategy(epic.project_id)
        if strategy == "shared":
            parent_epic = self._resolve_parent_epic(epic)
            if parent_epic is not None:
                return self.project_store.epic_branch_name(parent_epic.identifier)
        return project.branch

    def _push_epic_branch(self, project, epic_identifier: str) -> None:
        """Push the shared epic branch from the local repo to origin.

        Best-effort: subprocess errors propagate so the caller can log
        and skip PR creation for this tick.
        """
        epic_branch = self.project_store.epic_branch_name(epic_identifier)
        # The branch lives on the project's main repo (stacked mode
        # children pushed there) or the shared epic worktree (shared
        # mode). Either way ``git push origin <branch>`` from the main
        # clone is sufficient because git knows about all worktrees.
        subprocess.run(
            ["git", "push", "origin", epic_branch],
            cwd=project.repo_path,
            capture_output=True, text=True, check=True, timeout=60,
        )

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
        # Per-project pause composes with the global pause: dispatch
        # is allowed only if NEITHER is set. This lets an operator
        # quiet one repo (CI flaking, PR backlog review, forge outage)
        # without halting the others. Same reject idiom as the global
        # pause; surfaced via the `paused` flag on each project in the
        # state snapshot. See bead oompah-zlz_2-u7c.
        if self._is_project_paused(issue.project_id):
            return _reject("project_paused")
        if not issue.id or not issue.identifier or not issue.title or not issue.state:
            return _reject("missing_fields")
        # Refuse to dispatch beads with no body. A title alone is not enough
        # context for an agent to do anything sensible — and we've watched
        # agents burn dozens of turns spinning on placeholder beads created
        # for ad-hoc CLI testing. Operator either fills in the description,
        # closes the bead, or defers it. Epics get a pass because they are
        # planned separately and may legitimately start as title-only.
        if issue.issue_type != "epic" and not (issue.description or "").strip():
            return _reject("empty_description")
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
        # Blocker rule for "open"/"todo" state — bypassed for P0.
        # P0 work is critical and is allowed to run even when its
        # declared blockers are non-terminal or have unmerged PRs.
        # Rationale: a P0 ci-fix on its own branch doesn't actually
        # depend on an upstream PR landing — its branch state is
        # independent. The `human-only` and `asking_question` label
        # gates above still apply and remain the operator's escape
        # hatch when a P0 must wait for a human. (oompah-zlz_2-dyi)
        if not is_p0 and state_norm in ("open", "todo"):
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
        # Serialize MR/PR fixes by project: if a project has reached its
        # configured in-flight PR cap, don't dispatch another agent until an
        # existing review merges. This prevents multiple simultaneous merges
        # from conflicting with each other (each merge changes the target branch).
        # P0 issues bypass this check to ensure critical fixes are never blocked.
        # The cap defaults to 1 (preserving the original single-in-flight
        # behavior) and can be raised per-project via Project.max_in_flight_prs
        # once GitHub Merge Queue is enabled for that repo.
        if not is_p0:
            n_open = self._count_open_reviews(issue.project_id)
            limit = self._project_max_in_flight(issue.project_id)
            if n_open >= limit:
                return _reject(f"open_reviews_at_cap={n_open}/{limit}")
        # epic_strategy=='shared' serializes child dispatch within an epic.
        # Multiple children share one worktree+branch and we don't have an
        # in-worktree coordination protocol yet (out of scope per the bead),
        # so only one child of a given epic can be in flight at a time.
        # Multiple epics still dispatch in parallel up to max_in_flight_prs.
        # P0 children bypass this check.
        if not is_p0 and issue.parent_id:
            strategy = self._project_epic_strategy(issue.project_id)
            if strategy == "shared":
                in_flight = self._epic_in_flight_count(issue.parent_id)
                if in_flight >= 1:
                    return _reject(
                        f"shared_epic_busy={issue.parent_id} count={in_flight}"
                    )
        # ACP-mode profiles bypass the budget gate entirely — their
        # per-token cost is billed against the operator's claude
        # subscription, not the per-token API meter the budget tracks.
        # Done BEFORE the cost-aware free-tier check so we don't pay
        # the model-resolution cost when the answer is "subscription".
        # See plans/acp-agent.md and bead oompah-zlz_2-bcl.
        if self._would_dispatch_via_acp(issue):
            return True
        # Budget circuit breaker — model-aware. When the window's spend has
        # exceeded the cap we still allow dispatch on models the provider
        # has explicitly priced at $0 (e.g. an internal-tier MiniMax). That
        # way an over-budget orchestrator continues chewing through cheap
        # work while paid escalations queue for the next window. See bead
        # oompah-zlz_2-fvt for the full rationale.
        if not self._check_budget():
            if not self.state.budget_exceeded:
                self.state.budget_exceeded = True
                logger.warning("Budget limit exceeded (%.2f/%.2f), halting paid dispatch",
                             self.state.agent_totals.estimated_cost, self.config.budget_limit)
            free_model = self._would_dispatch_on_free_model(issue)
            if free_model:
                self.state.free_tier_dispatches_this_window += 1
                logger.info(
                    "Budget exceeded ($%.4f spent vs $%.4f limit) but dispatching"
                    " %s on free-tier model %s",
                    self.state.agent_totals.estimated_cost,
                    self.config.budget_limit,
                    issue.identifier,
                    free_model,
                )
                return True
            return _reject("budget_exceeded_paid")
        return True

    def _would_dispatch_via_acp(self, issue: Issue) -> bool:
        """True if the dispatch would route through an ACP profile
        AND the resolved provider is subscription-billed. The budget
        gate uses this to bypass the cap for subscription-billed
        sessions; subscription ACP dispatches don't consume the
        per-token API meter that ``budget_limit`` tracks.

        Per-token-billed ACP providers (``billing_model == "per_token"``,
        e.g. some Codex tiers or third-party agents) DO consume the
        budget — they fall through to the normal _check_budget gate.
        See bead oompah-zlz_2-ag7h.

        Mirrors the safety-critical ACP-routing carve-out in
        ``_dispatch`` (oompah-zlz_2-lfy): when a merge-conflict /
        ci-fix bead would otherwise resolve to a non-ACP profile but
        an ACP profile is configured, the dispatcher swaps to ACP —
        so the budget gate must agree (subject to the same
        subscription-only constraint), otherwise an over-budget
        orchestrator would reject a dispatch that would actually be
        subscription-billed.

        Conservative on resolution failure (returns False) so a
        misconfigured profile cannot accidentally bypass the cap.
        """
        try:
            profile = self._match_agent_profile(issue)
            if self._profile_is_acp(profile):
                if self._acp_profile_is_subscription(profile):
                    return True
                # per-token ACP — falls through to budget gate.
                return False
            # Safety-critical ACP-routing parity with _dispatch.
            # Mirrors the conditions there so the budget gate's view
            # of "would this dispatch via ACP?" matches what
            # _dispatch will actually choose. We don't have the
            # attempt / override_profile here — the budget gate runs
            # for first dispatches and doesn't see retries (those
            # take override_profile and are handled elsewhere) — so
            # treating the candidate as a first dispatch is correct.
            if (
                not self._has_explicit_handoff_label(issue)
                and issue.issue_type != "epic"
                and self._is_safety_critical_issue(issue)
            ):
                acp_profile = self._find_acp_profile()
                if (
                    acp_profile is not None
                    and self._acp_profile_is_subscription(acp_profile)
                ):
                    return True
            return False
        except Exception:
            return False

    def _acp_profile_is_subscription(self, profile: AgentProfile | None) -> bool:
        """True iff *profile* is mode=acp AND the resolved provider is
        subscription-billed (``billing_model == "subscription"``).

        Conservative default: any failure to resolve the provider, or a
        provider with no explicit billing_model, falls through to True
        (subscription) — that's the legacy behaviour predating this
        bead (oompah-zlz_2-ag7h) and matches the back-compat default
        applied by ``ModelProvider.from_dict`` for records that lack
        the field.

        Used by ``_would_dispatch_via_acp`` and ``_would_dispatch_on_free_model``
        to decide whether to bypass the budget gate.
        """
        if not self._profile_is_acp(profile):
            return False
        try:
            provider = self._resolve_provider(profile)
        except Exception:
            return True
        if provider is None:
            # No provider configured (CLI-only / legacy deployments running
            # ACP without a provider record) → subscription is the only
            # sensible default; there's nothing to meter against.
            return True
        return not provider.is_per_token_billed("acp")

    def _would_dispatch_on_free_model(self, issue: Issue) -> str | bool:
        """True (and returns the model name) when the model that WOULD be used
        for this dispatch has an explicit $0/$0 entry in its provider's
        model_costs. Used by the budget gate to decide whether to bypass the
        over-budget cap.

        Returns the model name (truthy) when the would-be dispatch is
        free-tier, or False on any resolution failure or when the model has
        any cost. The conservative default (False) means unknown-cost models
        are treated as paid so a misconfigured provider doesn't silently
        bypass the budget cap.

        Mirrors the profile resolution logic in _dispatch(), including the
        default_first_dispatch path, so the budget bypass uses exactly the
        same model selection path that dispatch would.
        """
        try:
            # Replicate profile resolution from _dispatch():
            # Use the default catch-all profile on the first dispatch when
            # default_first_dispatch is enabled; otherwise use the natural match.
            profile: AgentProfile | None
            is_first = (issue.id not in self.state.running and
                        issue.id not in self.state.retry_attempts)
            if (
                self.config.default_first_dispatch
                and is_first
                and not self._has_explicit_handoff_label(issue)
                and issue.issue_type != "epic"
                and not self._is_safety_critical_issue(issue)
            ):
                default_profile = self._get_default_catch_all_profile()
                if default_profile is not None:
                    profile = default_profile
                else:
                    profile = self._match_agent_profile(issue)
            else:
                profile = self._match_agent_profile(issue)

            if not profile:
                return False
            provider = self._resolve_provider(profile)
            if not provider:
                return False
            model = self._resolve_model(profile, provider)
            if not model:
                return False
            if provider.is_model_explicitly_free(model):
                return model  # truthy and carries the model name for logging
            return False
        except Exception as exc:
            # Don't let the dispatch path crash on a budget-introspection bug.
            logger.debug("free-model resolution failed for %s: %s", issue.identifier, exc)
            return False

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
        """Fetch open reviews for projects with stale or missing webhooks.

        Returns a dict of project_id -> list[ReviewRequest], cached for the
        entire tick so list_open_reviews is called at most once per project.

        Projects with recent webhook deliveries (within 2.5 minutes) are
        skipped — webhooks serve as the primary signal for those repos.
        Stale-projects are polled to catch anything webhooks may have missed.
        """
        projects = self.project_store.list_all()
        if not projects:
            return {}

        def _fetch_for_project(project) -> tuple[str, list]:
            # Skip polling for webhook-healthy projects
            if self.is_webhook_healthy(project.id):
                return (project.id, [])
            provider = detect_provider(project.repo_url, access_token=project.access_token)
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
        """Fetch merged PR/MR branch names across projects with stale webhooks.

        Projects with recent webhook deliveries (within 2.5 minutes) are
        skipped — webhooks serve as the primary signal.
        """
        projects = self.project_store.list_all()
        if not projects:
            return set()

        def _fetch_for_project(project) -> set[str]:
            # Skip polling for webhook-healthy projects
            if self.is_webhook_healthy(project.id):
                return set()
            provider = detect_provider(project.repo_url, access_token=project.access_token)
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
            provider = detect_provider(project.repo_url, access_token=project.access_token)
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
        """Create a review (PR/MR) if the agent pushed a branch but none exists.

        Honors the project's ``epic_strategy``:

        * ``flat`` (default) — branch is the bead identifier; PR targets main.
        * ``stacked`` — for a child of an epic, the PR's *base* is the
          epic's branch (``epic-<epic_identifier>``) instead of main, so
          all children stack on the epic and the operator gets one
          combined epic→main PR at the end.
        * ``shared`` — children commit directly to the shared epic branch.
          NO per-child PR is created here (the epic→main PR is the only
          one). Top-level beads in shared mode behave like flat.
        """
        if not project_id:
            return
        project = self.project_store.get(project_id)
        if not project or not project.repo_url:
            return
        provider = detect_provider(project.repo_url, access_token=project.access_token)
        if not provider:
            return
        slug = extract_repo_slug(project.repo_url)

        strategy = self._project_epic_strategy(project_id)
        # Resolve parent epic only for issues that have one. For top-level
        # beads (no parent_id), strategy/parent treatment doesn't matter.
        parent_epic: Issue | None = None
        if entry.issue and entry.issue.parent_id and strategy in ("stacked", "shared"):
            parent_epic = self._resolve_parent_epic(entry.issue)

        # Shared mode: child commits live on the shared epic branch and
        # the only PR is the epic→main PR. Skip per-child review creation.
        if strategy == "shared" and parent_epic is not None:
            logger.debug(
                "Skip per-child review for %s: epic_strategy=shared "
                "(child shares branch with epic %s)",
                entry.identifier, parent_epic.identifier,
            )
            return

        branch = entry.identifier  # branch is named after the issue
        # Stacked mode: the child PR targets the epic branch instead of main.
        target_branch = project.branch
        if strategy == "stacked" and parent_epic is not None:
            target_branch = self.project_store.epic_branch_name(
                parent_epic.identifier,
            )

        # Check if a review already exists for this branch
        reviews = getattr(self, "_reviews_cache", {}).get(project_id, [])
        for r in reviews:
            if r.source_branch == branch:
                return  # review already exists
        # Create the review
        try:
            title = f"{entry.identifier}: {entry.issue.title}" if entry.issue else entry.identifier
            result = provider.create_review(
                slug, title, branch, target_branch=target_branch,
            )
            if result:
                logger.info(
                    "Auto-created review for %s on %s (review #%s, base=%s)",
                    entry.identifier, project.name, result.id, target_branch,
                )
            else:
                logger.warning(
                    "Failed to create review for %s on %s (base=%s)",
                    entry.identifier, project.name, target_branch,
                )
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

        **Serialization** (oompah-zlz_2-grw, sibling of -8b9):

        - Direct-merge mode (merge_queue_enabled=False): a SUCCESSFUL
          merge breaks the loop — each merge changes the target branch
          and subsequent PRs would need rebasing first.
        - Direct-merge mode FAILURE: continue to next PR (target branch
          did NOT change, no race to serialize, breaking would starve
          later conflict-path / ci-failed dispatches).
        - Merge-queue mode (merge_queue_enabled=True): NEITHER success
          nor failure breaks the loop. GitHub's merge queue handles
          ordering for successful enqueues; a failed enqueue means
          GitHub rejected the request (config error or "PR already
          mergeable") so there's nothing to serialize.

        Conflict-path (has_conflicts) and ci-failed (retry_ci) dispatches
        are NOT serialized — they're pure idempotent tracker writes and
        all matching PRs in iteration order get acted on in a single tick.
        Serializing them caused starvation of older PRs when GitHub
        returned PRs in created_at DESC order (oompah-zlz_2-8b9).

        **Watchdog (oompah-zlz_2-jg4)**: every action attempt (success
        or failure) is recorded in ``self._yolo_action_history`` so the
        watchdog detectors can identify recurring no-progress patterns
        and file P0 escalation beads. Per-project loop-coverage stats
        are recorded in ``self._yolo_coverage_history`` for D2.
        """
        reviews_cache = getattr(self, "_reviews_cache", {})
        # Bump the tick counter once per call — detectors use it to
        # determine "consecutive ticks" semantics.
        self._yolo_tick_counter += 1
        tick = self._yolo_tick_counter

        for project in self.project_store.list_all():
            if not project.yolo:
                continue
            provider = detect_provider(project.repo_url, access_token=project.access_token)
            if not provider:
                continue
            slug = extract_repo_slug(project.repo_url)
            reviews = reviews_cache.get(project.id, [])

            # Loop-coverage tracking for D2.
            considered = 0
            actions_fired = 0
            considered_ids: set[str] = set()
            non_draft_total = sum(1 for r in reviews if not r.draft)

            for review in reviews:
                if review.draft:
                    continue
                considered += 1
                considered_ids.add(str(review.id))
                review_id = review.id

                # Conflict check FIRST — before the auto_merge_enabled
                # idempotency guard. A PR enqueued for auto-merge can
                # go DIRTY when another PR lands with overlapping files,
                # and the queue then sits forever waiting for manual
                # conflict resolution. We must dispatch a conflict agent
                # in that case even though auto_merge is "enabled" —
                # GitHub will never make progress on a DIRTY queued PR.
                # (oompah-zlz_2-l81)
                if review.has_conflicts:
                    logger.info("YOLO: conflicts on %s review #%s — dispatching conflict agent",
                                project.name, review_id)
                    self._yolo_notify_conflict(project, provider, slug, review_id)
                    self._record_yolo_action(
                        project.id, str(review_id), "notify_conflict",
                        "success", "", tick=tick,
                    )
                    actions_fired += 1
                    continue

                # CI-failure check BEFORE the auto_merge_enabled
                # idempotency guard. `auto_merge_enabled=True` means
                # GitHub will merge the PR "when it's ready" — it stays
                # True even when CI is currently failing. GitHub will
                # never make the PR ready on its own in that case, and
                # a failing PR with auto_merge requested is exactly the
                # scenario that needs a ci-fix agent. Without this
                # ordering, btf.1's idempotency skip silently swallows
                # all ci_status=='failed' dispatches for the
                # auto_merge_enabled subset. (oompah-zlz_2-wjz)
                if review.ci_status == "failed":
                    logger.info("YOLO: auto-retrying failed CI on %s MR #%s",
                                project.name, review_id)
                    self._yolo_retry_ci(project, review)
                    self._record_yolo_action(
                        project.id, str(review_id), "retry_ci",
                        "success", "", tick=tick,
                    )
                    actions_fired += 1
                    # ci-fix relabel is an idempotent tracker write — no
                    # reason to serialize across PRs in this tick.
                    # Using `break` here starves conflict-path and
                    # additional ci-failed dispatches for older PRs that
                    # come LATER in iteration order (GitHub returns PRs
                    # in created_at DESC order). (oompah-zlz_2-8b9)
                    continue

                # Idempotency guard: if GitHub auto-merge is already
                # enabled on this PR AND CI is not failing, the merge
                # queue is handling it. Don't re-dispatch the GraphQL
                # mutation every tick — at best it's a no-op API call,
                # at worst a future API version could double-enqueue or
                # revoke the existing auto-merge. (oompah-zlz_2-btf.1,
                # scope refined by oompah-zlz_2-wjz)
                if getattr(review, "auto_merge_enabled", False):
                    logger.debug(
                        "YOLO: %s MR #%s already enqueued (auto_merge_enabled=true) — skipping",
                        project.name, review_id,
                    )
                    # Treat "already enqueued" as a successful enqueue
                    # outcome for watchdog purposes — clears any prior
                    # consecutive-failure run and prevents D1 from
                    # firing on PRs GitHub is already handling.
                    self._record_yolo_action(
                        project.id, str(review_id), "enqueue",
                        "success", "", tick=tick,
                    )
                    continue

                # Merge (or enqueue) if CI passed or if there's no CI pipeline (empty status)
                ci_ok = review.ci_status in ("passed", "", None)
                if ci_ok and not review.needs_rebase:
                    merge_queue = getattr(project, "merge_queue_enabled", False)
                    # D4 strategy switch: if this PR has hit
                    # "PR already mergeable" enough times, skip the
                    # auto-merge attempt and try direct merge instead.
                    # (oompah-zlz_2-jg4)
                    switch_key = (project.id, str(review_id))
                    use_direct_merge_fallback = (
                        merge_queue and switch_key in self._yolo_already_mergeable_switched
                    )
                    if merge_queue and not use_direct_merge_fallback:
                        logger.info("YOLO: enqueued for merge %s MR #%s (ci=%s)",
                                    project.name, review_id, review.ci_status)
                        success, msg = provider.enable_auto_merge(slug, review_id)
                        if success:
                            logger.info("YOLO: enqueued %s MR #%s", project.name, review_id)
                            self._clear_repo_config_error(project.id, str(review_id))
                            self._record_yolo_action(
                                project.id, str(review_id), "enqueue",
                                "success", "", tick=tick,
                            )
                            self._clear_already_mergeable_switch(project.id, str(review_id))
                            actions_fired += 1
                            # Merge-queue mode: GitHub's queue handles
                            # serialization, so a successful enqueue does
                            # NOT need to break. Continue iterating to
                            # enqueue any further qualified PRs in the
                            # same tick. (oompah-zlz_2-grw, fix B)
                            continue
                        else:
                            self._record_yolo_action(
                                project.id, str(review_id), "enqueue",
                                "failure", msg or "", tick=tick,
                            )
                            # D4: check whether to switch strategy now.
                            self._maybe_switch_to_direct_merge(
                                project.id, str(review_id),
                            )
                            self._handle_yolo_merge_failure(
                                project, provider, slug, review_id, msg,
                                operation="enqueue",
                            )
                            actions_fired += 1
                            # A FAILED enqueue must NOT break either —
                            # there's no race to serialize and breaking
                            # starves later conflict-path / ci-failed
                            # dispatches for older PRs in the iteration
                            # (GitHub returns PRs in created_at DESC).
                            # (oompah-zlz_2-grw, fix A — sibling of
                            # oompah-zlz_2-8b9)
                            continue
                    elif use_direct_merge_fallback:
                        logger.info(
                            "YOLO: direct merge fallback (already-mergeable loop) on %s MR #%s",
                            project.name, review_id,
                        )
                        success, msg = provider.merge_review(slug, review_id)
                        if success:
                            logger.info(
                                "YOLO: direct-merge fallback succeeded for %s MR #%s",
                                project.name, review_id,
                            )
                            self._clear_repo_config_error(project.id, str(review_id))
                            self._record_yolo_action(
                                project.id, str(review_id),
                                "merge_after_already_mergeable",
                                "success", "", tick=tick,
                            )
                            self._clear_already_mergeable_switch(project.id, str(review_id))
                            actions_fired += 1
                            # Direct merge (fallback path): each merge
                            # changes the target branch, so subsequent
                            # PRs would need a rebase before they can
                            # merge cleanly. Serialize: one merge per
                            # project per tick. (oompah-zlz_2-grw)
                            break
                        else:
                            self._record_yolo_action(
                                project.id, str(review_id),
                                "merge_after_already_mergeable",
                                "failure", msg or "", tick=tick,
                            )
                            self._handle_yolo_merge_failure(
                                project, provider, slug, review_id, msg,
                                operation="merge",
                            )
                            actions_fired += 1
                            # FAILED direct merge: target branch did
                            # NOT change, so there's no race. Continue
                            # to the next PR rather than starve later
                            # conflict-path / ci-failed dispatches.
                            # (oompah-zlz_2-grw, fix A)
                            continue
                    else:
                        logger.info("YOLO: auto-merging %s MR #%s (ci=%s)",
                                    project.name, review_id, review.ci_status)
                        success, msg = provider.merge_review(slug, review_id)
                        if success:
                            logger.info("YOLO: merged %s MR #%s", project.name, review_id)
                            self._clear_repo_config_error(project.id, str(review_id))
                            self._record_yolo_action(
                                project.id, str(review_id), "merge",
                                "success", "", tick=tick,
                            )
                            actions_fired += 1
                            # Direct-merge mode: each merge changes the
                            # target branch, so subsequent PRs would
                            # need a rebase before they can merge
                            # cleanly. Serialize: one merge per
                            # project per tick. (oompah-zlz_2-grw)
                            break
                        else:
                            self._record_yolo_action(
                                project.id, str(review_id), "merge",
                                "failure", msg or "", tick=tick,
                            )
                            self._handle_yolo_merge_failure(
                                project, provider, slug, review_id, msg,
                                operation="merge",
                            )
                            actions_fired += 1
                            # FAILED direct merge: target branch did
                            # NOT change, so there's no race. Continue
                            # to the next PR rather than starve later
                            # conflict-path / ci-failed dispatches.
                            # (oompah-zlz_2-grw, fix A)
                            continue

                # MR doesn't match any action condition (e.g. CI running/pending)
                logger.debug("YOLO: skipping %s MR #%s branch=%s (ci=%s, conflicts=%s, needs_rebase=%s)",
                             project.name, review_id, review.source_branch,
                             review.ci_status, review.has_conflicts, review.needs_rebase)

            # Per-project end-of-loop instrumentation (D2).
            missing_ids = sorted({
                str(r.id) for r in reviews
                if not r.draft and str(r.id) not in considered_ids
            })
            logger.info(
                "YOLO iteration: project=%s considered=%d/%d actions=%d",
                project.name, considered, non_draft_total, actions_fired,
            )
            self._yolo_coverage_history.append(CoverageRecord(
                tick=tick,
                project_id=project.id,
                considered=considered,
                total=non_draft_total,
                actions=actions_fired,
                missing_review_ids=missing_ids,
            ))

        # End-of-tick cleanup: drop tracked repo-config errors for any
        # PR that has disappeared from the per-tick reviews cache (PR
        # was merged, closed, or otherwise resolved).
        self._prune_stale_repo_config_errors(reviews_cache)
        # Watchdog: clear cached watchdog-bead refs for PRs that are no
        # longer in the cache (PR closed/merged) so future recurrences
        # can re-file. Then run all detectors and file beads / log
        # warnings as appropriate.
        self._prune_stale_watchdog_state(reviews_cache)
        self._run_yolo_watchdog(reviews_cache)

    def _handle_yolo_merge_failure(
        self, project, provider, slug: str, review_id, msg: str,
        *, operation: str,
    ) -> None:
        """Classify and handle a failed YOLO enqueue/merge call.

        oompah-zlz_2-btf.2: route operator-action errors (repo config)
        away from the conflict-resolution path so we don't dispatch
        doomed agents for problems no agent can fix.
        """
        review_id_str = str(review_id)
        kind = _classify_yolo_merge_error(msg or "")

        if kind == "config":
            fingerprint = _yolo_error_fingerprint(project.id, msg or "")
            # Track this PR as needing operator action — surfaces in
            # reviews_summary and the /api/v1/reviews payload.
            self._yolo_repo_config_errors[(project.id, review_id_str)] = {
                "msg": msg or "",
                "fingerprint": fingerprint,
                "operation": operation,
            }
            # Deduplicated ERROR log: one line per (project, error)
            # pair, not per tick per PR.
            if fingerprint not in self._logged_repo_config_fingerprints:
                self._logged_repo_config_fingerprints.add(fingerprint)
                logger.error(
                    "YOLO: %s blocked on %s MR #%s by repo configuration (operator must fix): %s "
                    "[fingerprint=%s] — NOT dispatching agent (no code change can resolve this)",
                    operation, project.name, review_id, msg, fingerprint,
                )
            else:
                logger.debug(
                    "YOLO: %s still blocked on %s MR #%s by repo config (fingerprint=%s) — suppressing log",
                    operation, project.name, review_id, fingerprint,
                )
            return

        # Anything else: clear any stale repo-config record for this PR
        # (the operator may have just fixed the toggle, and the next
        # error is a real conflict / transient issue).
        self._clear_repo_config_error(project.id, review_id_str)

        if kind == "conflict":
            logger.warning(
                "YOLO: %s failed for %s MR #%s: %s — dispatching conflict agent",
                operation, project.name, review_id, msg,
            )
            self._yolo_notify_conflict(project, provider, slug, review_id)
            return

        # Transient: log a warning and let the next tick retry.
        # No agent dispatch — that would be wasteful for rate-limit /
        # network blips that resolve themselves.
        logger.warning(
            "YOLO: %s failed for %s MR #%s (transient): %s — will retry next tick",
            operation, project.name, review_id, msg,
        )

    def _clear_repo_config_error(self, project_id: str, review_id: str) -> None:
        """Drop any tracked repo-config error for (project, review).

        Called on successful enqueue/merge or when the failure mode
        changes (config → conflict). The associated fingerprint is
        intentionally NOT removed from ``_logged_repo_config_fingerprints``
        — that set is purely a per-process log dedup; re-logging on a
        process restart is fine.
        """
        self._yolo_repo_config_errors.pop((project_id, review_id), None)

    def _prune_stale_repo_config_errors(self, reviews_cache: dict) -> None:
        """Drop tracked repo-config errors for PRs no longer in the cache.

        A review disappears from the cache when the PR is merged, closed,
        or otherwise removed by a webhook. Without this prune, the
        ``needs_repo_config`` count in ``_reviews_summary`` could stay
        elevated forever for a PR that's already been resolved.
        """
        live_keys: set[tuple[str, str]] = set()
        for project_id, reviews in reviews_cache.items():
            for r in reviews or []:
                live_keys.add((project_id, str(r.id)))
        stale = [k for k in self._yolo_repo_config_errors if k not in live_keys]
        for k in stale:
            self._yolo_repo_config_errors.pop(k, None)
        # Also prune orphan-recovery bead bookkeeping (oompah-zlz_2-975).
        # Key shape is (project_id, review_id, kind); strip the kind to
        # check liveness against (project_id, review_id) pairs.
        stale_orphan = [
            k for k in self._yolo_orphan_recovery_beads
            if (k[0], k[1]) not in live_keys
        ]
        for k in stale_orphan:
            self._yolo_orphan_recovery_beads.pop(k, None)

    # ------------------------------------------------------------------
    # YOLO watchdog (oompah-zlz_2-jg4)
    # ------------------------------------------------------------------

    def _record_yolo_action(
        self,
        project_id: str,
        review_id: str,
        action_type: str,
        outcome: str,
        error_msg: str,
        *,
        tick: int,
    ) -> None:
        """Append a YoloActionRecord to the action history.

        Called on every YOLO action attempt — success or failure.
        Successful attempts implicitly clear D1's consecutive-failure
        run for that (project, review, action) tuple.

        Also clears any cached watchdog-bead reference for this
        (project, review) on success: when a PR's situation resolves,
        future recurrences should be able to re-file.
        """
        record = YoloActionRecord(
            project_id=project_id,
            review_id=review_id,
            action_type=action_type,
            outcome=outcome,
            error_msg=error_msg,
            tick=tick,
            timestamp=time.time(),
        )
        self._yolo_action_history.append(record)
        if outcome == "success":
            self._clear_watchdog_filed_for_review(project_id, review_id)

    def _clear_watchdog_filed_for_review(self, project_id: str, review_id: str) -> None:
        """Drop watchdog-bead cache entries for one (project, review).

        Called when an action on the PR succeeds — the PR has made
        progress, so any prior watchdog beads were resolved (or will
        be) and a future recurrence should re-file freshly.
        """
        keys_to_drop = [
            k for k in self._yolo_watchdog_filed
            if k.startswith(f"d1:{project_id}:{review_id}:")
            or k == f"d4:{project_id}:{review_id}"
            or k.startswith(f"d3:{project_id}:{review_id}:")
        ]
        for k in keys_to_drop:
            self._yolo_watchdog_filed.pop(k, None)

    def _maybe_switch_to_direct_merge(self, project_id: str, review_id: str) -> None:
        """D4: switch strategy from auto-merge to direct merge.

        Called after an enqueue failure. If the consecutive
        "PR already mergeable" failure run for this PR has reached
        ``D4_ALREADY_MERGEABLE_THRESHOLD``, mark the PR for
        direct-merge fallback on subsequent ticks.
        """
        run = count_consecutive_already_mergeable(
            self._yolo_action_history, project_id, review_id,
            action_type="enqueue",
        )
        if run >= D4_ALREADY_MERGEABLE_THRESHOLD:
            key = (project_id, review_id)
            if key not in self._yolo_already_mergeable_switched:
                self._yolo_already_mergeable_switched.add(key)
                logger.warning(
                    "YOLO watchdog: switching to direct-merge fallback for "
                    "%s MR #%s after %d consecutive 'already mergeable' "
                    "failures",
                    project_id, review_id, run,
                )

    def _clear_already_mergeable_switch(self, project_id: str, review_id: str) -> None:
        """Clear D4 strategy-switch state on a successful action."""
        self._yolo_already_mergeable_switched.discard((project_id, review_id))

    def _prune_stale_watchdog_state(self, reviews_cache: dict) -> None:
        """Drop watchdog state for PRs that have left the cache.

        When a PR closes/merges and disappears from the cache:
        * Drop strategy-switch flags so future recurrences re-evaluate.
        * Drop filed-watchdog-bead refs so future recurrences re-file.
        * Drop the PR's action history entries so detectors don't keep
          re-firing on a closed PR's stale failure run.
        * Drop d2-warned project keys when a project no longer has
          starvation (handled in the warning emission).
        """
        live_pairs: set[tuple[str, str]] = set()
        for project_id, reviews in reviews_cache.items():
            for r in reviews or []:
                live_pairs.add((project_id, str(r.id)))

        stale_switches = [
            k for k in self._yolo_already_mergeable_switched
            if k not in live_pairs
        ]
        for k in stale_switches:
            self._yolo_already_mergeable_switched.discard(k)

        # Drop D1/D4 watchdog-bead refs for PRs no longer in cache.
        # D2 keys are project-scoped and stay until the warning clears
        # naturally on a coverage tick.
        stale_filed: list[str] = []
        for key in self._yolo_watchdog_filed:
            if key.startswith("d2:"):
                continue
            # key format: "<detector>:<project_id>:<review_id>[:rest]"
            parts = key.split(":", 3)
            if len(parts) < 3:
                continue
            project_id, review_id = parts[1], parts[2]
            if (project_id, review_id) not in live_pairs:
                stale_filed.append(key)
        for k in stale_filed:
            self._yolo_watchdog_filed.pop(k, None)

        # Drop action-history entries for PRs no longer in cache so
        # detectors don't keep firing on a closed PR's stale run. The
        # deque maxlen will eventually evict them, but explicit pruning
        # here keeps the watchdog tight.
        if self._yolo_action_history:
            kept = [
                r for r in self._yolo_action_history
                if (r.project_id, r.review_id) in live_pairs
            ]
            if len(kept) != len(self._yolo_action_history):
                self._yolo_action_history.clear()
                self._yolo_action_history.extend(kept)

    def _build_incoherent_prs_for_d3(self, reviews_cache: dict) -> list[dict]:
        """Build the D3 incoherent-PR list for the watchdog.

        For each PR in the cache:
        * If has_conflicts=True or ci_status=='failed', verify a matching
          recovery bead exists. If we previously filed an orphan-
          recovery bead AND that bead is now closed AND the PR still
          shows the failing condition, the bead-PR pair is incoherent.
          Reset the orphan-recovery cache entry (so the next tick
          re-files) and record an entry for the watchdog to escalate.
        """
        incoherent: list[dict] = []
        for project in self.project_store.list_all():
            reviews = reviews_cache.get(project.id, [])
            try:
                tracker = self._tracker_for_project(project.id)
            except Exception:  # noqa: BLE001 — best-effort coherence check
                continue
            for review in reviews:
                if review.draft:
                    continue
                review_id = str(review.id)
                source_branch = review.source_branch or ""
                if review.has_conflicts:
                    kind = "merge-conflict"
                elif review.ci_status == "failed":
                    kind = "ci-fix"
                else:
                    continue
                key = (project.id, review_id, kind)
                bead_id = self._yolo_orphan_recovery_beads.get(key)
                if not bead_id:
                    # We haven't filed an orphan-recovery bead — the
                    # standard YOLO path is responsible for handling
                    # this PR. D3 only fires when a recovery bead WAS
                    # filed but is now closed without resolving.
                    continue
                # Check: is the orphan-recovery bead still open?
                try:
                    issue = tracker.fetch_issue_detail(bead_id)
                except Exception:  # noqa: BLE001
                    continue
                if not issue:
                    # Bead disappeared entirely — reset the cache.
                    self._yolo_orphan_recovery_beads.pop(key, None)
                    incoherent.append({
                        "project_id": project.id,
                        "review_id": review_id,
                        "kind": kind,
                        "source_branch": source_branch,
                        "reason": (
                            f"recovery bead {bead_id} no longer exists; "
                            "PR still in failing state"
                        ),
                    })
                    continue
                state_lower = issue.state.strip().lower()
                terminal = {s.lower() for s in self.config.tracker_terminal_states}
                if state_lower in terminal:
                    # Bead closed but PR still failing — reset cache so
                    # the next tick refiles a fresh recovery bead.
                    self._yolo_orphan_recovery_beads.pop(key, None)
                    incoherent.append({
                        "project_id": project.id,
                        "review_id": review_id,
                        "kind": kind,
                        "source_branch": source_branch,
                        "reason": (
                            f"recovery bead {bead_id} is closed (state={issue.state}) "
                            f"but PR still has {kind} condition"
                        ),
                    })
        return incoherent

    def _run_yolo_watchdog(self, reviews_cache: dict) -> None:
        """Run all detectors and file beads / log warnings."""
        # Build helper lookup of project_id → name for nicer titles.
        project_lookup = {}
        try:
            for p in self.project_store.list_all():
                project_lookup[p.id] = p.name
        except Exception:  # noqa: BLE001 — fallback to ids
            pass

        incoherent = self._build_incoherent_prs_for_d3(reviews_cache)

        patterns = run_all_detectors(
            history=list(self._yolo_action_history),
            coverage_history=list(self._yolo_coverage_history),
            incoherent_prs=incoherent,
            project_lookup=project_lookup,
        )

        # Track which projects had a D2 hit this tick — used to clear
        # the d2-warned flag on projects that recovered.
        d2_hit_projects: set[str] = set()

        for pattern in patterns:
            if pattern.severity == "warning":
                if pattern.detector == "d2":
                    d2_hit_projects.add(pattern.project_id)
                    if pattern.pattern_key not in self._yolo_watchdog_d2_warned:
                        self._yolo_watchdog_d2_warned.add(pattern.pattern_key)
                        logger.warning(
                            "YOLO watchdog D2: %s\n%s",
                            pattern.title, pattern.body,
                        )
                continue

            # P0 bead-filing patterns (D1, D3, D4).
            if pattern.pattern_key in self._yolo_watchdog_filed:
                # Already filed for this pattern. Idempotent skip.
                continue
            try:
                self._file_watchdog_bead(pattern)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "YOLO watchdog: failed to file bead for %s: %s",
                    pattern.pattern_key, exc,
                )

        # Clear D2-warned flags for projects that didn't hit this tick —
        # i.e. the starvation has resolved. A future recurrence will re-warn.
        d2_keys_to_drop = [
            k for k in self._yolo_watchdog_d2_warned
            if k.startswith("d2:") and k not in {f"d2:{p}" for p in d2_hit_projects}
        ]
        for k in d2_keys_to_drop:
            self._yolo_watchdog_d2_warned.discard(k)

    def _file_watchdog_bead(self, pattern: WatchdogPattern) -> None:
        """File a P0 bead for a watchdog pattern and stamp the idempotency cache."""
        try:
            tracker = self._tracker_for_project(pattern.project_id)
        except ProjectError as exc:
            logger.warning(
                "YOLO watchdog: cannot get tracker for %s: %s",
                pattern.project_id, exc,
            )
            return
        labels = list(pattern.labels)
        new_issue = tracker.create_issue(
            title=pattern.title,
            issue_type="task",
            description=pattern.body,
            priority=0,
            labels=labels,
            initial_status="open",
        )
        self._yolo_watchdog_filed[pattern.pattern_key] = new_issue.identifier
        # Log at WARNING (not ERROR): filing a P0 escalation bead is the
        # watchdog's *expected* notification path for stuck PRs — it's
        # not an oompah-internal failure. Logging at ERROR would cause
        # error_watcher's _BeadLoggingHandler to auto-file a duplicate
        # meta-bead in the oompah project, dirtying the queue with
        # notifications that already have their own bead in the target
        # project (oompah-zlz_2-8vc).
        logger.warning(
            "YOLO watchdog: filed P0 bead %s for pattern %s "
            "(project=%s review=%s detector=%s)",
            new_issue.identifier, pattern.pattern_key,
            pattern.project_id, pattern.review_id, pattern.detector,
        )

    def _file_orphan_recovery_bead(
        self,
        project,
        tracker,
        review_id: str,
        source_branch: str,
        kind: str,
    ) -> None:
        """File a recovery bead for a PR whose branch matches no bead.

        Used by ``_yolo_notify_conflict`` and ``_yolo_retry_ci`` when
        ``fetch_issue_detail(source_branch)`` returns ``None``. Without
        this, an orphan PR (branch with no attaching bead) would sit
        DIRTY/FAILED forever because the YOLO escalation has nothing to
        relabel/reopen. The bead's identifier won't match the branch —
        that's fine: it's the work item, not the branch source. The
        focus matcher routes via the label.

        ``kind`` is one of ``"merge-conflict"`` or ``"ci-fix"`` and
        controls the title/description/label. Idempotent: the
        ``(project_id, review_id, kind)`` tuple is tracked in
        ``self._yolo_orphan_recovery_beads`` so a second YOLO fire on
        the same orphan PR will not file a duplicate.
        (oompah-zlz_2-975)
        """
        if kind not in ("merge-conflict", "ci-fix"):
            logger.error("Unknown orphan recovery bead kind: %s", kind)
            return
        key = (project.id, str(review_id), kind)
        if key in self._yolo_orphan_recovery_beads:
            logger.debug(
                "YOLO: orphan recovery bead already filed for %s MR #%s (%s): %s",
                project.name, review_id, kind,
                self._yolo_orphan_recovery_beads[key],
            )
            return
        if kind == "merge-conflict":
            title = f"merge conflict on PR #{review_id} ({source_branch})"
            description = (
                f"YOLO: conflict detected on MR #{review_id} "
                f"(branch {source_branch}) but no bead matches the "
                f"branch name. This bead is the manual recovery — "
                f"work directly on the branch. Rebase the branch onto "
                f"the target and resolve conflicts."
            )
            label = "merge-conflict"
        else:  # ci-fix
            title = f"fix CI on PR #{review_id} ({source_branch})"
            description = (
                f"YOLO: CI failure detected on MR #{review_id} "
                f"(branch {source_branch}) but no bead matches the "
                f"branch name. This bead is the manual recovery — "
                f"work directly on the branch. Fix the failing tests "
                f"so this MR can merge. Do NOT rewrite the feature — "
                f"only fix test failures. IMPORTANT: Paths in CI logs "
                f"are not trustworthy. Run tests locally to get "
                f"accurate paths and errors."
            )
            label = "ci-fix"
        try:
            new_issue = tracker.create_issue(
                title=title,
                issue_type="task",
                description=description,
                priority=0,
                initial_status="open",
            )
        except Exception as exc:
            logger.warning(
                "YOLO: failed to file orphan recovery bead for %s MR #%s (%s): %s",
                project.name, review_id, kind, exc,
            )
            return
        try:
            tracker.add_label(new_issue.identifier, label)
        except Exception as exc:
            logger.warning(
                "YOLO: filed orphan recovery bead %s but failed to add %s label: %s",
                new_issue.identifier, label, exc,
            )
        self._yolo_orphan_recovery_beads[key] = new_issue.identifier
        logger.info(
            "YOLO: filed orphan recovery bead %s for %s MR #%s (%s, branch %s)",
            new_issue.identifier, project.name, review_id, kind, source_branch,
        )

    def _yolo_notify_conflict(self, project, provider, slug: str, review_id: str) -> None:
        """Notify the bead about a merge conflict (YOLO mode).

        Before falling through to the bead-notification path, attempt a
        provider-level rebase. GitHub frequently marks a PR ``mergeable=CONFLICTING``
        when the branch is merely out-of-date — the underlying patches don't
        actually overlap. In that case ``provider.rebase_review`` succeeds and
        clears ``has_conflicts`` on the next review fetch, so no agent work is
        needed. Only when the rebase truly fails with conflict markers (or for
        unrelated transport/auth reasons) do we fall through to today's
        notify-bead behavior. See oompah-zlz_2-s56w.
        """
        # Step 1: try a provider-level rebase before disturbing the bead.
        try:
            success, message = provider.rebase_review(slug, review_id)
            if success:
                logger.info(
                    "YOLO: rebased %s MR #%s clean (no conflict)",
                    slug, review_id,
                )
                return
            msg_lower = (message or "").lower()
            if "conflict" not in msg_lower:
                # Network/auth/etc — preserve today's safety net by
                # falling through to notify the bead, but log so an
                # operator can see why YOLO didn't get the cheap path.
                logger.warning(
                    "YOLO: provider rebase failed for %s MR #%s (non-conflict): %s",
                    slug, review_id, message,
                )
            # else: real merge conflict — fall through to bead-notify below.
        except Exception as exc:
            logger.warning(
                "YOLO: provider rebase raised for %s MR #%s: %s",
                slug, review_id, exc,
            )
            # Fall through to bead-notify (safety net).

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
                # Orphan branch: no bead matches. File a recovery bead so
                # the YOLO escalation chain isn't a silent dead-end.
                # (oompah-zlz_2-975)
                self._file_orphan_recovery_bead(
                    project, tracker, str(review_id), source_branch,
                    kind="merge-conflict",
                )
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
            terminal = {s.lower() for s in self.config.tracker_terminal_states}
            if state_lower in terminal:
                tracker.update_issue(
                    issue.identifier,
                    status="open", priority="0",
                    **{"add-label": "merge-conflict"},
                )
                self.state.completed.discard(issue.id)
                logger.info("YOLO: reopened %s as P0 for conflict resolution", issue.identifier)
            else:
                try:
                    tracker.update_issue(issue.identifier, **{"add-label": "merge-conflict"})
                except Exception:
                    pass
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
                # Orphan branch: no bead matches. File a recovery bead so
                # the YOLO escalation chain isn't a silent dead-end.
                # (oompah-zlz_2-975)
                self._file_orphan_recovery_bead(
                    project, tracker, str(review.id), source_branch,
                    kind="ci-fix",
                )
                return
            # If the matched bead has children, the dispatcher will never
            # dispatch the bead itself — children-with-unmerged-reviews
            # block the parent via the standard blocker chain, and
            # epic-planner won't re-plan an already-planned bead. This
            # is independent of issue_type: a type=feature bead with
            # children behaves identically to a type=epic bead from the
            # dispatcher's perspective. Relabeling such a bead ci-fix
            # would silently strand the work forever — that's the live
            # bug behind oompah-zlz_2-gf9 (trickle-rl5 is type=feature
            # with 7 children, created via epic_planner but stamped as
            # feature). File a sibling task bead under the parent
            # instead so an agent actually gets dispatched against the
            # CI failure. See oompah-zlz_2-p4y, oompah-zlz_2-cd5
            # (idempotency-via-sibling-presence), and oompah-zlz_2-gf9
            # (behavioral has-children gate, not issue_type).
            #
            # IMPORTANT: this check runs BEFORE the
            # already-labeled-ci-fix early-exit below. Without that
            # ordering, a parent-with-children that was relabeled ci-fix
            # in a previous YOLO cycle (legacy state, or operator
            # action) would short-circuit forever and never produce a
            # sibling bead — which is exactly the bug
            # oompah-zlz_2-cd5 fixes.
            children = self._fetch_epic_children(issue)
            if children:
                # Idempotency: if there's already an OPEN/IN_PROGRESS
                # ci-fix sibling under this parent, a fix is already in
                # flight — don't file a duplicate. CLOSED siblings
                # from previous attempts don't count (treat as
                # finished and file a new one).
                existing_sibling = next(
                    (
                        c for c in children
                        if c.state.strip().lower() in ("open", "in_progress")
                        and "ci-fix" in (c.labels or [])
                    ),
                    None,
                )
                if existing_sibling is not None:
                    logger.debug(
                        "YOLO: ci-fix sibling %s already open under "
                        "%s — skipping duplicate",
                        existing_sibling.identifier, issue.identifier,
                    )
                    return
                # Third idempotency signal: if the parent epic is already
                # labeled ci-fix (e.g., a human operator or是一场 legacy
                # YOLO cycle marked it before this fix shipped), treat it as
                # "a fix was already tried" — don't stack a second sibling
                # on top of an unacted-on label.
                if "ci-fix" in issue.labels:
                    logger.debug(
                        "YOLO: parent %s already labeled ci-fix "
                        "(prior attempt) — skipping sibling",
                        issue.identifier,
                    )
                    return
                sibling_title = (
                    f"CI fix: PR #{review.id} on branch {source_branch}"
                )
                sibling_description = (
                    f"YOLO: CI tests failed on MR #{review.id} "
                    f"(branch {source_branch}). The branch's primary "
                    f"bead {issue.identifier} (type={issue.issue_type}) "
                    f"has {len(children)} children and won't be "
                    f"dispatched. This sibling bead carries the actual "
                    f"fix work.\n\n"
                    "Fix the failing tests so this MR can merge. "
                    "Do NOT rewrite the feature — only fix test failures. "
                    "IMPORTANT: Paths in CI logs are not trustworthy. "
                    "Run tests locally to get accurate paths and errors."
                )
                sibling = tracker.create_issue(
                    title=sibling_title,
                    issue_type="task",
                    description=sibling_description,
                    priority=0,
                    labels=["ci-fix"],
                    parent=issue.identifier,
                    initial_status="open",
                )
                logger.info(
                    "YOLO: filed sibling ci-fix bead %s under %s "
                    "(type=%s, %d children) for MR #%s",
                    sibling.identifier, issue.identifier,
                    issue.issue_type, len(children), review.id,
                )
                return
            # Childless bead path (any issue_type): keep the existing
            # relabel-or-skip behavior. The early-exit below is the
            # original idempotency guard — for beads with no children,
            # a ci-fix label genuinely means "a fix is already in
            # flight" because the bead itself can be dispatched.
            state_lower = issue.state.strip().lower()
            if state_lower in ("open", "in_progress") and "ci-fix" in issue.labels:
                return
            # If the matched bead is an epic with children, the dispatcher will
            # never dispatch it (epics-with-children are gated out of both
            # regular dispatch and epic-planner dispatch). Relabeling such an
            # epic as ci-fix would silently strand the work forever. File a
            # sibling task bead under the epic instead so an agent actually
            # gets dispatched against the CI failure. See oompah-zlz_2-p4y.
            if issue.issue_type == "epic":
                children = self._fetch_epic_children(issue)
                if children:
                    sibling_title = (
                        f"CI fix: PR #{review.id} on branch {source_branch}"
                    )
                    sibling_description = (
                        f"YOLO: CI tests failed on MR #{review.id} "
                        f"(branch {source_branch}). The branch's primary "
                        f"bead {issue.identifier} is an epic with "
                        f"{len(children)} children and won't be dispatched. "
                        "This sibling bead carries the actual fix work.\n\n"
                        "Fix the failing tests so this MR can merge. "
                        "Do NOT rewrite the feature — only fix test failures. "
                        "IMPORTANT: Paths in CI logs are not trustworthy. "
                        "Run tests locally to get accurate paths and errors."
                    )
                    sibling = tracker.create_issue(
                        title=sibling_title,
                        issue_type="task",
                        description=sibling_description,
                        priority=0,
                        labels=["ci-fix"],
                        parent=issue.identifier,
                        initial_status="open",
                    )
                    logger.info(
                        "YOLO: filed sibling ci-fix bead %s under epic %s "
                        "for MR #%s",
                        sibling.identifier, issue.identifier, review.id,
                    )
                    return
            tracker.update_issue(
                issue.identifier,
                status="open", priority="0",
                **{"add-label": "ci-fix"},
            )
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

    def _select_dispatchable(self, candidates: list[Issue]) -> list[Issue]:
        """Sort candidates and filter via _should_dispatch.

        Designed to be called via run_in_executor from _handle_dispatch_needed
        so the bd CLI calls inside _should_dispatch (label/blocker resolution
        at ~150ms each) run off the asyncio event loop, keeping uvicorn
        responsive during heavy ticks. See bead oompah-zlz_2-nvr.

        Returns the issues that pass _should_dispatch in priority/age order.
        The async caller is still responsible for re-checking _available_slots
        in its dispatch loop because slot count drops with each successful
        dispatch.
        """
        sorted_issues = self._sort_for_dispatch(candidates)
        return [issue for issue in sorted_issues if self._should_dispatch(issue)]

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

    def _next_profile_for_retry(self, entry: "RunningEntry") -> tuple[AgentProfile | None, str]:
        """Compute the next profile for a retry, respecting default_first_dispatch semantics.

        When ``default_first_dispatch`` is enabled and the issue was first
        dispatched on the default catch-all profile (i.e. ``entry.natural_profile_name``
        is set), the first retry jumps straight to the naturally-matched profile
        rather than escalating one step up from ``default``.

        Returns (profile, escalated_profile_name_or_empty):
        - profile: the AgentProfile to use for the retry (may be None if same)
        - escalated_profile_name: non-empty when a specific profile should be
          passed as ``override_profile`` to the next _dispatch call.
        """
        if self.config.default_first_dispatch and entry.natural_profile_name:
            # First retry after a default_first_dispatch run: jump to the
            # natural profile (what _match_agent_profile would have returned).
            natural = self._get_profile_by_name(entry.natural_profile_name)
            if natural:
                return natural, natural.name
            # Profile no longer exists — fall through to normal escalation

        # Normal escalation: walk up the hierarchy from current profile
        current_profile = self._get_profile_by_name(entry.agent_profile_name)
        escalated = self._escalate_profile(current_profile, entry.issue)
        return escalated, escalated.name if escalated else ""

    def _record_generated_attachments(self, workspace_path: str, issue: Issue) -> None:
        """Write agent-generated outputs into the issue's
        ``oompah.attachments`` metadata.

        Idempotent: existing metadata entries with the same path are
        preserved (so re-running the agent on the same issue doesn't
        produce duplicate records). Posts a completion comment listing
        any new artifacts.
        """
        from oompah.attachments import (
            ATTACHMENTS_SUBDIR, AttachmentStore, Attachment,
        )
        store = AttachmentStore(workspace_path)
        try:
            disk_records = store.list(issue.identifier)
        except Exception as exc:
            logger.debug("attachment list failed for %s: %s", issue.identifier, exc)
            return

        # Keep only the agent-generated entries from disk.
        generated_on_disk = [r for r in disk_records if r.generated]
        if not generated_on_disk:
            return

        try:
            tracker = self._tracker_for_issue(issue)
        except Exception as exc:
            logger.warning("tracker lookup failed for %s: %s", issue.identifier, exc)
            return

        # Read existing rich records from beads, then merge.
        try:
            existing = tracker.fetch_attachments(issue.identifier)
        except Exception:
            existing = []
        existing_paths = {e.get("path") for e in existing if isinstance(e, dict)}

        merged = list(existing)
        new_records: list[dict] = []
        for rec in generated_on_disk:
            if rec.path in existing_paths:
                continue
            entry = rec.to_dict()
            entry["added_by"] = "agent"
            merged.append(entry)
            new_records.append(entry)

        if not new_records:
            return

        try:
            tracker.set_attachments(
                issue.identifier, merged, project_root=workspace_path,
            )
        except Exception as exc:
            logger.warning(
                "set_attachments failed for %s: %s", issue.identifier, exc,
            )
            return

        # Completion comment listing what was generated.
        names = [os.path.basename(e["path"]) for e in new_records]
        msg = "Agent produced " + ", ".join(names)
        try:
            self._post_comment(
                issue.identifier, msg, project_id=issue.project_id,
            )
        except Exception:
            pass

    def _reap_oversize_outputs(self, workspace_path: str, issue: Issue) -> None:
        """Drop agent-generated attachments that push the issue over the
        per-issue size cap. Posts a warning comment listing what was
        removed."""
        from oompah.attachments import (
            ATTACHMENTS_SUBDIR, MAX_PER_ISSUE_BYTES,
        )
        out_dir = os.path.join(
            workspace_path, ATTACHMENTS_SUBDIR, issue.identifier, "outputs",
        )
        if not os.path.isdir(out_dir):
            return
        # Sum across both inputs and outputs to compute total.
        in_dir = os.path.join(
            workspace_path, ATTACHMENTS_SUBDIR, issue.identifier,
        )
        total = 0
        for d in (in_dir, out_dir):
            if not os.path.isdir(d):
                continue
            for entry in os.listdir(d):
                full = os.path.join(d, entry)
                if os.path.isfile(full) and entry != ".gitattributes":
                    total += os.path.getsize(full)

        if total <= MAX_PER_ISSUE_BYTES:
            return

        # Reap newest-first from outputs/ until under the cap.
        files = []
        for entry in os.listdir(out_dir):
            full = os.path.join(out_dir, entry)
            if os.path.isfile(full):
                files.append((os.path.getmtime(full), full, entry, os.path.getsize(full)))
        files.sort(reverse=True)  # newest first

        dropped: list[str] = []
        for _mtime, full, entry, size in files:
            if total <= MAX_PER_ISSUE_BYTES:
                break
            try:
                os.remove(full)
                dropped.append(entry)
                total -= size
            except OSError as exc:
                logger.warning("could not drop oversize output %s: %s", full, exc)

        if dropped:
            msg = (
                f"Dropped {len(dropped)} agent-generated attachment(s) to stay "
                f"under the per-issue {MAX_PER_ISSUE_BYTES} byte cap: "
                + ", ".join(dropped)
            )
            logger.warning("%s for %s", msg, issue.identifier)
            try:
                self._post_comment(
                    issue.identifier, msg, project_id=issue.project_id,
                )
            except Exception:
                pass

    @staticmethod
    def _lfs_pull_attachments(workspace_path: str, issue_identifier: str) -> None:
        """Best-effort `git lfs pull` for a single issue's attachment dir.

        No-op when ``git lfs`` isn't installed or the include path doesn't
        exist; both are normal for projects without LFS configured. Errors
        are logged at DEBUG so a missing LFS doesn't drown the orchestrator
        log.
        """
        include = f".oompah/attachments/{issue_identifier}/"
        try:
            subprocess.run(
                ["git", "lfs", "pull", f"--include={include}"],
                cwd=workspace_path,
                capture_output=True, text=True,
                timeout=60, check=False,
            )
        except FileNotFoundError:
            logger.debug("git lfs not installed; skipping pull for %s", issue_identifier)
        except subprocess.TimeoutExpired:
            logger.warning("git lfs pull timed out for %s", issue_identifier)
        except Exception as exc:
            logger.debug("git lfs pull failed for %s: %s", issue_identifier, exc)

    @staticmethod
    def _resolve_capabilities(provider, model: str | None) -> list[str]:
        """Return the modality capability list for a resolved (provider,
        model) pair.

        Defaults to ``["text"]`` when ``model`` is ``None`` or the
        provider hasn't declared capabilities for it. Used by the prompt
        renderer to decide whether to send attachments inline.
        """
        if not model:
            return ["text"]
        caps = (getattr(provider, "model_capabilities", None) or {}).get(model)
        if not caps:
            return ["text"]
        # Defensive: normalize to a list of unique non-empty strings.
        out: list[str] = []
        for c in caps:
            s = str(c).strip().lower()
            if s and s not in out:
                out.append(s)
        return out or ["text"]

    def _resolve_role(self, role_name: str | None):
        """Look up a role in RoleStore and return (provider, model).

        Returns ``(None, None)`` when ``role_name`` is empty, the role
        isn't in RoleStore, or the role's ``provider_id`` no longer
        points to an existing provider. Callers fall back to legacy
        profile-level resolution in that case.

        Primary resolution path for the role/profile decoupling — see
        epic oompah-zlz_2-xau7.
        """
        if not role_name:
            return (None, None)
        role = self.role_store.get(role_name)
        if role is None:
            return (None, None)
        provider = self.provider_store.get(role.provider_id)
        if provider is None:
            return (None, None)
        return (provider, role.model)

    def _resolve_provider(self, profile: AgentProfile, focus=None):
        """Resolve the provider for a profile.

        Priority:
        1. focus.provider_id (explicit operator override)
        2. focus.model_role → RoleStore
        3. profile.model_role → RoleStore
        4. profile.provider_id (legacy)
        5. provider_store.get_default()
        """
        if focus is not None and getattr(focus, "provider_id", None):
            p = self.provider_store.get(focus.provider_id)
            if p is not None:
                return p
            logger.warning(
                "Focus %r references unknown provider_id=%r; falling back to profile/default",
                focus.name, focus.provider_id,
            )
        # Role-based resolution (epic xau7). focus's role wins over profile's role.
        focus_role = getattr(focus, "model_role", None) if focus is not None else None
        for candidate_role in (focus_role, profile.model_role):
            p, _ = self._resolve_role(candidate_role)
            if p is not None:
                return p
        # Legacy fallback: profile.provider_id (kept for back-compat until
        # the migration soaks).
        if profile.provider_id:
            return self.provider_store.get(profile.provider_id)
        return self.provider_store.get_default()

    def _resolve_model(self, profile: AgentProfile, provider, focus=None) -> str | None:
        """Resolve the model name.

        Priority:
        1. focus.model (explicit operator override)
        2. focus.model_role → RoleStore (epic xau7)
        3. focus.model_role → provider.model_roles (legacy)
        4. profile.model (legacy explicit)
        5. profile.model_role → RoleStore (epic xau7)
        6. profile.model_role → provider.model_roles (legacy)
        7. provider.default_model
        8. provider.models[0]
        """
        # Focus-level overrides first.
        if focus is not None:
            if getattr(focus, "model", None):
                return focus.model
            role = getattr(focus, "model_role", None)
            if role:
                # RoleStore wins over provider.model_roles for the same role name.
                _, m = self._resolve_role(role)
                if m:
                    return m
                if provider.model_roles:
                    m = provider.model_roles.get(role)
                    if m:
                        return m
                    logger.warning(
                        "Focus %r model_role=%r not defined in RoleStore "
                        "or on provider %s; falling back to profile",
                        focus.name, role, provider.name,
                    )

        # Profile-level resolution. profile.model_role wins over
        # profile.model when both are set (preserves the legacy
        # behaviour from before epic xau7).
        if profile.model_role:
            _, m = self._resolve_role(profile.model_role)
            if m:
                return m
            if provider.model_roles:
                m = provider.model_roles.get(profile.model_role)
                if m:
                    return m
        return profile.model or provider.default_model or (provider.models[0] if provider.models else None)

    def _describe_rate_limit_context(
        self,
        entry: "RunningEntry",
        error_text: str | None,
    ) -> str:
        """Build a human-readable context string for rate-limit alerts and comments.

        Returns a string like ``"InferenceAPI (claude-sonnet-4-6) — tokens"``
        suitable for embedding in alert messages. Falls back to
        ``"an upstream API"`` if the profile or provider can't be resolved.

        ACP-mode dispatches (Claude SDK / Codex) omit the model because the
        SDK manages models internally with no fixed catalog — only the
        provider/backend name is shown (e.g. ``"Claude SDK"``).
        """
        # Parse the error body for a rate-limit reason first (needed even
        # for the fallback path when profile resolution fails).
        reason: str | None = None
        if error_text:
            error_lower = error_text.lower()
            if "rate limit type: tokens" in error_lower or "tokens" in error_lower:
                reason = "tokens"
            elif "requests per minute" in error_lower or "per minute" in error_lower:
                reason = "requests per minute"
            elif "overloaded" in error_lower:
                reason = "overloaded"
            elif "quota" in error_lower:
                reason = "quota"

        if not entry:
            return f"an upstream API — Reason: {reason}" if reason else "an upstream API"

        profile = self._get_profile_by_name(entry.agent_profile_name)
        if not profile:
            return f"an upstream API — Reason: {reason}" if reason else "an upstream API"

        mode = (getattr(profile, "mode", "auto") or "auto").lower()
        # ACP mode — SDK manages models internally; show backend name only.
        if mode == "acp":
            provider = self._resolve_provider(profile)
            if provider:
                backend = provider.backend or "Claude SDK"
                # Pretty-print the registered backend name (e.g. "claude" → "Claude SDK")
                if backend.lower() == "claude":
                    return "Claude SDK"
                return backend
            return "Claude SDK"

        # API/CLI mode — include provider + model.
        provider = self._resolve_provider(profile)
        provider_name = getattr(provider, "name", None) if provider else None
        model = self._resolve_model(profile, provider) if provider else None

        # Build the context string.
        if provider_name and model:
            core = f"{provider_name} ({model})"
        elif provider_name:
            core = provider_name
        else:
            core = "an upstream API"

        if reason:
            return f"{core} — Reason: {reason}"
        return core

    def _estimate_cost(
        self,
        profile: AgentProfile,
        input_tokens: int,
        output_tokens: int,
        *,
        sdk_cost_usd: float | None = None,
    ) -> float:
        """Estimate cost for a session based on provider model costs, falling back to profile rates.

        Returns 0.0 for ACP sessions whose provider is subscription-billed
        (``billing_model == "subscription"``) — those flat-rate sessions
        should not contribute to the rolling-window spend tracker even
        when ``model_costs`` is populated. See bead oompah-zlz_2-ag7h.

        For per-token ACP sessions, callers may pass ``sdk_cost_usd``
        with a non-None value to prefer the SDK's tier-aware total over
        the local ``model_costs`` lookup. Subscription ACP sessions
        ignore ``sdk_cost_usd`` and always return 0.
        """
        cost_in = profile.cost_per_1k_input
        cost_out = profile.cost_per_1k_output
        # Resolve costs from provider if available
        provider = self._resolve_provider(profile)
        mode = (getattr(profile, "mode", "auto") or "auto").lower()
        if provider:
            # Subscription-billed ACP providers do not contribute cost
            # to the rolling-window tracker — calls bill against the
            # operator's flat-rate subscription. Short-circuit here so
            # an operator-set model_costs entry (used only for
            # informational display) doesn't accidentally meter.
            if mode == "acp" and not provider.is_per_token_billed("acp"):
                return 0.0
            if provider.model_costs:
                model = self._resolve_model(profile, provider)
                if model:
                    pc_in, pc_out = provider.get_model_costs(model)
                    if pc_in or pc_out:
                        cost_in, cost_out = pc_in, pc_out
        # Per-token ACP: prefer SDK-reported total if present. The SDK
        # knows tier discounts oompah doesn't.
        if (
            mode == "acp"
            and provider is not None
            and provider.is_per_token_billed("acp")
            and sdk_cost_usd is not None
        ):
            try:
                return float(sdk_cost_usd)
            except (TypeError, ValueError):
                # Defensive: malformed SDK output → fall through to
                # local calc rather than crashing or charging $0.
                pass
        return (input_tokens / 1000.0) * cost_in + \
               (output_tokens / 1000.0) * cost_out

    def _check_budget(self) -> bool:
        """Return True if within budget, False if budget exceeded.

        Rolls the budget window first: if more than ``budget_window``
        has elapsed since ``budget_window_start``, ``estimated_cost`` is
        reset to zero and the window restarts. Persisted across restarts
        via ``service_state.json``.
        """
        if self.config.budget_limit <= 0:
            return True  # no budget limit set
        self._roll_budget_window_if_due()
        return self.state.agent_totals.estimated_cost < self.config.budget_limit

    def _budget_window_seconds(self) -> int:
        """Nominal window size in seconds for the configured budget_window.

        Used for display only — the actual roll boundary is calendar-
        aligned (top-of-hour / local midnight / Sunday 00:00) and may
        differ on DST transition days when a "day" window is 23 or 25
        wall-clock hours. See ``_next_budget_boundary``.
        """
        return {
            "hour": 3600,
            "day": 86400,
            "week": 604800,
        }.get(self.config.budget_window, 86400)

    def _budget_tz(self) -> ZoneInfo:
        """Resolve the timezone used to compute calendar boundaries.

        Caches the result on first call. Order of precedence:
        1. Explicit OOMPAH_BUDGET_TIMEZONE / config.budget_timezone (IANA).
        2. Host's local timezone (from TZ env var or /etc/localtime).
        3. UTC fallback.

        Invalid IANA names log a warning and fall through to UTC.
        """
        cached = getattr(self, "_cached_budget_tz", None)
        if cached is not None:
            return cached
        tz = self._resolve_budget_tz()
        self._cached_budget_tz = tz
        return tz

    def _resolve_budget_tz(self) -> ZoneInfo:
        """Compute (uncached) the configured ZoneInfo. See _budget_tz."""
        name = (self.config.budget_timezone or "").strip()
        if name:
            try:
                return ZoneInfo(name)
            except ZoneInfoNotFoundError:
                logger.warning(
                    "Invalid OOMPAH_BUDGET_TIMEZONE=%r — falling back to UTC. "
                    "Use IANA names like 'America/Los_Angeles' or 'UTC'.",
                    name,
                )
                return ZoneInfo("UTC")
        # No explicit value — auto-detect host local zone.
        return self._detect_local_tz()

    def _detect_local_tz(self) -> ZoneInfo:
        """Best-effort detection of the host's IANA timezone.

        Tries the TZ env var first (if it names a valid IANA zone), then
        the /etc/localtime symlink (Linux/macOS), then falls back to UTC.
        We avoid the ``tzlocal`` third-party package — operators who care
        about a specific zone can set OOMPAH_BUDGET_TIMEZONE explicitly.
        """
        tz_env = (os.environ.get("TZ") or "").strip()
        if tz_env:
            try:
                return ZoneInfo(tz_env)
            except ZoneInfoNotFoundError:
                pass
        try:
            link = os.path.realpath("/etc/localtime")
            marker = "/zoneinfo/"
            if marker in link:
                iana = link.split(marker, 1)[1]
                try:
                    return ZoneInfo(iana)
                except ZoneInfoNotFoundError:
                    pass
        except OSError:
            pass
        return ZoneInfo("UTC")

    def _previous_budget_boundary(self, ts: float) -> float:
        """Return the most-recent calendar boundary at-or-before ``ts``.

        - hour: :00:00 of the current hour in the budget timezone.
        - day:  00:00:00 of the current calendar date.
        - week: 00:00:00 Sunday of the current week (Sunday-start).

        Result is a Unix timestamp. Day/week boundaries are computed via
        ``datetime.combine(..., tzinfo=tz)`` so DST transitions snap to
        the wall-clock midnight in the configured zone.
        """
        tz = self._budget_tz()
        now = datetime.fromtimestamp(ts, tz=tz)
        kind = self.config.budget_window
        if kind == "hour":
            boundary = now.replace(minute=0, second=0, microsecond=0)
        elif kind == "week":
            # weekday() => Mon=0..Sun=6. We want Sunday 00:00 as the start.
            # days_since_sunday: Sun=0, Mon=1, ..., Sat=6.
            days_since_sunday = (now.weekday() + 1) % 7
            sunday_date = (now - timedelta(days=days_since_sunday)).date()
            boundary = datetime.combine(
                sunday_date, datetime.min.time(), tzinfo=tz,
            )
        else:  # "day" (and any unknown value via the parser fallback)
            boundary = datetime.combine(
                now.date(), datetime.min.time(), tzinfo=tz,
            )
        return boundary.timestamp()

    def _next_budget_boundary(self, ts: float) -> float:
        """Return the first calendar boundary STRICTLY AFTER ``ts``."""
        tz = self._budget_tz()
        prev_ts = self._previous_budget_boundary(ts)
        prev_dt = datetime.fromtimestamp(prev_ts, tz=tz)
        kind = self.config.budget_window
        if kind == "hour":
            # +1 hour in UTC seconds. Hour boundaries on DST days are a
            # known edge: the wall-clock "next :00" can be 0 or 2 hours
            # away, but operators choosing hour windows tend to reset
            # frequently enough that this is acceptable.
            next_dt = prev_dt + timedelta(hours=1)
        elif kind == "week":
            next_date = prev_dt.date() + timedelta(days=7)
            next_dt = datetime.combine(
                next_date, datetime.min.time(), tzinfo=tz,
            )
        else:  # "day"
            next_date = prev_dt.date() + timedelta(days=1)
            next_dt = datetime.combine(
                next_date, datetime.min.time(), tzinfo=tz,
            )
        next_ts = next_dt.timestamp()
        # If `ts` happened to land exactly on a boundary, prev_ts == ts;
        # next_ts is then strictly greater, which is what we want.
        if next_ts <= ts:
            # Defensive: shouldn't happen with sane inputs, but keep us
            # monotonic so the roll loop terminates.
            next_ts = ts + 1.0
        return next_ts

    def _budget_window_remaining_seconds(self, now_ts: float | None = None) -> float:
        """Seconds from ``now`` (default: current time) until the next
        calendar boundary. Used by the dashboard countdown."""
        now = time.time() if now_ts is None else now_ts
        next_boundary = self._next_budget_boundary(now)
        return max(0.0, next_boundary - now)

    def _roll_budget_window_if_due(self) -> None:
        """If the active budget window has crossed its calendar boundary,
        reset spend to zero and snap to the most-recent boundary. Persists
        the new window start.

        On a fresh boot with no persisted window, snap ``budget_window_start``
        to the *previous* boundary — so spend already accrued in the
        current calendar period is correctly attributed instead of starting
        a new "hour" at 14:17:23.

        No-op when ``budget_limit`` is unset (no limit, no rollover
        semantics).
        """
        if self.config.budget_limit <= 0:
            return
        now = time.time()
        start = self.state.budget_window_start
        # First call after a fresh boot with no persisted window — snap
        # to the most-recent boundary so the window is calendar-aligned
        # from the very first dispatch.
        if start <= 0:
            snapped = self._previous_budget_boundary(now)
            self.state.budget_window_start = snapped
            self.state.budget_window_kind = self.config.budget_window
            self._save_state(
                budget_window_start=snapped,
                budget_window_kind=self.config.budget_window,
                estimated_cost=self.state.agent_totals.estimated_cost,
            )
            return
        # If the configured window kind changed since the last save (e.g.
        # operator switched from "day" to "hour" via env var), treat that
        # as a fresh window — otherwise an in-flight day-window would carry
        # forward as a stale hour-window.
        if self.state.budget_window_kind != self.config.budget_window:
            snapped = self._previous_budget_boundary(now)
            self.state.agent_totals.estimated_cost = 0.0
            self.state.budget_window_start = snapped
            self.state.budget_window_kind = self.config.budget_window
            self.state.free_tier_dispatches_this_window = 0
            logger.info(
                "Budget window kind changed to %r — resetting spent to $0",
                self.config.budget_window,
            )
            self._save_state(
                budget_window_start=snapped,
                budget_window_kind=self.config.budget_window,
                estimated_cost=0.0,
            )
            return
        if now >= self._next_budget_boundary(start):
            # Snap to the most-recent boundary (handles long sleeps where
            # multiple windows lapsed without an intervening dispatch).
            snapped = self._previous_budget_boundary(now)
            self.state.agent_totals.estimated_cost = 0.0
            self.state.budget_window_start = snapped
            self.state.free_tier_dispatches_this_window = 0
            logger.info(
                "Budget window rolled (%s boundary crossed) — spent reset to $0",
                self.config.budget_window,
            )
            self._save_state(
                budget_window_start=snapped,
                budget_window_kind=self.config.budget_window,
                estimated_cost=0.0,
            )

    def _persist_budget_state(self) -> None:
        """Write the current spend + window markers to service_state.json
        so a restart preserves spend within the active window."""
        self._save_state(
            estimated_cost=self.state.agent_totals.estimated_cost,
            budget_window_start=self.state.budget_window_start,
            budget_window_kind=self.config.budget_window,
        )

    def _post_comment(self, identifier: str, text: str, author: str = "oompah",
                      project_id: str | None = None) -> None:
        """Post a comment on an issue (best-effort, non-blocking)."""
        try:
            tracker = self._tracker_for_project(project_id) if project_id else self.tracker
            tracker.add_comment(identifier, text, author=author)
        except Exception as exc:
            logger.debug("Failed to post comment on %s: %s", identifier, exc)

    # ------------------------------------------------------------------
    # Per-task cost telemetry
    # ------------------------------------------------------------------

    def _compute_run_cost_record(
        self,
        entry: RunningEntry,
    ) -> dict[str, Any] | None:
        """Build a cost record for one completed run.

        Returns a dict with shape::

            {
                "total_input_tokens": int,
                "total_output_tokens": int,
                "total_cost_usd": float,
                "by_model": {
                    "<model_id>": {
                        "input_tokens": int,
                        "output_tokens": int,
                        "cost_usd": float,
                    },
                    ...
                },
                "runs": [
                    {
                        "profile": str,
                        "model": str,
                        "input_tokens": int,
                        "output_tokens": int,
                        "cost_usd": float,
                        "recorded_at": str (ISO-8601),
                    },
                    ...
                ],
            }

        Returns None when there are no tokens to record (e.g. session
        never started or the agent exited before producing any output).
        """
        if not entry.session:
            return None
        input_tokens = entry.session.input_tokens
        output_tokens = entry.session.output_tokens
        if input_tokens == 0 and output_tokens == 0:
            return None

        profile = self._get_profile_by_name(entry.agent_profile_name)
        # Resolve model for this run
        model_id = "unknown"
        cost_usd = 0.0
        if profile:
            # Start with profile-level fallback rates
            pc_in: float = profile.cost_per_1k_input
            pc_out: float = profile.cost_per_1k_output
            provider = self._resolve_provider(profile)
            mode = (getattr(profile, "mode", "auto") or "auto").lower()
            if provider:
                m = self._resolve_model(profile, provider)
                if m:
                    model_id = m
                # Subscription-billed ACP providers do not contribute
                # cost to the per-issue task_costs metadata — calls
                # bill against the operator's flat-rate subscription.
                # See bead oompah-zlz_2-ag7h edge case
                # "model_costs set on a subscription-billed provider".
                if mode == "acp" and not provider.is_per_token_billed("acp"):
                    pc_in, pc_out = 0.0, 0.0
                elif provider.model_costs and model_id != "unknown":
                    # Override with provider model costs if available.
                    mp_in, mp_out = provider.get_model_costs(model_id)
                    if mp_in or mp_out:
                        pc_in, pc_out = mp_in, mp_out
            cost_usd = (input_tokens / 1000.0) * pc_in + (output_tokens / 1000.0) * pc_out

        # Per-token ACP providers: prefer SDK-reported total_cost_usd
        # over the local model_costs lookup (the SDK knows tier
        # discounts oompah doesn't). Subscription ACP runs short-
        # circuit above with pc_in/pc_out=0 and stay at $0 regardless
        # of any SDK number, matching the "subscription bills flat"
        # contract.
        sdk_cost = getattr(entry.session, "sdk_cost_usd", None)
        if sdk_cost is not None and profile:
            mode = (getattr(profile, "mode", "auto") or "auto").lower()
            provider = self._resolve_provider(profile) if profile else None
            if (
                mode == "acp"
                and provider is not None
                and provider.is_per_token_billed("acp")
            ):
                try:
                    cost_usd = float(sdk_cost)
                except (TypeError, ValueError):
                    # Defensive: malformed SDK output → keep local calc.
                    pass

        now_iso = datetime.now(timezone.utc).isoformat()
        run_record = {
            "profile": entry.agent_profile_name,
            "model": model_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 8),
            "recorded_at": now_iso,
        }

        # Build top-level totals and per-model breakdown
        by_model: dict[str, dict[str, Any]] = {
            model_id: {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(cost_usd, 8),
            }
        }
        return {
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
            "total_cost_usd": round(cost_usd, 8),
            "by_model": by_model,
            "runs": [run_record],
        }

    @staticmethod
    def _merge_cost_records(
        existing: dict[str, Any] | None,
        new_record: dict[str, Any],
    ) -> dict[str, Any]:
        """Accumulate *new_record* into *existing*, returning the merged result.

        Per-model entries are deduplicated by model id and summed.
        The ``runs`` list is appended so the full history is preserved.
        """
        if not existing or not isinstance(existing, dict):
            return new_record

        merged = {
            "total_input_tokens": (
                existing.get("total_input_tokens", 0)
                + new_record.get("total_input_tokens", 0)
            ),
            "total_output_tokens": (
                existing.get("total_output_tokens", 0)
                + new_record.get("total_output_tokens", 0)
            ),
            "total_cost_usd": round(
                existing.get("total_cost_usd", 0.0)
                + new_record.get("total_cost_usd", 0.0),
                8,
            ),
            "by_model": dict(existing.get("by_model", {})),
            "runs": list(existing.get("runs", [])),
        }

        # Merge per-model breakdown
        for model_id, new_model_data in new_record.get("by_model", {}).items():
            if model_id in merged["by_model"]:
                existing_model = merged["by_model"][model_id]
                merged["by_model"][model_id] = {
                    "input_tokens": (
                        existing_model.get("input_tokens", 0)
                        + new_model_data.get("input_tokens", 0)
                    ),
                    "output_tokens": (
                        existing_model.get("output_tokens", 0)
                        + new_model_data.get("output_tokens", 0)
                    ),
                    "cost_usd": round(
                        existing_model.get("cost_usd", 0.0)
                        + new_model_data.get("cost_usd", 0.0),
                        8,
                    ),
                }
            else:
                merged["by_model"][model_id] = dict(new_model_data)

        # Append run history
        merged["runs"].extend(new_record.get("runs", []))

        return merged

    def _write_task_cost_record(self, entry: RunningEntry) -> None:
        """Persist cost telemetry for a completed run into the issue's metadata.

        Storage key: ``oompah.task_costs`` in the issue's beads metadata.
        Multiple runs accumulate cumulatively — per-model entries are summed.

        This method is designed to be called from a background thread
        (fire-and-forget) so it must not block the worker exit path.
        Any exception is logged at WARNING and swallowed.
        """
        try:
            new_record = self._compute_run_cost_record(entry)
            if new_record is None:
                return  # nothing to record

            issue = entry.issue
            try:
                tracker = self._tracker_for_issue(issue)
            except Exception as exc:
                logger.warning(
                    "cost_record: tracker lookup failed for %s: %s",
                    entry.identifier, exc,
                )
                return

            # Fetch existing metadata
            existing_meta: dict[str, Any] = {}
            try:
                raw = tracker._run_bd(["show", issue.identifier, "--json"])
                rec = raw[0] if isinstance(raw, list) and raw else raw
                if isinstance(rec, dict):
                    meta = rec.get("metadata") or {}
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except (ValueError, TypeError):
                            meta = {}
                    if isinstance(meta, dict):
                        existing_meta = dict(meta)
            except Exception as exc:
                logger.debug(
                    "cost_record: failed to fetch metadata for %s: %s",
                    entry.identifier, exc,
                )
                # Proceed with empty metadata — we'll write what we have

            # Merge new record into existing cost record
            existing_costs = existing_meta.get("oompah.task_costs")
            merged_costs = self._merge_cost_records(
                existing_costs if isinstance(existing_costs, dict) else None,
                new_record,
            )
            existing_meta["oompah.task_costs"] = merged_costs

            # Persist merged metadata
            try:
                tracker._run_bd([
                    "update", issue.identifier,
                    "--metadata", json.dumps(existing_meta),
                ])
                logger.info(
                    "cost_record: wrote %s total=$%.4f models=%s",
                    entry.identifier,
                    merged_costs["total_cost_usd"],
                    ",".join(merged_costs["by_model"].keys()),
                )
            except Exception as exc:
                logger.warning(
                    "cost_record: failed to write metadata for %s: %s",
                    entry.identifier, exc,
                )
        except Exception as exc:
            logger.warning(
                "cost_record: unexpected error for %s: %s",
                entry.identifier, exc,
            )

    def _fire_task_cost_record(self, entry: RunningEntry) -> None:
        """Fire-and-forget: write cost telemetry in a background thread.

        Exceptions are logged but never propagate — the worker exit path
        must not be blocked or broken by cost-writing failures.
        """
        try:
            self._tick_pool.submit(self._write_task_cost_record, entry)
        except Exception as exc:
            logger.warning(
                "cost_record: failed to submit background write for %s: %s",
                entry.identifier, exc,
            )

    # ------------------------------------------------------------------
    # Per-agent telemetry comment (bead oompah-zlz_2-y3fy)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_tokens(n: int) -> str:
        """Format a token count compactly (e.g. 14200 → '14.2K')."""
        try:
            n = int(n)
        except (ValueError, TypeError):
            return "0"
        if n < 1000:
            return str(n)
        if n < 1_000_000:
            return f"{n / 1000:.1f}K"
        return f"{n / 1_000_000:.1f}M"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format a duration in seconds as '<H>h <M>m <S>s' or '<M>m <S>s' or '<S>s'."""
        try:
            seconds = float(seconds)
        except (ValueError, TypeError):
            return "0s"
        if seconds < 0:
            seconds = 0.0
        total = int(round(seconds))
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h {m}m {s}s"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"

    def _dispatch_attempt_label(self, entry: RunningEntry) -> str:
        """Return the dispatch_attempt label for the telemetry comment.

        Plain integers ("1", "2", ...) for the natural retry counter,
        or "YOLO-reopen" when the bead carries a YOLO reopen label
        (ci-fix / merge-conflict) — those dispatches are not driven by
        the orchestrator's retry queue, they're orchestrated by YOLO
        relabeling the bead.
        """
        labels = {str(l).lower() for l in (entry.issue.labels or [])}
        if "ci-fix" in labels or "merge-conflict" in labels:
            return "YOLO-reopen"
        attempt_num = (entry.retry_attempt or 0) + 1
        return str(attempt_num)

    def _count_tool_calls(self, entry: RunningEntry) -> int:
        """Count tool_call kind entries in the agent's activity log.

        Both api_agent and acp_agent emit ``AgentActivity(kind="tool_call", ...)``
        for each tool invocation; counting those is the canonical
        per-run tool-call metric. CLI runs (legacy subprocess agent) do
        not populate activity_log uniformly — they'll show 0, which is
        accurate ("not tracked") rather than wrong.
        """
        count = 0
        for activity in entry.activity_log or []:
            kind = getattr(activity, "kind", None)
            if kind == "tool_call":
                count += 1
        return count

    def _resolve_run_provider_and_model(
        self, entry: RunningEntry,
    ) -> tuple[str, str, str, bool]:
        """Resolve (provider_name, model_id, mode, is_subscription_acp).

        Prefers the snapshot fields populated by the worker
        (``entry.provider_name`` / ``entry.model_name``) since the focus
        / role may have changed mid-run; falls back to live resolution
        via the agent profile when those are not set (back-compat path).

        ``is_subscription_acp`` is True when the run was an ACP session
        against a subscription-billed provider — used by the telemetry
        formatter to render "(subscription)" instead of a $0 cost number.
        """
        profile = self._get_profile_by_name(entry.agent_profile_name)
        mode = (getattr(profile, "mode", "auto") or "auto").lower() if profile else "auto"
        provider = self._resolve_provider(profile) if profile else None
        if entry.provider_name:
            provider_name = entry.provider_name
        elif provider is not None:
            provider_name = provider.name
        else:
            provider_name = "unknown"
        if entry.model_name:
            model_id = entry.model_name
        else:
            model_id = self._resolve_model(profile, provider) if profile and provider else None
            model_id = model_id or "unknown"
        is_subscription_acp = bool(
            mode == "acp"
            and provider is not None
            and not provider.is_per_token_billed("acp")
        )
        return provider_name, model_id, mode, is_subscription_acp

    def _format_telemetry_comment(
        self, entry: RunningEntry, exit_reason: str, elapsed_seconds: float,
    ) -> str:
        """Build the per-agent telemetry comment text for ``entry``.

        Format (one block per worker run, see bead oompah-zlz_2-y3fy):

            Run #2 [attempt=2, profile=deep -> InferenceAPI/claude-sonnet-4-6]
            - Turns: 27, Tool calls: 18
            - Tokens: 14.2K in / 3.1K out [17.3K total]
            - Cost: $0.0042
            - Exit: normal, Duration: 6m 12s
            - Log: oompah-zlz_2-xxx__20260512T130000Z.jsonl
        """
        attempt_label = self._dispatch_attempt_label(entry)
        provider_name, model_id, mode, is_subscription_acp = (
            self._resolve_run_provider_and_model(entry)
        )

        role = entry.model_role or "—"
        profile_name = entry.agent_profile_name or "default"
        header = (
            f"Run #{attempt_label} "
            f"[attempt={attempt_label}, profile={profile_name}, "
            f"role={role} -> {provider_name}/{model_id}]"
        )

        session = entry.session
        if session:
            input_tokens = int(getattr(session, "input_tokens", 0) or 0)
            output_tokens = int(getattr(session, "output_tokens", 0) or 0)
            total_tokens = int(getattr(session, "total_tokens", 0) or 0)
            turns = int(getattr(session, "turn_count", 0) or 0)
        else:
            input_tokens = output_tokens = total_tokens = turns = 0

        tool_calls = self._count_tool_calls(entry)

        # Cost: subscription ACP runs display "(subscription)" verbatim;
        # everything else uses the same calc as the budget tracker so the
        # comment matches the running tally.
        if is_subscription_acp:
            cost_str = "(subscription)"
        else:
            profile = self._get_profile_by_name(entry.agent_profile_name)
            if profile is not None:
                cost_value = self._estimate_cost(
                    profile,
                    input_tokens,
                    output_tokens,
                    sdk_cost_usd=getattr(session, "sdk_cost_usd", None) if session else None,
                )
                cost_str = f"${cost_value:.4f}"
            else:
                cost_str = "$0.0000"

        log_basename = ""
        if entry.agent_log_path:
            try:
                log_basename = os.path.basename(entry.agent_log_path)
            except Exception:
                log_basename = entry.agent_log_path

        # Normalize exit reason for display: the orchestrator uses
        # "abnormal" internally, surface it as "error" to operators.
        exit_display = "error" if exit_reason == "abnormal" else exit_reason

        lines = [
            header,
            f"- Turns: {turns}, Tool calls: {tool_calls}",
            (
                f"- Tokens: {self._format_tokens(input_tokens)} in / "
                f"{self._format_tokens(output_tokens)} out "
                f"[{self._format_tokens(total_tokens)} total]"
            ),
            f"- Cost: {cost_str}",
            (
                f"- Exit: {exit_display}, "
                f"Duration: {self._format_duration(elapsed_seconds)}"
            ),
        ]
        if log_basename:
            lines.append(f"- Log: {log_basename}")
        return "\n".join(lines)

    def _write_telemetry_comment(
        self, entry: RunningEntry, exit_reason: str, elapsed_seconds: float,
    ) -> None:
        """Post the per-agent telemetry comment for ``entry`` (sync).

        Exceptions are caught and logged at WARNING so a comment-write
        failure can never block the worker exit path. Designed to be
        invoked from a background thread via ``_fire_telemetry_comment``.
        """
        try:
            comment = self._format_telemetry_comment(
                entry, exit_reason, elapsed_seconds,
            )
            project_id = entry.issue.project_id if entry.issue else None
            self._post_comment(
                entry.identifier, comment, project_id=project_id,
            )
        except Exception as exc:
            logger.warning(
                "telemetry_comment: failed to write for %s: %s",
                entry.identifier, exc,
            )

    def _fire_telemetry_comment(
        self, entry: RunningEntry, exit_reason: str, elapsed_seconds: float,
    ) -> None:
        """Fire-and-forget: post the per-agent telemetry comment in a
        background thread.

        Mirrors :meth:`_fire_task_cost_record` — exceptions are logged
        but never propagate so the worker exit path stays unblocked.
        See bead oompah-zlz_2-y3fy.
        """
        try:
            self._tick_pool.submit(
                self._write_telemetry_comment,
                entry, exit_reason, elapsed_seconds,
            )
        except Exception as exc:
            logger.warning(
                "telemetry_comment: failed to submit background write for %s: %s",
                entry.identifier, exc,
            )

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

    def _is_first_dispatch(self, issue: Issue, attempt: int | None,
                           override_profile: str | None) -> bool:
        """Return True if this is the very first dispatch of an issue.

        First dispatch means: no retry attempt number, no explicit profile
        override (i.e. not coming from a retry timer), and the issue hasn't
        been seen in the running set before.
        """
        return attempt is None and override_profile is None

    def _has_explicit_handoff_label(self, issue: Issue) -> bool:
        """Return True if the issue carries a needs:* label (explicit user routing)."""
        return any(label.startswith("needs:") for label in (issue.labels or []))

    def _is_safety_critical_issue(self, issue: Issue) -> bool:
        """Return True if this issue requires safety-critical handling that must
        bypass cost optimizations like default_first_dispatch.

        Two foci qualify today:
          * merge_conflict — rebase work has a high blast radius (force-pushes,
            dropped commits, blind ours/theirs accepts).
          * ci_fix — CI-fix work must push to the existing PR's branch, NOT
            cut a new branch and open a new PR. The ci_fix Focus's must_not_do
            rails ('Create a new branch...', 'Open a new pull request') are
            precisely what stops the failure mode in oompah-zlz_2-0pr (bead
            trickle-icl → PR #32 against main instead of pushing to
            trickle-rl5).

        Running such issues on the catch-all "default" profile first means
        the safety rails come too late: if the cheap-profile dispatch
        produces a bad-but-CI-passing change, the bead closes without the
        specialist ever running. See oompah-zlz_2-2sd and oompah-zlz_2-0pr.

        Detection mirrors each Focus's labels and keywords. We check
        labels/keywords directly rather than running select_focus to keep
        this fast and deterministic — and to avoid taking the LLM-triage
        path during the dispatch decision.
        """
        labels = {l.lower() for l in (issue.labels or [])}
        if "merge-conflict" in labels or "ci-fix" in labels:
            return True
        # Also match each Focus's keywords (whole-word, case-insensitive)
        # so beads that describe the work but lack the label still get the carve-out.
        text = f"{issue.title or ''} {issue.description or ''}".lower()
        for kw in (
            # merge_conflict keywords
            "merge conflict", "rebase conflict", "resolve conflict",
            # ci_fix keywords
            "ci fix", "ci-fix", "failed ci", "fix ci", "failing tests",
            "tier-", "matrix-verify", "github actions failure",
        ):
            if re.search(r"\b" + re.escape(kw) + r"\b", text):
                return True
        return False

    def _get_default_catch_all_profile(self) -> AgentProfile | None:
        """Return the catch-all profile (no issue_type / keyword / priority constraints).

        This is the profile with the name 'default', or the first profile
        found that has no constraints if 'default' doesn't exist.
        """
        # Prefer the profile explicitly named "default"
        explicit = self._get_profile_by_name("default")
        if explicit:
            return explicit
        # Fall back to the first profile with no constraints at all
        for p in self.config.agent_profiles:
            if not p.issue_types and not p.keywords and p.min_priority is None and p.max_priority is None:
                return p
        return None

    @staticmethod
    def _profile_is_acp(profile: AgentProfile | None) -> bool:
        """Return True iff *profile* is configured for ACP-mode dispatch.

        Centralizes the (mode or 'auto').lower() == 'acp' check used in
        several places — kept here so future tweaks (alias names, env
        overrides) only land in one spot.
        """
        if profile is None:
            return False
        return (getattr(profile, "mode", "auto") or "auto").lower() == "acp"

    def _find_acp_profile(self) -> AgentProfile | None:
        """Return the first configured profile whose ``mode`` is ``acp``.

        Used by the safety-critical carve-out (oompah-zlz_2-lfy): when a
        merge-conflict / ci-fix bead is dispatched outside the
        default_first_dispatch path AND the natural-resolved profile
        does NOT have mode=acp, we'd rather route the dispatch through
        an ACP profile (typically ``default``) so per-token billing
        flows through the operator's claude subscription instead of the
        per-token API meter — which on 2026-05-07 went hard 429 on
        trickle-6zi after _is_safety_critical_issue carved out
        default_first_dispatch.

        Preference order:
        1. The profile explicitly named ``default`` if it has mode=acp
           (matches what default_first_dispatch already prefers).
        2. Any other profile with mode=acp, in declaration order.

        Returns None when no ACP profile is configured (legacy /
        api-only deployments). Callers must handle that case by
        falling back to the natural profile.
        """
        # Prefer "default" so the carve-out behaves consistently with
        # default_first_dispatch's catch-all selection.
        named_default = self._get_profile_by_name("default")
        if self._profile_is_acp(named_default):
            return named_default
        for p in self.config.agent_profiles:
            if self._profile_is_acp(p):
                return p
        return None

    async def _dispatch(self, issue: Issue, attempt: int | None,
                        override_profile: str | None = None) -> None:
        """Dispatch a worker for an issue."""
        # Belt-and-suspenders: the regular dispatch loop already checks
        # _paused via _should_dispatch, but the retry path
        # (_on_retry_timer -> _dispatch) bypasses that check. Reject here
        # too so a retry that was already in flight when pause() was
        # called can't silently re-dispatch.
        if self._paused:
            logger.info(
                "Skipping dispatch of %s: orchestrator paused",
                issue.identifier,
            )
            self.state.claimed.discard(issue.id)
            return
        self.state.reject_streak.pop(issue.id, None)

        # Resolve profile and compute natural_profile_name for default_first_dispatch.
        natural_profile_name: str | None = None

        # Use escalated profile if provided, otherwise match normally
        if override_profile:
            profile = self._get_profile_by_name(override_profile)
            if not profile:
                profile = self._match_agent_profile(issue)
        elif (
            self.config.default_first_dispatch
            and self._is_first_dispatch(issue, attempt, override_profile)
            and not self._has_explicit_handoff_label(issue)
            and issue.issue_type != "epic"  # epics keep existing routing
            and not self._is_safety_critical_issue(issue)  # merge-conflict: skip cost opt
        ):
            # default_first_dispatch: use the catch-all profile on first dispatch,
            # but remember what the "natural" profile would be so the first retry
            # can jump straight to it instead of walking up from "default".
            default_profile = self._get_default_catch_all_profile()
            natural_matched = self._match_agent_profile(issue)
            if default_profile is None:
                # No default catch-all found — fall back to normal matching
                profile = natural_matched
            elif natural_matched and natural_matched.name != (default_profile.name if default_profile else ""):
                # Natural profile differs from default — record it for escalation
                profile = default_profile
                natural_profile_name = natural_matched.name
                logger.info(
                    "default_first_dispatch: using profile=%s for %s (natural=%s)",
                    profile.name, issue.identifier, natural_profile_name,
                )
            else:
                # Natural match IS the default, or no natural match — no change
                profile = default_profile if default_profile else natural_matched
        else:
            profile = self._match_agent_profile(issue)
            # Safety-critical ACP preservation (oompah-zlz_2-lfy):
            # The default_first_dispatch carve-out for merge-conflict /
            # ci-fix beads is intentional (we want the specialist focus's
            # safety rails on the FIRST dispatch). Side effect: in
            # setups where only the ``default`` profile has mode=acp,
            # carving out also strands the dispatch on the per-token
            # api_agent path, which is what blew up trickle-6zi on
            # 2026-05-07 (HTTP 429 token-rate-limit cascade).
            #
            # Fix: when the carve-out fires (i.e. a safety-critical
            # bead routed via natural matching) AND the natural-matched
            # profile is NOT ACP, swap to the first ACP profile we can
            # find. Focus selection is independent of profile (label-
            # /keyword-driven), so the merge_conflict / ci_fix Focus's
            # must_not_do rails still apply unchanged.
            #
            # Only fires for first dispatch on a safety-critical bead
            # without an explicit needs:* handoff label or override.
            # Retries / escalations keep their existing routing — we
            # don't want to second-guess the escalation hierarchy.
            if (
                self._is_first_dispatch(issue, attempt, override_profile)
                and not self._has_explicit_handoff_label(issue)
                and issue.issue_type != "epic"
                and self._is_safety_critical_issue(issue)
                and not self._profile_is_acp(profile)
            ):
                acp_profile = self._find_acp_profile()
                if acp_profile is not None and (
                    profile is None or acp_profile.name != profile.name
                ):
                    natural_name = profile.name if profile else "<none>"
                    natural_profile_name = natural_name if profile else None
                    logger.info(
                        "safety_critical_acp_routing: using profile=%s for %s "
                        "(natural=%s, labels=%s) — carve-out kept ACP routing "
                        "to avoid per-token rate limits",
                        acp_profile.name,
                        issue.identifier,
                        natural_name,
                        sorted(issue.labels or []),
                    )
                    profile = acp_profile

        profile_name = profile.name if profile else "default"

        logger.info(
            "Dispatching issue_id=%s issue_identifier=%s attempt=%s agent_profile=%s",
            issue.id,
            issue.identifier,
            attempt,
            profile_name,
        )
        self.state.claimed.add(issue.id)

        # Race protection: the candidate fetch that produced ``issue`` may
        # have predated a state change (e.g. user closing the bead via the
        # UI between fetch and dispatch). If we blindly write
        # status=in_progress here, we'd silently re-open a closed issue.
        # Re-read current state and abort if it's terminal.
        try:
            tracker = self._tracker_for_issue(issue)
            refreshed = await asyncio.get_event_loop().run_in_executor(
                self._tick_pool,
                lambda: tracker.fetch_issue_states_by_ids([issue.id]),
            )
        except Exception as exc:
            logger.debug(
                "Pre-dispatch state recheck failed for %s: %s — proceeding anyway",
                issue.identifier, exc,
            )
            refreshed = []
        if refreshed:
            cur_state = (refreshed[0].state or "").strip().lower()
            terminal = {s.strip().lower() for s in self.config.tracker_terminal_states}
            if cur_state in terminal:
                logger.info(
                    "Aborting dispatch of %s: state moved to %r since fetch",
                    issue.identifier, cur_state,
                )
                self.state.claimed.discard(issue.id)
                self.state.completed.add(issue.id)
                # Drop any pending retry too — the issue is done.
                rt = self.state.retry_attempts.pop(issue.id, None)
                if rt and rt.timer_handle and not rt.timer_handle.cancelled():
                    rt.timer_handle.cancel()
                return

        # Move issue to in_progress (in thread to avoid blocking event loop)
        try:
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
        if retry and retry.timer_handle and not retry.timer_handle.cancelled():
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
            natural_profile_name=natural_profile_name,
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
        """Worker: create workspace, build prompt, run agent turns.

        Routing is keyed off ``profile.mode`` (default ``auto``):

        * ``"acp"`` — Claude Agent SDK / claude CLI subprocess. Calls
          bill against the operator's claude subscription, not the
          per-token API meter. See ``oompah/acp_agent.py``.
        * ``"api"`` — OpenAI-compatible chat completions. The
          dispatcher asserts the profile resolves to a provider; if
          not, falls through to cli with a warning.
        * ``"cli"`` — legacy subprocess + native streaming-JSON path
          (oompah/agent.py). No provider needed.
        * ``"auto"`` (default) — preserves today's behavior: api if a
          provider resolves, else cli.

        Invalid mode strings get normalized to ``auto`` at config-load
        time, so by the time we get here only the four valid values
        are in play.
        """
        mode = (profile.mode if profile else "auto").lower()

        if mode == "acp":
            await self._run_acp_worker(issue, attempt, profile)
            return

        if mode == "cli":
            await self._run_cli_worker(issue, attempt, profile)
            return

        # api or auto: dispatch by the resolved provider's mode.
        # When the provider itself is ACP-mode, route through the ACP
        # worker even though the profile said "api"/"auto" — RoleStore
        # may have repointed this role at an ACP-mode provider after
        # the profile was created (epic xau7).
        if profile:
            provider = self._resolve_provider(profile)
            if provider:
                if getattr(provider, "mode", "api") == "acp":
                    await self._run_acp_worker(issue, attempt, profile)
                    return
                await self._run_api_worker(issue, attempt, profile, provider)
                return
            if mode == "api":
                logger.warning(
                    "Profile %r is mode=api but provider did not resolve; "
                    "falling through to cli for issue %s",
                    profile.name, issue.identifier,
                )

        await self._run_cli_worker(issue, attempt, profile)

    async def _run_api_worker(self, issue: Issue, attempt: int | None, profile: AgentProfile, provider) -> None:
        """Worker using the OpenAI-compatible API agent."""
        exit_reason = "normal"
        error_msg = None
        max_turns = profile.max_turns if profile.max_turns else self.config.max_turns

        # Select focus first so its (optional) model/provider overrides
        # participate in resolution. See plans/per-focus-models.md and
        # plans/agentic-focus-triage.md. The async variant tries an LLM
        # call against the provider's default_model and falls back to
        # the deterministic scorer on any failure.
        focus = await select_focus_async(issue, provider=provider)
        logger.info("Issue %s assigned focus: %s (%s)",
                    issue.identifier, focus.name, focus.role)

        # Apply focus-level provider override if any. If the focus changes
        # the provider, log it.
        focus_provider = self._resolve_provider(profile, focus=focus)
        if focus_provider is not None and focus_provider is not provider:
            logger.info(
                "Focus %r overrides provider: %s -> %s",
                focus.name, provider.name, focus_provider.name,
            )
            provider = focus_provider

        # Resolve model with focus participating. ACP-mode providers
        # with an empty catalog (Claude SDK, etc.) are SDK-managed —
        # the SDK picks the model from the operator's subscription,
        # so no model name is required at dispatch time.
        model = self._resolve_model(profile, provider, focus=focus)
        is_acp_sdk_managed = (
            getattr(provider, "mode", "api") == "acp"
            and not (provider.models or [])
        )
        if not model and not is_acp_sdk_managed:
            raise ValueError(f"No model resolved for profile {profile.name!r} with provider {provider.name}")

        # Diagnostic: surface where the model came from.
        if is_acp_sdk_managed and not model:
            model_source = "acp.sdk-managed"
            model_display = "(SDK-managed)"
        elif focus.model:
            model_source = f"focus={focus.name}.model"
            model_display = model
        elif focus.model_role and provider.model_roles and provider.model_roles.get(focus.model_role) == model:
            model_source = f"focus={focus.name}.model_role={focus.model_role}"
            model_display = model
        elif profile.model_role and provider.model_roles and provider.model_roles.get(profile.model_role) == model:
            model_source = f"profile={profile.name}.model_role={profile.model_role}"
            model_display = model
        elif profile.model and profile.model == model:
            model_source = f"profile={profile.name}.model"
            model_display = model
        else:
            model_source = "provider.default"
            model_display = model
        logger.info("Resolved provider=%s model=%s source=%s for %s",
                    provider.name, model_display, model_source, issue.identifier)

        if not is_acp_sdk_managed:
            if profile.model_role and provider.model_roles and profile.model_role not in provider.model_roles:
                logger.error("Model role %r not defined in provider %s (available roles: %s)",
                             profile.model_role, provider.name, ", ".join(provider.model_roles))
                raise ValueError(f"Model role {profile.model_role!r} not defined in provider {provider.name}")
            if provider.models and model not in provider.models and model != provider.default_model:
                logger.error("Model %s not available in provider %s (available: %s)",
                             model, provider.name, ", ".join(provider.models))
                raise ValueError(f"Model {model} not available in provider {provider.name}")
            if provider.models and model not in provider.models and model == provider.default_model:
                logger.warning("Model %s is provider.default_model but not in provider.models; proceeding with dispatch",
                               model)

        # Resolve modality capabilities for the (provider, model) pair.
        # Used by the prompt renderer to decide whether to embed
        # attachments inline or only mention them in the text body.
        capabilities = self._resolve_capabilities(provider, model)
        project_obj = (
            self.project_store.get(issue.project_id) if issue.project_id else None
        )

        try:
            # Run blocking setup work in thread to avoid blocking event loop
            def _setup_worker():
                # Resolve workspace via the epic_strategy-aware helper:
                # under epic_strategy='shared' a child of an epic uses
                # the shared epic worktree; otherwise per-bead path.
                wp, _epic = self._create_workspace_for_issue(issue)

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

                # Materialize attachments under the worktree — `git lfs pull`
                # is a no-op when LFS isn't installed or the path doesn't
                # exist, so this is safe to run unconditionally.
                attachments = list(getattr(issue, "attachments", None) or [])
                if attachments and issue.identifier:
                    self._lfs_pull_attachments(wp, issue.identifier)

                rendered = render_prompt(
                    self._prompt_template, issue, attempt,
                    comments=comments, focus_text=focus.render(project_obj),
                    workspace_path=wp, memories=memories,
                    attachments=attachments,
                    capabilities=capabilities,
                    project_root=wp,
                    project=project_obj,
                )
                return wp, rendered, attachments

            loop = asyncio.get_event_loop()
            workspace_path, prompt, attachment_paths = await loop.run_in_executor(
                self._tick_pool, _setup_worker
            )

            # One-line summary of what made it into the prompt.
            if attachment_paths:
                embedded = len(prompt.parts) - 1 if prompt.parts else 0
                elided = len(prompt.elided)
                logger.info(
                    "Issue %s attachments: total=%d embedded=%d elided=%d caps=%s",
                    issue.identifier, len(attachment_paths),
                    embedded, elided, ",".join(capabilities),
                    )

            # Store focus on running entry for dashboard display
            running_entry = self.state.running.get(issue.id)
            if running_entry:
                running_entry.focus_name = focus.name
                running_entry.focus_role = focus.role

            # Decide which opt-in tools to expose. Currently this is
            # just attach_image, gated on (a) the active focus opting in
            # and (b) the resolved model declaring image capability.
            from oompah.api_agent import TOOL_DEFINITIONS as _TD, _OPT_IN_TOOLS as _OPT
            base_tools = {
                t["function"]["name"] for t in _TD
                if t["function"]["name"] not in _OPT
            }
            if getattr(focus, "allow_image_output", False) and "image" in capabilities:
                base_tools.add("attach_image")

            # Per-dispatch JSONL log capturing every request, response,
            # and activity event. One file per dispatch so the user can
            # see exactly what was sent to and returned from the model.
            log_dir = os.environ.get("OOMPAH_AGENT_LOG_DIR") or os.path.join(
                os.path.expanduser("~"), ".oompah", "agent-logs",
            )
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            agent_log_path = os.path.join(
                log_dir, f"{issue.identifier}__{ts}.jsonl",
            )

            # Compute the project's main beads directory so the agent's
            # ``bd`` commands write to the orchestrator's source-of-truth DB,
            # not the worktree's forked dolt. Falls back to None for the
            # legacy single-project path (no project_id), in which case the
            # agent's bd commands resolve normally from cwd.
            beads_dir = None
            if issue.project_id:
                proj = self.project_store.get(issue.project_id)
                if proj and proj.repo_path:
                    beads_dir = os.path.join(proj.repo_path, ".beads")

            session = ApiAgentSession(
                base_url=provider.base_url,
                api_key=provider.api_key,
                model=model,
                workspace_path=workspace_path,
                max_turns=max_turns,
                stall_turns=self.config.stall_turns,
                system_prompt="You are an autonomous coding agent. Use the provided tools to complete the task.",
                enabled_tools=base_tools,
                model_max_context=provider.get_model_context(model),
                log_path=agent_log_path,
                beads_dir=beads_dir,
            )
            logger.info(
                "Agent log for %s -> %s", issue.identifier, agent_log_path,
            )

            # Update running entry with minimal session info, log path,
            # and resolved provider/model snapshot so _on_worker_exit's
            # telemetry comment can name them without re-resolving (the
            # focus / role may have changed mid-run). See bead
            # oompah-zlz_2-y3fy.
            if issue.id in self.state.running:
                running_entry = self.state.running[issue.id]
                running_entry.agent_log_path = agent_log_path
                running_entry.provider_name = provider.name
                running_entry.model_name = model
                # Role: focus override wins over profile role; falls back
                # to None when nothing role-driven was used.
                running_entry.model_role = (
                    getattr(focus, "model_role", None)
                    or profile.model_role
                )
                running_entry.session = LiveSession(
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

            # Enforce per-issue attachment cap on agent-generated outputs,
            # then record what was produced in beads metadata so the
            # dashboard can render it. Only on successful runs.
            if result.status == "succeeded":
                try:
                    self._reap_oversize_outputs(workspace_path, issue)
                except Exception as exc:
                    logger.debug(
                        "output reap failed for %s: %s", issue.identifier, exc,
                    )
                try:
                    self._record_generated_attachments(workspace_path, issue)
                except Exception as exc:
                    logger.warning(
                        "metadata writeback failed for %s: %s",
                        issue.identifier, exc,
                    )

        except Exception as exc:
            exit_reason = "abnormal"
            error_msg = str(exc)
            logger.exception(
                "API worker failed issue_id=%s",
                issue.id,
                extra={"issue_id": issue.id},
            )
        finally:
            if not issue.project_id:
                try:
                    wp = self.workspace_mgr.workspace_path_for(issue.identifier)
                    self.workspace_mgr.run_after_run(wp)
                except Exception:
                    pass
            await self._on_worker_exit(issue.id, exit_reason, error_msg)

    async def _run_acp_worker(
        self, issue: Issue, attempt: int | None, profile: AgentProfile,
    ) -> None:
        """Worker that drives the bundled ``claude`` CLI via the Claude
        Agent SDK so per-token costs bill against the operator's
        Pro/Max subscription instead of the API meter.

        Mirrors :meth:`_run_api_worker`'s structure: select focus,
        resolve the (informational) provider+model, set up the worktree,
        render the prompt, instantiate ``AcpAgentSession``, run the
        task, emit completion via ``_on_worker_exit``. The big shape
        differences:

        * Token usage is reported by the SDK and rolled into
          state.agent_totals at end-of-task, but ``estimated_cost`` is
          not incremented for ACP sessions because the actual billing
          happens against the subscription, not a per-token meter.
        * The tool catalog comes from ``oompah/acp_tools.py``, which
          wraps the same ``_exec_*`` helpers api_agent uses. This
          keeps cd-guard / BEADS_DIR / shell-redirect in force.
        * Permission prompts are auto-accepted via the SDK's
          ``permission_mode="bypassPermissions"`` (mirrors
          ``--dangerously-skip-permissions``); the audit trail goes
          into per-agent JSONL via on_event.
        """
        from oompah.acp_agent import AcpAgentSession
        from oompah.acp_tools import build_tool_catalog

        exit_reason = "normal"
        error_msg = None
        max_turns = profile.max_turns if profile.max_turns else self.config.max_turns

        focus = await select_focus_async(issue, provider=None)
        logger.info(
            "Issue %s assigned focus: %s (%s)",
            issue.identifier, focus.name, focus.role,
        )

        # Resolve a provider/model purely for diagnostic and prompt-render
        # purposes — the SDK doesn't need a provider URL or API key, but
        # the prompt template embeds the model name and our state response
        # surfaces it for dashboard display.
        provider = self._resolve_provider(profile, focus=focus)
        model: str | None = None
        if provider is not None:
            model = self._resolve_model(profile, provider, focus=focus)
        # Fallback model name when no provider is configured at all (e.g.
        # CLI-only deployments running ACP). Use whatever the profile
        # specifies; ultimately the SDK / claude CLI choose.
        model = model or profile.model or "default"

        capabilities = self._resolve_capabilities(provider, model) if provider else []
        project_obj = (
            self.project_store.get(issue.project_id) if issue.project_id else None
        )

        try:
            def _setup_worker():
                # Resolve workspace via the epic_strategy-aware helper.
                wp, _epic = self._create_workspace_for_issue(issue)

                self._post_comment(
                    issue.identifier, f"Focus: {focus.role}",
                    project_id=issue.project_id,
                )
                self._clear_handoff_labels(issue)

                try:
                    tracker = self._tracker_for_issue(issue)
                    comments = tracker.fetch_comments(issue.identifier)
                except Exception:
                    comments = []
                try:
                    memories = tracker.fetch_memories()
                except Exception:
                    memories = {}

                attachments = list(getattr(issue, "attachments", None) or [])
                if attachments and issue.identifier:
                    self._lfs_pull_attachments(wp, issue.identifier)

                rendered = render_prompt(
                    self._prompt_template, issue, attempt,
                    comments=comments, focus_text=focus.render(project_obj),
                    workspace_path=wp, memories=memories,
                    attachments=attachments,
                    capabilities=capabilities,
                    project_root=wp,
                    project=project_obj,
                )
                return wp, rendered, attachments

            loop = asyncio.get_event_loop()
            workspace_path, prompt, _attachment_paths = await loop.run_in_executor(
                self._tick_pool, _setup_worker,
            )

            running_entry = self.state.running.get(issue.id)
            if running_entry:
                running_entry.focus_name = focus.name
                running_entry.focus_role = focus.role

            beads_dir = None
            if issue.project_id:
                proj = self.project_store.get(issue.project_id)
                if proj and proj.repo_path:
                    beads_dir = os.path.join(proj.repo_path, ".beads")

            # Per-dispatch JSONL log. Reuses api_agent's location convention.
            log_dir = os.environ.get("OOMPAH_AGENT_LOG_DIR") or os.path.join(
                os.path.expanduser("~"), ".oompah", "agent-logs",
            )
            os.makedirs(log_dir, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            agent_log_path = os.path.join(
                log_dir, f"{issue.identifier}__{ts}.jsonl",
            )
            log_fp = open(agent_log_path, "a", encoding="utf-8")
            logger.info(
                "ACP agent log for %s -> %s (mode=acp model=%s)",
                issue.identifier, agent_log_path, model,
            )

            # Update running entry session + telemetry snapshot. The
            # provider/model fields are diagnostic for ACP runs (the
            # SDK picks the actual model from the subscription) but
            # they're still what the operator sees in `bd comments`.
            # See bead oompah-zlz_2-y3fy.
            if issue.id in self.state.running:
                running_entry_acp = self.state.running[issue.id]
                running_entry_acp.agent_log_path = agent_log_path
                running_entry_acp.provider_name = (
                    provider.name if provider is not None else "acp"
                )
                running_entry_acp.model_name = model
                running_entry_acp.model_role = (
                    getattr(focus, "model_role", None)
                    or profile.model_role
                )
                running_entry_acp.session = LiveSession(
                    session_id=f"acp-{model}",
                    thread_id="acp",
                    turn_id="0",
                    agent_pid=None,
                    last_event="acp_started",
                    last_timestamp=datetime.now(timezone.utc),
                    last_message=f"ACP session: {model}",
                )

            tool_catalog = build_tool_catalog(
                workspace_path,
                beads_dir=beads_dir,
                run_command_timeout_s=60,
            )

            from oompah.api_agent import AgentActivity

            def _on_event(ev) -> None:
                """Capture ACP events to JSONL + the running session
                state + the activity_log the dashboard reads.

                The dashboard's per-agent step list reads from
                ``RunningEntry.activity_log`` and gets push notifications
                via ``_notify_activity``. Forgetting this is why ACP
                runs initially appeared "doing nothing" in the UI even
                when the agent was actively working — the JSONL log was
                being written but the live state wasn't.
                """
                # 1. Persist the raw event to per-agent JSONL.
                try:
                    log_fp.write(json.dumps({
                        "ts": datetime.fromtimestamp(
                            ev.timestamp, timezone.utc,
                        ).isoformat(),
                        "kind": ev.event,
                        "usage": ev.usage,
                        "payload": ev.payload,
                    }, default=str) + "\n")
                    log_fp.flush()
                except Exception:
                    pass

                # 2. Map ACP event kinds onto the AgentActivity vocabulary
                #    the UI already renders for api_agent runs. Keeping
                #    the same kinds means no template changes needed.
                payload = ev.payload or {}
                # Only `acp_text` (actual model speech) maps to 'message'.
                # Session start/result events are metadata-shaped (JSON-ish
                # blobs in the detail field) and should NOT be hidden by
                # the dashboard's Verbose:OFF filter that targets human-
                # readable speech only. Give them distinct kinds so the
                # client allowlist can include 'message' alone and still
                # show speech without the metadata noise.
                #
                # Default fallback must NOT be 'message' — any unmapped
                # event would otherwise leak through the Verbose:OFF
                # filter masquerading as model speech. 'other' is opaque
                # to the filter (still visible in Verbose:ON).
                kind_map = {
                    "acp_text": "message",
                    "acp_thinking": "thinking",
                    "acp_tool_use": "tool_call",
                    "acp_tool_result": "tool_result",
                    "acp_session_start": "session",
                    "acp_result": "session",
                    "acp_permission_grant": "permission",
                    "acp_permission_deny": "permission",
                    "acp_assistant_error": "error",
                    "acp_session_error": "error",
                    "acp_turn_timeout": "error",
                }
                activity_kind = kind_map.get(ev.event, "other")

                if ev.event == "acp_tool_use":
                    tool_name = payload.get("tool", "?")
                    raw_input = payload.get("input")
                    args_str = json.dumps(raw_input, default=str)[:140] \
                        if raw_input is not None else ""
                    summary = f"{tool_name}({args_str})"
                    detail = json.dumps(raw_input, default=str)[:2000] \
                        if raw_input is not None else ""
                elif ev.event == "acp_tool_result":
                    summary = (
                        "tool error" if payload.get("is_error")
                        else "tool ok"
                    )
                    detail = str(payload.get("content", ""))[:2000]
                elif ev.event == "acp_text":
                    text = str(payload.get("text", ""))
                    summary = text[:200] or "(empty text)"
                    detail = text[:2000]
                elif ev.event == "acp_thinking":
                    text = str(payload.get("text", ""))
                    summary = text[:200] or "(thinking)"
                    detail = text[:2000]
                elif ev.event == "acp_session_start":
                    summary = (
                        f"ACP session: model={payload.get('model') or 'subscription default'} "
                        f"perm={payload.get('permission_mode')}"
                    )
                    detail = json.dumps(payload, default=str)[:2000]
                elif ev.event == "acp_result":
                    sub = payload.get("subtype") or "completed"
                    is_err = payload.get("is_error")
                    cost = payload.get("total_cost_usd")
                    summary = (
                        f"{sub}{' (error)' if is_err else ''}"
                        f"{f' cost=${cost:.4f}' if isinstance(cost, (int, float)) else ''}"
                    )
                    detail = json.dumps(payload, default=str)[:2000]
                else:
                    summary = ev.event
                    detail = json.dumps(payload, default=str)[:2000]

                if issue.id in self.state.running:
                    entry = self.state.running[issue.id]
                    sess = entry.session
                    turn_count = sess.turn_count if sess else 0

                    activity = AgentActivity(
                        turn=turn_count,
                        kind=activity_kind,
                        summary=summary,
                        detail=detail,
                        timestamp=ev.timestamp,
                        usage=dict(ev.usage) if ev.usage else None,
                    )
                    entry.activity_log.append(activity)

                    if sess:
                        sess.last_event = ev.event
                        sess.last_timestamp = datetime.fromtimestamp(
                            ev.timestamp, timezone.utc,
                        )
                        sess.last_message = summary[:200]
                        u = ev.usage or {}
                        sess.input_tokens = int(u.get("input_tokens", 0) or 0)
                        sess.output_tokens = int(u.get("output_tokens", 0) or 0)
                        sess.total_tokens = int(u.get("total_tokens", 0) or 0)

                    # 3. Push to WS clients exactly the same way api_agent does.
                    self._notify_activity(issue.identifier, activity)
                    self._notify_state_only()

            # RenderedPrompt has both `text` (canonical) and optional
            # `parts` (OpenAI-style content array, only set when images
            # are embedded). ACP/claude takes a single string, so use
            # `text`. parts being None is the common case.
            prompt_text = getattr(prompt, "text", None) or str(prompt)

            # ACP-mode model selection: the per-issue model resolved
            # against InferenceAPI (e.g. claude-sonnet-4-6, MiniMax)
            # is not what claude CLI dispatches against — claude uses
            # whichever model the operator's subscription / auth chose.
            # Passing a non-claude model name (the MiniMax name slipped
            # in via the default profile's model_role: fast) is a no-op
            # at best, an error at worst. Only forward model names that
            # look like Claude models; otherwise let the SDK pick the
            # subscription default.
            acp_model: str | None = None
            if model and any(
                marker in model.lower()
                for marker in ("claude", "haiku", "sonnet", "opus")
            ):
                acp_model = model

            # ACP backend selection (oompah-zlz_2-0hzh): provider may
            # nominate a non-default backend via ModelProvider.backend.
            # Falls back to "claude" when unset, preserving back-compat
            # for legacy providers persisted before the field existed.
            acp_backend_name = (
                getattr(provider, "backend", None) or "claude"
                if provider is not None
                else "claude"
            )

            session = AcpAgentSession(
                workspace_path=workspace_path,
                prompt=prompt_text,
                model=acp_model,
                max_turns=max_turns,
                env={"BEADS_DIR": beads_dir} if beads_dir else None,
                tool_catalog=tool_catalog,
                on_event=_on_event,
                backend_name=acp_backend_name,
            )

            try:
                status = await session.run_task()
            finally:
                try:
                    log_fp.close()
                except Exception:
                    pass

            # Roll per-session counters into orchestrator totals. Token
            # totals always accumulate for observability / reporting.
            # Cost accumulation happens in :meth:`_on_worker_exit` via
            # :meth:`_estimate_cost`, which is billing_model-aware:
            #
            # * subscription-billed ACP providers (default for legacy
            #   ACP) — cost stays at $0; calls bill against the
            #   operator's flat-rate subscription.
            # * per-token-billed ACP providers — cost is metered
            #   against the rolling-window budget. We prefer the SDK's
            #   ``total_cost_usd`` (it knows tier discounts oompah
            #   doesn't, see ``sdk_cost_usd`` stashed below); when
            #   absent, fall back to the local ``model_costs`` lookup.
            #   Missing both → cost defaults to 0 with a WARNING (don't
            #   crash dispatch over missing config). See bead
            #   oompah-zlz_2-ag7h.
            self.state.agent_totals.input_tokens += session.input_tokens
            self.state.agent_totals.output_tokens += session.output_tokens
            self.state.agent_totals.total_tokens += session.total_tokens

            if issue.id in self.state.running and self.state.running[issue.id].session:
                s = self.state.running[issue.id].session
                s.input_tokens = session.input_tokens
                s.output_tokens = session.output_tokens
                s.total_tokens = session.total_tokens
                s.turn_count = session.turn_count
                s.last_event = f"acp_{status}"
                # Stash the SDK-reported total cost (if any) so
                # _estimate_cost / _compute_run_cost_record can prefer
                # it over the local model_costs lookup for per-token
                # ACP runs. None means "fall back to model_costs";
                # subscription ACP runs are short-circuited to $0 in
                # the cost helpers regardless of the SDK number.
                # See bead oompah-zlz_2-ag7h.
                s.sdk_cost_usd = (
                    session.total_cost_usd
                    if (
                        provider is not None
                        and provider.is_per_token_billed("acp")
                    )
                    else None
                )
                # Emit a warning when per-token ACP runs have no usable
                # rate source (no SDK cost AND no model_costs entry).
                # The cost helpers default to $0 in that case so dispatch
                # proceeds; the operator just needs to backfill rates
                # for accurate budget tracking on the next run.
                if (
                    provider is not None
                    and provider.is_per_token_billed("acp")
                    and session.total_cost_usd is None
                    and (
                        not model
                        or not provider.model_costs
                        or provider.get_model_costs(model) == (0.0, 0.0)
                    )
                ):
                    logger.warning(
                        "Per-token ACP provider %r has no model_costs entry for "
                        "model %r (issue %s); cost recorded as $0.00. Set rates "
                        "via /providers to enable accurate budget tracking.",
                        provider.name, model, issue.identifier,
                    )

            if status == "succeeded":
                exit_reason = "normal"
            elif status == "stalled":
                exit_reason = "stalled"
                error_msg = "ACP turn timeout exceeded"
            elif status == "interrupted":
                exit_reason = "interrupted"
                error_msg = session.last_error
            elif status == "failed":
                exit_reason = "abnormal"
                error_msg = session.last_error or "ACP session reported failure"
            else:  # "errored"
                exit_reason = "abnormal"
                error_msg = session.last_error or "ACP session errored"

            if status == "succeeded":
                try:
                    self._reap_oversize_outputs(workspace_path, issue)
                except Exception as exc:
                    logger.debug(
                        "output reap failed for %s: %s", issue.identifier, exc,
                    )
                try:
                    self._record_generated_attachments(workspace_path, issue)
                except Exception as exc:
                    logger.warning(
                        "metadata writeback failed for %s: %s",
                        issue.identifier, exc,
                    )

        except Exception as exc:
            exit_reason = "abnormal"
            error_msg = str(exc)
            logger.exception(
                "ACP worker failed issue_id=%s",
                issue.id,
                extra={"issue_id": issue.id},
            )
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
            # Resolve workspace via the epic_strategy-aware helper:
            # under epic_strategy='shared' a child of an epic uses
            # the shared epic worktree; otherwise per-bead path.
            workspace_path, _epic = self._create_workspace_for_issue(issue)

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
                # Store focus on running entry for dashboard display.
                # CLI worker has no API provider/model resolution (the
                # claude subprocess picks its own model from auth), but
                # we still record the model role and a placeholder
                # provider/model so the telemetry comment has SOMETHING
                # to render. See bead oompah-zlz_2-y3fy.
                cli_running = self.state.running.get(issue.id)
                if cli_running:
                    cli_running.focus_name = cli_focus.name
                    cli_running.focus_role = cli_focus.role
                    cli_running.provider_name = "cli"
                    cli_running.model_name = (
                        (profile.model if profile and profile.model else None)
                        or "cli-managed"
                    )
                    cli_running.model_role = (
                        getattr(cli_focus, "model_role", None)
                        or (profile.model_role if profile else None)
                    )

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

                cli_project_obj = (
                    self.project_store.get(issue.project_id)
                    if issue.project_id else None
                )

                for turn_number in range(1, max_turns + 1):
                    # Build prompt
                    if turn_number == 1:
                        prompt = render_prompt(
                            self._prompt_template, current_issue, attempt,
                            comments=cli_comments,
                            focus_text=cli_focus.render(cli_project_obj),
                            workspace_path=workspace_path, memories=cli_memories,
                            project=cli_project_obj,
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
                extra={"issue_id": issue.id},
            )
        except Exception as exc:
            exit_reason = "abnormal"
            error_msg = str(exc)
            logger.exception(
                "Worker unexpected error issue_id=%s issue_identifier=%s",
                issue.id,
                issue.identifier,
                extra={"issue_id": issue.id},
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

    # ------------------------------------------------------------------
    # Close gate (oompah-zlz_2-gz8w)
    # ------------------------------------------------------------------

    def _run_close_gate(
        self,
        entry: "RunningEntry",
        current_issue: Issue,
        project_id: str | None,
    ) -> bool:
        """Run the close gate for an agent-driven close.

        Returns True when the close is ALLOWED, False when REFUSED.

        When refused:
        * Posts a diagnostic comment on the bead (author=oompah).
        * Reopens the bead so it re-enters the dispatch cycle.

        Fail-open on any internal error so a gate bug can never pin a
        bead in-progress forever.
        """
        from oompah.close_gate import (
            CloseGateResult,
            check_close_gate,
            build_refusal_comment,
        )

        if not self.config.close_gate_enabled:
            return True

        # Resolve project context
        repo_path = ""
        slug = ""
        base_branch = "main"
        access_token = None
        if project_id:
            try:
                project = self.project_store.get(project_id)
                if project:
                    repo_path = project.repo_path or ""
                    base_branch = project.branch or "main"
                    access_token = getattr(project, "access_token", None)
                    if project.repo_url:
                        from oompah.scm import extract_repo_slug
                        slug = extract_repo_slug(project.repo_url)
            except Exception as exc:
                logger.warning(
                    "close_gate: project lookup failed for %s: %s — failing open",
                    entry.identifier, exc,
                )
                return True

        result = check_close_gate(
            current_issue,
            repo_path=repo_path,
            slug=slug,
            base_branch=base_branch,
            access_token=access_token,
            entry_profile=entry.agent_profile_name,
            entry_focus=entry.focus_name or "",
            entry_attempt=entry.retry_attempt or 0,
        )

        if result.allowed:
            if result.skip_reason:
                logger.debug(
                    "close_gate: allowed for %s (skip_reason=%s)",
                    entry.identifier, result.skip_reason,
                )
            else:
                logger.debug(
                    "close_gate: allowed for %s (open_prs=%d merged_prs=%d)",
                    entry.identifier, result.open_prs, result.merged_prs,
                )
            return True

        # REFUSED — post comment, reopen, return False
        try:
            comment = build_refusal_comment(current_issue, result, base_branch)
            self._post_comment(
                entry.identifier,
                comment,
                project_id=project_id,
            )
        except Exception as exc:
            logger.warning(
                "close_gate: failed to post refusal comment for %s: %s",
                entry.identifier, exc,
            )

        # Reopen the bead
        try:
            tracker = self._tracker_for_project(project_id) if project_id else self.tracker
            tracker.update_issue(entry.identifier, status="open")
            logger.warning(
                "close_gate: REFUSED close for %s — %d commit(s) ahead of %s, "
                "open_prs=%d merged_prs=%d — bead reopened",
                entry.identifier, result.commits_ahead, base_branch,
                result.open_prs, result.merged_prs,
            )
        except Exception as exc:
            logger.warning(
                "close_gate: failed to reopen %s after refusal: %s",
                entry.identifier, exc,
            )

        return False

    def _run_completion_verifier(
        self,
        entry: "RunningEntry",
        current_issue: Issue,
        project_id: str | None,
    ) -> VerifierResult:
        """Run the post-close verification pass (oompah-zlz_2-y0ns).

        Called from ``_on_worker_exit`` when the worker exited
        ``normal`` AND the bead has moved to a terminal state — i.e.
        the agent successfully ran ``bd close``.

        Returns a ``VerifierResult``. Callers inspect ``passed`` to
        decide whether to honor the close or reopen with diagnostics.
        Every internal exception fails open (returns ``passed=True``,
        ``skipped=True``) so verification can never become a stuck
        loop hazard.
        """
        if not self.config.verify_completion:
            return VerifierResult(passed=True, skipped=True, skip_reason="disabled")
        try:
            workspace_path = self.workspace_mgr.workspace_path_for(entry.identifier)
        except Exception as exc:
            logger.warning(
                "completion verifier: unable to resolve workspace for %s: %s",
                entry.identifier, exc,
            )
            return VerifierResult(passed=True, skipped=True, skip_reason=f"workspace error: {exc}")

        base_branch = "main"
        if project_id:
            try:
                project = self.project_store.get(project_id)
                if project and project.branch:
                    base_branch = project.branch
            except Exception:
                pass

        # Use the same provider the agent's profile resolved to —
        # ensures the verifier hits the same endpoint the operator has
        # already authenticated against.
        provider = None
        try:
            profile = self._get_profile_by_name(entry.agent_profile_name)
            if profile is not None:
                provider = self._resolve_provider(profile)
        except Exception:
            provider = None
        if provider is None:
            try:
                provider = self.provider_store.get_default()
            except Exception:
                provider = None

        attempt = entry.retry_attempt or 0
        try:
            result = verify_completion(
                current_issue,
                workspace_path,
                base_branch,
                provider,
                attempt=attempt,
                escalate_after_attempts=self.config.escalate_after_attempts,
                enable_stage2=self.config.verify_completion_llm,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "completion verifier raised for %s; failing open. err=%s",
                entry.identifier, exc,
            )
            return VerifierResult(passed=True, skipped=True, skip_reason=f"verifier error: {exc}")

        if result.skipped:
            logger.info(
                "completion verifier skipped for %s: %s",
                entry.identifier, result.skip_reason,
            )
        elif result.passed:
            logger.info(
                "completion verifier passed for %s",
                entry.identifier,
            )
        else:
            logger.warning(
                "completion verifier REJECTED close for %s: missing_files=%s missing_symbols=%s llm_verdict=%s",
                entry.identifier,
                (result.stage1.missing_files if result.stage1 else []),
                (result.stage1.missing_symbols if result.stage1 else []),
                (result.stage2.verdict if result.stage2 else None),
            )
        return result

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

            # Estimate cost from agent profile. For per-token ACP runs
            # the SDK-reported total_cost_usd (stashed on the LiveSession
            # by _run_acp_worker) is preferred over the local
            # model_costs calc — the SDK knows tier discounts oompah
            # doesn't. Subscription ACP runs always cost $0 regardless.
            profile = self._get_profile_by_name(entry.agent_profile_name)
            if profile:
                cost = self._estimate_cost(
                    profile,
                    entry.session.input_tokens,
                    entry.session.output_tokens,
                    sdk_cost_usd=getattr(entry.session, "sdk_cost_usd", None),
                )
                # Roll the window first so the increment lands in the
                # right bucket — otherwise a worker that finishes 1ms
                # after the day rollover would be charged to yesterday.
                self._roll_budget_window_if_due()
                self.state.agent_totals.estimated_cost += cost
                self.state.cost_by_profile[entry.agent_profile_name] = \
                    self.state.cost_by_profile.get(entry.agent_profile_name, 0.0) + cost

                # Reset circuit breaker if we're back under budget
                if self.state.budget_exceeded and self._check_budget():
                    self.state.budget_exceeded = False

                # Persist updated spend so a restart inside the active
                # window doesn't reset the counter to $0.
                self._persist_budget_state()

        # Write per-task cost telemetry (fire-and-forget, never blocks exit)
        self._fire_task_cost_record(entry)

        # Write per-agent telemetry comment for this run (fire-and-forget,
        # never blocks exit). One comment per worker run, regardless of
        # exit reason — multiple runs on the same bead each leave a
        # separate comment so the bead history shows all attempts
        # side-by-side. See bead oompah-zlz_2-y3fy.
        self._fire_telemetry_comment(entry, reason, elapsed)

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
                tracker.update_issue(
                    entry.identifier,
                    status="open",
                    **{"add-label": "asking_question"},
                )
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
            # If this success came from a retry (attempt > 0) the
            # earlier failure(s) likely filed transient bug beads via
            # the error watcher.  Auto-close them now.  attempt == 0
            # was the first dispatch — nothing was retried, so don't
            # auto-close anything.
            if entry.retry_attempt and entry.retry_attempt > 0:
                self._auto_close_transient_errors_for_entry(entry)
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
                        # Close is a separate bd command — can't combine with update
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
                            # Try to escalate to a stronger profile before retrying
                            escalated, escalated_name = self._next_profile_for_retry(entry)
                            if escalated:
                                delay = self._backoff_delay(reopen_count)
                                self._post_comment(
                                    entry.identifier,
                                    f"Agent completed without closing this issue ({elapsed:.0f}s{tokens_str}). "
                                    f"Escalating from '{entry.agent_profile_name}' to '{escalated.name}'. "
                                    f"Retrying in {delay // 1000}s ({reopen_count}/{max_reopens}).",
                                    project_id=project_id,
                                )
                                self._schedule_retry(
                                    issue_id,
                                    attempt=reopen_count,
                                    identifier=entry.identifier,
                                    delay_ms=delay,
                                    error="completed_without_closing",
                                    escalated_profile=escalated_name,
                                )
                                logger.info("Escalating %s from %s to %s after completing without closing (%d/%d)",
                                            entry.identifier, entry.agent_profile_name, escalated.name,
                                            reopen_count, max_reopens)
                            else:
                                # No higher profile available — retry with same profile
                                tracker.update_issue(entry.identifier, status="open")
                                logger.info("Agent completed without closing %s — reset to open (%d/%d)",
                                            entry.identifier, reopen_count, max_reopens)
                else:
                    # Agent successfully closed the bead.
                    #
                    # Step 1: Close gate (oompah-zlz_2-gz8w).
                    # Refuse the close when the branch has unmerged
                    # commits AND no open/merged PR exists. When
                    # refused, the gate reopens the bead and posts a
                    # diagnostic comment — we don't proceed to the
                    # verifier or mark completed.
                    gate_passed = self._run_close_gate(
                        entry, current, project_id,
                    )
                    if not gate_passed:
                        # Gate refused. The bead was reopened by the
                        # gate; the next dispatch cycle will pick it up.
                        # Skip verifier and completed tracking.
                        pass
                    else:
                        # Step 2: Completion verifier (oompah-zlz_2-y0ns).
                        # Run the two-stage check (regex + LLM) against the
                        # bead's "# Acceptance criteria" section to catch
                        # false-success closures where the agent's diff
                        # doesn't actually satisfy the AC.
                        verifier_result = self._run_completion_verifier(
                            entry, current, project_id,
                        )
                        max_verifier_rejects = 3
                        reject_count = self._verifier_reject_counts.get(issue_id, 0)
                        if not verifier_result.passed and reject_count < max_verifier_rejects:
                            # Reject the close: reopen, post diagnostics,
                            # schedule a retry. Increment reject count so
                            # we eventually give up if the agent keeps
                            # shipping the same gap.
                            self._verifier_reject_counts[issue_id] = reject_count + 1
                            try:
                                tracker.reopen_issue(entry.identifier)
                            except Exception as exc:
                                logger.warning(
                                    "Failed to reopen %s after verifier rejection: %s",
                                    entry.identifier, exc,
                                )
                                self.state.completed.add(issue_id)
                                self.state.reopen_counts.pop(issue_id, None)
                                self._ensure_review_exists(entry, project_id)
                            else:
                                try:
                                    self._post_comment(
                                        entry.identifier,
                                        verifier_result.render_rejection_comment(),
                                        project_id=project_id,
                                    )
                                except Exception as exc:
                                    logger.warning(
                                        "Failed to post verifier-rejection comment "
                                        "to %s: %s", entry.identifier, exc,
                                    )
                                # Schedule a retry — try a higher profile if
                                # available so the next attempt has more
                                # capacity to satisfy the AC.
                                next_attempt = (entry.retry_attempt or 0) + 1
                                escalated, escalated_name = (
                                    self._next_profile_for_retry(entry)
                                )
                                delay = self._backoff_delay(next_attempt)
                                self._schedule_retry(
                                    issue_id,
                                    attempt=next_attempt,
                                    identifier=entry.identifier,
                                    delay_ms=delay,
                                    error="completion_verifier_rejected",
                                    escalated_profile=escalated_name if escalated else None,
                                )
                                logger.info(
                                    "Completion verifier rejected close for %s — "
                                    "reopened, retrying in %ds (reject %d/%d)",
                                    entry.identifier, delay // 1000,
                                    reject_count + 1, max_verifier_rejects,
                                )
                        else:
                            if not verifier_result.passed:
                                # We've hit the verifier reject ceiling —
                                # fail open and let the close stick, but
                                # log a WARNING so the operator can
                                # investigate.
                                logger.warning(
                                    "Completion verifier rejected %s for the %dth "
                                    "time — failing open and honoring the close",
                                    entry.identifier, reject_count + 1,
                                )
                            self.state.completed.add(issue_id)
                            self.state.reopen_counts.pop(issue_id, None)
                            self._verifier_reject_counts.pop(issue_id, None)
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
            rl_ctx = self._describe_rate_limit_context(entry, error)
            self._alerts.append({
                "level": "warning",
                "source": "rate_limit",
                "message": f"Rate limited by {rl_ctx} — pausing dispatch for {cooldown_s}s",
            })
            next_attempt = (entry.retry_attempt or 0) + 1
            delay = max(cooldown_s * 1000, self._backoff_delay(next_attempt))
            self._post_comment(
                entry.identifier,
                f"Rate limited by {rl_ctx}. Pausing all dispatch for {cooldown_s}s. "
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
                "Rate limited by %s — pausing dispatch for %ds. issue_id=%s retrying_in_ms=%d",
                rl_ctx, cooldown_s, issue_id, delay,
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
                escalated_name = ""
                if reason == "stalled":
                    self.state.stall_counts[issue_id] = self.state.stall_counts.get(issue_id, 0) + 1
                    stall_count = self.state.stall_counts[issue_id]

                # Escalate on both stalled and max_turns once threshold is met
                if next_attempt >= self.config.escalate_after_attempts:
                    escalated, escalated_name = self._next_profile_for_retry(entry)

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
                    escalated_profile=escalated_name or None,
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
                rl_ctx = self._describe_rate_limit_context(entry, error)
                self._alerts.append({
                    "level": "warning",
                    "source": "rate_limit",
                    "message": f"Rate limited by {rl_ctx} — pausing dispatch for {cooldown_s}s",
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
      "focus_hint": "one of: feature, refactor, frontend, docs, test, security, devops, chore",
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
                              if f.name not in ("epic_planner", "merge_conflict", "ci_fix"))
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

        # Label the original issue as decomposed and move to deferred (atomic)
        try:
            tracker.update_issue(
                parent_issue.identifier,
                status="deferred",
                **{"add-label": "decomposed"},
            )
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
        if existing and existing.timer_handle and not existing.timer_handle.cancelled():
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

        # Write per-task cost telemetry before dropping the runtime entry
        # (fire-and-forget, never blocks termination)
        self._fire_task_cost_record(entry)

        # Write per-agent telemetry comment for this terminated run too
        # so the operator sees every attempt — including manual kills —
        # in `bd comments <id>`. Exit reason is "terminated" to
        # distinguish from natural exits. See bead oompah-zlz_2-y3fy.
        self._fire_telemetry_comment(entry, "terminated", elapsed)

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
            "config": {
                "default_first_dispatch": self.config.default_first_dispatch,
            },
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
                "window": self.config.budget_window,
                "window_seconds": self._budget_window_seconds(),
                "window_start": self.state.budget_window_start,
                # Seconds from "now" until the NEXT calendar boundary
                # (top-of-hour / local midnight / Sunday 00:00). This is
                # what dashboards should countdown against — not
                # window_start + nominal_seconds, which can drift on DST
                # transition days.
                "window_remaining_seconds": self._budget_window_remaining_seconds(),
                "window_timezone": str(self._budget_tz().key),
                # True when the budget is exceeded but free-tier dispatches
                # are still happening in the current window. Lets the
                # dashboard show "exceeded but still working" instead of
                # appearing dead.
                "free_tier_active": (
                    self.state.budget_exceeded
                    and self.state.free_tier_dispatches_this_window > 0
                ),
                "free_tier_dispatches_this_window": (
                    self.state.free_tier_dispatches_this_window
                ),
            },
            "agent_profiles": [
                {
                    "name": p.name,
                    "command": p.command,
                    "provider_id": p.provider_id or (dp.id if (dp := self.provider_store.get_default()) else None),
                    "model": p.model,
                    "model_role": p.model_role,
                    "mode": p.mode,
                }
                for p in self.config.agent_profiles
            ],
            # Tells the dashboard whether agent profiles are managed via the
            # JSON store (read/write through CRUD endpoints) or pinned to
            # WORKFLOW.md (read-only). See docs/agent-profiles.md.
            "agent_profiles_source": getattr(
                self.config, "agent_profiles_source", "json",
            ),
            "rate_limits": self.state.rate_limits,
            "projects": [p.to_dict() for p in self.project_store.list_all()],
            "open_reviews_by_project": {
                pid: self._count_open_reviews(pid)
                for pid in (getattr(self, "_reviews_cache", None) or {})
            },
            "alerts": list(self._alerts),
            "reviews_summary": self._reviews_summary(),
            "proposed_foci_count": self._proposed_foci_count(),
            "dolt_sync": self.dolt_sync_snapshot(),
        }

    def dolt_sync_snapshot(self) -> dict[str, Any]:
        """Public-facing snapshot of the dolt sync watchdog state.

        Mapping of ``project_id`` -> per-project state dict with
        ``last_push_at`` / ``last_pull_at`` / ``last_error`` / ``divergent``
        fields. Used by both ``get_snapshot()`` (dashboard) and the
        ``/api/v1/orchestrator/dolt-sync`` endpoint.

        Each entry also carries ``project_name`` and ``repo_path``
        (resolved from the project store) so the dashboard's
        click-to-expand alert modal can render the project label and
        suggested recovery commands without a second round-trip
        (oompah-zlz_2-g8uk).
        """
        try:
            projects_by_id = {p.id: p for p in self.project_store.list_all()}
        except Exception:
            projects_by_id = {}
        out: dict[str, Any] = {}
        for pid, st in self._dolt_sync_state.items():
            entry = st.to_dict()
            proj = projects_by_id.get(pid)
            entry["project_name"] = proj.name if proj else pid
            entry["repo_path"] = (
                getattr(proj, "repo_path", None) if proj else None
            )
            out[pid] = entry
        return out

    def _reviews_summary(self) -> dict[str, int]:
        """Aggregate per-tick review cache for the dashboard badge.

        Avoids the dashboard polling /api/v1/reviews every WS state update.

        ``total`` counts every open non-draft review across every project,
        including yolo projects. Yolo PRs auto-merge once their CI is
        green, but until then they (a) block other dispatch in the same
        project via ``_project_has_open_review``, and (b) the operator may
        still want to peek at what landed. So we show them.

        ``needs_attention`` stays non-yolo: it flags reviews that the
        watchdog cannot resolve on its own (conflicts, failed CI) and
        therefore require human action. That's the red badge.
        """
        reviews_cache = getattr(self, "_reviews_cache", {}) or {}
        yolo_ids = {p.id for p in self.project_store.list_all() if getattr(p, "yolo", False)}
        total = 0
        yolo_pending = 0
        queued = 0
        conflicts = 0
        ci_failures = 0
        for project_id, reviews in reviews_cache.items():
            for r in reviews or []:
                # Skip reviews where an agent is currently working — handled elsewhere.
                if getattr(r, "agent_active", False):
                    continue
                total += 1
                if project_id in yolo_ids:
                    yolo_pending += 1
                    # Of those, count how many GitHub has already accepted into
                    # its merge queue (auto_merge enabled). The remainder are
                    # still awaiting enqueue by oompah's YOLO watchdog.
                    if getattr(r, "auto_merge_enabled", False):
                        queued += 1
                    continue
                if getattr(r, "has_conflicts", False):
                    conflicts += 1
                elif getattr(r, "ci_status", None) == "failed":
                    ci_failures += 1
        # oompah-zlz_2-btf.2: count PRs whose YOLO enqueue is blocked on
        # a repo-level configuration toggle. Only count entries whose
        # review still appears in this tick's cache so a closed PR
        # doesn't keep inflating the badge.
        live_keys = set()
        for project_id, reviews in reviews_cache.items():
            for r in reviews or []:
                live_keys.add((project_id, str(getattr(r, "id", ""))))
        repo_config_errors = getattr(self, "_yolo_repo_config_errors", {}) or {}
        needs_repo_config = sum(1 for k in repo_config_errors if k in live_keys)

        return {
            "total": total,
            "yolo_pending": yolo_pending,
            "queued": queued,
            "conflicts": conflicts,
            "ci_failures": ci_failures,
            "needs_repo_config": needs_repo_config,
            "needs_attention": conflicts + ci_failures,
        }

    def _proposed_foci_count(self) -> int:
        """Count foci with status='proposed'.

        Cached by foci.json mtime so the snapshot doesn't re-read JSON on
        every state push. Returns 0 when the file does not yet exist.
        """
        path = ".oompah/foci.json"
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0.0
        cached = getattr(self, "_proposed_foci_cache", None)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        try:
            count = sum(1 for f in load_foci() if f.status == "proposed")
        except Exception:
            count = 0
        self._proposed_foci_cache = (mtime, count)
        return count

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
