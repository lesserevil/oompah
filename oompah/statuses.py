"""Canonical Backlog.md lifecycle statuses used by oompah."""

from __future__ import annotations

from collections.abc import Iterable


PROPOSED = "Proposed"
BACKLOG = "Backlog"
OPEN = "Open"
IN_PROGRESS = "In Progress"
NEEDS_ANSWER = "Needs Answer"
NEEDS_HUMAN = "Needs Human"
NEEDS_CI_FIX = "Needs CI Fix"
NEEDS_REBASE = "Needs Rebase"
IN_REVIEW = "In Review"
DECOMPOSED = "Decomposed"
DUPLICATE_CANDIDATE = "Duplicate Candidate"
DONE = "Done"
MERGED = "Merged"
ARCHIVED = "Archived"

CANONICAL_STATUSES: tuple[str, ...] = (
    PROPOSED,
    BACKLOG,
    OPEN,
    IN_PROGRESS,
    NEEDS_ANSWER,
    NEEDS_HUMAN,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
    IN_REVIEW,
    DECOMPOSED,
    DUPLICATE_CANDIDATE,
    DONE,
    MERGED,
    ARCHIVED,
)

DEFAULT_STATUS = BACKLOG
DISPATCHABLE_STATUSES: frozenset[str] = frozenset({
    OPEN,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
})
WORKING_STATUSES: frozenset[str] = frozenset({IN_PROGRESS})
WAITING_STATUSES: frozenset[str] = frozenset({NEEDS_ANSWER, NEEDS_HUMAN})
REVIEW_STATUSES: frozenset[str] = frozenset({
    IN_REVIEW,
    NEEDS_CI_FIX,
    NEEDS_REBASE,
})
TERMINAL_STATUSES: frozenset[str] = frozenset({DONE, MERGED, ARCHIVED})


def status_key(status: str | None) -> str:
    return str(status or "").strip().lower().replace("-", " ").replace("_", " ")


_ALIASES = {
    "": DEFAULT_STATUS,
    "proposed": PROPOSED,
    "to do": BACKLOG,
    "todo": BACKLOG,
    "deferred": BACKLOG,
    "backlog": BACKLOG,
    "open": OPEN,
    "in progress": IN_PROGRESS,
    "doing": IN_PROGRESS,
    "started": IN_PROGRESS,
    "asking question": NEEDS_ANSWER,
    "asking_question": NEEDS_ANSWER,
    "needs answer": NEEDS_ANSWER,
    "needs info": NEEDS_ANSWER,
    "needs information": NEEDS_ANSWER,
    "human only": NEEDS_HUMAN,
    "human-only": NEEDS_HUMAN,
    "needs human": NEEDS_HUMAN,
    "ci fix": NEEDS_CI_FIX,
    "ci-fix": NEEDS_CI_FIX,
    "needs ci fix": NEEDS_CI_FIX,
    "merge conflict": NEEDS_REBASE,
    "merge-conflict": NEEDS_REBASE,
    "needs rebase": NEEDS_REBASE,
    "in review": IN_REVIEW,
    "review": IN_REVIEW,
    "decomposed": DECOMPOSED,
    "duplicate candidate": DUPLICATE_CANDIDATE,
    "duplicate-candidate": DUPLICATE_CANDIDATE,
    "closed": DONE,
    "done": DONE,
    "merged": MERGED,
    "archive:yes": ARCHIVED,
    "archived": ARCHIVED,
}


def canonicalize_status(status: str | None) -> str:
    """Return the canonical oompah status for a user or legacy value."""
    key = status_key(status)
    return _ALIASES.get(key, str(status or DEFAULT_STATUS).strip() or DEFAULT_STATUS)


def canonical_statuses_with(existing: Iterable[str] | None = None) -> list[str]:
    """Return canonical statuses plus non-legacy custom statuses.

    ``To Do``/``deferred`` are intentionally not preserved as custom
    statuses because they are compatibility aliases for ``Backlog``.
    """
    values = list(CANONICAL_STATUSES)
    seen = {status_key(value) for value in values}
    for raw in existing or []:
        value = str(raw).strip()
        if not value:
            continue
        canonical = canonicalize_status(value)
        key = status_key(canonical)
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
    return values


def is_dispatchable_status(status: str | None) -> bool:
    return canonicalize_status(status) in DISPATCHABLE_STATUSES


def is_working_status(status: str | None) -> bool:
    return canonicalize_status(status) in WORKING_STATUSES


def is_terminal_status(status: str | None) -> bool:
    return canonicalize_status(status) in TERMINAL_STATUSES


# Workflow rank for "which status is further along" comparisons.
_STATUS_RANK = {s: i for i, s in enumerate(CANONICAL_STATUSES)}


def status_rank(status: str | None) -> int:
    """Position of *status* in the canonical workflow order, or -1 if unknown."""
    return _STATUS_RANK.get(canonicalize_status(status), -1)


def more_advanced_status(a: str | None, b: str | None) -> str:
    """Return whichever of *a*/*b* is further along the workflow (ties → a)."""
    return a if status_rank(a) >= status_rank(b) else b  # type: ignore[return-value]


# Child statuses that mean "work is actively underway" for epic rollup.
_ROLLUP_ACTIVE = frozenset(
    {
        IN_PROGRESS,
        NEEDS_ANSWER,
        NEEDS_HUMAN,
        NEEDS_CI_FIX,
        NEEDS_REBASE,
        IN_REVIEW,
        DECOMPOSED,
        DUPLICATE_CANDIDATE,
    }
)


def epic_rollup_state(child_states: Iterable[str | None]) -> str | None:
    """Derive an epic's state from its children's statuses.

    ``Proposed`` children are excluded before computing the rollup because
    ``Proposed`` is a pre-backlog intake state: work that has not yet been
    accepted for implementation.  A proposed child should not make an epic
    look active or complete — the epic's own state is used instead when all
    remaining children are proposed.

    Precedence (per the agreed model):

    * no children (or all Proposed)     → None (caller keeps the epic's own state)
    * all children Merged/Archived      → ``Merged`` (whole epic has landed)
    * all children terminal (Done/...)  → ``Done``   (complete → ready to merge)
    * any child actively working        → ``In Progress`` (beats Open: a mix of
      Open + In Progress rolls up to In Progress)
    * any child Open                    → ``Open``
    * all children Backlog              → ``Backlog``
    * otherwise (e.g. some Done + some Backlog, none open/active) → ``In Progress``
      (the epic has started but isn't complete)
    """
    canon = [
        canonicalize_status(s)
        for s in child_states
        if s is not None and canonicalize_status(s) != PROPOSED
    ]
    if not canon:
        return None
    cset = set(canon)
    if cset <= {MERGED, ARCHIVED}:
        return MERGED
    if cset <= TERMINAL_STATUSES:
        return DONE
    if cset & _ROLLUP_ACTIVE:
        return IN_PROGRESS
    if OPEN in cset:
        return OPEN
    if cset == {BACKLOG}:
        return BACKLOG
    return IN_PROGRESS
