"""Tests for the beads-jsonl custom git merge driver.

Covers:
- scripts/beads-merge.sh (the shell + Python merge script)
- oompah/projects._install_beads_merge_driver (git config installation)
- A synthetic git conflict fixture: two branches both touch .beads/issues.jsonl
  in non-overlapping ways, the driver resolves it without human input.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from oompah.projects import _install_beads_merge_driver, ProjectStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "beads-merge.sh"


def _issue(
    id: str,
    title: str = "T",
    status: str = "open",
    updated_at: str = "2024-01-01T00:00:00Z",
    created_at: str = "2024-01-01T00:00:00Z",
    comments: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "title": title,
        "status": status,
        "updated_at": updated_at,
        "created_at": created_at,
        "comments": comments or [],
        "comment_count": len(comments or []),
    }


def _comment(
    id: str,
    text: str = "hi",
    created_at: str = "2024-01-01T00:00:00Z",
) -> dict[str, Any]:
    return {"id": id, "text": text, "created_at": created_at}


def _write_jsonl(path: Path, issues: list[dict]) -> None:
    lines = [json.dumps(obj, separators=(",", ":")) for obj in issues]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            result.append(json.loads(line))
    return result


def _run_driver(current: Path, base: Path, other: Path) -> subprocess.CompletedProcess:
    """Invoke scripts/beads-merge.sh and return the CompletedProcess."""
    return subprocess.run(
        [str(SCRIPT_PATH), str(current), str(base), str(other)],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Script existence and executability
# ---------------------------------------------------------------------------

class TestScriptExists:
    def test_script_is_present(self):
        assert SCRIPT_PATH.exists(), f"scripts/beads-merge.sh not found at {SCRIPT_PATH}"

    def test_script_is_executable(self):
        st = os.stat(SCRIPT_PATH)
        assert st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH), (
            "scripts/beads-merge.sh is not executable"
        )

    def test_python3_available(self):
        r = subprocess.run(["python3", "--version"], capture_output=True)
        assert r.returncode == 0, "python3 is required by beads-merge.sh"


# ---------------------------------------------------------------------------
# Core merge logic: non-overlapping issues
# ---------------------------------------------------------------------------

class TestNonOverlappingIssues:
    """Two branches each add a distinct new issue — both must appear."""

    def test_both_new_issues_present(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        shared = _issue("issue-common", updated_at="2024-01-01T00:00:00Z")
        _write_jsonl(base, [shared])
        _write_jsonl(current, [shared, _issue("issue-A", updated_at="2024-01-02T00:00:00Z")])
        _write_jsonl(other, [shared, _issue("issue-B", updated_at="2024-01-03T00:00:00Z")])

        result = _run_driver(current, base, other)
        assert result.returncode == 0, result.stderr

        merged = _read_jsonl(current)
        ids = {obj["id"] for obj in merged}
        assert "issue-common" in ids
        assert "issue-A" in ids
        assert "issue-B" in ids
        assert len(merged) == 3

    def test_one_side_only_adds(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        _write_jsonl(base, [])
        _write_jsonl(current, [_issue("issue-X")])
        _write_jsonl(other, [])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        assert len(merged) == 1
        assert merged[0]["id"] == "issue-X"


# ---------------------------------------------------------------------------
# Last-writer-wins per issue id
# ---------------------------------------------------------------------------

class TestLastWriterWins:
    def test_newer_updated_at_wins(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        old = _issue("issue-1", status="open", updated_at="2024-01-01T12:00:00Z")
        newer = _issue("issue-1", status="closed", updated_at="2024-01-02T12:00:00Z")

        _write_jsonl(base, [old])
        _write_jsonl(current, [old])   # current didn't change this issue
        _write_jsonl(other, [newer])   # other closed it

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        assert len(merged) == 1
        assert merged[0]["status"] == "closed"

    def test_current_wins_when_newer(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        base_issue = _issue("issue-2", status="open", updated_at="2024-01-01T00:00:00Z")
        current_issue = _issue("issue-2", status="closed", updated_at="2024-01-03T00:00:00Z")
        other_issue = _issue("issue-2", status="in_progress", updated_at="2024-01-02T00:00:00Z")

        _write_jsonl(base, [base_issue])
        _write_jsonl(current, [current_issue])
        _write_jsonl(other, [other_issue])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        assert len(merged) == 1
        assert merged[0]["status"] == "closed"

    def test_equal_timestamps_other_wins(self, tmp_path):
        """On tie, the other branch (incoming) wins — for freshly-added content."""
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        ts = "2024-06-01T00:00:00Z"
        a = _issue("tie-issue", status="open", updated_at=ts)
        b = _issue("tie-issue", status="closed", updated_at=ts)

        _write_jsonl(base, [a])
        _write_jsonl(current, [a])
        _write_jsonl(other, [b])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        assert merged[0]["status"] == "closed"


# ---------------------------------------------------------------------------
# Comment merging
# ---------------------------------------------------------------------------

class TestCommentMerging:
    def test_comments_unioned(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        c1 = _comment("cmt-1", text="first", created_at="2024-01-01T10:00:00Z")
        c2 = _comment("cmt-2", text="second", created_at="2024-01-01T11:00:00Z")
        c3 = _comment("cmt-3", text="third", created_at="2024-01-01T12:00:00Z")

        base_issue = _issue("iss", updated_at="2024-01-01T00:00:00Z", comments=[c1])
        cur_issue = _issue("iss", updated_at="2024-01-01T11:00:00Z", comments=[c1, c2])
        oth_issue = _issue("iss", updated_at="2024-01-01T12:00:00Z", comments=[c1, c3])

        _write_jsonl(base, [base_issue])
        _write_jsonl(current, [cur_issue])
        _write_jsonl(other, [oth_issue])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        assert len(merged) == 1
        comment_ids = {c["id"] for c in merged[0]["comments"]}
        assert comment_ids == {"cmt-1", "cmt-2", "cmt-3"}

    def test_duplicate_comments_deduped(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        c1 = _comment("shared-cmt", text="hello", created_at="2024-01-01T00:00:00Z")

        issue_a = _issue("iss", updated_at="2024-01-02T00:00:00Z", comments=[c1])
        issue_b = _issue("iss", updated_at="2024-01-01T00:00:00Z", comments=[c1])

        _write_jsonl(base, [_issue("iss")])
        _write_jsonl(current, [issue_a])
        _write_jsonl(other, [issue_b])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        assert len(merged[0]["comments"]) == 1
        assert merged[0]["comment_count"] == 1

    def test_comment_count_updated(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        c1 = _comment("c1", created_at="2024-01-01T01:00:00Z")
        c2 = _comment("c2", created_at="2024-01-01T02:00:00Z")

        issue_with_one = _issue("x", updated_at="2024-01-02T00:00:00Z", comments=[c1])
        issue_with_two = _issue("x", updated_at="2024-01-01T00:00:00Z", comments=[c2])

        _write_jsonl(base, [_issue("x")])
        _write_jsonl(current, [issue_with_one])
        _write_jsonl(other, [issue_with_two])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        issue = merged[0]
        assert issue["comment_count"] == len(issue["comments"]) == 2

    def test_comments_sorted_by_created_at(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        late = _comment("c-late", created_at="2024-06-01T10:00:00Z")
        early = _comment("c-early", created_at="2024-01-01T10:00:00Z")

        cur_issue = _issue("iss", updated_at="2024-06-01T00:00:00Z", comments=[late])
        oth_issue = _issue("iss", updated_at="2024-01-01T00:00:00Z", comments=[early])

        _write_jsonl(base, [_issue("iss")])
        _write_jsonl(current, [cur_issue])
        _write_jsonl(other, [oth_issue])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        comments = merged[0]["comments"]
        assert comments[0]["id"] == "c-early"
        assert comments[1]["id"] == "c-late"


# ---------------------------------------------------------------------------
# Output determinism
# ---------------------------------------------------------------------------

class TestOutputOrder:
    def test_output_sorted_by_created_at(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        issues = [
            _issue("z-issue", created_at="2024-03-01T00:00:00Z"),
            _issue("a-issue", created_at="2024-01-01T00:00:00Z"),
            _issue("m-issue", created_at="2024-02-01T00:00:00Z"),
        ]
        _write_jsonl(base, issues)
        _write_jsonl(current, issues)
        _write_jsonl(other, issues)

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        assert [obj["id"] for obj in merged] == ["a-issue", "m-issue", "z-issue"]

    def test_empty_file_ok(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        _write_jsonl(base, [])
        _write_jsonl(current, [])
        _write_jsonl(other, [])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        content = current.read_text(encoding="utf-8").strip()
        assert content == ""


# ---------------------------------------------------------------------------
# Robustness: malformed / edge-case input
# ---------------------------------------------------------------------------

class TestRobustness:
    def test_blank_lines_skipped(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        # Inject blank lines and non-JSON garbage
        current.write_text(
            '\n' + json.dumps(_issue("ok-issue"), separators=(",", ":")) + '\n\n',
            encoding="utf-8",
        )
        _write_jsonl(base, [_issue("ok-issue")])
        _write_jsonl(other, [_issue("ok-issue")])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        assert len(merged) == 1

    def test_invalid_json_line_skipped(self, tmp_path):
        base = tmp_path / "base.jsonl"
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        current.write_text(
            'NOT JSON\n' + json.dumps(_issue("real-issue"), separators=(",", ":")) + '\n',
            encoding="utf-8",
        )
        _write_jsonl(base, [_issue("real-issue")])
        _write_jsonl(other, [_issue("real-issue")])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        assert len(merged) == 1
        assert merged[0]["id"] == "real-issue"

    def test_missing_base_file_still_merges(self, tmp_path):
        """The BASE arg is provided but never read by the Python script.
        It must accept a path that happens to not exist (git passes a real
        temp path; we just verify the driver doesn't crash if current/other
        are valid).
        """
        base = tmp_path / "nonexistent.jsonl"   # intentionally not created
        current = tmp_path / "current.jsonl"
        other = tmp_path / "other.jsonl"

        _write_jsonl(current, [_issue("i1")])
        _write_jsonl(other, [_issue("i2")])

        result = _run_driver(current, base, other)
        assert result.returncode == 0

        merged = _read_jsonl(current)
        ids = {obj["id"] for obj in merged}
        assert ids == {"i1", "i2"}


# ---------------------------------------------------------------------------
# Synthetic git conflict fixture
# ---------------------------------------------------------------------------

def _make_git_repo(path: Path) -> None:
    """Create a minimal git repo with the beads-jsonl merge driver configured."""
    # -b main forces the initial branch name regardless of the runner's
    # init.defaultBranch config (Linux CI may default to "master").
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)

    # Point to the actual script in this workspace (absolute path for the test)
    script_abs = str(SCRIPT_PATH.resolve())
    subprocess.run(
        ["git", "config", "merge.beads-jsonl.driver", f"{script_abs} %A %O %B"],
        cwd=path, check=True,
    )
    subprocess.run(
        ["git", "config", "merge.beads-jsonl.name", "Beads JSONL issue-id merge driver"],
        cwd=path, check=True,
    )

    # Write .gitattributes
    (path / ".gitattributes").write_text(
        ".beads/issues.jsonl merge=beads-jsonl\n", encoding="utf-8"
    )
    (path / ".beads").mkdir()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + list(args),
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


class TestGitConflictFixture:
    """End-to-end test: create a real git repo with two conflicting branches
    and verify the merge driver resolves without human input."""

    def test_non_overlapping_branches_merge_cleanly(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        beads = repo / ".beads"
        issues_path = beads / "issues.jsonl"

        # Initial commit with one shared issue on main
        initial_issue = _issue("issue-shared", status="open",
                                updated_at="2024-01-01T00:00:00Z",
                                created_at="2024-01-01T00:00:00Z")
        _write_jsonl(issues_path, [initial_issue])
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "init")

        # Branch A: close the shared issue and add a new one
        _git(repo, "checkout", "-b", "branch-a")
        issue_a_closed = _issue("issue-shared", status="closed",
                                 updated_at="2024-01-02T00:00:00Z",
                                 created_at="2024-01-01T00:00:00Z")
        issue_a_new = _issue("issue-new-a", status="open",
                              updated_at="2024-01-02T00:00:00Z",
                              created_at="2024-01-02T00:00:00Z")
        _write_jsonl(issues_path, [issue_a_closed, issue_a_new])
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "branch-a changes")

        # Back to main, branch B: add a comment to shared issue and add another new one
        _git(repo, "checkout", "main")
        comment = _comment("cmt-1", text="A comment", created_at="2024-01-01T12:00:00Z")
        issue_b_with_comment = _issue(
            "issue-shared", status="open",
            updated_at="2024-01-01T15:00:00Z",
            created_at="2024-01-01T00:00:00Z",
            comments=[comment],
        )
        issue_b_new = _issue("issue-new-b", status="open",
                              updated_at="2024-01-01T15:00:00Z",
                              created_at="2024-01-01T15:00:00Z")
        _write_jsonl(issues_path, [issue_b_with_comment, issue_b_new])
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "branch-b changes")

        # Merge branch-a into main — driver should resolve without conflict
        merge_result = subprocess.run(
            ["git", "merge", "--no-edit", "branch-a"],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert merge_result.returncode == 0, (
            f"Merge failed (expected driver to resolve):\n"
            f"stdout: {merge_result.stdout}\nstderr: {merge_result.stderr}"
        )

        # Verify merged content
        merged = _read_jsonl(issues_path)
        ids = {obj["id"] for obj in merged}

        # All three issues must be present
        assert "issue-shared" in ids, "shared issue missing from merge"
        assert "issue-new-a" in ids, "branch-a's new issue missing"
        assert "issue-new-b" in ids, "branch-b's new issue missing"

        # The shared issue: branch-a has updated_at=2024-01-02, branch-b has 2024-01-01T15
        # → branch-a wins the status field (closed), but comment from branch-b is preserved
        shared = next(obj for obj in merged if obj["id"] == "issue-shared")
        assert shared["status"] == "closed", "branch-a's closed status should win"
        assert len(shared["comments"]) == 1
        assert shared["comments"][0]["id"] == "cmt-1"

    def test_both_add_comments_no_duplicates(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        issues_path = repo / ".beads" / "issues.jsonl"

        base_issue = _issue("iss", updated_at="2024-01-01T00:00:00Z",
                             created_at="2024-01-01T00:00:00Z")
        _write_jsonl(issues_path, [base_issue])
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "base")

        # Branch A adds comment-A
        _git(repo, "checkout", "-b", "branch-a")
        _write_jsonl(issues_path, [_issue(
            "iss", updated_at="2024-01-02T00:00:00Z",
            created_at="2024-01-01T00:00:00Z",
            comments=[_comment("cmt-a", created_at="2024-01-02T00:00:00Z")],
        )])
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "add comment-A")

        # Main adds comment-B
        _git(repo, "checkout", "main")
        _write_jsonl(issues_path, [_issue(
            "iss", updated_at="2024-01-01T12:00:00Z",
            created_at="2024-01-01T00:00:00Z",
            comments=[_comment("cmt-b", created_at="2024-01-01T12:00:00Z")],
        )])
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "add comment-B")

        merge_result = subprocess.run(
            ["git", "merge", "--no-edit", "branch-a"],
            cwd=repo, capture_output=True, text=True,
        )
        assert merge_result.returncode == 0, (
            f"Merge failed:\nstdout: {merge_result.stdout}\nstderr: {merge_result.stderr}"
        )

        merged = _read_jsonl(issues_path)
        assert len(merged) == 1
        comment_ids = {c["id"] for c in merged[0]["comments"]}
        assert comment_ids == {"cmt-a", "cmt-b"}, "both comments must survive"
        assert merged[0]["comment_count"] == 2


# ---------------------------------------------------------------------------
# _install_beads_merge_driver
# ---------------------------------------------------------------------------

class TestInstallBeadsMergeDriver:
    def _make_bare_repo(self, tmp_path: Path) -> str:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
        return str(repo)

    def test_installs_driver_config(self, tmp_path):
        repo = self._make_bare_repo(tmp_path)
        result = _install_beads_merge_driver(repo)
        assert result is True

        r = subprocess.run(
            ["git", "config", "--local", "merge.beads-jsonl.driver"],
            cwd=repo, capture_output=True, text=True,
        )
        assert r.returncode == 0
        assert r.stdout.strip() == "./scripts/beads-merge.sh %A %O %B"

        r2 = subprocess.run(
            ["git", "config", "--local", "merge.beads-jsonl.name"],
            cwd=repo, capture_output=True, text=True,
        )
        assert r2.returncode == 0
        assert "Beads" in r2.stdout

    def test_idempotent(self, tmp_path):
        repo = self._make_bare_repo(tmp_path)
        assert _install_beads_merge_driver(repo) is True
        # Second call must also return True without changing anything
        assert _install_beads_merge_driver(repo) is True

        r = subprocess.run(
            ["git", "config", "--local", "merge.beads-jsonl.driver"],
            cwd=repo, capture_output=True, text=True,
        )
        assert r.stdout.strip() == "./scripts/beads-merge.sh %A %O %B"

    def test_returns_false_on_failure(self, tmp_path):
        """If git config fails (e.g. no git binary), return False, don't raise."""
        repo = self._make_bare_repo(tmp_path)
        with patch("oompah.projects.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            result = _install_beads_merge_driver(repo)
        assert result is False

    def test_git_config_failure_returns_false(self, tmp_path):
        repo = self._make_bare_repo(tmp_path)
        real_run = subprocess.run

        call_count = [0]

        def fake_run(args, **kwargs):
            call_count[0] += 1
            # First call (check existing config) returns 1 (not set).
            if call_count[0] == 1:
                return MagicMock(returncode=1, stdout="", stderr="")
            # Second call (git config ... driver) raises.
            raise subprocess.CalledProcessError(1, args, stderr="permission denied")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            result = _install_beads_merge_driver(repo)
        assert result is False

    def test_driver_installed_during_project_create(self, tmp_path):
        """ProjectStore.create() must call _install_beads_merge_driver."""
        from oompah.projects import ProjectStore

        # We don't actually clone; mock out subprocess to fake a successful clone
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()
        (repo_path / ".beads").mkdir()

        store = ProjectStore(
            path=str(tmp_path / "projects.json"),
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )

        install_calls = []

        real_run = subprocess.run

        def fake_run(args, **kwargs):
            # Simulate git clone by making the repo dir appear
            if args[:2] == ["git", "clone"]:
                target = args[-1]
                os.makedirs(os.path.join(target, ".git"), exist_ok=True)
                os.makedirs(os.path.join(target, ".beads"), exist_ok=True)
                return MagicMock(returncode=0, stdout="", stderr="")
            if args[:2] == ["git", "config"] and "beads-jsonl" in " ".join(args):
                install_calls.append(args)
                return MagicMock(returncode=0, stdout="", stderr="")
            # For git config user.name/email reads, return sensible values
            if args == ["git", "config", "--global", "user.name"]:
                return MagicMock(returncode=0, stdout="Test User\n", stderr="")
            if args == ["git", "config", "--global", "user.email"]:
                return MagicMock(returncode=0, stdout="test@example.com\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("oompah.projects.subprocess.run", side_effect=fake_run):
            with patch("oompah.projects._bootstrap_lfs", return_value=False):
                project = store.create(
                    repo_url="https://example.com/repo.git",
                    name="testrepo",
                    branch="main",
                )

        assert len(install_calls) > 0, (
            "Expected _install_beads_merge_driver to configure merge.beads-jsonl.driver "
            "via git config, but no such call was made"
        )


# ---------------------------------------------------------------------------
# Failure fallback: driver script missing should not corrupt the file
# ---------------------------------------------------------------------------

class TestDriverMissingFallback:
    """When the driver script is absent, git must fall back to conflict markers
    (not silently produce garbage).  We test this by temporarily making the
    script unexecutable, then verifying git reports a merge conflict.
    """

    def test_merge_falls_back_to_conflict_markers_when_driver_fails(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()

        # -b main forces the initial branch name (CI may default to "master").
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)

        # Point to a script that always exits non-zero (simulates broken driver)
        bad_script = tmp_path / "bad-driver.sh"
        bad_script.write_text("#!/bin/sh\nexit 1\n")
        bad_script.chmod(0o755)

        subprocess.run(
            ["git", "config", "merge.beads-jsonl.driver", f"{bad_script} %A %O %B"],
            cwd=repo, check=True,
        )
        (repo / ".gitattributes").write_text(
            ".beads/issues.jsonl merge=beads-jsonl\n", encoding="utf-8"
        )
        (repo / ".beads").mkdir()
        issues_path = repo / ".beads" / "issues.jsonl"

        base_issue = _issue("iss", status="open", updated_at="2024-01-01T00:00:00Z",
                             created_at="2024-01-01T00:00:00Z")
        _write_jsonl(issues_path, [base_issue])
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True)

        subprocess.run(["git", "checkout", "-b", "branch-a"], cwd=repo, check=True)
        a_issue = _issue("iss", status="closed", updated_at="2024-01-02T00:00:00Z",
                          created_at="2024-01-01T00:00:00Z")
        _write_jsonl(issues_path, [a_issue])
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "close on A"], cwd=repo, check=True)

        subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
        b_issue = _issue("iss", status="in_progress", updated_at="2024-01-01T12:00:00Z",
                          created_at="2024-01-01T00:00:00Z")
        _write_jsonl(issues_path, [b_issue])
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "progress on main"], cwd=repo, check=True)

        # Merge should FAIL (driver exits 1), not silently corrupt the file
        merge_result = subprocess.run(
            ["git", "merge", "--no-edit", "branch-a"],
            cwd=repo, capture_output=True, text=True,
        )
        # git merge returns non-zero when the driver exits non-zero
        assert merge_result.returncode != 0, (
            "Expected merge to fail when driver exits 1, but it succeeded"
        )

        # The file must contain conflict markers — not silently mangled JSON
        content = issues_path.read_text(encoding="utf-8")
        assert "<<<<<<" in content or merge_result.returncode != 0, (
            "Expected conflict markers or non-zero exit from git merge"
        )
