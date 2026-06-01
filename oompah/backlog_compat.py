"""Backlog.md project compatibility checks for oompah."""

from __future__ import annotations

import subprocess
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


class _BacklogConfigDumper(yaml.SafeDumper):
    """YAML dumper for Backlog.md config files."""


class _FlowStyleList(list):
    """Marker list that should be emitted in YAML flow style."""


def _represent_flow_style_list(
    dumper: yaml.SafeDumper,
    data: _FlowStyleList,
) -> yaml.SequenceNode:
    return dumper.represent_sequence(
        "tag:yaml.org,2002:seq",
        data,
        flow_style=True,
    )


_BacklogConfigDumper.add_representer(_FlowStyleList, _represent_flow_style_list)


@dataclass
class BacklogCompatibilityResult:
    project_root: Path
    config_path: Path | None = None
    present: bool = False
    changed: bool = False
    migrations: list[str] = field(default_factory=list)
    task_statuses_migrated: int = 0
    error: str | None = None


class BacklogCompatibilityError(Exception):
    """Raised when a repository is not a usable Backlog.md project."""


def ensure_backlog_compatible(project_root: str | Path) -> BacklogCompatibilityResult:
    """Ensure a repository's Backlog.md config contains oompah's statuses.

    Backlog.md's CLI expects snake_case config keys in ``backlog/config.yml``.
    This helper migrates legacy or accidental camelCase keys and status values,
    then rewrites active task files whose status is not compatible with the
    configured status list back to the default Backlog status.
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

    serialized = _dump_backlog_config(migrated)
    if migrated != data or serialized != original_text:
        if migrated == data:
            result.migrations.append("config-format")
        config_path.write_text(serialized, encoding="utf-8")
        result.changed = True

    changed_tasks = _migrate_active_task_statuses(
        root,
        config_path,
        migrated,
    )
    if changed_tasks:
        result.task_statuses_migrated = changed_tasks
        result.migrations.append("task-statuses")
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


def _dump_backlog_config(config: dict[str, Any]) -> str:
    """Dump Backlog.md config in the shape its CLI validates.

    Backlog.md 1.45.2 writes snake_case keys, but its status validator only
    recognizes the ``statuses`` list when it is emitted as an inline YAML array.
    Keep all config lists in flow style so future list-valued options get the
    same parser-friendly treatment.
    """
    return yaml.dump(
        _with_flow_style_lists(config),
        Dumper=_BacklogConfigDumper,
        sort_keys=False,
        allow_unicode=False,
        width=1000,
    )


def _with_flow_style_lists(value: Any) -> Any:
    if isinstance(value, list):
        return _FlowStyleList(_with_flow_style_lists(item) for item in value)
    if isinstance(value, dict):
        return {
            key: _with_flow_style_lists(item)
            for key, item in value.items()
        }
    return value


def _migrate_active_task_statuses(
    root: Path,
    config_path: Path,
    config: dict[str, Any],
) -> int:
    statuses = _list_value(config.get("statuses"))
    configured_by_key = {
        _status_match_key(status): status
        for status in statuses
        if status
    }
    default_status = str(config.get("default_status") or DEFAULT_STATUS)
    backlog_status = configured_by_key.get(
        _status_match_key(DEFAULT_STATUS),
        default_status,
    )
    tasks_dir = _backlog_dir_for_config(root, config_path, config) / "tasks"
    if not tasks_dir.is_dir():
        return 0

    changed = 0
    for path in sorted(tasks_dir.glob("*.md")):
        try:
            meta, body = _read_markdown_frontmatter(path)
        except BacklogCompatibilityError:
            continue
        raw_status = str(meta.get("status") or "").strip()
        configured_status = configured_by_key.get(_status_match_key(raw_status))
        if configured_status:
            if raw_status != configured_status:
                _update_task_status(root, path, meta, body, configured_status)
                changed += 1
            continue
        _update_task_status(root, path, meta, body, backlog_status)
        changed += 1
    return changed


def _backlog_dir_for_config(
    root: Path,
    config_path: Path,
    config: dict[str, Any],
) -> Path:
    if config_path.name == "config.yml":
        return config_path.parent
    directory = config.get("backlog_directory") or config.get("backlogDirectory")
    if directory:
        path = Path(str(directory))
        return path if path.is_absolute() else root / path
    return root / "backlog"


def _read_markdown_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BacklogCompatibilityError(f"Cannot read {path}: {exc}") from exc
    if not text.startswith("---"):
        raise BacklogCompatibilityError(f"Task file lacks frontmatter: {path}")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise BacklogCompatibilityError(f"Task file has unterminated frontmatter: {path}")
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise BacklogCompatibilityError(f"Cannot parse task frontmatter {path}: {exc}") from exc
    if not isinstance(meta, dict):
        raise BacklogCompatibilityError(f"Task frontmatter is not a mapping: {path}")
    return meta, parts[2].lstrip("\n")


def _write_markdown_frontmatter(
    path: Path,
    meta: dict[str, Any],
    body: str,
) -> None:
    path.write_text(
        "---\n"
        + yaml.safe_dump(meta, sort_keys=False, allow_unicode=False)
        + "---\n"
        + body,
        encoding="utf-8",
    )


def _update_task_status(
    root: Path,
    path: Path,
    meta: dict[str, Any],
    body: str,
    status: str,
) -> None:
    task_id = str(meta.get("id") or "").strip()
    if task_id and _edit_task_status_with_cli(root, task_id, status):
        return
    meta["status"] = status
    _write_markdown_frontmatter(path, meta, body)


def _edit_task_status_with_cli(root: Path, task_id: str, status: str) -> bool:
    try:
        completed = subprocess.run(
            [
                "backlog",
                "task",
                "edit",
                task_id,
                "--status",
                status,
                "--plain",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def _status_match_key(status: str | None) -> str:
    return str(status or "").strip().lower().replace("-", " ").replace("_", " ")
