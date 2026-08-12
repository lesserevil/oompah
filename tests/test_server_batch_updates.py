"""Project-scoped atomic batch task update API tests (OOMPAH-1178)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.events import EventBus, EventType
from oompah.models import Project
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.projects import ProjectStore
from oompah.server import app
from oompah.statuses import BACKLOG, DONE, OPEN
from oompah.terminal_audit import RequestState
from oompah.task_transition_service import issue_authority_version


@pytest.fixture()
def batch_context(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tracker = OompahMarkdownTracker(
        active_states=[OPEN],
        terminal_states=[DONE],
        cwd=str(root),
        default_branch="main",
        git_sync=False,
    )
    first = tracker.create_issue(
        "First task",
        description="Move the first accepted task.",
        initial_status=BACKLOG,
    )
    second = tracker.create_issue(
        "Second task",
        description="Move the second accepted task.",
        initial_status=BACKLOG,
    )
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "worktrees"),
    )
    project = Project(
        id="project-1",
        name="test-project",
        repo_url="https://github.com/example/project.git",
        repo_path=str(root),
        tracker_kind="oompah_md",
        status_actor_login="alice",
    )
    store._projects[project.id] = project
    orch = MagicMock()
    orch.project_store = store
    orch._tracker_for_project.return_value = tracker
    orch.state = SimpleNamespace(
        running={}, claimed=set(), retry_attempts={}, completed=set()
    )
    orch.integration_queue = MagicMock()
    orch.integration_queue.get.return_value = None
    orch.task_transition_journal = None
    orch._owner_claim_for_issue.return_value = None
    orch._audit_store = None
    orch._is_project_paused.side_effect = lambda project_id: bool(
        store.get(project_id).paused
    )
    orch.event_bus = EventBus()
    orch.request_refresh = MagicMock()
    for issue in (first, second):
        issue.project_id = project.id
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new=AsyncMock()),
    ):
        yield TestClient(app, raise_server_exceptions=False), orch, tracker, first, second


def _payload(first, second, *, actor="alice", status=OPEN):
    return {
        "project_id": "project-1",
        "actor_login": actor,
        "status": status,
        "operation": {
            "kind": "whole_column_move",
            "source_status": BACKLOG,
            "scope": "flat_board",
        },
        "updates": [
            {
                "identifier": issue.identifier,
                "expected_status": issue.state,
                "expected_revision": issue_authority_version(issue),
            }
            for issue in (first, second)
        ],
    }


def test_successful_column_move_is_one_atomic_api_operation(batch_context):
    client, orch, tracker, first, second = batch_context
    initial_revision = server_module._protocol_values()[2]
    events = []
    orch.event_bus.subscribe(
        EventType.ISSUE_STATE_CHANGED,
        lambda _event, payload: events.append(payload),
    )
    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=_payload(first, second),
        headers={"Idempotency-Key": "column-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["atomicity"] == "atomic"
    assert body["storage_transactions"] == 1
    assert body["batch_size"] == 2
    assert body["operation"]["kind"] == "whole_column_move"
    assert [row["identifier"] for row in body["results"]] == [
        first.identifier,
        second.identifier,
    ]
    assert tracker.fetch_issue_detail(first.identifier).state == OPEN
    assert tracker.fetch_issue_detail(second.identifier).state == OPEN
    orch.request_refresh.assert_called_once_with()
    assert body["event_cursor"]["epoch"]
    assert body["event_cursor"]["issue_revision"] == initial_revision + 1
    assert events == [
        {
            "project_id": "project-1",
            "identifiers": [first.identifier, second.identifier],
            "status": OPEN,
            "change": "batch-updated",
            "batch_id": body["batch_id"],
        }
    ]
    server_module.broadcast_issues.assert_not_awaited()


def test_paused_project_allows_owner_batch_but_reports_scheduler_suppression(
    batch_context,
):
    client, orch, tracker, first, second = batch_context
    orch.project_store.update("project-1", paused=True)

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=_payload(first, second),
        headers={"Idempotency-Key": "column-paused"},
    )

    assert response.status_code == 200
    assert response.json()["project_paused"] is True
    assert tracker.fetch_issue_detail(first.identifier).state == OPEN
    orch.request_refresh.assert_not_called()


def test_stale_member_rejects_complete_batch(batch_context):
    client, _orch, tracker, first, second = batch_context
    payload = _payload(first, second)
    payload["updates"][1]["expected_revision"] = "stale"

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=payload,
        headers={"Idempotency-Key": "column-stale"},
    )

    assert response.status_code == 409
    assert response.json()["applied"] == 0
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG
    assert tracker.fetch_issue_detail(second.identifier).state == BACKLOG


def test_replay_is_idempotent_and_reports_zero_new_transactions(batch_context):
    client, _orch, _tracker, first, second = batch_context
    payload = _payload(first, second)
    headers = {"Idempotency-Key": "column-replay"}

    initial = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=payload,
        headers=headers,
    )
    replay = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=payload,
        headers=headers,
    )

    assert initial.status_code == replay.status_code == 200
    assert replay.json()["batch_id"] == initial.json()["batch_id"]
    assert replay.json()["replayed"] is True
    assert replay.json()["storage_transactions"] == 0
    server_module.broadcast_issues.assert_not_awaited()


def test_non_owner_cannot_promote_backlog_batch_to_open(batch_context):
    client, _orch, tracker, first, second = batch_context

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=_payload(first, second, actor="bob"),
        headers={"Idempotency-Key": "column-not-owner"},
    )

    assert response.status_code == 409
    assert {
        rejection["code"]
        for rejection in response.json()["error"]["rejections"]
    } == {"intake_transition_rejected"}
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG
    assert tracker.fetch_issue_detail(second.identifier).state == BACKLOG


def test_terminal_batch_requires_audit_workflow(batch_context):
    client, _orch, tracker, first, second = batch_context

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=_payload(first, second, status=DONE),
        headers={"Idempotency-Key": "column-terminal"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "terminal_transition_requires_audit"
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG


def test_remote_backend_explicitly_reports_non_atomic_capability(batch_context):
    client, orch, _tracker, first, second = batch_context
    remote = MagicMock()
    remote.supports_atomic_batch_updates = False
    orch._tracker_for_project.return_value = remote

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=_payload(first, second),
        headers={"Idempotency-Key": "column-remote"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "atomic_batch_unsupported"
    remote.update_issue.assert_not_called()


def test_active_owner_claim_rejects_complete_batch(batch_context):
    client, orch, tracker, first, second = batch_context
    orch._owner_claim_for_issue.side_effect = (
        lambda issue_id, _project_id: object() if issue_id == second.id else None
    )

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=_payload(first, second),
        headers={"Idempotency-Key": "column-owned"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["rejections"] == [
        {
            "identifier": second.identifier,
            "code": "owner_claim_active",
            "message": "A direct-owner lease owns this task.",
        }
    ]
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG
    assert tracker.fetch_issue_detail(second.identifier).state == BACKLOG


def test_active_transition_claim_rejects_complete_batch(batch_context):
    client, orch, tracker, first, second = batch_context
    journal = MagicMock()
    journal.active_claims_for_tasks.return_value = {second.identifier}
    orch.task_transition_journal = journal

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=_payload(first, second),
        headers={"Idempotency-Key": "column-transition-owned"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["rejections"][0]["code"] == "transition_owned"
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG
    assert tracker.fetch_issue_detail(second.identifier).state == BACKLOG


def test_active_integration_lease_rejects_complete_batch(batch_context):
    client, orch, tracker, first, second = batch_context
    orch.integration_queue.get.side_effect = (
        lambda _project_id, identifier: (
            SimpleNamespace(state="ready") if identifier == second.identifier else None
        )
    )

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=_payload(first, second),
        headers={"Idempotency-Key": "column-integration-owned"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["rejections"][0]["code"] == "integration_owned"
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG
    assert tracker.fetch_issue_detail(second.identifier).state == BACKLOG


def test_active_terminal_audit_rejects_complete_batch(batch_context):
    client, orch, tracker, first, second = batch_context
    orch._audit_store = lambda issue: SimpleNamespace(
        read=lambda _identifier: SimpleNamespace(
            is_quarantined=False,
            pending_chain=(
                [SimpleNamespace(request_state=RequestState.PENDING)]
                if issue.identifier == second.identifier
                else []
            ),
        )
    )

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=_payload(first, second),
        headers={"Idempotency-Key": "column-audit-owned"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["rejections"][0]["code"] == "audit_owned"
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG
    assert tracker.fetch_issue_detail(second.identifier).state == BACKLOG


def test_mixed_legal_and_already_target_members_change_nothing(batch_context):
    client, _orch, tracker, first, second = batch_context
    tracker.update_issue(second.identifier, status=OPEN)
    refreshed_second = tracker.fetch_issue_detail(second.identifier)
    refreshed_second.project_id = "project-1"

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=_payload(first, refreshed_second),
        headers={"Idempotency-Key": "column-mixed"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["rejections"][0]["code"] == "already_in_target_status"
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG
    assert tracker.fetch_issue_detail(second.identifier).state == OPEN


def test_authenticated_principal_rejects_supplied_actor_spoof(batch_context):
    client, _orch, tracker, first, second = batch_context
    principal = server_module.AuthenticatedPrincipal(
        username="operator-http",
        actor_login="alice",
        source="basic",
    )

    with patch.object(
        server_module, "_authenticated_principal", return_value=principal
    ):
        response = client.post(
            "/api/v1/projects/project-1/tasks/batch-update",
            json=_payload(first, second, actor="mallory"),
            headers={"Idempotency-Key": "column-spoof"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "actor_mismatch"
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG
    assert tracker.fetch_issue_detail(second.identifier).state == BACKLOG


def test_duplicate_identifiers_are_rejected_before_storage(batch_context):
    client, _orch, tracker, first, second = batch_context
    payload = _payload(first, second)
    payload["updates"][1] = dict(payload["updates"][0])

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=payload,
        headers={"Idempotency-Key": "column-duplicate"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "duplicate_identifier"
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG


def test_batch_size_limit_is_enforced_before_storage(batch_context):
    client, _orch, tracker, first, second = batch_context
    payload = _payload(first, second)
    payload["updates"] = [dict(payload["updates"][0]) for _ in range(201)]

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=payload,
        headers={"Idempotency-Key": "column-too-large"},
    )

    assert response.status_code == 400
    assert "1-200" in response.json()["error"]["message"]
    assert tracker.fetch_issue_detail(first.identifier).state == BACKLOG


def test_idempotency_key_reuse_for_changed_payload_conflicts(batch_context):
    client, _orch, _tracker, first, second = batch_context
    payload = _payload(first, second)
    headers = {"Idempotency-Key": "column-conflict"}
    initial = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=payload,
        headers=headers,
    )
    changed = _payload(first, second)
    changed["updates"].reverse()

    response = client.post(
        "/api/v1/projects/project-1/tasks/batch-update",
        json=changed,
        headers=headers,
    )

    assert initial.status_code == 200
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_conflict"
