"""Tests for Backlog.md project compatibility migration."""

import subprocess
from unittest.mock import patch

import yaml
import pytest

from oompah.backlog_compat import (
    BacklogCompatibilityError,
    ensure_backlog_compatible,
)
from oompah.statuses import CANONICAL_STATUSES


def _write_task(backlog_dir, task_id, status, *, folder="tasks"):
    task_dir = backlog_dir / folder
    task_dir.mkdir(parents=True, exist_ok=True)
    path = task_dir / f"task-{task_id} - Sample.md"
    path.write_text(
        "\n".join([
            "---",
            f"id: TASK-{task_id}",
            "title: Sample",
            f"status: {status}",
            "---",
            "## Description",
            "",
            "Body stays intact.",
            "",
        ]),
        encoding="utf-8",
    )
    return path


def test_ensure_backlog_compatible_migrates_legacy_statuses(tmp_path):
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir()
    config_path = backlog_dir / "config.yml"
    config_path.write_text(
        "\n".join([
            "project_name: Legacy",
            "default_status: To Do",
            "task_prefix: TASK",
            "statuses:",
            "  - To Do",
            "  - In Progress",
            "  - Done",
            "",
        ]),
        encoding="utf-8",
    )

    result = ensure_backlog_compatible(tmp_path)

    assert result.changed is True
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["project_name"] == "Legacy"
    assert data["task_prefix"] == "TASK"
    assert data["default_status"] == "Backlog"
    for status in CANONICAL_STATUSES:
        assert status in data["statuses"]
    assert "To Do" not in data["statuses"]
    assert "statuses: [Proposed, Backlog, Open," in config_path.read_text(
        encoding="utf-8"
    )


def test_ensure_backlog_compatible_rewrites_statuses_as_inline_array(tmp_path):
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir()
    config_path = backlog_dir / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "project_name": "Current",
                "task_prefix": "TASK",
                "default_status": "Backlog",
                "statuses": list(CANONICAL_STATUSES),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = ensure_backlog_compatible(tmp_path)

    assert result.changed is True
    assert "config-format" in result.migrations
    text = config_path.read_text(encoding="utf-8")
    assert "statuses: [Proposed, Backlog, Open," in text
    assert "\n- Backlog\n" not in text


def test_ensure_backlog_compatible_moves_invalid_active_task_statuses_to_backlog(tmp_path):
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir()
    config_path = backlog_dir / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "project_name": "Tasks",
                "task_prefix": "TASK",
                "default_status": "Backlog",
                "statuses": list(CANONICAL_STATUSES),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    legacy = _write_task(backlog_dir, "1", "To Do")
    unknown = _write_task(backlog_dir, "2", "Blocked")
    valid = _write_task(backlog_dir, "3", "Open")
    lower_case = _write_task(backlog_dir, "4", "open")
    completed = _write_task(backlog_dir, "5", "To Do", folder="completed")

    with patch(
        "oompah.backlog_compat.subprocess.run",
        return_value=subprocess.CompletedProcess([], 1, "", "failed"),
    ) as run:
        result = ensure_backlog_compatible(tmp_path)

    assert result.changed is True
    assert result.task_statuses_migrated == 3
    assert "task-statuses" in result.migrations
    assert run.call_count == 3
    assert yaml.safe_load(legacy.read_text(encoding="utf-8").split("---", 2)[1])[
        "status"
    ] == "Backlog"
    assert yaml.safe_load(unknown.read_text(encoding="utf-8").split("---", 2)[1])[
        "status"
    ] == "Backlog"
    assert yaml.safe_load(valid.read_text(encoding="utf-8").split("---", 2)[1])[
        "status"
    ] == "Open"
    assert yaml.safe_load(lower_case.read_text(encoding="utf-8").split("---", 2)[1])[
        "status"
    ] == "Open"
    assert yaml.safe_load(completed.read_text(encoding="utf-8").split("---", 2)[1])[
        "status"
    ] == "To Do"
    assert "Body stays intact." in legacy.read_text(encoding="utf-8")


def test_ensure_backlog_compatible_uses_backlog_cli_for_task_status_migration(tmp_path):
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir()
    (backlog_dir / "config.yml").write_text(
        yaml.safe_dump(
            {
                "project_name": "Tasks",
                "task_prefix": "TASK",
                "default_status": "Backlog",
                "statuses": list(CANONICAL_STATUSES),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _write_task(backlog_dir, "1", "To Do")

    with patch(
        "oompah.backlog_compat.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, "ok", ""),
    ) as run:
        result = ensure_backlog_compatible(tmp_path)

    assert result.changed is True
    assert result.task_statuses_migrated == 1
    run.assert_called_once_with(
        [
            "backlog",
            "task",
            "edit",
            "TASK-1",
            "--status",
            "Backlog",
            "--plain",
        ],
        cwd=str(tmp_path.resolve()),
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_ensure_backlog_compatible_migrates_camel_case_config_keys(tmp_path):
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir()
    config_path = backlog_dir / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "projectName": "Camel",
                "taskPrefix": "TASK",
                "defaultStatus": "To Do",
                "dateFormat": "yyyy-mm-dd",
                "statuses": ["To Do", "In Progress", "Done"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = ensure_backlog_compatible(tmp_path)

    assert result.changed is True
    assert "config-key-shape" in result.migrations
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["project_name"] == "Camel"
    assert data["task_prefix"] == "TASK"
    assert data["default_status"] == "Backlog"
    assert data["date_format"] == "yyyy-mm-dd"
    assert "projectName" not in data
    assert "defaultStatus" not in data


def test_ensure_backlog_compatible_is_idempotent_for_current_config(tmp_path):
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir()
    config_path = backlog_dir / "config.yml"
    config_path.write_text(
        "\n".join([
            "project_name: Current",
            "task_prefix: TASK",
            "default_status: Backlog",
            f"statuses: [{', '.join(CANONICAL_STATUSES)}]",
            "",
        ]),
        encoding="utf-8",
    )

    result = ensure_backlog_compatible(tmp_path)

    assert result.changed is False
    assert result.migrations == []


def test_ensure_backlog_compatible_requires_backlog_config(tmp_path):
    with pytest.raises(BacklogCompatibilityError, match="No Backlog.md project"):
        ensure_backlog_compatible(tmp_path)
