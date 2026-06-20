"""Tests for intake status transition gates across mutation paths."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.github_tracker import GitHubAuth, GitHubIssueTracker
from oompah.models import Issue
from oompah.server import app
from oompah.transition_gate import check_intake_transition


def _project(
    owner: str = "owner",
    authorized: list[str] | None = None,
    status_actor_login: str | None = None,
):
    return SimpleNamespace(
        id="proj-1",
        name="proj",
        repo_url="https://github.com/owner/repo.git",
        tracker_owner=owner,
        tracker_repo="repo",
        tracker_kind="github_issues",
        webhook_secret=None,
        status_actor_login=status_actor_login,
        status_label_authorized_logins=authorized or [],
    )


def _issue(state: str = "Proposed") -> Issue:
    return Issue(
        id="owner/repo#42",
        identifier="owner/repo#42",
        title="Intake issue",
        state=state,
        issue_type="task",
        requestor_login="alice",
        tracker_kind="github_issues",
    )


def _make_orchestrator(issue: Issue, project=None):
    project = project or _project()
    tracker = MagicMock()
    tracker.repo = "repo"
    tracker.fetch_issue_detail.return_value = issue
    tracker.fetch_comments.return_value = []
    tracker.update_issue = MagicMock()
    tracker.add_label = MagicMock()
    tracker.remove_label = MagicMock()
    tracker.add_comment = MagicMock(return_value={"ok": True})
    tracker.record_trusted_status = MagicMock()
    tracker.record_untrusted_status_label_change = MagicMock()
    tracker.identifier_for_number.side_effect = lambda number: f"owner/repo#{number}"
    tracker._trusted_status_ledger = {}
    tracker._untrusted_status_issues = set()

    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store.list_all.return_value = [project]
    orch.config.tracker_terminal_states = ["Done"]
    orch.state.running = {}
    orch.state.retry_attempts = {}
    orch.state.claimed = set()
    orch.state.completed = set()
    return orch, tracker


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestTransitionGateCore:
    def test_proposed_to_backlog_requires_readiness(self):
        result = check_intake_transition(
            "Proposed",
            "Backlog",
            "alice",
            _project(owner="owner"),
        )

        assert result.allowed is False
        assert "readiness validation" in result.reason

    def test_ready_issue_can_move_to_backlog_without_requestor_approval(self):
        result = check_intake_transition(
            "Proposed",
            "Backlog",
            "alice",
            _project(owner="owner"),
            issue_is_ready=True,
        )

        assert result.allowed is True

    def test_owner_override_is_marked(self):
        result = check_intake_transition(
            "Proposed",
            "Backlog",
            "owner",
            _project(owner="owner"),
        )

        assert result.allowed is True
        assert result.is_owner_override is True

    def test_status_actor_is_project_owner(self):
        result = check_intake_transition(
            "Backlog",
            "Open",
            "status-actor",
            _project(owner="repo-owner", status_actor_login="status-actor"),
        )

        assert result.allowed is True

    def test_non_owner_cannot_make_backlog_issue_open(self):
        result = check_intake_transition(
            "Backlog",
            "Open",
            "alice",
            _project(owner="owner"),
        )

        assert result.allowed is False
        assert "project owner" in result.reason


class TestApiTransitionGates:
    def test_non_owner_patch_cannot_promote_backlog_to_open(self, client):
        orch, tracker = _make_orchestrator(_issue(state="Backlog"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/placeholder",
                json={
                    "issue_key": "owner/repo#42",
                    "project_id": "proj-1",
                    "status": "Open",
                    "actor_login": "alice",
                },
            )

        assert resp.status_code == 403
        error = resp.json()["error"]
        assert error["code"] == "intake_transition_rejected"
        assert "project owner" in error["message"]
        tracker.update_issue.assert_not_called()

    def test_owner_patch_can_promote_backlog_to_open(self, client):
        orch, tracker = _make_orchestrator(_issue(state="Backlog"))

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/placeholder",
                json={
                    "issue_key": "owner/repo#42",
                    "project_id": "proj-1",
                    "status": "Open",
                    "actor_login": "owner",
                },
            )

        assert resp.status_code == 200
        tracker.update_issue.assert_called_once_with("owner/repo#42", status="Open")

    def test_owner_patch_can_promote_project_scoped_display_id(self, client):
        issue = _issue(state="Backlog")
        orch, tracker = _make_orchestrator(issue)

        def fetch_issue_detail(identifier):
            return issue if identifier == "owner/repo#42" else None

        tracker.fetch_issue_detail.side_effect = fetch_issue_detail

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/placeholder",
                json={
                    "issue_key": "repo#42",
                    "project_id": "proj-1",
                    "status": "Open",
                    "actor_login": "owner",
                },
            )

        assert resp.status_code == 200
        tracker.update_issue.assert_called_once_with("owner/repo#42", status="Open")

    def test_proposed_to_backlog_rejection_is_actionable(self, client):
        orch, tracker = _make_orchestrator(_issue(state="Proposed"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/placeholder",
                json={
                    "issue_key": "owner/repo#42",
                    "project_id": "proj-1",
                    "status": "Backlog",
                    "actor_login": "alice",
                },
            )

        assert resp.status_code == 403
        message = resp.json()["error"]["message"]
        assert "readiness validation" in message
        assert "To promote this issue to Backlog" in message
        tracker.update_issue.assert_not_called()

    def test_ready_approved_patch_can_promote_to_backlog(self, client):
        orch, tracker = _make_orchestrator(_issue(state="Proposed"))

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/placeholder",
                json={
                    "issue_key": "owner/repo#42",
                    "project_id": "proj-1",
                    "status": "Backlog",
                    "actor_login": "alice",
                    "issue_is_ready": True,
                    "requestor_approved": True,
                },
            )

        assert resp.status_code == 200
        tracker.update_issue.assert_called_once_with(
            "owner/repo#42",
            status="Backlog",
        )

    def test_owner_override_patch_records_audit_comment(self, client):
        orch, tracker = _make_orchestrator(_issue(state="Proposed"))

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.patch(
                "/api/v1/issues/placeholder",
                json={
                    "issue_key": "owner/repo#42",
                    "project_id": "proj-1",
                    "status": "Backlog",
                    "actor_login": "owner",
                },
            )

        assert resp.status_code == 200
        tracker.update_issue.assert_called_once_with(
            "owner/repo#42",
            status="Backlog",
        )
        comment = tracker.add_comment.call_args.args[1]
        assert "override_readiness" in comment

    def test_status_label_api_cannot_bypass_open_gate(self, client):
        orch, tracker = _make_orchestrator(_issue(state="Proposed"))

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues/placeholder/labels",
                json={
                    "issue_key": "owner/repo#42",
                    "project_id": "proj-1",
                    "label": "oompah:status:open",
                    "actor_login": "alice",
                },
            )

        assert resp.status_code == 403
        tracker.update_issue.assert_not_called()
        tracker.add_label.assert_not_called()

    def test_status_label_api_routes_allowed_status_through_update_issue(self, client):
        orch, tracker = _make_orchestrator(_issue(state="Proposed"))

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues/placeholder/labels",
                json={
                    "issue_key": "owner/repo#42",
                    "project_id": "proj-1",
                    "label": "oompah:status:backlog",
                    "actor_login": "owner",
                },
            )

        assert resp.status_code == 201
        tracker.update_issue.assert_called_once_with(
            "owner/repo#42",
            status="Backlog",
        )
        tracker.add_label.assert_not_called()


class TestWebhookTransitionGates:
    def test_owner_proposed_to_backlog_label_records_override_and_trust(self, client):
        project = _project(owner="owner")
        orch, tracker = _make_orchestrator(_issue(state="Backlog"), project=project)
        tracker._trusted_status_ledger = {42: "Proposed"}

        payload = {
            "action": "labeled",
            "issue": {
                "number": 42,
                "title": "Intake issue",
                "user": {"login": "alice"},
            },
            "label": {"name": "oompah:status:backlog"},
            "repository": {"full_name": "owner/repo"},
            "sender": {"login": "owner"},
        }

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}),
        ):
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "issues",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        tracker.record_trusted_status.assert_called_once_with(42, "Backlog")
        comment = tracker.add_comment.call_args.args[1]
        assert "override_readiness" in comment

    def test_unauthorized_open_label_webhook_marks_untrusted(self, client):
        project = _project(owner="owner")
        orch, tracker = _make_orchestrator(_issue(state="Open"), project=project)
        payload = {
            "action": "labeled",
            "issue": {
                "number": 42,
                "title": "Intake issue",
                "user": {"login": "alice"},
            },
            "label": {"name": "oompah:status:open"},
            "repository": {"full_name": "owner/repo"},
            "sender": {"login": "mallory"},
        }

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.dict("os.environ", {"OOMPAH_BOT_LOGIN": "oompah"}),
        ):
            resp = client.post(
                "/api/v1/webhooks/github",
                content=json.dumps(payload),
                headers={
                    "X-GitHub-Event": "issues",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 200
        for _ in range(100):
            if tracker.record_untrusted_status_label_change.called:
                break
            time.sleep(0.02)

        tracker.record_untrusted_status_label_change.assert_called()
        tracker.record_trusted_status.assert_not_called()


def _response(json_data):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.is_success = True
    resp.headers = httpx.Headers({})
    resp.text = json.dumps(json_data)
    resp.json.return_value = json_data
    resp.request = MagicMock()
    return resp


def _gh_issue(number: int, label: str = "oompah:status:open") -> dict:
    return {
        "number": number,
        "title": f"Issue {number}",
        "body": "",
        "state": "open",
        "labels": [{"name": label}],
        "user": {"login": "alice"},
        "assignees": [],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "html_url": f"https://github.com/org/repo/issues/{number}",
    }


class TestPollingTransitionGates:
    def _tracker(self) -> GitHubIssueTracker:
        auth = MagicMock(spec=GitHubAuth)
        auth.get_token.return_value = "token"
        return GitHubIssueTracker(
            owner="org",
            repo="repo",
            active_states=["Open"],
            terminal_states=["Done"],
            auth=auth,
        )

    def test_polling_rejects_open_label_from_unauthorized_actor(self):
        tracker = self._tracker()
        issues = [_gh_issue(7)]
        events = [
            {
                "event": "labeled",
                "label": {"name": "oompah:status:open"},
                "actor": {"login": "mallory"},
            }
        ]

        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[_response(issues), _response(events)],
        ):
            candidates = tracker.fetch_candidate_issues()

        assert candidates == []
        assert 7 in tracker._untrusted_status_issues
        assert 7 not in tracker._trusted_status_ledger

    def test_polling_trusts_open_label_from_owner(self):
        tracker = self._tracker()
        issues = [_gh_issue(8)]
        events = [
            {
                "event": "labeled",
                "label": {"name": "oompah:status:open"},
                "actor": {"login": "org"},
            }
        ]

        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[_response(issues), _response(events)],
        ):
            candidates = tracker.fetch_candidate_issues()

        assert [issue.issue_number for issue in candidates] == ["8"]
        assert tracker._trusted_status_ledger[8] == "Open"
