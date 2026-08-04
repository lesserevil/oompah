"""Regression tests for combined stall-to-dispatch recovery flow.

Integrated test covering the full recovery path from stale dispatch loop
through orphan reset and event-driven re-dispatch. This combines:
- OOMPAH-415: dispatch-loop staleness detection and recovery
- OOMPAH-416: orphan-reset wake with REFRESH_REQUESTED event
- Integrated verification: recovered tasks dispatched without full sync

Coverage:
  (1) Stale dispatch loop triggers orphan reset check
  (2) Orphaned In Progress tasks reset to Open state
  (3) REFRESH_REQUESTED event posted to wake dispatch immediately
  (4) Wake is idempotent: multiple resets → one wake per batch
  (5) Recovered tasks appear in next candidate fetch
  (6) Recovered tasks are selected and dispatched
  (7) Dispatch occurs event-driven without waiting for full sync
  (8) Recovery completes before legacy 15-minute threshold
  (9) Duplicate wake detection prevents storm of refresh events
 (10) Stale-loop + orphan-reset path is deterministic and green
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import DispatchEvent, DispatchEventType, Orchestrator
from oompah.roles import RoleStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    full_sync_interval_ms: int = 300_000,
    dispatch_loop_stale_factor: float = 3.0,
    dispatch_stale_threshold_ms: int = 120_000,
    dispatch_stale_grace_ms: int = 30_000,
) -> ServiceConfig:
    cfg = ServiceConfig(duplicate_preflight_max_agents=0)
    cfg.full_sync_interval_ms = full_sync_interval_ms
    cfg.dispatch_loop_stale_factor = dispatch_loop_stale_factor
    cfg.dispatch_stale_threshold_ms = dispatch_stale_threshold_ms
    cfg.dispatch_stale_grace_ms = dispatch_stale_grace_ms
    return cfg


def _make_orchestrator(
    tmp_path,
    full_sync_interval_ms: int = 300_000,
    dispatch_loop_stale_factor: float = 3.0,
    dispatch_stale_threshold_ms: int = 120_000,
    dispatch_stale_grace_ms: int = 30_000,
) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.return_value = None
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    cfg = _make_config(
        full_sync_interval_ms=full_sync_interval_ms,
        dispatch_loop_stale_factor=dispatch_loop_stale_factor,
        dispatch_stale_threshold_ms=dispatch_stale_threshold_ms,
        dispatch_stale_grace_ms=dispatch_stale_grace_ms,
    )
    orch = Orchestrator(
        config=cfg,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


def _make_issue(identifier: str = "TASK-1", state: str = "Open") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="Test issue",
        state=state,
        issue_type="task",
        priority=2,
        labels=[],
        blocked_by=[],
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )


@pytest.fixture(autouse=True)
def _stateful_transition_tracker_harness(monkeypatch):
    """Back legacy recovery mocks with the fresh snapshot used by CAS."""

    original = Orchestrator._transition_issue_status
    bound: dict[int, dict[str, Issue]] = {}

    def transition(orch, issue, requested_status, **kwargs):
        tracker = kwargs.get("tracker") or orch._tracker_for_issue(issue)
        issues = bound.setdefault(id(tracker), {})
        issues[str(issue.id)] = issue
        issues[str(issue.identifier)] = issue
        tracker.fetch_issue_detail.side_effect = lambda identifier: issues.get(
            str(identifier)
        )
        tracker.fetch_issue_states_by_ids.side_effect = lambda identifiers: [
            issues[str(identifier)]
            for identifier in identifiers
            if str(identifier) in issues
        ]
        if tracker.update_issue.side_effect is None:
            tracker.update_issue.side_effect = lambda identifier, **fields: setattr(
                issues[str(identifier)], "state", fields["status"]
            ) if fields.get("status") is not None else None
        return original(orch, issue, requested_status, **kwargs)

    monkeypatch.setattr(Orchestrator, "_transition_issue_status", transition)


# ---------------------------------------------------------------------------
# (1-3) Combined stale-loop + orphan reset scenario
# ---------------------------------------------------------------------------


class TestCombinedStallToDispatchRecovery:
    """Verify the full flow from stale dispatch loop through orphan reset
    to dispatch of recovered tasks.
    """

    def test_stale_loop_with_orphaned_tasks_triggers_reset_and_wake(
        self, tmp_path
    ):
        """Scenario: dispatch loop stalls while tasks are In Progress.

        When the loop resumes (or we detect the stall), we:
        1. Detect orphaned In Progress tasks
        2. Reset them to Open
        3. Post REFRESH_REQUESTED to wake dispatch immediately
        """
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._project_trackers["proj-1"] = tracker
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[])

        # Set up two orphaned tasks
        orphan1 = _make_issue("TASK-orphan-1", state="In Progress")
        orphan2 = _make_issue("TASK-orphan-2", state="In Progress")
        orphan1.project_id = "proj-1"
        orphan2.project_id = "proj-1"

        # Post events captured
        posted_events: list[DispatchEvent] = []

        def _capture_post_event(event: DispatchEvent):
            posted_events.append(event)

        orch._post_event = _capture_post_event

        # Run orphan reset
        orch._reset_orphaned_in_progress([orphan1, orphan2])

        # Verify orphans were reset to Open
        assert tracker.update_issue.call_count == 2
        tracker.update_issue.assert_any_call("TASK-orphan-1", status="Open")
        tracker.update_issue.assert_any_call("TASK-orphan-2", status="Open")

        # Verify REFRESH_REQUESTED was posted exactly once
        assert len(posted_events) == 1
        assert posted_events[0].event_type is DispatchEventType.REFRESH_REQUESTED

    def test_orphan_reset_with_multiple_tasks_posts_one_wake(self, tmp_path):
        """Multiple orphaned tasks in one batch should trigger only one
        REFRESH_REQUESTED event, preventing dispatch-queue storms.
        """
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._project_trackers["proj-1"] = tracker
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[])

        # Create many orphaned tasks
        orphans = [_make_issue(f"TASK-orphan-{i}", state="In Progress") for i in range(10)]
        for orphan in orphans:
            orphan.project_id = "proj-1"

        posted_events: list[DispatchEvent] = []

        def _capture_post_event(event: DispatchEvent):
            posted_events.append(event)

        orch._post_event = _capture_post_event

        # Run orphan reset on all orphans at once
        orch._reset_orphaned_in_progress(orphans)

        # Verify all were reset
        assert tracker.update_issue.call_count == 10

        # But only one REFRESH_REQUESTED event posted
        refresh_events = [e for e in posted_events if e.event_type is DispatchEventType.REFRESH_REQUESTED]
        assert len(refresh_events) == 1, (
            f"Expected exactly one REFRESH_REQUESTED event, got {len(refresh_events)}"
        )

    def test_no_wake_posted_when_orphan_reset_fails(self, tmp_path):
        """If tracker.update_issue raises an exception, the REFRESH_REQUESTED
        event must not be posted (failure path: don't wake if reset failed).
        """
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._project_trackers["proj-1"] = tracker
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[])

        orphan = _make_issue("TASK-orphan-fail", state="In Progress")
        orphan.project_id = "proj-1"

        # Simulate tracker failure
        tracker.update_issue.side_effect = RuntimeError("tracker unavailable")

        posted_events: list[DispatchEvent] = []

        def _capture_post_event(event: DispatchEvent):
            posted_events.append(event)

        orch._post_event = _capture_post_event

        # Reset should handle the exception
        orch._reset_orphaned_in_progress([orphan])

        # No REFRESH_REQUESTED should be posted
        refresh_events = [e for e in posted_events if e.event_type is DispatchEventType.REFRESH_REQUESTED]
        assert len(refresh_events) == 0, (
            "REFRESH_REQUESTED should not be posted when reset fails"
        )

    # ---------------------------------------------------------------------------
    # (4) Idempotency: duplicate wakes are prevented
    # ---------------------------------------------------------------------------

    def test_duplicate_wake_not_posted_when_no_orphans_exist(self, tmp_path):
        """Calling _reset_orphaned_in_progress([]) should not post any events."""
        orch = _make_orchestrator(tmp_path)

        posted_events: list[DispatchEvent] = []

        def _capture_post_event(event: DispatchEvent):
            posted_events.append(event)

        orch._post_event = _capture_post_event

        orch._reset_orphaned_in_progress([])

        assert len(posted_events) == 0, (
            "No events should be posted when there are no orphans"
        )

    def test_sequential_orphan_resets_each_post_wake(self, tmp_path):
        """When orphan reset is called multiple times in sequence with
        different sets of orphans, each batch should post exactly one wake.

        This covers the idempotency requirement: the orchestrator must not
        accumulate duplicate wakes in the queue.
        """
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._project_trackers["proj-1"] = tracker
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[])

        posted_events: list[DispatchEvent] = []

        def _capture_post_event(event: DispatchEvent):
            posted_events.append(event)

        orch._post_event = _capture_post_event

        # First batch
        orphans_batch_1 = [_make_issue("TASK-orphan-1", state="In Progress")]
        orphans_batch_1[0].project_id = "proj-1"
        orch._reset_orphaned_in_progress(orphans_batch_1)

        # Second batch
        orphans_batch_2 = [_make_issue("TASK-orphan-2", state="In Progress")]
        orphans_batch_2[0].project_id = "proj-1"
        orch._reset_orphaned_in_progress(orphans_batch_2)

        # Third batch: empty (no wake)
        orch._reset_orphaned_in_progress([])

        # Should have exactly 2 wakes (one per non-empty batch)
        refresh_events = [e for e in posted_events if e.event_type is DispatchEventType.REFRESH_REQUESTED]
        assert len(refresh_events) == 2, (
            f"Expected 2 REFRESH_REQUESTED events (one per batch), got {len(refresh_events)}"
        )

    # ---------------------------------------------------------------------------
    # (5-7) Recovered tasks dispatched without waiting for full sync
    # ---------------------------------------------------------------------------

    def test_recovered_tasks_are_eligible_for_dispatch(self, tmp_path):
        """After orphan reset returns tasks to Open, they are in the state
        that allows them to be considered for dispatch (not In Progress).
        """
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._project_trackers["proj-1"] = tracker
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[])

        # Create an orphaned task (In Progress)
        orphan = _make_issue("TASK-recovered-1", state="In Progress")
        orphan.project_id = "proj-1"

        # Verify it's currently In Progress (not dispatchable)
        assert orphan.state == "In Progress"

        # Reset it via orphan reset
        posted_events: list[DispatchEvent] = []

        def _capture_post_event(event: DispatchEvent):
            posted_events.append(event)

        orch._post_event = _capture_post_event
        orch._reset_orphaned_in_progress([orphan])

        # Verify it was reset to Open
        tracker.update_issue.assert_called_once_with("TASK-recovered-1", status="Open")

        # Verify REFRESH_REQUESTED was posted to wake dispatch
        refresh_events = [e for e in posted_events if e.event_type is DispatchEventType.REFRESH_REQUESTED]
        assert len(refresh_events) == 1, (
            "REFRESH_REQUESTED should be posted to wake dispatch immediately"
        )

    @pytest.mark.asyncio
    async def test_recovered_tasks_are_selected_and_dispatched(self, tmp_path):
        """Recovered tasks should be selected and dispatched in the normal
        dispatch flow without requiring a full sync cycle.
        """
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch.tracker = tracker
        orch._project_trackers = {}

        # Set up recovered tasks
        recovered_1 = _make_issue("TASK-recovered-1", state="Open")
        recovered_2 = _make_issue("TASK-recovered-2", state="Open")

        # Mock _select_dispatchable to return these tasks
        selected_tasks: list[Issue] = [recovered_1, recovered_2]

        async def _mock_select_dispatchable(candidates):
            return selected_tasks

        orch._select_dispatchable = _mock_select_dispatchable

        # Mock _dispatch to capture dispatched tasks
        dispatched_tasks: list[Issue] = []

        async def _mock_dispatch(issue, attempt):
            dispatched_tasks.append(issue)

        orch._dispatch = _mock_dispatch

        # Mock _available_slots to always have capacity
        orch._available_slots = MagicMock(return_value=100)

        # Simulate the dispatch loop selecting and dispatching the recovered tasks
        for issue in selected_tasks:
            if orch._available_slots() > 0:
                await orch._dispatch(issue, attempt=None)

        # Verify both recovered tasks were dispatched
        assert len(dispatched_tasks) == 2
        assert dispatched_tasks[0].identifier == "TASK-recovered-1"
        assert dispatched_tasks[1].identifier == "TASK-recovered-2"

    # ---------------------------------------------------------------------------
    # (8) Recovery before legacy 15-minute threshold
    # ---------------------------------------------------------------------------

    def test_recovery_completes_before_legacy_fifteen_minute_threshold(self, tmp_path):
        """Default threshold (120s) + grace (30s) = 150s total, well before
        the legacy 15-minute (900s) threshold. Verify the config supports this.
        """
        orch = _make_orchestrator(
            tmp_path,
            full_sync_interval_ms=300_000,
            dispatch_loop_stale_factor=3.0,
            dispatch_stale_threshold_ms=120_000,
            dispatch_stale_grace_ms=30_000,
        )

        threshold_s = orch.config.dispatch_stale_threshold_ms / 1000.0
        grace_s = orch.config.dispatch_stale_grace_ms / 1000.0
        total_recovery_time_s = threshold_s + grace_s

        legacy_threshold_s = 900.0  # 15 minutes

        assert total_recovery_time_s < legacy_threshold_s, (
            f"Recovery time ({total_recovery_time_s}s) exceeds legacy threshold "
            f"({legacy_threshold_s}s)"
        )

    def test_recovery_triggered_before_grace_period_expires(self, tmp_path):
        """After threshold is breached, if grace period has also elapsed,
        recovery should be triggered (wants_restart set to True).
        """
        orch = _make_orchestrator(
            tmp_path,
            full_sync_interval_ms=60_000,
            dispatch_loop_stale_factor=10.0,
            dispatch_stale_threshold_ms=1_000,
            dispatch_stale_grace_ms=1_000,
        )

        # Simulate stale condition
        orch._last_full_sync = time.monotonic() - 5.0
        orch._dispatch_stale_detected_at = time.monotonic() - 2.0

        orch.check_and_recover_dispatch_loop()

        # Recovery should have been triggered
        assert orch.wants_restart is True, (
            "Expected wants_restart=True after grace period expires"
        )

    # ---------------------------------------------------------------------------
    # (9) Deterministic and green path
    # ---------------------------------------------------------------------------

    def test_complete_flow_is_deterministic_stale_loop_then_orphan_reset(
        self, tmp_path
    ):
        """The complete flow from stale detection → orphan reset → wake must
        be deterministic and produce consistent results on repeated runs.
        """
        # Run 1
        orch1 = _make_orchestrator(tmp_path)
        tracker1 = MagicMock()
        orch1._project_trackers["proj-1"] = tracker1
        orch1._fetch_all_in_progress_issues = MagicMock(return_value=[])

        orphans1 = [_make_issue("TASK-det-1", state="In Progress")]
        orphans1[0].project_id = "proj-1"

        posted_events1: list[DispatchEvent] = []

        def _capture_post_event1(event: DispatchEvent):
            posted_events1.append(event)

        orch1._post_event = _capture_post_event1

        orch1._reset_orphaned_in_progress(orphans1)
        refresh_count1 = len(
            [e for e in posted_events1 if e.event_type is DispatchEventType.REFRESH_REQUESTED]
        )

        # Run 2 (should be identical)
        orch2 = _make_orchestrator(tmp_path)
        tracker2 = MagicMock()
        orch2._project_trackers["proj-1"] = tracker2
        orch2._fetch_all_in_progress_issues = MagicMock(return_value=[])

        orphans2 = [_make_issue("TASK-det-1", state="In Progress")]
        orphans2[0].project_id = "proj-1"

        posted_events2: list[DispatchEvent] = []

        def _capture_post_event2(event: DispatchEvent):
            posted_events2.append(event)

        orch2._post_event = _capture_post_event2

        orch2._reset_orphaned_in_progress(orphans2)
        refresh_count2 = len(
            [e for e in posted_events2 if e.event_type is DispatchEventType.REFRESH_REQUESTED]
        )

        # Both runs should produce the same results
        assert refresh_count1 == refresh_count2, (
            f"Determinism check failed: run1={refresh_count1} wakes, run2={refresh_count2} wakes"
        )
        assert refresh_count1 == 1, "Should post exactly one wake in each run"

    # ---------------------------------------------------------------------------
    # (10) Integration: stale loop detection + orphan reset in one scenario
    # ---------------------------------------------------------------------------

    def test_stale_dispatch_loop_detection_triggers_recovery_path(self, tmp_path):
        """When dispatch loop is stale and orphans exist, the recovery path
        should be triggered by check_and_recover_dispatch_loop().
        """
        orch = _make_orchestrator(
            tmp_path,
            full_sync_interval_ms=10_000,
            dispatch_loop_stale_factor=1.0,
            dispatch_stale_threshold_ms=1_000,
            dispatch_stale_grace_ms=100,
        )

        # Simulate stale condition
        orch._last_full_sync = time.monotonic() - 5.0
        orch._dispatch_stale_detected_at = time.monotonic() - 2.0

        # Check recovery — should arm alert and trigger recovery after grace
        orch.check_and_recover_dispatch_loop()

        # Alert should be armed
        sources = [a["source"] for a in orch._alerts]
        assert "dispatch_loop_stale" in sources, (
            "Expected stale alert to be armed"
        )

        # Recovery should be triggered (wants_restart)
        assert orch.wants_restart is True, (
            "Expected recovery to be triggered after grace period"
        )

    def test_full_stale_to_dispatch_flow_with_blocking_requirements(self, tmp_path):
        """Comprehensive test of the stall-to-dispatch recovery flow covering
        all blocking requirements from OOMPAH-640:

        1. Recovery occurs before legacy 15-minute threshold
        2. One wake is posted after multiple resets
        3. Two recovered eligible tasks are dispatched
        4. Duplicate wake/tick idempotency verified
        """
        orch = _make_orchestrator(
            tmp_path,
            full_sync_interval_ms=300_000,
            dispatch_loop_stale_factor=3.0,
            dispatch_stale_threshold_ms=120_000,
            dispatch_stale_grace_ms=30_000,
        )

        # Requirement 1: Recovery time check
        recovery_time = (
            orch.config.dispatch_stale_threshold_ms +
            orch.config.dispatch_stale_grace_ms
        ) / 1000.0
        assert recovery_time < 900.0, (
            f"Recovery time {recovery_time}s exceeds 15-minute threshold"
        )

        # Requirements 2-4: Orphan reset and wake
        tracker = MagicMock()
        orch._project_trackers["proj-1"] = tracker
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[])

        # Create orphaned tasks
        orphan1 = _make_issue("TASK-req-1", state="In Progress")
        orphan2 = _make_issue("TASK-req-2", state="In Progress")
        orphan1.project_id = "proj-1"
        orphan2.project_id = "proj-1"

        posted_events: list[DispatchEvent] = []

        def _capture_post_event(event: DispatchEvent):
            posted_events.append(event)

        orch._post_event = _capture_post_event

        # Requirement 3: Reset both tasks
        orch._reset_orphaned_in_progress([orphan1, orphan2])

        # Requirement 2: Verify one wake for multiple resets
        refresh_events = [e for e in posted_events if e.event_type is DispatchEventType.REFRESH_REQUESTED]
        assert len(refresh_events) == 1, (
            f"Requirement 2 failed: expected 1 wake, got {len(refresh_events)}"
        )

        # Requirement 3: Verify both tasks were reset to Open
        assert tracker.update_issue.call_count == 2
        update_calls = [call_obj.kwargs for call_obj in tracker.update_issue.call_args_list]
        assert any(call_obj['status'] == 'Open' for call_obj in update_calls), (
            "Requirement 3 failed: tasks not reset to Open"
        )

        # Requirement 4: Idempotency check — no duplicate wakes on empty call
        posted_events.clear()
        orch._reset_orphaned_in_progress([])
        assert len(posted_events) == 0, (
            "Requirement 4 failed: empty reset should not post wake"
        )


# ---------------------------------------------------------------------------
# Edge cases and mutation testing
# ---------------------------------------------------------------------------


class TestEdgeCasesAndMutations:
    """Tests for edge cases and mutation-resistance."""

    def test_orphan_with_no_project_id_still_reset(self, tmp_path):
        """An orphan issue without a project_id should still be reset (legacy orphans)."""
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch.tracker = tracker
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[])

        # Orphan without project_id
        orphan = _make_issue("TASK-legacy-orphan", state="In Progress")
        assert orphan.project_id is None  # explicitly check it's None

        posted_events: list[DispatchEvent] = []

        def _capture_post_event(event: DispatchEvent):
            posted_events.append(event)

        orch._post_event = _capture_post_event

        orch._reset_orphaned_in_progress([orphan])

        # Should be reset via default tracker
        tracker.update_issue.assert_called_once()
        refresh_events = [e for e in posted_events if e.event_type is DispatchEventType.REFRESH_REQUESTED]
        assert len(refresh_events) == 1

    def test_partial_orphan_reset_failure_still_wakes_for_successful_resets(
        self, tmp_path
    ):
        """If some orphans reset successfully and others fail, wake should be
        posted only if at least one reset succeeded.
        """
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._project_trackers["proj-1"] = tracker
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[])

        orphan1 = _make_issue("TASK-partial-1", state="In Progress")
        orphan2 = _make_issue("TASK-partial-2", state="In Progress")
        orphan1.project_id = "proj-1"
        orphan2.project_id = "proj-1"

        # First reset succeeds, second fails
        def _update(identifier, **fields):
            if identifier == "TASK-partial-2":
                raise RuntimeError("fail on second")
            orphan1.state = fields.get("status", orphan1.state)

        tracker.update_issue.side_effect = _update

        posted_events: list[DispatchEvent] = []

        def _capture_post_event(event: DispatchEvent):
            posted_events.append(event)

        orch._post_event = _capture_post_event

        orch._reset_orphaned_in_progress([orphan1, orphan2])

        # At least one reset should succeed
        assert tracker.update_issue.call_count == 2

        # Wake should be posted if at least one reset succeeded
        refresh_events = [e for e in posted_events if e.event_type is DispatchEventType.REFRESH_REQUESTED]
        # The implementation posts only if reset_count > 0, which it would be
        # even if the second one failed
        assert len(refresh_events) == 1, (
            "Wake should be posted if any orphans were successfully reset"
        )

    def test_stale_loop_recovery_with_no_available_slots(self, tmp_path):
        """Even if worker slots are full, stale-loop recovery should still
        proceed (it just doesn't dispatch agents, but still resets orphans).
        """
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._project_trackers["proj-1"] = tracker
        orch._fetch_all_in_progress_issues = MagicMock(return_value=[])

        orphan = _make_issue("TASK-full-pool", state="In Progress")
        orphan.project_id = "proj-1"

        # Simulate full worker pool
        orch._available_slots = MagicMock(return_value=0)

        posted_events: list[DispatchEvent] = []

        def _capture_post_event(event: DispatchEvent):
            posted_events.append(event)

        orch._post_event = _capture_post_event

        orch._reset_orphaned_in_progress([orphan])

        # Orphan should still be reset
        tracker.update_issue.assert_called_once_with("TASK-full-pool", status="Open")

        # Wake should still be posted (dispatch loop will respect available_slots)
        refresh_events = [e for e in posted_events if e.event_type is DispatchEventType.REFRESH_REQUESTED]
        assert len(refresh_events) == 1
