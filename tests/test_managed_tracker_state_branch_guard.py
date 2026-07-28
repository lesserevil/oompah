"""Regression coverage for managed tracker state-branch write isolation."""

from __future__ import annotations

import asyncio
import subprocess
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from oompah.agent_profile_store import AgentProfileStore
from oompah.config import ServiceConfig
from oompah.error_watcher import ErrorWatcher
from oompah.models import Issue, Project
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.orchestrator import Orchestrator
from oompah.projects import ProjectError, ProjectStore
from oompah.providers import ProviderStore
from oompah.roles import RoleStore
from oompah.statuses import ARCHIVED, DONE, OPEN
from oompah.tracker import TrackerError


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _code_checkout_snapshot(repo: Path, remote: Path) -> dict[str, str]:
    """Capture every tracked code-checkout surface maintenance must preserve."""
    return {
        "head": _git(repo, "rev-parse", "HEAD"),
        "branch": _git(repo, "symbolic-ref", "--short", "HEAD"),
        "worktree": _git(repo, "status", "--porcelain=v2"),
        "worktree_diff": _git(repo, "diff", "--binary"),
        "index": _git(repo, "diff", "--cached", "--binary"),
        "origin_default": _git(repo, "rev-parse", "refs/remotes/origin/main"),
        "remote_default": _git(remote, "rev-parse", "refs/heads/main"),
    }


def _assert_no_live_owned_pool_threads(orch: Orchestrator) -> None:
    """Ensure an orchestrator shutdown did not leave executor workers alive."""
    assert all(not thread.is_alive() for thread in orch._tick_pool._threads)
    assert all(not thread.is_alive() for thread in orch._refresh_pool._threads)


def _make_project(
    repo: Path,
    *,
    project_id: str = "proj-state-guard",
    state_branch_enabled: bool = True,
) -> Project:
    return Project(
        id=project_id,
        name="state-guard",
        repo_url=str(repo),
        repo_path=str(repo),
        default_branch="main",
        tracker_kind="oompah_md",
        state_branch_enabled=state_branch_enabled,
    )


def _make_project_store(tmp_path: Path, project: Project) -> ProjectStore:
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    store._projects[project.id] = project
    store._save()
    return store


def _make_orchestrator(
    tmp_path: Path,
    project: Project,
    *,
    workflow_root: Path | None = None,
) -> Orchestrator:
    provider_store = ProviderStore(path=str(tmp_path / "providers.json"))
    return Orchestrator(
        config=ServiceConfig(),
        workflow_path=str((workflow_root or Path(project.repo_path)) / "WORKFLOW.md"),
        provider_store=provider_store,
        project_store=_make_project_store(tmp_path, project),
        agent_profile_store=AgentProfileStore(
            path=str(tmp_path / "agent_profiles.json")
        ),
        role_store=RoleStore(
            path=str(tmp_path / "roles.json"),
            provider_store=provider_store,
        ),
        state_path=str(tmp_path / "state.json"),
    )


class _NoopTimer:
    def __init__(self, *_args, **_kwargs) -> None:
        self.daemon = False

    def start(self) -> None:
        return None

    def cancel(self) -> None:
        return None


@pytest.fixture
def guarded_tracker(tmp_path: Path) -> OompahMarkdownTracker:
    return OompahMarkdownTracker(
        active_states=[OPEN],
        terminal_states=[DONE],
        cwd=str(tmp_path),
        git_sync=False,
        allow_default_branch_task_writes=False,
    )


@pytest.mark.parametrize(
    ("operation", "mutate"),
    [
        (
            "create",
            lambda tracker: tracker.create_issue(
                title="must not be written",
                description="guard regression",
            ),
        ),
        ("update", lambda tracker: tracker.update_issue("TASK-1", status=DONE)),
        ("archive", lambda tracker: tracker.archive_issue("TASK-1")),
        (
            "comment",
            lambda tracker: tracker.add_comment("TASK-1", "must not be written"),
        ),
        ("label", lambda tracker: tracker.add_label("TASK-1", "blocked")),
        (
            "parent",
            lambda tracker: tracker.add_parent_child("TASK-1", "EPIC-1"),
        ),
        (
            "dependency",
            lambda tracker: tracker.add_dependency("TASK-1", "TASK-2"),
        ),
        (
            "attachments",
            lambda tracker: tracker.set_attachments("TASK-1", []),
        ),
        (
            "metadata",
            lambda tracker: tracker.set_metadata_field(
                "TASK-1", "oompah.work_branch", "work"
            ),
        ),
        (
            "raw body",
            lambda tracker: tracker.set_raw_body("TASK-1", "replacement"),
        ),
        (
            "external import index",
            lambda tracker: tracker.record_external_import(
                "owner/repo#1", "TASK-1"
            ),
        ),
    ],
)
def test_unscoped_guard_rejects_every_task_mutation_before_writing(
    guarded_tracker: OompahMarkdownTracker,
    operation: str,
    mutate,
) -> None:
    root = guarded_tracker.root_path

    with pytest.raises(
        TrackerError,
        match="Refusing an unscoped native task write",
    ):
        mutate(guarded_tracker)

    assert not (root / ".oompah").exists(), operation


def test_unscoped_guard_does_not_block_non_task_ledger(
    guarded_tracker: OompahMarkdownTracker,
) -> None:
    guarded_tracker.write_and_commit_ledger_file(
        ".oompah/release-deliveries.yml",
        "version: 1\n",
        "Update release delivery ledger",
    )

    assert (
        guarded_tracker.root_path / ".oompah" / "release-deliveries.yml"
    ).read_text(encoding="utf-8") == "version: 1\n"


def test_state_branch_tracker_remains_writable_when_default_branch_is_forbidden(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state-worktree"
    state_root.mkdir()
    tracker = OompahMarkdownTracker(
        active_states=[OPEN],
        terminal_states=[DONE],
        cwd=str(tmp_path / "code"),
        git_sync=False,
        state_branch_enabled=True,
        state_branch_name="oompah/state/proj-test",
        allow_default_branch_task_writes=False,
        _checkpoint_timer_factory=_NoopTimer,
    )
    tracker._state_root = state_root

    issue = tracker.create_issue(
        title="state-only",
        description="written through the configured state tracker",
    )

    assert issue.identifier
    assert list((state_root / ".oompah" / "tasks" / "backlog").glob("*.md"))
    assert not (tmp_path / "code" / ".oompah").exists()


def test_orchestrator_global_tracker_is_read_only_in_managed_mode(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    project = _make_project(repo)
    orch = _make_orchestrator(tmp_path, project)

    assert isinstance(orch.tracker, OompahMarkdownTracker)
    assert orch.tracker.allow_default_branch_task_writes is False

    project_tracker = orch._tracker_for_project(project.id)
    assert isinstance(project_tracker, OompahMarkdownTracker)
    assert project_tracker.state_branch_enabled is True
    assert project_tracker.allow_default_branch_task_writes is False

    with pytest.raises(TrackerError, match="unscoped native task write"):
        orch.tracker.create_issue(
            title="wrong tracker",
            description="must fail before touching the code checkout",
        )
    assert not (repo / ".oompah").exists()


def test_management_tracker_resolves_the_workflow_project_by_canonical_id(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    project = _make_project(repo)
    orch = _make_orchestrator(tmp_path, project)

    tracker, project_id = orch._management_tracker_scope()

    assert project_id == project.id
    assert tracker is orch._tracker_for_project(project.id)
    assert tracker is not orch.tracker


def test_management_tracker_refuses_to_guess_when_workflow_is_unregistered(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    unrelated = tmp_path / "unregistered"
    unrelated.mkdir()
    project = _make_project(repo)
    orch = _make_orchestrator(tmp_path, project, workflow_root=unrelated)

    with pytest.raises(ProjectError, match="Cannot resolve.*management tracker"):
        orch._management_tracker_scope()

    with pytest.raises(ProjectError, match="refusing to use the unscoped"):
        orch._tracker_for_issue(
            Issue(
                id="unscoped",
                identifier="TASK-UNSCOPED",
                title="ambiguous management issue",
            )
        )
    assert not (repo / ".oompah").exists()


def _init_remote_with_state_branch(tmp_path: Path) -> tuple[Path, Path, str]:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare")

    repo = tmp_path / "code"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test Agent")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "README.md").write_text("# state guard\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "Initial code")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-u", "origin", "main")

    state_branch = "oompah/state/proj-state-guard"
    _git(repo, "switch", "--orphan", state_branch)
    (repo / "README.md").unlink(missing_ok=True)
    tasks_root = repo / ".oompah" / "tasks"
    (tasks_root / "backlog").mkdir(parents=True)
    (tasks_root / "backlog" / ".gitkeep").write_text("", encoding="utf-8")
    (tasks_root / "config.yml").write_text(
        "task_prefix: GUARD\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "Bootstrap state branch")
    _git(repo, "push", "-u", "origin", state_branch)
    _git(repo, "switch", "main")
    return repo, remote, state_branch


def test_auto_archive_and_shutdown_leave_code_branch_untouched(
    tmp_path: Path,
) -> None:
    repo, remote, state_branch = _init_remote_with_state_branch(tmp_path)
    project = _make_project(repo)
    orch = _make_orchestrator(tmp_path, project)
    tracker = orch._tracker_for_project(project.id)
    assert isinstance(tracker, OompahMarkdownTracker)

    old_timestamp = "2026-07-01T00:00:00+00:00"
    with patch("oompah.oompah_md_tracker._now_iso", return_value=old_timestamp):
        issue = tracker.create_issue(
            title="archive from state branch",
            description="maintenance must not touch main",
            initial_status=DONE,
        )
    assert tracker.flush_checkpoint(reason="test-seed") == 1

    code_before = _code_checkout_snapshot(repo, remote)
    state_before = _git(remote, "rev-parse", f"refs/heads/{state_branch}")

    orch._do_auto_archive()

    archived = tracker.fetch_issue_detail(issue.identifier)
    assert archived is not None
    assert archived.state == ARCHIVED
    state_after = _git(remote, "rev-parse", f"refs/heads/{state_branch}")
    assert state_after != state_before
    assert _code_checkout_snapshot(repo, remote) == code_before

    state_paths = _git(
        remote,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        state_before,
        state_after,
    ).splitlines()
    assert state_paths
    assert all(path.startswith(".oompah/tasks/") for path in state_paths)

    with pytest.raises(TrackerError, match="unscoped native task write"):
        orch.tracker.create_issue(
            title="escaped maintenance",
            description="the global tracker must fail before changing main",
        )
    assert _code_checkout_snapshot(repo, remote) == code_before

    asyncio.run(orch.stop())
    assert orch._maintenance_future is None or orch._maintenance_future.done()
    assert (
        orch._epic_maintenance_future is None
        or orch._epic_maintenance_future.done()
    )
    _assert_no_live_owned_pool_threads(orch)


def test_server_error_watcher_and_scheduler_write_only_to_state_branch(
    tmp_path: Path,
) -> None:
    """Server startup and background archive mutations share the state tracker."""
    repo, remote, state_branch = _init_remote_with_state_branch(tmp_path)
    project = _make_project(repo)
    orch = _make_orchestrator(tmp_path, project)
    tracker = orch._tracker_for_project(project.id)
    assert isinstance(tracker, OompahMarkdownTracker)

    # Exercise the actual server startup consumer that creates the global
    # ErrorWatcher.  Unrelated startup migrations are covered separately and
    # are suppressed here so this test remains focused on tracker routing.
    import oompah.server as server

    with (
        patch.object(server, "remove_draft_labels_from_epics", return_value=0),
        patch.object(server, "_migrate_release_picks_on_startup"),
        patch.object(server, "ProjectLogWatcherManager") as watcher_manager,
    ):
        server.set_orchestrator(orch)
        watcher_manager.return_value.sync_watchers.assert_called_once()

    watcher = server._error_watcher
    assert isinstance(watcher, ErrorWatcher)
    assert watcher._tracker is tracker
    assert watcher._project_id == project.id

    try:
        error_id = watcher.report_error(
            source="backend",
            message="state-branch maintenance regression",
            detail="The error watcher must not write the service checkout.",
        )
        assert error_id
        # ErrorWatcher creates a deferred task, so flush it before taking the
        # state-branch baseline.  The scheduler mutation below must advance it
        # again while the code checkout remains byte-for-byte unchanged.
        assert tracker.flush_checkpoint(reason="test-error-watcher") == 1

        old_timestamp = "2026-07-01T00:00:00+00:00"
        with patch("oompah.oompah_md_tracker._now_iso", return_value=old_timestamp):
            archived_id = tracker.create_issue(
                title="archive from scheduler",
                description="maintenance must use the project tracker",
                initial_status=DONE,
            )
        assert archived_id.identifier
        assert tracker.flush_checkpoint(reason="test-seed") == 1

        code_before = _code_checkout_snapshot(repo, remote)
        state_before = _git(remote, "rev-parse", f"refs/heads/{state_branch}")

        # Run the actual maintenance wrapper used by _tick(), keeping the
        # other independent jobs inert so only archive performs a durable
        # mutation in this focused end-to-end test.
        orch._maybe_heal_repos = lambda: None
        orch._maybe_cleanup_worktrees = lambda: None
        orch._maybe_open_deferred_done_reviews = lambda: None
        orch._maybe_run_merged_labels = lambda: None
        orch._maybe_run_release_pick_reconciliation = lambda: None
        orch._maybe_sync_github_issue_intake = lambda: None
        orch._maybe_run_stalled_task_watchdog = lambda: None
        orch._run_step5b_maintenance()

        archived = tracker.fetch_issue_detail(archived_id.identifier)
        assert archived is not None
        assert archived.state == ARCHIVED
        error_task = tracker.fetch_issue_detail(error_id)
        assert error_task is not None
        assert error_task.state == "Backlog"

        state_after = _git(remote, "rev-parse", f"refs/heads/{state_branch}")
        assert state_after != state_before
        assert _code_checkout_snapshot(repo, remote) == code_before
        state_paths = _git(
            remote,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            state_before,
            state_after,
        ).splitlines()
        assert state_paths
        assert all(path.startswith(".oompah/tasks/") for path in state_paths)
        state_root = tracker._state_root
        assert state_root is not None
        error_paths = list(tracker.tasks_root.rglob(f"{error_id}.md"))
        assert len(error_paths) == 1
        error_path = error_paths[0].relative_to(state_root).as_posix()
        error_body = _git(remote, "show", f"{state_after}:{error_path}")
        assert "state-branch maintenance regression" in error_body
    finally:
        watcher.uninstall_log_handler("oompah")
        server._error_watcher = None
        server._log_watcher_manager = None
        asyncio.run(orch.stop())
        _assert_no_live_owned_pool_threads(orch)


def test_stop_drains_blocked_maintenance_future_and_owned_executors(
    tmp_path: Path,
) -> None:
    """A scheduler stop waits for maintenance before releasing test fixtures."""
    repo = tmp_path / "repo"
    repo.mkdir()
    orch = _make_orchestrator(tmp_path, _make_project(repo, state_branch_enabled=False))
    started = threading.Event()
    release = threading.Event()

    def blocked_maintenance() -> None:
        started.set()
        assert release.wait(timeout=5), "maintenance future was not released"

    orch._run_step5b_maintenance = blocked_maintenance
    orch._run_step5c_epic_maintenance = lambda: None
    async def async_noop() -> None:
        return None

    async def async_yolo_noop() -> float:
        return 0.0

    orch._recover_release_addendum_leases = lambda: None
    orch._handle_reconcile = async_noop
    orch._handle_review_check = async_noop
    orch._handle_dispatch_needed = async_noop
    orch._handle_yolo_review = async_yolo_noop
    orch._handle_auto_update = async_noop
    orch._notify_observers = lambda: None
    orch._maybe_run_watchdog = lambda: None

    async def run_and_stop() -> None:
        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            await orch._tick()
        assert orch._maintenance_future is not None
        assert await asyncio.to_thread(started.wait, 2)
        stop_task = asyncio.create_task(orch.stop())
        await asyncio.sleep(0.01)
        assert not stop_task.done()
        release.set()
        await asyncio.wait_for(stop_task, timeout=5)

    asyncio.run(run_and_stop())
    assert orch._maintenance_future is not None
    assert orch._maintenance_future.done()
    assert orch._epic_maintenance_future is not None
    assert orch._epic_maintenance_future.done()
    _assert_no_live_owned_pool_threads(orch)
