"""Tests for Epic-state reversion handling in PATCH /api/v1/issues.

Covers the fix for oompah-zlz_2-sytm: bd's post-update Epic state hook
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
from oompah.server import app, _verify_epic_state_after_update
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
        state=state,
        issue_type=issue_type,
    )


def _make_mock_orchestrator(project_id: str = "proj-1") -> tuple[MagicMock, MagicMock]:
    mock_tracker = MagicMock()
    mock_tracker.create_issue = MagicMock()
    mock_tracker.update_issue = MagicMock()
    mock_tracker.close_issue = MagicMock()
    mock_tracker.fetch_issue_detail = MagicMock()
    mock_tracker.fetch_children = MagicMock(return_value=[])

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    mock_orch.config.tracker_terminal_states = ["closed"]

    return mock_orch, mock_tracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Return a TestClient backed by the FastAPI app."""
    return TestClient(app, raise_server_exceptions=False)


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
        # No fetch_issue_detail re-call for non-Epic
        assert mock_tracker.fetch_issue_detail.call_count == 1

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
        """When Epic state is immediately reverted by bd backend, return 409."""
        mock_orch, mock_tracker = _make_mock_orchestrator()
        existing_epic = _make_issue(identifier="epic-1", issue_type="epic", state="deferred")
        mock_tracker.fetch_issue_detail.return_value = existing_epic
        mock_tracker.update_issue = MagicMock()

        # State reverts to 'deferred' after the update (bd backend hook)
        reverted_issue = _make_issue(identifier="epic-1", issue_type="epic", state="deferred")

        call_count = [0]

        def fetch_side_effect(identifier):
            call_count[0] += 1
            if call_count[0] == 1:
                return existing_epic
            return reverted_issue  # bd reverted

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
        assert "bd backend reverted" in err["message"]
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
        tracker.fetch_issue_detail.side_effect = Exception("bd error")

        result = _verify_epic_state_after_update(tracker, "epic-1", "open")
        assert result is True  # best-effort