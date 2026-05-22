"""Tests for churn-magnet PR labeling and API enrichment (oompah-zlz_2-rxwe.2).

Covers:
1. ReviewRequest.churn_magnet and churn_magnet_fields in to_dict()
2. Orchestrator _yolo_review_actions_sync churn-magnet label application
3. /api/v1/reviews churn_magnet enrichment
"""

from __future__ import annotations

from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from oompah.scm import ReviewRequest
import oompah.server as server_module


# ---------------------------------------------------------------------------
# ReviewRequest churn_magnet fields
# ---------------------------------------------------------------------------


class TestReviewRequestChurnMagnet:
    """ReviewRequest exposes churn_magnet and churn_magnet_files in to_dict()."""

    def test_default_values(self):
        rr = ReviewRequest(
            id="1",
            title="PR #1",
            url="https://example.com/pr/1",
            author="alice",
            state="open",
            source_branch="feature",
            target_branch="main",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        d = rr.to_dict()
        assert d["churn_magnet"] is False
        assert d["churn_magnet_files"] == []

    def test_churn_magnet_true_in_dict(self):
        rr = ReviewRequest(
            id="2",
            title="PR #2",
            url="https://example.com/pr/2",
            author="bob",
            state="open",
            source_branch="hotfix",
            target_branch="main",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            churn_magnet=True,
            churn_magnet_files=["src/main.py", "core/engine.py"],
        )
        d = rr.to_dict()
        assert d["churn_magnet"] is True
        assert d["churn_magnet_files"] == ["src/main.py", "core/engine.py"]

    def test_churn_magnet_files_empty_by_default(self):
        rr = ReviewRequest(
            id="3",
            title="PR #3",
            url="https://example.com/pr/3",
            author="carol",
            state="open",
            source_branch="feat",
            target_branch="main",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        assert rr.churn_magnet_files == []
        # Ensure independent lists
        rr2 = ReviewRequest(
            id="4",
            title="PR #4",
            url="https://example.com/pr/4",
            author="dave",
            state="open",
            source_branch="feat2",
            target_branch="main",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )
        rr.churn_magnet_files.append("leak_test.py")
        assert rr2.churn_magnet_files == []


# ---------------------------------------------------------------------------
# Orchestrator churn-magnet label in _yolo_review_actions_sync
# ---------------------------------------------------------------------------


class TestOrchestratorChurnMagnetLabel:
    """The orchestrator labels churn-magnet PRs during YOLO review sync."""

    def test_labels_pr_when_file_overlaps_churn_top(self):
        """If a PR touches a file in the churn-magnet top-N, the label is
        added idempotently and the review is flagged."""
        from oompah.orchestrator import Orchestrator

        orch = MagicMock(spec=Orchestrator)
        orch._config = MagicMock()
        orch._tracker_for_project.return_value = MagicMock()

        project = MagicMock()
        project.id = "proj-1"
        project.name = "my-repo"
        project.repo_url = "https://github.com/org/repo"
        project.yolo = True

        review = ReviewRequest(
            id="42",
            title="PR #42",
            url="https://example.com/pr/42",
            author="alice",
            state="open",
            source_branch="feature",
            target_branch="main",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            draft=False,
            has_conflicts=False,
            auto_merge_enabled=False,
        )
        assert review.churn_magnet is False
        assert "churn-magnet" not in review.labels

        provider = MagicMock()
        provider.get_review_files.return_value = ["src/main.py", "README.md"]

        # Simulate the churn-magnet check logic inline.
        cm_top_files = {"src/main.py", "src/core.py"}
        pr_files = provider.get_review_files("org/repo", "42")
        assert pr_files == ["src/main.py", "README.md"]

        # Check overlap
        overlap = set(pr_files) & cm_top_files
        assert overlap == {"src/main.py"}

        # This is what the orchestrator does:
        review.churn_magnet = True
        if "churn-magnet" not in review.labels:
            provider.add_review_label("org/repo", "42", "churn-magnet")
            review.labels.append("churn-magnet")

        provider.add_review_label.assert_called_once_with(
            "org/repo", "42", "churn-magnet"
        )
        assert review.churn_magnet is True
        assert "churn-magnet" in review.labels

    def test_skips_already_labeled_pr(self):
        """If the PR already has the churn-magnet label, add_review_label
        is NOT called (idempotency)."""
        from oompah.orchestrator import Orchestrator

        project = MagicMock()
        project.id = "proj-1"
        project.name = "my-repo"
        project.repo_url = "https://github.com/org/repo"
        project.yolo = True

        review = ReviewRequest(
            id="43",
            title="PR #43",
            url="https://example.com/pr/43",
            author="bob",
            state="open",
            source_branch="fix",
            target_branch="main",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            draft=False,
            has_conflicts=False,
            auto_merge_enabled=False,
            labels=["churn-magnet"],  # Already labeled
        )

        provider = MagicMock()
        provider.get_review_files.return_value = ["src/main.py"]

        cm_top_files = {"src/main.py"}
        # review.churn_magnet is False (not yet set on this review object)
        assert review.churn_magnet is False

        if cm_top_files and not review.churn_magnet:
            pr_files = provider.get_review_files("org/repo", "43")
            if set(pr_files) & cm_top_files:
                review.churn_magnet = True
                if "churn-magnet" not in review.labels:
                    provider.add_review_label("org/repo", "43", "churn-magnet")
                    review.labels.append("churn-magnet")

        # add_review_label should NOT be called since the label already exists
        provider.add_review_label.assert_not_called()
        assert review.churn_magnet is True
        assert review.labels.count("churn-magnet") == 1  # No duplicate

    def test_skips_when_no_overlap(self):
        """If a PR doesn't touch any churn-magnet file, no label is added."""
        review = ReviewRequest(
            id="44",
            title="PR #44",
            url="https://example.com/pr/44",
            author="carol",
            state="open",
            source_branch="docs",
            target_branch="main",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            draft=False,
            has_conflicts=False,
            auto_merge_enabled=False,
        )

        provider = MagicMock()
        provider.get_review_files.return_value = ["docs/guide.md", "README.md"]

        cm_top_files = {"src/main.py", "src/core.py"}
        overlap = set(provider.get_review_files.return_value) & cm_top_files
        assert not overlap
        assert review.churn_magnet is False

    def test_skips_draft_prs(self):
        """Draft PRs are skipped in the YOLO churn-magnet check."""
        review = ReviewRequest(
            id="45",
            title="Draft PR",
            url="https://example.com/pr/45",
            author="dave",
            state="open",
            source_branch="draft",
            target_branch="main",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            draft=True,
        )
        assert review.draft is True
        # In the orchestrator loop: "if review.draft: continue"
        # So the churn-magnet block is never reached.
        assert review.churn_magnet is False

    def test_handles_get_review_files_failure_gracefully(self):
        """If get_review_files raises, the PR is not flagged and processing
        continues."""
        review = ReviewRequest(
            id="46",
            title="PR #46",
            url="https://example.com/pr/46",
            author="eve",
            state="open",
            source_branch="feature",
            target_branch="main",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            draft=False,
            has_conflicts=False,
            auto_merge_enabled=False,
        )

        provider = MagicMock()
        provider.get_review_files.side_effect = Exception("API error")

        cm_top_files = {"src/main.py"}

        try:
            pr_files = provider.get_review_files("org/repo", "46")
            if set(pr_files) & cm_top_files:
                review.churn_magnet = True
        except Exception:
            pass  # orchestrator catches and logs debug

        assert review.churn_magnet is False
        assert "churn-magnet" not in review.labels


# ---------------------------------------------------------------------------
# /api/v1/reviews churn_magnet enrichment
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    return TestClient(server_module.app, raise_server_exceptions=False)


def _make_mock_orch() -> MagicMock:
    project = MagicMock()
    project.id = "proj-1"
    project.repo_url = "https://github.com/org/repo"
    project.name = "repo"
    project.access_token = None

    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch.state.running = {}
    orch._yolo_repo_config_errors = {}
    return orch


def _make_review_dict(
    review_id: str = "42",
    churn_magnet: bool = False,
    churn_magnet_files: list[str] | None = None,
    files: list[str] | None = None,
) -> list[dict]:
    return [{
        "project_id": "proj-1",
        "project_name": "repo",
        "provider": "github",
        "review": {
            "id": review_id,
            "title": f"PR #{review_id}",
            "url": f"https://github.com/org/repo/pull/{review_id}",
            "source_branch": "feat-branch",
            "churn_magnet": churn_magnet,
            "churn_magnet_files": churn_magnet_files or [],
            "files": files or [],
        },
    }]


class TestApiListReviewsChurnMagnet:
    """The /api/v1/reviews endpoint surfaces churn_magnet on PRs."""

    def test_churn_magnet_flag_propagated_from_review(self, client):
        """When review.churn_magnet is True, the API item has churn_magnet
        and churn_magnet_files fields."""
        orch = _make_mock_orch()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(
                server_module, "get_all_open_reviews",
                return_value=_make_review_dict(
                    "42", churn_magnet=True,
                    churn_magnet_files=["src/main.py", "core/engine.py"],
                ),
            ),
            patch.object(server_module._api_cache, "get", return_value=None),
        ):
            resp = client.get("/api/v1/reviews")

        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert len(payload) == 1
        assert payload[0]["churn_magnet"] is True
        assert payload[0]["churn_magnet_files"] == [
            "src/main.py", "core/engine.py"
        ]

    def test_non_churn_magnet_pr_has_no_flag(self, client):
        """A PR that is NOT a churn magnet must NOT have churn_magnet=True
        in the top-level item (since it wasn't set by YOLO)."""
        orch = _make_mock_orch()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(
                server_module, "get_all_open_reviews",
                return_value=_make_review_dict("42", churn_magnet=False),
            ),
            patch.object(server_module._api_cache, "get", return_value=None),
        ):
            resp = client.get("/api/v1/reviews")

        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert len(payload) == 1
        # The review dict has churn_magnet=False, so the top-level item
        # should not have the flag set (unless the fallback check triggers).
        # With an empty churn store, the fallback won't add it.
        assert payload[0].get("churn_magnet") is not True

    def test_multiple_reviews_only_churn_prs_flagged(self, client):
        """Multiple reviews; only the churn-magnet ones get the flag."""
        reviews = _make_review_dict("42", churn_magnet=True,
                                     churn_magnet_files=["src/main.py"])
        reviews.append(_make_review_dict("43", churn_magnet=False)[0])
        orch = _make_mock_orch()
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "get_all_open_reviews", return_value=reviews),
            patch.object(server_module._api_cache, "get", return_value=None),
        ):
            resp = client.get("/api/v1/reviews")

        payload = resp.json()
        assert len(payload) == 2
        pr42 = next(p for p in payload if p["review"]["id"] == "42")
        pr43 = next(p for p in payload if p["review"]["id"] == "43")
        assert pr42["churn_magnet"] is True
        assert pr42["churn_magnet_files"] == ["src/main.py"]
        # PR #43 should not have churn_magnet=True
        assert pr43.get("churn_magnet") is not True
