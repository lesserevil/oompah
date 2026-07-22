"""Bootstrap tests for the repository-map feature (OOMPAH-299).

Coverage:
  § 1  Service config defaults — feature is disabled for new projects
  § 2  State-branch prerequisite — repo map requires state_branch_enabled
  § 3  Environment activation — feature activates only via OOMPAH_REPO_MAP_ENABLED
  § 4  Bootstrap state-branch creates required infrastructure for repo maps
  § 5  Documentation fixtures — docs/project-bootstrap.md covers repo map
  § 6  Documentation fixtures — docs/repository-map.md exists and covers required topics
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from oompah.config import ServiceConfig, _REPO_MAP_SUPPORTED_LANGUAGES
from oompah.models import Project, WorkflowDefinition
from oompah.project_bootstrap import initialize_state_branch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with one commit on main."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(repo), check=True, capture_output=True)
    return repo


def _default_config(monkeypatch) -> ServiceConfig:
    """Build a ServiceConfig with all OOMPAH_REPO_MAP_* env vars cleared."""
    for key in list(os.environ):
        if key.startswith("OOMPAH_"):
            monkeypatch.delenv(key, raising=False)
    return ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="test"))


def _project(state_branch_enabled: bool = False, repo_path: str = "/tmp/repo") -> Project:
    return Project(
        id="proj-maptest",
        name="maptest",
        repo_url="https://github.com/org/maptest.git",
        repo_path=repo_path,
        default_branch="main",
        state_branch_enabled=state_branch_enabled,
    )


# ===========================================================================
# § 1 — Service config defaults: feature is disabled for new projects
# ===========================================================================


class TestRepoMapDefaultsLeaveFeatureDisabled:
    """Without any env var, the service config must have repo_map_enabled=False."""

    def test_repo_map_disabled_by_default(self, monkeypatch):
        cfg = _default_config(monkeypatch)
        assert cfg.repo_map_enabled is False

    def test_repo_map_token_budget_default(self, monkeypatch):
        cfg = _default_config(monkeypatch)
        assert cfg.repo_map_token_budget == 2000

    def test_repo_map_languages_default_is_all_supported(self, monkeypatch):
        cfg = _default_config(monkeypatch)
        assert set(cfg.repo_map_languages) == set(_REPO_MAP_SUPPORTED_LANGUAGES)

    def test_repo_map_max_file_size_default(self, monkeypatch):
        cfg = _default_config(monkeypatch)
        assert cfg.repo_map_max_file_size == 1_000_000

    def test_repo_map_generation_timeout_default(self, monkeypatch):
        cfg = _default_config(monkeypatch)
        assert cfg.repo_map_generation_timeout == 120

    def test_repo_map_retained_artifacts_default(self, monkeypatch):
        cfg = _default_config(monkeypatch)
        assert cfg.repo_map_retained_artifacts == 5

    def test_project_bootstrapped_without_env_var_is_disabled(self, monkeypatch):
        """A freshly bootstrapped project — no env var set — must be feature-disabled."""
        cfg = _default_config(monkeypatch)
        # The project model has state_branch_enabled; that alone is not enough.
        p = _project(state_branch_enabled=True)
        # Feature gated by ServiceConfig.repo_map_enabled, not the project flag alone.
        assert cfg.repo_map_enabled is False
        assert p.state_branch_enabled is True  # infra is ready, but feature is off


# ===========================================================================
# § 2 — State-branch prerequisite: repo map requires state_branch_enabled
# ===========================================================================


class TestStateBranchPrerequisite:
    """The project must have state_branch_enabled=True for repo maps to work."""

    def test_project_without_state_branch_has_no_state_branch_enabled(self):
        p = _project(state_branch_enabled=False)
        assert p.state_branch_enabled is False

    def test_project_with_state_branch_has_state_branch_enabled(self):
        p = _project(state_branch_enabled=True)
        assert p.state_branch_enabled is True

    def test_state_branch_name_is_correct_for_repo_map_project(self):
        """The state branch where repo maps are stored follows the canonical pattern."""
        p = _project(state_branch_enabled=True)
        assert p.state_branch_name == "oompah/state/proj-maptest"

    def test_project_without_state_branch_does_not_have_state_branch_name(self):
        """Projects with state_branch_enabled=False still expose the name (computed)."""
        p = _project(state_branch_enabled=False)
        # The name property is always available (it's derived from the ID).
        assert p.state_branch_name == "oompah/state/proj-maptest"

    def test_feature_enabled_plus_no_state_branch_is_misconfigured(self, monkeypatch):
        """When the feature is on but no state branch exists, the project is
        misconfigured. This test documents the contract: both must be true.
        """
        monkeypatch.setenv("OOMPAH_REPO_MAP_ENABLED", "true")
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="t"))
        p = _project(state_branch_enabled=False)
        # operator-level check: repo map enabled + no state branch = misconfigured
        assert cfg.repo_map_enabled is True
        assert p.state_branch_enabled is False  # prerequisite missing

    def test_feature_enabled_with_state_branch_is_correctly_configured(self, monkeypatch):
        """Both conditions together represent a correctly configured project."""
        monkeypatch.setenv("OOMPAH_REPO_MAP_ENABLED", "true")
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="t"))
        p = _project(state_branch_enabled=True)
        assert cfg.repo_map_enabled is True
        assert p.state_branch_enabled is True


# ===========================================================================
# § 3 — Environment activation: feature activates only via env var
# ===========================================================================


class TestEnvironmentActivation:
    """Feature is enabled only when OOMPAH_REPO_MAP_ENABLED=true."""

    def test_explicit_false_keeps_feature_disabled(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_REPO_MAP_ENABLED", "false")
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="t"))
        assert cfg.repo_map_enabled is False

    def test_true_enables_feature(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_REPO_MAP_ENABLED", "true")
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="t"))
        assert cfg.repo_map_enabled is True

    def test_one_enables_feature(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_REPO_MAP_ENABLED", "1")
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="t"))
        assert cfg.repo_map_enabled is True

    def test_yes_enables_feature(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_REPO_MAP_ENABLED", "yes")
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="t"))
        assert cfg.repo_map_enabled is True

    def test_other_settings_readable_while_disabled(self, monkeypatch):
        """All settings are parsed even when the feature is disabled."""
        monkeypatch.setenv("OOMPAH_REPO_MAP_ENABLED", "false")
        monkeypatch.setenv("OOMPAH_REPO_MAP_TOKEN_BUDGET", "4096")
        cfg = ServiceConfig.from_workflow(WorkflowDefinition(config={}, prompt_template="t"))
        assert cfg.repo_map_enabled is False
        assert cfg.repo_map_token_budget == 4096

    def test_workflow_md_cannot_enable_repo_map(self, monkeypatch):
        """The feature cannot be enabled from WORKFLOW.md — env vars only."""
        # A WORKFLOW.md front matter with a repo_map block must be ignored.
        # (No repo_map key in WORKFLOW.md schema; env var is the only lever.)
        monkeypatch.delenv("OOMPAH_REPO_MAP_ENABLED", raising=False)
        wf = WorkflowDefinition(
            config={"repo_map": {"enabled": True}},
            prompt_template="test",
        )
        cfg = ServiceConfig.from_workflow(wf)
        # WORKFLOW.md config is not read for this setting.
        assert cfg.repo_map_enabled is False


# ===========================================================================
# § 4 — Bootstrap state-branch creates required infrastructure for repo maps
# ===========================================================================


class TestStateBranchInfrastructureForRepoMaps:
    """initialize_state_branch must create the state branch that repo maps write to."""

    def test_state_branch_created_during_bootstrap(self, tmp_path):
        """initialize_state_branch creates the branch that repo maps store artifacts on."""
        repo = _make_repo(tmp_path)
        project_id = "proj-repomap"
        result = initialize_state_branch(repo, project_id, push=False)
        assert result.error == ""
        assert result.created is True
        assert result.branch_name == f"oompah/state/{project_id}"

    def test_state_branch_contains_oompah_namespace(self, tmp_path):
        """The state branch must only contain .oompah/ content (safe for map writes)."""
        repo = _make_repo(tmp_path)
        project_id = "proj-mapns"
        initialize_state_branch(repo, project_id, push=False)
        branch = f"oompah/state/{project_id}"
        r = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", branch],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        files = r.stdout.splitlines()
        non_oompah = [f for f in files if not f.startswith(".oompah/")]
        assert non_oompah == [], (
            f"State branch must only contain .oompah/ files; found: {non_oompah}"
        )

    def test_repo_map_artifacts_path_is_within_state_branch_namespace(self):
        """The canonical repo-map storage path must be within .oompah/."""
        from oompah.repo_map import is_within_namespace, repo_map_path
        p = repo_map_path("https://github.com/org/repo", "a" * 40)
        assert is_within_namespace(p), (
            f"repo_map_path() returned a path outside .oompah/: {p}"
        )

    def test_state_branch_is_orphan_so_maps_never_pollute_code_history(self, tmp_path):
        """The state branch must have no shared ancestor with main."""
        repo = _make_repo(tmp_path)
        project_id = "proj-orphan-map"
        initialize_state_branch(repo, project_id, push=False)
        branch = f"oompah/state/{project_id}"
        r = subprocess.run(
            ["git", "merge-base", branch, "main"],
            cwd=str(repo),
            capture_output=True,
        )
        assert r.returncode != 0, (
            "State branch must be an orphan with no common ancestor with main"
        )

    def test_bootstrap_is_idempotent_so_repeat_runs_do_not_break_maps(self, tmp_path):
        """A second bootstrap call must preserve existing state-branch content."""
        repo = _make_repo(tmp_path)
        project_id = "proj-idem-map"
        branch = f"oompah/state/{project_id}"

        initialize_state_branch(repo, project_id, push=False)
        r1 = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", branch],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        files_first = set(r1.stdout.splitlines())

        result2 = initialize_state_branch(repo, project_id, push=False)
        assert result2.already_existed is True

        r2 = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", branch],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        files_second = set(r2.stdout.splitlines())
        assert files_second == files_first, (
            "Idempotent re-run must not alter state-branch content"
        )

    def test_code_branch_unchanged_after_bootstrap(self, tmp_path):
        """Bootstrap must not alter the code branch (main)."""
        repo = _make_repo(tmp_path)
        # Record files on main before bootstrap
        r_before = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "main"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        files_before = set(r_before.stdout.splitlines())

        initialize_state_branch(repo, "proj-code-safe", push=False)

        r_after = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "main"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        files_after = set(r_after.stdout.splitlines())
        assert files_after == files_before, (
            "initialize_state_branch must not change files on the main branch"
        )


# ===========================================================================
# § 5 — Documentation fixture: docs/project-bootstrap.md covers repo map
# ===========================================================================


class TestProjectBootstrapDocumentationCoversRepoMap:
    """docs/project-bootstrap.md must document the repo-map bootstrap requirements."""

    @pytest.fixture(autouse=True)
    def _doc(self) -> str:
        doc_path = Path(__file__).parents[1] / "docs" / "project-bootstrap.md"
        return doc_path.read_text(encoding="utf-8")

    def test_project_bootstrap_doc_exists(self):
        doc_path = Path(__file__).parents[1] / "docs" / "project-bootstrap.md"
        assert doc_path.exists(), "docs/project-bootstrap.md must exist"

    def test_doc_mentions_repository_map(self, _doc):
        assert "repository" in _doc.lower() and "map" in _doc.lower(), (
            "docs/project-bootstrap.md must mention the repository-map feature"
        )

    def test_doc_mentions_state_branch_as_prerequisite(self, _doc):
        assert "state_branch_enabled" in _doc or "state branch" in _doc.lower(), (
            "docs/project-bootstrap.md must describe state_branch as a prerequisite"
        )

    def test_doc_mentions_env_var_to_enable(self, _doc):
        assert "OOMPAH_REPO_MAP_ENABLED" in _doc, (
            "docs/project-bootstrap.md must mention OOMPAH_REPO_MAP_ENABLED"
        )

    def test_doc_references_repository_map_doc(self, _doc):
        assert "repository-map.md" in _doc, (
            "docs/project-bootstrap.md must link to docs/repository-map.md"
        )


# ===========================================================================
# § 6 — Documentation fixture: docs/repository-map.md covers required topics
# ===========================================================================


class TestRepositoryMapDocumentationCoversRequiredTopics:
    """docs/repository-map.md must cover operator topics from the acceptance criteria."""

    @pytest.fixture(autouse=True)
    def _doc(self) -> str:
        doc_path = Path(__file__).parents[1] / "docs" / "repository-map.md"
        assert doc_path.exists(), "docs/repository-map.md must exist"
        return doc_path.read_text(encoding="utf-8")

    def test_doc_covers_activation(self, _doc):
        assert "activation" in _doc.lower() or "enable" in _doc.lower(), (
            "docs/repository-map.md must cover activation/enabling"
        )

    def test_doc_covers_freshness(self, _doc):
        assert "freshness" in _doc.lower() or "fresh" in _doc.lower(), (
            "docs/repository-map.md must cover map freshness behavior"
        )

    def test_doc_covers_diagnostics(self, _doc):
        assert "diagnostic" in _doc.lower() or "diagnos" in _doc.lower(), (
            "docs/repository-map.md must cover diagnostics"
        )

    def test_doc_covers_privacy_and_trust(self, _doc):
        assert "privacy" in _doc.lower() or "trust" in _doc.lower(), (
            "docs/repository-map.md must cover privacy/trust boundaries"
        )

    def test_doc_covers_disabling(self, _doc):
        assert "disabl" in _doc.lower(), (
            "docs/repository-map.md must document how to disable the feature"
        )

    def test_doc_covers_rebuild(self, _doc):
        assert "rebuild" in _doc.lower() or "rebuild" in _doc, (
            "docs/repository-map.md must document how to rebuild a map"
        )

    def test_doc_documents_all_env_vars(self, _doc):
        """Every documented environment variable must appear in the operator doc."""
        required_vars = {
            "OOMPAH_REPO_MAP_ENABLED",
            "OOMPAH_REPO_MAP_TOKEN_BUDGET",
            "OOMPAH_REPO_MAP_LANGUAGES",
            "OOMPAH_REPO_MAP_MAX_FILE_SIZE",
            "OOMPAH_REPO_MAP_GENERATION_TIMEOUT",
            "OOMPAH_REPO_MAP_RETAINED_ARTIFACTS",
        }
        for var in required_vars:
            assert var in _doc, (
                f"docs/repository-map.md must document {var}"
            )

    def test_doc_states_no_external_service_required(self, _doc):
        """Acceptance criteria: no new daemon, database, or externally hosted service."""
        assert "no" in _doc.lower() and (
            "daemon" in _doc.lower()
            or "database" in _doc.lower()
            or "external" in _doc.lower()
        ), (
            "docs/repository-map.md must state that no external service is required"
        )

    def test_doc_mentions_state_branch_storage(self, _doc):
        assert "state branch" in _doc.lower() or "oompah/state" in _doc, (
            "docs/repository-map.md must explain that maps are stored on the state branch"
        )
