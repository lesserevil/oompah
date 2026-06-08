"""Tests for the release-pick commit resolver (TASK-455.2).

Covers:
  - resolve_commits_for_entry: all 3 strategies (explicit, SCM, git)
  - resolve_and_record_commits: metadata write-back and idempotency
  - _resolve_via_scm: merged / not-merged / not-found / error paths
  - _resolve_via_git: success / non-zero exit / timeout / no commits
  - _write_commits_to_metadata: replace existing entry, append new entry,
    preserve other entries, propagate tracker errors
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from unittest.mock import MagicMock, call, patch

import pytest

from oompah.models import Issue
from oompah.release_pick_commit_resolver import (
    _resolve_via_git,
    _resolve_via_scm,
    _write_commits_to_metadata,
    resolve_and_record_commits,
    resolve_commits_for_entry,
)
from oompah.release_pick_schema import (
    BackportEntry,
    ReleasePick,
    backports_to_raw,
    parse_backports,
)
from oompah.statuses import MERGED, OPEN


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _issue(
    identifier: str = "TASK-1",
    title: str = "Feature work",
    branch_name: str | None = None,
    state: str = MERGED,
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=title,
        description="desc",
        state=state,
        branch_name=branch_name or identifier,
    )


def _entry(
    branch: str = "release/1.0",
    commits: list[str] | None = None,
    status: ReleasePick = ReleasePick.TASK_CREATED,
    task_id: str | None = "TASK-1.1",
    pr_url: str | None = None,
) -> BackportEntry:
    return BackportEntry(
        branch=branch,
        commits=list(commits or []),
        status=status,
        task_id=task_id,
        pr_url=pr_url,
    )


def _make_scm(
    pr_state: str | None = "merged",
    pr_id: str = "42",
    commits: list[str] | None = None,
    find_raises: Exception | None = None,
    commits_raises: Exception | None = None,
) -> MagicMock:
    """Build a mock SCM provider with configurable behaviour."""
    scm = MagicMock()

    if find_raises is not None:
        scm.find_pr_for_branch.side_effect = find_raises
    elif pr_state is None:
        scm.find_pr_for_branch.return_value = None
    else:
        pr = MagicMock()
        pr.id = pr_id
        pr.state = pr_state
        scm.find_pr_for_branch.return_value = pr

    if commits_raises is not None:
        scm.get_pr_commits.side_effect = commits_raises
    else:
        scm.get_pr_commits.return_value = list(commits or ["abc123", "def456"])

    return scm


def _make_tracker(
    metadata: dict | None = None,
) -> MagicMock:
    """Build a mock tracker."""
    tracker = MagicMock()
    _meta = dict(metadata or {})

    def _get_meta(identifier: str) -> dict:
        return _meta.get(identifier, {})

    tracker.get_metadata.side_effect = _get_meta
    return tracker


# ---------------------------------------------------------------------------
# resolve_commits_for_entry — Strategy 1: explicit commits
# ---------------------------------------------------------------------------


class TestExplicitCommits:
    def test_returns_explicit_commits_immediately(self):
        task = _issue()
        entry = _entry(commits=["aaa", "bbb"])
        scm = _make_scm()

        result = resolve_commits_for_entry(task, entry, scm=scm, repo="org/repo")

        assert result == ["aaa", "bbb"]
        # SCM should NOT be called when commits are already known
        scm.find_pr_for_branch.assert_not_called()
        scm.get_pr_commits.assert_not_called()

    def test_single_explicit_commit(self):
        task = _issue()
        entry = _entry(commits=["only_sha"])

        result = resolve_commits_for_entry(task, entry)

        assert result == ["only_sha"]

    def test_explicit_commits_returned_as_new_list(self):
        """Result must be a copy, not a reference to entry.commits."""
        original = ["sha1", "sha2"]
        task = _issue()
        entry = _entry(commits=original)

        result = resolve_commits_for_entry(task, entry)

        assert result == original
        result.append("sha3")
        assert entry.commits == original  # entry.commits not mutated


# ---------------------------------------------------------------------------
# resolve_commits_for_entry — Strategy 2: SCM PR lookup
# ---------------------------------------------------------------------------


class TestSCMStrategy:
    def test_resolves_commits_from_merged_pr(self):
        task = _issue()
        entry = _entry()
        scm = _make_scm(pr_state="merged", commits=["c1", "c2", "c3"])

        result = resolve_commits_for_entry(task, entry, scm=scm, repo="org/repo")

        assert result == ["c1", "c2", "c3"]
        scm.find_pr_for_branch.assert_called_once_with("org/repo", task.branch_name)
        scm.get_pr_commits.assert_called_once_with("org/repo", "42")

    def test_skips_open_pr(self):
        task = _issue()
        entry = _entry()
        scm = _make_scm(pr_state="open")

        result = resolve_commits_for_entry(task, entry, scm=scm, repo="org/repo")

        assert result == []
        scm.get_pr_commits.assert_not_called()

    def test_skips_closed_non_merged_pr(self):
        task = _issue()
        entry = _entry()
        scm = _make_scm(pr_state="closed")

        result = resolve_commits_for_entry(task, entry, scm=scm, repo="org/repo")

        assert result == []
        scm.get_pr_commits.assert_not_called()

    def test_skips_when_no_pr_found(self):
        task = _issue()
        entry = _entry()
        scm = _make_scm(pr_state=None)

        result = resolve_commits_for_entry(task, entry, scm=scm, repo="org/repo")

        assert result == []
        scm.get_pr_commits.assert_not_called()

    def test_find_pr_exception_returns_empty(self):
        task = _issue()
        entry = _entry()
        scm = _make_scm(find_raises=RuntimeError("API error"))

        result = resolve_commits_for_entry(task, entry, scm=scm, repo="org/repo")

        assert result == []

    def test_get_pr_commits_exception_returns_empty(self):
        task = _issue()
        entry = _entry()
        scm = _make_scm(pr_state="merged", commits_raises=RuntimeError("API error"))

        result = resolve_commits_for_entry(task, entry, scm=scm, repo="org/repo")

        assert result == []

    def test_merged_pr_with_empty_commits_returns_empty(self):
        task = _issue()
        entry = _entry()
        scm = _make_scm(pr_state="merged", commits=[])

        result = resolve_commits_for_entry(task, entry, scm=scm, repo="org/repo")

        assert result == []

    def test_skips_scm_when_repo_missing(self):
        """No repo slug → SCM strategy silently skipped."""
        task = _issue()
        entry = _entry()
        scm = _make_scm(pr_state="merged")

        result = resolve_commits_for_entry(task, entry, scm=scm, repo=None)

        scm.find_pr_for_branch.assert_not_called()
        assert result == []

    def test_skips_scm_when_scm_is_none(self):
        task = _issue()
        entry = _entry()

        # Passing repo without scm → no SCM call, no error
        result = resolve_commits_for_entry(task, entry, scm=None, repo="org/repo")

        assert result == []

    def test_uses_branch_name_for_lookup(self):
        """The lookup uses source_task.branch_name, not source_task.identifier."""
        task = _issue(identifier="TASK-10", branch_name="feature/my-work")
        entry = _entry()
        scm = _make_scm(pr_state="merged", commits=["sha1"])

        resolve_commits_for_entry(task, entry, scm=scm, repo="org/repo")

        scm.find_pr_for_branch.assert_called_once_with("org/repo", "feature/my-work")

    def test_falls_back_to_identifier_when_branch_name_none(self):
        """When branch_name is None, fall back to identifier."""
        task = _issue(identifier="TASK-10", branch_name=None)
        entry = _entry()
        scm = _make_scm(pr_state="merged", commits=["sha1"])

        resolve_commits_for_entry(task, entry, scm=scm, repo="org/repo")

        scm.find_pr_for_branch.assert_called_once_with("org/repo", "TASK-10")


# ---------------------------------------------------------------------------
# resolve_commits_for_entry — Strategy 3: git rev-list fallback
# ---------------------------------------------------------------------------


class TestGitStrategy:
    def test_resolves_commits_via_git_revlist(self, tmp_path):
        task = _issue()
        entry = _entry()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "aabbcc\nddeeff\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = resolve_commits_for_entry(
                task, entry, repo_path=str(tmp_path), default_branch="main"
            )

        assert result == ["aabbcc", "ddeeff"]
        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        assert "git" in cmd[0]
        assert "rev-list" in cmd
        assert "--reverse" in cmd
        assert f"origin/{task.branch_name}" in cmd
        assert "^origin/main" in cmd

    def test_git_non_zero_exit_returns_empty(self, tmp_path):
        task = _issue()
        entry = _entry()

        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_result.stderr = "fatal: not a git repository"

        with patch("subprocess.run", return_value=mock_result):
            result = resolve_commits_for_entry(
                task, entry, repo_path=str(tmp_path)
            )

        assert result == []

    def test_git_timeout_returns_empty(self, tmp_path):
        task = _issue()
        entry = _entry()

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=30)):
            result = resolve_commits_for_entry(
                task, entry, repo_path=str(tmp_path)
            )

        assert result == []

    def test_git_file_not_found_returns_empty(self, tmp_path):
        task = _issue()
        entry = _entry()

        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            result = resolve_commits_for_entry(
                task, entry, repo_path=str(tmp_path)
            )

        assert result == []

    def test_git_empty_output_returns_empty(self, tmp_path):
        task = _issue()
        entry = _entry()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "\n\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = resolve_commits_for_entry(
                task, entry, repo_path=str(tmp_path)
            )

        assert result == []

    def test_git_strips_whitespace_from_shas(self, tmp_path):
        task = _issue()
        entry = _entry()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  abc123  \n  def456  \n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = resolve_commits_for_entry(
                task, entry, repo_path=str(tmp_path)
            )

        assert result == ["abc123", "def456"]

    def test_git_uses_custom_default_branch(self, tmp_path):
        task = _issue()
        entry = _entry()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "sha1\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            resolve_commits_for_entry(
                task, entry, repo_path=str(tmp_path), default_branch="develop"
            )

        cmd = mock_run.call_args.args[0]
        assert "^origin/develop" in cmd

    def test_git_skipped_when_repo_path_is_none(self):
        task = _issue()
        entry = _entry()

        with patch("subprocess.run") as mock_run:
            result = resolve_commits_for_entry(task, entry, repo_path=None)

        assert result == []
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# SCM preferred over git fallback
# ---------------------------------------------------------------------------


class TestStrategyPriority:
    def test_scm_wins_over_git_when_both_available(self, tmp_path):
        task = _issue()
        entry = _entry()
        scm = _make_scm(pr_state="merged", commits=["scm_sha"])

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "git_sha\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = resolve_commits_for_entry(
                task, entry, scm=scm, repo="org/repo", repo_path=str(tmp_path)
            )

        # SCM result returned; git subprocess not called
        assert result == ["scm_sha"]
        mock_run.assert_not_called()

    def test_git_used_when_scm_finds_no_pr(self, tmp_path):
        task = _issue()
        entry = _entry()
        scm = _make_scm(pr_state=None)  # no PR found

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "fallback_sha\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = resolve_commits_for_entry(
                task, entry, scm=scm, repo="org/repo", repo_path=str(tmp_path)
            )

        assert result == ["fallback_sha"]

    def test_git_used_when_scm_errors(self, tmp_path):
        task = _issue()
        entry = _entry()
        scm = _make_scm(find_raises=RuntimeError("SCM unavailable"))

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "fallback_sha\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = resolve_commits_for_entry(
                task, entry, scm=scm, repo="org/repo", repo_path=str(tmp_path)
            )

        assert result == ["fallback_sha"]

    def test_all_strategies_fail_returns_empty(self, tmp_path):
        task = _issue()
        entry = _entry()
        scm = _make_scm(pr_state=None)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"

        with patch("subprocess.run", return_value=mock_result):
            result = resolve_commits_for_entry(
                task, entry, scm=scm, repo="org/repo", repo_path=str(tmp_path)
            )

        assert result == []


# ---------------------------------------------------------------------------
# _resolve_via_scm — unit tests
# ---------------------------------------------------------------------------


class TestResolveViaSCM:
    def test_returns_commits_for_merged_pr(self):
        scm = _make_scm(pr_state="merged", commits=["sha1", "sha2"])
        result = _resolve_via_scm(scm, "org/repo", "feature", "TASK-1", "release/1.0")
        assert result == ["sha1", "sha2"]

    def test_returns_empty_for_open_pr(self):
        scm = _make_scm(pr_state="open")
        result = _resolve_via_scm(scm, "org/repo", "feature", "TASK-1", "release/1.0")
        assert result == []

    def test_returns_empty_when_no_pr(self):
        scm = _make_scm(pr_state=None)
        result = _resolve_via_scm(scm, "org/repo", "feature", "TASK-1", "release/1.0")
        assert result == []

    def test_returns_empty_on_find_pr_exception(self):
        scm = _make_scm(find_raises=ValueError("bad"))
        result = _resolve_via_scm(scm, "org/repo", "feature", "TASK-1", "release/1.0")
        assert result == []

    def test_returns_empty_on_get_commits_exception(self):
        scm = _make_scm(pr_state="merged", commits_raises=IOError("timeout"))
        result = _resolve_via_scm(scm, "org/repo", "feature", "TASK-1", "release/1.0")
        assert result == []

    def test_returns_empty_when_merged_pr_has_no_commits(self):
        scm = _make_scm(pr_state="merged", commits=[])
        result = _resolve_via_scm(scm, "org/repo", "feature", "TASK-1", "release/1.0")
        assert result == []

    def test_passes_correct_args(self):
        scm = _make_scm(pr_state="merged", pr_id="99", commits=["x"])
        _resolve_via_scm(scm, "myorg/myrepo", "my-branch", "TASK-5", "release/2.0")
        scm.find_pr_for_branch.assert_called_once_with("myorg/myrepo", "my-branch")
        scm.get_pr_commits.assert_called_once_with("myorg/myrepo", "99")


# ---------------------------------------------------------------------------
# _resolve_via_git — unit tests
# ---------------------------------------------------------------------------


class TestResolveViaGit:
    def _mock_run(self, returncode: int, stdout: str, stderr: str = "") -> MagicMock:
        r = MagicMock()
        r.returncode = returncode
        r.stdout = stdout
        r.stderr = stderr
        return r

    def test_success(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_run(0, "sha1\nsha2\n")):
            result = _resolve_via_git(
                str(tmp_path), "TASK-1", "main", "TASK-1", "release/1.0"
            )
        assert result == ["sha1", "sha2"]

    def test_nonzero_exit(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_run(1, "", "error")):
            result = _resolve_via_git(
                str(tmp_path), "TASK-1", "main", "TASK-1", "release/1.0"
            )
        assert result == []

    def test_timeout(self, tmp_path):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)):
            result = _resolve_via_git(
                str(tmp_path), "TASK-1", "main", "TASK-1", "release/1.0"
            )
        assert result == []

    def test_os_error(self, tmp_path):
        with patch("subprocess.run", side_effect=OSError("permission denied")):
            result = _resolve_via_git(
                str(tmp_path), "TASK-1", "main", "TASK-1", "release/1.0"
            )
        assert result == []

    def test_empty_output(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_run(0, "")):
            result = _resolve_via_git(
                str(tmp_path), "TASK-1", "main", "TASK-1", "release/1.0"
            )
        assert result == []

    def test_command_args(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_run(0, "sha\n")) as mock_run:
            _resolve_via_git(
                str(tmp_path), "TASK-42", "develop", "TASK-42", "release/1.0"
            )
        cmd = mock_run.call_args.args[0]
        assert cmd == [
            "git", "rev-list", "--reverse",
            "origin/TASK-42", "^origin/develop"
        ]
        assert mock_run.call_args.kwargs["cwd"] == str(tmp_path)

    def test_timeout_parameter(self, tmp_path):
        with patch("subprocess.run", return_value=self._mock_run(0, "sha\n")) as mock_run:
            _resolve_via_git(
                str(tmp_path), "branch", "main", "TASK-1", "release/1.0"
            )
        assert mock_run.call_args.kwargs["timeout"] == 30


# ---------------------------------------------------------------------------
# _write_commits_to_metadata
# ---------------------------------------------------------------------------


class TestWriteCommitsToMetadata:
    def test_replaces_matching_entry(self):
        tracker = _make_tracker(
            metadata={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "task_created", "task_id": "TASK-1.1"},
                    ]
                }
            }
        )
        updated = BackportEntry(
            branch="release/1.0",
            status=ReleasePick.TASK_CREATED,
            task_id="TASK-1.1",
            commits=["new_sha"],
        )

        _write_commits_to_metadata(tracker, "TASK-1", updated)

        tracker.set_metadata_field.assert_called_once()
        call_args = tracker.set_metadata_field.call_args
        assert call_args.args[0] == "TASK-1"
        assert call_args.args[1] == "oompah.backports"
        written = parse_backports(call_args.args[2])
        assert len(written) == 1
        assert written[0].branch == "release/1.0"
        assert written[0].commits == ["new_sha"]

    def test_preserves_other_entries(self):
        tracker = _make_tracker(
            metadata={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "task_created"},
                        {"branch": "release/2.0", "status": "waiting"},
                    ]
                }
            }
        )
        updated = BackportEntry(branch="release/1.0", commits=["sha1"])

        _write_commits_to_metadata(tracker, "TASK-1", updated)

        written = parse_backports(
            tracker.set_metadata_field.call_args.args[2]
        )
        branches = [e.branch for e in written]
        assert "release/1.0" in branches
        assert "release/2.0" in branches
        assert len(written) == 2

    def test_appends_when_branch_not_in_list(self):
        """Entry not in current list → appended."""
        tracker = _make_tracker(
            metadata={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "task_created"},
                    ]
                }
            }
        )
        new_entry = BackportEntry(branch="release/3.0", commits=["sha_new"])

        _write_commits_to_metadata(tracker, "TASK-1", new_entry)

        written = parse_backports(
            tracker.set_metadata_field.call_args.args[2]
        )
        branches = [e.branch for e in written]
        assert "release/3.0" in branches
        assert "release/1.0" in branches

    def test_handles_empty_backports(self):
        """Empty backports list → new entry appended."""
        tracker = _make_tracker(
            metadata={"TASK-1": {"oompah.backports": []}}
        )
        entry = BackportEntry(branch="release/1.0", commits=["sha1"])

        _write_commits_to_metadata(tracker, "TASK-1", entry)

        written = parse_backports(
            tracker.set_metadata_field.call_args.args[2]
        )
        assert written[0].branch == "release/1.0"
        assert written[0].commits == ["sha1"]

    def test_handles_missing_backports_key(self):
        """No backports key in metadata → new entry appended."""
        tracker = _make_tracker(metadata={"TASK-1": {}})
        entry = BackportEntry(branch="release/1.0", commits=["sha1"])

        _write_commits_to_metadata(tracker, "TASK-1", entry)

        written = parse_backports(
            tracker.set_metadata_field.call_args.args[2]
        )
        assert written[0].commits == ["sha1"]

    def test_preserves_status_from_live_entry(self):
        """The replacement preserves the live entry's status, not updated_entry's default."""
        tracker = _make_tracker(
            metadata={
                "TASK-1": {
                    "oompah.backports": [
                        {
                            "branch": "release/1.0",
                            "status": "cherry_picking",
                            "task_id": "TASK-1.1",
                            "pr_url": "https://github.com/org/repo/pull/7",
                        }
                    ]
                }
            }
        )
        # updated_entry has default status; live entry has cherry_picking
        updated = BackportEntry(
            branch="release/1.0",
            commits=["sha1", "sha2"],
        )

        _write_commits_to_metadata(tracker, "TASK-1", updated)

        written = parse_backports(
            tracker.set_metadata_field.call_args.args[2]
        )
        assert written[0].status == ReleasePick.CHERRY_PICKING
        assert written[0].task_id == "TASK-1.1"
        assert written[0].pr_url == "https://github.com/org/repo/pull/7"
        assert written[0].commits == ["sha1", "sha2"]

    def test_propagates_get_metadata_exception(self):
        tracker = MagicMock()
        tracker.get_metadata.side_effect = RuntimeError("db down")
        entry = BackportEntry(branch="release/1.0", commits=["sha1"])

        with pytest.raises(RuntimeError, match="db down"):
            _write_commits_to_metadata(tracker, "TASK-1", entry)

    def test_propagates_set_metadata_field_exception(self):
        tracker = _make_tracker(metadata={"TASK-1": {"oompah.backports": []}})
        tracker.set_metadata_field.side_effect = RuntimeError("write failed")
        entry = BackportEntry(branch="release/1.0", commits=["sha1"])

        with pytest.raises(RuntimeError, match="write failed"):
            _write_commits_to_metadata(tracker, "TASK-1", entry)


# ---------------------------------------------------------------------------
# resolve_and_record_commits — integration tests
# ---------------------------------------------------------------------------


class TestResolveAndRecordCommits:
    def test_resolves_and_writes_commits(self):
        task = _issue()
        entry = _entry(commits=[])  # no explicit commits
        scm = _make_scm(pr_state="merged", commits=["sha1", "sha2"])
        tracker = _make_tracker(
            metadata={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "task_created", "task_id": "TASK-1.1"}
                    ]
                }
            }
        )

        result = resolve_and_record_commits(
            tracker, task, entry, scm=scm, repo="org/repo"
        )

        assert result.commits == ["sha1", "sha2"]
        tracker.set_metadata_field.assert_called_once()
        written = parse_backports(
            tracker.set_metadata_field.call_args.args[2]
        )
        assert written[0].commits == ["sha1", "sha2"]

    def test_no_write_when_commits_already_present(self):
        task = _issue()
        entry = _entry(commits=["existing_sha"])
        tracker = _make_tracker(
            metadata={"TASK-1": {"oompah.backports": [{"branch": "release/1.0"}]}}
        )

        result = resolve_and_record_commits(tracker, task, entry)

        assert result.commits == ["existing_sha"]
        tracker.set_metadata_field.assert_not_called()
        tracker.get_metadata.assert_not_called()

    def test_no_write_when_resolution_yields_nothing(self):
        task = _issue()
        entry = _entry(commits=[])
        scm = _make_scm(pr_state=None)  # no PR
        tracker = _make_tracker(metadata={"TASK-1": {}})

        result = resolve_and_record_commits(
            tracker, task, entry, scm=scm, repo="org/repo"
        )

        assert result.commits == []
        tracker.set_metadata_field.assert_not_called()

    def test_returns_updated_entry(self):
        task = _issue()
        entry = _entry(commits=[])
        scm = _make_scm(pr_state="merged", commits=["sha_x"])
        tracker = _make_tracker(
            metadata={
                "TASK-1": {
                    "oompah.backports": [{"branch": "release/1.0", "status": "task_created"}]
                }
            }
        )

        result = resolve_and_record_commits(
            tracker, task, entry, scm=scm, repo="org/repo"
        )

        assert isinstance(result, BackportEntry)
        assert result.branch == entry.branch
        assert result.commits == ["sha_x"]

    def test_returns_original_entry_when_nothing_resolved(self):
        task = _issue()
        entry = _entry(commits=[])
        scm = _make_scm(pr_state=None)
        tracker = _make_tracker(metadata={"TASK-1": {}})

        result = resolve_and_record_commits(
            tracker, task, entry, scm=scm, repo="org/repo"
        )

        assert result is entry  # unchanged original

    def test_git_fallback_writes_commits(self, tmp_path):
        task = _issue()
        entry = _entry(commits=[])
        tracker = _make_tracker(
            metadata={
                "TASK-1": {
                    "oompah.backports": [{"branch": "release/1.0", "status": "task_created"}]
                }
            }
        )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "git_sha_a\ngit_sha_b\n"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            result = resolve_and_record_commits(
                tracker, task, entry, repo_path=str(tmp_path)
            )

        assert result.commits == ["git_sha_a", "git_sha_b"]
        tracker.set_metadata_field.assert_called_once()

    def test_metadata_write_exception_propagates(self):
        task = _issue()
        entry = _entry(commits=[])
        scm = _make_scm(pr_state="merged", commits=["sha1"])
        tracker = _make_tracker(
            metadata={
                "TASK-1": {
                    "oompah.backports": [{"branch": "release/1.0", "status": "task_created"}]
                }
            }
        )
        tracker.set_metadata_field.side_effect = RuntimeError("write failed")

        with pytest.raises(RuntimeError, match="write failed"):
            resolve_and_record_commits(tracker, task, entry, scm=scm, repo="org/repo")

    def test_updates_correct_branch_in_multientry_list(self):
        task = _issue()
        entry = _entry(branch="release/2.0", commits=[])
        scm = _make_scm(pr_state="merged", commits=["sha_for_2"])
        tracker = _make_tracker(
            metadata={
                "TASK-1": {
                    "oompah.backports": [
                        {"branch": "release/1.0", "status": "merged", "commits": ["old_sha"]},
                        {"branch": "release/2.0", "status": "task_created"},
                    ]
                }
            }
        )

        resolve_and_record_commits(tracker, task, entry, scm=scm, repo="org/repo")

        written = parse_backports(
            tracker.set_metadata_field.call_args.args[2]
        )
        by_branch = {e.branch: e for e in written}
        assert by_branch["release/2.0"].commits == ["sha_for_2"]
        # Other entry should still be there with its own commits
        assert by_branch["release/1.0"].branch == "release/1.0"

    def test_idempotent_second_call(self):
        """Calling resolve_and_record_commits twice with resolved entry is a no-op."""
        task = _issue()
        entry = _entry(commits=["already_resolved"])
        tracker = _make_tracker(metadata={"TASK-1": {}})

        result = resolve_and_record_commits(tracker, task, entry)

        assert result.commits == ["already_resolved"]
        tracker.set_metadata_field.assert_not_called()
        tracker.get_metadata.assert_not_called()
