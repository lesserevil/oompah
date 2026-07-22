"""GitLab Issues REST adapter.

The adapter deliberately uses GitLab's v4 REST API directly rather than a
third-party SDK.  This keeps self-hosted GitLab support to a base URL and a
personal/project access token, and gives callers the same ``TrackerProtocol``
contract as the GitHub adapter.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any
from urllib.parse import quote

import httpx

from oompah.models import BlockerRef, Issue
from oompah.statuses import ARCHIVED, DONE, NEEDS_HUMAN, canonicalize_status
from oompah.tracker import (
    TrackerAuthError,
    TrackerError,
    TrackerTimeoutError,
    _issue_type_from_labels,
    _parse_timestamp,
    _sort_issues_for_dispatch,
    normalize_priority_int,
)

logger = logging.getLogger(__name__)
_DEFAULT_TIMEOUT_S = 30.0
_MAX_RETRIES = 3
_STATUS_PREFIX = "oompah:status:"
_IDENTIFIER_RE = re.compile(r"^(?P<project>[^#\s]+)#(?P<iid>[1-9][0-9]*)$")


class GitLabIdentifierError(ValueError):
    """Raised when an issue identifier is not globally qualified."""


class GitLabIdentifier:
    """Fully-qualified GitLab issue identity: ``group/subgroup/project#iid``."""

    def __init__(self, project: str, iid: int) -> None:
        if not project or project.startswith("/") or project.endswith("/"):
            raise GitLabIdentifierError(
                "project path must be a non-empty namespace/project"
            )
        if iid < 1:
            raise GitLabIdentifierError("issue iid must be a positive integer")
        self.project, self.iid = project, iid

    @property
    def canonical(self) -> str:
        return f"{self.project}#{self.iid}"

    @property
    def display(self) -> str:
        return f"{self.project.rsplit('/', 1)[-1]}#{self.iid}"

    def __str__(self) -> str:
        return self.canonical


def parse_gitlab_identifier(value: str) -> GitLabIdentifier:
    match = _IDENTIFIER_RE.fullmatch((value or "").strip())
    if not match:
        raise GitLabIdentifierError(
            "GitLab issue identifiers must be fully qualified as "
            "namespace/project#<iid>; bare issue numbers are ambiguous."
        )
    return GitLabIdentifier(match.group("project"), int(match.group("iid")))


def _status_label(status: str) -> str:
    return _STATUS_PREFIX + re.sub(r"[^a-z0-9]+", "-", status.lower()).strip("-")


def _status_from_labels(labels: list[str], gitlab_state: str) -> str:
    for label in labels:
        if label.startswith(_STATUS_PREFIX):
            return canonicalize_status(label[len(_STATUS_PREFIX) :].replace("-", " "))
    return DONE if gitlab_state == "closed" else "Open"


_DESCRIPTION_METADATA_RE = re.compile(
    r"<!--\s*oompah:metadata\s*\n(.*?)\n\s*-->",
    re.DOTALL,
)


def _parse_description_metadata(description: str | None) -> dict[str, Any]:
    """Extract the structured oompah metadata block from a GitLab issue description.

    Returns an empty dict when *description* is *None* or contains no
    ``<!-- oompah:metadata … -->`` block.
    """
    if not description:
        return {}
    m = _DESCRIPTION_METADATA_RE.search(description)
    if not m:
        return {}
    try:
        return json.loads(m.group(1).strip())
    except (json.JSONDecodeError, Exception):
        return {}


def _update_description_metadata(
    description: str | None, meta: dict[str, Any]
) -> str:
    """Insert or replace the oompah metadata block in a GitLab issue description.

    The visible description text before the metadata block is preserved
    unchanged.  When no existing block is found the block is appended with a
    double newline separator.
    """
    description = description or ""
    meta_json = json.dumps(meta, indent=2, sort_keys=True)
    meta_block = f"<!-- oompah:metadata\n{meta_json}\n-->"
    m = _DESCRIPTION_METADATA_RE.search(description)
    if m:
        return description[: m.start()] + meta_block + description[m.end() :]
    separator = "\n\n" if description.rstrip("\n") else ""
    return description.rstrip("\n") + separator + meta_block


class GitLabClient:
    """Small retrying GitLab REST transport with normalized errors."""

    def __init__(
        self, *, base_url: str, token: str, client: httpx.Client | None = None
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/api/v4"
        self.token = token
        self._client = client or httpx.Client(timeout=_DEFAULT_TIMEOUT_S)

    def request(
        self, method: str, path: str, **kwargs: Any
    ) -> tuple[Any, httpx.Headers]:
        url = self.base_url + path
        headers = dict(kwargs.pop("headers", {}))
        headers["PRIVATE-TOKEN"] = self.token
        timeout = kwargs.pop(
            "timeout", float(os.getenv("OOMPAH_GITLAB_API_TIMEOUT", _DEFAULT_TIMEOUT_S))
        )
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.request(
                    method, url, headers=headers, timeout=timeout, **kwargs
                )
            except httpx.TimeoutException as exc:
                if attempt + 1 == _MAX_RETRIES:
                    raise TrackerTimeoutError(
                        f"GitLab request timed out: {method} {path}"
                    ) from exc
            except httpx.HTTPError as exc:
                if attempt + 1 == _MAX_RETRIES:
                    raise TrackerError(
                        f"GitLab request failed: {method} {path}: {exc}"
                    ) from exc
            else:
                if response.status_code in (401, 403):
                    raise TrackerAuthError(
                        f"GitLab authentication/authorization failed ({response.status_code})"
                    )
                if response.status_code == 404:
                    raise TrackerError(f"GitLab API returned 404 for {path}")
                if response.status_code < 500 and response.status_code != 429:
                    if not response.is_success:
                        raise TrackerError(
                            f"GitLab API returned {response.status_code}: {response.text[:500]}"
                        )
                    try:
                        return response.json(), response.headers
                    except ValueError:
                        return None, response.headers
                if attempt + 1 == _MAX_RETRIES:
                    raise TrackerError(
                        f"GitLab API returned {response.status_code}: {response.text[:500]}"
                    )
            time.sleep(min(0.1 * (2**attempt), 1.0))
        raise AssertionError("unreachable")

    def paginated(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> list[Any]:
        result: list[Any] = []
        query = dict(params or {})
        query.setdefault("per_page", 100)
        query.setdefault("page", 1)
        while True:
            data, headers = self.request("GET", path, params=query)
            if isinstance(data, list):
                result.extend(data)
            next_page = headers.get("X-Next-Page", "")
            if not next_page:
                return result
            query["page"] = int(next_page)


class GitLabIssueTracker:
    """GitLab-backed implementation of :class:`TrackerProtocol`."""

    def __init__(
        self,
        *,
        project: str,
        active_states: list[str],
        terminal_states: list[str],
        access_token: str | None = None,
        base_url: str | None = None,
        client: GitLabClient | None = None,
        cwd: str | None = None,
        **_: Any,
    ) -> None:
        self.project = project.strip("/")
        if not self.project:
            raise TrackerError("GitLab Issues tracker requires a project path")
        token = (
            access_token
            or os.getenv("OOMPAH_GITLAB_TOKEN")
            or os.getenv("GITLAB_TOKEN")
        )
        if not token and client is None:
            raise TrackerAuthError(
                "GitLab Issues tracker requires OOMPAH_GITLAB_TOKEN or GITLAB_TOKEN"
            )
        self.active_states, self.terminal_states = (
            list(active_states),
            list(terminal_states),
        )
        self._client = client or GitLabClient(
            base_url=base_url
            or os.getenv("OOMPAH_GITLAB_BASE_URL", "https://gitlab.com"),
            token=token or "",
        )

    @property
    def _project_path(self) -> str:
        return "/projects/" + quote(self.project, safe="")

    def _issue_path(self, iid: int, suffix: str = "") -> str:
        return f"{self._project_path}/issues/{iid}{suffix}"

    def parse_identifier(self, identifier: str) -> GitLabIdentifier:
        try:
            parsed = parse_gitlab_identifier(identifier)
        except GitLabIdentifierError as exc:
            raise TrackerError(str(exc)) from exc
        if parsed.project != self.project:
            raise TrackerError(
                f"issue {identifier!r} belongs to a different GitLab project"
            )
        return parsed

    def _issue(self, data: dict[str, Any]) -> Issue:
        labels = [str(label) for label in data.get("labels") or []]
        iid = int(data["iid"])
        status = _status_from_labels(labels, str(data.get("state", "opened")))
        parent = next(
            (
                label[len("parent:") :]
                for label in labels
                if label.startswith("parent:")
            ),
            None,
        )
        blockers = [
            BlockerRef(identifier=label[len("blocked-by:") :])
            for label in labels
            if label.startswith("blocked-by:")
        ]
        return Issue(
            id=f"{self.project}#{iid}",
            identifier=f"{self.project}#{iid}",
            display_identifier=f"{self.project.rsplit('/', 1)[-1]}#{iid}",
            title=data.get("title") or "",
            description=data.get("description") or None,
            state=status,
            priority=next(
                (
                    normalize_priority_int(x[len("priority:") :])
                    for x in labels
                    if x.startswith("priority:")
                ),
                None,
            ),
            issue_type=_issue_type_from_labels(labels),
            labels=labels,
            parent_id=parent,
            blocked_by=blockers,
            url=data.get("web_url"),
            provider_url=data.get("web_url"),
            created_at=_parse_timestamp(data.get("created_at")),
            updated_at=_parse_timestamp(data.get("updated_at")),
            closed_at=_parse_timestamp(data.get("closed_at")),
            tracker_kind="gitlab_issues",
            tracker_owner=self.project.rsplit("/", 1)[0]
            if "/" in self.project
            else None,
            tracker_repo=self.project.rsplit("/", 1)[-1],
            issue_number=str(iid),
            requestor_login=(data.get("author") or {}).get("username"),
        )

    def _list(self, **params: Any) -> list[Issue]:
        return [
            self._issue(row)
            for row in self._client.paginated(
                f"{self._project_path}/issues", params=params
            )
            if isinstance(row, dict)
        ]

    def _labels(self, iid: int) -> list[str]:
        data, _ = self._client.request("GET", self._issue_path(iid))
        return [str(x) for x in (data or {}).get("labels", [])]

    def _edit(self, iid: int, **data: Any) -> None:
        self._client.request("PUT", self._issue_path(iid), json=data)

    def _replace_status(
        self, iid: int, status: str, *, close: bool | None = None
    ) -> None:
        labels = [x for x in self._labels(iid) if not x.startswith(_STATUS_PREFIX)] + [
            _status_label(status)
        ]
        payload: dict[str, Any] = {"labels": ",".join(labels)}
        if close is not None:
            payload["state_event"] = "close" if close else "reopen"
        self._edit(iid, **payload)

    def fetch_candidate_issues(self) -> list[Issue]:
        active = {canonicalize_status(s) for s in self.active_states}
        return _sort_issues_for_dispatch(
            [
                issue
                for issue in self._list(state="opened")
                if canonicalize_status(issue.state) in active
            ]
        )

    def fetch_all_issues(self) -> list[Issue]:
        return self._list(state="all")

    def fetch_all_issues_enriched(self) -> list[Issue]:
        return self.fetch_all_issues()

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        try:
            parsed = self.parse_identifier(identifier)
            data, _ = self._client.request("GET", self._issue_path(parsed.iid))
            return self._issue(data)
        except TrackerError as exc:
            if "404" in str(exc):
                return None
            raise

    def fetch_children(self, epic_id: str) -> list[Issue]:
        try:
            parent = self.parse_identifier(epic_id)
        except TrackerError:
            return []
        return [
            issue
            for issue in self.fetch_all_issues()
            if issue.parent_id in {epic_id, str(parent.iid)}
            or f"parent:{parent.iid}" in issue.labels
        ]

    def fetch_comments(self, identifier: str) -> list[dict]:
        try:
            parsed = self.parse_identifier(identifier)
            notes = self._client.paginated(self._issue_path(parsed.iid, "/notes"))
        except TrackerError:
            return []
        return [
            {
                **note,
                "author": (note.get("author") or {}).get("username", ""),
                "text": note.get("body", ""),
            }
            for note in notes
            if isinstance(note, dict) and not note.get("system")
        ]

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        wanted = {canonicalize_status(s) for s in state_names}
        return [
            x for x in self.fetch_all_issues() if canonicalize_status(x.state) in wanted
        ]

    def fetch_issues_by_labels(
        self, labels: list[str], *, states: list[str] | None = None
    ) -> list[Issue]:
        issues = (
            self.fetch_all_issues()
            if states is None
            else self.fetch_issues_by_states(states)
        )
        return [x for x in issues if set(labels).issubset(x.labels)]

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        return [
            x for x in (self.fetch_issue_detail(i) for i in issue_ids) if x is not None
        ]

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
        all_labels = list(labels or []) + [
            issue_type,
            _status_label(
                initial_status
                or (self.active_states[0] if self.active_states else "Open")
            ),
        ]
        if priority is not None:
            all_labels.append(f"priority:{priority}")
        if parent:
            parent_id = self.parse_identifier(parent)
            all_labels.append(f"parent:{parent_id.iid}")
        data, _ = self._client.request(
            "POST",
            f"{self._project_path}/issues",
            json={
                "title": title,
                "description": description or "",
                "labels": ",".join(all_labels),
            },
        )
        return self._issue(data)

    def update_issue(self, identifier: str, **fields: str) -> None:
        iid = self.parse_identifier(identifier).iid
        payload: dict[str, Any] = {}
        for key in (
            "title",
            "description",
            "labels",
            "confidential",
            "due_date",
            "assignee_ids",
        ):
            if key in fields:
                payload[key] = fields[key]
        if "priority" in fields:
            labels = [x for x in self._labels(iid) if not x.startswith("priority:")] + [
                f"priority:{fields['priority']}"
            ]
            payload["labels"] = ",".join(labels)
        if "state" in fields:
            self._replace_status(
                iid,
                fields["state"],
                close=canonicalize_status(fields["state"]) in {DONE, ARCHIVED},
            )
            return
        if payload:
            self._edit(iid, **payload)

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        iid = self.parse_identifier(identifier).iid
        self._replace_status(iid, DONE, close=True)
        if reason:
            self.add_comment(identifier, reason)

    def reopen_issue(self, identifier: str) -> None:
        self._replace_status(
            self.parse_identifier(identifier).iid,
            self.active_states[0] if self.active_states else "Open",
            close=False,
        )

    def archive_issue(self, identifier: str) -> None:
        self._replace_status(
            self.parse_identifier(identifier).iid, ARCHIVED, close=True
        )

    def mark_needs_human(
        self, identifier: str, comment: str, author: str = "oompah"
    ) -> None:
        self._replace_status(self.parse_identifier(identifier).iid, NEEDS_HUMAN)
        self.add_comment(identifier, comment, author)

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        data, _ = self._client.request(
            "POST",
            self._issue_path(self.parse_identifier(identifier).iid, "/notes"),
            json={"body": text},
        )
        return {
            **data,
            "author": (data.get("author") or {}).get("username", author),
            "text": data.get("body", text),
        }

    def add_label(self, identifier: str, label: str) -> None:
        iid = self.parse_identifier(identifier).iid
        self._edit(iid, labels=",".join(self._labels(iid) + [label]))

    def remove_label(self, identifier: str, label: str) -> None:
        iid = self.parse_identifier(identifier).iid
        self._edit(iid, labels=",".join(x for x in self._labels(iid) if x != label))

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        child, parent = (
            self.parse_identifier(child_id),
            self.parse_identifier(parent_id),
        )
        self.add_label(child.canonical, f"parent:{parent.iid}")

    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        self.add_label(
            blocked_id, f"blocked-by:{self.parse_identifier(blocker_id).canonical}"
        )

    def fetch_attachments(self, identifier: str) -> list[dict]:
        """Return rich attachment records stored in the issue description metadata.

        Attachment records are read from the ``attachments`` key inside the
        hidden ``<!-- oompah:metadata … -->`` block in the issue description.
        An empty list is returned when no block is present or when the
        ``attachments`` key is absent.
        """
        meta = self.get_metadata(identifier)
        attachments = meta.get("oompah.attachments")
        if not isinstance(attachments, list):
            return []
        return [a for a in attachments if isinstance(a, dict)]

    def set_attachments(
        self,
        identifier: str,
        attachments: list[dict],
        *,
        project_root: str | None = None,
    ) -> None:
        """Replace the attachment records stored in the issue description metadata.

        Attachments are persisted in the hidden oompah metadata block in the
        issue description.  *project_root* is accepted for protocol
        compatibility but ignored here.
        """
        self.set_metadata_field(identifier, "oompah.attachments", list(attachments))

    def get_metadata(self, identifier: str) -> dict[str, object]:
        """Return oompah-owned metadata fields for an issue.

        Reads the hidden ``<!-- oompah:metadata … -->`` block from the issue
        description.  All keys are returned with an ``oompah.`` prefix so
        callers receive a namespace-consistent mapping.

        Returns an empty dict when the issue cannot be found, when the
        identifier is invalid, or when the description contains no metadata
        block.
        """
        try:
            parsed = self.parse_identifier(identifier)
            data, _ = self._client.request("GET", self._issue_path(parsed.iid))
        except TrackerError:
            return {}
        description = (data or {}).get("description") or ""
        meta = _parse_description_metadata(description)
        return {f"oompah.{k}": v for k, v in meta.items()}

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        """Set one oompah-owned metadata field on an issue.

        The value is written into the hidden ``<!-- oompah:metadata … -->``
        block in the issue description.  The ``oompah.`` prefix is stripped
        before writing so description JSON keys remain compact.

        Raises
        ------
        TrackerError
            When *key* does not start with ``oompah.``, or when the issue
            cannot be found.
        """
        if not key.startswith("oompah."):
            raise TrackerError(
                f"GitLab metadata key must start with 'oompah.': {key!r}"
            )
        body_key = key[len("oompah."):]
        parsed = self.parse_identifier(identifier)
        try:
            data, _ = self._client.request("GET", self._issue_path(parsed.iid))
        except TrackerError as exc:
            raise TrackerError(
                f"Cannot set metadata: issue not found: {identifier}"
            ) from exc
        current_desc = (data or {}).get("description") or ""
        meta = _parse_description_metadata(current_desc)
        meta[body_key] = value
        new_desc = _update_description_metadata(current_desc, meta)
        self._edit(parsed.iid, description=new_desc)

    def is_archived(self, issue: Issue) -> bool:
        return canonicalize_status(issue.state) == ARCHIVED

    def invalidate_read_cache(self) -> None:
        return None


def _gitlab_issues_factory(
    *,
    active_states: list[str],
    terminal_states: list[str],
    owner: str | None = None,
    repo: str | None = None,
    project: str | None = None,
    access_token: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> GitLabIssueTracker:
    resolved_project = (
        project
        or "/".join(x for x in (owner, repo) if x)
        or os.getenv("OOMPAH_GITLAB_TRACKER_PROJECT", "")
    )
    if not resolved_project:
        raise TrackerError(
            "GitLab Issues tracker requires project or OOMPAH_GITLAB_TRACKER_PROJECT"
        )
    return GitLabIssueTracker(
        project=resolved_project,
        active_states=active_states,
        terminal_states=terminal_states,
        access_token=access_token,
        base_url=base_url,
        **kwargs,
    )
