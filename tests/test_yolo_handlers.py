"""Tests for YOLO mode helpers (oompah-zlz_2-s56w).

Covers the rebase-before-notify behavior in
``Orchestrator._yolo_notify_conflict``:

- Provider rebase succeeds → no task notification.
- Provider rebase fails with ``conflict`` in message → task notify path runs.
- Provider rebase fails for unrelated reason (network/auth/etc.) → task notify
  path still runs (safety net) AND a WARNING is logged.
- Provider rebase raises → task notify path still runs (safety net).
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import EpicRebaseState
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest
from oompah.statuses import IN_REVIEW, NEEDS_CI_FIX, NEEDS_REBASE


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_project(
    project_id: str = "proj-1",
    repo_url: str = "https://github.com/org/repo",
    yolo: bool = True,
):
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = "test-project"
    p.yolo = yolo
    p.default_branch = "main"
    return p


def _make_review_request(
    review_id: str = "30",
    source_branch: str = "trickle-x1y",
    target_branch: str = "main",
    has_conflicts: bool = True,
    ci_status: str = "passed",
) -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title=f"PR #{review_id}",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="alice",
        state="open",
        source_branch=source_branch,
        target_branch=target_branch,
        created_at="2025-01-01",
        updated_at="2025-01-02",
        ci_status=ci_status,
        has_conflicts=has_conflicts,
    )


def _make_orchestrator(tmp_path, projects=None):
    """Create a test orchestrator with a mocked project store."""
    from oompah.roles import RoleStore

    all_projects = list(projects or [])
    project_store = MagicMock()
    project_store.list_all.return_value = all_projects
    project_store.get.side_effect = lambda pid: next(
        (p for p in all_projects if p.id == pid), None
    )
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    return Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )


class TestYoloNotifyConflictRebaseFirst:
    """_yolo_notify_conflict tries provider.rebase_review before the task.

    Mirrors the dashboard "Resolve Conflicts" button's behavior at
    server.py:2825 — try the cheap provider rebase first, only disturb the
    task if the rebase produces a real merge conflict. (oompah-zlz_2-s56w)
    """

    # --- Path 1: rebase success short-circuits the task-notify path ---

    def test_rebase_success_skips_task_notification(self, tmp_path, caplog):
        """When provider.rebase_review returns success, no task is touched."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.rebase_review.return_value = (True, "Rebase initiated successfully")
        # If anything tries to fetch the review / task, the test must fail
        # — short-circuit must happen before that.
        provider.get_review.side_effect = AssertionError(
            "rebase success path must NOT fetch the review"
        )

        tracker = MagicMock()
        # Same guard: tracker must not be touched on the success path.
        tracker.fetch_issue_detail.side_effect = AssertionError(
            "rebase success path must NOT touch the tracker"
        )
        orch._project_trackers[project.id] = tracker

        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            orch._yolo_notify_conflict(project, provider, "org/repo", "30")

        provider.rebase_review.assert_called_once_with("org/repo", "30")
        # Task untouched
        tracker.fetch_issue_detail.assert_not_called()
        tracker.add_comment.assert_not_called()
        tracker.update_issue.assert_not_called()
        # Telemetry: success log present.
        assert any(
            "rebased" in rec.message.lower() and "30" in rec.message
            for rec in caplog.records
        ), (
            f"expected YOLO rebase-success log, got: {[r.message for r in caplog.records]}"
        )

    # --- Path 2: rebase fails with 'conflict' -> task-notify fires ---

    def test_rebase_fails_with_conflict_falls_through_to_task(self, tmp_path):
        """Rebase fails with 'merge conflicts' in the message → existing task path runs."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.rebase_review.return_value = (
            False,
            "Rebase failed: merge conflicts require manual resolution",
        )
        provider.get_review.return_value = _make_review_request(
            review_id="30",
            source_branch="trickle-real",
        )

        tracker = MagicMock()
        existing = MagicMock()
        existing.state = "closed"
        existing.labels = []
        existing.identifier = "trickle-real"
        existing.id = "trickle-real"
        tracker.fetch_issue_detail.return_value = existing
        orch._project_trackers[project.id] = tracker

        orch._yolo_notify_conflict(project, provider, "org/repo", "30")

        # Task path ran: comment + reopen
        provider.rebase_review.assert_called_once_with("org/repo", "30")
        tracker.fetch_issue_detail.assert_called_once()
        tracker.add_comment.assert_called_once()
        tracker.update_issue.assert_called_once()

    # --- Path 3: rebase fails with non-conflict reason -> task-notify still fires ---

    def test_rebase_fails_with_network_error_still_notifies_task(
        self, tmp_path, caplog
    ):
        """Network/transport failure: WARNING logged, task notification fires anyway."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.rebase_review.return_value = (
            False,
            "Rebase failed: HTTPSConnectionPool(host='api.github.com'): Read timed out",
        )
        provider.get_review.return_value = _make_review_request(
            review_id="31",
            source_branch="trickle-real-31",
        )

        tracker = MagicMock()
        existing = MagicMock()
        existing.state = "closed"
        existing.labels = []
        existing.identifier = "trickle-real-31"
        existing.id = "trickle-real-31"
        tracker.fetch_issue_detail.return_value = existing
        orch._project_trackers[project.id] = tracker

        with caplog.at_level(logging.WARNING, logger="oompah.orchestrator"):
            orch._yolo_notify_conflict(project, provider, "org/repo", "31")

        # The safety net is preserved: task-notify path still ran.
        provider.rebase_review.assert_called_once_with("org/repo", "31")
        tracker.fetch_issue_detail.assert_called_once()
        tracker.add_comment.assert_called_once()
        tracker.update_issue.assert_called_once()
        # WARNING surfaced so an operator can see the non-conflict failure
        # didn't get the cheap rebase path.
        assert any(
            "non-conflict" in rec.message.lower() and rec.levelname == "WARNING"
            for rec in caplog.records
        ), (
            "expected WARNING for non-conflict rebase failure, got: "
            f"{[(r.levelname, r.message) for r in caplog.records]}"
        )

    def test_rebase_raises_still_notifies_task(self, tmp_path, caplog):
        """If provider.rebase_review raises, fall through to task-notify anyway."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.rebase_review.side_effect = RuntimeError("boom")
        provider.get_review.return_value = _make_review_request(
            review_id="32",
            source_branch="trickle-real-32",
        )

        tracker = MagicMock()
        existing = MagicMock()
        existing.state = "closed"
        existing.labels = []
        existing.identifier = "trickle-real-32"
        existing.id = "trickle-real-32"
        tracker.fetch_issue_detail.return_value = existing
        orch._project_trackers[project.id] = tracker

        with caplog.at_level(logging.WARNING, logger="oompah.orchestrator"):
            orch._yolo_notify_conflict(project, provider, "org/repo", "32")

        provider.rebase_review.assert_called_once_with("org/repo", "32")
        tracker.fetch_issue_detail.assert_called_once()
        tracker.add_comment.assert_called_once()
        tracker.update_issue.assert_called_once()
        # And a WARNING was emitted so we can spot the raising provider.
        assert any("rebase raised" in rec.message.lower() for rec in caplog.records), (
            "expected WARNING for raising provider.rebase_review, got: "
            f"{[(r.levelname, r.message) for r in caplog.records]}"
        )

    def test_deferred_issue_reopened_for_conflict(self, tmp_path):
        """Non-terminal, non-actionable states like 'deferred' are reopened as P0
        for conflict resolution, not just labeled and left behind."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.rebase_review.return_value = (False, "merge conflict in foo.py")
        provider.get_review.return_value = _make_review_request(
            review_id="33",
            source_branch="trickle-deferred-33",
        )

        tracker = MagicMock()
        existing = MagicMock()
        existing.state = "deferred"
        existing.labels = ["merge-conflict"]
        existing.identifier = "trickle-deferred-33"
        existing.id = "trickle-deferred-33"
        tracker.fetch_issue_detail.return_value = existing
        orch._project_trackers[project.id] = tracker

        orch._yolo_notify_conflict(project, provider, "org/repo", "33")

        # The comment is added every tick
        tracker.add_comment.assert_called_once()
        # The issue MUST be reopened from deferred -> open with P0 priority so
        # the conflict-resolution agent can actually be dispatched.
        tracker.update_issue.assert_called_once_with(
            "trickle-deferred-33",
            status="Needs Rebase",
            priority="0",
            **{"add-label": "merge-conflict"},
        )

    def test_orphan_recovery_cross_restart_dedup_skips_filing(self, tmp_path):
        """When an open issue with the matching label already exists in the
        tracker, _file_orphan_recovery_task should reuse it rather than
        filing a duplicate (cross-restart safety net)."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.rebase_review.return_value = (False, "merge conflict in foo.py")
        provider.get_review.return_value = _make_review_request(
            review_id="40",
            source_branch="orphan-branch-40",
        )

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None  # orphan branch
        # Cross-restart check: existing open issue with merge-conflict label
        existing_issue = MagicMock()
        existing_issue.identifier = "rogers-existing"
        existing_issue.created_at = "2026-01-01T00:00:00Z"
        tracker.fetch_issues_by_labels.return_value = [existing_issue]
        orch._project_trackers[project.id] = tracker

        orch._yolo_notify_conflict(project, provider, "org/repo", "40")

        # Must NOT create a new issue
        tracker.create_issue.assert_not_called()
        tracker.add_label.assert_not_called()
        # But should record the reused task in bookkeeping
        assert (project.id, "40", "merge-conflict") in orch._yolo_orphan_recovery_tasks
        assert (
            orch._yolo_orphan_recovery_tasks[(project.id, "40", "merge-conflict")]
            == "rogers-existing"
        )


# ---------------------------------------------------------------------------
# Branch -> task resolution (epic-<id> branches map back to the epic)
# ---------------------------------------------------------------------------

from unittest.mock import call  # noqa: E402


class TestResolveTaskForBranch:
    def test_normal_branch_resolves_directly(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        task = MagicMock(identifier="TASK-8.2")
        tracker.fetch_issue_detail.return_value = task
        assert orch._resolve_task_for_branch(tracker, "TASK-8.2") is task
        tracker.fetch_issue_detail.assert_called_once_with("TASK-8.2")

    def test_epic_branch_strips_prefix(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        epic = MagicMock(identifier="TASK-706")
        tracker.fetch_issue_detail.side_effect = lambda i: epic if i == "TASK-706" else None
        got = orch._resolve_task_for_branch(tracker, "epic-TASK-706")
        assert got is epic
        assert tracker.fetch_issue_detail.call_args_list == [
            call("epic-TASK-706"), call("TASK-706")
        ]

    def test_true_orphan_returns_none(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        assert orch._resolve_task_for_branch(tracker, "epic-TASK-999") is None

    # -----------------------------------------------------------------------
    # Branch-index path (TASK-462.1) — GitHub-backed tasks
    # -----------------------------------------------------------------------

    def test_github_branch_resolved_via_index(self, tmp_path):
        """AC#1: GitHub-style branch resolved through work_branch index."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()

        # The tracker has one issue whose work_branch is the GitHub slug.
        gh_issue = MagicMock()
        gh_issue.work_branch = "oompah/trickle/gh-42"
        gh_issue.identifier = "example-org/oompah-tasks#42"
        tracker.fetch_issues_by_states.return_value = [gh_issue]

        resolved = MagicMock(identifier="example-org/oompah-tasks#42")
        tracker.fetch_issue_detail.return_value = resolved

        result = orch._resolve_task_for_branch(
            tracker, "oompah/trickle/gh-42", project_id="proj-1"
        )
        assert result is resolved
        tracker.fetch_issue_detail.assert_called_once_with("example-org/oompah-tasks#42")

    def test_github_epic_branch_resolved_via_index(self, tmp_path):
        """epic- prefix is stripped when looking up the index."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()

        gh_epic = MagicMock()
        gh_epic.work_branch = "oompah/trickle/epic-gh-7"
        gh_epic.identifier = "example-org/oompah-tasks#7"
        tracker.fetch_issues_by_states.return_value = [gh_epic]

        resolved = MagicMock(identifier="example-org/oompah-tasks#7")
        tracker.fetch_issue_detail.return_value = resolved

        result = orch._resolve_task_for_branch(
            tracker, "epic-oompah/trickle/epic-gh-7", project_id="proj-2"
        )
        assert result is resolved

    def test_no_project_id_skips_index(self, tmp_path):
        """Legacy path: no project_id → direct fetch_issue_detail, no index built."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        task = MagicMock(identifier="TASK-9")
        tracker.fetch_issue_detail.return_value = task

        result = orch._resolve_task_for_branch(tracker, "TASK-9")
        assert result is task
        # No call to fetch_issues_by_states (index not built)
        tracker.fetch_issues_by_states.assert_not_called()

    def test_index_miss_falls_back_to_legacy_lookup(self, tmp_path):
        """AC#2: When branch isn't in the index, fall back to fetch_issue_detail."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        # Index has no entries matching the branch.
        tracker.fetch_issues_by_states.return_value = []
        task = MagicMock(identifier="TASK-50")
        tracker.fetch_issue_detail.return_value = task

        result = orch._resolve_task_for_branch(
            tracker, "TASK-50", project_id="proj-3"
        )
        assert result is task
        tracker.fetch_issue_detail.assert_called_with("TASK-50")

    def test_index_is_cached_across_calls(self, tmp_path):
        """Branch index is built once per project per cache window."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()

        gh_issue = MagicMock()
        gh_issue.work_branch = "oompah/proj/gh-5"
        gh_issue.identifier = "owner/repo#5"
        tracker.fetch_issues_by_states.return_value = [gh_issue]

        resolved = MagicMock(identifier="owner/repo#5")
        tracker.fetch_issue_detail.return_value = resolved

        # First call builds the index.
        orch._resolve_task_for_branch(tracker, "oompah/proj/gh-5", project_id="p1")
        # Second call for same project should NOT rebuild the index.
        orch._resolve_task_for_branch(tracker, "oompah/proj/gh-5", project_id="p1")

        # fetch_issues_by_states called exactly once (index was cached).
        tracker.fetch_issues_by_states.assert_called_once()

    def test_invalidate_clears_branch_index(self, tmp_path):
        """_invalidate_tracker_read_caches() clears the branch index."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()

        gh_issue = MagicMock()
        gh_issue.work_branch = "oompah/proj/gh-6"
        gh_issue.identifier = "owner/repo#6"
        tracker.fetch_issues_by_states.return_value = [gh_issue]
        tracker.fetch_issue_detail.return_value = MagicMock(identifier="owner/repo#6")

        # Populate the cache.
        orch._resolve_task_for_branch(tracker, "oompah/proj/gh-6", project_id="p2")
        assert "p2" in orch._branch_indexes

        # Invalidate: the tracker is registered so _invalidate can call its method.
        orch._project_trackers["p2"] = tracker
        orch._invalidate_tracker_read_caches()

        # Index should be cleared.
        assert orch._branch_indexes == {}

    def test_index_build_error_falls_back_to_legacy(self, tmp_path):
        """If index build raises, legacy lookup is still attempted."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issues_by_states.side_effect = RuntimeError("API offline")
        task = MagicMock(identifier="TASK-10")
        tracker.fetch_issue_detail.return_value = task

        result = orch._resolve_task_for_branch(
            tracker, "TASK-10", project_id="proj-err"
        )
        assert result is task
        # Legacy path ran.
        tracker.fetch_issue_detail.assert_called_with("TASK-10")


class TestEpicBranchCiFailUsesEpicNotOrphan:
    """An epic->main PR's CI failure must resolve to the epic (and route
    through the parent/sibling path), not be treated as an orphan PR."""

    def test_epic_branch_does_not_file_orphan_task(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        epic = MagicMock(
            identifier="TASK-706",
            id="TASK-706",
            labels=[],
            state="Backlog",
            issue_type="epic",
        )
        tracker.fetch_issue_detail.side_effect = lambda i: epic if i == "TASK-706" else None
        orch._project_trackers[project.id] = tracker
        orch._file_orphan_recovery_task = MagicMock()  # must NOT be used now
        # Epic has a child → retry_ci routes to the epic/parent path.
        orch._fetch_epic_children = MagicMock(
            return_value=[MagicMock(identifier="TASK-706.1", state="Done", labels=[])]
        )
        review = MagicMock(source_branch="epic-TASK-706", id="171", ci_status="failed")
        orch._yolo_retry_ci(project, review)
        orch._file_orphan_recovery_task.assert_not_called()

    def test_epic_branch_parent_ci_fix_label_marks_mature_epic(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        epic = MagicMock(
            identifier="TASK-706",
            id="TASK-706",
            labels=["ci-fix"],
            state="In Review",
            issue_type="epic",
        )
        tracker.fetch_issue_detail.side_effect = lambda i: epic if i == "TASK-706" else None
        orch._project_trackers[project.id] = tracker
        orch._file_orphan_recovery_task = MagicMock()
        orch._fetch_epic_children = MagicMock(
            return_value=[MagicMock(identifier="TASK-706.1", state=IN_REVIEW, labels=[])]
        )
        review = MagicMock(source_branch="epic-TASK-706", id="171", ci_status="failed")

        orch._yolo_retry_ci(project, review)

        orch._file_orphan_recovery_task.assert_not_called()
        tracker.create_issue.assert_not_called()
        tracker.update_issue.assert_called_once_with(
            "TASK-706",
            status=NEEDS_CI_FIX,
            priority="0",
            **{"add-label": "ci-fix"},
        )

    def test_true_orphan_still_files_recovery_task(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None  # nothing resolves
        orch._project_trackers[project.id] = tracker
        orch._file_orphan_recovery_task = MagicMock()
        review = MagicMock(source_branch="some-random-branch", id="42", ci_status="failed")
        orch._yolo_retry_ci(project, review)
        orch._file_orphan_recovery_task.assert_called_once()


class TestYoloNotifyConflictEpicBranch:
    """A conflict on a mature EPIC branch repairs the epic PR directly."""

    def _epic(self):
        epic = MagicMock()
        epic.issue_type = "epic"
        epic.identifier = "TASK-18"
        epic.id = "TASK-18"
        epic.state = "Backlog"
        epic.labels = []
        return epic

    def test_mature_epic_branch_conflict_marks_epic_needs_rebase(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.epic_branch_name.side_effect = lambda ident: f"epic-{ident}"
        orch._set_epic_rebase_state = MagicMock()
        provider = MagicMock()
        provider.rebase_review.return_value = (
            False, "Rebase failed: merge conflicts require manual resolution",
        )
        provider.get_review.return_value = _make_review_request(
            review_id="42", source_branch="epic-TASK-18", target_branch="dev",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = self._epic()
        with patch.object(
            orch,
            "_fetch_epic_children",
            return_value=[MagicMock(identifier="TASK-18.1", state=IN_REVIEW, labels=[])],
        ):
            orch._project_trackers[project.id] = tracker
            orch._yolo_notify_conflict(project, provider, "org/repo", "42")

        tracker.create_issue.assert_not_called()
        tracker.update_issue.assert_called_once_with(
            "TASK-18",
            status=NEEDS_REBASE,
            priority="0",
            **{"add-label": "merge-conflict"},
        )

    def test_epic_branch_conflict_idempotent_when_rebase_sibling_open(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.epic_branch_name.side_effect = lambda ident: f"epic-{ident}"
        orch._set_epic_rebase_state = MagicMock()
        provider = MagicMock()
        provider.rebase_review.return_value = (False, "merge conflicts")
        provider.get_review.return_value = _make_review_request(
            review_id="42", source_branch="epic-TASK-18", target_branch="dev",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = self._epic()
        existing = MagicMock(id="TASK-18.r", state="In Progress",
                             title="Rebase epic-TASK-18 onto dev")
        with patch.object(orch, "_fetch_epic_children", return_value=[existing]):
            orch._project_trackers[project.id] = tracker
            orch._yolo_notify_conflict(project, provider, "org/repo", "42")

        # No duplicate rebase task while one is already open.
        tracker.create_issue.assert_not_called()
        orch._set_epic_rebase_state.assert_called_once_with(
            "TASK-18",
            EpicRebaseState.REBASING,
            project_id=project.id,
        )

    def test_epic_branch_conflict_idempotent_when_child_read_misses_existing_rebase(
        self, tmp_path
    ):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch.project_store.epic_branch_name.side_effect = lambda ident: f"epic-{ident}"
        orch._set_epic_rebase_state = MagicMock()
        provider = MagicMock()
        provider.rebase_review.return_value = (False, "merge conflicts")
        provider.get_review.return_value = _make_review_request(
            review_id="42", source_branch="epic-TASK-18", target_branch="dev",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = self._epic()
        existing = MagicMock(
            id="TASK-18.7",
            identifier="TASK-18.7",
            state="Needs Rebase",
            title="Rebase epic-TASK-18 onto dev",
            parent_id="TASK-18",
            created_at="2026-06-10T06:00:00+00:00",
        )
        tracker.fetch_issues_by_states.return_value = [existing]
        with patch.object(orch, "_fetch_epic_children", return_value=[]):
            orch._project_trackers[project.id] = tracker
            orch._yolo_notify_conflict(project, provider, "org/repo", "42")

        tracker.create_issue.assert_not_called()
        orch._set_epic_rebase_state.assert_called_once_with(
            "TASK-18",
            EpicRebaseState.REBASING,
            project_id=project.id,
        )

    def test_epic_branch_conflict_helper_marks_epic_rebasing(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        orch._set_epic_rebase_state = MagicMock()
        provider = MagicMock()
        provider.rebase_review.return_value = (False, "merge conflicts")
        provider.get_review.return_value = _make_review_request(
            review_id="42", source_branch="epic-TASK-18", target_branch="dev",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = self._epic()
        tracker.fetch_issues_by_states.return_value = []
        open_child = MagicMock(identifier="TASK-18.1", state="Open", labels=[])

        with patch.object(orch, "_fetch_epic_children", return_value=[open_child]):
            orch._project_trackers[project.id] = tracker
            orch._yolo_notify_conflict(project, provider, "org/repo", "42")

        tracker.create_issue.assert_called_once()
        orch._set_epic_rebase_state.assert_called_once_with(
            "TASK-18",
            EpicRebaseState.REBASING,
            project_id=project.id,
        )


class TestFileRebaseTaskPriority:
    def test_rebase_task_is_p0_to_bypass_in_flight_cap(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        epic = MagicMock()
        epic.identifier = "TASK-18"
        tracker = MagicMock()
        orch._file_rebase_task(tracker, epic, "epic-TASK-18", "dev")
        tracker.create_issue.assert_called_once()
        # P0 so it bypasses the open-PR cap;
        # otherwise the conflicting epic PR (which holds the in-flight slot)
        # would block the very agent that must resolve it.
        assert tracker.create_issue.call_args.kwargs.get("priority") == 0
