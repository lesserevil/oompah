"""Tests for the Backlog.md tracker adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import yaml

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.roles import RoleStore
from oompah.tracker import BacklogMdTracker


def _write_config(root, *, directory="backlog"):
    backlog_dir = root / directory
    (backlog_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "completed").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "config.yml").write_text(
        "\n".join([
            'projectName: "Test"',
            'defaultStatus: "Backlog"',
            'statuses: ["Backlog", "Open", "In Progress", "Needs CI Fix", '
            '"Needs Rebase", "Done", "Merged", "Archived"]',
            'taskPrefix: "task"',
            "",
        ]),
        encoding="utf-8",
    )
    return backlog_dir


def _write_task(
    backlog_dir,
    task_id: str,
    title: str,
    *,
    status: str = "Open",
    priority: str = "medium",
    labels: list[str] | None = None,
    dependencies: list[str] | None = None,
    description: str = "Body",
    folder: str = "tasks",
    comments: bool = False,
    extra_meta: dict | None = None,
):
    number = task_id.split("-", 1)[1]
    path = backlog_dir / folder / f"task-{number} - {title.replace(' ', '-')}.md"
    meta = {
        "id": task_id,
        "title": title,
        "status": status,
        "created_date": "2026-05-31 10:00",
        "updated_date": "2026-05-31 10:05",
        "labels": labels or [],
        "dependencies": dependencies or [],
        "priority": priority,
    }
    if extra_meta:
        meta.update(extra_meta)
    comment_block = ""
    if comments:
        comment_block = """\

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-05-31 10:06

Progress note
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
"""
    path.write_text(
        "---\n"
        + yaml.safe_dump(meta, sort_keys=False)
        + "---\n"
        + f"""\
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
{description}
<!-- SECTION:DESCRIPTION:END -->
{comment_block}""",
        encoding="utf-8",
    )
    return path


def _tracker(root):
    return BacklogMdTracker(
        active_states=["Open", "Needs CI Fix", "Needs Rebase"],
        terminal_states=["Done"],
        cwd=str(root),
    )


def test_fetch_candidate_issues_parses_and_filters(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Fix auth",
        priority="high",
        labels=["Bug", "Auth"],
        dependencies=["TASK-9"],
        description="Investigate login failure",
    )
    _write_task(
        backlog_dir,
        "TASK-2",
        "Ship docs",
        status="Done",
        folder="completed",
        priority="low",
    )

    issues = _tracker(tmp_path).fetch_candidate_issues()

    assert [issue.identifier for issue in issues] == ["TASK-1"]
    issue = issues[0]
    assert issue.title == "Fix auth"
    assert issue.description == "Investigate login failure"
    assert issue.state == "Open"
    assert issue.priority == 1
    assert issue.issue_type == "bug"
    assert issue.labels == ["bug", "auth"]
    assert issue.blocked_by[0].identifier == "TASK-9"


def test_fetch_all_issues_includes_completed_folder(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Open task")
    _write_task(backlog_dir, "TASK-2", "Done task", status="Done", folder="completed")

    issues = _tracker(tmp_path).fetch_all_issues()

    assert {issue.identifier for issue in issues} == {"TASK-1", "TASK-2"}


def test_fetch_issue_detail_and_comments(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "With comments", comments=True)

    tracker = _tracker(tmp_path)
    issue = tracker.fetch_issue_detail("1")
    comments = tracker.fetch_comments("TASK-1")

    assert issue is not None
    assert issue.identifier == "TASK-1"
    assert comments == [{
        "id": "1",
        "author": "oompah",
        "created_at": "2026-05-31 10:06",
        "text": "Progress note",
    }]


def test_set_attachments_updates_frontmatter_and_manifest(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Attachment task")
    attachments = [{"path": ".oompah/attachments/TASK-1/mock.png"}]

    tracker = _tracker(tmp_path)
    tracker.set_attachments("TASK-1", attachments, project_root=str(tmp_path))

    issue = tracker.fetch_issue_detail("TASK-1")
    assert issue is not None
    assert issue.attachments == [".oompah/attachments/TASK-1/mock.png"]
    manifest = tmp_path / ".oompah" / "attachments" / "TASK-1" / "manifest.json"
    assert manifest.exists()


def test_close_issue_uses_done_status_and_optional_comment(tmp_path):
    _write_config(tmp_path)
    tracker = _tracker(tmp_path)

    with (
        patch.object(tracker, "_run_backlog", return_value="") as run_backlog,
        patch.object(tracker, "add_comment") as add_comment,
    ):
        tracker.close_issue("TASK-1", reason="Completed")

    assert run_backlog.call_args_list[0].args[0] == [
        "task", "edit", "TASK-1", "--status", "Done", "--plain",
    ]
    add_comment.assert_called_once_with("TASK-1", "Completed")


def test_update_issue_maps_legacy_statuses_to_backlog_statuses(tmp_path):
    _write_config(tmp_path)
    tracker = _tracker(tmp_path)

    with patch.object(tracker, "_run_backlog", return_value="") as run_backlog:
        tracker.update_issue("TASK-1", status="in_progress")
        tracker.update_issue("TASK-2", status="deferred")
        tracker.update_issue("TASK-3", status="open")

    assert run_backlog.call_args_list[0].args[0] == [
        "task", "edit", "TASK-1", "--plain", "--status", "In Progress",
    ]
    assert run_backlog.call_args_list[1].args[0] == [
        "task", "edit", "TASK-2", "--plain", "--status", "Backlog",
    ]
    assert run_backlog.call_args_list[2].args[0] == [
        "task", "edit", "TASK-3", "--plain", "--status", "Open",
    ]


def test_mark_needs_human_updates_status_then_appends_comment(tmp_path):
    _write_config(tmp_path)
    tracker = _tracker(tmp_path)

    with patch.object(tracker, "_run_backlog", return_value="") as run_backlog:
        tracker.mark_needs_human("TASK-1", "Human action required")

    assert run_backlog.call_args_list[0].args[0] == [
        "task", "edit", "TASK-1", "--plain", "--status", "Needs Human",
    ]
    assert run_backlog.call_args_list[1].args[0] == [
        "task", "edit", "TASK-1",
        "--comment", "Human action required",
        "--comment-author", "oompah",
        "--plain",
    ]


def test_set_metadata_field_preserves_existing_comments(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Metadata comments", comments=True)

    tracker = _tracker(tmp_path)
    tracker.set_metadata_field("TASK-1", "oompah.task_costs", {"runs": []})

    comments = tracker.fetch_comments("TASK-1")
    assert comments == [{
        "id": "1",
        "author": "oompah",
        "created_at": "2026-05-31 10:06",
        "text": "Progress note",
    }]
    assert tracker.get_metadata("TASK-1")["oompah.task_costs"] == {"runs": []}


def test_working_set_fingerprint_changes_when_task_changes(tmp_path):
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(backlog_dir, "TASK-1", "Fingerprint")

    tracker = _tracker(tmp_path)
    before = tracker.working_set_fingerprint()
    task_path.write_text(
        task_path.read_text(encoding="utf-8").replace("Fingerprint", "Changed"),
        encoding="utf-8",
    )
    after = tracker.working_set_fingerprint()

    assert before != after


def test_create_issue_builds_backlog_cli_command(tmp_path):
    _write_config(tmp_path)
    tracker = _tracker(tmp_path)

    with (
        patch.object(
            tracker,
            "_run_backlog",
            return_value="Task TASK-7 - New feature\n",
        ) as run_backlog,
        patch.object(tracker, "fetch_issue_detail") as fetch_issue_detail,
    ):
        fetch_issue_detail.return_value = Issue(
            id="TASK-7", identifier="TASK-7", title="New feature",
        )
        tracker.create_issue(
            "New feature",
            issue_type="feature",
            description="Details",
            priority=1,
            labels=["api"],
            parent="TASK-1",
        )

    assert run_backlog.call_args.args[0] == [
        "task", "create", "New feature", "--plain",
        "--description", "Details",
        "--status", "Backlog",
        "--priority", "high",
        "--labels", "api,feature",
        "--parent", "TASK-1",
    ]


def test_orchestrator_constructs_backlog_tracker(tmp_path):
    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.return_value = None
    config = ServiceConfig(
        tracker_kind="backlog_md",
        tracker_active_states=["Open", "Needs CI Fix", "Needs Rebase"],
        tracker_terminal_states=["Done"],
        workspace_root=str(tmp_path / "workspaces"),
    )

    orch = Orchestrator(
        config=config,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=RoleStore(path=str(tmp_path / "roles.json")),
        state_path=str(tmp_path / "state.json"),
    )

    assert isinstance(orch.tracker, BacklogMdTracker)
