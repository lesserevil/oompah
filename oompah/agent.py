"""Agent runner: launches and manages coding agent subprocesses."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
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


@dataclass(frozen=True)
class ProcessIdentity:
    """Kernel identity captured before a process can be cleaned up."""

    pid: int
    starttime: int
    process_group: int
    session: int
    cwd: str | None


@dataclass(frozen=True)
class _ProcessRecord:
    """The identity plus ancestry and argv used during process discovery."""

    ppid: int
    identity: ProcessIdentity
    argv: tuple[str, ...]


def _same_process(current: ProcessIdentity, expected: ProcessIdentity) -> bool:
    """Compare the stable kernel fields that protect against PID reuse."""

    return (
        current.pid == expected.pid
        and current.starttime == expected.starttime
    )


def _same_root_route(current: ProcessIdentity, expected: ProcessIdentity) -> bool:
    """Validate broad-signaling authority for a captured root process."""

    cwd_matches = (
        current.cwd is None
        or expected.cwd is None
        or current.cwd == expected.cwd
    )
    return (
        _same_process(current, expected)
        and current.process_group == expected.process_group
        and current.session == expected.session
        and cwd_matches
    )


def _linux_process_record(pid: int) -> _ProcessRecord | None:
    """Return one procfs record without scanning unrelated processes."""

    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        fields = stat[stat.rfind(")") + 2 :].split()
        if fields[0] == "Z":
            return None
        ppid = int(fields[1])
        starttime = int(fields[19])
        process_group = int(fields[2])
        session = int(fields[3])
    except (OSError, ValueError, IndexError):
        return None
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
    return _ProcessRecord(
        ppid=ppid,
        identity=ProcessIdentity(
            pid=pid,
            starttime=starttime,
            process_group=process_group,
            session=session,
            cwd=cwd,
        ),
        argv=argv,
    )


def _linux_process_snapshot() -> dict[int, _ProcessRecord]:
    """Return process records containing ancestry and kernel identity.

    ``starttime`` protects the termination path from PID reuse.  Procfs reads
    are intentionally best-effort because processes may exit between any two
    entries while the snapshot is being assembled.
    """

    if os.name != "posix" or not os.path.isdir("/proc"):
        return {}
    snapshot: dict[int, _ProcessRecord] = {}
    for raw_pid in os.listdir("/proc"):
        if not raw_pid.isdigit():
            continue
        pid = int(raw_pid)
        record = _linux_process_record(pid)
        if record is not None:
            snapshot[pid] = record
    return snapshot


def _capture_linux_descendants(
    expected_root: ProcessIdentity,
    *,
    deadline: float | None = None,
) -> tuple[dict[int, _ProcessRecord], bool]:
    """Capture one exact process tree and whether the walk was complete.

    Linux exposes each thread's direct children in procfs.  Walking those
    files keeps lifecycle cleanup proportional to the owned process tree;
    scanning every host PID can exceed bounded shutdown budgets on shared CI
    runners and busy production hosts.  Every parent is revalidated around
    its children read so PID reuse cannot introduce an unrelated subtree.
    """

    if os.name != "posix" or not os.path.isdir("/proc"):
        return {}, False

    records: dict[int, _ProcessRecord] = {}
    frontier = {expected_root.pid: expected_root}
    while frontier:
        if deadline is not None and time.monotonic() >= deadline:
            return records, False
        next_frontier: dict[int, ProcessIdentity] = {}
        for parent_pid, expected_parent in frontier.items():
            if deadline is not None and time.monotonic() >= deadline:
                return records, False
            before = _linux_process_record(parent_pid)
            if before is None or not _same_process(
                before.identity,
                expected_parent,
            ):
                return records, False
            records.setdefault(parent_pid, before)
            task_root = Path(f"/proc/{parent_pid}/task")
            try:
                task_ids = [
                    value for value in os.listdir(task_root) if value.isdigit()
                ]
            except OSError:
                return records, False
            child_pids: set[int] = set()
            for task_id in task_ids:
                if deadline is not None and time.monotonic() >= deadline:
                    return records, False
                try:
                    raw_children = (task_root / task_id / "children").read_text(
                        encoding="utf-8"
                    )
                except OSError:
                    return records, False
                for raw_pid in raw_children.split():
                    if raw_pid.isdigit():
                        child_pids.add(int(raw_pid))
            after = _linux_process_record(parent_pid)
            if after is None or not _same_process(
                after.identity,
                expected_parent,
            ):
                return records, False
            records[parent_pid] = after
            for child_pid in child_pids:
                if deadline is not None and time.monotonic() >= deadline:
                    return records, False
                if child_pid == expected_root.pid or child_pid in records:
                    continue
                record = _linux_process_record(child_pid)
                if record is None:
                    return records, False
                if record.ppid != parent_pid:
                    return records, False
                records[child_pid] = record
                next_frontier[child_pid] = record.identity
        frontier = next_frontier
    return records, True


def _linux_descendant_records(
    root_pid: int,
    *,
    deadline: float | None = None,
) -> dict[int, _ProcessRecord]:
    """Compatibility wrapper returning descendants of the observed root."""

    root = _linux_process_record(root_pid)
    if root is None:
        return {}
    records, _complete = _capture_linux_descendants(
        root.identity,
        deadline=deadline,
    )
    records.pop(root_pid, None)
    return records


async def _bounded_descendant_capture(
    expected_root: ProcessIdentity,
    *,
    deadline: float,
) -> tuple[dict[int, _ProcessRecord], bool]:
    """Run a read-only procfs walk within one event-loop deadline."""

    loop = asyncio.get_running_loop()
    remaining = max(deadline - loop.time(), 0.0)
    if remaining <= 0:
        return {}, False
    proc_deadline = time.monotonic() + remaining
    worker = asyncio.create_task(
        asyncio.to_thread(
            _capture_linux_descendants,
            expected_root,
            deadline=proc_deadline,
        )
    )

    def _consume_late_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except (asyncio.CancelledError, Exception):
            pass

    try:
        async with asyncio.timeout_at(deadline):
            return await asyncio.shield(worker)
    except TimeoutError:
        worker.add_done_callback(_consume_late_result)
        return {}, False
    except asyncio.CancelledError:
        worker.add_done_callback(_consume_late_result)
        raise


def _capture_live_processes(
    captured: dict[int, ProcessIdentity],
    *,
    deadline: float,
) -> tuple[dict[int, _ProcessRecord], bool]:
    """Read exact live identities without exceeding a monotonic deadline."""

    live: dict[int, _ProcessRecord] = {}
    for pid, expected in captured.items():
        if time.monotonic() >= deadline:
            return live, False
        record = _linux_process_record(pid)
        # Check after every procfs read, including the last one.  A result that
        # arrived outside the budget is never signaling authority.
        if time.monotonic() >= deadline:
            return live, False
        if record is not None and _same_process(record.identity, expected):
            live[pid] = record
    return live, True


async def _bounded_live_capture(
    captured: dict[int, ProcessIdentity],
    *,
    deadline: float,
) -> tuple[dict[int, _ProcessRecord], bool]:
    """Run one read-only live-identity snapshot behind a loop deadline."""

    loop = asyncio.get_running_loop()
    remaining = max(deadline - loop.time(), 0.0)
    if remaining <= 0:
        return {}, False
    worker = asyncio.create_task(
        asyncio.to_thread(
            _capture_live_processes,
            dict(captured),
            deadline=time.monotonic() + remaining,
        )
    )

    def _consume_late_result(task: asyncio.Task) -> None:
        try:
            task.result()
        except (asyncio.CancelledError, Exception):
            pass

    try:
        async with asyncio.timeout_at(deadline):
            return await asyncio.shield(worker)
    except TimeoutError:
        worker.add_done_callback(_consume_late_result)
        return {}, False
    except asyncio.CancelledError:
        worker.add_done_callback(_consume_late_result)
        raise


def capture_workspace_processes(
    workspace_path: str,
    *,
    ancestor_pid: int | None = None,
) -> dict[int, ProcessIdentity]:
    """Capture service-owned processes associated with *workspace_path*.

    Some third-party SDKs terminate only their immediate subprocess, allowing
    grandchildren to survive and continue editing after Oompah has forgotten
    the worker.  Before cancellation severs the ancestry, this function finds
    descendants of the service whose cwd or argv identifies the exact managed
    workspace, then includes every descendant of those matching processes.

    The returned mapping contains PID start time, process-group, session, and
    cwd identities and is safe to pass to :func:`terminate_captured_processes`.
    """

    root_pid = os.getpid() if ancestor_pid is None else int(ancestor_pid)
    snapshot = _linux_descendant_records(root_pid)
    if not snapshot:
        return {}
    workspace = os.path.realpath(workspace_path)
    workspace_prefix = workspace + os.sep

    seeds = {
        pid
        for pid in snapshot
        if (
            (snapshot[pid].identity.cwd == workspace)
            or bool(
                snapshot[pid].identity.cwd
                and snapshot[pid].identity.cwd.startswith(workspace_prefix)
            )
            or any(
                argument == workspace or argument.startswith(workspace_prefix)
                for argument in snapshot[pid].argv
            )
        )
    }
    selected = set(seeds)
    frontier = set(seeds)
    while frontier:
        parents = frontier
        frontier = {
            pid
            for pid, record in snapshot.items()
            if record.ppid in parents and pid not in selected
        }
        selected.update(frontier)
    return {pid: snapshot[pid].identity for pid in selected}


def terminate_captured_processes(
    captured: dict[int, int | ProcessIdentity],
    *,
    timeout_s: float = DEFAULT_STOP_TIMEOUT_S,
) -> set[int]:
    """Terminate an exact, PID-reuse-safe process set and return survivors."""

    if not captured:
        return set()

    # Older callers may still provide only a start time.  Normalize those
    # entries while retaining full identity for every process discovered by
    # the ownership-aware path.
    def _matches(
        snapshot: dict[int, _ProcessRecord],
        pid: int,
        expected: int | ProcessIdentity,
    ) -> bool:
        record = snapshot.get(pid)
        if record is None:
            return False
        if isinstance(expected, ProcessIdentity):
            return _same_process(record.identity, expected)
        return record.identity.starttime == int(expected)

    # Include children created in the narrow interval between the orchestrator's
    # capture and this termination worker beginning.  Validate each captured
    # root before walking only its kernel-reported descendants, avoiding an
    # unbounded scan of unrelated host processes.
    matched_roots: set[int] = set()
    for pid, expected in captured.items():
        record = _linux_process_record(pid)
        if record is not None and _matches({pid: record}, pid, expected):
            matched_roots.add(pid)
    for root_pid in matched_roots:
        for pid, record in _linux_descendant_records(root_pid).items():
            captured.setdefault(pid, record.identity)

    def _alive() -> set[int]:
        alive: set[int] = set()
        for pid, expected in captured.items():
            record = _linux_process_record(pid)
            if record is not None and _matches({pid: record}, pid, expected):
                alive.add(pid)
        return alive

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
        env: dict[str, str] | None = None,
        isolate_remote_write: bool = False,
        provider_auth_kind: str | None = None,
        before_transport_contact: Callable[[], str | None] | None = None,
        on_transport_contact: Callable[[], None] | None = None,
        on_precontact_admission_cancelled: Callable[[], None] | None = None,
    ):
        self.command = command
        self.workspace_path = workspace_path
        self.read_timeout_ms = read_timeout_ms
        self.turn_timeout_ms = turn_timeout_ms
        self.env = dict(env or {})
        self.isolate_remote_write = bool(isolate_remote_write)
        self.provider_auth_kind = provider_auth_kind
        self.before_transport_contact = before_transport_contact
        self.on_transport_contact = on_transport_contact
        self.on_precontact_admission_cancelled = (
            on_precontact_admission_cancelled
        )
        self._process: asyncio.subprocess.Process | None = None
        self._process_identity: ProcessIdentity | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._thread_id: str | None = None
        self._turn_id: str | None = None
        self._request_id = 0
        # Track temporary worker runtime directory for cleanup (OOMPAH-686)
        self._worker_runtime_dir: str | None = None
        self._transport_admitted = False
        self._transport_contacted = False
        self._transport_starting = False
        self._stop_requested = False
        self._stop_lock = asyncio.Lock()

    @property
    def transport_contacted(self) -> bool:
        """Whether the legacy CLI subprocess boundary was crossed."""

        return self._transport_contacted

    def _cancel_precontact_admission(self) -> None:
        """Return a permit when local CLI startup never created a process."""

        if not self._transport_admitted or self._transport_contacted:
            return
        self._transport_admitted = False
        callback = self.on_precontact_admission_cancelled
        if callback is None:
            return
        try:
            callback()
        except Exception:  # pragma: no cover - defensive authority cleanup
            logger.exception("Unable to roll back unused CLI contact admission")

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
        if self.isolate_remote_write:
            # A legacy CLI combines provider transport and an unrestricted
            # native shell in one child process.  It cannot safely receive
            # the provider credential required for transport while keeping
            # that shell out of the operator credential/network domain.
            # Direct rebase work must use an API/ACP bridged catalog instead.
            raise AgentError(
                "direct CLI agents are unavailable for shared-epic rebase work; "
                "select an API/ACP bridged provider",
                error_class="isolated_cli_unavailable",
            )
        try:
            # Prepare the agent environment (includes XDG_RUNTIME_DIR fallback)
            agent_env = agent_environment(
                {**os.environ, **self.env},
                workspace_path=self.workspace_path,
                isolate_remote_write=self.isolate_remote_write,
                provider_auth_kind=self.provider_auth_kind,
            )

            # Track the temporary worker runtime directory for cleanup (OOMPAH-686)
            self._worker_runtime_dir = agent_env.get("OOMPAH_WORKER_RUNTIME_DIR")

            if self._stop_requested:
                raise AgentError(
                    "Agent launch was cancelled before subprocess contact",
                    error_class="agent_launch_cancelled",
                )

            # This callback owns the exact runtime-authority CAS.  Keep it
            # adjacent to create_subprocess_exec: all environment and local
            # setup has completed, and there is no user callback or local
            # operation between the permit and the Popen edge.
            if self.before_transport_contact is not None:
                denial = self.before_transport_contact()
                if denial is not None:
                    raise AgentError(
                        denial,
                        error_class="provider_contact_denied",
                    )
                self._transport_admitted = True
                if self._stop_requested:
                    self._cancel_precontact_admission()
                    raise AgentError(
                        "Agent launch was cancelled before subprocess contact",
                        error_class="agent_launch_cancelled",
                    )

            self._transport_starting = True
            try:
                process_args = ["bash", "-lc", self.command]
                process = await asyncio.create_subprocess_exec(
                    *process_args,
                    cwd=self.workspace_path,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=agent_env,
                    start_new_session=(os.name == "posix"),
                    limit=MAX_LINE_SIZE,
                )
            finally:
                self._transport_starting = False
            # Publish the process and register its stderr reader without an
            # intervening await, so a racing stop always observes both.
            self._process = process
            self._stderr_task = asyncio.create_task(self._drain_stderr())
            if process.pid is not None:
                record = _linux_process_record(process.pid)
                if record is not None:
                    expected_cwd = os.path.realpath(self.workspace_path)
                    if record.identity.cwd in {None, expected_cwd}:
                        observed = record.identity
                        self._process_identity = ProcessIdentity(
                            pid=observed.pid,
                            starttime=observed.starttime,
                            process_group=observed.process_group,
                            session=observed.session,
                            cwd=expected_cwd,
                        )
            self._transport_contacted = True
            self._transport_admitted = False
            if self.on_transport_contact is not None:
                try:
                    self.on_transport_contact()
                except Exception:  # pragma: no cover - observer only
                    logger.exception("Unable to publish CLI transport contact")
            if self._stop_requested:
                # Admission won the exact edge race, so the subprocess is a
                # real contacted attempt.  Retire it immediately rather than
                # returning an untracked process to the caller.
                await self.stop()
                raise AgentError(
                    "Agent launch was cancelled at subprocess contact",
                    error_class="agent_launch_cancelled",
                )
        except asyncio.CancelledError:
            self._cancel_precontact_admission()
            raise
        except FileNotFoundError:
            self._cancel_precontact_admission()
            raise AgentError(
                f"Agent command not found: {self.command}",
                error_class="agent_not_found",
            )
        except Exception:
            self._cancel_precontact_admission()
            raise

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

        # SECURITY: the raw subprocess message may quote back an
        # authorization header, URL with userinfo, or configured
        # credential. Redact before packaging into the AgentEvent so
        # every downstream consumer (JSONL log, orchestrator state,
        # WS fan-out) sees only scrubbed text.
        from oompah.secrets import redact_sensitive_data as _redact

        _redacted_summary = _redact(summary)
        if not isinstance(_redacted_summary, str):
            _redacted_summary = str(_redacted_summary)

        return AgentEvent(
            event=event_name,
            timestamp=now,
            agent_pid=self.pid,
            usage=usage,
            payload={"message": _redacted_summary, "method": method},
        )

    async def stop(self, timeout_s: float = DEFAULT_STOP_TIMEOUT_S) -> None:
        """Terminate the agent subprocess and all of its descendants."""
        self._stop_requested = True
        process = self._process
        if process is None:
            # When create_subprocess_exec is already in flight, the contact
            # permit won the linearization race.  ``start`` will observe the
            # stop flag immediately after Popen and retire the child.  A stop
            # before that edge returns any unused permit here.
            if not self._transport_starting:
                self._cancel_precontact_admission()
            return

        async with self._stop_lock:
            await self._stop_locked(process, max(float(timeout_s), 0.0))

    async def _stop_locked(
        self,
        process: asyncio.subprocess.Process,
        timeout_s: float,
    ) -> None:
        """Stop one process tree while holding the session stop lock."""

        pid = process.pid
        is_real_process = isinstance(process, asyncio.subprocess.Process)
        use_process_group = (
            os.name == "posix" and pid is not None and hasattr(os, "killpg")
        )
        identity = self._process_identity
        captured: dict[int, ProcessIdentity] = {}
        captured_parents: dict[int, int] = {}
        group_authorized = False
        transport_closed = False
        loop = asyncio.get_running_loop()
        started = loop.time()
        deadline = started + timeout_s
        term_deadline = started + (timeout_s * 0.7)
        kill_deadline = started + (timeout_s * 0.9)
        capture_deadline = started + (timeout_s * 0.2)
        capture_complete = not is_real_process

        # Capture the exact tree once, before the first signal can sever its
        # ancestry.  A missing launch identity remains fail-closed on Linux.
        if is_real_process and identity is not None and pid is not None:
            records, capture_complete = await _bounded_descendant_capture(
                identity,
                deadline=capture_deadline,
            )
            root_record = records.pop(pid, None)
            if root_record is not None and _same_process(
                root_record.identity,
                identity,
            ):
                captured[pid] = identity
                captured.update(
                    {
                        child_pid: record.identity
                        for child_pid, record in records.items()
                    }
                )
                captured_parents.update(
                    {
                        child_pid: record.ppid
                        for child_pid, record in records.items()
                    }
                )
                group_authorized = (
                    identity.process_group == pid
                    and identity.session == pid
                    and _same_root_route(root_record.identity, identity)
                )
            else:
                capture_complete = False

        root_provenance = bool(pid is not None and pid in captured)

        async def _live_captured(
            live_deadline: float,
        ) -> tuple[dict[int, _ProcessRecord], bool]:
            nonlocal capture_complete
            live, complete = await _bounded_live_capture(
                captured,
                deadline=live_deadline,
            )
            capture_complete = capture_complete and complete
            return live, complete

        async def _refresh_live_descendants(
            refresh_deadline: float,
        ) -> None:
            """Capture TERM-handler children from non-overlapping live roots."""

            nonlocal capture_complete
            live, _complete = await _live_captured(refresh_deadline)
            live_pids = set(live)
            roots = [
                child_pid
                for child_pid in live
                if captured_parents.get(child_pid) not in live_pids
            ]
            for root_pid in roots:
                if loop.time() >= refresh_deadline:
                    capture_complete = False
                    break
                records, complete = await _bounded_descendant_capture(
                    captured[root_pid],
                    deadline=refresh_deadline,
                )
                capture_complete = capture_complete and complete
                records.pop(root_pid, None)
                for child_pid, record in records.items():
                    captured.setdefault(child_pid, record.identity)
                    captured_parents.setdefault(child_pid, record.ppid)

        def _mock_tree_is_running() -> bool:
            if process.returncode is not None:
                return False
            if not use_process_group:
                return True
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
            return True

        async def _signal_tree(
            sig: signal.Signals,
            operation_deadline: float,
        ) -> None:
            nonlocal capture_complete
            if not is_real_process:
                if use_process_group:
                    try:
                        os.killpg(pid, sig)
                        return
                    except ProcessLookupError:
                        return
                    except OSError:
                        pass
                try:
                    if sig == getattr(signal, "SIGKILL", signal.SIGTERM):
                        process.kill()
                    else:
                        process.terminate()
                except ProcessLookupError:
                    pass
                return

            live, _complete = await _live_captured(operation_deadline)
            # Incompleteness means this is not a full liveness observation,
            # but every returned record still passed the exact PID/starttime
            # check.  Those records remain safe signaling authority; only an
            # empty *complete* snapshot may prove retirement.
            if not live:
                logger.warning(
                    "Refusing to signal agent without an exact live identity "
                    "pid=%s workspace=%s",
                    pid,
                    self.workspace_path,
                )
                return

            group_signalled = False
            if group_authorized and identity is not None:
                group_id = identity.process_group
                group_session = identity.session
                group_anchor = any(
                    record.identity.process_group == group_id
                    and record.identity.session == group_session
                    for record in live.values()
                )
                if group_anchor:
                    try:
                        os.killpg(group_id, sig)
                        group_signalled = True
                    except (ProcessLookupError, PermissionError):
                        pass

            # Stable PID/starttime ownership survives a descendant changing
            # cwd, process group, or session in response to SIGTERM.
            for child_pid, record in sorted(live.items(), reverse=True):
                if (
                    group_signalled
                    and identity is not None
                    and record.identity.process_group == identity.process_group
                    and record.identity.session == identity.session
                ):
                    continue
                try:
                    os.kill(child_pid, sig)
                except (ProcessLookupError, PermissionError):
                    continue

        async def _wait_until(deadline: float) -> bool:
            nonlocal capture_complete
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return False
                if not is_real_process:
                    running = _mock_tree_is_running()
                else:
                    live, complete = await _live_captured(deadline)
                    # An incomplete snapshot is uncertainty, not proof that
                    # the process tree stopped.  Escalate while later phases
                    # still have their independently reserved budgets.
                    if not complete:
                        return False
                    running = bool(live)
                if not running:
                    return True
                await asyncio.sleep(min(STOP_POLL_INTERVAL_S, remaining))

        async def _join_process_transport(deadline: float) -> bool:
            """Join the child and stderr reader without exceeding *deadline*."""

            if not isinstance(process, asyncio.subprocess.Process):
                return True

            nonlocal transport_closed
            stderr_task = self._stderr_task

            def _may_close() -> bool:
                return process.returncode is not None or (
                    root_provenance and capture_complete
                )

            def _close_transport() -> None:
                nonlocal transport_closed
                if transport_closed:
                    return
                transport = getattr(process, "_transport", None)
                if transport is not None:
                    transport.close()
                    transport_closed = True

            may_close = _may_close()
            if (
                may_close
                and process.stdin is not None
                and not process.stdin.is_closing()
            ):
                process.stdin.close()

            async def _wait_process(wait_deadline: float) -> bool:
                if process.returncode is not None and transport_closed:
                    await asyncio.sleep(0)
                if loop.time() >= wait_deadline:
                    return False
                try:
                    async with asyncio.timeout_at(wait_deadline):
                        await process.wait()
                except TimeoutError:
                    return False
                return True

            async def _wait_stderr(
                wait_deadline: float,
                *,
                cancel: bool = False,
            ) -> bool:
                if stderr_task is None or stderr_task is asyncio.current_task():
                    return True
                if cancel and not stderr_task.done():
                    stderr_task.cancel()
                if not stderr_task.done() and loop.time() < wait_deadline:
                    try:
                        async with asyncio.timeout_at(wait_deadline):
                            if cancel:
                                await stderr_task
                            else:
                                await asyncio.shield(stderr_task)
                    except TimeoutError:
                        pass
                    except asyncio.CancelledError:
                        if not cancel and not stderr_task.cancelled():
                            raise
                if stderr_task.done():
                    try:
                        stderr_task.result()
                    except (asyncio.CancelledError, Exception):
                        pass
                    return True
                return False

            join_started = loop.time()
            remaining = max(deadline - join_started, 0.0)
            probe_deadline = join_started + (remaining * 0.5)
            completion_deadline = join_started + (remaining * 0.9)

            # A published return code with a pending stderr reader is exactly
            # the inherited-pipe case.  Close it before spending the budget.
            if (
                may_close
                and stderr_task is not None
                and not stderr_task.done()
                and process.returncode is not None
            ):
                _close_transport()

            process_done = await _wait_process(probe_deadline)
            stderr_done = await _wait_stderr(probe_deadline)
            may_close = _may_close()
            if (not process_done or not stderr_done) and may_close:
                _close_transport()
                await asyncio.sleep(0)

            if not process_done:
                process_done = await _wait_process(completion_deadline)
            if not stderr_done:
                stderr_done = await _wait_stderr(completion_deadline)
            may_close = _may_close()
            if not stderr_done and may_close:
                _close_transport()
                await asyncio.sleep(0)
            if not stderr_done and may_close:
                stderr_done = await _wait_stderr(deadline, cancel=True)
            if not process_done:
                process_done = await _wait_process(deadline)

            # Let final pipe connection_lost callbacks run before a short-lived
            # test event loop is closed.
            await asyncio.sleep(0)
            return process_done and stderr_done

        stopped = False
        transport_clean = False

        try:
            if captured or not is_real_process:
                stopped = not is_real_process and not _mock_tree_is_running()
                if not stopped:
                    await _signal_tree(signal.SIGTERM, term_deadline)
                    stopped = await _wait_until(term_deadline)
                    if not stopped:
                        escalation_window = kill_deadline - term_deadline
                        refresh_deadline = term_deadline + (
                            escalation_window * 0.5
                        )
                        signal_deadline = term_deadline + (
                            escalation_window * 0.8
                        )
                        await _refresh_live_descendants(refresh_deadline)
                        await _signal_tree(
                            getattr(signal, "SIGKILL", signal.SIGTERM),
                            signal_deadline,
                        )
                        stopped = await _wait_until(kill_deadline)
            transport_clean = await _join_process_transport(deadline)
        except asyncio.CancelledError:
            # Cancellation completes a bounded hard stop synchronously.  No
            # private cleanup task is left behind for production callers.
            hard_started = loop.time()
            hard_budget = min(
                max(timeout_s * 0.2, STOP_POLL_INTERVAL_S),
                1.0,
            )
            hard_deadline = hard_started + hard_budget
            hard_refresh_deadline = hard_started + (hard_budget * 0.4)
            hard_signal_deadline = hard_started + (hard_budget * 0.6)
            hard_observe_deadline = hard_started + (hard_budget * 0.7)
            await _refresh_live_descendants(hard_refresh_deadline)
            await _signal_tree(
                getattr(signal, "SIGKILL", signal.SIGTERM),
                hard_signal_deadline,
            )
            stopped = await _wait_until(hard_observe_deadline)
            transport_clean = await _join_process_transport(hard_deadline)
            raise

        if is_real_process and not captured:
            logger.warning(
                "Agent identity provenance was unavailable; descendants may "
                "remain pid=%s workspace=%s",
                pid,
                self.workspace_path,
            )
        elif not stopped:
            logger.warning(
                "Agent process tree did not exit within %.3fs pid=%s",
                timeout_s,
                pid,
            )
        if not capture_complete:
            logger.warning(
                "Agent descendant capture was incomplete pid=%s workspace=%s",
                pid,
                self.workspace_path,
            )
        if not transport_clean:
            logger.warning(
                "Agent process transport did not close within %.3fs pid=%s",
                timeout_s,
                pid,
            )
        retirement_complete = (
            stopped
            and transport_clean
            and capture_complete
            and (not is_real_process or bool(captured))
        )
        if retirement_complete:
            logger.info("Agent process stopped pid=%s", pid)
        else:
            logger.warning(
                "Agent process retirement incomplete pid=%s workspace=%s",
                pid,
                self.workspace_path,
            )

        # Preserve the established runtime-directory cleanup behavior only for
        # a successful normal stop.  Pre-contact cleanup is a separate concern.
        if (
            self._worker_runtime_dir
            and retirement_complete
        ):
            self._cleanup_worker_runtime_dir()

    def _cleanup_worker_runtime_dir(self) -> None:
        """Remove the temporary worker runtime directory created in start().

        This is called from stop() after the worker process has exited.
        The directory may contain podman/container artifacts that cannot be
        cleaned up from inside the sandbox (it's read-only), so cleanup happens
        from the orchestrator process. Failures are logged but not fatal.
        """
        if not self._worker_runtime_dir:
            return

        try:
            if os.path.isdir(self._worker_runtime_dir):
                shutil.rmtree(self._worker_runtime_dir, ignore_errors=True)
                logger.debug(
                    "Cleaned up temporary worker runtime directory: %s",
                    self._worker_runtime_dir,
                )
            else:
                logger.debug(
                    "Worker runtime directory already removed: %s",
                    self._worker_runtime_dir,
                )
        except Exception as exc:
            logger.warning(
                "Failed to clean up worker runtime directory %s: %s; "
                "administrator may need to manually remove",
                self._worker_runtime_dir,
                exc,
            )
