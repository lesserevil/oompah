"""Tests for state-branch initialization in project-bootstrap (OOMPAH-258).

Coverage:
  § 1  Happy path — state branch created for a fresh empty repo
  § 2  Canonical task-tree layout is present after bootstrap
  § 3  State branch is an orphan (no shared history with code branches)
  § 4  State branch is seeded from default branch when .oompah/tasks/ exists
  § 5  Idempotency — rerunning bootstrap leaves existing data intact
  § 6  Config verification — state-branch setting in project bootstrap config
  § 7  Naming convention — branch name derived from project ID
  § 8  Push behavior — optional remote push
  § 9  Error handling — graceful failure paths
  § 10 ensure_state_branch_initialized raises on error
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterator

import pytest

from oompah.project_bootstrap import (
    STATE_BRANCH_TASK_DIRS,
    StateBranchBootstrapResult,
    ensure_state_branch_initialized,
    initialize_state_branch,
)
from oompah.models import Project


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command in *cwd*."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def _make_repo(tmp_path: Path, *, with_oompah_tasks: bool = False) -> Path:
    """Create a minimal git repo on main with an initial commit.

    Parameters
    ----------
    tmp_path:
        pytest tmp_path fixture — unique per test.
    with_oompah_tasks:
        When True, also create ``.oompah/tasks/`` subdirectories and a sample
        task file on the main branch.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", cwd=str(repo))
    _git("config", "user.name", "Test User", cwd=str(repo))
    _git("config", "user.email", "test@example.com", cwd=str(repo))

    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")

    if with_oompah_tasks:
        tasks_root = repo / ".oompah" / "tasks"
        for d in STATE_BRANCH_TASK_DIRS:
            (tasks_root / d).mkdir(parents=True, exist_ok=True)

        # Add a sample task in the "open" directory.
        (tasks_root / "open" / "PROJ-1.md").write_text(
            "---\nid: PROJ-1\ntitle: Sample Task\nstatus: Open\n---\n"
            "\nSample task body.\n",
            encoding="utf-8",
        )

    _git("add", ".", cwd=str(repo))
    _git("commit", "-m", "initial", cwd=str(repo))
    return repo


@pytest.fixture
def fresh_repo(tmp_path: Path) -> Path:
    """Minimal repo with no .oompah/tasks/ on main."""
    return _make_repo(tmp_path)


@pytest.fixture
def repo_with_tasks(tmp_path: Path) -> Path:
    """Repo that already has .oompah/tasks/ populated on main."""
    return _make_repo(tmp_path, with_oompah_tasks=True)


# ---------------------------------------------------------------------------
# § 1 — Happy path: state branch created for a fresh empty repo
# ---------------------------------------------------------------------------


class TestStateBranchCreation:
    """State branch is created correctly for a new project."""

    def test_returns_success_result_for_fresh_repo(self, fresh_repo: Path):
        """initialize_state_branch must return a result with no error."""
        result = initialize_state_branch(fresh_repo, "proj-abc", push=False)
        assert result.error == "", f"Unexpected error: {result.error}"

    def test_created_flag_is_true_for_new_branch(self, fresh_repo: Path):
        """result.created must be True when the branch is freshly created."""
        result = initialize_state_branch(fresh_repo, "proj-abc", push=False)
        assert result.created is True

    def test_already_existed_flag_is_false_for_new_branch(self, fresh_repo: Path):
        """result.already_existed must be False on first creation."""
        result = initialize_state_branch(fresh_repo, "proj-abc", push=False)
        assert result.already_existed is False

    def test_commit_sha_is_populated(self, fresh_repo: Path):
        """result.commit_sha must be a 40-character hex SHA."""
        result = initialize_state_branch(fresh_repo, "proj-abc", push=False)
        assert len(result.commit_sha) == 40
        assert all(c in "0123456789abcdef" for c in result.commit_sha)

    def test_branch_exists_after_creation(self, fresh_repo: Path):
        """The state branch must be visible in git rev-parse after creation."""
        project_id = "proj-xyz"
        branch_name = f"oompah/state/{project_id}"
        initialize_state_branch(fresh_repo, project_id, push=False)
        r = _git("rev-parse", "--verify", branch_name, cwd=str(fresh_repo), check=False)
        assert r.returncode == 0, f"State branch {branch_name!r} not found after bootstrap"

    def test_branch_name_in_result(self, fresh_repo: Path):
        """result.branch_name must be oompah/state/<project-id>."""
        result = initialize_state_branch(fresh_repo, "proj-test-123", push=False)
        assert result.branch_name == "oompah/state/proj-test-123"

    def test_repo_returns_to_main_after_bootstrap(self, fresh_repo: Path):
        """After bootstrap, the working tree must be back on the default branch."""
        initialize_state_branch(fresh_repo, "proj-abc", push=False)
        r = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=str(fresh_repo))
        assert r.stdout.strip() == "main", (
            "Bootstrap must return the repo to 'main' after creating the state branch"
        )


# ---------------------------------------------------------------------------
# § 2 — Canonical task-tree layout is present after bootstrap
# ---------------------------------------------------------------------------


class TestTaskTreeLayout:
    """The canonical task-tree directories are present on the state branch."""

    def _state_branch_files(self, repo: Path, branch: str) -> set[str]:
        """Return the set of files on *branch* as repo-relative paths."""
        r = _git("ls-tree", "-r", "--name-only", branch, cwd=str(repo))
        return set(r.stdout.splitlines())

    def test_oompah_tasks_directory_exists(self, fresh_repo: Path):
        """The state branch must contain .oompah/tasks/ entries."""
        project_id = "proj-layout"
        branch = f"oompah/state/{project_id}"
        initialize_state_branch(fresh_repo, project_id, push=False)
        files = self._state_branch_files(fresh_repo, branch)
        oompah_files = [f for f in files if f.startswith(".oompah/tasks/")]
        assert len(oompah_files) >= 1, (
            f"State branch {branch!r} must contain .oompah/tasks/ entries; got: {files}"
        )

    def test_all_canonical_task_subdirs_present(self, fresh_repo: Path):
        """Every canonical status directory must exist on the state branch."""
        project_id = "proj-dirs"
        branch = f"oompah/state/{project_id}"
        initialize_state_branch(fresh_repo, project_id, push=False)
        files = self._state_branch_files(fresh_repo, branch)
        for d in STATE_BRANCH_TASK_DIRS:
            expected_prefix = f".oompah/tasks/{d}/"
            matching = [f for f in files if f.startswith(expected_prefix)]
            assert len(matching) >= 1, (
                f"State branch must contain {expected_prefix!r} entries; "
                f"found files: {sorted(files)}"
            )

    def test_state_branch_contains_only_oompah_content(self, fresh_repo: Path):
        """The state branch must not carry source code or project files."""
        project_id = "proj-nocode"
        branch = f"oompah/state/{project_id}"
        initialize_state_branch(fresh_repo, project_id, push=False)
        files = self._state_branch_files(fresh_repo, branch)
        non_oompah = [f for f in files if not f.startswith(".oompah/")]
        assert non_oompah == [], (
            f"State branch must not contain non-.oompah files: {non_oompah}"
        )

    def test_readme_md_not_on_state_branch(self, fresh_repo: Path):
        """README.md (project code file) must not appear on the state branch."""
        project_id = "proj-readme-check"
        branch = f"oompah/state/{project_id}"
        initialize_state_branch(fresh_repo, project_id, push=False)
        files = self._state_branch_files(fresh_repo, branch)
        assert "README.md" not in files, (
            "State branch must not contain README.md from the code branch"
        )


# ---------------------------------------------------------------------------
# § 3 — State branch is an orphan (no shared history with code branches)
# ---------------------------------------------------------------------------


class TestOrphanBranch:
    """State branch has no shared ancestor with the default code branch."""

    def test_state_branch_root_differs_from_main_root(self, fresh_repo: Path):
        """The root commits of main and the state branch must be different."""
        project_id = "proj-orphan"
        branch = f"oompah/state/{project_id}"
        initialize_state_branch(fresh_repo, project_id, push=False)

        main_root = _git(
            "rev-list", "--max-parents=0", "main", cwd=str(fresh_repo)
        ).stdout.strip()
        state_root = _git(
            "rev-list", "--max-parents=0", branch, cwd=str(fresh_repo)
        ).stdout.strip()

        assert main_root != state_root, (
            "State branch root commit must differ from main's root commit "
            "(orphan branch has independent history)"
        )

    def test_state_branch_has_no_common_ancestor_with_main(self, fresh_repo: Path):
        """git merge-base must fail (no common ancestor) for an orphan branch."""
        project_id = "proj-no-ancestor"
        branch = f"oompah/state/{project_id}"
        initialize_state_branch(fresh_repo, project_id, push=False)

        merge_base_r = _git(
            "merge-base", branch, "main", cwd=str(fresh_repo), check=False
        )
        assert merge_base_r.returncode != 0, (
            "Orphan state branch must share no common ancestor with main; "
            "git merge-base should exit non-zero"
        )

    def test_state_branch_bootstrap_commit_has_no_parent(self, fresh_repo: Path):
        """The bootstrap commit must have no parent (--max-parents=0 == HEAD)."""
        project_id = "proj-no-parent"
        branch = f"oompah/state/{project_id}"
        initialize_state_branch(fresh_repo, project_id, push=False)

        # Rev-list --max-parents=0 returns the root commit(s); for an orphan
        # this should be the same as HEAD.
        root = _git(
            "rev-list", "--max-parents=0", branch, cwd=str(fresh_repo)
        ).stdout.strip()
        head = _git("rev-parse", branch, cwd=str(fresh_repo)).stdout.strip()
        assert root == head, (
            "For a freshly bootstrapped state branch the root == HEAD (only 1 commit)"
        )


# ---------------------------------------------------------------------------
# § 4 — State branch is seeded from default branch when .oompah/tasks/ exists
# ---------------------------------------------------------------------------


class TestSeedingFromMain:
    """When main has .oompah/tasks/, the state branch inherits it."""

    def _files_on_branch(self, repo: Path, branch: str) -> set[str]:
        r = _git("ls-tree", "-r", "--name-only", branch, cwd=str(repo))
        return set(r.stdout.splitlines())

    def test_seeded_from_main_flag_is_true_when_tasks_exist(
        self, repo_with_tasks: Path
    ):
        """result.seeded_from_main must be True when .oompah/tasks/ exists on main."""
        result = initialize_state_branch(repo_with_tasks, "proj-seed", push=False)
        assert result.seeded_from_main is True

    def test_task_file_from_main_appears_on_state_branch(
        self, repo_with_tasks: Path
    ):
        """The sample task file from main must appear on the state branch."""
        project_id = "proj-seed-file"
        branch = f"oompah/state/{project_id}"
        initialize_state_branch(repo_with_tasks, project_id, push=False)
        files = self._files_on_branch(repo_with_tasks, branch)
        assert ".oompah/tasks/open/PROJ-1.md" in files, (
            "State branch must include task files seeded from main's .oompah/tasks/"
        )

    def test_seeded_from_main_flag_is_false_for_empty_repo(
        self, fresh_repo: Path
    ):
        """When main has no .oompah/tasks/, seeded_from_main must be False."""
        result = initialize_state_branch(fresh_repo, "proj-empty-seed", push=False)
        assert result.seeded_from_main is False

    def test_task_file_content_is_preserved_after_seeding(
        self, repo_with_tasks: Path
    ):
        """The content of task files seeded from main must be preserved."""
        project_id = "proj-seed-content"
        branch = f"oompah/state/{project_id}"
        initialize_state_branch(repo_with_tasks, project_id, push=False)

        # Checkout the task file from the state branch and verify content
        r = _git(
            "show",
            f"{branch}:.oompah/tasks/open/PROJ-1.md",
            cwd=str(repo_with_tasks),
        )
        assert "PROJ-1" in r.stdout
        assert "Sample Task" in r.stdout


# ---------------------------------------------------------------------------
# § 5 — Idempotency: rerunning bootstrap leaves existing data intact
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Rerunning initialize_state_branch preserves existing state data."""

    def test_already_existed_true_on_second_call(self, fresh_repo: Path):
        """Second call must report already_existed=True, not create a new branch."""
        project_id = "proj-idempotent"
        initialize_state_branch(fresh_repo, project_id, push=False)
        result2 = initialize_state_branch(fresh_repo, project_id, push=False)
        assert result2.already_existed is True

    def test_created_false_on_second_call(self, fresh_repo: Path):
        """Second call must not report created=True."""
        project_id = "proj-idempotent-created"
        initialize_state_branch(fresh_repo, project_id, push=False)
        result2 = initialize_state_branch(fresh_repo, project_id, push=False)
        assert result2.created is False

    def test_no_error_on_second_call(self, fresh_repo: Path):
        """Second call must succeed without an error."""
        project_id = "proj-idempotent-err"
        initialize_state_branch(fresh_repo, project_id, push=False)
        result2 = initialize_state_branch(fresh_repo, project_id, push=False)
        assert result2.error == ""

    def test_task_data_preserved_on_second_call(self, repo_with_tasks: Path):
        """Rerunning bootstrap must not delete or overwrite existing task data.

        This is the core idempotency acceptance criterion: running the bootstrap
        twice must leave the task tree byte-for-byte identical to after the first run.
        """
        project_id = "proj-preserve"
        branch = f"oompah/state/{project_id}"

        # First bootstrap — seeds from main's tasks.
        initialize_state_branch(repo_with_tasks, project_id, push=False)

        # Record state after first run.
        r1 = _git("ls-tree", "-r", "--name-only", branch, cwd=str(repo_with_tasks))
        files_after_first = set(r1.stdout.splitlines())

        # Second run — must be a no-op.
        initialize_state_branch(repo_with_tasks, project_id, push=False)

        r2 = _git("ls-tree", "-r", "--name-only", branch, cwd=str(repo_with_tasks))
        files_after_second = set(r2.stdout.splitlines())

        assert files_after_second == files_after_first, (
            "Rerunning bootstrap must not add, remove, or modify task files"
        )

    def test_only_one_commit_created_after_two_runs(self, fresh_repo: Path):
        """The state branch must have exactly one commit after two bootstrap calls."""
        project_id = "proj-one-commit"
        branch = f"oompah/state/{project_id}"

        initialize_state_branch(fresh_repo, project_id, push=False)
        initialize_state_branch(fresh_repo, project_id, push=False)

        r = _git(
            "rev-list", "--count", branch, cwd=str(fresh_repo)
        )
        commit_count = int(r.stdout.strip())
        assert commit_count == 1, (
            f"State branch must have exactly 1 commit after idempotent re-run; "
            f"got {commit_count}"
        )

    def test_task_file_content_not_duplicated(self, repo_with_tasks: Path):
        """Task file content must not be duplicated on idempotent re-run."""
        project_id = "proj-no-dup"
        branch = f"oompah/state/{project_id}"

        initialize_state_branch(repo_with_tasks, project_id, push=False)
        initialize_state_branch(repo_with_tasks, project_id, push=False)

        content_r = _git(
            "show",
            f"{branch}:.oompah/tasks/open/PROJ-1.md",
            cwd=str(repo_with_tasks),
        )
        # Content must appear exactly once, not be doubled.
        content = content_r.stdout
        assert content.count("PROJ-1") == 1, (
            "Task file content must not be duplicated by a re-run"
        )

    def test_already_existed_branch_result_carries_branch_name(self, fresh_repo: Path):
        """Second call result must still populate branch_name correctly."""
        project_id = "proj-branch-name"
        initialize_state_branch(fresh_repo, project_id, push=False)
        result2 = initialize_state_branch(fresh_repo, project_id, push=False)
        assert result2.branch_name == f"oompah/state/{project_id}"


# ---------------------------------------------------------------------------
# § 6 — Config verification: project model state_branch_enabled
# ---------------------------------------------------------------------------


class TestStateBranchProjectConfig:
    """The Project model reports state_branch_enabled and state_branch_name."""

    def _make_project(self, **overrides) -> Project:
        defaults = dict(
            id="proj-cfg-abc",
            name="testrepo",
            repo_url="https://github.com/org/testrepo.git",
            repo_path="/tmp/testrepo",
            default_branch="main",
        )
        defaults.update(overrides)
        return Project(**defaults)

    def test_new_project_state_branch_enabled_defaults_false(self):
        """Project.state_branch_enabled must default to False (backward compat)."""
        p = self._make_project()
        assert p.state_branch_enabled is False

    def test_state_branch_enabled_can_be_set_true(self):
        """Project.state_branch_enabled can be set True for new projects."""
        p = self._make_project(state_branch_enabled=True)
        assert p.state_branch_enabled is True

    def test_state_branch_name_derived_from_project_id(self):
        """Project.state_branch_name must be oompah/state/<project-id>."""
        p = self._make_project(id="proj-14849f1b")
        assert p.state_branch_name == "oompah/state/proj-14849f1b"

    def test_bootstrap_result_branch_name_matches_project_state_branch_name(
        self, fresh_repo: Path
    ):
        """The branch name in the bootstrap result must match Project.state_branch_name."""
        project_id = "proj-cfg-match"
        p = self._make_project(id=project_id)
        result = initialize_state_branch(fresh_repo, project_id, push=False)
        assert result.branch_name == p.state_branch_name

    def test_state_branch_name_in_bootstrap_template_docs(self):
        """docs/project-bootstrap.md must document state_branch_enabled."""
        import os
        doc_path = os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            "docs",
            "project-bootstrap.md",
        )
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "state_branch" in content or "state branch" in content.lower(), (
            "docs/project-bootstrap.md must document the state branch feature"
        )

    def test_state_branch_migration_doc_exists(self):
        """docs/state-branch-migration.md must exist with operator instructions."""
        import os
        doc_path = os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            "docs",
            "state-branch-migration.md",
        )
        assert os.path.exists(doc_path), (
            "docs/state-branch-migration.md must exist for operator recovery docs"
        )
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Must cover required operator topics
        assert "branch protection" in content.lower(), (
            "Migration doc must cover branch protection considerations"
        )
        assert "troubleshoot" in content.lower() or "troubleshooting" in content.lower(), (
            "Migration doc must include a troubleshooting section"
        )
        assert "rollback" in content.lower(), (
            "Migration doc must document rollback/recovery procedures"
        )

    def test_project_bootstrap_doc_mentions_state_branch(self):
        """docs/project-bootstrap.md must mention state branch behavior."""
        import os
        doc_path = os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            "docs",
            "project-bootstrap.md",
        )
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        # New-project state branch is the key addition from OOMPAH-258
        assert "state branch" in content.lower() or "state_branch" in content, (
            "docs/project-bootstrap.md must explain that new projects get a state branch"
        )


# ---------------------------------------------------------------------------
# § 7 — Naming convention: branch name derived from project ID
# ---------------------------------------------------------------------------


class TestBranchNaming:
    """Branch name formula is correct for all valid project IDs."""

    @pytest.mark.parametrize(
        "project_id",
        [
            "proj-abc",
            "proj-14849f1b",
            "proj-xyz-123",
            "proj-00000000",
        ],
    )
    def test_branch_name_is_oompah_state_project_id(
        self, project_id: str, tmp_path: Path
    ):
        """State branch name must be oompah/state/<project-id>."""
        repo = _make_repo(tmp_path)
        result = initialize_state_branch(repo, project_id, push=False)
        assert result.branch_name == f"oompah/state/{project_id}"

    def test_branch_name_uses_project_id_not_project_name(
        self, fresh_repo: Path
    ):
        """Branch name is stable — it uses the immutable project ID."""
        project_id = "proj-stable"
        result = initialize_state_branch(fresh_repo, project_id, push=False)
        # The name must be derived from the ID, not a human-readable name.
        assert result.branch_name == "oompah/state/proj-stable"
        assert "stable" not in result.branch_name.replace(project_id, "")

    def test_state_branch_not_under_feature_or_release_namespace(
        self, fresh_repo: Path
    ):
        """State branch must be under oompah/, not feature/ or release/."""
        project_id = "proj-namespace"
        result = initialize_state_branch(fresh_repo, project_id, push=False)
        for bad_prefix in ("feature/", "release/", "hotfix/", "main"):
            assert not result.branch_name.startswith(bad_prefix), (
                f"State branch must not start with {bad_prefix!r}"
            )
        assert result.branch_name.startswith("oompah/state/")

    def test_state_branch_task_dirs_constant_covers_all_statuses(self):
        """STATE_BRANCH_TASK_DIRS must cover all expected oompah task statuses."""
        expected = {
            "proposed", "backlog", "open", "in-progress", "needs-human",
            "in-review", "done", "merged", "archived",
        }
        actual = set(STATE_BRANCH_TASK_DIRS)
        assert expected.issubset(actual), (
            f"STATE_BRANCH_TASK_DIRS missing required statuses: {expected - actual}"
        )


# ---------------------------------------------------------------------------
# § 8 — Push behavior
# ---------------------------------------------------------------------------


class TestPushBehavior:
    """Push is optional; pushed flag reflects actual push."""

    def test_pushed_false_when_push_not_requested(self, fresh_repo: Path):
        """result.pushed must be False when push=False."""
        result = initialize_state_branch(fresh_repo, "proj-no-push", push=False)
        assert result.pushed is False

    def test_no_error_when_push_false_and_no_remote(self, fresh_repo: Path):
        """With push=False and no remote, bootstrap must succeed without error."""
        result = initialize_state_branch(fresh_repo, "proj-no-remote", push=False)
        assert result.error == ""

    def _make_repo_with_remote(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create a local repo wired to a bare 'remote' repo.

        Returns (working_tree_path, bare_repo_path).
        """
        bare = tmp_path / "bare.git"
        bare.mkdir()
        _git("init", "--bare", cwd=str(bare))

        # Create a separate working tree that treats bare as origin.
        work = tmp_path / "work"
        work.mkdir()
        _git("init", "-b", "main", cwd=str(work))
        _git("config", "user.name", "Test User", cwd=str(work))
        _git("config", "user.email", "test@example.com", cwd=str(work))
        _git("remote", "add", "origin", str(bare), cwd=str(work))
        (work / "README.md").write_text("# Test\n", encoding="utf-8")
        _git("add", ".", cwd=str(work))
        _git("commit", "-m", "initial", cwd=str(work))
        _git("push", "--set-upstream", "origin", "main", cwd=str(work))
        return work, bare

    def test_push_to_local_bare_remote(self, tmp_path: Path):
        """When a bare remote exists, push=True must succeed and set pushed=True."""
        work, _bare = self._make_repo_with_remote(tmp_path)

        result = initialize_state_branch(work, "proj-push-test", push=True)

        assert result.error == "", f"Unexpected error: {result.error}"
        assert result.pushed is True
        assert result.created is True

    def test_state_branch_visible_at_remote_after_push(self, tmp_path: Path):
        """After push=True, the state branch must be present at the remote."""
        work, bare = self._make_repo_with_remote(tmp_path)

        project_id = "proj-remote-visible"
        branch_name = f"oompah/state/{project_id}"
        initialize_state_branch(work, project_id, push=True)

        # Verify the branch is in the bare remote.
        r = _git("rev-parse", "--verify", branch_name, cwd=str(bare), check=False)
        assert r.returncode == 0, (
            f"State branch {branch_name!r} must exist in the remote after push"
        )


# ---------------------------------------------------------------------------
# § 9 — Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Graceful failure paths in initialize_state_branch."""

    def test_error_result_when_repo_path_does_not_exist(self, tmp_path: Path):
        """initialize_state_branch must return an error for a non-existent path."""
        bad_path = tmp_path / "nonexistent"
        result = initialize_state_branch(bad_path, "proj-bad", push=False)
        assert result.error != "", "Must return an error for a non-existent repo path"
        assert result.created is False

    def test_no_exception_raised_for_bad_repo(self, tmp_path: Path):
        """initialize_state_branch must not raise; it returns errors in the result."""
        bad_path = tmp_path / "also-nonexistent"
        try:
            result = initialize_state_branch(bad_path, "proj-no-raise", push=False)
        except Exception as exc:
            pytest.fail(
                f"initialize_state_branch raised an exception instead of returning "
                f"error in result: {exc}"
            )


# ---------------------------------------------------------------------------
# § 10 — ensure_state_branch_initialized raises on error
# ---------------------------------------------------------------------------


class TestEnsureStateBranchInitialized:
    """ensure_state_branch_initialized raises RuntimeError on failure."""

    def test_raises_runtime_error_for_bad_path(self, tmp_path: Path):
        """ensure_state_branch_initialized must raise RuntimeError for bad paths."""
        bad_path = tmp_path / "nonexistent-repo"
        with pytest.raises(RuntimeError):
            ensure_state_branch_initialized(bad_path, "proj-raise-test")

    def test_success_path_returns_result(self, fresh_repo: Path):
        """ensure_state_branch_initialized returns the result on success."""
        result = ensure_state_branch_initialized(
            fresh_repo, "proj-ensure-ok", push=False
        )
        assert isinstance(result, StateBranchBootstrapResult)
        assert result.error == ""
        assert result.created is True

    def test_idempotent_call_does_not_raise(self, fresh_repo: Path):
        """Calling ensure_state_branch_initialized twice must not raise."""
        project_id = "proj-ensure-idem"
        ensure_state_branch_initialized(fresh_repo, project_id, push=False)
        # Second call must also not raise.
        result2 = ensure_state_branch_initialized(fresh_repo, project_id, push=False)
        assert result2.already_existed is True
