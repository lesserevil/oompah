"""Unpushed gate: block agent escalation when no commits were pushed.

Motivating issue: oompah-zlz_2-kc2k.1

When an agent session ends (worker exits) and the bead is still open
(not closed), check whether there are any commits on the issue's branch
that have been pushed to origin. If no commits were pushed, refuse to
let the agent escalate — log the situation, post a diagnostic comment,
and stash the agent instead of escalating.

Pattern: close_gate.py implements a similar gate that runs in
_on_worker_exit on the 'completed without closing' path. This gate
checks for unpushed commits instead of unmerged PRs.

Skip rules (fail-open without checking):
* Issue is an epic.
* Branch is 0 commits ahead of the base branch (nothing to land).
* Git command fails or times out (fail-open, log WARNING).

Refusal output:
* Do NOT mark completed; the bead remains in_progress/open.
* Post a diagnostic comment (author=oompah) with the required
  commit + push + close steps.
* Reopen the bead so the existing dispatch/retry cycle picks it up.
* Log a structured telemetry event ``completion_rejected_unpushed_work``.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Timeout for git operations inside the gate check.
_GIT_TIMEOUT_S = 15.0


@dataclass
class UnpushedGateResult:
    """Outcome of the unpushed gate check."""

    # True = no gate triggered, proceed normally
    allowed: bool
    # Why the gate was skipped (empty when the gate ran and allowed)
    skip_reason: str = ""
    # True when the worktree has uncommitted changes
    has_uncommitted: bool = False
    # Number of unpushed commits on the branch
    commits_ahead: int = 0
    # SHA + subject lines for the refusal comment (max 20)
    commit_lines: list[str] = field(default_factory=list)
    # Internal error message (gate failed open)
    error: str = ""


def _branch_for_issue(issue: Any) -> str:
    """Return the best branch name known for an issue."""
    for value in (
        getattr(issue, "work_branch", None),
        getattr(issue, "branch_name", None),
        getattr(issue, "identifier", None),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _check_unpushed(
    repo_path: str,
    branch: str,
    base_branch: str,
) -> tuple[bool, int, list[str], str]:
    """Check for unpushed commits and uncommitted work.

    Returns (has_uncommitted, commits_ahead, commit_lines, error).

    ``commit_lines`` is a list of "<sha> <subject>" strings (max 20).
    ``error`` is non-empty when commands failed but we fail-open.
    """
    has_uncommitted = False
    commits_ahead = 0
    commit_lines: list[str] = []
    error = ""

    if not branch:
        return False, 0, [], "no_branch"

    # --- 1. Check for uncommitted changes in the worktree ---
    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if status_result.returncode == 0:
            for line in status_result.stdout.splitlines():
                if line.strip():
                    has_uncommitted = True
                    break
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as exc:
        logger.debug("unpushed_gate: git status failed: %s", exc)

    # --- 2. Check for unpushed commits on the branch ---
    # Fetch to get the latest remote state (quick, never fails)
    try:
        subprocess.run(
            ["git", "fetch", "origin", "--quiet"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass  # Non-fatal — we fall back to local tracking ref

    # Count commits ahead of origin/<branch>.
    remote_ref = f"origin/{branch}"

    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{remote_ref}..{branch}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as exc:
        error = f"git rev-list --count failed: {exc}"
        return has_uncommitted, 0, [], error

    if result.returncode != 0:
        # Branch may not exist on remote yet — no commits to push
        commits_ahead = 0
    else:
        stdout = result.stdout.strip()
        if not stdout:
            commits_ahead = 0
        else:
            try:
                commits_ahead = int(stdout)
            except ValueError:
                error = f"git rev-list --count unexpected output: {stdout!r}"
                return has_uncommitted, 0, [], error

    if commits_ahead == 0 and not has_uncommitted:
        return False, 0, [], ""

    # --- 3. Collect commit lines for the diagnostic comment ---
    if commits_ahead > 0:
        try:
            log_result = subprocess.run(
                ["git", "log", "--oneline", "-20", f"{remote_ref}..{branch}"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if log_result.returncode == 0:
                commit_lines = [
                    l.strip()
                    for l in log_result.stdout.splitlines()
                    if l.strip()
                ]
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            pass

    return has_uncommitted, commits_ahead, commit_lines, ""


def check_unpushed_gate(
    issue: Any,
    *,
    repo_path: str,
    base_branch: str,
    entry_profile: str = "",
    entry_focus: str = "",
    entry_attempt: int = 0,
) -> UnpushedGateResult:
    """Run the unpushed gate check.

    Args:
        issue: The Issue being checked.
        repo_path: Filesystem path to the project's git clone.
        base_branch: The base branch name (e.g. "main").
        entry_profile: Agent profile name (for telemetry).
        entry_focus: Focus name (for telemetry).
        entry_attempt: Retry attempt count (for telemetry).

    Returns:
        An :class:`UnpushedGateResult`. When ``allowed=True`` the
        completion may proceed. When ``allowed=False`` the caller
        should post a refusal comment, revert to in_progress, and
        log telemetry.
    """
    # ------------------------------------------------------------------
    # Skip: epic issues don't have their own branch/commit cadence
    # ------------------------------------------------------------------
    if (issue.issue_type or "").strip().lower() == "epic":
        return UnpushedGateResult(allowed=True, skip_reason="epic")

    branch = _branch_for_issue(issue)
    if not branch:
        logger.debug(
            "unpushed_gate: no branch resolved for %s — skipping",
            issue.identifier,
        )
        return UnpushedGateResult(allowed=True, skip_reason="no_branch")

    if not repo_path:
        logger.debug(
            "unpushed_gate: no repo_path for %s — skipping",
            issue.identifier,
        )
        return UnpushedGateResult(allowed=True, skip_reason="no_repo_path")

    # ------------------------------------------------------------------
    # Git check
    # ------------------------------------------------------------------
    has_uncommitted, commits_ahead, commit_lines, git_error = _check_unpushed(
        repo_path, branch, base_branch,
    )

    if git_error:
        logger.warning(
            "unpushed_gate: git check failed for %s branch=%s: %s — failing open",
            issue.identifier,
            branch,
            git_error,
        )
        return UnpushedGateResult(
            allowed=True,
            skip_reason="git_error",
            error=git_error,
        )

    if commits_ahead == 0 and not has_uncommitted:
        return UnpushedGateResult(allowed=True, skip_reason="no_unpushed_work")

    # ------------------------------------------------------------------
    # Refusal: uncommitted changes or unpushed commits found
    # ------------------------------------------------------------------
    telemetry = {
        "event": "completion_rejected_unpushed_work",
        "issue_id": issue.id or "",
        "issue_identifier": issue.identifier or "",
        "branch": branch,
        "commits_ahead": commits_ahead,
        "has_uncommitted": has_uncommitted,
        "agent_profile": entry_profile,
        "focus": entry_focus,
        "attempt": entry_attempt,
    }
    logger.info("unpushed_gate_telemetry: %s", json.dumps(telemetry, default=str))

    return UnpushedGateResult(
        allowed=False,
        has_uncommitted=has_uncommitted,
        commits_ahead=commits_ahead,
        commit_lines=commit_lines,
    )


def build_unpushed_refusal_comment(
    issue: Any,
    result: UnpushedGateResult,
    base_branch: str,
) -> str:
    """Build the diagnostic comment to post when unpushed work is found."""
    branch = _branch_for_issue(issue)

    lines: list[str] = [
        "Completion refused by orchestrator: unpushed work detected on "
        f"branch `{branch}` while bead is in a terminal state.",
        "",
        "Diagnostic:",
    ]

    if result.has_uncommitted:
        lines.append(
            "  Worktree has uncommitted changes — file(s) created but never committed."
        )

    if result.commits_ahead > 0:
        n = result.commits_ahead
        commit_noun = "commit" if n == 1 else "commits"
        lines.append(f"  Unpushed commits: {n} {commit_noun}")
        for cl in result.commit_lines[:10]:
            lines.append(f"    {cl}")
        if n > len(result.commit_lines):
            lines.append(f"    ... and {n - len(result.commit_lines)} more")

    lines.extend([
        "",
        "Required: commit the work, push to origin, then close the bead.",
        "",
        "Steps to resolve:",
        f"  git checkout {branch}",
        "  git add -A",
        f'  git commit -m "Descriptive commit message"',
        f"  git push origin {branch}",
        "",
        "Bead re-opened. Re-dispatch will push a fresh agent to complete the landing.",
    ])

    return "\n".join(lines)
