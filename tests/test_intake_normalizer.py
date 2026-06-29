"""Tests for oompah.intake_normalizer (OOMPAH-159).

Coverage targets:
- Pure normalize_body() function:
  - Malformed nested-heading bodies like TRICKLE-8 (H2 inside Summary area).
  - Underspecified bodies that get marked placeholders for missing fields.
  - Complete bodies that need no change (idempotency).
  - Unrecognized sections preserved in ## Notes.
  - Extra preamble text in Summary preserved.
  - Multiple heading aliases mapping to the same canonical field.
  - Issue-type-specific required fields (bug, feature, task, chore, epic).
  - Placeholder detection helpers: is_placeholder_content, make_placeholder.
- normalize_native_task() integration helper:
  - No-op for trackers without get_raw_body / set_raw_body.
  - Calls set_raw_body when body changes.
  - No-op when body is unchanged.
  - Graceful handling of None body.
- Validator integration:
  - _section_nonempty() returns False for placeholder content.
  - Validator marks placeholder sections as missing fields.
- GitHub intake regression:
  - Normalization does NOT rewrite the GitHub issue body.
  - Only the internal native task body is rewritten.
"""

from __future__ import annotations

import pytest

from oompah.intake_normalizer import (
    CANONICAL_HEADINGS,
    PLACEHOLDER_MARKER,
    REQUIRED_BY_TYPE,
    is_placeholder_content,
    make_placeholder,
    normalize_body,
    normalize_native_task,
)
from oompah.issue_validator import _section_nonempty, validate_issue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ph(field: str) -> str:
    return make_placeholder(field)


def _has_h3(body: str, heading: str) -> bool:
    return f"### {heading}" in body


def _summary_content(body: str) -> str:
    """Extract the content of ## Summary from a normalized body."""
    import re

    pattern = re.compile(r"(?ms)^##\s+Summary\s*$\n?(.*?)(?=^##\s+|\Z)")
    m = pattern.search(body)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Placeholder helpers
# ---------------------------------------------------------------------------


class TestPlaceholderHelpers:
    def test_make_placeholder_contains_marker(self) -> None:
        ph = make_placeholder("acceptance_criteria")
        assert PLACEHOLDER_MARKER in ph

    def test_make_placeholder_contains_field_name(self) -> None:
        ph = make_placeholder("acceptance_criteria")
        assert 'field="acceptance_criteria"' in ph

    def test_make_placeholder_human_label(self) -> None:
        ph = make_placeholder("problem_statement")
        assert "problem statement" in ph

    def test_is_placeholder_content_true(self) -> None:
        ph = make_placeholder("acceptance_criteria")
        assert is_placeholder_content(ph)

    def test_is_placeholder_content_false_for_real_content(self) -> None:
        assert not is_placeholder_content("- AC1: the system validates input")

    def test_is_placeholder_content_false_for_empty(self) -> None:
        assert not is_placeholder_content("")

    def test_is_placeholder_case_insensitive(self) -> None:
        assert is_placeholder_content("<!-- OOMPAH:PLACEHOLDER field='x' -->")


# ---------------------------------------------------------------------------
# normalize_body() — TRICKLE-8 regression (malformed nested H2 in Summary)
# ---------------------------------------------------------------------------


TRICKLE8_BODY = """\
## Summary

## Summary
GitHub issue content with real information.

## Acceptance Criteria
- AC1: the system does X
- AC2: the system does Y

## External GitHub Issue
- URL: https://github.com/example/repo/issues/268
- Requestor: @alice
- Reference: example/repo#268

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-27 03:20
---
Imported into oompah.
---
<!-- COMMENTS:END -->
"""


class TestTrickle8Regression:
    """Malformed body where H2 headings inside Summary area break _section()."""

    def test_was_changed(self) -> None:
        _, changed = normalize_body(TRICKLE8_BODY, "task")
        assert changed

    def test_summary_contains_problem(self) -> None:
        body, _ = normalize_body(TRICKLE8_BODY, "task")
        content = _summary_content(body)
        assert "GitHub issue content" in content

    def test_summary_contains_acceptance_criteria(self) -> None:
        body, _ = normalize_body(TRICKLE8_BODY, "task")
        content = _summary_content(body)
        assert _has_h3(content, "Acceptance Criteria")
        assert "AC1" in content
        assert "AC2" in content

    def test_external_github_issue_preserved(self) -> None:
        body, _ = normalize_body(TRICKLE8_BODY, "task")
        assert "## External GitHub Issue" in body
        assert "https://github.com/example/repo/issues/268" in body

    def test_comments_preserved_verbatim(self) -> None:
        body, _ = normalize_body(TRICKLE8_BODY, "task")
        assert "<!-- COMMENTS:BEGIN -->" in body
        assert "Imported into oompah." in body
        assert "<!-- COMMENTS:END -->" in body

    def test_no_placeholder_when_content_present(self) -> None:
        body, _ = normalize_body(TRICKLE8_BODY, "task")
        content = _summary_content(body)
        # Both required fields are present — no placeholder expected.
        assert PLACEHOLDER_MARKER not in content

    def test_trivial_default_acceptance_criteria_discarded(self) -> None:
        """The default-template '- [ ] Define acceptance criteria.' is discarded."""
        body, _ = normalize_body(TRICKLE8_BODY, "task")
        content = _summary_content(body)
        assert "Define acceptance criteria" not in content

    def test_duplicate_h2_summary_not_in_output(self) -> None:
        """The malformed inner ## Summary heading should not appear in output."""
        body, _ = normalize_body(TRICKLE8_BODY, "task")
        # Only one ## Summary should remain at the top level.
        assert body.count("\n## Summary") <= 1


# ---------------------------------------------------------------------------
# normalize_body() — placeholder insertion for missing required fields
# ---------------------------------------------------------------------------


MISSING_AC_BODY = """\
## Summary

### Problem

The system crashes when the user provides empty input.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
"""


class TestPlaceholderInsertion:
    def test_placeholder_inserted_for_missing_ac(self) -> None:
        body, _ = normalize_body(MISSING_AC_BODY, "task")
        content = _summary_content(body)
        assert PLACEHOLDER_MARKER in content
        assert 'field="acceptance_criteria"' in content

    def test_problem_content_preserved(self) -> None:
        body, _ = normalize_body(MISSING_AC_BODY, "task")
        content = _summary_content(body)
        assert "crashes when the user provides empty input" in content

    def test_was_changed_for_missing_ac(self) -> None:
        _, changed = normalize_body(MISSING_AC_BODY, "task")
        assert changed

    def test_placeholder_inserted_for_missing_problem_statement(self) -> None:
        body_no_problem = """\
## Summary

### Acceptance Criteria

- [ ] AC1: the system validates input.
- [ ] AC2: error is shown.

## Notes
"""
        body, _ = normalize_body(body_no_problem, "task")
        content = _summary_content(body)
        assert PLACEHOLDER_MARKER in content
        assert 'field="problem_statement"' in content

    def test_epic_only_requires_problem_statement(self) -> None:
        body_epic = """\
## Summary

### Problem

This is a large-scale refactor of the authentication system.

## Notes
"""
        body, changed = normalize_body(body_epic, "epic")
        content = _summary_content(body)
        # AC placeholder should NOT be inserted for epics.
        assert 'field="acceptance_criteria"' not in content

    def test_bug_type_has_correct_required_fields(self) -> None:
        assert "problem_statement" in REQUIRED_BY_TYPE["bug"]
        assert "acceptance_criteria" in REQUIRED_BY_TYPE["bug"]


# ---------------------------------------------------------------------------
# normalize_body() — complete issues that need no change
# ---------------------------------------------------------------------------


CANONICAL_BODY = """\
## Summary

### Problem

The system crashes on empty input.

### Acceptance Criteria

- [ ] Empty input shows a validation error.
- [ ] No crash occurs.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-29 12:00
---
Good issue.
---
<!-- COMMENTS:END -->
"""


class TestCanonicalBodyIdempotency:
    def test_no_change_on_canonical_body(self) -> None:
        _, changed = normalize_body(CANONICAL_BODY, "task")
        # The body already has the canonical structure; no rewrite needed.
        assert not changed

    def test_idempotent_double_normalization(self) -> None:
        body1, _ = normalize_body(CANONICAL_BODY, "task")
        body2, changed2 = normalize_body(body1, "task")
        assert not changed2
        assert _summary_content(body1) == _summary_content(body2)

    def test_all_content_preserved(self) -> None:
        body, _ = normalize_body(CANONICAL_BODY, "task")
        assert "crashes on empty input" in body
        assert "Empty input shows a validation error" in body
        assert "Good issue." in body


# ---------------------------------------------------------------------------
# normalize_body() — unrecognized sections go to Notes
# ---------------------------------------------------------------------------


BODY_WITH_EXTRA_SECTIONS = """\
## Summary

### Problem

The widget rendering is broken.

### Design Notes

These are internal design notes that don't fit any canonical section.

### Acceptance Criteria

- [ ] Widget renders correctly.

## Notes

Original notes here.
"""


class TestUnrecognizedSections:
    def test_unrecognized_section_preserved_in_summary(self) -> None:
        body, _ = normalize_body(BODY_WITH_EXTRA_SECTIONS, "task")
        content = _summary_content(body)
        assert "Design Notes" in content
        assert "internal design notes" in content

    def test_canonical_fields_still_present(self) -> None:
        body, _ = normalize_body(BODY_WITH_EXTRA_SECTIONS, "task")
        content = _summary_content(body)
        assert "widget rendering is broken" in content
        assert "Widget renders correctly" in content


# ---------------------------------------------------------------------------
# normalize_body() — heading keyword aliases
# ---------------------------------------------------------------------------


class TestHeadingAliases:
    def test_background_maps_to_problem_statement(self) -> None:
        body = """\
## Summary

### Background

The system does not validate input.

### Acceptance Criteria

- AC1
- AC2

## Notes
"""
        normalized, _ = normalize_body(body, "task")
        content = _summary_content(normalized)
        assert _has_h3(content, "Problem")
        assert "does not validate input" in content

    def test_desired_behavior_alias(self) -> None:
        body = """\
## Summary

### Problem

Bug here.

### Expected Behavior

It should work correctly.

### Acceptance Criteria

- AC1

## Notes
"""
        normalized, _ = normalize_body(body, "feature")
        content = _summary_content(normalized)
        assert _has_h3(content, "Desired Behavior")
        assert "work correctly" in content

    def test_success_criteria_maps_to_acceptance_criteria(self) -> None:
        body = """\
## Summary

### Problem

Something is broken.

### Success Criteria

- SC1
- SC2

## Notes
"""
        normalized, _ = normalize_body(body, "task")
        content = _summary_content(normalized)
        assert _has_h3(content, "Acceptance Criteria")
        assert "SC1" in content


# ---------------------------------------------------------------------------
# normalize_body() — preamble text preserved
# ---------------------------------------------------------------------------


BODY_WITH_PREAMBLE = """\
## Summary

Triggered by: OOMPAH-158

### Problem

Something went wrong.

### Acceptance Criteria

- AC1
- AC2

## Notes
"""


class TestPreamblePreservation:
    def test_preamble_in_summary(self) -> None:
        """Preamble text inside ## Summary (before first H3) is preserved."""
        body, _ = normalize_body(BODY_WITH_PREAMBLE, "task")
        content = _summary_content(body)
        assert "Triggered by: OOMPAH-158" in content

    def test_preamble_content_preserved_under_problem(self) -> None:
        """## Summary preamble text is mapped to problem_statement and appears
        in the ## Summary content of the normalized body."""
        body, _ = normalize_body(BODY_WITH_PREAMBLE, "task")
        content = _summary_content(body)
        # Both preamble and Problem content should appear somewhere in Summary.
        assert "Triggered by: OOMPAH-158" in content
        assert "Something went wrong" in content


# ---------------------------------------------------------------------------
# normalize_body() — multiple mappings to same field consolidated
# ---------------------------------------------------------------------------


class TestMultipleFieldMappings:
    def test_summary_and_problem_both_map_to_problem_statement(self) -> None:
        body = """\
## Summary

### Summary
First description of the issue.

### Problem
More detailed problem statement.

### Acceptance Criteria
- AC1

## Notes
"""
        normalized, _ = normalize_body(body, "task")
        content = _summary_content(normalized)
        # Both should appear under ### Problem
        assert _has_h3(content, "Problem")
        assert "First description" in content
        assert "More detailed problem statement" in content


# ---------------------------------------------------------------------------
# Validator integration — placeholders treated as missing
# ---------------------------------------------------------------------------


class TestValidatorPlaceholderIgnored:
    def test_section_nonempty_false_for_placeholder(self) -> None:
        description = (
            "### Acceptance Criteria\n\n"
            + make_placeholder("acceptance_criteria")
            + "\n"
        )
        assert not _section_nonempty(description, "acceptance_criteria")

    def test_section_nonempty_true_for_real_content(self) -> None:
        description = "### Acceptance Criteria\n\n- AC1: the system validates input.\n- AC2: error shown."
        assert _section_nonempty(description, "acceptance_criteria")

    def test_validate_issue_fails_for_placeholder_description(self) -> None:
        """validate_issue reports missing fields when description has only placeholders."""
        description = (
            "### Problem\n\n"
            + make_placeholder("problem_statement")
            + "\n\n"
            "### Acceptance Criteria\n\n"
            + make_placeholder("acceptance_criteria")
        )
        result = validate_issue(
            title="A sufficiently long task title for validation",
            description=description,
            issue_type="task",
        )
        assert not result.ready
        field_names = {f.field for f in result.missing_fields}
        # At least one required field should be flagged as missing.
        assert field_names

    def test_validate_issue_passes_after_normalization(self) -> None:
        """validate_issue passes when normalized body has real content."""
        description = (
            "### Problem\n\nThe system crashes on empty input.\n\n"
            "### Acceptance Criteria\n\n"
            "- Empty input shows a validation error.\n"
            "- No crash occurs when input is empty."
        )
        result = validate_issue(
            title="Fix crash on empty input in widget",
            description=description,
            issue_type="task",
        )
        assert result.ready


# ---------------------------------------------------------------------------
# normalize_native_task() integration helper
# ---------------------------------------------------------------------------


class FakeTrackerWithBodySupport:
    """Minimal tracker with get_raw_body / set_raw_body support."""

    def __init__(self, body: str) -> None:
        self._body = body
        self.set_raw_body_called = False
        self._new_body: str | None = None

    def get_raw_body(self, identifier: str) -> str | None:
        return self._body

    def set_raw_body(self, identifier: str, body: str) -> None:
        self.set_raw_body_called = True
        self._new_body = body
        self._body = body

    def fetch_issue_detail(self, identifier: str):
        return None


class FakeTrackerWithoutBodySupport:
    """Minimal tracker WITHOUT get_raw_body / set_raw_body (e.g. GitHub tracker)."""

    def update_issue_body_called(self) -> bool:
        return False


class TestNormalizeNativeTask:
    def test_no_op_for_tracker_without_body_support(self) -> None:
        tracker = FakeTrackerWithoutBodySupport()
        result = normalize_native_task(tracker, "TASK-1", "task")
        assert not result

    def test_no_op_when_body_is_unchanged(self) -> None:
        tracker = FakeTrackerWithBodySupport(CANONICAL_BODY)
        result = normalize_native_task(tracker, "TASK-1", "task")
        assert not result
        assert not tracker.set_raw_body_called

    def test_rewrites_body_when_changed(self) -> None:
        tracker = FakeTrackerWithBodySupport(MISSING_AC_BODY)
        result = normalize_native_task(tracker, "TASK-1", "task")
        assert result
        assert tracker.set_raw_body_called
        assert tracker._new_body is not None

    def test_rewritten_body_has_placeholder(self) -> None:
        tracker = FakeTrackerWithBodySupport(MISSING_AC_BODY)
        normalize_native_task(tracker, "TASK-1", "task")
        assert PLACEHOLDER_MARKER in tracker._new_body  # type: ignore[operator]

    def test_no_op_when_get_raw_body_returns_none(self) -> None:
        class NoneBodyTracker:
            def get_raw_body(self, identifier: str) -> str | None:
                return None

            def set_raw_body(self, identifier: str, body: str) -> None:
                raise AssertionError("set_raw_body should not be called for None body")

        result = normalize_native_task(NoneBodyTracker(), "TASK-1", "task")
        assert not result


# ---------------------------------------------------------------------------
# GitHub intake regression: external GitHub issue body NOT rewritten
# ---------------------------------------------------------------------------


class TestGitHubIntakeNoBodRewrite:
    """Normalization touches only the internal native task, never the GitHub issue."""

    def test_normalize_native_task_does_not_affect_github_tracker(self) -> None:
        """normalize_native_task is a no-op for GitHub-style trackers."""

        class FakeGitHubTracker:
            """Simulates a GitHubIssueTracker (no get_raw_body / set_raw_body)."""

            def __init__(self) -> None:
                self.update_called = False
                self.issue_body = "## Summary\n\nOriginal GitHub issue body."

            # GitHubIssueTracker exposes add_comment, update_issue, etc.
            # but NOT get_raw_body / set_raw_body.
            def add_comment(self, identifier, text, author="oompah"):
                pass

            def update_issue(self, identifier, **fields):
                self.update_called = True

        gh_tracker = FakeGitHubTracker()
        result = normalize_native_task(gh_tracker, "owner/repo#42", "task")
        assert not result, "normalize_native_task must be a no-op for GitHub trackers"
        assert not gh_tracker.update_called, "GitHub issue body must not be rewritten"

    def test_native_tracker_body_is_rewritten_for_github_intake(self) -> None:
        """The INTERNAL native task body IS normalized; the GitHub body is not touched."""
        # Simulate a native task that was created from a malformed GitHub import
        # (old TRICKLE-8 style body without heading demotion).
        native_tracker = FakeTrackerWithBodySupport(TRICKLE8_BODY)

        result = normalize_native_task(native_tracker, "TASK-1", "task")
        assert result, "Native task body should be normalized"
        # The normalized body should have the GitHub issue content in Summary.
        assert "GitHub issue content" in native_tracker._body
        # External GitHub Issue section is preserved verbatim.
        assert "## External GitHub Issue" in native_tracker._body


# ---------------------------------------------------------------------------
# normalize_body() — external github issue and notes section ordering
# ---------------------------------------------------------------------------


class TestSectionOrdering:
    def test_external_github_issue_after_summary(self) -> None:
        body = """\
## Summary

### Problem

Some problem.

### Acceptance Criteria

- AC1

## External GitHub Issue
- URL: https://github.com/example/repo/issues/1

## Notes
"""
        normalized, _ = normalize_body(body, "task")
        summary_pos = normalized.index("## Summary")
        github_pos = normalized.index("## External GitHub Issue")
        notes_pos = normalized.index("## Notes")
        assert summary_pos < github_pos < notes_pos

    def test_notes_section_always_present(self) -> None:
        simple_body = """\
## Summary

### Problem

Some problem.

### Acceptance Criteria

- AC1
"""
        normalized, _ = normalize_body(simple_body, "task")
        assert "## Notes" in normalized

    def test_comments_section_last(self) -> None:
        body_with_comments = """\
## Summary

### Problem

Some problem.

### Acceptance Criteria

- AC1

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-29 10:00
---
A comment.
---
<!-- COMMENTS:END -->
"""
        normalized, _ = normalize_body(body_with_comments, "task")
        notes_pos = normalized.index("## Notes")
        comments_pos = normalized.index("## Comments")
        assert notes_pos < comments_pos
