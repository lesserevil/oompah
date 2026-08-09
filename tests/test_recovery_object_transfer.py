"""Recovery publication across linked worktrees and standalone clones."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from oompah.models import Project
from oompah.projects import (
    ProjectError,
    ProjectStore,
    RecoveryPublicationError,
    _transfer_recovery_snapshot_objects,
    _worktree_consumed_recovery_ref,
    _worktree_pending_recovery_ref,
    _worktree_recovery_ref,
)


def _git(repo: Path | str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "--initial-branch=main")
    _git(path, "config", "user.name", "Test")
    _git(path, "config", "user.email", "test@example.com")
    (path / "base.txt").write_text("base\n", encoding="utf-8")
    _git(path, "add", "base.txt")
    _git(path, "commit", "-m", "base")


def _store(tmp_path: Path, repo: Path) -> tuple[ProjectStore, Project]:
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    project = Project(
        id="proj-standalone",
        name="project",
        repo_url=str(repo),
        repo_path=str(repo),
        branch="main",
        default_branch="main",
    )
    store._projects[project.id] = project
    return store, project


def _standalone_task(
    tmp_path: Path,
    issue: str = "TASK-RECOVERY",
) -> tuple[ProjectStore, Project, Path]:
    authority = tmp_path / "authority"
    _init_repo(authority)
    store, project = _store(tmp_path, authority)
    checkout = Path(store.worktree_path_for(project.id, issue))
    checkout.parent.mkdir(parents=True)
    _git(tmp_path, "clone", str(authority), str(checkout))
    _git(checkout, "config", "user.name", "Test")
    _git(checkout, "config", "user.email", "test@example.com")
    _git(checkout, "switch", "-c", issue)
    return store, project, checkout


def _resolve(repo: Path | str, revision: str, *, check: bool = True) -> str:
    result = _git(repo, "rev-parse", "--verify", revision, check=check)
    return result.stdout.strip()


def test_linked_worktree_publication_is_exact_and_idempotent(tmp_path):
    authority = tmp_path / "authority"
    _init_repo(authority)
    store, project = _store(tmp_path, authority)
    issue = "TASK-LINKED"
    checkout = Path(store.worktree_path_for(project.id, issue))
    checkout.parent.mkdir(parents=True)
    _git(authority, "worktree", "add", "-b", issue, str(checkout), "main")
    (checkout / "linked.txt").write_text("linked state\n", encoding="utf-8")

    first = store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )
    restarted, _ = _store(tmp_path, authority)
    second = restarted.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )

    assert first is not None
    assert second is not None
    assert first["snapshot_head"] == second["snapshot_head"]
    assert _resolve(authority, f"{first['recovery_ref']}^{{commit}}") == first[
        "snapshot_head"
    ]
    assert _git(
        authority,
        "show",
        f"{first['snapshot_head']}:linked.txt",
    ).stdout == "linked state\n"


def test_standalone_checkpoint_objects_precede_recovery_ref(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    (checkout / "standalone.txt").write_text("must survive\n", encoding="utf-8")

    context = store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )

    assert context is not None
    snapshot = str(context["snapshot_head"])
    assert context["publication_state"] == "published"
    assert _resolve(project.repo_path, f"{context['recovery_ref']}^{{commit}}") == snapshot
    assert _git(
        project.repo_path,
        "show",
        f"{snapshot}:standalone.txt",
    ).stdout == "must survive\n"
    assert _git(
        checkout,
        "rev-parse",
        "--verify",
        _worktree_pending_recovery_ref(issue),
        check=False,
    ).returncode != 0


def test_successor_submission_consumes_checkpoint_and_stays_consumed(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    (checkout / "checkpoint.txt").write_text("checkpoint\n", encoding="utf-8")
    checkpoint = store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )
    assert checkpoint is not None
    snapshot = str(checkpoint["snapshot_head"])

    (checkout / "successor.txt").write_text("successor\n", encoding="utf-8")
    _git(checkout, "add", "successor.txt")
    _git(checkout, "commit", "-m", "legitimate successor")
    successor = _resolve(checkout, "HEAD")

    assert store.consume_worktree_recovery_if_incorporated(
        project.id,
        issue,
        successor,
        accepted_branch=issue,
        wt_path=str(checkout),
        expected_snapshot=snapshot,
    ) == "consumed"
    assert store.worktree_recovery_context(project.id, issue) is None
    assert store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    ) is None

    restarted, _ = _store(tmp_path, Path(project.repo_path))
    assert restarted.pending_worktree_recoveries() == []


def test_pending_delete_failure_cannot_resurrect_consumed_generation(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    (checkout / "checkpoint.txt").write_text("checkpoint\n", encoding="utf-8")
    checkpoint = store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )
    assert checkpoint is not None
    snapshot = str(checkpoint["snapshot_head"])
    pending_ref = _worktree_pending_recovery_ref(issue)
    recovery_ref = _worktree_recovery_ref(issue)
    # Recreate the supported publication-cleanup-failure state: both exact
    # copies point at A even though publication already succeeded.
    _git(checkout, "update-ref", pending_ref, snapshot)
    (checkout / "successor.txt").write_text("accepted\n", encoding="utf-8")
    _git(checkout, "add", "successor.txt")
    _git(checkout, "commit", "-m", "accepted successor")
    successor = _resolve(checkout, "HEAD")
    real_run = subprocess.run

    def fail_pending_delete(args, *positional, **kwargs):
        command = list(args)
        if command[:4] == ["git", "update-ref", "-d", pending_ref]:
            return subprocess.CompletedProcess(command, 1, "", "injected failure")
        return real_run(args, *positional, **kwargs)

    with patch("oompah.projects.subprocess.run", side_effect=fail_pending_delete):
        result = store.consume_worktree_recovery_if_incorporated(
            project.id,
            issue,
            successor,
            accepted_branch=issue,
            wt_path=str(checkout),
            expected_snapshot=snapshot,
        )

    assert result == "unknown"
    assert _resolve(project.repo_path, f"{recovery_ref}^{{commit}}") == snapshot
    assert _resolve(checkout, f"{pending_ref}^{{commit}}") == snapshot

    # A retry removes the source copy first and the authority last. Restart
    # discovery therefore cannot republish A after consumption is reported.
    assert store.consume_worktree_recovery_if_incorporated(
        project.id,
        issue,
        successor,
        accepted_branch=issue,
        wt_path=str(checkout),
        expected_snapshot=snapshot,
    ) == "consumed"
    restarted, _ = _store(tmp_path, Path(project.repo_path))
    assert restarted.pending_worktree_recoveries() == []


def test_pending_probe_failure_retains_authoritative_generation(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    (checkout / "checkpoint.txt").write_text("checkpoint\n", encoding="utf-8")
    checkpoint = store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )
    assert checkpoint is not None
    snapshot = str(checkpoint["snapshot_head"])
    pending_ref = _worktree_pending_recovery_ref(issue)
    recovery_ref = _worktree_recovery_ref(issue)
    _git(checkout, "update-ref", pending_ref, snapshot)
    (checkout / "successor.txt").write_text("accepted\n", encoding="utf-8")
    _git(checkout, "add", "successor.txt")
    _git(checkout, "commit", "-m", "accepted successor")
    successor = _resolve(checkout, "HEAD")
    real_run = subprocess.run

    def fail_pending_probe(args, *positional, **kwargs):
        command = list(args)
        if command[:5] == [
            "git",
            "show-ref",
            "--verify",
            "--quiet",
            pending_ref,
        ]:
            return subprocess.CompletedProcess(command, 128, "", "probe failed")
        return real_run(args, *positional, **kwargs)

    with patch("oompah.projects.subprocess.run", side_effect=fail_pending_probe):
        result = store.consume_worktree_recovery_if_incorporated(
            project.id,
            issue,
            successor,
            accepted_branch=issue,
            wt_path=str(checkout),
            expected_snapshot=snapshot,
        )

    assert result == "unknown"
    assert _resolve(project.repo_path, f"{recovery_ref}^{{commit}}") == snapshot
    assert _resolve(checkout, f"{pending_ref}^{{commit}}") == snapshot


def test_pending_recreation_and_post_delete_probe_failure_retain_authority(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    (checkout / "checkpoint.txt").write_text("checkpoint\n", encoding="utf-8")
    checkpoint = store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )
    assert checkpoint is not None
    snapshot = str(checkpoint["snapshot_head"])
    pending_ref = _worktree_pending_recovery_ref(issue)
    recovery_ref = _worktree_recovery_ref(issue)
    _git(checkout, "update-ref", pending_ref, snapshot)
    (checkout / "successor.txt").write_text("accepted\n", encoding="utf-8")
    _git(checkout, "add", "successor.txt")
    _git(checkout, "commit", "-m", "accepted successor")
    successor = _resolve(checkout, "HEAD")
    real_run = subprocess.run
    quiet_probes = 0

    def recreate_then_fail_post_delete_probe(args, *positional, **kwargs):
        nonlocal quiet_probes
        command = list(args)
        if command[:5] == [
            "git",
            "show-ref",
            "--verify",
            "--quiet",
            pending_ref,
        ]:
            quiet_probes += 1
            if quiet_probes == 2:
                real_run(
                    ["git", "update-ref", pending_ref, snapshot],
                    cwd=checkout,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return subprocess.CompletedProcess(command, 128, "", "probe failed")
        return real_run(args, *positional, **kwargs)

    with patch(
        "oompah.projects.subprocess.run",
        side_effect=recreate_then_fail_post_delete_probe,
    ):
        result = store.consume_worktree_recovery_if_incorporated(
            project.id,
            issue,
            successor,
            accepted_branch=issue,
            wt_path=str(checkout),
            expected_snapshot=snapshot,
        )

    assert result == "unknown"
    assert _resolve(project.repo_path, f"{recovery_ref}^{{commit}}") == snapshot
    assert _resolve(checkout, f"{pending_ref}^{{commit}}") == snapshot


def test_consumed_tombstone_blocks_recreation_after_final_absence_probe(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    (checkout / "checkpoint.txt").write_text("checkpoint\n", encoding="utf-8")
    checkpoint = store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )
    assert checkpoint is not None
    snapshot = str(checkpoint["snapshot_head"])
    pending_ref = _worktree_pending_recovery_ref(issue)
    recovery_ref = _worktree_recovery_ref(issue)
    consumed_ref = _worktree_consumed_recovery_ref(issue, snapshot)
    _git(checkout, "update-ref", pending_ref, snapshot)
    (checkout / "successor.txt").write_text("accepted\n", encoding="utf-8")
    _git(checkout, "add", "successor.txt")
    _git(checkout, "commit", "-m", "accepted successor")
    successor = _resolve(checkout, "HEAD")
    real_run = subprocess.run
    quiet_probes = 0

    def recreate_after_proven_absence(args, *positional, **kwargs):
        nonlocal quiet_probes
        command = list(args)
        result = real_run(args, *positional, **kwargs)
        if command[:5] == [
            "git",
            "show-ref",
            "--verify",
            "--quiet",
            pending_ref,
        ]:
            quiet_probes += 1
            if quiet_probes == 2:
                assert result.returncode == 1
                real_run(
                    ["git", "update-ref", pending_ref, snapshot],
                    cwd=checkout,
                    capture_output=True,
                    text=True,
                    check=True,
                )
        return result

    with patch(
        "oompah.projects.subprocess.run",
        side_effect=recreate_after_proven_absence,
    ):
        result = store.consume_worktree_recovery_if_incorporated(
            project.id,
            issue,
            successor,
            accepted_branch=issue,
            wt_path=str(checkout),
            expected_snapshot=snapshot,
        )

    assert result == "consumed"
    assert _git(
        project.repo_path,
        "show-ref",
        "--verify",
        "--quiet",
        recovery_ref,
        check=False,
    ).returncode == 1
    assert _resolve(project.repo_path, f"{consumed_ref}^{{commit}}") == snapshot
    assert _resolve(checkout, f"{pending_ref}^{{commit}}") == snapshot

    restarted, _ = _store(tmp_path, Path(project.repo_path))
    assert restarted.pending_worktree_recoveries() == []
    assert restarted.worktree_recovery_context(project.id, issue) is None


def test_restart_consumes_successor_from_authoritative_branch(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    (checkout / "checkpoint.txt").write_text("checkpoint\n", encoding="utf-8")
    checkpoint = store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )
    assert checkpoint is not None
    snapshot = str(checkpoint["snapshot_head"])
    (checkout / "successor.txt").write_text("accepted\n", encoding="utf-8")
    _git(checkout, "add", "successor.txt")
    _git(checkout, "commit", "-m", "accepted successor")
    successor = _resolve(checkout, "HEAD")
    _git(checkout, "push", "origin", f"HEAD:refs/heads/{issue}")

    restarted, _ = _store(tmp_path, Path(project.repo_path))
    assert restarted.consume_worktree_recovery_if_incorporated(
        project.id,
        issue,
        successor,
        accepted_branch=issue,
        wt_path=None,
        expected_snapshot=snapshot,
    ) == "consumed"
    assert restarted.worktree_recovery_context(project.id, issue) is None


def test_missing_object_update_ref_reproduction_then_transfer(tmp_path):
    _store_value, project, checkout = _standalone_task(tmp_path)
    (checkout / "new.txt").write_text("new graph\n", encoding="utf-8")
    _git(checkout, "add", "new.txt")
    _git(checkout, "commit", "-m", "standalone commit")
    snapshot = _resolve(checkout, "HEAD")
    recovery_ref = _worktree_recovery_ref("TASK-MISSING")

    failed = _git(
        project.repo_path,
        "update-ref",
        recovery_ref,
        snapshot,
        check=False,
    )
    assert failed.returncode != 0
    assert "nonexistent object" in failed.stderr

    assert _transfer_recovery_snapshot_objects(
        snapshot,
        str(checkout),
        project.repo_path,
    ) is True
    assert _resolve(project.repo_path, f"{snapshot}^{{commit}}") == snapshot
    assert _transfer_recovery_snapshot_objects(
        snapshot,
        str(checkout),
        project.repo_path,
    ) is False


def test_transfer_requires_exact_commit_not_blob_or_abbreviation(tmp_path):
    _store_value, project, checkout = _standalone_task(tmp_path)
    snapshot = _resolve(checkout, "HEAD")
    blob = _resolve(checkout, "HEAD:base.txt")

    with pytest.raises(ProjectError, match="full hexadecimal"):
        _transfer_recovery_snapshot_objects(
            snapshot[:12], str(checkout), project.repo_path
        )
    with pytest.raises(ProjectError, match="not an exact commit"):
        _transfer_recovery_snapshot_objects(
            blob, str(checkout), project.repo_path
        )


def test_interrupted_transfer_retries_same_checkpoint_after_restart(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    changed = checkout / "interrupted.txt"
    changed.write_text("retained exactly\n", encoding="utf-8")

    with patch(
        "oompah.projects._transfer_recovery_snapshot_objects",
        side_effect=ProjectError("simulated transfer interruption"),
    ):
        with pytest.raises(RecoveryPublicationError) as raised:
            store.preserve_worktree_changes(
                project.id, issue, str(checkout), issue
            )

    pending = raised.value.context
    checkpoint = str(pending["snapshot_head"])
    assert _resolve(checkout, "HEAD") == checkpoint
    assert changed.read_text(encoding="utf-8") == "retained exactly\n"
    assert _resolve(
        checkout,
        f"{_worktree_pending_recovery_ref(issue)}^{{commit}}",
    ) == checkpoint
    assert _git(
        project.repo_path,
        "rev-parse",
        "--verify",
        _worktree_recovery_ref(issue),
        check=False,
    ).returncode != 0
    pending_context = store.worktree_recovery_context(project.id, issue)
    assert pending_context is not None
    assert pending_context["publication_state"] == "pending"
    assert pending_context["snapshot_head"] == checkpoint

    restarted, _ = _store(tmp_path, Path(project.repo_path))
    recovered = restarted.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )

    assert recovered is not None
    assert recovered["snapshot_head"] == checkpoint
    assert _resolve(checkout, "HEAD") == checkpoint
    assert _resolve(
        project.repo_path,
        f"{_worktree_recovery_ref(issue)}^{{commit}}",
    ) == checkpoint


def test_restart_discovery_finds_source_local_pending_checkpoint(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    (checkout / "restart.txt").write_text("survives restart\n", encoding="utf-8")

    with patch(
        "oompah.projects._transfer_recovery_snapshot_objects",
        side_effect=ProjectError("authority unavailable"),
    ):
        with pytest.raises(RecoveryPublicationError) as raised:
            store.preserve_worktree_changes(project.id, issue, str(checkout), issue)

    restarted, _ = _store(tmp_path, Path(project.repo_path))
    pending = restarted.pending_worktree_recoveries()

    assert len(pending) == 1
    assert pending[0]["project_id"] == project.id
    assert pending[0]["issue_identifier"] == issue
    assert pending[0]["snapshot_head"] == raised.value.context["snapshot_head"]
    assert Path(str(pending[0]["worktree_path"])).resolve() == checkout.resolve()


def test_temporary_transfer_ref_timeout_is_typed_publication_failure(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    (checkout / "timeout.txt").write_text("retained\n", encoding="utf-8")
    real_run = subprocess.run

    def timeout_transfer_ref(args, *positional, **kwargs):
        command = list(args)
        if (
            command[:2] == ["git", "update-ref"]
            and len(command) > 2
            and str(command[2]).startswith("refs/oompah/recovery-transfer/")
        ):
            raise subprocess.TimeoutExpired(command, 10)
        return real_run(args, *positional, **kwargs)

    with patch("oompah.projects.subprocess.run", side_effect=timeout_transfer_ref):
        with pytest.raises(RecoveryPublicationError, match="make recovery checkpoint durable"):
            store.preserve_worktree_changes(project.id, issue, str(checkout), issue)

    assert _resolve(
        checkout,
        f"{_worktree_pending_recovery_ref(issue)}^{{commit}}",
    )


def test_interrupted_ref_publication_never_resets_checkout(tmp_path):
    store, project, checkout = _standalone_task(tmp_path)
    issue = "TASK-RECOVERY"
    (checkout / "ref-failure.txt").write_text("preserved\n", encoding="utf-8")
    recovery_ref = _worktree_recovery_ref(issue)
    real_run = subprocess.run
    calls: list[list[str]] = []
    failed = False

    def fail_first_authoritative_ref(args, *positional, **kwargs):
        nonlocal failed
        command = list(args)
        calls.append(command)
        if (
            not failed
            and command[:3] == ["git", "update-ref", recovery_ref]
            and Path(kwargs.get("cwd", "")).resolve()
            == Path(project.repo_path).resolve()
        ):
            failed = True
            return subprocess.CompletedProcess(command, 1, "", "interrupted")
        return real_run(args, *positional, **kwargs)

    with patch("oompah.projects.subprocess.run", side_effect=fail_first_authoritative_ref):
        with pytest.raises(RecoveryPublicationError) as raised:
            store.preserve_worktree_changes(
                project.id, issue, str(checkout), issue
            )

    checkpoint = str(raised.value.context["snapshot_head"])
    assert _resolve(checkout, "HEAD") == checkpoint
    assert (checkout / "ref-failure.txt").read_text(encoding="utf-8") == "preserved\n"
    assert not any(command[:2] in (["git", "reset"], ["git", "clean"]) for command in calls)

    recovered = store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )
    assert recovered is not None
    assert recovered["snapshot_head"] == checkpoint
    assert _resolve(project.repo_path, f"{recovery_ref}^{{commit}}") == checkpoint


def test_standalone_active_rebase_checkpoint_preserves_operation(tmp_path):
    store, project, checkout = _standalone_task(tmp_path, "TASK-REBASE")
    issue = "TASK-REBASE"
    (checkout / "base.txt").write_text("task\n", encoding="utf-8")
    _git(checkout, "add", "base.txt")
    _git(checkout, "commit", "-m", "task change")
    task_branch_head = _resolve(checkout, f"refs/heads/{issue}")

    authority = Path(project.repo_path)
    (authority / "base.txt").write_text("main\n", encoding="utf-8")
    _git(authority, "add", "base.txt")
    _git(authority, "commit", "-m", "main change")
    _git(checkout, "fetch", "origin")
    rebased = _git(checkout, "rebase", "origin/main", check=False)
    assert rebased.returncode != 0
    (checkout / "base.txt").write_text("resolved\n", encoding="utf-8")
    _git(checkout, "add", "base.txt")
    detached_head = _resolve(checkout, "HEAD")
    git_dir = Path(_git(checkout, "rev-parse", "--git-dir").stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (checkout / git_dir).resolve()
    operation_path = git_dir / "rebase-merge"
    assert operation_path.is_dir()

    context = store.preserve_worktree_changes(
        project.id, issue, str(checkout), issue
    )

    assert context is not None
    assert context["operation"]["kind"] == "rebase"
    assert _resolve(checkout, "HEAD") == detached_head
    assert _resolve(checkout, f"refs/heads/{issue}") == task_branch_head
    assert operation_path.is_dir()
    assert _git(
        project.repo_path,
        "show",
        f"{context['snapshot_head']}:base.txt",
    ).stdout == "resolved\n"
    assert _resolve(
        project.repo_path,
        f"{context['recovery_ref']}^{{commit}}",
    ) == context["snapshot_head"]
    assert store.consume_worktree_recovery_if_incorporated(
        project.id,
        issue,
        detached_head,
        accepted_branch=issue,
        wt_path=str(checkout),
        expected_snapshot=str(context["snapshot_head"]),
    ) == "current"
    assert _resolve(
        project.repo_path,
        f"{context['recovery_ref']}^{{commit}}",
    ) == context["snapshot_head"]


def test_active_operation_pending_ref_failure_is_manual_not_retryable(tmp_path):
    """An unreachable commit-tree object cannot masquerade as durable evidence."""

    store, project, checkout = _standalone_task(tmp_path, "TASK-REBASE")
    issue = "TASK-REBASE"
    (checkout / "base.txt").write_text("task\n", encoding="utf-8")
    _git(checkout, "add", "base.txt")
    _git(checkout, "commit", "-m", "task change")
    authority = Path(project.repo_path)
    (authority / "base.txt").write_text("main\n", encoding="utf-8")
    _git(authority, "add", "base.txt")
    _git(authority, "commit", "-m", "main change")
    _git(checkout, "fetch", "origin")
    assert _git(checkout, "rebase", "origin/main", check=False).returncode != 0
    (checkout / "base.txt").write_text("resolved\n", encoding="utf-8")
    _git(checkout, "add", "base.txt")
    detached_head = _resolve(checkout, "HEAD")
    git_dir = Path(_git(checkout, "rev-parse", "--git-dir").stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (checkout / git_dir).resolve()
    real_run = subprocess.run
    pending_ref = _worktree_pending_recovery_ref(issue)

    def timeout_pending_ref(args, *positional, **kwargs):
        command = list(args)
        if command[:3] == ["git", "update-ref", pending_ref]:
            raise subprocess.TimeoutExpired(command, 10)
        return real_run(args, *positional, **kwargs)

    with patch("oompah.projects.subprocess.run", side_effect=timeout_pending_ref):
        with pytest.raises(ProjectError, match="not durably discoverable") as raised:
            store.preserve_worktree_changes(project.id, issue, str(checkout), issue)

    assert not isinstance(raised.value, RecoveryPublicationError)
    assert _resolve(checkout, "HEAD") == detached_head
    assert (git_dir / "rebase-merge").is_dir()
