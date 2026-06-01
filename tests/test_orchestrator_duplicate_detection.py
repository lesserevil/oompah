"""Integration tests for orchestrator duplicate detection (oompah-zlz_2-x6w3).

Tests that find_similar_issues() is wired into the orchestrator dispatch flow:
- Open-issue duplicates get rejected via Duplicate Candidate status
- Closed-issue matches get needs:duplicate_detector label
- _should_dispatch rejects duplicate-candidate labelled issues
"""

from unittest.mock import MagicMock

import pytest

from oompah.focus import (
    BUILTIN_FOCI,
    _MIN_SCORE_TO_FLAG,
    find_similar_issues,
    select_focus,
)
from oompah.models import Issue


def _make_issue(**kwargs):
    defaults = dict(
        id="1",
        identifier="beads-001",
        title="Test issue",
        state="open",
        issue_type="bug",
        priority=2,
        labels=None,
        project_id="proj-1",
        blocked_by=[],
        description="Test description",
    )
    defaults.update(kwargs)
    if defaults["labels"] is None:
        defaults["labels"] = []
    if defaults["blocked_by"] is None:
        defaults["blocked_by"] = []
    return Issue(**defaults)


class TestFindSimilarIssuesInOrchestratorFlow:
    """Tests that verify find_similar_issues integration into the orchestrator."""

    def test_find_similar_issues_returns_rogers_prefix_matches(self):
        """Pattern-based duplicate: rogers-how and rogers-5hd should be found."""
        base = _make_issue(identifier="new-rogers", title="rogers-how to connect",
                           project_id="p", issue_type="bug")
        candidates = [
            _make_issue(identifier="old-1", title="rogers-5hd setup",
                        project_id="p", issue_type="bug"),
            _make_issue(identifier="old-2", title="rogers-zdn error",
                        project_id="p", issue_type="bug"),
            _make_issue(identifier="unrelated", title="database-migration",
                        project_id="p", issue_type="bug"),
        ]
        similar = find_similar_issues(base, candidates)
        # Both rogers-* issues should be found
        identifiers = {s.identifier for s, _ in similar}
        assert "old-1" in identifiers
        assert "old-2" in identifiers
        # Unrelated issue should not be found (no shared prefix, different topic)
        assert "unrelated" not in identifiers

    def test_find_similar_issues_respects_min_score(self):
        """Raising min_score should exclude borderline matches."""
        base = _make_issue(identifier="x", title="rogers-alpha",
                           project_id="p", issue_type="bug", labels=[])
        candidates = [
            _make_issue(identifier="y", title="rogers-beta",
                        project_id="p", issue_type="bug", labels=[]),
        ]
        # Default threshold (0.5) should include it
        similar = find_similar_issues(base, candidates, min_score=_MIN_SCORE_TO_FLAG)
        assert len(similar) == 1
        # Higher threshold should exclude it
        similar_high = find_similar_issues(base, candidates, min_score=0.9)
        assert len(similar_high) == 0


class TestShouldDispatchRejectsDuplicateCandidate:
    """Tests that _should_dispatch rejects issues with duplicate-candidate label."""

    def _make_orch_for_should_dispatch(self):
        """Create a minimal Orchestrator instance suitable for _should_dispatch."""
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        config = ServiceConfig()
        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch._paused = False
        orch._rate_limit_until = 0
        orch.state = MagicMock()
        orch.state.running = {}
        orch.state.claimed = set()
        orch.state.retry_attempts = {}
        orch.state.completed = set()
        orch.state.reject_streak = {}

        orch._is_project_paused = lambda pid: False
        orch._is_rate_limited = lambda: False
        orch._available_slots = lambda: 1
        orch._per_state_available = lambda s: True
        orch._check_budget = lambda: True
        orch._would_dispatch_via_acp = lambda i: False
        orch._would_dispatch_on_free_model = lambda i: False
        orch._count_open_reviews = lambda pid: 0
        orch._project_max_in_flight = lambda pid: 1
        return orch

    def test_should_dispatch_rejects_duplicate_candidate(self):
        """An issue with duplicate-candidate label should be rejected."""
        orch = self._make_orch_for_should_dispatch()

        issue = _make_issue(
            identifier="rogers-xyz",
            title="rogers-xyz duplicate issue",
            labels=["duplicate-candidate"],
        )

        result = orch._should_dispatch(issue)
        assert result is False

    def test_issue_without_duplicate_candidate_label_allowed(self):
        """An issue WITHOUT duplicate-candidate label should not be rejected for that reason."""
        orch = self._make_orch_for_should_dispatch()

        issue = _make_issue(
            identifier="rogers-abc",
            title="rogers-abc unique issue",
            labels=[],
        )

        result = orch._should_dispatch(issue)
        assert result is True


class TestApplyDuplicateDetection:
    """Tests for the _apply_duplicate_detection orchestrator method."""

    def test_detects_open_duplicate_and_labels_candidate(self, tmp_path, monkeypatch):
        """When candidate matches open issue by prefix, add duplicate-candidate label."""
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig
        from oompah.projects import ProjectStore

        monkeypatch.setattr("oompah.projects.DEFAULT_PROJECTS_PATH",
                            str(tmp_path / "projects.json"))

        config = ServiceConfig()
        projects_path = tmp_path / "projects.json"
        projects_path.write_text("[]")
        project_store = ProjectStore()

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.project_store = project_store
        orch._project_trackers = {}
        orch._blocker_state_cache = {}
        orch._alerts = []

        mock_tracker = MagicMock()

        existing_issue = _make_issue(
            identifier="rogers-alpha",
            title="rogers-alpha issue",
            project_id="proj-1",
            issue_type="bug",
            state="open",
        )
        mock_tracker.fetch_issues_by_states.return_value = [existing_issue]

        candidate = _make_issue(
            identifier="rogers-beta",
            title="rogers-beta issue",
            project_id="proj-1",
            issue_type="bug",
            state="open",
            labels=[],
        )

        orch._tracker_for_project = lambda pid: mock_tracker
        orch._post_comment = MagicMock()

        result = orch._apply_duplicate_detection([candidate])

        # Should have moved the candidate to the Duplicate Candidate status.
        mock_tracker.update_issue.assert_called_with(
            "rogers-beta", status="Duplicate Candidate"
        )
        # Should have posted a comment
        orch._post_comment.assert_called()
        comment_text = orch._post_comment.call_args[0][1]
        assert "duplicate" in comment_text.lower() or "similar" in comment_text.lower()

    def test_detects_closed_match_and_labels_candidate(self, tmp_path, monkeypatch):
        """When candidate matches closed issue by prefix, add needs:duplicate_detector label."""
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig
        from oompah.projects import ProjectStore

        monkeypatch.setattr("oompah.projects.DEFAULT_PROJECTS_PATH",
                            str(tmp_path / "projects.json"))

        config = ServiceConfig()
        projects_path = tmp_path / "projects.json"
        projects_path.write_text("[]")
        project_store = ProjectStore()

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.project_store = project_store
        orch._project_trackers = {}
        orch._blocker_state_cache = {}
        orch._alerts = []

        mock_tracker = MagicMock()

        # Closed issue — terminal state
        closed_issue = _make_issue(
            identifier="rogers-fixed",
            title="rogers-fixed issue",
            project_id="proj-1",
            issue_type="bug",
            state="closed",
        )
        mock_tracker.fetch_issues_by_states.return_value = [closed_issue]

        candidate = _make_issue(
            identifier="rogers-new",
            title="rogers-new issue",
            project_id="proj-1",
            issue_type="bug",
            state="open",
            labels=[],
        )

        orch._tracker_for_project = lambda pid: mock_tracker
        orch._post_comment = MagicMock()

        result = orch._apply_duplicate_detection([candidate])

        # Should have added needs:duplicate_detector label
        mock_tracker.add_label.assert_called_with("rogers-new", "needs:duplicate_detector")

    def test_no_duplicate_when_different_prefix(self, tmp_path, monkeypatch):
        """Issues with different prefixes should not trigger duplicate detection."""
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig
        from oompah.projects import ProjectStore

        monkeypatch.setattr("oompah.projects.DEFAULT_PROJECTS_PATH",
                            str(tmp_path / "projects.json"))

        config = ServiceConfig()
        projects_path = tmp_path / "projects.json"
        projects_path.write_text("[]")
        project_store = ProjectStore()

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.project_store = project_store
        orch._project_trackers = {}
        orch._blocker_state_cache = {}
        orch._alerts = []

        mock_tracker = MagicMock()

        existing_issue = _make_issue(
            identifier="database-migration",
            title="database-migration issue",
            project_id="proj-1",
            issue_type="bug",
            state="open",
        )
        mock_tracker.fetch_issues_by_states.return_value = [existing_issue]

        candidate = _make_issue(
            identifier="rogers-connect",
            title="rogers-connect issue",
            project_id="proj-1",
            issue_type="bug",
            state="open",
            labels=[],
        )

        orch._tracker_for_project = lambda pid: mock_tracker
        orch._post_comment = MagicMock()

        result = orch._apply_duplicate_detection([candidate])

        # Should NOT add any labels (different topic prefix)
        mock_tracker.add_label.assert_not_called()

    def test_empty_candidates_returns_early(self):
        """Empty candidate list should return immediately without querying trackers."""
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        config = ServiceConfig()
        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config

        result = orch._apply_duplicate_detection([])
        assert result == []


class TestEndToEndDispatchFlow:
    """End-to-end test verifying the full dispatch flow rejects duplicates."""

    def test_rogers_pattern_duplicate_rejected_in_dispatch_flow(self):
        """Simulate the full dispatch flow: fetch → detect → select_dispatchable.

        This tests the critical path through _apply_duplicate_detection and
        _should_dispatch to verify rogers-* issues with same prefix but
        different suffixes are properly detected as duplicates.
        """
        from unittest.mock import MagicMock
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig
        from oompah.projects import ProjectStore

        config = ServiceConfig()
        project_store = ProjectStore()

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.project_store = project_store
        orch._project_trackers = {}
        orch._blocker_state_cache = {}
        orch._alerts = []

        # Setup the tracker mock to return an existing open rogers issue
        mock_tracker = MagicMock()
        existing_issue = _make_issue(
            identifier="rogers-alpha",
            title="rogers-alpha issue",
            project_id="proj-1",
            issue_type="bug",
            state="open",
        )
        mock_tracker.fetch_issues_by_states.return_value = [existing_issue]
        orch._tracker_for_project = lambda pid: mock_tracker
        orch._post_comment = MagicMock()

        # Setup _should_dispatch mocks
        orch._paused = False
        orch._is_project_paused = lambda pid: False
        orch._is_rate_limited = lambda: False
        orch._available_slots = lambda: 1
        orch._per_state_available = lambda s: True
        orch._check_budget = lambda: True
        orch._would_dispatch_via_acp = lambda i: False
        orch._would_dispatch_on_free_model = lambda i: False
        orch._count_open_reviews = lambda pid: 0
        orch._project_max_in_flight = lambda pid: 1
        orch.state = MagicMock()
        orch.state.running = {}
        orch.state.claimed = set()
        orch.state.retry_attempts = {}
        orch.state.completed = set()
        orch.state.reject_streak = {}

        # The dispatch flow: fetch candidates → apply_duplicate_detection → _should_dispatch
        candidate = _make_issue(
            identifier="rogers-beta",
            title="rogers-beta new issue",
            project_id="proj-1",
            issue_type="bug",
            state="open",
            labels=[],
        )

        # Step 1: Apply duplicate detection (simulates _handle_dispatch_needed)
        detected_candidates = orch._apply_duplicate_detection([candidate])

        # Step 2: Check if candidate passes _should_dispatch
        should_dispatch = orch._should_dispatch(detected_candidates[0])

        # Assert: candidate should NOT be dispatchable because it was flagged
        assert should_dispatch is False, (
            "Candidate with duplicate-candidate label should be rejected by _should_dispatch"
        )

        # Verify the Duplicate Candidate status was written.
        mock_tracker.update_issue.assert_called()
        call_args = mock_tracker.update_issue.call_args
        assert call_args.kwargs["status"] == "Duplicate Candidate"

    def test_closed_match_routes_to_duplicate_detector_focus(self):
        """When candidate matches closed issue, needs:duplicate_detector label
        should cause the duplicate_detector focus to be selected."""
        from unittest.mock import MagicMock
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig
        from oompah.projects import ProjectStore

        config = ServiceConfig()
        project_store = ProjectStore()

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.project_store = project_store
        orch._project_trackers = {}
        orch._blocker_state_cache = {}
        orch._alerts = []

        mock_tracker = MagicMock()
        closed_issue = _make_issue(
            identifier="rogers-fixed",
            title="rogers-fixed issue",
            project_id="proj-1",
            issue_type="bug",
            state="closed",
        )
        mock_tracker.fetch_issues_by_states.return_value = [closed_issue]
        orch._tracker_for_project = lambda pid: mock_tracker
        orch._post_comment = MagicMock()

        candidate = _make_issue(
            identifier="rogers-new",
            title="rogers-new issue",
            project_id="proj-1",
            issue_type="bug",
            state="open",
            labels=[],
        )

        # Apply duplicate detection
        detected_candidates = orch._apply_duplicate_detection([candidate])

        # Now check that select_focus picks duplicate_detector due to the label
        focus = select_focus(detected_candidates[0])
        assert focus.name == "duplicate_detector", (
            f"Expected duplicate_detector focus, got {focus.name}"
        )
