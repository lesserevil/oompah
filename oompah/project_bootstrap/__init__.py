"""Managed-project bootstrap scaffolding.

This module owns the project-template bits that used to live in the separate
``lesserevil/bootstrap`` repository.  It provides drift detection, preview, and
apply helpers for baseline AGENTS.md, docs/plans READMEs, githook scaffolding,
and missing Makefile/.gitignore files.
"""

from __future__ import annotations

import difflib
import os
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from oompah.agent_instructions import update_agents_text_for_oompah_tasks
from oompah.project_bootstrap.templates import (
    CANONICAL_FILES,
    COMMENT_BEGIN_MARKER,
    EXECUTABLE_PATHS,
    HTML_BEGIN_MARKER,
)


@dataclass
class BootstrapDrift:
    """State of one bootstrap-managed path relative to oompah's canonical text."""

    path: str
    canonical: str
    current: str | None
    is_current: bool
    diff: str
    protected: bool = False
    reason: str = ""


@dataclass
class ProjectBootstrapStatus:
    """Drift status for canonical project bootstrap files."""

    all_current: bool
    drifted: list[BootstrapDrift] = field(default_factory=list)
    current: list[BootstrapDrift] = field(default_factory=list)
    protected: list[BootstrapDrift] = field(default_factory=list)


@dataclass
class ProjectBootstrapApplyResult:
    """Result of applying bootstrap files to a managed repo."""

    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    protected: list[str] = field(default_factory=list)
    commit_sha: str = ""
    pushed: bool = False
    error: str = ""


def _read_current(repo_path: str | Path, rel_path: str) -> str | None:
    try:
        return (Path(repo_path) / rel_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _is_oompah_managed_file(rel_path: str, current: str | None) -> bool:
    if current is None:
        return True
    if rel_path == "AGENTS.md":
        return True
    return HTML_BEGIN_MARKER in current or COMMENT_BEGIN_MARKER in current


def _canonical_for_path(rel_path: str, current: str | None) -> tuple[str, bool, str]:
    """Return canonical content, protected flag, and reason for *rel_path*."""

    if rel_path == "AGENTS.md" and current is not None:
        updated, _changed = update_agents_text_for_oompah_tasks(current)
        return updated, False, ""

    canonical = CANONICAL_FILES[rel_path]
    if _is_oompah_managed_file(rel_path, current):
        return canonical, False, ""
    return (
        current or canonical,
        True,
        "existing file is project-owned and has no oompah bootstrap marker",
    )


def _build_diff(rel_path: str, canonical: str, current: str | None) -> str:
    if current == canonical:
        return ""
    return "".join(
        difflib.unified_diff(
            (current or "").splitlines(keepends=True),
            canonical.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
    )


def check_project_bootstrap_drift(repo_path: str | Path) -> ProjectBootstrapStatus:
    """Return bootstrap drift status for *repo_path*.

    Existing project-owned files without oompah bootstrap markers are reported
    as protected and are not considered drift.  AGENTS.md is special: only its
    oompah task-tracking block is updated when the file already exists.
    """

    drifted: list[BootstrapDrift] = []
    current_entries: list[BootstrapDrift] = []
    protected: list[BootstrapDrift] = []

    for rel_path in CANONICAL_FILES:
        current = _read_current(repo_path, rel_path)
        canonical, is_protected, reason = _canonical_for_path(rel_path, current)
        diff = "" if is_protected else _build_diff(rel_path, canonical, current)
        entry = BootstrapDrift(
            path=rel_path,
            canonical=canonical,
            current=current,
            is_current=(not is_protected and current == canonical),
            diff=diff,
            protected=is_protected,
            reason=reason,
        )
        if is_protected:
            protected.append(entry)
        elif entry.is_current:
            current_entries.append(entry)
        else:
            drifted.append(entry)

    return ProjectBootstrapStatus(
        all_current=len(drifted) == 0,
        drifted=drifted,
        current=current_entries,
        protected=protected,
    )


def preview_project_bootstrap_updates(repo_path: str | Path) -> str:
    """Return a combined unified diff for pending bootstrap updates."""

    status = check_project_bootstrap_drift(repo_path)
    return "\n".join(d.diff for d in status.drifted if d.diff)


def _repo_is_dirty(repo_path: str | Path, paths: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "-u"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"git status failed: {exc}") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"git status exited {result.returncode}: {result.stderr.strip()[:200]}"
        )

    dirty: set[str] = set()
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        dirty.add(line[3:].strip())

    return [p for p in paths if p in dirty]


def apply_project_bootstrap_updates(
    repo_path: str | Path,
    *,
    git_user_name: str | None = None,
    git_user_email: str | None = None,
    branch: str = "main",
    commit_message: str = "chore: refresh oompah project bootstrap files",
    push: bool = True,
    commit: bool = True,
    dry_run: bool = False,
) -> ProjectBootstrapApplyResult:
    """Write pending bootstrap files and optionally commit/push.

    The apply path only writes drifted oompah-owned paths.  Existing
    project-owned files without bootstrap markers are reported as protected and
    left untouched.
    """

    repo_path = Path(repo_path)
    result = ProjectBootstrapApplyResult()
    status = check_project_bootstrap_drift(repo_path)
    result.protected = [d.path for d in status.protected]

    if status.all_current:
        result.skipped = [d.path for d in status.current]
        return result

    to_write = [d.path for d in status.drifted]
    try:
        conflicts = _repo_is_dirty(repo_path, to_write)
    except RuntimeError as exc:
        result.error = f"dirty-worktree check failed: {exc}"
        return result

    if conflicts:
        result.error = (
            "Refused: the following bootstrap files have uncommitted changes "
            "that would be overwritten - commit or stash them first:\n"
            + "\n".join(f"  {p}" for p in conflicts)
        )
        return result

    if dry_run:
        result.applied = to_write
        result.skipped = [d.path for d in status.current]
        return result

    for drift in status.drifted:
        dest = repo_path / drift.path
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(drift.canonical, encoding="utf-8")
            if drift.path in EXECUTABLE_PATHS:
                mode = dest.stat().st_mode
                dest.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            result.applied.append(drift.path)
        except OSError as exc:
            result.error = f"Failed to write {drift.path}: {exc}"
            return result

    result.skipped = [d.path for d in status.current]

    if not commit:
        return result

    env = os.environ.copy()
    if git_user_name:
        env["GIT_AUTHOR_NAME"] = git_user_name
        env["GIT_COMMITTER_NAME"] = git_user_name
    if git_user_email:
        env["GIT_AUTHOR_EMAIL"] = git_user_email
        env["GIT_COMMITTER_EMAIL"] = git_user_email

    def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

    add = _run(["git", "add"] + result.applied)
    if add.returncode != 0:
        result.error = f"git add failed: {add.stderr.strip()[:300]}"
        return result

    commit_r = _run(["git", "commit", "-m", commit_message])
    if commit_r.returncode != 0:
        stderr = commit_r.stderr.strip()[:300]
        if "nothing to commit" in commit_r.stdout or "nothing to commit" in stderr:
            result.applied = []
            result.skipped = list(CANONICAL_FILES.keys())
            return result
        result.error = f"git commit failed: {stderr}"
        return result

    sha_r = _run(["git", "rev-parse", "HEAD"])
    if sha_r.returncode == 0:
        result.commit_sha = sha_r.stdout.strip()

    if push:
        push_r = _run(["git", "push", "origin", branch], timeout=60)
        if push_r.returncode != 0:
            result.error = f"git push failed: {push_r.stderr.strip()[:300]}"
            return result
        result.pushed = True

    return result


def ensure_project_bootstrap(
    repo_path: str | Path,
    *,
    git_user_name: str | None = None,
    git_user_email: str | None = None,
    branch: str = "main",
    push: bool = True,
) -> bool:
    """Idempotently apply, commit, and push bootstrap updates when needed."""

    result = apply_project_bootstrap_updates(
        repo_path,
        git_user_name=git_user_name,
        git_user_email=git_user_email,
        branch=branch,
        push=push,
        commit=True,
    )
    if result.error:
        raise RuntimeError(result.error)
    return bool(result.applied)


__all__ = [
    "BootstrapDrift",
    "ProjectBootstrapApplyResult",
    "ProjectBootstrapStatus",
    "apply_project_bootstrap_updates",
    "check_project_bootstrap_drift",
    "ensure_project_bootstrap",
    "preview_project_bootstrap_updates",
]

