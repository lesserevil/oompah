from __future__ import annotations

import shlex
import subprocess
import threading
from unittest.mock import MagicMock

from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.quality_gate import BranchQualityGate


def _git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "oompah"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "lesserevil@users.noreply.github.com"],
        cwd=repo,
        check=True,
    )
    source = repo / "source.txt"
    source.write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "work"], cwd=repo, check=True)
    return repo


def _run(gate, repo, command, **overrides):
    args = {
        "repo_path": str(repo),
        "repo_identity": "https://example.test/org/repo",
        "target_branch": "main",
        "work_branch": "work",
        "command": command,
    }
    args.update(overrides)
    return gate.run(**args)


def test_passing_head_is_cached_and_survives_restart(tmp_path):
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    command = f"printf x >> {shlex.quote(str(counter))}"
    state = tmp_path / "quality.json"

    first = _run(BranchQualityGate(str(state)), repo, command)
    second = _run(BranchQualityGate(str(state)), repo, command)

    assert first.passed and not first.cached
    assert second.passed and second.cached
    assert counter.read_text(encoding="utf-8") == "x"


def test_new_head_command_or_target_invalidates_pass(tmp_path):
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    state = tmp_path / "quality.json"
    command = f"printf x >> {shlex.quote(str(counter))}"
    gate = BranchQualityGate(str(state))

    assert _run(gate, repo, command).passed
    assert _run(gate, repo, command, target_branch="release/1").passed
    assert _run(gate, repo, f"{command}; true").passed

    (repo / "source.txt").write_text("two\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "change"], cwd=repo, check=True)
    changed = _run(gate, repo, command)

    assert changed.passed and not changed.cached
    assert counter.read_text(encoding="utf-8") == "xxxx"


def test_failure_and_timeout_do_not_create_passing_evidence(tmp_path):
    repo = _git_repo(tmp_path)
    state = tmp_path / "quality.json"
    gate = BranchQualityGate(str(state), timeout_seconds=1)

    failed = _run(gate, repo, "sh -c 'echo broken; exit 7'")
    timed_out = _run(gate, repo, "sleep 2")
    cached_failure = _run(gate, repo, "sh -c 'echo broken; exit 7'")

    assert failed.status == "failed"
    assert "broken" in failed.output_tail
    assert timed_out.status == "timed_out"
    assert cached_failure.status == "failed"
    assert cached_failure.cached
    assert not failed.passed
    assert not timed_out.passed


def test_concurrent_readiness_checks_execute_once(tmp_path):
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    command = f"printf x >> {shlex.quote(str(counter))}; sleep 0.2"
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    barrier = threading.Barrier(3)
    results = []

    def worker():
        barrier.wait()
        results.append(_run(gate, repo, command))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)

    assert len(results) == 2
    assert all(result.passed for result in results)
    assert sum(result.cached for result in results) == 1
    assert counter.read_text(encoding="utf-8") == "x"


def test_no_command_is_an_explicit_non_blocking_result(tmp_path):
    repo = _git_repo(tmp_path)
    result = _run(
        BranchQualityGate(str(tmp_path / "quality.json")),
        repo,
        "",
    )

    assert result.status == "not_configured"
    assert result.passed


def test_orchestrator_resolves_exact_branch_worktree_and_posts_evidence(tmp_path):
    repo = _git_repo(tmp_path)
    project = Project(
        id="project-1",
        name="project",
        repo_url="https://example.test/org/repo",
        repo_path=str(repo),
        test_command="true",
    )
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id=project.id,
        work_branch="work",
    )
    tracker = MagicMock()
    project_store = MagicMock()
    project_store.worktree_path_for.return_value = str(repo)
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = project_store
    orch._issue_has_children = MagicMock(return_value=False)
    orch._branch_quality_gate = BranchQualityGate(
        str(tmp_path / "quality.json")
    )
    orch._tracker_for_project = MagicMock(return_value=tracker)

    resolved = orch._quality_gate_worktree(project, issue, "work")
    passed = orch._review_quality_gate_passes(
        project,
        issue,
        "work",
        "main",
    )

    assert resolved == str(repo)
    assert passed is True
    assert tracker.add_comment.call_count == 1
    assert "Review creation may proceed" in tracker.add_comment.call_args.args[1]


def test_orchestrator_rejects_checkout_that_is_not_branch_tip(tmp_path):
    repo = _git_repo(tmp_path)
    (repo / "work.txt").write_text("work\n", encoding="utf-8")
    subprocess.run(["git", "add", "work.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "work"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "main"], cwd=repo, check=True)
    project = Project(
        id="project-1",
        name="project",
        repo_url="https://example.test/org/repo",
        repo_path=str(repo),
    )
    issue = Issue(
        id="task-1",
        identifier="task-1",
        title="Task",
        project_id=project.id,
    )
    project_store = MagicMock()
    project_store.worktree_path_for.return_value = str(repo)
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = project_store
    orch._issue_has_children = MagicMock(return_value=False)

    assert orch._quality_gate_worktree(project, issue, "work") == ""
