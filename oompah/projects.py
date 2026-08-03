"""Project storage and git worktree management."""

from __future__ import annotations

import hashlib
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
from fnmatch import fnmatchcase
from urllib.parse import urlsplit

from oompah.git_credentials import git_credential_environment, redact_git_output
from oompah.git_hooks import hook_path as _bundled_hook_path
from oompah.git_noninteractive import NONINTERACTIVE_GIT_ENV
from oompah.models import Project
from oompah.repo_health import ensure_repo_sound
from oompah.secrets import register_secret_values

logger = logging.getLogger(__name__)

DEFAULT_PROJECTS_PATH = ".oompah/projects.json"
DEFAULT_REPOS_ROOT = os.path.expanduser("~/.oompah/repos")
DEFAULT_WORKTREE_ROOT = os.path.expanduser("~/.oompah/worktrees")
DEFAULT_SOURCE_SYNC_TIMEOUT_S = 45.0


class ProjectError(Exception):
    """Raised when project registration or worktree management fails."""


_WORKTREE_RECOVERY_VERSION = 1
_WORKTREE_RECOVERY_MARKER = "oompah-recovery-json:"
_RECOVERY_METADATA_LIMIT = 64 * 1024


def _is_generated_worktree_helper(path: str) -> bool:
    """Return whether *path* names an Oompah-owned worktree artifact.

    Worktree helpers are deliberately kept at the worktree root and use the
    ``.oompah-`` namespace.  The namespace rule covers the hook directory and
    future generated helpers without treating the tracked ``.oompah/tasks``
    tree as disposable task output.
    """

    normalized = str(path or "").replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    root = normalized.split("/", 1)[0]
    return root.startswith(".oompah-")


def is_generated_worktree_helper(path: str) -> bool:
    """Return whether a relative path is an Oompah-generated helper."""

    return _is_generated_worktree_helper(path)


def _generated_worktree_helper_paths(wt_path: str) -> list[str]:
    """List generated helper paths without asking Git to expose ignored files."""

    paths: list[str] = []
    if not os.path.isdir(wt_path):
        return paths
    try:
        children = list(os.scandir(wt_path))
    except OSError:
        return paths
    for child in children:
        if not _is_generated_worktree_helper(child.name):
            continue
        if child.is_dir(follow_symlinks=False) and not child.is_symlink():
            found = False
            for root, _dirs, files in os.walk(child.path, followlinks=False):
                for name in files:
                    found = True
                    relative = os.path.relpath(os.path.join(root, name), wt_path)
                    paths.append(relative.replace(os.sep, "/"))
            if not found:
                paths.append(child.name)
        else:
            paths.append(child.name)
    return sorted(dict.fromkeys(paths))


def generated_worktree_helpers_in_revision(
    repo_path: str,
    revision: str,
) -> list[str]:
    """Return Oompah-generated helper paths tracked by *revision*.

    Worktree-local helpers are intentionally ignored by normal status and
    cleanup code.  That is safe for the working tree, but a legacy task head
    can still have committed one.  Delivery callers use this check before
    resetting or merging a shared worktree so an ignored helper can never be
    promoted into a delivered tree.
    """

    try:
        result = subprocess.run(
            ["git", "-C", repo_path, "ls-tree", "-r", "--name-only", revision],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env={**os.environ, **NONINTERACTIVE_GIT_ENV},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProjectError(
            f"could not inspect generated helpers in {revision}: {exc}"
        ) from exc
    if result.returncode != 0:
        raise ProjectError(
            "could not inspect generated helpers in "
            f"{revision}: {result.stderr.strip()[:500]}"
        )
    return [
        path
        for path in result.stdout.splitlines()
        if _is_generated_worktree_helper(path)
    ]


def remove_generated_worktree_helpers(wt_path: str) -> list[str]:
    """Remove only generated Oompah helpers from one exact worktree.

    This is intentionally limited to direct children of *wt_path*.  Callers
    must invoke it only after task-owned changes have been durably snapshotted;
    it never removes arbitrary ignored files or nested task content.
    """

    removed: list[str] = []
    if not os.path.isdir(wt_path):
        return removed
    try:
        children = list(os.scandir(wt_path))
    except OSError:
        return removed
    for child in children:
        if not _is_generated_worktree_helper(child.name):
            continue
        try:
            if child.is_dir(follow_symlinks=False) and not child.is_symlink():
                shutil.rmtree(child.path)
            else:
                os.unlink(child.path)
        except OSError:
            logger.warning(
                "recovery generated-helper cleanup failed path=%s",
                child.path,
                exc_info=True,
            )
            continue
        removed.append(child.name)
    if removed:
        logger.info(
            "recovery generated-helper exclusion removed helpers path=%s helpers=%s",
            wt_path,
            sorted(removed),
        )
    return removed


def _read_recovery_metadata(path: str) -> str:
    """Read a bounded Git operation metadata file for recovery evidence."""

    try:
        with open(path, "r", encoding="utf-8", errors="surrogateescape") as fh:
            return fh.read(_RECOVERY_METADATA_LIMIT)
    except (OSError, UnicodeError):
        return ""


def _recovery_git_env() -> dict[str, str]:
    """Return the process environment with Git prompts disabled."""

    env = dict(os.environ)
    env.update(NONINTERACTIVE_GIT_ENV)
    return env


def _worktree_git_dir(wt_path: str) -> str | None:
    """Resolve the per-worktree Git directory without invoking a prompt."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env=_recovery_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    git_dir = result.stdout.strip()
    if not os.path.isabs(git_dir):
        git_dir = os.path.join(wt_path, git_dir)
    return os.path.realpath(git_dir)


def _git_operation_state(
    wt_path: str,
    *,
    current_branch: str = "",
    branch_result_code: int = 0,
) -> dict[str, object] | None:
    """Inspect paused Git operations without changing the worktree.

    Rebase state lives in the worktree's private Git directory, while merge,
    cherry-pick, and sequencer markers may be placed in the common directory by
    older Git versions.  We inspect both locations and only read metadata.  In
    particular, this helper never runs ``rebase --continue`` or another
    operation that could consume conflict resolutions.
    """

    git_dir = _worktree_git_dir(wt_path)
    if not git_dir:
        return None
    git_dirs = [git_dir]
    commondir_file = os.path.join(git_dir, "commondir")
    try:
        common = _read_recovery_metadata(commondir_file).strip()
    except Exception:  # pragma: no cover - defensive filesystem guard
        common = ""
    if common:
        common_dir = common if os.path.isabs(common) else os.path.join(git_dir, common)
        common_dir = os.path.realpath(common_dir)
        if common_dir not in git_dirs:
            git_dirs.append(common_dir)

    rebase_dir = next(
        (
            os.path.join(candidate, name)
            for candidate in git_dirs
            for name in ("rebase-merge", "rebase-apply")
            if os.path.isdir(os.path.join(candidate, name))
        ),
        None,
    )
    marker_names = (
        ("rebase", rebase_dir),
        ("merge", next(
            (
                os.path.join(candidate, "MERGE_HEAD")
                for candidate in git_dirs
                if os.path.isfile(os.path.join(candidate, "MERGE_HEAD"))
            ),
            None,
        )),
        ("cherry-pick", next(
            (
                os.path.join(candidate, "CHERRY_PICK_HEAD")
                for candidate in git_dirs
                if os.path.isfile(os.path.join(candidate, "CHERRY_PICK_HEAD"))
            ),
            None,
        )),
        ("revert", next(
            (
                os.path.join(candidate, "REVERT_HEAD")
                for candidate in git_dirs
                if os.path.isfile(os.path.join(candidate, "REVERT_HEAD"))
            ),
            None,
        )),
        ("sequencer", next(
            (
                os.path.join(candidate, "sequencer")
                for candidate in git_dirs
                if os.path.isdir(os.path.join(candidate, "sequencer"))
            ),
            None,
        )),
    )
    active_kind, state_path = next(
        ((kind, path) for kind, path in marker_names if path),
        (None, None),
    )
    if not active_kind or not state_path:
        return None

    metadata: dict[str, str] = {}
    if active_kind == "rebase":
        names = (
            "head-name",
            "onto",
            "orig-head",
            "git-rebase-todo",
            "done",
            "msgnum",
            "end",
            "stopped-sha",
            "rewritten-list",
        )
        for name in names:
            metadata_path = os.path.join(state_path, name)
            if os.path.isfile(metadata_path):
                metadata[name] = _read_recovery_metadata(metadata_path)
        for candidate in git_dirs:
            value = _read_recovery_metadata(os.path.join(candidate, "REBASE_HEAD"))
            if value:
                metadata["REBASE_HEAD"] = value
                break
        raw_branch = metadata.get("head-name", "").strip()
        operation_branch = (
            raw_branch[len("refs/heads/") :]
            if raw_branch.startswith("refs/heads/")
            else raw_branch
        )
    else:
        operation_branch = current_branch
        if os.path.isfile(state_path):
            metadata[os.path.basename(state_path)] = _read_recovery_metadata(state_path)
        elif active_kind == "sequencer":
            for name in ("head", "onto", "todo", "done", "opts", "abort-safety"):
                metadata_path = os.path.join(state_path, name)
                if os.path.isfile(metadata_path):
                    metadata[name] = _read_recovery_metadata(metadata_path)

    return {
        "kind": active_kind,
        "git_dir": git_dir,
        "state_path": state_path,
        "branch": operation_branch or current_branch,
        "detached": branch_result_code != 0,
        "metadata": metadata,
    }


def _worktree_recovery_ref(issue_identifier: str) -> str:
    """Return the stable, task-scoped ref used for dirty-worktree recovery."""

    identifier = str(issue_identifier or "").strip()
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:16]
    return (
        "refs/oompah/recovery/"
        f"{_sanitize_identifier(identifier)}-{digest}"
    )


def _validate_supported_release_branches(
    supported: list,
    branches_patterns: list[str],
    default_branch: str,
) -> list[str]:
    """Validate and normalise ``supported_release_branches`` before persisting.

    Rules (section 5 of plans/release-branch-addendums.md):
    - Each entry must be a nonempty branch name (string, stripped).
    - Names must be unique after case-insensitive normalisation.
    - No entry may equal the project's ``default_branch``.
    - Every entry must match at least one pattern in ``branches_patterns`` via
      ``fnmatch``.

    Returns the cleaned list (order preserved).
    Raises :exc:`ProjectError` on any violation.
    """
    import fnmatch

    if not isinstance(supported, list):
        raise ProjectError(
            "'supported_release_branches' must be a list of strings or null"
        )

    cleaned: list[str] = []
    seen_lower: set[str] = set()

    for raw in supported:
        if not isinstance(raw, str):
            raise ProjectError(
                "'supported_release_branches' entries must be strings"
            )
        name = raw.strip()
        if not name:
            raise ProjectError(
                "'supported_release_branches' entries must not be empty"
            )
        norm = name.lower()
        if norm in seen_lower:
            raise ProjectError(
                f"'supported_release_branches' has a duplicate entry after "
                f"normalisation: {name!r}"
            )
        seen_lower.add(norm)
        if name == default_branch:
            raise ProjectError(
                f"'supported_release_branches' must not include the "
                f"default branch: {default_branch!r}"
            )
        if not any(fnmatch.fnmatch(name, pat) for pat in branches_patterns):
            raise ProjectError(
                f"'supported_release_branches' entry {name!r} does not match "
                f"any pattern in 'branches': {branches_patterns!r}"
            )
        cleaned.append(name)

    return cleaned


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


def gitlab_owner_repo_from_url(repo_url: str, gitlab_base_url: str | None = None) -> tuple[str | None, str | None]:
    """Return ``(owner/path, repo)`` for GitLab clone URLs, else ``(None, None)``.
    
    GitLab project paths can include groups and subgroups (e.g., "group/subgroup/project").
    This function extracts the full path as the owner component.
    
    Args:
        repo_url: Git clone URL (https, ssh, or local).
        gitlab_base_url: Expected GitLab instance base URL (e.g., "https://gitlab.com").
                         If provided, only URLs matching this host are accepted.
    
    Returns:
        Tuple of (project_path, repo_name) for GitLab URLs matching the base URL,
        or (None, None) if the URL doesn't match or isn't a valid GitLab URL.
    """
    value = (repo_url or "").strip()
    if not value:
        return None, None
    
    # Determine the expected GitLab host from gitlab_base_url
    expected_host = None
    if gitlab_base_url:
        parsed_base = urlsplit(gitlab_base_url)
        expected_host = (parsed_base.hostname or "").lower()
    
    path = ""
    host = ""
    
    if value.startswith("git@") or re.match(r"^[^/@:]+@", value):
        # SSH format: git@gitlab.com:group/subgroup/project.git
        if ":" not in value:
            return None, None
        host_part, path = value.split(":", 1)
        # Extract hostname from git@host
        if "@" in host_part:
            host = host_part.split("@")[1].lower()
        else:
            return None, None
    elif value.lower().startswith(("https://", "http://", "ssh://")):
        # HTTPS format: https://gitlab.com/group/subgroup/project.git
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        path = parsed.path
    else:
        # Local path or unrecognized format
        return None, None
    
    # Check if host matches the expected GitLab instance
    if expected_host and host != expected_host:
        return None, None
    
    # Check if it looks like a GitLab host
    if not (host and ("gitlab" in host or host in ("localhost", "127.0.0.1") or ":" in host)):
        return None, None
    
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        return None, None
    
    # For GitLab, the owner is the full path (group/subgroup/project)
    # and we need at least group/project
    project_name = parts[-1]
    project_path = "/".join(parts)
    
    return project_path, project_name


def _sanitize_identifier(value: str) -> str:
    """Make a project or task identifier safe for local branch/path names."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return cleaned.strip("._-") or "unnamed"


# ---------------------------------------------------------------------------
# Forge configuration validation (OOMPAH-319)
# ---------------------------------------------------------------------------

_VALID_FORGE_KINDS = frozenset({"github", "gitlab"})
_GITHUB_BASE_URL = "https://github.com"
_GITLAB_COM_BASE_URL = "https://gitlab.com"

# Tracker kinds that bind to a specific forge
_TRACKER_KIND_FORGE = {
    "github_issues": "github",
    "github-issues": "github",
    "gitlab_issues": "gitlab",
    "gitlab-issues": "gitlab",
}


def _validate_forge_config(
    forge_kind: str,
    forge_base_url: str,
    tracker_kind: str | None = None,
    repo_url: str | None = None,
) -> tuple[str, str]:
    """Validate and normalise explicit forge configuration before saving.

    Returns ``(normalised_forge_kind, normalised_forge_base_url)`` on
    success.  Raises :exc:`ProjectError` with an actionable message on any
    invalid combination.

    Rules
    -----
    - ``forge_kind`` must be ``"github"`` or ``"gitlab"`` (case-insensitive).
    - ``forge_base_url`` must be an ``https://`` URL with no trailing slash.
    - GitHub projects must use ``https://github.com`` as the base URL.
    - GitLab projects that omit ``forge_base_url`` default to
      ``https://gitlab.com``.
    - ``tracker_kind`` must be compatible with ``forge_kind`` when set:
      ``github_issues`` requires GitHub; ``gitlab_issues`` requires GitLab.
    - If ``repo_url`` resolves to a known forge host, it must match
      ``forge_kind`` (e.g. a ``github.com`` clone URL with
      ``forge_kind="gitlab"`` is rejected).
    """
    # --- forge_kind ---
    fk = str(forge_kind or "").strip().lower()
    if fk not in _VALID_FORGE_KINDS:
        raise ProjectError(
            f"forge_kind must be 'github' or 'gitlab', got {forge_kind!r}"
        )

    # --- forge_base_url ---
    raw_url = str(forge_base_url or "").strip().rstrip("/")
    if not raw_url:
        raw_url = _GITHUB_BASE_URL if fk == "github" else _GITLAB_COM_BASE_URL

    if not raw_url.startswith("https://"):
        raise ProjectError(
            f"forge_base_url must be an https:// URL, got {forge_base_url!r}"
        )

    # GitHub must always use exactly https://github.com
    if fk == "github" and raw_url != _GITHUB_BASE_URL:
        raise ProjectError(
            f"forge_base_url must be '{_GITHUB_BASE_URL}' for GitHub projects, "
            f"got {forge_base_url!r}"
        )

    # --- tracker_kind compatibility ---
    if tracker_kind:
        tk_norm = str(tracker_kind).strip().lower()
        required_forge = _TRACKER_KIND_FORGE.get(tk_norm)
        if required_forge is not None and required_forge != fk:
            raise ProjectError(
                f"tracker_kind '{tracker_kind}' requires forge_kind='{required_forge}', "
                f"but forge_kind is set to '{fk}'"
            )

    # --- repo_url host vs forge_kind ---
    if repo_url:
        _url = str(repo_url).strip()
        try:
            parsed = urlsplit(_url)
            host = (parsed.hostname or "").lower()
        except Exception:
            host = ""

        # SSH URL pattern (git@github.com:org/repo.git)
        if not host and ("@" in _url and ":" in _url):
            at_part = _url.split("@", 1)[-1]
            host = at_part.split(":")[0].lower()

        if host == "github.com" and fk != "github":
            raise ProjectError(
                f"repo_url host is github.com but forge_kind is '{fk}'; "
                "set forge_kind='github' or use a GitLab repo URL"
            )
        if host == "gitlab.com" and fk != "gitlab":
            raise ProjectError(
                f"repo_url host is gitlab.com but forge_kind is '{fk}'; "
                "set forge_kind='gitlab' or use a GitHub repo URL"
            )
        # For self-managed GitLab, the repo host must match the forge_base_url host
        if fk == "gitlab" and host and raw_url != _GITLAB_COM_BASE_URL:
            try:
                forge_host = (urlsplit(raw_url).hostname or "").lower()
            except Exception:
                forge_host = ""
            if forge_host and host != forge_host:
                raise ProjectError(
                    f"repo_url host '{host}' does not match forge_base_url host "
                    f"'{forge_host}'; they must refer to the same GitLab instance"
                )

    return fk, raw_url


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


def _bootstrap_lfs(repo_path: str) -> bool:
    """Install git LFS locally for a repo.

    Returns False when git-lfs is unavailable or fails. The project can
    still operate without LFS; attachments just won't get large-file
    handling until the operator installs it.

    This deliberately does not write ``.oompah/attachments/.gitattributes``.
    Project registration must not dirty managed checkouts. The attachment
    store writes that tracked scaffold only when an attachment is actually
    added.
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


def _is_stale_worktree_remove_error(stderr: str) -> bool:
    """Return True when ``git worktree remove`` failed because the directory
    is no longer a valid registered worktree.

    These directories can be left behind after interrupted cleanup or manual
    deletion of entries under ``.git/worktrees``.  Once Git no longer owns the
    path, ``git worktree remove --force`` cannot remove it, so ProjectStore
    falls back to deleting the exact managed directory on disk.
    """
    text = (stderr or "").lower()
    return any(
        marker in text
        for marker in (
            "is not a working tree",
            "not a working tree",
            "not a git repository",
            "gitdir file points to non-existent location",
            "invalid gitfile",
            "validation failed",
        )
    )


def _safe_remove_managed_dir(path: str, managed_root: str) -> None:
    """Remove ``path`` only when it is a direct managed worktree directory."""
    abs_path = os.path.abspath(path)
    abs_root = os.path.abspath(managed_root)
    if os.path.islink(abs_path):
        raise ProjectError(f"Refusing to remove symlinked worktree path: {path}")
    try:
        common = os.path.commonpath([abs_root, abs_path])
    except ValueError as exc:
        raise ProjectError(f"Refusing to remove path outside worktree root: {path}") from exc
    if common != abs_root or abs_path == abs_root:
        raise ProjectError(f"Refusing to remove path outside worktree root: {path}")
    if os.path.dirname(abs_path) != abs_root:
        raise ProjectError(f"Refusing to remove nested worktree path: {path}")
    shutil.rmtree(abs_path)


def _is_git_working_tree(path: str) -> bool:
    """Return True when ``path`` is still a usable Git working tree."""
    try:
        result = subprocess.run(
            ["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


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


def _is_oompah_md_kind(kind: str) -> bool:
    """Return True when *kind* is the native oompah Markdown tracker."""
    return kind in ("oompah_md", "oompah.md", "oompah")


def _is_github_backed(project: "Project") -> bool:
    """Return True when *project* uses the GitHub Issues tracker backend.

    Recognised values are ``"github_issues"`` and ``"github-issues"`` to
    tolerate minor spelling variations. All other tracker kinds return False.
    """
    kind = (getattr(project, "tracker_kind", None) or "").strip().lower()
    return _is_github_backed_kind(kind)


def _is_gitlab_backed_kind(kind: str) -> bool:
    """Return True when *kind* (already lower-stripped) is a GitLab Issues tracker."""
    return kind in ("gitlab_issues", "gitlab-issues")


def _is_gitlab_backed(project: "Project") -> bool:
    """Return True when *project* uses the GitLab Issues tracker backend."""
    kind = (getattr(project, "tracker_kind", None) or "").strip().lower()
    return _is_gitlab_backed_kind(kind)


def _resolve_owner_identity(
    repo_url: str,
    tracker_kind: str | None,
    tracker_owner: str | None,
    forge_kind: str | None,
    forge_base_url: str | None,
    status_actor_login: str | None,
    is_dispatchable: bool = False,
) -> tuple[str | None, str | None]:
    """Resolve the owner identity for a project (OOMPAH-677).
    
    This function derives the project owner (status_actor_login) from the
    repo_url, tracker configuration, and/or provided credentials. It never
    trusts client-supplied status_actor_login values for authorization.
    
    For dispatchable projects (paused=False), it validates that an owner
    can be determined.
    
    Args:
        repo_url: Git clone URL.
        tracker_kind: Tracker backend kind (e.g., "github_issues", "gitlab_issues", "oompah_md").
        tracker_owner: Explicitly configured tracker owner/namespace.
        forge_kind: Forge kind ("github" or "gitlab").
        forge_base_url: Base URL of the forge instance.
        status_actor_login: Client-supplied status actor (NOT used for authorization).
        is_dispatchable: If True, the project must have a derivable owner.
    
    Returns:
        Tuple of (resolved_status_actor_login, error_message).
        - resolved_status_actor_login: The derived owner login, or None.
        - error_message: None if successful, or an error message if
          is_dispatchable=True and no owner could be derived.
    """
    resolved_kind = str(tracker_kind or "").strip().lower()
    resolved_forge = str(forge_kind or "github").strip().lower()
    
    # Try to derive owner from repo_url based on tracker/forge configuration
    inferred_owner = None
    
    if resolved_kind in ("github_issues", "github-issues"):
        # GitHub Issues tracker: derive owner from GitHub repo URL
        inferred_owner, _ = github_owner_repo_from_url(repo_url)
    elif resolved_kind in ("gitlab_issues", "gitlab-issues"):
        # GitLab Issues tracker: derive owner from GitLab repo URL
        inferred_owner, _ = gitlab_owner_repo_from_url(repo_url, forge_base_url)
    elif resolved_kind in ("oompah_md", "oompah.md", "oompah", ""):
        # Native Markdown tracker (or None/empty): try to infer from GitHub URL if it's a GitHub repo
        inferred_owner, _ = github_owner_repo_from_url(repo_url)
        # If no GitHub owner but we have tracker_owner (e.g., GitLab-hosted oompah_md),
        # use that as the project owner
        if not inferred_owner and tracker_owner:
            inferred_owner = tracker_owner
    
    # For dispatchable projects, ensure we have an owner
    error_message = None
    if is_dispatchable and not inferred_owner:
        error_message = (
            "Dispatchable projects must have a configured owner. "
            "Set status_actor_login, tracker_owner, or ensure the repository URL "
            "is from a supported forge (GitHub, GitLab)."
        )
    
    return inferred_owner, error_message


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
        # Serializes concurrent tracker writes and
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
                    register_secret_values((p.access_token, p.webhook_secret))
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

    def find_by_name(self, name: str) -> Project | None:
        """Return the project with the given name, or None if not found.

        This is a secondary lookup by human-readable project name (e.g.
        ``"coroot"``) for callers that have a name but not an internal ID.
        IDs always take precedence — use :meth:`get` when you have the ID.
        """
        for p in self._projects.values():
            if p.name == name:
                return p
        return None

    def project_write_lock(self, project_id: str) -> threading.RLock:
        """Return the per-project write lock for *project_id*.

        The lock is created on first access and cached for the lifetime of this
        store instance.  Callers should hold the lock while performing any
        operation that mutates tracker state, git
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

    @staticmethod
    def _run_network_git(
        project: Project,
        args: list[str],
        *,
        cwd: str | None = None,
        timeout: float = 60,
    ) -> subprocess.CompletedProcess[str]:
        """Run one managed network Git operation with project credentials.

        The project token is held only by the child environment while Git is
        running.  Callers receive redacted output, and the command/remote
        remain credential-free.
        """
        token = getattr(project, "access_token", None)
        forge_kind = getattr(project, "forge_kind", "github")
        with git_credential_environment(
            forge_kind=forge_kind,
            access_token=token,
            base_env=_recovery_git_env(),
        ) as env:
            result = subprocess.run(
                args,
                cwd=cwd or project.repo_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
                env=env,
            )
        result.stdout = redact_git_output(result.stdout, (token or "",))
        result.stderr = redact_git_output(result.stderr, (token or "",))
        return result

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
        forge_kind: str = "github",
        forge_base_url: str | None = None,
        tracker_kind: str | None = "oompah_md",
        tracker_owner: str | None = None,
        tracker_repo: str | None = None,
        github_project_node_id: str | None = None,
        github_issue_intake_enabled: bool = False,
        status_actor_login: str | None = None,
        status_label_authorized_logins: list[str] | None = None,
        supported_release_branches: list[str] | None = None,
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
            tracker_kind: Per-project tracker backend (e.g. "oompah_md",
                          "github_issues"). Defaults to oompah's native
                          Markdown task store.
            tracker_owner: GitHub org/user owning the task hub repository.
            tracker_repo: GitHub task hub repository name.
            github_issue_intake_enabled: For native Markdown projects, import
                                      incoming GitHub issues from tracker_owner/repo.
            github_project_node_id: GitHub Projects v2 node ID for board views.
            status_actor_login: GitHub login used as the project-owner status actor.
            status_label_authorized_logins: Additional GitHub logins authorized to
                                      move protected status labels.
            supported_release_branches: Ordered list of exact branch names that
                                      are configured as supported release lines
                                      (section 5 of release-branch-addendums.md).
                                      Each entry must be nonempty, unique after
                                      normalisation, not equal to default_branch,
                                      and matched by at least one branches pattern.
                                      Defaults to [] when not provided or None.
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

        # Validate and normalise forge configuration (OOMPAH-319).
        # Default forge_base_url to the canonical value for the given forge_kind.
        _default_forge_base = (
            _GITLAB_COM_BASE_URL if str(forge_kind or "").strip().lower() == "gitlab"
            else _GITHUB_BASE_URL
        )
        forge_kind_norm, forge_base_url_norm = _validate_forge_config(
            forge_kind=forge_kind,
            forge_base_url=forge_base_url or _default_forge_base,
            tracker_kind=tracker_kind,
            repo_url=repo_url,
        )

        # Validate and normalise supported_release_branches.
        if supported_release_branches is None:
            supported_release_branches = []
        else:
            supported_release_branches = _validate_supported_release_branches(
                supported_release_branches, branches, default_branch
            )

        # Validate owner identity early (before git clone) for dispatchable projects (OOMPAH-677).
        # Never trust client-supplied status_actor_login for authorization.
        tracker_kind_resolved = tracker_kind or "oompah_md"
        _resolved_kind = str(tracker_kind_resolved).strip().lower()
        tracker_owner_value = str(tracker_owner).strip() if tracker_owner else None
        
        resolved_status_actor, owner_error = _resolve_owner_identity(
            repo_url=repo_url,
            tracker_kind=_resolved_kind,
            tracker_owner=tracker_owner_value,
            forge_kind=forge_kind_norm,
            forge_base_url=forge_base_url_norm,
            status_actor_login=None,  # Never trust client input
            is_dispatchable=not paused,
        )
        
        if owner_error and not paused:
            raise ProjectError(owner_error)

        # Clone into ~/.oompah/repos/<name>/
        repo_path = os.path.join(self.repos_root, _sanitize_identifier(name))
        bootstrap_project = Project(
            id="project-bootstrap",
            name=name,
            repo_url=repo_url,
            repo_path=repo_path,
            default_branch=default_branch,
            access_token=access_token,
            forge_kind=forge_kind_norm,
        )

        if os.path.isdir(repo_path):
            # Already cloned — pull latest
            logger.info("Repo already cloned at %s, pulling latest", repo_path)
            try:
                fetched = self._run_network_git(
                    bootstrap_project,
                    ["git", "fetch", "--all"],
                    timeout=120,
                )
                if fetched.returncode != 0:
                    logger.warning(
                        "git fetch failed for %s: %s",
                        repo_path,
                        fetched.stderr.strip()[:500],
                    )
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.warning(
                    "git fetch failed for %s: %s", repo_path, type(exc).__name__
                )
        else:
            os.makedirs(os.path.dirname(repo_path), exist_ok=True)
            try:
                clone = self._run_network_git(
                    bootstrap_project,
                    ["git", "clone", "--branch", default_branch, repo_url, repo_path],
                    timeout=300,
                )
                if clone.returncode != 0:
                    shutil.rmtree(repo_path, ignore_errors=True)
                    raise ProjectError(f"git clone failed: {clone.stderr.strip()[:500]}")
            except OSError as exc:
                shutil.rmtree(repo_path, ignore_errors=True)
                raise ProjectError(f"git clone failed: {type(exc).__name__}") from exc
            except subprocess.TimeoutExpired:
                shutil.rmtree(repo_path, ignore_errors=True)
                raise ProjectError("git clone timed out")

        # Validate clone
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            raise ProjectError(f"Clone succeeded but no .git/ found in: {repo_path}")
        tracker_kind = tracker_kind or "oompah_md"
        _resolved_kind = str(tracker_kind).strip().lower()

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
        
        # For GitHub-backed trackers and oompah_md with GitHub intake, infer tracker_owner/repo from URL
        if (
            _is_github_backed_kind(_resolved_kind)
            or (
                _is_oompah_md_kind(_resolved_kind)
                and bool(github_issue_intake_enabled)
            )
        ):
            if not tracker_owner_value or not tracker_repo_value:
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
            forge_kind=forge_kind_norm,
            forge_base_url=forge_base_url_norm,
            tracker_kind=str(tracker_kind).strip() if tracker_kind else None,
            tracker_owner=tracker_owner_value,
            tracker_repo=tracker_repo_value,
            github_issue_intake_enabled=bool(github_issue_intake_enabled),
            github_project_node_id=str(github_project_node_id).strip() if github_project_node_id else None,
            status_actor_login=resolved_status_actor,
            status_label_authorized_logins=[
                str(login).strip()
                for login in (status_label_authorized_logins or [])
                if str(login).strip()
            ],
            supported_release_branches=supported_release_branches,
            paused=bool(paused),
        )
        self._projects[project_id] = project
        register_secret_values((project.access_token, project.webhook_secret))
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
            "webhook_forwarding_enabled",
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
            # Explicit forge configuration.  The legacy GitHub defaults are
            # retained for projects which never send either field.
            "forge_kind",
            "forge_base_url",
            # Per-project tracker configuration
            "tracker_kind",
            "tracker_owner",
            "tracker_repo",
            "github_issue_intake_enabled",
            "external_issue_intake_enabled",
            "github_project_node_id",
            # Supported release lines (section 5 of release-branch-addendums.md)
            "supported_release_branches",
            # State-branch configuration (OOMPAH-255 / OOMPAH-253 / OOMPAH-259)
            "state_branch_enabled",
            "state_branch_checkpoint_debounce_ms",
            "state_branch_checkpoint_max_delay_ms",
            "state_branch_shadow_write",
            "state_branch_migration_stage",
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

        # Validate epic_strategy: only "shared" is supported.
        # "flat" and "stacked" were removed; callers that still send them
        # receive a validation error so they can update their integration.
        if "epic_strategy" in fields:
            val = fields["epic_strategy"]
            if val is None:
                fields["epic_strategy"] = "shared"
            else:
                if not isinstance(val, str):
                    raise ProjectError("'epic_strategy' must be 'shared'")
                norm = val.strip().lower()
                if norm != "shared":
                    raise ProjectError(
                        "'epic_strategy' must be 'shared' — flat and stacked"
                        " strategies have been removed"
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

        # external_issue_intake_enabled is the forge-neutral public alias.
        # Keep storing the existing field name so persisted records and old
        # clients remain compatible.  Clients which round-trip a GET response
        # may send both aliases; accept that only when the values agree.
        intake_aliases = (
            "external_issue_intake_enabled",
            "github_issue_intake_enabled",
        )
        normalized_intake_values = {}
        for key in intake_aliases:
            if key not in fields:
                continue
            val = fields[key]
            if val is None:
                normalized_intake_values[key] = False
            elif isinstance(val, bool):
                normalized_intake_values[key] = val
            else:
                raise ProjectError(f"'{key}' must be a boolean")

        if len(normalized_intake_values) == 2:
            external_value = normalized_intake_values[
                "external_issue_intake_enabled"
            ]
            github_value = normalized_intake_values[
                "github_issue_intake_enabled"
            ]
            if external_value != github_value:
                raise ProjectError(
                    "Conflicting values for 'external_issue_intake_enabled' and "
                    "'github_issue_intake_enabled'; when both are provided they "
                    "must match"
                )

        if normalized_intake_values:
            fields["github_issue_intake_enabled"] = next(
                iter(normalized_intake_values.values())
            )
            fields.pop("external_issue_intake_enabled", None)

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

        # Validate that dispatchable projects don't lose their owner (OOMPAH-677).
        # If the project is active (not paused) and owner fields that are currently set
        # are being cleared, ensure that an owner can still be derived.
        effective_paused = fields.get("paused", project.paused)
        if not effective_paused:
            # Only apply validation if we're actually clearing a previously-set owner field
            clearing_status_actor = (
                "status_actor_login" in fields
                and fields["status_actor_login"] is None
                and project.status_actor_login  # Was previously set
            )
            clearing_tracker_owner = (
                "tracker_owner" in fields
                and fields["tracker_owner"] is None
                and project.tracker_owner  # Was previously set
            )
            
            if clearing_status_actor or clearing_tracker_owner:
                # Try to resolve owner with the new configuration
                effective_repo_url = fields.get("repo_url", project.repo_url)
                effective_tracker_kind = fields.get("tracker_kind", project.tracker_kind)
                effective_tracker_owner = fields.get("tracker_owner", project.tracker_owner)
                effective_forge_kind = fields.get("forge_kind", project.forge_kind)
                effective_forge_base = fields.get("forge_base_url", project.forge_base_url)
                
                resolved_owner, error = _resolve_owner_identity(
                    repo_url=effective_repo_url,
                    tracker_kind=effective_tracker_kind,
                    tracker_owner=effective_tracker_owner,
                    forge_kind=effective_forge_kind,
                    forge_base_url=effective_forge_base,
                    status_actor_login=None,
                    is_dispatchable=True,
                )
                if error:
                    raise ProjectError(error)

        # Validate forge configuration against the effective values after all
        # related fields have been normalized.  This prevents a PATCH from
        # persisting a forge/tracker/repository mismatch.
        if "forge_kind" in fields or "forge_base_url" in fields or \
                "tracker_kind" in fields or "repo_url" in fields:
            effective_kind = fields.get("forge_kind", project.forge_kind)
            effective_base = fields.get("forge_base_url", project.forge_base_url)
            effective_tracker = fields.get("tracker_kind", project.tracker_kind)
            effective_repo = fields.get("repo_url", project.repo_url)
            norm_kind, norm_base = _validate_forge_config(
                forge_kind=effective_kind,
                forge_base_url=effective_base,
                tracker_kind=effective_tracker,
                repo_url=effective_repo,
            )
            fields["forge_kind"] = norm_kind
            fields["forge_base_url"] = norm_base

        # Validate and normalise supported_release_branches.
        # Cross-field validation uses the effective branches/default_branch
        # values from this update (or the project's current values if not
        # being changed in the same call).
        if "supported_release_branches" in fields:
            val = fields["supported_release_branches"]
            if val is None:
                fields["supported_release_branches"] = []
            else:
                effective_branches = fields.get("branches", project.branches)
                effective_default = fields.get(
                    "default_branch", project.default_branch
                )
                if isinstance(effective_branches, list) and effective_branches:
                    eff_branches = effective_branches
                else:
                    eff_branches = project.branches
                if isinstance(effective_default, str) and effective_default.strip():
                    eff_default = effective_default.strip()
                else:
                    eff_default = project.default_branch
                fields["supported_release_branches"] = (
                    _validate_supported_release_branches(
                        val, eff_branches, eff_default
                    )
                )

        # ---- State-branch configuration (OOMPAH-255 / OOMPAH-259) ----

        # state_branch_enabled: must be a boolean.
        if "state_branch_enabled" in fields:
            val = fields["state_branch_enabled"]
            if not isinstance(val, bool):
                raise ProjectError("'state_branch_enabled' must be a boolean")

        # state_branch_shadow_write: must be a boolean.
        if "state_branch_shadow_write" in fields:
            val = fields["state_branch_shadow_write"]
            if not isinstance(val, bool):
                raise ProjectError("'state_branch_shadow_write' must be a boolean")

        # state_branch_migration_stage: must be one of "", "A", "B".
        if "state_branch_migration_stage" in fields:
            val = fields["state_branch_migration_stage"]
            if val not in ("", "A", "B"):
                raise ProjectError(
                    "'state_branch_migration_stage' must be '', 'A', or 'B'"
                )

        # state_branch_checkpoint_debounce_ms / state_branch_checkpoint_max_delay_ms:
        # optional positive integer or null.  When both are supplied in the same
        # update, cross-validate that max_delay >= debounce + 1000.
        for key in (
            "state_branch_checkpoint_debounce_ms",
            "state_branch_checkpoint_max_delay_ms",
        ):
            if key in fields:
                val = fields[key]
                if val is None:
                    fields[key] = None
                elif isinstance(val, bool) or not isinstance(val, int):
                    # Strict type check: booleans, strings, floats etc. are
                    # all rejected.  Only bare int values (not bool subclass)
                    # are accepted.
                    raise ProjectError(f"'{key}' must be a positive integer or null")
                elif val <= 0:
                    raise ProjectError(
                        f"'{key}' must be a positive integer or null"
                    )
                else:
                    fields[key] = val

        # Cross-validate that max_delay >= debounce + 1000 when both are set
        # (either in this update or carried over from the existing project).
        if "state_branch_checkpoint_debounce_ms" in fields or \
                "state_branch_checkpoint_max_delay_ms" in fields:
            eff_debounce = fields.get(
                "state_branch_checkpoint_debounce_ms",
                project.state_branch_checkpoint_debounce_ms,
            )
            eff_max_delay = fields.get(
                "state_branch_checkpoint_max_delay_ms",
                project.state_branch_checkpoint_max_delay_ms,
            )
            if eff_debounce is not None and eff_max_delay is not None:
                if eff_max_delay < eff_debounce + 1000:
                    raise ProjectError(
                        "'state_branch_checkpoint_max_delay_ms' must be at least "
                        "'state_branch_checkpoint_debounce_ms' + 1000 ms"
                    )

        for key, value in fields.items():
            setattr(project, key, value)

        # Dynamic project updates can introduce a new opaque token/secret;
        # retain both the new and old value in the process-local registry so
        # delayed workers cannot expose either during rotation.
        register_secret_values((project.access_token, project.webhook_secret))

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
        """Pull latest code and run generic git self-heal for a managed project.

        Best-effort: any failure is logged and recorded in the returned
        status dict but does NOT raise. The orchestrator should boot
        even if a project's network is flaky — it just operates on
        whatever local state exists.

        Returns ``{"git": "ok"|"reset:ok"|"failed: <reason>"|"skipped: <reason>",
                  "tracker": "<tracker_kind>"  # present for explicit project trackers
                  }``.
        """
        project = self._projects.get(project_id)
        if not project:
            return {"git": "skipped: unknown project"}

        tracker_kind = (getattr(project, "tracker_kind", None) or "").strip().lower()
        status: dict[str, str] = {}
        if tracker_kind:
            status["tracker"] = tracker_kind

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

    def create_detached_audit_worktree(
        self,
        project_id: str,
        workspace_identifier: str,
        revision: str,
    ) -> tuple[str, str]:
        """Create a branchless, read-only audit view at an exact commit.

        Auditor workspaces must not reuse implementation branches.  Historical
        task and epic branches are routinely deleted after merge, and trying to
        recreate them both fails legitimate retention audits and risks turning
        a read-only audit into a branch-writing implementation checkout.

        Returns ``(path, resolved_sha)``.  The caller supplies a unique
        attempt-scoped workspace identifier so an implementation worktree is
        never reset or cleaned as a side effect.
        """

        with self.project_write_lock(project_id):
            project = self._projects.get(project_id)
            if not project:
                raise ProjectError(f"Unknown project: {project_id}")

            requested = str(revision or "").strip()
            if not requested:
                raise ProjectError("terminal audit requires a revision")

            try:
                self._run_network_git(
                    project,
                    ["git", "fetch", "origin"],
                    cwd=project.repo_path,
                    timeout=60,
                )
                resolved = subprocess.run(
                    ["git", "rev-parse", "--verify", f"{requested}^{{commit}}"],
                    cwd=project.repo_path,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ProjectError(
                    f"terminal audit revision lookup failed: {exc}"
                ) from exc
            resolved_sha = resolved.stdout.strip()
            if resolved.returncode != 0 or not re.fullmatch(
                r"[0-9a-fA-F]{40,64}", resolved_sha
            ):
                raise ProjectError(
                    f"terminal audit revision is unavailable: {requested}"
                )

            wt_path = self.worktree_path_for(project_id, workspace_identifier)
            if os.path.isdir(wt_path):
                try:
                    existing = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=wt_path,
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=10,
                    )
                    status = self._git_status_for_worktree(wt_path)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise ProjectError(
                        f"cannot verify existing terminal audit worktree: {exc}"
                    ) from exc
                if (
                    existing.returncode == 0
                    and existing.stdout.strip() == resolved_sha
                    and status.returncode == 0
                    and not self._worktree_dirty_paths(status.stdout)
                ):
                    self._disable_worktree_hooks(wt_path)
                    return wt_path, resolved_sha
                raise ProjectError(
                    "existing terminal audit worktree does not match its "
                    "attempt revision; refusing to reset it"
                )

            os.makedirs(os.path.dirname(wt_path), exist_ok=True)
            try:
                _git_worktree_add_with_recovery(
                    ["git", "worktree", "add", "--detach", wt_path, resolved_sha],
                    cwd=project.repo_path,
                    wt_path=wt_path,
                )
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.strip()[:500] if exc.stderr else ""
                raise ProjectError(
                    f"terminal audit worktree add failed: {stderr}"
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise ProjectError("terminal audit worktree add timed out") from exc

            self._disable_worktree_hooks(wt_path)
            logger.info(
                "Detached terminal audit worktree created path=%s revision=%s",
                wt_path,
                resolved_sha,
            )
            return wt_path, resolved_sha

    def epic_worktree_path_for(self, project_id: str, epic_identifier: str) -> str:
        """Path used for the shared epic worktree under epic_strategy='shared'.

        Lives at ``<worktree_root>/<project>/epic-<epic_identifier>`` so it
        can never collide with a per-issue worktree (which uses just the
        issue identifier). The branch name on the worktree mirrors the
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

    def epic_child_branch_name(
        self,
        epic_identifier: str,
        child_identifier: str,
    ) -> str:
        """Return a private child ref that cannot prefix-collide with an epic."""

        return (
            f"epic-{_sanitize_identifier(epic_identifier)}"
            f"--task-{_sanitize_identifier(child_identifier)}"
        )

    def delete_epic_child_branch(
        self,
        project_id: str,
        epic_identifier: str,
        child_identifier: str,
    ) -> bool:
        """Delete one landed private child branch and its managed worktree.

        The branch name is derived internally instead of accepted from a
        caller, which keeps this cleanup narrowly scoped and prevents a stale
        tracker value from targeting an unrelated remote ref. Returns whether
        the remote branch existed.
        """

        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        branch = self.epic_child_branch_name(
            epic_identifier,
            child_identifier,
        )
        with self.project_write_lock(project_id):
            self._remove_worktree_locked(project_id, child_identifier)
            remote = self._run_network_git(
                project,
                [
                    "git",
                    "ls-remote",
                    "--exit-code",
                    "--heads",
                    "origin",
                    branch,
                ],
                timeout=30,
            )
            if remote.returncode not in {0, 2}:
                raise ProjectError(
                    "git remote branch check failed: "
                    f"{remote.stderr.strip()[:500]}"
                )
            existed = remote.returncode == 0
            if existed:
                deleted = self._run_network_git(
                    project,
                    ["git", "push", "origin", "--delete", branch],
                    timeout=60,
                )
                if deleted.returncode != 0:
                    raise ProjectError(
                        "git remote branch delete failed: "
                        f"{deleted.stderr.strip()[:500]}"
                    )
            local = subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
                cwd=project.repo_path,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if local.returncode == 0:
                removed = subprocess.run(
                    ["git", "branch", "-D", branch],
                    cwd=project.repo_path,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if removed.returncode != 0:
                    raise ProjectError(
                        "git local branch delete failed: "
                        f"{removed.stderr.strip()[:500]}"
                    )
        if existed:
            logger.info(
                "Deleted landed private epic child branch project=%s branch=%s",
                project_id,
                branch,
            )
        return existed

    @staticmethod
    def _worktree_dirty_paths(status_output: str) -> list[str]:
        """Extract changed deliverable paths, excluding generated helpers."""

        paths: list[str] = []
        for line in str(status_output or "").splitlines():
            if len(line) < 3:
                continue
            path = line[3:].strip()
            # A rename is represented as ``old -> new``.  Keeping both paths
            # makes the recovery context useful without attempting to parse
            # Git's quoting rules here.
            candidates = [part.strip() for part in path.split(" -> ")]
            if any(_is_generated_worktree_helper(candidate) for candidate in candidates):
                continue
            paths.extend(candidate for candidate in candidates if candidate)
        return list(dict.fromkeys(paths))

    @staticmethod
    def _worktree_generated_paths(status_output: str) -> list[str]:
        """Extract generated helper paths for operator-facing diagnostics."""

        paths: list[str] = []
        for line in str(status_output or "").splitlines():
            if len(line) < 3:
                continue
            payload = line[3:].strip()
            candidates = [part.strip() for part in payload.split(" -> ")]
            paths.extend(
                candidate
                for candidate in candidates
                if candidate and _is_generated_worktree_helper(candidate)
            )
        return list(dict.fromkeys(paths))

    @staticmethod
    def _git_status_for_worktree(wt_path: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [
                    "git",
                    "status",
                    "--porcelain=v1",
                    "--untracked-files=all",
                ],
                cwd=wt_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
                env=_recovery_git_env(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectError(f"git status failed for worktree {wt_path}: {exc}") from exc

    def _recovery_context_from_ref(
        self,
        project: Project,
        issue_identifier: str,
    ) -> dict[str, object] | None:
        """Read durable recovery evidence for one task, if present."""

        recovery_ref = _worktree_recovery_ref(issue_identifier)
        try:
            resolved = subprocess.run(
                ["git", "rev-parse", "--verify", recovery_ref],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                env=_recovery_git_env(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectError(
                f"git recovery ref lookup failed for {issue_identifier}: {exc}"
            ) from exc
        if resolved.returncode != 0 or not resolved.stdout.strip():
            return None

        snapshot_head = resolved.stdout.strip()
        try:
            message = subprocess.run(
                ["git", "show", "-s", "--format=%B", snapshot_head],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                env=_recovery_git_env(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectError(
                f"git recovery evidence lookup failed for {issue_identifier}: {exc}"
            ) from exc
        if message.returncode != 0:
            raise ProjectError(
                "git recovery evidence commit cannot be read for "
                f"{issue_identifier}: {message.stderr.strip()[:500]}"
            )

        for line in message.stdout.splitlines():
            if not line.startswith(_WORKTREE_RECOVERY_MARKER):
                continue
            try:
                context = json.loads(
                    line[len(_WORKTREE_RECOVERY_MARKER) :].strip()
                )
            except (TypeError, ValueError) as exc:
                raise ProjectError(
                    f"invalid recovery evidence for {issue_identifier}"
                ) from exc
            if not isinstance(context, dict):
                raise ProjectError(f"invalid recovery evidence for {issue_identifier}")
            context = dict(context)
            context.setdefault("recovery_ref", recovery_ref)
            context.setdefault("snapshot_head", snapshot_head)
            return context

        # A ref without the structured marker is still evidence that must not
        # be discarded.  Return a minimal context so a retry can show the
        # operator/agent exactly which commit to inspect.
        return {
            "version": _WORKTREE_RECOVERY_VERSION,
            "project_id": project.id,
            "issue_identifier": issue_identifier,
            "snapshot_head": snapshot_head,
            "recovery_ref": recovery_ref,
            "evidence": "recovery ref exists but its commit metadata is unavailable",
        }

    def worktree_recovery_context(
        self,
        project_id: str,
        issue_identifier: str,
    ) -> dict[str, object] | None:
        """Return durable dirty-worktree recovery evidence for a task."""

        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        with self.project_write_lock(project_id):
            return self._recovery_context_from_ref(project, issue_identifier)

    def _preserve_dirty_worktree_locked(
        self,
        project: Project,
        issue_identifier: str,
        wt_path: str,
        *,
        branch_name: str | None = None,
    ) -> dict[str, object] | None:
        """Snapshot task-owned state before any reuse, sync, or cleanup.

        Ordinary dirty work is captured by a commit on the task branch.  A
        paused Git operation is different: Git intentionally detaches HEAD and
        stores conflict/todo state outside the index.  In that case we create a
        checkpoint commit with ``commit-tree`` while leaving HEAD, the index,
        and operation metadata in place.  Both paths update a stable recovery
        ref only after the snapshot is durable.
        """

        status = self._git_status_for_worktree(wt_path)
        if status.returncode != 0:
            raise ProjectError(
                f"cannot inspect task worktree {wt_path}: "
                f"{status.stderr.strip()[:500]}"
            )
        dirty_paths = self._worktree_dirty_paths(status.stdout)
        generated_paths = sorted(
            set(self._worktree_generated_paths(status.stdout))
            | set(_generated_worktree_helper_paths(wt_path))
        )
        if generated_paths:
            logger.info(
                "recovery snapshot excluded ignored-helper paths issue=%s paths=%s",
                issue_identifier,
                sorted(generated_paths),
            )

        branch_result = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env=_recovery_git_env(),
        )
        current_branch = branch_result.stdout.strip()
        operation = _git_operation_state(
            wt_path,
            current_branch=current_branch,
            branch_result_code=branch_result.returncode,
        )
        operation_branch = str(operation.get("branch") or "").strip() if operation else ""
        expected_branch = str(branch_name or current_branch or operation_branch).strip()

        if operation:
            if operation.get("detached") and not operation_branch:
                logger.error(
                    "recovery snapshot unrecoverable active-operation branch "
                    "identity issue=%s operation=%s",
                    issue_identifier,
                    operation.get("kind"),
                )
                raise ProjectError(
                    f"cannot checkpoint active {operation.get('kind')} for "
                    f"{issue_identifier}: branch identity metadata is missing"
                )
            if operation_branch and expected_branch and operation_branch != expected_branch:
                raise ProjectError(
                    f"cannot snapshot task worktree {wt_path}: active "
                    f"{operation.get('kind')} belongs to branch {operation_branch!r}, "
                    f"not expected branch {expected_branch!r}"
                )
            logger.info(
                "recovery snapshot preserving active-operation state issue=%s "
                "operation=%s branch=%s detached=%s",
                issue_identifier,
                operation.get("kind"),
                operation_branch or expected_branch,
                operation.get("detached"),
            )
        elif branch_result.returncode != 0 or not current_branch:
            logger.error(
                "recovery snapshot unrecoverable detached HEAD issue=%s path=%s",
                issue_identifier,
                wt_path,
            )
            raise ProjectError(
                f"cannot snapshot task worktree {wt_path}: detached HEAD with no "
                "active Git operation"
            )
        elif expected_branch and current_branch != expected_branch:
            raise ProjectError(
                f"cannot snapshot task worktree {wt_path}: branch changed from "
                f"{expected_branch!r} to {current_branch!r}"
            )

        # A helper-only change is not a task change.  Do not manufacture a
        # recovery commit for it, but still checkpoint an active operation so
        # its detached state and todo metadata are durable.
        if not dirty_paths and not operation:
            return self._recovery_context_from_ref(project, issue_identifier)

        before = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env=_recovery_git_env(),
        )
        if before.returncode != 0 or not before.stdout.strip():
            raise ProjectError(
                f"cannot resolve task worktree HEAD for {issue_identifier}"
            )
        prior_head = before.stdout.strip()
        recovery_ref = _worktree_recovery_ref(issue_identifier)
        branch_ref = (
            f"refs/heads/{operation_branch or current_branch}"
            if operation_branch or current_branch
            else None
        )
        branch_head = None
        if branch_ref:
            branch_result_for_context = subprocess.run(
                ["git", "rev-parse", "--verify", branch_ref],
                cwd=wt_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                env=_recovery_git_env(),
            )
            if branch_result_for_context.returncode == 0:
                branch_head = branch_result_for_context.stdout.strip()

        context: dict[str, object] = {
            "version": _WORKTREE_RECOVERY_VERSION,
            "project_id": project.id,
            "issue_identifier": issue_identifier,
            "branch": operation_branch or current_branch,
            "branch_ref": branch_ref,
            "branch_head": branch_head,
            "prior_head": prior_head,
            "changed_paths": dirty_paths,
            "excluded_generated_helpers": generated_paths,
            "recovery_ref": recovery_ref,
            "preserved_at": time.time(),
        }
        if operation:
            context["operation"] = {
                "kind": operation.get("kind"),
                "detached": operation.get("detached"),
                "metadata": operation.get("metadata", {}),
            }
            operation_heads = {
                name: str(value).strip()
                for name, value in (
                    (
                        "rebase_head",
                        (operation.get("metadata") or {}).get("REBASE_HEAD")
                        or (operation.get("metadata") or {}).get("stopped-sha"),
                    ),
                    ("merge_head", (operation.get("metadata") or {}).get("MERGE_HEAD")),
                    ("cherry_pick_head", (operation.get("metadata") or {}).get("CHERRY_PICK_HEAD")),
                )
                if str(value or "").strip()
            }
            if operation_heads:
                context["operation_heads"] = operation_heads

        message = (
            "Oompah preserved task worktree recovery checkpoint\n\n"
            f"{_WORKTREE_RECOVERY_MARKER}"
            f"{json.dumps(context, ensure_ascii=False, sort_keys=True)}"
            "\n\n🤖 Generated with https://github.com/lesserevil/oompah"
            "\n\nCo-authored-by: oompah "
            "<lesserevil@users.noreply.github.com>"
        )

        if dirty_paths:
            try:
                added = subprocess.run(
                    [
                        "git",
                        "add",
                        "--all",
                        "--",
                        *dirty_paths,
                    ],
                    cwd=wt_path,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                    env=_recovery_git_env(),
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ProjectError(
                    f"could not stage recovery snapshot for {issue_identifier}: {exc}"
                ) from exc
            if added.returncode != 0:
                raise ProjectError(
                    f"could not stage recovery snapshot for {issue_identifier}: "
                    f"{added.stderr.strip()[:500]}"
                )

        if operation:
            # write-tree refuses unresolved index entries.  That is useful
            # evidence: do not invent a commit or erase the conflict state.
            tree = subprocess.run(
                ["git", "write-tree"],
                cwd=wt_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
                env=_recovery_git_env(),
            )
            if tree.returncode != 0 or not tree.stdout.strip():
                logger.error(
                    "recovery snapshot unrecoverable active-operation index issue=%s "
                    "operation=%s error=%s",
                    issue_identifier,
                    operation.get("kind"),
                    tree.stderr.strip()[:500],
                )
                raise ProjectError(
                    f"could not checkpoint active {operation.get('kind')} for "
                    f"{issue_identifier}: index is not representable: "
                    f"{tree.stderr.strip()[:500]}"
                )
            committed = subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=oompah",
                    "-c",
                    "user.email=lesserevil@users.noreply.github.com",
                    "-c",
                    "commit.gpgsign=false",
                    "commit-tree",
                    tree.stdout.strip(),
                    "-p",
                    prior_head,
                    "-m",
                    message,
                ],
                cwd=wt_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                env=_recovery_git_env(),
            )
            commit_error = "could not create active-operation recovery checkpoint"
        else:
            committed = subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=oompah",
                    "-c",
                    "user.email=lesserevil@users.noreply.github.com",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "--no-verify",
                    "-m",
                    message,
                ],
                cwd=wt_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                env=_recovery_git_env(),
            )
            commit_error = "could not commit recovery snapshot"
        if committed.returncode != 0:
            raise ProjectError(
                f"{commit_error} for {issue_identifier}: "
                f"{committed.stderr.strip()[:500]}"
            )

        if operation:
            snapshot_head = committed.stdout.strip()
        else:
            after = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=wt_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                env=_recovery_git_env(),
            )
            snapshot_head = after.stdout.strip()
        if not snapshot_head:
            raise ProjectError(
                f"recovery snapshot commit has no resolvable head for {issue_identifier}"
            )
        context["snapshot_head"] = snapshot_head

        try:
            updated_ref = subprocess.run(
                ["git", "update-ref", recovery_ref, snapshot_head],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                env=_recovery_git_env(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectError(
                f"could not persist recovery ref for {issue_identifier}: {exc}"
            ) from exc
        if updated_ref.returncode != 0:
            raise ProjectError(
                f"could not persist recovery ref for {issue_identifier}: "
                f"{updated_ref.stderr.strip()[:500]}"
            )

        # The helper is disposable only after the task snapshot/ref is durable.
        # A subsequent dispatch reinstalls the hook before the worker starts.
        removed_helpers = remove_generated_worktree_helpers(wt_path)
        context["removed_generated_helpers"] = removed_helpers

        final_status = self._git_status_for_worktree(wt_path)
        if final_status.returncode != 0:
            raise ProjectError(
                f"recovery snapshot for {issue_identifier} did not produce a clean "
                "worktree; refusing further Git mutation"
            )
        if operation:
            # A staged conflict resolution is expected to remain dirty against
            # detached HEAD.  The operation marker itself is the cleanliness
            # invariant for this checkpoint; refusing to reset it is the point
            # of the active-operation path.
            if _git_operation_state(
                wt_path,
                current_branch="",
                branch_result_code=128,
            ) is None:
                raise ProjectError(
                    f"active {operation.get('kind')} disappeared while "
                    f"checkpointing {issue_identifier}"
                )
        elif self._worktree_dirty_paths(final_status.stdout):
            raise ProjectError(
                f"recovery snapshot for {issue_identifier} did not produce a clean "
                "worktree; refusing further Git mutation"
            )
        return context

    def preserve_worktree_changes(
        self,
        project_id: str,
        issue_identifier: str,
        wt_path: str | None = None,
        branch_name: str | None = None,
    ) -> dict[str, object] | None:
        """Durably preserve a task worktree's dirty state, if any."""

        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        path = wt_path or self.worktree_path_for(project_id, issue_identifier)
        if not os.path.isdir(path):
            return self._recovery_context_from_ref(project, issue_identifier)
        with self.project_write_lock(project_id):
            return self._preserve_dirty_worktree_locked(
                project,
                issue_identifier,
                path,
                branch_name=branch_name,
            )

    def _project_worktree_root(self, project: Project) -> str:
        return os.path.join(self.worktree_root, _sanitize_identifier(project.name))

    def _prune_git_worktrees(self, repo_path: str) -> None:
        try:
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            logger.debug("git worktree prune failed for %s", repo_path, exc_info=True)

    def _registered_worktree_paths(self, repo_path: str) -> set[str]:
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()[:500] if exc.stderr else ""
            raise ProjectError(f"git worktree list failed: {stderr}")
        except subprocess.TimeoutExpired:
            raise ProjectError("git worktree list timed out")

        paths: set[str] = set()
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                paths.add(os.path.realpath(line[len("worktree ") :]))
        return paths

    def _registered_worktree_branches(self, repo_path: str) -> set[str]:
        """Return local branch names currently checked out in any worktree."""

        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()[:500] if exc.stderr else ""
            raise ProjectError(f"git worktree list failed: {stderr}")
        except subprocess.TimeoutExpired:
            raise ProjectError("git worktree list timed out")

        prefix = "branch refs/heads/"
        return {
            line[len(prefix) :]
            for line in result.stdout.splitlines()
            if line.startswith(prefix)
        }

    def _registered_worktree_branch_paths(
        self, repo_path: str
    ) -> dict[str, set[str]]:
        """Return the registered checkout paths for each local branch.

        The branch-only inventory is sufficient for ordinary branch deletion,
        but auxiliary cleanup must distinguish the candidate worktree from a
        second checkout that is using the same private branch.  Keeping this
        mapping local to the conservative cleanup path avoids changing the
        long-standing inventory API used by other maintenance jobs.
        """

        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()[:500] if exc.stderr else ""
            raise ProjectError(f"git worktree list failed: {stderr}")
        except subprocess.TimeoutExpired:
            raise ProjectError("git worktree list timed out")

        branch_paths: dict[str, set[str]] = {}
        current_path: str | None = None
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                current_path = os.path.realpath(line[len("worktree ") :])
            elif line.startswith("branch refs/heads/") and current_path:
                branch = line[len("branch refs/heads/") :]
                branch_paths.setdefault(branch, set()).add(current_path)
        return branch_paths

    @staticmethod
    def _branch_is_protected(project: Project, branch_name: str) -> bool:
        """Return whether cleanup must preserve a configured long-lived ref."""

        exact = {
            str(value or "").strip()
            for value in (
                project.default_branch,
                project.branch,
                project.state_branch_name,
                *(project.supported_release_branches or []),
            )
            if str(value or "").strip()
        }
        if branch_name in exact:
            return True
        return any(
            fnmatchcase(branch_name, str(pattern).strip())
            for pattern in (project.branches or [])
            if str(pattern).strip()
        )

    def _is_owned_issue_branch(
        self,
        project: Project,
        issue_identifier: str,
        branch_name: str,
        *,
        is_epic: bool,
        issue_number: str | None = None,
    ) -> bool:
        """Restrict force deletion to branch names generated by Oompah."""

        identifier = _sanitize_identifier(issue_identifier)
        if is_epic:
            return branch_name == self.epic_branch_name(issue_identifier)
        if branch_name == identifier:
            return True
        # Older Oompah releases allocated some non-epic task workspaces using
        # the epic-named shape.  The exact same-identifier form remains
        # unambiguous: a child can never claim its parent's ``epic-*`` branch.
        if branch_name == self.epic_branch_name(issue_identifier):
            return True
        if issue_number:
            expected_github_branch = github_work_branch_name(
                project.name,
                issue_number,
            )
            if branch_name == expected_github_branch:
                return True
        return (
            branch_name.startswith("epic-")
            and branch_name.endswith(f"--task-{identifier}")
        )

    @staticmethod
    def _ref_exists(repo_path: str, ref: str) -> bool:
        try:
            result = subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", ref],
                cwd=repo_path,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectError(f"git ref check failed for {ref}: {exc}") from exc
        if result.returncode not in {0, 1}:
            raise ProjectError(
                f"git ref check failed for {ref}: {result.stderr.strip()[:500]}"
            )
        return result.returncode == 0

    def _delete_owned_issue_branch_locked(
        self,
        project: Project,
        issue_identifier: str,
        branch_name: str,
        *,
        is_epic: bool,
        issue_number: str | None = None,
    ) -> tuple[bool, str | None]:
        """Delete one terminal Oompah-owned branch locally and remotely.
        
        Returns (changed, skip_reason). skip_reason is None if the branch was
        deleted or attempted (changed=True or attempted), or a category string
        if skipped (changed=False): 'shared_epic_branch', 'protected_branch',
        'checked_out_in_worktree'.
        """

        branch_name = str(branch_name or "").strip()
        if not branch_name:
            return False, None
        if not self._is_owned_issue_branch(
            project,
            issue_identifier,
            branch_name,
            is_epic=is_epic,
            issue_number=issue_number,
        ):
            # Silently skip likely shared epic branches (epic-*) to avoid warning
            # floods when terminal child tasks legitimately share their parent's branch.
            # Only warn for ambiguous cases that might indicate misconfiguration.
            if branch_name.startswith("epic-"):
                # Likely a parent epic branch shared with child tasks.
                return False, "shared_epic_branch"
            logger.warning(
                "Skipping terminal branch not owned by issue project=%s "
                "issue=%s branch=%s",
                project.id,
                issue_identifier,
                branch_name,
            )
            return False, "not_owned"
        if self._branch_is_protected(project, branch_name):
            logger.warning(
                "Skipping protected terminal branch project=%s issue=%s branch=%s",
                project.id,
                issue_identifier,
                branch_name,
            )
            return False, "protected_branch"

        self._prune_git_worktrees(project.repo_path)
        if branch_name in self._registered_worktree_branches(project.repo_path):
            logger.warning(
                "Skipping terminal branch still checked out in a worktree "
                "project=%s issue=%s branch=%s",
                project.id,
                issue_identifier,
                branch_name,
            )
            return False, "checked_out_in_worktree"

        local_ref = f"refs/heads/{branch_name}"
        remote_ref = f"refs/remotes/origin/{branch_name}"
        local_exists = self._ref_exists(project.repo_path, local_ref)
        remote_exists = self._ref_exists(project.repo_path, remote_ref)
        changed = False

        # Preserve the local ref until the remote deletion succeeds. If the
        # push fails, a later pass can retry without losing the submitted head.
        if remote_exists:
            try:
                deleted = self._run_network_git(
                    project,
                    ["git", "push", "origin", "--delete", branch_name],
                    timeout=60,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ProjectError(
                    f"git remote branch delete failed for {branch_name}: {exc}"
                ) from exc
            if deleted.returncode != 0:
                raise ProjectError(
                    "git remote branch delete failed: "
                    f"{deleted.stderr.strip()[:500]}"
                )
            changed = True

        if local_exists:
            try:
                removed = subprocess.run(
                    ["git", "branch", "-D", "--", branch_name],
                    cwd=project.repo_path,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ProjectError(
                    f"git local branch delete failed for {branch_name}: {exc}"
                ) from exc
            if removed.returncode != 0:
                raise ProjectError(
                    "git local branch delete failed: "
                    f"{removed.stderr.strip()[:500]}"
                )
            changed = True

        if changed:
            logger.info(
                "Deleted terminal branch project=%s issue=%s branch=%s",
                project.id,
                issue_identifier,
                branch_name,
            )
        return changed, None

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

    def prepare_epic_branch_for_private_dispatch(
        self,
        project_id: str,
        epic_identifier: str,
    ) -> tuple[str, str]:
        """Return a clean epic worktree synchronized with its remote head.

        Private child branches must be cut from the newest published epic
        head. A clean local branch may safely fast-forward to a newer remote;
        local commits may safely publish when the remote is its ancestor.
        Divergence is left for a human/repair agent because choosing a side
        would discard work.
        """

        project = self._projects.get(project_id)
        if project is None:
            raise ProjectError(f"Unknown project: {project_id}")
        branch_name = self.epic_branch_name(epic_identifier)
        with self.project_write_lock(project_id):
            wt_path = self._create_epic_worktree_locked(
                project_id, epic_identifier
            )

            def _run(
                args: list[str],
                *,
                timeout: int = 60,
                check: bool = False,
            ) -> subprocess.CompletedProcess:
                try:
                    if args and args[0] in {"fetch", "pull", "push", "ls-remote"}:
                        result = self._run_network_git(
                            project,
                            ["git", "-C", wt_path, *args],
                            timeout=timeout,
                        )
                        if check and result.returncode != 0:
                            raise subprocess.CalledProcessError(
                                result.returncode,
                                ["git", "-C", wt_path, *args],
                                output=result.stdout,
                                stderr=result.stderr,
                            )
                        return result
                    return subprocess.run(
                        ["git", "-C", wt_path, *args],
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        check=check,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise ProjectError(
                        f"git {' '.join(args[:2])} timed out for {branch_name}"
                    ) from exc
                except subprocess.CalledProcessError as exc:
                    detail = (exc.stderr or exc.stdout or "").strip()[:500]
                    raise ProjectError(
                        f"git {' '.join(args[:2])} failed for {branch_name}: "
                        f"{detail}"
                    ) from exc

            status = _run(["status", "--porcelain"], timeout=10)
            dirty_lines = [
                line
                for line in status.stdout.splitlines()
                if not _is_generated_worktree_helper(
                    line[3:].strip() if len(line) >= 3 else ""
                )
            ]
            if status.returncode != 0 or dirty_lines:
                raise ProjectError(
                    f"Epic worktree {branch_name} is dirty; drain or repair "
                    "shared-mode work before dispatching private children"
                )
            fetch = _run(["fetch", "origin"])
            if fetch.returncode != 0:
                raise ProjectError(
                    f"Could not refresh epic branch {branch_name}: "
                    f"{fetch.stderr.strip()[:500]}"
                )

            remote_ref = f"origin/{branch_name}"
            remote = _run(["rev-parse", "--verify", remote_ref], timeout=10)
            if remote.returncode == 0:
                local_is_ancestor = _run(
                    ["merge-base", "--is-ancestor", "HEAD", remote_ref],
                    timeout=10,
                ).returncode == 0
                remote_is_ancestor = _run(
                    ["merge-base", "--is-ancestor", remote_ref, "HEAD"],
                    timeout=10,
                ).returncode == 0
                if local_is_ancestor:
                    reset = _run(["reset", "--hard", remote_ref], timeout=30)
                    if reset.returncode != 0:
                        raise ProjectError(
                            f"Could not fast-forward {branch_name} to its "
                            f"remote head: {reset.stderr.strip()[:500]}"
                        )
                elif not remote_is_ancestor:
                    raise ProjectError(
                        f"Epic branch {branch_name} diverged from {remote_ref}; "
                        "reconcile both heads before dispatching more children"
                    )

            push = _run(
                [
                    "push",
                    "--set-upstream",
                    "origin",
                    f"HEAD:{branch_name}",
                ]
            )
            if push.returncode != 0:
                raise ProjectError(
                    f"Could not publish epic integration branch {branch_name}: "
                    f"{push.stderr.strip()[:500]}"
                )
            head = _run(["rev-parse", "HEAD"], timeout=10)
            if head.returncode != 0 or not head.stdout.strip():
                raise ProjectError(
                    f"Could not resolve current head for {branch_name}"
                )
            return wt_path, head.stdout.strip()

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
            self._run_network_git(
                project,
                ["git", "fetch", "origin"],
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
        per-issue worktree), this one preserves any in-flight commits on
        the shared epic branch so a previous child's work isn't lost.
        We still fetch, ensure the branch is checked out, and disable
        hooks; we do NOT ``git reset --hard`` or ``git clean``.
        """

        def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
            timeout = kw.pop("timeout", 30)
            check = kw.pop("check", False)
            if len(cmd) > 1 and cmd[1] in {
                "fetch",
                "pull",
                "push",
                "ls-remote",
            }:
                result = self._run_network_git(
                    project,
                    cmd,
                    cwd=wt_path,
                    timeout=timeout,
                )
                if check and result.returncode != 0:
                    raise subprocess.CalledProcessError(
                        result.returncode,
                        cmd,
                        output=result.stdout,
                        stderr=result.stderr,
                    )
                return result
            kw.setdefault("env", _recovery_git_env())
            return subprocess.run(
                cmd,
                cwd=wt_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check,
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

    def remove_epic_worktree(self, project_id: str, epic_identifier: str) -> bool:
        """Remove the shared epic worktree (used after the epic→main PR
        merges or when the operator deletes a project).

        Mirrors :meth:`remove_worktree` but with the epic-named directory
        and a tolerant fall-through when the worktree no longer exists.
        Returns whether a directory was removed.
        """
        # Acquire per-project lock so concurrent remove operations are serialized.
        with self.project_write_lock(project_id):
            return self._remove_epic_worktree_locked(project_id, epic_identifier)

    def _remove_epic_worktree_locked(
        self, project_id: str, epic_identifier: str
    ) -> bool:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        wt_path = self.epic_worktree_path_for(project_id, epic_identifier)
        if not os.path.isdir(wt_path):
            self._prune_git_worktrees(project.repo_path)
            return False

        # ``remove_worktree`` is used by termination cleanup as well as
        # terminal maintenance.  Never force-remove a live operation or dirty
        # task worktree here; the snapshot must succeed first and active Git
        # state must remain inspectable for a retry.
        if _is_git_working_tree(wt_path):
            status = self._git_status_for_worktree(wt_path)
            if status.returncode != 0:
                raise ProjectError(
                    f"cannot inspect worktree before removal {wt_path}: "
                    f"{status.stderr.strip()[:500]}"
                )
            branch_probe = subprocess.run(
                ["git", "symbolic-ref", "--short", "HEAD"],
                cwd=wt_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                env=_recovery_git_env(),
            )
            operation = _git_operation_state(
                wt_path,
                current_branch=branch_probe.stdout.strip(),
                branch_result_code=branch_probe.returncode,
            )
            if operation:
                recovery = self._preserve_dirty_worktree_locked(
                    project,
                    issue_identifier,
                    wt_path,
                    branch_name=str(operation.get("branch") or "") or None,
                )
                raise ProjectError(
                    f"Refusing to remove active {operation.get('kind')} worktree "
                    f"{wt_path}; recovery snapshot "
                    f"{recovery.get('recovery_ref') if recovery else 'unavailable'} "
                    "was preserved"
                )
            if self._worktree_dirty_paths(status.stdout):
                recovery = self._preserve_dirty_worktree_locked(
                    project,
                    issue_identifier,
                    wt_path,
                    branch_name=branch_probe.stdout.strip() or None,
                )
                raise ProjectError(
                    f"Refusing to remove dirty task worktree {wt_path}; recovery "
                    f"snapshot {recovery.get('recovery_ref') if recovery else 'unavailable'} "
                    "was preserved"
                )

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
            if not _is_stale_worktree_remove_error(stderr):
                raise ProjectError(f"git worktree remove failed: {stderr}")
            if _is_git_working_tree(wt_path):
                raise ProjectError(
                    f"Refusing to remove valid Git worktree not owned by project: {wt_path}"
                )
            _safe_remove_managed_dir(wt_path, self._project_worktree_root(project))
        except subprocess.TimeoutExpired:
            raise ProjectError("git worktree remove timed out")
        finally:
            self._prune_git_worktrees(project.repo_path)
        logger.info("Epic worktree removed path=%s", wt_path)
        return True

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
        # sanitized identifier for native tasks.
        branch_name = branch_name or _sanitize_identifier(issue_identifier)

        if os.path.isdir(wt_path):
            logger.info("Worktree already exists path=%s", wt_path)
            self._prepare_existing_worktree(
                wt_path,
                branch_name,
                project,
                issue_identifier=issue_identifier,
            )
            return wt_path

        os.makedirs(os.path.dirname(wt_path), exist_ok=True)

        # Fetch latest from remote before creating worktree
        try:
            self._run_network_git(
                project,
                ["git", "fetch", "origin"],
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
        *,
        issue_identifier: str | None = None,
    ) -> None:
        """Reuse an existing task worktree without discarding task-owned work."""

        def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
            timeout = kw.pop("timeout", 30)
            check = kw.pop("check", False)
            if len(cmd) > 1 and cmd[1] in {
                "fetch",
                "pull",
                "push",
                "ls-remote",
            }:
                result = self._run_network_git(
                    project,
                    cmd,
                    cwd=wt_path,
                    timeout=timeout,
                )
                if check and result.returncode != 0:
                    raise subprocess.CalledProcessError(
                        result.returncode,
                        cmd,
                        output=result.stdout,
                        stderr=result.stderr,
                    )
                return result
            kw.setdefault("env", _recovery_git_env())
            return subprocess.run(
                cmd,
                cwd=wt_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=check,
                **kw,
            )

        # A queue item can be stale or malformed.  Do not reset, clean, or
        # check out another branch until we know this registered task path is
        # still attached to the branch it was created for.
        try:
            r = _run(["git", "symbolic-ref", "--short", "HEAD"])
            current_branch = r.stdout.strip() if r.returncode == 0 else ""
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            current_branch = ""
        operation = _git_operation_state(
            wt_path,
            current_branch=current_branch,
            branch_result_code=0 if current_branch else 128,
        )
        operation_branch = str(operation.get("branch") or "").strip() if operation else ""
        if current_branch != branch_name and operation_branch != branch_name:
            raise ProjectError(
                f"Task worktree {wt_path} is on "
                f"{current_branch or ('active ' + str(operation.get('kind')) if operation else 'a detached HEAD')}, not expected branch "
                f"{branch_name}; refusing to reset it"
            )

        recovery_identifier = issue_identifier or branch_name
        # This check must happen before fetch/reset/clean.  A terminated worker
        # intentionally leaves its task worktree in place for retry, and the
        # old implementation erased that state here.
        recovery = self._preserve_dirty_worktree_locked(
            project,
            recovery_identifier,
            wt_path,
            branch_name=branch_name,
        )
        if recovery and recovery.get("snapshot_head"):
            logger.info(
                "Reusing task worktree with durable recovery snapshot "
                "project=%s issue=%s ref=%s head=%s operation=%s",
                project.id,
                recovery_identifier,
                recovery.get("recovery_ref"),
                recovery.get("snapshot_head"),
                (recovery.get("operation") or {}).get("kind")
                if isinstance(recovery.get("operation"), dict)
                else None,
            )
            self._disable_worktree_hooks(wt_path)
            return

        # Fetch latest from remote.
        try:
            _run(["git", "fetch", "origin"])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        # Discard any uncommitted changes from a previous run only after the
        # branch check above has confirmed this is the intended task checkout.
        try:
            _run(["git", "reset", "--hard"])
            _run(["git", "clean", "-fd"])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

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
                env=_recovery_git_env(),
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

    def remove_worktree(self, project_id: str, issue_identifier: str) -> bool:
        # Acquire the per-project lock so concurrent dispatch and maintenance
        # operations (e.g. self-heal removing a worktree while dispatch creates
        # one) for the same project are serialized.
        with self.project_write_lock(project_id):
            return self._remove_worktree_locked(project_id, issue_identifier)

    def _assert_terminal_worktree_safe_locked(
        self,
        project: Project,
        issue_identifier: str,
        wt_path: str,
        *,
        branch_name: str,
    ) -> None:
        """Refuse terminal removal unless dirty work is durably preserved.

        Terminal cleanup is allowed for clean work whose head is already
        published on its branch or reachable from the default branch.  A
        local-only head is retained because removing its worktree would make
        the task's only copy unrecoverable.
        """

        if not _is_git_working_tree(wt_path):
            return
        status = self._git_status_for_worktree(wt_path)
        if status.returncode != 0:
            raise ProjectError(
                f"cannot inspect terminal worktree {wt_path}: "
                f"{status.stderr.strip()[:500]}"
            )
        branch_probe = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env=_recovery_git_env(),
        )
        operation = _git_operation_state(
            wt_path,
            current_branch=branch_probe.stdout.strip(),
            branch_result_code=branch_probe.returncode,
        )
        if operation:
            operation_branch = str(operation.get("branch") or "").strip()
            if operation_branch and operation_branch != branch_name:
                raise ProjectError(
                    f"Refusing terminal cleanup of {wt_path}: active "
                    f"{operation.get('kind')} belongs to {operation_branch!r}, "
                    f"not {branch_name!r}"
                )
            recovery = self._preserve_dirty_worktree_locked(
                project,
                issue_identifier,
                wt_path,
                branch_name=branch_name,
            )
            logger.warning(
                "terminal cleanup preserved active-operation recovery issue=%s "
                "operation=%s ref=%s",
                issue_identifier,
                operation.get("kind"),
                recovery.get("recovery_ref") if recovery else None,
            )
            raise ProjectError(
                f"Refusing terminal cleanup of active {operation.get('kind')} "
                f"worktree {wt_path}; recovery state was preserved"
            )
        if self._worktree_dirty_paths(status.stdout):
            recovery = self._preserve_dirty_worktree_locked(
                project,
                issue_identifier,
                wt_path,
                branch_name=branch_name,
            )
            raise ProjectError(
                f"Refusing terminal cleanup of dirty task worktree {wt_path}; "
                f"recovery snapshot {recovery.get('recovery_ref') if recovery else 'unavailable'} "
                "was preserved"
            )

        current_branch = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if current_branch.returncode != 0 or current_branch.stdout.strip() != branch_name:
            raise ProjectError(
                f"Refusing terminal cleanup of {wt_path}: expected branch "
                f"{branch_name!r}, found {current_branch.stdout.strip()!r}"
            )

        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if head.returncode != 0 or not head.stdout.strip():
            raise ProjectError(
                f"cannot prove terminal worktree head for {issue_identifier}"
            )
        head_sha = head.stdout.strip()

        published = subprocess.run(
            ["git", "merge-base", "--is-ancestor", "HEAD", f"origin/{branch_name}"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        ).returncode == 0
        merged = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                "HEAD",
                f"origin/{project.default_branch}",
            ],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        ).returncode == 0
        if not published and not merged:
            raise ProjectError(
                f"Refusing terminal cleanup of unpublished task worktree "
                f"{wt_path}; head {head_sha} has no pushed or merged evidence"
            )

    def _remove_worktree_locked(
        self, project_id: str, issue_identifier: str
    ) -> bool:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        wt_path = self.worktree_path_for(project_id, issue_identifier)
        if not os.path.isdir(wt_path):
            self._prune_git_worktrees(project.repo_path)
            return False

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
            if not _is_stale_worktree_remove_error(stderr):
                raise ProjectError(f"git worktree remove failed: {stderr}")
            if _is_git_working_tree(wt_path):
                raise ProjectError(
                    f"Refusing to remove valid Git worktree not owned by project: {wt_path}"
                )
            _safe_remove_managed_dir(wt_path, self._project_worktree_root(project))
        except subprocess.TimeoutExpired:
            raise ProjectError("git worktree remove timed out")
        finally:
            self._prune_git_worktrees(project.repo_path)

        logger.info("Worktree removed path=%s", wt_path)
        return True

    def _cleanup_epic_repair_workspace_locked(
        self,
        project_id: str,
        issue_identifier: str,
    ) -> bool:
        """Remove the task-style repair worktree left by an epic repair/planner run.

        A terminal epic records ``work_branch=epic-<id>`` for its primary
        shared worktree.  When an epic repair or planner agent runs under a
        task-style context it may create an *auxiliary* managed worktree at
        ``<worktree_root>/<project>/<id>`` on branch ``<id>`` — identical to
        what a regular task worktree uses.  This residue is safe to remove
        only when ALL of the following hold:

        - The path is the **exact managed registered** worktree for this
          identifier (``worktree_path_for``), not an arbitrary directory.
        - The **exact same-identifier branch** (``<id>``, not ``epic-<id>``)
          is checked out in the worktree.
        - The worktree is **clean** (``git status --porcelain`` is empty,
          ignoring the ``.oompah-no-hooks`` sentinel).
        - The branch head is an **ancestor** of ``origin/<default_branch>``
          (i.e. the work is already merged).

        The method never infers arbitrary paths, tolerates shared branches,
        removes dirty worktrees, or deletes unmerged heads.  It is called
        only for terminal *epic* records and is a no-op when no such
        auxiliary workspace exists.

        Returns ``True`` when the worktree and/or branch were removed.
        """
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        # The repair workspace uses the exact task-style path and branch name.
        repair_branch = _sanitize_identifier(issue_identifier)
        repair_path = self.worktree_path_for(project_id, issue_identifier)

        if not os.path.isdir(repair_path):
            return False

        # Guard 1: the path must be a registered managed git worktree.
        registered_paths = self._registered_worktree_paths(project.repo_path)
        if os.path.realpath(repair_path) not in registered_paths:
            logger.debug(
                "Epic repair workspace exists but is not a registered worktree; "
                "skipping cleanup path=%s",
                repair_path,
            )
            return False

        # Guard 2: the exact same-identifier branch must be checked out.
        try:
            head_result = subprocess.run(
                ["git", "symbolic-ref", "--short", "HEAD"],
                cwd=repair_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectError(
                f"git symbolic-ref failed in repair workspace {repair_path}: {exc}"
            ) from exc

        checked_out_branch = head_result.stdout.strip()
        if head_result.returncode != 0 or checked_out_branch != repair_branch:
            logger.debug(
                "Epic repair workspace branch mismatch; skipping cleanup "
                "path=%s expected=%s found=%s",
                repair_path,
                repair_branch,
                checked_out_branch if head_result.returncode == 0 else "(detached)",
            )
            return False

        # Guard 3: the worktree must be clean (no uncommitted changes).
        try:
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repair_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectError(
                f"git status failed in repair workspace {repair_path}: {exc}"
            ) from exc

        dirty_lines = [
            line
            for line in status_result.stdout.splitlines()
            if not _is_generated_worktree_helper(
                line[3:].strip() if len(line) >= 3 else ""
            )
        ]
        if status_result.returncode != 0 or dirty_lines:
            logger.warning(
                "Epic repair workspace is dirty; skipping cleanup "
                "project=%s identifier=%s path=%s",
                project.id,
                issue_identifier,
                repair_path,
            )
            return False

        # Guard 4: the branch head must be fully merged into the default branch.
        default_ref = f"origin/{project.default_branch}"
        try:
            ancestor_result = subprocess.run(
                [
                    "git",
                    "merge-base",
                    "--is-ancestor",
                    repair_branch,
                    default_ref,
                ],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectError(
                f"git merge-base ancestry check failed for repair branch "
                f"{repair_branch}: {exc}"
            ) from exc

        if ancestor_result.returncode != 0:
            logger.warning(
                "Epic repair workspace branch is not merged; skipping cleanup "
                "project=%s identifier=%s branch=%s",
                project.id,
                issue_identifier,
                repair_branch,
            )
            return False

        # All guards passed — remove the repair worktree then its branch.
        worktree_removed = self._remove_worktree_locked(project_id, issue_identifier)
        branch_removed, _skip_reason = self._delete_owned_issue_branch_locked(
            project,
            issue_identifier,
            repair_branch,
            is_epic=False,
            issue_number=None,
        )
        if worktree_removed or branch_removed:
            logger.info(
                "Removed epic repair workspace project=%s identifier=%s "
                "path=%s branch=%s",
                project.id,
                issue_identifier,
                repair_path,
                repair_branch,
            )
        return worktree_removed or branch_removed

    def _cleanup_direct_epic_auxiliary_workspace_locked(
        self,
        project_id: str,
        issue_identifier: str,
        recorded_branch: str,
    ) -> tuple[bool, str | None] | None:
        """Prune a private checkout accidentally allocated to a direct epic task.

        A direct epic maintenance task records the shared branch
        ``epic-<parent>`` even when an ordinary dispatch has already allocated
        its managed issue path on ``epic-<parent>--task-<issue>``.  The shared
        epic worktree must never be inferred from the issue path.  This helper
        therefore returns a result only after it has identified the exact
        derived branch at the exact registered task path; otherwise ``None``
        leaves the existing terminal-cleanup behavior in charge.

        Unlike ordinary terminal branch cleanup, this path deletes only the
        exact local derived ref.  A remote private branch can be the durable
        evidence that makes the local checkout disposable, so it is
        intentionally never deleted here.
        """

        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        recorded = str(recorded_branch or "").strip()
        epic_prefix = "epic-"
        if not recorded.startswith(epic_prefix):
            return None
        parent_identifier = recorded[len(epic_prefix) :]
        if not parent_identifier or self.epic_branch_name(parent_identifier) != recorded:
            return None

        derived_branch = self.epic_child_branch_name(
            parent_identifier,
            issue_identifier,
        )
        auxiliary_path = self.worktree_path_for(project_id, issue_identifier)
        if not os.path.isdir(auxiliary_path):
            return None

        try:
            checked_out = subprocess.run(
                ["git", "symbolic-ref", "--short", "HEAD"],
                cwd=auxiliary_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                env=_recovery_git_env(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectError(
                f"git branch identity check failed for direct epic auxiliary "
                f"workspace {auxiliary_path}: {exc}"
            ) from exc

        if checked_out.returncode != 0 or checked_out.stdout.strip() != derived_branch:
            # Returning None is deliberate: the normal cleanup path will then
            # report the existing branch mismatch without touching this path.
            return None

        registered_paths = self._registered_worktree_paths(project.repo_path)
        if os.path.realpath(auxiliary_path) not in registered_paths:
            logger.warning(
                "Direct epic auxiliary workspace is not registered; preserving "
                "project=%s issue=%s path=%s branch=%s",
                project.id,
                issue_identifier,
                auxiliary_path,
                derived_branch,
            )
            return False, "direct_epic_auxiliary_unregistered"

        branch_paths = self._registered_worktree_branch_paths(project.repo_path)
        other_checkouts = branch_paths.get(derived_branch, set()) - {
            os.path.realpath(auxiliary_path)
        }
        if other_checkouts:
            logger.warning(
                "Direct epic auxiliary branch is checked out elsewhere; "
                "preserving project=%s issue=%s branch=%s paths=%s",
                project.id,
                issue_identifier,
                derived_branch,
                sorted(other_checkouts),
            )
            return False, "direct_epic_auxiliary_shared_checkout"

        operation = _git_operation_state(
            auxiliary_path,
            current_branch=derived_branch,
            branch_result_code=0,
        )
        if operation:
            logger.warning(
                "Direct epic auxiliary workspace has active Git operation; "
                "preserving project=%s issue=%s operation=%s path=%s",
                project.id,
                issue_identifier,
                operation.get("kind"),
                auxiliary_path,
            )
            return False, "direct_epic_auxiliary_active_operation"

        recovery = self._recovery_context_from_ref(project, issue_identifier)
        if recovery:
            logger.warning(
                "Direct epic auxiliary workspace has recovery evidence; "
                "preserving project=%s issue=%s ref=%s",
                project.id,
                issue_identifier,
                recovery.get("recovery_ref"),
            )
            return False, "direct_epic_auxiliary_recovery"

        status = self._git_status_for_worktree(auxiliary_path)
        if status.returncode != 0:
            raise ProjectError(
                f"cannot inspect direct epic auxiliary workspace {auxiliary_path}: "
                f"{status.stderr.strip()[:500]}"
            )
        if self._worktree_dirty_paths(status.stdout):
            logger.warning(
                "Direct epic auxiliary workspace is dirty; preserving "
                "project=%s issue=%s path=%s",
                project.id,
                issue_identifier,
                auxiliary_path,
            )
            return False, "direct_epic_auxiliary_dirty"

        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=auxiliary_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env=_recovery_git_env(),
        )
        if head.returncode != 0 or not head.stdout.strip():
            raise ProjectError(
                f"cannot prove direct epic auxiliary head for {issue_identifier}"
            )
        head_sha = head.stdout.strip()

        local_head = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{derived_branch}"],
            cwd=project.repo_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env=_recovery_git_env(),
        )
        if local_head.returncode != 0 or local_head.stdout.strip() != head_sha:
            logger.warning(
                "Direct epic auxiliary local ref changed; preserving "
                "project=%s issue=%s branch=%s head=%s",
                project.id,
                issue_identifier,
                derived_branch,
                head_sha,
            )
            return False, "direct_epic_auxiliary_ref_changed"

        # Only the default branch, the authoritative epic branch, and private
        # branches derived from that same epic are trusted reachability
        # evidence.  In particular, an unrelated project/task branch cannot
        # make this workspace eligible for deletion.
        remote_refs = subprocess.run(
            [
                "git",
                "for-each-ref",
                "--format=%(refname:short)",
                "refs/remotes/origin",
            ],
            cwd=project.repo_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env=_recovery_git_env(),
        )
        if remote_refs.returncode != 0:
            raise ProjectError(
                "could not inspect direct epic auxiliary remote evidence: "
                f"{remote_refs.stderr.strip()[:500]}"
            )
        remote_branches = {
            line.strip()[len("origin/") :]
            for line in remote_refs.stdout.splitlines()
            if line.strip().startswith("origin/")
            and line.strip() != "origin/HEAD"
        }
        trusted_branches = {
            project.default_branch,
            recorded,
            derived_branch,
        }
        trusted_branches.update(
            branch
            for branch in remote_branches
            if branch.startswith(f"{recorded}--task-")
            and branch[len(f"{recorded}--task-") :].strip()
        )

        evidence_branch = None
        for branch in sorted(trusted_branches):
            if branch not in remote_branches:
                continue
            ancestry = subprocess.run(
                [
                    "git",
                    "merge-base",
                    "--is-ancestor",
                    head_sha,
                    f"refs/remotes/origin/{branch}",
                ],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
                env=_recovery_git_env(),
            )
            if ancestry.returncode == 0:
                evidence_branch = branch
                break

        if evidence_branch is None:
            logger.warning(
                "Direct epic auxiliary head has no durable pushed/merged "
                "evidence; preserving project=%s issue=%s branch=%s head=%s",
                project.id,
                issue_identifier,
                derived_branch,
                head_sha,
            )
            return False, "direct_epic_auxiliary_unpublished"

        if self._branch_is_protected(project, derived_branch):
            logger.warning(
                "Direct epic auxiliary branch is protected; preserving "
                "project=%s issue=%s branch=%s",
                project.id,
                issue_identifier,
                derived_branch,
            )
            return False, "direct_epic_auxiliary_protected"

        worktree_removed = self._remove_worktree_locked(
            project_id,
            issue_identifier,
        )
        if not worktree_removed:
            return False, "direct_epic_auxiliary_missing_worktree"

        removed_ref = subprocess.run(
            [
                "git",
                "update-ref",
                "-d",
                f"refs/heads/{derived_branch}",
                head_sha,
            ],
            cwd=project.repo_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env=_recovery_git_env(),
        )
        if removed_ref.returncode != 0:
            raise ProjectError(
                "direct epic auxiliary local ref changed during cleanup for "
                f"{issue_identifier}; worktree was removed but ref was preserved: "
                f"{removed_ref.stderr.strip()[:500]}"
            )

        logger.info(
            "Removed direct epic auxiliary workspace project=%s issue=%s "
            "path=%s local_branch=%s evidence=origin/%s",
            project.id,
            issue_identifier,
            auxiliary_path,
            derived_branch,
            evidence_branch,
        )
        return True, None

    def cleanup_terminal_issue(
        self,
        project_id: str,
        issue_identifier: str,
        *,
        branch_name: str | None = None,
        is_epic: bool = False,
        issue_number: str | None = None,
    ) -> tuple[bool, str | None]:
        """Remove one terminal issue's worktree and Oompah-owned branch.

        The tracker-provided branch is accepted only when it matches a branch
        shape Oompah generates for this exact issue. This prevents stale or
        manually edited metadata from targeting a shared epic, default, state,
        release, or other operator-owned branch.

        For terminal epics, also removes any auxiliary task-style repair
        workspace at ``<worktree_root>/<project>/<id>`` on branch ``<id>``
        left by an epic repair/planner run, subject to the strict ownership
        and ancestry guards in ``_cleanup_epic_repair_workspace_locked``.

        Returns (changed, skip_reason). changed indicates whether either the
        worktree, branch, or auxiliary repair workspace was actually removed.
        skip_reason is None if the branch was removed or attempted, or a
        category string if skipped ('shared_epic_branch', 'protected_branch',
        'checked_out_in_worktree').
        """

        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        candidate = str(branch_name or "").strip()
        if not candidate:
            legacy_epic_worktree = self.epic_worktree_path_for(
                project_id,
                issue_identifier,
            )
            if not is_epic and os.path.isdir(legacy_epic_worktree):
                candidate = self.epic_branch_name(issue_identifier)
            else:
                candidate = (
                    self.epic_branch_name(issue_identifier)
                    if is_epic
                    else _sanitize_identifier(issue_identifier)
                )
        legacy_epic_task = (
            not is_epic
            and candidate == self.epic_branch_name(issue_identifier)
        )

        with self.project_write_lock(project_id):
            if not is_epic:
                auxiliary_result = (
                    self._cleanup_direct_epic_auxiliary_workspace_locked(
                        project_id,
                        issue_identifier,
                        candidate,
                    )
                )
                if auxiliary_result is not None:
                    return auxiliary_result

            if is_epic or legacy_epic_task:
                epic_path = self.epic_worktree_path_for(project_id, issue_identifier)
                if os.path.isdir(epic_path):
                    self._assert_terminal_worktree_safe_locked(
                        project,
                        issue_identifier,
                        epic_path,
                        branch_name=candidate,
                    )
                worktree_removed = self._remove_epic_worktree_locked(
                    project_id,
                    issue_identifier,
                )
            else:
                task_path = self.worktree_path_for(project_id, issue_identifier)
                if os.path.isdir(task_path):
                    self._assert_terminal_worktree_safe_locked(
                        project,
                        issue_identifier,
                        task_path,
                        branch_name=candidate,
                    )
                worktree_removed = self._remove_worktree_locked(
                    project_id,
                    issue_identifier,
                )
            branch_removed, skip_reason = self._delete_owned_issue_branch_locked(
                project,
                issue_identifier,
                candidate,
                is_epic=is_epic,
                issue_number=issue_number,
            )
            # For terminal epics, also clean up any auxiliary task-style repair
            # workspace left by an epic repair/planner run (e.g. the OOMPAH-459
            # residue shape: worktree at <root>/<id> on branch <id>).
            repair_removed = False
            if is_epic:
                repair_removed = self._cleanup_epic_repair_workspace_locked(
                    project_id,
                    issue_identifier,
                )
            if branch_removed:
                recovery_ref = _worktree_recovery_ref(issue_identifier)
                removed_ref = subprocess.run(
                    ["git", "update-ref", "-d", recovery_ref],
                    cwd=project.repo_path,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
                if removed_ref.returncode != 0:
                    raise ProjectError(
                        "could not remove terminal recovery ref: "
                        f"{removed_ref.stderr.strip()[:500]}"
                    )
        return worktree_removed or branch_removed or repair_removed, skip_reason

    def cleanup_stale_worktree_dirs(
        self, project_id: str, limit: int | None = None
    ) -> tuple[int, bool]:
        """Remove managed worktree directories Git no longer registers.

        Returns ``(removed_count, deferred)``.  ``deferred`` is true when the
        caller-provided limit was reached before all stale directories were
        removed.
        """
        with self.project_write_lock(project_id):
            return self._cleanup_stale_worktree_dirs_locked(project_id, limit)

    def _cleanup_stale_worktree_dirs_locked(
        self, project_id: str, limit: int | None = None
    ) -> tuple[int, bool]:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        if limit is not None and limit <= 0:
            return 0, True

        project_root = self._project_worktree_root(project)
        self._prune_git_worktrees(project.repo_path)
        if not os.path.isdir(project_root):
            return 0, False

        registered = self._registered_worktree_paths(project.repo_path)
        removed = 0
        deferred = False
        for entry in sorted(os.listdir(project_root)):
            path = os.path.join(project_root, entry)
            if not os.path.isdir(path) or os.path.islink(path):
                continue
            if os.path.realpath(path) in registered:
                continue
            if _is_git_working_tree(path):
                logger.warning(
                    "Skipping unregistered but valid Git worktree path=%s",
                    path,
                )
                continue
            if limit is not None and removed >= limit:
                deferred = True
                break
            _safe_remove_managed_dir(path, project_root)
            removed += 1
            logger.info("Removed stale worktree directory path=%s", path)

        try:
            os.rmdir(project_root)
        except OSError:
            pass
        return removed, deferred

    def cleanup_stale_local_branches(
        self,
        project_id: str,
        limit: int | None = None,
    ) -> tuple[int, bool]:
        """Delete fully merged local branches whose configured upstream is gone.

        This sweep handles old branches that predate terminal task cleanup or
        were created manually. It never force-deletes unmerged work and skips
        configured long-lived branches plus every branch checked out in a
        worktree. Returns ``(removed_count, deferred)``.
        """

        with self.project_write_lock(project_id):
            project = self._projects.get(project_id)
            if not project:
                raise ProjectError(f"Unknown project: {project_id}")
            if limit is not None and limit <= 0:
                return 0, True

            self._prune_git_worktrees(project.repo_path)
            checked_out = self._registered_worktree_branches(project.repo_path)
            try:
                listed = subprocess.run(
                    [
                        "git",
                        "for-each-ref",
                        "--format=%(refname:short)%09%(upstream:track)",
                        "refs/heads",
                    ],
                    cwd=project.repo_path,
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError as exc:
                raise ProjectError(
                    "git local branch listing failed: "
                    f"{exc.stderr.strip()[:500] if exc.stderr else ''}"
                ) from exc
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ProjectError(f"git local branch listing failed: {exc}") from exc

            removed = 0
            deferred = False
            default_ref = f"origin/{project.default_branch}"
            for line in listed.stdout.splitlines():
                branch, _separator, tracking = line.partition("\t")
                if tracking.strip() != "[gone]":
                    continue
                if (
                    not branch
                    or branch in checked_out
                    or self._branch_is_protected(project, branch)
                ):
                    continue
                try:
                    merged = subprocess.run(
                        [
                            "git",
                            "merge-base",
                            "--is-ancestor",
                            branch,
                            default_ref,
                        ],
                        cwd=project.repo_path,
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise ProjectError(
                        f"git branch ancestry check failed for {branch}: {exc}"
                    ) from exc
                if merged.returncode != 0:
                    continue
                if limit is not None and removed >= limit:
                    deferred = True
                    break
                try:
                    deleted = subprocess.run(
                        ["git", "branch", "-D", "--", branch],
                        cwd=project.repo_path,
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise ProjectError(
                        f"git local branch delete failed for {branch}: {exc}"
                    ) from exc
                if deleted.returncode != 0:
                    raise ProjectError(
                        "git local branch delete failed: "
                        f"{deleted.stderr.strip()[:500]}"
                    )
                removed += 1
                logger.info(
                    "Pruned merged local branch with gone upstream "
                    "project=%s branch=%s",
                    project.id,
                    branch,
                )
            return removed, deferred

    def list_worktrees(self, project_id: str) -> list[str]:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")

        wt_root = self._project_worktree_root(project)
        if not os.path.isdir(wt_root):
            return []

        paths = []
        for entry in sorted(os.listdir(wt_root)):
            full = os.path.join(wt_root, entry)
            if os.path.isdir(full):
                paths.append(full)
        return paths
