from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from oompah.models import Issue, Project
from oompah.orchestrator import Orchestrator
from oompah.quality_gate import BranchQualityGate, QualityGateResult
from oompah.statuses import OPEN, READY_TO_INTEGRATE


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
    # Create a compliant Makefile with OOMPAH-652 isolation logic
    makefile = repo / "Makefile"
    makefile.write_text(
        """
_PYTEST_GATE := $(filter 1 true yes,$(strip $(OOMPAH_PYTEST_GATE)))
ifeq ($(_PYTEST_GATE),)
PID_FILE ?= .oompah.pid
else
PID_FILE := $(OOMPAH_TEST_PID_FILE)
endif
PORT := $(OOMPAH_TEST_SERVER_PORT)
OOMPAH_PYTEST_RUN_ROOT := /tmp/test

.PHONY: test
test:
\t@pytest
""",
        encoding="utf-8",
    )
    source = repo / "source.txt"
    source.write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "Makefile", "source.txt"], cwd=repo, check=True)
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


def test_pre_sanitization_evidence_is_invalidated(tmp_path):
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    state = tmp_path / "quality.json"
    command = f"printf x >> {shlex.quote(str(counter))}"
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    legacy_key = hashlib.sha256(
        "\0".join(
            (
                "https://example.test/org/repo",
                "main",
                "work",
                head_sha,
                command,
            )
        ).encode("utf-8")
    ).hexdigest()
    state.write_text(
        json.dumps(
            {
                "version": 1,
                "results": {
                    legacy_key: {
                        "status": "passed",
                        "head_sha": head_sha,
                        "command": command,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = _run(BranchQualityGate(str(state)), repo, command)

    assert result.passed and not result.cached
    assert counter.read_text(encoding="utf-8") == "x"
    assert json.loads(state.read_text(encoding="utf-8"))["version"] == 2


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


def test_gate_reads_only_its_detached_snapshot_after_task_worktree_changes(tmp_path):
    repo = _git_repo(tmp_path)
    observed = tmp_path / "observed.txt"
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    head = _run(gate, repo, "true").head_sha
    command = (
        f"sleep 0.3; cat source.txt > {shlex.quote(str(observed))}"
    )

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _run,
                gate,
                repo,
                command,
                expected_head_sha=head,
                generation="task-generation-1",
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if BranchQualityGate._active_snapshots:
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("quality gate snapshot was not active")

            # Simulate an operator reopening the task and the replacement
            # agent mutating the reusable task worktree.
            (repo / "source.txt").write_text("replacement\n", encoding="utf-8")
            result = future.result(timeout=5)

        assert result.passed
        assert result.head_sha == head
        assert observed.read_text(encoding="utf-8") == "one\n"
        with BranchQualityGate._processes_lock:
            assert BranchQualityGate._active_snapshots == {}
    finally:
        BranchQualityGate.cleanup_active_processes()


def test_gate_rejects_a_worktree_that_is_not_the_recorded_head(tmp_path):
    repo = _git_repo(tmp_path)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    first_head = _run(gate, repo, "true").head_sha
    (repo / "source.txt").write_text("two\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "second"], cwd=repo, check=True)
    marker = tmp_path / "must-not-run"

    result = _run(
        gate,
        repo,
        f"touch {shlex.quote(str(marker))}",
        expected_head_sha=first_head,
    )

    assert result.status == "stale_head"
    assert not marker.exists()


def test_generation_cancellation_does_not_stop_a_replacement_head_gate(tmp_path):
    repo = _git_repo(tmp_path)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    old_head = _run(gate, repo, "true").head_sha
    old_marker = tmp_path / "old-marker"
    new_marker = tmp_path / "new-marker"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            old_future = pool.submit(
                _run,
                gate,
                repo,
                f"sleep 2; touch {shlex.quote(str(old_marker))}",
                expected_head_sha=old_head,
                generation="old-generation",
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if any(
                        generation == "old-generation"
                        for generation in BranchQualityGate._active_generations.values()
                    ):
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("old quality gate was not active")

            (repo / "source.txt").write_text("new\n", encoding="utf-8")
            subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "new"], cwd=repo, check=True)
            new_head = _run(gate, repo, "true").head_sha
            new_future = pool.submit(
                _run,
                gate,
                repo,
                f"sleep 0.1; touch {shlex.quote(str(new_marker))}",
                expected_head_sha=new_head,
                generation="new-generation",
            )
            assert BranchQualityGate.cancel_generation("old-generation") == 1
            old_result = old_future.result(timeout=5)
            new_result = new_future.result(timeout=5)

        assert old_result.status == "interrupted"
        assert new_result.passed
        assert not old_marker.exists()
        assert new_marker.exists()
    finally:
        BranchQualityGate.cleanup_active_processes()


def test_gate_liveness_callback_cancels_only_its_owned_process(tmp_path):
    repo = _git_repo(tmp_path)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    head = BranchQualityGate._head_sha(str(repo))
    current = threading.Event()
    current.set()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _run,
                gate,
                repo,
                "sleep 60",
                expected_head_sha=head,
                generation="liveness-generation",
                is_current=current.is_set,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if BranchQualityGate._active_generations:
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("liveness quality gate was not active")

            current.clear()
            result = future.result(timeout=5)

        assert result.status == "interrupted"
        assert not (tmp_path / "quality.json").exists()
    finally:
        BranchQualityGate.cleanup_active_processes()


def test_no_command_is_an_explicit_non_blocking_result(tmp_path):
    repo = _git_repo(tmp_path)
    result = _run(
        BranchQualityGate(str(tmp_path / "quality.json")),
        repo,
        "",
    )

    assert result.status == "not_configured"
    assert result.passed


def test_gate_subprocess_strips_client_credentials_only(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path)
    monkeypatch.setenv("OOMPAH_SERVER_USERNAME", "operator")
    monkeypatch.setenv("OOMPAH_SERVER_PASSWORD", "secret")
    monkeypatch.setenv("OOMPAH_SERVER_PASSWORD_FILE", "/secret/path")
    monkeypatch.setenv("QUALITY_GATE_SENTINEL", "visible")
    command = (
        'test -z "${OOMPAH_SERVER_USERNAME+x}"'
        ' && test -z "${OOMPAH_SERVER_PASSWORD+x}"'
        ' && test -z "${OOMPAH_SERVER_PASSWORD_FILE+x}"'
        ' && test "$QUALITY_GATE_SENTINEL" = visible'
    )

    result = _run(
        BranchQualityGate(str(tmp_path / "quality.json")),
        repo,
        command,
    )

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
    orch._standalone_delivery_authority_lock = threading.RLock()
    orch._standalone_delivery_authorities = {}

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


def test_orchestrator_discards_a_pass_when_the_branch_advances_during_gate(tmp_path):
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
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._standalone_delivery_authorities = {}
    orch._standalone_delivery_authority_lock = threading.RLock()

    class AdvancingGate:
        def run(self, **kwargs):
            (repo / "source.txt").write_text("replacement\n", encoding="utf-8")
            subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "replacement"],
                cwd=repo,
                check=True,
            )
            return QualityGateResult(
                status="passed",
                head_sha=kwargs["expected_head_sha"],
                command=kwargs["command"],
            )

    orch._branch_quality_gate = AdvancingGate()

    assert not orch._review_quality_gate_passes(project, issue, "work", "main")
    tracker.add_comment.assert_not_called()


def test_standalone_review_gate_receives_live_delivery_authority(tmp_path):
    """Standalone gates re-read authority until their exact command finishes."""
    repo = _git_repo(tmp_path)
    head = BranchQualityGate._head_sha(str(repo))
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
        state=READY_TO_INTEGRATE,
        work_branch="work",
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    project_store = MagicMock()
    project_store.get.return_value = project

    class RecordingGate:
        def run(self, **kwargs):
            self.kwargs = kwargs
            return QualityGateResult(
                status="passed",
                head_sha=kwargs["expected_head_sha"],
                command=kwargs["command"],
            )

    gate = RecordingGate()
    orch = Orchestrator.__new__(Orchestrator)
    orch.project_store = project_store
    orch._tracker_for_project = MagicMock(return_value=tracker)
    orch._standalone_delivery_authority_lock = threading.RLock()
    orch._standalone_delivery_authorities = {}
    orch._branch_quality_gate = gate
    orch._quality_gate_worktree = MagicMock(return_value=str(repo))
    orch._quality_gate_branch_head = MagicMock(return_value=head)

    assert orch._review_quality_gate_passes(project, issue, "work", "main")
    is_current = gate.kwargs["is_current"]
    assert callable(is_current)
    assert is_current()

    issue.state = OPEN
    assert not is_current()


def test_quality_gate_cleans_up_active_process_groups(tmp_path):
    repo = _git_repo(tmp_path)
    state = tmp_path / "quality.json"
    gate = BranchQualityGate(str(state))
    with BranchQualityGate._processes_lock:
        BranchQualityGate._active_processes.clear()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run, gate, repo, "sleep 60")
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if BranchQualityGate._active_processes:
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("quality gate process was not tracked")

            assert BranchQualityGate.cleanup_active_processes() == 1
            result = future.result(timeout=5)

        assert result.status == "interrupted"
        assert result.cached is False
        assert not state.exists()
        with BranchQualityGate._processes_lock:
            assert BranchQualityGate._active_processes == {}
    finally:
        BranchQualityGate.cleanup_active_processes()


def test_quality_gate_tracks_and_removes_processes_on_completion(tmp_path):
    repo = _git_repo(tmp_path)
    with BranchQualityGate._processes_lock:
        BranchQualityGate._active_processes.clear()
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    result = _run(gate, repo, "true")

    assert result.passed
    with BranchQualityGate._processes_lock:
        assert BranchQualityGate._active_processes == {}


def test_quality_gate_cleans_up_on_timeout(tmp_path):
    repo = _git_repo(tmp_path)
    with BranchQualityGate._processes_lock:
        BranchQualityGate._active_processes.clear()
    gate = BranchQualityGate(str(tmp_path / "quality.json"), timeout_seconds=1)
    result = _run(gate, repo, "sleep 10")

    assert result.status == "timed_out"
    with BranchQualityGate._processes_lock:
        assert BranchQualityGate._active_processes == {}


def test_explicit_retry_re_executes_failed_result(tmp_path):
    """Forced retry should bypass cache for failed results and re-execute."""
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    state = tmp_path / "quality.json"
    gate = BranchQualityGate(str(state))

    # First run: fails and is cached
    (repo / "work.txt").write_text("fail\n", encoding="utf-8")
    subprocess.run(["git", "add", "work.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fail"], cwd=repo, check=True)
    failed = _run(gate, repo, f"echo fail; exit 1")
    assert failed.status == "failed" and not failed.cached

    # Second run: same head, cache hit for failure
    cached_fail = _run(gate, repo, f"echo fail; exit 1")
    assert cached_fail.status == "failed" and cached_fail.cached

    # Third run: forced retry should re-execute (not use cache)
    retry = _run(gate, repo, f"echo fail; exit 1", retry_forced=True)
    assert retry.status == "failed" and not retry.cached


def test_explicit_retry_re_executes_timeout_result(tmp_path):
    """Forced retry should bypass cache for timed_out results and re-execute."""
    repo = _git_repo(tmp_path)
    state = tmp_path / "quality.json"
    gate = BranchQualityGate(str(state), timeout_seconds=1)

    # First run: times out
    timed_out = _run(gate, repo, "sleep 2")
    assert timed_out.status == "timed_out" and not timed_out.cached

    # Second run: same head, cache hit for timeout
    cached_timeout = _run(gate, repo, "sleep 2")
    assert cached_timeout.status == "timed_out" and cached_timeout.cached

    # Third run: forced retry should re-execute (not use cache)
    retry = _run(gate, repo, "sleep 2", retry_forced=True)
    assert retry.status == "timed_out" and not retry.cached


def test_explicit_retry_re_executes_failed_with_non_zero_exit(tmp_path):
    """Forced retry should bypass cache for failed results (non-zero exit) and re-execute."""
    repo = _git_repo(tmp_path)
    state = tmp_path / "quality.json"
    gate = BranchQualityGate(str(state))

    # First run: fails with non-zero exit code
    failed = _run(gate, repo, "sh -c 'echo error; exit 42'")
    assert failed.status == "failed" and not failed.cached

    # Second run: same head, cache hit for failure
    cached_failed = _run(gate, repo, "sh -c 'echo error; exit 42'")
    assert cached_failed.status == "failed" and cached_failed.cached

    # Third run: forced retry should re-execute (not use cache)
    retry = _run(gate, repo, "sh -c 'echo error; exit 42'", retry_forced=True)
    assert retry.status == "failed" and not retry.cached


def test_explicit_retry_preserves_passed_cache(tmp_path):
    """Forced retry should NOT bypass cache for passed results."""
    repo = _git_repo(tmp_path)
    counter = tmp_path / "counter"
    command = f"printf x >> {shlex.quote(str(counter))}"
    state = tmp_path / "quality.json"
    gate = BranchQualityGate(str(state))

    # First run: passes and is cached
    first = _run(gate, repo, command)
    assert first.passed and not first.cached

    # Second run: same head, cache hit for pass
    second = _run(gate, repo, command)
    assert second.passed and second.cached
    assert counter.read_text(encoding="utf-8") == "x"

    # Third run: forced retry should still use cache for passed result
    retry = _run(gate, repo, command, retry_forced=True)
    assert retry.passed and retry.cached
    # Counter should not increment (command was not re-executed)
    assert counter.read_text(encoding="utf-8") == "x"


def test_explicit_retry_can_recover_from_transient_failure(tmp_path):
    """When a transient failure is retried with retry_forced, it can pass."""
    repo = _git_repo(tmp_path)
    trigger = tmp_path / "trigger"
    state = tmp_path / "quality.json"
    gate = BranchQualityGate(str(state))
    trigger.write_text("fail\n", encoding="utf-8")

    # First run: fails (trigger file exists)
    failed = _run(gate, repo, f"test -f {shlex.quote(str(trigger))} && exit 1 || true")
    assert failed.status == "failed"

    # Second run: same head, cache hit
    cached = _run(gate, repo, f"test -f {shlex.quote(str(trigger))} && exit 1 || true")
    assert cached.cached

    # Remove the failure trigger
    trigger.unlink()

    # Third run: forced retry bypasses cache, re-executes, and passes
    retry = _run(gate, repo, f"test -f {shlex.quote(str(trigger))} && exit 1 || true", retry_forced=True)
    assert retry.status == "passed" and not retry.cached


# ---------------------------------------------------------------------------
# Deterministic pre-spawn barrier tests
# These cover the three live failure windows identified in OOMPAH-657.
# ---------------------------------------------------------------------------


def test_tombstone_set_before_run_stops_gate_at_first_barrier(tmp_path):
    """cancel_generation before run() prevents any snapshot or spawn.

    Barrier 1: The tombstone is checked before _create_snapshot().  A gate
    cancelled by the tracker transition to Open/rejected before it even
    starts must not create a snapshot or run the command.
    """
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    head = BranchQualityGate._head_sha(str(repo))

    # Tombstone the generation before run() is called.  This simulates
    # _retire_inactive_integration_rows cancelling the generation when the
    # tracker moves a task from Ready to Integrate to Open before the gate
    # loop has a chance to spawn the process.
    BranchQualityGate.cancel_generation("pre-spawn-gen")
    try:
        result = _run(
            gate,
            repo,
            f"touch {shlex.quote(str(marker))}",
            expected_head_sha=head,
            generation="pre-spawn-gen",
        )

        assert result.status == "interrupted"
        assert not marker.exists()
        # The tombstone must be cleaned up after the gate exits.
        with BranchQualityGate._processes_lock:
            assert "pre-spawn-gen" not in BranchQualityGate._cancelled_generations
    finally:
        BranchQualityGate.cleanup_active_processes()
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard("pre-spawn-gen")


def test_is_current_false_before_snapshot_stops_gate_at_barrier_one(tmp_path):
    """is_current() returning False before snapshot creation stops the gate.

    Barrier 1: authority is checked before _create_snapshot() so that the
    expensive git worktree add is never called when the task is no longer
    authorised.
    """
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    head = BranchQualityGate._head_sha(str(repo))

    result = _run(
        gate,
        repo,
        f"touch {shlex.quote(str(marker))}",
        expected_head_sha=head,
        generation="barrier1-gen",
        # Authority already withdrawn — simulates a Ready-to-Open transition
        # that completes before the gate even acquires the key lock.
        is_current=lambda: False,
    )

    assert result.status == "interrupted"
    assert not marker.exists()
    # No snapshot should have been created.
    with BranchQualityGate._processes_lock:
        assert not BranchQualityGate._active_snapshots


def test_is_current_false_after_snapshot_stops_gate_before_spawn(tmp_path):
    """is_current() returning False after snapshot but before Popen stops gate.

    Barrier 2: authority is rechecked after _create_snapshot() completes
    (which can take up to 60 s) and before subprocess.Popen() is called,
    closing the window where cancel_generation() arrived during worktree
    creation but found no registered process to kill.
    """
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    head = BranchQualityGate._head_sha(str(repo))
    original_create = BranchQualityGate._create_snapshot

    # Simulate authority being withdrawn mid-snapshot by patching
    # _create_snapshot to flip the authority flag after it returns.
    authority = threading.Event()
    authority.set()

    def _create_and_revoke(repo_path: str, head_sha: str):
        snap = original_create(repo_path, head_sha)
        # Revoke authority to simulate the Ready-to-Open transition arriving
        # while the worktree was being created.
        authority.clear()
        return snap

    gate._create_snapshot = staticmethod(_create_and_revoke)
    try:
        result = _run(
            gate,
            repo,
            f"touch {shlex.quote(str(marker))}",
            expected_head_sha=head,
            generation="barrier2-gen",
            is_current=authority.is_set,
        )

        assert result.status == "interrupted"
        assert not marker.exists()
    finally:
        BranchQualityGate.cleanup_active_processes()


def test_tombstone_during_snapshot_stops_gate_at_barrier_two(tmp_path):
    """cancel_generation() during _create_snapshot() stops gate before spawn.

    This covers the same Barrier 2 window as the is_current variant but
    uses the tombstone path: cancel_generation() is called on a thread
    that blocks inside the (mocked) snapshot creation and the gate must
    not proceed to Popen even though it was not yet registered.
    """
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    head = BranchQualityGate._head_sha(str(repo))
    original_create = BranchQualityGate._create_snapshot

    snapshot_started = threading.Event()

    def _slow_create(repo_path: str, head_sha: str):
        snapshot_started.set()
        # Block until the test thread has set the tombstone.
        while "tombstone-during-snap" not in BranchQualityGate._cancelled_generations:
            time.sleep(0.01)
        return original_create(repo_path, head_sha)

    gate._create_snapshot = staticmethod(_slow_create)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _run,
                gate,
                repo,
                f"touch {shlex.quote(str(marker))}",
                expected_head_sha=head,
                generation="tombstone-during-snap",
            )
            # Wait until the gate is inside the (slow) snapshot creation,
            # then tombstone it to simulate a Ready-to-Open row retirement
            # arriving while the worktree is being materialised.
            assert snapshot_started.wait(timeout=5), "snapshot hook not reached"
            BranchQualityGate.cancel_generation("tombstone-during-snap")
            result = future.result(timeout=10)

        assert result.status == "interrupted"
        assert not marker.exists()
        # Tombstone must be cleaned up.
        with BranchQualityGate._processes_lock:
            assert "tombstone-during-snap" not in BranchQualityGate._cancelled_generations
    finally:
        BranchQualityGate.cleanup_active_processes()
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard("tombstone-during-snap")


def test_tombstone_set_between_popen_and_registration_stops_gate(tmp_path):
    """cancel_generation() between Popen and registration terminates the process.

    Barrier 3: the gate checks the tombstone under _processes_lock immediately
    after registering the process (the same lock cancel_generation uses), so a
    cancel that races Popen will kill the just-spawned process and return
    interrupted rather than letting the command run to completion.
    """
    repo = _git_repo(tmp_path)
    marker = tmp_path / "must-not-run"
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    head = BranchQualityGate._head_sha(str(repo))
    original_create = BranchQualityGate._create_snapshot

    snapshot_done = threading.Event()

    def _create_and_signal(repo_path: str, head_sha: str):
        snap = original_create(repo_path, head_sha)
        # Signal that the snapshot is ready; the test thread will tombstone
        # the generation while Popen is being called.  The gate must still
        # detect the cancel via barrier 3 (post-registration check).
        snapshot_done.set()
        return snap

    gate._create_snapshot = staticmethod(_create_and_signal)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                _run,
                gate,
                repo,
                f"sleep 30 && touch {shlex.quote(str(marker))}",
                expected_head_sha=head,
                generation="popen-to-reg-gen",
            )
            # Wait until after snapshot creation, then tombstone to simulate
            # the Popen-to-registration window cancellation.
            assert snapshot_done.wait(timeout=5), "snapshot hook not reached"
            BranchQualityGate.cancel_generation("popen-to-reg-gen")
            result = future.result(timeout=10)

        assert result.status == "interrupted"
        assert not marker.exists()
        with BranchQualityGate._processes_lock:
            assert "popen-to-reg-gen" not in BranchQualityGate._cancelled_generations
    finally:
        BranchQualityGate.cleanup_active_processes()
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard("popen-to-reg-gen")


def test_cancelled_generation_stays_tombstoned_for_waiting_same_generation(tmp_path):
    """One interrupted caller cannot revive another caller waiting on its key."""
    repo = _git_repo(tmp_path)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    head = BranchQualityGate._head_sha(str(repo))
    marker = tmp_path / "must-not-run"
    generation = "shared-generation"
    command = f"sleep 30; touch {shlex.quote(str(marker))}"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(
                _run,
                gate,
                repo,
                command,
                expected_head_sha=head,
                generation=generation,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if BranchQualityGate._active_generations:
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("first quality gate was not active")

            # The second caller registers before it waits on the same
            # evidence key.  Cancelling the generation must fence both
            # callers, rather than allowing the waiter to launch after the
            # first caller's cleanup runs.
            second = pool.submit(
                _run,
                gate,
                repo,
                command,
                expected_head_sha=head,
                generation=generation,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with BranchQualityGate._processes_lock:
                    if BranchQualityGate._generation_run_counts.get(generation) == 2:
                        break
                time.sleep(0.01)
            else:
                raise AssertionError("second quality gate did not wait on the key")

            assert BranchQualityGate.cancel_generation(generation) == 1
            assert first.result(timeout=10).status == "interrupted"
            assert second.result(timeout=10).status == "interrupted"

        assert not marker.exists()
        with BranchQualityGate._processes_lock:
            assert generation not in BranchQualityGate._cancelled_generations
            assert generation not in BranchQualityGate._generation_run_counts
    finally:
        BranchQualityGate.cleanup_active_processes()
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard(generation)
            BranchQualityGate._generation_run_counts.pop(generation, None)


def test_single_flight_locks_are_released_after_unique_evidence(tmp_path):
    """Completed evidence keys do not leave an unbounded lock registry."""
    repo = _git_repo(tmp_path)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))

    for index in range(20):
        result = _run(gate, repo, f"true # evidence-{index}")
        assert result.passed

    assert gate._key_locks == {}


def test_cancel_before_spawn_tombstones_are_bounded(monkeypatch):
    """Abandoned pre-spawn generations cannot grow process state forever."""
    monkeypatch.setattr(BranchQualityGate, "_MAX_CANCELLED_GENERATIONS", 2)
    with BranchQualityGate._processes_lock:
        BranchQualityGate._cancelled_generations.clear()
        BranchQualityGate._cancelled_generation_order.clear()
        BranchQualityGate._generation_run_counts.clear()
    try:
        for generation in ("oldest", "middle", "newest"):
            BranchQualityGate.cancel_generation(generation)

        with BranchQualityGate._processes_lock:
            assert "oldest" not in BranchQualityGate._cancelled_generations
            assert BranchQualityGate._cancelled_generations == {"middle", "newest"}
    finally:
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.clear()
            BranchQualityGate._cancelled_generation_order.clear()
            BranchQualityGate._generation_run_counts.clear()


def test_failed_snapshot_verification_removes_worktree_registration(tmp_path, monkeypatch):
    """A post-add snapshot verification failure leaves no registered worktree."""
    repo = _git_repo(tmp_path)
    head = BranchQualityGate._head_sha(str(repo))
    snapshot = tmp_path / "failed-snapshot"
    monkeypatch.setattr(
        "oompah.quality_gate.tempfile.mkdtemp",
        lambda prefix: str(snapshot),
    )
    monkeypatch.setattr(
        BranchQualityGate,
        "_head_sha",
        staticmethod(lambda _path: "not-the-requested-head"),
    )

    with pytest.raises(RuntimeError, match="different commit"):
        BranchQualityGate._create_snapshot(str(repo), head)

    registered = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert f"worktree {snapshot}" not in registered
    assert not snapshot.exists()


def test_preflight_rejects_old_makefile_without_isolation_logic(tmp_path):
    """Branches created before OOMPAH-652 lack isolation logic and must rebase."""
    repo = _git_repo(tmp_path)
    # Old Makefile without OOMPAH_PYTEST_GATE handling
    old_makefile = repo / "Makefile"
    old_makefile.write_text(
        """
.PHONY: test
test:
\t@pytest
PID_FILE ?= .oompah.pid
PORT ?= 8080
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "Makefile"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "old makefile"], cwd=repo, check=True)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))

    result = _run(gate, repo, "true")

    assert result.status == "needs_rebase"
    assert "OOMPAH-652" in result.output_tail
    assert "Branch requires rebase" in result.output_tail


def test_preflight_allows_makefile_with_isolation_logic(tmp_path):
    """Branches with OOMPAH-652 isolation logic are allowed to execute."""
    repo = _git_repo(tmp_path)
    # Makefile with OOMPAH_PYTEST_GATE handling (from OOMPAH-652)
    compliant_makefile = repo / "Makefile"
    compliant_makefile.write_text(
        """
_PYTEST_GATE := $(filter 1 true yes,$(strip $(OOMPAH_PYTEST_GATE)))
ifeq ($(_PYTEST_GATE),)
PID_FILE ?= .oompah.pid
else
PID_FILE := $(OOMPAH_TEST_PID_FILE)
endif
PORT := $(OOMPAH_TEST_SERVER_PORT)
OOMPAH_PYTEST_RUN_ROOT := /tmp/test
.PHONY: test
test:
\t@pytest
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "Makefile"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "isolation makefile"], cwd=repo, check=True)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    counter = tmp_path / "counter"

    result = _run(gate, repo, f"printf x >> {shlex.quote(str(counter))}")

    assert result.passed


def test_preflight_rejects_missing_makefile(tmp_path):
    """Branches without a Makefile cannot be checked for isolation logic."""
    repo = _git_repo(tmp_path)
    # Delete the Makefile if it exists (it shouldn't in the test repo)
    makefile = repo / "Makefile"
    if makefile.exists():
        makefile.unlink()
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "no makefile"], cwd=repo, check=True)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))

    result = _run(gate, repo, "true")

    assert result.status == "needs_rebase"
    assert "Makefile not found" in result.output_tail


def test_hostile_old_makefile_is_rejected_before_execution(tmp_path, monkeypatch):
    """
    Intentionally malicious old Makefile attempting canonical file discovery
    is rejected at preflight without ever executing.

    This proves that the preflight validation prevents hostile candidate code
    from discovering or signaling the operator service, even if the Makefile
    ignores isolation variables.
    """
    repo = _git_repo(tmp_path)

    # Create an intentionally old/malicious Makefile that ignores OOMPAH_PYTEST_GATE
    # and tries to discover the operator service. This Makefile predates OOMPAH-652
    # and does NOT contain the isolation logic.
    hostile_makefile = repo / "Makefile"
    hostile_makefile.write_text(
        """
# Hostile old Makefile that ignores isolation variables
# and tries to discover/signal the operator service

.PHONY: test
test:
\t@echo "Attempting to discover operator service..."
\t@test -f .oompah.pid && echo "FOUND OPERATOR PID FILE" || true
\t@test -f .oompah.pid.meta && echo "FOUND OPERATOR PID META" || true
\t@curl -s http://127.0.0.1:8090/healthz && echo "FOUND OPERATOR SERVICE" || true
\t@if [ -f .oompah.pid ]; then kill -0 $$(cat .oompah.pid) && echo "OPERATOR PID ALIVE"; fi || true

PID_FILE = .oompah.pid
PORT = 8080
OOMPAH_PYTEST_GATE is ignored
""",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "Makefile"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "hostile makefile"], cwd=repo, check=True)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))

    # The preflight validation should reject this branch BEFORE executing
    # the make test command, preventing any discovery attempts.
    result = _run(gate, repo, "make test")

    # Verify the branch was rejected at preflight
    assert result.status == "needs_rebase"
    assert "OOMPAH-652" in result.output_tail
    # Verify the hostile command output does NOT appear (command was never executed)
    assert "FOUND OPERATOR" not in result.output_tail
    assert "ATTEMPTING TO DISCOVER" not in result.output_tail.upper()


def test_compliant_branch_allows_execution(tmp_path):
    """
    Compliant branches with OOMPAH-652 isolation logic pass the preflight
    and are allowed to execute. The Makefile contains the logic to use
    private PID files and ephemeral ports when OOMPAH_PYTEST_GATE is set.
    """
    repo = _git_repo(tmp_path)
    gate = BranchQualityGate(str(tmp_path / "quality.json"))
    counter = tmp_path / "counter"

    # Compliant Makefile is already in the repo from _git_repo
    result = _run(gate, repo, f"printf x >> {shlex.quote(str(counter))}")

    # Preflight passes and command executes
    assert result.passed
    assert counter.read_text(encoding="utf-8") == "x"
