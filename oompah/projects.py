"""Project storage and git worktree management."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from oompah.attachments import AttachmentStore
from oompah.models import Project

logger = logging.getLogger(__name__)


def _bootstrap_lfs(repo_path: str) -> bool:
    """Run `git lfs install --local` in ``repo_path`` and write the
    attachments .gitattributes. Idempotent.

    Returns ``True`` when LFS is configured and ready, ``False`` when
    ``git lfs`` isn't installed or `install` failed. The caller stores
    this as :attr:`Project.lfs_available`; multimodal-attachment features
    silently no-op when it's ``False``.
    """
    try:
        subprocess.run(
            ["git", "lfs", "install", "--local"],
            cwd=repo_path,
            capture_output=True, text=True,
            check=True, timeout=15,
        )
    except FileNotFoundError:
        logger.warning("git lfs not installed; attachments disabled for %s", repo_path)
        return False
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        stderr = (getattr(exc, "stderr", "") or "").strip()[:200]
        logger.warning("git lfs install failed for %s: %s", repo_path, stderr or exc)
        return False
    try:
        AttachmentStore(repo_path).ensure_lfs_configured()
    except Exception as exc:
        logger.warning("attachments .gitattributes write failed for %s: %s", repo_path, exc)
        return False
    return True

DEFAULT_PROJECTS_PATH = ".oompah/projects.json"
DEFAULT_REPOS_ROOT = os.path.join(os.path.expanduser("~"), ".oompah", "repos")
DEFAULT_WORKTREE_ROOT = os.path.join(os.path.expanduser("~"), ".oompah", "worktrees")

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _repo_name_from_url(url: str) -> str:
    """Extract a repo name from a git URL.

    Examples:
        https://github.com/org/repo.git -> repo
        git@github.com:org/repo.git     -> repo
        /local/path/to/repo             -> repo
    """
    # Strip trailing slashes and .git suffix
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    # Get the last path component
    name = url.rsplit("/", 1)[-1]
    # Handle ssh-style git@host:org/repo
    if ":" in name and not name.startswith("/"):
        name = name.rsplit(":", 1)[-1].rsplit("/", 1)[-1]
    return name or "unnamed"


def _sanitize_identifier(identifier: str) -> str:
    """Replace any character not in [A-Za-z0-9._-] with underscore."""
    return _SAFE_CHARS.sub("_", identifier)


class ProjectError(Exception):
    """Raised when project operations fail."""


class ProjectStore:
    """File-backed store for project configurations."""

    def __init__(self, path: str | None = None, repos_root: str | None = None,
                 worktree_root: str | None = None):
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

    def create(self, repo_url: str, name: str | None = None,
               branch: str = "main",
               git_user_name: str | None = None,
               git_user_email: str | None = None,
               access_token: str | None = None) -> Project:
        """Register a project by cloning its git repo.

        Args:
            repo_url: Git clone URL (https or ssh) or local path.
            name: Optional display name. Defaults to repo name from URL.
            branch: Branch to track. Defaults to "main".
        """
        if not name:
            name = _repo_name_from_url(repo_url)

        # Clone into ~/.oompah/repos/<name>/
        repo_path = os.path.join(self.repos_root, _sanitize_identifier(name))

        if os.path.isdir(repo_path):
            # Already cloned — pull latest
            logger.info("Repo already cloned at %s, pulling latest", repo_path)
            try:
                subprocess.run(
                    ["git", "fetch", "--all"],
                    cwd=repo_path, capture_output=True, text=True,
                    check=True, timeout=120,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                logger.warning("git fetch failed for %s: %s", repo_path, exc)
        else:
            os.makedirs(os.path.dirname(repo_path), exist_ok=True)
            try:
                subprocess.run(
                    ["git", "clone", "--branch", branch, repo_url, repo_path],
                    capture_output=True, text=True, check=True, timeout=300,
                )
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.strip()[:500] if exc.stderr else ""
                raise ProjectError(f"git clone failed: {stderr}")
            except subprocess.TimeoutExpired:
                raise ProjectError("git clone timed out")

        # Validate clone
        if not os.path.isdir(os.path.join(repo_path, ".git")):
            raise ProjectError(f"Clone succeeded but no .git/ found in: {repo_path}")
        if not os.path.isdir(os.path.join(repo_path, ".beads")):
            raise ProjectError(
                f"Repo cloned but no .beads/ directory found. "
                f"Run 'bd init' in {repo_path} to set up beads issue tracking."
            )

        # If git_user_name / git_user_email not provided, read global git config
        if not git_user_name:
            try:
                r = subprocess.run(
                    ["git", "config", "--global", "user.name"],
                    capture_output=True, text=True, timeout=5,
                )
                git_user_name = r.stdout.strip() or None
            except Exception:
                pass
        if not git_user_email:
            try:
                r = subprocess.run(
                    ["git", "config", "--global", "user.email"],
                    capture_output=True, text=True, timeout=5,
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
                    cwd=repo_path, capture_output=True, text=True, timeout=5,
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
            branch=branch,
            git_user_name=git_user_name,
            git_user_email=git_user_email,
            access_token=access_token,
            lfs_available=lfs_available,
        )
        self._projects[project_id] = project
        self._save()
        logger.info(
            "Project created id=%s name=%s repo=%s lfs_available=%s",
            project_id, name, repo_url, lfs_available,
        )
        return project

    # Fields that may be changed via update().
    UPDATABLE_FIELDS = frozenset({
        "name", "repo_url", "branch", "git_user_name", "git_user_email",
        "yolo", "log_path", "webhook_secret", "access_token",
        "last_webhook_received_at",
    })

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
        self, project_id: str, timeout_s: float = 60,
    ) -> dict[str, str]:
        """Pull latest code (git) and beads state (dolt) for one project.

        Best-effort: any failure is logged and recorded in the returned
        status dict but does NOT raise. The orchestrator should boot
        even if a project's network is flaky — it just operates on
        whatever local state exists.

        Returns ``{"git": "ok"|"failed: <reason>"|"skipped: <reason>",
                  "beads": "ok"|"failed: <reason>"|"skipped: <reason>"}``.
        """
        project = self._projects.get(project_id)
        if not project:
            return {"git": "skipped: unknown project", "beads": "skipped: unknown project"}
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
                    capture_output=True, text=True,
                    timeout=timeout_s,
                )
                # --autostash: handle the common case where bd has written
                # to .beads/issues.jsonl (unstaged) since the last commit.
                # Without it, fast-forward pulls fail with "Your local
                # changes to the following files would be overwritten by
                # merge". --ff-only still refuses if origin has diverged.
                pull = subprocess.run(
                    ["git", "pull", "--ff-only", "--autostash",
                     "origin", project.branch],
                    cwd=project.repo_path,
                    capture_output=True, text=True,
                    timeout=timeout_s,
                )
                if pull.returncode == 0:
                    status["git"] = "ok"
                else:
                    stderr = (pull.stderr or "").strip()[:200]
                    status["git"] = f"failed: {stderr}"
                    logger.warning(
                        "Startup git pull failed for %s: %s", project.name, stderr,
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
                status["git"] = f"failed: {exc}"
                logger.warning(
                    "Startup git fetch/pull failed for %s: %s", project.name, exc,
                )

        # bd dolt pull. Skip if there's no .beads/ directory at all.
        if not os.path.isdir(os.path.join(project.repo_path, ".beads")):
            status["beads"] = "skipped: no .beads"
        else:
            try:
                pull = subprocess.run(
                    ["bd", "dolt", "pull"],
                    cwd=project.repo_path,
                    capture_output=True, text=True,
                    timeout=timeout_s,
                )
                if pull.returncode == 0:
                    status["beads"] = "ok"
                else:
                    stderr = (pull.stderr or "").strip()[:200]
                    status["beads"] = f"failed: {stderr}"
                    logger.warning(
                        "Startup bd dolt pull failed for %s: %s", project.name, stderr,
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
                status["beads"] = f"failed: {exc}"
                logger.warning(
                    "Startup bd dolt pull failed for %s: %s", project.name, exc,
                )

        return status

    def sync_all_sources(
        self, timeout_s: float = 60, max_workers: int = 4,
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
                        "sync_all_sources: project %s raised: %s", p.name, exc,
                    )
                    results[p.id] = {
                        "git": f"exception: {exc}",
                        "beads": f"exception: {exc}",
                    }
        return results

    # -- Worktree helpers --

    def worktree_path_for(self, project_id: str, issue_identifier: str) -> str:
        project = self._projects.get(project_id)
        if not project:
            raise ProjectError(f"Unknown project: {project_id}")
        sanitized = _sanitize_identifier(issue_identifier)
        return os.path.join(self.worktree_root, _sanitize_identifier(project.name), sanitized)

    def create_worktree(self, project_id: str, issue_identifier: str) -> str:
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
                capture_output=True, text=True, timeout=60,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass  # best-effort

        # Create worktree on a new branch based on the project's main branch
        base = f"origin/{project.branch}"
        try:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, wt_path, base],
                cwd=project.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip()[:500] if exc.stderr else ""
            # Branch may already exist from a previous run — try reusing it
            if "already exists" in stderr:
                try:
                    subprocess.run(
                        ["git", "worktree", "add", wt_path, branch_name],
                        cwd=project.repo_path,
                        capture_output=True, text=True, check=True, timeout=30,
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
                    cwd=wt_path, capture_output=True, text=True, timeout=5,
                )
            except Exception:
                pass
        if project.git_user_email:
            try:
                subprocess.run(
                    ["git", "config", "user.email", project.git_user_email],
                    cwd=wt_path, capture_output=True, text=True, timeout=5,
                )
            except Exception:
                pass

        # Disable beads hooks to prevent state interference
        self._disable_worktree_hooks(wt_path)
        # Remove any forked per-worktree beads dolt state and stop
        # orphan dolt-sql-server processes — agent bd commands route
        # to the main DB via BEADS_DIR, so the worktree's copy is dead weight.
        self._strip_worktree_beads_fork(wt_path)

        logger.info("Worktree created path=%s branch=%s", wt_path, branch_name)
        return wt_path

    def _prepare_existing_worktree(
        self, wt_path: str, branch_name: str, project: Project,
    ) -> None:
        """Ensure an existing worktree is on the correct branch with a clean state."""
        def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
            return subprocess.run(
                cmd, cwd=wt_path, capture_output=True, text=True, timeout=30, **kw,
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
                logger.info("Checked out branch %s in worktree %s", branch_name, wt_path)
            except subprocess.CalledProcessError as exc:
                logger.warning(
                    "Failed to checkout branch %s in worktree %s: %s",
                    branch_name, wt_path, exc.stderr.strip()[:200] if exc.stderr else "",
                )

        # Disable beads hooks in worktrees to prevent post-checkout/pre-commit
        # hooks from syncing backup JSONL back to Dolt and reverting issue states
        self._disable_worktree_hooks(wt_path)
        # Defensive cleanup of any forked per-worktree beads dolt state.
        self._strip_worktree_beads_fork(wt_path)

    def _disable_worktree_hooks(self, wt_path: str) -> None:
        """Point worktree hooks to an empty directory to prevent beads hook interference.

        Beads git hooks (post-checkout, pre-commit) sync backup JSONL into the
        Dolt database. When agents run git operations (rebase, checkout) in
        worktrees, these hooks overwrite the orchestrator's in_progress state
        back to the stale state from the backup. Disabling hooks in worktrees
        prevents this.
        """
        try:
            empty_hooks = os.path.join(wt_path, ".oompah-no-hooks")
            os.makedirs(empty_hooks, exist_ok=True)
            subprocess.run(
                ["git", "config", "core.hooksPath", empty_hooks],
                cwd=wt_path,
                capture_output=True, text=True, timeout=5,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            pass

    def _strip_worktree_beads_fork(self, wt_path: str) -> None:
        """Remove any per-worktree beads dolt detritus.

        Each agent runs ``bd`` from inside its worktree. Without
        ``BEADS_DIR`` set, ``bd`` would create its own ``.beads/dolt/``
        and spawn a per-worktree dolt-sql-server, then write closures
        and comments into a forked DB the orchestrator never sees.

        The agent's run_command tool now sets ``BEADS_DIR`` to the
        project's main ``.beads`` so future invocations route correctly.
        This function defensively cleans any existing per-worktree
        dolt files left from past runs (gitignored, so they survive
        ``git reset --hard``) and stops orphan dolt-sql-server
        processes referenced by ``.beads/dolt-server.pid``.
        """
        beads_dir = os.path.join(wt_path, ".beads")
        if not os.path.isdir(beads_dir):
            return
        # Stop any orphan dolt server still tied to this worktree.
        pid_file = os.path.join(beads_dir, "dolt-server.pid")
        if os.path.isfile(pid_file):
            try:
                with open(pid_file) as f:
                    pid_str = f.read().strip()
                if pid_str.isdigit():
                    pid = int(pid_str)
                    try:
                        os.kill(pid, 15)  # SIGTERM
                    except ProcessLookupError:
                        pass
                    except OSError:
                        pass
            except OSError:
                pass
        # Drop dolt server runtime files and the embedded DB itself —
        # all gitignored, all safe to remove. ``bd`` will not regenerate
        # them as long as BEADS_DIR is set on every invocation.
        import shutil
        for entry in (
            "dolt-server.pid", "dolt-server.port", "dolt-server.log",
            "dolt-server.lock", "dolt", "embeddeddolt",
        ):
            path = os.path.join(beads_dir, entry)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                elif os.path.isfile(path) or os.path.islink(path):
                    os.remove(path)
            except OSError:
                pass

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
