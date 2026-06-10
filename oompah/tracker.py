"""Backlog.md issue tracker client for oompah."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

import yaml

from oompah.models import BlockerRef, Issue
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DONE,
    IN_PROGRESS,
    NEEDS_ANSWER,
    NEEDS_HUMAN,
    OPEN,
    canonicalize_status,
    status_key,
)

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
_BACKLOG_CLI_OWNED_FRONTMATTER = frozenset({
    "id",
    "title",
    "status",
    "assignee",
    "assignees",
    "created_date",
    "updated_date",
    "labels",
    "dependencies",
    "priority",
    "ordinal",
})

# Front-matter fields that the Backlog CLI owns and rewrites on every edit.
# Any key NOT in this set is considered custom/user-defined and must be
# preserved across CLI mutations (TASK-397 / TASK-408).
_KNOWN_BACKLOG_FIELDS: frozenset[str] = frozenset({
    "id",
    "title",
    "status",
    "assignee",
    "assignees",
    "created_date",
    "updated_date",
    "labels",
    "dependencies",
    "priority",
    "ordinal",
    "parent",
    "parent_task_id",
    "milestone",
    "plan",
    "notes",
    "final_summary",
    "finalSummary",
    "acceptance_criteria",
    "acceptanceCriteria",
    "definition_of_done",
    "definitionOfDone",
    "refs",
    "references",
    "modified_files",
    "modifiedFiles",
    "doc",
    # oompah-owned fields written via _write_markdown_frontmatter (not CLI)
    "oompah.attachments",
    "oompah_attachments",
    # release-pick / target-branch metadata (TASK-454.1)
    "oompah.target_branch",
    "oompah.backports",
    "oompah.backport_of",
})


def _sanitize_identifier(identifier: str) -> str:
    """Replace any character not in [A-Za-z0-9._-] with underscore.

    This mirrors the branch-name sanitization done in projects.py so that
    the normalized Issue.branch_name matches the actual git worktree branch.
    """
    return _SAFE_CHARS.sub("_", identifier)


logger = logging.getLogger(__name__)

# Default status for newly created tasks. Oompah-created tasks start in
# Backlog unless the caller explicitly asks for a dispatchable status.
DEFAULT_INITIAL_STATUS = BACKLOG
_DEFAULT_BACKLOG_TIMEOUT_SECONDS = 60.0

_BACKLOG_PRIORITY_TO_INT = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "normal": 2,
    "low": 3,
    "backlog": 4,
}
# Backlog.md's CLI only accepts high/medium/low even though oompah supports P0.
# P0/critical is therefore written directly to task frontmatter.
_INT_TO_BACKLOG_CLI_PRIORITY = {
    1: "high",
    2: "medium",
    3: "low",
    4: "low",
}


def _resolve_backlog_timeout() -> float:
    """Read the Backlog.md subprocess timeout from env."""
    raw = os.environ.get("OOMPAH_BACKLOG_MD_TIMEOUT_SECONDS")
    if raw is None or not raw.strip():
        return _DEFAULT_BACKLOG_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid OOMPAH_BACKLOG_MD_TIMEOUT_SECONDS=%r — using default %ss",
            raw, _DEFAULT_BACKLOG_TIMEOUT_SECONDS,
        )
        return _DEFAULT_BACKLOG_TIMEOUT_SECONDS
    if value <= 0:
        logger.warning(
            "OOMPAH_BACKLOG_MD_TIMEOUT_SECONDS=%r must be > 0 — using default %ss",
            raw, _DEFAULT_BACKLOG_TIMEOUT_SECONDS,
        )
        return _DEFAULT_BACKLOG_TIMEOUT_SECONDS
    return value


def _sort_issues_for_dispatch(issues: list[Issue]) -> list[Issue]:
    """Sort issues by priority, creation time, and identifier."""
    def sort_key(issue: Issue):
        pri = issue.priority if issue.priority is not None else 999
        created = issue.created_at or datetime.max.replace(tzinfo=timezone.utc)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (pri, created, issue.identifier)

    return sorted(issues, key=sort_key)


class TrackerError(Exception):
    """Raised when tracker operations fail."""


class TrackerNotConfiguredError(TrackerError):
    """Raised when the project's Backlog.md store is missing."""


class TrackerTimeoutError(TrackerError):
    """Raised when a tracker subprocess exceeds its timeout.

    Treated as transient/environmental rather than a code bug. Callers
    should log at WARNING and let the next poll tick retry.
    """


def _write_attachments_manifest(
    project_root: str,
    identifier: str,
    attachments: list[dict],
) -> None:
    """Write the dashboard sidecar attachment manifest.

    Best-effort: failures are logged, not raised.
    """
    from oompah.attachments import ATTACHMENTS_SUBDIR

    directory = os.path.join(project_root, ATTACHMENTS_SUBDIR, identifier)
    try:
        os.makedirs(directory, exist_ok=True)
        with open(
            os.path.join(directory, "manifest.json"), "w", encoding="utf-8",
        ) as f:
            json.dump(list(attachments), f, indent=2)
    except OSError as exc:
        logger.warning(
            "manifest write failed for %s in %s: %s",
            identifier,
            project_root,
            exc,
        )


@runtime_checkable
class TrackerProtocol(Protocol):
    """Common interface that every oompah tracker adapter must satisfy.

    All operations used by the orchestrator, server, watchers, prompts, and
    attachments are declared here.  Both ``BacklogMdTracker`` and any future
    adapter (e.g. ``GitHubIssueTracker``) must implement every method in this
    protocol so that callers can depend on the protocol rather than a concrete
    class.

    Methods that are specific to a single backend (such as
    ``BacklogMdTracker.task_file_path`` and ``.root_path``) are intentionally
    excluded; callers that need them should narrow the type with
    ``isinstance(..., BacklogMdTracker)`` as appropriate.
    """

    # ------------------------------------------------------------------
    # Issue reads
    # ------------------------------------------------------------------

    def fetch_candidate_issues(self) -> list[Issue]:
        """Return issues in active (dispatchable) states, sorted for dispatch."""
        ...

    def fetch_all_issues(self) -> list[Issue]:
        """Return all issues regardless of state."""
        ...

    def fetch_all_issues_enriched(self) -> list[Issue]:
        """Return all issues with full detail (may make extra API calls)."""
        ...

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        """Return a single issue by identifier, or None if not found."""
        ...

    def fetch_children(self, epic_id: str) -> list[Issue]:
        """Return child issues that reference the given parent identifier."""
        ...

    def fetch_comments(self, identifier: str) -> list[dict]:
        """Return all comments on an issue as a list of dicts."""
        ...

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        """Return all issues whose state matches any of the given names."""
        ...

    def fetch_issues_by_labels(
        self,
        labels: list[str],
        *,
        states: list[str] | None = None,
    ) -> list[Issue]:
        """Return issues matching all labels and an optional state filter."""
        ...

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        """Return current state snapshots for the given identifiers."""
        ...

    def fetch_memories(self) -> dict[str, str]:
        """Return backend-specific memory key/value pairs (may be empty)."""
        ...

    # ------------------------------------------------------------------
    # Issue mutations
    # ------------------------------------------------------------------

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
        """Create a new issue and return the normalized Issue record."""
        ...

    def update_issue(self, identifier: str, **fields: str) -> None:
        """Update one or more fields on an existing issue."""
        ...

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        """Move an issue to the first configured terminal state."""
        ...

    def reopen_issue(self, identifier: str) -> None:
        """Move an issue back to the first configured active state."""
        ...

    def archive_issue(self, identifier: str) -> None:
        """Archive an issue (backend-specific semantics)."""
        ...

    def mark_needs_human(
        self, identifier: str, comment: str, author: str = "oompah"
    ) -> None:
        """Move an issue to Needs Human and post the actionable comment."""
        ...

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        """Append a comment to an issue and return the comment dict."""
        ...

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def add_label(self, identifier: str, label: str) -> None:
        """Add a label to an issue."""
        ...

    def remove_label(self, identifier: str, label: str) -> None:
        """Remove a label from an issue (no-op if label is absent)."""
        ...

    # ------------------------------------------------------------------
    # Hierarchy and dependencies
    # ------------------------------------------------------------------

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        """Link a child issue to a parent issue."""
        ...

    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        """Record that blocked_id depends on blocker_id."""
        ...

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    def fetch_attachments(self, identifier: str) -> list[dict]:
        """Return rich attachment records for an issue."""
        ...

    def set_attachments(
        self,
        identifier: str,
        attachments: list[dict],
        *,
        project_root: str | None = None,
    ) -> None:
        """Replace the attachment records for an issue."""
        ...

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self, identifier: str) -> dict[str, object]:
        """Return oompah-owned metadata fields for an issue."""
        ...

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        """Set one oompah-owned metadata field on an issue."""
        ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_archived(self, issue: Issue) -> bool:
        """Return True when the issue should be considered archived."""
        ...

    def invalidate_read_cache(self) -> None:
        """Invalidate any cached reads so the next fetch returns fresh data."""
        ...


class BacklogMdTracker(TrackerProtocol):
    """Issue tracker client backed by Backlog.md task files and CLI writes."""

    def __init__(
        self,
        active_states: list[str],
        terminal_states: list[str],
        cwd: str | None = None,
        backlog_dir: str | None = None,
    ):
        self.active_states = [s.strip().lower() for s in active_states]
        self.terminal_states = [s.strip().lower() for s in terminal_states]
        self.cwd = cwd
        self._root = Path(cwd or os.getcwd()).resolve()
        self._configured_backlog_dir = backlog_dir
        self._last_fingerprint: str | None = None
        self._task_locks: dict[str, threading.RLock] = {}
        self._task_locks_guard = threading.Lock()
        # Per-(include_completed) cache of parsed task records. Reading and
        # YAML-parsing the whole task corpus is the dominant tick cost, and
        # several tick phases each call it; caching collapses those to one
        # parse. Invalidated at tick start (by the orchestrator) and on any
        # write, so a read never returns a snapshot older than the last
        # mutation. Guarded for the orchestrator's concurrent tick phases.
        self._read_cache: dict[bool, list[dict]] = {}
        self._read_cache_guard = threading.Lock()
        self._last_read_stats: dict[str, object] = {}

    def fetch_candidate_issues(self) -> list[Issue]:
        """Fetch tasks in active states, sorted for dispatch."""
        if not self.active_states:
            return []
        issues = [
            issue for issue in self._read_all_tasks(include_completed=False)
            if canonicalize_status(issue.state).strip().lower() in self.active_states
        ]
        return _sort_issues_for_dispatch(issues)

    def fetch_in_progress_issues(self) -> list[Issue]:
        """Fetch tasks currently in In Progress state (not completed).

        Unlike ``fetch_candidate_issues``, this returns tasks in the working
        state that are not normally in the dispatch candidate list.  Used by
        the orphan-reset sweep to find tasks left In Progress after a retry
        claim is released (TASK-409).
        """
        return [
            issue
            for issue in self._read_all_tasks(include_completed=False)
            if canonicalize_status(issue.state) == IN_PROGRESS
        ]

    def fetch_all_issues(self) -> list[Issue]:
        """Fetch all Backlog.md tasks from active and completed folders."""
        return self._read_all_tasks(include_completed=True)

    def fetch_all_issues_enriched(self) -> list[Issue]:
        """Backlog.md task files already contain the details we need."""
        return self.fetch_all_issues()

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
        """Create a Backlog.md task and return the normalized Issue."""
        args = ["task", "create", title, "--plain"]
        if description:
            args.extend(["--description", description])
        status = self._create_status(initial_status)
        if status:
            args.extend(["--status", status])
        priority_name = _backlog_cli_priority_name(priority)
        direct_priority = _backlog_direct_priority_value(priority)
        if priority_name:
            args.extend(["--priority", priority_name])
        effective_labels = list(labels or [])
        if issue_type and issue_type != "task" and issue_type not in effective_labels:
            effective_labels.append(issue_type)
        if effective_labels:
            args.extend(["--labels", ",".join(effective_labels)])
        if parent:
            args.extend(["--parent", parent])
        output = self._run_backlog(args)
        identifier = _parse_backlog_plain_identifier(output)
        if identifier:
            if direct_priority is not None:
                self._set_frontmatter_field(identifier, "priority", direct_priority)
            issue = self.fetch_issue_detail(identifier)
            if issue:
                return issue
        created = self._find_task_by_title(title)
        if created:
            if direct_priority is not None:
                self._set_frontmatter_field(created.identifier, "priority", direct_priority)
                refreshed = self.fetch_issue_detail(created.identifier)
                if refreshed:
                    return refreshed
            return created
        raise TrackerError("Unexpected response from backlog task create")

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        """Append a comment to a Backlog.md task."""
        comment_text = str(text).strip()
        if not comment_text:
            raise TrackerError("Comment text is required")
        comment_author = _backlog_comment_field(author, fallback="oompah")
        with self._task_lock(identifier):
            path = self._task_path_for(identifier)
            if not path:
                raise TrackerError(f"Backlog.md task not found: {identifier}")
            meta, body = _read_markdown_frontmatter(path)
            created = _format_backlog_comment_timestamp()
            body = _append_backlog_comment(
                body,
                text=comment_text,
                author=comment_author,
                created=created,
            )
            meta["updated_date"] = created
            _write_markdown_frontmatter(path, meta, body)
        return {"author": comment_author, "text": comment_text}

    def fetch_memories(self) -> dict[str, str]:
        """Backlog.md has no memories equivalent."""
        return {}

    def fetch_comments(self, identifier: str) -> list[dict]:
        """Fetch comments parsed from the task markdown file."""
        rec = self._read_task_record(identifier)
        if not rec:
            return []
        return _parse_backlog_comments(rec["body"])

    def task_file_path(self, identifier: str) -> Path | None:
        """Return the Backlog.md file path for a task identifier, if present."""
        return self._task_path_for(identifier)

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        """Fallback for callers that could not set the Backlog.md parent at creation."""
        self.update_issue(child_id, parent=parent_id)

    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        """Set the task dependency list to include blocker_id."""
        with self._task_lock(blocked_id):
            issue = self.fetch_issue_detail(blocked_id)
            existing = [b.identifier or b.id for b in (issue.blocked_by if issue else [])]
            deps = [d for d in existing if d]
            if blocker_id not in deps:
                deps.append(blocker_id)
            self._run_backlog_task_edit([
                "task", "edit", blocked_id,
                "--depends-on", ",".join(deps),
                "--plain",
            ], blocked_id)

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        """Fetch a single task with full details."""
        rec = self._read_task_record(identifier)
        if not rec:
            return None
        return self._normalize_task(rec)

    def fetch_children(self, epic_id: str) -> list[Issue]:
        """Fetch child tasks that reference the given parent id."""
        needle = self._normalize_lookup_id(epic_id)
        children = []
        for rec in self._read_task_records(include_completed=True):
            parent = rec["meta"].get("parent") or rec["meta"].get("parent_task_id")
            if parent and self._normalize_lookup_id(str(parent)) == needle:
                children.append(self._normalize_task(rec))
        return _sort_issues_for_dispatch(children)

    def update_issue(self, identifier: str, **fields: str) -> None:
        """Update common Backlog.md task fields."""
        with self._task_lock(identifier):
            args = ["task", "edit", identifier, "--plain"]
            handled = False
            direct_priority = None
            for key, value in fields.items():
                key_norm = key.replace("_", "-")
                if key_norm == "status":
                    args.extend(["--status", self._status_with_config_case(str(value))])
                    handled = True
                elif key_norm == "title":
                    args.extend(["--title", str(value)])
                    handled = True
                elif key_norm in ("description", "desc"):
                    args.extend(["--description", str(value)])
                    handled = True
                elif key_norm == "priority":
                    direct_priority = _backlog_direct_priority_value(value)
                    pri = _backlog_cli_priority_name(value)
                    if pri:
                        args.extend(["--priority", pri])
                        handled = True
                elif key_norm in ("assignee", "labels", "label", "parent"):
                    if key_norm == "parent":
                        self._set_frontmatter_field(identifier, "parent", str(value))
                        continue
                    flag = {
                        "label": "--label",
                        "labels": "--label",
                    }.get(key_norm, f"--{key_norm}")
                    args.extend([flag, str(value)])
                    handled = True
                elif key_norm == "add-label":
                    args.extend(["--add-label", str(value)])
                    handled = True
                elif key_norm == "remove-label":
                    args.extend(["--remove-label", str(value)])
                    handled = True
                else:
                    logger.debug(
                        "Backlog.md update_issue ignoring unsupported field %s", key,
                    )
            if handled:
                try:
                    self._run_backlog_task_edit(args, identifier)
                except TrackerError as exc:
                    # The Backlog CLI cannot edit tasks in the completed/ directory.
                    # Fall back to direct file editing when the task exists on disk
                    # (e.g. in completed/) but the CLI reports it as not found.
                    if _is_task_not_found_error(exc) and self._task_path_for(identifier):
                        logger.debug(
                            "Backlog CLI could not find %s; falling back to direct edit",
                            identifier,
                        )
                        self._update_issue_fields_direct(identifier, fields)
                    else:
                        raise
            if direct_priority is not None:
                self._set_frontmatter_field(identifier, "priority", direct_priority)

    def _update_issue_fields_direct(self, identifier: str, fields: dict) -> None:
        """Write task fields directly to the markdown file.

        Used as a fallback when the backlog CLI cannot find the task (e.g.
        because it lives in ``completed/`` rather than ``tasks/``).  Mirrors
        the same field mapping used by ``update_issue`` for the CLI path.
        """
        path = self._task_path_for(identifier)
        if not path:
            raise TrackerError(f"Backlog.md task not found: {identifier}")
        meta, body = _read_markdown_frontmatter(path)
        body_changed = False
        for key, value in fields.items():
            key_norm = key.replace("_", "-")
            if key_norm == "status":
                meta["status"] = self._status_with_config_case(str(value))
            elif key_norm == "title":
                meta["title"] = str(value)
            elif key_norm in ("description", "desc"):
                begin_marker = "<!-- SECTION:DESCRIPTION:BEGIN -->"
                end_marker = "<!-- SECTION:DESCRIPTION:END -->"
                start = body.find(begin_marker)
                if start != -1:
                    stop = body.find(end_marker, start + len(begin_marker))
                    if stop != -1:
                        body = (
                            body[: start + len(begin_marker)]
                            + f"\n{value}\n"
                            + body[stop:]
                        )
                        body_changed = True
                if not body_changed:
                    body = body.rstrip("\n") + (
                        f"\n\n## Description\n\n"
                        f"{begin_marker}\n{value}\n{end_marker}\n"
                    )
                    body_changed = True
            elif key_norm == "priority":
                pri = _backlog_cli_priority_name(value)
                if pri:
                    meta["priority"] = pri
            elif key_norm == "assignee":
                meta["assignee"] = str(value)
            elif key_norm in ("label", "labels"):
                meta["labels"] = [str(value)]
            elif key_norm == "add-label":
                existing = meta.get("labels") or []
                if not isinstance(existing, list):
                    existing = [str(existing)] if existing else []
                if str(value) not in existing:
                    existing = list(existing) + [str(value)]
                meta["labels"] = existing
            elif key_norm == "remove-label":
                existing = meta.get("labels") or []
                if isinstance(existing, list):
                    meta["labels"] = [lb for lb in existing if lb != str(value)]
        meta["updated_date"] = _format_backlog_comment_timestamp()
        _write_markdown_frontmatter(path, meta, body)

    def mark_needs_human(
        self, identifier: str, comment: str, author: str = "oompah"
    ) -> None:
        """Move a task to Needs Human and leave the actionable comment last."""
        with self._task_lock(identifier):
            self.update_issue(identifier, status=NEEDS_HUMAN)
            self.add_comment(identifier, comment, author=author)

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        """Move a Backlog.md task to the configured terminal status."""
        with self._task_lock(identifier):
            status = self._terminal_status()
            self._run_backlog_task_edit([
                "task", "edit", identifier,
                "--status", status,
                "--plain",
            ], identifier)
            if reason:
                self.add_comment(identifier, reason)

    def reopen_issue(self, identifier: str) -> None:
        """Move a task back to the first configured active status."""
        with self._task_lock(identifier):
            self._run_backlog_task_edit([
                "task", "edit", identifier,
                "--status", self._active_status(),
                "--plain",
            ], identifier)

    def add_label(self, identifier: str, label: str) -> None:
        with self._task_lock(identifier):
            self._run_backlog_task_edit([
                "task", "edit", identifier, "--add-label", label, "--plain",
            ], identifier)

    def remove_label(self, identifier: str, label: str) -> None:
        with self._task_lock(identifier):
            try:
                self._run_backlog_task_edit([
                    "task", "edit", identifier, "--remove-label", label, "--plain",
                ], identifier)
            except TrackerError:
                pass

    def fetch_attachments(self, identifier: str) -> list[dict]:
        """Return rich attachment records from task front matter."""
        rec = self._read_task_record(identifier)
        if not rec:
            return []
        meta = rec["meta"]
        entries = (
            meta.get("oompah.attachments")
            or meta.get("oompah_attachments")
            or []
        )
        return [e for e in entries if isinstance(e, dict)]

    def set_attachments(
        self,
        identifier: str,
        attachments: list[dict],
        *,
        project_root: str | None = None,
    ) -> None:
        """Replace the task's ``oompah.attachments`` front-matter metadata."""
        path = self._task_path_for(identifier)
        if not path:
            raise TrackerError(f"Backlog.md task not found: {identifier}")
        with self._task_lock(identifier):
            meta, body = _read_markdown_frontmatter(path)
            meta["oompah.attachments"] = list(attachments)
            _write_markdown_frontmatter(path, meta, body)
        if project_root:
            _write_attachments_manifest(project_root, identifier, attachments)

    def get_metadata(self, identifier: str) -> dict[str, object]:
        """Return oompah-owned metadata fields from task front matter."""
        rec = self._read_task_record(identifier)
        if not rec:
            return {}
        meta = rec["meta"]
        return {
            str(key): value
            for key, value in meta.items()
            if str(key).startswith("oompah.")
        }

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        """Set one oompah-owned front-matter metadata field on a task."""
        if not key.startswith("oompah."):
            raise TrackerError(f"Backlog.md metadata key must be oompah-owned: {key}")
        path = self._task_path_for(identifier)
        if not path:
            raise TrackerError(f"Backlog.md task not found: {identifier}")
        with self._task_lock(identifier):
            meta, body = _read_markdown_frontmatter(path)
            meta[key] = value
            _write_markdown_frontmatter(path, meta, body)

    def archive_issue(self, identifier: str) -> None:
        self._run_backlog(["task", "archive", identifier])

    def is_archived(self, issue: Issue) -> bool:
        return (
            canonicalize_status(issue.state) == ARCHIVED
            or "archive:yes" in issue.labels
            or "archived" in issue.labels
        )

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        if not state_names:
            return []
        normalized = {canonicalize_status(s).strip().lower() for s in state_names}
        return [
            issue for issue in self._read_all_tasks(include_completed=True)
            if canonicalize_status(issue.state).strip().lower() in normalized
        ]

    def fetch_issues_by_labels(
        self,
        labels: list[str],
        *,
        states: list[str] | None = None,
    ) -> list[Issue]:
        """Fetch tasks matching all labels and optional statuses."""
        wanted_labels = {label.strip().lower() for label in labels if label.strip()}
        wanted_states = (
            {canonicalize_status(state).strip().lower() for state in states}
            if states is not None
            else None
        )
        issues = []
        for issue in self._read_all_tasks(include_completed=True):
            labels_present = {label.strip().lower() for label in (issue.labels or [])}
            if wanted_labels and not wanted_labels.issubset(labels_present):
                continue
            if wanted_states is not None and (
                canonicalize_status(issue.state).strip().lower() not in wanted_states
            ):
                continue
            issues.append(issue)
        return _sort_issues_for_dispatch(issues)

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        issues = []
        for issue_id in issue_ids:
            issue = self.fetch_issue_detail(issue_id)
            if issue:
                issues.append(issue)
        return issues

    def working_set_fingerprint(self) -> str:
        """Hash Backlog.md config and task-file contents."""
        backlog_dir = self._backlog_dir()
        files = []
        for candidate in [
            self._root / "backlog.config.yml",
            backlog_dir / "config.yml",
        ]:
            if candidate.exists():
                files.append(candidate)
        files.extend(self._task_files(include_completed=True))
        if not files:
            raise TrackerError("Unable to compute Backlog.md working set fingerprint")
        digest = hashlib.sha256()
        for path in sorted(files):
            rel = path.relative_to(self._root) if path.is_relative_to(self._root) else path
            digest.update(str(rel).encode())
            digest.update(b"\0")
            try:
                digest.update(path.read_bytes())
            except OSError as exc:
                raise TrackerError(f"Failed to read Backlog.md file {path}: {exc}")
            digest.update(b"\0")
        return f"backlog:{digest.hexdigest()[:16]}"

    def has_changed(self) -> bool:
        try:
            current = self.working_set_fingerprint()
        except TrackerError:
            logger.debug("Backlog.md fingerprint unavailable — assuming changed")
            return True
        if self._last_fingerprint is None:
            self._last_fingerprint = current
            return True
        if current != self._last_fingerprint:
            self._last_fingerprint = current
            return True
        return False

    def reset_fingerprint(self) -> None:
        self._last_fingerprint = None

    @property
    def last_fingerprint(self) -> str | None:
        return self._last_fingerprint

    @property
    def root_path(self) -> Path:
        """Repository root used for Backlog.md commands and file reads."""
        return self._root

    def _read_all_tasks(self, *, include_completed: bool) -> list[Issue]:
        return [
            self._normalize_task(rec)
            for rec in self._read_task_records(include_completed=include_completed)
        ]

    def invalidate_read_cache(self) -> None:
        """Drop the cached task-record snapshots.

        Called at tick start (by the orchestrator) and after any write, so
        cached reads never outlive a mutation.
        """
        with self._read_cache_guard:
            self._read_cache.clear()

    def read_stats(self) -> dict[str, object]:
        """Return timing/count data for the most recent corpus read."""
        with self._read_cache_guard:
            return dict(self._last_read_stats)

    def _read_task_records(self, *, include_completed: bool) -> list[dict]:
        start = time.monotonic()
        with self._read_cache_guard:
            cached = self._read_cache.get(include_completed)
        if cached is not None:
            with self._read_cache_guard:
                self._last_read_stats = {
                    "include_completed": include_completed,
                    "cache_hit": True,
                    "record_count": len(cached),
                    "duration_ms": round((time.monotonic() - start) * 1000, 3),
                    "root": str(self._root),
                }
            return cached
        records = []
        for path in self._task_files(include_completed=include_completed):
            try:
                meta, body = _read_markdown_frontmatter(path)
            except TrackerError as exc:
                logger.warning("Skipping invalid Backlog.md task %s: %s", path, exc)
                continue
            records.append({"path": path, "meta": meta, "body": body})
        with self._read_cache_guard:
            self._read_cache[include_completed] = records
            self._last_read_stats = {
                "include_completed": include_completed,
                "cache_hit": False,
                "record_count": len(records),
                "duration_ms": round((time.monotonic() - start) * 1000, 3),
                "root": str(self._root),
            }
        return records

    def _read_task_record(self, identifier: str) -> dict | None:
        path = self._task_path_for(identifier)
        if not path:
            return None
        meta, body = _read_markdown_frontmatter(path)
        return {"path": path, "meta": meta, "body": body}

    def _find_task_by_title(self, title: str) -> Issue | None:
        for issue in self.fetch_all_issues():
            if issue.title == title:
                return issue
        return None

    def _set_frontmatter_field(self, identifier: str, key: str, value) -> None:
        path = self._task_path_for(identifier)
        if not path:
            raise TrackerError(f"Backlog.md task not found: {identifier}")
        with self._task_lock(identifier):
            meta, body = _read_markdown_frontmatter(path)
            meta[key] = value
            _write_markdown_frontmatter(path, meta, body)
        # Direct frontmatter write bypasses _run_backlog — drop the cache.
        self.invalidate_read_cache()

    def _normalize_task(self, rec: dict) -> Issue:
        meta = rec["meta"]
        body = rec["body"]
        path = rec["path"]
        task_prefix = self._task_prefix()
        identifier = _identifier_from_task_record(meta, path, task_prefix)
        title = _title_from_task_record(meta, path, task_prefix) or identifier
        state = canonicalize_status(str(meta.get("status") or self._default_status()))
        # Files in archive/tasks/ are treated as Archived even when their
        # frontmatter still shows the original status; the backlog CLI moves
        # the file without updating the status field.
        if path.is_relative_to(self._backlog_dir() / "archive" / "tasks"):
            state = ARCHIVED
        labels = _string_list(meta.get("labels"))
        priority = _backlog_priority_int(meta.get("priority"))
        dependencies = _string_list(meta.get("dependencies"))
        blocked_by = [
            BlockerRef(id=dep, identifier=dep)
            for dep in dependencies
        ]
        created_at = _parse_backlog_timestamp(meta.get("created_date"))
        updated_at = _parse_backlog_timestamp(meta.get("updated_date"))
        terminal = canonicalize_status(state).strip().lower() in self.terminal_states
        closed_at = updated_at if terminal else None
        parent_id = meta.get("parent") or meta.get("parent_task_id")
        attachments = []
        entries = (
            meta.get("oompah.attachments")
            or meta.get("oompah_attachments")
            or []
        )
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and isinstance(entry.get("path"), str):
                    attachments.append(entry["path"])
                elif isinstance(entry, str):
                    attachments.append(entry)
        description = _extract_backlog_section(body, "DESCRIPTION")
        explicit_type = meta.get("type")
        if explicit_type:
            issue_type = str(explicit_type)
        elif _looks_like_epic_task(title, description):
            issue_type = "epic"
        else:
            issue_type = _issue_type_from_labels(labels)
        # Populate target_branch from oompah.target_branch (preferred) or the
        # compatible top-level target_branch frontmatter field (TASK-454.1).
        raw_target = meta.get("oompah.target_branch") or meta.get("target_branch")
        target_branch = str(raw_target).strip() if raw_target else None
        return Issue(
            id=identifier,
            identifier=identifier,
            title=title,
            description=description,
            priority=priority,
            state=state,
            branch_name=_sanitize_identifier(identifier),
            target_branch=target_branch,
            backports=meta.get("oompah.backports"),
            backport_of=meta.get("oompah.backport_of"),
            release_pick_metadata_loaded=True,
            issue_type=issue_type,
            parent_id=str(parent_id) if parent_id else None,
            labels=[label.lower() for label in labels],
            blocked_by=blocked_by,
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
            attachments=attachments,
        )

    def _task_path_for(self, identifier: str) -> Path | None:
        needle = self._normalize_lookup_id(identifier)
        for path in self._task_files(include_completed=True):
            try:
                meta, _body = _read_markdown_frontmatter(path)
            except TrackerError:
                continue
            task_prefix = self._task_prefix()
            task_id = _identifier_from_task_record(meta, path, task_prefix)
            if self._normalize_lookup_id(task_id) == needle:
                return path
        return None

    def _task_files(self, *, include_completed: bool) -> list[Path]:
        backlog_dir = self._backlog_dir()
        dirs = [backlog_dir / "tasks"]
        if include_completed:
            dirs.append(backlog_dir / "completed")
            # The backlog CLI `task archive` command moves files to archive/tasks/
            # (not completed/) without updating the status field.  Include that
            # directory so fetch_issue_detail and other reads can still find them.
            dirs.append(backlog_dir / "archive" / "tasks")
        files: list[Path] = []
        for directory in dirs:
            if directory.is_dir():
                files.extend(directory.glob("*.md"))
        return sorted(files)

    def _backlog_dir(self) -> Path:
        configured = (
            self._configured_backlog_dir
            or os.environ.get("OOMPAH_BACKLOG_MD_DIR")
            or os.environ.get("OOMPAH_BACKLOG_DIR")
        )
        if configured:
            path = Path(configured)
            if not path.is_absolute():
                path = self._root / path
            if path.exists():
                return path.resolve()
            raise TrackerNotConfiguredError(
                f"Backlog.md directory not found: {path}"
            )

        root_config = self._root / "backlog.config.yml"
        if root_config.exists():
            config = _read_yaml_file(root_config)
            directory = config.get("backlogDirectory") or config.get("backlog_directory")
            if directory:
                path = self._root / str(directory)
                if path.exists():
                    return path.resolve()

        for name in ("backlog", ".backlog"):
            path = self._root / name
            if (path / "config.yml").exists() or (path / "tasks").exists():
                return path.resolve()

        raise TrackerNotConfiguredError(
            f"No Backlog.md project found in {self._root}. Run `backlog init`."
        )

    def _config(self) -> dict:
        backlog_dir = self._backlog_dir()
        for path in (self._root / "backlog.config.yml", backlog_dir / "config.yml"):
            if path.exists():
                return _read_yaml_file(path)
        return {}

    def _task_prefix(self) -> str:
        config = self._config()
        return str(config.get("taskPrefix") or config.get("task_prefix") or "task")

    def _default_status(self) -> str:
        config = self._config()
        return str(config.get("defaultStatus") or config.get("default_status") or DEFAULT_INITIAL_STATUS)

    def _active_status(self) -> str:
        if self.active_states:
            return self._status_from_config_list(self.active_states, 0)
        return self._default_status()

    def _terminal_status(self) -> str:
        if self.terminal_states:
            return self._status_from_config_list(self.terminal_states, 0)
        return "Done"

    def _create_status(self, initial_status: str | None) -> str:
        if initial_status and initial_status.strip().lower() != DEFAULT_INITIAL_STATUS.lower():
            return self._status_with_config_case(initial_status)
        return self._default_status()

    def _status_with_config_case(self, status: str) -> str:
        needle = status.strip().lower()
        configured = self._configured_status_case(status)
        if configured:
            return configured
        canonical = canonicalize_status(status)
        canonical_configured = self._configured_status_case(canonical)
        if canonical_configured:
            return canonical_configured
        if needle in {"to do", "todo", "deferred", "backlog", DEFAULT_INITIAL_STATUS.lower()}:
            return self._default_status()
        if canonical == OPEN:
            return self._status_from_config_list(self.active_states, 0)
        if canonical == IN_PROGRESS:
            configured = self._configured_status_case(IN_PROGRESS)
            if configured:
                return configured
            return IN_PROGRESS
        if canonical in {DONE, ARCHIVED}:
            return self._status_from_config_list(self.terminal_states, 0)
        return status

    def _status_from_config_list(
        self,
        statuses: list[str],
        index: int,
        *,
        fallback: str | None = None,
    ) -> str:
        if len(statuses) > index:
            status = statuses[index]
            return self._configured_status_case(status) or status
        return fallback or self._default_status()

    def _configured_status_case(self, status: str) -> str | None:
        needle = status_key(status)
        statuses = self._config().get("statuses") or []
        if isinstance(statuses, list):
            for configured in statuses:
                if status_key(str(configured)) == needle:
                    return str(configured)
        return None

    def _normalize_lookup_id(self, identifier: str) -> str:
        value = str(identifier).strip()
        if value.isdigit():
            value = f"{self._task_prefix()}-{value}"
        return value.lower()

    def _task_lock(self, identifier: str) -> threading.RLock:
        key = self._normalize_lookup_id(identifier)
        with self._task_locks_guard:
            lock = self._task_locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._task_locks[key] = lock
            return lock

    def _run_backlog_task_edit(self, args: list[str], identifier: str) -> str:
        """Run a Backlog task edit while preserving non-CLI frontmatter."""
        custom_meta = self._custom_frontmatter_snapshot(identifier)
        result = self._run_backlog(args)
        if custom_meta:
            self._restore_missing_frontmatter(identifier, custom_meta)
        return result

    def _custom_frontmatter_snapshot(self, identifier: str) -> dict:
        path = self._task_path_for(identifier)
        if not path:
            return {}
        try:
            meta, _body = _read_markdown_frontmatter(path)
        except TrackerError:
            return {}
        snapshot = {
            key: value
            for key, value in meta.items()
            if str(key) not in _BACKLOG_CLI_OWNED_FRONTMATTER
        }
        # The Backlog CLI only accepts named priority strings (high/medium/low)
        # and silently drops numeric values such as ``priority: 0`` (P0) when it
        # rewrites frontmatter during any edit — even a status-only update.
        # Include an existing numeric priority in the snapshot so that
        # ``_restore_missing_frontmatter`` can put it back if the CLI drops it.
        # This covers reopen_issue, close_issue, and status-only update_issue
        # calls (e.g. the restart-recovery path). (TASK-465.6)
        if isinstance(meta.get("priority"), int):
            snapshot["priority"] = meta["priority"]
        return snapshot

    def _restore_missing_frontmatter(
        self, identifier: str, custom_meta: dict,
    ) -> None:
        path = self._task_path_for(identifier)
        if not path:
            return
        try:
            meta, body = _read_markdown_frontmatter(path)
        except TrackerError as exc:
            logger.warning(
                "Backlog.md: could not restore custom frontmatter for %s: %s",
                identifier,
                exc,
            )
            return
        restored = False
        for key, value in custom_meta.items():
            if key not in meta:
                meta[key] = value
                restored = True
        if restored:
            _write_markdown_frontmatter(path, meta, body)


    def _run_backlog(
        self, args: list[str], *, timeout: float | None = None,
    ) -> str:
        """Run a backlog command and return stdout."""
        if shutil.which("backlog") is None:
            raise TrackerError("backlog command not found. Is Backlog.md installed?")
        cmd = ["backlog"] + args
        effective_timeout = (
            timeout if timeout is not None else _resolve_backlog_timeout()
        )
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=str(self._root),
            )
        except FileNotFoundError:
            raise TrackerError("backlog command not found. Is Backlog.md installed?")
        except subprocess.TimeoutExpired:
            raise TrackerTimeoutError(
                f"backlog command timed out: {' '.join(cmd)}"
            )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            if "no backlog.md project found" in stderr.lower():
                raise TrackerNotConfiguredError(stderr)
            raise TrackerError(
                f"backlog command failed (exit {result.returncode}): {stderr}"
            )
        # CLI invocations are mutations (create/edit/archive); reads go
        # through direct file I/O. Drop the cached snapshot so the next
        # read reflects this write.
        self.invalidate_read_cache()
        return result.stdout


def _read_yaml_file(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TrackerError(f"Cannot read {path}: {exc}")
    except yaml.YAMLError as exc:
        raise TrackerError(f"Cannot parse YAML {path}: {exc}")
    return data if isinstance(data, dict) else {}


def _read_markdown_frontmatter(path: Path) -> tuple[dict, str]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TrackerError(f"Cannot read {path}: {exc}")
    if not content.startswith("---\n"):
        raise TrackerError(f"Missing YAML front matter in {path}")
    end = content.find("\n---", 4)
    if end == -1:
        raise TrackerError(f"Unterminated YAML front matter in {path}")
    frontmatter = content[4:end]
    body_start = end + len("\n---")
    if content[body_start:body_start + 1] == "\n":
        body_start += 1
    try:
        meta = yaml.safe_load(frontmatter) or {}
    except yaml.YAMLError as exc:
        raise TrackerError(f"Cannot parse task metadata {path}: {exc}")
    if not isinstance(meta, dict):
        meta = {}
    return meta, content[body_start:]


def _write_markdown_frontmatter(path: Path, meta: dict, body: str) -> None:
    payload = yaml.safe_dump(meta, sort_keys=False, allow_unicode=False)
    try:
        path.write_text(f"---\n{payload}---\n{body}", encoding="utf-8")
    except OSError as exc:
        raise TrackerError(f"Cannot write {path}: {exc}")


def _extract_backlog_section(body: str, section: str) -> str | None:
    begin = f"<!-- SECTION:{section}:BEGIN -->"
    end = f"<!-- SECTION:{section}:END -->"
    start = body.find(begin)
    if start == -1:
        return None
    start += len(begin)
    stop = body.find(end, start)
    if stop == -1:
        return None
    return body[start:stop].strip() or None


def _looks_like_epic_task(title: str, description: str | None) -> bool:
    """Detect Backlog tasks that clearly describe themselves as epics.

    This is a defensive fallback for manually-created Backlog.md tasks that
    missed the explicit ``epic`` label/type but were written as epic rollups.
    It intentionally avoids treating every parent-with-children as an epic
    because oompah also supports decomposed non-epic parent tasks.
    """
    title_key = title.strip().lower()
    if title_key.startswith(("epic:", "epic -", "epic ")):
        return True
    text = (description or "").strip()
    if not text:
        return False
    return bool(re.search(r"(?im)^\s*epic\s+(?:for|to|covering)\b", text[:1000]))


def _parse_backlog_comments(body: str) -> list[dict]:
    comments: list[dict] = []
    pattern = re.compile(
        r"<!-- COMMENT:BEGIN -->\n(.*?)\n<!-- COMMENT:END -->",
        re.DOTALL,
    )
    for match in pattern.finditer(body):
        block = match.group(1)
        header, _, text = block.partition("\n\n")
        fields: dict[str, str] = {}
        for line in header.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.strip()
        comments.append({
            "id": fields.get("index"),
            "author": fields.get("author"),
            "created_at": fields.get("created"),
            "text": text.strip(),
        })
    return comments


def _append_backlog_comment(
    body: str,
    *,
    text: str,
    author: str,
    created: str,
) -> str:
    comment = _format_backlog_comment(
        index=_next_backlog_comment_index(body),
        author=author,
        created=created,
        text=_sanitize_backlog_comment_text(text),
    )
    end_marker = "<!-- COMMENTS:END -->"
    end_pos = body.find(end_marker)
    if end_pos >= 0:
        prefix = body[:end_pos]
        suffix = body[end_pos:]
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        return f"{prefix}{comment}{suffix}"

    comments_section = (
        "\n\n## Comments\n"
        "<!-- COMMENTS:BEGIN -->\n"
        f"{comment}"
        "<!-- COMMENTS:END -->\n"
    )
    if not body:
        return comments_section.lstrip()
    return body.rstrip("\n") + comments_section


def _format_backlog_comment(
    *,
    index: int,
    author: str,
    created: str,
    text: str,
) -> str:
    return (
        "<!-- COMMENT:BEGIN -->\n"
        f"index: {index}\n"
        f"author: {author}\n"
        f"created: {created}\n\n"
        f"{text}\n"
        "<!-- COMMENT:END -->\n"
    )


def _next_backlog_comment_index(body: str) -> int:
    indexes = [
        int(match.group(1))
        for match in re.finditer(r"^index:\s*(\d+)\s*$", body, re.MULTILINE)
    ]
    if indexes:
        return max(indexes) + 1
    return len(_parse_backlog_comments(body)) + 1


def _format_backlog_comment_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def _backlog_comment_field(value, *, fallback: str) -> str:
    field = re.sub(r"[\r\n]+", " ", str(value or "")).strip()
    return field or fallback


def _sanitize_backlog_comment_text(text: str) -> str:
    cleaned = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    for marker in (
        "<!-- COMMENT:BEGIN -->",
        "<!-- COMMENT:END -->",
        "<!-- COMMENTS:BEGIN -->",
        "<!-- COMMENTS:END -->",
    ):
        escaped_marker = marker.replace("<!--", "<!-- ").replace("-->", " -->")
        cleaned = cleaned.replace(marker, escaped_marker)
    return cleaned


def _is_task_not_found_error(exc: TrackerError) -> bool:
    """Return True when the error signals that the backlog CLI could not find the task.

    The Backlog CLI exits with code 1 and prints "Task <ID> not found." to
    stdout when the requested task does not exist in its search path (e.g. the
    task was already moved to ``completed/``).  We detect this pattern so that
    callers can fall back to direct file editing.
    """
    return "not found" in str(exc).lower()


def _parse_backlog_plain_identifier(output: str) -> str | None:
    match = re.search(r"\bTask\s+([A-Za-z]+-\d+(?:\.\d+)*)\s+-", output)
    if match:
        return match.group(1)
    match = re.search(r"/(?:task|Task)-(\d+(?:\.\d+)*)\s+-", output)
    if match:
        return f"TASK-{match.group(1)}"
    return None


def _identifier_from_task_record(meta: dict, path: Path, prefix: str) -> str:
    raw_id = str(meta.get("id") or "").strip()
    if _is_valid_task_identifier(raw_id, prefix):
        return _canonical_task_identifier(raw_id, prefix)
    return _id_from_task_path(path, prefix)


def _title_from_task_record(meta: dict, path: Path, prefix: str) -> str:
    raw_title = str(meta.get("title") or "").strip()
    if raw_title:
        return raw_title
    return _title_from_task_path(path, prefix)


def _is_valid_task_identifier(identifier: str, prefix: str) -> bool:
    return re.match(
        rf"^{re.escape(prefix)}-\d+(?:\.\d+)*$",
        str(identifier).strip(),
        re.I,
    ) is not None


def _canonical_task_identifier(identifier: str, prefix: str) -> str:
    match = re.match(
        rf"^{re.escape(prefix)}-(\d+(?:\.\d+)*)$",
        str(identifier).strip(),
        re.I,
    )
    if match:
        return f"{prefix.upper()}-{match.group(1)}"
    return str(identifier).strip()


def _id_from_task_path(path: Path, prefix: str) -> str:
    match = re.match(rf"{re.escape(prefix)}-(\d+(?:\.\d+)*)\b", path.stem, re.I)
    if match:
        return f"{prefix.upper()}-{match.group(1)}"
    return path.stem


def _title_from_task_path(path: Path, prefix: str) -> str:
    match = re.match(
        rf"{re.escape(prefix)}-\d+(?:\.\d+)*\s+-\s+(.+)$",
        path.stem,
        re.I,
    )
    if not match:
        return ""
    return match.group(1).replace("-", " ").strip()


def _string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v)]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _backlog_priority_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raw = str(value).strip().lower()
    if raw.isdigit():
        return int(raw)
    if raw.startswith("p") and raw[1:].isdigit():
        return int(raw[1:])
    return _BACKLOG_PRIORITY_TO_INT.get(raw)


def _backlog_cli_priority_name(value) -> str | None:
    """Return the priority name accepted by Backlog.md's CLI, if any."""
    if value is None:
        return None
    if isinstance(value, int):
        if value == 0:
            return None
        return _INT_TO_BACKLOG_CLI_PRIORITY.get(value)
    raw = str(value).strip().lower()
    if raw.isdigit():
        numeric = int(raw)
        if numeric == 0:
            return None
        return _INT_TO_BACKLOG_CLI_PRIORITY.get(numeric)
    if raw.startswith("p") and raw[1:].isdigit():
        numeric = int(raw[1:])
        if numeric == 0:
            return None
        return _INT_TO_BACKLOG_CLI_PRIORITY.get(numeric)
    if raw == "critical":
        return None
    if raw in _BACKLOG_PRIORITY_TO_INT:
        return "medium" if raw == "normal" else raw
    return None


def _backlog_direct_priority_value(value) -> int | None:
    """Return a priority value that must be written directly to frontmatter.

    Backlog.md's CLI only supports ``high``, ``medium``, and ``low``. Oompah
    needs P0 to be distinct from P1, so numeric zero is oompah-owned metadata
    written directly to the task file after any CLI operation completes.
    """
    priority = _backlog_priority_int(value)
    if priority == 0:
        return 0
    return None


def _parse_backlog_timestamp(value) -> datetime | None:
    dt = _parse_timestamp(value)
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _issue_type_from_labels(labels: list[str]) -> str:
    for label in labels:
        lower = label.lower()
        if lower in {"bug", "feature", "task", "epic", "chore"}:
            return lower
    return "task"


def _parse_timestamp(value) -> datetime | None:
    """Parse an ISO-8601 timestamp string."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        s = str(value)
        # Handle various ISO formats
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

#: Type alias for a tracker factory callable.
#: A factory takes ``active_states``, ``terminal_states``, and an optional
#: ``cwd`` keyword argument and returns a :class:`TrackerProtocol` instance.
#: Additional keyword arguments may be accepted for future extensibility.
TrackerFactory = Callable[..., TrackerProtocol]


def _backlog_md_factory(
    active_states: list[str],
    terminal_states: list[str],
    cwd: str | None = None,
    **kwargs: object,
) -> BacklogMdTracker:
    """Factory for the Backlog.md tracker adapter."""
    return BacklogMdTracker(
        active_states=active_states,
        terminal_states=terminal_states,
        cwd=cwd,
    )


#: Adapter registry — maps a normalised ``tracker.kind`` string to a
#: :data:`TrackerFactory` callable.
#:
#: The orchestrator uses this registry to instantiate the correct tracker for
#: each project.  Unknown kinds are rejected by
#: :func:`oompah.config.validate_dispatch_config` with a descriptive error that
#: lists the registered adapters.
#:
#: Third-party adapters can extend this dict at import time::
#:
#:     from oompah.tracker import ADAPTER_REGISTRY
#:     ADAPTER_REGISTRY["my_tracker"] = my_factory_function
def _github_issues_registry_factory(**kwargs) -> "TrackerProtocol":
    """Lazy-import wrapper so github_tracker is only loaded when needed."""
    from oompah.github_tracker import _github_issues_factory
    return _github_issues_factory(**kwargs)


ADAPTER_REGISTRY: dict[str, TrackerFactory] = {
    "backlog_md": _backlog_md_factory,
    "github_issues": _github_issues_registry_factory,
}
