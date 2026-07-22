"""Tests for OOMPAH-346 — atomic round-robin dispatch-time reservation.

Covers the acceptance criteria from OOMPAH-346:

  AC#1  Simultaneous batch for a Claude/Codex round-robin role is balanced
        within one dispatch per provider whenever both are eligible.
  AC#2  Running-task state shows the actual chosen provider.
  AC#3  No duplicate candidate selection is caused solely by dispatching
        before a prior session completes.
  AC#4  Existing provider-selection and full test suites pass (regression).

Tests included:

  - Orchestrator: concurrent dispatches on the same round-robin role produce
    alternating provider targets before workers complete (AC#1, AC#3).
  - Failover: preflight failure → next candidate reserved correctly (AC#1).
  - Failover: startup failure → next candidate tried (AC#1).
  - Next dispatch after failover selects the correct next candidate (AC#3).
  - Regression: 5 concurrent Claude/Codex dispatches include Codex, not all Claude.
  - Priority role is not affected by the reservation change.
  - Legacy single-provider profiles are not affected.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import AgentProfile, Issue, ModelProvider, RunningEntry
from oompah.orchestrator import (
    DispatchTarget,
    Orchestrator,
    ProviderStartupError,
)
from oompah.roles import Candidate, CandidateSelector, Role, RoleStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _c(provider_id: str, model: str = "m1") -> Candidate:
    return Candidate(provider_id=provider_id, model=model)


def _role(name: str, strategy: str, candidates: list[Candidate]) -> Role:
    return Role(
        name=name,
        strategy=strategy,
        candidates=candidates,
        updated_at=datetime.now(timezone.utc),
    )


def _provider(pid: str, name: str = "", models: list[str] | None = None) -> ModelProvider:
    return ModelProvider(
        id=pid,
        name=name or pid,
        base_url="http://example.com/v1",
        api_key="sk-test",
        models=models or ["m1"],
        default_model=(models or ["m1"])[0],
    )


def _make_issue(identifier: str = "test-1") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Test issue — enough text to pass the empty-description gate.",
        state="open",
        issue_type="task",
        priority=2,
        labels=[],
    )


def _make_orchestrator(tmp_path, *, role_store: RoleStore | None = None) -> Orchestrator:
    """Minimal Orchestrator with no running server required."""
    project_store = MagicMock()
    project_store.list_all.return_value = []
    rs = role_store or RoleStore(path=str(tmp_path / "roles.json"))
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=rs,
        state_path=str(tmp_path / "state.json"),
    )
    orch._fetch_in_progress_issues = MagicMock(return_value=[])
    return orch


def _register_issue(orch: Orchestrator, issue: Issue) -> None:
    """Put issue into the orchestrator's running state."""
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


def _make_provider_store(providers: list[ModelProvider]) -> MagicMock:
    """Mock ProviderStore that returns providers by id."""
    ps = MagicMock()
    prov_map = {p.id: p for p in providers}
    ps.get = lambda pid: prov_map.get(pid)
    ps.get_default = lambda: providers[0] if providers else None
    return ps


# ---------------------------------------------------------------------------
# AC#1 & AC#3 — Concurrent dispatches produce alternating provider targets
# ---------------------------------------------------------------------------


class TestConcurrentDispatchAlternation:
    """Concurrent _resolve_dispatch_targets() calls for a round-robin role
    must return different first targets (alternating providers), even before
    any worker has completed."""

    def test_two_concurrent_dispatches_select_different_providers(self, tmp_path):
        """Two concurrent dispatch-target resolutions select different providers."""
        prov_a = _provider("claude", "Claude", ["sonnet"])
        prov_b = _provider("codex", "Codex", ["gpt-4o"])
        c_a = Candidate(provider_id="claude", model="sonnet")
        c_b = Candidate(provider_id="codex", model="gpt-4o")

        # Set up role store with round-robin role
        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_a, c_b])

        # Shared CandidateSelector
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))

        orch1 = _make_orchestrator(tmp_path, role_store=role_store)
        orch1.provider_store = _make_provider_store([prov_a, prov_b])
        orch1._candidate_selector = sel

        orch2 = _make_orchestrator(tmp_path, role_store=role_store)
        orch2.provider_store = _make_provider_store([prov_a, prov_b])
        orch2._candidate_selector = sel

        profile = AgentProfile(name="default", command="cli", model_role="fast")

        first_targets: list[list[DispatchTarget]] = [None, None]  # type: ignore[list-item]

        def resolve1():
            first_targets[0] = orch1._resolve_dispatch_targets(profile)

        def resolve2():
            first_targets[1] = orch2._resolve_dispatch_targets(profile)

        t1 = threading.Thread(target=resolve1)
        t2 = threading.Thread(target=resolve2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert first_targets[0] is not None
        assert first_targets[1] is not None

        first_provider_0 = first_targets[0][0].provider.id
        first_provider_1 = first_targets[1][0].provider.id

        assert first_provider_0 != first_provider_1, (
            f"Both concurrent dispatches selected the same provider: {first_provider_0!r}. "
            "The all-first-candidate race is NOT fixed."
        )

    def test_n_concurrent_dispatches_balance_providers(self, tmp_path):
        """N concurrent _resolve_dispatch_targets() calls distribute providers fairly."""
        N = 10  # must be even
        prov_a = _provider("p-a", models=["m1"])
        prov_b = _provider("p-b", models=["m2"])
        c_a = Candidate(provider_id="p-a", model="m1")
        c_b = Candidate(provider_id="p-b", model="m2")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_a, c_b])

        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        profile = AgentProfile(name="default", command="cli", model_role="fast")

        first_provider_ids: list[str] = []
        lock = threading.Lock()

        def resolve():
            orch = _make_orchestrator(tmp_path, role_store=role_store)
            orch.provider_store = _make_provider_store([prov_a, prov_b])
            orch._candidate_selector = sel
            targets = orch._resolve_dispatch_targets(profile)
            if targets:
                with lock:
                    first_provider_ids.append(targets[0].provider.id)

        threads = [threading.Thread(target=resolve) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(first_provider_ids) == N
        count_a = first_provider_ids.count("p-a")
        count_b = first_provider_ids.count("p-b")

        assert abs(count_a - count_b) <= 1, (
            f"Unfair distribution: p-a={count_a}, p-b={count_b}. "
            "The atomic reservation is not working correctly."
        )
        assert count_a > 0, "p-a must be selected at least once"
        assert count_b > 0, "p-b must be selected at least once"

    def test_dispatches_alternate_before_any_worker_completes(self, tmp_path):
        """Alternation must occur even when no worker has completed yet (no record_used)."""
        prov_a = _provider("claude", models=["sonnet"])
        prov_b = _provider("codex", models=["gpt-4o"])
        c_a = Candidate(provider_id="claude", model="sonnet")
        c_b = Candidate(provider_id="codex", model="gpt-4o")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_a, c_b])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))

        profile = AgentProfile(name="default", command="cli", model_role="fast")

        selections: list[str] = []

        # Simulate N dispatches all happening before any worker completes
        # (no record_used() calls anywhere)
        for _ in range(4):
            orch = _make_orchestrator(tmp_path, role_store=role_store)
            orch.provider_store = _make_provider_store([prov_a, prov_b])
            orch._candidate_selector = sel
            targets = orch._resolve_dispatch_targets(profile)
            assert targets, "Must resolve at least one target"
            selections.append(targets[0].provider.id)

        count_claude = selections.count("claude")
        count_codex = selections.count("codex")

        assert count_codex > 0, (
            f"Regression: all dispatches selected Claude only. "
            f"selections={selections}. Codex never dispatched before workers complete."
        )
        assert abs(count_claude - count_codex) <= 1, (
            f"Unfair distribution: claude={count_claude}, codex={count_codex}"
        )


# ---------------------------------------------------------------------------
# Failover tests
# ---------------------------------------------------------------------------


class TestPreflightFailoverReservation:
    """Failover: preflight failure does not corrupt round-robin ordering."""

    def _make_orch_with_issue(self, tmp_path, issue: Issue, *,
                               prov_a, prov_b, c_a, c_b, sel):
        """Build an orchestrator with the issue in running state."""
        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_a, c_b])
        orch = _make_orchestrator(tmp_path, role_store=role_store)
        orch.provider_store = _make_provider_store([prov_a, prov_b])
        orch._candidate_selector = sel
        orch._on_worker_exit = AsyncMock()
        _register_issue(orch, issue)
        return orch

    def test_preflight_failure_falls_back_to_second_candidate(self, tmp_path):
        """When the reserved candidate fails preflight, the next is tried."""
        prov_a = _provider("p-a", models=["m1"])
        prov_b = _provider("p-b", models=["m2"])
        c_a = Candidate(provider_id="p-a", model="m1")
        c_b = Candidate(provider_id="p-b", model="m2")

        issue = _make_issue("fail-pref-1")
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        orch = self._make_orch_with_issue(tmp_path, issue,
                                          prov_a=prov_a, prov_b=prov_b,
                                          c_a=c_a, c_b=c_b, sel=sel)

        # Make first candidate fail preflight, second pass
        call_count = [0]
        original_preflight = orch._candidate_preflight

        def preflight_first_fails(target):
            call_count[0] += 1
            if target.provider.id == "p-a" and call_count[0] == 1:
                return "rate_limited"  # first candidate fails preflight
            return ""  # all others pass

        orch._candidate_preflight = preflight_first_fails

        calls: list[str] = []

        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)

        orch._run_api_worker = mock_api_worker

        profile = AgentProfile(name="default", command="cli", model_role="fast", mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=profile))

        assert "p-a" not in calls, "p-a must be preflight-skipped"
        assert "p-b" in calls, "p-b must be tried as fallback"
        orch._on_worker_exit.assert_not_called()

    def test_next_dispatch_after_preflight_failure_gets_correct_next_candidate(self, tmp_path):
        """After a preflight-fail/fallback dispatch, the next dispatch picks
        the correct next candidate based on updated usage state."""
        prov_a = _provider("p-a", models=["m1"])
        prov_b = _provider("p-b", models=["m2"])
        c_a = Candidate(provider_id="p-a", model="m1")
        c_b = Candidate(provider_id="p-b", model="m2")

        sel = CandidateSelector(path=str(tmp_path / "usage.json"))

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_a, c_b])
        profile = AgentProfile(name="default", command="cli", model_role="fast", mode="api")

        # Dispatch 1: p-a reserved but fails preflight, p-b succeeds
        issue1 = _make_issue("d1")
        orch1 = _make_orchestrator(tmp_path, role_store=role_store)
        orch1.provider_store = _make_provider_store([prov_a, prov_b])
        orch1._candidate_selector = sel
        orch1._on_worker_exit = AsyncMock()
        _register_issue(orch1, issue1)

        first_pref_call = [True]

        def preflight_fail_a_once(target):
            if target.provider.id == "p-a" and first_pref_call[0]:
                first_pref_call[0] = False
                return "rate_limited"
            return ""

        orch1._candidate_preflight = preflight_fail_a_once
        calls1: list[str] = []

        async def mock_api1(issue, attempt, profile, provider, target=None):
            calls1.append(provider.id)

        orch1._run_api_worker = mock_api1
        asyncio.run(orch1._run_worker(issue1, attempt=1, profile=profile))

        assert "p-b" in calls1, "p-b must be tried after p-a preflight failure"

        # Dispatch 2: p-a was reserved (stamped) and p-b succeeded (record_used).
        # p-a was stamped first (at reservation), p-b later (after success).
        # → p-a should be the LRU → next dispatch picks p-a.
        targets2 = []
        orch2 = _make_orchestrator(tmp_path, role_store=role_store)
        orch2.provider_store = _make_provider_store([prov_a, prov_b])
        orch2._candidate_selector = sel
        targets2 = orch2._resolve_dispatch_targets(profile)

        assert targets2, "Dispatch 2 must resolve targets"
        first_target_2 = targets2[0].provider.id
        # p-b was record_used() (most recent); p-a was only reserved (earlier stamp).
        # So p-a is LRU → dispatch 2 picks p-a.
        assert first_target_2 == "p-a", (
            f"After p-b succeeded as fallback, next dispatch should pick p-a (LRU). "
            f"Got: {first_target_2!r}"
        )


class TestStartupFailoverReservation:
    """Failover: ProviderStartupError does not corrupt round-robin ordering."""

    def test_startup_failure_falls_back_to_second_candidate(self, tmp_path):
        """When the reserved candidate raises ProviderStartupError, the next is tried."""
        prov_a = _provider("p-a", models=["m1"])
        prov_b = _provider("p-b", models=["m2"])
        c_a = Candidate(provider_id="p-a", model="m1")
        c_b = Candidate(provider_id="p-b", model="m2")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_a, c_b])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))

        issue = _make_issue("fail-start-1")
        orch = _make_orchestrator(tmp_path, role_store=role_store)
        orch.provider_store = _make_provider_store([prov_a, prov_b])
        orch._candidate_selector = sel
        orch._on_worker_exit = AsyncMock()
        _register_issue(orch, issue)

        calls: list[str] = []

        async def mock_api_worker(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
            if provider.id == "p-a":
                raise ProviderStartupError(
                    "p-a startup failed",
                    candidate_key="p-a/m1",
                    reason="overloaded",
                )

        orch._run_api_worker = mock_api_worker
        profile = AgentProfile(name="default", command="cli", model_role="fast", mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=profile))

        assert "p-a" in calls, "p-a must be attempted"
        assert "p-b" in calls, "p-b must be tried after p-a startup failure"
        orch._on_worker_exit.assert_not_called()

    def test_next_dispatch_after_startup_failure_gets_correct_candidate(self, tmp_path):
        """After a startup-fail/fallback dispatch, the next dispatch picks
        the correct next candidate."""
        prov_a = _provider("p-a", models=["m1"])
        prov_b = _provider("p-b", models=["m2"])
        c_a = Candidate(provider_id="p-a", model="m1")
        c_b = Candidate(provider_id="p-b", model="m2")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_a, c_b])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        profile = AgentProfile(name="default", command="cli", model_role="fast", mode="api")

        # Dispatch 1: p-a reserved, starts but raises ProviderStartupError; p-b succeeds
        issue1 = _make_issue("d1-startup")
        orch1 = _make_orchestrator(tmp_path, role_store=role_store)
        orch1.provider_store = _make_provider_store([prov_a, prov_b])
        orch1._candidate_selector = sel
        orch1._on_worker_exit = AsyncMock()
        _register_issue(orch1, issue1)

        calls1: list[str] = []

        async def mock_api_startup_fail(issue, attempt, profile, provider, target=None):
            calls1.append(provider.id)
            if provider.id == "p-a":
                raise ProviderStartupError("fail", candidate_key="p-a/m1", reason="timeout")

        orch1._run_api_worker = mock_api_startup_fail
        asyncio.run(orch1._run_worker(issue1, attempt=1, profile=profile))

        assert calls1 == ["p-a", "p-b"], (
            f"Expected p-a (fail) then p-b (success), got {calls1}"
        )

        # Dispatch 2: p-a was stamped at reservation, p-b was record_used() after success.
        # p-a is the LRU → next dispatch should pick p-a.
        orch2 = _make_orchestrator(tmp_path, role_store=role_store)
        orch2.provider_store = _make_provider_store([prov_a, prov_b])
        orch2._candidate_selector = sel
        targets2 = orch2._resolve_dispatch_targets(profile)

        assert targets2
        assert targets2[0].provider.id == "p-a", (
            "After p-b succeeded as fallback, next dispatch should pick p-a (LRU)"
        )

    def test_repeated_startup_failures_do_not_repeat_failed_candidate(self, tmp_path):
        """When both candidates fail on startup, neither is repeated in the same dispatch."""
        prov_a = _provider("p-a", models=["m1"])
        prov_b = _provider("p-b", models=["m2"])
        c_a = Candidate(provider_id="p-a", model="m1")
        c_b = Candidate(provider_id="p-b", model="m2")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_a, c_b])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))

        issue = _make_issue("all-fail-start")
        orch = _make_orchestrator(tmp_path, role_store=role_store)
        orch.provider_store = _make_provider_store([prov_a, prov_b])
        orch._candidate_selector = sel
        orch._on_worker_exit = AsyncMock()
        _register_issue(orch, issue)

        calls: list[str] = []

        async def mock_both_fail(issue, attempt, profile, provider, target=None):
            calls.append(provider.id)
            raise ProviderStartupError("fail", candidate_key=f"{provider.id}/m1",
                                       reason="overloaded")

        orch._run_api_worker = mock_both_fail
        profile = AgentProfile(name="default", command="cli", model_role="fast", mode="api")
        asyncio.run(orch._run_worker(issue, attempt=1, profile=profile))

        # Each candidate tried at most once
        assert calls.count("p-a") <= 1, "p-a must not be tried more than once"
        assert calls.count("p-b") <= 1, "p-b must not be tried more than once"
        orch._on_worker_exit.assert_called_once()


# ---------------------------------------------------------------------------
# Regression test: 5 concurrent Claude/Codex dispatches include Codex
# ---------------------------------------------------------------------------


class TestClaudeCodexRegression:
    """Regression: five concurrent dispatches for a Claude/Codex round-robin role
    must include Codex (not all select Claude).

    Before the OOMPAH-346 fix: all 5 concurrent dispatches observed the same stale
    usage state and all selected Claude (the first configured candidate).
    After the fix: the atomic reserve_candidate() call distributes dispatches
    across both providers.
    """

    def test_five_concurrent_dispatches_include_codex(self, tmp_path):
        """Regression: 5 concurrent Claude/Codex dispatches must include Codex."""
        claude = _provider("claude", "Claude", ["claude-3-5-sonnet-20241022"])
        codex = _provider("codex", "Codex", ["gpt-4o"])
        c_claude = Candidate(provider_id="claude", model="claude-3-5-sonnet-20241022")
        c_codex = Candidate(provider_id="codex", model="gpt-4o")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_claude, c_codex])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))

        profile = AgentProfile(name="default", command="cli", model_role="fast")

        first_providers: list[str] = []
        lock = threading.Lock()

        def dispatch():
            orch = _make_orchestrator(tmp_path, role_store=role_store)
            orch.provider_store = _make_provider_store([claude, codex])
            orch._candidate_selector = sel
            targets = orch._resolve_dispatch_targets(profile)
            if targets:
                with lock:
                    first_providers.append(targets[0].provider.id)

        threads = [threading.Thread(target=dispatch) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(first_providers) == 5, "All 5 dispatches must resolve targets"
        codex_count = first_providers.count("codex")
        claude_count = first_providers.count("claude")

        assert codex_count > 0, (
            f"REGRESSION: All 5 concurrent dispatches selected Claude only! "
            f"providers={first_providers}. Codex was never dispatched. "
            f"The all-first-candidate race is NOT fixed."
        )
        assert abs(claude_count - codex_count) <= 1, (
            f"Distribution unfair: claude={claude_count}, codex={codex_count}. "
            f"Expected near-equal split."
        )

    def test_five_sequential_dispatches_alternate_claude_codex(self, tmp_path):
        """Five sequential dispatches alternate: C, X, C, X, C (or X, C, X, C, X)."""
        claude = _provider("claude", "Claude", ["claude-3-5-sonnet-20241022"])
        codex = _provider("codex", "Codex", ["gpt-4o"])
        c_claude = Candidate(provider_id="claude", model="claude-3-5-sonnet-20241022")
        c_codex = Candidate(provider_id="codex", model="gpt-4o")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_claude, c_codex])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        profile = AgentProfile(name="default", command="cli", model_role="fast")

        providers: list[str] = []
        for _ in range(5):
            orch = _make_orchestrator(tmp_path, role_store=role_store)
            orch.provider_store = _make_provider_store([claude, codex])
            orch._candidate_selector = sel
            targets = orch._resolve_dispatch_targets(profile)
            assert targets
            providers.append(targets[0].provider.id)

        # Must alternate (strictly): consecutive values must differ
        for i in range(len(providers) - 1):
            assert providers[i] != providers[i + 1], (
                f"Sequential dispatches must alternate. "
                f"Got two consecutive {providers[i]!r} at positions {i} and {i+1}. "
                f"Full sequence: {providers}"
            )


# ---------------------------------------------------------------------------
# Priority role is not affected by the reservation change
# ---------------------------------------------------------------------------


class TestPriorityRoleNotAffected:
    """Priority roles must always use the configured candidate order."""

    def test_priority_role_always_returns_first_candidate(self, tmp_path):
        """_resolve_dispatch_targets() for a priority role always picks the first."""
        prov_a = _provider("p-a", models=["m1"])
        prov_b = _provider("p-b", models=["m2"])
        c_a = Candidate(provider_id="p-a", model="m1")
        c_b = Candidate(provider_id="p-b", model="m2")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "priority", [c_a, c_b])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        profile = AgentProfile(name="default", command="cli", model_role="fast")

        for _ in range(5):
            orch = _make_orchestrator(tmp_path, role_store=role_store)
            orch.provider_store = _make_provider_store([prov_a, prov_b])
            orch._candidate_selector = sel
            targets = orch._resolve_dispatch_targets(profile)
            assert targets
            assert targets[0].provider.id == "p-a", (
                "Priority role must always start with the configured first candidate"
            )

    def test_priority_role_does_not_stamp_usage(self, tmp_path):
        """_resolve_dispatch_targets() for a priority role does not write usage state."""
        prov_a = _provider("p-a", models=["m1"])
        c_a = Candidate(provider_id="p-a", model="m1")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "priority", [c_a])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        profile = AgentProfile(name="default", command="cli", model_role="fast")

        orch = _make_orchestrator(tmp_path, role_store=role_store)
        orch.provider_store = _make_provider_store([prov_a])
        orch._candidate_selector = sel
        orch._resolve_dispatch_targets(profile)

        assert not (tmp_path / "usage.json").exists(), (
            "Priority role dispatch must not create usage file"
        )

    def test_concurrent_priority_dispatches_all_get_first_candidate(self, tmp_path):
        """All concurrent dispatches for a priority role get the same first candidate."""
        prov_a = _provider("p-a", models=["m1"])
        prov_b = _provider("p-b", models=["m2"])
        c_a = Candidate(provider_id="p-a", model="m1")
        c_b = Candidate(provider_id="p-b", model="m2")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "priority", [c_a, c_b])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        profile = AgentProfile(name="default", command="cli", model_role="fast")

        first_providers: list[str] = []
        lock = threading.Lock()

        def dispatch():
            orch = _make_orchestrator(tmp_path, role_store=role_store)
            orch.provider_store = _make_provider_store([prov_a, prov_b])
            orch._candidate_selector = sel
            targets = orch._resolve_dispatch_targets(profile)
            if targets:
                with lock:
                    first_providers.append(targets[0].provider.id)

        threads = [threading.Thread(target=dispatch) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All priority dispatches must always select p-a (the first configured)
        assert all(p == "p-a" for p in first_providers), (
            f"Priority role must always dispatch to p-a. Got: {first_providers}"
        )


# ---------------------------------------------------------------------------
# Legacy single-provider profile — not affected
# ---------------------------------------------------------------------------


class TestLegacySingleProviderNotAffected:
    """Single-provider profiles (profile.provider_id) must not be changed."""

    def test_single_provider_profile_dispatches_to_configured_provider(self, tmp_path):
        """A profile with provider_id (not model_role) dispatches to that provider."""
        prov = _provider("my-prov", models=["m1"])

        orch = _make_orchestrator(tmp_path)
        ps = MagicMock()
        ps.get = lambda pid: prov if pid == "my-prov" else None
        ps.get_default = lambda: prov
        orch.provider_store = ps

        profile = AgentProfile(
            name="default", command="cli", provider_id="my-prov", model="m1"
        )
        targets = orch._resolve_dispatch_targets(profile)

        assert len(targets) == 1
        assert targets[0].provider.id == "my-prov"
        assert targets[0].role_name is None  # not from a role

    def test_single_provider_does_not_create_usage_file(self, tmp_path):
        """Legacy single-provider profile dispatch does not touch usage state."""
        prov = _provider("my-prov", models=["m1"])

        orch = _make_orchestrator(tmp_path)
        ps = MagicMock()
        ps.get = lambda pid: prov if pid == "my-prov" else None
        ps.get_default = lambda: prov
        orch.provider_store = ps

        profile = AgentProfile(
            name="default", command="cli", provider_id="my-prov", model="m1"
        )
        orch._resolve_dispatch_targets(profile)

        # No usage file should be created for legacy single-provider profiles
        usage_path = tmp_path / "role_usage.json"
        # The candidate selector uses DEFAULT_USAGE_PATH, but since no role is
        # involved, reserve_candidate() is never called.
        # We verify by checking the in-memory usage state is still empty.
        assert orch._candidate_selector._usage == {}, (
            "Legacy single-provider dispatch must not write usage state"
        )


# ---------------------------------------------------------------------------
# State shows actual chosen provider (AC#2)
# ---------------------------------------------------------------------------


class TestReservedCandidateVisibleInTargets:
    """AC#2 — The first DispatchTarget in the resolved list reflects the reserved provider."""

    def test_reserved_candidate_is_first_target(self, tmp_path):
        """The reserved candidate is always the first DispatchTarget."""
        prov_a = _provider("p-a", models=["m1"])
        prov_b = _provider("p-b", models=["m2"])
        c_a = Candidate(provider_id="p-a", model="m1")
        c_b = Candidate(provider_id="p-b", model="m2")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_a, c_b])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        profile = AgentProfile(name="default", command="cli", model_role="fast")

        # Dispatch 1: c_a reserved → first target is p-a
        orch1 = _make_orchestrator(tmp_path, role_store=role_store)
        orch1.provider_store = _make_provider_store([prov_a, prov_b])
        orch1._candidate_selector = sel
        targets1 = orch1._resolve_dispatch_targets(profile)
        assert targets1[0].provider.id == "p-a"
        assert targets1[0].candidate == c_a

        # Dispatch 2: c_b reserved → first target is p-b
        orch2 = _make_orchestrator(tmp_path, role_store=role_store)
        orch2.provider_store = _make_provider_store([prov_a, prov_b])
        orch2._candidate_selector = sel
        targets2 = orch2._resolve_dispatch_targets(profile)
        assert targets2[0].provider.id == "p-b"
        assert targets2[0].candidate == c_b

    def test_targets_list_contains_all_candidates_as_fallbacks(self, tmp_path):
        """_resolve_dispatch_targets() returns ALL candidates, not just the reserved one."""
        prov_a = _provider("p-a", models=["m1"])
        prov_b = _provider("p-b", models=["m2"])
        c_a = Candidate(provider_id="p-a", model="m1")
        c_b = Candidate(provider_id="p-b", model="m2")

        role_store = RoleStore(path=str(tmp_path / "roles.json"))
        role_store.set_candidates("fast", "round_robin", [c_a, c_b])
        sel = CandidateSelector(path=str(tmp_path / "usage.json"))
        profile = AgentProfile(name="default", command="cli", model_role="fast")

        orch = _make_orchestrator(tmp_path, role_store=role_store)
        orch.provider_store = _make_provider_store([prov_a, prov_b])
        orch._candidate_selector = sel
        targets = orch._resolve_dispatch_targets(profile)

        assert len(targets) == 2, (
            "Both candidates must be in the targets list for failover support"
        )
        provider_ids = {t.provider.id for t in targets}
        assert provider_ids == {"p-a", "p-b"}
