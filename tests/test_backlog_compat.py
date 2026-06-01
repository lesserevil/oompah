"""Tests for Backlog.md project compatibility migration."""

import yaml
import pytest

from oompah.backlog_compat import (
    BacklogCompatibilityError,
    ensure_backlog_compatible,
)
from oompah.statuses import CANONICAL_STATUSES


def test_ensure_backlog_compatible_migrates_snake_case_config(tmp_path):
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
    assert data["projectName"] == "Legacy"
    assert data["taskPrefix"] == "TASK"
    assert data["defaultStatus"] == "Backlog"
    for status in CANONICAL_STATUSES:
        assert status in data["statuses"]
    assert "To Do" not in data["statuses"]


def test_ensure_backlog_compatible_is_idempotent_for_current_config(tmp_path):
    backlog_dir = tmp_path / "backlog"
    backlog_dir.mkdir()
    config_path = backlog_dir / "config.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "projectName": "Current",
                "taskPrefix": "TASK",
                "defaultStatus": "Backlog",
                "statuses": list(CANONICAL_STATUSES),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = ensure_backlog_compatible(tmp_path)

    assert result.changed is False
    assert result.migrations == []


def test_ensure_backlog_compatible_requires_backlog_config(tmp_path):
    with pytest.raises(BacklogCompatibilityError, match="No Backlog.md project"):
        ensure_backlog_compatible(tmp_path)
