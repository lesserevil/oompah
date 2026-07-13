"""Domain models for oompah."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Epic rebase outcome states (oompah-zlz_2-82dr.3)
#
# Tracks whether an epic branch has been detected as stale, is currently
# being rebased, or has been successfully rebased onto main. Persisted
# as labels on the epic task (epic:stale, epic:rebasing, epic:rebased)
# AND in-memory via the Orchestrator._epic_rebase_states dict so the
# dispatch loop can skip redundant rebase agent dispatches.
# ---------------------------------------------------------------------------


class EpicRebaseState(str, Enum):
    """Possible outcomes of a proactive rebase for an epic branch."""

    STALE = "stale"              # Branch detected as behind main
    REBASING = "rebasing"       # Rebase agent dispatched / in progress
    REBASED = "rebased"         # Rebase succeeded, branch updated
    FAILED = "failed"           # Rebase failed (conflict, network, etc.)

    @property
    def label(self) -> str:
        """The issue label representing this state (e.g. 'epic:stale')."""
        return f"epic:{self.value}"

    @classmethod
    def from_label(cls, label: str) -> "EpicRebaseState | None":
        """Parse a label like 'epic:stale' back to the enum, or None."""
        if label.startswith("epic:"):
            try:
                return cls(label[len("epic:"):])
            except ValueError:
                return None
        return None


@dataclass
class EpicRebaseStateEntry:
    """Per-epic rebase state tracked by the orchestrator.

    Kept in-memory in ``Orchestrator._epic_rebase_states`` and persisted
    to ``service_state.json`` so restart doesn't lose rebase progress.
    """

    state: str  # EpicRebaseState.value
    updated_at: float  # epoch seconds
    project_id: str | None = None
    retry_count: int = 0  # number of failed attempts (for exponential backoff)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "state": self.state,
            "updated_at": self.updated_at,
            "project_id": self.project_id,
        }
        if self.retry_count:
            d["retry_count"] = self.retry_count
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EpicRebaseStateEntry":
        return cls(
            state=str(d.get("state", "")),
            updated_at=float(d.get("updated_at", 0) or 0),
            project_id=d.get("project_id") or None,
            retry_count=int(d.get("retry_count", 0) or 0),
        )


@dataclass
class BlockerRef:
    """Reference to an issue that blocks another."""

    id: str | None = None
    identifier: str | None = None
    state: str | None = None


@dataclass
class Issue:
    """Normalized issue record used by orchestration, prompt rendering, and observability."""

    id: str
    identifier: str
    title: str
    description: str | None = None
    priority: int | None = None
    state: str = ""
    branch_name: str | None = None
    # Target branch for this issue's work. When None, uses project's default_branch.
    # This allows issues to target branches other than the project default (e.g.,
    # release/*, hotfix/*, or epic branches in stacked mode).
    target_branch: str | None = None
    # Raw release-pick metadata mirrored from tracker storage. These keep
    # maintenance passes from rereading every task after fetch_all_issues().
    backports: Any | None = None
    backport_of: Any | None = None
    release_pick_metadata_loaded: bool = False
    url: str | None = None
    issue_type: str = "task"
    parent_id: str | None = None
    project_id: str | None = None
    labels: list[str] = field(default_factory=list)
    blocked_by: list[BlockerRef] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
    # Repo-relative attachment paths (e.g.
    # ".oompah/attachments/<identifier>/<sha>-<name>.png"). Parsed from
    # tracker metadata["oompah.attachments"]; the rich record (mime, size,
    # generated, added_by, ...) lives in the metadata block. The list
    # here carries just paths so prompt rendering and dispatch can ignore
    # the metadata structure.
    attachments: list[str] = field(default_factory=list)
    # Raw intake-readiness metadata (oompah.intake). The dashboard turns this
    # into a compact intake_summary without requiring tracker-specific reads.
    intake: dict[str, Any] | None = None
    # Explicit work branch stored in tracker metadata (oompah.work_branch).
    # Populated for GitHub-backed tasks from the hidden body metadata block.
    # When set, branch-to-issue resolution uses this value instead of
    # deriving the branch from the identifier.
    work_branch: str | None = None
    tracker_kind: str | None = None
    tracker_owner: str | None = None
    tracker_repo: str | None = None
    issue_number: str | None = None
    display_identifier: str | None = None
    provider_url: str | None = None
    review_url: str | None = None
    review_number: str | None = None
    # GitHub login of the issue creator/requestor when supplied by the tracker.
    requestor_login: str | None = None
    # Managed code repository for this issue (e.g. "lesserevil/trickle").
    # Set by the tracker adapter for GitHub-backed issues.
    managed_repo: str | None = None
    # Branch created for the agent to work on this issue.
    # Stored in GitHub issue metadata so review reconciliation can resolve
    # the task from the PR without guessing by task ID.
    work_branch: str | None = None


@dataclass
class WorkflowDefinition:
    """Parsed WORKFLOW.md payload."""

    config: dict[str, Any]
    prompt_template: str


@dataclass
class Workspace:
    """Filesystem workspace assigned to one issue identifier."""

    path: str
    workspace_key: str
    created_now: bool


@dataclass
class RunAttempt:
    """One execution attempt for one issue."""

    issue_id: str
    issue_identifier: str
    attempt: int | None
    workspace_path: str
    started_at: datetime
    status: str
    error: str | None = None


@dataclass
class LiveSession:
    """State tracked while a coding-agent subprocess is running."""

    session_id: str
    thread_id: str
    turn_id: str
    agent_pid: str | None = None
    last_event: str | None = None
    last_timestamp: datetime | None = None
    last_message: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    last_reported_input_tokens: int = 0
    last_reported_output_tokens: int = 0
    last_reported_total_tokens: int = 0
    turn_count: int = 0
    # Optional SDK-reported total cost for this session in USD. Set
    # by _run_acp_worker for per-token-billed ACP providers when the
    # SDK's ResultMessage.total_cost_usd is non-None — the SDK knows
    # tier discounts oompah doesn't, so when present this beats the
    # local model_costs lookup. None means "fall back to model_costs"
    # (or "no cost" for subscription/api/cli paths). See issue
    # oompah-zlz_2-ag7h.
    sdk_cost_usd: float | None = None


@dataclass
class RetryEntry:
    """Scheduled retry state for an issue."""

    issue_id: str
    identifier: str
    attempt: int
    due_at_ms: float
    timer_handle: Any = None
    error: str | None = None
    escalated_profile: str | None = None
    project_id: str | None = None
    agent_profile_name: str | None = None
    model_role: str | None = None
    provider_id: str | None = None
    provider_name: str | None = None
    model_name: str | None = None
    candidate_key: str | None = None


@dataclass
class Project:
    """A managed git repo with tracker-backed work."""

    id: str
    name: str
    repo_url: str
    repo_path: str  # local clone path (derived)
    # Legacy single branch field (deprecated, kept for backward compatibility).
    # Use branches and default_branch instead.
    branch: str = "main"
    # List of branch patterns that can be targets of tasks. Supports glob
    # patterns like "main", "release/*", "hotfix/*". The first entry is
    # treated as the default if default_branch is not explicitly set.
    branches: list[str] = field(default_factory=lambda: ["main"])
    # Default branch for new tasks. Defaults to the first entry in branches,
    # or "main" if branches is empty.
    default_branch: str = "main"
    git_user_name: str | None = None
    git_user_email: str | None = None
    yolo: bool = False
    log_path: str | None = None  # optional path to a log file to watch for errors
    webhook_secret: str | None = None  # HMAC secret for validating forge webhooks
    # Optional GitHub/GitLab API token used by SCM operations (list/rebase/merge
    # PRs and MRs). When None, the SCM provider falls back to env vars
    # (GH_TOKEN/GITHUB_TOKEN, GITLAB_TOKEN) and then to the gh/glab CLI auth.
    access_token: str | None = None
    # True when `git lfs install` succeeded for this clone. When False, the
    # attachments feature is silently disabled for this project.
    lfs_available: bool = False
    # UTC timestamp of the most recent successful webhook delivery for this
    # project, updated every time a forge webhook (GitHub/GitLab) is received.
    last_webhook_received_at: datetime | None = None
    # When False, do not launch gh-webhook forwarding for this project. Some
    # GitHub repos allow issue/PR automation but do not grant repo-hook admin
    # permission to the project token; those projects intentionally rely on
    # polling instead of surfacing a repeated forwarder failure.
    webhook_forwarding_enabled: bool = True
    # Maximum number of concurrent open (non-draft) PRs/MRs allowed for this
    # project before new review handoffs are deferred. Dispatch can continue
    # while this limit is full. Default 1 preserves the original
    # single-review-handoff behavior. Raise per-project once GitHub Merge
    # Queue is enabled and verified for that repo.
    max_in_flight_prs: int = 1
    # When True, YOLO auto-merge calls enable_auto_merge (GitHub merge queue)
    # instead of directly merging the PR.  Default False preserves today's
    # direct-merge behaviour.
    merge_queue_enabled: bool = False
    # Per-project pause flag. When True, the orchestrator's _should_dispatch
    # rejects every issue belonging to this project with reason
    # "project_paused" — same idiom as the global pause but scoped to one
    # repo. Composes with the global pause: a request is dispatchable only
    # if neither the global nor the project's pause is set.
    paused: bool = False
    # Per-project pre-push verification command. When set, agents (especially
    # the merge_conflict focus) run this exact command instead of inferring a
    # test target from repo layout. Example: "cargo test --workspace --lib"
    # for a Rust workspace where --workspace alone would pull in flaky
    # platform-specific or network-dependent crates.  When None/empty, the
    # agent falls back to its prior best-guess inference.
    test_command: str | None = None
    # Optional broader pre-merge-queue verification command. Used when an
    # agent wants more coverage than test_command before a final push (e.g.
    # integration tests). When None/empty, agents only see test_command.
    test_command_full: str | None = None
    # Optional glob-style paths to exclude from testing (e.g. flaky,
    # hardware-dependent, or network-dependent suites). Surfaced to agents
    # as a hint; agents are responsible for honoring it. Empty list = no
    # exclusions.
    test_skip_paths: list[str] = field(default_factory=list)
    # Per-project strategy controlling how children of an epic relate to
    # branches and CI.  "shared" is the only supported value: each epic gets
    # ONE shared worktree and ONE shared branch; child tasks commit directly
    # to the epic branch (no per-child PRs, no per-child CI).  Children
    # dispatch SERIALLY within an epic (one agent at a time per epic
    # worktree); multiple epics still dispatch concurrently up to
    # ``max_in_flight_prs``.
    #
    # Legacy persisted values "flat" and "stacked" are transparently
    # normalized to "shared" at load time (see from_dict).  Unknown or
    # invalid values are also normalized to "shared".
    epic_strategy: str = "shared"
    # When true, ordinary implementation tasks must be attached to an epic
    # before dispatch/review automation can act on them. This is stricter
    # than epic_strategy: shared/stacked, which only changes behavior once a
    # parent epic exists.
    require_epic_for_tasks: bool = False
    # When true, a Proposed GitHub issue that satisfies intake readiness is
    # promoted to Backlog as soon as validation records a pass. When false, a
    # project owner must explicitly move the issue to Backlog.
    intake_auto_promote: bool = True

    churn_magnet_gate_enabled: bool = False
    churn_magnet_top_n: int = 10
    # Per-project provider whitelist. When empty (the default), all providers
    # allowed by role assignment settings are eligible for this project.
    # When set to one or more provider *names*, dispatch filters role
    # candidates to only those providers before applying priority or
    # round-robin selection. This is provider-level filtering only;
    # model-level role rules and provider health/failover still apply
    # after the whitelist filter. See TASK-407.10.
    provider_whitelist: list[str] = field(default_factory=list)
    # GitHub login oompah uses as the project-owner actor for protected status
    # transitions.  By default this is resolved from the configured project
    # access token owner.  Operators may override it when the token owner cannot
    # be resolved or a different service account should represent the project.
    status_actor_login: str | None = None
    # Additional GitHub logins authorized to apply or remove
    # ``oompah:status:*`` labels on issues in this project.  The oompah bot
    # login and ``status_actor_login`` are implicitly authorized and do not need
    # to be listed here.  All comparisons are case-insensitive.
    status_label_authorized_logins: list[str] = field(default_factory=list)

    # ---------------------------------------------------------------------------
    # Per-project tracker configuration.
    # ---------------------------------------------------------------------------
    # Which tracker backend this project uses. When None, falls back to the
    # global ServiceConfig.tracker_kind. Recognized values are the keys in
    # oompah.tracker.ADAPTER_REGISTRY plus aliases like "oompah".
    # Use "oompah_md" for native Markdown task files or
    # "github_issues" for GitHub-backed projects.
    tracker_kind: str | None = None
    # GitHub Issues task hub owner/repo for this project. When set, new tasks
    # are created under <tracker_owner>/<tracker_repo> on GitHub.  Falls back
    # to global OOMPAH_GITHUB_TRACKER_OWNER / _REPO env vars when None.
    tracker_owner: str | None = None
    tracker_repo: str | None = None
    # For native Markdown projects, allow GitHub issues in tracker_owner/repo
    # to act as an external customer intake source. The internal Markdown task
    # remains authoritative after import.
    github_issue_intake_enabled: bool = False
    # GitHub Projects (v2) node ID for board/roadmap views. Optional — oompah
    # does not require a Project board to manage GitHub Issues.
    github_project_node_id: str | None = None

    def __post_init__(self):
        # Ensure branches is never empty and default_branch is set
        if not self.branches:
            self.branches = ["main"]
        if not self.default_branch:
            self.default_branch = self.branches[0]
        # Backward compatibility: if branch is set but branches only has default,
        # use branch as the primary branch
        if self.branch != "main" and self.branches == ["main"]:
            self.branches = [self.branch]
            self.default_branch = self.branch

    @property
    def primary_branch(self) -> str:
        """Return the primary/default branch for this project."""
        return self.default_branch

    def matches_branch(self, branch_name: str) -> bool:
        """Check if a branch name matches any of the tracked branch patterns."""
        import fnmatch

        for pattern in self.branches:
            if fnmatch.fnmatch(branch_name, pattern):
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "name": self.name,
            "repo_url": self.repo_url,
            "repo_path": self.repo_path,
            "branch": self.branch,
            "branches": list(self.branches),
            "default_branch": self.default_branch,
            "yolo": self.yolo,
            "lfs_available": self.lfs_available,
            "max_in_flight_prs": self.max_in_flight_prs,
            "merge_queue_enabled": self.merge_queue_enabled,
            "paused": self.paused,
            "webhook_forwarding_enabled": self.webhook_forwarding_enabled,
        }
        if self.git_user_name:
            d["git_user_name"] = self.git_user_name
        if self.git_user_email:
            d["git_user_email"] = self.git_user_email
        if self.log_path:
            d["log_path"] = self.log_path
        if self.webhook_secret:
            d["webhook_secret"] = self.webhook_secret
        if self.access_token:
            d["access_token"] = self.access_token
        if self.last_webhook_received_at:
            d["last_webhook_received_at"] = self.last_webhook_received_at.isoformat()
        if self.test_command:
            d["test_command"] = self.test_command
        if self.test_command_full:
            d["test_command_full"] = self.test_command_full
        if self.test_skip_paths:
            d["test_skip_paths"] = list(self.test_skip_paths)
        # Always emit epic_strategy so dashboards can render the current
        # mode without back-compat guessing.  "shared" is the only supported
        # value; always writing the field ensures legacy flat/stacked entries
        # are overwritten on the next save.
        d["epic_strategy"] = self.epic_strategy
        d["require_epic_for_tasks"] = self.require_epic_for_tasks
        d["intake_auto_promote"] = self.intake_auto_promote
        # Always emit churn-magnet gate config so dashboards can render
        # the settings and the orchestrator persists them across restarts.
        d["churn_magnet_gate_enabled"] = self.churn_magnet_gate_enabled
        d["churn_magnet_top_n"] = self.churn_magnet_top_n
        # Always emit provider_whitelist (even when empty) so the API
        # response consistently includes the field for dashboard rendering.
        d["provider_whitelist"] = list(self.provider_whitelist)
        if self.status_actor_login:
            d["status_actor_login"] = self.status_actor_login
        # Only emit status_label_authorized_logins when non-empty — most
        # projects rely on the default project status actor and don't need this field.
        if self.status_label_authorized_logins:
            d["status_label_authorized_logins"] = list(self.status_label_authorized_logins)
        # Per-project tracker configuration. Only emit when set to keep the
        # serialized dict compact for projects that haven't been cut over yet.
        if self.tracker_kind is not None:
            d["tracker_kind"] = self.tracker_kind
        if self.tracker_owner is not None:
            d["tracker_owner"] = self.tracker_owner
        if self.tracker_repo is not None:
            d["tracker_repo"] = self.tracker_repo
        d["github_issue_intake_enabled"] = self.github_issue_intake_enabled
        if self.github_project_node_id is not None:
            d["github_project_node_id"] = self.github_project_node_id
        return d

    def to_safe_dict(self) -> dict[str, Any]:
        """Return dict with secrets redacted for display / API responses.

        Removes ``access_token`` and ``webhook_secret`` from the returned dict
        so they are never surfaced through the state API or WebSocket
        broadcasts.  Presence-flags (``has_access_token``, ``has_webhook_secret``)
        are added so dashboards can indicate whether credentials are configured
        without exposing the values.
        """
        d = self.to_dict()
        token = d.pop("access_token", None)
        if token:
            d["access_token_masked"] = (
                token[:4] + "..." + token[-4:] if len(token) > 8 else "***"
            )
            d["has_access_token"] = True
        else:
            d["access_token_masked"] = ""
            d["has_access_token"] = False
        # Redact webhook_secret — the value must not appear in API responses.
        webhook_secret = d.pop("webhook_secret", None)
        d["has_webhook_secret"] = bool(webhook_secret)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Project:
        last_webhook_received_at: datetime | None = None
        raw = d.get("last_webhook_received_at")
        if raw:
            if isinstance(raw, datetime):
                last_webhook_received_at = raw
            else:
                try:
                    last_webhook_received_at = datetime.fromisoformat(str(raw))
                except (ValueError, TypeError):
                    pass
        raw_max = d.get("max_in_flight_prs", 1)
        try:
            max_in_flight_prs = max(1, int(raw_max))
        except (ValueError, TypeError):
            max_in_flight_prs = 1
        raw_skip = d.get("test_skip_paths") or []
        if isinstance(raw_skip, list):
            test_skip_paths = [str(p) for p in raw_skip if str(p).strip()]
        else:
            test_skip_paths = []
        raw_test_command = d.get("test_command")
        test_command = str(raw_test_command).strip() if raw_test_command else None
        raw_test_command_full = d.get("test_command_full")
        test_command_full = (
            str(raw_test_command_full).strip() if raw_test_command_full else None
        )
        # Migration: "flat" and "stacked" were legacy epic strategy values.
        # Normalize all persisted values (including unknown ones) to "shared",
        # the only supported strategy.  The normalized value is written back on
        # the next safe save, so the migration is restart-safe and requires no
        # separate script.
        epic_strategy = "shared"
        # Handle branches and default_branch with backward compatibility
        raw_branches = d.get("branches")
        if isinstance(raw_branches, list):
            branches = [str(b).strip() for b in raw_branches if str(b).strip()]
        else:
            # Backward compatibility: use legacy branch field
            branches = [str(d.get("branch", "main")).strip()]
        raw_default_branch = d.get("default_branch")
        if raw_default_branch:
            default_branch = str(raw_default_branch).strip()
        else:
            default_branch = branches[0] if branches else "main"
        raw_whitelist = d.get("provider_whitelist") or []
        if isinstance(raw_whitelist, list):
            provider_whitelist = [
                str(name).strip()
                for name in raw_whitelist
                if str(name).strip()
            ]
        else:
            provider_whitelist = []
        # Per-project tracker configuration
        raw_tracker_kind = d.get("tracker_kind")
        tracker_kind_proj: str | None = (
            str(raw_tracker_kind).strip() if raw_tracker_kind else None
        )
        raw_tracker_owner = d.get("tracker_owner")
        tracker_owner: str | None = (
            str(raw_tracker_owner).strip() if raw_tracker_owner else None
        ) or None
        raw_tracker_repo = d.get("tracker_repo")
        tracker_repo: str | None = (
            str(raw_tracker_repo).strip() if raw_tracker_repo else None
        ) or None
        raw_github_node = d.get("github_project_node_id")
        github_project_node_id: str | None = (
            str(raw_github_node).strip() if raw_github_node else None
        ) or None
        raw_status_actor_login = d.get("status_actor_login")
        status_actor_login: str | None = (
            str(raw_status_actor_login).strip() if raw_status_actor_login else None
        ) or None
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            repo_url=str(d.get("repo_url", "")),
            repo_path=str(d.get("repo_path", "")),
            branch=str(d.get("branch", "main")),
            branches=branches,
            default_branch=default_branch,
            git_user_name=d.get("git_user_name"),
            git_user_email=d.get("git_user_email"),
            yolo=bool(d.get("yolo", False)),
            log_path=d.get("log_path"),
            webhook_secret=d.get("webhook_secret"),
            access_token=d.get("access_token"),
            lfs_available=bool(d.get("lfs_available", False)),
            last_webhook_received_at=last_webhook_received_at,
            webhook_forwarding_enabled=bool(
                d.get("webhook_forwarding_enabled", True)
            ),
            max_in_flight_prs=max_in_flight_prs,
            merge_queue_enabled=bool(d.get("merge_queue_enabled", False)),
            paused=bool(d.get("paused", False)),
            test_command=test_command or None,
            test_command_full=test_command_full or None,
            test_skip_paths=test_skip_paths,
            epic_strategy=epic_strategy,
            require_epic_for_tasks=bool(d.get("require_epic_for_tasks", False)),
            intake_auto_promote=bool(d.get("intake_auto_promote", True)),
            churn_magnet_gate_enabled=bool(d.get("churn_magnet_gate_enabled", False)),
            churn_magnet_top_n=max(1, int(d.get("churn_magnet_top_n", 10))),
            provider_whitelist=provider_whitelist,
            status_actor_login=status_actor_login,
            status_label_authorized_logins=[
                str(login).strip()
                for login in (d.get("status_label_authorized_logins") or [])
                if str(login).strip()
            ],
            tracker_kind=tracker_kind_proj,
            tracker_owner=tracker_owner,
            tracker_repo=tracker_repo,
            github_issue_intake_enabled=bool(
                d.get("github_issue_intake_enabled", False)
            ),
            github_project_node_id=github_project_node_id,
        )


@dataclass
class ModelProvider:
    """An API endpoint for model inference (OpenAI-compatible)."""

    id: str
    name: str
    base_url: str
    api_key: str = ""
    models: list[str] = field(default_factory=list)
    default_model: str | None = None
    # provider_type collapses to exactly two canonical values:
    #   * "openai_compatible" — anything speaking the OpenAI chat-completions
    #     wire format (OpenAI, vLLM, custom proxies, Anthropic-via-OAI-proxy)
    #   * "acp" — sessions driven through a registered ACP backend (the
    #     Claude Agent SDK today; future Codex etc. via oompah-zlz_2-0hzh).
    # Legacy values ("openai", "anthropic", "custom") are migrated at load
    # time by ``from_dict`` so existing providers.json records keep working
    # without operator action. See issue oompah-zlz_2-zvm0 for the rationale.
    provider_type: str = "openai_compatible"
    model_roles: dict[str, str] = field(default_factory=dict)
    model_costs: dict[str, dict[str, float]] = field(default_factory=dict)
    # Per-model modality capability map. Keys are model names (matching
    # entries in ``models``); values list supported modalities, e.g.
    # ``{"gpt-4o-mini": ["text", "image"]}``. When a model is unset,
    # callers should default to ``["text"]``. See
    # plans/multimodal-attachments.md§Provider modality capability.
    model_capabilities: dict[str, list[str]] = field(default_factory=dict)
    # Per-model maximum total context window (input + output) in tokens.
    # When set, the API agent estimates the outgoing prompt size and
    # (a) prunes oldest history if the budget would overflow,
    # (b) clamps max_tokens to the remaining headroom.
    # When unset, the agent uses the legacy fixed max_tokens with no
    # pruning — only safe for models with very large windows.
    model_contexts: dict[str, int] = field(default_factory=dict)
    # ACP backend selector. When this provider is used by an agent
    # profile with mode=acp, ``backend`` picks which registered backend
    # (see oompah/acp_backends/registry.py) handles the session.
    # ``None`` defaults to ``"claude"`` for back-compat with providers
    # persisted before this field existed. Ignored for non-acp modes.
    # See issue oompah-zlz_2-0hzh for the multi-backend ACP epic.
    backend: str | None = None
    # Provider mode: "api" (default — OpenAI-compatible HTTP) or "acp"
    # (Claude Agent SDK; auth via operator's claude subscription).
    # ACP providers do not require base_url or api_key. Mirrors the
    # AgentProfile.mode field but at the provider granularity, so a
    # role-assignment matrix (child B of oompah-zlz_2-4a6) can dispatch
    # a model_role at this provider through the ACP path. See
    # docs/acp-agent.md and issue oompah-zlz_2-keb.
    mode: str = "api"
    # ACP-only: passed to ClaudeAgentOptions(permission_mode=...) when
    # mode == "acp". One of {"default", "acceptEdits", "plan",
    # "bypassPermissions"}. None falls through to "default".
    acp_permission_mode: str | None = None
    # ACP-only: marks the provider as billed via the operator's claude
    # subscription, not the per-token API meter. The orchestrator's
    # budget gate uses this to bypass the over-budget cap (mirrors the
    # AgentProfile.mode == "acp" carve-out).
    #
    # DEPRECATED — superseded by ``billing_model`` (oompah-zlz_2-ag7h),
    # which generalizes this binary flag to a labeled enum. Kept for
    # back-compat: existing provider records that set
    # acp_subscription_only=True still load fine, and the UI mirrors
    # the value into billing_model="subscription" so the budget gate
    # behaves identically. Prefer billing_model in new code.
    acp_subscription_only: bool = False
    # Billing model for this provider when used in mode=acp.
    # ``"subscription"`` (default) — calls are billed against the
    # operator's flat-rate subscription; the orchestrator bypasses
    # the budget gate and does NOT add cost to the rolling-window
    # spend tracker. This is the legacy behaviour for the Claude
    # Agent SDK path.
    # ``"per_token"`` — calls are metered per-token; the orchestrator
    # treats them like api-mode dispatches (budget gate enforced,
    # cost added to estimated_cost based on provider.model_costs OR
    # the SDK-reported total_cost_usd, whichever is available).
    # For mode != "acp" this field is ignored — api/cli/auto modes
    # always meter per-token via the existing api_agent path.
    # See issue oompah-zlz_2-ag7h.
    billing_model: str = "subscription"

    def get_model_costs(self, model: str) -> tuple[float, float]:
        """Return (cost_per_1k_input, cost_per_1k_output) for a model, or (0, 0) if unknown."""
        costs = self.model_costs.get(model, {})
        return (
            costs.get("cost_per_1k_input", 0.0),
            costs.get("cost_per_1k_output", 0.0),
        )

    def is_model_explicitly_free(self, model: str) -> bool:
        """True only when the model has an explicit model_costs entry whose
        input AND output costs are both 0. Models missing from model_costs
        are conservatively treated as paid (False) so a misconfigured
        provider doesn't accidentally bypass the budget cap."""
        if not model or model not in self.model_costs:
            return False
        entry = self.model_costs[model] or {}
        return (
            entry.get("cost_per_1k_input", -1) == 0
            and entry.get("cost_per_1k_output", -1) == 0
        )

    def get_model_context(self, model: str) -> int | None:
        """Return the configured max context window for ``model`` or None."""
        v = self.model_contexts.get(model)
        return int(v) if v else None

    def _reconcile_model_roles(self) -> list[str]:
        """Repoint model_roles entries that don't reference a model in self.models.

        Returns the list of role names that were re-pointed (empty if nothing changed).
        Used to keep the role dict in sync after model_list mutations.

        Behaviour:
          - models[] empty: leave roles as-is, emit WARNING for any roles
            pointing at missing models (ACP / SDK-managed scenario).
          - default_model is in models[]: use it as the fallback.
          - default_model is absent: use the first entry in models[].
          - Roles whose target is still in models[]: untouched.
        """
        if not self.model_roles:
            return []
        model_list = self.models or []
        if not model_list:
            # Empty catalog: preserve the roles verbatim (ACP scenario where
            # the SDK resolves models against its own catalog at dispatch time).
            dangling = [
                r for r, m in self.model_roles.items() if m not in (self.models or [])
            ]
            if dangling:
                logger.warning(
                    "Provider %s: empty models[] — %d role(s) left dangling: %s",
                    self.name,
                    len(dangling),
                    dangling,
                )
            return []
        # Determine the fallback: default_model if present in the catalog, else the
        # first entry in models[] (order-preserving — uses the list directly, not
        # a set, so iteration order is the operator-defined ordering).
        fallback = (
            self.default_model if self.default_model in model_list else model_list[0]
        )
        available = set(model_list)  # O(1) membership checks.
        changed: list[str] = []
        snapshot = list(self.model_roles.items())  # snapshot before mutation.
        for role, model in snapshot:
            if model not in available:
                self.model_roles[role] = fallback
                changed.append(role)
                logger.info(
                    "Provider %s: role=%s repointed from %r to %r (stale catalog)",
                    self.name,
                    role,
                    model,
                    fallback,
                )
        return changed

    def is_per_token_billed(self, mode: str) -> bool:
        """Whether dispatches through this provider in ``mode`` are
        per-token-metered (cost should be tracked against budget).

        * For ``mode == "acp"``: returns True iff
          ``billing_model == "per_token"``. Subscription-billed ACP
          providers return False and the orchestrator bypasses the
          budget gate / cost accumulator for them.
        * For any other mode (api/cli/auto): always True. The api_agent
          path is the canonical per-token meter; cli historically had
          no cost tracking but treating it as per-token here is a
          no-op (CLI workers don't roll through these helpers).

        Mirrors ``is_model_explicitly_free`` in spirit: a conservative
        helper used by the budget gate to decide whether a dispatch
        should consume the budget. See issue oompah-zlz_2-ag7h.
        """
        if mode == "acp":
            return self.billing_model == "per_token"
        return True

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "models": self.models,
            "default_model": self.default_model,
            "provider_type": self.provider_type,
        }
        if self.model_roles:
            d["model_roles"] = self.model_roles
        if self.model_costs:
            d["model_costs"] = self.model_costs
        if self.model_capabilities:
            d["model_capabilities"] = self.model_capabilities
        if self.model_contexts:
            d["model_contexts"] = self.model_contexts
        if self.backend:
            d["backend"] = self.backend
        # ACP-mode fields. mode is always emitted so downstream code
        # (and the dashboard) can rely on it being present; the ACP-
        # specific fields are only emitted when in ACP mode (or when
        # they have explicit non-default values) to keep the JSON
        # compact for the common API-mode case.
        d["mode"] = self.mode
        if self.acp_permission_mode is not None:
            d["acp_permission_mode"] = self.acp_permission_mode
        if self.acp_subscription_only:
            d["acp_subscription_only"] = self.acp_subscription_only
        # Always emit billing_model so dashboards / clients can render
        # the current billing mode without back-compat guessing. The
        # default value "subscription" is intentional — existing
        # ACP providers persisted before this field existed are
        # subscription-billed, matching prior orchestrator behaviour.
        d["billing_model"] = self.billing_model
        return d

    def to_safe_dict(self) -> dict[str, Any]:
        """Return dict with masked API key for display."""
        d = self.to_dict()
        if d["api_key"]:
            k = d["api_key"]
            d["api_key_masked"] = k[:8] + "..." + k[-4:] if len(k) > 12 else "***"
        else:
            d["api_key_masked"] = ""
        del d["api_key"]
        return d

    def validate_for_mode(self, mode: str) -> list[str]:
        """Validate the provider record for the given profile-mode context.

        Checks:

        * :attr:`backend` — when ``mode == "acp"`` it must resolve to a
          registered backend (defaults to ``"claude"`` when unset, for
          back-compat). For non-acp modes the backend field is ignored.
        * :attr:`billing_model` — must be one of
          ``{"subscription", "per_token"}`` when ``mode == "acp"``. For
          non-acp modes the billing_model is ignored (api/cli/auto are
          always per-token via the api_agent path).

        Returns a list of human-readable error strings; empty list
        means the provider is valid for the requested mode.
        """
        # Import inline to avoid a circular import at module load time:
        # oompah.acp_backends imports oompah.models for type hints.
        from oompah.acp_backends.registry import validate_provider_backend

        errors: list[str] = list(validate_provider_backend(self, mode))
        if mode == "acp":
            valid = {"subscription", "per_token"}
            if self.billing_model not in valid:
                errors.append(
                    f"Unknown billing_model: {self.billing_model!r}. "
                    f"Valid values: {sorted(valid)}."
                )
        return errors

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ModelProvider:
        # ----- provider_type migration (oompah-zlz_2-zvm0) -----
        # Collapse the legacy three-way dropdown ("openai", "anthropic",
        # "custom") to the canonical two-way split ("openai_compatible",
        # "acp"). All three legacy values denoted an OpenAI-compatible
        # HTTP endpoint — only the dropdown label differed — so they all
        # migrate forward to "openai_compatible". A persisted "acp"
        # value (set by the new dialog) round-trips unchanged.
        raw_ptype = (
            str(d.get("provider_type", "openai_compatible") or "").lower().strip()
        )
        if raw_ptype in ("openai", "anthropic", "custom", ""):
            provider_type = "openai_compatible"
        elif raw_ptype in ("openai_compatible", "acp"):
            provider_type = raw_ptype
        else:
            # Unknown future value — preserve verbatim. A separate
            # validate_for_mode() check will flag it if it's actually
            # used.
            provider_type = raw_ptype

        # Normalize mode: anything other than the two known values
        # falls back to "api" so a typo can't accidentally bypass the
        # budget gate. Mirrors the AgentProfile.mode validation.
        raw_mode = str(d.get("mode", "api") or "api").lower()
        mode = raw_mode if raw_mode in ("api", "acp") else "api"

        # ----- provider_type <-> mode reconciliation -----
        # The two fields are isomorphic: provider_type=="acp" iff mode=="acp".
        # If a persisted record disagrees (e.g. a hand-edited providers.json
        # set provider_type="acp" but left mode="api"), trust the field that
        # signals ACP — the budget-gate carve-out only fires when mode=="acp"
        # so the safer default is to honour any ACP signal in either field.
        if provider_type == "acp" or mode == "acp":
            provider_type = "acp"
            mode = "acp"
        else:
            provider_type = "openai_compatible"
            mode = "api"
        acp_perm_raw = d.get("acp_permission_mode")
        acp_permission_mode: str | None = (
            str(acp_perm_raw)
            if acp_perm_raw is not None and acp_perm_raw != ""
            else None
        )
        raw_backend = d.get("backend")
        backend = str(raw_backend).strip() if raw_backend else None
        # billing_model defaults to "subscription" so providers
        # persisted before this field existed (the legacy ACP path)
        # read back as subscription-billed — preserving today's
        # budget-bypass behaviour as the back-compat default.
        # Unknown values fall back to "subscription" so a typo in
        # providers.json doesn't silently start metering against
        # the budget without the operator noticing.
        raw_billing = d.get("billing_model", "subscription")
        billing_model = (
            str(raw_billing).strip().lower() if raw_billing else "subscription"
        )
        if billing_model not in ("subscription", "per_token"):
            billing_model = "subscription"
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            base_url=str(d.get("base_url", "")),
            api_key=str(d.get("api_key", "")),
            models=d.get("models", []),
            default_model=d.get("default_model"),
            provider_type=provider_type,
            model_roles=d.get("model_roles", {}),
            model_costs=d.get("model_costs", {}),
            model_capabilities={
                str(k): [str(c) for c in (v or [])]
                for k, v in (d.get("model_capabilities") or {}).items()
            },
            model_contexts={
                str(k): int(v)
                for k, v in (d.get("model_contexts") or {}).items()
                if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit())
            },
            mode=mode,
            acp_permission_mode=acp_permission_mode,
            acp_subscription_only=bool(d.get("acp_subscription_only", False)),
            backend=backend or None,
            billing_model=billing_model,
        )


@dataclass
class AgentProfile:
    """Defines an agent tier with its command and cost characteristics."""

    name: str
    command: str
    provider_id: str | None = None
    model: str | None = None
    model_role: str | None = None
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    max_turns: int | None = None
    keywords: list[str] = field(default_factory=list)
    issue_types: list[str] = field(default_factory=list)
    min_priority: int | None = None
    max_priority: int | None = None
    # Execution mode for this profile. Default is "auto": api if a
    # provider resolves else cli (today's behavior). Explicit values:
    # - "api"  forces the OpenAI-compatible chat completions path.
    # - "cli"  forces the legacy subprocess + native streaming-JSON path.
    # - "acp"  routes to ACP/Claude-Agent-SDK so calls bill against the
    #          operator's claude subscription instead of the per-token
    #          API meter. See plans/acp-agent.md / oompah-zlz_2-bcl.
    # Invalid values fall back to "auto" with a warning at config load.
    mode: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-friendly dict for AgentProfileStore.

        Mirrors WORKFLOW.md profile YAML keys 1:1 so a round-trip through
        the JSON store and back into ServiceConfig.from_workflow's profile
        loader (oompah/config.py) is byte-identical. Optional fields that
        are at their default value are omitted to keep stored JSON tidy.
        """
        d: dict[str, Any] = {
            "name": self.name,
            "command": self.command,
            "mode": self.mode,
        }
        if self.provider_id is not None:
            d["provider_id"] = self.provider_id
        if self.model is not None:
            d["model"] = self.model
        if self.model_role is not None:
            d["model_role"] = self.model_role
        if self.cost_per_1k_input:
            d["cost_per_1k_input"] = self.cost_per_1k_input
        if self.cost_per_1k_output:
            d["cost_per_1k_output"] = self.cost_per_1k_output
        if self.max_turns is not None:
            d["max_turns"] = self.max_turns
        if self.keywords:
            d["keywords"] = list(self.keywords)
        if self.issue_types:
            d["issue_types"] = list(self.issue_types)
        if self.min_priority is not None:
            d["min_priority"] = self.min_priority
        if self.max_priority is not None:
            d["max_priority"] = self.max_priority
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentProfile:
        """Construct an AgentProfile from its JSON dict.

        Permissive about types: integers/floats parsed leniently, missing
        keys fall back to the dataclass defaults. Mode validation happens
        in oompah.config._parse_profile_mode (called separately) — this
        constructor stores whatever value was on disk so callers can spot
        bad data and decide how to handle it. Unknown keys are ignored.
        """

        def _opt_int(v: Any) -> int | None:
            if v is None:
                return None
            try:
                return int(v)
            except (ValueError, TypeError):
                return None

        return cls(
            name=str(d.get("name", "")),
            command=str(d.get("command", "claude --dangerously-skip-permissions")),
            provider_id=(str(d["provider_id"]) if d.get("provider_id") else None),
            model=(str(d["model"]) if d.get("model") else None),
            model_role=(str(d["model_role"]) if d.get("model_role") else None),
            cost_per_1k_input=float(d.get("cost_per_1k_input", 0) or 0),
            cost_per_1k_output=float(d.get("cost_per_1k_output", 0) or 0),
            max_turns=_opt_int(d.get("max_turns")),
            keywords=[str(k) for k in (d.get("keywords") or [])],
            issue_types=[str(t) for t in (d.get("issue_types") or [])],
            min_priority=_opt_int(d.get("min_priority")),
            max_priority=_opt_int(d.get("max_priority")),
            mode=str(d.get("mode", "auto") or "auto"),
        )


@dataclass
class AgentTotals:
    """Aggregate token counts and runtime."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    seconds_running: float = 0.0
    estimated_cost: float = 0.0


@dataclass
class RunningEntry:
    """Tracked state for a running worker."""

    worker_task: Any
    identifier: str
    issue: Issue
    session: LiveSession | None
    retry_attempt: int
    started_at: datetime
    agent_profile_name: str = "default"
    focus_name: str = ""
    focus_role: str = ""
    activity_log: list[Any] = field(default_factory=list)
    # When default_first_dispatch is True, this stores the profile name that
    # _match_agent_profile() would have chosen for the issue, so the first
    # retry can jump straight to it instead of walking up from "default".
    # None means either the flag was off, or the issue was already on its
    # natural profile (retry path).
    natural_profile_name: str | None = None
    # Absolute path of the per-dispatch JSONL log this worker is
    # writing (api_agent / acp_agent / cli). Set by each worker when
    # the log file is opened so the per-agent telemetry comment
    # written at _on_worker_exit can reference it. None for legacy /
    # mid-startup state where the log path has not yet been resolved.
    # See issue oompah-zlz_2-y3fy.
    agent_log_path: str | None = None
    # Model role resolved for this dispatch (e.g. "fast", "deep").
    # Captured at worker startup so the telemetry comment can show
    # role + resolved (provider, model) without re-resolving at exit
    # time (the focus / role may have changed mid-run).
    model_role: str | None = None
    # Provider name resolved for this dispatch (informational, shown
    # in the telemetry comment). None means "no provider resolved"
    # (legacy CLI path / startup failures).
    provider_name: str | None = None
    # Model id resolved for this dispatch (informational, shown in
    # the telemetry comment). May be "unknown" for ACP runs using
    # the subscription default.
    model_name: str | None = None
    # Provider id / candidate key selected for this dispatch. These
    # are safe, non-secret identifiers used in telemetry and dashboard
    # warnings when provider startup fails.
    provider_id: str | None = None
    candidate_key: str | None = None
    # Absolute path to the workspace/worktree used for this dispatch.
    workspace_path: str | None = None


@dataclass
class OrchestratorState:
    """Single authoritative in-memory state owned by the orchestrator."""

    poll_interval_ms: int = 120000
    max_concurrent_agents: int = 10
    running: dict[str, RunningEntry] = field(default_factory=dict)
    claimed: set[str] = field(default_factory=set)
    retry_attempts: dict[str, RetryEntry] = field(default_factory=dict)
    completed: set[str] = field(default_factory=set)
    stall_counts: dict[str, int] = field(default_factory=dict)  # issue_id → stall count
    reopen_counts: dict[str, int] = field(
        default_factory=dict
    )  # issue_id → times agent completed without closing
    reject_streak: dict[str, tuple[str, int]] = field(
        default_factory=dict
    )  # issue_id → (reason, count)
    agent_totals: AgentTotals = field(default_factory=AgentTotals)
    cost_by_profile: dict[str, float] = field(default_factory=dict)
    decompose_attempts: dict[str, int] = field(
        default_factory=dict
    )  # issue_id → decomposition attempt count
    budget_exceeded: bool = False
    # Counter for dispatches that bypassed an over-budget gate because the
    # would-be model was explicitly $0/token. Reset whenever the budget
    # window rolls. Surfaced as `budget.free_tier_active` in the state
    # response so the dashboard can show "exceeded but still working on
    # free tier" rather than appearing dead.
    free_tier_dispatches_this_window: int = 0
    # Unix timestamp marking when the active budget window started.
    # Persisted to service_state.json so a restart inside the window
    # preserves spend rather than resetting to zero. <=0 means "not yet
    # initialized" — the next budget check will set it to now().
    budget_window_start: float = 0.0
    # The budget_window kind (hour/day/week) the persisted state was
    # written under. If config changes the kind, we treat that as a
    # fresh window rather than carrying spend forward into the new bucket.
    budget_window_kind: str = ""
    rate_limits: dict | None = None
