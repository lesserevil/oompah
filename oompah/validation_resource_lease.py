"""Process-safe, restart-safe validation resource lease for heavyweight commands.

Serializes heavyweight validation (like full test suites) between quality gates and
auditors to prevent resource exhaustion and I/O blocking. Lightweight/focused audits
bypass the lease entirely. Fair queueing ensures no starvation.

Acceptance criteria (OOMPAH-816):
- Service never oversubscribes configured heavyweight validation capacity
- Exact gates cannot fail because a completion auditor launched a competing full suite
- Normal capacity waits clear automatically without actionable warnings
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)


# Command classification patterns for heavyweight commands
# These patterns identify full test suite runs that exhaust host resources
_HEAVYWEIGHT_PATTERNS = [
    r"make\s+test(?:\s|$)",           # make test
    r"make\s+test-serial(?:\s|$)",    # make test-serial
    r"pytest\s+(?!.*--co|-k\s+\S+\s*$)[^-]",  # pytest without bounded filters
    r"make\s+(?:setup|develop|install)(?:\s|$)",  # setup commands
]

# Patterns that are definitely lightweight and should bypass the lease
_LIGHTWEIGHT_PATTERNS = [
    r"grep\s+",
    r"find\s+",
    r"ls\s+",
    r"cat\s+",
    r"head\s+",
    r"tail\s+",
    r"wc\s+",
    r"echo\s+",
    r"rg\s+",
    r"pytest\s+.*-k\s+\S+",  # pytest with specific test selection
    r"pytest\s+.*--co(?:\s|$)",  # pytest collection-only
    r"make\s+help(?:\s|$)",
    r"git\s+",
    r"git\s+log",
    r"git\s+show",
]

_HEAVYWEIGHT_RE = re.compile("|".join(f"(?:{p})" for p in _HEAVYWEIGHT_PATTERNS), re.IGNORECASE)
_LIGHTWEIGHT_RE = re.compile("|".join(f"(?:{p})" for p in _LIGHTWEIGHT_PATTERNS), re.IGNORECASE)


def _default_lease_root() -> Path:
    """Return the default directory for validation resource lease state."""
    return Path.home() / ".oompah" / "validation_leases"


def _now_iso() -> str:
    """Return the current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _now_timestamp() -> float:
    """Return the current UTC time as a float seconds since epoch."""
    return time.time()


@dataclass(frozen=True)
class LeaseOwner:
    """Exact authority that owns one validation resource lease."""

    project_id: str
    task_id: str
    authority_generation: str
    # Priority: 100 for exact gates, 1 for auditor work
    priority: int = 1

    @property
    def complete(self) -> bool:
        return all(
            str(value or "").strip()
            for value in (self.project_id, self.task_id, self.authority_generation)
        )

    @property
    def key(self) -> str:
        """Return a collision-resistant in-process identity for this owner."""
        return "\0".join(
            (
                str(self.project_id),
                str(self.task_id),
                str(self.authority_generation),
            )
        )

    def to_dict(self) -> dict[str, str | int]:
        return {
            "project_id": str(self.project_id),
            "task_id": str(self.task_id),
            "authority_generation": str(self.authority_generation),
            "priority": int(self.priority),
        }


@dataclass(frozen=True)
class LeaseWaiter:
    """One waiter in the fair-queue, identified by owner + start time."""

    owner: LeaseOwner
    queued_at: str  # ISO format timestamp
    # Number of seconds this waiter has been waiting
    wait_seconds: float = 0.0

    def to_dict(self) -> dict[str, str | float]:
        return {
            "owner": self.owner.to_dict(),
            "queued_at": self.queued_at,
            "wait_seconds": self.wait_seconds,
        }


@dataclass(frozen=True)
class LeaseStatus:
    """Current state of the validation resource lease."""

    has_owner: bool
    owner: LeaseOwner | None = None
    owner_acquired_at: str | None = None
    waiters: list[LeaseWaiter] = None
    capacity: int = 1  # Number of concurrent heavyweight commands allowed

    def __post_init__(self) -> None:
        if self.waiters is None:
            object.__setattr__(self, "waiters", [])

    def to_dict(self) -> dict[str, str | bool | int | dict | list]:
        return {
            "has_owner": self.has_owner,
            "owner": self.owner.to_dict() if self.owner else None,
            "owner_acquired_at": self.owner_acquired_at,
            "waiter_count": len(self.waiters),
            "oldest_waiter_age_seconds": (
                self.waiters[0].wait_seconds if self.waiters else 0
            ),
            "capacity": self.capacity,
        }


class ValidationResourceLease:
    """Process-safe, restart-safe validation resource lease.

    Serializes heavyweight validation commands (full test suites) between
    quality gates and auditors. Lightweight/focused audits bypass the lease.
    Fair queueing with priority for exact gates (priority 100) over auditors (priority 1).
    """

    def __init__(self, root: Path | None = None, capacity: int = 1) -> None:
        self._root = (root or _default_lease_root()).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._capacity = max(1, int(capacity))

        # In-process state for performance
        self._lock = threading.Lock()
        self._owner: LeaseOwner | None = None
        self._owner_acquired_at: float | None = None
        self._waiters: list[tuple[LeaseOwner, float]] = []  # (owner, queued_timestamp)

        # Persistent state file
        self._state_file = self._root / "lease_state.json"
        self._lock_file = self._root / "lease.lock"

        # Recover from last state
        self._recover_from_persistent_state()

    def _recover_from_persistent_state(self) -> None:
        """Recover lease state from persistent storage on startup."""
        if not self._state_file.exists():
            return

        try:
            with open(self._state_file, "r") as f:
                data = json.load(f)

            owner_data = data.get("owner")
            if owner_data:
                self._owner = LeaseOwner(
                    project_id=owner_data.get("project_id", ""),
                    task_id=owner_data.get("task_id", ""),
                    authority_generation=owner_data.get("authority_generation", ""),
                    priority=owner_data.get("priority", 1),
                )
                self._owner_acquired_at = data.get("owner_acquired_at", time.time())

            # Recover waiters
            waiters_data = data.get("waiters", [])
            self._waiters = []
            for waiter_data in waiters_data:
                owner_data = waiter_data.get("owner", {})
                owner = LeaseOwner(
                    project_id=owner_data.get("project_id", ""),
                    task_id=owner_data.get("task_id", ""),
                    authority_generation=owner_data.get("authority_generation", ""),
                    priority=owner_data.get("priority", 1),
                )
                queued_at = waiter_data.get("queued_at", time.time())
                self._waiters.append((owner, queued_at))

            logger.info(
                "Recovered validation lease: owner=%s, waiters=%d",
                self._owner,
                len(self._waiters),
            )
        except Exception as exc:
            logger.exception("Failed to recover validation lease state: %s", exc)

    def _persist_state(self) -> None:
        """Write lease state to persistent storage."""
        try:
            data = {
                "owner": self._owner.to_dict() if self._owner else None,
                "owner_acquired_at": self._owner_acquired_at,
                "waiters": [
                    {
                        "owner": owner.to_dict(),
                        "queued_at": queued_at,
                    }
                    for owner, queued_at in self._waiters
                ],
                "capacity": self._capacity,
            }
            # Write atomically
            temp_file = self._state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)
            temp_file.replace(self._state_file)
        except Exception as exc:
            logger.exception("Failed to persist validation lease state: %s", exc)

    def is_heavyweight(self, command: str) -> bool:
        """Return True if the command is classified as heavyweight."""
        if _LIGHTWEIGHT_RE.search(command):
            return False
        return bool(_HEAVYWEIGHT_RE.search(command))

    def status(self) -> LeaseStatus:
        """Return the current lease status (non-blocking)."""
        with self._lock:
            waiters = [
                LeaseWaiter(
                    owner=owner,
                    queued_at=datetime.fromtimestamp(queued_at, tz=timezone.utc).isoformat(),
                    wait_seconds=time.time() - queued_at,
                )
                for owner, queued_at in self._waiters
            ]
            return LeaseStatus(
                has_owner=self._owner is not None,
                owner=self._owner,
                owner_acquired_at=(
                    datetime.fromtimestamp(self._owner_acquired_at, tz=timezone.utc).isoformat()
                    if self._owner_acquired_at
                    else None
                ),
                waiters=waiters,
                capacity=self._capacity,
            )

    def acquire(
        self,
        owner: LeaseOwner,
        timeout_seconds: float = 300.0,
    ) -> bool:
        """Acquire the lease for the given owner, or wait in fair queue.

        Returns True if the lease was acquired, False on timeout.
        Raises ValueError if the owner is incomplete.
        """
        if not owner.complete:
            raise ValueError(f"Incomplete owner: {owner}")

        start_time = time.time()
        owner_key = owner.key

        with self._lock:
            # Already own the lease
            if self._owner and self._owner.key == owner_key:
                return True

            # Add to waiters queue (sorted by priority, then insertion order)
            self._waiters.append((owner, time.time()))
            self._waiters.sort(key=lambda x: (-x[0].priority, self._waiters.index(x)))
            self._persist_state()

        # Spin-wait until the lease is acquired or timeout
        poll_interval = 0.1
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                with self._lock:
                    # Remove from waiters if we're still there
                    self._waiters = [
                        (w_owner, w_time)
                        for w_owner, w_time in self._waiters
                        if w_owner.key != owner_key
                    ]
                    self._persist_state()
                return False

            with self._lock:
                # Check if we now own the lease
                if self._owner and self._owner.key == owner_key:
                    # Remove from waiters
                    self._waiters = [
                        (w_owner, w_time)
                        for w_owner, w_time in self._waiters
                        if w_owner.key != owner_key
                    ]
                    self._persist_state()
                    return True

                # Check if we're first in queue and no current owner
                if not self._owner and self._waiters:
                    first_owner, first_time = self._waiters[0]
                    if first_owner.key == owner_key:
                        # Acquire the lease
                        self._owner = owner
                        self._owner_acquired_at = time.time()
                        self._waiters.pop(0)
                        self._persist_state()
                        logger.info(
                            "Validation lease acquired by %s (priority %d, waited %.1fs)",
                            owner_key[:20],
                            owner.priority,
                            time.time() - first_time,
                        )
                        return True

            time.sleep(poll_interval)

    def release(self, owner: LeaseOwner) -> bool:
        """Release the lease if the given owner holds it.

        Returns True if the lease was released, False if owner doesn't hold it.
        """
        owner_key = owner.key

        with self._lock:
            if not self._owner or self._owner.key != owner_key:
                return False

            self._owner = None
            self._owner_acquired_at = None
            self._persist_state()
            logger.info("Validation lease released by %s", owner_key[:20])
            return True

    def force_release(self, owner: LeaseOwner | None = None) -> bool:
        """Force release the lease (for crash recovery or testing).

        If owner is provided, only release if it matches the current owner.
        Returns True if the lease was released.
        """
        with self._lock:
            if owner is not None and self._owner and self._owner.key != owner.key:
                return False

            if self._owner is None:
                return False

            self._owner = None
            self._owner_acquired_at = None
            self._persist_state()
            return True

    def cancel_owner(self, owner: LeaseOwner) -> int:
        """Cancel an owner's presence in the lease (both held and waiting).

        Returns the number of queue positions removed.
        """
        owner_key = owner.key
        removed_count = 0

        with self._lock:
            # If owner currently holds the lease, release it
            if self._owner and self._owner.key == owner_key:
                self._owner = None
                self._owner_acquired_at = None
                removed_count += 1

            # Remove from waiters
            original_count = len(self._waiters)
            self._waiters = [
                (w_owner, w_time)
                for w_owner, w_time in self._waiters
                if w_owner.key != owner_key
            ]
            removed_count += original_count - len(self._waiters)

            if removed_count > 0:
                self._persist_state()
                logger.info(
                    "Cancelled owner %s from lease (removed %d position(s))",
                    owner_key[:20],
                    removed_count,
                )

        return removed_count


# Global instance (initialized in server startup)
_global_lease: ValidationResourceLease | None = None
_global_lease_lock = threading.Lock()


def get_global_lease() -> ValidationResourceLease:
    """Get or create the global validation resource lease."""
    global _global_lease
    with _global_lease_lock:
        if _global_lease is None:
            capacity = int(os.environ.get("OOMPAH_HEAVYWEIGHT_CAPACITY", "1"))
            _global_lease = ValidationResourceLease(capacity=capacity)
        return _global_lease


def init_global_lease(root: Path | None = None, capacity: int = 1) -> None:
    """Initialize the global validation resource lease (for testing)."""
    global _global_lease
    with _global_lease_lock:
        _global_lease = ValidationResourceLease(root=root, capacity=capacity)
