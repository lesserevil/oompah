"""Tests for Epic-state reversion handling in PATCH /api/v1/issues.

Covers the fix for oompah-zlz_2-sytm: tracker's post-update Epic state hook
reverts a manual state transition back to the children's-computed state.
The endpoint now detects this by re-reading after the write and returns a
clear 409 (epic_state_reverted) rather than silently returning ok=true.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app, _state_key, _verify_epic_state_after_update
from oompah.models import Issue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(
    identifier: str = "epic-1",
    issue_type: str = "epic",
    state: str = "deferred",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Test epic",
        description="Test issue description for state transition tests.",
        state=state,
        issue_type=issue_type,
    )


def _make_mock_orchestrator(project_id: str = "proj-1") -> tuple[MagicMock, MagicMock]:
    mock_tracker = MagicMock()
    mock_tracker.create_issue = MagicMock()
    mock_tracker.update_issue = MagicMock()
    mock_tracker.close_issue = MagicMock()
    mock_tracker.mark_needs_human = MagicMock()
    mock_tracker.fetch_issue_detail = MagicMock()
    mock_tracker.fetch_children = MagicMock(return_value=[])

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    mock_orch.config.tracker_terminal_states = ["closed"]
    mock_orch.state.running = {}
    mock_orch.state.retry_attempts = {}
    mock_orch.state.claimed = set()
    mock_orch.state.completed = set()

    return mock_orch, mock_tracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient backed by the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# PATCH /api/v1/issues — project_id validation
# ---------------------------------------------------------------------------

def test_state_key_normalizes_backlog_in_progress_for_ui_termination_guard():
    assert _state_key("In Progress") == "in_progress"
    assert _state_key("in-progress") == "in_progress"


class TestUpdateIssueProjectIdValidation:
    """Tests for PATCH /api/v1/issues/{identifier} tracker resolution.

    Previously project_id was strictly required (400 when absent).  After
    TASK-459.2 the endpoint falls back to searching all projects by identifier
    when project_id is omitted, so omitting project_id for an unknown
    identifier returns 404 (issue_not_found) rather than 400 (validation).
    Clients can still pass project_id explicitly for faster, unambiguous
    resolution.
    """

    def test_missing_project_id_with_unknown_identifier_returns_404(self, client):
        """When project_id is absent and identifier not found, return 404."""
        mock_orch, _ = _make_mock_orchestrator()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
        ):
            resp = client.patch(
                "/api/v1/issues/task-1",
                json={"status": "in_progress"},  # no project_id
            )

        # Falls back to searching all projects; none found → 404.
        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == "issue_not_found"

    def test_missing_project_id_resolves_via_identifier_search(self, client):
        """When project_id is absent but identifier found, update succeeds."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        found_issue = _make_issue(identifier="task-1", issue_type="task", state="open")
        # Set up project store to return a project and tracker that has the issue.
        mock_project = MagicMock()
        mock_project.id = "proj-1"
        mock_orch.project_store.list_all.return_value = [mock_project]
        mock_tracker.fetch_issue_detail.return_value = found_issue

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/task-1",
                json={"status": "open"},  # no project_id
            )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_github_identifier_infers_project_without_search(self, client):
        """Fully-qualified GitHub identifiers resolve by managed repo slug."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_project = MagicMock()
        mock_project.id = "proj-1"
        mock_project.repo_url = "https://github.com/NVIDIA-Omniverse/trickle"
        mock_orch.project_store.list_all.return_value = [mock_project]
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="NVIDIA-Omniverse/trickle#240",
            issue_type="task",
            state="open",
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(
                server_module,
                "_find_tracker_for_issue",
                side_effect=AssertionError("should not search all projects"),
            ) as mock_find,
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/ignored",
                json={
                    "issue_key": "NVIDIA-Omniverse/trickle#240",
                    "status": "in_progress",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_tracker.update_issue.assert_called_once_with(
            "NVIDIA-Omniverse/trickle#240",
            status="in_progress",
        )
        mock_find.assert_not_called()

    def test_valid_project_id_in_body_proceeds(self, client):
        """When project_id is present, the normal flow proceeds."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="task-1", issue_type="task", state="open"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/task-1",
                json={"status": "in_progress", "project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestUpdateIssueNeedsHumanComment:
    def test_needs_human_status_adds_actionable_comment(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="task-1", issue_type="task", state="open"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/task-1",
                json={
                    "status": "Needs Human",
                    "project_id": "proj-1",
                    "comment": "Human action required: choose the deployment path.",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_tracker.update_issue.assert_not_called()
        mock_tracker.mark_needs_human.assert_called_once_with(
            "task-1",
            "Human action required: choose the deployment path.",
            author="oompah",
        )

    def test_needs_human_status_without_comment_uses_default_action(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="task-1", issue_type="task", state="open"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/task-1",
                json={"status": "Needs Human", "project_id": "proj-1"},
            )

        assert resp.status_code == 200
        comment = mock_tracker.mark_needs_human.call_args.args[1]
        assert "Human action required" in comment
        assert "move the task back to Open" in comment


class TestReopenClearsSchedulerCompletionState:
    def test_reopen_removes_completed_and_claimed_entries(self, client):
        mock_orch, mock_tracker = _make_mock_orchestrator()
        issue = _make_issue(identifier="task-1", issue_type="task", state="Needs Human")
        mock_tracker.fetch_issue_detail.return_value = issue
        mock_orch.state.completed.add(issue.id)
        mock_orch.state.claimed.add(issue.id)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/task-1",
                json={"status": "Open", "project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert issue.id not in mock_orch.state.completed
        assert issue.id not in mock_orch.state.claimed


# ---------------------------------------------------------------------------
# PATCH /api/v1/issues — Epic state verification
# ---------------------------------------------------------------------------

class TestEpicStateVerification:
    """Tests for Epic state reversion detection in api_update_issue."""

    def test_non_epic_state_update_no_verification(self, client):
        """Non-Epic issues skip the verification pass entirely."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="task-1", issue_type="task", state="open"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/task-1",
                json={"status": "in_progress", "project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        # Non-Epic issues do not trigger the Epic verification re-read pass.
        # The endpoint calls fetch_issue_detail once inside
        # _get_tracker_for_issue_or_project (tracker resolution) and once
        # to read `existing_issue` for the is_epic check, but it must NOT
        # call it again for the Epic verification loop.
        assert mock_tracker.fetch_issue_detail.call_count == 2

    def test_epic_state_update_persists_returns_200(self, client):
        """When Epic state change persists, return 200 ok."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        existing_epic = _make_issue(identifier="epic-1", issue_type="epic", state="deferred")
        mock_tracker.fetch_issue_detail.return_value = existing_epic
        mock_tracker.update_issue = MagicMock()

        # After update the state is correctly 'open'
        verification_issue = _make_issue(identifier="epic-1", issue_type="epic", state="open")

        call_count = [0]

        def fetch_side_effect(identifier):
            call_count[0] += 1
            # First call: existing issue; subsequent calls: re-reads
            if call_count[0] == 1:
                return existing_epic
            return verification_issue

        mock_tracker.fetch_issue_detail.side_effect = fetch_side_effect

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/epic-1",
                json={"status": "open", "project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_epic_state_update_reverts_returns_409(self, client):
        """When Epic state is immediately reverted by tracker backend, return 409."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        existing_epic = _make_issue(identifier="epic-1", issue_type="epic", state="deferred")
        mock_tracker.fetch_issue_detail.return_value = existing_epic
        mock_tracker.update_issue = MagicMock()

        # State reverts to 'deferred' after the update (tracker backend hook)
        reverted_issue = _make_issue(identifier="epic-1", issue_type="epic", state="deferred")

        call_count = [0]

        def fetch_side_effect(identifier):
            call_count[0] += 1
            if call_count[0] == 1:
                return existing_epic
            return reverted_issue  # tracker reverted

        mock_tracker.fetch_issue_detail.side_effect = fetch_side_effect

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/epic-1",
                json={"status": "open", "project_id": "proj-1"},
            )

        assert resp.status_code == 409
        err = resp.json()["error"]
        assert err["code"] == "epic_state_reverted"
        assert "tracker backend reverted" in err["message"]
        assert "epic-1" in err["message"]

    def test_epic_priority_update_no_verification(self, client):
        """Epic priority/title updates without status change skip verification."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="epic-1", issue_type="epic", state="deferred"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/epic-1",
                json={"priority": 1, "project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_epic_close_does_not_verify(self, client):
        """Closing an Epic (terminal transition) skips the verification pass."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        mock_tracker.fetch_issue_detail.return_value = _make_issue(
            identifier="epic-1", issue_type="epic", state="deferred"
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/epic-1",
                json={"status": "closed", "project_id": "proj-1"},
            )

        # No verification for terminal transitions (close is aterminal state)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# _verify_epic_state_after_update — unit tests
# ---------------------------------------------------------------------------

class TestVerifyEpicStateAfterUpdate:
    """Unit tests for the verification helper."""

    def test_returns_true_when_state_matches(self):
        tracker = MagicMock()
        issue = _make_issue(identifier="epic-1", issue_type="epic", state="open")
        tracker.fetch_issue_detail.return_value = issue

        result = _verify_epic_state_after_update(tracker, "epic-1", "open")
        assert result is True

    def test_returns_false_when_state_mismatch(self):
        tracker = MagicMock()
        issue = _make_issue(identifier="epic-1", issue_type="epic", state="deferred")
        tracker.fetch_issue_detail.return_value = issue

        result = _verify_epic_state_after_update(tracker, "epic-1", "open")
        assert result is False

    def test_returns_true_when_issue_not_found(self):
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None

        result = _verify_epic_state_after_update(tracker, "epic-1", "open")
        assert result is True  # treat as settled when unreachable

    def test_normalizes_case_and_whitespace(self):
        tracker = MagicMock()
        issue = _make_issue(identifier="epic-1", issue_type="epic", state="  OPEN  ")
        tracker.fetch_issue_detail.return_value = issue

        result = _verify_epic_state_after_update(tracker, "epic-1", "open")
        assert result is True

    def test_returns_true_on_fetch_exception(self):
        tracker = MagicMock()
        tracker.fetch_issue_detail.side_effect = Exception("tracker error")

        result = _verify_epic_state_after_update(tracker, "epic-1", "open")
        assert result is True  # best-effort
