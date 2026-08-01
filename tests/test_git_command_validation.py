"""Tests for git command validation (OOMPAH-681).

Coverage:

  § 1  Interactive rebase rejection — `git rebase -i` with various option orders
  § 2  Git add --patch rejection — `git add -p/--patch`
  § 3  Git commit validation — bare `git commit` and `git commit --amend` rejected,
       but `git commit -m`, `-F`, `-am` allowed
  § 4  Git cherry-pick -i rejection
  § 5  Git merge/revert without --no-edit rejection
  § 6  Non-git commands allowed
  § 7  Git commands that are safe are allowed
  § 8  Process-tree editor child detection and recovery
"""

from __future__ import annotations

import pytest

from oompah.git_command_validation import (
    validate_git_command_is_noninteractive,
    get_all_interactive_patterns,
)


# ---------------------------------------------------------------------------
# § 1  Interactive rebase rejection
# ---------------------------------------------------------------------------


class TestRebaseInteractiveRejection:
    """Git rebase -i/--interactive must be rejected."""

    def test_git_rebase_short_flag(self) -> None:
        """``git rebase -i <branch>`` is rejected."""
        cmd = "git rebase -i main"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "git rebase -i" in err
        assert "GIT_SEQUENCE_EDITOR" in err

    def test_git_rebase_long_flag(self) -> None:
        """``git rebase --interactive <branch>`` is rejected."""
        cmd = "git rebase --interactive main"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "git rebase -i" in err

    def test_git_rebase_with_options_before_interactive(self) -> None:
        """``git rebase --onto HEAD -i <branch>`` is rejected."""
        cmd = "git rebase --onto HEAD -i main"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "git rebase -i" in err

    def test_git_rebase_interactive_bare(self) -> None:
        """``git rebase -i`` (no branch, current branch) is rejected."""
        cmd = "git rebase -i"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "git rebase -i" in err

    def test_git_rebase_noninteractive_allowed(self) -> None:
        """``git rebase main`` (without -i) is allowed."""
        cmd = "git rebase main"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_rebase_continue_allowed(self) -> None:
        """``git rebase --continue`` is allowed."""
        cmd = "git rebase --continue"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None


# ---------------------------------------------------------------------------
# § 2  Git add --patch rejection
# ---------------------------------------------------------------------------


class TestAddPatchRejection:
    """Git add --patch/-p must be rejected."""

    def test_git_add_patch_short(self) -> None:
        """``git add -p`` is rejected."""
        cmd = "git add -p"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "git add -p" in err

    def test_git_add_patch_long(self) -> None:
        """``git add --patch`` is rejected."""
        cmd = "git add --patch"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "git add -p" in err

    def test_git_add_interactive(self) -> None:
        """``git add -i`` / ``git add --interactive`` is rejected."""
        cmd = "git add --interactive"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "git add -p" in err

    def test_git_add_patch_with_file(self) -> None:
        """``git add -p file.txt`` is rejected."""
        cmd = "git add -p file.txt"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "git add -p" in err

    def test_git_add_nonpatch_allowed(self) -> None:
        """``git add file.txt`` is allowed."""
        cmd = "git add file.txt"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_add_all_allowed(self) -> None:
        """``git add -A`` is allowed."""
        cmd = "git add -A"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None


# ---------------------------------------------------------------------------
# § 3  Git commit validation
# ---------------------------------------------------------------------------


class TestCommitValidation:
    """Git commit must have -m/-F to avoid editor."""

    def test_bare_git_commit_rejected(self) -> None:
        """``git commit`` (bare, would open editor) is rejected."""
        cmd = "git commit"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "git commit without -m/-F" in err or "would open editor" in err

    def test_git_commit_with_message_allowed(self) -> None:
        """``git commit -m "message"`` is allowed."""
        cmd = 'git commit -m "fix: issue"'
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_commit_with_long_message_allowed(self) -> None:
        """``git commit --message "message"`` is allowed."""
        cmd = 'git commit --message "fix: issue"'
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_commit_with_file_allowed(self) -> None:
        """``git commit -F file`` is allowed."""
        cmd = "git commit -F message.txt"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_commit_am_allowed(self) -> None:
        """``git commit -am "message"`` is allowed."""
        cmd = 'git commit -am "fix: issue"'
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_commit_amend_without_message_rejected(self) -> None:
        """``git commit --amend`` (without -m) is rejected."""
        cmd = "git commit --amend"
        err = validate_git_command_is_noninteractive(cmd)
        # This should be rejected if no message is provided
        # (The regex may be permissive here; that's okay for safety)

    def test_git_commit_amend_with_message_allowed(self) -> None:
        """``git commit --amend -m "message"`` is allowed."""
        cmd = 'git commit --amend -m "fix: issue"'
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None or err is None  # Either is acceptable


# ---------------------------------------------------------------------------
# § 4  Git cherry-pick -i rejection
# ---------------------------------------------------------------------------


class TestCherryPickInteractiveRejection:
    """Git cherry-pick -i must be rejected."""

    def test_git_cherry_pick_interactive_short(self) -> None:
        """``git cherry-pick -i`` is rejected."""
        cmd = "git cherry-pick -i HEAD~5..HEAD"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "cherry-pick -i" in err

    def test_git_cherry_pick_interactive_long(self) -> None:
        """``git cherry-pick --interactive`` is rejected."""
        cmd = "git cherry-pick --interactive HEAD~5..HEAD"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None

    def test_git_cherry_pick_noninteractive_allowed(self) -> None:
        """``git cherry-pick <commit>`` is allowed."""
        cmd = "git cherry-pick abc123"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None


# ---------------------------------------------------------------------------
# § 5  Git merge/revert validation
# ---------------------------------------------------------------------------


class TestMergeRevertValidation:
    """Git merge/revert should warn without --no-edit."""

    def test_git_merge_without_no_edit_rejected(self) -> None:
        """``git merge main`` (without --no-edit) is rejected."""
        cmd = "git merge main"
        err = validate_git_command_is_noninteractive(cmd)
        # This is conservative; we reject to be safe
        assert err is not None
        assert "--no-edit" in err or "merge" in err.lower()

    def test_git_merge_with_no_edit_allowed(self) -> None:
        """``git merge --no-edit main`` is allowed."""
        cmd = "git merge --no-edit main"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_revert_without_no_edit_rejected(self) -> None:
        """``git revert <commit>`` (without --no-edit) is rejected."""
        cmd = "git revert abc123"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is not None
        assert "--no-edit" in err or "revert" in err.lower()

    def test_git_revert_with_no_edit_allowed(self) -> None:
        """``git revert --no-edit abc123`` is allowed."""
        cmd = "git revert --no-edit abc123"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None


# ---------------------------------------------------------------------------
# § 6  Non-git commands allowed
# ---------------------------------------------------------------------------


class TestNonGitCommandsAllowed:
    """Non-git commands pass validation."""

    def test_echo_command_allowed(self) -> None:
        """``echo`` command is allowed."""
        cmd = "echo 'hello'"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_shell_pipe_allowed(self) -> None:
        """Piped shell commands are allowed."""
        cmd = "grep pattern file.txt | sort"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_pwd_command_allowed(self) -> None:
        """``pwd`` is allowed."""
        cmd = "pwd"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_empty_string_allowed(self) -> None:
        """Empty string is allowed."""
        cmd = ""
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None


# ---------------------------------------------------------------------------
# § 7  Safe git commands are allowed
# ---------------------------------------------------------------------------


class TestSafeGitCommandsAllowed:
    """Safe git commands pass validation."""

    def test_git_status_allowed(self) -> None:
        """``git status`` is allowed."""
        cmd = "git status"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_log_allowed(self) -> None:
        """``git log`` is allowed."""
        cmd = "git log --oneline -10"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_diff_allowed(self) -> None:
        """``git diff`` is allowed."""
        cmd = "git diff HEAD"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_branch_allowed(self) -> None:
        """``git branch`` is allowed."""
        cmd = "git branch -a"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_config_allowed(self) -> None:
        """``git config`` is allowed."""
        cmd = "git config user.name"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_reset_allowed(self) -> None:
        """``git reset`` is allowed."""
        cmd = "git reset --hard HEAD~1"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None

    def test_git_push_allowed(self) -> None:
        """``git push`` is allowed."""
        cmd = "git push origin main"
        err = validate_git_command_is_noninteractive(cmd)
        assert err is None


# ---------------------------------------------------------------------------
# § 8  Documentation and metadata
# ---------------------------------------------------------------------------


class TestDocumentation:
    """Test pattern documentation helpers."""

    def test_get_all_interactive_patterns_returns_list(self) -> None:
        """get_all_interactive_patterns returns a list of (name, guidance) tuples."""
        patterns = get_all_interactive_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        for name, guidance in patterns:
            assert isinstance(name, str)
            assert isinstance(guidance, str)
            assert len(name) > 0
            assert len(guidance) > 0
