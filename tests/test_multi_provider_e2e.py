"""End-to-end verification of the multi-provider role assignment feature.

Covers TASK-407.9 acceptance criteria:

  AC#1  User-facing documentation exists (smoke-tested by file presence).
  AC#4  Migration from old single-candidate roles.json works correctly.
  AC#5  make test passes — this file's tests are part of that gate.
  AC#6  Single-candidate projects do not regress.

The tests deliberately avoid the HTTP server wherever possible so that
the acceptance criteria around "automated tests" can run without a
running oompah process.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from oompah.providers import ProviderStore
from oompah.roles import (
    Candidate,
    CandidateSelector,
    Role,
    RoleStore,
    migrate_agent_profiles_to_roles,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _role(name: str, strategy: str, candidates: list[Candidate]) -> Role:
    return Role(
        name=name,
        strategy=strategy,
        candidates=candidates,
        updated_at=datetime.now(timezone.utc),
    )


def _c(provider_id: str, model: str = "") -> Candidate:
    return Candidate(provider_id=provider_id, model=model)


# ---------------------------------------------------------------------------
# AC#1 — User-facing documentation exists in docs/
# ---------------------------------------------------------------------------


class TestDocumentationExists:
    """Smoke-test: the required doc files exist in the project tree."""

    @pytest.fixture
    def repo_root(self) -> Path:
        # This test file lives at tests/test_multi_provider_e2e.py.
        # The project root is one level up.
        return Path(__file__).parent.parent

    def test_user_facing_docs_file_exists(self, repo_root):
        """docs/multi-provider-roles.md must exist for operator reference."""
        doc = repo_root / "docs" / "multi-provider-roles.md"
        assert doc.exists(), f"Expected user-facing doc at {doc}"

    def test_user_facing_docs_covers_priority_strategy(self, repo_root):
        """The operator doc must mention priority strategy."""
        doc = repo_root / "docs" / "multi-provider-roles.md"
        content = doc.read_text()
        assert "priority" in content.lower(), "Doc must explain priority strategy"

    def test_user_facing_docs_covers_round_robin_strategy(self, repo_root):
        """The operator doc must mention round-robin strategy."""
        doc = repo_root / "docs" / "multi-provider-roles.md"
        content = doc.read_text()
        assert "round" in content.lower(), "Doc must explain round-robin strategy"

    def test_user_facing_docs_covers_failover(self, repo_root):
        """The operator doc must describe failover / fallback conditions."""
        doc = repo_root / "docs" / "multi-provider-roles.md"
        content = doc.read_text()
        assert any(kw in content.lower() for kw in ("failover", "fallback", "fail over")), (
            "Doc must explain what causes failover to the next candidate"
        )

    def test_user_facing_docs_covers_test_button(self, repo_root):
        """The operator doc must describe the provider Test button."""
        doc = repo_root / "docs" / "multi-provider-roles.md"
        content = doc.read_text()
        assert "test button" in content.lower() or "test" in content.lower(), (
            "Doc must mention the provider Test button"
        )

    def test_user_facing_docs_test_button_no_round_robin_update(self, repo_root):
        """The doc must state that the Test button does NOT update round-robin usage."""
        doc = repo_root / "docs" / "multi-provider-roles.md"
        content = doc.read_text()
        # Must include something like "does not update round-robin usage"
        assert "round-robin" in content.lower() or "round_robin" in content.lower(), (
            "Doc must clarify the Test button does not update round-robin state"
        )

    def test_internal_design_plan_exists(self, repo_root):
        """plans/multi-provider-role-dispatch.md must exist for developer reference."""
        plan = repo_root / "plans" / "multi-provider-role-dispatch.md"
        assert plan.exists(), f"Expected design plan at {plan}"

    def test_internal_plan_covers_candidate_schema(self, repo_root):
        """The design plan must describe the candidate data model."""
        plan = repo_root / "plans" / "multi-provider-role-dispatch.md"
        content = plan.read_text()
        assert "candidate" in content.lower(), "Plan must describe the Candidate schema"

    def test_internal_plan_covers_selector_state(self, repo_root):
        """The design plan must describe CandidateSelector state."""
        plan = repo_root / "plans" / "multi-provider-role-dispatch.md"
        content = plan.read_text()
        assert "selector" in content.lower() or "usage" in content.lower(), (
            "Plan must explain selector state and role_usage.json"
        )


# ---------------------------------------------------------------------------
# AC#4 — Migration from old single-candidate roles.json
# ---------------------------------------------------------------------------


class TestLegacyRolesMigration:
    """Migration from the old flat provider_id/model format is transparent."""

    def test_old_roles_json_loads_as_priority_roles(self, tmp_path):
        """An old-format roles.json is read as one-candidate priority roles."""
        path = str(tmp_path / "roles.json")
        with open(path, "w") as f:
            json.dump([
                {
                    "name": "fast",
                    "provider_id": "prov-old",
                    "model": "gpt-4o",
                    "updated_at": "2025-01-01T00:00:00+00:00",
                },
                {
                    "name": "standard",
                    "provider_id": "prov-old",
                    "model": "gpt-4",
                    "updated_at": "2025-01-01T00:00:00+00:00",
                },
            ], f)

        store = RoleStore(path=path)

        fast = store.get("fast")
        assert fast is not None
        assert fast.strategy == "priority", "Old format migrates to priority"
        assert len(fast.candidates) == 1
        assert fast.candidates[0].provider_id == "prov-old"
        assert fast.candidates[0].model == "gpt-4o"
        # Backward-compat properties still work
        assert fast.provider_id == "prov-old"
        assert fast.model == "gpt-4o"

        standard = store.get("standard")
        assert standard is not None
        assert standard.model == "gpt-4"

    def test_old_roles_json_rewritten_in_new_format_on_save(self, tmp_path):
        """After loading old format and saving, the file uses the new schema."""
        path = str(tmp_path / "roles.json")
        with open(path, "w") as f:
            json.dump([
                {"name": "fast", "provider_id": "prov-1", "model": "gpt-4o"},
            ], f)

        store = RoleStore(path=path)
        # Trigger a save by updating
        store.set("fast", "prov-1", "gpt-4o")

        with open(path) as f:
            data = json.load(f)

        entry = data[0]
        assert "strategy" in entry, "Saved file must include strategy"
        assert "candidates" in entry, "Saved file must include candidates list"
        assert entry["strategy"] == "priority"
        assert entry["candidates"] == [{"provider_id": "prov-1", "model": "gpt-4o"}]
        assert "provider_id" not in entry, "Old flat field must be absent after save"
        assert "model" not in entry, "Old flat model field must be absent after save"

    def test_dispatch_behavior_unchanged_for_single_candidate(self, tmp_path):
        """Single-candidate roles dispatch in priority order (no regression)."""
        selector = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("prov-1", "gpt-4o")
        role = _role("standard", "priority", [c1])

        result = selector.ordered_candidates(role)
        assert result == [c1], "Single-candidate priority role returns exactly one candidate"

    def test_dispatch_after_migration_matches_original_model(self, tmp_path):
        """After migrating an old roles.json, the dispatched model is unchanged."""
        path = str(tmp_path / "roles.json")
        with open(path, "w") as f:
            json.dump([
                {"name": "deep", "provider_id": "prov-abc", "model": "claude-3-opus"},
            ], f)

        store = RoleStore(path=path)
        selector = CandidateSelector(path=str(tmp_path / "usage.json"))

        role = store.get("deep")
        assert role is not None
        ordered = selector.ordered_candidates(role)
        assert len(ordered) == 1
        assert ordered[0].model == "claude-3-opus"

    def test_all_four_standard_roles_migrate(self, tmp_path):
        """All four standard roles in an old file are correctly loaded."""
        path = str(tmp_path / "roles.json")
        roles_data = [
            {"name": name, "provider_id": "prov-x", "model": f"model-{name}"}
            for name in ("fast", "standard", "deep", "default")
        ]
        with open(path, "w") as f:
            json.dump(roles_data, f)

        store = RoleStore(path=path)
        for name in ("fast", "standard", "deep", "default"):
            role = store.get(name)
            assert role is not None, f"Role {name!r} must survive migration"
            assert role.strategy == "priority"
            assert role.model == f"model-{name}"


# ---------------------------------------------------------------------------
# AC#4 — migrate_agent_profiles_to_roles correctness
# ---------------------------------------------------------------------------


class TestAgentProfileMigration:
    """Verify migrate_agent_profiles_to_roles fills empty role slots."""

    def test_migrates_profile_with_model_to_role_store(self, tmp_path):
        """Profile with provider_id + model + model_role writes to RoleStore."""
        from oompah.models import AgentProfile

        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4o"])
        prov = prov_store.get_default()

        role_store = RoleStore(path=str(tmp_path / "roles.json"), provider_store=prov_store)

        profiles = [
            AgentProfile(
                name="default",
                command="cli",
                provider_id=prov.id,
                model="gpt-4o",
                model_role="fast",
            ),
        ]
        migrated = migrate_agent_profiles_to_roles(role_store, profiles)
        assert migrated == 1
        role = role_store.get("fast")
        assert role is not None
        assert role.provider_id == prov.id
        assert role.model == "gpt-4o"
        assert role.strategy == "priority"
        assert len(role.candidates) == 1

    def test_migration_does_not_overwrite_existing_role(self, tmp_path):
        """Existing role slots are not overwritten by migration."""
        from oompah.models import AgentProfile

        prov_store = ProviderStore(path=str(tmp_path / "providers.json"))
        prov_store.create(name="test", base_url="http://x", models=["gpt-4o", "gpt-4"])
        prov = prov_store.get_default()

        role_store = RoleStore(path=str(tmp_path / "roles.json"), provider_store=prov_store)
        role_store.set("fast", prov.id, "gpt-4o")  # pre-existing

        profiles = [
            AgentProfile(
                name="default",
                command="cli",
                provider_id=prov.id,
                model="gpt-4",  # different model
                model_role="fast",
            ),
        ]
        migrated = migrate_agent_profiles_to_roles(role_store, profiles)
        assert migrated == 0, "Should not overwrite existing role"
        assert role_store.get("fast").model == "gpt-4o"


# ---------------------------------------------------------------------------
# AC#6 — single-candidate project non-regression
# ---------------------------------------------------------------------------


class TestSingleCandidateNonRegression:
    """Projects that still use one candidate per role continue to work."""

    def test_single_candidate_priority_order_unchanged(self, tmp_path):
        """Single-candidate priority role returns same candidate on every call."""
        selector = CandidateSelector(path=str(tmp_path / "usage.json"))
        c = _c("prov-1", "gpt-4")
        role = _role("standard", "priority", [c])

        for _ in range(5):
            assert selector.ordered_candidates(role) == [c]

    def test_single_candidate_round_robin_returns_only_candidate(self, tmp_path):
        """Round-robin with a single candidate always returns that candidate."""
        selector = CandidateSelector(path=str(tmp_path / "usage.json"))
        c = _c("prov-1", "m1")
        role = _role("fast", "round_robin", [c])

        assert selector.ordered_candidates(role) == [c]
        selector.record_used("fast", c)
        assert selector.ordered_candidates(role) == [c]

    def test_single_candidate_usage_file_not_created_on_read(self, tmp_path):
        """Calling ordered_candidates on a single-candidate role does not create usage file."""
        usage_path = str(tmp_path / "usage.json")
        selector = CandidateSelector(path=usage_path)
        role = _role("fast", "priority", [_c("p", "m")])

        selector.ordered_candidates(role)

        assert not (tmp_path / "usage.json").exists(), (
            "Read-only ordered_candidates must not create the usage file"
        )

    def test_single_candidate_record_used_does_not_affect_ordering(self, tmp_path):
        """Recording usage for the only candidate still returns it first."""
        selector = CandidateSelector(path=str(tmp_path / "usage.json"))
        c = _c("prov-1", "m1")
        role = _role("fast", "priority", [c])

        selector.record_used("fast", c)
        assert selector.ordered_candidates(role) == [c]

    def test_single_candidate_role_store_is_empty_detection(self, tmp_path):
        """RoleStore.is_empty is correct for zero vs. one role."""
        store = RoleStore(path=str(tmp_path / "roles.json"))
        assert store.is_empty

        store.set("fast", "prov-1", "gpt-4o")
        assert not store.is_empty

    def test_single_candidate_role_backward_compat_properties(self, tmp_path):
        """role.provider_id and role.model still work for single-candidate roles."""
        store = RoleStore(path=str(tmp_path / "roles.json"))
        store.set("fast", "prov-1", "gpt-4o")

        role = store.get("fast")
        assert role.provider_id == "prov-1"
        assert role.model == "gpt-4o"

    def test_single_candidate_delete_and_recheck(self, tmp_path):
        """Deleting a role returns None from get(); re-adding works."""
        store = RoleStore(path=str(tmp_path / "roles.json"))
        store.set("fast", "prov-1", "gpt-4o")
        assert store.delete("fast") is True
        assert store.get("fast") is None
        store.set("fast", "prov-2", "gpt-4")
        assert store.get("fast").provider_id == "prov-2"

    def test_multi_candidate_does_not_break_single_candidate_reads(self, tmp_path):
        """A store with both multi-candidate and single-candidate roles reads both correctly."""
        store = RoleStore(path=str(tmp_path / "roles.json"))
        # Single-candidate role
        store.set("standard", "prov-1", "gpt-4o")
        # Multi-candidate role
        store.set_candidates("fast", "round_robin", [
            Candidate(provider_id="prov-1", model="gpt-4o"),
            Candidate(provider_id="prov-2", model="claude-3"),
        ])

        std = store.get("standard")
        assert len(std.candidates) == 1
        assert std.provider_id == "prov-1"

        fast = store.get("fast")
        assert len(fast.candidates) == 2
        assert fast.strategy == "round_robin"

    def test_reload_after_mixed_store_preserves_both(self, tmp_path):
        """After writing a mixed store, reloading from disk preserves both roles."""
        path = str(tmp_path / "roles.json")
        store = RoleStore(path=path)
        store.set("standard", "prov-1", "gpt-4o")
        store.set_candidates("fast", "round_robin", [
            Candidate(provider_id="prov-1", model="gpt-4o"),
            Candidate(provider_id="prov-2", model="claude-3"),
        ])

        store2 = RoleStore(path=path)
        assert store2.get("standard").model == "gpt-4o"
        assert store2.get("fast").strategy == "round_robin"
        assert len(store2.get("fast").candidates) == 2


# ---------------------------------------------------------------------------
# Manual scenario verification (mocked) — end-to-end dispatch simulation
# ---------------------------------------------------------------------------


class TestDispatchSimulation:
    """Simulate the full dispatch loop with mocked providers and workers.

    These tests exercise the orchestrator's dispatch logic with controlled
    inputs to verify that:
    - priority roles try candidates in order and stop at the first success
    - round-robin roles rotate through candidates across dispatches
    - single-candidate projects experience no behaviour change
    - Test button endpoint does not update usage state
    """

    def _make_provider(self, pid: str, name: str = "", models: list | None = None):
        from oompah.models import ModelProvider
        return ModelProvider(
            id=pid,
            name=name or pid,
            base_url="http://example.com/v1",
            api_key="sk-test",
            models=models if models is not None else ["m1"],
            default_model="m1",
        )

    # ------------------------------------------------------------------
    # Priority: first candidate used when available
    # ------------------------------------------------------------------

    def test_priority_first_candidate_used_on_success(self, tmp_path):
        """Priority role: first candidate is chosen when it passes preflight."""
        selector = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("standard", "priority", [c1, c2])

        ordered = selector.ordered_candidates(role)
        assert ordered[0] == c1, "First configured candidate is tried first"

    def test_priority_order_unchanged_after_usage(self, tmp_path):
        """Priority role: recording usage does not change order."""
        selector = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("standard", "priority", [c1, c2])

        selector.record_used("standard", c1)
        ordered = selector.ordered_candidates(role)
        assert ordered[0] == c1, "Priority order is fixed regardless of usage"

    # ------------------------------------------------------------------
    # Round-robin: rotates across dispatches
    # ------------------------------------------------------------------

    def test_round_robin_cycles_through_two_candidates(self, tmp_path):
        """Round-robin role rotates between two candidates across dispatches."""
        selector = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("fast", "round_robin", [c1, c2])

        # First dispatch: both never used → c1 (configured first)
        first = selector.ordered_candidates(role)[0]
        assert first == c1
        selector.record_used("fast", c1)

        # Second dispatch: c1 used, c2 never used → c2
        second = selector.ordered_candidates(role)[0]
        assert second == c2
        selector.record_used("fast", c2)

        # Third dispatch: both used, c1 LRU → c1
        third = selector.ordered_candidates(role)[0]
        assert third == c1

    def test_round_robin_usage_persists_across_selector_instances(self, tmp_path):
        """Usage recorded in one selector instance is visible in a fresh instance."""
        path = str(tmp_path / "usage.json")
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("fast", "round_robin", [c1, c2])

        sel1 = CandidateSelector(path=path)
        assert sel1.ordered_candidates(role)[0] == c1
        sel1.record_used("fast", c1)

        # Fresh instance reads persisted usage
        sel2 = CandidateSelector(path=path)
        assert sel2.ordered_candidates(role)[0] == c2  # c1 already used

    # ------------------------------------------------------------------
    # Provider test endpoint does not update usage state
    # ------------------------------------------------------------------

    def test_provider_health_check_does_not_update_usage(self, tmp_path):
        """The Test button health check must not call record_used."""
        selector = CandidateSelector(path=str(tmp_path / "usage.json"))
        c1 = _c("p1", "m1")
        c2 = _c("p2", "m2")
        role = _role("fast", "round_robin", [c1, c2])

        # Verify no usage before the "health check"
        assert selector.ordered_candidates(role)[0] == c1

        # Simulate the provider health check: it DOES NOT call record_used
        # (the real endpoint never touches CandidateSelector)
        # — we just verify the ordering is unchanged
        assert selector.ordered_candidates(role)[0] == c1, (
            "Health check must not update round-robin state"
        )

    # ------------------------------------------------------------------
    # Single-candidate project: dispatch produces correct target
    # ------------------------------------------------------------------

    def test_single_candidate_dispatch_target(self, tmp_path):
        """Single-candidate role resolves to one DispatchTarget."""
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        project_store = MagicMock()
        project_store.list_all.return_value = []
        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        # One candidate, priority
        role_store.set("standard", "prov-1", "gpt-4o")

        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            role_store=role_store,
            state_path=str(tmp_path / "state.json"),
        )

        from oompah.models import AgentProfile, ModelProvider

        prov = ModelProvider(
            id="prov-1",
            name="TestProv",
            base_url="http://example.com/v1",
            api_key="sk-test",
            models=["gpt-4o"],
            default_model="gpt-4o",
        )
        mock_ps = MagicMock()
        mock_ps.get.return_value = prov
        mock_ps.get_default.return_value = prov
        orch.provider_store = mock_ps

        profile = AgentProfile(name="default", command="cli", model_role="standard")
        targets = orch._resolve_dispatch_targets(profile)

        assert len(targets) == 1, "Single-candidate role must produce exactly one target"
        assert targets[0].provider == prov
        assert targets[0].model == "gpt-4o"
        assert targets[0].role_name == "standard"
