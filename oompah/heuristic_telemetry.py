"""Heuristic telemetry for merge-order conflict-impact predictor.

Tracks whether the merge-order heuristic (oompah-zlz_2-vm1p.2) actually
reduces conflict-agent dispatches and total time-to-merge.

Metrics per project:
- conflict_predictions: number of PRs scored by the heuristic
- predicted_conflicts: how many PRs had a predicted score > 0
- conflict_dispatches: how many times a conflict-agent was dispatched
- conflicts_avoided: PRs with predicted score > 0 that merged cleanly
- merge_timers: per-PR wall-clock time from created_at to merge
- heuristic_accuracy: fraction of predictions that matched actual outcome
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class _ProjectTelemetry:
    """Mutable per-project telemetry counters."""

    # Prediction tracking
    conflict_predictions: int = 0  # total PRs scored
    predicted_conflicts: int = 0  # PRs with score > 0

    # Dispatch tracking
    conflict_dispatches: int = 0  # times _yolo_notify_conflict was called

    # Outcome tracking
    clean_merges: int = 0  # PRs that merged without conflict dispatch
    conflicts_avoided: int = 0  # PRs with score>0 that merged cleanly

    # Accuracy tracking: how many predictions matched reality
    correct_predictions: int = 0  # predicted right (score>0 and conflicted, or score==0 and clean)
    total_outcomes: int = 0  # outcomes we can compare against predictions

    # Time-to-merge tracking
    _merge_times: list[float] = field(default_factory=list)  # seconds

    # Per-branch prediction records: branch -> score at time of prediction
    _predicted_scores: dict[str, int] = field(default_factory=dict)

    # Branches that actually had conflict dispatches
    _conflict_branches: set[str] = field(default_factory=set)

    def record_prediction(self, branch: str, score: int) -> None:
        """Record a conflict-impact prediction for a branch."""
        self.conflict_predictions += 1
        if score > 0:
            self.predicted_conflicts += 1
        self._predicted_scores[branch] = score

    def record_conflict_dispatch(self, branch: str | None) -> None:
        """Record that a conflict-agent was dispatched for this branch."""
        self.conflict_dispatches += 1
        if branch:
            self._conflict_branches.add(branch)

    def record_merge(self, branch: str | None, created_at: datetime | None) -> None:
        """Record a successful merge for a branch.

        Computes time-to-merge if created_at is available.
        Also updates accuracy counters by comparing prediction vs outcome.
        """
        self.clean_merges += 1

        # Time-to-merge
        if created_at:
            try:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                elapsed = (datetime.now(timezone.utc) - created_at).total_seconds()
                self._merge_times.append(elapsed)
            except (ValueError, TypeError, OverflowError):
                pass

        # Accuracy: check if this branch had a prediction
        if branch and branch in self._predicted_scores:
            score = self._predicted_scores[branch]
            had_conflict = branch in self._conflict_branches
            self.total_outcomes += 1
            if score > 0:
                if had_conflict:
                    self.correct_predictions += 1
                else:
                    # Predicted conflict but merged cleanly — a conflict avoided!
                    self.correct_predictions += 1
                    self.conflicts_avoided += 1
            else:
                if not had_conflict:
                    self.correct_predictions += 1

    def clear_branch(self, branch: str) -> None:
        """Clear per-branch state when a PR closes/merges."""
        self._predicted_scores.pop(branch, None)
        self._conflict_branches.discard(branch)

    def avg_time_to_merge(self) -> float | None:
        """Return average time-to-merge in seconds, or None."""
        if not self._merge_times:
            return None
        return sum(self._merge_times) / len(self._merge_times)

    def heuristic_accuracy(self) -> float | None:
        """Return heuristic accuracy 0.0-1.0, or None if no outcomes yet."""
        if self.total_outcomes == 0:
            return None
        return self.correct_predictions / self.total_outcomes

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable dict of current metrics."""
        return {
            "conflict_predictions": self.conflict_predictions,
            "predicted_conflicts": self.predicted_conflicts,
            "conflict_dispatches": self.conflict_dispatches,
            "clean_merges": self.clean_merges,
            "conflicts_avoided": self.conflicts_avoided,
            "heuristic_accuracy": self.heuristic_accuracy(),
            "avg_time_to_merge": self.avg_time_to_merge(),
        }


class HeuristicTelemetry:
    """Tracks merge-order heuristic effectiveness per project.

    Meant to be stored on the Orchestrator as
    ``self._heuristic_telemetry`` and called from the scoring,
    conflict-dispatch, and merge-detection paths.
    """

    def __init__(self) -> None:
        self._projects: dict[str, _ProjectTelemetry] = {}

    def _get(self, project_id: str) -> _ProjectTelemetry:
        if project_id not in self._projects:
            self._projects[project_id] = _ProjectTelemetry()
        return self._projects[project_id]

    # ---- Public API called from orchestrator instrumentation ----

    def record_predictions(
        self, project_id: str, predictions: dict[str, int]
    ) -> None:
        """Record all conflict-impact predictions from one sort pass.

        ``predictions`` maps source_branch -> conflict_score.
        """
        p = self._get(project_id)
        for branch, score in predictions.items():
            p.record_prediction(branch, score)

    def record_conflict_dispatch(self, project_id: str, branch: str | None) -> None:
        """Record a conflict-agent dispatch."""
        self._get(project_id).record_conflict_dispatch(branch)

    def record_merge(
        self, project_id: str, branch: str | None, created_at: datetime | None
    ) -> None:
        """Record a successful merge for time-to-merge and accuracy."""
        p = self._get(project_id)
        p.record_merge(branch, created_at)
        if branch:
            p.clear_branch(branch)

    # ---- Snapshot / serialization ----

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return all project telemetry as a nested dict for get_snapshot()."""
        return {
            pid: p.to_dict() for pid, p in self._projects.items()
        }

    def clear_project(self, project_id: str) -> None:
        """Remove all telemetry for a project (e.g. on project delete)."""
        self._projects.pop(project_id, None)
