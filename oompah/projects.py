"""Project storage and git worktree management."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import uuid

from oompah.models import Project

logger = logging.getLogger(__name__)

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
               git_user_email: str | None = None) -> Project:
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

        project_id = f"proj-{uuid.uuid4().hex[:8]}"
        project = Project(
            id=project_id,
            name=name,
            repo_url=repo_url,
            repo_path=repo_path,
            branch=branch,
            git_user_name=git_user_name,
            git_user_email=git_user_email,
        )
        self._projects[project_id] = project
        self._save()
        logger.info("Project created id=%s name=%s repo=%s", project_id, name, repo_url)
        return project

    def update(self, project_id: str, **fields) -> Project | None:
        project = self._projects.get(project_id)
        if not project:
            return None
        for key, value in fields.items():
            if hasattr(project, key) and key != "id":
                setattr(project, key, value)
        self._save()
        return project

    def delete(self, project_id: str) -> bool:
        if project_id in self._projects:
            del self._projects[project_id]
            self._save()
            return True
        return False

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

        # Inherit core.hooksPath from the parent repo (e.g. beads merge hooks)
        self._inherit_hooks_path(wt_path, project)

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

        # Ensure hooks path is set (e.g. beads merge hooks)
        self._inherit_hooks_path(wt_path, project)

    def _inherit_hooks_path(self, wt_path: str, project: Project) -> None:
        """Copy core.hooksPath from the parent repo to a worktree."""
        try:
            r = subprocess.run(
                ["git", "config", "core.hooksPath"],
                cwd=project.repo_path,
                capture_output=True, text=True, timeout=5,
            )
            hooks_path = r.stdout.strip() if r.returncode == 0 else ""
            if not hooks_path:
                return

            # Resolve relative paths against the parent repo
            if not os.path.isabs(hooks_path):
                hooks_path = os.path.join(project.repo_path, hooks_path)

            subprocess.run(
                ["git", "config", "core.hooksPath", hooks_path],
                cwd=wt_path,
                capture_output=True, text=True, timeout=5,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
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
