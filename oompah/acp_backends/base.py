"""ACP backend ABC + session protocol + typed event/options dataclasses.

The shapes here are intentionally minimal: one ABC, one Protocol, two
dataclasses. Concrete backends (claude.py, future codex.py, etc.)
implement :class:`AcpBackend` and yield a :class:`AcpBackendSession`
from ``start_session``. The session protocol is session-shaped because
both today's only proven backend (Claude Agent SDK) and the operator's
near-term need (Codex) are session-shaped — a single-shot adapter is a
future refinement.

Why a custom :class:`BackendEvent` instead of reusing
:class:`oompah.agent.AgentEvent`? AgentEvent is the orchestrator-side
audit log shape (carries ``agent_pid`` and an aggregate ``usage``
dict). BackendEvent is the backend-side "I just saw the SDK do X" type
— cleaner to keep them separate so a backend can be unit-tested
without dragging the orchestrator's event vocabulary along.
"""

from __future__ import annotations

import abc
import asyncio
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    Protocol,
    runtime_checkable,
)

if TYPE_CHECKING:
    # Avoid a runtime import cycle: models.py is loaded before this
    # module in many test paths, and base.py is loaded as part of
    # ``import oompah.acp_backends``. Use TYPE_CHECKING-only import so
    # the ABC reference type-checks without forcing the load order.
    from oompah.models import ModelProvider


# Default per-turn timeout, mirrored from the original AcpAgentSession.
# Kept here so backends share the same default rather than each picking
# their own.
DEFAULT_TURN_TIMEOUT_S = 3600.0


@dataclass
class BackendEvent:
    """Event yielded by an :class:`AcpBackendSession`'s ``run_turn``.

    The ``kind`` strings are backend-defined; today's ClaudeAcpBackend
    emits ``"session_start" | "text" | "thinking" | "tool_use" |
    "tool_result" | "permission_grant" | "permission_deny" |
    "assistant_error" | "session_error" | "turn_timeout" | "result"``.
    Consumers that want a UI-friendly stream should map each kind to
    the activity vocabulary the dashboard already renders (see
    ``oompah/orchestrator.py:_run_acp_worker``).

    ``payload`` mirrors the payloads ``AcpAgentSession._emit`` produced
    before this refactor — same keys, same truncation, just typed.
    """

    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class AcpBackendOptions:
    """Typed kwargs passed to :meth:`AcpBackend.start_session`.

    These mirror the historic :class:`oompah.acp_agent.AcpAgentSession`
    constructor kwargs so a backend can be a near-drop-in replacement
    for the inlined SDK logic. ``on_event`` is the audit callback the
    backend uses for direct event emission (e.g. permission decisions
    that fire from SDK callbacks outside the main run_turn loop).
    """

    workspace_path: str
    prompt: str
    model: str | None = None
    fallback_model: str | None = None
    max_turns: int | None = None
    env: dict[str, str] | None = None
    tool_catalog: list[Any] | None = None
    # Permission mode kept accessible through options (not buried inside
    # the Claude-specific path) so future backends honoring different
    # permission semantics can read the same field. Today's
    # ClaudeAcpBackend treats "default" as "strict allowlist of
    # mcp__oompah__*" (see plans/acp-agent.md and oompah-zlz_2-rls).
    permission_mode: str = "default"
    turn_timeout_s: float = DEFAULT_TURN_TIMEOUT_S
    # When set, the backend emits AgentEvents directly via this
    # callback in addition to yielding BackendEvents from run_turn().
    # Callers can pass ``None`` to suppress direct emission.
    on_event: Callable[[Any], None] | None = None
    # Billing tier of the originating provider, flowed first-class so a
    # backend can pick its execution path without sniffing env vars.
    # ``"per_token"`` (the default) means API-key billing; backends like
    # Codex route this to the in-process OpenAI-Agents SDK path.
    # ``"subscription"`` means the operator's OAuth/subscription login
    # (e.g. ``~/.codex/auth.json``); Codex routes it to the CLI
    # subprocess path that honors that login. The Claude backend ignores
    # this field (its SDK is always subscription-billed).
    billing_model: str = "per_token"
    # Non-HTTP project management (TASK-464.8): the ProjectStore instance
    # and the project_id for the task this session is executing.  Backends
    # pass these into the tool catalog so agents can call list_projects,
    # get_project/get_project_by_id, and update_project/update_project_by_id
    # without making deadlock-inducing HTTP self-calls to
    # the local oompah server.  Both default to None; tools degrade
    # gracefully (return an error string) when not supplied.
    project_store: Any = None
    project_id: str | None = None
    # Tracker for the task's managed project. ACP run_command uses this to
    # execute ``oompah task ...`` commands directly instead of spawning the
    # HTTP-backed CLI, which would self-call the local server process.
    task_tracker: Any = None
    # Optional asyncio.Queue for mid-run comment injection (OOMPAH-211).
    # When set, the backend drains this queue at each turn boundary and
    # sends any pending text as a new user turn in the same session.
    # put_nowait()-safe from the async event loop thread.
    # None = injection disabled for this session.
    comment_queue: "asyncio.Queue[str] | None" = None


@runtime_checkable
class AcpBackendSession(Protocol):
    """Session-shaped backend handle.

    ``run_turn`` drives the session to completion (or until ``close``
    is invoked) and yields :class:`BackendEvent` objects as it makes
    progress. After ``run_turn`` returns, the ``status`` property must
    be one of: ``"succeeded" | "failed" | "stalled" | "interrupted" |
    "errored"``.

    ``close`` is idempotent and safe to call multiple times. Today's
    ClaudeAcpBackendSession ``close`` signals the SDK's ``interrupt``
    and breaks out of the ``receive_response`` loop.

    All property accessors are valid both DURING and AFTER ``run_turn``;
    counters increment live as the session progresses so the dashboard
    can render real-time token usage.
    """

    async def run_turn(self) -> AsyncIterator[BackendEvent]:
        ...

    async def close(self) -> None:
        ...

    @property
    def status(self) -> str:
        ...

    @property
    def input_tokens(self) -> int:
        ...

    @property
    def output_tokens(self) -> int:
        ...

    @property
    def total_tokens(self) -> int:
        ...

    @property
    def session_id(self) -> str | None:
        ...

    @property
    def turn_count(self) -> int:
        ...

    @property
    def total_cost_usd(self) -> float | None:
        ...

    @property
    def last_error(self) -> str | None:
        ...

    @property
    def permission_denials(self) -> list[Any]:
        ...


class AcpBackend(abc.ABC):
    """Abstract base for an ACP backend.

    Each concrete backend exposes:

    * :meth:`name` (classmethod) — registry key.
    * :meth:`start_session` — open a backend-specific session.
    * :meth:`validate_provider` — backend-specific validation of a
      :class:`oompah.models.ModelProvider` record (e.g. require an
      api_key, refuse a non-Anthropic base_url, etc.). Returns a list
      of human-readable error strings; an empty list means "OK".
    """

    @classmethod
    @abc.abstractmethod
    def name(cls) -> str:
        """The registry key for this backend. Must be lowercase,
        underscore-separated, and stable across versions — it's
        persisted in ModelProvider.backend on disk."""
        raise NotImplementedError

    @abc.abstractmethod
    def start_session(self, options: AcpBackendOptions) -> AcpBackendSession:
        """Construct a backend-specific session handle.

        Implementations should NOT start the SDK loop here — that
        happens lazily on the first ``run_turn`` call. This lets the
        orchestrator wire up logging/observers before the backend
        begins emitting events.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def validate_provider(self, provider: "ModelProvider") -> list[str]:
        """Backend-specific validation of a provider record.

        Returns a list of human-readable error strings; empty list
        means the provider is usable. Today's ClaudeAcpBackend returns
        ``[]`` unconditionally (the SDK relies on the operator's
        subscription auth, no api_key required); a future backend that
        needs an api_key should return ``["api_key required"]`` when
        the field is empty.
        """
        raise NotImplementedError
