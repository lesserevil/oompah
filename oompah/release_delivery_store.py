"""Release delivery ledger store (OOMPAH-193).

Implements the versioned ``.oompah/release-deliveries.yml`` ledger and the
:class:`ReleaseDeliveryStore` that provides atomic CRUD operations for
:class:`ReleaseDelivery` records.

This module intentionally does **not** read or write task YAML metadata.  It
is a standalone ledger store for project-owned delivery records that may or
may not have an associated source task or epic.

The lifecycle status vocabulary and valid transitions are reused from
:mod:`oompah.release_addendum_schema` (:class:`~oompah.release_addendum_schema.AddendumStatus`,
:data:`~oompah.release_addendum_schema.VALID_TRANSITIONS`,
:func:`~oompah.release_addendum_schema.is_valid_transition`) to maintain a
single source of truth for the lifecycle FSM.

Schema (version 1)
------------------

.. code-block:: yaml

    version: 1
    deliveries:
      - id: rd_01J...                 # non-empty string, immutable
        project_id: proj-123          # ownership check, immutable
        source_branch: main           # immutable
        source_kind: task             # task | epic | commits, immutable
        source_identifier: FOO-10     # null when source_kind=commits, immutable
        source_commits:               # full ordered 40-hex SHAs, immutable
          - 3c8c1d5fabc...
          - a4f0192e...
        target_branch: release/1.1    # immutable
        status: open                  # reuses AddendumStatus vocabulary
        queued_at: "2026-07-13T12:00:00Z"
        claimed_by: null
        lease_expires_at: null
        started_at: null
        completed_at: null
        work_branch: null
        pr_url: null
        pr_number: null
        result_commits: []
        error: null
        migrated_from: null

Immutable fields
----------------

``id``, ``project_id``, ``source_branch``, ``source_kind``,
``source_identifier``, ``source_commits``, and ``target_branch`` are set at
creation time and may **never** be changed by lifecycle updates.

Source-kind / source-identifier invariant
-----------------------------------------

When ``source_kind`` is ``task`` or ``epic``, ``source_identifier`` must be a
non-empty string.  When ``source_kind`` is ``commits``, ``source_identifier``
must be ``null``.

Full SHA format
---------------

Every entry in ``source_commits`` and ``result_commits`` must be exactly
40 lowercase hexadecimal characters.

Missing vs. malformed ledger
-----------------------------

A missing ledger file is treated as an empty version-1 ledger.  A malformed
ledger (YAML parse error, wrong version, invalid entries) raises
:class:`LedgerParseError` with an actionable message and is **never**
overwritten.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from oompah.release_addendum_schema import (
    AddendumStatus,
    InvalidTransitionError,
    is_valid_transition,
)
from oompah.tracker import TrackerError

_YAML_SAFE_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

#: Path to the ledger file, relative to the project root.
LEDGER_PATH = ".oompah/release-deliveries.yml"

#: Current ledger schema version.
LEDGER_VERSION = 1

#: Pattern that matches a full 40-character lowercase hex SHA.
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# ---------------------------------------------------------------------------
# Module-level project-level locks
# ---------------------------------------------------------------------------

_delivery_locks: dict[str, threading.RLock] = {}
_delivery_locks_guard = threading.Lock()


def _delivery_lock(project_id: str) -> threading.RLock:
    """Return the process-local reentrant write lock for *project_id*'s ledger.

    The lock is created lazily on first access and retained for the process
    lifetime.  Using a reentrant lock (``threading.RLock``) allows code that
    already holds the lock to re-enter without deadlock — the same pattern as
    :func:`oompah.release_addendum_queue._source_lock`.

    Args:
        project_id: Project identifier.

    Returns:
        Per-project :class:`threading.RLock`.
    """
    with _delivery_locks_guard:
        return _delivery_locks.setdefault(project_id, threading.RLock())


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class LedgerParseError(ValueError):
    """Raised when the ledger file exists but is malformed or has wrong version.

    Malformed ledgers are **never** overwritten — callers must repair or restore
    the file (e.g. with ``git show HEAD:.oompah/release-deliveries.yml``)
    before new writes are possible.
    """


class ImmutableFieldError(ValueError):
    """Raised when an attempt is made to change an immutable delivery field.

    Immutable fields (``id``, ``project_id``, ``source_branch``,
    ``source_kind``, ``source_identifier``, ``source_commits``,
    ``target_branch``) are set at creation time and cannot be modified by
    :meth:`ReleaseDeliveryStore.update`.
    """


class DeliveryNotFoundError(KeyError):
    """Raised when a delivery ID is not found in the ledger."""


# ---------------------------------------------------------------------------
# SourceKind enum
# ---------------------------------------------------------------------------


class SourceKind(str, Enum):
    """The kind of entity that originated this release delivery.

    Attributes:
        TASK: Delivery was triggered by a source task; ``source_identifier``
            holds the task ID.
        EPIC: Delivery was triggered by an epic; ``source_identifier`` holds
            the epic ID.
        COMMITS: Delivery was triggered by a direct commit selection;
            ``source_identifier`` must be ``null``.
    """

    TASK = "task"
    EPIC = "epic"
    COMMITS = "commits"

    @classmethod
    def from_raw(cls, raw: Any) -> "SourceKind":
        """Parse a raw value into a :class:`SourceKind`.

        Accepts the enum value string (case-insensitive).  Raises
        :class:`ValueError` for unrecognised or missing values.

        Args:
            raw: Raw value (string, :class:`SourceKind`, or ``None``).

        Returns:
            The matching :class:`SourceKind` member.

        Raises:
            ValueError: When *raw* is ``None``, empty, or does not match any
                known ``SourceKind`` value.
        """
        if isinstance(raw, cls):
            return raw
        if not raw:
            valid = ", ".join(m.value for m in cls)
            raise ValueError(
                f"SourceKind must not be empty, got {raw!r}; "
                f"must be one of: {valid}"
            )
        normalised = str(raw).strip().lower()
        try:
            return cls(normalised)
        except ValueError:
            valid = ", ".join(m.value for m in cls)
            raise ValueError(
                f"Unknown SourceKind {raw!r}; must be one of: {valid}"
            ) from None


# ---------------------------------------------------------------------------
# Immutable / mutable field sets
# ---------------------------------------------------------------------------

#: Fields that are set at creation time and may never be changed.
_IMMUTABLE_FIELDS: frozenset[str] = frozenset({
    "id",
    "project_id",
    "source_branch",
    "source_kind",
    "source_identifier",
    "source_commits",
    "target_branch",
})

#: Fields that may be updated by :meth:`ReleaseDeliveryStore.update`.
_MUTABLE_FIELDS: frozenset[str] = frozenset({
    "status",
    "queued_at",
    "claimed_by",
    "lease_expires_at",
    "started_at",
    "completed_at",
    "work_branch",
    "pr_url",
    "pr_number",
    "result_commits",
    "error",
    "migrated_from",
})


# ---------------------------------------------------------------------------
# ReleaseDelivery dataclass
# ---------------------------------------------------------------------------


@dataclass
class ReleaseDelivery:
    """One delivery record in the project-owned release delivery ledger.

    Source fields are set at creation time and are immutable.  Lifecycle and
    execution evidence fields may be updated by
    :meth:`ReleaseDeliveryStore.update`.

    Attributes:
        id: Stable unique delivery identifier (non-empty string; typically a
            ULID or similar, e.g. ``rd_01JXYZ...``); immutable.
        project_id: Project that owns this delivery; immutable.
        source_branch: Project default branch at creation time; immutable.
        source_kind: Origin of the delivery; immutable.
        source_identifier: Source task or epic ID when ``source_kind`` is
            ``task`` or ``epic``; ``None`` when ``source_kind`` is
            ``commits``; immutable.
        source_commits: Ordered full 40-hex SHA list to cherry-pick; immutable.
        target_branch: Target release branch name; immutable.
        status: Current lifecycle status (reuses
            :class:`~oompah.release_addendum_schema.AddendumStatus`).
        queued_at: ISO-8601 UTC timestamp when the delivery was created.
        claimed_by: Worker identity while ``in_progress`` (nullable).
        lease_expires_at: ISO-8601 UTC expiry of the in-progress lease
            (nullable).
        started_at: ISO-8601 UTC timestamp when a worker claimed the delivery
            (nullable).
        completed_at: ISO-8601 UTC timestamp when the delivery reached a
            terminal state (nullable).
        work_branch: Git branch created for the cherry-pick (nullable).
        pr_url: URL of the cherry-pick PR (nullable).
        pr_number: Number of the cherry-pick PR as string (nullable).
        result_commits: Full SHAs actually landed on the target branch
            (execution evidence; empty until after merge).
        error: Diagnostic message when ``blocked`` (nullable).
        migrated_from: Legacy addendum ID when this record was migrated from
            task-owned metadata (nullable).
    """

    # -- Immutable source fields --
    id: str
    project_id: str
    source_branch: str
    source_kind: SourceKind
    source_identifier: str | None
    source_commits: list[str]
    target_branch: str

    # -- Mutable lifecycle / evidence fields --
    status: AddendumStatus
    queued_at: str
    claimed_by: str | None = None
    lease_expires_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    work_branch: str | None = None
    pr_url: str | None = None
    pr_number: str | None = None
    result_commits: list[str] = field(default_factory=list)
    error: str | None = None
    migrated_from: str | None = None

    def to_raw(self) -> dict[str, Any]:
        """Serialise this delivery to a raw dict for YAML storage.

        All fields are included so the record is self-contained.  ``None``
        values for nullable fields and empty lists are preserved so the YAML
        representation is stable across round-trips.

        Returns:
            Dict suitable for inclusion in the ``deliveries`` list.
        """
        return {
            "id": self.id,
            "project_id": self.project_id,
            "source_branch": self.source_branch,
            "source_kind": self.source_kind.value,
            "source_identifier": self.source_identifier,
            "source_commits": list(self.source_commits),
            "target_branch": self.target_branch,
            "status": self.status.value,
            "queued_at": self.queued_at,
            "claimed_by": self.claimed_by,
            "lease_expires_at": self.lease_expires_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "work_branch": self.work_branch,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "result_commits": list(self.result_commits),
            "error": self.error,
            "migrated_from": self.migrated_from,
        }

    @classmethod
    def from_raw(cls, raw: Any) -> "ReleaseDelivery":
        """Parse a raw dict into a :class:`ReleaseDelivery`.

        Validates required fields, full SHA format, enum values, and the
        source-kind / source-identifier invariant.

        Args:
            raw: Raw dict (one element of the ``deliveries`` list).

        Returns:
            Parsed :class:`ReleaseDelivery`.

        Raises:
            ValueError: When *raw* is not a dict, required fields are missing
                or invalid, SHA format is incorrect, or the
                source-kind/source-identifier invariant is violated.
        """
        if not isinstance(raw, dict):
            raise ValueError(
                f"ReleaseDelivery entry must be a dict, got "
                f"{type(raw).__name__!r}: {raw!r}"
            )

        # -- id --
        delivery_id = str(raw.get("id") or "").strip()
        if not delivery_id:
            raise ValueError(
                f"ReleaseDelivery missing required 'id': {raw!r}"
            )

        # -- project_id --
        project_id = str(raw.get("project_id") or "").strip()
        if not project_id:
            raise ValueError(
                f"ReleaseDelivery {delivery_id!r} missing required 'project_id': {raw!r}"
            )

        # -- source_branch --
        source_branch = str(raw.get("source_branch") or "").strip()
        if not source_branch:
            raise ValueError(
                f"ReleaseDelivery {delivery_id!r} missing required 'source_branch': {raw!r}"
            )

        # -- source_kind --
        source_kind = SourceKind.from_raw(raw.get("source_kind"))

        # -- source_identifier (with source-kind invariant check) --
        raw_source_id = raw.get("source_identifier")
        source_identifier: str | None = None
        if raw_source_id is not None:
            stripped = str(raw_source_id).strip()
            source_identifier = stripped if stripped else None

        if source_kind in (SourceKind.TASK, SourceKind.EPIC):
            if not source_identifier:
                raise ValueError(
                    f"ReleaseDelivery {delivery_id!r}: 'source_identifier' is required "
                    f"when source_kind={source_kind.value!r}: {raw!r}"
                )
        elif source_kind is SourceKind.COMMITS:
            if source_identifier is not None:
                raise ValueError(
                    f"ReleaseDelivery {delivery_id!r}: 'source_identifier' must be null "
                    f"when source_kind='commits', got {source_identifier!r}: {raw!r}"
                )

        # -- source_commits: required, nonempty, full SHA format --
        raw_commits = raw.get("source_commits")
        if not raw_commits:
            raise ValueError(
                f"ReleaseDelivery {delivery_id!r}: 'source_commits' must be a "
                f"nonempty list: {raw!r}"
            )
        if isinstance(raw_commits, str):
            raw_commits = [raw_commits]
        source_commits = [str(c).strip() for c in raw_commits if str(c).strip()]
        if not source_commits:
            raise ValueError(
                f"ReleaseDelivery {delivery_id!r}: 'source_commits' must contain "
                f"nonempty SHA strings: {raw!r}"
            )
        for sha in source_commits:
            _validate_full_sha(sha, f"ReleaseDelivery {delivery_id!r} source_commits")

        # -- target_branch --
        target_branch = str(raw.get("target_branch") or "").strip()
        if not target_branch:
            raise ValueError(
                f"ReleaseDelivery {delivery_id!r} missing required 'target_branch': {raw!r}"
            )

        # -- status --
        status = AddendumStatus.from_raw(raw.get("status"))

        # -- queued_at --
        queued_at = str(raw.get("queued_at") or "").strip()
        if not queued_at:
            raise ValueError(
                f"ReleaseDelivery {delivery_id!r} missing required 'queued_at': {raw!r}"
            )

        # -- Nullable string fields helper --
        def _opt_str(key: str) -> str | None:
            v = raw.get(key)
            if v is None:
                return None
            s = str(v).strip()
            return s if s else None

        # -- result_commits: optional, full SHA format --
        raw_result = raw.get("result_commits") or []
        if isinstance(raw_result, str):
            raw_result = [raw_result]
        result_commits = [str(c).strip() for c in raw_result if str(c).strip()]
        for sha in result_commits:
            _validate_full_sha(sha, f"ReleaseDelivery {delivery_id!r} result_commits")

        return cls(
            id=delivery_id,
            project_id=project_id,
            source_branch=source_branch,
            source_kind=source_kind,
            source_identifier=source_identifier,
            source_commits=source_commits,
            target_branch=target_branch,
            status=status,
            queued_at=queued_at,
            claimed_by=_opt_str("claimed_by"),
            lease_expires_at=_opt_str("lease_expires_at"),
            started_at=_opt_str("started_at"),
            completed_at=_opt_str("completed_at"),
            work_branch=_opt_str("work_branch"),
            pr_url=_opt_str("pr_url"),
            pr_number=_opt_str("pr_number"),
            result_commits=result_commits,
            error=_opt_str("error"),
            migrated_from=_opt_str("migrated_from"),
        )


# ---------------------------------------------------------------------------
# ReleaseDeliveryLedger
# ---------------------------------------------------------------------------


@dataclass
class ReleaseDeliveryLedger:
    """The versioned project-owned release delivery ledger.

    Attributes:
        version: Schema version number; must equal :data:`LEDGER_VERSION`.
        deliveries: Ordered list of :class:`ReleaseDelivery` records.
    """

    version: int
    deliveries: list[ReleaseDelivery]

    @classmethod
    def empty(cls) -> "ReleaseDeliveryLedger":
        """Return an empty version-1 ledger.

        Used when the ledger file does not yet exist.

        Returns:
            A fresh :class:`ReleaseDeliveryLedger` with no deliveries.
        """
        return cls(version=LEDGER_VERSION, deliveries=[])

    def to_raw(self) -> dict[str, Any]:
        """Serialise the ledger to a raw dict for YAML storage.

        Returns:
            Dict with ``version`` and ``deliveries`` keys.
        """
        return {
            "version": self.version,
            "deliveries": [d.to_raw() for d in self.deliveries],
        }

    @classmethod
    def from_raw(cls, raw: Any) -> "ReleaseDeliveryLedger":
        """Parse a raw dict (from YAML load) into a :class:`ReleaseDeliveryLedger`.

        Args:
            raw: Raw dict from YAML.

        Returns:
            Parsed :class:`ReleaseDeliveryLedger`.

        Raises:
            LedgerParseError: When *raw* is not a dict, the version field is
                missing or wrong, or a delivery entry is malformed.
        """
        _RESTORE_HINT = (
            "Restore the file from git history: "
            f"git show HEAD:{LEDGER_PATH}"
        )

        if not isinstance(raw, dict):
            raise LedgerParseError(
                f"Ledger root must be a mapping, got {type(raw).__name__!r}. "
                + _RESTORE_HINT
            )

        # -- version --
        raw_version = raw.get("version")
        if raw_version is None:
            raise LedgerParseError(
                f"Ledger is missing required 'version' field. "
                + _RESTORE_HINT
            )
        try:
            version = int(raw_version)
        except (TypeError, ValueError):
            raise LedgerParseError(
                f"Ledger 'version' must be an integer, got {raw_version!r}. "
                + _RESTORE_HINT
            ) from None

        if version != LEDGER_VERSION:
            raise LedgerParseError(
                f"Ledger version {version!r} is not supported; "
                f"expected {LEDGER_VERSION!r}. "
                f"Upgrade oompah or restore a compatible ledger: "
                + _RESTORE_HINT
            )

        # -- deliveries --
        raw_deliveries = raw.get("deliveries")
        if raw_deliveries is None:
            raw_deliveries = []
        if not isinstance(raw_deliveries, list):
            raise LedgerParseError(
                f"Ledger 'deliveries' must be a list, got "
                f"{type(raw_deliveries).__name__!r}. "
                + _RESTORE_HINT
            )

        deliveries: list[ReleaseDelivery] = []
        for i, entry in enumerate(raw_deliveries):
            try:
                deliveries.append(ReleaseDelivery.from_raw(entry))
            except (ValueError, TypeError) as exc:
                raise LedgerParseError(
                    f"Ledger entry at index {i} is invalid: {exc}. "
                    + _RESTORE_HINT
                ) from exc

        return cls(version=version, deliveries=deliveries)


# ---------------------------------------------------------------------------
# Atomic file write helper
# ---------------------------------------------------------------------------


def _atomic_write_ledger(path: Path, content: str) -> None:
    """Write *content* to *path* atomically using a temporary file + rename.

    Creates parent directories as needed.  The destination file is never left
    empty or partially written — if any error occurs before the rename, the
    temporary file is cleaned up and the original *path* is left intact.

    Uses a ``.tmp`` suffix (not ``.yml``) on the temporary file so that stale
    orphans cannot be mistaken for valid ledger files.

    Args:
        path: Destination path.
        content: Full text content to write.

    Raises:
        TrackerError: When the write or rename fails.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        fd, tmp_str = tempfile.mkstemp(
            dir=path.parent, prefix=".oompah_tmp_", suffix=".tmp"
        )
        tmp_path = Path(tmp_str)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass  # best-effort; not all filesystems support fsync
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            tmp_path = None
            raise
        tmp_path.replace(path)
        tmp_path = None
    except OSError as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise TrackerError(f"Cannot write ledger file {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# SHA validation helper
# ---------------------------------------------------------------------------


def _validate_full_sha(sha: str, context: str) -> None:
    """Raise :class:`ValueError` if *sha* is not a valid 40-char hex SHA.

    Args:
        sha: The SHA string to validate.
        context: Human-readable description of where *sha* appears (for the
            error message).

    Raises:
        ValueError: When *sha* does not match :data:`_FULL_SHA_RE`.
    """
    if not _FULL_SHA_RE.match(sha):
        raise ValueError(
            f"{context}: {sha!r} is not a valid 40-character lowercase hex SHA"
        )


# ---------------------------------------------------------------------------
# ReleaseDeliveryStore
# ---------------------------------------------------------------------------


class ReleaseDeliveryStore:
    """Atomic CRUD store for the project-owned release delivery ledger.

    The ledger file is written to :data:`LEDGER_PATH` relative to
    *project_root* and, when *git_writer* is supplied, committed on the
    project's default branch via
    :meth:`~oompah.oompah_md_tracker.OompahMarkdownTracker.write_and_commit_ledger_file`.

    All mutating operations (:meth:`append`, :meth:`update`) are serialised
    under a per-project process-level lock.  The lock is keyed by *project_id*
    and is reentrant so a caller that already holds it can re-enter without
    deadlock.

    **Missing ledger** → treated as an empty version-1 ledger.

    **Malformed ledger** → :class:`LedgerParseError` is raised; the file is
    **never** overwritten until repaired by restoring from git history.

    Args:
        project_root: Root directory of the managed git repository.
        project_id: Identifier of the project that owns this ledger.
        git_writer: Optional object implementing
            ``write_and_commit_ledger_file(relative_path, content, subject)``.
            When supplied, :meth:`append` and :meth:`update` commit the
            ledger via its git infrastructure.  When ``None``, only the
            filesystem write is performed (useful in tests).

    Raises:
        ValueError: When *project_id* is empty.
    """

    def __init__(
        self,
        project_root: str | Path,
        project_id: str,
        *,
        git_writer: Any = None,
    ) -> None:
        self._root = Path(project_root)
        self._project_id = str(project_id or "").strip()
        if not self._project_id:
            raise ValueError("project_id must not be empty")
        self._git_writer = git_writer
        self._ledger_path = self._root / LEDGER_PATH

    @property
    def project_id(self) -> str:
        """The project identifier for this store."""
        return self._project_id

    @property
    def ledger_path(self) -> Path:
        """Absolute path to the ledger file."""
        return self._ledger_path

    def read_ledger(self) -> ReleaseDeliveryLedger:
        """Read and parse the ledger file.

        Returns:
            Parsed :class:`ReleaseDeliveryLedger`.  Returns an empty
            version-1 ledger when the file does not exist.

        Raises:
            LedgerParseError: When the file exists but is malformed (bad YAML,
                wrong version, or invalid entries).
        """
        if not self._ledger_path.exists():
            return ReleaseDeliveryLedger.empty()
        try:
            content = self._ledger_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise LedgerParseError(
                f"Cannot read ledger file {self._ledger_path}: {exc}. "
                f"Restore from git history: git show HEAD:{LEDGER_PATH}"
            ) from exc
        try:
            raw = yaml.load(content, Loader=_YAML_SAFE_LOADER)
        except yaml.YAMLError as exc:
            raise LedgerParseError(
                f"Cannot parse ledger YAML at {self._ledger_path}: {exc}. "
                f"Restore from git history: git show HEAD:{LEDGER_PATH}"
            ) from exc
        return ReleaseDeliveryLedger.from_raw(raw)

    def _write_ledger(self, ledger: ReleaseDeliveryLedger, subject: str) -> None:
        """Write *ledger* to disk and commit it via the git writer if available.

        Must be called within the project-level lock.

        Args:
            ledger: Ledger to persist.
            subject: Commit message subject (used by the git writer).
        """
        content = yaml.safe_dump(
            ledger.to_raw(),
            sort_keys=False,
            allow_unicode=False,
            default_flow_style=False,
        )
        if self._git_writer is not None:
            self._git_writer.write_and_commit_ledger_file(
                LEDGER_PATH,
                content,
                subject,
            )
        else:
            _atomic_write_ledger(self._ledger_path, content)

    def append(self, delivery: ReleaseDelivery) -> ReleaseDelivery:
        """Atomically append a new delivery to the ledger.

        The ledger is read first under the project lock.  If the file is
        malformed the :class:`LedgerParseError` is raised without writing.

        Args:
            delivery: :class:`ReleaseDelivery` to append.  The ``project_id``
                field must match this store's :attr:`project_id`.

        Returns:
            The appended :class:`ReleaseDelivery` (unchanged).

        Raises:
            LedgerParseError: When the existing ledger is malformed.
            ValueError: When *delivery.id* is already present in the ledger,
                or when the delivery's ``project_id`` does not match.
            TrackerError: Propagated from the git writer on commit failure.
        """
        if delivery.project_id != self._project_id:
            raise ValueError(
                f"Delivery project_id {delivery.project_id!r} does not match "
                f"store project_id {self._project_id!r}"
            )
        with _delivery_lock(self._project_id):
            ledger = self.read_ledger()
            existing_ids = {d.id for d in ledger.deliveries}
            if delivery.id in existing_ids:
                raise ValueError(
                    f"Delivery {delivery.id!r} already exists in the ledger; "
                    f"use update() to modify existing entries"
                )
            updated = ReleaseDeliveryLedger(
                version=ledger.version,
                deliveries=list(ledger.deliveries) + [delivery],
            )
            self._write_ledger(updated, f"Append release delivery {delivery.id}")
        return delivery

    def lookup_by_id(self, delivery_id: str) -> ReleaseDelivery | None:
        """Return the delivery with the given *delivery_id*, or ``None``.

        This is a read-only, lock-free operation.

        Args:
            delivery_id: The delivery ID to search for.

        Returns:
            The matching :class:`ReleaseDelivery`, or ``None`` when not found.

        Raises:
            LedgerParseError: When the ledger file is malformed.
        """
        ledger = self.read_ledger()
        for d in ledger.deliveries:
            if d.id == delivery_id:
                return d
        return None

    def lookup_by_source_identifier(
        self,
        source_identifier: str,
    ) -> list[ReleaseDelivery]:
        """Return all deliveries for the given *source_identifier*.

        Deliveries with ``source_kind=commits`` (null identifier) are never
        returned by this method.  This is a read-only, lock-free operation.

        Args:
            source_identifier: Source task or epic identifier to search for.

        Returns:
            Possibly empty list of :class:`ReleaseDelivery` objects whose
            ``source_identifier`` matches *source_identifier*.

        Raises:
            LedgerParseError: When the ledger file is malformed.
        """
        ledger = self.read_ledger()
        return [
            d for d in ledger.deliveries
            if d.source_identifier == source_identifier
        ]

    def update(
        self,
        delivery_id: str,
        **mutable_fields: Any,
    ) -> ReleaseDelivery:
        """Atomically update mutable fields of an existing delivery.

        Only fields listed in :data:`_MUTABLE_FIELDS` may be updated.
        Immutable fields cannot be changed; passing them raises
        :class:`ImmutableFieldError`.

        Status transitions are validated against the lifecycle FSM
        (:data:`~oompah.release_addendum_schema.VALID_TRANSITIONS`).

        Args:
            delivery_id: ID of the delivery to update.
            **mutable_fields: Keyword arguments matching :data:`_MUTABLE_FIELDS`.
                Fields not supplied are preserved from the existing record.

        Returns:
            The updated :class:`ReleaseDelivery`.

        Raises:
            LedgerParseError: When the existing ledger is malformed.
            DeliveryNotFoundError: When *delivery_id* is not in the ledger.
            ImmutableFieldError: When a caller attempts to change an immutable
                field.
            ValueError: When *mutable_fields* contains unknown field names or
                ``result_commits`` entries that are not valid full SHAs.
            InvalidTransitionError: When the requested status transition is
                invalid per the lifecycle FSM.
            TrackerError: Propagated from the git writer on commit failure.
        """
        # Validate field names before acquiring the lock
        immutable_attempts = set(mutable_fields) & _IMMUTABLE_FIELDS
        if immutable_attempts:
            raise ImmutableFieldError(
                f"Cannot change immutable field(s): {sorted(immutable_attempts)}. "
                f"Immutable fields are: {sorted(_IMMUTABLE_FIELDS)}"
            )
        unknown = set(mutable_fields) - _MUTABLE_FIELDS
        if unknown:
            raise ValueError(
                f"Unknown update field(s): {sorted(unknown)}. "
                f"Allowed mutable fields are: {sorted(_MUTABLE_FIELDS)}"
            )

        with _delivery_lock(self._project_id):
            ledger = self.read_ledger()
            index = next(
                (i for i, d in enumerate(ledger.deliveries) if d.id == delivery_id),
                None,
            )
            if index is None:
                raise DeliveryNotFoundError(
                    f"Delivery {delivery_id!r} not found in ledger for "
                    f"project {self._project_id!r}"
                )

            current = ledger.deliveries[index]

            # Validate status transition if a new status is requested
            new_status: AddendumStatus | None = None
            if "status" in mutable_fields:
                raw_new_status = mutable_fields["status"]
                if isinstance(raw_new_status, AddendumStatus):
                    new_status = raw_new_status
                else:
                    new_status = AddendumStatus.from_raw(raw_new_status)
                if not is_valid_transition(current.status, new_status):
                    raise InvalidTransitionError(
                        f"Cannot transition delivery {delivery_id!r} "
                        f"from {current.status.value!r} to {new_status.value!r}"
                    )
                mutable_fields = {**mutable_fields, "status": new_status}

            # Validate result_commits SHA format if provided
            if "result_commits" in mutable_fields:
                raw_result = mutable_fields.get("result_commits") or []
                for sha in raw_result:
                    _validate_full_sha(
                        str(sha),
                        f"delivery {delivery_id!r} result_commits update",
                    )

            # Build the updated delivery, preserving immutable fields
            updated_delivery = ReleaseDelivery(
                # Immutable fields — copied exactly, never from mutable_fields
                id=current.id,
                project_id=current.project_id,
                source_branch=current.source_branch,
                source_kind=current.source_kind,
                source_identifier=current.source_identifier,
                source_commits=list(current.source_commits),
                target_branch=current.target_branch,
                # Mutable fields — apply updates or preserve existing
                status=mutable_fields.get("status", current.status),
                queued_at=mutable_fields.get("queued_at", current.queued_at),
                claimed_by=mutable_fields.get("claimed_by", current.claimed_by),
                lease_expires_at=mutable_fields.get(
                    "lease_expires_at", current.lease_expires_at
                ),
                started_at=mutable_fields.get("started_at", current.started_at),
                completed_at=mutable_fields.get("completed_at", current.completed_at),
                work_branch=mutable_fields.get("work_branch", current.work_branch),
                pr_url=mutable_fields.get("pr_url", current.pr_url),
                pr_number=mutable_fields.get("pr_number", current.pr_number),
                result_commits=mutable_fields.get(
                    "result_commits", list(current.result_commits)
                ),
                error=mutable_fields.get("error", current.error),
                migrated_from=mutable_fields.get(
                    "migrated_from", current.migrated_from
                ),
            )

            updated_deliveries = list(ledger.deliveries)
            updated_deliveries[index] = updated_delivery
            updated_ledger = ReleaseDeliveryLedger(
                version=ledger.version,
                deliveries=updated_deliveries,
            )
            self._write_ledger(
                updated_ledger,
                f"Update release delivery {delivery_id}",
            )

        return updated_delivery
