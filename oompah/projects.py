"""Project storage and git worktree management."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

import yaml

from oompah.attachments import ATTACHMENTS_SUBDIR, LFS_PATTERNS
from oompah.backlog_compat import (
    BacklogCompatibilityError,
    ensure_backlog_compatible,
)
from oompah.git_hooks import hook_path as _bundled_hook_path
from oompah.models import Project

logger = logging.getLogger(__name__)

DEFAULT_PROJECTS_PATH = ".oompah/projects.json"
DEFAULT_REPOS_ROOT = os.path.expanduser("~/.oompah/repos")
DEFAULT_WORKTREE_ROOT = os.path.expanduser("~/.oompah/worktrees")
DEFAULT_SOURCE_SYNC_TIMEOUT_S = 45.0


class ProjectError(Exception):
    """Raised when project registration or worktree management fails."""


def _repo_name_from_url(repo_url: str) -> str:
    """Derive a stable display/repo directory name from a git URL or path."""
    value = (repo_url or "").strip().rstrip("/")
    if not value:
        return "unnamed"
    if value.endswith(".git"):
        value = value[:-4]
    if ":" in value and "/" not in value.rsplit(":", 1)[0]:
        value = value.rsplit(":", 1)[-1]
    name = os.path.basename(value)
    return name or "unnamed"


def github_owner_repo_from_url(repo_url: str) -> tuple[str | None, str | None]:
    """Return ``(owner, repo)`` for GitHub clone URLs, else ``(None, None)``."""
    value = (repo_url or "").strip()
    if not value:
        return None, None

    path = ""
    if value.startswith("git@") or re.match(r"^[^/@:]+@github\.com:", value, re.I):
        if ":" not in value:
            return None, None
        host, path = value.split(":", 1)
        if not host.lower().endswith("@github.com"):
            return None, None
    elif value.lower().startswith(("https://", "http://", "ssh://")):
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if host != "github.com":
            return None, None
        path = parsed.path
    else:
        return None, None

    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        return None, None
    return parts[0], parts[1]


def _sanitize_identifier(value: str) -> str:
    """Make a project or task identifier safe for local branch/path names."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned.strip("._-") or "unnamed"


def github_work_branch_name(project_name: str, issue_number: int | str) -> str:
    """Generate a GitHub-safe git branch name for a GitHub-backed task.

    Branch names follow the format ``oompah/<project-slug>/gh-<number>``
    so they are filesystem-safe, globally unique within the project, and
    do not rely on bare task numbers (AC#1 in TASK-461.3).

    Storing the result in GitHub issue metadata before creating the worktree
    lets review reconciliation resolve the task from a PR source branch
    without guessing by task ID (AC#2 in TASK-461.3).

    Parameters
    ----------
    project_name:
        Human-readable project name (e.g. ``"trickle"``). Sanitized to
        ``[A-Za-z0-9._-]+`` and used as the middle path component.
    issue_number:
        GitHub issue number (positive integer or numeric string).

    Returns
    -------
    str
        Branch name of the form ``oompah/<project-slug>/gh-<number>``.
    """
    slug = _sanitize_identifier(str(project_name))
    return f"oompah/{slug}/gh-{issue_number}"


def _task_id_key(value: str | None) -> str:
    return str(value or "").strip().lower()


def _task_file_frontmatter_id(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end < 0:
        return None
    try:
        meta = yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        return None
    task_id = meta.get("id") if isinstance(meta, dict) else None
    return str(task_id).strip() if task_id else None


def _task_file_status(path: str) -> str | None:
    """Read the ``status:`` field from a Backlog task file's frontmatter,
    or None when absent/unparseable."""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end < 0:
        return None
    try:
        meta = yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        return None
    status = meta.get("status") if isinstance(meta, dict) else None
    return str(status).strip() if status else None


def _backlog_task_files(root: str) -> list[str]:
    files: list[str] = []
    for rel_dir in ("backlog/tasks", "backlog/completed"):
        task_dir = os.path.join(root, rel_dir)
        if not os.path.isdir(task_dir):
            continue
        for dirpath, _dirs, filenames in os.walk(task_dir):
            for filename in filenames:
                if filename.endswith(".md"):
                    files.append(os.path.join(dirpath, filename))
    return files


def _task_file_matches(path: str, issue_identifier: str) -> bool:
    key = _task_id_key(issue_identifier)
    if not key:
        return False
    frontmatter_id = _task_file_frontmatter_id(path)
    if frontmatter_id and _task_id_key(frontmatter_id) == key:
        return True
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    return stem.startswith(key)


def _bootstrap_lfs(repo_path: str) -> bool:
    """Install git LFS and track supported attachment formats for a repo.

    Returns False when git-lfs is unavailable or fails. The project can
    still operate without LFS; attachments just won't get large-file
    handling until the operator installs it.
    """
    if not repo_path or not os.path.isdir(repo_path):
        return False
    try:
        subprocess.run(
            ["git", "lfs", "install", "--local"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False

    attributes_dir = os.path.join(repo_path, ATTACHMENTS_SUBDIR)
    attributes_path = os.path.join(attributes_dir, ".gitattributes")
    os.makedirs(attributes_dir, exist_ok=True)
    lines = [
        f"{pattern} filter=lfs diff=lfs merge=lfs -text"
        for pattern in LFS_PATTERNS
    ]
    try:
        with open(attributes_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        return False
    return True


def _install_prepare_commit_msg_hook(wt_path: str) -> None:
    """Symlink the bundled ``prepare-commit-msg`` hook into the worktree's
    redirected hooks directory (``<wt_path>/.oompah-no-hooks``).

    Agents commit from inside worktrees; this hook (see
    ``oompah/git_hooks/prepare-commit-msg``) rewrites every commit message
    to strip model-attribution trailers (``Co-authored-by: Claude``, etc.)
    and stamp the canonical oompah trailer block.

    Falls back to a file copy if the platform refuses to create a symlink
    (e.g. some Windows configurations). Idempotent — re-running on an
    existing worktree replaces a stale link/copy with the current bundled
    source, so an oompah upgrade flows through to in-flight worktrees on
    the next dispatch.
    """
    src = _bundled_hook_path("prepare-commit-msg")
    if not os.path.isfile(src):
        # Should never happen in a normal install, but be defensive: bail
        # silently rather than crash worktree creation.
        return
    hooks_dir = os.path.join(wt_path, ".oompah-no-hooks")
    os.makedirs(hooks_dir, exist_ok=True)
    dst = os.path.join(hooks_dir, "prepare-commit-msg")

    # Remove any existing entry so we can replace it with a fresh link.
    try:
        if os.path.islink(dst) or os.path.exists(dst):
            os.remove(dst)
    except OSError:
        pass

    try:
        os.symlink(src, dst)
    except (OSError, NotImplementedError):
        # Symlink failed (Windows without privilege, etc.) — copy instead.
        try:
            with open(src, "rb") as rf, open(dst, "wb") as wf:
                wf.write(rf.read())
        except OSError:
            return

    # Ensure the hook is executable. Symlinks resolve to the bundled source
    # (already chmod +x in the repo); only chmod a real file copy to avoid
    # follow_symlinks-on-chmod portability issues on macOS/BSD.
    if not os.path.islink(dst):
        try:
            os.chmod(dst, 0o755)
        except OSError:
            pass


def _is_transient_git_config_lock_error(stderr: str) -> bool:
    """Return True if ``stderr`` indicates a transient ``.git/config`` lock
    contention failure.

    These happen when concurrent git operations (in oompah's case: multiple
    ``git worktree add`` calls running in parallel from the orchestrator's
    thread pool) race for the ``.git/config`` lock. ``git worktree add``
    still creates the worktree directory and branch on disk — only the
    final upstream-tracking config write fails. Our workflow doesn't
    depend on upstream tracking at creation time (agents push with
    ``git push -u origin HEAD`` later), so the partial success is safely
    recoverable.

    Symptom from the bug report (oompah-zlz_2-7iq)::

        error: could not lock config file .git/config: File exists
        error: unable to write upstream branch configuration
    """
    return "could not lock config file" in stderr


def _is_ref_namespace_conflict_error(stderr: str, branch_name: str) -> bool:
    """Return True if ``stderr`` indicates a git ref-namespace conflict for
    ``branch_name``.

    Git's filesystem-based ref storage cannot have both
    ``refs/heads/<branch>`` (a file) AND ``refs/heads/<branch>/<sub>``
    (a file inside a directory named ``<branch>``). Creating either when
    the other exists fails.

    Git emits two slightly different stderr formats depending on whether
    the conflicting nested ref is stored as a **loose ref** (file under
    ``.git/refs/heads/``) or a **packed ref** (entry in
    ``.git/packed-refs``):

    Loose nested ref::

        fatal: cannot lock ref 'refs/heads/<branch>':
        'refs/heads/<branch>/<sub>' exists; cannot create 'refs/heads/<branch>'

    Packed nested ref::

        fatal: 'refs/heads/<branch>/<sub>' exists; cannot create 'refs/heads/<branch>'

    Both share the ``exists; cannot create 'refs/heads/<branch>'`` tail —
    we detect on that, plus the presence of the ``refs/heads/<branch>/``
    namespace prefix, so both loose and packed variants trigger the
    recovery path in ``_git_worktree_add_with_recovery``.

    This typically happens when a previous agent (or a hand-pushed branch)
    used a slash-style nested name like ``trickle-u02z/strip-signing``,
    consuming the ``trickle-u02z`` namespace and blocking subsequent
    creation of a flat branch named ``trickle-u02z``.

    Symptom from bug reports:

    - oompah-zlz_2-kudu (loose variant)::

        fatal: cannot lock ref 'refs/heads/trickle-u02z':
        'refs/heads/trickle-u02z/strip-signing' exists;
        cannot create 'refs/heads/trickle-u02z'

    - oompah-zlz_2-4g1y (packed-refs variant — note no
      ``cannot lock ref`` prefix)::

        fatal: 'refs/heads/trickle-zwmx/in-binary-url-register' exists;
        cannot create 'refs/heads/trickle-zwmx'
    """
    if not stderr or not branch_name:
        return False
    # Match git's canonical phrasing. Be lenient about exact quoting and
    # accept both loose and packed-refs variants — both contain
    # ``exists; cannot create 'refs/heads/<branch>'`` and reference at
    # least one ``refs/heads/<branch>/<sub>`` nested ref.
    return (
        f"refs/heads/{branch_name}/" in stderr
        and f"cannot create 'refs/heads/{branch_name}'" in stderr
        and "exists" in stderr
    )


def _is_worktree_branch_already_used_error(stderr: str) -> bool:
    """Return True if ``stderr`` indicates a worktree-add failure because
    the local branch is already checked out in *another* worktree.

    Symptom (oompah-zlz_2-kcdb)::

        fatal: 'epic-rogers-zql' is already used by worktree at
        '/home/shedwards/.oompah/worktrees/rogers/rogers-gv96'

    Recovery: fall back to ``git worktree add <path> <branch>`` (no
    ``-b`` or ``-B`` flag) — this attaches the new worktree path to the
    already-checked-out branch without attempting to create or reset it.
    """
    return "is already used by worktree" in (stderr or "")


def _resolve_ref_namespace_conflict(
    cwd: str,
    branch_name: str,
    *,
    timeout: int = 5,
) -> list[tuple[str, str]]:
    """Free the ``refs/heads/<branch_name>`` namespace by renaming any local
    nested refs of the form ``<branch_name>/<sub>`` to ``<branch_name>__<sub>``.

    Returns the list of (old_name, new_name) renames performed. Empty list
    means there was nothing to do.

    Safety:

    - Only LOCAL refs are touched. Remote-tracking refs
      (``refs/remotes/origin/<branch>/<sub>``) are untouched, so the work
      remains reachable via ``origin/<old_name>`` and ``git fetch`` will
      not re-create the local branches in the conflicting namespace.
    - Renames preserve commit reachability — no work is lost. If the
      target name ``<branch_name>__<sub>`` is already taken, append a
      numeric suffix to avoid clobbering an unrelated branch.
    - Failures are logged at WARNING and skip the offending branch; the
      caller's retry will surface any unrecoverable conflict to the
      operator via the original CalledProcessError.
    """
    if not branch_name:
        return []
    # List local branches under the conflicting prefix.
    try:
        r = subprocess.run(
            [
                "git",
                "for-each-ref",
                "--format=%(refname:short)",
                f"refs/heads/{branch_name}/",
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(
            "ref-namespace-conflict: failed to enumerate refs under %s/: %s",
            branch_name,
            exc,
        )
        return []
    if r.returncode != 0:
        logger.warning(
            "ref-namespace-conflict: git for-each-ref failed rc=%d stderr=%s",
            r.returncode,
            (r.stderr or "").strip()[:200],
        )
        return []

    nested = [line.strip() for line in (r.stdout or "").splitlines() if line.strip()]
    if not nested:
        return []

    # Use a separator that cannot appear in a sanitized identifier
    # (_sanitize_identifier produces [A-Za-z0-9._-]). Double underscore
    # is safe and visually distinct.
    renames: list[tuple[str, str]] = []
    for old in nested:
        # Guard: only rename if the prefix really matches our branch.
        prefix = f"{branch_name}/"
        if not old.startswith(prefix):
            continue
        sub = old[len(prefix) :]
        # Replace any further slashes inside sub so the new name is flat.
        sub_flat = sub.replace("/", "__")
        new_base = f"{branch_name}__{sub_flat}"
        new = new_base
        # Find a free target name by appending a numeric suffix if needed.
        for n in range(1, 100):
            try:
                check = subprocess.run(
                    [
                        "git",
                        "show-ref",
                        "--verify",
                        "--quiet",
                        f"refs/heads/{new}",
                    ],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
                # If we can't check, assume free and try; rename will fail loudly.
                check = None
            if check is None or check.returncode != 0:
                # returncode != 0 from show-ref means the ref does NOT exist — free.
                break
            new = f"{new_base}_{n}"
        else:
            logger.warning(
                "ref-namespace-conflict: could not find a free rename target "
                "for %s (last tried %s); skipping",
                old,
                new,
            )
            continue

        try:
            mv = subprocess.run(
                ["git", "branch", "-m", old, new],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning(
                "ref-namespace-conflict: git branch -m %s %s failed: %s",
                old,
                new,
                exc,
            )
            continue
        if mv.returncode != 0:
            logger.warning(
                "ref-namespace-conflict: git branch -m %s %s failed rc=%d stderr=%s",
                old,
                new,
                mv.returncode,
                (mv.stderr or "").strip()[:200],
            )
            continue
        renames.append((old, new))
        logger.warning(
            "ref-namespace-conflict: renamed local branch %s -> %s to free "
            "refs/heads/%s namespace (commits preserved, remote untouched)",
            old,
            new,
            branch_name,
        )
    return renames


def _branch_name_from_worktree_cmd(cmd: list[str]) -> str | None:
    """Extract the branch name from a ``git worktree add`` command list.

    Accepts both the create-new-branch form
    (``git worktree add -b <branch> <path> <base>``) and the
    force-or-reuse form (``git worktree add -B <branch> ...``).

    Returns ``None`` if the command shape is unrecognised — callers must
    treat that as "no namespace recovery possible".
    """
    try:
        i = cmd.index("worktree")
        if cmd[i + 1] != "add":
            return None
        # Look for -b or -B after "add".
        for j in range(i + 2, len(cmd) - 1):
            if cmd[j] in ("-b", "-B"):
                return cmd[j + 1]
    except (ValueError, IndexError):
        return None
    return None


def _git_worktree_add_with_recovery(
    cmd: list[str],
    *,
    cwd: str,
    wt_path: str,
    max_attempts: int = 3,
    timeout: int = 30,
    sleep_fn=time.sleep,
) -> None:
    """Run ``git worktree add`` with retry+recovery for transient config-lock
    errors.

    Behaviour:

    - On success → return ``None``.
    - On the transient ``.git/config`` lock error: if the worktree
      directory exists, treat as success (logged at WARNING). Otherwise
      sleep with exponential backoff and retry, up to ``max_attempts``.
    - On any other ``CalledProcessError`` → re-raise immediately so the
      caller's existing branch handling (e.g. ``"already exists"``)
      remains in charge.
    - On ``TimeoutExpired`` → re-raise (caller wraps as ``ProjectError``).
    - After all retries exhaust on a transient error with no worktree
      dir → re-raise the last ``CalledProcessError``.

    ``sleep_fn`` is a seam for unit tests — production callers leave it
    as the default ``time.sleep``.

    Additional recovery (oompah-zlz_2-kudu): a one-shot ref-namespace
    conflict resolver runs when stderr matches the
    ``cannot lock ref 'refs/heads/<branch>'`` pattern. Any local nested
    refs that consumed the namespace (e.g. ``trickle-u02z/strip-signing``
    blocking creation of ``trickle-u02z``) are renamed locally with a
    ``__`` separator. The retry happens once per call to avoid loops.
    """
    last_exc: subprocess.CalledProcessError | None = None
    namespace_conflict_handled = False
    for attempt in range(max_attempts):
        try:
            subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout,
            )
            return
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            # First, see if this is a ref-namespace conflict we can heal.
            branch_name = _branch_name_from_worktree_cmd(cmd)
            if (
                branch_name
                and not namespace_conflict_handled
                and _is_ref_namespace_conflict_error(stderr, branch_name)
            ):
                namespace_conflict_handled = True
                renames = _resolve_ref_namespace_conflict(cwd, branch_name)
                if renames:
                    logger.warning(
                        "git worktree add: freed refs/heads/%s namespace by "
                        "renaming %d nested local branch(es); retrying",
                        branch_name,
                        len(renames),
                    )
                    # Don't consume the attempt budget for this recovery —
                    # this is a one-shot mitigation, not a transient race.
                    last_exc = exc
                    continue
                # Nothing to rename means a different ref still blocks us
                # (e.g. packed-refs out of sync, or a remote-tracking ref).
                # Fall through to re-raise so the operator can investigate.
                raise
            if not _is_transient_git_config_lock_error(stderr):
                raise
            last_exc = exc
            # Transient lock error: the worktree directory + branch may
            # already be on disk (upstream-config was the last step).
            # Accept that as success; we'll set upstream lazily at push.
            if os.path.isdir(wt_path):
                logger.warning(
                    "git worktree add: upstream config write failed "
                    "(.git/config lock contention) but worktree was created "
                    "path=%s attempt=%d/%d — continuing without upstream tracking",
                    wt_path,
                    attempt + 1,
                    max_attempts,
                )
                return
            # No worktree on disk — back off and retry.
            if attempt < max_attempts - 1:
                sleep_s = 0.1 * (2**attempt)
                logger.warning(
                    "git worktree add: .git/config lock contention "
                    "attempt=%d/%d; retrying in %.2fs",
                    attempt + 1,
                    max_attempts,
                    sleep_s,
                )
                sleep_fn(sleep_s)
    # Exhausted retries on a transient error with no worktree created —
    # re-raise the last CalledProcessError so the caller surfaces the
    # underlying failure to the operator.
    assert last_exc is not None
    raise last_exc



def _is_github_backed_kind(kind: str) -> bool:
    """Return True when *kind* (already lower-stripped) is a GitHub Issues tracker."""
    return kind in ("github_issues", "github-issues")


def _is_github_backed(project: "Project") -> bool:
    """Return True when *project* uses the GitHub Issues tracker backend.

    Recognised values are ``"github_issues"`` and ``"github-issues"`` to
    tolerate minor spelling variations.  All other tracker kinds (including
    ``None``, which means legacy Backlog.md) return False.
    """
    kind = (getattr(project, "tracker_kind", None) or "").strip().lower()
    return _is_github_backed_kind(kind)


class ProjectStore:
    """File-backed store for project configurations."""

    def __init__(
        self,
        path: str | None = None,
        repos_root: str | None = None,
        worktree_root: str | None = None,
    ):
        self.path = path or DEFAULT_PROJECTS_PATH
        self.repos_root = repos_root or DEFAULT_REPOS_ROOT
        self.worktree_root = worktree_root or DEFAULT_WORKTREE_ROOT
        self._projects: dict[str, Project] = {}

        # Per-project write locks for tracker mutations and git operations.
        # Serializes concurrent tracker writes (Backlog task file updates) and
        # git worktree/branch mutations for the same project so background
        # parallelism cannot corrupt shared state.  Different projects hold
        # independent locks so unrelated projects can make progress concurrently.
        # RLock (reentrant) so a caller that already holds the lock can call
        # worktree methods that also acquire it without deadlocking.
        # Access to _project_locks dict itself is protected by _project_locks_meta.
        self._project_locks: dict[str, threading.RLock] = {}
        self._project_locks_meta: threading.Lock = threading.Lock()

        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            self._projects = {}
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            self._projects = {}
            for entry in data:
                p = Project.from_dict(entry)
                if p.id:
                    self._projects[p.id] = p
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load projects from %s: %s", self.path, exc)
            self._projects = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump([p.to_dict() for p in self._projects.values()], f, indent=2)

    def list_all(self) -> list[Project]:
        return list(self._projects.values())

    def get(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)

    def project_write_lock(self, project_id: str) -> threading.RLock:
        """Return the per-project write lock for *project_id*.

        The lock is created on first access and cached for the lifetime of this
        store instance.  Callers should hold the lock while performing any
        operation that mutates Backlog task files, GitHub tracker state, git
        worktrees, or review metadata for the given project:

            with self.project_store.project_write_lock(project_id):
                tracker.update_issue(...)
                # or:
                self.project_store.create_worktree(...)

        Different projects have independent locks so unrelated projects can
        run maintenance and dispatch concurrently without blocking each other.
        The lock is reentrant (``threading.RLock``) so callers that already hold
        it can invoke worktree methods without deadlocking.
        """
        with self._project_locks_meta:
            if project_id not in self._project_locks:
                self._project_locks[project_id] = threading.RLock()
            return self._project_locks[project_id]

    def create(
        self,
        repo_url: str,
        name: str | None = None,
        branch: str = "main",
        branches: list[str] | None = None,
        default_branch: str | None = None,
        git_user_name: str | None = None,
        git_user_email: str | None = None,
        access_token: str | None = None,
        tracker_kind: str | None = None,
        tracker_owner: str | None = None,
        tracker_repo: str | None = None,
        github_project_node_id: str | None = None,
        status_actor_login: str | None = None,
        status_label_authorized_logins: list[str] | None = None,
        legacy_backlog_enabled: bool = False,
        legacy_backlog_dispatch: bool = False,
        paused: bool = True,
    ) -> Project:
        """Register a project by cloning its git repo.

        Args:
            repo_url: Git clone URL (https or ssh) or local path.
            name: Optional display name. Defaults to repo name from URL.
            branch: Legacy single branch to track. Defaults to "main".
                    Deprecated: use branches and default_branch instead.
            branches: List of branch patterns to track (e.g., ["main", "release/*", "hotfix/*"]).
                      Supports glob patterns. Defaults to ["main"].
            default_branch: Default branch for new task branches. Defaults to first entry in branches.
            tracker_kind: Per-project tracker backend (e.g. "backlog_md", "github_issues"). None
                          means fall back to global ServiceConfig.tracker_kind.
            tracker_owner: GitHub org/user owning the task hub repository.
            tracker_repo: GitHub task hub repository name.
            github_project_node_id: GitHub Projects v2 node ID for board views.
            status_actor_login: GitHub login used as the project-owner status actor.
            status_label_authorized_logins: Additional GitHub logins authorized to
                                      move protected status labels.
            legacy_backlog_enabled: When True, existing Backlog.md tasks are still readable.
            legacy_backlog_dispatch: When True, existing Backlog.md tasks are still dispatchable.
            paused: New managed projects start paused so operators can confirm
                    tracker, token, branch, and provider settings before dispatch.
        """
        if not name:
            name = _repo_name_from_url(repo_url)

        # Handle backward compatibility and new branch configuration
        if branches is None:
            branches = [branch] if branch != "main" else ["main"]
        if default_branch is None:
            default_branch = branches[0] if branches else "main"

        # Clone into ~/.oompah/repos/<name>/
        repo_path = os.path.join(self.repos_root, _sanitize_identifier(name))

        if os.path.isdir(repo_path):
            # Already cloned — pull latest
            logger.info("Repo already cloned at %s, pulling latest", repo_path)
            try:
                subprocess.run(
                    ["git", "fetch", "--all"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                logger.warning("git fetch failed for %s: %s", repo_path, exc)
        else:
            os.makedirs(os.path.dirname(repo_path), exist_ok=True)
            try:
                subprocess.run(
                    ["git", "clone", "--branch", default_branch, repo_url, repo_path],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=300,
                )
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.strip()[:500] if exc.stderr else ""
                raise ProjectError(f"git clone failed: {stderr}")
            except subprocess.TimeoutExpired:
                raise ProjectError("git clone timed out")

        # Validate clone
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            raise ProjectError(f"Clone succeeded but no .git/ found in: {repo_path}")
        # Backlog.md compatibility is only relevant for legacy Backlog projects.
        # GitHub-backed projects (tracker_kind == "github_issues") do not use
        # Backlog.md files at all, so skip the check for them (TASK-464.7).
        _resolved_kind = (tracker_kind or "").strip().lower()
        if not _is_github_backed_kind(_resolved_kind):
            try:
                ensure_backlog_compatible(repo_path)
            except BacklogCompatibilityError as exc:
                raise ProjectError(str(exc)) from exc

        # If git_user_name / git_user_email not provided, read global git config
        if not git_user_name:
            try:
                r = subprocess.run(
                    ["git", "config", "--global", "user.name"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                git_user_name = r.stdout.strip() or None
            except Exception:
                pass
        if not git_user_email:
            try:
                r = subprocess.run(
                    ["git", "config", "--global", "user.email"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                git_user_email = r.stdout.strip() or None
            except Exception:
                pass

        if not git_user_name or not git_user_email:
            missing = []
            if not git_user_name:
                missing.append("git_user_name")
            if not git_user_email:
                missing.append("git_user_email")
            raise ProjectError(
                f"No global git config found. {', '.join(missing)} must be provided."
            )

        # Set git identity on the cloned repo
        for key, val in [("user.name", git_user_name), ("user.email", git_user_email)]:
            try:
                subprocess.run(
                    ["git", "config", key, val],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except Exception:
                pass

        # Bootstrap git LFS for the multimodal attachments feature.
        # Always idempotent; degrades gracefully when git lfs is missing.
        lfs_available = _bootstrap_lfs(repo_path)

        tracker_owner_value = str(tracker_owner).strip() if tracker_owner else None
        tracker_repo_value = str(tracker_repo).strip() if tracker_repo else None
        if _is_github_backed_kind(_resolved_kind) and (
            not tracker_owner_value or not tracker_repo_value
        ):
            inferred_owner, inferred_repo = github_owner_repo_from_url(repo_url)
            tracker_owner_value = tracker_owner_value or inferred_owner
            tracker_repo_value = tracker_repo_value or inferred_repo

        project_id = f"proj-{uuid.uuid4().hex[:8]}"
        project = Project(
            id=project_id,
            name=name,
            repo_url=repo_url,
            repo_path=repo_path,
            branch=branch,  # Legacy field for backward compatibility
            branches=branches,
            default_branch=default_branch,
            git_user_name=git_user_name,
            git_user_email=git_user_email,
            access_token=access_token,
            lfs_available=lfs_available,
            tracker_kind=str(tracker_kind).strip() if tracker_kind else None,
            tracker_owner=tracker_owner_value,
            tracker_repo=tracker_repo_value,
            github_project_node_id=str(github_project_node_id).strip() if github_project_node_id else None,
            status_actor_login=str(status_actor_login).strip() if status_actor_login else None,
            status_label_authorized_logins=[
                str(login).strip()
                for login in (status_label_authorized_logins or [])
                if str(login).strip()
            ],
            legacy_backlog_enabled=bool(legacy_backlog_enabled),
            legacy_backlog_dispatch=bool(legacy_backlog_dispatch),
            paused=bool(paused),
        )
        self._projects[project_id] = project
        self._save()
        logger.info(
            "Project created id=%s name=%s repo=%s lfs_available=%s",
            project_id,
            name,
            repo_url,
            lfs_available,
        )
        return project

    # Fields that may be changed via update().
    UPDATABLE_FIELDS = frozenset(
        {
            "name",
            "repo_url",
            "branch",
            "branches",
            "default_branch",
            "git_user_name",
            "git_user_email",
            "yolo",
            "log_path",
            "webhook_secret",
            "access_token",
            "last_webhook_received_at",
            "max_in_flight_prs",
            "merge_queue_enabled",
            "paused",
            "test_command",
            "test_command_full",
            "test_skip_paths",
            "epic_strategy",
            "require_epic_for_tasks",
            "intake_auto_promote",
            "provider_whitelist",
            "status_actor_login",
            "status_label_authorized_logins",
            "backlog_conflict_paths",
            # Per-project tracker configuration (TASK-459.3 / TASK-464.2)
            "tracker_kind",
            "tracker_owner",
            "tracker_repo",
            "github_project_node_id",
            "legacy_backlog_enabled",
            "legacy_backlog_dispatch",
            "tracker_cutover_at",
        }
    )

    def update(self, project_id: str, **fields) -> Project | None:
        """Update a project's mutable fields.

        Args:
            project_id: The project to update.
            **fields: Key/value pairs to change. Only keys listed in
                      ``UPDATABLE_FIELDS`` are accepted.

        Returns:
            The updated Project, or ``None`` if *project_id* is unknown.

        Raises:
            ProjectError: If a field name is not in the allow-list or
                          if a required-string field is set to an empty value.
        """
        project = self._projects.get(project_id)
        if not project:
            return None

        unknown = set(fields) - self.UPDATABLE_FIELDS
        if unknown:
            raise ProjectError(
                f"Unknown or immutable fields: {', '.join(sorted(unknown))}"
            )

        # Validate non-empty for fields that must have a value
        for key in ("name",):
            if key in fields:
                val = fields[key]
                if isinstance(val, str):
                    val = val.strip()
                if not val:
                    raise ProjectError(f"'{key}' must not be empty")
                fields[key] = val  # store trimmed value

        # Normalize test_command / test_command_full: trim, treat empty as None.
        for key in ("test_command", "test_command_full"):
            if key in fields:
                val = fields[key]
                if val is None:
                    fields[key] = None
                else:
                    if not isinstance(val, str):
                        raise ProjectError(f"'{key}' must be a string or null")
                    s = val.strip()
                    fields[key] = s or None

        # Normalize test_skip_paths: must be a list of non-empty strings.
        if "test_skip_paths" in fields:
            val = fields["test_skip_paths"]
            if val is None:
                fields["test_skip_paths"] = []
            elif isinstance(val, list):
                cleaned = []
                for item in val:
                    if not isinstance(item, str):
                        raise ProjectError("'test_skip_paths' entries must be strings")
                    s = item.strip()
                    if s:
                        cleaned.append(s)
                fields["test_skip_paths"] = cleaned
            else:
                raise ProjectError("'test_skip_paths' must be a list of strings")

        # Validate epic_strategy is one of the three allowed modes.
        if "epic_strategy" in fields:
            val = fields["epic_strategy"]
            if val is None:
                fields["epic_strategy"] = "flat"
            else:
                if not isinstance(val, str):
                    raise ProjectError(
                        "'epic_strategy' must be one of: flat, stacked, shared"
                    )
                norm = val.strip().lower()
                if norm not in ("flat", "stacked", "shared"):
                    raise ProjectError(
                        "'epic_strategy' must be one of: flat, stacked, shared"
                    )
                fields["epic_strategy"] = norm

        if "require_epic_for_tasks" in fields:
            val = fields["require_epic_for_tasks"]
            if not isinstance(val, bool):
                raise ProjectError("'require_epic_for_tasks' must be a boolean")

        if "intake_auto_promote" in fields:
            val = fields["intake_auto_promote"]
            if not isinstance(val, bool):
                raise ProjectError("'intake_auto_promote' must be a boolean")

        # Normalize provider_whitelist: must be a list of non-empty strings.
        if "provider_whitelist" in fields:
            val = fields["provider_whitelist"]
            if val is None:
                fields["provider_whitelist"] = []
            elif isinstance(val, list):
                cleaned = []
                for item in val:
                    if not isinstance(item, str):
                        raise ProjectError(
                            "'provider_whitelist' entries must be strings"
                        )
                    s = item.strip()
                    if s:
                        cleaned.append(s)
                fields["provider_whitelist"] = cleaned
            else:
                raise ProjectError(
                    "'provider_whitelist' must be a list of strings or null"
                )

        # Normalize the project status actor: optional non-empty string.
        if "status_actor_login" in fields:
            val = fields["status_actor_login"]
            if val is None:
                fields["status_actor_login"] = None
            elif isinstance(val, str):
                fields["status_actor_login"] = val.strip() or None
            else:
                raise ProjectError("'status_actor_login' must be a string or null")

        # Normalize status label actor allowlist: must be a list of non-empty strings.
        if "status_label_authorized_logins" in fields:
            val = fields["status_label_authorized_logins"]
            if val is None:
                fields["status_label_authorized_logins"] = []
            elif isinstance(val, list):
                cleaned = []
                seen = set()
                for item in val:
                    if not isinstance(item, str):
                        raise ProjectError(
                            "'status_label_authorized_logins' entries must be strings"
                        )
                    s = item.strip()
                    key = s.lower()
                    if s and key not in seen:
                        cleaned.append(s)
                        seen.add(key)
                fields["status_label_authorized_logins"] = cleaned
            else:
                raise ProjectError(
                    "'status_label_authorized_logins' must be a list of strings or null"
                )

        # Validate max_in_flight_prs is a positive integer (floats are rejected)
        if "max_in_flight_prs" in fields:
            val = fields["max_in_flight_prs"]
            if isinstance(val, float):
                raise ProjectError("'max_in_flight_prs' must be a positive integer")
            try:
                val = int(val)
            except (TypeError, ValueError):
                raise ProjectError("'max_in_flight_prs' must be a positive integer")
            if val < 1:
                raise ProjectError("'max_in_flight_prs' must be >= 1")
            fields["max_in_flight_prs"] = val

        # ---- Per-project tracker configuration (TASK-459.3) ----

        # tracker_kind: optional string; None clears to global default.
        if "tracker_kind" in fields:
            val = fields["tracker_kind"]
            if val is None:
                fields["tracker_kind"] = None
            elif isinstance(val, str):
                s = val.strip()
                fields["tracker_kind"] = s or None
            else:
                raise ProjectError("'tracker_kind' must be a string or null")

        # tracker_owner / tracker_repo / github_project_node_id: optional strings.
        for key in ("tracker_owner", "tracker_repo", "github_project_node_id"):
            if key in fields:
                val = fields[key]
                if val is None:
                    fields[key] = None
                elif isinstance(val, str):
                    s = val.strip()
                    fields[key] = s or None
                else:
                    raise ProjectError(f"'{key}' must be a string or null")

        # legacy_backlog_enabled / legacy_backlog_dispatch: boolean flags.
        for key in ("legacy_backlog_enabled", "legacy_backlog_dispatch"):
            if key in fields:
                val = fields[key]
                if val is None:
                    fields[key] = False
                else:
                    fields[key] = bool(val)

        # tracker_cutover_at: datetime or ISO string or null.
        if "tracker_cutover_at" in fields:
            from datetime import datetime as _datetime

            val = fields["tracker_cutover_at"]
            if val is None:
                fields["tracker_cutover_at"] = None
            elif isinstance(val, _datetime):
                fields["tracker_cutover_at"] = val
            elif isinstance(val, str):
                s = val.strip()
                if not s:
                    fields["tracker_cutover_at"] = None
                else:
                    try:
                        fields["tracker_cutover_at"] = _datetime.fromisoformat(s)
                    except ValueError as exc:
                        raise ProjectError(
                            f"'tracker_cutover_at' must be an ISO 8601 datetime string or null: {exc}"
                        )
            else:
                raise ProjectError(
                    "'tracker_cutover_at' must be an ISO 8601 datetime string or null"
                )

        for key, value in fields.items():
            setattr(project, key, value)

        self._save()
        return project

    def delete(self, project_id: str) -> bool:
        if project_id in self._projects:
            del self._projects[project_id]
            self._save()
            return True
        return False

    # -- Startup sync --

    def sync_project_sources(
        self,
        project_id: str,
        timeout_s: float = DEFAULT_SOURCE_SYNC_TIMEOUT_S,
    ) -> dict[str, str]:
        """Pull latest code and (for legacy Backlog projects) check compatibility.

        Best-effort: any failure is logged and recorded in the returned
        status dict but does NOT raise. The orchestrator should boot
        even if a project's network is flaky — it just operates on
        whatever local state exists.

        **Tracker-aware behaviour:**

        * For *all* projects: git self-heal (``ensure_repo_sound``) runs so
          the checkout stays on the correct branch and tracks origin.
        * For **legacy Backlog projects** (``tracker_kind`` is ``None`` or
          ``"backlog"``): Backlog.md config compatibility checks and Backlog
          task-file conflict repair/quarantine also run.
        * For **GitHub-backed projects** (``tracker_kind="github_issues"``):
          Backlog compatibility and conflict repair are skipped — GitHub is the
          source of truth.  A ``"tracker": "github_issues"`` key is added to
          the returned status dict.

        After a successful git pull on a legacy project, inspects backlog task
        files for git conflict markers.  For conflicts limited to backlog task
        files, a deterministic structured repair is attempted (see
        :mod:`oompah.backlog_conflict`).  If repair is not safe, the
        project is quarantined (``paused=True``) and the conflicted file
        paths are stored on the project so the dashboard can surface an
        alert.

        Returns ``{"git": "ok"|"reset:ok"|"failed: <reason>"|"skipped: <reason>",
                  "backlog": "ok"|"migrated"|"failed: <reason>"|"skipped: <reason>",
                  "conflicts": "none"|"repaired:<n>"|"quarantined:<paths>"|"skipped: <reason>",
                  "tracker": "github_issues"  # only present for GitHub-backed projects
                  }``.
        """
        from oompah.backlog_conflict import (
            ensure_repo_sound,
            repair_repo_backlog_conflicts,
        )

        project = self._projects.get(project_id)
        if not project:
            return {
                "git": "skipped: unknown project",
                "backlog": "skipped: unknown project",
                "conflicts": "skipped: unknown project",
            }

        github_backed = _is_github_backed(project)
        status: dict[str, str] = {}
        if github_backed:
            status["tracker"] = "github_issues"

        # Paths ensure_repo_sound() could not heal — fed into the quarantine
        # decision below so an un-healable checkout is loud, never silent.
        unmerged_failed: list[str] = []

        # Aggressively drive the checkout back to a sound state: abort stranded
        # merges/rebases, clear colliding untracked files, recover unmerged
        # entries, repair conflict markers, return to the default branch, and
        # fast-forward to origin — hard-resetting to origin as a last resort
        # when no unpushed code work would be lost. This runs every sync (not
        # just at boot) so a checkout can't silently drift/wedge between
        # restarts.  This step is tracker-agnostic — it always runs.
        if not project.repo_path or not os.path.isdir(
            os.path.join(project.repo_path, ".git")
        ):
            status["git"] = "skipped: no .git"
        else:
            try:
                heal = ensure_repo_sound(project.repo_path, project.default_branch)
                if heal.get("sound"):
                    status["git"] = "reset:ok" if heal.get("reset") else "ok"
                else:
                    status["git"] = "failed: not sound after heal"
                    unmerged_failed = list(heal.get("unrecoverable", []))
                if heal.get("actions"):
                    status["heal"] = ",".join(heal["actions"])
                    logger.info(
                        "Self-heal on %s: %s (sound=%s)",
                        project.name,
                        ",".join(heal["actions"]),
                        heal.get("sound"),
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
                status["git"] = f"failed: {exc}"
                logger.warning(
                    "Self-heal git ops failed for %s: %s",
                    project.name,
                    exc,
                )

        # Backlog.md compatibility checks and conflict repair are only relevant
        # for legacy Backlog projects.  GitHub-backed projects skip both steps
        # because GitHub Issues is the authoritative task store and there are no
        # Backlog task files to validate or repair.
        if github_backed:
            status["backlog"] = "skipped: github_issues"
            status["conflicts"] = "skipped: github_issues"
            return status

        try:
            compat = ensure_backlog_compatible(project.repo_path)
            status["backlog"] = "migrated" if compat.changed else "ok"
        except BacklogCompatibilityError as exc:
            status["backlog"] = f"failed: {exc}"
            logger.warning("Backlog compatibility check failed for %s: %s", project.name, exc)

        # Inspect and repair Backlog task file conflicts.
        # This runs unconditionally (not gated on git success) because
        # conflicts may already exist from a previous run's stash collision.
        if project.repo_path and os.path.isdir(project.repo_path):
            try:
                repair_result = repair_repo_backlog_conflicts(project.repo_path)
                repaired = repair_result.get("repaired", [])
                failed = list(repair_result.get("failed", []))
                # Unmerged-index entries that recovery could NOT resolve are
                # also unrepairable conflicts — quarantine on them too so the
                # checkout never silently stalls behind origin.
                for p in unmerged_failed:
                    if p not in failed:
                        failed.append(p)
                if repaired or failed:
                    # Log repair summary
                    if repaired:
                        logger.info(
                            "Auto-repaired %d backlog conflict(s) in %s: %s",
                            len(repaired),
                            project.name,
                            ", ".join(os.path.basename(p) for p in repaired[:5]),
                        )
                    if failed:
                        logger.warning(
                            "Could not repair %d backlog conflict(s) in %s: %s",
                            len(failed),
                            project.name,
                            ", ".join(os.path.basename(p) for p in failed[:5]),
                        )
                    # Quarantine project if any conflicts remain unrepairable
                    if failed:
                        # Pause the project so no tasks are dispatched until
                        # the operator resolves the remaining conflicts.
                        failed_basenames = [os.path.basename(p) for p in failed]
                        status["conflicts"] = (
                            f"quarantined:{','.join(failed_basenames)}"
                        )
                        self.update(
                            project_id,
                            paused=True,
                            backlog_conflict_paths=list(failed),
                        )
                        logger.warning(
                            "Project %s quarantined due to unresolvable backlog "
                            "conflicts. Repair or remove: %s",
                            project.name,
                            ", ".join(failed),
                        )
                    else:
                        # All conflicts repaired — clear any previous quarantine
                        status["conflicts"] = f"repaired:{len(repaired)}"
                        if project.backlog_conflict_paths:
                            self.update(
                                project_id,
                                paused=False,
                                backlog_conflict_paths=[],
                            )
                            logger.info(
                                "Project %s conflict quarantine cleared after "
                                "successful repair.",
                                project.name,
                            )
                else:
                    # No conflicts — clear any stale quarantine from a previous run
                    if project.backlog_conflict_paths:
                        self.update(
                            project_id,
                            paused=False,
                            backlog_conflict_paths=[],
                        )
                        logger.info(
                            "Project %s stale conflict quarantine cleared "
                            "(no conflicts detected).",
                            project.name,
                        )
                    status["conflicts"] = "none"
            except Exception as exc:
                logger.warning(
                    "Backlog conflict inspection failed for %s: %s",
                    project.name,
                    exc,
                )
                status["conflicts"] = f"failed: {exc}"
        else:
            status["conflicts"] = "skipped: no repo"

        return status

    def sync_all_sources(
        self,
        timeout_s: float = DEFAULT_SOURCE_SYNC_TIMEOUT_S,
        max_workers: int = 4,
    ) -> dict[str, dict[str, str]]:
        """Run :meth:`sync_project_sources` for every project in parallel.

        Returns a mapping of project_id → status dict. Never raises.
        """
        projects = list(self._projects.values())
        if not projects:
            return {}
        results: dict[str, dict[str, str]] = {}
        workers = min(len(projects), max_workers)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self.sync_project_sources, p.id, timeout_s): p
                for p in projects
            }
            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    results[p.id] = fut.result()
                except Exception as exc:
                    logger.warning(
                        "sync_all_sources: project %s raised: %s",
                        p.name,
                        exc,
                    )
                    results[p.id] = {
                        "git": f"exception: {exc}",
                        "backlog": f"exception: {exc}",
                    }
        return results

    # -- Worktree helpers --

    def worktree_path_for(self, project_id: str, issue_identifier: str) -> str:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        sanitized = _sanitize_identifier(issue_identifier)
        return os.path.join(
            self.worktree_root, _sanitize_identifier(project.name), sanitized
        )

    def epic_worktree_path_for(self, project_id: str, epic_identifier: str) -> str:
        """Path used for the shared epic worktree under epic_strategy='shared'.

        Lives at ``<worktree_root>/<project>/epic-<epic_identifier>`` so it
        can never collide with a per-bead worktree (which uses just the
        bead identifier). The branch name on the worktree mirrors the
        directory name (also ``epic-<epic_identifier>``).
        """
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        sanitized = _sanitize_identifier(epic_identifier)
        return os.path.join(
            self.worktree_root,
            _sanitize_identifier(project.name),
            f"epic-{sanitized}",
        )

    def epic_branch_name(self, epic_identifier: str) -> str:
        """Branch name used for the shared epic branch (shared/stacked modes).

        Must match :meth:`epic_worktree_path_for`'s last segment so that
        ``git worktree add`` and ``git push`` see the same name.
        """
        return f"epic-{_sanitize_identifier(epic_identifier)}"

    def create_epic_worktree(self, project_id: str, epic_identifier: str) -> str:
        """Create or reuse a shared epic worktree (for ``epic_strategy='shared'``
        and the long-lived epic branch under ``epic_strategy='stacked'``).

        The worktree path is ``<worktree_root>/<project>/epic-<epic_id>``
        and the branch is ``epic-<epic_id>``. Idempotent: if the worktree
        already exists it is repaired (fetch, hard reset only if it sits
        on the wrong branch — keeps in-flight commits from previous
        agents on the shared branch).
        """
        # Acquire per-project lock to serialize concurrent epic worktree
        # create/remove operations for the same project.
        with self.project_write_lock(project_id):
            return self._create_epic_worktree_locked(project_id, epic_identifier)

    def _create_epic_worktree_locked(self, project_id: str, epic_identifier: str) -> str:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        wt_path = self.epic_worktree_path_for(project_id, epic_identifier)
        branch_name = self.epic_branch_name(epic_identifier)

        if os.path.isdir(wt_path):
            logger.info("Epic worktree already exists path=%s", wt_path)
            self._prepare_existing_epic_worktree(wt_path, branch_name, project)
            return wt_path

        os.makedirs(os.path.dirname(wt_path), exist_ok=True)

        # Fetch latest from remote before creating the worktree so we
        # pick up an existing remote epic branch from a prior session.
        try:
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass  # best-effort

        # Prefer to attach to an existing origin branch (so a previous
        # session's epic work is preserved). Fall back to creating a new
        # branch off the project's default branch.
        remote_ref = f"origin/{branch_name}"
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--verify", remote_ref],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            remote_exists = r.returncode == 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            remote_exists = False

        try:
            if remote_exists:
                _git_worktree_add_with_recovery(
                    ["git", "worktree", "add", "-B", branch_name, wt_path, remote_ref],
                    cwd=project.repo_path,
                    wt_path=wt_path,
                )
            else:
                base = f"origin/{project.default_branch}"
                _git_worktree_add_with_recovery(
                    ["git", "worktree", "add", "-b", branch_name, wt_path, base],
                    cwd=project.repo_path,
                    wt_path=wt_path,
                )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()[:500] if exc.stderr else ""
            # Branch exists locally but no remote — reuse the existing branch
            if "already exists" in stderr or "already used by worktree at" in stderr:
                try:
                    _git_worktree_add_with_recovery(
                        ["git", "worktree", "add", wt_path, branch_name],
                        cwd=project.repo_path,
                        wt_path=wt_path,
                    )
                except subprocess.CalledProcessError as exc2:
                    stderr2 = exc2.stderr.strip()[:500] if exc2.stderr else ""
                    raise ProjectError(f"git worktree add failed: {stderr2}")
            # Branch checked out in another worktree — reuse the existing branch
            # by attaching our worktree path to it (no -b/-B flag, avoids conflict).
            elif _is_worktree_branch_already_used_error(stderr):
                try:
                    _git_worktree_add_with_recovery(
                        ["git", "worktree", "add", wt_path, branch_name],
                        cwd=project.repo_path,
                        wt_path=wt_path,
                    )
                except subprocess.CalledProcessError as exc2:
                    stderr2 = exc2.stderr.strip()[:500] if exc2.stderr else ""
                    raise ProjectError(f"git worktree add failed: {stderr2}")
            else:
                raise ProjectError(f"git worktree add failed: {stderr}")
        except subprocess.TimeoutExpired:
            raise ProjectError("git worktree add timed out")

        # Set git identity on the worktree from project config (mirrors
        # create_worktree() so child agents use the same author).
        if project.git_user_name:
            try:
                subprocess.run(
                    ["git", "config", "user.name", project.git_user_name],
                    cwd=wt_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except Exception:
                pass
        if project.git_user_email:
            try:
                subprocess.run(
                    ["git", "config", "user.email", project.git_user_email],
                    cwd=wt_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except Exception:
                pass

        self._disable_worktree_hooks(wt_path)
        logger.info("Epic worktree created path=%s branch=%s", wt_path, branch_name)
        return wt_path

    def _prepare_existing_epic_worktree(
        self,
        wt_path: str,
        branch_name: str,
        project: Project,
    ) -> None:
        """Soft-prepare an existing epic worktree for reuse.

        Unlike ``_prepare_existing_worktree`` (which hard-resets the
        per-bead worktree), this one preserves any in-flight commits on
        the shared epic branch so a previous child's work isn't lost.
        We still fetch, ensure the branch is checked out, and disable
        hooks; we do NOT ``git reset --hard`` or ``git clean``.
        """

        def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                cwd=wt_path,
                capture_output=True,
                text=True,
                timeout=30,
                **kw,
            )

        try:
            _run(["git", "fetch", "origin"])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        try:
            r = _run(["git", "symbolic-ref", "--short", "HEAD"])
            current_branch = r.stdout.strip() if r.returncode == 0 else ""
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            current_branch = ""

        if current_branch != branch_name:
            try:
                _run(["git", "checkout", branch_name], check=True)
                logger.info(
                    "Checked out epic branch %s in worktree %s",
                    branch_name,
                    wt_path,
                )
            except subprocess.CalledProcessError as exc:
                logger.warning(
                    "Failed to checkout epic branch %s in %s: %s",
                    branch_name,
                    wt_path,
                    exc.stderr.strip()[:200] if exc.stderr else "",
                )

        self._disable_worktree_hooks(wt_path)

    def remove_epic_worktree(self, project_id: str, epic_identifier: str) -> None:
        """Remove the shared epic worktree (used after the epic→main PR
        merges or when the operator deletes a project).

        Mirrors :meth:`remove_worktree` but with the epic-named directory
        and a tolerant fall-through when the worktree no longer exists.
        """
        # Acquire per-project lock so concurrent remove operations are serialized.
        with self.project_write_lock(project_id):
            self._remove_epic_worktree_locked(project_id, epic_identifier)

    def _remove_epic_worktree_locked(self, project_id: str, epic_identifier: str) -> None:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        wt_path = self.epic_worktree_path_for(project_id, epic_identifier)
        if not os.path.isdir(wt_path):
            return

        try:
            subprocess.run(
                ["git", "worktree", "remove", wt_path, "--force"],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()[:500] if exc.stderr else ""
            raise ProjectError(f"git worktree remove failed: {stderr}")
        except subprocess.TimeoutExpired:
            raise ProjectError("git worktree remove timed out")
        logger.info("Epic worktree removed path=%s", wt_path)

    def create_worktree(
        self,
        project_id: str,
        issue_identifier: str,
        base_branch: str | None = None,
        branch_name: str | None = None,
    ) -> str:
        """Create (or reuse) a git worktree for ``issue_identifier``.

        Parameters
        ----------
        project_id:
            Registered project ID.
        issue_identifier:
            Stable issue identifier used to derive the worktree path.
        base_branch:
            Remote branch to base the new local branch on.  Defaults to the
            project's ``default_branch``.
        branch_name:
            Explicit git branch name for the worktree.  When provided (e.g.
            a GitHub-safe name like ``oompah/myproject/gh-1234``), it is used
            verbatim instead of the sanitized ``issue_identifier``.  Defaults
            to ``_sanitize_identifier(issue_identifier)`` when ``None``.
        """
        # Acquire the per-project lock so concurrent dispatch and maintenance
        # operations for the same project are serialized through git.  The lock
        # is reentrant so callers that already hold it (e.g. dispatch holding
        # the lock across a tracker write + worktree create) do not deadlock.
        with self.project_write_lock(project_id):
            return self._create_worktree_locked(
                project_id, issue_identifier, base_branch, branch_name
            )

    def _create_worktree_locked(
        self,
        project_id: str,
        issue_identifier: str,
        base_branch: str | None = None,
        branch_name: str | None = None,
    ) -> str:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        wt_path = self.worktree_path_for(project_id, issue_identifier)
        # Use the caller-supplied branch name (e.g. GitHub-safe
        # ``oompah/<slug>/gh-<n>``) when provided; fall back to the
        # sanitized identifier for legacy Backlog-backed tasks.
        branch_name = branch_name or _sanitize_identifier(issue_identifier)

        if os.path.isdir(wt_path):
            logger.info("Worktree already exists path=%s", wt_path)
            self._prepare_existing_worktree(wt_path, branch_name, project)
            return wt_path

        os.makedirs(os.path.dirname(wt_path), exist_ok=True)

        # Fetch latest from remote before creating worktree
        try:
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass  # best-effort

        # Create worktree on a new branch based on the specified base branch,
        # or the project's default_branch if not specified.
        # _git_worktree_add_with_recovery handles transient .git/config lock
        # contention (oompah-zlz_2-7iq) by either accepting partial success
        # (worktree dir created, only upstream-config write failed) or
        # retrying with exponential backoff.
        base = f"origin/{base_branch or project.default_branch}"
        try:
            _git_worktree_add_with_recovery(
                ["git", "worktree", "add", "-b", branch_name, wt_path, base],
                cwd=project.repo_path,
                wt_path=wt_path,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()[:500] if exc.stderr else ""
            # Branch may already exist from a previous run — try reusing it
            if "already exists" in stderr or "already used by worktree at" in stderr:
                try:
                    _git_worktree_add_with_recovery(
                        ["git", "worktree", "add", wt_path, branch_name],
                        cwd=project.repo_path,
                        wt_path=wt_path,
                    )
                except subprocess.CalledProcessError as exc2:
                    stderr2 = exc2.stderr.strip()[:500] if exc2.stderr else ""
                    raise ProjectError(f"git worktree add failed: {stderr2}")
            # Branch checked out in another worktree — reuse the existing branch
            # by attaching our worktree path to it (no -b/-B flag, avoids conflict).
            elif _is_worktree_branch_already_used_error(stderr):
                try:
                    _git_worktree_add_with_recovery(
                        ["git", "worktree", "add", wt_path, branch_name],
                        cwd=project.repo_path,
                        wt_path=wt_path,
                    )
                except subprocess.CalledProcessError as exc2:
                    stderr2 = exc2.stderr.strip()[:500] if exc2.stderr else ""
                    raise ProjectError(f"git worktree add failed: {stderr2}")
            else:
                raise ProjectError(f"git worktree add failed: {stderr}")
        except subprocess.TimeoutExpired:
            raise ProjectError("git worktree add timed out")

        # Set git identity on the worktree from project config
        if project.git_user_name:
            try:
                subprocess.run(
                    ["git", "config", "user.name", project.git_user_name],
                    cwd=wt_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except Exception:
                pass
        if project.git_user_email:
            try:
                subprocess.run(
                    ["git", "config", "user.email", project.git_user_email],
                    cwd=wt_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except Exception:
                pass

        self._disable_worktree_hooks(wt_path)

        logger.info("Worktree created path=%s branch=%s", wt_path, branch_name)
        return wt_path

    def sync_task_file_to_worktree(
        self,
        project_id: str,
        issue_identifier: str,
        wt_path: str,
        preserve_statuses: "frozenset[str] | set[str] | None" = None,
    ) -> bool:
        """Copy the current Backlog task markdown into an agent worktree.

        ``preserve_statuses`` guards against regressing agent-owned
        progress: when the worktree's existing task file already records
        a status in this set (e.g. terminal states like ``Done`` /
        ``Merged``), that status is preserved in the synced file rather
        than being overwritten by the (possibly stale) source copy.

        This matters for ``epic_strategy='shared'`` children: they live
        on a persistent epic branch and write ``status: Done`` there, but
        the source-of-truth main checkout still shows ``Open`` until the
        epic→main PR lands. Without this guard, every re-dispatch copied
        the stale ``Open`` over the agent's ``Done``, causing an infinite
        re-dispatch loop (the child never appeared complete).
        """
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        if not os.path.isdir(wt_path):
            raise ProjectError(f"Worktree path does not exist: {wt_path}")

        source_path = next(
            (
                path
                for path in _backlog_task_files(project.repo_path)
                if _task_file_matches(path, issue_identifier)
            ),
            None,
        )
        if not source_path:
            logger.debug(
                "No Backlog task file found to sync project=%s issue=%s",
                project_id,
                issue_identifier,
            )
            return False

        # Capture the worktree copy's status BEFORE deleting it, so we can
        # avoid regressing an agent-owned advanced status (e.g. Done).
        preserved_status: str | None = None
        norm_preserve = (
            {s.strip().lower() for s in preserve_statuses}
            if preserve_statuses
            else set()
        )
        for stale_path in _backlog_task_files(wt_path):
            if _task_file_matches(stale_path, issue_identifier):
                if norm_preserve and preserved_status is None:
                    wt_status = _task_file_status(stale_path)
                    src_status = _task_file_status(source_path)
                    if (
                        wt_status
                        and wt_status.strip().lower() in norm_preserve
                        and (src_status or "").strip().lower()
                        != wt_status.strip().lower()
                    ):
                        preserved_status = wt_status
                try:
                    os.remove(stale_path)
                except OSError as exc:
                    raise ProjectError(f"Failed to remove stale task file: {exc}")

        rel_path = os.path.relpath(source_path, project.repo_path)
        target_path = os.path.join(wt_path, rel_path)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        try:
            shutil.copy2(source_path, target_path)
        except OSError as exc:
            raise ProjectError(f"Failed to sync task file: {exc}")

        if preserved_status is not None:
            if not self._rewrite_task_status(target_path, preserved_status):
                logger.warning(
                    "Could not preserve worktree status %r for %s; "
                    "synced file may regress progress",
                    preserved_status,
                    issue_identifier,
                )
            else:
                logger.info(
                    "Preserved worktree status %r over stale source for "
                    "project=%s issue=%s",
                    preserved_status,
                    project_id,
                    issue_identifier,
                )

        logger.info(
            "Synced task file to worktree project=%s issue=%s path=%s",
            project_id,
            issue_identifier,
            target_path,
        )
        return True

    def read_task_status_in_epic_worktree(
        self,
        project_id: str,
        epic_identifier: str,
        issue_identifier: str,
    ) -> str | None:
        """Return a child task's ``status:`` as recorded in the shared
        epic worktree's Backlog copy, or None if the worktree or task
        file doesn't exist.

        Shared-epic children write their status to the persistent epic
        branch, not the main checkout. The dispatch loop reads status
        from main (which lags until the epic lands), so it needs this to
        tell whether a child is already complete on the epic branch.
        """
        if not self._projects.get(project_id):
            return None
        wt_path = self.epic_worktree_path_for(project_id, epic_identifier)
        if not os.path.isdir(wt_path):
            return None
        path = next(
            (
                p
                for p in _backlog_task_files(wt_path)
                if _task_file_matches(p, issue_identifier)
            ),
            None,
        )
        if not path:
            return None
        return _task_file_status(path)

    @staticmethod
    def _rewrite_task_status(path: str, status: str) -> bool:
        """Rewrite the ``status:`` frontmatter line of *path* to *status*.

        Returns True on success. Best-effort: only touches the first
        ``status:`` line inside the leading ``---`` frontmatter block.
        """
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return False
        if not content.startswith("---"):
            return False
        end = content.find("\n---", 3)
        if end < 0:
            return False
        head = content[: end]
        tail = content[end:]
        new_head, n = re.subn(
            r"(?m)^(status:).*$",
            lambda m: f"{m.group(1)} {status}",
            head,
            count=1,
        )
        if n == 0:
            # No status line in frontmatter — insert one just after the
            # opening fence.
            new_head = head.replace("---", f"---\nstatus: {status}", 1)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_head + tail)
        except OSError:
            return False
        return True

    def _prepare_existing_worktree(
        self,
        wt_path: str,
        branch_name: str,
        project: Project,
    ) -> None:
        """Ensure an existing worktree is on the correct branch with a clean state."""

        def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd,
                cwd=wt_path,
                capture_output=True,
                text=True,
                timeout=30,
                **kw,
            )

        # Fetch latest from remote
        try:
            _run(["git", "fetch", "origin"])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        # Discard any uncommitted changes from previous runs
        try:
            _run(["git", "reset", "--hard"])
            _run(["git", "clean", "-fd"])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        # If HEAD is detached or on the wrong branch, check out the issue branch
        try:
            r = _run(["git", "symbolic-ref", "--short", "HEAD"])
            current_branch = r.stdout.strip() if r.returncode == 0 else ""
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            current_branch = ""

        if current_branch != branch_name:
            try:
                _run(["git", "checkout", branch_name], check=True)
                logger.info(
                    "Checked out branch %s in worktree %s", branch_name, wt_path
                )
            except subprocess.CalledProcessError as exc:
                logger.warning(
                    "Failed to checkout branch %s in worktree %s: %s",
                    branch_name,
                    wt_path,
                    exc.stderr.strip()[:200] if exc.stderr else "",
                )

        self._disable_worktree_hooks(wt_path)

    def _disable_worktree_hooks(self, wt_path: str) -> None:
        """Point worktree hooks to oompah's isolated hook directory.

        The redirected hooks directory is NOT empty: we install the oompah
        ``prepare-commit-msg`` hook into it so every commit produced by an
        agent picks up the canonical oompah attribution trailer (see
        :mod:`oompah.git_hooks` and oompah-zlz_2-3cpz).
        """
        try:
            hooks_dir = os.path.join(wt_path, ".oompah-no-hooks")
            os.makedirs(hooks_dir, exist_ok=True)
            subprocess.run(
                ["git", "config", "core.hooksPath", hooks_dir],
                cwd=wt_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            pass
        # Best-effort install of the prepare-commit-msg hook. Failures here
        # must never block worktree creation — agents can still commit, the
        # trailer just won't be auto-enforced.
        try:
            _install_prepare_commit_msg_hook(wt_path)
        except Exception:  # pragma: no cover - defensive
            logger.warning(
                "Failed to install prepare-commit-msg hook in %s",
                wt_path,
                exc_info=True,
            )

    def remove_worktree(self, project_id: str, issue_identifier: str) -> None:
        # Acquire the per-project lock so concurrent dispatch and maintenance
        # operations (e.g. self-heal removing a worktree while dispatch creates
        # one) for the same project are serialized.
        with self.project_write_lock(project_id):
            self._remove_worktree_locked(project_id, issue_identifier)

    def _remove_worktree_locked(self, project_id: str, issue_identifier: str) -> None:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        wt_path = self.worktree_path_for(project_id, issue_identifier)
        if not os.path.isdir(wt_path):
            return

        try:
            subprocess.run(
                ["git", "worktree", "remove", wt_path, "--force"],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()[:500] if exc.stderr else ""
            raise ProjectError(f"git worktree remove failed: {stderr}")
        except subprocess.TimeoutExpired:
            raise ProjectError("git worktree remove timed out")

        logger.info("Worktree removed path=%s", wt_path)

    def list_worktrees(self, project_id: str) -> list[str]:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        wt_root = os.path.join(self.worktree_root, _sanitize_identifier(project.name))
        if not os.path.isdir(wt_root):
            return []

        paths = []
        for entry in sorted(os.listdir(wt_root)):
            full = os.path.join(wt_root, entry)
            if os.path.isdir(full):
                paths.append(full)
        return paths
