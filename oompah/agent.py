"""Agent runner: launches and manages coding agent subprocesses."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Max line size for safe buffering (10 MB)
MAX_LINE_SIZE = 10 * 1024 * 1024


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

    async def stop(self) -> None:
        """Terminate the agent subprocess."""
        if self._process:
            try:
                if self._process.returncode is None:
                    self._process.terminate()
                    try:
                        await asyncio.wait_for(self._process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        self._process.kill()
                        await self._process.wait()
            except ProcessLookupError:
                pass
            logger.info("Agent process stopped pid=%s", self.pid)
