"""Backlog.md project compatibility checks for oompah."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from oompah.statuses import DEFAULT_STATUS, canonical_statuses_with


_CAMEL_TO_SNAKE = {
    "projectName": "project_name",
    "defaultStatus": "default_status",
    "dateFormat": "date_format",
    "maxColumnWidth": "max_column_width",
    "autoOpenBrowser": "auto_open_browser",
    "defaultPort": "default_port",
    "remoteOperations": "remote_operations",
    "autoCommit": "auto_commit",
    "filesystemOnly": "filesystem_only",
    "bypassGitHooks": "bypass_git_hooks",
    "checkActiveBranches": "check_active_branches",
    "activeBranchDays": "active_branch_days",
    "taskPrefix": "task_prefix",
    "backlogDirectory": "backlog_directory",
}


@dataclass
class BacklogCompatibilityResult:
    project_root: Path
    config_path: Path | None = None
    present: bool = False
    changed: bool = False
    migrations: list[str] = field(default_factory=list)
    error: str | None = None


class BacklogCompatibilityError(Exception):
    """Raised when a repository is not a usable Backlog.md project."""


def ensure_backlog_compatible(project_root: str | Path) -> BacklogCompatibilityResult:
    """Ensure a repository's Backlog.md config contains oompah's statuses.

    Backlog.md's CLI expects snake_case config keys in ``backlog/config.yml``.
    This helper migrates legacy or accidental camelCase keys and status values
    without rewriting task files.
    """
    root = Path(project_root).resolve()
    result = BacklogCompatibilityResult(project_root=root)
    config_path = _find_config_path(root)
    if config_path is None:
        result.error = f"No Backlog.md project found in {root}. Run `backlog init`."
        raise BacklogCompatibilityError(result.error)

    result.present = True
    result.config_path = config_path
    try:
        original_text = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(original_text) or {}
    except OSError as exc:
        result.error = f"Cannot read {config_path}: {exc}"
        raise BacklogCompatibilityError(result.error) from exc
    except yaml.YAMLError as exc:
        result.error = f"Cannot parse {config_path}: {exc}"
        raise BacklogCompatibilityError(result.error) from exc
    if not isinstance(data, dict):
        data = {}

    migrated = _migrate_config_dict(data)
    if migrated != data:
        result.migrations.append("config-key-shape")

    old_statuses = _list_value(data.get("statuses"))
    new_statuses = canonical_statuses_with(_list_value(migrated.get("statuses")))
    if new_statuses != old_statuses:
        result.migrations.append("canonical-statuses")
    migrated["statuses"] = new_statuses

    if migrated.get("default_status") != DEFAULT_STATUS:
        migrated["default_status"] = DEFAULT_STATUS
        result.migrations.append("default-status")

    if "project_name" not in migrated:
        migrated["project_name"] = root.name
        result.migrations.append("project-name")
    if "task_prefix" not in migrated:
        migrated["task_prefix"] = "task"
        result.migrations.append("task-prefix")

    if migrated != data:
        config_path.write_text(
            yaml.safe_dump(migrated, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        result.changed = True

    return result


def _find_config_path(root: Path) -> Path | None:
    root_config = root / "backlog.config.yml"
    if root_config.exists():
        root_data = _read_yaml(root_config)
        directory = root_data.get("backlogDirectory") or root_data.get(
            "backlog_directory"
        )
        if directory:
            config_path = root / str(directory) / "config.yml"
            if config_path.exists():
                return config_path
        return root_config

    for name in ("backlog", ".backlog"):
        config_path = root / name / "config.yml"
        if config_path.exists():
            return config_path
    return None


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _migrate_config_dict(data: dict[str, Any]) -> dict[str, Any]:
    migrated: dict[str, Any] = {}
    for key, value in data.items():
        migrated[_CAMEL_TO_SNAKE.get(str(key), str(key))] = value
    return migrated


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []
