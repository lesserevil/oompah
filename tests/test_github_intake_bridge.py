"""Tests for importing GitHub issue intake into native oompah tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from oompah.github_intake_bridge import (
    _github_issue_from_event,
    _reconcile_native_type_and_labels,
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
        if "type" in fields:
            issue.issue_type = str(fields["type"])
        if "add-label" in fields:
            lbl = str(fields["add-label"])
            if lbl not in (issue.labels or []):
                issue.labels = list(issue.labels or []) + [lbl]
        if "labels" in fields:
            issue.labels = list(fields["labels"])  # type: ignore[arg-type]
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


def _valid_bug_description() -> str:
    """A description that passes the bug-type intake validator."""
    return (
        "## Problem\n"
        "Widget renders incorrectly when data contains unicode characters.\n\n"
        "## Steps to Reproduce\n"
        "1. Open the widget panel\n"
        "2. Load a dataset that contains unicode characters in labels\n"
        "3. Observe the garbled output\n\n"
        "## Actual Behavior\n"
        "The widget shows garbled text instead of the correct characters.\n\n"
        "## Expected Behavior\n"
        "The widget should render unicode characters correctly.\n\n"
        "## Acceptance Criteria\n"
        "- Widget renders unicode labels without garbling\n"
        "- A regression test covers this rendering path\n"
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


# ---------------------------------------------------------------------------
# Label and type normalization (OOMPAH-14)
# ---------------------------------------------------------------------------

def _webhook_issue_payload(
    number: int = 7,
    title: str = "Bug: widget renders wrong",
    body: str = "",
    state: str = "open",
    labels: list[dict] | None = None,
    login: str = "alice",
    html_url: str | None = None,
) -> dict:
    """Build a minimal GitHub webhook issue dict with the specified labels."""
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": state,
        "labels": labels or [],
        "user": {"login": login},
        "html_url": html_url or f"https://github.com/example-org/app/issues/{number}",
        "closed_at": None,
    }


def test_github_issue_from_event_parses_type_bug_label():
    """_github_issue_from_event() must extract issue_type from a type:bug label."""
    event = WebhookEvent(
        provider="github",
        event_type="issues",
        action="opened",
        repo_slug="example-org/app",
        issue_number="7",
        raw={
            "issue": _webhook_issue_payload(
                labels=[{"name": "type:bug"}, {"name": "team-alpha"}]
            )
        },
    )

    result = _github_issue_from_event(event, _project())

    assert result is not None
    assert result.issue_type == "bug"
    # user-facing label preserved; oompah-internal type label excluded
    assert "team-alpha" in (result.labels or [])
    assert "type:bug" not in (result.labels or [])


def test_github_issue_from_event_parses_priority_label():
    """_github_issue_from_event() must extract priority from a priority:N label."""
    event = WebhookEvent(
        provider="github",
        event_type="issues",
        action="opened",
        repo_slug="example-org/app",
        issue_number="7",
        raw={
            "issue": _webhook_issue_payload(
                labels=[{"name": "priority:2"}, {"name": "type:feature"}]
            )
        },
    )

    result = _github_issue_from_event(event, _project())

    assert result is not None
    assert result.priority == 2
    assert result.issue_type == "feature"


def test_github_issue_from_event_parses_parent_label():
    """_github_issue_from_event() must extract parent_id from a parent:N label."""
    event = WebhookEvent(
        provider="github",
        event_type="issues",
        action="opened",
        repo_slug="example-org/app",
        issue_number="7",
        raw={
            "issue": _webhook_issue_payload(
                labels=[{"name": "parent:42"}]
            )
        },
    )

    result = _github_issue_from_event(event, _project())

    assert result is not None
    assert result.parent_id == "example-org/app#42"
    # parent: label must not appear in user-facing labels
    assert "parent:42" not in (result.labels or [])


def test_github_issue_from_event_parses_depends_on_label():
    """_github_issue_from_event() must extract blocked_by from depends-on:N labels."""
    event = WebhookEvent(
        provider="github",
        event_type="issues",
        action="opened",
        repo_slug="example-org/app",
        issue_number="7",
        raw={
            "issue": _webhook_issue_payload(
                labels=[{"name": "depends-on:17"}, {"name": "depends-on:23"}]
            )
        },
    )

    result = _github_issue_from_event(event, _project())

    assert result is not None
    dep_ids = [str(b.identifier) for b in (result.blocked_by or [])]
    assert "example-org/app#17" in dep_ids
    assert "example-org/app#23" in dep_ids


def test_github_issue_from_event_preserves_routing_labels():
    """_github_issue_from_event() must keep user/routing labels not in oompah namespace."""
    event = WebhookEvent(
        provider="github",
        event_type="issues",
        action="opened",
        repo_slug="example-org/app",
        issue_number="7",
        raw={
            "issue": _webhook_issue_payload(
                labels=[
                    {"name": "type:bug"},
                    {"name": "priority:1"},
                    {"name": "team-alpha"},
                    {"name": "area:infra"},
                    {"name": "oompah:status:backlog"},  # internal — must be excluded
                ]
            )
        },
    )

    result = _github_issue_from_event(event, _project())

    assert result is not None
    user_labels = result.labels or []
    assert "team-alpha" in user_labels
    assert "area:infra" in user_labels
    # oompah-internal labels must not appear in user_labels
    assert "oompah:status:backlog" not in user_labels
    assert "type:bug" not in user_labels
    assert "priority:1" not in user_labels


def test_ensure_native_issue_forwards_issue_type_to_native_create():
    """ensure_native_issue_for_github_issue() must pass issue_type to create_issue()."""
    native = FakeNativeTracker()
    github = FakeGitHubTracker()

    gh_issue = _github_issue(issue_type="bug")
    created = ensure_native_issue_for_github_issue(native, github, gh_issue)

    assert created is not None
    assert created.issue_type == "bug"


def test_ensure_native_issue_forwards_user_labels_to_native_create():
    """User-facing GitHub labels are preserved on the native task alongside external:github."""
    native = FakeNativeTracker()
    github = FakeGitHubTracker()

    gh_issue = _github_issue(labels=["team-alpha", "area:backend"])
    created = ensure_native_issue_for_github_issue(native, github, gh_issue)

    assert created is not None
    assert "external:github" in created.labels
    assert "team-alpha" in created.labels
    assert "area:backend" in created.labels


def test_ensure_native_issue_forwards_parent_id_to_native_create():
    """parent_id from the GitHub issue is forwarded to the native task's parent field."""
    native = FakeNativeTracker()
    github = FakeGitHubTracker()

    gh_issue = _github_issue(parent_id="example-org/app#42")
    created = ensure_native_issue_for_github_issue(native, github, gh_issue)

    assert created is not None
    assert created.parent_id == "example-org/app#42"


def test_ensure_native_issue_sets_only_external_github_label_when_no_user_labels():
    """When the GitHub issue has no user-facing labels, only 'external:github' is set."""
    native = FakeNativeTracker()
    github = FakeGitHubTracker()

    # _github_issue() defaults: labels=None (no user labels)
    created = ensure_native_issue_for_github_issue(native, github, _github_issue())

    assert created is not None
    assert created.labels == ["external:github"]


def test_webhook_opened_event_creates_native_task_with_type_and_labels(monkeypatch):
    """Full webhook handler must create a native task with correct type and labels.

    Simulates an issues.opened webhook for a GitHub issue that carries type:bug,
    priority:2, and routing label team-alpha.  The FakeGitHubTracker returns an
    issue pre-populated with the same metadata (as if parsed by the API).
    """
    native = FakeNativeTracker()
    gh_issue = _github_issue(
        title="Widget renders incorrectly always",
        description=_valid_bug_description(),
        issue_type="bug",
        priority=2,
        labels=["team-alpha"],
    )
    github = FakeGitHubTracker([gh_issue])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )

    event = WebhookEvent(
        provider="github",
        event_type="issues",
        action="opened",
        repo_slug="example-org/app",
        issue_number="7",
        raw={
            "issue": _webhook_issue_payload(
                title="Widget renders incorrectly always",
                body=_valid_bug_description(),
                labels=[
                    {"name": "type:bug"},
                    {"name": "priority:2"},
                    {"name": "team-alpha"},
                ],
            )
        },
    )

    handle_github_issue_event_for_native_project(_orch(native), event, _project())

    assert len(native.issues) == 1
    task = next(iter(native.issues.values()))
    assert task.issue_type == "bug"
    assert task.priority == 2
    assert "external:github" in task.labels
    assert "team-alpha" in task.labels
    assert task.state == PROPOSED


def test_polling_and_webhook_produce_equivalent_native_metadata(monkeypatch):
    """Polling and webhook intake paths must produce the same native task metadata.

    Uses the same GitHub issue (type:bug, priority:2, team-alpha) for both
    paths and asserts that issue_type, priority, and labels match.
    """
    # ---- polling path ----
    native_poll = FakeNativeTracker()
    gh_issue = _github_issue(
        title="Widget unicode rendering bug",
        description=_valid_bug_description(),
        issue_type="bug",
        priority=2,
        labels=["team-alpha"],
    )
    github_poll = FakeGitHubTracker([gh_issue])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github_poll,
    )
    poll_github_issue_intake_project(_orch(native_poll), _project())
    poll_task = next(iter(native_poll.issues.values()))

    # ---- webhook path ----
    native_wh = FakeNativeTracker()
    gh_issue_wh = _github_issue(
        title="Widget unicode rendering bug",
        description=_valid_bug_description(),
        issue_type="bug",
        priority=2,
        labels=["team-alpha"],
    )
    github_wh = FakeGitHubTracker([gh_issue_wh])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github_wh,
    )
    event = WebhookEvent(
        provider="github",
        event_type="issues",
        action="opened",
        repo_slug="example-org/app",
        issue_number="7",
        raw={
            "issue": _webhook_issue_payload(
                title="Widget unicode rendering bug",
                body=_valid_bug_description(),
                labels=[
                    {"name": "type:bug"},
                    {"name": "priority:2"},
                    {"name": "team-alpha"},
                ],
            )
        },
    )
    handle_github_issue_event_for_native_project(_orch(native_wh), event, _project())
    wh_task = next(iter(native_wh.issues.values()))

    # Both paths must produce matching metadata.
    assert poll_task.issue_type == wh_task.issue_type
    assert poll_task.priority == wh_task.priority
    assert sorted(poll_task.labels or []) == sorted(wh_task.labels or [])


def test_reconcile_native_type_and_labels_backfills_type_on_default_task():
    """_reconcile_native_type_and_labels() updates type when native has default 'task'."""
    native = FakeNativeTracker()
    existing = native.create_issue("Old task", issue_type="task", initial_status=PROPOSED)

    gh_issue = _github_issue(issue_type="bug")
    updated = _reconcile_native_type_and_labels(native, existing, gh_issue)

    assert updated.issue_type == "bug"
    assert any(
        "type" in fields for _, fields in native.update_calls
    )


def test_reconcile_native_type_and_labels_does_not_overwrite_explicit_type():
    """_reconcile_native_type_and_labels() must not overwrite an explicitly set type."""
    native = FakeNativeTracker()
    # Issue was explicitly set to 'feature' after import.
    existing = native.create_issue("Epic: new thing", issue_type="feature", initial_status=PROPOSED)

    # GitHub says it is now a bug, but we should not override an explicit type.
    gh_issue = _github_issue(issue_type="bug")
    updated = _reconcile_native_type_and_labels(native, existing, gh_issue)

    assert updated.issue_type == "feature"
    assert not any("type" in fields for _, fields in native.update_calls)


def test_reconcile_native_type_and_labels_adds_missing_labels():
    """_reconcile_native_type_and_labels() adds GitHub user labels absent on native task."""
    native = FakeNativeTracker()
    existing = native.create_issue(
        "Imported",
        issue_type="task",
        labels=["external:github"],
        initial_status=PROPOSED,
    )

    gh_issue = _github_issue(issue_type="task", labels=["team-alpha", "area:backend"])
    updated = _reconcile_native_type_and_labels(native, existing, gh_issue)

    assert "team-alpha" in (updated.labels or [])
    assert "area:backend" in (updated.labels or [])
    assert "external:github" in (updated.labels or [])


def test_reconcile_native_type_and_labels_preserves_existing_native_labels():
    """_reconcile_native_type_and_labels() never removes manually-added native labels."""
    native = FakeNativeTracker()
    existing = native.create_issue(
        "Imported",
        issue_type="task",
        labels=["external:github", "manually-added"],
        initial_status=PROPOSED,
    )

    gh_issue = _github_issue(issue_type="task", labels=["team-alpha"])
    updated = _reconcile_native_type_and_labels(native, existing, gh_issue)

    # Both the new GitHub label and the existing manual label must be present.
    assert "manually-added" in (updated.labels or [])
    assert "team-alpha" in (updated.labels or [])


def test_reconcile_from_poll_backfills_type_on_existing_task(monkeypatch):
    """Polling an open GitHub issue must backfill missing type/labels on an existing native task.

    This covers the scenario where a webhook created the native task before the
    label-parsing fix was deployed (issue_type='task', labels=['external:github']),
    and the polling path must repair the metadata.
    """
    native = FakeNativeTracker()
    # Simulate a task that was created before the fix: default type, no routing labels.
    task = native.create_issue(
        "Bug report",
        issue_type="task",
        labels=["external:github"],
        initial_status=PROPOSED,
    )
    native.set_metadata_field(
        task.identifier,
        "oompah.external.github",
        {
            "id": "example-org/app#7",
            "last_synced_status": PROPOSED,
            "imported_comment_ids": [],
        },
    )
    # GitHub issue now has type:bug and routing label team-alpha.
    gh_issue = _github_issue(
        description=_valid_bug_description(),
        issue_type="bug",
        labels=["team-alpha"],
    )
    github = FakeGitHubTracker([gh_issue])
    monkeypatch.setattr(
        "oompah.github_intake_bridge._github_tracker_for_project",
        lambda project, active, terminal: github,
    )

    poll_github_issue_intake_project(_orch(native), _project())

    repaired = native.issues[task.identifier]
    assert repaired.issue_type == "bug"
    assert "team-alpha" in (repaired.labels or [])
