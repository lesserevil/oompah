"""Thread-safe auth-plane health counters for operator and worker authentication.

Separate counters are maintained for:

- **Operator plane** — HTTP Basic authentication managed by the server
  middleware.  A 401 here means the operator's htpasswd credentials are
  stale, missing, or misconfigured.

- **Worker plane** — Scoped task-handoff capability tokens issued to
  spawned agent processes.  Distinct failure modes:
    * 401 — token absent, malformed, or expired (minting/delivery failure)
    * 403 scope — token presented but scoped to a different project or task
    * 403 action — token presented but the action is not in the grant set
      (intentional least-privilege denial; NOT surfaced as an alert)
    * minted — token was issued (count incremented at mint time)
    * accepted — token passed all checks and the operation proceeded

No credential material, token values, or authentication headers are stored
or returned.  All public surfaces expose only non-sensitive counts and bool
flags.

The module is process-local and intentionally avoids persistence so no
sensitive information accumulates on disk.  Restart-persistence is tracked
only by the orchestrator's durable alert list when it chooses to escalate.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

# Rolling window for "recent failure" status (15 minutes)
_WINDOW_SECONDS = 15 * 60


@dataclass
class _BucketEntry:
    """One timed event in the sliding window."""
    ts: float


class _SlidingWindow:
    """Bounded list of timestamps; thread-safe; used only under caller's lock."""

    __slots__ = ("_entries", "_maxlen")

    def __init__(self, maxlen: int = 512) -> None:
        self._entries: list[float] = []
        self._maxlen = maxlen

    def record(self, ts: float) -> None:
        self._entries.append(ts)
        if len(self._entries) > self._maxlen:
            self._entries = self._entries[-self._maxlen :]

    def count_since(self, cutoff: float) -> int:
        return sum(1 for t in self._entries if t >= cutoff)

    def clear(self) -> None:
        self._entries.clear()


class OperatorAuthHealth:
    """Tracks HTTP Basic auth failures and successes on the operator plane.

    Thread-safe; all public methods may be called from any thread.

    Tracks both failures (401s) and successes to detect when credentials are
    recovered. A failure followed by a success invalidates the failure-based
    alert, allowing the dashboard to show "recovered" status instead of
    remaining actionable.
    """

    def __init__(self, *, now=time.monotonic) -> None:
        self._lock = threading.Lock()
        self._now = now
        self._401_window = _SlidingWindow()
        self._total_401: int = 0
        self._last_success_ts: float | None = None

    def record_401(self) -> None:
        """Increment the 401 counter (wrong/stale operator credentials)."""
        with self._lock:
            ts = self._now()
            self._401_window.record(ts)
            self._total_401 += 1

    def record_success(self) -> None:
        """Record a successful authenticated operator request.

        When a success is recorded after previous failures, the failure-based
        alert is marked as recovered, allowing the dashboard to show that
        credentials have been restored.
        """
        with self._lock:
            self._last_success_ts = self._now()

    def snapshot(self, window_seconds: float = _WINDOW_SECONDS) -> dict[str, Any]:
        """Return a safe, redacted health snapshot.

        Returns:
            dict with keys:
              - plane: "operator_basic"
              - recent_401_count: int  # failures in last *window_seconds*
              - total_401_count: int   # lifetime failures (resets on restart)
              - window_seconds: float  # the window used
              - status: "ok" | "degraded" | "recovered"
              - recovered: bool  # true if most recent success > most recent failure
        """
        with self._lock:
            cutoff = self._now() - window_seconds
            recent = self._401_window.count_since(cutoff)
            total = self._total_401
            last_success = self._last_success_ts
            # Get the most recent failure timestamp (newest entry at the end)
            entries = self._401_window._entries
            last_failure = entries[-1] if entries else None

        # If there have been failures and successes, check if the most recent
        # success is more recent than the most recent failure in the window.
        recovered = False
        if recent > 0 and last_success is not None and last_failure is not None:
            recovered = last_success > last_failure

        status = "ok" if recent == 0 else ("recovered" if recovered else "degraded")
        return {
            "plane": "operator_basic",
            "recent_401_count": recent,
            "total_401_count": total,
            "window_seconds": window_seconds,
            "status": status,
            "recovered": recovered,
        }

    def build_alert(self, window_seconds: float = _WINDOW_SECONDS) -> dict[str, Any] | None:
        """Return an alert dict if recent operator auth failures warrant one.

        Returns None when the operator plane is healthy.  If credentials have
        recovered (recent success after recent failures), returns an alert with
        "recovered" recovery_state so the dashboard marks it as cleared.

        The alert includes actionable recovery guidance only when the issue
        remains active; no credentials are included.
        """
        snap = self.snapshot(window_seconds)
        if snap["recent_401_count"] == 0:
            return None

        count = snap["recent_401_count"]
        is_recovered = snap.get("recovered", False)

        summary = (
            f"Operator HTTP Basic auth: {count} failed "
            f"request{'s' if count != 1 else ''} in the last "
            f"{int(window_seconds // 60)} min — credentials may be stale."
        )

        if is_recovered:
            # Credentials have recovered; mark the alert as resolved
            remediation = (
                "Operator credentials have been restored. "
                "The server is now accepting authenticated requests."
            )
            recovery_state = "recovered"
            action_required = False
        else:
            # Credentials are still failing; provide actionable remediation
            remediation = (
                "Update OOMPAH_HTPASSWD_FILE (or regenerate .htpasswd beside "
                "your .env), then run `make restart` to reload credentials."
            )
            recovery_state = "active"
            action_required = True

        return {
            "level": "warning",
            "severity": "warning",
            "source": "auth_health:operator",
            "stable_id": "auth_health:operator",
            "action_required": action_required,
            "recovery_state": recovery_state,
            "lifecycle_state": recovery_state,
            "status": recovery_state,
            "active": not is_recovered,
            "recovered": is_recovered,
            "summary": summary,
            "message": summary,
            "detail": (
                "The server's htpasswd file may not match the credentials "
                "being supplied.  This does not affect running workers."
            ),
            "remediation": remediation,
            "action": remediation,
        }


class WorkerAuthHealth:
    """Tracks task-handoff capability health on the worker plane.

    Distinguishes four event types:

    * **minted** — a capability was issued by the server (token created)
    * **accepted** — capability presented, scope/expiry checks passed
    * **401** — capability absent, malformed, or expired
    * **403_scope** — capability scoped to a different project or task
    * **403_action** — capability action not in the grant set (intentional
      least-privilege; never counted toward degraded status)
    * **403_policy** — a verified live worker intentionally attempted a
      read-only view of another task (policy denial; never counted toward
      degraded status). The target may be non-running or unknown; it is never
      resolved for this classification.

    Thread-safe; all public methods may be called from any thread.
    """

    def __init__(self, *, now=time.monotonic) -> None:
        self._lock = threading.Lock()
        self._now = now
        self._minted: int = 0
        self._accepted: int = 0
        self._401_window = _SlidingWindow()
        self._403_scope_window = _SlidingWindow()
        self._403_action: int = 0  # intentional — not a health signal
        self._403_policy: int = 0  # intentional cross-task policy denials
        self._total_401: int = 0
        self._total_403_scope: int = 0

    def record_minted(self) -> None:
        """Increment the minted counter when a handoff token is issued."""
        with self._lock:
            self._minted += 1

    def record_accepted(self) -> None:
        """Increment the accepted counter when a handoff request passes all checks."""
        with self._lock:
            self._accepted += 1

    def record_401(self) -> None:
        """Increment the worker 401 counter (missing/invalid/expired token)."""
        with self._lock:
            ts = self._now()
            self._401_window.record(ts)
            self._total_401 += 1

    def record_403_scope(self) -> None:
        """Increment the cross-scope 403 counter (wrong project or task)."""
        with self._lock:
            ts = self._now()
            self._403_scope_window.record(ts)
            self._total_403_scope += 1

    def record_403_action(self) -> None:
        """Increment intentional action-denial counter (no health alert raised)."""
        with self._lock:
            self._403_action += 1

    def record_403_policy(self) -> None:
        """Increment verified intentional cross-task policy denials."""
        with self._lock:
            self._403_policy += 1

    def snapshot(self, window_seconds: float = _WINDOW_SECONDS) -> dict[str, Any]:
        """Return a safe, redacted health snapshot.

        Returns:
            dict with keys:
              - plane: "worker_task_handoff"
              - token_ever_minted: bool
              - token_ever_accepted: bool
              - recent_401_count: int
              - recent_403_scope_count: int
              - total_401_count: int
              - total_403_scope_count: int
              - policy_denial_count: int  # intentional, informational only
              - scope_denial_count: int   # compatibility alias for policy count
              - window_seconds: float
              - status: "ok" | "degraded" | "never_minted"
        """
        with self._lock:
            cutoff = self._now() - window_seconds
            recent_401 = self._401_window.count_since(cutoff)
            recent_403_scope = self._403_scope_window.count_since(cutoff)
            minted = self._minted
            accepted = self._accepted
            total_401 = self._total_401
            total_403_scope = self._total_403_scope
            policy_denials = self._403_action + self._403_policy

        if minted == 0:
            status = "never_minted"
        elif recent_401 > 0 or recent_403_scope > 0:
            status = "degraded"
        else:
            status = "ok"

        return {
            "plane": "worker_task_handoff",
            "token_ever_minted": minted > 0,
            "token_ever_accepted": accepted > 0,
            "recent_401_count": recent_401,
            "recent_403_scope_count": recent_403_scope,
            "total_401_count": total_401,
            "total_403_scope_count": total_403_scope,
            "policy_denial_count": policy_denials,
            "scope_denial_count": policy_denials,
            "window_seconds": window_seconds,
            "status": status,
        }

    def build_alert(self, window_seconds: float = _WINDOW_SECONDS) -> dict[str, Any] | None:
        """Return an alert dict if recent worker auth failures warrant one.

        Returns None when the worker plane is healthy or has never minted a
        token (quiet — no workers have been dispatched yet).
        """
        snap = self.snapshot(window_seconds)
        status = snap["status"]
        if status in ("ok", "never_minted"):
            return None

        parts: list[str] = []
        if snap["recent_401_count"] > 0:
            n = snap["recent_401_count"]
            parts.append(
                f"{n} token-missing/expired failure{'s' if n != 1 else ''}"
            )
        if snap["recent_403_scope_count"] > 0:
            n = snap["recent_403_scope_count"]
            parts.append(f"{n} cross-scope rejection{'s' if n != 1 else ''}")

        description = "; ".join(parts) if parts else "failures detected"
        window_min = int(window_seconds // 60)

        not_accepted_note = ""
        if snap["token_ever_minted"] and not snap["token_ever_accepted"]:
            not_accepted_note = (
                " A token was minted but never successfully accepted — "
                "the worker may not be forwarding the capability header."
            )

        summary = (
            f"Worker task-handoff auth: {description} "
            f"in the last {window_min} min.{not_accepted_note}"
        )
        remediation = (
            "Check that agent_environment() strips OOMPAH_SERVER_PASSWORD "
            "and forwards OOMPAH_TASK_HANDOFF_TOKEN and "
            "OOMPAH_TASK_HANDOFF_PROJECT_ID to every spawned worker.  "
            "See docs/scoped-task-cli-authentication.md for the live probe "
            "procedure."
        )
        return {
            "level": "warning",
            "severity": "warning",
            "source": "auth_health:worker",
            "stable_id": "auth_health:worker",
            "action_required": True,
            "recovery_state": "active",
            "lifecycle_state": "active",
            "status": "active",
            "active": True,
            "recovered": False,
            "summary": summary,
            "message": summary,
            "detail": (
                "Worker tokens are scoped to one project and task.  "
                "Cross-scope rejections indicate a misconfigured project_id or "
                "task identifier.  Missing-token errors indicate the worker "
                "did not receive or forward OOMPAH_TASK_HANDOFF_TOKEN."
            ),
            "remediation": remediation,
            "action": remediation,
        }


# ---------------------------------------------------------------------------
# Process-level singletons — one counter set per running service instance.
# ---------------------------------------------------------------------------

_operator_health = OperatorAuthHealth()
_worker_health = WorkerAuthHealth()


def record_operator_401() -> None:
    """Record an operator Basic-auth 401 from the server middleware."""
    _operator_health.record_401()


def record_operator_success() -> None:
    """Record a successful operator Basic-auth request from the server middleware.

    When a success is recorded after previous failures, the failure-based
    alert will be marked as recovered, allowing the dashboard to show that
    credentials have been restored.
    """
    _operator_health.record_success()


def record_worker_token_minted() -> None:
    """Record that a worker token was successfully minted."""
    _worker_health.record_minted()


def record_worker_token_accepted() -> None:
    """Record that a worker token was presented and accepted."""
    _worker_health.record_accepted()


def record_worker_401() -> None:
    """Record a 401 on the task-handoff endpoint (missing/invalid token)."""
    _worker_health.record_401()


def record_worker_403_scope() -> None:
    """Record a cross-scope 403 on the task-handoff endpoint."""
    _worker_health.record_403_scope()


def record_worker_403_action() -> None:
    """Record an intentional action-denial 403 (not a health signal)."""
    _worker_health.record_403_action()


def record_worker_403_policy() -> None:
    """Record a verified intentional cross-task policy 403."""
    _worker_health.record_403_policy()


def auth_health_snapshot() -> dict[str, Any]:
    """Return a combined operator+worker auth health snapshot for the state API.

    The returned dict is safe to include in API responses; no credentials,
    tokens, or sensitive fields are included.
    """
    return {
        "operator": _operator_health.snapshot(),
        "worker": _worker_health.snapshot(),
    }


def auth_health_alerts() -> list[dict[str, Any]]:
    """Return 0–2 alert dicts if either auth plane is degraded.

    Suitable for inclusion in the orchestrator's alerts list.  Returns an
    empty list when both planes are healthy or never-minted.
    """
    alerts: list[dict[str, Any]] = []
    op_alert = _operator_health.build_alert()
    if op_alert is not None:
        alerts.append(op_alert)
    wk_alert = _worker_health.build_alert()
    if wk_alert is not None:
        alerts.append(wk_alert)
    return alerts


def _reset_for_testing() -> None:
    """Reset all counters to zero.  For use in tests only."""
    global _operator_health, _worker_health
    _operator_health = OperatorAuthHealth()
    _worker_health = WorkerAuthHealth()
