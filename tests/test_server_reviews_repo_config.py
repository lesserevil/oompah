"""Tests for /api/v1/reviews enrichment with repo_config_error.

Covers oompah-zlz_2-btf.2: when YOLO encounters a repo-configuration
failure (e.g. GitHub auto-merge toggle disabled) the orchestrator
records the error in ``_yolo_repo_config_errors``. The /api/v1/reviews
endpoint must surface that per-PR so the dashboard / per-PR detail
page can display the underlying error message.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def _make_mock_orch(repo_config_errors: dict | None = None) -> MagicMock:
    project = MagicMock()
    project.id = "proj-1"
    project.repo_url = "https://github.com/org/repo"
    project.name = "repo"
    project.access_token = None

    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    # Empty running set so no reviews look agent-active.
    orch.state.running = {}
    orch._yolo_repo_config_errors = repo_config_errors or {}
    return orch


def _make_review_dict(review_id: str = "42") -> dict:
    return [{
        "project_id": "proj-1",
        "project_name": "repo",
        "provider": "github",
        "review": {
            "id": review_id,
            "title": f"PR #{review_id}",
            "url": f"https://github.com/org/repo/pull/{review_id}",
            "source_branch": "feat-branch",
        },
    }]


class TestApiListReviewsRepoConfig:
    def test_review_with_repo_config_error_is_enriched(self, client):
        """A PR tracked in _yolo_repo_config_errors gets repo_config_error
        and repo_config_error_fingerprint fields on the API payload."""
        orch = _make_mock_orch(repo_config_errors={
            ("proj-1", "42"): {
                "msg": "Auto merge is not allowed for this repository",
                "fingerprint": "abc123def456",
                "operation": "enqueue",
            }
        })
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "get_all_open_reviews",
                         return_value=_make_review_dict("42")),
            patch.object(server_module._api_cache, "get", return_value=None),
        ):
            resp = client.get("/api/v1/reviews")

        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert len(payload) == 1
        assert payload[0]["repo_config_error"] == (
            "Auto merge is not allowed for this repository"
        )
        assert payload[0]["repo_config_error_fingerprint"] == "abc123def456"

    def test_review_without_error_has_no_extra_fields(self, client):
        """A PR with no tracked error must NOT have repo_config_error
        keys (so the dashboard can use absence as the empty state)."""
        orch = _make_mock_orch(repo_config_errors={})
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "get_all_open_reviews",
                         return_value=_make_review_dict("42")),
            patch.object(server_module._api_cache, "get", return_value=None),
        ):
            resp = client.get("/api/v1/reviews")

        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert "repo_config_error" not in payload[0]
        assert "repo_config_error_fingerprint" not in payload[0]

    def test_only_matching_pr_is_enriched(self, client):
        """Multiple reviews; only the one whose (project_id, review_id)
        matches an entry in _yolo_repo_config_errors gets the field."""
        reviews = _make_review_dict("42") + _make_review_dict("43")
        orch = _make_mock_orch(repo_config_errors={
            ("proj-1", "43"): {
                "msg": "Auto merge not allowed",
                "fingerprint": "xyz",
                "operation": "enqueue",
            }
        })
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "get_all_open_reviews",
                         return_value=reviews),
            patch.object(server_module._api_cache, "get", return_value=None),
        ):
            resp = client.get("/api/v1/reviews")

        payload = resp.json()
        assert len(payload) == 2
        # PR #42: no error.
        forty_two = next(p for p in payload if p["review"]["id"] == "42")
        assert "repo_config_error" not in forty_two
        # PR #43: enriched.
        forty_three = next(p for p in payload if p["review"]["id"] == "43")
        assert forty_three["repo_config_error"] == "Auto merge not allowed"
