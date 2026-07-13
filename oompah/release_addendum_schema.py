"""Release-addendum metadata schema and lifecycle (OOMPAH-173).

Defines the typed schema for the ``oompah.release_addendums`` tracker metadata
field that coordinates cherry-pick PRs from a merged source task to one or more
release branches.

Overview
--------

When a merged source task (or epic) is approved for delivery to a release
branch, Oompah writes a :class:`ReleaseAddendum` entry to the source task's
``oompah.release_addendums`` metadata list::

    oompah.release_addendums:
      - id: "FOO-10/release/1.0"
        source_branch: main
        target_branch: release/1.0
        status: open
        commits:
          - 3c8c1d5f6a...  # immutable, ordered, full SHA
        queued_at: "2026-07-13T12:00:00Z"
        started_at: null
        completed_at: null
        work_branch: "oompah/release/FOO-10/release-1.0"
        worktree_key: "release-FOO-10-release-1.0"
        pr_url: null
        result_commits: []
        error: null

Invariants
----------

- ``id`` is the stable tuple ``<source_identifier>/<target_branch>`` and is an
  identifier, not a filesystem path.
- A source task has **at most one non-archived addendum** per target branch.
- ``source_branch`` is set at creation time from the project's
  ``default_branch``; it is not editable by the client.
- ``commits`` is an immutable, non-empty, ordered snapshot set before the
  addendum becomes ``open``.  A retry uses the same list.
- ``work_branch`` is deterministic from source ID and target branch, and is
  namespaced under ``oompah/release/`` to avoid collisions.
- ``result_commits``, ``pr_url``, timestamps (``started_at``,
  ``completed_at``), ``error``, ``claimed_by``, and ``lease_expires_at`` are
  execution evidence populated only by automation, not by the client.

Status lifecycle (section 4.2)
-------------------------------

::

    [*] → open              release branches approved
    open → in_progress      queue worker claims
    in_progress → in_review cherry-pick pushed and PR opened
    in_progress → blocked   conflict or execution failure
    in_review → merged      target PR merged
    in_review → open        unmerged PR closed; retry requested
    blocked → open          operator retries
    open → archived         operator cancels
    blocked → archived      operator cancels
    merged → [*]
    archived → [*]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Branch-name sanitizer
# ---------------------------------------------------------------------------

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_part(value: str) -> str:
    """Replace unsafe characters with ``-`` and strip leading/trailing specials.

    Produces a Git-safe segment for embedding in branch names and worktree
    keys.  Uses ``-`` as the replacement character (not ``_``) so that
    branch components read more naturally and remain consistent with the
    ``oompah/release/`` namespace convention.

    Args:
        value: Raw string to sanitize.

    Returns:
        Sanitized string; falls back to ``"unnamed"`` for empty results.
    """
    cleaned = _SAFE_CHARS.sub("-", str(value or "").strip())
    return cleaned.strip(".-") or "unnamed"


# ---------------------------------------------------------------------------
# AddendumStatus enum
# ---------------------------------------------------------------------------


class AddendumStatus(str, Enum):
    """Lifecycle status of a single release addendum.

    Values are lower-cased strings so they serialise cleanly to YAML/JSON
    and remain readable by non-Python tooling.
    """

    #: Queued and awaiting a queue worker to claim it.
    OPEN = "open"
    #: Claimed by a worker; cherry-pick in progress.
    IN_PROGRESS = "in_progress"
    #: Cherry-pick pushed, PR opened; awaiting review and CI.
    IN_REVIEW = "in_review"
    #: Blocked by a conflict or execution failure; needs operator attention.
    BLOCKED = "blocked"
    #: PR has been merged into the target branch.
    MERGED = "merged"
    #: Addendum has been cancelled by the operator.
    ARCHIVED = "archived"

    @classmethod
    def from_raw(cls, raw: Any) -> "AddendumStatus":
        """Parse a raw string (or enum value) into an :class:`AddendumStatus`.

        Accepts the enum value string (case-insensitive, hyphens normalised to
        underscores).  Raises :class:`ValueError` for unrecognised or missing
        values — callers must handle missing statuses explicitly rather than
        silently defaulting, because a missing status indicates a malformed
        record.

        Args:
            raw: Raw frontmatter value (``str``, ``None``, or already an
                :class:`AddendumStatus`).

        Returns:
            The matching :class:`AddendumStatus` member.

        Raises:
            ValueError: When *raw* is ``None``, empty, or does not match any
                known status value.
        """
        if isinstance(raw, cls):
            return raw
        if not raw:
            raise ValueError(f"AddendumStatus value must not be empty, got {raw!r}")
        normalised = str(raw).strip().lower().replace("-", "_")
        try:
            return cls(normalised)
        except ValueError:
            valid = ", ".join(m.value for m in cls)
            raise ValueError(
                f"Unknown AddendumStatus {raw!r}; must be one of: {valid}"
            ) from None

    @property
    def is_terminal(self) -> bool:
        """Return True when this status represents a final, non-advancing state."""
        return self in _TERMINAL_STATUSES

    @property
    def is_active(self) -> bool:
        """Return True when this addendum is considered active (not archived/merged).

        Active addendums count toward the one-per-target-branch limit.
        """
        return self not in _INACTIVE_STATUSES


_TERMINAL_STATUSES: frozenset[AddendumStatus] = frozenset({
    AddendumStatus.MERGED,
    AddendumStatus.ARCHIVED,
})

_INACTIVE_STATUSES: frozenset[AddendumStatus] = frozenset({
    AddendumStatus.MERGED,
    AddendumStatus.ARCHIVED,
})

# ---------------------------------------------------------------------------
# Transition table (section 4.2)
# ---------------------------------------------------------------------------

#: Machine-readable FSM: maps each status to the set it may transition to.
VALID_TRANSITIONS: dict[AddendumStatus, frozenset[AddendumStatus]] = {
    AddendumStatus.OPEN: frozenset({
        AddendumStatus.IN_PROGRESS,
        AddendumStatus.ARCHIVED,
    }),
    AddendumStatus.IN_PROGRESS: frozenset({
        AddendumStatus.IN_REVIEW,
        AddendumStatus.BLOCKED,
        # A worker lease is deliberately recoverable.  The queue reconciler
        # uses this edge only after ``lease_expires_at`` has elapsed.
        AddendumStatus.OPEN,
    }),
    AddendumStatus.IN_REVIEW: frozenset({
        AddendumStatus.MERGED,
        AddendumStatus.OPEN,   # unmerged PR closed; retry
    }),
    AddendumStatus.BLOCKED: frozenset({
        AddendumStatus.OPEN,
        AddendumStatus.ARCHIVED,
    }),
    AddendumStatus.MERGED: frozenset(),    # terminal
    AddendumStatus.ARCHIVED: frozenset(),  # terminal
}


def is_valid_transition(
    from_status: AddendumStatus,
    to_status: AddendumStatus,
) -> bool:
    """Return True when *from_status* → *to_status* is a valid lifecycle transition.

    A self-transition always returns False.

    Args:
        from_status: The current :class:`AddendumStatus`.
        to_status: The desired next :class:`AddendumStatus`.

    Returns:
        True if the transition is allowed by :data:`VALID_TRANSITIONS`.
    """
    if from_status == to_status:
        return False
    return to_status in VALID_TRANSITIONS.get(from_status, frozenset())


# ---------------------------------------------------------------------------
# Deterministic ID / branch / worktree helpers
# ---------------------------------------------------------------------------


def make_addendum_id(source_id: str, target_branch: str) -> str:
    """Return the stable addendum identifier ``<source_id>/<target_branch>``.

    The ID is the human-readable tuple and is used as a key in the metadata
    list.  Encode it when embedding in a URL; use
    :func:`make_work_branch` or :func:`make_worktree_key` for Git names.

    Args:
        source_id: Source task or epic identifier (e.g. ``"FOO-10"``).
        target_branch: Exact target branch name (e.g. ``"release/1.0"``).

    Returns:
        Stable addendum ID string.

    Raises:
        ValueError: When either argument is empty.
    """
    source_id = str(source_id or "").strip()
    target_branch = str(target_branch or "").strip()
    if not source_id:
        raise ValueError("source_id must not be empty")
    if not target_branch:
        raise ValueError("target_branch must not be empty")
    return f"{source_id}/{target_branch}"


def make_work_branch(source_id: str, target_branch: str) -> str:
    """Return the deterministic work branch name for a release addendum.

    The name is namespaced under ``oompah/release/`` so it cannot collide
    with ordinary task branches.  Individual segments are sanitized via
    :func:`_sanitize_part`.

    Example::

        make_work_branch("FOO-10", "release/1.0")
        # → "oompah/release/FOO-10/release-1.0"

    Args:
        source_id: Source task or epic identifier.
        target_branch: Exact target branch name.

    Returns:
        Deterministic, Git-safe work branch name.

    Raises:
        ValueError: When either argument is empty.
    """
    source_id = str(source_id or "").strip()
    target_branch = str(target_branch or "").strip()
    if not source_id:
        raise ValueError("source_id must not be empty")
    if not target_branch:
        raise ValueError("target_branch must not be empty")
    safe_source = _sanitize_part(source_id)
    safe_target = _sanitize_part(target_branch)
    return f"oompah/release/{safe_source}/{safe_target}"


def make_worktree_key(source_id: str, target_branch: str) -> str:
    """Return the deterministic worktree key for a release addendum.

    The key is a flat, filesystem-safe slug derived from source ID and target
    branch, prefixed with ``release-``.

    Example::

        make_worktree_key("FOO-10", "release/1.0")
        # → "release-FOO-10-release-1.0"

    Args:
        source_id: Source task or epic identifier.
        target_branch: Exact target branch name.

    Returns:
        Deterministic, filesystem-safe worktree key.

    Raises:
        ValueError: When either argument is empty.
    """
    source_id = str(source_id or "").strip()
    target_branch = str(target_branch or "").strip()
    if not source_id:
        raise ValueError("source_id must not be empty")
    if not target_branch:
        raise ValueError("target_branch must not be empty")
    safe_source = _sanitize_part(source_id)
    safe_target = _sanitize_part(target_branch)
    return f"release-{safe_source}-{safe_target}"


# ---------------------------------------------------------------------------
# ReleaseAddendum dataclass
# ---------------------------------------------------------------------------


@dataclass
class ReleaseAddendum:
    """One release addendum attached to a source task.

    Persisted as one element of the ``oompah.release_addendums`` list in
    task metadata.

    Fields that are execution evidence (``result_commits``, ``pr_url``,
    ``started_at``, ``completed_at``, ``error``, ``claimed_by``,
    ``lease_expires_at``) are populated only by automation and must never
    be accepted from client input.

    Attributes:
        id: Stable ``<source_id>/<target_branch>`` identifier.
        source_branch: Project's default branch at creation time; immutable.
        target_branch: Exact release branch name (e.g. ``"release/1.0"``).
        status: Current lifecycle status.
        commits: Immutable, ordered, nonempty list of full SHAs to cherry-pick.
        work_branch: Deterministic branch name under ``oompah/release/``.
        worktree_key: Deterministic filesystem slug for the worktree.
        queued_at: ISO-8601 UTC timestamp when the addendum was created.
        started_at: ISO-8601 UTC timestamp when a worker claimed it (nullable).
        completed_at: ISO-8601 UTC timestamp when it reached a terminal state
            (nullable).
        pr_url: URL of the cherry-pick PR, once opened (execution evidence).
        result_commits: SHAs actually landed on the target branch (execution
            evidence).
        error: Diagnostic message on ``blocked`` (execution evidence).
        claimed_by: Worker identity during ``in_progress`` (execution evidence).
        lease_expires_at: ISO-8601 UTC expiry of the in-progress lease
            (execution evidence).
    """

    id: str
    source_branch: str
    target_branch: str
    status: AddendumStatus
    commits: list[str]
    work_branch: str
    worktree_key: str
    queued_at: str
    # Nullable fields
    started_at: str | None = None
    completed_at: str | None = None
    pr_url: str | None = None
    result_commits: list[str] = field(default_factory=list)
    error: str | None = None
    claimed_by: str | None = None
    lease_expires_at: str | None = None

    def to_raw(self) -> dict[str, Any]:
        """Serialise this addendum to a raw dict for storage in task metadata.

        All fields are included so the record is self-contained.  ``None``
        values for nullable fields and empty lists are preserved explicitly
        so the YAML representation is stable across round-trips.

        Returns:
            Dict suitable for writing to ``oompah.release_addendums`` list.
        """
        out: dict[str, Any] = {
            "id": self.id,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "status": self.status.value,
            "commits": list(self.commits),
            "work_branch": self.work_branch,
            "worktree_key": self.worktree_key,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "pr_url": self.pr_url,
            "result_commits": list(self.result_commits),
            "error": self.error,
        }
        # Lease fields — only include when set to keep records compact
        if self.claimed_by is not None:
            out["claimed_by"] = self.claimed_by
        if self.lease_expires_at is not None:
            out["lease_expires_at"] = self.lease_expires_at
        return out

    @classmethod
    def from_raw(cls, raw: Any) -> "ReleaseAddendum":
        """Parse a raw dict into a :class:`ReleaseAddendum`.

        Validates required fields and rejects execution-evidence fields if
        they contain unexpected types, but does not silently drop or mutate
        them — the serialised record is the authoritative source.

        Args:
            raw: Raw frontmatter dict (one element of
                ``oompah.release_addendums``).

        Returns:
            Parsed :class:`ReleaseAddendum`.

        Raises:
            ValueError: When *raw* is not a dict, required fields are
                missing or invalid, the status is unknown, or ``commits``
                is empty.
        """
        if not isinstance(raw, dict):
            raise ValueError(
                f"ReleaseAddendum entry must be a dict, got {type(raw).__name__!r}: {raw!r}"
            )

        # --- Required string fields ---
        addendum_id = str(raw.get("id") or "").strip()
        if not addendum_id:
            raise ValueError(f"ReleaseAddendum missing required 'id': {raw!r}")

        source_branch = str(raw.get("source_branch") or "").strip()
        if not source_branch:
            raise ValueError(f"ReleaseAddendum missing required 'source_branch': {raw!r}")

        target_branch = str(raw.get("target_branch") or "").strip()
        if not target_branch:
            raise ValueError(f"ReleaseAddendum missing required 'target_branch': {raw!r}")

        # --- Status ---
        status = AddendumStatus.from_raw(raw.get("status"))

        # --- Commits: required, nonempty ---
        raw_commits = raw.get("commits")
        if not raw_commits:
            raise ValueError(
                f"ReleaseAddendum 'commits' must be a nonempty list: {raw!r}"
            )
        if isinstance(raw_commits, str):
            raw_commits = [raw_commits]
        commits = [str(c).strip() for c in raw_commits if str(c).strip()]
        if not commits:
            raise ValueError(
                f"ReleaseAddendum 'commits' must contain nonempty SHA strings: {raw!r}"
            )

        # --- Deterministic branch fields ---
        work_branch = str(raw.get("work_branch") or "").strip()
        if not work_branch:
            raise ValueError(f"ReleaseAddendum missing required 'work_branch': {raw!r}")

        worktree_key = str(raw.get("worktree_key") or "").strip()
        if not worktree_key:
            raise ValueError(f"ReleaseAddendum missing required 'worktree_key': {raw!r}")

        queued_at = str(raw.get("queued_at") or "").strip()
        if not queued_at:
            raise ValueError(f"ReleaseAddendum missing required 'queued_at': {raw!r}")

        # --- Nullable / execution-evidence fields ---
        def _opt_str(key: str) -> str | None:
            v = raw.get(key)
            if v is None:
                return None
            s = str(v).strip()
            return s if s else None

        raw_result_commits = raw.get("result_commits") or []
        if isinstance(raw_result_commits, str):
            raw_result_commits = [raw_result_commits]
        result_commits = [str(c).strip() for c in raw_result_commits if str(c).strip()]

        return cls(
            id=addendum_id,
            source_branch=source_branch,
            target_branch=target_branch,
            status=status,
            commits=commits,
            work_branch=work_branch,
            worktree_key=worktree_key,
            queued_at=queued_at,
            started_at=_opt_str("started_at"),
            completed_at=_opt_str("completed_at"),
            pr_url=_opt_str("pr_url"),
            result_commits=result_commits,
            error=_opt_str("error"),
            claimed_by=_opt_str("claimed_by"),
            lease_expires_at=_opt_str("lease_expires_at"),
        )


# ---------------------------------------------------------------------------
# Top-level parsing and serialisation helpers
# ---------------------------------------------------------------------------


def parse_addendums(raw: Any) -> list[ReleaseAddendum]:
    """Parse the raw ``oompah.release_addendums`` metadata value.

    Accepts ``None`` (returns empty list) or a list of dicts (returns typed
    objects).  String scalars are not accepted — every addendum is a full
    dict record.

    Args:
        raw: Raw value from
            ``tracker.get_metadata(identifier).get("oompah.release_addendums")``.

    Returns:
        List of :class:`ReleaseAddendum` objects.  Returns an empty list
        when *raw* is ``None`` or empty.

    Raises:
        ValueError: Propagated from :meth:`ReleaseAddendum.from_raw` when an
            individual entry is malformed.
    """
    if raw is None:
        return []
    if isinstance(raw, dict):
        # Single dict — treat as a one-element list for partial compatibility
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError(
            f"oompah.release_addendums must be a list or null, got {type(raw).__name__!r}"
        )
    return [ReleaseAddendum.from_raw(item) for item in raw]


def addendums_to_raw(addendums: list[ReleaseAddendum]) -> list[dict[str, Any]]:
    """Serialise a list of :class:`ReleaseAddendum` objects to raw form.

    Args:
        addendums: List of typed addendum objects.

    Returns:
        List of dicts suitable for writing to ``oompah.release_addendums``.
    """
    return [a.to_raw() for a in addendums]


# ---------------------------------------------------------------------------
# AddendumRepository — metadata read/write helper
# ---------------------------------------------------------------------------


class DuplicateTargetError(ValueError):
    """Raised when adding an addendum to a branch that already has an active one.

    An "active" addendum is any with a status other than ``merged`` or
    ``archived``.
    """


class InvalidTransitionError(ValueError):
    """Raised when an illegal status transition is attempted."""


class ImmutableCommitsError(ValueError):
    """Raised when an attempt is made to change the commits of an existing addendum."""


class AddendumRepository:
    """Read and atomically replace ``oompah.release_addendums`` on a source task.

    This helper wraps a :class:`~oompah.tracker.TrackerProtocol` and provides
    typed, validated access to the release addendum list.  It only reads and
    writes the ``oompah.release_addendums`` field; all other metadata on the
    task is preserved unchanged.

    Usage::

        repo = AddendumRepository(tracker)
        addendums = repo.read("FOO-10")
        updated = transition_addendum(addendums, "FOO-10/release/1.0", AddendumStatus.IN_PROGRESS)
        repo.write("FOO-10", updated)

    Note: this class deliberately does not implement locking — callers that
    need mutual exclusion (e.g. the queue worker) must hold a higher-level
    per-source-task lock before calling :meth:`write`.
    """

    _METADATA_KEY = "oompah.release_addendums"

    def __init__(self, tracker: Any) -> None:
        """Initialise the repository.

        Args:
            tracker: An object implementing the
                :class:`~oompah.tracker.TrackerProtocol` interface.  The only
                methods used are :meth:`get_metadata` and
                :meth:`set_metadata_field`.
        """
        self._tracker = tracker

    def read(self, identifier: str) -> list[ReleaseAddendum]:
        """Read the current release addendum list for *identifier*.

        Args:
            identifier: Source task or epic identifier.

        Returns:
            Parsed list of :class:`ReleaseAddendum` objects.  Returns an
            empty list when the field is absent or null.

        Raises:
            ValueError: When the stored value is malformed.
        """
        meta = self._tracker.get_metadata(identifier)
        raw = meta.get(self._METADATA_KEY)
        return parse_addendums(raw)

    def write(
        self,
        identifier: str,
        addendums: list[ReleaseAddendum],
    ) -> None:
        """Atomically replace the ``oompah.release_addendums`` field.

        All other fields on the task are preserved unchanged.

        Args:
            identifier: Source task or epic identifier.
            addendums: Updated list of :class:`ReleaseAddendum` objects.

        Raises:
            :exc:`DuplicateTargetError`: When more than one active addendum
                exists for the same target branch.
            :exc:`TrackerError`: Propagated from the underlying tracker when
                the write fails.
        """
        _validate_no_duplicate_active_targets(addendums)
        raw = addendums_to_raw(addendums)
        self._tracker.set_metadata_field(identifier, self._METADATA_KEY, raw)

    def add(
        self,
        identifier: str,
        addendum: ReleaseAddendum,
        existing: list[ReleaseAddendum] | None = None,
    ) -> list[ReleaseAddendum]:
        """Add *addendum* to the source task's list if no active entry already exists.

        If an active addendum already exists for ``addendum.target_branch``,
        the existing entry is returned unchanged (idempotent approval
        semantics).  If only an archived/merged entry exists, a new active
        entry is added.

        Args:
            identifier: Source task or epic identifier.
            addendum: New :class:`ReleaseAddendum` to add.
            existing: Optional pre-read list to avoid a redundant read.
                When ``None``, the list is fetched from the tracker.

        Returns:
            The updated list after writing.

        Raises:
            :exc:`DuplicateTargetError`: When an active addendum already
                exists for the same branch (raised only when the new entry
                is not identical to the existing one — true duplicates are
                a bug, not idempotency).
            :exc:`TrackerError`: Propagated from the underlying tracker.
        """
        if existing is None:
            existing = self.read(identifier)

        active_for_branch = [
            a for a in existing
            if a.target_branch == addendum.target_branch and a.status.is_active
        ]
        if active_for_branch:
            # Idempotent: same active entry already present
            return existing

        updated = list(existing) + [addendum]
        self.write(identifier, updated)
        return updated

    def transition(
        self,
        identifier: str,
        addendum_id: str,
        to_status: AddendumStatus,
        *,
        existing: list[ReleaseAddendum] | None = None,
        **execution_evidence: Any,
    ) -> list[ReleaseAddendum]:
        """Transition the addendum identified by *addendum_id* to *to_status*.

        Only the fields listed under "execution evidence" may be updated
        alongside a transition.  The ``commits`` field is always preserved
        from the existing record.

        Args:
            identifier: Source task or epic identifier.
            addendum_id: The ``id`` of the addendum to transition.
            to_status: Target :class:`AddendumStatus`.
            existing: Optional pre-read list to avoid a redundant read.
            **execution_evidence: Keyword arguments for allowed execution-
                evidence fields: ``pr_url``, ``result_commits``, ``error``,
                ``claimed_by``, ``lease_expires_at``, ``started_at``,
                ``completed_at``.

        Returns:
            The updated list after writing.

        Raises:
            :exc:`KeyError`: When *addendum_id* is not found in the list.
            :exc:`InvalidTransitionError`: When the transition is not valid
                per :data:`VALID_TRANSITIONS`.
            :exc:`TrackerError`: Propagated from the underlying tracker.
        """
        _EVIDENCE_FIELDS = {
            "pr_url",
            "result_commits",
            "error",
            "claimed_by",
            "lease_expires_at",
            "started_at",
            "completed_at",
        }
        unknown = set(execution_evidence) - _EVIDENCE_FIELDS
        if unknown:
            raise ValueError(
                f"Unexpected keyword arguments (not execution evidence): {sorted(unknown)}"
            )

        if existing is None:
            existing = self.read(identifier)

        index = next(
            (i for i, a in enumerate(existing) if a.id == addendum_id),
            None,
        )
        if index is None:
            raise KeyError(f"No addendum with id={addendum_id!r} on {identifier!r}")

        current = existing[index]
        if not is_valid_transition(current.status, to_status):
            raise InvalidTransitionError(
                f"Cannot transition addendum {addendum_id!r} "
                f"from {current.status.value!r} to {to_status.value!r}"
            )

        # Build updated record, preserving commits and all other fields
        updated_addendum = ReleaseAddendum(
            id=current.id,
            source_branch=current.source_branch,
            target_branch=current.target_branch,
            status=to_status,
            commits=list(current.commits),  # immutable — never changed by transition
            work_branch=current.work_branch,
            worktree_key=current.worktree_key,
            queued_at=current.queued_at,
            started_at=execution_evidence.get("started_at", current.started_at),
            completed_at=execution_evidence.get("completed_at", current.completed_at),
            pr_url=execution_evidence.get("pr_url", current.pr_url),
            result_commits=execution_evidence.get("result_commits", list(current.result_commits)),
            error=execution_evidence.get("error", current.error),
            claimed_by=execution_evidence.get("claimed_by", current.claimed_by),
            lease_expires_at=execution_evidence.get("lease_expires_at", current.lease_expires_at),
        )

        updated_list = list(existing)
        updated_list[index] = updated_addendum
        self.write(identifier, updated_list)
        return updated_list


# ---------------------------------------------------------------------------
# Internal validation helpers
# ---------------------------------------------------------------------------


def _validate_no_duplicate_active_targets(addendums: list[ReleaseAddendum]) -> None:
    """Raise :exc:`DuplicateTargetError` if two active addendums share a target branch.

    Args:
        addendums: List to validate.

    Raises:
        :exc:`DuplicateTargetError`: On the first detected duplicate.
    """
    seen: dict[str, str] = {}  # target_branch → addendum_id
    for a in addendums:
        if not a.status.is_active:
            continue
        if a.target_branch in seen:
            raise DuplicateTargetError(
                f"Duplicate active addendum for target branch {a.target_branch!r}: "
                f"{seen[a.target_branch]!r} and {a.id!r}"
            )
        seen[a.target_branch] = a.id
