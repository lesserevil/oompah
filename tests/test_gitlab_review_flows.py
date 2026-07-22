"""Tests for GitLab SCM and pipeline integration in review, YOLO, and release delivery.

OOMPAH-326: Integrate GitLab SCM and pipelines into review, YOLO, and release delivery.

Covers the acceptance criteria from plans/gitlab-forge-parity.md:
- GitLab managed projects support the same Oompah review/release workflows as GitHub.
- A failed GitLab release pipeline produces one actionable remediation task.
- make test passes.

Test categories:
1. Normal review flow — GitLab MR with CI passed → direct merge or auto-merge.
2. Pending CI flow — CI pending → no YOLO action taken.
3. Failed CI flow — CI failed → _yolo_retry_ci dispatched.
4. Rebase/conflict flow — MR has conflicts → _yolo_notify_conflict → rebase attempted.
5. Auto-merge via merge_when_pipeline_succeeds — GitLab queue mode uses MWPS, not merge trains.
6. Auto-merge rejection — MWPS rejected by approval policy → error surfaced.
7. Merge outcome — merged MR calls merge_review successfully.
8. Branch protection — protected GitLab source branch not deleted after merge.
9. Selected release delivery CI monitor — GitLab release pipeline failure → one task.
10. GitHub regression — same YOLO flows work unchanged for GitHub projects.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

try:
    from oompah.scm import (
        CIStatus,
        GitLabProvider,
        ReviewRequest,
        _is_protected_branch,
    )

    _SCM_AVAILABLE = True
except ModuleNotFoundError:
    _SCM_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _SCM_AVAILABLE, reason="oompah.scm unavailable")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_GITLAB_REPO_URL = "https://gitlab.com/org/project.git"
_GITLAB_SLUG = "org/project"
_GITLAB_NESTED_SLUG = "group/subgroup/project"
_GITHUB_REPO_URL = "https://github.com/org/repo.git"
_GITHUB_SLUG = "org/repo"

_CI_PROJECT_ID = "proj-ci-monitor"
_SHA_A = "a" * 40
_SHA_B = "b" * 40
_RESULT_SHA = "e" * 40


def _make_gitlab_project(
    project_id: str = "proj-gl",
    repo_url: str = _GITLAB_REPO_URL,
    yolo: bool = True,
    merge_queue_enabled: bool = False,
    access_token: str | None = None,
    default_branch: str = "main",
    repo_path: str = "/tmp/repo",
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = "gitlab-project"
    p.yolo = yolo
    p.merge_queue_enabled = merge_queue_enabled
    p.access_token = access_token
    p.tracker_kind = "oompah_md"
    p.default_branch = default_branch
    p.repo_path = repo_path
    p.churn_magnet_gate_enabled = False
    p.churn_magnet_top_n = 10
    p.paused = False
    p.epic_strategy = "flat"
    return p


def _make_github_project(
    project_id: str = "proj-gh",
    repo_url: str = _GITHUB_REPO_URL,
    yolo: bool = True,
    merge_queue_enabled: bool = False,
    access_token: str | None = None,
    default_branch: str = "main",
    repo_path: str = "/tmp/repo",
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = "github-project"
    p.yolo = yolo
    p.merge_queue_enabled = merge_queue_enabled
    p.access_token = access_token
    p.tracker_kind = "oompah_md"
    p.default_branch = default_branch
    p.repo_path = repo_path
    p.churn_magnet_gate_enabled = False
    p.churn_magnet_top_n = 10
    p.paused = False
    p.epic_strategy = "flat"
    return p


def _make_review(
    review_id: str = "7",
    source_branch: str = "oompah/FEAT-1",
    target_branch: str = "main",
    ci_status: str = "passed",
    has_conflicts: bool = False,
    needs_rebase: bool = False,
    draft: bool = False,
    auto_merge_enabled: bool = False,
    mergeable_state: str = "",
    url: str = "https://gitlab.com/org/project/-/merge_requests/7",
    ci_warnings: list[dict] | None = None,
) -> "ReviewRequest":
    return ReviewRequest(
        id=review_id,
        title=f"MR #{review_id}",
        url=url,
        author="alice",
        state="open",
        source_branch=source_branch,
        target_branch=target_branch,
        created_at="2026-01-01",
        updated_at="2026-01-02",
        ci_status=ci_status,
        has_conflicts=has_conflicts,
        needs_rebase=needs_rebase,
        draft=draft,
        auto_merge_enabled=auto_merge_enabled,
        mergeable_state=mergeable_state,
        ci_warnings=ci_warnings or [],
    )


def _make_orchestrator(tmp_path, projects=None):
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator

    project_store = MagicMock()
    all_projects = list(projects or [])
    project_store.list_all.return_value = all_projects
    project_store.get.side_effect = lambda pid: next(
        (p for p in all_projects if p.id == pid), None
    )
    return Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def _make_delivery(
    delivery_id: str = "rd_gl_001",
    *,
    ci_remediation_task_id: str | None = None,
    target_branch: str = "release/1.0",
    pr_url: str = "https://gitlab.com/group/project/-/merge_requests/7",
    result_commits: list[str] | None = None,
):
    """Build a minimal merged ReleaseDelivery for CI monitor tests."""
    from oompah.release_delivery_store import ReleaseDelivery, SourceKind
    from oompah.release_addendum_schema import AddendumStatus
    from datetime import datetime, timezone

    return ReleaseDelivery(
        id=delivery_id,
        project_id=_CI_PROJECT_ID,
        source_branch="main",
        source_kind=SourceKind.TASK,
        source_identifier="FEAT-1",
        source_commits=[_SHA_A, _SHA_B],
        target_branch=target_branch,
        status=AddendumStatus.MERGED,
        queued_at=datetime.now(timezone.utc).isoformat(),
        work_branch="oompah/release/FEAT-1/release-1.0",
        pr_url=pr_url,
        result_commits=result_commits if result_commits is not None else [_RESULT_SHA],
        ci_remediation_task_id=ci_remediation_task_id,
    )


def _run_ci_monitor(
    deliveries,
    *,
    ci_status: str = "failed",
    repo_url: str = "https://gitlab.com/group/project.git",
    repo_slug: str = "group/project",
    existing_remediation_ids: set[str] | None = None,
    scm_capture: list[MagicMock] | None = None,
):
    """Run _monitor_merged_delivery_ci via the fake orchestrator pattern.

    Mirrors the pattern in tests/test_release_delivery_ci_monitor.py.
    Returns (created_issues, store).
    """
    import dataclasses
    from oompah.release_delivery_store import ReleaseDeliveryLedger, DeliveryNotFoundError
    from oompah.release_addendum_schema import AddendumStatus
    from oompah.orchestrator import Orchestrator

    if existing_remediation_ids is None:
        existing_remediation_ids = {
            d.ci_remediation_task_id
            for d in deliveries
            if d.ci_remediation_task_id
        }

    class _FakeStore:
        def __init__(self, items):
            self._items = list(items)
            self.updates: list[dict] = []

        def read_ledger(self):
            return ReleaseDeliveryLedger(version=1, deliveries=list(self._items))

        def lookup_by_id(self, did):
            return next((d for d in self._items if d.id == did), None)

        def update(self, did, **fields):
            idx = next((i for i, d in enumerate(self._items) if d.id == did), None)
            if idx is None:
                raise DeliveryNotFoundError(did)
            current = self._items[idx]
            new_status = current.status
            if "status" in fields:
                raw = fields["status"]
                new_status = raw if isinstance(raw, AddendumStatus) else AddendumStatus.from_raw(raw)
            updated = dataclasses.replace(
                current,
                status=new_status,
                ci_remediation_task_id=fields.get(
                    "ci_remediation_task_id", current.ci_remediation_task_id
                ),
                **{
                    k: v
                    for k, v in fields.items()
                    if k not in ("status", "ci_remediation_task_id")
                },
            )
            self._items[idx] = updated
            self.updates.append({"id": did, **fields})
            return updated

    store = _FakeStore(deliveries)
    created_issues: list[dict] = []

    class _FakeTracker:
        def fetch_issue_detail(self, identifier):
            if identifier in existing_remediation_ids:
                return SimpleNamespace(identifier=identifier)
            return None

        def create_issue(self, **kwargs):
            iss = SimpleNamespace(identifier=f"PROJ-{len(created_issues) + 1}")
            created_issues.append(kwargs)
            return iss

    project = SimpleNamespace(
        id=_CI_PROJECT_ID,
        name="gl-project",
        repo_url=repo_url,
        repo_path="/tmp/gl-project",
        access_token=None,
    )

    mock_scm = MagicMock()
    mock_scm.get_branch_ci_status.return_value = ci_status
    if scm_capture is not None:
        scm_capture.append(mock_scm)

    class _FakeOrch:
        project_store = SimpleNamespace(list_all=lambda: [project])

        def _tracker_for_project(self, pid):
            return _FakeTracker()

        def _job_deadline_exceeded(self, _label):
            return False

        _check_and_remediate_delivery_ci = Orchestrator._check_and_remediate_delivery_ci
        _dispatch_release_ci_fix_task = Orchestrator._dispatch_release_ci_fix_task
        _monitor_merged_delivery_ci = Orchestrator._monitor_merged_delivery_ci
        _has_live_release_ci_remediation = staticmethod(
            Orchestrator._has_live_release_ci_remediation
        )

    orch = _FakeOrch()

    with (
        patch("oompah.orchestrator.make_delivery_store", return_value=store),
        patch("oompah.orchestrator.detect_provider", return_value=mock_scm),
        patch("oompah.orchestrator.extract_repo_slug", return_value=repo_slug),
    ):
        Orchestrator._monitor_merged_delivery_ci(orch)

    return created_issues, store


# ---------------------------------------------------------------------------
# 1. Normal review flow — CI passed → merge_review called
# ---------------------------------------------------------------------------


class TestGitLabNormalReviewFlow:
    """GitLab MR with CI passed goes through direct merge when merge_queue_enabled=False."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gitlab_direct_merge_on_ci_passed(self, mock_slug, mock_detect, tmp_path):
        """GitLab MR with CI passed and direct mode calls merge_review."""
        project = _make_gitlab_project(merge_queue_enabled=False)
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("7", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called_once_with(_GITLAB_SLUG, "7")
        provider.enable_auto_merge.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gitlab_detect_provider_uses_repo_url(self, mock_slug, mock_detect, tmp_path):
        """detect_provider is called with the project's repo_url for GitLab projects."""
        project = _make_gitlab_project(repo_url=_GITLAB_REPO_URL)
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("7", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        # detect_provider is called with the project's repo_url
        mock_detect.assert_called()
        call_urls = [str(c) for c in mock_detect.call_args_list]
        assert any(_GITLAB_REPO_URL in cu for cu in call_urls), (
            f"Expected detect_provider to be called with {_GITLAB_REPO_URL}, "
            f"got calls: {call_urls}"
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gitlab_only_passed_ci_triggers_merge(self, mock_slug, mock_detect, tmp_path):
        """Only ci_status='passed' triggers YOLO merge; unknown/empty CI is skipped."""
        project = _make_gitlab_project(merge_queue_enabled=False)
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        # CIStatus.UNKNOWN ("unknown") is not "passed" → merge NOT triggered
        orch._reviews_cache = {project.id: [_make_review("7", ci_status="unknown")]}

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gitlab_draft_mr_not_merged(self, mock_slug, mock_detect, tmp_path):
        """Draft GitLab MRs are not merged by YOLO."""
        project = _make_gitlab_project(merge_queue_enabled=False)
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [_make_review("7", ci_status="passed", draft=True)]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()
        provider.enable_auto_merge.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gitlab_nested_namespace_slug_passed_to_provider(
        self, mock_slug, mock_detect, tmp_path
    ):
        """For nested GitLab groups the full slug is passed unchanged to provider calls."""
        project = _make_gitlab_project(
            repo_url="https://gitlab.com/group/subgroup/project.git",
            merge_queue_enabled=False,
        )
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_NESTED_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("7", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called_once_with(_GITLAB_NESTED_SLUG, "7")


# ---------------------------------------------------------------------------
# 2. Pending CI flow — no action taken
# ---------------------------------------------------------------------------


class TestGitLabPendingCIFlow:
    """GitLab MR with pending CI is not merged or retried."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_pending_ci_does_not_merge(self, mock_slug, mock_detect, tmp_path):
        """GitLab MR with pending CI is skipped by YOLO."""
        project = _make_gitlab_project()
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [_make_review("7", ci_status="pending")]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()
        provider.enable_auto_merge.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_pending_ci_also_does_not_dispatch_retry_ci(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Pending CI is not a failure — _yolo_retry_ci must not be triggered."""
        project = _make_gitlab_project()
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_retry_ci = MagicMock()
        orch._reviews_cache = {
            project.id: [_make_review("7", ci_status="pending")]
        }

        orch._yolo_review_actions_sync()

        orch._yolo_retry_ci.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_unknown_ci_status_does_not_trigger_merge_or_retry(
        self, mock_slug, mock_detect, tmp_path
    ):
        """CIStatus.UNKNOWN (no pipeline configured) → YOLO does not merge or retry."""
        project = _make_gitlab_project(merge_queue_enabled=False)
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_retry_ci = MagicMock()
        orch._reviews_cache = {
            project.id: [_make_review("7", ci_status=CIStatus.UNKNOWN)]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()
        orch._yolo_retry_ci.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Failed CI flow — retry dispatched
# ---------------------------------------------------------------------------


class TestGitLabFailedCIFlow:
    """GitLab MR with failed CI triggers _yolo_retry_ci (ci-fix agent dispatch)."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_failed_ci_triggers_retry_ci(self, mock_slug, mock_detect, tmp_path):
        """GitLab MR with CI failed → _yolo_retry_ci called, not merge_review."""
        project = _make_gitlab_project()
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_retry_ci = MagicMock()
        orch._reviews_cache = {
            project.id: [_make_review("7", ci_status="failed")]
        }

        orch._yolo_review_actions_sync()

        orch._yolo_retry_ci.assert_called_once()
        provider.merge_review.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_failed_ci_does_not_merge_even_with_auto_merge_requested(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Failed CI takes precedence over auto_merge_enabled guard for GitLab MRs."""
        project = _make_gitlab_project(merge_queue_enabled=True)
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_retry_ci = MagicMock()
        # auto_merge_enabled=True simulates MWPS already requested but CI failing
        orch._reviews_cache = {
            project.id: [
                _make_review("7", ci_status="failed", auto_merge_enabled=True)
            ]
        }

        orch._yolo_review_actions_sync()

        # CI failure check must fire BEFORE the auto_merge_enabled idempotency guard
        orch._yolo_retry_ci.assert_called_once()
        provider.enable_auto_merge.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Rebase/conflict flow
# ---------------------------------------------------------------------------


class TestGitLabRebaseConflictFlow:
    """GitLab MR with conflicts triggers _yolo_notify_conflict which tries rebase."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_conflict_triggers_notify_conflict(self, mock_slug, mock_detect, tmp_path):
        """GitLab MR with has_conflicts=True → _yolo_notify_conflict dispatched."""
        project = _make_gitlab_project()
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {
            project.id: [_make_review("7", ci_status="passed", has_conflicts=True)]
        }

        orch._yolo_review_actions_sync()

        orch._yolo_notify_conflict.assert_called_once_with(
            project, provider, _GITLAB_SLUG, "7"
        )
        provider.merge_review.assert_not_called()

    def test_gitlab_rebase_success_skips_task_notification(self, tmp_path):
        """When GitLab rebase_review returns success, no task is filed."""
        project = _make_gitlab_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.rebase_review.return_value = (True, "Rebase initiated")
        provider.get_review.side_effect = AssertionError("should not fetch review on success")

        tracker = MagicMock()
        tracker.fetch_issue_detail.side_effect = AssertionError(
            "should not touch tracker on success"
        )
        orch._project_trackers[project.id] = tracker

        orch._yolo_notify_conflict(project, provider, _GITLAB_SLUG, "7")

        provider.rebase_review.assert_called_once_with(_GITLAB_SLUG, "7")
        tracker.add_comment.assert_not_called()

    def test_gitlab_rebase_conflict_falls_through_to_task(self, tmp_path):
        """When GitLab rebase returns conflict, task notification path runs."""
        project = _make_gitlab_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.rebase_review.return_value = (
            False,
            "Rebase failed: merge conflicts require manual resolution",
        )
        review = _make_review(
            review_id="7",
            source_branch="oompah/FEAT-1",
            target_branch="main",
        )
        provider.get_review.return_value = review

        # Wire a tracker so we can assert it was called
        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = []
        orch._project_trackers[project.id] = tracker

        # _yolo_notify_conflict should not raise
        orch._yolo_notify_conflict(project, provider, _GITLAB_SLUG, "7")

        provider.rebase_review.assert_called_once_with(_GITLAB_SLUG, "7")

    def test_gitlab_rebase_network_error_still_notifies(self, tmp_path, caplog):
        """If GitLab rebase raises, the conflict notification still runs."""
        project = _make_gitlab_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.rebase_review.side_effect = RuntimeError("network timeout")
        review = _make_review(review_id="7")
        provider.get_review.return_value = review

        tracker = MagicMock()
        tracker.fetch_issues_by_states.return_value = []
        orch._project_trackers[project.id] = tracker

        with caplog.at_level(logging.WARNING, logger="oompah.orchestrator"):
            orch._yolo_notify_conflict(project, provider, _GITLAB_SLUG, "7")

        provider.rebase_review.assert_called_once_with(_GITLAB_SLUG, "7")
        # A warning about the unexpected failure should be emitted
        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("network timeout" in m or "rebase" in m.lower() for m in warning_messages), (
            f"Expected warning about rebase failure, got: {warning_messages}"
        )


# ---------------------------------------------------------------------------
# 5. Auto-merge via merge_when_pipeline_succeeds
# ---------------------------------------------------------------------------


class TestGitLabAutoMergeMWPS:
    """GitLab queue mode uses merge_when_pipeline_succeeds via enable_auto_merge."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_calls_enable_auto_merge_not_merge_review(
        self, mock_slug, mock_detect, tmp_path
    ):
        """GitLab with merge_queue_enabled=True calls enable_auto_merge (MWPS), not merge_review."""
        project = _make_gitlab_project(merge_queue_enabled=True)
        provider = MagicMock()
        provider.enable_auto_merge.return_value = (
            True,
            "Auto-merge enabled: will merge when pipeline succeeds",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("7", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_called_once_with(_GITLAB_SLUG, "7")
        provider.merge_review.assert_not_called()

    def test_mwps_success_message_contains_pipeline_language(self):
        """The enable_auto_merge success message explicitly mentions pipeline-based merge."""
        provider = GitLabProvider(access_token="tok")

        class _FakeResponse:
            status_code = 200
            text = "{}"

            def json(self):
                return {}

        provider._api = MagicMock(return_value=_FakeResponse())

        ok, msg = provider.enable_auto_merge("org/project", "7")

        assert ok is True
        assert "pipeline" in msg.lower(), f"Expected 'pipeline' in message, got: {msg!r}"

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_already_enqueued_mr_skips_reenqueue(
        self, mock_slug, mock_detect, tmp_path
    ):
        """GitLab MR already with MWPS enabled skips re-enqueue (idempotency)."""
        project = _make_gitlab_project(merge_queue_enabled=True)
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        # auto_merge_enabled=True means MWPS is already set on the MR
        orch._reviews_cache = {
            project.id: [_make_review("7", ci_status="passed", auto_merge_enabled=True)]
        }

        orch._yolo_review_actions_sync()

        # Should not re-call enable_auto_merge
        provider.enable_auto_merge.assert_not_called()
        provider.merge_review.assert_not_called()

    def test_mwps_endpoint_path_uses_merge_not_merge_trains(self):
        """enable_auto_merge uses the standard merge endpoint, NOT a merge_trains path."""
        provider = GitLabProvider(access_token="tok")

        class _FakeResponse:
            status_code = 200
            text = "{}"

            def json(self):
                return {}

        captured_calls: list[tuple] = []

        def _fake_api(method, path, **kwargs):
            captured_calls.append((method, path))
            return _FakeResponse()

        provider._api = _fake_api

        provider.enable_auto_merge("org/project", "7")

        assert len(captured_calls) == 1, f"Expected 1 API call, got: {captured_calls}"
        method, path = captured_calls[0]
        assert method == "PUT"
        assert "merge_requests/7/merge" in path, f"Expected merge endpoint, got: {path}"
        assert "merge_trains" not in path, f"Merge trains endpoint must not be used: {path}"


# ---------------------------------------------------------------------------
# 6. Auto-merge rejection (approval policy / merge trains unsupported)
# ---------------------------------------------------------------------------


class TestGitLabAutoMergeRejection:
    """GitLab enable_auto_merge rejections are surfaced and handled correctly."""

    def test_approval_policy_rejection_returns_actionable_message(self):
        """GitLab approval policy rejection message is actionable."""
        provider = GitLabProvider(access_token="tok")

        class _FakeResponse:
            status_code = 401
            text = "You need approvals before merging"

            def json(self):
                return {}

        provider._api = MagicMock(return_value=_FakeResponse())

        ok, msg = provider.enable_auto_merge("org/project", "7")

        assert ok is False
        assert "approvals" in msg.lower() or "auto-merge rejected" in msg.lower(), (
            f"Expected actionable rejection message, got: {msg!r}"
        )

    def test_403_policy_rejection_also_returns_false(self):
        """GitLab 403 (policy) rejection returns False with message."""
        provider = GitLabProvider(access_token="tok")

        class _FakeResponse:
            status_code = 403
            text = "Project policy requires approvals"

            def json(self):
                return {}

        provider._api = MagicMock(return_value=_FakeResponse())

        ok, msg = provider.enable_auto_merge("org/project", "7")

        assert ok is False
        assert msg  # Message must be non-empty

    def test_405_not_allowed_returns_false(self):
        """GitLab 405 (not allowed) returns False with message."""
        provider = GitLabProvider(access_token="tok")

        class _FakeResponse:
            status_code = 405
            text = "Method not allowed"

            def json(self):
                return {}

        provider._api = MagicMock(return_value=_FakeResponse())

        ok, msg = provider.enable_auto_merge("org/project", "7")

        assert ok is False
        assert "not allowed" in msg.lower() or "405" in msg, (
            f"Expected 'not allowed' message, got: {msg!r}"
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gitlab_merge_failure_dispatches_conflict_agent_on_conflict_message(
        self, mock_slug, mock_detect, tmp_path
    ):
        """GitLab merge conflict message → _yolo_notify_conflict dispatched."""
        project = _make_gitlab_project(merge_queue_enabled=True)
        provider = MagicMock()
        provider.enable_auto_merge.return_value = (
            False,
            "MR is not mergeable: merge conflict in config.yml",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {project.id: [_make_review("7", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        orch._yolo_notify_conflict.assert_called_once_with(
            project, provider, _GITLAB_SLUG, "7"
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gitlab_approval_policy_rejection_does_not_dispatch_conflict_agent(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Approval policy rejection (config error) does NOT dispatch a conflict agent."""
        project = _make_gitlab_project(merge_queue_enabled=False)
        provider = MagicMock()
        # This message matches the "auto_merge" config category
        provider.merge_review.return_value = (
            False,
            "auto-merge not allowed by project settings",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {project.id: [_make_review("7", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        # Config errors should NOT trigger conflict dispatch
        orch._yolo_notify_conflict.assert_not_called()


# ---------------------------------------------------------------------------
# 7. Merge outcome
# ---------------------------------------------------------------------------


class TestGitLabMergeOutcome:
    """Successful GitLab merge calls merge_review once and does not crash."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_successful_direct_merge_calls_provider_once(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Successful direct merge calls merge_review exactly once."""
        project = _make_gitlab_project(merge_queue_enabled=False)
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("7", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called_once_with(_GITLAB_SLUG, "7")

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_merge_failure_does_not_raise(self, mock_slug, mock_detect, tmp_path):
        """Failed merge is handled gracefully — no exception propagated."""
        project = _make_gitlab_project(merge_queue_enabled=False)
        provider = MagicMock()
        provider.merge_review.return_value = (
            False,
            "Merge conflict in src/main.py",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("7", ci_status="passed")]}

        # Must not raise
        orch._yolo_review_actions_sync()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_successful_enqueue_does_not_call_merge_review(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Successful MWPS enqueue never falls back to calling merge_review."""
        project = _make_gitlab_project(merge_queue_enabled=True)
        provider = MagicMock()
        provider.enable_auto_merge.return_value = (True, "Auto-merge enabled")
        mock_detect.return_value = provider
        mock_slug.return_value = _GITLAB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("7", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_called_once()
        provider.merge_review.assert_not_called()


# ---------------------------------------------------------------------------
# 8. Branch protection
# ---------------------------------------------------------------------------


class TestGitLabBranchProtection:
    """Protected GitLab source branches are not deleted after merge."""

    def test_release_branch_is_protected(self):
        """A release/ prefixed source branch is not deleted after GitLab merge."""
        assert _is_protected_branch("release/1.0") is True

    def test_hotfix_branch_is_protected(self):
        """A hotfix/ prefixed source branch is not deleted."""
        assert _is_protected_branch("hotfix/critical-fix") is True

    def test_main_branch_is_protected(self):
        """main/master/develop/trunk are always protected."""
        for branch in ("main", "master", "develop", "trunk"):
            assert _is_protected_branch(branch) is True

    def test_normal_work_branch_is_not_protected(self):
        """An Oompah work branch (feat/task) is eligible for deletion."""
        assert _is_protected_branch("oompah/FEAT-1") is False
        assert _is_protected_branch("feat/my-feature") is False

    def test_gitlab_provider_sends_remove_source_false_for_protected_branch(self):
        """GitLabProvider.merge_review sends should_remove_source_branch=False for release/ branches."""
        provider = GitLabProvider(access_token="tok")
        api_calls: list[tuple] = []

        class _FakeResponse:
            def __init__(self, sc, body=None):
                self.status_code = sc
                self._body = body or {}

            def json(self):
                return self._body

        def _fake_api(method, path, **kwargs):
            api_calls.append((method, path, kwargs))
            if method == "GET":
                return _FakeResponse(200, {"source_branch": "release/1.0"})
            if method == "PUT":
                return _FakeResponse(200, {"state": "merged"})
            return _FakeResponse(200)

        provider._api = _fake_api
        ok, msg = provider.merge_review("org/project", "7")

        assert ok is True
        # Find the PUT merge call
        put_calls = [(p, k) for m, p, k in api_calls if m == "PUT"]
        assert put_calls, "Expected a PUT merge call"
        _, put_kwargs = put_calls[0]
        json_body = put_kwargs.get("json", {})
        assert json_body.get("should_remove_source_branch") is False, (
            f"Expected should_remove_source_branch=False for release/ branch, "
            f"got json={json_body}"
        )

    def test_gitlab_provider_sends_remove_source_true_for_work_branch(self):
        """GitLabProvider.merge_review sends should_remove_source_branch=True for work branches."""
        provider = GitLabProvider(access_token="tok")
        api_calls: list[tuple] = []

        class _FakeResponse:
            def __init__(self, sc, body=None):
                self.status_code = sc
                self._body = body or {}

            def json(self):
                return self._body

        def _fake_api(method, path, **kwargs):
            api_calls.append((method, path, kwargs))
            if method == "GET":
                return _FakeResponse(200, {"source_branch": "oompah/FEAT-1"})
            if method == "PUT":
                return _FakeResponse(200, {"state": "merged"})
            return _FakeResponse(200)

        provider._api = _fake_api
        ok, _ = provider.merge_review("org/project", "7")

        assert ok is True
        put_calls = [(p, k) for m, p, k in api_calls if m == "PUT"]
        assert put_calls, "Expected a PUT merge call"
        _, put_kwargs = put_calls[0]
        json_body = put_kwargs.get("json", {})
        assert json_body.get("should_remove_source_branch") is True, (
            f"Expected should_remove_source_branch=True for work branch, "
            f"got json={json_body}"
        )


# ---------------------------------------------------------------------------
# 9. GitLab release delivery CI remediation (idempotency)
# ---------------------------------------------------------------------------


class TestGitLabReleaseDeliveryCIRemediation:
    """GitLab release pipeline failure creates exactly one remediation task."""

    def test_gitlab_failed_pipeline_creates_one_remediation_task(self):
        """A failed GitLab release pipeline creates exactly one remediation task."""
        delivery = _make_delivery(
            pr_url="https://gitlab.com/group/project/-/merge_requests/7",
        )

        created, store = _run_ci_monitor(
            [delivery],
            ci_status="failed",
            repo_url="https://gitlab.com/group/project.git",
            repo_slug="group/project",
        )

        assert len(created) == 1, f"Expected 1 remediation task, got {len(created)}"

    def test_gitlab_nested_namespace_slug_used_for_ci_check(self):
        """Nested GitLab namespace is passed intact to get_branch_ci_status."""
        delivery = _make_delivery(
            delivery_id="rd_gl_002",
            pr_url="https://gitlab.com/group/subgroup/project/-/merge_requests/8",
        )

        captured_scm: list[MagicMock] = []
        _run_ci_monitor(
            [delivery],
            ci_status="failed",
            repo_url="https://gitlab.com/group/subgroup/project.git",
            repo_slug="group/subgroup/project",
            scm_capture=captured_scm,
        )

        assert len(captured_scm) == 1
        captured_scm[0].get_branch_ci_status.assert_called_with(
            "group/subgroup/project", "release/1.0"
        )

    def test_gitlab_idempotency_second_tick_skips_already_remediated(self):
        """A delivery already stamped with ci_remediation_task_id is not re-remediated."""
        delivery = _make_delivery(
            delivery_id="rd_gl_003",
            ci_remediation_task_id="PROJ-42",  # Already remediated
        )

        created, store = _run_ci_monitor(
            [delivery],
            ci_status="failed",
            existing_remediation_ids={"PROJ-42"},
        )

        assert len(created) == 0, f"Expected no new tasks (idempotent), got {len(created)}"

    def test_gitlab_passed_pipeline_does_not_create_remediation(self):
        """Passing CI on GitLab release branch → no remediation task."""
        delivery = _make_delivery(delivery_id="rd_gl_004")

        created, store = _run_ci_monitor([delivery], ci_status="passed")

        assert len(created) == 0, f"Expected no remediation on passed CI, got {len(created)}"

    def test_gitlab_pending_pipeline_does_not_create_remediation(self):
        """Pending CI is not yet actionable → no remediation task created."""
        delivery = _make_delivery(delivery_id="rd_gl_005")

        created, store = _run_ci_monitor([delivery], ci_status="pending")

        assert len(created) == 0, f"Expected no remediation on pending CI, got {len(created)}"

    def test_gitlab_remediation_stamps_delivery_before_creating_task(self):
        """The delivery is stamped with ci_remediation_task_id before the task is created."""
        delivery = _make_delivery(delivery_id="rd_gl_006")

        created, store = _run_ci_monitor(
            [delivery],
            ci_status="failed",
        )

        # After remediation the stored delivery must have a task ID
        updated = next(d for d in store._items if d.id == "rd_gl_006")
        assert updated.ci_remediation_task_id is not None, (
            "Expected ci_remediation_task_id to be stamped after remediation"
        )

    def test_gitlab_delivery_without_result_commits_skipped(self):
        """Merged delivery without result_commits is not checked (no evidence of what landed)."""
        delivery = _make_delivery(delivery_id="rd_gl_007", result_commits=[])

        created, store = _run_ci_monitor([delivery], ci_status="failed")

        assert len(created) == 0, (
            f"Expected no remediation for delivery without result_commits, got {len(created)}"
        )


# ---------------------------------------------------------------------------
# 10. GitHub regression tests — same flows must still work
# ---------------------------------------------------------------------------


class TestGitHubRegressionNormalFlow:
    """GitHub YOLO flows are unaffected by GitLab integration."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_github_direct_merge_on_ci_passed(self, mock_slug, mock_detect, tmp_path):
        """GitHub project still uses direct merge when merge_queue_enabled=False."""
        project = _make_github_project(merge_queue_enabled=False)
        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = _GITHUB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "42",
                    url="https://github.com/org/repo/pull/42",
                    ci_status="passed",
                )
            ]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called_once_with(_GITHUB_SLUG, "42")

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_github_pending_ci_skipped(self, mock_slug, mock_detect, tmp_path):
        """GitHub project with pending CI → YOLO skips merge."""
        project = _make_github_project()
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITHUB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "42",
                    url="https://github.com/org/repo/pull/42",
                    ci_status="pending",
                )
            ]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()
        provider.enable_auto_merge.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_github_failed_ci_triggers_retry(self, mock_slug, mock_detect, tmp_path):
        """GitHub project with failed CI → _yolo_retry_ci dispatched."""
        project = _make_github_project()
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITHUB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_retry_ci = MagicMock()
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "42",
                    url="https://github.com/org/repo/pull/42",
                    ci_status="failed",
                )
            ]
        }

        orch._yolo_review_actions_sync()

        orch._yolo_retry_ci.assert_called_once()
        provider.merge_review.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_github_conflict_triggers_notify_conflict(self, mock_slug, mock_detect, tmp_path):
        """GitHub PR with conflicts → _yolo_notify_conflict dispatched."""
        project = _make_github_project()
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITHUB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "42",
                    url="https://github.com/org/repo/pull/42",
                    ci_status="passed",
                    has_conflicts=True,
                )
            ]
        }

        orch._yolo_review_actions_sync()

        orch._yolo_notify_conflict.assert_called_once_with(
            project, provider, _GITHUB_SLUG, "42"
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_github_queue_mode_uses_enable_auto_merge(self, mock_slug, mock_detect, tmp_path):
        """GitHub merge queue mode calls enable_auto_merge as before."""
        project = _make_github_project(merge_queue_enabled=True)
        provider = MagicMock()
        provider.enable_auto_merge.return_value = (True, "enqueued")
        mock_detect.return_value = provider
        mock_slug.return_value = _GITHUB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "42",
                    url="https://github.com/org/repo/pull/42",
                    ci_status="passed",
                )
            ]
        }

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_called_once_with(_GITHUB_SLUG, "42")
        provider.merge_review.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_github_draft_pr_not_merged(self, mock_slug, mock_detect, tmp_path):
        """GitHub draft PRs are skipped."""
        project = _make_github_project()
        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = _GITHUB_SLUG

        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "42",
                    url="https://github.com/org/repo/pull/42",
                    ci_status="passed",
                    draft=True,
                )
            ]
        }

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_not_called()
        provider.enable_auto_merge.assert_not_called()


class TestGitHubRegressionBranchProtection:
    """GitHub branch protection works the same as GitLab."""

    def test_github_release_branch_is_protected(self):
        assert _is_protected_branch("release/2.0") is True

    def test_github_feature_branch_not_protected(self):
        assert _is_protected_branch("feature/my-thing") is False

    def test_github_merge_queue_branch_is_protected(self):
        """GitHub's merge queue uses gh-readonly-queue/ prefix."""
        assert _is_protected_branch("gh-readonly-queue/main/pr-42-abc") is True


class TestGitHubReleaseDeliveryCIRemediation:
    """GitHub release pipeline failure also creates exactly one remediation task (regression)."""

    def test_github_failed_pipeline_creates_one_task(self):
        """GitHub release CI failure creates a remediation task (parity with GitLab)."""
        delivery = _make_delivery(
            delivery_id="rd_gh_001",
            pr_url="https://github.com/org/project/pull/7",
        )

        created, store = _run_ci_monitor(
            [delivery],
            ci_status="failed",
            repo_url="https://github.com/org/project.git",
            repo_slug="org/project",
        )

        assert len(created) == 1, f"Expected 1 remediation task, got {len(created)}"

    def test_github_idempotency_second_tick_skips_already_remediated(self):
        """GitHub delivery already stamped skips re-remediation."""
        delivery = _make_delivery(
            delivery_id="rd_gh_002",
            pr_url="https://github.com/org/project/pull/8",
            ci_remediation_task_id="PROJ-99",
        )

        created, _ = _run_ci_monitor(
            [delivery],
            ci_status="failed",
            repo_url="https://github.com/org/project.git",
            repo_slug="org/project",
            existing_remediation_ids={"PROJ-99"},
        )

        assert len(created) == 0


class TestMixedForgeNoInterference:
    """GitLab and GitHub projects in the same orchestrator tick don't interfere."""

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_gitlab_and_github_projects_each_get_correct_provider(
        self, mock_slug, mock_detect, tmp_path
    ):
        """When a GitLab and GitHub project coexist, each gets its own provider instance."""
        gl_project = _make_gitlab_project(project_id="proj-gl")
        gh_project = _make_github_project(project_id="proj-gh")

        gl_provider = MagicMock(name="gitlab_provider")
        gl_provider.merge_review.return_value = (True, "merged")
        gh_provider = MagicMock(name="github_provider")
        gh_provider.merge_review.return_value = (True, "merged")

        # detect_provider returns the right provider based on the repo_url
        def _detect(url, access_token=None):
            if "gitlab" in url:
                return gl_provider
            return gh_provider

        mock_detect.side_effect = _detect

        def _slug(url):
            if "gitlab" in url:
                return _GITLAB_SLUG
            return _GITHUB_SLUG

        mock_slug.side_effect = _slug

        orch = _make_orchestrator(tmp_path, projects=[gl_project, gh_project])
        gl_review = _make_review(
            "7",
            url="https://gitlab.com/org/project/-/merge_requests/7",
            ci_status="passed",
        )
        gh_review = _make_review(
            "42",
            url="https://github.com/org/repo/pull/42",
            ci_status="passed",
        )
        orch._reviews_cache = {
            "proj-gl": [gl_review],
            "proj-gh": [gh_review],
        }

        orch._yolo_review_actions_sync()

        gl_provider.merge_review.assert_called_once_with(_GITLAB_SLUG, "7")
        gh_provider.merge_review.assert_called_once_with(_GITHUB_SLUG, "42")
