"""Security regressions for spawned-worker task handoffs."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.client_auth import ClientCredentials, agent_environment
from oompah.models import Issue, RunningEntry
from oompah.task_handoff import (
    TASK_HANDOFF_HEADER,
    TASK_HANDOFF_PROJECT_ENV,
    TASK_HANDOFF_TOKEN_ENV,
    TaskHandoffGrantStore,
)


class TestTaskHandoffGrantStore:
    def test_scope_expiry_and_revoke_do_not_store_bearer_token(self):
        now = [100.0]
        store = TaskHandoffGrantStore(now=lambda: now[0])
        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment", "set-status"},
            ttl_seconds=10,
        )

        assert token not in repr(store._grants)
        assert store.validate(
            token,
            project_id="proj-a",
            task_identifier="TASK-1",
            action="comment",
        ) == (True, "")
        assert store.validate(
            token,
            project_id="proj-b",
            task_identifier="TASK-1",
            action="comment",
        )[0] is False
        assert store.validate(
            token,
            project_id="proj-a",
            task_identifier="TASK-2",
            action="comment",
        )[0] is False
        assert store.validate(
            token,
            project_id="proj-a",
            task_identifier="TASK-1",
            action="view",
        )[0] is False

        now[0] = 111.0
        assert store.validate(
            token,
            project_id="proj-a",
            task_identifier="TASK-1",
            action="comment",
        )[0] is False

        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
        )
        store.revoke(token)
        assert store.validate(
            token,
            project_id="proj-a",
            task_identifier="TASK-1",
            action="comment",
        )[0] is False


class TestTaskCliHandoff:
    def test_capability_route_has_no_basic_auth_and_uses_project_scope(
        self, monkeypatch
    ):
        token = "opaque-task-capability"
        monkeypatch.setenv(TASK_HANDOFF_TOKEN_ENV, token)
        monkeypatch.setenv(TASK_HANDOFF_PROJECT_ENV, "proj-a")

        response = MagicMock()
        response.is_success = True
        response.status_code = 200
        response.json.return_value = {"ok": True}
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.post.return_value = response

        from oompah import task_cli

        with (
            patch("httpx.Client", return_value=client) as client_factory,
            patch.object(
                task_cli,
                "_session_auth",
                ClientCredentials("operator", "reusable-secret"),
            ),
        ):
            result = task_cli._task_handoff_request(
                "http://server",
                "comment",
                {"identifier": "TASK-1", "message": "done"},
            )

        assert result == {"ok": True}
        kwargs = client_factory.call_args.kwargs
        assert kwargs["auth"] is None
        assert kwargs["headers"] == {TASK_HANDOFF_HEADER: token}
        request_data = client.post.call_args.kwargs["json"]
        assert request_data["project_id"] == "proj-a"
        assert request_data["identifier"] == "TASK-1"
        assert request_data["action"] == "comment"
        assert "reusable-secret" not in repr(client_factory.call_args)

    def test_spawned_cli_does_not_resolve_inherited_operator_credentials(
        self, monkeypatch
    ):
        from oompah import task_cli

        monkeypatch.setenv(TASK_HANDOFF_TOKEN_ENV, "opaque")
        monkeypatch.setenv(TASK_HANDOFF_PROJECT_ENV, "proj-a")
        with (
            patch.object(task_cli, "resolve_client_credentials") as resolve,
            patch.object(task_cli, "_cmd_comment") as command,
        ):
            task_cli.main(
                [
                    "comment",
                    "TASK-1",
                    "--message",
                    "handoff",
                ]
            )
        resolve.assert_not_called()
        command.assert_called_once()


class TestTaskScopeDirectPath:
    def test_direct_acp_command_allows_only_assigned_task_and_actions(self):
        from oompah.acp_tools import _exec_oompah_task_command

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = SimpleNamespace(
            identifier="TASK-1",
            title="Task",
            description="body",
            state="In Progress",
            priority=2,
            labels=[],
        )

        assert (
            _exec_oompah_task_command(
                "oompah task comment TASK-1 --message 'progress' --author attacker",
                tracker,
                "proj-a",
                task_identifier="TASK-1",
            ).startswith("Error:")
        )
        assert (
            _exec_oompah_task_command(
                "oompah task comment TASK-1 --message 'progress' --author oompah",
                tracker,
                "proj-a",
                task_identifier="TASK-1",
            )
            == "Comment posted."
        )
        assert (
            _exec_oompah_task_command(
                "oompah task set-status TASK-1 Done --summary 'Completed'",
                tracker,
                "proj-a",
                task_identifier="TASK-1",
            )
            == "Status set to: Done"
        )
        assert (
            _exec_oompah_task_command(
                "oompah task view TASK-2",
                tracker,
                "proj-a",
                task_identifier="TASK-1",
            ).startswith("Error:")
        )
        assert (
            _exec_oompah_task_command(
                "oompah task create --title 'escape' --description 'x'",
                tracker,
                "proj-a",
                task_identifier="TASK-1",
            ).startswith("Error:")
        )
        tracker.add_comment.assert_any_call(
            "TASK-1", "progress", author="oompah"
        )
        assert tracker.add_comment.call_count == 2
        tracker.update_issue.assert_called_once_with("TASK-1", status="Done")

    def test_api_session_routes_handoff_without_http_self_call(self):
        from oompah.api_agent import _execute_tool

        tracker = MagicMock()
        result = _execute_tool(
            Path("."),
            "run_command",
            {
                "command": (
                    "oompah task comment TASK-1 --message 'api progress' "
                    "--author oompah"
                )
            },
            task_tracker=tracker,
            project_id="proj-a",
            task_identifier="TASK-1",
        )
        assert result == "Comment posted."
        tracker.add_comment.assert_called_once_with(
            "TASK-1", "api progress", author="oompah"
        )


class TestTaskHandoffEndpoint:
    def test_authenticated_worker_can_comment_and_transition_own_task(self):
        from fastapi.testclient import TestClient

        import oompah.server as server
        from oompah.server import app
        from oompah.task_handoff import issue_task_handoff_token

        issue = Issue(
            id="issue-1",
            identifier="TASK-1",
            title="Task",
            description="body",
            state="In Progress",
            project_id="proj-a",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        orch = MagicMock()
        orch._tracker_for_project.return_value = tracker
        orch.project_store.get.return_value = None
        token = issue_task_handoff_token(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment", "set-status"},
        )
        old_orch = server._orchestrator
        old_creds = server._http_credentials
        old_broadcast = server.broadcast_issues
        server._orchestrator = orch
        server._http_credentials = None
        server.broadcast_issues = AsyncMock()
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                headers = {TASK_HANDOFF_HEADER: token}
                comment = client.post(
                    "/api/v1/task-handoff",
                    headers=headers,
                    json={
                        "action": "comment",
                        "project_id": "proj-a",
                        "identifier": "TASK-1",
                        "message": "handoff complete",
                    },
                )
                status = client.post(
                    "/api/v1/task-handoff",
                    headers=headers,
                    json={
                        "action": "set-status",
                        "project_id": "proj-a",
                        "identifier": "TASK-1",
                        "status": "Done",
                    },
                )
                cross_scope = client.post(
                    "/api/v1/task-handoff",
                    headers=headers,
                    json={
                        "action": "comment",
                        "project_id": "proj-other",
                        "identifier": "TASK-1",
                        "message": "escape",
                    },
                )
        finally:
            server._orchestrator = old_orch
            server._http_credentials = old_creds
            server.broadcast_issues = old_broadcast

        assert comment.status_code == 200
        assert status.status_code == 200
        assert cross_scope.status_code == 403
        tracker.add_comment.assert_any_call(
            "TASK-1", "handoff complete", author="oompah"
        )
        tracker.update_issue.assert_called_once_with("TASK-1", status="Done")

    def test_capability_header_cannot_bypass_basic_auth_on_general_api(self):
        from fastapi.testclient import TestClient

        import oompah.server as server
        from oompah.http_auth import HtpasswdCredentials, VerificationError
        from oompah.server import app
        from oompah.task_handoff import issue_task_handoff_token

        creds = HtpasswdCredentials(enabled=True)

        def verifier(username, password):
            raise VerificationError("invalid")

        creds.verifier = verifier
        old_creds = server._http_credentials
        server._http_credentials = creds
        token = issue_task_handoff_token(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
        )
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get(
                    "/api/v1/state",
                    headers={TASK_HANDOFF_HEADER: token},
                )
        finally:
            server._http_credentials = old_creds
        assert response.status_code == 401


class TestAgentCredentialBoundary:
    def test_agent_environment_removes_reusable_service_credentials(self):
        env = agent_environment(
            {
                "OOMPAH_SERVER_USERNAME": "operator",
                "OOMPAH_SERVER_PASSWORD": "reusable-secret",
                "OOMPAH_SERVER_PASSWORD_FILE": "/secret",
                TASK_HANDOFF_TOKEN_ENV: "opaque",
                TASK_HANDOFF_PROJECT_ENV: "proj-a",
            }
        )
        assert "OOMPAH_SERVER_USERNAME" not in env
        assert "OOMPAH_SERVER_PASSWORD" not in env
        assert "OOMPAH_SERVER_PASSWORD_FILE" not in env
        assert env[TASK_HANDOFF_TOKEN_ENV] == "opaque"
        assert env[TASK_HANDOFF_PROJECT_ENV] == "proj-a"
        assert "reusable-secret" not in repr(env)

    def test_codex_subscription_session_forwards_only_scoped_handoff_env(
        self, monkeypatch
    ):
        from oompah.acp_backends import AcpBackendOptions
        from oompah.acp_backends.codex import CodexAcpBackendSession

        captured: dict[str, object] = {}

        class FakeThread:
            async def run_streamed(self, prompt, turn_options=None):
                async def events():
                    if False:
                        yield None

                return SimpleNamespace(events=events())

        class FakeCodex:
            def __init__(self, *, env):
                captured["env"] = env

            def start_thread(self, options=None):
                return FakeThread()

        class FakeThreadOptions:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        class FakeTurnOptions:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        session = CodexAcpBackendSession(
            AcpBackendOptions(
                workspace_path=".",
                prompt="handoff",
                billing_model="subscription",
                project_id="proj-a",
                task_handoff_token="opaque",
                env={"OOMPAH_SERVER_PASSWORD": "reusable-secret"},
            )
        )
        monkeypatch.setattr(
            session,
            "_import_codex_cli",
            lambda: (FakeCodex, FakeThreadOptions, FakeTurnOptions),
        )

        async def run():
            async for _event in session.run_turn():
                pass

        asyncio.run(run())
        child_env = captured["env"]
        assert child_env[TASK_HANDOFF_TOKEN_ENV] == "opaque"
        assert child_env[TASK_HANDOFF_PROJECT_ENV] == "proj-a"
        assert "OOMPAH_SERVER_PASSWORD" not in child_env
        assert "reusable-secret" not in repr(child_env)


class TestFailedHandoffLifecycle:
    def test_failed_handoff_is_held_for_human_without_retry(self, tmp_path):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator
        from oompah.task_handoff import (
            issue_task_handoff_token,
            record_task_handoff_failure,
        )

        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )
        issue = Issue(
            id="issue-1",
            identifier="TASK-1",
            title="Task",
            description="body",
            state="In Progress",
            project_id=None,
        )
        token = issue_task_handoff_token(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
        )
        record_task_handoff_failure(token, "task handoff operation failed")
        entry = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
            task_handoff_token=token,
        )
        orch.state.running[issue.id] = entry
        orch.tracker = MagicMock()

        asyncio.run(orch._on_worker_exit(issue.id, "normal", None))

        assert issue.id in orch.state.completed
        assert issue.id not in orch.state.running
        orch.tracker.mark_needs_human.assert_called_once()
        assert "handoff" in orch.tracker.mark_needs_human.call_args.args[1].lower()
        assert not orch.state.retry_attempts

    @pytest.mark.parametrize(
        "error",
        [
            "oompah task returned HTTP 401 Unauthorized",
            "ERROR (401): Authentication required for oompah task handoff",
        ],
    )
    def test_reported_auth_failure_is_not_silently_redispatched(
        self, tmp_path, error
    ):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        orch = Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )
        issue = Issue(
            id="issue-1",
            identifier="TASK-1",
            title="Task",
            description="body",
            state="In Progress",
        )
        orch.state.running[issue.id] = RunningEntry(
            worker_task=None,
            identifier=issue.identifier,
            issue=issue,
            session=None,
            retry_attempt=0,
            started_at=datetime.now(timezone.utc),
        )
        orch.tracker = MagicMock()

        asyncio.run(orch._on_worker_exit(issue.id, "abnormal", error))

        assert issue.id in orch.state.completed
        assert not orch.state.retry_attempts
