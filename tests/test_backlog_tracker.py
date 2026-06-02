"""Tests for the Backlog.md tracker adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.roles import RoleStore
from oompah.tracker import (
    BacklogMdTracker,
    _read_markdown_frontmatter,
    _write_markdown_frontmatter,
)


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


def test_fetch_candidate_issues_parses_numeric_p0_priority(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "P0 task", priority="0")
    _write_task(backlog_dir, "TASK-2", "P1 task", priority="high")

    issues = _tracker(tmp_path).fetch_candidate_issues()

    assert [issue.identifier for issue in issues] == ["TASK-1", "TASK-2"]
    assert issues[0].priority == 0
    assert issues[1].priority == 1


def test_fetch_candidate_issues_parses_critical_priority_as_p0(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Critical task", priority="critical")

    issue = _tracker(tmp_path).fetch_issue_detail("TASK-1")

    assert issue is not None
    assert issue.priority == 0


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


def test_add_comment_appends_backlog_comment_without_cli(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Comment target")
    tracker = _tracker(tmp_path)

    with patch.object(tracker, "_run_backlog", return_value="") as run_backlog:
        result = tracker.add_comment("TASK-1", "Human answer\nwith detail", author="user")

    run_backlog.assert_not_called()
    assert result == {"author": "user", "text": "Human answer\nwith detail"}
    comments = tracker.fetch_comments("TASK-1")
    assert len(comments) == 1
    assert comments[0]["id"] == "1"
    assert comments[0]["author"] == "user"
    assert comments[0]["created_at"]
    assert comments[0]["text"] == "Human answer\nwith detail"


def test_add_comment_preserves_existing_comments_and_increments_index(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Existing comments", comments=True)
    tracker = _tracker(tmp_path)

    tracker.add_comment("TASK-1", "Second note")

    comments = tracker.fetch_comments("TASK-1")
    assert comments[0] == {
        "id": "1",
        "author": "oompah",
        "created_at": "2026-05-31 10:06",
        "text": "Progress note",
    }
    assert comments[1]["id"] == "2"
    assert comments[1]["author"] == "oompah"
    assert comments[1]["created_at"]
    assert comments[1]["text"] == "Second note"


def test_add_comment_updates_task_updated_date(tmp_path):
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(backlog_dir, "TASK-1", "Updated date")
    tracker = _tracker(tmp_path)

    tracker.add_comment("TASK-1", "Update timestamp")

    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["updated_date"] != "2026-05-31 10:05"
    assert meta["updated_date"] == tracker.fetch_comments("TASK-1")[0]["created_at"]


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


def test_update_issue_preserves_custom_frontmatter_dropped_by_cli(tmp_path):
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-1",
        "Custom metadata",
        extra_meta={
            "type": "bug",
            "parent": "TASK-9",
            "beads": {"id": "oompah-legacy"},
            "oompah.custom": {"kept": True},
        },
    )
    tracker = _tracker(tmp_path)

    def fake_cli_rewrite(_args):
        meta, body = yaml.safe_load(
            task_path.read_text(encoding="utf-8").split("---\n", 2)[1],
        ), task_path.read_text(encoding="utf-8").split("---\n", 2)[2]
        rewritten = {
            key: meta[key]
            for key in (
                "id",
                "title",
                "status",
                "created_date",
                "updated_date",
                "labels",
                "dependencies",
                "priority",
            )
            if key in meta
        }
        rewritten["status"] = "In Progress"
        task_path.write_text(
            "---\n"
            + yaml.safe_dump(rewritten, sort_keys=False)
            + "---\n"
            + body,
            encoding="utf-8",
        )
        return ""

    with patch.object(tracker, "_run_backlog", side_effect=fake_cli_rewrite):
        tracker.update_issue("TASK-1", status="In Progress")

    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["status"] == "In Progress"
    assert meta["type"] == "bug"
    assert meta["parent"] == "TASK-9"
    assert meta["beads"] == {"id": "oompah-legacy"}
    assert meta["oompah.custom"] == {"kept": True}


def test_update_issue_priority_zero_writes_numeric_frontmatter_without_cli(tmp_path):
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(backlog_dir, "TASK-1", "P0 target", priority="high")
    tracker = _tracker(tmp_path)

    with patch.object(tracker, "_run_backlog", return_value="") as run_backlog:
        tracker.update_issue("TASK-1", priority=0)

    run_backlog.assert_not_called()
    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["priority"] == 0
    assert tracker.fetch_issue_detail("TASK-1").priority == 0


def test_update_issue_priority_zero_survives_other_cli_updates(tmp_path):
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(backlog_dir, "TASK-1", "P0 with status", priority="high")
    tracker = _tracker(tmp_path)

    def fake_cli_rewrite(_args):
        meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
        body = task_path.read_text(encoding="utf-8").split("---\n", 2)[2]
        meta["status"] = "In Progress"
        meta["priority"] = "high"
        task_path.write_text(
            "---\n"
            + yaml.safe_dump(meta, sort_keys=False)
            + "---\n"
            + body,
            encoding="utf-8",
        )
        return ""

    with patch.object(tracker, "_run_backlog", side_effect=fake_cli_rewrite) as run_backlog:
        tracker.update_issue("TASK-1", status="In Progress", priority="P0")

    assert run_backlog.call_args.args[0] == [
        "task", "edit", "TASK-1", "--plain", "--status", "In Progress",
    ]
    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["priority"] == 0
    assert tracker.fetch_issue_detail("TASK-1").priority == 0


def test_update_issue_critical_priority_writes_numeric_p0_frontmatter(tmp_path):
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(backlog_dir, "TASK-1", "Critical target", priority="high")
    tracker = _tracker(tmp_path)

    with patch.object(tracker, "_run_backlog", return_value="") as run_backlog:
        tracker.update_issue("TASK-1", priority="critical")

    run_backlog.assert_not_called()
    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["priority"] == 0
    assert tracker.fetch_issue_detail("TASK-1").priority == 0


def test_mark_needs_human_updates_status_then_appends_comment(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Needs human")
    tracker = _tracker(tmp_path)

    with patch.object(tracker, "_run_backlog", return_value="") as run_backlog:
        tracker.mark_needs_human("TASK-1", "Human action required")

    assert run_backlog.call_args_list[0].args[0] == [
        "task", "edit", "TASK-1", "--plain", "--status", "Needs Human",
    ]
    assert len(run_backlog.call_args_list) == 1
    assert tracker.fetch_comments("TASK-1")[-1]["text"] == "Human action required"
    assert tracker.fetch_comments("TASK-1")[-1]["author"] == "oompah"


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


def test_create_issue_priority_zero_does_not_collapse_to_high(tmp_path):
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(backlog_dir, "TASK-7", "Critical feature", priority="medium")
    tracker = _tracker(tmp_path)

    with patch.object(
        tracker,
        "_run_backlog",
        return_value="Task TASK-7 - Critical feature\n",
    ) as run_backlog:
        issue = tracker.create_issue("Critical feature", priority=0)

    assert "--priority" not in run_backlog.call_args.args[0]
    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["priority"] == 0
    assert issue.priority == 0


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


# ---------------------------------------------------------------------------
# Regression tests for TASK-397 / TASK-408: custom frontmatter preservation
# ---------------------------------------------------------------------------


def _cli_strips_to_known_fields(task_path: Path, new_status: str):
    """Simulate what the Backlog CLI does: rewrite frontmatter, drop custom keys."""
    meta, body = _read_markdown_frontmatter(task_path)
    stripped = {
        k: v for k, v in meta.items()
        if k in {
            "id", "title", "status", "assignee", "created_date",
            "updated_date", "labels", "dependencies", "priority", "ordinal",
        }
    }
    stripped["status"] = new_status
    _write_markdown_frontmatter(task_path, stripped, body)


def test_update_issue_preserves_custom_frontmatter(tmp_path):
    """update_issue must not drop unknown frontmatter keys like type and beads."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-1",
        "Migrated task",
        extra_meta={
            "type": "feature",
            "beads": {
                "id": "oompah-zlz_2-54k",
                "state": "open",
                "branch_name": "oompah-zlz_2-54k",
                "created_at": "2026-05-05T20:18:01Z",
            },
        },
    )
    tracker = _tracker(tmp_path)

    def _fake_run_backlog(args):
        _cli_strips_to_known_fields(task_path, "In Progress")
        return ""

    with patch.object(tracker, "_run_backlog", side_effect=_fake_run_backlog):
        tracker.update_issue("TASK-1", status="in_progress")

    meta, _ = _read_markdown_frontmatter(task_path)
    assert meta["status"] == "In Progress", "status must be updated by CLI"
    assert meta["type"] == "feature", "custom 'type' must be preserved"
    assert isinstance(meta["beads"], dict), "nested 'beads' dict must be preserved"
    assert meta["beads"]["id"] == "oompah-zlz_2-54k"


def test_close_issue_preserves_custom_frontmatter(tmp_path):
    """close_issue must preserve custom frontmatter even when the task file is moved."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-2",
        "Closeable task",
        extra_meta={"type": "bug", "beads": {"id": "bead-99"}},
    )
    tracker = _tracker(tmp_path)

    def _fake_run_backlog(args):
        # Simulate CLI moving the file to completed/ and stripping custom keys.
        completed_path = backlog_dir / "completed" / task_path.name
        _cli_strips_to_known_fields(task_path, "Done")
        task_path.rename(completed_path)
        return ""

    with (
        patch.object(tracker, "_run_backlog", side_effect=_fake_run_backlog),
        patch.object(tracker, "add_comment"),
    ):
        tracker.close_issue("TASK-2", reason="Done")

    completed_path = backlog_dir / "completed" / task_path.name
    assert completed_path.exists(), "task file should be in completed/"
    meta, _ = _read_markdown_frontmatter(completed_path)
    assert meta["status"] == "Done"
    assert meta["type"] == "bug", "custom 'type' must survive close_issue"
    assert meta["beads"] == {"id": "bead-99"}, "custom 'beads' must survive close_issue"


def test_add_label_preserves_custom_frontmatter(tmp_path):
    """add_label must not drop unknown frontmatter keys."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-3",
        "Labeled task",
        extra_meta={"type": "chore", "beads": {"id": "bead-7", "seq": 3}},
    )
    tracker = _tracker(tmp_path)

    def _fake_run_backlog(args):
        meta, body = _read_markdown_frontmatter(task_path)
        # CLI strips custom fields and adds the new label
        stripped = {
            k: v for k, v in meta.items()
            if k in {
                "id", "title", "status", "assignee", "created_date",
                "updated_date", "labels", "dependencies", "priority",
            }
        }
        stripped["labels"] = stripped.get("labels", []) + ["needs-review"]
        _write_markdown_frontmatter(task_path, stripped, body)
        return ""

    with patch.object(tracker, "_run_backlog", side_effect=_fake_run_backlog):
        tracker.add_label("TASK-3", "needs-review")

    meta, _ = _read_markdown_frontmatter(task_path)
    assert "needs-review" in meta["labels"], "label must be added"
    assert meta["type"] == "chore", "custom 'type' must be preserved after add_label"
    assert meta["beads"]["seq"] == 3, "nested beads fields must be preserved"


def test_update_issue_known_fields_updated_once(tmp_path):
    """Normal Backlog fields must be updated exactly once with no duplication."""
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-4",
        "Normal task",
        extra_meta={"type": "task"},
    )
    tracker = _tracker(tmp_path)
    calls: list[list[str]] = []

    def _fake_run_backlog(args):
        calls.append(args)
        return ""

    with patch.object(tracker, "_run_backlog", side_effect=_fake_run_backlog):
        tracker.update_issue("TASK-4", status="in_progress", priority=1)

    # _run_backlog must be called exactly once (the CLI edit call)
    assert len(calls) == 1, f"expected 1 CLI call, got {len(calls)}: {calls}"
    assert "--status" in calls[0]
    assert "--priority" in calls[0]
