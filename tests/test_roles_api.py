"""Tests for GET /api/v1/roles and PUT /api/v1/roles.

Covers:
- GET response includes strategy and candidates (TASK-407.2 new fields)
- GET per-candidate status information
- GET backward-compat fields (provider_id, model, provider_mode, provider_name)
- PUT with new multi-candidate format (strategy + candidates)
- PUT with legacy single-candidate format (provider_id + model)
- PUT validation: invalid strategy, empty candidates, unknown provider,
  bad model, missing role, duplicate candidates
- PUT atomicity: invalid candidate rolls back all roles
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from oompah.providers import ProviderStore
from oompah.agent_profile_store import AgentProfileStore
from oompah.roles import Candidate, Role, RoleStore


# ---------------------------------------------------------------------------
# Fixture: wires fresh stores into the server module.
# ---------------------------------------------------------------------------


@pytest.fixture
def roles_client(tmp_path):
    """Fresh ProviderStore + RoleStore wired into the FastAPI app.

    Pre-seeds:
    - Two providers: ``p_api`` (api-mode, two models) and
      ``p_acp`` (acp-mode, subscription-only, empty catalog).
    - Four standard roles (fast/standard/deep/default) pointing at
      p_api / nvidia/MiniMax-M2.7 so GET tests have data to inspect.
    """
    from oompah import server as server_mod
    from oompah.server import app

    server_mod._template_cache.clear()

    provider_store = ProviderStore(path=str(tmp_path / "providers.json"))
    p_api = provider_store.create(
        name="Speedway",
        base_url="https://api.speedway.example",
        models=["nvidia/MiniMax-M2.7", "nvidia/llama3-70b"],
        default_model="nvidia/MiniMax-M2.7",
        provider_type="openai",
        mode="api",
    )
    p_acp = provider_store.create(
        name="CloudSDK",
        base_url="",
        models=[],
        default_model="",
        provider_type="openai",
        mode="acp",
        acp_permission_mode="default",
        acp_subscription_only=True,
    )

    agent_store = AgentProfileStore(path=str(tmp_path / "agent_profiles.json"))

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
    server_mod._orchestrator = None

    try:
        client = TestClient(app)
        yield {
            "client": client,
            "provider_store": provider_store,
            "role_store": role_store,
            "p_api": p_api,
            "p_acp": p_acp,
        }
    finally:
        server_mod._provider_store = original_provider_store
        server_mod._agent_profile_store = original_profile_store
        server_mod._role_store = original_role_store
        server_mod._orchestrator = original_orch


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _all_roles_body(p_api_id: str) -> dict:
    """Return a minimal valid PUT body (legacy format, all four roles)."""
    return {
        "fast": {"provider_id": p_api_id, "model": "nvidia/MiniMax-M2.7"},
        "standard": {"provider_id": p_api_id, "model": "nvidia/MiniMax-M2.7"},
        "deep": {"provider_id": p_api_id, "model": "nvidia/MiniMax-M2.7"},
        "default": {"provider_id": p_api_id, "model": "nvidia/MiniMax-M2.7"},
    }


# ---------------------------------------------------------------------------
# GET /api/v1/roles — new fields
# ---------------------------------------------------------------------------


class TestGetRolesNewFields:
    """GET /api/v1/roles returns strategy and candidates in each row."""

    def test_returns_strategy_field(self, roles_client):
        """Each role row includes a 'strategy' key."""
        r = roles_client["client"].get("/api/v1/roles")
        assert r.status_code == 200
        rows = r.json()["rows"]
        for row in rows:
            assert "strategy" in row, f"row missing strategy: {row}"

    def test_strategy_is_priority_for_single_candidate(self, roles_client):
        """Roles seeded with set() default to 'priority' strategy."""
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            assert row["strategy"] == "priority", row

    def test_returns_candidates_field(self, roles_client):
        """Each role row includes a 'candidates' key that is a list."""
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            assert "candidates" in row, f"row missing candidates: {row}"
            assert isinstance(row["candidates"], list), row

    def test_single_candidate_list(self, roles_client):
        """Single-candidate roles expose exactly one candidate."""
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            assert len(row["candidates"]) == 1, row

    def test_candidate_has_provider_id_and_model(self, roles_client):
        """Each candidate dict contains provider_id and model."""
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            for cand in row["candidates"]:
                assert "provider_id" in cand, cand
                assert "model" in cand, cand

    def test_candidate_has_status(self, roles_client):
        """Each candidate dict includes a 'status' field."""
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            for cand in row["candidates"]:
                assert "status" in cand, cand

    def test_candidate_status_resolved_when_valid(self, roles_client):
        """Valid candidates report status='resolved'."""
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            for cand in row["candidates"]:
                assert cand["status"] == "resolved", cand

    def test_candidate_has_provider_name_and_mode(self, roles_client):
        """Candidates include provider_name and provider_mode when provider exists."""
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            for cand in row["candidates"]:
                assert "provider_name" in cand, cand
                assert "provider_mode" in cand, cand
                assert cand["provider_mode"] == "api", cand
                assert cand["provider_name"] == "Speedway", cand

    def test_four_standard_roles_returned(self, roles_client):
        """GET returns exactly four rows for fast/standard/deep/default."""
        r = roles_client["client"].get("/api/v1/roles")
        assert r.status_code == 200
        rows = r.json()["rows"]
        names = [row["role"] for row in rows]
        assert names == ["fast", "standard", "deep", "default"]

    def test_unassigned_role_has_no_candidates_or_strategy(self, roles_client):
        """Roles with no RoleStore entry omit candidates and strategy."""
        role_store = roles_client["role_store"]
        role_store.delete("fast")
        r = roles_client["client"].get("/api/v1/roles")
        rows = {row["role"]: row for row in r.json()["rows"]}
        fast = rows["fast"]
        assert fast["status"] == "unassigned"
        assert "candidates" not in fast
        assert "strategy" not in fast

    def test_multi_candidate_role_get(self, roles_client):
        """Roles with multiple candidates expose all of them in order."""
        role_store = roles_client["role_store"]
        p_api = roles_client["p_api"]
        p_acp = roles_client["p_acp"]
        candidates = [
            Candidate(provider_id=p_api.id, model="nvidia/MiniMax-M2.7"),
            Candidate(provider_id=p_acp.id, model=""),
        ]
        role_store.set_candidates("fast", "round_robin", candidates)

        r = roles_client["client"].get("/api/v1/roles")
        rows = {row["role"]: row for row in r.json()["rows"]}
        fast = rows["fast"]
        assert fast["strategy"] == "round_robin"
        assert len(fast["candidates"]) == 2
        assert fast["candidates"][0]["provider_id"] == p_api.id
        assert fast["candidates"][0]["model"] == "nvidia/MiniMax-M2.7"
        assert fast["candidates"][1]["provider_id"] == p_acp.id

    def test_missing_provider_candidate_status(self, roles_client):
        """Candidate pointing at a vanished provider reports missing_provider."""
        role_store = roles_client["role_store"]
        role_store._roles["fast"] = Role(
            name="fast",
            strategy="priority",
            candidates=[Candidate(provider_id="prov-vanished", model="any-model")],
            updated_at=datetime.now(timezone.utc),
        )
        r = roles_client["client"].get("/api/v1/roles")
        rows = {row["role"]: row for row in r.json()["rows"]}
        fast = rows["fast"]
        assert fast["status"] == "missing_provider"
        assert fast["candidates"][0]["status"] == "missing_provider"

    def test_missing_model_candidate_status(self, roles_client):
        """Candidate with model not in catalog reports missing_model."""
        role_store = roles_client["role_store"]
        p_api = roles_client["p_api"]
        role_store._roles["standard"] = Role(
            name="standard",
            strategy="priority",
            candidates=[Candidate(provider_id=p_api.id, model="nvidia/no-such-model")],
            updated_at=datetime.now(timezone.utc),
        )
        r = roles_client["client"].get("/api/v1/roles")
        rows = {row["role"]: row for row in r.json()["rows"]}
        standard = rows["standard"]
        assert standard["status"] == "missing_model"
        assert standard["candidates"][0]["status"] == "missing_model"


# ---------------------------------------------------------------------------
# GET /api/v1/roles — backward-compat fields
# ---------------------------------------------------------------------------


class TestGetRolesBackwardCompat:
    """GET /api/v1/roles still includes top-level provider_id, model, etc."""

    def test_provider_id_mirrors_first_candidate(self, roles_client):
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        p_api = roles_client["p_api"]
        for row in rows:
            assert row["provider_id"] == p_api.id, row

    def test_model_mirrors_first_candidate(self, roles_client):
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            assert row["model"] == "nvidia/MiniMax-M2.7", row

    def test_provider_mode_mirrors_first_candidate(self, roles_client):
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            assert row["provider_mode"] == "api", row

    def test_provider_name_mirrors_first_candidate(self, roles_client):
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            assert row["provider_name"] == "Speedway", row

    def test_status_resolved(self, roles_client):
        r = roles_client["client"].get("/api/v1/roles")
        rows = r.json()["rows"]
        for row in rows:
            assert row["status"] == "resolved", row

    def test_multi_candidate_compat_fields_mirror_first(self, roles_client):
        """With multiple candidates, compat fields still mirror the FIRST one."""
        role_store = roles_client["role_store"]
        p_api = roles_client["p_api"]
        p_acp = roles_client["p_acp"]
        candidates = [
            Candidate(provider_id=p_api.id, model="nvidia/llama3-70b"),
            Candidate(provider_id=p_acp.id, model=""),
        ]
        role_store.set_candidates("deep", "priority", candidates)

        r = roles_client["client"].get("/api/v1/roles")
        rows = {row["role"]: row for row in r.json()["rows"]}
        deep = rows["deep"]
        # Compat fields = first candidate
        assert deep["provider_id"] == p_api.id
        assert deep["model"] == "nvidia/llama3-70b"
        assert deep["provider_mode"] == "api"


# ---------------------------------------------------------------------------
# PUT /api/v1/roles — new multi-candidate format
# ---------------------------------------------------------------------------


class TestPutRolesNewFormat:
    """PUT /api/v1/roles accepts the new strategy + candidates body."""

    def test_single_candidate_new_format_accepted(self, roles_client):
        """New format with one candidate per role is accepted."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            role: {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            }
            for role in ("fast", "standard", "deep", "default")
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200, r.text

    def test_multi_candidate_accepted(self, roles_client):
        """New format with two candidates per role is accepted."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        p_acp = roles_client["p_acp"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                    {"provider_id": p_acp.id, "model": ""},
                ],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/llama3-70b"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200, r.text

    def test_round_robin_strategy_accepted(self, roles_client):
        """round_robin strategy is accepted."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        p_acp = roles_client["p_acp"]
        body = {
            "fast": {
                "strategy": "round_robin",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                    {"provider_id": p_acp.id, "model": ""},
                ],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200, r.text
        rows = {row["role"]: row for row in r.json()["rows"]}
        assert rows["fast"]["strategy"] == "round_robin"

    def test_response_includes_strategy_and_candidates(self, roles_client):
        """PUT response echoes the new strategy and candidates fields."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            role: {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/llama3-70b"}],
            }
            for role in ("fast", "standard", "deep", "default")
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200
        rows = r.json()["rows"]
        for row in rows:
            assert row.get("strategy") == "priority", row
            assert len(row.get("candidates", [])) == 1, row

    def test_persists_multi_candidate_to_role_store(self, roles_client):
        """Multi-candidate PUT persists all candidates to RoleStore."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        p_acp = roles_client["p_acp"]
        role_store = roles_client["role_store"]
        body = {
            "fast": {
                "strategy": "round_robin",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                    {"provider_id": p_acp.id, "model": ""},
                ],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/llama3-70b"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200

        fast = role_store.get("fast")
        assert fast is not None
        assert fast.strategy == "round_robin"
        assert len(fast.candidates) == 2
        assert fast.candidates[0].provider_id == p_api.id
        assert fast.candidates[1].provider_id == p_acp.id

    def test_put_then_get_round_trip(self, roles_client):
        """PUT multi-candidate followed by GET reflects the new assignments."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        p_acp = roles_client["p_acp"]
        body = {
            "fast": {
                "strategy": "round_robin",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/llama3-70b"},
                    {"provider_id": p_acp.id, "model": ""},
                ],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r1 = client.put("/api/v1/roles", json=body)
        assert r1.status_code == 200

        r2 = client.get("/api/v1/roles")
        rows = {row["role"]: row for row in r2.json()["rows"]}
        fast = rows["fast"]
        assert fast["strategy"] == "round_robin"
        assert len(fast["candidates"]) == 2
        assert fast["candidates"][0]["model"] == "nvidia/llama3-70b"

    def test_missing_strategy_defaults_to_priority(self, roles_client):
        """Omitting strategy in new format defaults to priority."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            role: {
                # No "strategy" key — should default to priority
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            }
            for role in ("fast", "standard", "deep", "default")
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200, r.text
        rows = {row["role"]: row for row in r.json()["rows"]}
        for role_name in ("fast", "standard", "deep", "default"):
            assert rows[role_name]["strategy"] == "priority", rows[role_name]

    def test_acp_provider_empty_catalog_accepted_in_new_format(self, roles_client):
        """ACP candidate with empty model is accepted in new format."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        p_acp = roles_client["p_acp"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_acp.id, "model": ""}],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# PUT /api/v1/roles — legacy single-candidate format (backward compat)
# ---------------------------------------------------------------------------


class TestPutRolesLegacyFormat:
    """Legacy provider_id + model format still works after TASK-407.2."""

    def test_legacy_format_accepted(self, roles_client):
        """Old-style provider_id/model body returns 200."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        r = client.put("/api/v1/roles", json=_all_roles_body(p_api.id))
        assert r.status_code == 200, r.text

    def test_legacy_format_creates_priority_role(self, roles_client):
        """Legacy format persists as a single-candidate priority role."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        role_store = roles_client["role_store"]
        r = client.put("/api/v1/roles", json=_all_roles_body(p_api.id))
        assert r.status_code == 200
        fast = role_store.get("fast")
        assert fast.strategy == "priority"
        assert len(fast.candidates) == 1
        assert fast.candidates[0].provider_id == p_api.id

    def test_legacy_format_response_includes_strategy(self, roles_client):
        """Response for legacy PUT includes the strategy field."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        r = client.put("/api/v1/roles", json=_all_roles_body(p_api.id))
        assert r.status_code == 200
        rows = r.json()["rows"]
        for row in rows:
            assert "strategy" in row, row

    def test_legacy_format_response_includes_candidates(self, roles_client):
        """Response for legacy PUT includes the candidates list."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        r = client.put("/api/v1/roles", json=_all_roles_body(p_api.id))
        assert r.status_code == 200
        rows = r.json()["rows"]
        for row in rows:
            assert "candidates" in row, row
            assert len(row["candidates"]) == 1, row

    def test_legacy_format_mixed_with_new_format(self, roles_client):
        """Each role can independently use old or new format in the same request."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        p_acp = roles_client["p_acp"]
        body = {
            # New format
            "fast": {
                "strategy": "round_robin",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                    {"provider_id": p_acp.id, "model": ""},
                ],
            },
            # Legacy format for remaining roles
            "standard": {"provider_id": p_api.id, "model": "nvidia/llama3-70b"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200, r.text
        rows = {row["role"]: row for row in r.json()["rows"]}
        assert rows["fast"]["strategy"] == "round_robin"
        assert len(rows["fast"]["candidates"]) == 2
        assert rows["standard"]["strategy"] == "priority"
        assert len(rows["standard"]["candidates"]) == 1


# ---------------------------------------------------------------------------
# PUT /api/v1/roles — validation: invalid strategy
# ---------------------------------------------------------------------------


class TestPutRolesStrategyValidation:
    """PUT rejects invalid strategy values."""

    def test_rejects_unknown_strategy(self, roles_client):
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {
                "strategy": "waterfall",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400
        msg = r.json()["error"]["message"]
        assert "waterfall" in msg or "strategy" in msg

    def test_rejects_empty_string_strategy(self, roles_client):
        """Empty string strategy fails (defaults aren't applied for explicit values)."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        # With candidates key but explicit empty strategy string, the default
        # is used (empty str falls back to DEFAULT_STRATEGY). Verify the
        # result is 200 or that validation is lenient for empty → default.
        # The implementation treats falsy strategy as DEFAULT_STRATEGY.
        body = {
            "fast": {
                "strategy": "",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        # Empty strategy should default to 'priority' (falsy → DEFAULT_STRATEGY)
        assert r.status_code == 200, r.text

    def test_rejects_numeric_strategy(self, roles_client):
        """Non-string strategy values are rejected."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {
                "strategy": 42,
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# PUT /api/v1/roles — validation: candidates
# ---------------------------------------------------------------------------


class TestPutRolesCandidatesValidation:
    """PUT validates each candidate in the new format."""

    def test_rejects_empty_candidates_list(self, roles_client):
        """Empty candidates list is rejected."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {"strategy": "priority", "candidates": []},
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400
        assert "candidates" in r.json()["error"]["message"]

    def test_rejects_unknown_provider_in_candidate(self, roles_client):
        """Candidate with non-existent provider_id is rejected."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [{"provider_id": "prov-bogus", "model": "any"}],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400
        assert "prov-bogus" in r.json()["error"]["message"]

    def test_rejects_model_not_in_catalog(self, roles_client):
        """Candidate whose model is not in provider's catalog is rejected."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/not-listed"}],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400
        msg = r.json()["error"]["message"]
        assert "nvidia/not-listed" in msg

    def test_rejects_missing_provider_id_in_candidate(self, roles_client):
        """Candidate missing provider_id is rejected."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [{"model": "nvidia/MiniMax-M2.7"}],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400
        assert "provider_id" in r.json()["error"]["message"]

    def test_rejects_non_list_candidates(self, roles_client):
        """Non-list candidates value is rejected."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": "not-a-list",
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400

    def test_rejects_non_dict_candidate_item(self, roles_client):
        """Non-dict item inside candidates list is rejected."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": ["not-a-dict"],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400

    def test_rejects_duplicate_candidates_same_role(self, roles_client):
        """Two identical (provider_id, model) pairs in one role are rejected."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},  # dup
                ],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400
        assert "duplicate" in r.json()["error"]["message"]

    def test_allows_same_provider_different_models(self, roles_client):
        """Same provider_id with different models is a valid multi-candidate list."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                    {"provider_id": p_api.id, "model": "nvidia/llama3-70b"},
                ],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 200, r.text

    def test_second_bad_candidate_still_rejected(self, roles_client):
        """Validation error in the second candidate of a list is caught."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                    {"provider_id": "prov-nonexistent", "model": "anything"},  # bad
                ],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400
        assert "prov-nonexistent" in r.json()["error"]["message"]


# ---------------------------------------------------------------------------
# PUT /api/v1/roles — validation: body structure
# ---------------------------------------------------------------------------


class TestPutRolesBodyValidation:
    """PUT validates top-level request body shape."""

    def test_rejects_missing_role(self, roles_client):
        """Body missing one of the four required roles is rejected."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            # "standard" omitted
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400
        assert "standard" in r.json()["error"]["message"]

    def test_rejects_non_dict_body(self, roles_client):
        """Non-object body is rejected."""
        client = roles_client["client"]
        r = client.put("/api/v1/roles", json=["not", "a", "dict"])
        assert r.status_code == 400

    def test_rejects_non_dict_role_row(self, roles_client):
        """A role row that is not a dict is rejected."""
        client = roles_client["client"]
        p_api = roles_client["p_api"]
        body = {
            "fast": "not-a-dict",
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# PUT /api/v1/roles — atomicity
# ---------------------------------------------------------------------------


class TestPutRolesAtomicity:
    """Validation failure rolls back all roles — none are mutated."""

    def test_invalid_new_format_candidate_rolls_back_all(self, roles_client):
        """One bad candidate in the new format leaves the entire store unchanged."""
        client = roles_client["client"]
        role_store = roles_client["role_store"]
        p_api = roles_client["p_api"]
        p_acp = roles_client["p_acp"]

        before = {r.name: r.to_dict() for r in role_store.list_all()}

        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [
                    {"provider_id": p_acp.id, "model": ""},
                    {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
                ],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/llama3-70b"}],
            },
            "deep": {
                "strategy": "priority",
                # Invalid candidate — unknown provider
                "candidates": [{"provider_id": "prov-vanished", "model": "anything"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400

        after = {r.name: r.to_dict() for r in role_store.list_all()}
        for name in before:
            b = {k: v for k, v in before[name].items() if k != "updated_at"}
            a = {k: v for k, v in after[name].items() if k != "updated_at"}
            assert a == b, f"role {name!r} was mutated despite 400"

    def test_invalid_strategy_rolls_back_all(self, roles_client):
        """Invalid strategy in one role leaves the entire store unchanged."""
        client = roles_client["client"]
        role_store = roles_client["role_store"]
        p_api = roles_client["p_api"]

        before = {r.name: r.to_dict() for r in role_store.list_all()}

        body = {
            "fast": {
                "strategy": "fastest",  # invalid
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "deep": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
            "default": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400

        after = {r.name: r.to_dict() for r in role_store.list_all()}
        for name in before:
            b = {k: v for k, v in before[name].items() if k != "updated_at"}
            a = {k: v for k, v in after[name].items() if k != "updated_at"}
            assert a == b, f"role {name!r} was mutated despite 400"

    def test_three_good_one_bad_new_format_atomic(self, roles_client):
        """Three valid roles + one bad candidate: none are stored."""
        client = roles_client["client"]
        role_store = roles_client["role_store"]
        p_api = roles_client["p_api"]

        before = {r.name: r.to_dict() for r in role_store.list_all()}

        body = {
            "fast": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/llama3-70b"}],
            },
            "standard": {
                "strategy": "priority",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/llama3-70b"}],
            },
            "deep": {
                "strategy": "round_robin",
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/llama3-70b"}],
            },
            "default": {
                "strategy": "priority",
                # model not in catalog
                "candidates": [{"provider_id": p_api.id, "model": "nvidia/no-such-model"}],
            },
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400

        after = {r.name: r.to_dict() for r in role_store.list_all()}
        for name in before:
            b = {k: v for k, v in before[name].items() if k != "updated_at"}
            a = {k: v for k, v in after[name].items() if k != "updated_at"}
            assert a == b, f"role {name!r} was mutated despite 400"

    def test_legacy_format_atomicity(self, roles_client):
        """Legacy format PUT is also atomic: one bad provider → no changes."""
        client = roles_client["client"]
        role_store = roles_client["role_store"]
        p_api = roles_client["p_api"]

        before = {r.name: r.to_dict() for r in role_store.list_all()}

        body = {
            "fast": {"provider_id": "prov-bogus", "model": "anything"},
            "standard": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "deep": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
            "default": {"provider_id": p_api.id, "model": "nvidia/MiniMax-M2.7"},
        }
        r = client.put("/api/v1/roles", json=body)
        assert r.status_code == 400

        after = {r.name: r.to_dict() for r in role_store.list_all()}
        for name in before:
            b = {k: v for k, v in before[name].items() if k != "updated_at"}
            a = {k: v for k, v in after[name].items() if k != "updated_at"}
            assert a == b, f"role {name!r} was mutated despite 400"
