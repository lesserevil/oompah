#!/usr/bin/env python3
"""Run dedicated-runner pytest behind Oompah's durable host lease."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from oompah.validation_resource_lease import (
    ValidationLeaseCancelled,
    ValidationLeaseError,
    ValidationLeaseOwner,
    ValidationResourceLease,
)


logger = logging.getLogger("oompah.ci_dedicated")
_POLL_SECONDS = 0.1
_TERMINATE_GRACE_SECONDS = 10.0
_MAX_CONSOLE_BYTES = 32 * 1024
_PR_SET_PDEATHSIG = 1


@dataclass(frozen=True)
class TestIdentity:
    """Numeric identity used by the hermetic test subprocess."""

    uid: int
    gid: int

    @classmethod
    def parse(cls, value: str) -> "TestIdentity":
        try:
            raw_uid, raw_gid = value.split(":", 1)
            identity = cls(uid=int(raw_uid), gid=int(raw_gid))
        except (TypeError, ValueError) as exc:
            raise argparse.ArgumentTypeError("identity must be numeric UID:GID") from exc
        if identity.uid <= 0 or identity.gid < 0:
            raise argparse.ArgumentTypeError("test UID must be non-root")
        return identity


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lease-db", required=True, type=Path)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--run-as", required=True, type=TestIdentity.parse)
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    parser.add_argument("--lease-wait-timeout-seconds", type=float, default=7200.0)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    return parser


def _stable_owner(arguments: argparse.Namespace) -> ValidationLeaseOwner:
    fields = {
        "project_id": arguments.project_id,
        "run_id": arguments.run_id,
        "run_attempt": arguments.run_attempt,
        "job_id": arguments.job_id,
    }
    if any(not str(value).strip() for value in fields.values()):
        raise ValueError("project, run, attempt, and job identities must be non-empty")
    return ValidationLeaseOwner.exact_gate(
        project_id=str(arguments.project_id).strip(),
        task_id=f"github-actions:{str(arguments.job_id).strip()}",
        authority_generation=(
            f"{str(arguments.run_id).strip()}:{str(arguments.run_attempt).strip()}"
        ),
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _artifact_tail(path: Path, *, limit: int = _MAX_CONSOLE_BYTES) -> str:
    """Return a byte-bounded UTF-8 tail without loading an unbounded log."""

    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(size - limit, 0))
            payload = stream.read(limit)
    except OSError as exc:
        return f"unable to read diagnostic log: {exc}"
    return payload.decode("utf-8", errors="replace")


def _pytest_command(artifact_dir: Path, pytest_args: Sequence[str]) -> list[str]:
    arguments = list(pytest_args) or ["tests/"]
    for argument in arguments:
        if argument == "--junitxml" or argument.startswith("--junitxml="):
            raise ValueError("the broker owns the durable JUnit output path")
        if argument == "--junit-xml" or argument.startswith("--junit-xml="):
            raise ValueError("the broker owns the durable JUnit output path")
    return [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=long",
        f"--junitxml={artifact_dir / 'test-results.xml'}",
        f"--basetemp={artifact_dir / 'pytest-temp'}",
        "-o",
        f"cache_dir={artifact_dir / 'pytest-cache'}",
        *arguments,
    ]


def _prepare_artifacts(
    path: Path,
    identity: TestIdentity,
    *,
    repository: Path,
) -> dict[str, str]:
    path.mkdir(mode=0o750, parents=True, exist_ok=True)
    child_paths = {
        "HOME": path / "home",
        "TMPDIR": path / "tmp",
        "XDG_CACHE_HOME": path / "xdg-cache",
        "XDG_CONFIG_HOME": path / "xdg-config",
        "XDG_DATA_HOME": path / "xdg-data",
        "PYTHONPYCACHEPREFIX": path / "pycache",
    }
    for child in child_paths.values():
        child.mkdir(mode=0o700, parents=True, exist_ok=True)
    git_config = child_paths["HOME"] / ".gitconfig"
    git_config.write_text(
        "[user]\n"
        "\tname = oompah-ci\n"
        "\temail = lesserevil@users.noreply.github.com\n"
        "[safe]\n"
        f"\tdirectory = {repository}\n",
        encoding="utf-8",
    )
    git_config.chmod(0o600)
    if os.geteuid() == 0:
        os.chown(path, identity.uid, identity.gid)
        for child in child_paths.values():
            os.chown(child, identity.uid, identity.gid)
        os.chown(git_config, identity.uid, identity.gid)
    return {name: str(child) for name, child in child_paths.items()}


def _child_setup(identity: TestIdentity, expected_parent_pid: int) -> None:
    """Fence parent death and discard the runner's privileged identity."""

    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(_PR_SET_PDEATHSIG, signal.SIGKILL) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    if os.getppid() != expected_parent_pid:
        os.kill(os.getpid(), signal.SIGKILL)
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(identity.gid)
        os.setuid(identity.uid)
    elif os.geteuid() != identity.uid or os.getegid() != identity.gid:
        raise PermissionError("broker cannot assume the requested test identity")
    os.umask(0o077)


def _signal_group(process: subprocess.Popen[bytes], signum: int) -> None:
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass


def _group_alive(group_id: int) -> bool:
    try:
        os.killpg(group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_group(process: subprocess.Popen[bytes]) -> bool:
    _signal_group(process, signal.SIGTERM)
    deadline = time.monotonic() + _TERMINATE_GRACE_SECONDS
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=_TERMINATE_GRACE_SECONDS)
    while _group_alive(process.pid) and time.monotonic() < deadline:
        time.sleep(_POLL_SECONDS)
    if _group_alive(process.pid):
        _signal_group(process, signal.SIGKILL)
        deadline = time.monotonic() + _TERMINATE_GRACE_SECONDS
        while _group_alive(process.pid) and time.monotonic() < deadline:
            time.sleep(_POLL_SECONDS)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=1)
    return not _group_alive(process.pid)


def _wait_for_process(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
    interrupted: list[int | None],
) -> tuple[int, str, bool]:
    deadline = time.monotonic() + max(timeout_seconds, 1.0)
    while process.poll() is None:
        if interrupted[0] is not None:
            group_dead = _terminate_group(process)
            return 128 + int(interrupted[0]), "cancelled", group_dead
        if time.monotonic() >= deadline:
            group_dead = _terminate_group(process)
            return 124, "timed_out", group_dead
        time.sleep(_POLL_SECONDS)
    # A normal pytest parent should reap its workers. Refuse to unlock the
    # inherited lease fence if an unexpected descendant remains alive.
    group_dead = not _group_alive(process.pid)
    if not group_dead:
        group_dead = _terminate_group(process)
    if interrupted[0] is not None:
        return 128 + int(interrupted[0]), "cancelled", group_dead
    return int(process.returncode or 0), "completed", group_dead


def run(arguments: argparse.Namespace) -> int:
    owner = _stable_owner(arguments)
    if arguments.timeout_seconds <= 0 or arguments.lease_wait_timeout_seconds <= 0:
        raise ValueError("timeouts must be positive")
    if os.geteuid() != 0 and (
        arguments.run_as.uid != os.geteuid()
        or arguments.run_as.gid != os.getegid()
    ):
        raise PermissionError("only root can select a different test identity")
    if os.geteuid() == 0 and arguments.run_as.uid == 0:
        raise PermissionError("dedicated tests must not run as root")

    artifact_dir = arguments.artifact_dir.expanduser().resolve()
    repository = Path.cwd().resolve()
    child_environment = _prepare_artifacts(
        artifact_dir,
        arguments.run_as,
        repository=repository,
    )
    full_log = artifact_dir / "pytest-full.log"
    metadata_path = artifact_dir / "broker-result.json"
    command = _pytest_command(artifact_dir, arguments.pytest_args)
    metadata: dict[str, object] = {
        "authority_generation": owner.authority_generation,
        "job_id": arguments.job_id,
        "project_id": owner.project_id,
        "run_as_gid": arguments.run_as.gid,
        "run_as_uid": arguments.run_as.uid,
        "run_id": arguments.run_id,
        "status": "waiting_for_capacity",
        "task_id": owner.task_id,
    }
    _write_json(metadata_path, metadata)

    interrupted: list[int | None] = [None]
    process: subprocess.Popen[bytes] | None = None

    def on_signal(signum: int, _frame: object) -> None:
        interrupted[0] = signum
        if process is not None:
            _signal_group(process, signal.SIGTERM)

    previous_handlers = {
        signum: signal.signal(signum, on_signal)
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    }
    lease = ValidationResourceLease(arguments.lease_db.expanduser().resolve())
    handle = None
    release_safely = True
    try:
        try:
            handle = lease.acquire(
                owner,
                is_cancelled=lambda: interrupted[0] is not None,
                wait_timeout_seconds=arguments.lease_wait_timeout_seconds,
            )
        except ValidationLeaseCancelled as exc:
            status = "cancelled" if interrupted[0] is not None else "lease_wait_timeout"
            metadata.update({"status": status, "error": str(exc)})
            _write_json(metadata_path, metadata)
            return 128 + int(interrupted[0]) if interrupted[0] is not None else 124

        metadata.update({"status": "running", "lease_slot": handle.slot})
        _write_json(metadata_path, metadata)
        environment = os.environ.copy()
        environment.update(child_environment)
        environment.update(
            {
                "LOGNAME": "oompah-ci",
                "USER": "oompah-ci",
                "GIT_CONFIG_GLOBAL": str(Path(child_environment["HOME"]) / ".gitconfig"),
                "GIT_CONFIG_NOSYSTEM": "1",
                "OOMPAH_PYTEST_GATE": "1",
                "OOMPAH_PYTEST_RUN_ROOT": str(artifact_dir / "pytest-temp"),
            }
        )
        parent_pid = os.getpid()
        with full_log.open("wb") as output:
            process = subprocess.Popen(
                command,
                cwd=repository,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                pass_fds=handle.pass_fds,
                start_new_session=True,
                preexec_fn=lambda: _child_setup(arguments.run_as, parent_pid),
            )
            try:
                handle.attach_process(process, timeout_seconds=arguments.timeout_seconds)
            except (ValidationLeaseCancelled, ValidationLeaseError):
                if process.poll() is None:
                    release_safely = _terminate_group(process)
                    raise
            exit_code, status, release_safely = _wait_for_process(
                process,
                timeout_seconds=arguments.timeout_seconds,
                interrupted=interrupted,
            )

        metadata.update(
            {
                "exit_code": exit_code,
                "finished_at": time.time(),
                "full_log": full_log.name,
                "junit_xml": "test-results.xml",
                "status": status,
            }
        )
        _write_json(metadata_path, metadata)
        tail = _artifact_tail(full_log)
        if tail:
            print("--- bounded pytest diagnostic tail ---")
            print(tail, end="" if tail.endswith("\n") else "\n")
            print("--- full diagnostics are in the uploaded ci-dedicated artifact ---")
        return exit_code
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        if handle is not None and release_safely:
            handle.release()
        elif handle is not None:
            logger.error(
                "Validation descendants survived termination; retaining the kernel fence "
                "until this broker and every inheriting descendant exit"
            )


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        return run(_parser().parse_args(argv))
    except (OSError, ValueError, ValidationLeaseError) as exc:
        logger.error("Dedicated CI broker failed: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
