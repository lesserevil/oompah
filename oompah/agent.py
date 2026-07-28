"""Agent runner: launches and manages coding agent subprocesses."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from oompah.client_auth import agent_environment

logger = logging.getLogger(__name__)

# Max line size for safe buffering (10 MB)
MAX_LINE_SIZE = 10 * 1024 * 1024
DEFAULT_STOP_TIMEOUT_S = 5.0
STOP_POLL_INTERVAL_S = 0.02


def _linux_process_snapshot() -> dict[int, tuple[int, int, str | None, tuple[str, ...]]]:
    """Return ``pid -> (ppid, starttime, cwd, argv)`` from procfs.

    ``starttime`` protects the termination path from PID reuse.  Procfs reads
    are intentionally best-effort because processes may exit between any two
    entries while the snapshot is being assembled.
    """

    if os.name != "posix" or not os.path.isdir("/proc"):
        return {}
    snapshot: dict[int, tuple[int, int, str | None, tuple[str, ...]]] = {}
    for raw_pid in os.listdir("/proc"):
        if not raw_pid.isdigit():
            continue
        pid = int(raw_pid)
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
            fields = stat[stat.rfind(")") + 2 :].split()
            if fields[0] == "Z":
                # A zombie has exited and cannot perform work; its owner only
                # needs to reap it. Treat it as gone for termination safety.
                continue
            ppid = int(fields[1])
            starttime = int(fields[19])
        except (OSError, ValueError, IndexError):
            continue
        try:
            cwd = os.path.realpath(os.readlink(f"/proc/{pid}/cwd"))
        except OSError:
            cwd = None
        try:
            argv = tuple(
                value.decode("utf-8", errors="replace")
                for value in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
                if value
            )
        except OSError:
            argv = ()
        snapshot[pid] = (ppid, starttime, cwd, argv)
    return snapshot


def capture_workspace_processes(
    workspace_path: str,
    *,
    ancestor_pid: int | None = None,
) -> dict[int, int]:
    """Capture service-owned processes associated with *workspace_path*.

    Some third-party SDKs terminate only their immediate subprocess, allowing
    grandchildren to survive and continue editing after Oompah has forgotten
    the worker.  Before cancellation severs the ancestry, this function finds
    descendants of the service whose cwd or argv identifies the exact managed
    workspace, then includes every descendant of those matching processes.

    The returned mapping contains PID start times and is safe to pass to
    :func:`terminate_captured_processes`.
    """

    snapshot = _linux_process_snapshot()
    if not snapshot:
        return {}
    root_pid = os.getpid() if ancestor_pid is None else int(ancestor_pid)
    workspace = os.path.realpath(workspace_path)
    workspace_prefix = workspace + os.sep

    descendants: set[int] = set()
    frontier = {root_pid}
    while frontier:
        parents = frontier
        frontier = {
            pid
            for pid, (ppid, _start, _cwd, _argv) in snapshot.items()
            if ppid in parents and pid not in descendants
        }
        descendants.update(frontier)

    seeds = {
        pid
        for pid in descendants
        if (
            (snapshot[pid][2] == workspace)
            or bool(snapshot[pid][2] and snapshot[pid][2].startswith(workspace_prefix))
            or workspace in snapshot[pid][3]
        )
    }
    selected = set(seeds)
    frontier = set(seeds)
    while frontier:
        parents = frontier
        frontier = {
            pid
            for pid, (ppid, _start, _cwd, _argv) in snapshot.items()
            if ppid in parents and pid not in selected
        }
        selected.update(frontier)
    return {pid: snapshot[pid][1] for pid in selected}


def terminate_captured_processes(
    captured: dict[int, int],
    *,
    timeout_s: float = DEFAULT_STOP_TIMEOUT_S,
) -> set[int]:
    """Terminate an exact, PID-reuse-safe process set and return survivors."""

    if not captured:
        return set()

    # Include children created in the narrow interval between the orchestrator's
    # capture and this termination worker beginning. They are accepted only
    # when their ancestry reaches a PID whose start time was already captured.
    current = _linux_process_snapshot()
    frontier = {
        pid
        for pid, starttime in captured.items()
        if pid in current and current[pid][1] == starttime
    }
    while frontier:
        parents = frontier
        frontier = {
            pid
            for pid, (ppid, starttime, _cwd, _argv) in current.items()
            if ppid in parents and pid not in captured
        }
        for pid in frontier:
            captured[pid] = current[pid][1]

    def _alive() -> set[int]:
        current = _linux_process_snapshot()
        return {
            pid
            for pid, starttime in captured.items()
            if pid in current and current[pid][1] == starttime
        }

    def _signal(pids: set[int], sig: signal.Signals) -> None:
        # Signal only the captured PID/start-time identities; never a broad
        # process group shared with the service or unrelated workers.
        for pid in sorted(pids, reverse=True):
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                continue

    alive = _alive()
    _signal(alive, signal.SIGTERM)
    deadline = time.monotonic() + max(float(timeout_s), 0.0)
    while alive and time.monotonic() < deadline:
        time.sleep(STOP_POLL_INTERVAL_S)
        alive = _alive()
    if alive:
        _signal(alive, signal.SIGKILL)
        kill_deadline = time.monotonic() + max(
            min(float(timeout_s), 1.0),
            STOP_POLL_INTERVAL_S,
        )
        while alive and time.monotonic() < kill_deadline:
            time.sleep(STOP_POLL_INTERVAL_S)
            alive = _alive()
    return alive


class AgentError(Exception):
    """Raised when agent session operations fail."""

    def __init__(self, message: str, error_class: str = "agent_error"):
        super().__init__(message)
        self.error_class = error_class


@dataclass
class AgentEvent:
    """Structured event emitted by the agent runner to the orchestrator."""

    event: str
    timestamp: float
    agent_pid: str | None = None
    usage: dict[str, int] | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class AgentSession:
    """Manages a single coding agent subprocess session."""

    def __init__(
        self,
        command: str,
        workspace_path: str,
        read_timeout_ms: int = 5000,
        turn_timeout_ms: int = 3_600_000,
    ):
        self.command = command
        self.workspace_path = workspace_path
        self.read_timeout_ms = read_timeout_ms
        self.turn_timeout_ms = turn_timeout_ms
        self._process: asyncio.subprocess.Process | None = None
        self._thread_id: str | None = None
        self._turn_id: str | None = None
        self._request_id = 0

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    @property
    def thread_id(self) -> str | None:
        return self._thread_id

    @property
    def turn_id(self) -> str | None:
        return self._turn_id

    @property
    def session_id(self) -> str | None:
        if self._thread_id and self._turn_id:
            return f"{self._thread_id}-{self._turn_id}"
        return None

    @property
    def pid(self) -> str | None:
        if self._process and self._process.pid:
            return str(self._process.pid)
        return None

    async def start(self) -> None:
        """Launch the agent subprocess."""
        logger.info(
            "Launching agent process command=%s cwd=%s",
            self.command,
            self.workspace_path,
        )
        try:
            self._process = await asyncio.create_subprocess_exec(
                "bash",
                "-lc",
                self.command,
                cwd=self.workspace_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=agent_environment(),
                start_new_session=(os.name == "posix"),
            )
        except FileNotFoundError:
            raise AgentError(
                f"Agent command not found: {self.command}",
                error_class="agent_not_found",
            )

        # Start draining stderr in the background
        asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        """Read and log stderr without treating it as protocol."""
        assert self._process and self._process.stderr
        while True:
            line = await self._process.stderr.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                logger.debug("agent stderr: %s", text[:500])

    async def _send(self, msg: dict[str, Any]) -> None:
        """Send a JSON-RPC message to the agent."""
        assert self._process and self._process.stdin
        data = json.dumps(msg) + "\n"
        self._process.stdin.write(data.encode())
        await self._process.stdin.drain()

    async def _read_response(self, timeout_ms: int | None = None) -> dict[str, Any]:
        """Read a single JSON-RPC response line from stdout."""
        timeout = (timeout_ms or self.read_timeout_ms) / 1000.0
        assert self._process and self._process.stdout

        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=timeout
            )
        except asyncio.TimeoutError:
            raise AgentError("Response timeout", error_class="response_timeout")

        if not line:
            raise AgentError("Agent process exited", error_class="port_exit")

        try:
            return json.loads(line.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            logger.warning("Non-JSON line from agent: %s", line[:200])
            raise AgentError(
                f"Malformed agent response: {exc}", error_class="malformed"
            )

    async def initialize(self) -> dict[str, Any]:
        """Perform the initialization handshake."""
        # 1. Send initialize request
        init_id = self._next_id()
        await self._send(
            {
                "id": init_id,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "oompah", "version": "0.1.0"},
                    "capabilities": {},
                },
            }
        )

        # Wait for initialize response
        resp = await self._read_response()
        if "error" in resp:
            raise AgentError(
                f"Initialize failed: {resp['error']}", error_class="startup_failed"
            )

        # 2. Send initialized notification
        await self._send({"method": "initialized", "params": {}})

        return resp

    async def start_thread(
        self,
        approval_policy: str = "auto-edit",
        sandbox: str = "none",
    ) -> str:
        """Start a new thread and return thread_id."""
        thread_id = self._next_id()
        await self._send(
            {
                "id": thread_id,
                "method": "thread/start",
                "params": {
                    "approvalPolicy": approval_policy,
                    "sandbox": sandbox,
                    "cwd": self.workspace_path,
                },
            }
        )

        resp = await self._read_response()
        if "error" in resp:
            raise AgentError(
                f"thread/start failed: {resp['error']}",
                error_class="startup_failed",
            )

        result = resp.get("result", {})
        thread = result.get("thread", result)
        self._thread_id = str(thread.get("id", thread.get("threadId", "")))
        if not self._thread_id:
            raise AgentError(
                "No thread ID in thread/start response",
                error_class="startup_failed",
            )

        logger.info("Agent thread started thread_id=%s", self._thread_id)
        return self._thread_id

    async def start_turn(
        self,
        prompt: str,
        issue_identifier: str,
        issue_title: str,
        approval_policy: str = "auto-edit",
        sandbox_policy: str | None = None,
    ) -> str:
        """Start a new turn and return turn_id."""
        turn_req_id = self._next_id()
        params: dict[str, Any] = {
            "threadId": self._thread_id,
            "input": [{"type": "text", "text": prompt}],
            "cwd": self.workspace_path,
            "title": f"{issue_identifier}: {issue_title}",
            "approvalPolicy": approval_policy,
        }
        if sandbox_policy:
            params["sandboxPolicy"] = {"type": sandbox_policy}

        await self._send(
            {"id": turn_req_id, "method": "turn/start", "params": params}
        )

        resp = await self._read_response()
        if "error" in resp:
            raise AgentError(
                f"turn/start failed: {resp['error']}", error_class="turn_failed"
            )

        result = resp.get("result", {})
        turn = result.get("turn", result)
        self._turn_id = str(turn.get("id", turn.get("turnId", "")))

        logger.info(
            "Agent turn started turn_id=%s session_id=%s",
            self._turn_id,
            self.session_id,
        )
        return self._turn_id

    async def stream_turn(
        self,
        on_event: Callable[[AgentEvent], None] | None = None,
    ) -> str:
        """Stream turn events until completion. Returns final status."""
        assert self._process and self._process.stdout
        timeout = self.turn_timeout_ms / 1000.0
        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AgentError("Turn timeout", error_class="turn_timeout")

            try:
                line = await asyncio.wait_for(
                    self._process.stdout.readline(), timeout=remaining
                )
            except asyncio.TimeoutError:
                raise AgentError("Turn timeout", error_class="turn_timeout")

            if not line:
                raise AgentError("Agent process exited during turn", error_class="port_exit")

            text = line.decode("utf-8", errors="replace").rstrip()
            if not text:
                continue

            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                logger.debug("Non-JSON line from agent stdout: %s", text[:200])
                continue

            event = self._classify_message(msg)
            if on_event:
                on_event(event)

            # Check for terminal turn events
            method = msg.get("method", "")
            if method == "turn/completed":
                return "succeeded"
            elif method == "turn/failed":
                return "failed"
            elif method == "turn/cancelled":
                return "cancelled"

            # Handle approval requests (auto-approve)
            if method in ("item/command/approval", "item/fileChange/approval"):
                approval_id = msg.get("id")
                if approval_id:
                    await self._send(
                        {"id": approval_id, "result": {"approved": True}}
                    )
                    logger.debug("Auto-approved %s id=%s", method, approval_id)

            # Handle unsupported tool calls
            if method == "item/tool/call":
                tool_id = msg.get("id")
                if tool_id:
                    await self._send(
                        {
                            "id": tool_id,
                            "result": {
                                "success": False,
                                "error": "unsupported_tool_call",
                            },
                        }
                    )

            # Handle user input requests (hard fail)
            if method == "item/tool/requestUserInput" or (
                method.startswith("turn/") and msg.get("params", {}).get("inputRequired")
            ):
                raise AgentError(
                    "Agent requested user input",
                    error_class="turn_input_required",
                )

    def _classify_message(self, msg: dict[str, Any]) -> AgentEvent:
        """Classify a raw agent message into a structured event."""
        method = msg.get("method", "")
        params = msg.get("params", msg.get("result", {}))
        now = time.time()

        # Extract usage if present
        usage = None
        for key in ("usage", "total_token_usage", "tokenUsage"):
            if key in params:
                raw = params[key]
                if isinstance(raw, dict):
                    usage = {
                        "input_tokens": raw.get("inputTokens", raw.get("input_tokens", 0)),
                        "output_tokens": raw.get("outputTokens", raw.get("output_tokens", 0)),
                        "total_tokens": raw.get("totalTokens", raw.get("total_tokens", 0)),
                    }
                    break

        event_name = method.replace("/", "_") if method else "other_message"

        # Summarize message
        summary = ""
        if isinstance(params, dict):
            summary = params.get("message", params.get("text", ""))
            if isinstance(summary, dict):
                summary = summary.get("text", str(summary))
            summary = str(summary)[:200]

        return AgentEvent(
            event=event_name,
            timestamp=now,
            agent_pid=self.pid,
            usage=usage,
            payload={"message": summary, "method": method},
        )

    async def stop(self, timeout_s: float = DEFAULT_STOP_TIMEOUT_S) -> None:
        """Terminate the agent subprocess and all of its descendants."""
        process = self._process
        if process is None:
            return

        pid = process.pid
        use_process_group = (
            os.name == "posix" and pid is not None and hasattr(os, "killpg")
        )

        def _tree_is_running() -> bool:
            parent_running = process.returncode is None
            if not use_process_group:
                return parent_running
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return parent_running
            except PermissionError:
                return True
            return True

        def _signal_tree(sig: signal.Signals, *, force: bool = False) -> None:
            if use_process_group:
                try:
                    os.killpg(pid, sig)
                    return
                except ProcessLookupError:
                    return
                except OSError as exc:
                    logger.warning(
                        "Failed to signal agent process group pgid=%s signal=%s: %s; "
                        "falling back to the immediate process",
                        pid,
                        sig.name,
                        exc,
                    )
            try:
                if force:
                    process.kill()
                else:
                    process.terminate()
            except ProcessLookupError:
                pass

        async def _wait_until(deadline: float) -> bool:
            while _tree_is_running():
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return False
                await asyncio.sleep(min(STOP_POLL_INTERVAL_S, remaining))
            return True

        timeout_s = max(float(timeout_s), 0.0)
        if not _tree_is_running():
            logger.info("Agent process stopped pid=%s", pid)
            return

        loop = asyncio.get_running_loop()
        started = loop.time()
        deadline = started + timeout_s
        term_deadline = started + (timeout_s * 0.8)

        try:
            _signal_tree(signal.SIGTERM)
            stopped = await _wait_until(term_deadline)
            if not stopped:
                _signal_tree(
                    getattr(signal, "SIGKILL", signal.SIGTERM),
                    force=True,
                )
                stopped = await _wait_until(deadline)
            if not stopped:
                logger.warning(
                    "Agent process tree did not exit within %.3fs pid=%s",
                    timeout_s,
                    pid,
                )
        except asyncio.CancelledError:
            # A caller enforcing its own deadline may cancel stop(). Make the
            # cancellation itself a hard-stop request before propagating it.
            _signal_tree(
                getattr(signal, "SIGKILL", signal.SIGTERM),
                force=True,
            )
            raise

        logger.info("Agent process stopped pid=%s", pid)
