"""Tests for labels support in POST /api/v1/issues.

Verifies that the create endpoint parses and forwards labels (focus/routing
labels such as "needs:frontend", "area:api") to tracker.create_issue(), and
that both list and comma-separated string forms are accepted.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue
from oompah.server import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(identifier: str = "tracker-1") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="from tracker",
        state="open",
        issue_type="task",
    )


def _make_orch(tmp_path, project_id: str = "proj-1"):
    """Return a minimal mock orchestrator with a tracker stub."""
    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.repo_path = str(tmp_path)

    mock_tracker = MagicMock()
    mock_tracker.create_issue = MagicMock(return_value=_make_issue())
    mock_tracker.add_label = MagicMock()

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    mock_orch.project_store.get = MagicMock(return_value=mock_project)
    return mock_orch, mock_tracker


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Labels as a JSON list
# ---------------------------------------------------------------------------


class TestCreateIssueLabelsAsList:
    def test_labels_list_forwarded_to_tracker(self, client, tmp_path):
        """Labels provided as a JSON list are passed to tracker.create_issue()."""
        mock_orch, mock_tracker = _make_orch(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "GitHub task with labels",
                    "project_id": "proj-1",
                    "labels": ["needs:frontend", "area:api"],
                    "description": "Task with labels",
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        assert call_kwargs["labels"] == ["needs:frontend", "area:api"]

    def test_single_label_in_list(self, client, tmp_path):
        """A single-element labels list is also forwarded."""
        mock_orch, mock_tracker = _make_orch(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "single label",
                    "project_id": "proj-1",
                    "labels": ["needs:backend"],
                    "description": "Single label task",
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        assert call_kwargs["labels"] == ["needs:backend"]

    def test_empty_list_results_in_none_labels(self, client, tmp_path):
        """An empty labels list is treated as no labels (None)."""
        mock_orch, mock_tracker = _make_orch(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "no labels",
                    "project_id": "proj-1",
                    "labels": [],
                    "description": "No labels task",
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        assert call_kwargs["labels"] is None

    def test_whitespace_only_labels_stripped(self, client, tmp_path):
        """Blank/whitespace-only label strings are filtered out."""
        mock_orch, mock_tracker = _make_orch(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "padded labels",
                    "project_id": "proj-1",
                    "labels": ["  needs:frontend  ", "  ", "area:api"],
                    "description": "Padded labels task",
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        assert call_kwargs["labels"] == ["needs:frontend", "area:api"]


# ---------------------------------------------------------------------------
# Labels as a comma-separated string
# ---------------------------------------------------------------------------


class TestCreateIssueLabelsAsString:
    def test_comma_separated_labels_forwarded(self, client, tmp_path):
        """Labels provided as a comma-separated string are split and forwarded."""
        mock_orch, mock_tracker = _make_orch(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "string labels",
                    "project_id": "proj-1",
                    "labels": "needs:frontend, area:api",
                    "description": "String labels task",
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        assert call_kwargs["labels"] == ["needs:frontend", "area:api"]

    def test_single_label_string(self, client, tmp_path):
        """A single label string with no comma is accepted."""
        mock_orch, mock_tracker = _make_orch(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "one string label",
                    "project_id": "proj-1",
                    "labels": "needs:frontend",
                    "description": "One label task",
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        assert call_kwargs["labels"] == ["needs:frontend"]

    def test_empty_string_results_in_none_labels(self, client, tmp_path):
        """An empty labels string is treated as no labels (None)."""
        mock_orch, mock_tracker = _make_orch(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "empty string labels",
                    "project_id": "proj-1",
                    "labels": "",
                    "description": "Empty labels task",
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        assert call_kwargs["labels"] is None


# ---------------------------------------------------------------------------
# No labels (absent field)
# ---------------------------------------------------------------------------


class TestCreateIssueNoLabels:
    def test_absent_labels_sends_none_to_tracker(self, client, tmp_path):
        """When labels is absent from the request body, None is passed to the tracker."""
        mock_orch, mock_tracker = _make_orch(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "no labels field",
                    "project_id": "proj-1",
                    "description": "No labels field task",
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        assert call_kwargs["labels"] is None

    def test_null_labels_sends_none_to_tracker(self, client, tmp_path):
        """When labels is JSON null, None is passed to the tracker."""
        mock_orch, mock_tracker = _make_orch(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "null labels",
                    "project_id": "proj-1",
                    "labels": None,
                    "description": "Null labels task",
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        assert call_kwargs["labels"] is None


# ---------------------------------------------------------------------------
# Labels combined with target_branch (regression: both can coexist)
# ---------------------------------------------------------------------------


class TestCreateIssueLabelsPlusTargetBranch:
    def test_labels_and_target_branch_both_forwarded(self, client, tmp_path):
        """Labels and target_branch can be sent together in one request."""
        mock_orch, mock_tracker = _make_orch(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "full GitHub issue",
                    "project_id": "proj-1",
                    "type": "task",
                    "priority": 1,
                    "labels": ["needs:frontend"],
                    "target_branch": "release/2.0",
                    "description": "Full GitHub issue description",
                },
            )
        assert resp.status_code == 201
        call_kwargs = mock_tracker.create_issue.call_args.kwargs
        assert call_kwargs["labels"] == ["needs:frontend"]
        # target_branch is persisted on the returned issue object, not in
        # create_issue kwargs, but the response body should include it.
        body = resp.json()
        assert body["ok"] is True
        assert body["issue"]["target_branch"] == "release/2.0"
