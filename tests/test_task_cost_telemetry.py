"""Tests for per-task cost telemetry: oompah-zlz_2-qh8.

Covers:
- _compute_run_cost_record: token accounting + model resolution
- _merge_cost_records: cumulative accumulation across runs
- _write_task_cost_record: metadata persistence + error resilience
- _fire_task_cost_record: non-blocking fire-and-forget
- Integration: single-run close, multi-run escalation, mid-flight UI move-to-open,
  agent terminated by drain/stall
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import AgentProfile, Issue, LiveSession, ModelProvider, RunningEntry
from oompah.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(
    identifier: str = "test-001",
    state: str = "in_progress",
    project_id: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Test issue body.",
        state=state,
        project_id=project_id,
    )


def _make_live_session(
    input_tokens: int = 1000,
    output_tokens: int = 500,
    total_tokens: int = 1500,
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
    return s


_SENTINEL = object()


def _make_running_entry(
    identifier: str = "test-001",
    profile_name: str = "standard",
    session=_SENTINEL,
    issue: Issue | None = None,
) -> RunningEntry:
    """Build a RunningEntry for tests.

    When ``session`` is not supplied, a default LiveSession is used.
    Pass ``session=None`` explicitly to get an entry with no session.
    """
    if session is _SENTINEL:
        resolved_session = _make_live_session()
    else:
        resolved_session = session
    return RunningEntry(
        worker_task=MagicMock(),
        identifier=identifier,
        issue=issue or _make_issue(identifier),
        session=resolved_session,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        agent_profile_name=profile_name,
    )


def _make_provider(
    model: str = "gpt-4o",
    cost_per_1k_input: float = 0.005,
    cost_per_1k_output: float = 0.015,
) -> ModelProvider:
    p = ModelProvider(
        id="prov-1",
        name="openai",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        models=[model],
        default_model=model,
        model_costs={
            model: {
                "cost_per_1k_input": cost_per_1k_input,
                "cost_per_1k_output": cost_per_1k_output,
            }
        },
    )
    return p


def _make_profile(
    name: str = "standard",
    model: str = "gpt-4o",
    provider_id: str = "prov-1",
) -> AgentProfile:
    return AgentProfile(
        name=name,
        command="agent",
        provider_id=provider_id,
        model=model,
        cost_per_1k_input=0.001,  # fallback rates
        cost_per_1k_output=0.002,
    )


def _make_orchestrator(tmp_path, providers=None):
    """Create a test orchestrator with optional provider store."""
    from oompah.providers import ProviderStore
    cfg = _make_config()
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
    return orch


# ---------------------------------------------------------------------------
# _compute_run_cost_record
# ---------------------------------------------------------------------------

class TestComputeRunCostRecord:
    """Tests for the cost record computation helper."""

    def test_no_session_returns_none(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(session=None)
        assert orch._compute_run_cost_record(entry) is None

    def test_zero_tokens_returns_none(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        session = _make_live_session(input_tokens=0, output_tokens=0, total_tokens=0)
        entry = _make_running_entry(session=session)
        assert orch._compute_run_cost_record(entry) is None

    def test_single_model_cost_computation(self, tmp_path):
        """With 1000 input + 500 output tokens at $0.005/$0.015 per 1K,
        cost should be $0.005 + $0.0075 = $0.0125."""
        provider = _make_provider(model="gpt-4o", cost_per_1k_input=0.005, cost_per_1k_output=0.015)
        profile = _make_profile(name="standard", model="gpt-4o")
        orch = _make_orchestrator(tmp_path, providers=[provider])
        orch.config.agent_profiles = [profile]

        session = _make_live_session(input_tokens=1000, output_tokens=500)
        entry = _make_running_entry(profile_name="standard", session=session)

        record = orch._compute_run_cost_record(entry)
        assert record is not None
        assert record["total_input_tokens"] == 1000
        assert record["total_output_tokens"] == 500
        # $0.005 * 1 (1000/1000) + $0.015 * 0.5 (500/1000) = $0.005 + $0.0075 = $0.0125
        assert abs(record["total_cost_usd"] - 0.0125) < 1e-6
        assert "gpt-4o" in record["by_model"]
        model_entry = record["by_model"]["gpt-4o"]
        assert model_entry["input_tokens"] == 1000
        assert model_entry["output_tokens"] == 500
        assert abs(model_entry["cost_usd"] - 0.0125) < 1e-6

    def test_runs_list_contains_one_entry(self, tmp_path):
        provider = _make_provider(model="gpt-4o")
        profile = _make_profile(name="standard", model="gpt-4o")
        orch = _make_orchestrator(tmp_path, providers=[provider])
        orch.config.agent_profiles = [profile]

        session = _make_live_session(input_tokens=200, output_tokens=100)
        entry = _make_running_entry(profile_name="standard", session=session)

        record = orch._compute_run_cost_record(entry)
        assert record is not None
        assert len(record["runs"]) == 1
        run = record["runs"][0]
        assert run["profile"] == "standard"
        assert run["model"] == "gpt-4o"
        assert run["input_tokens"] == 200
        assert run["output_tokens"] == 100

    def test_fallback_profile_rates_when_no_provider(self, tmp_path):
        """When no provider is found, fall back to profile's cost_per_1k rates."""
        profile = AgentProfile(
            name="quick",
            command="agent",
            cost_per_1k_input=0.001,
            cost_per_1k_output=0.002,
        )
        orch = _make_orchestrator(tmp_path)
        orch.config.agent_profiles = [profile]

        session = _make_live_session(input_tokens=1000, output_tokens=1000)
        entry = _make_running_entry(profile_name="quick", session=session)

        record = orch._compute_run_cost_record(entry)
        assert record is not None
        # $0.001 * 1 + $0.002 * 1 = $0.003
        assert abs(record["total_cost_usd"] - 0.003) < 1e-6

    def test_unknown_profile_still_returns_record_with_zero_cost(self, tmp_path):
        """An unrecognized profile name doesn't crash — cost is just $0."""
        orch = _make_orchestrator(tmp_path)
        session = _make_live_session(input_tokens=500, output_tokens=200)
        entry = _make_running_entry(profile_name="nonexistent-profile", session=session)

        record = orch._compute_run_cost_record(entry)
        assert record is not None
        assert record["total_input_tokens"] == 500
        assert record["total_output_tokens"] == 200
        # No profile matched — cost is 0 but record still written
        assert record["total_cost_usd"] == 0.0

    def test_recorded_at_is_iso_utc_string(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        session = _make_live_session(input_tokens=100, output_tokens=50)
        entry = _make_running_entry(session=session)

        record = orch._compute_run_cost_record(entry)
        assert record is not None
        run = record["runs"][0]
        # Should be parseable as ISO datetime
        dt = datetime.fromisoformat(run["recorded_at"])
        assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# _merge_cost_records
# ---------------------------------------------------------------------------

class TestMergeCostRecords:
    """Tests for the cumulative merge helper."""

    def _single_record(
        self,
        model: str = "gpt-4o",
        input_tokens: int = 1000,
        output_tokens: int = 500,
        cost_usd: float = 0.0125,
    ) -> dict:
        return {
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
            "total_cost_usd": cost_usd,
            "by_model": {
                model: {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost_usd,
                }
            },
            "runs": [
                {
                    "profile": "standard",
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost_usd,
                    "recorded_at": "2024-01-01T00:00:00+00:00",
                }
            ],
        }

    def test_merge_into_none_returns_new_record(self):
        record = self._single_record()
        result = Orchestrator._merge_cost_records(None, record)
        assert result == record

    def test_merge_into_empty_dict_returns_new_record(self):
        record = self._single_record()
        result = Orchestrator._merge_cost_records({}, record)
        assert result == record

    def test_merge_same_model_sums_tokens_and_cost(self):
        """Two runs on the same model — tokens and cost should sum."""
        r1 = self._single_record(input_tokens=1000, output_tokens=500, cost_usd=0.0125)
        r2 = self._single_record(input_tokens=800, output_tokens=400, cost_usd=0.010)

        merged = Orchestrator._merge_cost_records(r1, r2)

        assert merged["total_input_tokens"] == 1800
        assert merged["total_output_tokens"] == 900
        assert abs(merged["total_cost_usd"] - 0.0225) < 1e-6
        assert merged["by_model"]["gpt-4o"]["input_tokens"] == 1800
        assert merged["by_model"]["gpt-4o"]["output_tokens"] == 900
        assert len(merged["runs"]) == 2

    def test_merge_different_models_creates_separate_entries(self):
        """Escalation chain: quick used gpt-4o-mini, then standard used gpt-4o."""
        r1 = self._single_record(model="gpt-4o-mini", input_tokens=500, cost_usd=0.002)
        r2 = self._single_record(model="gpt-4o", input_tokens=2000, cost_usd=0.020)

        merged = Orchestrator._merge_cost_records(r1, r2)

        assert "gpt-4o-mini" in merged["by_model"]
        assert "gpt-4o" in merged["by_model"]
        assert merged["by_model"]["gpt-4o-mini"]["input_tokens"] == 500
        assert merged["by_model"]["gpt-4o"]["input_tokens"] == 2000
        assert merged["total_input_tokens"] == 2500
        assert len(merged["runs"]) == 2

    def test_three_runs_accumulate_correctly(self):
        """Three escalated runs: quick → standard → deep."""
        r1 = self._single_record(model="gpt-4o-mini", input_tokens=300, cost_usd=0.001)
        r2 = self._single_record(model="gpt-4o", input_tokens=1000, cost_usd=0.010)
        r3 = self._single_record(model="gpt-4o", input_tokens=2000, cost_usd=0.020)

        merged_12 = Orchestrator._merge_cost_records(r1, r2)
        merged_all = Orchestrator._merge_cost_records(merged_12, r3)

        assert merged_all["total_input_tokens"] == 3300
        assert abs(merged_all["total_cost_usd"] - 0.031) < 1e-6
        # gpt-4o entry should have sum of r2 + r3
        assert merged_all["by_model"]["gpt-4o"]["input_tokens"] == 3000
        assert len(merged_all["runs"]) == 3

    def test_runs_list_preserved_in_order(self):
        """Earlier run should be first in the runs list."""
        r1 = self._single_record()
        r2 = self._single_record(cost_usd=0.5)
        r2["runs"][0]["recorded_at"] = "2024-01-02T00:00:00+00:00"

        merged = Orchestrator._merge_cost_records(r1, r2)
        assert merged["runs"][0]["recorded_at"] == "2024-01-01T00:00:00+00:00"
        assert merged["runs"][1]["recorded_at"] == "2024-01-02T00:00:00+00:00"


# ---------------------------------------------------------------------------
# _write_task_cost_record
# ---------------------------------------------------------------------------

class TestWriteTaskCostRecord:
    """Tests for the metadata persistence method."""

    def test_writes_cost_into_metadata(self, tmp_path):
        """Happy path: cost record written into issue metadata."""
        provider = _make_provider(model="gpt-4o")
        profile = _make_profile(name="standard", model="gpt-4o")
        orch = _make_orchestrator(tmp_path, providers=[provider])
        orch.config.agent_profiles = [profile]

        session = _make_live_session(input_tokens=1000, output_tokens=500)
        issue = _make_issue("abc-001")
        entry = _make_running_entry(
            identifier="abc-001", profile_name="standard",
            session=session, issue=issue,
        )

        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {}
        orch._project_trackers["__legacy__"] = mock_tracker
        orch.tracker = mock_tracker

        orch._write_task_cost_record(entry)

        mock_tracker.get_metadata.assert_called_once_with("abc-001")
        mock_tracker.set_metadata_field.assert_called_once()
        args = mock_tracker.set_metadata_field.call_args.args
        assert args[0] == "abc-001"
        assert args[1] == "oompah.task_costs"
        costs = args[2]
        assert costs["total_input_tokens"] == 1000
        assert costs["total_output_tokens"] == 500
        assert "gpt-4o" in costs["by_model"]

    def test_merges_with_existing_cost_record(self, tmp_path):
        """Second run should accumulate into the existing oompah.task_costs."""
        provider = _make_provider(model="gpt-4o")
        profile = _make_profile(name="standard", model="gpt-4o")
        orch = _make_orchestrator(tmp_path, providers=[provider])
        orch.config.agent_profiles = [profile]

        # Existing cost record in metadata (from first run)
        existing_costs = {
            "total_input_tokens": 500,
            "total_output_tokens": 200,
            "total_cost_usd": 0.005,
            "by_model": {
                "gpt-4o": {
                    "input_tokens": 500,
                    "output_tokens": 200,
                    "cost_usd": 0.005,
                }
            },
            "runs": [{"profile": "quick", "model": "gpt-4o", "input_tokens": 500,
                      "output_tokens": 200, "cost_usd": 0.005, "recorded_at": "2024-01-01T00:00:00+00:00"}],
        }

        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {"oompah.task_costs": existing_costs}
        orch.tracker = mock_tracker

        session = _make_live_session(input_tokens=1000, output_tokens=500)
        issue = _make_issue("abc-001")
        entry = _make_running_entry(
            identifier="abc-001", profile_name="standard",
            session=session, issue=issue,
        )

        orch._write_task_cost_record(entry)

        mock_tracker.set_metadata_field.assert_called_once()
        costs = mock_tracker.set_metadata_field.call_args.args[2]

        # Should have accumulated: 500+1000=1500 input, 200+500=700 output
        assert costs["total_input_tokens"] == 1500
        assert costs["total_output_tokens"] == 700
        # Two runs in the history
        assert len(costs["runs"]) == 2

    def test_no_session_skips_write(self, tmp_path):
        """Entry with no session produces no metadata writes."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry(session=None)

        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        orch._write_task_cost_record(entry)

        mock_tracker.get_metadata.assert_not_called()
        mock_tracker.set_metadata_field.assert_not_called()

    def test_zero_tokens_skips_write(self, tmp_path):
        """Entry with zero tokens produces no metadata writes."""
        orch = _make_orchestrator(tmp_path)
        session = _make_live_session(input_tokens=0, output_tokens=0, total_tokens=0)
        entry = _make_running_entry(session=session)

        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        orch._write_task_cost_record(entry)

        mock_tracker.get_metadata.assert_not_called()
        mock_tracker.set_metadata_field.assert_not_called()

    def test_tracker_error_on_show_still_writes(self, tmp_path):
        """If metadata read fails, we still attempt the write."""
        provider = _make_provider(model="gpt-4o")
        profile = _make_profile(name="standard", model="gpt-4o")
        orch = _make_orchestrator(tmp_path, providers=[provider])
        orch.config.agent_profiles = [profile]

        from oompah.tracker import TrackerError
        mock_tracker = MagicMock()
        mock_tracker.get_metadata.side_effect = TrackerError("metadata read failed")
        orch.tracker = mock_tracker

        session = _make_live_session(input_tokens=100, output_tokens=50)
        issue = _make_issue("abc-001")
        entry = _make_running_entry(session=session, issue=issue)

        # Should not raise
        orch._write_task_cost_record(entry)
        mock_tracker.set_metadata_field.assert_called_once()

    def test_tracker_error_on_update_is_swallowed(self, tmp_path):
        """If metadata write fails, exception is logged but not propagated."""
        from oompah.tracker import TrackerError
        orch = _make_orchestrator(tmp_path)

        mock_tracker = MagicMock()
        mock_tracker.get_metadata.return_value = {}
        mock_tracker.set_metadata_field.side_effect = TrackerError(
            "metadata update failed"
        )
        orch.tracker = mock_tracker

        session = _make_live_session(input_tokens=100, output_tokens=50)
        issue = _make_issue("abc-001")
        entry = _make_running_entry(session=session, issue=issue)

        # Should not raise
        orch._write_task_cost_record(entry)

    def test_unexpected_exception_is_swallowed(self, tmp_path):
        """Any unexpected exception in cost writing is swallowed."""
        orch = _make_orchestrator(tmp_path)

        mock_tracker = MagicMock()
        mock_tracker.get_metadata.side_effect = RuntimeError("unexpected crash")
        orch.tracker = mock_tracker

        session = _make_live_session(input_tokens=100, output_tokens=50)
        issue = _make_issue("abc-001")
        entry = _make_running_entry(session=session, issue=issue)

        # Should not raise
        orch._write_task_cost_record(entry)


# ---------------------------------------------------------------------------
# _fire_task_cost_record (non-blocking)
# ---------------------------------------------------------------------------

class TestFireTaskCostRecord:
    """Tests that fire_task_cost_record is non-blocking."""

    def test_fire_submits_to_thread_pool(self, tmp_path):
        """_fire_task_cost_record must submit work to the thread pool, not call synchronously."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry()

        submitted = []
        original_submit = orch._tick_pool.submit

        def tracking_submit(fn, *args, **kwargs):
            submitted.append((fn, args))
            return original_submit(fn, *args, **kwargs)

        orch._tick_pool.submit = tracking_submit

        orch._fire_task_cost_record(entry)

        assert len(submitted) == 1
        fn, args = submitted[0]
        assert fn == orch._write_task_cost_record
        assert args == (entry,)

    def test_fire_does_not_block(self, tmp_path):
        """_fire_task_cost_record returns immediately even if writing is slow."""
        orch = _make_orchestrator(tmp_path)

        write_started = threading.Event()
        write_done = threading.Event()

        slow_writes = []

        original_write = orch._write_task_cost_record

        def slow_write(entry):
            write_started.set()
            write_done.wait(timeout=5)  # wait until test says go
            slow_writes.append(entry)

        orch._write_task_cost_record = slow_write

        entry = _make_running_entry()
        start_time = __import__("time").monotonic()
        orch._fire_task_cost_record(entry)
        elapsed = __import__("time").monotonic() - start_time

        # The submit itself should be near-instant
        assert elapsed < 1.0, f"_fire_task_cost_record took {elapsed:.2f}s — it's blocking!"

        # Signal the slow write to complete
        write_done.set()

    def test_fire_survives_pool_full_exception(self, tmp_path):
        """If submitting to the pool raises, _fire must not propagate the exception."""
        orch = _make_orchestrator(tmp_path)
        entry = _make_running_entry()

        def failing_submit(fn, *args, **kwargs):
            raise RuntimeError("pool is shut down")

        orch._tick_pool.submit = failing_submit

        # Should not raise
        orch._fire_task_cost_record(entry)


# ---------------------------------------------------------------------------
# Integration: on_worker_exit calls fire_task_cost_record
# ---------------------------------------------------------------------------

class TestOnWorkerExitWritesCostRecord:
    """Integration tests: cost record fires on every worker exit path."""

    def _make_orchestrator_with_entry(self, tmp_path, issue_id="test-001"):
        orch = _make_orchestrator(tmp_path)
        session = _make_live_session(input_tokens=1000, output_tokens=500)
        issue = _make_issue(issue_id)
        entry = RunningEntry(
            worker_task=MagicMock(),
            identifier=issue_id,
            issue=issue,
            session=session,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="standard",
        )
        orch.state.running[issue_id] = entry
        return orch, entry

    def test_normal_exit_fires_cost_record(self, tmp_path):
        """Agent completes normally → cost record written."""
        orch, entry = self._make_orchestrator_with_entry(tmp_path)
        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        # Patch tracker to prevent actual tracker calls
        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = _make_issue("test-001", state="closed")
        orch.tracker = mock_tracker

        asyncio.run(orch._on_worker_exit("test-001", "normal", None))

        assert len(fire_calls) == 1
        assert fire_calls[0] is entry

    def test_stalled_exit_fires_cost_record(self, tmp_path):
        """Agent stalled → cost record written before retry scheduled."""
        orch, entry = self._make_orchestrator_with_entry(tmp_path)
        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._on_worker_exit("test-001", "stalled", "no progress"))

        assert len(fire_calls) == 1
        assert fire_calls[0] is entry

    def test_max_turns_exit_fires_cost_record(self, tmp_path):
        """Agent hit max turns → cost record written."""
        orch, entry = self._make_orchestrator_with_entry(tmp_path)
        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._on_worker_exit("test-001", "max_turns", None))

        assert len(fire_calls) == 1

    def test_abnormal_exit_fires_cost_record(self, tmp_path):
        """Agent failed with an error → cost record written."""
        orch, entry = self._make_orchestrator_with_entry(tmp_path)
        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._on_worker_exit("test-001", "abnormal", "some error"))

        assert len(fire_calls) == 1

    def test_rate_limited_exit_fires_cost_record(self, tmp_path):
        """Agent rate-limited → cost record written before retry scheduled."""
        orch, entry = self._make_orchestrator_with_entry(tmp_path)
        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._on_worker_exit("test-001", "rate_limited", "HTTP 429"))

        assert len(fire_calls) == 1

    def test_ask_question_exit_fires_cost_record(self, tmp_path):
        """Agent asked a question → issue transitions out of in_progress → cost IS recorded.

        The ask_question path moves the issue from in_progress → open,
        which IS a transition out of in_progress, so cost is recorded per spec.
        """
        orch, entry = self._make_orchestrator_with_entry(tmp_path)
        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        asyncio.run(orch._on_worker_exit("test-001", "ask_question", "What should I do?"))

        # ask_question transitions out of in_progress — cost record IS written
        assert len(fire_calls) == 1
        assert fire_calls[0] is entry

    def test_unknown_issue_id_no_crash(self, tmp_path):
        """If the issue_id is not in running, exit is a no-op (no crash)."""
        orch = _make_orchestrator(tmp_path)
        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._on_worker_exit("nonexistent", "normal", None))

        assert len(fire_calls) == 0


# ---------------------------------------------------------------------------
# Integration: _terminate_running writes cost before dropping entry
# ---------------------------------------------------------------------------

class TestTerminateRunningWritesCostRecord:
    """Mid-flight termination paths also persist cost data."""

    def _make_orchestrator_with_running(self, tmp_path, issue_id="test-001"):
        orch = _make_orchestrator(tmp_path)
        session = _make_live_session(input_tokens=800, output_tokens=300)
        issue = _make_issue(issue_id)
        task = MagicMock()
        task.done.return_value = True  # already done — no cancel needed
        entry = RunningEntry(
            worker_task=task,
            identifier=issue_id,
            issue=issue,
            session=session,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="standard",
        )
        orch.state.running[issue_id] = entry
        return orch, entry

    def test_terminate_fires_cost_record(self, tmp_path):
        """_terminate_running writes cost before dropping the entry."""
        orch, entry = self._make_orchestrator_with_running(tmp_path)
        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._terminate_running("test-001", cleanup_workspace=False))

        assert len(fire_calls) == 1
        assert fire_calls[0] is entry

    def test_terminate_fires_cost_before_workspace_cleanup(self, tmp_path):
        """Cost record must be written before workspace is removed
        (so entry still holds the session token data at write time)."""
        orch, entry = self._make_orchestrator_with_running(tmp_path)

        call_order = []
        orch._fire_task_cost_record = lambda e: call_order.append("cost")
        orch.workspace_mgr.remove_workspace = MagicMock(
            side_effect=lambda _: call_order.append("workspace")
        )

        asyncio.run(orch._terminate_running("test-001", cleanup_workspace=True))

        assert "cost" in call_order
        # Cost must appear before workspace removal (or workspace may not be called
        # if no project_id, but cost must still be first)
        if "workspace" in call_order:
            assert call_order.index("cost") < call_order.index("workspace")

    def test_terminate_with_no_entry_does_not_crash(self, tmp_path):
        """Terminating a non-existent issue is a no-op."""
        orch = _make_orchestrator(tmp_path)
        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._terminate_running("nonexistent", cleanup_workspace=False))

        assert len(fire_calls) == 0

    def test_terminate_does_not_wait_forever_for_cancelled_worker(self, tmp_path):
        """A cancellation-resistant worker cannot wedge service shutdown."""
        orch = _make_orchestrator(tmp_path)
        orch.config.worker_termination_timeout_ms = 10

        async def _ignores_first_cancel():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                await asyncio.sleep(0.1)

        async def _run():
            task = asyncio.create_task(_ignores_first_cancel())
            entry = _make_running_entry("stuck-worker")
            entry.worker_task = task
            orch.state.running["stuck-worker"] = entry
            started = asyncio.get_running_loop().time()
            await orch._terminate_running("stuck-worker", cleanup_workspace=False)
            return asyncio.get_running_loop().time() - started

        elapsed = asyncio.run(_run())

        assert elapsed < 0.08
        assert "stuck-worker" not in orch.state.running


# ---------------------------------------------------------------------------
# Acceptance: reconcile-triggered termination writes cost
# ---------------------------------------------------------------------------

class TestReconcileTriggeredCostRecord:
    """When reconcile detects issue no longer in_progress, cost is recorded."""

    def test_terminal_state_in_reconcile_writes_cost(self, tmp_path):
        """Issue moved to closed by user → reconcile terminates → cost written."""
        orch = _make_orchestrator(tmp_path)

        session = _make_live_session(input_tokens=600, output_tokens=200)
        issue = _make_issue("abc-001", state="in_progress")
        task = MagicMock()
        task.done.return_value = True
        entry = RunningEntry(
            worker_task=task,
            identifier="abc-001",
            issue=issue,
            session=session,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="standard",
        )
        orch.state.running["abc-001"] = entry

        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        # Simulate reconcile detecting terminal state
        asyncio.run(orch._terminate_running("abc-001", cleanup_workspace=True))

        assert len(fire_calls) == 1
        assert fire_calls[0] is entry

    def test_moved_to_open_in_reconcile_writes_cost(self, tmp_path):
        """Issue dragged to open by user → reconcile terminates → cost written."""
        orch = _make_orchestrator(tmp_path)

        session = _make_live_session(input_tokens=300, output_tokens=100)
        issue = _make_issue("abc-002", state="in_progress")
        task = MagicMock()
        task.done.return_value = True
        entry = RunningEntry(
            worker_task=task,
            identifier="abc-002",
            issue=issue,
            session=session,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="standard",
        )
        orch.state.running["abc-002"] = entry

        fire_calls = []
        orch._fire_task_cost_record = lambda e: fire_calls.append(e)

        asyncio.run(orch._terminate_running("abc-002", cleanup_workspace=False))

        assert len(fire_calls) == 1


# ---------------------------------------------------------------------------
# Acceptance: multi-run escalation records accumulate
# ---------------------------------------------------------------------------

class TestMultiRunAccumulation:
    """Multi-run with escalation: two model entries summed in the record."""

    def test_two_runs_accumulate_by_model(self, tmp_path):
        """Simulate quick → standard escalation: record shows both models."""
        provider = _make_provider(model="gpt-4o")
        profile_quick = _make_profile(name="quick", model="gpt-4o-mini")
        profile_standard = _make_profile(name="standard", model="gpt-4o")

        # Add gpt-4o-mini costs to provider
        provider.models = ["gpt-4o", "gpt-4o-mini"]
        provider.model_costs["gpt-4o-mini"] = {
            "cost_per_1k_input": 0.00015,
            "cost_per_1k_output": 0.0006,
        }

        orch = _make_orchestrator(tmp_path, providers=[provider])
        orch.config.agent_profiles = [profile_quick, profile_standard]

        # First run: quick with gpt-4o-mini, 500 input 200 output
        session1 = _make_live_session(input_tokens=500, output_tokens=200)
        issue = _make_issue("abc-003")
        entry1 = _make_running_entry(
            identifier="abc-003", profile_name="quick",
            session=session1, issue=issue,
        )
        record1 = orch._compute_run_cost_record(entry1)
        assert record1 is not None
        assert "gpt-4o-mini" in record1["by_model"]

        # Second run: standard with gpt-4o, 2000 input 800 output
        session2 = _make_live_session(input_tokens=2000, output_tokens=800)
        entry2 = _make_running_entry(
            identifier="abc-003", profile_name="standard",
            session=session2, issue=issue,
        )
        record2 = orch._compute_run_cost_record(entry2)
        assert record2 is not None
        assert "gpt-4o" in record2["by_model"]

        # Merge
        merged = Orchestrator._merge_cost_records(record1, record2)

        # Both models present
        assert "gpt-4o-mini" in merged["by_model"]
        assert "gpt-4o" in merged["by_model"]
        # Total across models
        assert merged["total_input_tokens"] == 2500
        assert merged["total_output_tokens"] == 1000
        assert len(merged["runs"]) == 2

    def test_write_merges_with_existing_metadata_across_runs(self, tmp_path):
        """Simulate two _write_task_cost_record calls on the same issue
        to verify the second call reads and merges the first call's output."""
        provider = _make_provider(model="gpt-4o", cost_per_1k_input=0.005, cost_per_1k_output=0.015)
        profile = _make_profile(name="standard", model="gpt-4o")
        orch = _make_orchestrator(tmp_path, providers=[provider])
        orch.config.agent_profiles = [profile]

        # Use a real in-memory metadata store to simulate sequential writes
        metadata_store: dict[str, dict] = {}

        mock_tracker = MagicMock()
        mock_tracker.get_metadata.side_effect = (
            lambda identifier: metadata_store.get(identifier, {})
        )
        mock_tracker.set_metadata_field.side_effect = (
            lambda identifier, key, value: metadata_store.setdefault(
                identifier, {}
            ).__setitem__(key, value)
        )
        orch.tracker = mock_tracker

        issue = _make_issue("abc-004")

        # First write: 1000 input, 500 output
        session1 = _make_live_session(input_tokens=1000, output_tokens=500)
        entry1 = _make_running_entry(
            identifier="abc-004", profile_name="standard",
            session=session1, issue=issue,
        )
        orch._write_task_cost_record(entry1)

        # Second write: 800 input, 300 output
        session2 = _make_live_session(input_tokens=800, output_tokens=300)
        entry2 = _make_running_entry(
            identifier="abc-004", profile_name="standard",
            session=session2, issue=issue,
        )
        orch._write_task_cost_record(entry2)

        # Check accumulated result
        final_meta = metadata_store.get("abc-004", {})
        costs = final_meta.get("oompah.task_costs", {})
        assert costs["total_input_tokens"] == 1800
        assert costs["total_output_tokens"] == 800
        assert len(costs["runs"]) == 2
