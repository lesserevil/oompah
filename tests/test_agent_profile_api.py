"""HTTP API tests for /api/v1/agent-profiles."""

import json
import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from oompah.agent_profile_store import AgentProfileStore


@pytest.fixture
def api_with_store(tmp_path, monkeypatch):
    """Return (client, store) with a fresh AgentProfileStore wired into server."""
    from oompah.server import app
    import oompah.server as server_mod

    path = str(tmp_path / "agent_profiles.json")
    store = AgentProfileStore(path=path)

    original_store = server_mod._agent_profile_store
    original_orch = server_mod._orchestrator
    server_mod._agent_profile_store = store
    server_mod._orchestrator = None  # disable reload hook for tests
    try:
        client = TestClient(app)
        yield client, store
    finally:
        server_mod._agent_profile_store = original_store
        server_mod._orchestrator = original_orch


class TestListAgentProfiles:
    def test_empty(self, api_with_store):
        client, _ = api_with_store
        resp = client.get("/api/v1/agent-profiles")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_lists_profiles(self, api_with_store):
        client, store = api_with_store
        store.create({"name": "fast", "command": "x", "mode": "cli"})
        store.create({"name": "slow", "command": "y", "mode": "acp"})
        resp = client.get("/api/v1/agent-profiles")
        assert resp.status_code == 200
        names = sorted(p["name"] for p in resp.json())
        assert names == ["fast", "slow"]


class TestCreateAgentProfile:
    def test_create_minimal(self, api_with_store):
        client, store = api_with_store
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "p1", "command": "claude", "mode": "cli"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "p1"
        # Persisted in the store
        assert store.get("p1") is not None

    def test_create_acp_no_provider(self, api_with_store):
        client, _ = api_with_store
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "claude-sub", "command": "claude --acp", "mode": "acp"},
        )
        assert resp.status_code == 201

    def test_create_api_requires_provider(self, api_with_store):
        client, _ = api_with_store
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "x", "command": "y", "mode": "api"},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "provider_id" in body["error"]["message"]

    def test_create_auto_requires_provider(self, api_with_store):
        client, _ = api_with_store
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "x", "command": "y", "mode": "auto"},
        )
        assert resp.status_code == 400

    def test_create_bad_mode(self, api_with_store):
        client, _ = api_with_store
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "x", "command": "y", "mode": "weird"},
        )
        assert resp.status_code == 400

    def test_create_duplicate_name(self, api_with_store):
        client, store = api_with_store
        store.create({"name": "x", "command": "c", "mode": "cli"})
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "x", "command": "c", "mode": "cli"},
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["error"]["message"]

    def test_create_non_object_body(self, api_with_store):
        client, _ = api_with_store
        resp = client.post(
            "/api/v1/agent-profiles",
            json=["not", "an", "object"],
        )
        assert resp.status_code == 400


class TestUpdateAgentProfile:
    def test_patch_partial(self, api_with_store):
        client, store = api_with_store
        store.create({"name": "p1", "command": "c", "mode": "cli"})
        resp = client.patch(
            "/api/v1/agent-profiles/p1",
            json={"command": "new-cmd"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["command"] == "new-cmd"
        # Mode preserved
        assert resp.json()["mode"] == "cli"

    def test_patch_change_mode_to_api(self, api_with_store):
        client, store = api_with_store
        store.create({"name": "p1", "command": "c", "mode": "cli"})
        # Without provider_id -> 400
        resp = client.patch(
            "/api/v1/agent-profiles/p1",
            json={"mode": "api"},
        )
        assert resp.status_code == 400
        # With provider_id -> 200
        resp = client.patch(
            "/api/v1/agent-profiles/p1",
            json={"mode": "api", "provider_id": "prov-1"},
        )
        assert resp.status_code == 200

    def test_patch_rename(self, api_with_store):
        client, store = api_with_store
        store.create({"name": "old", "command": "c", "mode": "cli"})
        resp = client.patch(
            "/api/v1/agent-profiles/old",
            json={"name": "new"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "new"
        assert store.get("old") is None
        assert store.get("new") is not None

    def test_patch_rename_collision(self, api_with_store):
        client, store = api_with_store
        store.create({"name": "a", "command": "c", "mode": "cli"})
        store.create({"name": "b", "command": "c", "mode": "cli"})
        resp = client.patch(
            "/api/v1/agent-profiles/a",
            json={"name": "b"},
        )
        assert resp.status_code == 400

    def test_patch_unknown(self, api_with_store):
        client, _ = api_with_store
        resp = client.patch(
            "/api/v1/agent-profiles/missing",
            json={"command": "x"},
        )
        assert resp.status_code == 404


class TestDeleteAgentProfile:
    def test_delete_existing(self, api_with_store):
        client, store = api_with_store
        store.create({"name": "x", "command": "c", "mode": "cli"})
        resp = client.delete("/api/v1/agent-profiles/x")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert store.get("x") is None

    def test_delete_unknown(self, api_with_store):
        client, _ = api_with_store
        resp = client.delete("/api/v1/agent-profiles/missing")
        assert resp.status_code == 404


class TestReloadHook:
    """Successful CRUD ops should trigger orchestrator.reload_config so the
    new profile list is in effect on the next dispatch tick."""

    def test_create_triggers_reload(self, tmp_path, monkeypatch):
        from oompah.server import app
        import oompah.server as server_mod

        path = str(tmp_path / "agent_profiles.json")
        store = AgentProfileStore(path=path)

        mock_orch = MagicMock()
        mock_orch.workflow_path = str(tmp_path / "WORKFLOW.md")
        # Write a minimal valid workflow
        with open(mock_orch.workflow_path, "w") as f:
            f.write("---\n---\nTemplate.")

        original_store = server_mod._agent_profile_store
        original_orch = server_mod._orchestrator
        server_mod._agent_profile_store = store
        server_mod._orchestrator = mock_orch
        try:
            client = TestClient(app)
            resp = client.post(
                "/api/v1/agent-profiles",
                json={"name": "x", "command": "c", "mode": "cli"},
            )
            assert resp.status_code == 201
            # reload_config should have been called once
            assert mock_orch.reload_config.call_count == 1
        finally:
            server_mod._agent_profile_store = original_store
            server_mod._orchestrator = original_orch

    def test_validation_failure_does_not_reload(self, tmp_path):
        from oompah.server import app
        import oompah.server as server_mod

        path = str(tmp_path / "agent_profiles.json")
        store = AgentProfileStore(path=path)
        mock_orch = MagicMock()
        mock_orch.workflow_path = "doesnt-matter"
        original_store = server_mod._agent_profile_store
        original_orch = server_mod._orchestrator
        server_mod._agent_profile_store = store
        server_mod._orchestrator = mock_orch
        try:
            client = TestClient(app)
            resp = client.post(
                "/api/v1/agent-profiles",
                json={"name": "x", "command": "c", "mode": "api"},  # missing provider
            )
            assert resp.status_code == 400
            assert mock_orch.reload_config.call_count == 0
        finally:
            server_mod._agent_profile_store = original_store
            server_mod._orchestrator = original_orch
