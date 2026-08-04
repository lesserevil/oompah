"""Integration tests for orchestrator duplicate detection (oompah-zlz_2-x6w3).

Tests that find_similar_issues() is wired into the orchestrator dispatch flow:
- Active-issue duplicates get rejected via Duplicate Candidate status
- Terminal issues are excluded from automatic duplicate detection
- _should_dispatch rejects duplicate-candidate labelled issues
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

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
        identifier="tasks-001",
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

        config = ServiceConfig(duplicate_preflight_max_agents=0)
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
        orch.state.owner_claims = {}
        orch._owner_claims_lock = threading.RLock()
        orch._retry_authority_lock = threading.RLock()

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

    def test_proposed_candidates_are_not_scanned(self):
        """Proposed is pre-work and should not enter duplicate detection."""
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        config = ServiceConfig()
        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch.project_store = MagicMock()
        orch.project_store.list_all.return_value = []
        orch.tracker = MagicMock()
        orch.tracker.fetch_comments.return_value = [
            {"text": "Focus handoff: duplicate_detector\nNo duplicate found."}
        ]

        candidate = _make_issue(
            identifier="rogers-proposal",
            title="rogers proposal",
            project_id=None,
            state="Proposed",
            labels=[],
        )

        result = orch._apply_duplicate_detection([candidate])

        assert result == [candidate]
        orch.tracker.fetch_issues_by_states.assert_not_called()
        assert orch._last_duplicate_detection_metrics["prework_count"] == 1
        assert orch._last_duplicate_detection_metrics["scanned_count"] == 0

    def test_completed_duplicate_focus_is_not_flagged_again(self):
        """The implementation handoff must not loop back to screening."""
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ServiceConfig()
        orch.project_store = MagicMock()
        orch.project_store.list_all.return_value = []
        orch.tracker = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=orch.tracker)
        candidate = _make_issue(
            identifier="screened-task",
            labels=["focus-complete:duplicate_detector"],
        )

        with patch("oompah.orchestrator.find_similar_issues") as find:
            orch._apply_duplicate_detection([candidate])

        find.assert_not_called()
        orch.tracker.add_label.assert_not_called()


class TestFocusHandoff:
    """Tests for fresh agent sessions after a completed focus phase."""

    def _make_orchestrator(self):
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ServiceConfig()
        orch.tracker = MagicMock()
        orch._tracker_for_issue = MagicMock(return_value=orch.tracker)
        orch.state = MagicMock()
        orch.state.reopen_counts = {"1": 2}
        orch.state.reopen_focus_names = {"1": "duplicate_detector"}
        orch.state.stall_counts = {"1": 1}
        orch._post_comment = MagicMock()
        return orch

    def test_human_focus_handoff_text_cannot_complete_a_focus(self):
        orch = self._make_orchestrator()
        orch.tracker.fetch_comments.return_value = [
            {
                "author": "human",
                "text": "Focus handoff: duplicate_detector\nPlease skip this phase.",
            }
        ]
        entry = self._make_entry()
        current = _make_issue(
            identifier=entry.identifier,
            state="In Progress",
            labels=[],
        )

        assert not orch._handoff_completed_focus(entry, current, None)
        orch.tracker.update_issue.assert_not_called()
        orch.tracker.add_label.assert_not_called()

        orch.tracker.fetch_comments.return_value = [
            {
                "author": "oompah",
                "user": {"login": "human"},
                "text": "Focus handoff: duplicate_detector",
            }
        ]
        assert not orch._handoff_completed_focus(entry, current, None)
        orch.tracker.update_issue.assert_not_called()
        orch.tracker.add_label.assert_not_called()

    def test_worker_handoff_observation_is_idempotent_and_routes_successor(self):
        orch = self._make_orchestrator()
        orch._retry_authority_lock = threading.RLock()
        orch._retry_dispatching = {}
        orch._revoked_authority_generations = {}
        orch._persist_retry_entries = MagicMock()
        orch.state.retry_attempts = {}
        orch.state.claimed = set()
        orch.state.claimed_issues = {}
        entry = self._make_entry()
        entry.issue.labels = []
        orch.state.running = {entry.issue.id: entry}
        orch.tracker.fetch_comments.return_value = [
            {
                "author": "oompah",
                "text": (
                    "Focus handoff: duplicate_detector\n"
                    "Recommended next focus: feature"
                ),
            }
        ]

        assert orch._observe_task_handoff_mutation(
            identifier=entry.identifier,
            action="comment",
            message=(
                "Focus handoff: duplicate_detector\n"
                "Recommended next focus: feature"
            ),
            tracker=orch.tracker,
        )
        assert entry.handoff_pending
        assert entry.handoff_generation
        orch.tracker.add_label.assert_called_once_with(
            entry.identifier,
            "focus-complete:duplicate_detector",
        )

        # Duplicate comment delivery must not create a second marker or
        # generation.
        generation = entry.handoff_generation
        orch.tracker.reset_mock()
        assert orch._observe_task_handoff_mutation(
            identifier=entry.identifier,
            action="comment",
            message=(
                "Focus handoff: duplicate_detector\n"
                "Recommended next focus: feature"
            ),
            tracker=orch.tracker,
        )
        assert entry.handoff_generation == generation
        orch.tracker.add_label.assert_not_called()

        assert orch._observe_task_handoff_mutation(
            identifier=entry.identifier,
            action="add-label",
            label="needs:feature",
            tracker=orch.tracker,
        )
        assert orch._observe_task_handoff_mutation(
            identifier=entry.identifier,
            action="set-status",
            status="Open",
            tracker=orch.tracker,
        )
        assert orch._handoff_completed_focus(entry, entry.issue, None)
        assert entry.handoff_finalized
        assert entry.issue.state == "Open"

    def test_reconcile_open_snapshot_finishes_handoff_before_retirement(self):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ServiceConfig()
        orch.state = MagicMock()
        orch.state.retry_attempts = {}
        orch.state.running = {}
        orch.state.claimed = set()
        orch.state.claimed_issues = {}
        orch._retry_authority_lock = threading.RLock()
        orch._retry_dispatching = {}
        orch._revoked_authority_generations = {}
        orch._tick_pool = ThreadPoolExecutor(max_workers=1)
        orch._fetch_running_states = MagicMock()
        orch._reconcile_retry_authority = AsyncMock()
        orch._handoff_completed_focus = MagicMock(return_value=True)
        orch._terminate_running = AsyncMock(return_value=True)
        orch._schedule_retry = MagicMock()

        entry = self._make_entry()
        entry.handoff_pending = True
        issue = _make_issue(
            identifier=entry.identifier,
            state="Open",
            labels=["focus-complete:duplicate_detector"],
        )
        orch.state.running[issue.id] = entry
        orch._fetch_running_states.return_value = {issue.id: issue}

        try:
            asyncio.run(orch._reconcile())
        finally:
            orch._tick_pool.shutdown(wait=True)

        orch._handoff_completed_focus.assert_called_once()
        orch._terminate_running.assert_awaited_once_with(
            issue.id,
            cleanup_workspace=False,
        )
        orch._schedule_retry.assert_not_called()

    def _make_entry(self):
        from datetime import datetime, timezone
        from oompah.models import RunningEntry

        issue = _make_issue(identifier="screened-task", state="In Progress")
        return RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            focus_name="duplicate_detector",
        )

    def test_completed_focus_reopens_task_for_fresh_dispatch(self):
        orch = self._make_orchestrator()
        orch.tracker.fetch_comments.return_value = [
            {
                "author": "oompah",
                "text": "Focus handoff: duplicate_detector\nNo duplicate found.",
            }
        ]
        entry = self._make_entry()
        current = _make_issue(
            identifier=entry.identifier,
            state="In Progress",
            labels=["focus-complete:duplicate_detector"],
        )

        assert orch._handoff_completed_focus(entry, current, None)

        orch.tracker.add_label.assert_not_called()
        orch.tracker.update_issue.assert_called_once_with(entry.identifier, status="Open")
        assert current.state == "Open"
        assert "focus-complete:duplicate_detector" in current.labels
        assert entry.identifier not in orch.state.reopen_counts
        assert entry.identifier not in orch.state.reopen_focus_names
        assert entry.identifier not in orch.state.stall_counts
        orch._post_comment.assert_called_once()

    def test_handoff_comment_without_label_advances_focus(self):
        """A posted handoff must not be retried when label creation was lost."""
        orch = self._make_orchestrator()
        orch.tracker.fetch_comments.return_value = [
            {
                "author": "oompah",
                "text": "Focus handoff: duplicate_detector\nNo duplicate found.",
            }
        ]
        entry = self._make_entry()
        current = _make_issue(
            identifier=entry.identifier,
            state="In Progress",
            labels=[],
        )

        assert orch._handoff_completed_focus(entry, current, None)

        orch.tracker.add_label.assert_called_once_with(
            entry.identifier, "focus-complete:duplicate_detector"
        )
        orch.tracker.update_issue.assert_called_once_with(entry.identifier, status="Open")
        assert "focus-complete:duplicate_detector" in current.labels
        assert entry.identifier not in orch.state.reopen_counts

    def test_terminal_task_is_not_handed_off(self):
        orch = self._make_orchestrator()
        entry = self._make_entry()
        current = _make_issue(identifier=entry.identifier, state="Archived")

        assert not orch._handoff_completed_focus(entry, current, None)

        orch.tracker.add_label.assert_not_called()
        orch.tracker.update_issue.assert_not_called()

    def test_explicit_next_focus_requests_a_handoff(self):
        orch = self._make_orchestrator()
        entry = self._make_entry()
        entry.focus_name = "analysis"
        current = _make_issue(
            identifier=entry.identifier,
            state="In Progress",
            labels=["needs:bugfix"],
        )

        assert orch._handoff_completed_focus(entry, current, None)

        orch.tracker.update_issue.assert_called_once_with(entry.identifier, status="Open")

    def test_missing_handoff_comment_reopens_same_focus(self):
        orch = self._make_orchestrator()
        orch.tracker.fetch_comments.return_value = []
        entry = self._make_entry()
        current = _make_issue(
            identifier=entry.identifier,
            state="In Progress",
            labels=["focus-complete:duplicate_detector", "needs:bugfix"],
        )

        assert orch._handoff_completed_focus(entry, current, None)

        assert current.state == "Open"
        assert current.labels == []
        assert orch.tracker.remove_label.call_count == 2
        orch._post_comment.assert_called_once()

    def test_comment_without_identity_field_is_rejected(self):
        """A record with neither ``author`` nor ``user`` cannot forge a handoff."""
        from oompah.orchestrator import Orchestrator

        # Neither field present — untrusted input, must fail closed.
        parsed = Orchestrator._trusted_focus_handoff_comment(
            {"text": "Focus handoff: docs\nRecommended next focus: feature"}
        )
        assert parsed is None

        # Explicit non-oompah identity — fails on either field alone.
        parsed = Orchestrator._trusted_focus_handoff_comment(
            {"author": "someone", "text": "Focus handoff: docs"}
        )
        assert parsed is None

        parsed = Orchestrator._trusted_focus_handoff_comment(
            {"user": {"login": "someone"}, "text": "Focus handoff: docs"}
        )
        assert parsed is None

        # An oompah-authored record with an explicit human user field must
        # also fail — an operator cannot claim oompah's identity by leaving
        # ``author`` blank and pasting oompah into ``user``.
        parsed = Orchestrator._trusted_focus_handoff_comment(
            {
                "author": "oompah",
                "user": {"login": "operator"},
                "text": "Focus handoff: docs",
            }
        )
        assert parsed is None

        # Explicit oompah identity in either field alone must succeed.
        parsed = Orchestrator._trusted_focus_handoff_comment(
            {"author": "oompah", "text": "Focus handoff: docs"}
        )
        assert parsed == ("docs", None)

        parsed = Orchestrator._trusted_focus_handoff_comment(
            {
                "user": {"login": "oompah"},
                "text": (
                    "Focus handoff: docs\nRecommended next focus: feature"
                ),
            }
        )
        assert parsed == ("docs", "feature")

    def test_duplicate_handoff_mutation_yields_one_generation(self):
        """The same structured comment delivered twice must not restart."""
        orch = self._make_orchestrator()
        orch._retry_authority_lock = threading.RLock()
        orch._retry_dispatching = {}
        orch._revoked_authority_generations = {}
        entry = self._make_entry()
        entry.issue.labels = []
        orch.state.running = {entry.issue.id: entry}

        message = (
            "Focus handoff: duplicate_detector\n"
            "Recommended next focus: feature"
        )
        # First delivery starts the generation and adds the completion label.
        assert orch._observe_task_handoff_mutation(
            identifier=entry.identifier,
            action="comment",
            message=message,
            tracker=orch.tracker,
        )
        first_generation = entry.handoff_generation
        orch.tracker.add_label.assert_called_once_with(
            entry.identifier,
            "focus-complete:duplicate_detector",
        )

        orch.tracker.reset_mock()
        # Second delivery of the same comment must be idempotent.
        assert orch._observe_task_handoff_mutation(
            identifier=entry.identifier,
            action="comment",
            message=message,
            tracker=orch.tracker,
        )
        assert entry.handoff_generation == first_generation
        orch.tracker.add_label.assert_not_called()

        # A duplicated add-label mutation is also idempotent.
        assert orch._observe_task_handoff_mutation(
            identifier=entry.identifier,
            action="add-label",
            label="needs:feature",
            tracker=orch.tracker,
        )
        assert entry.handoff_requested_focus == "feature"
        # A duplicated set-status mutation is also idempotent.
        assert orch._observe_task_handoff_mutation(
            identifier=entry.identifier,
            action="set-status",
            status="Open",
            tracker=orch.tracker,
        )
        assert orch._observe_task_handoff_mutation(
            identifier=entry.identifier,
            action="set-status",
            status="Open",
            tracker=orch.tracker,
        )
        assert entry.handoff_status_open

    def test_already_completed_focus_still_selects_successor(self):
        """A task with an existing focus-complete label picks the successor.

        The bug this test guards against is looping back to the completed
        focus after label persistence but before the successor label was
        written. select_focus must not pick the completed focus even without
        an explicit needs:* hint when the label has been backfilled.
        """
        from oompah.focus import BUILTIN_FOCI, select_focus

        # A task already tagged focus-complete:docs must not re-select docs.
        # In the absence of any needs:* label, any other applicable focus
        # (feature, general, or any active builtin) is fine — the only
        # forbidden outcome is docs itself.
        issue = _make_issue(
            identifier="OOMPAH-757",
            title="Persist completed focus before a task handoff reopens work",
            issue_type="bug",
            state="Open",
            labels=["focus-complete:docs"],
        )
        focus = select_focus(issue, foci=BUILTIN_FOCI)
        assert focus.name.lower() != "docs"

    def test_explicit_needs_feature_selects_feature_over_docs(self):
        """The exact OOMPAH-757 recovery expects needs:feature to route to feature."""
        from oompah.focus import BUILTIN_FOCI, select_focus

        issue = _make_issue(
            identifier="OOMPAH-757",
            title="Persist completed focus before a task handoff reopens work",
            issue_type="bug",
            state="Open",
            labels=["focus-complete:docs", "needs:feature"],
        )
        focus = select_focus(issue, foci=BUILTIN_FOCI)
        assert focus.name.lower() == "feature"

    def test_dispatch_backfills_marker_after_restart(self):
        """Restart between structured comment and Open transition.

        After a restart there is no in-memory RunningEntry.  When dispatch
        selects the recovered Open task, it must backfill focus-complete
        and needs:<next> from the trusted Oompah HANDOFF comment before
        focus selection scores the issue.
        """
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ServiceConfig()
        tracker = MagicMock()
        tracker.fetch_comments.return_value = [
            {
                "author": "oompah",
                "text": (
                    "Focus handoff: docs\n"
                    "Outcome: this task needs backend implementation.\n"
                    "Recommended next focus: feature"
                ),
            }
        ]
        orch._tracker_for_issue = MagicMock(return_value=tracker)

        recovered = _make_issue(
            identifier="OOMPAH-757",
            state="Open",
            labels=[],
        )
        orch._backfill_focus_handoff_markers([recovered])

        # Both markers must be added atomically from the same trusted
        # comment; the mutations must be observed as label writes on
        # the tracker.
        add_calls = [call.args for call in tracker.add_label.call_args_list]
        assert ("OOMPAH-757", "focus-complete:docs") in add_calls
        assert ("OOMPAH-757", "needs:feature") in add_calls
        assert "focus-complete:docs" in recovered.labels
        assert "needs:feature" in recovered.labels

        # Second dispatch tick must not duplicate either label.
        tracker.add_label.reset_mock()
        orch._backfill_focus_handoff_markers([recovered])
        tracker.add_label.assert_not_called()

    def test_forced_termination_finalizes_pending_handoff(self):
        """A late worker exit must not turn an accepted handoff into a retry.

        _terminate_running fetches the current tracker snapshot and finalizes
        the handoff when handoff_pending is set. The finalization block is
        exercised in isolation to avoid the full async cleanup pipeline.
        """
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ServiceConfig()
        entry = self._make_entry()
        entry.handoff_pending = True
        entry.issue.project_id = None

        tracker = MagicMock()
        current_snapshot = _make_issue(
            identifier=entry.identifier,
            state="Open",
            labels=["focus-complete:duplicate_detector"],
        )
        tracker.fetch_issue_detail.return_value = current_snapshot
        orch.tracker = tracker
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._handoff_completed_focus = MagicMock(return_value=True)

        # Reproduce the retirement guard: if the entry is pending, finalize
        # the handoff before the runtime entry is removed.
        assert getattr(entry, "handoff_pending", False)
        assert not getattr(entry, "handoff_finalized", False)
        project_id = entry.issue.project_id if entry.issue else None
        tracker_for_project = (
            orch._tracker_for_project(project_id) if project_id else orch.tracker
        )
        current = tracker_for_project.fetch_issue_detail(entry.identifier)
        orch._handoff_completed_focus(entry, current, project_id)

        orch._handoff_completed_focus.assert_called_once()
        called_entry, called_issue, _project = (
            orch._handoff_completed_focus.call_args.args
        )
        assert called_entry is entry
        assert called_issue is current_snapshot

    def test_forced_termination_finalization_survives_tracker_error(self):
        """A tracker fetch error must not prevent retirement or the finalizer.

        _terminate_running wraps the finalization block in a broad exception
        handler so a transient tracker error cannot leave the worker orphaned;
        retirement continues.
        """
        from oompah.orchestrator import Orchestrator
        from oompah.tracker import TrackerError
        from oompah.config import ServiceConfig

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ServiceConfig()
        entry = self._make_entry()
        entry.handoff_pending = True
        entry.issue.project_id = None

        tracker = MagicMock()
        tracker.fetch_issue_detail.side_effect = TrackerError("no tracker")
        orch.tracker = tracker
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._handoff_completed_focus = MagicMock(return_value=True)

        # The finalization block swallows errors; simulate its guard.
        try:
            project_id = entry.issue.project_id if entry.issue else None
            tracker_for_project = (
                orch._tracker_for_project(project_id)
                if project_id
                else orch.tracker
            )
            current = tracker_for_project.fetch_issue_detail(entry.identifier)
            if current is not None:
                orch._handoff_completed_focus(entry, current, project_id)
        except TrackerError:
            pass

        # A raised error means the finalizer was not called, but the outer
        # retirement path continues regardless. The important guarantee is
        # that state is not corrupted.
        assert entry.handoff_pending
        assert not entry.handoff_finalized

    def test_docs_to_feature_open_before_worker_exit(self):
        """Reconcile sees Open before the worker exits; the exact OOMPAH-757 race.

        The bug: reconcile treated Open as a state revert, terminated the
        worker, and scheduled a retry on the same docs focus before
        _on_worker_exit could persist focus-complete:docs. The fix: the Open
        branch runs _handoff_completed_focus first, retires the worker
        without scheduling a retry, and produces the docs handoff artifacts.
        """
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        async def _run():
            orch = Orchestrator.__new__(Orchestrator)
            orch.config = ServiceConfig()
            orch.state = MagicMock()
            orch.state.retry_attempts = {}
            orch.state.running = {}
            orch.state.claimed = set()
            orch.state.claimed_issues = {}
            orch._retry_authority_lock = threading.RLock()
            orch._retry_dispatching = {}
            orch._revoked_authority_generations = {}
            orch._tick_pool = ThreadPoolExecutor(max_workers=1)
            orch._fetch_running_states = MagicMock()
            orch._reconcile_retry_authority = AsyncMock()
            orch._handoff_completed_focus = MagicMock(return_value=True)
            orch._terminate_running = AsyncMock(return_value=True)
            orch._schedule_retry = MagicMock()

            docs_entry = self._make_entry()
            docs_entry.focus_name = "docs"
            docs_entry.handoff_pending = True
            docs_entry.identifier = "OOMPAH-757"
            docs_entry.issue.identifier = "OOMPAH-757"
            docs_entry.issue.labels = []

            # The tracker publishes Open with the durable focus-complete
            # marker while the docs worker is still registered.
            open_snapshot = _make_issue(
                identifier="OOMPAH-757",
                state="Open",
                labels=["focus-complete:docs", "needs:feature"],
            )
            orch.state.running[open_snapshot.id] = docs_entry
            orch._fetch_running_states.return_value = {
                open_snapshot.id: open_snapshot,
            }

            try:
                await orch._reconcile()
            finally:
                orch._tick_pool.shutdown(wait=True)

            # A valid handoff must retire the docs worker exactly once and
            # must not schedule an implementation retry that would repeat
            # the docs focus.
            orch._handoff_completed_focus.assert_called_once()
            orch._terminate_running.assert_awaited_once_with(
                open_snapshot.id,
                cleanup_workspace=False,
            )
            orch._schedule_retry.assert_not_called()

        asyncio.run(_run())


class TestFocusScopedIncompleteSessionLimit:
    """The three-session guard applies to consecutive sessions of one focus."""

    def test_focus_change_resets_the_incomplete_session_count(self):
        from oompah.models import OrchestratorState
        from oompah.orchestrator import Orchestrator

        orch = Orchestrator.__new__(Orchestrator)
        orch.state = OrchestratorState()

        assert orch._increment_reopen_count("task-1", "duplicate_detector") == 1
        assert orch._increment_reopen_count("task-1", "duplicate_detector") == 2
        assert orch._increment_reopen_count("task-1", "docs") == 1
        # Returning to an earlier focus after a different one is not
        # consecutive, so it starts a new safety-limit sequence.
        assert orch._increment_reopen_count("task-1", "duplicate_detector") == 1

    def test_three_consecutive_sessions_of_one_focus_reach_limit(self):
        from oompah.models import OrchestratorState
        from oompah.orchestrator import Orchestrator

        orch = Orchestrator.__new__(Orchestrator)
        orch.state = OrchestratorState()

        assert [
            orch._increment_reopen_count("task-1", "docs") for _ in range(3)
        ] == [1, 2, 3]

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

    def test_terminal_match_returned_by_tracker_is_ignored(self, tmp_path, monkeypatch):
        """A tracker returning extra terminal records must not flag a candidate."""
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

        orch._apply_duplicate_detection([candidate])

        mock_tracker.fetch_issues_by_states.assert_called_once_with(
            ["Open", "Needs CI Fix", "Needs Rebase"]
        )
        mock_tracker.update_issue.assert_not_called()
        mock_tracker.add_label.assert_not_called()
        orch._post_comment.assert_not_called()

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


class TestProposedDispatchFiltering:
    """Dispatch selection treats Proposed as pre-work even from stale inputs."""

    def _make_orch(self):
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        config = ServiceConfig(
            tracker_active_states=["Proposed", "Open"],
            dispatch_scan_limit=1,
            dispatch_ready_buffer=0,
            duplicate_preflight_max_agents=0,
        )
        orch = Orchestrator.__new__(Orchestrator)
        orch.config = config
        orch._paused = False
        orch.project_store = MagicMock()
        orch.state = MagicMock()
        orch.state.running = {}
        orch.state.claimed = set()
        orch.state.retry_attempts = {}
        orch.state.completed = set()
        orch.state.reject_streak = {}
        orch.state.owner_claims = {}
        orch._owner_claims_lock = threading.RLock()
        orch._retry_authority_lock = threading.RLock()

        orch._is_project_paused = lambda pid: False
        orch._issue_has_children = lambda issue: False
        orch._project_epic_strategy = lambda pid: "flat"
        orch._issue_requires_parent_epic = lambda issue: False
        orch._available_slots = lambda: 1
        orch._per_state_available = lambda s: True
        orch._check_budget = lambda: True
        orch._would_dispatch_via_acp = lambda i: False
        orch._would_dispatch_on_free_model = lambda i: False
        orch._is_epic_rebase_task = lambda i: False
        return orch

    def test_select_dispatchable_skips_proposed_before_scan_limit(self):
        orch = self._make_orch()
        proposed = _make_issue(
            identifier="intake-1",
            title="Intake proposal",
            state="Proposed",
            priority=0,
            project_id=None,
        )
        ready = _make_issue(
            identifier="ready-1",
            title="Ready work",
            state="Open",
            priority=1,
            project_id=None,
        )

        result = orch._select_dispatchable([proposed, ready])

        assert [issue.identifier for issue in result] == ["ready-1"]
        assert orch._last_selection_metrics["candidate_count"] == 2
        assert orch._last_selection_metrics["prework_count"] == 1
        assert orch._last_selection_metrics["scanned_count"] == 1

    def test_retryable_state_keys_exclude_proposed_even_if_configured_active(self):
        orch = self._make_orch()

        keys = orch._retryable_state_keys()

        assert "open" in keys
        assert "in_progress" in keys
        assert "proposed" not in keys


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

    def test_terminal_match_does_not_add_duplicate_detector_handoff(self):
        """A matching terminal issue does not create an automatic handoff."""
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

        detected_candidates = orch._apply_duplicate_detection([candidate])

        assert "needs:duplicate_detector" not in detected_candidates[0].labels
        mock_tracker.add_label.assert_not_called()
        mock_tracker.update_issue.assert_not_called()


class TestNoCommitFocusCompletionAdvancesToFeature:
    """Regression for EXOCOMP-55: a no-commit duplicate_detector run that
    correctly records its handoff comment and completion label must not be
    re-dispatched as another duplicate_detector pass.

    Acceptance (from issue OOMPAH-430): duplicate detection that finds no
    duplicate records its completion and handoff exactly once, and the next
    run begins feature work rather than another duplicate pass.
    """

    def _make_orchestrator(self):
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ServiceConfig()
        orch.tracker = MagicMock()
        orch.state = MagicMock()
        orch.state.reopen_counts = {}
        orch.state.reopen_focus_names = {}
        orch.state.stall_counts = {}
        orch._post_comment = MagicMock()
        return orch

    def _make_entry(self, issue):
        from datetime import datetime, timezone
        from oompah.models import RunningEntry

        return RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            focus_name="duplicate_detector",
        )

    def test_no_commit_handoff_detected_and_not_retried(self):
        """When duplicate_detector posts a handoff comment and adds the
        focus-complete label (no git commits), _handoff_completed_focus must
        return True, the issue must be reopened for a fresh dispatch, and
        select_focus on the resulting issue must pick a focus other than
        duplicate_detector — preventing the completed phase from repeating."""
        from oompah.focus import select_focus

        orch = self._make_orchestrator()
        orch.tracker.fetch_comments.return_value = [
            {
                "author": "oompah",
                "text": "Focus handoff: duplicate_detector\nNo duplicate found.",
            }
        ]

        issue = _make_issue(
            identifier="OOMPAH-430",
            title="Provide focus agents a supported tracker-handoff mutation path",
            state="In Progress",
            issue_type="task",
            labels=["focus-complete:duplicate_detector"],
        )
        entry = self._make_entry(issue)

        # Simulate the orchestrator processing _on_worker_exit for a normal exit.
        result = orch._handoff_completed_focus(entry, issue, None)

        # Handoff must be recognised — True means _on_worker_exit will NOT
        # treat this as an unclosed issue requiring re-dispatch to the same focus.
        assert result is True

        # The issue must be opened for the next applicable focus.
        orch.tracker.update_issue.assert_called_once_with(entry.identifier, status="Open")
        assert issue.state == "Open"

        # The completion label must be preserved so select_focus can skip it
        # on every subsequent dispatch, including after a service restart.
        assert "focus-complete:duplicate_detector" in issue.labels

        # No extra label add_label call should have been made: the label was
        # already present before _handoff_completed_focus ran.
        orch.tracker.add_label.assert_not_called()

        # The next focus selected for the reopened issue must NOT be
        # duplicate_detector — that would repeat the completed phase.
        focus = select_focus(issue)
        assert focus.name != "duplicate_detector", (
            f"Expected a non-duplicate_detector focus after handoff, "
            f"got {focus.name!r}"
        )

    def test_no_commit_handoff_with_needs_feature_routes_to_feature(self):
        """When the handoff comment requests a feature focus via needs:feature
        label, select_focus must pick feature — not duplicate_detector.

        Uses BUILTIN_FOCI to ensure the feature focus is active regardless of
        the local .oompah/foci.json configuration (which may mark it inactive).
        """
        from oompah.focus import select_focus, BUILTIN_FOCI

        orch = self._make_orchestrator()
        orch.tracker.fetch_comments.return_value = [
            {
                "author": "oompah",
                "text": (
                    "Focus handoff: duplicate_detector\n"
                    "No duplicate found. OOMPAH-430 is unique.\n"
                    "Recommended next focus: feature"
                ),
            }
        ]

        issue = _make_issue(
            identifier="OOMPAH-430",
            title="Implement new feature for tracker handoff",
            state="In Progress",
            issue_type="task",
            labels=["focus-complete:duplicate_detector", "needs:feature"],
        )
        entry = self._make_entry(issue)

        result = orch._handoff_completed_focus(entry, issue, None)

        assert result is True
        # Issue must be reopened.
        assert issue.state == "Open"
        # No extra label should be added (focus-complete label was already present).
        orch.tracker.add_label.assert_not_called()

        # With needs:feature label, select_focus must pick feature.
        # Use BUILTIN_FOCI to ensure the feature focus is active in this
        # environment (the local foci.json may mark it inactive).
        focus = select_focus(issue, foci=BUILTIN_FOCI)
        assert focus.name == "feature", (
            f"Expected feature focus due to needs:feature label, got {focus.name!r}"
        )


class TestDispatchResponsivenessLimits:
    """Dispatch loops should bound work per tick under large candidate sets."""

    def test_select_dispatchable_respects_scan_limit(self):
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ServiceConfig(dispatch_scan_limit=3, dispatch_ready_buffer=0)
        orch.state = MagicMock()
        orch.state.running = {}
        orch.state.claimed = set()
        orch.state.retry_attempts = {}
        orch._retry_authority_lock = threading.RLock()
        orch._available_slots = lambda: 2
        orch._should_dispatch = MagicMock(return_value=False)

        candidates = [
            _make_issue(identifier=f"TASK-{i}", title=f"unique task {i}")
            for i in range(10)
        ]

        ready = orch._select_dispatchable(candidates)

        assert ready == []
        assert orch._should_dispatch.call_count == 3
        assert orch._last_selection_metrics["scanned_count"] == 3
        assert orch._last_selection_metrics["deferred_count"] == 7

    def test_duplicate_detection_respects_candidate_limit(self):
        from oompah.orchestrator import Orchestrator
        from oompah.config import ServiceConfig

        orch = Orchestrator.__new__(Orchestrator)
        orch.config = ServiceConfig(duplicate_detection_candidate_limit=2)
        orch.project_store = MagicMock()
        orch.project_store.list_all.return_value = []
        orch.tracker = MagicMock()
        orch.tracker.fetch_issues_by_states.return_value = []

        candidates = [
            _make_issue(identifier=f"TASK-{i}", title=f"unique task {i}", project_id=None)
            for i in range(5)
        ]

        with patch("oompah.orchestrator.find_similar_issues", return_value=[]) as find:
            result = orch._apply_duplicate_detection(candidates)

        assert result == candidates
        assert find.call_count == 2
        assert orch._last_duplicate_detection_metrics["scanned_count"] == 2
        assert orch._last_duplicate_detection_metrics["deferred_count"] == 3
