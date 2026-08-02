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

Grants have a short wall-clock TTL (15 minutes) as a safety mechanism: if the
grant is leaked or reused after termination, it expires naturally. A
server-side lease renews the grant while the worker is live, keeping it active
through long tool calls and restart recovery. When the worker terminates, the
orchestrator stops the lease and revokes the grant, immediately blocking
further access. If the lease thread crashes or the server restarts unexpectedly,
the grant still expires at the wall-clock boundary instead of remaining live.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable, FrozenSet


# OOMPAH-651 supplies the process-wide dynamic-secret registry.  Keep this
# boundary import-compatible with the pre-651 branch so the lease lifecycle
# can be tested and integrated independently; once the secrets module is
# present these are the real retention hooks, never bearer logging.
try:
    from oompah.secrets import (
        SECRET_REDACTION_GRACE_SECONDS,
        renew_secret,
        retire_secret,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - removed when 651 lands
    if exc.name != "oompah.secrets":
        raise
    SECRET_REDACTION_GRACE_SECONDS = 60 * 60

    def renew_secret(
        _value: str | bytes | None,
        *,
        expires_in: float,
    ) -> None:
        """Compatibility no-op until the centralized secret registry exists."""

    def retire_secret(
        _value: str | bytes | None,
        *,
        grace_seconds: float = SECRET_REDACTION_GRACE_SECONDS,
    ) -> None:
        """Compatibility no-op until the centralized secret registry exists."""


TASK_HANDOFF_TOKEN_ENV = "OOMPAH_TASK_HANDOFF_TOKEN"
TASK_HANDOFF_PROJECT_ENV = "OOMPAH_TASK_HANDOFF_PROJECT_ID"
# Non-secret assignment context used only to classify an intentional peer
# denial in auth-health telemetry. The server verifies it against the live
# running entry and presented capability before treating a 403 as expected.
TASK_HANDOFF_TASK_ENV = "OOMPAH_TASK_HANDOFF_TASK_ID"
TASK_HANDOFF_HEADER = "x-oompah-task-capability"
# Bind grant lifetime to the owning worker session, not wall-clock TTL.
# This TTL should be longer than any single worker's expected runtime,
# allowing safe execution of long tool calls and restart recovery.
# TTL is reset on each heartbeat; expiry should only occur if worker is
# truly dead or the grant is explicitly revoked.
DEFAULT_TTL_SECONDS = 15 * 60  # 15 minutes — short wall-clock safety bound
_MAX_HEARTBEAT_INTERVAL_SECONDS = 60.0
_MIN_HEARTBEAT_INTERVAL_SECONDS = 0.01


class OperationPermitDenied(Exception):
    """Grant was revoked or operation not authorized after validation."""


@dataclass
class _OperationState:
    """Mutable admission state kept separately from immutable grant records."""

    active: int = 0


@dataclass
class OperationPermit:
    """Admission ticket for one scoped mutation.

    ``acquire_permit`` only authenticates and scopes the ticket. The
    linearization point is ``begin``: it increments the grant's active
    operation count while holding the store lock. ``revoke`` closes the same
    admission gate under that lock, so a mutation cannot start after
    revocation. The ticket remains active across an ``await`` without holding
    a threading lock; ``end`` releases the refcount when the adapter returns.
    """

    token_digest: str
    store: TaskHandoffGrantStore
    generation_at_acquisition: int
    _active: bool = False

    def begin(self) -> None:
        """Linearize and admit the protected operation, or fail closed."""
        if self._active:
            raise OperationPermitDenied("task handoff operation already active")
        if not self.store._begin_operation(
            self.token_digest, self.generation_at_acquisition
        ):
            raise OperationPermitDenied(
                "task handoff capability was revoked before the operation started"
            )
        self._active = True

    def end(self) -> None:
        """Release the operation refcount after the protected awaitable ends."""
        if not self._active:
            return
        self._active = False
        self.store._end_operation(self.token_digest)

    async def __aenter__(self) -> "OperationPermit":
        self.begin()
        return self

    async def __aexit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.end()

@dataclass(frozen=True)
class TaskHandoffGrant:
    """Server-owned authorization for one spawned worker session.

    Grants have a short wall-clock TTL (15 minutes) as a safety mechanism. The
    server-owned lease keeps the grant renewed while the worker is live; if the
    lease dies or the server restarts, the grant expires naturally. Expiry or
    explicit revocation both prevent reuse after termination.

    ``original_ttl_seconds`` is the TTL the grant was minted with. Heartbeat
    renewal (only from the server-side lease) uses this value as the default
    extension so a grant minted with a deliberately short TTL is not silently
    widened to the module default. Operators who configure a short-lived
    capability retain that bound across the entire session.

    ``operation_permit_generation`` is incremented when the grant is revoked.
    An OperationPermit holds the generation number at acquisition time. Before
    performing tracker mutations, the permit checks its generation matches
    the current grant; if not, the grant was revoked mid-operation and the
    mutation must abort.
    """

    token_digest: str
    project_id: str
    task_identifier: str
    allowed_actions: FrozenSet[str]
    expires_at: float
    owner_id: str | None = None
    revoked_at: float | None = None  # Explicit revocation timestamp
    original_ttl_seconds: float = DEFAULT_TTL_SECONDS
    operation_permit_generation: int = 0  # Incremented on revocation


class TaskHandoffGrantStore:
    """In-memory capability registry with constant-time token lookup.

    Provides linearizable operation authorization: a permit acquired after
    validation remains valid only until revoke() invalidates it. This prevents
    tracker mutations from racing with termination-triggered revocation.
    """

    def __init__(self, *, now=time.time):
        self._now = now
        self._lock = threading.Lock()
        self._grants: dict[str, TaskHandoffGrant] = {}
        self._operations: dict[str, _OperationState] = {}
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
        # The capability is intentionally returned to the subprocess, but
        # any parent-side event, exception, or telemetry text containing it
        # must be redacted even without a token-shaped label around it.
        from oompah.secrets import (
            SECRET_REDACTION_GRACE_SECONDS,
            register_secret,
        )

        register_secret(
            token,
            # Keep a bounded grace period after grant expiry for delayed
            # worker shutdown/error events without retaining every historical
            # handoff capability forever.
            expires_in=ttl + SECRET_REDACTION_GRACE_SECONDS,
        )
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

        Marks the grant as revoked to prevent reuse after termination and
        increments the operation permit generation to invalidate any permits
        that were acquired before this revocation. This ensures that even if
        a tracker mutation started between validation and revocation, it will
        detect the revocation before proceeding.
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
                # Increment operation_permit_generation to invalidate any
                # permits acquired before revocation.
                revoked_grant = TaskHandoffGrant(
                    token_digest=grant.token_digest,
                    project_id=grant.project_id,
                    task_identifier=grant.task_identifier,
                    allowed_actions=grant.allowed_actions,
                    expires_at=now + 10.0,  # Short grace period
                    owner_id=grant.owner_id,
                    revoked_at=now,
                    original_ttl_seconds=grant.original_ttl_seconds,
                    operation_permit_generation=grant.operation_permit_generation + 1,
                )
                self._grants[digest] = revoked_grant
            lease = self._leases.pop(digest, None)
            self._failures.pop(digest, None)
        if lease is not None:
            lease.stop()
        # Keep delayed shutdown/error events safe without retaining every
        # revoked bearer for the original grant lifetime.  The redaction
        # registry consumes the value only to register its digest-independent
        # literal; this path never logs or returns the token.  The module-
        # level ``retire_secret`` binding is used deliberately so tests can
        # patch ``oompah.task_handoff.retire_secret`` to observe the call;
        # the grace value is looked up on ``oompah.secrets`` at call time so
        # ``monkeypatch.setattr(secrets_module, "SECRET_REDACTION_GRACE_SECONDS", ...)``
        # is honored even after this module has cached the initial import.
        import oompah.secrets as _secrets_module

        retire_secret(
            token,
            grace_seconds=getattr(
                _secrets_module,
                "SECRET_REDACTION_GRACE_SECONDS",
                SECRET_REDACTION_GRACE_SECONDS,
            ),
        )

    def record_failure(self, token: str | None, reason: str) -> None:
        """Remember an actionable failure without retaining the bearer token.

        Informational policy denials, such as a verified worker's read-only
        exploration of another task, must not call this method. The exit
        reconciler consumes this registry specifically as evidence that the
        assigned task's handoff could not be completed.
        """
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

    def _begin_operation(self, token_digest: str, generation: int) -> bool:
        """Atomically admit one mutation before its first awaited I/O."""
        now = float(self._now())
        with self._lock:
            grant = self._grants.get(token_digest)
            if (
                grant is None
                or grant.revoked_at is not None
                or grant.expires_at <= now
                or grant.operation_permit_generation != generation
            ):
                return False
            state = self._operations.setdefault(token_digest, _OperationState())
            state.active += 1
            return True

    def _end_operation(self, token_digest: str) -> None:
        """Release one admitted mutation without retaining bearer material."""
        with self._lock:
            state = self._operations.get(token_digest)
            if state is None:
                return
            state.active = max(0, state.active - 1)
            if state.active == 0 and token_digest not in self._grants:
                self._operations.pop(token_digest, None)

    def current_grant_ttl(self, token: str | None) -> float | None:
        """Return the active grant's bounded renewal TTL without exposing it.

        The server-owned lease uses the original minted TTL for both grant
        renewal and secret-redaction retention.  A missing, revoked, or
        expired grant has no TTL to retain.
        """
        if not token:
            return None
        digest = self._digest(token)
        now = float(self._now())
        with self._lock:
            grant = self._grants.get(digest)
            if (
                grant is None
                or grant.revoked_at is not None
                or grant.expires_at <= now
            ):
                return None
            return float(grant.original_ttl_seconds)

    def acquire_permit(
        self,
        token: str | None,
        *,
        project_id: str,
        task_identifier: str,
        action: str,
    ) -> OperationPermit | None:
        """Acquire an operation permit after successful validation.

        Returns a permit if the token is valid and scope matches. The permit
        must be entered as an async context manager around exactly one
        tracker mutation; admission then remains active across awaited I/O.

        This is called AFTER validate() succeeds and should only fail if the
        grant was just revoked or expired in the narrow window between
        validation and permit acquisition.
        """
        if not isinstance(token, str) or not token:
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
            # Quick scope check (revalidate project/task/action)
            if not hmac.compare_digest(grant.project_id, str(project_id or "")):
                return None
            if not hmac.compare_digest(
                grant.task_identifier, str(task_identifier or "")
            ):
                return None
            if action not in grant.allowed_actions:
                return None
            # Capture current generation so permit can detect revocation
            generation = grant.operation_permit_generation
        return OperationPermit(
            token_digest=digest,
            store=self,
            generation_at_acquisition=generation,
        )

    def refresh(
        self,
        token: str | None,
        *,
        ttl_seconds: float | None = None,
        owner_id: str | None = None,
    ) -> bool:
        """Extend the TTL of an active grant (heartbeat-based renewal).

        Called by the server-owned lease to keep the grant alive during long
        tool calls and restart recovery. When
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
            # Renewal is a server-owned lease operation, never a bearer-only
            # request. An owner identity is mandatory and must match the
            # identity bound when the grant was minted.
            if owner_id is None or grant.owner_id != str(owner_id):
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
                operation_permit_generation=grant.operation_permit_generation,
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
            if grant.owner_id is None or owner_id is None:
                return None
            if grant.owner_id != str(owner_id):
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
            state = self._operations.get(digest)
            if state is None or state.active == 0:
                self._operations.pop(digest, None)


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
        current_grant_ttl = self._store.current_grant_ttl(self._token)
        if current_grant_ttl is None:
            return False
        if not self._store.refresh(self._token, owner_id=self._owner_id):
            return False
        renew_secret(
            self._token,
            expires_in=current_grant_ttl + SECRET_REDACTION_GRACE_SECONDS,
        )
        return True

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
    """Record an actionable handoff failure for exit reconciliation.

    Callers must leave intentional policy denials out of this registry; they
    are informational auth-health events rather than failures of the worker's
    assigned task.
    """
    _default_store.record_failure(token, reason)


def consume_task_handoff_failure(token: str | None) -> str | None:
    """Consume an operation failure for the orchestrator's exit reconciler."""
    return _default_store.consume_failure(token)


def acquire_task_handoff_permit(
    token: str | None,
    *,
    project_id: str,
    task_identifier: str,
    action: str,
) -> OperationPermit | None:
    """Acquire a permit whose async context admits one tracker mutation.

    Call this AFTER validate_task_handoff_token() succeeds. The endpoint must
    use the returned permit as an async context manager around the actual
    mutation; ``async with permit`` is the linearizable admission point.
    """
    return _default_store.acquire_permit(
        token,
        project_id=project_id,
        task_identifier=task_identifier,
        action=action,
    )


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
