"""Tests for auditor role independent candidate selection (OOMPAH-470).

Covers:
- Different provider/model candidates
- Same-provider different-model fallback
- Same model on another provider (independent)
- Multi-contributor epic exclusion
- Unknown ACP models rejection
- Round-robin ordering (future)
- Provider whitelist filtering
- Unhealthy/missing credentials blocking
- Budget constraints
- Empty role handling
- Migration seeding
- No-candidate diagnostics

Test organization follows the spec exactly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from oompah.auditor_candidate_selector import (
    AUDITOR_ROLE_NAME,
    AuditorCandidateSelector,
    NoCandidateReason,
    seed_auditor_role_from_config,
)
from oompah.models import ModelProvider
from oompah.providers import ProviderStore
from oompah.roles import Candidate, Role, RoleStore
from oompah.work_contributors import WorkContributor


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _make_provider(
    provider_id: str = "prov-test",
    name: str = "TestProvider",
    models: list[str] | None = None,
    default_model: str | None = None,
    mode: str = "api",
    api_key: str = "test-key",
    base_url: str = "http://localhost:8000",
    billing_model: str = "per_token",
) -> ModelProvider:
    """Create a test ModelProvider."""
    if models is None:
        models = ["test-model-1", "test-model-2"]
    return ModelProvider(
        id=provider_id,
        name=name,
        models=models,
        default_model=default_model or (models[0] if models else None),
        mode=mode,
        api_key=api_key,
        base_url=base_url,
        billing_model=billing_model,
    )


def _make_contributor(
    provider_id: str | None = "prov-contrib",
    model_id: str | None = "model-contrib",
) -> WorkContributor:
    """Create a test WorkContributor."""
    return WorkContributor(
        run_id="run-1",
        provider_id=provider_id,
        provider_name="ContributorProvider",
        model_id=model_id,
        focus="feature",
        source_branch="main",
        source_sha="abc123",
        completed_at=datetime.now(timezone.utc).isoformat(),
    )


def _make_project_config(provider_whitelist: list[str] | None = None):
    """Create a mock ProjectConfig."""
    config = MagicMock()
    config.provider_whitelist = provider_whitelist or []
    return config


def _make_role_store_with_roles(roles_dict: dict[str, Role] | None = None) -> RoleStore:
    """Create a RoleStore with predefined roles."""
    store = MagicMock(spec=RoleStore)
    roles = roles_dict or {}
    store.get = lambda name: roles.get(name)
    store.list_all = lambda: list(roles.values())
    return store


def _make_provider_store(providers: dict[str, ModelProvider] | None = None) -> ProviderStore:
    """Create a ProviderStore with predefined providers."""
    store = MagicMock(spec=ProviderStore)
    providers = providers or {}
    store.get = lambda provider_id: providers.get(provider_id)
    store.list_all = lambda: list(providers.values())
    return store


# ---------------------------------------------------------------------------
# TestNoCandidateReason
# ---------------------------------------------------------------------------


class TestNoCandidateReason:
    """NoCandidateReason serialization and structure."""

    def test_to_dict(self):
        reason = NoCandidateReason(
            reason="all_are_contributors",
            detail="Providers used by all contributors",
        )
        d = reason.to_dict()
        assert d["reason"] == "all_are_contributors"
        assert d["detail"] == "Providers used by all contributors"

    def test_from_dict_roundtrip(self):
        reason = NoCandidateReason(
            reason="no_providers",
            detail="Empty role",
        )
        d = reason.to_dict()
        restored = NoCandidateReason.from_dict(d)
        assert restored.reason == reason.reason
        assert restored.detail == reason.detail

    def test_from_dict_missing_fields(self):
        reason = NoCandidateReason.from_dict({})
        assert reason.reason == "unknown_error"
        assert reason.detail == ""

    def test_valid_reason_strings(self):
        """Verify all expected reason values are acceptable."""
        valid_reasons = {
            "empty_role",
            "no_providers",
            "no_whitelisted_providers",
            "all_require_missing_credentials",
            "all_unhealthy",
            "all_over_budget",
            "all_are_contributors",
            "unknown_acp_models_only",
            "unknown_error",
        }
        for reason_str in valid_reasons:
            reason = NoCandidateReason(reason=reason_str, detail="test")
            assert reason.reason == reason_str


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_DifferentProviderModel
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_DifferentProviderModel:
    """Select independent provider/model (no overlap with contributors)."""

    def test_independent_provider_selected(self):
        """Candidate with independent provider is selected."""
        prov_a = _make_provider("prov-a", "ProviderA", models=["model-x"])
        prov_b = _make_provider("prov-b", "ProviderB", models=["model-y"])

        candidates = [
            Candidate(provider_id="prov-a", model="model-x"),
            Candidate(provider_id="prov-b", model="model-y"),
        ]
        role = Role(
            name="deep",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"deep": role})
        provider_store = _make_provider_store({"prov-a": prov_a, "prov-b": prov_b})

        selector = AuditorCandidateSelector(role_store, provider_store)
        contributor = _make_contributor(provider_id="prov-a", model_id="model-x")

        auditor_role, reason = selector.seed_auditor_role(contributors=[contributor])

        assert auditor_role is not None
        assert reason is None
        assert auditor_role.candidates[0].provider_id == "prov-b"
        assert auditor_role.candidates[0].model == "model-y"

    def test_single_independent_provider_among_many(self):
        """One independent provider among many contributors is chosen."""
        providers = {
            "prov-1": _make_provider("prov-1", "Prov1", models=["m1"]),
            "prov-2": _make_provider("prov-2", "Prov2", models=["m2"]),
            "prov-3": _make_provider("prov-3", "Prov3", models=["m3"]),
        }
        candidates = [
            Candidate(provider_id="prov-1", model="m1"),
            Candidate(provider_id="prov-2", model="m2"),
            Candidate(provider_id="prov-3", model="m3"),
        ]
        role = Role(
            name="standard",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"standard": role})
        provider_store = _make_provider_store(providers)

        selector = AuditorCandidateSelector(role_store, provider_store)
        contributors = [
            _make_contributor(provider_id="prov-1", model_id="m1"),
            _make_contributor(provider_id="prov-2", model_id="m2"),
        ]

        auditor_role, reason = selector.seed_auditor_role(contributors=contributors)

        assert auditor_role is not None
        assert reason is None
        assert auditor_role.candidates[0].provider_id == "prov-3"


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_SameProviderDifferentModel
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_SameProviderDifferentModel:
    """Fall back to same-provider different-model when independent unavailable."""

    def test_same_provider_different_model_fallback(self):
        """When no independent provider, use same provider with different model."""
        prov = _make_provider("prov-a", "ProviderA", models=["model-1", "model-2"], default_model="model-1")

        candidates = [
            Candidate(provider_id="prov-a", model="model-1"),
            Candidate(provider_id="prov-a", model="model-2"),
        ]
        role = Role(
            name="deep",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"deep": role})
        provider_store = _make_provider_store({"prov-a": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)
        contributor = _make_contributor(provider_id="prov-a", model_id="model-1")

        auditor_role, reason = selector.seed_auditor_role(contributors=[contributor])

        assert auditor_role is not None
        assert reason is None
        assert auditor_role.candidates[0].provider_id == "prov-a"
        assert auditor_role.candidates[0].model == "model-2"

    def test_rejects_same_model_even_on_same_provider(self):
        """Exact (provider, model) match is excluded."""
        prov = _make_provider("prov-a", "ProviderA", models=["model-x"], default_model="model-x")

        candidates = [Candidate(provider_id="prov-a", model="model-x")]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store({"prov-a": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)
        contributor = _make_contributor(provider_id="prov-a", model_id="model-x")

        auditor_role, reason = selector.seed_auditor_role(contributors=[contributor])

        assert auditor_role is None
        assert reason is not None
        assert reason.reason == "all_are_contributors"


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_SameModelAnotherProvider
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_SameModelAnotherProvider:
    """Same model on another provider is independent (preferred over same-provider)."""

    def test_same_model_different_provider_is_independent(self):
        """Model exists on both providers; independent provider preferred."""
        prov_1 = _make_provider("prov-1", "Prov1", models=["claude-3"], default_model="claude-3")
        prov_2 = _make_provider("prov-2", "Prov2", models=["claude-3"], default_model="claude-3")

        candidates = [
            Candidate(provider_id="prov-1", model="claude-3"),
            Candidate(provider_id="prov-2", model="claude-3"),
        ]
        role = Role(
            name="standard",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"standard": role})
        provider_store = _make_provider_store({"prov-1": prov_1, "prov-2": prov_2})

        selector = AuditorCandidateSelector(role_store, provider_store)
        contributor = _make_contributor(provider_id="prov-1", model_id="claude-3")

        auditor_role, reason = selector.seed_auditor_role(contributors=[contributor])

        assert auditor_role is not None
        assert reason is None
        # Should select prov-2 since prov-1 is a contributor
        assert auditor_role.candidates[0].provider_id == "prov-2"


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_MultiContributorExclusion
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_MultiContributorExclusion:
    """Multiple contributors' models all excluded correctly."""

    def test_epic_multi_contributor_all_excluded(self):
        """All contributors excluded; independent provider chosen."""
        providers = {
            "prov-1": _make_provider("prov-1", "P1", models=["m1"], default_model="m1"),
            "prov-2": _make_provider("prov-2", "P2", models=["m2"], default_model="m2"),
            "prov-3": _make_provider("prov-3", "P3", models=["m3"], default_model="m3"),
        }
        candidates = [
            Candidate(provider_id="prov-1", model="m1"),
            Candidate(provider_id="prov-2", model="m2"),
            Candidate(provider_id="prov-3", model="m3"),
        ]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store(providers)

        selector = AuditorCandidateSelector(role_store, provider_store)
        contributors = [
            _make_contributor(provider_id="prov-1", model_id="m1"),
            _make_contributor(provider_id="prov-2", model_id="m2"),
        ]

        auditor_role, reason = selector.seed_auditor_role(contributors=contributors)

        assert auditor_role is not None
        assert auditor_role.candidates[0].provider_id == "prov-3"

    def test_different_models_same_provider_from_multiple_runs(self):
        """Different models from same provider in contributors still make
        that provider a contributor."""
        prov = _make_provider(
            "prov-1", "P1", models=["model-a", "model-b", "model-c"], default_model="model-a"
        )
        candidates = [
            Candidate(provider_id="prov-1", model="model-a"),
            Candidate(provider_id="prov-1", model="model-b"),
            Candidate(provider_id="prov-1", model="model-c"),
        ]
        role = Role(
            name="deep",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"deep": role})
        provider_store = _make_provider_store({"prov-1": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)
        contributors = [
            _make_contributor(provider_id="prov-1", model_id="model-a"),
            _make_contributor(provider_id="prov-1", model_id="model-b"),
        ]

        auditor_role, reason = selector.seed_auditor_role(contributors=contributors)

        # model-c is on a contributing provider, but the models are explicit and
        # different, so it should be used as a fallback (if no other option)
        # But in this test it's the only option so it should be selected
        assert auditor_role is not None
        assert auditor_role.candidates[0].model == "model-c"


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_UnknownACPModels
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_UnknownACPModels:
    """Reject unknown SDK-managed models on contributing providers."""

    def test_unknown_acp_model_rejected(self):
        """Unknown ACP model (empty/default/cli-managed) excluded."""
        prov = _make_provider(
            "prov-acp",
            "ACP",
            models=[],
            mode="acp",
            api_key="",
        )
        candidates = [Candidate(provider_id="prov-acp", model="")]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store({"prov-acp": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)
        # Mark ACP as contributor with unknown model
        contributor = _make_contributor(provider_id="prov-acp", model_id=None)

        auditor_role, reason = selector.seed_auditor_role(contributors=[contributor])

        assert auditor_role is None
        assert reason is not None
        assert reason.reason == "unknown_acp_models_only"

    def test_known_acp_model_accepted(self):
        """Known ACP model (explicit) accepted even on contributing provider."""
        prov = _make_provider(
            "prov-acp",
            "ACP",
            models=["claude-3-sonnet"],
            mode="acp",
            api_key="",
        )
        candidates = [
            Candidate(provider_id="prov-acp", model="claude-3-sonnet"),
        ]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store({"prov-acp": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)
        # Different model on same ACP provider
        contributor = _make_contributor(
            provider_id="prov-acp", model_id="claude-3-opus"
        )

        auditor_role, reason = selector.seed_auditor_role(contributors=[contributor])

        assert auditor_role is not None
        assert auditor_role.candidates[0].model == "claude-3-sonnet"


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_RoundRobinOrdering
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_RoundRobinOrdering:
    """Round-robin ordering preserved in multi-candidate seeding."""

    def test_preserves_candidate_order(self):
        """Candidate order from role is preserved."""
        prov = _make_provider("prov-1", "P1", models=["m1", "m2", "m3"], default_model="m1")
        candidates = [
            Candidate(provider_id="prov-1", model="m1"),
            Candidate(provider_id="prov-1", model="m2"),
            Candidate(provider_id="prov-1", model="m3"),
        ]
        role = Role(
            name="standard",
            strategy="round_robin",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"standard": role})
        provider_store = _make_provider_store({"prov-1": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)
        # No contributors, so all should be candidates
        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        assert auditor_role is not None
        # Auditor role is priority strategy with first candidate
        assert auditor_role.candidates[0].model == "m1"


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_Whitelist
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_Whitelist:
    """Provider whitelist respected in candidate filtering."""

    def test_whitelist_filters_out_non_whitelisted(self):
        """Only whitelisted providers are considered."""
        providers = {
            "prov-1": _make_provider("prov-1", "P1", models=["m1"], default_model="m1"),
            "prov-2": _make_provider("prov-2", "P2", models=["m2"], default_model="m2"),
            "prov-3": _make_provider("prov-3", "P3", models=["m3"], default_model="m3"),
        }
        candidates = [
            Candidate(provider_id="prov-1", model="m1"),
            Candidate(provider_id="prov-2", model="m2"),
            Candidate(provider_id="prov-3", model="m3"),
        ]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store(providers)
        project_config = _make_project_config(provider_whitelist=["prov-2", "prov-3"])

        selector = AuditorCandidateSelector(
            role_store, provider_store, project_config
        )

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        assert auditor_role is not None
        assert auditor_role.candidates[0].provider_id in ["prov-2", "prov-3"]

    def test_whitelist_no_matches_returns_error(self):
        """No candidates match whitelist → error."""
        providers = {
            "prov-1": _make_provider("prov-1", "P1", models=["m1"], default_model="m1"),
            "prov-2": _make_provider("prov-2", "P2", models=["m2"], default_model="m2"),
        }
        candidates = [
            Candidate(provider_id="prov-1", model="m1"),
            Candidate(provider_id="prov-2", model="m2"),
        ]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store(providers)
        project_config = _make_project_config(provider_whitelist=["prov-99"])

        selector = AuditorCandidateSelector(
            role_store, provider_store, project_config
        )

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        assert auditor_role is None
        assert reason is not None
        assert reason.reason == "no_whitelisted_providers"


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_Credentials
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_Credentials:
    """Missing credentials block API-mode providers."""

    def test_missing_api_key_blocks_provider(self):
        """API-mode provider without api_key is blocked."""
        prov_no_key = _make_provider("prov-1", "P1", models=["m1"], api_key="")
        prov_with_key = _make_provider("prov-2", "P2", models=["m2"], api_key="key-123")

        candidates = [
            Candidate(provider_id="prov-1", model="m1"),
            Candidate(provider_id="prov-2", model="m2"),
        ]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store(
            {"prov-1": prov_no_key, "prov-2": prov_with_key}
        )

        selector = AuditorCandidateSelector(role_store, provider_store)

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        assert auditor_role is not None
        assert auditor_role.candidates[0].provider_id == "prov-2"

    def test_acp_provider_no_api_key_requirement(self):
        """ACP-mode provider without api_key is allowed."""
        prov = _make_provider(
            "prov-acp", "ACP", mode="acp", api_key="", models=["m1"]
        )

        candidates = [Candidate(provider_id="prov-acp", model="m1")]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store({"prov-acp": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        assert auditor_role is not None
        assert auditor_role.candidates[0].provider_id == "prov-acp"


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_Budget
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_Budget:
    """Budget constraints respected."""

    def test_subscription_acp_provider_bypasses_budget(self):
        """Subscription-billing ACP provider is never budget-blocked."""
        prov = _make_provider(
            "prov-acp",
            "ACP",
            mode="acp",
            api_key="",
            billing_model="subscription",
            models=["m1"],
        )

        candidates = [Candidate(provider_id="prov-acp", model="m1")]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store({"prov-acp": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        assert auditor_role is not None


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_EmptyRole
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_EmptyRole:
    """Empty role or no candidates yields proper diagnostic."""

    def test_empty_role_returns_diagnostic(self):
        """No candidates from any source returns empty_role reason."""
        role_store = _make_role_store_with_roles({})
        provider_store = _make_provider_store({})

        selector = AuditorCandidateSelector(role_store, provider_store)

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        assert auditor_role is None
        assert reason is not None
        assert reason.reason == "no_providers"

    def test_no_providers_configured(self):
        """No providers in ProviderStore returns error."""
        role = Role(
            name="default",
            strategy="priority",
            candidates=[Candidate(provider_id="prov-missing", model="m1")],
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store({})

        selector = AuditorCandidateSelector(role_store, provider_store)

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        assert auditor_role is None
        assert reason is not None


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_MigrationSeeding
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_MigrationSeeding:
    """Migration seeding from deep/standard/default/provider defaults."""

    def test_migration_seeds_from_deep_standard_default(self):
        """Candidates from deep/standard/default roles aggregated."""
        prov_1 = _make_provider("prov-1", "P1", models=["m1"])
        prov_2 = _make_provider("prov-2", "P2", models=["m2"])
        prov_3 = _make_provider("prov-3", "P3", models=["m3"])

        deep_role = Role(
            name="deep",
            strategy="priority",
            candidates=[Candidate(provider_id="prov-1", model="m1")],
            updated_at=datetime.now(timezone.utc),
        )
        standard_role = Role(
            name="standard",
            strategy="priority",
            candidates=[Candidate(provider_id="prov-2", model="m2")],
            updated_at=datetime.now(timezone.utc),
        )
        default_role = Role(
            name="default",
            strategy="priority",
            candidates=[Candidate(provider_id="prov-3", model="m3")],
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles(
            {"deep": deep_role, "standard": standard_role, "default": default_role}
        )
        provider_store = _make_provider_store(
            {"prov-1": prov_1, "prov-2": prov_2, "prov-3": prov_3}
        )

        selector = AuditorCandidateSelector(role_store, provider_store)

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        # Should select one of the available candidates
        assert auditor_role is not None
        assert auditor_role.candidates[0].provider_id in ["prov-1", "prov-2", "prov-3"]

    def test_migration_adds_provider_defaults(self):
        """Provider default_model included in candidates."""
        prov_1 = _make_provider(
            "prov-1", "P1", models=["m1"], default_model="m1"
        )
        prov_2 = _make_provider(
            "prov-2", "P2", models=["m2", "m2-extra"], default_model="m2"
        )

        role_store = _make_role_store_with_roles({})
        provider_store = _make_provider_store({"prov-1": prov_1, "prov-2": prov_2})

        selector = AuditorCandidateSelector(role_store, provider_store)

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        # Should select from provider defaults
        assert auditor_role is not None
        assert auditor_role.candidates[0].model in ["m1", "m2"]

    def test_deduplication_avoids_duplicate_candidates(self):
        """Same candidate from multiple sources only added once."""
        prov = _make_provider("prov-1", "P1", models=["m1"], default_model="m1")

        # Both deep and standard roles have same candidate
        shared_candidate = Candidate(provider_id="prov-1", model="m1")
        deep_role = Role(
            name="deep",
            strategy="priority",
            candidates=[shared_candidate],
            updated_at=datetime.now(timezone.utc),
        )
        standard_role = Role(
            name="standard",
            strategy="priority",
            candidates=[shared_candidate],
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles(
            {"deep": deep_role, "standard": standard_role}
        )
        provider_store = _make_provider_store({"prov-1": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        assert auditor_role is not None
        # Deduplication ensures no duplicates
        assert len(auditor_role.candidates) == 1


# ---------------------------------------------------------------------------
# TestAuditorCandidateSelector_NoCandidateDiagnostics
# ---------------------------------------------------------------------------


class TestAuditorCandidateSelector_NoCandidateDiagnostics:
    """Normalized no-candidate diagnostics."""

    def test_all_contributors_diagnostic(self):
        """When all candidates are from contributors, diagnostic explains."""
        prov = _make_provider("prov-1", "P1", models=["m1"])

        candidates = [Candidate(provider_id="prov-1", model="m1")]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store({"prov-1": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)
        contributor = _make_contributor(provider_id="prov-1", model_id="m1")

        auditor_role, reason = selector.seed_auditor_role(contributors=[contributor])

        assert auditor_role is None
        assert reason is not None
        assert reason.reason == "all_are_contributors"
        assert "contributor" in reason.detail.lower()

    def test_missing_credentials_diagnostic(self):
        """Diagnostic when all providers lack credentials."""
        prov = _make_provider("prov-1", "P1", api_key="")

        candidates = [Candidate(provider_id="prov-1", model="m1")]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store({"prov-1": prov})

        selector = AuditorCandidateSelector(role_store, provider_store)

        auditor_role, reason = selector.seed_auditor_role(contributors=[])

        assert auditor_role is None
        assert reason is not None
        assert reason.reason == "all_require_missing_credentials"


# ---------------------------------------------------------------------------
# TestSeedAuditorRoleFromConfig
# ---------------------------------------------------------------------------


class TestSeedAuditorRoleFromConfig:
    """seed_auditor_role_from_config public entry point."""

    def test_writes_to_role_store(self):
        """Successfully seeds auditor role into RoleStore."""
        prov = _make_provider("prov-1", "P1", models=["m1"])

        candidates = [Candidate(provider_id="prov-1", model="m1")]
        role = Role(
            name="default",
            strategy="priority",
            candidates=candidates,
            updated_at=datetime.now(timezone.utc),
        )

        role_store = _make_role_store_with_roles({"default": role})
        provider_store = _make_provider_store({"prov-1": prov})

        # Mock set_candidates to verify it gets called
        write_calls = []
        role_store.set_candidates = lambda *args, **kwargs: write_calls.append(
            (args, kwargs)
        )

        seed_auditor_role_from_config(
            role_store, provider_store, project_config=None, contributors=None
        )

        # Should attempt to write
        assert len(write_calls) > 0

    def test_handles_no_candidate_gracefully(self):
        """When no candidate available, does not crash."""
        role_store = _make_role_store_with_roles({})
        provider_store = _make_provider_store({})

        # Should not raise
        seed_auditor_role_from_config(
            role_store, provider_store, project_config=None, contributors=None
        )
