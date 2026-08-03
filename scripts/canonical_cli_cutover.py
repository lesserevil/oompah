#!/usr/bin/env python3
"""Coordinate a safe canonical-CLI and service restart cutover.

The old service is quiesced and drained before a candidate is staged.  Staging
uses an isolated UV tool root; activation is the only operation that changes
the canonical launcher.  Failures before a restart attempt restore and resume
the old pair.  After a restart attempt, bounded build/instance probes either
prove the candidate pair, prove that the untouched old service can be paired
with the rollback launcher, or stop the exact lifecycle-owned service before
returning an uncertain result.  The helper never knowingly leaves a live
server paired with a launcher for another revision.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


logger = logging.getLogger(__name__)

try:  # Works both as ``python -m`` and as a Makefile script path.
    from scripts.sync_canonical_cli import (
        DEFAULT_SOURCE_URL,
        Activation,
        StagedCLI,
        SyncError,
        activate_candidate,
        serialized_cli_lifecycle,
        stage_candidate,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised by script startup
    from sync_canonical_cli import (  # type: ignore[no-redef]
        DEFAULT_SOURCE_URL,
        Activation,
        StagedCLI,
        SyncError,
        activate_candidate,
        serialized_cli_lifecycle,
        stage_candidate,
    )

try:
    from scripts.process_identity import identity_matches, read_identity
except ModuleNotFoundError:  # pragma: no cover - exercised by script startup
    from process_identity import identity_matches, read_identity  # type: ignore[no-redef]


class CutoverError(RuntimeError):
    """Raised when a service/CLI cutover cannot safely complete."""


class CutoverUncertainError(CutoverError):
    """The restart may have crossed its exec boundary; keep the candidate CLI."""


Request = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]
Quarantine = Callable[[str], None]


@dataclass(frozen=True)
class OwnedService:
    """A lifecycle process identity captured before a risky cutover."""

    pid: int
    expected: dict[str, Any]
    workspace: Path
    pid_file: Path
    pid_meta_file: Path


@dataclass(frozen=True)
class ServiceObservation:
    """One best-effort view of the server after a restart attempt."""

    health: dict[str, Any]
    state: dict[str, Any]
    errors: tuple[str, ...]

    @property
    def health_instance(self) -> str | None:
        value = self.health.get("instance_id")
        return value if isinstance(value, str) and value else None

    @property
    def state_instance(self) -> str | None:
        value = self.state.get("service_instance_id")
        return value if isinstance(value, str) and value else None

    @property
    def health_revision(self) -> str | None:
        return _revision_from_identity(self.health)

    @property
    def state_revision(self) -> str | None:
        return _revision_from_identity(self.state)

    @property
    def restart_in_progress(self) -> bool | None:
        restart = self.state.get("restart")
        if not isinstance(restart, dict):
            return None
        value = restart.get("in_progress")
        return value if isinstance(value, bool) else None


def _http_request(
    *,
    repo: Path,
    python: str,
    url: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Call the existing credential-safe HTTP helper and parse its JSON."""
    command = [python, "scripts/oompah_http.py", method, path]
    if body is not None:
        command.append(json.dumps(body, separators=(",", ":")))
    env = {**os.environ, "OOMPAH_SERVER_URL": url}
    result = subprocess.run(
        command,
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise CutoverError(
            f"{method} {path} failed; the running service was not cut over: "
            f"{detail or 'unknown HTTP error'}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CutoverError(
            f"{method} {path} returned invalid JSON; service cutover was not completed"
        ) from exc
    if not isinstance(payload, dict):
        raise CutoverError(f"{method} {path} returned a non-object JSON response")
    return payload


def _revision_from_identity(payload: dict[str, Any]) -> str | None:
    build_id = payload.get("build_id")
    if not isinstance(build_id, dict):
        return None
    revision = build_id.get("revision")
    return revision.lower() if isinstance(revision, str) else None


def _running_count(state: dict[str, Any]) -> int | None:
    counts = state.get("counts")
    if not isinstance(counts, dict):
        return None
    value = counts.get("running")
    return value if isinstance(value, int) else None


def _capture_owned_service(
    *,
    repo: Path,
    pid_file: Path,
    pid_meta_file: Path,
) -> OwnedService:
    """Capture and verify the exact service process before activation."""
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        expected = json.loads(pid_meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise CutoverError(
            "cannot capture the running service identity from the lifecycle "
            "PID files; refusing a cutover that could not be quarantined"
        ) from exc
    if not isinstance(expected, dict) or not identity_matches(
        expected,
        pid=pid,
        workspace=str(repo),
    ):
        raise CutoverError(
            "running service PID does not match its stored lifecycle identity; "
            "refusing to activate a new canonical CLI"
        )
    return OwnedService(
        pid=pid,
        expected=dict(expected),
        workspace=repo,
        pid_file=pid_file,
        pid_meta_file=pid_meta_file,
    )


def _quarantine_owned_service(
    service: OwnedService,
    *,
    timeout: float,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Stop only the process that still matches the captured identity."""
    actual = read_identity(service.pid)
    if actual is None:
        service.pid_file.unlink(missing_ok=True)
        service.pid_meta_file.unlink(missing_ok=True)
        return
    if not identity_matches(
        service.expected,
        pid=service.pid,
        workspace=str(service.workspace),
    ):
        raise CutoverError(
            "refusing quarantine because the lifecycle PID identity changed"
        )

    process_group = int(service.expected.get("process_group", -1))
    session = int(service.expected.get("session", -1))
    if process_group == service.pid and session == service.pid:
        os.killpg(service.pid, signal.SIGTERM)
    else:
        os.kill(service.pid, signal.SIGTERM)

    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        try:
            reaped_pid, _ = os.waitpid(service.pid, os.WNOHANG)
        except ChildProcessError:
            reaped_pid = 0
        if reaped_pid == service.pid:
            service.pid_file.unlink(missing_ok=True)
            service.pid_meta_file.unlink(missing_ok=True)
            return
        actual = read_identity(service.pid)
        if actual is None:
            service.pid_file.unlink(missing_ok=True)
            service.pid_meta_file.unlink(missing_ok=True)
            return
        if not identity_matches(
            service.expected,
            pid=service.pid,
            workspace=str(service.workspace),
        ):
            # The captured process is gone and its PID was reused.  The
            # quarantine objective is complete; importantly, do not signal
            # the replacement process.
            service.pid_file.unlink(missing_ok=True)
            service.pid_meta_file.unlink(missing_ok=True)
            return
        if time.monotonic() >= deadline:
            raise CutoverError(
                f"owned service PID {service.pid} did not stop within {timeout:g}s"
            )
        sleep(min(0.1, max(deadline - time.monotonic(), 0.01)))


def _wait_for_state(
    request: Request,
    predicate: Callable[[dict[str, Any]], bool],
    *,
    timeout: float,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = request("GET", "/api/v1/state", None)
        if predicate(last):
            return last
        sleep(min(1.0, max(deadline - time.monotonic(), 0.01)))
    raise CutoverError(
        "service did not reach the required lifecycle state before the timeout; "
        f"last state={json.dumps(last, sort_keys=True)[:500]}"
    )


def _observe_service(request: Request) -> ServiceObservation:
    health: dict[str, Any] = {}
    state: dict[str, Any] = {}
    errors: list[str] = []
    try:
        health = request("GET", "/healthz", None)
    except Exception as exc:  # noqa: BLE001 - observations are best effort
        errors.append(f"health={str(exc) or exc.__class__.__name__}")
    try:
        state = request("GET", "/api/v1/state", None)
    except Exception as exc:  # noqa: BLE001 - observations are best effort
        errors.append(f"state={str(exc) or exc.__class__.__name__}")
    return ServiceObservation(health=health, state=state, errors=tuple(errors))


def _is_candidate_pair(
    observation: ServiceObservation,
    *,
    old_instance: str | None,
    revision: str,
) -> bool:
    instance = observation.health_instance
    state_instance = observation.state_instance
    return bool(
        observation.health.get("status") == "ok"
        and instance
        and instance != old_instance
        and observation.health_revision == revision.lower()
        and observation.state_revision == revision.lower()
        and state_instance == instance
    )


def _is_verified_old_pair(
    observation: ServiceObservation,
    *,
    old_instance: str | None,
    old_revision: str,
) -> bool:
    return bool(
        old_instance
        and observation.health.get("status") == "ok"
        and observation.health_instance == old_instance
        and observation.health_revision == old_revision.lower()
        and observation.state_revision == old_revision.lower()
        and observation.state_instance == old_instance
        # The synchronous restart endpoint sets this before returning.  Only
        # an explicit false proves that a dropped request did not schedule an
        # exec which could occur after a one-sided launcher rollback.
        and observation.restart_in_progress is False
    )


def _is_definitive_wrong_build(
    observation: ServiceObservation,
    *,
    old_instance: str | None,
    revision: str,
) -> bool:
    instance = observation.health_instance
    return bool(
        observation.health.get("status") == "ok"
        and instance
        and instance != old_instance
        and observation.health_revision
        and observation.health_revision != revision.lower()
    )


def _wait_for_cutover_resolution(
    request: Request,
    old_instance: str | None,
    old_revision: str,
    revision: str,
    *,
    timeout: float,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[str, ServiceObservation]:
    """Classify the post-request service as candidate, old, or uncertain."""
    deadline = time.monotonic() + timeout
    last = ServiceObservation({}, {}, ())
    while True:
        last = _observe_service(request)
        if _is_candidate_pair(last, old_instance=old_instance, revision=revision):
            return "candidate", last
        if _is_definitive_wrong_build(
            last,
            old_instance=old_instance,
            revision=revision,
        ):
            return "uncertain", last
        if time.monotonic() >= deadline:
            break
        sleep(min(1.0, max(deadline - time.monotonic(), 0.01)))
    if _is_verified_old_pair(
        last,
        old_instance=old_instance,
        old_revision=old_revision,
    ):
        return "old", last
    return "uncertain", last


def _observation_summary(observation: ServiceObservation) -> str:
    return json.dumps(
        {
            "errors": list(observation.errors),
            "health_instance": observation.health_instance,
            "health_revision": observation.health_revision,
            "state_instance": observation.state_instance,
            "state_revision": observation.state_revision,
            "restart_in_progress": observation.restart_in_progress,
        },
        sort_keys=True,
    )


def verify_pair(
    *,
    repo: Path,
    canonical: Path,
    url: str,
    environ: dict[str, str] | None = None,
    operator_path: str | None = None,
    request: Request | None = None,
) -> str:
    """Verify command resolution and equality for an already-running service."""
    env = dict(os.environ if environ is None else environ)
    validation_path = env.get("PATH", "") if operator_path is None else operator_path
    if request is None:
        def request(method, path, body):
            return _http_request(
                repo=repo,
                python=sys.executable,
                url=url,
                method=method,
                path=path,
                body=body,
            )
    health = request("GET", "/healthz", None)
    state = request("GET", "/api/v1/state", None)
    health_revision = _revision_from_identity(health)
    state_revision = _revision_from_identity(state)
    health_instance = health.get("instance_id")
    state_instance = state.get("service_instance_id")
    if not (
        health.get("status") == "ok"
        and isinstance(health_instance, str)
        and health_instance
        and state_instance == health_instance
    ):
        raise CutoverError(
            "health and authenticated state must report the same non-null "
            "service instance"
        )
    resolved = shutil.which("oompah", path=validation_path)
    if resolved is None or os.path.abspath(resolved) != os.path.abspath(canonical):
        raise CutoverError(
            "command -v oompah does not resolve to the canonical launcher "
            f"{canonical} (resolved {resolved or 'not found'})"
        )
    result = subprocess.run(
        [str(canonical), "--version"],
        env={**env, "PATH": validation_path},
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise CutoverError("canonical oompah --version failed")
    match = re.search(r"revision\s+([0-9a-fA-F]{7,64})\b", output)
    cli_revision = match.group(1).lower() if match else None
    if not cli_revision or health_revision != cli_revision or state_revision != cli_revision:
        raise CutoverError(
            "CLI/server build-id mismatch: "
            f"cli={cli_revision or 'unknown'}, health={health_revision or 'unknown'}, "
            f"state={state_revision or 'unknown'}"
        )
    return cli_revision


@serialized_cli_lifecycle(error_type=CutoverError)
def graceful_cutover(
    *,
    repo: Path,
    canonical: Path,
    url: str,
    source_url: str = DEFAULT_SOURCE_URL,
    uv: str = "uv",
    tool_dir: Path | None = None,
    bin_dir: Path | None = None,
    environ: dict[str, str] | None = None,
    operator_path: str | None = None,
    request: Request | None = None,
    stage: Callable[..., StagedCLI] = stage_candidate,
    activate: Callable[..., Activation] = activate_candidate,
    timeout: float = 3600,
    health_timeout: float = 3660,
    force: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    pid_file: Path | None = None,
    pid_meta_file: Path | None = None,
    quarantine: Quarantine | None = None,
    quarantine_timeout: float = 30,
) -> str:
    """Perform a quiesce, drain, stage, restart, and identity transaction."""
    env = dict(os.environ if environ is None else environ)
    validation_path = env.get("PATH", "") if operator_path is None else operator_path
    operator_env = {**env, "PATH": validation_path}
    home = Path(env.get("HOME", str(Path.home())))
    tool_dir = tool_dir or Path(env.get("UV_TOOL_DIR", home / ".local/share/uv/tools"))
    bin_dir = bin_dir or Path(env.get("UV_TOOL_BIN_DIR", canonical.parent))
    resolved = shutil.which("oompah", path=validation_path)
    if resolved is None or os.path.abspath(resolved) != os.path.abspath(canonical):
        raise CutoverError(
            "command -v oompah does not resolve to the canonical launcher "
            f"{canonical} (resolved {resolved or 'not found'})"
        )
    if request is None:
        def request(method, path, body):
            return _http_request(
                repo=repo,
                python=sys.executable,
                url=url,
                method=method,
                path=path,
                body=body,
            )

    old_health = request("GET", "/healthz", None)
    old_state = request("GET", "/api/v1/state", None)
    old_observation = ServiceObservation(old_health, old_state, ())
    old_instance = old_observation.health_instance
    old_health_revision = old_observation.health_revision
    old_state_revision = old_observation.state_revision
    if not (
        old_health.get("status") == "ok"
        and old_instance
        and old_observation.state_instance == old_instance
        and old_health_revision
        and old_state_revision == old_health_revision
    ):
        raise CutoverError(
            "running health and authenticated state do not report the same "
            "non-null service instance and exact revision; refusing to risk "
            "a CLI/server mismatch"
        )
    old_revision = old_health_revision
    current = subprocess.run(
        [str(canonical), "--version"],
        env=operator_env,
        capture_output=True,
        text=True,
        check=False,
    )
    current_cli_revision = None
    if current.returncode == 0:
        match = re.search(r"revision\s+([0-9a-fA-F]{7,64})\b", current.stdout + current.stderr)
        if match:
            current_cli_revision = match.group(1).lower()
    
    # Recovery: detect launcher/service mismatch and repair automatically
    # by installing the launcher from the running service revision
    if current_cli_revision != old_revision.lower():
        if current_cli_revision is None or current.returncode != 0:
            raise CutoverError(
                "canonical CLI is not installed or not executable; repair it with "
                "make install-cli before attempting a restart"
            )
        # Launcher exists but doesn't match running service revision.
        # Recovery: reinstall launcher from running service revision.
        try:
            from scripts.sync_canonical_cli import synchronize as sync_cli
            sync_cli(
                repo=repo,
                canonical=canonical,
                source_url=source_url,
                uv=uv,
                tool_dir=tool_dir,
                bin_dir=bin_dir,
                environ=env,
                operator_path=operator_path,
                running_revision=old_revision,
            )
        except Exception as sync_exc:
            raise CutoverError(
                f"failed to repair canonical CLI from running service revision {old_revision}; "
                f"manual recovery may be needed: {sync_exc}"
            ) from sync_exc

    owned_service: OwnedService | None = None
    if quarantine is None:
        if pid_file is None or pid_meta_file is None:
            raise CutoverError(
                "a restart cutover requires both --pid-file and --pid-meta-file "
                "so an uncertain service can be stopped by exact identity"
            )
        owned_service = _capture_owned_service(
            repo=repo,
            pid_file=pid_file,
            pid_meta_file=pid_meta_file,
        )

    def quarantine_service(reason: str) -> None:
        if quarantine is not None:
            quarantine(reason)
            return
        if owned_service is None:
            raise CutoverError(
                "post-restart identity is uncertain, but no verified PID/meta "
                "identity was supplied for safe quarantine"
            )
        _quarantine_owned_service(
            owned_service,
            timeout=quarantine_timeout,
            sleep=sleep,
        )

    was_paused = bool(old_state.get("paused"))
    quiesced_by_cutover = False
    restart_attempted = False
    staged: StagedCLI | None = None
    activation: Activation | None = None
    try:
        if not was_paused:
            request("POST", "/api/v1/orchestrator/quiesce", {})
            quiesced_by_cutover = True
        if not force:
            drain_gate = "paused" if was_paused else "quiesced"
            try:
                _wait_for_state(
                    request,
                    lambda state: bool(state.get(drain_gate))
                    and _running_count(state) == 0,
                    timeout=timeout,
                    sleep=sleep,
                )
            except CutoverError as drain_error:
                # The local wait owns the configured drain budget.  If the
                # transient gate is still confirmed but workers remain, let
                # the restart endpoint cross its zero-budget persistence and
                # shutdown boundary.  It will record only those workers that
                # are genuinely still running at that point.  A missing gate
                # is a control-plane failure and must still roll back.
                latest_state = request("GET", "/api/v1/state", None)
                if not bool(latest_state.get(drain_gate)):
                    raise drain_error
                if _running_count(latest_state) == 0:
                    pass
                else:
                    logger.warning(
                        "Lifecycle drain timed out with %d worker(s) still running; "
                        "delegating persistence and termination to restart",
                        _running_count(latest_state),
                    )

        staged = stage(
            repo=repo,
            source_url=source_url,
            uv=uv,
            environ=env,
            operator_path=operator_path,
        )
        activation = activate(
            staged,
            canonical=canonical,
            tool_dir=tool_dir,
            bin_dir=bin_dir,
            environ=env,
            operator_path=operator_path,
        )

        # This request is the cutover point: the old process has drained, and
        # the candidate launcher is already active with a rollback journal.
        # Mark uncertainty before making the request.  A transport error can
        # mean the old process accepted the restart and dropped the connection
        # while executing the new revision.
        restart_attempted = True
        restart_error: Exception | None = None
        try:
            request("POST", "/api/v1/orchestrator/restart", {"drain_timeout_s": 0})
        except Exception as exc:  # noqa: BLE001 - acceptance may be unknowable
            restart_error = exc

        resolution, observation = _wait_for_cutover_resolution(
            request,
            old_instance,
            old_revision,
            staged.revision,
            timeout=health_timeout,
            sleep=sleep,
        )

        if resolution == "candidate":
            # Equality is proven.  Close the rollback journal before the
            # optional resume request so a resume transport failure cannot
            # roll the CLI back underneath a healthy new server.
            activation.commit()
            activation = None
            restart_attempted = False
            if not was_paused:
                # Candidate health and state have already proved the new
                # instance/revision pair.  Resume is a post-exec control-plane
                # hint: lifecycle reconciliation may still be draining in the
                # candidate, so a dropped or delayed response must not turn an
                # authoritative cutover into a rollback/error.  The next
                # state probe will expose the migration progress.
                try:
                    request("POST", "/api/v1/orchestrator/resume", {})
                except Exception as resume_error:  # noqa: BLE001 - candidate is authoritative
                    logger.warning(
                        "Candidate revision %s is healthy but resume response was "
                        "unavailable; migration remains observable on the new "
                        "instance: %s",
                        staged.revision,
                        resume_error,
                    )
                quiesced_by_cutover = False
            return staged.revision

        if resolution == "old":
            # The dropped request did not schedule a restart: the exact old
            # instance and build are healthy and explicitly report no restart
            # in progress.  Restoring the old launcher is a verified two-sided
            # rollback because the server side never changed.
            activation.rollback()
            activation = None
            restart_attempted = False
            if quiesced_by_cutover:
                request("POST", "/api/v1/orchestrator/resume", {})
                quiesced_by_cutover = False
            detail = str(restart_error) if restart_error else "restart was not accepted"
            raise CutoverError(
                f"{detail}; the verified old service and CLI pair was restored"
            )

        # A wrong build, a still-pending restart, or unavailable health cannot
        # safely be paired with either launcher.  Stop only the lifecycle PID
        # captured before activation; never issue a broad process kill.
        summary = _observation_summary(observation)
        reason = (
            str(restart_error)
            if restart_error
            else ("post-restart build/instance probes did not prove either pair")
        )
        quarantine_service(f"{reason}; observation={summary}")
        activation.commit()
        activation = None
        restart_attempted = False
        raise CutoverUncertainError(
            f"{reason}; observation={summary}. The exact lifecycle-owned "
            "service was stopped, so no mismatched server remains live. The "
            "candidate CLI was retained for a clean recovery start."
        )
    except CutoverUncertainError:
        raise
    except Exception as exc:
        if restart_attempted:
            # An unexpected failure while resolving the post-request identity
            # has the same safety requirements as a failed probe: quarantine
            # the exact owned process before retaining the candidate launcher.
            detail = str(exc) or exc.__class__.__name__
            try:
                quarantine_service(detail)
            except Exception as quarantine_exc:
                raise CutoverUncertainError(
                    f"{detail}; CRITICAL: the restart result is uncertain and "
                    "the exact lifecycle-owned service could not be stopped: "
                    f"{quarantine_exc}. Do not invoke either CLI until the "
                    "service PID is inspected and stopped."
                ) from exc
            if activation is not None:
                activation.commit()
                activation = None
            raise CutoverUncertainError(
                f"{detail}; the restart result is uncertain, so the exact "
                "lifecycle-owned service was stopped before retaining the "
                "candidate CLI. No mismatched server remains live."
            ) from exc

        if activation is not None:
            activation.rollback()
        if quiesced_by_cutover:
            try:
                request("POST", "/api/v1/orchestrator/resume", {})
            except Exception as resume_exc:  # pragma: no cover - defensive alert
                raise CutoverError(
                    f"{exc}; additionally could not resume the old service: "
                    f"{resume_exc}"
                ) from exc
        if isinstance(exc, CutoverError):
            raise
        if isinstance(exc, SyncError):
            raise CutoverError(str(exc)) from exc
        raise CutoverError(f"CLI/server cutover failed: {exc}") from exc
    finally:
        if staged is not None:
            staged.cleanup()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--tool-dir", type=Path)
    parser.add_argument("--bin-dir", type=Path)
    parser.add_argument(
        "--operator-path",
        help="PATH from the operator shell for canonical CLI validation",
    )
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--health-timeout", type=float, default=3660)
    parser.add_argument("--pid-file", type=Path)
    parser.add_argument("--pid-meta-file", type=Path)
    parser.add_argument("--quarantine-timeout", type=float, default=30)
    parser.add_argument(
        "--force",
        action="store_true",
        help="skip the graceful agent-drain wait after pausing the service",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify an already-running CLI/server pair without changing it",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.verify_only:
            revision = verify_pair(
                repo=args.repo,
                canonical=args.canonical,
                url=args.url,
                operator_path=args.operator_path,
            )
        else:
            revision = graceful_cutover(
                repo=args.repo,
                canonical=args.canonical,
                url=args.url,
                source_url=args.source_url,
                uv=args.uv,
                tool_dir=args.tool_dir,
                bin_dir=args.bin_dir,
                operator_path=args.operator_path,
                timeout=args.timeout,
                health_timeout=args.health_timeout,
                force=args.force,
                pid_file=args.pid_file,
                pid_meta_file=args.pid_meta_file,
                quarantine_timeout=args.quarantine_timeout,
            )
    except CutoverUncertainError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "Recovery: the candidate CLI remains canonical and the exact "
            "lifecycle-owned service was quarantined where identity proof was "
            "available. Inspect 'make status' and 'make logs', then use "
            "'make start' to establish the matching candidate pair.",
            file=sys.stderr,
        )
        return 1
    except CutoverError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "Recovery: verify the old service with make status, then run "
            "make install-cli after the checkout is clean and pushed.",
            file=sys.stderr,
        )
        return 1
    print(f"oompah service and canonical CLI cut over to revision {revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
