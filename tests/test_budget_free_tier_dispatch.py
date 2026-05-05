"""Tests for budget-cap free-tier model bypass (oompah-zlz_2-fvt).

When the budget window's spend exceeds the limit, _should_dispatch should still
permit dispatch if the model that *would* be used for this issue has $0 cost in
the resolved provider's model_costs map.

Acceptance criteria:
- Free model with budget exceeded → dispatched (not rejected)
- Paid model with budget exceeded → rejected with "budget_exceeded_paid"
- Model with no entry in model_costs → conservatively treated as paid (rejected)
- Mixed scenario: _match_agent_profile picks paid (rejected), but with
  OOMPAH_DEFAULT_FIRST_DISPATCH the same issue routes to free (dispatched)
- get_snapshot() budget block includes "free_tier_active" flag
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.models import AgentProfile, Issue, ModelProvider, RunningEntry
from oompah.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_free_provider(
    provider_id: str = "prov-free-01",
    model: str = "minimaxai/minimax-m2",
) -> ModelProvider:
    """Provider with a single $0-cost model."""
    return ModelProvider(
        id=provider_id,
        name="InferenceAPI-free",
        base_url="https://api.example.com/v1",
        api_key="test-key",
        models=[model],
        default_model=model,
        model_costs={
            model: {"cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0},
        },
    )


def _make_paid_provider(
    provider_id: str = "prov-paid-01",
    model: str = "claude-sonnet-4-5",
) -> ModelProvider:
    """Provider with a paid model."""
    return ModelProvider(
        id=provider_id,
        name="Anthropic",
        base_url="https://api.anthropic.com/v1",
        api_key="test-key",
        models=[model],
        default_model=model,
        model_costs={
            model: {"cost_per_1k_input": 3.0, "cost_per_1k_output": 15.0},
        },
    )


def _make_mixed_provider(
    provider_id: str = "prov-mixed-01",
    free_model: str = "minimaxai/minimax-m2",
    paid_model: str = "claude-sonnet-4-5",
) -> ModelProvider:
    """Provider with both a $0 model and a paid model (like InferenceAPI)."""
    return ModelProvider(
        id=provider_id,
        name="InferenceAPI",
        base_url="https://api.example.com/v1",
        api_key="test-key",
        models=[free_model, paid_model],
        default_model=free_model,  # default is the free one
        model_costs={
            free_model: {"cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0},
            paid_model: {"cost_per_1k_input": 3.0, "cost_per_1k_output": 15.0},
        },
    )


def _make_issue(
    identifier: str = "test-1",
    state: str = "open",
    issue_type: str = "task",
    priority: int = 2,
    labels: list | None = None,
    description: str = "Test issue description.",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description=description,
        state=state,
        issue_type=issue_type,
        priority=priority,
        labels=labels or [],
    )


def _make_orchestrator(
    tmp_path,
    provider: ModelProvider | None = None,
    profiles: list[AgentProfile] | None = None,
    budget_limit: float = 10.0,
    default_first_dispatch: bool = False,
) -> Orchestrator:
    """Create a minimal Orchestrator with mocked stores."""
    project_store = MagicMock()
    project_store.list_all.return_value = []

    cfg = ServiceConfig(
        budget_limit=budget_limit,
        default_first_dispatch=default_first_dispatch,
    )
    if profiles is not None:
        cfg.agent_profiles = profiles
    else:
        # Default single profile bound to the provided/default provider
        pid = provider.id if provider else None
        cfg.agent_profiles = [
            AgentProfile(
                name="default",
                command="cli",
                provider_id=pid,
            )
        ]

    orch = Orchestrator(
        config=cfg,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )

    # Inject a mock provider store
    if provider:
        mock_ps = MagicMock()
        mock_ps.get.side_effect = lambda pid: provider if pid == provider.id else None
        mock_ps.get_default.return_value = provider
        orch.provider_store = mock_ps
    else:
        mock_ps = MagicMock()
        mock_ps.get_default.return_value = None
        orch.provider_store = mock_ps

    return orch


def _exceed_budget(orch: Orchestrator) -> None:
    """Push spend over the budget limit to trigger the exceeded state."""
    orch.state.agent_totals.estimated_cost = orch.config.budget_limit + 1.0
    orch.state.budget_exceeded = True


# ---------------------------------------------------------------------------
# ModelProvider.is_model_explicitly_free — unit tests
# ---------------------------------------------------------------------------

class TestIsModelExplicitlyFree:
    """Tests for the ModelProvider.is_model_explicitly_free helper."""

    def test_explicit_zero_cost_returns_true(self):
        provider = _make_free_provider()
        assert provider.is_model_explicitly_free("minimaxai/minimax-m2") is True

    def test_paid_model_returns_false(self):
        provider = _make_paid_provider()
        assert provider.is_model_explicitly_free("claude-sonnet-4-5") is False

    def test_missing_from_model_costs_returns_false(self):
        """Conservative: missing entry → not free."""
        provider = ModelProvider(
            id="p", name="n", base_url="x", api_key="k",
            models=["m"], default_model="m",
            model_costs={},
        )
        assert provider.is_model_explicitly_free("m") is False

    def test_empty_string_model_returns_false(self):
        provider = _make_free_provider()
        assert provider.is_model_explicitly_free("") is False

    def test_input_nonzero_returns_false(self):
        provider = ModelProvider(
            id="p", name="n", base_url="x", api_key="k",
            models=["m"], default_model="m",
            model_costs={"m": {"cost_per_1k_input": 0.5, "cost_per_1k_output": 0.0}},
        )
        assert provider.is_model_explicitly_free("m") is False

    def test_output_nonzero_returns_false(self):
        provider = ModelProvider(
            id="p", name="n", base_url="x", api_key="k",
            models=["m"], default_model="m",
            model_costs={"m": {"cost_per_1k_input": 0.0, "cost_per_1k_output": 0.1}},
        )
        assert provider.is_model_explicitly_free("m") is False


# ---------------------------------------------------------------------------
# _would_dispatch_on_free_model
# ---------------------------------------------------------------------------

class TestWouldDispatchOnFreeModel:
    """Unit tests for the _would_dispatch_on_free_model helper."""

    def test_free_model_returns_truthy_model_name(self, tmp_path):
        """Returns the model name (truthy) for a $0 model."""
        provider = _make_free_provider()
        orch = _make_orchestrator(tmp_path, provider=provider)
        issue = _make_issue()
        result = orch._would_dispatch_on_free_model(issue)
        assert result  # truthy
        assert result == "minimaxai/minimax-m2"

    def test_paid_model_returns_falsy(self, tmp_path):
        """Returns falsy for a paid model."""
        provider = _make_paid_provider()
        orch = _make_orchestrator(tmp_path, provider=provider)
        issue = _make_issue()
        result = orch._would_dispatch_on_free_model(issue)
        assert not result

    def test_model_not_in_model_costs_returns_falsy(self, tmp_path):
        """Missing model_costs entry → conservatively treated as paid."""
        provider = ModelProvider(
            id="prov-01",
            name="NoCosted",
            base_url="https://x.example.com/v1",
            api_key="k",
            models=["some-model"],
            default_model="some-model",
            model_costs={},  # empty — no cost info
        )
        orch = _make_orchestrator(tmp_path, provider=provider)
        issue = _make_issue()
        result = orch._would_dispatch_on_free_model(issue)
        assert not result

    def test_partially_free_model_input_nonzero(self, tmp_path):
        """Model with only output cost = 0 (input = nonzero) → treated as paid."""
        provider = ModelProvider(
            id="prov-01",
            name="Weird",
            base_url="https://x.example.com/v1",
            api_key="k",
            models=["m"],
            default_model="m",
            model_costs={
                "m": {"cost_per_1k_input": 0.5, "cost_per_1k_output": 0.0},
            },
        )
        orch = _make_orchestrator(tmp_path, provider=provider)
        result = orch._would_dispatch_on_free_model(_make_issue())
        assert not result

    def test_partially_free_model_output_nonzero(self, tmp_path):
        """Model with input cost = 0 but output cost != 0 → treated as paid."""
        provider = ModelProvider(
            id="prov-01",
            name="Weird",
            base_url="https://x.example.com/v1",
            api_key="k",
            models=["m"],
            default_model="m",
            model_costs={
                "m": {"cost_per_1k_input": 0.0, "cost_per_1k_output": 0.1},
            },
        )
        orch = _make_orchestrator(tmp_path, provider=provider)
        result = orch._would_dispatch_on_free_model(_make_issue())
        assert not result

    def test_no_provider_returns_falsy(self, tmp_path):
        """No provider configured → cannot determine cost → falsy."""
        orch = _make_orchestrator(tmp_path, provider=None)
        result = orch._would_dispatch_on_free_model(_make_issue())
        assert not result

    def test_no_profiles_returns_falsy(self, tmp_path):
        """No agent profiles configured → falsy."""
        orch = _make_orchestrator(tmp_path, provider=_make_free_provider(), profiles=[])
        result = orch._would_dispatch_on_free_model(_make_issue())
        assert not result

    def test_mixed_provider_default_is_free(self, tmp_path):
        """Provider with both free and paid models; default is free → returns free model."""
        provider = _make_mixed_provider()
        orch = _make_orchestrator(tmp_path, provider=provider)
        result = orch._would_dispatch_on_free_model(_make_issue())
        # default_model is the free one
        assert result == "minimaxai/minimax-m2"

    def test_mixed_provider_profile_selects_paid(self, tmp_path):
        """Profile explicitly selects the paid model → falsy (paid)."""
        provider = _make_mixed_provider()
        profiles = [
            AgentProfile(
                name="default",
                command="cli",
                provider_id=provider.id,
                model="claude-sonnet-4-5",  # explicitly the paid model
            )
        ]
        orch = _make_orchestrator(tmp_path, provider=provider, profiles=profiles)
        result = orch._would_dispatch_on_free_model(_make_issue())
        assert not result

    def test_mixed_provider_profile_selects_free(self, tmp_path):
        """Profile explicitly selects the free model → returns free model."""
        provider = _make_mixed_provider()
        profiles = [
            AgentProfile(
                name="default",
                command="cli",
                provider_id=provider.id,
                model="minimaxai/minimax-m2",  # explicitly the free model
            )
        ]
        orch = _make_orchestrator(tmp_path, provider=provider, profiles=profiles)
        result = orch._would_dispatch_on_free_model(_make_issue())
        assert result == "minimaxai/minimax-m2"


# ---------------------------------------------------------------------------
# _should_dispatch — budget exceeded with free model
# ---------------------------------------------------------------------------

class TestShouldDispatchBudgetFreeTier:
    """_should_dispatch must allow dispatch on free models when budget exceeded."""

    def test_free_model_dispatched_when_budget_exceeded(self, tmp_path):
        """Core case: budget exceeded but model is $0 → dispatch allowed."""
        provider = _make_free_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()
        assert orch._should_dispatch(issue) is True

    def test_paid_model_rejected_when_budget_exceeded(self, tmp_path):
        """Paid model → rejected when budget exceeded."""
        provider = _make_paid_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()
        assert orch._should_dispatch(issue) is False

    def test_paid_reject_reason_is_budget_exceeded_paid(self, tmp_path):
        """Reject reason for paid models is 'budget_exceeded_paid'."""
        provider = _make_paid_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()
        orch._should_dispatch(issue)
        # The reject streak should record the new reason
        reason, count = orch.state.reject_streak.get(issue.id, ("", 0))
        assert reason == "budget_exceeded_paid"

    def test_unknown_cost_model_rejected_conservatively(self, tmp_path):
        """Model not in model_costs → conservatively rejected as paid."""
        provider = ModelProvider(
            id="prov-01",
            name="NoCosted",
            base_url="https://x.example.com/v1",
            api_key="k",
            models=["unknown-model"],
            default_model="unknown-model",
            model_costs={},
        )
        profiles = [AgentProfile(name="default", command="cli", provider_id="prov-01")]
        orch = _make_orchestrator(tmp_path, provider=provider, profiles=profiles, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()
        assert orch._should_dispatch(issue) is False
        reason, _ = orch.state.reject_streak.get(issue.id, ("", 0))
        assert reason == "budget_exceeded_paid"

    def test_budget_not_exceeded_still_allowed(self, tmp_path):
        """Normal case: budget not exceeded → dispatch allowed (paid or free)."""
        provider = _make_paid_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=100.0)
        # Don't exceed budget
        orch.state.agent_totals.estimated_cost = 5.0
        issue = _make_issue()
        assert orch._should_dispatch(issue) is True

    def test_no_budget_limit_always_allowed(self, tmp_path):
        """budget_limit=0 means no limit → dispatch always allowed."""
        provider = _make_paid_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=0.0)
        # Pretend lots of cost
        orch.state.agent_totals.estimated_cost = 9999.0
        issue = _make_issue()
        assert orch._should_dispatch(issue) is True

    def test_free_model_dispatch_increments_counter(self, tmp_path):
        """Dispatching a free model increments free_tier_dispatches_this_window."""
        provider = _make_free_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()
        assert orch.state.free_tier_dispatches_this_window == 0
        orch._should_dispatch(issue)
        assert orch.state.free_tier_dispatches_this_window == 1

    def test_paid_model_dispatch_does_not_increment_counter(self, tmp_path):
        """Rejecting a paid model does not increment the counter."""
        provider = _make_paid_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()
        orch._should_dispatch(issue)
        assert orch.state.free_tier_dispatches_this_window == 0

    def test_free_model_dispatch_does_not_reset_budget_exceeded(self, tmp_path):
        """Budget exceeded state stays True even when free model is dispatched.
        It only clears when actual spend drops under the limit (via _check_budget)."""
        provider = _make_free_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()
        orch._should_dispatch(issue)  # allowed
        # budget_exceeded should still be True
        assert orch.state.budget_exceeded is True


# ---------------------------------------------------------------------------
# Mixed scenario: default_first_dispatch + budget exceeded
# ---------------------------------------------------------------------------

class TestDefaultFirstDispatchWithBudgetExceeded:
    """When default_first_dispatch=True and budget exceeded:
    - The issue's first dispatch routes to the default (free) profile → allowed
    - Without the flag, natural profile selection might pick a paid profile → rejected
    """

    def _make_two_profile_orch(
        self,
        tmp_path,
        default_first_dispatch: bool,
        budget_limit: float = 10.0,
    ) -> Orchestrator:
        """Orchestrator with default (free) and standard (paid) profiles."""
        free_model = "minimaxai/minimax-m2"
        paid_model = "claude-sonnet-4-5"

        # Mixed provider: default_model is free
        provider = _make_mixed_provider(free_model=free_model, paid_model=paid_model)

        profiles = [
            AgentProfile(
                name="default",
                command="cli",
                provider_id=provider.id,
                model=free_model,  # default uses free model
            ),
            AgentProfile(
                name="standard",
                command="cli",
                provider_id=provider.id,
                model=paid_model,  # standard uses paid model
                issue_types=["task", "feature"],
            ),
        ]

        orch = _make_orchestrator(
            tmp_path,
            provider=provider,
            profiles=profiles,
            budget_limit=budget_limit,
            default_first_dispatch=default_first_dispatch,
        )
        _exceed_budget(orch)
        return orch

    def test_with_default_first_dispatch_free_issue_allowed(self, tmp_path):
        """default_first_dispatch=True: first dispatch uses free model → allowed when budget exceeded."""
        orch = self._make_two_profile_orch(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="task")
        # With flag, first dispatch routes to "default" (free model)
        assert orch._should_dispatch(issue) is True

    def test_without_default_first_dispatch_paid_issue_rejected(self, tmp_path):
        """default_first_dispatch=False: task matches 'standard' (paid) → rejected when budget exceeded."""
        orch = self._make_two_profile_orch(tmp_path, default_first_dispatch=False)
        issue = _make_issue(issue_type="task")
        # Without flag, task matches "standard" (paid model) → rejected
        assert orch._should_dispatch(issue) is False
        reason, _ = orch.state.reject_streak.get(issue.id, ("", 0))
        assert reason == "budget_exceeded_paid"

    def test_default_first_dispatch_retry_is_natural_profile(self, tmp_path):
        """On retry (issue already in retry_attempts), _would_dispatch_on_free_model
        resolves the natural profile (not the default catch-all) for a task → paid → falsy."""
        orch = self._make_two_profile_orch(tmp_path, default_first_dispatch=True)
        issue = _make_issue(issue_type="task")
        # Simulate that this is already in a retry state (not is_first)
        from oompah.models import RetryEntry
        orch.state.retry_attempts[issue.id] = RetryEntry(
            issue_id=issue.id,
            identifier=issue.identifier,
            attempt=1,
            due_at_ms=0.0,
        )
        # On retry, won't use the default profile → resolves to "standard" (paid)
        result = orch._would_dispatch_on_free_model(issue)
        # task → "standard" profile → paid model → falsy
        assert not result


# ---------------------------------------------------------------------------
# get_snapshot() — free_tier_active flag
# ---------------------------------------------------------------------------

class TestGetSnapshotFreeTierActive:
    """budget block must include free_tier_active flag."""

    def test_free_tier_active_false_when_not_exceeded(self, tmp_path):
        orch = _make_orchestrator(tmp_path, provider=_make_free_provider(), budget_limit=10.0)
        snapshot = orch.get_snapshot()
        assert snapshot["budget"]["free_tier_active"] is False

    def test_free_tier_active_false_when_exceeded_but_no_dispatches(self, tmp_path):
        """Exceeded + no free-tier dispatches yet = free_tier_active is False."""
        orch = _make_orchestrator(tmp_path, provider=_make_free_provider(), budget_limit=10.0)
        _exceed_budget(orch)
        # No free-tier dispatches recorded
        assert orch.state.free_tier_dispatches_this_window == 0
        snapshot = orch.get_snapshot()
        assert snapshot["budget"]["free_tier_active"] is False

    def test_free_tier_active_true_when_exceeded_and_dispatches_happened(self, tmp_path):
        """Exceeded + free-tier dispatch counter > 0 = free_tier_active is True."""
        orch = _make_orchestrator(tmp_path, provider=_make_free_provider(), budget_limit=10.0)
        _exceed_budget(orch)
        orch.state.free_tier_dispatches_this_window = 3  # simulated dispatches
        snapshot = orch.get_snapshot()
        assert snapshot["budget"]["free_tier_active"] is True

    def test_free_tier_active_false_when_budget_limit_is_zero(self, tmp_path):
        """With budget_limit=0 (unlimited), budget_exceeded is never True → False."""
        orch = _make_orchestrator(tmp_path, provider=_make_free_provider(), budget_limit=0.0)
        # budget_exceeded never gets set to True when budget_limit=0
        assert orch.state.budget_exceeded is False
        snapshot = orch.get_snapshot()
        assert snapshot["budget"]["free_tier_active"] is False

    def test_budget_block_has_free_tier_active_key(self, tmp_path):
        """budget block always has the free_tier_active key."""
        orch = _make_orchestrator(tmp_path, provider=_make_free_provider(), budget_limit=10.0)
        snapshot = orch.get_snapshot()
        assert "free_tier_active" in snapshot["budget"]

    def test_budget_block_has_free_tier_dispatches_count(self, tmp_path):
        """budget block also exposes free_tier_dispatches_this_window count."""
        orch = _make_orchestrator(tmp_path, provider=_make_free_provider(), budget_limit=10.0)
        orch.state.free_tier_dispatches_this_window = 5
        snapshot = orch.get_snapshot()
        assert "free_tier_dispatches_this_window" in snapshot["budget"]
        assert snapshot["budget"]["free_tier_dispatches_this_window"] == 5

    def test_should_dispatch_increments_and_snapshot_reflects_it(self, tmp_path):
        """End-to-end: _should_dispatch increments counter, snapshot reflects free_tier_active."""
        provider = _make_free_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()
        # Before dispatch
        assert orch.get_snapshot()["budget"]["free_tier_active"] is False
        # Dispatch on free model
        orch._should_dispatch(issue)
        # After dispatch
        assert orch.get_snapshot()["budget"]["free_tier_active"] is True


# ---------------------------------------------------------------------------
# Logging: ensure the "dispatching on free-tier model" log line fires
# ---------------------------------------------------------------------------

class TestFreeTierDispatchLogging:
    """The log line must fire when dispatching a free model with budget exceeded."""

    def test_free_tier_log_emitted(self, tmp_path, caplog):
        """A clear log message fires when free-tier bypass triggers."""
        import logging
        provider = _make_free_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()

        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            result = orch._should_dispatch(issue)

        assert result is True
        # Check that the key info message was logged
        free_tier_messages = [
            r.message for r in caplog.records
            if "free-tier model" in r.message
        ]
        assert free_tier_messages, "Expected a 'free-tier model' log message"
        msg = free_tier_messages[0]
        # Must include issue identifier and model name
        assert issue.identifier in msg
        assert "minimaxai/minimax-m2" in msg
        # Must mention the budget context
        assert "Budget exceeded" in msg or "budget exceeded" in msg.lower()

    def test_free_tier_log_includes_spend_vs_limit(self, tmp_path, caplog):
        """Log message must include the dollar amounts (spend vs limit)."""
        import logging
        provider = _make_free_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()

        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            orch._should_dispatch(issue)

        free_tier_messages = [
            r.message for r in caplog.records
            if "free-tier model" in r.message
        ]
        assert free_tier_messages
        msg = free_tier_messages[0]
        # Should contain dollar amounts
        assert "$" in msg

    def test_no_free_tier_log_for_paid_model(self, tmp_path, caplog):
        """No free-tier log when model is paid."""
        import logging
        provider = _make_paid_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=10.0)
        _exceed_budget(orch)
        issue = _make_issue()

        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            result = orch._should_dispatch(issue)

        assert result is False
        free_tier_messages = [
            r.message for r in caplog.records
            if "free-tier model" in r.message
        ]
        assert not free_tier_messages, "Should not log free-tier message for paid model"

    def test_no_free_tier_log_when_budget_not_exceeded(self, tmp_path, caplog):
        """No free-tier log when budget is within limit."""
        import logging
        provider = _make_free_provider()
        orch = _make_orchestrator(tmp_path, provider=provider, budget_limit=100.0)
        orch.state.agent_totals.estimated_cost = 5.0  # under limit
        issue = _make_issue()

        with caplog.at_level(logging.INFO, logger="oompah.orchestrator"):
            orch._should_dispatch(issue)

        free_tier_messages = [
            r.message for r in caplog.records
            if "free-tier model" in r.message
        ]
        assert not free_tier_messages
