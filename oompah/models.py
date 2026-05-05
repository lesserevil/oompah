"""Domain models for oompah."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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
    # beads metadata["oompah.attachments"]; the rich record (mime, size,
    # generated, added_by, ...) lives in the metadata block. The list
    # here carries just paths so prompt rendering and dispatch can ignore
    # the metadata structure.
    attachments: list[str] = field(default_factory=list)


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


@dataclass
class Project:
    """A git repo with beads issue tracking."""

    id: str
    name: str
    repo_url: str
    repo_path: str  # local clone path (derived)
    branch: str = "main"
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
    # Maximum number of concurrent open (non-draft) PRs/MRs allowed for this
    # project before dispatch is held. Default 1 preserves the original
    # single-in-flight behavior. Raise per-project once GitHub Merge Queue
    # (Step 5) is enabled and verified for that repo.
    max_in_flight_prs: int = 1

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "name": self.name,
            "repo_url": self.repo_url,
            "repo_path": self.repo_path,
            "branch": self.branch,
            "yolo": self.yolo,
            "lfs_available": self.lfs_available,
            "max_in_flight_prs": self.max_in_flight_prs,
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
        return d

    def to_safe_dict(self) -> dict[str, Any]:
        """Return dict with the access token masked for display."""
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
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            repo_url=str(d.get("repo_url", "")),
            repo_path=str(d.get("repo_path", "")),
            branch=str(d.get("branch", "main")),
            git_user_name=d.get("git_user_name"),
            git_user_email=d.get("git_user_email"),
            yolo=bool(d.get("yolo", False)),
            log_path=d.get("log_path"),
            webhook_secret=d.get("webhook_secret"),
            access_token=d.get("access_token"),
            lfs_available=bool(d.get("lfs_available", False)),
            last_webhook_received_at=last_webhook_received_at,
            max_in_flight_prs=max_in_flight_prs,
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
    provider_type: str = "openai"  # openai | anthropic | custom
    model_roles: dict[str, str] = field(default_factory=dict)
    model_costs: dict[str, dict[str, float]] = field(default_factory=dict)
    # Per-model modality capability map. Keys are model names (matching
    # entries in ``models``); values list supported modalities, e.g.
    # ``{"gpt-4o-mini": ["text", "image"]}``. When a model is unset,
    # callers should default to ``["text"]``. See
    # docs/multimodal-attachments.md§Provider modality capability.
    model_capabilities: dict[str, list[str]] = field(default_factory=dict)
    # Per-model maximum total context window (input + output) in tokens.
    # When set, the API agent estimates the outgoing prompt size and
    # (a) prunes oldest history if the budget would overflow,
    # (b) clamps max_tokens to the remaining headroom.
    # When unset, the agent uses the legacy fixed max_tokens with no
    # pruning — only safe for models with very large windows.
    model_contexts: dict[str, int] = field(default_factory=dict)

    def get_model_costs(self, model: str) -> tuple[float, float]:
        """Return (cost_per_1k_input, cost_per_1k_output) for a model, or (0, 0) if unknown."""
        costs = self.model_costs.get(model, {})
        return (costs.get("cost_per_1k_input", 0.0), costs.get("cost_per_1k_output", 0.0))

    def is_model_explicitly_free(self, model: str) -> bool:
        """True only when the model has an explicit model_costs entry whose
        input AND output costs are both 0. Models missing from model_costs
        are conservatively treated as paid (False) so a misconfigured
        provider doesn't accidentally bypass the budget cap."""
        if not model or model not in self.model_costs:
            return False
        entry = self.model_costs[model] or {}
        return (entry.get("cost_per_1k_input", -1) == 0
                and entry.get("cost_per_1k_output", -1) == 0)

    def get_model_context(self, model: str) -> int | None:
        """Return the configured max context window for ``model`` or None."""
        v = self.model_contexts.get(model)
        return int(v) if v else None

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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ModelProvider:
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            base_url=str(d.get("base_url", "")),
            api_key=str(d.get("api_key", "")),
            models=d.get("models", []),
            default_model=d.get("default_model"),
            provider_type=str(d.get("provider_type", "openai")),
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
    reopen_counts: dict[str, int] = field(default_factory=dict)  # issue_id → times agent completed without closing
    reject_streak: dict[str, tuple[str, int]] = field(default_factory=dict)  # issue_id → (reason, count)
    agent_totals: AgentTotals = field(default_factory=AgentTotals)
    cost_by_profile: dict[str, float] = field(default_factory=dict)
    decompose_attempts: dict[str, int] = field(default_factory=dict)  # issue_id → decomposition attempt count
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
