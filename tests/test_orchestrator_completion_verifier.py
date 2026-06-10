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
* GitHub-backed tasks: verifier pass/fail flows update GitHub issue
  comments and status via the tracker protocol (TASK-461.5).
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


# ---------------------------------------------------------------------------
# TASK-461.5: GitHub verifier pass/fail flows
#
# The completion verifier must route all writes (reopen, comment) through the
# tracker protocol so GitHub-backed tasks receive GitHub API calls rather than
# Backlog file mutations.  This class tests AC #1:
#   "Verifier pass/fail flows update GitHub issue comments and status."
# ---------------------------------------------------------------------------

def _make_github_issue(
    issue_id: str = "gh-100",
    identifier: str = "owner/repo#100",
    description: str = "",
    project_id: str = "proj-gh",
    tracker_kind: str = "github_issues",
) -> Issue:
    """Return a minimal GitHub-backed Issue."""
    return Issue(
        id=issue_id,
        identifier=identifier,
        title="GitHub issue",
        description=description,
        state="in_progress",
        labels=[],
        priority=2,
        issue_type="task",
        project_id=project_id,
        tracker_kind=tracker_kind,
    )


def _closed_github_issue(identifier: str = "owner/repo#100", description: str = "") -> Issue:
    """Return a closed GitHub-backed Issue — simulates fetch_issue_detail."""
    return Issue(
        id=identifier,
        identifier=identifier,
        title="GitHub issue",
        description=description,
        state="closed",
        labels=[],
        priority=2,
        issue_type="task",
        tracker_kind="github_issues",
    )


class TestGitHubVerifierFlow:
    """TASK-461.5: Verifier pass/fail flows must update GitHub issue comments
    and status via the tracker protocol.

    For GitHub-backed tasks the orchestrator uses _tracker_for_project() to
    resolve the per-project GitHubIssueTracker.  All writes (reopen, comment)
    must go through that tracker, not through the global self.tracker.

    Acceptance criterion: AC #1 — "Verifier pass/fail flows update GitHub
    issue comments and status."
    """

    def test_github_verifier_rejection_calls_reopen_via_tracker(
        self, tmp_path, event_loop
    ):
        """When the verifier rejects a GitHub-backed close, the tracker
        adapter's reopen_issue() is invoked — not a Backlog file write.

        This exercises the path:
          tracker.reopen_issue(entry.identifier)
          self._post_comment(entry.identifier, ..., project_id=project_id)
        where `tracker` is the project's GitHub tracker, not self.tracker.
        """
        orch = _make_orch(tmp_path, verify_completion=True)
        issue = _make_github_issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/new_feature.py` must exist.\n"
        ))
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        # GitHub-like mock tracker for the project
        gh_tracker = MagicMock()
        assert not isinstance(gh_tracker, BacklogMdTracker)
        closed = _closed_github_issue(description=issue.description)
        gh_tracker.fetch_issue_detail.return_value = closed

        rejected = VerifierResult(
            passed=False,
            stage1=Stage1Result(
                references=ExtractedReferences(),
                missing_files=["oompah/new_feature.py"],
            ),
        )
        with (
            patch.object(orch, "_tracker_for_project", return_value=gh_tracker),
            patch.object(orch, "_run_completion_verifier", return_value=rejected),
        ):
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )

        # The GitHub tracker must be used to reopen the issue (not a Backlog write).
        gh_tracker.reopen_issue.assert_called_once_with(issue.identifier)
        # Reject count incremented.
        assert orch._verifier_reject_counts[issue.id] == 1
        # Not yet completed — retry is pending.
        assert issue.id not in orch.state.completed
        # A retry is scheduled for the next attempt.
        assert issue.id in orch.state.retry_attempts

    def test_github_verifier_rejection_posts_comment_via_tracker(
        self, tmp_path, event_loop
    ):
        """After reopen, a diagnostic comment is posted via the GitHub tracker
        (tracker.add_comment), not written to a Backlog file.
        """
        orch = _make_orch(tmp_path, verify_completion=True)
        issue = _make_github_issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/missing.py` must exist.\n"
        ))
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        gh_tracker = MagicMock()
        assert not isinstance(gh_tracker, BacklogMdTracker)
        closed = _closed_github_issue(description=issue.description)
        gh_tracker.fetch_issue_detail.return_value = closed

        rejected = VerifierResult(
            passed=False,
            stage1=Stage1Result(
                references=ExtractedReferences(),
                missing_files=["oompah/missing.py"],
            ),
        )
        with (
            patch.object(orch, "_tracker_for_project", return_value=gh_tracker),
            patch.object(orch, "_run_completion_verifier", return_value=rejected),
        ):
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )

        # reopen_issue called first, then add_comment with diagnostic.
        gh_tracker.reopen_issue.assert_called_once_with(issue.identifier)
        # add_comment must be called at least once (telemetry + diagnostic).
        # The diagnostic comment about missing files should appear.
        comment_texts = [
            call.args[1] if call.args else call.kwargs.get("text", "")
            for call in gh_tracker.add_comment.call_args_list
        ]
        assert any(
            "oompah/missing.py" in text or "missing" in text.lower()
            for text in comment_texts
        ), (
            f"No diagnostic comment about missing files posted; "
            f"add_comment calls: {gh_tracker.add_comment.call_args_list!r}"
        )

    def test_github_verifier_pass_honors_close(self, tmp_path, event_loop):
        """When the verifier passes for a GitHub-backed issue, the close is
        honored — no reopen, task added to completed.
        """
        orch = _make_orch(tmp_path, verify_completion=True)
        issue = _make_github_issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/done.py` updated.\n"
        ))
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        gh_tracker = MagicMock()
        assert not isinstance(gh_tracker, BacklogMdTracker)
        closed = _closed_github_issue(description=issue.description)
        gh_tracker.fetch_issue_detail.return_value = closed

        with (
            patch.object(orch, "_tracker_for_project", return_value=gh_tracker),
            patch.object(
                orch, "_run_completion_verifier",
                return_value=VerifierResult(passed=True),
            ),
        ):
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )

        # Close is honored.
        assert issue.id in orch.state.completed
        gh_tracker.reopen_issue.assert_not_called()

    def test_github_verifier_max_rejections_fails_open(self, tmp_path, event_loop):
        """After the max rejection threshold, the close sticks even for a
        GitHub-backed issue — fail-open so a buggy verifier can't lock the
        task forever.
        """
        orch = _make_orch(tmp_path, verify_completion=True)
        issue = _make_github_issue(description=(
            "# Acceptance criteria\n"
            "- `oompah/missing.py` must exist.\n"
        ))
        # Pre-seed: already at the ceiling (3 rejections).
        orch._verifier_reject_counts[issue.id] = 3
        entry = _make_running_entry(issue, retry_attempt=3)
        orch.state.running[issue.id] = entry

        gh_tracker = MagicMock()
        assert not isinstance(gh_tracker, BacklogMdTracker)
        closed = _closed_github_issue(description=issue.description)
        gh_tracker.fetch_issue_detail.return_value = closed

        rejected = VerifierResult(
            passed=False,
            stage1=Stage1Result(
                references=ExtractedReferences(),
                missing_files=["oompah/missing.py"],
            ),
        )
        with (
            patch.object(orch, "_tracker_for_project", return_value=gh_tracker),
            patch.object(orch, "_run_completion_verifier", return_value=rejected),
        ):
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )

        # Close stands (fail-open) — issue is completed.
        assert issue.id in orch.state.completed
        # No reopen on fail-open path.
        gh_tracker.reopen_issue.assert_not_called()
        # Reject count cleared after fail-open.
        assert issue.id not in orch._verifier_reject_counts

    def test_github_verifier_retry_uses_github_identifier(
        self, tmp_path, event_loop
    ):
        """The retry scheduled after a GitHub verifier rejection must carry
        the GitHub identifier (e.g. ``owner/repo#100``) so that a subsequent
        manual close via the UI can find and cancel it.

        This exercises the intersection of AC #1 (verifier) and AC #2 (races).
        """
        orch = _make_orch(tmp_path, verify_completion=True)
        issue = _make_github_issue(
            issue_id="gh-100",
            identifier="owner/repo#100",
            description=(
                "# Acceptance criteria\n"
                "- `oompah/widget.py` updated.\n"
            ),
        )
        entry = _make_running_entry(issue)
        orch.state.running[issue.id] = entry

        gh_tracker = MagicMock()
        assert not isinstance(gh_tracker, BacklogMdTracker)
        closed = _closed_github_issue(description=issue.description)
        gh_tracker.fetch_issue_detail.return_value = closed

        rejected = VerifierResult(
            passed=False,
            stage1=Stage1Result(
                references=ExtractedReferences(),
                missing_files=["oompah/widget.py"],
            ),
        )
        with (
            patch.object(orch, "_tracker_for_project", return_value=gh_tracker),
            patch.object(orch, "_run_completion_verifier", return_value=rejected),
        ):
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )

        # A retry must have been scheduled.
        assert issue.id in orch.state.retry_attempts
        retry_entry = orch.state.retry_attempts[issue.id]
        # The retry identifier must be the GitHub identifier, not a numeric stub.
        assert retry_entry.identifier == "owner/repo#100", (
            f"Expected retry identifier 'owner/repo#100', "
            f"got {retry_entry.identifier!r}"
        )
