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
        labels: list[str] | None = None,
    ):
        self.id = id
        self.identifier = identifier
        self.issue_type = issue_type
        self.branch_name = branch_name
        self.labels = labels or []


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
        assert event["event"] == "landing_gate_stashed"
        assert event["issue_id"] == "id-x"
        assert event["issue_identifier"] == "bead-1"
        assert event["branch"] == "feat-x"
        assert event["branch_on_origin"] is False
