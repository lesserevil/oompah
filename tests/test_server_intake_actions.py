"""Tests for intake action API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue
from oompah.server import app
from oompah.statuses import BACKLOG


def _make_issue(
    *,
    state: str = "Proposed",
    requestor_login: str = "alice",
) -> Issue:
    return Issue(
        id="owner/repo#1",
        identifier="owner/repo#1",
        title="Proposed work",
        description="Enough detail",
        state=state,
        requestor_login=requestor_login,
        tracker_kind="github_issues",
    )


def _make_orchestrator(issue: Issue | None = None):
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue or _make_issue()
    tracker.update_issue = MagicMock()
    tracker.add_comment = MagicMock(return_value={"ok": True})

    project = MagicMock()
    project.id = "proj-1"
    project.tracker_owner = "owner"
    project.status_label_authorized_logins = ["pm"]
    project.tracker_kind = "github_issues"
    project.legacy_backlog_enabled = False

    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store.list_all.return_value = [project]
    orch.tracker = tracker

    return orch, tracker


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestIssueIntakeActionApi:
    def test_requestor_approval_posts_audit_comment_without_status_update(self, client):
        orch, tracker = _make_orchestrator(_make_issue(requestor_login="alice"))

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/requestor-approve",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                    "actor": "alice",
                    "message": "Scope approved.",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["action"] == "requestor_approve"
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_called_once()
        args, kwargs = tracker.add_comment.call_args
        assert args[0] == "owner/repo#1"
        assert "requestor_approve" in args[1]
        assert "Scope approved." in args[1]
        assert kwargs["author"] == "alice"

    def test_non_requestor_cannot_approve_scope(self, client):
        orch, tracker = _make_orchestrator(_make_issue(requestor_login="alice"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/requestor-approve",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                    "actor": "pm",
                },
            )

        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "not_requestor"
        tracker.add_comment.assert_not_called()

    def test_owner_promote_updates_backlog_and_posts_audit_comment(self, client):
        orch, tracker = _make_orchestrator(_make_issue())

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/promote-to-backlog",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                    "actor": "pm",
                },
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == BACKLOG
        tracker.update_issue.assert_called_once_with("owner/repo#1", status=BACKLOG)
        tracker.add_comment.assert_called_once()
        comment = tracker.add_comment.call_args.args[1]
        assert "promote_to_backlog" in comment
        assert "promoted this Proposed issue to Backlog" in comment
        assert tracker.add_comment.call_args.kwargs["author"] == "pm"

    def test_unauthorized_user_cannot_promote(self, client):
        orch, tracker = _make_orchestrator(_make_issue())

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/promote-to-backlog",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                    "actor": "mallory",
                },
            )

        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "owner_required"
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()

    def test_owner_action_on_non_proposed_issue_returns_409(self, client):
        orch, tracker = _make_orchestrator(_make_issue(state="Backlog"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/promote-to-backlog",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                    "actor": "pm",
                },
            )

        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "invalid_state"
        tracker.update_issue.assert_not_called()

    def test_missing_actor_returns_400(self, client):
        orch, _ = _make_orchestrator(_make_issue())

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/promote-to-backlog",
                json={"issue_key": "owner/repo#1", "project_id": "proj-1"},
            )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "validation"

    def test_unknown_action_returns_400(self, client):
        orch, _ = _make_orchestrator(_make_issue())

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/not-a-real-action",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                    "actor": "pm",
                },
            )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "validation"

    def test_request_changes_posts_owner_audit_comment(self, client):
        orch, tracker = _make_orchestrator(_make_issue())

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/intake/request-changes",
                json={
                    "issue_key": "owner/repo#1",
                    "project_id": "proj-1",
                    "actor": "owner",
                    "message": "Please add acceptance criteria.",
                },
            )

        assert resp.status_code == 200
        tracker.update_issue.assert_not_called()
        comment = tracker.add_comment.call_args.args[1]
        assert "request_changes" in comment
        assert "Please add acceptance criteria." in comment
