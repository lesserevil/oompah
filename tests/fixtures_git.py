"""Git fixtures for evidence collection testing.

Provides isolated git repositories and worktrees with various configurations
for testing DoneEvidenceCollector behavior with real git operations.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class GitFixtureError(Exception):
    """Raised when a git fixture operation fails."""


def run_git(cwd: Path, args: list[str]) -> str:
    """Run git command and return output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise GitFixtureError(
            f"git {' '.join(args)} failed in {cwd}:\n{exc.stderr.strip()}"
        )


@dataclass
class GitFixture:
    """A disposable git repository for testing."""

    path: Path
    bare: bool = False

    def cleanup(self) -> None:
        """Remove the fixture repository."""
        import shutil

        if self.path.exists():
            shutil.rmtree(self.path)

    def __enter__(self) -> GitFixture:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup()


class LocalRepo(GitFixture):
    """A local (non-bare) git repository."""

    def __init__(self, path: Path | None = None, bare: bool = False) -> None:
        if path is None:
            path = Path(tempfile.mkdtemp(prefix="git_fixture_"))
        super().__init__(path, bare=bare)
        if not bare:
            self._init_repo()

    def _init_repo(self) -> None:
        """Initialize a new local repository."""
        self.path.mkdir(parents=True, exist_ok=True)
        run_git(self.path, ["init", "-b", "main"])  # Use main as default branch
        run_git(self.path, ["config", "user.email", "test@example.com"])
        run_git(self.path, ["config", "user.name", "Test User"])

    def commit(self, message: str, content: dict[str, str] | None = None) -> str:
        """Create a commit with optional file content."""
        if content is None:
            content = {"test.txt": message}

        for filename, file_content in content.items():
            filepath = self.path / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(file_content)
            run_git(self.path, ["add", filename])

        run_git(self.path, ["commit", "-m", message])
        return run_git(self.path, ["rev-parse", "HEAD"])

    def create_branch(self, branch: str, start_point: str = "HEAD") -> None:
        """Create and checkout a branch."""
        # First ensure we're on a valid branch
        try:
            self.checkout(start_point)
        except GitFixtureError:
            pass
        run_git(self.path, ["checkout", "-b", branch, start_point])

    def checkout(self, ref: str) -> None:
        """Checkout a branch or ref."""
        run_git(self.path, ["checkout", ref])

    def get_sha(self, ref: str = "HEAD") -> str:
        """Get the SHA of a ref."""
        return run_git(self.path, ["rev-parse", ref])

    def get_branch(self) -> str:
        """Get the current branch name."""
        return run_git(self.path, ["rev-parse", "--abbrev-ref", "HEAD"])

    def is_dirty(self) -> bool:
        """Check if the repository has uncommitted changes."""
        output = run_git(self.path, ["status", "--porcelain"])
        return bool(output.strip())

    def add_remote(self, name: str, url: str) -> None:
        """Add a remote."""
        run_git(self.path, ["remote", "add", name, url])

    def push(self, refspec: str = "HEAD", remote: str = "origin", force: bool = False) -> None:
        """Push to a remote."""
        args = ["push"]
        if force:
            args.append("-f")
        args.extend([remote, refspec])
        run_git(self.path, args)

    def fetch(self, remote: str = "origin", refspec: str = "") -> None:
        """Fetch from a remote."""
        args = ["fetch", remote]
        if refspec:
            args.append(refspec)
        run_git(self.path, args)

    def get_diff(self, base: str, head: str = "HEAD") -> str:
        """Get diff between two refs."""
        return run_git(self.path, ["diff", f"{base}...{head}"])

    def get_diff_stat(self, base: str, head: str = "HEAD") -> str:
        """Get diff stat between two refs."""
        return run_git(self.path, ["diff", "--stat", f"{base}...{head}"])

    def get_changed_files(self, base: str, head: str = "HEAD") -> list[str]:
        """Get list of changed files between two refs."""
        output = run_git(self.path, ["diff", "--name-only", f"{base}...{head}"])
        return [f for f in output.split("\n") if f.strip()]

    def create_worktree(self, path: Path, branch: str) -> LocalRepo:
        """Create a git worktree from this repository."""
        path.parent.mkdir(parents=True, exist_ok=True)
        run_git(self.path, ["worktree", "add", str(path), branch])
        return LocalRepo(path)


def create_two_repo_fixture(
    main_path: Path | None = None, bare_path: Path | None = None
) -> tuple[LocalRepo, LocalRepo]:
    """Create a main repo and bare remote for push testing.

    Returns:
        (main_repo, bare_remote)
    """
    if main_path is None:
        main_path = Path(tempfile.mkdtemp(prefix="git_main_"))
    if bare_path is None:
        bare_path = Path(tempfile.mkdtemp(prefix="git_bare_"))

    # Create bare remote
    bare_path.mkdir(parents=True, exist_ok=True)
    run_git(bare_path, ["init", "--bare", "-b", "main"])

    # Create main repo
    main_repo = LocalRepo(main_path)
    main_repo.add_remote("origin", str(bare_path))

    # Create and push initial commit to establish main branch on bare repo
    main_repo.commit("Initial commit for bare repo")
    try:
        main_repo.push("main", "origin", force=False)
    except GitFixtureError:
        # If push fails, that's OK for now - tests will handle it
        pass

    return main_repo, LocalRepo(bare_path)


def create_epic_fixture_with_children(
    epic_path: Path | None = None,
    num_children: int = 3,
) -> tuple[LocalRepo, list[LocalRepo]]:
    """Create an epic repository with child task worktrees.

    Each child is created as a worktree from the epic main worktree.

    Returns:
        (epic_repo, child_worktrees)
    """
    if epic_path is None:
        epic_path = Path(tempfile.mkdtemp(prefix="git_epic_"))

    epic_repo = LocalRepo(epic_path)

    # Create initial commit on main
    epic_repo.commit("Initial commit", {"README.md": "Epic project"})

    # Create feature branches for each child
    children = []
    for i in range(num_children):
        child_branch = f"child-{i}"
        epic_repo.checkout("main")
        epic_repo.create_branch(child_branch, "main")
        epic_repo.commit(
            f"Child {i} work",
            {f"child-{i}.txt": f"Work for child {i}"},
        )
        children.append(epic_repo)

    # Switch back to main
    epic_repo.checkout("main")

    # Create worktrees for children
    child_worktrees = []
    for i in range(num_children):
        child_path = epic_path.parent / f"child-{i}-wt"
        child_wt = epic_repo.create_worktree(child_path, f"child-{i}")
        child_worktrees.append(child_wt)

    return epic_repo, child_worktrees


__all__ = [
    "GitFixture",
    "GitFixtureError",
    "LocalRepo",
    "create_two_repo_fixture",
    "create_epic_fixture_with_children",
    "run_git",
]
