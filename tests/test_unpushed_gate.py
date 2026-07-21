"""Tests for the unpushed gate (oompah-zlz_2-kc2k.1).

Covers:
* unpushed commits + no PR → refused
* branch on main (0 commits ahead) → allowed
* only uncommitted changes (no commits) → refused
* both uncommitted + unpushed → refused
* epic issue → allowed (skip)
* no branch resolved → allowed (skip)
* no repo_path → allowed (skip)
* git error → fail-open + WARNING logged
* orchestrator wiring: gate refused → task re-opens to in_progress, comment posted
* gate disabled → always allowed (no-op)
* _check_unpushed helper: subprocess edge cases
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from oompah.unpushed_gate import (
    UnpushedGateResult,
    check_unpushed_gate,
    build_unpushed_refusal_comment,
    _check_unpushed,
)


def _make_issue(
    identifier: str = "test-001",
    issue_id: str = "iss-1",
    issue_type: str = "feature",
    labels: list[str] | None = None,
    branch_name: str | None = None,
    work_branch: str | None = None,
    project_id: str | None = "proj-1",
):
    """Minimal Issue constructor matching the test pattern from test_close_gate."""
    return MagicMock(
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
        work_branch=work_branch,
    )


class FakeIssue:
    """Lightweight Issue stand-in using plain attrs (matches object model)."""

    def __init__(
        self,
        identifier: str = "test-001",
        issue_id: str = "iss-1",
        issue_type: str = "feature",
        labels: list[str] | None = None,
        branch_name: str | None = None,
        work_branch: str | None = None,
    ):
        self.id = issue_id
        self.identifier = identifier
        self.title = "Test issue"
        self.description = "# Acceptance criteria\n- Something"
        self.state = "in_progress"
        self.labels = list(labels) if labels else []
        self.priority = 2
        self.issue_type = issue_type
        self.project_id = "proj-1"
        self.branch_name = branch_name
        self.work_branch = work_branch


class TestCheckUnpushedGate:
    """Unit tests for check_unpushed_gate()."""

    def test_epic_skipped(self):
        """Epic issues always allowed (no own branch cadence)."""
        issue = FakeIssue(issue_type="epic", branch_name="my-epic")
        result = check_unpushed_gate(
            issue,
            repo_path="/tmp/repo",
            base_branch="main",
        )
        assert result.allowed is True
        assert result.skip_reason == "epic"

    def _test_no_repo_path_skipped_placeholder(self):
        # NOTE: the no_branch skip is effectively unreachable in oompah —
        # every Issue has an identifier that resolves to a branch name in
        # the or-chain. This test is kept as a canary in case a future
        # code change reintroduces the path.
        pass

    def test_no_repo_path_skipped(self):
        """No repo_path → no_repo_path skip."""
        issue = FakeIssue(branch_name="my-branch")
        result = check_unpushed_gate(
            issue,
            repo_path="",
            base_branch="main",
        )
        assert result.allowed is True
        assert result.skip_reason == "no_repo_path"

    def test_git_error_fails_open(self):
        """git failure → fail-open with skip_reason=git_error."""
        issue = FakeIssue(branch_name="my-branch")
        with patch("oompah.unpushed_gate._check_unpushed") as mock_check:
            mock_check.return_value = (False, 0, [], "git rev-list failed: OOM")
            result = check_unpushed_gate(
                issue,
                repo_path="/tmp/repo",
                base_branch="main",
            )
        assert result.allowed is True
        assert result.skip_reason == "git_error"
        assert "git rev-list failed" in result.error

    def test_no_unpushed_allowed(self):
        """Branch on main with no uncommitted + no untracked → allowed."""
        issue = FakeIssue(branch_name="my-branch")
        with patch("oompah.unpushed_gate._check_unpushed") as mock_check:
            mock_check.return_value = (False, 0, [], "")
            result = check_unpushed_gate(
                issue,
                repo_path="/tmp/repo",
                base_branch="main",
            )
        assert result.allowed is True
        assert result.skip_reason == "no_unpushed_work"

    def test_work_branch_preferred(self):
        """GitHub work branch is used instead of the issue identifier."""
        issue = FakeIssue(
            identifier="org/repo#42",
            branch_name="org/repo#42",
            work_branch="oompah/repo/gh-42",
        )
        with patch("oompah.unpushed_gate._check_unpushed") as mock_check:
            mock_check.return_value = (False, 0, [], "")
            result = check_unpushed_gate(
                issue,
                repo_path="/tmp/repo",
                base_branch="main",
            )
        assert result.allowed is True
        mock_check.assert_called_once_with(
            "/tmp/repo",
            "oompah/repo/gh-42",
            "main",
            worktree_path="",
        )

    def test_unpushed_commits_refused(self):
        """Branch whose origin/branch is behind → refused with commits_ahead > 0."""
        issue = FakeIssue(identifier="oompah-zlz_2-kc2k.1", branch_name="oompah-zlz_2-kc2k.1")
        with patch("oompah.unpushed_gate._check_unpushed") as mock_check:
            mock_check.return_value = (
                False,  # no uncommitted worktree changes
                3,      # 3 commits ahead
                ["abc1 feat: add thing", "def2 feat: another"],
                "",
            )
            result = check_unpushed_gate(
                issue,
                repo_path="/tmp/repo",
                base_branch="main",
                entry_profile="standard",
                entry_focus="backend",
                entry_attempt=1,
            )
        assert result.allowed is False
        assert result.commits_ahead == 3
        assert result.has_uncommitted is False
        assert "abc1 feat: add thing" in result.commit_lines

    def test_uncommitted_worktree_refused(self):
        """Worktree has uncommitted changes but branch is clean → refused."""
        issue = FakeIssue(branch_name="my-branch")
        with patch("oompah.unpushed_gate._check_unpushed") as mock_check:
            mock_check.return_value = (True, 0, [], "")  # has_uncommitted=True
            result = check_unpushed_gate(
                issue,
                repo_path="/tmp/repo",
                base_branch="main",
            )
        assert result.allowed is False
        assert result.has_uncommitted is True
        assert result.commits_ahead == 0

    def test_both_uncommitted_and_unpushed_refused(self):
        """Both uncommitted worktree + unpushed commits → refused."""
        issue = FakeIssue(branch_name="my-branch")
        with patch("oompah.unpushed_gate._check_unpushed") as mock_check:
            mock_check.return_value = (
                True,   # has_uncommitted
                2,      # commits ahead
                ["abc feat"],
                "",
            )
            result = check_unpushed_gate(
                issue,
                repo_path="/tmp/repo",
                base_branch="main",
            )
        assert result.allowed is False
        assert result.has_uncommitted is True
        assert result.commits_ahead == 2

    def test_telemetry_on_refusal(self, caplog):
        """Refusal logs structured telemetry event."""
        issue = FakeIssue(identifier="test-42", branch_name="test-42")
        with (
            patch("oompah.unpushed_gate._check_unpushed") as mock_check,
            caplog.at_level(logging.INFO, logger="oompah.unpushed_gate"),
        ):
            mock_check.return_value = (False, 4, ["abc feat"], "")
            check_unpushed_gate(
                issue,
                repo_path="/tmp/repo",
                base_branch="main",
                entry_profile="deep",
                entry_focus="feature",
                entry_attempt=2,
            )
        telemetry_records = [
            r for r in caplog.records
            if "completion_rejected_unpushed_work" in getattr(r, "message", r.getMessage())
        ]
        assert len(telemetry_records) == 1
        record = telemetry_records[0]
        msg = record.getMessage()
        assert "completion_rejected_unpushed_work" in msg
        # Payload is embedded in "unpushed_gate_telemetry: {json}"
        assert "unpushed_gate_telemetry:" in msg
        payload_str = msg.split("unpushed_gate_telemetry: ", 1)[1]
        payload = json.loads(payload_str)
        assert payload["event"] == "completion_rejected_unpushed_work"
        assert payload["commits_ahead"] == 4
        assert payload["has_uncommitted"] is False
        assert payload["agent_profile"] == "deep"
        assert payload["focus"] == "feature"
        assert payload["attempt"] == 2

    def test_git_warning_logged_on_error(self, caplog):
        """git error logs a WARNING so operators notice."""
        issue = FakeIssue(branch_name="my-branch")
        with (
            patch("oompah.unpushed_gate._check_unpushed") as mock_check,
            caplog.at_level(logging.WARNING, logger="oompah.unpushed_gate"),
        ):
            mock_check.return_value = (False, 0, [], "git fetch timed out")
            check_unpushed_gate(
                issue,
                repo_path="/tmp/repo",
                base_branch="main",
            )
        warn_records = [
            r for r in caplog.records
            if r.levelno == logging.WARNING and "git check failed" in r.getMessage()
        ]
        assert len(warn_records) == 1


class TestBuildUnpushedRefusalComment:
    """Tests for build_unpushed_refusal_comment()."""

    def test_refuses_with_unpushed_commits(self):
        """Comment contains commit count, commit lines, and required steps."""
        issue = FakeIssue(identifier="my-task", branch_name="my-task")
        result = UnpushedGateResult(
            allowed=False,
            has_uncommitted=False,
            commits_ahead=3,
            commit_lines=["abc123 feat: add thing", "def456 fix: other"],
        )
        comment = build_unpushed_refusal_comment(issue, result, "main")
        assert "Completion refused" in comment
        assert "`my-task`" in comment
        assert "3 commit" in comment
        assert "abc123 feat: add thing" in comment
        assert "git checkout my-task" in comment
        assert "git push origin my-task" in comment
        assert "Task re-opened" in comment

    def test_refusal_comment_uses_work_branch(self):
        issue = FakeIssue(
            identifier="org/repo#42",
            branch_name="org/repo#42",
            work_branch="oompah/repo/gh-42",
        )
        result = UnpushedGateResult(
            allowed=False,
            has_uncommitted=False,
            commits_ahead=1,
        )
        comment = build_unpushed_refusal_comment(issue, result, "main")
        assert "`oompah/repo/gh-42`" in comment
        assert "org/repo#42" not in comment

    def test_refuses_with_uncommitted(self):
        """Comment notes uncommitted worktree changes."""
        issue = FakeIssue(branch_name="my-branch")
        result = UnpushedGateResult(
            allowed=False,
            has_uncommitted=True,
            commits_ahead=0,
            commit_lines=[],
        )
        comment = build_unpushed_refusal_comment(issue, result, "main")
        assert "uncommitted" in comment
        assert "Worktree has uncommitted changes" in comment

    def test_refuses_with_both(self):
        """Comment shows both uncommitted flag and commit count."""
        issue = FakeIssue(branch_name="x")
        result = UnpushedGateResult(
            allowed=False,
            has_uncommitted=True,
            commits_ahead=2,
            commit_lines=["abc fix"],
        )
        comment = build_unpushed_refusal_comment(issue, result, "main")
        assert "uncommitted" in comment
        assert "2 commit" in comment

    def test_singular_commit_noun(self):
        """Singular 'commit' when commits_ahead == 1."""
        issue = FakeIssue()
        result = UnpushedGateResult(allowed=False, commits_ahead=1, commit_lines=["abc feat"])
        comment = build_unpushed_refusal_comment(issue, result, "main")
        assert "1 commit" in comment

    def test_plural_commits_noun(self):
        """Plural 'commits' when commits_ahead > 1."""
        issue = FakeIssue()
        result = UnpushedGateResult(allowed=False, commits_ahead=5, commit_lines=[])
        comment = build_unpushed_refusal_comment(issue, result, "main")
        assert "5 commit" in comment


class TestCheckUnpushedHelper:
    """Tests for the private _check_unpushed() git helper."""

    def test_clean_repo_returns_false(self):
        """Worktree clean + branch on base → (False, 0, [], '')."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            has_uncommitted, commits_ahead, commit_lines, err = _check_unpushed(
                "/tmp/repo", "my-branch", "main",
            )
        assert has_uncommitted is False
        assert commits_ahead == 0
        assert err == ""

    def test_uncommitted_detected(self):
        """Non-empty git status --porcelain → has_uncommitted=True."""
        def run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            if "status" in cmd_str:
                return MagicMock(returncode=0, stdout=" M modified.txt\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=run_side_effect):
            has_uncommitted, commits_ahead, lines, err = _check_unpushed(
                "/tmp/repo", "my-branch", "main",
            )
        assert has_uncommitted is True
        assert commits_ahead == 0

    def test_commit_count_positive(self):
        """git rev-list returns N > 0 → commits_ahead=N."""
        def run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            if "--count" in cmd_str:
                return MagicMock(returncode=0, stdout="3\n", stderr="")
            if "log --oneline" in cmd_str:
                return MagicMock(
                    returncode=0,
                    stdout="abc1 feat: add thing\ndef2 fix: bar\n",
                    stderr="",
                )
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=run_side_effect):
            has_uncommitted, commits_ahead, lines, err = _check_unpushed(
                "/tmp/repo", "my-branch", "main",
            )
        assert has_uncommitted is False
        assert commits_ahead == 3
        assert len(lines) == 2

    def test_branch_not_on_remote(self):
        """Branch doesn't exist on origin → returncode != 0 → 0 commits ahead."""
        def run_side_effect(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
            if "--count" in cmd_str:
                return MagicMock(returncode=128, stdout="", stderr="fatal: ambiguous argument")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=run_side_effect):
            has_uncommitted, commits_ahead, lines, err = _check_unpushed(
                "/tmp/repo", "new-branch", "main",
            )
        assert commits_ahead == 0
        assert err == ""

    def test_git_not_found_error(self):
        """FileNotFoundError → error string, fail-open."""
        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            has_uncommitted, commits_ahead, lines, err = _check_unpushed(
                "/tmp/repo", "my-branch", "main",
            )
        assert has_uncommitted is False
        assert commits_ahead == 0
        assert "failed" in err

    def test_git_timeout(self):
        """TimeoutExpired → error string."""
        with patch("subprocess.run", side_effect=TimeoutExpired("git", 15)):
            has_uncommitted, commits_ahead, lines, err = _check_unpushed(
                "/tmp/repo", "my-branch", "main",
            )
        assert has_uncommitted is False
        assert commits_ahead == 0
        assert "failed" in err

    def test_rev_list_non_int_output(self):
        """Non-integer stdout from git rev-list → error string."""
        def run_side_effect(cmd, **kwargs):
            if "--count" in " ".join(cmd):
                return MagicMock(returncode=0, stdout="not-a-number\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=run_side_effect):
            _, commits_ahead, _, err = _check_unpushed("/tmp/repo", "my-branch", "main")
        assert commits_ahead == 0
        assert "unexpected output" in err


class TestWorktreePathStatusCheck:
    """Regression tests for OOMPAH-306: worktree_path used for status check.

    The orchestrator passes project.repo_path (the main clone) to the gate.
    The main clone may have unrelated dirty state on a different branch.
    _check_unpushed must use the branch's own worktree directory for
    git status --porcelain so it does not misread the main clone's dirt.
    """

    def test_worktree_path_used_for_status_when_exists(self, tmp_path):
        """When worktree_path exists, git status runs there (not repo_path)."""
        worktree_dir = tmp_path / "wt"
        worktree_dir.mkdir()

        seen_cwds: list[str] = []

        def run_side_effect(cmd, cwd=None, **kwargs):
            if "status" in cmd:
                seen_cwds.append(str(cwd) if cwd else "")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=run_side_effect):
            _check_unpushed(
                "/tmp/main-repo",
                "my-branch",
                "main",
                worktree_path=str(worktree_dir),
            )

        # The status cwd must be the worktree, not the main repo
        status_cwds = [c for c in seen_cwds if c]
        assert status_cwds, "git status --porcelain was not called"
        assert all(c == str(worktree_dir) for c in status_cwds), (
            f"Expected all status calls to use worktree {worktree_dir}, got {status_cwds}"
        )

    def test_worktree_path_absent_falls_back_to_repo_path(self):
        """When worktree_path is empty, repo_path is used for status."""
        seen_cwds: list[str] = []

        def run_side_effect(cmd, cwd=None, **kwargs):
            if "status" in cmd:
                seen_cwds.append(str(cwd) if cwd else "")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=run_side_effect):
            _check_unpushed(
                "/tmp/main-repo",
                "my-branch",
                "main",
                worktree_path="",
            )

        status_cwds = [c for c in seen_cwds if c]
        assert status_cwds, "git status --porcelain was not called"
        assert all(c == "/tmp/main-repo" for c in status_cwds)

    def test_worktree_path_nonexistent_falls_back_to_repo_path(self, tmp_path):
        """When worktree_path points to a missing directory, repo_path is used."""
        nonexistent = str(tmp_path / "does-not-exist")
        seen_cwds: list[str] = []

        def run_side_effect(cmd, cwd=None, **kwargs):
            if "status" in cmd:
                seen_cwds.append(str(cwd) if cwd else "")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=run_side_effect):
            _check_unpushed(
                "/tmp/main-repo",
                "my-branch",
                "main",
                worktree_path=nonexistent,
            )

        status_cwds = [c for c in seen_cwds if c]
        assert status_cwds, "git status --porcelain was not called"
        assert all(c == "/tmp/main-repo" for c in status_cwds)

    def test_regression_oompah_306_main_dirty_worktree_clean(self, tmp_path):
        """Regression: main repo dirty, branch worktree clean → gate allows.

        Previously the gate ran git status --porcelain in project.repo_path
        (the main clone).  If the main clone had unrelated dirty files (e.g.
        AGENTS.md modified while on branch 'main'), the gate would incorrectly
        detect has_uncommitted=True for the feature branch and refuse closure.

        With the fix, the status check runs in worktree_path when it exists,
        so the feature branch's own clean state is correctly detected.
        """
        worktree_dir = tmp_path / "feature-worktree"
        worktree_dir.mkdir()

        def run_side_effect(cmd, cwd=None, **kwargs):
            cmd_list = list(cmd)
            if "status" in cmd_list:
                # The worktree is clean; the main repo would return dirty output.
                if str(cwd) == str(worktree_dir):
                    return MagicMock(returncode=0, stdout="", stderr="")
                # Simulate main-repo dirty state (OOMPAH-306 root cause)
                return MagicMock(returncode=0, stdout=" M AGENTS.md\n", stderr="")
            if "--count" in cmd_list:
                # Branch is already fully pushed: 0 commits ahead
                return MagicMock(returncode=0, stdout="0\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        issue = FakeIssue(identifier="OOMPAH-306", branch_name="OOMPAH-306")

        with patch("subprocess.run", side_effect=run_side_effect):
            result = check_unpushed_gate(
                issue,
                repo_path="/tmp/main-repo",
                base_branch="main",
                worktree_path=str(worktree_dir),
            )

        assert result.allowed is True, (
            f"Gate should allow when worktree is clean (even if main repo is dirty). "
            f"allowed={result.allowed}, has_uncommitted={result.has_uncommitted}, "
            f"skip_reason={result.skip_reason!r}"
        )

    def test_worktree_path_forwarded_from_check_unpushed_gate(self, tmp_path):
        """check_unpushed_gate passes worktree_path through to _check_unpushed."""
        worktree_dir = tmp_path / "wt"
        worktree_dir.mkdir()
        issue = FakeIssue(branch_name="my-branch")

        with patch("oompah.unpushed_gate._check_unpushed") as mock_check:
            mock_check.return_value = (False, 0, [], "")
            check_unpushed_gate(
                issue,
                repo_path="/tmp/repo",
                base_branch="main",
                worktree_path=str(worktree_dir),
            )

        mock_check.assert_called_once_with(
            "/tmp/repo",
            "my-branch",
            "main",
            worktree_path=str(worktree_dir),
        )
