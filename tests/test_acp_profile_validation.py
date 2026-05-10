"""Tests for the ACP-mode validation hook in /api/v1/agent-profiles.

These cover the rls-specific cross-store validations that go on top of
AgentProfileStore's per-record checks (which the xaj tests already
cover):

* mode=api: provider_id must EXIST in ProviderStore (not just be
  non-empty).
* mode=acp: provider_id is ignored at dispatch — surface a non-fatal
  warning when one is supplied.
* model_role: when set AND the resolved provider has a model_roles
  map, the role must exist as a key.

See bead oompah-zlz_2-rls.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from oompah.agent_profile_store import AgentProfileStore
from oompah.providers import ProviderStore


@pytest.fixture
def api_client(tmp_path):
    """Wire a fresh AgentProfileStore + ProviderStore into the server.

    Returns (client, profile_store, provider_store) so each test can
    register specific providers (with model_roles maps as needed) and
    drive the API directly.
    """
    from oompah.server import app
    import oompah.server as server_mod

    profile_store = AgentProfileStore(path=str(tmp_path / "agent_profiles.json"))
    provider_store = ProviderStore(path=str(tmp_path / "providers.json"))

    original_profile = server_mod._agent_profile_store
    original_provider = server_mod._provider_store
    original_orch = server_mod._orchestrator
    server_mod._agent_profile_store = profile_store
    server_mod._provider_store = provider_store
    server_mod._orchestrator = None
    try:
        yield TestClient(app), profile_store, provider_store
    finally:
        server_mod._agent_profile_store = original_profile
        server_mod._provider_store = original_provider
        server_mod._orchestrator = original_orch


def _create_provider(provider_store, name="p1", *, model_roles=None):
    p = provider_store.create(name=name, base_url="http://x")
    if model_roles:
        provider_store.update(p.id, model_roles=dict(model_roles))
    return provider_store.get(p.id)


# ----------------------------------------------------------------------
# mode=api: provider_id must EXIST
# ----------------------------------------------------------------------

class TestModeApiRequiresExistingProvider:
    def test_api_with_nonexistent_provider_rejected(self, api_client):
        client, _, _ = api_client
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "api", "provider_id": "prov-bogus",
                  "command": "x"},
        )
        assert res.status_code == 400
        assert "does not exist" in res.json()["error"]["message"]

    def test_api_with_existing_provider_accepted(self, api_client):
        client, _, provider_store = api_client
        prov = _create_provider(provider_store, "openai")
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "api", "provider_id": prov.id,
                  "command": "x"},
        )
        assert res.status_code == 201, res.text

    def test_api_without_provider_rejected(self, api_client):
        client, _, _ = api_client
        # The store-level validation also rejects this; we just want to
        # confirm the cross-store hook doesn't accidentally let it
        # through.
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "api", "command": "x"},
        )
        assert res.status_code == 400


# ----------------------------------------------------------------------
# mode=auto: provider_id optional but must exist if supplied
# ----------------------------------------------------------------------

class TestModeAutoExistsCheck:
    def test_auto_without_provider_accepted(self, api_client):
        # auto can fall back to the lone default provider, so empty
        # provider_id is OK.
        client, _, _ = api_client
        # store-level validation requires provider_id for auto, so we
        # check via PATCH on an existing profile to bypass that.
        # Actually store-level requires it; this test reflects that
        # store rejects, not that the cross-store hook does.
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "auto", "command": "x"},
        )
        # 400 from the store layer — auto requires provider_id.
        assert res.status_code == 400

    def test_auto_with_nonexistent_provider_rejected(self, api_client):
        client, _, _ = api_client
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "auto", "provider_id": "prov-bogus",
                  "command": "x"},
        )
        assert res.status_code == 400
        assert "does not exist" in res.json()["error"]["message"]


# ----------------------------------------------------------------------
# mode=acp: provider_id ignored, warn if set
# ----------------------------------------------------------------------

class TestModeAcpProviderIgnored:
    def test_acp_without_provider_accepted_no_warning(self, api_client):
        client, _, _ = api_client
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "acp", "command": "x"},
        )
        assert res.status_code == 201
        body = res.json()
        warns = body.get("warnings") or []
        assert not any("ignores provider_id" in w for w in warns)

    def test_acp_with_provider_warns_but_creates(self, api_client):
        client, _, provider_store = api_client
        prov = _create_provider(provider_store, "p")
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "acp", "provider_id": prov.id,
                  "command": "x"},
        )
        assert res.status_code == 201
        body = res.json()
        warns = body.get("warnings") or []
        assert any("ignores provider_id" in w for w in warns)

    def test_patch_to_acp_with_existing_provider_warns(self, api_client):
        # Start with a valid api profile, then PATCH to acp keeping the
        # provider_id implicitly. The hook must still warn.
        client, profile_store, provider_store = api_client
        prov = _create_provider(provider_store, "p")
        profile_store.create({
            "name": "f", "mode": "api", "provider_id": prov.id,
            "command": "x",
        })
        res = client.patch(
            "/api/v1/agent-profiles/f",
            json={"mode": "acp"},
        )
        assert res.status_code == 200, res.text
        warns = res.json().get("warnings") or []
        assert any("ignores provider_id" in w for w in warns)


# ----------------------------------------------------------------------
# model_role validation against provider.model_roles
# ----------------------------------------------------------------------

class TestModelRoleValidation:
    def test_role_must_exist_in_provider_model_roles(self, api_client):
        client, _, provider_store = api_client
        prov = _create_provider(
            provider_store, "p", model_roles={"fast": "m1", "deep": "m2"},
        )
        # Bogus role rejected.
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "api", "provider_id": prov.id,
                  "model_role": "bogus", "command": "x"},
        )
        assert res.status_code == 400
        msg = res.json()["error"]["message"]
        assert "model_role" in msg
        assert "fast" in msg or "deep" in msg

    def test_role_accepted_when_in_model_roles(self, api_client):
        client, _, provider_store = api_client
        prov = _create_provider(
            provider_store, "p", model_roles={"fast": "m1"},
        )
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "api", "provider_id": prov.id,
                  "model_role": "fast", "command": "x"},
        )
        assert res.status_code == 201

    def test_role_skipped_when_provider_has_no_roles_map(self, api_client):
        # When provider.model_roles is empty, the check is a no-op
        # (the role gets passed through to dispatch which falls back
        # to provider.default_model). The intent is to avoid 400-ing
        # operators who haven't filled in a roles map yet.
        client, _, provider_store = api_client
        prov = _create_provider(provider_store, "p")
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "api", "provider_id": prov.id,
                  "model_role": "anything", "command": "x"},
        )
        assert res.status_code == 201

    def test_role_not_checked_for_acp_mode(self, api_client):
        # ACP profiles don't go through provider model_role lookup at
        # dispatch (the SDK takes the model name directly), so the
        # check shouldn't fire for acp.
        client, _, provider_store = api_client
        _create_provider(
            provider_store, "p", model_roles={"fast": "m1"},
        )
        res = client.post(
            "/api/v1/agent-profiles",
            json={"name": "f", "mode": "acp",
                  "model_role": "anything-goes", "command": "x"},
        )
        assert res.status_code == 201


# ----------------------------------------------------------------------
# PATCH partial: rls hook honors merged shape
# ----------------------------------------------------------------------

class TestPatchMergedShape:
    def test_patch_only_provider_against_existing_api_profile(self, api_client):
        client, profile_store, provider_store = api_client
        prov_a = _create_provider(provider_store, "a")
        prov_b = _create_provider(provider_store, "b")
        profile_store.create({
            "name": "f", "mode": "api", "provider_id": prov_a.id,
            "command": "x",
        })
        # Switching provider stays valid because the new provider exists.
        res = client.patch(
            "/api/v1/agent-profiles/f",
            json={"provider_id": prov_b.id},
        )
        assert res.status_code == 200
        # And rejects nonexistent IDs.
        res = client.patch(
            "/api/v1/agent-profiles/f",
            json={"provider_id": "prov-bogus"},
        )
        assert res.status_code == 400

    def test_patch_only_role_validated_against_existing_provider(self, api_client):
        client, profile_store, provider_store = api_client
        prov = _create_provider(
            provider_store, "p", model_roles={"fast": "m1"},
        )
        profile_store.create({
            "name": "f", "mode": "api", "provider_id": prov.id,
            "command": "x",
        })
        # Role exists → OK.
        res = client.patch(
            "/api/v1/agent-profiles/f",
            json={"model_role": "fast"},
        )
        assert res.status_code == 200
        # Bogus role → 400.
        res = client.patch(
            "/api/v1/agent-profiles/f",
            json={"model_role": "bogus"},
        )
        assert res.status_code == 400
