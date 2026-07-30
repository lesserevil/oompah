"""Worker submission staging API and CLI tests."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from oompah import server as server_module
from oompah import task_cli
from oompah.integration import IntegrationRecord
from oompah.integration_queue import IntegrationQueueStore
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


def test_submit_endpoint_accepts_the_assigned_task_worktree_and_enqueues_it(
    tmp_path,
):
    issue = _issue()
    issue.parent_id = "EPIC-1"
    issue.integration = IntegrationRecord(
        state="working",
        task_branch=issue.work_branch,
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store.list_all.return_value = []
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite"))
    orch.config.parallel_epic_children_enabled = True
    orch.integration_queue = queue
    calls: list[str] = []
    tracker.set_metadata_field.side_effect = lambda *args, **kwargs: calls.append(
        "metadata"
    )
    tracker.update_issue.side_effect = lambda *args, **kwargs: calls.append("status")

    try:
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

        queued = queue.items(project_id="proj-1", epic_id="EPIC-1")
        assert len(queued) == 1
        assert queued[0].task_branch == issue.work_branch
        assert queued[0].head_sha == "a" * 40
    finally:
        queue.close()

    assert response.status_code == 201
    assert response.json()["state"] == "Ready to Integrate"
    assert calls[:2] == ["metadata", "status"]
    metadata = tracker.set_metadata_field.call_args.args[2]
    assert metadata["state"] == "ready"
    assert metadata["head_sha"] == "a" * 40
    tracker.update_issue.assert_called_once_with(
        "TASK-2", status="Ready to Integrate"
    )


def test_submit_endpoint_rejects_wrong_checkout_without_mutating_queue(tmp_path):
    issue = _issue()
    issue.parent_id = "EPIC-1"
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.config.parallel_epic_children_enabled = True
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite"))
    orch.integration_queue = queue
    queue.enqueue(
        project_id="proj-1",
        epic_id="EPIC-1",
        task_id="TASK-2",
        task_branch=issue.work_branch or "",
        head_sha="a" * 40,
    )

    try:
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            response = client.post(
                "/api/v1/issues/TASK-2/submit",
                json={
                    "project_id": "proj-1",
                    "task_branch": "main",
                    "head_sha": "b" * 40,
                    "remote_head_sha": "b" * 40,
                    "worktree_clean": True,
                    "summary": "Submitted from the service checkout",
                },
            )

        assert response.status_code == 400
        assert "expected work branch" in response.json()["error"]["message"]
        queued = queue.items(project_id="proj-1", epic_id="EPIC-1")
        assert len(queued) == 1
        assert queued[0].task_branch == issue.work_branch
        assert queued[0].head_sha == "a" * 40
    finally:
        queue.close()

    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()


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
        "submitted branch 'oompah/task/TASK-OTHER' does not match the task's "
        "expected work branch 'oompah/task/TASK-2'; submit from the assigned "
        "task checkout"
    )
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()
    orch.integration_queue.enqueue.assert_not_called()
