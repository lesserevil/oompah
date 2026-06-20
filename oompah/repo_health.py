"""Generic managed-repository health checks."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


def _run_git(args: list[str], repo_path: str, *, timeout: int = 60) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, "", str(exc)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _current_branch(repo_path: str) -> str:
    rc, out, _ = _run_git(["symbolic-ref", "--short", "HEAD"], repo_path)
    return out.strip() if rc == 0 else ""


def _rev_count(repo_path: str, rangespec: str) -> int:
    rc, out, _ = _run_git(["rev-list", "--count", rangespec], repo_path)
    try:
        return int(out.strip()) if rc == 0 else 0
    except ValueError:
        return 0


def list_unmerged_paths(repo_path: str) -> list[str]:
    """Return all unmerged-index paths in a repository."""
    rc, out, _ = _run_git(["ls-files", "-u", "-z"], repo_path)
    if rc != 0 or not out:
        return []
    paths: set[str] = set()
    for entry in out.split("\0"):
        if not entry:
            continue
        tab = entry.find("\t")
        if tab != -1:
            paths.add(entry[tab + 1 :])
    return sorted(paths)


def ensure_repo_sound(
    repo_path: str,
    default_branch: str,
    remote: str = "origin",
) -> dict[str, Any]:
    """Best-effort recovery for a managed checkout.

    The function is intentionally tracker-neutral. It aborts stranded merge or
    rebase operations, fetches, returns to the default branch, and fast-forwards
    to the remote default branch. It only hard-resets when the worktree is clean
    and there are no unpushed commits.
    """
    actions: list[str] = []
    git_dir = os.path.join(repo_path, ".git")
    if not os.path.isdir(git_dir):
        return {"sound": False, "actions": [], "unrecoverable": [], "reset": False}

    default_branch = (default_branch or "main").strip() or "main"
    remote_ref = f"{remote}/{default_branch}"

    if os.path.exists(os.path.join(git_dir, "MERGE_HEAD")):
        _run_git(["merge", "--abort"], repo_path)
        actions.append("merge-abort")
    if os.path.isdir(os.path.join(git_dir, "rebase-merge")) or os.path.isdir(
        os.path.join(git_dir, "rebase-apply")
    ):
        _run_git(["rebase", "--abort"], repo_path)
        actions.append("rebase-abort")

    _run_git(["fetch", remote], repo_path)

    if _current_branch(repo_path) != default_branch:
        if _run_git(["checkout", default_branch], repo_path)[0] == 0:
            actions.append("checkout-default")

    rc, _, _ = _run_git(
        ["pull", "--ff-only", "--autostash", remote, default_branch],
        repo_path,
        timeout=120,
    )
    if rc == 0:
        actions.append("ff-pull")

    def _sound() -> bool:
        return (
            not list_unmerged_paths(repo_path)
            and _rev_count(repo_path, f"HEAD..{remote_ref}") == 0
            and _current_branch(repo_path) == default_branch
        )

    if _sound():
        return {"sound": True, "actions": actions, "unrecoverable": [], "reset": False}

    rc, dirty_out, _ = _run_git(["status", "--porcelain"], repo_path)
    working_tree_clean = rc == 0 and not dirty_out.strip()
    unpushed = _rev_count(repo_path, f"{remote_ref}..HEAD")

    if working_tree_clean and unpushed == 0:
        _run_git(["reset", "--hard", remote_ref], repo_path)
        actions.append("hard-reset")
        sound = _sound()
        return {
            "sound": sound,
            "actions": actions,
            "unrecoverable": [] if sound else list_unmerged_paths(repo_path),
            "reset": True,
        }

    unrecoverable = list_unmerged_paths(repo_path) or [
        f"unsound: dirty/divergent checkout at {repo_path} "
        f"({unpushed} unpushed, dirty={not working_tree_clean})"
    ]
    logger.warning(
        "Checkout %s not sound; preserving uncommitted/unpushed work. actions=%s",
        repo_path,
        ",".join(actions) or "none",
    )
    return {
        "sound": False,
        "actions": actions,
        "unrecoverable": unrecoverable,
        "reset": False,
    }
