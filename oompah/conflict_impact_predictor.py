"""Conflict-impact predictor.

For a given open PR, simulate its merge into main and run git merge-tree
against every other open PR to predict downstream conflicts.  Cache results
with SHA-based keys so pushes/rebases naturally invalidate.

Uses git merge-tree (git 2.53+) which performs a recursive merge
without touching the working tree or index.  Exit code 0 = clean,
1 = conflicts, any other code = error.

Typical usage:

    predictor = ConflictImpactPredictor()

    # Given a repo path and a list of open PR branches:
    result = predictor.predict(
        repo_path="/path/to/repo",
        target_branch="feature/foo",
        other_branches=["feature/bar", "feature/baz"],
    )

    print(f"Conflict score: {result.score} / {len(result.predictions)}")
    for p in result.conflicting_predictions:
        print(f"  Conflicts with {p.branch}: {p.conflicting_files}")
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from oompah.cache import TTLCache

logger = logging.getLogger(__name__)

# Default cache TTL: 30 minutes.
_DEFAULT_CACHE_TTL_MS = 30 * 60 * 1000

# Timeout for each git merge-tree invocation (seconds).
_MERGE_TREE_TIMEOUT_S = 30

# Regex to extract conflicting file paths from merge-tree output.
# Matches lines like: "CONFLICT (content): Merge conflict in file.txt"
_CONFLICT_FILE_RE = re.compile(r"CONFLICT \(.+?\): Merge conflict in (.+)$")


@dataclass
class ConflictPrediction:
    """Result of a single merge-tree check between two branches.

    Attributes:
        branch: The other branch that was checked.
        head_sha: The HEAD SHA of the other branch (for display).
        has_conflict: True if merging the target into this branch would
            produce conflicts.
        conflicting_files: List of file paths with conflicts (empty if
            clean merge).
        error: Non-empty string if the merge-tree command failed.
    """

    branch: str
    head_sha: str = ""
    has_conflict: bool = False
    conflicting_files: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class ConflictImpactResult:
    """Aggregate result of conflict-impact prediction for one PR.

    Attributes:
        target_branch: The PR branch being analyzed.
        score: Number of other open PRs that would conflict.
        total_checked: Total number of other PRs checked.
        predictions: Per-branch predictions.
        conflicting_predictions: Subset of predictions where
            has_conflict is True.
        error: Non-empty if the overall prediction failed.
    """

    target_branch: str
    score: int = 0
    total_checked: int = 0
    predictions: list[ConflictPrediction] = field(default_factory=list)
    conflicting_predictions: list[ConflictPrediction] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_branch": self.target_branch,
            "score": self.score,
            "total_checked": self.total_checked,
            "predictions": [
                {
                    "branch": p.branch,
                    "head_sha": p.head_sha,
                    "has_conflict": p.has_conflict,
                    "conflicting_files": p.conflicting_files,
                    "error": p.error,
                }
                for p in self.predictions
            ],
            "error": self.error,
        }


def _resolve_head_sha(repo_path: str, branch: str) -> tuple[str, str]:
    """Resolve a branch name to its HEAD SHA.

    Returns (sha, error).  sha is empty on error.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"{branch}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as exc:
        return "", f"git rev-parse {branch!r} failed: {exc}"
    if result.returncode != 0:
        return "", f"git rev-parse {branch!r}: {result.stderr.strip()}"
    sha = result.stdout.strip()
    if not sha:
        return "", f"git rev-parse {branch!r}: empty output"
    return sha, ""


def _check_conflict(
    repo_path: str,
    base_branch: str,
    merge_branch: str,
) -> tuple[bool, list[str], str]:
    """Check if merging merge_branch into base_branch produces conflicts.

    Uses git merge-tree to simulate the merge without touching the working
    tree.  Returns (has_conflict, conflicting_files, error).
    """
    try:
        result = subprocess.run(
            ["git", "merge-tree", base_branch, merge_branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=_MERGE_TREE_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError) as exc:
        return False, [], f"git merge-tree failed: {exc}"

    if result.returncode == 0:
        return False, [], ""
    if result.returncode == 1:
        # Conflicts detected — parse the output for conflicting files.
        files: list[str] = []
        seen: set[str] = set()
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            m = _CONFLICT_FILE_RE.search(line)
            if m:
                fpath = m.group(1)
                if fpath not in seen:
                    files.append(fpath)
                    seen.add(fpath)
        return True, files, ""

    # Return code other than 0 or 1 — treat as error.
    stderr = result.stderr.strip() if result.stderr else ""
    return False, [], f"git merge-tree exit code {result.returncode}: {stderr}"


class ConflictImpactPredictor:
    """Predict downstream merge conflicts for a PR against other open PRs.

    Uses git merge-tree to simulate merges without touching the working
    tree.  Results are cached with SHA-based keys for automatic
    invalidation on push/rebase.

    Attributes:
        cache: The TTLCache instance used for result caching.
    """

    def __init__(self, cache: TTLCache | None = None) -> None:
        self.cache = cache or TTLCache()

    def predict(
        self,
        repo_path: str,
        target_branch: str,
        other_branches: list[str],
        cache_ttl_ms: int = _DEFAULT_CACHE_TTL_MS,
    ) -> ConflictImpactResult:
        """Predict conflicts between target_branch and each other branch.

        Args:
            repo_path: Path to the git repository.
            target_branch: The PR branch being analyzed.
            other_branches: List of other open PR branches to check against.
            cache_ttl_ms: Cache TTL in milliseconds.

        Returns:
            A ConflictImpactResult with the aggregate score and per-branch
            predictions.
        """
        if not other_branches:
            return ConflictImpactResult(
                target_branch=target_branch,
                score=0,
                total_checked=0,
            )

        # Resolve the target branch SHA.
        target_sha, target_err = _resolve_head_sha(repo_path, target_branch)
        if target_err:
            logger.warning(
                "conflict_impact: cannot resolve target branch %r: %s",
                target_branch, target_err,
            )
            return ConflictImpactResult(
                target_branch=target_branch,
                error=f"Cannot resolve target branch: {target_err}",
            )

        predictions: list[ConflictPrediction] = []

        for branch in other_branches:
            # Skip self-comparisons.
            if branch == target_branch:
                continue

            # Resolve the other branch SHA.
            other_sha, sha_err = _resolve_head_sha(repo_path, branch)
            if sha_err:
                logger.debug(
                    "conflict_impact: cannot resolve branch %r: %s",
                    branch, sha_err,
                )
                predictions.append(
                    ConflictPrediction(
                        branch=branch,
                        has_conflict=False,
                        error=sha_err,
                    )
                )
                continue

            # Check cache.
            cache_key = f"cip:{repo_path}:{target_sha}:{other_sha}"
            cached = self.cache.get(cache_key)
            if cached is not None:
                # cached is (has_conflict, conflicting_files)
                has_conflict, conflicting_files = cached
                predictions.append(
                    ConflictPrediction(
                        branch=branch,
                        head_sha=other_sha,
                        has_conflict=has_conflict,
                        conflicting_files=conflicting_files,
                    )
                )
                continue

            # Run git merge-tree: simulate merging target into other.
            # The question is "if target lands on main, would other conflict?"
            # We simulate by checking if the two branches can merge.
            has_conflict, files, err = _check_conflict(
                repo_path, other_sha, target_sha,
            )

            if err:
                logger.debug(
                    "conflict_impact: merge-tree %r vs %r failed: %s",
                    target_branch, branch, err,
                )
                predictions.append(
                    ConflictPrediction(
                        branch=branch,
                        head_sha=other_sha,
                        has_conflict=False,
                        error=err,
                    )
                )
            else:
                # Cache the result.
                self.cache.set(
                    cache_key, (has_conflict, files), ttl_ms=cache_ttl_ms,
                )
                predictions.append(
                    ConflictPrediction(
                        branch=branch,
                        head_sha=other_sha,
                        has_conflict=has_conflict,
                        conflicting_files=files,
                    )
                )

        # Compute aggregate.
        conflicting = [p for p in predictions if p.has_conflict]
        return ConflictImpactResult(
            target_branch=target_branch,
            score=len(conflicting),
            total_checked=len(predictions),
            predictions=predictions,
            conflicting_predictions=conflicting,
        )

    def invalidate_branch(self, repo_path: str, branch: str) -> None:
        """Invalidate all cached results involving the given branch.

        Call this when a branch has been updated (push/rebase) to ensure
        stale predictions are evicted.
        """
        prefix = f"cip:{repo_path}:"
        self.cache.invalidate_prefix(prefix)

    def clear(self) -> None:
        """Clear all cached predictions."""
        self.cache.invalidate_prefix("cip:")
