"""Security regressions for spawned-worker task handoffs."""

from __future__ import annotations

import asyncio
import time
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

    def test_spawned_cli_reports_terminal_audit_response(self, monkeypatch, capsys):
        from oompah import task_cli

        monkeypatch.setenv(TASK_HANDOFF_TOKEN_ENV, "opaque")
        monkeypatch.setenv(TASK_HANDOFF_PROJECT_ENV, "proj-a")
        response = {
            "ok": True,
            "status": "In Validation",
            "requested_target": "Done",
            "audit_id": "audit-cli-handoff",
        }
        with patch.object(task_cli, "_task_handoff_request", return_value=response) as request:
            args = task_cli.build_parser().parse_args(
                [
                    "set-status",
                    "TASK-1",
                    "Done",
                    "--actor",
                    "owner",
                    "--audit-override",
                    "--override-reason",
                    "Approved",
                ]
            )
            task_cli._cmd_set_status("http://server", args)

        assert "Terminal transition queued: Done" in capsys.readouterr().out
        request.assert_called_once()
        assert request.call_args.args[1] == "set-status"
        assert request.call_args.args[2]["status"] == "Done"
        assert request.call_args.args[2]["actor_login"] == "owner"
        assert request.call_args.args[2]["audit_override"] is True
        assert request.call_args.args[2]["override_reason"] == "Approved"

    def test_spawned_comment_includes_required_scope_fields(self):
        """The handoff endpoint requires the exact task identifier."""
        from oompah import task_cli

        args = task_cli.build_parser().parse_args(
            [
                "comment",
                "TASK-1",
                "--project",
                "proj-a",
                "--message",
                "handoff",
            ]
        )
        with patch.object(
            task_cli, "_task_handoff_request", return_value={"ok": True}
        ) as request:
            task_cli._cmd_comment("http://server", args)

        request.assert_called_once()
        assert request.call_args.args[1] == "comment"
        payload = request.call_args.args[2]
        assert payload["identifier"] == "TASK-1"
        assert payload["project_id"] == "proj-a"

    def test_spawned_add_label_includes_required_scope_fields(self):
        """Scoped label changes must be bound to their assigned task."""
        from oompah import task_cli

        args = task_cli.build_parser().parse_args(
            ["add-label", "TASK-1", "needs:devops", "--project", "proj-a"]
        )
        with patch.object(
            task_cli, "_task_handoff_request", return_value={"ok": True}
        ) as request:
            task_cli._cmd_add_label("http://server", args)

        request.assert_called_once()
        assert request.call_args.args[1] == "add-label"
        payload = request.call_args.args[2]
        assert payload["identifier"] == "TASK-1"
        assert payload["project_id"] == "proj-a"


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
        terminal_result = _exec_oompah_task_command(
            "oompah task set-status TASK-1 Done --summary 'Completed'",
            tracker,
            "proj-a",
            task_identifier="TASK-1",
        )
        assert terminal_result.startswith("Error:")
        assert "oompah task submit" in terminal_result
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
        assert tracker.add_comment.call_count == 1
        tracker.update_issue.assert_not_called()

    def test_direct_acp_submit_requires_and_persists_pushed_git_evidence(
        self,
        tmp_path,
    ):
        from oompah.acp_tools import _exec_oompah_task_command

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Task",
            work_branch="epic-TASK-0--task-TASK-1",
        )
        coordination = MagicMock()
        with patch(
            "oompah.task_cli._git_submission_evidence",
            return_value={
                "task_branch": "epic-TASK-0--task-TASK-1",
                "head_sha": "a" * 40,
                "remote_head_sha": "a" * 40,
                "worktree_clean": True,
                "base_sha": "b" * 40,
                "changed_paths": ["oompah/example.py"],
            },
        ):
            result = _exec_oompah_task_command(
                "oompah task submit TASK-1 --summary 'Completed and tested'",
                tracker,
                "proj-a",
                task_identifier="TASK-1",
                coordination_service=coordination,
                workspace_path=tmp_path,
            )

        assert result == "Submitted for integration: TASK-1"
        record = tracker.set_metadata_field.call_args.args[2]
        assert record["task_branch"] == "epic-TASK-0--task-TASK-1"
        assert record["head_sha"] == "a" * 40
        tracker.update_issue.assert_called_once_with(
            "TASK-1",
            status="Ready to Integrate",
        )
        coordination.coordination_checkpoint.assert_called_once()

    def test_direct_acp_submit_rejects_evidence_from_the_wrong_checkout(
        self,
        tmp_path,
    ):
        from oompah.acp_tools import _exec_oompah_task_command

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Task",
            work_branch="epic-TASK-0--task-TASK-1",
        )
        with patch(
            "oompah.task_cli._git_submission_evidence",
            return_value={
                "task_branch": "main",
                "head_sha": "a" * 40,
                "remote_head_sha": "a" * 40,
                "worktree_clean": True,
            },
        ):
            result = _exec_oompah_task_command(
                "oompah task submit TASK-1 --summary 'Completed and tested'",
                tracker,
                "proj-a",
                task_identifier="TASK-1",
                workspace_path=tmp_path,
            )

        assert result.startswith("Error: submitted branch 'main'")
        tracker.set_metadata_field.assert_not_called()
        tracker.update_issue.assert_not_called()

    def test_direct_acp_submission_survives_coordination_outage(
        self,
        tmp_path,
    ):
        from oompah.acp_tools import _exec_oompah_task_command

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = Issue(
            id="TASK-1",
            identifier="TASK-1",
            title="Task",
            work_branch="epic-TASK-0--task-TASK-1",
        )
        coordination = MagicMock()
        coordination.coordination_checkpoint.side_effect = RuntimeError(
            "coordination database temporarily unavailable"
        )
        with patch(
            "oompah.task_cli._git_submission_evidence",
            return_value={
                "task_branch": "epic-TASK-0--task-TASK-1",
                "head_sha": "a" * 40,
                "remote_head_sha": "a" * 40,
                "worktree_clean": True,
                "base_sha": "b" * 40,
                "changed_paths": ["oompah/example.py"],
            },
        ):
            result = _exec_oompah_task_command(
                "oompah task submit TASK-1 --summary 'Completed and tested'",
                tracker,
                "proj-a",
                task_identifier="TASK-1",
                coordination_service=coordination,
                workspace_path=tmp_path,
            )

        assert result == "Submitted for integration: TASK-1"
        tracker.update_issue.assert_called_once_with(
            "TASK-1",
            status="Ready to Integrate",
        )

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
    def test_api_submission_marks_queue_enqueue_as_explicit_retry(self):
        from oompah.server import _enqueue_worker_submission

        orch = MagicMock()
        orch.config.parallel_epic_children_enabled = True
        issue = SimpleNamespace(
            identifier="TASK-1",
            parent_id="EPIC-1",
            priority=1,
        )
        record = SimpleNamespace(
            state="ready",
            task_branch="epic-EPIC-1--task-TASK-1",
            head_sha="a" * 40,
            base_sha="b" * 40,
            submitted_at="2026-07-30T00:00:00+00:00",
        )

        _enqueue_worker_submission(orch, "proj-a", issue, record)

        assert (
            orch.integration_queue.enqueue.call_args.kwargs["explicit_retry"]
            is True
        )
        assert (
            orch.integration_queue.enqueue.call_args.kwargs["rearm_integrated"]
            is True
        )

    def test_api_submission_does_not_rearm_without_fresh_ready_record(self):
        from oompah.server import _enqueue_worker_submission

        orch = MagicMock()
        orch.config.parallel_epic_children_enabled = True
        issue = SimpleNamespace(
            identifier="TASK-1",
            parent_id="EPIC-1",
            priority=1,
        )
        record = SimpleNamespace(
            state="integrated",
            task_branch="epic-EPIC-1--task-TASK-1",
            head_sha="a" * 40,
            base_sha="b" * 40,
            submitted_at="2026-07-30T00:00:00+00:00",
        )

        _enqueue_worker_submission(orch, "proj-a", issue, record)

        assert (
            orch.integration_queue.enqueue.call_args.kwargs["rearm_integrated"]
            is False
        )

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
        from oompah.terminal_audit import TargetState
        from oompah.terminal_transition_coordinator import TransitionResult

        orch.terminal_transition_coordinator.request_transition = AsyncMock(
            return_value=TransitionResult(
                success=True,
                audit_id="audit-handoff-1",
                queued_targets=[TargetState.DONE],
                status_staged=True,
            )
        )
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
                        "summary": "Completed and tested",
                        "task_branch": "oompah/task/TASK-1",
                        "head_sha": "a" * 40,
                        "remote_head_sha": "a" * 40,
                        "worktree_clean": True,
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
        assert status.json()["status"] == "In Validation"
        assert status.json()["requested_target"] == "Done"
        assert status.json()["audit_id"] == "audit-handoff-1"
        tracker.update_issue.assert_not_called()

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


class TestHandoffTokenFailClosed:
    """OOMPAH-575 regression: missing, invalid, and cross-scope tokens must
    fail closed.  The handoff endpoint must never grant access when the
    capability is absent, bogus, or scoped to a different task/project.

    These tests complement TestTaskHandoffEndpoint by explicitly covering
    the failure modes asserted in the acceptance criteria:
    - missing/expired tokens return 401
    - unrelated tasks remain unauthorized (403)
    - server-wide credentials are never usable via the handoff path
    """

    def _make_server_context(self, server_module):
        """Return (old_orch, old_creds, orch) and set up the module globals."""
        from unittest.mock import MagicMock

        orch = MagicMock()
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = Issue(
            id="issue-1",
            identifier="TASK-1",
            title="Task",
            description="body",
            state="In Progress",
            project_id="proj-a",
        )
        orch._tracker_for_project.return_value = tracker
        orch.project_store.get.return_value = None
        return orch, tracker

    def test_missing_capability_header_returns_401(self):
        """POST to /api/v1/task-handoff with no capability header must return
        401 with a clear 'required' error message."""
        from fastapi.testclient import TestClient

        import oompah.server as server
        from oompah.server import app

        orch, _tracker = self._make_server_context(server)
        old_orch = server._orchestrator
        old_creds = server._http_credentials
        server._orchestrator = orch
        server._http_credentials = None
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/api/v1/task-handoff",
                    json={
                        "action": "view",
                        "project_id": "proj-a",
                        "identifier": "TASK-1",
                    },
                )
        finally:
            server._orchestrator = old_orch
            server._http_credentials = old_creds

        assert response.status_code == 401
        body = response.json()
        msg = body.get("error", {}).get("message", "")
        assert "capability required" in msg or "missing" in msg.lower()

    def test_invalid_token_returns_401(self):
        """An unrecognized (never-issued) token string must be rejected 401.
        Responses must not reveal whether a valid grant exists for another
        task/project at the same digest."""
        from fastapi.testclient import TestClient

        import oompah.server as server
        from oompah.server import app

        orch, _tracker = self._make_server_context(server)
        old_orch = server._orchestrator
        old_creds = server._http_credentials
        server._orchestrator = orch
        server._http_credentials = None
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/api/v1/task-handoff",
                    headers={TASK_HANDOFF_HEADER: "never-issued-garbage-token"},
                    json={
                        "action": "view",
                        "project_id": "proj-a",
                        "identifier": "TASK-1",
                    },
                )
        finally:
            server._orchestrator = old_orch
            server._http_credentials = old_creds

        assert response.status_code == 401
        body = response.json()
        msg = body.get("error", {}).get("message", "")
        # The response must say "invalid or expired" (no information about
        # whether a grant for another task/project exists)
        assert "invalid" in msg.lower() or "expired" in msg.lower()
        # The garbage token must not appear verbatim in the response
        assert "never-issued-garbage-token" not in response.text

    def test_wrong_project_scope_returns_403(self):
        """A valid token scoped to proj-a must be rejected when used against
        proj-other — even for the same task identifier."""
        from fastapi.testclient import TestClient

        import oompah.server as server
        from oompah.server import app
        from oompah.task_handoff import issue_task_handoff_token

        token = issue_task_handoff_token(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"view", "comment"},
        )

        orch, _tracker = self._make_server_context(server)
        old_orch = server._orchestrator
        old_creds = server._http_credentials
        server._orchestrator = orch
        server._http_credentials = None
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/api/v1/task-handoff",
                    headers={TASK_HANDOFF_HEADER: token},
                    json={
                        "action": "view",
                        "project_id": "proj-other",
                        "identifier": "TASK-1",
                    },
                )
        finally:
            server._orchestrator = old_orch
            server._http_credentials = old_creds

        assert response.status_code == 403
        body = response.json()
        msg = body.get("error", {}).get("message", "")
        assert "another project" in msg

    def test_wrong_task_scope_returns_403(self):
        """A valid token scoped to TASK-1 must be rejected when the request
        body targets TASK-99 in the same project."""
        from fastapi.testclient import TestClient

        import oompah.server as server
        from oompah.server import app
        from oompah.task_handoff import issue_task_handoff_token

        token = issue_task_handoff_token(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"view", "comment"},
        )

        orch, _tracker = self._make_server_context(server)
        old_orch = server._orchestrator
        old_creds = server._http_credentials
        server._orchestrator = orch
        server._http_credentials = None
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/api/v1/task-handoff",
                    headers={TASK_HANDOFF_HEADER: token},
                    json={
                        "action": "view",
                        "project_id": "proj-a",
                        "identifier": "TASK-99",
                    },
                )
        finally:
            server._orchestrator = old_orch
            server._http_credentials = old_creds

        assert response.status_code == 403
        body = response.json()
        msg = body.get("error", {}).get("message", "")
        assert "another task" in msg

    def test_ungranted_action_returns_403(self):
        """A token that was issued without 'create' in its allowed_actions
        must return 403 when the request asks for 'create'-equivalent actions.
        Only the exact set of granted operations is accepted."""
        from fastapi.testclient import TestClient

        import oompah.server as server
        from oompah.server import app
        from oompah.task_handoff import issue_task_handoff_token

        # Issue a token without the "add-label" action
        token = issue_task_handoff_token(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"view", "comment"},
        )

        orch, _tracker = self._make_server_context(server)
        old_orch = server._orchestrator
        old_creds = server._http_credentials
        server._orchestrator = orch
        server._http_credentials = None
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.post(
                    "/api/v1/task-handoff",
                    headers={TASK_HANDOFF_HEADER: token},
                    json={
                        "action": "add-label",
                        "project_id": "proj-a",
                        "identifier": "TASK-1",
                        "label": "needs:attention",
                    },
                )
        finally:
            server._orchestrator = old_orch
            server._http_credentials = old_creds

        # 403 because action not in granted set
        assert response.status_code == 403

    def test_codex_assigned_session_can_view_and_comment_its_task(self):
        """Integration path: a Codex-session CLI env with a valid scoped token
        can call the view and comment operations for its own task.

        This test exercises the full capability chain:
        1. Orchestrator mints a scoped token (simulated via issue_task_handoff_token)
        2. Token ends up in the Codex subprocess env (verified by
           TestCodexHandoffAuth.test_cli_session_injects_task_handoff_token_and_project_id)
        3. task_cli routes via the token, hitting /api/v1/task-handoff
        4. Server validates the token scope and executes the operation
        """
        from fastapi.testclient import TestClient

        import oompah.server as server
        from oompah.server import app
        from oompah.task_handoff import issue_task_handoff_token

        issue = Issue(
            id="issue-codex-1",
            identifier="OOMPAH-479",
            title="Repair session",
            description="Repair body",
            state="In Progress",
            project_id="proj-a",
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = issue
        tracker.fetch_comments.return_value = []
        orch = MagicMock()
        orch._tracker_for_project.return_value = tracker
        orch.project_store.get.return_value = None

        # Simulate what the orchestrator issues for a Codex repair session
        token = issue_task_handoff_token(
            project_id="proj-a",
            task_identifier="OOMPAH-479",
            allowed_actions={"view", "comment", "submit", "set-status"},
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

                # Assigned agent can VIEW its own task (no 401)
                view_resp = client.post(
                    "/api/v1/task-handoff",
                    headers=headers,
                    json={
                        "action": "view",
                        "project_id": "proj-a",
                        "identifier": "OOMPAH-479",
                    },
                )
                # Assigned agent can COMMENT on its own task
                comment_resp = client.post(
                    "/api/v1/task-handoff",
                    headers=headers,
                    json={
                        "action": "comment",
                        "project_id": "proj-a",
                        "identifier": "OOMPAH-479",
                        "message": "Implementation complete",
                        "author": "oompah",
                    },
                )
                # Cross-task access MUST be unauthorized
                cross_task_resp = client.post(
                    "/api/v1/task-handoff",
                    headers=headers,
                    json={
                        "action": "view",
                        "project_id": "proj-a",
                        "identifier": "OOMPAH-999",
                    },
                )
                # Cross-project access MUST be unauthorized
                cross_proj_resp = client.post(
                    "/api/v1/task-handoff",
                    headers=headers,
                    json={
                        "action": "comment",
                        "project_id": "proj-other",
                        "identifier": "OOMPAH-479",
                        "message": "escape",
                    },
                )
        finally:
            server._orchestrator = old_orch
            server._http_credentials = old_creds
            server.broadcast_issues = old_broadcast

        # View and comment succeed
        assert view_resp.status_code == 200, f"view failed: {view_resp.text}"
        assert comment_resp.status_code == 200, f"comment failed: {comment_resp.text}"
        view_detail = view_resp.json().get("detail", {})
        assert view_detail.get("identifier") == "OOMPAH-479"

        # Cross-scope requests are rejected
        assert cross_task_resp.status_code == 403, (
            f"cross-task should be 403, got {cross_task_resp.status_code}"
        )
        assert cross_proj_resp.status_code == 403, (
            f"cross-project should be 403, got {cross_proj_resp.status_code}"
        )


class TestOrchestratorHandoffTokenMint:
    """OOMPAH-593 live-path reproducer: verify Orchestrator._issue_task_handoff_token
    mints a capability whose scope and action set are exactly what a
    service-launched Codex worker needs to complete its own task CLI workflow.

    If any of these tests fail, the live path returns 401/403 for a real worker
    against its own assigned task — the failure mode explicitly called out in
    the OOMPAH-593 acceptance criteria ("If the live path still returns 401,
    fix the actual launch/environment propagation gap with tests before
    resubmission.").  The rest of the handoff pipeline (env injection,
    endpoint validation) is covered by TestCodexHandoffAuth and
    TestHandoffTokenFailClosed; this suite closes the remaining gap between
    those two by exercising the orchestrator's mint step directly.
    """

    # Actions the task CLI ever dispatches through /api/v1/task-handoff.
    # Keep in sync with oompah/task_cli.py and oompah/server.py.
    _CLI_DISPATCHED_ACTIONS = frozenset(
        {
            "view",
            "comment",
            "set-status",
            "submit",
            "add-label",
            "remove-label",
            "coordination-peers",
            "coordination-inbox",
            "coordination-send",
            "coordination-checkpoint",
        }
    )

    def _make_orch(self, tmp_path):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        return Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            state_path=str(tmp_path / "state.json"),
        )

    def test_orchestrator_mints_scoped_token_for_valid_issue(self, tmp_path):
        """The orchestrator's mint returns a non-empty token that is
        scoped to the exact issue.identifier and issue.project_id.  This is
        the smoke test for the live-path — if this returns None the worker
        would launch without any tracker credential and fail closed on its
        first CLI call."""
        from oompah.task_handoff import validate_task_handoff_token

        orch = self._make_orch(tmp_path)
        issue = Issue(
            id="issue-live-1",
            identifier="OOMPAH-999",
            title="Live probe",
            description="body",
            state="In Progress",
            project_id="proj-live",
        )

        token = orch._issue_task_handoff_token(issue)

        assert token, "orchestrator must mint a non-empty capability for scoped issues"
        allowed, reason = validate_task_handoff_token(
            token,
            project_id="proj-live",
            task_identifier="OOMPAH-999",
            action="view",
        )
        assert allowed, f"minted token should validate for its own scope: {reason}"

    def test_orchestrator_mint_returns_none_when_issue_has_no_project(
        self, tmp_path
    ):
        """When issue.project_id is None the orchestrator must fail closed at
        mint time.  Returning a token here would grant an unscoped capability
        because task_handoff.issue() requires project_id."""
        orch = self._make_orch(tmp_path)
        issue = Issue(
            id="issue-unscoped",
            identifier="ORPHAN-1",
            title="No project",
            description="body",
            state="In Progress",
            project_id=None,
        )

        token = orch._issue_task_handoff_token(issue)

        assert token is None

    def test_orchestrator_grants_every_action_the_cli_dispatches(self, tmp_path):
        """Drift guard: every action the task CLI can dispatch must be in the
        orchestrator's granted set.  If someone widens the CLI without
        updating the mint, a live worker gets 403 when it tries the missing
        action.  This is the "live path still returns 401/403" scenario
        called out in the OOMPAH-593 acceptance criteria."""
        from oompah.task_handoff import validate_task_handoff_token

        orch = self._make_orch(tmp_path)
        issue = Issue(
            id="issue-drift",
            identifier="OOMPAH-1000",
            title="Drift probe",
            description="body",
            state="In Progress",
            project_id="proj-drift",
        )

        token = orch._issue_task_handoff_token(issue)
        assert token

        missing_actions = []
        for action in self._CLI_DISPATCHED_ACTIONS:
            allowed, _reason = validate_task_handoff_token(
                token,
                project_id="proj-drift",
                task_identifier="OOMPAH-1000",
                action=action,
            )
            if not allowed:
                missing_actions.append(action)

        assert not missing_actions, (
            f"orchestrator mint is missing CLI-dispatched actions: "
            f"{sorted(missing_actions)} — a live worker will get 403 when it "
            f"invokes any of these operations. Add them to "
            f"Orchestrator._issue_task_handoff_token.allowed_actions."
        )

    def test_orchestrator_token_denies_actions_outside_grant_set(self, tmp_path):
        """Least-privilege guard: the minted token must NOT grant actions the
        orchestrator did not explicitly list.  A future action the CLI hasn't
        opted into (e.g. "delete", "archive") must fail closed unless it is
        also added to the grant set."""
        from oompah.task_handoff import validate_task_handoff_token

        orch = self._make_orch(tmp_path)
        issue = Issue(
            id="issue-least-priv",
            identifier="OOMPAH-1001",
            title="Least priv probe",
            description="body",
            state="In Progress",
            project_id="proj-lp",
        )

        token = orch._issue_task_handoff_token(issue)
        assert token

        # These actions are not in the CLI dispatch set and must be refused.
        for action in ("delete", "archive", "reassign", "close", "admin"):
            allowed, _reason = validate_task_handoff_token(
                token,
                project_id="proj-lp",
                task_identifier="OOMPAH-1001",
                action=action,
            )
            assert not allowed, (
                f"orchestrator minted a token that grants '{action}' — this "
                f"widens least-privilege. Remove it from allowed_actions."
            )

    def test_orchestrator_token_denies_cross_task_and_cross_project_access(
        self, tmp_path
    ):
        """A token minted for issue A/project P must not authorise operations
        on a different task or a different project.  This is the live-path
        equivalent of TestHandoffTokenFailClosed.test_wrong_task_scope_returns_403
        and test_wrong_project_scope_returns_403 — verified through the actual
        orchestrator mint rather than a hand-built issue_task_handoff_token
        call, so drift in the orchestrator's scope arguments is caught here."""
        from oompah.task_handoff import validate_task_handoff_token

        orch = self._make_orch(tmp_path)
        issue = Issue(
            id="issue-scope-a",
            identifier="OOMPAH-2001",
            title="Scope-A",
            description="body",
            state="In Progress",
            project_id="proj-a",
        )

        token = orch._issue_task_handoff_token(issue)
        assert token

        # Same project, different task — must be denied
        wrong_task_ok, _reason = validate_task_handoff_token(
            token,
            project_id="proj-a",
            task_identifier="OOMPAH-9999",
            action="view",
        )
        assert not wrong_task_ok

        # Different project, same task identifier — must be denied
        wrong_proj_ok, _reason = validate_task_handoff_token(
            token,
            project_id="proj-other",
            task_identifier="OOMPAH-2001",
            action="view",
        )
        assert not wrong_proj_ok

    def test_orchestrator_mint_survives_issue_task_handoff_token_exception(
        self, monkeypatch, tmp_path
    ):
        """If the underlying task_handoff module raises (e.g. the grant store
        is unavailable), the orchestrator must return None rather than raising
        — a dispatch failure is preferable to letting the worker launch
        without a scoped capability and then falling back to operator creds."""
        orch = self._make_orch(tmp_path)
        issue = Issue(
            id="issue-broken",
            identifier="OOMPAH-3001",
            title="Broken grant store",
            description="body",
            state="In Progress",
            project_id="proj-broken",
        )

        def _boom(**_kwargs):
            raise RuntimeError("grant store unavailable")

        import oompah.orchestrator as orch_mod

        monkeypatch.setattr(orch_mod, "issue_task_handoff_token", _boom)

        token = orch._issue_task_handoff_token(issue)

        assert token is None


class TestOOMPAH650WorkerLifetimeCredentials:
    """OOMPAH-650: Keep scoped task handoff credentials valid for the full
    worker lifetime.

    These regressions cover the four properties spelled out in the acceptance
    criteria:

    * A worker outliving the wall-clock TTL can still view/comment/submit
      because the server-side lease renewed the grant while the worker was
      inside a long tool call.
    * The endpoint refresh and lease heartbeat preserve the ORIGINAL TTL a
      grant was minted with; a deliberately short capability is never
      silently widened to the module default.
    * Ownership is generation-bound: a stale worker cannot renew after a
      replacement dispatch or forced termination has taken over the entry.
    * The task-handoff endpoint aborts the tracker mutation and returns an
      explicit ``handoff_expired`` / ``handoff_revoked`` diagnostic when the
      grant is no longer usable, so the CLI can distinguish auth transport
      failure from task failure.
    """

    def test_endpoint_refresh_preserves_original_short_ttl(self):
        """A grant minted with a 60 s TTL must never be widened to 24 h.

        Refresh (either via the endpoint after a validated request or via
        the lease heartbeat) uses the grant's own ``original_ttl_seconds``
        when the caller does not supply an explicit override.
        """
        now = [1000.0]
        store = TaskHandoffGrantStore(now=lambda: now[0])
        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
            ttl_seconds=60.0,
        )

        assert store.refresh(token) is True
        grant = store._grants[store._digest(token)]
        # Refreshed at t=1000 with original TTL 60 → expires at 1060, not 24h out.
        assert grant.expires_at == pytest.approx(1060.0)
        assert grant.original_ttl_seconds == pytest.approx(60.0)

    def test_refresh_never_widens_grant_beyond_original_ttl(self):
        """Even an explicit oversize ttl_seconds is clamped to the grant's
        minted TTL. This preserves any deliberate operator bound."""
        now = [1000.0]
        store = TaskHandoffGrantStore(now=lambda: now[0])
        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
            ttl_seconds=60.0,
        )
        assert store.refresh(token, ttl_seconds=24 * 60 * 60) is True
        grant = store._grants[store._digest(token)]
        # Clamped to original 60 s TTL, not extended to the requested 24 h.
        assert grant.expires_at <= 1060.0

    def test_lease_heartbeat_preserves_original_short_ttl(self):
        """The heartbeat thread renews with the grant's original TTL, so the
        capability is not silently widened while the worker is idle."""
        now = [1000.0]
        store = TaskHandoffGrantStore(now=lambda: now[0])
        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
            ttl_seconds=60.0,
            owner_id="worker-A",
        )
        lease = store.start_lease(
            token,
            owner_id="worker-A",
            heartbeat_interval_seconds=0.005,
        )
        assert lease is not None
        try:
            # Wait for at least one heartbeat to fire.
            deadline = time.monotonic() + 1.0
            baseline = store._grants[store._digest(token)].expires_at
            while time.monotonic() < deadline:
                grant = store._grants.get(store._digest(token))
                if grant is not None and grant.expires_at != baseline:
                    break
                time.sleep(0.005)
            grant = store._grants[store._digest(token)]
            # Heartbeat renewed with ORIGINAL 60 s TTL, not the 24 h default.
            assert grant.expires_at <= 1060.0
            assert grant.expires_at > baseline - 0.001  # actually renewed
            assert grant.original_ttl_seconds == pytest.approx(60.0)
        finally:
            lease.stop()

    def test_worker_survives_beyond_initial_ttl_via_endpoint_refresh(self):
        """A worker whose bearer token is older than its wall-clock TTL still
        completes its tracker mutation, because the endpoint refreshes the
        grant on every request and preserves the original TTL.

        This is the core acceptance case: no 401 solely because the initial
        TTL aged out during a legitimate long-running tool call.
        """
        from fastapi.testclient import TestClient

        import oompah.server as server
        import oompah.task_handoff as task_handoff_module
        from oompah.server import app
        from oompah.task_handoff import TaskHandoffGrantStore

        now = [1000.0]
        store = TaskHandoffGrantStore(now=lambda: now[0])
        old_store = task_handoff_module._default_store
        task_handoff_module._default_store = store
        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
            ttl_seconds=60.0,
        )

        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = Issue(
            id="issue-1",
            identifier="TASK-1",
            title="Task",
            description="body",
            state="In Progress",
            project_id="proj-a",
        )
        tracker.fetch_comments.return_value = []
        tracker.add_comment.return_value = None
        orch = MagicMock()
        orch._tracker_for_project.return_value = tracker
        orch.project_store.get.return_value = None

        old_orch = server._orchestrator
        old_creds = server._http_credentials
        old_broadcast = server.broadcast_issues
        server._orchestrator = orch
        server._http_credentials = None
        server.broadcast_issues = AsyncMock()
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                # First request at t=1030 (halfway through TTL): succeeds and
                # bumps expires_at to 1090.
                now[0] = 1030.0
                r1 = client.post(
                    "/api/v1/task-handoff",
                    headers={TASK_HANDOFF_HEADER: token},
                    json={
                        "action": "comment",
                        "project_id": "proj-a",
                        "identifier": "TASK-1",
                        "message": "midpoint update",
                    },
                )
                assert r1.status_code == 200, r1.text
                # The original TTL was 60 s; a widening bug would place
                # expires_at at ~1030 + 24h. Preservation keeps it near 1090.
                grant = store._grants[store._digest(token)]
                assert grant.expires_at <= 1090.0 + 1.0

                # Now advance PAST the ORIGINAL TTL (t=1080 > 1060) but stay
                # within the refreshed window (< 1090). The endpoint must
                # still accept and mutate — this is the OOMPAH-650 case.
                now[0] = 1080.0
                r2 = client.post(
                    "/api/v1/task-handoff",
                    headers={TASK_HANDOFF_HEADER: token},
                    json={
                        "action": "comment",
                        "project_id": "proj-a",
                        "identifier": "TASK-1",
                        "message": "past-initial-ttl update",
                    },
                )
                assert r2.status_code == 200, r2.text
                assert tracker.add_comment.call_count >= 2
        finally:
            task_handoff_module._default_store = old_store
            server._orchestrator = old_orch
            server._http_credentials = old_creds
            server.broadcast_issues = old_broadcast

    def test_endpoint_returns_handoff_expired_when_grant_ages_out(self):
        """When a grant has expired without ever being renewed, the endpoint
        returns 401 with error code ``handoff_expired`` so the CLI can
        distinguish auth transport failure from task failure."""
        from fastapi.testclient import TestClient

        import oompah.server as server
        import oompah.task_handoff as task_handoff_module
        from oompah.server import app
        from oompah.task_handoff import TaskHandoffGrantStore

        now = [1000.0]
        store = TaskHandoffGrantStore(now=lambda: now[0])
        old_store = task_handoff_module._default_store
        task_handoff_module._default_store = store
        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
            ttl_seconds=1.0,
        )

        old_creds = server._http_credentials
        server._http_credentials = None
        try:
            now[0] = 1010.0  # well past expiry
            with TestClient(app, raise_server_exceptions=False) as client:
                r = client.post(
                    "/api/v1/task-handoff",
                    headers={TASK_HANDOFF_HEADER: token},
                    json={
                        "action": "comment",
                        "project_id": "proj-a",
                        "identifier": "TASK-1",
                        "message": "should be rejected",
                    },
                )
        finally:
            task_handoff_module._default_store = old_store
            server._http_credentials = old_creds

        assert r.status_code == 401
        body = r.json()
        assert body["error"]["code"] == "handoff_expired"
        assert "expired" in body["error"]["message"].lower()

    def test_endpoint_returns_handoff_revoked_after_explicit_revocation(self):
        """After the orchestrator explicitly revokes a token (worker
        termination), the endpoint returns 401 ``handoff_revoked`` so the
        client understands the failure was ownership loss, not transport."""
        from fastapi.testclient import TestClient

        import oompah.server as server
        import oompah.task_handoff as task_handoff_module
        from oompah.server import app
        from oompah.task_handoff import TaskHandoffGrantStore

        store = TaskHandoffGrantStore()
        old_store = task_handoff_module._default_store
        task_handoff_module._default_store = store
        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
            ttl_seconds=60.0,
        )
        store.revoke(token)

        old_creds = server._http_credentials
        server._http_credentials = None
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                r = client.post(
                    "/api/v1/task-handoff",
                    headers={TASK_HANDOFF_HEADER: token},
                    json={
                        "action": "comment",
                        "project_id": "proj-a",
                        "identifier": "TASK-1",
                        "message": "should be rejected after revocation",
                    },
                )
        finally:
            task_handoff_module._default_store = old_store
            server._http_credentials = old_creds

        assert r.status_code == 401
        body = r.json()
        assert body["error"]["code"] == "handoff_revoked"
        assert "revoked" in body["error"]["message"].lower()

    def test_endpoint_aborts_mutation_when_refresh_races_with_termination(self):
        """Between validate and mutate the endpoint refreshes the grant; if
        that refresh fails (owner lost the race with forced termination) the
        endpoint MUST NOT call the tracker."""
        from fastapi.testclient import TestClient

        import oompah.server as server
        import oompah.task_handoff as task_handoff_module
        from oompah.server import app
        from oompah.task_handoff import TaskHandoffGrantStore

        store = TaskHandoffGrantStore()
        old_store = task_handoff_module._default_store
        task_handoff_module._default_store = store
        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
            ttl_seconds=60.0,
        )
        tracker = MagicMock()
        tracker.fetch_issue_detail.return_value = Issue(
            id="issue-1",
            identifier="TASK-1",
            title="Task",
            description="body",
            state="In Progress",
            project_id="proj-a",
        )
        tracker.fetch_comments.return_value = []
        tracker.add_comment.return_value = None
        orch = MagicMock()
        orch._tracker_for_project.return_value = tracker
        orch.project_store.get.return_value = None

        old_orch = server._orchestrator
        old_creds = server._http_credentials
        old_broadcast = server.broadcast_issues
        server._orchestrator = orch
        server._http_credentials = None
        server.broadcast_issues = AsyncMock()
        try:
            with (
                patch.object(
                    server, "refresh_task_handoff_token", return_value=False
                ),
                TestClient(app, raise_server_exceptions=False) as client,
            ):
                r = client.post(
                    "/api/v1/task-handoff",
                    headers={TASK_HANDOFF_HEADER: token},
                    json={
                        "action": "comment",
                        "project_id": "proj-a",
                        "identifier": "TASK-1",
                        "message": "must not be committed",
                    },
                )
        finally:
            task_handoff_module._default_store = old_store
            server._orchestrator = old_orch
            server._http_credentials = old_creds
            server.broadcast_issues = old_broadcast

        assert r.status_code == 401
        body = r.json()
        assert body["error"]["code"] in {"handoff_revoked", "handoff_expired"}
        # The mutation must not have reached the tracker.
        tracker.add_comment.assert_not_called()

    def test_owner_mismatch_denies_lease_and_refresh(self):
        """A grant bound to worker A cannot be renewed by worker B, either
        via ``refresh(owner_id=...)`` or by starting a second lease."""
        store = TaskHandoffGrantStore()
        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
            ttl_seconds=60,
            owner_id="worker-A",
        )
        # Wrong owner in refresh path is rejected.
        assert store.refresh(token, owner_id="worker-B") is False
        # Wrong owner cannot start a lease either.
        assert store.start_lease(token, owner_id="worker-B") is None
        # The right owner still works.
        assert store.refresh(token, owner_id="worker-A") is True

    def test_lease_revokes_when_owner_generation_changes(self):
        """When the running-entry generation changes underneath a live lease
        (dispatch replaced the entry), the lease's ``owner_is_live`` check
        must trip and the token must be revoked automatically."""
        store = TaskHandoffGrantStore()
        token = store.issue(
            project_id="proj-a",
            task_identifier="TASK-1",
            allowed_actions={"comment"},
            ttl_seconds=60,
            owner_id="dispatch-gen-1",
        )
        current_generation = ["dispatch-gen-1"]

        def _owner_is_live() -> bool:
            return current_generation[0] == "dispatch-gen-1"

        lease = store.start_lease(
            token,
            owner_id="dispatch-gen-1",
            heartbeat_interval_seconds=0.005,
            owner_is_live=_owner_is_live,
        )
        assert lease is not None
        try:
            current_generation[0] = "dispatch-gen-2"  # Replacement happened.
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                grant = store._grants.get(store._digest(token))
                if grant is not None and grant.revoked_at is not None:
                    break
                time.sleep(0.005)
            grant = store._grants[store._digest(token)]
            assert grant.revoked_at is not None
        finally:
            lease.stop()

    def test_forced_termination_revokes_even_when_entry_replaced(self):
        """Fix for the ``_terminate_running`` early-return race: if a
        replacement RunningEntry has already been inserted for the same
        issue_id, forced termination must still revoke the OLD entry's
        token so a surviving subprocess cannot reuse its bearer credential
        during the window before the daemon heartbeat notices."""
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator
        from oompah.task_handoff import (
            issue_task_handoff_token,
            validate_task_handoff_token,
        )

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            orch = Orchestrator(
                config=ServiceConfig(),
                workflow_path="WORKFLOW.md",
                state_path=str(Path(tmp) / "state.json"),
            )
            issue = Issue(
                id="issue-1",
                identifier="TASK-1",
                title="Task",
                state="In Progress",
                project_id="proj-a",
            )

            old_token = issue_task_handoff_token(
                project_id="proj-a",
                task_identifier="TASK-1",
                allowed_actions={"comment"},
                ttl_seconds=60,
            )
            new_token = issue_task_handoff_token(
                project_id="proj-a",
                task_identifier="TASK-1",
                allowed_actions={"comment"},
                ttl_seconds=60,
            )
            old_entry = RunningEntry(
                worker_task=None,
                identifier=issue.identifier,
                issue=issue,
                session=None,
                retry_attempt=0,
                started_at=datetime.now(timezone.utc),
                task_handoff_token=old_token,
            )
            replacement_entry = RunningEntry(
                worker_task=None,
                identifier=issue.identifier,
                issue=issue,
                session=None,
                retry_attempt=1,
                started_at=datetime.now(timezone.utc),
                task_handoff_token=new_token,
            )
            # Seed the terminator with the OLD entry, then swap in the
            # replacement before the terminate loop reaches the pop.
            orch.state.running[issue.id] = old_entry

            async def _swap_and_terminate():
                terminate_task = asyncio.create_task(
                    orch._terminate_running(issue.id, False)
                )
                # Give the terminate loop a moment to capture ``entry``.
                await asyncio.sleep(0)
                # Simulate the replacement entering the runtime map before
                # the terminator's early-return check.
                orch.state.running[issue.id] = replacement_entry
                return await terminate_task

            assert asyncio.run(_swap_and_terminate()) is True

            # OLD token: revoked (or already outright removed after grace).
            valid_old, reason_old = validate_task_handoff_token(
                old_token,
                project_id="proj-a",
                task_identifier="TASK-1",
                action="comment",
            )
            assert valid_old is False
            assert (
                "revoked" in reason_old.lower()
                or "invalid" in reason_old.lower()
            )
            # NEW token belonging to the replacement must remain usable.
            valid_new, _ = validate_task_handoff_token(
                new_token,
                project_id="proj-a",
                task_identifier="TASK-1",
                action="comment",
            )
            assert valid_new is True
            # And the replacement entry is still present.
            assert orch.state.running.get(issue.id) is replacement_entry
            # Clean up the replacement grant.
            from oompah.task_handoff import revoke_task_handoff_token
            revoke_task_handoff_token(new_token)

    def test_no_basic_auth_environment_leaks_into_worker(self):
        """Worker environments must never receive reusable operator Basic
        credentials, only the task-scoped handoff token."""
        env = agent_environment(
            base_env={
                "PATH": "/usr/bin",
                "OOMPAH_SERVER_USERNAME": "operator",
                "OOMPAH_SERVER_PASSWORD": "secret",
                "OOMPAH_SERVER_PASSWORD_FILE": "/tmp/pw",
                TASK_HANDOFF_TOKEN_ENV: "scoped-token",
                TASK_HANDOFF_PROJECT_ENV: "proj-a",
            },
        )
        # Only the scoped capability may reach the worker environment.
        assert env.get(TASK_HANDOFF_TOKEN_ENV) == "scoped-token"
        assert env.get(TASK_HANDOFF_PROJECT_ENV) == "proj-a"
        # None of the reusable operator credentials survive.
        assert "OOMPAH_SERVER_USERNAME" not in env
        assert "OOMPAH_SERVER_PASSWORD" not in env
        assert "OOMPAH_SERVER_PASSWORD_FILE" not in env
