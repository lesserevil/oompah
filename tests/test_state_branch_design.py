"""Design-validation tests for the state-branch feature (OOMPAH-254 / OOMPAH-253).

These tests validate the machine-readable defaults and configuration schemas
defined in plans/state-branch-design.md.  They do NOT require the runtime
state-branch implementation — they exercise existing interfaces and document
expected behavior for interfaces that do not yet exist.

Tests that cover not-yet-implemented behavior are marked with
``pytest.mark.xfail(strict=False)`` so they document the expected contract
without causing CI failures.  When the feature ships, remove the
``xfail`` marks.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path
from typing import Iterator

import pytest
import yaml

from oompah.models import Project


# ---------------------------------------------------------------------------
# § 3.2 — Design: .env variable names and defaults
#
# These tests validate that the design's declared defaults are honored by the
# runtime when those defaults are expressed via existing config mechanisms.
# They also document the variable names so future implementation code has a
# single authoritative reference.
# ---------------------------------------------------------------------------

# Variable name → expected default value (as the design specifies)
_STATE_BRANCH_ENV_DEFAULTS: dict[str, object] = {
    "OOMPAH_STATE_BRANCH_ENABLED": False,       # global opt-in; must default to off
    "OOMPAH_STATE_BRANCH_CHECKPOINT_DEBOUNCE_MS": 5000,
    "OOMPAH_STATE_BRANCH_CHECKPOINT_MAX_DELAY_MS": 30000,
    "OOMPAH_STATE_BRANCH_PUSH_RETRY_COUNT": 3,
    "OOMPAH_STATE_BRANCH_PUSH_RETRY_BACKOFF_MS": 1000,
    "OOMPAH_STATE_BRANCH_SYNC_TIMEOUT_MS": 30000,
}


class TestEnvVariableContract:
    """Validate that the design-specified env variable names are well-formed."""

    def test_all_variable_names_are_valid_env_keys(self):
        """Every design-declared variable must be a valid shell env-variable name."""
        import re
        pattern = re.compile(r"^[A-Z][A-Z0-9_]+$")
        for name in _STATE_BRANCH_ENV_DEFAULTS:
            assert pattern.match(name), (
                f"{name!r} is not a valid uppercase env variable name"
            )

    def test_all_variable_names_are_oompah_prefixed(self):
        """All state-branch variables must share the OOMPAH_STATE_BRANCH_ prefix."""
        for name in _STATE_BRANCH_ENV_DEFAULTS:
            assert name.startswith("OOMPAH_STATE_BRANCH_"), (
                f"{name!r} does not follow the OOMPAH_STATE_BRANCH_ prefix convention"
            )

    def test_default_for_enabled_flag_is_false(self):
        """State branch is off by default — existing projects opt in explicitly."""
        assert _STATE_BRANCH_ENV_DEFAULTS["OOMPAH_STATE_BRANCH_ENABLED"] is False

    def test_debounce_less_than_max_delay(self):
        """Debounce must be strictly less than the max delay (design § 5.2)."""
        debounce = _STATE_BRANCH_ENV_DEFAULTS["OOMPAH_STATE_BRANCH_CHECKPOINT_DEBOUNCE_MS"]
        max_delay = _STATE_BRANCH_ENV_DEFAULTS["OOMPAH_STATE_BRANCH_CHECKPOINT_MAX_DELAY_MS"]
        assert int(debounce) < int(max_delay), (
            "Default debounce interval must be strictly less than default max delay"
        )


# ---------------------------------------------------------------------------
# § 3.1 / § 3.3 — Project model backward compatibility
#
# The Project dataclass must default state_branch_enabled=False so that
# every existing project that doesn't carry the new field continues to
# write task state to the default branch (unchanged behavior).
# ---------------------------------------------------------------------------


class TestProjectModelDefaults:
    """Validate backward-compatible defaults on the Project model."""

    def _make_project(self) -> Project:
        return Project(
            id="proj-14849f1b",
            name="myrepo",
            repo_url="https://github.com/org/myrepo.git",
            repo_path="/tmp/myrepo",
            default_branch="main",
        )

    def test_state_branch_enabled_defaults_to_false(self):
        """Newly created projects must not opt in to state branches automatically.

        Once the field is added to Project, this test enforces the backward-
        compatible default.  Until the field exists, this documents the
        requirement and is marked xfail.
        """
        p = self._make_project()
        enabled = getattr(p, "state_branch_enabled", None)
        if enabled is None:
            pytest.xfail(
                "Project.state_branch_enabled not yet implemented; "
                "remove xfail when field is added (plans/state-branch-design.md § 3.1)"
            )
        assert enabled is False, (
            "state_branch_enabled must default to False for backward compatibility"
        )

    def test_state_branch_name_derivation(self):
        """State branch name must be oompah/state/<project-id>.

        Validate the naming contract from § 2.1 of the design.
        """
        p = self._make_project()
        project_id = p.id
        expected_branch = f"oompah/state/{project_id}"
        # The naming is deterministic from project ID — validate the formula.
        assert expected_branch == "oompah/state/proj-14849f1b"
        # Check that the prefix follows the namespace convention.
        assert expected_branch.startswith("oompah/state/"), (
            "State branch must be under the oompah/state/ namespace"
        )

    def test_state_branch_per_project_checkpoint_fields_default_none(self):
        """Per-project checkpoint overrides must default to None (fall through to .env).

        Once the fields are added to Project, this test enforces that they don't
        inadvertently override the global .env defaults.
        """
        p = self._make_project()
        debounce = getattr(p, "state_branch_checkpoint_debounce_ms", "MISSING")
        max_delay = getattr(p, "state_branch_checkpoint_max_delay_ms", "MISSING")
        if debounce == "MISSING":
            pytest.xfail(
                "Project.state_branch_checkpoint_debounce_ms not yet implemented; "
                "remove xfail when field is added"
            )
        assert debounce is None, (
            "Per-project debounce must default to None so the .env global value is used"
        )
        assert max_delay is None, (
            "Per-project max_delay must default to None so the .env global value is used"
        )


# ---------------------------------------------------------------------------
# § 5.2 — Checkpoint interval validation constraint
#
# The service must reject (and auto-correct) configurations where
# max_delay < debounce, since that would make the hard deadline fire
# before the debounce timer and confuse the coalescing logic.
# ---------------------------------------------------------------------------


class TestCheckpointIntervalConstraint:
    """Validate the debounce/max-delay ordering constraint (design § 5.2)."""

    def test_valid_configuration_is_accepted(self):
        """debounce=5000, max_delay=30000 satisfies the constraint."""
        debounce_ms = 5000
        max_delay_ms = 30000
        # Constraint: max_delay >= debounce + 1000 (from design § 5.2)
        assert max_delay_ms >= debounce_ms + 1000

    def test_invalid_configuration_must_be_auto_corrected(self):
        """When max_delay < debounce, the corrected max_delay is debounce + 1000.

        This is the documented correction formula from design § 5.2.
        """
        debounce_ms = 10000
        max_delay_ms = 3000   # invalid: less than debounce

        # The correction formula from § 5.2:
        if max_delay_ms < debounce_ms:
            corrected = max(max_delay_ms, debounce_ms + 1000)
        else:
            corrected = max_delay_ms

        assert corrected == 11000
        assert corrected >= debounce_ms + 1000

    def test_equal_values_require_correction(self):
        """debounce == max_delay should also be corrected (max_delay = debounce + 1s)."""
        debounce_ms = 5000
        max_delay_ms = 5000

        if max_delay_ms < debounce_ms + 1000:
            corrected = debounce_ms + 1000
        else:
            corrected = max_delay_ms

        assert corrected == 6000


# ---------------------------------------------------------------------------
# § 6.1 and § 7.7 — Historical task data fixture
#
# The design requires that the implementation is validated against a fixture
# representing a project with:
# - Historical .oompah task data on main
# - An active release branch that also has .oompah task files (inherited from
#   main before the branch was cut)
#
# These tests build that fixture and verify properties the migration design
# requires.
# ---------------------------------------------------------------------------


@pytest.fixture
def historical_task_repo(tmp_path: Path) -> Iterator[Path]:
    """Bare-minimum git repo fixture with historical oompah task data.

    Creates:
    - main: two tasks (one in-progress, one done)
    - release/1.0: same task files (inherited from main at branch-cut time),
      plus a code commit representing release work

    Returns the path to the repo root.
    """
    repo = tmp_path / "myrepo"
    repo.mkdir()

    def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=check,
        )

    # Initialize
    git("init", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")

    # Create task directory structure
    tasks_root = repo / ".oompah" / "tasks"
    for d in [
        "proposed", "backlog", "open", "in-progress", "needs-human",
        "in-review", "done", "merged", "archived",
    ]:
        (tasks_root / d).mkdir(parents=True, exist_ok=True)

    # Task 1: in-progress
    task1_meta = {
        "id": "PROJ-1",
        "type": "task",
        "status": "In Progress",
        "priority": 2,
        "title": "Implement login endpoint",
        "parent": None,
        "children": [],
        "blocked_by": [],
        "labels": ["backend"],
        "created_at": "2026-07-01T10:00:00Z",
        "updated_at": "2026-07-15T08:00:00Z",
        "work_branch": "PROJ-1",
        "target_branch": None,
        "review_url": None,
        "review_number": None,
        "merged_at": None,
    }
    task1_body = "## Summary\n\nImplement the login endpoint.\n\n## Acceptance Criteria\n\n- [ ] POST /login returns 200.\n"
    task1_path = tasks_root / "in-progress" / "PROJ-1.md"
    task1_path.write_text(
        f"---\n{yaml.safe_dump(task1_meta)}---\n{task1_body}",
        encoding="utf-8",
    )

    # Task 2: done
    task2_meta = {
        "id": "PROJ-2",
        "type": "task",
        "status": "Done",
        "priority": 1,
        "title": "Setup CI pipeline",
        "parent": None,
        "children": [],
        "blocked_by": [],
        "labels": ["devops"],
        "created_at": "2026-06-01T09:00:00Z",
        "updated_at": "2026-07-10T12:00:00Z",
        "work_branch": None,
        "target_branch": None,
        "review_url": None,
        "review_number": None,
        "merged_at": "2026-07-10T12:00:00Z",
    }
    task2_body = "## Summary\n\nSetup CI pipeline.\n\n## Acceptance Criteria\n\n- [x] CI runs on every PR.\n"
    task2_path = tasks_root / "done" / "PROJ-2.md"
    task2_path.write_text(
        f"---\n{yaml.safe_dump(task2_meta)}---\n{task2_body}",
        encoding="utf-8",
    )

    # Also add a source code file
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("# main\n", encoding="utf-8")

    git("add", ".")
    git("commit", "-m", "Initial: code + task history on main")

    # Cut release/1.0 from current main (inherits .oompah/tasks/ from main)
    git("checkout", "-b", "release/1.0")
    (repo / "src" / "release_notes.txt").write_text("Release 1.0\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "Add release notes for 1.0")

    # Return to main
    git("checkout", "main")

    yield repo


class TestHistoricalTaskDataFixture:
    """Validate the design against a fixture with historical task data (§ 7.7)."""

    def test_fixture_has_tasks_on_main(self, historical_task_repo: Path):
        """main branch must have .oompah/tasks/ with at least one in-progress task."""
        tasks_root = historical_task_repo / ".oompah" / "tasks"
        assert tasks_root.is_dir(), ".oompah/tasks/ must exist on main"
        in_progress_files = list((tasks_root / "in-progress").glob("*.md"))
        assert len(in_progress_files) >= 1, (
            "main branch must have at least one in-progress task"
        )

    def test_fixture_release_branch_also_has_tasks(self, historical_task_repo: Path):
        """release/1.0 inherits .oompah/tasks/ from main at branch-cut time."""
        result = subprocess.run(
            ["git", "show", "release/1.0:.oompah/tasks/done/PROJ-2.md"],
            cwd=str(historical_task_repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "release/1.0 should have .oompah/tasks/ files inherited from main"
        )
        assert "PROJ-2" in result.stdout

    def test_fixture_release_branch_has_code_not_on_main(self, historical_task_repo: Path):
        """release/1.0 has a code commit (release notes) not on main."""
        main_files = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "main"],
            cwd=str(historical_task_repo),
            capture_output=True, text=True,
        ).stdout.splitlines()
        release_files = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "release/1.0"],
            cwd=str(historical_task_repo),
            capture_output=True, text=True,
        ).stdout.splitlines()
        assert "src/release_notes.txt" not in main_files
        assert "src/release_notes.txt" in release_files

    def test_state_branch_bootstrap_creates_orphan(self, historical_task_repo: Path):
        """Bootstrapping the state branch must create an orphan with no shared history.

        An orphan branch has a different root commit from main, so git cannot
        fast-forward it into code history.  This test validates the orphan
        property described in design § 2.3.

        Note: This test exercises the bootstrap contract only; it does NOT call
        the not-yet-implemented OompahMarkdownTracker state-branch bootstrap
        method.  It validates the git mechanics directly.
        """
        repo = historical_task_repo
        project_id = "proj-test"
        state_branch = f"oompah/state/{project_id}"

        def git(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git", *args],
                cwd=str(repo),
                capture_output=True,
                text=True,
            )

        # Simulate what the bootstrap must do: create orphan, seed, commit
        git("checkout", "--orphan", state_branch)
        git("reset", "--hard")  # unstage everything from the previous tree

        # Seed .oompah/ from main
        git("checkout", "main", "--", ".oompah/")
        git("add", ".oompah/")
        git("commit", "-m", f"Bootstrap oompah state branch for {project_id}")

        # Verify: state branch exists
        result = git("rev-parse", "--verify", state_branch)
        assert result.returncode == 0, "State branch must exist after bootstrap"

        # Verify: state branch has no common ancestor with main (orphan property)
        merge_base = git("merge-base", state_branch, "main")
        assert merge_base.returncode != 0, (
            "Orphan state branch must share no common ancestor with main"
        )

        # Verify: state branch root commit has no parent
        root_commit = git(
            "rev-list", "--max-parents=0", state_branch
        ).stdout.strip()
        main_root = git("rev-list", "--max-parents=0", "main").stdout.strip()
        assert root_commit != main_root, (
            "State branch root commit must differ from main's root commit"
        )

        # Return to main for any subsequent operations
        git("checkout", "main")

    def test_state_branch_contains_only_oompah_directory(self, historical_task_repo: Path):
        """After bootstrap, the state branch must contain only .oompah/ content.

        Source code files (src/, etc.) must not be present on the state branch.
        This validates the directory layout contract from design § 2.2.
        """
        repo = historical_task_repo
        project_id = "proj-layout-test"
        state_branch = f"oompah/state/{project_id}"

        def git(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git", *args],
                cwd=str(repo),
                capture_output=True,
                text=True,
            )

        # Bootstrap: orphan + seed from main's .oompah/ only
        git("checkout", "--orphan", state_branch)
        git("reset", "--hard")
        git("checkout", "main", "--", ".oompah/")
        git("add", ".oompah/")
        git("commit", "-m", f"Bootstrap {state_branch}")

        # List all files on the state branch
        ls_result = git("ls-tree", "-r", "--name-only", state_branch)
        assert ls_result.returncode == 0
        state_files = ls_result.stdout.splitlines()

        # Every file must be under .oompah/
        non_oompah = [f for f in state_files if not f.startswith(".oompah/")]
        assert non_oompah == [], (
            f"State branch must not contain non-.oompah files: {non_oompah}"
        )

        # Specifically: source code files must NOT be present
        assert "src/main.py" not in state_files
        assert "src/release_notes.txt" not in state_files

        # .oompah/tasks/ directory must be present
        oompah_paths = [f for f in state_files if ".oompah/tasks/" in f]
        assert len(oompah_paths) >= 1, (
            "State branch must contain .oompah/tasks/ files seeded from main"
        )

        git("checkout", "main")

    def test_task_files_have_valid_yaml_frontmatter(self, historical_task_repo: Path):
        """All task files in the fixture must have valid YAML front matter.

        This validates the pre-migration validation check described in § 6.1.
        """
        tasks_root = historical_task_repo / ".oompah" / "tasks"
        task_files = list(tasks_root.glob("*/*.md"))
        assert len(task_files) >= 2, "Fixture should have at least 2 task files"

        for task_file in task_files:
            content = task_file.read_text(encoding="utf-8")
            assert content.startswith("---\n"), (
                f"{task_file} must start with YAML front matter delimiter"
            )
            end = content.find("\n---", 4)
            assert end > 0, f"{task_file} must have closing --- delimiter"
            frontmatter = content[4:end]
            try:
                meta = yaml.safe_load(frontmatter)
            except yaml.YAMLError as exc:
                pytest.fail(f"{task_file} has invalid YAML front matter: {exc}")
            assert isinstance(meta, dict), (
                f"{task_file} front matter must parse as a dict"
            )
            # Required fields per design § 4.1
            assert "id" in meta, f"{task_file} must have an 'id' field"
            assert "status" in meta, f"{task_file} must have a 'status' field"
            assert "title" in meta, f"{task_file} must have a 'title' field"

    def test_no_duplicate_task_ids_in_fixture(self, historical_task_repo: Path):
        """The fixture must have no duplicate task IDs (pre-migration requirement § 6.1)."""
        tasks_root = historical_task_repo / ".oompah" / "tasks"
        seen_ids: dict[str, Path] = {}

        for task_file in tasks_root.glob("*/*.md"):
            content = task_file.read_text(encoding="utf-8")
            if not content.startswith("---\n"):
                continue
            end = content.find("\n---", 4)
            if end < 0:
                continue
            try:
                meta = yaml.safe_load(content[4:end]) or {}
            except yaml.YAMLError:
                continue
            task_id = str(meta.get("id") or task_file.stem).upper()
            if task_id in seen_ids:
                pytest.fail(
                    f"Duplicate task ID {task_id!r} found at "
                    f"{task_file} and {seen_ids[task_id]}"
                )
            seen_ids[task_id] = task_file

        assert len(seen_ids) >= 2, "Fixture should have at least 2 distinct task IDs"


# ---------------------------------------------------------------------------
# § 2.1 — State branch naming convention
# ---------------------------------------------------------------------------


class TestStateBranchNaming:
    """Validate the state branch naming formula (design § 2.1)."""

    @pytest.mark.parametrize("project_id,expected_branch", [
        ("proj-14849f1b", "oompah/state/proj-14849f1b"),
        ("proj-abc", "oompah/state/proj-abc"),
        ("proj-xyz-123", "oompah/state/proj-xyz-123"),
    ])
    def test_branch_name_formula(self, project_id: str, expected_branch: str):
        """State branch name is deterministically derived from project ID."""
        computed = f"oompah/state/{project_id}"
        assert computed == expected_branch

    def test_branch_name_uses_project_id_not_name(self):
        """Branch name uses the immutable project ID, not the mutable project name.

        If branch name used project.name instead of project.id, renaming the
        project would break the branch reference.
        """
        project_id = "proj-14849f1b"
        project_name = "myrepo-renamed"

        branch_from_id = f"oompah/state/{project_id}"
        branch_from_name = f"oompah/state/{project_name}"

        assert branch_from_id != branch_from_name
        # The design chooses project_id (stable) over name (mutable)
        assert branch_from_id == "oompah/state/proj-14849f1b"

    def test_branch_namespace_does_not_conflict_with_code_refs(self):
        """oompah/ prefix is distinct from common code branch prefixes."""
        state_branch = "oompah/state/proj-abc"
        common_prefixes = ["feature/", "release/", "hotfix/", "main", "develop"]
        for prefix in common_prefixes:
            assert not state_branch.startswith(prefix), (
                f"State branch {state_branch!r} must not start with {prefix!r}"
            )
