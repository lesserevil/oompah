"""Native oompah Markdown task tracker.

Stores canonical task state under ``.oompah/tasks`` in the managed repository.
The running oompah service is the intended writer; humans can inspect the files
directly on the project's default branch.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from oompah.models import BlockerRef, Issue
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DONE,
    IN_PROGRESS,
    MERGED,
    OPEN,
    PROPOSED,
    canonicalize_status,
    status_key,
)
from oompah.tracker import (
    TrackerError,
    _append_backlog_comment,
    _backlog_comment_field,
    _backlog_priority_int,
    _format_backlog_comment_timestamp,
    _parse_backlog_comments,
    _parse_timestamp,
    _sanitize_identifier,
    _sort_issues_for_dispatch,
    _string_list,
)

logger = logging.getLogger(__name__)

TRACKER_KIND = "oompah_md"
TASKS_DIR = ".oompah/tasks"
DEFAULT_TASK_PREFIX = "TASK"
_YAML_SAFE_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

_STATUS_DIRS: dict[str, str] = {
    "proposed": "proposed",
    "backlog": "backlog",
    "open": "open",
    "in progress": "in-progress",
    "needs answer": "needs-answer",
    "needs human": "needs-human",
    "needs ci fix": "needs-ci-fix",
    "needs rebase": "needs-rebase",
    "in review": "in-review",
    "decomposed": "decomposed",
    "duplicate candidate": "duplicate-candidate",
    "done": "done",
    "merged": "merged",
    "archived": "archived",
}
_ISSUE_TYPES = frozenset({"bug", "feature", "task", "epic", "chore"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _status_dir(status: str) -> str:
    key = status_key(canonicalize_status(status))
    return _STATUS_DIRS.get(key, key.replace(" ", "-") or "backlog")


def _safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    return cleaned.strip(".-_") or "task"


def _section(body: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)"
    )
    match = pattern.search(body or "")
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _replace_section(body: str, heading: str, text: str | None) -> str:
    new_text = (text or "").strip()
    section_text = f"## {heading}\n\n{new_text}\n"
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n?.*?(?=^##\s+|\Z)"
    )
    if pattern.search(body or ""):
        return pattern.sub(section_text, body).rstrip() + "\n"
    prefix = (body or "").rstrip()
    if prefix:
        return f"{prefix}\n\n{section_text}"
    return section_text


def _read_markdown(path: Path) -> tuple[dict[str, Any], str]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TrackerError(f"Cannot read native task {path}: {exc}") from exc
    if not content.startswith("---\n"):
        raise TrackerError(f"Missing YAML front matter in native task {path}")
    end = content.find("\n---", 4)
    if end < 0:
        raise TrackerError(f"Unterminated YAML front matter in native task {path}")
    frontmatter = content[4:end]
    body_start = end + len("\n---")
    if content[body_start : body_start + 1] == "\n":
        body_start += 1
    try:
        meta = yaml.load(frontmatter, Loader=_YAML_SAFE_LOADER) or {}
    except yaml.YAMLError as exc:
        raise TrackerError(f"Cannot parse native task metadata {path}: {exc}") from exc
    if not isinstance(meta, dict):
        meta = {}
    return meta, content[body_start:]


def _write_markdown(path: Path, meta: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(dict(meta), sort_keys=False, allow_unicode=False)
    try:
        path.write_text(f"---\n{payload}---\n{body}", encoding="utf-8")
    except OSError as exc:
        raise TrackerError(f"Cannot write native task {path}: {exc}") from exc


class OompahMarkdownTracker:
    """Tracker adapter backed by native Markdown files under ``.oompah/tasks``."""

    def __init__(
        self,
        *,
        active_states: list[str],
        terminal_states: list[str],
        cwd: str | None = None,
        default_branch: str | None = None,
        git_sync: bool = True,
    ) -> None:
        self.active_states = [canonicalize_status(s) for s in active_states]
        self.terminal_states = [canonicalize_status(s) for s in terminal_states]
        self.cwd = cwd
        self._root = Path(cwd or os.getcwd()).resolve()
        self.default_branch = (default_branch or "").strip() or None
        self.git_sync = bool(git_sync)
        self._write_lock = threading.RLock()
        self._read_cache: list[dict[str, Any]] | None = None
        self._read_cache_guard = threading.Lock()

    @property
    def root_path(self) -> Path:
        return self._root

    @property
    def tasks_root(self) -> Path:
        return self._root / TASKS_DIR

    def fetch_candidate_issues(self) -> list[Issue]:
        active = {
            status_key(state)
            for state in self.active_states
            if canonicalize_status(state) != PROPOSED
        }
        issues = [
            issue
            for issue in self.fetch_all_issues()
            if status_key(issue.state) in active and issue.state != PROPOSED
        ]
        return _sort_issues_for_dispatch(issues)

    def fetch_in_progress_issues(self) -> list[Issue]:
        """Fetch tasks currently in In Progress state for orphan cleanup."""
        return self.fetch_issues_by_states([IN_PROGRESS])

    def fetch_all_issues(self) -> list[Issue]:
        return [self._normalize_record(rec) for rec in self._read_records()]

    def fetch_all_issues_enriched(self) -> list[Issue]:
        return self.fetch_all_issues()

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        rec = self._read_record(identifier)
        return self._normalize_record(rec) if rec else None

    def fetch_children(self, epic_id: str) -> list[Issue]:
        needle = self._lookup_id(epic_id)
        children = []
        for issue in self.fetch_all_issues():
            if issue.parent_id and self._lookup_id(issue.parent_id) == needle:
                children.append(issue)
        return _sort_issues_for_dispatch(children)

    def fetch_comments(self, identifier: str) -> list[dict]:
        rec = self._read_record(identifier)
        if not rec:
            return []
        return _parse_backlog_comments(str(rec["body"]))

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        wanted = {status_key(canonicalize_status(s)) for s in state_names}
        return [
            issue
            for issue in self.fetch_all_issues()
            if status_key(issue.state) in wanted
        ]

    def fetch_issues_by_labels(
        self,
        labels: list[str],
        *,
        states: list[str] | None = None,
    ) -> list[Issue]:
        wanted_labels = {label.strip().lower() for label in labels if label.strip()}
        wanted_states = (
            {status_key(canonicalize_status(state)) for state in states}
            if states is not None
            else None
        )
        matched = []
        for issue in self.fetch_all_issues():
            present = {label.strip().lower() for label in (issue.labels or [])}
            if wanted_labels and not wanted_labels.issubset(present):
                continue
            if wanted_states is not None and status_key(issue.state) not in wanted_states:
                continue
            matched.append(issue)
        return _sort_issues_for_dispatch(matched)

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        issues = []
        for issue_id in issue_ids:
            issue = self.fetch_issue_detail(issue_id)
            if issue:
                issues.append(issue)
        return issues

    def fetch_memories(self) -> dict[str, str]:
        return {}

    def create_issue(
        self,
        title: str,
        issue_type: str = "task",
        description: str | None = None,
        priority: int | None = None,
        initial_status: str | None = None,
        labels: list[str] | None = None,
        parent: str | None = None,
    ) -> Issue:
        clean_title = str(title or "").strip()
        if not clean_title:
            raise TrackerError("Native oompah task title is required")
        status = canonicalize_status(initial_status or BACKLOG)
        with self._write_lock:
            self._prepare_default_branch_for_write()
            identifier = self._next_identifier()
            now = _now_iso()
            issue_type = (issue_type or "task").strip().lower()
            if issue_type not in _ISSUE_TYPES:
                issue_type = "task"
            effective_labels = _dedupe_strings(labels or [])
            meta: dict[str, Any] = {
                "id": identifier,
                "type": issue_type,
                "status": status,
                "priority": priority,
                "title": clean_title,
                "parent": parent or None,
                "children": [],
                "blocked_by": [],
                "labels": effective_labels,
                "assignee": None,
                "created_at": now,
                "updated_at": now,
                "work_branch": None,
                "target_branch": None,
                "review_url": None,
                "review_number": None,
                "merged_at": None,
            }
            body = self._initial_body(description)
            path = self._path_for(identifier, status)
            _write_markdown(path, meta, body)
            if parent:
                self._add_child_to_parent(parent, identifier)
            self.invalidate_read_cache()
            self._commit_and_push(f"Create oompah task {identifier}")
        created = self.fetch_issue_detail(identifier)
        if not created:
            raise TrackerError(f"Created native oompah task disappeared: {identifier}")
        return created

    def update_issue(self, identifier: str, **fields: str) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(identifier)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {identifier}")
            path = Path(rec["path"])
            meta: dict[str, Any] = dict(rec["meta"])
            body = str(rec["body"])
            old_status = canonicalize_status(str(meta.get("status") or BACKLOG))
            for key, value in fields.items():
                body = self._apply_field(meta, body, key, value)
            meta["updated_at"] = _now_iso()
            new_status = canonicalize_status(str(meta.get("status") or old_status))
            new_path = self._path_for(str(meta["id"]), new_status)
            _write_markdown(new_path, meta, body)
            if new_path != path and path.exists():
                try:
                    path.unlink()
                except OSError as exc:
                    raise TrackerError(f"Cannot remove moved native task {path}: {exc}") from exc
            self.invalidate_read_cache()
            self._commit_and_push(f"Update oompah task {meta['id']}")

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        status = self._terminal_status()
        fields: dict[str, str] = {"status": status}
        self.update_issue(identifier, **fields)
        if reason:
            self.add_comment(identifier, reason)

    def reopen_issue(self, identifier: str) -> None:
        self.update_issue(identifier, status=self._active_status())

    def archive_issue(self, identifier: str) -> None:
        self.update_issue(identifier, status=ARCHIVED)

    def mark_needs_human(
        self,
        identifier: str,
        comment: str,
        author: str = "oompah",
    ) -> None:
        self.update_issue(identifier, status="Needs Human")
        self.add_comment(identifier, comment, author=author)

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        comment_text = str(text or "").strip()
        if not comment_text:
            raise TrackerError("Comment text is required")
        comment_author = _backlog_comment_field(author, fallback="oompah")
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(identifier)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {identifier}")
            meta = dict(rec["meta"])
            body = _append_backlog_comment(
                str(rec["body"]),
                text=comment_text,
                author=comment_author,
                created=_format_backlog_comment_timestamp(),
            )
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, body)
            self.invalidate_read_cache()
            self._commit_and_push(f"Comment on oompah task {meta['id']}")
        return {"author": comment_author, "text": comment_text}

    def add_label(self, identifier: str, label: str) -> None:
        self.update_issue(identifier, **{"add-label": label})

    def remove_label(self, identifier: str, label: str) -> None:
        self.update_issue(identifier, **{"remove-label": label})

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            child = self._read_record_uncached(child_id)
            if not child:
                raise TrackerError(f"Native oompah task not found: {child_id}")
            child_meta = dict(child["meta"])
            child_meta["parent"] = parent_id
            child_meta["updated_at"] = _now_iso()
            _write_markdown(Path(child["path"]), child_meta, str(child["body"]))
            self._add_child_to_parent(parent_id, str(child_meta["id"]))
            self.invalidate_read_cache()
            self._commit_and_push(f"Link oompah task {child_meta['id']} to parent")

    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(blocked_id)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {blocked_id}")
            meta = dict(rec["meta"])
            deps = _dedupe_strings(_string_list(meta.get("blocked_by")) + [blocker_id])
            meta["blocked_by"] = deps
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, str(rec["body"]))
            self.invalidate_read_cache()
            self._commit_and_push(f"Add dependency to oompah task {meta['id']}")

    def fetch_attachments(self, identifier: str) -> list[dict]:
        rec = self._read_record(identifier)
        if not rec:
            return []
        entries = rec["meta"].get("oompah.attachments") or []
        return [entry for entry in entries if isinstance(entry, dict)]

    def set_attachments(
        self,
        identifier: str,
        attachments: list[dict],
        *,
        project_root: str | None = None,
    ) -> None:
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(identifier)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {identifier}")
            meta = dict(rec["meta"])
            meta["oompah.attachments"] = list(attachments)
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, str(rec["body"]))
            self.invalidate_read_cache()
            self._commit_and_push(f"Update attachments for oompah task {meta['id']}")

    def get_metadata(self, identifier: str) -> dict[str, object]:
        rec = self._read_record(identifier)
        if not rec:
            return {}
        meta = rec["meta"]
        result = {
            str(key): value
            for key, value in meta.items()
            if str(key).startswith("oompah.")
        }
        for key in (
            "work_branch",
            "target_branch",
            "review_url",
            "review_number",
            "merged_at",
        ):
            if key in meta and meta[key] is not None:
                result[f"oompah.{key}"] = meta[key]
        return result

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        if not key.startswith("oompah."):
            raise TrackerError(f"Native metadata key must be oompah-owned: {key}")
        with self._write_lock:
            self._prepare_default_branch_for_write()
            rec = self._read_record_uncached(identifier)
            if not rec:
                raise TrackerError(f"Native oompah task not found: {identifier}")
            meta = dict(rec["meta"])
            meta[key] = value
            compat_key = key.removeprefix("oompah.")
            if compat_key in {
                "work_branch",
                "target_branch",
                "review_url",
                "review_number",
                "merged_at",
            }:
                meta[compat_key] = value
            meta["updated_at"] = _now_iso()
            _write_markdown(Path(rec["path"]), meta, str(rec["body"]))
            self.invalidate_read_cache()
            self._commit_and_push(f"Update metadata for oompah task {meta['id']}")

    def is_archived(self, issue: Issue) -> bool:
        return canonicalize_status(issue.state) == ARCHIVED

    def invalidate_read_cache(self) -> None:
        with self._read_cache_guard:
            self._read_cache = None

    def _apply_field(
        self,
        meta: dict[str, Any],
        body: str,
        key: str,
        value: Any,
    ) -> str:
        key_norm = key.replace("_", "-")
        if key_norm == "status":
            meta["status"] = canonicalize_status(str(value))
        elif key_norm == "title":
            meta["title"] = str(value)
        elif key_norm in ("description", "desc"):
            body = _replace_section(body, "Summary", str(value))
        elif key_norm == "priority":
            meta["priority"] = _backlog_priority_int(value)
        elif key_norm == "assignee":
            meta["assignee"] = str(value) if value is not None else None
        elif key_norm in ("label", "labels"):
            meta["labels"] = _dedupe_strings(_string_list(value))
        elif key_norm == "add-label":
            meta["labels"] = _dedupe_strings(_string_list(meta.get("labels")) + [value])
        elif key_norm == "remove-label":
            remove = str(value).strip().lower()
            meta["labels"] = [
                label
                for label in _string_list(meta.get("labels"))
                if label.strip().lower() != remove
            ]
        elif key_norm == "parent":
            meta["parent"] = str(value) if value else None
        elif key_norm in ("type", "issue-type"):
            issue_type = str(value or "task").strip().lower()
            meta["type"] = issue_type if issue_type in _ISSUE_TYPES else "task"
        elif key_norm == "target-branch":
            meta["target_branch"] = str(value) if value else None
            meta["oompah.target_branch"] = str(value) if value else None
        elif key_norm == "work-branch":
            meta["work_branch"] = str(value) if value else None
            meta["oompah.work_branch"] = str(value) if value else None
        elif key_norm == "review-url":
            meta["review_url"] = str(value) if value else None
            meta["oompah.review_url"] = str(value) if value else None
        elif key_norm == "review-number":
            meta["review_number"] = str(value) if value else None
            meta["oompah.review_number"] = str(value) if value else None
        elif str(key).startswith("oompah."):
            meta[str(key)] = value
            compat_key = str(key).removeprefix("oompah.")
            if compat_key in {
                "work_branch",
                "target_branch",
                "review_url",
                "review_number",
                "merged_at",
            }:
                meta[compat_key] = value
        else:
            logger.debug("oompah_md update_issue ignoring unsupported field %s", key)
        return body

    def _normalize_record(self, rec: dict[str, Any]) -> Issue:
        meta = rec["meta"]
        identifier = str(meta.get("id") or Path(rec["path"]).stem)
        state = canonicalize_status(str(meta.get("status") or BACKLOG))
        labels = _string_list(meta.get("labels"))
        priority = _backlog_priority_int(meta.get("priority"))
        blocked_ids = _string_list(meta.get("blocked_by") or meta.get("dependencies"))
        created_at = _parse_utc(meta.get("created_at") or meta.get("created_date"))
        updated_at = _parse_utc(meta.get("updated_at") or meta.get("updated_date"))
        closed_at = updated_at if status_key(state) in {
            status_key(s) for s in self.terminal_states + [MERGED, ARCHIVED]
        } else None
        body = str(rec["body"])
        description = _section(body, "Summary")
        issue_type = str(meta.get("type") or "task").strip().lower()
        if issue_type not in _ISSUE_TYPES:
            issue_type = "task"
        attachments = []
        for entry in meta.get("oompah.attachments") or []:
            if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                attachments.append(entry["path"])
            elif isinstance(entry, str):
                attachments.append(entry)
        return Issue(
            id=identifier,
            identifier=identifier,
            title=str(meta.get("title") or identifier),
            description=description,
            priority=priority,
            state=state,
            branch_name=_sanitize_identifier(identifier),
            target_branch=_optional_str(
                meta.get("target_branch") or meta.get("oompah.target_branch")
            ),
            backports=meta.get("oompah.backports"),
            backport_of=meta.get("oompah.backport_of"),
            release_pick_metadata_loaded=True,
            issue_type=issue_type,
            parent_id=_optional_str(meta.get("parent") or meta.get("parent_task_id")),
            labels=[label.lower() for label in labels],
            blocked_by=[BlockerRef(id=dep, identifier=dep) for dep in blocked_ids],
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
            attachments=attachments,
            intake=meta.get("oompah.intake") if isinstance(meta.get("oompah.intake"), dict) else None,
            work_branch=_optional_str(
                meta.get("work_branch") or meta.get("oompah.work_branch")
            ),
            tracker_kind=TRACKER_KIND,
        )

    def _read_records(self) -> list[dict[str, Any]]:
        with self._read_cache_guard:
            cached = self._read_cache
        if cached is not None:
            return cached
        records: list[dict[str, Any]] = []
        if self.tasks_root.is_dir():
            for path in sorted(self.tasks_root.glob("*/*.md")):
                try:
                    meta, body = _read_markdown(path)
                except TrackerError as exc:
                    logger.warning("Skipping invalid native oompah task %s: %s", path, exc)
                    continue
                records.append({"path": path, "meta": meta, "body": body})
        with self._read_cache_guard:
            self._read_cache = records
        return records

    def _read_record(self, identifier: str) -> dict[str, Any] | None:
        needle = self._lookup_id(identifier)
        for rec in self._read_records():
            task_id = str(rec["meta"].get("id") or Path(rec["path"]).stem)
            if self._lookup_id(task_id) == needle:
                return rec
        return None

    def _read_record_uncached(self, identifier: str) -> dict[str, Any] | None:
        self.invalidate_read_cache()
        return self._read_record(identifier)

    def _lookup_id(self, identifier: str) -> str:
        return str(identifier or "").strip().lower()

    def _initial_body(self, description: str | None) -> str:
        summary = (description or "").strip()
        return (
            f"## Summary\n\n{summary}\n\n"
            "## Acceptance Criteria\n\n"
            "- [ ] Define acceptance criteria.\n\n"
            "## Notes\n\n"
        )

    def _path_for(self, identifier: str, status: str) -> Path:
        return self.tasks_root / _status_dir(status) / f"{_safe_id(identifier)}.md"

    def _task_prefix(self) -> str:
        config_path = self.tasks_root / "config.yml"
        if config_path.exists():
            try:
                data = yaml.load(config_path.read_text(encoding="utf-8"), Loader=_YAML_SAFE_LOADER)
            except (OSError, yaml.YAMLError):
                data = {}
            if isinstance(data, dict):
                prefix = str(data.get("task_prefix") or data.get("taskPrefix") or "").strip()
                if prefix:
                    return _safe_id(prefix).upper()
        repo_name = _safe_id(self._root.name).upper()
        return repo_name or DEFAULT_TASK_PREFIX

    def _next_identifier(self) -> str:
        prefix = self._task_prefix()
        max_seen = 0
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.I)
        for rec in self._read_records():
            match = pattern.match(str(rec["meta"].get("id") or ""))
            if match:
                max_seen = max(max_seen, int(match.group(1)))
        return f"{prefix}-{max_seen + 1}"

    def _active_status(self) -> str:
        return self.active_states[0] if self.active_states else OPEN

    def _terminal_status(self) -> str:
        return self.terminal_states[0] if self.terminal_states else DONE

    def _add_child_to_parent(self, parent_id: str, child_id: str) -> None:
        parent = self._read_record_uncached(parent_id)
        if not parent:
            return
        meta = dict(parent["meta"])
        children = _dedupe_strings(_string_list(meta.get("children")) + [child_id])
        meta["children"] = children
        meta["updated_at"] = _now_iso()
        _write_markdown(Path(parent["path"]), meta, str(parent["body"]))

    def _git_sync_requested(self) -> bool:
        if not self.git_sync:
            return False
        raw = os.environ.get("OOMPAH_MD_TRACKER_GIT_SYNC", "1").strip().lower()
        return raw not in {"0", "false", "no", "off"}

    def _prepare_default_branch_for_write(self) -> None:
        if not self._git_sync_requested() or not self._is_git_repo():
            return
        branch = self.default_branch or self._infer_default_branch() or "main"
        current = self._git(["symbolic-ref", "--short", "HEAD"], check=True).stdout.strip()
        if current != branch:
            raise TrackerError(
                f"Native oompah task writes must run on default branch {branch!r}; "
                f"current branch is {current!r}"
            )
        if self._has_remote("origin"):
            self._git(["fetch", "origin", branch], check=False)
            self._git(["pull", "--rebase", "origin", branch], check=True)

    def _commit_and_push(self, subject: str) -> None:
        if not self._git_sync_requested() or not self._is_git_repo():
            return
        self._git(["add", TASKS_DIR], check=True)
        if self._git(["diff", "--cached", "--quiet", "--", TASKS_DIR], check=False).returncode == 0:
            return
        message = (
            f"{subject}\n\n"
            "🤖 Generated with https://github.com/lesserevil/oompah\n\n"
            "Co-authored-by: oompah <lesserevil@users.noreply.github.com>\n"
        )
        self._git(["commit", "-m", message], check=True)
        branch = self.default_branch or self._infer_default_branch() or "main"
        if not self._has_remote("origin"):
            return
        push = self._git(["push", "origin", f"HEAD:{branch}"], check=False)
        if push.returncode == 0:
            return
        self._git(["pull", "--rebase", "origin", branch], check=True)
        self._git(["push", "origin", f"HEAD:{branch}"], check=True)

    def _is_git_repo(self) -> bool:
        return self._git(["rev-parse", "--is-inside-work-tree"], check=False).returncode == 0

    def _has_remote(self, name: str) -> bool:
        return self._git(["remote", "get-url", name], check=False).returncode == 0

    def _infer_default_branch(self) -> str | None:
        result = self._git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], check=False)
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        if value.startswith("origin/"):
            return value.split("/", 1)[1]
        return value or None

    def _git(self, args: list[str], *, check: bool) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *args],
            cwd=str(self._root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if check and result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise TrackerError(f"git {' '.join(args)} failed: {stderr}")
        return result


def _dedupe_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_utc(value: Any) -> datetime | None:
    parsed = _parse_timestamp(value)
    if parsed is not None and parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _oompah_md_factory(
    *,
    active_states: list[str],
    terminal_states: list[str],
    cwd: str | None = None,
    default_branch: str | None = None,
    **kwargs: Any,
) -> OompahMarkdownTracker:
    return OompahMarkdownTracker(
        active_states=active_states,
        terminal_states=terminal_states,
        cwd=cwd,
        default_branch=default_branch,
    )
