"""Tests for _sort_reviews_by_conflict_impact (oompah-zlz_2-vm1p.2).

Least-disruptive-first merge-candidate sorting for the YOLO loop.
"""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from oompah.config import ServiceConfig
from oompah.models import Project
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest
from oompah.conflict_impact_predictor import ConflictImpactResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_project(
    tmp_path: Path,
    project_id: str = "proj-1",
    repo_url: str = "https://github.com/org/repo",
) -> Project:
    """Make a Project with a real local clone path for git-based tests."""
    repo_path = str(tmp_path / "repo")
    os.makedirs(repo_path, exist_ok=True)
    return Project(
        id=project_id,
        name="test-project",
        repo_url=repo_url,
        repo_path=repo_path,
        yolo=True,
    )


def _make_review(
    review_id: int | str,
    source_branch: str,
    draft: bool = False,
) -> ReviewRequest:
    return ReviewRequest(
        id=str(review_id),
        title=f"PR #{review_id}",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="author",
        state="open",
        source_branch=source_branch,
        target_branch="main",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        draft=draft,
        ci_status="passed",
    )


def _make_orchestrator(tmp_path: Path) -> Orchestrator:
    """Build a minimal Orchestrator with no real backends."""
    p1 = patch.object(Orchestrator, "_arm_profile_drift_alert")
    p2 = patch.object(Orchestrator, "_restore_budget_state")
    p1.start()
    p2.start()
    try:
        orch = Orchestrator(
            config=_make_config(),
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )
    finally:
        p1.stop()
        p2.stop()
    return orch


# ---------------------------------------------------------------------------
# Tests for sorting ascending by conflict-impact score
# ---------------------------------------------------------------------------

class TestSortByConflictImpactAscending:
    """Score=0 (no downstream conflicts) sorts before score=2, etc."""

    def test_score_zero_before_score_two(self, tmp_path: Path):
        """PR with no downstream conflicts is attempted before one with conflicts."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor

        project = _make_project(tmp_path)

        def mock_predict(repo_path, target_branch, other_branches):
            if target_branch == "feature-a":
                return MagicMock(score=0)  # no downstream conflicts
            elif target_branch == "feature-b":
                return MagicMock(score=2)  # would conflict with 2 other PRs

        predictor.predict.side_effect = mock_predict

        reviews = [
            _make_review(88, "feature-b"),
            _make_review(77, "feature-a"),
        ]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        # feature-a (score=0) should come before feature-b (score=2)
        assert result[0].source_branch == "feature-a"
        assert result[1].source_branch == "feature-b"

    def test_high_score_last(self, tmp_path: Path):
        """PRs with the highest conflict-impact scores are attempted last."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor

        project = _make_project(tmp_path)

        def mock_predict(repo_path, target_branch, other_branches):
            scores = {"low": 0, "medium": 1, "high": 3}
            return MagicMock(score=scores.get(target_branch, 99))

        predictor.predict.side_effect = mock_predict

        reviews = [
            _make_review(3, "high"),
            _make_review(1, "low"),
            _make_review(2, "medium"),
        ]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        branches = [r.source_branch for r in result]
        assert branches == ["low", "medium", "high"]

    def test_all_score_zero_preserves_tie_order(self, tmp_path: Path):
        """When all scores are 0, tie-breaker is alphabetically by branch name."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor
        predictor.predict.return_value = MagicMock(score=0)

        project = _make_project(tmp_path)

        reviews = [
            _make_review(3, "zulu"),
            _make_review(1, "alpha"),
            _make_review(2, "mike"),
        ]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        branches = [r.source_branch for r in result]
        assert branches == ["alpha", "mike", "zulu"]


# ---------------------------------------------------------------------------
# Tests for graceful degradation
# ---------------------------------------------------------------------------

class TestSortDegradesSafely:
    """Fail-safe: sorting errors never block merge attempts."""

    def test_no_local_repo_returns_original_order(self, tmp_path: Path):
        """When the project has no repo_path, reviews are returned in original order."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor

        project = _make_project(tmp_path)
        project.repo_path = ""  # no local clone path

        reviews = [
            _make_review(2, "feature-b"),
            _make_review(1, "feature-a"),
        ]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        # Original order preserved — no git calls attempted
        assert [r.source_branch for r in result] == ["feature-b", "feature-a"]
        predictor.predict.assert_not_called()

    def test_nonexistent_repo_path_returns_original_order(self, tmp_path: Path):
        """When the repo path does not exist on disk, original order is preserved."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor

        project = _make_project(tmp_path)
        project.repo_path = "/nonexistent/path/that/does/not/exist"

        reviews = [
            _make_review(2, "feature-b"),
            _make_review(1, "feature-a"),
        ]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        assert [r.source_branch for r in result] == ["feature-b", "feature-a"]
        predictor.predict.assert_not_called()

    def test_single_review_not_scored(self, tmp_path: Path):
        """With only one non-draft review, no scoring is performed."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor

        project = _make_project(tmp_path)

        reviews = [_make_review(1, "solo")]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        assert len(result) == 1
        assert result[0].source_branch == "solo"
        predictor.predict.assert_not_called()

    def test_predictor_exception_treated_as_score_zero(self, tmp_path: Path):
        """When the predictor raises, the branch gets score 0 (attempted anyway)."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor

        project = _make_project(tmp_path)

        def mock_predict(repo_path, target_branch, other_branches):
            if target_branch == "failing":
                raise RuntimeError("git merge-tree blew up")
            return MagicMock(score=0)

        predictor.predict.side_effect = mock_predict

        reviews = [
            _make_review(2, "failing"),
            _make_review(1, "clean"),
        ]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        # "clean" score=0, "failing" treated as 0 → tie-breaker: alpha order
        assert [r.source_branch for r in result] == ["clean", "failing"]

    def test_predictor_returns_result_with_error_treated_as_score_zero(
        self, tmp_path: Path,
    ):
        """When the predictor returns a result with an error field, treat it as score 0."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor

        project = _make_project(tmp_path)

        def mock_predict(repo_path, target_branch, other_branches):
            result = ConflictImpactResult(
                target_branch=target_branch,
                score=0,
                total_checked=0,
            )
            if target_branch == "error-branch":
                result.error = "git merge-tree: something went wrong"
                # score stays 0, treated as "no conflicts"
            return result

        predictor.predict.side_effect = mock_predict

        reviews = [
            _make_review(2, "error-branch"),
            _make_review(1, "ok-branch"),
        ]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        # Both treated as score 0 → tie-break by branch name
        assert [r.source_branch for r in result] == ["error-branch", "ok-branch"]


# ---------------------------------------------------------------------------
# Tests for draft/PR property handling
# ---------------------------------------------------------------------------

class TestSortPreservesDraftAndOtherReviewProperties:
    """Draft PRs are excluded from scoring but preserved in output."""

    def test_draft_reviews_excluded_from_scoring(self, tmp_path: Path):
        """Draft PRs should not be passed to the predictor."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor
        predictor.predict.return_value = MagicMock(score=0)

        project = _make_project(tmp_path)

        # Need >=2 non-draft reviews for scoring to fire.
        # One draft + two open = two non-drafts = predictor called for
        # only the open branches.
        reviews = [
            _make_review(1, "open-a", draft=False),
            _make_review(2, "draft-branch", draft=True),
            _make_review(3, "open-b", draft=False),
        ]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        # All 3 returned in output (draft included)
        assert len(result) == 3
        # Predictor called for the two open branches (not the draft)
        called_branches = [c.kwargs["target_branch"] for c in predictor.predict.call_args_list]
        assert "draft-branch" not in called_branches
        assert sorted(called_branches) == ["open-a", "open-b"]

    def test_draft_reviews_included_in_output(self, tmp_path: Path):
        """Draft PRs are preserved in the returned list."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor
        predictor.predict.return_value = MagicMock(score=0)

        project = _make_project(tmp_path)

        reviews = [
            _make_review(1, "open"),
            _make_review(2, "draft", draft=True),
            _make_review(3, "open-2"),
        ]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        # All 3 returned
        assert len(result) == 3
        # Drafts are in original positions relative to the sorted open PRs
        open_branches = [r.source_branch for r in result if not r.draft]
        assert open_branches == ["open", "open-2"]

    def test_reviews_without_source_branch_handled(self, tmp_path: Path):
        """Reviews with empty source_branch are included with score 0."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor
        predictor.predict.return_value = MagicMock(score=0)

        project = _make_project(tmp_path)

        reviews = [
            _make_review(1, "has-branch"),
            _make_review(2, "", draft=False),  # no branch
        ]

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        assert len(result) == 2
        # Both included; empty-branch review gets key (0, "")
        assert [r.source_branch for r in result] == ["has-branch", ""]

    def test_empty_reviews_list_is_noop(self, tmp_path: Path):
        """An empty reviews list is returned as-is."""
        orch = _make_orchestrator(tmp_path)
        predictor = MagicMock()
        orch._conflict_impact_predictor = predictor

        project = _make_project(tmp_path)
        reviews: list[ReviewRequest] = []

        result = orch._sort_reviews_by_conflict_impact(project, reviews)

        assert result == []
        predictor.predict.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for integration with _yolo_review_actions_sync
# ---------------------------------------------------------------------------

class TestYoloReviewActionsSyncIntegration:
    """Verify the sort call fires inside _yolo_review_actions_sync for YOLO projects."""

    def test_yolo_calls_sort_method(self, tmp_path: Path):
        """When yolo=True projects have reviews, _sort_reviews_by_conflict_impact is called."""
        orch = _make_orchestrator(tmp_path)
        orch._conflict_impact_predictor = MagicMock()
        orch._conflict_impact_predictor.predict.return_value = MagicMock(score=0)

        mock_project = _make_project(tmp_path, project_id="proj-yolo")
        mock_project.yolo = True

        reviews = [
            _make_review(2, "b-branch"),
            _make_review(1, "a-branch"),
        ]
        orch._reviews_cache = {"proj-yolo": reviews}
        orch._merged_branches = set()
        orch._merged_branches_dirty = False

        # Wire the project store so the loop iterates.
        mock_store = MagicMock()
        mock_store.list_all.return_value = [mock_project]
        orch.project_store = mock_store

        with patch.object(orch, "_sort_reviews_by_conflict_impact", wraps=orch._sort_reviews_by_conflict_impact) as mock_sort:
            orch._yolo_review_actions_sync()
            mock_sort.assert_called_once_with(mock_project, reviews)

    def test_non_yolo_project_skips_sort(self, tmp_path: Path):
        """YOLO=projects are skipped entirely so no sort call is made."""
        orch = _make_orchestrator(tmp_path)

        # Non-YOLO project — no sort should be called
        mock_project = _make_project(tmp_path, project_id="proj-no-yolo")
        mock_project.yolo = False  # explicitly off

        orch._reviews_cache = {"proj-no-yolo": [_make_review(1, "branch")]}
        orch._merged_branches = set()
        orch._merged_branches_dirty = False

        with patch.object(orch, "_sort_reviews_by_conflict_impact", wraps=orch._sort_reviews_by_conflict_impact) as mock_sort:
            orch._yolo_review_actions_sync()
            mock_sort.assert_not_called()