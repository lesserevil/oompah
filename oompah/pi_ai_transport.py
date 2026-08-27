"""Subprocess transport for the optional ``@earendil-works/pi-ai`` bridge."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import signal
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from oompah.agent import MAX_LINE_SIZE
from oompah.client_auth import agent_environment
from oompah.secrets import redact_sensitive_data, register_secret

PI_AI_PROTOCOL = "oompah-pi-ai-v1"
DEFAULT_BRIDGE_PATH = Path(__file__).resolve().parent.parent / "bridge" / "pi-ai" / "src" / "main.mjs"


class PiAiTransportError(RuntimeError):
    """A local bridge or upstream Pi transport operation failed."""


class PiAiTransport:
    """Own one persistent Node sidecar for a single Oompah worker."""

    def __init__(self, *, workspace_path: str, provider: str, model: str, api_key: str = "", base_url: str = "", provider_name: str = "", model_context: int | None = None, model_capabilities: Sequence[str] = (), thinking: str = "off", timeout_s: float = 600.0, bridge_path: str | os.PathLike[str] | None = None, env: Mapping[str, str] | None = None, before_transport_contact: Callable[[], str | None] | None = None) -> None:
        self.workspace_path = str(Path(workspace_path).resolve())
        self.provider = str(provider).strip()
        self.model = str(model).strip()
        self.api_key = str(api_key or "")
        self.base_url = str(base_url or "").strip()
        self.provider_name = str(provider_name or provider).strip()
        self.model_context = int(model_context) if model_context else None
        self.model_capabilities = tuple(str(value) for value in model_capabilities)
        self.thinking = str(thinking or "off")
        self.timeout_s = max(float(timeout_s), 0.1)
        self.bridge_path = Path(bridge_path or DEFAULT_BRIDGE_PATH).resolve()
        self.env = dict(env or {})
        self.before_transport_contact = before_transport_contact
        self.transport_contacted = False
        self._proc: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._lock = asyncio.Lock()
        register_secret(self.api_key)

    def _next_id(self) -> str:
        self._request_id += 1
        return f"pi-{self._request_id}"

    async def _write(self, payload: Mapping[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise PiAiTransportError("Pi AI bridge is not running")
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        if len(encoded.encode("utf-8")) > MAX_LINE_SIZE:
            raise PiAiTransportError("Pi AI bridge request exceeds the JSONL frame limit")
        self._proc.stdin.write(encoded.encode("utf-8") + b"\n")
        await self._proc.stdin.drain()

    async def _read(self) -> dict[str, Any]:
        if self._proc is None or self._proc.stdout is None:
            raise PiAiTransportError("Pi AI bridge is not running")
        try:
            line = await self._proc.stdout.readline()
        except (ValueError, asyncio.LimitOverrunError) as exc:
            raise PiAiTransportError("Pi AI bridge response exceeds the JSONL frame limit") from exc
        if not line:
            stderr = ""
            if self._proc.stderr is not None:
                with contextlib.suppress(Exception):
                    raw = await asyncio.wait_for(self._proc.stderr.read(), timeout=0.2)
                    stderr = raw.decode("utf-8", errors="replace")[-2000:]
            safe = redact_sensitive_data(stderr)
            raise PiAiTransportError(f"Pi AI bridge exited unexpectedly{': ' + str(safe) if safe else ''}")
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PiAiTransportError("Pi AI bridge returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise PiAiTransportError("Pi AI bridge returned a non-object frame")
        return value

    async def start(self) -> None:
        if self._proc is not None:
            return
        node = shutil.which("node")
        if node is None:
            raise PiAiTransportError("Node.js is required for the Pi AI transport")
        if not self.bridge_path.is_file():
            raise PiAiTransportError(f"Pi AI bridge is unavailable: {self.bridge_path}")
        environment = agent_environment({**os.environ, **self.env}, workspace_path=self.workspace_path)
        environment.update({"PI_OFFLINE": "1", "PI_SKIP_VERSION_CHECK": "1", "PI_TELEMETRY": "0"})
        self._proc = await asyncio.create_subprocess_exec(node, str(self.bridge_path), cwd=self.workspace_path, env=environment, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=MAX_LINE_SIZE, start_new_session=(os.name == "posix"))
        request_id = self._next_id()
        await self._write({"id": request_id, "type": "initialize", "protocol": PI_AI_PROTOCOL, "provider": self.provider, "model": self.model, "credential": self.api_key or None, "base_url": self.base_url or None, "provider_name": self.provider_name, "context_window": self.model_context, "input": list(self.model_capabilities or ("text",)), "reasoning": self.thinking != "off", "thinking": self.thinking, "timeout_ms": int(self.timeout_s * 1000), "max_retries": 0})
        response = await asyncio.wait_for(self._read(), timeout=15.0)
        if response.get("type") == "error":
            raise PiAiTransportError(str(response.get("message") or "initialization failed"))
        if response.get("type") != "ready" or response.get("id") != request_id:
            raise PiAiTransportError("Pi AI bridge returned an invalid initialization response")

    async def complete(self, *, system_prompt: str, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]], max_tokens: int, session_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        async with self._lock:
            await self.start()
            if not self.transport_contacted:
                denial = self.before_transport_contact() if self.before_transport_contact is not None else None
                if denial is not None:
                    raise PiAiTransportError(str(denial))
            request_id = self._next_id()
            await self._write({"id": request_id, "type": "complete", "system_prompt": system_prompt, "messages": list(messages), "tools": list(tools), "max_tokens": int(max_tokens), "session_id": session_id})
            deadline = asyncio.get_running_loop().time() + self.timeout_s
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    await self.abort()
                    raise PiAiTransportError("Pi AI provider request timed out")
                event = await asyncio.wait_for(self._read(), timeout=remaining)
                if event.get("id") != request_id:
                    continue
                if event.get("type") == "provider_start":
                    self.transport_contacted = True
                if event.get("type") == "error":
                    raise PiAiTransportError(str(event.get("message") or "Pi AI request failed"))
                yield event
                if event.get("type") == "done":
                    return

    async def abort(self) -> None:
        if self._proc is None or self._proc.returncode is not None:
            return
        with contextlib.suppress(Exception):
            await self._write({"id": self._next_id(), "type": "abort"})

    async def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        if proc.returncode is None:
            with contextlib.suppress(Exception):
                if proc.stdin is not None:
                    proc.stdin.write(json.dumps({"id": self._next_id(), "type": "shutdown"}).encode() + b"\n")
                    await proc.stdin.drain()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGTERM) if os.name == "posix" else proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(proc.pid, signal.SIGKILL) if os.name == "posix" else proc.kill()
                    await proc.wait()
