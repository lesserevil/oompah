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
    labels: list[str] = field(default_factory=list)
    blocked_by: list[BlockerRef] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


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

    def get_model_costs(self, model: str) -> tuple[float, float]:
        """Return (cost_per_1k_input, cost_per_1k_output) for a model, or (0, 0) if unknown."""
        costs = self.model_costs.get(model, {})
        return (costs.get("cost_per_1k_input", 0.0), costs.get("cost_per_1k_output", 0.0))

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
    activity_log: list[Any] = field(default_factory=list)


@dataclass
class OrchestratorState:
    """Single authoritative in-memory state owned by the orchestrator."""

    poll_interval_ms: int = 30000
    max_concurrent_agents: int = 10
    running: dict[str, RunningEntry] = field(default_factory=dict)
    claimed: set[str] = field(default_factory=set)
    retry_attempts: dict[str, RetryEntry] = field(default_factory=dict)
    completed: set[str] = field(default_factory=set)
    agent_totals: AgentTotals = field(default_factory=AgentTotals)
    cost_by_profile: dict[str, float] = field(default_factory=dict)
    budget_exceeded: bool = False
    rate_limits: dict | None = None
