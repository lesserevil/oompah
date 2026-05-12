"""HTTP API + UI tests for the /providers role-assignment matrix.

See bead oompah-zlz_2-6xc for design. The matrix maps the four standard
role names (fast/standard/deep/default) to (provider, model) pairs in a
single PUT call against ``/api/v1/agent-profiles/role-matrix``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oompah.agent_profile_store import AgentProfileStore
from oompah.providers import ProviderStore


@pytest.fixture
def matrix_client(tmp_path):
    """Wire fresh ProviderStore + AgentProfileStore into the FastAPI app.

    Pre-seeds two providers (one api, one acp) and the four standard
    profiles (fast/standard/deep/default) so individual tests don't have
    to bootstrap them.
    """
    from oompah import server as server_mod
    from oompah.server import app

    # Clear any cached templates so each test runs in isolation.
    server_mod._template_cache.clear()

    provider_store = ProviderStore(path=str(tmp_path / "providers.json"))
    p_api = provider_store.create(
        name="Godspeed",
        base_url="https://api.godspeed.example",
        models=["nvidia/MiniMax-M2.7", "nvidia/llama3-70b"],
        default_model="nvidia/MiniMax-M2.7",
        provider_type="openai",
        mode="api",
    )
    p_acp = provider_store.create(
        name="InferenceAPI",
        base_url="",
        models=["nvidia/minimaxai/minimax-m2.7"],
        default_model="nvidia/minimaxai/minimax-m2.7",
        provider_type="openai",
        mode="acp",
        acp_permission_mode="default",
        acp_subscription_only=True,
    )

    agent_store = AgentProfileStore(path=str(tmp_path / "agent_profiles.json"))
    # Seed the four standard profiles all pointing at the api provider
    # initially. Tests will reassign via the matrix.
    for role in ("fast", "standard", "deep", "default"):
        agent_store.create({
            "name": role,
            "command": "claude --foo",
            "mode": "api",
            "provider_id": p_api.id,
            "model": "nvidia/MiniMax-M2.7",
            "model_role": role,
        })
    # Add an unrelated specialty profile that the matrix MUST NOT touch.
    agent_store.create({
        "name": "merge_conflict",
        "command": "claude --foo",
        "mode": "api",
        "provider_id": p_api.id,
        "model": "nvidia/llama3-70b",
        "model_role": "deep",
    })

    original_provider_store = server_mod._provider_store
    original_profile_store = server_mod._agent_profile_store
    original_orch = server_mod._orchestrator

    server_mod._provider_store = provider_store
    server_mod._agent_profile_store = agent_store
    server_mod._orchestrator = None  # disable reload hook in tests

    try:
        client = TestClient(app)
        yield {
            "client": client,
            "provider_store": provider_store,
            "profile_store": agent_store,
            "p_api": p_api,
            "p_acp": p_acp,
        }
    finally:
        server_mod._provider_store = original_provider_store
        server_mod._agent_profile_store = original_profile_store
        server_mod._orchestrator = original_orch


# ----------------------------------------------------------------------
# GET /api/v1/agent-profiles/role-matrix
# ----------------------------------------------------------------------


class TestGetRoleMatrix:
    def test_returns_four_rows(self, matrix_client):
        client = matrix_client["client"]
        r = client.get("/api/v1/agent-profiles/role-matrix")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        rows = data["rows"]
        assert [row["role"] for row in rows] == [
            "fast", "standard", "deep", "default",
        ]

    def test_resolved_status_when_clean(self, matrix_client):
        client = matrix_client["client"]
        r = client.get("/api/v1/agent-profiles/role-matrix")
        rows = r.json()["rows"]
        for row in rows:
            assert row["status"] == "resolved", row

    def test_includes_provider_mode(self, matrix_client):
        client = matrix_client["client"]
        r = client.get("/api/v1/agent-profiles/role-matrix")
        rows = r.json()["rows"]
        # All four are seeded against the api-mode provider.
        for row in rows:
            assert row["provider_mode"] == "api", row

    def test_missing_profile_status(self, matrix_client):
        # Delete the "fast" profile and re-fetch. Status should reflect
        # the missing profile.
        store = matrix_client["profile_store"]
        store.delete("fast")
        client = matrix_client["client"]
        r = client.get("/api/v1/agent-profiles/role-matrix")
        rows = r.json()["rows"]
        fast = next(row for row in rows if row["role"] == "fast")
        assert fast["status"] == "missing_profile"
        # Other rows still resolved.
        for row in rows:
            if row["role"] != "fast":
                assert row["status"] == "resolved", row

    def test_missing_provider_status(self, matrix_client):
        # Point the "deep" profile at a vanished provider and verify.
        store = matrix_client["profile_store"]
        store.update("deep", provider_id="prov-vanished")
        client = matrix_client["client"]
        r = client.get("/api/v1/agent-profiles/role-matrix")
        rows = r.json()["rows"]
        deep = next(row for row in rows if row["role"] == "deep")
        assert deep["status"] == "missing_provider"

    def test_missing_model_status(self, matrix_client):
        # Reassign "standard" to an explicit model that's NOT in the
        # provider's catalog.
        store = matrix_client["profile_store"]
        store.update("standard", model="nvidia/not-real-model")
        client = matrix_client["client"]
        r = client.get("/api/v1/agent-profiles/role-matrix")
        rows = r.json()["rows"]
        standard = next(row for row in rows if row["role"] == "standard")
        assert standard["status"] == "missing_model"


# ----------------------------------------------------------------------
# PUT /api/v1/agent-profiles/role-matrix — happy path
# ----------------------------------------------------------------------


class TestPutRoleMatrixHappy:
    def test_round_trip(self, matrix_client):
        """Saving (fast=acp/minimax, standard=api/llama3, ...) reflects in GET."""
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        p_acp = matrix_client["p_acp"]
        body = {
            "fast": {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/llama3-70b"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 200, r.text
        rows = r.json()["rows"]
        assert {row["role"]: row["status"] for row in rows} == {
            "fast": "resolved",
            "standard": "resolved",
            "deep": "resolved",
            "default": "resolved",
        }

    def test_each_role_updates_its_own_profile(self, matrix_client):
        """Verify the right profile got the right (provider, model) pair."""
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        p_acp = matrix_client["p_acp"]
        body = {
            "fast": {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/llama3-70b"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 200, r.text

        store = matrix_client["profile_store"]
        fast = store.get("fast")
        assert fast.provider_id == p_acp.id
        assert fast.model == "nvidia/minimaxai/minimax-m2.7"
        assert fast.model_role == "fast"

        standard = store.get("standard")
        assert standard.provider_id == p_api.id
        assert standard.model == "nvidia/llama3-70b"
        assert standard.model_role == "standard"

    def test_specialty_profile_untouched(self, matrix_client):
        """``merge_conflict`` (not in the matrix) must not be modified."""
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        p_acp = matrix_client["p_acp"]
        store = matrix_client["profile_store"]
        before = store.get("merge_conflict")
        before_dict = before.to_dict()

        body = {
            "fast": {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/llama3-70b"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 200, r.text

        after = store.get("merge_conflict")
        assert after.to_dict() == before_dict

    def test_persists_through_get(self, matrix_client):
        """A PUT followed by a GET reflects the new assignments."""
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        p_acp = matrix_client["p_acp"]
        body = {
            "fast": {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
            "standard": {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
            "deep": {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 200

        r2 = client.get("/api/v1/agent-profiles/role-matrix")
        rows = r2.json()["rows"]
        by_role = {row["role"]: row for row in rows}
        assert by_role["fast"]["provider_id"] == p_acp.id
        assert by_role["fast"]["provider_mode"] == "acp"
        assert by_role["fast"]["model"] == "nvidia/minimaxai/minimax-m2.7"
        assert by_role["default"]["provider_mode"] == "api"

    def test_other_profile_fields_preserved(self, matrix_client):
        """Updating provider/model must not clobber unrelated fields."""
        client = matrix_client["client"]
        store = matrix_client["profile_store"]
        # Set extra fields on "fast" first.
        store.update(
            "fast",
            command="claude --custom",
            max_turns=42,
            keywords=["typo", "lint"],
            issue_types=["chore"],
            min_priority=0,
            max_priority=4,
        )
        p_acp = matrix_client["p_acp"]
        p_api = matrix_client["p_api"]
        body = {
            "fast": {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/llama3-70b"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 200

        fast = store.get("fast")
        assert fast.command == "claude --custom"
        assert fast.max_turns == 42
        assert fast.keywords == ["typo", "lint"]
        assert fast.issue_types == ["chore"]
        assert fast.min_priority == 0
        assert fast.max_priority == 4


# ----------------------------------------------------------------------
# PUT /api/v1/agent-profiles/role-matrix — validation
# ----------------------------------------------------------------------


class TestPutRoleMatrixValidation:
    def test_rejects_unknown_provider(self, matrix_client):
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        body = {
            "fast": {"provider_id": "prov-bogus", "model": "anything"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 400
        assert "prov-bogus" in r.json()["error"]["message"]

    def test_rejects_model_not_in_catalog(self, matrix_client):
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        body = {
            "fast": {"provider_id": p_api.id, "model": "nvidia/not-listed"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 400
        msg = r.json()["error"]["message"]
        assert "nvidia/not-listed" in msg
        assert "Godspeed" in msg

    def test_rejects_missing_role(self, matrix_client):
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        body = {
            "fast": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            # "standard" missing
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 400
        assert "standard" in r.json()["error"]["message"]

    def test_rejects_empty_provider_id(self, matrix_client):
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        body = {
            "fast": {"provider_id": "", "model": "nvidia/MiniMax-M2.7"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 400

    def test_rejects_empty_model(self, matrix_client):
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        body = {
            "fast": {"provider_id": p_api.id, "model": ""},
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 400

    def test_rejects_non_object_body(self, matrix_client):
        client = matrix_client["client"]
        r = client.put("/api/v1/agent-profiles/role-matrix", json=["not", "an", "object"])
        assert r.status_code == 400

    def test_rejects_row_not_object(self, matrix_client):
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        body = {
            "fast": "not-a-dict",
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 400

    def test_rejects_missing_role_profile(self, matrix_client):
        """If a target profile (e.g. 'fast') doesn't exist in the store, fail."""
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        store = matrix_client["profile_store"]
        store.delete("fast")
        body = {
            "fast": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 400
        assert "fast" in r.json()["error"]["message"]


# ----------------------------------------------------------------------
# Atomicity: a partially-bad payload must not leave any profile mutated
# ----------------------------------------------------------------------


class TestPutRoleMatrixAtomicity:
    def test_validation_failure_leaves_profiles_unchanged(self, matrix_client):
        """A 400 response means NO profile was modified."""
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        p_acp = matrix_client["p_acp"]
        store = matrix_client["profile_store"]

        # Snapshot all profiles before the bad request.
        before = {
            name: store.get(name).to_dict()
            for name in ("fast", "standard", "deep", "default", "merge_conflict")
        }

        # Three-good, one-bad payload. The "deep" row uses an unknown
        # provider — should bounce the entire request.
        body = {
            "fast": {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
            "standard": {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
            "deep": {"provider_id": "prov-vanished", "model": "anything"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 400

        # Every profile must be byte-identical to before.
        after = {
            name: store.get(name).to_dict()
            for name in ("fast", "standard", "deep", "default", "merge_conflict")
        }
        assert after == before

    def test_acp_provider_with_no_catalog_accepts_any_model(self, matrix_client):
        """ACP-mode providers with empty catalog skip the model-membership check.

        The Claude Agent SDK manages the model catalog out-of-band so
        the matrix should not block on an empty provider.models list.
        Provider with non-empty catalog still enforces membership.
        """
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        provider_store = matrix_client["provider_store"]
        # Strip the ACP provider's catalog.
        provider_store.update(matrix_client["p_acp"].id, models=[])
        p_acp_id = matrix_client["p_acp"].id

        body = {
            "fast": {"provider_id": p_acp_id, "model": "claude-sonnet-4-6"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 200, r.text


# ----------------------------------------------------------------------
# UI smoke: providers.html renders the matrix scaffolding
# ----------------------------------------------------------------------


class TestProvidersHtmlMatrixScaffold:
    """Static template smoke tests — verify the matrix DOM nodes exist
    in providers.html. Mirrors the pattern in tests/test_providers_ui.py.
    """

    @pytest.fixture
    def html(self) -> str:
        path = Path(__file__).parent.parent / "oompah" / "templates" / "providers.html"
        return path.read_text()

    def test_role_matrix_container_present(self, html):
        assert 'id="role-matrix-container"' in html

    def test_role_matrix_save_button_present(self, html):
        assert 'id="role-matrix-save"' in html
        assert "saveRoleMatrix()" in html

    def test_role_matrix_renders_four_roles(self, html):
        # The roles array is hard-coded in the JS for v1.
        assert "['fast', 'standard', 'deep', 'default']" in html

    def test_render_function_exists(self, html):
        assert "function renderRoleMatrix" in html

    def test_change_handler_exists(self, html):
        assert "function onRoleMatrixChange" in html

    def test_save_function_exists(self, html):
        assert "async function saveRoleMatrix" in html

    def test_status_classes_present(self, html):
        # CSS for the three status colors used by computeRoleMatrixStatus.
        assert ".status-resolved" in html
        assert ".status-warn" in html

    def test_uses_put_endpoint(self, html):
        assert "/api/v1/agent-profiles/role-matrix" in html
        assert "method: 'PUT'" in html

    def test_matrix_table_columns(self, html):
        # The four header cells.
        for col in ("Role", "Provider", "Model", "Mode", "Status"):
            assert f">{col}<" in html
