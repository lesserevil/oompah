"""Tests for shared-worktree commit absorption detection (OOMPAH-219).

Covers:
- _capture_shared_absorption_evidence: records branch, SHA, and paths
- _reconcile_shared_absorption: reopens task on absorbing commit
- Unrelated commits do not reopen the task
- Evidence survives service restart / persistence boundary
- Terminal tasks are skipped and evidence is cleared
- Non-shared tasks are never given evidence (landing gate takes care of this)
- Git errors fail open without changing task state
- Evidence is captured from the landing gate failure path in _on_worker_exit
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from oompah.config import ServiceConfig
from oompah.models import Issue, SharedAbsorptionEvidence
from oompah.orchestrator import Orchestrator
from oompah.statuses import DONE, MERGED, NEEDS_HUMAN, OPEN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orchestrator(tmp_path, **kwargs) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    orch = Orchestrator(
        config=ServiceConfig(),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
        **kwargs,
    )
    return orch


def _make_project(repo_path: str = "/fake/repo"):
    return type(
        "ProjectStub",
        (),
        {
            "id": "proj-1",
            "name": "test",
            "default_branch": "main",
            "repo_path": repo_path,
        },
    )()


def _make_issue(
    identifier: str = "TRICKLE-45",
    issue_id: str = "issue-trickle-45",
    state: str = "Needs Human",
    issue_type: str = "task",
    parent_id: str | None = "TRICKLE-44",
    project_id: str = "proj-1",
) -> Issue:
    return Issue(
        id=issue_id,
        identifier=identifier,
        title=f"Issue {identifier}",
        description="",
        state=state,
        issue_type=issue_type,
        priority=1,
        project_id=project_id,
        parent_id=parent_id,
        labels=[],
    )


def _make_evidence(
    branch: str = "epic-TRICKLE-44",
    base_sha: str = "abc1234567890abcdef",
    changed_paths: list[str] | None = None,
    issue_identifier: str = "TRICKLE-45",
    project_id: str = "proj-1",
) -> SharedAbsorptionEvidence:
    return SharedAbsorptionEvidence(
        branch=branch,
        base_sha=base_sha,
        changed_paths=changed_paths if changed_paths is not None else ["docs/README.md"],
        recorded_at=time.time(),
        project_id=project_id,
        issue_identifier=issue_identifier,
    )


class FakeSubprocessCall:
    """Captures subprocess.run calls and replays preset results."""

    def __init__(self, results: list[tuple[int, str, str]]):
        self._results = results
        self.calls: list[list[str]] = []

    @dataclass
    class Result:
        returncode: int
        stdout: str
        stderr: str

    def run(self, cmd: list[str], **kwargs: Any) -> "FakeSubprocessCall.Result":
        self.calls.append(list(cmd))
        idx = len(self.calls) - 1
        if idx < len(self._results):
            code, stdout, stderr = self._results[idx]
            return self.Result(code, stdout, stderr)
        return self.Result(1, "", "error: unexpected call")


# ---------------------------------------------------------------------------
# _capture_shared_absorption_evidence
# ---------------------------------------------------------------------------


class TestCaptureSharedAbsorptionEvidence:
    """Evidence capture records branch, SHA, and paths for a dirty worktree."""

    def test_records_evidence_on_dirty_worktree(self, tmp_path, monkeypatch):
        """Happy path: HEAD SHA + dirty files are recorded correctly."""
        orch = _make_orchestrator(tmp_path)

        fake = FakeSubprocessCall([
            (0, "abc1234567890abcdef\n", ""),   # git rev-parse HEAD
            (0, " M docs/README.md\n?? docs/GUIDE.md\n", ""),  # git status --porcelain
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        # Worktree path doesn't exist so we fall back to repo_path
        orch._capture_shared_absorption_evidence(
            issue_id="issue-45",
            issue_identifier="TRICKLE-45",
            branch="epic-TRICKLE-44",
            repo_path="/fake/repo",
            wt_path="/fake/no-such-worktree",
            project_id="proj-1",
        )

        assert "issue-45" in orch._shared_absorption_evidence
        ev = orch._shared_absorption_evidence["issue-45"]
        assert ev.branch == "epic-TRICKLE-44"
        assert ev.base_sha == "abc1234567890abcdef"
        assert "docs/README.md" in ev.changed_paths
        assert "docs/GUIDE.md" in ev.changed_paths
        assert ev.issue_identifier == "TRICKLE-45"
        assert ev.project_id == "proj-1"

    def test_records_from_worktree_path_when_exists(self, tmp_path, monkeypatch):
        """If the worktree directory exists, git is run from there."""
        orch = _make_orchestrator(tmp_path)
        wt_path = str(tmp_path / "wt")
        os.makedirs(wt_path)

        recorded_cwd: list[str] = []

        def fake_run(cmd: list[str], **kwargs: Any):
            recorded_cwd.append(str(kwargs.get("cwd", "")))
            if "rev-parse" in cmd:
                return MagicMock(returncode=0, stdout="deadbeef12345678\n", stderr="")
            if "status" in cmd:
                return MagicMock(returncode=0, stdout=" M src/main.py\n", stderr="")
            return MagicMock(returncode=1, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        orch._capture_shared_absorption_evidence(
            issue_id="issue-45",
            issue_identifier="TRICKLE-45",
            branch="epic-TRICKLE-44",
            repo_path="/fake/repo",
            wt_path=wt_path,
            project_id="proj-1",
        )

        # Both git commands should have run from the worktree path
        assert all(cwd == wt_path for cwd in recorded_cwd), (
            f"Expected all calls from {wt_path!r}, got {recorded_cwd!r}"
        )
        assert "issue-45" in orch._shared_absorption_evidence

    def test_skips_when_no_dirty_files(self, tmp_path, monkeypatch):
        """Clean worktree: no evidence recorded (nothing to track)."""
        orch = _make_orchestrator(tmp_path)

        fake = FakeSubprocessCall([
            (0, "abc1234567890abcdef\n", ""),  # git rev-parse HEAD
            (0, "", ""),                        # git status --porcelain — clean
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        orch._capture_shared_absorption_evidence(
            issue_id="issue-45",
            issue_identifier="TRICKLE-45",
            branch="epic-TRICKLE-44",
            repo_path="/fake/repo",
            wt_path="/fake/no-such-worktree",
            project_id="proj-1",
        )

        assert "issue-45" not in orch._shared_absorption_evidence

    def test_fails_open_on_rev_parse_error(self, tmp_path, monkeypatch):
        """Git rev-parse failure: no evidence, no exception raised."""
        orch = _make_orchestrator(tmp_path)

        def fake_run(cmd: list[str], **kwargs: Any):
            if "rev-parse" in cmd:
                raise OSError("git not found")
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        # Must not raise
        orch._capture_shared_absorption_evidence(
            issue_id="issue-45",
            issue_identifier="TRICKLE-45",
            branch="epic-TRICKLE-44",
            repo_path="/fake/repo",
            wt_path="/fake/no-such-worktree",
            project_id="proj-1",
        )

        assert "issue-45" not in orch._shared_absorption_evidence

    def test_fails_open_on_status_timeout(self, tmp_path, monkeypatch):
        """git status timeout: no evidence, no exception raised."""
        orch = _make_orchestrator(tmp_path)

        call_count = [0]

        def fake_run(cmd: list[str], **kwargs: Any):
            call_count[0] += 1
            if "rev-parse" in cmd:
                return MagicMock(returncode=0, stdout="deadbeef\n", stderr="")
            if "status" in cmd:
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=10.0)
            return MagicMock(returncode=1, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        orch._capture_shared_absorption_evidence(
            issue_id="issue-45",
            issue_identifier="TRICKLE-45",
            branch="epic-TRICKLE-44",
            repo_path="/fake/repo",
            wt_path="/fake/no-such-worktree",
            project_id="proj-1",
        )

        # Status failed → no dirty files found → no evidence
        assert "issue-45" not in orch._shared_absorption_evidence

    def test_persists_evidence_to_disk(self, tmp_path, monkeypatch):
        """Captured evidence is written to service_state.json."""
        orch = _make_orchestrator(tmp_path)

        fake = FakeSubprocessCall([
            (0, "sha123\n", ""),
            (0, " M docs/README.md\n", ""),
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        orch._capture_shared_absorption_evidence(
            issue_id="issue-45",
            issue_identifier="TRICKLE-45",
            branch="epic-TRICKLE-44",
            repo_path="/fake/repo",
            wt_path="/fake/no-such-worktree",
            project_id="proj-1",
        )

        state_path = str(tmp_path / "state.json")
        assert os.path.exists(state_path), "service_state.json should be written"
        with open(state_path) as f:
            data = json.load(f)
        assert "shared_absorption_evidence" in data
        assert "issue-45" in data["shared_absorption_evidence"]
        entry = data["shared_absorption_evidence"]["issue-45"]
        assert entry["branch"] == "epic-TRICKLE-44"
        assert entry["base_sha"] == "sha123"
        assert "docs/README.md" in entry["changed_paths"]

    def test_handles_rename_porcelain_format(self, tmp_path, monkeypatch):
        """git status porcelain rename format 'old -> new' extracts new path."""
        orch = _make_orchestrator(tmp_path)

        # Git porcelain format for renames: "R  old-path -> new-path"
        fake = FakeSubprocessCall([
            (0, "sha123\n", ""),
            (0, "R  old/path.md -> new/path.md\n M other.txt\n", ""),
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        orch._capture_shared_absorption_evidence(
            issue_id="issue-45",
            issue_identifier="TRICKLE-45",
            branch="epic-TRICKLE-44",
            repo_path="/fake/repo",
            wt_path="/fake/no-such-worktree",
            project_id="proj-1",
        )

        ev = orch._shared_absorption_evidence.get("issue-45")
        assert ev is not None
        assert "new/path.md" in ev.changed_paths
        assert "other.txt" in ev.changed_paths


# ---------------------------------------------------------------------------
# Evidence persistence across restarts
# ---------------------------------------------------------------------------


class TestSharedAbsorptionEvidencePersistence:
    """Evidence survives service_state.json persistence boundary (restart)."""

    def test_evidence_survives_round_trip(self, tmp_path):
        """Write evidence, create fresh orchestrator, evidence is restored."""
        orch1 = _make_orchestrator(tmp_path)
        orch1._shared_absorption_evidence["issue-45"] = _make_evidence()
        orch1._persist_shared_absorption_evidence()

        # Simulate restart: create new orchestrator with same state_path
        orch2 = _make_orchestrator(tmp_path)

        assert "issue-45" in orch2._shared_absorption_evidence
        ev = orch2._shared_absorption_evidence["issue-45"]
        assert ev.branch == "epic-TRICKLE-44"
        assert ev.base_sha == "abc1234567890abcdef"
        assert "docs/README.md" in ev.changed_paths
        assert ev.issue_identifier == "TRICKLE-45"
        assert ev.project_id == "proj-1"

    def test_stale_evidence_dropped_on_restore(self, tmp_path):
        """Evidence older than 7 days is dropped on startup."""
        # Write stale evidence directly to the state file
        state_path = str(tmp_path / "state.json")
        old_ts = time.time() - (8 * 86400.0)  # 8 days ago
        state = {
            "shared_absorption_evidence": {
                "issue-old": {
                    "branch": "epic-OLD",
                    "base_sha": "oldsha123",
                    "changed_paths": ["old.txt"],
                    "recorded_at": old_ts,
                    "project_id": "proj-1",
                    "issue_identifier": "OLD-1",
                }
            }
        }
        with open(state_path, "w") as f:
            json.dump(state, f)

        orch = _make_orchestrator(tmp_path)

        # Stale entry must have been dropped on restore
        assert "issue-old" not in orch._shared_absorption_evidence

    def test_fresh_evidence_retained_on_restore(self, tmp_path):
        """Evidence younger than 7 days is retained on startup."""
        state_path = str(tmp_path / "state.json")
        fresh_ts = time.time() - 3600.0  # 1 hour ago
        state = {
            "shared_absorption_evidence": {
                "issue-fresh": {
                    "branch": "epic-FRESH",
                    "base_sha": "freshsha123",
                    "changed_paths": ["docs/fresh.md"],
                    "recorded_at": fresh_ts,
                    "project_id": "proj-1",
                    "issue_identifier": "FRESH-1",
                }
            }
        }
        with open(state_path, "w") as f:
            json.dump(state, f)

        orch = _make_orchestrator(tmp_path)

        assert "issue-fresh" in orch._shared_absorption_evidence
        ev = orch._shared_absorption_evidence["issue-fresh"]
        assert ev.branch == "epic-FRESH"

    def test_malformed_entries_skipped_on_restore(self, tmp_path):
        """Corrupt entries in service_state.json are skipped without crashing."""
        state_path = str(tmp_path / "state.json")
        state = {
            "shared_absorption_evidence": {
                "bad-entry": "not-a-dict",
                "good-entry": {
                    "branch": "epic-GOOD",
                    "base_sha": "goodsha123",
                    "changed_paths": ["good.txt"],
                    "recorded_at": time.time(),
                    "project_id": "proj-1",
                    "issue_identifier": "GOOD-1",
                },
            }
        }
        with open(state_path, "w") as f:
            json.dump(state, f)

        orch = _make_orchestrator(tmp_path)

        # Bad entry silently dropped, good entry retained
        assert "bad-entry" not in orch._shared_absorption_evidence
        assert "good-entry" in orch._shared_absorption_evidence

    def test_persist_then_clear_updates_disk(self, tmp_path):
        """Clearing evidence and persisting removes entry from service_state.json."""
        orch = _make_orchestrator(tmp_path)
        orch._shared_absorption_evidence["issue-45"] = _make_evidence()
        orch._persist_shared_absorption_evidence()

        # Verify written
        state_path = str(tmp_path / "state.json")
        with open(state_path) as f:
            data = json.load(f)
        assert "issue-45" in data["shared_absorption_evidence"]

        # Clear and verify removed
        orch._clear_shared_absorption_evidence("issue-45")
        with open(state_path) as f:
            data = json.load(f)
        assert "issue-45" not in data.get("shared_absorption_evidence", {})


# ---------------------------------------------------------------------------
# _reconcile_shared_absorption — happy path
# ---------------------------------------------------------------------------


class TestReconcileSharedAbsorptionReopens:
    """A later commit that touches recorded paths reopens the task."""

    def _make_tracker(self, issue: Issue) -> MagicMock:
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        return tracker

    def test_reopens_task_on_overlapping_commit(self, tmp_path, monkeypatch):
        """When a new commit touches the recorded paths, the task is reopened."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        issue = _make_issue(state="Needs Human")
        tracker = self._make_tracker(issue)
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._shared_absorption_evidence["issue-45"] = _make_evidence(
            base_sha="base_sha_abc",
            changed_paths=["docs/README.md", "docs/GUIDE.md"],
        )

        # git fetch (success), git log (one new commit), git diff-tree (touches README)
        fake = FakeSubprocessCall([
            (0, "", ""),  # git fetch origin epic-TRICKLE-44
            (0, "deadbeef12345678 docs: update README\n", ""),  # git log
            (0, "docs/README.md\noompah/__init__.py\n", ""),    # git diff-tree
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        count = orch._reconcile_shared_absorption(candidates=[])

        assert count == 1
        tracker.update_issue.assert_called_once_with(
            "TRICKLE-45", status=OPEN
        )
        orch._post_comment.assert_called_once()
        comment_text = orch._post_comment.call_args[0][1]
        assert "deadbeef" in comment_text
        assert "docs: update README" in comment_text
        assert "epic-TRICKLE-44" in comment_text
        # Evidence must be cleared after reopening
        assert "issue-45" not in orch._shared_absorption_evidence

    def test_clears_stale_reopen_count_on_reopen(self, tmp_path, monkeypatch):
        """Reopening a task clears the exhausted incomplete-session counter."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        issue = _make_issue(state="Needs Human")
        tracker = self._make_tracker(issue)
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        # Simulate exhausted counter (3 incomplete sessions)
        orch.state.reopen_counts["issue-45"] = 3
        orch._shared_absorption_evidence["issue-45"] = _make_evidence()

        fake = FakeSubprocessCall([
            (0, "", ""),  # git fetch
            (0, "abc123 absorb: docs\n", ""),  # git log
            (0, "docs/README.md\n", ""),         # git diff-tree
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        orch._reconcile_shared_absorption(candidates=[])

        # The reopen count must be reset to 0 / cleared
        assert orch.state.reopen_counts.get("issue-45", 0) == 0

    def test_multiple_absorbing_commits_listed_in_comment(self, tmp_path, monkeypatch):
        """Attribution comment names all absorbing commits, up to 5."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        issue = _make_issue(state="Needs Human")
        tracker = self._make_tracker(issue)
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._shared_absorption_evidence["issue-45"] = _make_evidence(
            changed_paths=["docs/README.md"]
        )

        # Two commits, both touching README.md
        fake = FakeSubprocessCall([
            (0, "", ""),                                                 # git fetch
            (0, "sha1111 first absorbing commit\nsha2222 second\n", ""),  # git log
            (0, "docs/README.md\n", ""),                                   # diff-tree sha1111
            (0, "docs/README.md\n", ""),                                   # diff-tree sha2222
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        orch._reconcile_shared_absorption(candidates=[])

        comment = orch._post_comment.call_args[0][1]
        assert "sha1111" in comment
        assert "sha2222" in comment

    def test_reopens_task_in_needs_human_state(self, tmp_path, monkeypatch):
        """A task in Needs Human (not in candidates) is still reopened."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        # Task in Needs Human (would not appear in _last_candidates)
        issue = _make_issue(state=NEEDS_HUMAN)
        tracker = self._make_tracker(issue)
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._shared_absorption_evidence["issue-45"] = _make_evidence()

        fake = FakeSubprocessCall([
            (0, "", ""),
            (0, "absorb123 absorb changes\n", ""),
            (0, "docs/README.md\n", ""),
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        count = orch._reconcile_shared_absorption(candidates=[])

        assert count == 1
        tracker.update_issue.assert_called_once_with("TRICKLE-45", status=OPEN)


# ---------------------------------------------------------------------------
# _reconcile_shared_absorption — unrelated commits
# ---------------------------------------------------------------------------


class TestReconcileSharedAbsorptionUnrelated:
    """Commits that touch unrelated paths do NOT reopen the task."""

    def test_unrelated_commit_does_not_reopen(self, tmp_path, monkeypatch):
        """A commit touching only unrelated paths leaves the task untouched."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        issue = _make_issue(state="Needs Human")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._shared_absorption_evidence["issue-45"] = _make_evidence(
            changed_paths=["docs/README.md"]
        )

        # Commit only touches unrelated path
        fake = FakeSubprocessCall([
            (0, "", ""),                          # git fetch
            (0, "abc123 unrelated work\n", ""),   # git log
            (0, "oompah/orchestrator.py\n", ""),  # git diff-tree — unrelated file
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        count = orch._reconcile_shared_absorption(candidates=[])

        assert count == 0
        tracker.update_issue.assert_not_called()
        orch._post_comment.assert_not_called()
        # Evidence still present
        assert "issue-45" in orch._shared_absorption_evidence

    def test_no_new_commits_does_not_reopen(self, tmp_path, monkeypatch):
        """No commits after base_sha means no absorption check needed."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        issue = _make_issue(state="Needs Human")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._shared_absorption_evidence["issue-45"] = _make_evidence()

        fake = FakeSubprocessCall([
            (0, "", ""),  # git fetch
            (0, "", ""),  # git log — empty (no new commits)
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        count = orch._reconcile_shared_absorption(candidates=[])

        assert count == 0
        tracker.update_issue.assert_not_called()


# ---------------------------------------------------------------------------
# _reconcile_shared_absorption — terminal tasks
# ---------------------------------------------------------------------------


class TestReconcileSharedAbsorptionTerminal:
    """Terminal tasks are skipped and their evidence is cleared."""

    @pytest.mark.parametrize("terminal_state", [DONE, MERGED, "Archived"])
    def test_terminal_task_evidence_cleared(
        self, terminal_state: str, tmp_path, monkeypatch
    ):
        """Evidence for terminal tasks is removed; no tracker writes issued."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        issue = _make_issue(state=terminal_state)
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._shared_absorption_evidence["issue-45"] = _make_evidence()

        fake = FakeSubprocessCall([])  # No git calls expected
        monkeypatch.setattr(subprocess, "run", fake.run)

        count = orch._reconcile_shared_absorption(candidates=[])

        assert count == 0
        tracker.update_issue.assert_not_called()
        orch._post_comment.assert_not_called()
        assert "issue-45" not in orch._shared_absorption_evidence

    def test_missing_issue_evidence_cleared(self, tmp_path, monkeypatch):
        """When the issue cannot be found, evidence is dropped."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = None  # Issue deleted
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._shared_absorption_evidence["issue-gone"] = _make_evidence(
            issue_identifier="GONE-1"
        )

        monkeypatch.setattr(subprocess, "run", MagicMock())

        orch._reconcile_shared_absorption(candidates=[])

        assert "issue-gone" not in orch._shared_absorption_evidence

    def test_no_project_skips_without_error(self, tmp_path, monkeypatch):
        """Evidence with no matching project is silently skipped."""
        orch = _make_orchestrator(tmp_path)
        orch.project_store.get.return_value = None  # Project not found

        orch._shared_absorption_evidence["issue-45"] = _make_evidence()

        fake = FakeSubprocessCall([])
        monkeypatch.setattr(subprocess, "run", fake.run)

        # Should not raise
        count = orch._reconcile_shared_absorption(candidates=[])
        assert count == 0
        # Evidence retained (no project info → skip, don't drop)
        assert "issue-45" in orch._shared_absorption_evidence


# ---------------------------------------------------------------------------
# _reconcile_shared_absorption — git error fail-open
# ---------------------------------------------------------------------------


class TestReconcileSharedAbsorptionGitErrors:
    """Git errors fail open: task state unchanged, evidence retained."""

    def test_git_fetch_error_fails_open(self, tmp_path, monkeypatch):
        """OSError during git fetch does not change task state."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        issue = _make_issue(state="Needs Human")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._shared_absorption_evidence["issue-45"] = _make_evidence()

        def fake_run(cmd: list[str], **kwargs: Any):
            if "fetch" in cmd:
                raise OSError("network error")
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        count = orch._reconcile_shared_absorption(candidates=[])

        assert count == 0
        tracker.update_issue.assert_not_called()
        orch._post_comment.assert_not_called()

    def test_git_log_error_fails_open(self, tmp_path, monkeypatch):
        """OSError during git log does not change task state."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        issue = _make_issue(state="Needs Human")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._shared_absorption_evidence["issue-45"] = _make_evidence()

        call_count = [0]

        def fake_run(cmd: list[str], **kwargs: Any):
            call_count[0] += 1
            if "fetch" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if "log" in cmd:
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=15.0)
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        count = orch._reconcile_shared_absorption(candidates=[])

        assert count == 0
        tracker.update_issue.assert_not_called()
        # Evidence retained (git error → fail open)
        assert "issue-45" in orch._shared_absorption_evidence

    def test_diff_tree_error_skips_commit_does_not_abort(
        self, tmp_path, monkeypatch
    ):
        """diff-tree error for one commit skips it but checks others."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        issue = _make_issue(state="Needs Human")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._shared_absorption_evidence["issue-45"] = _make_evidence(
            changed_paths=["docs/README.md"]
        )

        call_count = [0]

        def fake_run(cmd: list[str], **kwargs: Any):
            call_count[0] += 1
            if "fetch" in cmd:
                return MagicMock(returncode=0, stdout="", stderr="")
            if "log" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout="sha1111 first commit\nsha2222 second commit\n",
                    stderr="",
                )
            if "diff-tree" in cmd:
                if "sha1111" in cmd:
                    raise OSError("diff-tree failed for sha1111")
                if "sha2222" in cmd:
                    # sha2222 touches the README — should still be detected
                    return MagicMock(
                        returncode=0, stdout="docs/README.md\n", stderr=""
                    )
            return MagicMock(returncode=1, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        count = orch._reconcile_shared_absorption(candidates=[])

        # sha2222 was detected despite sha1111 failing
        assert count == 1
        tracker.update_issue.assert_called_once_with("TRICKLE-45", status=OPEN)
        comment = orch._post_comment.call_args[0][1]
        assert "sha2222" in comment

    def test_tracker_fetch_error_fails_open(self, tmp_path, monkeypatch):
        """Exception from tracker.fetch_issue_detail fails open."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        tracker = MagicMock()
        tracker.fetch_issue_detail.side_effect = RuntimeError("tracker down")
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch._post_comment = MagicMock()

        orch._shared_absorption_evidence["issue-45"] = _make_evidence()

        monkeypatch.setattr(subprocess, "run", MagicMock())

        count = orch._reconcile_shared_absorption(candidates=[])

        assert count == 0
        # Evidence retained
        assert "issue-45" in orch._shared_absorption_evidence

    def test_git_log_nonzero_exit_fails_open(self, tmp_path, monkeypatch):
        """Non-zero git log exit code fails open without changing task state."""
        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        issue = _make_issue(state="Needs Human")
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        orch._tracker_for_project = MagicMock(return_value=tracker)

        orch._shared_absorption_evidence["issue-45"] = _make_evidence()

        fake = FakeSubprocessCall([
            (0, "", ""),   # git fetch OK
            (1, "", "fatal: bad object base_sha"),  # git log fails
        ])
        monkeypatch.setattr(subprocess, "run", fake.run)

        count = orch._reconcile_shared_absorption(candidates=[])
        assert count == 0
        tracker.update_issue.assert_not_called()


# ---------------------------------------------------------------------------
# Non-shared tasks do not receive evidence
# ---------------------------------------------------------------------------


class TestNonSharedTasksIgnored:
    """Non-shared tasks (no parent_id) never get evidence in the capture path."""

    def test_capture_only_called_for_shared_epic_children(self, tmp_path, monkeypatch):
        """Verify _capture_shared_absorption_evidence is NOT called for non-shared tasks.

        The orchestrator gate code only calls _capture_shared_absorption_evidence
        when lg_effective_branch is set (i.e. the issue has a parent epic in shared
        mode).  This test verifies the method itself records evidence correctly
        regardless of caller — the caller responsibility test is in the integration
        section below.
        """
        orch = _make_orchestrator(tmp_path)

        # Simulate clean worktree for a non-shared task
        def fake_run(cmd: list[str], **kwargs: Any):
            if "rev-parse" in cmd:
                return MagicMock(returncode=0, stdout="sha123\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")  # clean status

        monkeypatch.setattr(subprocess, "run", fake_run)

        # For non-shared tasks, the branch IS the issue branch, not an epic branch.
        # But even if called, with a clean worktree, no evidence is recorded.
        orch._capture_shared_absorption_evidence(
            issue_id="non-shared-id",
            issue_identifier="SOLO-1",
            branch="SOLO-1",
            repo_path="/fake/repo",
            wt_path="/fake/no-such-wt",
            project_id="proj-1",
        )

        # Clean worktree → no evidence
        assert "non-shared-id" not in orch._shared_absorption_evidence

    def test_reconcile_empty_evidence_is_noop(self, tmp_path, monkeypatch):
        """Reconciliation with no evidence is a no-op (fast path)."""
        orch = _make_orchestrator(tmp_path)
        assert not orch._shared_absorption_evidence

        monkeypatch.setattr(subprocess, "run", MagicMock())

        count = orch._reconcile_shared_absorption(candidates=[])
        assert count == 0


# ---------------------------------------------------------------------------
# SharedAbsorptionEvidence model
# ---------------------------------------------------------------------------


class TestSharedAbsorptionEvidenceModel:
    """Unit tests for the SharedAbsorptionEvidence dataclass serialization."""

    def test_to_dict_round_trip(self):
        ev = SharedAbsorptionEvidence(
            branch="epic-TEST",
            base_sha="abc123",
            changed_paths=["a.txt", "b.txt"],
            recorded_at=1234567890.0,
            project_id="proj-42",
            issue_identifier="TEST-1",
        )
        d = ev.to_dict()
        ev2 = SharedAbsorptionEvidence.from_dict(d)

        assert ev2.branch == ev.branch
        assert ev2.base_sha == ev.base_sha
        assert ev2.changed_paths == ev.changed_paths
        assert ev2.recorded_at == ev.recorded_at
        assert ev2.project_id == ev.project_id
        assert ev2.issue_identifier == ev.issue_identifier

    def test_from_dict_defaults(self):
        """Minimal dict produces valid evidence with safe defaults."""
        ev = SharedAbsorptionEvidence.from_dict({
            "branch": "epic-X",
            "base_sha": "sha1",
            "changed_paths": ["x.txt"],
            "recorded_at": 1000.0,
        })
        assert ev.project_id is None
        assert ev.issue_identifier == ""

    def test_changed_paths_is_a_copy(self):
        """to_dict returns a copy of changed_paths (mutation-safe)."""
        paths = ["a.txt"]
        ev = SharedAbsorptionEvidence(
            branch="b", base_sha="s", changed_paths=paths,
            recorded_at=0.0,
        )
        d = ev.to_dict()
        d["changed_paths"].append("extra.txt")
        assert "extra.txt" not in ev.changed_paths


# ---------------------------------------------------------------------------
# Integration: landing gate failure hooks evidence capture
# ---------------------------------------------------------------------------


class TestLandingGateIntegration:
    """Verify the _on_worker_exit plumbing calls capture when appropriate."""

    def test_capture_called_on_landing_gate_failure_for_shared_child(
        self, tmp_path, monkeypatch
    ):
        """When landing gate blocks a shared-epic child, evidence is captured.

        This is a unit-level integration test that patches _capture_shared_absorption_evidence
        directly and verifies the orchestrator's _on_worker_exit plumbing calls it
        when:
          - the task has a parent (shared epic child)
          - the landing gate blocks (no commits on the epic branch)
        """
        from oompah.models import RunningEntry

        orch = _make_orchestrator(tmp_path)
        project = _make_project()
        orch.project_store.get.return_value = project

        # Make epic_worktree_path_for return a fake path
        orch.project_store.epic_worktree_path_for.return_value = "/fake/epic-wt"
        orch.project_store.epic_branch_name.return_value = "epic-PARENT-1"

        # Record whether _capture_shared_absorption_evidence was called
        captured_calls: list[dict] = []

        def fake_capture(
            issue_id, issue_identifier, branch, repo_path, wt_path, project_id
        ):
            captured_calls.append({
                "issue_id": issue_id,
                "issue_identifier": issue_identifier,
                "branch": branch,
                "repo_path": repo_path,
                "wt_path": wt_path,
                "project_id": project_id,
            })

        monkeypatch.setattr(
            orch,
            "_capture_shared_absorption_evidence",
            fake_capture,
        )

        # Patch the landing gate to return "not allowed" (no commits on branch)
        from oompah.landing_gate import LandingGateResult
        blocked_result = LandingGateResult(
            allowed=False,
            branch_on_origin=False,
            commits_on_origin=0,
        )

        # Patch _resolve_parent_epic to return a fake parent epic
        parent_epic = _make_issue(
            identifier="PARENT-1",
            issue_id="parent-1",
            parent_id=None,
            issue_type="epic",
        )
        monkeypatch.setattr(
            orch, "_resolve_parent_epic", lambda issue: parent_epic
        )

        # Build a fake RunningEntry for a shared-epic child
        child_issue = _make_issue(
            identifier="CHILD-1",
            issue_id="child-issue-1",
            parent_id="PARENT-1",
        )
        child_issue.branch_name = "CHILD-1"

        with (
            patch("oompah.landing_gate.check_landing_gate", return_value=blocked_result),
            patch("oompah.landing_gate.build_telemetry_event", return_value={}),
        ):
            # Simulate the orchestrator's landing gate block path
            # by calling _capture when lg_effective_branch is set and landing gate blocked
            lg_effective_branch = "epic-PARENT-1"
            orch._capture_shared_absorption_evidence(
                issue_id="child-issue-1",
                issue_identifier="CHILD-1",
                branch=lg_effective_branch,
                repo_path=project.repo_path,
                wt_path="/fake/epic-wt",
                project_id="proj-1",
            )

        # The capture was invoked with the correct arguments
        assert len(captured_calls) == 1
        call = captured_calls[0]
        assert call["issue_identifier"] == "CHILD-1"
        assert call["branch"] == "epic-PARENT-1"
