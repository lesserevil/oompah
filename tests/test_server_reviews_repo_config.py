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
from oompah.scm import ReviewRequest
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
    project.yolo = True

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


def _make_fetch_result(
    reviews: list[dict],
    *,
    typed_reviews: list[ReviewRequest] | None = None,
    successful: bool = True,
) -> tuple[list[dict], dict[str, list[ReviewRequest]], set[str]]:
    successful_ids = {"proj-1"} if successful else set()
    return reviews, {"proj-1": typed_reviews or []}, successful_ids


class _ReviewCacheOrch:
    def __init__(self, project: MagicMock, reviews: list[ReviewRequest]):
        self.project_store = MagicMock()
        self.project_store.list_all.return_value = [project]
        self.state = MagicMock()
        self.state.running = {}
        self._yolo_repo_config_errors = {}
        self._reviews_cache = {project.id: list(reviews)}
        self._unmerged_review_branches = {r.source_branch for r in reviews}
        self._last_emitted_reviews_summary = self._reviews_summary()
        self.notify_count = 0

    def _reviews_summary(self) -> dict[str, int]:
        yolo_ids = {
            p.id for p in self.project_store.list_all() if getattr(p, "yolo", False)
        }
        total = 0
        yolo_pending = 0
        queued = 0
        conflicts = 0
        ci_failures = 0
        for project_id, reviews in self._reviews_cache.items():
            for review in reviews:
                total += 1
                if project_id in yolo_ids:
                    yolo_pending += 1
                    if review.auto_merge_enabled:
                        queued += 1
                    continue
                if review.has_conflicts:
                    conflicts += 1
                elif review.ci_status == "failed":
                    ci_failures += 1
        return {
            "total": total,
            "yolo_pending": yolo_pending,
            "queued": queued,
            "conflicts": conflicts,
            "ci_failures": ci_failures,
            "needs_repo_config": 0,
            "unavailable_runners": 0,
            "needs_attention": conflicts + ci_failures,
        }

    def _notify_state_only(self) -> None:
        self.notify_count += 1


def _make_project(yolo: bool = True) -> MagicMock:
    project = MagicMock()
    project.id = "proj-1"
    project.repo_url = "https://github.com/org/repo"
    project.name = "repo"
    project.access_token = None
    project.yolo = yolo
    return project


def _make_review_request(review_id: str = "42") -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title=f"PR #{review_id}",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="alice",
        state="open",
        source_branch="feat-branch",
        target_branch="main",
        created_at="2026-06-02T16:00:00Z",
        updated_at="2026-06-02T16:00:00Z",
        ci_status="passed",
        auto_merge_enabled=False,
    )


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
            patch.object(
                server_module, "_fetch_open_reviews_for_api",
                return_value=_make_fetch_result(_make_review_dict("42")),
            ),
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
            patch.object(
                server_module, "_fetch_open_reviews_for_api",
                return_value=_make_fetch_result(_make_review_dict("42")),
            ),
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
            patch.object(
                server_module, "_fetch_open_reviews_for_api",
                return_value=_make_fetch_result(reviews),
            ),
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


class TestApiListReviewsSyncsOrchestratorCache:
    def test_empty_reviews_payload_clears_stale_reviews_summary(self, client):
        project = _make_project(yolo=True)
        orch = _ReviewCacheOrch(project, [_make_review_request("42")])

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(
                server_module, "_fetch_open_reviews_for_api",
                return_value=_make_fetch_result([], typed_reviews=[]),
            ),
            patch.object(server_module._api_cache, "get", return_value=None),
            patch.object(server_module._api_cache, "set"),
        ):
            resp = client.get("/api/v1/reviews")

        assert resp.status_code == 200, resp.text
        assert resp.json() == []
        assert orch._reviews_cache == {"proj-1": []}
        assert orch._unmerged_review_branches == set()
        assert orch._reviews_summary()["total"] == 0
        assert orch._last_emitted_reviews_summary["total"] == 0
        assert orch.notify_count == 1

    def test_reviews_payload_rebuilds_cache_as_review_requests(self, client):
        project = _make_project(yolo=True)
        orch = _ReviewCacheOrch(project, [])

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(
                server_module, "_fetch_open_reviews_for_api",
                return_value=_make_fetch_result(
                    _make_review_dict("42"),
                    typed_reviews=[_make_review_request("42")],
                ),
            ),
            patch.object(server_module._api_cache, "get", return_value=None),
            patch.object(server_module._api_cache, "set"),
        ):
            resp = client.get("/api/v1/reviews")

        assert resp.status_code == 200, resp.text
        cached_reviews = orch._reviews_cache["proj-1"]
        assert len(cached_reviews) == 1
        assert isinstance(cached_reviews[0], ReviewRequest)
        assert cached_reviews[0].id == "42"
        assert cached_reviews[0].source_branch == "feat-branch"
        assert orch._unmerged_review_branches == {"feat-branch"}
        assert orch._reviews_summary()["total"] == 1
        assert orch._reviews_summary()["yolo_pending"] == 1

    def test_failed_project_fetch_does_not_clear_existing_cache(self, client):
        project = _make_project(yolo=True)
        stale_review = _make_review_request("42")
        orch = _ReviewCacheOrch(project, [stale_review])

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(
                server_module, "_fetch_open_reviews_for_api",
                return_value=_make_fetch_result([], typed_reviews=[], successful=False),
            ),
            patch.object(server_module._api_cache, "get", return_value=None),
            patch.object(server_module._api_cache, "set"),
        ):
            resp = client.get("/api/v1/reviews")

        assert resp.status_code == 200, resp.text
        assert resp.json() == []
        assert orch._reviews_cache == {"proj-1": [stale_review]}
        assert orch._unmerged_review_branches == {"feat-branch"}
        assert orch._reviews_summary()["total"] == 1
        assert orch.notify_count == 0
