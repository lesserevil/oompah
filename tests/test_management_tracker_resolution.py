"""Regression tests for identity-safe management tracker resolution."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from oompah.agent_profile_store import AgentProfileStore
from oompah.config import ServiceConfig
from oompah.models import Project
from oompah.orchestrator import Orchestrator
from oompah.projects import (
    ProjectError,
    ProjectStore,
    canonical_repository_identity,
)
from oompah.providers import ProviderStore
from oompah.roles import RoleStore


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repository_topology(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return (remote, managed clone, service clone)."""

    remote = tmp_path / "oompah.git"
    _git(tmp_path, "init", "--bare", str(remote))

    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-b", "main")
    _git(seed, "config", "user.name", "Test Agent")
    _git(seed, "config", "user.email", "test@example.com")
    (seed / "README.md").write_text("# oompah\n", encoding="utf-8")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "initial")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-u", "origin", "main")

    managed = tmp_path / "managed"
    service = tmp_path / "service"
    _git(tmp_path, "clone", "--branch", "main", str(remote), str(managed))
    _git(tmp_path, "clone", "--branch", "main", str(remote), str(service))
    for checkout in (managed, service):
        _git(checkout, "config", "user.name", "Test Agent")
        _git(checkout, "config", "user.email", "test@example.com")
    (service / "WORKFLOW.md").write_text("# test workflow\n", encoding="utf-8")
    return remote, managed, service


def _project_store(tmp_path: Path, projects: list[Project]) -> ProjectStore:
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    store._projects = {project.id: project for project in projects}
    store._save()
    return store


def _orchestrator(
    tmp_path: Path,
    project_store: ProjectStore,
    workflow_root: Path,
) -> Orchestrator:
    provider_store = ProviderStore(path=str(tmp_path / "providers.json"))
    return Orchestrator(
        config=ServiceConfig(),
        workflow_path=str(workflow_root / "WORKFLOW.md"),
        provider_store=provider_store,
        project_store=project_store,
        agent_profile_store=AgentProfileStore(
            path=str(tmp_path / "agent_profiles.json")
        ),
        role_store=RoleStore(
            path=str(tmp_path / "roles.json"),
            provider_store=provider_store,
        ),
        state_path=str(tmp_path / "state.json"),
    )


def _project(repo: Path, project_id: str, repo_url: str) -> Project:
    return Project(
        id=project_id,
        name=project_id,
        repo_url=repo_url,
        repo_path=str(repo),
        tracker_kind="oompah_md",
    )


def test_canonical_repository_identity_equates_common_clone_urls() -> None:
    expected = "github.com/lesserevil/oompah"
    clone_urls = (
        "http://github.com:80/lesserevil/oompah.git",
        "https://git@GitHub.com:443/lesserevil/oompah.git",
        "ssh://git@github.com:22/lesserevil/oompah.git",
        "git://github.com:9418/lesserevil/oompah.git",
        "git@github.com:lesserevil/oompah.git",
    )

    assert {
        canonical_repository_identity(clone_url) for clone_url in clone_urls
    } == {expected}
    assert (
        canonical_repository_identity(
            "https://github.com:8443/lesserevil/oompah.git"
        )
        == "github.com:8443/lesserevil/oompah"
    )
    assert canonical_repository_identity("custom://github.com/org/repo") is None
    assert (
        canonical_repository_identity("https://github.com/org/repo?tenant=one")
        is None
    )
    assert canonical_repository_identity(42) is None  # type: ignore[arg-type]
    assert canonical_repository_identity(
        "https://github.com/org/a%2Frepo"
    ) != canonical_repository_identity("https://github.com/org/a/repo")


def test_relative_local_remote_identity_is_checkout_scoped(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    assert canonical_repository_identity(
        "mirror.git", base_dir=first
    ) == f"file://{first / 'mirror.git'}"
    assert canonical_repository_identity(
        "mirror.git", base_dir=second
    ) == f"file://{second / 'mirror.git'}"


def test_canonical_service_clone_maps_to_registered_project(tmp_path: Path) -> None:
    remote, managed, service = _repository_topology(tmp_path)
    project = _project(managed, "proj-oompah", str(remote))
    orch = _orchestrator(
        tmp_path,
        _project_store(tmp_path, [project]),
        service,
    )

    tracker, project_id = orch._management_tracker_scope()

    assert project_id == project.id
    assert tracker is orch._tracker_for_project(project.id)
    assert tracker is not orch.tracker
    asyncio.run(orch.stop())


def test_cached_mirror_maps_only_by_matching_remote_identity(tmp_path: Path) -> None:
    remote, _managed, service = _repository_topology(tmp_path)
    mirror = tmp_path / "managed-mirror.git"
    _git(tmp_path, "clone", "--mirror", str(remote), str(mirror))
    project = _project(mirror, "proj-oompah", str(remote))
    orch = _orchestrator(
        tmp_path,
        _project_store(tmp_path, [project]),
        service,
    )

    _tracker, project_id = orch._management_tracker_scope()

    assert project_id == project.id
    asyncio.run(orch.stop())


def test_service_startup_enables_global_error_watcher_for_clone_alias(
    tmp_path: Path,
) -> None:
    remote, managed, service = _repository_topology(tmp_path)
    project = _project(managed, "proj-oompah", str(remote))
    orch = _orchestrator(tmp_path, _project_store(tmp_path, [project]), service)

    import oompah.server as server
    from oompah.error_watcher import ErrorWatcher

    server._error_watcher = None
    orch._alerts.append(
        {
            "source": "management_tracker_resolution",
            "level": "error",
            "message": "stale startup failure",
        }
    )
    saved_orchestrator = server._orchestrator
    try:
        with (
            patch.object(server, "remove_draft_labels_from_epics", return_value=0),
            patch.object(server, "_migrate_release_picks_on_startup"),
            patch.object(server, "ProjectLogWatcherManager", MagicMock()),
        ):
            server.set_orchestrator(orch)

        watcher = server._error_watcher
        assert isinstance(watcher, ErrorWatcher)
        assert watcher._tracker is orch._tracker_for_project(project.id)
        assert watcher._project_id == project.id
        assert not any(
            alert.get("source") == "management_tracker_resolution"
            for alert in orch._alerts
        )
    finally:
        if isinstance(server._error_watcher, ErrorWatcher):
            server._error_watcher.uninstall_log_handler("oompah")
        server._orchestrator = saved_orchestrator
        server._error_watcher = None
        server._log_watcher_manager = None
        asyncio.run(orch.stop())


def test_agent_worktree_alias_maps_only_with_matching_repository_identity(
    tmp_path: Path,
) -> None:
    remote, managed, _service = _repository_topology(tmp_path)
    alias = tmp_path / "agent-worktree"
    _git(managed, "worktree", "add", "--detach", str(alias), "main")
    (alias / "WORKFLOW.md").write_text("# test workflow\n", encoding="utf-8")

    project = _project(managed, "proj-oompah", str(remote))
    orch = _orchestrator(tmp_path, _project_store(tmp_path, [project]), alias)

    _tracker, project_id = orch._management_tracker_scope()

    assert project_id == project.id
    asyncio.run(orch.stop())


def test_shared_worktree_maps_with_explicit_local_repository_authority(
    tmp_path: Path,
) -> None:
    _remote, managed, _service = _repository_topology(tmp_path)
    alias = tmp_path / "agent-worktree"
    _git(managed, "worktree", "add", "--detach", str(alias), "main")
    (alias / "WORKFLOW.md").write_text("# test workflow\n", encoding="utf-8")

    project = _project(managed, "proj-oompah", str(managed))
    orch = _orchestrator(tmp_path, _project_store(tmp_path, [project]), alias)

    _tracker, project_id = orch._management_tracker_scope()

    assert project_id == project.id
    asyncio.run(orch.stop())


def test_foreign_checkout_at_configured_path_is_rejected(tmp_path: Path) -> None:
    remote, _managed, foreign = _repository_topology(tmp_path)
    foreign_remote = tmp_path / "foreign.git"
    _git(tmp_path, "init", "--bare", str(foreign_remote))
    _git(foreign, "remote", "set-url", "origin", str(foreign_remote))
    (foreign / "WORKFLOW.md").write_text("# foreign\n", encoding="utf-8")

    project = _project(foreign, "proj-oompah", str(remote))
    orch = _orchestrator(tmp_path, _project_store(tmp_path, [project]), foreign)

    with pytest.raises(ProjectError, match="management tracker safely"):
        orch._management_tracker_scope()
    asyncio.run(orch.stop())


def test_foreign_service_clone_is_rejected_for_valid_managed_checkout(
    tmp_path: Path,
) -> None:
    remote, managed, service = _repository_topology(tmp_path)
    foreign_remote = tmp_path / "foreign.git"
    _git(tmp_path, "init", "--bare", str(foreign_remote))
    _git(service, "remote", "set-url", "origin", str(foreign_remote))

    project = _project(managed, "proj-oompah", str(remote))
    orch = _orchestrator(tmp_path, _project_store(tmp_path, [project]), service)

    with pytest.raises(ProjectError, match="matching project IDs: none"):
        orch._management_tracker_scope()
    asyncio.run(orch.stop())


def test_missing_managed_checkout_evidence_is_rejected(tmp_path: Path) -> None:
    remote, _managed, service = _repository_topology(tmp_path)
    project = _project(tmp_path / "missing", "proj-oompah", str(remote))
    orch = _orchestrator(tmp_path, _project_store(tmp_path, [project]), service)

    with pytest.raises(ProjectError, match="valid checkout"):
        orch._management_tracker_scope()
    asyncio.run(orch.stop())


def test_ambiguous_repository_matches_fail_closed_with_actionable_alert(
    tmp_path: Path,
) -> None:
    remote, managed, service = _repository_topology(tmp_path)
    second = tmp_path / "managed-second"
    _git(tmp_path, "clone", "--branch", "main", str(remote), str(second))
    projects = [
        _project(managed, "proj-one", str(remote)),
        _project(second, "proj-two", str(remote)),
    ]
    orch = _orchestrator(tmp_path, _project_store(tmp_path, projects), service)

    with pytest.raises(ProjectError, match="proj-one, proj-two") as exc_info:
        orch._management_tracker_scope()
    assert "canonical repo_url" in str(exc_info.value)

    import oompah.server as server

    server._error_watcher = None
    saved_orchestrator = server._orchestrator
    try:
        with (
            patch.object(server, "remove_draft_labels_from_epics", return_value=0),
            patch.object(server, "_migrate_release_picks_on_startup"),
            patch.object(server, "ProjectLogWatcherManager", MagicMock()),
        ):
            server.set_orchestrator(orch)
        assert server._error_watcher is None
        alerts = [
            alert
            for alert in orch._alerts
            if alert.get("source") == "management_tracker_resolution"
        ]
        assert len(alerts) == 1
        assert alerts[0]["action_required"] is True
        assert "proj-one, proj-two" in alerts[0]["detail"]
        snapshot_alerts = [
            alert
            for alert in orch.get_snapshot()["alerts"]
            if alert.get("source") == "management_tracker_resolution"
        ]
        assert len(snapshot_alerts) == 1
        assert snapshot_alerts[0]["severity"] == "error"
        assert snapshot_alerts[0]["active"] is True
        assert "proj-one, proj-two" in snapshot_alerts[0]["sanitized_detail"]
    finally:
        server._orchestrator = saved_orchestrator
        server._error_watcher = None
        server._log_watcher_manager = None
        asyncio.run(orch.stop())


def test_restart_retains_identity_mapping_from_persisted_project_store(
    tmp_path: Path,
) -> None:
    remote, managed, service = _repository_topology(tmp_path)
    project = _project(managed, "proj-oompah", str(remote))
    store = _project_store(tmp_path, [project])
    first = _orchestrator(tmp_path, store, service)
    _tracker, first_project_id = first._management_tracker_scope()
    asyncio.run(first.stop())

    restarted_store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    restarted = _orchestrator(tmp_path, restarted_store, service)
    _tracker, restarted_project_id = restarted._management_tracker_scope()

    assert first_project_id == project.id
    assert restarted_project_id == project.id
    asyncio.run(restarted.stop())
