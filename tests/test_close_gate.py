"""Tests for the close gate (oompah-zlz_2-gz8w).

Covers:
* branch ahead + no PR → refused
* branch ahead + open PR → allowed
* branch ahead + merged PR → allowed
* branch empty (0 commits ahead) → allowed
* operator close (no agent context / gate disabled) → allowed
* forge timeout → allowed + WARNING logged
* epic issue → allowed (skip)
* decomposed label → allowed (skip)
* operator-style close reasons → allowed (skip)
* orchestrator wiring: gate refused → bead reopened, comment posted, not in completed
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from oompah.close_gate import (
    CloseGateResult,
    check_close_gate,
    build_refusal_comment,
    _count_commits_ahead,
    _query_prs_for_branch,
    _OPERATOR_CLOSE_REASONS,
)
from oompah.config import ServiceConfig
from oompah.models import Issue, RunningEntry
from oompah.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    identifier: str = "test-001",
    issue_id: str = "iss-1",
    issue_type: str = "feature",
    labels: list[str] | None = None,
    branch_name: str | None = None,
    project_id: str | None = "proj-1",
) -> Issue:
    return Issue(
        id=issue_id,
        identifier=identifier,
        title="Test issue",
        description="# Acceptance criteria\n- Something",
        state="in_progress",
        labels=list(labels or []),
        priority=2,
        issue_type=issue_type,
        project_id=project_id,
        branch_name=branch_name,
    )


def _make_entry(issue: Issue, *, retry_attempt: int = 0) -> RunningEntry:
    return RunningEntry(
        worker_task=None,
        identifier=issue.identifier,
        issue=issue,
        session=None,
        retry_attempt=retry_attempt,
        started_at=datetime.now(timezone.utc),
        agent_profile_name="default",
    )


def _make_orch(tmp_path, *, close_gate_enabled: bool = True) -> Orchestrator:
    config = ServiceConfig(
        close_gate_enabled=close_gate_enabled,
        verify_completion=False,
        verify_completion_llm=False,
    )
    return Orchestrator(
        config=config,
        workflow_path="WORKFLOW.md",
        state_path=str(tmp_path / "state.json"),
    )


def _closed_issue(identifier: str = "test-001") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="x",
        description="",
        state="closed",
        labels=[],
        priority=2,
        issue_type="feature",
    )


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


# ---------------------------------------------------------------------------
# Unit tests for check_close_gate()
# ---------------------------------------------------------------------------


class TestCheckCloseGate:
    """Tests for the pure check_close_gate() function."""

    def test_epic_skipped(self):
        """Epic issues are always allowed (they have no own branch)."""
        issue = _make_issue(issue_type="epic")
        result = check_close_gate(
            issue,
            repo_path="/tmp",
            slug="owner/repo",
            base_branch="main",
        )
        assert result.allowed is True
        assert result.skip_reason == "epic"

    def test_decomposed_label_skipped(self):
        """Issues with 'decomposed' label are always allowed."""
        issue = _make_issue(labels=["decomposed"])
        result = check_close_gate(
            issue,
            repo_path="/tmp",
            slug="owner/repo",
            base_branch="main",
        )
        assert result.allowed is True
        assert result.skip_reason == "decomposed"

    def test_operator_close_reason_noop_skipped(self):
        """Operator-style close reasons bypass the gate."""
        issue = _make_issue()
        result = check_close_gate(
            issue,
            repo_path="/tmp",
            slug="owner/repo",
            base_branch="main",
            close_reason="no-op",
        )
        assert result.allowed is True
        assert "operator_reason" in result.skip_reason

    def test_operator_close_reason_wontfix_skipped(self):
        """wontfix close reason bypasses the gate."""
        issue = _make_issue()
        result = check_close_gate(
            issue,
            repo_path="/tmp",
            slug="owner/repo",
            base_branch="main",
            close_reason="wontfix",
        )
        assert result.allowed is True
        assert "operator_reason" in result.skip_reason

    def test_no_branch_resolved_skipped(self):
        """Issue with no branch name → no_branch skip."""
        issue = Issue(
            id="x",
            identifier="",
            title="t",
            description="",
            state="closed",
            labels=[],
            priority=2,
            issue_type="feature",
        )
        result = check_close_gate(
            issue,
            repo_path="/tmp",
            slug="owner/repo",
            base_branch="main",
        )
        assert result.allowed is True
        assert result.skip_reason == "no_branch"

    def test_no_repo_path_skipped(self):
        """No repo_path → no_repo_path skip."""
        issue = _make_issue()
        result = check_close_gate(
            issue,
            repo_path="",
            slug="owner/repo",
            base_branch="main",
        )
        assert result.allowed is True
        assert result.skip_reason == "no_repo_path"

    def test_git_error_fails_open(self):
        """git rev-list error → fail-open."""
        issue = _make_issue()
        with patch("oompah.close_gate._count_commits_ahead") as mock_git:
            mock_git.return_value = (0, [], "git error")
            result = check_close_gate(
                issue,
                repo_path="/tmp/repo",
                slug="owner/repo",
                base_branch="main",
            )
        assert result.allowed is True
        assert result.skip_reason == "git_error"

    def test_no_commits_ahead_allowed(self):
        """Branch with 0 commits ahead → allowed (no unmerged work)."""
        issue = _make_issue()
        with patch("oompah.close_gate._count_commits_ahead") as mock_git:
            mock_git.return_value = (0, [], "")
            result = check_close_gate(
                issue,
                repo_path="/tmp/repo",
                slug="owner/repo",
                base_branch="main",
            )
        assert result.allowed is True
        assert result.skip_reason == "no_commits_ahead"

    def test_no_slug_fails_open_with_commits(self):
        """No slug for forge query → fail-open even with commits ahead."""
        issue = _make_issue()
        with patch("oompah.close_gate._count_commits_ahead") as mock_git:
            mock_git.return_value = (3, ["abc123 feat: something"], "")
            result = check_close_gate(
                issue,
                repo_path="/tmp/repo",
                slug="",
                base_branch="main",
            )
        assert result.allowed is True
        assert result.skip_reason == "no_slug"

    def test_open_pr_allows_close(self):
        """Branch ahead + open PR → allowed."""
        issue = _make_issue()
        with (
            patch("oompah.close_gate._count_commits_ahead") as mock_git,
            patch("oompah.close_gate._query_prs_for_branch") as mock_prs,
        ):
            mock_git.return_value = (3, ["abc123 feat"], "")
            mock_prs.return_value = (1, 0, [], "")  # 1 open, 0 merged
            result = check_close_gate(
                issue,
                repo_path="/tmp/repo",
                slug="owner/repo",
                base_branch="main",
            )
        assert result.allowed is True
        assert result.open_prs == 1
        assert result.merged_prs == 0

    def test_merged_pr_allows_close(self):
        """Branch ahead + merged PR → allowed."""
        issue = _make_issue()
        with (
            patch("oompah.close_gate._count_commits_ahead") as mock_git,
            patch("oompah.close_gate._query_prs_for_branch") as mock_prs,
        ):
            mock_git.return_value = (2, ["def456 fix: something"], "")
            mock_prs.return_value = (
                0,
                1,
                ["PR #42: https://github.com/o/r/pull/42"],
                "",
            )
            result = check_close_gate(
                issue,
                repo_path="/tmp/repo",
                slug="owner/repo",
                base_branch="main",
            )
        assert result.allowed is True
        assert result.merged_prs == 1

    def test_no_pr_refuses_close(self):
        """Branch ahead + no PR → refused."""
        issue = _make_issue()
        with (
            patch("oompah.close_gate._count_commits_ahead") as mock_git,
            patch("oompah.close_gate._query_prs_for_branch") as mock_prs,
        ):
            mock_git.return_value = (5, ["abc feat1", "def feat2"], "")
            mock_prs.return_value = (0, 0, [], "")  # no PRs
            result = check_close_gate(
                issue,
                repo_path="/tmp/repo",
                slug="owner/repo",
                base_branch="main",
            )
        assert result.allowed is False
        assert result.commits_ahead == 5
        assert result.open_prs == 0
        assert result.merged_prs == 0

    def test_forge_timeout_fails_open(self):
        """Forge API timeout → fail-open with error recorded."""
        issue = _make_issue()
        with (
            patch("oompah.close_gate._count_commits_ahead") as mock_git,
            patch("oompah.close_gate._query_prs_for_branch") as mock_prs,
        ):
            mock_git.return_value = (3, ["abc feat"], "")
            mock_prs.return_value = (
                0,
                0,
                [],
                "GitHub PR query timed out: connect timeout",
            )
            result = check_close_gate(
                issue,
                repo_path="/tmp/repo",
                slug="owner/repo",
                base_branch="main",
            )
        assert result.allowed is True
        assert result.skip_reason == "forge_error"
        assert "timed out" in result.error

    def test_telemetry_logged_on_refusal(self, caplog):
        """Telemetry event is logged as INFO when close is refused."""
        issue = _make_issue()
        with (
            patch("oompah.close_gate._count_commits_ahead") as mock_git,
            patch("oompah.close_gate._query_prs_for_branch") as mock_prs,
            caplog.at_level(logging.INFO, logger="oompah.close_gate"),
        ):
            mock_git.return_value = (4, ["abc"], "")
            mock_prs.return_value = (0, 0, [], "")
            check_close_gate(
                issue,
                repo_path="/tmp/repo",
                slug="owner/repo",
                base_branch="main",
                entry_profile="standard",
                entry_focus="feature_developer",
                entry_attempt=1,
            )
        # Find the telemetry log line
        telemetry_records = [
            r for r in caplog.records if "close_refused_unmerged_work" in r.getMessage()
        ]
        assert len(telemetry_records) == 1
        payload = json.loads(
            telemetry_records[0].getMessage().split("close_gate_telemetry: ", 1)[1]
        )
        assert payload["event"] == "close_refused_unmerged_work"
        assert payload["commits_ahead"] == 4
        assert payload["open_prs"] == 0
        assert payload["agent_profile"] == "standard"
        assert payload["focus"] == "feature_developer"
        assert payload["attempt"] == 1

    def test_forge_warning_logged_on_timeout(self, caplog):
        """forge timeout logs a WARNING."""
        issue = _make_issue()
        with (
            patch("oompah.close_gate._count_commits_ahead") as mock_git,
            patch("oompah.close_gate._query_prs_for_branch") as mock_prs,
            caplog.at_level(logging.WARNING, logger="oompah.close_gate"),
        ):
            mock_git.return_value = (2, ["abc"], "")
            mock_prs.return_value = (0, 0, [], "GitHub PR query timed out")
            check_close_gate(
                issue,
                repo_path="/tmp/repo",
                slug="owner/repo",
                base_branch="main",
            )
        warn_records = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and "forge query failed" in r.getMessage()
        ]
        assert len(warn_records) == 1


# ---------------------------------------------------------------------------
# Unit tests for build_refusal_comment()
# ---------------------------------------------------------------------------


class TestBuildRefusalComment:
    """Tests for the refusal comment builder."""

    def test_basic_refusal_comment(self):
        issue = _make_issue(identifier="test-123")
        result = CloseGateResult(
            allowed=False,
            commits_ahead=3,
            open_prs=0,
            merged_prs=0,
            commit_lines=["abc123 feat: add thing", "def456 fix: other"],
        )
        comment = build_refusal_comment(issue, result, "main")
        assert "Close refused by orchestrator" in comment
        assert "`test-123`" in comment
        assert "3 commit" in comment
        assert "`main`" in comment
        assert "abc123 feat: add thing" in comment
        assert "gh pr create" in comment
        assert "--base main" in comment
        assert "--head test-123" in comment
        assert "Required: open a PR before closing" in comment
        assert "Bead reopened" in comment

    def test_comment_with_merged_prs(self):
        issue = _make_issue(identifier="my-issue")
        result = CloseGateResult(
            allowed=False,
            commits_ahead=1,
            open_prs=0,
            merged_prs=2,
            merged_pr_links=["PR #10: https://...", "PR #11: https://..."],
        )
        comment = build_refusal_comment(issue, result, "main")
        assert "Merged PRs from this branch: 2" in comment
        assert "PR #10" in comment

    def test_singular_commit_noun(self):
        issue = _make_issue()
        result = CloseGateResult(
            allowed=False,
            commits_ahead=1,
            commit_lines=["abc feat"],
        )
        comment = build_refusal_comment(issue, result, "main")
        assert "1 commit not on" in comment

    def test_plural_commit_noun(self):
        issue = _make_issue()
        result = CloseGateResult(
            allowed=False,
            commits_ahead=5,
            commit_lines=["abc feat"],
        )
        comment = build_refusal_comment(issue, result, "main")
        assert "5 commits not on" in comment


# ---------------------------------------------------------------------------
# Orchestrator integration tests
# ---------------------------------------------------------------------------


class TestOrchestratorCloseGateWiring:
    """Tests for the orchestrator wiring of the close gate."""

    def test_gate_disabled_allows_close(self, tmp_path, event_loop):
        """When close_gate_enabled=False, the gate is a no-op."""
        orch = _make_orch(tmp_path, close_gate_enabled=False)
        issue = _make_issue()
        entry = _make_entry(issue)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        closed = _closed_issue(issue.identifier)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        event_loop.run_until_complete(orch._on_worker_exit(issue.id, "normal", None))

        # Issue should be in completed set (gate was disabled, close honored)
        assert issue.id in orch.state.completed
        # update_issue was NOT called to reopen the bead
        calls = [str(c) for c in mock_tracker.method_calls]
        reopen_calls = [c for c in calls if "status='open'" in c or '"open"' in c]
        assert len(reopen_calls) == 0

    def test_gate_refuses_no_pr(self, tmp_path, event_loop):
        """Branch ahead + no PR → close refused, bead reopened, comment posted."""
        orch = _make_orch(tmp_path, close_gate_enabled=True)
        issue = _make_issue(project_id="proj-1")
        entry = _make_entry(issue)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        closed = _closed_issue(issue.identifier)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        # Mock a project with repo context
        mock_project = MagicMock()
        mock_project.id = "proj-1"
        mock_project.repo_path = "/tmp/repo"
        mock_project.branch = "main"
        mock_project.repo_url = "https://github.com/owner/repo.git"
        mock_project.access_token = None
        orch.project_store.get = MagicMock(return_value=mock_project)
        orch._project_trackers["proj-1"] = mock_tracker

        refused_result = CloseGateResult(
            allowed=False,
            commits_ahead=3,
            open_prs=0,
            merged_prs=0,
            commit_lines=["abc feat"],
        )
        with patch.object(orch, "_run_close_gate", return_value=False) as mock_gate:
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "normal", None)
            )
            mock_gate.assert_called_once()

        # Gate refused → issue NOT in completed
        assert issue.id not in orch.state.completed
        # No retry scheduled (bead reopened, will be picked up by next tick)
        # The gate itself does the reopen; orchestrator just stops processing

    def test_gate_allows_with_open_pr(self, tmp_path, event_loop):
        """Branch ahead + open PR → close allowed, proceeds to verifier."""
        orch = _make_orch(tmp_path, close_gate_enabled=True)
        issue = _make_issue()
        entry = _make_entry(issue)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        closed = _closed_issue(issue.identifier)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        # Gate returns True (allowed)
        with patch.object(orch, "_run_close_gate", return_value=True):
            with patch.object(
                orch,
                "_run_completion_verifier",
                return_value=MagicMock(
                    passed=True, skipped=True, skip_reason="disabled"
                ),
            ):
                event_loop.run_until_complete(
                    orch._on_worker_exit(issue.id, "normal", None)
                )

        # Close went through
        assert issue.id in orch.state.completed

    def test_operator_close_bypasses_gate(self, tmp_path, event_loop):
        """Operator-style close (gate disabled) → always allowed."""
        # Operators close via the dashboard or CLI which doesn't go through
        # _on_worker_exit at all. The gate only runs in _on_worker_exit
        # (agent-driven closes). Verify gate is never called for
        # non-"normal" exit reasons.
        orch = _make_orch(tmp_path, close_gate_enabled=True)
        issue = _make_issue()
        entry = _make_entry(issue)
        orch.state.running[issue.id] = entry

        mock_tracker = MagicMock()
        closed = _closed_issue(issue.identifier)
        mock_tracker.fetch_issue_detail.return_value = closed
        orch.tracker = mock_tracker

        with patch.object(orch, "_run_close_gate") as mock_gate:
            # Abnormal exit (e.g. operator interruption) — gate should NOT fire
            event_loop.run_until_complete(
                orch._on_worker_exit(issue.id, "abnormal", "some error")
            )
            mock_gate.assert_not_called()

    def test_gate_run_close_gate_method_calls_check_close_gate(self, tmp_path):
        """_run_close_gate calls check_close_gate with correct arguments."""
        orch = _make_orch(tmp_path, close_gate_enabled=True)
        issue = _make_issue(project_id="proj-1")

        mock_project = MagicMock()
        mock_project.repo_path = "/tmp/myrepo"
        mock_project.default_branch = "main"
        mock_project.repo_url = "https://github.com/myorg/myrepo.git"
        mock_project.access_token = "gh_tok"
        orch.project_store.get = MagicMock(return_value=mock_project)

        entry = _make_entry(issue)
        entry.agent_profile_name = "standard"
        entry.focus_name = "feature"
        entry.retry_attempt = 2

        current = _closed_issue(issue.identifier)

        with (
            patch("oompah.close_gate.check_close_gate") as mock_check,
            patch("oompah.close_gate.build_refusal_comment"),
        ):
            mock_check.return_value = CloseGateResult(
                allowed=True, skip_reason="no_commits_ahead"
            )
            result = orch._run_close_gate(entry, current, "proj-1")

        assert result is True
        mock_check.assert_called_once()
        call_kwargs = mock_check.call_args
        assert call_kwargs[1]["repo_path"] == "/tmp/myrepo"
        assert call_kwargs[1]["base_branch"] == "main"
        assert call_kwargs[1]["entry_profile"] == "standard"
        assert call_kwargs[1]["entry_focus"] == "feature"
        assert call_kwargs[1]["entry_attempt"] == 2

    def test_gate_refused_posts_comment_and_reopens(self, tmp_path):
        """When gate refuses, a comment is posted and the bead is reopened."""
        orch = _make_orch(tmp_path, close_gate_enabled=True)
        issue = _make_issue(project_id=None)

        entry = _make_entry(issue)
        current = _closed_issue(issue.identifier)

        mock_tracker = MagicMock()
        orch.tracker = mock_tracker

        refused = CloseGateResult(
            allowed=False,
            commits_ahead=2,
            open_prs=0,
            merged_prs=0,
            commit_lines=["abc fix"],
        )
        with patch("oompah.close_gate.check_close_gate") as mock_check:
            mock_check.return_value = refused
            result = orch._run_close_gate(entry, current, None)

        assert result is False
        # Comment posted
        assert mock_tracker.add_comment.called
        comment_args = mock_tracker.add_comment.call_args
        assert "Close refused" in comment_args[0][1]
        assert "2 commit" in comment_args[0][1]
        # Bead reopened
        assert mock_tracker.update_issue.called
        update_call = mock_tracker.update_issue.call_args
        assert "open" in str(update_call)


# ---------------------------------------------------------------------------
# Unit tests for _count_commits_ahead
# ---------------------------------------------------------------------------


class TestCountCommitsAhead:
    """Tests for the git commit counting helper."""

    def test_count_zero(self):
        """Returns 0 when branch has no commits ahead of base."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="0\n", stderr="")
            count, lines, err = _count_commits_ahead("/tmp/repo", "main", "my-branch")
        assert count == 0
        assert lines == []
        assert err == ""

    def test_count_positive(self):
        """Returns N when branch has N commits ahead."""

        def side_effect(cmd, **kwargs):
            if "--count" in cmd:
                return MagicMock(returncode=0, stdout="3\n", stderr="")
            else:
                # git log --oneline
                return MagicMock(
                    returncode=0,
                    stdout="abc1234 feat: add foo\ndef5678 fix: bar\nghi0123 chore: baz\n",
                    stderr="",
                )

        with patch("subprocess.run", side_effect=side_effect):
            count, lines, err = _count_commits_ahead("/tmp/repo", "main", "my-branch")
        assert count == 3
        assert len(lines) == 3
        assert "abc1234 feat: add foo" in lines
        assert err == ""

    def test_git_not_found(self):
        """FileNotFoundError → returns error string."""
        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            count, lines, err = _count_commits_ahead("/tmp/repo", "main", "my-branch")
        assert count == 0
        assert "failed" in err

    def test_git_timeout(self):
        """TimeoutExpired → returns error string."""
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 15)):
            count, lines, err = _count_commits_ahead("/tmp/repo", "main", "my-branch")
        assert count == 0
        assert "failed" in err


# ---------------------------------------------------------------------------
# Unit tests for _query_prs_for_branch
# ---------------------------------------------------------------------------


class TestQueryPrsForBranch:
    """Tests for the GitHub PR query helper."""

    def test_no_prs_returns_zero(self):
        """No PRs returns (0, 0, [], '')."""
        mock_client = MagicMock()
        mock_resp_open = MagicMock(status_code=200)
        mock_resp_open.json.return_value = []
        mock_resp_closed = MagicMock(status_code=200)
        mock_resp_closed.json.return_value = []
        mock_client.get.side_effect = [mock_resp_open, mock_resp_closed]

        with patch("httpx.Client", return_value=mock_client):
            open_c, merged_c, links, err = _query_prs_for_branch(
                "tok",
                "owner/repo",
                "owner:my-branch",
                "main",
            )
        assert open_c == 0
        assert merged_c == 0
        assert links == []
        assert err == ""

    def test_open_pr_found(self):
        """Open PR targeting base → open_count=1."""
        mock_client = MagicMock()
        mock_resp_open = MagicMock(status_code=200)
        mock_resp_open.json.return_value = [
            {
                "number": 42,
                "html_url": "https://github.com/owner/repo/pull/42",
                "base": {"ref": "main"},
                "merged_at": None,
            }
        ]
        mock_resp_closed = MagicMock(status_code=200)
        mock_resp_closed.json.return_value = []
        mock_client.get.side_effect = [mock_resp_open, mock_resp_closed]

        with patch("httpx.Client", return_value=mock_client):
            open_c, merged_c, links, err = _query_prs_for_branch(
                None,
                "owner/repo",
                "owner:my-branch",
                "main",
            )
        assert open_c == 1
        assert merged_c == 0
        assert err == ""

    def test_merged_pr_found(self):
        """Closed PR with merged_at → merged_count=1."""
        mock_client = MagicMock()
        mock_resp_open = MagicMock(status_code=200)
        mock_resp_open.json.return_value = []
        mock_resp_closed = MagicMock(status_code=200)
        mock_resp_closed.json.return_value = [
            {
                "number": 99,
                "html_url": "https://github.com/owner/repo/pull/99",
                "base": {"ref": "main"},
                "merged_at": "2026-05-10T12:00:00Z",
            }
        ]
        mock_client.get.side_effect = [mock_resp_open, mock_resp_closed]

        with patch("httpx.Client", return_value=mock_client):
            open_c, merged_c, links, err = _query_prs_for_branch(
                None,
                "owner/repo",
                "owner:my-branch",
                "main",
            )
        assert open_c == 0
        assert merged_c == 1
        assert "PR #99" in links[0]
        assert err == ""

    def test_http_timeout_returns_error(self):
        """Timeout → returns ('', '', [], error_string)."""
        import httpx as _httpx

        mock_client = MagicMock()
        mock_client.get.side_effect = _httpx.TimeoutException("connect timed out")

        with patch("httpx.Client", return_value=mock_client):
            open_c, merged_c, links, err = _query_prs_for_branch(
                None,
                "owner/repo",
                "owner:my-branch",
                "main",
            )
        assert open_c == 0
        assert merged_c == 0
        assert "timed out" in err

    def test_auth_error_returns_error(self):
        """401 status → returns error string."""
        mock_client = MagicMock()
        mock_resp = MagicMock(status_code=401)
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client", return_value=mock_client):
            open_c, merged_c, links, err = _query_prs_for_branch(
                None,
                "owner/repo",
                "owner:my-branch",
                "main",
            )
        assert open_c == 0
        assert "401" in err
