"""Tests for the native oompah Markdown tracker."""

from __future__ import annotations

import subprocess

import pytest
import yaml

from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.statuses import BACKLOG, DONE, OPEN
from oompah.tracker import TrackerError


def _tracker(tmp_path, *, git_sync: bool = False) -> OompahMarkdownTracker:
    root = tmp_path / "repo"
    root.mkdir()
    return OompahMarkdownTracker(
        active_states=[OPEN],
        terminal_states=[DONE],
        cwd=str(root),
        default_branch="main",
        git_sync=git_sync,
    )


def _frontmatter(path):
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    end = content.find("\n---", 4)
    assert end > 0
    return yaml.safe_load(content[4:end])


class TestOompahMarkdownTrackerCreate:
    def test_create_issue_writes_markdown_task_file(self, tmp_path):
        tracker = _tracker(tmp_path)

        issue = tracker.create_issue(
            "Normalize task priority creation",
            issue_type="bug",
            description="The CLI rejects documented priorities.",
            priority=1,
            labels=["cli"],
        )

        assert issue.identifier == "REPO-1"
        assert issue.state == BACKLOG
        assert issue.issue_type == "bug"
        assert issue.description == "The CLI rejects documented priorities."
        assert issue.priority == 1
        assert issue.tracker_kind == "oompah_md"

        path = tmp_path / "repo" / ".oompah" / "tasks" / "backlog" / "REPO-1.md"
        assert path.exists()
        meta = _frontmatter(path)
        assert meta["id"] == "REPO-1"
        assert meta["status"] == BACKLOG
        assert meta["type"] == "bug"
        assert meta["labels"] == ["cli"]

    def test_create_issue_uses_next_numeric_id(self, tmp_path):
        tracker = _tracker(tmp_path)

        first = tracker.create_issue("First")
        second = tracker.create_issue("Second")

        assert first.identifier == "REPO-1"
        assert second.identifier == "REPO-2"


class TestOompahMarkdownTrackerMutations:
    def test_update_status_moves_file_between_status_directories(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Move me")

        tracker.update_issue(issue.identifier, status=OPEN)

        old_path = tmp_path / "repo" / ".oompah" / "tasks" / "backlog" / "REPO-1.md"
        new_path = tmp_path / "repo" / ".oompah" / "tasks" / "open" / "REPO-1.md"
        assert not old_path.exists()
        assert new_path.exists()
        assert tracker.fetch_issue_detail("REPO-1").state == OPEN

    def test_labels_dependencies_parent_and_metadata_round_trip(self, tmp_path):
        tracker = _tracker(tmp_path)
        parent = tracker.create_issue("Epic", issue_type="epic")
        child = tracker.create_issue("Child")

        tracker.add_parent_child(child.identifier, parent.identifier)
        tracker.add_dependency(child.identifier, "REPO-99")
        tracker.add_label(child.identifier, "backend")
        tracker.set_metadata_field(child.identifier, "oompah.work_branch", "oompah/repo-1")

        refreshed = tracker.fetch_issue_detail(child.identifier)
        assert refreshed.parent_id == parent.identifier
        assert refreshed.blocked_by[0].identifier == "REPO-99"
        assert "backend" in refreshed.labels
        assert refreshed.work_branch == "oompah/repo-1"
        assert tracker.get_metadata(child.identifier)["oompah.work_branch"] == "oompah/repo-1"

        parent_refreshed = tracker.fetch_issue_detail(parent.identifier)
        parent_path = (
            tmp_path / "repo" / ".oompah" / "tasks" / "backlog" / "REPO-1.md"
        )
        assert child.identifier in _frontmatter(parent_path)["children"]
        assert parent_refreshed.issue_type == "epic"

    def test_comments_are_appended_and_parsed(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Needs comment")

        tracker.add_comment(issue.identifier, "Please fix this.", author="oompah")

        comments = tracker.fetch_comments(issue.identifier)
        assert len(comments) == 1
        assert comments[0]["author"] == "oompah"
        assert comments[0]["text"] == "Please fix this."

    def test_candidate_fetch_uses_active_states_only(self, tmp_path):
        tracker = _tracker(tmp_path)
        open_issue = tracker.create_issue("Open", initial_status=OPEN)
        tracker.create_issue("Backlog")

        candidates = tracker.fetch_candidate_issues()

        assert [issue.identifier for issue in candidates] == [open_issue.identifier]

    def test_fetch_in_progress_issues_returns_only_in_progress(self, tmp_path):
        tracker = _tracker(tmp_path)
        tracker.create_issue("Open", initial_status=OPEN)
        in_progress = tracker.create_issue("Stuck", initial_status="In Progress")

        issues = tracker.fetch_in_progress_issues()

        assert [issue.identifier for issue in issues] == [in_progress.identifier]
        path = tmp_path / "repo" / ".oompah" / "tasks" / "in-progress" / "REPO-2.md"
        assert path.exists()

    def test_close_issue_uses_terminal_state(self, tmp_path):
        tracker = _tracker(tmp_path)
        issue = tracker.create_issue("Close me", initial_status=OPEN)

        tracker.close_issue(issue.identifier)

        refreshed = tracker.fetch_issue_detail(issue.identifier)
        assert refreshed.state == DONE
        assert refreshed.closed_at is not None


class TestOompahMarkdownTrackerDefaultBranchGuard:
    def test_git_synced_writes_require_default_branch(self, tmp_path):
        root = tmp_path / "repo"
        root.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
        )
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=root, check=True)
        tracker = OompahMarkdownTracker(
            active_states=[OPEN],
            terminal_states=[DONE],
            cwd=str(root),
            default_branch="main",
            git_sync=True,
        )

        with pytest.raises(TrackerError, match="default branch"):
            tracker.create_issue("Should fail")
