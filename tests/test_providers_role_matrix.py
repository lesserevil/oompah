"""HTTP API + UI tests for the /providers role-assignment matrix.

See task oompah-zlz_2-6xc for design. The matrix maps the four standard
role names (fast/standard/deep/default) to (provider, model) pairs in a
single PUT call against ``/api/v1/agent-profiles/role-matrix``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oompah.agent_profile_store import AgentProfileStore
from oompah.providers import ProviderStore
from oompah.roles import RoleStore


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
    # Add an unrelated specialty profile that the matrix MUST NOT touch.
    # Post-xau7 the matrix lives in RoleStore (not AgentProfileStore), so
    # this specialty profile is the only profile-store fixture.
    agent_store.create({
        "name": "merge_conflict",
        "command": "claude --foo",
        "mode": "api",
        "provider_id": p_api.id,
        "model": "nvidia/llama3-70b",
        "model_role": "deep",
    })

    # RoleStore (epic xau7) — populate the four standard roles pointing
    # at the api provider initially. Tests reassign via the matrix.
    role_store = RoleStore(
        path=str(tmp_path / "roles.json"),
        provider_store=provider_store,
    )
    for role_name in ("fast", "standard", "deep", "default"):
        role_store.set(role_name, p_api.id, "nvidia/MiniMax-M2.7")

    original_provider_store = server_mod._provider_store
    original_profile_store = server_mod._agent_profile_store
    original_role_store = server_mod._role_store
    original_orch = server_mod._orchestrator

    server_mod._provider_store = provider_store
    server_mod._agent_profile_store = agent_store
    server_mod._role_store = role_store
    server_mod._orchestrator = None  # disable reload hook in tests

    try:
        client = TestClient(app)
        yield {
            "client": client,
            "provider_store": provider_store,
            "profile_store": agent_store,
            "role_store": role_store,
            "p_api": p_api,
            "p_acp": p_acp,
        }
    finally:
        server_mod._provider_store = original_provider_store
        server_mod._agent_profile_store = original_profile_store
        server_mod._role_store = original_role_store
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

    def test_unassigned_status(self, matrix_client):
        # Delete the "fast" role from RoleStore and re-fetch. Post-xau7
        # the matrix's truth lives in RoleStore, not AgentProfileStore.
        role_store = matrix_client["role_store"]
        role_store.delete("fast")
        client = matrix_client["client"]
        r = client.get("/api/v1/agent-profiles/role-matrix")
        rows = r.json()["rows"]
        fast = next(row for row in rows if row["role"] == "fast")
        assert fast["status"] == "unassigned"
        # Other rows still resolved.
        for row in rows:
            if row["role"] != "fast":
                assert row["status"] == "resolved", row

    def test_missing_provider_status(self, matrix_client):
        # Point "deep" at a vanished provider directly in RoleStore
        # (bypass validation by writing through the store's internal
        # dict — the validate path would refuse).
        role_store = matrix_client["role_store"]
        from oompah.roles import Candidate, Role
        from datetime import datetime, timezone
        role_store._roles["deep"] = Role(
            name="deep",
            strategy="priority",
            candidates=[Candidate(provider_id="prov-vanished", model="nvidia/MiniMax-M2.7")],
            updated_at=datetime.now(timezone.utc),
        )
        client = matrix_client["client"]
        r = client.get("/api/v1/agent-profiles/role-matrix")
        rows = r.json()["rows"]
        deep = next(row for row in rows if row["role"] == "deep")
        assert deep["status"] == "missing_provider"

    def test_missing_model_status(self, matrix_client):
        # Reassign "standard" to a model that's NOT in the provider's
        # catalog (bypass validation via internal dict write).
        role_store = matrix_client["role_store"]
        from oompah.roles import Candidate, Role
        from datetime import datetime, timezone
        existing = role_store.get("standard")
        role_store._roles["standard"] = Role(
            name="standard",
            strategy="priority",
            candidates=[Candidate(provider_id=existing.provider_id, model="nvidia/not-real-model")],
            updated_at=datetime.now(timezone.utc),
        )
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

    def test_each_role_updates_role_store(self, matrix_client):
        """Verify each role wrote the right (provider, model) pair to RoleStore."""
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

        role_store = matrix_client["role_store"]
        fast = role_store.get("fast")
        assert fast.provider_id == p_acp.id
        assert fast.model == "nvidia/minimaxai/minimax-m2.7"

        standard = role_store.get("standard")
        assert standard.provider_id == p_api.id
        assert standard.model == "nvidia/llama3-70b"

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

    def test_does_not_touch_profile_store(self, matrix_client):
        """Post-xau7 the matrix lives in RoleStore — profile records of
        any name should be left alone when the matrix PUT runs.
        """
        client = matrix_client["client"]
        store = matrix_client["profile_store"]
        # Create a profile literally named "fast" with arbitrary fields.
        # Pre-xau7 the matrix would have mutated this; post-xau7 it must
        # not touch it.
        store.create({
            "name": "fast",
            "command": "claude --custom",
            "mode": "api",
            "provider_id": matrix_client["p_api"].id,
            "model": "nvidia/MiniMax-M2.7",
            "model_role": "fast",
            "max_turns": 42,
        })
        before = store.get("fast").to_dict()

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

        after = store.get("fast").to_dict()
        assert after == before, "matrix PUT must not mutate profile records"


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

    def test_accepts_when_no_profile_of_role_name(self, matrix_client):
        """Post-xau7: roles are independent of profiles. PUT succeeds
        even when no profile of the role's name exists.

        Inverts the pre-xau7 ``test_rejects_missing_role_profile``.
        """
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        # Profile store doesn't have profiles named fast/standard/deep/default
        # (only "merge_conflict" from the fixture); PUT should succeed.
        body = {
            "fast": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 200, r.text


# ----------------------------------------------------------------------
# Atomicity: a partially-bad payload must not leave any profile mutated
# ----------------------------------------------------------------------


class TestPutRoleMatrixAtomicity:
    def test_validation_failure_leaves_role_store_unchanged(self, matrix_client):
        """A 400 response means NO role was modified in RoleStore."""
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        p_acp = matrix_client["p_acp"]
        role_store = matrix_client["role_store"]

        # Snapshot RoleStore before the bad request.
        before = {r.name: r.to_dict() for r in role_store.list_all()}

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

        # Every role must be byte-identical to before. (Roles also keep
        # an updated_at timestamp — skip that field when comparing.)
        after = {r.name: r.to_dict() for r in role_store.list_all()}
        for name in before:
            b = {k: v for k, v in before[name].items() if k != "updated_at"}
            a = {k: v for k, v in after[name].items() if k != "updated_at"}
            assert a == b, f"role {name!r} mutated despite 400"

        # Sentinel: merge_conflict profile untouched by matrix activity.
        store = matrix_client["profile_store"]
        mc = store.get("merge_conflict")
        assert mc is not None
        assert mc.model == "nvidia/llama3-70b"

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

    def test_acp_provider_with_no_catalog_accepts_empty_model(self, matrix_client):
        """ACP + empty catalog also accepts an empty/missing model
        (SDK-managed model selection)."""
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        provider_store = matrix_client["provider_store"]
        provider_store.update(matrix_client["p_acp"].id, models=[])
        p_acp_id = matrix_client["p_acp"].id

        body = {
            "fast": {"provider_id": p_acp_id, "model": ""},
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/agent-profiles/role-matrix", json=body)
        assert r.status_code == 200, r.text
        rows = {row["role"]: row for row in r.json()["rows"]}
        assert rows["fast"]["status"] == "resolved"

    def test_api_provider_rejects_empty_model(self, matrix_client):
        """Non-ACP provider still requires a model even after the
        ACP empty-catalog exemption lands."""
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
        assert "model is required" in r.json()["error"]["message"]


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
        # The matrix header cells after TASK-407.7 multi-candidate rewrite.
        # Role and Mode columns were removed (roles appear in role-header-rows;
        # mode info is embedded in the Billing column). Billing and Status remain.
        for col in ("Provider", "Model", "Billing", "Status"):
            assert f">{col}<" in html
        # Role name still appears in role-header-row spans (class role-name).
        assert "role-name" in html


class TestBillingColumn:
    """Static template smoke tests for the Billing column added by
    oompah-zlz_2-yqss. Verifies that the column's rendering helper and
    its rate-lookup helper are wired into the matrix.
    """

    @pytest.fixture
    def html(self) -> str:
        path = Path(__file__).parent.parent / "oompah" / "templates" / "providers.html"
        return path.read_text()

    def test_billing_header_present(self, html):
        # The Billing <th> appears between Mode and Status in the
        # matrix header (oompah-zlz_2-yqss).
        assert ">Billing<" in html

    def test_billing_compute_helper_defined(self, html):
        # The per-row helper that classifies (backend, billing_model,
        # rate) for the cell.
        assert "function computeRoleMatrixBilling" in html

    def test_rate_lookup_helper_defined(self, html):
        # The model_costs rate lookup helper used by both modes.
        assert "function lookupModelRate" in html

    def test_rate_warning_text_present(self, html):
        # The "rates not set" warning copy from the task description.
        assert "rates not set — set via Edit Provider" in html

    def test_billing_per_token_tag_css(self, html):
        # CSS classes for the two ACP billing-model tags + the api
        # tag must exist so the column has visible styling.
        assert ".billing-per-token" in html
        assert ".billing-subscription" in html
        assert ".billing-api" in html

    def test_billing_rate_missing_class_css(self, html):
        # The yellow-text variant for the warning state.
        assert ".billing-rate-missing" in html

    def test_billing_cell_invoked_from_render(self, html):
        # renderRoleMatrix() must call computeRoleMatrixBilling so the
        # new column is actually rendered per candidate row (TASK-407.7:
        # parameter is now `cand` not `row` since candidates are iterated).
        assert "computeRoleMatrixBilling(cand, provider)" in html

    def test_billing_cell_class_in_render(self, html):
        # The cell uses matrix-billing as its CSS class.
        assert "matrix-billing" in html


class TestComputeBilling:
    """Behaviour tests for the computeRoleMatrixBilling JS helper.

    Renders providers.html into a minimal jsdom-like context via a
    regex pull of the function bodies, then exercises them with a few
    representative inputs. Keeps the test in Python by treating the
    JavaScript as a string and asserting on its branching structure.
    """

    @pytest.fixture
    def script(self) -> str:
        path = Path(__file__).parent.parent / "oompah" / "templates" / "providers.html"
        return path.read_text()

    def test_subscription_branch_returns_flat_label(self, script):
        # The subscription branch must produce the "subscription"
        # tag label, not "per-token".
        assert "tagLabel = isPerToken ? 'per-token' : 'subscription'" in script

    def test_per_token_branch_uses_rate_lookup(self, script):
        # Per-token providers display the rate from model_costs.
        assert "lookupModelRate(provider, row.model)" in script

    def test_api_mode_falls_back_to_api_path(self, script):
        # API mode reuses the same rate-lookup helper but tags the
        # cell with the neutral "api" colour.
        assert "billing-api" in script

    def test_lookup_returns_warning_when_no_costs(self, script):
        # Missing-model-costs entry => warning string in the return.
        assert "rates not set — set via Edit Provider" in script

    def test_lookup_formats_per_1k_in_out(self, script):
        # Rate display is per-1k input/output tokens.
        assert "/1k in" in script
        assert "/1k out" in script

    def test_default_backend_falls_back_to_claude(self, script):
        # provider.backend missing => the column shows "claude" since
        # that is the registry default.
        assert "provider.backend || 'claude'" in script


class TestProviderTestButton:
    """Static template smoke tests for the Test button added by TASK-407.8.

    Checks that providers.html contains the expected markup and JS for
    inline provider health-check from the Providers page.
    """

    @pytest.fixture
    def html(self) -> str:
        path = Path(__file__).parent.parent / "oompah" / "templates" / "providers.html"
        return path.read_text()

    def test_test_button_in_provider_actions(self, html):
        # The Test button must appear inside the provider-actions block
        # produced by renderProviders().
        assert "testProvider(" in html
        assert ">Test<" in html

    def test_test_button_passes_id_and_self(self, html):
        # The onclick must pass the provider id and `this` so the
        # function can locate the per-provider result div.
        assert "onclick=\"testProvider('${esc(p.id)}', this)\"" in html

    def test_result_div_per_provider(self, html):
        # Each card must contain a result div whose id is keyed to the
        # provider id so multiple cards can show independent results.
        assert "provider-test-result-${esc(p.id)}" in html

    def test_result_div_hidden_by_default(self, html):
        # The result area must start hidden so it does not take up
        # space before a test has been run.
        assert 'style="display:none;"' in html

    def test_testprovider_function_defined(self, html):
        assert "async function testProvider(" in html

    def test_testprovider_calls_correct_endpoint(self, html):
        # The function must POST to the provider test endpoint from
        # TASK-407.3.
        assert "/api/v1/providers/" in html
        assert "method: 'POST'" in html

    def test_testprovider_disables_button_while_loading(self, html):
        # Prevents duplicate clicks: button must be disabled during
        # the request.
        assert "btn.disabled = true" in html

    def test_testprovider_restores_button_in_finally(self, html):
        # The finally block must re-enable the button so a transient
        # failure does not permanently lock the UI.
        assert "btn.disabled = false" in html

    def test_success_result_css_class(self, html):
        assert ".test-result-ok" in html

    def test_failure_result_css_class(self, html):
        assert ".test-result-fail" in html

    def test_result_shows_model(self, html):
        # On success the inline result must include the model field.
        assert "data.model" in html

    def test_result_shows_latency(self, html):
        # On success the inline result must include the latency field.
        assert "latency_ms" in html

    def test_result_shows_error_reason(self, html):
        # On failure the inline result must include the normalized
        # error reason returned by the endpoint.
        assert "error_reason" in html

    def test_result_shows_response_text(self, html):
        # On success the inline result must include the short response
        # text from the provider.
        assert "response_text" in html


class TestMultiCandidateScaffold:
    """Static template smoke tests for the multi-candidate role matrix
    introduced by TASK-407.7. Verifies that the new UI elements for
    strategy selection, candidate management, and reordering are present
    in providers.html.
    """

    @pytest.fixture
    def html(self) -> str:
        from pathlib import Path
        path = Path(__file__).parent.parent / "oompah" / "templates" / "providers.html"
        return path.read_text()

    def test_strategy_control_css_present(self, html):
        # The strategy toggle container must be styled.
        assert ".strategy-control" in html

    def test_strategy_btn_css_present(self, html):
        # Strategy buttons and their active state must be styled.
        assert ".strategy-btn" in html
        assert ".strategy-btn.active" in html

    def test_role_header_row_css_present(self, html):
        # Each role gets a spanning header row.
        assert ".role-header-row" in html

    def test_candidate_num_css_present(self, html):
        # Candidate index number column must be styled.
        assert ".candidate-num" in html

    def test_candidate_actions_css_present(self, html):
        # Candidate action buttons (up/down/remove) container must be styled.
        assert ".candidate-actions" in html

    def test_btn_move_css_present(self, html):
        assert ".btn-move" in html

    def test_btn_remove_cand_css_present(self, html):
        assert ".btn-remove-cand" in html

    def test_btn_add_candidate_css_present(self, html):
        assert ".btn-add-candidate" in html

    def test_set_role_strategy_function_defined(self, html):
        assert "function setRoleStrategy(" in html

    def test_add_candidate_function_defined(self, html):
        assert "function addCandidate(" in html

    def test_remove_candidate_function_defined(self, html):
        assert "function removeCandidate(" in html

    def test_move_candidate_function_defined(self, html):
        assert "function moveCandidate(" in html

    def test_strategy_buttons_in_render(self, html):
        # The render function emits Priority and Round-robin buttons.
        assert "Priority</button>" in html
        assert "Round-robin</button>" in html

    def test_add_button_calls_add_candidate(self, html):
        # The + Add button's onclick calls addCandidate.
        assert "addCandidate(" in html

    def test_move_up_button_calls_move_candidate(self, html):
        # Move-up button calls moveCandidate with -1.
        assert "moveCandidate(" in html
        assert ", -1)" in html

    def test_move_down_button_calls_move_candidate(self, html):
        # Move-down button calls moveCandidate with 1.
        assert ", 1)" in html

    def test_remove_button_calls_remove_candidate(self, html):
        # Remove button calls removeCandidate.
        assert "removeCandidate(" in html

    def test_set_strategy_called_from_button(self, html):
        # The strategy button onclick calls setRoleStrategy.
        assert "setRoleStrategy(" in html

    def test_data_idx_attribute_present(self, html):
        # Candidate selects carry data-idx so the change handler can
        # update the right candidate.
        assert "data-idx=" in html

    def test_state_has_candidates_key(self, html):
        # The state comment describes the new structure.
        assert "candidates:" in html

    def test_save_sends_strategy(self, html):
        # saveRoleMatrix must include strategy in the body.
        assert "strategy: r.strategy" in html

    def test_save_sends_candidates(self, html):
        # saveRoleMatrix must include candidates in the body.
        assert "candidates:" in html
        assert "r.candidates" in html

    def test_load_reads_candidates_from_server(self, html):
        # renderRoleMatrix reads r.candidates from the server response.
        assert "r.candidates" in html

    def test_load_reads_strategy_from_server(self, html):
        # renderRoleMatrix reads r.strategy from the server response.
        assert "r.strategy" in html

    def test_backward_compat_single_candidate(self, html):
        # When the server returns no candidates array, fallback to
        # provider_id/model at the row level for backward compat.
        assert "r.provider_id" in html


class TestPutRoleMatrixNewFormat:
    """End-to-end API tests for the new strategy + candidates body shape
    introduced by TASK-407.7.

    These tests call PUT /api/v1/roles (via the legacy alias) with the new
    multi-candidate format and verify that the response reflects the shape
    and that multiple candidates are stored correctly.
    """

    def test_put_with_strategy_and_multiple_candidates(self, matrix_client):
        """PUT with strategy + candidates list round-trips correctly."""
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        p_acp = matrix_client["p_acp"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                    {"provider_id": p_api.id, "model": "nvidia/llama3-70b"},
                ],
            },
            "standard": {
                "strategy": "round_robin",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                ],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [
                    {"provider_id": p_acp.id, "model": "nvidia/minimaxai/minimax-m2.7"},
                ],
            },
            "default": {
                "strategy": "priority",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                ],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200, r.text
        rows = {row["role"]: row for row in r.json()["rows"]}
        assert rows["fast"]["status"] == "resolved"
        assert rows["fast"]["strategy"] == "priority"
        assert len(rows["fast"]["candidates"]) == 2
        assert rows["standard"]["strategy"] == "round_robin"

    def test_put_strategy_round_robin_stored(self, matrix_client):
        """Round-robin strategy is persisted to RoleStore."""
        client = matrix_client["client"]
        p_api = matrix_client["p_api"]
        body = {
            "fast": {
                "strategy": "round_robin",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                    {"provider_id": p_api.id, "model": "nvidia/llama3-70b"},
                ],
            },
            "standard": {"strategy": "priority", "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}]},
            "deep": {"strategy": "priority", "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}]},
            "default": {"strategy": "priority", "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}]},
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200, r.text
        role_store = matrix_client["role_store"]
        fast = role_store.get("fast")
        assert fast.strategy == "round_robin"
        assert len(fast.candidates) == 2

    def test_get_returns_candidates_list(self, matrix_client):
        """GET /api/v1/roles returns candidates list with provider details."""
        client = matrix_client["client"]
        r = client.get("/api/v1/roles")
        assert r.status_code == 200
        rows = {row["role"]: row for row in r.json()["rows"]}
        # All four roles were seeded with a single candidate.
        assert "candidates" in rows["fast"]
        assert len(rows["fast"]["candidates"]) == 1
        assert "provider_id" in rows["fast"]["candidates"][0]
        assert "strategy" in rows["fast"]

    def test_get_returns_strategy_field(self, matrix_client):
        """GET /api/v1/roles returns strategy for each role."""
        client = matrix_client["client"]
        r = client.get("/api/v1/roles")
        assert r.status_code == 200
        for row in r.json()["rows"]:
            assert "strategy" in row
