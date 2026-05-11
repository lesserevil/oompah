"""Tests for /api/v1/agent-profiles endpoints (oompah-zlz_2-xaj / -mif)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.agent_profile_store import AgentProfileStore
from oompah.config import ServiceConfig
from oompah.models import AgentProfile
from oompah.orchestrator import Orchestrator
from oompah.server import app


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Replace the global agent profile store with a tmp_path-backed one
    so tests don't write to .oompah/agent_profiles.json."""
    path = tmp_path / "agent_profiles.json"
    store = AgentProfileStore(path=str(path))
    server_module._set_agent_profile_store(store)
    yield store
    # Restore a fresh empty store afterwards.
    server_module._set_agent_profile_store(AgentProfileStore())


@pytest.fixture
def orch(tmp_path):
    cfg = ServiceConfig(workspace_root=str(tmp_path / "ws"))
    cfg.agent_profiles = [AgentProfile(name="default", command="claude", mode="cli")]
    o = Orchestrator(
        cfg, str(tmp_path / "WORKFLOW.md"),
        state_path=str(tmp_path / "service_state.json"),
    )
    return o


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestList:
    def test_empty(self, isolated_store, client):
        resp = client.get("/api/v1/agent-profiles")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_existing(self, isolated_store, client):
        isolated_store.create({"name": "quick", "mode": "cli", "command": "claude"})
        resp = client.get("/api/v1/agent-profiles")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "quick"
        assert body[0]["mode"] == "cli"


class TestCreate:
    def test_minimal_cli(self, isolated_store, client):
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "quick", "mode": "cli", "command": "claude"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["name"] == "quick"
        # Persisted in the store
        assert isolated_store.get("quick") is not None

    def test_missing_name_400(self, isolated_store, client):
        resp = client.post("/api/v1/agent-profiles", json={"mode": "cli"})
        assert resp.status_code == 400
        assert "name" in resp.json()["error"]["message"]

    def test_duplicate_name_400(self, isolated_store, client):
        isolated_store.create({"name": "dup", "mode": "cli", "command": "claude"})
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "dup", "mode": "cli", "command": "claude"},
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["error"]["message"]

    def test_api_mode_without_provider_id_400(self, isolated_store, client):
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "x", "mode": "api"},
        )
        assert resp.status_code == 400
        assert "provider_id" in resp.json()["error"]["message"]

    def test_acp_mode_succeeds_without_provider_id(self, isolated_store, client):
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "claude-acp", "mode": "acp", "command": "claude"},
        )
        assert resp.status_code == 201, resp.text

    def test_invalid_json_body_400(self, isolated_store, client):
        resp = client.post(
            "/api/v1/agent-profiles",
            content="not-json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_extra_fields_silently_dropped(self, isolated_store, client):
        # Unknown fields (e.g., 'spam') must not 400 — they're ignored.
        # This preserves forward-compat with clients that might send extras.
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
        # And it's NOT exposed in the response (we serialize only known fields).
        assert "spam" not in resp.json()


class TestUpdate:
    def test_partial_update(self, isolated_store, client):
        isolated_store.create({"name": "a", "mode": "cli", "command": "claude"})
        resp = client.patch(
            "/api/v1/agent-profiles/a",
            json={"model": "claude-sonnet-4"},
        )
        assert resp.status_code == 200
        assert resp.json()["model"] == "claude-sonnet-4"

    def test_rename_via_patch(self, isolated_store, client):
        isolated_store.create({"name": "old", "mode": "cli", "command": "claude"})
        resp = client.patch(
            "/api/v1/agent-profiles/old",
            json={"name": "new"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "new"
        assert isolated_store.get("old") is None
        assert isolated_store.get("new") is not None

    def test_404_on_missing(self, isolated_store, client):
        resp = client.patch(
            "/api/v1/agent-profiles/ghost",
            json={"model": "x"},
        )
        assert resp.status_code == 404

    def test_invalid_mode_400(self, isolated_store, client):
        isolated_store.create({"name": "x", "mode": "cli", "command": "claude"})
        resp = client.patch(
            "/api/v1/agent-profiles/x",
            json={"mode": "api"},  # missing provider_id
        )
        assert resp.status_code == 400


class TestDelete:
    def test_deletes(self, isolated_store, client):
        isolated_store.create({"name": "a", "mode": "cli", "command": "claude"})
        resp = client.delete("/api/v1/agent-profiles/a")
        assert resp.status_code == 200
        assert isolated_store.get("a") is None

    def test_404_on_missing(self, isolated_store, client):
        resp = client.delete("/api/v1/agent-profiles/ghost")
        assert resp.status_code == 404


class TestLiveReload:
    """Verify a write through the API triggers Orchestrator.replace_agent_profiles."""

    def test_create_triggers_orch_reload(
        self, isolated_store, client, orch, monkeypatch,
    ):
        # Wire the orchestrator via set_orchestrator() so the callback fires.
        # set_orchestrator does more than we need (error_watcher, log watcher)
        # — we just want the agent-profile callback wiring. So we wire the
        # callback directly to mirror what set_orchestrator does.
        isolated_store.set_reload_callback(
            lambda profs, src: orch.replace_agent_profiles(profs, source=f"api:{src}"),
        )

        # POST a new profile via the API
        resp = client.post(
            "/api/v1/agent-profiles",
            json={"name": "quick", "mode": "cli", "command": "claude"},
        )
        assert resp.status_code == 201

        # Before tick: pending swap queued, config still on the seed list.
        assert [p.name for p in orch.config.agent_profiles] == ["default"]

        # Simulate tick: pending swap applies.
        orch._apply_pending_agent_profiles()
        names = sorted(p.name for p in orch.config.agent_profiles)
        # The store had no other profiles, so the swap is just ['quick'].
        # (The seed 'default' was on cfg, not in the store.)
        assert names == ["quick"]

    def test_api_reload_logs_with_api_source(
        self, isolated_store, client, orch, caplog,
    ):
        import logging
        isolated_store.set_reload_callback(
            lambda profs, src: orch.replace_agent_profiles(profs, source=f"api:{src}"),
        )
        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            client.post(
                "/api/v1/agent-profiles",
                json={"name": "quick", "mode": "cli", "command": "claude"},
            )
        assert any(
            "Agent profiles reload queued" in rec.message
            and "api:create" in rec.message
            for rec in caplog.records
        )
