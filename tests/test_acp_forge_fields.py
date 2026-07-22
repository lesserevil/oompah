"""Tests for forge_kind/forge_base_url exposure in ACP project tools (OOMPAH-327).

Covers:
- _project_snapshot() includes forge_kind and forge_base_url.
- _project_snapshot() includes external_issue_intake_enabled as alias.
- _PROJECT_READABLE_FIELDS includes forge_kind, forge_base_url,
  external_issue_intake_enabled.
- _PROJECT_UPDATABLE_FIELDS includes forge_kind and forge_base_url.
- _exec_get_project() returns forge fields in JSON output.
- _exec_list_projects() returns forge fields for each project.
- _exec_update_project() accepts forge_kind and forge_base_url as valid fields.
- GitHub-defaulted projects have correct defaults (forge_kind='github').
- GitLab projects have forge_kind='gitlab' and non-default forge_base_url.
- Legacy GitHub payloads work without forge fields (backward compat).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    project_id: str = "proj-test",
    name: str = "test-project",
    repo_url: str = "https://github.com/acme/test-project",
    forge_kind: str = "github",
    forge_base_url: str = "https://github.com",
    tracker_kind: str | None = None,
    tracker_owner: str | None = None,
    tracker_repo: str | None = None,
    github_issue_intake_enabled: bool = False,
    paused: bool = False,
) -> MagicMock:
    """Build a mock Project with realistic field defaults including forge config."""
    p = MagicMock()
    p.id = project_id
    p.name = name
    p.repo_url = repo_url
    # Set string fields explicitly so MagicMock doesn't return a MagicMock
    # when str_attr() checks isinstance(value, str).
    p.forge_kind = forge_kind
    p.forge_base_url = forge_base_url
    p.tracker_kind = tracker_kind
    p.tracker_owner = tracker_owner
    p.tracker_repo = tracker_repo
    p.github_issue_intake_enabled = github_issue_intake_enabled
    p.github_project_node_id = None
    p.status_actor_login = None
    p.status_label_authorized_logins = []
    p.intake_auto_promote = True
    p.paused = paused
    return p


def _make_store(project: MagicMock | None = None) -> MagicMock:
    store = MagicMock()
    store.get.return_value = project
    store.update.return_value = project
    store.list_all.return_value = [] if project is None else [project]
    return store


# ---------------------------------------------------------------------------
# _project_snapshot() forge fields
# ---------------------------------------------------------------------------


class TestProjectSnapshotForgeFields:
    """_project_snapshot() must include forge_kind, forge_base_url, and
    external_issue_intake_enabled for all project types."""

    def test_snapshot_includes_forge_kind_github(self) -> None:
        """Snapshot includes forge_kind for a GitHub project."""
        from oompah.acp_tools import _project_snapshot

        p = _make_project(forge_kind="github", forge_base_url="https://github.com")
        snap = _project_snapshot(p)

        assert "forge_kind" in snap, "forge_kind must be in _project_snapshot output"
        assert snap["forge_kind"] == "github"

    def test_snapshot_includes_forge_kind_gitlab(self) -> None:
        """Snapshot includes forge_kind for a GitLab project."""
        from oompah.acp_tools import _project_snapshot

        p = _make_project(
            forge_kind="gitlab",
            forge_base_url="https://gitlab.com",
            repo_url="https://gitlab.com/my-group/my-project",
        )
        snap = _project_snapshot(p)

        assert snap["forge_kind"] == "gitlab"

    def test_snapshot_includes_forge_base_url(self) -> None:
        """Snapshot includes forge_base_url."""
        from oompah.acp_tools import _project_snapshot

        p = _make_project(forge_kind="github", forge_base_url="https://github.com")
        snap = _project_snapshot(p)

        assert "forge_base_url" in snap
        assert snap["forge_base_url"] == "https://github.com"

    def test_snapshot_includes_self_managed_gitlab_url(self) -> None:
        """Snapshot preserves non-default GitLab base URL for self-managed instances."""
        from oompah.acp_tools import _project_snapshot

        p = _make_project(
            forge_kind="gitlab",
            forge_base_url="https://gitlab.mycompany.com",
            repo_url="https://gitlab.mycompany.com/team/project",
        )
        snap = _project_snapshot(p)

        assert snap["forge_base_url"] == "https://gitlab.mycompany.com"

    def test_snapshot_includes_external_issue_intake_enabled(self) -> None:
        """Snapshot includes external_issue_intake_enabled as forge-neutral alias."""
        from oompah.acp_tools import _project_snapshot

        p = _make_project(github_issue_intake_enabled=True)
        snap = _project_snapshot(p)

        assert "external_issue_intake_enabled" in snap, (
            "external_issue_intake_enabled must be in snapshot for forge-neutral access."
        )
        assert snap["external_issue_intake_enabled"] is True

    def test_snapshot_external_intake_mirrors_github_intake(self) -> None:
        """external_issue_intake_enabled has the same value as github_issue_intake_enabled."""
        from oompah.acp_tools import _project_snapshot

        p = _make_project(github_issue_intake_enabled=False)
        snap = _project_snapshot(p)

        assert snap["external_issue_intake_enabled"] == snap["github_issue_intake_enabled"]

    def test_snapshot_forge_kind_defaults_to_github_for_mock_without_attr(self) -> None:
        """When project has no forge_kind attr (legacy), snapshot defaults to 'github'."""
        from oompah.acp_tools import _project_snapshot

        # Simulate a project object that has forge_kind as a MagicMock (non-string)
        p = MagicMock()
        p.id = "proj-legacy"
        p.name = "legacy"
        p.repo_url = "https://github.com/org/repo"
        p.status_label_authorized_logins = []
        p.github_issue_intake_enabled = False
        # Do NOT set forge_kind / forge_base_url — let them be MagicMocks

        snap = _project_snapshot(p)

        # str_attr must fall back to defaults for non-string values
        assert snap["forge_kind"] == "github", (
            "forge_kind must default to 'github' when the attribute is missing/non-string."
        )
        assert snap["forge_base_url"] == "https://github.com", (
            "forge_base_url must default to 'https://github.com' when missing/non-string."
        )


# ---------------------------------------------------------------------------
# _PROJECT_READABLE_FIELDS and _PROJECT_UPDATABLE_FIELDS
# ---------------------------------------------------------------------------


class TestForgeFieldSets:
    """forge_kind and forge_base_url must be in the readable and updatable sets."""

    def test_forge_kind_in_readable_fields(self) -> None:
        from oompah.acp_tools import _PROJECT_READABLE_FIELDS

        assert "forge_kind" in _PROJECT_READABLE_FIELDS, (
            "forge_kind must be in _PROJECT_READABLE_FIELDS so agents can "
            "inspect the forge without calling the HTTP API."
        )

    def test_forge_base_url_in_readable_fields(self) -> None:
        from oompah.acp_tools import _PROJECT_READABLE_FIELDS

        assert "forge_base_url" in _PROJECT_READABLE_FIELDS, (
            "forge_base_url must be in _PROJECT_READABLE_FIELDS."
        )

    def test_external_issue_intake_in_readable_fields(self) -> None:
        """external_issue_intake_enabled is readable (forge-neutral alias)."""
        from oompah.acp_tools import _PROJECT_READABLE_FIELDS

        assert "external_issue_intake_enabled" in _PROJECT_READABLE_FIELDS, (
            "external_issue_intake_enabled must be in _PROJECT_READABLE_FIELDS "
            "as the forge-neutral alias for github_issue_intake_enabled."
        )

    def test_forge_kind_in_updatable_fields(self) -> None:
        from oompah.acp_tools import _PROJECT_UPDATABLE_FIELDS

        assert "forge_kind" in _PROJECT_UPDATABLE_FIELDS, (
            "forge_kind must be in _PROJECT_UPDATABLE_FIELDS so agents can "
            "switch a project between GitHub and GitLab."
        )

    def test_forge_base_url_in_updatable_fields(self) -> None:
        from oompah.acp_tools import _PROJECT_UPDATABLE_FIELDS

        assert "forge_base_url" in _PROJECT_UPDATABLE_FIELDS, (
            "forge_base_url must be in _PROJECT_UPDATABLE_FIELDS."
        )

    def test_external_issue_intake_not_in_updatable_fields(self) -> None:
        """external_issue_intake_enabled is read-only (alias); update via
        github_issue_intake_enabled."""
        from oompah.acp_tools import _PROJECT_UPDATABLE_FIELDS

        # external_issue_intake_enabled is a read alias only — the canonical
        # write field is github_issue_intake_enabled to preserve backward compat.
        assert "external_issue_intake_enabled" not in _PROJECT_UPDATABLE_FIELDS, (
            "external_issue_intake_enabled must NOT be updatable — it is a "
            "read-only alias; update via github_issue_intake_enabled instead."
        )


# ---------------------------------------------------------------------------
# _exec_get_project() returns forge fields
# ---------------------------------------------------------------------------


class TestExecGetProjectForgeFields:
    """get_project JSON output must include forge_kind and forge_base_url."""

    def test_get_project_returns_forge_kind(self) -> None:
        from oompah.acp_tools import _exec_get_project

        p = _make_project(forge_kind="github", forge_base_url="https://github.com")
        store = _make_store(p)

        result = _exec_get_project(store, "proj-test")
        data = json.loads(result)

        assert "forge_kind" in data, "get_project result must include forge_kind"
        assert data["forge_kind"] == "github"

    def test_get_project_returns_forge_base_url(self) -> None:
        from oompah.acp_tools import _exec_get_project

        p = _make_project(forge_kind="github", forge_base_url="https://github.com")
        store = _make_store(p)

        result = _exec_get_project(store, "proj-test")
        data = json.loads(result)

        assert "forge_base_url" in data
        assert data["forge_base_url"] == "https://github.com"

    def test_get_project_returns_gitlab_forge_kind(self) -> None:
        from oompah.acp_tools import _exec_get_project

        p = _make_project(
            forge_kind="gitlab",
            forge_base_url="https://gitlab.com",
            repo_url="https://gitlab.com/mygroup/myproject",
        )
        store = _make_store(p)

        result = _exec_get_project(store, "proj-test")
        data = json.loads(result)

        assert data["forge_kind"] == "gitlab"
        assert data["forge_base_url"] == "https://gitlab.com"

    def test_get_project_returns_self_managed_gitlab_url(self) -> None:
        from oompah.acp_tools import _exec_get_project

        p = _make_project(
            forge_kind="gitlab",
            forge_base_url="https://gitlab.myorg.example",
            repo_url="https://gitlab.myorg.example/team/project",
        )
        store = _make_store(p)

        result = _exec_get_project(store, "proj-test")
        data = json.loads(result)

        assert data["forge_base_url"] == "https://gitlab.myorg.example"

    def test_get_project_returns_external_issue_intake_enabled(self) -> None:
        from oompah.acp_tools import _exec_get_project

        p = _make_project(github_issue_intake_enabled=True)
        store = _make_store(p)

        result = _exec_get_project(store, "proj-test")
        data = json.loads(result)

        assert "external_issue_intake_enabled" in data
        assert data["external_issue_intake_enabled"] is True


# ---------------------------------------------------------------------------
# _exec_list_projects() returns forge fields
# ---------------------------------------------------------------------------


class TestExecListProjectsForgeFields:
    """list_projects JSON output must include forge fields for each project."""

    def test_list_projects_includes_forge_kind(self) -> None:
        from oompah.acp_tools import _exec_list_projects

        github_proj = _make_project(
            project_id="proj-gh",
            forge_kind="github",
            forge_base_url="https://github.com",
        )
        gitlab_proj = _make_project(
            project_id="proj-gl",
            forge_kind="gitlab",
            forge_base_url="https://gitlab.com",
            repo_url="https://gitlab.com/gl-group/gl-proj",
        )
        store = _make_store()
        store.list_all.return_value = [github_proj, gitlab_proj]

        result = _exec_list_projects(store)
        data = json.loads(result)

        assert data["projects"][0]["forge_kind"] == "github"
        assert data["projects"][1]["forge_kind"] == "gitlab"

    def test_list_projects_includes_forge_base_url(self) -> None:
        from oompah.acp_tools import _exec_list_projects

        p = _make_project(forge_kind="github", forge_base_url="https://github.com")
        store = _make_store()
        store.list_all.return_value = [p]

        result = _exec_list_projects(store)
        data = json.loads(result)

        assert "forge_base_url" in data["projects"][0]

    def test_list_projects_includes_external_issue_intake_enabled(self) -> None:
        from oompah.acp_tools import _exec_list_projects

        p = _make_project(github_issue_intake_enabled=True)
        store = _make_store()
        store.list_all.return_value = [p]

        result = _exec_list_projects(store)
        data = json.loads(result)

        assert "external_issue_intake_enabled" in data["projects"][0]
        assert data["projects"][0]["external_issue_intake_enabled"] is True


# ---------------------------------------------------------------------------
# _exec_update_project() accepts forge fields
# ---------------------------------------------------------------------------


class TestExecUpdateProjectForgeFields:
    """update_project must accept forge_kind and forge_base_url as valid fields."""

    def test_update_project_accepts_forge_kind(self) -> None:
        from oompah.acp_tools import _exec_update_project

        p = _make_project(forge_kind="gitlab", forge_base_url="https://gitlab.com")
        store = _make_store(p)
        store.update.return_value = p

        result = _exec_update_project(store, "proj-test", '{"forge_kind": "gitlab"}')
        data = json.loads(result)

        assert data.get("updated") is True
        store.update.assert_called_once_with("proj-test", forge_kind="gitlab")

    def test_update_project_accepts_forge_base_url(self) -> None:
        from oompah.acp_tools import _exec_update_project

        p = _make_project(
            forge_kind="gitlab",
            forge_base_url="https://gitlab.mycompany.com",
        )
        store = _make_store(p)
        store.update.return_value = p

        fields = {"forge_kind": "gitlab", "forge_base_url": "https://gitlab.mycompany.com"}
        result = _exec_update_project(store, "proj-test", json.dumps(fields))
        data = json.loads(result)

        assert data.get("updated") is True
        store.update.assert_called_once_with(
            "proj-test",
            forge_kind="gitlab",
            forge_base_url="https://gitlab.mycompany.com",
        )

    def test_update_project_forge_kind_rejected_unknown_value(self) -> None:
        """Validation in ProjectStore.update() rejects unknown forge kinds.

        The ACP layer passes through forge_kind; ProjectStore validates.
        An unknown value should propagate back as an error string.
        """
        from oompah.acp_tools import _exec_update_project

        store = _make_store()
        store.update.side_effect = ValueError("forge_kind must be 'github' or 'gitlab'")

        result = _exec_update_project(store, "proj-test", '{"forge_kind": "bitbucket"}')

        assert result.startswith("error:"), (
            "An invalid forge_kind should result in an error: response."
        )
        assert "forge_kind" in result or "bitbucket" in result or "github" in result

    def test_update_project_external_issue_intake_rejected(self) -> None:
        """external_issue_intake_enabled is a read-only alias and must be rejected."""
        from oompah.acp_tools import _exec_update_project

        store = _make_store()
        result = _exec_update_project(
            store,
            "proj-test",
            '{"external_issue_intake_enabled": true}',
        )

        assert result.startswith("error:"), (
            "external_issue_intake_enabled is not in UPDATABLE_FIELDS and must "
            "be rejected; use github_issue_intake_enabled instead."
        )
        store.update.assert_not_called()

    def test_update_project_gitlab_full_config(self) -> None:
        """Full GitLab project configuration update passes through."""
        from oompah.acp_tools import _exec_update_project

        p = _make_project(
            forge_kind="gitlab",
            forge_base_url="https://gitlab.com",
            tracker_kind="gitlab_issues",
            tracker_owner="my-group",
            tracker_repo="my-project",
        )
        store = _make_store(p)
        store.update.return_value = p

        fields = {
            "forge_kind": "gitlab",
            "forge_base_url": "https://gitlab.com",
            "tracker_kind": "gitlab_issues",
            "tracker_owner": "my-group",
            "tracker_repo": "my-project",
        }
        result = _exec_update_project(store, "proj-test", json.dumps(fields))
        data = json.loads(result)

        assert data.get("updated") is True
        store.update.assert_called_once_with(
            "proj-test",
            forge_kind="gitlab",
            forge_base_url="https://gitlab.com",
            tracker_kind="gitlab_issues",
            tracker_owner="my-group",
            tracker_repo="my-project",
        )


# ---------------------------------------------------------------------------
# Backward compatibility — GitHub-defaulted projects
# ---------------------------------------------------------------------------


class TestLegacyGitHubProjectCompat:
    """Legacy GitHub projects (without explicit forge_kind) must work correctly."""

    def test_legacy_project_defaults_forge_kind_to_github(self) -> None:
        """A project mock without explicit forge attrs defaults to github."""
        from oompah.acp_tools import _project_snapshot

        # Legacy project mock: forge_kind returns a MagicMock (non-string)
        p = MagicMock()
        p.id = "proj-legacy"
        p.name = "legacy"
        p.repo_url = "https://github.com/org/legacy"
        p.status_label_authorized_logins = []
        p.github_issue_intake_enabled = False
        p.intake_auto_promote = True
        p.paused = False
        # forge_kind is NOT set — MagicMock will return a MagicMock object

        snap = _project_snapshot(p)

        assert snap["forge_kind"] == "github"
        assert snap["forge_base_url"] == "https://github.com"

    def test_list_projects_handles_legacy_project(self) -> None:
        """list_projects produces valid JSON even for projects without forge attrs.

        A legacy project may be a MagicMock where forge_kind/forge_base_url
        are unset (return non-string MagicMock objects). The str_attr helper
        must fall back to the github defaults so JSON serialization succeeds.
        Other JSON-sensitive fields (tracker_kind, tracker_owner, tracker_repo,
        status_actor_login, github_project_node_id) must be set to None explicitly
        to avoid MagicMock JSON-serialization failures.
        """
        from oompah.acp_tools import _exec_list_projects

        legacy = MagicMock()
        legacy.id = "proj-legacy"
        legacy.name = "legacy"
        legacy.repo_url = "https://github.com/org/legacy"
        legacy.status_label_authorized_logins = []
        legacy.github_issue_intake_enabled = False
        legacy.intake_auto_promote = True
        legacy.paused = False
        # Set other string-type fields to None to avoid MagicMock JSON errors.
        legacy.tracker_kind = None
        legacy.tracker_owner = None
        legacy.tracker_repo = None
        legacy.status_actor_login = None
        legacy.github_project_node_id = None
        # forge_kind and forge_base_url are intentionally NOT set;
        # they return MagicMock objects that str_attr() must reject in favour
        # of the 'github' and 'https://github.com' defaults.

        store = _make_store()
        store.list_all.return_value = [legacy]

        result = _exec_list_projects(store)
        # Must be valid JSON even for legacy project with missing forge attrs.
        data = json.loads(result)
        assert data["projects"][0]["forge_kind"] == "github"
