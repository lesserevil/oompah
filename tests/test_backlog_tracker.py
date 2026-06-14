"""Tests for the Backlog.md tracker adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from oompah.config import ServiceConfig
from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.roles import RoleStore
from oompah.tracker import (
    BacklogMdTracker,
    TrackerError,
    _YAML_SAFE_LOADER,
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


def test_frontmatter_parser_uses_accelerated_safe_loader_when_available(tmp_path):
    assert _YAML_SAFE_LOADER is getattr(yaml, "CSafeLoader", yaml.SafeLoader)

    path = _write_task(_write_config(tmp_path), "TASK-1", "Fast parser")

    meta, body = _read_markdown_frontmatter(path)

    assert meta["id"] == "TASK-1"
    assert "Fast parser" == meta["title"]
    assert "## Description" in body


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


def test_fetch_candidate_issues_excludes_proposed_even_if_configured_active(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Intake item", status="Proposed")
    _write_task(backlog_dir, "TASK-2", "Ready item", status="Open")
    tracker = BacklogMdTracker(
        active_states=["Proposed", "Open"],
        terminal_states=["Done"],
        cwd=str(tmp_path),
    )

    issues = tracker.fetch_candidate_issues()

    assert [issue.identifier for issue in issues] == ["TASK-2"]


def test_fetch_issue_detail_infers_epic_from_epic_title_without_label(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Epic: Ubuntu 22.04 Debian package support",
        labels=["feature", "infra"],
    )

    issue = _tracker(tmp_path).fetch_issue_detail("TASK-1")

    assert issue is not None
    assert issue.issue_type == "epic"


def test_fetch_issue_detail_infers_epic_from_epic_description_without_label(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Ubuntu 22.04 Debian package support",
        labels=["feature", "infra", "tooling"],
        description=(
            "Plan: plans/ubuntu-2204-support-plan.md.\n\n"
            "Epic for adding Jammy Debian package support while keeping Noble "
            "packages, package names, OCI relay compatibility, tests, and docs "
            "in sync."
        ),
    )

    issue = _tracker(tmp_path).fetch_issue_detail("TASK-1")

    assert issue is not None
    assert issue.issue_type == "epic"


def test_fetch_issue_detail_does_not_infer_epic_from_incidental_word(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Implement child task",
        description="Do the implementation work after the epic design lands.",
    )

    issue = _tracker(tmp_path).fetch_issue_detail("TASK-1")

    assert issue is not None
    assert issue.issue_type == "task"


def test_fetch_issue_detail_explicit_type_beats_epic_heuristic(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Epic: not actually an epic",
        extra_meta={"type": "feature"},
    )

    issue = _tracker(tmp_path).fetch_issue_detail("TASK-1")

    assert issue is not None
    assert issue.issue_type == "feature"


def test_fetch_candidate_issues_falls_back_for_malformed_frontmatter_id(tmp_path):
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-705",
        "Fix e2e Windows CMake dependency",
    )
    meta, body = _read_markdown_frontmatter(task_path)
    meta["id"] = "TASK-TASK-"
    meta["title"] = ""
    _write_markdown_frontmatter(task_path, meta, body)

    tracker = _tracker(tmp_path)
    issues = tracker.fetch_candidate_issues()
    issue = tracker.fetch_issue_detail("TASK-705")

    assert [candidate.identifier for candidate in issues] == ["TASK-705"]
    assert issue is not None
    assert issue.identifier == "TASK-705"
    assert issue.title == "Fix e2e Windows CMake dependency"
    assert issue.branch_name == "TASK-705"
    assert tracker.fetch_issue_detail("TASK-TASK-") is None


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


def test_read_stats_records_parse_and_cache_hit(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Open task")
    tracker = _tracker(tmp_path)

    tracker.fetch_all_issues()
    first = tracker.read_stats()
    tracker.fetch_all_issues()
    second = tracker.read_stats()

    assert first["cache_hit"] is False
    assert first["record_count"] == 1
    assert first["duration_ms"] >= 0
    assert second["cache_hit"] is True
    assert second["record_count"] == 1


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


def test_fetch_comments_parses_native_backlog_cli_comment_blocks(tmp_path):
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(backlog_dir, "TASK-1", "Native comments")
    text = task_path.read_text(encoding="utf-8")
    task_path.write_text(
        text
        + """\

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 10:36
---
Completion correction mirrored from epic-TASK-464.
---

author: oompah
created: 2026-06-10 13:59
---
Human needed: choose/approve the canary repo.
Confirm the GitHub task hub owner/repo before cutover.
---
<!-- COMMENTS:END -->
""",
        encoding="utf-8",
    )

    comments = _tracker(tmp_path).fetch_comments("TASK-1")

    assert comments == [
        {
            "id": "1",
            "author": "oompah",
            "created_at": "2026-06-10 10:36",
            "text": "Completion correction mirrored from epic-TASK-464.",
        },
        {
            "id": "2",
            "author": "oompah",
            "created_at": "2026-06-10 13:59",
            "text": (
                "Human needed: choose/approve the canary repo.\n"
                "Confirm the GitHub task hub owner/repo before cutover."
            ),
        },
    ]


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


def test_update_issue_status_only_preserves_p0_priority(tmp_path):
    """A status-only update must not clobber an existing priority: 0 field.

    Regression test for TASK-465.6: during restart recovery, tasks were marked
    Open via update_issue(identifier, status=OPEN) with no priority argument.
    The Backlog CLI dropped the numeric priority: 0 from frontmatter because it
    only understands named priority strings.  The snapshot/restore mechanism
    must now include numeric priority values so they survive the CLI round-trip.
    """
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(backlog_dir, "TASK-1", "P0 recovery task", priority=0)
    tracker = _tracker(tmp_path)

    def _cli_drops_priority(_args):
        """Simulate the Backlog CLI silently dropping priority: 0."""
        meta, body = _read_markdown_frontmatter(task_path)
        meta["status"] = "In Progress"
        # CLI does not recognise numeric priority — it omits the key entirely.
        meta.pop("priority", None)
        task_path.write_text(
            "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body,
            encoding="utf-8",
        )
        return ""

    with patch.object(tracker, "_run_backlog", side_effect=_cli_drops_priority):
        tracker.update_issue("TASK-1", status="In Progress")

    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["priority"] == 0, "priority: 0 must be preserved after status-only update"
    assert tracker.fetch_issue_detail("TASK-1").priority == 0


def test_reopen_issue_preserves_p0_priority(tmp_path):
    """reopen_issue must not strip an existing priority: 0 field.

    Regression test for TASK-465.6: the verifier-rejection and orphan-reset
    paths call reopen_issue(), which previously did not protect numeric priority
    from the Backlog CLI stripping it during the status rewrite.
    """
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(backlog_dir, "TASK-1", "P0 reopened", priority=0)
    tracker = _tracker(tmp_path)

    def _cli_drops_priority(_args):
        """Simulate the Backlog CLI silently dropping priority: 0."""
        meta, body = _read_markdown_frontmatter(task_path)
        meta["status"] = "Open"
        meta.pop("priority", None)
        task_path.write_text(
            "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body,
            encoding="utf-8",
        )
        return ""

    with patch.object(tracker, "_run_backlog", side_effect=_cli_drops_priority):
        tracker.reopen_issue("TASK-1")

    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["priority"] == 0, "priority: 0 must survive reopen_issue"
    assert tracker.fetch_issue_detail("TASK-1").priority == 0


def test_restart_recovery_preserves_p0_priority(tmp_path):
    """Restart recovery (status=Open, no priority arg) must not drop priority: 0.

    Regression test for TASK-465.6: _recover_restart_issues calls
    tracker.update_issue(identifier, status=OPEN), which is a pure status-only
    call.  Verify this is functionally equivalent to the status-only test above
    and that the issue still reads back as P0 afterwards.
    """
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(backlog_dir, "TASK-1", "P0 undrained", priority=0)
    tracker = _tracker(tmp_path)

    def _cli_drops_priority(_args):
        meta, body = _read_markdown_frontmatter(task_path)
        # Mimic the CLI rewriting the file during a --status Open edit and
        # discarding the numeric priority it cannot represent.
        meta["status"] = "Open"
        meta.pop("priority", None)
        task_path.write_text(
            "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body,
            encoding="utf-8",
        )
        return ""

    # This mirrors exactly what _recover_restart_issues does:
    #   tracker.update_issue(identifier, status=OPEN)
    with patch.object(tracker, "_run_backlog", side_effect=_cli_drops_priority):
        tracker.update_issue("TASK-1", status="Open")

    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["priority"] == 0, "priority: 0 must survive restart-recovery status update"
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


# ---------------------------------------------------------------------------
# Integration test: _write_task_cost_record with real BacklogMdTracker
# (TASK-399: cost metadata uses get_metadata / set_metadata_field protocol)
# ---------------------------------------------------------------------------

def test_write_task_cost_record_works_with_backlog_tracker(tmp_path):
    """_write_task_cost_record persists cost data via BacklogMdTracker."""
    from oompah.models import AgentProfile, ModelProvider, RunningEntry
    from oompah.orchestrator import Orchestrator
    from oompah.config import ServiceConfig
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-5", "Agent work item")

    project_store = MagicMock()
    project_store.list_all.return_value = []
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
        state_path=str(tmp_path / "state.json"),
    )
    # Wire up a real BacklogMdTracker pointed at tmp_path
    tracker = BacklogMdTracker(
        active_states=["To Do", "In Progress"],
        terminal_states=["Done"],
        cwd=str(tmp_path),
    )
    orch.tracker = tracker

    provider = ModelProvider(
        id="prov-test",
        name="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        models=["gpt-4o"],
        default_model="gpt-4o",
        model_costs={"gpt-4o": {"cost_per_1k_input": 0.005, "cost_per_1k_output": 0.015}},
    )
    orch.provider_store._providers["prov-test"] = provider
    profile = AgentProfile(
        name="standard", command="agent", provider_id="prov-test", model="gpt-4o",
    )
    orch.config.agent_profiles = [profile]

    from oompah.models import LiveSession, Issue
    session = LiveSession(session_id="s1", thread_id="t1", turn_id="0", agent_pid=None)
    session.input_tokens = 1000
    session.output_tokens = 500
    session.total_tokens = 1500

    issue = Issue(id="TASK-5", identifier="TASK-5", title="Agent work item",
                  description="", state="In Progress")
    entry = RunningEntry(
        worker_task=MagicMock(),
        identifier="TASK-5",
        issue=issue,
        session=session,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="standard",
    )

    # Should not raise — uses BacklogMdTracker's get_metadata/set_metadata_field API
    orch._write_task_cost_record(entry)

    # Verify the cost was stored in the frontmatter via get_metadata
    meta = tracker.get_metadata("TASK-5")
    assert "oompah.task_costs" in meta, "Cost metadata should have been written to frontmatter"
    costs = meta["oompah.task_costs"]
    assert costs["total_input_tokens"] == 1000
    assert costs["total_output_tokens"] == 500
    assert "gpt-4o" in costs["by_model"]


# ---------------------------------------------------------------------------
# Regression tests for TASK-427: update_issue falls back to direct editing
# when the Backlog CLI reports "task not found" (e.g. task is in completed/).
# ---------------------------------------------------------------------------


def test_update_issue_falls_back_to_direct_edit_when_cli_says_not_found(tmp_path):
    """update_issue must silently fall back to direct file editing when the
    Backlog CLI returns a 'not found' error but the task exists on disk."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-10",
        "Completed task",
        status="Done",
        folder="completed",
    )
    tracker = _tracker(tmp_path)

    def _cli_not_found(args):
        raise TrackerError("backlog command failed (exit 1): Task TASK-10 not found.")

    with patch.object(tracker, "_run_backlog", side_effect=_cli_not_found):
        # Should not raise — falls back to direct edit
        tracker.update_issue("TASK-10", status="In Progress")

    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["status"] == "In Progress", "status must be written directly to frontmatter"


def test_update_issue_direct_fallback_updates_title(tmp_path):
    """Direct fallback must handle title updates for completed tasks."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-11",
        "Old title",
        status="Done",
        folder="completed",
    )
    tracker = _tracker(tmp_path)

    with patch.object(
        tracker,
        "_run_backlog",
        side_effect=TrackerError("backlog command failed (exit 1): Task TASK-11 not found."),
    ):
        tracker.update_issue("TASK-11", title="New title")

    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["title"] == "New title"


def test_update_issue_direct_fallback_updates_description(tmp_path):
    """Direct fallback must update the description section in the body."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-12",
        "Desc task",
        status="Done",
        folder="completed",
        description="Old description",
    )
    tracker = _tracker(tmp_path)

    with patch.object(
        tracker,
        "_run_backlog",
        side_effect=TrackerError("backlog command failed (exit 1): Task TASK-12 not found."),
    ):
        tracker.update_issue("TASK-12", description="New description")

    content = task_path.read_text(encoding="utf-8")
    assert "New description" in content
    assert "Old description" not in content


def test_update_issue_direct_fallback_add_remove_label(tmp_path):
    """Direct fallback must handle add-label and remove-label."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-13",
        "Label task",
        status="Done",
        folder="completed",
        labels=["existing"],
    )
    tracker = _tracker(tmp_path)

    with patch.object(
        tracker,
        "_run_backlog",
        side_effect=TrackerError("backlog command failed (exit 1): Task TASK-13 not found."),
    ):
        tracker.update_issue("TASK-13", **{"add-label": "new-label"})

    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert "new-label" in meta["labels"]
    assert "existing" in meta["labels"]

    with patch.object(
        tracker,
        "_run_backlog",
        side_effect=TrackerError("backlog command failed (exit 1): Task TASK-13 not found."),
    ):
        tracker.update_issue("TASK-13", **{"remove-label": "existing"})

    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert "existing" not in meta["labels"]
    assert "new-label" in meta["labels"]


def test_update_issue_direct_fallback_updates_updated_date(tmp_path):
    """Direct fallback must update updated_date in the frontmatter."""
    backlog_dir = _write_config(tmp_path)
    task_path = _write_task(
        backlog_dir,
        "TASK-14",
        "Date task",
        status="Done",
        folder="completed",
    )
    tracker = _tracker(tmp_path)

    with patch.object(
        tracker,
        "_run_backlog",
        side_effect=TrackerError("backlog command failed (exit 1): Task TASK-14 not found."),
    ):
        tracker.update_issue("TASK-14", status="In Progress")

    meta = yaml.safe_load(task_path.read_text(encoding="utf-8").split("---\n", 2)[1])
    assert meta["updated_date"] != "2026-05-31 10:05", "updated_date must be refreshed"


def test_update_issue_reraises_other_cli_errors(tmp_path):
    """update_issue must not suppress CLI errors unrelated to 'not found'."""
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-15", "Active task")
    tracker = _tracker(tmp_path)

    with patch.object(
        tracker,
        "_run_backlog",
        side_effect=TrackerError("backlog command failed (exit 1): Invalid status: Foo"),
    ):
        import pytest
        with pytest.raises(TrackerError, match="Invalid status"):
            tracker.update_issue("TASK-15", status="Foo")


def test_update_issue_reraises_not_found_when_task_absent_from_disk(tmp_path):
    """update_issue must re-raise when the CLI fails AND the task is not on disk."""
    _write_config(tmp_path)
    tracker = _tracker(tmp_path)

    with patch.object(
        tracker,
        "_run_backlog",
        side_effect=TrackerError("backlog command failed (exit 1): Task TASK-99 not found."),
    ):
        import pytest
        with pytest.raises(TrackerError, match="not found"):
            tracker.update_issue("TASK-99", status="In Progress")


# ---------------------------------------------------------------------------
# Per-tick read cache (perf: collapse repeated full-corpus parses)
# ---------------------------------------------------------------------------


def test_read_cache_collapses_repeated_reads(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "A")
    tracker = _tracker(tmp_path)
    with patch.object(tracker, "_task_files", wraps=tracker._task_files) as spy:
        tracker.fetch_all_issues()
        tracker.fetch_all_issues()
    # Second read served from cache → the corpus is globbed/parsed only once.
    assert spy.call_count == 1


def test_invalidate_read_cache_forces_reread(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "A")
    tracker = _tracker(tmp_path)
    with patch.object(tracker, "_task_files", wraps=tracker._task_files) as spy:
        tracker.fetch_all_issues()
        tracker.invalidate_read_cache()
        tracker.fetch_all_issues()
    assert spy.call_count == 2


def test_write_invalidates_read_cache(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "A", status="Open")
    tracker = _tracker(tmp_path)
    # Prime the cache.
    assert any(i.identifier == "TASK-1" for i in tracker.fetch_all_issues())
    # A direct frontmatter write must bust the cache so the next read is fresh.
    tracker._set_frontmatter_field("TASK-1", "status", "Done")
    t1 = next(i for i in tracker.fetch_all_issues() if i.identifier == "TASK-1")
    assert t1.state.lower() == "done"


def test_completed_and_active_reads_cached_independently(tmp_path):
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "A", status="Open")
    _write_task(backlog_dir, "TASK-2", "B", status="Done", folder="completed")
    tracker = _tracker(tmp_path)
    with patch.object(tracker, "_task_files", wraps=tracker._task_files) as spy:
        tracker.fetch_candidate_issues()          # include_completed=False
        tracker.fetch_all_issues()                # include_completed=True
        tracker.fetch_candidate_issues()          # cached
        tracker.fetch_all_issues()                # cached
    # One miss per include_completed variant, then all cached.
    assert spy.call_count == 2


# ---------------------------------------------------------------------------
# Tests for TASK-454.1: target_branch and release-pick metadata reading
# ---------------------------------------------------------------------------


def test_normalize_task_sets_target_branch_from_oompah_frontmatter(tmp_path):
    """Issue.target_branch is populated from oompah.target_branch frontmatter."""
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Release pick",
        extra_meta={"oompah.target_branch": "release/1.2"},
    )

    issue = _tracker(tmp_path).fetch_issue_detail("TASK-1")

    assert issue is not None
    assert issue.target_branch == "release/1.2"


def test_normalize_task_target_branch_missing_yields_none(tmp_path):
    """Issue.target_branch is None when no target_branch frontmatter is present."""
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Regular task")

    issue = _tracker(tmp_path).fetch_issue_detail("TASK-1")

    assert issue is not None
    assert issue.target_branch is None


def test_normalize_task_sets_target_branch_from_compatible_frontmatter(tmp_path):
    """Issue.target_branch falls back to the top-level target_branch field."""
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Compat target branch",
        extra_meta={"target_branch": "hotfix/critical"},
    )

    issue = _tracker(tmp_path).fetch_issue_detail("TASK-1")

    assert issue is not None
    assert issue.target_branch == "hotfix/critical"


def test_normalize_task_oompah_target_branch_takes_precedence(tmp_path):
    """oompah.target_branch wins over the compatible top-level target_branch."""
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Priority check",
        extra_meta={
            "oompah.target_branch": "release/2.0",
            "target_branch": "old-field",
        },
    )

    issue = _tracker(tmp_path).fetch_issue_detail("TASK-1")

    assert issue is not None
    assert issue.target_branch == "release/2.0"


def test_normalize_task_loads_release_pick_metadata(tmp_path):
    """Issue carries release-pick metadata from frontmatter after normalization."""
    backlog_dir = _write_config(tmp_path)
    backports = [{"branch": "release/1.0", "status": "waiting"}]
    backport_of = {"source": "TASK-100", "status": "task_created"}
    _write_task(
        backlog_dir,
        "TASK-1",
        "Release metadata",
        extra_meta={
            "oompah.backports": backports,
            "oompah.backport_of": backport_of,
        },
    )

    issue = _tracker(tmp_path).fetch_issue_detail("TASK-1")

    assert issue is not None
    assert issue.backports == backports
    assert issue.backport_of == backport_of
    assert issue.release_pick_metadata_loaded is True


def test_get_metadata_returns_scalar_backport_of(tmp_path):
    """get_metadata exposes oompah.backport_of as a scalar string."""
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Backport task",
        extra_meta={"oompah.backport_of": "TASK-100"},
    )

    meta = _tracker(tmp_path).get_metadata("TASK-1")

    assert meta.get("oompah.backport_of") == "TASK-100"


def test_get_metadata_returns_scalar_backports(tmp_path):
    """get_metadata exposes oompah.backports as a scalar branch name."""
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Has backport branch",
        extra_meta={"oompah.backports": "release/1.0"},
    )

    meta = _tracker(tmp_path).get_metadata("TASK-1")

    assert meta.get("oompah.backports") == "release/1.0"


def test_get_metadata_returns_nested_backports_list(tmp_path):
    """get_metadata exposes oompah.backports as a list of branch names."""
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Multi-backport",
        extra_meta={"oompah.backports": ["release/1.0", "release/2.0"]},
    )

    meta = _tracker(tmp_path).get_metadata("TASK-1")

    assert meta.get("oompah.backports") == ["release/1.0", "release/2.0"]


def test_get_metadata_returns_nested_backport_of_dict(tmp_path):
    """get_metadata exposes oompah.backport_of as a nested dict."""
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-1",
        "Nested backport_of",
        extra_meta={
            "oompah.backport_of": {
                "identifier": "TASK-42",
                "branch": "release/1.5",
            }
        },
    )

    meta = _tracker(tmp_path).get_metadata("TASK-1")

    assert meta.get("oompah.backport_of") == {
        "identifier": "TASK-42",
        "branch": "release/1.5",
    }


def test_get_metadata_missing_backport_fields_returns_empty(tmp_path):
    """get_metadata returns an empty dict when no oompah.* keys are present."""
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Plain task")

    meta = _tracker(tmp_path).get_metadata("TASK-1")

    assert "oompah.backports" not in meta
    assert "oompah.backport_of" not in meta
    assert "oompah.target_branch" not in meta


def test_set_metadata_field_stores_and_retrieves_backports(tmp_path):
    """set_metadata_field persists oompah.backports and get_metadata reads it back."""
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Backport target")
    tracker = _tracker(tmp_path)

    tracker.set_metadata_field("TASK-1", "oompah.backports", ["release/3.0", "release/3.1"])

    meta = tracker.get_metadata("TASK-1")
    assert meta["oompah.backports"] == ["release/3.0", "release/3.1"]


def test_set_metadata_field_stores_and_retrieves_backport_of(tmp_path):
    """set_metadata_field persists oompah.backport_of and get_metadata reads it back."""
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Backport origin")
    tracker = _tracker(tmp_path)

    tracker.set_metadata_field("TASK-1", "oompah.backport_of", "TASK-200")

    meta = tracker.get_metadata("TASK-1")
    assert meta["oompah.backport_of"] == "TASK-200"


def test_set_metadata_field_stores_and_retrieves_target_branch(tmp_path):
    """set_metadata_field persists oompah.target_branch and it populates Issue."""
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-1", "Branch target")
    tracker = _tracker(tmp_path)

    tracker.set_metadata_field("TASK-1", "oompah.target_branch", "release/4.0")

    issue = tracker.fetch_issue_detail("TASK-1")
    assert issue is not None
    assert issue.target_branch == "release/4.0"
    meta = tracker.get_metadata("TASK-1")
    assert meta["oompah.target_branch"] == "release/4.0"


def test_fetch_in_progress_issues_returns_only_in_progress(tmp_path):
    """fetch_in_progress_issues() returns tasks in In Progress state only."""
    backlog_dir = _write_config(tmp_path)
    _write_task(backlog_dir, "TASK-10", "Open task", status="Open")
    _write_task(backlog_dir, "TASK-11", "In progress task", status="In Progress")
    _write_task(backlog_dir, "TASK-12", "Another in progress", status="in_progress")
    _write_task(backlog_dir, "TASK-13", "Done task", status="Done", folder="completed")

    issues = _tracker(tmp_path).fetch_in_progress_issues()

    identifiers = {i.identifier for i in issues}
    assert "TASK-10" not in identifiers
    assert "TASK-11" in identifiers
    assert "TASK-12" in identifiers
    assert "TASK-13" not in identifiers


def test_fetch_in_progress_issues_excludes_completed_folder(tmp_path):
    """fetch_in_progress_issues() does not include completed tasks."""
    backlog_dir = _write_config(tmp_path)
    _write_task(
        backlog_dir,
        "TASK-20",
        "Stale done",
        status="In Progress",
        folder="completed",
    )
    _write_task(backlog_dir, "TASK-21", "Active in progress", status="In Progress")

    issues = _tracker(tmp_path).fetch_in_progress_issues()

    identifiers = {i.identifier for i in issues}
    assert "TASK-20" not in identifiers
    assert "TASK-21" in identifiers


# ---------------------------------------------------------------------------
# Tests for TASK-461.1: per-project tracker resolution via the adapter registry
# ---------------------------------------------------------------------------


def _make_orch(tmp_path, *, global_tracker_kind="backlog_md"):
    """Helper: build a minimal Orchestrator with a mocked ProjectStore."""
    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.return_value = None
    config = ServiceConfig(
        tracker_kind=global_tracker_kind,
        tracker_active_states=["Open"],
        tracker_terminal_states=["Done"],
        workspace_root=str(tmp_path / "workspaces"),
    )
    return Orchestrator(
        config=config,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=RoleStore(path=str(tmp_path / "roles.json")),
        state_path=str(tmp_path / "state.json"),
    )


def _make_project(
    *,
    project_id: str = "proj-1",
    repo_url: str = "https://example.com/repo.git",
    repo_path: str = "/tmp/repo",
    tracker_kind: str | None = None,
    tracker_owner: str | None = None,
    tracker_repo: str | None = None,
    access_token: str | None = None,
):
    """Helper: build a minimal Project with optional tracker fields."""
    from oompah.models import Project

    return Project(
        id=project_id,
        name="Test Project",
        repo_url=repo_url,
        repo_path=repo_path,
        tracker_kind=tracker_kind,
        tracker_owner=tracker_owner,
        tracker_repo=tracker_repo,
        access_token=access_token,
    )


class TestNewTrackerForProject:
    """Tests for Orchestrator._new_tracker_for_project (TASK-461.1 AC #1)."""

    def test_project_without_tracker_kind_uses_global_backlog_md(self, tmp_path):
        """A project with no tracker_kind inherits the global backlog_md config."""
        orch = _make_orch(tmp_path, global_tracker_kind="backlog_md")
        project = _make_project(repo_path=str(tmp_path))

        tracker = orch._new_tracker_for_project(project)

        assert isinstance(tracker, BacklogMdTracker)

    def test_project_with_explicit_backlog_md_returns_backlog_tracker(self, tmp_path):
        """A project with tracker_kind='backlog_md' gets a BacklogMdTracker."""
        orch = _make_orch(tmp_path, global_tracker_kind="backlog_md")
        project = _make_project(repo_path=str(tmp_path), tracker_kind="backlog_md")

        tracker = orch._new_tracker_for_project(project)

        assert isinstance(tracker, BacklogMdTracker)

    def test_project_with_github_issues_calls_factory_with_owner_and_repo(self, tmp_path):
        """A github_issues project passes tracker_owner/repo to the factory."""
        from oompah.tracker import ADAPTER_REGISTRY

        factory_calls: list[dict] = []

        def _fake_gh_factory(**kwargs):
            factory_calls.append(dict(kwargs))
            return MagicMock()

        orch = _make_orch(tmp_path, global_tracker_kind="backlog_md")
        project = _make_project(
            repo_path=str(tmp_path),
            tracker_kind="github_issues",
            tracker_owner="myorg",
            tracker_repo="myrepo",
        )

        original = ADAPTER_REGISTRY.get("github_issues")
        ADAPTER_REGISTRY["github_issues"] = _fake_gh_factory
        try:
            orch._new_tracker_for_project(project)
        finally:
            if original is not None:
                ADAPTER_REGISTRY["github_issues"] = original
            else:
                ADAPTER_REGISTRY.pop("github_issues", None)

        assert len(factory_calls) == 1
        call = factory_calls[0]
        assert call["owner"] == "myorg"
        assert call["repo"] == "myrepo"
        assert call["cwd"] == str(tmp_path)

    def test_project_with_github_issues_passes_access_token_to_factory(self, tmp_path):
        """A github_issues project passes its managed access_token to the tracker."""
        from oompah.tracker import ADAPTER_REGISTRY

        factory_calls: list[dict] = []

        def _fake_gh_factory(**kwargs):
            factory_calls.append(dict(kwargs))
            return MagicMock()

        orch = _make_orch(tmp_path, global_tracker_kind="backlog_md")
        project = _make_project(
            repo_path=str(tmp_path),
            tracker_kind="github_issues",
            tracker_owner="myorg",
            tracker_repo="myrepo",
            access_token="ghp_project_token",
        )

        original = ADAPTER_REGISTRY.get("github_issues")
        ADAPTER_REGISTRY["github_issues"] = _fake_gh_factory
        try:
            orch._new_tracker_for_project(project)
        finally:
            if original is not None:
                ADAPTER_REGISTRY["github_issues"] = original
            else:
                ADAPTER_REGISTRY.pop("github_issues", None)

        assert len(factory_calls) == 1
        assert factory_calls[0]["access_token"] == "ghp_project_token"

    def test_project_with_github_issues_infers_owner_repo_from_repo_url(self, tmp_path):
        """A github_issues project can infer owner/repo from a GitHub repo URL."""
        from oompah.tracker import ADAPTER_REGISTRY

        factory_calls: list[dict] = []

        def _fake_gh_factory(**kwargs):
            factory_calls.append(dict(kwargs))
            return MagicMock()

        orch = _make_orch(tmp_path, global_tracker_kind="backlog_md")
        project = _make_project(
            repo_url="https://actor@github.com/example-org/example-repo.git",
            repo_path=str(tmp_path),
            tracker_kind="github_issues",
            # tracker_owner and tracker_repo intentionally omitted
        )

        original = ADAPTER_REGISTRY.get("github_issues")
        ADAPTER_REGISTRY["github_issues"] = _fake_gh_factory
        try:
            orch._new_tracker_for_project(project)
        finally:
            if original is not None:
                ADAPTER_REGISTRY["github_issues"] = original
            else:
                ADAPTER_REGISTRY.pop("github_issues", None)

        assert len(factory_calls) == 1
        call = factory_calls[0]
        assert call["owner"] == "example-org"
        assert call["repo"] == "example-repo"

    def test_project_with_github_issues_but_no_owner_repo_raises(self, tmp_path):
        """Missing owner/repo must not fall back to the global task hub."""
        orch = _make_orch(tmp_path, global_tracker_kind="backlog_md")
        project = _make_project(
            repo_url="https://gitlab.com/example-org/example-repo.git",
            repo_path=str(tmp_path),
            tracker_kind="github_issues",
        )

        with pytest.raises(TrackerError, match="tracker_owner and tracker_repo"):
            orch._new_tracker_for_project(project)

    def test_project_with_unknown_tracker_kind_raises_tracker_error(self, tmp_path):
        """An unregistered tracker_kind raises TrackerError with the project id."""
        import pytest

        orch = _make_orch(tmp_path)
        project = _make_project(tracker_kind="jira")

        with pytest.raises(TrackerError, match="jira"):
            orch._new_tracker_for_project(project)

    def test_project_tracker_kind_overrides_global_kind(self, tmp_path):
        """Project-level tracker_kind wins over the global config."""
        from oompah.tracker import ADAPTER_REGISTRY

        factory_calls: list[dict] = []

        def _fake_gh_factory(**kwargs):
            factory_calls.append(dict(kwargs))
            return MagicMock()

        orch = _make_orch(tmp_path, global_tracker_kind="backlog_md")
        project = _make_project(
            repo_path=str(tmp_path),
            tracker_kind="github_issues",
            tracker_owner="org",
            tracker_repo="hub",
        )

        original = ADAPTER_REGISTRY.get("github_issues")
        ADAPTER_REGISTRY["github_issues"] = _fake_gh_factory
        try:
            tracker = orch._new_tracker_for_project(project)
        finally:
            if original is not None:
                ADAPTER_REGISTRY["github_issues"] = original
            else:
                ADAPTER_REGISTRY.pop("github_issues", None)

        # Factory was called (not BacklogMdTracker)
        assert len(factory_calls) == 1
        assert not isinstance(tracker, BacklogMdTracker)


class TestTrackerForProject:
    """Tests for Orchestrator._tracker_for_project (TASK-461.1 AC #2)."""

    def test_returns_backlog_tracker_for_legacy_project(self, tmp_path):
        """_tracker_for_project returns BacklogMdTracker for an unlabeled project."""
        orch = _make_orch(tmp_path)
        project = _make_project(project_id="p1", repo_path=str(tmp_path))
        orch.project_store.get.return_value = project

        tracker = orch._tracker_for_project("p1")

        assert isinstance(tracker, BacklogMdTracker)

    def test_caches_tracker_on_second_call(self, tmp_path):
        """_tracker_for_project returns the same instance on repeated calls."""
        orch = _make_orch(tmp_path)
        project = _make_project(project_id="p1", repo_path=str(tmp_path))
        orch.project_store.get.return_value = project

        first = orch._tracker_for_project("p1")
        second = orch._tracker_for_project("p1")

        assert first is second

    def test_cache_is_project_scoped(self, tmp_path):
        """Different project ids produce independent tracker instances."""
        orch = _make_orch(tmp_path)
        proj_a = _make_project(project_id="proj-a", repo_path=str(tmp_path))
        proj_b = _make_project(project_id="proj-b", repo_path=str(tmp_path))
        orch.project_store.get.side_effect = lambda pid: {
            "proj-a": proj_a,
            "proj-b": proj_b,
        }.get(pid)

        tracker_a = orch._tracker_for_project("proj-a")
        tracker_b = orch._tracker_for_project("proj-b")

        assert tracker_a is not tracker_b

    def test_raises_project_error_for_unknown_project_id(self, tmp_path):
        """_tracker_for_project raises ProjectError when the project does not exist."""
        import pytest
        from oompah.projects import ProjectError

        orch = _make_orch(tmp_path)
        orch.project_store.get.return_value = None

        with pytest.raises(ProjectError, match="unknown-proj"):
            orch._tracker_for_project("unknown-proj")

    def test_github_project_gets_different_tracker_type(self, tmp_path):
        """A GitHub-backed project yields a different tracker type than a legacy project."""
        from oompah.tracker import ADAPTER_REGISTRY

        github_tracker_mock = MagicMock()

        def _fake_gh_factory(**kwargs):
            return github_tracker_mock

        orch = _make_orch(tmp_path)
        legacy_proj = _make_project(project_id="legacy", repo_path=str(tmp_path))
        gh_proj = _make_project(
            project_id="github",
            repo_path=str(tmp_path),
            tracker_kind="github_issues",
            tracker_owner="org",
            tracker_repo="hub",
        )
        orch.project_store.get.side_effect = lambda pid: {
            "legacy": legacy_proj,
            "github": gh_proj,
        }.get(pid)

        original = ADAPTER_REGISTRY.get("github_issues")
        ADAPTER_REGISTRY["github_issues"] = _fake_gh_factory
        try:
            legacy_tracker = orch._tracker_for_project("legacy")
            gh_tracker = orch._tracker_for_project("github")
        finally:
            if original is not None:
                ADAPTER_REGISTRY["github_issues"] = original
            else:
                ADAPTER_REGISTRY.pop("github_issues", None)

        assert isinstance(legacy_tracker, BacklogMdTracker)
        assert gh_tracker is github_tracker_mock


class TestGitHubIssuesFactoryOwnerRepoKwargs:
    """Tests for _github_issues_factory kwarg precedence (TASK-461.1).

    Verifies that owner/repo kwargs take precedence over env vars so
    per-project tracker configuration is honoured by the factory.
    """

    def test_kwargs_owner_repo_preferred_over_env_vars(self, tmp_path, monkeypatch):
        """Explicit owner/repo kwargs must be used even when env vars differ."""
        from oompah.github_tracker import _github_issues_factory, GitHubIssueTracker

        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_OWNER", "env-org")
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_REPO", "env-repo")

        with patch("oompah.github_tracker.GitHubAuth"):
            tracker = _github_issues_factory(
                active_states=["Open"],
                terminal_states=["Done"],
                owner="kwarg-org",
                repo="kwarg-repo",
            )

        assert tracker.owner == "kwarg-org"
        assert tracker.repo == "kwarg-repo"

    def test_falls_back_to_env_vars_when_no_kwargs(self, tmp_path, monkeypatch):
        """Without owner/repo kwargs the factory must read env vars."""
        from oompah.github_tracker import _github_issues_factory

        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_OWNER", "env-owner")
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_REPO", "env-repo")

        with patch("oompah.github_tracker.GitHubAuth"):
            tracker = _github_issues_factory(
                active_states=["Open"],
                terminal_states=["Done"],
            )

        assert tracker.owner == "env-owner"
        assert tracker.repo == "env-repo"

    def test_raises_tracker_error_when_neither_kwargs_nor_env_set(self, monkeypatch):
        """TrackerError must be raised when owner/repo cannot be resolved."""
        import pytest
        from oompah.github_tracker import _github_issues_factory

        monkeypatch.delenv("OOMPAH_GITHUB_TRACKER_OWNER", raising=False)
        monkeypatch.delenv("OOMPAH_GITHUB_TRACKER_REPO", raising=False)

        with pytest.raises(TrackerError, match="OOMPAH_GITHUB_TRACKER_OWNER"):
            _github_issues_factory(
                active_states=["Open"],
                terminal_states=["Done"],
            )

    def test_partial_env_only_owner_raises_tracker_error(self, monkeypatch):
        """Only owner in env (no repo) must still raise TrackerError."""
        import pytest
        from oompah.github_tracker import _github_issues_factory

        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_OWNER", "some-org")
        monkeypatch.delenv("OOMPAH_GITHUB_TRACKER_REPO", raising=False)

        with pytest.raises(TrackerError):
            _github_issues_factory(
                active_states=["Open"],
                terminal_states=["Done"],
            )
