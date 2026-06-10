"""Tests for the orchestrator wiring of the completion verifier
(oompah-zlz_2-y0ns).

Covers:
* Verifier disabled by default → close goes through.
* Verifier enabled + clean diff → close goes through.
* Verifier enabled + AC mentions a file the diff doesn't touch →
  bead is reopened, a diagnostic comment is posted, and a retry is
  scheduled.
* Three consecutive rejections fail open (let the close stick).
* Workspace-not-found fails open.
* GitHub-backed tasks: terminal state is re-read from GitHub via
  fetch_issue_detail; no Backlog workspace files are consulted
  (TASK-461.4).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from oompah.completion_verifier import (
    ExtractedReferences,
    Stage1Result,
    VerifierResult,
)
from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.tracker import BacklogMdTracker


def _make_issue(
    issue_id: str = "iss-1",
    identifier: str = "test-001",
    description: str = "",
    issue_type: str = "feature",
    labels: list[str] | None = None,
    project_id: str | None = None,
) -> Issue:
    return Issue(
        id=issue_id,
        identifier=identifier,
        title="Some issue",
        description=description,
        state="in_progress",
        labels=list(labels or []),
        priority=2,
        issue_type=issue_type,
        project_id=project_id,
    )


def _make_running_entry(issue: Issue, *, retry_attempt: int = 0) -> RunningEntry:
    return RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=retry_attempt,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="default",
    )


def _closed_issue(identifier: str, description: str = "", labels=None) -> Issue:
    """Return an Issue whose state is 'closed' — simulates fetch_issue_detail."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title="x",
        description=description,
        state="closed",
        labels=list(labels or []),
        priority=2,
        issue_type="feature",
    )


def _make_orch(tmp_path, *, verify_completion: bool = False) -> Orchestrator:
    config = ServiceConfig(
        verify_completion=verify_completion,
        verify_completion_llm=False,  # disable LLM in tests (no network)
    )
    return Orchestrator(
        config=config,
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "state.json"),
    )


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


class TestVerifierDisabled:
    """When the feature flag is off, verification is a no-op."""

    def test_close_goes_through(self, tmp_path, event_loop):
        orch = _make_orch(tmp_path, verify_completion=False)
        issue = _make_issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/foo.py` is updated.\n"
        ))
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        closed = _closed_issue(issue.identifier, description=issue.description)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )

        # Issue should be in completed set (close honored).
        assert issue.id in orch.state.completed
        # No reopen — verifier was disabled.
        mock_tracker.reopen_issue.assert_not_called()


class TestVerifierEnabled:
    """With verifier on, behavior depends on diff-vs-AC analysis."""

    def test_passes_when_no_ac(self, tmp_path, event_loop):
        """A bead with no AC section is skipped → close goes through."""
        orch = _make_orch(tmp_path, verify_completion=True)
        issue = _make_issue(description="just prose, no AC")
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        closed = _closed_issue(issue.identifier, description=issue.description)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )

        assert issue.id in orch.state.completed
        mock_tracker.reopen_issue.assert_not_called()

    def test_rejects_and_reopens_when_files_missing(self, tmp_path, event_loop):
        """AC mentions a file the diff doesn't touch → reject + reopen."""
        orch = _make_orch(tmp_path, verify_completion=True)
        issue = _make_issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/missing_file.py` must exist with the new field.\n"
        ))
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        closed = _closed_issue(issue.identifier, description=issue.description)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        # Stub the verifier to return a rejected result regardless of
        # the actual git state. We're testing the wiring, not the
        # verifier internals (those are covered in test_completion_verifier).
        rejected = VerifierResult(
            passed=False,
            stage1=Stage1Result(
                references=ExtractedReferences(),
                missing_files=["oompah/missing_file.py"],
            ),
        )
        with patch.object(
            orch, "_run_completion_verifier", return_value=rejected,
        ):
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )

        # Bead must be reopened.
        mock_tracker.reopen_issue.assert_called_once_with(issue.identifier)
        # Reject count incremented.
        assert orch._verifier_reject_counts[issue.id] == 1
        # Not in completed set yet — retry will run.
        assert issue.id not in orch.state.completed
        # A retry should be scheduled.
        assert issue.id in orch.state.retry_attempts

    def test_third_rejection_fails_open(self, tmp_path, event_loop):
        """After 3 verifier rejections the close stands (fail-open)."""
        orch = _make_orch(tmp_path, verify_completion=True)
        issue = _make_issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/missing_file.py` must exist.\n"
        ))
        # Simulate that this bead has already been rejected 3 times.
        orch._verifier_reject_counts[issue.id] = 3
        entry = _make_running_entry(issue, retry_attempt=3)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        closed = _closed_issue(issue.identifier, description=issue.description)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        rejected = VerifierResult(
            passed=False,
            stage1=Stage1Result(
                references=ExtractedReferences(),
                missing_files=["oompah/missing_file.py"],
            ),
        )
        with patch.object(
            orch, "_run_completion_verifier", return_value=rejected,
        ):
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )

        # Close stands.
        assert issue.id in orch.state.completed
        mock_tracker.reopen_issue.assert_not_called()
        # Reject count cleared.
        assert issue.id not in orch._verifier_reject_counts

    def test_passes_when_verifier_passes(self, tmp_path, event_loop):
        """Verifier returns passed=True → close honored."""
        orch = _make_orch(tmp_path, verify_completion=True)
        issue = _make_issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/foo.py` updated\n"
        ))
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        closed = _closed_issue(issue.identifier, description=issue.description)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        with patch.object(
            orch, "_run_completion_verifier",
            return_value=VerifierResult(passed=True),
        ):
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )

        assert issue.id in orch.state.completed
        mock_tracker.reopen_issue.assert_not_called()

    def test_workspace_error_fails_open(self, tmp_path, event_loop):
        """Workspace lookup raising should not block the close."""
        orch = _make_orch(tmp_path, verify_completion=True)
        issue = _make_issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/foo.py` is updated.\n"
        ))
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        closed = _closed_issue(issue.identifier, description=issue.description)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        # Simulate workspace path resolution failure.
        with patch.object(
            orch.workspace_mgr, "workspace_path_for",
            side_effect=RuntimeError("workspace gone"),
        ):
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )

        # Close stands (fail-open).
        assert issue.id in orch.state.completed
        mock_tracker.reopen_issue.assert_not_called()


class TestGitHubBackedWorkerExit:
    """TASK-461.4: For GitHub-backed tasks the terminal state is re-read from
    GitHub via fetch_issue_detail.  No Backlog workspace files are consulted.

    Acceptance criteria:
    * AC #1 — GitHub-backed completion does not inspect Backlog files in the
              worker worktree.
    * AC #2 — Legacy Backlog terminal-state recognition remains intact
              (covered by TestVerifierDisabled / TestVerifierEnabled).
    """

    def test_github_close_honored_using_fetch_issue_detail(self, tmp_path, event_loop):
        """Worker exits normally; mock GitHub tracker says Done.
        The issue is added to completed without touching workspace files.

        AC #1: _fetch_terminal_issue_from_worker_workspace must NOT produce a
        BacklogMd read path override when the tracker is not BacklogMdTracker.
        """
        orch = _make_orch(tmp_path, verify_completion=False)
        issue = _make_issue(description="")
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        # A MagicMock is not a BacklogMdTracker, so it simulates a GitHub
        # adapter from the isinstance guard's perspective.
        mock_tracker = MagicMock()
        assert not isinstance(mock_tracker, BacklogMdTracker)
        closed = _closed_issue(issue.identifier)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        # Track whether _fetch_terminal_issue_from_worker_workspace is called
        # and confirm it returns None (no Backlog workspace read).
        # Use a side_effect closure to capture the actual return value —
        # patch.object(wraps=) forwards calls to the real function but leaves
        # mock.return_value as sentinel.DEFAULT, so we capture it ourselves.
        captured_rv: list = []
        real_fn = orch._fetch_terminal_issue_from_worker_workspace

        def capturing_side_effect(*args, **kwargs):
            rv = real_fn(*args, **kwargs)
            captured_rv.append(rv)
            return rv

        with patch.object(
            orch,
            "_fetch_terminal_issue_from_worker_workspace",
            side_effect=capturing_side_effect,
        ) as spy_workspace:
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )

        # Close should be honored based on GitHub state alone.
        assert issue.id in orch.state.completed
        # The workspace helper was called but must have returned None
        # (guard fires because mock_tracker is not BacklogMdTracker).
        spy_workspace.assert_called_once()
        assert len(captured_rv) == 1
        assert captured_rv[0] is None

    def test_github_open_state_triggers_reopen_retry(self, tmp_path, event_loop):
        """Worker exits normally but GitHub still shows the issue as open.
        The orchestrator should schedule a retry (not mark completed).

        This verifies that the GitHub-fetched state (not a stale Backlog file)
        drives the completion/retry decision.
        """
        orch = _make_orch(tmp_path, verify_completion=False)
        issue = _make_issue(description="")
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        assert not isinstance(mock_tracker, BacklogMdTracker)
        # GitHub says the issue is still open — agent completed without closing.
        still_open = Issue(
            id=issue.id,
            identifier=issue.identifier,
            title="x",
            description="",
            state="open",  # not terminal
            labels=[],
            priority=2,
            issue_type="feature",
        )
        mock_tracker.fetch_issue_detail.return_value = still_open
        orch.tracker = mock_tracker

        event_loop.run_until_complete(
            orch._on_worker_exit(issue.id, "normal", None)
        )

        # Issue is NOT completed — the open GitHub state was used.
        assert issue.id not in orch.state.completed
        # A reopen entry should have been counted.
        assert orch.state.reopen_counts.get(issue.id, 0) >= 1

    def test_fetch_terminal_workspace_returns_none_for_non_backlog_tracker(
        self, tmp_path
    ):
        """Direct unit test of the fixed guard in
        _fetch_terminal_issue_from_worker_workspace.

        Passing a non-BacklogMdTracker (GitHub-like) as ``tracker`` must
        return None immediately, even when self.tracker is still BacklogMdTracker
        (the common mixed-deployment scenario during tracker migration).

        This is the regression test for TASK-461.4 — before the fix the guard
        required BOTH check_tracker AND self.tracker to be non-Backlog.
        """
        orch = _make_orch(tmp_path)
        # The global tracker is BacklogMd (default installation).
        assert isinstance(orch.tracker, BacklogMdTracker)

        issue = _make_issue(identifier="owner/repo#7")
        entry = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            agent_profile_name="default",
            workspace_path="/some/workspace",
        )

        # GitHub-like tracker: NOT a BacklogMdTracker.
        github_like_tracker = MagicMock()
        assert not isinstance(github_like_tracker, BacklogMdTracker)

        with patch("os.path.isdir", return_value=True):
            result = orch._fetch_terminal_issue_from_worker_workspace(
                entry, tracker=github_like_tracker
            )

        # Guard must fire; no Backlog workspace read should occur.
        assert result is None
