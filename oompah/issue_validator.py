"""Deterministic readiness validator for proposed issues.

Before a proposed issue can enter Backlog it must pass this validator.
The validator is pure-function and produces the same structured result
for any given input — no LLM calls, no I/O side effects.

Design
------

Validation proceeds in four stages:

1. **Title check** — must be present, long enough, and not degenerate
   (a single word or a bare question).

2. **Common field check** — all issue types require a problem/purpose
   statement, a desired-behavior section, and acceptance criteria. The
   validator scans the markdown description for either a labeled heading
   (e.g. ``## Acceptance Criteria``) or a substantive inline section.
   Each missing field is recorded as a :class:`MissingField` with a
   ``suggested_fix`` so the author knows exactly what to add.

3. **Type-specific check** — bugs need reproduction detail (or an
   explicit note explaining its absence) and actual vs. expected
   behavior; feature requests need expected behavior and success
   criteria; chores and tasks are lighter but still require a work
   description and acceptance criteria.

4. **Scope classification** — the validator classifies the issue as one
   of :class:`ScopeClassification`:

   * ``small_task`` — default for focused, well-bounded work.
   * ``epic_needed`` — description spans multiple independent
     workstreams, mentions phases/milestones, or exceeds the single-
     session word threshold.
   * ``duplicate_candidate`` — title or description signals that an
     equivalent issue may already exist.
   * ``needs_human_owner_review`` — architectural decision, security
     implication, external dependency, or compliance concern detected.

``ready`` is ``True`` iff ``missing_fields`` is empty.  Warnings are
informational only and do not block readiness.

See lesserevil/oompah#279 for the originating issue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Recognised issue types (lower-case).
VALID_ISSUE_TYPES: frozenset[str] = frozenset(
    {"bug", "feature", "task", "chore", "epic"}
)

# Minimum title length in characters (including spaces).
_MIN_TITLE_CHARS = 10

# Minimum title word count.
_MIN_TITLE_WORDS = 3

# Word count above which we start looking for epic-scope signals.
_EPIC_WORD_THRESHOLD = 600

# Patterns for heading-delimited sections.  We match any markdown
# heading level (# through ######) followed by a keyword phrase,
# case-insensitively.
_ANY_HEADER_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)


def _section_re(*keywords: str) -> re.Pattern[str]:
    """Return a compiled regex that matches an H1-H6 heading for any of
    the given *keywords*.  Anchored at the start of a line."""
    alts = "|".join(re.escape(k) for k in keywords)
    return re.compile(
        rf"^#{{1,6}}\s*(?:{alts})\b.*$",
        re.IGNORECASE | re.MULTILINE,
    )


# Section detection regexes keyed by logical field name.
_SECTION_RES: dict[str, re.Pattern[str]] = {
    "problem_statement": _section_re(
        "problem", "problem statement", "background", "context",
        "motivation", "rationale", "overview", "summary", "description",
    ),
    "desired_behavior": _section_re(
        "desired behavior", "desired behaviour", "expected behavior",
        "expected behaviour", "goal", "goals", "proposed solution",
        "solution", "approach",
    ),
    "acceptance_criteria": _section_re(
        "acceptance criteria", "acceptance criterion", "success criteria",
        "success criterion", "ac", "done criteria", "definition of done",
        "dod",
    ),
    "repro_steps": _section_re(
        "steps to reproduce", "reproduction steps", "repro steps",
        "how to reproduce", "reproduce", "repro",
    ),
    "actual_behavior": _section_re(
        "actual behavior", "actual behaviour", "current behavior",
        "current behaviour", "observed behavior", "observed behaviour",
    ),
    "environment": _section_re(
        "environment", "env", "version", "setup", "system info",
    ),
}

# Patterns that indicate the author acknowledged they could not provide
# reproduction/environment detail.
_UNAVAILABLE_RE = re.compile(
    r"\b(not\s+(?:available|reproducible|applicable)|unable\s+to\s+reproduce"
    r"|n/a|cannot\s+reproduce|intermittent|flaky|no\s+repro"
    r"|reproduction\s+(?:not\s+)?(?:available|possible))\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Scope classification patterns
# ---------------------------------------------------------------------------

# Signals for ``epic_needed`` scope.
_EPIC_SCOPE_RE = re.compile(
    r"\b(phase[s]?|milestone[s]?|rewrite|redesign|overhaul|refactor\s+(?:the\s+)?entire"
    r"|multi[\s-]?(?:component|service|phase|stage)"
    r"|system[\s-]wide|platform[\s-](?:wide|level)"
    r"|large[\s-]scale|major\s+(?:refactor|overhaul|redesign|rework)"
    r"|series\s+of\s+(?:tasks|changes|issues))\b",
    re.IGNORECASE,
)

# Signals for ``duplicate_candidate`` scope.
_DUPLICATE_SIGNAL_RE = re.compile(
    r"\b(duplicate|dup\s+of|same\s+as\s+(?:issue|task|#)"
    r"|similar\s+to\s+(?:issue|task|#|the)"
    r"|already\s+(?:filed|exists|reported|implemented)"
    r"|copy\s+of|see\s+(?:also\s+)?(?:issue|task|#))\b",
    re.IGNORECASE,
)

# Signals for ``needs_human_owner_review`` scope.
_HUMAN_REVIEW_RE = re.compile(
    r"\b(architect(?:ure|ural)\s+decision|architect(?:ure|ural)\s+(?:change|choice|review)"
    r"|architectural\s+(?:decision|change|choice|review)"
    r"|security\s+(?:implications?|impacts?|concerns?|review|audit)"
    r"|compliance|legal\s+(?:review|implications?|requirement)"
    r"|gdpr|pii|personally\s+identifiable|privacy\s+(?:law|regulation|policy)"
    r"|breaking[\s-]changes?"
    r"|external\s+(?:vendor|dependency|team|stakeholder)"
    r"|governance|executive\s+(?:approval|sign[\s-]off)"
    r"|requires?\s+(?:a\s+)?(?:human|owner|manager|director)\s+(?:decision|approval|review))\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


class ScopeClassification(str, Enum):
    """Scope category assigned to a proposed issue by the validator."""

    SMALL_TASK = "small_task"
    """Default: focused, single-session implementation work."""

    EPIC_NEEDED = "epic_needed"
    """Issue spans multiple independent workstreams — should be an epic
    with child tasks, not a single task."""

    DUPLICATE_CANDIDATE = "duplicate_candidate"
    """Title or description signals an equivalent issue may already exist.
    An investigator should search for duplicates before accepting."""

    NEEDS_HUMAN_OWNER_REVIEW = "needs_human_owner_review"
    """Issue contains architectural, security, compliance, or governance
    concerns that require human sign-off before implementation."""


@dataclass
class MissingField:
    """A required field that is absent or insufficient.

    ``field`` is a short label (e.g. ``"acceptance criteria"``).
    ``reason`` explains why the field is required for this issue type.
    ``suggested_fix`` is a concrete instruction the author can follow to
    resolve the gap.
    """

    field: str
    reason: str
    suggested_fix: str

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "reason": self.reason,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class ValidationResult:
    """Outcome of :func:`validate_issue`.

    ``ready`` is ``True`` iff ``missing_fields`` is empty.
    ``warnings`` carry informational notes that don't block readiness.
    """

    ready: bool
    issue_type: str
    scope: ScopeClassification
    missing_fields: list[MissingField] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable representation."""
        return {
            "ready": self.ready,
            "issue_type": self.issue_type,
            "scope": self.scope.value,
            "missing_fields": [f.to_dict() for f in self.missing_fields],
            "warnings": list(self.warnings),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _word_count(text: str) -> int:
    """Return the number of whitespace-delimited tokens in *text*."""
    return len(text.split())


def _has_section(description: str, section_key: str) -> bool:
    """Return True iff *description* has a heading for *section_key*.

    Uses the pre-compiled patterns in :data:`_SECTION_RES`.
    """
    pat = _SECTION_RES.get(section_key)
    if pat is None:
        return False
    return bool(pat.search(description))


def _section_body(description: str, section_key: str) -> str:
    """Return the text body following the *section_key* heading.

    Returns an empty string when the section is absent.
    """
    pat = _SECTION_RES.get(section_key)
    if pat is None:
        return ""
    m = pat.search(description)
    if not m:
        return ""
    start = m.end()
    rest = description[start:]
    # Section ends at the next markdown heading.
    m2 = _ANY_HEADER_RE.search(rest)
    if m2:
        return rest[: m2.start()].strip()
    return rest.strip()


def _section_nonempty(description: str, section_key: str) -> bool:
    """Return True iff the section exists *and* contains non-trivial content.

    Trivial content: the body is empty, ``TBD``, ``TODO``, or ``N/A``
    (case-insensitive, optionally with surrounding whitespace/punctuation).
    Machine-marked placeholders (``<!-- oompah:placeholder … -->``) are also
    treated as absent so they never falsely satisfy a required-field check.
    """
    body = _section_body(description, section_key)
    if not body:
        return False
    # Machine-marked placeholders inserted by the intake normalizer are treated
    # as missing content, not as user-provided information.
    if "<!-- oompah:placeholder" in body:
        return False
    stripped = body.strip(" \t\n\r-*_#|.")
    trivial = re.fullmatch(r"(?:tbd|todo|n/?a|none|unknown|\?+)", stripped, re.IGNORECASE)
    return trivial is None and len(stripped) > 2


def _infer_issue_type(labels: list[str]) -> str:
    """Derive issue type from label list, returning ``"task"`` as default."""
    for label in labels:
        lower = (label or "").strip().lower()
        if lower in VALID_ISSUE_TYPES:
            return lower
        # Strip ``type:`` prefix used by github_tracker.
        if lower.startswith("type:") and lower[5:] in VALID_ISSUE_TYPES:
            return lower[5:]
    return "task"


def _classify_scope(title: str, description: str) -> ScopeClassification:
    """Return the :class:`ScopeClassification` for the given title+description.

    Checks are ordered: duplicate > human-review > epic > small-task.
    """
    combined = (title + "\n" + description).strip()

    if _DUPLICATE_SIGNAL_RE.search(combined):
        return ScopeClassification.DUPLICATE_CANDIDATE

    if _HUMAN_REVIEW_RE.search(combined):
        return ScopeClassification.NEEDS_HUMAN_OWNER_REVIEW

    # Epic signals: explicit keywords OR description too large for one session.
    if _EPIC_SCOPE_RE.search(combined) or _word_count(description) > _EPIC_WORD_THRESHOLD:
        return ScopeClassification.EPIC_NEEDED

    return ScopeClassification.SMALL_TASK


# ---------------------------------------------------------------------------
# Type-specific validators (return lists of MissingField)
# ---------------------------------------------------------------------------


def _validate_bug(description: str) -> list[MissingField]:
    """Return missing fields specific to bug reports."""
    missing: list[MissingField] = []

    # Reproduction steps.
    has_repro = _section_nonempty(description, "repro_steps")
    has_unavailable = bool(_UNAVAILABLE_RE.search(description))
    if not has_repro and not has_unavailable:
        missing.append(
            MissingField(
                field="reproduction steps",
                reason=(
                    "Bug reports need steps to reproduce the issue so it can be "
                    "confirmed and fixed reliably."
                ),
                suggested_fix=(
                    "Add a '## Steps to Reproduce' section with numbered steps, "
                    "or explain why reproduction steps are unavailable "
                    "(e.g. 'Intermittent — not reliably reproducible')."
                ),
            )
        )

    # Actual behavior.
    if not _section_nonempty(description, "actual_behavior"):
        # Fallback: accept if the description mentions "actual" or "observed"
        # inline.
        fallback_re = re.compile(
            r"\b(actual|observed|current)\s+(behavior|behaviour|output|result|error)\b",
            re.IGNORECASE,
        )
        if not fallback_re.search(description):
            missing.append(
                MissingField(
                    field="actual behavior",
                    reason=(
                        "Without knowing what currently happens, the bug cannot be "
                        "confirmed or differentiated from expected behavior."
                    ),
                    suggested_fix=(
                        "Add an '## Actual Behavior' section describing what "
                        "currently happens."
                    ),
                )
            )

    # Expected behavior (shared with features but mandatory for bugs too).
    has_desired = _section_nonempty(description, "desired_behavior")
    if not has_desired:
        fallback_re = re.compile(
            r"\b(should|expected|instead|want\s+it\s+to|supposed\s+to)\b",
            re.IGNORECASE,
        )
        if not fallback_re.search(description):
            missing.append(
                MissingField(
                    field="expected behavior",
                    reason=(
                        "Without a statement of expected behavior, 'fixed' is "
                        "undefined."
                    ),
                    suggested_fix=(
                        "Add a '## Expected Behavior' section describing what "
                        "should happen instead."
                    ),
                )
            )

    return missing


def _validate_feature(description: str) -> list[MissingField]:
    """Return missing fields specific to feature requests."""
    missing: list[MissingField] = []

    # Expected / desired behavior.
    if not _section_nonempty(description, "desired_behavior"):
        fallback_re = re.compile(
            r"\b(should|will|would|want|goal|allows?|enables?|provides?)\b",
            re.IGNORECASE,
        )
        if not fallback_re.search(description):
            missing.append(
                MissingField(
                    field="expected behavior",
                    reason=(
                        "Feature requests must describe what the system should do "
                        "after the change."
                    ),
                    suggested_fix=(
                        "Add a '## Expected Behavior' or '## Desired Behavior' "
                        "section describing what the feature should do."
                    ),
                )
            )

    # Success criteria / acceptance criteria are checked separately in
    # the common path, but we add a stronger note if the AC section is
    # also missing alongside desired_behavior.
    return missing


def _validate_chore_or_task(description: str) -> list[MissingField]:
    """Return missing fields specific to chore / task types.

    Chores and tasks are lighter than features/bugs: they need a work
    description (at least a few sentences of substance) but do not
    require dedicated reproduction or expected-behavior sections.
    """
    missing: list[MissingField] = []

    if _word_count(description) < 20:
        missing.append(
            MissingField(
                field="work description",
                reason=(
                    "A chore or task must describe the work to be done in "
                    "enough detail for an agent to act on it without further "
                    "clarification."
                ),
                suggested_fix=(
                    "Expand the description to include what needs to be done, "
                    "why, and any important constraints or context."
                ),
            )
        )

    return missing


def _validate_epic(description: str) -> list[MissingField]:
    """Return missing fields specific to epics.

    Epics do not need the same level of per-task detail, but must have
    enough context for an epic_planner agent to decompose them.
    """
    missing: list[MissingField] = []

    if not _section_nonempty(description, "problem_statement") and _word_count(description) < 30:
        missing.append(
            MissingField(
                field="epic overview",
                reason=(
                    "Epics must describe the high-level goal so the planner "
                    "knows what child tasks to create."
                ),
                suggested_fix=(
                    "Add a '## Problem' or '## Overview' section summarising "
                    "the epic's goal and scope."
                ),
            )
        )

    return missing


# ---------------------------------------------------------------------------
# Common field validator (all types)
# ---------------------------------------------------------------------------


def _validate_common(title: str, description: str) -> list[MissingField]:
    """Return missing fields that apply to every issue type."""
    missing: list[MissingField] = []

    # Title checks.
    stripped_title = title.strip()
    if not stripped_title:
        missing.append(
            MissingField(
                field="title",
                reason="Every issue must have a non-empty title.",
                suggested_fix="Provide a concise, specific title describing the issue.",
            )
        )
        return missing  # No point checking further without a title.

    if len(stripped_title) < _MIN_TITLE_CHARS:
        missing.append(
            MissingField(
                field="title",
                reason=(
                    f"Title is too short ({len(stripped_title)} chars; "
                    f"minimum {_MIN_TITLE_CHARS})."
                ),
                suggested_fix=(
                    "Expand the title to clearly name the feature, bug, or task. "
                    "Example: 'Fix login redirect loop on mobile Safari' rather "
                    "than 'Login bug'."
                ),
            )
        )

    title_word_count = _word_count(stripped_title)
    if title_word_count < _MIN_TITLE_WORDS and not missing:
        missing.append(
            MissingField(
                field="title",
                reason=(
                    f"Title contains only {title_word_count} word(s); a meaningful "
                    "title needs at least 3 words."
                ),
                suggested_fix=(
                    "Write a title that names the component AND the change, "
                    "e.g. 'Add OAuth2 login flow' or 'Fix crash on empty input'."
                ),
            )
        )

    # Problem / purpose statement.
    if not _section_nonempty(description, "problem_statement"):
        # Fallback: accept a description of >= 20 words without a heading.
        if _word_count(description) < 20:
            missing.append(
                MissingField(
                    field="problem statement",
                    reason=(
                        "Every issue must explain what problem it solves or what "
                        "goal it achieves."
                    ),
                    suggested_fix=(
                        "Add a '## Problem' section (or a substantive opening "
                        "paragraph) describing the issue's purpose."
                    ),
                )
            )

    # Acceptance criteria.
    if not _section_nonempty(description, "acceptance_criteria"):
        # Fallback: a bullet list at the start of a line with substance.
        # The ^[-*] anchor is important: it prevents HTML comment content
        # (e.g. <!-- oompah:placeholder --> markers) from falsely satisfying
        # this check by matching the '--' inside the comment delimiters.
        inline_ac_re = re.compile(
            r"^[-*]\s+.{15,}",  # At least one bullet with substance
            re.MULTILINE,
        )
        inline_ac_matches = inline_ac_re.findall(description)
        has_inline_ac = len(inline_ac_matches) >= 2
        if not has_inline_ac:
            missing.append(
                MissingField(
                    field="acceptance criteria",
                    reason=(
                        "Acceptance criteria define when the issue is done and "
                        "allow the completion verifier to check the agent's work."
                    ),
                    suggested_fix=(
                        "Add an '## Acceptance Criteria' section with a bullet "
                        "list of testable conditions, e.g.:\n"
                        "- `validate_issue()` returns `ready=True` for a well-formed issue\n"
                        "- Tests in `tests/test_issue_validator.py` pass"
                    ),
                )
            )

    return missing


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def validate_issue(
    *,
    title: str,
    description: str | None = None,
    issue_type: str | None = None,
    labels: list[str] | None = None,
) -> ValidationResult:
    """Validate a proposed issue for readiness to enter Backlog.

    Parameters
    ----------
    title:
        The issue title (mandatory).
    description:
        Full markdown body of the issue.  ``None`` is treated as empty.
    issue_type:
        One of ``"bug"``, ``"feature"``, ``"task"``, ``"chore"``,
        ``"epic"``.  When ``None``, the type is inferred from
        *labels* (falling back to ``"task"``).
    labels:
        Optional list of label strings (e.g. ``["type:bug", "priority:0"]``).
        Used only for type inference when *issue_type* is not supplied.

    Returns
    -------
    ValidationResult
        ``ready`` is ``True`` iff ``missing_fields`` is empty.
    """
    desc = (description or "").strip()
    labels = labels or []

    # 1. Resolve issue type.
    effective_type: str
    warnings: list[str] = []
    if issue_type:
        norm = issue_type.strip().lower()
        if norm not in VALID_ISSUE_TYPES:
            warnings.append(
                f"Unknown issue type '{issue_type}'; treating as 'task'. "
                f"Valid types: {', '.join(sorted(VALID_ISSUE_TYPES))}."
            )
            effective_type = "task"
        else:
            effective_type = norm
    else:
        effective_type = _infer_issue_type(labels)

    # 2. Scope classification (independent of field validation).
    scope = _classify_scope(title, desc)

    # 3. Common field checks.
    missing: list[MissingField] = _validate_common(title, desc)

    # 4. Type-specific checks (only when we have a title to work with).
    if not any(f.field == "title" for f in missing):
        if effective_type == "bug":
            missing.extend(_validate_bug(desc))
        elif effective_type == "feature":
            missing.extend(_validate_feature(desc))
        elif effective_type in {"chore", "task"}:
            missing.extend(_validate_chore_or_task(desc))
        elif effective_type == "epic":
            missing.extend(_validate_epic(desc))

    # 5. Informational warnings.
    if scope == ScopeClassification.EPIC_NEEDED and effective_type != "epic":
        warnings.append(
            "Issue may be too large for a single task (epic scope detected). "
            "Consider converting to an epic with child tasks."
        )
    if scope == ScopeClassification.DUPLICATE_CANDIDATE:
        warnings.append(
            "Issue body mentions a possible duplicate. "
            "Search existing issues before accepting."
        )
    if scope == ScopeClassification.NEEDS_HUMAN_OWNER_REVIEW:
        warnings.append(
            "Issue contains architectural, security, or compliance signals. "
            "A human owner should review before dispatching to an agent."
        )

    return ValidationResult(
        ready=len(missing) == 0,
        issue_type=effective_type,
        scope=scope,
        missing_fields=missing,
        warnings=warnings,
    )
