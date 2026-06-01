"""Canonical Backlog.md lifecycle statuses used by oompah."""

from __future__ import annotations

from collections.abc import Iterable


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
