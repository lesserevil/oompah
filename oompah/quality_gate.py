"""Persistent, single-flight quality gates for review-ready branch heads."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

logger = logging.getLogger(__name__)

_EVIDENCE_VERSION = 2
_OOMPAH_652_SAFETY_HEAD = "ec0ec7d89fb8804571fcf7e780558e6d979b73ea"

_SANDBOX_RUN_ROOT = Path("/oompah-gate")


class _SandboxUnavailable(RuntimeError):
    """Raised when the operator cannot create the required OS boundary."""


@dataclass(frozen=True)
class QualityGateResult:
    """Outcome of checking one exact branch head with one exact command."""

    status: str
    head_sha: str
    command: str
    duration_seconds: float = 0.0
    output_tail: str = ""
    cached: bool = False

    @property
    def passed(self) -> bool:
        return self.status in {"passed", "not_configured"}


@dataclass
class _KeyLockEntry:
    """One in-process single-flight lock plus its current users."""

    lock: threading.Lock
    users: int = 0


class BranchQualityGate:
    """Run and persist full branch checks without duplicate concurrent work.

    Outcomes are keyed by repository identity, target branch, work branch,
    exact head SHA, and command. Any new commit, rebase, target, or command
    therefore invalidates them naturally. A process-wide lock makes concurrent
    readiness sweeps single-flight; persisted results make readiness recovery
    safe across service restarts.
    """

    # Class-level tracking of active process groups for graceful shutdown.
    # Maps pid -> process object for cleanup on orchestrator stop.
    _active_processes: dict[int, subprocess.Popen[str]] = {}
    # Keep generation and snapshot ownership beside the process itself.  A
    # task may be reopened while an old gate is still running; generation
    # scoping ensures cancellation cannot terminate a replacement gate.
    _active_generations: dict[int, str | None] = {}
    _active_snapshots: dict[int, Path] = {}
    # Durable tombstones for cancelled generations: set before the gate
    # spawns so that pre-spawn authority withdrawals (during snapshot
    # creation or between Popen and registration) are guaranteed to stop
    # the gate even if the process is not yet in _active_generations.
    # Protected by _processes_lock.  A tombstone is retained until every
    # caller that had entered ``run`` for that generation has left it.  This
    # is deliberately not a per-call finally cleanup: another same-generation
    # caller may still be waiting on the evidence-key lock.
    _cancelled_generations: set[str] = set()
    _generation_run_counts: dict[str, int] = {}
    # Cancel-before-spawn has no running caller to release the tombstone. Keep
    # those records in LRU order so abandoned generations cannot grow this
    # process-wide registry without bound.
    _cancelled_generation_order: dict[str, None] = {}
    _MAX_CANCELLED_GENERATIONS = 1024
    _processes_lock = threading.Lock()

    def __init__(
        self,
        state_path: str,
        *,
        timeout_seconds: int = 3600,
        output_tail_bytes: int = 16 * 1024,
        safety_head: str = _OOMPAH_652_SAFETY_HEAD,
        sandbox_launcher: Callable[[str, str, Path], list[str]] | None = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.timeout_seconds = max(int(timeout_seconds), 1)
        self.output_tail_bytes = max(int(output_tail_bytes), 1024)
        self.safety_head = safety_head
        self._sandbox_launcher = sandbox_launcher or self._sandbox_command
        self._lock = threading.Lock()
        self._key_locks: dict[str, _KeyLockEntry] = {}

    @classmethod
    def _terminate_active_processes(
        cls,
        *,
        generation: str | None = None,
    ) -> int:
        """Terminate active process groups owned by *generation*.

        When *generation* is given, the generation is also added to
        _cancelled_generations so that gates not yet spawned (during snapshot
        creation or between Popen and registration) also see the cancellation
        on their next barrier check.

        Keeping this operation centralized makes shutdown and task-specific
        cancellation use the same process-group and snapshot cleanup rules.
        """
        with cls._processes_lock:
            processes = [
                (pid, process)
                for pid, process in cls._active_processes.items()
                if generation is None
                or cls._active_generations.get(pid) == generation
            ]
            for _pid, process in processes:
                # The run thread uses this marker to return a non-cached
                # interruption instead of recording a false CI failure.
                setattr(process, "_oompah_interrupted", True)
            # Record a durable tombstone so that gates currently between
            # pre-spawn barrier checks (snapshot creation, Popen-to-
            # registration window) also stop on their next check.
            if generation is not None:
                cls._mark_generation_cancelled_locked(generation)

        terminated_count = 0
        for pid, process in processes:
            try:
                os.killpg(pid, signal.SIGTERM)
                terminated_count += 1
            except ProcessLookupError:
                pass
            except OSError as exc:
                logger.warning(
                    "Failed to terminate quality gate process group %d: %s",
                    pid,
                    exc,
                )
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    logger.warning(
                        "Failed to kill quality gate process group %d: %s",
                        pid,
                        exc,
                    )
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(
                        "Quality gate process group %d did not stop after SIGKILL",
                        pid,
                    )
            with cls._processes_lock:
                cls._active_processes.pop(pid, None)
                cls._active_generations.pop(pid, None)
                cls._active_snapshots.pop(pid, None)

        if terminated_count:
            logger.info(
                "Interrupted %d active quality gate process group(s)",
                terminated_count,
            )
        return terminated_count

    @classmethod
    def cleanup_active_processes(cls) -> int:
        """Terminate all active quality gate process groups.

        Called during orchestrator shutdown to ensure process groups are
        cleaned up before leases become reclaimable. Returns count terminated.
        """
        return cls._terminate_active_processes()

    @classmethod
    def cancel_generation(cls, generation: str) -> int:
        """Cancel only gates belonging to one exact task generation.

        Sets a durable tombstone so that gates currently between pre-spawn
        barrier checks (during snapshot creation or between Popen and
        registration) also stop when they next reach a check point.
        """
        return cls._terminate_active_processes(generation=str(generation))

    @classmethod
    def _generation_is_cancelled(cls, generation: str) -> bool:
        """Return True when *generation* has been tombstoned by cancel_generation."""
        with cls._processes_lock:
            return generation in cls._cancelled_generations

    @classmethod
    def _mark_generation_cancelled_locked(cls, generation: str) -> None:
        """Tombstone *generation* while holding ``_processes_lock``."""
        cls._cancelled_generations.add(generation)
        cls._cancelled_generation_order.pop(generation, None)
        cls._cancelled_generation_order[generation] = None
        cls._prune_cancelled_generations_locked()

    @classmethod
    def _prune_cancelled_generations_locked(cls) -> None:
        """Bound inactive cancel-before-spawn tombstones by LRU age."""
        while len(cls._cancelled_generation_order) > cls._MAX_CANCELLED_GENERATIONS:
            oldest = next(iter(cls._cancelled_generation_order))
            if oldest not in cls._cancelled_generations:
                cls._cancelled_generation_order.pop(oldest, None)
                continue
            if cls._generation_run_counts.get(oldest, 0) > 0:
                # Active/waiting callers must keep their cancellation fence.
                # Move it behind inactive candidates and stop if all entries
                # are active; normal completion will release it later.
                cls._cancelled_generation_order.pop(oldest)
                cls._cancelled_generation_order[oldest] = None
                if all(
                    cls._generation_run_counts.get(generation, 0) > 0
                    for generation in cls._cancelled_generation_order
                ):
                    return
                continue
            cls._cancelled_generation_order.pop(oldest, None)
            cls._cancelled_generations.discard(oldest)

    @classmethod
    def _register_generation(cls, generation: str) -> None:
        """Record a caller before it can wait behind a single-flight lock."""
        with cls._processes_lock:
            cls._generation_run_counts[generation] = (
                cls._generation_run_counts.get(generation, 0) + 1
            )

    @classmethod
    def _release_generation(cls, generation: str) -> None:
        """Release one caller and retire a cancelled generation when it is idle."""
        with cls._processes_lock:
            remaining = cls._generation_run_counts.get(generation, 0) - 1
            if remaining > 0:
                cls._generation_run_counts[generation] = remaining
                return
            cls._generation_run_counts.pop(generation, None)
            cls._cancelled_generations.discard(generation)
            cls._cancelled_generation_order.pop(generation, None)

    @staticmethod
    def _head_sha(repo_path: str) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return result.stdout.strip()

    @staticmethod
    def _resolve_commit(repo_path: str, commit: str) -> str:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"{commit}^{{commit}}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return result.stdout.strip()

    def _verify_isolation_contract(self, repo_path: str) -> tuple[bool, str]:
        """Verify the candidate is based on the deployed lifecycle contract.

        The quality gate runs in a disposable worktree. Candidate code cannot be trusted
        to implement its own containment boundary. A same-UID process with access to the
        source tree can read absolute canonical paths, connect to localhost:8090, or
        signal the operator service regardless of environment variables or marker strings.

        The OS sandbox is the containment boundary; the candidate is expressly
        allowed to evolve its Makefile and test runner.  This preflight only
        establishes that a recovered branch has been rebased onto the durable,
        operator-configured lifecycle base.  All checks happen before Popen,
        so a rejected candidate command never gets a chance to inspect or
        signal the operator service.

        Returns:
            (is_compliant, reason) — True if the branch contains OOMPAH-652 safety head
            in its ancestry, False if the branch needs rebase.
        """
        safety_head = self.safety_head
        if not isinstance(safety_head, str) or len(safety_head) != 40:
            return False, "Configured lifecycle safety head is not a full commit SHA"
        try:
            int(safety_head, 16)
        except ValueError:
            return False, "Configured lifecycle safety head is not a full commit SHA"

        # Verify git repository exists and is valid
        repo_path_obj = Path(repo_path)
        if not (repo_path_obj / ".git").exists():
            return False, "Not a git repository (required for ancestry verification)"

        try:
            # Check if the safety head commit is an ancestor of HEAD in this
            # repository.  This uses git merge-base --is-ancestor which is
            # efficient and cannot be spoofed by Makefile marker text.
            result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", safety_head, "HEAD"],
                cwd=repo_path,
                capture_output=True,
                timeout=5,
            )
            # merge-base --is-ancestor exits 0 if ancestor exists, non-zero otherwise.
            if result.returncode == 0:
                dirty = subprocess.run(
                    [
                        "git",
                        "diff",
                        "--quiet",
                        "HEAD",
                        "--",
                    ],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if dirty.returncode not in {0, 1}:
                    return False, "Cannot inspect quality-gate worktree state"
                if dirty.returncode == 1:
                    return (
                        False,
                        "The quality-gate worktree has uncommitted changes. "
                        "Commit and push the repair before rerunning the exact "
                        "review-head gate.",
                    )
                return True, ""
            return (
                False,
                f"Branch does not contain the deployed OOMPAH-652 isolation "
                f"contract (commit {safety_head}). This branch was likely "
                "created before the safety prerequisite was merged. Rebase "
                "to the current base before rerunning the gate; see "
                "OOMPAH-652 and OOMPAH-655 for lifecycle isolation details.",
            )
        except subprocess.TimeoutExpired:
            return False, "Git ancestry check timed out (git repository may be corrupted)"
        except OSError as exc:
            return False, f"Cannot verify git ancestry: {exc}"

    @staticmethod
    def _gate_run_root() -> Path:
        """Create an operator-owned, private root for one candidate command."""
        root = Path(tempfile.mkdtemp(prefix="oompah-quality-gate-"))
        os.chmod(root, 0o700)
        for relative in ("home", "tmp", "cache", "config", "data", "lifecycle"):
            path = root / relative
            path.mkdir(mode=0o700)
        return root

    @staticmethod
    def _cleanup_gate_run_root(root: Path) -> None:
        """Remove only a root created by :meth:`_gate_run_root`."""
        try:
            resolved = root.resolve(strict=False)
            temp_root = Path(tempfile.gettempdir()).resolve()
            if (
                resolved.parent != temp_root
                or not resolved.name.startswith("oompah-quality-gate-")
                or root.is_symlink()
                or not root.exists()
                or root.stat().st_uid != os.getuid()
            ):
                logger.warning("Refusing to remove unexpected gate root %s", root)
                return
            shutil.rmtree(root)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("Failed to clean quality gate root %s: %s", root, exc)

    @staticmethod
    def _snapshot_candidate_worktree(
        repo_path: str,
        run_root: Path,
        head_sha: str = "HEAD",
    ) -> Path:
        """Archive the exact candidate head into a disposable gate workspace.

        A candidate command must never receive a writable bind of the service's
        live worktree.  ``git archive`` takes only tracked files at ``HEAD``;
        this excludes operator .env/PID/log files and all other untracked
        state.  The archive is extracted with tar's data filter so a malicious
        symlink cannot escape the private run root.
        """
        snapshot = run_root / "workspace"
        archive_path = run_root / "candidate.tar"
        try:
            archive = subprocess.run(
                [
                    "git",
                    "archive",
                    "--format=tar",
                    f"--output={archive_path}",
                    head_sha,
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise _SandboxUnavailable(
                f"cannot create an immutable candidate snapshot: {exc}"
            ) from exc
        if archive.returncode != 0:
            detail = (archive.stderr or archive.stdout).strip()[-500:]
            raise _SandboxUnavailable(
                "cannot create an immutable candidate snapshot"
                + (f": {detail}" if detail else "")
            )
        try:
            snapshot.mkdir(mode=0o700)
            with tarfile.open(archive_path) as candidate_archive:
                for member in candidate_archive:
                    member_path = PurePosixPath(member.name)
                    if (
                        not member_path.parts
                        or member_path.is_absolute()
                        or ".." in member_path.parts
                        or member.isdev()
                        or member.isfifo()
                    ):
                        raise tarfile.TarError(
                            f"unsafe member in candidate archive: {member.name!r}"
                        )
                    if member.issym() or member.islnk():
                        link_path = PurePosixPath(member.linkname)
                        if link_path.is_absolute() or ".." in link_path.parts:
                            raise tarfile.TarError(
                                "unsafe link in candidate archive: "
                                f"{member.name!r} -> {member.linkname!r}"
                            )
                    # Oompah supports Python 3.11, whose early releases did
                    # not accept ``filter``.  We apply the same validation
                    # above, then use an explicit compatibility filter where
                    # the newer tarfile API is available.
                    try:
                        candidate_archive.extract(
                            member, path=snapshot, filter="fully_trusted"
                        )
                    except TypeError:
                        candidate_archive.extract(member, path=snapshot)
            archive_path.unlink()
            # Preserve exact-revision tests without exposing the service's
            # live object database, worktree metadata, remotes, or hooks.  A
            # shallow local fetch copies only the candidate commit into this
            # disposable repository; reset populates the index but never
            # replaces the archive contents validated above.
            commands = (
                ("git", "init", "--quiet"),
                (
                    "git",
                    "fetch",
                    "--quiet",
                    "--depth=1",
                    "--no-tags",
                    str(Path(repo_path).resolve()),
                    str(head_sha),
                ),
            )
            for command in commands:
                completed = subprocess.run(
                    command,
                    cwd=snapshot,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if completed.returncode != 0:
                    detail = (completed.stderr or completed.stdout).strip()[-500:]
                    raise tarfile.TarError(
                        "cannot create private exact-head Git metadata"
                        + (f": {detail}" if detail else "")
                    )
            private_head = subprocess.run(
                ["git", "rev-parse", "FETCH_HEAD"],
                cwd=snapshot,
                capture_output=True,
                text=True,
                check=True,
                timeout=15,
            ).stdout.strip()
            for command in (
                ("git", "update-ref", "refs/heads/quality-gate", private_head),
                ("git", "symbolic-ref", "HEAD", "refs/heads/quality-gate"),
                ("git", "reset", "--mixed", "--quiet", private_head),
            ):
                subprocess.run(
                    command,
                    cwd=snapshot,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=15,
                )
            (snapshot / ".git" / "FETCH_HEAD").unlink(missing_ok=True)
        except (OSError, tarfile.TarError) as exc:
            raise _SandboxUnavailable(
                f"cannot prepare an immutable candidate snapshot: {exc}"
            ) from exc
        except subprocess.SubprocessError as exc:
            raise _SandboxUnavailable(
                f"cannot prepare private exact-head Git metadata: {exc}"
            ) from exc
        return snapshot

    @staticmethod
    def _quality_gate_environment(run_root: Path) -> dict[str, str]:
        """Build the complete server-owned lifecycle environment for a gate."""
        # Do not inherit the server environment wholesale.  In particular,
        # inherited OOMPAH/PIP/UV variables can point at operator state even
        # when the corresponding filesystem paths are hidden.  Keep only
        # display/locale settings plus a path backed by the sandbox's /usr.
        environment = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
        for key in ("LANG", "LC_ALL", "LC_CTYPE", "TERM"):
            value = os.environ.get(key)
            if value:
                environment[key] = value
        # The host root is bound at _SANDBOX_RUN_ROOT.  Export only that
        # sandbox-visible path: a host tempfile path would be inaccessible
        # after /tmp and /home are hidden by bubblewrap.
        private_tmp = _SANDBOX_RUN_ROOT / "tmp"
        private_lifecycle = _SANDBOX_RUN_ROOT / "lifecycle"
        private_home = _SANDBOX_RUN_ROOT / "home"
        # Bind-and-close allocation is the portable interface available to the
        # existing Makefile contract.  The candidate still cannot select the
        # operator's configured port because this value is server-generated.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            private_port = str(listener.getsockname()[1])

        environment.update(
            {
                "OOMPAH_PYTEST_GATE": "1",
                "OOMPAH_PYTEST_RUN_ROOT": str(_SANDBOX_RUN_ROOT),
                "OOMPAH_PYTEST_TEMP_ROOT": str(private_tmp),
                "OOMPAH_TEMP_ROOT": str(private_tmp),
                "OOMPAH_TEST_SERVER_PORT": private_port,
                "OOMPAH_SERVER_PORT": private_port,
                "OOMPAH_TEST_PID_FILE": str(private_lifecycle / ".oompah.pid"),
                "OOMPAH_TEST_PID_META_FILE": str(
                    private_lifecycle / ".oompah.pid.meta"
                ),
                "HOME": str(private_home),
                "TMPDIR": str(private_tmp),
                "TMP": str(private_tmp),
                "TEMP": str(private_tmp),
                "XDG_CACHE_HOME": str(_SANDBOX_RUN_ROOT / "cache"),
                "XDG_CONFIG_HOME": str(_SANDBOX_RUN_ROOT / "config"),
                "XDG_DATA_HOME": str(_SANDBOX_RUN_ROOT / "data"),
                "PYTHONPYCACHEPREFIX": str(
                    _SANDBOX_RUN_ROOT / "cache" / "pycache"
                ),
            }
        )
        return environment

    @staticmethod
    def _sandbox_command(
        command: str,
        repo_path: str,
        run_root: Path,
    ) -> list[str]:
        """Return a bubblewrap command with host lifecycle state hidden.

        The candidate command runs in a private mount, PID, and network
        namespace.  The repository and one operator-created run root are the
        only task-owned paths made visible.  If bubblewrap or unprivileged
        namespaces are unavailable, the caller fails closed before starting
        candidate code.
        """
        bubblewrap = shutil.which("bwrap")
        if not bubblewrap:
            raise _SandboxUnavailable(
                "bubblewrap is not installed; refusing to run an unsandboxed gate"
            )

        probe = subprocess.run(
            [
                bubblewrap,
                "--die-with-parent",
                "--new-session",
                "--unshare-user",
                "--unshare-pid",
                "--unshare-net",
                "--cap-add",
                "CAP_NET_ADMIN",
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "--ro-bind",
                "/usr",
                "/usr",
                "--symlink",
                "usr/bin",
                "/bin",
                # The ELF dynamic loader lives at /lib64/ld-linux-*.so on many
                # distributions where /lib64 -> usr/lib64.  Without this
                # symlink in the probe namespace, execvp /bin/sh fails with
                # "No such file or directory" even though /usr is bound.
                "--symlink",
                "usr/lib64",
                "/lib64",
                "/bin/sh",
                "-c",
                # Verify that /bin/sh runs and the network namespace was
                # created (lo exists).  Do not require ip link set to
                # succeed: on kernel 6.x the loopback carries
                # netns-immutable and starts UP without an explicit set,
                # so ip link set lo up returns EPERM even though the
                # interface is already functional.
                "ip link show lo >/dev/null 2>&1",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if probe.returncode != 0:
            detail = (probe.stderr or probe.stdout).strip()[-500:]
            raise _SandboxUnavailable(
                "bubblewrap cannot create the required OS namespaces"
                + (f": {detail}" if detail else "")
            )

        repo = Path(repo_path).resolve()
        if not repo.is_dir() or repo.is_symlink():
            raise _SandboxUnavailable("quality-gate worktree is not a real directory")

        # Start from an empty root rather than a read-only host root.  Candidate
        # code receives only a disposable source snapshot, its private gate
        # state, and the runtime needed to execute the configured command.
        args = [
            bubblewrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-net",
            "--cap-add",
            "CAP_NET_ADMIN",
            "--tmpfs",
            "/",
            "--dir",
            "/usr",
            "--ro-bind",
            "/usr",
            "/usr",
            "--symlink",
            "usr/bin",
            "/bin",
            "--symlink",
            "usr/sbin",
            "/sbin",
            "--symlink",
            "usr/lib",
            "/lib",
            "--symlink",
            "usr/lib64",
            "/lib64",
            "--dir",
            "/dev",
            "--dev",
            "/dev",
            "--dir",
            "/proc",
            "--proc",
            "/proc",
            "--dir",
            "/tmp",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/var",
            "--dir",
            "/var/tmp",
            "--tmpfs",
            "/var/tmp",
            "--dir",
            "/home",
            "--tmpfs",
            "/home",
        ]

        # bwrap's bind destinations must already exist.  Do not inherit an
        # arbitrary directory tree simply to make the worktree path available.
        created_dirs = {
            Path("/"),
            Path("/usr"),
            Path("/dev"),
            Path("/proc"),
            Path("/tmp"),
            Path("/var"),
            Path("/var/tmp"),
            Path("/home"),
        }

        def add_destination(path: Path) -> None:
            current = Path("/")
            for part in path.parts[1:]:
                current /= part
                if current not in created_dirs:
                    args.extend(["--dir", str(current)])
                    created_dirs.add(current)

        # Make's trusted test virtualenv comes from the server process, not the
        # candidate checkout.  It is mounted read-only in the snapshot.  Its
        # Python base installation is also mapped at the path recorded by the
        # virtualenv, without exposing the rest of the operator's home.
        runtime_binds: list[str] = []
        runtime_prefix = Path(sys.prefix).resolve()
        runtime_python = runtime_prefix / "bin" / "python"
        if runtime_python.exists():
            add_destination(repo / ".venv")
            base_prefix = Path(sys.base_prefix).resolve()
            python_destination = base_prefix
            try:
                link_target = os.readlink(runtime_python)
            except OSError:
                link_target = ""
            if link_target.startswith("/"):
                python_destination = Path(link_target).parent.parent
            add_destination(python_destination)
            runtime_checkout = runtime_prefix.parent
            if runtime_prefix != base_prefix and runtime_checkout != repo:
                # Editable console launchers retain the trusted environment's
                # absolute shebang and source path.  Map those paths to the
                # candidate snapshot and the same read-only runtime, never to
                # the operator checkout, so packaging/CLI tests exercise this
                # exact head without mutating the trusted virtualenv.
                add_destination(runtime_checkout)
                add_destination(runtime_prefix)
                runtime_binds.extend(
                    [
                        "--bind",
                        str(repo),
                        str(runtime_checkout),
                        "--ro-bind",
                        str(runtime_prefix),
                        str(runtime_prefix),
                    ]
                )
            runtime_binds.extend(
                [
                    "--ro-bind",
                    str(runtime_prefix),
                    str(repo / ".venv"),
                    "--ro-bind",
                    str(base_prefix),
                    str(python_destination),
                ]
            )
            # Overlay writable sentinel files over the read-only venv mount so
            # Make skips uv-based setup steps inside the gate.  Git archive
            # stamps every file in the snapshot with the commit timestamp,
            # which can be newer than the sentinel files in the ro-mounted
            # venv; Make then tries to rebuild them by running uv, which is
            # unavailable in the sandbox PATH.  Creating fresh sentinels in
            # run_root and binding them over the venv paths ensures Make sees
            # setup as current without any uv invocation or write access.
            for _sentinel_name in (".uv-setup", ".uv-test-setup"):
                _writable_sentinel = run_root / _sentinel_name
                _writable_sentinel.touch()
                runtime_binds.extend(
                    [
                        "--bind",
                        str(_writable_sentinel),
                        str(repo / ".venv" / _sentinel_name),
                    ]
                )
            # Also bind the operator venv at its original absolute path so
            # that entry-point scripts (e.g. the ``oompah`` console-script)
            # whose shebangs reference that absolute path can execute inside
            # the sandbox.  Without this, the shebang
            # ``#!/path/to/operator/.venv/bin/python3`` resolves to a path
            # that is not visible in the sandbox, causing subprocess calls to
            # the binary entry point to fail with ENOENT.  The venv is still
            # mounted read-only; no operator state is writable.
            if runtime_prefix != (repo / ".venv").resolve():
                add_destination(runtime_prefix)
                runtime_binds.extend(
                    [
                        "--ro-bind",
                        str(runtime_prefix),
                        str(runtime_prefix),
                    ]
                )

        add_destination(repo)
        add_destination(_SANDBOX_RUN_ROOT)
        args.extend(
            [
                "--bind",
                str(repo),
                str(repo),
                "--bind",
                str(run_root),
                str(_SANDBOX_RUN_ROOT),
                *runtime_binds,
                "--chdir",
                str(repo),
                # bwrap leaves loopback in its default state in the new network
                # namespace.  Attempt to bring it up explicitly for
                # compatibility with older kernels; on kernel 6.x the
                # interface carries netns-immutable and is already UP, so
                # ip link set returns EPERM — ignore the error and proceed.
                "/bin/sh",
                "-c",
                'ip link set lo up 2>/dev/null || true; exec "$@"',
                "oompah-gate-bootstrap",
                "/bin/sh",
                "-c",
                command,
            ]
        )
        return args

    @staticmethod
    def _evidence_key(
        *,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
        head_sha: str,
        command: str,
    ) -> str:
        payload = "\0".join(
            (
                str(_EVIDENCE_VERSION),
                repo_identity,
                target_branch,
                work_branch,
                head_sha,
                command,
            )
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load(self) -> dict[str, dict]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        entries = raw.get("results", {}) if isinstance(raw, dict) else {}
        if not entries and isinstance(raw, dict):
            entries = raw.get("passed", {})
        return entries if isinstance(entries, dict) else {}

    def _save(self, entries: dict[str, dict]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"version": _EVIDENCE_VERSION, "results": entries},
            indent=2,
            sort_keys=True,
        ) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.state_path.name}.",
            dir=self.state_path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.state_path)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass

    def _store_result(
        self,
        entries: dict[str, dict],
        key: str,
        result: QualityGateResult,
        *,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
    ) -> None:
        with self._lock:
            # Reload while holding the state lock: gates for different heads
            # are intentionally allowed to overlap, so retaining a caller's
            # pre-execution dictionary could otherwise drop another result.
            entries = self._load()
            entries[key] = {
                **asdict(result),
                "recorded_at": time.time(),
                "repo_identity": repo_identity,
                "target_branch": target_branch,
                "work_branch": work_branch,
            }
            # Old outcomes are only an optimization and can be discarded
            # safely, but active subprocesses never rely on this evidence file.
            if len(entries) > 500:
                newest = sorted(
                    entries.items(),
                    key=lambda item: float(item[1].get("recorded_at", 0) or 0),
                    reverse=True,
                )[:500]
                entries.clear()
                entries.update(newest)
            try:
                self._save(entries)
            except OSError as exc:
                logger.warning("Failed to persist branch quality evidence: %s", exc)

    @contextmanager
    def _key_lock(self, key: str):
        """Yield a single-flight lock and discard it once its last user leaves."""
        with self._lock:
            entry = self._key_locks.get(key)
            if entry is None:
                entry = _KeyLockEntry(lock=threading.Lock())
                self._key_locks[key] = entry
            entry.users += 1
        entry.lock.acquire()
        try:
            yield
        finally:
            entry.lock.release()
            with self._lock:
                entry.users -= 1
                if (
                    entry.users == 0
                    and self._key_locks.get(key) is entry
                ):
                    self._key_locks.pop(key, None)

    def run(
        self,
        *,
        repo_path: str,
        repo_identity: str,
        target_branch: str,
        work_branch: str,
        command: str,
        retry_forced: bool = False,
        expected_head_sha: str | None = None,
        generation: str | None = None,
        is_current: Callable[[], bool] | None = None,
    ) -> QualityGateResult:
        """Return passing evidence or execute the configured full check.

        When retry_forced=True, bypasses cache for failed/timed_out/error
        results and re-executes. Passed results remain cached and reusable.

        Pre-spawn barriers
        ------------------
        Two deterministic checkpoints prevent stale gate spawns:

        1. Before snapshot creation: checks tombstone + is_current.
        2. After snapshot creation, before Popen: checks tombstone + is_current.

        A third barrier closes the Popen-to-registration window: after
        registering the process, the code re-checks the tombstone under the
        same lock and immediately kills+marks-interrupted any process that
        was cancelled between Popen and registration.
        """
        command = str(command or "").strip()
        if not command:
            return QualityGateResult(
                status="not_configured",
                head_sha=self._head_sha(repo_path),
                command="",
            )

        owned_generation = str(generation) if generation is not None else None
        # Register before resolving the head or waiting on the evidence key.
        # A cancellation that arrives while a second caller waits on that key
        # must remain authoritative until that waiter has observed it.
        if owned_generation is not None:
            self._register_generation(owned_generation)

        # Serialize only identical evidence keys. Different exact heads must
        # be able to run concurrently so a replacement generation never waits
        # behind (or shares state with) an obsolete gate.
        try:
            observed_head = self._head_sha(repo_path)
            head_sha = (
                self._resolve_commit(repo_path, expected_head_sha)
                if expected_head_sha
                else observed_head
            )
            if expected_head_sha and observed_head != head_sha:
                if owned_generation is not None:
                    self._release_generation(owned_generation)
                return QualityGateResult(
                    status="stale_head",
                    head_sha=observed_head,
                    command=command,
                    output_tail=(
                        f"Expected task head {head_sha}, but worktree is "
                        f"at {observed_head}."
                    ),
                )
        except (OSError, subprocess.SubprocessError) as exc:
            if owned_generation is not None:
                self._release_generation(owned_generation)
            return QualityGateResult(
                status="error",
                head_sha="",
                command=command,
                output_tail=f"Could not resolve branch HEAD: {exc}",
            )

        # Fail closed before candidate code starts when the required lifecycle
        # isolation contract is absent, while retaining main's exact-head and
        # generation-aware launch sequencing.
        is_compliant, reason = self._verify_isolation_contract(repo_path)
        if not is_compliant:
            if owned_generation is not None:
                self._release_generation(owned_generation)
            return QualityGateResult(
                status="needs_rebase",
                head_sha=head_sha,
                command=command,
                output_tail=reason,
            )

        key = self._evidence_key(
            repo_identity=repo_identity,
            target_branch=target_branch,
            work_branch=work_branch,
            head_sha=head_sha,
            command=command,
        )
        with self._key_lock(key):
            try:
                with self._lock:
                    entries = self._load()
            except OSError:
                entries = {}
            cached = entries.get(key)
            if isinstance(cached, dict) and cached.get("status"):
                cached_status = str(cached["status"])
                # On forced retry, skip cache for failed/timed_out/error.
                # Reuse passed results regardless of retry_forced flag.
                if retry_forced and cached_status in {"failed", "timed_out", "error"}:
                    # Fall through to re-execute instead of returning cached result
                    pass
                else:
                    if owned_generation is not None:
                        self._release_generation(owned_generation)
                    return QualityGateResult(
                        status=cached_status,
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=float(cached.get("duration_seconds", 0) or 0),
                        output_tail=str(cached.get("output_tail", "") or ""),
                        cached=True,
                    )

            started = time.monotonic()
            process: subprocess.Popen[str] | None = None
            run_root = self._gate_run_root()
            snapshot: Path | None = None
            monitor_stop = threading.Event()
            monitor: threading.Thread | None = None
            try:
                # --- Barrier 1: before snapshot creation ---
                # Check authority before creating the immutable archive.
                # cancel_generation() may have been called while we were
                # waiting in the key lock or the evidence load above.
                if owned_generation is not None and self._generation_is_cancelled(
                    owned_generation
                ):
                    return QualityGateResult(
                        status="interrupted",
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=time.monotonic() - started,
                        output_tail="Gate cancelled before snapshot creation.",
                    )
                if is_current is not None:
                    try:
                        authority_ok = bool(is_current())
                    except Exception as exc:  # noqa: BLE001
                        authority_ok = False
                        logger.warning(
                            "Quality gate pre-spawn authority check failed: %s", exc
                        )
                    if not authority_ok:
                        return QualityGateResult(
                            status="interrupted",
                            head_sha=head_sha,
                            command=command,
                            duration_seconds=time.monotonic() - started,
                            output_tail="Gate authority withdrawn before snapshot creation.",
                        )

                try:
                    snapshot = self._snapshot_candidate_worktree(
                        repo_path, run_root, head_sha
                    )
                except _SandboxUnavailable as exc:
                    return QualityGateResult(
                        status="needs_rebase",
                        head_sha=head_sha,
                        command=command,
                        output_tail=(
                            "OS-enforced quality-gate sandbox is unavailable; "
                            f"refusing to execute candidate code: {exc}"
                        ),
                    )

                # --- Barrier 2: after snapshot, before Popen ---
                # cancel_generation() may have arrived during the up-to-60s
                # archive creation above.  Check again before spawning.
                if owned_generation is not None and self._generation_is_cancelled(
                    owned_generation
                ):
                    return QualityGateResult(
                        status="interrupted",
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=time.monotonic() - started,
                        output_tail="Gate cancelled after snapshot creation, before spawn.",
                    )
                if is_current is not None:
                    try:
                        authority_ok = bool(is_current())
                    except Exception as exc:  # noqa: BLE001
                        authority_ok = False
                        logger.warning(
                            "Quality gate pre-spawn authority check failed: %s", exc
                        )
                    if not authority_ok:
                        return QualityGateResult(
                            status="interrupted",
                            head_sha=head_sha,
                            command=command,
                            duration_seconds=time.monotonic() - started,
                            output_tail="Gate authority withdrawn after snapshot, before spawn.",
                        )

                try:
                    sandboxed_command = self._sandbox_launcher(
                        command,
                        str(snapshot),
                        run_root,
                    )
                except _SandboxUnavailable as exc:
                    return QualityGateResult(
                        status="needs_rebase",
                        head_sha=head_sha,
                        command=command,
                        output_tail=(
                            "OS-enforced quality-gate sandbox is unavailable; "
                            f"refusing to execute candidate code: {exc}"
                        ),
                    )
                process = subprocess.Popen(  # noqa: S602 - operator-owned command
                    sandboxed_command,
                    cwd=str(snapshot),
                    env=self._quality_gate_environment(run_root),
                    shell=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                )
                # Track process group for graceful shutdown cleanup.
                # --- Barrier 3: Popen-to-registration window ---
                # Re-check the tombstone under the lock immediately after
                # registration so that cancel_generation() calls that arrived
                # between Popen and here are caught and the just-spawned
                # process is killed before the monitor thread starts.
                with self._processes_lock:
                    if owned_generation is None:
                        owned_generation = f"pid:{process.pid}"
                    self._active_processes[process.pid] = process
                    self._active_generations[process.pid] = owned_generation
                    self._active_snapshots[process.pid] = snapshot
                    # Check tombstone under the same lock that cancel_generation
                    # uses to add to _cancelled_generations and mark _interrupted.
                    post_spawn_cancelled = (
                        owned_generation in self._cancelled_generations
                    )
                    if post_spawn_cancelled:
                        setattr(process, "_oompah_interrupted", True)

                if post_spawn_cancelled:
                    # Kill the just-spawned process; the normal flow will
                    # see _oompah_interrupted=True and return interrupted.
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except (ProcessLookupError, OSError):
                        pass

                if is_current is not None:
                    def _monitor_gate_authority() -> None:
                        while not monitor_stop.wait(0.1):
                            try:
                                current = bool(is_current())
                            except Exception as exc:  # noqa: BLE001
                                logger.warning(
                                    "Quality gate authority check failed: %s",
                                    exc,
                                )
                                current = False
                            if not current:
                                self.cancel_generation(owned_generation)
                                return

                    monitor = threading.Thread(
                        target=_monitor_gate_authority,
                        name=f"quality-gate-watch-{process.pid}",
                        daemon=True,
                    )
                    monitor.start()
                stdout, stderr = process.communicate(timeout=self.timeout_seconds)
                duration = time.monotonic() - started
                combined = "\n".join(
                    part for part in (stdout, stderr) if part
                )
                output_tail = combined.encode("utf-8", errors="replace")[
                    -self.output_tail_bytes :
                ].decode("utf-8", errors="replace")
                with self._processes_lock:
                    interrupted = bool(
                        getattr(process, "_oompah_interrupted", False)
                    )
                    self._active_processes.pop(process.pid, None)
                if interrupted:
                    return QualityGateResult(
                        status="interrupted",
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=duration,
                        output_tail=output_tail,
                    )
                if process.returncode != 0:
                    result = QualityGateResult(
                        status="failed",
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=duration,
                        output_tail=output_tail,
                    )
                    self._store_result(
                        entries,
                        key,
                        result,
                        repo_identity=repo_identity,
                        target_branch=target_branch,
                        work_branch=work_branch,
                    )
                    return result
            except subprocess.TimeoutExpired as exc:
                assert process is not None
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass
                stdout, stderr = process.communicate()
                duration = time.monotonic() - started
                combined = "\n".join(
                    str(part or "")
                    for part in (
                        stdout or exc.stdout,
                        stderr or exc.stderr,
                    )
                    if part
                )
                with self._processes_lock:
                    interrupted = bool(
                        getattr(process, "_oompah_interrupted", False)
                    )
                    self._active_processes.pop(process.pid, None)
                if interrupted:
                    return QualityGateResult(
                        status="interrupted",
                        head_sha=head_sha,
                        command=command,
                        duration_seconds=duration,
                        output_tail=combined[-self.output_tail_bytes :],
                    )
                result = QualityGateResult(
                    status="timed_out",
                    head_sha=head_sha,
                    command=command,
                    duration_seconds=duration,
                    output_tail=combined[-self.output_tail_bytes :],
                )
                self._store_result(
                    entries,
                    key,
                    result,
                    repo_identity=repo_identity,
                    target_branch=target_branch,
                    work_branch=work_branch,
                )
                return result
            except OSError as exc:
                result = QualityGateResult(
                    status="error",
                    head_sha=head_sha,
                    command=command,
                    duration_seconds=time.monotonic() - started,
                    output_tail=str(exc),
                )
                self._store_result(
                    entries,
                    key,
                    result,
                    repo_identity=repo_identity,
                    target_branch=target_branch,
                    work_branch=work_branch,
                )
                return result
            finally:
                monitor_stop.set()
                if monitor is not None and monitor is not threading.current_thread():
                    monitor.join(timeout=1)
                if process is not None:
                    with self._processes_lock:
                        self._active_processes.pop(process.pid, None)
                        self._active_generations.pop(process.pid, None)
                        self._active_snapshots.pop(process.pid, None)
                # A cancelled generation remains fenced until every caller
                # already registered for it has crossed the barrier.  This
                # prevents one interrupted caller from clearing the tombstone
                # while another is still waiting on this evidence-key lock.
                if owned_generation is not None:
                    self._release_generation(owned_generation)
                self._cleanup_gate_run_root(run_root)

            result = QualityGateResult(
                status="passed",
                head_sha=head_sha,
                command=command,
                duration_seconds=duration,
                output_tail=output_tail,
            )
            self._store_result(
                entries,
                key,
                result,
                repo_identity=repo_identity,
                target_branch=target_branch,
                work_branch=work_branch,
            )
            return result
