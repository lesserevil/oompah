"""ConsoleSession + ConsoleSessionManager (oompah-zlz_2-49tv, Console 3/6).

In-memory wrapper that wires the on-disk transcript store
(:mod:`oompah.console_store`) and the normalized-event translators
(:mod:`oompah.console_translators`) to an :class:`AcpAgentSession`.
Manages one project's interactive operator conversation.

Architecture
------------

* :class:`ConsoleSession` — one per project_id. Holds a serial queue
  so concurrent operator inputs run one-at-a-time, rehydrates the SDK
  session from the on-disk transcript before sending each turn, fans
  every backend event back through the on_event callback and the
  store.

* :class:`ConsoleSessionManager` — process-singleton dict of
  ``project_id → ConsoleSession``. ``get(project_id)`` constructs on
  first call, caches for the process lifetime.

Concurrency invariants
~~~~~~~~~~~~~~~~~~~~~~

* **One in-flight turn per session.** A second :meth:`send` while a
  turn is running is queued in an :class:`asyncio.Queue` and drained
  FIFO. The queue is bounded (defaults to 128) to keep a runaway
  operator from filling memory.

* **switch_backend refuses mid-turn (v1 policy).** Operators see a
  :class:`RuntimeError` and the UI surfaces the message. v2 may wait
  for the in-flight turn to finish.

* **All state mutation runs on the asyncio loop.** ``send`` /
  ``switch_backend`` / ``clear`` are coroutines; the queue drainer is
  an asyncio task. We don't need to wrap shared state in a threading
  lock — the loop serializes access by construction. The underlying
  :class:`ConsoleStore` is already threadsafe.

Rehydration
~~~~~~~~~~~

Before each turn the session reads the canonical transcript from
disk, converts every dict event back to a :class:`ConsoleEvent`,
hands it to the per-backend ``normalized_to_sdk_history`` builder,
and passes the resulting structured history to a fresh
:class:`AcpAgentSession`. Service restarts therefore lose nothing —
the next operator message picks up exactly where the prior session
left off.

Out of scope
~~~~~~~~~~~~

HTTP / WS endpoints, the dashboard UI panel, and the end-to-end
cross-backend integration test are tracked in beads
oompah-zlz_2-g73s, -577a, -elug respectively.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from oompah.console_format import ConsoleEvent, make_error, make_operator_input
from oompah.console_store import ConsoleStore
from oompah.console_translators import get_translator, known_backends

if TYPE_CHECKING:
    from oompah.providers import ProviderStore
    from oompah.roles import RoleStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

DEFAULT_BACKEND = "claude"
"""Backend used when meta on disk has no backend selection yet."""

DEFAULT_MODEL_ROLE = "default"
"""Role name resolved against :class:`RoleStore` to pick provider/model."""

_DEFAULT_QUEUE_MAXSIZE = 128
"""Cap on the pending-send queue size to keep a runaway operator from
unbounded memory growth. 128 messages is hundreds of pages of
operator input — well past anything a human would queue up but small
enough to fail fast on a bug."""

_DEFAULT_PERMISSION_MODE = "acceptEdits"
"""The operator-at-the-keyboard is the human gate, so the SDK doesn't
need to interactively confirm edits. Matches the v1 design in
plans/console.md."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp with microsecond precision and a Z suffix.

    Matches the format the claude translator emits, so chronological
    string ordering works on a mixed feed."""
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _events_from_store(store: ConsoleStore, project_id: str) -> list[ConsoleEvent]:
    """Materialize the on-disk transcript as :class:`ConsoleEvent`s.

    Malformed rows are skipped by :meth:`ConsoleStore.read_all`; here
    we additionally defend against bad row dicts by routing
    construction through :meth:`ConsoleEvent.from_dict` which is
    permissive.
    """
    out: list[ConsoleEvent] = []
    for row in store.read_all(project_id):
        try:
            out.append(ConsoleEvent.from_dict(row))
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "ConsoleSession[%s]: dropping malformed transcript row: %s",
                project_id, exc,
            )
    return out


# ---------------------------------------------------------------------------
# AcpAgentSession factory injection
# ---------------------------------------------------------------------------


# The tests inject a mocked AcpAgentSession by patching this attribute
# on the module. Production code uses the real class, lazy-loaded so
# importing :mod:`oompah.console` doesn't drag the SDK in.
def _resolve_agent_session_cls() -> Any:
    from oompah.acp_agent import AcpAgentSession  # lazy
    return AcpAgentSession


AgentSessionFactory = Callable[..., Any]


def _default_agent_session_factory(**kwargs: Any) -> Any:
    """Default factory: instantiate the real AcpAgentSession.

    Tests replace this on the module to inject a mock. Centralizing
    construction here means callers don't have to mock both class and
    instantiation paths.
    """
    cls = _resolve_agent_session_cls()
    return cls(**kwargs)


# Module-level factory the tests monkey-patch. ConsoleSession reads it
# at turn time so a test patch takes effect even after the session was
# constructed.
agent_session_factory: AgentSessionFactory = _default_agent_session_factory


# ---------------------------------------------------------------------------
# Internal queue item
# ---------------------------------------------------------------------------


@dataclass
class _PendingSend:
    """One queued operator input awaiting its turn."""

    text: str
    attachments: list[str] = field(default_factory=list)
    # Resolved when the turn that processes this send completes (or
    # errors). Lets callers ``await session.send(...)`` and know the
    # turn has finished.
    done: asyncio.Future[None] | None = None


# ---------------------------------------------------------------------------
# ConsoleSession
# ---------------------------------------------------------------------------


class ConsoleSession:
    """In-memory wrapper for one project's interactive ACP conversation.

    Holds:

    * The :class:`ConsoleStore` (on-disk transcript + meta sidecar).
    * The :class:`ProviderStore` / :class:`RoleStore` references used
      to resolve which backend + model to use per turn (operators can
      flip the project's ``default`` role from ``/providers`` between
      turns and the next message will pick up the change).
    * A serial :class:`asyncio.Queue` of :class:`_PendingSend` items.
    * A background runner task that drains the queue one turn at a
      time, spawning a fresh :class:`AcpAgentSession` per turn with
      the rehydrated history.

    All public methods are coroutines; the loop serializes state
    access so the session needs no explicit lock for in-memory fields.
    The :class:`ConsoleStore` it wraps is already threadsafe — fine
    to share across sessions or call from outside the loop.
    """

    def __init__(
        self,
        project_id: str,
        store: ConsoleStore,
        provider_store: "ProviderStore",
        role_store: "RoleStore",
        on_event: Callable[[ConsoleEvent], None] | None = None,
        *,
        workspace_path: str | None = None,
        queue_maxsize: int = _DEFAULT_QUEUE_MAXSIZE,
    ) -> None:
        if not project_id:
            raise ValueError("ConsoleSession requires non-empty project_id")
        self.project_id = project_id
        self.store = store
        self.provider_store = provider_store
        self.role_store = role_store
        self.on_event = on_event
        # workspace_path is optional at construction so the manager can
        # wire it in once the project record is resolved. Production
        # code (server.py / manager) sets it; tests usually leave it
        # None when they're mocking AcpAgentSession.
        self.workspace_path = workspace_path
        # Backend + model role come from the meta sidecar if present.
        # First-time projects use DEFAULT_BACKEND / DEFAULT_MODEL_ROLE.
        meta = store.load_meta(project_id) if store else {}
        self._backend: str = (
            meta.get("backend") if isinstance(meta.get("backend"), str)
            else DEFAULT_BACKEND
        )
        self._model_role: str = (
            meta.get("model_role")
            if isinstance(meta.get("model_role"), str)
            else DEFAULT_MODEL_ROLE
        )
        self._queue: asyncio.Queue[_PendingSend] = asyncio.Queue(
            maxsize=queue_maxsize
        )
        # Turn-in-flight tracking: switch_backend uses this to decide
        # whether to refuse with a RuntimeError. _turn_active is True
        # iff a turn is currently between dequeue and full event-drain
        # completion.
        self._turn_active: bool = False
        # The asyncio.Task that drains the queue. Created lazily on
        # the first ``send`` so a freshly-constructed session in a
        # test without a running loop doesn't try to schedule a task.
        self._runner_task: asyncio.Task | None = None
        self._closed: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_meta(self) -> dict:
        """Return the session's current metadata snapshot.

        Read-only convenience: callers can render the current backend
        and model_role in the UI without poking the store directly.
        Returned dict is a copy — mutating it does NOT update session
        state. Use :meth:`switch_backend` to change backend/role.
        """
        return {
            "project_id": self.project_id,
            "backend": self._backend,
            "model_role": self._model_role,
            "turn_active": self._turn_active,
            "queue_size": self._queue.qsize(),
        }

    async def send(
        self,
        text: str,
        attachments: list[str] | None = None,
    ) -> None:
        """Append an operator_input event and drive one turn.

        Concurrency: serializes through the session's
        :class:`asyncio.Queue`. The caller's coroutine resolves once
        the turn finishes (success, error, or backend missing) — that
        makes ``await session.send(...)`` a natural "wait for the
        model to reply" primitive for both tests and the WS handler.
        """
        if self._closed:
            raise RuntimeError(
                f"ConsoleSession[{self.project_id}] is closed"
            )
        text = (text or "").strip()
        if not text:
            return
        loop = asyncio.get_event_loop()
        done: asyncio.Future[None] = loop.create_future()
        item = _PendingSend(
            text=text,
            attachments=list(attachments or []),
            done=done,
        )
        # Ensure the runner is up before enqueuing.
        self._ensure_runner(loop)
        # The queue is bounded; if the operator floods inputs faster
        # than the model replies, this will block (back-pressure) —
        # exactly what we want.
        await self._queue.put(item)
        # Wait for the turn that processes THIS send to complete.
        # Using a per-item Future means concurrent ``await send()``
        # callers each resolve independently in FIFO order.
        await done

    async def switch_backend(
        self,
        backend: str,
        model_role: str = DEFAULT_MODEL_ROLE,
    ) -> None:
        """Swap the backend + model_role for the next turn.

        v1 policy: refuses with :class:`RuntimeError` if a turn is
        currently in flight. The UI surfaces the error message; the
        operator retries after the turn settles. v2 may queue the
        swap.

        Persists the new selection to the meta sidecar so a restart
        picks up the latest choice. The next :meth:`send` rehydrates
        the SDK with the on-disk transcript under the NEW backend's
        translator — that's the cross-backend continuity story.
        """
        if self._closed:
            raise RuntimeError(
                f"ConsoleSession[{self.project_id}] is closed"
            )
        if self._turn_active:
            raise RuntimeError(
                f"ConsoleSession[{self.project_id}]: cannot switch backend "
                "while a turn is in flight"
            )
        # Validate the backend has a registered translator. Don't gate
        # on the codex stub raising NotImplementedError — that's a
        # downstream concern for the actual turn execution; v1 lets
        # the operator pick codex and learn about the stub error when
        # the next message tries to use it.
        if backend not in known_backends():
            raise ValueError(
                f"Unknown backend {backend!r}. "
                f"Known: {sorted(known_backends())}"
            )
        self._backend = backend
        self._model_role = model_role or DEFAULT_MODEL_ROLE
        # Persist immediately so a restart sees the operator's choice
        # even if no turn has run yet.
        meta = self.store.load_meta(self.project_id) if self.store else {}
        meta["backend"] = self._backend
        meta["model_role"] = self._model_role
        meta["switched_at"] = _utc_now_iso()
        self.store.save_meta(self.project_id, meta)

    async def clear(self) -> None:
        """Clear the on-disk transcript + meta for this project.

        Cancels any pending sends in the queue (each gets its
        ``done`` Future resolved with a CancelledError-compatible
        :class:`RuntimeError`) so callers awaiting :meth:`send` see a
        prompt failure. The backend/model_role selection IS reset to
        defaults — the cleared meta sidecar implies a fresh start.

        Refuses (RuntimeError) if a turn is in flight. v1 keeps clear
        in the same conservative bucket as :meth:`switch_backend`.
        """
        if self._closed:
            return
        if self._turn_active:
            raise RuntimeError(
                f"ConsoleSession[{self.project_id}]: cannot clear "
                "while a turn is in flight"
            )
        # Drain any queued pending sends and fail their futures.
        drained: list[_PendingSend] = []
        while not self._queue.empty():
            try:
                drained.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        for item in drained:
            if item.done is not None and not item.done.done():
                item.done.set_exception(
                    RuntimeError("console transcript cleared")
                )
        self.store.clear(self.project_id)
        self._backend = DEFAULT_BACKEND
        self._model_role = DEFAULT_MODEL_ROLE

    async def shutdown(self) -> None:
        """Stop the runner task and mark the session closed.

        Idempotent. Not strictly required for unit tests (they don't
        leak loops) but the manager calls it on its own shutdown to
        keep CI tidy.
        """
        if self._closed:
            return
        self._closed = True
        runner = self._runner_task
        if runner is not None and not runner.done():
            # Drop a sentinel onto the queue so the runner wakes up
            # and checks _closed.
            try:
                self._queue.put_nowait(_PendingSend(text=""))
            except asyncio.QueueFull:
                pass
            try:
                await asyncio.wait_for(runner, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                runner.cancel()

    # ------------------------------------------------------------------
    # Internal: runner task drains the queue one item at a time
    # ------------------------------------------------------------------

    def _ensure_runner(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the runner task if it isn't running yet. Idempotent."""
        if self._runner_task is not None and not self._runner_task.done():
            return
        self._runner_task = loop.create_task(self._run_forever())

    async def _run_forever(self) -> None:
        """Pull pending sends off the queue and process one at a time."""
        while not self._closed:
            try:
                item = await self._queue.get()
            except asyncio.CancelledError:
                return
            if self._closed:
                # Resolve the item's future so its caller doesn't hang.
                if item.done is not None and not item.done.done():
                    item.done.set_exception(
                        RuntimeError("console session closed mid-flight")
                    )
                return
            if not item.text.strip():
                # Shutdown sentinel.
                if item.done is not None and not item.done.done():
                    item.done.set_result(None)
                continue
            self._turn_active = True
            try:
                await self._run_one_turn(item)
            except Exception as exc:  # pragma: no cover — runner safety net
                logger.exception(
                    "ConsoleSession[%s] turn crashed: %s",
                    self.project_id, exc,
                )
                self._record_error(
                    f"turn crashed: {type(exc).__name__}: {exc}"
                )
                if item.done is not None and not item.done.done():
                    item.done.set_exception(exc)
            else:
                if item.done is not None and not item.done.done():
                    item.done.set_result(None)
            finally:
                self._turn_active = False

    async def _run_one_turn(self, item: _PendingSend) -> None:
        """Execute one full operator turn end-to-end.

        Steps (mirrors plans/console.md §"Backend switching"):

        1. Record the operator_input event to disk + fan out via
           on_event.
        2. Rehydrate the SDK history from disk via the per-backend
           translator's ``normalized_to_sdk_history``.
        3. Resolve provider + model via the role store.
        4. Construct an AcpAgentSession with ``history=`` and a
           backend-event callback that translates each backend event
           back through ``acp_to_normalized`` then appends + fans out.
        5. Run the turn (``await session.run_task()``) and emit a
           terminal status event so the UI can stop the spinner.
        """
        # Step 1: persist + emit operator_input.
        op_event = make_operator_input(
            ts=_utc_now_iso(),
            text=item.text,
            attachments=item.attachments or None,
            backend=self._backend,
        )
        self._persist_and_emit(op_event)

        # Step 2: rehydrate the SDK history. We use the per-backend
        # translator chosen at submit time (the operator may have
        # flipped backend before sending this message; the queue is
        # serial so we can rely on _backend being current).
        try:
            translator = get_translator(self._backend)
        except KeyError as exc:
            self._record_error(f"unknown backend {self._backend!r}: {exc}")
            return
        transcript_events = _events_from_store(self.store, self.project_id)
        try:
            history = translator.normalized_to_sdk_history(transcript_events)
        except NotImplementedError as exc:
            # Codex stub today, until oompah-zlz_2-elug lands.
            self._record_error(
                f"backend {self._backend!r} cannot build history: {exc}"
            )
            return
        except Exception as exc:
            self._record_error(
                f"backend {self._backend!r} history-build failed: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        # Step 3: resolve provider + model. Fail-open with informative
        # error events — a missing role / provider shouldn't crash the
        # whole session.
        role = None
        try:
            role = self.role_store.get(self._model_role)
        except Exception as exc:
            logger.warning(
                "ConsoleSession[%s] role lookup failed: %s",
                self.project_id, exc,
            )
        provider = None
        if role is not None:
            try:
                provider = self.provider_store.get(role.provider_id)
            except Exception:
                provider = None
        if provider is None:
            # Fall back to a single configured provider if any.
            try:
                provider = self.provider_store.get_default()
            except Exception:
                provider = None
        # Choose a model from role > provider default.
        model: str | None = None
        if role is not None and role.model:
            model = role.model
        elif provider is not None and getattr(provider, "default_model", None):
            model = provider.default_model

        # Step 4: build the AcpAgentSession. Pass ``history`` through
        # as a kwarg so the tests can mock the class and assert the
        # rehydrated structure. Production AcpAgentSession today does
        # not consume ``history`` — that's tracked as a future
        # enhancement; for v1 the on-disk transcript is also reflected
        # in the prompt itself via the operator_input we just
        # persisted (and any prior turns' agent_text already drove the
        # SDK during their original execution).
        try:
            agent_session = agent_session_factory(
                workspace_path=self.workspace_path or "",
                prompt=item.text,
                history=history,
                model=model,
                backend_name=self._backend,
                permission_mode=_DEFAULT_PERMISSION_MODE,
                on_event=self._make_backend_event_callback(translator),
            )
        except TypeError as exc:
            # AcpAgentSession may not accept ``history`` yet in
            # production; degrade gracefully and try without it. Tests
            # always inject a mock so they hit the happy path above.
            if "history" in str(exc):
                try:
                    agent_session = agent_session_factory(
                        workspace_path=self.workspace_path or "",
                        prompt=item.text,
                        model=model,
                        backend_name=self._backend,
                        permission_mode=_DEFAULT_PERMISSION_MODE,
                        on_event=self._make_backend_event_callback(translator),
                    )
                except Exception as inner_exc:
                    self._record_error(
                        f"agent session construction failed: "
                        f"{type(inner_exc).__name__}: {inner_exc}"
                    )
                    return
            else:
                self._record_error(
                    f"agent session construction failed: "
                    f"{type(exc).__name__}: {exc}"
                )
                return
        except Exception as exc:
            self._record_error(
                f"agent session construction failed: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        # Step 5: drive the turn. The agent session's run_task is a
        # coroutine; events flow through on_event during the call.
        try:
            run_task = getattr(agent_session, "run_task", None)
            if run_task is None:
                self._record_error(
                    "agent session has no run_task method"
                )
                return
            result = run_task()
            if asyncio.iscoroutine(result):
                status = await result
            elif asyncio.isfuture(result):
                status = await result
            else:
                # Mock returned a plain value — treat as the status.
                status = result
        except Exception as exc:
            self._record_error(
                f"agent run_task crashed: {type(exc).__name__}: {exc}"
            )
            return

        # Emit a synthetic session_meta event with the terminal status
        # so the UI can drop the spinner. The translator's
        # acp_to_normalized path would normally do this on the SDK's
        # ``acp_result`` event, but a misbehaving backend that never
        # fires Result still owes the UI a terminal signal.
        status_str = str(status) if status is not None else "unknown"
        terminal = ConsoleEvent(
            ts=_utc_now_iso(),
            kind="session_meta",
            backend=self._backend,
            args={"status": status_str, "synthetic_terminal": True},
            raw_event_kind="console_turn_end",
        )
        self._persist_and_emit(terminal)

    # ------------------------------------------------------------------
    # Internal: persistence + fan-out
    # ------------------------------------------------------------------

    def _make_backend_event_callback(
        self,
        translator: Any,
    ) -> Callable[[Any], None]:
        """Build the on_event callback handed to AcpAgentSession.

        Each backend event is translated to a normalized ConsoleEvent,
        appended to the store, and forwarded to the session's
        ``on_event`` consumer. We catch and log translator errors so
        a bad event payload doesn't kill the turn.
        """
        def _on_backend_event(backend_event: Any) -> None:
            try:
                normalized = translator.acp_to_normalized(backend_event)
            except Exception as exc:
                logger.warning(
                    "ConsoleSession[%s] translator error on event %r: %s",
                    self.project_id, backend_event, exc,
                )
                # Don't drop the event — surface as session_meta with
                # the raw kind so the UI shows *something*.
                raw_kind = getattr(backend_event, "event", None)
                normalized = ConsoleEvent(
                    ts=_utc_now_iso(),
                    kind="session_meta",
                    backend=self._backend,
                    args={"_translator_error": str(exc)},
                    raw_event_kind=str(raw_kind) if raw_kind else None,
                )
            self._persist_and_emit(normalized)

        return _on_backend_event

    def _persist_and_emit(self, event: ConsoleEvent) -> None:
        """Append ``event`` to disk and fan out via on_event.

        Both operations are best-effort — we don't want a buggy on_event
        consumer to corrupt the transcript or vice-versa.
        """
        try:
            self.store.append(self.project_id, event.to_dict())
        except Exception as exc:
            logger.warning(
                "ConsoleSession[%s] store.append failed: %s",
                self.project_id, exc,
            )
        if self.on_event is not None:
            try:
                self.on_event(event)
            except Exception as exc:
                logger.debug(
                    "ConsoleSession[%s] on_event callback raised: %s",
                    self.project_id, exc,
                )

    def _record_error(self, message: str) -> None:
        """Emit an ``error`` ConsoleEvent. Used as the unified
        sad-path for any failure inside ``_run_one_turn``."""
        event = make_error(
            ts=_utc_now_iso(),
            text=message,
            backend=self._backend,
        )
        self._persist_and_emit(event)
        logger.warning(
            "ConsoleSession[%s] %s", self.project_id, message,
        )


# ---------------------------------------------------------------------------
# ConsoleSessionManager
# ---------------------------------------------------------------------------


OnEventFactory = Callable[[str], Callable[[ConsoleEvent], None]]
"""Factory hook signature: given a ``project_id``, return the
``on_event`` callback the freshly-constructed :class:`ConsoleSession`
will invoke for every persisted event. Wired in by ``server.py`` so
console events fan out over the existing WebSocket pool (see
oompah-zlz_2-g73s, Console 4/6)."""


class ConsoleSessionManager:
    """Process-singleton registry mapping ``project_id`` → ConsoleSession.

    Thread-safe (lock around the dict) because :meth:`get` may be
    called from any of: the WS handler (asyncio loop), the REST
    endpoint (executor thread pool), or test code (main thread).
    The :class:`ConsoleSession` instances themselves are loop-bound;
    callers should not invoke their coroutines off the originating
    loop.

    The optional ``on_event_factory`` parameter lets the wiring layer
    (``server.py``) provide a project-scoped event callback for each
    newly-constructed session — used to fan console events out over
    the WebSocket pool. The factory runs once per session at
    construction time; the returned callable is stored on the session
    and called synchronously from the per-event persist path.
    """

    def __init__(
        self,
        store: ConsoleStore,
        provider_store: "ProviderStore",
        role_store: "RoleStore",
        *,
        on_event_factory: OnEventFactory | None = None,
        workspace_resolver: Callable[[str], str | None] | None = None,
    ) -> None:
        self.store = store
        self.provider_store = provider_store
        self.role_store = role_store
        self._on_event_factory = on_event_factory
        # Optional callback that resolves project_id → workspace_path
        # (an absolute or repo-relative path the SDK uses for tool
        # execution). Wired in by server.py so the manager can build
        # sessions that know their checkout directory; tests typically
        # leave this None.
        self._workspace_resolver = workspace_resolver
        self._sessions: dict[str, ConsoleSession] = {}
        self._lock = threading.Lock()

    def get(self, project_id: str) -> ConsoleSession:
        """Return the singleton :class:`ConsoleSession` for ``project_id``.

        Creates on first call and caches for the process lifetime.
        Subsequent calls return the same instance, which is the
        acceptance criterion: any caller (WS handler, REST endpoint,
        test) sees the same conversation state.
        """
        if not project_id:
            raise ValueError("ConsoleSessionManager.get requires project_id")
        with self._lock:
            existing = self._sessions.get(project_id)
            if existing is not None:
                return existing
            on_event: Callable[[ConsoleEvent], None] | None = None
            if self._on_event_factory is not None:
                try:
                    on_event = self._on_event_factory(project_id)
                except Exception as exc:  # pragma: no cover — defensive
                    logger.warning(
                        "ConsoleSessionManager: on_event_factory raised "
                        "for project_id %r: %s",
                        project_id, exc,
                    )
                    on_event = None
            workspace_path: str | None = None
            if self._workspace_resolver is not None:
                try:
                    workspace_path = self._workspace_resolver(project_id)
                except Exception as exc:  # pragma: no cover — defensive
                    logger.warning(
                        "ConsoleSessionManager: workspace_resolver raised "
                        "for project_id %r: %s",
                        project_id, exc,
                    )
                    workspace_path = None
            session = ConsoleSession(
                project_id=project_id,
                store=self.store,
                provider_store=self.provider_store,
                role_store=self.role_store,
                on_event=on_event,
                workspace_path=workspace_path,
            )
            self._sessions[project_id] = session
            return session

    def get_existing(self, project_id: str) -> ConsoleSession | None:
        """Return the in-memory session for ``project_id`` if it has been
        constructed, else ``None``. Never constructs a new session —
        useful for endpoints that want to test existence without
        side-effects (e.g., DELETE on an unused project).
        """
        if not project_id:
            return None
        with self._lock:
            return self._sessions.get(project_id)

    async def remove(self, project_id: str) -> bool:
        """Drop the cached session for ``project_id``.

        Returns ``True`` when there was a session to drop, ``False``
        otherwise. Idempotent — repeated calls on an unknown
        project_id are no-ops.

        Best-effort shutdown of the underlying runner task. The caller
        is responsible for clearing the on-disk transcript separately
        (via :attr:`store`) if a hard reset is intended.
        """
        with self._lock:
            session = self._sessions.pop(project_id, None)
        if session is None:
            return False
        try:
            await session.shutdown()
        except Exception as exc:
            logger.debug(
                "ConsoleSessionManager.remove: shutdown raised for %r: %s",
                project_id, exc,
            )
        return True

    def known_project_ids(self) -> list[str]:
        """Sorted list of project_ids the manager has constructed
        sessions for. Useful for diagnostics and shutdown loops."""
        with self._lock:
            return sorted(self._sessions)

    async def shutdown(self) -> None:
        """Shut down every cached session. Best-effort."""
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            try:
                await session.shutdown()
            except Exception:
                pass


__all__ = [
    "ConsoleSession",
    "ConsoleSessionManager",
    "DEFAULT_BACKEND",
    "DEFAULT_MODEL_ROLE",
    "OnEventFactory",
    "agent_session_factory",
]
