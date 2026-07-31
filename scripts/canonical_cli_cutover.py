#!/usr/bin/env python3
"""Coordinate a safe canonical-CLI and service restart cutover.

The old service is paused and drained before a candidate is staged.  Staging
uses an isolated UV tool root; activation is the only operation that changes
the canonical launcher.  The activation journal is retained until the new
service reports the expected build identity, so every failure before that
point can restore the old CLI and resume the old service.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

try:  # Works both as ``python -m`` and as a Makefile script path.
    from scripts.sync_canonical_cli import (
        DEFAULT_SOURCE_URL,
        Activation,
        StagedCLI,
        SyncError,
        activate_candidate,
        stage_candidate,
    )
except ModuleNotFoundError:  # pragma: no cover - exercised by script startup
    from sync_canonical_cli import (  # type: ignore[no-redef]
        DEFAULT_SOURCE_URL,
        Activation,
        StagedCLI,
        SyncError,
        activate_candidate,
        stage_candidate,
    )


class CutoverError(RuntimeError):
    """Raised when a service/CLI cutover cannot safely complete."""


Request = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]


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


def _wait_for_new_health(
    request: Request,
    old_instance: str | None,
    revision: str,
    *,
    timeout: float,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = request("GET", "/healthz", None)
        instance = last.get("instance_id")
        if (
            last.get("status") == "ok"
            and instance
            and instance != old_instance
            and _revision_from_identity(last) == revision.lower()
        ):
            return last
        sleep(min(1.0, max(deadline - time.monotonic(), 0.01)))
    raise CutoverError(
        "new service instance did not pass the health/build-id check; "
        f"expected revision {revision}, last health="
        f"{json.dumps(last, sort_keys=True)[:500]}"
    )


def verify_pair(
    *,
    repo: Path,
    canonical: Path,
    url: str,
    environ: dict[str, str] | None = None,
    request: Request | None = None,
) -> str:
    """Verify command resolution and equality for an already-running service."""
    env = dict(os.environ if environ is None else environ)
    if request is None:
        request = lambda method, path, body: _http_request(
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
    resolved = shutil.which("oompah", path=env.get("PATH"))
    if resolved is None or os.path.abspath(resolved) != os.path.abspath(canonical):
        raise CutoverError(
            "command -v oompah does not resolve to the canonical launcher "
            f"{canonical} (resolved {resolved or 'not found'})"
        )
    result = subprocess.run(
        [str(canonical), "--version"],
        env=env,
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
    request: Request | None = None,
    stage: Callable[..., StagedCLI] = stage_candidate,
    activate: Callable[..., Activation] = activate_candidate,
    timeout: float = 3600,
    health_timeout: float = 3660,
    force: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Perform a pause, stage, activate, restart, and health-check transaction."""
    env = dict(os.environ if environ is None else environ)
    home = Path(env.get("HOME", str(Path.home())))
    tool_dir = tool_dir or Path(env.get("UV_TOOL_DIR", home / ".local/share/uv/tools"))
    bin_dir = bin_dir or Path(env.get("UV_TOOL_BIN_DIR", canonical.parent))
    if request is None:
        request = lambda method, path, body: _http_request(
            repo=repo,
            python=sys.executable,
            url=url,
            method=method,
            path=path,
            body=body,
        )

    old_health = request("GET", "/healthz", None)
    old_state = request("GET", "/api/v1/state", None)
    old_instance = old_health.get("instance_id")
    old_revision = _revision_from_identity(old_state) or _revision_from_identity(old_health)
    if old_revision is None:
        raise CutoverError(
            "running service has no build identity; refusing to risk a CLI/server mismatch"
        )
    current = subprocess.run(
        [str(canonical), "--version"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if current.returncode != 0 or f"revision {old_revision}" not in (
        current.stdout + current.stderr
    ).lower():
        raise CutoverError(
            "canonical CLI does not match the running service; repair it with "
            "make install-cli before attempting a restart"
        )

    was_paused = bool(old_state.get("paused"))
    paused = False
    committed = False
    staged: StagedCLI | None = None
    activation: Activation | None = None
    try:
        request("POST", "/api/v1/orchestrator/pause", {})
        paused = True
        if not force:
            _wait_for_state(
                request,
                lambda state: bool(state.get("paused")) and _running_count(state) == 0,
                timeout=timeout,
                sleep=sleep,
            )

        staged = stage(
            repo=repo,
            source_url=source_url,
            uv=uv,
            environ=env,
        )
        activation = activate(
            staged,
            canonical=canonical,
            tool_dir=tool_dir,
            bin_dir=bin_dir,
            environ=env,
        )

        # This request is the cutover point: the old process has drained, and
        # the candidate launcher is already active with a rollback journal.
        request("POST", "/api/v1/orchestrator/restart", {"drain_timeout_s": 0})
        committed = True
        _wait_for_new_health(
            request,
            old_instance,
            staged.revision,
            timeout=health_timeout,
            sleep=sleep,
        )
        new_state = request("GET", "/api/v1/state", None)
        if _revision_from_identity(new_state) != staged.revision.lower():
            raise CutoverError(
                "new service state build identity does not match the staged CLI"
            )
        # Equality is proven.  Close the rollback journal before the optional
        # resume request so a resume transport failure cannot roll the CLI
        # back underneath a healthy new server.
        activation.commit()
        if not was_paused:
            request("POST", "/api/v1/orchestrator/resume", {})
        return staged.revision
    except Exception as exc:
        if activation is not None:
            # Roll back both pre-cutover failures and a post-cutover health
            # failure.  The latter leaves an explicit operator alert below;
            # restoring the launcher makes the next recovery command safe.
            activation.rollback()
        if paused:
            # A restart request is asynchronous.  If health still identifies
            # the old instance, the process never crossed the cutover and it
            # is safe—and necessary—to unpause it.  Once a new instance is
            # visible, leave the explicit post-cutover failure alert intact;
            # blindly resuming would target the wrong process.
            should_resume = not committed
            if committed:
                try:
                    should_resume = (
                        request("GET", "/healthz", None).get("instance_id")
                        == old_instance
                    )
                except Exception:
                    should_resume = False
            if should_resume:
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
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--health-timeout", type=float, default=3660)
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
                timeout=args.timeout,
                health_timeout=args.health_timeout,
                force=args.force,
            )
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
