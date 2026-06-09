"""Release-pick metadata schema and status lifecycle (TASK-454.4).

Defines the formal typed schema for the ``oompah.backports`` and
``oompah.backport_of`` Backlog.md frontmatter fields used to coordinate
cherry-pick PRs to release branches.

Overview
--------

When a source task (e.g. a feature or bugfix) is ready to be backported to
one or more release branches, the operator adds an ``oompah.backports`` entry
to its Backlog frontmatter listing the target branches::

    oompah:
      backports:
        - branch: release/1.0
          status: waiting
        - branch: release/2.0
          status: waiting

The reconciliation loop (TASK-455.1) reads this list, creates a child Backlog
task per target branch, cherry-picks the source commits, opens a PR, and
advances the ``status`` field as the work progresses.

The child (backport) task carries ``oompah.backport_of`` pointing back to the
source::

    oompah:
      backport_of: TASK-100

Or, in the richer form, with a status that mirrors the parent's entry::

    oompah:
      backport_of:
        source: TASK-100
        status: cherry_picking

Status lifecycle
----------------

Each release-pick entry moves through the following states.  The state
machine is intentionally lenient — only the forward transitions below are
produced by automation; any state can transition to ``archived`` or
``needs_human`` by operator action::

    waiting → task_created → cherry_picking → pr_open → merged
                                           ↘ conflict → needs_human
                                                       → cherry_picking  (retry)
    (any) → archived
    (any) → needs_human

See the ``VALID_TRANSITIONS`` mapping for the full machine-readable graph.

Schema
------

``oompah.backports`` accepts three equivalent forms:

1. A scalar string (single target branch, shorthand):
   ``oompah.backports: "release/1.0"``
2. A list of strings (multiple branches, all implicitly ``waiting``):
   ``oompah.backports: ["release/1.0", "release/2.0"]``
3. A list of objects with ``branch`` and optional ``status``, ``task_id``,
   ``pr_url`` fields (full tracking form):
   ``oompah.backports: [{branch: "release/1.0", status: merged, task_id: TASK-100.1}]``

``oompah.backport_of`` accepts two forms:

1. A plain string (source task identifier):
   ``oompah.backport_of: TASK-100``
2. A mapping with ``source`` and optional ``status``:
   ``oompah.backport_of: {source: TASK-100, status: pr_open}``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Status lifecycle
# ---------------------------------------------------------------------------


class ReleasePick(str, Enum):
    """Status of a single release-pick (cherry-pick) to one target branch.

    Values are lower-cased strings so they serialise cleanly as Backlog.md
    frontmatter and are readable by non-Python tooling.
    """

    #: Requested but not yet started; no child task exists.
    WAITING = "waiting"
    #: Child backport task has been created in the tracker.
    TASK_CREATED = "task_created"
    #: Cherry-pick commit is being authored in a worktree.
    CHERRY_PICKING = "cherry_picking"
    #: PR has been opened against the target branch; awaiting review/CI.
    PR_OPEN = "pr_open"
    #: Cherry-pick produced merge conflicts; blocked pending resolution.
    CONFLICT = "conflict"
    #: PR has been successfully merged into the target branch.
    MERGED = "merged"
    #: Pick has been abandoned (target branch no longer relevant, etc.).
    ARCHIVED = "archived"
    #: Stuck; manual human intervention required before automation can proceed.
    NEEDS_HUMAN = "needs_human"
    #: Intentionally excluded from backporting (operator-set; no automation will act on it).
    SKIPPED = "skipped"

    @classmethod
    def from_raw(cls, raw: Any) -> "ReleasePick":
        """Parse a raw string (or enum value) into a :class:`ReleasePick`.

        Accepts the enum value string (case-insensitive).  Falls back to
        :attr:`WAITING` for unrecognised or missing values so that new
        entries always start in the expected initial state.

        Args:
            raw: Raw value from Backlog frontmatter (``str``, ``None``,
                 or already a :class:`ReleasePick`).

        Returns:
            The matching :class:`ReleasePick` member, or
            :attr:`ReleasePick.WAITING` when ``raw`` is ``None``, empty, or
            unrecognised.
        """
        if isinstance(raw, cls):
            return raw
        if not raw:
            return cls.WAITING
        normalised = str(raw).strip().lower().replace("-", "_")
        try:
            return cls(normalised)
        except ValueError:
            return cls.WAITING

    @property
    def is_terminal(self) -> bool:
        """Return True when this status represents a final (non-advancing) state."""
        return self in _TERMINAL_STATUSES

    @property
    def is_blocked(self) -> bool:
        """Return True when this status represents a blocked state needing attention."""
        return self in _BLOCKED_STATUSES


_TERMINAL_STATUSES: frozenset[ReleasePick] = frozenset({
    ReleasePick.MERGED,
    ReleasePick.ARCHIVED,
    ReleasePick.SKIPPED,
})

_BLOCKED_STATUSES: frozenset[ReleasePick] = frozenset({
    ReleasePick.CONFLICT,
    ReleasePick.NEEDS_HUMAN,
})

# Machine-readable FSM: maps each status to the set of statuses it may
# transition to.  Any status can transition to ARCHIVED or NEEDS_HUMAN
# outside the table (operator override / escalation).
VALID_TRANSITIONS: dict[ReleasePick, frozenset[ReleasePick]] = {
    ReleasePick.WAITING: frozenset({
        ReleasePick.TASK_CREATED,
        ReleasePick.ARCHIVED,
        ReleasePick.NEEDS_HUMAN,
        ReleasePick.SKIPPED,
    }),
    ReleasePick.TASK_CREATED: frozenset({
        ReleasePick.CHERRY_PICKING,
        ReleasePick.ARCHIVED,
        ReleasePick.NEEDS_HUMAN,
        ReleasePick.SKIPPED,
    }),
    ReleasePick.CHERRY_PICKING: frozenset({
        ReleasePick.PR_OPEN,
        ReleasePick.CONFLICT,
        ReleasePick.ARCHIVED,
        ReleasePick.NEEDS_HUMAN,
        ReleasePick.SKIPPED,
    }),
    ReleasePick.PR_OPEN: frozenset({
        ReleasePick.MERGED,
        ReleasePick.CHERRY_PICKING,   # PR closed, need to re-cherry-pick
        ReleasePick.CONFLICT,
        ReleasePick.ARCHIVED,
        ReleasePick.NEEDS_HUMAN,
        ReleasePick.SKIPPED,
    }),
    ReleasePick.CONFLICT: frozenset({
        ReleasePick.CHERRY_PICKING,   # conflict resolved, retry
        ReleasePick.NEEDS_HUMAN,
        ReleasePick.ARCHIVED,
        ReleasePick.SKIPPED,
    }),
    ReleasePick.MERGED: frozenset(),          # terminal — no forward transitions
    ReleasePick.ARCHIVED: frozenset(),        # terminal — no forward transitions
    ReleasePick.SKIPPED: frozenset(),         # terminal — no forward transitions
    ReleasePick.NEEDS_HUMAN: frozenset({
        ReleasePick.CHERRY_PICKING,   # operator resolved, retry
        ReleasePick.ARCHIVED,
        ReleasePick.SKIPPED,
    }),
}


def is_valid_transition(from_status: ReleasePick, to_status: ReleasePick) -> bool:
    """Return True when *from_status* → *to_status* is a valid lifecycle transition.

    Args:
        from_status: The current :class:`ReleasePick` status.
        to_status: The desired next :class:`ReleasePick` status.

    Returns:
        True if the transition is allowed by :data:`VALID_TRANSITIONS`,
        False otherwise.  A no-op self-transition always returns False.
    """
    if from_status == to_status:
        return False
    return to_status in VALID_TRANSITIONS.get(from_status, frozenset())


# ---------------------------------------------------------------------------
# BackportEntry — one element of oompah.backports
# ---------------------------------------------------------------------------


@dataclass
class BackportEntry:
    """Represents one target branch entry in the ``oompah.backports`` list.

    Stored in Backlog.md frontmatter as either:

    * A plain string (branch name only, implicitly ``waiting``)::

          oompah:
            backports: release/1.0

    * A list item with ``branch`` and optional tracking fields::

          oompah:
            backports:
              - branch: release/1.0
                status: pr_open
                task_id: TASK-100.1
                pr_url: https://github.com/org/repo/pull/42

    Attributes:
        branch: Target branch name (e.g. ``"release/1.0"``).
        status: Current lifecycle status of this pick.
        task_id: Identifier of the child backport task, once created.
        pr_url: URL of the cherry-pick PR, once opened.
    """

    branch: str
    status: ReleasePick = ReleasePick.WAITING
    task_id: str | None = None
    pr_url: str | None = None
    #: Resolved commit SHAs to cherry-pick (set by release_pick_commit_resolver).
    #: When populated, the cherry-pick step uses these directly; when empty the
    #: resolver must derive them from the source PR or branch.
    commits: list[str] = field(default_factory=list)

    def to_raw(self) -> str | dict[str, Any]:
        """Serialise to the canonical Backlog.md frontmatter form.

        Returns a plain string when only ``branch`` and the default
        ``waiting`` status are set (compact form); otherwise returns a
        dict with all populated fields.
        """
        if (
            self.status == ReleasePick.WAITING
            and self.task_id is None
            and self.pr_url is None
            and not self.commits
        ):
            return self.branch
        out: dict[str, Any] = {"branch": self.branch, "status": self.status.value}
        if self.task_id is not None:
            out["task_id"] = self.task_id
        if self.pr_url is not None:
            out["pr_url"] = self.pr_url
        if self.commits:
            out["commits"] = list(self.commits)
        return out

    @classmethod
    def from_raw(cls, raw: Any) -> "BackportEntry":
        """Parse a raw frontmatter value into a :class:`BackportEntry`.

        Accepts:
        * A plain string (branch name, status defaults to ``waiting``).
        * A mapping with ``branch`` key and optional ``status``, ``task_id``,
          ``pr_url``, ``commits`` fields.

        Args:
            raw: Raw value from Backlog frontmatter.

        Returns:
            A :class:`BackportEntry` parsed from *raw*.

        Raises:
            ValueError: When *raw* is a mapping missing the required
                ``branch`` key, or when *raw* is neither a string nor a
                mapping.
        """
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                raise ValueError("BackportEntry.branch must not be empty")
            return cls(branch=raw)

        if isinstance(raw, dict):
            branch = str(raw.get("branch") or "").strip()
            if not branch:
                raise ValueError(
                    f"BackportEntry dict missing required 'branch' key: {raw!r}"
                )
            raw_commits = raw.get("commits") or []
            if isinstance(raw_commits, str):
                raw_commits = [raw_commits]
            commits = [str(c).strip() for c in raw_commits if str(c).strip()]
            return cls(
                branch=branch,
                status=ReleasePick.from_raw(raw.get("status")),
                task_id=str(raw["task_id"]) if raw.get("task_id") else None,
                pr_url=str(raw["pr_url"]) if raw.get("pr_url") else None,
                commits=commits,
            )

        raise ValueError(
            f"Cannot parse BackportEntry from {type(raw).__name__!r}: {raw!r}"
        )


# ---------------------------------------------------------------------------
# BackportOf — oompah.backport_of field on child tasks
# ---------------------------------------------------------------------------


@dataclass
class BackportOf:
    """Value of the ``oompah.backport_of`` field on a child backport task.

    Links the child task back to the source task and mirrors the per-branch
    status from the parent's ``oompah.backports`` entry.

    Stored in Backlog.md frontmatter as either:

    * A plain string (source task identifier, status implicitly derived from
      the child task's own lifecycle)::

          oompah:
            backport_of: TASK-100

    * A mapping with ``source`` and optional ``status``::

          oompah:
            backport_of:
              source: TASK-100
              status: pr_open

    Attributes:
        source: Identifier of the source task (e.g. ``"TASK-100"``).
        status: Current lifecycle status mirroring the parent entry.
    """

    source: str
    status: ReleasePick = ReleasePick.WAITING

    def to_raw(self) -> str | dict[str, Any]:
        """Serialise to the canonical Backlog.md frontmatter form.

        Returns a plain string when ``status`` is ``waiting`` (compact
        form); otherwise returns a ``{"source": ..., "status": ...}`` dict.
        """
        if self.status == ReleasePick.WAITING:
            return self.source
        return {"source": self.source, "status": self.status.value}

    @classmethod
    def from_raw(cls, raw: Any) -> "BackportOf":
        """Parse the raw ``oompah.backport_of`` frontmatter value.

        Accepts:
        * A plain string (source task identifier, status defaults to
          ``waiting``).
        * A mapping with ``source`` key and optional ``status``.

        Args:
            raw: Raw value from Backlog frontmatter.

        Returns:
            A :class:`BackportOf` parsed from *raw*.

        Raises:
            ValueError: When *raw* is a mapping missing the required
                ``source`` key, or an unsupported type.
        """
        if isinstance(raw, str):
            source = raw.strip()
            if not source:
                raise ValueError("BackportOf.source must not be empty")
            return cls(source=source)

        if isinstance(raw, dict):
            source = str(raw.get("source") or "").strip()
            if not source:
                raise ValueError(
                    f"BackportOf dict missing required 'source' key: {raw!r}"
                )
            return cls(
                source=source,
                status=ReleasePick.from_raw(raw.get("status")),
            )

        raise ValueError(
            f"Cannot parse BackportOf from {type(raw).__name__!r}: {raw!r}"
        )


# ---------------------------------------------------------------------------
# Top-level parsing helpers
# ---------------------------------------------------------------------------


def parse_backports(raw: Any) -> list[BackportEntry]:
    """Parse the raw ``oompah.backports`` metadata value.

    Accepts ``None``, a scalar string, a list of strings, a list of dicts,
    or a mixed list.  All forms are normalised into a list of
    :class:`BackportEntry` objects.

    Args:
        raw: Raw value from ``tracker.get_metadata(identifier).get("oompah.backports")``.

    Returns:
        List of :class:`BackportEntry` objects.  Returns an empty list
        when *raw* is ``None`` or empty.

    Raises:
        ValueError: Propagated from :meth:`BackportEntry.from_raw` when an
            individual entry is malformed.
    """
    if raw is None:
        return []
    if isinstance(raw, (str, dict)):
        # Scalar — treat as single entry
        raw = [raw]
    entries: list[BackportEntry] = []
    for item in raw:
        entries.append(BackportEntry.from_raw(item))
    return entries


def parse_backport_of(raw: Any) -> "BackportOf | None":
    """Parse the raw ``oompah.backport_of`` metadata value.

    Args:
        raw: Raw value from ``tracker.get_metadata(identifier).get("oompah.backport_of")``.

    Returns:
        A :class:`BackportOf` object, or ``None`` when *raw* is ``None``
        or empty.

    Raises:
        ValueError: Propagated from :meth:`BackportOf.from_raw` when the
            value is present but malformed.
    """
    if raw is None or raw == "":
        return None
    return BackportOf.from_raw(raw)


def backports_to_raw(entries: list[BackportEntry]) -> list[Any]:
    """Serialise a list of :class:`BackportEntry` objects to raw frontmatter form.

    Each entry is serialised via :meth:`BackportEntry.to_raw`, producing
    either a plain string or a dict depending on which fields are populated.

    Args:
        entries: List of :class:`BackportEntry` objects.

    Returns:
        List of strings/dicts suitable for writing to Backlog frontmatter.
    """
    return [e.to_raw() for e in entries]
