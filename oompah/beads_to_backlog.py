"""Migration utility for moving bd/beads issues into Backlog.md."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from oompah.models import BlockerRef, Issue
from oompah.tracker import (
    BeadsTracker,
    TrackerError,
    _backlog_priority_name,
    _read_markdown_frontmatter,
    _read_yaml_file,
    _write_markdown_frontmatter,
)

logger = logging.getLogger(__name__)


class MigrationError(Exception):
    """Raised when the beads-to-Backlog.md migration cannot proceed."""


@dataclass
class MigrationOptions:
    """Options for a beads-to-Backlog.md migration."""

    source: str = "."
    backlog_dir: str = "backlog"
    project_name: str | None = None
    dry_run: bool = False
    force: bool = False
    init: bool = True
    backlog_active_states: list[str] = field(
        default_factory=lambda: ["To Do", "In Progress"]
    )
    backlog_terminal_states: list[str] = field(default_factory=lambda: ["Done"])


@dataclass
class MigrationRecord:
    """One issue's migration outcome."""

    old_id: str
    new_id: str | None
    title: str
    action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_id": self.old_id,
            "new_id": self.new_id,
            "title": self.title,
            "action": self.action,
        }


@dataclass
class MigrationResult:
    """Summary of a migration run."""

    total: int
    dry_run: bool
    mapping: dict[str, str] = field(default_factory=dict)
    records: list[MigrationRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def created(self) -> int:
        return sum(1 for r in self.records if r.action in {"created", "would_create"})

    @property
    def updated(self) -> int:
        return sum(1 for r in self.records if r.action in {"updated", "would_update"})

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.records if r.action in {"skipped", "would_skip"})

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "dry_run": self.dry_run,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "mapping": self.mapping,
            "warnings": list(self.warnings),
            "records": [record.to_dict() for record in self.records],
        }


@dataclass
class _TaskPlan:
    old_id: str
    new_id: str
    issue: Issue
    path: Path
    action: str


def migrate_beads_to_backlog(
    options: MigrationOptions,
    *,
    source_tracker: BeadsTracker | None = None,
) -> MigrationResult:
    """Migrate all beads issues in ``options.source`` to Backlog.md files.

    The migration intentionally keeps Backlog.md task IDs native to Backlog.md.
    The original bead identifier is stored in YAML front matter under
    ``beads.id`` and dependencies/parent links are remapped to the newly
    allocated Backlog.md task IDs.
    """
    root = Path(options.source).expanduser().resolve()
    backlog_dir = _resolve_backlog_dir(root, options.backlog_dir)

    if not options.dry_run:
        _ensure_backlog_project(
            root=root,
            backlog_dir=backlog_dir,
            project_name=options.project_name or root.name or "Migrated",
            should_init=options.init,
        )

    config = _read_backlog_config_if_present(backlog_dir)
    task_prefix = str(config.get("task_prefix") or "task")
    active_states = options.backlog_active_states or ["To Do", "In Progress"]
    terminal_states = options.backlog_terminal_states or ["Done"]

    source = source_tracker or BeadsTracker(
        active_states=["open", "deferred", "blocked", "in_progress"],
        terminal_states=["closed"],
        cwd=str(root),
    )
    issues = _sort_source_issues(source.fetch_all_issues_enriched())
    result = MigrationResult(total=len(issues), dry_run=options.dry_run)

    existing = _existing_migrated_tasks(backlog_dir) if backlog_dir.exists() else {}
    next_number = _next_task_number(backlog_dir, task_prefix)
    planned: list[_TaskPlan] = []

    for issue in issues:
        old_id = _issue_key(issue)
        existing_task = existing.get(old_id)
        if existing_task:
            new_id, path = existing_task
            result.mapping[old_id] = new_id
            action = "would_update" if options.dry_run and options.force else (
                "updated" if options.force else "skipped"
            )
            if not options.force:
                if options.dry_run:
                    action = "would_skip"
                result.records.append(
                    MigrationRecord(old_id, new_id, issue.title, action)
                )
                continue
            result.records.append(MigrationRecord(old_id, new_id, issue.title, action))
            planned.append(_TaskPlan(old_id, new_id, issue, path, action))
            continue

        new_id = f"{task_prefix.upper()}-{next_number}"
        next_number += 1
        status = _map_status(issue, active_states, terminal_states)
        path = _task_file_path(backlog_dir, new_id, issue.title, status, terminal_states)
        result.mapping[old_id] = new_id
        action = "would_create" if options.dry_run else "created"
        result.records.append(MigrationRecord(old_id, new_id, issue.title, action))
        planned.append(_TaskPlan(old_id, new_id, issue, path, action))

    if options.dry_run:
        _collect_relation_warnings(planned, result)
        return result

    for plan in planned:
        comments = _safe_fetch_comments(source, plan.old_id, result)
        attachments = _safe_fetch_attachments(source, plan.old_id, result)
        dependencies, original_dependencies = _mapped_dependencies(plan.issue, result)
        parent = _mapped_parent(plan.issue, result)
        if plan.issue.parent_id and parent is None:
            result.warnings.append(
                f"{plan.old_id}: parent {plan.issue.parent_id} was not migrated"
            )
        for blocker in original_dependencies:
            if blocker not in result.mapping:
                result.warnings.append(
                    f"{plan.old_id}: dependency {blocker} was not migrated"
                )
        _write_migrated_task(
            path=plan.path,
            issue=plan.issue,
            new_id=plan.new_id,
            status=_map_status(plan.issue, active_states, terminal_states),
            dependencies=dependencies,
            original_dependencies=original_dependencies,
            parent=parent,
            comments=comments,
            attachments=attachments,
        )

    _merge_config_labels(backlog_dir, issues)
    return result


def _resolve_backlog_dir(root: Path, backlog_dir: str) -> Path:
    path = Path(backlog_dir).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _ensure_backlog_project(
    *,
    root: Path,
    backlog_dir: Path,
    project_name: str,
    should_init: bool,
) -> None:
    if (backlog_dir / "config.yml").exists():
        (backlog_dir / "tasks").mkdir(parents=True, exist_ok=True)
        (backlog_dir / "completed").mkdir(parents=True, exist_ok=True)
        return
    if not should_init:
        raise MigrationError(
            f"Backlog.md project not found at {backlog_dir}; run backlog init first"
        )
    if shutil.which("backlog") is None:
        raise MigrationError("backlog command not found; install Backlog.md first")

    backlog_arg = os.path.relpath(backlog_dir, root)
    cmd = [
        "backlog",
        "init",
        project_name,
        "--defaults",
        "--backlog-dir",
        backlog_arg,
        "--config-location",
        "folder",
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise MigrationError("backlog init timed out") from exc
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise MigrationError(f"backlog init failed: {stderr}")
    (backlog_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (backlog_dir / "completed").mkdir(parents=True, exist_ok=True)


def _read_backlog_config_if_present(backlog_dir: Path) -> dict[str, Any]:
    config_path = backlog_dir / "config.yml"
    if not config_path.exists():
        return {}
    return _read_yaml_file(config_path)


def _existing_migrated_tasks(backlog_dir: Path) -> dict[str, tuple[str, Path]]:
    existing: dict[str, tuple[str, Path]] = {}
    for path in _task_files(backlog_dir):
        try:
            meta, _body = _read_markdown_frontmatter(path)
        except TrackerError:
            continue
        old_id = _beads_id_from_meta(meta)
        new_id = str(meta.get("id") or "").strip()
        if old_id and new_id:
            existing[old_id] = (new_id, path)
    return existing


def _beads_id_from_meta(meta: dict[str, Any]) -> str | None:
    beads = meta.get("beads")
    if isinstance(beads, dict) and beads.get("id"):
        return str(beads["id"])
    dotted = meta.get("beads.id")
    return str(dotted) if dotted else None


def _next_task_number(backlog_dir: Path, task_prefix: str) -> int:
    highest = 0
    pattern = re.compile(rf"^{re.escape(task_prefix)}-(\d+)(?:\b|$)", re.I)
    for path in _task_files(backlog_dir):
        task_id = ""
        try:
            meta, _body = _read_markdown_frontmatter(path)
            task_id = str(meta.get("id") or "")
        except TrackerError:
            task_id = path.stem
        match = pattern.match(task_id) or pattern.match(path.stem)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _task_files(backlog_dir: Path) -> list[Path]:
    files: list[Path] = []
    for name in ("tasks", "completed"):
        directory = backlog_dir / name
        if directory.is_dir():
            files.extend(directory.glob("*.md"))
    return sorted(files)


def _task_file_path(
    backlog_dir: Path,
    task_id: str,
    title: str,
    status: str,
    terminal_states: list[str],
) -> Path:
    terminal = {state.strip().lower() for state in terminal_states}
    folder = "completed" if status.strip().lower() in terminal else "tasks"
    prefix, number = task_id.split("-", 1)
    slug = _slug_title(title)
    return backlog_dir / folder / f"{prefix.lower()}-{number} - {slug}.md"


def _write_migrated_task(
    *,
    path: Path,
    issue: Issue,
    new_id: str,
    status: str,
    dependencies: list[str],
    original_dependencies: list[str],
    parent: str | None,
    comments: list[dict[str, Any]],
    attachments: list[dict[str, Any]],
) -> None:
    existing_meta: dict[str, Any] = {}
    if path.exists():
        try:
            existing_meta, _existing_body = _read_markdown_frontmatter(path)
        except TrackerError:
            existing_meta = {}

    meta: dict[str, Any] = {
        "id": new_id,
        "title": issue.title,
        "status": status,
        "assignee": existing_meta.get("assignee", []),
        "created_date": _backlog_date(issue.created_at)
        or existing_meta.get("created_date")
        or _backlog_date(datetime.now(timezone.utc)),
        "updated_date": _backlog_date(issue.updated_at)
        or existing_meta.get("updated_date")
        or _backlog_date(datetime.now(timezone.utc)),
        "labels": _migration_labels(issue),
        "dependencies": dependencies,
        "priority": _backlog_priority_name(issue.priority) or "medium",
        "ordinal": existing_meta.get("ordinal", 1000),
        "type": issue.issue_type or "task",
        "beads": {
            "id": _issue_key(issue),
            "state": issue.state,
            "parent_id": issue.parent_id,
            "dependencies": original_dependencies,
            "branch_name": issue.branch_name,
            "target_branch": issue.target_branch,
            "url": issue.url,
            "created_at": _iso(issue.created_at),
            "updated_at": _iso(issue.updated_at),
            "closed_at": _iso(issue.closed_at),
        },
    }
    if parent:
        meta["parent"] = parent
    if attachments:
        meta["oompah.attachments"] = attachments

    body = _backlog_body(issue.description or "", comments)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_markdown_frontmatter(path, meta, body)


def _backlog_body(description: str, comments: list[dict[str, Any]]) -> str:
    return (
        "## Description\n\n"
        "<!-- SECTION:DESCRIPTION:BEGIN -->\n"
        f"{description.strip()}\n"
        "<!-- SECTION:DESCRIPTION:END -->\n\n"
        "## Comments\n"
        "<!-- COMMENTS:BEGIN -->\n"
        f"{''.join(_format_comment(index, comment) for index, comment in enumerate(comments, 1))}"
        "<!-- COMMENTS:END -->\n"
    )


def _format_comment(index: int, comment: dict[str, Any]) -> str:
    author = (
        comment.get("author")
        or comment.get("created_by")
        or comment.get("user")
        or "unknown"
    )
    created = (
        comment.get("created_at")
        or comment.get("created")
        or comment.get("timestamp")
        or ""
    )
    text = (
        comment.get("text")
        or comment.get("body")
        or comment.get("comment")
        or comment.get("content")
        or ""
    )
    comment_id = comment.get("id") or index
    return (
        "<!-- COMMENT:BEGIN -->\n"
        f"index: {comment_id}\n"
        f"author: {author}\n"
        f"created: {_comment_timestamp(created)}\n\n"
        f"{str(text).strip()}\n"
        "<!-- COMMENT:END -->\n"
    )


def _comment_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return _iso(value) or ""
    return str(value)


def _safe_fetch_comments(
    source: BeadsTracker,
    old_id: str,
    result: MigrationResult,
) -> list[dict[str, Any]]:
    try:
        comments = source.fetch_comments(old_id)
    except Exception as exc:  # best-effort historical data
        result.warnings.append(f"{old_id}: failed to fetch comments: {exc}")
        return []
    return [c for c in comments if isinstance(c, dict)]


def _safe_fetch_attachments(
    source: BeadsTracker,
    old_id: str,
    result: MigrationResult,
) -> list[dict[str, Any]]:
    try:
        attachments = source.fetch_attachments(old_id)
    except Exception as exc:  # best-effort historical data
        result.warnings.append(f"{old_id}: failed to fetch attachments: {exc}")
        return []
    return [a for a in attachments if isinstance(a, dict)]


def _mapped_dependencies(
    issue: Issue,
    result: MigrationResult,
) -> tuple[list[str], list[str]]:
    original: list[str] = []
    mapped: list[str] = []
    for blocker in issue.blocked_by:
        blocker_id = _blocker_key(blocker)
        if not blocker_id:
            continue
        original.append(blocker_id)
        if blocker_id in result.mapping:
            mapped.append(result.mapping[blocker_id])
    return mapped, original


def _mapped_parent(issue: Issue, result: MigrationResult) -> str | None:
    if not issue.parent_id:
        return None
    return result.mapping.get(str(issue.parent_id))


def _collect_relation_warnings(
    planned: list[_TaskPlan],
    result: MigrationResult,
) -> None:
    for plan in planned:
        if plan.issue.parent_id and str(plan.issue.parent_id) not in result.mapping:
            result.warnings.append(
                f"{plan.old_id}: parent {plan.issue.parent_id} was not migrated"
            )
        for blocker in plan.issue.blocked_by:
            blocker_id = _blocker_key(blocker)
            if blocker_id and blocker_id not in result.mapping:
                result.warnings.append(
                    f"{plan.old_id}: dependency {blocker_id} was not migrated"
                )


def _merge_config_labels(backlog_dir: Path, issues: list[Issue]) -> None:
    config_path = backlog_dir / "config.yml"
    if not config_path.exists():
        return
    try:
        config = _read_yaml_file(config_path)
    except TrackerError:
        return
    labels = config.get("labels")
    existing = [str(label) for label in labels] if isinstance(labels, list) else []
    merged = list(dict.fromkeys(existing + [
        label for issue in issues for label in _migration_labels(issue)
    ]))
    config["labels"] = merged
    try:
        config_path.write_text(
            yaml.safe_dump(config, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Failed to update Backlog.md labels in %s: %s", config_path, exc)


def _migration_labels(issue: Issue) -> list[str]:
    labels = [str(label).strip().lower() for label in issue.labels if str(label).strip()]
    issue_type = (issue.issue_type or "task").strip().lower()
    if issue_type and issue_type != "task":
        labels.append(issue_type)
    labels.append("beads-migrated")
    return list(dict.fromkeys(labels))


def _map_status(
    issue: Issue,
    active_states: list[str],
    terminal_states: list[str],
) -> str:
    terminal = terminal_states[0] if terminal_states else "Done"
    active = active_states[0] if active_states else "To Do"
    in_progress = active_states[1] if len(active_states) > 1 else active
    normalized = (issue.state or "").strip().lower().replace("-", "_").replace(" ", "_")
    if issue.closed_at is not None or normalized in {
        "closed",
        "done",
        "resolved",
        "merged",
    }:
        return terminal
    if normalized in {"in_progress", "doing", "started"}:
        return in_progress
    return active


def _sort_source_issues(issues: list[Issue]) -> list[Issue]:
    def key(issue: Issue) -> tuple[str, str]:
        created = _iso(issue.created_at) or ""
        return (created, _issue_key(issue))

    return sorted(issues, key=key)


def _issue_key(issue: Issue) -> str:
    return str(issue.identifier or issue.id)


def _blocker_key(blocker: BlockerRef) -> str | None:
    value = blocker.identifier or blocker.id
    return str(value) if value else None


def _slug_title(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title.strip()).strip("-")
    return slug[:80] or "task"


def _backlog_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.strftime("%Y-%m-%d %H:%M")


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oompah-migrate-beads-to-backlog",
        description="Migrate a project's bd/beads issues into Backlog.md task files.",
    )
    parser.add_argument(
        "--source",
        default=".",
        help="Project directory containing the beads database (default: current directory).",
    )
    parser.add_argument(
        "--backlog-dir",
        default="backlog",
        help="Backlog.md directory to create/use relative to --source (default: backlog).",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Backlog.md project name when initializing a new Backlog.md directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan the migration without writing Backlog.md files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Update existing migrated Backlog.md tasks instead of skipping them.",
    )
    parser.add_argument(
        "--no-init",
        action="store_true",
        help="Do not run backlog init when the Backlog.md directory is missing.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the migration result as JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    options = MigrationOptions(
        source=args.source,
        backlog_dir=args.backlog_dir,
        project_name=args.project_name,
        dry_run=args.dry_run,
        force=args.force,
        init=not args.no_init,
    )
    try:
        result = migrate_beads_to_backlog(options)
    except (MigrationError, TrackerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        verb = "Planned" if result.dry_run else "Migrated"
        print(
            f"{verb} {result.total} issue(s): "
            f"{result.created} created, {result.updated} updated, {result.skipped} skipped"
        )
        for warning in result.warnings:
            print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
