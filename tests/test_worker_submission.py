"""Worker submission staging API and CLI tests."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from oompah import server as server_module
from oompah import task_cli
from oompah.models import Issue
from oompah.server import app


def _issue() -> Issue:
    return Issue(
        id="TASK-2",
        identifier="TASK-2",
        title="Submitted task",
        state="In Progress",
        project_id="proj-1",
        work_branch="oompah/task/TASK-2",
        target_branch="main",
    )


def test_submit_cli_sends_git_evidence_and_summary():
    args = MagicMock(
        identifier="TASK-2",
        project="proj-1",
        summary="Implemented and tested",
    )
    with (
        patch.object(
            task_cli,
            "_git_submission_evidence",
            return_value={
                "task_branch": "oompah/task/TASK-2",
                "head_sha": "a" * 40,
                "remote_head_sha": "a" * 40,
                "worktree_clean": True,
            },
        ),
        patch.object(task_cli, "_http", return_value={"ok": True}) as request,
    ):
        task_cli._cmd_submit("http://server", args)

    assert request.call_args.args[:2] == (
        "POST",
        "http://server/api/v1/issues/TASK-2/submit",
    )
    assert request.call_args.kwargs["data"]["head_sha"] == "a" * 40
    assert request.call_args.kwargs["data"]["summary"] == "Implemented and tested"


def test_submit_endpoint_persists_evidence_before_ready_state():
    issue = _issue()
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store.list_all.return_value = []
    calls: list[str] = []
    tracker.set_metadata_field.side_effect = lambda *args, **kwargs: calls.append(
        "metadata"
    )
    tracker.update_issue.side_effect = lambda *args, **kwargs: calls.append("status")

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.post(
            "/api/v1/issues/TASK-2/submit",
            json={
                "project_id": "proj-1",
                "task_branch": "oompah/task/TASK-2",
                "head_sha": "a" * 40,
                "remote_head_sha": "a" * 40,
                "worktree_clean": True,
                "summary": "Done",
            },
        )

    assert response.status_code == 201
    assert response.json()["state"] == "Ready to Integrate"
    assert calls[:2] == ["metadata", "status"]
    metadata = tracker.set_metadata_field.call_args.args[2]
    assert metadata["state"] == "ready"
    assert metadata["head_sha"] == "a" * 40
    tracker.update_issue.assert_called_once_with(
        "TASK-2", status="Ready to Integrate"
    )


def test_submit_endpoint_rejects_invalid_git_object_id_without_writing():
    issue = _issue()
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.post(
            "/api/v1/issues/TASK-2/submit",
            json={"project_id": "proj-1", "head_sha": "not-a-sha"},
        )

    assert response.status_code == 400
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()


def test_submit_endpoint_rejects_foreign_task_branch_without_writing():
    issue = _issue()
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        response = client.post(
            "/api/v1/issues/TASK-2/submit",
            json={
                "project_id": "proj-1",
                "task_branch": "oompah/task/TASK-OTHER",
                "head_sha": "a" * 40,
                "remote_head_sha": "a" * 40,
                "worktree_clean": True,
                "summary": "Wrong worktree",
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == (
        "task_branch does not match the task's canonical work branch"
    )
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()
    orch.integration_queue.enqueue.assert_not_called()
