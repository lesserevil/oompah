"""Tests for importing GitHub issue intake into native oompah tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from oompah.github_intake_bridge import (
    ensure_native_issue_for_github_issue,
    handle_github_issue_event_for_native_project,
    import_github_comment_to_native,
    poll_github_issue_intake_project,
    sync_github_issue_intake_statuses_for_project,
)
from oompah.models import Issue, Project
from oompah.statuses import ARCHIVED, MERGED, PROPOSED
from oompah.webhooks import WebhookEvent


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

    def fetch_all_issues_enriched(self) -> list[Issue]:
        return list(self.issues.values())

    def get_metadata(self, identifier: str) -> dict[str, object]:
        return dict(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        self.metadata.setdefault(identifier, {})[key] = value

    def update_issue(self, identifier: str, **fields: object) -> None:
        issue = self.issues[identifier]
        if "status" in fields:
            issue.state = str(fields["status"])
        if "state" in fields:
            issue.state = str(fields["state"])
        if "title" in fields:
            issue.title = str(fields["title"])
        self.update_calls.append((identifier, dict(fields)))

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        self.comments.append((identifier, text, author))
        return {"author": author, "text": text}


class FakeGitHubTracker:
    def __init__(self, issues: list[Issue] | None = None):
        self.issues = {issue.identifier: issue for issue in issues or []}
        self.metadata: dict[str, dict[str, object]] = {}
        self.metadata_writes = 0
        self.comments: list[tuple[str, str, str]] = []
        self.update_calls: list[tuple[str, dict[str, object]]] = []

    def fetch_all_issues(self) -> list[Issue]:
        return list(self.issues.values())

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issues.get(identifier)

    def get_metadata(self, identifier: str) -> dict[str, object]:
        return dict(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        self.metadata_writes += 1
        self.metadata.setdefault(identifier, {})[key] = value

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        self.comments.append((identifier, text, author))
        return {"author": author, "text": text}

    def update_issue(self, identifier: str, **fields: object) -> None:
        self.update_calls.append((identifier, dict(fields)))


def _github_issue(**overrides) -> Issue:
    defaults = {
        "id": "example-org/app#7",
        "identifier": "example-org/app#7",
        "title": "Report export fails",
        "description": "Exporting a large report returns a 500.",
        "state": "open",
        "issue_type": "task",
        "tracker_kind": "github_issues",
        "tracker_owner": "example-org",
        "tracker_repo": "app",
        "issue_number": "7",
        "provider_url": "https://github.com/example-org/app/issues/7",
        "requestor_login": "alice",
    }
    defaults.update(overrides)
    return Issue(**defaults)


def _project() -> Project:
    return Project(
        id="proj-test",
        name="app",
        repo_url="https://github.com/example-org/app.git",
        repo_path="/tmp/app",
        tracker_kind="oompah_md",
        tracker_owner="example-org",
        tracker_repo="app",
        github_issue_intake_enabled=True,
    )


def _orch(native: FakeNativeTracker):
    return SimpleNamespace(
        config=SimpleNamespace(
            tracker_active_states=["Open"],
            tracker_terminal_states=["Done", "Merged", "Archived"],
        ),
        _tracker_for_project=lambda project_id: native,
    )


def _valid_description() -> str:
    return (
        "## Problem\n"
        "Exporting large reports fails for customers and leaves them without "
        "the data they need for end-of-month review.\n\n"
        "## Acceptance Criteria\n"
        "- Large report exports complete successfully\n"
        "- A regression test covers the large report export path\n"
    )


def test_github_issue_import_creates_native_proposed_task_with_external_metadata():
    native = FakeNativeTracker()
    github = FakeGitHubTracker([_github_issue()])

    created = ensure_native_issue_for_github_issue(
        native,
        github,
        _github_issue(),
    )

    assert created is not None
    assert created.identifier == "TASK-1"
    assert created.state == PROPOSED
    assert created.issue_type == "task"
    assert "external:github" in created.labels
    assert "https://github.com/example-org/app/issues/7" in (created.description or "")
    metadata = native.metadata[created.identifier]["oompah.external.github"]
    assert metadata["id"] == "example-org/app#7"
    assert metadata["requestor_login"] == "alice"
    assert metadata["last_synced_status"] == PROPOSED
    assert github.comments == [
        (
            "example-org/app#7",
            "Imported into oompah as `TASK-1` and queued for intake validation in `Proposed`.",
            "oompah",
        )
    ]


def test_github_comments_copy_to_native_once_and_skip_oompah_comments():
    native = FakeNativeTracker()
    issue = native.create_issue("Imported", initial_status=PROPOSED)
    metadata = {
        "id": "example-org/app#7",
        "imported_comment_ids": [],
    }
    native.set_metadata_field(issue.identifier, "oompah.external.github", metadata)

    copied = import_github_comment_to_native(
        native,
        issue.identifier,
        metadata,
        comment_id=100,
        author="alice",
        body="I can reproduce this on a fresh profile.",
    )
    duplicate = import_github_comment_to_native(
        native,
        issue.identifier,
        native.metadata[issue.identifier]["oompah.external.github"],
        comment_id=100,
        author="alice",
        body="I can reproduce this on a fresh profile.",
    )
    oompah = import_github_comment_to_native(
        native,
        issue.identifier,
        native.metadata[issue.identifier]["oompah.external.github"],
        comment_id=101,
        author="oompah",
        body="Imported into oompah.",
    )

    assert copied is True
    assert duplicate is False
    assert oompah is False
    assert native.comments == [
        (issue.identifier, "I can reproduce this on a fresh profile.", "alice")
    ]
    metadata = native.metadata[issue.identifier]["oompah.external.github"]
    assert metadata["imported_comment_ids"] == ["100"]


def test_poll_rejects_invalid_github_issue_before_native_import(monkeypatch):
    native = FakeNativeTracker()
    invalid_issue = _github_issue(
        title="Bug",
        description="Broken.",
    )
    github = FakeGitHubTracker([invalid_issue])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )

    imported = poll_github_issue_intake_project(_orch(native), _project())

    assert imported == 0
    assert native.issues == {}
    assert len(github.comments) == 1
    assert github.comments[0][0] == "example-org/app#7"
    assert "missing the following information" in github.comments[0][1]
    assert "oompah.intake_comment" in github.metadata["example-org/app#7"]


def test_poll_does_not_rewrite_unchanged_invalid_github_issue(monkeypatch):
    native = FakeNativeTracker()
    invalid_issue = _github_issue(
        title="Bug",
        description="Broken.",
    )
    github = FakeGitHubTracker([invalid_issue])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )

    poll_github_issue_intake_project(_orch(native), _project())
    writes_after_first_poll = github.metadata_writes
    poll_github_issue_intake_project(_orch(native), _project())

    assert native.issues == {}
    assert len(github.comments) == 1
    assert github.metadata_writes == writes_after_first_poll


def test_poll_skips_readiness_comment_for_existing_native_import(monkeypatch):
    native = FakeNativeTracker()
    imported = native.create_issue("Imported", initial_status=PROPOSED)
    native.set_metadata_field(
        imported.identifier,
        "oompah.external.github",
        {
            "id": "example-org/app#7",
            "last_synced_status": PROPOSED,
            "imported_comment_ids": [],
        },
    )
    invalid_issue = _github_issue(
        title="Bug",
        description="Broken.",
    )
    github = FakeGitHubTracker([invalid_issue])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )

    imported_count = poll_github_issue_intake_project(_orch(native), _project())

    assert imported_count == 0
    assert list(native.issues) == [imported.identifier]
    assert github.comments == []
    assert github.metadata_writes == 0
    assert native.update_calls == []


def test_poll_imports_github_issue_after_external_readiness_passes(monkeypatch):
    native = FakeNativeTracker()
    github = FakeGitHubTracker([_github_issue(description=_valid_description())])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )

    imported = poll_github_issue_intake_project(_orch(native), _project())

    assert imported == 1
    assert list(native.issues) == ["TASK-1"]
    assert native.issues["TASK-1"].state == PROPOSED
    assert github.comments == [
        (
            "example-org/app#7",
            "Imported into oompah as `TASK-1` and queued for intake validation in `Proposed`.",
            "oompah",
        )
    ]


def test_poll_archives_native_task_when_github_issue_is_closed(monkeypatch):
    native = FakeNativeTracker()
    issue = native.create_issue("Imported", initial_status=PROPOSED)
    native.set_metadata_field(
        issue.identifier,
        "oompah.external.github",
        {
            "id": "example-org/app#7",
            "last_synced_status": PROPOSED,
            "imported_comment_ids": [],
        },
    )
    github = FakeGitHubTracker(
        [
            _github_issue(
                state=ARCHIVED,
                closed_at=datetime(2026, 6, 19, tzinfo=timezone.utc),
            )
        ]
    )
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )

    imported = poll_github_issue_intake_project(_orch(native), _project())

    assert imported == 0
    assert native.issues[issue.identifier].state == ARCHIVED
    assert native.update_calls == [(issue.identifier, {"status": ARCHIVED})]
    metadata = native.metadata[issue.identifier]["oompah.external.github"]
    assert metadata["last_github_state"] == "closed"
    assert metadata["last_synced_status"] == ARCHIVED
    assert "external_closed_at" in metadata


def test_closed_github_webhook_archives_existing_native_task(monkeypatch):
    native = FakeNativeTracker()
    issue = native.create_issue("Imported", initial_status=PROPOSED)
    native.set_metadata_field(
        issue.identifier,
        "oompah.external.github",
        {
            "id": "example-org/app#7",
            "last_synced_status": PROPOSED,
            "imported_comment_ids": [],
        },
    )
    github = FakeGitHubTracker([_github_issue(state="closed")])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )
    event = WebhookEvent(
        provider="github",
        event_type="issues",
        action="closed",
        repo_slug="example-org/app",
        issue_number="7",
        raw={"issue": {"number": 7, "state": "closed", "title": "Report export fails"}},
    )

    handle_github_issue_event_for_native_project(_orch(native), event, _project())

    assert native.issues[issue.identifier].state == ARCHIVED
    assert native.update_calls == [(issue.identifier, {"status": ARCHIVED})]


def test_existing_native_import_comment_webhook_copies_without_readiness_comment(monkeypatch):
    native = FakeNativeTracker()
    issue = native.create_issue("Imported", initial_status=PROPOSED)
    native.set_metadata_field(
        issue.identifier,
        "oompah.external.github",
        {
            "id": "example-org/app#7",
            "last_synced_status": PROPOSED,
            "imported_comment_ids": [],
        },
    )
    github = FakeGitHubTracker(
        [
            _github_issue(
                title="Bug",
                description="Broken.",
            )
        ]
    )
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )
    event = WebhookEvent(
        provider="github",
        event_type="issue_comment",
        action="created",
        repo_slug="example-org/app",
        issue_number="7",
        comment_id="100",
        author="alice",
        raw={
            "issue": {
                "number": 7,
                "state": "open",
                "title": "Bug",
                "body": "Broken.",
                "user": {"login": "alice"},
            },
            "comment": {
                "id": 100,
                "body": "Here is the extra context.",
                "user": {"login": "alice"},
            },
        },
    )

    handle_github_issue_event_for_native_project(_orch(native), event, _project())

    assert github.comments == []
    assert github.metadata_writes == 0
    assert native.comments == [
        (issue.identifier, "Here is the extra context.", "alice")
    ]


def test_closed_github_issue_does_not_archive_merged_native_task(monkeypatch):
    native = FakeNativeTracker()
    issue = native.create_issue("Imported", initial_status=MERGED)
    native.set_metadata_field(
        issue.identifier,
        "oompah.external.github",
        {
            "id": "example-org/app#7",
            "last_synced_status": MERGED,
            "imported_comment_ids": [],
        },
    )
    github = FakeGitHubTracker([_github_issue(state="closed")])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )

    poll_github_issue_intake_project(_orch(native), _project())

    assert native.issues[issue.identifier].state == MERGED
    assert native.update_calls == []


def test_reopened_github_issue_moves_externally_archived_task_to_proposed(monkeypatch):
    native = FakeNativeTracker()
    issue = native.create_issue("Imported", initial_status=ARCHIVED)
    native.set_metadata_field(
        issue.identifier,
        "oompah.external.github",
        {
            "id": "example-org/app#7",
            "last_github_state": "closed",
            "external_closed_at": "2026-06-19T00:00:00+00:00",
            "last_synced_status": ARCHIVED,
            "imported_comment_ids": [],
        },
    )
    github = FakeGitHubTracker([_github_issue(description=_valid_description())])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )

    imported = poll_github_issue_intake_project(_orch(native), _project())

    assert imported == 0
    assert native.issues[issue.identifier].state == PROPOSED
    assert native.update_calls == [(issue.identifier, {"status": PROPOSED})]
    metadata = native.metadata[issue.identifier]["oompah.external.github"]
    assert metadata["last_github_state"] == "open"
    assert metadata["last_synced_status"] == PROPOSED
    assert "external_reopened_at" in metadata


def test_status_sync_comments_and_closes_github_issue_on_terminal_state(monkeypatch):
    native = FakeNativeTracker()
    issue = native.create_issue("Imported", initial_status=MERGED)
    native.set_metadata_field(
        issue.identifier,
        "oompah.external.github",
        {
            "id": "example-org/app#7",
            "last_synced_status": PROPOSED,
            "imported_comment_ids": [],
        },
    )
    github = FakeGitHubTracker([_github_issue()])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )

    metrics = sync_github_issue_intake_statuses_for_project(_orch(native), _project())

    assert metrics["scanned"] == 1
    assert metrics["commented"] == 1
    assert metrics["closed"] == 1
    assert github.comments == [
        ("example-org/app#7", "Oompah task `TASK-1` is now `Merged`.", "oompah")
    ]
    assert github.update_calls == [("example-org/app#7", {"status": MERGED})]
    metadata = native.metadata[issue.identifier]["oompah.external.github"]
    assert metadata["last_synced_status"] == MERGED
