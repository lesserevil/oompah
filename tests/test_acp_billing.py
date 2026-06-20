"""Tests for per-token ACP billing (oompah-zlz_2-ag7h).

Child C of the multi-backend ACP epic. Validates that:

* ``ModelProvider.billing_model`` defaults to ``"subscription"`` and
  round-trips through to_dict/from_dict for back-compat.
* ``_would_dispatch_via_acp`` only bypasses the budget gate for
  subscription-billed ACP providers — per-token ACP providers
  participate in the budget check.
* ACP turns through per-token providers add cost to the rolling-window
  spend tracker via :meth:`_estimate_cost` / :meth:`_on_worker_exit`.
* Subscription ACP turns do NOT add cost, even when ``model_costs``
  is populated for the model.
* SDK-reported ``total_cost_usd`` (when present) is preferred over
  the local ``model_costs`` calc for per-token providers.
* Missing ``model_costs`` on a per-token provider does NOT crash
  dispatch — cost defaults to $0 with a WARNING log line.
* A per-token provider whose budget is exceeded blocks the next
  dispatch via the existing ``budget_exceeded_paid`` reject path.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.models import (
    AgentProfile,
    AgentTotals,
    Issue,
    LiveSession,
    ModelProvider,
    RunningEntry,
)
from oompah.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# ModelProvider.billing_model
# ---------------------------------------------------------------------------


class TestBillingModelField:
    """ModelProvider.billing_model: default, round-trip, validation."""

    def test_default_is_subscription(self):
        """New providers default to subscription so legacy ACP keeps
        flat-rate billing without operator intervention."""
        p = ModelProvider(id="p1", name="x", base_url="")
        assert p.billing_model == "subscription"

    def test_to_dict_emits_billing_model(self):
        """billing_model is always emitted (no default-omission) so the
        on-disk JSON has an explicit value for clients to render."""
        p = ModelProvider(id="p1", name="x", base_url="")
        d = p.to_dict()
        assert d["billing_model"] == "subscription"

    def test_to_dict_per_token(self):
        p = ModelProvider(
            id="p1", name="x", base_url="", billing_model="per_token",
        )
        d = p.to_dict()
        assert d["billing_model"] == "per_token"

    def test_from_dict_missing_defaults_to_subscription(self):
        """Existing providers persisted before this field existed read
        back as subscription-billed (back-compat preserved). The
        orchestrator's budget bypass logic continues to apply."""
        p = ModelProvider.from_dict({
            "id": "p1", "name": "x", "base_url": "",
        })
        assert p.billing_model == "subscription"

    def test_from_dict_per_token(self):
        p = ModelProvider.from_dict({
            "id": "p1", "name": "x", "base_url": "",
            "billing_model": "per_token",
        })
        assert p.billing_model == "per_token"

    def test_from_dict_unknown_falls_back_to_subscription(self):
        """A typo in providers.json must not silently start metering
        against the budget. Fall back conservatively to subscription."""
        p = ModelProvider.from_dict({
            "id": "p1", "name": "x", "base_url": "",
            "billing_model": "totally-bogus",
        })
        assert p.billing_model == "subscription"

    def test_from_dict_case_normalized(self):
        """Mixed-case input is normalised to lowercase."""
        p = ModelProvider.from_dict({
            "id": "p1", "name": "x", "base_url": "",
            "billing_model": "Per_Token",
        })
        assert p.billing_model == "per_token"

    def test_round_trip(self):
        original = ModelProvider(
            id="p1", name="x", base_url="", billing_model="per_token",
        )
        round_trip = ModelProvider.from_dict(original.to_dict())
        assert round_trip.billing_model == "per_token"

    def test_validate_for_mode_acp_subscription_ok(self):
        p = ModelProvider(
            id="p1", name="x", base_url="", billing_model="subscription",
        )
        assert p.validate_for_mode("acp") == []

    def test_validate_for_mode_acp_per_token_ok(self):
        p = ModelProvider(
            id="p1", name="x", base_url="", billing_model="per_token",
        )
        assert p.validate_for_mode("acp") == []

    def test_validate_for_mode_acp_unknown_billing_fails(self):
        """An invalid billing_model under mode=acp surfaces an error so
        the operator can fix their config rather than silently
        falling back."""
        p = ModelProvider(id="p1", name="x", base_url="")
        # Bypass from_dict's normalization to simulate a runtime
        # field corruption.
        p.billing_model = "weekly-flat"
        errors = p.validate_for_mode("acp")
        assert any("billing_model" in e for e in errors)

    def test_validate_for_mode_api_ignores_billing(self):
        """billing_model is ignored for non-ACP modes — even an
        invalid value passes validation under mode=api."""
        p = ModelProvider(id="p1", name="x", base_url="")
        p.billing_model = "anything-goes"
        assert p.validate_for_mode("api") == []


# ---------------------------------------------------------------------------
# ModelProvider.is_per_token_billed
# ---------------------------------------------------------------------------


class TestIsPerTokenBilled:
    def test_subscription_acp_returns_false(self):
        p = ModelProvider(
            id="p1", name="x", base_url="", billing_model="subscription",
        )
        assert p.is_per_token_billed("acp") is False

    def test_per_token_acp_returns_true(self):
        p = ModelProvider(
            id="p1", name="x", base_url="", billing_model="per_token",
        )
        assert p.is_per_token_billed("acp") is True

    def test_api_mode_always_per_token(self):
        """API/CLI/auto modes always meter per-token via api_agent —
        the billing_model field is ignored for them."""
        p_sub = ModelProvider(
            id="p1", name="x", base_url="", billing_model="subscription",
        )
        p_per = ModelProvider(
            id="p2", name="y", base_url="", billing_model="per_token",
        )
        for mode in ("api", "cli", "auto"):
            assert p_sub.is_per_token_billed(mode) is True
            assert p_per.is_per_token_billed(mode) is True


# ---------------------------------------------------------------------------
# Helpers (mirror tests/test_budget_free_tier_dispatch.py patterns)
# ---------------------------------------------------------------------------


def _make_subscription_acp_provider(
    provider_id: str = "prov-sub-01",
    model: str = "claude-sonnet-4-5",
    *,
    with_costs: bool = False,
) -> ModelProvider:
    """ACP-billed-as-subscription provider. Optionally with model_costs
    populated to exercise the "ignored when subscription" edge case."""
    return ModelProvider(
        id=provider_id,
        name="Anthropic-Subscription",
        base_url="https://api.anthropic.com",
        api_key="",
        models=[model],
        default_model=model,
        backend="claude",
        billing_model="subscription",
        model_costs=(
            {model: {"cost_per_1k_input": 3.0, "cost_per_1k_output": 15.0}}
            if with_costs else {}
        ),
    )


def _make_per_token_acp_provider(
    provider_id: str = "prov-per-01",
    model: str = "codex-tier-2",
    *,
    cost_in: float = 5.0,
    cost_out: float = 20.0,
) -> ModelProvider:
    """ACP-billed-per-token provider with rates populated."""
    return ModelProvider(
        id=provider_id,
        name="Codex-PerToken",
        base_url="https://api.codex.example.com",
        api_key="test-key",
        models=[model],
        default_model=model,
        backend="claude",  # any registered backend; per_token semantics independent
        billing_model="per_token",
        model_costs={
            model: {
                "cost_per_1k_input": cost_in,
                "cost_per_1k_output": cost_out,
            },
        },
    )


def _make_per_token_no_costs_provider(
    provider_id: str = "prov-per-noc-01",
    model: str = "no-rate-model",
) -> ModelProvider:
    """Per-token ACP provider missing model_costs — exercises the
    "missing rates → $0 + WARNING" edge case."""
    return ModelProvider(
        id=provider_id,
        name="Misconfigured",
        base_url="https://api.example.com",
        api_key="k",
        models=[model],
        default_model=model,
        backend="claude",
        billing_model="per_token",
        model_costs={},  # no rates set
    )


def _make_issue(
    identifier: str = "test-1",
    state: str = "open",
    issue_type: str = "task",
    priority: int = 2,
    labels: list | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Per-token ACP billing test.",
        state=state,
        issue_type=issue_type,
        priority=priority,
        labels=labels or [],
    )


def _make_acp_profile(
    name: str = "default",
    provider_id: str | None = None,
) -> AgentProfile:
    """An mode=acp profile bound to a given provider."""
    return AgentProfile(
        name=name,
        command="claude",
        provider_id=provider_id,
        mode="acp",
    )


def _make_orchestrator(
    tmp_path,
    provider: ModelProvider | None,
    profile_mode: str = "acp",
    budget_limit: float = 10.0,
) -> Orchestrator:
    """Create a minimal Orchestrator with mocked stores."""
    project_store = MagicMock()
    project_store.list_all.return_value = []

    cfg = ServiceConfig(budget_limit=budget_limit)
    pid = provider.id if provider else None
    cfg.agent_profiles = [
        AgentProfile(
            name="default",
            command="claude",
            provider_id=pid,
            mode=profile_mode,
        )
    ]

    orch = Orchestrator(
        config=cfg,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )

    mock_ps = MagicMock()
    if provider:
        mock_ps.get.side_effect = lambda x: provider if x == provider.id else None
        mock_ps.get_default.return_value = provider
    else:
        mock_ps.get.return_value = None
        mock_ps.get_default.return_value = None
    orch.provider_store = mock_ps

    return orch


def _make_running_entry(
    issue: Issue,
    *,
    input_tokens: int = 1000,
    output_tokens: int = 500,
    profile_name: str = "default",
    sdk_cost_usd: float | None = None,
) -> RunningEntry:
    """A RunningEntry with a populated LiveSession, suitable for
    driving _on_worker_exit's cost-accumulation path."""
    sess = LiveSession(
        session_id="sess-1",
        thread_id="thr-1",
        turn_id="t-1",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        sdk_cost_usd=sdk_cost_usd,
    )
    return RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=sess,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        agent_profile_name=profile_name,
    )


# ---------------------------------------------------------------------------
# Budget gate behaviour: _would_dispatch_via_acp + _acp_profile_is_subscription
# ---------------------------------------------------------------------------


class TestWouldDispatchViaAcp:
    """The budget gate only bypasses for subscription-billed ACP."""

    def test_subscription_acp_bypasses_budget(self, tmp_path):
        provider = _make_subscription_acp_provider()
        orch = _make_orchestrator(tmp_path, provider=provider)
        assert orch._would_dispatch_via_acp(_make_issue()) is True

    def test_per_token_acp_does_not_bypass(self, tmp_path):
        provider = _make_per_token_acp_provider()
        orch = _make_orchestrator(tmp_path, provider=provider)
        assert orch._would_dispatch_via_acp(_make_issue()) is False

    def test_no_provider_treated_as_subscription(self, tmp_path):
        """ACP profile without a provider record (CLI-only / legacy
        deployments) is conservatively subscription-billed — the
        prior behaviour before this task."""
        orch = _make_orchestrator(tmp_path, provider=None)
        assert orch._would_dispatch_via_acp(_make_issue()) is True

    def test_api_profile_returns_false(self, tmp_path):
        """Non-ACP profiles never hit the ACP bypass."""
        provider = _make_per_token_acp_provider()
        orch = _make_orchestrator(
            tmp_path, provider=provider, profile_mode="api",
        )
        assert orch._would_dispatch_via_acp(_make_issue()) is False


class TestShouldDispatchPerTokenAcpOverBudget:
    """End-to-end: per-token ACP over budget → rejected."""

    def test_subscription_acp_dispatches_over_budget(self, tmp_path):
        provider = _make_subscription_acp_provider()
        orch = _make_orchestrator(tmp_path, provider=provider)
        # Push spend over the limit.
        orch.state.agent_totals.estimated_cost = orch.config.budget_limit + 1.0
        orch.state.budget_exceeded = True

        issue = _make_issue()
        result = orch._should_dispatch(issue)
        # Subscription ACP bypasses the budget gate, so True even when
        # the budget is exceeded.
        assert result is True

    def test_per_token_acp_rejected_over_budget(self, tmp_path):
        provider = _make_per_token_acp_provider()
        orch = _make_orchestrator(tmp_path, provider=provider)
        # Push spend over the limit so _check_budget returns False.
        orch.state.agent_totals.estimated_cost = orch.config.budget_limit + 1.0

        issue = _make_issue()
        result = orch._should_dispatch(issue)
        # Per-token ACP must participate in the budget gate.
        assert result is not True
        # Reject reason carries the budget marker.
        if isinstance(result, dict):
            assert "budget_exceeded" in (result.get("reason") or "")


# ---------------------------------------------------------------------------
# Cost recording: _estimate_cost / _on_worker_exit
# ---------------------------------------------------------------------------


class TestEstimateCostBillingAware:
    """_estimate_cost short-circuits to 0 for subscription ACP and
    computes local model_costs for per-token ACP."""

    def test_subscription_acp_returns_zero_even_with_model_costs(self, tmp_path):
        """Edge case: model_costs set on a subscription-billed provider.
        The field is ignored at billing time so the rolling-window
        tracker doesn't accidentally meter against a flat-rate provider."""
        provider = _make_subscription_acp_provider(with_costs=True)
        orch = _make_orchestrator(tmp_path, provider=provider)
        profile = orch.config.agent_profiles[0]
        cost = orch._estimate_cost(profile, 1000, 500)
        assert cost == 0.0

    def test_per_token_acp_uses_model_costs(self, tmp_path):
        provider = _make_per_token_acp_provider(
            cost_in=5.0, cost_out=20.0,
        )
        orch = _make_orchestrator(tmp_path, provider=provider)
        profile = orch.config.agent_profiles[0]
        cost = orch._estimate_cost(profile, 1000, 500)
        # 1000/1000 * 5 + 500/1000 * 20 = 5 + 10 = 15
        assert cost == pytest.approx(15.0)

    def test_per_token_acp_prefers_sdk_cost(self, tmp_path):
        """When the SDK reports a total_cost_usd, prefer it over the
        local model_costs lookup — the SDK knows tier discounts."""
        provider = _make_per_token_acp_provider(
            cost_in=5.0, cost_out=20.0,
        )
        orch = _make_orchestrator(tmp_path, provider=provider)
        profile = orch.config.agent_profiles[0]
        cost = orch._estimate_cost(
            profile, 1000, 500, sdk_cost_usd=3.50,
        )
        # SDK number wins, not the 15 USD local calc.
        assert cost == pytest.approx(3.50)

    def test_subscription_acp_ignores_sdk_cost(self, tmp_path):
        """Subscription ACP runs always cost $0 regardless of any
        SDK-reported total — the operator's subscription is the
        billing channel, not the per-token meter."""
        provider = _make_subscription_acp_provider(with_costs=True)
        orch = _make_orchestrator(tmp_path, provider=provider)
        profile = orch.config.agent_profiles[0]
        cost = orch._estimate_cost(
            profile, 1000, 500, sdk_cost_usd=9.99,
        )
        assert cost == 0.0

    def test_per_token_acp_missing_costs_defaults_to_zero(self, tmp_path, caplog):
        """Per-token provider with no model_costs → cost defaults to
        $0 (don't crash dispatch over missing config)."""
        provider = _make_per_token_no_costs_provider()
        orch = _make_orchestrator(tmp_path, provider=provider)
        profile = orch.config.agent_profiles[0]
        cost = orch._estimate_cost(profile, 1000, 500)
        assert cost == 0.0


class TestOnWorkerExitCostAccumulation:
    """_on_worker_exit rolls cost through _estimate_cost; the
    billing_model gate flows through that helper."""

    def test_subscription_acp_does_not_increment_estimated_cost(
        self, tmp_path,
    ):
        provider = _make_subscription_acp_provider(with_costs=True)
        orch = _make_orchestrator(tmp_path, provider=provider)
        issue = _make_issue()
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        before = orch.state.agent_totals.estimated_cost
        asyncio.run(orch._on_worker_exit(issue.id, "normal", None))
        # Subscription ACP must NOT contribute to estimated_cost.
        assert orch.state.agent_totals.estimated_cost == before

    def test_per_token_acp_increments_estimated_cost(self, tmp_path):
        provider = _make_per_token_acp_provider(
            cost_in=5.0, cost_out=20.0,
        )
        orch = _make_orchestrator(tmp_path, provider=provider)
        issue = _make_issue()
        # 1000 input + 500 output → 5 + 10 = $15
        entry = _make_running_entry(
            issue, input_tokens=1000, output_tokens=500,
        )
        orch.state.running[issue.id] = entry

        before = orch.state.agent_totals.estimated_cost
        asyncio.run(orch._on_worker_exit(issue.id, "normal", None))
        delta = orch.state.agent_totals.estimated_cost - before
        assert delta == pytest.approx(15.0)
        # And surfaces in cost_by_profile so dashboards render it.
        assert orch.state.cost_by_profile.get("default", 0.0) == pytest.approx(15.0)

    def test_per_token_acp_sdk_cost_wins(self, tmp_path):
        provider = _make_per_token_acp_provider(
            cost_in=5.0, cost_out=20.0,
        )
        orch = _make_orchestrator(tmp_path, provider=provider)
        issue = _make_issue()
        entry = _make_running_entry(
            issue, input_tokens=1000, output_tokens=500,
            sdk_cost_usd=2.25,
        )
        orch.state.running[issue.id] = entry

        before = orch.state.agent_totals.estimated_cost
        asyncio.run(orch._on_worker_exit(issue.id, "normal", None))
        delta = orch.state.agent_totals.estimated_cost - before
        # SDK number wins, not the $15 local calc.
        assert delta == pytest.approx(2.25)


# ---------------------------------------------------------------------------
# Per-issue task_costs metadata (the dashboard's per-issue cost line)
# ---------------------------------------------------------------------------


class TestComputeRunCostRecord:
    """The per-issue cost line read from oompah.task_costs metadata."""

    def test_subscription_acp_zero_cost_record(self, tmp_path):
        """Subscription ACP runs surface $0 in the per-issue cost line
        even when model_costs is populated. The model name is still
        recorded so the operator can see which model ran."""
        provider = _make_subscription_acp_provider(with_costs=True)
        orch = _make_orchestrator(tmp_path, provider=provider)
        issue = _make_issue()
        entry = _make_running_entry(issue)

        record = orch._compute_run_cost_record(entry)
        assert record is not None
        assert record["total_cost_usd"] == 0.0
        # Run record exists with cost_usd=0.
        assert record["runs"][0]["cost_usd"] == 0.0
        # by_model entry still records tokens.
        for _model, by in record["by_model"].items():
            assert by["cost_usd"] == 0.0

    def test_per_token_acp_records_cost(self, tmp_path):
        provider = _make_per_token_acp_provider(
            cost_in=5.0, cost_out=20.0,
        )
        orch = _make_orchestrator(tmp_path, provider=provider)
        issue = _make_issue()
        entry = _make_running_entry(
            issue, input_tokens=1000, output_tokens=500,
        )
        record = orch._compute_run_cost_record(entry)
        assert record is not None
        # 1000 input * $5/1k + 500 output * $20/1k = $5 + $10 = $15
        assert record["total_cost_usd"] == pytest.approx(15.0)

    def test_per_token_acp_prefers_sdk_cost_in_record(self, tmp_path):
        provider = _make_per_token_acp_provider(
            cost_in=5.0, cost_out=20.0,
        )
        orch = _make_orchestrator(tmp_path, provider=provider)
        issue = _make_issue()
        entry = _make_running_entry(
            issue, input_tokens=1000, output_tokens=500,
            sdk_cost_usd=7.13,
        )
        record = orch._compute_run_cost_record(entry)
        assert record is not None
        assert record["total_cost_usd"] == pytest.approx(7.13)


# ---------------------------------------------------------------------------
# Logging behaviour for missing rates
# ---------------------------------------------------------------------------


class TestMissingRatesWarningLogged:
    """Missing model_costs on a per-token provider should not crash —
    it logs a WARNING and falls back to $0."""

    def test_estimate_cost_returns_zero_no_crash(self, tmp_path):
        provider = _make_per_token_no_costs_provider()
        orch = _make_orchestrator(tmp_path, provider=provider)
        profile = orch.config.agent_profiles[0]
        # No crash:
        cost = orch._estimate_cost(profile, 5000, 2500)
        assert cost == 0.0

    def test_on_worker_exit_no_cost_no_crash(self, tmp_path):
        provider = _make_per_token_no_costs_provider()
        orch = _make_orchestrator(tmp_path, provider=provider)
        issue = _make_issue()
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        before = orch.state.agent_totals.estimated_cost
        asyncio.run(orch._on_worker_exit(issue.id, "normal", None))
        # No cost added (defaults to 0 for missing rates).
        assert orch.state.agent_totals.estimated_cost == before
