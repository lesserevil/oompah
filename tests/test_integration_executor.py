from __future__ import annotations

from contextlib import nullcontext
import subprocess
import time
from unittest import mock

from oompah.config import ServiceConfig
from oompah.integration import IntegrationRecord
from oompah.integration_executor import execute_integration
from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.quality_gate import BranchQualityGate, QualityGateResult
from oompah.statuses import READY_TO_INTEGRATE


def _git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _gate(state_path, repo_path):
    safety_head = _git(repo_path, "log", "--format=%H", "--grep=^OOMPAH-652: lifecycle isolation$", "-n", "1")
    return BranchQualityGate(str(state_path), safety_head=safety_head)


def _repo(tmp_path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "clone", str(remote), str(seed)], check=True)
    _git(seed, "config", "user.name", "Test")
    _git(seed, "config", "user.email", "test@example.com")
    
    # Create synthetic OOMPAH-652 safety head commit for testing
    (seed / "safety.txt").write_text("OOMPAH-652 safety head\n")
    _git(seed, "add", "safety.txt")
    _git(seed, "commit", "-m", "OOMPAH-652: lifecycle isolation")
    (seed / "base.txt").write_text("base\n")
    _git(seed, "add", "base.txt")
    _git(seed, "commit", "-m", "base")
    _git(seed, "branch", "-M", "main")
    _git(seed, "push", "-u", "origin", "main")
    _git(seed, "checkout", "-b", "epic-E-1")
    _git(seed, "push", "-u", "origin", "epic-E-1")
    _git(seed, "checkout", "-b", "epic-E-1--task-T-1")
    (seed / "task.txt").write_text("task\n")
    _git(seed, "add", "task.txt")
    _git(seed, "commit", "-m", "task")
    task_head = _git(seed, "rev-parse", "HEAD")
    _git(seed, "push", "-u", "origin", "epic-E-1--task-T-1")
    epic = tmp_path / "epic"
    task = tmp_path / "task"
    subprocess.run(
        ["git", "clone", "--branch", "epic-E-1", str(remote), str(epic)],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "clone",
            "--branch",
            "epic-E-1--task-T-1",
            str(remote),
            str(task),
        ],
        check=True,
    )
    for repo in (epic, task):
        _git(repo, "config", "user.name", "Test")
        _git(repo, "config", "user.email", "test@example.com")
    return remote, epic, task, task_head


def _lease_authority_harness(tmp_path, *, remote, task_branch, task_head):
    project = Project(
        id="project-1",
        name="Lease authority",
        repo_url=str(remote),
        repo_path=str(remote),
        default_branch="main",
    )
    issue = Issue(
        id="T-1",
        identifier="T-1",
        title="Lease authority task",
        state=READY_TO_INTEGRATE,
        parent_id="E-1",
        integration=IntegrationRecord(
            state="ready",
            task_branch=task_branch,
            head_sha=task_head,
        ),
    )
    tracker = mock.MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    project_store = mock.MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.side_effect = lambda project_id: (
        project if project_id == project.id else None
    )
    orchestrator = Orchestrator(
        config=ServiceConfig(),
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service-state.json"),
    )
    orchestrator._project_trackers[project.id] = tracker
    return orchestrator, project, issue


def _close_authority_harness(orchestrator):
    orchestrator.integration_queue.close()
    orchestrator.coordination_store.close()
    orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
    orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_executor_rebases_tests_and_fast_forwards_epic(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)
    gate_calls = {}

    class RecordingGate:
        def run(self, **kwargs):
            gate_calls.update(kwargs)
            return QualityGateResult(
                status="passed",
                head_sha=kwargs["expected_head_sha"],
                command=kwargs["command"],
            )

    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="epic-E-1--task-T-1",
        submitted_head_sha=task_head,
        quality_gate=RecordingGate(),
        quality_command="test -f task.txt",
        repo_identity=str(remote),
        gate_generation="integration-generation-1",
    )
    assert result.integrated
    assert _git(epic, "rev-parse", "HEAD") == result.integrated_sha
    assert _git(epic, "rev-parse", "origin/epic-E-1") == result.integrated_sha
    assert gate_calls["expected_head_sha"] == result.rebased_task_sha
    assert gate_calls["generation"] == "integration-generation-1"


def test_executor_preserves_rebased_task_when_quality_fails(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)
    gate = _gate(tmp_path / "quality.json", task)
    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="epic-E-1--task-T-1",
        submitted_head_sha=task_head,
        quality_gate=gate,
        quality_command="false",
        repo_identity=str(remote),
    )
    assert result.status == "ci_failure"
    assert result.rebased_task_sha
    assert _git(epic, "rev-parse", "HEAD") != result.rebased_task_sha


def test_executor_preserves_retryable_quality_gate_interruption(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)

    class InterruptedGate:
        def run(self, **_kwargs):
            return QualityGateResult(
                status="interrupted",
                head_sha=task_head,
                command="make test",
            )

    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="epic-E-1--task-T-1",
        submitted_head_sha=task_head,
        quality_gate=InterruptedGate(),
        quality_command="make test",
        repo_identity=str(remote),
    )

    assert result.status == "interrupted"
    assert result.rebased_task_sha
    assert _git(epic, "rev-parse", "HEAD") != result.rebased_task_sha


def test_executor_preserves_quality_gate_needs_rebase_status(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)

    class NeedsRebaseGate:
        def run(self, **_kwargs):
            return QualityGateResult(
                status="needs_rebase",
                head_sha=task_head,
                command="make test",
                output_tail="lifecycle safety prerequisite is missing",
            )

    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="epic-E-1--task-T-1",
        submitted_head_sha=task_head,
        quality_gate=NeedsRebaseGate(),
        quality_command="make test",
        repo_identity=str(remote),
    )

    assert result.status == "needs_rebase"
    assert result.quality is not None
    assert "safety prerequisite" in result.message
    assert _git(epic, "rev-parse", "origin/epic-E-1") != result.rebased_task_sha


def test_executor_rechecks_authority_after_gate_before_epic_push(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)
    original_epic_head = _git(epic, "rev-parse", "origin/epic-E-1")

    # The gate's run() now calls is_current() at two pre-spawn barriers
    # (before and after snapshot creation) in addition to the monitor thread
    # poll during execution.  Using a fixed iterator like iter((True, False))
    # is therefore fragile.  Instead we use a state flag that stays True until
    # the gate has returned its result, then flips to False, so the
    # authority check in execute_integration (before epic commit) fails.
    gate_completed = [False]

    def commit_allowed() -> bool:
        return not gate_completed[0]

    inner_gate = BranchQualityGate(str(tmp_path / "quality.json"))

    class _GateWrapper:
        """Flip the flag after the gate returns so post-gate check fails."""

        def run(self, **kwargs):
            result = inner_gate.run(**kwargs)
            # Signal that the gate has completed: all subsequent
            # commit_allowed() calls (the post-gate authority check in
            # execute_integration) should now return False.
            gate_completed[0] = True
            return result

    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="epic-E-1--task-T-1",
        submitted_head_sha=task_head,
        quality_gate=_GateWrapper(),
        quality_command="true",
        repo_identity=str(remote),
        commit_allowed=commit_allowed,
    )

    assert result.status == "cancelled"
    assert "before epic commit" in result.message
    assert _git(epic, "rev-parse", "origin/epic-E-1") == original_epic_head


def test_expired_lease_discards_stale_gate_pass_before_epic_commit(tmp_path):
    """Only the replacement lease may consume gate evidence and commit.

    The tracker record does not change when an expired integration lease is
    reclaimed.  The old executor must consequently lose its quality-gate
    authority before the epic push, even when its gate returns passed evidence.
    """

    remote, epic, task, task_head = _repo(tmp_path)
    original_epic_head = _git(epic, "rev-parse", "origin/epic-E-1")
    orchestrator, project, issue = _lease_authority_harness(
        tmp_path,
        remote=remote,
        task_branch="epic-E-1--task-T-1",
        task_head=task_head,
    )
    try:
        claimed_at = time.time()
        queued = orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id=issue.parent_id or "E-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        stale = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id=queued.epic_id,
            lease_owner="stale-generation",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
            lease_seconds=1,
            now=claimed_at,
        )
        assert stale is not None
        assert orchestrator._integration_task_still_ready(stale)

        replacement = []

        class ReclaimingGate:
            def run(self, **kwargs):
                assert kwargs["is_current"]()
                replacement_item = orchestrator.integration_queue.claim_next(
                    project_id=project.id,
                    epic_id=queued.epic_id,
                    lease_owner="replacement-generation",
                    dependency_map={issue.identifier: ()},
                    satisfied=set(),
                    now=claimed_at + 2,
                )
                assert replacement_item is not None
                replacement.append(replacement_item)
                assert not kwargs["is_current"]()
                return QualityGateResult(
                    status="passed",
                    head_sha=kwargs["expected_head_sha"],
                    command=kwargs["command"],
                )

        stale_result = execute_integration(
            project_lock=nullcontext(),
            epic_worktree=str(epic),
            task_worktree=str(task),
            epic_branch="epic-E-1",
            task_branch=issue.integration.task_branch,
            submitted_head_sha=task_head,
            quality_gate=ReclaimingGate(),
            quality_command="true",
            repo_identity=str(remote),
            gate_generation="stale-generation",
            commit_allowed=lambda: orchestrator._integration_task_still_ready(stale),
        )

        assert stale_result.status == "cancelled"
        assert "before epic commit" in stale_result.message
        assert _git(epic, "rev-parse", "origin/epic-E-1") == original_epic_head
        assert not orchestrator._integration_task_still_ready(stale)
        assert len(replacement) == 1
        assert orchestrator._integration_task_still_ready(replacement[0])

        class PassingGate:
            def run(self, **kwargs):
                assert kwargs["is_current"]()
                return QualityGateResult(
                    status="passed",
                    head_sha=kwargs["expected_head_sha"],
                    command=kwargs["command"],
                )

        replacement_result = execute_integration(
            project_lock=nullcontext(),
            epic_worktree=str(epic),
            task_worktree=str(task),
            epic_branch="epic-E-1",
            task_branch=issue.integration.task_branch,
            submitted_head_sha=task_head,
            quality_gate=PassingGate(),
            quality_command="true",
            repo_identity=str(remote),
            gate_generation="replacement-generation",
            commit_allowed=lambda: orchestrator._integration_task_still_ready(
                replacement[0]
            ),
        )

        assert replacement_result.integrated
        assert _git(epic, "rev-parse", "origin/epic-E-1") == (
            replacement_result.integrated_sha
        )
    finally:
        _close_authority_harness(orchestrator)


def test_executor_rejects_changed_remote_task_head(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)
    seed = tmp_path / "seed"
    (seed / "other.txt").write_text("other\n")
    _git(seed, "add", "other.txt")
    _git(seed, "commit", "-m", "other")
    _git(seed, "push", "origin", "epic-E-1--task-T-1")
    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="epic-E-1--task-T-1",
        submitted_head_sha=task_head,
        quality_gate=_gate(tmp_path / "quality.json", task),
        quality_command="true",
        repo_identity=str(remote),
    )
    assert result.status == "stale_head"


def test_executor_rejects_foreign_branch_without_moving_task_worktree(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)
    seed = tmp_path / "seed"
    foreign_branch = "epic-E-2--task-T-2"
    _git(seed, "branch", foreign_branch, task_head)
    _git(seed, "push", "origin", foreign_branch)
    original_branch = _git(task, "branch", "--show-current")
    original_head = _git(task, "rev-parse", "HEAD")
    original_task_ref = _git(task, "rev-parse", "epic-E-1--task-T-1")

    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch=foreign_branch,
        submitted_head_sha=task_head,
        quality_gate=_gate(tmp_path / "quality.json", task),
        quality_command="true",
        repo_identity=str(remote),
    )

    assert result.status == "wrong_worktree"
    assert "refusing to reset" in result.message
    assert _git(task, "branch", "--show-current") == original_branch
    assert _git(task, "rev-parse", "HEAD") == original_head
    assert _git(task, "rev-parse", "epic-E-1--task-T-1") == original_task_ref


def test_executor_refuses_stale_queue_branch_without_resetting_task_worktree(tmp_path):
    remote, epic, task, _task_head = _repo(tmp_path)
    original_branch = _git(task, "branch", "--show-current")
    original_head = _git(task, "rev-parse", "HEAD")
    main_head = _git(task, "rev-parse", "origin/main")

    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="main",
        submitted_head_sha=main_head,
        quality_gate=_gate(tmp_path / "quality.json", task),
        quality_command="true",
        repo_identity=str(remote),
    )

    assert result.status == "wrong_worktree"
    assert "refusing to reset" in result.message
    assert _git(task, "branch", "--show-current") == original_branch
    assert _git(task, "rev-parse", "HEAD") == original_head


def test_executor_refuses_dirty_task_worktree_before_reset(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)
    original = b"worker edits\x00\xff"
    (task / "task.txt").write_bytes(original)

    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="epic-E-1--task-T-1",
        submitted_head_sha=task_head,
        quality_gate=_gate(tmp_path / "quality.json", task),
        quality_command="true",
        repo_identity=str(remote),
    )

    assert result.status == "dirty_worktree"
    assert (task / "task.txt").read_bytes() == original
    assert _git(task, "rev-parse", "HEAD") == task_head


def test_executor_refuses_dirty_epic_worktree_before_reset(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)
    original = b"shared edits\x00\xfe"
    (epic / "base.txt").write_bytes(original)

    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="epic-E-1--task-T-1",
        submitted_head_sha=task_head,
        quality_gate=_gate(tmp_path / "quality.json", task),
        quality_command="true",
        repo_identity=str(remote),
    )

    assert result.status == "dirty_worktree"
    assert (epic / "base.txt").read_bytes() == original
