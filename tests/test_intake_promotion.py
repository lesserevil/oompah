from __future__ import annotations

import time
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from oompah.intake_promotion import (
    promote_proposed_issue_to_backlog,
    record_intake_approval,
)
from oompah.intake_schema import (
    DecompositionStatus,
    IntakeReadiness,
    IntakeScopeKind,
    ValidatorResult,
    intake_to_raw,
)
from oompah.models import Issue, Project
from oompah.projects import ProjectError, ProjectStore
from oompah.statuses import BACKLOG, PROPOSED


class FakeTracker:
    def __init__(self, readiness: IntakeReadiness):
        self.metadata = {"oompah.intake": intake_to_raw(readiness)}
        self.update_calls: list[tuple[str, dict]] = []
        self.comments: list[tuple[str, str, str]] = []
        self.set_metadata_calls: list[tuple[str, str, object]] = []

    def get_metadata(self, identifier: str) -> dict[str, object]:
        return dict(self.metadata)

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        self.set_metadata_calls.append((identifier, key, value))
        self.metadata[key] = value

    def update_issue(self, identifier: str, **fields: str) -> None:
        self.update_calls.append((identifier, fields))

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> None:
        self.comments.append((identifier, text, author))


def _valid_unapproved_readiness() -> IntakeReadiness:
    return IntakeReadiness(
        missing_fields=[],
        scope=IntakeScopeKind.SMALL,
        requestor_approved=False,
        last_validator_result=ValidatorResult.PASS,
    )


def test_requestor_approval_promotes_ready_proposed_issue_to_backlog():
    tracker = FakeTracker(_valid_unapproved_readiness())
    project = Project(id="p", name="proj", repo_url="u", repo_path="/tmp/repo")

    readiness = record_intake_approval(
        tracker,
        "org/repo#1",
        issue_description="Ready proposal",
        actor="alice",
        requestor="alice",
        project=project,
        approved_at="2026-06-11T17:00:00+00:00",
    )
    assert readiness is not None
    assert readiness.requestor_approved is True

    result = promote_proposed_issue_to_backlog(
        tracker,
        "org/repo#1",
        current_status=PROPOSED,
    )

    assert result.promoted is True
    assert tracker.update_calls == [("org/repo#1", {"status": BACKLOG})]
    assert len(tracker.comments) == 1
    assert "moved this issue from Proposed to Backlog" in tracker.comments[0][1]
    assert "not dispatchable" in tracker.comments[0][1]


def test_requestor_approval_accepts_proposed_decomposition():
    tracker = FakeTracker(
        IntakeReadiness(
            missing_fields=[],
            scope=IntakeScopeKind.NEEDS_DECOMPOSITION,
            decomposition_status=DecompositionStatus.PROPOSED,
            requestor_approved=False,
            last_validator_result=ValidatorResult.PASS,
        )
    )
    project = Project(id="p", name="proj", repo_url="u", repo_path="/tmp/repo")

    readiness = record_intake_approval(
        tracker,
        "org/repo#1",
        issue_description="Ready epic proposal",
        actor="alice",
        requestor="alice",
        project=project,
        approved_at="2026-06-11T17:00:00+00:00",
    )

    assert readiness is not None
    assert readiness.requestor_approved is True
    assert readiness.decomposition_status == DecompositionStatus.ACCEPTED


def test_validator_pass_promotes_unapproved_proposed_issue_to_backlog():
    tracker = FakeTracker(_valid_unapproved_readiness())

    result = promote_proposed_issue_to_backlog(
        tracker,
        "org/repo#2",
        current_status=PROPOSED,
    )

    assert result.promoted is True
    assert result.reason == "validator_passed"
    assert tracker.update_calls == [("org/repo#2", {"status": BACKLOG})]
    assert len(tracker.comments) == 1


def test_validator_pass_can_promote_without_audit_comment():
    tracker = FakeTracker(_valid_unapproved_readiness())

    result = promote_proposed_issue_to_backlog(
        tracker,
        "org/repo#2",
        current_status=PROPOSED,
        post_audit_comment=False,
    )

    assert result.promoted is True
    assert result.reason == "validator_passed"
    assert result.audit_comment is None
    assert tracker.update_calls == [("org/repo#2", {"status": BACKLOG})]
    assert tracker.comments == []


def test_owner_override_promotes_even_when_readiness_is_blocked():
    tracker = FakeTracker(
        IntakeReadiness(
            missing_fields=["acceptance_criteria"],
            scope=IntakeScopeKind.SMALL,
            requestor_approved=False,
            last_validator_result=ValidatorResult.FAIL,
        )
    )
    project = Project(
        id="p",
        name="proj",
        repo_url="u",
        repo_path="/tmp/repo",
        tracker_owner="owner",
    )

    readiness = record_intake_approval(
        tracker,
        "org/repo#3",
        issue_description="Incomplete proposal",
        actor="owner",
        requestor="alice",
        project=project,
        approved_at="2026-06-11T17:00:00+00:00",
    )
    assert readiness is not None
    assert readiness.owner_override is True

    result = promote_proposed_issue_to_backlog(
        tracker,
        "org/repo#3",
        current_status=PROPOSED,
    )

    assert result.promoted is True
    assert tracker.update_calls == [("org/repo#3", {"status": BACKLOG})]
    assert "owner override" in tracker.comments[0][1]


def test_promotion_helper_never_moves_non_proposed_issue():
    tracker = FakeTracker(_valid_unapproved_readiness())

    result = promote_proposed_issue_to_backlog(
        tracker,
        "org/repo#4",
        current_status="Open",
    )

    assert result.promoted is False
    assert tracker.update_calls == []
    assert tracker.comments == []


@dataclass
class _WebhookTracker:
    readiness: IntakeReadiness
    issue: Issue

    def __post_init__(self):
        self.update_issue = MagicMock()
        self.add_comment = MagicMock()
        self.set_metadata_field = MagicMock(side_effect=self._set_metadata)

    def get_metadata(self, identifier: str) -> dict[str, object]:
        return {"oompah.intake": intake_to_raw(self.readiness)}

    def _set_metadata(self, identifier: str, key: str, value: object) -> None:
        if key == "oompah.intake":
            self.readiness = IntakeReadiness.from_raw(value)

    def fetch_issue_detail(self, identifier: str) -> Issue:
        return self.issue


def _approval_payload(
    body: str = "/oompah approve",
    *,
    requestor: str = "alice",
    comment_author: str | None = None,
) -> dict:
    author = comment_author or requestor
    return {
        "action": "created",
        "issue": {
            "number": 11,
            "title": "Proposed task",
            "body": "Ready proposal",
            "user": {"login": requestor},
            "pull_request": None,
        },
        "comment": {
            "id": 99,
            "body": body,
            "user": {"login": author},
        },
        "repository": {"full_name": "org/repo"},
        "sender": {"login": author},
    }


def test_approval_comment_auto_promotes_when_project_allows_it():
    import oompah.server as server

    issue = Issue(
        id="org/repo#11",
        identifier="org/repo#11",
        title="Proposed task",
        state=PROPOSED,
        description="Ready proposal",
    )
    tracker = _WebhookTracker(_valid_unapproved_readiness(), issue)
    project = Project(
        id="proj",
        name="proj",
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repo",
        tracker_kind="github_issues",
        tracker_owner="org",
        tracker_repo="repo",
        intake_auto_promote=True,
    )
    orch = MagicMock()
    orch.event_bus = MagicMock()
    orch.request_refresh = MagicMock()
    orch.invalidate_merged_branches = MagicMock()
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch.project_store.update = MagicMock()
    orch._tracker_for_project.return_value = tracker

    with patch.object(server, "_orchestrator", orch):
        client = TestClient(server.app)
        response = client.post(
            "/api/v1/webhooks/github",
            json=_approval_payload(),
            headers={"X-GitHub-Event": "issue_comment"},
        )

    assert response.status_code == 200
    for _ in range(50):
        if tracker.update_issue.called:
            break
        time.sleep(0.02)

    tracker.update_issue.assert_called_once_with("org/repo#11", status=BACKLOG)
    tracker.add_comment.assert_called_once()
    assert tracker.readiness.requestor_approved is True


def test_plain_requestor_approval_comment_auto_promotes_ready_issue():
    import oompah.server as server

    issue = Issue(
        id="org/repo#11",
        identifier="org/repo#11",
        title="Proposed task",
        state=PROPOSED,
        description="Ready proposal",
    )
    tracker = _WebhookTracker(_valid_unapproved_readiness(), issue)
    project = Project(
        id="proj",
        name="proj",
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repo",
        tracker_kind="github_issues",
        tracker_owner="org",
        tracker_repo="repo",
        intake_auto_promote=True,
    )
    orch = MagicMock()
    orch.event_bus = MagicMock()
    orch.request_refresh = MagicMock()
    orch.invalidate_merged_branches = MagicMock()
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch.project_store.update = MagicMock()
    orch._tracker_for_project.return_value = tracker

    with patch.object(server, "_orchestrator", orch):
        client = TestClient(server.app)
        response = client.post(
            "/api/v1/webhooks/github",
            json=_approval_payload("I approve this. Please add it to the backlog."),
            headers={"X-GitHub-Event": "issue_comment"},
        )

    assert response.status_code == 200
    for _ in range(50):
        if tracker.update_issue.called:
            break
        time.sleep(0.02)

    tracker.update_issue.assert_called_once_with("org/repo#11", status=BACKLOG)
    tracker.add_comment.assert_called_once()
    assert tracker.readiness.requestor_approved is True
    assert tracker.readiness.requestor_actor == "alice"


def test_plain_approval_records_and_comments_when_readiness_missing():
    import oompah.server as server

    issue = Issue(
        id="org/repo#11",
        identifier="org/repo#11",
        title="Proposed task",
        state=PROPOSED,
        description="Incomplete proposal",
    )
    tracker = _WebhookTracker(
        IntakeReadiness(
            missing_fields=["acceptance_criteria"],
            scope=IntakeScopeKind.SMALL,
            requestor_approved=False,
            last_validator_result=ValidatorResult.FAIL,
        ),
        issue,
    )
    project = Project(
        id="proj",
        name="proj",
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repo",
        tracker_kind="github_issues",
        tracker_owner="org",
        tracker_repo="repo",
        intake_auto_promote=True,
    )
    orch = MagicMock()
    orch.event_bus = MagicMock()
    orch.request_refresh = MagicMock()
    orch.invalidate_merged_branches = MagicMock()
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch.project_store.update = MagicMock()
    orch._tracker_for_project.return_value = tracker

    with patch.object(server, "_orchestrator", orch):
        client = TestClient(server.app)
        response = client.post(
            "/api/v1/webhooks/github",
            json=_approval_payload("I approve this. Please add it to the backlog."),
            headers={"X-GitHub-Event": "issue_comment"},
        )

    assert response.status_code == 200
    for _ in range(50):
        if tracker.set_metadata_field.called:
            break
        time.sleep(0.02)

    assert tracker.readiness.requestor_approved is True
    tracker.update_issue.assert_not_called()
    tracker.add_comment.assert_not_called()
    assert "acceptance_criteria" in tracker.readiness.missing_fields


def test_plain_approval_from_non_requestor_is_ignored():
    import oompah.server as server

    project = Project(
        id="proj",
        name="proj",
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repo",
        tracker_kind="github_issues",
        tracker_owner="org",
        tracker_repo="repo",
        intake_auto_promote=True,
    )
    orch = MagicMock()
    orch.event_bus = MagicMock()
    orch.request_refresh = MagicMock()
    orch.invalidate_merged_branches = MagicMock()
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch.project_store.update = MagicMock()

    with patch.object(server, "_orchestrator", orch):
        client = TestClient(server.app)
        response = client.post(
            "/api/v1/webhooks/github",
            json=_approval_payload(
                "I approve this. Please add it to the backlog.",
                requestor="alice",
                comment_author="bob",
            ),
            headers={"X-GitHub-Event": "issue_comment"},
        )

    assert response.status_code == 200
    time.sleep(0.1)
    orch._tracker_for_project.assert_not_called()


def test_ambiguous_requestor_comment_is_not_approval():
    import oompah.server as server

    project = Project(
        id="proj",
        name="proj",
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repo",
        tracker_kind="github_issues",
        tracker_owner="org",
        tracker_repo="repo",
        intake_auto_promote=True,
    )
    orch = MagicMock()
    orch.event_bus = MagicMock()
    orch.request_refresh = MagicMock()
    orch.invalidate_merged_branches = MagicMock()
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch.project_store.update = MagicMock()

    with patch.object(server, "_orchestrator", orch):
        client = TestClient(server.app)
        response = client.post(
            "/api/v1/webhooks/github",
            json=_approval_payload("Looks good to me."),
            headers={"X-GitHub-Event": "issue_comment"},
        )

    assert response.status_code == 200
    time.sleep(0.1)
    orch._tracker_for_project.assert_not_called()


def test_approval_comment_records_but_does_not_auto_promote_when_disabled():
    import oompah.server as server

    issue = Issue(
        id="org/repo#11",
        identifier="org/repo#11",
        title="Proposed task",
        state=PROPOSED,
        description="Ready proposal",
    )
    tracker = _WebhookTracker(_valid_unapproved_readiness(), issue)
    project = Project(
        id="proj",
        name="proj",
        repo_url="https://github.com/org/repo.git",
        repo_path="/tmp/repo",
        tracker_kind="github_issues",
        tracker_owner="org",
        tracker_repo="repo",
        intake_auto_promote=False,
    )
    orch = MagicMock()
    orch.event_bus = MagicMock()
    orch.request_refresh = MagicMock()
    orch.invalidate_merged_branches = MagicMock()
    orch.project_store = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch.project_store.update = MagicMock()
    orch._tracker_for_project.return_value = tracker

    with patch.object(server, "_orchestrator", orch):
        client = TestClient(server.app)
        response = client.post(
            "/api/v1/webhooks/github",
            json=_approval_payload(),
            headers={"X-GitHub-Event": "issue_comment"},
        )

    assert response.status_code == 200
    for _ in range(50):
        if tracker.set_metadata_field.called:
            break
        time.sleep(0.02)

    tracker.set_metadata_field.assert_called()
    tracker.update_issue.assert_not_called()
    tracker.add_comment.assert_not_called()


def test_api_rejects_direct_proposed_to_open_transition():
    import oompah.server as server

    issue = Issue(
        id="org/repo#12",
        identifier="org/repo#12",
        title="Proposed task",
        description="Implementation scope for this proposed task.",
        state=PROPOSED,
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store = MagicMock()

    with patch.object(server, "_orchestrator", orch):
        client = TestClient(server.app)
        response = client.patch(
            "/api/v1/issues/12",
            json={"issue_key": "org/repo#12", "project_id": "proj", "status": "Open"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "intake_transition_blocked"
    tracker.update_issue.assert_not_called()


def test_api_owner_override_promotes_proposed_to_backlog():
    import oompah.server as server

    issue = Issue(
        id="org/repo#13",
        identifier="org/repo#13",
        title="Proposed task",
        state=PROPOSED,
    )
    tracker = _WebhookTracker(
        IntakeReadiness(
            missing_fields=["acceptance_criteria"],
            requestor_approved=False,
            last_validator_result=ValidatorResult.FAIL,
        ),
        issue,
    )
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store = MagicMock()
    orch.config.tracker_terminal_states = ["Done", "Merged", "Archived"]
    orch.state.running = {}
    orch.state.retry_attempts = {}
    orch.state.claimed = set()
    orch.state.completed = set()
    orch._terminate_running = AsyncMock()

    with (
        patch.object(server, "_orchestrator", orch),
        patch.object(server, "broadcast_issues", new_callable=AsyncMock),
    ):
        client = TestClient(server.app)
        response = client.patch(
            "/api/v1/issues/13",
            json={
                "issue_key": "org/repo#13",
                "project_id": "proj",
                "status": "Backlog",
                "owner_override": True,
                "owner_actor": "owner",
            },
        )

    assert response.status_code == 200
    tracker.update_issue.assert_called_once_with("org/repo#13", status=BACKLOG)
    tracker.add_comment.assert_called_once()


def test_project_store_updates_intake_auto_promote(tmp_path):
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    project = Project(id="proj", name="proj", repo_url="u", repo_path="/tmp/repo")
    store._projects[project.id] = project

    updated = store.update("proj", intake_auto_promote=False)

    assert updated is not None
    assert updated.intake_auto_promote is False


def test_project_store_rejects_non_boolean_intake_auto_promote(tmp_path):
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    project = Project(id="proj", name="proj", repo_url="u", repo_path="/tmp/repo")
    store._projects[project.id] = project

    try:
        store.update("proj", intake_auto_promote="false")
    except ProjectError as exc:
        assert "intake_auto_promote" in str(exc)
    else:
        raise AssertionError("Expected ProjectError")
