"""Git command validation to prevent interactive modes that block worker slots.

OOMPAH-681: Reject interactive Git commands before they can deadlock worker slots.

Scope: Enforce noninteractive Git at the worker shell/MCP command boundary.
Rejects commands whose semantics require a TTY/editor, including:
  - git rebase -i / --interactive
  - git add -p / --patch
  - git commit (without -m/-F/-am when editing is required)
  - git cherry-pick -i / --interactive
  - git merge (when conflicts require manual resolution)
  - And other known interactive Git modes

For each rejected pattern, provides an actionable replacement such as:
  - Scripted GIT_SEQUENCE_EDITOR for rebase automation
  - git add (non-patch) for staged changes
  - git commit -m "<message>" to skip the editor
  - git merge --no-edit to suppress editor on merge commits
"""

from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Interactive git command patterns
# ---------------------------------------------------------------------------

# Patterns that indicate an interactive git command requiring a TTY/editor.
# These match common invocation forms, tolerating shell quoting and options.
#
# The regex patterns are designed to be:
#   - Safe (no ReDoS risk)
#   - Permissive (match common variants and option orders)
#   - Focused (target only truly interactive modes, not all commits)
#   - Anchored (match the command invocation, not just substrings)
#
# NOTE: Order matters! More-specific patterns must come before more-general ones
# to avoid false positives. For example, "git add --interactive" must be checked
# before "git rebase -i" to avoid the generic -i matching the rebase pattern.

_INTERACTIVE_GIT_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    # --------- git add --patch/--interactive (must come before generic -i) ---------
    (
        "git add -p/--patch/--interactive",
        re.compile(
            r'\bgit\s+add\s+(?:.*\s+)?(?:-p|--patch|--interactive)(?:\s|$)',
            re.IGNORECASE,
        ),
        "Use git add (without -p) to stage files, or use git add -u/--all for bulk staging. "
        "If you need selective staging, use scripted workflows or git diff to identify changes.",
    ),
    # --------- git cherry-pick -i/--interactive (must come before generic -i) ---------
    (
        "git cherry-pick -i/--interactive",
        re.compile(
            r'\bgit\s+cherry-pick\s+(?:.*\s+)?(?:-i|--interactive)(?:\s|$)',
            re.IGNORECASE,
        ),
        "Interactive cherry-pick is not supported. Use non-interactive cherry-pick: "
        "git cherry-pick <commit>",
    ),
    # --------- git rebase (interactive mode) ---------
    (
        "git rebase -i/--interactive",
        re.compile(
            r'\bgit\s+rebase\s+(?:.*\s+)?(?:-i|--interactive)(?:\s|$)',
            re.IGNORECASE,
        ),
        "Use GIT_SEQUENCE_EDITOR to script rebase automation: "
        "GIT_SEQUENCE_EDITOR=<script> git rebase --continue",
    ),
    # --------- git commit (without -m/-F/--am/--amend) ---------
    # Matches: git commit, git commit --amend (without message), etc.
    # But allows: git commit -m "msg", git commit -F file, git commit -am "msg", etc.
    (
        "git commit without -m/-F/--am (would open editor)",
        re.compile(
            r'\bgit\s+commit\b'
            r'(?!.*(?:\s-[mF]|\s--message|\s--file|\s-a[m]|\s--all))',
            re.IGNORECASE,
        ),
        "Use git commit -m \"<message>\" to set the commit message without an editor, "
        "or git commit -F <file> to read the message from a file.",
    ),
    # --------- git merge (without --no-edit) ---------
    # Note: This is complex because merge may need editor only on conflict or for merge commits.
    # We conservatively reject bare `git merge` without --no-edit when it might open an editor.
    (
        "git merge (without --no-edit)",
        re.compile(
            r'\bgit\s+merge\s+(?!.*--no-edit).*$',
            re.IGNORECASE,
        ),
        "Use git merge --no-edit to suppress the editor on merge commits. "
        "Alternatively, handle conflicts non-interactively and use git merge --continue.",
    ),
    # --------- git revert (without --no-edit) ---------
    (
        "git revert (without --no-edit)",
        re.compile(
            r'\bgit\s+revert\s+(?!.*--no-edit).*$',
            re.IGNORECASE,
        ),
        "Use git revert --no-edit to suppress the editor on revert commits.",
    ),
]

# ---------------------------------------------------------------------------
# Validation function
# ---------------------------------------------------------------------------


def validate_git_command_is_noninteractive(
    command: str,
) -> Optional[str]:
    """Validate that a git command does not require an interactive editor or TTY.

    Returns an error message (actionable guidance) if the command is interactive,
    or None if the command is safe to execute noninteractively.

    Parameters
    ----------
    command : str
        The shell command string to validate (e.g., from `mcp__oompah__run_command`).

    Returns
    -------
    str or None
        An error message with guidance if the command is interactive, or None
        if it is safe to run noninteractively.

    Examples
    --------
    >>> validate_git_command_is_noninteractive("git rebase -i main")
    "git rebase -i/--interactive: Use GIT_SEQUENCE_EDITOR to script rebase automation..."

    >>> validate_git_command_is_noninteractive("git commit -m 'msg'")
    None

    >>> validate_git_command_is_noninteractive("echo 'not git'")
    None
    """
    if not command or not isinstance(command, str):
        return None

    # Quick pre-check: only validate git commands
    if "git" not in command:
        return None

    # Try each pattern; first match wins
    for pattern_name, pattern, guidance in _INTERACTIVE_GIT_PATTERNS:
        if pattern.search(command):
            return f"{pattern_name}: {guidance}"

    return None


# ---------------------------------------------------------------------------
# Exported helpers for testing and tooling
# ---------------------------------------------------------------------------


def get_all_interactive_patterns() -> list[tuple[str, str]]:
    """Return a list of (pattern_name, guidance) for documentation/testing."""
    return [(name, guidance) for name, _, guidance in _INTERACTIVE_GIT_PATTERNS]
