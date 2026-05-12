"""Tests for per-agent telemetry comment on bead at worker completion.

Covers (oompah-zlz_2-y3fy):
- _format_tokens, _format_duration, _dispatch_attempt_label,
  _count_tool_calls helpers
- _resolve_run_provider_and_model: snapshot vs live resolution,
  subscription-ACP detection
- _format_telemetry_comment: all fields render per spec for API and
  ACP (subscription + per-token) and CLI runs
- _fire_telemetry_comment: submits to the tick pool; never raises
- _on_worker_exit fires the comment alongside _fire_task_cost_record
  for every exit reason (normal, stalled, abnormal/error,
  ask_question, max_turns)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from oompah.api_agent import AgentActivity
from oompah.config import ServiceConfig
from oompah.models import (
    AgentProfile,
    Issue,
    LiveSession,
    ModelProvider,
    RunningEntry,
)
from oompah.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    identifier: str = "test-001",
    state: str = "in_progress",
    project_id: str | None = None,
    labels: list[str] | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Test issue body.",
        state=state,
        project_id=project_id,
        labels=labels or [],
    )


def _make_live_session(
    input_tokens: int = 1000,
    output_tokens: int = 500,
    total_tokens: int = 1500,
    turn_count: int = 5,
    sdk_cost_usd: float | None = None,
) -> LiveSession:
    s = LiveSession(
        session_id="test-session",
        thread_id="t1",
        turn_id="0",
        agent_pid=None,
    )
    s.input_tokens = input_tokens
    s.output_tokens = output_tokens
    s.total_tokens = total_tokens
    s.turn_count = turn_count
    s.sdk_cost_usd = sdk_cost_usd
    return s


_SENTINEL = object()


def _make_running_entry(
    identifier: str = "test-001",
    profile_name: str = "standard",
    session=_SENTINEL,
    issue: Issue | None = None,
    retry_attempt: int = 0,
    agent_log_path: str | None = "/tmp/agent-logs/test-001__20260512T130000Z.jsonl",
    provider_name: str | None = "openai",
    model_name: str | None = "gpt-4o",
    model_role: str | None = "deep",
    activity_log: list | None = None,
) -> RunningEntry:
    if session is _SENTINEL:
        resolved_session = _make_live_session()
    else:
        resolved_session = session
    return RunningEntry(
        worker_task=MagicMock(),
        identifier=identifier,
        issue=issue or _make_issue(identifier),
        session=resolved_session,
        retry_attempt=retry_attempt,
        started_at=datetime.now(timezone.utc),
        agent_profile_name=profile_name,
        activity_log=activity_log or [],
        agent_log_path=agent_log_path,
        provider_name=provider_name,
        model_name=model_name,
        model_role=model_role,
    )


def _make_provider(
    name: str = "openai",
    model: str = "gpt-4o",
    mode: str = "api",
    billing_model: str = "subscription",
    cost_per_1k_input: float = 0.005,
    cost_per_1k_output: float = 0.015,
) -> ModelProvider:
    return ModelProvider(
        id=f"prov-{name}",
        name=name,
        base_url="https://api.openai.com/v1" if mode == "api" else "",
        api_key="sk-test" if mode == "api" else "",
        models=[model],
        default_model=model,
        mode=mode,
        billing_model=billing_model,
        model_costs={
            model: {
                "cost_per_1k_input": cost_per_1k_input,
                "cost_per_1k_output": cost_per_1k_output,
            }
        },
    )


def _make_profile(
    name: str = "standard",
    model: str = "gpt-4o",
    provider_id: str = "prov-openai",
    mode: str = "auto",
    model_role: str | None = None,
) -> AgentProfile:
    return AgentProfile(
        name=name,
        command="agent",
        provider_id=provider_id,
        model=model,
        mode=mode,
        model_role=model_role,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.002,
    )


def _make_orchestrator(tmp_path, providers=None, profiles=None):
    cfg = ServiceConfig()
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orch = Orchestrator(
        config=cfg,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    if providers:
        for p in providers:
            orch.provider_store._providers[p.id] = p
    if profiles:
        orch.config.agent_profiles = list(profiles)
    return orch


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------


class TestFormatTokens:
    def test_below_thousand(self):
        assert Orchestrator._format_tokens(0) == "0"
        assert Orchestrator._format_tokens(42) == "42"
        assert Orchestrator._format_tokens(999) == "999"

    def test_thousands(self):
        assert Orchestrator._format_tokens(1000) == "1.0K"
        assert Orchestrator._format_tokens(14200) == "14.2K"
        assert Orchestrator._format_tokens(999999) == "1000.0K"

    def test_millions(self):
        assert Orchestrator._format_tokens(1_000_000) == "1.0M"
        assert Orchestrator._format_tokens(2_500_000) == "2.5M"

    def test_bad_input(self):
        assert Orchestrator._format_tokens(None) == "0"
        assert Orchestrator._format_tokens("oops") == "0"


class TestFormatDuration:
    def test_seconds_only(self):
        assert Orchestrator._format_duration(0) == "0s"
        assert Orchestrator._format_duration(5) == "5s"
        assert Orchestrator._format_duration(59) == "59s"

    def test_minutes_and_seconds(self):
        assert Orchestrator._format_duration(60) == "1m 0s"
        assert Orchestrator._format_duration(372) == "6m 12s"

    def test_hours_minutes_seconds(self):
        assert Orchestrator._format_duration(3600) == "1h 0m 0s"
        assert Orchestrator._format_duration(3661) == "1h 1m 1s"
        assert Orchestrator._format_duration(7325) == "2h 2m 5s"

    def test_negative_clamps(self):
        assert Orchestrator._format_duration(-3) == "0s"

    def test_bad_input(self):
        assert Orchestrator._format_duration(None) == "0s"
        assert Orchestrator._format_duration("oops") == "0s"


class TestDispatchAttemptLabel:
    def test_first_attempt(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(retry_attempt=0)
        assert orch._dispatch_attempt_label(entry) == "1"

    def test_second_attempt(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(retry_attempt=1)
        assert orch._dispatch_attempt_label(entry) == "2"

    def test_yolo_reopen_ci_fix(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(
            retry_attempt=0,
            issue=_make_issue(labels=["ci-fix"]),
        )
        assert orch._dispatch_attempt_label(entry) == "YOLO-reopen"

    def test_yolo_reopen_merge_conflict(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(
            retry_attempt=5,
            issue=_make_issue(labels=["merge-conflict"]),
        )
        # Reopen-label trumps retry counter so the operator can
        # distinguish YOLO retries from natural escalations.
        assert orch._dispatch_attempt_label(entry) == "YOLO-reopen"


class TestCountToolCalls:
    def test_empty_log(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(activity_log=[])
        assert orch._count_tool_calls(entry) == 0

    def test_mixed_kinds(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        log = [
            AgentActivity(turn=1, kind="message", summary="hi"),
            AgentActivity(turn=1, kind="tool_call", summary="run"),
            AgentActivity(turn=1, kind="tool_result", summary="ok"),
            AgentActivity(turn=2, kind="tool_call", summary="read"),
            AgentActivity(turn=2, kind="thinking", summary="..."),
            AgentActivity(turn=3, kind="tool_call", summary="write"),
        ]
        entry = _make_running_entry(activity_log=log)
        assert orch._count_tool_calls(entry) == 3


# ---------------------------------------------------------------------------
# _resolve_run_provider_and_model
# ---------------------------------------------------------------------------


class TestResolveRunProviderAndModel:
    def test_prefers_entry_snapshot(self, tmp_path):
        provider = _make_provider(name="provA", model="modelA")
        profile = _make_profile(provider_id=provider.id, model="modelA")
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry(
            provider_name="snapshotProvider",
            model_name="snapshotModel",
        )
        prov_name, model_id, mode, is_sub = orch._resolve_run_provider_and_model(entry)
        assert prov_name == "snapshotProvider"
        assert model_id == "snapshotModel"
        assert mode == "auto"
        assert is_sub is False

    def test_falls_back_to_live_resolution(self, tmp_path):
        provider = _make_provider(name="provLive", model="modelLive")
        profile = _make_profile(provider_id=provider.id, model="modelLive")
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry(
            provider_name=None,
            model_name=None,
        )
        prov_name, model_id, _, _ = orch._resolve_run_provider_and_model(entry)
        assert prov_name == "provLive"
        assert model_id == "modelLive"

    def test_acp_subscription_flagged(self, tmp_path):
        provider = _make_provider(
            name="claude",
            model="claude-sonnet-4-6",
            mode="acp",
            billing_model="subscription",
        )
        profile = _make_profile(
            name="acp_sub",
            model="claude-sonnet-4-6",
            provider_id=provider.id,
            mode="acp",
        )
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry(profile_name="acp_sub")
        _, _, mode, is_sub = orch._resolve_run_provider_and_model(entry)
        assert mode == "acp"
        assert is_sub is True

    def test_acp_per_token_not_flagged(self, tmp_path):
        provider = _make_provider(
            name="claude",
            model="claude-sonnet-4-6",
            mode="acp",
            billing_model="per_token",
        )
        profile = _make_profile(
            name="acp_pt",
            model="claude-sonnet-4-6",
            provider_id=provider.id,
            mode="acp",
        )
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry(profile_name="acp_pt")
        _, _, mode, is_sub = orch._resolve_run_provider_and_model(entry)
        assert mode == "acp"
        assert is_sub is False


# ---------------------------------------------------------------------------
# _format_telemetry_comment
# ---------------------------------------------------------------------------


class TestFormatTelemetryComment:
    def test_api_run_complete_fields(self, tmp_path):
        provider = _make_provider(
            name="openai",
            model="gpt-4o",
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
        )
        profile = _make_profile(
            name="deep",
            model="gpt-4o",
            provider_id=provider.id,
        )
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        log = [
            AgentActivity(turn=1, kind="tool_call", summary="run"),
            AgentActivity(turn=1, kind="tool_call", summary="read"),
            AgentActivity(turn=2, kind="tool_call", summary="write"),
            AgentActivity(turn=2, kind="message", summary="hello"),
        ]
        session = _make_live_session(
            input_tokens=14200,
            output_tokens=3100,
            total_tokens=17300,
            turn_count=27,
        )
        entry = _make_running_entry(
            identifier="oompah-zlz_2-xxx",
            profile_name="deep",
            session=session,
            retry_attempt=1,
            provider_name="openai",
            model_name="gpt-4o",
            model_role="deep",
            activity_log=log,
            agent_log_path=(
                "/tmp/agent-logs/oompah-zlz_2-xxx__20260512T130000Z.jsonl"
            ),
        )
        comment = orch._format_telemetry_comment(entry, "normal", 372)
        assert "Run #2 [attempt=2, profile=deep, role=deep -> openai/gpt-4o]" in comment
        assert "Turns: 27" in comment
        assert "Tool calls: 3" in comment
        assert "14.2K in" in comment
        assert "3.1K out" in comment
        assert "[17.3K total]" in comment
        # Cost: $0.005 * 14.2 + $0.015 * 3.1 = $0.071 + $0.0465 = $0.1175
        assert "Cost: $0.1175" in comment
        assert "Exit: normal" in comment
        assert "Duration: 6m 12s" in comment
        assert "Log: oompah-zlz_2-xxx__20260512T130000Z.jsonl" in comment

    def test_acp_subscription_shows_subscription_label(self, tmp_path):
        provider = _make_provider(
            name="claude",
            model="claude-sonnet-4-6",
            mode="acp",
            billing_model="subscription",
        )
        profile = _make_profile(
            name="acp_sub",
            model="claude-sonnet-4-6",
            provider_id=provider.id,
            mode="acp",
        )
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        session = _make_live_session(input_tokens=5000, output_tokens=1000)
        entry = _make_running_entry(
            profile_name="acp_sub",
            session=session,
            provider_name="claude",
            model_name="claude-sonnet-4-6",
        )
        comment = orch._format_telemetry_comment(entry, "normal", 120)
        assert "Cost: (subscription)" in comment

    def test_acp_per_token_uses_sdk_cost(self, tmp_path):
        provider = _make_provider(
            name="claude",
            model="claude-sonnet-4-6",
            mode="acp",
            billing_model="per_token",
        )
        profile = _make_profile(
            name="acp_pt",
            model="claude-sonnet-4-6",
            provider_id=provider.id,
            mode="acp",
        )
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        session = _make_live_session(
            input_tokens=5000,
            output_tokens=1000,
            sdk_cost_usd=0.0042,
        )
        entry = _make_running_entry(
            profile_name="acp_pt",
            session=session,
            provider_name="claude",
            model_name="claude-sonnet-4-6",
        )
        comment = orch._format_telemetry_comment(entry, "normal", 60)
        assert "Cost: $0.0042" in comment

    def test_yolo_reopen_attempt_label(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry(
            issue=_make_issue(labels=["ci-fix"]),
        )
        comment = orch._format_telemetry_comment(entry, "normal", 30)
        assert "Run #YOLO-reopen" in comment
        assert "attempt=YOLO-reopen" in comment

    def test_abnormal_renders_as_error(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry()
        comment = orch._format_telemetry_comment(entry, "abnormal", 12)
        assert "Exit: error" in comment

    def test_stalled_exit(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry()
        comment = orch._format_telemetry_comment(entry, "stalled", 50)
        assert "Exit: stalled" in comment

    def test_no_session_renders_zeros(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry(session=None)
        comment = orch._format_telemetry_comment(entry, "normal", 10)
        assert "Turns: 0" in comment
        assert "Tool calls: 0" in comment
        assert "0 in" in comment
        assert "0 out" in comment

    def test_log_basename_only(self, tmp_path):
        """Log line shows just the filename, not the full path."""
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry(
            agent_log_path="/home/user/.oompah/agent-logs/test__20260101T120000Z.jsonl",
        )
        comment = orch._format_telemetry_comment(entry, "normal", 10)
        assert "Log: test__20260101T120000Z.jsonl" in comment
        # No path components
        assert "/home/" not in comment

    def test_no_log_path_omits_line(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry(agent_log_path=None)
        comment = orch._format_telemetry_comment(entry, "normal", 10)
        assert "Log:" not in comment

    def test_role_unknown_renders_dash(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry(model_role=None)
        comment = orch._format_telemetry_comment(entry, "normal", 10)
        assert "role=—" in comment


# ---------------------------------------------------------------------------
# _fire_telemetry_comment / _write_telemetry_comment
# ---------------------------------------------------------------------------


class TestFireTelemetryComment:
    def test_submits_to_pool(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry()
        with patch.object(orch._tick_pool, "submit") as submit:
            orch._fire_telemetry_comment(entry, "normal", 5.0)
            assert submit.called
            args, _ = submit.call_args
            # The submitted callable + the 3 args we forwarded.
            assert args[0] == orch._write_telemetry_comment
            assert args[1] is entry
            assert args[2] == "normal"
            assert args[3] == 5.0

    def test_swallows_submit_exception(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry()
        with patch.object(
            orch._tick_pool, "submit", side_effect=RuntimeError("boom"),
        ):
            # Must not raise — fire-and-forget.
            orch._fire_telemetry_comment(entry, "normal", 5.0)

    def test_write_calls_post_comment(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry()
        with patch.object(orch, "_post_comment") as pc:
            orch._write_telemetry_comment(entry, "normal", 5.0)
            assert pc.called
            args, kwargs = pc.call_args
            assert args[0] == entry.identifier
            # Posted comment text should include the header.
            assert "Run #" in args[1]

    def test_write_swallows_post_failure(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry()
        with patch.object(
            orch, "_post_comment", side_effect=RuntimeError("forge down"),
        ):
            # Must not raise.
            orch._write_telemetry_comment(entry, "normal", 5.0)


# ---------------------------------------------------------------------------
# Integration: _on_worker_exit fires the telemetry comment
# ---------------------------------------------------------------------------


class TestOnWorkerExitFires:
    @pytest.mark.asyncio
    async def test_normal_exit_fires(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry()
        orch.state.running[entry.issue.id] = entry
        with patch.object(orch, "_fire_telemetry_comment") as ftc, \
             patch.object(orch, "_fire_task_cost_record"), \
             patch.object(orch, "_post_comment"), \
             patch.object(orch, "_tracker_for_project"), \
             patch.object(
                 orch, "_tracker_for_issue",
                 side_effect=Exception("skip downstream"),
             ):
            await orch._on_worker_exit(entry.issue.id, "normal", None)
            assert ftc.called
            args, _ = ftc.call_args
            assert args[0] is entry
            assert args[1] == "normal"
            assert isinstance(args[2], float)

    @pytest.mark.asyncio
    async def test_stalled_exit_fires(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry()
        orch.state.running[entry.issue.id] = entry
        with patch.object(orch, "_fire_telemetry_comment") as ftc, \
             patch.object(orch, "_fire_task_cost_record"), \
             patch.object(orch, "_post_comment"), \
             patch.object(orch, "_schedule_retry"):
            await orch._on_worker_exit(entry.issue.id, "stalled", "boom")
            assert ftc.called
            args, _ = ftc.call_args
            assert args[1] == "stalled"

    @pytest.mark.asyncio
    async def test_abnormal_exit_fires(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry()
        orch.state.running[entry.issue.id] = entry
        with patch.object(orch, "_fire_telemetry_comment") as ftc, \
             patch.object(orch, "_fire_task_cost_record"), \
             patch.object(orch, "_post_comment"), \
             patch.object(orch, "_schedule_retry"):
            await orch._on_worker_exit(entry.issue.id, "abnormal", "crash")
            assert ftc.called
            args, _ = ftc.call_args
            assert args[1] == "abnormal"

    @pytest.mark.asyncio
    async def test_ask_question_exit_fires(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        entry = _make_running_entry()
        orch.state.running[entry.issue.id] = entry
        with patch.object(orch, "_fire_telemetry_comment") as ftc, \
             patch.object(orch, "_fire_task_cost_record"), \
             patch.object(orch, "_post_comment"), \
             patch.object(orch, "_tracker_for_project"):
            await orch._on_worker_exit(entry.issue.id, "ask_question", "Why?")
            assert ftc.called
            args, _ = ftc.call_args
            assert args[1] == "ask_question"

    @pytest.mark.asyncio
    async def test_missing_entry_skips_silently(self, tmp_path):
        provider = _make_provider()
        profile = _make_profile(provider_id=provider.id)
        orch = _make_orchestrator(tmp_path, [provider], [profile])
        with patch.object(orch, "_fire_telemetry_comment") as ftc:
            await orch._on_worker_exit("does-not-exist", "normal", None)
            assert not ftc.called
