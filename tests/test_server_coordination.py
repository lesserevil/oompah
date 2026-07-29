"""API coverage for durable inter-task coordination."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


def _orchestrator() -> MagicMock:
    orch = MagicMock()
    orch.coordination_peers.return_value = [
        {
            "identifier": "TASK-1",
            "reasons": ["finish-dependency"],
        }
    ]
    orch.coordination_inbox.return_value = [
        {
            "id": "message-1",
            "sender_task": "TASK-1",
            "recipient_task": "TASK-2",
            "text": "The interface is ready.",
        }
    ]
    orch.coordination_timeline.return_value = []
    orch.coordination_send.return_value = {
        "id": "message-2",
        "live_delivery": "durable_fallback",
    }
    orch.coordination_checkpoint.return_value = {
        "task_identifier": "TASK-2",
        "conflict_peers": ["TASK-1"],
    }
    return orch


def test_peers_resolves_project_and_returns_suggestions(client):
    orch = _orchestrator()
    with patch.object(server_module, "_get_orchestrator", return_value=orch):
        response = client.get(
            "/api/v1/issues/TASK-2/coordination/peers",
            params={"project_id": "proj-1"},
        )

    assert response.status_code == 200
    assert response.json()["peers"][0]["identifier"] == "TASK-1"
    orch.coordination_peers.assert_called_once_with("proj-1", "TASK-2")


def test_inbox_forwards_read_filters(client):
    orch = _orchestrator()
    with patch.object(server_module, "_get_orchestrator", return_value=orch):
        response = client.get(
            "/api/v1/issues/TASK-2/coordination/inbox",
            params={
                "project_id": "proj-1",
                "unread_only": "true",
                "after_id": "message-0",
                "limit": "20",
            },
        )

    assert response.status_code == 200
    orch.coordination_inbox.assert_called_once_with(
        "proj-1",
        "TASK-2",
        unread_only=True,
        after_id="message-0",
        limit=20,
    )


def test_send_persists_authorized_message(client):
    orch = _orchestrator()
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(
            server_module,
            "broadcast_issues",
            new_callable=AsyncMock,
        ) as broadcast,
    ):
        response = client.post(
            "/api/v1/issues/TASK-2/coordination/send",
            json={
                "project_id": "proj-1",
                "recipient": "TASK-1",
                "text": "The result shape changed.",
                "kind": "interface-change",
                "idempotency_key": "shape-v2",
            },
        )

    assert response.status_code == 201
    assert response.json()["message"]["id"] == "message-2"
    orch.coordination_send.assert_called_once_with(
        project_id="proj-1",
        sender="TASK-2",
        recipient="TASK-1",
        text="The result shape changed.",
        kind="interface-change",
        changed_paths=None,
        commit_sha=None,
        idempotency_key="shape-v2",
    )
    broadcast.assert_awaited_once()


def test_send_rejects_non_peer(client):
    orch = _orchestrator()
    orch.coordination_send.side_effect = PermissionError(
        "TASK-9 is not a suggested peer for TASK-2"
    )
    with patch.object(server_module, "_get_orchestrator", return_value=orch):
        response = client.post(
            "/api/v1/issues/TASK-2/coordination/send",
            json={
                "project_id": "proj-1",
                "recipient": "TASK-9",
                "text": "Unscoped message",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "coordination_forbidden"


def test_checkpoint_forwards_changed_path_evidence(client):
    orch = _orchestrator()
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(
            server_module,
            "broadcast_issues",
            new_callable=AsyncMock,
        ),
    ):
        response = client.post(
            "/api/v1/issues/TASK-2/coordination/checkpoint",
            json={
                "project_id": "proj-1",
                "changed_paths": ["oompah/models.py"],
                "head_sha": "a" * 40,
                "summary": "Model changes complete",
            },
        )

    assert response.status_code == 201
    orch.coordination_checkpoint.assert_called_once_with(
        project_id="proj-1",
        identifier="TASK-2",
        changed_paths=["oompah/models.py"],
        commit_sha="a" * 40,
        summary="Model changes complete",
    )


def test_inbox_rejects_invalid_limit(client):
    orch = _orchestrator()
    with patch.object(server_module, "_get_orchestrator", return_value=orch):
        response = client.get(
            "/api/v1/issues/TASK-2/coordination/inbox",
            params={"project_id": "proj-1", "limit": "many"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation"
