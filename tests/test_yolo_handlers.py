"""Tests for YOLO mode helpers (oompah-zlz_2-s56w).

Covers the rebase-before-notify behavior in
``Orchestrator._yolo_notify_conflict``:

- Provider rebase succeeds → no bead notification.
- Provider rebase fails with ``conflict`` in message → bead notify path runs.
- Provider rebase fails for unrelated reason (network/auth/etc.) → bead notify
  path still runs (safety net) AND a WARNING is logged.
- Provider rebase raises → bead notify path still runs (safety net).
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.orchestrator import Orchestrator
from oompah.scm import ReviewRequest


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
    """_yolo_notify_conflict tries provider.rebase_review before the bead.

    Mirrors the dashboard "Resolve Conflicts" button's behavior at
    server.py:2825 — try the cheap provider rebase first, only disturb the
    bead if the rebase produces a real merge conflict. (oompah-zlz_2-s56w)
    """

    # --- Path 1: rebase success short-circuits the bead-notify path ---

    def test_rebase_success_skips_bead_notification(self, tmp_path, caplog):
        """When provider.rebase_review returns success, no bead is touched."""
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])

        provider = MagicMock()
        provider.rebase_review.return_value = (True, "Rebase initiated successfully")
        # If anything tries to fetch the review / bead, the test must fail
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
        # Bead untouched
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

    # --- Path 2: rebase fails with 'conflict' -> bead-notify fires ---

    def test_rebase_fails_with_conflict_falls_through_to_bead(self, tmp_path):
        """Rebase fails with 'merge conflicts' in the message → existing bead path runs."""
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

        # Bead path ran: comment + reopen
        provider.rebase_review.assert_called_once_with("org/repo", "30")
        tracker.fetch_issue_detail.assert_called_once()
        tracker.add_comment.assert_called_once()
        tracker.update_issue.assert_called_once()

    # --- Path 3: rebase fails with non-conflict reason -> bead-notify still fires ---

    def test_rebase_fails_with_network_error_still_notifies_bead(
        self, tmp_path, caplog
    ):
        """Network/transport failure: WARNING logged, bead notification fires anyway."""
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

        # The safety net is preserved: bead-notify path still ran.
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

    def test_rebase_raises_still_notifies_bead(self, tmp_path, caplog):
        """If provider.rebase_review raises, fall through to bead-notify anyway."""
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
        # But should record the reused bead in bookkeeping
        assert (project.id, "40", "merge-conflict") in orch._yolo_orphan_recovery_tasks
        assert (
            orch._yolo_orphan_recovery_tasks[(project.id, "40", "merge-conflict")]
            == "rogers-existing"
        )


# ---------------------------------------------------------------------------
# Branch -> bead resolution (epic-<id> branches map back to the epic)
# ---------------------------------------------------------------------------

from unittest.mock import call  # noqa: E402


class TestResolveBeadForBranch:
    def test_normal_branch_resolves_directly(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        bead = MagicMock(identifier="TASK-8.2")
        tracker.fetch_issue_detail.return_value = bead
        assert orch._resolve_task_for_branch(tracker, "TASK-8.2") is bead
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


class TestEpicBranchCiFailUsesEpicNotOrphan:
    """An epic->main PR's CI failure must resolve to the epic (and route
    through the parent/sibling path), not be treated as an orphan PR."""

    def test_epic_branch_does_not_file_orphan_bead(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        tracker = MagicMock()
        epic = MagicMock(identifier="TASK-706", labels=[], state="Backlog")
        tracker.fetch_issue_detail.side_effect = lambda i: epic if i == "TASK-706" else None
        orch._project_trackers[project.id] = tracker
        orch._file_orphan_recovery_task = MagicMock()  # must NOT be used now
        # Epic has a child → retry_ci routes to the sibling/parent path.
        orch._fetch_epic_children = MagicMock(
            return_value=[MagicMock(identifier="TASK-706.1", state="Done", labels=[])]
        )
        review = MagicMock(source_branch="epic-TASK-706", id="171", ci_status="failed")
        orch._yolo_retry_ci(project, review)
        orch._file_orphan_recovery_task.assert_not_called()

    def test_true_orphan_still_files_recovery_bead(self, tmp_path):
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
    """A conflict on a shared/stacked EPIC branch must route into the
    epic-rebase machinery (mark STALE → dispatchable P0 rebase sibling),
    NOT mark the non-dispatchable epic 'Needs Rebase' (which loops forever)."""

    def _epic(self):
        epic = MagicMock()
        epic.issue_type = "epic"
        epic.identifier = "TASK-18"
        epic.id = "TASK-18"
        epic.state = "Backlog"
        epic.labels = []
        return epic

    def test_epic_branch_conflict_files_p0_rebase_bead_not_needs_rebase(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
        provider = MagicMock()
        provider.rebase_review.return_value = (
            False, "Rebase failed: merge conflicts require manual resolution",
        )
        provider.get_review.return_value = _make_review_request(
            review_id="42", source_branch="epic-TASK-18", target_branch="dev",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = self._epic()
        # No existing rebase sibling.
        with patch.object(orch, "_fetch_epic_children", return_value=[]):
            orch._project_trackers[project.id] = tracker
            orch._yolo_notify_conflict(project, provider, "org/repo", "42")

        # Filed a dispatchable P0 rebase sibling under the epic...
        tracker.create_issue.assert_called_once()
        kw = tracker.create_issue.call_args.kwargs
        assert kw.get("priority") == 0
        assert kw.get("parent") == "TASK-18"
        # ...and did NOT mark the (non-dispatchable) epic Needs Rebase.
        from oompah.statuses import NEEDS_REBASE
        for c in tracker.update_issue.call_args_list:
            assert c.kwargs.get("status") != NEEDS_REBASE

    def test_epic_branch_conflict_idempotent_when_rebase_sibling_open(self, tmp_path):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
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

        # No duplicate rebase bead while one is already open.
        tracker.create_issue.assert_not_called()

    def test_epic_branch_conflict_idempotent_when_child_read_misses_existing_rebase(
        self, tmp_path
    ):
        project = _make_project()
        orch = _make_orchestrator(tmp_path, projects=[project])
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


class TestFileRebaseBeadPriority:
    def test_rebase_bead_is_p0_to_bypass_in_flight_cap(self, tmp_path):
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
