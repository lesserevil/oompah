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


# The command timeout is deliberately separate from the result-delivery
# timeout.  A subprocess can have exited while its provider transport is
# still draining the bounded result (or while a descendant is closing an
# inherited stdout/stderr pipe).  That interval must be finite, but it must
# not be mistaken for a generic prompt stall.
DEFAULT_RESULT_DELIVERY_TIMEOUT_S = 30.0


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
    result_delivery_deadline_monotonic: float | None = None
    result_delivery_timeout_s: float = DEFAULT_RESULT_DELIVERY_TIMEOUT_S

    @property
    def deadline_exceeded(self) -> bool:
        """Whether the command-specific deadline has elapsed."""

        return self.phase == "running" and time.monotonic() >= self.deadline_monotonic

    @property
    def result_delivery_deadline_exceeded(self) -> bool:
        """Whether a completed command missed its provider handoff deadline."""

        return (
            self.phase in {"result_pending", "provider_stalled"}
            and self.result_delivery_deadline_monotonic is not None
            and time.monotonic() >= self.result_delivery_deadline_monotonic
        )

    @property
    def protects_from_stall(self) -> bool:
        """Whether generic no-event stall detection should defer."""

        if self.phase == "waiting_for_capacity":
            return True
        if self.phase == "running":
            return self.process_alive and not self.deadline_exceeded
        if self.phase == "result_pending":
            return not self.result_delivery_deadline_exceeded
        return False

    @property
    def timeout_diagnostic(self) -> str:
        """Stable diagnostic used when the command deadline wins."""

        return (
            (
                f"{self.tool_name} result delivery timed out after "
                f"{self.result_delivery_timeout_s:g}s"
            )
            if self.phase in {"result_pending", "provider_stalled"}
            else (
                f"{self.tool_name} command timed out after "
                f"{self.command_timeout_s:g}s"
            )
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
    result_delivery_deadline_monotonic: float | None = None
    result_delivery_timeout_s: float = DEFAULT_RESULT_DELIVERY_TIMEOUT_S
    result_delivery_required: bool = False


class ToolLivenessMonitor:
    """Track bounded subprocess-backed tool calls for one agent session."""

    def __init__(
        self,
        *,
        result_delivery_timeout_s: float = DEFAULT_RESULT_DELIVERY_TIMEOUT_S,
    ) -> None:
        self._lock = threading.RLock()
        self._active: dict[str, _ToolExecution] = {}
        self._cancel_requested = threading.Event()
        self._result_delivery_timeout_s = max(float(result_delivery_timeout_s), 0.0)
        # Retain terminal delivery metrics after the active invocation is
        # removed.  This makes result_delivered observable without keeping a
        # provider slot or a RunningEntry liveness owner alive.
        self._terminal_counts = {"result_delivered": 0}

    def request_cancel(self) -> None:
        """Withdraw authority for queued tool work without inventing a process."""

        self._cancel_requested.set()

    def is_cancelled(self) -> bool:
        """Return whether the owning agent session has been terminated."""

        return self._cancel_requested.is_set()

    def start(
        self,
        *,
        tool_name: str,
        timeout_s: float,
        result_delivery_required: bool = False,
    ) -> str:
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
            result_delivery_required=bool(result_delivery_required),
        )
        with self._lock:
            self._active[invocation_id] = execution
        return invocation_id

    def start_waiting(
        self,
        *,
        tool_name: str,
        result_delivery_required: bool = False,
    ) -> str:
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
                result_delivery_required=bool(result_delivery_required),
            )
        return invocation_id

    def start_runtime(
        self,
        invocation_id: str,
        *,
        timeout_s: float,
        result_delivery_required: bool | None = None,
    ) -> None:
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
            if result_delivery_required is not None:
                execution.result_delivery_required = bool(result_delivery_required)

    def attach_process(self, invocation_id: str, process: Any) -> None:
        """Associate the subprocess with a previously registered call."""

        with self._lock:
            execution = self._active.get(invocation_id)
            if execution is not None:
                execution.process = process
                execution.last_heartbeat_monotonic = time.monotonic()

    def _select_invocation(
        self,
        invocation_id: str | None,
        *,
        phases: tuple[str, ...],
    ) -> _ToolExecution | None:
        if invocation_id is not None:
            execution = self._active.get(invocation_id)
            if execution is not None and execution.phase in phases:
                return execution
            return None
        candidates = [
            execution
            for execution in self._active.values()
            if execution.phase in phases
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda item: item.started_monotonic)

    def _transition_to_result_pending(
        self,
        execution: _ToolExecution,
        *,
        now: float | None = None,
    ) -> None:
        if execution.phase != "running":
            return
        completed_at = time.monotonic() if now is None else now
        execution.phase = "result_pending"
        execution.result_delivery_deadline_monotonic = (
            completed_at + self._result_delivery_timeout_s
        )
        execution.result_delivery_timeout_s = self._result_delivery_timeout_s
        execution.last_heartbeat_monotonic = completed_at

    def result_pending(self, invocation_id: str | None = None) -> str | None:
        """Transfer ownership from the child to the result-delivery bridge.

        The command helper calls this before returning its bounded string.  It
        is idempotent because the supervisor may observe ``Popen.poll()`` at
        the same time and perform the same transition first.
        """

        with self._lock:
            execution = self._select_invocation(
                invocation_id,
                phases=("running", "result_pending"),
            )
            if execution is None:
                return None
            self._transition_to_result_pending(execution)
            return execution.invocation_id

    # Alias with an explicit verb for callers that model the bridge as a
    # durable handoff rather than a subprocess state transition.
    mark_result_pending = result_pending

    def result_delivered(self, invocation_id: str | None = None) -> str | None:
        """Acknowledge one provider-visible tool result exactly once.

        Removing the active record here is intentional: result delivery, not
        child exit, is the point at which the liveness owner may be cleared.
        The terminal counter remains available through :meth:`metrics`.
        """

        with self._lock:
            execution = self._select_invocation(
                invocation_id,
                phases=("result_pending",),
            )
            if execution is None:
                return None
            execution.phase = "result_delivered"
            execution.last_heartbeat_monotonic = time.monotonic()
            self._terminal_counts["result_delivered"] += 1
            self._active.pop(execution.invocation_id, None)
            return execution.invocation_id

    mark_result_delivered = result_delivered

    def provider_stalled(self, invocation_id: str | None = None) -> str | None:
        """Classify a result whose bounded provider handoff deadline expired."""

        with self._lock:
            execution = self._select_invocation(
                invocation_id,
                phases=("result_pending",),
            )
            if execution is None:
                return None
            execution.phase = "provider_stalled"
            return execution.invocation_id

    mark_provider_stalled = provider_stalled

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

                # ``poll()`` observes the shell, not necessarily the pipe
                # readers/descendants that communicate() is still draining.
                # Treat child exit as result_pending, not as permission to
                # retire the provider. The result bridge will acknowledge it
                # or the fixed handoff deadline will classify a stall.
                if (
                    execution.phase == "running"
                    and execution.process is not None
                    and not process_alive
                    and execution.result_delivery_required
                ):
                    self._transition_to_result_pending(execution)
                if (
                    execution.phase == "result_pending"
                    and execution.result_delivery_deadline_monotonic is not None
                    and time.monotonic()
                    >= execution.result_delivery_deadline_monotonic
                ):
                    execution.phase = "provider_stalled"

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
                        result_delivery_deadline_monotonic=(
                            execution.result_delivery_deadline_monotonic
                        ),
                        result_delivery_timeout_s=(
                            execution.result_delivery_timeout_s
                        ),
                    )
                )
            return snapshots

    def metrics(self) -> dict[str, int]:
        """Return bounded lifecycle counts for state/health telemetry."""

        with self._lock:
            counts = {
                "running": 0,
                "result_pending": 0,
                "result_delivered": self._terminal_counts["result_delivered"],
                "provider_stalled": 0,
            }
            for execution in self._active.values():
                if execution.phase in counts:
                    counts[execution.phase] += 1
            return counts

    state_metrics = metrics

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
