"""Epic branch staleness detection.

Compares an epic branch's merge-base with its target branch (usually
``main``) to determine whether the epic has fallen behind. Staleness is
detected by two independent triggers:

1. **Commit threshold** — the target branch is ahead of the merge-base
   by at least ``threshold_commits`` commits.
2. **File overlap** — any commit between the merge-base and the target
   branch HEAD touches a file that the epic branch also modified
   (relative to its own merge-base).

Both triggers are evaluated; the branch is considered stale if *either*
fires. The commit threshold can be set to 0 to disable that trigger
while still checking file overlap.

Design
------

* **Pure functions** — the module contains no orchestrator state.
  Callers pass in the project path and branch names; the module
  returns a ``StalenessResult``.
* **Fail-open** — subprocess failures (git not found, timeout, etc.)
  return a result with ``stale=False`` and an ``error`` message.
* **Fast** — uses ``git rev-list --count`` for commit counting and
  ``git diff --name-only`` for file sets; no expensive operations.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StalenessResult:
    """Result of a staleness check for one epic branch.

    Attributes:
        stale: ``True`` if the epic branch is considered stale.
        commits_behind: Number of commits on the target branch since the
            merge-base. ``0`` means the epic is up to date.
        shared_files: Files modified on *both* the target branch (since
            merge-base) and the epic branch (since merge-base). Empty
            means no file overlap.
        threshold: The configured commit threshold that was used.
        error: Error message if the check could not complete. Empty
            string on success.
    """

    stale: bool
    commits_behind: int
    shared_files: tuple[str, ...]
    threshold: int
    error: str = ""


def check_epic_branch_staleness(
    repo_path: str,
    epic_branch: str,
    target_branch: str,
    threshold_commits: int = 5,
    *,
    timeout: int = 30,
) -> StalenessResult:
    """Check whether ``epic_branch`` is stale relative to ``target_branch``.

    Args:
        repo_path: Path to the git repository (the project's main clone).
        epic_branch: The local or remote epic branch name
            (e.g. ``epic-trickle-abc123``).
        target_branch: The target branch name (e.g. ``main``).
        threshold_commits: Number of commits behind to trigger staleness.
            Set to 0 to disable the commit-count trigger.
        timeout: Subprocess timeout in seconds.

    Returns:
        A ``StalenessResult`` describing the staleness status.
    """

    def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # 1. Compute merge-base between epic branch and target branch.
    # ------------------------------------------------------------------
    try:
        # Ensure we have the latest refs
        _git(["fetch", "origin"])
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # best-effort fetch — continue with whatever refs exist
        pass

    try:
        r = _git(["merge-base", epic_branch, target_branch])
        if r.returncode != 0:
            stderr = (r.stderr or "").strip()[:300]
            return StalenessResult(
                stale=False, commits_behind=0, shared_files=(),
                threshold=threshold_commits,
                error=f"merge-base failed: {stderr}",
            )
        merge_base = r.stdout.strip()
    except subprocess.TimeoutExpired:
        return StalenessResult(
            stale=False, commits_behind=0, shared_files=(),
            threshold=threshold_commits,
            error="merge-base timed out",
        )

    # ------------------------------------------------------------------
    # 2. Count commits on target branch since merge-base.
    # ------------------------------------------------------------------
    try:
        r = _git(["rev-list", "--count", f"{merge_base}..{target_branch}"])
        if r.returncode != 0:
            stderr = (r.stderr or "").strip()[:300]
            return StalenessResult(
                stale=False, commits_behind=0, shared_files=(),
                threshold=threshold_commits,
                error=f"rev-list failed: {stderr}",
            )
        commits_behind = int(r.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError):
        return StalenessResult(
            stale=False, commits_behind=0, shared_files=(),
            threshold=threshold_commits,
            error="rev-list --count failed",
        )

    # ------------------------------------------------------------------
    # 3. Fast-path: if not behind enough commits and threshold > 0,
    #    skip file overlap check.
    # ------------------------------------------------------------------
    if threshold_commits > 0 and commits_behind < threshold_commits:
        return StalenessResult(
            stale=False, commits_behind=commits_behind,
            shared_files=(), threshold=threshold_commits,
        )

    # ------------------------------------------------------------------
    # 4. File overlap check.
    # ------------------------------------------------------------------
    try:
        # Files changed on target branch since merge-base
        r_target = _git(
            ["diff", "--name-only", merge_base, target_branch]
        )
        target_files: set[str] = set()
        if r_target.returncode == 0:
            target_files = {
                f.strip()
                for f in r_target.stdout.splitlines()
                if f.strip()
            }

        # Files changed on epic branch since merge-base
        r_epic = _git(
            ["diff", "--name-only", merge_base, epic_branch]
        )
        epic_files: set[str] = set()
        if r_epic.returncode == 0:
            epic_files = {
                f.strip()
                for f in r_epic.stdout.splitlines()
                if f.strip()
            }

        shared = target_files & epic_files
    except subprocess.TimeoutExpired:
        shared = set()
        # If we timed out on file diff but commits_behind >= threshold,
        # still report stale based on commit count alone
        if threshold_commits > 0 and commits_behind >= threshold_commits:
            return StalenessResult(
                stale=True, commits_behind=commits_behind,
                shared_files=(), threshold=threshold_commits,
                error="file diff timed out (staleness determined by commit count)",
            )
        return StalenessResult(
            stale=False, commits_behind=commits_behind,
            shared_files=(), threshold=threshold_commits,
            error="file diff timed out",
        )

    # ------------------------------------------------------------------
    # 5. Determine staleness.
    # ------------------------------------------------------------------
    behind_by_commits = (
        threshold_commits <= 0 or commits_behind >= threshold_commits
    )
    has_file_overlap = len(shared) > 0
    stale = behind_by_commits or has_file_overlap

    return StalenessResult(
        stale=stale,
        commits_behind=commits_behind,
        shared_files=tuple(sorted(shared)),
        threshold=threshold_commits,
    )
