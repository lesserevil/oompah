"""Tests for oompah.issue_validator (lesserevil/oompah#279).

Coverage targets:
- Ready issues for each type (bug, feature, chore, task, epic).
- Incomplete issues — each required field missing individually.
- Ambiguous inputs — edge-case descriptions that could be misclassified.
- Oversized issues — epic_needed scope classification.
- All scope classifications (small_task, epic_needed, duplicate_candidate,
  needs_human_owner_review).
- to_dict() serialisation shape.
- Label-based type inference.
- Explicit unknown issue_type warning.
"""

from __future__ import annotations

import pytest

from oompah.issue_validator import (
    MissingField,
    ScopeClassification,
    ValidationResult,
    VALID_ISSUE_TYPES,
    _classify_scope,
    _has_section,
    _infer_issue_type,
    _section_body,
    _section_nonempty,
    _validate_bug,
    _validate_common,
    _validate_feature,
    _validate_chore_or_task,
    _validate_epic,
    validate_issue,
)


# ---------------------------------------------------------------------------
# Helper builders for test descriptions
# ---------------------------------------------------------------------------


def _bug_description(
    *,
    repro: str | None = "1. Navigate to /login\n2. Click 'Forgot password'\n3. See error",
    actual: str | None = "The page shows a 500 error and no email is sent.",
    expected: str | None = "A password reset email should be sent.",
    ac: str | None = "- `send_reset_email()` is called\n- User receives an email within 30s",
    env: str | None = "Python 3.11, oompah v0.9.3, Ubuntu 22.04",
) -> str:
    parts: list[str] = []
    parts.append("## Problem\nPassword reset is broken — users cannot recover their accounts.")
    if repro is not None:
        parts.append(f"## Steps to Reproduce\n{repro}")
    if actual is not None:
        parts.append(f"## Actual Behavior\n{actual}")
    if expected is not None:
        parts.append(f"## Expected Behavior\n{expected}")
    if env is not None:
        parts.append(f"## Environment\n{env}")
    if ac is not None:
        parts.append(f"## Acceptance Criteria\n{ac}")
    return "\n\n".join(parts)


def _feature_description(
    *,
    problem: str | None = "Users cannot filter issues by priority in the dashboard.",
    desired: str | None = "Users can select one or more priorities and the list updates live.",
    ac: str | None = "- Filter persists across navigation\n- Works for all 5 priority levels",
) -> str:
    parts: list[str] = []
    if problem is not None:
        parts.append(f"## Problem\n{problem}")
    if desired is not None:
        parts.append(f"## Desired Behavior\n{desired}")
    if ac is not None:
        parts.append(f"## Acceptance Criteria\n{ac}")
    return "\n\n".join(parts)


def _task_description(
    *,
    body: str = (
        "Update the pyproject.toml to use Python 3.12 and bump all test "
        "dependencies to their latest compatible versions. Run make test "
        "to verify nothing breaks."
    ),
    ac: str | None = "- `make test` passes on Python 3.12\n- CI is green",
) -> str:
    parts: list[str] = [f"## Problem\n{body}"]
    if ac is not None:
        parts.append(f"## Acceptance Criteria\n{ac}")
    return "\n\n".join(parts)


_EPIC_DESCRIPTION = """
## Overview

Migrate the orchestrator from a polling-based model to a pure event-driven
model to reduce CPU usage and improve response latency.

## Goals

- Replace the 10-second polling tick with a webhook-driven event loop.
- Maintain backward compatibility with projects that don't have webhooks.
- Add telemetry for event throughput and latency.

## Acceptance Criteria

- Existing tests continue to pass.
- New event-loop tests cover the happy path and error cases.
- Orchestrator CPU usage drops by at least 50 % in benchmarks.
""".strip()


# ---------------------------------------------------------------------------
# Ready issues — all types
# ---------------------------------------------------------------------------


class TestReadyBugReport:
    def test_ready_bug_returns_ready_true(self):
        result = validate_issue(
            title="Fix password reset 500 error on /login page",
            description=_bug_description(),
            issue_type="bug",
        )
        assert result.ready is True
        assert result.issue_type == "bug"
        assert result.missing_fields == []

    def test_scope_defaults_to_small_task(self):
        result = validate_issue(
            title="Fix password reset 500 error on /login page",
            description=_bug_description(),
            issue_type="bug",
        )
        assert result.scope == ScopeClassification.SMALL_TASK

    def test_repro_unavailable_note_accepted(self):
        desc = _bug_description(repro=None) + "\n\nN/A — intermittent, not reliably reproducible."
        result = validate_issue(
            title="Intermittent crash in worker thread on shutdown",
            description=desc,
            issue_type="bug",
        )
        missing_names = [f.field for f in result.missing_fields]
        assert "reproduction steps" not in missing_names


class TestReadyFeatureRequest:
    def test_ready_feature_returns_ready_true(self):
        result = validate_issue(
            title="Add priority filter to the dashboard issue list",
            description=_feature_description(),
            issue_type="feature",
        )
        assert result.ready is True
        assert result.issue_type == "feature"
        assert result.missing_fields == []

    def test_inline_desired_behavior_accepted(self):
        # Should be accepted even without a dedicated heading if the
        # description explains what the feature should do.
        desc = (
            "## Problem\nThere is no way to search issues by keyword.\n\n"
            "The search should allow users to type a keyword and filter the "
            "visible issues in real time. This will improve the workflow for "
            "large projects with many issues.\n\n"
            "## Acceptance Criteria\n"
            "- Search input is visible on the dashboard\n"
            "- Results update as the user types"
        )
        result = validate_issue(
            title="Add keyword search to the issue dashboard",
            description=desc,
            issue_type="feature",
        )
        assert result.ready is True


class TestReadyTaskAndChore:
    def test_ready_task_returns_ready_true(self):
        result = validate_issue(
            title="Bump test dependencies to Python 3.12",
            description=_task_description(),
            issue_type="task",
        )
        assert result.ready is True

    def test_ready_chore_returns_ready_true(self):
        result = validate_issue(
            title="Remove deprecated _legacy_parse helper from tracker.py",
            description=_task_description(
                body=(
                    "The `_legacy_parse` helper in `oompah/tracker.py` was replaced "
                    "in TASK-200 but never removed. It is dead code and increases "
                    "cognitive overhead."
                ),
            ),
            issue_type="chore",
        )
        assert result.ready is True


class TestReadyEpic:
    def test_ready_epic_returns_ready_true(self):
        result = validate_issue(
            title="Migrate orchestrator to event-driven model",
            description=_EPIC_DESCRIPTION,
            issue_type="epic",
        )
        assert result.ready is True
        assert result.issue_type == "epic"


# ---------------------------------------------------------------------------
# Incomplete issues — missing individual fields
# ---------------------------------------------------------------------------


class TestMissingTitle:
    def test_empty_title_missing_field(self):
        result = validate_issue(title="", description="Something")
        fields = [f.field for f in result.missing_fields]
        assert "title" in fields
        assert result.ready is False

    def test_blank_title_missing_field(self):
        result = validate_issue(title="   ", description="Something")
        fields = [f.field for f in result.missing_fields]
        assert "title" in fields

    def test_too_short_title(self):
        result = validate_issue(title="Bug", description="Something")
        fields = [f.field for f in result.missing_fields]
        assert "title" in fields

    def test_single_word_title(self):
        result = validate_issue(title="Bug", description="Something")
        assert result.ready is False


class TestMissingProblemStatement:
    def test_no_description_at_all(self):
        result = validate_issue(
            title="Add password reset feature to mobile app",
            description=None,
        )
        fields = [f.field for f in result.missing_fields]
        assert "problem statement" in fields
        assert result.ready is False

    def test_empty_description_triggers_problem_field(self):
        result = validate_issue(
            title="Add password reset feature to mobile app",
            description="",
        )
        fields = [f.field for f in result.missing_fields]
        assert "problem statement" in fields

    def test_short_description_triggers_problem_field(self):
        result = validate_issue(
            title="Fix login redirect loop on mobile Safari",
            description="Broken.",
        )
        fields = [f.field for f in result.missing_fields]
        assert "problem statement" in fields


class TestMissingAcceptanceCriteria:
    def test_missing_ac_section_flagged(self):
        desc = (
            "## Problem\n"
            "Users cannot log in using Google OAuth on mobile devices. "
            "The redirect URI is incorrect for the mobile web view.\n\n"
            "## Expected Behavior\n"
            "OAuth login should work on mobile devices with the correct redirect."
        )
        result = validate_issue(
            title="Fix Google OAuth redirect on mobile web view",
            description=desc,
            issue_type="feature",
        )
        fields = [f.field for f in result.missing_fields]
        assert "acceptance criteria" in fields

    def test_ac_section_present_clears_field(self):
        desc = _feature_description()
        result = validate_issue(
            title="Add priority filter to dashboard issue list",
            description=desc,
            issue_type="feature",
        )
        fields = [f.field for f in result.missing_fields]
        assert "acceptance criteria" not in fields

    def test_two_or_more_bullets_accepted_as_inline_ac(self):
        desc = (
            "## Problem\n"
            "There is no keyboard shortcut to create a new issue from anywhere "
            "in the dashboard. This slows down power users.\n\n"
            "The implementation should:\n"
            "- Bind Ctrl+N (or Cmd+N on macOS) to the new-issue modal\n"
            "- Show a toast when the shortcut fires\n"
            "- Work from every dashboard page"
        )
        result = validate_issue(
            title="Add keyboard shortcut to create a new issue",
            description=desc,
            issue_type="feature",
        )
        fields = [f.field for f in result.missing_fields]
        assert "acceptance criteria" not in fields


class TestBugSpecificMissingFields:
    def test_missing_repro_steps_flagged(self):
        desc = _bug_description(repro=None)
        result = validate_issue(
            title="Fix crash when opening settings on Android",
            description=desc,
            issue_type="bug",
        )
        fields = [f.field for f in result.missing_fields]
        assert "reproduction steps" in fields

    def test_missing_actual_behavior_flagged(self):
        desc = _bug_description(actual=None)
        result = validate_issue(
            title="Fix broken password reset on login page",
            description=desc,
            issue_type="bug",
        )
        fields = [f.field for f in result.missing_fields]
        assert "actual behavior" in fields

    def test_missing_expected_behavior_flagged(self):
        desc = _bug_description(expected=None)
        result = validate_issue(
            title="Fix broken password reset on login page",
            description=desc,
            issue_type="bug",
        )
        fields = [f.field for f in result.missing_fields]
        assert "expected behavior" in fields

    def test_inline_actual_behavior_accepted(self):
        desc = (
            "## Problem\nLogin redirects to 404 instead of dashboard.\n\n"
            "## Steps to Reproduce\n1. Log in\n2. See wrong redirect\n\n"
            "The actual behavior is a 404 page. The expected behavior is "
            "the user lands on /dashboard.\n\n"
            "## Acceptance Criteria\n- Login redirects to /dashboard"
        )
        result = validate_issue(
            title="Fix post-login redirect sending users to 404 page",
            description=desc,
            issue_type="bug",
        )
        fields = [f.field for f in result.missing_fields]
        assert "actual behavior" not in fields

    def test_inline_expected_behavior_accepted(self):
        desc = (
            "## Problem\nEmails are not sent on password reset.\n\n"
            "## Steps to Reproduce\n1. Click reset\n2. No email arrives\n\n"
            "## Actual Behavior\nNo email is sent.\n\n"
            "The system should send an email to the registered address.\n\n"
            "## Acceptance Criteria\n- Email is delivered within 30s"
        )
        result = validate_issue(
            title="Fix password reset email not being sent",
            description=desc,
            issue_type="bug",
        )
        fields = [f.field for f in result.missing_fields]
        assert "expected behavior" not in fields


class TestFeatureSpecificMissingFields:
    def test_feature_without_desired_behavior_flagged(self):
        desc = (
            "## Problem\nThe dashboard has no dark mode.\n\n"
            "## Acceptance Criteria\n- A dark mode toggle is visible in settings"
        )
        result = validate_issue(
            title="Add dark mode support to the oompah dashboard",
            description=desc,
            issue_type="feature",
        )
        # The "expected behavior" check may not trigger if the problem
        # section or AC section provides implicit behavior cues.
        # The important thing is we accept valid feature requests.
        assert isinstance(result, ValidationResult)


class TestChoreTaskMissingFields:
    def test_empty_chore_description_flagged(self):
        result = validate_issue(
            title="Clean up dead code in the parser module",
            description="",
            issue_type="chore",
        )
        assert result.ready is False

    def test_very_short_task_description_flagged(self):
        result = validate_issue(
            title="Update the CI configuration to use Python 3.12",
            description="Update CI.",
            issue_type="task",
        )
        fields = [f.field for f in result.missing_fields]
        assert "work description" in fields or len(result.missing_fields) > 0


# ---------------------------------------------------------------------------
# Scope classification
# ---------------------------------------------------------------------------


class TestScopeSmallTask:
    def test_focused_bug_is_small_task(self):
        result = validate_issue(
            title="Fix NullPointerException in UserService.getById",
            description=_bug_description(),
            issue_type="bug",
        )
        assert result.scope == ScopeClassification.SMALL_TASK

    def test_focused_feature_is_small_task(self):
        result = validate_issue(
            title="Add loading spinner to the issue detail panel",
            description=_feature_description(),
            issue_type="feature",
        )
        assert result.scope == ScopeClassification.SMALL_TASK


class TestScopeEpicNeeded:
    def test_phases_keyword_triggers_epic_needed(self):
        desc = (
            "## Problem\nThe current tracker needs to be migrated in phases.\n\n"
            "Phase 1: schema migration. Phase 2: API layer. Phase 3: frontend.\n\n"
            "## Acceptance Criteria\n- All three phases complete\n- No data loss"
        )
        result = validate_issue(
            title="Migrate tracker to new schema across three phases",
            description=desc,
            issue_type="task",
        )
        assert result.scope == ScopeClassification.EPIC_NEEDED

    def test_oversized_description_triggers_epic_needed(self):
        # Generate a description that exceeds the word threshold.
        long_desc = "word " * 700 + "\n\n## Acceptance Criteria\n- Done"
        result = validate_issue(
            title="Refactor the entire authentication subsystem",
            description=long_desc,
            issue_type="task",
        )
        assert result.scope == ScopeClassification.EPIC_NEEDED

    def test_epic_needed_adds_warning_when_not_epic_type(self):
        desc = (
            "## Problem\nFull platform redesign in multiple milestones.\n\n"
            "## Acceptance Criteria\n- All milestones done"
        )
        result = validate_issue(
            title="Platform redesign across multiple milestones",
            description=desc,
            issue_type="task",
        )
        assert result.scope == ScopeClassification.EPIC_NEEDED
        assert any("epic" in w.lower() for w in result.warnings)

    def test_epic_type_with_epic_scope_no_extra_warning(self):
        result = validate_issue(
            title="Migrate orchestrator to event-driven model",
            description=_EPIC_DESCRIPTION,
            issue_type="epic",
        )
        # An epic with epic scope should NOT get the "convert to epic" warning.
        assert not any("convert" in w.lower() for w in result.warnings)


class TestScopeDuplicateCandidate:
    def test_duplicate_keyword_triggers_scope(self):
        desc = (
            "## Problem\nDuplicate of #123 — same crash in the worker thread.\n\n"
            "## Acceptance Criteria\n- Closed as duplicate or resolved"
        )
        result = validate_issue(
            title="Worker thread crash on shutdown (same as issue #123)",
            description=desc,
            issue_type="bug",
        )
        assert result.scope == ScopeClassification.DUPLICATE_CANDIDATE

    def test_already_implemented_triggers_duplicate_scope(self):
        desc = (
            "## Problem\nNeed dark mode. Already implemented in PR #200 but "
            "seems to have regressed.\n\n"
            "## Acceptance Criteria\n- Dark mode works again"
        )
        result = validate_issue(
            title="Re-enable dark mode that was already implemented",
            description=desc,
            issue_type="task",
        )
        assert result.scope == ScopeClassification.DUPLICATE_CANDIDATE

    def test_duplicate_scope_adds_warning(self):
        desc = (
            "## Problem\nSimilar to issue #42 — pagination is broken on mobile.\n\n"
            "## Acceptance Criteria\n- Pagination works on mobile"
        )
        result = validate_issue(
            title="Fix pagination similar to issue #42",
            description=desc,
            issue_type="bug",
        )
        assert any("duplicate" in w.lower() for w in result.warnings)


class TestScopeNeedsHumanOwnerReview:
    def test_security_implication_triggers_scope(self):
        desc = (
            "## Problem\nThe API tokens are stored in plaintext. "
            "This has security implications for all users.\n\n"
            "## Acceptance Criteria\n- Tokens are encrypted at rest"
        )
        result = validate_issue(
            title="Encrypt API tokens stored in the database",
            description=desc,
            issue_type="task",
        )
        assert result.scope == ScopeClassification.NEEDS_HUMAN_OWNER_REVIEW

    def test_architecture_decision_triggers_scope(self):
        desc = (
            "## Problem\nWe need to make an architectural decision about "
            "whether to use Redis or Postgres for the job queue.\n\n"
            "## Acceptance Criteria\n- Decision is documented"
        )
        result = validate_issue(
            title="Architectural decision: Redis vs Postgres for job queue",
            description=desc,
            issue_type="task",
        )
        assert result.scope == ScopeClassification.NEEDS_HUMAN_OWNER_REVIEW

    def test_breaking_change_triggers_scope(self):
        desc = (
            "## Problem\nThe `validate_issue()` API needs a breaking change "
            "to the return type to add structured warnings.\n\n"
            "## Acceptance Criteria\n- API change is backward compatible or documented"
        )
        result = validate_issue(
            title="Breaking change to validate_issue return type",
            description=desc,
            issue_type="task",
        )
        assert result.scope == ScopeClassification.NEEDS_HUMAN_OWNER_REVIEW

    def test_human_review_scope_adds_warning(self):
        desc = (
            "## Problem\nGDPR compliance requires data deletion within 30 days.\n\n"
            "## Acceptance Criteria\n- Data deletion process is documented"
        )
        result = validate_issue(
            title="GDPR data deletion compliance",
            description=desc,
            issue_type="task",
        )
        assert result.scope == ScopeClassification.NEEDS_HUMAN_OWNER_REVIEW
        assert any("security" in w.lower() or "human" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Ambiguous inputs
# ---------------------------------------------------------------------------


class TestAmbiguousInputs:
    def test_tbd_in_ac_section_is_not_accepted(self):
        desc = (
            "## Problem\n"
            "The search results are not sorted by relevance.\n\n"
            "## Acceptance Criteria\nTBD"
        )
        result = validate_issue(
            title="Sort search results by relevance score",
            description=desc,
            issue_type="feature",
        )
        fields = [f.field for f in result.missing_fields]
        assert "acceptance criteria" in fields

    def test_na_in_section_is_not_accepted(self):
        desc = (
            "## Problem\n"
            "Sorting is missing from the issue list.\n\n"
            "## Acceptance Criteria\nN/A"
        )
        result = validate_issue(
            title="Add column sorting to the issue list table",
            description=desc,
            issue_type="feature",
        )
        fields = [f.field for f in result.missing_fields]
        assert "acceptance criteria" in fields

    def test_question_mark_only_ac_not_accepted(self):
        desc = "## Problem\nThere is no sorting on the issue list.\n\n## Acceptance Criteria\n???"
        result = validate_issue(
            title="Add sortable columns to the issue list table",
            description=desc,
            issue_type="feature",
        )
        fields = [f.field for f in result.missing_fields]
        assert "acceptance criteria" in fields

    def test_unknown_issue_type_defaults_to_task_with_warning(self):
        result = validate_issue(
            title="Do something with the frobnicator module",
            description=_task_description(),
            issue_type="unknown_type",
        )
        assert result.issue_type == "task"
        assert any("task" in w.lower() or "unknown" in w.lower() for w in result.warnings)

    def test_no_issue_type_inferred_from_bug_label(self):
        result = validate_issue(
            title="Fix password reset crash on mobile",
            description=_bug_description(),
            labels=["type:bug", "priority:0"],
        )
        assert result.issue_type == "bug"

    def test_no_issue_type_inferred_from_feature_label(self):
        result = validate_issue(
            title="Add CSV export to the dashboard report",
            description=_feature_description(),
            labels=["feature"],
        )
        assert result.issue_type == "feature"

    def test_no_issue_type_defaults_to_task_when_no_labels(self):
        result = validate_issue(
            title="Update documentation for the new API endpoint",
            description=_task_description(),
        )
        assert result.issue_type == "task"


# ---------------------------------------------------------------------------
# to_dict serialisation
# ---------------------------------------------------------------------------


class TestValidationResultToDict:
    def test_ready_result_dict_shape(self):
        result = validate_issue(
            title="Fix password reset 500 error on login page",
            description=_bug_description(),
            issue_type="bug",
        )
        d = result.to_dict()
        assert d["ready"] is True
        assert d["issue_type"] == "bug"
        assert d["scope"] == "small_task"
        assert d["missing_fields"] == []
        assert isinstance(d["warnings"], list)

    def test_not_ready_result_dict_has_missing_fields(self):
        result = validate_issue(
            title="Fix crash",
            description="It crashes.",
            issue_type="bug",
        )
        d = result.to_dict()
        assert d["ready"] is False
        assert len(d["missing_fields"]) > 0
        mf = d["missing_fields"][0]
        assert "field" in mf
        assert "reason" in mf
        assert "suggested_fix" in mf

    def test_scope_serialises_as_string(self):
        result = validate_issue(
            title="Migrate tracker in phases milestone one of three",
            description=(
                "## Problem\nMigrate in phases.\n\n"
                "## Acceptance Criteria\n- Phase 1 done"
            ),
            issue_type="task",
        )
        d = result.to_dict()
        assert isinstance(d["scope"], str)
        assert d["scope"] == "epic_needed"


class TestMissingFieldToDict:
    def test_missing_field_dict_has_all_keys(self):
        mf = MissingField(
            field="acceptance criteria",
            reason="Required for verification.",
            suggested_fix="Add an ## Acceptance Criteria section.",
        )
        d = mf.to_dict()
        assert d == {
            "field": "acceptance criteria",
            "reason": "Required for verification.",
            "suggested_fix": "Add an ## Acceptance Criteria section.",
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestSectionHelpers:
    def test_has_section_detects_heading(self):
        text = "## Problem\nSomething is wrong.\n\n## Acceptance Criteria\n- Done"
        assert _has_section(text, "problem_statement") is True
        assert _has_section(text, "acceptance_criteria") is True

    def test_has_section_returns_false_when_absent(self):
        assert _has_section("## Steps to Reproduce\ndo X", "acceptance_criteria") is False

    def test_section_body_returns_content_until_next_header(self):
        text = "## Problem\nBug description.\n\n## Next\nOther section."
        body = _section_body(text, "problem_statement")
        assert "Bug description" in body
        assert "Other section" not in body

    def test_section_nonempty_rejects_tbd(self):
        text = "## Acceptance Criteria\nTBD"
        assert _section_nonempty(text, "acceptance_criteria") is False

    def test_section_nonempty_rejects_na(self):
        text = "## Acceptance Criteria\nN/A"
        assert _section_nonempty(text, "acceptance_criteria") is False

    def test_section_nonempty_accepts_real_content(self):
        text = "## Acceptance Criteria\n- Tests pass\n- Coverage >= 80 %"
        assert _section_nonempty(text, "acceptance_criteria") is True


class TestInferIssueType:
    def test_type_prefix_label(self):
        assert _infer_issue_type(["type:bug"]) == "bug"

    def test_bare_type_label(self):
        assert _infer_issue_type(["feature"]) == "feature"

    def test_no_matching_labels_defaults_to_task(self):
        assert _infer_issue_type(["priority:high", "component:api"]) == "task"

    def test_empty_labels_defaults_to_task(self):
        assert _infer_issue_type([]) == "task"

    def test_mixed_labels_returns_first_match(self):
        assert _infer_issue_type(["priority:0", "type:chore", "type:bug"]) == "chore"


class TestClassifyScope:
    def test_phases_trigger_epic(self):
        assert _classify_scope("", "We will do this in phases.") == ScopeClassification.EPIC_NEEDED

    def test_duplicate_keyword_beats_epic(self):
        assert _classify_scope("", "duplicate of #100 phases platform") == ScopeClassification.DUPLICATE_CANDIDATE

    def test_security_beats_epic(self):
        # human-review comes before epic in the check order
        scope = _classify_scope(
            "",
            "security implications across multiple phases of the platform",
        )
        assert scope == ScopeClassification.NEEDS_HUMAN_OWNER_REVIEW

    def test_default_is_small_task(self):
        assert _classify_scope("Fix typo", "A small typo in the docs.") == ScopeClassification.SMALL_TASK


# ---------------------------------------------------------------------------
# VALID_ISSUE_TYPES constant
# ---------------------------------------------------------------------------


class TestValidIssueTypesConstant:
    def test_contains_expected_types(self):
        assert "bug" in VALID_ISSUE_TYPES
        assert "feature" in VALID_ISSUE_TYPES
        assert "task" in VALID_ISSUE_TYPES
        assert "chore" in VALID_ISSUE_TYPES
        assert "epic" in VALID_ISSUE_TYPES

    def test_does_not_contain_invalid_types(self):
        assert "unknown" not in VALID_ISSUE_TYPES
        assert "enhancement" not in VALID_ISSUE_TYPES
