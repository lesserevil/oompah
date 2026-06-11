"""Tests for landing_gate: refuse escalation when agent completed without landing."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from oompah.landing_gate import (
    LandingGateResult,
    build_telemetry_event,
    check_landing_gate,
)


class FakeIssue:
    def __init__(
        self,
        id: str = "test-id",
        identifier: str = "test",
        issue_type: str = "task",
        branch_name: str = "test-branch",
        work_branch: str | None = None,
        labels: list[str] | None = None,
        parent_id: str | None = None,
    ):
        self.id = id
        self.identifier = identifier
        self.issue_type = issue_type
        self.branch_name = branch_name
        self.work_branch = work_branch
        self.labels = labels or []
        self.parent_id = parent_id


class FakeSubprocess:
    """Fake subprocess for testing git calls inside the gate."""

    def __init__(self, results: list[tuple[int, str, str]]):
        self.results = results
        self.calls: list[list[str]] = []

    def run(self, cmd: list[str], **kwargs: Any):
        self.calls.append(cmd)
        idx = len(self.calls) - 1
        if idx < len(self.results):
            code, stdout, stderr = self.results[idx]
            return MagicMock(returncode=code, stdout=stdout, stderr=stderr)
        return MagicMock(returncode=1, stdout="", stderr="")


class TestCheckLandingGateSkipRules:
    """Skip rules that always allow escalation/fail-open."""

    def test_epic_allowed(self, monkeypatch: pytest.MonkeyPatch):
        """Epics auto-close via children — gate never runs."""
        issue = FakeIssue(issue_type="epic")
        result = check_landing_gate(issue, workspace_path="/fake", base_branch="main")
        assert result.allowed is True
        assert result.skip_reason == "issue is an epic"

    def test_decomposed_allowed(self, monkeypatch: pytest.MonkeyPatch):
        """Decomposed issues are managed externally."""
        issue = FakeIssue(labels=["decomposed"])
        result = check_landing_gate(issue, workspace_path="/fake", base_branch="main")
        assert result.allowed is True
        assert result.skip_reason == "issue is decomposed"

    def test_no_branch_allowed(self, monkeypatch: pytest.MonkeyPatch):
        """No branch name and no identifier — fail open."""
        issue = FakeIssue(identifier="test", branch_name="")
        result = check_landing_gate(issue, workspace_path="/fake", base_branch="main")
        assert result.allowed is True

    def test_work_branch_preferred(self, monkeypatch: pytest.MonkeyPatch):
        """GitHub work branch is used instead of the issue identifier."""
        fake = FakeSubprocess([
            (0, "abc refs/heads/oompah/repo/gh-42\n", ""),
            (0, "1\n", ""),
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)
        issue = FakeIssue(
            identifier="org/repo#42",
            branch_name="org/repo#42",
            work_branch="oompah/repo/gh-42",
        )

        result = check_landing_gate(issue, workspace_path="/fake", base_branch="main")

        assert result.allowed is True
        assert result.effective_branch == "oompah/repo/gh-42"
        assert fake.calls[0][-1] == "oompah/repo/gh-42"
        assert "origin/oompah/repo/gh-42" in fake.calls[1][-1]


class TestCheckLandingGateBlocked:
    """Cases where the gate should refuse escalation."""

    def test_branch_not_on_origin_no_local_commits(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        """Branch never pushed and no local commits — agent produced nothing."""
        subprocess_results = [
            (0, "", ""),  # git ls-remote --heads → no output (branch not on origin)
            (0, "0\n", ""),  # git rev-list count (0 local commits)
        ]

        @dataclass
        class RunResult:
            returncode: int
            stdout: str
            stderr: str

        def fake_run(cmd: list[str], **kwargs: Any):
            idx = len(fake_run.calls)
            fake_run.calls.append(cmd)
            if idx < len(subprocess_results):
                code, stdout, stderr = subprocess_results[idx]
                return RunResult(code, stdout, stderr)
            return RunResult(1, "", "")

        fake_run.calls = []
        monkeypatch.setattr(subprocess, "run", fake_run)

        issue = FakeIssue(branch_name="feat-nothing")
        result = check_landing_gate(issue, workspace_path="/fake", base_branch="main")

        assert result.allowed is False
        assert result.branch_on_origin is False
        assert result.commits_on_origin == 0

    def test_branch_not_on_origin_but_local_commits_allowed(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        """Branch never pushed but has local commits — allow escalation."""
        subprocess_results = [
            (0, "", ""),  # git ls-remote --heads → no output
            (0, "3\n", ""),  # git rev-list count (3 local commits not pushed)
        ]

        @dataclass
        class RunResult:
            returncode: int
            stdout: str
            stderr: str

        def fake_run(cmd: list[str], **kwargs: Any):
            idx = len(fake_run.calls)
            fake_run.calls.append(cmd)
            if idx < len(subprocess_results):
                code, stdout, stderr = subprocess_results[idx]
                return RunResult(code, stdout, stderr)
            return RunResult(1, "", "")

        fake_run.calls = []
        monkeypatch.setattr(subprocess, "run", fake_run)

        issue = FakeIssue(branch_name="feat-done")
        result = check_landing_gate(issue, workspace_path="/fake", base_branch="main")

        assert result.allowed is True
        assert result.skip_reason.startswith("branch never pushed (3 local commits)")

    def test_branch_on_origin_but_not_merged_allowed(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        """Branch on origin with commits ahead — agent landed normally."""
        subprocess_results = [
            (0, "abc123 refs/heads/feat-done\n", ""),  # git ls-remote --heads
            (0, "5\n", ""),  # git rev-list count (5 commits ahead on origin)
        ]

        @dataclass
        class RunResult:
            returncode: int
            stdout: str
            stderr: str

        def fake_run(cmd: list[str], **kwargs: Any):
            idx = len(fake_run.calls)
            fake_run.calls.append(cmd)
            if idx < len(subprocess_results):
                code, stdout, stderr = subprocess_results[idx]
                return RunResult(code, stdout, stderr)
            return RunResult(1, "", "")

        fake_run.calls = []
        monkeypatch.setattr(subprocess, "run", fake_run)

        issue = FakeIssue(branch_name="feat-done")
        result = check_landing_gate(issue, workspace_path="/fake", base_branch="main")

        assert result.allowed is True
        assert result.branch_on_origin is True
        assert result.commits_on_origin == 5
        assert "agent landed normally" in result.skip_reason


class TestSharedEpicLandingGate:
    """Shared-epic children land on the parent epic branch — gate must check there."""

    def _make_fake_run(self, subprocess_results):
        """Return a fake subprocess.run that replays subprocess_results in order."""

        @dataclass
        class RunResult:
            returncode: int
            stdout: str
            stderr: str

        def fake_run(cmd: list[str], **kwargs: Any):
            idx = len(fake_run.calls)
            fake_run.calls.append(cmd)
            if idx < len(subprocess_results):
                code, stdout, stderr = subprocess_results[idx]
                return RunResult(code, stdout, stderr)
            return RunResult(1, "", "")

        fake_run.calls = []
        return fake_run

    def test_shared_epic_child_with_commits_on_epic_branch_allowed(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        """TASK-706.1-style: own branch absent, epic branch has commits → allowed."""
        # effective_branch='epic-TASK-706' is passed by the orchestrator
        # because the project uses epic_strategy=shared and the child's
        # work is committed there.
        subprocess_results = [
            # git ls-remote --heads origin epic-TASK-706 → branch exists
            (0, "abc123 refs/heads/epic-TASK-706\n", ""),
            # git rev-list --count origin/main..origin/epic-TASK-706 → 3 commits
            (0, "3\n", ""),
        ]
        fake_run = self._make_fake_run(subprocess_results)
        monkeypatch.setattr(subprocess, "run", fake_run)

        issue = FakeIssue(
            identifier="TASK-706.1",
            branch_name="TASK-706.1",
            parent_id="TASK-706",
        )
        result = check_landing_gate(
            issue,
            workspace_path="/fake",
            base_branch="main",
            effective_branch="epic-TASK-706",
        )

        assert result.allowed is True
        assert result.branch_on_origin is True
        assert result.commits_on_origin == 3
        assert result.effective_branch == "epic-TASK-706"
        assert "agent landed normally" in result.skip_reason
        # Confirm the gate checked the epic branch, not the child's own branch
        assert any("epic-TASK-706" in " ".join(call) for call in fake_run.calls)

    def test_shared_epic_child_no_commits_anywhere_blocked(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        """shared epic branch absent + no local commits → gate blocks (allowed=False)."""
        subprocess_results = [
            # git ls-remote --heads origin epic-TASK-706 → branch not present
            (0, "", ""),
            # git rev-list count (0 local commits on epic branch)
            (0, "0\n", ""),
        ]
        fake_run = self._make_fake_run(subprocess_results)
        monkeypatch.setattr(subprocess, "run", fake_run)

        issue = FakeIssue(
            identifier="TASK-706.2",
            branch_name="TASK-706.2",
            parent_id="TASK-706",
        )
        result = check_landing_gate(
            issue,
            workspace_path="/fake",
            base_branch="main",
            effective_branch="epic-TASK-706",
        )

        assert result.allowed is False
        assert result.branch_on_origin is False
        assert result.commits_on_origin == 0
        assert result.effective_branch == "epic-TASK-706"

    def test_flat_strategy_child_still_checks_own_branch(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        """Without effective_branch override, gate checks issue's own branch."""
        subprocess_results = [
            # git ls-remote --heads origin TASK-707.1 → exists
            (0, "def456 refs/heads/TASK-707.1\n", ""),
            # git rev-list --count origin/main..origin/TASK-707.1 → 2 commits
            (0, "2\n", ""),
        ]
        fake_run = self._make_fake_run(subprocess_results)
        monkeypatch.setattr(subprocess, "run", fake_run)

        issue = FakeIssue(
            identifier="TASK-707.1",
            branch_name="TASK-707.1",
        )
        # No effective_branch — flat strategy, caller does not pass one
        result = check_landing_gate(
            issue,
            workspace_path="/fake",
            base_branch="main",
        )

        assert result.allowed is True
        assert result.effective_branch == "TASK-707.1"
        assert result.commits_on_origin == 2
        # The checked branch must be TASK-707.1, not an epic branch
        ls_remote_call = fake_run.calls[0]
        assert "TASK-707.1" in ls_remote_call


class TestBuildTelemetryEvent:
    def test_basic_event(self):
        issue = FakeIssue(id="id-x", identifier="bead-1", branch_name="feat-x")
        result = LandingGateResult(
            allowed=False,
            branch_on_origin=False,
            commits_on_origin=0,
            local_only_commits=0,
        )
        event = build_telemetry_event(
            result, issue, "feat-x", "standard", "deep", 2, 1,
        )
        assert event["event"] == "landing_gate_retry_scheduled"
        assert event["issue_id"] == "id-x"
        assert event["issue_identifier"] == "bead-1"
        assert event["branch"] == "feat-x"
        assert event["branch_on_origin"] is False

    def test_effective_branch_included_when_different(self):
        """effective_branch appears in telemetry when it differs from branch."""
        issue = FakeIssue(id="id-y", identifier="TASK-706.1", branch_name="TASK-706.1")
        result = LandingGateResult(
            allowed=False,
            branch_on_origin=False,
            commits_on_origin=0,
            local_only_commits=0,
            effective_branch="epic-TASK-706",
        )
        event = build_telemetry_event(
            result, issue, "TASK-706.1", "standard", None, 1, 0,
        )
        assert event["effective_branch"] == "epic-TASK-706"

    def test_effective_branch_omitted_when_same(self):
        """No effective_branch key when it matches the nominal branch."""
        issue = FakeIssue(id="id-z", identifier="TASK-707", branch_name="TASK-707")
        result = LandingGateResult(
            allowed=False,
            branch_on_origin=False,
            commits_on_origin=0,
            local_only_commits=0,
            effective_branch="TASK-707",
        )
        event = build_telemetry_event(
            result, issue, "TASK-707", "standard", None, 1, 0,
        )
        assert "effective_branch" not in event
