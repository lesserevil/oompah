"""Tests for importing GitLab issue intake into native oompah tasks."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from oompah.gitlab_intake_bridge import (
    _demote_h1_h2_headings,
    _native_description_for_gitlab_issue,
    ensure_native_issue_for_gitlab_issue,
    import_gitlab_comment_to_native,
    poll_gitlab_issue_intake_project,
    project_uses_gitlab_issue_intake,
    sync_gitlab_issue_intake_statuses_for_project,
)
from oompah.models import Issue, Project
from oompah.statuses import ARCHIVED, IN_VALIDATION, MERGED, PROPOSED
from oompah.tracker import TrackerAuthError


class FakeNativeTracker:
    def __init__(self):
        self.issues: dict[str, Issue] = {}
        self.metadata: dict[str, dict[str, object]] = {}
        self.comments: list[tuple[str, str, str]] = []
        self.update_calls: list[tuple[str, dict[str, object]]] = []
        self._next = 1

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
        identifier = f"TASK-{self._next}"
        self._next += 1
        issue = Issue(
            id=identifier,
            identifier=identifier,
            title=title,
            description=description,
            priority=priority,
            state=initial_status or "Backlog",
            issue_type=issue_type,
            labels=list(labels or []),
            parent_id=parent,
            tracker_kind="oompah_md",
        )
        self.issues[identifier] = issue
        return issue

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issues.get(identifier)

    def fetch_all_issues(self) -> list[Issue]:
        return list(self.issues.values())

    def fetch_all_issues_enriched(self) -> list[Issue]:
        return list(self.issues.values())

    def add_comment(self, identifier: str, text: str, author: str = "gitlab") -> None:
        self.comments.append((identifier, text, author))

    def update_issue(self, identifier: str, **fields: str) -> None:
        self.update_calls.append((identifier, fields))
        if identifier in self.issues:
            issue = self.issues[identifier]
            if "status" in fields:
                issue.state = fields["status"]

    def get_metadata(self, identifier: str) -> dict[str, object]:
        return self.metadata.get(identifier, {})

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        if identifier not in self.metadata:
            self.metadata[identifier] = {}
        self.metadata[identifier][key] = value

    def record_external_import(self, external_id: str, task_id: str) -> None:
        pass

    def find_imported_task_id_for_external(self, external_id: str) -> str | None:
        return None

    def list_corrupt_stubs(self) -> list[dict[str, str]]:
        return []


class FakeGitLabTracker:
    def __init__(self, issues: list[Issue] | None = None):
        self.issues_list = issues or []
        self.comments_added: list[tuple[str, str, str]] = []
        self.issues_updated: list[tuple[str, dict[str, object]]] = []
        self.metadata: dict[str, dict[str, object]] = {}

    def fetch_all_issues(self) -> list[Issue]:
        return self.issues_list

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        for issue in self.issues_list:
            if issue.identifier == identifier:
                return issue
        return None

    def fetch_comments(self, identifier: str) -> list[dict]:
        return []

    def add_comment(self, identifier: str, text: str, author: str = "gitlab") -> None:
        self.comments_added.append((identifier, text, author))

    def update_issue(self, identifier: str, **fields: object) -> None:
        self.issues_updated.append((identifier, fields))

    def get_metadata(self, identifier: str) -> dict[str, object]:
        return self.metadata.get(identifier, {})

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        if identifier not in self.metadata:
            self.metadata[identifier] = {}
        self.metadata[identifier][key] = value


def test_project_uses_gitlab_issue_intake_requires_gitlab_forge_kind():
    """GitLab intake requires explicit forge_kind check."""
    project = Project(
        id="p1",
        name="test",
        repo_url="https://gitlab.com/test/test.git",
        repo_path="/tmp/test",
        tracker_kind="oompah_md",
        github_issue_intake_enabled=True,
        forge_kind="github",  # Wrong forge kind
    )
    assert not project_uses_gitlab_issue_intake(project)


def test_project_uses_gitlab_issue_intake_checks_forge_kind():
    """GitLab intake is enabled only for GitLab forge_kind."""
    project = Project(
        id="p1",
        name="test",
        repo_url="https://gitlab.com/test/test.git",
        repo_path="/tmp/test",
        tracker_kind="oompah_md",
        github_issue_intake_enabled=True,
        forge_kind="gitlab",
    )
    assert project_uses_gitlab_issue_intake(project)


def test_project_uses_gitlab_issue_intake_requires_intake_enabled():
    """GitLab intake requires github_issue_intake_enabled flag."""
    project = Project(
        id="p1",
        name="test",
        repo_url="https://gitlab.com/test/test.git",
        repo_path="/tmp/test",
        tracker_kind="oompah_md",
        github_issue_intake_enabled=False,
        forge_kind="gitlab",
    )
    assert not project_uses_gitlab_issue_intake(project)


def test_ensure_native_issue_for_gitlab_creates_proposed_task():
    """ensure_native_issue_for_gitlab_issue creates a native Proposed task."""
    native = FakeNativeTracker()
    gitlab = FakeGitLabTracker()

    gitlab_issue = Issue(
        id="1",
        identifier="my-namespace/my-project#1",
        issue_number=1,
        title="Test GitLab issue",
        description="Test description",
        state="open",
        tracker_kind="gitlab",
        tracker_owner="my-namespace",
        tracker_repo="my-project",
        requestor_login="alice",
        provider_url="https://gitlab.com/my-namespace/my-project/-/issues/1",
    )

    created = ensure_native_issue_for_gitlab_issue(
        native,
        gitlab,
        gitlab_issue,
        post_import_comment=False,
    )

    assert created is not None
    assert created.identifier == "TASK-1"
    assert "external:gitlab" in created.labels
    assert created.state == PROPOSED


def test_gitlab_comments_copy_to_native_once():
    """Poll copies GitLab comments to native once."""
    native = FakeNativeTracker()
    created_issue = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Test",
        state=PROPOSED,
        tracker_kind="oompah_md",
    )
    native.issues["TASK-1"] = created_issue
    native.metadata["TASK-1"] = {
        "oompah.external.gitlab": {
            "id": "my-namespace/my-project#1",
            "imported_comment_ids": [],
        }
    }

    gitlab = FakeGitLabTracker()
    gitlab.issues_list = [
        Issue(
            id="1",
            identifier="my-namespace/my-project#1",
            issue_number=1,
            title="Test",
            state="open",
            tracker_owner="my-namespace",
            tracker_repo="my-project",
        )
    ]

    # Mock fetch_comments to return a comment
    def mock_fetch_comments(identifier: str) -> list[dict]:
        return [
            {"id": "c1", "author": "bob", "text": "This is a comment"}
        ]

    gitlab.fetch_comments = mock_fetch_comments

    class FakeConfig:
        tracker_active_states = ["Open"]
        tracker_terminal_states = ["Done"]

    class FakeOrch:
        def _tracker_for_project(self, pid: str):
            return native

        config = FakeConfig()

    orch = FakeOrch()
    project = Project(
        id="p1",
        name="test",
        repo_url="https://gitlab.com/my-namespace/my-project.git",
        repo_path="/tmp/test",
        tracker_kind="oompah_md",
        github_issue_intake_enabled=True,
        forge_kind="gitlab",
        tracker_owner="my-namespace",
        tracker_repo="my-project",
    )

    with patch(
        "oompah.gitlab_intake_bridge._gitlab_tracker_for_project",
        return_value=gitlab,
    ):
        poll_gitlab_issue_intake_project(orch, project)
        assert ("TASK-1", "This is a comment", "bob") in native.comments


def test_demote_h1_h2_headings():
    """H1 and H2 headings are demoted to H3."""
    result = _demote_h1_h2_headings("# Heading 1\n## Heading 2\n### Heading 3")
    assert result == "### Heading 1\n### Heading 2\n### Heading 3"


def test_native_description_for_gitlab_issue():
    """Native description includes GitLab-specific metadata."""
    issue = Issue(
        id="1",
        identifier="my-namespace/my-project#1",
        title="Test",
        description="Original description",
        state="open",
        requestor_login="alice",
        provider_url="https://gitlab.com/my-namespace/my-project/-/issues/1",
    )
    description = _native_description_for_gitlab_issue(issue)
    assert "Original description" in description
    assert "External GitLab Issue" in description
    assert "@alice" in description
    assert "my-namespace/my-project#1" in description


def test_import_gitlab_comment_skips_oompah_comments():
    """Comments from oompah are not imported."""
    native = FakeNativeTracker()
    metadata = {"imported_comment_ids": []}
    
    result = import_gitlab_comment_to_native(
        native,
        "TASK-1",
        metadata,
        comment_id="c1",
        author="oompah",
        body="Imported into oompah as `TASK-1`",
    )
    assert result is False
    assert len(native.comments) == 0


def test_import_gitlab_comment_idempotent():
    """Importing the same comment twice is idempotent."""
    native = FakeNativeTracker()
    metadata = {"imported_comment_ids": ["c1"]}
    
    result = import_gitlab_comment_to_native(
        native,
        "TASK-1",
        metadata,
        comment_id="c1",
        author="bob",
        body="This is a comment",
    )
    assert result is False  # Already imported
    assert len(native.comments) == 0


def test_sync_gitlab_intake_statuses_comments_and_closes():
    """Status sync posts comment and closes on terminal status."""
    native = FakeNativeTracker()
    task = Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="Test",
        state=MERGED,
        tracker_kind="oompah_md",
    )
    native.issues["TASK-1"] = task
    native.metadata["TASK-1"] = {
        "oompah.external.gitlab": {
            "id": "my-namespace/my-project#1",
            "last_synced_status": PROPOSED,
        }
    }

    gitlab = FakeGitLabTracker()

    class FakeConfig:
        tracker_active_states = ["Open"]
        tracker_terminal_states = ["Done"]

    class FakeOrch:
        def _tracker_for_project(self, pid: str):
            return native

        config = FakeConfig()

    orch = FakeOrch()
    project = Project(
        id="p1",
        name="test",
        repo_url="https://gitlab.com/my-namespace/my-project.git",
        repo_path="/tmp/test",
        tracker_kind="oompah_md",
        github_issue_intake_enabled=True,
        forge_kind="gitlab",
        tracker_owner="my-namespace",
        tracker_repo="my-project",
    )

    with patch(
        "oompah.gitlab_intake_bridge._gitlab_tracker_for_project",
        return_value=gitlab,
    ):
        metrics = sync_gitlab_issue_intake_statuses_for_project(orch, project)
        assert metrics["scanned"] == 1
        assert metrics["commented"] == 1
        assert metrics["closed"] == 1
        assert len(gitlab.comments_added) == 1
        assert "MERGED" in gitlab.comments_added[0][1].upper()
