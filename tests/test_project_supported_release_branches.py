"""Tests for OOMPAH-174 — supported_release_branches on Project.

Covers (section 5 of plans/release-branch-addendums.md):
  - Project model: field default, to_dict, from_dict round-trip (legacy compat)
  - _validate_supported_release_branches: nonempty, unique, not default_branch,
    matched by branches patterns
  - ProjectStore.update(): validation and persistence
  - Server PATCH and POST APIs: field accepted / validated / returned
  - Template: presence of form elements for supported_release_branches (light)

Acceptance:
  - Operators can configure supported release lines without any
    release-addendum feature being enabled.
  - Legacy records (no supported_release_branches key) default to [].
  - Create/update/serialisation round-trips preserve the ordered list.
  - Invalid values return 400 validation errors.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from oompah.models import Project
from oompah.projects import ProjectError, ProjectStore, _validate_supported_release_branches


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _base_dict(**kwargs) -> dict:
    """Return a minimal valid project dict for Project.from_dict()."""
    d: dict = {
        "id": "proj-abc",
        "name": "myproject",
        "repo_url": "https://example.com/repo.git",
        "repo_path": "/tmp/repo",
        "branches": ["main", "release/*"],
        "default_branch": "main",
    }
    d.update(kwargs)
    return d


def _make_project(
    *,
    pid: str = "proj-1",
    name: str = "myproject",
    branches: list[str] | None = None,
    default_branch: str = "main",
    supported_release_branches: list[str] | None = None,
) -> Project:
    return Project(
        id=pid,
        name=name,
        repo_url="https://github.com/org/repo.git",
        repo_path=f"/tmp/repos/{name}",
        branch=default_branch,
        branches=branches or ["main", "release/*"],
        default_branch=default_branch,
        supported_release_branches=supported_release_branches or [],
    )


def _make_project_store(tmp_path) -> ProjectStore:
    store = ProjectStore(
        path=str(tmp_path / "projects.json"),
        repos_root=str(tmp_path / "repos"),
        worktree_root=str(tmp_path / "wt"),
    )
    p = _make_project()
    store._projects[p.id] = p
    store._save()
    return store


# ===========================================================================
# 1. Project model: field default, to_dict, from_dict, legacy compat
# ===========================================================================


class TestProjectModel:
    """Project dataclass field tests."""

    def test_default_supported_release_branches_is_empty(self):
        p = _make_project()
        assert p.supported_release_branches == []

    def test_to_dict_always_includes_field_when_empty(self):
        p = _make_project()
        d = p.to_dict()
        assert "supported_release_branches" in d
        assert d["supported_release_branches"] == []

    def test_to_dict_includes_field_with_values(self):
        p = _make_project(supported_release_branches=["release/1.1", "release/1.0"])
        d = p.to_dict()
        assert d["supported_release_branches"] == ["release/1.1", "release/1.0"]

    def test_to_dict_preserves_order(self):
        branches = ["release/2.0", "release/1.1", "release/1.0"]
        p = _make_project(supported_release_branches=branches)
        assert p.to_dict()["supported_release_branches"] == branches

    def test_to_safe_dict_includes_field(self):
        p = _make_project(supported_release_branches=["release/1.0"])
        d = p.to_safe_dict()
        assert "supported_release_branches" in d
        assert d["supported_release_branches"] == ["release/1.0"]

    # from_dict tests ---

    def test_from_dict_reads_supported_release_branches(self):
        d = _base_dict(supported_release_branches=["release/1.0", "release/1.1"])
        p = Project.from_dict(d)
        assert p.supported_release_branches == ["release/1.0", "release/1.1"]

    def test_from_dict_missing_key_defaults_to_empty_list(self):
        """Legacy project records that lack the field default to []."""
        d = _base_dict()  # no supported_release_branches key
        p = Project.from_dict(d)
        assert p.supported_release_branches == []

    def test_from_dict_null_defaults_to_empty_list(self):
        d = _base_dict(supported_release_branches=None)
        p = Project.from_dict(d)
        assert p.supported_release_branches == []

    def test_from_dict_strips_blank_entries(self):
        d = _base_dict(supported_release_branches=["  release/1.0  ", "  ", "release/1.1"])
        p = Project.from_dict(d)
        assert "release/1.0" in p.supported_release_branches
        assert "release/1.1" in p.supported_release_branches
        assert "" not in p.supported_release_branches
        assert "  " not in p.supported_release_branches

    def test_from_dict_ignores_empty_string_entries(self):
        d = _base_dict(supported_release_branches=["", "release/1.0"])
        p = Project.from_dict(d)
        assert p.supported_release_branches == ["release/1.0"]

    def test_round_trip_empty(self):
        p = _make_project()
        p2 = Project.from_dict(p.to_dict())
        assert p2.supported_release_branches == []

    def test_round_trip_with_values(self):
        p = _make_project(supported_release_branches=["release/1.1", "release/1.0"])
        p2 = Project.from_dict(p.to_dict())
        assert p2.supported_release_branches == ["release/1.1", "release/1.0"]

    def test_round_trip_preserves_order(self):
        branches = ["release/3.0", "release/1.0", "release/2.0"]
        p = _make_project(supported_release_branches=branches)
        p2 = Project.from_dict(p.to_dict())
        assert p2.supported_release_branches == branches


# ===========================================================================
# 2. _validate_supported_release_branches helper
# ===========================================================================


class TestValidateSupportedReleaseBranches:
    """Unit tests for the validation helper."""

    def test_valid_single_entry(self):
        result = _validate_supported_release_branches(
            ["release/1.0"], ["main", "release/*"], "main"
        )
        assert result == ["release/1.0"]

    def test_valid_multiple_entries(self):
        result = _validate_supported_release_branches(
            ["release/1.1", "release/1.0"], ["main", "release/*"], "main"
        )
        assert result == ["release/1.1", "release/1.0"]

    def test_empty_list_is_valid(self):
        result = _validate_supported_release_branches([], ["main", "release/*"], "main")
        assert result == []

    def test_order_is_preserved(self):
        raw = ["release/2.0", "release/0.9", "release/1.5"]
        result = _validate_supported_release_branches(
            raw, ["main", "release/*"], "main"
        )
        assert result == raw

    def test_strips_whitespace(self):
        result = _validate_supported_release_branches(
            ["  release/1.0  "], ["main", "release/*"], "main"
        )
        assert result == ["release/1.0"]

    def test_rejects_non_list(self):
        with pytest.raises(ProjectError, match="must be a list"):
            _validate_supported_release_branches(
                "release/1.0", ["main", "release/*"], "main"
            )

    def test_rejects_non_string_entry(self):
        with pytest.raises(ProjectError, match="entries must be strings"):
            _validate_supported_release_branches(
                [123], ["main", "release/*"], "main"
            )

    def test_rejects_empty_string_entry(self):
        with pytest.raises(ProjectError, match="must not be empty"):
            _validate_supported_release_branches(
                [""], ["main", "release/*"], "main"
            )

    def test_rejects_whitespace_only_entry(self):
        with pytest.raises(ProjectError, match="must not be empty"):
            _validate_supported_release_branches(
                ["   "], ["main", "release/*"], "main"
            )

    def test_rejects_duplicate_exact(self):
        with pytest.raises(ProjectError, match="duplicate"):
            _validate_supported_release_branches(
                ["release/1.0", "release/1.0"], ["main", "release/*"], "main"
            )

    def test_rejects_duplicate_case_insensitive(self):
        """Uniqueness is checked after case-insensitive normalisation.

        Note: fnmatch on Linux is case-sensitive, so we use a case-insensitive
        branches pattern (Release/*) that matches the mixed-case entry.
        """
        with pytest.raises(ProjectError, match="duplicate"):
            _validate_supported_release_branches(
                ["release/1.0", "RELEASE/1.0"],
                ["main", "release/*", "RELEASE/*"],
                "main",
            )

    def test_rejects_default_branch(self):
        with pytest.raises(ProjectError, match="must not include the default branch"):
            _validate_supported_release_branches(
                ["main"], ["main", "release/*"], "main"
            )

    def test_rejects_entry_not_matching_branches_patterns(self):
        with pytest.raises(ProjectError, match="does not match any pattern"):
            _validate_supported_release_branches(
                ["hotfix/1.0"], ["main", "release/*"], "main"
            )

    def test_exact_branch_in_patterns_is_accepted(self):
        """An exact branch name that matches a literal pattern is accepted."""
        result = _validate_supported_release_branches(
            ["release/1.0"], ["release/1.0", "release/*", "main"], "main"
        )
        assert result == ["release/1.0"]

    def test_glob_match_is_accepted(self):
        """Glob patterns in branches_patterns work via fnmatch."""
        result = _validate_supported_release_branches(
            ["release/1.2.3"], ["main", "release/*"], "main"
        )
        assert result == ["release/1.2.3"]

    def test_default_branch_exclusion_is_case_sensitive(self):
        """Exclusion uses exact string comparison, not normalised."""
        # 'Main' != 'main' so this should pass (different case)
        # The entry must still match a branches pattern though.
        result = _validate_supported_release_branches(
            ["Main"], ["main", "Main", "release/*"], "main"
        )
        assert result == ["Main"]

    def test_multiple_patterns_any_match_accepted(self):
        """Entry is valid if it matches ANY of the patterns."""
        result = _validate_supported_release_branches(
            ["hotfix/critical"], ["main", "release/*", "hotfix/*"], "main"
        )
        assert result == ["hotfix/critical"]


# ===========================================================================
# 3. ProjectStore.update() — validation and persistence
# ===========================================================================


class TestProjectStoreUpdate:
    """ProjectStore.update() tests for supported_release_branches."""

    @pytest.fixture(autouse=True)
    def store(self, tmp_path):
        self.store = _make_project_store(tmp_path)

    def test_update_empty_list_clears_field(self):
        updated = self.store.update("proj-1", supported_release_branches=[])
        assert updated is not None
        assert updated.supported_release_branches == []

    def test_update_null_clears_to_empty(self):
        self.store.update("proj-1", supported_release_branches=["release/1.0"])
        updated = self.store.update("proj-1", supported_release_branches=None)
        assert updated.supported_release_branches == []

    def test_update_sets_valid_entries(self):
        updated = self.store.update(
            "proj-1",
            supported_release_branches=["release/1.1", "release/1.0"],
        )
        assert updated.supported_release_branches == ["release/1.1", "release/1.0"]

    def test_update_preserves_order(self):
        ordered = ["release/2.0", "release/1.0"]
        updated = self.store.update("proj-1", supported_release_branches=ordered)
        assert updated.supported_release_branches == ordered

    def test_update_persists_to_disk(self, tmp_path):
        self.store.update(
            "proj-1", supported_release_branches=["release/1.0"]
        )
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        proj = store2.get("proj-1")
        assert proj is not None
        assert proj.supported_release_branches == ["release/1.0"]

    def test_update_rejects_non_list(self):
        with pytest.raises(ProjectError, match="must be a list"):
            self.store.update("proj-1", supported_release_branches="release/1.0")

    def test_update_rejects_non_string_entry(self):
        with pytest.raises(ProjectError, match="entries must be strings"):
            self.store.update("proj-1", supported_release_branches=[42])

    def test_update_rejects_empty_name(self):
        with pytest.raises(ProjectError, match="must not be empty"):
            self.store.update("proj-1", supported_release_branches=[""])

    def test_update_rejects_duplicate_after_normalisation(self):
        with pytest.raises(ProjectError, match="duplicate"):
            self.store.update(
                "proj-1",
                supported_release_branches=["release/1.0", "RELEASE/1.0"],
            )

    def test_update_rejects_default_branch(self):
        with pytest.raises(ProjectError, match="must not include the default branch"):
            self.store.update("proj-1", supported_release_branches=["main"])

    def test_update_rejects_branch_not_matching_patterns(self):
        with pytest.raises(ProjectError, match="does not match any pattern"):
            self.store.update(
                "proj-1", supported_release_branches=["hotfix/oops"]
            )

    def test_update_uses_effective_branches_when_updated_together(self, tmp_path):
        """When branches and supported_release_branches are updated together,
        validation uses the NEW branches value."""
        # hotfix/* is not currently in project.branches, so we add it along
        # with a matching supported_release_branches entry.
        updated = self.store.update(
            "proj-1",
            branches=["main", "release/*", "hotfix/*"],
            supported_release_branches=["hotfix/1.x"],
        )
        assert updated is not None
        assert "hotfix/1.x" in updated.supported_release_branches

    def test_update_uses_effective_default_branch_when_updated_together(self, tmp_path):
        """When default_branch changes, the exclusion check uses the new value."""
        # Change default_branch to release/1.0 — then main should become valid
        # as a supported release line (if it matches a branch pattern).
        updated = self.store.update(
            "proj-1",
            branches=["main", "release/*"],
            default_branch="release/1.0",
            supported_release_branches=["main"],
        )
        assert updated is not None
        assert "main" in updated.supported_release_branches

    def test_update_blocks_new_default_branch_in_supported(self, tmp_path):
        """When default_branch is changed to X, X must be excluded."""
        with pytest.raises(ProjectError, match="must not include the default branch"):
            self.store.update(
                "proj-1",
                branches=["main", "release/*"],
                default_branch="release/1.0",
                supported_release_branches=["release/1.0"],
            )

    def test_update_unknown_project_returns_none(self):
        result = self.store.update("proj-nonexistent", supported_release_branches=[])
        assert result is None

    def test_existing_project_without_field_can_still_be_updated(self, tmp_path):
        """Projects that predate the field continue to work after update."""
        store2 = ProjectStore(
            path=self.store.path,
            repos_root=str(tmp_path / "repos"),
            worktree_root=str(tmp_path / "wt"),
        )
        proj = store2.get("proj-1")
        assert proj is not None
        assert proj.supported_release_branches == []
        # Should accept an update
        updated = store2.update("proj-1", supported_release_branches=["release/1.0"])
        assert updated.supported_release_branches == ["release/1.0"]


# ===========================================================================
# 4. Server API — GET and PATCH
# ===========================================================================


class TestServerApiSupportedReleaseBranches:
    """Server PATCH/GET API tests for supported_release_branches."""

    @pytest.fixture(autouse=True)
    def _patch_server(self, tmp_path):
        from oompah import server
        from fastapi.testclient import TestClient
        from oompah.server import app

        project = _make_project()
        store = _make_project_store(tmp_path)
        store._projects.clear()
        store._projects[project.id] = project
        store._save()

        orch = MagicMock()
        orch.project_store = store
        orch._observers = []
        orch._state_only_observers = []
        orch._activity_observers = []
        orch.get_snapshot.return_value = {"counts": {}, "running": {}}

        old_orch = server._orchestrator
        server._orchestrator = orch
        self.client = TestClient(app)
        self.project = project
        self.store = store
        yield
        server._orchestrator = old_orch

    # GET tests ---

    def test_get_includes_field_when_empty(self):
        res = self.client.get(f"/api/v1/projects/{self.project.id}")
        assert res.status_code == 200
        body = res.json()
        assert "supported_release_branches" in body
        assert body["supported_release_branches"] == []

    def test_get_includes_field_with_values(self):
        self.store.update(
            self.project.id,
            supported_release_branches=["release/1.0"],
        )
        res = self.client.get(f"/api/v1/projects/{self.project.id}")
        assert res.status_code == 200
        body = res.json()
        assert body["supported_release_branches"] == ["release/1.0"]

    # PATCH valid tests ---

    def test_patch_sets_field(self):
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"supported_release_branches": ["release/1.1", "release/1.0"]},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["supported_release_branches"] == ["release/1.1", "release/1.0"]

    def test_patch_clears_with_empty_list(self):
        self.store.update(
            self.project.id, supported_release_branches=["release/1.0"]
        )
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"supported_release_branches": []},
        )
        assert res.status_code == 200
        assert res.json()["supported_release_branches"] == []

    def test_patch_clears_with_null(self):
        self.store.update(
            self.project.id, supported_release_branches=["release/1.0"]
        )
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"supported_release_branches": None},
        )
        assert res.status_code == 200
        assert res.json()["supported_release_branches"] == []

    def test_patch_persists_to_store(self):
        self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"supported_release_branches": ["release/1.0"]},
        )
        proj = self.store.get(self.project.id)
        assert proj.supported_release_branches == ["release/1.0"]

    # PATCH invalid tests ---

    def test_patch_rejects_non_list(self):
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"supported_release_branches": "release/1.0"},
        )
        assert res.status_code == 400
        assert "supported_release_branches" in res.json()["error"]["message"]

    def test_patch_rejects_list_with_non_strings(self):
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"supported_release_branches": [123, "release/1.0"]},
        )
        assert res.status_code == 400

    def test_patch_rejects_empty_branch_name(self):
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"supported_release_branches": [""]},
        )
        assert res.status_code == 400

    def test_patch_rejects_duplicate_entries(self):
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"supported_release_branches": ["release/1.0", "release/1.0"]},
        )
        assert res.status_code == 400

    def test_patch_rejects_default_branch(self):
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"supported_release_branches": ["main"]},
        )
        assert res.status_code == 400

    def test_patch_rejects_branch_not_matching_patterns(self):
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"supported_release_branches": ["hotfix/oops"]},
        )
        assert res.status_code == 400

    def test_patch_not_sent_leaves_field_unchanged(self):
        """Not including supported_release_branches in a PATCH body
        leaves the existing value untouched."""
        self.store.update(
            self.project.id, supported_release_branches=["release/1.0"]
        )
        res = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            json={"name": "renamed-project"},
        )
        assert res.status_code == 200
        assert res.json()["supported_release_branches"] == ["release/1.0"]


# ===========================================================================
# 5. Template: field presence (light smoke tests)
# ===========================================================================


class TestTemplatePresence:
    """Light checks that the projects.html template includes the new field."""

    def test_template_contains_supported_release_branches_input_id(self, tmp_path):
        """The edit form must have an input element keyed on the field name."""
        import pathlib
        template_path = pathlib.Path("oompah/templates/projects.html")
        content = template_path.read_text()
        assert "edit-supported-release-branches-" in content, (
            "Expected an edit input for supported_release_branches in projects.html"
        )

    def test_template_contains_display_data_field(self, tmp_path):
        """The read-only view must expose a data-field attribute for the field."""
        import pathlib
        template_path = pathlib.Path("oompah/templates/projects.html")
        content = template_path.read_text()
        assert "supported-release-branches" in content, (
            "Expected data-field for supported_release_branches in projects.html"
        )

    def test_template_mentions_removing_does_not_cancel_addendums(self):
        """The template must include the removal-warning text per spec."""
        import pathlib
        template_path = pathlib.Path("oompah/templates/projects.html")
        content = template_path.read_text()
        assert "not delete" in content or "does not delete" in content, (
            "Template should explain removing a line does not delete the branch "
            "or cancel existing addendums"
        )

    def test_template_saveproject_sends_supported_release_branches(self):
        """saveProject() must include supported_release_branches in the request body."""
        import pathlib
        template_path = pathlib.Path("oompah/templates/projects.html")
        content = template_path.read_text()
        assert "supportedReleaseBranches" in content or "supported_release_branches" in content, (
            "saveProject() must send supported_release_branches in the PATCH body"
        )
