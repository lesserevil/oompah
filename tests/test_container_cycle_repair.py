from __future__ import annotations

import subprocess

import pytest

from oompah.container_cycle_repair import (
    ContainerCycleRepairExecutor,
    ContainerCycleRepairPlan,
    CycleRepairRow,
    MergeConflict,
    UnsafePrerequisite,
)


def _run(cwd, *args):
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    _run(tmp_path, "init", "--bare", str(remote))
    _run(tmp_path, "init", str(repo))
    _run(repo, "config", "user.name", "repair-test")
    _run(repo, "config", "user.email", "repair@example.invalid")
    (repo / "tracked.txt").write_text("base\n")
    _run(repo, "add", "tracked.txt")
    _run(repo, "commit", "-m", "base")
    _run(repo, "branch", "-M", "main")
    _run(repo, "remote", "add", "origin", str(remote))
    _run(repo, "push", "origin", "main")
    return repo, remote


def _branch(repo, branch, *, base="main", text=None):
    _run(repo, "switch", "-c", branch, base)
    if text is not None:
        (repo / "tracked.txt").write_text(text)
        _run(repo, "add", "tracked.txt")
        _run(repo, "commit", "-m", branch)
    _run(repo, "push", "origin", branch)
    return _run(repo, "rev-parse", "HEAD").stdout.strip()


def _plan(parent_sha, *, child="EXOCOMP-130"):
    return ContainerCycleRepairPlan(
        key="cycle-1",
        authoritative_container="EXOCOMP-127",
        dependent_containers=(child,),
        prerequisite_shas=(("EXOCOMP-171", parent_sha),),
        declared_closure=(parent_sha,),
        rows=(
            CycleRepairRow(
                task_id="EXOCOMP-200",
                container_id=child,
                epic_id=child,
                task_branch="task/EXOCOMP-200",
                head_sha=parent_sha,
            ),
        ),
    )


def test_parent_fast_forward_and_parent_only_child_sync_are_idempotent(tmp_path):
    repo, _remote = _repo(tmp_path)
    old = _branch(repo, "epic-EXOCOMP-127")
    _branch(repo, "epic-EXOCOMP-130", base="main")
    _run(repo, "switch", "epic-EXOCOMP-127")
    (repo / "tracked.txt").write_text("prerequisite\n")
    _run(repo, "add", "tracked.txt")
    _run(repo, "commit", "-m", "EXOCOMP-171")
    selected = _run(repo, "rev-parse", "HEAD").stdout.strip()
    plan = _plan(selected)

    first = ContainerCycleRepairExecutor(str(repo)).execute(plan)

    assert first.status == "ready_for_queue_restore"
    assert first.parent_expected_sha == old
    assert first.parent_sha == selected
    assert first.children[0].action == "fast_forward"
    assert ContainerCycleRepairExecutor(str(repo)).prove_reachability(plan, first)

    second = ContainerCycleRepairExecutor(str(repo)).execute(
        plan,
        prior_evidence=first.to_dict(),
    )
    assert second.status == "ready_for_queue_restore"
    assert second.parent_sha == selected
    assert second.children[0].action == "already_reachable"
    assert _run(repo, "rev-parse", "origin/epic-EXOCOMP-130").stdout.strip() == selected


def test_selected_prerequisite_with_unrelated_sibling_commit_is_rejected(tmp_path):
    repo, _remote = _repo(tmp_path)
    old = _branch(repo, "epic-EXOCOMP-127")
    _run(repo, "switch", "epic-EXOCOMP-127")
    (repo / "tracked.txt").write_text("sibling\n")
    _run(repo, "add", "tracked.txt")
    _run(repo, "commit", "-m", "unrelated sibling")
    sibling = _run(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "tracked.txt").write_text("selected\n")
    _run(repo, "add", "tracked.txt")
    _run(repo, "commit", "-m", "selected prerequisite")
    selected = _run(repo, "rev-parse", "HEAD").stdout.strip()

    executor = ContainerCycleRepairExecutor(str(repo))
    with pytest.raises(UnsafePrerequisite, match="outside its declared closure"):
        executor.validate_prerequisite_descendant(old, selected, (selected,))
    assert sibling != selected


def test_diverged_parent_only_child_conflict_does_not_change_remote_ref(tmp_path):
    repo, _remote = _repo(tmp_path)
    _branch(repo, "epic-EXOCOMP-127")
    _branch(repo, "epic-EXOCOMP-130", base="main", text="child\n")
    _run(repo, "switch", "epic-EXOCOMP-127")
    (repo / "tracked.txt").write_text("parent\n")
    _run(repo, "add", "tracked.txt")
    _run(repo, "commit", "-m", "parent prerequisite")
    selected = _run(repo, "rev-parse", "HEAD").stdout.strip()
    child_before = _run(repo, "rev-parse", "origin/epic-EXOCOMP-130").stdout.strip()
    plan = _plan(selected)

    result = ContainerCycleRepairExecutor(str(repo)).execute(plan)

    assert result.status == "partial"
    assert result.children[0].action == "conflict"
    assert _run(repo, "rev-parse", "origin/epic-EXOCOMP-130").stdout.strip() == child_before


def test_diverged_parent_only_child_clean_merge_uses_only_authoritative_parent(tmp_path):
    repo, _remote = _repo(tmp_path)
    _branch(repo, "epic-EXOCOMP-127")
    _branch(repo, "epic-EXOCOMP-130", base="main")
    _run(repo, "switch", "epic-EXOCOMP-130")
    (repo / "child.txt").write_text("child work\n")
    _run(repo, "add", "child.txt")
    _run(repo, "commit", "-m", "child work")
    child_before = _run(repo, "rev-parse", "HEAD").stdout.strip()
    _run(repo, "push", "origin", "epic-EXOCOMP-130")
    _run(repo, "switch", "epic-EXOCOMP-127")
    (repo / "tracked.txt").write_text("parent prerequisite\n")
    _run(repo, "add", "tracked.txt")
    _run(repo, "commit", "-m", "parent prerequisite")
    selected = _run(repo, "rev-parse", "HEAD").stdout.strip()

    result = ContainerCycleRepairExecutor(str(repo)).execute(_plan(selected))

    assert result.status == "ready_for_queue_restore"
    child = result.children[0]
    assert child.action == "merge_parent"
    assert child.resulting_sha != child_before
    assert _run(
        repo,
        "merge-base",
        "--is-ancestor",
        selected,
        child.resulting_sha,
    ).returncode == 0
    assert _run(repo, "show", "-s", "--format=%P", child.resulting_sha).stdout.count(" ") == 1


class _DurableRepairCrash(RuntimeError):
    pass


def test_restart_after_parent_and_child_durable_steps_converges(tmp_path):
    repo, _remote = _repo(tmp_path)
    _branch(repo, "epic-EXOCOMP-127")
    _branch(repo, "epic-EXOCOMP-130", base="main")
    _run(repo, "switch", "epic-EXOCOMP-127")
    (repo / "tracked.txt").write_text("selected prerequisite\n")
    _run(repo, "add", "tracked.txt")
    _run(repo, "commit", "-m", "selected prerequisite")
    selected = _run(repo, "rev-parse", "HEAD").stdout.strip()
    plan = _plan(selected)
    journal = {}

    def crash_after_parent(evidence):
        journal.update(evidence)
        if evidence.get("phase") == "parent_advanced":
            raise _DurableRepairCrash("restart after parent push")

    with pytest.raises(_DurableRepairCrash):
        ContainerCycleRepairExecutor(
            str(repo),
            persist=crash_after_parent,
        ).execute(plan)
    assert journal["parent_sha"] == selected

    def crash_after_child(evidence):
        journal.update(evidence)
        if evidence.get("phase") == "child_synchronized":
            raise _DurableRepairCrash("restart after child push")

    with pytest.raises(_DurableRepairCrash):
        ContainerCycleRepairExecutor(
            str(repo),
            persist=crash_after_child,
        ).execute(plan, prior_evidence=journal)
    assert journal["child"]["action"] == "fast_forward"

    result = ContainerCycleRepairExecutor(str(repo)).execute(
        plan,
        prior_evidence=journal,
    )
    assert result.status == "ready_for_queue_restore"
    assert result.children[0].action == "already_reachable"


def test_parent_compare_and_swap_race_fails_closed_without_child_sync(tmp_path):
    repo, remote = _repo(tmp_path)
    old = _branch(repo, "epic-EXOCOMP-127")
    _branch(repo, "epic-EXOCOMP-130", base="main")
    _run(repo, "switch", "epic-EXOCOMP-127")
    (repo / "tracked.txt").write_text("selected prerequisite\n")
    _run(repo, "add", "tracked.txt")
    _run(repo, "commit", "-m", "selected prerequisite")
    selected = _run(repo, "rev-parse", "HEAD").stdout.strip()
    plan = _plan(selected)

    racer = tmp_path / "racer"
    raced = False

    def run_git(args, cwd, timeout):
        nonlocal raced
        if args and args[0] == "push" and not raced:
            raced = True
            _run(tmp_path, "clone", str(remote), str(racer))
            _run(racer, "config", "user.name", "race-test")
            _run(racer, "config", "user.email", "race@example.invalid")
            _run(
                racer,
                "switch",
                "-c",
                "epic-EXOCOMP-127",
                "--track",
                "origin/epic-EXOCOMP-127",
            )
            (racer / "race.txt").write_text("concurrent writer\n")
            _run(racer, "add", "race.txt")
            _run(racer, "commit", "-m", "concurrent parent writer")
            _run(racer, "push", "origin", "epic-EXOCOMP-127")
        return subprocess.run(
            ["git", *args],
            cwd=cwd or repo,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    result = ContainerCycleRepairExecutor(str(repo), run_git=run_git).execute(plan)

    assert raced
    assert result.status == "blocked"
    assert "compare-and-swap" in (result.error or "")
    assert not result.children
    assert _run(repo, "rev-parse", "origin/epic-EXOCOMP-130").stdout.strip() != selected
    assert _run(repo, "rev-parse", "origin/epic-EXOCOMP-127").stdout.strip() != selected
    assert _run(repo, "rev-parse", "origin/epic-EXOCOMP-127").stdout.strip() != old


def test_missing_or_changed_queue_head_is_not_overwritten(tmp_path):
    from oompah.integration_queue import IntegrationQueueStore

    store = IntegrationQueueStore(str(tmp_path / "queue.sqlite3"))
    store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="T-1",
        task_branch="task/T-1",
        head_sha="old",
    )
    assert store.cancel(
        "p1",
        "T-1",
        reason="container dependency cycle requires authorized repair",
        expected_head_sha="old",
        expected_state="ready",
    )
    store.enqueue(
        project_id="p1",
        epic_id="E-1",
        task_id="T-1",
        task_branch="task/T-1",
        head_sha="new",
    )
    assert not store.restore_cancelled(
        "p1",
        "T-1",
        expected_head_sha="old",
        expected_task_branch="task/T-1",
        expected_epic_id="E-1",
    )
    assert store.items(project_id="p1")[0].head_sha == "new"
