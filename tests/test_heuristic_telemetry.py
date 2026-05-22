"""Tests for heuristic_telemetry (oompah-zlz_2-vm1p.3).

Covers:
- _ProjectTelemetry: prediction tracking, accuracy, conflicts_avoided,
  time-to-merge, clear_branch
- HeuristicTelemetry: multi-project isolation, snapshot, clear_project
- Instrumented scenarios: predictions → conflict dispatch → merge
  (the three integration points in orchestrator.py)
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from oompah.heuristic_telemetry import HeuristicTelemetry, _ProjectTelemetry


class TestProjectTelemetryPredictionTracking:
    def test_records_conflict_prediction(self):
        pt = _ProjectTelemetry()
        pt.record_prediction("feat-a", score=0)
        pt.record_prediction("feat-b", score=3)
        pt.record_prediction("feat-c", score=0)

        assert pt.conflict_predictions == 3
        assert pt.predicted_conflicts == 1

    def test_records_multiple_predictions_per_branch_overwrites(self):
        pt = _ProjectTelemetry()
        pt.record_prediction("feat-a", score=5)
        pt.record_prediction("feat-a", score=2)  # later score wins

        # Conflict predictions tracked via the dict; the second call updates
        assert pt._predicted_scores["feat-a"] == 2

    def test_records_conflict_dispatch(self):
        pt = _ProjectTelemetry()
        pt.record_conflict_dispatch("feat-a")
        pt.record_conflict_dispatch("feat-b")
        pt.record_conflict_dispatch(None)  # no branch available

        assert pt.conflict_dispatches == 3
        assert "feat-a" in pt._conflict_branches
        assert "feat-b" in pt._conflict_branches

    def test_record_merge_increments_clean_merges(self):
        pt = _ProjectTelemetry()
        pt.record_merge("feat-a", created_at=None)

        assert pt.clean_merges == 1

    def test_record_merge_with_created_at_appends_time(self):
        pt = _ProjectTelemetry()
        before = datetime.now(timezone.utc)
        pt.record_merge("feat-a", created_at=before)
        after = datetime.now(timezone.utc)

        assert len(pt._merge_times) == 1
        assert 0 <= pt._merge_times[0] <= (after - before).total_seconds() + 1

    def test_record_merge_with_naive_datetime_utc_normalized(self):
        pt = _ProjectTelemetry()
        naive = datetime(2025, 1, 1, 12, 0, 0)
        pt.record_merge("feat-a", created_at=naive)

        assert len(pt._merge_times) == 1
        # Should not raise

    def test_avg_time_to_merge_returns_none_when_empty(self):
        pt = _ProjectTelemetry()
        assert pt.avg_time_to_merge() is None

    def test_avg_time_to_merge_returns_mean(self):
        pt = _ProjectTelemetry()
        # Manually append times to isolate from wall-clock
        pt._merge_times = [100.0, 200.0, 300.0]
        assert pt.avg_time_to_merge() == 200.0

    def test_clear_branch_removes_state(self):
        pt = _ProjectTelemetry()
        pt.record_prediction("feat-a", score=3)
        pt.record_conflict_dispatch("feat-a")
        pt.clear_branch("feat-a")

        assert "feat-a" not in pt._predicted_scores
        assert "feat-a" not in pt._conflict_branches

    def test_clear_branch_noop_for_unknown_branch(self):
        pt = _ProjectTelemetry()
        pt.clear_branch("unknown")  # must not raise


class TestProjectTelemetryAccuracy:
    def test_correct_prediction_when_score_zero_and_no_conflict(self):
        """PR scored low (score=0), no conflict dispatcher touched it → correct."""
        pt = _ProjectTelemetry()
        pt.record_prediction("feat-a", score=0)
        pt.record_merge("feat-a", created_at=None)

        assert pt.correct_predictions == 1
        assert pt.total_outcomes == 1
        assert pt.heuristic_accuracy() == 1.0

    def test_correct_prediction_when_score_positive_and_conflict_dispatched(self):
        """PR scored high (score>0), conflict agent dispatched → correct."""
        pt = _ProjectTelemetry()
        pt.record_prediction("feat-a", score=3)
        pt.record_conflict_dispatch("feat-a")
        pt.record_merge("feat-a", created_at=None)

        assert pt.correct_predictions == 1
        assert pt.total_outcomes == 1
        assert pt.heuristic_accuracy() == 1.0

    def test_conflicts_avoided_when_score_positive_but_no_conflict(self):
        """PR scored high (score>0), merged cleanly without dispatch → conflict avoided."""
        pt = _ProjectTelemetry()
        pt.record_prediction("feat-a", score=3)
        # No conflict_dispatch recorded
        pt.record_merge("feat-a", created_at=None)

        assert pt.correct_predictions == 1
        assert pt.conflicts_avoided == 1
        assert pt.total_outcomes == 1
        assert pt.heuristic_accuracy() == 1.0

    def test_incorrect_prediction_when_score_zero_but_conflict_dispatched(self):
        """PR scored low (score=0), but conflict agent WAS dispatched → wrong."""
        pt = _ProjectTelemetry()
        pt.record_prediction("feat-a", score=0)
        pt.record_conflict_dispatch("feat-a")
        pt.record_merge("feat-a", created_at=None)

        assert pt.correct_predictions == 0
        assert pt.total_outcomes == 1
        assert pt.heuristic_accuracy() == 0.0

    def test_heuristic_accuracy_returns_none_when_no_outcomes(self):
        pt = _ProjectTelemetry()
        assert pt.heuristic_accuracy() is None


class TestProjectTelemetryToDict:
    def test_to_dict_includes_all_counters(self):
        pt = _ProjectTelemetry()
        # feat-a: score>0, conflict dispatched → correct (not conflicts_avoided)
        pt.record_prediction("feat-a", score=5)
        pt.record_conflict_dispatch("feat-a")
        pt.record_merge("feat-a", created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
        d = pt.to_dict()

        # These are the fields surfaced to get_snapshot() dashboard
        assert d["conflict_predictions"] == 1
        assert d["predicted_conflicts"] == 1
        assert d["conflict_dispatches"] == 1
        assert d["clean_merges"] == 1
        # conflicts_avoided only increments when we PREDICTED a conflict
        # (score>0) but no conflict-agent was actually dispatched — that
        # PR merged cleanly despite the high score, meaning the heuristic
        # was wrong but the outcome was good.
        assert d["conflicts_avoided"] == 0
        assert d["heuristic_accuracy"] == 1.0
        assert d["avg_time_to_merge"] is not None


class TestHeuristicTelemetry:
    def test_separate_projects_get_isolated_counters(self):
        ht = HeuristicTelemetry()
        ht.record_predictions("proj-a", {"feat-a": 5, "feat-b": 0})
        ht.record_predictions("proj-b", {"feat-c": 2})
        ht.record_conflict_dispatch("proj-a", "feat-a")
        ht.record_merge("proj-b", "feat-c", None)

        snap = ht.snapshot()
        assert "proj-a" in snap
        assert "proj-b" in snap
        assert snap["proj-a"]["conflict_predictions"] == 2
        assert snap["proj-b"]["conflict_predictions"] == 1
        assert snap["proj-b"]["clean_merges"] == 1

    def test_snapshot_empty_when_no_data(self):
        ht = HeuristicTelemetry()
        assert ht.snapshot() == {}

    def test_clear_project_removes_data(self):
        ht = HeuristicTelemetry()
        ht.record_predictions("proj-a", {"feat-a": 1})
        ht.clear_project("proj-a")

        assert ht.snapshot() == {}

    def test_clear_project_noop_for_unknown_project(self):
        ht = HeuristicTelemetry()
        ht.clear_project("unknown")  # must not raise
        assert ht.snapshot() == {}

    def test_record_predictions_with_empty_dict(self):
        """Empty prediction dict should be handled gracefully.

        Creates the project record (all zeros) — snapshot() is never empty
        once any call has been made for a project.
        """
        ht = HeuristicTelemetry()
        ht.record_predictions("proj-a", {})  # no-op; project still registered
        snap = ht.snapshot()["proj-a"]
        assert snap["conflict_predictions"] == 0
        assert snap["predicted_conflicts"] == 0
        assert snap["conflict_dispatches"] == 0

    def test_record_conflict_dispatch_with_none_branch(self):
        """Branch may be None when source_branch isn't available."""
        ht = HeuristicTelemetry()
        ht.record_conflict_dispatch("proj-a", None)
        assert ht.snapshot()["proj-a"]["conflict_dispatches"] == 1

    def test_record_merge_with_none_created_at(self):
        """created_at may be None; time-to-merge just won't be recorded."""
        ht = HeuristicTelemetry()
        ht.record_merge("proj-a", "feat-a", None)
        snap = ht.snapshot()["proj-a"]
        assert snap["clean_merges"] == 1
        assert snap["avg_time_to_merge"] is None


class TestIntegrationScenario:
    def test_full_scenario_predictions_then_dispatch_then_merge(self):
        """Simulate: heuristic scores 3 PRs → one conflict dispatches → one merges cleanly.

        Snapshot fields are correct_predictions / total_away from the dashboard
        (to keep the API lean). Verify them via the internal pt directly.
        """
        ht = HeuristicTelemetry()

        # Predictions from _sort_reviews_by_conflict_impact
        ht.record_predictions(
            "rogers",
            {
                "feat-bump-deps": 0,
                "feat-dark-mode": 3,  # predicted high-conflict
                "feat-i18n": 1,
            },
        )

        # Only feat-dark-mode actually needed the conflict agent
        ht.record_conflict_dispatch("rogers", "feat-dark-mode")

        # All three eventually merged cleanly
        for branch in ("feat-bump-deps", "feat-dark-mode", "feat-i18n"):
            ht.record_merge("rogers", branch, created_at=None)

        snap = ht.snapshot()["rogers"]
        # Dashboard-visible fields from to_dict():
        assert snap["conflict_predictions"] == 3
        assert snap["predicted_conflicts"] == 2  # dark-mode(3) and i18n(1)
        assert snap["conflict_dispatches"] == 1
        assert snap["clean_merges"] == 3
        assert snap["conflicts_avoided"] == 1  # feat-i18n: predicted conflict, merged cleanly
        # Internal accuracy (verified via pt directly):
        pt = ht._projects["rogers"]
        assert pt.correct_predictions == 3
        assert pt.total_outcomes == 3
        assert pt.heuristic_accuracy() == 1.0