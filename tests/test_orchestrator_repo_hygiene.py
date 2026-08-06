"""Orchestrator integration tests for live repository hygiene inventory."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.repo_hygiene import HealthThresholds


def _orchestrator(project, issues, *, age_seconds=100):
    tracker = SimpleNamespace(fetch_all_issues=lambda: issues)
    project_store = SimpleNamespace(list_all=lambda: [project])
    orchestrator = object.__new__(Orchestrator)
    orchestrator.project_store = project_store
    orchestrator._tracker_for_project = lambda _project_id: tracker
    orchestrator._repo_hygiene_thresholds = HealthThresholds(
        safely_prunable_age_seconds=age_seconds,
        safely_prunable_count_warning=100,
        safely_prunable_count_critical=200,
    )
    orchestrator._cleanup_error_last = None
    return orchestrator


def _project():
    return SimpleNamespace(
        id="proj-1",
        repo_path="/repo",
        default_branch="main",
        branch="main",
        state_branch_name=None,
        supported_release_branches=[],
        branches=["main"],
    )


def _issue(identifier, state, branch, *, closed_at=None):
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        state=state,
        project_id="proj-1",
        work_branch=branch,
        closed_at=closed_at,
    )


def test_inventory_distinguishes_protected_work_from_prunable_debt():
    old = datetime.now(timezone.utc) - timedelta(seconds=500)
    issues = [
        _issue("OPEN-1", "Open", "feature-open"),
        _issue("DONE-1", "Done", "feature-unmerged", closed_at=old),
        _issue("MERGED-1", "Merged", "feature-merged", closed_at=old),
    ]
    orchestrator = _orchestrator(_project(), issues)
    worktrees = [
        {"path": "/repo", "branch": "main", "dirty": False},
        {"path": "/wt/open", "branch": "feature-open", "dirty": False},
        {"path": "/wt/unmerged", "branch": "feature-unmerged", "dirty": False},
        {"path": "/wt/merged", "branch": "feature-merged", "dirty": False},
    ]
    refs = [
        {"ref": "refs/heads/main", "name": "main", "remote": False, "commit_timestamp": 1},
        {"ref": "refs/heads/feature-open", "name": "feature-open", "remote": False, "commit_timestamp": 1},
        {"ref": "refs/heads/feature-unmerged", "name": "feature-unmerged", "remote": False, "commit_timestamp": 1},
        {"ref": "refs/heads/feature-merged", "name": "feature-merged", "remote": False, "commit_timestamp": 1},
        {"ref": "refs/remotes/origin/feature-merged", "name": "origin/feature-merged", "remote": True, "commit_timestamp": 1},
    ]
    with (
        patch.object(Orchestrator, "_repo_hygiene_git_worktrees", return_value=worktrees),
        patch.object(Orchestrator, "_repo_hygiene_git_refs", return_value=refs),
        patch.object(
            Orchestrator,
            "_repo_hygiene_branch_merged",
            side_effect=lambda _repo, ref, _default: "unmerged" not in ref,
        ),
    ):
        health = orchestrator._evaluate_repo_hygiene_health()

    assert health.worktrees.active == 1
    assert health.worktrees.terminal_protected == 0
    assert health.worktrees.unmerged == 1
    assert health.worktrees.safely_prunable == 1
    assert health.branches_local.shared_owner == 1
    assert health.branches_local.active == 1
    assert health.branches_local.unmerged == 1
    assert health.branches_local.terminal_protected == 1
    assert health.branches_local.safely_prunable == 0
    assert health.branches_remote.safely_prunable == 1
    assert all(item.project_id == "proj-1" for item in health.overdue_artifacts)
    assert any(item.task_id == "MERGED-1" for item in health.overdue_artifacts)


def test_dirty_work_is_preserved_even_when_task_is_terminal():
    issue = _issue("MERGED-1", "Merged", "feature-merged")
    orchestrator = _orchestrator(_project(), [issue])
    with (
        patch.object(
            Orchestrator,
            "_repo_hygiene_git_worktrees",
            return_value=[{"path": "/wt/merged", "branch": "feature-merged", "dirty": True}],
        ),
        patch.object(
            Orchestrator,
            "_repo_hygiene_git_refs",
            return_value=[
                {
                    "ref": "refs/heads/feature-merged",
                    "name": "feature-merged",
                    "remote": False,
                    "commit_timestamp": 1,
                }
            ],
        ),
    ):
        health = orchestrator._evaluate_repo_hygiene_health()

    assert health.worktrees.dirty == 1
    assert health.branches_local.dirty == 1
    assert health.worktrees.safely_prunable == 0
    assert not health.overdue_artifacts


def test_health_payload_is_persisted_and_restored():
    orchestrator = object.__new__(Orchestrator)
    orchestrator._maintenance_status = {}
    orchestrator._alerts = []
    orchestrator._alerts_lock = RLock()
    orchestrator._cleanup_error_last = None
    orchestrator._repo_hygiene_thresholds = HealthThresholds()
    payload = {"is_healthy": True, "summary": "retained work is healthy"}
    orchestrator._evaluate_repo_hygiene_health = lambda: SimpleNamespace(
        to_dict=lambda: payload
    )
    saved = {}
    orchestrator._save_state = lambda **updates: saved.update(updates)

    orchestrator._update_repo_hygiene_health()

    assert orchestrator._maintenance_status["repo_hygiene_health"] == payload
    assert saved["repo_hygiene_health"] == payload


def test_health_alert_clears_after_safe_cleanup():
    orchestrator = object.__new__(Orchestrator)
    orchestrator._maintenance_status = {}
    orchestrator._alerts = []
    orchestrator._alerts_lock = RLock()
    orchestrator._cleanup_error_last = None
    orchestrator._repo_hygiene_thresholds = HealthThresholds()
    unhealthy = {"is_healthy": False, "summary": "1 artifact overdue"}
    healthy = {"is_healthy": True, "summary": "Repository hygiene healthy"}
    objects = iter(
        (
            SimpleNamespace(
                to_dict=lambda: unhealthy,
                is_healthy=False,
                summary="1 artifact overdue",
            ),
            SimpleNamespace(
                to_dict=lambda: healthy,
                is_healthy=True,
                summary="Repository hygiene healthy",
            ),
        )
    )
    orchestrator._evaluate_repo_hygiene_health = lambda: next(objects)
    orchestrator._save_state = lambda **_updates: None

    orchestrator._update_repo_hygiene_health()
    assert len(orchestrator._alerts) == 1
    assert orchestrator._alerts[0]["source"] == "repo_hygiene_health"

    orchestrator._update_repo_hygiene_health()
    assert orchestrator._alerts == []


def test_service_config_exposes_repo_hygiene_thresholds(monkeypatch):
    monkeypatch.setenv("OOMPAH_REPO_HYGIENE_SAFELY_PRUNABLE_AGE_SECONDS", "42")
    monkeypatch.setenv("OOMPAH_REPO_HYGIENE_SAFELY_PRUNABLE_COUNT_WARNING", "7")
    monkeypatch.setenv("OOMPAH_REPO_HYGIENE_SAFELY_PRUNABLE_COUNT_CRITICAL", "9")
    monkeypatch.setenv("OOMPAH_REPO_HYGIENE_CLEANUP_ERROR_THRESHOLD", "2")
    config = ServiceConfig.from_workflow(
        SimpleNamespace(config={}, prompt_template="test")
    )

    assert config.repo_hygiene_safely_prunable_age_seconds == 42
    assert config.repo_hygiene_safely_prunable_count_warning == 7
    assert config.repo_hygiene_safely_prunable_count_critical == 9
    assert config.repo_hygiene_cleanup_error_threshold == 2


def test_git_ref_inventory_parses_local_remote_and_ignores_symbolic_head():
    result = MagicMock(
        returncode=0,
        stdout=(
            "refs/heads/main\tmain\t1700000000\n"
            "refs/remotes/origin/main\torigin/main\t1700000001\n"
            "refs/remotes/origin/HEAD\torigin/HEAD\t1700000001\n"
        ),
        stderr="",
    )
    with patch("oompah.orchestrator.subprocess.run", return_value=result):
        refs = Orchestrator._repo_hygiene_git_refs("/repo")

    assert [(ref["name"], ref["remote"]) for ref in refs] == [
        ("main", False),
        ("origin/main", True),
    ]
    assert refs[1]["commit_timestamp"] == 1700000001


def test_registered_worktree_inventory_marks_dirty_paths():
    listing = MagicMock(
        returncode=0,
        stdout=(
            "worktree /repo\n"
            "HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /wt/task\n"
            "HEAD bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
            "branch refs/heads/task\n"
        ),
        stderr="",
    )
    clean = MagicMock(returncode=0, stdout="", stderr="")
    dirty = MagicMock(returncode=0, stdout=" M tracked.txt\n", stderr="")
    with patch(
        "oompah.orchestrator.subprocess.run",
        side_effect=[listing, clean, dirty],
    ):
        records = Orchestrator._repo_hygiene_git_worktrees("/repo")

    assert records[0]["branch"] == "main"
    assert records[0]["dirty"] is False
    assert records[1]["branch"] == "task"
    assert records[1]["dirty"] is True


def test_snapshot_exposes_health_under_both_maintenance_namespaces(tmp_path):
    from oompah.projects import ProjectStore

    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    orchestrator = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=store,
        state_path=str(tmp_path / "state.json"),
    )
    payload = {
        "is_healthy": True,
        "worktrees": {"active": 1},
        "overdue_artifacts": [],
    }
    orchestrator._maintenance_status["repo_hygiene_health"] = payload

    snapshot = orchestrator.get_snapshot()

    assert snapshot["maintenance"]["repo_hygiene_health"] == payload
    assert snapshot["orchestrator_metrics"]["maintenance"]["repo_hygiene_health"] == payload
