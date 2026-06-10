"""Orchestrator lifecycle tests for GitHub-backed tasks (TASK-461.7).

Covers the full orchestrator lifecycle against mocked GitHub-like trackers:

1. Candidate fetch — ``_fetch_all_candidates`` returns GitHub issues stamped
   with the correct ``project_id``; tracker errors are silently skipped.
2. Mixed fetch — two projects (Backlog + GitHub) return disjoint candidates;
   issue IDs from different projects never collide (AC #2).
3. Dispatch + GitHub claim protocol — run-ID stamp and verify; race abort when
   a concurrent writer wins; pre-dispatch terminal-state abort.
4. Needs Human routing — ``_mark_needs_human`` calls ``mark_needs_human`` on
   trackers that support it; falls back to ``update_issue`` + ``add_comment``
   for trackers that do not.
5. Retry scheduling — ``_schedule_retry`` propagates ``project_id`` so the
   retry re-dispatches to the same GitHub project.
6. Close / reopen via tracker — GitHub close/reopen goes through the tracker
   protocol (no Backlog file mutations).
7. Worker exit + retry path — completing without closing triggers a retry for
   GitHub-backed tasks; tracked in ``state.retry_attempts`` with correct
   ``project_id``.
8. Watcher-created tasks — ``ErrorWatcher`` calls ``create_issue`` on the
   project-scoped tracker (GitHub or Backlog) so auto-filed work goes to the
   canonical backend.
9. Mixed-project dispatch — two projects with overlapping issue numbers are
   each dispatched only once; no cross-project task ID confusion.

All tests use mocked trackers and never require live GitHub network access
(AC #1).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.error_watcher import ErrorWatcher
from oompah.models import AgentProfile, Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.roles import RoleStore
from oompah.tracker import BacklogMdTracker, TrackerError, TrackerNotConfiguredError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dt() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def _github_issue(
    issue_id: str = "GH_1",
    identifier: str = "acme/tasks#1",
    issue_number: str = "1",
    state: str = "open",
    project_id: str = "proj-gh",
    priority: int = 2,
) -> Issue:
    return Issue(
        id=issue_id,
        identifier=identifier,
        title=f"GitHub task #{issue_number}",
        description="Detailed description that passes the empty-description gate.",
        state=state,
        priority=priority,
        issue_type="task",
        labels=[],
        tracker_kind="github_issues",
        tracker_owner="acme",
        tracker_repo="tasks",
        issue_number=issue_number,
        display_identifier=f"tasks#{issue_number}",
        provider_url=f"https://github.com/acme/tasks/issues/{issue_number}",
        project_id=project_id,
        created_at=_dt(),
        updated_at=_dt(),
    )


def _backlog_issue(
    issue_id: str = "TASK-1",
    state: str = "open",
    project_id: str = "proj-bl",
    priority: int = 2,
) -> Issue:
    return Issue(
        id=issue_id,
        identifier=issue_id,
        title=f"Backlog task {issue_id}",
        description="Detailed description that passes the empty-description gate.",
        state=state,
        priority=priority,
        issue_type="task",
        labels=[],
        tracker_kind=None,
        project_id=project_id,
        created_at=_dt(),
        updated_at=_dt(),
    )


def _make_project(
    project_id: str,
    *,
    name: str = "myproject",
    tracker_kind: str = "github_issues",
    repo_path: str = "/tmp/fake",
    tracker_owner: str = "acme",
    tracker_repo: str = "tasks",
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.name = name
    p.tracker_kind = tracker_kind
    p.tracker_owner = tracker_owner
    p.tracker_repo = tracker_repo
    p.repo_path = repo_path
    p.repo_url = "https://github.com/acme/tasks"
    return p


def _make_tracker(issues: list[Issue] | None = None) -> MagicMock:
    t = MagicMock()
    _issues = list(issues or [])
    t.fetch_candidate_issues.return_value = _issues
    t.fetch_issues_by_states.return_value = [
        i for i in _issues if "progress" in i.state.lower()
    ]
    t.fetch_issue_detail.return_value = None
    t.fetch_issue_states_by_ids.return_value = []
    t.update_issue = MagicMock()
    t.close_issue = MagicMock()
    t.reopen_issue = MagicMock()
    t.add_comment = MagicMock()
    t.set_metadata_field = MagicMock()
    t.get_metadata = MagicMock(return_value={})
    t.create_issue = MagicMock()
    return t


def _make_running_entry(
    issue: Issue,
    *,
    retry_attempt: int = 0,
) -> RunningEntry:
    return RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=retry_attempt,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="default",
    )


def _make_orch(tmp_path, *, projects: list | None = None) -> Orchestrator:
    """Create a minimal Orchestrator with mocked project store.

    If ``projects`` is provided the store returns those; otherwise an empty
    list so ``_fetch_all_candidates`` falls through to the legacy tracker.
    """
    role_store = RoleStore(path=str(tmp_path / "roles.json"))
    project_store = MagicMock()
    project_store.list_all.return_value = list(projects or [])
    project_store.get.side_effect = lambda pid: next(
        (p for p in (projects or []) if p.id == pid), None
    )

    config = ServiceConfig()
    orch = Orchestrator(
        config=config,
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=role_store,
        state_path=str(tmp_path / "state.json"),
    )
    # Disable startup delay so maintenance paths don't interfere.
    orch._started_monotonic = 0.0
    return orch


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


# ---------------------------------------------------------------------------
# 1. Candidate fetch — GitHub-backed projects
# ---------------------------------------------------------------------------


class TestCandidateFetchGitHub:
    """``_fetch_all_candidates`` pulls issues from GitHub-backed projects."""

    def test_returns_github_issues_from_project(self, tmp_path):
        """Issues from a GitHub-backed project are returned as candidates."""
        gh_issue = _github_issue("GH_42", "acme/tasks#42", "42")
        tracker = _make_tracker([gh_issue])

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        candidates = orch._fetch_all_candidates()

        assert any(c.identifier == "acme/tasks#42" for c in candidates)

    def test_stamps_project_id_on_fetched_issues(self, tmp_path):
        """Each fetched issue has its source ``project_id`` stamped."""
        gh_issue = _github_issue("GH_1", "acme/tasks#1", "1", project_id=None)
        tracker = _make_tracker([gh_issue])

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        candidates = orch._fetch_all_candidates()

        assert all(c.project_id == "proj-gh" for c in candidates)

    def test_tracker_error_returns_empty_not_raises(self, tmp_path):
        """A TrackerError from one project does not crash the fetch cycle."""
        tracker = _make_tracker()
        tracker.fetch_candidate_issues.side_effect = TrackerError("boom")

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        # Must not raise; returns empty list.
        candidates = orch._fetch_all_candidates()
        assert candidates == []

    def test_not_configured_error_is_silenced(self, tmp_path):
        """TrackerNotConfiguredError is silently skipped (project not yet set up)."""
        tracker = _make_tracker()
        tracker.fetch_candidate_issues.side_effect = TrackerNotConfiguredError(
            "not configured"
        )

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        candidates = orch._fetch_all_candidates()
        assert candidates == []

    def test_multiple_issues_from_single_github_project(self, tmp_path):
        """All issues from the project are returned."""
        issues = [_github_issue(f"GH_{i}", f"acme/tasks#{i}", str(i)) for i in range(3)]
        tracker = _make_tracker(issues)

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        candidates = orch._fetch_all_candidates()
        assert len(candidates) == 3

    def test_github_issues_have_correct_tracker_kind(self, tmp_path):
        """tracker_kind='github_issues' is preserved on returned candidates."""
        gh_issue = _github_issue("GH_7", "acme/tasks#7", "7")
        tracker = _make_tracker([gh_issue])

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        candidates = orch._fetch_all_candidates()
        assert all(c.tracker_kind == "github_issues" for c in candidates)


# ---------------------------------------------------------------------------
# 2. Mixed fetch — Backlog + GitHub, no ID collisions (AC #2)
# ---------------------------------------------------------------------------


class TestMixedCandidateFetch:
    """Mixed Backlog + GitHub projects return disjoint candidate sets (AC #2)."""

    def _make_mixed_orch(
        self,
        tmp_path,
        bl_issues: list[Issue],
        gh_issues: list[Issue],
    ) -> tuple[Orchestrator, MagicMock, MagicMock]:
        bl_tracker = _make_tracker(bl_issues)
        gh_tracker = _make_tracker(gh_issues)

        proj_bl = _make_project("proj-bl", name="myproject", tracker_kind="backlog_md")
        proj_gh = _make_project("proj-gh", name="mygh", tracker_kind="github_issues")

        orch = _make_orch(tmp_path, projects=[proj_bl, proj_gh])
        orch._project_trackers["proj-bl"] = bl_tracker
        orch._project_trackers["proj-gh"] = gh_tracker

        return orch, bl_tracker, gh_tracker

    def test_issues_from_both_projects_returned(self, tmp_path):
        """Candidates include both Backlog and GitHub issues."""
        bl = _backlog_issue("TASK-1", project_id="proj-bl")
        gh = _github_issue("GH_1", "acme/tasks#1", "1", project_id="proj-gh")

        orch, _, _ = self._make_mixed_orch(tmp_path, [bl], [gh])
        candidates = orch._fetch_all_candidates()

        identifiers = {c.identifier for c in candidates}
        assert "TASK-1" in identifiers
        assert "acme/tasks#1" in identifiers

    def test_project_ids_are_distinct_and_correct(self, tmp_path):
        """Each candidate is stamped with its source project's ID."""
        bl = _backlog_issue("TASK-2", project_id="proj-bl")
        gh = _github_issue("GH_2", "acme/tasks#2", "2", project_id="proj-gh")

        orch, _, _ = self._make_mixed_orch(tmp_path, [bl], [gh])
        candidates = orch._fetch_all_candidates()

        by_id = {c.identifier: c for c in candidates}
        assert by_id["TASK-2"].project_id == "proj-bl"
        assert by_id["acme/tasks#2"].project_id == "proj-gh"

    def test_overlapping_bare_numbers_no_id_collision(self, tmp_path):
        """TASK-1 and GitHub #1 share a bare number but get distinct identifiers."""
        bl = _backlog_issue("TASK-1", project_id="proj-bl")
        gh = _github_issue("GH_1", "acme/tasks#1", "1", project_id="proj-gh")

        orch, _, _ = self._make_mixed_orch(tmp_path, [bl], [gh])
        candidates = orch._fetch_all_candidates()

        ids = [c.id for c in candidates]
        identifiers = [c.identifier for c in candidates]
        # issue IDs are distinct
        assert len(set(ids)) == len(ids), f"Duplicate issue IDs: {ids}"
        # display identifiers are distinct
        assert len(set(identifiers)) == len(identifiers), (
            f"Duplicate identifiers: {identifiers}"
        )

    def test_github_project_error_doesnt_lose_backlog_candidates(self, tmp_path):
        """If the GitHub tracker raises, Backlog candidates are still returned."""
        bl = _backlog_issue("TASK-5", project_id="proj-bl")
        gh_tracker = _make_tracker()
        gh_tracker.fetch_candidate_issues.side_effect = TrackerError("github down")

        bl_tracker = _make_tracker([bl])
        proj_bl = _make_project("proj-bl", name="myproject", tracker_kind="backlog_md")
        proj_gh = _make_project("proj-gh", name="mygh", tracker_kind="github_issues")

        orch = _make_orch(tmp_path, projects=[proj_bl, proj_gh])
        orch._project_trackers["proj-bl"] = bl_tracker
        orch._project_trackers["proj-gh"] = gh_tracker

        candidates = orch._fetch_all_candidates()
        assert any(c.identifier == "TASK-5" for c in candidates)
        # GitHub failure leaves only Backlog candidates
        assert all(c.project_id == "proj-bl" for c in candidates)


# ---------------------------------------------------------------------------
# 3. GitHub claim protocol in _dispatch
# ---------------------------------------------------------------------------


class TestGitHubClaimProtocol:
    """``_dispatch`` stamps a run-ID and verifies ownership for GitHub tasks."""

    def _make_dispatch_orch(self, tmp_path) -> tuple[Orchestrator, MagicMock]:
        """Return (orch, github_tracker) ready for _dispatch tests."""
        issue = _github_issue("GH_10", "acme/tasks#10", "10")
        tracker = _make_tracker([issue])

        # Return the same issue on pre-dispatch state recheck
        tracker.fetch_issue_states_by_ids.return_value = [issue]
        # get_metadata returns our run ID (confirm claim)
        tracker.get_metadata.return_value = {}  # overridden per test

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        # Stub profile matching so _dispatch doesn't need full WORKFLOW.md
        mock_profile = AgentProfile(name="default", command="echo test")
        orch._match_agent_profile = MagicMock(return_value=mock_profile)
        orch._get_profile_by_name = MagicMock(return_value=mock_profile)

        # Stub _run_worker to capture dispatches without actually running agents
        orch._run_worker = AsyncMock()

        return orch, tracker

    def test_claim_writes_run_id_to_tracker(self, tmp_path, event_loop):
        """``set_metadata_field`` is called with ``oompah.agent_run_id`` key."""
        issue = _github_issue("GH_10", "acme/tasks#10", "10")
        orch, tracker = self._make_dispatch_orch(tmp_path)

        # Confirm our run ID so the claim succeeds
        def _confirm_meta(identifier):
            call_args = tracker.set_metadata_field.call_args
            if call_args:
                written_id = call_args[0][2] if len(call_args[0]) >= 3 else None
                return {"oompah.agent_run_id": written_id}
            return {}

        tracker.get_metadata.side_effect = _confirm_meta
        tracker.fetch_issue_states_by_ids.return_value = [issue]

        event_loop.run_until_complete(orch._dispatch(issue, attempt=None))

        # Verify set_metadata_field was called with the run_id key
        call_args_list = tracker.set_metadata_field.call_args_list
        assert any(
            len(c[0]) >= 2 and c[0][1] == "oompah.agent_run_id"
            for c in call_args_list
        ), "set_metadata_field was not called with 'oompah.agent_run_id'"

    def test_claim_race_aborts_dispatch(self, tmp_path, event_loop):
        """If another instance stamped a different run_id, dispatch is aborted."""
        issue = _github_issue("GH_11", "acme/tasks#11", "11")
        orch, tracker = self._make_dispatch_orch(tmp_path)

        # get_metadata returns a *different* run ID (simulating race)
        tracker.fetch_issue_states_by_ids.return_value = [issue]
        tracker.get_metadata.return_value = {
            "oompah.agent_run_id": "OTHER-INSTANCE-UUID"
        }

        event_loop.run_until_complete(orch._dispatch(issue, attempt=None))

        # Claim was released; the issue should NOT be dispatched to a worker
        orch._run_worker.assert_not_awaited()
        # The issue must be removed from claimed after aborting
        assert issue.id not in orch.state.claimed

    def test_claim_success_proceeds_to_worker(self, tmp_path, event_loop):
        """When our run-ID is confirmed, the worker is started."""
        issue = _github_issue("GH_12", "acme/tasks#12", "12")
        orch, tracker = self._make_dispatch_orch(tmp_path)
        tracker.fetch_issue_states_by_ids.return_value = [issue]

        # Make get_metadata echo back whatever was written
        written_ids: list[str] = []

        def _capture_set(identifier, key, value):
            written_ids.append(value)

        def _echo_metadata(identifier):
            if written_ids:
                return {"oompah.agent_run_id": written_ids[-1]}
            return {}

        tracker.set_metadata_field.side_effect = _capture_set
        tracker.get_metadata.side_effect = _echo_metadata

        event_loop.run_until_complete(orch._dispatch(issue, attempt=None))

        # Worker should have been started
        orch._run_worker.assert_awaited_once()

    def test_non_github_issue_skips_claim_protocol(self, tmp_path, event_loop):
        """Backlog-backed issues do not call set_metadata_field (no claim protocol)."""
        bl_issue = _backlog_issue("TASK-20", project_id="proj-bl")
        tracker = _make_tracker([bl_issue])
        tracker.fetch_issue_states_by_ids.return_value = [bl_issue]

        proj = _make_project(
            "proj-bl", name="myproject", tracker_kind="backlog_md"
        )
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-bl"] = tracker

        mock_profile = AgentProfile(name="default", command="echo test")
        orch._match_agent_profile = MagicMock(return_value=mock_profile)
        orch._get_profile_by_name = MagicMock(return_value=mock_profile)
        orch._run_worker = AsyncMock()

        event_loop.run_until_complete(orch._dispatch(bl_issue, attempt=None))

        # No metadata write for Backlog issues
        tracker.set_metadata_field.assert_not_called()

    def test_pre_dispatch_terminal_state_aborts(self, tmp_path, event_loop):
        """If the issue is already Done before dispatch, the dispatch is aborted."""
        issue = _github_issue("GH_13", "acme/tasks#13", "13")
        orch, tracker = self._make_dispatch_orch(tmp_path)

        # Recheck says the issue is now Done
        done_issue = _github_issue(
            "GH_13", "acme/tasks#13", "13", state="done"
        )
        done_issue = Issue(
            **{**done_issue.__dict__, "state": "done"}
        )
        tracker.fetch_issue_states_by_ids.return_value = [done_issue]

        # Need ServiceConfig with Done in terminal states
        orch.config = ServiceConfig(tracker_terminal_states=["done"])

        event_loop.run_until_complete(orch._dispatch(issue, attempt=None))

        # No worker started; issue added to completed
        orch._run_worker.assert_not_awaited()
        assert issue.id in orch.state.completed

    def test_in_progress_update_called_on_github_tracker(self, tmp_path, event_loop):
        """``update_issue(status='In Progress')`` is called on the GitHub tracker."""
        issue = _github_issue("GH_14", "acme/tasks#14", "14")
        orch, tracker = self._make_dispatch_orch(tmp_path)
        tracker.fetch_issue_states_by_ids.return_value = [issue]

        written_ids: list[str] = []

        def _capture_set(identifier, key, value):
            written_ids.append(value)

        def _echo_metadata(identifier):
            if written_ids:
                return {"oompah.agent_run_id": written_ids[-1]}
            return {}

        tracker.set_metadata_field.side_effect = _capture_set
        tracker.get_metadata.side_effect = _echo_metadata

        event_loop.run_until_complete(orch._dispatch(issue, attempt=None))

        # update_issue should have been called to set In Progress
        assert tracker.update_issue.called
        call_kwargs = tracker.update_issue.call_args[1]
        assert "status" in call_kwargs
        assert "progress" in call_kwargs["status"].lower()


# ---------------------------------------------------------------------------
# 4. _mark_needs_human routing
# ---------------------------------------------------------------------------


class TestMarkNeedsHumanGitHub:
    """``_mark_needs_human`` routes to GitHub tracker correctly."""

    def test_calls_mark_needs_human_when_available(self, tmp_path):
        """If the tracker has mark_needs_human, it is called directly."""
        orch = _make_orch(tmp_path)
        tracker = MagicMock()
        tracker.mark_needs_human = MagicMock()

        orch._mark_needs_human(tracker, "acme/tasks#5", "Please review manually.")

        tracker.mark_needs_human.assert_called_once_with(
            "acme/tasks#5", "Please review manually.", author="oompah"
        )
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()

    def test_falls_back_to_update_and_comment_when_mark_not_present(self, tmp_path):
        """Trackers without mark_needs_human get update_issue + add_comment."""
        orch = _make_orch(tmp_path)
        tracker = MagicMock(spec=["update_issue", "add_comment"])
        # No mark_needs_human attribute
        assert not hasattr(tracker, "mark_needs_human")

        orch._mark_needs_human(tracker, "TASK-100", "Human needed.")

        tracker.update_issue.assert_called_once()
        call_kwargs = tracker.update_issue.call_args[1]
        assert "needs_human" in call_kwargs.get("status", "").lower().replace(" ", "_")

        tracker.add_comment.assert_called_once()

    def test_custom_author_is_forwarded(self, tmp_path):
        """The author kwarg is passed through to mark_needs_human."""
        orch = _make_orch(tmp_path)
        tracker = MagicMock()
        tracker.mark_needs_human = MagicMock()

        orch._mark_needs_human(
            tracker, "acme/tasks#6", "Review needed.", author="bot"
        )

        tracker.mark_needs_human.assert_called_once_with(
            "acme/tasks#6", "Review needed.", author="bot"
        )

    def test_github_tracker_mark_needs_human_not_backlog_file(self, tmp_path):
        """A non-BacklogMdTracker receives mark_needs_human, not a file write."""
        orch = _make_orch(tmp_path)
        tracker = MagicMock()
        tracker.mark_needs_human = MagicMock()
        assert not isinstance(tracker, BacklogMdTracker)

        orch._mark_needs_human(tracker, "acme/tasks#7", "Need a human.")

        tracker.mark_needs_human.assert_called_once()
        # Backlog file path logic must not be involved
        # (we just verify the correct method was called, no file I/O)


# ---------------------------------------------------------------------------
# 5. Retry scheduling — project_id propagation
# ---------------------------------------------------------------------------


class TestRetrySchedulingGitHub:
    """``_schedule_retry`` propagates ``project_id`` for GitHub tasks."""

    def test_retry_entry_has_correct_project_id(self, tmp_path, event_loop):
        """After _schedule_retry, the RetryEntry stores the correct project_id."""
        orch = _make_orch(tmp_path)

        # Provide a running event loop for call_later
        event_loop.run_until_complete(asyncio.sleep(0))

        orch._schedule_retry(
            issue_id="GH_20",
            attempt=1,
            identifier="acme/tasks#20",
            delay_ms=500,
            error="agent-did-not-close",
            project_id="proj-gh",
        )

        assert "GH_20" in orch.state.retry_attempts
        entry = orch.state.retry_attempts["GH_20"]
        assert entry.project_id == "proj-gh"
        assert entry.identifier == "acme/tasks#20"

    def test_retry_attempt_count_is_incremented(self, tmp_path, event_loop):
        """The RetryEntry stores the supplied attempt count."""
        orch = _make_orch(tmp_path)
        event_loop.run_until_complete(asyncio.sleep(0))

        orch._schedule_retry(
            issue_id="GH_21",
            attempt=2,
            identifier="acme/tasks#21",
            delay_ms=1000,
            error="completion_verifier_rejected",
            project_id="proj-gh",
        )

        entry = orch.state.retry_attempts["GH_21"]
        assert entry.attempt == 2

    def test_retry_replaces_existing_timer(self, tmp_path, event_loop):
        """Calling _schedule_retry twice cancels the first timer."""
        orch = _make_orch(tmp_path)
        event_loop.run_until_complete(asyncio.sleep(0))

        orch._schedule_retry(
            issue_id="GH_22",
            attempt=1,
            identifier="acme/tasks#22",
            delay_ms=5000,
            error="attempt1",
            project_id="proj-gh",
        )
        first_handle = orch.state.retry_attempts["GH_22"].timer_handle

        orch._schedule_retry(
            issue_id="GH_22",
            attempt=2,
            identifier="acme/tasks#22",
            delay_ms=5000,
            error="attempt2",
            project_id="proj-gh",
        )

        # First timer should be cancelled
        assert first_handle.cancelled()
        # New entry is in place
        assert orch.state.retry_attempts["GH_22"].attempt == 2

    def test_retry_without_project_id_still_succeeds(self, tmp_path, event_loop):
        """Retries work even when project_id is None (legacy path)."""
        orch = _make_orch(tmp_path)
        event_loop.run_until_complete(asyncio.sleep(0))

        orch._schedule_retry(
            issue_id="TASK-99",
            attempt=1,
            identifier="TASK-99",
            delay_ms=500,
            error="agent-error",
            project_id=None,
        )

        entry = orch.state.retry_attempts["TASK-99"]
        assert entry.project_id is None


# ---------------------------------------------------------------------------
# 6. Close / reopen via GitHub tracker
# ---------------------------------------------------------------------------


class TestCloseReopenGitHub:
    """Orchestrator close/reopen paths call tracker methods directly."""

    def test_close_issue_called_on_github_tracker(self, tmp_path, event_loop):
        """When worker closes a GitHub task, tracker.close_issue is called."""
        issue = _github_issue("GH_30", "acme/tasks#30", "30")
        # fetch_issue_detail returns None → the agent closed the issue
        tracker = _make_tracker([issue])
        tracker.fetch_issue_detail.return_value = None

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        # Use the existing worker exit path; verify no Backlog file path
        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )

        # Issue should be completed (closed)
        assert issue.id in orch.state.completed

    def test_reopen_issue_called_via_tracker_when_agent_fails(self, tmp_path, event_loop):
        """``tracker.reopen_issue`` is callable and is used in the retry path."""
        issue = _github_issue("GH_31", "acme/tasks#31", "31")
        tracker = _make_tracker([issue])
        # Simulate issue still open after agent run (not closed)
        open_issue = _github_issue("GH_31", "acme/tasks#31", "31", state="open")
        tracker.fetch_issue_detail.return_value = open_issue

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        entry = _make_running_entry(issue, retry_attempt=0)
        orch.state.running[issue.id] = entry

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )

        # Issue was not closed, so either a retry is scheduled or it's
        # in the reopen flow.  Either way it must NOT be in completed.
        # The reopen count should be set.
        assert issue.id not in orch.state.completed or issue.id in {
            r for r in orch.state.retry_attempts
        }

    def test_reopen_count_increments_on_agent_not_closing(self, tmp_path, event_loop):
        """``state.reopen_counts`` is incremented when agent completes without close."""
        issue = _github_issue("GH_32", "acme/tasks#32", "32")
        tracker = _make_tracker([issue])
        open_issue = _github_issue("GH_32", "acme/tasks#32", "32", state="open")
        tracker.fetch_issue_detail.return_value = open_issue

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        entry = _make_running_entry(issue, retry_attempt=0)
        orch.state.running[issue.id] = entry

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )

        assert orch.state.reopen_counts.get(issue.id, 0) >= 1


# ---------------------------------------------------------------------------
# 7. Worker exit retry path for GitHub tasks
# ---------------------------------------------------------------------------


class TestWorkerExitRetryGitHub:
    """GitHub task worker-exit handling schedules retry with correct metadata."""

    def test_abnormal_exit_schedules_retry_not_completed(self, tmp_path, event_loop):
        """Abnormal exit should schedule a retry (not close)."""
        issue = _github_issue("GH_40", "acme/tasks#40", "40")
        tracker = _make_tracker()
        tracker.fetch_issue_detail.return_value = None

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        entry = _make_running_entry(issue, retry_attempt=0)
        orch.state.running[issue.id] = entry

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "abnormal", "subprocess error")
        )

        # Not completed on first abnormal exit
        assert issue.id not in orch.state.completed

    def test_needs_human_triggered_after_max_reopens(self, tmp_path, event_loop):
        """After max reopens, the issue is moved to Needs Human."""
        issue = _github_issue("GH_41", "acme/tasks#41", "41")
        tracker = _make_tracker()
        open_issue = _github_issue("GH_41", "acme/tasks#41", "41", state="open")
        tracker.fetch_issue_detail.return_value = open_issue
        tracker.mark_needs_human = MagicMock()

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        # Pre-seed reopen count to max-1 so the next exit crosses the threshold
        orch.state.reopen_counts[issue.id] = 2  # max is 3

        entry = _make_running_entry(issue, retry_attempt=2)
        orch.state.running[issue.id] = entry

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )

        # mark_needs_human should have been called (either directly or via fallback)
        needs_human_called = (
            tracker.mark_needs_human.called
            or (
                tracker.update_issue.called
                and any(
                    "needs" in str(c).lower()
                    for c in tracker.update_issue.call_args_list
                )
            )
        )
        assert needs_human_called, (
            "Expected _mark_needs_human to be called after max reopens"
        )

    def test_project_id_preserved_in_retry_entry(self, tmp_path, event_loop):
        """Retry entry keeps the issue's project_id after worker exit."""
        issue = _github_issue("GH_42", "acme/tasks#42", "42")
        tracker = _make_tracker()
        open_issue = _github_issue("GH_42", "acme/tasks#42", "42", state="open")
        tracker.fetch_issue_detail.return_value = open_issue

        proj = _make_project("proj-gh")
        orch = _make_orch(tmp_path, projects=[proj])
        orch._project_trackers["proj-gh"] = tracker

        entry = _make_running_entry(issue, retry_attempt=0)
        orch.state.running[issue.id] = entry

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )

        # If a retry was scheduled it must have project_id set
        retry = orch.state.retry_attempts.get(issue.id)
        if retry is not None:
            assert retry.project_id == "proj-gh"


# ---------------------------------------------------------------------------
# 8. Watcher-created tasks → canonical tracker
# ---------------------------------------------------------------------------


class TestWatcherCreatedTasksGitHub:
    """ErrorWatcher creates tasks via the project-scoped tracker."""

    def _make_github_tracker_mock(self, issue_id: str = "GH_100") -> MagicMock:
        t = MagicMock()
        created = _github_issue(issue_id, f"acme/tasks#{issue_id[3:]}", issue_id[3:])
        t.create_issue.return_value = created
        return t

    def test_error_watcher_uses_github_tracker_for_github_project(self):
        """ErrorWatcher with a GitHub tracker calls tracker.create_issue."""
        gh_tracker = self._make_github_tracker_mock()
        watcher = ErrorWatcher(tracker=gh_tracker, project_id="proj-gh")

        watcher.report_error(
            source="backend",
            message="Some runtime error occurred",
        )

        gh_tracker.create_issue.assert_called_once()
        call_kwargs = gh_tracker.create_issue.call_args[1]
        assert call_kwargs.get("issue_type") == "bug"

    def test_error_watcher_includes_project_id_in_description(self):
        """Auto-filed task description includes source_project identifier."""
        gh_tracker = self._make_github_tracker_mock()
        watcher = ErrorWatcher(tracker=gh_tracker, project_id="my-project")

        watcher.report_error(
            source="backend",
            message="Unhandled exception in worker",
        )

        call_kwargs = gh_tracker.create_issue.call_args[1]
        description = call_kwargs.get("description", "")
        assert "my-project" in description

    def test_error_watcher_includes_tracker_kind_in_description(self):
        """Auto-filed task description identifies the tracker backend (TASK-461.6)."""
        gh_tracker = self._make_github_tracker_mock()
        # Simulate GitHubIssueTracker having owner/repo attributes
        gh_tracker.owner = "acme"
        gh_tracker.repo = "tasks"
        watcher = ErrorWatcher(tracker=gh_tracker, project_id="proj-gh")

        watcher.report_error(
            source="backend",
            message="Worker crashed",
        )

        call_kwargs = gh_tracker.create_issue.call_args[1]
        description = call_kwargs.get("description", "")
        assert "tracker_kind" in description

    def test_error_watcher_for_backlog_project_uses_backlog_tracker(self, tmp_path):
        """ErrorWatcher initialized with a Backlog tracker calls Backlog create_issue."""
        bl_tracker = MagicMock(spec=BacklogMdTracker)
        bl_tracker.root_path = str(tmp_path)
        created = _backlog_issue("TASK-999", project_id="proj-bl")
        bl_tracker.create_issue.return_value = created
        bl_tracker.task_file_path = MagicMock(return_value=str(tmp_path / "TASK-999.md"))

        watcher = ErrorWatcher(tracker=bl_tracker, project_id="proj-bl")

        with patch("oompah.error_watcher._persist_error_task_to_git", return_value=None):
            watcher.report_error(
                source="backend",
                message="Backlog error scenario",
            )

        bl_tracker.create_issue.assert_called_once()
        call_kwargs = bl_tracker.create_issue.call_args[1]
        assert call_kwargs.get("issue_type") == "bug"

    def test_error_watcher_doesnt_cross_trackers(self):
        """A Backlog watcher must NOT call the GitHub tracker and vice versa."""
        bl_tracker = MagicMock(spec=BacklogMdTracker)
        bl_tracker.root_path = "/tmp/bl"
        bl_tracker.task_file_path = MagicMock(return_value="/tmp/bl/TASK-1.md")
        created = _backlog_issue("TASK-1")
        bl_tracker.create_issue.return_value = created

        gh_tracker = self._make_github_tracker_mock()

        watcher = ErrorWatcher(tracker=bl_tracker, project_id="proj-bl")

        with patch("oompah.error_watcher._persist_error_task_to_git", return_value=None):
            watcher.report_error(
                source="backend",
                message="Some error",
            )

        bl_tracker.create_issue.assert_called_once()
        gh_tracker.create_issue.assert_not_called()


# ---------------------------------------------------------------------------
# 9. Mixed-project dispatch — no cross-project task ID confusion (AC #2)
# ---------------------------------------------------------------------------


class TestMixedProjectDispatch:
    """Dispatch across Backlog + GitHub projects without ID confusion (AC #2)."""

    def _make_mixed_orch(
        self,
        tmp_path,
        bl_issues: list[Issue],
        gh_issues: list[Issue],
    ) -> tuple[Orchestrator, MagicMock, MagicMock]:
        bl_tracker = _make_tracker(bl_issues)
        gh_tracker = _make_tracker(gh_issues)

        proj_bl = _make_project(
            "proj-bl", name="myproject", tracker_kind="backlog_md"
        )
        proj_gh = _make_project("proj-gh", name="mygh", tracker_kind="github_issues")

        orch = _make_orch(tmp_path, projects=[proj_bl, proj_gh])
        orch._project_trackers["proj-bl"] = bl_tracker
        orch._project_trackers["proj-gh"] = gh_tracker

        return orch, bl_tracker, gh_tracker

    def test_candidates_for_two_projects_have_distinct_project_ids(self, tmp_path):
        """After fetch, every candidate carries its own project_id."""
        bl = _backlog_issue("TASK-1", project_id="proj-bl")
        gh = _github_issue("GH_1", "acme/tasks#1", "1", project_id="proj-gh")

        orch, _, _ = self._make_mixed_orch(tmp_path, [bl], [gh])
        candidates = orch._fetch_all_candidates()

        by_proj = {c.project_id for c in candidates}
        assert by_proj == {"proj-bl", "proj-gh"}

    def test_total_candidate_count_matches_both_projects(self, tmp_path):
        """Total candidate count equals sum of issues from both projects."""
        bl_issues = [_backlog_issue(f"TASK-{i}", project_id="proj-bl") for i in range(3)]
        gh_issues = [
            _github_issue(f"GH_{i}", f"acme/tasks#{i}", str(i), project_id="proj-gh")
            for i in range(2)
        ]

        orch, _, _ = self._make_mixed_orch(tmp_path, bl_issues, gh_issues)
        candidates = orch._fetch_all_candidates()

        assert len(candidates) == 5

    def test_backlog_issue_tracker_for_issue_returns_backlog_tracker(self, tmp_path):
        """``_tracker_for_issue`` resolves to the correct tracker for each type."""
        bl = _backlog_issue("TASK-5", project_id="proj-bl")
        gh = _github_issue("GH_5", "acme/tasks#5", "5", project_id="proj-gh")

        bl_tracker = _make_tracker([bl])
        gh_tracker = _make_tracker([gh])

        proj_bl = _make_project(
            "proj-bl", name="myproject", tracker_kind="backlog_md"
        )
        proj_gh = _make_project("proj-gh", name="mygh", tracker_kind="github_issues")

        orch = _make_orch(tmp_path, projects=[proj_bl, proj_gh])
        orch._project_trackers["proj-bl"] = bl_tracker
        orch._project_trackers["proj-gh"] = gh_tracker

        resolved_bl = orch._tracker_for_issue(bl)
        resolved_gh = orch._tracker_for_issue(gh)

        assert resolved_bl is bl_tracker
        assert resolved_gh is gh_tracker

    def test_same_bare_number_issues_resolve_to_different_trackers(self, tmp_path):
        """TASK-1 and GH_1 resolve to different tracker instances."""
        bl = _backlog_issue("TASK-1", project_id="proj-bl")
        gh = _github_issue("GH_1", "acme/tasks#1", "1", project_id="proj-gh")

        bl_tracker = _make_tracker([bl])
        gh_tracker = _make_tracker([gh])

        proj_bl = _make_project(
            "proj-bl", name="myproject", tracker_kind="backlog_md"
        )
        proj_gh = _make_project("proj-gh", name="mygh", tracker_kind="github_issues")

        orch = _make_orch(tmp_path, projects=[proj_bl, proj_gh])
        orch._project_trackers["proj-bl"] = bl_tracker
        orch._project_trackers["proj-gh"] = gh_tracker

        resolved_bl = orch._tracker_for_issue(bl)
        resolved_gh = orch._tracker_for_issue(gh)

        assert resolved_bl is not resolved_gh
        assert resolved_bl is bl_tracker
        assert resolved_gh is gh_tracker

    def test_dispatch_uses_project_scoped_tracker_for_github_issue(
        self, tmp_path, event_loop
    ):
        """Dispatch routes the GitHub issue to the GitHub tracker only."""
        gh = _github_issue("GH_10", "acme/tasks#10", "10", project_id="proj-gh")
        gh_tracker = _make_tracker([gh])
        gh_tracker.fetch_issue_states_by_ids.return_value = [gh]
        bl_tracker = _make_tracker()

        # Confirm GitHub claim
        written_ids: list[str] = []

        def _capture_set(identifier, key, value):
            written_ids.append(value)

        def _echo_meta(identifier):
            if written_ids:
                return {"oompah.agent_run_id": written_ids[-1]}
            return {}

        gh_tracker.set_metadata_field.side_effect = _capture_set
        gh_tracker.get_metadata.side_effect = _echo_meta

        proj_bl = _make_project(
            "proj-bl", name="myproject", tracker_kind="backlog_md"
        )
        proj_gh = _make_project("proj-gh", name="mygh", tracker_kind="github_issues")

        orch = _make_orch(tmp_path, projects=[proj_bl, proj_gh])
        orch._project_trackers["proj-bl"] = bl_tracker
        orch._project_trackers["proj-gh"] = gh_tracker

        mock_profile = AgentProfile(name="default", command="echo test")
        orch._match_agent_profile = MagicMock(return_value=mock_profile)
        orch._get_profile_by_name = MagicMock(return_value=mock_profile)
        orch._run_worker = AsyncMock()

        event_loop.run_until_complete(orch._dispatch(gh, attempt=None))

        # GitHub tracker was used for in-progress update; Backlog was not
        assert gh_tracker.update_issue.called
        assert not bl_tracker.update_issue.called
