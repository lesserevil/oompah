from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from oompah.integration import IntegrationRecord
from oompah.integration_executor import IntegrationExecutionResult
from oompah.integration_queue import IntegrationQueueItem
from oompah.auditor_dispatch import AuditDispatchPlan
from oompah.models import (
    BlockerRef,
    EpicRebaseState,
    Issue,
    Project,
    RunningEntry,
)
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore
from oompah.roles import Candidate
from oompah.server import _integration_queue_summary
from oompah.terminal_audit import EvidenceFingerprint, TargetState
from tests.test_epic_strategy import (
    _make_issue,
    _make_orch,
    _make_project_record,
)


def test_parallel_mode_bypasses_same_epic_start_gate(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    orchestrator = _make_orch(tmp_path, projects=[project])
    orchestrator.config.parallel_epic_children_enabled = True
    sibling = _make_issue(
        identifier="TASK-1",
        parent_id="EPIC-1",
        project_id=project.id,
    )
    orchestrator.state.running[sibling.id] = RunningEntry(
        worker_task=MagicMock(),
        identifier=sibling.identifier,
        issue=sibling,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="default",
    )
    candidate = _make_issue(
        identifier="TASK-2",
        parent_id="EPIC-1",
        project_id=project.id,
    )
    orchestrator._reviews_cache = {}

    assert orchestrator._should_dispatch(candidate) is True


def test_integrated_queue_item_waits_for_terminal_audit():
    orchestrator = Orchestrator.__new__(Orchestrator)
    issue = Issue(
        id="native-task-uuid",
        identifier="TASK-1",
        title="Task",
        state="Ready to Integrate",
    )
    item = IntegrationQueueItem(
        project_id="project-1",
        epic_id="EPIC-1",
        task_id="TASK-1",
        task_branch="epic-EPIC-1--task-TASK-1",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="integrated",
        attempts=1,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:01:00+00:00",
    )

    satisfied = orchestrator._integration_satisfied_dependencies(
        [issue],
        [item],
    )

    assert satisfied == set()

    issue.state = "Done"
    satisfied = orchestrator._integration_satisfied_dependencies(
        [issue],
        [item],
    )
    assert satisfied == {"TASK-1", "native-task-uuid"}


def test_cross_epic_dependency_requires_reachable_integrated_head(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        project_id=project.id,
    )
    upstream = _make_issue(
        identifier="TASK-1",
        parent_id="EPIC-1",
        project_id=project.id,
        state="Done",
    )
    upstream.integration = IntegrationRecord(
        state="integrated",
        integrated_sha="a" * 40,
    )
    fetch = subprocess.CompletedProcess([], 0, stdout="", stderr="")
    unreachable = subprocess.CompletedProcess([], 1, stdout="", stderr="")
    reachable = subprocess.CompletedProcess([], 0, stdout="", stderr="")

    with patch(
        "oompah.orchestrator.subprocess.run",
        side_effect=[fetch, unreachable],
    ):
        assert (
            orchestrator._integration_satisfied_dependencies(
                [epic, upstream],
                [],
                project_id=project.id,
                epic_id=epic.identifier,
            )
            == set()
        )

    with patch(
        "oompah.orchestrator.subprocess.run",
        side_effect=[fetch, reachable],
    ):
        assert (
            orchestrator._integration_satisfied_dependencies(
                [epic, upstream],
                [],
                project_id=project.id,
                epic_id=epic.identifier,
            )
            == {upstream.id, upstream.identifier}
        )


def test_cross_epic_done_dependency_uses_default_after_parent_lands(
    tmp_path,
):
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        project_id=project.id,
    )
    upstream_parent = _make_issue(
        identifier="EPIC-1",
        issue_type="epic",
        project_id=project.id,
        state="Merged",
    )
    upstream = _make_issue(
        identifier="TASK-1",
        parent_id=upstream_parent.identifier,
        project_id=project.id,
        state="Done",
    )
    upstream.integration = IntegrationRecord(state="working")
    fetch = subprocess.CompletedProcess([], 0, stdout="", stderr="")
    unreachable = subprocess.CompletedProcess([], 1, stdout="", stderr="")
    reachable = subprocess.CompletedProcess([], 0, stdout="", stderr="")

    with patch(
        "oompah.orchestrator.subprocess.run",
        side_effect=[fetch, unreachable, unreachable],
    ):
        assert (
            orchestrator._integration_satisfied_dependencies(
                [epic, upstream_parent, upstream],
                [],
                project_id=project.id,
                epic_id=epic.identifier,
            )
            == set()
        )

    with patch(
        "oompah.orchestrator.subprocess.run",
        side_effect=[fetch, reachable, reachable],
    ):
        assert (
            orchestrator._integration_satisfied_dependencies(
                [epic, upstream_parent, upstream],
                [],
                project_id=project.id,
                epic_id=epic.identifier,
            )
            == {
                upstream_parent.id,
                upstream_parent.identifier,
                upstream.id,
                upstream.identifier,
            }
        )


@pytest.mark.parametrize("parent_state", [None, "In Progress", "Done"])
def test_cross_epic_done_dependency_rejects_unlanded_parent(
    tmp_path,
    parent_state,
):
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        project_id=project.id,
    )
    upstream = _make_issue(
        identifier="TASK-1",
        parent_id="EPIC-1",
        project_id=project.id,
        state="Done",
    )
    issues = [epic, upstream]
    if parent_state is not None:
        issues.append(
            _make_issue(
                identifier="EPIC-1",
                issue_type="epic",
                project_id=project.id,
                state=parent_state,
            )
        )

    with patch(
        "oompah.orchestrator.subprocess.run",
        return_value=subprocess.CompletedProcess(
            [],
            0,
            stdout="",
            stderr="",
        ),
    ):
        assert (
            orchestrator._integration_satisfied_dependencies(
                issues,
                [],
                project_id=project.id,
                epic_id=epic.identifier,
            )
            == set()
        )


@pytest.mark.parametrize(
    "upstream_state, parent_state",
    [("Merged", None), ("Done", "Merged")],
)
def test_stale_queue_files_one_authorized_epic_rebase(
    tmp_path,
    upstream_state,
    parent_state,
):
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        project_id=project.id,
    )
    upstream = _make_issue(
        identifier="TASK-1",
        parent_id="EPIC-1",
        project_id=project.id,
        state=upstream_state,
    )
    issues = [epic, upstream]
    if parent_state is not None:
        issues.append(
            _make_issue(
                identifier="EPIC-1",
                issue_type="epic",
                project_id=project.id,
                state=parent_state,
            )
        )
    queued = IntegrationQueueItem(
        project_id=project.id,
        epic_id=epic.identifier,
        task_id="TASK-2",
        task_branch="epic-EPIC-2--task-TASK-2",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
    )
    tracker = MagicMock()
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator._resolve_epic_target_branch = MagicMock(return_value="main")
    orchestrator._find_active_epic_rebase_sibling = MagicMock(
        return_value=None
    )
    orchestrator._file_rebase_task = MagicMock()
    orchestrator._set_epic_rebase_state = MagicMock()

    with patch(
        "oompah.orchestrator.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    ):
        repaired = (
            orchestrator._detect_and_repair_integration_queue_staleness_block(
                project_id=project.id,
                epic_id=epic.identifier,
                issues=issues,
                queue_items=[queued],
                dependency_map={"TASK-2": ("TASK-1",)},
                satisfied=set(),
            )
        )

    assert repaired is True
    tracker.update_issue.assert_called_once_with(
        epic.identifier,
        **{"add-label": "rebase-requested"},
    )
    assert "rebase-requested" in epic.labels
    orchestrator._file_rebase_task.assert_called_once_with(
        tracker,
        epic,
        "epic-EPIC-2",
        "main",
    )
    orchestrator._set_epic_rebase_state.assert_called_once_with(
        epic.identifier,
        EpicRebaseState.REBASING,
        project_id=project.id,
        reason="queue_staleness_block",
    )


def test_stale_queue_reuses_active_rebase_and_obeys_cooldown(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        project_id=project.id,
        labels=["rebase-requested"],
    )
    upstream = _make_issue(
        identifier="TASK-1",
        parent_id="EPIC-1",
        project_id=project.id,
        state="Archived",
    )
    queued = IntegrationQueueItem(
        project_id=project.id,
        epic_id=epic.identifier,
        task_id="TASK-2",
        task_branch="epic-EPIC-2--task-TASK-2",
        head_sha="a" * 40,
        base_sha=None,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
    )
    active_rebase = _make_issue(
        identifier="TASK-REBASE",
        parent_id=epic.identifier,
        project_id=project.id,
        state="Needs Rebase",
    )
    tracker = MagicMock()
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator._resolve_epic_target_branch = MagicMock(return_value="main")
    orchestrator._find_active_epic_rebase_sibling = MagicMock(
        return_value=active_rebase
    )
    orchestrator._file_rebase_task = MagicMock()
    orchestrator._set_epic_rebase_state = MagicMock()

    def detect() -> bool:
        return orchestrator._detect_and_repair_integration_queue_staleness_block(
            project_id=project.id,
            epic_id=epic.identifier,
            issues=[epic, upstream],
            queue_items=[queued],
            dependency_map={"TASK-2": ("TASK-1",)},
            satisfied=set(),
        )

    with patch(
        "oompah.orchestrator.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    ), patch("oompah.orchestrator.time.monotonic", return_value=100.0):
        assert detect() is True
        assert detect() is False

    tracker.update_issue.assert_not_called()
    orchestrator._file_rebase_task.assert_not_called()
    orchestrator._set_epic_rebase_state.assert_called_once()


def test_stale_queue_repair_survives_low_monotonic_clock(tmp_path):
    """Regression: cooldown default must not gate the first repair.

    On a freshly booted VM (e.g. a GitHub Actions runner), ``time.monotonic()``
    can return a value smaller than the 600s cooldown window. The default for
    the per-epic ``_epic_rebase_filed_at`` timestamp must therefore be
    ``float("-inf")`` (matching the other cooldown site in the orchestrator),
    otherwise ``now - 0 < 600`` erroneously blocks the very first repair.
    """
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        project_id=project.id,
    )
    upstream = _make_issue(
        identifier="TASK-1",
        parent_id="EPIC-1",
        project_id=project.id,
        state="Merged",
    )
    queued = IntegrationQueueItem(
        project_id=project.id,
        epic_id=epic.identifier,
        task_id="TASK-2",
        task_branch="epic-EPIC-2--task-TASK-2",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
    )
    tracker = MagicMock()
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator._resolve_epic_target_branch = MagicMock(return_value="main")
    orchestrator._find_active_epic_rebase_sibling = MagicMock(
        return_value=None
    )
    orchestrator._file_rebase_task = MagicMock()
    orchestrator._set_epic_rebase_state = MagicMock()

    # Simulate a fresh VM whose monotonic clock is well under the 600s cooldown.
    with patch(
        "oompah.orchestrator.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    ), patch(
        "oompah.orchestrator.time.monotonic",
        return_value=42.0,
    ):
        repaired = (
            orchestrator._detect_and_repair_integration_queue_staleness_block(
                project_id=project.id,
                epic_id=epic.identifier,
                issues=[epic, upstream],
                queue_items=[queued],
                dependency_map={"TASK-2": ("TASK-1",)},
                satisfied=set(),
            )
        )

    assert repaired is True
    orchestrator._file_rebase_task.assert_called_once()
    orchestrator._set_epic_rebase_state.assert_called_once()


def test_done_dependency_not_on_target_does_not_schedule_useless_rebase(
    tmp_path,
):
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        project_id=project.id,
    )
    upstream = _make_issue(
        identifier="TASK-1",
        parent_id="EPIC-1",
        project_id=project.id,
        state="Done",
    )
    upstream.integration = IntegrationRecord(
        state="integrated",
        integrated_sha="c" * 40,
    )
    queued = IntegrationQueueItem(
        project_id=project.id,
        epic_id=epic.identifier,
        task_id="TASK-2",
        task_branch="epic-EPIC-2--task-TASK-2",
        head_sha="a" * 40,
        base_sha=None,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
    )
    orchestrator._resolve_epic_target_branch = MagicMock(return_value="main")
    fetch = subprocess.CompletedProcess([], 0, stdout="", stderr="")
    absent_from_target = subprocess.CompletedProcess(
        [], 1, stdout="", stderr=""
    )

    with patch(
        "oompah.orchestrator.subprocess.run",
        side_effect=[fetch, absent_from_target],
    ):
        repaired = (
            orchestrator._detect_and_repair_integration_queue_staleness_block(
                project_id=project.id,
                epic_id=epic.identifier,
                issues=[epic, upstream],
                queue_items=[queued],
                dependency_map={"TASK-2": ("TASK-1",)},
                satisfied=set(),
            )
        )

    assert repaired is False


def test_integration_queue_summary_explains_finish_dependency_wait():
    blocker = Issue(
        id="dep-uuid",
        identifier="TASK-1",
        title="Dependency",
        state="In Progress",
    )
    task = Issue(
        id="task-uuid",
        identifier="TASK-2",
        title="Dependent",
        state="Ready to Integrate",
        blocked_by=[BlockerRef(id=blocker.id, identifier=blocker.identifier)],
    )
    item = IntegrationQueueItem(
        project_id="project-1",
        epic_id="EPIC-1",
        task_id=task.identifier,
        task_branch="epic-EPIC-1--task-TASK-2",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
    )

    summary = _integration_queue_summary(item, task, [task, blocker])

    assert summary["waiting_on"] == ["TASK-1"]
    assert summary["wait_reason"] == (
        "Waiting for finish dependencies to pass terminal audit: TASK-1"
    )


def test_integration_queue_summary_surfaces_failure_retry_and_repair_action():
    task = Issue(
        id="task-uuid",
        identifier="TASK-2",
        title="Poisoned task",
        state="Ready to Integrate",
    )
    item = IntegrationQueueItem(
        project_id="project-1",
        epic_id="EPIC-1",
        task_id=task.identifier,
        task_branch="epic-EPIC-1--task-TASK-2",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=3,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
        last_error="submitted task head tracks Oompah-generated worktree helper: `"
        ".oompah-no-hooks/prepare-commit-msg`",
        next_retry_at=2_000_000_000,
    )

    summary = _integration_queue_summary(item, task, [task])

    assert summary["failing_step"] == "generated-helper validation"
    assert "Next retry at" in summary["wait_reason"]
    assert "git rm" in summary["repair_action"]


def test_integration_queue_summary_accepts_done_child_of_landed_parent():
    upstream_parent = Issue(
        id="upstream-epic-uuid",
        identifier="EPIC-1",
        title="Upstream epic",
        state="Merged",
        issue_type="epic",
    )
    blocker = Issue(
        id="dep-uuid",
        identifier="TASK-1",
        title="Dependency",
        state="Done",
        parent_id=upstream_parent.identifier,
    )
    target_parent = Issue(
        id="target-epic-uuid",
        identifier="EPIC-2",
        title="Target epic",
        state="In Progress",
        issue_type="epic",
    )
    task = Issue(
        id="task-uuid",
        identifier="TASK-2",
        title="Dependent",
        state="Ready to Integrate",
        parent_id=target_parent.identifier,
        blocked_by=[BlockerRef(id=blocker.id, identifier=blocker.identifier)],
    )
    item = IntegrationQueueItem(
        project_id="project-1",
        epic_id=target_parent.identifier,
        task_id=task.identifier,
        task_branch="epic-EPIC-2--task-TASK-2",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
    )

    summary = _integration_queue_summary(
        item,
        task,
        [task, target_parent, blocker, upstream_parent],
    )

    assert summary["waiting_on"] == []
    assert summary["wait_reason"] == "Waiting for the per-epic integration executor"


def test_integration_queue_summary_rejects_done_child_of_unlanded_parent():
    upstream_parent = Issue(
        id="upstream-epic-uuid",
        identifier="EPIC-1",
        title="Upstream epic",
        state="In Progress",
        issue_type="epic",
    )
    blocker = Issue(
        id="dep-uuid",
        identifier="TASK-1",
        title="Dependency",
        state="Done",
        parent_id=upstream_parent.identifier,
    )
    task = Issue(
        id="task-uuid",
        identifier="TASK-2",
        title="Dependent",
        state="Ready to Integrate",
        parent_id="EPIC-2",
        blocked_by=[BlockerRef(id=blocker.id, identifier=blocker.identifier)],
    )
    item = IntegrationQueueItem(
        project_id="project-1",
        epic_id="EPIC-2",
        task_id=task.identifier,
        task_branch="epic-EPIC-2--task-TASK-2",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
    )

    summary = _integration_queue_summary(
        item,
        task,
        [task, blocker, upstream_parent],
    )

    assert summary["waiting_on"] == ["TASK-1"]
    assert summary["wait_reason"] == (
        "Waiting for upstream dependency code to reach this epic branch: TASK-1"
    )


def test_dashboard_shows_queue_wait_reason_and_dependency_semantics():
    html = (
        Path(__file__).resolve().parents[1]
        / "oompah"
        / "templates"
        / "dashboard.html"
    ).read_text(encoding="utf-8")

    assert "renderIntegrationSummary(issue.integration, issue.integration_queue)" in html
    assert "source.wait_reason" in html
    assert "Must finish after:" in html
    assert "Cannot start until:" in html


def test_parallel_workspace_persists_private_branch_and_integration_record(
    tmp_path,
):
    project = _make_project_record(epic_strategy="shared")
    orchestrator = _make_orch(tmp_path, projects=[project])
    orchestrator.config.parallel_epic_children_enabled = True
    orchestrator.project_store.prepare_epic_branch_for_private_dispatch.return_value = (
        "/wt/epic",
        "a" * 40,
    )
    orchestrator.project_store.create_worktree.return_value = "/wt/private"
    orchestrator.project_store.epic_child_branch_name.return_value = (
        "epic-EPIC-1--task-TASK-1"
    )
    epic = _make_issue(
        identifier="EPIC-1",
        issue_type="epic",
        project_id=project.id,
    )
    child = _make_issue(
        identifier="TASK-1",
        parent_id=epic.identifier,
        project_id=project.id,
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = epic
    with patch.object(orchestrator, "_tracker_for_issue", return_value=tracker):
        workspace, shared_epic = orchestrator._create_workspace_for_issue(
            child
        )

    assert workspace == "/wt/private"
    assert shared_epic is None
    assert child.work_branch == "epic-EPIC-1--task-TASK-1"
    orchestrator.project_store.create_worktree.assert_called_once_with(
        project.id,
        child.identifier,
        base_branch="epic-EPIC-1",
        branch_name="epic-EPIC-1--task-TASK-1",
    )
    metadata_calls = tracker.set_metadata_field.call_args_list
    assert metadata_calls[0].args == (
        child.identifier,
        "oompah.work_branch",
        "epic-EPIC-1--task-TASK-1",
    )
    record = metadata_calls[1].args[2]
    assert record["state"] == "working"
    assert record["base_sha"] == "a" * 40


def test_parallel_auditor_workspace_preserves_integrated_metadata(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    orchestrator = _make_orch(tmp_path, projects=[project])
    orchestrator.config.parallel_epic_children_enabled = True
    orchestrator.project_store.prepare_epic_branch_for_private_dispatch.return_value = (
        "/wt/epic",
        "a" * 40,
    )
    orchestrator.project_store.create_worktree.return_value = "/wt/private"
    orchestrator.project_store.epic_child_branch_name.return_value = (
        "epic-EPIC-1--task-TASK-1"
    )
    epic = _make_issue(
        identifier="EPIC-1",
        issue_type="epic",
        project_id=project.id,
    )
    child = _make_issue(
        identifier="TASK-1",
        parent_id=epic.identifier,
        project_id=project.id,
        state="In Validation",
    )
    child.integration = IntegrationRecord(
        state="integrated",
        task_branch="epic-EPIC-1--task-TASK-1",
        base_branch="epic-EPIC-1",
        base_sha="9" * 40,
        head_sha="b" * 40,
        integrated_sha="c" * 40,
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = epic

    with patch.object(orchestrator, "_tracker_for_issue", return_value=tracker):
        workspace, shared_epic = orchestrator._create_workspace_for_issue(
            child,
            persist_dispatch_metadata=False,
        )

    assert workspace == "/wt/private"
    assert shared_epic is None
    assert child.work_branch == "epic-EPIC-1--task-TASK-1"
    orchestrator.project_store.create_worktree.assert_called_once_with(
        project.id,
        child.identifier,
        base_branch="epic-EPIC-1",
        branch_name="epic-EPIC-1--task-TASK-1",
    )
    tracker.set_metadata_field.assert_not_called()
    assert child.integration.state == "integrated"
    assert child.integration.integrated_sha == "c" * 40


def _audit_plan(
    *,
    target: TargetState = TargetState.ARCHIVED,
    previous_state: str | None = "Merged",
) -> AuditDispatchPlan:
    return AuditDispatchPlan(
        audit_id="audit-1",
        attempt_id="attempt-1",
        target_state=target,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        candidate=Candidate("provider-1", "model-1"),
        rotation_count=0,
        branch_key="epic-EPIC-1",
        created_at="2026-07-31T00:00:00+00:00",
        previous_state=previous_state,
    )


def test_auditor_uses_detached_integrated_revision_not_epic_branch(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    orchestrator = _make_orch(tmp_path, projects=[project])
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.create_detached_audit_worktree.return_value = (
        "/wt/audit",
        "c" * 40,
    )
    child = _make_issue(
        identifier="TASK-1",
        parent_id="EPIC-1",
        project_id=project.id,
        state="In Validation",
    )
    child.work_branch = "epic-EPIC-1"
    child.integration = IntegrationRecord(
        state="integrated",
        task_branch="epic-EPIC-1--task-TASK-1",
        head_sha="b" * 40,
        integrated_sha="c" * 40,
    )

    workspace = orchestrator._create_workspace_for_auditor(
        child,
        _audit_plan(target=TargetState.DONE, previous_state="Ready to Integrate"),
    )

    assert workspace == "/wt/audit"
    orchestrator.project_store.create_detached_audit_worktree.assert_called_once_with(
        project.id,
        "TASK-1--terminal-audit-attempt-1",
        "c" * 40,
    )
    orchestrator.project_store.create_worktree.assert_not_called()
    orchestrator.project_store.prepare_epic_branch_for_private_dispatch.assert_not_called()


def test_archived_auditor_falls_back_to_default_when_merged_branch_deleted(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    project.default_branch = "main"
    orchestrator = _make_orch(tmp_path, projects=[project])
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.create_detached_audit_worktree.side_effect = [
        ProjectError(
            "terminal audit revision is unavailable: origin/epic-EPIC-OLD"
        ),
        ("/wt/audit", "d" * 40),
    ]
    child = _make_issue(
        identifier="TASK-1",
        project_id=project.id,
        state="Needs Human",
    )
    child.work_branch = "epic-EPIC-OLD"

    workspace = orchestrator._create_workspace_for_auditor(child, _audit_plan())

    assert workspace == "/wt/audit"
    revisions = [
        call.args[2]
        for call in orchestrator.project_store.create_detached_audit_worktree.call_args_list
    ]
    assert revisions == ["origin/epic-EPIC-OLD", "origin/main"]


def test_archived_auditor_fails_closed_without_merged_evidence(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    orchestrator = _make_orch(tmp_path, projects=[project])
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.create_detached_audit_worktree.side_effect = ProjectError(
        "terminal audit revision is unavailable: origin/epic-EPIC-OLD"
    )
    child = _make_issue(identifier="TASK-1", project_id=project.id)
    child.work_branch = "epic-EPIC-OLD"

    with pytest.raises(ProjectError, match="no safely resolvable revision"):
        orchestrator._create_workspace_for_auditor(
            child,
            _audit_plan(previous_state="Done"),
        )

    revisions = [
        call.args[2]
        for call in orchestrator.project_store.create_detached_audit_worktree.call_args_list
    ]
    assert revisions == ["origin/epic-EPIC-OLD"]


def test_auditor_never_substitutes_default_for_unreachable_immutable_head(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    orchestrator = _make_orch(tmp_path, projects=[project])
    orchestrator.project_store.get.return_value = project
    orchestrator.project_store.create_detached_audit_worktree.side_effect = ProjectError(
        f"terminal audit revision is unavailable: {'c' * 40}"
    )
    child = _make_issue(identifier="TASK-1", project_id=project.id)
    child.work_branch = "epic-EPIC-OLD"
    child.integration = IntegrationRecord(
        state="integrated",
        integrated_sha="c" * 40,
    )

    with pytest.raises(ProjectError, match="no safely resolvable revision"):
        orchestrator._create_workspace_for_auditor(child, _audit_plan())

    revisions = [
        call.args[2]
        for call in orchestrator.project_store.create_detached_audit_worktree.call_args_list
    ]
    assert revisions == ["c" * 40]


def test_epic_head_race_requeues_the_rebased_remote_head(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    orchestrator = _make_orch(tmp_path, projects=[project])
    queued = orchestrator.integration_queue.enqueue(
        project_id=project.id,
        epic_id="EPIC-1",
        task_id="TASK-1",
        task_branch="epic-EPIC-1--task-TASK-1",
        head_sha="a" * 40,
        priority=1,
    )
    claimed = orchestrator.integration_queue.claim_next(
        project_id=project.id,
        epic_id="EPIC-1",
        lease_owner="lease-1",
        dependency_map={"TASK-1": ()},
        satisfied=set(),
    )
    assert queued.state == "ready"
    assert claimed is not None
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        state="Ready to Integrate",
        integration=IntegrationRecord(
            state="ready",
            task_branch=claimed.task_branch,
            head_sha=claimed.head_sha,
        ),
    )
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)

    orchestrator._route_integration_failure(
        claimed,
        IntegrationExecutionResult(
            status="epic_head_race",
            message="epic advanced",
            expected_epic_sha="b" * 40,
            rebased_task_sha="c" * 40,
        ),
    )

    refreshed = orchestrator.integration_queue.items(
        project_id=project.id,
        epic_id="EPIC-1",
    )[0]
    assert refreshed.state == "ready"
    assert refreshed.head_sha == "c" * 40
    assert refreshed.next_retry_at is not None
    diagnostic = next(
        alert
        for alert in orchestrator._alerts
        if alert["source"] == f"integration_retry:{project.id}:TASK-1"
    )
    assert diagnostic["task_id"] == "TASK-1"
    assert diagnostic["failing_step"] == "epic compare-and-swap"
    assert diagnostic["next_retry_at"] is not None
    assert "wait for the scheduled retry" in diagnostic["repair_action"]


def test_interrupted_quality_gate_requeues_the_rebased_remote_head(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    orchestrator = _make_orch(tmp_path, projects=[project])
    orchestrator.integration_queue.enqueue(
        project_id=project.id,
        epic_id="EPIC-1",
        task_id="TASK-1",
        task_branch="epic-EPIC-1--task-TASK-1",
        head_sha="a" * 40,
        priority=1,
    )
    claimed = orchestrator.integration_queue.claim_next(
        project_id=project.id,
        epic_id="EPIC-1",
        lease_owner="lease-1",
        dependency_map={"TASK-1": ()},
        satisfied=set(),
    )
    assert claimed is not None
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        state="Ready to Integrate",
        integration=IntegrationRecord(
            state="ready",
            task_branch=claimed.task_branch,
            head_sha=claimed.head_sha,
        ),
    )
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)

    orchestrator._route_integration_failure(
        claimed,
        IntegrationExecutionResult(
            status="interrupted",
            message="quality gate interrupted by shutdown",
            expected_epic_sha="b" * 40,
            rebased_task_sha="c" * 40,
        ),
    )

    refreshed = orchestrator.integration_queue.items(
        project_id=project.id,
        epic_id="EPIC-1",
    )[0]
    assert refreshed.state == "ready"
    assert refreshed.head_sha == "c" * 40
    metadata = tracker.set_metadata_field.call_args.args[2]
    assert metadata["state"] == "ready"


def test_needs_rebase_quality_gate_routes_task_to_rebase_repair(tmp_path):
    project = _make_project_record(epic_strategy="shared")
    orchestrator = _make_orch(tmp_path, projects=[project])
    orchestrator.integration_queue.enqueue(
        project_id=project.id,
        epic_id="EPIC-1",
        task_id="TASK-1",
        task_branch="epic-EPIC-1--task-TASK-1",
        head_sha="a" * 40,
        priority=1,
    )
    claimed = orchestrator.integration_queue.claim_next(
        project_id=project.id,
        epic_id="EPIC-1",
        lease_owner="lease-1",
        dependency_map={"TASK-1": ()},
        satisfied=set(),
    )
    assert claimed is not None
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Task",
        state="Ready to Integrate",
        integration=IntegrationRecord(
            state="ready",
            task_branch=claimed.task_branch,
            head_sha=claimed.head_sha,
        ),
    )
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)

    orchestrator._route_integration_failure(
        claimed,
        IntegrationExecutionResult(
            status="needs_rebase",
            message="lifecycle safety prerequisite is missing",
            expected_epic_sha="b" * 40,
            rebased_task_sha="c" * 40,
        ),
    )

    tracker.update_issue.assert_called_once_with(
        "TASK-1", status="Needs Rebase"
    )
    assert "rebase" in tracker.add_comment.call_args.args[1].lower()
    metadata = tracker.set_metadata_field.call_args.args[2]
    assert metadata["state"] == "blocked"


def test_project_store_deletes_only_derived_private_child_branch(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "clone", str(remote), str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
    )
    (repo / "base.txt").write_text("base\n")
    subprocess.run(["git", "-C", str(repo), "add", "base.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "base"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "branch", "-M", "main"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "push", "-u", "origin", "main"],
        check=True,
    )
    branch = "epic-EPIC-1--task-TASK-1"
    subprocess.run(
        ["git", "-C", str(repo), "branch", branch],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "push", "origin", branch],
        check=True,
    )
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    store._projects["p1"] = Project(
        id="p1",
        name="project",
        repo_url=str(remote),
        repo_path=str(repo),
    )

    assert store.delete_epic_child_branch(
        "p1",
        "EPIC-1",
        "TASK-1",
    )
    remote_ref = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "ls-remote",
            "--heads",
            "origin",
            branch,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    local_ref = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
        ],
        check=False,
    )
    assert remote_ref.stdout == ""
    assert local_ref.returncode != 0


def test_private_dispatch_fast_forwards_clean_epic_to_latest_remote(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    peer = tmp_path / "peer"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "clone", str(remote), str(repo)], check=True)
    for checkout in (repo,):
        subprocess.run(
            ["git", "-C", str(checkout), "config", "user.name", "Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(checkout), "config", "user.email", "test@example.com"],
            check=True,
        )
    (repo / "base.txt").write_text("base\n")
    subprocess.run(["git", "-C", str(repo), "add", "base.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True)
    subprocess.run(["git", "-C", str(repo), "branch", "-M", "main"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "push", "-u", "origin", "main"],
        check=True,
    )
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    store._projects["p1"] = Project(
        id="p1",
        name="project",
        repo_url=str(remote),
        repo_path=str(repo),
        default_branch="main",
    )
    _, initial = store.prepare_epic_branch_for_private_dispatch(
        "p1", "EPIC-1"
    )

    subprocess.run(["git", "clone", str(remote), str(peer)], check=True)
    subprocess.run(
        ["git", "-C", str(peer), "config", "user.name", "Peer"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(peer), "config", "user.email", "peer@example.com"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(peer),
            "checkout",
            "-b",
            "epic-EPIC-1",
            "origin/epic-EPIC-1",
        ],
        check=True,
    )
    (peer / "peer.txt").write_text("newer\n")
    subprocess.run(["git", "-C", str(peer), "add", "peer.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(peer), "commit", "-m", "remote advance"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(peer), "push", "origin", "epic-EPIC-1"],
        check=True,
    )
    remote_head = subprocess.run(
        ["git", "-C", str(peer), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert remote_head != initial

    epic_worktree, synchronized = (
        store.prepare_epic_branch_for_private_dispatch("p1", "EPIC-1")
    )

    assert synchronized == remote_head
    assert (
        subprocess.run(
            ["git", "-C", epic_worktree, "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == remote_head
    )


def test_nested_epic_queue_repair_with_parent_target(tmp_path):
    """Nested epic with parent epic target can repair stale integration queue.
    
    When a nested epic (EPIC-2) has a parent epic (EPIC-1) with a terminal
    sibling dependency, the queue repair should be triggered for EPIC-2
    targeting EPIC-1's branch (epic-EPIC-1).
    """
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    
    # Create parent epic
    parent_epic = _make_issue(
        identifier="EPIC-1",
        issue_type="epic",
        project_id=project.id,
        state="Merged",
    )
    
    # Create nested epic with parent
    nested_epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        parent_id=parent_epic.identifier,
        project_id=project.id,
    )
    
    # Create a task in parent that's terminal (sibling dependency)
    upstream_task = _make_issue(
        identifier="TASK-1",
        parent_id=parent_epic.identifier,
        project_id=project.id,
        state="Merged",
    )
    
    # Queue item for nested epic's child
    queued = IntegrationQueueItem(
        project_id=project.id,
        epic_id=nested_epic.identifier,
        task_id="TASK-2",
        task_branch="epic-EPIC-2--task-TASK-2",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
    )
    
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = parent_epic
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator._tracker_for_issue = MagicMock(return_value=tracker)
    orchestrator._find_active_epic_rebase_sibling = MagicMock(
        return_value=None
    )
    orchestrator._file_rebase_task = MagicMock()
    orchestrator._set_epic_rebase_state = MagicMock()

    with patch(
        "oompah.orchestrator.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    ):
        repaired = (
            orchestrator._detect_and_repair_integration_queue_staleness_block(
                project_id=project.id,
                epic_id=nested_epic.identifier,
                issues=[nested_epic, parent_epic, upstream_task],
                queue_items=[queued],
                dependency_map={"TASK-2": ("TASK-1",)},
                satisfied=set(),
            )
        )

    # Should repair: nested epic targets parent epic branch
    assert repaired is True
    
    # Should file rebase with parent epic's branch as target
    parent_branch = orchestrator.project_store.epic_branch_name(parent_epic.identifier)
    orchestrator._file_rebase_task.assert_called_once_with(
        tracker,
        nested_epic,
        "epic-EPIC-2",
        parent_branch,
    )


def test_nested_epic_queue_repair_denies_unrelated_epic_target(tmp_path):
    """Nested epic queue repair denies unrelated epic branches.
    
    When a nested epic's target is an unrelated epic (not its parent),
    the queue repair should be denied. Tests that parent resolution is
    properly wired: EPIC-2 resolves to parent EPIC-P with branch epic-EPIC-P,
    but target_branch is epic-EPIC-X (an unrelated epic), so repair denied.
    """
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    
    # Create proper parent epic
    parent_epic = _make_issue(
        identifier="EPIC-P",
        issue_type="epic",
        project_id=project.id,
    )
    
    # Create nested epic with parent EPIC-P
    nested_epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        parent_id=parent_epic.identifier,
        project_id=project.id,
    )
    
    # Create unrelated epic
    unrelated_epic = _make_issue(
        identifier="EPIC-X",
        issue_type="epic",
        project_id=project.id,
    )
    
    # Queue item for nested epic's child
    queued = IntegrationQueueItem(
        project_id=project.id,
        epic_id=nested_epic.identifier,
        task_id="TASK-2",
        task_branch="epic-EPIC-2--task-TASK-2",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
    )
    
    # Create upstream task that's terminal
    upstream_task = _make_issue(
        identifier="TASK-1",
        parent_id=parent_epic.identifier,
        project_id=project.id,
        state="Merged",
    )
    
    # Properly mock _resolve_parent_epic to return the parent epic
    orchestrator._resolve_parent_epic = MagicMock(return_value=parent_epic)
    # Mock _resolve_epic_target_branch to return unrelated epic branch
    orchestrator._resolve_epic_target_branch = MagicMock(
        return_value="epic-EPIC-X"
    )

    with patch(
        "oompah.orchestrator.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    ):
        repaired = (
            orchestrator._detect_and_repair_integration_queue_staleness_block(
                project_id=project.id,
                epic_id=nested_epic.identifier,
                issues=[nested_epic, parent_epic, unrelated_epic, upstream_task],
                queue_items=[queued],
                dependency_map={"TASK-2": ("TASK-1",)},
                satisfied=set(),
            )
        )

    # Should NOT repair: target is unrelated epic, not the parent
    assert repaired is False


def test_nested_epic_queue_repair_skips_already_reachable_nonterminal_dependencies(
    tmp_path,
):
    """Queue repair is not triggered for nonterminal dependencies on target.
    
    When a nested epic's dependency is already reachable from the target
    branch but not in a terminal state (not Merged/Done/Archived),
    the queue repair should not be triggered since the dependency may
    still change.
    """
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    
    # Create parent epic
    parent_epic = _make_issue(
        identifier="EPIC-1",
        issue_type="epic",
        project_id=project.id,
        state="In Progress",
    )
    
    # Create nested epic
    nested_epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        parent_id=parent_epic.identifier,
        project_id=project.id,
    )
    
    # Create dependency that's In Progress (nonterminal) but already on target
    upstream_task = _make_issue(
        identifier="TASK-1",
        parent_id=parent_epic.identifier,
        project_id=project.id,
        state="In Progress",  # Nonterminal state
    )
    
    # Queue item for nested epic's child
    queued = IntegrationQueueItem(
        project_id=project.id,
        epic_id=nested_epic.identifier,
        task_id="TASK-2",
        task_branch="epic-EPIC-2--task-TASK-2",
        head_sha="a" * 40,
        base_sha="b" * 40,
        priority=1,
        submitted_at="2026-07-29T00:00:00+00:00",
        state="ready",
        attempts=0,
        lease_owner=None,
        lease_expires_at=None,
        updated_at="2026-07-29T00:00:00+00:00",
    )
    
    tracker = MagicMock()
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator._resolve_parent_epic = MagicMock(return_value=parent_epic)
    
    # Simulate dependency already on target (ancestor check returns 0)
    ancestor_check = subprocess.CompletedProcess(
        [], 0, stdout="", stderr=""
    )
    
    with patch(
        "oompah.orchestrator.subprocess.run",
        return_value=ancestor_check,
    ):
        repaired = (
            orchestrator._detect_and_repair_integration_queue_staleness_block(
                project_id=project.id,
                epic_id=nested_epic.identifier,
                issues=[nested_epic, parent_epic, upstream_task],
                queue_items=[queued],
                dependency_map={"TASK-2": ("TASK-1",)},
                satisfied=set(),
            )
        )
    
    # Should NOT repair: nonterminal dependency means we wait for it to finish
    assert repaired is False


def test_nested_epic_queue_repair_with_successful_parent_sync_allows_claim_next(
    tmp_path,
):
    """Successful parent epic sync lets claim_next work on nested epic queue.
    
    When a parent epic's rebase completes successfully and the dependency
    becomes reachable, the nested epic's claim_next should be able to
    advance past the stale queue item.
    """
    project = _make_project_record(epic_strategy="shared")
    project.repo_path = str(tmp_path)
    orchestrator = _make_orch(tmp_path, projects=[project])
    
    # Create parent epic with terminal status
    parent_epic = _make_issue(
        identifier="EPIC-1",
        issue_type="epic",
        project_id=project.id,
        state="Merged",  # Parent is landed
    )
    
    # Create nested epic
    nested_epic = _make_issue(
        identifier="EPIC-2",
        issue_type="epic",
        parent_id=parent_epic.identifier,
        project_id=project.id,
    )
    
    # Create terminal dependency (merged sibling)
    upstream_task = _make_issue(
        identifier="TASK-1",
        parent_id=parent_epic.identifier,
        project_id=project.id,
        state="Merged",
    )
    upstream_task.integration = IntegrationRecord(
        state="integrated",
        integrated_sha="d" * 40,
    )
    
    tracker = MagicMock()
    orchestrator._tracker_for_project = MagicMock(return_value=tracker)
    orchestrator._tracker_for_issue = MagicMock(return_value=tracker)
    orchestrator._resolve_parent_epic = MagicMock(return_value=parent_epic)
    orchestrator._find_active_epic_rebase_sibling = MagicMock(
        return_value=None
    )
    orchestrator._file_rebase_task = MagicMock()
    orchestrator._set_epic_rebase_state = MagicMock()

    # Enqueue queue item for nested epic's child with dependency
    queued = orchestrator.integration_queue.enqueue(
        project_id=project.id,
        epic_id=nested_epic.identifier,
        task_id="TASK-2",
        task_branch="epic-EPIC-2--task-TASK-2",
        head_sha="a" * 40,
        priority=1,
    )
    
    # Simulate successful ancestor check (dependency is reachable)
    with patch(
        "oompah.orchestrator.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    ):
        repaired = (
            orchestrator._detect_and_repair_integration_queue_staleness_block(
                project_id=project.id,
                epic_id=nested_epic.identifier,
                issues=[nested_epic, parent_epic, upstream_task],
                queue_items=[queued],
                dependency_map={"TASK-2": ("TASK-1",)},
                satisfied=set(),
            )
        )

    # Should repair: terminal dependency on parent epic
    assert repaired is True
    # Verify rebase was filed for the nested epic
    orchestrator._file_rebase_task.assert_called_once()
    orchestrator._set_epic_rebase_state.assert_called_once()
    
    # After successful parent sync, nested epic can advance
    # Verify claim_next can now proceed (queue state allows it)
    claimed = orchestrator.integration_queue.claim_next(
        project_id=project.id,
        epic_id=nested_epic.identifier,
        lease_owner="test-lease",
        dependency_map={"TASK-2": ("TASK-1",)},
        satisfied={"TASK-1"},  # After parent sync, dependency is satisfied
    )
    # Should be able to claim the item once dependency is satisfied
    assert claimed is not None
    assert claimed.task_id == "TASK-2"
