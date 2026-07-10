"""Release-pick target branch validation (TASK-454.3).

Validates that requested release-pick target branches:

1. Match at least one of the project's configured branch patterns
   (the ``branches`` list on the :class:`~oompah.models.Project`).
2. Are not the project's protected default (source) branch unless the
   issue explicitly opts in via the ``backport:allow-source`` label.

The module exposes two public entry points:

* :func:`validate_release_pick_target` — validates a single issue's
  ``target_branch`` field. Called from ``Orchestrator._should_dispatch``
  to gate dispatch on issues that would create a PR against an unknown
  or untracked branch.

* :func:`validate_backports_list` — validates the list of branch names
  stored in the ``oompah.backports`` frontmatter field of a source issue.
  Each entry must match a tracked branch pattern and must not be the
  default (source) branch.

Both return :class:`ReleaseBranchValidationResult` objects with
``valid=True/False``, a machine-readable ``reason`` code, and a
human-readable ``error`` string suitable for posting as a task comment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from oompah.models import Issue, Project
from oompah.projects import _sanitize_identifier

logger = logging.getLogger(__name__)

# Label that explicitly allows a release-pick task to target the
# project's default (source) branch.  Without this label, targeting
# the source branch in a backport context is rejected as a likely error.
ALLOW_SOURCE_LABEL = "backport:allow-source"

# Label prefix and exact label that identify an issue as a backport
# (cherry-pick) task for the purpose of source-only branch protection.
_BACKPORT_LABEL = "backport"
_BACKPORT_LABEL_PREFIX = "backport:"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ReleaseBranchValidationResult:
    """Outcome of validating one release-pick target branch.

    Attributes:
        valid: True when the target is acceptable; False when it must be
            rejected with ``error`` / ``reason`` explaining why.
        target_branch: The branch name that was examined (``None`` when
            ``issue.target_branch`` was unset and validation was skipped).
        error: Human-readable description of the failure.  Empty when
            ``valid=True``.  Suitable for posting as a task comment.
        reason: Machine-readable failure code.  One of:

            * ``""``              — no error (valid)
            * ``"untracked_branch"`` — branch doesn't match any configured
              pattern in ``project.branches``
            * ``"source_only_branch"`` — branch equals the project's
              default branch; release picks must not target the source trunk
              unless ``ALLOW_SOURCE_LABEL`` is present on the issue
    """

    valid: bool
    target_branch: str | None = None
    error: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_release_pick_target(
    issue: Issue,
    project: Project,
    *,
    tracker: Any | None = None,
) -> ReleaseBranchValidationResult:
    """Validate that *issue*'s ``target_branch`` is valid for *project*.

    The function is intentionally lightweight so it can be called from
    the hot dispatch loop without I/O.  Pass a tracker instance only when
    the caller already holds one (e.g. during API request handling) so
    backport metadata can be checked directly; otherwise the function
    falls back to label inspection on the ``Issue`` object.

    Returns:
        :class:`ReleaseBranchValidationResult` with ``valid=True`` when:

        * ``issue.target_branch`` is ``None``/empty (not a release-pick
          scenario — normal dispatch proceeds unimpeded), OR
        * the branch matches a configured pattern and is not a forbidden
          source-only target.

        ``valid=False`` with an actionable ``error`` message when the
        target is unknown or untracked, or when it points at the source
        branch without an explicit opt-in label.

    Args:
        issue: The issue whose ``target_branch`` to validate.
        project: The project the issue belongs to.
        tracker: Optional tracker instance for richer backport-metadata
            detection.  When ``None``, backport status is inferred from
            ``issue.labels``.
    """
    target = (issue.target_branch or "").strip()

    if not target:
        # No target_branch set → not a release-pick context; skip
        return ReleaseBranchValidationResult(valid=True, target_branch=None)

    if _is_generated_epic_target_branch(issue, target):
        return ReleaseBranchValidationResult(valid=True, target_branch=target)

    # ------------------------------------------------------------------
    # 1. Branch-pattern check — the target must match at least one of
    #    the project's configured patterns (e.g. "release/*", "main").
    # ------------------------------------------------------------------
    if not project.matches_branch(target):
        tracked = list(project.branches) or [project.default_branch or "main"]
        patterns_str = ", ".join(f"'{p}'" for p in tracked)
        logger.debug(
            "release_pick_validation: issue=%s target=%r untracked (patterns: %s)",
            issue.identifier,
            target,
            patterns_str,
        )
        return ReleaseBranchValidationResult(
            valid=False,
            target_branch=target,
            reason="untracked_branch",
            error=(
                f"Target branch '{target}' does not match any configured branch "
                f"pattern for project '{project.name}'. "
                f"Tracked patterns: {patterns_str}. "
                f"To fix: add a matching pattern to the project's 'branches' list "
                f"or update the 'oompah.target_branch' frontmatter field in this task."
            ),
        )

    # ------------------------------------------------------------------
    # 2. Source-only branch protection — the default branch is where code
    #    is authored; release-pick tasks must target downstream release or
    #    hotfix branches, not the development trunk.
    #
    #    This check only fires for issues identified as backport/release-pick
    #    tasks (via metadata or label) so that normal tasks targeting the
    #    default branch are unaffected.
    # ------------------------------------------------------------------
    default = (project.default_branch or "").strip()
    if default and target == default and _is_release_pick_issue(issue, tracker):
        labels = _label_set(issue)
        if ALLOW_SOURCE_LABEL not in labels:
            logger.debug(
                "release_pick_validation: issue=%s target=%r is source-only branch",
                issue.identifier,
                target,
            )
            return ReleaseBranchValidationResult(
                valid=False,
                target_branch=target,
                reason="source_only_branch",
                error=(
                    f"Target branch '{target}' is the project's default (source) "
                    f"branch and must not be used as a release-pick target. "
                    f"Release picks should target release or hotfix branches. "
                    f"If this is intentional, add the '{ALLOW_SOURCE_LABEL}' label "
                    f"to this task to bypass this check."
                ),
            )

    return ReleaseBranchValidationResult(valid=True, target_branch=target)


def _is_generated_epic_target_branch(issue: Issue, target_branch: str) -> bool:
    """Return True for oompah-owned epic branches generated from parent_id."""
    parent_id = (getattr(issue, "parent_id", None) or "").strip()
    if not parent_id:
        return False
    expected = f"epic-{_sanitize_identifier(parent_id)}"
    return target_branch == expected


def validate_backports_list(
    backports: list[str] | Any,
    project: Project,
) -> list[ReleaseBranchValidationResult]:
    """Validate a list of release-pick targets from ``oompah.backports``.

    Each entry in ``backports`` must:

    * Match at least one configured branch pattern in ``project.branches``.
    * Not equal the project's default (source) branch — backports always
      flow *from* the source branch *to* release/hotfix branches, never
      the reverse.

    Args:
        backports: List (or scalar string) of branch names from the
            ``oompah.backports`` frontmatter field.  Scalar strings are
            treated as a one-element list.  ``None`` and empty lists
            return an empty results list.
        project: The project to validate against.

    Returns:
        One :class:`ReleaseBranchValidationResult` per non-empty entry.
        Results with ``valid=False`` carry actionable error messages.
        An empty list is returned when ``backports`` is ``None``/empty.
    """
    if not backports:
        return []

    # Accept scalar (single branch string) or list
    if isinstance(backports, str):
        entries: list[str] = [backports]
    else:
        try:
            entries = [str(b) for b in backports]
        except TypeError:
            entries = [str(backports)]

    results: list[ReleaseBranchValidationResult] = []
    default = (project.default_branch or "").strip()
    tracked = list(project.branches) or [default or "main"]
    patterns_str = ", ".join(f"'{p}'" for p in tracked)

    for raw in entries:
        branch = raw.strip()
        if not branch:
            continue

        if not project.matches_branch(branch):
            logger.debug(
                "validate_backports_list: branch=%r untracked for project=%s",
                branch,
                project.name,
            )
            results.append(ReleaseBranchValidationResult(
                valid=False,
                target_branch=branch,
                reason="untracked_branch",
                error=(
                    f"Backport target '{branch}' does not match any configured "
                    f"branch pattern for project '{project.name}'. "
                    f"Tracked patterns: {patterns_str}."
                ),
            ))
        elif default and branch == default:
            logger.debug(
                "validate_backports_list: branch=%r is source-only for project=%s",
                branch,
                project.name,
            )
            results.append(ReleaseBranchValidationResult(
                valid=False,
                target_branch=branch,
                reason="source_only_branch",
                error=(
                    f"Backport target '{branch}' is the project's default (source) "
                    f"branch. Release picks must flow from the source branch to "
                    f"release or hotfix branches, not back to the development trunk."
                ),
            ))
        else:
            results.append(ReleaseBranchValidationResult(
                valid=True,
                target_branch=branch,
            ))

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _label_set(issue: Issue) -> frozenset[str]:
    """Return a normalised (lower-cased, stripped) frozenset of issue labels."""
    return frozenset((l or "").strip().lower() for l in (issue.labels or []))


def _is_release_pick_issue(issue: Issue, tracker: Any | None) -> bool:
    """Return True if the issue appears to be a release-pick (backport) task.

    Attempts two detection strategies:

    1. **Tracker metadata** (most accurate): if *tracker* is provided,
       look up ``oompah.backport_of`` and ``oompah.backports`` in the
       task's frontmatter.  Either field being present marks the issue
       as backport-related.
    2. **Label fallback**: inspect ``issue.labels`` for the ``backport``
       label or any label starting with ``backport:``.

    Returns ``False`` (skipping the protection) when detection fails so
    that false-positives never block legitimate work.
    """
    # Strategy 1: tracker metadata
    if tracker is not None:
        try:
            meta = tracker.get_metadata(issue.identifier) or {}
            if meta.get("oompah.backport_of") or meta.get("oompah.backports"):
                return True
        except Exception:  # pragma: no cover — defensive, fail-open
            pass

    # Strategy 2: label-based heuristic
    labels = _label_set(issue)
    if _BACKPORT_LABEL in labels:
        return True
    if any(lbl.startswith(_BACKPORT_LABEL_PREFIX) for lbl in labels):
        return True

    return False
