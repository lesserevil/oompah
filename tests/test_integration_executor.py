from __future__ import annotations

from contextlib import nullcontext
import subprocess

from oompah.integration_executor import execute_integration
from oompah.quality_gate import BranchQualityGate, QualityGateResult


def _git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo(tmp_path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True)
    subprocess.run(["git", "clone", str(remote), str(seed)], check=True)
    _git(seed, "config", "user.name", "Test")
    _git(seed, "config", "user.email", "test@example.com")
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


def test_executor_rebases_tests_and_fast_forwards_epic(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="epic-E-1--task-T-1",
        submitted_head_sha=task_head,
        quality_gate=gate,
        quality_command="test -f task.txt",
        repo_identity=str(remote),
    )
    assert result.integrated
    assert _git(epic, "rev-parse", "HEAD") == result.integrated_sha
    assert _git(epic, "rev-parse", "origin/epic-E-1") == result.integrated_sha


def test_executor_preserves_rebased_task_when_quality_fails(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
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


def test_executor_rechecks_authority_after_gate_before_epic_push(tmp_path):
    remote, epic, task, task_head = _repo(tmp_path)
    original_epic_head = _git(epic, "rev-parse", "origin/epic-E-1")
    checks = iter((True, False))

    result = execute_integration(
        project_lock=nullcontext(),
        epic_worktree=str(epic),
        task_worktree=str(task),
        epic_branch="epic-E-1",
        task_branch="epic-E-1--task-T-1",
        submitted_head_sha=task_head,
        quality_gate=BranchQualityGate(str(tmp_path / "quality.json")),
        quality_command="true",
        repo_identity=str(remote),
        commit_allowed=lambda: next(checks),
    )

    assert result.status == "cancelled"
    assert "before epic commit" in result.message
    assert _git(epic, "rev-parse", "origin/epic-E-1") == original_epic_head


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
        quality_gate=BranchQualityGate(str(tmp_path / "quality.json")),
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
        quality_gate=BranchQualityGate(str(tmp_path / "quality.json")),
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
        quality_gate=BranchQualityGate(str(tmp_path / "quality.json")),
        quality_command="true",
        repo_identity=str(remote),
    )

    assert result.status == "wrong_worktree"
    assert "refusing to reset" in result.message
    assert _git(task, "branch", "--show-current") == original_branch
    assert _git(task, "rev-parse", "HEAD") == original_head
