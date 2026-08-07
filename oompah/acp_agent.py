"""ACP-mode agent execution path.

Drives the bundled `claude` CLI (via the Claude Agent SDK) — or any
other registered ACP backend — so the per-token cost is billed against
the operator's Pro/Max subscription rather than the per-token API
meter that the api_agent path incurs. See ``plans/acp-agent.md`` and
task ``oompah-zlz_2-bcl``.

This module used to inline all the Claude Agent SDK setup directly.
As of task ``oompah-zlz_2-0hzh`` (Child A of the multi-backend epic)
it has been split: SDK-specific code now lives in
``oompah/acp_backends/claude.py`` (registered as ``"claude"``);
:class:`AcpAgentSession` is a thin facade that looks up the requested
backend from the registry and delegates session lifecycle to it.

The class shape mirrors :class:`oompah.api_agent.ApiAgentSession` so
``_run_acp_worker`` in the orchestrator can be a thin variant of
``_run_api_worker``: same observable surface (token counters, run_task
return shape, terminate semantics, JSONL event stream).

Key architectural decisions (locked in via the task's Q&A in
plans/acp-agent.md):

* **Tool bridging (Q2 = B).** The SDK's ``ClaudeAgentOptions.mcp_servers``
  takes an in-process MCP server. We declare oompah's existing tool
  catalog (read_file / edit_file / write_file / run_command /
  search_files / list_files / task helpers) as ``@tool``-decorated functions
  and intercept their execution. That keeps the cd-out-of-worktree
  guard and shell-as-tool-name redirect in force —
  none of those exist in claude's native tools.
* **Permissions (Q4).** A strict allowlist of ``mcp__oompah__*`` —
  native built-ins are hard-blocked via ``disallowed_tools``. Each
  permission grant/deny is logged to the per-agent JSONL.
* **Budget tracking (Q3).** Token usage IS reported by the SDK and we
  surface it on the session for observability, though billing flows
  through the subscription. The orchestrator's budget gate decides
  whether to ENFORCE against ACP profiles.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Callable

from oompah.acp_backends.base import (
    AcpBackendOptions,
    AcpBackendSession,
    BackendEvent,
    DEFAULT_TURN_TIMEOUT_S,
)
from oompah.acp_backends.registry import get_backend_or_raise
from oompah.agent import AgentEvent, AgentError  # noqa: F401  back-compat re-export

logger = logging.getLogger(__name__)


# Re-exported for back-compat: tests and other modules import these
# symbols from oompah.acp_agent. The actual implementations live in
# ``oompah/acp_backends/claude.py`` now.
from oompah.acp_backends.claude import (  # noqa: E402
    _SessionCounters,
    _truncate_for_log,
)


# Kept as a module-level constant so callers and tests that imported
# ``_DEFAULT_TURN_TIMEOUT_S`` from this file keep working.
_DEFAULT_TURN_TIMEOUT_S = DEFAULT_TURN_TIMEOUT_S


class AcpAgentSession:
    """Run one issue's worth of work via the configured ACP backend.

    Public surface intentionally mirrors :class:`ApiAgentSession`:

        * ``run_task(prompt, on_event=...)`` returns a status string
        * ``terminate()`` stops the subprocess
        * ``input_tokens`` / ``output_tokens`` / ``total_tokens``

    Internally, this class is a thin facade: it looks up the requested
    backend by name from :data:`oompah.acp_backends.BACKENDS`,
    constructs a backend-specific session via ``start_session``, and
    drains the session's ``run_turn`` iterator until terminal status.

    The optional ``backend_name`` kwarg selects which registered
    backend handles the session. Defaults to ``"claude"`` (today's
    Claude Agent SDK path). Future backends (Codex etc.) plug in by
    registering themselves in the registry and passing their name.
    """

    def __init__(
        self,
        workspace_path: str,
        prompt: str,
        *,
        model: str | None = None,
        fallback_model: str | None = None,
        max_turns: int | None = None,
        env: dict[str, str] | None = None,
        isolate_remote_write: bool = False,
        provider_auth_kind: str | None = None,
        tool_catalog: list[Any] | None = None,
        read_only: bool = False,
        on_event: Callable[[AgentEvent], None] | None = None,
        turn_timeout_s: float = _DEFAULT_TURN_TIMEOUT_S,
        permission_mode: str = "default",
        backend_name: str = "claude",
        billing_model: str = "per_token",
        project_store: Any = None,
        project_id: str | None = None,
        task_tracker: Any = None,
        coordination_service: Any = None,
        task_identifier: str | None = None,
        action_policy: Any = None,
        policy_denial_handler: Callable[[str], None] | None = None,
        task_handoff_token: str | None = None,
        terminal_transition_coordinator: Any = None,
        comment_queue: Any = None,
        tool_liveness: Any = None,
        validation_authority_generation: str | None = None,
        focus: Any = None,
        auditor: bool = False,
        audit_target: Any = None,
        audit_result_handler: Any = None,
        validation_reuse_policy: dict[str, Any] | None = None,
        validation_reuse_authority_check: Callable[[], object] | None = None,
        before_transport_contact: Callable[[], str | None] | None = None,
        on_precontact_admission_cancelled: Callable[[], None] | None = None,
    ):
        self.workspace_path = workspace_path
        self.prompt = prompt
        self.model = model
        self.fallback_model = fallback_model
        self.max_turns = max_turns
        self.env = env or {}
        self.isolate_remote_write = bool(isolate_remote_write)
        self.provider_auth_kind = provider_auth_kind
        self.tool_catalog = tool_catalog or []
        self.read_only = bool(read_only)
        self.on_event = on_event
        self.turn_timeout_s = turn_timeout_s
        self.permission_mode = permission_mode
        self.backend_name = backend_name
        self.billing_model = billing_model
        # Non-HTTP project management (TASK-464.8): passed through to
        # AcpBackendOptions so Codex/OpenCode backends can include the
        # non-HTTP project-management tools in their tool catalog.
        self.project_store = project_store
        self.project_id = project_id
        self.task_tracker = task_tracker
        self.coordination_service = coordination_service
        self.task_identifier = task_identifier
        self.action_policy = action_policy
        self.policy_denial_handler = policy_denial_handler
        self.task_handoff_token = task_handoff_token
        # These values are intentionally passed to selected backend
        # environments.  Register them before the backend can emit a startup
        # event so an opaque token cannot leak through an innocuous payload.
        from oompah.secrets import register_configured_secrets, register_secret

        register_secret(task_handoff_token, expires_in=60 * 60)
        # Only register the explicit credential sources understood by the
        # service. Broad key-name heuristics would treat innocuous values such
        # as ``BUILD_KEY=1`` as process-wide secrets and could redact ordinary
        # diagnostics. Authoritative project/provider credentials are
        # registered by their stores; this covers the environment passed to
        # the backend without duplicating that policy here.
        register_configured_secrets(self.env)
        self.focus = focus
        self.auditor = auditor
        self.audit_target = audit_target
        self.audit_result_handler = audit_result_handler
        self.validation_reuse_policy = validation_reuse_policy
        self.validation_reuse_authority_check = validation_reuse_authority_check
        # This is the irreversible transport boundary owned by the
        # orchestrator.  It runs after local stop/setup checks but before the
        # backend's first ``run_turn`` call, which is the ACP contract's
        # provider/subprocess edge.  A rejected admission is deliberately not
        # transport evidence and must not poison provider health or spend.
        self.before_transport_contact = before_transport_contact
        self.on_precontact_admission_cancelled = on_precontact_admission_cancelled
        self.terminal_transition_coordinator = terminal_transition_coordinator
        # Mid-run comment injection queue (OOMPAH-211).
        self.comment_queue = comment_queue
        # A per-session monitor lets reconciliation distinguish a live,
        # bounded run_command child from silent model/prompt work.
        self.tool_liveness = tool_liveness
        self.validation_authority_generation = validation_authority_generation

        # Resolve the backend class at construction time so an
        # unregistered name fails fast rather than at dispatch time.
        backend_cls = get_backend_or_raise(self.backend_name)
        self._backend = backend_cls()
        self._backend_session: AcpBackendSession | None = None
        self._stop_requested = False
        self._transport_admitted = False
        self._transport_contacted = False
        # Live counters start at zero, which is not evidence that a paid
        # provider's final bill was zero.  These flags move only when a
        # terminal backend result is observed.
        self._final_usage_observed = False
        self._final_cost_observed = False
        # Surface a last_error attribute even when no session has run,
        # mirroring the legacy API. Cleared at run_task start, set by
        # the backend on failure.
        self.last_error: str | None = None
        # Permission denials are tracked by the SDK's ResultMessage; we
        # mirror the legacy attribute so callers (orchestrator,
        # dashboard) read it from the same field.
        self.permission_denials: list[Any] = []

    # ------------------------------------------------------------------
    # Public properties expected by orchestrator (mirrors api_agent)
    # ------------------------------------------------------------------

    @property
    def input_tokens(self) -> int:
        return (
            self._backend_session.input_tokens
            if self._backend_session is not None
            else 0
        )

    @property
    def output_tokens(self) -> int:
        return (
            self._backend_session.output_tokens
            if self._backend_session is not None
            else 0
        )

    @property
    def total_tokens(self) -> int:
        return (
            self._backend_session.total_tokens
            if self._backend_session is not None
            else 0
        )

    @property
    def session_id(self) -> str | None:
        return (
            self._backend_session.session_id
            if self._backend_session is not None
            else None
        )

    @property
    def turn_count(self) -> int:
        return (
            self._backend_session.turn_count
            if self._backend_session is not None
            else 0
        )

    @property
    def total_cost_usd(self) -> float | None:
        """Whatever the backend's terminal event reported (subscription-
        billed runs typically report 0 here; pay-as-you-go reports the
        real amount). Available only after the turn completes."""
        return (
            self._backend_session.total_cost_usd
            if self._backend_session is not None
            else None
        )

    @property
    def transport_contacted(self) -> bool:
        """Whether this session crossed its provider/subprocess boundary.

        ``start_session`` only constructs a local backend handle.  The first
        ``run_turn`` call is the backend contract's transport edge, so callers
        can reliably distinguish local startup/termination from a real
        provider outcome.
        """

        return self._transport_contacted

    @property
    def final_usage_observed(self) -> bool:
        """Whether a terminal backend usage envelope was observed."""

        return self._final_usage_observed

    @property
    def final_cost_observed(self) -> bool:
        """Whether that terminal envelope reported an exact numeric cost."""

        return self._final_cost_observed

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _cancel_precontact_admission(self) -> None:
        """Return a granted-but-unused contact permit to the orchestrator."""

        if not self._transport_admitted or self._transport_contacted:
            return
        self._transport_admitted = False
        if self.on_precontact_admission_cancelled is None:
            return
        try:
            self.on_precontact_admission_cancelled()
        except Exception:  # pragma: no cover - defensive authority cleanup
            logger.exception("Unable to roll back unused ACP contact admission")

    async def run_task(self) -> str:
        """Open a session, send the prompt, drive the message stream,
        return when the backend signals completion. Returns one of:

            * ``"succeeded"`` — terminal Result event with no error
            * ``"failed"`` — terminal Result event with an error
            * ``"stalled"`` — turn_timeout_s exceeded; subprocess killed
            * ``"interrupted"`` — orchestrator called ``terminate()``
            * ``"errored"`` — SDK / subprocess crashed unexpectedly

        ``on_event`` (if set on construction) is called with
        :class:`AgentEvent` for every interesting message — assistant
        text, tool use, tool result, permission grant. Mirrors the
        api_agent observation surface so per-agent JSONL logging plugs
        in unchanged.
        """
        # Honor a pre-run terminate(): tests rely on this exact ordering
        # to drive ``run_task`` into the interrupted branch.
        if self._stop_requested:
            return "interrupted"

        options = AcpBackendOptions(
            workspace_path=self.workspace_path,
            prompt=self.prompt,
            model=self.model,
            fallback_model=self.fallback_model,
            max_turns=self.max_turns,
            env=self.env or None,
            isolate_remote_write=self.isolate_remote_write,
            provider_auth_kind=self.provider_auth_kind,
            tool_catalog=list(self.tool_catalog) if self.tool_catalog else None,
            read_only=self.read_only,
            permission_mode=self.permission_mode,
            turn_timeout_s=self.turn_timeout_s,
            on_event=self.on_event,
            billing_model=self.billing_model,
            project_store=self.project_store,
            project_id=self.project_id,
            task_tracker=self.task_tracker,
            coordination_service=self.coordination_service,
            task_identifier=self.task_identifier,
            action_policy=self.action_policy,
            policy_denial_handler=self.policy_denial_handler,
            task_handoff_token=self.task_handoff_token,
            terminal_transition_coordinator=self.terminal_transition_coordinator,
            comment_queue=self.comment_queue,
            tool_liveness=self.tool_liveness,
            validation_authority_generation=self.validation_authority_generation,
            focus=self.focus,
            auditor=self.auditor,
            audit_target=self.audit_target,
            audit_result_handler=self.audit_result_handler,
            validation_reuse_policy=self.validation_reuse_policy,
            validation_reuse_authority_check=(
                self.validation_reuse_authority_check
            ),
            begin_transport_contact=self._begin_backend_transport_contact,
            transport_contacted=self._mark_backend_transport_contacted,
            cancel_transport_contact=self._cancel_precontact_admission,
        )

        try:
            self._backend_session = self._backend.start_session(options)
        except Exception as exc:
            # Backend construction itself failed (e.g. missing SDK).
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Failed to start ACP backend %r: %s",
                self.backend_name, self.last_error,
            )
            return "errored"

        # ``terminate()`` can race local backend construction.  Concrete
        # backends receive the contact callbacks above and invoke them only
        # at their actual SDK/network/Popen edge; never spend or publish
        # health merely because a local backend handle was constructed.
        if self._stop_requested:
            await self.terminate()
            return "interrupted"

        try:
            async for _ev in self._backend_session.run_turn():
                if getattr(_ev, "kind", None) in {"result", "acp_result"}:
                    # A terminal result is the backend's authoritative
                    # roll-up, including a legitimate all-zero report.  Do
                    # not infer this from initialized live counters.
                    self._final_usage_observed = True
                    payload = getattr(_ev, "payload", None)
                    if isinstance(payload, dict):
                        reported_cost = payload.get("total_cost_usd")
                        if isinstance(reported_cost, (int, float)) and not isinstance(
                            reported_cost, bool
                        ):
                            self._final_cost_observed = True
                # The command helper keeps liveness ownership in
                # ``result_pending`` until the backend has translated and
                # emitted the provider-visible tool result.  All ACP
                # backends converge on this event vocabulary, so the facade
                # is the single race-safe acknowledgement point.
                if getattr(_ev, "kind", None) == "tool_result":
                    mark_delivered = getattr(
                        self.tool_liveness,
                        "result_delivered",
                        None,
                    )
                    if callable(mark_delivered):
                        try:
                            mark_delivered()
                        except Exception:  # pragma: no cover - observer path
                            logger.debug(
                                "Unable to acknowledge ACP tool result",
                                exc_info=True,
                            )
                if self._stop_requested:
                    # The backend will see _stop_requested via close()
                    # and break out; but we also want to short-circuit
                    # the outer iteration so we don't block on a slow
                    # SDK shutdown.
                    return "interrupted"
            # run_turn exited cleanly; mirror back-compat attributes
            # from the backend session.
            self.last_error = self._backend_session.last_error
            self.permission_denials = list(
                self._backend_session.permission_denials
            )
            return self._backend_session.status
        except Exception as exc:
            # Defensive: a bug inside the backend that escaped its own
            # try/except shouldn't take down the orchestrator worker.
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "ACP backend %r crashed during run_turn: %s",
                self.backend_name, self.last_error,
            )
            return "errored"
        finally:
            # A backend that fails or is cancelled between admission and its
            # true edge cannot leave the durable audit reservation marked as
            # spend-eligible.  The helper is idempotent after real contact.
            self._cancel_precontact_admission()

    def _begin_backend_transport_contact(self) -> str | None:
        """Fence one concrete backend immediately before provider contact."""

        if self._stop_requested:
            return "ACP provider launch was cancelled before transport contact"
        if self.before_transport_contact is not None:
            error = self.before_transport_contact()
            if error is not None:
                return error
        self._transport_admitted = True
        # A lifecycle drain can win inside the admission callback.  Do not
        # let a backend cross its edge after that stop has become visible.
        if self._stop_requested:
            self._cancel_precontact_admission()
            return "ACP provider launch was cancelled before transport contact"
        return None

    def _mark_backend_transport_contacted(self) -> None:
        """Record actual backend contact, rather than assumed run_turn entry."""

        self._transport_contacted = True
        self._transport_admitted = False

    async def terminate(self) -> None:
        """Request that the active session stop. Safe to call multiple
        times. Idempotent. The backend session's ``close`` cleans up the
        subprocess; this just signals our drain loop to break."""
        self._stop_requested = True
        if self.tool_liveness is not None:
            request_cancel = getattr(self.tool_liveness, "request_cancel", None)
            if callable(request_cancel):
                request_cancel()
        backend_session = self._backend_session
        if backend_session is not None:
            try:
                await backend_session.close()
            except Exception as exc:  # pragma: no cover — defensive
                logger.debug("backend close raised: %s", exc)

    async def inject_message(self, text: str) -> bool:
        """Inject *text* into the running session for delivery at the next
        turn boundary (OOMPAH-211).

        Returns True when the backend session accepted the message, False when
        no session is active or the backend does not support injection (e.g.
        the CLI worker). Callers should treat False as a graceful fallback —
        the comment will be available on the next dispatch.
        """
        backend_session = self._backend_session
        if backend_session is None:
            return False
        inject = getattr(backend_session, "inject_message", None)
        if inject is None:
            # Backend does not support mid-run injection — graceful fallback.
            logger.debug(
                "Backend %r does not support inject_message; "
                "comment will be available on next dispatch",
                self.backend_name,
            )
            return False
        try:
            await inject(text)
            return True
        except Exception as exc:
            logger.warning("inject_message to backend %r failed: %s", self.backend_name, exc)
            return False
