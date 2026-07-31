"""Task-scoped handoff capabilities for spawned workers.

The service's HTTP Basic password is an operator credential and must never be
made available to an agent process.  Subprocess-backed agents still need a
way to finish the small tracker handoff required by ``AGENTS.md``, so the
server issues an opaque, expiring capability scoped to exactly one project,
task, and set of operations.

The registry is intentionally process-local: capabilities are minted and
consumed by the same oompah service that owns the tracker. A capability is
not a replacement for Basic authentication on the general API; it is accepted
only by the dedicated task-handoff endpoint, which performs the scope check
again before touching the tracker.

Each dispatched worker also owns a server-side lease. The lease refreshes the
grant without requiring tracker traffic, so a worker can spend longer than the
initial TTL inside a tool call. The orchestrator stops the lease and revokes
the grant when the worker's process tree has actually terminated.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable, FrozenSet


TASK_HANDOFF_TOKEN_ENV = "OOMPAH_TASK_HANDOFF_TOKEN"
TASK_HANDOFF_PROJECT_ENV = "OOMPAH_TASK_HANDOFF_PROJECT_ID"
TASK_HANDOFF_HEADER = "x-oompah-task-capability"
# Bind grant lifetime to the owning worker session, not wall-clock TTL.
# This TTL should be longer than any single worker's expected runtime,
# allowing safe execution of long tool calls and restart recovery.
# TTL is reset on each heartbeat; expiry should only occur if worker is
# truly dead or the grant is explicitly revoked.
DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24 hours — covers session lifetime
_MAX_HEARTBEAT_INTERVAL_SECONDS = 60.0
_MIN_HEARTBEAT_INTERVAL_SECONDS = 0.01


@dataclass(frozen=True)
class TaskHandoffGrant:
    """Server-owned authorization for one spawned worker session.

    Grants are bound to the owning worker's lifetime, not wall-clock time.
    Expiry should occur only if the worker is truly dead or the grant is
    explicitly revoked to prevent reuse after termination.

    ``original_ttl_seconds`` is the TTL the grant was minted with. Heartbeat
    renewal (either from the server-side lease or the endpoint refresh) uses
    this value as the default extension so a grant minted with a deliberately
    short TTL is not silently widened to the module default. Operators who
    configure a short-lived capability retain that bound across the entire
    session.
    """

    token_digest: str
    project_id: str
    task_identifier: str
    allowed_actions: FrozenSet[str]
    expires_at: float
    owner_id: str | None = None
    revoked_at: float | None = None  # Explicit revocation timestamp
    original_ttl_seconds: float = DEFAULT_TTL_SECONDS


class TaskHandoffGrantStore:
    """In-memory capability registry with constant-time token lookup."""

    def __init__(self, *, now=time.time):
        self._now = now
        self._lock = threading.Lock()
        self._grants: dict[str, TaskHandoffGrant] = {}
        self._failures: dict[str, str] = {}
        self._leases: dict[str, TaskHandoffLease] = {}

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
        owner_id: str | None = None,
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
            owner_id=str(owner_id).strip() if owner_id else None,
            original_ttl_seconds=ttl,
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

        Returns an explicit reason that distinguishes between expired,
        revoked, and missing/invalid tokens. Reasons are suitable for
        agent-facing diagnostics. The token itself is never included in
        the reason or logs.
        """
        if not isinstance(token, str) or not token:
            return False, "missing task handoff capability"
        digest = self._digest(token)
        now = float(self._now())
        with self._lock:
            grant = self._grants.get(digest)
            # Check expiry before purging to provide better diagnostics
            if grant is not None:
                if grant.expires_at <= now:
                    # Distinguish revoked from TTL expiry
                    reason = (
                        "task handoff capability was revoked when the worker terminated"
                        if grant.revoked_at is not None
                        else "task handoff capability expired; worker must complete within the session lifetime"
                    )
                    self._purge_locked(now)
                    return False, reason
            # Now purge expired grants from the store
            self._purge_locked(now)
            grant = self._grants.get(digest)
        
        # Distinguish revoked (explicit termination) from expired (TTL)
        if grant is None or not hmac.compare_digest(grant.token_digest, digest):
            # Token never existed, was purged, or digest doesn't match
            return False, "invalid or expired task handoff capability"
        
        # Check revocation state (should not happen given purge above, but be safe)
        if grant.revoked_at is not None:
            return False, "task handoff capability was revoked when the worker terminated"
        
        # Check project/task scope (prevent cross-task/project use)
        if not hmac.compare_digest(grant.project_id, str(project_id or "")):
            return False, "task handoff capability is scoped to another project"
        if not hmac.compare_digest(
            grant.task_identifier, str(task_identifier or "")
        ):
            return False, "task handoff capability is scoped to another task"
        
        # Check action scope (prevent privilege escalation)
        if action not in grant.allowed_actions:
            return False, "task handoff action is not granted"
        return True, ""

    def revoke(self, token: str | None) -> None:
        """Revoke a capability after its worker exits.
        
        Marks the grant as revoked to prevent reuse after termination.
        Keeps the grant in memory briefly to distinguish explicit revocation
        from expiry when validating stale or retry attempts.
        """
        if not token:
            return
        digest = self._digest(token)
        now = float(self._now())
        lease = None
        with self._lock:
            grant = self._grants.get(digest)
            if grant is not None:
                # Mark as revoked with a grace period (10 seconds) to catch
                # late-arriving requests that race with termination.
                # After grace, normal expiry will purge the entry.
                revoked_grant = TaskHandoffGrant(
                    token_digest=grant.token_digest,
                    project_id=grant.project_id,
                    task_identifier=grant.task_identifier,
                    allowed_actions=grant.allowed_actions,
                    expires_at=now + 10.0,  # Short grace period
                    owner_id=grant.owner_id,
                    revoked_at=now,
                    original_ttl_seconds=grant.original_ttl_seconds,
                )
                self._grants[digest] = revoked_grant
            lease = self._leases.pop(digest, None)
            self._failures.pop(digest, None)
        if lease is not None:
            lease.stop()

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
    
    def refresh(
        self,
        token: str | None,
        *,
        ttl_seconds: float | None = None,
        owner_id: str | None = None,
    ) -> bool:
        """Extend the TTL of an active grant (heartbeat-based renewal).

        Called on each tool invocation and by the server-owned lease to keep
        the grant alive during long tool calls and restart recovery. When
        ``ttl_seconds`` is ``None`` the grant's original TTL is reused, so a
        deliberately short-lived capability is never silently widened to the
        module default. Returns True if refresh succeeded, False if the token
        is invalid, expired, revoked, or minted for a different owner.
        """
        if not token:
            return False
        digest = self._digest(token)
        now = float(self._now())
        with self._lock:
            grant = self._grants.get(digest)
            if grant is None or grant.revoked_at is not None:
                # Token is missing or revoked; do not extend
                return False
            if grant.expires_at <= now:
                self._purge_locked(now)
                return False
            # The endpoint is already protected by the bearer capability and
            # exact task/project/action scope. A lease heartbeat additionally
            # supplies owner_id, which prevents one worker's lease from
            # renewing another worker's grant. The endpoint intentionally
            # leaves owner_id unset so it can refresh an otherwise valid grant
            # during a server-side request.
            if owner_id is not None and grant.owner_id != str(owner_id):
                return False
            # Custom TTL preservation: never extend beyond what the grant was
            # minted with unless the caller explicitly opts into a shorter
            # override. This blocks accidental widening of an intentionally
            # short-lived capability by a periodic heartbeat.
            if ttl_seconds is None:
                ttl = float(grant.original_ttl_seconds)
            else:
                ttl = float(ttl_seconds)
                if ttl <= 0:
                    return False
                if ttl > float(grant.original_ttl_seconds):
                    ttl = float(grant.original_ttl_seconds)
            if ttl <= 0:
                return False
            # Extend expiry; preserve revocation state (should be None)
            extended_grant = TaskHandoffGrant(
                token_digest=grant.token_digest,
                project_id=grant.project_id,
                task_identifier=grant.task_identifier,
                allowed_actions=grant.allowed_actions,
                expires_at=now + ttl,
                owner_id=grant.owner_id,
                revoked_at=grant.revoked_at,
                original_ttl_seconds=grant.original_ttl_seconds,
            )
            self._grants[digest] = extended_grant
            return True

    def start_lease(
        self,
        token: str | None,
        *,
        owner_id: str | None = None,
        heartbeat_interval_seconds: float | None = None,
        owner_is_live: Callable[[], bool] | None = None,
    ) -> "TaskHandoffLease | None":
        """Start an independent renewal heartbeat for a live worker.

        A lease can only be started for an active grant. Grants issued with an
        owner identity require the same identity here; the bearer token alone
        is not sufficient to create a second renewal owner. ``None`` indicates
        a missing, expired, revoked, or owner-mismatched grant.
        """
        if not token:
            return None
        digest = self._digest(token)
        now = float(self._now())
        with self._lock:
            grant = self._grants.get(digest)
            if grant is None or grant.revoked_at is not None:
                return None
            if grant.expires_at <= now:
                self._purge_locked(now)
                return None
            if grant.owner_id is not None and grant.owner_id != str(owner_id or ""):
                return None
            if heartbeat_interval_seconds is None:
                heartbeat_interval_seconds = min(
                    _MAX_HEARTBEAT_INTERVAL_SECONDS,
                    max(
                        (grant.expires_at - now) / 3.0,
                        _MIN_HEARTBEAT_INTERVAL_SECONDS,
                    ),
                )
            interval = float(heartbeat_interval_seconds)
            if interval <= 0:
                return None
            previous = self._leases.pop(digest, None)
            lease = TaskHandoffLease(
                self,
                token,
                owner_id=owner_id,
                heartbeat_interval_seconds=interval,
                owner_is_live=owner_is_live,
            )
            self._leases[digest] = lease
        if previous is not None:
            previous.stop()
        lease.start()
        return lease

    def _purge_locked(self, now: float) -> None:
        expired = [
            digest for digest, grant in self._grants.items()
            if grant.expires_at <= now
        ]
        for digest in expired:
            self._grants.pop(digest, None)
            self._failures.pop(digest, None)
            self._leases.pop(digest, None)


class TaskHandoffLease:
    """A daemon heartbeat that renews one grant while its worker is live."""

    def __init__(
        self,
        store: TaskHandoffGrantStore,
        token: str,
        *,
        owner_id: str | None,
        heartbeat_interval_seconds: float,
        owner_is_live: Callable[[], bool] | None,
    ) -> None:
        self._store = store
        self._token = token
        self._owner_id = owner_id
        self._interval = heartbeat_interval_seconds
        self._owner_is_live = owner_is_live
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Begin the renewal thread after the grant has been registered."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="oompah-task-handoff-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def heartbeat(self) -> bool:
        """Renew once; useful for deterministic tests and diagnostics."""
        return self._store.refresh(self._token, owner_id=self._owner_id)

    def stop(self) -> None:
        """Stop renewal promptly without extending the grant."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=min(self._interval, 1.0))

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            if self._owner_is_live is not None:
                try:
                    owner_is_live = self._owner_is_live()
                except Exception:
                    owner_is_live = False
                if not owner_is_live:
                    self._store.revoke(self._token)
                    return
            if not self.heartbeat():
                return


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


def refresh_task_handoff_token(
    token: str | None,
    *,
    ttl_seconds: float | None = None,
) -> bool:
    """Extend the TTL of a task handoff grant (heartbeat-based renewal).

    Called on tool invocation to keep the grant alive during long tool calls.
    When ``ttl_seconds`` is ``None`` the grant's original TTL is reused, so a
    grant minted with a short TTL is not silently widened to the module
    default. Returns True if refresh succeeded, False if token is
    invalid/revoked.
    """
    return _default_store.refresh(token, ttl_seconds=ttl_seconds)


def start_task_handoff_lease(
    token: str | None,
    *,
    owner_id: str | None = None,
    heartbeat_interval_seconds: float | None = None,
    owner_is_live: Callable[[], bool] | None = None,
) -> TaskHandoffLease | None:
    """Start a server-owned heartbeat for a live worker grant."""
    return _default_store.start_lease(
        token,
        owner_id=owner_id,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        owner_is_live=owner_is_live,
    )
