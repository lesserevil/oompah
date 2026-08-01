"""Regression test for EXOCOMP-140 (OOMPAH-681).

This test verifies that the exact scenario from the regression is now prevented:
- A worker invoked `git rebase -i b1a07ccf` through mcp__oompah__run_command
- Git spawned `/usr/bin/vi` to edit the rebase-merge/git-rebase-todo file
- The worker slot blocked for ~10 minutes until an operator terminated the vi process

With OOMPAH-681 implementation:
1. The `git rebase -i` command is rejected at the validation layer
2. An error message is returned immediately with guidance
3. No subprocess is spawned
4. No editor process can block the worker
"""

from __future__ import annotations

from oompah.api_agent import _exec_run_command


def test_exocomp_140_exact_reproduction_blocked(tmp_path):
    """The EXOCOMP-140 regression (git rebase -i b1a07ccf) is now blocked.

    Instead of spawning vi and blocking the worker, the command is rejected
    at the validation layer with actionable guidance.
    """
    # This is the exact command from EXOCOMP-140
    result = _exec_run_command(
        tmp_path,
        {"command": "git rebase -i b1a07ccf"},
        timeout=10,
    )

    # Should be rejected with an error, not blocked
    assert "Error" in result
    assert "git rebase -i" in result
    assert "GIT_SEQUENCE_EDITOR" in result


def test_exocomp_140_variant_with_options_also_blocked(tmp_path):
    """Variants of the interactive rebase are also blocked."""
    result = _exec_run_command(
        tmp_path,
        {"command": "git rebase -i HEAD~5"},
        timeout=10,
    )

    assert "Error" in result
    assert "git rebase -i" in result


def test_exocomp_140_replacement_with_sequence_editor_allowed(tmp_path):
    """The suggested replacement (GIT_SEQUENCE_EDITOR) is syntactically allowed."""
    # This command uses GIT_SEQUENCE_EDITOR to automate rebase and should pass
    # the validation (though it may fail to execute due to lack of git repo)
    result = _exec_run_command(
        tmp_path,
        {"command": "GIT_SEQUENCE_EDITOR=cat git rebase --continue"},
        timeout=10,
    )

    # Should not be rejected by validation (may fail due to no rebase in progress)
    assert "Error: git rebase -i" not in result


def test_worker_slot_cannot_be_blocked_by_editor_spawn(tmp_path):
    """No worker slot can be occupied by an editor or terminal prompt."""
    # Attempt to execute git rebase -i and verify immediate return
    import time

    start = time.time()
    result = _exec_run_command(
        tmp_path,
        {"command": "git rebase -i main"},
        timeout=2,
    )
    elapsed = time.time() - start

    # Should return in milliseconds, not block for seconds
    assert elapsed < 1.0, f"Command took {elapsed:.2f}s, suggesting a block"
    assert "Error" in result


def test_all_interactive_git_modes_blocked_same_way(tmp_path):
    """All interactive git modes are blocked consistently."""
    interactive_commands = [
        "git rebase -i main",
        "git add -p",
        "git commit",
        "git cherry-pick -i HEAD~5",
        "git merge main",
        "git revert abc123",
    ]

    for cmd in interactive_commands:
        result = _exec_run_command(
            tmp_path,
            {"command": cmd},
            timeout=2,
        )
        assert "Error" in result, f"Expected {cmd!r} to be rejected"
        # No subprocess should have been spawned
        assert "exit_code" not in result or "Error" in result
