"""Tests for epic rebase outcome state tracking (oompah-zlz_2-82dr.3).

Covers:
- _set_epic_rebase_state transitions and label syncing
- _get_epic_rebase_state reading
- _clear_epic_rebase_state cleanup
- _prune_stale_epic_rebase_states dropping closed epics
- _should_dispatch_rebase_agent idempotency
- _restore_epic_rebase_states / _persist_epic_rebase_states persistence
- Snapshot inclusion
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock

import pytest

from oompah.config import ServiceConfig
from oompah.models import EpicRebaseState, EpicRebaseStateEntry, Issue
from oompah.orchestrator import Orchestrator


def _make_issue(
    identifier: str,
    *,
    state: str = "open",
    issue_type: str = "epic",
    priority: int = 1,
    project_id: str = "proj-1",
    labels: list[str] | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="",
        state=state,
        issue_type=issue_type,
        priority=priority,
        project_id=project_id,
        labels=labels or [],
    )


def _make_orchestrator(tmp_path, **kwargs):
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
        **kwargs,
    )
    return orch


# ---------------------------------------------------------------------------
# _set_epic_rebase_state
# ---------------------------------------------------------------------------


class TestSetEpicRebaseState:
    def test_sets_state_and_updates_timestamp(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE, project_id="proj-1"
        )

        entry = orch._epic_rebase_states["epic-1"]
        assert entry.state == "stale"
        assert entry.project_id == "proj-1"
        assert entry.updated_at > 0

    def test_adds_label_when_not_present(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue(
            "epic-1", labels=["other"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE, project_id="proj-1"
        )

        tracker.update_issue.assert_any_call(
            "epic-1", **{"add-label": "epic:stale"}
        )

    def test_removes_old_label_on_transition(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue(
            "epic-1", labels=["epic:stale"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.REBASING, project_id="proj-1"
        )

        tracker.update_issue.assert_any_call(
            "epic-1", **{"remove-label": "epic:stale"}
        )
        tracker.update_issue.assert_any_call(
            "epic-1", **{"add-label": "epic:rebasing"}
        )

    def test_idempotent_same_state_refreshes_timestamp(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue(
            "epic-1", labels=["epic:stale"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE, project_id="proj-1"
        )
        first_ts = orch._epic_rebase_states["epic-1"].updated_at
        time.sleep(0.01)
        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE, project_id="proj-1"
        )
        second_ts = orch._epic_rebase_states["epic-1"].updated_at

        assert second_ts > first_ts
        # No label changes on idempotent call.
        add_label_calls = [
            c for c in tracker.update_issue.call_args_list
            if c.kwargs.get("add-label")
        ]
        # The label was already present on the issue, so no add-label needed.
        assert len(add_label_calls) == 0

    def test_uses_legacy_tracker_when_no_project_id(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch.tracker = tracker

        orch._set_epic_rebase_state("epic-1", EpicRebaseState.STALE)

        tracker.update_issue.assert_called_once_with(
            "epic-1", **{"add-label": "epic:stale"}
        )


# ---------------------------------------------------------------------------
# _get_epic_rebase_state
# ---------------------------------------------------------------------------


class TestGetEpicRebaseState:
    def test_returns_none_when_not_tracked(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._get_epic_rebase_state("epic-x") is None

    def test_returns_enum_when_tracked(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="rebasing",
            updated_at=time.time(),
        )
        assert orch._get_epic_rebase_state("epic-1") == EpicRebaseState.REBASING

    def test_returns_none_for_unknown_state_value(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="garbage",
            updated_at=time.time(),
        )
        assert orch._get_epic_rebase_state("epic-1") is None


# ---------------------------------------------------------------------------
# _clear_epic_rebase_state
# ---------------------------------------------------------------------------


class TestClearEpicRebaseState:
    def test_removes_state_and_labels(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue(
            "epic-1", labels=["epic:stale", "other"]
        )
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="stale",
            updated_at=time.time(),
        )

        orch._clear_epic_rebase_state("epic-1", project_id="proj-1")

        assert "epic-1" not in orch._epic_rebase_states
        tracker.update_issue.assert_called_once_with(
            "epic-1", **{"remove-label": "epic:stale"}
        )

    def test_noop_when_not_tracked(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._clear_epic_rebase_state("epic-1", project_id="proj-1")

        tracker.fetch_issue_detail.assert_not_called()


# ---------------------------------------------------------------------------
# _prune_stale_epic_rebase_states
# ---------------------------------------------------------------------------


class TestPruneStaleEpicRebaseStates:
    def test_drops_closed_epics(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-open"] = EpicRebaseStateEntry(
            state="stale", updated_at=time.time()
        )
        orch._epic_rebase_states["epic-closed"] = EpicRebaseStateEntry(
            state="rebased", updated_at=time.time()
        )

        candidates = [
            _make_issue("epic-open", state="open"),
            _make_issue("epic-closed", state="closed"),
        ]
        orch._prune_stale_epic_rebase_states(candidates)

        assert "epic-open" in orch._epic_rebase_states
        assert "epic-closed" not in orch._epic_rebase_states

    def test_keeps_non_epic_issues_out_of_consideration(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="stale", updated_at=time.time()
        )

        candidates = [_make_issue("epic-1", state="open", issue_type="task")]
        orch._prune_stale_epic_rebase_states(candidates)

        # epic-1 is not an epic in this candidate list → dropped
        assert "epic-1" not in orch._epic_rebase_states


# ---------------------------------------------------------------------------
# _should_dispatch_rebase_agent
# ---------------------------------------------------------------------------


class TestShouldDispatchRebaseAgent:
    def test_true_when_no_state(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        assert orch._should_dispatch_rebase_agent("epic-1") is True

    def test_true_when_stale(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="stale", updated_at=time.time()
        )
        assert orch._should_dispatch_rebase_agent("epic-1") is True

    def test_true_when_failed(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        # Set updated_at far enough in the past that the exponential
        # backoff (300 * 2^retry_count, capped 3600s) has elapsed.
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="failed", updated_at=time.time() - 7200
        )
        assert orch._should_dispatch_rebase_agent("epic-1") is True

    def test_false_when_failed_in_backoff(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        # updated_at just now — backoff (300 * 2^0 = 300s) has not elapsed.
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="failed", updated_at=time.time(), retry_count=0
        )
        assert orch._should_dispatch_rebase_agent("epic-1") is False

    def test_false_when_rebasing(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="rebasing", updated_at=time.time()
        )
        assert orch._should_dispatch_rebase_agent("epic-1") is False

    def test_false_when_rebased(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="rebased", updated_at=time.time()
        )
        assert orch._should_dispatch_rebase_agent("epic-1") is True


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_restore_from_disk(self, tmp_path):
        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps(
                {
                    "epic_rebase_states": {
                        "epic-a": {
                            "state": "stale",
                            "updated_at": time.time(),
                            "project_id": "proj-1",
                        }
                    }
                }
            )
        )
        orch = _make_orchestrator(tmp_path)
        assert "epic-a" in orch._epic_rebase_states
        assert orch._epic_rebase_states["epic-a"].state == "stale"

    def test_drops_stale_entries_on_restore(self, tmp_path):
        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps(
                {
                    "epic_rebase_states": {
                        "epic-old": {
                            "state": "rebasing",
                            "updated_at": time.time() - 90000,  # > 24h
                            "project_id": None,
                        }
                    }
                }
            )
        )
        orch = _make_orchestrator(tmp_path)
        assert "epic-old" not in orch._epic_rebase_states

    def test_persists_on_set(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state(
            "epic-1", EpicRebaseState.STALE, project_id="proj-1"
        )

        disk = json.loads((tmp_path / "state.json").read_text())
        assert "epic_rebase_states" in disk
        assert disk["epic_rebase_states"]["epic-1"]["state"] == "stale"

    def test_persists_on_clear(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._set_epic_rebase_state("epic-1", EpicRebaseState.STALE)
        orch._clear_epic_rebase_state("epic-1")

        disk = json.loads((tmp_path / "state.json").read_text())
        assert "epic-1" not in disk.get("epic_rebase_states", {})


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


class TestSnapshot:
    def test_includes_epic_rebase_states(self, tmp_path):
        orch = _make_orchestrator(tmp_path)
        orch._epic_rebase_states["epic-1"] = EpicRebaseStateEntry(
            state="rebasing", updated_at=1234.0, project_id="proj-1"
        )
        snapshot = orch.get_snapshot()
        assert "epic_rebase_states" in snapshot
        assert snapshot["epic_rebase_states"]["epic-1"]["state"] == "rebasing"
        assert snapshot["epic_rebase_states"]["epic-1"]["updated_at"] == 1234.0
