"""Orchestrator: polling, dispatch, reconciliation, and retry management."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from enum import Enum
from typing import Any

from oompah.agent import AgentError, AgentEvent, AgentSession
from oompah.agent_profile_store import AgentProfileStore
from oompah.api_agent import AgentActivity, ApiAgentSession
from oompah.completion_verifier import VerifierResult, verify_completion
from oompah.config import (
    ServiceConfig,
    WorkflowError,
    load_workflow,
    validate_dispatch_config,
)
from oompah.events import EventBus, EventType
from oompah.release_addendum_queue import ReleaseAddendumQueue
from oompah.release_delivery_compat import make_delivery_store
from oompah.release_delivery_executor import cherry_pick_delivery
from oompah.release_delivery_queue import ReleaseDeliveryQueue
from oompah.release_delivery_store import make_delivery_worktree_key
from oompah.epic_proposal import process_epic_proposal_issue
from oompah.github_intake_bridge import (
    poll_github_issue_intake_project,
    project_uses_github_issue_intake,
    sync_github_issue_intake_statuses_for_project,
)
from oompah.models import (
    AgentProfile,
    AgentTotals,
    BlockerRef,
    EpicRebaseState,
    EpicRebaseStateEntry,
    Issue,
    LiveSession,
    OrchestratorState,
    Project,
    RetryEntry,
    RunningEntry,
)
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DECOMPOSED,
    DUPLICATE_CANDIDATE,
    DONE,
    IN_PROGRESS,
    IN_REVIEW,
    MERGED,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    PROPOSED,
    canonicalize_status,
    epic_rollup_state,
    is_terminal_status,
    more_advanced_status,
)
from oompah.focus import (
    _MIN_SCORE_TO_FLAG,
    analyze_completed_issue,
    find_similar_issues,
    load_foci,
    save_suggestion,
    select_focus,
    select_focus_async,
)
from oompah.prompt import PromptError, build_continuation_prompt, render_prompt
from oompah.projects import (
    ProjectError,
    ProjectStore,
    github_owner_repo_from_url,
    github_work_branch_name,
)
from oompah.providers import ProviderStore
from oompah.roles import CandidateSelector, RoleStore
from oompah.scm import ReviewRequest, detect_provider, extract_repo_slug
from oompah.error_watcher import ErrorWatcher
from oompah.tracker import (
    ADAPTER_REGISTRY,
    TrackerAuthError,
    TrackerError,
    TrackerNotConfiguredError,
    TrackerProtocol,
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
from oompah.churn_magnet import (
    ChurnMagnetStore,
    get_store as _get_churn_store,
    record_conflicts_for_project,
    run_git_merge_tree,
)

import json
import os

from oompah.ipc import OrchestratorIPC, get_ipc

_DISPATCH_DUPLICATE_SUPPRESSION_SCORE = 0.75

logger = logging.getLogger(__name__)


_AGENT_LOG_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _agent_log_issue_stem(issue_identifier: str) -> str:
    """Return a filesystem-safe stem for per-dispatch agent log filenames."""
    stem = _AGENT_LOG_STEM_RE.sub("_", str(issue_identifier or "").strip())
    stem = stem.strip("._-")
    return stem or "issue"


def _agent_log_path(log_dir: str, issue_identifier: str, ts: str | None = None) -> str:
    """Return a per-dispatch agent log path with a safe basename."""
    os.makedirs(log_dir, exist_ok=True)
    stamp = ts or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return os.path.join(log_dir, f"{_agent_log_issue_stem(issue_identifier)}__{stamp}.jsonl")


def _error_class_for_tracker_exc(exc: BaseException) -> str:
    """Classify a tracker/project exception for error_watcher dedup.

    Returned values match the documented classes used by the error
    watcher fingerprint:
      - "tracker_timeout"      — TrackerTimeoutError (subprocess timeout)
      - "tracker_not_configured" — TrackerNotConfiguredError
      - "tracker_auth_failed"  — TrackerAuthError (401/403 credential error)
      - "tracker_failed"       — generic TrackerError
      - "project_error"        — ProjectError fallback

    The returned class collapses every report with the same class to one
    task in the dedup window, regardless of which project/subcommand
    surfaced the failure.
    """
    if isinstance(exc, TrackerTimeoutError):
        return "tracker_timeout"
    if isinstance(exc, TrackerNotConfiguredError):
        return "tracker_not_configured"
    if isinstance(exc, TrackerAuthError):
        return "tracker_auth_failed"
    if isinstance(exc, TrackerError):
        return "tracker_failed"
    return "project_error"


DEFAULT_SERVICE_STATE_PATH = ".oompah/service_state.json"


def _state_key(state: str | None) -> str:
    """Normalize tracker status spelling for internal comparisons."""
    return canonicalize_status(state).strip().lower().replace("-", "_").replace(" ", "_")


_WORKTREE_CLEANUP_STATES: tuple[str, ...] = (MERGED, ARCHIVED)
_WORKTREE_CLEANUP_STATE_KEYS: frozenset[str] = frozenset(
    _state_key(state) for state in _WORKTREE_CLEANUP_STATES
)
_EPIC_REVIEW_REPAIR_STATUSES: frozenset[str] = frozenset(
    {NEEDS_CI_FIX, NEEDS_REBASE}
)
_EPIC_REVIEW_REPAIR_RUNNING_STATUSES: frozenset[str] = frozenset(
    {NEEDS_CI_FIX, NEEDS_REBASE, IN_PROGRESS}
)
_EPIC_REVIEW_REPAIR_LABELS: frozenset[str] = frozenset(
    {"ci-fix", "merge-conflict"}
)
_EPIC_REVIEW_READY_CHILD_STATES: frozenset[str] = frozenset(
    {IN_REVIEW, DONE, MERGED, ARCHIVED}
)


def _is_cleanable_worktree_state(state: str | None) -> bool:
    """Return True when a task state is safe for automatic worktree removal."""
    return _state_key(state) in _WORKTREE_CLEANUP_STATE_KEYS


def _is_epic_issue(issue: Issue) -> bool:
    """Return True when *issue* represents an epic rollup task."""
    if (issue.issue_type or "").strip().lower() == "epic":
        return True
    return any(str(label).strip().lower() == "epic" for label in issue.labels or [])


def _terminal_state_keys(terminal_states: list[str] | tuple[str, ...]) -> set[str]:
    """Return canonical terminal status keys including legacy aliases."""
    keys = {_state_key(s) for s in terminal_states}
    keys.update({_state_key(DONE), _state_key(MERGED), _state_key(ARCHIVED)})
    keys.add(_state_key("closed"))
    return keys


def _dispatch_active_state_names(active_states: list[str] | tuple[str, ...]) -> list[str]:
    """Return configured dispatch-active states excluding pre-work intake states."""
    return [s for s in active_states if canonicalize_status(s) != PROPOSED]


def _dispatch_active_state_keys(active_states: list[str] | tuple[str, ...]) -> set[str]:
    """Return dispatch-active state keys excluding pre-work intake states."""
    return {_state_key(s) for s in _dispatch_active_state_names(active_states)}


def _is_terminal_state(state: str | None, terminal_states: list[str] | tuple[str, ...]) -> bool:
    """Return True when a tracker state is terminal in canonical oompah terms."""
    return is_terminal_status(state) or _state_key(state) in _terminal_state_keys(terminal_states)


def _configured_in_progress_state(active_states: list[str]) -> str:
    """Return the tracker-native status oompah treats as in-progress."""
    return IN_PROGRESS


# Signatures of ACP-backend *launch* failures: the agent process never began
# task turns (vs. failing mid-task). These are provider-level and warrant
# failing over to the next dispatch candidate rather than a terminal exit.
_ACP_LAUNCH_FAILURE_PHRASES: tuple[str, ...] = (
    "argument list too long",          # E2BIG execing the CLI (oversized argv)
    "failed to start claude",          # SDK CLIConnectionError on connect
    "cliconnectionerror",
    "clinotfounderror",
    "cli path not resolved",
    "not installed",                   # SDK/backend dependency missing
    "extension not available",         # codex CLI extension missing
    "failed to start a session",
    "failed to start",
)

# After filing a conflict-driven rebase task for an epic, suppress re-filing for
# this long so a completed rebase's force-push has time to settle and the forge
# can recompute the PR's mergeability (otherwise duplicates pile up each tick).
# Short enough to retry if the rebase genuinely didn't resolve the conflict.
_EPIC_REBASE_REFILE_COOLDOWN_S: float = 600.0


def _is_acp_launch_failure(error_msg: str | None) -> bool:
    """True when an ACP session's error string looks like a launch/startup
    failure (process never began task turns), as opposed to a task-level
    error. Used to decide whether to fail over to the next candidate."""
    if not error_msg:
        return False
    low = error_msg.lower()
    return any(phrase in low for phrase in _ACP_LAUNCH_FAILURE_PHRASES)


# Phrases that identify credential-related errors in agent retry error strings.
# Kept narrow to avoid false positives on e.g. HTTP 403 permission errors or
# filesystem "access denied" responses that are not credential failures.
_CREDENTIAL_ERROR_PHRASES: tuple[str, ...] = (
    "missing credentials",
    "missing_credentials",
    "authenticationerror",
    "authentication_error",
    "invalid api key",
    "incorrect api key",
    "authentication failed",
    "invalid_api_key",
    "no api key",
    "api key not found",
)


def _is_credential_error(error: str | None) -> bool:
    """Return True when *error* describes a missing or invalid credential.

    Matches common error strings from OpenAI-compatible SDKs and HTTP
    clients without leaking any credential values.  The check is
    case-insensitive and phrase-based so it catches variations like
    ``OpenAIError: Missing credentials`` or ``AuthenticationError: …``.
    """
    if not error:
        return False
    lower = error.lower()
    return any(phrase in lower for phrase in _CREDENTIAL_ERROR_PHRASES)


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
    # Graceful shutdown: wake the dispatch loop so it can exit cleanly
    SHUTDOWN = "shutdown"


class DispatchLane(str, Enum):
    """Lane identifiers for the orchestrator's two work channels.

    The dispatch contract keeps candidate claiming and agent startup on a
    single serialized lane (DISPATCH), while non-critical maintenance sweeps
    run on a separate bounded lane (MAINTENANCE).  Lane names are stable
    string constants used in comments, log messages, and tests so the
    ownership rules are explicit and greppable.

    DISPATCH:
        Serialized, single-owner.  Candidate selection, issue claiming, and
        ``_dispatch()`` run exclusively here.  Concurrent wakeups block until
        the active pass completes (guarded by ``_dispatch_lane_lock``).

    MAINTENANCE:
        Bounded concurrency.  Non-critical sweeps — staleness checks, rebase
        filing, orphan reset, watchdog, and repo self-heal — run here.
        Maintenance work does **not** hold the dispatch lock except where its
        output is required for correctness before the dispatch pass runs (e.g.
        blocker pre-resolution happens before candidate selection but is still
        part of the serialized dispatch pass).
    """

    DISPATCH = "dispatch"
    MAINTENANCE = "maintenance"


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


class ProviderStartupError(Exception):
    """A provider-level startup failure that may be retried with the next dispatch candidate.

    Raised before the agent worker actually starts executing task turns.
    :meth:`~Orchestrator._run_worker` catches this and tries the next
    :class:`DispatchTarget` in the ordered candidate list.  Non-provider
    task failures (bugs in the agent, task-level errors) should NOT use
    this exception — they must propagate normally so the existing
    retry/escalation machinery handles them.

    Attributes:
        candidate_key:  Human-readable ``provider_id/model`` string for
                        logging (e.g. ``"openai/gpt-4o"``).
        reason:         Short machine-readable reason code
                        (e.g. ``"no_model"``, ``"invalid_model"``).
    """

    def __init__(
        self,
        message: str,
        candidate_key: str = "",
        reason: str = "startup_failed",
    ) -> None:
        super().__init__(message)
        self.candidate_key = candidate_key
        self.reason = reason


@dataclass
class DispatchTarget:
    """A resolved provider/model candidate for a single dispatch attempt.

    Produced by :meth:`~Orchestrator._resolve_dispatch_targets` before
    the worker is launched.  Workers receive the target explicitly so
    they do not re-resolve the provider/model from the role config (which
    would always return the *first* candidate, defeating failover).

    Attributes:
        role_name:      The role this target was drawn from, or ``None``
                        for legacy profile-level targets.
        provider:       Resolved :class:`~oompah.models.ModelProvider`.
        model:          Model name string, or ``None`` for ACP-SDK-managed
                        providers that let the SDK choose.
        candidate_key:  Short ``provider_id/model`` string for log messages.
        source:         Human-readable description of where this target
                        came from (e.g. ``"role:fast[0]"``,
                        ``"profile.provider_id"``, ``"default"``).
        candidate:      The original :class:`~oompah.roles.Candidate`
                        object; ``None`` for legacy single-provider paths.
                        Used by :meth:`~Orchestrator._run_worker` to
                        record usage via :class:`~oompah.roles.CandidateSelector`.
    """

    role_name: str | None
    provider: Any  # ModelProvider
    model: str | None
    candidate_key: str
    source: str
    candidate: Any | None = None  # oompah.roles.Candidate | None


# ---------------------------------------------------------------------------
# Maintenance lane scheduling controls (TASK-466.4)
# ---------------------------------------------------------------------------


@dataclass
class MaintenanceJobState:
    """Per-job scheduling state for the maintenance lane.

    Tracks in-flight coalescing, throttle timestamps, skip counters, and
    observability status for a named maintenance job.  One instance lives in
    ``Orchestrator._maintenance_jobs[name]`` for every job that has been
    submitted at least once.

    Attributes:
        name:                 Stable job name used in logs and snapshots.
        last_run_monotonic:   ``time.monotonic()`` timestamp of the last run
                              start.  ``None`` if the job has never run.
        next_run_monotonic:   Earliest ``time.monotonic()`` at which the job
                              may next be scheduled.  Set to
                              ``last_run_monotonic + min_interval_s`` after
                              each completed or failed run.  ``None`` means
                              "run as soon as possible."
        in_flight:            True while a run is currently executing.  A
                              second request while ``in_flight`` is coalesced
                              (dropped) and counted in ``skip_count``.
        skip_count:           Number of times this job was skipped — either
                              because it was already in flight, because
                              ``next_run_monotonic`` was in the future, or
                              because the dispatch lane was busy.
        run_count:            Number of times the job has successfully started
                              (including runs that subsequently failed).
        last_status:          Human-readable last lifecycle status:
                              ``"never_run"`` | ``"running"`` |
                              ``"completed"`` | ``"failed"`` | ``"skipped"``.
        last_duration_s:      Wall-clock seconds of the most recent run.
                              ``None`` if the job has never completed.
        last_error:           String representation of the last exception, or
                              ``None`` if the last run completed cleanly.
    """

    name: str
    last_run_monotonic: float | None = None
    next_run_monotonic: float | None = None
    in_flight: bool = False
    skip_count: int = 0
    run_count: int = 0
    last_status: str = "never_run"
    last_duration_s: float | None = None
    last_error: str | None = None
    current_deadline: float | None = None  # monotonic deadline for the active run


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


def _is_delivery_conflict_error(error: str) -> bool:
    """Return True when *error* from a blocked delivery indicates a merge conflict.

    Used by :meth:`~Orchestrator._dispatch_delivery_conflict_agents` to
    distinguish deliveries that need a conflict-resolution agent from those
    that are blocked for other reasons (missing commits, push failures, etc.).

    Args:
        error: The ``error`` field from a ``blocked``
            :class:`~oompah.release_delivery_store.ReleaseDelivery`.

    Returns:
        ``True`` when the error message mentions a merge conflict.
    """
    if not error:
        return False
    haystack = error.lower()
    return any(
        needle in haystack
        for needle in (
            "merge conflict",
            "conflict",
            "automatic merge failed",
            "cannot merge",
        )
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

    def __init__(
        self,
        config: ServiceConfig,
        workflow_path: str,
        provider_store: ProviderStore | None = None,
        project_store: ProjectStore | None = None,
        agent_profile_store: AgentProfileStore | None = None,
        role_store: RoleStore | None = None,
        state_path: str | None = None,
        ipc: OrchestratorIPC | None = None,
    ):
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
        # CandidateSelector tracks per-role last-used timestamps so the
        # round-robin strategy can pick the least-recently-used candidate.
        # The usage file lives next to the service-state file so it shares
        # the same directory isolation in tests.
        _state_dir = os.path.dirname(state_path or DEFAULT_SERVICE_STATE_PATH) or "."
        self._candidate_selector = CandidateSelector(
            path=os.path.join(_state_dir, "role_usage.json")
        )
        self._state_path = state_path or DEFAULT_SERVICE_STATE_PATH
        self.state = OrchestratorState(
            poll_interval_ms=config.poll_interval_ms,
            max_concurrent_agents=config.max_concurrent_agents,
        )
        # Legacy single tracker (used when no projects configured)
        self.tracker = self._new_tracker()
        # Per-project trackers, keyed by project_id
        self._project_trackers: dict[str, TrackerProtocol] = {}
        # Per-project branch-to-issue index: maps work_branch → identifier.
        # Built lazily the first time _resolve_task_for_branch needs it for
        # a project and cleared with tracker read caches each tick so the
        # index stays consistent with the tracker's view of open issues.
        # (TASK-462.1)
        self._branch_indexes: dict[str, dict[str, str]] = {}
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
        self._alerts: list[
            dict[str, str]
        ] = []  # {"level": "warning", "message": "..."}
        self._rate_limit_until: float = 0.0  # epoch time until which dispatch is paused
        # Throttle for _auto_archive: it does a full-corpus read per project
        # but only ever acts on issues closed >= _ARCHIVE_DAYS ago, so it
        # needn't run every tick. monotonic() of the last run; None = never.
        self._last_auto_archive_monotonic: float | None = None
        self._started_monotonic: float = time.monotonic()
        state_data = self._load_state()
        cursors = state_data.get("maintenance_cursors", {})
        self._maintenance_cursors: dict[str, str | None] = (
            dict(cursors) if isinstance(cursors, dict) else {}
        )
        self._maintenance_status: dict[str, Any] = {}
        self._last_tick_metrics: dict[str, Any] = {}
        self._last_dispatch_metrics: dict[str, Any] = {}
        self._dispatch_pending_event_keys: set[str] = set()
        self._dispatch_pending_coalesced_counts: dict[str, int] = {}
        self._dispatch_event_lock = threading.Lock()
        self._dispatch_events_coalesced = 0
        self._dispatch_loop: asyncio.AbstractEventLoop | None = None
        # EventBus: typed pub/sub for internal event-driven communication.
        # The legacy _observers/_state_only_observers/_activity_observers lists
        # are kept for backward compatibility with server.py, but internally
        # the EventBus is the canonical dispatch mechanism.
        self.event_bus: EventBus = EventBus()
        # Release addendums have their own durable queue.  A ready event is a
        # prompt wake-up only; the queue's metadata scan remains authoritative
        # after missed events or process restarts.
        self.event_bus.subscribe(
            EventType.RELEASE_ADDENDUM_READY, self._on_release_addendum_ready
        )
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
        # Dispatch-loop heartbeat staleness detection (lesserevil/oompah#305).
        # Monotonic timestamp when staleness was first detected. 0.0 means
        # either not yet stale or we have never completed a tick.
        self._dispatch_stale_detected_at: float = 0.0
        # True once automatic loop recovery has been requested (prevents
        # duplicate restart requests on consecutive supervise iterations).
        self._dispatch_loop_recovery_requested: bool = False
        # Timestamp (monotonic) of the last managed-checkout self-heal pass.
        # Drives the periodic ensure_repo_sound() sweep so checkouts can't
        # silently drift/wedge between restarts. 0.0 => never run yet.
        self._last_repo_heal: float = 0.0
        # Maintenance lane job status (TASK-466.1).
        # Populated by _maybe_heal_repos() so operators can see when the
        # maintenance lane last ran and whether it encountered errors.
        # Exposed via get_snapshot() under the "maintenance" key.
        self._last_heal_at: float = 0.0           # monotonic; 0.0 = never run
        self._heal_error_last: str | None = None   # most recent heal error, or None
        self._last_cleanup_at: float = 0.0         # monotonic; 0.0 = never run
        self._cleanup_count_last: int = 0          # worktrees removed in last run
        self._cleanup_error_last: str | None = None  # most recent cleanup error, or None
        # Running maintenance executor future so _tick() can fire-and-forget
        # without accumulating unbounded concurrent maintenance runs.
        self._maintenance_future: "asyncio.Future[None] | None" = None
        # Dedicated future for epic maintenance (step 5c) so it does not
        # compete for the same coalescing gate as the step-5b heal/cleanup
        # jobs.  Fire-and-forget: a new run starts only when the previous one
        # has finished.
        self._epic_maintenance_future: "asyncio.Future[None] | None" = None
        # Per-project threading locks for epic maintenance jobs (TASK-466.3).
        # Serialises epic close/PR/staleness/rebase/orphan-reset on the same
        # project so two concurrent maintenance sweeps (e.g. from a tick burst)
        # cannot corrupt per-epic git state or tracker state concurrently.
        # Lazily populated on first access via _get_project_maintenance_lock().
        self._epic_maintenance_project_locks: dict[str, threading.Lock] = {}
        # Dedicated thread pool for tick operations so they don't compete
        # with agent tool-execution threads on the default pool.
        self._tick_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tick")
        # Watchdog state
        self._last_watchdog_run: float = 0.0
        self._watchdog_interval_s: float = 300.0  # 5 minutes
        self._last_candidates: list[Issue] = []
        # Maintenance lane scheduling state (TASK-466.4).
        # Maps job name → MaintenanceJobState for in-flight coalescing,
        # skip counters, throttle timestamps, and observability.
        self._maintenance_jobs: dict[str, MaintenanceJobState] = {}
        self._orphan_reset_counts: dict[str, int] = {}
        self._yolo_limbo_ticks: dict[str, int] = {}
        self._last_emitted_reviews_summary: dict[str, int] | None = None
        # YOLO repo-config errors: keyed by (project_id, review_id) →
        # {"msg": str, "fingerprint": str}. Surfaced in reviews_summary
        # and the /api/v1/reviews payload; cleared when the review
        # disappears from the cache. (oompah-zlz_2-btf.2)
        self._yolo_repo_config_errors: dict[tuple[str, str], dict[str, str]] = {}
        # De-dup table for already-logged repo-config error fingerprints
        # so identical errors don't spam the log every tick. Keyed on the
        # fingerprint string. (oompah-zlz_2-btf.2)
        self._logged_repo_config_fingerprints: set[str] = set()
        # YOLO orphan-branch recovery tasks: keyed by
        # (project_id, review_id_str, kind) where kind in
        # {"merge-conflict", "ci-fix"} → task identifier created as the
        # manual-recovery hook for a PR whose source branch doesn't
        # match any existing task. Used for idempotency so the YOLO
        # loop doesn't file a fresh duplicate task every tick for the
        # same orphan PR. Cleared when the review leaves the cache.
        # (oompah-zlz_2-975)
        self._yolo_orphan_recovery_tasks: dict[tuple[str, str, str], str] = {}
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
        # WatchdogPattern.pattern_key → identifier of the filed task.
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
        # path so that previously filed transient-error tasks can close
        # themselves automatically.
        self._error_watchers: dict[str | None, ErrorWatcher] = {}

        # Epic rebase outcome tracking (oompah-zlz_2-82dr.3).
        # Maps epic identifier -> EpicRebaseStateEntry.  Persisted
        # across restarts via service_state.json so the orchestrator
        # doesn't lose "rebase already in progress" on restart.
        self._epic_rebase_states: dict[str, EpicRebaseStateEntry] = {}
        self._restore_epic_rebase_states()
        # Per-epic cooldown (monotonic ts of last conflict-driven rebase task
        # filed) so YOLO doesn't re-file duplicates while a force-pushed rebase
        # is still settling and the forge hasn't recomputed PR mergeability.
        self._epic_rebase_filed_at: dict[str, float] = {}

        # Fine-grained tick telemetry (TASK-465.1).
        # Stores the timing breakdown of the most-recently completed _tick()
        # call so the dashboard snapshot can surface per-substep latency
        # without requiring the caller to hold a reference to the tick future.
        # Keys: top-level phase names (reconcile_ms, reviews_ms, dispatch_ms,
        # yolo_ms, archive_ms, merged_ms, watchdog_ms, heal_ms, total_ms) plus
        # a nested "dispatch_substeps" dict with per-substep ms timings.
        # Empty until the first tick completes.
        self._last_tick_timings: dict[str, object] = {}

        # Dispatch lane serialization contract (TASK-465.2).
        # _dispatch_lane_lock serializes the DISPATCH lane: only one
        # _handle_dispatch_needed() pass can run at a time, ensuring
        # candidate selection and _dispatch() are single-owner.
        # See DispatchLane for the full contract documentation.
        self._dispatch_lane_lock: asyncio.Lock = asyncio.Lock()

        # Tick-event coalescing counter (TASK-465.2).
        # Counts events that were drained from the dispatch queue and coalesced
        # into the current tick so slow-tick logs can report burst size.
        self._last_coalesced_event_count: int = 0
        # ---- Bounded per-project refresh infrastructure (TASK-467.2) ----
        # Per-project semaphores for bounded concurrency. Created on-demand
        # when a project is first refreshed.
        self._project_semaphores: dict[str, asyncio.Semaphore] = {}
        # Per-project stale caches with timestamps. Keyed by project_id.
        # Each cache entry is a tuple of (data, timestamp_ms).
        self._stale_caches: dict[str, dict[str, tuple[Any, float]]] = {}
        # Per-project refresh metrics for diagnostics.
        # project_id -> {operation: {last_duration_ms, timeout_count, success_count, last_error}}
        self._project_refresh_metrics: dict[str, dict[str, dict[str, Any]]] = {}
        # Lock for thread-safe stale cache updates.
        self._stale_cache_lock = threading.Lock()

        # Surface the agent.profiles drift alert (oompah-zlz_2-hye) so
        # the dashboard shows a banner whenever WORKFLOW.md still has a
        # stale agent.profiles block that disagrees with the persisted
        # store. Same channel as auto-update warnings.
        self._arm_profile_drift_alert()

        # IPC layer for multi-process service split (TASK-469.5.1).
        # When ipc is passed explicitly (tests / custom startup), use it.
        # Otherwise try to pick up the process-level singleton from the
        # OOMPAH_IPC_DB_PATH env var.  If neither is configured, stays None
        # and the orchestrator operates in single-process / combined mode.
        self._ipc: OrchestratorIPC | None = ipc if ipc is not None else get_ipc()

        # --- Mid-run comment delivery (OOMPAH-211) ---
        # Per-issue asyncio.Queue for comments pending delivery to a
        # running ACP agent. Keyed by issue_id. Created when an ACP
        # worker starts, removed when it exits.
        self._agent_comment_queues: dict[str, asyncio.Queue] = {}
        # Idempotency: set of comment_ids already delivered per issue_id.
        # Prevents double-delivery if deliver_comment_to_running_agent is
        # called twice with the same comment_id.
        self._agent_delivered_comment_ids: dict[str, set[str]] = {}
        # Audit log: list of delivery records per issue_id. Each record:
        #   {"ts": float, "comment_id": str|None, "text_preview": str,
        #    "status": "queued"|"fallback"}
        self._agent_comment_delivery_log: dict[str, list[dict]] = {}

    # --- Bounded per-project refresh helpers (TASK-467.2) ---

    def _get_project_semaphore(self, project_id: str) -> asyncio.Semaphore:
        """Get or create a semaphore for a project's refresh operations."""
        if project_id not in self._project_semaphores:
            max_concurrent = self.config.project_refresh_max_concurrent
            self._project_semaphores[project_id] = asyncio.Semaphore(max_concurrent)
        return self._project_semaphores[project_id]

    def _get_stale_cache(self, project_id: str, operation: str) -> Any | None:
        """Retrieve stale cached data for a project operation if within TTL."""
        ttl_ms = self.config.project_stale_cache_ttl_ms
        if ttl_ms <= 0:
            return None
        with self._stale_cache_lock:
            project_cache = self._stale_caches.get(project_id, {})
            if operation in project_cache:
                data, timestamp_ms = project_cache[operation]
                age_ms = (time.time() * 1000) - timestamp_ms
                if age_ms <= ttl_ms:
                    logger.debug(
                        "Using stale cache for project %s operation %s (age=%.0fms)",
                        project_id, operation, age_ms
                    )
                    return data
                else:
                    # Expired - remove it
                    del project_cache[operation]
                    if not project_cache:
                        self._stale_caches.pop(project_id, None)
        return None

    def _set_stale_cache(self, project_id: str, operation: str, data: Any) -> None:
        """Store fresh data in the stale cache for a project operation."""
        with self._stale_cache_lock:
            if project_id not in self._stale_caches:
                self._stale_caches[project_id] = {}
            self._stale_caches[project_id][operation] = (data, time.time() * 1000)

    def _record_refresh_metric(
        self,
        project_id: str,
        operation: str,
        duration_ms: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Record refresh metrics for diagnostics."""
        if project_id not in self._project_refresh_metrics:
            self._project_refresh_metrics[project_id] = {}
        if operation not in self._project_refresh_metrics[project_id]:
            self._project_refresh_metrics[project_id][operation] = {
                "last_duration_ms": 0.0,
                "timeout_count": 0,
                "success_count": 0,
                "last_error": None,
            }
        m = self._project_refresh_metrics[project_id][operation]
        m["last_duration_ms"] = duration_ms
        if success:
            m["success_count"] += 1
            m["last_error"] = None
        else:
            m["timeout_count"] += 1
            m["last_error"] = error

    async def _run_bounded_refresh(
        self,
        project_id: str,
        operation: str,
        coro_factory,
        *,
        timeout_ms: int | None = None,
    ) -> tuple[Any, bool]:
        """Run a project-scoped refresh operation with bounded concurrency and timeout.

        Args:
            project_id: The project identifier (or "legacy" for global tracker).
            operation: Operation name for metrics/cache (e.g. "candidates", "reviews").
            coro_factory: Async callable that returns the fresh data.
            timeout_ms: Override timeout in milliseconds (None = use config default).

        Returns:
            Tuple of (data, is_fresh) where is_fresh is True if data came from
            the live operation, False if it came from stale cache.
        """
        timeout_ms = timeout_ms or self.config.project_refresh_timeout_ms
        semaphore = self._get_project_semaphore(project_id)
        start = time.monotonic()

        # If timeout is 0, disable timeout entirely
        has_timeout = timeout_ms > 0
        timeout_s = timeout_ms / 1000.0 if has_timeout else None

        async def _run_with_semaphore():
            async with semaphore:
                if has_timeout:
                    return await asyncio.wait_for(coro_factory(), timeout=timeout_s)
                else:
                    return await coro_factory()

        try:
            data = await _run_with_semaphore()
            duration_ms = (time.monotonic() - start) * 1000
            self._record_refresh_metric(project_id, operation, duration_ms, True)
            self._set_stale_cache(project_id, operation, data)
            return data, True
        except asyncio.TimeoutError:
            duration_ms = (time.monotonic() - start) * 1000
            error = f"timeout after {timeout_ms}ms"
            logger.warning(
                "Project %s operation %s timed out after %.0fms, using stale cache",
                project_id, operation, duration_ms
            )
            self._record_refresh_metric(project_id, operation, duration_ms, False, error)
            stale = self._get_stale_cache(project_id, operation)
            return stale if stale is not None else [], False
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Project %s operation %s failed after %.0fms: %s, using stale cache",
                project_id, operation, duration_ms, exc
            )
            self._record_refresh_metric(project_id, operation, duration_ms, False, error)
            stale = self._get_stale_cache(project_id, operation)
            return stale if stale is not None else [], False

    def _arm_profile_drift_alert(self) -> None:
        """Add or clear the profile-drift alert based on config state.

        Idempotent — call once at __init__ and again on every
        reload_config, so a fresh WORKFLOW.md edit either raises or
        silences the dashboard banner without restart.
        """
        # Always drop any previously-armed drift alert before re-checking.
        self._alerts = [a for a in self._alerts if a.get("source") != "profile_drift"]
        if getattr(self.config, "agent_profiles_drift", False):
            self._alerts.append(
                {
                    "level": "warning",
                    "source": "profile_drift",
                    "message": (
                        "WORKFLOW.md agent.profiles block detected and "
                        "differs from persisted profile store — using the "
                        "persisted store. Delete the agent.profiles "
                        "section from WORKFLOW.md to clear this warning."
                    ),
                }
            )

    def _load_state(self) -> dict:
        """Load persisted service state from disk."""
        if not os.path.exists(self._state_path):
            return {}
        try:
            with open(self._state_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to load service state from %s: %s", self._state_path, exc
            )
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
                persisted_cost,
                persisted_kind,
                elapsed,
                remaining,
            )

    def _restore_epic_rebase_states(self) -> None:
        """Restore persisted epic rebase states on startup.

        Loads the ``epic_rebase_states`` dict from ``service_state.json``
        and re-hydrates it into ``self._epic_rebase_states``.  Entries
        older than 24 h are dropped so a stale ``REBASING`` entry from
        a crashed process doesn't block rebase dispatch forever.
        """
        data = self._load_state()
        raw = data.get("epic_rebase_states")
        if not raw or not isinstance(raw, dict):
            return
        now = time.time()
        cutoff = now - 86400.0  # 24 hours
        restored: dict[str, EpicRebaseStateEntry] = {}
        for epic_id, entry_dict in raw.items():
            if not isinstance(entry_dict, dict):
                continue
            updated_at = float(entry_dict.get("updated_at", 0) or 0)
            if updated_at < cutoff:
                logger.debug(
                    "Dropping stale epic rebase state for %s (age=%.0fh)",
                    epic_id,
                    (now - updated_at) / 3600.0,
                )
                continue
            try:
                restored[epic_id] = EpicRebaseStateEntry.from_dict(entry_dict)
            except Exception as exc:
                logger.debug(
                    "Failed to restore epic rebase state for %s: %s",
                    epic_id,
                    exc,
                )
        self._epic_rebase_states = restored
        if restored:
            logger.info(
                "Restored %d epic rebase state(s) from disk",
                len(restored),
            )

    def _persist_epic_rebase_states(self) -> None:
        """Write ``self._epic_rebase_states`` to ``service_state.json``."""
        payload = {
            epic_id: entry.to_dict()
            for epic_id, entry in self._epic_rebase_states.items()
        }
        self._save_state(epic_rebase_states=payload)

    def _save_state(self, **updates: object) -> None:
        """Persist service state to disk, merging with existing state."""
        try:
            data = self._load_state()
            data.update(updates)
            os.makedirs(os.path.dirname(self._state_path) or ".", exist_ok=True)
            with open(self._state_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as exc:
            logger.warning(
                "Failed to save service state to %s: %s", self._state_path, exc
            )

    def _save_paused_state(self) -> None:
        """Persist paused state to disk."""
        self._save_state(paused=self._paused)

    def _set_maintenance_cursor(self, name: str, value: str | None) -> None:
        cursors = getattr(self, "_maintenance_cursors", {})
        if value is None:
            cursors.pop(name, None)
        else:
            cursors[name] = value
        self._maintenance_cursors = cursors
        self._save_state(maintenance_cursors=cursors)

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
            logger.warning("reload_config: agent profile store reload failed: %s", exc)
        self._prompt_template = prompt_template
        self.state.poll_interval_ms = config.poll_interval_ms
        self.state.max_concurrent_agents = config.max_concurrent_agents
        self.tracker = self._new_tracker()
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
        logger.info(
            "Config reloaded poll_interval_ms=%d full_sync_interval_ms=%d max_agents=%d",
            config.poll_interval_ms,
            config.full_sync_interval_ms,
            config.max_concurrent_agents,
        )

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
            "Agent profiles reload queued (source=%s, count=%d) — applies at next tick",
            source,
            len(snapshot),
        )
        # Wake the dispatch loop so the swap takes effect immediately rather
        # than waiting for the next safety-net full-sync. The loop will call
        # _apply_pending_agent_profiles() at the start of _tick().
        self._post_event(
            DispatchEvent(
                event_type=DispatchEventType.REFRESH_REQUESTED,
                payload={"reason": f"agent_profiles_reload:{source}"},
            )
        )

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
            before_names,
            after_names,
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
        # Terminate all running agents (keep workspaces for resume).
        # Use get_running_loop() so we don't accidentally create a new
        # event loop when called from a synchronous context (e.g. tests).
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._terminate_all_running())
        except RuntimeError:
            # No running event loop — no active agents to terminate.
            pass
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
        self._set_refresh_requested()
        self._post_event(
            DispatchEvent(
                event_type=DispatchEventType.REFRESH_REQUESTED,
                payload={"reason": "unpaused"},
            )
        )
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
            logger.info(
                "Draining: %d agent(s) still running, %.0fs remaining",
                remaining,
                deadline - time.monotonic(),
            )
            await asyncio.sleep(2)

        # Save issue IDs of anything still running for re-dispatch
        restart_issues = []
        for issue_id, entry in self.state.running.items():
            restart_issues.append(
                {
                    "issue_id": issue_id,
                    "identifier": entry.issue.identifier if entry.issue else issue_id,
                    "project_id": entry.issue.project_id if entry.issue else None,
                }
            )

        # Merge with any restart_issues saved from a previous graceful_restart
        # call (e.g. the user triggered restart twice before the process exited).
        # Deduplication by issue_id ensures each task is persisted exactly once.
        existing_restart_issues: list[dict] = self._load_state().get(
            "restart_issues", []
        )
        existing_ids = {e["issue_id"] for e in existing_restart_issues}
        new_issues = [
            e for e in restart_issues if e["issue_id"] not in existing_ids
        ]
        merged_restart_issues = existing_restart_issues + new_issues

        if new_issues:
            logger.info(
                "Saving %d undrained issue(s) for re-dispatch after restart "
                "(%d already queued)",
                len(new_issues),
                len(existing_restart_issues),
            )
        elif restart_issues:
            logger.info(
                "All %d undrained issue(s) already queued for restart recovery",
                len(restart_issues),
            )

        # Preserve user's explicit pause across the restart; otherwise
        # come up unpaused so the saved restart_issues can re-dispatch.
        self._save_state(
            paused=was_user_paused,
            restart_issues=merged_restart_issues,
        )

        # Signal the main loop to stop and restart
        self._restart_requested = True
        self._stopping = True
        # Wake the dispatch loop if it's blocked on _dispatch_queue.get()
        self._post_event(
            DispatchEvent(event_type=DispatchEventType.SHUTDOWN)
        )

    @property
    def wants_restart(self) -> bool:
        return self._restart_requested

    def _new_tracker(
        self, cwd: str | None = None,
    ) -> TrackerProtocol:
        """Construct a tracker adapter for the configured tracker.kind.

        The factory is looked up in :data:`oompah.tracker.ADAPTER_REGISTRY`
        using the normalised ``tracker.kind`` from the service config.  An
        unrecognised kind raises :class:`TrackerError`; callers should treat
        that as a configuration error (``validate_dispatch_config`` will have
        already reported it during startup).
        """
        kind = self.config.tracker_kind
        factory = ADAPTER_REGISTRY.get(kind)
        if factory is None:
            registered = sorted(ADAPTER_REGISTRY)
            raise TrackerError(
                f"Unsupported tracker.kind: {kind!r}."
                f" Registered adapters: {registered}"
            )
        return factory(
            active_states=self.config.tracker_active_states,
            terminal_states=self.config.tracker_terminal_states,
            cwd=cwd,
        )

    def _new_tracker_for_project(self, project: "Project") -> TrackerProtocol:
        """Construct a tracker adapter scoped to a specific project.

        Resolves the tracker backend using the project's own ``tracker_kind``
        field when set, falling back to the global service ``tracker_kind``
        when the project has no explicit configuration.

        For ``github_issues`` projects the factory receives the project's
        ``tracker_owner`` and ``tracker_repo`` so each project targets its
        own GitHub task hub rather than reading env vars.

        Raises :class:`TrackerError` when the resolved kind is not registered.
        """
        # Prefer the project-level kind when it is an explicit non-empty string;
        # fall back to the global service kind for projects that have not been
        # configured (tracker_kind is None or has not been set at all).
        _project_kind = project.tracker_kind
        kind: str = (
            _project_kind
            if isinstance(_project_kind, str) and _project_kind
            else self.config.tracker_kind
        )
        factory = ADAPTER_REGISTRY.get(kind)
        if factory is None:
            registered = sorted(ADAPTER_REGISTRY)
            raise TrackerError(
                f"Unsupported tracker.kind {kind!r} for project {project.id!r}."
                f" Registered adapters: {registered}"
            )
        # For GitHub-backed projects pass the project-specific owner/repo so
        # the adapter targets the correct task hub. Never let a project-scoped
        # GitHub tracker fall back to the global GitHub env vars; that leaks one
        # project's issues into another project's board.
        extra: dict[str, object] = {}
        if kind == "github_issues":
            owner = (getattr(project, "tracker_owner", None) or "").strip()
            repo = (getattr(project, "tracker_repo", None) or "").strip()
            if not owner or not repo:
                inferred_owner, inferred_repo = github_owner_repo_from_url(
                    getattr(project, "repo_url", "") or ""
                )
                owner = owner or (inferred_owner or "")
                repo = repo or (inferred_repo or "")
            if not owner or not repo:
                raise TrackerError(
                    "GitHub Issues project "
                    f"{getattr(project, 'id', '<unknown>')!r} requires "
                    "tracker_owner and tracker_repo, or a github.com repo_url "
                    "that oompah can infer them from."
                )
            extra["owner"] = owner
            extra["repo"] = repo
            if getattr(project, "access_token", None):
                extra["access_token"] = project.access_token
            status_label_logins = list(
                getattr(project, "status_label_authorized_logins", []) or []
            )
            status_actor_login = getattr(project, "status_actor_login", None)
            if status_actor_login:
                status_label_logins.append(str(status_actor_login))
            extra["status_label_authorized_logins"] = status_label_logins
        elif kind in ("oompah_md", "oompah.md", "oompah"):
            default_branch = (getattr(project, "default_branch", None) or "").strip()
            if default_branch:
                extra["default_branch"] = default_branch
        return factory(
            active_states=self.config.tracker_active_states,
            terminal_states=self.config.tracker_terminal_states,
            cwd=project.repo_path,
            **extra,
        )

    def _tracker_for_project(self, project_id: str) -> TrackerProtocol:
        """Get or create the tracker for a project.

        Returns the cached instance when available.  On first access the
        project's ``tracker_kind`` is resolved: projects with an explicit
        ``tracker_kind`` get the corresponding adapter (e.g.
        ``GitHubIssueTracker`` for ``"github_issues"``); projects without
        an explicit kind fall back to the global service ``tracker_kind``
        Cache is project-scoped; ``_project_trackers`` is keyed by
        ``project_id`` so each project has its own instance.

        As a convenience, ``project_id`` may also be a project *name*
        (e.g. ``"coroot"``).  When the ID lookup fails, a secondary
        name-based lookup is attempted so callers that hold the human-
        readable name do not need to resolve it to the internal ID first.
        The tracker cache is always keyed by canonical ID.
        """
        if project_id in self._project_trackers:
            return self._project_trackers[project_id]
        project = self.project_store.get(project_id)
        if not project:
            # Fall back to name-based lookup for callers that supply a
            # human-readable project name instead of the internal ID.
            project = self.project_store.find_by_name(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        tracker = self._new_tracker_for_project(project)
        # Always cache by canonical ID so subsequent lookups hit the fast path.
        self._project_trackers[project.id] = tracker
        return tracker

    def _tracker_for_issue(self, issue: Issue) -> TrackerProtocol:
        """Get the appropriate tracker for an issue."""
        if issue.project_id:
            return self._tracker_for_project(issue.project_id)
        return self.tracker

    def _invalidate_tracker_read_caches(self) -> None:
        """Clear the per-tick task-record cache on every tracker.

        Called at tick start so each tick reads fresh state, then reuses
        that parse across its phases. Best-effort: a tracker without the
        method (e.g. a test double) is skipped.

        Also clears the per-project branch-to-issue index so that the next
        ``_resolve_task_for_branch`` call rebuilds it from fresh issue data.
        """
        trackers = [
            self.tracker,
            *self._project_trackers.values(),
        ]
        for tracker in trackers:
            inval = getattr(tracker, "invalidate_read_cache", None)
            if callable(inval):
                try:
                    inval()
                except Exception:  # noqa: BLE001 — never let cache reset break a tick
                    pass
        # Clear the branch index cache so it is rebuilt next time a branch
        # lookup is needed.  Stale entries would cause lookups to resolve
        # to closed/stale issues after a tick boundary.
        self._branch_indexes.clear()

    def _on_release_addendum_ready(
        self, _event_type: EventType | str, payload: dict[str, Any]
    ) -> None:
        """Wake the event-driven loop when durable release work is approved."""
        self._post_event(
            DispatchEvent(
                event_type=DispatchEventType.REFRESH_REQUESTED,
                payload={"release_addendum_ready": dict(payload)},
            )
        )

    def release_addendum_queue(
        self, project_id: str | None, *, worker_id: str
    ) -> ReleaseAddendumQueue:
        """Build the release-only queue adapter for an executor worker.

        This deliberately returns metadata queue items, not tracker Issues.
        """
        tracker = self._tracker_for_project(project_id) if project_id else self.tracker
        return ReleaseAddendumQueue(
            project_id or "legacy",
            tracker,
            worker_id=worker_id,
            event_bus=self.event_bus,
        )

    def _recover_release_addendum_leases(self) -> int:
        """Periodic durable recovery for workers that died with a lease."""
        projects = self.project_store.list_all()
        queue_specs: list[tuple[str | None, TrackerProtocol]] = []
        if projects:
            for project in projects:
                try:
                    queue_specs.append((project.id, self._tracker_for_project(project.id)))
                except (ProjectError, TrackerError) as exc:
                    logger.warning("Release-addendum recovery skipped project %s: %s", project.id, exc)
        else:
            queue_specs.append((None, self.tracker))

        recovered = 0
        for project_id, tracker in queue_specs:
            try:
                queue = ReleaseAddendumQueue(
                    project_id or "legacy", tracker, worker_id="orchestrator-recovery"
                )
                recovered += len(queue.recover_expired_leases())
            except (TrackerError, ValueError) as exc:
                logger.warning(
                    "Release-addendum recovery failed project_id=%s: %s", project_id, exc
                )
        return recovered

    # ------------------------------------------------------------------
    # Error watcher integration (oompah-zlz_2-0nc)
    # ------------------------------------------------------------------
    def register_error_watcher(
        self, watcher: ErrorWatcher, project_id: str | None = None
    ) -> None:
        """Register an :class:`ErrorWatcher` so the orchestrator can
        ask it to auto-close transient error tasks.

        ``project_id=None`` registers the global / unscoped watcher (the
        one that handles ``logger.error`` records emitted from the
        orchestrator itself and any project-less log file).  Project-
        scoped watchers are registered with their project's id.

        Idempotent: re-registering replaces the previous reference.
        """
        self._error_watchers[project_id] = watcher

    def _error_watchers_for_project(self, project_id: str | None) -> list[ErrorWatcher]:
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

    def _auto_close_transient_errors_for_entry(self, entry: RunningEntry) -> None:
        """Best-effort auto-close of error tasks tied to ``entry.issue``.

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
                        "Auto-closed %d transient error task(s) for %s: %s",
                        len(closed),
                        entry.identifier,
                        ", ".join(closed),
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug(
                    "auto_close_for_issue failed for %s: %s",
                    entry.identifier,
                    exc,
                )

    @property
    def is_paused(self) -> bool:
        return self._paused

    def invalidate_merged_branches(self) -> None:
        """Mark the merged-branches cache as stale (called by webhook handler)."""
        self._merged_branches_dirty = True
        with self._stale_cache_lock:
            for project_cache in self._stale_caches.values():
                project_cache.pop("merged_branches", None)

    def request_refresh(self) -> None:
        """Request an immediate poll+reconciliation cycle."""
        self._set_refresh_requested()
        self._post_event(
            DispatchEvent(
                event_type=DispatchEventType.REFRESH_REQUESTED,
                payload={"reason": "api_request"},
            )
        )

    def _cleanup_stale_project_worktree_dirs(
        self, project: Any, limit: int
    ) -> tuple[int, bool]:
        """Remove stale managed worktree directories when ProjectStore supports it."""
        if limit <= 0:
            return 0, True
        cleanup = getattr(type(self.project_store), "cleanup_stale_worktree_dirs", None)
        if cleanup is None:
            return 0, False
        try:
            return self.project_store.cleanup_stale_worktree_dirs(
                project.id, limit=limit
            )
        except ProjectError as exc:
            logger.warning(
                "Stale worktree directory cleanup failed for project %s: %s",
                project.name,
                exc,
            )
            return 0, False

    def _cleanup_terminal_worktrees(self, projects: list | None = None) -> int:
        """Remove workspaces/worktrees for issues safe to discard.

        Done worktrees are intentionally preserved because they may still hold
        conflict state or other context needed for follow-up. Only Merged and
        Archived tasks are cleanable.

        Returns the number of successful removals.
        Individual project/tracker/worktree failures are logged and do not stop
        cleanup for other projects.
        """
        cleaned = 0
        limit = getattr(self.config, "worktree_cleanup_batch_size", 25)
        if limit <= 0:
            self._maintenance_status["worktree_cleanup"] = {
                "last_run_at": datetime.now(timezone.utc).isoformat(),
                "cleaned": 0,
                "limit": limit,
                "deferred": True,
            }
            return 0
        last_key = getattr(self, "_maintenance_cursors", {}).get("worktree_cleanup")
        seen_cursor = last_key is None
        last_processed_key = last_key
        if projects is None:
            projects = self.project_store.list_all()
        if projects:
            for project in projects:
                try:
                    tracker = self._tracker_for_project(project.id)
                    terminal_issues = tracker.fetch_issues_by_states(
                        list(_WORKTREE_CLEANUP_STATES)
                    )
                    for issue in terminal_issues:
                        issue_key = f"{project.id}:{issue.identifier}"
                        if not seen_cursor:
                            seen_cursor = issue_key == last_key
                            continue
                        if not _is_cleanable_worktree_state(issue.state):
                            continue
                        if cleaned >= limit:
                            self._set_maintenance_cursor(
                                "worktree_cleanup", last_processed_key
                            )
                            self._maintenance_status["worktree_cleanup"] = {
                                "last_run_at": datetime.now(timezone.utc).isoformat(),
                                "cleaned": cleaned,
                                "limit": limit,
                                "deferred": True,
                                "cursor": last_processed_key,
                            }
                            return cleaned
                        try:
                            if _is_epic_issue(issue) and hasattr(
                                self.project_store, "remove_epic_worktree"
                            ):
                                self.project_store.remove_epic_worktree(
                                    project.id, issue.identifier
                                )
                            else:
                                self.project_store.remove_worktree(
                                    project.id, issue.identifier
                                )
                            cleaned += 1
                            logger.info(
                                "Cleaned terminal worktree project=%s issue=%s",
                                project.name,
                                issue.identifier,
                            )
                        except Exception as exc:
                            logger.warning(
                                "Failed to clean worktree project=%s issue=%s error=%s",
                                project.name,
                                issue.identifier,
                                exc,
                            )
                        last_processed_key = issue_key
                    remaining = limit - cleaned
                    if remaining > 0:
                        stale_cleaned, stale_deferred = (
                            self._cleanup_stale_project_worktree_dirs(
                                project, remaining
                            )
                        )
                        cleaned += stale_cleaned
                        if stale_deferred:
                            self._set_maintenance_cursor(
                                "worktree_cleanup", last_processed_key
                            )
                            self._maintenance_status["worktree_cleanup"] = {
                                "last_run_at": datetime.now(timezone.utc).isoformat(),
                                "cleaned": cleaned,
                                "limit": limit,
                                "deferred": True,
                                "cursor": last_processed_key,
                            }
                            return cleaned
                except (TrackerError, ProjectError) as exc:
                    logger.warning(
                        "Terminal worktree cleanup failed for project %s: %s",
                        project.name,
                        exc,
                    )
        else:
            try:
                terminal_issues = self.tracker.fetch_issues_by_states(
                    list(_WORKTREE_CLEANUP_STATES)
                )
                for issue in terminal_issues:
                    issue_key = f"legacy:{issue.identifier}"
                    if not seen_cursor:
                        seen_cursor = issue_key == last_key
                        continue
                    if not _is_cleanable_worktree_state(issue.state):
                        continue
                    if cleaned >= limit:
                        self._set_maintenance_cursor(
                            "worktree_cleanup", last_processed_key
                        )
                        self._maintenance_status["worktree_cleanup"] = {
                            "last_run_at": datetime.now(timezone.utc).isoformat(),
                            "cleaned": cleaned,
                            "limit": limit,
                            "deferred": True,
                            "cursor": last_processed_key,
                        }
                        return cleaned
                    try:
                        self.workspace_mgr.remove_workspace(issue.identifier)
                        cleaned += 1
                        logger.info(
                            "Cleaned terminal workspace issue_identifier=%s",
                            issue.identifier,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to clean workspace issue_identifier=%s error=%s",
                            issue.identifier,
                            exc,
                        )
                    last_processed_key = issue_key
            except TrackerError as exc:
                logger.warning("Terminal workspace cleanup failed: %s", exc)
        self._set_maintenance_cursor("worktree_cleanup", None)
        self._maintenance_status["worktree_cleanup"] = {
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "cleaned": cleaned,
            "limit": limit,
            "deferred": False,
            "cursor": None,
        }
        return cleaned

    async def startup_cleanup(self) -> None:
        """Remove workspaces/worktrees for issues in terminal states."""
        projects = self.project_store.list_all()
        self._maintenance_status["startup_cleanup"] = {
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "worktree_cleanup_deferred": True,
            "delay_seconds": self.config.maintenance_startup_delay_seconds,
        }

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
                tracker.update_issue(identifier, status=OPEN)
                logger.info(
                "Marked %s as Open for re-dispatch after restart", identifier
                )
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

    # ------------------------------------------------------------------
    # Dispatch-loop heartbeat / staleness detection (lesserevil/oompah#305)
    # ------------------------------------------------------------------

    def is_dispatch_loop_stale(self) -> bool:
        """Return True when the dispatch loop has stopped ticking.

        The loop is considered stale when:
        - At least one tick has completed (``_last_full_sync != 0.0``), AND
        - The elapsed time since the last tick exceeds
          ``full_sync_interval_ms × dispatch_loop_stale_factor``.

        Returns False before the first tick so a slow-starting service does
        not falsely alarm, and also returns False when
        ``dispatch_loop_stale_factor == 0`` (detection disabled).
        """
        factor = self.config.dispatch_loop_stale_factor
        if factor <= 0:
            return False
        if self._last_full_sync == 0.0:
            return False
        threshold_ms = self.config.full_sync_interval_ms * factor
        elapsed_ms = (time.monotonic() - self._last_full_sync) * 1000
        return elapsed_ms >= threshold_ms

    def dispatch_loop_stale_seconds(self) -> float:
        """Return seconds elapsed since the last completed dispatch tick.

        Returns 0.0 before the first tick completes.
        """
        if self._last_full_sync == 0.0:
            return 0.0
        return time.monotonic() - self._last_full_sync

    def _arm_dispatch_stale_alert(self, elapsed_s: float) -> None:
        """Arm (or refresh) the dispatch-loop-stale dashboard alert.

        Idempotent: calling repeatedly only updates the elapsed-time
        message; it does not add duplicate entries.
        """
        source = "dispatch_loop_stale"
        self._alerts = [a for a in self._alerts if a.get("source") != source]
        self._alerts.append(
            {
                "level": "error",
                "source": source,
                "title": "Orchestrator dispatch loop is stale",
                "message": (
                    f"The dispatch loop has not completed a tick in "
                    f"{elapsed_s:.0f}s "
                    f"(threshold: {self.config.full_sync_interval_ms / 1000 * self.config.dispatch_loop_stale_factor:.0f}s). "
                    "Open issues will not be dispatched until the loop recovers. "
                    "Automatic recovery has been attempted."
                ),
            }
        )
        logger.error(
            "Dispatch loop stale: no tick completed in %.0fs "
            "(threshold=%.0fs). Alert armed, recovery queued.",
            elapsed_s,
            self.config.full_sync_interval_ms / 1000 * self.config.dispatch_loop_stale_factor,
        )

    def _clear_dispatch_stale_alert(self) -> None:
        """Clear the dispatch-loop-stale alert if present."""
        source = "dispatch_loop_stale"
        before = len(self._alerts)
        self._alerts = [a for a in self._alerts if a.get("source") != source]
        if len(self._alerts) != before:
            logger.info("Dispatch loop recovered — cleared stale-loop alert.")

    def recover_stale_dispatch_loop(self) -> bool:
        """Attempt to recover a stale dispatch loop.

        Recovery is safe: it uses the existing ``wants_restart`` mechanism
        which the server's ``_supervise`` task already monitors. Before
        requesting restart, ``_save_state`` preserves any running-agent
        issue IDs so they are re-dispatched after the service comes back up.

        Returns True if recovery was requested, False if it was skipped
        (e.g. already requested, or no agents to recover).

        Thread-safe: may be called from the server's supervise task (a
        different thread/event loop from the orchestrator's own loop).
        """
        if self._dispatch_loop_recovery_requested:
            return False  # already requested

        running_count = len(self.state.running)

        if running_count > 0:
            # There are active agents in flight. The stale loop is a problem
            # but killing those agents is worse. Log loudly and arm the alert;
            # the operator must intervene or wait for agents to finish.
            logger.error(
                "Dispatch loop stale but %d agent(s) are active — "
                "skipping auto-restart to avoid killing in-flight work. "
                "Restart manually when agents complete.",
                running_count,
            )
            return False

        logger.warning(
            "Dispatch loop stale with no running agents — "
            "preserving state and requesting service restart for recovery."
        )

        # Save state so issue IDs that were queued/retrying survive restart.
        # paused=False ensures the service comes up dispatching after restart.
        try:
            self._save_state(paused=False, restart_issues=[])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to persist state before stale-loop restart: %s", exc)

        # Signal the Granian supervisor to restart the service.
        self._restart_requested = True
        self._stopping = True
        # Post SHUTDOWN to wake the dispatch queue in case the loop IS alive
        # but blocked waiting on a queue.get().
        try:
            self._post_event(DispatchEvent(event_type=DispatchEventType.SHUTDOWN))
        except Exception:  # noqa: BLE001
            pass  # Best-effort; supervisor restart will handle it regardless.

        self._dispatch_loop_recovery_requested = True
        return True

    def check_and_recover_dispatch_loop(self) -> None:
        """Heartbeat check: arm alert and attempt recovery when the loop is stale.

        Designed to be called periodically from the server's ``_supervise``
        task (or any thread). On each call:

        - If not stale: clear any existing stale alert and reset detection state.
        - If stale and first detection: record detection time, arm alert.
        - If stale and past grace period (1× full_sync_interval_ms of
          continued staleness): attempt ``recover_stale_dispatch_loop()``.
        """
        if not self.is_dispatch_loop_stale():
            self._clear_dispatch_stale_alert()
            self._dispatch_stale_detected_at = 0.0
            self._dispatch_loop_recovery_requested = False
            return

        elapsed_s = self.dispatch_loop_stale_seconds()

        if self._dispatch_stale_detected_at == 0.0:
            self._dispatch_stale_detected_at = time.monotonic()

        # Always arm/refresh the alert so the dashboard shows current elapsed.
        self._arm_dispatch_stale_alert(elapsed_s)

        # After a grace period of continued staleness, trigger recovery.
        grace_s = self.config.full_sync_interval_ms / 1000.0
        time_since_detection = time.monotonic() - self._dispatch_stale_detected_at
        if time_since_detection >= grace_s:
            self.recover_stale_dispatch_loop()

    def _maybe_heal_repos(self) -> None:
        """Periodically drive every managed checkout back to a sound state.

        Delegates to the maintenance lane scheduling gate (:meth:`_run_maintenance_job`)
        so the job participates in in-flight coalescing, interval throttling, skip
        accounting, and observability alongside all other maintenance jobs.

        The actual work is in :meth:`_do_heal_repos`.
        """
        # Honour startup delay: don't run expensive git I/O immediately after
        # the service starts.  This mirrors the HEAD behaviour from TASK-469.2
        # and keeps _maintenance_status visible for dashboard diagnostics.
        startup_delay = getattr(self.config, "maintenance_startup_delay_seconds", 60)
        startup_age = time.monotonic() - self._started_monotonic
        if startup_age < startup_delay:
            self._maintenance_status["repo_heal"] = {
                "last_run_at": None,
                "delayed": True,
                "delay_remaining_seconds": round(startup_delay - startup_age, 1),
            }
            return

        interval_s = self.config.full_sync_interval_ms / 1000.0
        self._run_maintenance_job(
            "repo_heal",
            self._do_heal_repos,
            min_interval_s=interval_s,
        )
        # Back-fill _last_repo_heal for legacy callers that read it directly.
        state = self._maintenance_jobs.get("repo_heal")
        if state and state.last_run_monotonic is not None:
            self._last_repo_heal = state.last_run_monotonic

    def _do_heal_repos(self) -> None:
        """Inner body of _maybe_heal_repos; called with the maintenance gate held.

        Performs managed checkout self-heal (sync_all_sources) only.
        Terminal worktree cleanup is handled by the separate 'worktree_cleanup' job.
        """
        # Record the start time for diagnostics even if we fail early.
        self._last_heal_at = time.monotonic()
        try:
            self.project_store.sync_all_sources()
            self._heal_error_last = None
        except Exception as exc:  # noqa: BLE001
            self._heal_error_last = str(exc)
            logger.warning("Periodic repo self-heal failed: %s", exc)
    def _maybe_cleanup_worktrees(self) -> None:
        """Periodically remove terminal worktrees (merged/archived tasks only).

        Delegates to the maintenance lane scheduling gate (:meth:`_run_maintenance_job`)
        so the job participates in in-flight coalescing, interval throttling, skip
        accounting, and observability alongside all other maintenance jobs.

        The actual work is in :meth:`_do_cleanup_worktrees`.
        """
        interval_s = self.config.full_sync_interval_ms / 1000.0
        self._run_maintenance_job(
            "worktree_cleanup",
            self._do_cleanup_worktrees,
            min_interval_s=interval_s,
        )
        # Back-fill _last_cleanup_at for legacy callers that read it directly.
        state = self._maintenance_jobs.get("worktree_cleanup")
        if state and state.last_run_monotonic is not None:
            self._last_cleanup_at = state.last_run_monotonic

    def _do_cleanup_worktrees(self) -> None:
        """Inner body of _maybe_cleanup_worktrees; called with the maintenance gate held.

        Removes worktrees for tasks in MERGED or ARCHIVED state only.
        Done/conflict worktrees are intentionally preserved.
        """
        projects = self.project_store.list_all()
        if projects:
            try:
                count = self._cleanup_terminal_worktrees(projects)
                self._last_cleanup_at = time.monotonic()
                self._cleanup_count_last = count
                self._cleanup_error_last = None
            except Exception as exc:  # noqa: BLE001
                self._cleanup_error_last = str(exc)
                logger.warning("Terminal worktree cleanup failed during maintenance: %s", exc)

    def _run_step5b_maintenance(self) -> None:
        """Combined fire-and-forget maintenance wrapper for ``_tick`` step 5b.

        Runs the following maintenance jobs back-to-back, each individually gated
        by :meth:`_run_maintenance_job` so in-flight coalescing, interval throttling,
        and observability tracking apply independently:

        1. :meth:`_maybe_heal_repos` — managed-checkout self-heal.
        2. :meth:`_maybe_cleanup_worktrees` — terminal worktree removal.
        3. :meth:`_auto_archive` — archive closed issues older than _ARCHIVE_DAYS.
        4. :meth:`_maybe_open_deferred_done_reviews` — hand Done work with
           unmerged branches to review when capacity frees.
        5. :meth:`_maybe_run_merged_labels` — label merged issues/epics + reconcile
           stale In Review tasks.
        6. :meth:`_maybe_run_release_pick_reconciliation` — reconcile release-pick
           metadata and backport tasks.
        7. :meth:`_maybe_sync_github_issue_intake` — import external GitHub intake
           into native tasks and mirror native status changes back to GitHub.

        Submitted to ``_tick_pool`` by :meth:`_tick` and **not** awaited so it
        does not contribute to dispatch tick latency.
        """
        self._maybe_heal_repos()
        self._maybe_cleanup_worktrees()
        self._auto_archive()
        self._maybe_open_deferred_done_reviews()
        self._maybe_run_merged_labels()
        self._maybe_run_release_pick_reconciliation()
        self._maybe_sync_github_issue_intake()

    def _dispatch_event_key(self, event: DispatchEvent) -> str:
        return str(event.event_type)

    def _running_loop(self) -> asyncio.AbstractEventLoop | None:
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def _set_refresh_requested(self) -> None:
        loop = self._dispatch_loop
        if loop is not None and loop.is_running() and self._running_loop() is not loop:
            loop.call_soon_threadsafe(self._refresh_requested.set)
            return
        self._refresh_requested.set()

    def _mark_dispatch_event_dequeued(self, event: DispatchEvent) -> int:
        key = self._dispatch_event_key(event)
        lock = getattr(self, "_dispatch_event_lock", None)
        pending = getattr(self, "_dispatch_pending_event_keys", None)
        counts = getattr(self, "_dispatch_pending_coalesced_counts", None)
        if lock is None or pending is None or counts is None:
            return 0
        with lock:
            pending.discard(key)
            return counts.pop(key, 0)

    def _post_event_on_loop(self, event: DispatchEvent) -> None:
        """Put an event onto the dispatch queue from its owning event loop."""
        key = self._dispatch_event_key(event)
        lock = getattr(self, "_dispatch_event_lock", None)
        pending = getattr(self, "_dispatch_pending_event_keys", None)
        if lock is not None and pending is not None:
            with lock:
                if key in pending:
                    self._dispatch_events_coalesced = (
                        getattr(self, "_dispatch_events_coalesced", 0) + 1
                    )
                    counts = getattr(self, "_dispatch_pending_coalesced_counts", None)
                    if counts is not None:
                        counts[key] = counts.get(key, 0) + 1
                    logger.debug("Coalesced pending dispatch event %s", key)
                    return
                pending.add(key)
        try:
            self._dispatch_queue.put_nowait(event)
        except asyncio.QueueFull:
            if lock is not None and pending is not None:
                with lock:
                    pending.discard(key)
            # The queue is unbounded, so this should never happen in practice.
            logger.warning(
                "Dispatch queue unexpectedly full; dropping event %s", event.event_type
            )

    def _post_event(self, event: DispatchEvent) -> None:
        """Put an event onto the dispatch queue (thread-safe, non-blocking)."""
        loop = self._dispatch_loop
        if loop is not None and loop.is_running() and self._running_loop() is not loop:
            loop.call_soon_threadsafe(self._post_event_on_loop, event)
            return
        self._post_event_on_loop(event)

    def stop_threadsafe(self):
        """Schedule ``stop()`` on the orchestrator loop from another thread."""
        loop = self._dispatch_loop
        if loop is None or not loop.is_running() or self._running_loop() is loop:
            return None
        return asyncio.run_coroutine_threadsafe(self.stop(), loop)

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
        self._dispatch_loop = asyncio.get_running_loop()
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
            p.name
            for p in self.config.agent_profiles
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

                logger.debug(
                    "Dispatch loop received event: %s issue_id=%s",
                    event.event_type,
                    event.issue_id,
                )

                coalesced = self._mark_dispatch_event_dequeued(event)
                while True:
                    try:
                        extra = self._dispatch_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    coalesced += 1
                    coalesced += self._mark_dispatch_event_dequeued(extra)
                # Track coalesced count for dashboard snapshots (TASK-465.2).
                self._last_coalesced_event_count = coalesced
                if coalesced:
                    logger.debug("Coalesced %d dispatch event(s)", coalesced)

                # All current event types still result in a full _tick(), but
                # bursts are coalesced so one worker-exit storm cannot queue a
                # long train of identical world scans.
                await _run_tick()

        finally:
            full_sync_task.cancel()
            try:
                await full_sync_task
            except (asyncio.CancelledError, Exception):
                pass
            self._dispatch_loop = None

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
        self._post_event(DispatchEvent(event_type=DispatchEventType.SHUTDOWN))
        logger.info("Orchestrator stopped")

    async def _tick(self) -> None:
        """One poll-and-dispatch cycle.

        Delegates to targeted handlers in lane order:

        DISPATCH lane (serialized, single-owner):
          1. _handle_reconcile()        — stall detection + tracker state refresh
          2. _handle_review_check()     — forge API: reviews + merged branches
          3. _handle_dispatch_needed()  — candidate fetch, blocker resolution,
                                          selection, and _dispatch(); guarded by
                                          ``_dispatch_lane_lock``.

        Supporting steps (not lane-gated):
          4. _handle_yolo_review()      — YOLO merge actions only.

        MAINTENANCE lane (bounded concurrency, non-blocking to dispatch):
          5a. _maybe_run_watchdog()     — stuck-issue detection + repair.
          5b. _run_step5b_maintenance()  — repo self-heal + terminal worktree cleanup
                                          + auto-archive + merged-label sweeps
                                          (TASK-466.2).
          5c. _run_step5c_epic_maintenance() — epic close/PR, staleness, rebase, orphan reset
                                             fire-and-forget, same pattern as 5b (TASK-466.3).

          6.  _handle_auto_update()     — git pull + restart when idle.
        """
        t0 = time.monotonic()

        # -1. Process any commands queued by the API process via the IPC layer.
        # Must run before profile swap so a "reload_profiles" command is
        # visible in step 0. Non-blocking: drains the SQLite command queue
        # in the current thread; individual command handlers are cheap.
        if self._ipc is not None:
            self._process_ipc_commands()

        # 0. Apply any pending profile swap queued via replace_agent_profiles().
        # Done at the very start of the tick so every step below sees a single
        # consistent profile list — mirrors the file-watcher reload semantics.
        self._apply_pending_agent_profiles()

        # 0a. Drop each tracker's cached task snapshot so this tick reads
        # fresh state once, then shares that parse across its phases (the
        # full-corpus read+parse is the dominant tick cost). Writes during
        # the tick re-invalidate, so reads never go stale.
        self._invalidate_tracker_read_caches()

        # Release addendum leases are independent of source-task lifecycle.
        # Run their durable recovery on every event/full-sync tick so a worker
        # crash cannot strand a row until the source task changes state.
        await asyncio.get_event_loop().run_in_executor(
            self._tick_pool, self._recover_release_addendum_leases
        )

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

        # 4. DISPATCH LANE — fetch candidates and dispatch eligible issues.
        # _handle_dispatch_needed() acquires _dispatch_lane_lock for its full
        # duration so no second selection pass can start concurrently.
        t3_start = time.monotonic()
        dispatch_timings = await self._handle_dispatch_needed()
        t3 = time.monotonic()

        # 5. YOLO merge actions (uses cached forge state).
        # Auto-archive and merged-labeling have moved to step 5b maintenance lane.
        yolo_result = await self._handle_yolo_review()
        archive_ms = 0.0
        merged_ms = 0.0
        if isinstance(yolo_result, tuple):
            yolo_ms = float(yolo_result[0])
            if len(yolo_result) > 1:
                archive_ms = float(yolo_result[1])
            if len(yolo_result) > 2:
                merged_ms = float(yolo_result[2])
        else:
            yolo_ms = float(yolo_result)
        t4 = time.monotonic()

        # 5a. MAINTENANCE LANE — watchdog: detect and fix stuck issues.
        # Offloaded to the tick thread pool to keep the event loop unblocked —
        # the four sub-checks iterate _last_candidates and may issue tracker
        # calls per stuck issue, which can block 200ms-2s. Safe because
        # watchdog runs after all other tick handlers have settled, so the
        # shared mutable state it reads (state.completed, _orphan_reset_counts,
        # _last_candidates) is not being concurrently written.
        _t_watchdog = time.monotonic()
        await asyncio.get_event_loop().run_in_executor(
            self._tick_pool, self._maybe_run_watchdog
        )
        watchdog_ms = (time.monotonic() - _t_watchdog) * 1000

        # 5b. MAINTENANCE LANE — periodic managed-checkout self-heal, terminal
        # worktree cleanup, auto-archive, and merged-label sweeps (TASK-466.2).
        # Submitted to the tick thread pool but NOT awaited so dispatch latency
        # is not inflated by git I/O or tracker queries.  A new run is only
        # started when the previous one has finished (or never started) so we
        # don't pile up concurrent maintenance jobs on a slow filesystem.  Each
        # sub-job inside _run_step5b_maintenance() is independently gated by
        # _run_maintenance_job() so the four jobs have separate in-flight
        # coalescing and interval throttling.
        _t_maintenance = time.monotonic()
        if self._maintenance_future is None or self._maintenance_future.done():
            self._maintenance_future = asyncio.get_event_loop().run_in_executor(
                self._tick_pool, self._run_step5b_maintenance
            )

        # 5c. MAINTENANCE LANE — epic rollup, staleness, rebase filing, and
        # orphan sweeps.  Submitted to the tick thread pool but NOT awaited so
        # dispatch latency is not inflated by git I/O or tracker writes.
        # A new run is only started when the previous one has finished (or never
        # started) so we don't pile up concurrent epic maintenance jobs on a
        # slow system.  Runs AFTER _handle_dispatch_needed so _last_candidates
        # is populated before the job reads it.  Ordering within the job is
        # preserved: staleness before rebase filing (oompah-zlz_2-82dr).
        if self._epic_maintenance_future is None or self._epic_maintenance_future.done():
            self._epic_maintenance_future = asyncio.get_event_loop().run_in_executor(
                self._tick_pool, self._run_step5c_epic_maintenance
            )
        heal_ms = (time.monotonic() - _t_maintenance) * 1000

        t4b = time.monotonic()
        total_ms = (t4b - t0) * 1000
        self._last_tick_metrics = {
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "total_ms": round(total_ms, 3),
            "reconcile_ms": round((t1 - t0) * 1000, 3),
            "reviews_ms": round((t2 - t1) * 1000, 3),
            "dispatch_ms": round((t3 - t3_start) * 1000, 3),
            "yolo_ms": round(yolo_ms, 3),
            "post_yolo_ms": round((t4b - t4) * 1000, 3),
            "tick_pool_queue_depth": self._tick_pool_queue_depth(),
            "dispatch_events_coalesced": getattr(
                self, "_dispatch_events_coalesced", 0
            ),
        }

        # Store per-substep telemetry for dashboard snapshots (TASK-465.1).
        # Also record the number of coalesced events (TASK-465.2) so operators
        # can see burst size when diagnosing tick latency.
        self._last_tick_timings = {
            "reconcile_ms": (t1 - t0) * 1000,
            "reviews_ms": (t2 - t1) * 1000,
            "dispatch_ms": (t3 - t3_start) * 1000,
            "yolo_ms": yolo_ms,
            "archive_ms": archive_ms,
            "merged_ms": merged_ms,
            "watchdog_ms": watchdog_ms,
            "heal_ms": heal_ms,
            "total_ms": total_ms,
            "dispatch_substeps": dispatch_timings,
            "coalesced_events": self._last_coalesced_event_count,
        }
        if total_ms > 2000:
            _dispatch_detail = " ".join(
                f"{k}={v:.0f}" for k, v in dispatch_timings.items()
            )
            logger.warning(
                "Slow tick: %.0fms (reconcile=%.0f reviews=%.0f dispatch=%.0f"
                " [%s] yolo=%.0f archive=%.0f merged=%.0f"
                " watchdog=%.0f heal=%.0f)",
                total_ms,
                (t1 - t0) * 1000,
                (t2 - t1) * 1000,
                (t3 - t3_start) * 1000,
                _dispatch_detail,
                yolo_ms,
                archive_ms,
                merged_ms,
                watchdog_ms,
                heal_ms,
            )

        self._notify_observers()

        # 6. Auto-update when idle (no agents, no retries)
        await self._handle_auto_update()

    def _tick_pool_queue_depth(self) -> int | None:
        queue = getattr(getattr(self, "_tick_pool", None), "_work_queue", None)
        if queue is None or not hasattr(queue, "qsize"):
            return None
        try:
            return int(queue.qsize())
        except Exception:  # noqa: BLE001
            return None

    # Supported IPC command types and their handlers.
    _IPC_COMMAND_HANDLERS: dict[str, str] = {
        "pause": "_ipc_cmd_pause",
        "unpause": "_ipc_cmd_unpause",
        "request_refresh": "_ipc_cmd_request_refresh",
        "dispatch_issue": "_ipc_cmd_dispatch_issue",
        "cleanup_commands": "_ipc_cmd_cleanup_commands",
    }

    def _process_ipc_commands(self) -> None:
        """Drain the IPC command queue and execute each pending command.

        Called once per tick before any other processing.  Each command is
        ACK'd (marked 'processed' or 'failed') regardless of outcome so
        the queue doesn't grow unboundedly.

        New command types can be added by implementing an
        ``_ipc_cmd_<type>`` method and registering it in
        ``_IPC_COMMAND_HANDLERS``.
        """
        if self._ipc is None:
            return
        try:
            commands = self._ipc.poll_commands()
        except Exception as exc:  # noqa: BLE001
            logger.warning("OrchestratorIPC.poll_commands failed: %s", exc)
            return
        for cmd in commands:
            cmd_id: int = cmd["id"]
            cmd_type: str = cmd.get("command", "")
            payload: dict = cmd.get("payload", {}) or {}
            handler_name = self._IPC_COMMAND_HANDLERS.get(cmd_type)
            if handler_name is None:
                logger.warning(
                    "OrchestratorIPC: unknown command type %r (id=%d) — skipped",
                    cmd_type,
                    cmd_id,
                )
                self._ipc.ack_command(cmd_id, ok=False)
                continue
            handler = getattr(self, handler_name, None)
            if handler is None:
                logger.error(
                    "OrchestratorIPC: handler %r not found for command %r (id=%d)",
                    handler_name,
                    cmd_type,
                    cmd_id,
                )
                self._ipc.ack_command(cmd_id, ok=False)
                continue
            try:
                handler(payload)
                self._ipc.ack_command(cmd_id, ok=True)
                logger.debug("OrchestratorIPC: executed command %r (id=%d)", cmd_type, cmd_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "OrchestratorIPC: command %r (id=%d) raised %s",
                    cmd_type,
                    cmd_id,
                    exc,
                )
                self._ipc.ack_command(cmd_id, ok=False)

    # ------------------------------------------------------------------
    # IPC command implementations
    # ------------------------------------------------------------------

    def _ipc_cmd_pause(self, _payload: dict) -> None:
        """IPC: pause the orchestrator."""
        self.pause()

    def _ipc_cmd_unpause(self, _payload: dict) -> None:
        """IPC: resume the orchestrator."""
        self.unpause()

    def _ipc_cmd_request_refresh(self, _payload: dict) -> None:
        """IPC: trigger a dispatch loop refresh."""
        self.request_refresh()

    def _ipc_cmd_dispatch_issue(self, payload: dict) -> None:
        """IPC: force-dispatch a specific issue by identifier.

        Payload: {"identifier": "TASK-123"}
        """
        identifier = payload.get("identifier")
        if not identifier:
            logger.warning("OrchestratorIPC: dispatch_issue command missing 'identifier'")
            return
        # Find the issue across all projects and dispatch it.  This reuses
        # the existing force-dispatch endpoint logic (no eligibility checks).
        # _process_ipc_commands is always called from the event-loop thread
        # (sync call inside the async _tick), so asyncio.ensure_future is safe.
        for project in self.project_store.list_all():
            try:
                tracker = self._tracker_for_project(project.id)
                issue = tracker.fetch_issue_detail(identifier)
            except Exception:  # noqa: BLE001
                continue
            if issue is not None:
                asyncio.ensure_future(self._dispatch(issue, attempt=None))
                return
        logger.warning(
            "OrchestratorIPC: dispatch_issue: issue %r not found in any project",
            identifier,
        )

    def _ipc_cmd_cleanup_commands(self, _payload: dict) -> None:
        """IPC: prune old processed/failed commands from the queue."""
        if self._ipc is not None:
            deleted = self._ipc.cleanup_old_commands()
            logger.debug("OrchestratorIPC: cleaned up %d old commands", deleted)

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

        if self._merged_branches_dirty:
            reviews_by_project, merged_branches = await asyncio.gather(
                self._fetch_all_reviews_bounded(),
                self._fetch_all_merged_branches_bounded(),
            )
            self._merged_branches = merged_branches
            self._merged_branches_dirty = False
        else:
            reviews_by_project = await self._fetch_all_reviews_bounded()

        self._reviews_cache = reviews_by_project
        # Derive unmerged review branches from cached reviews
        self._unmerged_review_branches = {
            r.source_branch
            for reviews in reviews_by_project.values()
            for r in reviews
            if r.source_branch
        }
        logger.debug(
            "Unmerged review branches: %s", sorted(self._unmerged_review_branches)
        )
        summary = self._reviews_summary()
        if summary != self._last_emitted_reviews_summary:
            self._last_emitted_reviews_summary = dict(summary)
            self._notify_state_only()

    async def _handle_dispatch_needed(self) -> dict[str, float]:
        """Fetch candidates, resolve blockers, and dispatch eligible issues.

        Runs exclusively on the DISPATCH lane (``DispatchLane.DISPATCH``).
        Acquires ``_dispatch_lane_lock`` for the full duration so that no
        two dispatch selection passes can run concurrently — candidate
        selection and ``_dispatch()`` are always single-owner.

        Returns a dict mapping substep name → elapsed milliseconds so the
        caller (_tick) can include per-substep timings in slow-tick logs and
        the dashboard snapshot.  Keys are stable; callers must tolerate new
        keys being added in future versions.
        """
        async with self._dispatch_lane_lock:
            return await self._handle_dispatch_needed_locked()

    async def _handle_dispatch_needed_locked(self) -> dict[str, float]:
        """Inner body of _handle_dispatch_needed; called with _dispatch_lane_lock held."""
        timings: dict[str, float] = {}
        self._blocker_state_cache = {}  # reset per fetch cycle
        loop = asyncio.get_event_loop()
        metrics: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "available_slots_start": self._available_slots(),
        }

        async def _timed(name: str, func, *args):
            start = time.monotonic()
            result = await loop.run_in_executor(self._tick_pool, func, *args)
            metrics[f"{name}_ms"] = round((time.monotonic() - start) * 1000, 3)
            return result

        # 1. Candidate fetch — dominant I/O cost (one tracker query per project)
        candidates = await _timed("fetch_candidates", self._fetch_all_candidates)
        self._last_candidates = candidates
        metrics["candidate_count"] = len(candidates)
        timings["candidate_fetch"] = metrics["fetch_candidates_ms"]

        # 2. Blocker pre-resolution — parallel tracker state lookups per blocker
        await _timed("pre_resolve_blockers", self._pre_resolve_blockers, candidates)
        timings["blocker_pre_resolution"] = metrics["pre_resolve_blockers_ms"]

        # 3. Duplicate detection — pattern-based de-dup (add-label, add-comment).
        # Tracker calls run off the event loop. This detects pattern-based
        # duplicates like "rogers-*" that share a topic prefix even when suffixes differ.
        await _timed("duplicate_detection", self._apply_duplicate_detection, candidates)
        metrics["duplicate_detection"] = getattr(
            self, "_last_duplicate_detection_metrics", {}
        )
        timings["duplicate_detection"] = metrics["duplicate_detection_ms"]

        # 4. Intake decomposition proposals — process Proposed issues that are
        # too large for one task.  This does not dispatch agents.
        await _timed("epic_proposals", self._process_epic_proposals, candidates)
        metrics["epic_proposals"] = getattr(
            self, "_last_epic_proposal_metrics", {}
        )
        timings["epic_proposals"] = metrics["epic_proposals_ms"]

        # 5. Candidate selection — sort + filter pass via _select_dispatchable.
        # Run in a worker thread so tracker calls inside _should_dispatch
        # don't block uvicorn's event loop. Returns the
        # final ordered list of issues that passed _should_dispatch; the
        # async loop below only yields once per actual dispatch — no sync
        # work between yields. See task oompah-zlz_2-nvr.
        ready = await _timed("select_dispatchable", self._select_dispatchable, candidates)
        metrics["selection"] = getattr(self, "_last_selection_metrics", {})
        metrics["ready_count"] = len(ready)
        timings["candidate_selection"] = metrics["select_dispatchable_ms"]

        # 6. Normal dispatch — one await per dispatched agent
        _t_dispatch = time.monotonic()
        dispatched = 0
        for issue in ready:
            if self._available_slots() <= 0:
                break
            await self._dispatch(issue, attempt=None)
            dispatched += 1
        timings["normal_dispatch"] = (time.monotonic() - _t_dispatch) * 1000
        metrics["dispatched_count"] = dispatched

        # 7. Epic planning — plan open epics without children
        _t_epic = time.monotonic()
        epics_to_plan = await _timed("plan_open_epics", self._plan_open_epics, candidates)
        planned = 0
        for epic in epics_to_plan:
            if self._available_slots() <= 0:
                break
            await self._dispatch(epic, attempt=None)
            planned += 1
        timings["epic_planning"] = (time.monotonic() - _t_epic) * 1000
        metrics["epics_to_plan_count"] = len(epics_to_plan)
        metrics["epics_dispatched_count"] = planned

        # Epic close / PR maintenance, staleness checks, rebase filing, orphan
        # reset (also), and proactive rebase pruning have been moved to the MAINTENANCE
        # LANE (_run_step5c_epic_maintenance, step 5c of _tick) so they do not
        # add to dispatch latency (TASK-466.3).
        for moved_key in (
            "epic_close_pr",
            "staleness_checks",
            "rebase_filing",
            "orphan_reset",
        ):
            timings[moved_key] = 0.0
        metrics["finished_at"] = datetime.now(timezone.utc).isoformat()
        self._last_dispatch_metrics = metrics
        return timings

    async def _handle_yolo_review(self) -> float:
        """Run YOLO merge actions only.

        Uses the forge state cached by ``_handle_review_check()`` to avoid
        redundant API calls within the same tick.

        Auto-archive, merged-issue labeling, merged-epic labeling, and stale
        In Review reconciliation have been moved to the maintenance lane (step 5b,
        :meth:`_run_step5b_maintenance`) so they no longer block dispatch-critical
        tick latency (TASK-466.2).

        Returns yolo_ms timing float for telemetry.
        """
        loop = asyncio.get_event_loop()

        def _timed_yolo():
            t = time.monotonic()
            self._yolo_review_actions_sync()
            return (time.monotonic() - t) * 1000

        yolo_ms: float = await loop.run_in_executor(self._tick_pool, _timed_yolo)
        return yolo_ms

    def _get_project_maintenance_lock(self, project_id: str) -> threading.Lock:
        """Return the per-project maintenance lock, creating it on first access.

        Epic maintenance jobs that touch git branches or tracker state for a
        specific project acquire this lock so two concurrent maintenance sweeps
        (e.g. from a tick burst) cannot corrupt per-epic git state or tracker
        state concurrently.

        The lock is a ``threading.Lock`` rather than an ``asyncio.Lock``
        because maintenance jobs run inside the tick thread pool via
        ``run_in_executor``, not on the event loop.
        """
        if project_id not in self._epic_maintenance_project_locks:
            self._epic_maintenance_project_locks[project_id] = threading.Lock()
        return self._epic_maintenance_project_locks[project_id]

    def _run_step5c_epic_maintenance(self) -> None:
        """Sync fire-and-forget wrapper for tick step 5c (epic maintenance).

        Runs in the tick thread pool so epic I/O (git branch reads, tracker
        label writes) does not block the event loop or inflate dispatch tick
        latency.  Called from :meth:`_tick` via ``run_in_executor`` and **not
        awaited** — identical in structure to :meth:`_run_step5b_maintenance`.

        Sub-operations run sequentially inside this single worker to preserve
        the staleness→rebase ordering contract (oompah-zlz_2-82dr).  Each
        sub-operation is gated by :meth:`_run_maintenance_job` so in-flight
        coalescing, interval throttling, and observability tracking apply
        independently per job.

        Jobs registered here:

          ``epic_rollup_status`` — persist epic status labels derived from
                                  child issue states.
          ``epic_auto_close``   — auto-close epics whose children are terminal.
          ``epic_open_prs``     — open epic→main PRs for stacked/shared epics.
          ``epic_staleness``    — arm/clear staleness alerts; update rebase
                                  states.  **MUST run before** ``epic_rebase_filing``.
          ``epic_rebase_filing``— dispatch proactive rebase agents for stale
                                  epics (depends on ``epic_staleness`` state).
          ``epic_prune_rebase`` — drop ghost rebase-state entries for closed
                                  epics.
          ``epic_orphan_reset`` — reset in_progress issues with no agent.

        Per-project maintenance locks (TASK-466.3 AC#3) are acquired inside
        the individual worker functions for any operation that touches git
        branches or tracker state.
        """
        # Snapshot candidates once at job-start time so all sub-steps share a
        # consistent view even if a concurrent tick updates _last_candidates.
        candidates = list(self._last_candidates)

        # 1. Persist epic rollup status labels from child states so GitHub
        # issue state matches the dashboard's derived epic state.
        self._run_maintenance_job(
            "epic_rollup_status",
            lambda: self._reconcile_epic_rollup_statuses(
                self._all_non_terminal_epics()
            ),
            min_interval_s=60.0,
        )

        # 2. Auto-close epics whose children are all terminal.
        self._run_maintenance_job(
            "epic_auto_close",
            lambda: self._auto_close_completed_epics(candidates),
            min_interval_s=60.0,
        )

        # 3. Open the epic→main PR for stacked/shared epics.
        # _all_non_terminal_epics() re-reads tracker state at call time so
        # epics that just closed in step 2 are correctly excluded.
        self._run_maintenance_job(
            "epic_open_prs",
            lambda: self._open_epic_main_prs(self._all_non_terminal_epics()),
            min_interval_s=60.0,
        )

        # 4 + 5. Staleness check then proactive rebase filing.
        # Step 4 MUST complete before step 5 — _check_epic_staleness()
        # updates _epic_rebase_states which _dispatch_proactive_rebase_agents()
        # reads.  Both share the same threshold guard; running them back-to-back
        # inside a single sequential function guarantees ordering regardless of
        # individual job throttle states (oompah-zlz_2-82dr ordering contract).
        if self.config.epic_staleness_threshold_commits > 0:
            self._run_maintenance_job(
                "epic_staleness",
                lambda: self._check_epic_staleness(candidates),
                min_interval_s=300.0,
            )
            self._run_maintenance_job(
                "epic_rebase_filing",
                lambda: self._dispatch_proactive_rebase_agents(candidates),
                min_interval_s=300.0,
            )

        # 6. Prune ghost rebase-state entries for closed epics.
        self._run_maintenance_job(
            "epic_prune_rebase",
            lambda: self._prune_stale_epic_rebase_states(candidates),
            min_interval_s=300.0,
        )

        # 7. Orphan reset — _fetch_in_progress_issues() reads tracker state
        # fresh at call time so issues that just closed during this tick are
        # not wrongly reset.
        self._run_maintenance_job(
            "epic_orphan_reset",
            lambda: self._reset_orphaned_in_progress(self._fetch_in_progress_issues()),
            min_interval_s=60.0,
        )

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
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            result = subprocess.run(
                ["git", "rev-list", "HEAD..origin/main", "--count"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            count = int(result.stdout.strip()) if result.returncode == 0 else 0
            ahead_result = subprocess.run(
                ["git", "rev-list", "origin/main..HEAD", "--count"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            ahead_count = (
                int(ahead_result.stdout.strip()) if ahead_result.returncode == 0 else 0
            )
            if count == 0:
                # Clear any previous auto-update alert
                self._alerts = [
                    a for a in self._alerts if a.get("source") != "auto_update"
                ]
                return

            # Native tracker writes are committed and pushed to the same
            # repository that runs this service.  Restarting for a commit
            # which changes only task-tracker state can interrupt the API
            # request that made that write (notably dashboard drag/drop),
            # producing a client-side network error.  The service reads task
            # state from each managed project's checkout, so its own source
            # checkout does not need to pull or restart for these commits.
            #
            # Fail safe: if Git cannot list the changed paths, retain the
            # existing update-and-restart behaviour rather than missing a
            # runtime update.
            changed_paths_result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD..origin/main"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=10,
            )
            changed_paths = [
                path.strip()
                for path in changed_paths_result.stdout.splitlines()
                if path.strip()
            ]
            if (
                changed_paths_result.returncode == 0
                and changed_paths
                and all(path.startswith(".oompah/tasks/") for path in changed_paths)
            ):
                logger.info(
                    "Auto-update: %d tracker-only commit(s) on origin/main; "
                    "skipping restart",
                    count,
                )
                self._alerts = [
                    a for a in self._alerts if a.get("source") != "auto_update"
                ]
                return

            logger.info(
                "Auto-update: %d new commit(s) on origin/main, pulling and restarting",
                count,
            )
            if ahead_count > 0:
                logger.info(
                    "Auto-update: local main is %d commit(s) ahead; rebasing onto origin/main",
                    ahead_count,
                )
                # Local agent/operator commits plus new origin/main commits make
                # --ff-only fail with "can't be fast-forwarded". Rebase keeps
                # the local commits and --autostash preserves routine dirty
                # tracked files while avoiding a merge commit on main.
                pull = subprocess.run(
                    ["git", "pull", "--rebase", "--autostash", "origin", "main"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                failure_operation = "git pull --rebase"
            else:
                # --autostash handles routine local config/task changes.
                # Without it, ``--ff-only`` refuses with "Your local changes
                # would be overwritten by merge" and surfaces a UI alert
                # every poll.
                pull = subprocess.run(
                    ["git", "pull", "--ff-only", "--autostash", "origin", "main"],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                failure_operation = "git pull"
            if pull.returncode != 0:
                if failure_operation == "git pull --rebase":
                    subprocess.run(
                        ["git", "rebase", "--abort"],
                        cwd=repo_dir,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                msg = f"Auto-update failed: {failure_operation} returned error — {pull.stderr.strip()[:200]}"
                logger.warning(
                    "Auto-update: %s failed: %s",
                    failure_operation,
                    pull.stderr.strip()[:200],
                )
                # Replace any existing auto-update alert
                self._alerts = [
                    a for a in self._alerts if a.get("source") != "auto_update"
                ]
                self._alerts.append(
                    {"level": "warning", "source": "auto_update", "message": msg}
                )
                return

            # Trigger graceful restart
            self._restart_requested = True
            self._stopping = True
        except (subprocess.TimeoutExpired, OSError, ValueError) as exc:
            msg = f"Auto-update failed: {exc}"
            logger.debug("Auto-update check failed: %s", exc)
            self._alerts = [a for a in self._alerts if a.get("source") != "auto_update"]
            self._alerts.append(
                {"level": "warning", "source": "auto_update", "message": msg}
            )

    def _fetch_all_candidates(self) -> list[Issue]:
        """Fetch candidate issues from all configured projects (parallel)."""
        projects = self.project_store.list_all()
        if not projects:
            # No projects configured — use legacy tracker
            return self._fetch_legacy_candidates()

        async def _fetch_all_projects() -> list[Issue]:
            # Use bounded per-project refresh for each project
            async def _fetch_one(project) -> list[Issue]:
                project_id = project.id
                async def _coro():
                    try:
                        tracker = self._tracker_for_project(project_id)
                        issues = tracker.fetch_candidate_issues()
                        for issue in issues:
                            issue.project_id = project_id
                        return issues
                    except TrackerNotConfiguredError:
                        return []
                    except TrackerTimeoutError as exc:
                        logger.warning(
                            "Fetch timed out for project %s: %s",
                            project.name,
                            exc,
                        )
                        return []
                    except (TrackerError, ProjectError) as exc:
                        logger.error(
                            "Fetch failed for project %s: %s",
                            project.name,
                            exc,
                            extra={"error_class": _error_class_for_tracker_exc(exc)},
                        )
                        return []

                data, _ = await self._run_bounded_refresh(
                    project_id, "candidates", _coro
                )
                return data

            all_candidates: list[Issue] = []
            # Use asyncio.gather for parallel bounded refresh
            results = await asyncio.gather(*[_fetch_one(p) for p in projects])
            for issues in results:
                all_candidates.extend(issues)
            return all_candidates

        return asyncio.run(_fetch_all_projects())

    def _fetch_legacy_candidates(self) -> list[Issue]:
        """Fetch candidates from the globally configured tracker."""
        try:
            return self.tracker.fetch_candidate_issues()
        except TrackerNotConfiguredError:
            return []
        except TrackerTimeoutError as exc:
            logger.warning("Tracker fetch timed out: %s", exc)
            return []
        except TrackerError as exc:
            logger.error(
                "Tracker fetch failed: %s",
                exc,
                extra={"error_class": _error_class_for_tracker_exc(exc)},
            )
            return []

    def _fetch_in_progress_issues(self) -> list[Issue]:
        """Fetch In Progress issues for orphan reconciliation.

        In Progress is not a dispatchable status in the oompah workflow, so
        these tasks must be fetched separately from normal dispatch candidates.
        """
        projects = self.project_store.list_all()
        if not projects:
            return self._fetch_legacy_in_progress()

        async def _fetch_all_projects() -> list[Issue]:
            async def _fetch_one(project) -> list[Issue]:
                project_id = project.id
                async def _coro():
                    try:
                        tracker = self._tracker_for_project(project_id)
                        issues = tracker.fetch_issues_by_states([IN_PROGRESS])
                        for issue in issues:
                            issue.project_id = project_id
                        return issues
                    except TrackerNotConfiguredError:
                        return []
                    except TrackerTimeoutError as exc:
                        logger.warning(
                            "In Progress fetch timed out for project %s: %s",
                            project.name,
                            exc,
                        )
                        return []
                    except (TrackerError, ProjectError) as exc:
                        logger.error(
                            "In Progress fetch failed for project %s: %s",
                            project.name,
                            exc,
                            extra={"error_class": _error_class_for_tracker_exc(exc)},
                        )
                        return []

                data, _ = await self._run_bounded_refresh(
                    project_id, "in_progress", _coro
                )
                return data

            in_progress: list[Issue] = []
            results = await asyncio.gather(*[_fetch_one(p) for p in projects])
            for issues in results:
                in_progress.extend(issues)
            return in_progress

        return asyncio.run(_fetch_all_projects())

    def _fetch_legacy_in_progress(self) -> list[Issue]:
        """Fetch In Progress from legacy tracker."""
        try:
            return self.tracker.fetch_issues_by_states([IN_PROGRESS])
        except TrackerNotConfiguredError:
            return []
        except TrackerTimeoutError as exc:
            logger.warning("Tracker In Progress fetch timed out: %s", exc)
            return []
        except TrackerError as exc:
            logger.error(
                "Tracker In Progress fetch failed: %s",
                exc,
                extra={"error_class": _error_class_for_tracker_exc(exc)},
            )
            return []

    def _retryable_state_keys(self) -> set[str]:
        """Return states that may be dispatched by a scheduled retry."""
        keys = {_state_key(IN_PROGRESS)}
        keys.update(_dispatch_active_state_keys(self.config.tracker_active_states))
        return keys

    def _retry_issue_matches(self, issue: Issue, retry: RetryEntry) -> bool:
        """Return True when ``issue`` is the task owned by ``retry``."""
        if retry.project_id and issue.project_id and issue.project_id != retry.project_id:
            return False
        issue_keys = {issue.id, issue.identifier}
        retry_keys = {retry.issue_id, retry.identifier}
        return bool(issue_keys & retry_keys)

    def _fetch_retry_issue(self, retry: RetryEntry) -> Issue | None:
        """Fetch the issue for a scheduled retry, including In Progress tasks."""
        for issue in self._fetch_all_candidates():
            if self._retry_issue_matches(issue, retry):
                return issue

        if retry.project_id:
            project_ids: list[str | None] = [retry.project_id]
        else:
            projects = self.project_store.list_all()
            project_ids = [p.id for p in projects if getattr(p, "id", None)]
            if not project_ids:
                project_ids = [None]

        for project_id in project_ids:
            tracker = (
                self._tracker_for_project(project_id)
                if project_id
                else self.tracker
            )
            issue: Issue | None = None
            for fetched in tracker.fetch_issue_states_by_ids([retry.issue_id]):
                if fetched.id == retry.issue_id or fetched.identifier == retry.identifier:
                    issue = fetched
                    break
            if issue is None:
                issue = tracker.fetch_issue_detail(retry.identifier)
            if issue is None:
                continue
            if project_id and not issue.project_id:
                issue.project_id = project_id
            if self._retry_issue_matches(issue, retry):
                return issue
        return None

    def _fetch_all_in_progress_issues(self) -> list[Issue]:
        """Fetch tasks in In Progress state across all configured trackers.

        Complements ``_fetch_all_candidates`` for the orphan-reset sweep:
        In Progress tasks are never candidates (they are not in active_states),
        so a separate pass is needed to discover orphaned In Progress tasks
        left behind after a retry claim is released (TASK-409).
        """
        projects = self.project_store.list_all()
        if not projects:
            try:
                return self.tracker.fetch_in_progress_issues()
            except (TrackerNotConfiguredError, TrackerError):
                return []

        all_in_progress: list[Issue] = []
        for project in projects:
            try:
                tracker = self._tracker_for_project(project.id)
                issues = tracker.fetch_in_progress_issues()
                for issue in issues:
                    issue.project_id = project.id
                all_in_progress.extend(issues)
            except (TrackerNotConfiguredError, TrackerError, ProjectError):
                continue
        return all_in_progress

    def _fetch_issue_across_trackers(self, identifier: str) -> Issue | None:
        """Look up an issue by identifier across all configured trackers.

        Tries project trackers first, then falls back to the service default
        tracker.  Returns the first match found, or ``None``.  Sets
        ``issue.project_id`` on the returned issue when found in a project
        tracker.
        """
        for project in self.project_store.list_all():
            try:
                tracker = self._tracker_for_project(project.id)
                issue = tracker.fetch_issue_detail(identifier)
                if issue is not None:
                    issue.project_id = project.id
                    return issue
            except (TrackerError, ProjectError):
                continue
        # Fall back to the default / legacy tracker (no-project setups)
        try:
            return self.tracker.fetch_issue_detail(identifier)
        except (TrackerError, ProjectError):
            return None

    def _available_slots(self) -> int:
        return max(self.state.max_concurrent_agents - len(self.state.running), 0)

    def _per_state_available(self, state: str) -> bool:
        normalized = _state_key(state)
        limit = self.config.max_concurrent_agents_by_state.get(normalized)
        if limit is None:
            return True
        count = sum(
            1
            for e in self.state.running.values()
            if _state_key(e.issue.state) == normalized
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
        # Treat timezone-naive datetimes as local wall-clock values; comparing
        # them to timezone-aware UTC values raises, and older persisted/test
        # values may be naive.
        if ts.tzinfo is None:
            age = datetime.now() - ts
        else:
            age = datetime.now(timezone.utc) - ts
        # Fall back to polling if delivery is older than 150 seconds.
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

    def _shared_epic_child_done(self, issue: Issue) -> bool:
        """Return True when the tracker says a shared-epic child is terminal."""
        return _is_terminal_state(issue.state, self.config.tracker_terminal_states)

    def _blocker_satisfied(self, issue: Issue, blocker, blocker_state: str) -> bool:
        """Whether a dependency/blocker counts as resolved for dispatch.

        The tracker owns task state, so the blocker is satisfied only when its
        current tracker state is terminal.
        """
        if _is_terminal_state(blocker_state, self.config.tracker_terminal_states):
            return True
        return False

    def _shared_epic_child_terminal(self, epic: Issue, child: Issue) -> bool:
        """Whether a shared-epic child counts as complete for the landing gate."""
        return _is_terminal_state(child.state, self.config.tracker_terminal_states)

    def _epic_child_effective_state(self, epic: Issue, child: Issue) -> str:
        """Return the tracker-backed effective state for a shared-epic child."""
        return child.state

    def _all_non_terminal_epics(self) -> list[Issue]:
        """Every unfinished epic across all projects, regardless of the
        dispatch active-state filter.

        Epics sit in non-dispatch states (commonly ``Backlog``) and so never
        appear in ``fetch_candidate_issues``. The epic→main landing gate must
        still see them — their children may all be done. Reuses the per-tick
        read cache (``fetch_all_issues`` is already warmed by other phases),
        so this adds no extra corpus parse within a tick.

        For epics, ``Done`` is not lifecycle-finished; it means the epic work is
        ready for or awaiting the rollup merge. Only ``Merged`` and ``Archived``
        remove an epic from rollup/merged-epic reconciliation.
        """
        out: list[Issue] = []
        projects = self.project_store.list_all()
        trackers: list[tuple[str | None, TrackerProtocol]] = []
        if projects:
            for p in projects:
                try:
                    trackers.append((p.id, self._tracker_for_project(p.id)))
                except (ProjectError, TrackerError):
                    pass
        else:
            trackers.append((None, self.tracker))
        for pid, tracker in trackers:
            try:
                issues = list(tracker.fetch_all_issues())
                parent_ids = {
                    str(issue.parent_id).strip()
                    for issue in issues
                    if (issue.parent_id or "").strip()
                }
                for issue in issues:
                    if pid:
                        issue.project_id = pid
                    status = canonicalize_status(issue.state)
                    labels = {str(label).strip().lower() for label in issue.labels or []}
                    if (
                        status in {MERGED, ARCHIVED}
                        or "merged" in labels
                        or "archive:yes" in labels
                    ):
                        continue
                    is_declared_epic = (
                        (issue.issue_type or "").strip().lower() == "epic"
                    )
                    issue_ids = {
                        str(value).strip()
                        for value in (issue.id, issue.identifier)
                        if value
                    }
                    has_children = bool(issue_ids & parent_ids)
                    is_rollup_parent = is_declared_epic or has_children
                    if is_rollup_parent:
                        out.append(issue)
            except (TrackerError, ProjectError) as exc:
                logger.debug("non-terminal epic fetch failed for %s: %s", pid, exc)
        return out

    def _reconcile_epic_rollup_statuses(self, epics: list[Issue]) -> int:
        """Persist each epic's tracker status from its children's states.

        The dashboard derives epic state from child issue state at render time,
        but the tracker itself also needs that status label so GitHub issues do
        not show stale Backlog/Open values while their children are active or
        complete.
        """
        updated = 0
        for epic in epics:
            if canonicalize_status(epic.state) in {MERGED, ARCHIVED}:
                continue

            children = self._fetch_epic_children(epic)
            if not children:
                continue

            current_status = canonicalize_status(epic.state)
            labels = {str(label).strip().lower() for label in epic.labels or []}
            has_review_evidence = bool(
                current_status in {IN_REVIEW, NEEDS_CI_FIX, NEEDS_REBASE}
                or getattr(epic, "review_url", None)
                or getattr(epic, "review_number", None)
                or labels.intersection({"ci-fix", "merge-conflict"})
            )
            epic_branch = str(getattr(epic, "work_branch", "") or "").strip()
            if has_review_evidence and not epic_branch:
                try:
                    epic_branch = self.project_store.epic_branch_name(epic.identifier)
                except Exception:  # noqa: BLE001 - rollup reconciliation is best-effort
                    epic_branch = ""
            if (
                has_review_evidence
                and epic_branch
                and any(canonicalize_status(child.state) == DONE for child in children)
            ):
                self._sync_epic_review_child_states(
                    epic.project_id,
                    epic,
                    epic_branch,
                    children=children,
                )

            child_states = [
                self._epic_child_effective_state(epic, child)
                for child in children
            ]

            rolled = epic_rollup_state(child_states)
            rolled_status = canonicalize_status(rolled)
            if rolled_status == MERGED:
                child_statuses = [
                    canonicalize_status(status)
                    for status in child_states
                    if canonicalize_status(status) not in {PROPOSED, DECOMPOSED}
                ]
                if child_statuses and any(
                    status == MERGED for status in child_statuses
                ):
                    rolled = DONE
                    rolled_status = DONE
            children_complete_for_review = self._epic_children_complete_for_review_work(
                children
            )
            if (
                has_review_evidence
                and children_complete_for_review
                and current_status not in {IN_REVIEW, NEEDS_CI_FIX, NEEDS_REBASE}
            ):
                rolled = IN_REVIEW
                rolled_status = IN_REVIEW
            if (
                not rolled
                or rolled_status == current_status
                or (
                    current_status in {IN_REVIEW, NEEDS_CI_FIX, NEEDS_REBASE}
                    and rolled_status
                    and rolled_status != MERGED
                    and children_complete_for_review
                )
            ):
                continue

            try:
                tracker = self._tracker_for_issue(epic)
                running_entry = self.state.running.get(epic.id or "")
                if (
                    running_entry
                    and running_entry.issue
                    and self._is_epic_review_repair_issue(
                        running_entry.issue,
                        children=children,
                    )
                ):
                    logger.info(
                        "Skipping rollup reconciliation for active epic repair %s",
                        epic.identifier,
                    )
                    continue
                refreshed = None
                try:
                    refreshed = tracker.fetch_issue_detail(epic.identifier)
                except Exception:
                    refreshed = None
                if isinstance(refreshed, Issue) and self._is_epic_review_repair_issue(
                    refreshed,
                    children=children,
                ):
                    logger.info(
                        "Skipping stale rollup reconciliation for active epic repair %s",
                        epic.identifier,
                    )
                    continue
                tracker.update_issue(epic.identifier, status=rolled)
                epic.state = rolled
                updated += 1
                logger.info(
                    "Reconciled epic %s status to %s from %d child issue(s)",
                    epic.identifier,
                    rolled,
                    len(children),
                )
            except Exception as exc:  # noqa: BLE001 - maintenance should continue
                logger.warning(
                    "Failed to reconcile epic %s rollup status to %s: %s",
                    epic.identifier,
                    rolled,
                    exc,
                )
        return updated

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

    def _project_review_capacity(
        self,
        project_id: str | None,
    ) -> tuple[int, int, bool]:
        """Return ``(open_reviews, limit, at_capacity)`` for review handoff."""
        n_open = self._count_open_reviews(project_id)
        limit = self._project_max_in_flight(project_id)
        return n_open, limit, n_open >= limit

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

    def _apply_project_provider_whitelist(
        self,
        targets: "list[DispatchTarget]",
        issue: Issue,
    ) -> "tuple[list[DispatchTarget], bool]":
        """Filter *targets* by the project-level provider whitelist.

        When the project associated with *issue* has a non-empty
        ``provider_whitelist``, only :class:`DispatchTarget` entries whose
        ``provider.name`` appears in that whitelist are retained.

        An empty whitelist (the default) leaves *targets* unchanged so
        existing projects are unaffected.  Unknown project ids or missing
        ``provider_whitelist`` attributes are treated as "no whitelist".

        Returns:
            A tuple ``(filtered_targets, whitelist_was_applied)`` where
            ``whitelist_was_applied`` is ``True`` only when a non-empty
            whitelist existed and reduced the target list (even to zero).
            The caller uses this flag to distinguish "whitelist blocked all
            candidates" from "no providers configured at all" so it can
            surface an appropriate error message.
        """
        if not issue.project_id:
            return targets, False
        project = self.project_store.get(issue.project_id)
        if project is None:
            return targets, False
        whitelist: list[str] = getattr(project, "provider_whitelist", []) or []
        if not whitelist:
            return targets, False

        whitelist_set = set(whitelist)
        filtered = [t for t in targets if t.provider.name in whitelist_set]

        if not filtered and targets:
            rejected = [t.provider.name for t in targets]
            logger.warning(
                "Project %r provider whitelist %s excludes all %d dispatch "
                "candidates for issue %s (rejected providers: %s). "
                "No agent will be started.",
                project.name,
                whitelist,
                len(targets),
                issue.identifier,
                rejected,
            )
        elif len(filtered) < len(targets):
            skipped = [
                t.provider.name
                for t in targets
                if t.provider.name not in whitelist_set
            ]
            logger.debug(
                "Project %r provider whitelist filtered %d/%d candidates for issue %s "
                "(skipped providers not in whitelist: %s)",
                project.name,
                len(targets) - len(filtered),
                len(targets),
                issue.identifier,
                skipped,
            )

        return filtered, True

    def _project_has_open_review(self, project_id: str | None) -> bool:
        """Return True if the project is at or above its in-flight PR cap.

        Thin compatibility wrapper around ``_count_open_reviews`` and
        ``_project_max_in_flight``. Retained so callers (tests, subclasses)
        that reference the old name continue to work unchanged.
        """
        return self._count_open_reviews(project_id) >= self._project_max_in_flight(
            project_id
        )

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
        state_norm = _state_key(issue.state)
        if state_norm not in _dispatch_active_state_keys(
            self.config.tracker_active_states
        ):
            return False
        if state_norm in {
            _state_key(s) for s in self.config.tracker_terminal_states
        }:
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
            children = tracker.fetch_children(epic.id)
        except Exception as exc:
            logger.debug(
                "Failed to fetch children for epic %s: %s", epic.identifier, exc
            )
            return []
        if children is None:
            return []
        if isinstance(children, list):
            return children
        try:
            return list(children)
        except TypeError:
            logger.debug(
                "Tracker returned non-iterable children for epic %s: %r",
                epic.identifier,
                children,
            )
            return []

    def _is_epic_rebase_task(
        self,
        issue: Issue,
        epic_identifier: str | None = None,
    ) -> bool:
        """Return True for auto-filed tasks that rebase a shared epic branch."""
        raw_parent_id = getattr(issue, "parent_id", None)
        parent_id = raw_parent_id.strip() if isinstance(raw_parent_id, str) else ""
        if epic_identifier is not None and parent_id and parent_id != epic_identifier:
            return False
        if epic_identifier is None and not parent_id:
            return False
        target_epic = epic_identifier or parent_id
        try:
            epic_branch = self.project_store.epic_branch_name(target_epic).lower()
        except Exception:  # noqa: BLE001 - fallback only affects classification
            epic_branch = f"epic-{target_epic}".lower()
        title = (issue.title or "").strip().lower()
        return title.startswith("rebase ") and epic_branch in title

    def _find_active_epic_rebase_sibling(
        self,
        tracker,
        epic: Issue,
    ) -> Issue | None:
        """Find an actionable existing rebase task for ``epic``.

        This is intentionally tracker-backed instead of relying only on the
        shared epic worktree copy. Shared worktrees can have stale task files
        while the managed repo has already moved duplicates to Archived.
        """
        actionable = {
            _state_key(OPEN),
            _state_key(IN_PROGRESS),
            _state_key(NEEDS_REBASE),
        }
        try:
            tracker.invalidate_read_cache()
        except Exception:  # noqa: BLE001
            pass

        children = self._fetch_epic_children(epic)
        child_identifiers = {
            str(getattr(child, "identifier", None) or getattr(child, "id", ""))
            for child in children
            if getattr(child, "identifier", None) or getattr(child, "id", "")
        }
        candidates: list[Issue] = list(children)
        try:
            states = list(
                dict.fromkeys(
                    _dispatch_active_state_names(self.config.tracker_active_states)
                    + [NEEDS_REBASE]
                )
            )
            pool = tracker.fetch_issues_by_states(states)
            if pool is not None:
                candidates.extend(list(pool))
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Failed to fetch active rebase sibling pool for %s: %s",
                epic.identifier,
                exc,
            )

        seen: set[str] = set()
        matches: list[Issue] = []
        for child in candidates:
            identifier = str(
                getattr(child, "identifier", None) or getattr(child, "id", "") or ""
            )
            if not identifier or identifier in seen or identifier == epic.identifier:
                continue
            seen.add(identifier)
            if _state_key(getattr(child, "state", "")) not in actionable:
                continue
            raw_child_parent = getattr(child, "parent_id", None)
            child_parent = (
                raw_child_parent.strip() if isinstance(raw_child_parent, str) else ""
            )
            from_fetch_children = identifier in child_identifiers
            if child_parent and child_parent != epic.identifier:
                continue
            if not child_parent and not from_fetch_children:
                continue
            if self._is_epic_rebase_task(child, epic.identifier):
                matches.append(child)

        if not matches:
            return None
        return min(
            matches,
            key=lambda i: (
                getattr(i, "created_at", None) or "",
                getattr(i, "identifier", None) or getattr(i, "id", "") or "",
            ),
        )

    def _issue_has_children(self, issue: Issue) -> bool:
        """Return True when tracker state shows this issue has children."""
        return bool(self._fetch_epic_children(issue))

    def _is_epic_rollup_parent(
        self,
        issue: Issue,
        children: list[Issue] | None = None,
    ) -> bool:
        """Return True when *issue* is the parent rollup for child work."""
        if _is_epic_issue(issue):
            return True
        if children is not None:
            return bool(children)
        return self._issue_has_children(issue)

    def _epic_children_complete_for_review_work(
        self,
        children: list[Issue] | tuple[Issue, ...],
    ) -> bool:
        """True when every actionable child has reached the epic-review phase."""
        if not children:
            return False
        actionable = [
            canonicalize_status(child.state)
            for child in children
            if canonicalize_status(child.state) not in {PROPOSED, DECOMPOSED}
        ]
        if not actionable:
            return False
        return all(
            status in _EPIC_REVIEW_READY_CHILD_STATES
            for status in actionable
        )

    def _is_mature_epic_review_issue(
        self,
        issue: Issue,
        children: list[Issue] | None = None,
    ) -> bool:
        """Return True when an epic/rollup should be treated as review work."""
        if children is None:
            children = self._fetch_epic_children(issue)
        return (
            self._is_epic_rollup_parent(issue, children)
            and self._epic_children_complete_for_review_work(children)
        )

    def _is_epic_review_repair_issue(
        self,
        issue: Issue,
        *,
        children: list[Issue] | None = None,
        dispatch_gate: bool = False,
    ) -> bool:
        """True when *issue* is mature epic review work needing an agent repair.

        ``dispatch_gate=True`` is stricter and only admits pre-dispatch repair
        statuses.  Once claimed, oompah moves the issue to ``In Progress``; the
        workspace and completion paths still need to recognize that same repair
        run by its safety label.
        """
        status = canonicalize_status(issue.state)
        labels = {str(label).strip().lower() for label in issue.labels or []}
        if dispatch_gate:
            if status not in _EPIC_REVIEW_REPAIR_STATUSES:
                return False
        elif (
            status not in _EPIC_REVIEW_REPAIR_RUNNING_STATUSES
            and labels.isdisjoint(_EPIC_REVIEW_REPAIR_LABELS)
        ):
            return False
        return self._is_mature_epic_review_issue(issue, children)

    def _epic_branch_for_issue(self, epic: Issue) -> str:
        """Return the branch that should carry an epic rollup."""
        work_branch = getattr(epic, "work_branch", None)
        if isinstance(work_branch, str) and work_branch.strip():
            return work_branch.strip()
        return self.project_store.epic_branch_name(epic.identifier)

    def _has_epic_landing_ref(
        self,
        project: Any,
        epic_identifier: str,
        *,
        epic_branch: str | None = None,
    ) -> bool:
        """Return True when local state has an epic branch/worktree to land."""
        epic_branch = epic_branch or self.project_store.epic_branch_name(
            epic_identifier
        )

        project_id = getattr(project, "id", None)
        if project_id and hasattr(self.project_store, "epic_worktree_path_for"):
            try:
                wt_path = self.project_store.epic_worktree_path_for(
                    project_id,
                    epic_identifier,
                )
            except Exception:
                wt_path = None
            if wt_path and os.path.isdir(wt_path):
                return True

        repo_path = getattr(project, "repo_path", None)
        if not repo_path or not os.path.isdir(repo_path):
            return False

        for ref in (
            f"refs/heads/{epic_branch}",
            f"refs/remotes/origin/{epic_branch}",
        ):
            try:
                result = subprocess.run(
                    ["git", "show-ref", "--verify", "--quiet", ref],
                    cwd=repo_path,
                    timeout=10,
                    check=False,
                )
            except Exception:
                continue
            if result.returncode == 0:
                return True
        return False

    def _project_epic_strategy(self, project_id: str | None) -> str:
        """Return the project's epic_strategy.

        Always returns 'shared' — flat and stacked strategies have been
        removed (OOMPAH-167).  The parameter is kept for call-site
        compatibility during the transition; it is no longer used.
        """
        return "shared"

    def _project_requires_epic_for_tasks(self, project_id: str | None) -> bool:
        """Whether a project forbids standalone task implementation work."""
        if not project_id:
            return False
        project_store = getattr(self, "project_store", None)
        if project_store is None:
            return False
        try:
            project = project_store.get(project_id)
        except Exception:  # noqa: BLE001 - dispatch gates must fail open here
            return False
        if not project:
            return False
        return getattr(project, "require_epic_for_tasks", False) is True

    def _issue_requires_parent_epic(
        self,
        issue: Issue | None,
        project_id: str | None = None,
    ) -> bool:
        """True when implementation work lacks a required parent epic.

        ``require_epic_for_tasks`` means a task must land through an epic
        rollup. A non-empty ``parent_id`` is not enough: the parent must
        resolve to an epic, or to an inferred rollup parent in stacked/shared
        projects.
        """
        if issue is None:
            return False
        if (issue.issue_type or "").strip().lower() == "epic":
            return False
        effective_project_id = project_id or issue.project_id
        if not self._project_requires_epic_for_tasks(effective_project_id):
            return False
        if not (issue.parent_id or "").strip():
            return True
        if effective_project_id and not issue.project_id:
            issue.project_id = effective_project_id
        return self._resolve_parent_epic(issue) is None

    def _mark_issue_needs_epic_parent(
        self,
        issue: Issue,
        project_id: str | None,
    ) -> None:
        """Move a task to Needs Human when policy requires a parent epic."""
        if not project_id:
            return
        try:
            tracker = self._tracker_for_project(project_id)
            tracker.update_issue(issue.identifier, status=NEEDS_HUMAN)
            tracker.add_comment(
                issue.identifier,
                "This project requires implementation tasks to be attached to "
                "an epic before oompah can dispatch, create, or merge task PRs. "
                "Attach this task to an epic, or disable "
                "`require_epic_for_tasks` for intentional standalone work.",
                author="oompah",
            )
        except Exception as exc:  # noqa: BLE001 - best-effort operator signal
            logger.debug(
                "Failed to mark %s Needs Human for missing parent epic: %s",
                issue.identifier,
                exc,
            )

    def _resolve_parent_epic(self, issue: Issue) -> Issue | None:
        """Resolve a child issue's parent rollup, or None when this issue has
        no parent or the parent should not be handled as an epic rollup.

        Used by the shared-epic orchestration to identify the rollup parent
        that owns the epic branch and worktree.

        A parent explicitly typed as ``epic`` always counts.  A parent with
        children also counts even if its ``epic`` label was accidentally
        omitted; otherwise one bad metadata sync can bypass the per-project
        rollup policy and create stray child PRs.
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
                parent_id,
                issue.identifier,
                exc,
            )
            return None
        if not parent:
            return None
        # Carry the project_id over from the child for downstream
        # consumers that rely on it (the parent record may have it set
        # already, but be defensive).
        if not parent.project_id and issue.project_id:
            parent.project_id = issue.project_id
        if (parent.issue_type or "").strip().lower() == "epic":
            return parent
        if self._issue_has_children(parent):
            logger.debug(
                "Treating parent %s as epic rollup for %s because the parent has children",
                parent.identifier,
                issue.identifier,
            )
            return parent
        return None

    def _epic_rollup_child_strategy(
        self,
        issue: Issue,
        project_id: str | None = None,
    ) -> str | None:
        """Return the rollup strategy for a non-epic child of an epic.

        Child work does not become ``Merged`` just because the child branch
        itself appears in forge merged-branch history.  ``Merged`` is reserved
        for the epic rollup merge; child-branch merges only advance the child
        to ``Done``.  Returns 'shared' when the issue is a child of a rollup
        parent, ``None`` otherwise.
        """
        effective_project_id = project_id or issue.project_id
        if (issue.issue_type or "").strip().lower() == "epic":
            return None
        if not (issue.parent_id or "").strip():
            return None
        if effective_project_id and not issue.project_id:
            issue.project_id = effective_project_id
        if self._resolve_parent_epic(issue) is None:
            return None
        return "shared"

    def _create_workspace_for_issue(
        self,
        issue: Issue,
    ) -> tuple[str, Issue | None]:
        """Resolve and create the workspace path used to dispatch ``issue``.

        Returns ``(workspace_path, epic_for_shared_mode)``. The second
        element is non-None when the issue is a child of an epic, in which
        case callers know to commit/push on the shared epic branch instead
        of a per-task branch.

        Children of an epic share the epic's worktree; non-children fall
        back to a per-task worktree.

        The shared-mode epic worktree is created via
        ``project_store.create_epic_worktree``, which is idempotent
        (does NOT hard-reset existing in-flight work).
        """
        if not issue.project_id:
            workspace = self.workspace_mgr.create_for_issue(issue.identifier)
            self.workspace_mgr.run_before_run(workspace.path)
            return workspace.path, None

        if self._is_epic_review_repair_issue(issue):
            default_epic_branch = self.project_store.epic_branch_name(
                issue.identifier
            )
            explicit_branch = (
                str(getattr(issue, "work_branch", "") or "").strip()
                or str(getattr(issue, "branch_name", "") or "").strip()
            )
            work_branch = explicit_branch or default_epic_branch
            issue.work_branch = work_branch
            issue.branch_name = work_branch
            if work_branch == default_epic_branch:
                wp = self.project_store.create_epic_worktree(
                    issue.project_id,
                    issue.identifier,
                )
                return wp, issue
            wp = self.project_store.create_worktree(
                issue.project_id,
                issue.identifier,
                base_branch=issue.target_branch,
                branch_name=work_branch,
            )
            return wp, issue

        parent_epic = self._resolve_parent_epic(issue)
        if parent_epic is not None:
            wp = self.project_store.create_epic_worktree(
                issue.project_id,
                parent_epic.identifier,
            )
            return wp, parent_epic

        # For GitHub-backed tasks, generate a GitHub-safe branch name
        # (oompah/<project-slug>/gh-<number>) and persist Work Branch +
        # Target Branch metadata to the issue before creating the worktree
        # so review reconciliation can resolve the task from a PR source
        # branch without guessing by task ID (TASK-461.3, AC#1 and AC#2).
        work_branch: str | None = None
        if issue.tracker_kind == "github_issues" and issue.issue_number and issue.project_id:
            project_obj = self.project_store.get(issue.project_id)
            if project_obj is not None:
                work_branch = github_work_branch_name(project_obj.name, issue.issue_number)
                issue.work_branch = work_branch
                issue.branch_name = work_branch
                try:
                    tracker = self._tracker_for_issue(issue)
                    tracker.set_metadata_field(
                        issue.identifier, "oompah.work_branch", work_branch
                    )
                    if issue.target_branch:
                        tracker.set_metadata_field(
                            issue.identifier,
                            "oompah.target_branch",
                            issue.target_branch,
                        )
                except Exception as _exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to persist branch metadata for %s: %s",
                        issue.identifier,
                        _exc,
                    )

        wp = self.project_store.create_worktree(
            issue.project_id,
            issue.identifier,
            base_branch=issue.target_branch,
            branch_name=work_branch,
        )
        return wp, None

    def _auto_close_completed_epics(self, candidates: list[Issue]) -> None:
        """Auto-close epics whose children are all in terminal states.

        Scans deferred/open epics that have children; for each, delegates
        to :meth:`_epic_auto_close_check` which enforces the full
        four-condition gate (terminal children + branch merges +
        not-already-closed). See oompah-zlz_2-lvcd.
        """
        for issue in candidates:
            if (
                (issue.issue_type or "").strip().lower() != "epic"
                and not self._issue_has_children(issue)
            ):
                continue
            if _is_terminal_state(issue.state, self.config.tracker_terminal_states):
                self._clear_stuck_epic_alert(issue.identifier)
                continue  # already closed
            self._epic_auto_close_check(issue)

    def _epic_auto_close_check(self, epic: Issue) -> bool:
        """Evaluate whether ``epic`` should auto-close, and close if so.

        Implements the four-condition gate from oompah-zlz_2-lvcd:

        1. Every child in a terminal state per ``tracker_terminal_states``.
        2. For every child whose branch produced a PR/MR, that PR was
           merged into the project's default branch (``project.default_branch``).
        3. Children with no PR/MR (research/triage tasks that closed
           without code) are treated as eligible — no merge check.
        4. Epic itself is not already in a terminal state (don't
           reanimate a manually-closed epic).

        Returns:
            ``True`` when the epic was closed by this call, ``False``
            otherwise. When condition 1 passes but condition 2 fails,
            an alert with ``source='stuck_epic'`` is added to
            ``self._alerts`` so the dashboard surfaces it.
        """
        # Condition 4: don't reanimate a manually-closed epic.
        if _is_terminal_state(epic.state, self.config.tracker_terminal_states):
            self._clear_stuck_epic_alert(epic.identifier)
            return False

        # Edge case: epic with no children — never auto-close.
        children = self._fetch_epic_children(epic)
        if not children:
            self._clear_stuck_epic_alert(epic.identifier)
            return False

        # Condition 1: every child in a terminal state.
        non_terminal_children = [
            c for c in children
            if not _is_terminal_state(c.state, self.config.tracker_terminal_states)
        ]
        if non_terminal_children:
            # Clear any previous stuck alert — work is still in
            # progress, so it's not stuck yet.
            self._clear_stuck_epic_alert(epic.identifier)
            return False

        # Conditions 2 + 3: per-child branch-merge check.
        merged_summaries: list[str] = []
        unmerged_children: list[tuple[Issue, ReviewRequest | None]] = []
        project = self.project_store.get(epic.project_id) if epic.project_id else None
        target_branch = (project.default_branch or "main") if project else "main"

        # Children of stacked/shared epics target the epic's own
        # branch (``epic-<identifier>``), not ``project.default_branch`` —
        # the epic→main merge happens via ``_open_epic_main_prs``.
        # For flat mode the expected child target is project.default_branch.
        try:
            expected_child_target = self._epic_branch_for_issue(epic)
        except Exception:
            expected_child_target = target_branch

        provider = None
        slug = ""
        if project and project.repo_url:
            try:
                provider = detect_provider(
                    project.repo_url,
                    access_token=project.access_token,
                )
                slug = extract_repo_slug(project.repo_url)
            except Exception as exc:
                logger.debug(
                    "Failed to resolve SCM provider for epic %s: %s",
                    epic.identifier,
                    exc,
                )

        for child in children:
            branch = (child.branch_name or "").strip()
            review: ReviewRequest | None = None
            if branch and provider is not None and slug:
                try:
                    review = provider.find_pr_for_branch(slug, branch)
                except Exception as exc:
                    logger.debug(
                        "find_pr_for_branch failed for %s (%s): %s",
                        child.identifier,
                        branch,
                        exc,
                    )
                    review = None

            if review is None:
                # Condition 3: no PR ever opened for this branch — treat
                # as a research/triage closure that needs no merge check.
                merged_summaries.append(f"{child.identifier} (closed without PR)")
                continue

            if review.state == "merged":
                # Verify the merge landed on the expected target.
                merged_target = (review.target_branch or "").strip()
                if not merged_target or merged_target == expected_child_target:
                    merged_summaries.append(
                        f"{child.identifier} (merged via PR #{review.id})"
                    )
                elif merged_target == target_branch:
                    # The child bypassed the epic branch and landed directly on
                    # the epic's final target.  That is already merged
                    # downstream, so keeping the epic permanently stuck would
                    # only require manual tracker surgery.
                    merged_summaries.append(
                        f"{child.identifier} (merged directly to "
                        f"{target_branch} via PR #{review.id})"
                    )
                else:
                    # Merged but to an unexpected branch.
                    unmerged_children.append((child, review))
                continue

            # PR exists but is open or closed-without-merge — stuck.
            unmerged_children.append((child, review))

        if unmerged_children:
            self._arm_stuck_epic_alert(
                epic,
                unmerged_children,
                expected_child_target,
            )
            return False

        # Additional gate: the epic's OWN branch (``epic-<id>``) must be merged
        # to ``project.default_branch`` before we auto-close.  Otherwise we'd
        # close the task while its merge-train work is still pending.
        # No "stuck_epic" alert is raised here — the epic→main PR is
        # owned by ``_open_epic_main_prs`` and merging is the
        # operator's responsibility.
        if provider is None or not slug:
            # Can't verify — fail closed (don't auto-close).
            return False
        try:
            epic_branch = self._epic_branch_for_issue(epic)
        except Exception:
            return False
        try:
            epic_review = provider.find_pr_for_branch(slug, epic_branch)
        except Exception as exc:
            logger.debug(
                "find_pr_for_branch failed for epic branch %s: %s",
                epic_branch,
                exc,
            )
            return False
        if (
            epic_review is None
            or epic_review.state != "merged"
            or (
                epic_review.target_branch
                and epic_review.target_branch != target_branch
            )
        ):
            # Epic branch hasn't merged to main yet — still pending,
            # not stuck.
            self._clear_stuck_epic_alert(epic.identifier)
            return False

        # All conditions hold — close + comment.
        reason = (
            f"Auto-closed: all {len(children)} children closed and merged "
            f"to {expected_child_target}.\n"
            f"Children: " + ", ".join(merged_summaries)
        )
        try:
            tracker = self._tracker_for_issue(epic)
            tracker.close_issue(epic.identifier, reason=reason)
            self._clear_stuck_epic_alert(epic.identifier)
            logger.info(
                "Auto-closed epic %s — all %d children closed and merged to %s",
                epic.identifier,
                len(children),
                expected_child_target,
            )
            return True
        except Exception as exc:
            logger.warning(
                "Failed to auto-close epic %s: %s",
                epic.identifier,
                exc,
            )
            return False

    def _arm_stuck_epic_alert(
        self,
        epic: Issue,
        unmerged: list[tuple[Issue, "ReviewRequest | None"]],
        target_branch: str,
    ) -> None:
        """Add (or replace) a ``stuck_epic`` alert for one epic.

        Triggered when every child is closed but at least one child
        has an unmerged branch — Condition 2 of the auto-close gate
        fails. The alert is keyed on ``source='stuck_epic'`` and the
        epic identifier, so re-arming is idempotent.
        """
        source = f"stuck_epic:{epic.identifier}"
        details: list[str] = []
        for child, review in unmerged:
            if review is None:
                details.append(
                    f"{child.identifier} (branch {child.branch_name or '?'})"
                )
            elif review.state == "merged":
                details.append(
                    f"{child.identifier} (PR #{review.id} merged to "
                    f"{review.target_branch or '?'}, expected {target_branch})"
                )
            else:
                details.append(f"{child.identifier} (PR #{review.id} {review.state})")
        message = (
            f"Epic {epic.identifier} has {len(unmerged)} child(ren) closed "
            f"with unmerged branches: " + ", ".join(details)
        )
        # Drop any prior alert for this epic, then re-arm.
        self._alerts = [a for a in self._alerts if a.get("source") != source]
        self._alerts.append(
            {
                "level": "warning",
                "source": source,
                "message": message,
            }
        )

    def _clear_stuck_epic_alert(self, epic_identifier: str) -> None:
        """Drop any ``stuck_epic`` alert previously armed for this epic."""
        source = f"stuck_epic:{epic_identifier}"
        before = len(self._alerts)
        self._alerts = [a for a in self._alerts if a.get("source") != source]
        if len(self._alerts) != before:
            logger.debug(
                "Cleared stuck_epic alert for %s",
                epic_identifier,
            )

    # ------------------------------------------------------------------
    # Epic branch staleness detection (oompah-zlz_2-82dr.1)
    # ------------------------------------------------------------------

    def _check_epic_staleness(self, candidates: list[Issue]) -> int:
        """Check staleness of epic branches and arm/clear alerts.

        For each active epic, compares the epic branch's merge-base
        with the target branch (usually ``main``). Triggers when:

        1. The epic branch is behind by at least
           ``epic_staleness_threshold_commits`` commits, OR
        2. Any of the intervening commits on main touch files that the
           epic branch also modifies.

        Surfaces staleness via the alert system
        (``source='epic_stale:<epic_identifier>'``) so the dashboard
        can show which epics need rebasing.

        Also transitions ``_epic_rebase_states``: stale → STALE,
        rebase-succeeded → REBASED, stuck-rebasing → FAILED.

        Returns the number of stale epics detected (for telemetry).
        """
        from oompah.epic_staleness import check_epic_branch_staleness
        from oompah.models import EpicRebaseState

        stale_count = 0
        threshold = self.config.epic_staleness_threshold_commits
        if threshold <= 0:
            return 0

        rebase_timeout_s = 1800.0  # 30 min timeout for a rebase agent

        for issue in candidates:
            if _is_terminal_state(issue.state, self.config.tracker_terminal_states):
                continue

            project_id = issue.project_id
            if not project_id:
                continue

            if (
                (issue.issue_type or "").strip().lower() != "epic"
                and not self._issue_has_children(issue)
            ):
                continue

            project = self.project_store.get(project_id)
            if not project or not project.repo_path:
                continue

            epic_branch = self.project_store.epic_branch_name(issue.identifier)
            target_branch = self._resolve_epic_target_branch(issue, project) or "main"
            current_state = self._get_epic_rebase_state(issue.identifier)
            entry = self._epic_rebase_states.get(issue.identifier)

            try:
                result = check_epic_branch_staleness(
                    project.repo_path,
                    epic_branch,
                    target_branch,
                    threshold_commits=threshold,
                )
            except Exception as exc:
                logger.debug(
                    "Staleness check failed for epic %s: %s",
                    issue.identifier,
                    exc,
                )
                self._clear_epic_stale_alert(issue.identifier)
                # If rebase has been in-flight for too long, mark failed
                if current_state == EpicRebaseState.REBASING and entry:
                    if time.time() - entry.updated_at > rebase_timeout_s:
                        self._mark_rebase_failed(issue.identifier, project_id=project_id)
                continue

            if result.stale:
                stale_count += 1
                self._arm_epic_stale_alert(
                    issue,
                    project,
                    result,
                    target_branch=target_branch,
                )
                # Set STALE state if not already tracking something active
                if current_state in (None, EpicRebaseState.REBASED):
                    self._set_epic_rebase_state(
                        issue.identifier,
                        EpicRebaseState.STALE,
                        project_id=project_id,
                    )
                elif current_state == EpicRebaseState.REBASING and entry:
                    if time.time() - entry.updated_at > rebase_timeout_s:
                        logger.warning(
                            "Epic %s rebase stuck (>%.0f min), marking failed",
                            issue.identifier,
                            rebase_timeout_s / 60.0,
                        )
                        self._mark_rebase_failed(issue.identifier, project_id=project_id)
            else:
                self._clear_epic_stale_alert(issue.identifier)
                if current_state == EpicRebaseState.REBASING:
                    # Rebase succeeded — epic is no longer stale
                    self._set_epic_rebase_state(
                        issue.identifier,
                        EpicRebaseState.REBASED,
                        project_id=project_id,
                    )
                elif current_state == EpicRebaseState.STALE:
                    # Staleness cleared (e.g., manual rebase)
                    self._clear_epic_rebase_state(
                        issue.identifier, project_id=project_id
                    )

        return stale_count

    def _arm_epic_stale_alert(
        self,
        epic: Issue,
        project,
        result,
        *,
        target_branch: str | None = None,
    ) -> None:
        """Add (or replace) an ``epic_stale`` alert for one epic.

        The alert is keyed on ``source='epic_stale:<epic_identifier>'``.
        """
        source = f"epic_stale:{epic.identifier}"
        target_branch = target_branch or project.default_branch or "main"

        # Drop existing alert for this epic (if any)
        self._alerts = [
            a for a in self._alerts if a.get("source") != source
        ]

        shared_files_hint = ""
        if result.shared_files:
            files = ", ".join(result.shared_files[:10])
            if len(result.shared_files) > 10:
                files += f" (+{len(result.shared_files) - 10} more)"
            shared_files_hint = f"\n\nOverlapping files: {files}"

        title = (
            f"Epic {epic.identifier} on {project.name} "
            f"is {result.commits_behind} commits behind "
            f"{target_branch}"
        )
        detail = (
            f"The epic branch for {epic.identifier} is "
            f"{result.commits_behind} commits behind "
            f"the target branch (threshold: "
            f"{result.threshold}).{shared_files_hint}"
        )
        rebase_state = self._get_epic_rebase_state(epic.identifier)
        if rebase_state == EpicRebaseState.FAILED:
            action = (
                "Oompah already filed a rebase task for this epic, but the "
                "last rebase run failed. Open the epic's rebase child task "
                "and finish or retry the rebase; this alert clears after "
                "the epic branch catches up."
            )
        elif rebase_state == EpicRebaseState.REBASING:
            action = (
                "Oompah has a rebase task in flight or queued for this epic. "
                "This alert clears after the epic branch catches up."
            )
        else:
            action = (
                "Oompah will file a high-priority rebase task for this epic "
                "and reuse any open rebase child task. This alert clears "
                "after the epic branch catches up."
            )

        self._alerts.append(
            {
                "source": source,
                "level": "warning",
                "title": title,
                "message": f"{title}. {action}",
                "detail": detail,
                "action": action,
                "epic_identifier": epic.identifier,
                "project_id": epic.project_id,
                "project_name": project.name,
                "target_branch": target_branch,
                "commits_behind": result.commits_behind,
            }
        )
        logger.info(
            "Armed epic_stale alert for %s: %d commits behind, "
            "%d overlapping files",
            epic.identifier,
            result.commits_behind,
            len(result.shared_files),
        )

    def _clear_epic_stale_alert(self, epic_identifier: str) -> None:
        """Drop any ``epic_stale`` alert previously armed for this epic."""
        source = f"epic_stale:{epic_identifier}"
        before = len(self._alerts)
        self._alerts = [
            a for a in self._alerts if a.get("source") != source
        ]
        if len(self._alerts) != before:
            logger.debug(
                "Cleared epic_stale alert for %s",
                epic_identifier,
            )

    def _maybe_auto_close_parent_epic(self, child: Issue | None) -> None:
        """If ``child`` has a parent epic, evaluate the parent for auto-close.

        Called from the worker-exit success path (oompah-zlz_2-lvcd) so
        the epic auto-close gate fires reactively when the last child
        closes, instead of waiting for the next full-sync tick. Failures
        are logged but never raised — this is best-effort.

        Cascading is handled implicitly: when a mid-tier epic closes
        here, the next tick's :meth:`_auto_close_completed_epics` sweep
        will pick up its grandparent.
        """
        if child is None:
            return
        parent_id = (child.parent_id or "").strip()
        if not parent_id:
            return
        parent_epic = self._resolve_parent_epic(child)
        if parent_epic is None:
            return
        try:
            self._epic_auto_close_check(parent_epic)
        except Exception as exc:
            logger.warning(
                "Epic auto-close check failed for %s: %s",
                parent_epic.identifier,
                exc,
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

    def _pending_epic_rollup_dependency(
        self,
        epic: Issue,
    ) -> tuple[str, str] | None:
        """Return the first dependency that has not landed for epic rollup.

        Dispatch can treat a blocker in ``Done`` as sufficient because the
        dependent worker may still run before final merge.  Epic rollup PRs are
        different: opening the dependent epic-to-main PR before its prerequisite
        epic lands can consume review capacity and merge work out of order.
        """
        for blocker in epic.blocked_by or []:
            blocker_id = (
                getattr(blocker, "identifier", None)
                or getattr(blocker, "id", None)
                or ""
            )
            if not blocker_id:
                continue
            blocker_state = getattr(blocker, "state", None) or ""
            if not blocker_state:
                blocker_state = self._resolve_blocker_state(blocker, epic)
            status = canonicalize_status(blocker_state)
            if status not in {MERGED, ARCHIVED}:
                return blocker_id, status or blocker_state or "unknown"
        return None

    def _open_epic_main_prs(self, candidates: list[Issue]) -> int:
        """Open epic completion PRs for epics whose children are all closed.

        For each active epic in ``candidates``:

        * If it has no children, skip (nothing has been done — wait for
          the planner).
        * If any child is NOT in a terminal state (open, in_progress,
          deferred, blocked, ...), skip — mid-flight children DELAY the
          push (acceptance criteria explicit edge case).
        * If a PR with source ``epic-<identifier>`` already exists, skip
          — idempotent.
        * Otherwise: push the epic branch and open a single
          source=``epic-<identifier>`` PR targeting the resolved branch:

          - For top-level epics (no parent epic): targets
            ``project.default_branch`` (typically ``main``).
          - For nested epics (the epic itself has a parent epic): targets
            the parent epic's branch. This creates a multi-level merge
            chain where child epic B's PR targets parent A's branch; A's
            PR targets main only when ALL of A's direct children
            (including sub-epic B) are terminal.

        Returns the number of PRs opened.
        """
        opened = 0
        opened_by_project: dict[str, int] = {}
        for issue in candidates:
            if canonicalize_status(issue.state) in {MERGED, ARCHIVED}:
                continue  # epic itself has already landed or been discarded
            project_id = issue.project_id
            if not project_id:
                continue
            children = self._fetch_epic_children(issue)
            if not children:
                continue  # not a rollup parent / nothing to roll up yet

            # All children must be in a terminal state. open / in_progress /
            # deferred / blocked all DELAY the push (per the acceptance
            # criteria). This intentionally treats deferred or blocked as
            # incomplete — operator action required to advance them.
            #
            # Judge each child from the EPIC BRANCH (where shared children
            # record their status), not the default branch the tracker reads —
            # the latter only catches up once this very PR lands, so reading
            # it would deadlock the gate. See _epic_child_effective_state.
            child_states = [
                self._epic_child_effective_state(issue, c) for c in children
            ]
            # Ignore pre-implementation wrapper states the same way
            # epic_rollup_state does, then require every actionable child to
            # be terminal. Child epics that are already Merged may only have
            # landed into this parent epic branch; they still make the parent
            # ready for its own PR rather than proving the parent landed.
            child_statuses = [
                canonicalize_status(status)
                for status in child_states
                if canonicalize_status(status) not in {PROPOSED, DECOMPOSED}
            ]
            if not child_statuses:
                continue
            if any(
                status not in {DONE, MERGED, ARCHIVED}
                for status in child_statuses
            ):
                continue
            if all(status == ARCHIVED for status in child_statuses):
                continue

            pending_dependency = self._pending_epic_rollup_dependency(issue)
            if pending_dependency is not None:
                blocker_id, blocker_state = pending_dependency
                logger.info(
                    "Deferred epic PR for %s: dependency %s is %s; waiting "
                    "for it to land",
                    issue.identifier,
                    blocker_id,
                    blocker_state,
                )
                continue

            project = self.project_store.get(project_id)
            if not project or not project.repo_url:
                continue
            epic_branch = self._epic_branch_for_issue(issue)
            if not self._has_epic_landing_ref(
                project,
                issue.identifier,
                epic_branch=epic_branch,
            ):
                logger.debug(
                    "Skipping epic rollup %s on %s: no epic branch "
                    "or worktree exists",
                    issue.identifier,
                    project.name,
                )
                continue
            provider = detect_provider(
                project.repo_url,
                access_token=project.access_token,
            )
            if provider is None:
                continue
            slug = extract_repo_slug(project.repo_url)
            target_branch = self._resolve_epic_target_branch(issue, project)

            # Authoritative already-landed check — MUST come before the
            # open-PR idempotency check below. A shared epic lands exactly
            # once; if any epic→main PR from this branch has ALREADY merged,
            # the epic is done. Re-opening/re-merging it is the squash-merge
            # loop: a squash merge never makes the branch an ancestor of main,
            # so the branch perpetually looks "ahead" and the rollup stays
            # == Done. The async _merged_branches set (which drives
            # _label_merged_epics) is targetless, and an epic branch can be a
            # child PR into an intermediate parent branch before it is the
            # parent PR into main. Ask the forge for source+target metadata so
            # only the resolved final target marks this epic Merged.
            if self._epic_branch_landed_on_target(
                provider,
                slug,
                epic_branch,
                target_branch,
            ):
                logger.info(
                    "Epic %s already landed (PR from %s merged to %s); "
                    "marking Merged instead of re-opening",
                    issue.identifier,
                    epic_branch,
                    target_branch,
                )
                self._mark_epic_merged(issue, epic_branch=epic_branch)
                continue

            # Idempotency: if a (first-landing) review already exists with this
            # source branch, do nothing — let it run through CI/merge. The
            # in-memory review cache can lag a freshly opened PR, so fall back
            # to the forge before pushing/creating another PR.
            existing_review = self._find_open_epic_review(
                provider,
                slug,
                project_id,
                epic_branch,
            )
            if existing_review is not None:
                self._ensure_epic_in_review_metadata(
                    project_id,
                    issue,
                    existing_review,
                    epic_branch,
                )
                continue

            n_open, limit, at_capacity = self._project_review_capacity(project_id)
            reserved = opened_by_project.get(project_id, 0)
            if at_capacity or n_open + reserved >= limit:
                logger.info(
                    "Deferred epic PR for %s on %s: project review cap "
                    "reached (%d/%d)",
                    issue.identifier,
                    project.name,
                    n_open + reserved,
                    limit,
                )
                continue

            if not self._ensure_review_target_branch_exists(project, target_branch):
                logger.warning(
                    "Deferred epic PR for %s on %s: target branch %s is not "
                    "available",
                    issue.identifier,
                    project.name,
                    target_branch,
                )
                continue

            # Push the epic branch from the shared epic worktree (shared
            # mode) or from the project's main repo path (stacked mode —
            # children's PRs already pushed their commits to the epic
            # branch on the remote).
            try:
                default_epic_branch = self.project_store.epic_branch_name(
                    issue.identifier
                )
                if epic_branch == default_epic_branch:
                    self._push_epic_branch(project, issue.identifier)
                else:
                    self._push_epic_branch(
                        project,
                        issue.identifier,
                        epic_branch=epic_branch,
                    )
            except Exception as exc:
                if not self._remote_epic_branch_has_unmerged_work(
                    project,
                    target_branch,
                    epic_branch,
                ):
                    logger.warning(
                        "Failed to push epic branch %s for epic %s: %s",
                        epic_branch,
                        issue.identifier,
                        exc,
                    )
                    continue
                logger.warning(
                    "Using existing remote epic branch %s for epic %s after "
                    "local push failed: %s",
                    epic_branch,
                    issue.identifier,
                    exc,
                )

            title = (
                f"{issue.identifier}: {issue.title}"
                if issue.title
                else f"Epic {issue.identifier}"
            )
            description = issue.description or ""
            hub_link = self._build_pr_body(
                issue,
                target_branch,
                slug,
                project.default_branch,
            )
            if hub_link:
                description = f"{hub_link}\n\n{description}".strip() if description else hub_link
            try:
                result = provider.create_review(
                    slug,
                    title,
                    epic_branch,
                    target_branch=target_branch,
                    description=description,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to create epic PR for %s on %s (target=%s): %s",
                    issue.identifier,
                    project.name,
                    target_branch,
                    exc,
                )
                continue

            if result is None:
                logger.warning(
                    "Failed to create epic PR for %s on %s (target=%s) "
                    "(provider returned None)",
                    issue.identifier,
                    project.name,
                    target_branch,
                )
                continue

            logger.info(
                "Opened epic PR for %s on %s (review #%s, source=%s, target=%s)",
                issue.identifier,
                project.name,
                result.id,
                epic_branch,
                target_branch,
            )
            # Persist review metadata on the epic task record (TASK-462.2).
            try:
                tracker = self._tracker_for_project(project_id)
                tracker.update_issue(issue.identifier, status=IN_REVIEW)
                self._write_review_metadata(
                    tracker,
                    issue.identifier,
                    review_id=getattr(result, "id", None),
                    review_url=getattr(result, "url", None),
                    source_branch=epic_branch,
                    target_branch=target_branch,
                )
                self._sync_epic_review_child_states(
                    project_id,
                    issue,
                    epic_branch,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to write review metadata for epic %s: %s",
                    issue.identifier,
                    exc,
                )
            opened += 1
            opened_by_project[project_id] = reserved + 1
        return opened

    def _find_open_epic_review(
        self,
        provider: Any,
        slug: str,
        project_id: str,
        epic_branch: str,
    ) -> ReviewRequest | Any | None:
        """Return an open review for ``epic_branch`` from cache or forge."""
        reviews = getattr(self, "_reviews_cache", {}).get(project_id, []) or []
        for review in reviews:
            if self._review_matches_open_branch(review, epic_branch):
                return review

        try:
            review = provider.find_pr_for_branch(slug, epic_branch)
        except Exception as exc:  # noqa: BLE001 - best-effort idempotency guard
            logger.debug(
                "find_pr_for_branch failed while checking epic PR %s/%s: %s",
                slug,
                epic_branch,
                exc,
            )
            return None
        if self._review_matches_open_branch(review, epic_branch):
            return review
        return None

    def _epic_branch_landed_on_target(
        self,
        provider: Any,
        slug: str,
        epic_branch: str,
        target_branch: str,
    ) -> bool:
        """True when ``epic_branch`` has a merged review to ``target_branch``."""
        source = str(epic_branch or "").strip()
        target = str(target_branch or "").strip()
        if provider is None or not slug or not source or not target:
            return False

        def matches(review: Any) -> bool:
            if review is None:
                return False
            return (
                str(getattr(review, "state", "") or "").lower() == "merged"
                and str(getattr(review, "source_branch", "") or "").strip() == source
                and str(getattr(review, "target_branch", "") or "").strip() == target
            )

        list_merged_reviews = getattr(provider, "list_merged_reviews", None)
        if callable(list_merged_reviews):
            try:
                reviews = list_merged_reviews(slug) or []
            except Exception as exc:  # noqa: BLE001 - best effort
                logger.debug(
                    "list_merged_reviews failed for %s branch %s: %s",
                    slug,
                    source,
                    exc,
                )
            else:
                for review in reviews:
                    if matches(review):
                        return True

        try:
            review = provider.find_pr_for_branch(slug, source)
        except Exception as exc:  # noqa: BLE001 - best effort
            logger.debug(
                "find_pr_for_branch failed while checking merged epic %s/%s: %s",
                slug,
                source,
                exc,
            )
            return False
        return matches(review)

    @staticmethod
    def _review_matches_open_branch(review: Any, branch: str) -> bool:
        """True when ``review`` is an open PR/MR from ``branch``."""
        if review is None:
            return False
        source = str(getattr(review, "source_branch", "") or "")
        if source != branch:
            return False
        state = str(getattr(review, "state", "open") or "open").lower()
        return state == "open"

    def _ensure_epic_in_review_metadata(
        self,
        project_id: str,
        issue: Issue,
        review: ReviewRequest | Any,
        epic_branch: str,
    ) -> None:
        """Keep an epic task aligned when the review already exists."""
        try:
            tracker = self._tracker_for_project(project_id)
            if canonicalize_status(issue.state) != IN_REVIEW:
                tracker.update_issue(issue.identifier, status=IN_REVIEW)
            self._write_review_metadata(
                tracker,
                issue.identifier,
                review_id=getattr(review, "id", None),
                review_url=getattr(review, "url", None),
                source_branch=getattr(review, "source_branch", None) or epic_branch,
                target_branch=getattr(review, "target_branch", None),
            )
            self._sync_epic_review_child_states(
                project_id,
                issue,
                epic_branch,
            )
        except Exception as exc:  # noqa: BLE001 - metadata alignment is best-effort
            logger.warning(
                "Failed to sync existing epic PR metadata for %s: %s",
                issue.identifier,
                exc,
            )

    def _sync_epic_review_child_states(
        self,
        project_id: str,
        epic: Issue,
        epic_branch: str,
        *,
        children: list[Issue] | None = None,
    ) -> int:
        """Reconcile Done epic children after the epic review PR exists.

        ``Done`` means the child agent says its work is complete. Once the
        epic has an open rollup PR, stacked-mode child implementation work is
        in review through that epic PR and should not remain visibly stranded
        in Done. Shared-mode children are already complete once their work is
        on the epic branch; the epic owns the review/CI/rebase state. If a Done
        child has no evidence on the epic branch, reopen it so an agent can do
        the missing work.
        """
        project = self.project_store.get(project_id)
        if project is None:
            return 0
        try:
            tracker = self._tracker_for_project(project_id)
            if children is None:
                children = self._fetch_epic_children(epic)
        except Exception as exc:  # noqa: BLE001 - best-effort reconciliation
            logger.debug(
                "Failed to sync review child states for epic %s: %s",
                epic.identifier,
                exc,
            )
            return 0

        moved = 0
        for child in children:
            if canonicalize_status(child.state) != DONE:
                continue
            if self._done_review_child_is_completed_maintenance(child):
                next_status = MERGED
                reason = "completed maintenance child"
            elif self._done_review_child_has_epic_branch_work(
                project,
                epic_branch,
                child,
            ):
                # Shared-mode children are already complete once their work is
                # on the epic branch; the epic owns the review/CI/rebase state.
                logger.info(
                    "Leaving Done child %s under epic %s in Done "
                    "(covered by epic review branch %s)",
                    child.identifier,
                    epic.identifier,
                    epic_branch,
                )
                continue
            else:
                next_status = OPEN
                reason = "no matching work found on epic review branch"
            try:
                tracker.update_issue(child.identifier, status=next_status)
                child.state = next_status
                moved += 1
                logger.info(
                    "Moved Done child %s under epic %s to %s (%s)",
                    child.identifier,
                    epic.identifier,
                    next_status,
                    reason,
                )
            except TrackerError as exc:
                logger.debug(
                    "Failed to move Done child %s under epic %s to %s: %s",
                    child.identifier,
                    epic.identifier,
                    next_status,
                    exc,
                )
        return moved

    @staticmethod
    def _done_review_child_is_completed_maintenance(child: Issue) -> bool:
        """Return True for Done helper tasks that do not carry review code."""
        title = str(child.title or "").strip().lower()
        labels = {str(label).strip().lower() for label in child.labels or []}
        if "ci-fix" in labels or "merge-conflict" in labels:
            return False
        return title.startswith("rebase ") and " onto " in title

    def _done_review_child_has_epic_branch_work(
        self,
        project: Project,
        epic_branch: str,
        child: Issue,
    ) -> bool:
        """Return True when the epic review branch contains this child work."""
        if child.work_branch or getattr(child, "review_url", None):
            return True
        repo_path = getattr(project, "repo_path", "") or ""
        if not repo_path or not epic_branch:
            return False
        target_branch = getattr(project, "default_branch", None) or "main"
        ranges = [
            f"origin/{target_branch}..origin/{epic_branch}",
            f"origin/{target_branch}..{epic_branch}",
            f"{target_branch}..origin/{epic_branch}",
            f"{target_branch}..{epic_branch}",
        ]
        needle = child.identifier.lower()
        seen: set[str] = set()
        for ref_range in ranges:
            if ref_range in seen:
                continue
            seen.add(ref_range)
            try:
                result = subprocess.run(
                    ["git", "log", "--format=%s", "--max-count=500", ref_range],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode != 0:
                continue
            for line in result.stdout.splitlines():
                if needle in line.lower():
                    return True
        return False

    def _remote_epic_branch_has_unmerged_work(
        self,
        project: Any,
        target_branch: str,
        epic_branch: str,
    ) -> bool:
        """Return True when origin has epic work that is not in the target.

        Shared epic worktrees can be left dirty or behind after an agent push.
        In that state the local push path may refuse to proceed even though
        ``origin/<epic_branch>`` already contains the completed work.  The PR
        can still be opened safely from that remote branch when git can prove
        it is ahead of the target branch.
        """
        repo_path = getattr(project, "repo_path", None)
        if not repo_path or not os.path.isdir(repo_path):
            return False
        try:
            subprocess.run(
                ["git", "fetch", "origin", epic_branch],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except Exception:
            pass
        ahead, _lines, error = self._count_review_branch_ahead(
            project,
            target_branch,
            epic_branch,
        )
        if error:
            logger.debug(
                "Remote epic branch ahead check failed for %s against %s: %s",
                epic_branch,
                target_branch,
                error,
            )
            return False
        return ahead > 0

    def _resolve_epic_target_branch(self, epic: Issue, project) -> str:
        """Resolve the target branch for an epic's completion PR.

        For nested epics in ``shared`` mode: if ``epic`` has a parent epic P,
        the completion PR should target P's branch (``epic-<P.identifier>``)
        rather than ``main``. This gives Linux-kernel-style multi-level merge
        trains where each sub-epic lands on its parent's branch before the
        top-level epic lands on main.

        For all other cases (top-level epic, non-shared mode, or no parent
        epic), the PR targets ``project.default_branch`` (typically ``main``).

        For nested epics: if ``epic`` has a parent epic P, the completion PR
        targets P's branch; the top-level epic targets
        ``project.default_branch`` (typically ``main``).
        """
        parent_epic = self._resolve_parent_epic(epic)
        if parent_epic is not None:
            return self._epic_branch_for_issue(parent_epic)
        return project.default_branch

    def _remote_branch_exists(self, repo_path: str, branch: str) -> bool:
        """Return True when ``origin`` already has ``branch``."""
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", "origin", branch],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except Exception:
            return False
        return result.returncode == 0 and bool(result.stdout.strip())

    def _local_ref_exists(self, repo_path: str, ref: str) -> bool:
        """Return True when ``ref`` resolves to a local commit."""
        try:
            result = subprocess.run(
                [
                    "git",
                    "rev-parse",
                    "--verify",
                    "--quiet",
                    f"{ref}^{{commit}}",
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except Exception:
            return False
        return result.returncode == 0

    def _ensure_review_target_branch_exists(
        self,
        project: Any,
        target_branch: str,
    ) -> bool:
        """Ensure a non-default review target branch exists on ``origin``.

        Nested shared epics use the parent epic branch as the child epic PR
        base. GitHub rejects PR creation with ``base invalid`` when that
        branch has not been pushed yet, so create the empty parent branch from
        the default branch before opening the child epic PR.
        """
        target_branch = (target_branch or "").strip()
        if not target_branch:
            return False

        default_branch = str(
            getattr(project, "default_branch", None)
            or getattr(project, "branch", None)
            or "main"
        ).strip()
        if target_branch == default_branch:
            return True

        repo_path = getattr(project, "repo_path", None)
        if not repo_path or not os.path.isdir(repo_path):
            logger.warning(
                "Cannot ensure review target branch %s: repo path is missing",
                target_branch,
            )
            return False

        if self._remote_branch_exists(repo_path, target_branch):
            return True

        subprocess.run(
            ["git", "fetch", "origin", default_branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        if self._local_ref_exists(repo_path, f"refs/heads/{target_branch}"):
            source_ref = f"refs/heads/{target_branch}"
        elif self._local_ref_exists(repo_path, f"refs/remotes/origin/{default_branch}"):
            source_ref = f"refs/remotes/origin/{default_branch}"
        elif self._local_ref_exists(repo_path, f"refs/heads/{default_branch}"):
            source_ref = f"refs/heads/{default_branch}"
        else:
            logger.warning(
                "Cannot create review target branch %s: no default branch ref "
                "%s is available",
                target_branch,
                default_branch,
            )
            return False

        try:
            result = subprocess.run(
                [
                    "git",
                    "push",
                    "origin",
                    f"{source_ref}:refs/heads/{target_branch}",
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except Exception as exc:
            logger.warning(
                "Failed to create review target branch %s from %s: %s",
                target_branch,
                source_ref,
                exc,
            )
            return False

        if result.returncode != 0:
            logger.warning(
                "Failed to create review target branch %s from %s: %s",
                target_branch,
                source_ref,
                result.stderr.strip() or result.stdout.strip(),
            )
            return False
        return True

    def _fast_forward_shared_epic_worktree_if_clean(
        self,
        wt_path: str,
        epic_branch: str,
    ) -> None:
        """Fast-forward a clean shared epic worktree to its remote branch."""
        fetch = subprocess.run(
            ["git", "fetch", "origin", epic_branch],
            cwd=wt_path,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if fetch.returncode != 0:
            logger.debug(
                "Skipping shared epic worktree fast-forward for %s: fetch failed: %s",
                epic_branch,
                fetch.stderr.strip(),
            )
            return

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        if status.stdout.strip():
            return

        ahead_behind = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "HEAD...FETCH_HEAD"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        counts = ahead_behind.stdout.strip().split()
        if len(counts) != 2:
            return
        try:
            ahead, behind = (int(counts[0]), int(counts[1]))
        except ValueError:
            return
        if ahead == 0 and behind > 0:
            subprocess.run(
                ["git", "merge", "--ff-only", "FETCH_HEAD"],
                cwd=wt_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )

    def _push_epic_branch(
        self,
        project,
        epic_identifier: str,
        *,
        epic_branch: str | None = None,
    ) -> None:
        """Push the shared epic branch from the local repo to origin.

        Best-effort: subprocess errors propagate so the caller can log
        and skip PR creation for this tick.
        """
        default_epic_branch = self.project_store.epic_branch_name(epic_identifier)
        epic_branch = epic_branch or default_epic_branch
        push_cwd = project.repo_path
        push_cmd = ["git", "push", "origin", epic_branch]

        if epic_branch == default_epic_branch:
            wt_path = self.project_store.epic_worktree_path_for(
                project.id,
                epic_identifier,
            )
            if os.path.isdir(wt_path):
                self._fast_forward_shared_epic_worktree_if_clean(
                    wt_path,
                    epic_branch,
                )
                push_cwd = wt_path
                push_cmd = ["git", "push", "origin", f"HEAD:{epic_branch}"]

        subprocess.run(
            push_cmd,
            cwd=push_cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )

    # ------------------------------------------------------------------
    # Epic rebase outcome tracking (oompah-zlz_2-82dr.3)
    # ------------------------------------------------------------------

    def _set_epic_rebase_state(
        self,
        epic_identifier: str,
        state: EpicRebaseState,
        *,
        project_id: str | None = None,
    ) -> None:
        """Transition ``epic_identifier`` to ``state`` and sync labels.

        Idempotent: calling twice with the same state is a no-op
        (except for the timestamp update).  Removes any other
        ``epic:*`` labels from the task before adding the new one.
        """
        old_entry = self._epic_rebase_states.get(epic_identifier)
        if old_entry is not None and old_entry.state == state.value:
            # Same state — just refresh the timestamp.
            old_entry.updated_at = time.time()
            self._persist_epic_rebase_states()
            return

        now = time.time()
        old_entry = self._epic_rebase_states.get(epic_identifier)
        retry_count = old_entry.retry_count if old_entry else 0
        # Increment retry count on FAILED transitions
        if state == EpicRebaseState.FAILED and (old_entry is None or old_entry.state != "failed"):
            retry_count += 1
        self._epic_rebase_states[epic_identifier] = EpicRebaseStateEntry(
            state=state.value,
            updated_at=now,
            project_id=project_id,
            retry_count=retry_count,
        )

        # Sync labels on the task.
        try:
            tracker = (
                self._tracker_for_project(project_id)
                if project_id
                else self.tracker
            )
            # Fetch current labels so we can remove stale epic:* ones.
            issue = tracker.fetch_issue_detail(epic_identifier)
            if issue and issue.labels:
                for label in list(issue.labels):
                    parsed = EpicRebaseState.from_label(label)
                    if parsed is not None and parsed != state:
                        tracker.update_issue(
                            epic_identifier,
                            **{"remove-label": label},
                        )
            # Add the new label if not already present.
            if issue is None or state.label not in (issue.labels or []):
                tracker.update_issue(
                    epic_identifier,
                    **{"add-label": state.label},
                )
        except Exception as exc:
            logger.debug(
                "Failed to sync rebase label %s for %s: %s",
                state.label,
                epic_identifier,
                exc,
            )

        self._persist_epic_rebase_states()
        logger.info(
            "Epic %s rebase state -> %s",
            epic_identifier,
            state.value,
        )

    def _get_epic_rebase_state(
        self, epic_identifier: str
    ) -> EpicRebaseState | None:
        """Return the current rebase state for ``epic_identifier``, or None."""
        entry = self._epic_rebase_states.get(epic_identifier)
        if entry is None:
            return None
        try:
            return EpicRebaseState(entry.state)
        except ValueError:
            return None

    def _clear_epic_rebase_state(
        self,
        epic_identifier: str,
        *,
        project_id: str | None = None,
    ) -> None:
        """Drop the tracked rebase state for ``epic_identifier`` and clear labels."""
        removed_entry = self._epic_rebase_states.pop(epic_identifier, None)
        try:
            tracker = (
                self._tracker_for_project(project_id)
                if project_id
                else self.tracker
            )
            issue = tracker.fetch_issue_detail(epic_identifier)
            if issue and issue.labels:
                for label in list(issue.labels):
                    if EpicRebaseState.from_label(label) is not None:
                        tracker.update_issue(
                            epic_identifier,
                            **{"remove-label": label},
                        )
        except Exception as exc:
            logger.debug(
                "Failed to clear rebase labels for %s: %s",
                epic_identifier,
                exc,
            )
        if removed_entry is not None:
            self._persist_epic_rebase_states()
            logger.info("Cleared epic rebase state for %s", epic_identifier)

    def _mark_rebase_failed(
        self,
        epic_identifier: str,
        *,
        project_id: str | None = None,
    ) -> None:
        """Transition an epic to FAILED and increment its retry count.

        Wraps :meth:`_set_epic_rebase_state` so callers don't have to
        remember to bump ``retry_count`` manually.
        """
        self._set_epic_rebase_state(
            epic_identifier,
            EpicRebaseState.FAILED,
            project_id=project_id,
        )

    def _prune_stale_epic_rebase_states(self, candidates: list[Issue]) -> None:
        """Drop rebase state for epics that are no longer active candidates.

        Called once per tick after candidate fetch so closed/merged
        epics don't accumulate ghost state forever.
        """
        active_epic_ids = {
            issue.identifier
            for issue in candidates
            if issue.issue_type == "epic"
            and not _is_terminal_state(
                issue.state, self.config.tracker_terminal_states
            )
        }
        stale = [
            epic_id
            for epic_id in self._epic_rebase_states
            if epic_id not in active_epic_ids
        ]
        for epic_id in stale:
            entry = self._epic_rebase_states.pop(epic_id)
            self._clear_epic_stale_alert(epic_id)
            logger.debug(
                "Pruned stale epic rebase state for %s (was %s)",
                epic_id,
                entry.state,
            )
        if stale:
            self._persist_epic_rebase_states()

    def _should_dispatch_rebase_agent(self, epic_identifier: str) -> bool:
        """Idempotency gate: should we dispatch a rebase agent for this epic?

        Returns ``False`` when:
        - the epic is ``REBASING`` and the 30-minute in-flight timeout
          has not yet elapsed;
        - the epic is ``FAILED`` and the exponential backoff window
          (``300s * 2^retry_count``, capped at 3600s) has not elapsed.

        Returns ``True`` for ``STALE``, ``REBASED``, no state, or when
        the respective timeout/backoff has elapsed.
        """
        entry = self._epic_rebase_states.get(epic_identifier)
        state = self._get_epic_rebase_state(epic_identifier)
        if state == EpicRebaseState.REBASING:
            timeout_s = 1800.0  # 30 minutes
            if entry and time.time() - entry.updated_at < timeout_s:
                logger.debug(
                    "Skipping rebase dispatch for %s: already rebasing",
                    epic_identifier,
                )
                return False
            logger.warning(
                "Rebase dispatch for %s: rebasing timeout elapsed, allowing retry",
                epic_identifier,
            )
            return True
        if state == EpicRebaseState.FAILED:
            if entry:
                backoff_s = min(300 * (2 ** entry.retry_count), 3600)
                elapsed = time.time() - entry.updated_at
                if elapsed < backoff_s:
                    logger.debug(
                        "Skipping rebase dispatch for %s: backoff %.0fs/%.0fs",
                        epic_identifier,
                        elapsed,
                        backoff_s,
                    )
                    return False
        return True

    def _is_epic_branch_being_rebased(
        self, project_id: str, source_branch: str | None
    ) -> bool:
        """Return True if ``source_branch`` is an epic branch with a
        proactive rebase currently in flight.

        Used by YOLO to suppress redundant conflict-agent dispatch
        when the orchestrator has already filed a rebase task for
        the epic (oompah-zlz_2-82dr.2).
        """
        if not source_branch or not source_branch.startswith("epic-"):
            return False
        for identifier, entry in self._epic_rebase_states.items():
            if entry.project_id != project_id:
                continue
            expected = self.project_store.epic_branch_name(identifier)
            if expected == source_branch:
                state = self._get_epic_rebase_state(identifier)
                if state == EpicRebaseState.REBASING:
                    return True
        return False

    def _dispatch_proactive_rebase_agents(self, candidates: list[Issue]) -> int:
        """Mark stale review-ready epics for rebase, or file helper tasks.

        Iterates over ``candidates`` looking for epics in ``STALE`` or
        ``FAILED`` state (or ``REBASING`` when the in-flight timeout has
        elapsed).  Once all children have reached review/terminal states,
        the epic itself is the dispatchable repair unit.  Earlier rollups
        keep the legacy sibling task fallback.

        Idempotent: checks for an existing open ``merge-conflict``
        sibling before creating a new one.

        Returns the number of rebase tasks filed.
        """
        from oompah.models import EpicRebaseState

        filed = 0
        for issue in candidates:
            if _is_terminal_state(issue.state, self.config.tracker_terminal_states):
                continue
            is_declared_epic = (issue.issue_type or "").strip().lower() == "epic"
            if not is_declared_epic and not self._issue_has_children(issue):
                continue

            state = self._get_epic_rebase_state(issue.identifier)
            if state not in (
                EpicRebaseState.STALE,
                EpicRebaseState.FAILED,
                EpicRebaseState.REBASING,
            ):
                continue
            if not self._should_dispatch_rebase_agent(issue.identifier):
                continue

            project = self.project_store.get(issue.project_id)
            if not project:
                continue
            epic_branch = self.project_store.epic_branch_name(issue.identifier)
            target_branch = self._resolve_epic_target_branch(issue, project) or "main"

            try:
                tracker = self._tracker_for_project(issue.project_id)
                children = self._fetch_epic_children(issue)
                if self._is_mature_epic_review_issue(issue, children):
                    self._mark_epic_review_repair_issue(
                        tracker,
                        issue,
                        status=NEEDS_REBASE,
                        label="merge-conflict",
                        source_branch=epic_branch,
                        target_branch=target_branch,
                        comment=(
                            f"The epic branch `{epic_branch}` is stale: it has "
                            f"fallen behind `{target_branch}`. Rebase the branch "
                            f"onto `origin/{target_branch}`, resolve any "
                            "conflicts, and force-push with "
                            "`git push --force-with-lease`."
                        ),
                    )
                    self._set_epic_rebase_state(
                        issue.identifier,
                        EpicRebaseState.REBASING,
                        project_id=issue.project_id,
                    )
                    filed += 1
                    continue

                # Idempotency: don't file duplicate if an actionable rebase
                # sibling already exists under this epic.
                open_rebase = self._find_active_epic_rebase_sibling(
                    tracker,
                    issue,
                )
                if open_rebase is not None:
                    logger.debug(
                        "Rebase sibling %s already open for %s — skipping",
                        open_rebase.identifier,
                        issue.identifier,
                    )
                    # Ensure state reflects the in-flight sibling
                    self._set_epic_rebase_state(
                        issue.identifier,
                        EpicRebaseState.REBASING,
                        project_id=issue.project_id,
                    )
                    continue

                self._file_rebase_task(
                    tracker, issue, epic_branch, target_branch
                )
                self._set_epic_rebase_state(
                    issue.identifier,
                    EpicRebaseState.REBASING,
                    project_id=issue.project_id,
                )
                filed += 1
            except Exception as exc:
                logger.warning(
                    "Failed to file rebase task for %s: %s",
                    issue.identifier,
                    exc,
                )

        return filed

    def _file_rebase_task(
        self,
        tracker,
        epic: Issue,
        epic_branch: str,
        target_branch: str,
    ) -> None:
        """Create a sibling task task under ``epic`` to rebase the epic branch.

        The task is labelled ``merge-conflict`` so the dispatcher routes
        it to the merge-conflict focus, which already knows how to
        ``git rebase origin/<target>`` and force-push.
        """
        title = f"Rebase {epic_branch} onto {target_branch}"
        description = (
            f"The epic branch `{epic_branch}` is stale: it has fallen "
            f"behind `{target_branch}`. Rebase the branch onto "
            f"`origin/{target_branch}`, resolve any conflicts, and "
            f"force-push with `git push --force-with-lease`.\n\n"
            f"This task was auto-filed because epic {epic.identifier} "
            f"was detected as stale. Do NOT create a new branch or PR — "
            f"work directly on `{epic_branch}`."
        )
        tracker.create_issue(
            title=title,
            issue_type="task",
            description=description,
            # P0: a rebase task resolves a merge conflict on the epic branch and
            # opens NO new PR, so it must bypass the in-flight-PR cap. Dispatch
            # still serializes multiple rebase siblings for the same epic branch;
            # only one agent may force-push a shared branch at a time.
            priority=0,
            parent=epic.identifier,
            initial_status=NEEDS_REBASE,
        )
        logger.info(
            "Filed rebase task for %s (branch=%s, target=%s)",
            epic.identifier,
            epic_branch,
            target_branch,
        )

    def _mark_epic_review_repair_issue(
        self,
        tracker,
        issue: Issue,
        *,
        status: str,
        label: str,
        source_branch: str | None = None,
        target_branch: str | None = None,
        review_id: str | None = None,
        review_url: str | None = None,
        comment: str | None = None,
    ) -> None:
        """Move a mature epic/rollup into a dispatchable repair state.

        This is intentionally different from filing a sibling helper task:
        once the children are complete, CI/rebase work belongs to the epic PR
        itself and must run on the epic branch.
        """
        current_status = canonicalize_status(issue.state)
        labels = {str(value).strip().lower() for value in issue.labels or []}
        clean_source = str(source_branch or "").strip()
        clean_target = str(target_branch or "").strip()
        if clean_source:
            issue.work_branch = clean_source
            issue.branch_name = clean_source
        if clean_target:
            issue.target_branch = clean_target

        if clean_source or clean_target or review_id or review_url:
            self._write_review_metadata(
                tracker,
                issue.identifier,
                review_id=str(review_id) if review_id else None,
                review_url=review_url if isinstance(review_url, str) else None,
                source_branch=clean_source or None,
                target_branch=clean_target or None,
            )

        if current_status == status and label in labels:
            if issue.id:
                self.state.completed.discard(issue.id)
            return

        tracker.update_issue(
            issue.identifier,
            status=status,
            priority="0",
            **{"add-label": label},
        )
        issue.state = status
        issue.priority = 0
        current_labels = list(issue.labels or [])
        if label not in current_labels:
            issue.labels = current_labels + [label]
        if issue.id:
            self.state.completed.discard(issue.id)
        if comment and label not in labels and current_status != status:
            tracker.add_comment(issue.identifier, comment, author="oompah")
        logger.info(
            "Marked mature epic review issue %s as %s on branch %s",
            issue.identifier,
            status,
            clean_source or getattr(issue, "work_branch", None) or "<default>",
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
                logger.warning(
                    "Stuck issue %s: rejected %d consecutive ticks (%s)",
                    issue.identifier,
                    count,
                    reason,
                )
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
        # state snapshot. See task oompah-zlz_2-u7c.
        if self._is_project_paused(issue.project_id):
            return _reject("project_paused")
        if not issue.id or not issue.identifier or not issue.title or not issue.state:
            return _reject("missing_fields")
        epic_review_repair = self._is_epic_review_repair_issue(
            issue,
            dispatch_gate=True,
        )
        if (
            (issue.issue_type or "").strip().lower() != "epic"
            and self._issue_has_children(issue)
            and not epic_review_repair
        ):
            return _reject("epic_rollup_parent")
        # Refuse to dispatch tasks with no body. A title alone is not enough
        # context for an agent to do anything sensible — and we've watched
        # agents burn dozens of turns spinning on placeholder tasks created
        # for ad-hoc CLI testing. Operator either fills in the description,
        # closes the task, or defers it. Epics get a pass because they are
        # planned separately and may legitimately start as title-only.
        if (
            (issue.issue_type or "").strip().lower() != "epic"
            and not epic_review_repair
            and not (issue.description or "").strip()
        ):
            return _reject("empty_description")
        # Planning epics are handled separately by
        # _plan_open_epics/_should_dispatch_epic. Once every child is complete
        # and the epic PR itself needs CI/rebase repair, the epic becomes the
        # dispatchable unit so the agent fixes the existing epic branch.
        if (issue.issue_type or "").strip().lower() == "epic" and not epic_review_repair:
            return _reject("epic")
        if not epic_review_repair and self._issue_requires_parent_epic(issue):
            if canonicalize_status(issue.state) != NEEDS_HUMAN:
                self._mark_issue_needs_epic_parent(issue, issue.project_id)
            return _reject("missing_parent_epic")
        # Never dispatch pre-backlog intake issues — Proposed is the intake
        # gate and must be triaged/approved before any agent work begins.
        if canonicalize_status(issue.state) == PROPOSED:
            return _reject("proposed")
        # Never dispatch issues that are waiting for a human answer
        if canonicalize_status(issue.state) == NEEDS_ANSWER or "asking_question" in issue.labels:
            return _reject("needs_answer")
        # Never dispatch issues reserved for human action (e.g. capability requests)
        if canonicalize_status(issue.state) == NEEDS_HUMAN or "human-only" in issue.labels:
            return _reject("needs_human")
        # Never dispatch issues that have been decomposed into children
        if canonicalize_status(issue.state) == DECOMPOSED or "decomposed" in issue.labels:
            return _reject("decomposed")
        # Never dispatch candidates flagged as duplicates of existing open issues
        if canonicalize_status(issue.state) == DUPLICATE_CANDIDATE or "duplicate-candidate" in issue.labels:
            return _reject("duplicate_candidate")
        # Validate release-pick target branch against project branch patterns
        # (TASK-454.3). When an issue has a target_branch set, it must match
        # at least one of the project's configured patterns, and must not
        # point at the project's protected source-only (default) branch
        # unless explicitly opted in via the ``backport:allow-source`` label.
        if issue.target_branch:
            _project = self.project_store.get(issue.project_id) if issue.project_id else None
            if _project is not None:
                from oompah.release_pick_validation import validate_release_pick_target
                _tbv = validate_release_pick_target(issue, _project)
                if not _tbv.valid:
                    logger.warning(
                        "Dispatch blocked for %s: %s",
                        issue.identifier,
                        _tbv.error,
                    )
                    return _reject(f"invalid_target_branch:{_tbv.reason}")
        state_norm = _state_key(issue.state)
        if state_norm not in _dispatch_active_state_keys(
            self.config.tracker_active_states
        ):
            return _reject(f"inactive_state={state_norm}")
        if state_norm in {
            _state_key(s) for s in self.config.tracker_terminal_states
        }:
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
            for blocker in issue.blocked_by:
                blocker_state = blocker.state or ""
                # If blocker state is unknown, look it up
                if not blocker_state and blocker.id:
                    resolved = self._resolve_blocker_state(blocker, issue)
                    blocker_state = resolved
                if not self._blocker_satisfied(issue, blocker, blocker_state):
                    # Blocker not yet closed — still blocked
                    return _reject(f"blocker={blocker.id} state={blocker_state}")
                if self._blocker_has_unmerged_pr(blocker):
                    # Blocker is closed but PR hasn't merged — still blocked
                    return _reject(f"blocker={blocker.id} unmerged_review")
        # Shared-epic child dispatch serialization: multiple children share one
        # worktree+branch with no in-worktree coordination protocol, so only
        # one child of a given epic can be in flight at a time.  Multiple epics
        # dispatch in parallel up to max_in_flight_prs.  P0 children bypass
        # the serialization check (but not the branch-done check).
        if issue.parent_id:
            # A shared-epic child writes its terminal status to the
            # persistent epic branch, but the main checkout the tracker
            # reads only catches up when the epic→main PR lands. Without
            # this, an already-Done child looks Open in main and gets
            # re-dispatched forever. Applies even to P0.
            if self._shared_epic_child_done(issue):
                return _reject(f"epic_branch_done={issue.parent_id}")
            # Serialize child dispatch within an epic — children share
            # one worktree/branch and we have no in-worktree
            # coordination protocol. Ordinary P0 children bypass this,
            # but epic rebase tasks do not: multiple rebase workers for
            # the same shared branch can race force-pushes and corrupt
            # each other's work.
            if not is_p0 or self._is_epic_rebase_task(issue):
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
        # See plans/acp-agent.md and task oompah-zlz_2-bcl.
        if self._would_dispatch_via_acp(issue):
            return True
        # Budget circuit breaker — model-aware. When the window's spend has
        # exceeded the cap we still allow dispatch on models the provider
        # has explicitly priced at $0 (e.g. an internal-tier MiniMax). That
        # way an over-budget orchestrator continues chewing through cheap
        # work while paid escalations queue for the next window. See task
        # oompah-zlz_2-fvt for the full rationale.
        if not self._check_budget():
            if not self.state.budget_exceeded:
                self.state.budget_exceeded = True
                logger.warning(
                    "Budget limit exceeded (%.2f/%.2f), halting paid dispatch",
                    self.state.agent_totals.estimated_cost,
                    self.config.budget_limit,
                )
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
        See task oompah-zlz_2-ag7h.

        Mirrors the safety-critical ACP-routing carve-out in
        ``_dispatch`` (oompah-zlz_2-lfy): when a merge-conflict /
        ci-fix task would otherwise resolve to a non-ACP profile but
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
                and self._is_safety_critical_issue(issue)
            ):
                acp_profile = self._find_acp_profile()
                if acp_profile is not None and self._acp_profile_is_subscription(
                    acp_profile
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
        task (oompah-zlz_2-ag7h) and matches the back-compat default
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
            is_first = (
                issue.id not in self.state.running
                and issue.id not in self.state.retry_attempts
            )
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
            logger.debug(
                "free-model resolution failed for %s: %s", issue.identifier, exc
            )
            return False

    def _pre_resolve_blockers(self, candidates: list[Issue]) -> None:
        """Pre-resolve unknown blocker states into the cache (blocking, runs in thread).

        Batches all unknown blockers into parallel tracker detail calls.
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

        A skipped or failed fetch is not evidence that a project has zero
        open reviews. Preserve the previous cache entry in those cases so
        dashboard state does not briefly erase real open PRs. A successful
        provider response of [] still clears the cache for that project.
        """
        projects = self.project_store.list_all()
        if not projects:
            return {}

        previous_cache = {
            str(project_id): list(reviews or [])
            for project_id, reviews in (
                getattr(self, "_reviews_cache", {}) or {}
            ).items()
        }

        def _cached_reviews(project_id: str) -> list:
            return list(previous_cache.get(str(project_id), []))

        def _has_warm_reviews_cache(project_id: str) -> bool:
            return str(project_id) in previous_cache

        def _fetch_for_project(project) -> tuple[str, list]:
            project_id = str(project.id)
            # Skip polling for webhook-healthy projects
            if self.is_webhook_healthy(project_id) and _has_warm_reviews_cache(
                project_id
            ):
                return (project_id, _cached_reviews(project_id))
            provider = detect_provider(
                project.repo_url, access_token=project.access_token
            )
            if not provider:
                return (project_id, _cached_reviews(project_id))
            slug = extract_repo_slug(project.repo_url)
            try:
                reviews = provider.list_open_reviews(slug)
                return (project_id, reviews)
            except Exception as exc:
                logger.debug(
                    "Failed to fetch open reviews for %s: %s", project.name, exc
                )
                return (project_id, _cached_reviews(project_id))

        result: dict[str, list] = {}
        with ThreadPoolExecutor(max_workers=min(len(projects), 4)) as pool:
            for pid, reviews in pool.map(_fetch_for_project, projects):
                result[pid] = reviews
        return result

    async def _fetch_all_reviews_bounded(self) -> dict[str, list]:
        """Fetch open reviews using bounded per-project concurrency with timeout and stale-cache fallback.

        Uses the shared bounded refresh infrastructure (_run_bounded_refresh) to
        ensure one slow project doesn't block others, and stale cached data is
        used as fallback when a project times out.
        """
        projects = self.project_store.list_all()
        if not projects:
            return {}

        previous_cache = {
            str(project_id): list(reviews or [])
            for project_id, reviews in (
                getattr(self, "_reviews_cache", {}) or {}
            ).items()
        }

        def _cached_reviews(project_id: str) -> list:
            return list(previous_cache.get(str(project_id), []))

        def _has_warm_reviews_cache(project_id: str) -> bool:
            return str(project_id) in previous_cache

        async def _fetch_one_project(project) -> tuple[str, list]:
            project_id = str(project.id)
            # Skip polling for webhook-healthy projects
            if self.is_webhook_healthy(project_id) and _has_warm_reviews_cache(
                project_id
            ):
                return (project_id, _cached_reviews(project_id))

            async def _coro() -> list:
                provider = detect_provider(
                    project.repo_url, access_token=project.access_token
                )
                if not provider:
                    return _cached_reviews(project_id)
                slug = extract_repo_slug(project.repo_url)
                try:
                    return provider.list_open_reviews(slug)
                except Exception as exc:
                    logger.debug(
                        "Failed to fetch open reviews for %s: %s", project.name, exc
                    )
                    return _cached_reviews(project_id)

            data, _ = await self._run_bounded_refresh(
                project_id, "reviews", _coro
            )
            return (project_id, data)

        # Run all project fetches concurrently with bounded concurrency
        results = await asyncio.gather(*[_fetch_one_project(p) for p in projects])
        return {pid: reviews for pid, reviews in results}

    @staticmethod
    def _coerce_branch_set(branches: Any) -> set[str]:
        """Normalize provider/cache branch lists into a string set."""
        if not branches:
            return set()
        if isinstance(branches, str):
            return {branches}
        try:
            return {str(branch) for branch in branches if branch}
        except TypeError:
            return set()

    def _fetch_all_merged_branches(self) -> set[str]:
        """Fetch merged PR/MR branch names across projects with stale webhooks.

        Projects with recent webhook deliveries (within 2.5 minutes) are
        skipped only when a per-project merged-branch cache is warm. Cold
        caches still poll once so a restart cannot lose the merged-branch
        signal for Done epics awaiting rollup reconciliation.
        """
        projects = self.project_store.list_all()
        if not projects:
            return set()

        def _fetch_for_project(project) -> set[str]:
            project_id = str(project.id)
            cached = self._get_stale_cache(project_id, "merged_branches")
            # Skip polling for webhook-healthy projects only after the cache
            # has been populated at least once in this process.
            if self.is_webhook_healthy(project_id) and cached is not None:
                return self._coerce_branch_set(cached)
            provider = detect_provider(
                project.repo_url, access_token=project.access_token
            )
            if not provider:
                return self._coerce_branch_set(cached)
            slug = extract_repo_slug(project.repo_url)
            try:
                branches = self._coerce_branch_set(provider.list_merged_branches(slug))
                self._set_stale_cache(project_id, "merged_branches", branches)
                return branches
            except Exception as exc:
                logger.debug(
                    "Failed to fetch merged branches for %s: %s", project.name, exc
                )
                return self._coerce_branch_set(cached)

        result: set[str] = set()
        with ThreadPoolExecutor(max_workers=min(len(projects), 4)) as pool:
            for branches in pool.map(_fetch_for_project, projects):
                result |= branches
        return result

    async def _fetch_all_merged_branches_bounded(self) -> set[str]:
        """Fetch merged branches using bounded per-project concurrency with timeout and stale-cache fallback.

        Uses the shared bounded refresh infrastructure (_run_bounded_refresh) to
        ensure one slow project doesn't block others, and stale cached data is
        used as fallback when a project times out.
        """
        projects = self.project_store.list_all()
        if not projects:
            return set()

        async def _fetch_one_project(project) -> set[str]:
            project_id = str(project.id)
            cached = self._get_stale_cache(project_id, "merged_branches")
            # Skip polling for webhook-healthy projects only after the cache
            # has been populated at least once in this process.
            if self.is_webhook_healthy(project_id) and cached is not None:
                return self._coerce_branch_set(cached)

            async def _coro() -> set[str]:
                provider = detect_provider(
                    project.repo_url, access_token=project.access_token
                )
                if not provider:
                    return self._coerce_branch_set(cached)
                slug = extract_repo_slug(project.repo_url)
                try:
                    return self._coerce_branch_set(provider.list_merged_branches(slug))
                except Exception as exc:
                    logger.debug(
                        "Failed to fetch merged branches for %s: %s", project.name, exc
                    )
                    return self._coerce_branch_set(cached)

            data, _ = await self._run_bounded_refresh(
                project_id, "merged_branches", _coro
            )
            return self._coerce_branch_set(data)

        # Run all project fetches concurrently with bounded concurrency
        results = await asyncio.gather(*[_fetch_one_project(p) for p in projects])
        merged: set[str] = set()
        for branches in results:
            merged |= branches
        return merged

    def _reset_orphaned_in_progress(self, candidates: list[Issue]) -> None:
        """Reset in_progress issues back to open if no agent is attached.

        An issue is orphaned if it's in_progress but has no running agent
        and no pending retry. This prevents issues from getting stuck.

        Also sweeps tasks currently in In Progress state in the tracker that
        are NOT in the candidates list (which only contains Open/active tasks).
        This catches orphans left by the retry-release "no longer candidate"
        path (TASK-409).
        """
        running_ids = set(self.state.running.keys())
        retry_ids = set(self.state.retry_attempts.keys())
        claimed_ids = self.state.claimed

        # Combine dispatch candidates with any In Progress tasks not already
        # represented.  In Progress tasks are never candidates (they are not
        # in active_states), so without this extra sweep orphaned In Progress
        # tasks left behind after retry-claim release would never be reset.
        candidate_ids = {i.id for i in candidates}
        all_issues: list[Issue] = list(candidates)
        try:
            in_progress = self._fetch_all_in_progress_issues()
            for issue in in_progress:
                if issue.id not in candidate_ids:
                    all_issues.append(issue)
        except Exception as exc:
            logger.debug(
                "Orphan check: failed to fetch In Progress tasks: %s", exc
            )

        for issue in all_issues:
            if _state_key(issue.state) != "in_progress":
                continue
            if (issue.issue_type or "").strip().lower() == "epic":
                # Planning epic state is a rollup of child state. A mature
                # epic review repair is different: the epic itself is the
                # dispatch unit for CI/rebase work on the existing epic PR.
                if not self._is_epic_review_repair_issue(issue):
                    continue
            if issue.id in running_ids or issue.id in retry_ids:
                continue
            if issue.id in claimed_ids:
                continue
            # Orphaned — return to the dispatchable state implied by any
            # recovery label. Plain work goes back to Open; CI/rebase recovery
            # must stay P0 so existing open PRs do not block its dispatch.
            try:
                project_id = issue.project_id
                tracker = (
                    self._tracker_for_project(project_id)
                    if project_id
                    else self.tracker
                )
                if issue.id in self.state.completed:
                    _lock_ctx = (
                        self.project_store.project_write_lock(project_id)
                        if project_id
                        else contextlib.nullcontext()
                    )
                    with _lock_ctx:
                        tracker.update_issue(issue.identifier, status=DONE)
                    logger.info(
                        "Preserved completed issue %s as Done during orphan reset",
                        issue.identifier,
                    )
                    continue
                labels = {str(label).lower() for label in (issue.labels or [])}
                status = OPEN
                updates: dict[str, str] = {}
                if "merge-conflict" in labels:
                    status = NEEDS_REBASE
                    updates["priority"] = "0"
                elif "ci-fix" in labels:
                    status = NEEDS_CI_FIX
                    updates["priority"] = "0"
                # Acquire per-project write lock so concurrent maintenance
                # passes don't interleave tracker writes for the same project.
                _lock_ctx = (
                    self.project_store.project_write_lock(project_id)
                    if project_id
                    else contextlib.nullcontext()
                )
                with _lock_ctx:
                    tracker.update_issue(issue.identifier, status=status, **updates)
                self.state.completed.discard(issue.id)
                self._orphan_reset_counts[issue.id] = (
                    self._orphan_reset_counts.get(issue.id, 0) + 1
                )
                logger.info(
                    "Reset orphaned In Progress issue %s to %s "
                    "(no agent attached, count=%d)",
                    issue.identifier,
                    status,
                    self._orphan_reset_counts[issue.id],
                )
            except Exception as exc:
                logger.debug(
                    "Failed to reset orphaned issue %s: %s", issue.identifier, exc
                )

    # ------------------------------------------------------------------
    # Maintenance lane scheduling gate (TASK-466.4)
    # ------------------------------------------------------------------

    def _get_or_create_job_state(self, name: str) -> MaintenanceJobState:
        """Return the :class:`MaintenanceJobState` for *name*, creating it on first access."""
        if name not in self._maintenance_jobs:
            self._maintenance_jobs[name] = MaintenanceJobState(name=name)
        return self._maintenance_jobs[name]

    def _run_maintenance_job(
        self,
        name: str,
        fn: Any,
        *,
        min_interval_s: float,
        max_runtime_s: float | None = None,
    ) -> None:
        """Gate-and-run a maintenance job with backpressure controls.

        Enforces three scheduling policies in order:

        1. **In-flight coalescing** — if a run of *name* is already executing,
           the request is dropped (coalesced) and ``skip_count`` is
           incremented.  This prevents a slow maintenance job from spawning
           duplicate concurrent copies of itself.

        2. **Minimum interval** — if the time since the last run is less than
           *min_interval_s*, the request is dropped and ``skip_count`` is
           incremented.  The explicit ``next_run_monotonic`` timestamp takes
           priority over the interval calculation when set.

        3. **Max runtime budget** — if *max_runtime_s* is given and the job
           runs longer, a deadline flag is set so callers can stop early (the
           job function receives no argument; callers must poll
           ``_job_deadline_exceeded(name)`` if they wish to respect it).

        State transitions (tracked in :class:`MaintenanceJobState`):

        * Before running: ``last_status = "running"``, ``in_flight = True``
        * After success:  ``last_status = "completed"``, ``in_flight = False``,
                          ``next_run_monotonic = now + min_interval_s``
        * After failure:  ``last_status = "failed"``, ``in_flight = False``,
                          ``last_error`` set, ``next_run_monotonic`` set
        * When skipped:   ``last_status = "skipped"``, ``skip_count`` incremented
        """
        state = self._get_or_create_job_state(name)
        now = time.monotonic()

        # ---- 1. In-flight coalescing ----
        if state.in_flight:
            state.skip_count += 1
            state.last_status = "skipped"
            logger.debug(
                "Maintenance job %r skipped: already in flight (total skips=%d)",
                name,
                state.skip_count,
            )
            return

        # ---- 2. Minimum interval / next-run gate ----
        if state.next_run_monotonic is not None:
            if now < state.next_run_monotonic:
                state.skip_count += 1
                state.last_status = "skipped"
                logger.debug(
                    "Maintenance job %r skipped: next_run in %.1fs (total skips=%d)",
                    name,
                    state.next_run_monotonic - now,
                    state.skip_count,
                )
                return
        elif state.last_run_monotonic is not None:
            elapsed = now - state.last_run_monotonic
            if elapsed < min_interval_s:
                state.skip_count += 1
                state.last_status = "skipped"
                logger.debug(
                    "Maintenance job %r skipped: %.1fs < min_interval %.1fs "
                    "(total skips=%d)",
                    name,
                    elapsed,
                    min_interval_s,
                    state.skip_count,
                )
                return

        # ---- 3. Run the job ----
        state.in_flight = True
        state.last_status = "running"
        state.last_run_monotonic = now
        state.run_count += 1
        # Store per-job deadline in the state (thread-safe: each job has its own state).
        state.current_deadline = (
            (now + max_runtime_s) if max_runtime_s is not None else None
        )
        t_start = time.monotonic()
        try:
            fn()
            state.last_status = "completed"
            state.last_error = None
        except Exception as exc:  # noqa: BLE001
            state.last_status = "failed"
            state.last_error = str(exc)
            logger.warning("Maintenance job %r failed: %s", name, exc)
        finally:
            elapsed_s = time.monotonic() - t_start
            state.last_duration_s = elapsed_s
            state.in_flight = False
            finished = time.monotonic()
            state.next_run_monotonic = finished + min_interval_s
            state.current_deadline = None

    def _job_deadline_exceeded(self, name: str) -> bool:
        """Return True if the current run of *name* has exceeded its runtime budget.

        Maintenance jobs that process items in a loop should call this
        periodically to honour the ``max_runtime_s`` budget passed to
        :meth:`_run_maintenance_job`.  Returns ``False`` when no deadline
        is active (either no budget was set or no run is in progress).
        """
        state = self._maintenance_jobs.get(name)
        if state is None or state.current_deadline is None:
            return False
        return time.monotonic() > state.current_deadline

    # ------------------------------------------------------------------
    # Watchdog: periodic health checks for stuck issues
    # ------------------------------------------------------------------

    def _maybe_run_watchdog(self) -> None:
        """Run watchdog if enough time has elapsed since last run.

        Delegates to the maintenance lane scheduling gate so the watchdog
        participates in in-flight coalescing and skip accounting.
        """
        self._run_maintenance_job(
            "watchdog",
            self._watchdog_check,
            min_interval_s=self._watchdog_interval_s,
        )
        # Back-fill _last_watchdog_run so legacy callers that read it
        # directly see a consistent value.
        state = self._maintenance_jobs.get("watchdog")
        if state and state.last_run_monotonic is not None:
            self._last_watchdog_run = state.last_run_monotonic

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
        active_norms = _dispatch_active_state_keys(self.config.tracker_active_states)
        stale = []
        for issue in self._last_candidates:
            if issue.id in self.state.completed:
                state_norm = _state_key(issue.state)
                if state_norm in active_norms:
                    stale.append(issue)
        for issue in stale:
            self.state.completed.discard(issue.id)
            logger.warning(
                "Watchdog: cleared stale completed entry for %s (tracker state=%s)",
                issue.identifier,
                issue.state,
            )
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
                logger.warning(
                    "Watchdog: issue %s reset from in_progress %d times "
                    "— possible state loop",
                    identifier,
                    count,
                )
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
                        logger.warning(
                            "Watchdog: clearing stale unmerged_review block "
                            "on %s (blocker %s has no open review after %d ticks)",
                            identifier,
                            blocker_id,
                            count,
                        )
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
            provider = detect_provider(
                project.repo_url, access_token=project.access_token
            )
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
                        # Skip if this is an epic branch being proactively rebased
                        if self._is_epic_branch_being_rebased(
                            project.id, review.source_branch
                        ):
                            logger.debug(
                                "Watchdog: suppressing limbo conflict notify for %s MR #%s "
                                "(proactive rebase in flight)",
                                project.name,
                                review.id,
                            )
                            continue
                        logger.warning(
                            "Watchdog: YOLO limbo MR #%s on %s needs rebase "
                            "(CI passed, %d cycles). Dispatching conflict agent.",
                            review.id,
                            project.name,
                            tick_count,
                        )
                        try:
                            self._yolo_notify_conflict(
                                project, provider, slug, review.id
                            )
                            fixed += 1
                        except Exception as exc:
                            logger.warning(
                                "Watchdog: conflict notify failed for %s #%s: %s",
                                project.name,
                                review.id,
                                exc,
                            )
                    else:
                        logger.warning(
                            "Watchdog: YOLO limbo MR #%s on %s — "
                            "ci=%r rebase=%s (%d cycles)",
                            review.id,
                            project.name,
                            review.ci_status,
                            review.needs_rebase,
                            tick_count,
                        )
        # Clear resolved limbo entries
        for key in list(self._yolo_limbo_ticks):
            if key not in current_limbo:
                del self._yolo_limbo_ticks[key]
        return fixed

    def _build_pr_body(
        self,
        issue: "Issue | None",
        target_branch: str,
        pr_repo_slug: str,
        default_branch: str,
    ) -> str:
        """Build the PR body linking to the central task hub issue.

        For GitHub-backed tasks that carry a ``url`` (the hub issue's HTML URL),
        the body includes a stable link so reviewers can navigate from the PR to
        the task context.

        A GitHub closing keyword (``Fixes #N``) is only emitted when ALL of
        the following hold — this is the only case GitHub honours it:

        1. The issue is GitHub-backed (``tracker_kind == "github_issues"``).
        2. The issue's ``owner/repo`` matches the PR's repo slug
           (cross-repository auto-close is not supported by GitHub).
        3. The PR targets the repository's default branch (GitHub only
           auto-closes on merges to the default branch).

        In every other case a plain markdown link is used so the PR is
        visible from the issue without relying on auto-close behaviour.
        """
        if not issue or not issue.url:
            return ""

        if issue.tracker_kind != "github_issues":
            # Non-GitHub tracker: include a plain text reference.
            label = issue.display_identifier or issue.identifier
            return f"Relates to: [{label}]({issue.url})"

        # GitHub issue: check whether we can safely use a closing keyword.
        issue_slug = ""
        if issue.tracker_owner and issue.tracker_repo:
            issue_slug = f"{issue.tracker_owner}/{issue.tracker_repo}"

        use_closing_keyword = (
            bool(issue_slug)
            and issue_slug.lower() == pr_repo_slug.lower()
            and target_branch == default_branch
        )

        label = issue.display_identifier or issue.identifier
        if use_closing_keyword and issue.issue_number:
            return f"Fixes #{issue.issue_number}\n\n[{label}]({issue.url})"
        else:
            return f"Relates to: [{label}]({issue.url})"

    def _work_branch_for_review(
        self,
        entry: RunningEntry,
        project: Any | None,
    ) -> str:
        issue = entry.issue
        if issue is not None:
            return self._branch_for_issue(issue, project)
        return entry.identifier

    def _branch_for_issue(self, issue: Issue, project: Any | None = None) -> str:
        for value in (
            getattr(issue, "work_branch", None),
            getattr(issue, "branch_name", None),
        ):
            if isinstance(value, str) and value.strip():
                return value.strip()
        if (
            issue.tracker_kind == "github_issues"
            and issue.issue_number
            and project is not None
        ):
            return github_work_branch_name(project.name, issue.issue_number)
        return issue.identifier

    def _helper_branch_token(self, raw: str | None) -> str:
        """Normalize a branch token parsed from an auto-filed helper issue."""
        value = str(raw or "").strip()
        return value.strip("`'\".,;)")

    def _helper_landing_branches_for_issue(self, issue: Issue) -> list[str]:
        """Return PR/epic branches named by CI-fix or rebase helper issues."""
        title = str(issue.title or "").strip()
        description = str(issue.description or "")
        branches: list[str] = []

        ci_match = re.search(
            r"\bCI\s+fix:\s*PR\s*#\d+\s+on branch\s+([^\s)]+)",
            title,
            flags=re.IGNORECASE,
        )
        if ci_match:
            branches.append(self._helper_branch_token(ci_match.group(1)))

        rebase_match = re.search(
            r"^Rebase\s+(.+?)\s+onto\s+\S+",
            title,
            flags=re.IGNORECASE,
        )
        if rebase_match:
            branches.append(self._helper_branch_token(rebase_match.group(1)))

        if ci_match is None and title.lower().startswith("ci fix:"):
            desc_match = re.search(
                r"\bbranch\s+`?([^`\s)]+)`?",
                description,
                flags=re.IGNORECASE,
            )
            if desc_match:
                branches.append(self._helper_branch_token(desc_match.group(1)))

        if title.lower().startswith("rebase ") and issue.parent_id:
            try:
                branches.append(
                    self.project_store.epic_branch_name(issue.parent_id)
                )
            except Exception:  # noqa: BLE001 - parsed title branch is enough
                pass

        return [branch for branch in branches if branch]

    def _candidate_landing_branches_for_issue(
        self,
        issue: Issue,
        project: Any | None = None,
    ) -> list[str]:
        """Return branch names whose merged PR should land ``issue``."""
        branches = [self._branch_for_issue(issue, project)]
        branches.extend(self._helper_landing_branches_for_issue(issue))
        return list(dict.fromkeys(branch for branch in branches if branch))

    def _is_helper_landing_issue(self, issue: Issue) -> bool:
        title = str(issue.title or "").strip().lower()
        return title.startswith("ci fix:") or title.startswith("rebase ")

    def _landed_branch_for_issue(
        self,
        project: Project,
        issue: Issue,
        project_id: str,
        candidate_branches: list[str],
        merged_branches: set[str],
        open_review_branches: set[str],
        provider: Any | None,
        slug: str,
    ) -> str | None:
        """Return the first candidate branch with a confirmed merged PR."""
        for branch in candidate_branches:
            if branch in open_review_branches:
                continue
            if branch in merged_branches and self._merged_branch_tip_landed(
                project,
                issue,
                project_id,
                branch,
                rollup_strategy=self._epic_rollup_child_strategy(issue, project_id),
            ):
                return branch

            if provider is None or not slug:
                continue
            try:
                review = provider.find_pr_for_branch(slug, branch)
            except Exception as exc:  # noqa: BLE001 - best-effort reconciliation
                logger.debug(
                    "Merged issue PR lookup failed for %s branch %s: %s",
                    issue.identifier,
                    branch,
                    exc,
                )
                continue
            if str(getattr(review, "state", "") or "").lower() != "merged":
                continue
            if self._merged_branch_tip_landed(
                project,
                issue,
                project_id,
                branch,
                rollup_strategy=self._epic_rollup_child_strategy(issue, project_id),
            ):
                return branch
        return None

    def _ensure_review_exists(
        self, entry: RunningEntry, project_id: str | None
    ) -> bool:
        """Create a review (PR/MR) if the agent pushed a branch but none exists.

        Shared workflow: children of an epic commit directly to the shared
        epic branch.  NO per-child PR is created (the epic→main PR is the
        only one).  Top-level tasks that are not children of an epic get their
        own PR targeting ``project.default_branch`` or ``issue.target_branch``.

        Returns ``True`` when no review is needed or a review exists/was
        created. Returns ``False`` when the branch has unmerged commits but
        oompah could not create the review; in that case the task is reopened
        with a diagnostic comment so it is not stranded in a review-like state.
        """
        if not project_id:
            return True
        project = self.project_store.get(project_id)
        if not project:
            return True

        if self._issue_requires_parent_epic(entry.issue, project_id):
            if entry.issue is not None:
                logger.warning(
                    "Review handoff blocked for %s: project requires a parent epic",
                    entry.issue.identifier,
                )
                self._mark_issue_needs_epic_parent(entry.issue, project_id)
            return False

        # Resolve parent epic for issues that have one.
        parent_epic: Issue | None = None
        if entry.issue and entry.issue.parent_id:
            parent_epic = self._resolve_parent_epic(entry.issue)

        # Shared workflow: children of a real epic commit to the shared epic
        # branch, and the only PR is the epic→main PR.  A task can have a
        # parent that is not an epic, though; those tasks still use per-task
        # worktrees and must get their own review instead of being stranded.
        if (
            entry.issue is not None
            and (entry.issue.parent_id or "").strip()
            and parent_epic is not None
        ):
            logger.debug(
                "Skip per-child review for %s: child shares branch with epic %s",
                entry.identifier,
                parent_epic.identifier,
            )
            return True

        branch = self._work_branch_for_review(entry, project)
        # Honor Issue.target_branch when set (e.g. release branches),
        # falling back to the project's default branch.
        target_branch = project.default_branch
        if entry.issue and entry.issue.target_branch:
            target_branch = entry.issue.target_branch

        # Check if a review already exists for this branch
        reviews = getattr(self, "_reviews_cache", {}).get(project_id, [])
        for r in reviews:
            if r.source_branch == branch:
                self._mark_task_in_review(entry, project_id, r)
                return True  # review already exists

        commits_ahead = 0
        commit_lines: list[str] = []
        commit_error = ""
        if project.repo_path:
            try:
                from oompah.close_gate import _count_commits_ahead

                commits_ahead, commit_lines, commit_error = _count_commits_ahead(
                    project.repo_path,
                    target_branch,
                    branch,
                )
            except Exception as exc:
                commit_error = str(exc)
        if commit_error:
            logger.warning(
                "Review handoff commit check failed for %s branch=%s base=%s: %s",
                entry.identifier,
                branch,
                target_branch,
                commit_error,
            )

        review_required = commits_ahead > 0
        if not review_required and not commit_error:
            return True

        if not project.repo_url:
            if review_required:
                self._reopen_missing_review(
                    entry,
                    project_id,
                    branch,
                    target_branch,
                    commits_ahead,
                    commit_lines,
                    "project has no repository URL configured",
                )
                return False
            return True

        provider = detect_provider(project.repo_url, access_token=project.access_token)
        if not provider:
            if review_required:
                self._reopen_missing_review(
                    entry,
                    project_id,
                    branch,
                    target_branch,
                    commits_ahead,
                    commit_lines,
                    "no supported forge provider was detected",
                )
                return False
            return True
        slug = extract_repo_slug(project.repo_url)

        if review_required:
            n_open, limit, at_capacity = self._project_review_capacity(project_id)
            if at_capacity:
                self._defer_review_handoff(
                    entry,
                    project_id,
                    branch,
                    target_branch,
                    commits_ahead,
                    commit_lines,
                    n_open,
                    limit,
                )
                return True

        # Create the review
        try:
            title = (
                f"{entry.identifier}: {entry.issue.title}"
                if entry.issue
                else entry.identifier
            )
            pr_body = self._build_pr_body(
                entry.issue,
                target_branch,
                slug,
                project.default_branch,
            )
            result = provider.create_review(
                slug,
                title,
                branch,
                target_branch=target_branch,
                description=pr_body,
            )
            if result:
                logger.info(
                    "Auto-created review for %s on %s (review #%s, base=%s)",
                    entry.identifier,
                    project.name,
                    result.id,
                    target_branch,
                )
                self._mark_task_in_review(entry, project_id, result)
                return True
            else:
                logger.warning(
                    "Failed to create review for %s on %s (base=%s)",
                    entry.identifier,
                    project.name,
                    target_branch,
                )
                if review_required:
                    self._reopen_missing_review(
                        entry,
                        project_id,
                        branch,
                        target_branch,
                        commits_ahead,
                        commit_lines,
                        "forge provider returned no review",
                    )
                    return False
        except Exception as exc:
            logger.warning("Error creating review for %s: %s", entry.identifier, exc)
            if review_required:
                self._reopen_missing_review(
                    entry,
                    project_id,
                    branch,
                    target_branch,
                    commits_ahead,
                    commit_lines,
                    str(exc),
                )
                return False

        return True

    def _mark_task_in_review(
        self,
        entry: RunningEntry,
        project_id: str | None,
        review: ReviewRequest | Any,
    ) -> None:
        """Mark the task ``In Review`` once a review artifact exists.

        Also persists ``oompah.review_url`` and ``oompah.review_number``
        metadata fields (TASK-462.2) so the task record carries the PR link
        without relying on GitHub's PR-to-issue auto-close semantics.
        """
        if not project_id:
            return
        try:
            tracker = self._tracker_for_project(project_id)
            tracker.update_issue(entry.identifier, status=IN_REVIEW)
            review_id = getattr(review, "id", None)
            review_url = getattr(review, "url", None)
            review_source = getattr(review, "source_branch", None)
            review_target = getattr(review, "target_branch", None)
            if review_id:
                logger.info(
                    "Marked %s as In Review (review #%s)",
                    entry.identifier,
                    review_id,
                )
            else:
                logger.info("Marked %s as In Review", entry.identifier)
            # Write review metadata so the task record carries the PR link
            # (Review URL / Review Number) without relying on GitHub
            # auto-close semantics.
            self._write_review_metadata(
                tracker,
                entry.identifier,
                review_id=review_id,
                review_url=review_url,
                source_branch=review_source,
                target_branch=review_target,
            )
        except Exception as exc:
            logger.warning(
                "Failed to mark %s as In Review after review handoff: %s",
                entry.identifier,
                exc,
            )

    def _write_review_metadata(
        self,
        tracker: "TrackerProtocol",
        identifier: str,
        *,
        review_id: str | None,
        review_url: str | None,
        source_branch: str | None = None,
        target_branch: str | None = None,
    ) -> None:
        """Persist review metadata fields on a task (best-effort).

        Writes ``oompah.review_url`` and ``oompah.review_number`` to the
        task's metadata block.  Also writes ``oompah.work_branch`` (source)
        and ``oompah.target_branch`` when supplied and not already set.

        All writes are best-effort: failures are logged as warnings but do
        not propagate so the caller's control flow is unaffected.
        """
        fields: dict[str, object] = {}
        if review_url:
            fields["oompah.review_url"] = review_url
        if review_id:
            fields["oompah.review_number"] = review_id
        if source_branch:
            fields["oompah.work_branch"] = source_branch
        if target_branch:
            fields["oompah.target_branch"] = target_branch
        for key, value in fields.items():
            try:
                tracker.set_metadata_field(identifier, key, value)
            except Exception as exc:
                logger.warning(
                    "Failed to write %s metadata %s=%r for %s: %s",
                    identifier,
                    key,
                    value,
                    identifier,
                    exc,
                )

    def _defer_review_handoff(
        self,
        entry: RunningEntry,
        project_id: str | None,
        branch: str,
        target_branch: str,
        commits_ahead: int,
        commit_lines: list[str],
        n_open: int,
        limit: int,
    ) -> None:
        """Leave a completed task closed while PR creation waits for capacity."""
        logger.info(
            "Deferred review handoff for %s: project review cap reached (%d/%d)",
            entry.identifier,
            n_open,
            limit,
        )
        if project_id:
            try:
                tracker = self._tracker_for_project(project_id)
                tracker.update_issue(entry.identifier, status=DONE)
            except Exception as exc:
                logger.warning(
                    "Failed to mark %s Done after deferred review handoff: %s",
                    entry.identifier,
                    exc,
                )
        commit_noun = "commit" if commits_ahead == 1 else "commits"
        lines = [
            "Review handoff deferred: the task branch has unmerged work, but "
            "this project is at its open review limit.",
            "",
            f"Branch: `{branch}`",
            f"Target branch: `{target_branch}`",
            f"Unmerged commits: {commits_ahead} {commit_noun}",
            f"Open reviews: {n_open}/{limit}",
            "",
            "oompah will create the review automatically when review capacity "
            "is available.",
        ]
        if commit_lines:
            lines.extend(["", "Recent commits:"])
            for line in commit_lines[:10]:
                lines.append(f"  {line}")
        try:
            self._post_comment(
                entry.identifier,
                "\n".join(lines),
                project_id=project_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to post review handoff deferral comment for %s: %s",
                entry.identifier,
                exc,
            )

    def _reopen_missing_review(
        self,
        entry: RunningEntry,
        project_id: str | None,
        branch: str,
        target_branch: str,
        commits_ahead: int,
        commit_lines: list[str],
        reason: str,
    ) -> None:
        """Reopen a closed task whose branch could not be handed to review."""
        try:
            tracker = (
                self._tracker_for_project(project_id) if project_id else self.tracker
            )
            tracker.update_issue(entry.identifier, status=OPEN)
        except Exception as exc:
            logger.warning(
                "Failed to reopen %s after review handoff failure: %s",
                entry.identifier,
                exc,
            )

        commit_noun = "commit" if commits_ahead == 1 else "commits"
        lines = [
            "Review handoff failed: the task branch has unmerged work but no "
            "review artifact was created.",
            "",
            f"Branch: `{branch}`",
            f"Target branch: `{target_branch}`",
            f"Unmerged commits: {commits_ahead} {commit_noun}",
        ]
        for line in commit_lines[:10]:
            lines.append(f"  {line}")
        if reason:
            lines.extend(["", f"Reason: {reason}"])
        lines.extend(
            [
                "",
                "Required: create or restore the PR/MR for this branch, then move "
                "the task to In Review only after the review exists.",
            ]
        )
        try:
            self._post_comment(
                entry.identifier,
                "\n".join(lines),
                project_id=project_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to post review handoff failure comment for %s: %s",
                entry.identifier,
                exc,
            )

    def _do_merged_labels(self) -> None:
        """Inner body of :meth:`_maybe_run_merged_labels`.

        Labels merged issues and epics and reconciles stale In Review tasks
        using the forge state cached by :meth:`_handle_review_check`.
        """
        sweeps = [
            ("label_merged_epics", self._label_merged_epics),
            ("reconcile_merged_epic_children", self._reconcile_merged_epic_children),
            ("label_merged_issues", self._label_merged_issues),
            ("reconcile_in_review_pr_outcomes", self._reconcile_in_review_pr_outcomes),
            ("reconcile_terminal_open_reviews", self._reconcile_terminal_open_reviews),
            ("reconcile_stale_in_review_tasks", self._reconcile_stale_in_review_tasks),
            ("reconcile_addendum_pr_outcomes", self._reconcile_addendum_pr_outcomes_sweep),
        ]
        for name, sweep in sweeps:
            if self._job_deadline_exceeded("merged_labels"):
                logger.info(
                    "merged_labels runtime budget exhausted before %s; "
                    "remaining sweep work will resume later",
                    name,
                )
                return
            sweep()

    def _maybe_open_deferred_done_reviews(self) -> None:
        """Retry Done-task review handoff as its own maintenance job.

        This used to run as the last sub-step of ``merged_labels``. Large
        projects can exhaust the merged-label runtime budget before that
        tail step, which strands completed task branches in Done with no PR.
        Keep it independently throttled so review handoff cannot starve behind
        merge reconciliation.
        """
        self._run_maintenance_job(
            "deferred_done_reviews",
            self._open_deferred_done_reviews,
            min_interval_s=self._MERGED_LABELS_INTERVAL_S,
            max_runtime_s=self.config.merged_labels_max_runtime_seconds or None,
        )

    def _open_deferred_done_reviews(self) -> None:
        """Retry review handoff for Done tasks when project capacity frees."""
        merged_branches = getattr(self, "_merged_branches", set()) or set()
        for project in self.project_store.list_all():
            if self._job_deadline_exceeded("deferred_done_reviews"):
                return
            project_id = str(project.id)
            if self._project_review_capacity(project_id)[2]:
                continue
            try:
                tracker = self._tracker_for_project(project_id)
                issues = tracker.fetch_issues_by_states([DONE])
            except (ProjectError, TrackerError) as exc:
                logger.debug(
                    "Deferred Done review fetch failed for %s: %s",
                    project_id,
                    exc,
                )
                continue

            for issue in issues:
                if self._job_deadline_exceeded("deferred_done_reviews"):
                    return
                if self._project_review_capacity(project_id)[2]:
                    break
                if not issue.project_id:
                    issue.project_id = project_id
                if canonicalize_status(issue.state) != DONE:
                    continue
                if (issue.issue_type or "").strip().lower() == "epic":
                    continue
                if self._issue_has_children(issue):
                    continue
                branch = self._branch_for_issue(issue, project)
                rollup_strategy = self._epic_rollup_child_strategy(
                    issue,
                    project_id,
                )
                # Shared-epic children commit to the epic branch; per-child
                # review and Merged promotion are handled via the epic→main PR.
                if issue.parent_id and rollup_strategy == "shared":
                    continue
                if (
                    branch
                    and branch in merged_branches
                    and self._merged_branch_tip_landed(
                        project,
                        issue,
                        project_id,
                        branch,
                        rollup_strategy=rollup_strategy,
                    )
                ):
                    try:
                        tracker.update_issue(issue.identifier, status=MERGED)
                        logger.info(
                            "Marked Done task %s Merged: branch %s has merged",
                            issue.identifier,
                            branch,
                        )
                    except TrackerError as exc:
                        logger.debug(
                            "Failed to mark merged Done task %s merged: %s",
                            issue.identifier,
                            exc,
                        )
                    continue
                if self._done_issue_branch_tip_landed(issue, project, project_id):
                    try:
                        tracker.update_issue(issue.identifier, status=MERGED)
                        logger.info(
                            "Marked Done task %s Merged: branch %s is already "
                            "contained in its target",
                            issue.identifier,
                            self._branch_for_issue(issue, project),
                        )
                    except TrackerError as exc:
                        logger.debug(
                            "Failed to mark landed Done task %s merged: %s",
                            issue.identifier,
                            exc,
                        )
                    continue
                if not self._done_issue_has_unmerged_review_work(
                    issue,
                    project,
                    project_id,
                ):
                    continue
                entry = RunningEntry(
                    worker_task=None,
                    identifier=issue.identifier,
                    issue=issue,
                    session=None,
                    retry_attempt=0,
                    started_at=datetime.now(timezone.utc),
                    agent_profile_name="maintenance",
                )
                self._ensure_review_exists(entry, project_id)

    def _done_issue_has_unmerged_review_work(
        self,
        issue: Issue,
        project: Project,
        project_id: str,
    ) -> bool:
        """Return True when a Done task branch is provably ahead of its base."""
        branch = self._branch_for_issue(issue, project)
        repo_path = getattr(project, "repo_path", "") or ""
        if not branch or not repo_path:
            return False

        target_branch = getattr(project, "default_branch", None) or "main"
        if issue.target_branch:
            target_branch = issue.target_branch

        try:
            from oompah.close_gate import _count_commits_ahead

            commits_ahead, _commit_lines, commit_error = _count_commits_ahead(
                repo_path,
                target_branch,
                branch,
            )
        except Exception as exc:
            logger.debug(
                "Deferred Done review git check failed for %s: %s",
                issue.identifier,
                exc,
            )
            return False
        if commit_error:
            logger.debug(
                "Deferred Done review skip for %s branch=%s base=%s: %s",
                issue.identifier,
                branch,
                target_branch,
                commit_error,
            )
            return False
        return commits_ahead > 0

    def _done_issue_branch_tip_landed(
        self,
        issue: Issue,
        project: Project,
        project_id: str,
    ) -> bool:
        """Return True when a Done task's branch is already in its target."""
        branch = self._branch_for_issue(issue, project)
        repo_path = getattr(project, "repo_path", "") or ""
        if not branch or not repo_path:
            return False
        if not self._managed_branch_ref_exists(repo_path, branch):
            return False

        target_branch = getattr(project, "default_branch", None) or "main"
        if issue.target_branch:
            target_branch = issue.target_branch

        ahead, _commit_lines, commit_error = self._count_review_branch_ahead(
            project,
            target_branch,
            branch,
        )
        if commit_error:
            logger.debug(
                "Done landed check skipped for %s branch=%s base=%s: %s",
                issue.identifier,
                branch,
                target_branch,
                commit_error,
            )
            return False
        return ahead <= 0

    def _maybe_run_merged_labels(self) -> None:
        """Periodically label merged issues/epics and reconcile stale In Review tasks.

        Uses the ``_merged_branches`` and ``_reviews_cache`` sets populated by
        :meth:`_handle_review_check` to avoid redundant forge API calls.

        Delegates to the maintenance lane scheduling gate (:meth:`_run_maintenance_job`)
        so the job participates in in-flight coalescing, interval throttling, skip
        accounting, and observability alongside all other maintenance jobs.

        The actual work is in :meth:`_do_merged_labels`.
        """
        self._run_maintenance_job(
            "merged_labels",
            self._do_merged_labels,
            min_interval_s=self._MERGED_LABELS_INTERVAL_S,
            max_runtime_s=self.config.merged_labels_max_runtime_seconds or None,
        )

    def _maybe_run_release_pick_reconciliation(self) -> None:
        """Periodically reconcile release-pick metadata and backport tasks.

        Release-pick reconciliation can do full-corpus metadata scans and SCM
        checks, so it has its own maintenance job state instead of being hidden
        behind ``merged_labels``.
        """
        self._run_maintenance_job(
            "release_picks",
            self._reconcile_release_picks_pass,
            min_interval_s=self._RELEASE_PICKS_INTERVAL_S,
            max_runtime_s=self.config.release_pick_max_runtime_seconds or None,
        )

    def _maybe_sync_github_issue_intake(self) -> None:
        """Periodically sync external GitHub intake for native Markdown projects."""
        self._run_maintenance_job(
            "github_issue_intake",
            self._sync_github_issue_intake_pass,
            min_interval_s=300.0,
            max_runtime_s=120.0,
        )

    def _sync_github_issue_intake_pass(self) -> None:
        """Import GitHub intake and mirror status changes for enabled projects."""
        metrics = {
            "projects": 0,
            "imported": 0,
            "status_scanned": 0,
            "status_commented": 0,
            "status_closed": 0,
            "errors": 0,
        }
        for project in self.project_store.list_all():
            if self._job_deadline_exceeded("github_issue_intake"):
                break
            if not project_uses_github_issue_intake(project):
                continue
            metrics["projects"] += 1
            project_name = getattr(project, "name", "?")
            auth_alert_source = f"github_intake_auth:{project_name}"
            try:
                metrics["imported"] += poll_github_issue_intake_project(self, project)
                status_metrics = sync_github_issue_intake_statuses_for_project(
                    self,
                    project,
                )
                metrics["status_scanned"] += int(status_metrics.get("scanned", 0))
                metrics["status_commented"] += int(status_metrics.get("commented", 0))
                metrics["status_closed"] += int(status_metrics.get("closed", 0))
                metrics["errors"] += int(status_metrics.get("errors", 0))
                self._alerts = [
                    a for a in self._alerts if a.get("source") != auth_alert_source
                ]
            except TrackerAuthError as exc:
                metrics["errors"] += 1
                self._alerts = [
                    a for a in self._alerts if a.get("source") != auth_alert_source
                ]
                self._alerts.append(
                    {
                        "level": "error",
                        "source": auth_alert_source,
                        "title": (
                            f"GitHub intake authentication failure for project "
                            f"{project_name!r}"
                        ),
                        "message": (
                            f"Oompah cannot fetch GitHub issues for project "
                            f"{project_name!r}: {exc}. "
                            "Set the project's access_token to a token with "
                            "read access to the intake repository, or configure "
                            "OOMPAH_GITHUB_TOKEN / GitHub App credentials that "
                            "cover this repository."
                        ),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                metrics["errors"] += 1
                logger.debug(
                    "GitHub issue intake sync failed for project %s: %s",
                    getattr(project, "name", "?"),
                    exc,
                )
        self._maintenance_status["github_issue_intake"] = {
            **metrics,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }

    def _label_merged_issues(self) -> None:
        """Label issues whose own or helper-associated branch has merged."""
        merged = getattr(self, "_merged_branches", set())
        reviews_cache = getattr(self, "_reviews_cache", {}) or {}

        for project in self.project_store.list_all():
            if self._job_deadline_exceeded("merged_labels"):
                return
            project_id = str(project.id)
            tracker = self._tracker_for_project(project.id)
            project_reviews = reviews_cache.get(project.id) or reviews_cache.get(
                project_id,
                [],
            )
            open_review_branches = {
                str(review.source_branch)
                for review in project_reviews
                if getattr(review, "source_branch", None)
                and str(getattr(review, "state", "") or "open").lower() == "open"
            }
            provider = None
            slug = ""
            if getattr(project, "repo_url", None):
                try:
                    provider = detect_provider(
                        project.repo_url,
                        access_token=getattr(project, "access_token", None),
                    )
                    if provider:
                        slug = extract_repo_slug(project.repo_url)
                except Exception as exc:  # noqa: BLE001 - best effort
                    logger.debug(
                        "Merged issue provider setup failed for %s: %s",
                        getattr(project, "name", project_id),
                        exc,
                    )
            try:
                merge_candidate_states = list(self.config.tracker_terminal_states)
                for state in (IN_REVIEW, NEEDS_CI_FIX, NEEDS_REBASE, NEEDS_HUMAN):
                    if state not in merge_candidate_states:
                        merge_candidate_states.append(state)
                closed_issues = tracker.fetch_issues_by_states(merge_candidate_states)
            except TrackerError:
                continue
            for issue in closed_issues:
                if self._job_deadline_exceeded("merged_labels"):
                    return
                if not issue.project_id:
                    issue.project_id = project_id
                issue_status = canonicalize_status(issue.state)
                labels = set(issue.labels or [])
                if (
                    issue_status in {MERGED, ARCHIVED}
                    or "merged" in labels
                    or "archive:yes" in labels
                ):
                    continue
                helper_issue = self._is_helper_landing_issue(issue)
                allow_provider_lookup = (
                    helper_issue
                    or not merged
                    or issue_status
                    in {IN_REVIEW, NEEDS_CI_FIX, NEEDS_REBASE, NEEDS_HUMAN}
                )
                branch = self._landed_branch_for_issue(
                    project,
                    issue,
                    project_id,
                    self._candidate_landing_branches_for_issue(issue, project),
                    merged,
                    open_review_branches,
                    provider if allow_provider_lookup else None,
                    slug if allow_provider_lookup else "",
                )
                if branch:
                    rollup_strategy = self._epic_rollup_child_strategy(
                        issue,
                        project_id,
                    )
                    if rollup_strategy == "shared" and not helper_issue:
                        logger.info(
                            "Skipped marking %s Merged from child branch %s: "
                            "shared epic workflow waits for the epic rollup merge",
                            issue.identifier,
                            branch,
                        )
                        continue
                    try:
                        tracker.update_issue(issue.identifier, status=MERGED)
                        logger.info(
                            "Marked %s as Merged (branch %s)",
                            issue.identifier,
                            branch,
                        )
                    except TrackerError as exc:
                        logger.debug(
                            "Failed to label %s as merged: %s", issue.identifier, exc
                        )

    def _reconcile_in_review_pr_outcomes(self) -> None:
        """Mark In Review tasks Needs CI Fix or Needs Rebase based on PR state.

        Uses the ``_reviews_cache`` populated by :meth:`_handle_review_check`
        to classify open PRs:

        * ``ci_status == "failed"`` → ``Needs CI Fix``
        * ``has_conflicts == True`` (and CI not already failed) → ``Needs Rebase``

        Tasks with healthy open PRs (CI passing, no conflicts) are left in
        ``In Review``.  Tasks with no PR in the cache are left to the
        :meth:`_reconcile_stale_in_review_tasks` sweep.

        Called from :meth:`_do_merged_labels` (maintenance lane).
        """
        reviews_cache = getattr(self, "_reviews_cache", {}) or {}
        if not reviews_cache:
            return

        for project in self.project_store.list_all():
            if self._job_deadline_exceeded("merged_labels"):
                return
            project_id = str(project.id)
            project_reviews = reviews_cache.get(project.id) or reviews_cache.get(
                project_id, []
            )
            if not project_reviews:
                continue

            # Build a branch → ReviewRequest index for fast lookups
            branch_to_review: dict[str, Any] = {}
            for review in project_reviews:
                branch = getattr(review, "source_branch", None)
                if branch:
                    branch_to_review[branch] = review

            if not branch_to_review:
                continue

            try:
                tracker = self._tracker_for_project(project_id)
                issues = tracker.fetch_issues_by_states([IN_REVIEW])
            except (ProjectError, TrackerError) as exc:
                logger.debug(
                    "PR outcome reconciliation fetch failed for %s: %s",
                    project_id,
                    exc,
                )
                continue

            for issue in issues:
                if self._job_deadline_exceeded("merged_labels"):
                    return
                if not issue.project_id:
                    issue.project_id = project_id
                if canonicalize_status(issue.state) != IN_REVIEW:
                    continue

                branch = self._stale_in_review_effective_branch(
                    issue,
                    project_id,
                    project,
                )
                review = branch_to_review.get(branch)
                if review is None:
                    # No open PR in cache — stale reconciliation handles this
                    continue

                ci_status = getattr(review, "ci_status", "") or ""
                has_conflicts = bool(getattr(review, "has_conflicts", False))

                if ci_status == "failed":
                    try:
                        tracker.update_issue(
                            issue.identifier, status=NEEDS_CI_FIX
                        )
                        logger.info(
                            "Marked %s as Needs CI Fix (PR #%s ci_status=failed)",
                            issue.identifier,
                            getattr(review, "id", "?"),
                        )
                    except TrackerError as exc:
                        logger.debug(
                            "Failed to mark %s Needs CI Fix: %s",
                            issue.identifier,
                            exc,
                        )
                elif has_conflicts:
                    try:
                        tracker.update_issue(
                            issue.identifier, status=NEEDS_REBASE
                        )
                        logger.info(
                            "Marked %s as Needs Rebase (PR #%s has_conflicts=True)",
                            issue.identifier,
                            getattr(review, "id", "?"),
                        )
                    except TrackerError as exc:
                        logger.debug(
                            "Failed to mark %s Needs Rebase: %s",
                            issue.identifier,
                            exc,
                        )

    def _reconcile_terminal_open_reviews(self) -> None:
        """Demote false terminal ``Merged`` state when an open PR still exists."""
        reviews_cache = getattr(self, "_reviews_cache", {}) or {}
        if not reviews_cache:
            return

        for project in self.project_store.list_all():
            if self._job_deadline_exceeded("merged_labels"):
                return
            project_id = str(project.id)
            project_reviews = reviews_cache.get(project.id) or reviews_cache.get(
                project_id, []
            )
            branch_to_review = {
                str(review.source_branch): review
                for review in project_reviews
                if getattr(review, "source_branch", None)
                and str(getattr(review, "state", "") or "").lower() == "open"
            }
            if not branch_to_review:
                continue
            provider = None
            slug = ""
            access_token = getattr(project, "access_token", None)
            if getattr(project, "repo_url", None) and access_token:
                try:
                    provider = detect_provider(
                        project.repo_url,
                        access_token=access_token,
                    )
                    if provider:
                        slug = extract_repo_slug(project.repo_url)
                except Exception as exc:  # noqa: BLE001 - cache fallback is enough
                    logger.debug(
                        "False-Merged provider setup failed for %s: %s",
                        getattr(project, "name", project_id),
                        exc,
                    )

            try:
                tracker = self._tracker_for_project(project_id)
                issues = tracker.fetch_issues_by_states([MERGED])
            except (ProjectError, TrackerError) as exc:
                logger.debug(
                    "Terminal/open-review reconciliation fetch failed for %s: %s",
                    project_id,
                    exc,
                )
                continue

            for issue in issues:
                if self._job_deadline_exceeded("merged_labels"):
                    return
                if not issue.project_id:
                    issue.project_id = project_id
                if canonicalize_status(issue.state) != MERGED:
                    continue

                branch = self._open_review_branch_for_issue(
                    issue,
                    project_id,
                    branch_to_review,
                )
                if not branch:
                    continue
                review = branch_to_review[branch]
                if provider is not None and slug:
                    try:
                        current_review = provider.find_pr_for_branch(slug, branch)
                    except Exception as exc:  # noqa: BLE001 - avoid false demotion
                        logger.debug(
                            "Skipping false-Merged repair for %s branch=%s: "
                            "could not verify cached open review: %s",
                            issue.identifier,
                            branch,
                            exc,
                        )
                        continue
                    current_state = str(
                        getattr(current_review, "state", "") or ""
                    ).lower()
                    if current_state != "open":
                        logger.debug(
                            "Skipping false-Merged repair for %s branch=%s: "
                            "cached open review is now %s",
                            issue.identifier,
                            branch,
                            current_state or "missing",
                        )
                        continue
                    review = current_review
                target_branch = self._review_target_branch(project, review)
                commits_ahead, _commit_lines, commit_error = (
                    self._count_review_branch_ahead(
                        project,
                        target_branch,
                        branch,
                    )
                )
                if commit_error:
                    logger.warning(
                        "Skipping false-Merged repair for %s branch=%s: could not "
                        "verify current branch tip against %s: %s",
                        issue.identifier,
                        branch,
                        target_branch,
                        commit_error,
                    )
                    continue
                if commits_ahead <= 0:
                    logger.debug(
                        "Skipping false-Merged repair for %s branch=%s: open "
                        "review branch is not ahead of %s",
                        issue.identifier,
                        branch,
                        target_branch,
                    )
                    continue

                new_status = IN_REVIEW
                if (getattr(review, "ci_status", "") or "") == "failed":
                    new_status = NEEDS_CI_FIX
                elif bool(getattr(review, "has_conflicts", False)):
                    new_status = NEEDS_REBASE

                try:
                    tracker.update_issue(issue.identifier, status=new_status)
                    logger.warning(
                        "Repaired false Merged state for %s: open review #%s "
                        "branch=%s is %d commit(s) ahead of %s; set status=%s",
                        issue.identifier,
                        getattr(review, "id", "?"),
                        branch,
                        commits_ahead,
                        target_branch,
                        new_status,
                    )
                except TrackerError as exc:
                    logger.debug(
                        "Failed to repair false Merged state for %s: %s",
                        issue.identifier,
                        exc,
                    )

    def _open_review_branch_for_issue(
        self,
        issue: Issue,
        project_id: str | None,
        branch_to_review: dict[str, ReviewRequest],
    ) -> str:
        """Return the open review branch matching ``issue``, if any."""
        candidates: list[str] = []
        for value in (
            getattr(issue, "work_branch", None),
            getattr(issue, "branch_name", None),
        ):
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        if (issue.issue_type or "").strip().lower() == "epic":
            try:
                candidates.append(
                    self.project_store.epic_branch_name(issue.identifier)
                )
            except Exception:  # noqa: BLE001 - fall back to the task identifier
                pass

        candidates.append(issue.identifier)
        for candidate in dict.fromkeys(candidates):
            if candidate in branch_to_review:
                return candidate
        return ""

    def _reconcile_stale_in_review_tasks(self) -> None:
        """Move ``In Review`` tasks out of review when no live PR/MR exists.

        ``In Review`` is only valid while the task branch has an open review
        artifact. If the artifact disappears, classify it from the strongest
        available signal:

        * merged branch or merged PR/MR -> ``Merged``
        * closed/unfound PR/MR with commits still ahead -> ``Open``
        * missing local evidence -> ``Needs Human``
        """
        reviews_cache = getattr(self, "_reviews_cache", {}) or {}
        merged_branches = getattr(self, "_merged_branches", set()) or set()

        for project in self.project_store.list_all():
            if self._job_deadline_exceeded("merged_labels"):
                return
            project_id = str(project.id)
            project_reviews = reviews_cache.get(project.id) or reviews_cache.get(
                project_id,
                [],
            )
            open_branches = {
                str(r.source_branch)
                for r in (project_reviews or [])
                if getattr(r, "source_branch", None)
            }
            try:
                tracker = self._tracker_for_project(project_id)
                issues = tracker.fetch_issues_by_states([IN_REVIEW])
            except (ProjectError, TrackerError) as exc:
                logger.debug(
                    "Stale In Review reconciliation fetch failed for %s: %s",
                    project_id,
                    exc,
                )
                continue

            provider = None
            slug = ""
            if getattr(project, "repo_url", None):
                provider = detect_provider(
                    project.repo_url, access_token=project.access_token
                )
                if provider:
                    slug = extract_repo_slug(project.repo_url)

            for issue in issues:
                if self._job_deadline_exceeded("merged_labels"):
                    return
                if not issue.project_id:
                    issue.project_id = project_id
                if canonicalize_status(issue.state) != IN_REVIEW:
                    continue
                branch = self._stale_in_review_effective_branch(
                    issue,
                    project_id,
                    project,
                )
                if not branch or branch in open_branches:
                    continue
                rollup_strategy = self._epic_rollup_child_strategy(
                    issue,
                    project_id,
                )
                if rollup_strategy == "shared":
                    parent_epic = self._resolve_parent_epic(issue)
                    epic_branch = ""
                    if parent_epic is not None:
                        try:
                            epic_branch = self._epic_branch_for_issue(parent_epic)
                        except Exception as exc:  # noqa: BLE001 - best effort
                            logger.debug(
                                "Failed to resolve epic branch for shared child "
                                "%s during stale In Review reconciliation: %s",
                                issue.identifier,
                                exc,
                            )
                    if epic_branch and self._done_review_child_has_epic_branch_work(
                        project,
                        epic_branch,
                        issue,
                    ):
                        self._mark_stale_in_review_done(tracker, issue, epic_branch)
                    else:
                        logger.debug(
                            "Leaving shared child %s in In Review: no open child "
                            "PR exists, but no matching work was found on the "
                            "epic review branch",
                            issue.identifier,
                        )
                    continue

                if branch in merged_branches and self._merged_branch_tip_landed(
                    project,
                    issue,
                    project_id,
                    branch,
                    rollup_strategy=rollup_strategy,
                ):
                    self._mark_stale_in_review_merged(tracker, issue, branch)
                    continue

                review = None
                if provider and slug:
                    try:
                        review = provider.find_pr_for_branch(slug, branch)
                    except Exception as exc:  # noqa: BLE001 - provider best effort
                        logger.debug(
                            "find_pr_for_branch failed for %s branch %s: %s",
                            project.name,
                            branch,
                            exc,
                        )
                review_state = str(getattr(review, "state", "") or "").lower()
                if review_state == "open":
                    continue
                if review_state == "merged":
                    self._mark_stale_in_review_merged(tracker, issue, branch)
                    continue

                target_branch = self._review_target_branch(project, review)
                ahead, commit_lines, commit_error = self._count_review_branch_ahead(
                    project,
                    target_branch,
                    branch,
                )
                if commit_error:
                    self._mark_stale_in_review_needs_human(
                        tracker,
                        issue,
                        branch,
                        target_branch,
                        commit_error,
                    )
                    continue
                if ahead <= 0:
                    self._mark_stale_in_review_merged(tracker, issue, branch)
                    continue

                self._reopen_stale_in_review_task(
                    tracker,
                    issue,
                    branch,
                    target_branch,
                    ahead,
                    commit_lines,
                    review,
                )

    def _reconcile_addendum_pr_outcomes_sweep(self) -> None:
        """Poll PR state for all ``in_review`` release addendums and reconcile.

        For each project that has a resolvable SCM provider, reads every
        source task's release-addendum list and delegates to
        :func:`~oompah.release_addendum_poller.poll_addendum_pr` for each
        ``in_review`` entry.

        State changes
        -------------
        - ``in_review`` + merged PR → ``merged`` (+ oompah comment on source)
        - ``in_review`` + closed PR → error field updated; stays ``in_review``
          (+ oompah comment); operator must call the retry endpoint to re-queue
        - All other states → skipped; the function is a no-op for them

        This sweep is idempotent: calling it twice with the same PR state
        produces the same result.  Failures on individual addendums are caught
        and logged without aborting the sweep.

        Called from :meth:`_do_merged_labels` (maintenance lane).
        """
        try:
            from oompah.release_addendum_poller import poll_addendum_pr
            from oompah.release_addendum_schema import (
                AddendumRepository,
                AddendumStatus,
            )
        except ImportError:
            logger.debug(
                "_reconcile_addendum_pr_outcomes_sweep: poller module not available"
            )
            return

        for project in self.project_store.list_all():
            if self._job_deadline_exceeded("merged_labels"):
                return

            project_id = str(project.id)
            repo_url = getattr(project, "repo_url", None)
            if not repo_url:
                continue

            try:
                provider = detect_provider(repo_url, access_token=getattr(project, "access_token", None))
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "_reconcile_addendum_pr_outcomes_sweep: provider detection failed for %s: %s",
                    project_id,
                    exc,
                )
                continue

            if not provider:
                continue

            slug = extract_repo_slug(repo_url)

            try:
                tracker = self._tracker_for_project(project_id)
                sources = tracker.fetch_all_issues()
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "_reconcile_addendum_pr_outcomes_sweep: fetch_all_issues failed for %s: %s",
                    project_id,
                    exc,
                )
                continue

            for source in sources:
                if self._job_deadline_exceeded("merged_labels"):
                    return

                identifier = (
                    getattr(source, "identifier", None)
                    or getattr(source, "id", None)
                )
                if not identifier:
                    continue
                identifier = str(identifier)

                try:
                    addendums = AddendumRepository(tracker).read(identifier)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "_reconcile_addendum_pr_outcomes_sweep: read failed for %s: %s",
                        identifier,
                        exc,
                    )
                    continue

                for addendum in addendums:
                    if addendum.status is not AddendumStatus.IN_REVIEW:
                        continue
                    try:
                        poll_addendum_pr(
                            tracker,
                            identifier,
                            addendum,
                            scm=provider,
                            repo=slug,
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "_reconcile_addendum_pr_outcomes_sweep: poll failed for %s %r: %s",
                            identifier,
                            addendum.id,
                            exc,
                        )

    def _review_target_branch(
        self,
        project: Project,
        review: ReviewRequest | None,
    ) -> str:
        """Return the review target branch with a safe project/default fallback."""
        target = getattr(review, "target_branch", "") if review else ""
        if not isinstance(target, str) or not target:
            target = getattr(project, "default_branch", "")
        if not isinstance(target, str) or not target:
            target = "main"
        return target

    def _target_branch_for_merged_signal(
        self,
        project: Project,
        issue: Issue,
        project_id: str | None,
        rollup_strategy: str | None = None,
    ) -> str:
        """Return the branch that should contain a merged task branch tip."""
        target = getattr(issue, "target_branch", None)
        if isinstance(target, str) and target.strip():
            return target.strip()
        project_target = getattr(project, "default_branch", None)
        if isinstance(project_target, str) and project_target.strip():
            return project_target.strip()
        return "main"

    def _managed_branch_ref_exists(self, repo_path: str, branch: str) -> bool:
        """Return True when the managed repo currently has a local/remote ref."""
        candidates = [branch]
        if not branch.startswith("origin/"):
            candidates.append(f"origin/{branch}")
        for candidate in candidates:
            try:
                result = subprocess.run(
                    [
                        "git",
                        "rev-parse",
                        "--verify",
                        "--quiet",
                        f"{candidate}^{{commit}}",
                    ],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
                continue
            if result.returncode == 0:
                return True
        return False

    def _merged_branch_tip_landed(
        self,
        project: Project,
        issue: Issue,
        project_id: str | None,
        branch: str,
        rollup_strategy: str | None = None,
    ) -> bool:
        """Return True when a merged-branch signal still matches the branch tip.

        Forge merged-branch lists are keyed by branch name. If a branch name is
        reused after an earlier PR merged, the old forge signal is stale. In
        that case the current remote branch tip must not be promoted to
        ``Merged`` or skipped by deferred review handoff until git shows it is
        contained in the target branch.
        """
        repo_path = getattr(project, "repo_path", "") or ""
        if (
            not isinstance(repo_path, str)
            or not repo_path
            or not os.path.isdir(repo_path)
        ):
            return True

        branch = (branch or "").strip()
        if not branch:
            return True
        if not self._managed_branch_ref_exists(repo_path, branch):
            # Branch deleted after merge: the forge merged-PR signal is the
            # strongest remaining evidence.
            return True

        target_branch = self._target_branch_for_merged_signal(
            project,
            issue,
            project_id,
            rollup_strategy=rollup_strategy,
        )
        ahead, _commit_lines, commit_error = self._count_review_branch_ahead(
            project,
            target_branch,
            branch,
        )
        if commit_error:
            logger.warning(
                "Skipping merged-branch promotion for %s branch=%s: could not "
                "verify current branch tip against %s: %s",
                issue.identifier,
                branch,
                target_branch,
                commit_error,
            )
            return False
        if ahead > 0:
            logger.info(
                "Skipping merged-branch promotion for %s branch=%s: current "
                "tip is %d commit(s) ahead of %s despite stale merged history",
                issue.identifier,
                branch,
                ahead,
                target_branch,
            )
            return False
        return True

    def _stale_in_review_effective_branch(
        self,
        issue: Issue,
        project_id: str | None,
        project: Project | None = None,
    ) -> str:
        """Return the branch stale-review reconciliation should verify."""
        if (issue.issue_type or "").strip().lower() == "epic":
            try:
                return self._epic_branch_for_issue(issue)
            except Exception:  # noqa: BLE001 - fall back to the legacy branch rule
                pass
        if project is None and project_id:
            try:
                project = self.project_store.get(project_id)
            except Exception:  # noqa: BLE001 - fall back to local issue fields
                project = None
        return self._branch_for_issue(issue, project)

    def _count_review_branch_ahead(
        self,
        project: Project,
        target_branch: str,
        branch: str,
    ) -> tuple[int, list[str], str]:
        repo_path = getattr(project, "repo_path", "")
        if not isinstance(repo_path, str) or not repo_path:
            return 0, [], "project has no managed repository path configured"
        try:
            from oompah.close_gate import _count_commits_ahead

            return _count_commits_ahead(repo_path, target_branch, branch)
        except Exception as exc:  # noqa: BLE001 - keep reconciliation best effort
            return 0, [], str(exc)

    def _mark_stale_in_review_merged(
        self,
        tracker: TrackerProtocol,
        issue: Issue,
        branch: str,
    ) -> None:
        try:
            tracker.update_issue(issue.identifier, status=MERGED)
            logger.info(
                "Marked %s as Merged during stale In Review reconciliation "
                "(branch %s)",
                issue.identifier,
                branch,
            )
        except TrackerError as exc:
            logger.debug(
                "Failed to mark stale In Review task %s merged: %s",
                issue.identifier,
                exc,
            )

    def _mark_stale_in_review_done(
        self,
        tracker: TrackerProtocol,
        issue: Issue,
        branch: str,
    ) -> None:
        """Mark an epic child ``Done`` once its work is on the epic branch.

        Shared children work directly on the epic branch and are complete for
        purposes of opening the epic rollup PR, but they are not globally
        ``Merged`` until that epic branch lands on the target.
        """
        try:
            tracker.update_issue(issue.identifier, status=DONE)
            logger.info(
                "Marked %s as Done during stale In Review reconciliation "
                "(child branch %s merged into epic branch)",
                issue.identifier,
                branch,
            )
        except TrackerError as exc:
            logger.debug(
                "Failed to mark stale In Review task %s done: %s",
                issue.identifier,
                exc,
            )

    def _mark_stale_in_review_needs_human(
        self,
        tracker: TrackerProtocol,
        issue: Issue,
        branch: str,
        target_branch: str,
        reason: str,
    ) -> None:
        comment = (
            "Review reconciliation could not verify this task branch after its "
            "review artifact disappeared.\n\n"
            f"Branch: `{branch}`\n"
            f"Target branch: `{target_branch}`\n"
            f"Reason: {reason}\n\n"
            "Required: confirm whether the branch landed, restore the PR/MR, "
            "or archive the task."
        )
        try:
            tracker.update_issue(issue.identifier, status=NEEDS_HUMAN)
            tracker.add_comment(issue.identifier, comment, author="oompah")
            logger.warning(
                "Marked %s Needs Human during stale In Review reconciliation: %s",
                issue.identifier,
                reason,
            )
        except TrackerError as exc:
            logger.debug(
                "Failed to mark stale In Review task %s Needs Human: %s",
                issue.identifier,
                exc,
            )

    def _reopen_stale_in_review_task(
        self,
        tracker: TrackerProtocol,
        issue: Issue,
        branch: str,
        target_branch: str,
        commits_ahead: int,
        commit_lines: list[str],
        review: ReviewRequest | None,
    ) -> None:
        commit_noun = "commit" if commits_ahead == 1 else "commits"
        if review is not None:
            review_id = getattr(review, "id", "")
            review_note = (
                f"Last known review #{review_id} was closed without merge."
                if review_id
                else "The last known review was closed without merge."
            )
        else:
            review_note = "No PR/MR for this branch was found."
        lines = [
            "Review reconciliation reopened this task because it was marked "
            "In Review but no open review artifact exists.",
            "",
            review_note,
            f"Branch: `{branch}`",
            f"Target branch: `{target_branch}`",
            f"Unmerged commits: {commits_ahead} {commit_noun}",
        ]
        for line in commit_lines[:10]:
            lines.append(f"  {line}")
        lines.extend(
            [
                "",
                "Required: restore or recreate the PR/MR for this branch, "
                "then move the task back to In Review after the review exists.",
            ]
        )
        try:
            tracker.update_issue(issue.identifier, status=OPEN)
            tracker.add_comment(issue.identifier, "\n".join(lines), author="oompah")
            logger.warning(
                "Reopened stale In Review task %s: branch %s has %d "
                "unmerged %s and no open review",
                issue.identifier,
                branch,
                commits_ahead,
                commit_noun,
            )
        except TrackerError as exc:
            logger.debug(
                "Failed to reopen stale In Review task %s: %s",
                issue.identifier,
                exc,
            )

    def _reconcile_release_picks_pass(self) -> None:
        """Run the release-pick reconciliation pass across all projects.

        Calls :func:`~oompah.release_pick_reconciler.reconcile_release_picks`
        for every configured project, passing the project store so that
        target-branch worktrees are created alongside child backport tasks,
        and passing the SCM provider and repo slug so that cherry-pick
        commits can be applied, pushed, and turned into PRs.

        Results are logged at INFO when any entries were advanced or child
        tasks created.

        This method is intentionally best-effort: exceptions from individual
        projects are caught and logged at DEBUG level so a single broken
        project never prevents reconciliation for the others.  When no
        projects are configured (legacy single-tracker mode), the pass is
        skipped — the release-pick feature requires per-project configuration.
        """
        from oompah.release_pick_reconciler import reconcile_release_picks
        from oompah.scm import detect_provider, extract_repo_slug

        for project in self.project_store.list_all():
            if self._job_deadline_exceeded("release_picks"):
                logger.debug("release_pick reconciliation stopped at runtime budget")
                break
            try:
                tracker = self._tracker_for_project(str(project.id))
                # Resolve SCM provider and repo slug for cherry-pick+PR step.
                # Best-effort: if detection fails we still run the earlier
                # reconcile steps (task creation, worktree creation).
                scm = None
                repo = None
                try:
                    if project.repo_url:
                        scm = detect_provider(
                            project.repo_url,
                            access_token=getattr(project, "access_token", None),
                        )
                        repo = extract_repo_slug(project.repo_url)
                except Exception as scm_exc:  # noqa: BLE001
                    logger.debug(
                        "release_pick reconciliation: SCM provider detection"
                        " failed for project %s: %s",
                        getattr(project, "name", project),
                        scm_exc,
                    )
                result = reconcile_release_picks(
                    tracker,
                    project_store=self.project_store,
                    project_id=str(project.id),
                    scm=scm,
                    repo=repo,
                    should_stop=lambda: self._job_deadline_exceeded("release_picks"),
                )
                if result.changed:
                    logger.info(
                        "release_pick reconciliation [%s]: scanned=%d advanced=%d"
                        " created=%d errors=%d",
                        project.name,
                        result.scanned,
                        result.advanced,
                        result.created,
                        result.errors,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "release_pick reconciliation failed for project %s: %s",
                    getattr(project, "name", project),
                    exc,
                )

        # Commit-centric release delivery persists work in a project ledger,
        # rather than task metadata.  Claim and execute it here so a UI queue
        # action is processed by the same durable maintenance lane as legacy
        # release picks.
        self._process_release_delivery_queue()
        # After execution, dispatch internal conflict-resolution agents for
        # any deliveries that are blocked due to merge conflicts.  This must
        # run after _process_release_delivery_queue so newly-blocked deliveries
        # are visible before the dispatch pass.
        self._dispatch_delivery_conflict_agents()

    def _process_release_delivery_queue(self) -> None:
        """Claim and execute one pending ledger delivery per project."""
        for project in self.project_store.list_all():
            if self._job_deadline_exceeded("release_picks"):
                break
            try:
                tracker = self._tracker_for_project(str(project.id))
                store = make_delivery_store(project, git_writer=tracker)
                queue = ReleaseDeliveryQueue(
                    str(project.id), store, worker_id="orchestrator-release-delivery"
                )
                item = queue.claim_one()
                if item is None:
                    continue
                if not project.repo_url:
                    logger.warning("release delivery %s has no repository URL", item.delivery_id)
                    continue
                scm = detect_provider(
                    project.repo_url,
                    access_token=getattr(project, "access_token", None),
                )
                repo = extract_repo_slug(project.repo_url)
                result = cherry_pick_delivery(
                    store,
                    item.delivery,
                    project_store=self.project_store,
                    project_id=str(project.id),
                    scm=scm,
                    repo=repo,
                    project=project,
                    sync_source_branch=True,
                )
                logger.info(
                    "release delivery %s for %s is now %s",
                    result.id,
                    project.name,
                    result.status.value,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "release delivery processing failed for project %s: %s",
                    getattr(project, "name", project),
                    exc,
                )

    # ------------------------------------------------------------------
    # Conflict-resolution agent dispatch for ledger deliveries (OOMPAH-214)
    # ------------------------------------------------------------------

    def _dispatch_delivery_conflict_agents(self) -> None:
        """Dispatch an internal conflict-resolution task for each delivery
        that is ``blocked`` due to a merge conflict and has not yet had an
        agent dispatched.

        Design invariants
        -----------------

        * Only ``blocked`` deliveries with a non-empty ``error`` containing
          conflict keywords are considered.
        * Idempotency: ``conflict_agent_task_id`` is set before the task is
          created; a second call for the same delivery is a no-op.
        * No child task is created in the managed project.  The
          conflict-resolution task is created in the oompah management tracker
          (``self.tracker``) so it is invisible to the managed project's users.
        * On recovery, the conflict-resolution agent resets the delivery to
          ``open`` and clears ``conflict_agent_task_id`` so the executor can
          re-run and create the PR.
        """
        from oompah.release_addendum_schema import AddendumStatus as _AS

        for project in self.project_store.list_all():
            try:
                tracker = self._tracker_for_project(str(project.id))
                store = make_delivery_store(project, git_writer=tracker)
                ledger = store.read_ledger()
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "_dispatch_delivery_conflict_agents: cannot read ledger "
                    "for project %s: %s",
                    getattr(project, "name", project),
                    exc,
                )
                continue

            for delivery in ledger.deliveries:
                if delivery.status is not _AS.BLOCKED:
                    continue
                if not delivery.error:
                    continue
                if not _is_delivery_conflict_error(delivery.error):
                    continue
                if delivery.conflict_agent_task_id:
                    # Already dispatched — skip (idempotent).
                    logger.debug(
                        "_dispatch_delivery_conflict_agents: delivery %r already "
                        "has conflict agent %r; skipping",
                        delivery.id,
                        delivery.conflict_agent_task_id,
                    )
                    continue
                try:
                    self._dispatch_conflict_agent_for_delivery(project, store, delivery)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "_dispatch_delivery_conflict_agents: failed to dispatch "
                        "conflict agent for delivery %r in project %s: %s",
                        delivery.id,
                        getattr(project, "name", project),
                        exc,
                    )

    def _dispatch_conflict_agent_for_delivery(
        self,
        project: Any,
        store: Any,
        delivery: Any,
    ) -> None:
        """Create an internal oompah conflict-resolution task for *delivery*
        and stamp the delivery record with the new task ID.

        The task is created in the oompah management tracker (``self.tracker``)
        so it does not appear in the managed project's user-facing backlog.
        The delivery's ``conflict_agent_task_id`` is updated atomically to
        prevent duplicate dispatches across ticks.

        Args:
            project: Project owning the delivery (provides ``name``,
                ``repo_path``, ``id``).
            store: :class:`~oompah.release_delivery_store.ReleaseDeliveryStore`
                for the managed project.
            delivery: The ``blocked``
                :class:`~oompah.release_delivery_store.ReleaseDelivery` to
                dispatch a conflict agent for.
        """
        worktree_key = make_delivery_worktree_key(delivery)
        try:
            wt_path = self.project_store.worktree_path_for(
                str(project.id), worktree_key
            )
        except Exception:  # noqa: BLE001
            wt_path = "<unknown — check delivery worktree key>"

        project_name = getattr(project, "name", str(project.id))
        title = (
            f"Resolve merge conflict: {project_name} {delivery.target_branch} "
            f"delivery {delivery.id}"
        )
        description = (
            f"Merge conflict in release delivery for project **{project_name}**.\n\n"
            f"**Delivery ID:** `{delivery.id}`\n"
            f"**Target branch:** `{delivery.target_branch}`\n"
            f"**Work branch:** `{delivery.work_branch or '<not yet set>'}`\n"
            f"**Worktree path:** `{wt_path}`\n\n"
            f"**Conflict error:**\n```\n{delivery.error}\n```\n\n"
            "**Instructions for the conflict-resolution agent:**\n\n"
            "1. Navigate to the worktree path shown above.\n"
            "2. Resolve all merge conflicts (check `git status`).\n"
            "3. Stage the resolved files: `git add <files>`\n"
            "4. Commit the resolution: `git commit --no-edit`\n"
            f"5. Push the branch: "
            f"`git push origin HEAD:{delivery.work_branch}`\n"
            "6. Reset the delivery to open so the executor creates the PR:\n"
            "   ```python\n"
            "   from oompah.release_delivery_store import ReleaseDeliveryStore\n"
            "   from oompah.release_addendum_schema import AddendumStatus\n"
            f"   store = ReleaseDeliveryStore({project.repo_path!r}, "
            f"{str(project.id)!r})\n"
            f"   store.update({delivery.id!r}, "
            f"status=AddendumStatus.OPEN,\n"
            "              claimed_by=None, lease_expires_at=None,\n"
            "              conflict_agent_task_id=None)\n"
            "   ```\n\n"
            "_This task was auto-filed by oompah for internal conflict resolution. "
            "Do NOT create a branch or PR for this task itself._"
        )

        new_task = self.tracker.create_issue(
            title=title,
            issue_type="task",
            description=description,
            priority=0,
            labels=["merge-conflict"],
            initial_status=NEEDS_REBASE,
        )

        # Stamp the delivery with the new task ID so we don't re-dispatch.
        store.update(
            delivery.id,
            conflict_agent_task_id=new_task.identifier,
        )
        logger.info(
            "_dispatch_conflict_agent_for_delivery: filed %s for delivery %r "
            "(project=%s target=%s worktree=%s)",
            new_task.identifier,
            delivery.id,
            project_name,
            delivery.target_branch,
            wt_path,
        )

    def _label_merged_epics(self) -> None:
        """When an epic→main PR has merged, mark the epic AND all its
        children ``Merged``.

        An epic lands as a single ``epic-<id>`` → main PR; the children
        have no individual merged branch, and the epic itself sits in a
        non-dispatch state — so neither is caught by
        :meth:`_label_merged_issues`. We detect the merged epic branch
        directly and roll ``Merged`` down to every child (when the epic
        merges, the epic and the tasks its branch contained all become
        Merged). Idempotent: already-terminal epics drop out of
        :meth:`_all_non_terminal_epics` and already-merged children are
        skipped.
        """
        provider_cache: dict[str, tuple[Any | None, str]] = {}
        for epic in self._all_non_terminal_epics():
            if self._job_deadline_exceeded("merged_labels"):
                return
            project_id = epic.project_id
            if not project_id:
                continue
            try:
                epic_branch = self._epic_branch_for_issue(epic)
            except Exception:  # noqa: BLE001
                continue
            project = self.project_store.get(project_id)
            if not project or not getattr(project, "repo_url", None):
                continue
            if project_id not in provider_cache:
                try:
                    provider = detect_provider(
                        project.repo_url,
                        access_token=getattr(project, "access_token", None),
                    )
                    slug = extract_repo_slug(project.repo_url) if provider else ""
                except Exception as exc:  # noqa: BLE001 - best effort
                    logger.debug(
                        "Merged epic provider setup failed for %s: %s",
                        project_id,
                        exc,
                    )
                    provider, slug = None, ""
                provider_cache[project_id] = (provider, slug)
            provider, slug = provider_cache[project_id]
            if provider is None or not slug:
                continue
            target_branch = self._resolve_epic_target_branch(epic, project)
            if not self._epic_branch_landed_on_target(
                provider,
                slug,
                epic_branch,
                target_branch,
            ):
                continue
            self._mark_epic_merged(epic, epic_branch=epic_branch)

    def _all_merged_epics(self) -> list[Issue]:
        """Return merged epic/rollup parents that may still have open children."""
        out: list[Issue] = []
        projects = self.project_store.list_all()
        trackers: list[tuple[str | None, TrackerProtocol]] = []
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
                issues = list(tracker.fetch_all_issues())
            except (TrackerError, ProjectError) as exc:
                logger.debug("merged epic fetch failed for %s: %s", pid, exc)
                continue

            parent_ids = {
                str(issue.parent_id).strip()
                for issue in issues
                if (issue.parent_id or "").strip()
            }
            for issue in issues:
                if pid:
                    issue.project_id = pid
                if canonicalize_status(issue.state) != MERGED:
                    continue
                is_declared_epic = (
                    (issue.issue_type or "").strip().lower() == "epic"
                )
                issue_ids = {
                    str(value).strip()
                    for value in (issue.id, issue.identifier)
                    if value
                }
                has_children = bool(issue_ids & parent_ids)
                is_rollup_parent = is_declared_epic or has_children
                if is_rollup_parent:
                    out.append(issue)
        return out

    def _reconcile_merged_epic_children(self) -> None:
        """Ensure children of already-merged epics are also terminal.

        A restart or stale review-cache race can mark the epic ``Merged`` before
        every child is swept. Since the epic is the authoritative rollup, any
        non-archived child under it should become ``Merged`` as well.
        """
        for epic in self._all_merged_epics():
            if self._job_deadline_exceeded("merged_labels"):
                return
            try:
                children = self._fetch_epic_children(epic)
            except Exception:  # noqa: BLE001 - reconciliation is best effort
                children = []
            if not any(
                canonicalize_status(child.state) not in {MERGED, ARCHIVED}
                for child in children
            ):
                continue
            try:
                epic_branch = self._epic_branch_for_issue(epic)
            except Exception:  # noqa: BLE001
                epic_branch = epic.identifier
            self._mark_epic_merged(epic, epic_branch=epic_branch)

    def _mark_epic_merged(self, epic: Issue, *, epic_branch: str | None = None) -> None:
        """Mark ``epic`` and all its non-terminal children ``Merged``.

        Shared by :meth:`_label_merged_epics` (driven by the async
        ``_merged_branches`` set) and :meth:`_open_epic_main_prs` (driven by
        an authoritative per-epic ``find_pr_for_branch`` lookup). Idempotent:
        already-``Merged``/``Archived`` children are skipped, and a re-marked
        epic simply re-asserts ``Merged``.
        """
        if epic_branch is None:
            try:
                epic_branch = self._epic_branch_for_issue(epic)
            except Exception:  # noqa: BLE001
                epic_branch = epic.identifier

        tracker = self._tracker_for_issue(epic)
        try:
            tracker.update_issue(epic.identifier, status=MERGED)
            self._clear_stuck_epic_alert(epic.identifier)
            logger.info(
                "Marked epic %s Merged (branch %s merged to main)",
                epic.identifier,
                epic_branch,
            )
        except TrackerError as exc:
            logger.debug("Failed to mark epic %s merged: %s", epic.identifier, exc)

        try:
            children = self._fetch_epic_children(epic)
        except Exception:  # noqa: BLE001
            children = []
        for child in children:
            if self._job_deadline_exceeded("merged_labels"):
                return
            if canonicalize_status(child.state) in (MERGED, ARCHIVED):
                continue
            try:
                tracker.update_issue(child.identifier, status=MERGED)
                logger.info(
                    "Marked epic child %s Merged (epic %s landed)",
                    child.identifier,
                    epic.identifier,
                )
            except TrackerError as exc:
                logger.debug(
                    "Failed to mark child %s merged: %s", child.identifier, exc
                )

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
        and file P0 escalation tasks. Per-project loop-coverage stats
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
            provider = detect_provider(
                project.repo_url, access_token=project.access_token
            )
            if not provider:
                continue
            slug = extract_repo_slug(project.repo_url)
            reviews = reviews_cache.get(project.id, [])

            # Loop-coverage tracking for D2.
            considered = 0
            actions_fired = 0
            considered_ids: set[str] = set()
            non_draft_total = sum(1 for r in reviews if not r.draft)

            # Pre-load the project's top-N churn-magnet files so we can
            # flag high-risk PRs (oompah-zlz_2-rxwe.2).
            try:
                _cm_store = _get_churn_store()
                _cm_top_files = set(
                    fp for fp, _ in _cm_store.get_top_files(project.id)
                )
            except Exception:
                _cm_top_files = set()

            for review in reviews:
                if review.draft:
                    continue
                considered += 1
                considered_ids.add(str(review.id))
                review_id = review.id
                # tracker used by _clear_merge_conflict_label_for_branch and
                # by the external-rebase stale-label check (oompah-zlz_2-683l)
                tracker = self._tracker_for_project(project.id)

                epic_block_reason = self._yolo_epic_strategy_block_reason(
                    project,
                    tracker,
                    review,
                )
                if epic_block_reason:
                    if self._close_invalid_epic_policy_review(
                        project,
                        provider,
                        slug,
                        tracker,
                        review,
                        epic_block_reason,
                        tick=tick,
                    ):
                        actions_fired += 1
                        continue
                    logger.warning(
                        "YOLO GATE: skipping %s MR #%s — %s",
                        project.name,
                        review_id,
                        epic_block_reason,
                    )
                    self._record_yolo_action(
                        project.id,
                        str(review_id),
                        "gate_blocked",
                        "success",
                        epic_block_reason,
                        tick=tick,
                    )
                    actions_fired += 1
                    continue

                # Churn-magnet check (oompah-zlz_2-rxwe.2): if this PR
                # touches a file in the project's top-N churn-magnet list,
                # flag it on the review and add a label to the PR.
                if _cm_top_files and not review.churn_magnet:
                    try:
                        pr_files = provider.get_review_files(slug, review_id)
                        if pr_files:
                            # Cache the file list on the review object so
                            # downstream consumers (like /api/v1/reviews)
                            # have access to it without another API call.
                            review.files = pr_files
                            if set(pr_files) & _cm_top_files:
                                review.churn_magnet = True
                                if "churn-magnet" not in review.labels:
                                    provider.add_review_label(
                                        slug, review_id, "churn-magnet"
                                    )
                                    review.labels.append("churn-magnet")
                                    _overlap = sorted(
                                        set(pr_files) & _cm_top_files
                                    )
                                    review.churn_magnet_files = _overlap
                                    logger.info(
                                        "YOLO: churn-magnet PR %s #%s "
                                        "(touches: %s)",
                                        project.name,
                                        review_id,
                                        ", ".join(_overlap[:5]),
                                    )
                                else:
                                    logger.debug(
                                        "YOLO: churn-magnet PR %s #%s already labeled",
                                        project.name,
                                        review_id,
                                    )
                    except Exception as _exc:
                        logger.debug(
                            "Churn-magnet: get_review_files failed for %s #%s: %s",
                            project.name,
                            review_id,
                            _exc,
                        )

                # Conflict check FIRST — before the auto_merge_enabled
                # idempotency guard. A PR enqueued for auto-merge can
                # go DIRTY when another PR lands with overlapping files,
                # and the queue then sits forever waiting for manual
                # conflict resolution. We must dispatch a conflict agent
                # in that case even though auto_merge is "enabled" —
                # GitHub will never make progress on a DIRTY queued PR.
                # (oompah-zlz_2-l81)
                if review.has_conflicts:
                    # Suppress conflict dispatch when the source branch is
                    # an epic branch already being proactively rebased.
                    # The rebase agent will handle any conflicts.
                    if self._is_epic_branch_being_rebased(
                        project.id, review.source_branch
                    ):
                        logger.debug(
                            "YOLO: suppressing conflict notify for %s MR #%s "
                            "(proactive rebase in flight)",
                            project.name,
                            review_id,
                        )
                        continue
                    logger.info(
                        "YOLO: conflicts on %s review #%s — dispatching conflict agent",
                        project.name,
                        review_id,
                    )
                    self._yolo_notify_conflict(project, provider, slug, review_id)
                    self._record_yolo_action(
                        project.id,
                        str(review_id),
                        "notify_conflict",
                        "success",
                        "",
                        tick=tick,
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
                    logger.info(
                        "YOLO: auto-retrying failed CI on %s MR #%s",
                        project.name,
                        review_id,
                    )
                    self._yolo_retry_ci(project, review)
                    self._record_yolo_action(
                        project.id,
                        str(review_id),
                        "retry_ci",
                        "success",
                        "",
                        tick=tick,
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
                        project.name,
                        review_id,
                    )
                    # Treat "already enqueued" as a successful enqueue
                    # outcome for watchdog purposes — clears any prior
                    # consecutive-failure run and prevents D1 from
                    # firing on PRs GitHub is already handling.
                    self._record_yolo_action(
                        project.id,
                        str(review_id),
                        "enqueue",
                        "success",
                        "",
                        tick=tick,
                    )
                    continue

                # High-risk PR gate (oompah-zlz_2-rxwe.3): when the project's
                # churn_magnet_gate is enabled, skip merge/enqueue for PRs
                # that have the churn-magnet label AND are stale
                # (needs_rebase=True).  This prevents YOLO from silently
                # merging a PR that is behind its target branch.
                # Placed OUTSIDE the ci_ok / needs_rebase base condition so
                # stale PRs are caught regardless of CI state.
                if (
                    getattr(project, "churn_magnet_gate_enabled", False)
                    and "churn-magnet" in review.labels
                    and review.needs_rebase
                ):
                    logger.warning(
                        "YOLO GATE: skipping merge/enqueue for %s #%s — "
                        "PR has [churn-magnet] label and is stale "
                        "(needs_rebase=True).  Gate is enabled on project "
                        "'%s'; rebase and re-trigger when ready.",
                        project.name,
                        review_id,
                        project.name,
                    )
                    self._record_yolo_action(
                        project.id,
                        str(review_id),
                        "gate_blocked",
                        "success",
                        "churn_magnet_gate: stale churn-magnet PR",
                        tick=tick,
                    )
                    actions_fired += 1
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
                        merge_queue
                        and switch_key in self._yolo_already_mergeable_switched
                    )
                    if merge_queue and not use_direct_merge_fallback:
                        logger.info(
                            "YOLO: enqueued for merge %s MR #%s (ci=%s)",
                            project.name,
                            review_id,
                            review.ci_status,
                        )
                        success, msg = provider.enable_auto_merge(slug, review_id)
                        if success:
                            logger.info(
                                "YOLO: enqueued %s MR #%s", project.name, review_id
                            )
                            self._clear_repo_config_error(project.id, str(review_id))
                            self._record_yolo_action(
                                project.id,
                                str(review_id),
                                "enqueue",
                                "success",
                                "",
                                tick=tick,
                            )
                            self._clear_already_mergeable_switch(
                                project.id, str(review_id)
                            )
                            self._clear_merge_conflict_label_for_branch(
                                project,
                                tracker,
                                review.source_branch,
                            )
                            self._yolo_comment_enqueued(
                                tracker, project, review, str(review_id)
                            )
                            actions_fired += 1
                            # Merge-queue mode: GitHub's queue handles
                            # serialization, so a successful enqueue does
                            # NOT need to break. Continue iterating to
                            # enqueue any further qualified PRs in the
                            # same tick. (oompah-zlz_2-grw, fix B)
                            continue
                        else:
                            self._record_yolo_action(
                                project.id,
                                str(review_id),
                                "enqueue",
                                "failure",
                                msg or "",
                                tick=tick,
                            )
                            # D4: check whether to switch strategy now.
                            self._maybe_switch_to_direct_merge(
                                project.id,
                                str(review_id),
                            )
                            self._handle_yolo_merge_failure(
                                project,
                                provider,
                                slug,
                                review_id,
                                msg,
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
                            project.name,
                            review_id,
                        )
                        success, msg = provider.merge_review(slug, review_id)
                        if success:
                            logger.info(
                                "YOLO: direct-merge fallback succeeded for %s MR #%s",
                                project.name,
                                review_id,
                            )
                            self._clear_repo_config_error(project.id, str(review_id))
                            self._record_yolo_action(
                                project.id,
                                str(review_id),
                                "merge_after_already_mergeable",
                                "success",
                                "",
                                tick=tick,
                            )
                            self._clear_already_mergeable_switch(
                                project.id, str(review_id)
                            )
                            self._clear_merge_conflict_label_for_branch(
                                project,
                                tracker,
                                review.source_branch,
                            )
                            self._yolo_mark_task_merged(
                                tracker, project, review, str(review_id)
                            )
                            actions_fired += 1
                            # Direct merge (fallback path): each merge
                            # changes the target branch, so subsequent
                            # PRs would need a rebase before they can
                            # merge cleanly. Serialize: one merge per
                            # project per tick. (oompah-zlz_2-grw)
                            break
                        else:
                            self._record_yolo_action(
                                project.id,
                                str(review_id),
                                "merge_after_already_mergeable",
                                "failure",
                                msg or "",
                                tick=tick,
                            )
                            self._handle_yolo_merge_failure(
                                project,
                                provider,
                                slug,
                                review_id,
                                msg,
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
                        logger.info(
                            "YOLO: auto-merging %s MR #%s (ci=%s)",
                            project.name,
                            review_id,
                            review.ci_status,
                        )
                        success, msg = provider.merge_review(slug, review_id)
                        if success:
                            logger.info(
                                "YOLO: merged %s MR #%s", project.name, review_id
                            )
                            self._clear_repo_config_error(project.id, str(review_id))
                            self._record_yolo_action(
                                project.id,
                                str(review_id),
                                "merge",
                                "success",
                                "",
                                tick=tick,
                            )
                            self._clear_merge_conflict_label_for_branch(
                                project,
                                tracker,
                                review.source_branch,
                            )
                            self._yolo_mark_task_merged(
                                tracker, project, review, str(review_id)
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
                                project.id,
                                str(review_id),
                                "merge",
                                "failure",
                                msg or "",
                                tick=tick,
                            )
                            self._handle_yolo_merge_failure(
                                project,
                                provider,
                                slug,
                                review_id,
                                msg,
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
                # **External-rebase check** (oompah-zlz_2-683l): PR might have
                # carried merge-conflict from a prior tick but the branch was
                # rebased externally (e.g. operator or CI script). GitHub now
                # reports has_conflicts=False and the label is stale. Clear it
                # here so the task doesn't stay blocked by a wrong label while
                # CI runs its pipeline.
                elif review.source_branch and not review.has_conflicts:
                    self._clear_merge_conflict_label_for_branch(
                        project,
                        tracker,
                        review.source_branch,
                    )
                logger.debug(
                    "YOLO: skipping %s MR #%s branch=%s (ci=%s, conflicts=%s, needs_rebase=%s)",
                    project.name,
                    review_id,
                    review.source_branch,
                    review.ci_status,
                    review.has_conflicts,
                    review.needs_rebase,
                )

            # Per-project end-of-loop instrumentation (D2).
            missing_ids = sorted(
                {
                    str(r.id)
                    for r in reviews
                    if not r.draft and str(r.id) not in considered_ids
                }
            )
            logger.info(
                "YOLO iteration: project=%s considered=%d/%d actions=%d",
                project.name,
                considered,
                non_draft_total,
                actions_fired,
            )
            self._yolo_coverage_history.append(
                CoverageRecord(
                    tick=tick,
                    project_id=project.id,
                    considered=considered,
                    total=non_draft_total,
                    actions=actions_fired,
                    missing_review_ids=missing_ids,
                )
            )

        # End-of-tick cleanup: drop tracked repo-config errors for any
        # PR that has disappeared from the per-tick reviews cache (PR
        # was merged, closed, or otherwise resolved).
        self._prune_stale_repo_config_errors(reviews_cache)
        # Watchdog: clear cached watchdog-task refs for PRs that are no
        # longer in the cache (PR closed/merged) so future recurrences
        # can re-file. Then run all detectors and file tasks / log
        # warnings as appropriate.
        self._prune_stale_watchdog_state(reviews_cache)
        self._run_yolo_watchdog(reviews_cache)

    def _handle_yolo_merge_failure(
        self,
        project,
        provider,
        slug: str,
        review_id,
        msg: str,
        *,
        operation: str,
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
                    operation,
                    project.name,
                    review_id,
                    msg,
                    fingerprint,
                )
            else:
                logger.debug(
                    "YOLO: %s still blocked on %s MR #%s by repo config (fingerprint=%s) — suppressing log",
                    operation,
                    project.name,
                    review_id,
                    fingerprint,
                )
            return

        # Anything else: clear any stale repo-config record for this PR
        # (the operator may have just fixed the toggle, and the next
        # error is a real conflict / transient issue).
        self._clear_repo_config_error(project.id, review_id_str)

        if kind == "conflict":
            logger.warning(
                "YOLO: %s failed for %s MR #%s: %s — dispatching conflict agent",
                operation,
                project.name,
                review_id,
                msg,
            )
            # Churn-magnet: detect and record conflicted files via merge-tree
            # for this PR (oompah-zlz_2-rxwe.1).  Fetch the review to get
            # the branch pair; record_conflicts_for_project handles the
            # merge-tree invocation.  Best-effort: a failure here never
            # blocks the task-notify path.
            _pid = project.id
            _rid = review_id_str
            _repo = project.repo_path
            _base = project.default_branch
            _head = ""  # resolved below
            try:
                _review = provider.get_review(slug, review_id)
                if _review:
                    _head = _review.source_branch or ""
            except Exception as _exc:
                logger.debug(
                    "Churn magnet: get_review failed for %s MR #%s: %s",
                    project.name,
                    review_id,
                    _exc,
                )
            if _head:
                try:
                    _store = _get_churn_store()
                    _files, _err = run_git_merge_tree(_repo, _base, _head)
                    if _files:
                        _store.record_conflicts(_pid, _files, _rid)
                        logger.info(
                            "Churn magnet: recorded %d conflicted file(s) for "
                            "%s MR #%s (base=%s head=%s)",
                            len(_files),
                            project.name,
                            review_id,
                            _base,
                            _head,
                        )
                    elif _err:
                        logger.debug(
                            "Churn magnet: merge-tree error for %s MR #%s: %s",
                            project.name,
                            review_id,
                            _err,
                        )
                except Exception as _exc:
                    logger.debug(
                        "Churn magnet: recording failed for %s MR #%s: %s",
                        project.name,
                        review_id,
                        _exc,
                    )
            self._yolo_notify_conflict(project, provider, slug, review_id)
            return

        # Transient: log a warning and let the next tick retry.
        # No agent dispatch — that would be wasteful for rate-limit /
        # network blips that resolve themselves.
        logger.warning(
            "YOLO: %s failed for %s MR #%s (transient): %s — will retry next tick",
            operation,
            project.name,
            review_id,
            msg,
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
        # Also prune orphan-recovery task bookkeeping (oompah-zlz_2-975).
        # Key shape is (project_id, review_id, kind); strip the kind to
        # check liveness against (project_id, review_id) pairs.
        stale_orphan = [
            k for k in self._yolo_orphan_recovery_tasks if (k[0], k[1]) not in live_keys
        ]
        for k in stale_orphan:
            self._yolo_orphan_recovery_tasks.pop(k, None)

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

        Also clears any cached watchdog-task reference for this
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
        """Drop watchdog-task cache entries for one (project, review).

        Called when an action on the PR succeeds — the PR has made
        progress, so any prior watchdog tasks were resolved (or will
        be) and a future recurrence should re-file freshly.
        """
        keys_to_drop = [
            k
            for k in self._yolo_watchdog_filed
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
            self._yolo_action_history,
            project_id,
            review_id,
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
                    project_id,
                    review_id,
                    run,
                )

    def _clear_already_mergeable_switch(self, project_id: str, review_id: str) -> None:
        """Clear D4 strategy-switch state on a successful action."""
        self._yolo_already_mergeable_switched.discard((project_id, review_id))

    def _prune_stale_watchdog_state(self, reviews_cache: dict) -> None:
        """Drop watchdog state for PRs that have left the cache.

        When a PR closes/merges and disappears from the cache:
        * Drop strategy-switch flags so future recurrences re-evaluate.
        * Drop filed-watchdog-task refs so future recurrences re-file.
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
            k for k in self._yolo_already_mergeable_switched if k not in live_pairs
        ]
        for k in stale_switches:
            self._yolo_already_mergeable_switched.discard(k)

        # Drop D1/D4 watchdog-task refs for PRs no longer in cache.
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
                r
                for r in self._yolo_action_history
                if (r.project_id, r.review_id) in live_pairs
            ]
            if len(kept) != len(self._yolo_action_history):
                self._yolo_action_history.clear()
                self._yolo_action_history.extend(kept)

    def _build_incoherent_prs_for_d3(self, reviews_cache: dict) -> list[dict]:
        """Build the D3 incoherent-PR list for the watchdog.

        For each PR in the cache:
        * If has_conflicts=True or ci_status=='failed', verify a matching
          recovery task exists. If we previously filed an orphan-
          recovery task AND that task is now closed AND the PR still
          shows the failing condition, the task-PR pair is incoherent.
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
                recovery_task_id = self._yolo_orphan_recovery_tasks.get(key)
                if not recovery_task_id:
                    # We haven't filed an orphan-recovery task — the
                    # standard YOLO path is responsible for handling
                    # this PR. D3 only fires when a recovery task WAS
                    # filed but is now closed without resolving.
                    continue
                # Check: is the orphan-recovery task still open?
                try:
                    issue = tracker.fetch_issue_detail(recovery_task_id)
                except Exception:  # noqa: BLE001
                    continue
                if not issue:
                    # Task disappeared entirely — reset the cache.
                    self._yolo_orphan_recovery_tasks.pop(key, None)
                    incoherent.append(
                        {
                            "project_id": project.id,
                            "review_id": review_id,
                            "kind": kind,
                            "source_branch": source_branch,
                            "reason": (
                                f"recovery task {recovery_task_id} no longer exists; "
                                "PR still in failing state"
                            ),
                        }
                    )
                    continue
                if _is_terminal_state(issue.state, self.config.tracker_terminal_states):
                    # Task closed but PR still failing — reset cache so
                    # the next tick refiles a fresh recovery task.
                    self._yolo_orphan_recovery_tasks.pop(key, None)
                    incoherent.append(
                        {
                            "project_id": project.id,
                            "review_id": review_id,
                            "kind": kind,
                            "source_branch": source_branch,
                            "reason": (
                                f"recovery task {recovery_task_id} is closed (state={issue.state}) "
                                f"but PR still has {kind} condition"
                            ),
                        }
                    )
        return incoherent

    def _run_yolo_watchdog(self, reviews_cache: dict) -> None:
        """Run all detectors and file tasks / log warnings."""
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
                            pattern.title,
                            pattern.body,
                        )
                continue

            # P0 task-filing patterns (D1, D3, D4).
            if pattern.pattern_key in self._yolo_watchdog_filed:
                # Already filed for this pattern. Idempotent skip.
                continue
            try:
                self._file_watchdog_task(pattern)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "YOLO watchdog: failed to file task for %s: %s",
                    pattern.pattern_key,
                    exc,
                )

        # Clear D2-warned flags for projects that didn't hit this tick —
        # i.e. the starvation has resolved. A future recurrence will re-warn.
        d2_keys_to_drop = [
            k
            for k in self._yolo_watchdog_d2_warned
            if k.startswith("d2:") and k not in {f"d2:{p}" for p in d2_hit_projects}
        ]
        for k in d2_keys_to_drop:
            self._yolo_watchdog_d2_warned.discard(k)

    def _file_watchdog_task(self, pattern: WatchdogPattern) -> None:
        """File a P0 task for a watchdog pattern and stamp the idempotency cache."""
        try:
            tracker = self._tracker_for_project(pattern.project_id)
        except ProjectError as exc:
            logger.warning(
                "YOLO watchdog: cannot get tracker for %s: %s",
                pattern.project_id,
                exc,
            )
            return
        labels = list(pattern.labels)
        new_issue = tracker.create_issue(
            title=pattern.title,
            issue_type="task",
            description=pattern.body,
            priority=0,
            labels=labels,
            initial_status=OPEN,
        )
        self._yolo_watchdog_filed[pattern.pattern_key] = new_issue.identifier
        # Log at WARNING (not ERROR): filing a P0 escalation task is the
        # watchdog's *expected* notification path for stuck PRs — it's
        # not an oompah-internal failure. Logging at ERROR would cause
        # error_watcher's _TaskLoggingHandler to auto-file a duplicate
        # meta-task in the oompah project, dirtying the queue with
        # notifications that already have their own task in the target
        # project (oompah-zlz_2-8vc).
        logger.warning(
            "YOLO watchdog: filed P0 task %s for pattern %s "
            "(project=%s review=%s detector=%s)",
            new_issue.identifier,
            pattern.pattern_key,
            pattern.project_id,
            pattern.review_id,
            pattern.detector,
        )

    def _file_orphan_recovery_task(
        self,
        project,
        tracker,
        review_id: str,
        source_branch: str,
        kind: str,
    ) -> None:
        """File a recovery task for a PR whose branch matches no task.

        Used by ``_yolo_notify_conflict`` and ``_yolo_retry_ci`` when
        ``fetch_issue_detail(source_branch)`` returns ``None``. Without
        this, an orphan PR (branch with no attaching task) would sit
        DIRTY/FAILED forever because the YOLO escalation has nothing to
        relabel/reopen. The task's identifier won't match the branch —
        that's fine: it's the work item, not the branch source. The
        focus matcher routes via the label.

        ``kind`` is one of ``"merge-conflict"`` or ``"ci-fix"`` and
        controls the title/description/label. Idempotent: the
        ``(project_id, review_id, kind)`` tuple is tracked in
        ``self._yolo_orphan_recovery_tasks`` so a second YOLO fire on
        the same orphan PR will not file a duplicate.
        (oompah-zlz_2-975)
        """
        if kind not in ("merge-conflict", "ci-fix"):
            logger.error("Unknown orphan recovery task kind: %s", kind)
            return
        key = (project.id, str(review_id), kind)
        if key in self._yolo_orphan_recovery_tasks:
            logger.debug(
                "YOLO: orphan recovery task already filed for %s MR #%s (%s): %s",
                project.name,
                review_id,
                kind,
                self._yolo_orphan_recovery_tasks[key],
            )
            return
        status = NEEDS_REBASE if kind == "merge-conflict" else NEEDS_CI_FIX
        label = "merge-conflict" if kind == "merge-conflict" else "ci-fix"
        # Cross-restart safety net: query the tracker for existing open
        # tasks with the matching label. The in-memory dict above is the
        # fast path, but it's wiped on every restart. Without this check,
        # a process restart creates a fresh task even though an open
        # duplicate already exists in the tracker.
        try:
            active_states = (
                _dispatch_active_state_names(self.config.tracker_active_states)
                + [status]
            )
            existing = tracker.fetch_issues_by_labels([label], states=active_states)
            if not existing:
                existing = tracker.fetch_issues_by_states([status])
            if existing:
                # Reuse the first matching open issue with this label instead
                # of creating a new one. This prevents the "dozens of merge
                # conflict on PR #2" duplicates seen after restarts.
                oldest = min(existing, key=lambda i: i.created_at or "")
                logger.info(
                    "YOLO: reusing existing open recovery task %s for %s MR #%s (%s) "
                    "instead of filing a duplicate",
                    oldest.identifier,
                    project.name,
                    review_id,
                    kind,
                )
                self._yolo_orphan_recovery_tasks[key] = oldest.identifier
                return
        except Exception as exc:
            logger.debug(
                "YOLO: cross-restart dup check failed for %s MR #%s: %s",
                project.name,
                review_id,
                exc,
            )
        if kind == "merge-conflict":
            title = f"merge conflict on PR #{review_id} ({source_branch})"
            description = (
                f"YOLO: conflict detected on MR #{review_id} "
                f"(branch {source_branch}) but no task matches the "
                f"branch name. This task is the manual recovery — "
                f"work directly on the branch. Rebase the branch onto "
                f"the target and resolve conflicts."
            )
            label = "merge-conflict"
        else:  # ci-fix
            title = f"fix CI on PR #{review_id} ({source_branch})"
            description = (
                f"YOLO: CI failure detected on MR #{review_id} "
                f"(branch {source_branch}) but no task matches the "
                f"branch name. This task is the manual recovery — "
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
                initial_status=status,
            )
        except Exception as exc:
            logger.warning(
                "YOLO: failed to file orphan recovery task for %s MR #%s (%s): %s",
                project.name,
                review_id,
                kind,
                exc,
            )
            return
        try:
            tracker.add_label(new_issue.identifier, label)
        except Exception as exc:
            logger.warning(
                "YOLO: filed orphan recovery task %s but failed to add %s label: %s",
                new_issue.identifier,
                label,
                exc,
            )
        self._yolo_orphan_recovery_tasks[key] = new_issue.identifier
        logger.info(
            "YOLO: filed orphan recovery task %s for %s MR #%s (%s, branch %s)",
            new_issue.identifier,
            project.name,
            review_id,
            kind,
            source_branch,
        )

    def _build_branch_index(
        self, project_id: str, tracker
    ) -> dict[str, str]:
        """Build a ``{work_branch: identifier}`` index for *project_id*.

        Fetches all open/in-review issues from *tracker* and collects those
        that carry a ``work_branch`` value in their metadata.  The resulting
        dict is cached in ``self._branch_indexes[project_id]`` and is
        invalidated by ``_invalidate_tracker_read_caches()`` at each tick.

        Returns an empty dict if the tracker call fails or no issues have
        ``work_branch`` set.
        """
        try:
            states = (
                _dispatch_active_state_names(self.config.tracker_active_states)
                + [IN_REVIEW]
            )
            issues = tracker.fetch_issues_by_states(states)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Branch index build failed for project %s: %s", project_id, exc
            )
            return {}
        index: dict[str, str] = {}
        for issue in issues:
            branch = getattr(issue, "work_branch", None)
            if branch:
                index[str(branch)] = issue.identifier
        return index

    def _resolve_task_for_branch(
        self, tracker, source_branch: str, *, project_id: str | None = None
    ):
        """Resolve a PR's source branch back to its tracker task.

        For **GitHub-backed tasks** the branch name is a generated slug like
        ``oompah/<project>/<gh-N>`` that does not equal the task identifier.
        When *project_id* is supplied this method first consults the per-project
        branch-to-issue index — a ``{work_branch: identifier}`` mapping built
        from open/in-review issues — before falling back to the legacy path.

        For native tasks, branches are named after the task identifier, so the
        direct ``fetch_issue_detail`` lookup still works as a fallback.

        Epic→main PRs use an ``epic-<identifier>`` branch (see
        ``ProjectStore.epic_branch_name``); the ``epic-`` prefix is stripped in
        both the index lookup and the legacy path so an epic PR's CI failure or
        merge conflict reopens the EPIC task rather than being treated as an
        orphan PR.
        """
        # --- GitHub-backed path: consult the per-project branch index first ---
        if project_id is not None:
            if project_id not in self._branch_indexes:
                self._branch_indexes[project_id] = self._build_branch_index(
                    project_id, tracker
                )
            branch_index = self._branch_indexes[project_id]

            # Try verbatim, then with epic- prefix stripped.
            lookup_key = source_branch
            if lookup_key not in branch_index and source_branch.startswith("epic-"):
                lookup_key = source_branch[len("epic-"):]

            if lookup_key in branch_index:
                identifier = branch_index[lookup_key]
                issue = tracker.fetch_issue_detail(identifier)
                if issue is not None:
                    return issue

        # --- Native fallback path: branch name == identifier ---
        issue = tracker.fetch_issue_detail(source_branch)
        if issue is None and source_branch.startswith("epic-"):
            issue = tracker.fetch_issue_detail(source_branch[len("epic-"):])
        return issue

    def _yolo_epic_strategy_block_reason(
        self,
        project: Project,
        tracker: TrackerProtocol,
        review: ReviewRequest,
    ) -> str | None:
        """Return a reason when YOLO must not act on this review.

        Children of a shared epic commit to the epic branch, not individual
        per-child PRs.  YOLO is the last gate before a merge, so it blocks
        per-child task PRs that violate the shared workflow.
        """
        source_branch = (getattr(review, "source_branch", "") or "").strip()
        if not source_branch:
            return None

        try:
            issue = self._resolve_task_for_branch(
                tracker, source_branch, project_id=project.id
            )
        except Exception as exc:  # noqa: BLE001 - do not break unrelated PRs
            logger.debug(
                "YOLO epic gate could not resolve branch %s on %s: %s",
                source_branch,
                project.name,
                exc,
            )
            return None
        if issue is None:
            return None
        if self._issue_requires_parent_epic(issue, project.id):
            target_branch = self._review_target_branch(project, review)
            return (
                f"project requires epic-owned tasks: {issue.identifier} has no "
                f"parent epic, so PR {source_branch}->{target_branch} cannot "
                "be merged as standalone task work"
            )
        if not (issue.parent_id or "").strip():
            return None

        try:
            issue_epic_branch = self._epic_branch_for_issue(issue)
        except Exception:  # noqa: BLE001
            issue_epic_branch = ""
        if source_branch == issue_epic_branch:
            # This is an epic rollup PR (including nested epics), not a
            # per-child task PR. The epic landing gate owns its creation.
            return None

        parent_epic = self._resolve_parent_epic(issue)
        if parent_epic is None:
            return None

        target_branch = self._review_target_branch(project, review)
        parent_epic_branch = self._epic_branch_for_issue(parent_epic)

        return (
            f"shared epic workflow: child task {issue.identifier} must land "
            f"via {parent_epic_branch}, not per-child PR "
            f"{source_branch}->{target_branch}"
        )

    def _close_invalid_epic_policy_review(
        self,
        project: Project,
        provider: Any,
        slug: str,
        tracker: TrackerProtocol,
        review: ReviewRequest,
        reason: str,
        *,
        tick: int,
    ) -> bool:
        """Close stale task PRs forbidden by epic-owned policy.

        ``_yolo_epic_strategy_block_reason`` intentionally blocks every
        epic-strategy violation. This helper closes violations that can never
        be valid under the current policy, so leaving them open would only let
        YOLO reprocess the same terminal violation:

        * top-level non-epic task PRs when ``require_epic_for_tasks`` is set
        * child task PRs in ``epic_strategy=shared`` projects, where work must
          land through the parent epic branch instead
        """
        source_branch = (getattr(review, "source_branch", "") or "").strip()
        if not source_branch:
            return False
        try:
            issue = self._resolve_task_for_branch(
                tracker, source_branch, project_id=project.id
            )
        except Exception as exc:  # noqa: BLE001 - fall back to gate-only behavior
            logger.debug(
                "YOLO epic-policy close could not resolve branch %s on %s: %s",
                source_branch,
                project.name,
                exc,
            )
            return False

        close_comment = ""
        task_comment_prefix = ""
        needs_human_tail = ""

        if self._issue_requires_parent_epic(issue, project.id):
            close_comment = (
                "Closing stale standalone task PR. This project requires "
                "epic-owned implementation work, so task work must land through "
                "an epic rollup PR instead of a direct task PR.\n\n"
                f"{reason}"
            )
            task_comment_prefix = (
                "Closed stale standalone PR #{review_id} because this project "
                "requires epic-owned implementation work. "
            )
            needs_human_tail = (
                " The task was moved to Needs Human so it can be attached "
                "to an epic or intentionally exempted."
            )
        elif (
            issue is not None
            and (issue.parent_id or "").strip()
        ):
            parent_epic = self._resolve_parent_epic(issue)
            if parent_epic is not None:
                try:
                    issue_epic_branch = self._epic_branch_for_issue(issue)
                except Exception:  # noqa: BLE001 - branch mismatch is enough
                    issue_epic_branch = ""
                if source_branch != issue_epic_branch:
                    parent_epic_branch = self._epic_branch_for_issue(parent_epic)
                    close_comment = (
                        "Closing stale child task PR. This project uses shared "
                        "epic branches, so child task work must land through "
                        f"the parent epic rollup PR from {parent_epic_branch} "
                        "instead of a direct task PR.\n\n"
                        f"{reason}"
                    )
                    task_comment_prefix = (
                        "Closed stale child PR #{review_id} because this "
                        "project uses shared epic branches. "
                    )
                    needs_human_tail = (
                        " The task was moved to Needs Human so the work can "
                        "be moved to the shared epic branch or the stale PR "
                        "can be inspected."
                    )

        if not close_comment:
            return False

        review_id = str(review.id)
        try:
            success, msg = provider.close_review(
                slug,
                review_id,
                comment=close_comment,
            )
        except Exception as exc:  # noqa: BLE001 - provider failures are retryable
            success, msg = False, str(exc)

        if not success:
            logger.warning(
                "YOLO GATE: failed to close invalid standalone %s MR #%s — %s",
                project.name,
                review_id,
                msg,
            )
            self._record_yolo_action(
                project.id,
                review_id,
                "close_invalid_review",
                "failure",
                msg or reason,
                tick=tick,
            )
            return True

        logger.warning(
            "YOLO GATE: closed invalid standalone %s MR #%s — %s",
            project.name,
            review_id,
            reason,
        )
        self._record_yolo_action(
            project.id,
            review_id,
            "close_invalid_review",
            "success",
            reason,
            tick=tick,
        )
        self._reconcile_closed_standalone_epic_policy_task(
            tracker,
            issue,
            review_id,
            reason,
            task_comment_prefix,
            needs_human_tail,
        )
        return True

    def _reconcile_closed_standalone_epic_policy_task(
        self,
        tracker: TrackerProtocol,
        issue: Issue | None,
        review_id: str,
        reason: str,
        task_comment_prefix: str,
        needs_human_tail: str,
    ) -> None:
        if issue is None:
            return
        current_status = canonicalize_status(issue.state)
        comment = task_comment_prefix.format(review_id=review_id) + reason
        try:
            if current_status == IN_REVIEW:
                tracker.update_issue(issue.identifier, status=NEEDS_HUMAN)
                tracker.add_comment(
                    issue.identifier,
                    comment + needs_human_tail,
                    author="oompah",
                )
            elif current_status == DONE:
                tracker.add_comment(
                    issue.identifier,
                    comment + " The task remains Done.",
                    author="oompah",
                )
            else:
                tracker.add_comment(
                    issue.identifier,
                    comment
                    + f" The task remains in {issue.state or current_status}.",
                    author="oompah",
                )
        except Exception as exc:  # noqa: BLE001 - review closure already succeeded
            logger.debug(
                "Failed to reconcile task %s after closing invalid PR #%s: %s",
                issue.identifier,
                review_id,
                exc,
            )

    def _yolo_notify_conflict(
        self, project, provider, slug: str, review_id: str
    ) -> None:
        """Notify the task about a merge conflict (YOLO mode).

        Before falling through to the task-notification path, attempt a
        provider-level rebase. GitHub frequently marks a PR ``mergeable=CONFLICTING``
        when the branch is merely out-of-date — the underlying patches don't
        actually overlap. In that case ``provider.rebase_review`` succeeds and
        clears ``has_conflicts`` on the next review fetch, so no agent work is
        needed. Only when the rebase truly fails with conflict markers (or for
        unrelated transport/auth reasons) do we fall through to today's
        notify-task behavior. See oompah-zlz_2-s56w.
        """
        # Normalise once — used in both churn-recording and the info block.
        review_id_str = str(review_id)
        # Step 1: try a provider-level rebase before disturbing the task.
        try:
            success, message = provider.rebase_review(slug, review_id)
            if success:
                logger.info(
                    "YOLO: rebased %s MR #%s clean (no conflict)",
                    slug,
                    review_id,
                )
                return
            msg_lower = (message or "").lower()
            if "conflict" not in msg_lower:
                # Network/auth/etc — preserve today's safety net by
                # falling through to notify the task, but log so an
                # operator can see why YOLO didn't get the cheap path.
                logger.warning(
                    "YOLO: provider rebase failed for %s MR #%s (non-conflict): %s",
                    slug,
                    review_id,
                    message,
                )
            # else: real merge conflict — fall through to task-notify below.
        except Exception as exc:
            logger.warning(
                "YOLO: provider rebase raised for %s MR #%s: %s",
                slug,
                review_id,
                exc,
            )
            # Fall through to task-notify (safety net).

        try:
            review = provider.get_review(slug, review_id)
            if not review:
                return
            source_branch = review.source_branch
            target_branch = review.target_branch
            if not source_branch:
                return

            # Record conflicted files for churn-magnet analysis (oompah-zlz_2-rxwe.1).
            # run_git_merge_tree uses git merge-base + merge-tree to identify
            # actual conflicting file paths.
            _base_branch = target_branch or project.default_branch
            try:
                churn_files, churn_err = run_git_merge_tree(
                    project.repo_path, _base_branch, source_branch
                )
                if churn_files:
                    _get_churn_store().record_conflicts(
                        project.id,
                        churn_files,
                        review_id_str,
                    )
                    logger.info(
                        "Churn magnet: recorded %d conflicted file(s) for %s MR #%s "
                        "(base=%s head=%s): %s",
                        len(churn_files),
                        project.name,
                        review_id,
                        _base_branch,
                        source_branch,
                        ", ".join(churn_files[:5]) + (" ..." if len(churn_files) > 5 else ""),
                    )
                elif churn_err:
                    logger.debug(
                        "Churn magnet: merge-tree failed for %s MR #%s: %s",
                        project.name,
                        review_id,
                        churn_err,
                    )
            except Exception as _exc:
                logger.debug(
                    "Churn magnet: recording raised for %s MR #%s: %s",
                    project.name,
                    review_id,
                    _exc,
                )

            tracker = self._tracker_for_project(project.id)
            issue = self._resolve_task_for_branch(
                tracker, source_branch, project_id=project.id
            )
            if not issue:
                # Orphan branch: no task matches (not even the epic the
                # branch belongs to). File a recovery task so the YOLO
                # escalation chain isn't a silent dead-end. (oompah-zlz_2-975)
                self._file_orphan_recovery_task(
                    project,
                    tracker,
                    str(review_id),
                    source_branch,
                    kind="merge-conflict",
                )
                return

            # Shared/stacked EPIC branches: once every child is complete, the
            # epic PR itself is the repair unit. Mark the epic Needs Rebase so
            # an agent runs directly on the epic branch. Before that point,
            # keep the legacy helper-task fallback because the parent is still
            # just a rollup over unfinished child work.
            #
            # Idempotency has two layers: (1) an existing actionable rebase
            # sibling means one is in flight; (2) a per-epic cooldown stops
            # re-filing during the window AFTER a rebase task completes but
            # BEFORE the forge recomputes the PR's mergeability — otherwise the
            # sibling goes terminal, the check sees "nothing active", and a
            # duplicate is filed every tick until the conflict clears.
            children = self._fetch_epic_children(issue)
            if self._is_mature_epic_review_issue(issue, children):
                self._mark_epic_review_repair_issue(
                    tracker,
                    issue,
                    status=NEEDS_REBASE,
                    label="merge-conflict",
                    source_branch=source_branch,
                    target_branch=target_branch or project.default_branch,
                    review_id=review_id_str,
                    review_url=getattr(review, "url", None),
                    comment=(
                        f"YOLO: Merge conflict detected on MR #{review_id}. "
                        f"Rebase `{source_branch}` onto {target_branch} and "
                        "resolve conflicts."
                    ),
                )
                self._set_epic_rebase_state(
                    issue.identifier,
                    EpicRebaseState.REBASING,
                    project_id=project.id,
                )
                self._epic_rebase_filed_at[issue.identifier] = time.monotonic()
                logger.info(
                    "YOLO: marked mature epic %s as P0 Needs Rebase "
                    "(MR #%s branch conflict)",
                    issue.identifier,
                    review_id,
                )
                return

            if self._is_epic_rollup_parent(issue, children):
                # Force a fresh read so the idempotency check below sees a
                # rebase sibling we filed on a previous tick (the per-tick read
                # cache would otherwise miss it and we'd re-file every tick).
                try:
                    tracker.invalidate_read_cache()
                except Exception:  # noqa: BLE001
                    pass
                existing = self._find_active_epic_rebase_sibling(
                    tracker,
                    issue,
                )
                if existing is not None:
                    # Rebase agent already queued/in flight — let it finish.
                    self.state.completed.discard(existing.id)
                    self._set_epic_rebase_state(
                        issue.identifier,
                        EpicRebaseState.REBASING,
                        project_id=project.id,
                    )
                    self._epic_rebase_filed_at[issue.identifier] = time.monotonic()
                    return
                last_filed = self._epic_rebase_filed_at.get(issue.identifier, float("-inf"))
                if time.monotonic() - last_filed < _EPIC_REBASE_REFILE_COOLDOWN_S:
                    # Recently filed a rebase task; the PR conflict is likely
                    # still settling after the rebase force-push. Don't pile on.
                    return
                self._file_rebase_task(
                    tracker,
                    issue,
                    source_branch,
                    target_branch or project.default_branch,
                )
                self._set_epic_rebase_state(
                    issue.identifier,
                    EpicRebaseState.REBASING,
                    project_id=project.id,
                )
                self._epic_rebase_filed_at[issue.identifier] = time.monotonic()
                self.state.completed.discard(issue.id)
                logger.info(
                    "YOLO: filed P0 rebase task for epic %s (MR #%s branch "
                    "conflict) — child work is not complete enough to dispatch "
                    "the parent directly",
                    issue.identifier,
                    review_id,
                )
                return

            # Don't re-notify if already open/in_progress with merge-conflict label,
            # but ensure we clear the completed set so it can be re-dispatched.
            state_lower = _state_key(issue.state)
            if (
                state_lower in {_state_key(OPEN), _state_key(IN_PROGRESS), _state_key(NEEDS_REBASE)}
                and "merge-conflict" in issue.labels
            ):
                self.state.completed.discard(issue.id)
                return
            comment_text = (
                f"YOLO: Merge conflict detected on MR #{review_id}. "
                f"Rebase onto {target_branch} and resolve conflicts."
            )
            tracker.add_comment(issue.identifier, comment_text, author="oompah")
            terminal = {_state_key(s) for s in self.config.tracker_terminal_states}
            if state_lower in terminal:
                tracker.update_issue(
                    issue.identifier,
                    status=NEEDS_REBASE,
                    priority="0",
                    **{"add-label": "merge-conflict"},
                )
                self.state.completed.discard(issue.id)
                logger.info(
                    "YOLO: reopened %s as P0 for conflict resolution", issue.identifier
                )
            else:
                # Issue is in a non-terminal, non-actionable state (e.g.
                # "deferred", "wont_fix").  Reopen as P0 so the
                # conflict-resolution agent can be dispatched.
                tracker.update_issue(
                    issue.identifier,
                    status=NEEDS_REBASE,
                    priority="0",
                    **{"add-label": "merge-conflict"},
                )
                logger.info(
                "YOLO: reopened %s from %r to P0 Needs Rebase for conflict resolution",
                    issue.identifier,
                    state_lower,
                )
        except Exception as exc:
            logger.warning(
                "YOLO: conflict notification failed for MR #%s: %s", review_id, exc
            )

    def _clear_merge_conflict_label_for_branch(
        self,
        project,
        tracker,
        source_branch: str,
    ) -> None:
        """Remove the merge-conflict label from a task if it is stale.

        Called from two contexts (oompah-zlz_2-683l):

        1. **Successful YOLO merge / enqueue** — when GitHub has accepted a
           merge the PR is by definition conflict-free. Clear the label
           asynchronously so a future tick that re-notices the branch name
           (e.g. after the PR disappears from the open-reviews list) does
           not re-label a resolved conflict.

        2. **External conflict-resolution check** — each YOLO tick loop
           iteration ends with a ``has_conflicts=False`` guard. If a PR
           previously had ``merge-conflict`` label but GitHub now reports
           ``has_conflicts=False`` the label is stale (someone rebased the
           branch without going through the YOLO agent path). Clear it.

        The removal is safe to re-issue idempotently; ``remove-label`` is a
        no-op when the label is absent.
        """
        if not source_branch:
            return
        project_id: str | None = getattr(project, "id", None)
        try:
            issue = self._resolve_task_for_branch(
                tracker, source_branch, project_id=project_id
            )
            if not issue:
                return
            labels = {l.lower() for l in (issue.labels or [])}
            if "merge-conflict" not in labels:
                return
            tracker.update_issue(issue.identifier, **{"remove-label": "merge-conflict"})
            # Update in-memory state so the completed-set is consistent.
            if issue.id:
                self.state.completed.discard(issue.id)
            logger.info(
                "Cleared stale merge-conflict label from %s "
                "(PR #%s branch=%s, GitHub reports no conflicts)",
                issue.identifier,
                getattr(issue, "id", "?"),
                source_branch,
            )
        except Exception as exc:
            logger.debug(
                "_clear_merge_conflict_label_for_branch failed for %s: %s",
                source_branch,
                exc,
            )

    def _yolo_comment_enqueued(
        self, tracker, project, review, review_id: str
    ) -> None:
        """Post a comment on a task when YOLO enqueues its PR.

        Best-effort: any failure is logged at DEBUG level so it never blocks
        the main YOLO loop.
        """
        try:
            source_branch = getattr(review, "source_branch", "") or ""
            if not source_branch:
                return
            issue = self._resolve_task_for_branch(
                tracker, source_branch, project_id=project.id
            )
            if not issue:
                return
            tracker.add_comment(
                issue.identifier,
                f"YOLO: PR #{review_id} enqueued for merge.",
                author="oompah",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "YOLO: enqueue comment failed for %s MR #%s: %s",
                project.name,
                review_id,
                exc,
            )

    def _yolo_mark_task_merged(
        self, tracker, project, review, review_id: str
    ) -> None:
        """Mark a task Merged and comment when YOLO directly merges its PR.

        Best-effort: any failure is logged at DEBUG level so it never
        blocks the main YOLO loop.
        """
        try:
            source_branch = getattr(review, "source_branch", "") or ""
            if not source_branch:
                return
            issue = self._resolve_task_for_branch(
                tracker, source_branch, project_id=project.id
            )
            if not issue:
                return
            if canonicalize_status(issue.state) != MERGED:
                tracker.update_issue(issue.identifier, status=MERGED)
                self.state.completed.discard(issue.id)
            tracker.add_comment(
                issue.identifier,
                f"YOLO: merged PR #{review_id}.",
                author="oompah",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "YOLO: merged update failed for %s MR #%s: %s",
                project.name,
                review_id,
                exc,
            )

    def _yolo_retry_ci(self, project, review) -> None:
        """Re-file a ticket to fix failed CI tests (YOLO mode)."""
        try:
            source_branch = review.source_branch
            if not source_branch:
                return
            tracker = self._tracker_for_project(project.id)
            issue = self._resolve_task_for_branch(
                tracker, source_branch, project_id=project.id
            )
            if not issue:
                # Orphan branch: no task matches (not even the epic the
                # branch belongs to). File a recovery task so the YOLO
                # escalation chain isn't a silent dead-end. (oompah-zlz_2-975)
                self._file_orphan_recovery_task(
                    project,
                    tracker,
                    str(review.id),
                    source_branch,
                    kind="ci-fix",
                )
                return
            # If the matched parent has children, choose the repair unit based
            # on maturity. Once every child is review-ready/terminal, the epic
            # PR itself is the dispatchable unit and the agent should fix that
            # branch. Before that point, keep the legacy helper-task fallback
            # because the parent is still a rollup over unfinished child work.
            #
            # IMPORTANT: this check runs BEFORE the
            # already-labeled-ci-fix early-exit below. Without that
            # ordering, a parent-with-children that was relabeled ci-fix
            # in a previous YOLO cycle (legacy state, or operator
            # action) would short-circuit forever and never produce a
            # sibling task — which is exactly the bug
            # oompah-zlz_2-cd5 fixes.
            children = self._fetch_epic_children(issue)
            if children:
                if self._is_mature_epic_review_issue(issue, children):
                    self._mark_epic_review_repair_issue(
                        tracker,
                        issue,
                        status=NEEDS_CI_FIX,
                        label="ci-fix",
                        source_branch=source_branch,
                        target_branch=getattr(review, "target_branch", None)
                        or project.default_branch,
                        review_id=str(getattr(review, "id", "") or ""),
                        review_url=getattr(review, "url", None),
                        comment=(
                            f"YOLO: CI tests failed on MR #{review.id}. "
                            "Fix the failing tests so this MR can merge. "
                            "Do NOT rewrite the feature — only fix test failures. "
                            "IMPORTANT: Paths in CI logs are not trustworthy. "
                            "Run tests locally to get accurate paths and errors."
                        ),
                    )
                    logger.info(
                        "YOLO: marked mature epic %s as P0 ci-fix for MR #%s",
                        issue.identifier,
                        review.id,
                    )
                    return

                sibling_title = f"CI fix: PR #{review.id} on branch {source_branch}"

                def _is_ci_fix_sibling(child: Issue) -> bool:
                    state_key = _state_key(child.state)
                    if state_key not in {
                        _state_key(OPEN),
                        _state_key(IN_PROGRESS),
                        _state_key(NEEDS_CI_FIX),
                    }:
                        return False
                    labels = {str(label) for label in (child.labels or [])}
                    title = str(child.title or "").strip()
                    return (
                        "ci-fix" in labels
                        or canonicalize_status(child.state) == NEEDS_CI_FIX
                        or title == sibling_title
                    )

                # Idempotency: if there's already an OPEN/IN_PROGRESS
                # ci-fix sibling under this parent, a fix is already in
                # flight — don't file a duplicate. CLOSED siblings
                # from previous attempts don't count (treat as
                # finished and file a new one).
                existing_sibling = next(
                    (c for c in children if _is_ci_fix_sibling(c)),
                    None,
                )
                if existing_sibling is not None:
                    logger.debug(
                        "YOLO: ci-fix sibling %s already open under "
                        "%s — skipping duplicate",
                        existing_sibling.identifier,
                        issue.identifier,
                    )
                    return
                sibling_description = (
                    f"YOLO: CI tests failed on MR #{review.id} "
                    f"(branch {source_branch}). The branch's primary "
                    f"task {issue.identifier} (type={issue.issue_type}) "
                    f"has {len(children)} children and won't be "
                    f"dispatched. This sibling task carries the actual "
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
                    parent=issue.identifier,
                    initial_status=NEEDS_CI_FIX,
                    labels=["ci-fix"],
                )
                logger.info(
                    "YOLO: filed sibling ci-fix task %s under %s "
                    "(type=%s, %d children) for MR #%s",
                    sibling.identifier,
                    issue.identifier,
                    issue.issue_type,
                    len(children),
                    review.id,
                )
                return
            # Childless task path (any issue_type): keep the existing
            # relabel-or-skip behavior. The early-exit below is the
            # original idempotency guard — for tasks with no children,
            # a ci-fix label genuinely means "a fix is already in
            # flight" because the task itself can be dispatched.
            state_lower = _state_key(issue.state)
            if state_lower in {_state_key(OPEN), _state_key(IN_PROGRESS), _state_key(NEEDS_CI_FIX)} and (
                "ci-fix" in issue.labels or canonicalize_status(issue.state) == NEEDS_CI_FIX
            ):
                return
            tracker.update_issue(
                issue.identifier,
                status=NEEDS_CI_FIX,
                priority="0",
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
            logger.warning(
                "YOLO: CI retry failed for branch %s: %s", review.source_branch, exc
            )

    def _resolve_blocker_state(self, blocker: BlockerRef, issue: Issue) -> str:
        """Look up a blocker's current state, using a per-tick cache."""
        cache = getattr(self, "_blocker_state_cache", {})
        bid = blocker.identifier or blocker.id or ""
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

    def _apply_duplicate_detection(self, candidates: list[Issue]) -> list[Issue]:
        """Run similarity-based duplicate detection on candidates (runs in thread pool).

        For each candidate issue, scans against the project's open+closed issue pool.
        When a high-similarity match (score >= _MIN_SCORE_TO_FLAG) is found:

        * If the matching issue is OPEN → adds ``duplicate-candidate`` label and posts
          a comment linking to the existing issue, so `_should_dispatch` will reject it.
        * If the matching issue is CLOSED → adds ``needs:duplicate_detector`` label so
          the ``duplicate_detector`` focus will be selected for agent investigation.

        Also updates the in-memory candidate's ``labels`` list so that subsequent
        checks in this tick (like ``_should_dispatch``) see the new labels without
        a re-fetch.

        Returns the (possibly modified) candidates list.

        Designed to run in the tick thread pool (called from ``_handle_dispatch_needed``
        via ``run_in_executor``).
        """
        if not candidates:
            return []

        sorted_all_candidates = self._sort_for_dispatch(candidates)
        sorted_candidates = [
            issue
            for issue in sorted_all_candidates
            if canonicalize_status(issue.state) != PROPOSED
        ]
        prework_count = len(sorted_all_candidates) - len(sorted_candidates)
        limit = getattr(self.config, "duplicate_detection_candidate_limit", 64)
        if limit > 0:
            detection_candidates = sorted_candidates[:limit]
        else:
            detection_candidates = sorted_candidates
        deferred_count = max(len(sorted_candidates) - len(detection_candidates), 0)
        if deferred_count:
            logger.debug(
                "Duplicate detection deferred %d candidate(s) after limit=%d",
                deferred_count,
                limit,
            )

        projects = self.project_store.list_all()
        project_by_id: dict[str, Project] = {p.id: p for p in projects}

        # Group candidates by project so we can batch queries
        by_project: dict[str | None, list[Issue]] = {}
        for c in detection_candidates:
            by_project.setdefault(c.project_id, []).append(c)

        for project_id, proj_candidates in by_project.items():
            tracker = self._tracker_for_project(project_id) if project_id else self.tracker
            try:
                # Fetch the full issue pool for this project (open + closed for comparison)
                all_pool = tracker.fetch_issues_by_states(
                    _dispatch_active_state_names(self.config.tracker_active_states)
                    + list(self.config.tracker_terminal_states)
                )
            except Exception:
                logger.debug("Failed to fetch issue pool for duplicate detection on %s", project_id)
                continue

            for candidate in proj_candidates:
                try:
                    similar = find_similar_issues(candidate, all_pool, min_score=_MIN_SCORE_TO_FLAG)
                except Exception as exc:
                    logger.debug("Duplicate detection raised for %s: %s", candidate.identifier, exc)
                    continue

                for match_issue, score in similar:
                    if not _is_terminal_state(
                        match_issue.state, self.config.tracker_terminal_states
                    ):
                        # Match is OPEN — reject candidate as duplicate of existing open issue
                        if "duplicate-candidate" not in (candidate.labels or []):
                            try:
                                tracker.update_issue(
                                    candidate.identifier,
                                    status=DUPLICATE_CANDIDATE,
                                )
                                # Update in-memory candidate so subsequent checks in this
                                # tick (_should_dispatch) see the new label without a re-fetch.
                                if candidate.labels is None:
                                    candidate.labels = []
                                candidate.state = DUPLICATE_CANDIDATE
                                self._post_comment(
                                    candidate.identifier,
                                    f"Potential duplicate detected (similarity={score:.2f}): "
                                    f"this issue appears similar to existing open issue "
                                    f"{match_issue.identifier}.\n"
                                    f"See {match_issue.identifier} for existing work.",
                                    project_id=project_id,
                                )
                                logger.info(
                                    "Duplicate detection: flagged %s as duplicate-candidate "
                                    "(score=%.2f, matches %s)",
                                    candidate.identifier, score, match_issue.identifier,
                                )
                            except Exception as exc:
                                logger.debug(
                                    "Failed to label/comment duplicate candidate %s: %s",
                                    candidate.identifier, exc,
                                )
                        break  # only flag the highest-scoring match
                    else:
                        # Match is CLOSED — route to duplicate_detector focus
                        if "needs:duplicate_detector" not in (candidate.labels or []):
                            try:
                                tracker.add_label(candidate.identifier, "needs:duplicate_detector")
                                # Update in-memory candidate for same reason.
                                if candidate.labels is None:
                                    candidate.labels = []
                                candidate.labels.append("needs:duplicate_detector")
                                logger.info(
                                    "Duplicate detection: added needs:duplicate_detector to %s "
                                    "(score=%.2f, matches closed %s)",
                                    candidate.identifier, score, match_issue.identifier,
                                )
                            except Exception as exc:
                                logger.debug(
                                    "Failed to add label for closed-match candidate %s: %s",
                                    candidate.identifier, exc,
                                )
                        break  # only flag the highest-scoring match

        self._last_duplicate_detection_metrics = {
            "candidate_count": len(candidates),
            "prework_count": prework_count,
            "scanned_count": len(detection_candidates),
            "deferred_count": deferred_count,
            "limit": limit,
        }
        return candidates

    @staticmethod
    def _is_native_decomposition_tracker_kind(kind: str | None) -> bool:
        return (kind or "").strip().lower() in {"oompah_md", "oompah.md", "oompah"}

    def _resolved_project_tracker_kind(self, project: object) -> str | None:
        project_kind = getattr(project, "tracker_kind", None)
        if isinstance(project_kind, str) and project_kind.strip():
            return project_kind
        return getattr(self.config, "tracker_kind", None)

    def _project_allows_native_decomposition(self, project: object) -> bool:
        return self._is_native_decomposition_tracker_kind(
            self._resolved_project_tracker_kind(project)
        )

    def _issue_allows_native_decomposition(
        self, issue: Issue, project_id: str | None = None
    ) -> bool:
        effective_project_id = project_id or issue.project_id
        if effective_project_id:
            try:
                project = self.project_store.get(effective_project_id)
            except Exception:
                project = None
            if project is not None:
                return self._project_allows_native_decomposition(project)

        tracker_kind = getattr(issue, "tracker_kind", None)
        if tracker_kind:
            return self._is_native_decomposition_tracker_kind(tracker_kind)
        return self._is_native_decomposition_tracker_kind(
            getattr(self.config, "tracker_kind", None)
        )

    def _fetch_proposed_issues(self) -> list[Issue]:
        """Fetch Proposed issues for intake processing.

        Proposed issues are intentionally not normal dispatch candidates, so
        intake maintenance reads them by state directly.
        """
        projects = self.project_store.list_all()
        if not projects:
            try:
                return self.tracker.fetch_issues_by_states([PROPOSED])
            except (TrackerNotConfiguredError, TrackerTimeoutError, TrackerError) as exc:
                logger.debug("Failed to fetch legacy Proposed issues: %s", exc)
                return []

        proposed: list[Issue] = []
        for project in projects:
            if getattr(project, "paused", False):
                continue
            try:
                tracker = self._tracker_for_project(project.id)
                issues = tracker.fetch_issues_by_states([PROPOSED])
            except TrackerNotConfiguredError:
                continue
            except (TrackerTimeoutError, TrackerError, ProjectError) as exc:
                logger.debug(
                    "Failed to fetch Proposed issues for project %s: %s",
                    project.id,
                    exc,
                )
                continue
            for issue in issues:
                issue.project_id = project.id
                proposed.append(issue)
        return proposed

    def _process_epic_proposals(
        self,
        _candidates: list[Issue] | None = None,
    ) -> list[Issue]:
        """Generate/apply decomposition proposals for oversized Proposed issues."""
        issues = self._fetch_proposed_issues()
        processed: list[Issue] = []
        metrics = {
            "proposed_count": len(issues),
            "processed_count": 0,
            "created_count": 0,
            "applied_count": 0,
            "promoted_count": 0,
            "comment_posted_count": 0,
            "duplicate_suppressed_count": 0,
            "error_count": 0,
        }
        for issue in issues:
            allow_decomposition = self._issue_allows_native_decomposition(issue)
            tracker = (
                self._tracker_for_project(issue.project_id)
                if issue.project_id
                else self.tracker
            )
            auto_promote = True
            project = None
            if issue.project_id:
                try:
                    project = self.project_store.get(issue.project_id)
                except Exception:
                    project = None
                if project is not None:
                    auto_promote = bool(getattr(project, "intake_auto_promote", True))
            try:
                result = process_epic_proposal_issue(
                    tracker,
                    issue,
                    auto_promote=auto_promote,
                    allow_decomposition=allow_decomposition,
                    project=project,
                )
            except Exception as exc:  # noqa: BLE001
                metrics["error_count"] += 1
                logger.debug(
                    "Failed to process epic proposal for %s: %s",
                    issue.identifier,
                    exc,
                )
                continue
            if result is None:
                continue
            processed.append(issue)
            metrics["processed_count"] += 1
            if getattr(result, "duplicate_suppressed", False):
                metrics["duplicate_suppressed_count"] += 1
            if getattr(result, "created", False):
                metrics["created_count"] += 1
            if getattr(result, "comment_posted", False):
                metrics["comment_posted_count"] += 1
            if getattr(result, "promoted", False):
                metrics["promoted_count"] += 1
            if getattr(result, "created_child_count", 0) or getattr(
                result, "updated_child_count", 0
            ):
                metrics["applied_count"] += 1

        self._last_epic_proposal_metrics = metrics
        return processed

    def _select_dispatchable(self, candidates: list[Issue]) -> list[Issue]:
        """Sort candidates and filter via _should_dispatch.

        Designed to be called via run_in_executor from _handle_dispatch_needed
        so tracker calls inside _should_dispatch (label/blocker resolution)
        run off the asyncio event loop, keeping uvicorn
        responsive during heavy ticks. See task oompah-zlz_2-nvr.

        Returns the issues that pass _should_dispatch in priority/age order.
        The async caller is still responsible for re-checking _available_slots
        in its dispatch loop because slot count drops with each successful
        dispatch.
        """
        sorted_candidates = self._sort_for_dispatch(candidates)
        sorted_issues = [
            issue
            for issue in sorted_candidates
            if canonicalize_status(issue.state) != PROPOSED
        ]
        prework_count = len(sorted_candidates) - len(sorted_issues)
        slots = self._available_slots()
        if slots <= 0:
            self._last_selection_metrics = {
                "candidate_count": len(sorted_candidates),
                "prework_count": prework_count,
                "scanned_count": 0,
                "ready_count": 0,
                "deferred_count": len(sorted_issues),
                "scan_limit": getattr(self.config, "dispatch_scan_limit", 64),
            }
            return []
        configured_limit = getattr(self.config, "dispatch_scan_limit", 64)
        scan_limit = configured_limit if configured_limit > 0 else len(sorted_issues)
        target_ready = slots + getattr(self.config, "dispatch_ready_buffer", 8)

        # Build the comparison pool: running + claimed + retry_pending issues
        # from all projects. These are the issues that already have or will get
        # an agent, so we want to suppress duplicates from the candidate list.
        in_flight_issues: list[Issue] = []
        for entry in self.state.running.values():
            if entry.issue:
                in_flight_issues.append(entry.issue)

        # claimed is a set of issue_ids — build minimal Issue stubs for similarity
        # comparison (only title + project_id matter for the check).
        claimed_ids: set[str] = self.state.claimed
        # retry_attempts also tracks in-flight work by issue_id
        retry_ids: set[str] = set(self.state.retry_attempts.keys())

        # Filter out candidates that are duplicates of in-flight issues.
        # For each candidate, check against both the in-flight set (to
        # suppress duplicates of already-dispatched work) and the candidate
        # list itself (to suppress inter-candidate duplicates, keeping the
        # highest-priority/oldest instance).
        dispatchable: list[Issue] = []
        reserved_shared_epics: set[tuple[str, str]] = set()
        scanned = 0

        for issue in sorted_issues:
            if scanned >= scan_limit:
                break
            scanned += 1
            # Build pool: full in-flight issues + already-accepted candidates this tick
            pool: list[Issue] = list(in_flight_issues) + list(dispatchable)
            similar = find_similar_issues(
                issue,
                pool,
                min_score=_DISPATCH_DUPLICATE_SUPPRESSION_SCORE,
            )
            if similar:
                dup_issue, score = similar[0]
                logger.debug(
                    "Dispatch duplicate suppressed %s (score=%.2f, dup=%s)",
                    issue.identifier,
                    score,
                    dup_issue.identifier,
                )
                continue

            shared_epic_key: tuple[str, str] | None = None
            serializes_shared_epic = (
                issue.priority != 0 or self._is_epic_rebase_task(issue)
            )
            if issue.parent_id and serializes_shared_epic:
                shared_epic_key = (
                    str(issue.project_id or ""),
                    str(issue.parent_id).strip(),
                )
                if shared_epic_key in reserved_shared_epics:
                    logger.debug(
                        "Dispatch shared-epic batch suppress %s "
                        "(epic=%s project=%s)",
                        issue.identifier,
                        issue.parent_id,
                        issue.project_id,
                    )
                    continue

            if not self._should_dispatch(issue):
                continue

            dispatchable.append(issue)
            if shared_epic_key is not None:
                reserved_shared_epics.add(shared_epic_key)
            if len(dispatchable) >= target_ready:
                break

        deferred_count = max(len(sorted_issues) - scanned, 0)
        if deferred_count:
            logger.debug(
                "Dispatch selection deferred %d candidate(s) after scanned=%d "
                "ready=%d scan_limit=%d target_ready=%d",
                deferred_count,
                scanned,
                len(dispatchable),
                scan_limit,
                target_ready,
            )
        self._last_selection_metrics = {
            "candidate_count": len(sorted_candidates),
            "prework_count": prework_count,
            "scanned_count": scanned,
            "ready_count": len(dispatchable),
            "deferred_count": deferred_count,
            "scan_limit": scan_limit,
            "target_ready": target_ready,
        }
        return dispatchable

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
            if (
                not profile.issue_types
                and not profile.keywords
                and profile.min_priority is None
                and profile.max_priority is None
            ):
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

    def _escalate_profile(
        self, current_profile: AgentProfile | None, issue: Issue
    ) -> AgentProfile | None:
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
        for higher_name in hierarchy[idx + 1 :]:
            higher = self._get_profile_by_name(higher_name)
            if higher:
                return higher
        return None

    def _next_profile_for_retry(
        self, entry: "RunningEntry"
    ) -> tuple[AgentProfile | None, str]:
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
            ATTACHMENTS_SUBDIR,
            AttachmentStore,
            Attachment,
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

        # Read existing rich records from tasks, then merge.
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
                issue.identifier,
                merged,
                project_root=workspace_path,
            )
        except Exception as exc:
            logger.warning(
                "set_attachments failed for %s: %s",
                issue.identifier,
                exc,
            )
            return

        # Completion comment listing what was generated.
        names = [os.path.basename(e["path"]) for e in new_records]
        msg = "Agent produced " + ", ".join(names)
        try:
            self._post_comment(
                issue.identifier,
                msg,
                project_id=issue.project_id,
            )
        except Exception:
            pass

    def _reap_oversize_outputs(self, workspace_path: str, issue: Issue) -> None:
        """Drop agent-generated attachments that push the issue over the
        per-issue size cap. Posts a warning comment listing what was
        removed."""
        from oompah.attachments import (
            ATTACHMENTS_SUBDIR,
            MAX_PER_ISSUE_BYTES,
        )

        out_dir = os.path.join(
            workspace_path,
            ATTACHMENTS_SUBDIR,
            issue.identifier,
            "outputs",
        )
        if not os.path.isdir(out_dir):
            return
        # Sum across both inputs and outputs to compute total.
        in_dir = os.path.join(
            workspace_path,
            ATTACHMENTS_SUBDIR,
            issue.identifier,
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
                files.append(
                    (os.path.getmtime(full), full, entry, os.path.getsize(full))
                )
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
                    issue.identifier,
                    msg,
                    project_id=issue.project_id,
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
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except FileNotFoundError:
            logger.debug(
                "git lfs not installed; skipping pull for %s", issue_identifier
            )
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
                focus.name,
                focus.provider_id,
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
                        focus.name,
                        role,
                        provider.name,
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
        return (
            profile.model
            or provider.default_model
            or (provider.models[0] if provider.models else None)
        )

    def _resolve_focus_provider_override(self, focus) -> "Any | None":
        """Return the provider specified by *focus*'s own overrides, or ``None``.

        Unlike :meth:`_resolve_provider`, this helper checks **only** the
        focus-level fields (``focus.provider_id`` and ``focus.model_role``)
        and returns ``None`` when the focus does not actively override the
        provider.  The profile-level fallback chain (``profile.model_role``,
        ``profile.provider_id``, default) is intentionally omitted so callers
        that already hold an explicit :class:`DispatchTarget` can preserve it
        unless the focus overrides it.
        """
        if focus is None:
            return None
        pid = getattr(focus, "provider_id", None)
        if pid:
            p = self.provider_store.get(pid)
            if p is not None:
                return p
            logger.warning(
                "Focus %r references unknown provider_id=%r; ignoring focus provider override",
                focus.name,
                pid,
            )
        role = getattr(focus, "model_role", None)
        if role:
            p, _ = self._resolve_role(role)
            if p is not None:
                return p
        return None

    def _resolve_dispatch_targets(
        self, profile: AgentProfile
    ) -> "list[DispatchTarget]":
        """Resolve an ordered list of :class:`DispatchTarget` for *profile*.

        The candidates reflect the multi-candidate selection order from the
        role assigned to ``profile.model_role`` (if set and known to
        :attr:`role_store`), falling back to the legacy single-provider paths.

        Priority:
        1. ``profile.model_role`` → :class:`~oompah.roles.CandidateSelector`
           ordered candidates.  Candidates whose ``provider_id`` no longer
           exists in :attr:`provider_store` are silently skipped.
        2. ``profile.provider_id`` → single target.
        3. :meth:`~oompah.providers.ProviderStore.get_default` → single target.

        Focus-level overrides (``focus.provider_id``, ``focus.model_role``)
        are applied *inside* the worker after focus selection, not here.

        Returns an empty list when no provider can be resolved at all (e.g.
        a CLI-only deployment with no provider configured).
        """
        if profile.model_role:
            role = self.role_store.get(profile.model_role)
            if role and role.candidates:
                ordered = self._candidate_selector.ordered_candidates(role)
                targets: list[DispatchTarget] = []
                for i, cand in enumerate(ordered):
                    prov = self.provider_store.get(cand.provider_id)
                    if prov is None:
                        logger.debug(
                            "Skipping candidate %s/%s for role %r: provider not found in store",
                            cand.provider_id,
                            cand.model,
                            profile.model_role,
                        )
                        continue
                    targets.append(
                        DispatchTarget(
                            role_name=profile.model_role,
                            provider=prov,
                            model=cand.model,
                            candidate_key=f"{cand.provider_id}/{cand.model}",
                            source=f"role:{profile.model_role}[{i}]",
                            candidate=cand,
                        )
                    )
                if targets:
                    return targets

        # Legacy: profile.provider_id
        if profile.provider_id:
            prov = self.provider_store.get(profile.provider_id)
            if prov is not None:
                return [
                    DispatchTarget(
                        role_name=None,
                        provider=prov,
                        model=profile.model,
                        candidate_key=prov.id,
                        source="profile.provider_id",
                        candidate=None,
                    )
                ]

        # Default provider
        prov = self.provider_store.get_default()
        if prov is not None:
            return [
                DispatchTarget(
                    role_name=None,
                    provider=prov,
                    model=None,
                    candidate_key=prov.id,
                    source="default",
                    candidate=None,
                )
            ]

        return []

    def _candidate_preflight(self, target: "DispatchTarget") -> str:
        """Check whether a candidate can reasonably be used before starting a worker.

        Returns an empty string when the candidate is usable, or a normalized
        skip-reason string when the candidate should be skipped.  Reason
        codes reuse the same names as :data:`oompah.provider_health.ERROR_REASONS`
        where applicable:

        * ``"missing_credentials"`` — ``provider.api_key`` is absent for a
          per-token API provider. Subscription/no-auth API gateways may be
          usable without an Authorization header, matching the provider health
          check behavior.
        * ``"rate_limited"`` — the global rate-limit cooldown is active.
        * ``"budget_exceeded"`` — the budget window is exhausted **and** the
          candidate is a paid (per-token) model.  ACP subscription-billed
          providers and explicitly-free models are allowed through.
        * ``"invalid_model"`` — ``target.model`` is set but absent from
          ``provider.models`` (and not equal to ``provider.default_model``).

        Log lines produced here must not include ``provider.api_key`` or any
        other secret value.  Only the normalized reason and the
        ``candidate_key`` are surfaced.

        :param target: The :class:`DispatchTarget` to evaluate.
        :returns: Empty string (usable) or a skip-reason string.
        """
        provider = target.provider
        model = target.model
        provider_mode = (getattr(provider, "mode", "api") or "api").lower()

        # 1. Missing credentials. ACP providers are SDK-managed and do not need
        #    an API key in the provider record. API providers may point at
        #    local/internal OpenAI-compatible gateways that accept unauthenticated
        #    requests, so only per-token API providers require an explicit key.
        requires_api_key = (
            provider_mode != "acp"
            and (getattr(provider, "billing_model", "per_token") or "per_token")
            == "per_token"
        )
        if requires_api_key and not getattr(provider, "api_key", ""):
            logger.warning(
                "Preflight skip candidate %s (role=%s, provider=%s): missing_credentials",
                target.candidate_key,
                target.role_name or "legacy",
                getattr(provider, "name", target.candidate_key),
            )
            return "missing_credentials"

        # 2. Active global rate-limit cooldown — all providers share it for now.
        if self._is_rate_limited():
            logger.warning(
                "Preflight skip candidate %s (role=%s, provider=%s): rate_limited",
                target.candidate_key,
                target.role_name or "legacy",
                getattr(provider, "name", target.candidate_key),
            )
            return "rate_limited"

        # 3. Budget exhaustion — paid candidates are blocked; free/subscription
        #    candidates pass through so the orchestrator keeps making progress.
        if not self._check_budget():
            # ACP subscription-billed providers bypass the budget gate.
            if provider_mode == "acp" and not provider.is_per_token_billed("acp"):
                pass  # subscription ACP — allowed through
            elif model and provider.is_model_explicitly_free(model):
                pass  # explicitly $0 model — allowed through
            else:
                logger.warning(
                    "Preflight skip candidate %s (role=%s, provider=%s, model=%s):"
                    " budget_exceeded",
                    target.candidate_key,
                    target.role_name or "legacy",
                    getattr(provider, "name", target.candidate_key),
                    model or "(unset)",
                )
                return "budget_exceeded"

        # 4. Invalid model — model is specified but not in the provider's catalog.
        #    Providers with an empty models list (ACP SDK-managed) are skipped.
        if (
            model
            and getattr(provider, "models", None)
            and model not in provider.models
            and model != getattr(provider, "default_model", None)
        ):
            logger.warning(
                "Preflight skip candidate %s (role=%s, provider=%s, model=%s):"
                " invalid_model",
                target.candidate_key,
                target.role_name or "legacy",
                getattr(provider, "name", target.candidate_key),
                model,
            )
            return "invalid_model"

        return ""  # candidate passes all preflight checks

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
            return (
                f"an upstream API — Reason: {reason}" if reason else "an upstream API"
            )

        profile = self._get_profile_by_name(entry.agent_profile_name)
        if not profile:
            return (
                f"an upstream API — Reason: {reason}" if reason else "an upstream API"
            )

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
        when ``model_costs`` is populated. See task oompah-zlz_2-ag7h.

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
        return (input_tokens / 1000.0) * cost_in + (output_tokens / 1000.0) * cost_out

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
                sunday_date,
                datetime.min.time(),
                tzinfo=tz,
            )
        else:  # "day" (and any unknown value via the parser fallback)
            boundary = datetime.combine(
                now.date(),
                datetime.min.time(),
                tzinfo=tz,
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
                next_date,
                datetime.min.time(),
                tzinfo=tz,
            )
        else:  # "day"
            next_date = prev_dt.date() + timedelta(days=1)
            next_dt = datetime.combine(
                next_date,
                datetime.min.time(),
                tzinfo=tz,
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

    def _post_comment(
        self,
        identifier: str,
        text: str,
        author: str = "oompah",
        project_id: str | None = None,
    ) -> None:
        """Post a comment on an issue (best-effort, non-blocking)."""
        try:
            tracker = (
                self._tracker_for_project(project_id) if project_id else self.tracker
            )
            tracker.add_comment(identifier, text, author=author)
        except Exception as exc:
            logger.debug("Failed to post comment on %s: %s", identifier, exc)

    def deliver_comment_to_running_agent(
        self,
        identifier: str,
        text: str,
        *,
        comment_id: str | None = None,
    ) -> bool:
        """Deliver a newly posted comment into a running agent's live context.

        When an ACP agent is active for *identifier*, the comment text is
        enqueued on the agent's comment queue and will be delivered as a new
        user turn at the next ResultMessage boundary (between SDK turns).

        Returns True when the comment was successfully queued for delivery.
        Returns False (graceful fallback) when:
          - No agent is running for *identifier*.
          - The running agent uses a backend that does not support injection
            (e.g. the CLI or api_agent paths); the comment will be available
            as context on the next dispatch.

        Ordering guarantee: comments are delivered in the order they arrive at
        this method (FIFO asyncio.Queue). Idempotency: if *comment_id* is
        supplied and has already been queued for this run, the call is a no-op
        that returns True (already delivered → idempotent success).

        Audit log: every call appends an entry to
        ``self._agent_comment_delivery_log[issue_id]`` with timestamp,
        comment_id, text preview (first 100 chars), and status.
        """
        # Resolve issue_id from the identifier string.
        issue_id: str | None = None
        for iid, entry in self.state.running.items():
            if entry.identifier == identifier:
                issue_id = iid
                break

        if issue_id is None:
            logger.debug(
                "deliver_comment_to_running_agent: no running agent for %s",
                identifier,
            )
            return False

        queue = self._agent_comment_queues.get(issue_id)
        if queue is None:
            # Running agent without a comment queue (CLI / api_agent worker).
            logger.info(
                "Comment for %s: agent does not support mid-run injection "
                "(non-ACP worker); comment will be available on next dispatch",
                identifier,
            )
            self._agent_comment_delivery_log.setdefault(issue_id, []).append({
                "ts": time.time(),
                "comment_id": comment_id,
                "text_preview": text[:100],
                "status": "fallback",
            })
            return False

        # Idempotency check.
        if comment_id is not None:
            delivered = self._agent_delivered_comment_ids.setdefault(issue_id, set())
            if comment_id in delivered:
                logger.debug(
                    "Comment %s already delivered to agent for %s (idempotent)",
                    comment_id,
                    identifier,
                )
                return True  # already delivered — idempotent success
            delivered.add(comment_id)

        # Enqueue for delivery.
        try:
            queue.put_nowait(text)
        except asyncio.QueueFull:
            # Should not happen with an unbounded queue, but handle defensively.
            logger.warning(
                "Comment queue full for %s; dropping comment (comment_id=%s)",
                identifier,
                comment_id,
            )
            return False

        # Audit log.
        self._agent_comment_delivery_log.setdefault(issue_id, []).append({
            "ts": time.time(),
            "comment_id": comment_id,
            "text_preview": text[:100],
            "status": "queued",
        })
        logger.info(
            "Queued mid-run comment for %s (comment_id=%s, queue_size=%d)",
            identifier,
            comment_id,
            queue.qsize(),
        )
        return True

    def _mark_needs_human(
        self,
        tracker,
        identifier: str,
        comment: str,
        *,
        author: str = "oompah",
    ) -> None:
        """Move a task to Needs Human with a final actionable comment."""
        if hasattr(tracker, "mark_needs_human"):
            tracker.mark_needs_human(identifier, comment, author=author)
            return
        tracker.update_issue(identifier, status=NEEDS_HUMAN)
        tracker.add_comment(identifier, comment, author=author)

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
                # See task oompah-zlz_2-ag7h edge case
                # "model_costs set on a subscription-billed provider".
                if mode == "acp" and not provider.is_per_token_billed("acp"):
                    pc_in, pc_out = 0.0, 0.0
                elif provider.model_costs and model_id != "unknown":
                    # Override with provider model costs if available.
                    mp_in, mp_out = provider.get_model_costs(model_id)
                    if mp_in or mp_out:
                        pc_in, pc_out = mp_in, mp_out
            cost_usd = (input_tokens / 1000.0) * pc_in + (
                output_tokens / 1000.0
            ) * pc_out

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

        Storage key: ``oompah.task_costs``, written via the tracker protocol
        (``set_metadata_field``). Works for native frontmatter and
        GitHub-backed tasks.
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
                    entry.identifier,
                    exc,
                )
                return

            # Fetch existing metadata
            existing_meta: dict[str, Any] = {}
            try:
                existing_meta = dict(tracker.get_metadata(issue.identifier))
            except Exception as exc:
                logger.debug(
                    "cost_record: failed to fetch metadata for %s: %s",
                    entry.identifier,
                    exc,
                )
                # Proceed with no existing costs — we'll write what we have

            # Merge new record into existing cost record
            existing_costs = existing_meta.get("oompah.task_costs")
            merged_costs = self._merge_cost_records(
                existing_costs if isinstance(existing_costs, dict) else None,
                new_record,
            )
            existing_meta["oompah.task_costs"] = merged_costs

            # Persist merged metadata
            try:
                tracker.set_metadata_field(
                    issue.identifier,
                    "oompah.task_costs",
                    merged_costs,
                )
                logger.info(
                    "cost_record: wrote %s total=$%.4f models=%s",
                    entry.identifier,
                    merged_costs["total_cost_usd"],
                    ",".join(merged_costs["by_model"].keys()),
                )
            except Exception as exc:
                logger.warning(
                    "cost_record: failed to write metadata for %s: %s",
                    entry.identifier,
                    exc,
                )
        except Exception as exc:
            logger.warning(
                "cost_record: unexpected error for %s: %s",
                entry.identifier,
                exc,
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
                entry.identifier,
                exc,
            )

    # ------------------------------------------------------------------
    # Per-agent telemetry comment (task oompah-zlz_2-y3fy)
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
        or "YOLO-reopen" when the task carries a YOLO reopen label
        (ci-fix / merge-conflict) — those dispatches are not driven by
        the orchestrator's retry queue, they're orchestrated by YOLO
        relabeling the task.
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
        self,
        entry: RunningEntry,
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
        mode = (
            (getattr(profile, "mode", "auto") or "auto").lower() if profile else "auto"
        )
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
            model_id = (
                self._resolve_model(profile, provider) if profile and provider else None
            )
            model_id = model_id or "unknown"
        is_subscription_acp = bool(
            mode == "acp"
            and provider is not None
            and not provider.is_per_token_billed("acp")
        )
        return provider_name, model_id, mode, is_subscription_acp

    def _format_telemetry_comment(
        self,
        entry: RunningEntry,
        exit_reason: str,
        elapsed_seconds: float,
    ) -> str:
        """Build the per-agent telemetry comment text for ``entry``.

        Format (one block per worker run, see task oompah-zlz_2-y3fy):

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
                    sdk_cost_usd=getattr(session, "sdk_cost_usd", None)
                    if session
                    else None,
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
        self,
        entry: RunningEntry,
        exit_reason: str,
        elapsed_seconds: float,
    ) -> None:
        """Post the per-agent telemetry comment for ``entry`` (sync).

        Exceptions are caught and logged at WARNING so a comment-write
        failure can never block the worker exit path. Designed to be
        invoked from a background thread via ``_fire_telemetry_comment``.
        """
        try:
            comment = self._format_telemetry_comment(
                entry,
                exit_reason,
                elapsed_seconds,
            )
            project_id = entry.issue.project_id if entry.issue else None
            self._post_comment(
                entry.identifier,
                comment,
                project_id=project_id,
            )
        except Exception as exc:
            logger.warning(
                "telemetry_comment: failed to write for %s: %s",
                entry.identifier,
                exc,
            )

    def _fire_telemetry_comment(
        self,
        entry: RunningEntry,
        exit_reason: str,
        elapsed_seconds: float,
    ) -> None:
        """Fire-and-forget: post the per-agent telemetry comment in a
        background thread.

        Mirrors :meth:`_fire_task_cost_record` — exceptions are logged
        but never propagate so the worker exit path stays unblocked.
        See task oompah-zlz_2-y3fy.
        """
        try:
            self._tick_pool.submit(
                self._write_telemetry_comment,
                entry,
                exit_reason,
                elapsed_seconds,
            )
        except Exception as exc:
            logger.warning(
                "telemetry_comment: failed to submit background write for %s: %s",
                entry.identifier,
                exc,
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
            logger.debug(
                "Failed to clear handoff labels on %s: %s", issue.identifier, exc
            )

    def _is_first_dispatch(
        self, issue: Issue, attempt: int | None, override_profile: str | None
    ) -> bool:
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
            precisely what stops the failure mode in oompah-zlz_2-0pr (task
            trickle-icl → PR #32 against main instead of pushing to
            trickle-rl5).

        Running such issues on the catch-all "default" profile first means
        the safety rails come too late: if the cheap-profile dispatch
        produces a bad-but-CI-passing change, the task closes without the
        specialist ever running. See oompah-zlz_2-2sd and oompah-zlz_2-0pr.

        Detection mirrors each Focus's labels and keywords. We check
        labels/keywords directly rather than running select_focus to keep
        this fast and deterministic — and to avoid taking the LLM-triage
        path during the dispatch decision.
        """
        labels = {l.lower() for l in (issue.labels or [])}
        if "merge-conflict" in labels or "ci-fix" in labels:
            return True
        if canonicalize_status(issue.state) in _EPIC_REVIEW_REPAIR_STATUSES:
            return True
        # Also match each Focus's keywords (whole-word, case-insensitive)
        # so tasks that describe the work but lack the label still get the carve-out.
        text = f"{issue.title or ''} {issue.description or ''}".lower()
        for kw in (
            # merge_conflict keywords
            "merge conflict",
            "rebase conflict",
            "resolve conflict",
            # ci_fix keywords
            "ci fix",
            "ci-fix",
            "failed ci",
            "fix ci",
            "failing tests",
            "tier-",
            "matrix-verify",
            "github actions failure",
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
            if (
                not p.issue_types
                and not p.keywords
                and p.min_priority is None
                and p.max_priority is None
            ):
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
        merge-conflict / ci-fix task is dispatched outside the
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

    async def _dispatch(
        self, issue: Issue, attempt: int | None, override_profile: str | None = None
    ) -> None:
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
            and not self._is_safety_critical_issue(
                issue
            )  # merge-conflict: skip cost opt
        ):
            # default_first_dispatch: use the catch-all profile on first dispatch,
            # but remember what the "natural" profile would be so the first retry
            # can jump straight to it instead of walking up from "default".
            default_profile = self._get_default_catch_all_profile()
            natural_matched = self._match_agent_profile(issue)
            if default_profile is None:
                # No default catch-all found — fall back to normal matching
                profile = natural_matched
            elif natural_matched and natural_matched.name != (
                default_profile.name if default_profile else ""
            ):
                # Natural profile differs from default — record it for escalation
                profile = default_profile
                natural_profile_name = natural_matched.name
                logger.info(
                    "default_first_dispatch: using profile=%s for %s (natural=%s)",
                    profile.name,
                    issue.identifier,
                    natural_profile_name,
                )
            else:
                # Natural match IS the default, or no natural match — no change
                profile = default_profile if default_profile else natural_matched
        else:
            profile = self._match_agent_profile(issue)
            # Safety-critical ACP preservation (oompah-zlz_2-lfy):
            # The default_first_dispatch carve-out for merge-conflict /
            # ci-fix tasks is intentional (we want the specialist focus's
            # safety rails on the FIRST dispatch). Side effect: in
            # setups where only the ``default`` profile has mode=acp,
            # carving out also strands the dispatch on the per-token
            # api_agent path, which is what blew up trickle-6zi on
            # 2026-05-07 (HTTP 429 token-rate-limit cascade).
            #
            # Fix: when the carve-out fires (i.e. a safety-critical
            # task routed via natural matching) AND the natural-matched
            # profile is NOT ACP, swap to the first ACP profile we can
            # find. Focus selection is independent of profile (label-
            # /keyword-driven), so the merge_conflict / ci_fix Focus's
            # must_not_do rails still apply unchanged.
            #
            # Only fires for first dispatch on a safety-critical task
            # without an explicit needs:* handoff label or override.
            # Retries / escalations keep their existing routing — we
            # don't want to second-guess the escalation hierarchy.
            if (
                self._is_first_dispatch(issue, attempt, override_profile)
                and not self._has_explicit_handoff_label(issue)
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
        # have predated a state change (e.g. user closing the task via the
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
                issue.identifier,
                exc,
            )
            refreshed = []
        if refreshed:
            cur_state = _state_key(refreshed[0].state)
            terminal = {_state_key(s) for s in self.config.tracker_terminal_states}
            if cur_state in terminal:
                logger.info(
                    "Aborting dispatch of %s: state moved to %r since fetch",
                    issue.identifier,
                    cur_state,
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
                lambda: tracker.update_issue(issue.identifier, status=IN_PROGRESS),
            )
        except Exception as exc:
            logger.warning(
                "Failed to set in_progress for %s: %s — aborting dispatch",
                issue.identifier,
                exc,
            )
            self.state.claimed.discard(issue.id)
            return

        # Shared tracker claim-and-verify protocol (TASK-461.2).
        # For trackers with an external/default-branch source of truth, stamp a
        # unique run ID onto the issue metadata and re-read it immediately. The
        # last writer wins: if another oompah instance claimed the issue after
        # us, our run ID will have been overwritten and we abort rather than
        # starting a duplicate agent.
        if (issue.tracker_kind or "").strip().lower() in {"github_issues", "oompah_md"}:
            _claim_run_id = str(uuid.uuid4())
            try:
                await asyncio.get_event_loop().run_in_executor(
                    self._tick_pool,
                    lambda rid=_claim_run_id: tracker.set_metadata_field(
                        issue.identifier, "oompah.agent_run_id", rid
                    ),
                )
                _claim_meta = await asyncio.get_event_loop().run_in_executor(
                    self._tick_pool,
                    lambda: tracker.get_metadata(issue.identifier),
                )
                _confirmed_run_id = _claim_meta.get("oompah.agent_run_id")
                if _confirmed_run_id != _claim_run_id:
                    logger.info(
                        "GitHub claim race on %s: our run_id=%s observed=%s"
                        " — aborting dispatch, another instance owns this task",
                        issue.identifier,
                        _claim_run_id,
                        _confirmed_run_id,
                    )
                    self.state.claimed.discard(issue.id)
                    return
                logger.debug(
                    "GitHub claim confirmed for %s run_id=%s",
                    issue.identifier,
                    _claim_run_id,
                )
            except Exception as exc:
                logger.warning(
                    "GitHub run-id claim protocol failed for %s: %s"
                    " — proceeding without claim verification",
                    issue.identifier,
                    exc,
                )

        running_issue = replace(
            issue,
            state=_configured_in_progress_state(self.config.tracker_active_states),
        )
        try:
            post_update = await asyncio.get_event_loop().run_in_executor(
                self._tick_pool,
                lambda: tracker.fetch_issue_states_by_ids([issue.id]),
            )
        except Exception as exc:
            logger.debug(
                "Post-dispatch state refresh failed for %s: %s — using optimistic in_progress snapshot",
                issue.identifier,
                exc,
            )
            post_update = []
        if post_update:
            running_issue = post_update[0]
            if not running_issue.project_id:
                running_issue.project_id = issue.project_id
            for attr in (
                "work_branch",
                "branch_name",
                "target_branch",
                "review_url",
                "review_number",
            ):
                if not getattr(running_issue, attr, None) and getattr(
                    issue,
                    attr,
                    None,
                ):
                    setattr(running_issue, attr, getattr(issue, attr))
            if _state_key(running_issue.state) != "in_progress":
                running_issue = replace(
                    running_issue,
                    state=_configured_in_progress_state(
                        self.config.tracker_active_states
                    ),
                )

        # Remove from retry if present
        retry = self.state.retry_attempts.pop(issue.id, None)
        if retry and retry.timer_handle and not retry.timer_handle.cancelled():
            retry.timer_handle.cancel()

        now = datetime.now(timezone.utc)
        worker_task = asyncio.create_task(
            self._run_worker(running_issue, attempt, profile),
            name=f"worker-{issue.identifier}",
        )

        self.state.running[issue.id] = RunningEntry(
            worker_task=worker_task,
            identifier=issue.identifier,
            issue=running_issue,
            session=None,
            retry_attempt=attempt or 0,
            started_at=now,
            agent_profile_name=profile_name,
            natural_profile_name=natural_profile_name,
        )

        # Post dispatch comment in thread to avoid blocking event loop
        comment = (
            f"Retrying (attempt #{attempt}, agent: {profile_name})"
            if attempt and attempt > 1
            else f"Agent dispatched (profile: {profile_name})"
        )
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            self._tick_pool,
            lambda: self._post_comment(
                issue.identifier, comment, project_id=issue.project_id
            ),
        )  # fire-and-forget, don't await

        # Emit agent dispatched event on EventBus
        self.event_bus.emit(
            EventType.AGENT_DISPATCHED,
            {
                "issue_id": issue.id,
                "identifier": issue.identifier,
                "profile": profile_name,
                "attempt": attempt,
            },
        )
        self._notify_observers()

    async def _run_worker(
        self, issue: Issue, attempt: int | None, profile: AgentProfile | None = None
    ) -> None:
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

        Candidate failover:
        :meth:`_resolve_dispatch_targets` produces an ordered list of
        :class:`DispatchTarget` values for the profile.  Each candidate is
        tried in order; a :class:`ProviderStartupError` (raised before the
        agent actually starts task turns) causes the next candidate to be
        attempted.  Non-provider task failures propagate normally so the
        existing retry/escalation machinery handles them.
        """
        mode = (profile.mode if profile else "auto").lower()

        if mode == "cli":
            await self._run_cli_worker(issue, attempt, profile)
            return

        # acp / api / auto: resolve ordered dispatch targets for candidate failover.
        targets = self._resolve_dispatch_targets(profile) if profile else []

        # Apply project-level provider whitelist filter (TASK-407.10).
        # When the project has a non-empty provider_whitelist, only targets
        # whose provider.name is in that whitelist are eligible.  An empty
        # whitelist (the default) leaves targets unchanged.
        targets, whitelist_filtered = self._apply_project_provider_whitelist(
            targets, issue
        )

        if not targets and whitelist_filtered:
            # All candidates were removed by the project provider whitelist.
            # Do NOT fall through to ACP-no-target or CLI — that would bypass
            # the operator's explicit restriction.  Surface a clear error.
            project = (
                self.project_store.get(issue.project_id) if issue.project_id else None
            )
            whitelist = list(getattr(project, "provider_whitelist", []) or [])
            error_msg = (
                f"Project provider whitelist {whitelist!r} excludes all available "
                f"role candidates for issue {issue.identifier}. "
                "No agent started. Add a whitelisted provider to the role assignment "
                "or expand the project provider whitelist."
            )
            logger.error(
                "Dispatch blocked by project provider whitelist for issue %s: "
                "whitelist=%s filtered all candidates",
                issue.identifier,
                whitelist,
            )
            await self._on_worker_exit(issue.id, "abnormal", error_msg)
            return

        if not targets:
            # No resolvable provider targets (no whitelist involved).
            if mode == "acp":
                # ACP can run without a specific provider — the SDK manages it.
                await self._run_acp_worker(issue, attempt, profile, target=None)
                return
            if mode == "api":
                logger.warning(
                    "Profile %r is mode=api but no provider resolved; "
                    "falling through to cli for issue %s",
                    profile.name if profile else "unknown",
                    issue.identifier,
                )
            await self._run_cli_worker(issue, attempt, profile)
            return

        # Try each target in dispatch order; fall back on preflight skip or
        # provider startup failure.  Collect per-candidate skip/fail reasons
        # so the final error message identifies every skipped provider.
        skip_reasons: list[str] = []  # populated for both preflight and startup fails
        last_startup_error: ProviderStartupError | None = None
        for target in targets:
            # --- Preflight: check availability before starting the worker ---
            preflight_skip = self._candidate_preflight(target)
            if preflight_skip:
                skip_reasons.append(f"{target.candidate_key}: {preflight_skip}")
                continue

            try:
                if mode == "acp" or getattr(target.provider, "mode", "api") == "acp":
                    await self._run_acp_worker(issue, attempt, profile, target=target)
                else:
                    await self._run_api_worker(
                        issue, attempt, profile, target.provider, target=target
                    )
                # Candidate started successfully — record usage for role candidates
                # so the round-robin strategy picks a different one next time.
                if target.role_name and target.candidate is not None:
                    try:
                        self._candidate_selector.record_used(
                            target.role_name, target.candidate
                        )
                    except Exception:
                        logger.exception(
                            "Failed to record candidate usage for role=%s candidate=%s",
                            target.role_name,
                            target.candidate_key,
                        )
                return  # Worker completed (task-level errors handled inside the worker)
            except ProviderStartupError as e:
                last_startup_error = e
                skip_reasons.append(f"{target.candidate_key}: {e.reason}")
                logger.warning(
                    "Candidate %s startup failed (reason=%s): %s — trying next candidate",
                    target.candidate_key,
                    e.reason,
                    e,
                )

        # All candidates exhausted — no inner worker completed, so _on_worker_exit
        # was never called.  Call it here so the issue is properly unregistered.
        reasons_str = "; ".join(skip_reasons) if skip_reasons else str(last_startup_error)
        error_msg = (
            f"All {len(targets)} dispatch candidates unavailable: {reasons_str}"
        )
        logger.error(
            "All dispatch candidates failed for issue %s: %s",
            issue.identifier,
            error_msg,
        )
        await self._on_worker_exit(issue.id, "abnormal", error_msg)

    async def _run_api_worker(
        self,
        issue: Issue,
        attempt: int | None,
        profile: AgentProfile,
        provider,
        target: "DispatchTarget | None" = None,
    ) -> None:
        """Worker using the OpenAI-compatible API agent.

        When *target* is supplied (i.e. the caller is the candidate-failover
        loop in :meth:`_run_worker`), the *provider* argument comes directly
        from ``target.provider`` and the method uses ``target.model`` as the
        model baseline.  Focus-level overrides still apply, but the full
        ``profile.model_role`` resolution chain is **not** re-run so the
        specific candidate being tried is preserved.

        Startup failures (configuration errors before the agent turns begin)
        raise :class:`ProviderStartupError` when *target* is provided, which
        lets :meth:`_run_worker` try the next candidate.  When no target is
        provided (legacy call site), the original ``ValueError`` is raised.
        """
        exit_reason = "normal"
        error_msg = None
        max_turns = profile.max_turns if profile.max_turns else self.config.max_turns

        # Select focus first so its (optional) model/provider overrides
        # participate in resolution. See plans/per-focus-models.md and
        # plans/agentic-focus-triage.md. The async variant tries an LLM
        # call against the provider's default_model and falls back to
        # the deterministic scorer on any failure.
        focus = await select_focus_async(issue, provider=provider)
        logger.info(
            "Issue %s assigned focus: %s (%s)", issue.identifier, focus.name, focus.role
        )

        # Apply focus-level provider override if any. If the focus changes
        # the provider, log it.
        if target is not None:
            # Explicit dispatch target: only apply focus-level overrides.
            # Re-running the full _resolve_provider chain would always return
            # the *first* role candidate (via profile.model_role) and defeat
            # the failover logic for candidates beyond the first.
            focus_provider = self._resolve_focus_provider_override(focus)
        else:
            # Legacy path: full resolution including profile.model_role.
            focus_provider = self._resolve_provider(profile, focus=focus)
        if focus_provider is not None and focus_provider is not provider:
            logger.info(
                "Focus %r overrides provider: %s -> %s",
                focus.name,
                provider.name,
                focus_provider.name,
            )
            provider = focus_provider

        # Resolve model with focus participating. ACP-mode providers
        # with an empty catalog (Claude SDK, etc.) are SDK-managed —
        # the SDK picks the model from the operator's subscription,
        # so no model name is required at dispatch time.
        if target is not None and not (
            getattr(focus, "model", None) or getattr(focus, "model_role", None)
        ):
            # No focus model override: use the target's model directly.
            # Calling _resolve_model would re-resolve via profile.model_role
            # and return the first candidate's model, which is wrong here.
            model: str | None = (
                target.model
                or provider.default_model
                or (provider.models[0] if provider.models else None)
            )
        else:
            model = self._resolve_model(profile, provider, focus=focus)

        is_acp_sdk_managed = getattr(provider, "mode", "api") == "acp" and not (
            provider.models or []
        )
        if not model and not is_acp_sdk_managed:
            msg = (
                f"No model resolved for profile {profile.name!r} "
                f"with provider {provider.name}"
            )
            if target is not None:
                raise ProviderStartupError(
                    msg, candidate_key=target.candidate_key, reason="no_model"
                )
            raise ValueError(msg)

        # Diagnostic: surface where the model came from.
        if is_acp_sdk_managed and not model:
            model_source = "acp.sdk-managed"
            model_display = "(SDK-managed)"
        elif focus.model:
            model_source = f"focus={focus.name}.model"
            model_display = model
        elif (
            focus.model_role
            and provider.model_roles
            and provider.model_roles.get(focus.model_role) == model
        ):
            model_source = f"focus={focus.name}.model_role={focus.model_role}"
            model_display = model
        elif target is not None and model == target.model:
            model_source = f"target:{target.source}"
            model_display = model
        elif (
            profile.model_role
            and provider.model_roles
            and provider.model_roles.get(profile.model_role) == model
        ):
            model_source = f"profile={profile.name}.model_role={profile.model_role}"
            model_display = model
        elif profile.model and profile.model == model:
            model_source = f"profile={profile.name}.model"
            model_display = model
        else:
            model_source = "provider.default"
            model_display = model
        logger.info(
            "Resolved provider=%s model=%s source=%s for %s",
            provider.name,
            model_display,
            model_source,
            issue.identifier,
        )

        if not is_acp_sdk_managed:
            if (
                target is None  # legacy path: model_role is a provider.model_roles key
                and profile.model_role
                and provider.model_roles
                and profile.model_role not in provider.model_roles
            ):
                logger.error(
                    "Model role %r not defined in provider %s (available roles: %s)",
                    profile.model_role,
                    provider.name,
                    ", ".join(provider.model_roles),
                )
                raise ValueError(
                    f"Model role {profile.model_role!r} not defined in provider {provider.name}"
                )
            if (
                provider.models
                and model not in provider.models
                and model != provider.default_model
            ):
                logger.error(
                    "Model %s not available in provider %s (available: %s)",
                    model,
                    provider.name,
                    ", ".join(provider.models),
                )
                msg = f"Model {model} not available in provider {provider.name}"
                if target is not None:
                    raise ProviderStartupError(
                        msg,
                        candidate_key=target.candidate_key,
                        reason="invalid_model",
                    )
                raise ValueError(msg)
            if (
                provider.models
                and model not in provider.models
                and model == provider.default_model
            ):
                logger.warning(
                    "Model %s is provider.default_model but not in provider.models; proceeding with dispatch",
                    model,
                )

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
                # the shared epic worktree; otherwise per-task path.
                wp, _epic = self._create_workspace_for_issue(issue)

                self._post_comment(
                    issue.identifier,
                    f"Focus: {focus.role}",
                    project_id=issue.project_id,
                )
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
                    self._prompt_template,
                    issue,
                    attempt,
                    comments=comments,
                    focus_text=focus.render(project_obj),
                    workspace_path=wp,
                    memories=memories,
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
                    issue.identifier,
                    len(attachment_paths),
                    embedded,
                    elided,
                    ",".join(capabilities),
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
                t["function"]["name"] for t in _TD if t["function"]["name"] not in _OPT
            }
            if getattr(focus, "allow_image_output", False) and "image" in capabilities:
                base_tools.add("attach_image")

            # Per-dispatch JSONL log capturing every request, response,
            # and activity event. One file per dispatch so the user can
            # see exactly what was sent to and returned from the model.
            log_dir = os.environ.get("OOMPAH_AGENT_LOG_DIR") or os.path.join(
                os.path.expanduser("~"),
                ".oompah",
                "agent-logs",
            )
            agent_log_path = _agent_log_path(log_dir, issue.identifier)

            session = ApiAgentSession(
                base_url=provider.base_url,
                api_key=provider.api_key,
                model=model,
                workspace_path=workspace_path,
                max_turns=max_turns,
                stall_turns=self.config.stall_turns,
                system_prompt=(
                    "You are an autonomous coding agent. Use the provided tools to complete the task. "
                    "You MUST work independently. NEVER ask the human to explain how something works, "
                    "diagnose a problem, or tell you what approach to take — that is YOUR job. "
                    "The `ask_question` tool exists ONLY for genuine ambiguity where the issue could "
                    "reasonably mean two different things that lead to fundamentally different implementations. "
                    "If a competent engineer would know what to do, DO the work. "
                    "NEVER ask for confirmation of your plan — just execute it. "
                    "NEVER ask 'how should I proceed' or 'what should I prioritize'. "
                    "Restating the issue as a question, asking for confirmation of your plan, or asking "
                    "'how should I proceed' are all failures."
                ),
                enabled_tools=base_tools,
                model_max_context=provider.get_model_context(model),
                log_path=agent_log_path,
            )
            logger.info(
                "Agent log for %s -> %s",
                issue.identifier,
                agent_log_path,
            )

            # Update running entry with minimal session info, log path,
            # and resolved provider/model snapshot so _on_worker_exit's
            # telemetry comment can name them without re-resolving (the
            # focus / role may have changed mid-run). See task
            # oompah-zlz_2-y3fy.
            if issue.id in self.state.running:
                running_entry = self.state.running[issue.id]
                running_entry.workspace_path = workspace_path
                running_entry.agent_log_path = agent_log_path
                running_entry.provider_id = getattr(provider, "id", None)
                running_entry.provider_name = provider.name
                running_entry.model_name = model
                running_entry.candidate_key = (
                    target.candidate_key if target is not None else provider.id
                )
                # Role: focus override wins over profile role; falls back
                # to None when nothing role-driven was used.
                running_entry.model_role = (
                    getattr(focus, "model_role", None) or profile.model_role
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
                        self.state.running[
                            issue.id
                        ].session.last_message = activity_entry.summary[:200]
                        self.state.running[
                            issue.id
                        ].session.last_event = activity_entry.kind
                        self.state.running[
                            issue.id
                        ].session.last_timestamp = datetime.now(timezone.utc)
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
                        terminal = {
                            s.strip().lower()
                            for s in self.config.tracker_terminal_states
                        }
                        if state in terminal:
                            return True
                except Exception:
                    pass
                return False

            result = await session.run_task(
                prompt, on_activity=_on_activity, is_cancelled=_is_cancelled
            )

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
                logger.info(
                    "API agent asked a question on %s: %s",
                    issue.identifier,
                    result.question,
                )
            elif result.status == "rate_limited":
                exit_reason = "rate_limited"
                error_msg = result.error or "Rate limited by API"
                logger.warning(
                    "API agent rate limited on %s: %s", issue.identifier, error_msg
                )
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
            # then record what was produced in tasks metadata so the
            # dashboard can render it. Only on successful runs.
            if result.status == "succeeded":
                try:
                    self._reap_oversize_outputs(workspace_path, issue)
                except Exception as exc:
                    logger.debug(
                        "output reap failed for %s: %s",
                        issue.identifier,
                        exc,
                    )
                try:
                    self._record_generated_attachments(workspace_path, issue)
                except Exception as exc:
                    logger.warning(
                        "metadata writeback failed for %s: %s",
                        issue.identifier,
                        exc,
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
        self,
        issue: Issue,
        attempt: int | None,
        profile: AgentProfile,
        target: "DispatchTarget | None" = None,
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
          keeps cd-guard / shell-redirect in force.
        * Permission prompts are auto-accepted via the SDK's
          ``permission_mode="bypassPermissions"`` (mirrors
          ``--dangerously-skip-permissions``); the audit trail goes
          into per-agent JSONL via on_event.

        When *target* is provided, the provider/model from the target are used
        as the starting point for informational resolution (focus can still
        override).  This preserves the correct candidate when the failover loop
        selects a non-first candidate.
        """
        from oompah.acp_agent import AcpAgentSession
        from oompah.acp_tools import build_tool_catalog

        exit_reason = "normal"
        error_msg = None
        # Set when a provider-level launch failure should fail over to the
        # next dispatch candidate (next model in the role's priority list)
        # instead of being booked as a terminal worker exit.
        startup_failover = False
        max_turns = profile.max_turns if profile.max_turns else self.config.max_turns

        focus = await select_focus_async(issue, provider=None)
        logger.info(
            "Issue %s assigned focus: %s (%s)",
            issue.identifier,
            focus.name,
            focus.role,
        )

        # Resolve a provider/model purely for diagnostic and prompt-render
        # purposes — the SDK doesn't need a provider URL or API key, but
        # the prompt template embeds the model name and our state response
        # surfaces it for dashboard display.
        if target is not None:
            # Explicit dispatch target: start from target's provider/model,
            # then apply focus-level overrides only (not the full profile chain).
            provider = target.provider
            focus_provider = self._resolve_focus_provider_override(focus)
            if focus_provider is not None:
                provider = focus_provider
            model: str | None = target.model
            if getattr(focus, "model", None) or getattr(focus, "model_role", None):
                if provider is not None:
                    model = self._resolve_model(profile, provider, focus=focus)
        else:
            # Legacy path: full _resolve_provider chain.
            provider = self._resolve_provider(profile, focus=focus)
            model = None
            if provider is not None:
                model = self._resolve_model(profile, provider, focus=focus)
        # Fallback model name for display/telemetry when no provider model is
        # configured. Keep track of whether "default" is synthetic: non-Claude
        # ACP backends should omit it so their subscription/OAuth clients can
        # choose their own default model.
        resolved_model = model or profile.model
        synthetic_default_model = not resolved_model
        model = resolved_model or "default"

        capabilities = self._resolve_capabilities(provider, model) if provider else []
        project_obj = (
            self.project_store.get(issue.project_id) if issue.project_id else None
        )

        try:

            def _setup_worker():
                # Resolve workspace via the epic_strategy-aware helper.
                wp, _epic = self._create_workspace_for_issue(issue)

                self._post_comment(
                    issue.identifier,
                    f"Focus: {focus.role}",
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
                    self._prompt_template,
                    issue,
                    attempt,
                    comments=comments,
                    focus_text=focus.render(project_obj),
                    workspace_path=wp,
                    memories=memories,
                    attachments=attachments,
                    capabilities=capabilities,
                    project_root=wp,
                    project=project_obj,
                )
                return wp, rendered, attachments

            loop = asyncio.get_event_loop()
            workspace_path, prompt, _attachment_paths = await loop.run_in_executor(
                self._tick_pool,
                _setup_worker,
            )

            running_entry = self.state.running.get(issue.id)
            if running_entry:
                running_entry.focus_name = focus.name
                running_entry.focus_role = focus.role

            # Per-dispatch JSONL log. Reuses api_agent's location convention.
            log_dir = os.environ.get("OOMPAH_AGENT_LOG_DIR") or os.path.join(
                os.path.expanduser("~"),
                ".oompah",
                "agent-logs",
            )
            agent_log_path = _agent_log_path(log_dir, issue.identifier)
            log_fp = open(agent_log_path, "a", encoding="utf-8")
            logger.info(
                "ACP agent log for %s -> %s (mode=acp model=%s)",
                issue.identifier,
                agent_log_path,
                model,
            )

            # Update running entry session + telemetry snapshot. The
            # provider/model fields are diagnostic for ACP runs (the
            # SDK picks the actual model from the subscription) but
            # they're still what the operator sees in task comments.
            # See task oompah-zlz_2-y3fy.
            if issue.id in self.state.running:
                running_entry_acp = self.state.running[issue.id]
                running_entry_acp.workspace_path = workspace_path
                running_entry_acp.agent_log_path = agent_log_path
                running_entry_acp.provider_id = (
                    provider.id if provider is not None else "acp"
                )
                running_entry_acp.provider_name = (
                    provider.name if provider is not None else "acp"
                )
                running_entry_acp.model_name = model
                running_entry_acp.candidate_key = (
                    target.candidate_key
                    if target is not None
                    else (provider.id if provider is not None else "acp")
                )
                running_entry_acp.model_role = (
                    getattr(focus, "model_role", None) or profile.model_role
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

            task_tracker = self._tracker_for_issue(issue)
            tool_catalog = build_tool_catalog(
                workspace_path,
                project_store=self.project_store,
                project_id=issue.project_id or None,
                task_tracker=task_tracker,
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
                    log_fp.write(
                        json.dumps(
                            {
                                "ts": datetime.fromtimestamp(
                                    ev.timestamp,
                                    timezone.utc,
                                ).isoformat(),
                                "kind": ev.event,
                                "usage": ev.usage,
                                "payload": ev.payload,
                            },
                            default=str,
                        )
                        + "\n"
                    )
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
                    args_str = (
                        json.dumps(raw_input, default=str)[:140]
                        if raw_input is not None
                        else ""
                    )
                    summary = f"{tool_name}({args_str})"
                    detail = (
                        json.dumps(raw_input, default=str)[:2000]
                        if raw_input is not None
                        else ""
                    )
                elif ev.event == "acp_tool_result":
                    summary = "tool error" if payload.get("is_error") else "tool ok"
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
                            ev.timestamp,
                            timezone.utc,
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

            # ACP backend selection (oompah-zlz_2-0hzh): provider may
            # nominate a non-default backend via ModelProvider.backend.
            # Falls back to "claude" when unset, preserving back-compat
            # for legacy providers persisted before the field existed.
            acp_backend_name = (
                getattr(provider, "backend", None) or "claude"
                if provider is not None
                else "claude"
            )

            acp_model: str | None = None
            if acp_backend_name == "claude":
                # The Claude SDK picks the subscription default and only
                # understands Claude model names; forwarding a non-Claude
                # name (e.g. a default profile's "fast" role) is a no-op
                # at best, an error at worst.
                if model and any(
                    marker in model.lower()
                    for marker in ("claude", "haiku", "sonnet", "opus")
                ):
                    acp_model = model
            else:
                # Other backends (codex, opencode) take their own model
                # names. If no model resolved, do not forward the synthetic
                # "default" placeholder; their clients will choose a default.
                acp_model = None if synthetic_default_model else model

            # Billing tier flows first-class so backends can pick their
            # execution path (e.g. codex: per_token -> in-process SDK,
            # subscription -> codex CLI w/ OAuth). Defaults to per_token.
            acp_billing_model = (
                getattr(provider, "billing_model", None) or "per_token"
                if provider is not None
                else "per_token"
            )

            # --- Mid-run comment delivery setup (OOMPAH-211) ---
            # Create a per-run asyncio.Queue and register it so that
            # deliver_comment_to_running_agent() can enqueue comments
            # while the agent is working. The queue is unregistered in
            # the finally block regardless of how the session exits.
            _comment_queue: asyncio.Queue = asyncio.Queue()
            self._agent_comment_queues[issue.id] = _comment_queue

            session = AcpAgentSession(
                workspace_path=workspace_path,
                prompt=prompt_text,
                model=acp_model,
                max_turns=max_turns,
                tool_catalog=tool_catalog,
                on_event=_on_event,
                backend_name=acp_backend_name,
                billing_model=acp_billing_model,
                project_store=self.project_store,
                project_id=issue.project_id or None,
                task_tracker=task_tracker,
                comment_queue=_comment_queue,
            )

            try:
                status = await session.run_task()
            finally:
                # Unregister the comment queue. Any un-drained comments
                # remain visible in the next dispatch via the task's
                # comment history.
                self._agent_comment_queues.pop(issue.id, None)
                # Clean up idempotency tracking for this run.
                self._agent_delivered_comment_ids.pop(issue.id, None)
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
            #   crash dispatch over missing config). See task
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
                # See task oompah-zlz_2-ag7h.
                s.sdk_cost_usd = (
                    session.total_cost_usd
                    if (provider is not None and provider.is_per_token_billed("acp"))
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
                        provider.name,
                        model,
                        issue.identifier,
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
                # A launch/startup failure (the agent process never began
                # task turns — e.g. CLIConnectionError, "Argument list too
                # long", missing CLI) is provider-level: fail over to the
                # next candidate (next model in the role's priority list)
                # rather than booking a terminal exit on this one.
                if target is not None and _is_acp_launch_failure(error_msg):
                    startup_failover = True
                    raise ProviderStartupError(
                        error_msg,
                        candidate_key=target.candidate_key,
                        reason="launch_failed",
                    )

            if status == "succeeded":
                try:
                    self._reap_oversize_outputs(workspace_path, issue)
                except Exception as exc:
                    logger.debug(
                        "output reap failed for %s: %s",
                        issue.identifier,
                        exc,
                    )
                try:
                    self._record_generated_attachments(workspace_path, issue)
                except Exception as exc:
                    logger.warning(
                        "metadata writeback failed for %s: %s",
                        issue.identifier,
                        exc,
                    )

        except ProviderStartupError:
            # Propagate to the candidate-failover loop in _run_worker so it
            # can try the next model in the role's priority list. Do NOT
            # book a worker exit here — the issue stays registered across
            # candidate attempts, mirroring the API worker's behavior.
            raise
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
            # On startup failover the candidate loop will retry (or finally
            # call _on_worker_exit once all candidates are exhausted), so
            # skip the terminal exit here.
            if not startup_failover:
                await self._on_worker_exit(issue.id, exit_reason, error_msg)

    async def _run_cli_worker(
        self, issue: Issue, attempt: int | None, profile: AgentProfile | None = None
    ) -> None:
        """Worker using CLI subprocess (original behavior)."""
        exit_reason = "normal"
        error_msg = None
        agent_command = profile.command if profile else self.config.agent_command
        max_turns = (
            profile.max_turns
            if profile and profile.max_turns
            else self.config.max_turns
        )

        try:
            # Resolve workspace via the epic_strategy-aware helper:
            # under epic_strategy='shared' a child of an epic uses
            # the shared epic worktree; otherwise per-task path.
            workspace_path, _epic = self._create_workspace_for_issue(issue)
            if issue.id in self.state.running:
                self.state.running[issue.id].workspace_path = workspace_path

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
                logger.info(
                    "Issue %s assigned focus: %s (%s)",
                    issue.identifier,
                    cli_focus.name,
                    cli_focus.role,
                )
                self._post_comment(
                    issue.identifier,
                    f"Focus: {cli_focus.role}",
                    project_id=issue.project_id,
                )
                # Clean up handoff labels after focus selection
                self._clear_handoff_labels(issue)
                # Store focus on running entry for dashboard display.
                # CLI worker has no API provider/model resolution (the
                # claude subprocess picks its own model from auth), but
                # we still record the model role and a placeholder
                # provider/model so the telemetry comment has SOMETHING
                # to render. See task oompah-zlz_2-y3fy.
                cli_running = self.state.running.get(issue.id)
                if cli_running:
                    cli_running.focus_name = cli_focus.name
                    cli_running.focus_role = cli_focus.role
                    cli_running.provider_id = "cli"
                    cli_running.provider_name = "cli"
                    cli_running.model_name = (
                        profile.model if profile and profile.model else None
                    ) or "cli-managed"
                    cli_running.candidate_key = "cli"
                    cli_running.model_role = getattr(cli_focus, "model_role", None) or (
                        profile.model_role if profile else None
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
                    if issue.project_id
                    else None
                )

                for turn_number in range(1, max_turns + 1):
                    # Build prompt
                    if turn_number == 1:
                        prompt = render_prompt(
                            self._prompt_template,
                            current_issue,
                            attempt,
                            comments=cli_comments,
                            focus_text=cli_focus.render(cli_project_obj),
                            workspace_path=workspace_path,
                            memories=cli_memories,
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

                    if (
                        issue.id in self.state.running
                        and self.state.running[issue.id].session
                    ):
                        self.state.running[issue.id].session.turn_count = turn_number
                        self.state.running[issue.id].session.turn_id = (
                            session.turn_id or ""
                        )
                        self.state.running[issue.id].session.session_id = (
                            session.session_id or ""
                        )

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

                    active_norms = _dispatch_active_state_keys(
                        self.config.tracker_active_states
                    )
                    if _state_key(current_issue.state) not in active_norms:
                        break
                else:
                    # Loop completed without break — all turns used up
                    active_norms = _dispatch_active_state_keys(
                        self.config.tracker_active_states
                    )
                    if _state_key(current_issue.state) in active_norms:
                        exit_reason = "max_turns"
                        logger.info(
                            "CLI agent reached max turns for %s", issue.identifier
                        )

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
                delta_input = max(
                    0, new_input - entry.session.last_reported_input_tokens
                )
                delta_output = max(
                    0, new_output - entry.session.last_reported_output_tokens
                )
                delta_total = max(
                    0, new_total - entry.session.last_reported_total_tokens
                )

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
        * Posts a diagnostic comment on the task (author=oompah).
        * Reopens the task so it re-enters the dispatch cycle.

        Fail-open on any internal error so a gate bug can never pin a
        task in-progress forever.
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
                    base_branch = project.default_branch or "main"
                    access_token = getattr(project, "access_token", None)
                    if project.repo_url:
                        from oompah.scm import extract_repo_slug

                        slug = extract_repo_slug(project.repo_url)
            except Exception as exc:
                logger.warning(
                    "close_gate: project lookup failed for %s: %s — failing open",
                    entry.identifier,
                    exc,
                )
                return True

        if entry.issue is not None:
            if not getattr(current_issue, "work_branch", None):
                current_issue.work_branch = getattr(entry.issue, "work_branch", None)
            if not getattr(current_issue, "branch_name", None):
                current_issue.branch_name = getattr(entry.issue, "branch_name", None)

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
                    entry.identifier,
                    result.skip_reason,
                )
            else:
                logger.debug(
                    "close_gate: allowed for %s (open_prs=%d merged_prs=%d)",
                    entry.identifier,
                    result.open_prs,
                    result.merged_prs,
                )
            return True

        if (
            project_id
            and result.commits_ahead > 0
            and result.open_prs == 0
            and result.merged_prs == 0
        ):
            n_open, limit, at_capacity = self._project_review_capacity(project_id)
            if at_capacity:
                logger.info(
                    "close_gate: allowing %s with deferred review handoff "
                    "because project review cap is full (%d/%d)",
                    entry.identifier,
                    n_open,
                    limit,
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
                entry.identifier,
                exc,
            )

        # Reopen the task
        try:
            tracker = (
                self._tracker_for_project(project_id) if project_id else self.tracker
            )
            tracker.update_issue(entry.identifier, status=OPEN)
            logger.warning(
                "close_gate: REFUSED close for %s — %d commit(s) ahead of %s, "
                "open_prs=%d merged_prs=%d — task reopened",
                entry.identifier,
                result.commits_ahead,
                base_branch,
                result.open_prs,
                result.merged_prs,
            )
        except Exception as exc:
            logger.warning(
                "close_gate: failed to reopen %s after refusal: %s",
                entry.identifier,
                exc,
            )

        return False

    def _run_unpushed_gate(
        self,
        entry: "RunningEntry",
        current_issue: Issue,
        project_id: str | None,
    ) -> bool:
        """Run the unpushed gate to detect agents who completed without landing.

        Returns True when the completion is ALLOWED, False when REFUSED.

        When refused:
        * Posts a diagnostic comment on the task (author=oompah).
        * Reopens the task so it re-enters the dispatch cycle.

        Fail-open on any internal error so a gate bug can never pin a
        task in-progress forever.
        """
        from oompah.unpushed_gate import (
            UnpushedGateResult,
            check_unpushed_gate,
            build_unpushed_refusal_comment,
        )

        if not getattr(self.config, "close_gate_enabled", True):
            return True

        repo_path = ""
        base_branch = "main"
        if project_id:
            try:
                project = self.project_store.get(project_id)
                if project:
                    repo_path = project.repo_path or ""
                    base_branch = project.default_branch or "main"
            except Exception as exc:
                logger.warning(
                    "unpushed_gate: project lookup failed for %s: %s — failing open",
                    entry.identifier,
                    exc,
                )
                return True

        if entry.issue is not None:
            if not getattr(current_issue, "work_branch", None):
                current_issue.work_branch = getattr(entry.issue, "work_branch", None)
            if not getattr(current_issue, "branch_name", None):
                current_issue.branch_name = getattr(entry.issue, "branch_name", None)

        result = check_unpushed_gate(
            current_issue,
            repo_path=repo_path,
            base_branch=base_branch,
            entry_profile=entry.agent_profile_name,
            entry_focus=entry.focus_name or "",
            entry_attempt=entry.retry_attempt or 0,
        )

        if result.allowed:
            if result.skip_reason:
                logger.debug(
                    "unpushed_gate: allowed for %s (skip_reason=%s)",
                    entry.identifier,
                    result.skip_reason,
                )
            else:
                logger.debug(
                    "unpushed_gate: allowed for %s",
                    entry.identifier,
                )
            return True

        # REFUSED — post comment and reopen
        try:
            comment = build_unpushed_refusal_comment(
                current_issue, result, base_branch,
            )
            self._post_comment(
                entry.identifier,
                comment,
                project_id=project_id,
            )
        except Exception as exc:
            logger.warning(
                "unpushed_gate: failed to post refusal comment for %s: %s",
                entry.identifier,
                exc,
            )

        try:
            tracker = (
                self._tracker_for_project(project_id)
                if project_id
                else self.tracker
            )
            tracker.update_issue(entry.identifier, status=IN_PROGRESS)
            logger.warning(
                "unpushed_gate: REFUSED completion for %s — "
                "unpushed work detected (ahead=%d uncommitted=%s) — task re-opened",
                entry.identifier,
                result.commits_ahead,
                result.has_uncommitted,
            )
        except Exception as exc:
            logger.warning(
                "unpushed_gate: failed to re-open %s after refusal: %s",
                entry.identifier,
                exc,
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
        ``normal`` AND the task has moved to a terminal state — i.e.
        the agent successfully moved the task to a terminal state.

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
                entry.identifier,
                exc,
            )
            return VerifierResult(
                passed=True, skipped=True, skip_reason=f"workspace error: {exc}"
            )

        base_branch = "main"
        if project_id:
            try:
                project = self.project_store.get(project_id)
                if project and project.default_branch:
                    base_branch = project.default_branch
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
                entry.identifier,
                exc,
            )
            return VerifierResult(
                passed=True, skipped=True, skip_reason=f"verifier error: {exc}"
            )

        if result.skipped:
            logger.info(
                "completion verifier skipped for %s: %s",
                entry.identifier,
                result.skip_reason,
            )
        elif result.passed:
            logger.info(
                "completion verifier passed for %s",
                entry.identifier,
            )
        else:
            logger.warning(
                "completion verifier REJECTED close for %s: "
                "missing_files=%s missing_symbols=%s llm_verdict=%s",
                entry.identifier,
                (result.stage1.missing_files if result.stage1 else []),
                (result.stage1.missing_symbols if result.stage1 else []),
                (result.stage2.verdict if result.stage2 else None),
            )
        return result

    def _finish_epic_review_repair(
        self,
        tracker,
        entry: RunningEntry,
        current: Issue,
        project_id: str | None,
    ) -> bool | None:
        """Finalize a successful repair run on an epic review branch.

        Returns ``None`` when ``current`` is not an epic repair issue,
        ``True`` when it was returned to review, and ``False`` when review
        handoff failed and the task should remain dispatchable.
        """
        if project_id and not current.project_id:
            current.project_id = project_id
        if entry.issue is not None:
            if not current.issue_type:
                current.issue_type = entry.issue.issue_type
            merged_labels: list[str] = []
            for label in list(current.labels or []) + list(entry.issue.labels or []):
                if label not in merged_labels:
                    merged_labels.append(label)
            current.labels = merged_labels
            if not getattr(current, "work_branch", None):
                current.work_branch = getattr(entry.issue, "work_branch", None)
            if not getattr(current, "branch_name", None):
                current.branch_name = getattr(entry.issue, "branch_name", None)
        if not self._is_epic_review_repair_issue(current):
            return None

        review_ready = self._ensure_review_exists(entry, project_id)
        if not review_ready:
            return False

        labels = {str(label).strip().lower() for label in current.labels or []}
        for label in sorted(labels.intersection(_EPIC_REVIEW_REPAIR_LABELS)):
            try:
                tracker.update_issue(
                    current.identifier,
                    **{"remove-label": label},
                )
            except Exception as exc:  # noqa: BLE001 - status handoff still matters
                logger.debug(
                    "Failed to remove repair label %s from %s: %s",
                    label,
                    current.identifier,
                    exc,
                )
        try:
            tracker.update_issue(current.identifier, status=IN_REVIEW)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to return repaired epic %s to In Review: %s",
                current.identifier,
                exc,
            )
            return False

        if "merge-conflict" in labels:
            self._set_epic_rebase_state(
                current.identifier,
                EpicRebaseState.REBASED,
                project_id=project_id,
            )
        current.state = IN_REVIEW
        logger.info(
            "Epic review repair completed for %s; returned to In Review",
            current.identifier,
        )
        return True

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
                self.state.cost_by_profile[entry.agent_profile_name] = (
                    self.state.cost_by_profile.get(entry.agent_profile_name, 0.0) + cost
                )

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
        # exit reason — multiple runs on the same task each leave a
        # separate comment so the task history shows all attempts
        # side-by-side. See task oompah-zlz_2-y3fy.
        self._fire_telemetry_comment(entry, reason, elapsed)

        tokens_str = ""
        if entry.session and entry.session.total_tokens > 0:
            tokens_str = f" ({entry.session.total_tokens} tokens)"

        project_id = entry.issue.project_id if entry.issue else None

        if reason == "ask_question":
            # Agent asked a question — post it and move the issue to Needs Answer
            self.state.claimed.discard(issue_id)
            self.state.stall_counts.pop(issue_id, None)
            question_text = error or "Agent has a question (no text provided)"
            self._post_comment(
                entry.identifier,
                f"🤚 **Question from agent:**\n\n{question_text}",
                project_id=project_id,
            )
            try:
                tracker = (
                    self._tracker_for_project(project_id)
                    if project_id
                    else self.tracker
                )
                tracker.update_issue(
                    entry.identifier,
                    status=NEEDS_ANSWER,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to set asking_question state for %s: %s",
                    entry.identifier,
                    exc,
                )
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
            _exit_event = (
                EventType.AGENT_STALLED
                if reason == "stalled"
                else EventType.AGENT_MAX_TURNS
            )
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
            # earlier failure(s) likely filed transient bug tasks via
            # the error watcher.  Auto-close them now.  attempt == 0
            # was the first dispatch — nothing was retried, so don't
            # auto-close anything.
            if entry.retry_attempt and entry.retry_attempt > 0:
                self._auto_close_transient_errors_for_entry(entry)
            # Check if the agent actually closed the issue
            try:
                tracker = (
                    self._tracker_for_project(project_id)
                    if project_id
                    else self.tracker
                )
                current = tracker.fetch_issue_detail(entry.identifier)
                if current and not _is_terminal_state(
                    current.state, self.config.tracker_terminal_states
                ):
                    # Merge-conflict agents just rebase — closure happens when
                    # YOLO merges the MR.  Don't count these toward the reopen
                    # limit; just mark completed and let YOLO handle the rest.
                    current_labels = {l.lower() for l in (current.labels or [])}
                    repair_finished = self._finish_epic_review_repair(
                        tracker,
                        entry,
                        current,
                        project_id,
                    )
                    if repair_finished is not None:
                        if repair_finished:
                            self.state.completed.add(issue_id)
                            self.state.reopen_counts.pop(issue_id, None)
                            self._verifier_reject_counts.pop(issue_id, None)
                        else:
                            self.state.completed.discard(issue_id)
                    elif (
                        "merge-conflict" in current_labels
                        or canonicalize_status(current.state) == NEEDS_REBASE
                    ):
                        logger.info(
                            "Merge-conflict agent completed for %s — "
                            "closing, awaiting YOLO merge",
                            entry.identifier,
                        )
                        # Close the issue — the agent resolved the conflict.
                        # YOLO will reopen it if new conflicts arise.
                        try:
                            tracker.update_issue(
                                entry.identifier, **{"remove-label": "merge-conflict"}
                            )
                        except Exception:
                            pass
                        tracker.close_issue(entry.identifier)
                        self.state.completed.add(issue_id)
                        self.state.reopen_counts.pop(issue_id, None)
                        # Reactive epic auto-close (oompah-zlz_2-lvcd).
                        self._maybe_auto_close_parent_epic(current)
                    else:
                        # Track how many times this issue completed without closing
                        reopen_count = self.state.reopen_counts.get(issue_id, 0) + 1
                        self.state.reopen_counts[issue_id] = reopen_count
                        max_reopens = 3
                        if reopen_count >= max_reopens:
                            # Stop re-dispatching — agent can't close this issue
                            logger.warning(
                                "Agent completed without closing %s %d times — giving up (marking deferred)",
                                entry.identifier,
                                reopen_count,
                            )
                            self._mark_needs_human(
                                tracker,
                                entry.identifier,
                                (
                                    f"Agent completed {reopen_count} times without "
                                    "closing this issue. Human action required: "
                                    "review the agent run history and task state, "
                                    "then either close the task if the work is done "
                                    "or add specific guidance and move it back to Open."
                                ),
                            )
                            self.state.completed.add(issue_id)
                        else:
                            # Landing gate: check if the agent completed without landing
                            # before spending tokens on a profile escalation.
                            landing_gate_blocked = False
                            landing_gate_branch = ""
                            project = self.project_store.get(project_id)
                            if project:
                                landing_gate_branch = (
                                    entry.issue.branch_name
                                    or entry.issue.identifier
                                )
                                from oompah.landing_gate import (
                                    build_telemetry_event,
                                    check_landing_gate,
                                )

                                # For shared epic children, work lands against
                                # the parent epic's branch (e.g. epic-TASK-706),
                                # not directly against the project default branch.
                                # Resolve and pass the effective landing branch
                                # so the gate checks the right ref.
                                lg_effective_branch: str | None = None
                                if (entry.issue.parent_id or "").strip():
                                    _parent_epic = self._resolve_parent_epic(
                                        entry.issue
                                    )
                                    if _parent_epic is not None:
                                        lg_effective_branch = (
                                            self.project_store.epic_branch_name(
                                                _parent_epic.identifier
                                            )
                                        )
                                        landing_gate_branch = lg_effective_branch

                                lg_result = check_landing_gate(
                                    entry.issue,
                                    workspace_path=project.repo_path,
                                    base_branch=project.default_branch,
                                    effective_branch=lg_effective_branch,
                                )
                                if not lg_result.allowed:
                                    landing_gate_blocked = True
                                    telemetry = build_telemetry_event(
                                        lg_result,
                                        entry.issue,
                                        landing_gate_branch,
                                        entry.agent_profile_name,
                                        getattr(entry, "focus", None),
                                        entry.retry_attempt or 0,
                                        reopen_count,
                                    )
                                    logger.info(
                                        json.dumps(telemetry),
                                    )

                            # Try to escalate to a stronger profile before retrying
                            escalated, escalated_name = self._next_profile_for_retry(
                                entry
                            )
                            retry_error = (
                                "completed_without_landing"
                                if landing_gate_blocked
                                else "completed_without_closing"
                            )
                            if escalated:
                                delay = self._backoff_delay(reopen_count)
                                if landing_gate_blocked:
                                    msg = (
                                        f"Agent completed without landing — no commits "
                                        f"found on origin for branch "
                                        f"`{landing_gate_branch or entry.identifier}`. "
                                        f"Escalating from '{entry.agent_profile_name}' "
                                        f"to '{escalated.name}'. Retrying in "
                                        f"{delay // 1000}s ({reopen_count}/{max_reopens})."
                                    )
                                else:
                                    msg = (
                                        f"Agent completed without closing this issue "
                                        f"({elapsed:.0f}s{tokens_str}). Escalating "
                                        f"from '{entry.agent_profile_name}' to "
                                        f"'{escalated.name}'. Retrying in "
                                        f"{delay // 1000}s ({reopen_count}/{max_reopens})."
                                    )
                                self._post_comment(
                                    entry.identifier,
                                    msg,
                                    project_id=project_id,
                                )
                                self._schedule_retry(
                                    issue_id,
                                    attempt=reopen_count,
                                    identifier=entry.identifier,
                                    delay_ms=delay,
                                    error=retry_error,
                                    escalated_profile=escalated_name,
                                    project_id=project_id,
                                    context_entry=entry,
                                )
                                logger.info(
                                    "Escalating %s from %s to %s after completing without closing (%d/%d)",
                                    entry.identifier,
                                    entry.agent_profile_name,
                                    escalated.name,
                                    reopen_count,
                                    max_reopens,
                                )
                            elif landing_gate_blocked:
                                delay = self._backoff_delay(reopen_count)
                                self._post_comment(
                                    entry.identifier,
                                    f"Agent completed without landing — no commits "
                                    f"found on origin for branch "
                                    f"`{landing_gate_branch or entry.identifier}`. "
                                    f"No stronger profile is configured; retrying "
                                    f"with '{entry.agent_profile_name}' in "
                                    f"{delay // 1000}s ({reopen_count}/{max_reopens}).",
                                    project_id=project_id,
                                )
                                self._schedule_retry(
                                    issue_id,
                                    attempt=reopen_count,
                                    identifier=entry.identifier,
                                    delay_ms=delay,
                                    error=retry_error,
                                    escalated_profile=None,
                                    project_id=project_id,
                                    context_entry=entry,
                                )
                                logger.info(
                                    "Retrying %s with same profile %s after landing gate blocked escalation (%d/%d)",
                                    entry.identifier,
                                    entry.agent_profile_name,
                                    reopen_count,
                                    max_reopens,
                                )
                            else:
                                # No higher profile available — retry with same profile
                                tracker.update_issue(entry.identifier, status=OPEN)
                                logger.info(
                                    "Agent completed without closing %s — reset to open (%d/%d)",
                                    entry.identifier,
                                    reopen_count,
                                    max_reopens,
                                )
                else:
                    # Agent successfully closed the task.
                    #
                    # Step 1: Close gate (oompah-zlz_2-gz8w).
                    # Refuse the close when the branch has unmerged
                    # commits AND no open/merged PR exists. When
                    # refused, the gate reopens the task and posts a
                    # diagnostic comment — we don't proceed to the
                    # verifier or mark completed.
                    gate_passed = self._run_close_gate(
                        entry,
                        current,
                        project_id,
                    )
                    if not gate_passed:
                        # Gate refused. The task was reopened by the
                        # gate; the next dispatch cycle will pick it up.
                        # Skip verifier and completed tracking.
                        pass
                    else:
                        # ------------------------------------------------------------
                        # Step 1b: Unpushed gate (oompah-zlz_2-kc2k.1).
                        # Detect the pattern where the task is in a terminal state
                        # but commits are still local/uncommitted — the agent closed
                        # the task without ever landing.  Refuse and re-dispatch so
                        # the next agent can push + close properly.
                        gate_passed = self._run_unpushed_gate(
                            entry,
                            current,
                            project_id,
                        )
                        if not gate_passed:
                            # Gate refused; task re-opened, skip verifier.
                            pass
                        else:
                            # Step 2: Completion verifier (oompah-zlz_2-y0ns).
                            # Run the two-stage check (regex + LLM) against the
                            # task's "# Acceptance criteria" section to catch
                            # false-success closures where the agent's diff
                            # doesn't actually satisfy the AC.
                            verifier_result = self._run_completion_verifier(
                                entry,
                                current,
                                project_id,
                            )
                            max_verifier_rejects = 3
                            reject_count = self._verifier_reject_counts.get(
                                issue_id, 0
                            )
                            if (
                                not verifier_result.passed
                                and reject_count < max_verifier_rejects
                            ):
                                # Reject the close: reopen, post diagnostics,
                                # schedule a retry. Increment reject count so
                                # we eventually give up if the agent keeps
                                # shipping the same gap.
                                self._verifier_reject_counts[issue_id] = (
                                    reject_count + 1
                                )
                                try:
                                    tracker.reopen_issue(entry.identifier)
                                except Exception as exc:
                                    logger.warning(
                                        "Failed to reopen %s after verifier rejection: %s",
                                        entry.identifier,
                                        exc,
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
                                            "to %s: %s",
                                            entry.identifier,
                                            exc,
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
                                        escalated_profile=escalated_name
                                        if escalated
                                        else None,
                                        project_id=project_id,
                                        context_entry=entry,
                                    )
                                    logger.info(
                                        "Completion verifier rejected close for %s — "
                                        "reopened, retrying in %ds (reject %d/%d)",
                                        entry.identifier,
                                        delay // 1000,
                                        reject_count + 1,
                                        max_verifier_rejects,
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
                                        entry.identifier,
                                        reject_count + 1,
                                    )
                                # Auto-create review if agent pushed a branch.
                                # If review handoff fails for unmerged work,
                                # the task is reopened and should not be
                                # recorded as cleanly completed.
                                review_ready = self._ensure_review_exists(
                                    entry,
                                    project_id,
                                )
                                if review_ready:
                                    self.state.completed.add(issue_id)
                                    self.state.reopen_counts.pop(issue_id, None)
                                    self._verifier_reject_counts.pop(issue_id, None)
                                    # Reactive epic auto-close: if the just-closed
                                    # task is a child of an epic, evaluate the
                                    # parent for auto-close immediately rather
                                    # than waiting for the next full-sync tick.
                                    # See oompah-zlz_2-lvcd.
                                    self._maybe_auto_close_parent_epic(current)
                                else:
                                    self.state.completed.discard(issue_id)
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
            self._alerts.append(
                {
                    "level": "warning",
                    "source": "rate_limit",
                    "message": f"Rate limited by {rl_ctx} — pausing dispatch for {cooldown_s}s",
                }
            )
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
                project_id=project_id,
                context_entry=entry,
            )
            logger.warning(
                "Rate limited by %s — pausing dispatch for %ds. issue_id=%s retrying_in_ms=%d",
                rl_ctx,
                cooldown_s,
                issue_id,
                delay,
            )
        elif reason in ("max_turns", "stalled"):
            next_attempt = (entry.retry_attempt or 0) + 1
            delay = self._backoff_delay(next_attempt)

            # Check if we should decompose instead of retrying
            if self._should_decompose(entry.issue, next_attempt, project_id=project_id):
                asyncio.ensure_future(
                    self._trigger_decomposition(
                        issue_id,
                        entry,
                        next_attempt,
                        project_id,
                    )
                )
                logger.info(
                    "Triggering auto-decomposition for %s after %d attempts",
                    entry.identifier,
                    next_attempt,
                )
            else:
                # Track stall/failure count for escalation
                escalated = None
                escalated_name = ""
                if reason == "stalled":
                    self.state.stall_counts[issue_id] = (
                        self.state.stall_counts.get(issue_id, 0) + 1
                    )
                    stall_count = self.state.stall_counts[issue_id]

                # Escalate on both stalled and max_turns once threshold is met
                if next_attempt >= self.config.escalate_after_attempts:
                    escalated, escalated_name = self._next_profile_for_retry(entry)

                if escalated:
                    if reason == "stalled":
                        msg = (
                            f"Agent stalled {self.state.stall_counts.get(issue_id, 1)} time(s) ({elapsed:.0f}s{tokens_str}). "
                            f"Escalating from '{entry.agent_profile_name}' to '{escalated.name}'. "
                            f"Retrying in {delay // 1000}s (attempt #{next_attempt})"
                        )
                    else:
                        msg = (
                            f"Agent hit turn limit ({elapsed:.0f}s{tokens_str}). "
                            f"Escalating from '{entry.agent_profile_name}' to '{escalated.name}'. "
                            f"Retrying in {delay // 1000}s (attempt #{next_attempt})"
                        )
                    logger.info(
                        "Escalating issue %s from profile %s to %s (attempt=%d, reason=%s)",
                        entry.identifier,
                        entry.agent_profile_name,
                        escalated.name,
                        next_attempt,
                        reason,
                    )
                elif reason == "stalled":
                    msg = (
                        f"Agent stalled — no productive actions (writes/commands) "
                        f"for {self.config.stall_turns} consecutive turns "
                        f"({elapsed:.0f}s{tokens_str}). "
                        f"Retrying in {delay // 1000}s (attempt #{next_attempt})"
                    )
                else:
                    msg = (
                        f"Agent hit safety turn limit ({elapsed:.0f}s{tokens_str}). "
                        f"Retrying in {delay // 1000}s (attempt #{next_attempt})"
                    )
                self._post_comment(entry.identifier, msg, project_id=project_id)
                self._schedule_retry(
                    issue_id,
                    attempt=next_attempt,
                    identifier=entry.identifier,
                    delay_ms=delay,
                    error=error or reason,
                    escalated_profile=escalated_name or None,
                    project_id=project_id,
                    context_entry=entry,
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
            is_rate_limit = any(
                s in error_lower
                for s in ("429", "rate limit", "too many requests", "overloaded")
            )
            if is_rate_limit:
                cooldown_s = 120
                self._rate_limit_until = time.time() + cooldown_s
                self._alerts = [
                    a for a in self._alerts if a.get("source") != "rate_limit"
                ]
                rl_ctx = self._describe_rate_limit_context(entry, error)
                self._alerts.append(
                    {
                        "level": "warning",
                        "source": "rate_limit",
                        "message": f"Rate limited by {rl_ctx} — pausing dispatch for {cooldown_s}s",
                    }
                )

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
                project_id=project_id,
                context_entry=entry,
            )
            logger.warning(
                "Worker failed issue_id=%s issue_identifier=%s error=%s retrying_in_ms=%d",
                issue_id,
                entry.identifier,
                error,
                delay,
            )

        # Emit the agent lifecycle event on the EventBus
        self.event_bus.emit(
            _exit_event,
            {
                "issue_id": issue_id,
                "identifier": entry.identifier,
                "reason": reason,
                "error": error,
                "elapsed_s": elapsed,
            },
        )
        self._notify_observers()
        # Wake the dispatch loop so it can pick up the next candidate immediately.
        self._post_event(
            DispatchEvent(
                event_type=DispatchEventType.WORKER_EXIT,
                issue_id=issue_id,
                payload={"reason": reason},
            )
        )

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

    @staticmethod
    def _safe_context_value(value: Any) -> str | None:
        """Return a display-safe string for alert context values."""
        if value is None or not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _display_provider(
        provider_name: str | None,
        provider_id: str | None,
    ) -> str | None:
        """Format a provider name/id pair without exposing provider secrets."""
        provider_name = Orchestrator._safe_context_value(provider_name)
        provider_id = Orchestrator._safe_context_value(provider_id)
        if provider_name and provider_id and provider_name != provider_id:
            return f"{provider_name} ({provider_id})"
        return provider_name or provider_id

    @classmethod
    def _display_candidate(cls, candidate: dict[str, Any]) -> str:
        """Format one provider/model candidate for operator-facing alerts."""
        provider = cls._display_provider(
            candidate.get("provider_name"),
            candidate.get("provider_id"),
        )
        model = cls._safe_context_value(candidate.get("model"))
        if provider and model:
            return f"{provider}/{model}"
        if provider:
            return provider
        return cls._safe_context_value(candidate.get("candidate_key")) or "unknown"

    def _credential_alert_context(self, retry: RetryEntry) -> dict[str, Any]:
        """Build safe provider-selection context for a credential retry alert."""
        context: dict[str, Any] = {
            "task": retry.identifier,
            "attempt": retry.attempt,
        }

        project_id = self._safe_context_value(retry.project_id)
        if project_id:
            context["project_id"] = project_id
            try:
                project = self.project_store.get(project_id)
            except Exception:
                project = None
            project_name = self._safe_context_value(getattr(project, "name", None))
            if project_name:
                context["project_name"] = project_name

        agent_profile = self._safe_context_value(retry.agent_profile_name)
        if agent_profile:
            context["agent_profile"] = agent_profile
        next_profile = self._safe_context_value(retry.escalated_profile)
        if next_profile and next_profile != agent_profile:
            context["next_profile"] = next_profile

        profile = None
        for profile_name in (agent_profile, next_profile):
            if not profile_name:
                continue
            profile = self._get_profile_by_name(profile_name)
            if profile is not None:
                break

        model_role = self._safe_context_value(retry.model_role)
        if not model_role and profile is not None:
            model_role = self._safe_context_value(profile.model_role)
        if model_role:
            context["model_role"] = model_role

        provider_id = self._safe_context_value(retry.provider_id)
        provider_name = self._safe_context_value(retry.provider_name)
        model_name = self._safe_context_value(retry.model_name)
        candidate_key = self._safe_context_value(retry.candidate_key)
        if provider_id:
            context["provider_id"] = provider_id
        if provider_name:
            context["provider_name"] = provider_name
        if model_name:
            context["model"] = model_name
        if candidate_key:
            context["candidate_key"] = candidate_key

        candidates: list[dict[str, Any]] = []
        if profile is not None:
            try:
                targets = self._resolve_dispatch_targets(profile)
            except Exception:
                targets = []
            for target in targets:
                provider = getattr(target, "provider", None)
                candidates.append(
                    {
                        "role": self._safe_context_value(target.role_name),
                        "provider_id": self._safe_context_value(
                            getattr(provider, "id", None)
                        ),
                        "provider_name": self._safe_context_value(
                            getattr(provider, "name", None)
                        ),
                        "model": self._safe_context_value(target.model),
                        "candidate_key": self._safe_context_value(target.candidate_key),
                        "source": self._safe_context_value(target.source),
                    }
                )
        if candidates:
            context["candidate_providers"] = candidates
            if "model_role" not in context:
                role = self._safe_context_value(candidates[0].get("role"))
                if role:
                    context["model_role"] = role

        return context

    def _format_credential_alert_message(
        self,
        retry: RetryEntry,
        context: dict[str, Any],
    ) -> str:
        """Render a credential retry alert with actionable non-secret context."""
        details: list[str] = []
        project_name = self._safe_context_value(context.get("project_name"))
        project_id = self._safe_context_value(context.get("project_id"))
        if project_name and project_id and project_name != project_id:
            details.append(f"project={project_name} ({project_id})")
        elif project_name or project_id:
            details.append(f"project={project_name or project_id}")

        agent_profile = self._safe_context_value(context.get("agent_profile"))
        if agent_profile:
            details.append(f"profile={agent_profile}")
        model_role = self._safe_context_value(context.get("model_role"))
        if model_role:
            details.append(f"role={model_role}")

        provider = self._display_provider(
            context.get("provider_name"),
            context.get("provider_id"),
        )
        model = self._safe_context_value(context.get("model"))
        candidate_key = self._safe_context_value(context.get("candidate_key"))
        if provider:
            details.append(f"provider={provider}")
        if model:
            details.append(f"model={model}")
        if not provider and candidate_key:
            details.append(f"candidate={candidate_key}")

        candidates = context.get("candidate_providers") or []
        if not provider and candidates:
            rendered = [self._display_candidate(c) for c in candidates[:5]]
            if len(candidates) > 5:
                rendered.append(f"+{len(candidates) - 5} more")
            details.append(f"candidates={', '.join(rendered)}")

        message = (
            f"Missing provider credentials for {retry.identifier} "
            f"(attempt #{retry.attempt})"
        )
        if details:
            message += f" [{'; '.join(details)}]"
        return (
            message
            + " — configure the named provider API key/token in the Providers page"
        )

    def _credential_error_alerts(self) -> list[dict[str, Any]]:
        """Return transient alerts for retrying tasks whose last error was credential-related.

        These alerts are computed on demand from the current retry_attempts so
        they clear automatically when the retry succeeds or the task is no
        longer retrying.  They are *not* stored in ``self._alerts`` — they are
        injected into the ``get_snapshot()`` response only.
        """
        alerts: list[dict[str, Any]] = []
        for retry in self.state.retry_attempts.values():
            if not _is_credential_error(retry.error):
                continue
            source = f"cred_error:{retry.identifier}"
            context = self._credential_alert_context(retry)
            alerts.append(
                {
                    "level": "error",
                    "source": source,
                    "message": self._format_credential_alert_message(retry, context),
                    "context": context,
                }
            )
        return alerts

    # ------------------------------------------------------------------
    # Auto-decomposition
    # ------------------------------------------------------------------

    def _should_decompose(
        self, issue: Issue, next_attempt: int, project_id: str | None = None
    ) -> bool:
        """Check whether an issue should be auto-decomposed instead of retried."""
        if next_attempt < self.config.decompose_after_attempts:
            return False
        if not self._issue_allows_native_decomposition(issue, project_id=project_id):
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

    def _build_decomposition_prompt(
        self, issue: Issue, comments: list[dict], attempt: int
    ) -> str:
        """Build the prompt for the decomposition planner."""
        from oompah.focus import BUILTIN_FOCI

        foci_text = "\n".join(
            f"- {f.name}: {f.role}"
            for f in BUILTIN_FOCI
            if f.name not in ("epic_planner", "merge_conflict", "ci_fix")
        )
        comments_text = (
            "\n".join(
                f"- {c.get('author', '?')} ({c.get('created_at', '?')}): {c.get('text', '')}"
                for c in (comments or [])
            )
            or "(no comments)"
        )
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
        self.state.decompose_attempts[issue_id] = (
            self.state.decompose_attempts.get(issue_id, 0) + 1
        )

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
            payload = json.dumps(
                {
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a task decomposition planner. Return only valid JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                }
            ).encode()

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
                project_id=project_id,
                context_entry=entry,
            )

    async def _execute_decomposition(
        self,
        parent_issue: Issue,
        tasks: list[dict],
        tracker: TrackerProtocol,
        project_id: str | None,
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
                initial_status=OPEN,
                parent=parent_issue.identifier,
            )
            created.append(child)

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
                if (
                    isinstance(dep_idx, int)
                    and 0 <= dep_idx < len(created)
                    and dep_idx != i
                ):
                    try:
                        tracker.add_dependency(
                            created[i].identifier, created[dep_idx].identifier
                        )
                    except Exception:
                        pass

        # Move the original issue to the decomposed status.
        try:
            tracker.update_issue(
                parent_issue.identifier,
                status=DECOMPOSED,
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
        project_id: str | None = None,
        context_entry: RunningEntry | None = None,
        context_retry: RetryEntry | None = None,
    ) -> None:
        """Schedule a retry timer for an issue."""
        # Cancel existing retry
        existing = self.state.retry_attempts.pop(issue_id, None)
        if existing and existing.timer_handle and not existing.timer_handle.cancelled():
            existing.timer_handle.cancel()
        context_retry = context_retry or existing

        agent_profile_name = (
            getattr(context_entry, "agent_profile_name", None)
            or getattr(context_retry, "agent_profile_name", None)
            or escalated_profile
        )
        model_role = (
            getattr(context_entry, "model_role", None)
            or getattr(context_retry, "model_role", None)
        )
        if not model_role and agent_profile_name:
            profile = self._get_profile_by_name(agent_profile_name)
            if profile is not None:
                model_role = profile.model_role
        provider_id = (
            getattr(context_entry, "provider_id", None)
            or getattr(context_retry, "provider_id", None)
        )
        provider_name = (
            getattr(context_entry, "provider_name", None)
            or getattr(context_retry, "provider_name", None)
        )
        model_name = (
            getattr(context_entry, "model_name", None)
            or getattr(context_retry, "model_name", None)
        )
        candidate_key = (
            getattr(context_entry, "candidate_key", None)
            or getattr(context_retry, "candidate_key", None)
        )

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
            project_id=project_id,
            agent_profile_name=agent_profile_name,
            model_role=model_role,
            provider_id=provider_id,
            provider_name=provider_name,
            model_name=model_name,
            candidate_key=candidate_key,
        )
        # Emit retry scheduled event on EventBus
        self.event_bus.emit(
            EventType.ISSUE_RETRY_SCHEDULED,
            {
                "issue_id": issue_id,
                "identifier": identifier,
                "attempt": attempt,
                "delay_ms": delay_ms,
                "error": error,
                "project_id": project_id,
            },
        )

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
        self._post_event(
            DispatchEvent(
                event_type=DispatchEventType.RETRY_FIRED,
                issue_id=issue_id,
            )
        )

        try:
            issue = await asyncio.to_thread(self._fetch_retry_issue, retry)
        except (TrackerError, ProjectError):
            # Requeue
            self._schedule_retry(
                issue_id,
                retry.attempt + 1,
                retry.identifier,
                self._backoff_delay(retry.attempt + 1),
                "retry poll failed",
                escalated_profile=retry.escalated_profile,
                project_id=retry.project_id,
                context_retry=retry,
            )
            return

        if issue is None:
            # Issue no longer exists, release claim
            self.state.claimed.discard(issue_id)
            logger.info(
                "Retry released claim issue_id=%s (issue not found)", issue_id
            )
            return

        state_norm = _state_key(issue.state)
        if state_norm not in self._retryable_state_keys():
            self.state.claimed.discard(issue_id)
            if _is_terminal_state(issue.state, self.config.tracker_terminal_states):
                self.state.completed.add(issue_id)
            logger.info(
                "Retry released claim issue_id=%s state=%s (not retryable)",
                issue_id,
                issue.state,
            )
            # TASK-409: if the task is still In Progress in the tracker and no
            # agent is running for it, reset it to Open immediately.  The normal
            # orphan-reset sweep (_reset_orphaned_in_progress) would catch this
            # on the next tick, but acting here closes the window and avoids a
            # full tick delay.  In Progress tasks are never candidates (they are
            # not in active_states), which is exactly why we reached this branch.
            if issue_id not in self.state.running:
                try:
                    orphan = self._fetch_issue_across_trackers(retry.identifier)
                    if orphan is not None and _state_key(orphan.state) == "in_progress":
                        orphan_tracker = self._tracker_for_issue(orphan)
                        orphan_tracker.update_issue(retry.identifier, status=OPEN)
                        logger.info(
                            "Retry claim released: reset stale In Progress issue %s to Open",
                            retry.identifier,
                        )
                except Exception as exc:
                    logger.debug(
                        "Retry claim released: failed to reset In Progress issue %s: %s",
                        retry.identifier,
                        exc,
                    )
            return

        if self._available_slots() <= 0:
            self._schedule_retry(
                issue_id,
                retry.attempt + 1,
                issue.identifier,
                self._backoff_delay(retry.attempt + 1),
                "no available orchestrator slots",
                escalated_profile=retry.escalated_profile,
                project_id=issue.project_id or retry.project_id,
                context_retry=retry,
            )
            return

        await self._dispatch(
            issue, attempt=retry.attempt, override_profile=retry.escalated_profile
        )

    def _fetch_running_states(self, by_project: dict) -> dict[str, Issue]:
        """Fetch current states for running issues (blocking, runs in thread).

        Parallelizes across projects; each project's tracker already
        parallelizes individual tracker detail calls internally.
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
                        project_id=entry.issue.project_id if entry.issue else None,
                        context_entry=entry,
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
        terminal_norms = _terminal_state_keys(self.config.tracker_terminal_states)
        active_norms = _dispatch_active_state_keys(self.config.tracker_active_states)

        for issue_id in running_ids:
            if issue_id not in self.state.running:
                continue
            issue = refreshed_map.get(issue_id)
            if not issue:
                continue

            state_norm = _state_key(issue.state)
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
                running_entry = self.state.running.get(issue_id)
                repair_status = canonicalize_status(issue.state)
                if (
                    running_entry
                    and repair_status in {IN_REVIEW, NEEDS_CI_FIX, NEEDS_REBASE}
                    and self._is_epic_review_repair_issue(issue)
                ):
                    logger.info(
                        "Reconcile: preserving active epic repair issue_id=%s state=%s",
                        issue_id,
                        issue.state,
                    )
                    try:
                        project_id = issue.project_id or (
                            running_entry.issue.project_id
                            if running_entry.issue
                            else None
                        )
                        tracker = (
                            self._tracker_for_project(project_id)
                            if project_id
                            else self.tracker
                        )
                        tracker.update_issue(issue.identifier, status=IN_PROGRESS)
                        issue.state = IN_PROGRESS
                    except Exception as exc:  # noqa: BLE001 - keep the repair alive
                        logger.warning(
                            "Failed to restore in-progress state for epic repair %s: %s",
                            issue.identifier,
                            exc,
                        )
                    self.state.running[issue_id].issue = issue
                    continue
                # Moved out of in_progress (to open, deferred, etc.) — stop agent
                logger.warning(
                    "Reconcile: no longer in_progress issue_id=%s state=%s — terminating agent",
                    issue_id,
                    issue.state,
                )
                await self._terminate_running(issue_id, cleanup_workspace=False)
                # If state reverted to an active state (e.g. open), mark as claimed
                # with a cooldown to prevent immediate re-dispatch loops
                if state_norm in active_norms and running_entry:
                    reopen_count = self.state.reopen_counts.get(issue_id, 0) + 1
                    self.state.reopen_counts[issue_id] = reopen_count
                    if reopen_count >= 3:
                        logger.warning(
                            "Reconcile: issue %s reverted to %s %d times — marking completed to stop loop",
                            running_entry.identifier,
                            state_norm,
                            reopen_count,
                        )
                        self.state.completed.add(issue_id)
                    else:
                        delay = self._backoff_delay(reopen_count)
                        logger.info(
                            "Reconcile: scheduling retry for %s in %dms (%d/3)",
                            running_entry.identifier,
                            delay,
                            reopen_count,
                        )
                        self._schedule_retry(
                            issue_id,
                            attempt=reopen_count,
                            identifier=running_entry.identifier,
                            delay_ms=delay,
                            error=f"state reverted to {state_norm}",
                            project_id=running_entry.issue.project_id
                            if running_entry.issue
                            else None,
                            context_entry=running_entry,
                        )

    _ARCHIVE_DAYS = 7
    # _auto_archive only acts on issues closed >= _ARCHIVE_DAYS ago — a set
    # that changes at most once a day — yet each run does a full-corpus task
    # read per project. Run it at most this often instead of every tick.
    _AUTO_ARCHIVE_INTERVAL_S = 3600.0  # 1 hour
    # merged-label sweeps (_label_merged_issues, _label_merged_epics) and stale
    # In Review reconciliation use the cached forge state populated by
    # _handle_review_check — they are cheap reads but should still be
    # rate-limited to avoid hammering the tracker on every tick.
    _MERGED_LABELS_INTERVAL_S = 60.0  # 1 minute
    # Release-pick reconciliation also does full-corpus tracker scans and SCM
    # checks, but it needs separate observability from merged-label sweeps.
    _RELEASE_PICKS_INTERVAL_S = 60.0  # 1 minute

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
                issue.identifier,
                suggestion.suggested_name,
                suggestion.suggested_role,
            )

    def _auto_archive(self) -> None:
        """Archive closed issues older than _ARCHIVE_DAYS days.

        Delegates to the maintenance lane scheduling gate (:meth:`_run_maintenance_job`)
        so the job participates in in-flight coalescing, interval throttling, skip
        accounting, and observability alongside all other maintenance jobs.

        The actual work is in :meth:`_do_auto_archive`.
        """
        self._run_maintenance_job(
            "auto_archive",
            self._do_auto_archive,
            min_interval_s=self._AUTO_ARCHIVE_INTERVAL_S,
        )
        # Back-fill _last_auto_archive_monotonic for legacy callers that read it directly.
        state = self._maintenance_jobs.get("auto_archive")
        if state and state.last_run_monotonic is not None:
            self._last_auto_archive_monotonic = state.last_run_monotonic

    def _do_auto_archive(self) -> None:
        """Inner body of _auto_archive; called with the maintenance gate held."""
        now = datetime.now(timezone.utc)
        limit = getattr(self.config, "auto_archive_batch_size", 25)
        projects = self.project_store.list_all()
        # Only scan states that can still transition to archived. Including
        # ARCHIVED would re-read every already-archived issue each run just
        # to skip it via is_archived().
        archive_scan_states = [
            s
            for s in self.config.tracker_terminal_states
            if canonicalize_status(s) != ARCHIVED
        ]

        trackers: list[tuple[str | None, TrackerProtocol]] = []
        if projects:
            for project in projects:
                try:
                    trackers.append((project.id, self._tracker_for_project(project.id)))
                except (ProjectError, TrackerError):
                    pass
        else:
            trackers.append((None, self.tracker))

        archived = 0
        scanned = 0
        last_key = getattr(self, "_maintenance_cursors", {}).get("auto_archive")
        seen_cursor = last_key is None
        last_processed_key = last_key
        for pid, tracker in trackers:
            try:
                closed = tracker.fetch_issues_by_states(archive_scan_states)
                for issue in closed:
                    issue_key = f"{pid or 'legacy'}:{issue.identifier}"
                    if not seen_cursor:
                        seen_cursor = issue_key == last_key
                        continue
                    scanned += 1
                    if tracker.is_archived(issue):
                        continue
                    if (
                        issue.closed_at
                        and (now - issue.closed_at).days >= self._ARCHIVE_DAYS
                    ):
                        if archived >= limit:
                            self._set_maintenance_cursor(
                                "auto_archive", last_processed_key
                            )
                            self._maintenance_status["auto_archive"] = {
                                "last_run_at": datetime.now(timezone.utc).isoformat(),
                                "archived": archived,
                                "scanned": scanned,
                                "limit": limit,
                                "deferred": True,
                                "cursor": last_processed_key,
                            }
                            return
                        try:
                            tracker.archive_issue(issue.identifier)
                            archived += 1
                            logger.info(
                                "Auto-archived issue %s (closed %d days ago)",
                                issue.identifier,
                                (now - issue.closed_at).days,
                            )
                        except TrackerError as exc:
                            logger.debug(
                                "Failed to archive %s: %s", issue.identifier, exc
                            )
                    last_processed_key = issue_key
            except (TrackerError, ProjectError) as exc:
                logger.debug("Auto-archive fetch failed for project %s: %s", pid, exc)
        self._set_maintenance_cursor("auto_archive", None)
        self._maintenance_status["auto_archive"] = {
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "archived": archived,
            "scanned": scanned,
            "limit": limit,
            "deferred": False,
            "cursor": None,
        }

    async def _terminate_running(self, issue_id: str, cleanup_workspace: bool) -> None:
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
        # in task comments. Exit reason is "terminated" to
        # distinguish from natural exits. See task oompah-zlz_2-y3fy.
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

    def _tracker_read_stats_snapshot(self) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        if hasattr(self.tracker, "read_stats"):
            try:
                stats["legacy"] = self.tracker.read_stats()
            except Exception:  # noqa: BLE001
                pass
        for project_id, tracker in getattr(self, "_project_trackers", {}).items():
            if not hasattr(tracker, "read_stats"):
                continue
            try:
                stats[str(project_id)] = tracker.read_stats()
            except Exception:  # noqa: BLE001
                continue
        return stats

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
                # AC #2 (TASK-461.2): include tracker identity so operators
                # can see which backend owns each running task.
                "tracker_kind": entry.issue.tracker_kind if entry.issue else None,
                "started_at": entry.started_at.isoformat(),
                "agent_profile": entry.agent_profile_name,
                "focus_name": entry.focus_name,
                "focus_role": entry.focus_role,
                "provider_name": entry.provider_name,
                "model_name": entry.model_name,
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
            due_dt = datetime.fromtimestamp(retry.due_at_ms / 1000.0, tz=timezone.utc)
            retry_rows.append(
                {
                    "issue_id": issue_id,
                    "issue_identifier": retry.identifier,
                    "attempt": retry.attempt,
                    "due_at": due_dt.isoformat(),
                    "error": retry.error,
                    "project_id": retry.project_id,
                    "agent_profile": retry.agent_profile_name,
                    "model_role": retry.model_role,
                    "provider_id": retry.provider_id,
                    "provider": retry.provider_name,
                    "model": retry.model_name,
                    "candidate_key": retry.candidate_key,
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
                    "provider_id": p.provider_id
                    or (dp.id if (dp := self.provider_store.get_default()) else None),
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
                self.config,
                "agent_profiles_source",
                "json",
            ),
            "rate_limits": self.state.rate_limits,
            "projects": [p.to_safe_dict() for p in self.project_store.list_all()],
            "open_reviews_by_project": {
                pid: self._count_open_reviews(pid)
                for pid in (getattr(self, "_reviews_cache", None) or {})
            },
            "alerts": list(self._alerts) + self._credential_error_alerts(),
            "reviews_summary": self._reviews_summary(),
            "orchestrator_metrics": {
                "last_tick": dict(getattr(self, "_last_tick_metrics", {}) or {}),
                "last_dispatch": dict(
                    getattr(self, "_last_dispatch_metrics", {}) or {}
                ),
                "maintenance": dict(
                    getattr(self, "_maintenance_status", {}) or {}
                ),
                # Per-project, per-operation refresh timing and timeout counts.
                # Operators can use this to identify which project or operation
                # is causing slow ticks. Each entry has:
                #   last_duration_ms  — wall-clock time for the last attempt
                #   success_count     — total successful refreshes since start
                #   timeout_count     — total timeouts (stale data was used)
                #   last_error        — error string from the most recent failure
                # A high timeout_count for a project's "candidates" operation
                # means that project's tracker is consistently slow and oompah
                # is falling back to cached data. See docs/tick-latency-diagnostics.md.
                "project_refresh": {
                    pid: dict(ops)
                    for pid, ops in (
                        getattr(self, "_project_refresh_metrics", {}) or {}
                    ).items()
                },
                "tracker_reads": self._tracker_read_stats_snapshot(),
                "ipc": (
                    self._ipc.diagnostics()
                    if self._ipc is not None
                    else None
                ),
            },
            "epic_rebase_states": {
                epic_id: {
                    "state": entry.state,
                    "updated_at": entry.updated_at,
                    "project_id": entry.project_id,
                }
                for epic_id, entry in self._epic_rebase_states.items()
            },
            "proposed_foci_count": self._proposed_foci_count(),
            # Maintenance lane job status (TASK-466.1 / TASK-466.4).
            # Populated by _maybe_heal_repos() and the unified
            # _run_maintenance_job() gate.  The top-level keys preserve the
            # TASK-466.1 heal/cleanup fields for backward compatibility;
            # "jobs" carries per-job scheduling state (TASK-466.4) so
            # operators can diagnose skipped, running, failed, and completed
            # jobs without reading logs.
            "maintenance": {
                "last_heal_at": self._last_heal_at if self._last_heal_at != 0.0 else None,
                "heal_error": self._heal_error_last,
                "last_cleanup_at": self._last_cleanup_at if self._last_cleanup_at != 0.0 else None,
                "cleanup_count": self._cleanup_count_last,
                "cleanup_error": self._cleanup_error_last,
                "jobs": {
                    name: {
                        "status": state.last_status,
                        "in_flight": state.in_flight,
                        "run_count": state.run_count,
                        "skip_count": state.skip_count,
                        "last_run_monotonic": state.last_run_monotonic,
                        "next_run_monotonic": state.next_run_monotonic,
                        "last_duration_s": state.last_duration_s,
                        "last_error": state.last_error,
                    }
                    for name, state in self._maintenance_jobs.items()
                },
            },
            # Fine-grained tick telemetry (TASK-465.1).  Empty dict until the
            # first tick completes.  Top-level keys are phase timings in ms;
            # "dispatch_substeps" contains per-substep breakdowns.  No secrets
            # are stored here — only numeric timing data.
            "tick_timings": dict(self._last_tick_timings),
        }

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
        yolo_ids = {
            p.id for p in self.project_store.list_all() if getattr(p, "yolo", False)
        }
        total = 0
        yolo_pending = 0
        queued = 0
        conflicts = 0
        ci_failures = 0
        unavailable_runners = 0
        for project_id, reviews in reviews_cache.items():
            for r in reviews or []:
                # Skip reviews where an agent is currently working — handled elsewhere.
                if getattr(r, "agent_active", False):
                    continue
                total += 1
                unavailable_runners += sum(
                    1
                    for warning in (getattr(r, "ci_warnings", []) or [])
                    if isinstance(warning, dict)
                    and warning.get("type") == "unavailable_runner"
                )
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
            "unavailable_runners": unavailable_runners,
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

        When the IPC layer is active (multi-process mode), also publishes the
        state snapshot to the shared SQLite database so the API process can
        serve cached reads without blocking on this process's GIL.
        """
        snapshot = self.get_snapshot()
        # Publish to IPC before notifying local observers so the API process
        # can serve reads as soon as the tick completes.
        if self._ipc is not None:
            try:
                self._ipc.publish_state(snapshot)
            except Exception as exc:  # noqa: BLE001
                logger.debug("OrchestratorIPC.publish_state failed (non-fatal): %s", exc)
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
