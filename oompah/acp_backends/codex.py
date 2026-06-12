"""Codex / OpenAI-Agents-SDK backend (the second registered ACP backend).

This is child B of the multi-backend ACP epic (bead
``oompah-zlz_2-yiuy``). It validates that the abstraction landed in
child A (``oompah-zlz_2-0hzh``) holds in practice by implementing a
second concrete :class:`oompah.acp_backends.base.AcpBackend` against
the OpenAI Agents Python SDK.

# Codex SDK choice

The issue's open question was: ``openai-agents`` vs ``openai-agentkit``
vs custom HTTP via the ``openai`` client. The verdict landed on
**openai-agents** (PyPI: ``openai-agents``, import path ``agents``)
because it's session-shaped (``Agent`` + ``Runner``), supports tool
injection via ``function_tool``, and streams events natively via
``Runner.run_streamed`` — the closest analogue to Claude's SDK among
the three candidates. The SDK is lazily imported so installations
that never use the Codex backend don't pay the import cost.

If the operator runs against a future release where the same package
is republished under ``openai_agents`` we fall back to that name; the
backend's only hard requirement is a module exposing ``Agent``,
``Runner``, and ``function_tool``.

# Streaming vs polling

The openai-agents SDK uses async streaming (``Runner.run_streamed``
yields ``RunStreamEvent`` items as they arrive). The Claude SDK
likewise uses async streaming. Both backends therefore expose the same
``async for ev in backend_session.run_turn()`` shape — no polling
shim is required.

# Cost reporting

We normalize the SDK's terminal usage payload to a stable shape on
:class:`oompah.acp_backends.base.BackendEvent` so the child-C billing
work consumes a uniform dict regardless of which backend the session
ran on::

    {
        "input_tokens": int,
        "output_tokens": int,
        "total_tokens": int,
        "cost_usd": float | None,  # None for subscription-tier Codex
    }

For per-token billing tiers we surface the SDK's reported cost
(currently from ``RunResult.context_wrapper.usage`` — see below). For
subscription tiers (Codex's OAuth flow handled by the codex CLI),
``cost_usd`` is None: there is no per-token bill, the cost rolls up
to the operator's monthly subscription.

# Tool bridging gap

The OpenAI Agents SDK does not expose a Claude-shaped
``can_use_tool`` callback nor a hard ``disallowed_tools`` denylist.
We work around this by ONLY providing oompah's safety-railed catalog
(see :func:`oompah.acp_tools.build_codex_tool_catalog`) to the agent.
The SDK has no native ``Bash``/``Read``/``Write`` equivalents to
worry about — its tool surface is whatever functions you decorate
with ``function_tool``. So the bridging story is simpler than Claude's:
no denylist needed, no can_use_tool callback, just don't pass
unsafe tools in. If a future oompah focus's must_do requires a tool
shape the SDK can't represent (e.g. a streaming MCP resource), the
backend raises :class:`NotImplementedError` at session-construction
time with a clear pointer at the unsupported tool.

# Permission handling

The SDK has no ``acceptEdits`` / ``bypassPermissions`` analog. The
backend accepts oompah's ``permission_mode`` field for symmetry but
treats every mode the same way: tools route through the safety-railed
catalog, and the orchestrator's permission gate (which is mode-aware
at the dispatch level, not the per-tool level) is the real safety
boundary. The session_start event records ``permission_mode`` for
audit but doesn't change SDK behavior based on it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, TYPE_CHECKING

from oompah.acp_backends.base import (
    AcpBackend,
    AcpBackendOptions,
    AcpBackendSession,
    BackendEvent,
)
from oompah.acp_backends.registry import register_backend
from oompah.agent import AgentEvent

if TYPE_CHECKING:
    from oompah.models import ModelProvider

logger = logging.getLogger(__name__)


def _import_sdk():
    """Lazy import of the OpenAI Agents SDK.

    Tries ``agents`` first (the canonical PyPI ``openai-agents``
    package import path); falls back to ``openai_agents`` for future-
    proofing against a possible rename. Raises :class:`ImportError`
    with an install hint if neither resolves — surfaces a clear
    operator-actionable error rather than an obscure ``ModuleNotFound``.
    """
    try:
        import agents as sdk  # type: ignore
        return sdk
    except ImportError as exc:
        try:
            import openai_agents as sdk  # type: ignore
            return sdk
        except ImportError:
            raise ImportError(
                "openai-agents SDK not installed. Codex ACP backend "
                "requires the OpenAI Agents Python SDK. Install with: "
                "uv pip install 'oompah[codex]'"
            ) from exc


@dataclass
class _CodexCounters:
    """Token-usage counters scraped from SDK events / RunResult.usage.

    Modeled after :class:`oompah.acp_backends.claude._SessionCounters`
    but tailored to the openai-agents shape. The SDK reports a single
    rollup at ``RunResult.context_wrapper.usage`` (input_tokens,
    output_tokens, total_tokens, requests). Where the SDK emits
    streaming deltas we increment live; if not available we let the
    terminal RunResult set the final values.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    turn_count: int = 0
    last_event: str | None = None

    def absorb_usage(self, usage: Any) -> None:
        """Pull token counts out of whatever ``usage`` shape the SDK
        version we're running against happens to use.

        Handles three shapes:

        * A dict with ``input_tokens`` / ``output_tokens`` keys.
        * An openai-agents ``Usage`` object with those attributes.
        * ``None`` / unrecognized — ignored.
        """
        if usage is None:
            return
        if isinstance(usage, dict):
            in_t = usage.get("input_tokens")
            out_t = usage.get("output_tokens")
            tot_t = usage.get("total_tokens")
        else:
            in_t = getattr(usage, "input_tokens", None)
            out_t = getattr(usage, "output_tokens", None)
            tot_t = getattr(usage, "total_tokens", None)
        try:
            if in_t is not None:
                self.input_tokens = int(in_t)
            if out_t is not None:
                self.output_tokens = int(out_t)
            if tot_t is not None:
                self.total_tokens = int(tot_t)
            elif in_t is not None or out_t is not None:
                self.total_tokens = self.input_tokens + self.output_tokens
        except (TypeError, ValueError):
            return


def _truncate(value: Any, limit: int = 1500) -> Any:
    """Same truncation policy as the Claude backend uses — keeps the
    per-agent JSONL log readable when tool inputs/outputs are huge."""
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + " …[truncated]"
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v, limit) for v in value]
    return value


class CodexAcpBackendSession(AcpBackendSession):
    """OpenAI-Agents-SDK-driven session handle.

    Mirrors :class:`oompah.acp_backends.claude.ClaudeAcpBackendSession`
    in surface and lifecycle, but drives the openai-agents
    ``Agent`` + ``Runner.run_streamed`` pair under the hood.
    """

    def __init__(self, options: AcpBackendOptions):
        self._options = options
        self._counters = _CodexCounters()
        self._stop_requested = False
        self._session_id: str | None = None
        self._final_cost_usd: float | None = None
        self._permission_denials: list[Any] = []
        self._last_error: str | None = None
        self._status: str = "pending"
        # Runtime SDK objects. Populated lazily on first run_turn so
        # constructor errors don't poison the registry.
        self._agent: Any = None
        self._streamed_result: Any = None
        # CLI-path (subscription/OAuth) abort handle. The experimental
        # Codex extension cancels a turn via an ``asyncio.Event`` signal
        # passed in TurnOptions; close() sets it.
        self._cli_abort: Any = None
        # Billing tier drives the execution path AND cost reporting:
        #   * "per_token"    -> in-process OpenAI-Agents SDK (API key)
        #   * "subscription" -> Codex CLI subprocess (OAuth via auth.json)
        # surfacing ``cost_usd=None`` for subscription tier.
        self._billing_model: str = self._resolve_billing_model()

    def _resolve_billing_model(self) -> str:
        """Resolve the billing model that selects the execution path.

        Reads the first-class :attr:`AcpBackendOptions.billing_model`
        field (flowed from ``ModelProvider.billing_model`` by the
        orchestrator / health probe). Defaults to ``"per_token"`` — the
        strict, API-key tier — when unset.
        """
        return (
            getattr(self._options, "billing_model", None) or "per_token"
        ).strip().lower() or "per_token"

    # ---- AcpBackendSession protocol property accessors ----

    @property
    def status(self) -> str:
        return self._status

    @property
    def input_tokens(self) -> int:
        return self._counters.input_tokens

    @property
    def output_tokens(self) -> int:
        return self._counters.output_tokens

    @property
    def total_tokens(self) -> int:
        return self._counters.total_tokens or (
            self._counters.input_tokens + self._counters.output_tokens
        )

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def turn_count(self) -> int:
        return self._counters.turn_count

    @property
    def total_cost_usd(self) -> float | None:
        return self._final_cost_usd

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def permission_denials(self) -> list[Any]:
        return list(self._permission_denials)

    # ---- Lifecycle ----

    async def close(self) -> None:
        """Request that the active session stop. Idempotent.

        The openai-agents SDK has a ``cancel`` method on the streamed
        result handle. If we have one we call it; if not (e.g. close()
        fires before run_turn started) we just set the flag and let
        run_turn() short-circuit.
        """
        self._stop_requested = True
        # CLI path: signal the Codex subprocess to abort.
        if self._cli_abort is not None:
            with contextlib.suppress(Exception):
                self._cli_abort.set()
        streamed = self._streamed_result
        if streamed is not None:
            cancel = getattr(streamed, "cancel", None)
            if cancel is not None:
                with contextlib.suppress(Exception):
                    res = cancel()
                    # ``cancel`` may be sync or async depending on SDK
                    # version. Await it only if it returned a coroutine.
                    if hasattr(res, "__await__"):
                        await res

    # ---- Internal: event emission ----

    def _emit_agent_event(self, kind: str, *, payload: dict[str, Any] | None = None) -> None:
        on_event = self._options.on_event
        if on_event is None:
            return
        ev = AgentEvent(
            event=kind,
            timestamp=time.time(),
            agent_pid=None,
            usage={
                "input_tokens": self._counters.input_tokens,
                "output_tokens": self._counters.output_tokens,
                "total_tokens": self.total_tokens,
            },
            payload=payload or {},
        )
        try:
            on_event(ev)
        except Exception as exc:  # pragma: no cover — observer's bug
            logger.debug("on_event observer raised: %s", exc)

    def _make_backend_event(self, kind: str, payload: dict[str, Any]) -> BackendEvent:
        prefix = "acp_"
        clean_kind = kind[len(prefix):] if kind.startswith(prefix) else kind
        return BackendEvent(
            kind=clean_kind,
            payload=dict(payload or {}),
            timestamp=time.time(),
            usage={
                "input_tokens": self._counters.input_tokens,
                "output_tokens": self._counters.output_tokens,
                "total_tokens": self.total_tokens,
            },
        )

    def _emit(self, kind: str, *, payload: dict[str, Any] | None = None) -> BackendEvent:
        """Dual-emit: forward an AgentEvent to on_event AND return a
        BackendEvent the caller can yield from run_turn."""
        self._emit_agent_event(kind, payload=payload)
        return self._make_backend_event(kind, payload or {})

    # ---- Internal: cost normalization ----

    def _cost_payload(self) -> dict[str, Any]:
        """Build the normalized cost dict for the terminal result event.

        Child C will read this same shape from both backends — keep it
        stable. ``cost_usd`` is None for subscription tiers (no
        per-token bill); per-token tiers populate it.
        """
        return {
            "input_tokens": self._counters.input_tokens,
            "output_tokens": self._counters.output_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": self._final_cost_usd,
        }

    # ---- Build the SDK-native tool catalog ----

    def _build_tool_catalog(self) -> list[Any]:
        """Build the Codex/OpenAI-Agents-SDK tool catalog for this run.

        Ignores any ``options.tool_catalog`` passed in by the
        orchestrator (which is Claude-formatted ``@tool`` functions —
        wrong shape for openai-agents) and rebuilds the catalog from
        ``options.workspace_path`` so the underlying ``_exec_*``
        helpers (cd-guard and shell-redirect) are identical between
        backends. See :func:`oompah.acp_tools.build_codex_tool_catalog`.
        """
        from oompah.acp_tools import build_codex_tool_catalog

        return build_codex_tool_catalog(
            self._options.workspace_path,
            project_store=self._options.project_store,
            project_id=self._options.project_id,
            task_tracker=self._options.task_tracker,
        )

    # ---- run_turn: drive the openai-agents Runner ----

    async def run_turn(self) -> AsyncIterator[BackendEvent]:
        """Open a session, run the turn, stream events, yield
        :class:`BackendEvent` until completion.

        Dispatches on billing tier:

        * ``"subscription"`` -> :meth:`_run_turn_via_cli` (Codex CLI
          subprocess, OAuth via ``~/.codex/auth.json``).
        * anything else -> :meth:`_run_turn_via_api` (in-process
          OpenAI-Agents SDK, API-key billing).

        After run_turn returns, ``self.status`` is one of:

        * ``"succeeded"`` — terminal event with no error
        * ``"failed"`` — terminal event flagged is_error
        * ``"stalled"`` — turn_timeout_s exceeded; cancelled
        * ``"interrupted"`` — caller invoked ``close()``
        * ``"errored"`` — SDK / subprocess crashed unexpectedly
        """
        if self._stop_requested:
            self._status = "interrupted"
            return

        if self._billing_model == "subscription":
            async for be in self._run_turn_via_cli():
                yield be
            return

        async for be in self._run_turn_via_api():
            yield be

    async def _run_turn_via_api(self) -> AsyncIterator[BackendEvent]:
        """In-process OpenAI-Agents SDK path (per-token / API-key tier)."""
        try:
            sdk = _import_sdk()
        except ImportError as exc:
            self._last_error = str(exc)
            logger.error("Codex ACP backend: %s", self._last_error)
            self._status = "errored"
            return

        Agent = getattr(sdk, "Agent", None)
        Runner = getattr(sdk, "Runner", None)
        if Agent is None or Runner is None:
            self._last_error = (
                "openai-agents SDK is missing 'Agent' or 'Runner' exports; "
                "Codex backend requires both."
            )
            logger.error(self._last_error)
            self._status = "errored"
            return

        # Compose env. agents runtime reads OPENAI_API_KEY from the
        # process env; if the provider configured a custom api_key it
        # will already be in options.env.
        agent_env = dict(os.environ)
        if self._options.env:
            agent_env.update(self._options.env)
        # Push the api_key into the process env if present in options
        # so the SDK's default client picks it up.
        api_key = agent_env.get("OPENAI_API_KEY") or agent_env.get("OOMPAH_CODEX_API_KEY")
        if api_key:
            os.environ.setdefault("OPENAI_API_KEY", api_key)

        try:
            tools = self._build_tool_catalog()
        except NotImplementedError as exc:
            # An oompah focus required a tool shape we can't represent
            # — surface as a hard error so the orchestrator can flip
            # the bead to needs-human instead of looping silently.
            self._last_error = (
                f"Codex backend cannot bridge required tools: {exc}"
            )
            logger.warning(self._last_error)
            self._status = "errored"
            return
        except Exception as exc:
            self._last_error = f"tool catalog build failed: {exc!r}"
            logger.warning(self._last_error)
            self._status = "errored"
            return

        agent_kwargs: dict[str, Any] = {
            "name": "oompah-codex-agent",
            "instructions": self._options.prompt,
            "tools": tools,
        }
        if self._options.model:
            agent_kwargs["model"] = self._options.model

        try:
            self._agent = Agent(**agent_kwargs)
        except Exception as exc:
            self._last_error = f"Agent construction failed: {exc!r}"
            logger.warning(self._last_error)
            self._status = "errored"
            return

        # Permission_mode is recorded for audit but doesn't change SDK
        # behavior — see module docstring. The bridged catalog is the
        # only safety surface here.
        yield self._emit(
            "acp_session_start",
            payload={
                "model": self._options.model,
                "fallback_model": self._options.fallback_model,
                "max_turns": self._options.max_turns,
                "permission_mode": self._options.permission_mode,
                "tool_policy": "codex:bridged_catalog_only",
                "tool_catalog": [
                    getattr(t, "name", getattr(t, "__name__", str(t)))
                    for t in tools
                ],
                "billing_model": self._billing_model,
                "cwd": self._options.workspace_path,
            },
        )

        # Start the streaming run. Newer SDK versions expose
        # Runner.run_streamed; older ones may use Runner.stream. Try
        # both before bailing.
        run_streamed = getattr(Runner, "run_streamed", None) or getattr(
            Runner, "stream", None
        )
        if run_streamed is None:
            self._last_error = (
                "openai-agents SDK Runner does not expose run_streamed/stream; "
                "Codex backend requires a streaming Runner."
            )
            logger.error(self._last_error)
            self._status = "errored"
            return

        try:
            self._streamed_result = run_streamed(
                self._agent, input=self._options.prompt
            )
        except Exception as exc:
            self._last_error = f"Runner.run_streamed failed: {exc!r}"
            logger.warning(self._last_error)
            yield self._emit(
                "acp_session_error", payload={"error": self._last_error}
            )
            self._status = "errored"
            return

        deadline = time.monotonic() + self._options.turn_timeout_s

        try:
            stream_events = getattr(
                self._streamed_result, "stream_events", None
            )
            if stream_events is None:
                # Some SDK shapes use direct async-iteration on the
                # result handle instead of an explicit stream_events
                # method. Fall back to iterating the result directly.
                event_iter = self._streamed_result.__aiter__()
            else:
                event_iter = stream_events()

            async for event in event_iter:
                if self._stop_requested:
                    self._status = "interrupted"
                    return
                if time.monotonic() > deadline:
                    yield self._emit(
                        "acp_turn_timeout",
                        payload={"timeout_s": self._options.turn_timeout_s},
                    )
                    self._status = "stalled"
                    return

                async for be in self._translate_stream_event(event):
                    yield be

            # Stream drained. Pull final usage/cost off the result.
            self._absorb_final_result()
            yield self._emit(
                "acp_result",
                payload={
                    "subtype": "success",
                    "is_error": False,
                    "stop_reason": "end_turn",
                    "num_turns": self._counters.turn_count,
                    "total_cost_usd": self._final_cost_usd,
                    "usage": self._cost_payload(),
                    "errors": None,
                },
            )
            self._status = "succeeded"
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Codex ACP session failed: %s", self._last_error)
            yield self._emit(
                "acp_session_error", payload={"error": self._last_error}
            )
            self._status = "errored"
        finally:
            self._streamed_result = None
            self._agent = None

    # ---- run_turn: drive the Codex CLI (subscription / OAuth tier) ----

    @staticmethod
    def _import_codex_cli():
        """Lazy import of the experimental Codex CLI extension.

        Raises :class:`ImportError` if the installed openai-agents SDK
        predates the experimental Codex extension.
        """
        from agents.extensions.experimental.codex import Codex
        from agents.extensions.experimental.codex.thread_options import (
            ThreadOptions,
        )
        from agents.extensions.experimental.codex.turn_options import TurnOptions

        return Codex, ThreadOptions, TurnOptions

    async def _run_turn_via_cli(self) -> AsyncIterator[BackendEvent]:
        """Codex CLI subprocess path (subscription / OAuth tier).

        Drives the bundled ``codex`` binary through the OpenAI-Agents
        SDK's experimental Codex extension. The CLI authenticates from
        ``~/.codex/auth.json`` (the operator's ChatGPT OAuth login),
        refreshes tokens, and routes to the ChatGPT backend — none of
        which the in-process API path can do. We pass NO api_key so the
        CLI uses its own login rather than an ``OPENAI_API_KEY``.

        Safety: unlike the API path (which bridges oompah's cd-guarded
        MCP catalog), the CLI ships its own tools. We confine them via
        the native sandbox (``workspace-write``) and disable approval
        prompts (``never``) since oompah runs autonomously.
        """
        try:
            Codex, ThreadOptions, TurnOptions = self._import_codex_cli()
        except ImportError as exc:
            self._last_error = (
                "openai-agents Codex CLI extension not available: "
                f"{exc}. Requires a recent openai-agents SDK plus the "
                "codex CLI on PATH."
            )
            logger.error("Codex CLI backend: %s", self._last_error)
            self._status = "errored"
            return

        # Compose the subprocess env: inherit the process env plus any
        # options.env overrides, but strip CODEX_API_KEY so the CLI's
        # OAuth login is used rather than a key.
        cli_env = dict(os.environ)
        if self._options.env:
            cli_env.update(self._options.env)
        cli_env.pop("CODEX_API_KEY", None)

        try:
            codex = Codex(env=cli_env)
            thread = codex.start_thread(
                ThreadOptions(
                    model=self._options.model or None,
                    working_directory=self._options.workspace_path,
                    skip_git_repo_check=True,
                    sandbox_mode="workspace-write",
                    approval_policy="never",
                    network_access_enabled=True,
                )
            )
        except Exception as exc:
            self._last_error = f"Codex CLI init failed: {exc!r}"
            logger.warning(self._last_error)
            self._status = "errored"
            return

        yield self._emit(
            "acp_session_start",
            payload={
                "model": self._options.model,
                "max_turns": self._options.max_turns,
                "permission_mode": self._options.permission_mode,
                "tool_policy": "codex_cli:native_sandbox",
                "sandbox_mode": "workspace-write",
                "approval_policy": "never",
                "billing_model": self._billing_model,
                "cwd": self._options.workspace_path,
            },
        )

        self._cli_abort = asyncio.Event()
        try:
            streamed = await thread.run_streamed(
                self._options.prompt,
                TurnOptions(signal=self._cli_abort),
            )
        except Exception as exc:
            self._last_error = f"Codex CLI run_streamed failed: {exc!r}"
            logger.warning(self._last_error)
            yield self._emit(
                "acp_session_error", payload={"error": self._last_error}
            )
            self._status = "errored"
            return

        deadline = time.monotonic() + self._options.turn_timeout_s
        try:
            async for event in streamed.events:
                if self._stop_requested:
                    self._status = "interrupted"
                    return
                if time.monotonic() > deadline:
                    self._cli_abort.set()
                    yield self._emit(
                        "acp_turn_timeout",
                        payload={"timeout_s": self._options.turn_timeout_s},
                    )
                    self._status = "stalled"
                    return
                async for be in self._translate_cli_event(event):
                    yield be

            # Stream drained without an explicit terminal event — treat
            # as success (defensive; turn.completed normally sets this).
            if self._status == "pending":
                yield self._emit(
                    "acp_result",
                    payload={
                        "subtype": "success",
                        "is_error": False,
                        "stop_reason": "end_turn",
                        "num_turns": self._counters.turn_count,
                        "total_cost_usd": self._final_cost_usd,
                        "usage": self._cost_payload(),
                        "errors": None,
                    },
                )
                self._status = "succeeded"
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Codex CLI session failed: %s", self._last_error)
            yield self._emit(
                "acp_session_error", payload={"error": self._last_error}
            )
            self._status = "errored"
        finally:
            self._cli_abort = None

    def _absorb_cli_usage(self, usage: Any) -> None:
        """Roll a Codex CLI ``Usage`` object into our counters.

        Subscription tier has no per-token bill, so ``_final_cost_usd``
        stays None — matching the API path's subscription behavior.
        """
        try:
            self._counters.input_tokens = int(
                getattr(usage, "input_tokens", self._counters.input_tokens) or 0
            )
            self._counters.output_tokens = int(
                getattr(usage, "output_tokens", self._counters.output_tokens) or 0
            )
        except (TypeError, ValueError):
            pass
        self._final_cost_usd = None

    async def _translate_cli_event(
        self, event: Any
    ) -> AsyncIterator[BackendEvent]:
        """Map one experimental-Codex ``ThreadEvent`` to BackendEvent(s).

        Pattern-matches on the event's ``type`` string (``thread.started``,
        ``turn.started``, ``turn.completed``, ``turn.failed``, ``error``,
        ``item.{started,updated,completed}``) rather than isinstance, for
        the same version-robustness reason as the API path.
        """
        ev_type = getattr(event, "type", None)

        if ev_type == "thread.started":
            tid = getattr(event, "thread_id", None)
            if isinstance(tid, str):
                self._session_id = tid
            return

        if ev_type == "turn.started":
            self._counters.turn_count += 1
            return

        if ev_type == "turn.completed":
            usage = getattr(event, "usage", None)
            if usage is not None:
                self._absorb_cli_usage(usage)
            yield self._emit(
                "acp_result",
                payload={
                    "subtype": "success",
                    "is_error": False,
                    "stop_reason": "end_turn",
                    "num_turns": self._counters.turn_count,
                    "total_cost_usd": self._final_cost_usd,
                    "usage": self._cost_payload(),
                    "errors": None,
                },
            )
            self._status = "succeeded"
            return

        if ev_type == "turn.failed":
            err = getattr(event, "error", None)
            msg = getattr(err, "message", None) or "Codex turn failed"
            self._last_error = msg
            yield self._emit("acp_assistant_error", payload={"error": msg})
            self._status = "failed"
            return

        if ev_type == "error":
            msg = getattr(event, "message", None) or "Codex thread error"
            self._last_error = msg
            yield self._emit("acp_session_error", payload={"error": msg})
            self._status = "errored"
            return

        if ev_type in ("item.started", "item.updated", "item.completed"):
            item = getattr(event, "item", None)
            async for be in self._translate_cli_item(ev_type, item):
                yield be
            return
        # Unknown / not-of-interest event kinds are ignored.

    async def _translate_cli_item(
        self, ev_type: str, item: Any
    ) -> AsyncIterator[BackendEvent]:
        """Map a Codex CLI ``ThreadItem`` to BackendEvent(s).

        Text/reasoning are emitted only on ``item.completed`` (the final
        form) to avoid duplicate deltas from started/updated. Command
        execution emits tool_use on start and tool_result on completion.
        """
        item_type = getattr(item, "type", None) if item is not None else None

        if item_type == "agent_message":
            if ev_type == "item.completed":
                text = getattr(item, "text", "") or ""
                if text:
                    self._counters.last_event = "text"
                    yield self._emit("acp_text", payload={"text": text[:2000]})
        elif item_type == "reasoning":
            if ev_type == "item.completed":
                text = getattr(item, "text", "") or ""
                if text:
                    self._counters.last_event = "thinking"
                    yield self._emit(
                        "acp_thinking", payload={"text": text[:2000]}
                    )
        elif item_type == "command_execution":
            if ev_type == "item.started":
                self._counters.last_event = "tool_use"
                yield self._emit(
                    "acp_tool_use",
                    payload={
                        "tool": "command_execution",
                        "input": _truncate(getattr(item, "command", "")),
                        "id": getattr(item, "id", None),
                    },
                )
            elif ev_type == "item.completed":
                self._counters.last_event = "tool_result"
                yield self._emit(
                    "acp_tool_result",
                    payload={
                        "tool_use_id": getattr(item, "id", None),
                        "is_error": bool(getattr(item, "exit_code", 0) or 0),
                        "content": _truncate(
                            getattr(item, "aggregated_output", "")
                        ),
                    },
                )
        elif item_type == "file_change":
            if ev_type == "item.completed":
                self._counters.last_event = "tool_use"
                changes = getattr(item, "changes", None) or []
                yield self._emit(
                    "acp_tool_use",
                    payload={
                        "tool": "file_change",
                        "input": _truncate(
                            [getattr(c, "path", "?") for c in changes]
                        ),
                        "id": getattr(item, "id", None),
                    },
                )
        elif item_type == "mcp_tool_call":
            if ev_type == "item.completed":
                self._counters.last_event = "tool_use"
                yield self._emit(
                    "acp_tool_use",
                    payload={
                        "tool": (
                            f"{getattr(item, 'server', '?')}::"
                            f"{getattr(item, 'tool', '?')}"
                        ),
                        "input": _truncate(getattr(item, "arguments", None)),
                        "id": getattr(item, "id", None),
                    },
                )
        elif item_type == "error":
            if ev_type == "item.completed":
                msg = getattr(item, "message", "") or ""
                self._last_error = msg or self._last_error
                yield self._emit("acp_assistant_error", payload={"error": msg})
        # Other item kinds (web_search, todo_list, unknown) are ignored.

    # ---- Internal: per-event translation ----

    async def _translate_stream_event(
        self, event: Any
    ) -> AsyncIterator[BackendEvent]:
        """Map a single SDK ``stream_events`` item to one or more
        :class:`BackendEvent` instances.

        The openai-agents SDK groups its stream events into a handful
        of categories. We pattern-match on ``event.type`` (a string)
        because the concrete classes are SDK-version dependent and
        attribute-poking is more robust than isinstance against
        types that move.
        """
        ev_type = getattr(event, "type", None)
        # ---- Text deltas / messages ----
        if ev_type == "raw_response_event":
            data = getattr(event, "data", None)
            # OpenAI streaming response delta event: pull text if any.
            delta = getattr(data, "delta", None) if data is not None else None
            if isinstance(delta, str) and delta:
                self._counters.last_event = "text"
                yield self._emit(
                    "acp_text", payload={"text": delta[:2000]}
                )
            # Capture session id if present.
            if data is not None and self._session_id is None:
                sid = getattr(data, "response_id", None) or getattr(
                    data, "id", None
                )
                if isinstance(sid, str):
                    self._session_id = sid
        elif ev_type == "run_item_stream_event":
            item = getattr(event, "item", None)
            item_type = getattr(item, "type", None) if item is not None else None
            if item_type == "message_output_item":
                text = self._extract_message_text(item)
                if text:
                    self._counters.last_event = "text"
                    yield self._emit(
                        "acp_text", payload={"text": text[:2000]}
                    )
            elif item_type == "tool_call_item":
                self._counters.last_event = "tool_use"
                self._counters.turn_count += 1
                tool_name = getattr(item, "tool_name", None) or getattr(
                    item, "name", "?"
                )
                tool_input = getattr(item, "arguments", None) or getattr(
                    item, "input", {}
                )
                tool_id = getattr(item, "call_id", None) or getattr(
                    item, "id", None
                )
                yield self._emit(
                    "acp_tool_use",
                    payload={
                        "tool": tool_name,
                        "input": _truncate(tool_input),
                        "id": tool_id,
                    },
                )
            elif item_type == "tool_call_output_item":
                self._counters.last_event = "tool_result"
                yield self._emit(
                    "acp_tool_result",
                    payload={
                        "tool_use_id": getattr(item, "call_id", None)
                        or getattr(item, "id", None),
                        "is_error": bool(getattr(item, "is_error", False)),
                        "content": _truncate(
                            getattr(item, "output", None)
                            or getattr(item, "content", None)
                        ),
                    },
                )
            elif item_type == "reasoning_item":
                self._counters.last_event = "thinking"
                text = self._extract_message_text(item) or ""
                if text:
                    yield self._emit(
                        "acp_thinking", payload={"text": text[:2000]}
                    )
        elif ev_type == "agent_updated_stream_event":
            # Handoff between sub-agents — not used by the baseline
            # Codex flow but emit for audit so the dashboard sees it.
            new_agent = getattr(event, "new_agent", None)
            yield self._emit(
                "acp_session_start",
                payload={
                    "kind": "agent_handoff",
                    "to": getattr(new_agent, "name", str(new_agent)),
                },
            )
        # else: silently ignore unknown event types — SDK versions may
        # introduce new ones, and we don't want to log spam every
        # stream tick.

    def _extract_message_text(self, item: Any) -> str:
        """Pull text content out of an SDK ``message_output_item`` /
        ``reasoning_item`` regardless of the exact field name."""
        for attr in ("text", "output_text", "content", "message"):
            val = getattr(item, attr, None)
            if isinstance(val, str):
                return val
            if isinstance(val, list):
                parts = [
                    (getattr(b, "text", None) or "")
                    for b in val
                    if getattr(b, "text", None)
                ]
                if parts:
                    return "".join(parts)
        return ""

    def _absorb_final_result(self) -> None:
        """Read the SDK's terminal RunResult and update counters + cost.

        The openai-agents SDK exposes the rolled-up usage at
        ``RunResult.context_wrapper.usage``. We also defensively look
        at top-level ``usage`` and ``raw_responses`` in case the SDK
        shape shifts between versions.
        """
        result = self._streamed_result
        if result is None:
            return
        # Try several shapes; the SDK has been moving usage around
        # between minor versions.
        usage_candidates = [
            getattr(result, "usage", None),
            getattr(
                getattr(result, "context_wrapper", None), "usage", None
            ),
            getattr(getattr(result, "context", None), "usage", None),
        ]
        for u in usage_candidates:
            if u is not None:
                self._counters.absorb_usage(u)
                break

        # Session id (response id) is sometimes only available on the
        # result object after the stream finishes.
        if self._session_id is None:
            for attr in ("response_id", "session_id", "id"):
                sid = getattr(result, attr, None)
                if isinstance(sid, str):
                    self._session_id = sid
                    break

        # Cost reporting — None for subscription tiers (no per-token
        # bill). For per-token tiers, surface whatever the SDK reports;
        # if absent (most current SDK versions don't report dollar
        # amounts), child C will compute it from token counts + the
        # provider's model_costs table.
        if self._billing_model == "subscription":
            self._final_cost_usd = None
        else:
            cost = (
                getattr(result, "total_cost_usd", None)
                or getattr(
                    getattr(result, "context_wrapper", None),
                    "total_cost_usd",
                    None,
                )
            )
            if isinstance(cost, (int, float)):
                self._final_cost_usd = float(cost)
            # else: leave at None; child C will compute from tokens.


# ----------------------------------------------------------------------
# Backend class
# ----------------------------------------------------------------------


class CodexAcpBackend(AcpBackend):
    """OpenAI-Agents-SDK-driven ACP backend.

    Validates that the abstraction landed by child A holds: a single
    concrete subclass can plug into the same registry + session
    protocol that the Claude backend uses.
    """

    @classmethod
    def name(cls) -> str:
        return "codex"

    def start_session(self, options: AcpBackendOptions) -> AcpBackendSession:
        return CodexAcpBackendSession(options)

    def validate_provider(self, provider: "ModelProvider") -> list[str]:
        """Backend-specific provider validation.

        Rules:

        * Per-token tier (default): requires ``api_key``.
        * Subscription tier: ``api_key`` optional — Codex CLI handles
          the OAuth flow at the binary level, not at the provider
          record level.
        * ``base_url`` is optional but, when overridden from the
          default Codex endpoint, must be a well-formed http(s) URL.

        The billing tier is read from ``provider.billing_model``
        (child C of the epic will land that field). Until then we read
        it via ``getattr`` with a default of ``"per_token"`` so the
        strict validator runs by default — i.e. operators must
        explicitly opt into the subscription tier.
        """
        errors: list[str] = []
        billing_model = (
            (getattr(provider, "billing_model", None) or "per_token")
            .strip()
            .lower()
        )
        # Treat anything not explicitly "subscription" as per-token
        # (strict). Conservative on purpose: a garbled or future-
        # added value shouldn't silently disable the api_key check.
        if billing_model != "subscription":
            if not (provider.api_key or "").strip():
                errors.append(
                    "api_key required for per-token Codex (OpenAI-compatible "
                    "key). Set billing_model='subscription' on the provider "
                    "if running Codex CLI with OAuth."
                )
        else:
            # Subscription tier drives the codex CLI subprocess, which
            # authenticates from ~/.codex/auth.json. Fail fast if the
            # binary can't be located. find_codex_path() returns falsy
            # OR raises when the binary is missing — treat both as a
            # missing CLI. If the SDK extension itself is unavailable we
            # stay silent and let the session path surface the error.
            try:
                from agents.extensions.experimental.codex.exec import (
                    find_codex_path,
                )
            except Exception:
                find_codex_path = None  # type: ignore[assignment]

            if find_codex_path is not None:
                missing = False
                try:
                    missing = not find_codex_path()
                except Exception:
                    missing = True
                if missing:
                    errors.append(
                        "subscription tier requires the 'codex' CLI on PATH "
                        "(authenticated via 'codex login' -> ~/.codex/auth.json)."
                    )

        base_url = (provider.base_url or "").strip()
        if base_url:
            if not (
                base_url.startswith("http://")
                or base_url.startswith("https://")
            ):
                errors.append(
                    f"base_url must start with http:// or https://; got "
                    f"{base_url!r}. Leave empty to use the default Codex "
                    f"endpoint."
                )

        return errors


# Register on import. ``oompah/acp_backends/__init__.py`` imports this
# module so the package import wires both ``claude`` and ``codex`` into
# the registry without callers having to remember to import each
# backend module explicitly.
register_backend(CodexAcpBackend.name(), CodexAcpBackend)
