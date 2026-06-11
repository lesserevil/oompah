"""HTTP API tests for /api/v1/agent-profiles."""

import json
import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from oompah.agent_profile_store import AgentProfileStore


@pytest.fixture
def api_with_store(tmp_path, monkeypatch):
    """Return (client, store) with a fresh AgentProfileStore wired into server.

    Also wires a fresh ProviderStore with a single ``prov-1`` entry so
    the rls validation hook (mode=api requires an EXISTING provider_id)
    can succeed without each test re-registering one.
    """
    from oompah.server import app
    from oompah.providers import ProviderStore
    import oompah.server as server_mod

    path = str(tmp_path / "agent_profiles.json")
    store = AgentProfileStore(path=path)

    provider_store = ProviderStore(path=str(tmp_path / "providers.json"))
    # Pre-register a single provider with id "prov-1" so existing tests
    # that hardcode that id keep working under the rls validation hook.
    p = provider_store.create(name="test-provider", base_url="http://x")
    # Coerce the id to "prov-1" for tests that hardcode it.
    provider_store._providers["prov-1"] = provider_store._providers.pop(p.id)
    provider_store._providers["prov-1"].id = "prov-1"
    provider_store._save()

    original_store = server_mod._agent_profile_store
    original_orch = server_mod._orchestrator
    original_provider_store = server_mod._provider_store
    server_mod._agent_profile_store = store
    server_mod._provider_store = provider_store
    server_mod._orchestrator = None  # disable reload hook for tests
    try:
        client = TestClient(app)
        yield client, store
    finally:
        server_mod._agent_profile_store = original_store
        server_mod._orchestrator = original_orch
        server_mod._provider_store = original_provider_store


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

    def test_create_missing_name_returns_400(self, api_with_store):
        """POST without a 'name' field returns 400 with a message mentioning 'name'."""
        client, _ = api_with_store
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"mode": "cli"},
        )
        assert resp.status_code == 400
        assert "name" in resp.json()["error"]["message"]

    def test_create_invalid_json_body_returns_400(self, api_with_store):
        """POST with a non-JSON body returns 400."""
        client, _ = api_with_store
        resp = client.post(
            "/api/v1/agent-profiles",
            content="not-json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_create_extra_fields_silently_dropped(self, api_with_store):
        """Unknown fields in the POST body are ignored, not rejected."""
        client, _ = api_with_store
        resp = client.post(
            "/api/v1/agent-profiles",
            json={
                "name": "ok",
                "mode": "cli",
                "command": "claude",
                "spam": "should be ignored",
            },
        )
        assert resp.status_code == 201, resp.text
        # Unknown field must not appear in the response (only known fields serialized).
        assert "spam" not in resp.json()


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
    """Successful CRUD ops should trigger Orchestrator.replace_agent_profiles
    (partial reload) so the new profile list takes effect on the next dispatch
    tick without a WORKFLOW.md round-trip (oompah-zlz_2-mif).
    """

    def test_create_triggers_reload(self, tmp_path, monkeypatch):
        from oompah.server import app
        import oompah.server as server_mod

        path = str(tmp_path / "agent_profiles.json")
        store = AgentProfileStore(path=path)

        # Mimic what set_orchestrator() wires: register a reload callback
        # that calls replace_agent_profiles on the orchestrator.
        mock_orch = MagicMock()
        store.set_reload_callback(
            lambda profs, src: mock_orch.replace_agent_profiles(
                profs, source=f"api:{src}",
            ),
        )

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
            # replace_agent_profiles should have been called once with
            # source='api:create'
            assert mock_orch.replace_agent_profiles.call_count == 1
            _, kwargs = mock_orch.replace_agent_profiles.call_args
            assert kwargs.get("source") == "api:create"
            # Workflow round-trip MUST NOT happen — mif explicitly avoids it
            assert mock_orch.reload_config.call_count == 0
        finally:
            server_mod._agent_profile_store = original_store
            server_mod._orchestrator = original_orch

    def test_validation_failure_does_not_reload(self, tmp_path):
        from oompah.server import app
        import oompah.server as server_mod

        path = str(tmp_path / "agent_profiles.json")
        store = AgentProfileStore(path=path)
        mock_orch = MagicMock()
        store.set_reload_callback(
            lambda profs, src: mock_orch.replace_agent_profiles(
                profs, source=f"api:{src}",
            ),
        )
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
            assert mock_orch.replace_agent_profiles.call_count == 0
            assert mock_orch.reload_config.call_count == 0
        finally:
            server_mod._agent_profile_store = original_store
            server_mod._orchestrator = original_orch
