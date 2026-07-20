"""Managed-project bootstrap scaffolding.

This module owns the project-template bits that used to live in the separate
``lesserevil/bootstrap`` repository.  It provides drift detection, preview, and
apply helpers for baseline AGENTS.md, docs/plans READMEs, githook scaffolding,
and missing Makefile/.gitignore files.

It also owns the **state-branch bootstrap** (OOMPAH-258): creating the initial
``oompah/state/<project-id>`` orphan branch with the canonical task-tree layout
so that newly bootstrapped projects are state-branch-enabled by default.
"""

from __future__ import annotations

import difflib
import os
import shutil
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

# ---------------------------------------------------------------------------
# Canonical task-tree directory names (state-branch layout).
# Mirrors the layout described in plans/state-branch-design.md § 2.2.
# ---------------------------------------------------------------------------

STATE_BRANCH_TASK_DIRS: tuple[str, ...] = (
    "proposed",
    "backlog",
    "open",
    "in-progress",
    "needs-human",
    "in-review",
    "done",
    "merged",
    "archived",
)


# ---------------------------------------------------------------------------
# Existing file-bootstrap types
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# State-branch bootstrap types
# ---------------------------------------------------------------------------


@dataclass
class StateBranchBootstrapResult:
    """Result of initialising the oompah state branch for a project.

    Attributes
    ----------
    branch_name:
        The canonical state-branch name (``oompah/state/<project-id>``).
    already_existed:
        ``True`` when the branch was found locally or at origin and no new
        commits were created.  The caller can use this to distinguish a fresh
        bootstrap from an idempotent re-run.
    created:
        ``True`` when the orphan branch was freshly created in this call.
    commit_sha:
        The SHA of the bootstrap commit, or ``""`` when the branch already
        existed and no commit was created.
    pushed:
        ``True`` when the branch was pushed to ``origin`` in this call.
    seeded_from_main:
        ``True`` when ``.oompah/tasks/`` was seeded from the default branch.
        ``False`` for a brand-new project where the seed is an empty layout.
    error:
        Non-empty string when the bootstrap failed; empty string on success.
    """

    branch_name: str = ""
    already_existed: bool = False
    created: bool = False
    commit_sha: str = ""
    pushed: bool = False
    seeded_from_main: bool = False
    error: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


def _run_git(
    args: list[str],
    *,
    cwd: str,
    env: dict[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    """Run a git command; return the CompletedProcess regardless of exit code."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _git_branch_exists_local(repo_path: str, branch: str) -> bool:
    r = _run_git(["rev-parse", "--verify", branch], cwd=repo_path)
    return r.returncode == 0


def _git_branch_exists_remote(repo_path: str, branch: str) -> bool:
    r = _run_git(
        ["rev-parse", "--verify", f"refs/remotes/origin/{branch}"],
        cwd=repo_path,
    )
    return r.returncode == 0


def _seed_task_dirs(target: Path, source: Path | None) -> bool:
    """Populate *target* with the canonical task-tree layout.

    When *source* is given and ``source/.oompah/tasks/`` exists, existing task
    files are copied into *target*.  Otherwise, an empty tree is created.

    Returns ``True`` when task files were seeded from *source*, ``False`` for
    an empty seed.
    """
    tasks_dir = target / ".oompah" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    seeded = False
    if source is not None:
        src_tasks = source / ".oompah" / "tasks"
        if src_tasks.is_dir():
            shutil.copytree(str(src_tasks), str(tasks_dir), dirs_exist_ok=True)
            seeded = True

    # Ensure all canonical status subdirectories exist (even if seeded).
    for d in STATE_BRANCH_TASK_DIRS:
        (tasks_dir / d).mkdir(exist_ok=True)
        # git does not track empty directories, so add a .gitkeep in each.
        gitkeep = tasks_dir / d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")

    return seeded


# ---------------------------------------------------------------------------
# State-branch bootstrap public API
# ---------------------------------------------------------------------------


def initialize_state_branch(
    repo_path: str | Path,
    project_id: str,
    *,
    default_branch: str = "main",
    git_user_name: str | None = None,
    git_user_email: str | None = None,
    push: bool = False,
) -> StateBranchBootstrapResult:
    """Create and seed the state branch for *project_id* inside *repo_path*.

    The state branch is named ``oompah/state/<project-id>``.  This function
    implements the bootstrap algorithm from ``plans/state-branch-design.md``
    § 2.3:

    1. If the branch already exists locally or at ``origin``, return immediately
       with ``already_existed=True`` (idempotent — no data is lost).
    2. Create an orphan branch (no shared history with code branches).
    3. Seed ``.oompah/tasks/`` from ``default_branch`` when it exists, or with
       an empty canonical layout for brand-new projects.
    4. Commit the initial state.
    5. Optionally push to ``origin``.
    6. Return to *default_branch*.

    Parameters
    ----------
    repo_path:
        Absolute path to the managed git checkout.
    project_id:
        Oompah project identifier (e.g. ``"proj-14849f1b"``).  Used to derive
        the state branch name.
    default_branch:
        The code branch to return to after bootstrapping.  Defaults to
        ``"main"``.
    git_user_name / git_user_email:
        Optional git identity to use for the bootstrap commit.
    push:
        When ``True``, push the new state branch to ``origin`` after the
        bootstrap commit.  Defaults to ``False`` to keep the function safe in
        unit tests that run without a remote.

    Returns
    -------
    StateBranchBootstrapResult
        On success, ``result.error`` is empty.  On failure, ``result.error``
        describes what went wrong.
    """
    repo_path = Path(repo_path)
    branch_name = f"oompah/state/{project_id}"
    result = StateBranchBootstrapResult(branch_name=branch_name)

    # Validate the repo path exists before running any git commands.
    if not repo_path.is_dir():
        result.error = (
            f"Repository path does not exist or is not a directory: {repo_path}"
        )
        return result

    repo_str = str(repo_path)

    # Build git env with optional identity override.
    env = os.environ.copy()
    if git_user_name:
        env["GIT_AUTHOR_NAME"] = git_user_name
        env["GIT_COMMITTER_NAME"] = git_user_name
    if git_user_email:
        env["GIT_AUTHOR_EMAIL"] = git_user_email
        env["GIT_COMMITTER_EMAIL"] = git_user_email

    def _git(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return _run_git(args, cwd=repo_str, env=env, timeout=timeout)

    # ------------------------------------------------------------------
    # Step 1: Idempotency — check whether the branch already exists.
    # ------------------------------------------------------------------
    local_exists = _git_branch_exists_local(repo_str, branch_name)
    remote_exists = _git_branch_exists_remote(repo_str, branch_name)

    if local_exists or remote_exists:
        result.already_existed = True
        return result

    # ------------------------------------------------------------------
    # Step 2: Remember current branch so we can return to it later.
    # ------------------------------------------------------------------
    current_branch_r = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    original_branch = (
        current_branch_r.stdout.strip() if current_branch_r.returncode == 0 else default_branch
    )

    # ------------------------------------------------------------------
    # Step 3: Create an orphan branch.
    # ------------------------------------------------------------------
    orphan_r = _git(["checkout", "--orphan", branch_name])
    if orphan_r.returncode != 0:
        result.error = (
            f"git checkout --orphan {branch_name} failed: "
            f"{orphan_r.stderr.strip()[:300]}"
        )
        return result

    # Remove everything from the working tree and index so the orphan starts
    # completely clean.  Ignore errors from rm — the working tree may be
    # empty for a brand-new repo.
    _git(["rm", "-rf", "--quiet", "."])

    # ------------------------------------------------------------------
    # Step 4: Seed .oompah/tasks/ from default_branch (if it exists) or
    #          from an empty canonical layout.
    # ------------------------------------------------------------------
    # Check whether the default branch has .oompah/tasks/
    source_branch_exists = _git_branch_exists_local(repo_str, default_branch)
    source_dir: Path | None = None
    if source_branch_exists:
        # Temporarily check out just .oompah/ from the default branch into a
        # temp directory, then copy it into the working tree.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # git archive into the temp dir
            archive_r = _run_git(
                [
                    "archive",
                    "--format=tar",
                    default_branch,
                    "--",
                    ".oompah/",
                ],
                cwd=repo_str,
                env=env,
            )
            if archive_r.returncode == 0 and archive_r.stdout:
                # Unpack the archive
                import tarfile
                import io
                tar_bytes = archive_r.stdout.encode("latin-1") if isinstance(archive_r.stdout, str) else archive_r.stdout
                try:
                    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tf:
                        tf.extractall(str(tmp_path), filter="data")
                    source_dir = tmp_path
                except Exception:
                    source_dir = None
            result.seeded_from_main = _seed_task_dirs(repo_path, source_dir)
    else:
        result.seeded_from_main = _seed_task_dirs(repo_path, None)

    # ------------------------------------------------------------------
    # Step 5: Stage and commit.
    # ------------------------------------------------------------------
    add_r = _git(["add", ".oompah/"])
    if add_r.returncode != 0:
        # Roll back to original branch before returning error.
        _git(["checkout", original_branch])
        result.error = f"git add .oompah/ failed: {add_r.stderr.strip()[:300]}"
        return result

    commit_r = _git(
        [
            "commit",
            "-m",
            f"chore: bootstrap oompah state branch for {project_id}",
        ]
    )
    if commit_r.returncode != 0:
        _git(["checkout", original_branch])
        result.error = f"git commit failed: {commit_r.stderr.strip()[:300]}"
        return result

    sha_r = _git(["rev-parse", "HEAD"])
    if sha_r.returncode == 0:
        result.commit_sha = sha_r.stdout.strip()

    result.created = True

    # ------------------------------------------------------------------
    # Step 6: Optionally push to origin.
    # ------------------------------------------------------------------
    if push:
        push_r = _git(["push", "origin", branch_name], timeout=60)
        if push_r.returncode != 0:
            # Return to original branch before surfacing the error.
            _git(["checkout", original_branch])
            result.error = f"git push failed: {push_r.stderr.strip()[:300]}"
            return result
        result.pushed = True

    # ------------------------------------------------------------------
    # Step 7: Return to original branch.
    # ------------------------------------------------------------------
    checkout_r = _git(["checkout", original_branch])
    if checkout_r.returncode != 0:
        # Non-fatal: log but don't override the success result.
        result.error = (
            f"state branch created successfully but failed to return to "
            f"{original_branch!r}: {checkout_r.stderr.strip()[:200]}"
        )

    return result


def ensure_state_branch_initialized(
    repo_path: str | Path,
    project_id: str,
    *,
    default_branch: str = "main",
    git_user_name: str | None = None,
    git_user_email: str | None = None,
    push: bool = False,
) -> StateBranchBootstrapResult:
    """Idempotently ensure the state branch is initialised.

    Delegates to :func:`initialize_state_branch`.  Raises :exc:`RuntimeError`
    on failure (unlike ``initialize_state_branch`` which returns errors in the
    result object).  Suitable for callers that want to fail loudly on setup
    errors.
    """
    result = initialize_state_branch(
        repo_path,
        project_id,
        default_branch=default_branch,
        git_user_name=git_user_name,
        git_user_email=git_user_email,
        push=push,
    )
    if result.error:
        raise RuntimeError(result.error)
    return result


# ---------------------------------------------------------------------------
# Existing file-bootstrap public API
# ---------------------------------------------------------------------------


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
    "STATE_BRANCH_TASK_DIRS",
    "StateBranchBootstrapResult",
    "apply_project_bootstrap_updates",
    "check_project_bootstrap_drift",
    "ensure_project_bootstrap",
    "ensure_state_branch_initialized",
    "initialize_state_branch",
    "preview_project_bootstrap_updates",
]
