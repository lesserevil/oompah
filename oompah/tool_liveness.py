"""Liveness state for bounded agent tool invocations.

The agent event stream is not a process heartbeat.  In particular, an ACP
``tool_use`` event is emitted before the tool starts and the matching result
may not arrive until a long-running command completes.  This small monitor
bridges that gap without making generic prompt silence look productive.

Instances are deliberately owned by one running session.  The monitor is
thread-safe because ACP tool implementations run their blocking subprocess
helpers in worker threads while reconciliation runs on the orchestrator's
event-loop thread.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolLivenessSnapshot:
    """A point-in-time view of the active bounded tool invocation."""

    invocation_id: str
    tool_name: str
    started_monotonic: float
    deadline_monotonic: float
    last_heartbeat_monotonic: float
    process_alive: bool
    command_timeout_s: float
    phase: str = "running"

    @property
    def deadline_exceeded(self) -> bool:
        """Whether the command-specific deadline has elapsed."""

        return self.phase == "running" and time.monotonic() >= self.deadline_monotonic

    @property
    def protects_from_stall(self) -> bool:
        """Whether generic no-event stall detection should defer."""

        return (
            self.phase == "waiting_for_capacity"
            or (self.process_alive and not self.deadline_exceeded)
        )

    @property
    def timeout_diagnostic(self) -> str:
        """Stable diagnostic used when the command deadline wins."""

        return (
            f"{self.tool_name} command timed out after "
            f"{self.command_timeout_s:g}s"
        )


@dataclass
class _ToolExecution:
    invocation_id: str
    tool_name: str
    started_monotonic: float
    deadline_monotonic: float
    command_timeout_s: float
    process: Any = None
    last_heartbeat_monotonic: float = 0.0
    phase: str = "running"


class ToolLivenessMonitor:
    """Track bounded subprocess-backed tool calls for one agent session."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active: dict[str, _ToolExecution] = {}
        self._cancel_requested = threading.Event()

    def request_cancel(self) -> None:
        """Withdraw authority for queued tool work without inventing a process."""

        self._cancel_requested.set()

    def is_cancelled(self) -> bool:
        """Return whether the owning agent session has been terminated."""

        return self._cancel_requested.is_set()

    def start(self, *, tool_name: str, timeout_s: float) -> str:
        """Register a tool invocation and return its opaque invocation id."""

        timeout = max(float(timeout_s), 0.0)
        now = time.monotonic()
        invocation_id = uuid.uuid4().hex
        execution = _ToolExecution(
            invocation_id=invocation_id,
            tool_name=tool_name,
            started_monotonic=now,
            deadline_monotonic=now + timeout,
            command_timeout_s=timeout,
            last_heartbeat_monotonic=now,
        )
        with self._lock:
            self._active[invocation_id] = execution
        return invocation_id

    def start_waiting(self, *, tool_name: str) -> str:
        """Register a capacity wait without starting the command timeout."""

        now = time.monotonic()
        invocation_id = uuid.uuid4().hex
        with self._lock:
            self._active[invocation_id] = _ToolExecution(
                invocation_id=invocation_id,
                tool_name=tool_name,
                started_monotonic=now,
                deadline_monotonic=float("inf"),
                command_timeout_s=0.0,
                last_heartbeat_monotonic=now,
                phase="waiting_for_capacity",
            )
        return invocation_id

    def start_runtime(self, invocation_id: str, *, timeout_s: float) -> None:
        """Start the bounded command clock after capacity is acquired."""

        timeout = max(float(timeout_s), 0.0)
        now = time.monotonic()
        with self._lock:
            execution = self._active.get(invocation_id)
            if execution is None:
                return
            execution.started_monotonic = now
            execution.deadline_monotonic = now + timeout
            execution.command_timeout_s = timeout
            execution.last_heartbeat_monotonic = now
            execution.phase = "running"

    def attach_process(self, invocation_id: str, process: Any) -> None:
        """Associate the subprocess with a previously registered call."""

        with self._lock:
            execution = self._active.get(invocation_id)
            if execution is not None:
                execution.process = process
                execution.last_heartbeat_monotonic = time.monotonic()

    def heartbeat(self, invocation_id: str) -> None:
        """Record an explicit supervisor heartbeat for a live invocation."""

        with self._lock:
            execution = self._active.get(invocation_id)
            if execution is not None:
                execution.last_heartbeat_monotonic = time.monotonic()

    def complete(self, invocation_id: str) -> None:
        """Remove a completed invocation; subsequent snapshots are empty."""

        with self._lock:
            self._active.pop(invocation_id, None)

    def snapshots(self) -> list[ToolLivenessSnapshot]:
        """Return active invocations and refresh process liveness.

        ``Popen.poll`` is intentionally used instead of trusting ACP events:
        it observes a child that is CPU-bound, quiet on stdout, or blocked in
        a syscall.  A dead child no longer protects the worker from recovery.
        """

        with self._lock:
            snapshots: list[ToolLivenessSnapshot] = []
            for execution in self._active.values():
                process_alive = execution.phase == "waiting_for_capacity"
                process = execution.process
                if process is not None:
                    try:
                        process_alive = process.poll() is None
                    except (AttributeError, OSError):
                        process_alive = False
                if process_alive:
                    execution.last_heartbeat_monotonic = time.monotonic()

                snapshots.append(
                    ToolLivenessSnapshot(
                        invocation_id=execution.invocation_id,
                        tool_name=execution.tool_name,
                        started_monotonic=execution.started_monotonic,
                        deadline_monotonic=execution.deadline_monotonic,
                        last_heartbeat_monotonic=execution.last_heartbeat_monotonic,
                        process_alive=process_alive,
                        command_timeout_s=execution.command_timeout_s,
                        phase=execution.phase,
                    )
                )
            return snapshots

    def snapshot(self) -> ToolLivenessSnapshot | None:
        """Return the most urgent active invocation for compatibility.

        A deadline-expired command wins over a live command so supervision
        cannot be bypassed by a second invocation. Otherwise a live command
        wins over an exited one because it is the current source of progress.
        """

        snapshots = self.snapshots()
        if not snapshots:
            return None
        expired = [snapshot for snapshot in snapshots if snapshot.deadline_exceeded]
        if expired:
            return expired[0]
        live = [snapshot for snapshot in snapshots if snapshot.process_alive]
        return (live or snapshots)[0]
