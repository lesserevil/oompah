"""Dolt sync watchdog: push/pull bd dolt state on the full-sync tick.

Today oompah calls ``bd dolt pull`` once per project at startup
(:mod:`oompah.projects`) and never pushes. Local bead changes from agents
(close, comment, status, auto-archive) commit to per-project local dolt
but never reach the upstream — ``sync.remote`` is configured in
``.beads/config.yaml`` but unused.

This module implements the periodic sync watchdog. The orchestrator calls
:func:`sync_project_dolt` per project on the full-sync tick, recording
status into :class:`DoltSyncState` for surfacing via the API/dashboard.

Decision tree per project:

1. ``bd dolt pull``  — fetches remote and merges into local. If it fails
   with a divergence-style message, record ``divergent=True`` and stop.
2. ``bd dolt push``  — sends local commits upstream. Idempotent: a
   nothing-to-push run still exits 0 in the bd CLI.
3. If a previous attempt set ``last_error``, the next attempt is deferred
   by 2x the configured interval (push backoff). Resets on first success.

All subprocesses are time-bound to a few seconds so a slow network can't
wedge the orchestrator tick. The module never raises — all failures are
recorded into the state dict.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from oompah.models import Project

logger = logging.getLogger(__name__)

# Per-subprocess timeout. Keep this bounded so bd/dolt network stalls do not
# wedge the orchestrator tick and starve unrelated dispatch/reconcile work.
DEFAULT_SUBPROCESS_TIMEOUT_S: float | None = 45.0

# Backoff multiplier on the existing full_sync interval after an error.
# A single transient error (rate limit, DNS hiccup) should not push a
# project into a long quiet period — 2x is enough to spread retries.
ERROR_BACKOFF_MULTIPLIER = 2.0

# Substrings in bd dolt pull stderr that indicate divergent history
# (i.e. a non-fast-forward merge that bd CLI refuses to auto-resolve).
# Dolt's exact wording varies by version; matching on these tokens
# is robust enough for the watchdog to flip the divergent flag.
_DIVERGENT_PATTERNS = (
    "non-fast-forward",
    "diverged",
    "would not be a fast-forward",
    "merge conflict",
    "conflicts during merge",
    "refusing to merge unrelated histories",
)


@dataclass
class DoltSyncResult:
    """Outcome of a single :func:`sync_project_dolt` invocation.

    ``pulled`` and ``pushed`` indicate whether the corresponding bd CLI
    command ran and succeeded this attempt. ``divergent`` is set when
    the remote and local histories have diverged in a way the watchdog
    cannot auto-resolve. ``error`` is a short human-readable string when
    something went wrong (network, timeout, divergence, subprocess
    failure). ``skipped_reason`` is set when the project was intentionally
    not synced (no .beads, in backoff, etc.).
    """

    project_id: str
    pulled: bool = False
    pushed: bool = False
    divergent: bool = False
    error: str | None = None
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "pulled": self.pulled,
            "pushed": self.pushed,
            "divergent": self.divergent,
            "error": self.error,
            "skipped_reason": self.skipped_reason,
        }


@dataclass
class DoltSyncState:
    """Per-project sync state, persisted in memory by the orchestrator.

    Used both to drive backoff (``next_attempt_monotonic``) and to surface
    status via :func:`Orchestrator.get_snapshot` / the dolt-sync HTTP
    endpoint and the dashboard banner.
    """

    project_id: str
    last_push_at: datetime | None = None
    last_pull_at: datetime | None = None
    last_error: str | None = None
    last_error_at: datetime | None = None
    divergent: bool = False
    consecutive_errors: int = 0
    # Monotonic seconds-since-boot until which this project should not
    # attempt another sync. Used purely for backoff; never persisted.
    next_attempt_monotonic: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "last_push_at": self.last_push_at.isoformat()
            if self.last_push_at
            else None,
            "last_pull_at": self.last_pull_at.isoformat()
            if self.last_pull_at
            else None,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at.isoformat()
            if self.last_error_at
            else None,
            "divergent": self.divergent,
            "consecutive_errors": self.consecutive_errors,
        }


def _is_divergent(stderr: str) -> bool:
    """Return True if the stderr message indicates divergent history."""
    lower = (stderr or "").lower()
    return any(pat in lower for pat in _DIVERGENT_PATTERNS)


def _truncate(msg: str, limit: int = 200) -> str:
    """Trim a (potentially long) stderr blob to a manageable length."""
    msg = (msg or "").strip()
    if len(msg) <= limit:
        return msg
    return msg[:limit] + "..."


def _run_bd_dolt(
    args: list[str],
    cwd: str,
    timeout_s: float | None,
    runner: Any = subprocess.run,
) -> subprocess.CompletedProcess:
    """Invoke ``bd dolt <args>`` with the given cwd and (optional) timeout.

    ``timeout_s`` is forwarded to ``subprocess.run``; ``None`` means no
    timeout (the default per ``DEFAULT_SUBPROCESS_TIMEOUT_S``).

    The ``runner`` indirection exists so tests can substitute a mock
    without monkey-patching the global ``subprocess.run``.
    """
    return runner(
        ["bd", "dolt", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def sync_project_dolt(
    project: Project,
    state: DoltSyncState,
    *,
    full_sync_interval_s: float,
    timeout_s: float | None = DEFAULT_SUBPROCESS_TIMEOUT_S,
    now_monotonic: float | None = None,
    now_utc: datetime | None = None,
    runner: Any = subprocess.run,
) -> DoltSyncResult:
    """Pull and push bd dolt state for one project.

    Never raises. All failures are recorded in ``state`` (mutated in place)
    and surfaced in the returned :class:`DoltSyncResult`.

    Backoff: if ``state.next_attempt_monotonic`` is in the future, the
    sync is skipped this tick and ``skipped_reason='backoff'`` is set.
    A successful sync clears the error state and the backoff window.

    Divergent history: if ``bd dolt pull`` reports a non-fast-forward or
    merge conflict, ``state.divergent`` is set and the push is skipped
    (operator must merge by hand). The watchdog will keep attempting
    pulls on subsequent ticks; the divergent flag clears as soon as a
    pull succeeds.
    """
    if now_monotonic is None:
        now_monotonic = time.monotonic()
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    result = DoltSyncResult(project_id=project.id)

    # Skip projects without a .beads/ directory — they don't use bd.
    if not project.repo_path or not os.path.isdir(
        os.path.join(project.repo_path, ".beads")
    ):
        result.skipped_reason = "no_beads_dir"
        return result

    # Backoff: respect next_attempt_monotonic on prior error.
    if state.next_attempt_monotonic > now_monotonic:
        result.skipped_reason = "backoff"
        return result

    # 1. Pull
    pull_ok = False
    pull_diverged = False
    try:
        pull = _run_bd_dolt(["pull"], project.repo_path, timeout_s, runner)
        if pull.returncode == 0:
            pull_ok = True
            state.last_pull_at = now_utc
            state.divergent = False  # successful pull clears divergence
            result.pulled = True
        else:
            stderr = pull.stderr or ""
            if _is_divergent(stderr):
                pull_diverged = True
                state.divergent = True
                result.divergent = True
                result.error = "diverged: " + _truncate(stderr)
            else:
                state.divergent = False
                result.error = "pull failed: " + _truncate(stderr)
    except subprocess.TimeoutExpired:
        state.divergent = False
        result.error = f"pull timed out after {timeout_s}s"
    except (FileNotFoundError, OSError) as exc:
        state.divergent = False
        result.error = f"pull failed: {exc}"

    # 2. Push — only if pull succeeded and history isn't diverged.
    push_attempted = False
    if pull_ok and not pull_diverged:
        push_attempted = True
        try:
            push = _run_bd_dolt(["push"], project.repo_path, timeout_s, runner)
            if push.returncode == 0:
                state.last_push_at = now_utc
                result.pushed = True
            else:
                stderr = push.stderr or ""
                if _is_divergent(stderr):
                    # A fast-follow remote change between pull and push.
                    # Pull again next tick will handle it; for now flag.
                    state.divergent = True
                    result.divergent = True
                    result.error = "push diverged: " + _truncate(stderr)
                else:
                    result.error = "push failed: " + _truncate(stderr)
        except subprocess.TimeoutExpired:
            result.error = f"push timed out after {timeout_s}s"
        except (FileNotFoundError, OSError) as exc:
            result.error = f"push failed: {exc}"

    # 3. Update backoff state. Any error in this attempt arms the
    # backoff window. A clean attempt clears it.
    if result.error is not None:
        state.last_error = result.error
        state.last_error_at = now_utc
        state.consecutive_errors += 1
        state.next_attempt_monotonic = (
            now_monotonic + full_sync_interval_s * ERROR_BACKOFF_MULTIPLIER
        )
        # Log once at WARNING so error_watcher does not auto-file beads.
        logger.warning(
            "Dolt sync error for %s: %s (backoff until +%.0fs)",
            project.name,
            result.error,
            full_sync_interval_s * ERROR_BACKOFF_MULTIPLIER,
        )
    else:
        if state.consecutive_errors or state.last_error:
            logger.info(
                "Dolt sync recovered for %s (pulled=%s pushed=%s)",
                project.name,
                result.pulled,
                push_attempted and result.pushed,
            )
        state.last_error = None
        state.last_error_at = None
        state.consecutive_errors = 0
        state.next_attempt_monotonic = 0.0

    return result


def get_or_create_state(
    states: dict[str, DoltSyncState],
    project_id: str,
) -> DoltSyncState:
    """Fetch the :class:`DoltSyncState` for a project, creating one on
    first access. Used by the orchestrator to lazily populate state
    without an explicit init pass."""
    st = states.get(project_id)
    if st is None:
        st = DoltSyncState(project_id=project_id)
        states[project_id] = st
    return st


def summarize_for_alerts(
    states: dict[str, DoltSyncState],
    projects_by_id: dict[str, Project],
) -> list[dict[str, str]]:
    """Render an alerts list (one entry per problematic project).

    Returns one alert per project that is either divergent or has at
    least 3 consecutive errors. The orchestrator merges these into its
    main ``_alerts`` list so the dashboard surfaces them next to
    auto-update/profile-drift warnings.

    Each alert dict carries ``project_id`` so the dashboard can map the
    click-to-expand modal back to a specific entry in
    ``/api/v1/orchestrator/dolt-sync`` (oompah-zlz_2-g8uk).
    """
    alerts: list[dict[str, str]] = []
    for pid, st in states.items():
        proj = projects_by_id.get(pid)
        name = proj.name if proj else pid
        if st.divergent:
            alerts.append(
                {
                    "level": "error",
                    "source": "dolt_sync",
                    "project_id": pid,
                    "message": (
                        f"Dolt sync diverged for {name} — operator must "
                        "merge bd dolt history by hand."
                    ),
                }
            )
        elif st.consecutive_errors >= 3 and st.last_error:
            alerts.append(
                {
                    "level": "warning",
                    "source": "dolt_sync",
                    "project_id": pid,
                    "message": (
                        f"Dolt sync failing for {name} "
                        f"({st.consecutive_errors}x): {st.last_error}"
                    ),
                }
            )
    return alerts
