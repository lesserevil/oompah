from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

from oompah.integration import IntegrationRecord
from oompah.integration_executor import IntegrationExecutionResult
from oompah.integration_queue import IntegrationQueueItem
from oompah.models import (
    BlockerRef,
    EpicRebaseState,
    Issue,
    Project,
    RunningEntry,
)
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectStore
from oompah.server import _integration_queue_summary
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


def test_stale_queue_files_one_authorized_epic_rebase(tmp_path):
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

    with patch(
        "oompah.orchestrator.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
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
    ):
        assert detect() is True
        assert detect() is False

    tracker.update_issue.assert_not_called()
    orchestrator._file_rebase_task.assert_not_called()
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
