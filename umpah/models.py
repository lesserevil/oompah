"""Domain models for umpah."""

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
class AgentTotals:
    """Aggregate token counts and runtime."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    seconds_running: float = 0.0


@dataclass
class RunningEntry:
    """Tracked state for a running worker."""

    worker_task: Any
    identifier: str
    issue: Issue
    session: LiveSession | None
    retry_attempt: int
    started_at: datetime


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
    rate_limits: dict | None = None
