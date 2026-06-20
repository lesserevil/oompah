"""Tests for the non-HTTP project management MCP tools (TASK-464.8).

Covers:
- _exec_list_projects: returns JSON snapshots for all managed projects
- _exec_get_project: returns JSON project tracker fields
- _exec_update_project: delegates to ProjectStore.update() with allowed fields
- build_tool_catalog: includes list/current/by-id project tools
- AcpAgentSession: project_store / project_id flow through to AcpBackendOptions
- project tools degrade gracefully without a project_store

These tests verify that agents running inside oompah MCP have a non-HTTP
path to read and mutate ProjectStore tracker fields for managed projects.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from oompah.models import Issue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(
    project_id: str = "proj-test",
    name: str = "test-project",
    repo_url: str = "https://github.com/acme/test-project",
    tracker_kind: str | None = None,
    tracker_owner: str | None = None,
    tracker_repo: str | None = None,
    github_project_node_id: str | None = None,
    status_actor_login: str | None = None,
    status_label_authorized_logins: list[str] | None = None,
    intake_auto_promote: bool = True,
    paused: bool = False,
) -> MagicMock:
    """Build a mock Project with realistic field defaults."""
    p = MagicMock()
    p.id = project_id
    p.name = name
    p.repo_url = repo_url
    p.tracker_kind = tracker_kind
    p.tracker_owner = tracker_owner
    p.tracker_repo = tracker_repo
    p.github_project_node_id = github_project_node_id
    p.status_actor_login = status_actor_login
    p.status_label_authorized_logins = status_label_authorized_logins or []
    p.intake_auto_promote = intake_auto_promote
    p.paused = paused
    return p


def _make_store(project: MagicMock | None = None) -> MagicMock:
    store = MagicMock()
    store.get.return_value = project
    store.update.return_value = project
    store.list_all.return_value = [] if project is None else [project]
    return store


def _make_issue(identifier: str = "owner/repo#240") -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Test issue",
        description="Issue body",
        state="open",
        issue_type="task",
        priority=2,
        labels=["oompah:status:open"],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Tests for _exec_list_projects
# ---------------------------------------------------------------------------

class TestExecListProjects:
    """Unit tests for the _exec_list_projects helper."""

    def test_returns_json_with_all_managed_projects(self):
        from oompah.acp_tools import _exec_list_projects

        trickle = _make_project(
            project_id="proj-trickle",
            name="trickle",
            repo_url="https://github.com/NVIDIA-Omniverse/trickle",
            tracker_kind="github_issues",
            tracker_owner="NVIDIA-Omniverse",
            tracker_repo="trickle",
        )
        aethel = _make_project(
            project_id="proj-aethel",
            name="aethel",
            repo_url="https://github.com/example-org/aethel",
        )
        store = _make_store()
        store.list_all.return_value = [trickle, aethel]

        result = _exec_list_projects(store)
        data = json.loads(result)

        assert [p["id"] for p in data["projects"]] == ["proj-trickle", "proj-aethel"]
        assert data["projects"][0]["repo_url"] == (
            "https://github.com/NVIDIA-Omniverse/trickle"
        )
        assert data["projects"][0]["tracker_kind"] == "github_issues"
        store.list_all.assert_called_once_with()

    def test_returns_error_when_project_store_is_none(self):
        from oompah.acp_tools import _exec_list_projects

        result = _exec_list_projects(None)
        data = json.loads(result)
        assert "error" in data
        assert "project_store" in data["error"]


# ---------------------------------------------------------------------------
# Tests for _exec_get_project
# ---------------------------------------------------------------------------

class TestExecGetProject:
    """Unit tests for the _exec_get_project helper."""

    def test_returns_json_with_tracker_fields(self):
        from oompah.acp_tools import _exec_get_project

        project = _make_project(
            project_id="proj-abc",
            name="my-repo",
            tracker_kind="github_issues",
            tracker_owner="my-org",
            tracker_repo="my-repo",
            status_actor_login="status-actor",
            status_label_authorized_logins=["release-manager"],
        )
        store = _make_store(project)

        result = _exec_get_project(store, "proj-abc")
        data = json.loads(result)

        assert data["id"] == "proj-abc"
        assert data["name"] == "my-repo"
        assert data["repo_url"] == "https://github.com/acme/test-project"
        assert data["tracker_kind"] == "github_issues"
        assert data["tracker_owner"] == "my-org"
        assert data["tracker_repo"] == "my-repo"
        assert data["status_actor_login"] == "status-actor"
        assert data["status_label_authorized_logins"] == ["release-manager"]
        assert data["intake_auto_promote"] is True
        assert data["paused"] is False

    def test_returns_error_when_project_store_is_none(self):
        from oompah.acp_tools import _exec_get_project

        result = _exec_get_project(None, "proj-test")
        data = json.loads(result)
        assert "error" in data
        assert "project_store" in data["error"]

    def test_returns_error_when_project_id_is_none(self):
        from oompah.acp_tools import _exec_get_project

        store = _make_store()
        result = _exec_get_project(store, None)
        data = json.loads(result)
        assert "error" in data

    def test_returns_error_when_project_id_is_empty(self):
        from oompah.acp_tools import _exec_get_project

        store = _make_store()
        result = _exec_get_project(store, "")
        data = json.loads(result)
        assert "error" in data

    def test_returns_error_when_project_not_found(self):
        from oompah.acp_tools import _exec_get_project

        store = _make_store(project=None)
        result = _exec_get_project(store, "proj-missing")
        data = json.loads(result)
        assert "error" in data
        assert "proj-missing" in data["error"]

    def test_calls_store_get_with_project_id(self):
        from oompah.acp_tools import _exec_get_project

        project = _make_project()
        store = _make_store(project)
        _exec_get_project(store, "proj-xyz")
        store.get.assert_called_once_with("proj-xyz")

    def test_target_project_id_overrides_current_project_id(self):
        from oompah.acp_tools import _exec_get_project

        project = _make_project(project_id="proj-target")
        store = _make_store(project)

        result = _exec_get_project(store, "proj-current", "proj-target")
        data = json.loads(result)

        assert data["id"] == "proj-target"
        store.get.assert_called_once_with("proj-target")

    def test_returns_all_readable_fields(self):
        from oompah.acp_tools import _exec_get_project, _PROJECT_READABLE_FIELDS

        project = _make_project(
            project_id="proj-full",
            name="full-project",
            tracker_kind="github_issues",
            tracker_owner="acme",
            tracker_repo="tasks",
            github_project_node_id="PVT_123",
            intake_auto_promote=False,
            paused=True,
        )
        store = _make_store(project)
        result = _exec_get_project(store, "proj-full")
        data = json.loads(result)

        # All readable fields must be present in the output.
        for field in _PROJECT_READABLE_FIELDS:
            assert field in data, f"field {field!r} missing from get_project output"


# ---------------------------------------------------------------------------
# Tests for _exec_update_project
# ---------------------------------------------------------------------------

class TestExecUpdateProject:
    """Unit tests for the _exec_update_project helper."""

    def test_updates_tracker_kind(self):
        from oompah.acp_tools import _exec_update_project

        updated = _make_project(tracker_kind="github_issues")
        store = _make_store(updated)
        store.update.return_value = updated

        fields_json = json.dumps({"tracker_kind": "github_issues"})
        result = _exec_update_project(store, "proj-test", fields_json)
        data = json.loads(result)

        assert data["updated"] is True
        assert data["tracker_kind"] == "github_issues"
        store.update.assert_called_once_with("proj-test", tracker_kind="github_issues")

    def test_updates_multiple_tracker_fields(self):
        from oompah.acp_tools import _exec_update_project

        updated = _make_project(
            tracker_kind="github_issues",
            tracker_owner="my-org",
            tracker_repo="my-tasks",
        )
        store = _make_store(updated)
        store.update.return_value = updated

        fields = {
            "tracker_kind": "github_issues",
            "tracker_owner": "my-org",
            "tracker_repo": "my-tasks",
        }
        result = _exec_update_project(store, "proj-test", json.dumps(fields))
        data = json.loads(result)

        assert data["updated"] is True
        store.update.assert_called_once_with(
            "proj-test",
            tracker_kind="github_issues",
            tracker_owner="my-org",
            tracker_repo="my-tasks",
        )

    def test_target_project_id_overrides_current_project_id(self):
        from oompah.acp_tools import _exec_update_project

        updated = _make_project(project_id="proj-aethel", tracker_kind="github_issues")
        store = _make_store(updated)
        fields_json = json.dumps({"tracker_kind": "github_issues"})

        result = _exec_update_project(
            store,
            "proj-current",
            fields_json,
            "proj-aethel",
        )
        data = json.loads(result)

        assert data["id"] == "proj-aethel"
        store.update.assert_called_once_with(
            "proj-aethel",
            tracker_kind="github_issues",
        )

    def test_rejects_unknown_fields(self):
        from oompah.acp_tools import _exec_update_project

        store = _make_store()
        fields_json = json.dumps({"repo_path": "/danger/path"})
        result = _exec_update_project(store, "proj-test", fields_json)

        assert result.startswith("error:")
        assert "repo_path" in result
        # store.update must NOT have been called
        store.update.assert_not_called()

    def test_rejects_non_dict_json(self):
        from oompah.acp_tools import _exec_update_project

        store = _make_store()
        result = _exec_update_project(store, "proj-test", '"just a string"')

        assert result.startswith("error:")
        store.update.assert_not_called()

    def test_rejects_invalid_json(self):
        from oompah.acp_tools import _exec_update_project

        store = _make_store()
        result = _exec_update_project(store, "proj-test", "not-json{{")

        assert result.startswith("error:")
        store.update.assert_not_called()

    def test_returns_error_when_project_store_is_none(self):
        from oompah.acp_tools import _exec_update_project

        result = _exec_update_project(None, "proj-test", "{}")
        assert result.startswith("error:")

    def test_returns_error_when_project_id_is_none(self):
        from oompah.acp_tools import _exec_update_project

        store = _make_store()
        result = _exec_update_project(store, None, "{}")
        assert result.startswith("error:")

    def test_returns_error_when_project_not_found(self):
        from oompah.acp_tools import _exec_update_project

        store = _make_store()
        store.update.return_value = None  # project not found

        result = _exec_update_project(store, "proj-missing", '{"tracker_kind": null}')
        assert result.startswith("error:")
        assert "proj-missing" in result

    def test_propagates_project_store_error(self):
        from oompah.acp_tools import _exec_update_project

        store = _make_store()
        store.update.side_effect = ValueError("invalid tracker_kind value")

        result = _exec_update_project(
            store, "proj-test", '{"tracker_kind": "bogus"}'
        )
        assert result.startswith("error:")
        assert "invalid tracker_kind" in result

    def test_updates_paused_flag(self):
        from oompah.acp_tools import _exec_update_project

        updated = _make_project(paused=True)
        store = _make_store(updated)
        store.update.return_value = updated

        result = _exec_update_project(store, "proj-test", '{"paused": true}')
        data = json.loads(result)
        assert data["paused"] is True

    def test_updates_intake_auto_promote_flag(self):
        from oompah.acp_tools import _exec_update_project

        updated = _make_project(intake_auto_promote=False)
        store = _make_store(updated)
        store.update.return_value = updated

        result = _exec_update_project(
            store, "proj-test", '{"intake_auto_promote": false}'
        )
        data = json.loads(result)
        assert data["intake_auto_promote"] is False

    def test_allowed_fields_set_is_correct(self):
        from oompah.acp_tools import _PROJECT_UPDATABLE_FIELDS

        expected = {
            "tracker_kind",
            "tracker_owner",
            "tracker_repo",
            "github_project_node_id",
            "status_actor_login",
            "status_label_authorized_logins",
            "intake_auto_promote",
            "github_issue_intake_enabled",
            "paused",
        }
        assert _PROJECT_UPDATABLE_FIELDS == expected, (
            "UPDATABLE_FIELDS changed — update this test and agent instructions"
        )


# ---------------------------------------------------------------------------
# Tests for direct oompah task command routing
# ---------------------------------------------------------------------------

class TestExecOompahTaskCommand:
    """ACP run_command must not self-call the local HTTP task CLI."""

    def test_non_task_command_not_intercepted(self):
        from oompah.acp_tools import _exec_oompah_task_command

        tracker = MagicMock()

        assert _exec_oompah_task_command("echo hi", tracker, "proj") is None

    def test_comment_routes_directly_to_tracker(self):
        from oompah.acp_tools import _exec_oompah_task_command

        tracker = MagicMock()

        result = _exec_oompah_task_command(
            "oompah task comment owner/repo#240 --message 'Working on it' "
            "--author oompah",
            tracker,
            "proj",
        )

        assert result == "Comment posted."
        tracker.add_comment.assert_called_once_with(
            "owner/repo#240",
            "Working on it",
            author="oompah",
        )

    def test_set_status_with_summary_routes_directly_to_tracker(self):
        from oompah.acp_tools import _exec_oompah_task_command

        tracker = MagicMock()

        result = _exec_oompah_task_command(
            "oompah task set-status owner/repo#240 Done --summary 'Finished'",
            tracker,
            "proj",
        )

        assert result == "Status set to: Done"
        tracker.update_issue.assert_called_once_with("owner/repo#240", status="Done")
        tracker.add_comment.assert_called_once_with(
            "owner/repo#240",
            "Finished",
            author="oompah",
        )

    def test_view_formats_tracker_detail_without_http(self):
        from oompah.acp_tools import _exec_oompah_task_command

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = _make_issue()
        tracker.fetch_comments.return_value = [
            {"id": 1, "author": "oompah", "created_at": "now", "text": "hello"}
        ]

        result = _exec_oompah_task_command(
            "oompah task view owner/repo#240",
            tracker,
            "proj",
        )

        assert "Task owner/repo#240 - Test issue" in result
        assert "hello" in result
        tracker.fetch_issue_detail.assert_called_once_with("owner/repo#240")

    def test_compound_task_command_returns_error_instead_of_subprocess(self):
        from oompah.acp_tools import _exec_oompah_task_command

        tracker = MagicMock()

        result = _exec_oompah_task_command(
            "oompah task comment owner/repo#240 --message hi && echo done",
            tracker,
            "proj",
        )

        assert result.startswith("Error:")
        tracker.add_comment.assert_not_called()


# ---------------------------------------------------------------------------
# Tests for the Claude tool catalog (build_tool_catalog)
# ---------------------------------------------------------------------------

# These tests require the claude_agent_sdk — skip gracefully if absent.
try:
    import claude_agent_sdk
    _HAS_CLAUDE_SDK = True
except ImportError:
    _HAS_CLAUDE_SDK = False

_skip_no_sdk = pytest.mark.skipif(
    not _HAS_CLAUDE_SDK,
    reason="claude_agent_sdk not installed",
)


@_skip_no_sdk
class TestBuildToolCatalogProjectTools:
    """The Claude catalog must include current and targeted project tools."""

    def test_includes_project_tools(self, tmp_path):
        from oompah.acp_tools import build_tool_catalog

        store = _make_store(_make_project())
        cat = build_tool_catalog(
            str(tmp_path), project_store=store, project_id="proj-test"
        )
        names = [t.name for t in cat]
        assert "list_projects" in names
        assert "get_project" in names
        assert "get_project_by_id" in names
        assert "update_project" in names
        assert "update_project_by_id" in names

    def test_catalog_has_11_tools_with_project_store(self, tmp_path):
        from oompah.acp_tools import build_tool_catalog

        store = _make_store(_make_project())
        cat = build_tool_catalog(
            str(tmp_path), project_store=store, project_id="proj-test"
        )
        assert len(cat) == 11

    def test_catalog_has_11_tools_without_project_store(self, tmp_path):
        """Project tools are always included and degrade gracefully."""
        from oompah.acp_tools import build_tool_catalog

        cat = build_tool_catalog(str(tmp_path))
        names = [t.name for t in cat]
        assert "list_projects" in names
        assert "get_project" in names
        assert "get_project_by_id" in names
        assert "update_project" in names
        assert "update_project_by_id" in names
        assert len(cat) == 11

    def test_run_command_tool_uses_env_timeout(self, tmp_path, monkeypatch):
        """ACP run_command must not pin the old 60s timeout."""
        import asyncio
        from oompah.acp_tools import build_tool_catalog

        monkeypatch.setenv("OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS", "1")
        cat = build_tool_catalog(str(tmp_path))
        tool = next(t for t in cat if t.name == "run_command")

        result = asyncio.run(tool.handler({"command": "sleep 2"}))
        text = result["content"][0]["text"]

        assert "Error: command timed out after 1s" in text

    def test_run_command_tool_intercepts_oompah_task_comment(self, tmp_path):
        """ACP run_command routes task CLI commands directly through tracker."""
        import asyncio
        from oompah.acp_tools import build_tool_catalog

        tracker = MagicMock()
        cat = build_tool_catalog(
            str(tmp_path),
            project_id="proj-test",
            task_tracker=tracker,
        )
        tool = next(t for t in cat if t.name == "run_command")

        result = asyncio.run(
            tool.handler({
                "command": (
                    "oompah task comment owner/repo#240 --message 'Working' "
                    "--author oompah"
                )
            })
        )
        text = result["content"][0]["text"]

        assert text == "Comment posted."
        tracker.add_comment.assert_called_once_with(
            "owner/repo#240",
            "Working",
            author="oompah",
        )

    def test_list_projects_tool_returns_data_with_store(self, tmp_path):
        """list_projects returns managed project snapshots when wired up."""
        import asyncio
        from oompah.acp_tools import build_tool_catalog

        trickle = _make_project(
            project_id="proj-trickle",
            name="trickle",
            repo_url="https://github.com/NVIDIA-Omniverse/trickle",
        )
        store = _make_store()
        store.list_all.return_value = [trickle]
        cat = build_tool_catalog(
            str(tmp_path), project_store=store, project_id="proj-current"
        )
        tool = next(t for t in cat if t.name == "list_projects")

        result = asyncio.run(tool.handler({}))
        text = result["content"][0]["text"]
        data = json.loads(text)

        assert data["projects"][0]["id"] == "proj-trickle"
        assert data["projects"][0]["repo_url"] == (
            "https://github.com/NVIDIA-Omniverse/trickle"
        )
        store.list_all.assert_called_once_with()

    def test_get_project_tool_returns_error_without_store(self, tmp_path):
        """When project_store is None the get_project tool returns an
        error JSON string instead of raising."""
        import asyncio
        from oompah.acp_tools import build_tool_catalog

        cat = build_tool_catalog(str(tmp_path))
        tool = next(t for t in cat if t.name == "get_project")

        # SdkMcpTool exposes the wrapped async function via .handler.
        result = asyncio.run(tool.handler({}))
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert "error" in data

    def test_update_project_tool_returns_error_without_store(self, tmp_path):
        """When project_store is None the update_project tool returns an
        error string instead of raising."""
        import asyncio
        from oompah.acp_tools import build_tool_catalog

        cat = build_tool_catalog(str(tmp_path))
        tool = next(t for t in cat if t.name == "update_project")

        result = asyncio.run(tool.handler({"fields_json": '{"tracker_kind": "github_issues"}'}))
        text = result["content"][0]["text"]
        assert text.startswith("error:")

    def test_get_project_tool_returns_data_with_store(self, tmp_path):
        """get_project tool returns real project data when store is wired up."""
        import asyncio
        from oompah.acp_tools import build_tool_catalog

        project = _make_project(
            project_id="proj-wired",
            tracker_kind="github_issues",
            tracker_owner="test-org",
        )
        store = _make_store(project)
        cat = build_tool_catalog(
            str(tmp_path), project_store=store, project_id="proj-wired"
        )
        tool = next(t for t in cat if t.name == "get_project")

        result = asyncio.run(tool.handler({}))
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["id"] == "proj-wired"
        assert data["tracker_kind"] == "github_issues"
        assert data["tracker_owner"] == "test-org"

    def test_get_project_by_id_tool_targets_requested_project(self, tmp_path):
        """get_project_by_id reads the explicit target project."""
        import asyncio
        from oompah.acp_tools import build_tool_catalog

        target = _make_project(project_id="proj-target")
        store = _make_store(target)
        cat = build_tool_catalog(
            str(tmp_path), project_store=store, project_id="proj-current"
        )
        tool = next(t for t in cat if t.name == "get_project_by_id")

        result = asyncio.run(tool.handler({"project_id": "proj-target"}))
        text = result["content"][0]["text"]
        data = json.loads(text)

        assert data["id"] == "proj-target"
        store.get.assert_called_once_with("proj-target")

    def test_update_project_tool_delegates_to_store(self, tmp_path):
        """update_project tool calls project_store.update() with the
        parsed fields dict."""
        import asyncio
        from oompah.acp_tools import build_tool_catalog

        updated = _make_project(project_id="proj-upd", tracker_kind="github_issues")
        store = _make_store(updated)
        store.update.return_value = updated

        cat = build_tool_catalog(
            str(tmp_path), project_store=store, project_id="proj-upd"
        )
        tool = next(t for t in cat if t.name == "update_project")

        fields = {"tracker_kind": "github_issues"}
        asyncio.run(tool.handler({"fields_json": json.dumps(fields)}))

        store.update.assert_called_once_with("proj-upd", tracker_kind="github_issues")

    def test_update_project_by_id_tool_targets_requested_project(self, tmp_path):
        """update_project_by_id updates the explicit target project."""
        import asyncio
        from oompah.acp_tools import build_tool_catalog

        updated = _make_project(project_id="proj-target", tracker_kind="github_issues")
        store = _make_store(updated)
        store.update.return_value = updated

        cat = build_tool_catalog(
            str(tmp_path), project_store=store, project_id="proj-current"
        )
        tool = next(t for t in cat if t.name == "update_project_by_id")

        fields = {"tracker_kind": "github_issues"}
        asyncio.run(
            tool.handler(
                {"project_id": "proj-target", "fields_json": json.dumps(fields)}
            )
        )

        store.update.assert_called_once_with(
            "proj-target",
            tracker_kind="github_issues",
        )


# ---------------------------------------------------------------------------
# Tests for AcpAgentSession project_store flow-through
# ---------------------------------------------------------------------------

@_skip_no_sdk
class TestAcpAgentSessionProjectStoreFlow:
    """AcpAgentSession must accept project_store / project_id and flow
    them into AcpBackendOptions so Codex/OpenCode backends can use them."""

    def test_session_stores_project_store_and_id(self):
        from oompah.acp_agent import AcpAgentSession

        store = _make_store()
        tracker = MagicMock()
        session = AcpAgentSession(
            workspace_path="/tmp/ws",
            prompt="test",
            project_store=store,
            project_id="proj-test",
            task_tracker=tracker,
        )
        assert session.project_store is store
        assert session.project_id == "proj-test"
        assert session.task_tracker is tracker

    def test_session_defaults_project_store_to_none(self):
        from oompah.acp_agent import AcpAgentSession

        session = AcpAgentSession(workspace_path="/tmp/ws", prompt="test")
        assert session.project_store is None
        assert session.project_id is None
        assert session.task_tracker is None

    def test_run_task_passes_project_context_to_backend_options(self):
        """run_task must include project_store / project_id / tracker in the
        AcpBackendOptions passed to start_session."""
        import asyncio
        from unittest.mock import MagicMock

        from oompah.acp_agent import AcpAgentSession
        from oompah.acp_backends.base import AcpBackendOptions

        captured_options: list[AcpBackendOptions] = []

        mock_session = MagicMock()
        mock_session.status = "succeeded"
        mock_session.last_error = None
        mock_session.permission_denials = []

        async def _fake_run_turn():
            return
            yield  # make it a generator

        mock_session.run_turn = MagicMock(return_value=_fake_run_turn())

        mock_backend = MagicMock()
        def _start_session(opts):
            captured_options.append(opts)
            return mock_session

        mock_backend.start_session = _start_session

        store = _make_store()
        tracker = MagicMock()

        with patch("oompah.acp_agent.get_backend_or_raise", return_value=lambda: mock_backend):
            session = AcpAgentSession(
                workspace_path="/tmp/ws",
                prompt="hello",
                project_store=store,
                project_id="proj-flow",
                task_tracker=tracker,
            )
            asyncio.run(session.run_task())

        assert len(captured_options) == 1
        opts = captured_options[0]
        assert opts.project_store is store
        assert opts.project_id == "proj-flow"
        assert opts.task_tracker is tracker


# ---------------------------------------------------------------------------
# Tests for the Codex catalog (build_codex_tool_catalog)
# ---------------------------------------------------------------------------

try:
    import agents as _agents_sdk
    _HAS_CODEX_SDK = True
except ImportError:
    try:
        import openai_agents as _agents_sdk  # type: ignore
        _HAS_CODEX_SDK = True
    except ImportError:
        _HAS_CODEX_SDK = False

_skip_no_codex = pytest.mark.skipif(
    not _HAS_CODEX_SDK,
    reason="openai-agents SDK not installed",
)


@_skip_no_codex
class TestBuildCodexToolCatalogProjectTools:
    """The Codex catalog must include current and targeted project tools."""

    def test_includes_project_tools(self, tmp_path):
        from oompah.acp_tools import build_codex_tool_catalog

        store = _make_store(_make_project())
        cat = build_codex_tool_catalog(
            str(tmp_path), project_store=store, project_id="proj-test"
        )
        # Codex function_tools expose their name via .name or .__name__
        names = [
            getattr(t, "name", None) or getattr(t, "__name__", None) or str(t)
            for t in cat
        ]
        for expected in (
            "list_projects",
            "get_project",
            "get_project_by_id",
            "update_project",
            "update_project_by_id",
        ):
            assert any(expected in str(n) for n in names), (
                f"{expected} not found in Codex catalog names: {names}"
            )

    def test_catalog_has_11_tools(self, tmp_path):
        from oompah.acp_tools import build_codex_tool_catalog

        store = _make_store(_make_project())
        cat = build_codex_tool_catalog(
            str(tmp_path), project_store=store, project_id="proj-test"
        )
        assert len(cat) == 11
