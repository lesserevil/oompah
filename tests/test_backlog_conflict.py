"""Tests for oompah.backlog_conflict — auto-repair and quarantine of
Backlog.md task files that contain git conflict markers.

Coverage:
- has_conflict_markers() detection
- _merge_frontmatter() structured merge rules
  * status: more-advanced lifecycle wins
  * updated_date: newer wins
  * dependencies/labels: union
  * parent_task_id/final_summary: prefer non-empty
  * oompah.task_costs: merge dicts
- repair_backlog_task_file() in-place repair
- inspect_repo_backlog_conflicts() path enumeration
- repair_repo_backlog_conflicts() batch repair / failure tracking
- projects.sync_project_sources() quarantine/clear via conflict detection
- orchestrator startup_cleanup() surfaces dashboard alerts
- _refresh_backlog_conflict_alerts() arms/clears alerts per project
- dispatch is blocked for quarantined (paused+conflict) projects
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from oompah.backlog_conflict import (
    _merge_frontmatter,
    _merge_oompah_costs,
    _merge_string_list,
    _status_priority,
    has_conflict_markers,
    inspect_repo_backlog_conflicts,
    inspect_repo_unmerged_backlog,
    recover_repo_unmerged_backlog,
    repair_backlog_task_file,
    repair_repo_backlog_conflicts,
)
from oompah.models import Issue, Project
from oompah.projects import ProjectStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_backlog_config(repo: Path) -> None:
    backlog_dir = repo / "backlog"
    (backlog_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "completed").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "config.yml").write_text(
        "project_name: Test\n"
        "default_status: Backlog\n"
        "task_prefix: TASK\n"
        "statuses: [Backlog, Open, In Progress, Done]\n",
        encoding="utf-8",
    )


def _store(tmp_path: Path) -> ProjectStore:
    return ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "wt"),
    )


def _store_with_project(tmp_path: Path, *, with_git: bool = True) -> tuple[ProjectStore, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    if with_git:
        (repo / ".git").mkdir()
    _write_backlog_config(repo)
    store = _store(tmp_path)
    project = Project(
        id="proj-1",
        name="myproject",
        repo_url="https://example.com/repo.git",
        repo_path=str(repo),
        branch="main",
        default_branch="main",
    )
    store._projects[project.id] = project
    return store, repo


def _conflicted_task(
    *,
    ours_status: str = "Done",
    theirs_status: str = "In Progress",
    ours_date: str = "2026-06-02 10:00",
    theirs_date: str = "2026-06-02 09:00",
    extra_ours: str = "",
    extra_theirs: str = "",
    body: str = "Task description\n",
) -> str:
    """Return a Backlog.md task file content with frontmatter conflict markers."""
    ours = (
        f"id: TASK-404\n"
        f"title: Some Task\n"
        f"status: {ours_status}\n"
        f"updated_date: '{ours_date}'\n"
        f"{extra_ours}"
    )
    theirs = (
        f"id: TASK-404\n"
        f"title: Some Task\n"
        f"status: {theirs_status}\n"
        f"updated_date: '{theirs_date}'\n"
        f"{extra_theirs}"
    )
    return (
        f"---\n"
        f"<<<<<<< HEAD\n"
        f"{ours}"
        f"=======\n"
        f"{theirs}"
        f">>>>>>> Stashed changes\n"
        f"---\n"
        f"{body}"
    )


def _clean_task(
    *,
    status: str = "Done",
    date: str = "2026-06-02 10:00",
) -> str:
    return (
        f"---\n"
        f"id: TASK-1\n"
        f"title: Clean Task\n"
        f"status: {status}\n"
        f"updated_date: '{date}'\n"
        f"---\n"
        f"Task body\n"
    )


# ---------------------------------------------------------------------------
# has_conflict_markers
# ---------------------------------------------------------------------------


class TestHasConflictMarkers:
    def test_detects_conflict_markers(self):
        content = "---\n<<<<<<< HEAD\nfoo\n=======\nbar\n>>>>>>> main\n---\n"
        assert has_conflict_markers(content) is True

    def test_no_conflict_markers(self):
        assert has_conflict_markers("---\nfoo: bar\n---\nbody\n") is False

    def test_partial_markers_detected(self):
        # Only opening marker — still detected
        assert has_conflict_markers("<<<<<<< HEAD\nfoo\n") is True

    def test_empty_string(self):
        assert has_conflict_markers("") is False


# ---------------------------------------------------------------------------
# _status_priority
# ---------------------------------------------------------------------------


class TestStatusPriority:
    def test_done_is_most_advanced(self):
        assert _status_priority("Done") < _status_priority("In Progress")
        assert _status_priority("done") < _status_priority("open")

    def test_merged_before_done(self):
        assert _status_priority("merged") < _status_priority("done")

    def test_archived_is_most_advanced(self):
        assert _status_priority("archived") == 0

    def test_unknown_status_is_middle(self):
        # Should not raise
        p = _status_priority("some-custom-status")
        assert p > 0

    def test_none_is_least_advanced(self):
        assert _status_priority(None) > _status_priority("done")


# ---------------------------------------------------------------------------
# _merge_string_list
# ---------------------------------------------------------------------------


class TestMergeStringList:
    def test_union_lists(self):
        result = _merge_string_list(["a", "b"], ["b", "c"])
        assert set(result) == {"a", "b", "c"}

    def test_comma_string(self):
        result = _merge_string_list("bug, feature", ["feature", "chore"])
        assert "bug" in result
        assert "feature" in result
        assert "chore" in result

    def test_none_values(self):
        assert _merge_string_list(None, ["a"]) == ["a"]
        assert _merge_string_list(["a"], None) == ["a"]

    def test_dedup(self):
        result = _merge_string_list(["x", "x"], ["x", "y"])
        assert result.count("x") == 1


# ---------------------------------------------------------------------------
# _merge_oompah_costs
# ---------------------------------------------------------------------------


class TestMergeOompahCosts:
    def test_prefers_nonempty(self):
        assert _merge_oompah_costs(None, {"input": 100}) == {"input": 100}
        assert _merge_oompah_costs({"input": 100}, None) == {"input": 100}

    def test_merges_dicts_taking_max(self):
        a = {"input": 1000, "output": 200}
        b = {"input": 500, "output": 400, "total": 900}
        result = _merge_oompah_costs(a, b)
        assert result["input"] == 1000  # max(1000, 500)
        assert result["output"] == 400  # max(200, 400)
        assert result["total"] == 900   # from b only


# ---------------------------------------------------------------------------
# _merge_frontmatter
# ---------------------------------------------------------------------------


class TestMergeFrontmatter:
    def test_takes_more_advanced_status(self):
        meta_a = {"id": "TASK-1", "status": "Done", "updated_date": "2026-06-02 10:00"}
        meta_b = {"id": "TASK-1", "status": "Open", "updated_date": "2026-06-02 09:00"}
        result = _merge_frontmatter(meta_a, meta_b)
        assert result["status"] == "Done"

    def test_takes_newer_updated_date(self):
        meta_a = {"status": "Done", "updated_date": "2026-06-02 10:00"}
        meta_b = {"status": "Done", "updated_date": "2026-06-03 08:00"}
        result = _merge_frontmatter(meta_a, meta_b)
        assert result["updated_date"] == "2026-06-03 08:00"

    def test_merges_dependencies(self):
        meta_a = {"status": "Open", "dependencies": ["TASK-1", "TASK-2"]}
        meta_b = {"status": "Open", "dependencies": ["TASK-2", "TASK-3"]}
        result = _merge_frontmatter(meta_a, meta_b)
        assert set(result["dependencies"]) == {"TASK-1", "TASK-2", "TASK-3"}

    def test_merges_labels(self):
        meta_a = {"status": "Open", "labels": ["bug"]}
        meta_b = {"status": "Open", "labels": ["feature"]}
        result = _merge_frontmatter(meta_a, meta_b)
        assert set(result["labels"]) == {"bug", "feature"}

    def test_prefers_nonempty_final_summary(self):
        meta_a = {"status": "Done", "final_summary": ""}
        meta_b = {"status": "Done", "final_summary": "Fixed the bug"}
        result = _merge_frontmatter(meta_a, meta_b)
        assert result["final_summary"] == "Fixed the bug"

    def test_prefers_nonempty_parent(self):
        meta_a = {"status": "Open", "parent": ""}
        meta_b = {"status": "Open", "parent": "TASK-10"}
        result = _merge_frontmatter(meta_a, meta_b)
        assert result["parent"] == "TASK-10"

    def test_merges_oompah_task_costs(self):
        meta_a = {"status": "Done", "oompah.task_costs": {"input": 1000}}
        meta_b = {"status": "Done", "oompah.task_costs": {"input": 500, "output": 200}}
        result = _merge_frontmatter(meta_a, meta_b)
        costs = result["oompah.task_costs"]
        assert costs["input"] == 1000   # max(1000, 500)
        assert costs["output"] == 200   # from b only

    def test_both_done_equal_priority(self):
        meta_a = {"status": "Done", "updated_date": "2026-06-02 10:00"}
        meta_b = {"status": "Done", "updated_date": "2026-06-02 09:00"}
        result = _merge_frontmatter(meta_a, meta_b)
        assert result["status"] == "Done"


# ---------------------------------------------------------------------------
# repair_backlog_task_file
# ---------------------------------------------------------------------------


class TestRepairBacklogTaskFile:
    def test_repairs_simple_frontmatter_conflict(self, tmp_path):
        task_file = tmp_path / "task-404.md"
        task_file.write_text(_conflicted_task(), encoding="utf-8")
        result = repair_backlog_task_file(task_file)
        assert result is True
        content = task_file.read_text(encoding="utf-8")
        assert "<<<<<<" not in content
        assert "=======" not in content
        assert ">>>>>>>" not in content
        # Validate it starts with --- and has valid YAML
        assert content.startswith("---\n")

    def test_repaired_file_has_valid_yaml_frontmatter(self, tmp_path):
        task_file = tmp_path / "task-404.md"
        task_file.write_text(_conflicted_task(), encoding="utf-8")
        repair_backlog_task_file(task_file)
        content = task_file.read_text(encoding="utf-8")
        fm_end = content.find("\n---", 4)
        assert fm_end > 4
        meta = yaml.safe_load(content[4:fm_end])
        assert isinstance(meta, dict)
        assert meta.get("id") == "TASK-404"

    def test_repaired_file_preserves_advanced_status(self, tmp_path):
        task_file = tmp_path / "task-404.md"
        # ours=Done (more advanced), theirs=Open
        task_file.write_text(
            _conflicted_task(ours_status="Done", theirs_status="Open"),
            encoding="utf-8",
        )
        repair_backlog_task_file(task_file)
        content = task_file.read_text(encoding="utf-8")
        fm_end = content.find("\n---", 4)
        meta = yaml.safe_load(content[4:fm_end])
        assert meta["status"] == "Done"

    def test_skips_non_conflicted_file(self, tmp_path):
        task_file = tmp_path / "task-clean.md"
        task_file.write_text(_clean_task(), encoding="utf-8")
        result = repair_backlog_task_file(task_file)
        assert result is False  # Not conflicted — skipped

    def test_returns_false_for_missing_file(self, tmp_path):
        result = repair_backlog_task_file(tmp_path / "does-not-exist.md")
        assert result is False

    def test_does_not_repair_non_frontmatter_conflict(self, tmp_path):
        """Conflicts that span the --- delimiters are unsafe to repair."""
        content = "no frontmatter delimiter\n<<<<<<< HEAD\nfoo\n=======\nbar\n>>>>>>>\n"
        task_file = tmp_path / "task-bad.md"
        task_file.write_text(content, encoding="utf-8")
        result = repair_backlog_task_file(task_file)
        assert result is False

    def test_repaired_content_includes_body(self, tmp_path):
        task_file = tmp_path / "task-body.md"
        task_file.write_text(
            _conflicted_task(body="Some body text\n"),
            encoding="utf-8",
        )
        repair_backlog_task_file(task_file)
        content = task_file.read_text(encoding="utf-8")
        assert "Some body text" in content

    def test_repaired_file_preserves_dependencies(self, tmp_path):
        extra_ours = "dependencies: [TASK-1, TASK-2]\n"
        extra_theirs = "dependencies: [TASK-2, TASK-3]\n"
        task_file = tmp_path / "task-deps.md"
        task_file.write_text(
            _conflicted_task(extra_ours=extra_ours, extra_theirs=extra_theirs),
            encoding="utf-8",
        )
        repair_backlog_task_file(task_file)
        content = task_file.read_text(encoding="utf-8")
        fm_end = content.find("\n---", 4)
        meta = yaml.safe_load(content[4:fm_end])
        deps = meta.get("dependencies", [])
        assert "TASK-1" in deps
        assert "TASK-2" in deps
        assert "TASK-3" in deps

    def test_repaired_file_labels_are_union(self, tmp_path):
        extra_ours = "labels: [bug]\n"
        extra_theirs = "labels: [feature]\n"
        task_file = tmp_path / "task-labels.md"
        task_file.write_text(
            _conflicted_task(extra_ours=extra_ours, extra_theirs=extra_theirs),
            encoding="utf-8",
        )
        repair_backlog_task_file(task_file)
        content = task_file.read_text(encoding="utf-8")
        fm_end = content.find("\n---", 4)
        meta = yaml.safe_load(content[4:fm_end])
        labels = meta.get("labels", [])
        assert "bug" in labels
        assert "feature" in labels


# ---------------------------------------------------------------------------
# inspect_repo_backlog_conflicts
# ---------------------------------------------------------------------------


class TestInspectRepoBacklogConflicts:
    def test_detects_conflicted_task_files(self, tmp_path):
        repo = tmp_path / "repo"
        _write_backlog_config(repo)
        task = repo / "backlog" / "tasks" / "task-1.md"
        task.write_text(_conflicted_task(), encoding="utf-8")
        result = inspect_repo_backlog_conflicts(str(repo))
        assert str(task) in result

    def test_ignores_clean_files(self, tmp_path):
        repo = tmp_path / "repo"
        _write_backlog_config(repo)
        task = repo / "backlog" / "tasks" / "task-1.md"
        task.write_text(_clean_task(), encoding="utf-8")
        result = inspect_repo_backlog_conflicts(str(repo))
        assert result == []

    def test_checks_completed_folder(self, tmp_path):
        repo = tmp_path / "repo"
        _write_backlog_config(repo)
        task = repo / "backlog" / "completed" / "task-1.md"
        task.write_text(_conflicted_task(), encoding="utf-8")
        result = inspect_repo_backlog_conflicts(str(repo))
        assert str(task) in result

    def test_empty_for_nonexistent_repo(self, tmp_path):
        result = inspect_repo_backlog_conflicts(str(tmp_path / "no-such-dir"))
        assert result == []

    def test_multiple_conflicted_files(self, tmp_path):
        repo = tmp_path / "repo"
        _write_backlog_config(repo)
        for i in range(3):
            (repo / "backlog" / "tasks" / f"task-{i}.md").write_text(
                _conflicted_task(), encoding="utf-8"
            )
        result = inspect_repo_backlog_conflicts(str(repo))
        assert len(result) == 3


# ---------------------------------------------------------------------------
# repair_repo_backlog_conflicts
# ---------------------------------------------------------------------------


class TestRepairRepoBacklogConflicts:
    def test_repairs_all_repairable_files(self, tmp_path):
        repo = tmp_path / "repo"
        _write_backlog_config(repo)
        t1 = repo / "backlog" / "tasks" / "task-1.md"
        t2 = repo / "backlog" / "tasks" / "task-2.md"
        t1.write_text(_conflicted_task(), encoding="utf-8")
        t2.write_text(_conflicted_task(), encoding="utf-8")
        result = repair_repo_backlog_conflicts(str(repo))
        assert str(t1) in result["repaired"]
        assert str(t2) in result["repaired"]
        assert result["failed"] == []

    def test_records_unrepairable_files(self, tmp_path):
        repo = tmp_path / "repo"
        _write_backlog_config(repo)
        bad = repo / "backlog" / "tasks" / "task-bad.md"
        # File without frontmatter delimiter — cannot be repaired
        bad.write_text("no delimiter\n<<<<<<< HEAD\n", encoding="utf-8")
        result = repair_repo_backlog_conflicts(str(repo))
        assert str(bad) in result["failed"]
        assert result["repaired"] == []

    def test_empty_repo_returns_empty_results(self, tmp_path):
        repo = tmp_path / "repo"
        _write_backlog_config(repo)
        result = repair_repo_backlog_conflicts(str(repo))
        assert result == {"repaired": [], "failed": []}


# ---------------------------------------------------------------------------
# ProjectStore.sync_project_sources() — conflict integration
# ---------------------------------------------------------------------------


class TestSyncProjectSourcesConflicts:
    def test_quarantines_project_when_repair_fails(self, tmp_path):
        store, repo = _store_with_project(tmp_path)
        # Write an unrepairable conflict file
        bad = repo / "backlog" / "tasks" / "task-bad.md"
        bad.write_text(
            "no frontmatter\n<<<<<<< HEAD\nfoo\n=======\nbar\n>>>>>>>\n",
            encoding="utf-8",
        )

        def fake_run(args, **kwargs):
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            status = store.sync_project_sources("proj-1")

        assert status["conflicts"].startswith("quarantined:")
        project = store.get("proj-1")
        assert project.paused is True
        assert len(project.backlog_conflict_paths) == 1

    def test_repairs_and_clears_quarantine(self, tmp_path):
        store, repo = _store_with_project(tmp_path)
        # Write a repairable conflict
        task = repo / "backlog" / "tasks" / "task-1.md"
        task.write_text(_conflicted_task(), encoding="utf-8")
        # Simulate a previously quarantined project
        store._projects["proj-1"].paused = True
        store._projects["proj-1"].backlog_conflict_paths = [str(task)]

        # No-op the git self-heal so the conflicted file survives to the
        # marker-repair + quarantine-clear path under test.
        with patch(
            "oompah.backlog_conflict.ensure_repo_sound",
            return_value={"sound": True, "actions": [], "unrecoverable": [], "reset": False},
        ):
            status = store.sync_project_sources("proj-1")

        assert status["conflicts"].startswith("repaired:")
        project = store.get("proj-1")
        assert project.paused is False
        assert project.backlog_conflict_paths == []

    def test_clears_stale_quarantine_when_no_conflicts(self, tmp_path):
        store, repo = _store_with_project(tmp_path)
        # Project was previously quarantined but no conflicts remain
        store._projects["proj-1"].paused = True
        store._projects["proj-1"].backlog_conflict_paths = ["/some/old/path.md"]

        def fake_run(args, **kwargs):
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            status = store.sync_project_sources("proj-1")

        assert status["conflicts"] == "none"
        project = store.get("proj-1")
        assert project.paused is False
        assert project.backlog_conflict_paths == []

    def test_no_conflicts_status_is_none(self, tmp_path):
        store, repo = _store_with_project(tmp_path)

        def fake_run(args, **kwargs):
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            status = store.sync_project_sources("proj-1")

        assert status["conflicts"] == "none"

    def test_unknown_project_returns_skipped(self, tmp_path):
        store, _ = _store_with_project(tmp_path)
        status = store.sync_project_sources("no-such-project")
        assert status["conflicts"].startswith("skipped:")

    def test_git_failure_does_not_block_conflict_check(self, tmp_path):
        """Conflict inspection runs even when git pull fails."""
        store, repo = _store_with_project(tmp_path)
        bad = repo / "backlog" / "tasks" / "task-bad.md"
        bad.write_text(
            "no frontmatter\n<<<<<<< HEAD\nfoo\n=======\nbar\n>>>>>>>\n",
            encoding="utf-8",
        )

        def fake_run(args, **kwargs):
            if args[:2] == ["git", "pull"]:
                return MagicMock(returncode=1, stdout="", stderr="non-fast-forward")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            status = store.sync_project_sources("proj-1")

        assert status["git"].startswith("failed:")
        # Conflict inspection still ran
        assert status["conflicts"].startswith("quarantined:")


# ---------------------------------------------------------------------------
# Project model — backlog_conflict_paths round-trip
# ---------------------------------------------------------------------------


class TestProjectConflictPathsModel:
    def test_default_is_empty_list(self):
        p = Project(
            id="p",
            name="n",
            repo_url="url",
            repo_path="/path",
        )
        assert p.backlog_conflict_paths == []

    def test_to_dict_omits_empty_list(self):
        p = Project(id="p", name="n", repo_url="url", repo_path="/path")
        d = p.to_dict()
        assert "backlog_conflict_paths" not in d

    def test_to_dict_includes_nonempty_list(self):
        p = Project(id="p", name="n", repo_url="url", repo_path="/path")
        p.backlog_conflict_paths = ["/path/task.md"]
        d = p.to_dict()
        assert d["backlog_conflict_paths"] == ["/path/task.md"]

    def test_from_dict_round_trips(self):
        d = {
            "id": "p", "name": "n", "repo_url": "url", "repo_path": "/path",
            "backlog_conflict_paths": ["/task-1.md", "/task-2.md"],
        }
        p = Project.from_dict(d)
        assert p.backlog_conflict_paths == ["/task-1.md", "/task-2.md"]

    def test_from_dict_missing_field_defaults_to_empty(self):
        d = {"id": "p", "name": "n", "repo_url": "url", "repo_path": "/path"}
        p = Project.from_dict(d)
        assert p.backlog_conflict_paths == []


# ---------------------------------------------------------------------------
# Orchestrator dashboard alerts for quarantined projects
# ---------------------------------------------------------------------------


def _make_orchestrator(tmp_path: Path):
    """Build a minimal orchestrator for alert tests."""
    from oompah.config import ServiceConfig
    from oompah.orchestrator import Orchestrator

    store = _store(tmp_path)
    return Orchestrator(ServiceConfig(), None, project_store=store)


class TestRefreshBacklogConflictAlerts:
    def test_arms_alert_for_quarantined_project(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        project = Project(
            id="p1",
            name="myproject",
            repo_url="url",
            repo_path="/repo",
            paused=True,
            backlog_conflict_paths=["/repo/backlog/tasks/task-1.md"],
        )
        orch.project_store._projects["p1"] = project

        orch._refresh_backlog_conflict_alerts()

        alerts = [a for a in orch._alerts if a.get("source") == "backlog_conflict:p1"]
        assert len(alerts) == 1
        assert alerts[0]["level"] == "error"
        assert "myproject" in alerts[0]["title"]
        assert "task-1.md" in alerts[0]["detail"]

    def test_clears_alert_when_no_more_conflicts(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        project = Project(
            id="p1",
            name="myproject",
            repo_url="url",
            repo_path="/repo",
            paused=False,
            backlog_conflict_paths=[],
        )
        orch.project_store._projects["p1"] = project
        # Pre-arm a stale alert
        orch._alerts.append({
            "source": "backlog_conflict:p1",
            "level": "error",
            "title": "Old alert",
        })

        orch._refresh_backlog_conflict_alerts()

        alerts = [a for a in orch._alerts if a.get("source") == "backlog_conflict:p1"]
        assert alerts == []

    def test_replaces_existing_alert_on_re_arm(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        project = Project(
            id="p1",
            name="myproject",
            repo_url="url",
            repo_path="/repo",
            paused=True,
            backlog_conflict_paths=["/repo/backlog/tasks/task-1.md"],
        )
        orch.project_store._projects["p1"] = project
        # Pre-arm an existing alert
        orch._alerts.append({
            "source": "backlog_conflict:p1",
            "level": "error",
            "title": "Old alert",
            "detail": "Old detail",
        })

        orch._refresh_backlog_conflict_alerts()

        alerts = [a for a in orch._alerts if a.get("source") == "backlog_conflict:p1"]
        assert len(alerts) == 1
        assert "Old detail" not in alerts[0]["detail"]

    def test_includes_project_id_and_conflict_paths_in_alert(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        paths = ["/repo/backlog/tasks/task-1.md", "/repo/backlog/tasks/task-2.md"]
        project = Project(
            id="p1",
            name="myproject",
            repo_url="url",
            repo_path="/repo",
            paused=True,
            backlog_conflict_paths=paths,
        )
        orch.project_store._projects["p1"] = project

        orch._refresh_backlog_conflict_alerts()

        alert = next(
            a for a in orch._alerts if a.get("source") == "backlog_conflict:p1"
        )
        assert alert["project_id"] == "p1"
        assert alert["conflict_paths"] == paths

    def test_no_alerts_when_no_projects(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._refresh_backlog_conflict_alerts()
        conflict_alerts = [
            a for a in orch._alerts if str(a.get("source", "")).startswith("backlog_conflict:")
        ]
        assert conflict_alerts == []

    def test_multiple_projects_independent_alerts(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        p1 = Project(
            id="p1", name="proj1", repo_url="url", repo_path="/r1",
            paused=True, backlog_conflict_paths=["/r1/task.md"],
        )
        p2 = Project(
            id="p2", name="proj2", repo_url="url", repo_path="/r2",
            paused=False, backlog_conflict_paths=[],
        )
        orch.project_store._projects["p1"] = p1
        orch.project_store._projects["p2"] = p2

        orch._refresh_backlog_conflict_alerts()

        p1_alerts = [a for a in orch._alerts if a.get("source") == "backlog_conflict:p1"]
        p2_alerts = [a for a in orch._alerts if a.get("source") == "backlog_conflict:p2"]
        assert len(p1_alerts) == 1
        assert p2_alerts == []


# ---------------------------------------------------------------------------
# Dispatch blocking for quarantined projects
# ---------------------------------------------------------------------------


class TestDispatchBlockingForQuarantinedProject:
    """Ensure tasks from quarantined projects are never dispatched."""

    def test_quarantined_project_does_not_dispatch(self, tmp_path):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        store = _store(tmp_path)
        project = Project(
            id="p1",
            name="quarantined-proj",
            repo_url="url",
            repo_path="/repo",
            paused=True,
            backlog_conflict_paths=["/repo/backlog/tasks/task-1.md"],
        )
        store._projects["p1"] = project

        orch = Orchestrator(ServiceConfig(), None, project_store=store)

        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Some task",
            description="Non-empty description",
            state="Open",
            priority=2,
            project_id="p1",
        )

        result = orch._should_dispatch(issue)
        assert result is False
        # Verify the reject reason is project_paused
        reject_streak = orch.state.reject_streak.get(issue.id)
        assert reject_streak is not None
        reason = reject_streak[0]
        assert reason == "project_paused"

    def test_non_quarantined_project_dispatches(self, tmp_path):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        store = _store(tmp_path)
        project = Project(
            id="p1",
            name="active-proj",
            repo_url="url",
            repo_path="/repo",
            paused=False,
            backlog_conflict_paths=[],
        )
        store._projects["p1"] = project

        orch = Orchestrator(ServiceConfig(), None, project_store=store)

        issue = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Some task",
            description="Non-empty description",
            state="Open",
            priority=2,
            project_id="p1",
        )

        orch._should_dispatch(issue)
        # Should not be blocked by project_paused — may be blocked by other
        # reasons (no agents configured, etc.) but NOT project_paused.
        # We just verify the paused gate doesn't trigger.
        reject_streak = orch.state.reject_streak.get(issue.id)
        if reject_streak:
            assert reject_streak[0] != "project_paused"


# ---------------------------------------------------------------------------
# Regression: parse failure detection (TASK-431 acceptance criterion #1)
# ---------------------------------------------------------------------------


class TestBacklogParseFailureDetection:
    """Verify inspect_repo_backlog_conflicts catches parse-failure files."""

    def test_detects_parse_failing_file_with_conflict_markers(self, tmp_path):
        repo = tmp_path / "repo"
        _write_backlog_config(repo)
        bad = repo / "backlog" / "tasks" / "task-broken.md"
        # Frontmatter has conflict markers that make YAML invalid
        bad.write_text(
            "---\n"
            "<<<<<<< HEAD\n"
            "id: TASK-5\nstatus: Done\n"
            "=======\n"
            "id: TASK-5\nstatus: In Progress\n"
            ">>>>>>> Stashed changes\n"
            "---\n"
            "Body\n",
            encoding="utf-8",
        )
        result = inspect_repo_backlog_conflicts(str(repo))
        assert str(bad) in result


# ---------------------------------------------------------------------------
# Unmerged-index recovery (markerless conflicts) — the aethel failure mode
# ---------------------------------------------------------------------------

import subprocess


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True
    )


def _init_repo_with_unmerged_task(tmp_path: Path) -> tuple[Path, Path]:
    """Build a real git repo where a backlog task file is an UNMERGED INDEX
    entry with NO conflict markers in the working tree (the state that wedged
    aethel). Returns (repo, task_file)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t.test")
    _git(repo, "config", "user.name", "t")
    _git(repo, "checkout", "-q", "-b", "main")
    tasks = repo / "backlog" / "tasks"
    tasks.mkdir(parents=True)
    tf = tasks / "task-9 - Some-task.md"
    tf.write_text(
        "---\nid: TASK-9\ntitle: Some task\nstatus: Backlog\n"
        "updated_date: '2026-06-01 10:00'\n---\nBody\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    # divergent branch: theirs sets status In Progress + a newer date
    _git(repo, "checkout", "-q", "-b", "other")
    tf.write_text(
        "---\nid: TASK-9\ntitle: Some task\nstatus: In Progress\n"
        "updated_date: '2026-06-03 10:00'\n---\nBody\n",
        encoding="utf-8",
    )
    _git(repo, "commit", "-qam", "theirs")
    # ours: status Done + a comment
    _git(repo, "checkout", "-q", "main")
    tf.write_text(
        "---\nid: TASK-9\ntitle: Some task\nstatus: Done\n"
        "updated_date: '2026-06-02 10:00'\n---\nBody\n\n"
        "<!-- COMMENT:BEGIN -->\nindex: 1\nnote: hi\n<!-- COMMENT:END -->\n",
        encoding="utf-8",
    )
    _git(repo, "commit", "-qam", "ours")
    # merge -> conflict (markers, UU), then clear markers in working tree
    # WITHOUT marking resolved -> markerless unmerged index entry.
    _git(repo, "merge", "other")  # expected to conflict
    _git(repo, "checkout", "--theirs", "--", str(tf.relative_to(repo)))
    return repo, tf


class TestUnmergedBacklogRecovery:
    def test_inspect_detects_markerless_unmerged_entry(self, tmp_path):
        repo, tf = _init_repo_with_unmerged_task(tmp_path)
        # Precondition: index is unmerged but the file has NO markers.
        assert _git(repo, "ls-files", "-u").stdout.strip() != ""
        assert not has_conflict_markers(tf.read_text(encoding="utf-8"))
        # The marker-based scanner is blind to it; the index scanner sees it.
        assert inspect_repo_backlog_conflicts(str(repo)) == []
        found = inspect_repo_unmerged_backlog(str(repo))
        assert len(found) == 1
        assert found[0].endswith("task-9 - Some-task.md")

    def test_recover_resolves_and_clears_unmerged_state(self, tmp_path):
        repo, tf = _init_repo_with_unmerged_task(tmp_path)
        result = recover_repo_unmerged_backlog(str(repo))
        assert len(result["recovered"]) == 1
        assert result["failed"] == []
        # Unmerged index entry is gone -> a pull would no longer be blocked.
        assert _git(repo, "ls-files", "-u").stdout.strip() == ""
        # Structured merge preserved data from BOTH sides: most-advanced status
        # (Done from ours) and the comment, with a valid parse.
        merged = tf.read_text(encoding="utf-8")
        assert not has_conflict_markers(merged)
        meta = yaml.safe_load(merged.split("---", 2)[1])
        assert meta["status"] == "Done"  # more-advanced lifecycle wins
        assert "COMMENT:BEGIN" in merged

    def test_recover_noop_on_clean_repo(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "t@t.test")
        _git(repo, "config", "user.name", "t")
        (repo / "backlog" / "tasks").mkdir(parents=True)
        (repo / "backlog" / "tasks" / "task-1 - x.md").write_text(
            "---\nid: TASK-1\nstatus: Backlog\n---\nb\n", encoding="utf-8"
        )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "c")
        result = recover_repo_unmerged_backlog(str(repo))
        assert result == {"recovered": [], "failed": []}
        assert inspect_repo_unmerged_backlog(str(repo)) == []


# ---------------------------------------------------------------------------
# ensure_repo_sound — aggressive whole-checkout self-heal
# ---------------------------------------------------------------------------

from oompah.backlog_conflict import ensure_repo_sound, list_unmerged_paths


def _mk_remote_clone(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "t@t.test")
    _git(work, "config", "user.name", "t")
    (work / "backlog" / "tasks").mkdir(parents=True)
    (work / "backlog" / "tasks" / "task-1 - a.md").write_text(
        "---\nid: TASK-1\nstatus: Backlog\n---\nbody\n", encoding="utf-8"
    )
    (work / "README.md").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "base")
    _git(work, "remote", "add", "origin", str(remote))
    _git(work, "push", "-q", "origin", "main")
    return remote, work


def _advance_origin(tmp_path: Path, remote: Path, relpath: str, content: str) -> None:
    c2 = tmp_path / "c2"
    if not c2.exists():
        _git(tmp_path, "clone", "-q", str(remote), str(c2))
        _git(c2, "config", "user.email", "t@t.test")
        _git(c2, "config", "user.name", "t")
    p = c2 / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    _git(c2, "add", "-A")
    _git(c2, "commit", "-qm", "origin-change")
    _git(c2, "push", "-q", "origin", "main")


class TestEnsureRepoSound:
    def test_fast_forwards_when_behind(self, tmp_path):
        remote, work = _mk_remote_clone(tmp_path)
        _advance_origin(tmp_path, remote, "backlog/tasks/task-2 - b.md",
                        "---\nid: TASK-2\nstatus: Backlog\n---\nb\n")
        res = ensure_repo_sound(str(work), "main")
        assert res["sound"] is True
        assert res["reset"] is False
        assert "ff-pull" in res["actions"]
        assert (work / "backlog" / "tasks" / "task-2 - b.md").exists()

    def test_hard_resets_on_backlog_only_divergence(self, tmp_path):
        remote, work = _mk_remote_clone(tmp_path)
        # origin changes task-1; local makes a DIFFERENT committed change to it
        _advance_origin(tmp_path, remote, "backlog/tasks/task-1 - a.md",
                        "---\nid: TASK-1\nstatus: Done\n---\norigin\n")
        (work / "backlog" / "tasks" / "task-1 - a.md").write_text(
            "---\nid: TASK-1\nstatus: In Progress\n---\nlocal\n", encoding="utf-8"
        )
        _git(work, "commit", "-qam", "local backlog change")
        res = ensure_repo_sound(str(work), "main")
        # Non-ff divergence on a backlog-only commit -> safe hard-reset.
        assert res["sound"] is True
        assert res["reset"] is True
        assert "hard-reset" in res["actions"]
        assert list_unmerged_paths(str(work)) == []
        assert _git(work, "rev-list", "--count", "HEAD..origin/main").stdout.strip() == "0"

    def test_quarantines_unpushed_code_commit(self, tmp_path):
        remote, work = _mk_remote_clone(tmp_path)
        # origin advances; local has an unpushed commit touching CODE (README).
        _advance_origin(tmp_path, remote, "backlog/tasks/task-3 - c.md",
                        "---\nid: TASK-3\nstatus: Backlog\n---\nc\n")
        (work / "README.md").write_text("local code change\n", encoding="utf-8")
        _git(work, "commit", "-qam", "local code change")
        res = ensure_repo_sound(str(work), "main")
        # Can't safely hard-reset (would drop unpushed code) -> not sound, flagged.
        assert res["sound"] is False
        assert res["reset"] is False
        assert res["unrecoverable"]
        # local code commit preserved
        assert "local code change" in (work / "README.md").read_text(encoding="utf-8")

    def test_clean_current_repo_is_sound_noop(self, tmp_path):
        remote, work = _mk_remote_clone(tmp_path)
        res = ensure_repo_sound(str(work), "main")
        assert res["sound"] is True
        assert res["reset"] is False
