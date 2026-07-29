"""Cross-surface terminal-status staging coverage (OOMPAH-476)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.models import Issue, Project
from oompah.server import app
from oompah.terminal_audit import TargetState
from oompah.terminal_transition_coordinator import (
    OverrideRejection,
    OverrideResult,
    TransitionResult,
)


class _Tracker:
    def __init__(self, issue: Issue) -> None:
        self.issue = issue
        self.status_updates: list[tuple[str, str]] = []
        self.comments: list[tuple[str, str]] = []

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issue if identifier == self.issue.identifier else None

    def update_issue(self, identifier: str, **fields: str) -> None:
        if "status" in fields:
            self.status_updates.append((identifier, fields["status"]))

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> None:
        self.comments.append((identifier, text))


class _Coordinator:
    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.overrides: list[dict] = []
        self.override_result: OverrideResult | None = None

    async def request_transition(self, **kwargs):
        self.requests.append(kwargs)
        return TransitionResult(
            success=True,
            audit_id="audit-request-1",
            queued_targets=[kwargs["requested_target"]],
        )

    async def override_transition(self, **kwargs):
        self.overrides.append(kwargs)
        if self.override_result is not None:
            return self.override_result
        return OverrideResult(
            success=True,
            override_id="audit-override-1",
            applied_status=kwargs["requested_target"].value,
        )


def _orchestrator(issue: Issue):
    tracker = _Tracker(issue)
    coordinator = _Coordinator()
    project = Project(
        id="proj-1",
        name="Project",
        repo_url="https://github.com/example/repo",
        repo_path=".",
        tracker_kind="oompah_md",
        tracker_owner="owner",
        tracker_repo="repo",
        status_label_authorized_logins=["owner"],
    )
    store = MagicMock()
    store.list_all.return_value = [project]
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store = store
    orch.terminal_transition_coordinator = coordinator
    orch.config.tracker_terminal_states = ["Done"]
    orch.state.running = {}
    orch.state.retry_attempts = {}
    orch.state.claimed = set()
    orch.state.completed = set()
    orch.request_refresh = MagicMock()
    return orch, tracker, coordinator


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def test_patch_terminal_status_stages_and_does_not_write_terminal(client):
    issue = Issue("task-1", "task-1", "Task", description="work", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-1",
            json={"project_id": "proj-1", "status": "closed"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "In Validation"
    assert response.json()["requested_target"] == "Done"
    assert response.json()["audit_id"] == "audit-request-1"
    assert tracker.status_updates == []
    assert coordinator.requests[0]["requested_target"] is TargetState.DONE


def test_patch_nonterminal_status_keeps_direct_behavior(client):
    issue = Issue("task-2", "task-2", "Task", description="work", state="Backlog")
    orch, tracker, _ = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-2",
            json={"project_id": "proj-1", "status": "open", "actor_login": "owner"},
        )

    assert response.status_code == 200
    assert tracker.status_updates == [("task-2", "open")]


def test_patch_owner_override_requires_reason_and_uses_coordinator(client):
    issue = Issue("task-3", "task-3", "Task", description="work", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        missing_reason = client.patch(
            "/api/v1/issues/task-3",
            json={
                "project_id": "proj-1",
                "status": "Done",
                "audit_override": True,
                "actor_login": "owner",
            },
        )
        applied = client.patch(
            "/api/v1/issues/task-3",
            json={
                "project_id": "proj-1",
                "status": "Done",
                "audit_override": True,
                "override_reason": "Emergency release approval",
                "actor_login": "owner",
            },
        )

    assert missing_reason.status_code == 400
    assert applied.status_code == 200
    assert applied.json()["status"] == "Done"
    assert applied.json()["audit_id"] == "audit-override-1"
    assert coordinator.overrides[0]["reason"] == "Emergency release approval"
    assert tracker.status_updates == []


def test_patch_owner_override_rejects_non_owner_without_metadata_details(client):
    issue = Issue("task-unauthorized", "task-unauthorized", "Task", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    coordinator.override_result = OverrideResult(
        success=False,
        error_code=OverrideRejection.UNAUTHORIZED_ACTOR,
    )
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.patch(
            "/api/v1/issues/task-unauthorized",
            json={
                "project_id": "proj-1",
                "status": "Done",
                "audit_override": True,
                "override_reason": "Emergency release approval",
                "actor_login": "not-owner",
            },
        )

    assert response.status_code == 403
    assert "owner" in response.json()["error"]["message"].lower()
    assert "metadata" not in response.text.lower()
    assert tracker.status_updates == []


def test_label_terminal_mutation_is_staged_without_override(client):
    issue = Issue("task-4", "task-4", "Task", description="work", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        response = client.post(
            "/api/v1/issues/task-4/labels",
            json={
                "project_id": "proj-1",
                "label": "oompah:status:archived",
            },
        )

    assert response.status_code == 201
    assert response.json()["requested_target"] == "Archived"
    assert response.json()["status"] == "In Validation"
    assert coordinator.requests[0]["requested_target"] is TargetState.ARCHIVED
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_acp_terminal_router_stages_and_supports_override():
    from oompah.acp_tools import _exec_oompah_task_command_async

    issue = Issue("task-5", "task-5", "Task", description="work", state="Open")
    tracker = _Tracker(issue)
    coordinator = _Coordinator()
    project_store = MagicMock()
    project_store.get.return_value = SimpleNamespace(
        id="proj-1", status_label_authorized_logins=["owner"], tracker_owner="owner"
    )

    staged = await _exec_oompah_task_command_async(
        "oompah task set-status task-5 Merged",
        tracker,
        "proj-1",
        project_store=project_store,
        terminal_transition_coordinator=coordinator,
    )
    overridden = await _exec_oompah_task_command_async(
        "oompah task set-status task-5 Archived --audit-override "
        "--override-reason 'retire task' --actor owner",
        tracker,
        "proj-1",
        project_store=project_store,
        terminal_transition_coordinator=coordinator,
    )

    assert "In Validation" in staged
    assert "audit-request-1" in staged
    assert "owner override" in overridden
    assert coordinator.requests[0]["requested_target"] is TargetState.MERGED
    assert coordinator.overrides[0]["requested_target"] is TargetState.ARCHIVED
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_acp_terminal_router_hides_tracker_error_details():
    from oompah.acp_tools import _exec_oompah_task_command_async

    class FailingCoordinator:
        async def request_transition(self, **kwargs):
            raise RuntimeError("terminal-audit metadata internals")

    issue = Issue("task-6", "task-6", "Task", description="work", state="Open")
    tracker = _Tracker(issue)
    result = await _exec_oompah_task_command_async(
        "oompah task set-status task-6 Done",
        tracker,
        "proj-1",
        project_store=MagicMock(),
        terminal_transition_coordinator=FailingCoordinator(),
    )

    assert result == "Error: terminal transition request failed"
    assert "metadata" not in result.lower()
    assert tracker.status_updates == []


@pytest.mark.asyncio
async def test_acp_terminal_router_hides_tracker_fetch_errors():
    from oompah.acp_tools import _exec_oompah_task_command_async

    class FailingTracker:
        def fetch_issue_detail(self, identifier):
            raise RuntimeError("terminal-audit metadata internals")

    result = await _exec_oompah_task_command_async(
        "oompah task set-status task-7 Done",
        FailingTracker(),
        "proj-1",
        terminal_transition_coordinator=MagicMock(),
    )

    assert result == "Error: terminal transition request failed"
    assert "metadata" not in result.lower()


def test_task_handoff_terminal_label_rejects_override_fields(client):
    from oompah.task_handoff import issue_task_handoff_token

    issue = Issue("task-label-override", "task-label-override", "Task", state="Open")
    orch, tracker, coordinator = _orchestrator(issue)
    token = issue_task_handoff_token(
        project_id="proj-1",
        task_identifier="task-label-override",
        allowed_actions={"add-label"},
    )
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        # TestClient cannot set the private ASGI scope capability directly;
        # exercise the same validation helper through the handoff route's
        # authorization middleware header.
        response = client.post(
            "/api/v1/task-handoff",
            headers={"x-oompah-task-capability": token},
            json={
                "action": "add-label",
                "project_id": "proj-1",
                "identifier": "task-label-override",
                "label": "oompah:status:done",
                "audit_override": True,
                "override_reason": "not supported on labels",
            },
        )

    assert response.status_code == 400
    assert "override" in response.json()["error"]["message"].lower()
    assert coordinator.overrides == []
    assert tracker.status_updates == []
