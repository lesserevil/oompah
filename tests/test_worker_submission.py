"""Worker submission staging API and CLI tests."""

import asyncio
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
    orch._cancel_retry_for_issue.assert_called_once_with(
        issue_id="TASK-2",
        identifier="TASK-2",
        project_id="proj-1",
        reason="task submitted for integration",
    )
    tracker.update_issue.assert_called_once_with(
        "TASK-2", status="Ready to Integrate"
    )


def test_direct_epic_rebase_submission_skips_child_queue_and_stages_audit(tmp_path):
    issue = Issue(
        id="EXOCOMP-244",
        identifier="EXOCOMP-244",
        title="Rebase epic-EXOCOMP-135 onto main",
        state="Needs Rebase",
        project_id="proj-1",
        parent_id="EXOCOMP-135",
        work_branch="epic-EXOCOMP-135",
        integration=IntegrationRecord(
            state="working",
            task_branch="epic-EXOCOMP-135",
            base_branch="epic-EXOCOMP-135",
            base_sha="1" * 40,
        ),
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    integrated = IntegrationRecord(
        state="integrated",
        task_branch="epic-EXOCOMP-135",
        base_branch="epic-EXOCOMP-135",
        base_sha="1" * 40,
        head_sha="2" * 40,
        integrated_sha="2" * 40,
    )
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store.list_all.return_value = []
    orch.config.parallel_epic_children_enabled = True
    orch.complete_direct_epic_maintenance_submission = AsyncMock(
        return_value=(True, "published epic head reconciled", integrated)
    )
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite"))
    orch.integration_queue = queue

    try:
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            response = client.post(
                "/api/v1/issues/EXOCOMP-244/submit",
                json={
                    "project_id": "proj-1",
                    "task_branch": "epic-EXOCOMP-135",
                    "head_sha": "2" * 40,
                    "remote_head_sha": "2" * 40,
                    "worktree_clean": True,
                    "summary": "Rebased and force-pushed the epic",
                },
            )

        assert response.status_code == 201, response.text
        assert response.json()["state"] == "In Validation"
        assert response.json()["integration"]["integrated_sha"] == "2" * 40
        orch.complete_direct_epic_maintenance_submission.assert_awaited_once()
        assert queue.items(project_id="proj-1", epic_id="EXOCOMP-135") == []
    finally:
        queue.close()


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


def test_same_head_ready_submit_backfills_missing_work_branch_projection(tmp_path):
    existing = IntegrationRecord(
        state="ready",
        task_branch="OOMPAH-814",
        base_branch="epic-OOMPAH-763",
        base_sha="1" * 40,
        head_sha="2" * 40,
    )
    issue = Issue(
        id="OOMPAH-814",
        identifier="OOMPAH-814",
        title="Accepted plain branch",
        state="Ready to Integrate",
        project_id="proj-1",
        parent_id="OOMPAH-763",
        work_branch=None,
        integration=existing,
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.config.parallel_epic_children_enabled = True
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite"))
    orch.integration_queue = queue
    try:
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            response = client.post(
                "/api/v1/issues/OOMPAH-814/submit",
                json={
                    "project_id": "proj-1",
                    "task_branch": "OOMPAH-814",
                    "head_sha": "2" * 40,
                    "remote_head_sha": "2" * 40,
                    "worktree_clean": True,
                    "summary": "Idempotent retry",
                },
            )
            duplicate = client.post(
                "/api/v1/issues/OOMPAH-814/submit",
                json={
                    "project_id": "proj-1",
                    "task_branch": "OOMPAH-814",
                    "head_sha": "2" * 40,
                    "remote_head_sha": "2" * 40,
                    "worktree_clean": True,
                    "summary": "Duplicate retry",
                },
            )
            queued = queue.items(project_id="proj-1", epic_id="OOMPAH-763")
    finally:
        queue.close()

    assert response.status_code == 201, response.text
    assert duplicate.status_code == 201, duplicate.text
    assert len(queued) == 1
    assert queued[0].task_branch == "OOMPAH-814"
    assert queued[0].head_sha == "2" * 40
    tracker.set_metadata_field.assert_called_once_with(
        "OOMPAH-814",
        "oompah.work_branch",
        "OOMPAH-814",
    )
    tracker.update_issue.assert_not_called()
    tracker.add_comment.assert_not_called()
    assert issue.work_branch == "OOMPAH-814"


def test_submit_refetch_fences_concurrent_branch_authority_change(tmp_path):
    stale = _issue()
    fresh = _issue()
    fresh.work_branch = "other-accepted-branch"
    fresh.integration = IntegrationRecord(
        state="blocked",
        task_branch="other-accepted-branch",
        head_sha="b" * 40,
    )
    tracker = MagicMock()
    # Project routing probes once, the endpoint fetches its initial snapshot,
    # then the submission authority fence performs the decisive fresh read.
    tracker.fetch_issue_detail.side_effect = [stale, stale, fresh]
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.config.parallel_epic_children_enabled = True
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite"))
    orch.integration_queue = queue
    try:
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            response = _post_submit(client)
    finally:
        queue.close()

    assert response.status_code == 400
    assert "expected work branch" in response.json()["error"]["message"]
    orch._cancel_retry_for_issue.assert_not_called()
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()


def test_remote_git_rejection_precedes_retry_tracker_and_queue_mutation(tmp_path):
    issue = _issue()
    issue.parent_id = "EPIC-1"
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.config.parallel_epic_children_enabled = True
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite"))
    orch.integration_queue = queue
    try:
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(
                server_module,
                "_verify_submission_git_authority",
                new=AsyncMock(side_effect=ValueError("remote head mismatch")),
            ),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            response = _post_submit(client)
    finally:
        queue.close()

    assert response.status_code == 400
    assert "remote head mismatch" in response.text
    orch._cancel_retry_for_issue.assert_not_called()
    tracker.get_metadata.assert_not_called()
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()


def test_direct_epic_verification_leaves_rewrite_ancestry_to_reconciliation():
    from oompah.projects import SubmissionGitAuthority

    issue = Issue(
        id="DIRECT-TASK",
        identifier="DIRECT-TASK",
        title="Rebase epic-EPIC-PARENT onto main",
        state="Needs Rebase",
        project_id="proj-1",
        parent_id="EPIC-PARENT",
        work_branch="epic-EPIC-PARENT",
    )
    record = IntegrationRecord(
        state="ready",
        task_branch="epic-EPIC-PARENT",
        base_branch="epic-EPIC-PARENT",
        base_sha="a" * 40,
        head_sha="b" * 40,
    )
    captured = {}

    class Store:
        @staticmethod
        def epic_branch_name(_identifier):
            return "epic-EPIC-PARENT"

        @staticmethod
        def verify_submission_git_authority(project_id, **kwargs):
            captured.update(project_id=project_id, **kwargs)
            return SubmissionGitAuthority(
                task_branch=kwargs["task_branch"],
                head_sha=kwargs["head_sha"],
                base_branch=kwargs["base_branch"],
                base_sha=None,
            )

    orch = MagicMock()
    orch.project_store = Store()
    orch.config.parallel_epic_children_enabled = True

    verified = asyncio.run(
        server_module._verify_submission_git_authority(
            orch,
            issue,
            "proj-1",
            record,
        )
    )

    assert captured == {
        "project_id": "proj-1",
        "task_branch": "epic-EPIC-PARENT",
        "head_sha": "b" * 40,
        "base_branch": "epic-EPIC-PARENT",
        "base_sha": None,
    }
    # The record retains the old base for the dedicated reconciliation path;
    # only generic ancestor validation omits it.
    assert verified.base_sha == "a" * 40


def test_nested_child_verification_preserves_recorded_immediate_parent_target():
    from oompah.projects import SubmissionGitAuthority

    issue = Issue(
        id="OOMPAH-834",
        identifier="OOMPAH-834",
        title="Nested child",
        parent_id="OOMPAH-804",
    )
    record = IntegrationRecord(
        state="ready",
        task_branch="epic-OOMPAH-804--task-OOMPAH-834",
        base_branch="epic-OOMPAH-768--task-OOMPAH-804",
        base_sha="a" * 40,
        head_sha="b" * 40,
    )
    captured = {}

    class Store:
        @staticmethod
        def epic_branch_name(_identifier):
            return "epic-OOMPAH-804"

        @staticmethod
        def verify_submission_git_authority(project_id, **kwargs):
            captured.update(project_id=project_id, **kwargs)
            return SubmissionGitAuthority(
                task_branch=kwargs["task_branch"],
                head_sha=kwargs["head_sha"],
                base_branch=kwargs["base_branch"],
                base_sha=kwargs["base_sha"],
            )

    orch = MagicMock()
    orch.project_store = Store()
    orch.config.parallel_epic_children_enabled = True

    verified = asyncio.run(
        server_module._verify_submission_git_authority(
            orch,
            issue,
            "oompah",
            record,
        )
    )

    assert captured["base_branch"] == (
        "epic-OOMPAH-768--task-OOMPAH-804"
    )
    assert verified.base_branch == captured["base_branch"]


def test_same_head_submission_with_corrected_target_is_a_new_authority():
    issue = Issue(
        id="OOMPAH-834",
        identifier="OOMPAH-834",
        title="Nested child",
        state="Ready to Integrate",
        parent_id="OOMPAH-804",
        work_branch="epic-OOMPAH-804--task-OOMPAH-834",
        integration=IntegrationRecord(
            state="ready",
            task_branch="epic-OOMPAH-804--task-OOMPAH-834",
            base_branch="epic-OOMPAH-804",
            base_sha="a" * 40,
            head_sha="b" * 40,
        ),
    )

    record = server_module._submission_record(
        issue,
        {
            "summary": "Correct the immediate parent target",
            "task_branch": issue.work_branch,
            "head_sha": "b" * 40,
            "remote_head_sha": "b" * 40,
            "base_branch": "epic-OOMPAH-768--task-OOMPAH-804",
            "base_sha": "c" * 40,
            "worktree_clean": True,
        },
    )

    assert record is not issue.integration
    assert record.base_branch == "epic-OOMPAH-768--task-OOMPAH-804"
    assert record.base_sha == "c" * 40


def _post_submit(client, *, head=None, summary="Done", branch="oompah/task/TASK-2"):
    """Helper: post a submit body for the shared test task with defaults."""
    return client.post(
        "/api/v1/issues/TASK-2/submit",
        json={
            "project_id": "proj-1",
            "task_branch": branch,
            "head_sha": head or "a" * 40,
            "remote_head_sha": head or "a" * 40,
            "worktree_clean": True,
            "summary": summary,
        },
    )


def _submit_test_bed(tmp_path, *, issue_state, existing_integration):
    """Wire an issue at a given canonical status with an existing integration.

    Returns (issue, tracker, orch, queue) that share a single queue store the
    caller must ``close()``. Metadata / status / comment tracker calls are
    recorded in ``tracker.set_metadata_field``, ``tracker.update_issue`` and
    ``tracker.add_comment``.
    """

    issue = Issue(
        id="TASK-2",
        identifier="TASK-2",
        title="Submitted task",
        state=issue_state,
        project_id="proj-1",
        work_branch="oompah/task/TASK-2",
        target_branch="main",
    )
    issue.parent_id = "EPIC-1"
    issue.integration = existing_integration
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store.list_all.return_value = []
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite"))
    orch.config.parallel_epic_children_enabled = True
    orch.integration_queue = queue
    return issue, tracker, orch, queue


def _run_submit(orch, body_head=None, summary="Done"):
    """Post a submit and return (response, tracker calls captured)."""
    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
        TestClient(app, raise_server_exceptions=False) as client,
    ):
        return _post_submit(client, head=body_head, summary=summary)


def _same_head_recovery_case(tmp_path, initial_status):
    """Same-head resubmit from a non-ready canonical status must reconcile
    the lifecycle to Ready to Integrate atomically and record the fresh
    summary comment.

    This is the OOMPAH-669 acceptance case: previously the identity-based
    guard in ``_persist_worker_submission`` returned early for a matching
    integration record and stranded the task at ``initial_status`` despite
    the 201 response.
    """

    existing = IntegrationRecord(
        state="ready",
        task_branch="oompah/task/TASK-2",
        head_sha="a" * 40,
    )
    _, tracker, orch, queue = _submit_test_bed(
        tmp_path, issue_state=initial_status, existing_integration=existing
    )
    try:
        response = _run_submit(orch, summary=f"Recovered from {initial_status}")
        assert response.status_code == 201, response.json()
        # Canonical lifecycle atomically reconciled to Ready to Integrate.
        tracker.update_issue.assert_called_once_with(
            "TASK-2", status="Ready to Integrate"
        )
        # Fresh summary comment recorded for this accepted generation.
        tracker.add_comment.assert_called_once()
        assert tracker.add_comment.call_args.args[1] == (
            f"Recovered from {initial_status}"
        )
        # Same-head recovery reuses the existing durable record, so no
        # spurious metadata rewrite fires.
        tracker.set_metadata_field.assert_not_called()
        # Queue is (re)armed for exactly one fresh delivery.
        queued = queue.items(project_id="proj-1", epic_id="EPIC-1")
        assert len(queued) == 1
        assert queued[0].head_sha == "a" * 40
        assert queued[0].state == "ready"
    finally:
        queue.close()


def test_same_head_resubmit_from_in_progress_restores_ready_lifecycle(tmp_path):
    _same_head_recovery_case(tmp_path, "In Progress")


def test_same_head_resubmit_from_needs_human_restores_ready_lifecycle(tmp_path):
    _same_head_recovery_case(tmp_path, "Needs Human")


def test_same_head_resubmit_clears_stale_dispatch_assignment(tmp_path):
    existing = IntegrationRecord(
        state="ready",
        task_branch="oompah/task/TASK-2",
        head_sha="a" * 40,
    )
    _, tracker, orch, queue = _submit_test_bed(
        tmp_path, issue_state="Needs Human", existing_integration=existing
    )
    tracker.get_metadata.return_value = {
        "oompah.agent_run_id": "stale-run-id",
    }
    try:
        response = _run_submit(orch, summary="Operator resubmission")
        assert response.status_code == 201, response.json()
    finally:
        queue.close()

    assert any(
        call.args[:3] == ("TASK-2", "oompah.agent_run_id", None)
        for call in tracker.set_metadata_field.call_args_list
    )
    tracker.update_issue.assert_called_once_with(
        "TASK-2", status="Ready to Integrate"
    )


def test_same_head_resubmit_from_needs_ci_fix_restores_ready_lifecycle(tmp_path):
    _same_head_recovery_case(tmp_path, "Needs CI Fix")


def test_duplicate_same_head_submit_already_ready_is_fully_idempotent(tmp_path):
    """A duplicate submit for a task already at Ready to Integrate with a
    matching integration record must not duplicate the summary comment, the
    status transition, or a metadata rewrite. Queue rearm must also be a
    no-op so identical resubmits cannot reset an active row."""

    existing = IntegrationRecord(
        state="ready",
        task_branch="oompah/task/TASK-2",
        head_sha="a" * 40,
    )
    _, tracker, orch, queue = _submit_test_bed(
        tmp_path,
        issue_state="Ready to Integrate",
        existing_integration=existing,
    )
    # Pre-populate the queue as though a prior accepted submit already
    # placed the row in ready state.
    queue.enqueue(
        project_id="proj-1",
        epic_id="EPIC-1",
        task_id="TASK-2",
        task_branch="oompah/task/TASK-2",
        head_sha="a" * 40,
    )
    try:
        response = _run_submit(orch, summary="Duplicate request")
        assert response.status_code == 201, response.json()
        # Zero tracker writes for a duplicate accepted submit.
        tracker.set_metadata_field.assert_not_called()
        tracker.update_issue.assert_not_called()
        tracker.add_comment.assert_not_called()
        # Queue still has exactly one identical row.
        queued = queue.items(project_id="proj-1", epic_id="EPIC-1")
        assert len(queued) == 1
        assert queued[0].head_sha == "a" * 40
        assert queued[0].state == "ready"
    finally:
        queue.close()


def test_same_head_resubmit_does_not_leak_to_other_projects(tmp_path):
    """Reconciling one task's lifecycle must not touch an unrelated task's
    tracker record or its integration queue row."""

    existing = IntegrationRecord(
        state="ready",
        task_branch="oompah/task/TASK-2",
        head_sha="a" * 40,
    )
    _, tracker, orch, queue = _submit_test_bed(
        tmp_path, issue_state="In Progress", existing_integration=existing
    )
    # Pre-seed an unrelated project's row that must remain untouched.
    queue.enqueue(
        project_id="proj-other",
        epic_id="EPIC-X",
        task_id="TASK-99",
        task_branch="oompah/task/TASK-99",
        head_sha="b" * 40,
    )
    try:
        response = _run_submit(orch)
        assert response.status_code == 201, response.json()
        # Only the submitted task's tracker is written.
        tracker.update_issue.assert_called_once_with(
            "TASK-2", status="Ready to Integrate"
        )
        # Unrelated project's queue row is untouched.
        untouched = queue.items(project_id="proj-other", epic_id="EPIC-X")
        assert len(untouched) == 1
        assert untouched[0].task_id == "TASK-99"
        assert untouched[0].head_sha == "b" * 40
        assert untouched[0].state == "ready"
    finally:
        queue.close()


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


def test_submit_endpoint_rejects_generated_worktree_helper_evidence():
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
                "task_branch": "oompah/task/TASK-2",
                "head_sha": "a" * 40,
                "remote_head_sha": "a" * 40,
                "worktree_clean": True,
                "changed_paths": [
                    "src/feature.py",
                    ".oompah-no-hooks/prepare-commit-msg",
                ],
                "summary": "Accidentally included helper",
            },
        )

    assert response.status_code == 400
    message = response.json()["error"]["message"]
    assert "Oompah-generated worktree helper" in message
    assert "git rm" in message
    tracker.set_metadata_field.assert_not_called()
    tracker.update_issue.assert_not_called()


def test_direct_epic_submission_avoids_ordinary_queue_enqueue(tmp_path):
    """Test that direct epic submission does not call _enqueue_worker_submission.
    
    Regression test for OOMPAH-758: direct epic maintenance tasks must not
    enter the ordinary child integration queue through api_submit_issue.
    """
    issue = Issue(
        id="DIRECT-TASK",
        identifier="DIRECT-TASK",
        title="Rebase epic-EPIC-PARENT onto main",
        state="Needs Rebase",
        project_id="proj-1",
        parent_id="EPIC-PARENT",
        work_branch="epic-EPIC-PARENT",
        integration=IntegrationRecord(
            state="working",
            task_branch="epic-EPIC-PARENT",
            base_branch="epic-EPIC-PARENT",
            base_sha="a" * 40,
        ),
    )
    tracker = MagicMock()
    tracker.fetch_issue_detail.return_value = issue
    integrated = IntegrationRecord(
        state="integrated",
        task_branch="epic-EPIC-PARENT",
        base_branch="epic-EPIC-PARENT",
        base_sha="a" * 40,
        head_sha="b" * 40,
        integrated_sha="b" * 40,
    )
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    orch.project_store.list_all.return_value = []
    orch.config.parallel_epic_children_enabled = True
    orch.complete_direct_epic_maintenance_submission = AsyncMock(
        return_value=(True, "published epic head reconciled", integrated)
    )
    queue = IntegrationQueueStore(str(tmp_path / "integration.sqlite"))
    orch.integration_queue = queue

    try:
        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            response = client.post(
                "/api/v1/issues/DIRECT-TASK/submit",
                json={
                    "project_id": "proj-1",
                    "task_branch": "epic-EPIC-PARENT",
                    "head_sha": "b" * 40,
                    "remote_head_sha": "b" * 40,
                    "worktree_clean": True,
                    "summary": "Rebased and ready",
                },
            )

        assert response.status_code == 201, response.text
        assert response.json()["state"] == "In Validation"
        # Verify complete_direct_epic_maintenance_submission was called
        orch.complete_direct_epic_maintenance_submission.assert_awaited_once()
        # Verify queue is empty - no rows created
        queue_items = queue.items(project_id="proj-1")
        assert queue_items == []
    finally:
        queue.close()
