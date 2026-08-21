"""Durable per-project review-capacity reservations.

The forge is the authority for reviews which already exist.  This store fills
the small but important gap between the capacity check and the forge create
call: a reservation is acquired atomically before creation and committed to
the resulting review identity afterwards.  Uncommitted reservations expire so
an interrupted create does not permanently consume capacity; committed
reservations remain durable until the review is observed closed/merged or an
explicit release arrives.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
import fcntl
import os
import sqlite3
import threading
import time
from typing import Iterable, Iterator


REVIEW_CAPACITY_SCHEMA_VERSION = 2
DEFAULT_REVIEW_RESERVATION_TTL_SECONDS = 15 * 60
_INITIALIZE_LOCK = threading.Lock()


@contextlib.contextmanager
def _bootstrap_lock(path: str) -> Iterator[None]:
    """Serialize connection bootstrap before the transactional migration."""

    lock_path = f"{path}.initialize.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


@dataclass(frozen=True)
class ReviewCapacityReservation:
    reservation_id: str
    project_id: str
    task_id: str
    source_branch: str
    target_branch: str
    review_id: str | None
    acquired_at: float
    lease_expires_at: float | None
    authority_generation: str | None = None
    head_sha: str | None = None
    # True only for the caller that inserted the reservation.  A competing
    # sweep may observe the existing row; it must defer instead of treating
    # that observation as permission to call the forge create API again.
    acquired_new: bool = False


_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS review_capacity_reservations (
    reservation_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    source_branch TEXT NOT NULL,
    target_branch TEXT NOT NULL,
    review_id TEXT,
    authority_generation TEXT,
    head_sha TEXT,
    acquired_at REAL NOT NULL,
    lease_expires_at REAL,
    released_at REAL
);
CREATE INDEX IF NOT EXISTS review_capacity_project_idx
    ON review_capacity_reservations(project_id, released_at, lease_expires_at);
CREATE UNIQUE INDEX IF NOT EXISTS review_capacity_active_task_idx
    ON review_capacity_reservations(project_id, task_id)
    WHERE released_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS review_capacity_active_branch_idx
    ON review_capacity_reservations(project_id, source_branch, target_branch)
    WHERE released_at IS NULL;
"""


class ReviewCapacityStore:
    """SQLite-backed review reservations with compare-and-swap acquisition."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=10,
        )
        self._conn.row_factory = sqlite3.Row
        with _INITIALIZE_LOCK, self._lock:
            self._conn.execute("PRAGMA busy_timeout=10000")
            # journal_mode and executescript can fail immediately with
            # SQLITE_BUSY when two newly spawned service processes bootstrap
            # the same file, before BEGIN IMMEDIATE's busy timeout has a chance
            # to serialize the real migration.  Fence only this bootstrap
            # phase; release it before _migrate_schema so the transactional
            # migration remains the cross-process authority.
            with _bootstrap_lock(self.path):
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.executescript(_SCHEMA)
            self._migrate_schema()

    def _migrate_schema(self) -> None:
        """Upgrade the reservation schema under a cross-process write lock."""

        # The process-local lock prevents duplicate initialization by this
        # store instance, but deployments can briefly have two service
        # processes during a graceful restart.  Serialize the column recheck
        # and ALTER statements through SQLite as one write transaction so both
        # processes cannot observe the v1 schema and then race the same ADD
        # COLUMN.
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            columns = {
                str(row[1])
                for row in self._conn.execute(
                    "PRAGMA table_info(review_capacity_reservations)"
                ).fetchall()
            }
            if "authority_generation" not in columns:
                self._conn.execute(
                    "ALTER TABLE review_capacity_reservations "
                    "ADD COLUMN authority_generation TEXT"
                )
            if "head_sha" not in columns:
                self._conn.execute(
                    "ALTER TABLE review_capacity_reservations "
                    "ADD COLUMN head_sha TEXT"
                )
            self._conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)",
                ("version", str(REVIEW_CAPACITY_SCHEMA_VERSION)),
            )
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _ensure_conn(self) -> None:
        """Re-open the connection if it was closed, preventing 'closed database' errors.
        
        This handles the race condition where an orchestrator is replaced and the
        old store may be garbage collected while API threads still hold references
        to it and try to access it.
        """
        try:
            # Test if the connection is alive by executing a simple query
            self._conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            # Connection is closed, re-open it
            self._conn = sqlite3.connect(
                self.path,
                check_same_thread=False,
                timeout=10,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA busy_timeout=10000")
            self._conn.execute("PRAGMA journal_mode=WAL")

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ReviewCapacityReservation:
        return ReviewCapacityReservation(
            reservation_id=str(row["reservation_id"]),
            project_id=str(row["project_id"]),
            task_id=str(row["task_id"]),
            source_branch=str(row["source_branch"]),
            target_branch=str(row["target_branch"]),
            review_id=(str(row["review_id"]) if row["review_id"] else None),
            acquired_at=float(row["acquired_at"]),
            lease_expires_at=(
                float(row["lease_expires_at"])
                if row["lease_expires_at"] is not None
                else None
            ),
            authority_generation=(
                str(row["authority_generation"])
                if row["authority_generation"]
                else None
            ),
            head_sha=(str(row["head_sha"]) if row["head_sha"] else None),
        )

    @staticmethod
    def _review_keys(review_ids: Iterable[str] | None) -> set[str]:
        return {
            str(review_id).strip()
            for review_id in (review_ids or ())
            if str(review_id).strip()
        }

    def _drop_expired_uncommitted(self, now: float) -> None:
        self._conn.execute(
            """
            UPDATE review_capacity_reservations
               SET released_at = ?
             WHERE released_at IS NULL
               AND review_id IS NULL
               AND lease_expires_at IS NOT NULL
               AND lease_expires_at <= ?
            """,
            (now, now),
        )

    def _active_rows(self, project_id: str, now: float) -> list[sqlite3.Row]:
        return list(
            self._conn.execute(
                """
                SELECT *
                  FROM review_capacity_reservations
                 WHERE project_id = ?
                   AND released_at IS NULL
                   AND (review_id IS NOT NULL OR lease_expires_at > ?)
                """,
                (str(project_id), now),
            ).fetchall()
        )

    @staticmethod
    def _occupied_count(
        rows: Iterable[sqlite3.Row],
        open_review_ids: set[str],
    ) -> int:
        """Count forge reviews and reservations without double-counting commits."""
        occupied_review_ids = set(open_review_ids)
        count = len(occupied_review_ids)
        for row in rows:
            review_id = str(row["review_id"] or "").strip()
            if review_id and review_id in occupied_review_ids:
                continue
            count += 1
            if review_id:
                occupied_review_ids.add(review_id)
        return count

    def count(self, project_id: str, open_review_ids: Iterable[str] | None = None) -> int:
        """Return forge-open reviews plus active durable reservations."""
        now = time.time()
        with self._lock:
            self._drop_expired_uncommitted(now)
            rows = self._active_rows(str(project_id), now)
            count = self._occupied_count(rows, self._review_keys(open_review_ids))
            self._conn.commit()
            return count

    def active(self, project_id: str) -> list[ReviewCapacityReservation]:
        """Return active reservations, primarily for reconciliation/diagnostics."""
        now = time.time()
        with self._lock:
            self._drop_expired_uncommitted(now)
            rows = self._active_rows(str(project_id), now)
            self._conn.commit()
            return [self._from_row(row) for row in rows]

    def acquire(
        self,
        *,
        project_id: str,
        task_id: str,
        source_branch: str,
        target_branch: str,
        limit: int,
        open_review_ids: Iterable[str] | None = None,
        reservation_id: str,
        lease_ttl_seconds: float = DEFAULT_REVIEW_RESERVATION_TTL_SECONDS,
        authority_generation: str | None = None,
        head_sha: str | None = None,
    ) -> ReviewCapacityReservation | None:
        """CAS-acquire one project slot, or return ``None`` at capacity.

        The immediate transaction serializes competing reconciliation sweeps,
        including sweeps running in separate service processes that share the
        same state directory.
        """
        project_id = str(project_id)
        task_id = str(task_id)
        source_branch = str(source_branch)
        target_branch = str(target_branch)
        now = time.time()
        open_ids = self._review_keys(open_review_ids)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._drop_expired_uncommitted(now)
                existing = self._conn.execute(
                    """
                    SELECT *
                      FROM review_capacity_reservations
                     WHERE project_id = ?
                       AND released_at IS NULL
                       AND (review_id IS NOT NULL OR lease_expires_at > ?)
                       AND (task_id = ? OR
                            (source_branch = ? AND target_branch = ?))
                     ORDER BY acquired_at
                     LIMIT 1
                    """,
                    (project_id, now, task_id, source_branch, target_branch),
                ).fetchone()
                if existing is not None:
                    self._conn.commit()
                    return self._from_row(existing)

                rows = self._active_rows(project_id, now)
                if self._occupied_count(rows, open_ids) >= max(1, int(limit)):
                    self._conn.rollback()
                    return None

                expires_at = now + max(1.0, float(lease_ttl_seconds))
                self._conn.execute(
                    """
                    INSERT INTO review_capacity_reservations(
                        reservation_id, project_id, task_id, source_branch,
                        target_branch, review_id, authority_generation,
                        head_sha, acquired_at,
                        lease_expires_at, released_at
                    ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, NULL)
                    """,
                    (
                        str(reservation_id), project_id, task_id,
                        source_branch, target_branch,
                        str(authority_generation or "").strip() or None,
                        str(head_sha or "").strip().lower() or None,
                        now, expires_at,
                    ),
                )
                self._conn.commit()
                return ReviewCapacityReservation(
                    reservation_id=str(reservation_id),
                    project_id=project_id,
                    task_id=task_id,
                    source_branch=source_branch,
                    target_branch=target_branch,
                    review_id=None,
                    acquired_at=now,
                    lease_expires_at=expires_at,
                    authority_generation=(
                        str(authority_generation or "").strip() or None
                    ),
                    head_sha=str(head_sha or "").strip().lower() or None,
                    acquired_new=True,
                )
            except Exception:
                self._conn.rollback()
                raise

    def commit(self, reservation_id: str, review_id: str) -> bool:
        """Commit a reservation to a forge review identity."""
        review_id = str(review_id or "").strip()
        if not review_id:
            return False
        with self._lock:
            cursor = self._conn.execute(
                """
                UPDATE review_capacity_reservations
                   SET review_id = ?, lease_expires_at = NULL
                 WHERE reservation_id = ?
                   AND released_at IS NULL
                """,
                (review_id, str(reservation_id)),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def adopt(
        self,
        *,
        project_id: str,
        task_id: str,
        source_branch: str,
        target_branch: str,
        review_id: str,
        reservation_id: str,
        authority_generation: str | None = None,
        head_sha: str | None = None,
    ) -> ReviewCapacityReservation:
        """Record an already-open forge review for future close/merge release."""
        project_id = str(project_id)
        task_id = str(task_id)
        source_branch = str(source_branch)
        target_branch = str(target_branch)
        review_id = str(review_id).strip()
        authority_generation = str(authority_generation or "").strip() or None
        head_sha = str(head_sha or "").strip().lower() or None
        now = time.time()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self._conn.execute(
                    """
                    SELECT *
                      FROM review_capacity_reservations
                     WHERE project_id = ?
                       AND released_at IS NULL
                       AND (review_id = ? OR task_id = ? OR
                            (source_branch = ? AND target_branch = ?))
                     ORDER BY acquired_at
                     LIMIT 1
                    """,
                    (project_id, review_id, task_id, source_branch, target_branch),
                ).fetchone()
                if existing is not None:
                    if (
                        not existing["review_id"]
                        or authority_generation is not None
                        or head_sha is not None
                    ):
                        self._conn.execute(
                            "UPDATE review_capacity_reservations "
                            "SET review_id = COALESCE(review_id, ?), "
                            "authority_generation = COALESCE(?, authority_generation), "
                            "head_sha = COALESCE(?, head_sha), "
                            "lease_expires_at = NULL "
                            "WHERE reservation_id = ?",
                            (
                                review_id,
                                authority_generation,
                                head_sha,
                                existing["reservation_id"],
                            ),
                        )
                        existing = self._conn.execute(
                            "SELECT * FROM review_capacity_reservations "
                            "WHERE reservation_id = ?",
                            (existing["reservation_id"],),
                        ).fetchone()
                    self._conn.commit()
                    return self._from_row(existing)

                self._conn.execute(
                    """
                    INSERT INTO review_capacity_reservations(
                        reservation_id, project_id, task_id, source_branch,
                        target_branch, review_id, authority_generation,
                        head_sha, acquired_at,
                        lease_expires_at, released_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                    """,
                    (
                        str(reservation_id), project_id, task_id,
                        source_branch, target_branch, review_id,
                        authority_generation, head_sha, now,
                    ),
                )
                self._conn.commit()
                return ReviewCapacityReservation(
                    reservation_id=str(reservation_id),
                    project_id=project_id,
                    task_id=task_id,
                    source_branch=source_branch,
                    target_branch=target_branch,
                    review_id=review_id,
                    acquired_at=now,
                    lease_expires_at=None,
                    authority_generation=authority_generation,
                    head_sha=head_sha,
                )
            except Exception:
                self._conn.rollback()
                raise

    def release(
        self,
        *,
        project_id: str,
        reservation_id: str | None = None,
        review_id: str | None = None,
        task_id: str | None = None,
        source_branch: str | None = None,
    ) -> int:
        """Release active reservations matching the supplied review identity."""
        clauses = ["project_id = ?", "released_at IS NULL"]
        args: list[object] = [str(project_id)]
        matchers: list[str] = []
        if reservation_id:
            matchers.append("reservation_id = ?")
            args.append(str(reservation_id))
        if review_id:
            matchers.append("review_id = ?")
            args.append(str(review_id).strip())
        if task_id:
            matchers.append("task_id = ?")
            args.append(str(task_id))
        if source_branch:
            matchers.append("source_branch = ?")
            args.append(str(source_branch))
        if not matchers:
            return 0
        clauses.append("(" + " OR ".join(matchers) + ")")
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE review_capacity_reservations SET released_at = ? "
                "WHERE " + " AND ".join(clauses),
                [time.time(), *args],
            )
            self._conn.commit()
            return int(cursor.rowcount)

    def reconcile_open_reviews(
        self,
        project_id: str,
        open_review_ids: Iterable[str],
        *,
        minimum_committed_age_seconds: float = 0.0,
    ) -> int:
        """Release sufficiently old committed rows absent from a live listing.

        Forge list endpoints may briefly lag a successful create response. The
        optional age fence prevents that stale-empty window from releasing a
        just-committed reservation and admitting a duplicate review.
        """
        ids = self._review_keys(open_review_ids)
        now = time.time()
        minimum_age = max(0.0, float(minimum_committed_age_seconds))
        released = 0
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._drop_expired_uncommitted(now)
                rows = self._conn.execute(
                    """
                    SELECT reservation_id, review_id, acquired_at
                      FROM review_capacity_reservations
                     WHERE project_id = ?
                       AND released_at IS NULL
                       AND review_id IS NOT NULL
                    """,
                    (str(project_id),),
                ).fetchall()
                for row in rows:
                    if (
                        str(row["review_id"]) not in ids
                        and now - float(row["acquired_at"]) >= minimum_age
                    ):
                        self._conn.execute(
                            "UPDATE review_capacity_reservations "
                            "SET released_at = ? WHERE reservation_id = ?",
                            (now, row["reservation_id"]),
                        )
                        released += 1
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return released
