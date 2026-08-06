"""Regression coverage for integration delivery recovery and authority fences."""

from __future__ import annotations

from dataclasses import replace
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import shlex
import subprocess
import threading
import time
from unittest import mock

import pytest

from oompah.config import ServiceConfig
from oompah.container_cycle_repair import (
    ChildRepairResult,
    ContainerCycleRepairPlan,
    ContainerCycleRepairResult,
    CycleRepairRow,
)
from oompah.dependency_graph import issue_index
from oompah.integration import IntegrationRecord
from oompah.integration_executor import IntegrationExecutionResult
from oompah.models import BlockerRef, Issue, Project, RunningEntry
from oompah.orchestrator import Orchestrator
from oompah.quality_gate import BranchQualityGate, QualityGateOwner
from oompah.statuses import (
    ARCHIVED,
    DONE,
    MERGED,
    NEEDS_CI_FIX,
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
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import METADATA_KEY, TerminalAuditMetadata
from oompah.terminal_transition_coordinator import TransitionResult


class _IntegratedAuditTracker:
    """Stateful tracker used across the real coordinator/orchestrator boundary."""

    def __init__(self, issue: Issue) -> None:
        self.issue = issue
        self.metadata: dict[str, dict[str, object]] = {}
        self._lock = threading.RLock()
        self.fetch_count = 0
        self.block_initial_fetch = False
        self.initial_fetch_entered = threading.Event()
        self.release_initial_fetch = threading.Event()
        self.fail_status_updates = False

    def fetch_issue_detail(self, identifier: str):
        with self._lock:
            self.fetch_count += 1
            should_block = self.block_initial_fetch and self.fetch_count == 1
            snapshot = copy.deepcopy(self.issue) if should_block else self.issue
        if should_block:
            self.initial_fetch_entered.set()
            if not self.release_initial_fetch.wait(timeout=5):
                raise TimeoutError("initial integrated-audit fetch was not released")
        return snapshot if identifier == self.issue.identifier else None

    def fetch_issues_by_states(self, _states):
        return [self.issue]

    def fetch_all_issues(self):
        return [self.issue]

    def get_metadata(self, identifier: str):
        with self._lock:
            return copy.deepcopy(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: object):
        with self._lock:
            self.metadata.setdefault(identifier, {})[key] = copy.deepcopy(value)

    def update_issue(self, identifier: str, **kwargs):
        assert identifier == self.issue.identifier
        if "status" in kwargs:
            if self.fail_status_updates:
                raise RuntimeError("tracker status writes unavailable")
            self.issue.state = kwargs["status"]

    def add_comment(self, _identifier: str, _text: str, author: str = "oompah"):
        return {"author": author}


class _BlockingAlertList(list[dict[str, object]]):
    """Pause one named writer while it iterates a stale alert snapshot."""

    def __init__(
        self,
        rows: list[dict[str, object]],
        entered: threading.Event,
        release: threading.Event,
    ) -> None:
        super().__init__(rows)
        self.entered = entered
        self.release = release
        self.blocked = False

    def __iter__(self):
        if threading.current_thread().name == "health-alert-writer" and not self.blocked:
            self.blocked = True
            self.entered.set()
            if not self.release.wait(timeout=5):
                raise TimeoutError("health alert writer was not released")
        return super().__iter__()


class _ObservedAlertLock:
    """Expose when the clear thread starts waiting on the alert mutex."""

    def __init__(self, clear_attempted: threading.Event) -> None:
        self._lock = threading.RLock()
        self.clear_attempted = clear_attempted

    def __enter__(self):
        if threading.current_thread().name == "integrated-alert-clear":
            self.clear_attempted.set()
        self._lock.acquire()
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self._lock.release()


def _make_real_audit_harness(tmp_path, issue: Issue, tracker: _IntegratedAuditTracker):
    project = Project(
        id="proj-1",
        name="Recovery project",
        repo_url="https://github.com/org/repo.git",
        repo_path=str(tmp_path / "repo"),
        default_branch="main",
        tracker_owner="project-owner",
        status_label_authorized_logins=["project-owner"],
    )
    project_store = mock.MagicMock()
    project_store.list_all.return_value = [project]
    project_store.get.side_effect = lambda project_id: (
        project if project_id == project.id else None
    )
    project_lock = threading.RLock()
    project_store.project_write_lock.side_effect = lambda _project_id: project_lock
    orchestrator = Orchestrator(
        config=ServiceConfig(),
        workflow_path=str(tmp_path / "WORKFLOW.md"),
        project_store=project_store,
        state_path=str(tmp_path / "real-service-state.json"),
    )
    orchestrator._project_trackers[project.id] = tracker
    return orchestrator, project


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


def _completed_integrated_audit_metadata(
    issue: Issue,
    project_id: str,
    classification: FailureClassification,
) -> dict[str, object]:
    fingerprint = compute_issue_evidence_fingerprint(issue, project_id)
    attempt = AuditAttempt(
        attempt_id="attempt-integrated-recovery",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        verdict="fail",
        failure_classification=classification,
        requested_by=ContributorIdentity("auditor", "service"),
        completed_at="2026-08-06T00:01:00Z",
    )
    record = TerminalAuditRecord(
        audit_id="audit-integrated-completed",
        project_id=project_id,
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[attempt],
        requested_by=ContributorIdentity("integration", "service"),
        previous_state="Ready to Integrate",
        created_at="2026-08-06T00:00:00Z",
    )
    return {METADATA_KEY: TerminalAuditMetadata(pending_chain=[record]).to_dict()}


def _close(orchestrator: Orchestrator) -> None:
    orchestrator.integration_queue.close()
    orchestrator.coordination_store.close()
    orchestrator.task_transition_journal.close()
    orchestrator._tick_pool.shutdown(wait=True, cancel_futures=True)
    orchestrator._refresh_pool.shutdown(wait=True, cancel_futures=True)


def test_integrated_audit_failure_arms_one_recovery_alert_without_warning_loop(tmp_path):
    issue = _issue(state="Needs Human", integration_state="integrated")
    issue.integration = replace(issue.integration, integrated_sha="c" * 40)
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
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
        assert alerts[0]["recovery_action"] == "audit_override"
        assert "audit_override=true" in alerts[0]["message"]
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


@pytest.mark.parametrize(
    ("classification", "expected_action"),
    [
        (FailureClassification.NO_AUDITOR, "audit_retry"),
        (
            FailureClassification.MISSING_EVIDENCE,
            "audit_retry_evidence_addendum",
        ),
    ],
)
def test_integrated_recovery_alert_matches_completed_failure_action(
    tmp_path,
    classification: FailureClassification,
    expected_action: str,
):
    """An integrated replay never advertises an ineligible retry contract."""

    issue = _issue(state="Needs Human", integration_state="integrated")
    issue.integration = replace(issue.integration, integrated_sha="d" * 40)
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    tracker.get_metadata.return_value = _completed_integrated_audit_metadata(
        issue, project.id, classification
    )
    try:
        _row = orchestrator.integration_queue.enqueue(
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

        alert = next(
            alert
            for alert in orchestrator._alerts
            if alert.get("source") == "terminal_audit_recovery:proj-1:TASK-1"
        )
        assert alert["recovery_action"] == expected_action
        if expected_action == "audit_retry":
            assert "audit_retry=true" in alert["message"]
            assert "audit_retry_evidence_addendum" not in alert["message"]
        else:
            fingerprint = compute_issue_evidence_fingerprint(issue, project.id)
            assert "audit_retry_evidence_addendum" in alert["message"]
            assert fingerprint.digest in alert["message"]
    finally:
        _close(orchestrator)


def test_concurrent_owner_terminal_commit_cannot_be_followed_by_stale_alert(
    tmp_path,
):
    """The real coordinator and staging path share one project CAS lock."""

    issue = _issue(state="Needs Human", integration_state="integrated")
    issue.integration = replace(issue.integration, integrated_sha="e" * 40)
    tracker = _IntegratedAuditTracker(issue)
    tracker.metadata[issue.identifier] = _completed_integrated_audit_metadata(
        issue,
        "proj-1",
        FailureClassification.NO_AUDITOR,
    )
    orchestrator, project = _make_real_audit_harness(tmp_path, issue, tracker)
    tracker.block_initial_fetch = True
    item = orchestrator.integration_queue.enqueue(
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
    fingerprint = compute_issue_evidence_fingerprint(issue, project.id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        staging = pool.submit(
            asyncio.run,
            orchestrator._stage_integrated_task_audit(claimed),
        )
        assert tracker.initial_fetch_entered.wait(timeout=5)

        def apply_override():
            return asyncio.run(
                orchestrator.terminal_transition_coordinator.override_transition(
                    current_issue=issue,
                    requested_target=TargetState.DONE,
                    authorized_actor=ContributorIdentity("project-owner", "api"),
                    project_id=project.id,
                    evidence_fingerprint=fingerprint,
                    reason="Owner verified the integrated revision.",
                    project=project,
                )
            )

        overriding = pool.submit(apply_override)
        override = overriding.result(timeout=5)
        assert issue.state == DONE
        tracker.release_initial_fetch.set()
        staging.result(timeout=5)

    try:
        assert override.success is True
        assert issue.state == DONE
        assert not any(
            alert.get("source") == "terminal_audit_recovery:proj-1:TASK-1"
            for alert in orchestrator._alerts
        )
    finally:
        _close(orchestrator)

    # Restart replay observes the real terminal tracker state before touching
    # metadata and therefore cannot recreate the warning.
    tracker.block_initial_fetch = False
    restarted, _project = _make_real_audit_harness(tmp_path, issue, tracker)
    try:
        asyncio.run(restarted._stage_integrated_task_audit(item))
        assert issue.state == DONE
        assert not any(
            alert.get("source") == "terminal_audit_recovery:proj-1:TASK-1"
            for alert in restarted._alerts
        )
    finally:
        _close(restarted)


def test_unknown_tracker_state_does_not_rearm_alert_after_terminal_commit(tmp_path):
    issue = _issue(state="Needs Human", integration_state="integrated")
    issue.integration = replace(issue.integration, integrated_sha="f" * 40)
    tracker = _IntegratedAuditTracker(issue)
    tracker.metadata[issue.identifier] = _completed_integrated_audit_metadata(
        issue,
        "proj-1",
        FailureClassification.NO_AUDITOR,
    )
    orchestrator, project = _make_real_audit_harness(tmp_path, issue, tracker)
    fingerprint = compute_issue_evidence_fingerprint(issue, project.id)
    orchestrator._arm_integrated_audit_recovery_alert(
        project.id,
        issue.identifier,
        DONE,
        "auditor capacity exhausted",
        issue.integration.integrated_sha,
        recovery_action="audit_retry",
        evidence_fingerprint=fingerprint,
    )

    try:
        override = asyncio.run(
            orchestrator.terminal_transition_coordinator.override_transition(
                current_issue=issue,
                requested_target=TargetState.DONE,
                authorized_actor=ContributorIdentity("project-owner", "api"),
                project_id=project.id,
                evidence_fingerprint=fingerprint,
                reason="Owner verified the integrated revision.",
                project=project,
            )
        )
        assert override.success is True
        assert issue.state == DONE
        assert not any(
            alert.get("source") == "terminal_audit_recovery:proj-1:TASK-1"
            for alert in orchestrator._alerts_snapshot()
        )

        with mock.patch.object(
            tracker,
            "fetch_issue_detail",
            side_effect=RuntimeError("tracker read unavailable"),
        ):
            changed = orchestrator._reconcile_integrated_audit_recovery_alert(
                project.id,
                issue.identifier,
                DONE,
                "stale staging failure",
                issue.integration.integrated_sha,
                fingerprint,
            )

        assert changed is False
        assert not any(
            alert.get("source") == "terminal_audit_recovery:proj-1:TASK-1"
            for alert in orchestrator._alerts_snapshot()
        )
    finally:
        _close(orchestrator)


@pytest.mark.parametrize(
    "detail_mutation",
    ("missing", "malformed", "identifier", "project"),
)
def test_untrusted_tracker_detail_cannot_clear_integrated_recovery_alert(
    tmp_path,
    detail_mutation: str,
):
    """Only the exact requested task scope can retire its recovery warning."""

    issue = _issue(state="Needs Human", integration_state="integrated")
    issue.integration = replace(issue.integration, integrated_sha="1" * 40)
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    fingerprint = compute_issue_evidence_fingerprint(issue, project.id)
    orchestrator._arm_integrated_audit_recovery_alert(
        project.id,
        issue.identifier,
        DONE,
        "auditor capacity exhausted",
        issue.integration.integrated_sha,
        recovery_action="audit_retry",
        evidence_fingerprint=fingerprint,
    )
    before = orchestrator._alerts_snapshot()
    if detail_mutation == "missing":
        untrusted = None
    elif detail_mutation == "malformed":
        untrusted = object()
    else:
        mismatched = copy.deepcopy(issue)
        mismatched.state = DONE
        if detail_mutation == "identifier":
            mismatched.identifier = "TASK-OTHER"
        else:
            mismatched.project_id = "proj-other"
        untrusted = mismatched
    tracker.fetch_issue_detail.return_value = untrusted

    try:
        changed = orchestrator._reconcile_integrated_audit_recovery_alert(
            project.id,
            issue.identifier,
            DONE,
            "stale staging failure",
            issue.integration.integrated_sha,
            fingerprint,
        )

        assert changed is False
        assert orchestrator._alerts_snapshot() == before
    finally:
        _close(orchestrator)


def test_integrated_replay_retains_retry_alert_while_status_staging_keeps_failing(
    tmp_path,
):
    """A durable owner rearm cannot make its warning disappear before staging."""

    issue = _issue(state="Needs Human", integration_state="integrated")
    issue.integration = replace(issue.integration, integrated_sha="2" * 40)
    tracker = _IntegratedAuditTracker(issue)
    tracker.metadata[issue.identifier] = _completed_integrated_audit_metadata(
        issue,
        "proj-1",
        FailureClassification.NO_AUDITOR,
    )
    tracker.fail_status_updates = True
    orchestrator, project = _make_real_audit_harness(tmp_path, issue, tracker)
    item = orchestrator.integration_queue.enqueue(
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
    fingerprint = compute_issue_evidence_fingerprint(issue, project.id)
    orchestrator._arm_integrated_audit_recovery_alert(
        project.id,
        issue.identifier,
        DONE,
        "auditor capacity exhausted",
        issue.integration.integrated_sha,
        recovery_action="audit_retry",
        evidence_fingerprint=fingerprint,
    )

    try:
        retry = asyncio.run(
            orchestrator.terminal_transition_coordinator.retry_failed_audit(
                current_issue=issue,
                requested_target=TargetState.DONE,
                authorized_actor=ContributorIdentity("project-owner", "api"),
                project_id=project.id,
                reason="Independent auditor capacity restored.",
                project=project,
                evidence_fingerprint=fingerprint,
            )
        )
        assert retry.success is False
        assert retry.reason == "status_stage_failed"

        # Periodic integrated replay repeatedly coalesces the durable pending
        # audit, and repeatedly fails the same tracker write.  Neither pass may
        # reinterpret or clear the accepted owner retry instruction.
        asyncio.run(orchestrator._stage_integrated_task_audit(item))
        asyncio.run(orchestrator._stage_integrated_task_audit(item))

        alerts = [
            alert
            for alert in orchestrator._alerts_snapshot()
            if alert.get("source")
            == "terminal_audit_recovery:proj-1:TASK-1"
        ]
        assert len(alerts) == 1
        assert alerts[0]["recovery_action"] == "audit_retry"
        assert issue.state == "Needs Human"
        stored = TerminalAuditMetadata.from_dict(
            tracker.metadata[issue.identifier][METADATA_KEY]
        )
        assert stored.pending_chain[-1].request_state == RequestState.PENDING
        intents = stored.unknown_fields["oompah.terminal_audit_result_intents"]
        assert intents[-1]["kind"] == "audit_rearm"
        assert intents[-1]["applied"] is False
    finally:
        _close(orchestrator)


def test_alert_family_refresh_cannot_resurrect_concurrently_cleared_alert(tmp_path):
    issue = _issue(state="Needs Human", integration_state="integrated")
    orchestrator, _project, _tracker = _make_harness(tmp_path, issue)
    source = "terminal_audit_recovery:proj-1:TASK-1"
    writer_entered = threading.Event()
    release_writer = threading.Event()
    clear_attempted = threading.Event()
    clear_finished = threading.Event()
    errors: list[BaseException] = []
    orchestrator._alerts_lock = _ObservedAlertLock(clear_attempted)
    orchestrator._alerts = _BlockingAlertList(
        [{"level": "warning", "source": source, "message": "stale"}],
        writer_entered,
        release_writer,
    )

    def refresh_health_alerts() -> None:
        try:
            orchestrator._refresh_terminal_audit_health(
                [],
                scan_complete=True,
                scan_error_count=0,
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    def clear_integrated_alert() -> None:
        try:
            orchestrator._clear_integrated_audit_recovery_alert(
                "proj-1",
                "TASK-1",
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)
        finally:
            clear_finished.set()

    health_thread = threading.Thread(
        target=refresh_health_alerts,
        name="health-alert-writer",
    )
    clear_thread = threading.Thread(
        target=clear_integrated_alert,
        name="integrated-alert-clear",
    )
    health_started = False
    clear_started = False
    try:
        health_thread.start()
        health_started = True
        assert writer_entered.wait(timeout=5)
        clear_thread.start()
        clear_started = True
        assert clear_attempted.wait(timeout=5)
        assert not clear_finished.wait(timeout=0.05)
        release_writer.set()
        health_thread.join(timeout=5)
        clear_thread.join(timeout=5)

        assert not health_thread.is_alive()
        assert not clear_thread.is_alive()
        assert errors == []
        assert not any(
            alert.get("source") == source
            for alert in orchestrator._alerts_snapshot()
        )
    finally:
        release_writer.set()
        if health_started:
            health_thread.join(timeout=5)
        if clear_started:
            clear_thread.join(timeout=5)
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
    def execute_live_item(item, **_kwargs):
        # The real executor durably canonicalizes the rebased combined-tree
        # candidate before it returns success.  Model that contract here so
        # finalization sees the same queue/tracker generation it would in
        # production; bypassing it would correctly fail closed.
        assert orchestrator.integration_queue.record_candidate(
            project_id=item.project_id,
            task_id=item.task_id,
            lease_owner=item.lease_owner or "",
            expected_head_sha=item.head_sha,
            expected_candidate_head_sha=item.candidate_head_sha,
            candidate_head_sha="c" * 40,
            candidate_base_sha="b" * 40,
        ) is not None
        issue.integration = replace(
            issue.integration,
            head_sha="c" * 40,
            base_sha="b" * 40,
        )
        return IntegrationExecutionResult(
            status="integrated",
            message="integrated",
            expected_epic_sha="b" * 40,
            rebased_task_sha="c" * 40,
            integrated_sha="d" * 40,
        )

    orchestrator._execute_integration_item = mock.MagicMock(
        side_effect=execute_live_item
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


def test_restart_sync_restores_recorded_nested_target_authority(tmp_path):
    issue = _issue(integration_state="ready")
    issue.parent_id = "OOMPAH-804"
    issue.integration = replace(
        issue.integration,
        base_branch="epic-OOMPAH-768--task-OOMPAH-804",
        base_sha="b" * 40,
    )
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator._sync_ready_integration_submissions()

        row = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert row is not None
        assert row.epic_id == "OOMPAH-804"
        assert row.base_branch == "epic-OOMPAH-768--task-OOMPAH-804"
        assert row.base_sha == "b" * 40
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


def test_changed_base_sha_revokes_executor_authority(tmp_path):
    issue = _issue(integration_state="ready")
    issue.integration = replace(
        issue.integration,
        base_branch="epic-EPIC-1",
        base_sha="b" * 40,
    )
    orchestrator, project, _tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
            base_branch=issue.integration.base_branch,
            base_sha=issue.integration.base_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="base-generation",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert orchestrator._integration_task_still_ready(claimed)

        issue.integration = replace(issue.integration, base_sha="c" * 40)

        assert not orchestrator._integration_task_still_ready(claimed)
    finally:
        _close(orchestrator)


def test_candidate_head_atomically_rebinds_queue_tracker_and_gate_owner(tmp_path):
    issue = _issue(integration_state="ready")
    issue.integration = replace(
        issue.integration,
        base_branch="epic-OOMPAH-768--task-OOMPAH-804",
    )
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="OOMPAH-804",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
            base_branch=issue.integration.base_branch,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="OOMPAH-804",
            lease_owner="candidate-generation",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None

        def persist(_identifier, _field, value):
            issue.integration = IntegrationRecord.from_dict(value)

        tracker.set_metadata_field.side_effect = persist
        authority = orchestrator._canonicalize_integration_candidate(
            claimed,
            "b" * 40,
            "c" * 40,
        )

        current = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert current is not None
        assert current.head_sha == "a" * 40
        assert current.candidate_head_sha == "b" * 40
        assert current.candidate_base_sha == "c" * 40
        assert issue.integration.head_sha == "b" * 40
        assert authority.owner is not None
        assert authority.owner.head_sha == "b" * 40
        assert "b" * 40 in str(authority.generation)
        assert authority.is_current is not None and authority.is_current()
    finally:
        _close(orchestrator)


def test_candidate_rebind_cannot_overwrite_waiting_new_submission(tmp_path):
    issue = _issue(integration_state="ready")
    issue.integration = replace(
        issue.integration,
        base_branch="epic-EPIC-1",
        base_sha="a" * 40,
    )
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    stale_write_started = threading.Event()
    replacement_waiting = threading.Event()
    replacement_done = threading.Event()
    replacement = IntegrationRecord(
        state="ready",
        task_branch=issue.integration.task_branch,
        base_branch=issue.integration.base_branch,
        base_sha="d" * 40,
        head_sha="e" * 40,
    )
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
            base_branch=issue.integration.base_branch,
            base_sha=issue.integration.base_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="stale-candidate",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None

        def persist_candidate(_identifier, _field, value):
            stale_write_started.set()
            assert replacement_waiting.wait(timeout=5)
            assert not replacement_done.is_set()
            issue.integration = IntegrationRecord.from_dict(value)

        tracker.set_metadata_field.side_effect = persist_candidate

        def fetch_current(_identifier):
            if stale_write_started.is_set() and replacement_waiting.is_set():
                assert replacement_done.wait(timeout=5)
            return issue

        tracker.fetch_issue_detail.side_effect = fetch_current

        def submit_replacement() -> None:
            assert stale_write_started.wait(timeout=5)
            replacement_waiting.set()
            with orchestrator.issue_transition_lock(issue.id).sync():
                orchestrator.integration_queue.enqueue(
                    project_id=project.id,
                    epic_id="EPIC-1",
                    task_id=issue.identifier,
                    task_branch=replacement.task_branch,
                    head_sha=replacement.head_sha,
                    base_branch=replacement.base_branch,
                    base_sha=replacement.base_sha,
                )
                issue.integration = replacement
            replacement_done.set()

        contender = threading.Thread(target=submit_replacement)
        contender.start()
        with pytest.raises(RuntimeError, match="did not persist atomically"):
            orchestrator._canonicalize_integration_candidate(
                claimed,
                "b" * 40,
                "c" * 40,
            )
        contender.join(timeout=5)

        assert not contender.is_alive()
        assert issue.integration == replacement
        current = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert current is not None
        assert current.head_sha == replacement.head_sha
        assert current.base_sha == replacement.base_sha
    finally:
        _close(orchestrator)


def test_success_finalization_cas_preserves_replacement_generation(tmp_path):
    issue = _issue(integration_state="ready")
    issue.integration = replace(
        issue.integration,
        base_branch="epic-EPIC-1",
        base_sha="a" * 40,
    )
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
            base_branch=issue.integration.base_branch,
            base_sha=issue.integration.base_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="stale-finalizer",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None
        issue.integration = replace(
            issue.integration,
            head_sha="b" * 40,
            base_sha="c" * 40,
        )
        assert orchestrator.integration_queue.record_candidate(
            project_id=project.id,
            task_id=issue.identifier,
            lease_owner="stale-finalizer",
            expected_head_sha=claimed.head_sha,
            candidate_head_sha="b" * 40,
            candidate_base_sha="c" * 40,
        ) is not None
        replacement = replace(
            issue.integration,
            head_sha="e" * 40,
            base_sha="d" * 40,
        )
        original_complete = orchestrator.integration_queue.complete

        def replace_before_cas(project_id, task_id, *, lease_owner):
            orchestrator.integration_queue.enqueue(
                project_id=project.id,
                epic_id="EPIC-1",
                task_id=issue.identifier,
                task_branch=replacement.task_branch,
                head_sha=replacement.head_sha,
                base_branch=replacement.base_branch,
                base_sha=replacement.base_sha,
            )
            issue.integration = replacement
            return original_complete(
                project_id,
                task_id,
                lease_owner=lease_owner,
            )

        tracker.set_metadata_field.reset_mock()
        with mock.patch.object(
            orchestrator.integration_queue,
            "complete",
            side_effect=replace_before_cas,
        ):
            finalized = orchestrator._finalize_integration_success(
                claimed,
                IntegrationExecutionResult(
                    status="integrated",
                    message="landed",
                    expected_epic_sha="c" * 40,
                    rebased_task_sha="b" * 40,
                    integrated_sha="b" * 40,
                ),
                epic_id="EPIC-1",
                lease_owner="stale-finalizer",
                dependency_heads={},
                expected_dependencies=None,
                expected_dependency_revision=None,
            )

        assert finalized is None
        tracker.set_metadata_field.assert_not_called()
        assert issue.integration == replacement
        current = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert current is not None
        assert current.head_sha == replacement.head_sha
        assert current.state == "ready"
    finally:
        _close(orchestrator)


def test_success_finalization_persists_exact_candidate_generation(tmp_path):
    issue = _issue(integration_state="ready")
    issue.integration = replace(
        issue.integration,
        base_branch="epic-EPIC-1",
        base_sha="a" * 40,
    )
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
            base_branch=issue.integration.base_branch,
            base_sha=issue.integration.base_sha,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="successful-finalizer",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None
        issue.integration = replace(
            issue.integration,
            head_sha="b" * 40,
            base_sha="c" * 40,
        )
        assert orchestrator.integration_queue.record_candidate(
            project_id=project.id,
            task_id=issue.identifier,
            lease_owner="successful-finalizer",
            expected_head_sha=claimed.head_sha,
            candidate_head_sha="b" * 40,
            candidate_base_sha="c" * 40,
        ) is not None

        def persist(_identifier, _field, value):
            issue.integration = IntegrationRecord.from_dict(value)

        tracker.set_metadata_field.side_effect = persist
        finalized = orchestrator._finalize_integration_success(
            claimed,
            IntegrationExecutionResult(
                status="integrated",
                message="landed",
                expected_epic_sha="c" * 40,
                rebased_task_sha="b" * 40,
                integrated_sha="f" * 40,
            ),
            epic_id="EPIC-1",
            lease_owner="successful-finalizer",
            dependency_heads={"UPSTREAM": "9" * 40},
            expected_dependencies=None,
            expected_dependency_revision=None,
        )

        assert finalized is not None
        assert finalized.state == "integrated"
        assert issue.integration.state == "integrated"
        assert issue.integration.head_sha == "b" * 40
        assert issue.integration.base_sha == "c" * 40
        assert issue.integration.integrated_sha == "f" * 40
        assert issue.integration.dependency_heads == {"UPSTREAM": "9" * 40}
    finally:
        _close(orchestrator)


def test_tracker_finalization_failure_rearms_integrated_queue_row(tmp_path):
    issue = _issue(integration_state="ready")
    issue.integration = replace(
        issue.integration,
        base_branch="epic-EPIC-1",
        base_sha="a" * 40,
        head_sha="b" * 40,
    )
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id="EPIC-1",
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha="a" * 40,
            base_branch=issue.integration.base_branch,
            base_sha="9" * 40,
        )
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="tracker-failure",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert orchestrator.integration_queue.record_candidate(
            project_id=project.id,
            task_id=issue.identifier,
            lease_owner="tracker-failure",
            expected_head_sha=claimed.head_sha,
            candidate_head_sha="b" * 40,
            candidate_base_sha="a" * 40,
        ) is not None
        tracker.set_metadata_field.side_effect = RuntimeError("tracker offline")

        finalized = orchestrator._finalize_integration_success(
            claimed,
            IntegrationExecutionResult(
                status="integrated",
                message="landed",
                expected_epic_sha="a" * 40,
                rebased_task_sha="b" * 40,
                integrated_sha="f" * 40,
            ),
            epic_id="EPIC-1",
            lease_owner="tracker-failure",
            dependency_heads={},
            expected_dependencies=None,
            expected_dependency_revision=None,
        )

        assert finalized is None
        current = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert current is not None
        assert current.state == "ready"
        assert current.attempts == 0
        assert current.candidate_head_sha == "b" * 40
        assert "tracker integration finalization failed" in (
            current.last_error or ""
        )
        assert issue.integration.state == "ready"
        assert orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id="EPIC-1",
            lease_owner="tracker-retry",
            dependency_map={issue.identifier: ()},
            satisfied=set(),
            max_attempts=1,
        ) is not None
    finally:
        _close(orchestrator)


def _cycle_restore_case(tmp_path):
    issue = _issue(state="Needs Human", integration_state="ready")
    issue.integration = replace(
        issue.integration,
        task_branch="task/TASK-1",
        base_branch="epic-ROOT--task-CHILD",
        base_sha="2" * 40,
        head_sha="b" * 40,
    )
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    orchestrator.integration_queue.enqueue(
        project_id=project.id,
        epic_id="CHILD",
        task_id=issue.identifier,
        task_branch=issue.integration.task_branch,
        head_sha="a" * 40,
        base_branch=issue.integration.base_branch,
        base_sha="1" * 40,
    )
    claimed = orchestrator.integration_queue.claim_next(
        project_id=project.id,
        epic_id="CHILD",
        lease_owner="cycle-generation",
        dependency_map={issue.identifier: ()},
        satisfied=set(),
    )
    assert claimed is not None
    assert orchestrator.integration_queue.record_candidate(
        project_id=project.id,
        task_id=issue.identifier,
        lease_owner="cycle-generation",
        expected_head_sha="a" * 40,
        candidate_head_sha="b" * 40,
        candidate_base_sha="2" * 40,
    ) is not None
    assert orchestrator.integration_queue.cancel(
        project.id,
        issue.identifier,
        reason="cycle fence",
        expected_head_sha="a" * 40,
        expected_state="integrating",
    )
    row = CycleRepairRow(
        task_id=issue.identifier,
        container_id="CHILD",
        epic_id="CHILD",
        task_branch=issue.integration.task_branch,
        head_sha="b" * 40,
        submission_head_sha="a" * 40,
        base_branch=issue.integration.base_branch,
    )
    plan = ContainerCycleRepairPlan(
        key="cycle-restore",
        authoritative_container="PARENT",
        dependent_containers=("CHILD",),
        prerequisite_shas=(("UPSTREAM", "c" * 40),),
        rows=(row,),
        container_branches=(("CHILD", issue.integration.base_branch),),
    )
    result = ContainerCycleRepairResult(
        status="ready_for_queue_restore",
        phase="children_synchronized",
        parent_branch="epic-PARENT",
        parent_sha="c" * 40,
        children=[
            ChildRepairResult(
                container_id="CHILD",
                branch=issue.integration.base_branch,
                expected_sha="3" * 40,
                resulting_sha="d" * 40,
                action="merge_parent",
            )
        ],
        restorable_rows=(issue.identifier,),
    )
    executor = mock.MagicMock()
    executor.remote_head.return_value = "b" * 40
    return orchestrator, project, tracker, issue, plan, result, executor


def test_cycle_restore_uses_exact_child_tip_in_queue_and_tracker(tmp_path):
    values = _cycle_restore_case(tmp_path)
    orchestrator, project, tracker, issue, plan, result, executor = values
    try:
        tracker.set_metadata_field.side_effect = (
            lambda _identifier, _field, value: setattr(
                issue,
                "integration",
                IntegrationRecord.from_dict(value),
            )
        )
        tracker.update_issue.side_effect = (
            lambda _identifier, **fields: setattr(issue, "state", fields["status"])
        )

        restored, changed = orchestrator._restore_container_cycle_rows(
            project.id,
            tracker,
            project,
            plan,
            result,
            executor,
        )

        assert restored == (issue.identifier,)
        assert changed == ()
        assert issue.integration.base_sha == "d" * 40
        assert issue.integration.base_sha != result.parent_sha
        current = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert current is not None
        assert current.base_branch == "epic-ROOT--task-CHILD"
        assert current.base_sha == "d" * 40
        assert current.candidate_base_sha == "d" * 40
    finally:
        _close(orchestrator)


def test_cycle_restore_tracker_failure_rolls_queue_back_to_cancelled(tmp_path):
    values = _cycle_restore_case(tmp_path)
    orchestrator, project, tracker, issue, plan, result, executor = values
    try:
        tracker.set_metadata_field.side_effect = RuntimeError("tracker offline")

        with pytest.raises(RuntimeError, match="tracker offline"):
            orchestrator._restore_container_cycle_rows(
                project.id,
                tracker,
                project,
                plan,
                result,
                executor,
            )

        tracker.update_issue.assert_not_called()
        current = orchestrator.integration_queue.get(project.id, issue.identifier)
        assert current is not None
        assert current.state == "cancelled"
        assert current.head_sha == "a" * 40
        assert current.candidate_head_sha == "b" * 40
    finally:
        _close(orchestrator)


def test_gate_authority_revokes_when_normalized_dependency_evidence_changes(
    tmp_path,
):
    issue = _issue(integration_state="ready")
    issue.parent_id = "EPIC-1"
    parent = Issue(
        id="epic-native",
        identifier="EPIC-1",
        title="Parent",
        project_id="proj-1",
        blocked_by=[BlockerRef(identifier="EXTERNAL")],
    )
    external = Issue(
        id="external-native",
        identifier="EXTERNAL",
        title="External prerequisite",
        project_id="proj-1",
        state=DONE,
        integration=IntegrationRecord(
            state="integrated",
            head_sha="e" * 40,
            integrated_sha="e" * 40,
        ),
    )
    orchestrator, project, tracker = _make_harness(tmp_path, issue)
    issues = [parent, issue, external]
    tracker.fetch_all_issues.return_value = issues
    try:
        orchestrator.integration_queue.enqueue(
            project_id=project.id,
            epic_id=parent.identifier,
            task_id=issue.identifier,
            task_branch=issue.integration.task_branch,
            head_sha=issue.integration.head_sha,
        )
        dependencies = orchestrator._integration_dependency_map(
            issues,
            orchestrator.integration_queue.items(project_id=project.id),
        )[issue.identifier]
        claimed = orchestrator.integration_queue.claim_next(
            project_id=project.id,
            epic_id=parent.identifier,
            lease_owner="dependency-authority",
            dependency_map={issue.identifier: dependencies},
            satisfied={external.identifier},
        )
        assert claimed is not None
        authority = orchestrator._integration_dependency_authority(
            claimed,
            dependencies,
            orchestrator._integration_dependency_revision(
                issue_index(issues),
                dependencies,
            ),
        )

        assert authority()
        external.state = OPEN
        # A second check in the same scheduling interval must observe the
        # change; authority evidence is never served from a time cache.
        assert not authority()
        external.state = DONE
        external.integration = replace(
            external.integration,
            base_sha="f" * 40,
        )
        assert not authority()
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
