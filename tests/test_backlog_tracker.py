"""Tests for the Backlog.md tracker adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import yaml

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.tracker import _read_markdown_frontmatter, _write_markdown_frontmatter
from oompah.orchestrator import Orchestrator
from oompah.roles import RoleStore
from oompah.tracker import BacklogMdTracker


def _write_config(root, *, directory="backlog"):
    backlog_dir = root / directory
    (backlog_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "completed").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "config.yml").write_text(
        "\n".join([
            'project_name: "Test"',
            'default_status: "To Do"',
            'statuses: ["To Do", "In Progress", "Done"]',
            'task_prefix: "task"',
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
    status: str = "To Do",
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
        active_states=["To Do", "In Progress"],
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
    assert issue.state == "To Do"
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
        "task", "edit", "TASK-2", "--plain", "--status", "To Do",
    ]
    assert run_backlog.call_args_list[2].args[0] == [
        "task", "edit", "TASK-3", "--plain", "--status", "To Do",
    ]


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
        "--status", "To Do",
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
        tracker_active_states=["To Do", "In Progress"],
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


# ---------------------------------------------------------------------------
# Frontmatter preservation tests (TASK-397)
# ---------------------------------------------------------------------------

def _make_cli_dropper(task_path, *, new_status: str = "In Progress"):
    """Return a fake _run_backlog that rewrites the task file without custom fields.

    This simulates the behaviour of the real backlog CLI: it re-serializes
    the YAML frontmatter and only emits the standard fields it knows about,
    silently dropping custom keys like ``type``, ``parent``, and ``beads.*``.
    """
    _STANDARD = {
        "id", "title", "status", "assignee", "created_date",
        "updated_date", "labels", "dependencies", "priority", "ordinal",
    }

    def fake_run_backlog(args):
        if "edit" in args:
            meta, body = _read_markdown_frontmatter(task_path)
            stripped = {k: v for k, v in meta.items() if k in _STANDARD}
            stripped["status"] = new_status
            _write_markdown_frontmatter(task_path, stripped, body)
        return ""

    return fake_run_backlog


def test_update_issue_preserves_extra_frontmatter_fields(tmp_path):
    """update_issue must not drop custom frontmatter fields (type, parent, beads.*)."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-1",
        "Test task",
        extra_meta={
            "type": "feature",
            "parent": "TASK-0",
            "beads": {
                "id": "proj-abc123",
                "state": "open",
                "parent_id": None,
            },
        },
    )
    tracker = _tracker(tmp_path)

    with patch.object(
        tracker, "_run_backlog",
        side_effect=_make_cli_dropper(task_path, new_status="In Progress"),
    ):
        tracker.update_issue("TASK-1", status="in_progress")

    meta, _ = _read_markdown_frontmatter(task_path)
    assert meta["status"] == "In Progress", "CLI status update must take effect"
    assert meta["type"] == "feature", "custom 'type' field must be preserved"
    assert meta["parent"] == "TASK-0", "custom 'parent' field must be preserved"
    assert meta["beads"]["id"] == "proj-abc123", "nested 'beads' block must be preserved"


def test_close_issue_preserves_extra_frontmatter_fields(tmp_path):
    """close_issue must not drop custom frontmatter fields (type, parent, beads.*)."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-1",
        "Test task",
        extra_meta={
            "type": "task",
            "beads": {"id": "proj-xyz", "state": "open"},
        },
    )
    tracker = _tracker(tmp_path)

    with (
        patch.object(
            tracker, "_run_backlog",
            side_effect=_make_cli_dropper(task_path, new_status="Done"),
        ),
        patch.object(tracker, "add_comment"),
        patch.object(tracker, "remove_label"),
    ):
        tracker.close_issue("TASK-1")

    meta, _ = _read_markdown_frontmatter(task_path)
    assert meta["status"] == "Done"
    assert meta["type"] == "task"
    assert meta["beads"]["id"] == "proj-xyz"


def test_add_comment_preserves_extra_frontmatter_fields(tmp_path):
    """add_comment must not drop custom frontmatter fields."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-1",
        "Test task",
        extra_meta={"type": "bug", "beads": {"id": "proj-qrs"}},
    )
    tracker = _tracker(tmp_path)

    with patch.object(
        tracker, "_run_backlog",
        side_effect=_make_cli_dropper(task_path, new_status="To Do"),
    ):
        tracker.add_comment("TASK-1", "progress note")

    meta, _ = _read_markdown_frontmatter(task_path)
    assert meta["type"] == "bug"
    assert meta["beads"]["id"] == "proj-qrs"


def test_run_backlog_task_edit_does_not_overwrite_cli_changes(tmp_path):
    """Fields the CLI updates (status) must NOT be overwritten by the restore step."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-1",
        "Test task",
        status="To Do",
        extra_meta={"type": "feature"},
    )
    tracker = _tracker(tmp_path)

    # The fake CLI updates status to "In Progress" and drops "type".
    with patch.object(
        tracker, "_run_backlog",
        side_effect=_make_cli_dropper(task_path, new_status="In Progress"),
    ):
        tracker.update_issue("TASK-1", status="in_progress")

    meta, _ = _read_markdown_frontmatter(task_path)
    # The CLI's status update must win; "type" must be restored.
    assert meta["status"] == "In Progress"
    assert meta["type"] == "feature"


def test_run_backlog_task_edit_no_file_before_edit(tmp_path):
    """_run_backlog_task_edit must not crash if the task file cannot be found before the edit."""
    _write_config(tmp_path)
    tracker = _tracker(tmp_path)

    # No task file exists — _task_path_for returns None.
    with patch.object(tracker, "_run_backlog", return_value="") as run_backlog:
        # Should not raise even though the task doesn't exist on disk.
        tracker._run_backlog_task_edit("TASK-MISSING", ["task", "edit", "TASK-MISSING", "--plain"])

    run_backlog.assert_called_once()
