"""Tests for TASK-407.6 — candidate preflight availability check.

Covers:
  - _candidate_preflight() unit tests for every skip condition
  - _run_worker() integration: preflight-skipped candidates trigger failover
  - All-candidates-unavailable error format lists each reason
  - Preflight log lines do not expose api_key or other secrets

Acceptance criteria verified:
  AC1  Paid candidate blocked by budget exhaustion is skipped, next candidate tried.
  AC2  Free model candidate is NOT skipped when paid budget window is exhausted.
  AC3  ACP subscription candidate is NOT skipped when paid budget is exhausted.
  AC4  Active provider cooldown causes the candidate to be skipped.
  AC5  All-unavailable error includes each provider/model and normalized reason.
  AC6  Skip decisions are logged without leaking API keys or secrets.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import fields
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.focus import Focus
from oompah.models import AgentProfile, Issue, ModelProvider, RunningEntry
from oompah.orchestrator import DispatchTarget, Orchestrator, ProviderStartupError
from oompah.roles import Candidate, RoleStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    identifier: str = "test-1",
    state: str = "open",
    issue_type: str = "task",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Test issue — enough text to pass the empty-description gate.",
        state=state,
        issue_type=issue_type,
        priority=2,
        labels=[],
    )


def _make_orchestrator(tmp_path) -> Orchestrator:
    """Minimal orchestrator with a fresh RoleStore and mocked project store."""
    project_store = MagicMock()
    project_store.list_all.return_value = []
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    orch._fetch_in_progress_issues = MagicMock(return_value=[])
    return orch


def _api_provider(
    *,
    pid: str = "p1",
    name: str = "TestProv",
    api_key: str = "sk-test",
    models: list[str] | None = None,
    default_model: str = "m1",
    model_costs: dict | None = None,
    billing_model: str = "subscription",
) -> ModelProvider:
    """Create a non-ACP (API-mode) ModelProvider for tests."""
    return ModelProvider(
        id=pid,
        name=name,
        base_url="http://test.example.com/v1",
        api_key=api_key,
        models=models if models is not None else [default_model],
        default_model=default_model,
        model_costs=model_costs or {},
        billing_model=billing_model,
    )


def _acp_provider(
    *,
    pid: str = "acp-p1",
    name: str = "ACPProv",
    billing_model: str = "subscription",
) -> ModelProvider:
    """Create an ACP ModelProvider for tests."""
    return ModelProvider(
        id=pid,
        name=name,
        base_url="",
        api_key="",
        models=[],
        default_model="",
        mode="acp",
        billing_model=billing_model,
    )


def _make_target(
    *,
    provider: ModelProvider,
    model: str | None = None,
    role_name: str = "fast",
    index: int = 0,
    candidate: Candidate | None = None,
) -> DispatchTarget:
    """Build a DispatchTarget from a provider."""
    m = model or (provider.models[0] if provider.models else None)
    cand = candidate or (Candidate(provider_id=provider.id, model=m or "") if m else None)
    return DispatchTarget(
        role_name=role_name,
        provider=provider,
        model=m,
        candidate_key=f"{provider.id}/{m}" if m else provider.id,
        source=f"role:{role_name}[{index}]",
        candidate=cand,
    )


def _make_orch_with_running(tmp_path, issue: Issue) -> Orchestrator:
    """Orchestrator with the issue already registered in state.running."""
    orch = _make_orchestrator(tmp_path)
    orch._on_worker_exit = AsyncMock()
    orch.state.running[issue.id] = RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="standard",
        natural_profile_name="standard",
    )
    return orch


def _exceed_budget(orch: Orchestrator) -> None:
    """Push spend over the configured budget limit."""
    orch.state.agent_totals.estimated_cost = orch.config.budget_limit + 1.0
    orch.state.budget_exceeded = True


# ---------------------------------------------------------------------------
# Unit tests: _candidate_preflight
# ---------------------------------------------------------------------------


class TestCandidatePreflight:
    """Unit tests for Orchestrator._candidate_preflight.

    Each test directly inspects the return value of the method.  No workers
    are started and no network calls are made.
    """

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_usable_candidate_returns_empty_string(self, tmp_path):
        """A fully-configured, valid candidate returns '' (usable)."""
        prov = _api_provider()
        target = _make_target(provider=prov, model="m1")
        orch = _make_orchestrator(tmp_path)

        result = orch._candidate_preflight(target)

        assert result == "", f"Expected '', got {result!r}"

    def test_usable_candidate_with_budget_under_limit(self, tmp_path):
        """When budget is under limit, a paid model returns '' (usable)."""
        prov = _api_provider(
            model_costs={"m1": {"cost_per_1k_input": 3.0, "cost_per_1k_output": 15.0}},
        )
        orch = _make_orchestrator(tmp_path)
        orch.config.budget_limit = 100.0
        orch.state.agent_totals.estimated_cost = 1.0  # well under limit
        target = _make_target(provider=prov, model="m1")

        assert orch._candidate_preflight(target) == ""

    # ------------------------------------------------------------------
    # AC: missing credentials
    # ------------------------------------------------------------------

    def test_subscription_api_provider_without_api_key_is_usable(self, tmp_path):
        """Subscription/no-auth API providers may be usable without api_key."""
        prov = _api_provider(api_key="", billing_model="subscription")
        target = _make_target(provider=prov, model="m1")
        orch = _make_orchestrator(tmp_path)

        result = orch._candidate_preflight(target)

        assert result == ""

    def test_missing_api_key_returns_missing_credentials(self, tmp_path):
        """Per-token API provider with empty api_key returns 'missing_credentials'."""
        prov = _api_provider(api_key="", billing_model="per_token")  # no key
        target = _make_target(provider=prov, model="m1")
        orch = _make_orchestrator(tmp_path)

        result = orch._candidate_preflight(target)

        assert result == "missing_credentials"

    def test_none_api_key_returns_missing_credentials(self, tmp_path):
        """Per-token API provider with api_key=None returns 'missing_credentials'."""
        prov = _api_provider(api_key="", billing_model="per_token")
        prov.api_key = None  # type: ignore[assignment]
        target = _make_target(provider=prov, model="m1")
        orch = _make_orchestrator(tmp_path)

        result = orch._candidate_preflight(target)

        assert result == "missing_credentials"

    def test_acp_provider_without_api_key_is_usable(self, tmp_path):
        """ACP providers do not need an api_key — should NOT return missing_credentials."""
        prov = _acp_provider()  # api_key="" by default
        target = _make_target(provider=prov, model=None)
        orch = _make_orchestrator(tmp_path)

        result = orch._candidate_preflight(target)

        assert result != "missing_credentials", (
            "ACP providers must not be rejected for missing api_key"
        )

    # ------------------------------------------------------------------
    # AC4: rate-limit cooldown
    # ------------------------------------------------------------------

    def test_rate_limited_candidate_returns_rate_limited(self, tmp_path):
        """Active global rate-limit cooldown causes 'rate_limited' skip."""
        prov = _api_provider()
        target = _make_target(provider=prov, model="m1")
        orch = _make_orchestrator(tmp_path)
        orch._rate_limit_until = time.time() + 120  # active cooldown

        result = orch._candidate_preflight(target)

        assert result == "rate_limited"

    def test_expired_rate_limit_returns_empty(self, tmp_path):
        """Expired rate-limit cooldown does not block the candidate."""
        prov = _api_provider()
        target = _make_target(provider=prov, model="m1")
        orch = _make_orchestrator(tmp_path)
        orch._rate_limit_until = time.time() - 1  # already expired

        result = orch._candidate_preflight(target)

        assert result == ""

    # ------------------------------------------------------------------
    # AC1: budget exhaustion — paid candidate skipped
    # ------------------------------------------------------------------

    def test_budget_exceeded_paid_candidate_returns_budget_exceeded(self, tmp_path):
        """Paid model candidate returns 'budget_exceeded' when budget is exhausted."""
        prov = _api_provider(
            model_costs={"m1": {"cost_per_1k_input": 3.0, "cost_per_1k_output": 15.0}},
        )
        orch = _make_orchestrator(tmp_path)
        orch.config.budget_limit = 10.0
        _exceed_budget(orch)
        target = _make_target(provider=prov, model="m1")

        result = orch._candidate_preflight(target)

        assert result == "budget_exceeded"

    def test_budget_exceeded_model_not_in_costs_returns_budget_exceeded(self, tmp_path):
        """Conservative: unknown-cost model is treated as paid when budget exceeded."""
        prov = _api_provider(model_costs={})  # no cost info → paid
        orch = _make_orchestrator(tmp_path)
        orch.config.budget_limit = 10.0
        _exceed_budget(orch)
        target = _make_target(provider=prov, model="m1")

        result = orch._candidate_preflight(target)

        assert result == "budget_exceeded"

    # ------------------------------------------------------------------
    # AC2: free model not blocked by budget exhaustion
    # ------------------------------------------------------------------

    def test_budget_exceeded_free_model_returns_empty(self, tmp_path):
        """Explicitly $0 model returns '' even when budget is exhausted (AC2)."""
        prov = _api_provider(
            model_costs={"m1": {"cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0}},
        )
        orch = _make_orchestrator(tmp_path)
        orch.config.budget_limit = 10.0
        _exceed_budget(orch)
        target = _make_target(provider=prov, model="m1")

        result = orch._candidate_preflight(target)

        assert result == "", (
            "Free-tier model must not be blocked by budget exhaustion"
        )

    # ------------------------------------------------------------------
    # AC3: ACP subscription not blocked by budget exhaustion
    # ------------------------------------------------------------------

    def test_budget_exceeded_acp_subscription_returns_empty(self, tmp_path):
        """ACP subscription-billed provider returns '' even when budget exceeded (AC3)."""
        prov = _acp_provider(billing_model="subscription")
        orch = _make_orchestrator(tmp_path)
        orch.config.budget_limit = 10.0
        _exceed_budget(orch)
        target = _make_target(provider=prov, model=None)

        result = orch._candidate_preflight(target)

        assert result == "", (
            "ACP subscription provider must not be blocked by budget exhaustion"
        )

    def test_budget_exceeded_acp_per_token_returns_budget_exceeded(self, tmp_path):
        """ACP per-token-billed provider IS blocked by budget exhaustion."""
        prov = _acp_provider(billing_model="per_token")
        orch = _make_orchestrator(tmp_path)
        orch.config.budget_limit = 10.0
        _exceed_budget(orch)
        target = _make_target(provider=prov, model=None)

        result = orch._candidate_preflight(target)

        assert result == "budget_exceeded", (
            "ACP per-token provider must be blocked when budget exceeded"
        )

    # ------------------------------------------------------------------
    # Invalid model
    # ------------------------------------------------------------------

    def test_invalid_model_not_in_catalog_returns_invalid_model(self, tmp_path):
        """Model not in provider.models catalog returns 'invalid_model'."""
        prov = _api_provider(models=["m-valid"], default_model="m-valid")
        target = _make_target(provider=prov, model="m-nonexistent")
        orch = _make_orchestrator(tmp_path)

        result = orch._candidate_preflight(target)

        assert result == "invalid_model"

    def test_valid_model_in_catalog_returns_empty(self, tmp_path):
        """Model that IS in provider.models catalog returns ''."""
        prov = _api_provider(models=["m-valid", "m-fast"], default_model="m-valid")
        target = _make_target(provider=prov, model="m-fast")
        orch = _make_orchestrator(tmp_path)

        assert orch._candidate_preflight(target) == ""

    def test_default_model_not_in_models_list_passes(self, tmp_path):
        """Model equal to provider.default_model passes even if not in models list."""
        prov = _api_provider(models=["m-a"], default_model="m-default-only")
        prov.models = ["m-a"]  # default_model is not in this list
        target = _make_target(provider=prov, model="m-default-only")
        orch = _make_orchestrator(tmp_path)

        result = orch._candidate_preflight(target)

        assert result == "", (
            "provider.default_model must be accepted even when absent from models list"
        )

    def test_no_model_set_skips_model_check(self, tmp_path):
        """When target.model is None/empty, the model check is skipped."""
        prov = _api_provider(models=["m-valid"], default_model="m-valid")
        target = _make_target(provider=prov, model=None)
        # Override model to None explicitly
        object.__setattr__(target, "model", None)
        orch = _make_orchestrator(tmp_path)

        result = orch._candidate_preflight(target)

        assert result == ""

    def test_provider_empty_models_list_skips_model_check(self, tmp_path):
        """Provider with empty models list (ACP/SDK-managed) passes model check."""
        prov = _acp_provider()  # models=[] by default
        target = _make_target(provider=prov, model=None)
        orch = _make_orchestrator(tmp_path)

        result = orch._candidate_preflight(target)

        # ACP with no models is SDK-managed — not rejected for invalid_model
        assert result != "invalid_model"

    # ------------------------------------------------------------------
    # Check ordering: credentials checked before budget
    # ------------------------------------------------------------------

    def test_missing_credentials_skipped_before_budget_check(self, tmp_path):
        """Missing credentials is returned even when budget is also exceeded."""
        prov = _api_provider(api_key="", billing_model="per_token")  # no key
        orch = _make_orchestrator(tmp_path)
        orch.config.budget_limit = 10.0
        _exceed_budget(orch)
        target = _make_target(provider=prov, model="m1")

        result = orch._candidate_preflight(target)

        # Should be missing_credentials, not budget_exceeded
        assert result == "missing_credentials"


# ---------------------------------------------------------------------------
# AC6: preflight log lines must not expose API keys
# ---------------------------------------------------------------------------


class TestPreflightLogSafety:
    """Skip log lines must not contain api_key values or any secret strings."""

    def _run_preflight_and_collect_logs(
        self,
        tmp_path,
        provider: ModelProvider,
        model: str | None = None,
        caplog=None,
        exceed_budget: bool = False,
    ) -> list[logging.LogRecord]:
        target = _make_target(provider=provider, model=model or (provider.models[0] if provider.models else None))
        orch = _make_orchestrator(tmp_path)
        if exceed_budget:
            orch.config.budget_limit = 10.0
            _exceed_budget(orch)
        import logging as _logging
        with caplog.at_level(_logging.WARNING, logger="oompah.orchestrator"):
            orch._candidate_preflight(target)
        return caplog.records

    def test_missing_credentials_log_no_api_key(self, tmp_path, caplog):
        """missing_credentials log line must NOT contain the api_key value."""
        secret_key = "sk-super-secret-key-12345"  # pragma: allowlist secret
        prov = _api_provider(api_key=secret_key, billing_model="per_token")
        prov.api_key = ""  # clear it to trigger missing_credentials
        self._run_preflight_and_collect_logs(tmp_path, prov, caplog=caplog)
        for record in caplog.records:
            assert secret_key not in record.message, (
                f"API key leaked in log: {record.message!r}"
            )

    def test_budget_exceeded_log_no_api_key(self, tmp_path, caplog):
        """budget_exceeded log line must NOT contain the api_key value."""
        secret_key = "sk-budget-test-key-99999"  # pragma: allowlist secret
        prov = _api_provider(api_key=secret_key)
        self._run_preflight_and_collect_logs(
            tmp_path, prov, caplog=caplog, exceed_budget=True
        )
        for record in caplog.records:
            assert secret_key not in record.message, (
                f"API key leaked in log: {record.message!r}"
            )

    def test_rate_limited_log_no_api_key(self, tmp_path, caplog):
        """rate_limited log line must NOT contain the api_key value."""
        secret_key = "sk-rate-limit-key-77777"  # pragma: allowlist secret
        prov = _api_provider(api_key=secret_key)
        target = _make_target(provider=prov, model="m1")
        orch = _make_orchestrator(tmp_path)
        orch._rate_limit_until = time.time() + 120
        import logging as _logging
        with caplog.at_level(_logging.WARNING, logger="oompah.orchestrator"):
            orch._candidate_preflight(target)
        for record in caplog.records:
            assert secret_key not in record.message, (
                f"API key leaked in log: {record.message!r}"
            )

    def test_invalid_model_log_no_api_key(self, tmp_path, caplog):
        """invalid_model log line must NOT contain the api_key value."""
        secret_key = "sk-model-test-key-55555"  # pragma: allowlist secret
        prov = _api_provider(
            api_key=secret_key,
            models=["m-only-valid"],
            default_model="m-only-valid",
        )
        target = _make_target(provider=prov, model="m-does-not-exist")
        orch = _make_orchestrator(tmp_path)
        import logging as _logging
        with caplog.at_level(_logging.WARNING, logger="oompah.orchestrator"):
            orch._candidate_preflight(target)
        for record in caplog.records:
            assert secret_key not in record.message, (
                f"API key leaked in log: {record.message!r}"
            )

    def test_preflight_skip_log_contains_candidate_key(self, tmp_path, caplog):
        """Preflight log must include the candidate_key for traceability."""
        prov = _api_provider(api_key="", billing_model="per_token")
        target = _make_target(provider=prov, model="m1")
        orch = _make_orchestrator(tmp_path)
        import logging as _logging
        with caplog.at_level(_logging.WARNING, logger="oompah.orchestrator"):
            orch._candidate_preflight(target)
        skip_logs = [r for r in caplog.records if "Preflight" in r.message]
        assert skip_logs, "Expected at least one Preflight log message"
        assert any(target.candidate_key in r.message for r in skip_logs), (
            "Preflight log must include candidate_key"
        )


# ---------------------------------------------------------------------------
# Integration tests: _run_worker with preflight
# ---------------------------------------------------------------------------


def _profile(name: str = "standard", **kw) -> AgentProfile:
    defaults = dict(name=name, command="cli")
    defaults.update(kw)
    return AgentProfile(**defaults)


class TestRunWorkerPreflightIntegration:
    """_run_worker skips preflight-failed candidates and falls through to the next."""

    # ------------------------------------------------------------------
    # AC1: budget-exhausted paid → skip; next (free) candidate tried
    # ------------------------------------------------------------------

    def test_paid_candidate_budget_skipped_fallback_to_free(self, tmp_path):
        """AC1+AC2: paid candidate skipped by budget exhaustion; free model tried next."""
        issue = _make_issue("feat-budget-1")
        orch = _make_orch_with_running(tmp_path, issue)
        orch.config.budget_limit = 10.0
        _exceed_budget(orch)

        paid_prov = _api_provider(
            pid="paid-p",
            api_key="sk-paid",
            models=["m-paid"],
            default_model="m-paid",
            model_costs={"m-paid": {"cost_per_1k_input": 3.0, "cost_per_1k_output": 15.0}},
        )
        free_prov = _api_provider(
            pid="free-p",
            api_key="sk-free",
            models=["m-free"],
            default_model="m-free",
            model_costs={"m-free": {"cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0}},
        )

        target_paid = _make_target(provider=paid_prov, model="m-paid", index=0)
        target_free = _make_target(provider=free_prov, model="m-free", index=1)
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_paid, target_free])

        calls = []
        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        assert "paid-p" not in calls, "Paid candidate must be preflight-skipped"
        assert "free-p" in calls, "Free candidate must be tried after paid is skipped"
        orch._on_worker_exit.assert_not_called()  # free candidate succeeded

    # ------------------------------------------------------------------
    # AC3: budget-exhausted but ACP subscription passes
    # ------------------------------------------------------------------

    def test_paid_candidate_skipped_fallback_to_acp_subscription(self, tmp_path):
        """AC3: paid API candidate skipped; ACP subscription candidate tried next."""
        issue = _make_issue("feat-acp-1")
        orch = _make_orch_with_running(tmp_path, issue)
        orch.config.budget_limit = 10.0
        _exceed_budget(orch)

        paid_prov = _api_provider(
            pid="paid-p",
            api_key="sk-paid",
            models=["m-paid"],
            default_model="m-paid",
            model_costs={"m-paid": {"cost_per_1k_input": 3.0, "cost_per_1k_output": 15.0}},
        )
        acp_prov = _acp_provider(pid="acp-p", billing_model="subscription")

        target_paid = _make_target(provider=paid_prov, model="m-paid", index=0)
        target_acp = _make_target(provider=acp_prov, model=None, index=1)
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_paid, target_acp])

        acp_calls = []
        async def mock_acp_worker(issue, attempt, profile, target=None):
            acp_calls.append("acp")
        orch._run_acp_worker = mock_acp_worker

        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            raise AssertionError("Paid candidate must be preflight-skipped, not tried")
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        assert acp_calls == ["acp"], "ACP subscription candidate must be tried"
        orch._on_worker_exit.assert_not_called()

    # ------------------------------------------------------------------
    # AC4: rate-limit cooldown skips candidate
    # ------------------------------------------------------------------

    def test_rate_limited_candidate_skipped_fallback_to_next(self, tmp_path):
        """AC4: rate-limited candidate is preflight-skipped; next candidate tried."""
        issue = _make_issue("feat-rate-1")
        orch = _make_orch_with_running(tmp_path, issue)
        orch._rate_limit_until = time.time() + 120  # active cooldown

        prov_a = _api_provider(pid="a", models=["m-a"], default_model="m-a")
        # Note: with a global rate limit, ALL candidates are rate-limited.
        # Clear it after first check to simulate the second candidate being ok.
        prov_b = _api_provider(pid="b", models=["m-b"], default_model="m-b")

        target_a = _make_target(provider=prov_a, model="m-a", index=0)
        target_b = _make_target(provider=prov_b, model="m-b", index=1)
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_a, target_b])

        # Patch _is_rate_limited to return True only for the first call, then False
        call_count = [0]
        original_is_rate_limited = orch._is_rate_limited
        def _rate_limited_once():
            call_count[0] += 1
            return call_count[0] == 1  # True for first candidate, False for second
        orch._is_rate_limited = _rate_limited_once

        calls = []
        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        assert "a" not in calls, "Rate-limited candidate must be skipped"
        assert "b" in calls, "Second candidate must be tried"
        orch._on_worker_exit.assert_not_called()

    # ------------------------------------------------------------------
    # Missing credentials skipped
    # ------------------------------------------------------------------

    def test_missing_credentials_candidate_skipped_fallback(self, tmp_path):
        """Candidate with missing api_key is preflight-skipped; next tried."""
        issue = _make_issue("feat-cred-1")
        orch = _make_orch_with_running(tmp_path, issue)

        prov_bad = _api_provider(
            pid="bad-cred",
            api_key="",
            billing_model="per_token",
        )  # no key
        prov_ok = _api_provider(pid="ok-cred", api_key="sk-ok")

        target_bad = _make_target(provider=prov_bad, model="m1", index=0)
        target_ok = _make_target(provider=prov_ok, model="m1", index=1)
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_bad, target_ok])

        calls = []
        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        assert "bad-cred" not in calls, "No-credentials candidate must be skipped"
        assert "ok-cred" in calls, "Valid candidate must be tried"
        orch._on_worker_exit.assert_not_called()

    # ------------------------------------------------------------------
    # Invalid model preflight-skipped
    # ------------------------------------------------------------------

    def test_invalid_model_candidate_skipped_fallback(self, tmp_path):
        """Candidate with model not in catalog is preflight-skipped; next tried."""
        issue = _make_issue("feat-model-1")
        orch = _make_orch_with_running(tmp_path, issue)

        prov_bad = _api_provider(pid="p-badmodel", models=["m-valid"], default_model="m-valid")
        prov_ok = _api_provider(pid="p-okmodel", models=["m-ok"], default_model="m-ok")

        # target_bad has a model not in prov_bad.models
        target_bad = _make_target(provider=prov_bad, model="m-nonexistent", index=0)
        target_ok = _make_target(provider=prov_ok, model="m-ok", index=1)
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_bad, target_ok])

        calls = []
        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        assert "p-badmodel" not in calls
        assert "p-okmodel" in calls
        orch._on_worker_exit.assert_not_called()

    # ------------------------------------------------------------------
    # AC5: all candidates unavailable → error lists reasons
    # ------------------------------------------------------------------

    def test_all_preflight_skipped_error_includes_reasons(self, tmp_path):
        """AC5: when all candidates fail preflight, error message lists each reason."""
        issue = _make_issue("feat-all-fail")
        orch = _make_orch_with_running(tmp_path, issue)
        orch.config.budget_limit = 10.0
        _exceed_budget(orch)

        prov_a = _api_provider(pid="p-a", api_key="sk-a", models=["m-a"], model_costs={})
        prov_b = _api_provider(pid="p-b", api_key="sk-b", models=["m-b"], model_costs={})

        target_a = _make_target(provider=prov_a, model="m-a", index=0)
        target_b = _make_target(provider=prov_b, model="m-b", index=1)
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_a, target_b])
        orch._run_api_worker = AsyncMock()  # should never be called

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        orch._on_worker_exit.assert_called_once()
        _, _, error_msg = orch._on_worker_exit.call_args[0]
        # Must contain both candidate keys and reasons
        assert "p-a" in error_msg, f"Expected 'p-a' in error: {error_msg!r}"
        assert "p-b" in error_msg, f"Expected 'p-b' in error: {error_msg!r}"
        assert "budget_exceeded" in error_msg, (
            f"Expected reason in error: {error_msg!r}"
        )

    def test_all_candidates_include_reasons_for_mixed_failures(self, tmp_path):
        """AC5: mix of preflight skip + startup error both appear in the error."""
        issue = _make_issue("feat-mixed-fail")
        orch = _make_orch_with_running(tmp_path, issue)

        prov_a = _api_provider(
            pid="p-a",
            api_key="",
            billing_model="per_token",
        )  # preflight: missing_credentials
        prov_b = _api_provider(pid="p-b", api_key="sk-b")  # startup: ProviderStartupError

        target_a = _make_target(provider=prov_a, model="m1", index=0)
        target_b = _make_target(provider=prov_b, model="m1", index=1)
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_a, target_b])

        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            raise ProviderStartupError(
                "p-b is down", candidate_key=target.candidate_key, reason="overloaded"
            )
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        orch._on_worker_exit.assert_called_once()
        _, _, error_msg = orch._on_worker_exit.call_args[0]
        assert "p-a" in error_msg or "missing_credentials" in error_msg
        assert "p-b" in error_msg or "overloaded" in error_msg

    def test_all_candidates_unavailable_calls_on_worker_exit_abnormal(self, tmp_path):
        """When all candidates are unavailable, _on_worker_exit is called with 'abnormal'."""
        issue = _make_issue("feat-exit-abnormal")
        orch = _make_orch_with_running(tmp_path, issue)

        prov = _api_provider(
            pid="p-only",
            api_key="",
            billing_model="per_token",
        )  # will be preflight-skipped
        target = _make_target(provider=prov, model="m1")
        orch._resolve_dispatch_targets = MagicMock(return_value=[target])
        orch._run_api_worker = AsyncMock()

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        orch._on_worker_exit.assert_called_once()
        call_args = orch._on_worker_exit.call_args[0]
        assert call_args[0] == issue.id
        assert call_args[1] == "abnormal"

    # ------------------------------------------------------------------
    # Preflight does not interfere with normal failover (ProviderStartupError)
    # ------------------------------------------------------------------

    def test_preflight_passes_startup_error_still_triggers_failover(self, tmp_path):
        """Candidates that pass preflight still fall back on ProviderStartupError."""
        issue = _make_issue("feat-startup-fail")
        orch = _make_orch_with_running(tmp_path, issue)

        prov_a = _api_provider(pid="a", api_key="sk-a")
        prov_b = _api_provider(pid="b", api_key="sk-b")

        target_a = _make_target(provider=prov_a, model="m1", index=0)
        target_b = _make_target(provider=prov_b, model="m1", index=1)
        orch._resolve_dispatch_targets = MagicMock(return_value=[target_a, target_b])

        calls = []
        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
            if provider.id == "a":
                raise ProviderStartupError("a is down", candidate_key="a/m1", reason="overloaded")
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        assert calls == ["a", "b"], "Normal startup failover must still work"
        orch._on_worker_exit.assert_not_called()

    # ------------------------------------------------------------------
    # Preflight all pass, no regression for happy path
    # ------------------------------------------------------------------

    def test_first_candidate_passes_preflight_and_runs(self, tmp_path):
        """When first candidate passes preflight, it is started immediately."""
        issue = _make_issue("feat-happy")
        orch = _make_orch_with_running(tmp_path, issue)

        prov = _api_provider(pid="p-happy", api_key="sk-ok")
        target = _make_target(provider=prov, model="m1")
        orch._resolve_dispatch_targets = MagicMock(return_value=[target])

        calls = []
        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
        orch._run_api_worker = mock_api_worker

        prof = _profile(mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=prof))

        assert calls == ["p-happy"]
        orch._on_worker_exit.assert_not_called()


# ---------------------------------------------------------------------------
# Test that existing budget tests still pass (DoD #2 proxy check)
# ---------------------------------------------------------------------------


class TestExistingBudgetSemanticsSurvive:
    """Regression: preflight must not break existing _should_dispatch budget behavior."""

    def test_should_dispatch_still_rejects_paid_model_when_budget_exceeded(self, tmp_path):
        """_should_dispatch must still return False for paid model over budget."""
        prov = _api_provider(
            pid="paid",
            model_costs={"m1": {"cost_per_1k_input": 3.0, "cost_per_1k_output": 15.0}},
        )
        project_store = MagicMock()
        project_store.list_all.return_value = []
        cfg = ServiceConfig(budget_limit=10.0)
        cfg.agent_profiles = [
            AgentProfile(name="default", command="cli", provider_id="paid")
        ]
        orch = Orchestrator(
            config=cfg,
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        mock_ps = MagicMock()
        mock_ps.get.return_value = prov
        mock_ps.get_default.return_value = prov
        orch.provider_store = mock_ps
        _exceed_budget(orch)

        issue = _make_issue()
        assert orch._should_dispatch(issue) is False

    def test_should_dispatch_still_allows_free_model_when_budget_exceeded(self, tmp_path):
        """_should_dispatch must still return True for $0 model over budget."""
        prov = _api_provider(
            pid="free-p",
            model_costs={"m1": {"cost_per_1k_input": 0.0, "cost_per_1k_output": 0.0}},
        )
        project_store = MagicMock()
        project_store.list_all.return_value = []
        cfg = ServiceConfig(budget_limit=10.0)
        cfg.agent_profiles = [
            AgentProfile(name="default", command="cli", provider_id="free-p")
        ]
        orch = Orchestrator(
            config=cfg,
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )
        mock_ps = MagicMock()
        mock_ps.get.return_value = prov
        mock_ps.get_default.return_value = prov
        orch.provider_store = mock_ps
        _exceed_budget(orch)

        issue = _make_issue()
        assert orch._should_dispatch(issue) is True
