"""Tests for the draft-label compatibility migration (OOMPAH-171).

remove_draft_labels_from_epics(tracker) must:
  1. Remove 'draft' from every epic that carries it.
  2. Leave non-epic issues untouched (even if they have a 'draft' label).
  3. Leave epics without 'draft' untouched.
  4. Not touch any other label on the epic.
  5. Return the count of epics updated.
  6. Handle tracker.fetch_all_issues() errors gracefully (return 0).
  7. Handle individual remove_label errors gracefully (skip, continue).
  8. Be idempotent — a second run returns 0 (nothing left to clean up).
  9. Integrate with set_orchestrator: migration runs on startup.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from oompah.models import Issue
from oompah.server import remove_draft_labels_from_epics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(
    *,
    id: str,
    identifier: str,
    issue_type: str = "task",
    labels: list[str] | None = None,
) -> Issue:
    return Issue(
        id=id,
        identifier=identifier,
        title="Test",
        state="open",
        issue_type=issue_type,
        labels=labels or [],
    )


def _make_tracker(issues: list[Issue]) -> MagicMock:
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = issues
    tracker.remove_label = MagicMock()
    return tracker


# ===========================================================================
# 1. Basic removal
# ===========================================================================

class TestRemoveDraftLabelsFromEpics:
    """Core behaviour of remove_draft_labels_from_epics."""

    def test_removes_draft_from_epic_with_only_draft_label(self):
        """An epic with only 'draft' label gets the label removed."""
        epic = _make_issue(id="e1", identifier="EPIC-1", issue_type="epic", labels=["draft"])
        tracker = _make_tracker([epic])

        count = remove_draft_labels_from_epics(tracker)

        assert count == 1
        tracker.remove_label.assert_called_once_with("EPIC-1", "draft")

    def test_removes_draft_from_epic_with_multiple_labels(self):
        """remove_label is called only for 'draft', not for other labels."""
        epic = _make_issue(
            id="e1", identifier="EPIC-1", issue_type="epic",
            labels=["draft", "planning", "team:alpha"],
        )
        tracker = _make_tracker([epic])

        count = remove_draft_labels_from_epics(tracker)

        assert count == 1
        tracker.remove_label.assert_called_once_with("EPIC-1", "draft")

    def test_removes_draft_from_multiple_draft_epics(self):
        """All epics with draft label are cleaned up; count matches."""
        epics = [
            _make_issue(id="e1", identifier="EPIC-1", issue_type="epic", labels=["draft"]),
            _make_issue(id="e2", identifier="EPIC-2", issue_type="epic", labels=["draft"]),
            _make_issue(id="e3", identifier="EPIC-3", issue_type="epic", labels=["draft"]),
        ]
        tracker = _make_tracker(epics)

        count = remove_draft_labels_from_epics(tracker)

        assert count == 3
        assert tracker.remove_label.call_count == 3
        tracker.remove_label.assert_any_call("EPIC-1", "draft")
        tracker.remove_label.assert_any_call("EPIC-2", "draft")
        tracker.remove_label.assert_any_call("EPIC-3", "draft")


# ===========================================================================
# 2. Non-epic issues are untouched
# ===========================================================================

class TestNonEpicIssuesUntouched:
    """Non-epic issues must never have remove_label called."""

    def test_task_with_draft_label_is_not_touched(self):
        """A task with 'draft' label must not have remove_label called."""
        task = _make_issue(id="t1", identifier="T-1", issue_type="task", labels=["draft"])
        tracker = _make_tracker([task])

        count = remove_draft_labels_from_epics(tracker)

        assert count == 0
        tracker.remove_label.assert_not_called()

    def test_bug_with_draft_label_is_not_touched(self):
        """A bug with 'draft' label must not have remove_label called."""
        bug = _make_issue(id="b1", identifier="B-1", issue_type="bug", labels=["draft"])
        tracker = _make_tracker([bug])

        count = remove_draft_labels_from_epics(tracker)

        assert count == 0
        tracker.remove_label.assert_not_called()

    def test_mixed_issues_only_epics_cleaned(self):
        """Only epics with 'draft' are cleaned; tasks with 'draft' are left alone."""
        issues = [
            _make_issue(id="e1", identifier="EPIC-1", issue_type="epic", labels=["draft"]),
            _make_issue(id="t1", identifier="T-1", issue_type="task", labels=["draft"]),
            _make_issue(id="t2", identifier="T-2", issue_type="task", labels=[]),
        ]
        tracker = _make_tracker(issues)

        count = remove_draft_labels_from_epics(tracker)

        assert count == 1
        tracker.remove_label.assert_called_once_with("EPIC-1", "draft")


# ===========================================================================
# 3. Epics without 'draft' label are untouched
# ===========================================================================

class TestEpicsWithoutDraftUntouched:
    """Epics that do not carry the 'draft' label must not be touched."""

    def test_epic_without_draft_label_not_touched(self):
        """An epic with no labels must not have remove_label called."""
        epic = _make_issue(id="e1", identifier="EPIC-1", issue_type="epic", labels=[])
        tracker = _make_tracker([epic])

        count = remove_draft_labels_from_epics(tracker)

        assert count == 0
        tracker.remove_label.assert_not_called()

    def test_epic_with_other_labels_not_touched(self):
        """An epic with non-draft labels must not have remove_label called."""
        epic = _make_issue(
            id="e1", identifier="EPIC-1", issue_type="epic",
            labels=["planning", "team:backend"],
        )
        tracker = _make_tracker([epic])

        count = remove_draft_labels_from_epics(tracker)

        assert count == 0
        tracker.remove_label.assert_not_called()


# ===========================================================================
# 4. Empty tracker
# ===========================================================================

def test_empty_tracker_returns_zero():
    """An empty tracker returns 0 and makes no remove_label calls."""
    tracker = _make_tracker([])

    count = remove_draft_labels_from_epics(tracker)

    assert count == 0
    tracker.remove_label.assert_not_called()


# ===========================================================================
# 5. Error handling
# ===========================================================================

class TestErrorHandling:
    """Migration must be resilient to tracker errors."""

    def test_fetch_all_issues_error_returns_zero(self):
        """If fetch_all_issues raises, return 0 without propagating."""
        tracker = MagicMock()
        tracker.fetch_all_issues.side_effect = RuntimeError("tracker down")

        count = remove_draft_labels_from_epics(tracker)

        assert count == 0

    def test_remove_label_error_continues_to_next(self):
        """If remove_label fails for one epic, the others are still processed."""
        epics = [
            _make_issue(id="e1", identifier="EPIC-1", issue_type="epic", labels=["draft"]),
            _make_issue(id="e2", identifier="EPIC-2", issue_type="epic", labels=["draft"]),
        ]
        tracker = _make_tracker(epics)
        # First call fails, second succeeds
        tracker.remove_label.side_effect = [RuntimeError("fail"), None]

        count = remove_draft_labels_from_epics(tracker)

        # Only 1 succeeded (the second one)
        assert count == 1
        assert tracker.remove_label.call_count == 2


# ===========================================================================
# 6. Idempotency
# ===========================================================================

def test_idempotent_second_run_returns_zero():
    """After a successful migration, a second run returns 0."""
    # Simulate tracker after migration: epic has no draft label
    epic = _make_issue(id="e1", identifier="EPIC-1", issue_type="epic", labels=[])
    tracker = _make_tracker([epic])

    count = remove_draft_labels_from_epics(tracker)

    assert count == 0
    tracker.remove_label.assert_not_called()


# ===========================================================================
# 7. Integration: migration runs at set_orchestrator startup
# ===========================================================================

def test_migration_called_during_set_orchestrator():
    """set_orchestrator must invoke remove_draft_labels_from_epics on startup."""
    import oompah.server as server_module

    mock_orch = MagicMock()
    mock_orch.tracker.fetch_all_issues.return_value = []

    with patch.object(server_module, "remove_draft_labels_from_epics") as mock_migrate:
        mock_migrate.return_value = 0
        # Provide minimal stubs so set_orchestrator doesn't crash
        mock_orch.agent_profile_store = MagicMock()
        mock_orch.role_store = MagicMock()
        mock_orch.provider_store = MagicMock()
        mock_orch._observers = []
        mock_orch._state_only_observers = []
        mock_orch._activity_observers = []
        mock_orch.project_store.list_all.return_value = []
        mock_orch.register_error_watcher = MagicMock()

        with (
            patch.object(server_module, "ErrorWatcher", MagicMock()),
            patch.object(server_module, "ProjectLogWatcherManager", MagicMock()),
        ):
            try:
                server_module.set_orchestrator(mock_orch)
            except Exception:
                pass  # ConsoleSessionManager setup may fail in tests

        mock_migrate.assert_called_once_with(mock_orch.tracker)
