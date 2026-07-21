"""Shared tracker protocol, registry, and Markdown helper functions."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Callable, Protocol, runtime_checkable

from oompah.models import Issue

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")

logger = logging.getLogger(__name__)

DEFAULT_INITIAL_STATUS = "Backlog"

_PRIORITY_TO_INT = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "normal": 2,
    "low": 3,
    "backlog": 4,
}


def _sanitize_identifier(identifier: str) -> str:
    """Replace characters that are unsafe for branch/path names."""
    return _SAFE_CHARS.sub("_", identifier)


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


class TrackerAuthError(TrackerError):
    """Raised when tracker authentication fails (e.g. HTTP 401 or 403).

    A ``TrackerAuthError`` is a non-transient, non-retriable failure: the
    configured credential does not have the access required to perform the
    operation.  Callers should surface this as an actionable operator alert
    rather than silently retrying.
    """


class TrackerNotConfiguredError(TrackerError):
    """Raised when a tracker backend is not configured for a project."""


class StateBranchMissingError(TrackerError):
    """Raised when a state branch does not exist and needs bootstrapping.

    This is a *configuration* error, not a runtime fault.  The project has
    ``state_branch_enabled=True`` but the bootstrap or migration flow has
    never been run to create the state branch.  The server degrades
    gracefully for this project (returning no issues) and logs a WARNING
    rather than an ERROR so that ``error_watcher`` is not triggered.
    """


class TrackerTimeoutError(TrackerError):
    """Raised when a tracker operation exceeds its timeout."""


# Backward-compatible alias — orchestrator.py and tests still reference this
# name; the canonical class is StateBranchMissingError (added by OOMPAH-316).
TrackerStateBranchMissingError = StateBranchMissingError


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
            os.path.join(directory, "manifest.json"),
            "w",
            encoding="utf-8",
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
    """Common interface that every oompah tracker adapter must satisfy."""

    def fetch_candidate_issues(self) -> list[Issue]:
        """Return issues in active dispatchable states, sorted for dispatch."""
        ...

    def fetch_all_issues(self) -> list[Issue]:
        """Return all issues regardless of state."""
        ...

    def fetch_all_issues_enriched(self) -> list[Issue]:
        """Return all issues with full detail."""
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
        """Return backend-specific memory key/value pairs."""
        ...

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
        """Move an issue to a terminal state."""
        ...

    def reopen_issue(self, identifier: str) -> None:
        """Move an issue back to an active state."""
        ...

    def archive_issue(self, identifier: str) -> None:
        """Archive an issue."""
        ...

    def mark_needs_human(
        self,
        identifier: str,
        comment: str,
        author: str = "oompah",
    ) -> None:
        """Move an issue to Needs Human and post an actionable comment."""
        ...

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        """Append a comment to an issue and return the comment dict."""
        ...

    def add_label(self, identifier: str, label: str) -> None:
        """Add a label to an issue."""
        ...

    def remove_label(self, identifier: str, label: str) -> None:
        """Remove a label from an issue."""
        ...

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        """Link a child issue to a parent issue."""
        ...

    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        """Record that blocked_id depends on blocker_id."""
        ...

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

    def get_metadata(self, identifier: str) -> dict[str, object]:
        """Return oompah-owned metadata fields for an issue."""
        ...

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        """Set one oompah-owned metadata field on an issue."""
        ...

    def is_archived(self, issue: Issue) -> bool:
        """Return True when the issue should be considered archived."""
        ...

    def invalidate_read_cache(self) -> None:
        """Invalidate cached reads so the next fetch returns fresh data."""
        ...


def parse_tracker_comments(body: str) -> list[dict]:
    comments: list[dict] = []

    section_pattern = re.compile(
        r"<!-- COMMENTS:BEGIN -->\n?(.*?)\n?<!-- COMMENTS:END -->",
        re.DOTALL,
    )
    sections = [match.group(1) for match in section_pattern.finditer(body or "")]
    if sections:
        for section in sections:
            comments.extend(_parse_comments_section(section, len(comments)))
        return comments

    block_pattern = re.compile(
        r"<!-- COMMENT:BEGIN -->\n(.*?)\n<!-- COMMENT:END -->",
        re.DOTALL,
    )
    for match in block_pattern.finditer(body or ""):
        parsed = _parse_comment_block(match.group(1), len(comments))
        if parsed:
            comments.append(parsed)
    return comments


def _parse_comments_section(section: str, existing_count: int = 0) -> list[dict]:
    comments: list[dict] = []
    lines = section.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if line == "<!-- COMMENT:BEGIN -->":
            block_lines: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() != "<!-- COMMENT:END -->":
                block_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            parsed = _parse_comment_block(
                "\n".join(block_lines),
                existing_count + len(comments),
            )
            if parsed:
                comments.append(parsed)
            continue

        parsed, next_index = _parse_structured_comment(
            lines,
            i,
            existing_count + len(comments),
        )
        if parsed:
            comments.append(parsed)
            i = next_index
            continue
        i += 1

    return comments


def _parse_comment_block(block: str, existing_count: int = 0) -> dict | None:
    header, _, text = block.partition("\n\n")
    fields: dict[str, str] = {}
    for line in header.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip().lower()] = value.strip()
    comment_text = text.strip()
    if not fields and not comment_text:
        return None
    return {
        "id": fields.get("index") or str(existing_count + 1),
        "author": fields.get("author"),
        "created_at": fields.get("created"),
        "text": comment_text,
    }


def _parse_structured_comment(
    lines: list[str],
    start: int,
    existing_count: int = 0,
) -> tuple[dict | None, int]:
    fields: dict[str, str] = {}
    i = start
    while i < len(lines):
        line = lines[i]
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if not sep or not key.strip():
            return None, start + 1
        fields[key.strip().lower()] = value.strip()
        i += 1

    if i >= len(lines) or lines[i].strip() != "---" or not fields:
        return None, start + 1

    i += 1
    text_lines: list[str] = []
    while i < len(lines) and lines[i].strip() != "---":
        text_lines.append(lines[i])
        i += 1
    if i >= len(lines):
        return None, start + 1

    i += 1
    return {
        "id": fields.get("index") or str(existing_count + 1),
        "author": fields.get("author"),
        "created_at": fields.get("created"),
        "text": "\n".join(text_lines).strip(),
    }, i


def append_tracker_comment(
    body: str,
    *,
    text: str,
    author: str,
    created: str,
) -> str:
    comment = format_tracker_comment(
        index=_next_comment_index(body),
        author=author,
        created=created,
        text=sanitize_comment_text(text),
    )
    end_marker = "<!-- COMMENTS:END -->"
    end_pos = (body or "").find(end_marker)
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


def format_tracker_comment(
    *,
    index: int,
    author: str,
    created: str,
    text: str,
) -> str:
    return f"author: {author}\ncreated: {created}\n---\n{text}\n---\n"


def _next_comment_index(body: str) -> int:
    indexes = [
        int(match.group(1))
        for match in re.finditer(r"^index:\s*(\d+)\s*$", body or "", re.MULTILINE)
    ]
    if indexes:
        return max(indexes) + 1
    return len(parse_tracker_comments(body or "")) + 1


def format_comment_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def comment_author_field(value, *, fallback: str) -> str:
    field = re.sub(r"[\r\n]+", " ", str(value or "")).strip()
    return field or fallback


def sanitize_comment_text(text: str) -> str:
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


def _string_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if str(v)]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def normalize_priority_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raw = str(value).strip().lower()
    if raw.isdigit():
        return int(raw)
    if raw.startswith("p") and raw[1:].isdigit():
        return int(raw[1:])
    return _PRIORITY_TO_INT.get(raw)


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
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


TrackerFactory = Callable[..., TrackerProtocol]


def _github_issues_registry_factory(**kwargs) -> TrackerProtocol:
    """Lazy-import wrapper so github_tracker is only loaded when needed."""
    from oompah.github_tracker import _github_issues_factory

    return _github_issues_factory(**kwargs)


def _oompah_md_registry_factory(**kwargs) -> TrackerProtocol:
    """Lazy-import wrapper for the native oompah Markdown tracker."""
    from oompah.oompah_md_tracker import _oompah_md_factory

    return _oompah_md_factory(**kwargs)


ADAPTER_REGISTRY: dict[str, TrackerFactory] = {
    "github_issues": _github_issues_registry_factory,
    "github-issues": _github_issues_registry_factory,
    "oompah_md": _oompah_md_registry_factory,
    "oompah.md": _oompah_md_registry_factory,
    "oompah": _oompah_md_registry_factory,
}
