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

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
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
    backend: str | None = None,
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
        backend=backend,
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
            "missing_audit_capability",
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

    def test_same_provider_fallback_is_not_kept_with_independent_candidates(self):
        """Contributing-provider fallbacks are used only when independence is unavailable."""
        providers = {
            "prov-a": _make_provider(
                "prov-a", "ProviderA", models=["model-1", "model-2"]
            ),
            "prov-b": _make_provider("prov-b", "ProviderB", models=["model-3"]),
        }
        role = Role(
            name="default",
            strategy="round_robin",
            candidates=[
                Candidate(provider_id="prov-a", model="model-1"),
                Candidate(provider_id="prov-a", model="model-2"),
                Candidate(provider_id="prov-b", model="model-3"),
            ],
            updated_at=datetime.now(timezone.utc),
        )

        selector = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store(providers),
        )
        auditor_role, reason = selector.seed_auditor_role(
            contributors=[_make_contributor(provider_id="prov-a", model_id="model-1")]
        )

        assert reason is None
        assert auditor_role is not None
        assert [(c.provider_id, c.model) for c in auditor_role.candidates] == [
            ("prov-b", "model-3")
        ]

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


class TestAuditorCandidateSelector_AuditCapability:
    """Only transports with a durable audit-verdict channel are eligible."""

    @staticmethod
    def _role(*candidates: Candidate) -> Role:
        return Role(
            name=AUDITOR_ROLE_NAME,
            strategy="priority",
            candidates=list(candidates),
            updated_at=datetime.now(timezone.utc),
        )

    def test_subscription_codex_is_skipped_for_capable_candidate(self):
        codex = _make_provider(
            "codex-subscription",
            "Codex Subscription",
            mode="acp",
            api_key="",
            billing_model="subscription",
            backend="codex",
            models=["gpt-5.6-sol"],
        )
        claude = _make_provider(
            "claude-subscription",
            "Claude Subscription",
            mode="acp",
            api_key="",
            billing_model="subscription",
            backend="claude",
            models=["sonnet"],
        )
        role = self._role(
            Candidate(provider_id=codex.id, model="gpt-5.6-sol"),
            Candidate(provider_id=claude.id, model="sonnet"),
        )
        selector = AuditorCandidateSelector(
            _make_role_store_with_roles({AUDITOR_ROLE_NAME: role}),
            _make_provider_store({codex.id: codex, claude.id: claude}),
        )

        candidates, reason = selector.select_candidates()

        assert reason is None
        assert [(item.provider_id, item.model) for item in candidates] == [
            (claude.id, "sonnet")
        ]

    def test_subscription_codex_only_reports_missing_capability(self):
        codex = _make_provider(
            "codex-subscription",
            "Codex Subscription",
            mode="acp",
            api_key="",
            billing_model="subscription",
            backend="codex",
            models=["gpt-5.6-sol"],
        )
        role = self._role(Candidate(provider_id=codex.id, model="gpt-5.6-sol"))
        selector = AuditorCandidateSelector(
            _make_role_store_with_roles({AUDITOR_ROLE_NAME: role}),
            _make_provider_store({codex.id: codex}),
        )

        candidates, reason = selector.select_candidates()

        assert candidates == []
        assert reason is not None
        assert reason.reason == "missing_audit_capability"
        assert "Codex Subscription" in reason.detail

    def test_per_token_codex_remains_eligible(self):
        codex = _make_provider(
            "codex-api",
            "Codex API",
            mode="acp",
            billing_model="per_token",
            backend="codex",
            models=["gpt-5.6-sol"],
        )
        role = self._role(Candidate(provider_id=codex.id, model="gpt-5.6-sol"))
        selector = AuditorCandidateSelector(
            _make_role_store_with_roles({AUDITOR_ROLE_NAME: role}),
            _make_provider_store({codex.id: codex}),
        )

        candidates, reason = selector.select_candidates()

        assert reason is None
        assert [(item.provider_id, item.model) for item in candidates] == [
            (codex.id, "gpt-5.6-sol")
        ]


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

    def test_does_not_overwrite_existing_operator_configuration(self):
        """Repeated migration preserves the operator's auditor candidates."""
        provider = _make_provider("prov-1", "P1", models=["m1"])
        existing = Role(
            name=AUDITOR_ROLE_NAME,
            strategy="priority",
            candidates=[Candidate(provider_id="prov-1", model="m1")],
            updated_at=datetime.now(timezone.utc),
        )
        role_store = _make_role_store_with_roles({AUDITOR_ROLE_NAME: existing})
        write_calls = []
        role_store.set_candidates = lambda *args, **kwargs: write_calls.append(
            (args, kwargs)
        )

        seed_auditor_role_from_config(
            role_store,
            _make_provider_store({"prov-1": provider}),
        )

        assert role_store.get(AUDITOR_ROLE_NAME) is existing
        assert write_calls == []


class TestAuditorCandidateSelectorUnknownProvenance:
    """Missing contributor identity must not be treated as independent."""

    def test_missing_contributor_provider_fails_closed(self):
        provider = _make_provider("prov-1", "P1", models=["m1"])
        role = Role(
            name="default",
            strategy="priority",
            candidates=[Candidate(provider_id="prov-1", model="m1")],
            updated_at=datetime.now(timezone.utc),
        )
        selector = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"prov-1": provider}),
        )

        selected, reason = selector.seed_auditor_role(
            contributors=[_make_contributor(provider_id=None, model_id="m1")]
        )

        assert selected is None
        assert reason is not None
        assert reason.reason == "unknown_error"
        assert "provider identity" in reason.detail


class TestAuditorCandidateSelectorPolicyGaps:
    """Regression coverage for policy checks that must fail closed."""

    @pytest.mark.parametrize("endpoint", ["", "/v1", "ftp://provider.example/v1"])
    def test_invalid_api_endpoint_is_excluded_from_auditor_role(self, endpoint):
        invalid = _make_provider("invalid", "Invalid", base_url=endpoint)
        valid = _make_provider("valid", "Valid", base_url="https://valid.example/v1")
        role = Role(
            "default",
            "priority",
            [Candidate("invalid", "test-model-1"), Candidate("valid", "test-model-1")],
            datetime.now(timezone.utc),
        )

        selected, reason = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"invalid": invalid, "valid": valid}),
        ).seed_auditor_role()

        assert reason is None
        assert selected is not None
        assert [candidate.provider_id for candidate in selected.candidates] == ["valid"]

    def test_all_invalid_api_endpoints_have_structured_safe_diagnostic(self):
        secret = "sk-do-not-log"
        invalid = _make_provider(
            "invalid", "Invalid", base_url=f"https://user:{secret}@provider.example/v1"
        )
        role = Role(
            "default", "priority", [Candidate("invalid", "test-model-1")], datetime.now(timezone.utc)
        )

        selected, reason = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"invalid": invalid}),
        ).seed_auditor_role()

        assert selected is None
        assert reason is not None
        assert reason.reason == "invalid_base_url"
        assert secret not in reason.detail
        assert reason.to_dict()["reason"] == "invalid_base_url"

    def test_acp_candidate_does_not_require_openai_endpoint(self):
        acp = _make_provider(
            "acp", "ACP", mode="acp", base_url="", api_key="", models=[], default_model=""
        )
        role = Role(
            "default", "priority", [Candidate("acp", "")], datetime.now(timezone.utc)
        )

        selected, reason = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"acp": acp}),
        ).seed_auditor_role()

        assert reason is None
        assert selected is not None
        assert selected.candidates[0].provider_id == "acp"

    def test_seed_retains_union_and_uses_round_robin_order(self):
        providers = {
            "deep-provider": _make_provider("deep-provider", "Deep", ["deep-model"]),
            "standard-provider": _make_provider(
                "standard-provider", "Standard", ["standard-model"]
            ),
            "default-provider": _make_provider(
                "default-provider", "Default", ["default-model"]
            ),
            "remaining-provider": _make_provider(
                "remaining-provider", "Remaining", ["remaining-model"]
            ),
        }
        now = datetime.now(timezone.utc)
        roles = {
            "deep": Role(
                "deep", "priority", [Candidate("deep-provider", "deep-model")], now
            ),
            "standard": Role(
                "standard", "priority", [Candidate("standard-provider", "standard-model")], now
            ),
            "default": Role(
                "default", "priority", [Candidate("default-provider", "default-model")], now
            ),
        }
        role_store = _make_role_store_with_roles(roles)
        provider_store = _make_provider_store(providers)

        role, reason = AuditorCandidateSelector(role_store, provider_store).seed_auditor_role()

        assert reason is None
        assert role is not None
        assert role.strategy == "round_robin"
        assert [(c.provider_id, c.model) for c in role.candidates] == [
            ("deep-provider", "deep-model"),
            ("standard-provider", "standard-model"),
            ("default-provider", "default-model"),
            ("remaining-provider", "remaining-model"),
        ]

    def test_health_result_blocks_unhealthy_provider(self):
        provider = _make_provider("provider", "Provider", ["model"])
        role = Role(
            "default", "priority", [Candidate("provider", "model")], datetime.now(timezone.utc)
        )
        selector = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"provider": provider}),
            health_results={
                ("provider", "model"): {
                    "success": False,
                    "error_reason": "timeout",
                }
            },
        )

        selected, reason = selector.seed_auditor_role()

        assert selected is None
        assert reason is not None
        assert reason.reason == "all_unhealthy"
        assert "timeout" in reason.detail

    def test_provider_level_health_cannot_authorize_a_different_model(self):
        provider = _make_provider("provider", "Provider", ["one", "two"])
        role = Role(
            "default",
            "priority",
            [Candidate("provider", "two")],
            datetime.now(timezone.utc),
        )
        selector = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"provider": provider}),
            health_results={"provider": {"success": True}},
        )

        selected, reason = selector.seed_auditor_role()

        assert selected is None
        assert reason is not None
        assert reason.reason == "all_unhealthy"
        assert "health_unknown" in reason.detail

    def test_provider_health_attribute_blocks_unhealthy_provider(self):
        provider = _make_provider("provider", "Provider", ["model"])
        provider.health_status = "overloaded"
        role = Role(
            "default", "priority", [Candidate("provider", "model")], datetime.now(timezone.utc)
        )

        selected, reason = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"provider": provider}),
        ).seed_auditor_role()

        assert selected is None
        assert reason is not None
        assert reason.reason == "all_unhealthy"

    def test_budget_state_blocks_paid_candidate(self):
        provider = _make_provider("provider", "Provider", ["model"])
        role = Role(
            "default", "priority", [Candidate("provider", "model")], datetime.now(timezone.utc)
        )
        selector = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"provider": provider}),
            budget_state={"budget_limit": 1.0, "estimated_cost": 1.0},
        )

        selected, reason = selector.seed_auditor_role()

        assert selected is None
        assert reason is not None
        assert reason.reason == "all_over_budget"

    def test_dataclass_like_budget_state_blocks_paid_candidate(self):
        provider = _make_provider("provider", "Provider", ["model"])
        role = Role(
            "default", "priority", [Candidate("provider", "model")], datetime.now(timezone.utc)
        )
        selected, reason = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"provider": provider}),
            budget_state=SimpleNamespace(budget_exceeded=True),
        ).seed_auditor_role()

        assert selected is None
        assert reason is not None
        assert reason.reason == "all_over_budget"

    def test_explicitly_free_candidate_survives_over_budget_state(self):
        provider = _make_provider("provider", "Provider", ["free-model"])
        provider.model_costs = {
            "free-model": {"cost_per_1k_input": 0, "cost_per_1k_output": 0}
        }
        role = Role(
            "default", "priority", [Candidate("provider", "free-model")], datetime.now(timezone.utc)
        )
        selected, reason = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"provider": provider}),
            budget_state={"budget_limit": 1.0, "estimated_cost": 2.0},
        ).seed_auditor_role()

        assert reason is None
        assert selected is not None
        assert selected.candidates[0].model == "free-model"

    def test_project_whitelist_accepts_provider_name(self):
        provider = _make_provider("provider-id", "Operator Provider", ["model"])
        role = Role(
            "default", "priority", [Candidate("provider-id", "model")], datetime.now(timezone.utc)
        )
        selected, reason = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"provider-id": provider}),
            _make_project_config(["operator provider"]),
        ).seed_auditor_role()

        assert reason is None
        assert selected is not None

    def test_unknown_contributor_model_blocks_same_provider_explicit_fallback(self):
        provider = _make_provider("provider", "Provider", ["model-a", "model-b"])
        role = Role(
            "default",
            "priority",
            [Candidate("provider", "model-a"), Candidate("provider", "model-b")],
            datetime.now(timezone.utc),
        )
        contributor = _make_contributor(provider_id="provider", model_id=None)

        selected, reason = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"provider": provider}),
        ).seed_auditor_role([contributor])

        assert selected is None
        assert reason is not None
        assert reason.reason == "unknown_acp_models_only"

    def test_invalid_model_has_normalized_diagnostic(self):
        provider = _make_provider("provider", "Provider", ["known-model"])
        provider.default_model = None
        role = Role(
            "default", "priority", [Candidate("provider", "unknown-model")], datetime.now(timezone.utc)
        )
        selected, reason = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"provider": provider}),
        ).seed_auditor_role()

        assert selected is None
        assert reason is not None
        assert reason.reason == "invalid_model"

    def test_budget_is_checked_before_model_validity(self):
        """The documented eligibility pipeline reports the budget gate first."""
        provider = _make_provider("provider", "Provider", ["known-model"])
        provider.default_model = None
        role = Role(
            "default",
            "priority",
            [Candidate("provider", "unknown-model")],
            datetime.now(timezone.utc),
        )
        selected, reason = AuditorCandidateSelector(
            _make_role_store_with_roles({"default": role}),
            _make_provider_store({"provider": provider}),
            budget_state={"budget_limit": 1.0, "estimated_cost": 1.0},
        ).seed_auditor_role()

        assert selected is None
        assert reason is not None
        assert reason.reason == "all_over_budget"


class TestContributorAuditorReservation:
    """OOMPAH-865: contributor dispatch must leave a terminal auditor path."""

    @staticmethod
    def _selector(models: list[str], *, unhealthy: set[str] | None = None):
        providers = {}
        candidates = []
        for model in models:
            provider = _make_provider(
                f"provider-{model}", model, [model], default_model=model
            )
            if model in (unhealthy or set()):
                provider.healthy = False
            providers[provider.id] = provider
            candidates.append(Candidate(provider.id, model))
        role = Role(
            AUDITOR_ROLE_NAME,
            "priority",
            candidates,
            datetime.now(timezone.utc),
        )
        return AuditorCandidateSelector(
            _make_role_store_with_roles({AUDITOR_ROLE_NAME: role}),
            _make_provider_store(providers),
        ), candidates

    def test_haiku_sonnet_opus_then_reserves_terra_for_terminal_audit(self):
        """The O858 escalation chain never spends its final auditor candidate."""
        selector, candidates = self._selector(["haiku", "sonnet", "opus", "terra"])
        contributors: list[WorkContributor] = []
        selected: list[str] = []

        for candidate in candidates:
            allowed, reserved, reason = selector.reserve_for_contributor_candidates(
                [candidate], contributors
            )
            if allowed:
                selected.append(candidate.model)
                contributors.append(
                    _make_contributor(candidate.provider_id, candidate.model)
                )
            else:
                assert candidate.model == "terra"
                assert reason is not None
                assert reason.reason == "insufficient_independent_candidates"
                assert reserved == candidate

        assert selected == ["haiku", "sonnet", "opus"]

    def test_same_decision_survives_restart_and_isolated_concurrent_tasks(self):
        """The decision derives from durable evidence, not process-local rotation."""
        selector, candidates = self._selector(["haiku", "sonnet", "opus", "terra"])
        contributors = [
            _make_contributor(candidates[0].provider_id, "haiku"),
            _make_contributor(candidates[1].provider_id, "sonnet"),
        ]

        # A newly constructed selector represents a service restart.  A second
        # task with the same persisted evidence must see the same reservation,
        # even when both dispatch decisions are made concurrently.
        restarted, _ = self._selector(["haiku", "sonnet", "opus", "terra"])
        with ThreadPoolExecutor(max_workers=2) as executor:
            first, second = list(
                executor.map(
                    lambda value: value.reserve_for_contributor_candidates(
                        [candidates[2]], contributors
                    ),
                    (selector, restarted),
                )
            )

        assert first[0] == [candidates[2]]
        assert first[1] == candidates[3]
        assert first[2] is None
        assert second[0] == [candidates[2]]
        assert second[1] == candidates[3]
        assert second[2] is None

    def test_dynamic_health_reassigns_reservation_without_consuming_last_healthy(self):
        selector, candidates = self._selector(
            ["haiku", "sonnet", "opus", "terra"], unhealthy={"terra"}
        )
        contributors = [_make_contributor(candidates[0].provider_id, "haiku")]

        allowed, reserved, reason = selector.reserve_for_contributor_candidates(
            [candidates[1], candidates[2]], contributors
        )

        assert allowed == [candidates[1]]
        assert reserved == candidates[2]
        assert reason is None

    def test_dynamic_role_configuration_reassigns_reservation(self):
        selector, candidates = self._selector(["haiku", "sonnet", "opus", "terra"])
        contributors = [_make_contributor(candidates[0].provider_id, "haiku")]
        role = selector.role_store.get(AUDITOR_ROLE_NAME)

        before = selector.reserve_for_contributor_candidates(
            [candidates[1], candidates[2], candidates[3]], contributors
        )
        role.candidates = role.candidates[:-1]  # operator removes terra at runtime
        after = selector.reserve_for_contributor_candidates(
            [candidates[1], candidates[2]], contributors
        )

        assert before[1] == candidates[3]
        assert after[0] == [candidates[1]]
        assert after[1] == candidates[2]
        assert after[2] is None

    def test_single_healthy_candidate_returns_actionable_predispatch_reason(self):
        selector, candidates = self._selector(["terra"])

        allowed, reserved, reason = selector.reserve_for_contributor_candidates(
            candidates, []
        )

        assert allowed == []
        assert reserved == candidates[0]
        assert reason is not None
        assert reason.reason == "insufficient_independent_candidates"
        assert "Configure or restore" in reason.detail

    def test_reservation_defaults_to_last_candidate_without_usage_hook(self):
        """Back-compat: with no usage signal, the last candidate is reserved."""
        selector, candidates = self._selector(["haiku", "sonnet", "opus", "terra"])

        _allowed, reserved, reason = selector.reserve_for_contributor_candidates(
            list(candidates), []
        )

        assert reason is None
        assert reserved == candidates[-1]

    def test_reservation_rotates_to_least_recently_used_candidate(self):
        """With a usage hook, the reserved auditor rotates (LRU), so no single
        provider is permanently excluded from implementation dispatch."""
        selector, candidates = self._selector(["haiku", "sonnet", "opus", "terra"])
        # Make the LAST candidate (terra) the most-recently-used and an earlier
        # one (sonnet) the least-recently-used; the reservation should pick the
        # LRU (sonnet) instead of the configured-last (terra).
        usage = {
            ("provider-haiku", "haiku"): "2026-08-21T00:00:03+00:00",
            ("provider-sonnet", "sonnet"): "2026-08-21T00:00:01+00:00",
            ("provider-opus", "opus"): "2026-08-21T00:00:02+00:00",
            ("provider-terra", "terra"): "2026-08-21T00:00:09+00:00",
        }
        selector.auditor_last_used = lambda pid, model: usage.get((pid, model))

        _allowed, reserved, reason = selector.reserve_for_contributor_candidates(
            list(candidates), []
        )

        assert reason is None
        assert reserved is not None
        assert (reserved.provider_id, reserved.model) == ("provider-sonnet", "sonnet")

    def test_reservation_prefers_never_used_candidate(self):
        """A never-used candidate sorts oldest and is reserved first."""
        selector, candidates = self._selector(["haiku", "sonnet", "opus", "terra"])
        usage = {
            ("provider-haiku", "haiku"): "2026-08-21T00:00:01+00:00",
            ("provider-sonnet", "sonnet"): "2026-08-21T00:00:02+00:00",
            # opus never used -> None
            ("provider-terra", "terra"): "2026-08-21T00:00:03+00:00",
        }
        selector.auditor_last_used = lambda pid, model: usage.get((pid, model))

        _allowed, reserved, reason = selector.reserve_for_contributor_candidates(
            list(candidates), []
        )

        assert reason is None
        assert reserved is not None
        assert (reserved.provider_id, reserved.model) == ("provider-opus", "opus")
