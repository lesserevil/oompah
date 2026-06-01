"""Project storage and git worktree management."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def _sanitize_identifier(value: str) -> str:
    """Make a project or task identifier safe for local branch/path names."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned.strip("._-") or "unnamed"


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
        """Pull latest code and ensure Backlog.md config compatibility.

        Best-effort: any failure is logged and recorded in the returned
        status dict but does NOT raise. The orchestrator should boot
        even if a project's network is flaky — it just operates on
        whatever local state exists.

        Returns ``{"git": "ok"|"failed: <reason>"|"skipped: <reason>",
                  "backlog": "ok"|"migrated"|"failed: <reason>"}``.
        """
        project = self._projects.get(project_id)
        if not project:
            return {
                "git": "skipped: unknown project",
                "backlog": "skipped: unknown project",
            }
        status: dict[str, str] = {}

        # git fetch + ff-only pull on the project's tracked branch.
        if not project.repo_path or not os.path.isdir(
            os.path.join(project.repo_path, ".git")
        ):
            status["git"] = "skipped: no .git"
        else:
            try:
                subprocess.run(
                    ["git", "fetch", "origin"],
                    cwd=project.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
                pull = subprocess.run(
                    [
                        "git",
                        "pull",
                        "--ff-only",
                        "--autostash",
                        "origin",
                        project.default_branch,
                    ],
                    cwd=project.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                )
                if pull.returncode == 0:
                    status["git"] = "ok"
                else:
                    stderr = (pull.stderr or "").strip()[:200]
                    status["git"] = f"failed: {stderr}"
                    logger.warning(
                        "Startup git pull failed for %s: %s",
                        project.name,
                        stderr,
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
                status["git"] = f"failed: {exc}"
                logger.warning(
                    "Startup git fetch/pull failed for %s: %s",
                    project.name,
                    exc,
                )

        try:
            compat = ensure_backlog_compatible(project.repo_path)
            status["backlog"] = "migrated" if compat.changed else "ok"
        except BacklogCompatibilityError as exc:
            status["backlog"] = f"failed: {exc}"
            logger.warning("Backlog compatibility check failed for %s: %s", project.name, exc)

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
        self, project_id: str, issue_identifier: str, base_branch: str | None = None
    ) -> str:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        wt_path = self.worktree_path_for(project_id, issue_identifier)
        branch_name = _sanitize_identifier(issue_identifier)

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
