"""Tests for _detect_independently_merged_children and
_reconcile_independently_merged_children (OOMPAH-311).

Covers:
- Detection of children that bypassed their parent epic's branch (the
  OOMPAH-286/PR #466 pattern).
- Idempotency: children already carrying the label are not re-annotated.
- Label annotation via tracker.update_issue(add_label=...).
- Children on the correct epic branch are NOT flagged.
- Non-Merged children are NOT flagged.
- The reconcile pass is hooked into _do_merged_labels via the sweeps list.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import EPIC_INDEPENDENTLY_MERGED_LABEL, Issue
from oompah.orchestrator import Orchestrator
from oompah.statuses import DONE, MERGED, OPEN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    identifier: str = "task-1",
    state: str = "open",
    issue_type: str = "task",
    parent_id: str | None = None,
    project_id: str | None = "proj-1",
    labels: list[str] | None = None,
    work_branch: str | None = None,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id=project_id,
        labels=labels or [],
        work_branch=work_branch,
    )


def _make_orch(tmp_path, projects=None):
    project_store = MagicMock()
    project_store.list_all.return_value = projects or []
    project_store.get.side_effect = lambda pid: next(
        (p for p in (projects or []) if p.id == pid), None
    )
    project_store.epic_branch_name.side_effect = lambda epic_id: (
        f"epic-{epic_id.replace('/', '_')}"
    )
    orch = Orchestrator(
        config=ServiceConfig(tracker_kind="oompah_md"),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )
    return orch


# ---------------------------------------------------------------------------
# Tests for _detect_independently_merged_children
# ---------------------------------------------------------------------------


class TestDetectIndependentlyMergedChildren:
    """Unit tests for the detection logic only."""

    def test_detects_child_with_own_branch_merged_to_main(self, tmp_path):
        """Child with its own branch (not the epic branch) in Merged state is flagged."""
        orch = _make_orch(tmp_path)
        epic = _make_issue(identifier="EPIC-1", issue_type="epic", state="Open")
        # Child has its own branch, not the epic branch, and is Merged.
        child = _make_issue(
            identifier="CHILD-286",
            state="Merged",
            parent_id="EPIC-1",
            work_branch="CHILD-286",  # own branch, NOT "epic-EPIC-1"
        )
        tracker = MagicMock()
        tracker.fetch_children.return_value = [child]

        with patch.object(orch, "_fetch_epic_children", return_value=[child]):
            results = orch._detect_independently_merged_children([epic])

        assert len(results) == 1
        found_child, found_epic, found_branch = results[0]
        assert found_child.identifier == "CHILD-286"
        assert found_epic.identifier == "EPIC-1"
        # epic_branch_name("EPIC-1") == "epic-EPIC-1" per the stub
        assert found_branch == "epic-EPIC-1"

    def test_ignores_child_on_epic_branch(self, tmp_path):
        """Child whose work_branch matches the epic's branch is NOT flagged."""
        orch = _make_orch(tmp_path)
        epic = _make_issue(identifier="EPIC-1", issue_type="epic", state="Open")
        # This child's work_branch is the epic branch itself — not independently merged.
        child = _make_issue(
            identifier="CHILD-OK",
            state="Merged",
            parent_id="EPIC-1",
            work_branch="epic-EPIC-1",  # matches the epic branch
        )
        with patch.object(orch, "_fetch_epic_children", return_value=[child]):
            results = orch._detect_independently_merged_children([epic])

        assert results == []

    def test_ignores_non_merged_children(self, tmp_path):
        """Children not in Merged state are NOT flagged even if on own branch."""
        orch = _make_orch(tmp_path)
        epic = _make_issue(identifier="EPIC-1", issue_type="epic", state="Open")
        for state in (OPEN, DONE, "In Progress", "In Review"):
            child = _make_issue(
                identifier=f"CHILD-{state}",
                state=state,
                parent_id="EPIC-1",
                work_branch="CHILD-own",
            )
            with patch.object(orch, "_fetch_epic_children", return_value=[child]):
                results = orch._detect_independently_merged_children([epic])
            assert results == [], f"Expected no results for state={state!r}"

    def test_ignores_child_with_no_work_branch(self, tmp_path):
        """Children without a work_branch recorded are NOT flagged."""
        orch = _make_orch(tmp_path)
        epic = _make_issue(identifier="EPIC-1", issue_type="epic", state="Open")
        child = _make_issue(
            identifier="CHILD-NO-BRANCH",
            state="Merged",
            parent_id="EPIC-1",
            work_branch=None,
        )
        with patch.object(orch, "_fetch_epic_children", return_value=[child]):
            results = orch._detect_independently_merged_children([epic])

        assert results == []

    def test_multiple_epics_multiple_children(self, tmp_path):
        """Handles multiple epics each with independent children correctly."""
        orch = _make_orch(tmp_path)
        epic_a = _make_issue(identifier="EPIC-A", issue_type="epic", state="Open")
        epic_b = _make_issue(identifier="EPIC-B", issue_type="epic", state="Merged")

        child_a_ind = _make_issue(
            identifier="CHILD-A-IND",
            state="Merged",
            parent_id="EPIC-A",
            work_branch="CHILD-A-IND",  # own branch
        )
        child_a_ok = _make_issue(
            identifier="CHILD-A-OK",
            state="Merged",
            parent_id="EPIC-A",
            work_branch="epic-EPIC-A",  # matches epic branch
        )
        child_b_ind = _make_issue(
            identifier="CHILD-B-IND",
            state="Merged",
            parent_id="EPIC-B",
            work_branch="CHILD-B-IND",  # own branch
        )

        def _fetch_children(epic):
            if epic.identifier == "EPIC-A":
                return [child_a_ind, child_a_ok]
            if epic.identifier == "EPIC-B":
                return [child_b_ind]
            return []

        with patch.object(orch, "_fetch_epic_children", side_effect=_fetch_children):
            results = orch._detect_independently_merged_children([epic_a, epic_b])

        child_ids = {r[0].identifier for r in results}
        assert child_ids == {"CHILD-A-IND", "CHILD-B-IND"}
        assert "CHILD-A-OK" not in child_ids

    def test_epic_work_branch_overrides_name_derivation(self, tmp_path):
        """When the epic has an explicit work_branch, use it (not epic_branch_name)."""
        orch = _make_orch(tmp_path)
        # Epic has an explicit work_branch set (not the auto-derived "epic-EPIC-1")
        epic = _make_issue(
            identifier="EPIC-1",
            issue_type="epic",
            state="Open",
            work_branch="custom-epic-branch",
        )
        # Child's branch is NOT "custom-epic-branch" → flagged
        child_ind = _make_issue(
            identifier="CHILD-OWN",
            state="Merged",
            parent_id="EPIC-1",
            work_branch="CHILD-OWN",
        )
        # Child's branch IS "custom-epic-branch" → not flagged
        child_ok = _make_issue(
            identifier="CHILD-EPIC",
            state="Merged",
            parent_id="EPIC-1",
            work_branch="custom-epic-branch",
        )

        with patch.object(orch, "_fetch_epic_children", return_value=[child_ind, child_ok]):
            results = orch._detect_independently_merged_children([epic])

        child_ids = {r[0].identifier for r in results}
        assert child_ids == {"CHILD-OWN"}
        assert "CHILD-EPIC" not in child_ids


# ---------------------------------------------------------------------------
# Tests for _reconcile_independently_merged_children
# ---------------------------------------------------------------------------


class TestReconcileIndependentlyMergedChildren:
    """Integration-style tests for the full reconcile pass."""

    def test_annotates_independently_merged_child(self, tmp_path):
        """A newly-found independent child gets the label via update_issue(add_label=...)."""
        orch = _make_orch(tmp_path)
        epic = _make_issue(identifier="EPIC-1", issue_type="epic", state="Open")
        child = _make_issue(
            identifier="CHILD-286",
            state="Merged",
            parent_id="EPIC-1",
            work_branch="CHILD-286",
            labels=[],  # no label yet
        )

        tracker = MagicMock()

        with (
            patch.object(orch, "_all_non_terminal_epics", return_value=[epic]),
            patch.object(orch, "_all_merged_epics", return_value=[]),
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
        ):
            count = orch._reconcile_independently_merged_children()

        assert count == 1
        tracker.update_issue.assert_called_once_with(
            "CHILD-286", add_label=EPIC_INDEPENDENTLY_MERGED_LABEL
        )

    def test_idempotent_already_labeled_child_is_skipped(self, tmp_path):
        """A child already carrying the label is NOT re-annotated."""
        orch = _make_orch(tmp_path)
        epic = _make_issue(identifier="EPIC-1", issue_type="epic", state="Open")
        child = _make_issue(
            identifier="CHILD-286",
            state="Merged",
            parent_id="EPIC-1",
            work_branch="CHILD-286",
            labels=[EPIC_INDEPENDENTLY_MERGED_LABEL],  # already annotated
        )

        tracker = MagicMock()

        with (
            patch.object(orch, "_all_non_terminal_epics", return_value=[epic]),
            patch.object(orch, "_all_merged_epics", return_value=[]),
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
        ):
            count = orch._reconcile_independently_merged_children()

        assert count == 0
        tracker.update_issue.assert_not_called()

    def test_child_on_epic_branch_not_annotated(self, tmp_path):
        """A child whose branch matches the epic branch is not touched."""
        orch = _make_orch(tmp_path)
        epic = _make_issue(identifier="EPIC-1", issue_type="epic", state="Open")
        child = _make_issue(
            identifier="CHILD-OK",
            state="Merged",
            parent_id="EPIC-1",
            work_branch="epic-EPIC-1",  # correct epic branch
        )

        tracker = MagicMock()

        with (
            patch.object(orch, "_all_non_terminal_epics", return_value=[epic]),
            patch.object(orch, "_all_merged_epics", return_value=[]),
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
        ):
            count = orch._reconcile_independently_merged_children()

        assert count == 0
        tracker.update_issue.assert_not_called()

    def test_tracker_error_does_not_crash_reconcile(self, tmp_path):
        """A TrackerError during annotation is swallowed (best-effort pass)."""
        from oompah.tracker import TrackerError

        orch = _make_orch(tmp_path)
        epic = _make_issue(identifier="EPIC-1", issue_type="epic", state="Open")
        child = _make_issue(
            identifier="CHILD-286",
            state="Merged",
            parent_id="EPIC-1",
            work_branch="CHILD-286",
            labels=[],
        )

        tracker = MagicMock()
        tracker.update_issue.side_effect = TrackerError("network timeout")

        with (
            patch.object(orch, "_all_non_terminal_epics", return_value=[epic]),
            patch.object(orch, "_all_merged_epics", return_value=[]),
            patch.object(orch, "_fetch_epic_children", return_value=[child]),
            patch.object(orch, "_tracker_for_issue", return_value=tracker),
        ):
            # Must not raise
            count = orch._reconcile_independently_merged_children()

        # The error was swallowed; annotated count reflects only successes.
        assert count == 0

    def test_returns_zero_when_no_candidates(self, tmp_path):
        """Returns 0 when no independently-merged children exist."""
        orch = _make_orch(tmp_path)

        with (
            patch.object(orch, "_all_non_terminal_epics", return_value=[]),
            patch.object(orch, "_all_merged_epics", return_value=[]),
        ):
            count = orch._reconcile_independently_merged_children()

        assert count == 0

    def test_reconcile_hooked_into_do_merged_labels_sweep(self, tmp_path):
        """_reconcile_independently_merged_children is called by _do_merged_labels."""
        orch = _make_orch(tmp_path)
        # Patch out all other sweeps and the new method to isolate test.
        with (
            patch.object(orch, "_label_merged_epics"),
            patch.object(orch, "_reconcile_merged_epic_children"),
            patch.object(
                orch,
                "_reconcile_independently_merged_children",
                return_value=0,
            ) as mock_reconcile,
            patch.object(orch, "_label_merged_issues"),
            patch.object(orch, "_reconcile_in_review_pr_outcomes"),
            patch.object(orch, "_reconcile_terminal_open_reviews"),
            patch.object(orch, "_reconcile_stale_in_review_tasks"),
            patch.object(orch, "_reconcile_addendum_pr_outcomes_sweep"),
            patch.object(orch, "_job_deadline_exceeded", return_value=False),
        ):
            orch._do_merged_labels()

        mock_reconcile.assert_called_once()
