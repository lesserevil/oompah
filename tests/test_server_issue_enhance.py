"""Tests for the issue-enhancement query param on POST /api/v1/issues,
the managed_repo create flow, and the supporting GET
/api/v1/projects/{id}/issue-quality-source endpoint. See oompah-zlz_2-u8pz.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.issue_enhancer import EnhancementResult, IssueEnhancerError
from oompah.models import Issue
from oompah.server import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(identifier="tracker-1", issue_type="task"):
    return Issue(
        id=identifier,
        identifier=identifier,
        title="from tracker",
        state="open",
        issue_type=issue_type,
    )


def _make_orch_with_project(tmp_path, project_id="proj-1"):
    """Build a mock orchestrator with a stub project + tracker."""
    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.repo_path = str(tmp_path)

    mock_tracker = MagicMock()
    mock_tracker.create_issue = MagicMock(return_value=_make_issue())
    mock_tracker.add_label = MagicMock()
    mock_tracker.add_parent_child = MagicMock()

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    mock_orch.project_store.get = MagicMock(return_value=mock_project)
    # Default role resolution: provide a fake provider + model.
    fake_provider = MagicMock()
    fake_provider.base_url = "https://x"
    fake_provider.api_key = "k"
    mock_orch._resolve_role = MagicMock(return_value=(fake_provider, "gpt-test"))
    mock_orch.provider_store.get_default = MagicMock(return_value=fake_provider)
    return mock_orch, mock_tracker, mock_project


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def _enhancement(title="Better", desc="Better body"):
    return EnhancementResult(
        original_title="fix the thing",
        original_description="thing broken",
        enhanced_title=title,
        enhanced_description=desc,
        missing_fields=["acceptance criteria"],
        suggested_changes="expanded with AC",
        diff="-thing broken\n+Better body",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/issues?enhance=true → preview only
# ---------------------------------------------------------------------------


class TestEnhancePreview:
    def test_returns_preview_without_writing(self, client, tmp_path):
        mock_orch, mock_tracker, _ = _make_orch_with_project(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "enhance_issue", return_value=_enhancement()),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues?enhance=true",
                json={
                    "title": "fix the thing",
                    "description": "thing broken",
                    "project_id": "proj-1",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["mode"] == "enhance_preview"
        assert body["original"]["title"] == "fix the thing"
        assert body["enhanced"]["title"] == "Better"
        assert "expanded" in body["suggested_changes"]
        # Nothing written.
        mock_tracker.create_issue.assert_not_called()

    def test_returns_502_on_enhancer_error(self, client, tmp_path):
        mock_orch, mock_tracker, _ = _make_orch_with_project(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(
                server_module, "enhance_issue",
                side_effect=IssueEnhancerError("no AGENTS.md"),
            ),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues?enhance=true",
                json={
                    "title": "x",
                    "description": "y",
                    "project_id": "proj-1",
                },
            )
        assert resp.status_code == 502
        assert resp.json()["error"]["code"] == "enhance_failed"
        mock_tracker.create_issue.assert_not_called()

    def test_400_on_empty_title(self, client, tmp_path):
        mock_orch, _, _ = _make_orch_with_project(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues?enhance=true",
                json={"title": "  ", "project_id": "proj-1"},
            )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /api/v1/issues?enhance=apply → enhance then write
# ---------------------------------------------------------------------------


class TestEnhanceApply:
    def test_writes_enhanced_version(self, client, tmp_path):
        mock_orch, mock_tracker, _ = _make_orch_with_project(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "enhance_issue", return_value=_enhancement()),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues?enhance=apply",
                json={
                    "title": "fix the thing",
                    "description": "thing broken",
                    "project_id": "proj-1",
                    "type": "task",
                },
            )
        assert resp.status_code == 201
        # tracker.create_issue called with the ENHANCED fields.
        call = mock_tracker.create_issue.call_args
        assert call.kwargs["title"] == "Better"
        assert call.kwargs["description"] == "Better body"

    def test_falls_back_to_verbatim_on_enhancer_error(self, client, tmp_path):
        mock_orch, mock_tracker, _ = _make_orch_with_project(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(
                server_module, "enhance_issue",
                side_effect=IssueEnhancerError("transient"),
            ),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues?enhance=apply",
                json={
                    "title": "fix the thing",
                    "description": "thing broken",
                    "project_id": "proj-1",
                    "type": "task",
                },
            )
        assert resp.status_code == 201
        call = mock_tracker.create_issue.call_args
        # Operator's input preserved verbatim.
        assert call.kwargs["title"] == "fix the thing"
        assert call.kwargs["description"] == "thing broken"


# ---------------------------------------------------------------------------
# POST /api/v1/issues (no enhance flag) → verbatim, back-compat
# ---------------------------------------------------------------------------


class TestVerbatimBackCompat:
    def test_writes_input_unchanged(self, client, tmp_path):
        mock_orch, mock_tracker, _ = _make_orch_with_project(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module, "enhance_issue") as mock_enhance,
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "raw title",
                    "description": "raw desc",
                    "project_id": "proj-1",
                    "type": "task",
                },
            )
        assert resp.status_code == 201
        # Enhancer was NOT called.
        mock_enhance.assert_not_called()
        call = mock_tracker.create_issue.call_args
        assert call.kwargs["title"] == "raw title"
        assert call.kwargs["description"] == "raw desc"

    def test_unknown_enhance_value_falls_through_to_verbatim(self, client, tmp_path):
        mock_orch, mock_tracker, _ = _make_orch_with_project(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            patch.object(server_module, "enhance_issue") as mock_enhance,
        ):
            resp = client.post(
                "/api/v1/issues?enhance=lol",
                json={
                    "title": "raw",
                    "project_id": "proj-1",
                    "type": "task",
                    "description": "Raw verbatim description",
                },
            )
        assert resp.status_code == 201
        mock_enhance.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{id}/issue-quality-source
# ---------------------------------------------------------------------------


class TestIssueQualitySourceEndpoint:
    def test_reports_agents_md(self, client, tmp_path):
        (tmp_path / "AGENTS.md").write_text("rules")
        mock_orch, _, _ = _make_orch_with_project(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/projects/proj-1/issue-quality-source")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_source"] is True
        assert body["kind"] == "agents_md"

    def test_reports_no_source(self, client, tmp_path):
        mock_orch, _, _ = _make_orch_with_project(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/projects/proj-1/issue-quality-source")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_source"] is False
        assert body["kind"] == ""

    def test_reports_workflow_quality(self, client, tmp_path):
        (tmp_path / "WORKFLOW.md").write_text("## issue.quality\nrules")
        mock_orch, _, _ = _make_orch_with_project(tmp_path)
        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/projects/proj-1/issue-quality-source")
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_source"] is True
        assert body["kind"] == "workflow_quality"

    def test_404_for_unknown_project(self, client, tmp_path):
        mock_orch, _, _ = _make_orch_with_project(tmp_path)
        mock_orch.project_store.get = MagicMock(return_value=None)
        with patch.object(server_module, "_get_orchestrator", return_value=mock_orch):
            resp = client.get("/api/v1/projects/missing/issue-quality-source")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# _run_issue_enhancement helper
# ---------------------------------------------------------------------------


class TestRunIssueEnhancementHelper:
    def test_requires_project_id(self, tmp_path):
        mock_orch, _, _ = _make_orch_with_project(tmp_path)
        with pytest.raises(IssueEnhancerError, match="project_id is required"):
            server_module._run_issue_enhancement(
                orch=mock_orch, project_id="", title="t", description="d",
            )

    def test_404_when_project_missing(self, tmp_path):
        mock_orch, _, _ = _make_orch_with_project(tmp_path)
        mock_orch.project_store.get = MagicMock(return_value=None)
        with pytest.raises(IssueEnhancerError, match="not found"):
            server_module._run_issue_enhancement(
                orch=mock_orch, project_id="x", title="t", description="d",
            )

    def test_falls_back_to_default_provider(self, tmp_path):
        """When RoleStore('default') is empty, use provider_store.get_default()
        plus the provider's own model_roles → default_model → models[0]
        resolution chain (mirrors completion_verifier)."""
        (tmp_path / "AGENTS.md").write_text("rules")
        mock_orch, _, _ = _make_orch_with_project(tmp_path)
        # RoleStore returns nothing.
        mock_orch._resolve_role = MagicMock(return_value=(None, None))
        fake_provider = MagicMock()
        fake_provider.base_url = "https://x"
        fake_provider.api_key = "k"
        fake_provider.model_roles = {"default": "via-role-map"}
        fake_provider.default_model = None
        mock_orch.provider_store.get_default = MagicMock(return_value=fake_provider)

        captured = {}

        def fake_enhance(**kwargs):
            captured.update(kwargs)
            return _enhancement()

        with patch.object(server_module, "enhance_issue", side_effect=fake_enhance):
            server_module._run_issue_enhancement(
                orch=mock_orch, project_id="proj-1", title="t", description="d",
            )
        assert captured["provider"] is fake_provider
        assert captured["model"] == "via-role-map"

    def test_uses_default_model_when_role_map_empty(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("rules")
        mock_orch, _, _ = _make_orch_with_project(tmp_path)
        mock_orch._resolve_role = MagicMock(return_value=(None, None))
        fake_provider = MagicMock()
        fake_provider.base_url = "https://x"
        fake_provider.api_key = "k"
        fake_provider.model_roles = {}
        fake_provider.default_model = "the-default"
        mock_orch.provider_store.get_default = MagicMock(return_value=fake_provider)

        captured = {}

        def fake_enhance(**kwargs):
            captured.update(kwargs)
            return _enhancement()

        with patch.object(server_module, "enhance_issue", side_effect=fake_enhance):
            server_module._run_issue_enhancement(
                orch=mock_orch, project_id="proj-1", title="t", description="d",
            )
        assert captured["model"] == "the-default"


# ---------------------------------------------------------------------------
# POST /api/v1/issues — create via managed_repo (backend-neutral, TASK-459.2)
# ---------------------------------------------------------------------------


def _make_orch_with_managed_repo(
    tmp_path,
    project_id: str = "proj-2",
    repo_url: str = "https://github.com/example-org/trickle",
):
    """Build a mock orchestrator whose project is identified by managed repo URL."""
    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.repo_path = str(tmp_path)
    mock_project.repo_url = repo_url

    mock_tracker = MagicMock()
    mock_tracker.create_issue = MagicMock(return_value=_make_issue())
    mock_tracker.add_label = MagicMock()

    mock_orch = MagicMock()
    mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
    mock_orch.project_store.get = MagicMock(return_value=mock_project)
    mock_orch.project_store.list_all = MagicMock(return_value=[mock_project])
    mock_orch._resolve_role = MagicMock(return_value=(MagicMock(), "m"))
    mock_orch.provider_store.get_default = MagicMock(return_value=None)
    return mock_orch, mock_tracker, mock_project


class TestCreateIssueManagedRepo:
    """POST /api/v1/issues with managed_repo instead of project_id."""

    def test_create_via_managed_repo_succeeds(self, client, tmp_path):
        """Creating with managed_repo finds the project by URL slug."""
        mock_orch, mock_tracker, _ = _make_orch_with_managed_repo(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "New GitHub task",
                    "managed_repo": "example-org/trickle",
                    "type": "task",
                    "description": "GitHub task description",
                },
            )
        assert resp.status_code == 201
        assert resp.json()["ok"] is True
        mock_tracker.create_issue.assert_called_once()

    def test_create_via_managed_repo_ssh_url(self, client, tmp_path):
        """SSH git remote URLs are also matched for managed_repo lookup."""
        mock_orch, mock_tracker, _ = _make_orch_with_managed_repo(
            tmp_path, repo_url="git@github.com:example-org/trickle.git"
        )
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "SSH repo task",
                    "managed_repo": "example-org/trickle",
                    "type": "task",
                    "description": "SSH repo task description",
                },
            )
        assert resp.status_code == 201
        mock_tracker.create_issue.assert_called_once()

    def test_create_without_project_id_or_managed_repo_returns_400(self, client, tmp_path):
        """Neither project_id nor managed_repo → 400 validation error."""
        mock_orch, mock_tracker, _ = _make_orch_with_managed_repo(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "no project", "description": "No project description"},
            )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "validation"
        assert "project_id" in data["error"]["message"] or "managed_repo" in data["error"]["message"]
        mock_tracker.create_issue.assert_not_called()

    def test_create_managed_repo_bad_format_returns_400(self, client, tmp_path):
        """managed_repo without slash returns 400 validation error."""
        mock_orch, _, _ = _make_orch_with_managed_repo(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "bad repo", "managed_repo": "nodash"},
            )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "validation"

    def test_create_managed_repo_no_match_returns_404(self, client, tmp_path):
        """managed_repo that matches no project returns 404."""
        mock_orch, _, _ = _make_orch_with_managed_repo(tmp_path)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={"title": "unknown repo", "managed_repo": "nobody/nowhere", "description": "Unknown repo description"},
            )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    def test_project_id_wins_over_managed_repo(self, client, tmp_path):
        """When both project_id and managed_repo are given, project_id wins."""
        mock_orch, mock_tracker, mock_project = _make_orch_with_managed_repo(tmp_path)
        # project_store.get returns the project when looked up by project_id
        mock_orch.project_store.get = MagicMock(return_value=mock_project)
        with (
            patch.object(server_module, "_get_orchestrator", return_value=mock_orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        ):
            resp = client.post(
                "/api/v1/issues",
                json={
                    "title": "explicit project",
                    "project_id": "proj-2",
                    "managed_repo": "example-org/trickle",
                    "type": "task",
                    "description": "Explicit project description",
                },
            )
        assert resp.status_code == 201
        # Tracker was fetched via _tracker_for_project (project_id path)
        mock_orch._tracker_for_project.assert_called_with("proj-2")


# ---------------------------------------------------------------------------
# Helpers: _resolve_identifier, _managed_repo_slug, _get_tracker_for_managed_repo
# ---------------------------------------------------------------------------


class TestResolveIdentifier:
    """Unit tests for the _resolve_identifier helper."""

    def test_path_param_used_when_no_overrides(self):
        result = server_module._resolve_identifier("TASK-123", {}, {})
        assert result == "TASK-123"

    def test_body_issue_key_overrides_path_param(self):
        result = server_module._resolve_identifier(
            "placeholder", {"issue_key": "example-org/oompah-tasks#1234"}, {}
        )
        assert result == "example-org/oompah-tasks#1234"

    def test_query_issue_key_overrides_path_param(self):
        result = server_module._resolve_identifier(
            "placeholder", {}, {"issue_key": "example-org/oompah-tasks#1234"}
        )
        assert result == "example-org/oompah-tasks#1234"

    def test_body_issue_key_wins_over_query(self):
        result = server_module._resolve_identifier(
            "placeholder",
            {"issue_key": "body-key"},
            {"issue_key": "query-key"},
        )
        assert result == "body-key"

    def test_url_decodes_path_param(self):
        # %23 is #; this should be decoded even when no issue_key is given.
        result = server_module._resolve_identifier("tasks%231234", {}, {})
        assert result == "tasks#1234"

    def test_empty_issue_key_falls_back_to_path_param(self):
        result = server_module._resolve_identifier("TASK-99", {"issue_key": "   "}, {})
        assert result == "TASK-99"

    def test_none_body_uses_path_param(self):
        result = server_module._resolve_identifier("TASK-42", None, None)
        assert result == "TASK-42"


class TestManagedRepoSlug:
    """Unit tests for the _managed_repo_slug helper."""

    def test_https_url(self):
        assert server_module._managed_repo_slug(
            "https://github.com/example-org/trickle"
        ) == "example-org/trickle"

    def test_https_url_with_git_suffix(self):
        assert server_module._managed_repo_slug(
            "https://github.com/example-org/trickle.git"
        ) == "example-org/trickle"

    def test_ssh_url(self):
        assert server_module._managed_repo_slug(
            "git@github.com:example-org/trickle.git"
        ) == "example-org/trickle"

    def test_ssh_url_no_git_suffix(self):
        assert server_module._managed_repo_slug(
            "git@github.com:example-org/trickle"
        ) == "example-org/trickle"

    def test_returns_none_for_local_path(self):
        assert server_module._managed_repo_slug("/home/user/repo") is None

    def test_empty_string(self):
        assert server_module._managed_repo_slug("") is None


class TestGetTrackerForManagedRepo:
    """Unit tests for the _get_tracker_for_managed_repo helper."""

    def _make_orch(self, repo_url: str, project_id: str = "proj-x"):
        mock_project = MagicMock()
        mock_project.id = project_id
        mock_project.repo_url = repo_url
        mock_tracker = MagicMock()
        mock_orch = MagicMock()
        mock_orch._tracker_for_project = MagicMock(return_value=mock_tracker)
        mock_orch.project_store.list_all = MagicMock(return_value=[mock_project])
        return mock_orch, mock_tracker, mock_project

    def test_finds_project_by_https_url(self):
        mock_orch, mock_tracker, _ = self._make_orch(
            "https://github.com/example-org/trickle.git"
        )
        tracker, project_id = server_module._get_tracker_for_managed_repo(
            mock_orch, "example-org/trickle"
        )
        assert tracker is mock_tracker
        assert project_id == "proj-x"

    def test_finds_project_by_ssh_url(self):
        mock_orch, mock_tracker, _ = self._make_orch(
            "git@github.com:example-org/trickle.git"
        )
        tracker, project_id = server_module._get_tracker_for_managed_repo(
            mock_orch, "example-org/trickle"
        )
        assert tracker is mock_tracker

    def test_case_insensitive_match(self):
        mock_orch, mock_tracker, _ = self._make_orch(
            "https://github.com/Example-Org/Trickle"
        )
        tracker, _ = server_module._get_tracker_for_managed_repo(
            mock_orch, "example-org/trickle"
        )
        assert tracker is mock_tracker

    def test_raises_when_no_match(self):
        mock_orch, _, _ = self._make_orch(
            "https://github.com/someone/other"
        )
        with pytest.raises(ValueError, match="No project found"):
            server_module._get_tracker_for_managed_repo(
                mock_orch, "example-org/trickle"
            )
