"""Short-lived task handoff capabilities for spawned workers.

The service's HTTP Basic password is an operator credential and must never be
made available to an agent process.  Subprocess-backed agents still need a
way to finish the small tracker handoff required by ``AGENTS.md``, so the
server issues an opaque, expiring capability scoped to exactly one project,
task, and set of operations.

The registry is intentionally process-local: capabilities are minted and
consumed by the same oompah service that owns the tracker.  A capability is
not a replacement for Basic authentication on the general API; it is accepted
only by the dedicated task-handoff endpoint, which performs the scope check
again before touching the tracker.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from typing import FrozenSet


TASK_HANDOFF_TOKEN_ENV = "OOMPAH_TASK_HANDOFF_TOKEN"
TASK_HANDOFF_PROJECT_ENV = "OOMPAH_TASK_HANDOFF_PROJECT_ID"
TASK_HANDOFF_HEADER = "x-oompah-task-capability"
DEFAULT_TTL_SECONDS = 15 * 60


@dataclass(frozen=True)
class TaskHandoffGrant:
    """Server-owned authorization for one spawned worker session."""

    token_digest: str
    project_id: str
    task_identifier: str
    allowed_actions: FrozenSet[str]
    expires_at: float


class TaskHandoffGrantStore:
    """In-memory capability registry with constant-time token lookup."""

    def __init__(self, *, now=time.time):
        self._now = now
        self._lock = threading.Lock()
        self._grants: dict[str, TaskHandoffGrant] = {}
        self._failures: dict[str, str] = {}

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(
        self,
        *,
        project_id: str,
        task_identifier: str,
        allowed_actions: set[str] | frozenset[str],
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ) -> str:
        """Mint an opaque token without logging or returning operator secrets."""
        project_id = str(project_id or "").strip()
        task_identifier = str(task_identifier or "").strip()
        if not project_id or not task_identifier:
            raise ValueError("project_id and task_identifier are required")
        ttl = float(ttl_seconds)
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        token = secrets.token_urlsafe(32)
        now = float(self._now())
        grant = TaskHandoffGrant(
            token_digest=self._digest(token),
            project_id=project_id,
            task_identifier=task_identifier,
            allowed_actions=frozenset(str(a) for a in allowed_actions),
            expires_at=now + ttl,
        )
        with self._lock:
            self._purge_locked(now)
            self._grants[grant.token_digest] = grant
        return token

    def validate(
        self,
        token: str | None,
        *,
        project_id: str,
        task_identifier: str,
        action: str,
    ) -> tuple[bool, str]:
        """Validate token, scope, expiry, and operation.

        Returns a generic reason suitable for an agent-facing error.  The
        token itself is never included in the reason or logs.
        """
        if not isinstance(token, str) or not token:
            return False, "missing task handoff capability"
        digest = self._digest(token)
        now = float(self._now())
        with self._lock:
            self._purge_locked(now)
            grant = self._grants.get(digest)
        if grant is None or not hmac.compare_digest(grant.token_digest, digest):
            return False, "invalid or expired task handoff capability"
        if grant.expires_at <= now:
            return False, "invalid or expired task handoff capability"
        if not hmac.compare_digest(grant.project_id, str(project_id or "")):
            return False, "task handoff capability is scoped to another project"
        if not hmac.compare_digest(
            grant.task_identifier, str(task_identifier or "")
        ):
            return False, "task handoff capability is scoped to another task"
        if action not in grant.allowed_actions:
            return False, "task handoff action is not granted"
        return True, ""

    def revoke(self, token: str | None) -> None:
        """Revoke a capability after its worker exits."""
        if not token:
            return
        with self._lock:
            digest = self._digest(token)
            self._grants.pop(digest, None)
            self._failures.pop(digest, None)

    def record_failure(self, token: str | None, reason: str) -> None:
        """Remember a failed operation without retaining the bearer token."""
        if not token:
            return
        digest = self._digest(token)
        # Reasons are server-generated in normal use. Bound the stored value
        # anyway so an adapter exception cannot become unbounded state.
        safe_reason = str(reason or "task handoff operation failed")[:240]
        with self._lock:
            if digest in self._grants:
                self._failures[digest] = safe_reason

    def consume_failure(self, token: str | None) -> str | None:
        """Return and remove the failure recorded for a worker capability."""
        if not token:
            return None
        with self._lock:
            return self._failures.pop(self._digest(token), None)

    def _purge_locked(self, now: float) -> None:
        expired = [
            digest for digest, grant in self._grants.items()
            if grant.expires_at <= now
        ]
        for digest in expired:
            self._grants.pop(digest, None)
            self._failures.pop(digest, None)


_default_store = TaskHandoffGrantStore()


def issue_task_handoff_token(**kwargs) -> str:
    """Issue a capability from the service-owned default registry."""
    return _default_store.issue(**kwargs)


def validate_task_handoff_token(token: str | None, **kwargs) -> tuple[bool, str]:
    """Validate a capability from the service-owned default registry."""
    return _default_store.validate(token, **kwargs)


def revoke_task_handoff_token(token: str | None) -> None:
    """Revoke a capability from the service-owned default registry."""
    _default_store.revoke(token)


def record_task_handoff_failure(token: str | None, reason: str) -> None:
    """Record an operation failure for the orchestrator's exit reconciler."""
    _default_store.record_failure(token, reason)


def consume_task_handoff_failure(token: str | None) -> str | None:
    """Consume an operation failure for the orchestrator's exit reconciler."""
    return _default_store.consume_failure(token)
