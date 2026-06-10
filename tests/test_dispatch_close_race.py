"""Tests for the close/dispatch race that caused oompah-zlz_2-4jq to keep
re-appearing as in_progress after the user closed it.

Two bugs covered:
1. ``_dispatch`` used to write status=in_progress without verifying the
   issue's current state. If the candidate fetch predated a close, the
   write silently re-opened the bead.
2. The UI close handler terminated the running worker but didn't touch
   ``state.retry_attempts``. A retry timer scheduled before the close
   would fire later, fetch candidates, and re-dispatch.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, RetryEntry
from oompah.orchestrator import Orchestrator


def _make_config() -> ServiceConfig:
    return ServiceConfig()


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


def _make_orchestrator(tmp_path) -> Orchestrator:
    return Orchestrator(
        config=_make_config(),
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "service_state.json"),
    )


def _issue(state: str = "open", **overrides) -> Issue:
    defaults = dict(
        id="i-abc",
        identifier="proj-1",
        title="Test issue",
        state=state,
        priority=2,
        issue_type="task",
        labels=[],
    )
    defaults.update(overrides)
    return Issue(**defaults)


class TestDispatchRecheckSkipsClosedIssue:
    """_dispatch must re-fetch the issue's state right before writing
    status=in_progress and bail if it's terminal — otherwise a UI close
    that lands between candidate fetch and dispatch is silently undone."""

    def test_aborts_when_state_moved_to_closed_since_fetch(self, tmp_path, event_loop):
        orch = _make_orchestrator(tmp_path)
        # Stale candidate (looks open) but tracker now says closed.
        stale = _issue(state="open")
        fresh = _issue(state="closed")

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_states_by_ids.return_value = [fresh]

        with patch.object(orch, "_tracker_for_issue", return_value=mock_tracker):
            event_loop.run_until_complete(orch._dispatch(stale, attempt=None))

        # No update_issue(status=in_progress) should have been called.
        for call in mock_tracker.update_issue.call_args_list:
            assert call.kwargs.get("status") != "in_progress", (
                f"Re-opened a closed issue via dispatch: {call!r}"
            )
        # State bookkeeping reflects the abort.
        assert stale.id not in orch.state.claimed
        assert stale.id in orch.state.completed
        # No worker entry should have been created either.
        assert stale.id not in orch.state.running

    def test_proceeds_when_state_still_active(self, tmp_path, event_loop):
        orch = _make_orchestrator(tmp_path)
        stale = _issue(state="open")
        fresh = _issue(state="open")

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_states_by_ids.return_value = [fresh]
        # Avoid actually constructing a session.
        with (
            patch.object(orch, "_tracker_for_issue", return_value=mock_tracker),
            patch.object(orch, "_run_worker", new=MagicMock(
                return_value=asyncio.sleep(0))),
        ):
            event_loop.run_until_complete(orch._dispatch(stale, attempt=None))

        # update_issue should have been called with the canonical in-progress status.
        in_progress_calls = [
            c for c in mock_tracker.update_issue.call_args_list
            if c.kwargs.get("status") == "In Progress"
        ]
        assert len(in_progress_calls) == 1, (
            f"Expected one in_progress write, got: {mock_tracker.update_issue.call_args_list!r}"
        )

    def test_running_entry_uses_post_update_backlog_status(self, tmp_path, event_loop):
        orch = _make_orchestrator(tmp_path)
        orch.config.tracker_active_states = ["To Do", "In Progress"]
        stale = _issue(state="To Do")
        pre_update = _issue(state="To Do")
        post_update = _issue(state="In Progress")

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_states_by_ids.side_effect = [
            [pre_update],
            [post_update],
        ]
        with (
            patch.object(orch, "_tracker_for_issue", return_value=mock_tracker),
            patch.object(orch, "_run_worker", new=MagicMock(
                return_value=asyncio.sleep(0))),
        ):
            event_loop.run_until_complete(orch._dispatch(stale, attempt=None))

        entry = orch.state.running[stale.id]
        assert entry.issue.state == "In Progress"

        if not entry.worker_task.done():
            entry.worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                event_loop.run_until_complete(entry.worker_task)

    def test_recheck_failure_does_not_block_dispatch(self, tmp_path, event_loop):
        """If the recheck fetch raises, fall through to the original
        behaviour (write in_progress) — better than blocking dispatch
        on a transient tracker hiccup."""
        orch = _make_orchestrator(tmp_path)
        stale = _issue(state="open")

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_states_by_ids.side_effect = RuntimeError("boom")

        with (
            patch.object(orch, "_tracker_for_issue", return_value=mock_tracker),
            patch.object(orch, "_run_worker", new=MagicMock(
                return_value=asyncio.sleep(0))),
        ):
            event_loop.run_until_complete(orch._dispatch(stale, attempt=None))

        in_progress_calls = [
            c for c in mock_tracker.update_issue.call_args_list
            if c.kwargs.get("status") == "In Progress"
        ]
        assert len(in_progress_calls) == 1


class TestUiCloseCancelsPendingRetry:
    """When the user closes via UI, any pending retry timer must be
    cancelled — otherwise it fires later and re-dispatches a closed bead."""

    def test_pending_retry_cancelled_when_issue_closed_via_ui(self, tmp_path):
        from fastapi.testclient import TestClient
        from oompah.server import app
        import oompah.server as srv

        orch = _make_orchestrator(tmp_path)

        # Seed a pending retry as if a worker had failed.
        cancel_called = {"flag": False}

        class FakeTimer:
            def __init__(self):
                self._cancelled = False
            def cancelled(self):
                return self._cancelled
            def cancel(self):
                self._cancelled = True
                cancel_called["flag"] = True

        orch.state.retry_attempts["i-abc"] = RetryEntry(
            issue_id="i-abc",
            identifier="proj-1",
            attempt=2,
            due_at_ms=0.0,
            timer_handle=FakeTimer(),
            error="connection refused",
        )
        orch.state.claimed.add("i-abc")

        # Patch the tracker so close_issue is a noop.
        mock_tracker = MagicMock()
        with (
            patch("oompah.server._get_tracker", return_value=mock_tracker),
            patch.object(srv, "_orchestrator", orch),
        ):
            client = TestClient(app)
            res = client.patch(
                "/api/v1/issues/proj-1",
                json={"status": "closed", "project_id": "proj-1"},
            )
        assert res.status_code == 200, res.text

        # Bookkeeping: retry cancelled, claim cleared, completed marked.
        assert cancel_called["flag"] is True, "retry timer was not cancelled"
        assert "i-abc" not in orch.state.retry_attempts
        assert "i-abc" not in orch.state.claimed
        assert "i-abc" in orch.state.completed
        # tracker.close_issue should have been invoked.
        mock_tracker.close_issue.assert_called_once_with("proj-1")


# ---------------------------------------------------------------------------
# Pause must also cancel pending retries and block the retry path.
# Covers the user-reported case: paused service + manual move-to-open
# resulted in one ticket popping back to in_progress because a retry
# timer fired while paused and bypassed the dispatch loop's paused check.
# ---------------------------------------------------------------------------

class TestPauseCancelsPendingRetries:
    def test_pause_cancels_all_retry_timers(self, tmp_path, event_loop):
        orch = _make_orchestrator(tmp_path)

        cancelled: dict[str, bool] = {"a": False, "b": False}

        class FakeTimer:
            def __init__(self, key: str):
                self._k = key
                self._cancelled = False
            def cancelled(self):
                return self._cancelled
            def cancel(self):
                self._cancelled = True
                cancelled[self._k] = True

        for k in ("a", "b"):
            orch.state.retry_attempts[k] = RetryEntry(
                issue_id=k, identifier=f"id-{k}",
                attempt=1, due_at_ms=0.0,
                timer_handle=FakeTimer(k),
                error="something",
            )
            orch.state.claimed.add(k)

        orch.pause()

        # Both retries cancelled and the dict drained.
        assert cancelled == {"a": True, "b": True}
        assert orch.state.retry_attempts == {}
        # claimed should be cleared for the cancelled retries too.
        assert "a" not in orch.state.claimed
        assert "b" not in orch.state.claimed


class TestDispatchRejectsWhilePaused:
    """Even if a retry task somehow makes it to _dispatch while paused,
    the dispatch must abort instead of writing in_progress."""

    def test_dispatch_aborts_when_paused(self, tmp_path, event_loop):
        orch = _make_orchestrator(tmp_path)
        orch._paused = True

        mock_tracker = MagicMock()
        with patch.object(orch, "_tracker_for_issue", return_value=mock_tracker):
            event_loop.run_until_complete(
                orch._dispatch(_issue(state="open"), attempt=2)
            )

        # No state writes should have happened.
        assert mock_tracker.update_issue.call_count == 0
        # Even the recheck fetch should not have been called — paused
        # short-circuits before any I/O.
        assert mock_tracker.fetch_issue_states_by_ids.call_count == 0


# ---------------------------------------------------------------------------
# GitHub run-id claim protocol (TASK-461.2)
#
# For GitHub-backed issues oompah writes a unique run ID to
# oompah.agent_run_id, re-reads it, and aborts if a different run ID was
# observed (another instance won the race).  BacklogMd projects skip the
# protocol and keep the current single-process dispatch lock behaviour.
# ---------------------------------------------------------------------------

def _github_issue(state: str = "open", **overrides) -> Issue:
    """Return a minimal GitHub-backed Issue."""
    defaults = dict(
        id="gh-789",
        identifier="owner/repo#42",
        title="GitHub test issue",
        state=state,
        priority=1,
        issue_type="task",
        labels=[],
        tracker_kind="github_issues",
    )
    defaults.update(overrides)
    return Issue(**defaults)


class TestGitHubClaimRunIdProtocol:
    """_dispatch must implement the run-ID claim protocol for GitHub tasks."""

    def test_claim_race_detected_aborts_dispatch(self, tmp_path, event_loop):
        """When another instance writes a different run_id after ours,
        dispatch must abort without starting a worker."""
        orch = _make_orchestrator(tmp_path)
        issue = _github_issue(state="open")
        fresh = _github_issue(state="open")

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_states_by_ids.return_value = [fresh]
        # Simulate a different run_id winning the race: get_metadata returns
        # a run_id that doesn't match what we wrote.
        mock_tracker.get_metadata.return_value = {
            "oompah.agent_run_id": "foreign-run-id-from-other-instance"
        }

        with patch.object(orch, "_tracker_for_issue", return_value=mock_tracker):
            event_loop.run_until_complete(orch._dispatch(issue, attempt=None))

        # set_metadata_field must have been called with our run_id.
        assert mock_tracker.set_metadata_field.call_count == 1
        _call_args = mock_tracker.set_metadata_field.call_args
        assert _call_args.args[1] == "oompah.agent_run_id"
        our_run_id = _call_args.args[2]
        assert our_run_id  # must be non-empty

        # get_metadata must have been called to verify the claim.
        mock_tracker.get_metadata.assert_called_once()

        # The foreign run_id does NOT match ours → dispatch must abort.
        assert issue.id not in orch.state.claimed, (
            "claimed set should be cleared on race loss"
        )
        assert issue.id not in orch.state.running, (
            "no worker must start when the claim race is lost"
        )

    def test_claim_succeeds_when_run_id_matches(self, tmp_path, event_loop):
        """When the re-read run_id matches ours, dispatch proceeds normally."""
        orch = _make_orchestrator(tmp_path)
        issue = _github_issue(state="open")
        fresh = _github_issue(state="open")

        captured: dict[str, str] = {}

        def _set_meta(identifier, key, value):
            captured["run_id"] = value

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_states_by_ids.return_value = [fresh]
        mock_tracker.set_metadata_field.side_effect = _set_meta
        # Return the same run_id we wrote → we own the claim.
        mock_tracker.get_metadata.side_effect = (
            lambda _id: {"oompah.agent_run_id": captured.get("run_id", "")}
        )

        with (
            patch.object(orch, "_tracker_for_issue", return_value=mock_tracker),
            patch.object(
                orch, "_run_worker", new=MagicMock(return_value=asyncio.sleep(0))
            ),
        ):
            event_loop.run_until_complete(orch._dispatch(issue, attempt=None))

        # update_issue(status=In Progress) must have been called.
        in_progress_calls = [
            c for c in mock_tracker.update_issue.call_args_list
            if c.kwargs.get("status") == "In Progress"
        ]
        assert len(in_progress_calls) == 1, (
            f"Expected one In Progress write, got {mock_tracker.update_issue.call_args_list!r}"
        )
        # Worker entry must exist.
        assert issue.id in orch.state.running, (
            "RunningEntry must be created when claim succeeds"
        )

    def test_backlog_issue_skips_run_id_protocol(self, tmp_path, event_loop):
        """BacklogMd-backed issues must NOT call set_metadata_field."""
        orch = _make_orchestrator(tmp_path)
        # Issue with no tracker_kind → BacklogMd path
        issue = _issue(state="open")
        fresh = _issue(state="open")

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_states_by_ids.return_value = [fresh]

        with (
            patch.object(orch, "_tracker_for_issue", return_value=mock_tracker),
            patch.object(
                orch, "_run_worker", new=MagicMock(return_value=asyncio.sleep(0))
            ),
        ):
            event_loop.run_until_complete(orch._dispatch(issue, attempt=None))

        # set_metadata_field must NOT be called for non-GitHub issues.
        assert mock_tracker.set_metadata_field.call_count == 0, (
            "BacklogMd dispatch must not use the run-id claim protocol"
        )
        assert mock_tracker.get_metadata.call_count == 0, (
            "BacklogMd dispatch must not read metadata for claim verification"
        )

    def test_run_id_failure_falls_through_gracefully(self, tmp_path, event_loop):
        """If set_metadata_field or get_metadata raises, dispatch must
        still proceed rather than blocking the queue."""
        orch = _make_orchestrator(tmp_path)
        issue = _github_issue(state="open")
        fresh = _github_issue(state="open")

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_states_by_ids.return_value = [fresh]
        mock_tracker.set_metadata_field.side_effect = RuntimeError("network error")

        with (
            patch.object(orch, "_tracker_for_issue", return_value=mock_tracker),
            patch.object(
                orch, "_run_worker", new=MagicMock(return_value=asyncio.sleep(0))
            ),
        ):
            event_loop.run_until_complete(orch._dispatch(issue, attempt=None))

        # Despite the failure, dispatch must have proceeded.
        in_progress_calls = [
            c for c in mock_tracker.update_issue.call_args_list
            if c.kwargs.get("status") == "In Progress"
        ]
        assert len(in_progress_calls) == 1, (
            "Dispatch must proceed even when run-id claim fails"
        )
        assert issue.id in orch.state.running


class TestSnapshotIncludesTrackerKind:
    """get_snapshot running rows must expose tracker_kind (AC #2)."""

    def test_running_row_has_tracker_kind_for_github_issue(self, tmp_path):
        """A GitHub-backed issue in the running dict surfaces tracker_kind."""
        orch = _make_orchestrator(tmp_path)
        from datetime import datetime, timezone
        from unittest.mock import MagicMock
        from oompah.models import RunningEntry

        gh_issue = _github_issue(state="In Progress")
        fake_task = MagicMock()
        fake_task.done.return_value = False

        orch.state.running["gh-789"] = RunningEntry(
            worker_task=fake_task,
            identifier=gh_issue.identifier,
            issue=gh_issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="default",
        )

        snap = orch.get_snapshot()
        rows = {r["issue_id"]: r for r in snap["running"]}
        assert "gh-789" in rows
        assert rows["gh-789"]["tracker_kind"] == "github_issues", (
            f"Expected tracker_kind=github_issues, got {rows['gh-789'].get('tracker_kind')!r}"
        )
        assert rows["gh-789"]["issue_identifier"] == "owner/repo#42"

    def test_running_row_tracker_kind_none_for_backlog_issue(self, tmp_path):
        """A BacklogMd issue surfaces tracker_kind=None in the snapshot."""
        orch = _make_orchestrator(tmp_path)
        from datetime import datetime, timezone
        from unittest.mock import MagicMock
        from oompah.models import RunningEntry

        bl_issue = _issue(state="In Progress")
        fake_task = MagicMock()
        fake_task.done.return_value = False

        orch.state.running["i-abc"] = RunningEntry(
            worker_task=fake_task,
            identifier=bl_issue.identifier,
            issue=bl_issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="default",
        )

        snap = orch.get_snapshot()
        rows = {r["issue_id"]: r for r in snap["running"]}
        assert "i-abc" in rows
        assert rows["i-abc"]["tracker_kind"] is None
