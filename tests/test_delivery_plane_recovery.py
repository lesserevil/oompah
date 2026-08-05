"""Regression coverage for integration delivery recovery and authority fences."""

from __future__ import annotations

from dataclasses import replace
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import shlex
import subprocess
import threading
import time
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from oompah import server as server_module
from oompah.config import ServiceConfig
from oompah.integration import IntegrationRecord
from oompah.integration_executor import IntegrationExecutionResult
from oompah.models import Issue, Project, RunningEntry
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.orchestrator import Orchestrator
from oompah.quality_gate import BranchQualityGate, QualityGateOwner
from oompah.server import AuthenticatedPrincipal, app
from oompah.statuses import (
    ARCHIVED,
    DONE,
    IN_VALIDATION,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    READY_TO_INTEGRATE,
)
from oompah.terminal_audit import (
    AuditAttempt,
    ContributorIdentity,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)
from oompah.terminal_transition_coordinator import TransitionResult


def _issue(
    *,
    identifier: str = "TASK-1",
    state: str = READY_TO_INTEGRATE,
    integration_state: str = "blocked",
    last_error: str | None = None,
) -> Issue:
    return Issue(
        id=identifier.lower(),
        identifier=identifier,
        title="Delivery task",
        state=state,
        parent_id="EPIC-1",
        integration=IntegrationRecord(
            state=integration_state,
            task_branch=f"epic-EPIC-1--task-{identifier}",
            head_sha="a" * 40,
            last_error=last_error,
        ),
    )


def _make_harness(tmp_path, issue: Issue):
    project = Project(
        id="proj-1",
        name="Recovery project",
        repo_url="https://github.com/org/repo.git",
        repo_path=str(tmp_path / "repo"),
        default_branch="main",
    )
    tracker = mock.MagicMock()
    tracker.fetch_issues_by_states.return_value = [issue]
    tracker.fetch_all_issues.return_value = [issue]
    tracker.fetch_issue_detail.return_value = issue
    project_store = mock.MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.side_effect = lambda project_id: (
        project if project_id == project.id else None
    )
    orchestrator = Orchestrator(
        config=ServiceConfig(),
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "service-state.json"),
    )
    orchestrator._project_trackers[project.id] = tracker
    return orchestrator, project, tracker


def _blocked_row(orchestrator: Orchestrator, project: Project, issue: Issue):
    row = orchestrator.integration_queue.enqueue(
        project_id=project.id,
        epic_id=issue.parent_id or "EPIC-1",
        task_id=issue.identifier,
        task_branch=issue.integration.task_branch,
        head_sha=issue.integration.head_sha,
    )
    claimed = orchestrator.integration_queue.claim_next(
        project_id=project.id,
        epic_id=issue.parent_id or "EPIC-1",
        lease_owner="worker-1",
        dependency_map={issue.identifier: ()},
        satisfied=set(),
    )
    assert claimed is not None
    assert orchestrator.integration_queue.fail(
        project.id,
        issue.identifier,
        lease_owner="worker-1",
        error="stale integration failure",
    )
    return row


def _seed_completed_audit(
    tracker,
    issue: Issue,
    classifications: list[FailureClassification],
) -> None:
    """Seed the durable terminal outcome used by the recovery sweep."""
    fingerprint = compute_issue_evidence_fingerprint(issue, "proj-1")
    attempts = [
        AuditAttempt(
            attempt_id=f"attempt-{index}",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.COMPLETED,
            verdict=Verdict.FAIL,
            failure_classification=classification,
        )
        for index, classification in enumerate(classifications)
    ]
    record = TerminalAuditRecord(
        audit_id="audit-recovery-1",
        project_id="proj-1",
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=attempts,
        requested_by=ContributorIdentity("auditor", "test"),
    )
    tracker.get_metadata.return_value = {
        METADATA_KEY: TerminalAuditMetadata(pending_chain=[record]).to_dict()
    }


def _close(orchestrator: Orchestrator) -> None:
    orchestrator.integration_queue.close()
    orchestrator.coordination_store.close()
    orchestrator.task_transition_journal.close()
    orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
    orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


class _RecoveryProjectStore:
    """Concrete project boundary for the durable recovery lifecycle test."""

    def __init__(self, project: Project) -> None:
        self.project = project
        self._lock = threading.RLock()
        self.removed_worktrees: list[tuple[str, str]] = []

    def list_all(self) -> list[Project]:
        return [self.project]

    def get(self, project_id: str) -> Project | None:
        return self.project if project_id == self.project.id else None

    def find_by_name(self, name: str) -> Project | None:
        return self.project if name == self.project.name else None

    def project_write_lock(self, project_id: str) -> threading.RLock:
        assert project_id == self.project.id
        return self._lock

    def epic_branch_name(self, project_id: str, epic_id: str) -> str:
        assert project_id == self.project.id
        return f"epic-{epic_id}"

    def remove_worktree(self, project_id: str, task_id: str) -> None:
        self.removed_worktrees.append((project_id, task_id))


def _close_durable_harness(orchestrator: Orchestrator) -> None:
    asyncio.run(orchestrator._drain_background_work())
    orchestrator.integration_queue.close()
    orchestrator.coordination_store.close()


def _durable_recovery_harness(tmp_path, project: Project, project_store):
    state_dir = tmp_path / "durable-state"
    state_dir.mkdir(exist_ok=True)
    tracker = OompahMarkdownTracker(
        active_states=[OPEN, IN_VALIDATION, NEEDS_HUMAN, READY_TO_INTEGRATE],
        terminal_states=[DONE],
        cwd=project.repo_path,
        default_branch=project.default_branch,
        git_sync=False,
    )
    orchestrator = Orchestrator(
        config=ServiceConfig(),
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(state_dir / "service-state.json"),
    )
    orchestrator._project_trackers[project.id] = tracker
    return orchestrator, tracker


def _authenticated_owner_retry(
    orchestrator: Orchestrator,
    *,
    project_id: str,
    task_id: str,
    reason: str,
):
    client = TestClient(app, raise_server_exceptions=False)
    try:
        with (
            mock.patch.object(
                server_module,
                "_get_orchestrator",
                return_value=orchestrator,
            ),
            mock.patch.object(
                server_module,
                "_authenticated_principal",
                return_value=AuthenticatedPrincipal("owner", "owner", "basic"),
            ),
            mock.patch.object(
                server_module,
                "broadcast_issues",
                new=mock.AsyncMock(),
            ),
        ):
            return client.patch(
                f"/api/v1/issues/{task_id}",
                json={
                    "project_id": project_id,
                    "status": DONE,
                    "audit_retry": True,
                    "audit_retry_reason": reason,
                },
            )
    finally:
        client.close()


def test_integrated_audit_failure_arms_one_recovery_alert_without_warning_loop(tmp_path):
    issue = _issue(state="Needs Human", integration_state="integrated")
    issue.integration = replace(issue.integration, integrated_sha="c" * 40)
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    _seed_completed_audit(
        tracker,
        issue,
        [
            FailureClassification.FINALIZATION_FAILURE,
            FailureClassification.NO_AUDITOR,
        ],
    )
    orchestrator.project_store.epic_branch_name.return_value = "epic-EPIC-1"
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id=issue.parent_id or "EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id=issue.parent_id or "EPIC-1",
            lease_owner="worker-1",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert orchestrator.integration_queue.complete(
            project.id,
            issue.identifier,
            lease_owner="worker-1",
        )

        orchestrator.request_terminal_transition = mock.AsyncMock(
            return_value=TransitionResult(success=False, reason="already completed")
        )
        asyncio.run(orchestrator._stage_integrated_task_audit(claimed))
        asyncio.run(orchestrator._stage_integrated_task_audit(claimed))

        alerts = [
            alert
            for alert in orchestrator._alerts
            if alert.get("source") == "terminal_audit_recovery:proj-1:TASK-1"
        ]
        assert len(alerts) == 1
        assert "c" * 40 in alerts[0]["message"]
        assert "audit_retry" in alerts[0]["message"]
        assert "audit_retry_evidence_addendum" not in alerts[0]["message"]
        assert (
            orchestrator.request_terminal_transition.call_args.kwargs[
                "evidence_fingerprint"
            ]
            == compute_issue_evidence_fingerprint(issue, project.id)
        )

        issue.state = "In Validation"
        asyncio.run(orchestrator._stage_integrated_task_audit(claimed))
        assert not any(
            alert.get("source") == "terminal_audit_recovery:proj-1:TASK-1"
            for alert in orchestrator._alerts
        )
    finally:
        _close(orchestrator)


def test_owner_recovery_lifecycle_is_durable_coalesced_and_clears_alert(tmp_path):
    """Exercise the production tracker, API, coordinator, queue, and restart path."""

    repo = tmp_path / "repo"
    repo.mkdir()
    project = Project(
        id="proj-durable",
        name="Durable recovery project",
        repo_url=str(repo),
        repo_path=str(repo),
        default_branch="main",
        tracker_kind="oompah_md",
        tracker_owner="owner",
        tracker_repo="durable-recovery",
        status_actor_login="owner",
        status_label_authorized_logins=["owner"],
    )
    project_store = _RecoveryProjectStore(project)
    orchestrator, tracker = _durable_recovery_harness(
        tmp_path,
        project,
        project_store,
    )
    restarted: Orchestrator | None = None
    orchestrator_closed = False
    issue = tracker.create_issue(
        "Durable audit recovery",
        description="Exercise the complete recovery lifecycle.",
        initial_status=NEEDS_HUMAN,
    )
    integration = IntegrationRecord(
        state="integrated",
        task_branch=f"task-{issue.identifier}",
        base_branch="main",
        base_sha="b" * 40,
        head_sha="a" * 40,
        integrated_sha="c" * 40,
    )
    tracker.set_metadata_field(
        issue.identifier,
        "oompah.integration",
        integration.to_dict(),
    )
    issue = tracker.fetch_issue_detail(issue.identifier)
    assert issue is not None
    fingerprint = compute_issue_evidence_fingerprint(issue, project.id)
    failed = TerminalAuditRecord(
        audit_id="audit-durable-failure",
        project_id=project.id,
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id="attempt-finalization",
                target_state=TargetState.DONE,
                evidence_fingerprint=fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.FAIL,
                failure_classification=FailureClassification.FINALIZATION_FAILURE,
            ),
            AuditAttempt(
                attempt_id="attempt-no-auditor",
                target_state=TargetState.DONE,
                evidence_fingerprint=fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.FAIL,
                failure_classification=FailureClassification.NO_AUDITOR,
            ),
        ],
        requested_by=ContributorIdentity("auditor", "service"),
        previous_state=READY_TO_INTEGRATE,
    )
    audit_store = TerminalAuditMetadataStore(
        tracker,
        project_store,
        project.id,
    )
    audit_store.write(
        issue.identifier,
        TerminalAuditMetadata(pending_chain=[failed]),
    )
    orchestrator.integration_queue.enqueue(
        project_id=project.id,
        epic_id="top-level",
        task_id=issue.identifier,
        task_branch=integration.task_branch or "",
        head_sha=integration.head_sha or "",
        base_sha=integration.base_sha,
    )
    claimed = orchestrator.integration_queue.claim_next(
        project_id=project.id,
        epic_id="top-level",
        lease_owner="integration-worker",
        dependency_map={issue.identifier: ()},
        satisfied=set(),
    )
    assert claimed is not None
    assert orchestrator.integration_queue.complete(
        project.id,
        issue.identifier,
        lease_owner="integration-worker",
    )
    integrated_row = orchestrator.integration_queue.get(project.id, issue.identifier)
    assert integrated_row is not None

    try:
        asyncio.run(orchestrator._stage_integrated_task_audit(integrated_row))
        recovery_source = (
            f"terminal_audit_recovery:{project.id}:{issue.identifier}"
        )
        recovery_alerts = [
            alert
            for alert in orchestrator._alerts
            if alert.get("source") == recovery_source
        ]
        assert len(recovery_alerts) == 1
        assert "`audit_retry`" in recovery_alerts[0]["message"]

        response = _authenticated_owner_retry(
            orchestrator,
            project_id=project.id,
            task_id=issue.identifier,
            reason="Auditor transport is healthy again.",
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["audit_retry"] is True
        assert payload["status"] == IN_VALIDATION
        fresh_audit_id = payload["audit_id"]
        recovered = audit_store.read(issue.identifier).pending_chain
        assert len(recovered) == 2
        assert recovered[0].request_state == RequestState.SUPERSEDED
        assert recovered[1].request_state == RequestState.PENDING
        assert recovered[1].audit_id == fresh_audit_id
        assert recovered[1].evidence_fingerprint == fingerprint

        asyncio.run(orchestrator._stage_integrated_task_audit(integrated_row))
        assert not any(
            alert.get("source") == recovery_source
            for alert in orchestrator._alerts
        )

        _close_durable_harness(orchestrator)
        orchestrator_closed = True
        restarted, restarted_tracker = _durable_recovery_harness(
            tmp_path,
            project,
            project_store,
        )
        restarted_row = restarted.integration_queue.get(project.id, issue.identifier)
        assert restarted_row is not None
        coalesced_response = _authenticated_owner_retry(
            restarted,
            project_id=project.id,
            task_id=issue.identifier,
            reason="Confirm recovery after restart.",
        )

        assert coalesced_response.status_code == 200
        assert coalesced_response.json()["audit_id"] == fresh_audit_id
        restarted_audit_store = TerminalAuditMetadataStore(
            restarted_tracker,
            project_store,
            project.id,
        )
        after_restart = restarted_audit_store.read(issue.identifier).pending_chain
        assert len(after_restart) == 2
        assert after_restart[-1].request_state == RequestState.PENDING
        asyncio.run(restarted._stage_integrated_task_audit(restarted_row))
        assert not any(
            alert.get("source") == recovery_source
            for alert in restarted._alerts
        )
    finally:
        if restarted is not None:
            _close_durable_harness(restarted)
        elif not orchestrator_closed:
            _close_durable_harness(orchestrator)


def test_integrated_audit_recovery_alert_uses_evidence_addendum_only_for_missing_evidence(
    tmp_path,
):
    issue = _issue(state="Needs Human", integration_state="integrated")
    issue.integration = replace(issue.integration, integrated_sha="c" * 40)
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    _seed_completed_audit(tracker, issue, [FailureClassification.MISSING_EVIDENCE])
    orchestrator.project_store.epic_branch_name.return_value = "epic-EPIC-1"
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id=issue.parent_id or "EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id=issue.parent_id or "EPIC-1",
            lease_owner="worker-1",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert orchestrator.integration_queue.complete(
            project.id, issue.identifier, lease_owner="worker-1"
        )
        orchestrator.request_terminal_transition = mock.AsyncMock(
            return_value=TransitionResult(success=False, reason="already completed")
        )

        asyncio.run(orchestrator._stage_integrated_task_audit(claimed))

        alerts = [
            alert
            for alert in orchestrator._alerts
            if alert.get("source") == "terminal_audit_recovery:proj-1:TASK-1"
        ]
        assert len(alerts) == 1
        assert "audit_retry_evidence_addendum" in alerts[0]["message"]
        assert "with `audit_retry`" not in alerts[0]["message"]
    finally:
        _close(orchestrator)


def test_integrated_audit_replay_is_bounded_and_resumes_after_restart(tmp_path):
    issue = _issue()
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    orchestrator.config.integration_audit_batch_size = 2
    for index in range(3):
        task_id = f"HIST-{index}"
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=task_id,
            task_branch=f"epic-EPIC-1--task-{task_id}",
            head_sha=(f"{index + 1:01x}" * 40),
            priority=index,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner=f"worker-{index}",
            dependency_map={task_id: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert orchestrator.integration_queue.complete(
            project.id,
            task_id,
            lease_owner=f"worker-{index}",
        )

    staged = mock.AsyncMock()
    orchestrator._stage_integrated_task_audit = staged
    try:
        first = asyncio.run(orchestrator._replay_integrated_audit_batch())
        assert first["replayed"] == 2
        assert first["deferred"] is True
        assert [call.args[0].task_id for call in staged.await_args_list] == [
            "HIST-0",
            "HIST-1",
        ]
    finally:
        _close(orchestrator)

    restarted, _project, _tracker = _make_harness(tmp_path, issue)
    restarted.config.integration_audit_batch_size = 2
    resumed_staged = mock.AsyncMock()
    restarted._stage_integrated_task_audit = resumed_staged
    try:
        resumed = asyncio.run(restarted._replay_integrated_audit_batch())
        assert resumed["replayed"] == 1
        assert resumed["deferred"] is False
        assert [
            call.args[0].task_id for call in resumed_staged.await_args_list
        ] == ["HIST-2"]
        assert restarted._maintenance_cursors.get("integration_audit") is None
    finally:
        _close(restarted)


@pytest.mark.timeout(30)
def test_live_ready_claim_precedes_large_integrated_audit_history(tmp_path):
    issue = _issue(identifier="LIVE-READY", integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    orchestrator.config.integration_audit_batch_size = 32
    for index in range(200):
        task_id = f"HIST-{index:03d}"
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=task_id,
            task_branch=f"epic-EPIC-1--task-{task_id}",
            head_sha=(f"{index + 1:x}" * 40),
            priority=index,
            submitted_at=f"2026-07-{(index % 28) + 1:02d}T00:00:00+00:00",
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner=f"history-worker-{index}",
            dependency_map={task_id: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert orchestrator.integration_queue.complete(
            project.id,
            task_id,
            lease_owner=f"history-worker-{index}",
        )

    events: list[str] = []
    original_claim_next = orchestrator.integration_queue.claim_next

    def record_claim(*args, **kwargs):
        events.append("claim")
        return original_claim_next(*args, **kwargs)

    orchestrator.integration_queue.claim_next = record_claim
    orchestrator._integration_dependency_map = mock.MagicMock(
        return_value={issue.identifier: ()}
    )
    orchestrator._integration_satisfied_dependencies = mock.MagicMock(
        return_value=set()
    )
    orchestrator._execute_integration_item = mock.MagicMock(
        return_value=IntegrationExecutionResult(
            status="integrated",
            message="integrated",
            expected_epic_sha="b" * 40,
            rebased_task_sha="c" * 40,
            integrated_sha="d" * 40,
        )
    )

    async def record_audit(item):
        events.append(f"audit:{item.task_id}")

    orchestrator._stage_integrated_task_audit = record_audit
    orchestrator.project_store.epic_branch_name.return_value = "epic-EPIC-1"
    try:
        asyncio.run(orchestrator._process_integration_queues())
        assert events[0] == "claim"
        assert events[1] == "audit:LIVE-READY"
        assert orchestrator._maintenance_status["integration_queue"][
            "audit_replayed"
        ] == 32
        assert orchestrator.integration_queue.items(
            states=("integrating",),
        ) == []
        assert orchestrator.integration_queue.items(
            project_id=project.id,
            epic_id="EPIC-1",
            states=("integrated",),
        )[-1].task_id == issue.identifier
    finally:
        _close(orchestrator)


def test_dependency_blocked_ready_row_is_not_reported_as_claim_stall(tmp_path):
    issue = _issue(identifier="BLOCKED", integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    row = orchestrator.integration_queue.enqueue(
        project_id=project.id,
        epic_id="EPIC-1",
        task_id=issue.identifier,
        task_branch=issue.integration.task_branch,
        head_sha=issue.integration.head_sha,
        submitted_at="2020-01-01T00:00:00+00:00",
    )
    try:
        orchestrator._record_integration_queue_progress(
            queue_items=[row],
            eligible_ready_count=0,
            oldest_eligible_submitted_at=None,
            claimed_count=0,
            audit_progress={"batch_size": 1, "replayed": 0},
        )
        assert orchestrator._maintenance_status["integration_queue"][
            "status"
        ] == "healthy"
        assert not any(
            alert.get("source") == "integration_queue_progress"
            for alert in orchestrator._alerts
        )

        orchestrator._record_integration_queue_progress(
            queue_items=[row],
            eligible_ready_count=1,
            oldest_eligible_submitted_at=row.submitted_at,
            claimed_count=0,
            audit_progress={"batch_size": 1, "replayed": 0},
        )
        assert orchestrator._maintenance_status["integration_queue"][
            "status"
        ] == "degraded"
        assert any(
            alert.get("source") == "integration_queue_progress"
            for alert in orchestrator._alerts
        )
    finally:
        _close(orchestrator)


def _local_quality_gate_repo(tmp_path):
    repo = tmp_path / "quality-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "oompah"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "lesserevil@users.noreply.github.com"],
        cwd=repo,
        check=True,
    )
    (repo / "source.txt").write_text("quality gate\n", encoding="utf-8")
    subprocess.run(["git", "add", "source.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "quality gate"], cwd=repo, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return repo, head


def test_ready_retry_metadata_rearms_identical_blocked_queue_row(tmp_path):
    issue = _issue(integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        _blocked_row(orchestrator, project, issue)

        orchestrator._sync_ready_integration_submissions()

        row = orchestrator.integration_queue.items(project_id=project.id)[0]
        assert row.state == "ready"
        assert row.retry_forced is True
        assert not any(
            alert.get("source") == "integration_delivery:proj-1:TASK-1"
            for alert in orchestrator._alerts
        )
    finally:
        _close(orchestrator)


def test_blocked_row_alerts_clear_after_row_and_scan_recover(tmp_path):
    issue = _issue(last_error="old merge conflict")
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    try:
        _blocked_row(orchestrator, project, issue)
        orchestrator._audit_blocked_integration_rows(project.id, tracker)
        assert any(
            alert.get("source") == "integration_delivery:proj-1:TASK-1"
            for alert in orchestrator._alerts
        )

        tracker.fetch_all_issues.side_effect = RuntimeError("tracker offline")
        orchestrator._audit_blocked_integration_rows(project.id, tracker)
        assert any(
            alert.get("source") == "integration_delivery_scan:proj-1"
            for alert in orchestrator._alerts
        )

        issue.state = NEEDS_REBASE
        tracker.fetch_all_issues.side_effect = None
        tracker.fetch_all_issues.return_value = [issue]
        orchestrator._audit_blocked_integration_rows(project.id, tracker)
        assert not any(
            str(alert.get("source", "")).startswith("integration_delivery")
            for alert in orchestrator._alerts
        )

        assert orchestrator.integration_queue.cancel(
            project.id,
            issue.identifier,
            reason="repair superseded",
        )
        orchestrator._audit_blocked_integration_rows(project.id, tracker)
        assert not any(
            str(alert.get("source", "")).startswith("integration_delivery")
            for alert in orchestrator._alerts
        )
    finally:
        _close(orchestrator)


def test_terminal_task_retires_active_row_and_invalidates_lease(tmp_path):
    issue = _issue(state=DONE, integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="stale-worker",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None

        assert (
            orchestrator._retire_inactive_integration_rows(
                project.id,
                [issue],
                [claimed],
            )
            == 1
        )
        row = orchestrator.integration_queue.items(project_id=project.id)[0]
        assert row.state == "cancelled"
        assert not orchestrator.integration_queue.fail(
            project.id,
            issue.identifier,
            lease_owner="stale-worker",
            error="late conflict",
        )
    finally:
        _close(orchestrator)


def test_retire_inactive_rows_retires_open_tasks_and_cancels_gate_generation(tmp_path):
    """Tasks returned to Open must have their integration row retired and gate cancelled.

    Root cause of OOMPAH-657: _retire_inactive_integration_rows excluded Open
    from its inactive_states set, so a task moved from Ready to Integrate back
    to Open kept its row alive and the gate continued running or re-launched.

    This test also verifies that exact-owner cancellation tombstones each
    retired row so a pre-spawn gate (in snapshot creation or between Popen and
    registration) also stops.
    """
    issue = _issue(state=OPEN, integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        # Claim the item so it transitions to "integrating" state (mimics the
        # live scenario where the row was claimed just before the Open transition).
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="stale-worker",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None

        # Compute the exact owner (same formula as _execute_integration_item).
        expected_gen = (
            f"integration:{claimed.project_id}:{claimed.task_id}:"
            f"{claimed.head_sha}:{claimed.lease_owner or ''}"
        )
        expected_owner = QualityGateOwner(
            project_id=claimed.project_id,
            task_id=claimed.task_id,
            head_sha=claimed.head_sha,
            authority_generation=expected_gen,
        )

        # Ensure the tombstone set is clean before the call.
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard(expected_gen)
            BranchQualityGate._cancelled_owner_keys.discard(expected_owner.key)

        retired = orchestrator._retire_inactive_integration_rows(
            project.id,
            [issue],
            [claimed],
        )

        assert retired == 1
        row = orchestrator.integration_queue.items(project_id=project.id)[0]
        assert row.state == "cancelled"

        # The exact-owner tombstone must have been set so that any running or
        # pre-spawn gate for this exact item also stops.
        with BranchQualityGate._processes_lock:
            assert expected_owner.key in BranchQualityGate._cancelled_owner_keys
    finally:
        # Clean up tombstone to avoid polluting other tests.
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard(expected_gen)
            BranchQualityGate._cancelled_owner_keys.discard(expected_owner.key)
        _close(orchestrator)


def test_completion_auditor_retirement_preserves_unrelated_branch_gate(tmp_path):
    """Retiring task A cannot interrupt task B's exact-head gate.

    This follows the production ordering: a completion auditor is retired,
    queue reconciliation observes its terminal task state, and the stale row
    is fenced while another task's branch gate is already running. Both rows
    intentionally share a legacy-looking generation so a generation-only
    cancellation would reproduce the original incident.
    """
    repo, head = _local_quality_gate_repo(tmp_path)
    marker = tmp_path / "task-b-accepted"
    gate = BranchQualityGate(
        str(tmp_path / "quality.json"),
        safety_head=head,
        sandbox_launcher=lambda command, _snapshot, _run_root: [
            "/bin/sh",
            "-c",
            command,
        ],
    )
    auditor_issue = _issue(
        identifier="TASK-A-AUDITOR",
        state=DONE,
        integration_state="ready",
    )
    auditor_issue.project_id = "proj-1"
    auditor_issue.integration = IntegrationRecord(
        state="ready",
        task_branch=auditor_issue.integration.task_branch,
        head_sha=head,
    )
    orchestrator, project, _tracker = _make_harness(tmp_path, auditor_issue)
    orchestrator._branch_quality_gate = gate
    entry = RunningEntry(
        worker_task=mock.MagicMock(),
        identifier=auditor_issue.identifier,
        issue=auditor_issue,
        session=None,
        retry_attempt=0,
        started_at=datetime.now(timezone.utc),
        is_auditor=True,
        audit_id="audit-a",
        audit_attempt_id="attempt-a",
        branch_key="task-a-branch",
    )
    entry.worker_task.done.return_value = True
    orchestrator.state.running[auditor_issue.id] = entry
    orchestrator.state.claimed.add(auditor_issue.id)
    orchestrator.state.claimed_issues[auditor_issue.id] = auditor_issue
    orchestrator._audit_branch_claims[entry.branch_key] = entry.audit_attempt_id
    generation = (
        f"integration:{project.id}:{auditor_issue.identifier}:"
        f"{head}:auditor-generation"
    )
    owner_b = QualityGateOwner(project.id, "TASK-B-BRANCH", head, generation)

    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=auditor_issue.identifier,
            task_branch=auditor_issue.integration.task_branch,
            head_sha=head,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="auditor-generation",
            dependency_map={auditor_issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                gate.run,
                repo_path=str(repo),
                repo_identity="https://example.test/org/repo",
                target_branch="main",
                work_branch="task-b-branch",
                command=f"sleep 0.5; touch {shlex.quote(str(marker))}",
                expected_head_sha=head,
                generation=generation,
                owner=owner_b,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                active = BranchQualityGate.active_state()
                if active:
                    assert active[0]["task_id"] == owner_b.task_id
                    break
                time.sleep(0.01)
            else:
                raise AssertionError("task B quality gate was not active")

            with (
                mock.patch.object(orchestrator, "_fire_task_cost_record"),
                mock.patch.object(orchestrator, "_fire_telemetry_comment"),
            ):
                assert asyncio.run(
                    orchestrator._terminate_running(
                        auditor_issue.id,
                        cleanup_workspace=False,
                    )
                )
            assert orchestrator._retire_inactive_integration_rows(
                project.id,
                [auditor_issue],
                [claimed],
            ) == 1
            assert BranchQualityGate.active_state()[0]["task_id"] == "TASK-B-BRANCH"
            result = future.result(timeout=5)

        assert result.passed
        assert marker.exists()
    finally:
        with BranchQualityGate._processes_lock:
            BranchQualityGate._cancelled_generations.discard(generation)
            BranchQualityGate._cancelled_owner_keys.discard(owner_b.key)
        BranchQualityGate.cleanup_active_processes()
        _close(orchestrator)


def test_retire_inactive_rows_does_not_retire_ready_to_integrate_tasks(tmp_path):
    """A task still in Ready to Integrate must keep its integration row alive."""
    issue = _issue(state=READY_TO_INTEGRATE, integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        item = orchestrator.integration_queue.items(project_id=project.id)[0]

        retired = orchestrator._retire_inactive_integration_rows(
            project.id,
            [issue],
            [item],
        )

        assert retired == 0
        assert (
            orchestrator.integration_queue.items(project_id=project.id)[0].state
            == "ready"
        )
    finally:
        _close(orchestrator)


def test_retire_inactive_rows_preserves_exact_blocked_repair_evidence(tmp_path):
    """Needs-CI repair keeps the durable failure row across reconciliation."""

    issue = _issue(state=NEEDS_CI_FIX, integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        queued = orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="failed-gate",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert orchestrator.integration_queue.fail(
            project.id,
            issue.identifier,
            lease_owner="failed-gate",
            error="combined-tree quality gate failed",
        )
        blocked = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert blocked is not None and blocked.state == "blocked"

        retired = orchestrator._retire_inactive_integration_rows(
            project.id,
            [issue],
            [blocked],
        )

        assert retired == 0
        retained = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert retained is not None
        assert retained.state == "blocked"
        assert retained.head_sha == queued.head_sha
    finally:
        _close(orchestrator)


def test_retire_inactive_rows_retires_mismatched_blocked_repair_evidence(tmp_path):
    """A newer accepted head must not inherit an obsolete blocked result."""

    issue = _issue(state=NEEDS_CI_FIX, integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="failed-gate",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert orchestrator.integration_queue.fail(
            project.id,
            issue.identifier,
            lease_owner="failed-gate",
            error="combined-tree quality gate failed",
        )
        issue.integration = IntegrationRecord(
            state="ready",
            task_branch=issue.integration.task_branch,
            head_sha="new-accepted-head",
        )
        blocked = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert blocked is not None and blocked.state == "blocked"

        retired = orchestrator._retire_inactive_integration_rows(
            project.id,
            [issue],
            [blocked],
        )

        assert retired == 1
        current = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert current is not None and current.state == "cancelled"
    finally:
        _close(orchestrator)


def test_exact_ready_submission_is_required_for_executor_authority(tmp_path):
    issue = _issue(integration_state="ready")
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    try:
        row = orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        # A queued submission has no executor authority until it has an exact
        # durable integrating lease.
        assert not orchestrator._integration_task_still_ready(row)
        claimed_at = time.time()
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id=issue.parent_id or "EPIC-1",
            lease_owner="first-generation",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
            lease_seconds=1,
            now=claimed_at,
        )
        assert claimed is not None
        assert orchestrator._integration_task_still_ready(claimed)

        issue.state = DONE
        assert not orchestrator._integration_task_still_ready(claimed)
        issue.state = READY_TO_INTEGRATE
        issue.integration = IntegrationRecord(
            state="ready",
            task_branch=claimed.task_branch,
            head_sha="b" * 40,
        )
        assert not orchestrator._integration_task_still_ready(claimed)
        tracker.fetch_issue_detail.return_value = None
        assert not orchestrator._integration_task_still_ready(claimed)
    finally:
        _close(orchestrator)


# ---------------------------------------------------------------------------
# OOMPAH-806: preserve blocked rows through watchdog-driven Open transitions
# ---------------------------------------------------------------------------


def _blocked_row_for(orchestrator, project, issue):
    """Enqueue an item and drive it to a durable ``blocked`` queue state."""
    orchestrator.integration_queue.enqueue(
        project_id=project.id,
        epic_id=issue.parent_id or "EPIC-1",
        task_id=issue.identifier,
        task_branch=issue.integration.task_branch,
        head_sha=issue.integration.head_sha,
    )
    claimed = orchestrator.integration_queue.claim_next(
        project_id=project.id,
        epic_id=issue.parent_id or "EPIC-1",
        lease_owner="gate-worker",
        dependency_map={issue.identifier: ()},
        satisfied=set(),
    )
    assert claimed is not None
    assert orchestrator.integration_queue.fail(
        project.id,
        issue.identifier,
        lease_owner="gate-worker",
        error="combined-tree gate failed at ef5e8c30e",
    )
    row = orchestrator.integration_queue.get(project.id, issue.identifier)
    assert row is not None
    assert row.state == "blocked"
    return row


def test_combined_tree_gate_failure_uses_transition_service(tmp_path):
    """The blocked record is persisted before its generation-fenced status."""

    issue = _issue(state=READY_TO_INTEGRATE, integration_state="ready")
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    orchestrator.project_store.epic_branch_name.return_value = "epic-EPIC-1"

    def set_metadata(identifier, key, value):
        assert identifier == issue.identifier
        assert key == "oompah.integration"
        issue.integration = IntegrationRecord.from_dict(value)

    def update_issue(identifier, **fields):
        assert identifier == issue.identifier
        issue.state = fields["status"]

    tracker.set_metadata_field.side_effect = set_metadata
    tracker.update_issue.side_effect = update_issue
    tracker.fetch_issue_detail.side_effect = lambda identifier: (
        issue if identifier == issue.identifier else None
    )

    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="gate-generation-1",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None

        orchestrator._route_integration_failure(
            claimed,
            IntegrationExecutionResult(
                status="ci_failure",
                message="combined-tree gate failed at exact head",
                expected_epic_sha="b" * 40,
                rebased_task_sha="a" * 40,
            ),
        )

        assert issue.integration.state == "blocked"
        assert issue.integration.head_sha == "a" * 40
        assert issue.state == NEEDS_CI_FIX
        tracker.update_issue.assert_called_once_with(
            issue.identifier, status=NEEDS_CI_FIX
        )
        row = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert row is not None and row.state == "blocked"
    finally:
        _close(orchestrator)


def test_retire_preserves_blocked_row_when_watchdog_reopens_task(tmp_path):
    """OOMPAH-806: an internal blocked gate must survive watchdog-driven Open.

    Reproduces OOMPAH-793: gate failed, integration row is blocked at head H,
    tracker task is Needs CI Fix.  Watchdog observed unrelated passing external
    CI and flipped the task to Open.  The queue reconciler previously cancelled
    the blocked row because tracker state was no longer Ready to Integrate,
    discarding authoritative internal gate authority.
    """
    issue = _issue(state=NEEDS_CI_FIX, integration_state="blocked")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        blocked = _blocked_row_for(orchestrator, project, issue)

        # Simulate the watchdog reopen: tracker now shows Open.
        issue.state = OPEN

        retired = orchestrator._retire_inactive_integration_rows(
            project.id,
            [issue],
            [blocked],
        )

        assert retired == 0
        row_after = orchestrator.integration_queue.get(
            project.id, issue.identifier
        )
        assert row_after is not None
        assert row_after.state == "blocked"
        assert row_after.head_sha == blocked.head_sha
    finally:
        _close(orchestrator)


def test_open_task_with_blocked_gate_cannot_dispatch_without_direct_owner(tmp_path):
    """Persisted gate authority prevents duplicate generic implementation."""

    issue = _issue(state=OPEN, integration_state="blocked")
    issue.project_id = "proj-1"
    issue.description = "Already implemented; exact-head gate needs repair."
    orchestrator, _project, _tracker = _make_harness(tmp_path, issue)
    try:
        assert not orchestrator._has_live_owner_claim(issue.id, issue.project_id)
        assert orchestrator._should_dispatch(issue) is False
        assert orchestrator.state.reject_streak[issue.id][0] == (
            "internal_gate_blocked"
        )
    finally:
        _close(orchestrator)


def test_retire_preserves_blocked_row_when_tracker_shows_needs_ci_fix(tmp_path):
    """Blocked rows also survive Needs CI Fix, In Progress, Needs Human, etc."""
    issue = _issue(state=NEEDS_CI_FIX, integration_state="blocked")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        blocked = _blocked_row_for(orchestrator, project, issue)

        for tracker_state in (NEEDS_CI_FIX, NEEDS_REBASE, OPEN, "In Progress"):
            issue.state = tracker_state
            retired = orchestrator._retire_inactive_integration_rows(
                project.id,
                [issue],
                [
                    orchestrator.integration_queue.get(
                        project.id, issue.identifier
                    )
                ],
            )
            assert retired == 0, (
                f"blocked row was retired under tracker state {tracker_state!r}"
            )
            assert (
                orchestrator.integration_queue.get(
                    project.id, issue.identifier
                ).state
                == "blocked"
            )
    finally:
        _close(orchestrator)


@pytest.mark.parametrize("terminal_state", [DONE, MERGED, ARCHIVED])
def test_retire_retires_blocked_row_when_task_is_terminal(tmp_path, terminal_state):
    """Terminal tracker state authorises retiring the blocked row."""
    issue = _issue(state=NEEDS_CI_FIX, integration_state="blocked")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        blocked = _blocked_row_for(orchestrator, project, issue)
        issue.state = terminal_state
        retired = orchestrator._retire_inactive_integration_rows(
            project.id,
            [issue],
            [blocked],
        )
        assert retired == 1
        assert (
            orchestrator.integration_queue.get(
                project.id, issue.identifier
            ).state
            == "cancelled"
        )
    finally:
        _close(orchestrator)


def test_retire_retires_blocked_row_when_tracker_head_moved_past(tmp_path):
    """A newer head on the tracker means the blocked row is superseded."""
    issue = _issue(state=NEEDS_CI_FIX, integration_state="blocked")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        blocked = _blocked_row_for(orchestrator, project, issue)

        # A fresh submission recorded a newer head on the tracker record while
        # the task is back in Open (a new implementation attempt is queued).
        issue.state = OPEN
        issue.integration = IntegrationRecord(
            state="ready",
            task_branch=blocked.task_branch,
            head_sha="b" * 40,
        )

        retired = orchestrator._retire_inactive_integration_rows(
            project.id,
            [issue],
            [blocked],
        )

        # The head divergence AND non-READY_TO_INTEGRATE tracker state make
        # the stale blocked generation retirable.
        assert retired == 1
        assert (
            orchestrator.integration_queue.get(
                project.id, issue.identifier
            ).state
            == "cancelled"
        )
    finally:
        _close(orchestrator)


def test_retire_still_cancels_ready_row_when_tracker_shows_open(tmp_path):
    """OOMPAH-657 regression: non-blocked (ready/integrating) rows still retire."""
    issue = _issue(state=OPEN, integration_state="ready")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        row = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert row is not None and row.state == "ready"

        retired = orchestrator._retire_inactive_integration_rows(
            project.id,
            [issue],
            [row],
        )

        assert retired == 1
        assert (
            orchestrator.integration_queue.get(project.id, issue.identifier).state
            == "cancelled"
        )
    finally:
        _close(orchestrator)


def test_retire_leaves_blocked_row_when_tracker_issue_absent(tmp_path):
    """When the tracker issue is missing entirely, retire the row (stale ref)."""
    issue = _issue(state=NEEDS_CI_FIX, integration_state="blocked")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        blocked = _blocked_row_for(orchestrator, project, issue)

        # The tracker no longer reports this task at all — treat as retirable
        # so stale references don't accumulate indefinitely.
        retired = orchestrator._retire_inactive_integration_rows(
            project.id,
            [],  # no issues at all
            [blocked],
        )
        assert retired == 1
    finally:
        _close(orchestrator)


def test_repair_submission_rearms_the_same_head_via_explicit_retry(tmp_path):
    """OOMPAH-806: an explicit retry with the same head rearms exactly once.

    Ensures the CI/CD boundary: a resubmission via ``oompah task submit``
    (which sets ``explicit_retry=True``) may reopen the blocked row exactly
    once, without racing the retirement logic.
    """
    issue = _issue(state=NEEDS_CI_FIX, integration_state="blocked")
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        blocked = _blocked_row_for(orchestrator, project, issue)
        first_head = blocked.head_sha

        # Explicit retry with SAME head must rearm to ready exactly once.
        rearmed = orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id=issue.parent_id or "EPIC-1",
            task_id=issue.identifier,
            task_branch=blocked.task_branch,
            head_sha=first_head,
            explicit_retry=True,
        )
        assert rearmed.state == "ready"
        assert rearmed.retry_forced is True

        # A second identical resubmission without explicit_retry is idempotent
        # — must not reset state (which is now "ready").
        again = orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id=issue.parent_id or "EPIC-1",
            task_id=issue.identifier,
            task_branch=blocked.task_branch,
            head_sha=first_head,
        )
        assert again.state == "ready"
        assert (
            orchestrator.integration_queue.get(project.id, issue.identifier).state
            == "ready"
        )
    finally:
        _close(orchestrator)
