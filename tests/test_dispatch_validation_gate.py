"""Tests for the _should_dispatch validation gate (oompah-zlz_2-izq9).

Before dispatch, _should_dispatch checks four required fields:
  - description: must be non-empty
  - acceptance_criteria: must be non-empty (extracted from description)
  - issue_type: must be present
  - priority: must be explicitly set (not None)

If any field is missing:
  1. "incomplete" label is added via tracker.add_label
  2. Dispatch is rejected with reason "incomplete:<missing_fields>"

Epics are excluded from this check.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import AgentProfile, Issue
from oompah.orchestrator import Orchestrator


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(
    identifier: str = "test-abc",
    state: str = "open",
    issue_type: str = "task",
    priority: int = 2,
    project_id: str | None = None,
    labels: list | None = None,
    description: str = "Test body.\n\n# Acceptance criteria\n\n- Do the thing",
    title: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title or f"Issue {identifier}",
        description=description,
        state=state,
        issue_type=issue_type,
        priority=priority,
        project_id=project_id,
        labels=labels or [],
    )


def _make_orchestrator(tmp_path):
    """Create a minimal orchestrator for testing _should_dispatch."""
    from oompah.roles import RoleStore

    project_store = MagicMock()
    project_store.list_all.return_value = []
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    orch = Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    orch.config.agent_profiles = [
        AgentProfile(name="default", command="test"),
    ]
    return orch


class TestValidationGateMissingDescription:
    """Missing description must add incomplete label and reject dispatch."""

    def test_empty_description_rejected(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("issue-1", description="")

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        tracker.add_label.assert_called_once_with("issue-1", "incomplete")
        # Reject streak should record the incomplete reason
        assert "issue-1" in orch.state.reject_streak
        reason, _ = orch.state.reject_streak["issue-1"]
        assert "incomplete" in reason
        assert "missing_description" in reason

    def test_whitespace_only_description_rejected(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("issue-1", description="   \n\t  ")

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        tracker.add_label.assert_called_once_with("issue-1", "incomplete")
        reason, _ = orch.state.reject_streak["issue-1"]
        assert "missing_description" in reason

    def test_none_description_rejected(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("issue-1", description=None)

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        tracker.add_label.assert_called_once_with("issue-1", "incomplete")
        reason, _ = orch.state.reject_streak["issue-1"]
        assert "missing_description" in reason


class TestValidationGateMissingPriority:
    """Missing priority (None) must add incomplete label and reject."""

    def test_none_priority_rejected(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            "issue-1",
            description="Body text.\n\n# Acceptance criteria\n\n- AC",
            priority=None,
        )

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        tracker.add_label.assert_called_once_with("issue-1", "incomplete")
        reason, _ = orch.state.reject_streak["issue-1"]
        assert "missing_priority" in reason


class TestValidationGateMissingIssueType:
    """Empty issue_type must add incomplete label and reject."""

    def test_empty_issue_type_rejected(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("issue-1", issue_type="")

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        tracker.add_label.assert_called_once_with("issue-1", "incomplete")
        reason, _ = orch.state.reject_streak["issue-1"]
        assert "missing_issue_type" in reason


class TestValidationGateMissingAcceptanceCriteria:
    """Missing acceptance criteria must add incomplete label and reject."""

    def test_no_acceptance_criteria_rejected(self, tmp_path):
        """Description without any AC section is rejected."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            "issue-1",
            description="Just a description with no acceptance criteria section.",
        )

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        tracker.add_label.assert_called_once_with("issue-1", "incomplete")
        reason, _ = orch.state.reject_streak["issue-1"]
        assert "missing_acceptance_criteria" in reason

    def test_empty_acceptance_criteria_section_rejected(self, tmp_path):
        """AC header present but empty content is rejected."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            "issue-1",
            description="Body.\n\n# Acceptance criteria\n\n",
        )

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        tracker.add_label.assert_called_once_with("issue-1", "incomplete")
        reason, _ = orch.state.reject_streak["issue-1"]
        assert "missing_acceptance_criteria" in reason

    def test_valid_acceptance_criteria_passes(self, tmp_path):
        """Description with a proper AC section passes the AC check."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            "issue-1",
            description="Body text.\n\n# Acceptance criteria\n\n- First criterion\n- Second criterion",
        )

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        # Don't mock _paused etc. — rely on the real method
        # The issue should pass the validation gate at minimum
        result = orch._should_dispatch(issue)

        # The incomplete label must NOT have been added
        tracker.add_label.assert_not_called()


class TestValidationGateMultipleFieldsMissing:
    """Multiple missing fields produces a combined reject reason."""

    def test_multiple_missing_fields_combined(self, tmp_path):
        """Empty description + None priority + no AC → combined reason."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            "issue-1",
            description="",
            priority=None,
        )

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        # Label added once (idempotent within one call)
        assert tracker.add_label.call_count == 1
        reason, _ = orch.state.reject_streak["issue-1"]
        assert "missing_description" in reason
        assert "missing_priority" in reason


class TestValidationGateEpicExcluded:
    """Epics must be excluded from the validation gate."""

    def test_epic_skips_validation_gate(self, tmp_path):
        """Epic with empty description and None priority bypasses the gate."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            "epic-1",
            issue_type="epic",
            description="",
            priority=None,
        )

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        # Epics are rejected via a separate gate ("epic"), not validation
        result = orch._should_dispatch(issue)

        # The incomplete label must NOT be added for epics
        tracker.add_label.assert_not_called()
        # Epic should still be rejected, but via the epic gate
        assert result is False
        reason, _ = orch.state.reject_streak["epic-1"]
        assert reason == "epic"


class TestValidationGateLabelErrorHandling:
    """If adding the label fails, the gate still rejects dispatch."""

    def test_label_add_failure_still_rejects(self, tmp_path):
        """Even if tracker.add_label raises, the issue is rejected."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("issue-1", description="")

        tracker = MagicMock()
        tracker.add_label.side_effect = Exception("bd command failed")
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        reason, _ = orch.state.reject_streak["issue-1"]
        assert "missing_description" in reason


class TestValidationGateOrder:
    """The validation gate runs before other gates."""

    def test_validation_runs_before_paused_check(self, tmp_path):
        """Even when paused, the incomplete label is still added."""
        orch = _make_orchestrator(tmp_path)
        orch._paused = True
        issue = _make_issue("issue-1", description="")

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        # Validation gate fires before the paused check
        tracker.add_label.assert_called_once_with("issue-1", "incomplete")
        reason, _ = orch.state.reject_streak["issue-1"]
        assert "incomplete" in reason

    def test_validation_runs_before_state_check(self, tmp_path):
        """Even a closed issue triggers the validation gate first."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue("issue-1", state="closed", description="")

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        result = orch._should_dispatch(issue)

        assert result is False
        # Validation gate fires before state checks
        tracker.add_label.assert_called_once_with("issue-1", "incomplete")


class TestValidationGateHappyPath:
    """Well-formed issues pass through the validation gate."""

    def test_complete_issue_passes_validation(self, tmp_path):
        """Issue with all required fields present passes the gate."""
        orch = _make_orchestrator(tmp_path)
        issue = _make_issue(
            "issue-1",
            description="Do this thing.\n\n# Acceptance criteria\n\n- Implement the feature\n- Add tests",
            issue_type="task",
            priority=2,
            state="open",
        )

        tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        # Issue should pass validation gate; may be rejected by other gates
        result = orch._should_dispatch(issue)

        # Incomplete label must NOT be added
        tracker.add_label.assert_not_called()
        # If rejected, it should NOT be for incomplete reasons
        if "issue-1" in orch.state.reject_streak:
            reason, _ = orch.state.reject_streak["issue-1"]
            assert "incomplete" not in reason
