"""Tests for tracker identity fields in the issue API schema (TASK-459.1).

Covers:
  1. Board (GET /api/v1/issues) entries include all tracker identity fields.
  2. Detail (GET /api/v1/issues/{id}/detail) responses include all tracker
     identity fields.
  3. Backlog-backed issues expose null/false tracker fields (backward compat).
  4. GitHub-backed issues expose populated tracker identity fields.
  5. display_identifier prefers the model field over the computed fallback.
  6. Create (POST /api/v1/issues) accepts and validates managed_repo,
     target_branch, and work_branch.
  7. Update (PATCH /api/v1/issues/{id}) accepts managed_repo, target_branch,
     work_branch and validates managed_repo format.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue, Project
from oompah.server import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_backlog_issue(identifier: str = "TASK-42") -> Issue:
    """Minimal Backlog-backed Issue with no tracker identity set."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Backlog issue",
        state="open",
        priority=2,
        issue_type="task",
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_github_issue(
    identifier: str = "example-org/oompah-tasks#7",
    issue_number: str = "7",
) -> Issue:
    """Issue object representing a GitHub-backed task with full tracker identity."""
    return Issue(
        id="GH_node_abc123",
        identifier=identifier,
        title="GitHub issue",
        state="open",
        priority=1,
        issue_type="task",
        labels=["area:api"],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        tracker_kind="github_issues",
        tracker_owner="example-org",
        tracker_repo="oompah-tasks",
        issue_number=issue_number,
        display_identifier="tasks#7",
        provider_url="https://github.com/example-org/oompah-tasks/issues/7",
        managed_repo="example-org/trickle",
        target_branch="main",
        work_branch="oompah/trickle/gh-7",
        is_legacy=False,
    )


def _make_legacy_backlog_issue(identifier: str = "TASK-OLD-1") -> Issue:
    """Issue that was created via Backlog but is flagged as legacy."""
    issue = _make_backlog_issue(identifier)
    issue.is_legacy = True
    return issue


def _make_project(project_id: str = "proj-1", name: str = "myproject") -> Project:
    return Project(
        id=project_id,
        name=name,
        repo_url="https://example.invalid/repo.git",
        repo_path="/tmp/fake-repo",
    )


def _make_orch(issues: list, project: Project | None = None) -> MagicMock:
    """Build a minimal mock Orchestrator."""
    p = project or _make_project()
    mock_tracker = MagicMock()
    mock_tracker.fetch_all_issues.return_value = issues
    mock_tracker.fetch_issue_detail = MagicMock(
        side_effect=lambda ident: next(
            (i for i in issues if i.identifier == ident), None
        )
    )
    mock_tracker.fetch_comments.return_value = []
    mock_tracker.fetch_children.return_value = []
    mock_tracker.update_issue = MagicMock()
    mock_tracker.create_issue = MagicMock()
    mock_tracker.add_label = MagicMock()

    orch = MagicMock()
    orch.project_store.list_all.return_value = [p]
    orch._tracker_for_project.return_value = mock_tracker
    orch.tracker = mock_tracker
    orch._unmerged_review_branches = set()

    return orch


@pytest.fixture(autouse=True)
def clear_api_cache():
    server_module._api_cache.clear()
    yield
    server_module._api_cache.clear()


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Board serialization — _fetch_and_serialize_issues
# ---------------------------------------------------------------------------

class TestBoardTrackerIdentityFields:
    """Board entries must include all tracker identity fields."""

    _EXPECTED_TRACKER_KEYS = {
        "tracker_kind",
        "tracker_owner",
        "tracker_repo",
        "issue_number",
        "url",
        "managed_repo",
        "target_branch",
        "work_branch",
        "is_legacy",
    }

    def test_backlog_issue_has_all_tracker_keys_as_null_or_false(self):
        """Backlog-backed board entries contain all tracker identity keys
        (null for string fields, false for is_legacy) — backward compat."""
        issue = _make_backlog_issue()
        orch = _make_orch([issue])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]

        for key in self._EXPECTED_TRACKER_KEYS:
            assert key in entry, f"Expected key {key!r} missing from board entry"

        assert entry["tracker_kind"] is None
        assert entry["tracker_owner"] is None
        assert entry["tracker_repo"] is None
        assert entry["issue_number"] is None
        assert entry["url"] is None
        assert entry["managed_repo"] is None
        assert entry["target_branch"] is None
        assert entry["work_branch"] is None
        assert entry["is_legacy"] is False

    def test_github_issue_has_populated_tracker_fields(self):
        """GitHub-backed board entries expose all tracker identity values."""
        issue = _make_github_issue()
        orch = _make_orch([issue])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]

        assert entry["tracker_kind"] == "github_issues"
        assert entry["tracker_owner"] == "example-org"
        assert entry["tracker_repo"] == "oompah-tasks"
        assert entry["issue_number"] == "7"
        assert entry["url"] == "https://github.com/example-org/oompah-tasks/issues/7"
        assert entry["managed_repo"] == "example-org/trickle"
        assert entry["target_branch"] == "main"
        assert entry["work_branch"] == "oompah/trickle/gh-7"
        assert entry["is_legacy"] is False

    def test_legacy_backlog_issue_has_is_legacy_true(self):
        """Issues marked is_legacy=True surface that flag in the board entry."""
        issue = _make_legacy_backlog_issue()
        orch = _make_orch([issue])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]

        assert entry["is_legacy"] is True

    def test_display_identifier_prefers_model_field_for_github_issues(self):
        """When Issue.display_identifier is set, the board uses it verbatim."""
        issue = _make_github_issue()
        # issue.display_identifier == "tasks#7" (set in constructor)
        orch = _make_orch([issue])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]

        assert entry["display_identifier"] == "tasks#7"

    def test_display_identifier_falls_back_for_backlog_issues(self):
        """Backlog issues without a model display_identifier get the computed form."""
        issue = _make_backlog_issue("TASK-99")
        orch = _make_orch([issue], project=_make_project(name="myproject"))

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]

        # Computed form: "<ProjectName>-<number>"
        assert entry["display_identifier"] == "myproject-99"

    def test_url_falls_back_to_provider_url(self):
        """When issue.url is None but provider_url is set, url field uses provider_url."""
        issue = _make_backlog_issue("TASK-5")
        issue.provider_url = "https://example.com/issue/5"
        # url field is not explicitly set on Issue (it's None by default)
        orch = _make_orch([issue])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]

        assert entry["url"] == "https://example.com/issue/5"

    def test_url_prefers_issue_url_over_provider_url(self):
        """When both url and provider_url are set, url takes priority."""
        issue = _make_backlog_issue("TASK-6")
        issue.url = "https://primary.example.com/6"
        issue.provider_url = "https://secondary.example.com/6"
        orch = _make_orch([issue])

        data = server_module._fetch_and_serialize_issues(orch)
        entry = data["Open"][0]

        assert entry["url"] == "https://primary.example.com/6"


# ---------------------------------------------------------------------------
# Detail endpoint — GET /api/v1/issues/{identifier}/detail
# ---------------------------------------------------------------------------

class TestDetailTrackerIdentityFields:
    """Detail responses must include all tracker identity fields."""

    _EXPECTED_TRACKER_KEYS = {
        "tracker_kind",
        "tracker_owner",
        "tracker_repo",
        "issue_number",
        "url",
        "managed_repo",
        "target_branch",
        "work_branch",
        "is_legacy",
    }

    def test_backlog_issue_detail_has_null_tracker_fields(self, client):
        """Detail for a Backlog-backed issue returns null tracker identity."""
        issue = _make_backlog_issue()
        orch = _make_orch([issue])

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-42/detail",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        body = resp.json()

        for key in self._EXPECTED_TRACKER_KEYS:
            assert key in body, f"Expected key {key!r} missing from detail response"

        assert body["tracker_kind"] is None
        assert body["tracker_owner"] is None
        assert body["tracker_repo"] is None
        assert body["issue_number"] is None
        assert body["url"] is None
        assert body["managed_repo"] is None
        assert body["target_branch"] is None
        assert body["work_branch"] is None
        assert body["is_legacy"] is False

    def test_github_issue_detail_has_populated_tracker_fields(self, client):
        """Detail for a GitHub-backed issue returns full tracker identity.

        GitHub identifiers contain slashes and hashes (URL-special chars)
        so this test uses the node ID as the route param and has the mock
        tracker return the issue regardless of the identifier value.  URL
        routing for fully-qualified GitHub identifiers is a Phase 5 concern.
        """
        issue = _make_github_issue()
        # Use the stable node ID as the route param to avoid URL encoding
        # issues with slashes/hashes in the identifier string.
        node_id = issue.id  # "GH_node_abc123"
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = issue
        mock_tracker.fetch_comments.return_value = []
        mock_tracker.fetch_children.return_value = []
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_make_project()]
        orch._tracker_for_project.return_value = mock_tracker
        orch.tracker = mock_tracker

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                f"/api/v1/issues/{node_id}/detail",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        body = resp.json()

        assert body["tracker_kind"] == "github_issues"
        assert body["tracker_owner"] == "example-org"
        assert body["tracker_repo"] == "oompah-tasks"
        assert body["issue_number"] == "7"
        assert (
            body["url"]
            == "https://github.com/example-org/oompah-tasks/issues/7"
        )
        assert body["managed_repo"] == "example-org/trickle"
        assert body["target_branch"] == "main"
        assert body["work_branch"] == "oompah/trickle/gh-7"
        assert body["is_legacy"] is False

    def test_detail_display_identifier_prefers_model_field(self, client):
        """Detail uses Issue.display_identifier when set (GitHub short form)."""
        issue = _make_github_issue()
        node_id = issue.id
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = issue
        mock_tracker.fetch_comments.return_value = []
        mock_tracker.fetch_children.return_value = []
        orch = MagicMock()
        orch.project_store.list_all.return_value = [_make_project()]
        orch._tracker_for_project.return_value = mock_tracker
        orch.tracker = mock_tracker

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                f"/api/v1/issues/{node_id}/detail",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert resp.json()["display_identifier"] == "tasks#7"

    def test_detail_legacy_marker_is_true_for_legacy_issues(self, client):
        """Detail for a legacy Backlog issue has is_legacy=true."""
        issue = _make_legacy_backlog_issue()
        orch = _make_orch([issue])

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                "/api/v1/issues/TASK-OLD-1/detail",
                params={"project_id": "proj-1"},
            )

        assert resp.status_code == 200
        assert resp.json()["is_legacy"] is True


# ---------------------------------------------------------------------------
# Create endpoint — POST /api/v1/issues
# ---------------------------------------------------------------------------

class TestCreateIssueTrackerFields:
    """POST /api/v1/issues validates and accepts tracker identity fields."""

    def _make_create_orch(self, created_issue: Issue) -> MagicMock:
        """Build an orchestrator whose tracker creates the given issue."""
        project = _make_project()
        mock_tracker = MagicMock()
        mock_tracker.create_issue.return_value = created_issue
        mock_tracker.add_label = MagicMock()

        orch = MagicMock()
        orch.project_store.list_all.return_value = [project]
        orch._tracker_for_project.return_value = mock_tracker
        orch.tracker = mock_tracker

        return orch

    def test_create_accepts_managed_repo_target_branch_work_branch(self, client):
        """Valid create request with tracker metadata fields returns 201."""
        created = _make_backlog_issue("TASK-100")
        orch = self._make_create_orch(created)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "New task",
                    "project_id": "proj-1",
                    "managed_repo": "acme/widget",
                    "target_branch": "main",
                    "work_branch": "oompah/widget/gh-100",
                },
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["ok"] is True
        # Fields flow through to the response
        assert body["issue"]["managed_repo"] == "acme/widget"
        assert body["issue"]["target_branch"] == "main"
        assert body["issue"]["work_branch"] == "oompah/widget/gh-100"

    def test_create_returns_tracker_kind_none_for_backlog_issue(self, client):
        """Create response includes null tracker fields for Backlog-backed issue."""
        created = _make_backlog_issue("TASK-101")
        orch = self._make_create_orch(created)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "Backlog task", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        issue_payload = resp.json()["issue"]
        assert issue_payload["tracker_kind"] is None
        assert issue_payload["tracker_owner"] is None
        assert issue_payload["tracker_repo"] is None
        assert issue_payload["issue_number"] is None
        assert issue_payload["is_legacy"] is False

    def test_create_returns_tracker_fields_for_github_issue(self, client):
        """Create response includes populated tracker fields for GitHub-backed issue."""
        created = _make_github_issue()
        orch = self._make_create_orch(created)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "GitHub task", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        issue_payload = resp.json()["issue"]
        assert issue_payload["tracker_kind"] == "github_issues"
        assert issue_payload["tracker_owner"] == "example-org"
        assert issue_payload["tracker_repo"] == "oompah-tasks"
        assert issue_payload["issue_number"] == "7"
        assert issue_payload["is_legacy"] is False

    def test_create_rejects_managed_repo_without_slash(self, client):
        """managed_repo must be in owner/repo format; bare name returns 400."""
        created = _make_backlog_issue("TASK-102")
        orch = self._make_create_orch(created)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "Bad managed repo",
                    "project_id": "proj-1",
                    "managed_repo": "justarepo",  # missing owner/
                },
            )

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "validation"
        assert "owner/repo" in body["error"]["message"]

    def test_create_accepts_empty_managed_repo(self, client):
        """Absent or empty managed_repo is silently ignored (not required)."""
        created = _make_backlog_issue("TASK-103")
        orch = self._make_create_orch(created)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "No managed repo", "project_id": "proj-1"},
            )

        assert resp.status_code == 201

    def test_create_response_always_has_is_legacy_key(self, client):
        """The is_legacy key is always present in the create response."""
        created = _make_backlog_issue("TASK-104")
        orch = self._make_create_orch(created)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "Task", "project_id": "proj-1"},
            )

        assert resp.status_code == 201
        assert "is_legacy" in resp.json()["issue"]


# ---------------------------------------------------------------------------
# Update endpoint — PATCH /api/v1/issues/{identifier}
# ---------------------------------------------------------------------------

class TestUpdateIssueTrackerFields:
    """PATCH /api/v1/issues/{id} validates managed_repo format and passes
    tracker metadata fields to the tracker adapter."""

    def _make_update_orch(self, existing: Issue | None = None) -> MagicMock:
        issue = existing or _make_backlog_issue()
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = issue
        mock_tracker.update_issue = MagicMock()

        orch = MagicMock()
        orch._tracker_for_project.return_value = mock_tracker
        orch.config.tracker_terminal_states = ["Done"]
        orch.state.running = {}
        orch.state.retry_attempts = {}
        return orch

    def test_update_rejects_managed_repo_without_slash(self, client):
        """PATCH with malformed managed_repo returns 400."""
        orch = self._make_update_orch()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-42",
                json={
                    "project_id": "proj-1",
                    "managed_repo": "noslash",
                },
            )

        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "validation"
        assert "owner/repo" in body["error"]["message"]

    def test_update_accepts_valid_managed_repo(self, client):
        """PATCH with valid managed_repo passes validation and calls tracker."""
        orch = self._make_update_orch()
        mock_tracker = orch._tracker_for_project.return_value

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-42",
                json={
                    "project_id": "proj-1",
                    "managed_repo": "acme/widget",
                },
            )

        assert resp.status_code == 200
        mock_tracker.update_issue.assert_called_once()
        call_kwargs = mock_tracker.update_issue.call_args[1]
        assert call_kwargs.get("managed_repo") == "acme/widget"

    def test_update_passes_target_branch_to_tracker(self, client):
        """PATCH with target_branch passes it to tracker.update_issue."""
        orch = self._make_update_orch()
        mock_tracker = orch._tracker_for_project.return_value

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-42",
                json={
                    "project_id": "proj-1",
                    "target_branch": "release/1.2",
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_tracker.update_issue.call_args[1]
        assert call_kwargs.get("target_branch") == "release/1.2"

    def test_update_passes_work_branch_to_tracker(self, client):
        """PATCH with work_branch passes it to tracker.update_issue."""
        orch = self._make_update_orch()
        mock_tracker = orch._tracker_for_project.return_value

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-42",
                json={
                    "project_id": "proj-1",
                    "work_branch": "oompah/widget/gh-42",
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_tracker.update_issue.call_args[1]
        assert call_kwargs.get("work_branch") == "oompah/widget/gh-42"

    def test_update_ignores_empty_tracker_fields(self, client):
        """Empty-string tracker fields are not passed to tracker.update_issue."""
        orch = self._make_update_orch()
        mock_tracker = orch._tracker_for_project.return_value

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.patch(
                "/api/v1/issues/TASK-42",
                json={
                    "project_id": "proj-1",
                    "managed_repo": "",
                    "target_branch": "  ",
                },
            )

        assert resp.status_code == 200
        # update_issue should not have been called since all field values are
        # empty (stripped to None) and no standard fields changed.
        mock_tracker.update_issue.assert_not_called()


# ---------------------------------------------------------------------------
# Issue model fields — unit tests
# ---------------------------------------------------------------------------

class TestIssueModelTrackerFields:
    """Unit tests for the Issue dataclass tracker identity fields."""

    def test_issue_defaults_to_all_none_tracker_fields(self):
        """A minimal Issue has None for all optional tracker identity fields."""
        issue = Issue(id="x", identifier="x", title="X")
        assert issue.tracker_kind is None
        assert issue.tracker_owner is None
        assert issue.tracker_repo is None
        assert issue.issue_number is None
        assert issue.display_identifier is None
        assert issue.provider_url is None
        assert issue.managed_repo is None
        assert issue.work_branch is None
        assert issue.is_legacy is False

    def test_issue_accepts_all_tracker_fields(self):
        """Issue can be constructed with all tracker identity fields."""
        issue = Issue(
            id="GH_node",
            identifier="owner/tasks#42",
            title="GH task",
            tracker_kind="github_issues",
            tracker_owner="owner",
            tracker_repo="tasks",
            issue_number="42",
            display_identifier="tasks#42",
            provider_url="https://github.com/owner/tasks/issues/42",
            managed_repo="owner/code",
            target_branch="main",
            work_branch="oompah/code/gh-42",
            is_legacy=False,
        )
        assert issue.tracker_kind == "github_issues"
        assert issue.tracker_owner == "owner"
        assert issue.tracker_repo == "tasks"
        assert issue.issue_number == "42"
        assert issue.display_identifier == "tasks#42"
        assert issue.managed_repo == "owner/code"
        assert issue.work_branch == "oompah/code/gh-42"
        assert issue.is_legacy is False

    def test_issue_is_legacy_can_be_true(self):
        """is_legacy=True is preserved on construction."""
        issue = Issue(id="bl", identifier="TASK-1", title="old", is_legacy=True)
        assert issue.is_legacy is True
