"""LEGACY per-project persistent ACP console session (umbrella ship of
oompah-zlz_2-ebwe).

.. note::

    This file is the inline implementation the umbrella epic shipped
    before the modular design (ConsoleStore / ConsoleEvent /
    translators / ConsoleSession) landed via the child tasks. New code
    should use :mod:`oompah.console` (the new ConsoleSession +
    ConsoleSessionManager built per the task spec in
    oompah-zlz_2-49tv). This module is kept around so
    :mod:`oompah.server` and existing tests for the umbrella code keep
    working; HTTP/WS endpoints will be swung over to the new design in
    task oompah-zlz_2-g73s (Console 4/6).

Provides the operator with a first-class interactive ACP session inside
the dashboard, using the same SDK and tool catalog as the worker
dispatch path. Each project has ONE console session keyed by
``project_id``; every dashboard browser viewing that project sees the
same transcript and contributes to the same conversation.

Architecture (see issue oompah-zlz_2-ebwe for the design discussion):

* :class:`ConsoleStore` — owns the per-project JSONL transcript at
  ``.oompah/console/<project_id>.jsonl``. Append-only event log
  identical in shape to the JSONL the worker path writes (one event
  per line, ``{"ts", "kind", "payload", "usage"?}``).

* :class:`ConsoleSession` — per-project session orchestrator. Owns an
  asyncio.Queue so concurrent operator inputs serialize naturally
  (second message queues server-side until the first turn completes).
  For each input, it builds a fresh :class:`AcpAgentSession` whose
  prompt embeds the full transcript as context (replay-on-every-turn).
  This means: service restarts do NOT lose context — the transcript on
  disk IS the source of truth for the conversation.

* :class:`ConsoleManager` — global singleton holding one
  :class:`ConsoleSession` per ``project_id`` and one shared event
  fan-out callback that the server wires to its WebSocket pool.

Key decisions:

* **Replay-on-every-turn** rather than "replay-once-after-restart, then
  in-memory". The Claude Agent SDK / openai-agents SDKs both treat
  ``ClaudeSDKClient`` (or its Codex analog) as session-shaped, but
  oompah's ``AcpAgentSession`` is single-turn (prompt-in, response-out).
  Reusing the worker path's machinery means replaying the transcript
  each turn — slightly more tokens, vastly simpler. The transcript JSONL
  is the canonical state; in-memory is just a cache for fast renders.

* **Per-input serialization** via :class:`asyncio.Queue`. v1 just queues;
  v2 could surface "X is typing" via the WS. The queue runs forever in
  the background of the FastAPI process — no per-request spawn cost.

* **Tool catalog comes from acp_tools.build_*_catalog** (the same one
  workers use). Permission mode is ``acceptEdits`` (operator is the
  human gate sitting in front of the browser). Working dir is the
  project's ``repo_path``.

* **Backend selection per project** via the existing provider/role
  machinery: project's ``default`` role -> provider -> provider.backend.
  Falls back to ``"claude"`` for back-compat with providers that don't
  specify a backend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator

logger = logging.getLogger(__name__)

# Default location for the per-project transcript directory. Mirrors the
# DEFAULT_SERVICE_STATE_PATH / DEFAULT_AGENT_PROFILES_PATH conventions:
# ``.oompah/<...>`` relative to the cwd of the running service. Tests
# override this via the OOMPAH_CONSOLE_DIR env var (see
# tests/conftest.py's pattern for agent_profile_store).
DEFAULT_CONSOLE_DIR = ".oompah/console"

# Per-event payload size cap applied at JSONL append time. The acp_*
# events already truncate their inner text/detail fields, but we still
# cap the whole serialized event to avoid pathological run_command
# outputs (e.g. a binary blob) blowing up the on-disk file.
_MAX_EVENT_BYTES = 64 * 1024


# ----------------------------------------------------------------------
# ConsoleStore — per-project JSONL transcript
# ----------------------------------------------------------------------


def _now_iso() -> str:
    """ISO-8601 timestamp (UTC, second precision)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _resolve_console_dir(base_dir: str | None) -> str:
    """Pick the console directory.

    Priority: explicit ``base_dir`` argument > ``OOMPAH_CONSOLE_DIR``
    env var > ``DEFAULT_CONSOLE_DIR`` (``.oompah/console``). Returned
    path is NOT created here — :class:`ConsoleStore` does that lazily.
    """
    if base_dir:
        return base_dir
    return os.environ.get("OOMPAH_CONSOLE_DIR") or DEFAULT_CONSOLE_DIR


class ConsoleStore:
    """Append-only JSONL transcript for one project.

    File path: ``<base_dir>/<project_id>.jsonl``. Each line is a JSON
    object with at minimum ``ts`` (ISO-8601) and ``kind`` (string);
    most events also have ``payload`` (dict) and ``usage`` (dict).

    Operator inputs are recorded as ``kind="operator_input"`` with
    payload ``{"text": "...", "attachments": [...]}``. Agent events
    are recorded with their backend kind (``acp_text``, ``acp_tool_use``,
    ``acp_result``, etc.) so the same UI rendering used for worker
    activity logs applies.

    File is opened lazily on first write and closed on
    :meth:`close` — long-lived sessions keep the FD open for the
    process lifetime, which is intentional (avoids open/fsync per event).
    """

    def __init__(self, project_id: str, *, base_dir: str | None = None):
        if not project_id:
            raise ValueError("ConsoleStore requires non-empty project_id")
        # Sanitize: project_id is operator-supplied so we forbid path
        # separators to keep the file inside base_dir. Real project IDs
        # are slugs (e.g. "proj-3e4e9214") so this never trips in
        # practice — it's just a defense against a misconfigured caller.
        if os.sep in project_id or "/" in project_id or "\\" in project_id:
            raise ValueError(
                f"project_id {project_id!r} contains path separator"
            )
        if project_id in ("", ".", ".."):
            raise ValueError(f"project_id {project_id!r} is not allowed")
        self.project_id = project_id
        self._base_dir = _resolve_console_dir(base_dir)
        self.path = os.path.join(self._base_dir, f"{project_id}.jsonl")
        self._lock = threading.Lock()
        self._fp: Any = None  # opened lazily

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        os.makedirs(self._base_dir, exist_ok=True)

    def _ensure_fp(self):
        if self._fp is None:
            self._ensure_dir()
            self._fp = open(self.path, "a", encoding="utf-8")
        return self._fp

    def append(
        self,
        kind: str,
        payload: dict[str, Any] | None = None,
        *,
        usage: dict[str, Any] | None = None,
        ts: str | None = None,
    ) -> dict[str, Any]:
        """Append one event to the JSONL transcript and return it.

        The returned dict is the canonical event shape used by the
        broadcast layer (WebSocket fan-out) and by callers that want
        to keep a parallel in-memory view.
        """
        event: dict[str, Any] = {
            "ts": ts or _now_iso(),
            "kind": kind,
            "payload": payload or {},
        }
        if usage:
            event["usage"] = usage
        serialized = json.dumps(event, default=str)
        if len(serialized) > _MAX_EVENT_BYTES:
            # Drop payload to keep the line small; preserve the kind +
            # a marker so consumers can see something happened.
            trimmed = {
                "ts": event["ts"],
                "kind": kind,
                "payload": {
                    "_truncated": True,
                    "_reason": (
                        f"event exceeded {_MAX_EVENT_BYTES} bytes "
                        f"(was {len(serialized)})"
                    ),
                },
            }
            if usage:
                trimmed["usage"] = usage
            event = trimmed
            serialized = json.dumps(event, default=str)
        with self._lock:
            fp = self._ensure_fp()
            fp.write(serialized + "\n")
            fp.flush()
        return event

    def read_all(self) -> list[dict[str, Any]]:
        """Return every event currently on disk, oldest first.

        Missing file -> empty list. Malformed JSONL lines are skipped
        with a WARNING (a partial write or a hand-edited file shouldn't
        crash the read path).
        """
        if not os.path.exists(self.path):
            return []
        events: list[dict[str, Any]] = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        logger.warning(
                            "Skipping malformed line %d in %s: %s",
                            lineno, self.path, exc,
                        )
        except OSError as exc:
            logger.warning("Failed to read %s: %s", self.path, exc)
            return []
        return events

    def read_page(
        self,
        *,
        limit: int = 200,
        before: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return up to ``limit`` events, with optional pagination.

        ``before`` is a 0-indexed position into the chronologically-
        ordered events list; events strictly BEFORE that index are
        returned (so the caller can scroll back). Returns the
        page-tuple ``(events, total_count)`` where total_count is the
        full length of the transcript on disk (handy for the UI to
        show "showing 50 of 327").
        """
        all_events = self.read_all()
        total = len(all_events)
        if before is None:
            # Default: latest ``limit`` events (newest end of the file).
            page = all_events[-limit:]
        else:
            end = max(0, int(before))
            start = max(0, end - limit)
            page = all_events[start:end]
        return page, total

    def close(self) -> None:
        """Close the underlying file descriptor. Idempotent."""
        with self._lock:
            fp = self._fp
            self._fp = None
            if fp is not None:
                try:
                    fp.close()
                except Exception:  # pragma: no cover — defensive
                    pass


# ----------------------------------------------------------------------
# ConsoleSession — orchestrates AcpAgentSession spawns per operator turn
# ----------------------------------------------------------------------


# Caller-supplied callback that resolves the (backend_name, model,
# permission_mode, env) tuple for a fresh ACP turn at the time of the
# turn, NOT at session construction. This lets operators flip the
# project's default role from the /providers page and have the next
# console message pick up the new backend without a restart.
ResolveBackendFn = Callable[[str], dict[str, Any]]

# Caller-supplied callback that fans out a console_event to WS clients.
# Signature: (project_id, event_dict) -> None. Implementations are
# expected to schedule the broadcast onto an event loop themselves.
BroadcastFn = Callable[[str, dict[str, Any]], None]


def _truncate(value: Any, limit: int = 2000) -> Any:
    """Mirror the truncation used by acp_backends.claude._truncate_for_log
    but inlined to avoid importing the backend module at console-load
    time."""
    if isinstance(value, str):
        return value if len(value) <= limit else (value[:limit] + " …[truncated]")
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v, limit) for v in value]
    return value


def render_transcript_as_prompt(
    transcript: list[dict[str, Any]],
    *,
    new_input: str,
    project_name: str | None = None,
    tools_summary: str | None = None,
    max_history_events: int = 200,
) -> str:
    """Build the prompt body fed to the next AcpAgentSession.

    Embeds the recent transcript so the model has full conversational
    context. ``new_input`` is appended at the end as the operator's
    latest message — that's what the model is responding to.

    We intentionally keep this rendering format simple and stable:
    each event maps to one line tagged with its role
    (Operator: / Assistant: / tool-use: / tool-result:). The Claude
    SDK / openai-agents SDK both treat the prompt as opaque text;
    structured replay would require a tighter coupling we don't need
    for v1.
    """
    lines: list[str] = []
    header_parts = ["You are the interactive ACP console for"]
    if project_name:
        header_parts.append(f"the {project_name!r} project")
    else:
        header_parts.append("an oompah project")
    header_parts.append(
        ". You're talking to a human operator through the dashboard. "
        "Be concise and direct. When the operator asks you to do something "
        "(close tasks, run commands, edit files), use the available tools. "
        "Keep prose readable in a terminal-sized panel."
    )
    lines.append("".join(header_parts))
    if tools_summary:
        lines.append(f"Tools: {tools_summary}")
    lines.append("")

    # Limit how much history we replay to keep prompts bounded; oldest
    # events get dropped first. The UI shows the full transcript still
    # — this just bounds the model's context window.
    if len(transcript) > max_history_events:
        skipped = len(transcript) - max_history_events
        history = transcript[-max_history_events:]
        lines.append(
            f"[Earlier {skipped} events elided from prompt; visible in UI.]"
        )
    else:
        history = transcript

    for ev in history:
        kind = ev.get("kind", "")
        payload = ev.get("payload") or {}
        if kind == "operator_input":
            text = (payload.get("text") or "").strip()
            if text:
                lines.append(f"Operator: {text}")
        elif kind in ("acp_text",):
            text = (payload.get("text") or "").strip()
            if text:
                lines.append(f"Assistant: {text}")
        elif kind == "acp_thinking":
            # Skip thinking blocks — they're internal scratch space and
            # replaying them tends to confuse the next turn.
            continue
        elif kind == "acp_tool_use":
            tool = payload.get("tool", "?")
            tool_input = payload.get("input")
            args = json.dumps(tool_input, default=str)[:200] \
                if tool_input is not None else ""
            lines.append(f"[tool-use {tool}: {args}]")
        elif kind == "acp_tool_result":
            content = str(payload.get("content", ""))[:300]
            lines.append(f"[tool-result: {content}]")
        elif kind == "acp_session_start":
            # Don't replay session-start headers — they'd accumulate
            # and confuse the model.
            continue
        elif kind == "acp_result":
            # Terminal events also skipped.
            continue
        # Unknown / metadata events ignored.

    lines.append("")
    lines.append(f"Operator: {new_input.strip()}")
    lines.append("")
    lines.append("Assistant:")
    return "\n".join(lines)


@dataclass
class _InputItem:
    """One queued operator turn."""
    text: str
    attachments: list[str] = field(default_factory=list)
    # Optional Future to wake up the caller when the turn finishes.
    # ConsoleManager.submit() awaits this in test mode; in production
    # the WS path doesn't wait — events flow asynchronously.
    done: asyncio.Future | None = None


class ConsoleSession:
    """One project's persistent console session.

    Holds:

    * The :class:`ConsoleStore` (transcript on disk).
    * An asyncio.Queue of pending operator inputs.
    * A background "runner" task that drains the queue, spawning a
      fresh AcpAgentSession per turn.
    * A list of in-memory events used by the read path while the queue
      is being drained (so reads-after-write are consistent without a
      round-trip to disk).

    Lifecycle:

    * :meth:`submit` enqueues an operator turn. Returns once the entry
      is in the queue; the actual model call happens off the caller's
      thread.
    * :meth:`shutdown` cancels the runner task and closes the store.
    """

    def __init__(
        self,
        project_id: str,
        *,
        workspace_path: str,
        project_name: str | None = None,
        store: ConsoleStore | None = None,
        resolve_backend: ResolveBackendFn,
        broadcast: BroadcastFn,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        self.project_id = project_id
        self.workspace_path = workspace_path
        self.project_name = project_name
        self.store = store or ConsoleStore(project_id)
        self._resolve_backend = resolve_backend
        self._broadcast = broadcast
        self._loop = loop
        self._queue: asyncio.Queue[_InputItem] = asyncio.Queue()
        self._runner_task: asyncio.Task | None = None
        self._closed = False
        self._stop_event: asyncio.Event | None = None
        # Mirror the on-disk transcript in memory after first read so
        # the prompt builder doesn't re-read the file on every turn.
        # Loaded lazily on first submit.
        self._memory_loaded = False
        self._memory: list[dict[str, Any]] = []
        # Counter so tests can synchronize on "all queued turns done".
        self._turns_started = 0
        self._turns_finished = 0
        self._activity_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transcript(self) -> list[dict[str, Any]]:
        """Return the in-memory transcript (loaded lazily from disk)."""
        if not self._memory_loaded:
            self._memory = self.store.read_all()
            self._memory_loaded = True
        return list(self._memory)

    def ensure_runner(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Start the background runner task if it isn't running yet.

        Called from the WS handler on every console_input so the runner
        is up by the time the first message lands. Idempotent.
        """
        if self._closed:
            raise RuntimeError(
                f"ConsoleSession for {self.project_id!r} is closed"
            )
        if self._runner_task is not None and not self._runner_task.done():
            return
        self._loop = loop or self._loop or asyncio.get_event_loop()
        self._stop_event = asyncio.Event()
        self._runner_task = self._loop.create_task(self._run_forever())

    async def submit(
        self,
        text: str,
        *,
        attachments: list[str] | None = None,
        wait: bool = False,
    ) -> asyncio.Future | None:
        """Enqueue an operator input. If wait=True, returns a Future
        that resolves when the turn finishes.

        Caller is responsible for ensuring :meth:`ensure_runner` ran
        first (typically called from the WS handler on the same loop).
        """
        if self._closed:
            raise RuntimeError(
                f"ConsoleSession for {self.project_id!r} is closed"
            )
        text = (text or "").strip()
        if not text:
            return None
        done: asyncio.Future | None = None
        if wait:
            loop = asyncio.get_event_loop()
            done = loop.create_future()
        item = _InputItem(
            text=text,
            attachments=list(attachments or []),
            done=done,
        )
        await self._queue.put(item)
        return done

    async def shutdown(self) -> None:
        """Stop the runner task and close the store. Idempotent."""
        if self._closed:
            return
        self._closed = True
        if self._stop_event is not None:
            self._stop_event.set()
        runner = self._runner_task
        if runner is not None and not runner.done():
            # Drop a sentinel onto the queue so the runner wakes up
            # and notices _closed=True.
            try:
                await self._queue.put(_InputItem(text=""))
            except Exception:
                pass
            try:
                await asyncio.wait_for(runner, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                runner.cancel()
        try:
            self.store.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Runner: pulls items off the queue and processes them one at a time
    # ------------------------------------------------------------------

    async def _run_forever(self) -> None:
        """Drain the queue forever, processing one input at a time."""
        while not self._closed:
            try:
                item = await self._queue.get()
            except asyncio.CancelledError:
                return
            if self._closed:
                return
            if not item.text.strip():
                # Sentinel from shutdown(); break out.
                continue
            self._turns_started += 1
            try:
                await self._handle_turn(item)
            except Exception as exc:  # pragma: no cover — defensive
                logger.exception(
                    "ConsoleSession[%s] turn failed: %s",
                    self.project_id, exc,
                )
                self._record_and_broadcast(
                    "console_error",
                    {"error": f"{type(exc).__name__}: {exc}"},
                )
            finally:
                self._turns_finished += 1
                if item.done is not None and not item.done.done():
                    item.done.set_result(None)

    async def _handle_turn(self, item: _InputItem) -> None:
        """Run one operator turn end-to-end.

        Steps:

        1. Record the operator input event (transcript + WS broadcast).
        2. Resolve the backend (claude / codex / ...).
        3. Build the tool catalog appropriate for the backend.
        4. Build the prompt by replaying the transcript + new input.
        5. Spawn a fresh AcpAgentSession and run_task.
        6. Each acp_* event the SDK emits is forwarded to the store
           (append-only JSONL) and the WS broadcast.
        """
        # Lazy import keeps module import cheap (the SDK is heavy).
        from oompah.acp_agent import AcpAgentSession
        from oompah.acp_tools import (
            build_codex_tool_catalog,
            build_tool_catalog,
        )

        # Mirror the operator input both to disk and to WS clients.
        operator_event = self._record_and_broadcast(
            "operator_input",
            {
                "text": item.text,
                "attachments": list(item.attachments),
            },
        )

        # Resolve backend + model + permission_mode for THIS turn so
        # provider/role changes pick up on the next message.
        try:
            backend_info = self._resolve_backend(self.project_id) or {}
        except Exception as exc:
            logger.warning(
                "ConsoleSession[%s] backend resolution failed: %s",
                self.project_id, exc,
            )
            backend_info = {}
        backend_name = backend_info.get("backend_name") or "claude"
        model = backend_info.get("model")
        permission_mode = backend_info.get("permission_mode") or "acceptEdits"

        # Build tool catalog for this backend.
        try:
            if backend_name == "codex":
                tool_catalog = build_codex_tool_catalog(self.workspace_path)
                tools_summary = (
                    "read/write/edit/list/search files + run_command + backlog"
                )
            else:
                tool_catalog = build_tool_catalog(self.workspace_path)
                tools_summary = (
                    "read/write/edit/list/search files + run_command + backlog"
                )
        except ImportError as exc:
            err = f"backend {backend_name!r} unavailable: {exc}"
            logger.warning("ConsoleSession[%s] %s", self.project_id, err)
            self._record_and_broadcast("console_error", {"error": err})
            return
        except Exception as exc:
            err = (
                f"backend {backend_name!r} catalog build failed: "
                f"{type(exc).__name__}: {exc}"
            )
            logger.warning("ConsoleSession[%s] %s", self.project_id, err)
            self._record_and_broadcast("console_error", {"error": err})
            return

        # Build the prompt by replaying transcript (in-memory) + new input.
        # Make sure to include the operator_event we just appended so the
        # session sees it.
        transcript = self.transcript()
        prompt = render_transcript_as_prompt(
            transcript,
            new_input=item.text,
            project_name=self.project_name,
            tools_summary=tools_summary,
        )

        # Forward every backend event into the transcript + WS fan-out.
        def _on_event(ev) -> None:
            kind = getattr(ev, "event", None) or "acp_event"
            payload = getattr(ev, "payload", None) or {}
            usage = getattr(ev, "usage", None) or None
            self._record_and_broadcast(kind, payload, usage=usage)

        session = AcpAgentSession(
            workspace_path=self.workspace_path,
            prompt=prompt,
            model=model,
            tool_catalog=tool_catalog,
            on_event=_on_event,
            permission_mode=permission_mode,
            backend_name=backend_name,
        )
        try:
            status = await session.run_task()
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            logger.warning("ConsoleSession[%s] run_task crashed: %s",
                           self.project_id, err)
            self._record_and_broadcast("console_error", {"error": err})
            return
        # A terminal status outside "succeeded" is informational only
        # for the console — the operator can just send another message.
        if status not in ("succeeded",):
            self._record_and_broadcast(
                "console_status",
                {
                    "status": status,
                    "error": session.last_error,
                },
            )

    # ------------------------------------------------------------------
    # Internal: dual-write (disk + WS)
    # ------------------------------------------------------------------

    def _record_and_broadcast(
        self,
        kind: str,
        payload: dict[str, Any] | None = None,
        *,
        usage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist an event to JSONL, append to in-memory transcript,
        and fan out to WS clients."""
        event = self.store.append(kind, payload or {}, usage=usage)
        # Keep the in-memory mirror in sync. We don't bother taking
        # an asyncio lock here because all writes flow through the
        # single runner task — the only contention is the initial
        # lazy load, and read_all() is safe to call any time.
        if self._memory_loaded:
            self._memory.append(event)
        try:
            self._broadcast(self.project_id, event)
        except Exception as exc:
            logger.debug(
                "ConsoleSession[%s] broadcast failed: %s",
                self.project_id, exc,
            )
        return event


# ----------------------------------------------------------------------
# ConsoleManager — global registry of per-project sessions
# ----------------------------------------------------------------------


class ConsoleManager:
    """Manages one :class:`ConsoleSession` per project_id.

    Wires the resolve_backend / broadcast callbacks down to each
    session. The server module owns a single ConsoleManager instance
    and routes WS messages through it.
    """

    def __init__(
        self,
        *,
        resolve_backend: ResolveBackendFn,
        broadcast: BroadcastFn,
        resolve_project: Callable[[str], dict[str, Any] | None],
        base_dir: str | None = None,
    ):
        """
        :param resolve_backend: Called per-turn with project_id; returns
            a dict with optional keys: ``backend_name``, ``model``,
            ``permission_mode``.
        :param broadcast: Called for every console event with
            ``(project_id, event)``; should fan out to WS clients.
        :param resolve_project: Called on first session construction;
            returns ``{"repo_path", "name"}`` for a project_id or
            ``None`` when the project doesn't exist.
        :param base_dir: Optional override for the transcript directory.
            Tests use this to point at tmp dirs.
        """
        self._resolve_backend = resolve_backend
        self._broadcast = broadcast
        self._resolve_project = resolve_project
        self._base_dir = base_dir
        self._sessions: dict[str, ConsoleSession] = {}
        self._lock = threading.Lock()

    def get_session(self, project_id: str) -> ConsoleSession | None:
        """Return the in-memory session for ``project_id`` if any.

        Does NOT create a session — call :meth:`get_or_create` for
        lazy construction.
        """
        with self._lock:
            return self._sessions.get(project_id)

    def get_or_create(
        self,
        project_id: str,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> ConsoleSession:
        """Get-or-create the session for ``project_id``.

        Raises :class:`KeyError` if the project doesn't exist.
        """
        with self._lock:
            existing = self._sessions.get(project_id)
            if existing is not None:
                return existing
            info = self._resolve_project(project_id)
            if not info:
                raise KeyError(f"Unknown project_id: {project_id!r}")
            workspace_path = info.get("repo_path") or ""
            if not workspace_path:
                raise KeyError(
                    f"Project {project_id!r} has no repo_path; "
                    "console requires a checked-out repo"
                )
            session = ConsoleSession(
                project_id=project_id,
                workspace_path=workspace_path,
                project_name=info.get("name"),
                store=ConsoleStore(project_id, base_dir=self._base_dir),
                resolve_backend=self._resolve_backend,
                broadcast=self._broadcast,
                loop=loop,
            )
            self._sessions[project_id] = session
            return session

    def read_transcript(
        self,
        project_id: str,
        *,
        limit: int = 200,
        before: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Read a page of transcript without creating a session.

        Useful for the REST endpoint that serves the initial page load
        before any operator input has triggered session construction.
        """
        store = ConsoleStore(project_id, base_dir=self._base_dir)
        return store.read_page(limit=limit, before=before)

    async def shutdown(self) -> None:
        """Shut down every active session."""
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for s in sessions:
            try:
                await s.shutdown()
            except Exception:
                pass
