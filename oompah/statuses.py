"""Compatibility facade for canonical oompah lifecycle statuses.

The authoritative status, phase, disposition, transition, ownership, and
reassessment contract lives in :mod:`oompah.workflow_contract`.  Existing
callers may continue importing the historic names from this module while
lifecycle components migrate to the richer contract.
"""

from __future__ import annotations

from collections.abc import Iterable

from oompah.workflow_contract import (
    ARCHIVED,
    BACKLOG,
    CANONICAL_STATUSES,
    DECOMPOSED,
    DEFAULT_STATUS,
    DISPATCHABLE_STATUSES,
    DONE,
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    PROPOSED,
    READY_TO_INTEGRATE,
    REVIEW_STATUSES,
    TERMINAL_STATUSES,
    WAITING_STATUSES,
    WORKING_STATUSES,
    canonical_statuses_with,
    canonicalize_status,
    is_dispatchable_status,
    is_terminal_status,
    is_working_status,
    more_advanced_status,
    status_key,
    status_rank,
)

__all__ = [
    "ARCHIVED",
    "BACKLOG",
    "CANONICAL_STATUSES",
    "DECOMPOSED",
    "DEFAULT_STATUS",
    "DISPATCHABLE_STATUSES",
    "DONE",
    "DUPLICATE_CANDIDATE",
    "IN_PROGRESS",
    "IN_REVIEW",
    "IN_VALIDATION",
    "MERGED",
    "NEEDS_ANSWER",
    "NEEDS_CI_FIX",
    "NEEDS_HUMAN",
    "NEEDS_REBASE",
    "OPEN",
    "PROPOSED",
    "READY_TO_INTEGRATE",
    "REVIEW_STATUSES",
    "TERMINAL_STATUSES",
    "WAITING_STATUSES",
    "WORKING_STATUSES",
    "canonical_statuses_with",
    "canonicalize_status",
    "epic_rollup_state",
    "is_dispatchable_status",
    "is_terminal_status",
    "is_working_status",
    "more_advanced_status",
    "status_key",
    "status_rank",
]


# Child statuses that mean "work is actively underway" for epic rollup.
_ROLLUP_ACTIVE = frozenset(
    {
        IN_PROGRESS,
        NEEDS_ANSWER,
        NEEDS_HUMAN,
        NEEDS_CI_FIX,
        NEEDS_REBASE,
        IN_REVIEW,
        IN_VALIDATION,
        READY_TO_INTEGRATE,
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

    * no children (or all Proposed/Decomposed) → None (caller keeps the epic's own state)
    * all children Merged/Archived      → ``Merged`` (whole epic has landed)
    * all children terminal (Done/...)  → ``Done``   (complete → ready to merge)
    * any child actively working        → ``In Progress`` (beats Open: a mix of
      Open + In Progress rolls up to In Progress)
    * any child Open                    → ``Open``
    * all children Proposed             → ``Proposed``
    * all children Proposed/Backlog     → ``Backlog`` if any child reached Backlog
    * otherwise (e.g. some Done + some Backlog, none open/active) → ``In Progress``
      (the epic has started but isn't complete)
    """
    # Proposed work has not entered the implementation workflow yet.
    # Decomposed work is a superseded wrapper whose generated leaves carry
    # the actionable state. Neither should keep an epic active by itself.
    ignored = {PROPOSED, DECOMPOSED}
    canon = [
        canonicalize_status(s)
        for s in child_states
        if s is not None and canonicalize_status(s) not in ignored
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
    if cset <= {PROPOSED, BACKLOG}:
        return BACKLOG if BACKLOG in cset else PROPOSED
    return IN_PROGRESS
