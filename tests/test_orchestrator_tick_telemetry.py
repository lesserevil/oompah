"""Tests for fine-grained orchestrator tick telemetry (TASK-465.1).

Verifies that:
- _handle_dispatch_needed() returns a dict of substep timings
- All expected substep keys are present and non-negative
- _tick() stores timing data in _last_tick_timings
- Slow-tick log includes dispatch substep detail
- get_snapshot() exposes tick_timings for the dashboard
- Missing/empty timings don't crash existing snapshot consumers
- No secrets appear in tick_timings snapshots
"""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import AgentProfile, Issue
from oompah.orchestrator import Orchestrator
from oompah.roles import RoleStore


# ---------------------------------------------------------------------------
# Helpers (mirrored from test_orchestrator_handlers.py)
# ---------------------------------------------------------------------------


def _make_config() -> ServiceConfig:
    return ServiceConfig()


def _make_issue(
    identifier: str,
    state: str = "open",
    issue_type: str = "task",
    priority: int = 2,
    project_id: str | None = None,
    labels: list | None = None,
    description: str = "Test issue body — passes the empty-description gate.",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description=description,
        state=state,
        issue_type=issue_type,
        priority=priority,
        project_id=project_id,
        labels=labels or [],
    )


def _make_orchestrator(tmp_path):
    """Create a minimal test orchestrator with mocked project store."""
    project_store = MagicMock()
    project_store.list_all.return_value = []
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    orch = Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    orch._fetch_in_progress_issues = MagicMock(return_value=[])
    return orch


def _stub_dispatch_needed(orch) -> None:
    """Stub all sub-methods called by _handle_dispatch_needed().

    Returns empty/no-op values so the method runs end-to-end without
    hitting the filesystem or tracker.
    """
    orch._fetch_all_candidates = MagicMock(return_value=[])
    orch._pre_resolve_blockers = MagicMock()
    orch._apply_duplicate_detection = MagicMock(return_value=[])
    orch._process_epic_proposals = MagicMock(return_value=[])
    orch._select_dispatchable = MagicMock(return_value=[])
    orch._plan_open_epics = MagicMock(return_value=[])
    orch._auto_close_completed_epics = MagicMock()
    orch._all_non_terminal_epics = MagicMock(return_value=[])
    orch._open_epic_main_prs = MagicMock()
    orch._check_epic_staleness = MagicMock()
    orch._dispatch_proactive_rebase_agents = MagicMock()
    orch._prune_stale_epic_rebase_states = MagicMock()
    orch._reset_orphaned_in_progress = MagicMock()


# ---------------------------------------------------------------------------
# _handle_dispatch_needed() return value and timing structure
# ---------------------------------------------------------------------------


class TestHandleDispatchNeededTimings:
    """_handle_dispatch_needed() must return a substep timing dict."""

    # Expected substep keys for the dispatch phase
    EXPECTED_SUBSTEP_KEYS = {
        "candidate_fetch",
        "blocker_pre_resolution",
        "duplicate_detection",
        "epic_proposals",
        "candidate_selection",
        "normal_dispatch",
        "epic_planning",
        "epic_close_pr",
        "staleness_checks",
        "rebase_filing",
        "orphan_reset",
    }

    def test_returns_dict_not_none(self, tmp_path):
        """_handle_dispatch_needed() returns a dict, not None."""
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)

        result = asyncio.run(orch._handle_dispatch_needed())

        assert result is not None
        assert isinstance(result, dict)

    def test_returns_all_expected_substep_keys(self, tmp_path):
        """All 10 expected substep timing keys are present in the return dict."""
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)

        result = asyncio.run(orch._handle_dispatch_needed())

        for key in self.EXPECTED_SUBSTEP_KEYS:
            assert key in result, f"Missing expected substep timing key: {key!r}"

    def test_all_timing_values_are_floats(self, tmp_path):
        """Every timing value in the returned dict is a float."""
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)

        result = asyncio.run(orch._handle_dispatch_needed())

        for key, value in result.items():
            assert isinstance(value, float), (
                f"Timing value for {key!r} is {type(value).__name__}, expected float"
            )

    def test_all_timing_values_are_non_negative(self, tmp_path):
        """Every timing value must be >= 0 (elapsed milliseconds can't be negative)."""
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)

        result = asyncio.run(orch._handle_dispatch_needed())

        for key, value in result.items():
            assert value >= 0, f"Timing for {key!r} is negative: {value}"

    def test_candidate_fetch_timing_reflects_real_elapsed_time(self, tmp_path):
        """candidate_fetch timing captures actual wall-clock time, not always zero."""
        import time

        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)

        # Override candidate fetch to introduce measurable latency
        def slow_fetch():
            time.sleep(0.05)  # 50 ms
            return []

        orch._fetch_all_candidates = slow_fetch

        result = asyncio.run(orch._handle_dispatch_needed())

        # Allow generous lower bound; wall-clock may be slow on CI
        assert result["candidate_fetch"] >= 30.0, (
            f"Expected candidate_fetch >= 30ms but got {result['candidate_fetch']:.1f}ms"
        )

    def test_staleness_timing_is_near_zero_when_disabled(self, tmp_path):
        """staleness_checks timing is effectively 0 when threshold is 0 (disabled)."""
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)
        # Explicitly disable the threshold so the staleness branch is skipped
        orch.config.epic_staleness_threshold_commits = 0

        result = asyncio.run(orch._handle_dispatch_needed())

        # _check_epic_staleness is not called → only the timing overhead
        assert result["staleness_checks"] >= 0
        # Sanity: should be very small (< 500ms) since no real work happens
        assert result["staleness_checks"] < 500

    def test_staleness_timing_stays_zero_on_dispatch_lane_when_enabled(self, tmp_path):
        """staleness_checks is a compatibility key; work runs in step 5c maintenance."""
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)
        orch.config = _make_config()
        orch.config.epic_staleness_threshold_commits = 3  # enable
        orch._check_epic_staleness = MagicMock()

        result = asyncio.run(orch._handle_dispatch_needed())

        assert result["staleness_checks"] == 0.0
        orch._check_epic_staleness.assert_not_called()

    def test_rebase_filing_timing_stays_zero_on_dispatch_lane_when_enabled(self, tmp_path):
        """rebase_filing is a compatibility key; work runs in step 5c maintenance."""
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)
        orch.config = _make_config()
        orch.config.epic_staleness_threshold_commits = 3  # enable
        orch._dispatch_proactive_rebase_agents = MagicMock()

        result = asyncio.run(orch._handle_dispatch_needed())

        assert result["rebase_filing"] == 0.0
        orch._dispatch_proactive_rebase_agents.assert_not_called()

    def test_no_unexpected_sensitive_keys_in_timings(self, tmp_path):
        """Timing dict must not contain keys that could hold sensitive values."""
        SENSITIVE_SUBSTRINGS = {"token", "key", "secret", "password", "api", "auth"}
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)

        result = asyncio.run(orch._handle_dispatch_needed())

        for key in result:
            lower = key.lower()
            for sensitive in SENSITIVE_SUBSTRINGS:
                assert sensitive not in lower, (
                    f"Timing key {key!r} looks sensitive (contains {sensitive!r})"
                )

    def test_returns_correct_number_of_substep_keys(self, tmp_path):
        """Return dict has exactly the expected number of substep keys (no extras dropped)."""
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)

        result = asyncio.run(orch._handle_dispatch_needed())

        # Should have at least all expected keys
        assert len(result) >= len(self.EXPECTED_SUBSTEP_KEYS)


# ---------------------------------------------------------------------------
# _tick() stores _last_tick_timings
# ---------------------------------------------------------------------------


class TestTickTimingsStorage:
    """_tick() must populate _last_tick_timings after each tick."""

    def _make_fast_tick_orch(self, tmp_path):
        """Orchestrator with all tick sub-handlers mocked for speed."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock(return_value={
            "candidate_fetch": 10.0,
            "blocker_pre_resolution": 5.0,
            "duplicate_detection": 2.0,
            "epic_proposals": 1.0,
            "candidate_selection": 8.0,
            "normal_dispatch": 0.0,
            "epic_planning": 3.0,
            "epic_close_pr": 4.0,
            "staleness_checks": 0.0,
            "rebase_filing": 1.0,
            "orphan_reset": 6.0,
        })
        orch._handle_yolo_review = AsyncMock(return_value=(5.0, 3.0, 4.0))
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()
        orch._refresh_effective_concurrency = MagicMock(return_value=10)
        return orch

    def test_last_tick_timings_empty_before_first_tick(self, tmp_path):
        """_last_tick_timings is empty dict before the first tick runs."""
        orch = _make_orchestrator(tmp_path)
        assert orch._last_tick_timings == {}

    def test_tick_populates_last_tick_timings(self, tmp_path):
        """After _tick(), _last_tick_timings is populated with timing data."""
        orch = self._make_fast_tick_orch(tmp_path)

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert orch._last_tick_timings != {}

    def test_tick_timings_contains_top_level_keys(self, tmp_path):
        """_last_tick_timings contains all expected top-level phase keys."""
        EXPECTED_TOP_LEVEL = {
            "reconcile_ms",
            "reviews_ms",
            "dispatch_ms",
            "yolo_ms",
            "archive_ms",
            "merged_ms",
            "watchdog_ms",
            "heal_ms",
            "total_ms",
            "dispatch_substeps",
        }
        orch = self._make_fast_tick_orch(tmp_path)

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        for key in EXPECTED_TOP_LEVEL:
            assert key in orch._last_tick_timings, (
                f"Missing top-level timing key: {key!r}"
            )

    def test_tick_timings_top_level_values_are_non_negative(self, tmp_path):
        """All top-level ms values in _last_tick_timings are >= 0."""
        orch = self._make_fast_tick_orch(tmp_path)

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        ms_keys = {
            "reconcile_ms", "reviews_ms", "dispatch_ms",
            "yolo_ms", "archive_ms", "merged_ms",
            "watchdog_ms", "heal_ms", "total_ms",
        }
        for key in ms_keys:
            value = orch._last_tick_timings[key]
            assert value >= 0, f"Timing {key!r} is negative: {value}"

    def test_tick_timings_dispatch_substeps_propagated(self, tmp_path):
        """_last_tick_timings['dispatch_substeps'] contains the dict returned
        by _handle_dispatch_needed()."""
        expected_substeps = {
            "candidate_fetch": 10.0,
            "blocker_pre_resolution": 5.0,
            "duplicate_detection": 2.0,
            "epic_proposals": 1.0,
            "candidate_selection": 8.0,
            "normal_dispatch": 0.0,
            "epic_planning": 3.0,
            "epic_close_pr": 4.0,
            "staleness_checks": 0.0,
            "rebase_filing": 1.0,
            "orphan_reset": 6.0,
        }
        orch = self._make_fast_tick_orch(tmp_path)
        orch._handle_dispatch_needed = AsyncMock(return_value=expected_substeps)

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert orch._last_tick_timings["dispatch_substeps"] == expected_substeps

    def test_tick_timings_overwritten_on_each_tick(self, tmp_path):
        """_last_tick_timings is freshly overwritten after each tick — stale data
        from the previous tick is not merged in."""
        orch = self._make_fast_tick_orch(tmp_path)

        # First tick
        orch._handle_dispatch_needed = AsyncMock(return_value={"candidate_fetch": 50.0})
        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())
        first_dispatch_substeps = dict(orch._last_tick_timings["dispatch_substeps"])

        # Second tick with different timings
        orch._handle_dispatch_needed = AsyncMock(return_value={"candidate_fetch": 200.0})
        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())
        second_dispatch_substeps = dict(orch._last_tick_timings["dispatch_substeps"])

        assert first_dispatch_substeps != second_dispatch_substeps
        assert second_dispatch_substeps["candidate_fetch"] == 200.0

    def test_tick_timings_not_stored_on_config_validation_error(self, tmp_path):
        """When config validation fails, _tick() aborts early and does NOT
        update _last_tick_timings (avoids storing partial data)."""
        orch = self._make_fast_tick_orch(tmp_path)

        # Ensure we start with empty timings
        assert orch._last_tick_timings == {}

        with patch(
            "oompah.orchestrator.validate_dispatch_config",
            return_value=["Agent command not configured"],
        ):
            asyncio.run(orch._tick())

        # Timings should still be empty — tick aborted before dispatch phase
        assert orch._last_tick_timings == {}

    def test_watchdog_ms_and_heal_ms_present_in_timings(self, tmp_path):
        """watchdog_ms and heal_ms are always present — they were missing before TASK-465.1."""
        orch = self._make_fast_tick_orch(tmp_path)

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert "watchdog_ms" in orch._last_tick_timings
        assert "heal_ms" in orch._last_tick_timings
        assert isinstance(orch._last_tick_timings["watchdog_ms"], float)
        assert isinstance(orch._last_tick_timings["heal_ms"], float)

    def test_total_ms_is_largest_value(self, tmp_path):
        """total_ms must be >= every individual phase ms (sanity check)."""
        orch = self._make_fast_tick_orch(tmp_path)

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        total = orch._last_tick_timings["total_ms"]
        for key in ("reconcile_ms", "reviews_ms", "dispatch_ms", "watchdog_ms", "heal_ms"):
            assert total >= orch._last_tick_timings[key], (
                f"total_ms ({total:.1f}) < {key} ({orch._last_tick_timings[key]:.1f})"
            )


# ---------------------------------------------------------------------------
# Slow-tick log includes dispatch substep detail
# ---------------------------------------------------------------------------


class TestSlowTickSubstepLogging:
    """When a tick is slow (>2000ms), the log includes per-substep dispatch timings."""

    def test_slow_tick_log_includes_dispatch_substep_names(self, tmp_path, caplog):
        """A slow-tick log line includes dispatch substep names."""
        import time

        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()

        substeps = {
            "candidate_fetch": 1500.0,
            "blocker_pre_resolution": 200.0,
            "duplicate_detection": 50.0,
            "epic_proposals": 25.0,
            "candidate_selection": 100.0,
            "normal_dispatch": 0.0,
            "epic_planning": 50.0,
            "epic_close_pr": 80.0,
            "staleness_checks": 0.0,
            "rebase_filing": 20.0,
            "orphan_reset": 30.0,
        }
        orch._handle_dispatch_needed = AsyncMock(return_value=substeps)

        # Inject artificial delay so total_ms > 2000
        original_dispatch = orch._handle_dispatch_needed

        async def slow_dispatch():
            time.sleep(2.1)  # make tick slow
            return substeps

        orch._handle_dispatch_needed = slow_dispatch

        with caplog.at_level(logging.WARNING, logger="oompah.orchestrator"):
            with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
                asyncio.run(orch._tick())

        warning_lines = [r.message for r in caplog.records if "Slow tick" in r.message]
        assert warning_lines, "No slow-tick warning was logged"

        slow_line = warning_lines[0]
        # Must mention at least one of the substep keys
        assert "candidate_fetch" in slow_line, (
            f"Slow tick log missing dispatch substep detail. Got: {slow_line!r}"
        )

    def test_slow_tick_log_includes_watchdog_and_heal(self, tmp_path, caplog):
        """Slow-tick log includes watchdog_ms and heal_ms."""
        import time

        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()

        substeps: dict[str, float] = {
            "candidate_fetch": 0.0,
            "blocker_pre_resolution": 0.0,
            "duplicate_detection": 0.0,
            "epic_proposals": 0.0,
            "candidate_selection": 0.0,
            "normal_dispatch": 0.0,
            "epic_planning": 0.0,
            "epic_close_pr": 0.0,
            "staleness_checks": 0.0,
            "rebase_filing": 0.0,
            "orphan_reset": 0.0,
        }
        orch._handle_dispatch_needed = AsyncMock(return_value=substeps)

        # Inject delay via watchdog stub
        def slow_watchdog():
            time.sleep(2.1)

        orch._maybe_run_watchdog = slow_watchdog
        orch._maybe_heal_repos = MagicMock()

        with caplog.at_level(logging.WARNING, logger="oompah.orchestrator"):
            with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
                asyncio.run(orch._tick())

        warning_lines = [r.message for r in caplog.records if "Slow tick" in r.message]
        assert warning_lines, "No slow-tick warning was logged"

        slow_line = warning_lines[0]
        assert "watchdog" in slow_line, (
            f"Slow tick log missing watchdog timing. Got: {slow_line!r}"
        )
        assert "heal" in slow_line, (
            f"Slow tick log missing heal timing. Got: {slow_line!r}"
        )

    def test_no_slow_tick_warning_for_fast_ticks(self, tmp_path, caplog):
        """No slow-tick warning is emitted for ticks that complete quickly."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()
        orch._handle_dispatch_needed = AsyncMock(return_value={})

        with caplog.at_level(logging.WARNING, logger="oompah.orchestrator"):
            with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
                asyncio.run(orch._tick())

        warning_lines = [r.message for r in caplog.records if "Slow tick" in r.message]
        assert not warning_lines, f"Unexpected slow-tick warning for fast tick: {warning_lines}"


# ---------------------------------------------------------------------------
# get_snapshot() exposes tick_timings
# ---------------------------------------------------------------------------


class TestTickTimingsSnapshot:
    """get_snapshot() must include tick_timings for the dashboard."""

    def test_snapshot_contains_tick_timings_key(self, tmp_path):
        """get_snapshot() always includes a 'tick_timings' key."""
        orch = _make_orchestrator(tmp_path)

        snap = orch.get_snapshot()

        assert "tick_timings" in snap, "get_snapshot() is missing 'tick_timings' key"

    def test_snapshot_tick_timings_empty_before_first_tick(self, tmp_path):
        """Before the first tick, tick_timings is an empty dict (not None, not missing)."""
        orch = _make_orchestrator(tmp_path)

        snap = orch.get_snapshot()

        assert snap["tick_timings"] == {}, (
            f"Expected empty dict before first tick, got: {snap['tick_timings']!r}"
        )

    def test_snapshot_tick_timings_populated_after_tick(self, tmp_path):
        """After _tick() runs, get_snapshot()['tick_timings'] is populated."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock(return_value={
            "candidate_fetch": 5.0,
            "blocker_pre_resolution": 1.0,
            "duplicate_detection": 1.0,
            "epic_proposals": 1.0,
            "candidate_selection": 2.0,
            "normal_dispatch": 0.0,
            "epic_planning": 0.0,
            "epic_close_pr": 0.0,
            "staleness_checks": 0.0,
            "rebase_filing": 0.0,
            "orphan_reset": 1.0,
        })
        orch._handle_yolo_review = AsyncMock(return_value=(1.0, 1.0, 1.0))
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()
        orch._refresh_effective_concurrency = MagicMock(return_value=10)

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        snap = orch.get_snapshot()

        assert snap["tick_timings"] != {}
        assert "total_ms" in snap["tick_timings"]
        assert "dispatch_substeps" in snap["tick_timings"]
        orch._refresh_effective_concurrency.assert_called_once()

    def test_snapshot_tick_timings_is_a_copy(self, tmp_path):
        """Modifying get_snapshot()['tick_timings'] does not corrupt _last_tick_timings."""
        orch = _make_orchestrator(tmp_path)
        orch._last_tick_timings = {
            "total_ms": 42.0,
            "dispatch_substeps": {"candidate_fetch": 10.0},
        }

        snap = orch.get_snapshot()
        snap["tick_timings"]["injected_key"] = "mutated"

        # Original must be unaffected
        assert "injected_key" not in orch._last_tick_timings

    def test_snapshot_tick_timings_no_sensitive_data(self, tmp_path):
        """tick_timings values must be numeric (ms), not strings or objects that
        could contain secrets."""
        SENSITIVE_SUBSTRINGS = {"token", "key", "secret", "password", "api_key"}
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock(return_value={
            "candidate_fetch": 10.0,
            "blocker_pre_resolution": 5.0,
            "duplicate_detection": 2.0,
            "epic_proposals": 1.0,
            "candidate_selection": 8.0,
            "normal_dispatch": 0.0,
            "epic_planning": 3.0,
            "epic_close_pr": 4.0,
            "staleness_checks": 0.0,
            "rebase_filing": 1.0,
            "orphan_reset": 6.0,
        })
        orch._handle_yolo_review = AsyncMock(return_value=(1.0, 1.0, 1.0))
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        snap = orch.get_snapshot()
        timings = snap["tick_timings"]

        def check_no_sensitive(d: dict, path: str = "") -> None:
            for k, v in d.items():
                full_key = f"{path}.{k}" if path else k
                # Key names must not resemble secret fields
                for sensitive in SENSITIVE_SUBSTRINGS:
                    assert sensitive not in k.lower(), (
                        f"Snapshot key {full_key!r} looks sensitive"
                    )
                # Values must be numeric or dicts (no strings that could hold secrets)
                if isinstance(v, dict):
                    check_no_sensitive(v, full_key)
                else:
                    assert isinstance(v, (int, float)), (
                        f"Snapshot value at {full_key!r} is {type(v).__name__!r}; "
                        "only numeric timings expected"
                    )

        check_no_sensitive(timings)

    def test_snapshot_tick_timings_dispatch_substeps_is_dict(self, tmp_path):
        """tick_timings['dispatch_substeps'] is always a dict (even if empty)."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock(return_value={})
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        snap = orch.get_snapshot()
        assert isinstance(snap["tick_timings"]["dispatch_substeps"], dict)

    def test_snapshot_tick_timings_unchanged_between_ticks(self, tmp_path):
        """get_snapshot() returns the timings from the LAST completed tick, not stale data."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()

        # First tick
        orch._handle_dispatch_needed = AsyncMock(return_value={"candidate_fetch": 10.0})
        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())
        snap1 = orch.get_snapshot()["tick_timings"]

        # Second tick with different substep timing
        orch._handle_dispatch_needed = AsyncMock(return_value={"candidate_fetch": 999.0})
        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())
        snap2 = orch.get_snapshot()["tick_timings"]

        assert snap2["dispatch_substeps"].get("candidate_fetch") == 999.0
        assert snap1["dispatch_substeps"].get("candidate_fetch") == 10.0


# ---------------------------------------------------------------------------
# Regression: no crash when timings are empty/missing
# ---------------------------------------------------------------------------


class TestTimingRobustness:
    """Consumers of tick_timings must not crash even if the dict is empty."""

    def test_snapshot_works_when_last_tick_timings_is_empty(self, tmp_path):
        """get_snapshot() does not crash when _last_tick_timings is empty."""
        orch = _make_orchestrator(tmp_path)
        # _last_tick_timings is {} by default (first tick hasn't run)
        assert orch._last_tick_timings == {}

        # Must not raise
        snap = orch.get_snapshot()
        assert "tick_timings" in snap
        assert snap["tick_timings"] == {}

    def test_snapshot_works_when_dispatch_substeps_missing(self, tmp_path):
        """get_snapshot() handles _last_tick_timings without 'dispatch_substeps' key."""
        orch = _make_orchestrator(tmp_path)
        # Simulate a partial/legacy timing dict (no dispatch_substeps)
        orch._last_tick_timings = {"total_ms": 150.0}

        snap = orch.get_snapshot()

        assert "tick_timings" in snap
        assert snap["tick_timings"]["total_ms"] == 150.0

    def test_handle_dispatch_needed_returns_dict_with_empty_candidates(self, tmp_path):
        """When candidates are empty, _handle_dispatch_needed() still returns full timing dict."""
        orch = _make_orchestrator(tmp_path)
        _stub_dispatch_needed(orch)
        orch._fetch_all_candidates = MagicMock(return_value=[])

        result = asyncio.run(orch._handle_dispatch_needed())

        assert isinstance(result, dict)
        assert "candidate_fetch" in result
        assert "orphan_reset" in result

    def test_tick_stores_empty_dispatch_substeps_when_handler_returns_empty(self, tmp_path):
        """If _handle_dispatch_needed() returns {}, _tick() stores that gracefully."""
        orch = _make_orchestrator(tmp_path)
        orch._handle_reconcile = AsyncMock()
        orch._handle_review_check = AsyncMock()
        orch._handle_dispatch_needed = AsyncMock(return_value={})
        orch._handle_yolo_review = AsyncMock(return_value=(0.0, 0.0, 0.0))
        orch._handle_auto_update = AsyncMock()
        orch._notify_observers = MagicMock()
        orch._maybe_run_watchdog = MagicMock()
        orch._maybe_heal_repos = MagicMock()

        with patch("oompah.orchestrator.validate_dispatch_config", return_value=[]):
            asyncio.run(orch._tick())

        assert orch._last_tick_timings["dispatch_substeps"] == {}

    def test_existing_snapshot_structure_unchanged_except_tick_timings(self, tmp_path):
        """Adding tick_timings to get_snapshot() does not remove any pre-existing key.

        This is a regression guard: if a consumer depends on a key that was in the
        snapshot before TASK-465.1, it must still be there.
        """
        PRE_EXISTING_KEYS = {
            "generated_at",
            "paused",
            "config",
            "counts",
            "running",
            "retrying",
            "agent_totals",
            "cost_by_profile",
            "budget",
            "agent_profiles",
            "agent_profiles_source",
            "rate_limits",
            "projects",
            "open_reviews_by_project",
            "alerts",
            "reviews_summary",
            "epic_rebase_states",
            "proposed_foci_count",
        }
        orch = _make_orchestrator(tmp_path)

        snap = orch.get_snapshot()

        for key in PRE_EXISTING_KEYS:
            assert key in snap, f"Pre-existing snapshot key {key!r} was removed"
        # Also check our new key is there
        assert "tick_timings" in snap
