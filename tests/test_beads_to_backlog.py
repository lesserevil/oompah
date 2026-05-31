"""Tests for the beads to Backlog.md migration utility."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import yaml

from oompah.beads_to_backlog import (
    MigrationOptions,
    _ensure_backlog_project,
    migrate_beads_to_backlog,
)
from oompah.models import BlockerRef, Issue
from oompah.tracker import _read_markdown_frontmatter


class FakeBeadsSource:
    def __init__(
        self,
        issues: list[Issue],
        *,
        comments: dict[str, list[dict]] | None = None,
        attachments: dict[str, list[dict]] | None = None,
    ):
        self._issues = issues
        self._comments = comments or {}
        self._attachments = attachments or {}

    def fetch_all_issues_enriched(self) -> list[Issue]:
        return list(self._issues)

    def fetch_comments(self, identifier: str) -> list[dict]:
        return list(self._comments.get(identifier, []))

    def fetch_attachments(self, identifier: str) -> list[dict]:
        return list(self._attachments.get(identifier, []))


def _write_backlog_config(root, *, prefix: str = "task"):
    backlog_dir = root / "backlog"
    (backlog_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "completed").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "config.yml").write_text(
        "\n".join([
            'project_name: "Migrated"',
            'default_status: "To Do"',
            'statuses: ["To Do", "In Progress", "Done"]',
            f'task_prefix: "{prefix}"',
            "labels: []",
            "",
        ]),
        encoding="utf-8",
    )
    return backlog_dir


def _issue(identifier: str, title: str, **kwargs) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        created_at=kwargs.pop("created_at", datetime(2026, 5, 31, tzinfo=timezone.utc)),
        **kwargs,
    )


def test_migration_creates_backlog_tasks_with_mapped_relations(tmp_path):
    backlog_dir = _write_backlog_config(tmp_path)
    source = FakeBeadsSource(
        [
            _issue("bd-1", "Build epic", issue_type="epic", labels=["planning"]),
            _issue("bd-2", "Fix blocker", issue_type="bug", labels=["backend"]),
            _issue(
                "bd-3",
                "Child task",
                parent_id="bd-1",
                blocked_by=[BlockerRef(identifier="bd-2")],
                description="Do the child work",
                priority=1,
            ),
        ],
        comments={
            "bd-3": [{
                "id": 7,
                "author": "oompah",
                "created_at": "2026-05-31T12:00:00Z",
                "text": "Progress note",
            }],
        },
        attachments={
            "bd-3": [{
                "path": ".oompah/attachments/bd-3/mock.png",
                "mime": "image/png",
            }],
        },
    )

    result = migrate_beads_to_backlog(
        MigrationOptions(source=str(tmp_path), backlog_dir="backlog"),
        source_tracker=source,
    )

    assert result.created == 3
    assert result.mapping == {
        "bd-1": "TASK-1",
        "bd-2": "TASK-2",
        "bd-3": "TASK-3",
    }

    child_path = next((backlog_dir / "tasks").glob("task-3 - *.md"))
    meta, body = _read_markdown_frontmatter(child_path)
    assert meta["id"] == "TASK-3"
    assert meta["parent"] == "TASK-1"
    assert meta["dependencies"] == ["TASK-2"]
    assert meta["beads"]["id"] == "bd-3"
    assert meta["beads"]["dependencies"] == ["bd-2"]
    assert meta["priority"] == "high"
    assert meta["oompah.attachments"][0]["path"] == ".oompah/attachments/bd-3/mock.png"
    assert "Do the child work" in body
    assert "Progress note" in body
    assert "author: oompah" in body


def test_closed_beads_land_in_completed_folder(tmp_path):
    backlog_dir = _write_backlog_config(tmp_path)
    source = FakeBeadsSource([
        _issue(
            "bd-1",
            "Already closed",
            state="closed",
            closed_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
        )
    ])

    result = migrate_beads_to_backlog(
        MigrationOptions(source=str(tmp_path), backlog_dir="backlog"),
        source_tracker=source,
    )

    assert result.created == 1
    completed = list((backlog_dir / "completed").glob("task-1 - *.md"))
    assert len(completed) == 1
    meta, _body = _read_markdown_frontmatter(completed[0])
    assert meta["status"] == "Done"


def test_existing_migrated_task_is_skipped_by_default(tmp_path):
    backlog_dir = _write_backlog_config(tmp_path)
    path = backlog_dir / "tasks" / "task-9 - Existing.md"
    path.write_text(
        "---\n"
        + yaml.safe_dump({
            "id": "TASK-9",
            "title": "Existing",
            "status": "To Do",
            "beads": {"id": "bd-1"},
        }, sort_keys=False)
        + "---\nExisting body\n",
        encoding="utf-8",
    )
    source = FakeBeadsSource([_issue("bd-1", "Updated title")])

    result = migrate_beads_to_backlog(
        MigrationOptions(source=str(tmp_path), backlog_dir="backlog"),
        source_tracker=source,
    )

    assert result.created == 0
    assert result.skipped == 1
    assert result.mapping["bd-1"] == "TASK-9"
    meta, body = _read_markdown_frontmatter(path)
    assert meta["title"] == "Existing"
    assert body == "Existing body\n"


def test_force_updates_existing_migrated_task(tmp_path):
    backlog_dir = _write_backlog_config(tmp_path)
    path = backlog_dir / "tasks" / "task-9 - Existing.md"
    path.write_text(
        "---\n"
        + yaml.safe_dump({
            "id": "TASK-9",
            "title": "Existing",
            "status": "To Do",
            "beads": {"id": "bd-1"},
        }, sort_keys=False)
        + "---\nExisting body\n",
        encoding="utf-8",
    )
    source = FakeBeadsSource([
        _issue("bd-1", "Updated title", description="New description")
    ])

    result = migrate_beads_to_backlog(
        MigrationOptions(source=str(tmp_path), backlog_dir="backlog", force=True),
        source_tracker=source,
    )

    assert result.updated == 1
    meta, body = _read_markdown_frontmatter(path)
    assert meta["id"] == "TASK-9"
    assert meta["title"] == "Updated title"
    assert meta["beads"]["id"] == "bd-1"
    assert "New description" in body


def test_dry_run_allocates_planned_ids_without_writing(tmp_path):
    source = FakeBeadsSource([_issue("bd-1", "Dry run")])

    result = migrate_beads_to_backlog(
        MigrationOptions(source=str(tmp_path), backlog_dir="backlog", dry_run=True),
        source_tracker=source,
    )

    assert result.dry_run is True
    assert result.records[0].action == "would_create"
    assert result.mapping == {"bd-1": "TASK-1"}
    assert not (tmp_path / "backlog").exists()


def test_init_uses_backlog_cli_when_destination_missing(tmp_path):
    backlog_dir = tmp_path / "backlog"

    with (
        patch("oompah.beads_to_backlog.shutil.which", return_value="/usr/bin/backlog"),
        patch("oompah.beads_to_backlog.subprocess.run") as run,
    ):
        run.return_value.returncode = 0
        run.return_value.stdout = ""
        run.return_value.stderr = ""
        _ensure_backlog_project(
            root=tmp_path,
            backlog_dir=backlog_dir,
            project_name="Migrated",
            should_init=True,
        )

    assert run.call_args.args[0] == [
        "backlog",
        "init",
        "Migrated",
        "--defaults",
        "--backlog-dir",
        "backlog",
        "--config-location",
        "folder",
    ]
    assert (backlog_dir / "tasks").is_dir()
    assert (backlog_dir / "completed").is_dir()
