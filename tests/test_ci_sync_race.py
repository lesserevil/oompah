"""Regression coverage for OOMPAH-449's post-synchronize CI race.

PR #555 received a new head at T+0. GitHub returned successful but empty
status and check-run responses at T+3, registered the workflow at T+4, and
started jobs at T+6. Oompah merged at T+7 even though CI did not finish until
roughly T+382.

These tests exercise the real GitHub review-listing path and the YOLO gate.
They deliberately create a new GitHubProvider on every observation because
the orchestrator does that on every tick.
"""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest

from oompah.scm import CIStatus, GitHubProvider, ReviewRequest


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._payload


class FakeGitHubReviews:
    """Mutable GitHub API fixture for one PR and multiple head SHAs."""

    repo = "org/repo"

    def __init__(self):
        self.pr: dict | None = {
            "number": 555,
            "title": "OOMPAH-447",
            "html_url": "https://github.com/org/repo/pull/555",
            "user": {"login": "oompah"},
            "head": {"ref": "OOMPAH-447", "sha": "old-sha"},
            "base": {"ref": "main"},
            "created_at": "2026-07-26T04:20:00Z",
            "updated_at": "2026-07-26T04:26:37Z",
            "body": "",
            "labels": [],
            "requested_reviewers": [],
            "draft": False,
            "additions": 1,
            "deletions": 0,
            "auto_merge": None,
            "mergeable": True,
            "mergeable_state": "clean",
        }
        self.checks_by_sha: dict[str, list[dict]] = {}
        self.requested_ci_shas: list[str] = []

    def provider(self) -> GitHubProvider:
        provider = GitHubProvider(access_token="token")
        provider._api = self.api
        provider._graphql = lambda query, variables=None: FakeResponse(
            {"data": {"repository": {"mergeQueue": None}}}
        )
        return provider

    def api(self, method, path, **kwargs):
        if path == f"/repos/{self.repo}/pulls":
            return FakeResponse([deepcopy(self.pr)] if self.pr else [])
        if path.endswith("/status") and "/commits/" in path:
            return FakeResponse({"state": "pending", "total_count": 0})
        if path.endswith("/check-runs"):
            sha = path.split("/commits/", 1)[1].split("/", 1)[0]
            self.requested_ci_shas.append(sha)
            return FakeResponse(
                {"check_runs": deepcopy(self.checks_by_sha.get(sha, []))}
            )
        if path == f"/repos/{self.repo}/pulls/555" and self.pr:
            return FakeResponse(deepcopy(self.pr))
        raise AssertionError(f"unexpected GitHub API call: {method} {path}")

    def set_head(self, sha: str, checks: list[dict]) -> None:
        assert self.pr is not None
        self.pr["head"]["sha"] = sha
        self.pr["updated_at"] = "2026-07-26T04:26:37Z"
        self.checks_by_sha[sha] = checks

    def reviews_at(self, monotonic_time: float) -> list[ReviewRequest]:
        with patch("oompah.scm.time.monotonic", return_value=monotonic_time):
            return self.provider().list_open_reviews(self.repo)


@pytest.fixture(autouse=True)
def isolate_github_class_caches():
    original_grace = GitHubProvider._CI_REGISTRATION_GRACE_SECONDS
    GitHubProvider._CI_REGISTRATION_GRACE_SECONDS = 60.0
    with GitHubProvider._ci_head_observations_lock:
        GitHubProvider._ci_head_observations.clear()
    with GitHubProvider._pr_detail_cache_lock:
        GitHubProvider._pr_detail_cache.clear()
    yield
    GitHubProvider._CI_REGISTRATION_GRACE_SECONDS = original_grace
    with GitHubProvider._ci_head_observations_lock:
        GitHubProvider._ci_head_observations.clear()
    with GitHubProvider._pr_detail_cache_lock:
        GitHubProvider._pr_detail_cache.clear()


def _make_project(merge_queue_enabled: bool = False):
    project = MagicMock()
    project.id = "proj-1"
    project.name = "test-project"
    project.repo_url = "https://github.com/org/repo"
    project.yolo = True
    project.default_branch = "main"
    project.merge_queue_enabled = merge_queue_enabled
    project.churn_magnet_gate_enabled = False
    project.access_token = None
    return project


def _run_yolo(tmp_path, review: ReviewRequest, *, merge_queue_enabled=False):
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator
    from oompah.roles import RoleStore

    project = _make_project(merge_queue_enabled)
    project_store = MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.return_value = project
    project_store.epic_branch_name.side_effect = lambda issue_id: f"epic-{issue_id}"
    orchestrator = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=RoleStore(path=str(tmp_path / "roles.json")),
        state_path=str(tmp_path / "state.json"),
    )
    orchestrator._reviews_cache = {project.id: [review]}
    orchestrator._yolo_epic_strategy_block_reason = MagicMock(return_value=None)
    orchestrator._tracker_for_project = MagicMock(return_value=MagicMock())

    provider = MagicMock()
    provider.merge_review.return_value = (True, "merged")
    provider.enable_auto_merge.return_value = (True, "queued")
    with (
        patch("oompah.orchestrator.detect_provider", return_value=provider),
        patch("oompah.orchestrator.extract_repo_slug", return_value="org/repo"),
    ):
        orchestrator._yolo_review_actions_sync()
    return provider


def _completed(conclusion: str) -> list[dict]:
    return [{"status": "completed", "conclusion": conclusion}]


@pytest.mark.parametrize("merge_queue_enabled", [False, True])
def test_pr555_sequence_blocks_empty_window_then_delivers(
    tmp_path,
    merge_queue_enabled,
):
    """Old failed SHA, synchronize, empty, pending, passed ordering."""
    forge = FakeGitHubReviews()

    forge.set_head("old-sha", _completed("failure"))
    old_review = forge.reviews_at(0.0)[0]
    assert old_review.ci_status == CIStatus.FAILED

    # T+3: synchronize changed the authoritative head, but GitHub has not
    # registered the replacement workflow yet.
    forge.set_head("ed815c908", [])
    empty_review = forge.reviews_at(3.0)[0]
    assert empty_review.ci_status == CIStatus.PENDING
    empty_gate = _run_yolo(
        tmp_path,
        empty_review,
        merge_queue_enabled=merge_queue_enabled,
    )
    empty_gate.merge_review.assert_not_called()
    empty_gate.enable_auto_merge.assert_not_called()

    # T+4 through T+6: checks now exist, but are not complete.
    forge.checks_by_sha["ed815c908"] = [
        {"status": "queued", "conclusion": None},
        {"status": "in_progress", "conclusion": None},
    ]
    pending_review = forge.reviews_at(6.0)[0]
    assert pending_review.ci_status == CIStatus.PENDING
    pending_gate = _run_yolo(
        tmp_path,
        pending_review,
        merge_queue_enabled=merge_queue_enabled,
    )
    pending_gate.merge_review.assert_not_called()
    pending_gate.enable_auto_merge.assert_not_called()

    # T+382: the replacement matrix has passed for the current head.
    forge.checks_by_sha["ed815c908"] = _completed("success")
    passed_review = forge.reviews_at(382.0)[0]
    assert passed_review.ci_status == CIStatus.PASSED
    passed_gate = _run_yolo(
        tmp_path,
        passed_review,
        merge_queue_enabled=merge_queue_enabled,
    )
    if merge_queue_enabled:
        passed_gate.enable_auto_merge.assert_called_once_with("org/repo", "555")
        passed_gate.merge_review.assert_not_called()
    else:
        passed_gate.merge_review.assert_called_once_with("org/repo", "555")
        passed_gate.enable_auto_merge.assert_not_called()

    assert forge.requested_ci_shas == [
        "old-sha",
        "ed815c908",
        "ed815c908",
        "ed815c908",
    ]


def test_true_no_ci_head_becomes_mergeable_after_bounded_observation(tmp_path):
    """A check-free SHA is positively classified no-CI after the grace."""
    forge = FakeGitHubReviews()
    forge.set_head("no-ci-sha", [])

    assert forge.reviews_at(100.0)[0].ci_status == CIStatus.PENDING
    assert forge.reviews_at(159.9)[0].ci_status == CIStatus.PENDING
    no_ci_review = forge.reviews_at(160.0)[0]
    assert no_ci_review.ci_status == CIStatus.PASSED

    provider = _run_yolo(tmp_path, no_ci_review)
    provider.merge_review.assert_called_once_with("org/repo", "555")


def test_synchronize_invalidates_prior_head_no_ci_verdict():
    """A new head cannot inherit the previous SHA's elapsed grace."""
    forge = FakeGitHubReviews()
    forge.set_head("old-no-ci", [])

    assert forge.reviews_at(0.0)[0].ci_status == CIStatus.PENDING
    assert forge.reviews_at(60.0)[0].ci_status == CIStatus.PASSED

    forge.set_head("new-no-ci", [])
    new_review = forge.reviews_at(61.0)[0]
    assert new_review.ci_status == CIStatus.PENDING
    with GitHubProvider._ci_head_observations_lock:
        assert GitHubProvider._ci_head_observations[
            ("org/repo", "555")
        ][0] == "new-no-ci"


def test_observation_survives_provider_recreation():
    """Provider-per-tick construction cannot reset the registration guard."""
    forge = FakeGitHubReviews()
    forge.set_head("same-sha", [])

    first_provider_review = forge.reviews_at(10.0)[0]
    second_provider_review = forge.reviews_at(69.0)[0]
    classified_review = forge.reviews_at(70.0)[0]

    assert first_provider_review.ci_status == CIStatus.PENDING
    assert second_provider_review.ci_status == CIStatus.PENDING
    assert classified_review.ci_status == CIStatus.PASSED


def test_closed_review_prunes_ci_head_observation():
    forge = FakeGitHubReviews()
    forge.set_head("open-sha", [])
    forge.reviews_at(0.0)
    assert ("org/repo", "555") in GitHubProvider._ci_head_observations

    forge.pr = None
    assert forge.reviews_at(1.0) == []
    assert ("org/repo", "555") not in GitHubProvider._ci_head_observations
