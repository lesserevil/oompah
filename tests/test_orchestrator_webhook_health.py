"""Tests for adaptive polling with webhook health check (oompah-zlz_2-vt9)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Project
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_project(
    project_id: str = "proj-1",
    last_webhook_received_at: datetime | None = None,
    repo_url: str = "https://github.com/org/repo",
) -> Project:
    return Project(
        id=project_id,
        name=f"Test Project {project_id}",
        repo_url=repo_url,
        repo_path=f"/tmp/repos/{project_id}",
        last_webhook_received_at=last_webhook_received_at,
    )


def _make_orchestrator(projects: list[Project] | None = None):
    """Create a test orchestrator with mocked project store."""
    project_store = MagicMock()
    project_store.list_all.return_value = list(projects or [])
    project_store.get.side_effect = lambda pid: next(
        (p for p in (projects or []) if p.id == pid), None
    )
    return Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
    )


# ---------------------------------------------------------------------------
# is_webhook_healthy
# ---------------------------------------------------------------------------


class TestIsWebhookHealthy:
    def test_no_webhook_ever_received(self):
        """Project with no last_webhook_received_at is unhealthy (needs polling)."""
        proj = _make_project(
            project_id="proj-1",
            last_webhook_received_at=None,
        )
        project_store = MagicMock()
        project_store.get.return_value = proj
        orch = _make_orchestrator(projects=[proj])
        orch.project_store = project_store
        assert orch.is_webhook_healthy("proj-1") is False

    def test_project_not_found(self):
        """Unknown project is unhealthy (should fall back to polling)."""
        orch = _make_orchestrator(projects=[])
        assert orch.is_webhook_healthy("nonexistent") is False

    def test_recent_webhook_within_threshold(self):
        """Recent webhook (within 150s) = healthy."""
        proj = _make_project(
            project_id="proj-1",
            last_webhook_received_at=datetime.now(timezone.utc) - timedelta(seconds=60),
        )
        project_store = MagicMock()
        project_store.get.return_value = proj
        orch = _make_orchestrator(projects=[proj])
        orch.project_store = project_store
        assert orch.is_webhook_healthy("proj-1") is True

    def test_webhook_just_at_threshold_boundary(self):
        """Webhook just under 150s threshold = healthy."""
        proj = _make_project(
            project_id="proj-1",
            last_webhook_received_at=datetime.now(timezone.utc) - timedelta(seconds=149),
        )
        project_store = MagicMock()
        project_store.get.return_value = proj
        orch = _make_orchestrator(projects=[proj])
        orch.project_store = project_store
        assert orch.is_webhook_healthy("proj-1") is True

    def test_slightly_stale_webhook_above_threshold(self):
        """Webhook older than 150s = unhealthy."""
        proj = _make_project(
            project_id="proj-1",
            last_webhook_received_at=datetime.now(timezone.utc) - timedelta(seconds=180),
        )
        project_store = MagicMock()
        project_store.get.return_value = proj
        orch = _make_orchestrator(projects=[proj])
        orch.project_store = project_store
        assert orch.is_webhook_healthy("proj-1") is False

    def test_very_old_webhook(self):
        """Webhook several minutes old = unhealthy."""
        proj = _make_project(
            project_id="proj-1",
            last_webhook_received_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        project_store = MagicMock()
        project_store.get.return_value = proj
        orch = _make_orchestrator(projects=[proj])
        orch.project_store = project_store
        assert orch.is_webhook_healthy("proj-1") is False

    def test_none_project_id_returns_false(self):
        """None project_id is unhealthy."""
        orch = _make_orchestrator(projects=[])
        assert orch.is_webhook_healthy(None) is False


# ---------------------------------------------------------------------------
# _fetch_all_reviews — adaptive skipping
# ---------------------------------------------------------------------------


def _make_orchestrator_with_store(projects: list[Project]):
    """Create orchestrator that maps project_store correctly."""
    project_store = MagicMock()
    project_store.list_all.return_value = projects

    def get_project(pid):
        for p in projects:
            if p.id == pid:
                return p
        return None

    project_store.get.side_effect = get_project
    orch = Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
    )
    return orch


class TestFetchAllReviewsSkipsHealthy:
    def test_skips_healthy_project_no_api_called(self):
        """Healthy project should not trigger forge API calls."""
        recent = datetime.now(timezone.utc) - timedelta(seconds=30)
        proj = _make_project(
            project_id="healthy",
            last_webhook_received_at=recent,
            repo_url="https://github.com/org/repo",
        )
        orch = _make_orchestrator_with_store([proj])
        with patch(
            "oompah.orchestrator.detect_provider"
        ) as mock_detect:
            result = orch._fetch_all_reviews()
            # Provider should NOT be called for healthy projects
            mock_detect.assert_not_called()
            # Result for the project should be empty
            assert result.get("healthy") == []

    def test_polls_unhealthy_project(self):
        """Unhealthy project (missing timestamp) is polled."""
        proj = _make_project(
            project_id="unhealthy",
            last_webhook_received_at=None,
            repo_url="https://github.com/org/repo",
        )
        mock_provider = MagicMock()
        mock_provider.list_open_reviews.return_value = [
            ReviewRequest(
                id="PR-1",
                title="PR 1",
                url="https://github.com/org/repo/pull/1",
                author="alice",
                state="open",
                source_branch="feat-1",
                target_branch="main",
                created_at="2025-01-01",
                updated_at="2025-01-01",
                ci_status="passed",
                has_conflicts=False,
                needs_rebase=False,
                draft=False,
            )
        ]
        orch = _make_orchestrator_with_store([proj])
        with patch(
            "oompah.orchestrator.detect_provider", return_value=mock_provider
        ):
            result = orch._fetch_all_reviews()
            mock_provider.list_open_reviews.assert_called_once()
            assert len(result.get("unhealthy", [])) == 1

    def test_polls_stale_project(self):
        """Project with old webhook is polled."""
        old = datetime.now(timezone.utc) - timedelta(minutes=5)
        proj = _make_orchestrator_with_store([old])._project_trackers
        stale_proj = _make_project(
            project_id="stale",
            last_webhook_received_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            repo_url="https://github.com/org/repo",
        )
        mock_provider = MagicMock()
        mock_provider.list_open_reviews.return_value = []
        orch = _make_orchestrator_with_store([stale_proj])
        with patch(
            "oompah.orchestrator.detect_provider", return_value=mock_provider
        ):
            result = orch._fetch_all_reviews()
            mock_provider.list_open_reviews.assert_called_once()
            assert result.get("stale") == []

    def test_mixed_healthy_and_unhealthy(self):
        """Only unhealthy projects are polled; healthy ones are skipped."""
        healthy_proj = _make_project(
            project_id="healthy",
            last_webhook_received_at=datetime.now(timezone.utc) - timedelta(seconds=30),
            repo_url="https://github.com/org/healthy",
        )
        unhealthy_proj = _make_project(
            project_id="unhealthy",
            last_webhook_received_at=None,
            repo_url="https://github.com/org/unhealthy",
        )
        mock_provider = MagicMock()
        mock_provider.list_open_reviews.return_value = [
            ReviewRequest(
                id="PR-42",
                title="Huge Feature",
                url="https://github.com/org/unhealthy/pull/42",
                author="alice",
                state="open",
                source_branch="feature-b",
                target_branch="main",
                created_at="2025-01-01",
                updated_at="2025-01-01",
                ci_status="failed",
                has_conflicts=False,
                needs_rebase=False,
                draft=False,
            )
        ]
        orch = _make_orchestrator_with_store([healthy_proj, unhealthy_proj])
        with patch(
            "oompah.orchestrator.detect_provider", return_value=mock_provider
        ):
            result = orch._fetch_all_reviews()
        # Healthy project has no reviews fetched
        assert result.get("healthy") == []
        # Unhealthy project is polled
        assert len(result.get("unhealthy", [])) == 1
        assert result["unhealthy"][0].id == "PR-42"

    def test_empty_projects_list(self):
        """No projects configured returns empty dict."""
        orch = _make_orchestrator_with_store([])
        result = orch._fetch_all_reviews()
        assert result == {}


# ---------------------------------------------------------------------------
# _fetch_all_merged_branches — adaptive skipping
# ---------------------------------------------------------------------------


class TestFetchAllMergedBranchesSkipsHealthy:
    def test_skips_healthy_project(self):
        """Healthy project should not trigger forge API calls."""
        recent = datetime.now(timezone.utc) - timedelta(seconds=45)
        proj = _make_project(
            project_id="healthy",
            last_webhook_received_at=recent,
            repo_url="https://github.com/org/repo",
        )
        orch = _make_orchestrator_with_store([proj])
        with patch(
            "oompah.orchestrator.detect_provider"
        ) as mock_detect:
            result = orch._fetch_all_merged_branches()
            mock_detect.assert_not_called()
            # Healthy project skipped
            assert "feature-a" not in result
            assert result == set()

    def test_polls_unhealthy_project(self):
        """Unhealthy project is polled for merged branches."""
        proj = _make_project(
            project_id="unhealthy",
            last_webhook_received_at=None,
            repo_url="https://github.com/org/repo",
        )
        mock_provider = MagicMock()
        mock_provider.list_merged_branches.return_value = {"feat-y", "feat-z"}
        orch = _make_orchestrator_with_store([proj])
        with patch(
            "oompah.orchestrator.detect_provider", return_value=mock_provider
        ):
            result = orch._fetch_all_merged_branches()
        mock_provider.list_merged_branches.assert_called_once()
        assert result == {"feat-y", "feat-z"}

    def test_aggregates_across_stale_projects(self):
        """Stale project branches are returned as union."""
        proj1 = _make_project(
            project_id="proj-1",
            last_webhook_received_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            repo_url="https://github.com/org/repo1",
        )
        proj2 = _make_project(
            project_id="proj-2",
            last_webhook_received_at=None,  # missing = unhealthy
            repo_url="https://github.com/org/repo2",
        )
        mock_provider1 = MagicMock()
        mock_provider1.list_merged_branches.return_value = {"branch-1"}
        mock_provider2 = MagicMock()
        mock_provider2.list_merged_branches.return_value = {"branch-2"}

        def detect_side_effect(url, access_token=None):
            if "repo1" in url:
                return mock_provider1
            return mock_provider2

        orch = _make_orchestrator_with_store([proj1, proj2])
        with patch(
            "oompah.orchestrator.detect_provider",
            side_effect=detect_side_effect,
        ):
            result = orch._fetch_all_merged_branches()
        assert result == {"branch-1", "branch-2"}

    def test_empty_projects(self):
        """No projects → empty set."""
        orch = _make_orchestrator_with_store([])
        result = orch._fetch_all_merged_branches()
        assert result == set()