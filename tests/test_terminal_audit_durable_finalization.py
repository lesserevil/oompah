"""End-to-end restart coverage for durable terminal-audit finalization."""

from __future__ import annotations

import asyncio
import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oompah.auditor_dispatch import AuditorDispatchLane
from oompah.models import Issue
from oompah.orchestrator import Orchestrator, _AuditCandidateScan
from oompah.roles import Candidate
from oompah.statuses import (
    DONE,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_HUMAN,
    OPEN,
)
from oompah.terminal_audit import (
    AuditAttempt,
    AuditAttemptOrigin,
    ContributorIdentity,
    EvidenceFingerprint,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadataStore
from oompah.terminal_audit_enforcement import TerminalAuditEnforcement
from oompah.terminal_audit_workflow import (
    AuditWorkflowIdentityError,
    TerminalAuditWorkflow,
)
from oompah.terminal_transition_coordinator import (
    AuditResult,
    ResultOutcome,
    ResultRejection,
    TerminalTransitionCoordinator,
)
from oompah.workflow_jobs import WorkflowJobState, WorkflowJobStore
from oompah.workflow_jobs import WorkflowFailureCategory
from oompah.workflow_controller import UniversalTotalityLivenessController
from oompah.workflow_runtime import WorkflowRuntime


PROJECT_ID = "proj-durable"
TASK_ID = "TASK-1"
SELECTED_REF = "refs/heads/review/TASK-1"
SELECTED_SHA = "a" * 40


class _ProjectLocks:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.worktrees: list[str] = []

    def project_write_lock(self, _project_id: str) -> threading.RLock:
        return self._lock

    def list_all(self) -> list[SimpleNamespace]:
        return [SimpleNamespace(id=PROJECT_ID)]

    def list_worktrees(self, _project_id: str) -> list[str]:
        return list(self.worktrees)


class _RevisionProjectLocks(_ProjectLocks):
    def get(self, _project_id: str) -> SimpleNamespace:
        return SimpleNamespace(default_branch="main")

    def resolve_audit_revision(self, _project_id: str, _revision: str) -> str:
        return SELECTED_SHA


class _Tracker:
    def __init__(self) -> None:
        self.metadata: dict[str, dict] = {}
        self.metadata_write_count = 0
        self.status = "In Review"
        self.cache_invalidations = 0
        self.fail_status_updates = False

    def invalidate_read_cache(self) -> None:
        self.cache_invalidations += 1

    def get_metadata(self, identifier: str) -> dict:
        return copy.deepcopy(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value) -> None:
        self.metadata_write_count += 1
        self.metadata.setdefault(identifier, {})[key] = copy.deepcopy(value)

    def update_issue(self, _identifier: str, **changes) -> None:
        if "status" in changes:
            if self.fail_status_updates:
                raise RuntimeError("tracker status writes unavailable")
            self.status = changes["status"]

    def add_comment(self, _identifier: str, _text: str, author: str = "oompah") -> dict:
        return {"author": author}

    def fetch_issue_detail(self, identifier: str) -> Issue:
        return Issue(
            id=identifier,
            identifier=identifier,
            title="Durable finalization",
            state=self.status,
            project_id=PROJECT_ID,
        )

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        return [self.fetch_issue_detail(identifier) for identifier in issue_ids]

    def fetch_all_issues_enriched(self) -> list[Issue]:
        return [self.fetch_issue_detail(TASK_ID)]


def _result(record, attempt_id: str) -> AuditResult:
    return AuditResult(
        audit_id=record.audit_id,
        target_state=record.target_state,
        evidence_fingerprint=record.evidence_fingerprint,
        verdict=Verdict.PASS,
        message="exact PASS",
        attempt_id=attempt_id,
    )


def _failed_result(
    record,
    attempt_id: str,
    *,
    classification: FailureClassification = FailureClassification.INCOMPLETE,
) -> AuditResult:
    return AuditResult(
        audit_id=record.audit_id,
        target_state=record.target_state,
        evidence_fingerprint=record.evidence_fingerprint,
        verdict=Verdict.FAIL,
        failure_classification=classification,
        message="exact substantive failure",
        attempt_id=attempt_id,
    )


def _test_audit_metrics(**overrides):
    metrics = {
        "dispatch_count": 0,
        "rotation_count": 0,
        "exhaustion_count": 0,
        "in_progress_count": 0,
        "last_error": None,
    }
    metrics.update(overrides)
    return metrics


def _orchestrator(
    tracker: _Tracker,
    coordinator: TerminalTransitionCoordinator,
    store: WorkflowJobStore,
    workflow: TerminalAuditWorkflow,
) -> Orchestrator:
    orchestrator = Orchestrator.__new__(Orchestrator)

    async def _prepare_audit_selector(issue, *, probe_missing=True):
        del probe_missing
        return orchestrator._audit_selector(issue, project=None), None

    orchestrator.workflow_job_store = store
    orchestrator.terminal_audit_workflow = workflow
    orchestrator.terminal_transition_coordinator = coordinator
    orchestrator.project_store = coordinator._project_store
    orchestrator._tick_pool = None
    orchestrator._audit_rollback_persistence_failed = False
    orchestrator._audit_rollback_lock = threading.RLock()
    orchestrator._pending_audit_rollbacks = {}
    orchestrator._maintenance_cursors = {}
    orchestrator._eligible_audit_stage_wakes = {}
    # The fixture bypasses Orchestrator.__init__, so model the service-state
    # transaction lock required by durable maintenance cursor updates.
    orchestrator._state_io_lock = threading.RLock()
    orchestrator._save_state = MagicMock(return_value=True)
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._reconcile_audit_budget_reservations = lambda: None
    orchestrator._reconcile_and_release_audit_budget = MagicMock(return_value=True)
    orchestrator._terminal_audit_manual_alerts = {}
    orchestrator._sync_terminal_audit_observability_alerts = MagicMock()
    orchestrator._refresh_terminal_audit_validation_configuration_alerts = MagicMock()
    orchestrator._terminal_audit_validation_configuration_error = MagicMock(
        return_value=None
    )
    orchestrator._prepare_audit_selector = _prepare_audit_selector
    orchestrator._revisionless_archive_evidence = MagicMock(return_value=None)
    orchestrator._bind_audit_record_revision = MagicMock(
        side_effect=lambda _issue, record: record
    )
    orchestrator._running_values_snapshot = lambda: []
    orchestrator._is_project_paused = MagicMock(return_value=False)
    orchestrator._tracker_for_project = lambda _project_id: tracker
    orchestrator._tracker_for_issue = lambda _issue: tracker
    orchestrator._record_audit_outcome_ownership = MagicMock()
    orchestrator._request_audit_lane_continuation = MagicMock(return_value=True)
    return orchestrator


def test_successor_wake_is_published_only_after_current_job_closes() -> None:
    orchestrator = Orchestrator.__new__(Orchestrator)
    calls: list[str] = []
    orchestrator._finish_terminal_audit_workflow = MagicMock(
        side_effect=lambda *_args: calls.append("closed") or True
    )
    orchestrator._record_audit_outcome_ownership = MagicMock(
        side_effect=lambda *_args: calls.append("owned")
    )
    orchestrator._request_next_audit_stage = MagicMock(
        side_effect=lambda **_kwargs: calls.append("wake") or True
    )
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="chained audit",
        state=IN_VALIDATION,
        project_id=PROJECT_ID,
    )
    outcome = ResultOutcome(
        success=True,
        audit_id="audit-done",
        applied_status=IN_VALIDATION,
        advanced_target=TargetState.MERGED,
        advanced_audit_id="audit-merged",
    )

    assert orchestrator._finish_and_wake_terminal_audit_workflow(
        issue, SimpleNamespace(), outcome, SimpleNamespace()
    )

    assert calls == ["closed", "owned", "wake"]
    orchestrator._request_next_audit_stage.assert_called_once_with(
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        audit_id="audit-merged",
    )


def test_done_pass_successor_converges_after_crash_before_wake(tmp_path) -> None:
    """Persisted eligibility makes the exact queued Merged job restart-safe."""

    tracker = _Tracker()
    locks = _RevisionProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID), PROJECT_ID
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.MERGED,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert staged.success
    assert tracker.status == IN_VALIDATION
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    done, merged = metadata.read(TASK_ID).pending_chain
    assert done.eligible_at == done.created_at
    assert merged.eligible_at is None
    assert merged.prerequisite_audit_id == done.audit_id

    db_path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(db_path)
    workflow = TerminalAuditWorkflow(store)
    merged_job = workflow.ensure(merged)
    attempt = AuditAttempt(
        attempt_id="attempt-done",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        provider_id="provider-a",
        model="model-a",
        selected_ref=done.selected_ref,
        selected_sha=done.selected_sha,
        landing_revision=done.landing_revision,
        created_at="2026-08-11T10:40:00+00:00",
        started_at="2026-08-11T10:40:00+00:00",
    )
    launched_done = replace(
        done,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
    )
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[launched_done, merged],
        ),
    )
    running = workflow.start(
        launched_done,
        attempt_id=attempt.attempt_id,
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    result = _result(launched_done, attempt.attempt_id)
    finalizing = workflow.mark_finalizing(
        running,
        launched_done,
        result=result,
        attempt_id=attempt.attempt_id,
        lease_token=running.lease_token,
    )
    outcome = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            result,
            PROJECT_ID,
        )
    )
    assert outcome.success
    assert outcome.advanced_target is TargetState.MERGED
    assert outcome.advanced_audit_id == merged.audit_id
    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    assert orchestrator._finish_terminal_audit_workflow(
        tracker.fetch_issue_detail(TASK_ID),
        result,
        outcome,
        finalizing,
    )
    eligible_merged = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == merged.audit_id
    )
    assert eligible_merged.eligible_at is not None
    assert store.get(merged_job.job_id).attempts == 0
    store.close()

    # Simulate death after result/job completion but before the in-memory
    # successor wake.  Startup metadata recovery reconstructs that exact hint
    # and the pre-existing semantic job remains the claim target.
    reopened_store = WorkflowJobStore(db_path)
    reopened_workflow = TerminalAuditWorkflow(reopened_store)
    enforcement = TerminalAuditEnforcement(
        str(tmp_path / "service-state.json"),
        terminal_states=(DONE, MERGED, "Archived"),
        project_store=locks,
    )
    enforcement.recover_pending_audits([(PROJECT_ID, tracker)])
    restarted = _orchestrator(
        tracker,
        coordinator,
        reopened_store,
        reopened_workflow,
    )
    restarted._terminal_audit_enforcement = enforcement
    restarted._maintenance_status = {}
    restarted._eligible_audit_stage_wakes = {}
    restarted._sync_terminal_audit_workflow_jobs()

    assert restarted._eligible_audit_stage_wakes == {
        (PROJECT_ID, TASK_ID): eligible_merged.audit_id
    }
    assert restarted._terminal_audit_continuation_wake_pending is True

    # A persisted eligibility timestamp is not authority by itself.  A crash
    # recovery pass must reject a replacement/stale prerequisite ID instead
    # of reconstructing the exact-stage wake from a different Done PASS.
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[
                replace(record, prerequisite_audit_id="audit-done-stale")
                if record.audit_id == eligible_merged.audit_id
                else record
                for record in document.pending_chain
            ],
        ),
    )
    enforcement.recover_pending_audits([(PROJECT_ID, tracker)])
    restarted._eligible_audit_stage_wakes = {}
    restarted._sync_terminal_audit_workflow_jobs()
    assert restarted._eligible_audit_stage_wakes == {}

    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[
                eligible_merged
                if record.audit_id == eligible_merged.audit_id
                else record
                for record in document.pending_chain
            ],
        ),
    )
    enforcement.recover_pending_audits([(PROJECT_ID, tracker)])
    restarted._sync_terminal_audit_workflow_jobs()
    assert restarted._eligible_audit_stage_wakes == {
        (PROJECT_ID, TASK_ID): eligible_merged.audit_id
    }
    next_job = reopened_workflow.start(
        eligible_merged,
        attempt_id="attempt-merged",
        candidate=Candidate("provider-b", "model-b"),
    )
    assert next_job is not None
    assert next_job.job_id == merged_job.job_id
    assert next_job.attempts == 1
    reopened_store.close()


def test_completed_recurrence_is_coordinator_resolved_without_rearm(
    tmp_path,
) -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    revoke_delivery = MagicMock()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
        revoke_delivery_authority=revoke_delivery,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    completed_attempt = AuditAttempt(
        attempt_id="attempt-completed",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        verdict=Verdict.PASS,
        created_at="2026-08-05T12:00:00+00:00",
        completed_at="2026-08-05T12:01:00+00:00",
    )
    completed = TerminalAuditRecord(
        audit_id="audit-completed",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[completed_attempt],
        source_generation=1,
    )
    recurrence = replace(
        completed,
        audit_id="audit-recurrence",
        request_state=RequestState.PENDING,
        attempts=[],
        source_generation=2,
    )
    unrelated_completed = replace(
        completed,
        audit_id="audit-unrelated-completed",
        source_generation=3,
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[completed, unrelated_completed, recurrence],
        ),
    )

    outcome = coordinator.reconcile_completed_recurrence_sync(
        tracker.fetch_issue_detail(TASK_ID),
        recurrence,
        PROJECT_ID,
        applied_status=DONE,
        completed_audit_id=completed.audit_id,
    )

    assert outcome.success and outcome.status_repaired
    assert outcome.audit_id == completed.audit_id
    assert outcome.cancelled_audit_ids == [recurrence.audit_id]
    assert tracker.status == DONE
    document = metadata.read(TASK_ID)
    by_id = {record.audit_id: record for record in document.pending_chain}
    assert by_id[completed.audit_id].request_state is RequestState.COMPLETED
    assert by_id[recurrence.audit_id].request_state is RequestState.SUPERSEDED
    intents = document.unknown_fields["oompah.terminal_audit_result_intents"]
    replay = next(
        intent
        for intent in intents
        if intent["attempt_id"] == "workflow-recurrence:audit-recurrence"
    )
    assert replay["audit_id"] == completed.audit_id
    assert replay["status"] == DONE
    assert replay["applied"] is True
    assert tracker.cache_invalidations == 1
    revoke_delivery.assert_called_once_with(PROJECT_ID, TASK_ID)


def test_completed_recurrence_refreshes_typed_live_status_inside_lock() -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    revoke_delivery = MagicMock()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
        revoke_delivery_authority=revoke_delivery,
    )
    stale_issue = tracker.fetch_issue_detail(TASK_ID)
    fingerprint = compute_issue_evidence_fingerprint(stale_issue, PROJECT_ID)
    completed = TerminalAuditRecord(
        audit_id="audit-completed",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id="attempt-completed",
                target_state=TargetState.DONE,
                evidence_fingerprint=fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.PASS,
            )
        ],
    )
    recurrence = replace(
        completed,
        audit_id="audit-recurrence",
        request_state=RequestState.PENDING,
        attempts=[],
        source_generation=2,
    )
    TerminalAuditMetadataStore(tracker, locks, PROJECT_ID).update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[completed, recurrence],
        ),
    )
    tracker.status = OPEN

    outcome = coordinator.reconcile_completed_recurrence_sync(
        stale_issue,
        recurrence,
        PROJECT_ID,
        applied_status=DONE,
        completed_audit_id=completed.audit_id,
    )

    assert not outcome.success
    assert outcome.reason == "issue_not_in_validation"
    assert tracker.status == OPEN
    assert tracker.cache_invalidations == 1
    revoke_delivery.assert_not_called()


def test_completed_recurrence_rejects_untyped_live_refresh() -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    stale_issue = tracker.fetch_issue_detail(TASK_ID)
    fingerprint = compute_issue_evidence_fingerprint(stale_issue, PROJECT_ID)
    record = TerminalAuditRecord(
        audit_id="audit-recurrence",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
    )
    tracker.fetch_issue_detail = lambda _identifier: {"state": IN_VALIDATION}

    outcome = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    ).reconcile_completed_recurrence_sync(
        stale_issue,
        record,
        PROJECT_ID,
        applied_status=DONE,
    )

    assert not outcome.success
    assert outcome.reason == "tracker_read_failed"
    assert tracker.status == IN_VALIDATION
    assert tracker.cache_invalidations == 1


def test_superseded_nonpass_cannot_impersonate_completed_workflow_evidence() -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    failed_source = TerminalAuditRecord(
        audit_id="audit-failed-source",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.SUPERSEDED,
        attempts=[
            AuditAttempt(
                attempt_id="attempt-failed-source",
                target_state=TargetState.DONE,
                evidence_fingerprint=fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.FAIL,
                failure_classification=FailureClassification.INCOMPLETE,
            )
        ],
        source_generation=1,
    )
    recurrence = replace(
        failed_source,
        audit_id="audit-failed-recurrence",
        request_state=RequestState.PENDING,
        attempts=[],
        source_generation=3,
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[failed_source, recurrence],
        ),
    )

    outcome = coordinator.reconcile_completed_recurrence_sync(
        tracker.fetch_issue_detail(TASK_ID),
        recurrence,
        PROJECT_ID,
        applied_status=DONE,
        completed_audit_id=failed_source.audit_id,
        completed_attempt_id="attempt-failed-source",
    )

    assert not outcome.success
    assert outcome.reason == "completed_workflow_status_mismatch"
    assert metadata.read(TASK_ID).pending_chain[-1].request_state is RequestState.PENDING
    assert tracker.status == IN_VALIDATION


def test_legacy_retirement_fence_allows_a_later_intervening_generation() -> None:
    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    first_evidence = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    first = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            first_evidence,
        )
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    first_record = metadata.read(TASK_ID).pending_chain[0]
    passed = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            _result(first_record, "attempt-legacy-pass"),
            PROJECT_ID,
        )
    )
    assert passed.success

    tracker.status = "In Review"
    second = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            EvidenceFingerprint("e" * 64),
        )
    )
    # Pre-source-generation metadata decodes every row as generation one.  The
    # append order still proves that E2 intervened after E1's retirement.
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[
                replace(record, source_generation=1)
                for record in document.pending_chain
            ],
        ),
    )

    tracker.status = "In Review"
    recurrence = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            first_evidence,
        )
    )

    assert recurrence.success
    assert recurrence.audit_id not in {first.audit_id, second.audit_id}
    current = metadata.read(TASK_ID).pending_chain[-1]
    assert current.audit_id == recurrence.audit_id
    assert current.source_generation == 2


def test_natural_completed_e1_e2_e1_reuses_exact_superseded_pass(
    tmp_path,
) -> None:
    """An intervening generation must not erase E1's exact accepted PASS."""

    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    current_evidence = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    first = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            current_evidence,
        )
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    first_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == first.audit_id
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    running = workflow.start(
        first_record,
        attempt_id="attempt-e1-pass",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    passed = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            _result(first_record, "attempt-e1-pass"),
            PROJECT_ID,
        )
    )
    assert passed.success and passed.applied_status == DONE
    workflow.complete(
        running,
        result={
            "accepted": True,
            "audit_id": first_record.audit_id,
            "applied_status": DONE,
        },
    )

    tracker.status = "In Review"
    second_evidence = EvidenceFingerprint("e" * 64)
    second = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            second_evidence,
        )
    )
    second_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == second.audit_id
    )
    workflow.ensure(second_record)

    tracker.status = "In Review"
    recurrence = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            current_evidence,
        )
    )
    recurrence_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == recurrence.audit_id
    )
    before_dispatch = {
        record.audit_id: record for record in metadata.read(TASK_ID).pending_chain
    }
    assert before_dispatch[first_record.audit_id].request_state is RequestState.SUPERSEDED
    assert before_dispatch[second_record.audit_id].request_state is RequestState.SUPERSEDED

    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator.project_store = locks
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._audit_selector = MagicMock()
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    asyncio.run(orchestrator._dispatch_audit_lane())

    orchestrator._dispatch.assert_not_awaited()
    assert tracker.status == DONE
    final = {
        record.audit_id: record for record in metadata.read(TASK_ID).pending_chain
    }
    assert final[first_record.audit_id].request_state is RequestState.SUPERSEDED
    assert final[recurrence_record.audit_id].request_state is RequestState.SUPERSEDED
    completed_job = workflow.ensure(recurrence_record)
    assert completed_job.state is WorkflowJobState.COMPLETED
    assert completed_job.result_transition["audit_id"] == first_record.audit_id
    store.close()


def test_legacy_workflow_recurrence_without_revision_fails_closed() -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    recurrence = TerminalAuditRecord(
        audit_id="audit-legacy-workflow-recurrence",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        requested_by=ContributorIdentity("oompah", "orchestrator"),
    )

    outcome = coordinator.reconcile_completed_recurrence_sync(
        tracker.fetch_issue_detail(TASK_ID),
        recurrence,
        PROJECT_ID,
        applied_status=DONE,
    )

    assert not outcome.success
    assert outcome.reason == "workflow_revision_missing"
    assert tracker.status == IN_VALIDATION


def test_restart_recovers_pre_upgrade_rearm_proof_only_for_legacy_record() -> None:
    record = TerminalAuditRecord(
        audit_id="audit-legacy-rearm",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        request_state=RequestState.PENDING,
        selected_ref=SELECTED_REF,
        selected_sha=SELECTED_SHA,
        source_generation=3,
    )
    authorization = {
        "version": 1,
        "audit_id": record.audit_id,
        "superseded_audit_id": "audit-legacy-exhausted",
        "project_id": record.project_id,
        "task_id": record.task_id,
        "target_state": record.target_state.value,
        "evidence_fingerprint": record.evidence_fingerprint.digest,
        "source_generation": record.source_generation,
        "actor": {"identity": "project-owner", "source": "api"},
        "reason": "retry after restart",
        "authorized_at": "2026-08-10T00:00:00+00:00",
        "mode": "infrastructure_recovery",
    }
    document = SimpleNamespace(
        unknown_fields={
            "oompah.terminal_audit_rearm_history": [authorization],
        }
    )

    assert (
        Orchestrator._terminal_audit_rearm_authorization(document, record)
        is authorization
    )
    assert (
        Orchestrator._terminal_audit_rearm_authorization(
            document,
            replace(record, workflow_revision="workflow-revision-2"),
        )
        is None
    )


def test_pre_cutover_workflow_record_without_revision_is_recovered_and_restaged(
    tmp_path,
) -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    record = TerminalAuditRecord(
        audit_id="audit-pre-cutover-pending",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        requested_by=ContributorIdentity("oompah", "orchestrator"),
        previous_state=IN_REVIEW,
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[record]),
    )
    workflow_path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(workflow_path)
    workflow = TerminalAuditWorkflow(store)
    running = workflow.start(
        record,
        attempt_id="attempt-pre-cutover",
        candidate=Candidate("provider-old", "model-old"),
    )
    assert running is not None
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    # Crash-window simulation: metadata retirement wins, but the first
    # attempt to restore the natural tracker state fails.
    tracker.fail_status_updates = True
    asyncio.run(orchestrator._dispatch_audit_lane())

    orchestrator._dispatch.assert_not_awaited()
    assert tracker.status == IN_VALIDATION
    migrated = metadata.read(TASK_ID)
    assert migrated.pending_chain[0].request_state is RequestState.SUPERSEDED
    assert store.get(running.job_id).state is WorkflowJobState.CANCELLED
    store.close()

    # A fresh process sees the durable migration intent even though there is
    # no longer a pending audit record, and completes the status hand-off.
    tracker.fail_status_updates = False
    reopened_store = WorkflowJobStore(workflow_path)
    reopened_workflow = TerminalAuditWorkflow(reopened_store)
    restarted = _orchestrator(
        tracker,
        coordinator,
        reopened_store,
        reopened_workflow,
    )
    restarted._audit_metrics = _test_audit_metrics()
    restarted._dispatch_is_blocked = MagicMock(return_value=False)
    restarted._is_rate_limited = MagicMock(return_value=False)
    restarted._available_slots = MagicMock(return_value=1)
    restarted._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    restarted._refresh_terminal_audit_health = MagicMock()
    restarted._dispatch = AsyncMock()
    restarted.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    asyncio.run(restarted._dispatch_audit_lane())

    assert tracker.status == IN_REVIEW
    recovered = metadata.read(TASK_ID)
    migration_intents = recovered.unknown_fields[
        "oompah.terminal_audit_result_intents"
    ]
    assert migration_intents[-1]["kind"] == "workflow_revision_migration"
    assert migration_intents[-1]["applied"] is True

    # The normal workflow can now stage a fresh request carrying the current
    # completion authority; the retired pre-cutover identity is not reused.
    refreshed = tracker.fetch_issue_detail(TASK_ID)
    fresh_fingerprint = compute_issue_evidence_fingerprint(refreshed, PROJECT_ID)
    staged = asyncio.run(
        coordinator.request_transition(
            refreshed,
            TargetState.DONE,
            ContributorIdentity("oompah", "orchestrator"),
            PROJECT_ID,
            fresh_fingerprint,
            workflow_revision="workflow-revision-fresh",
        )
    )
    assert staged.success
    assert tracker.status == IN_VALIDATION
    fresh = metadata.read(TASK_ID).pending_chain[-1]
    assert fresh.request_state is RequestState.PENDING
    assert fresh.workflow_revision == "workflow-revision-fresh"
    assert fresh.audit_id != record.audit_id
    reopened_store.close()


def test_natural_completed_failure_recurrence_replays_fail_closed_disposition(
    tmp_path,
) -> None:
    """Exact failed evidence is resolved to its repair lane, never re-audited."""

    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    first_evidence = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    first = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            first_evidence,
        )
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    first_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == first.audit_id
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    running = workflow.start(
        first_record,
        attempt_id="attempt-e1-fail",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    failed = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            _failed_result(first_record, "attempt-e1-fail"),
            PROJECT_ID,
        )
    )
    assert failed.success and failed.applied_status == OPEN
    workflow.complete(
        running,
        result={
            "accepted": True,
            "audit_id": first_record.audit_id,
            "applied_status": OPEN,
        },
    )

    tracker.status = "In Review"
    second_evidence = EvidenceFingerprint("e" * 64)
    second = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            second_evidence,
        )
    )
    second_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == second.audit_id
    )
    workflow.ensure(second_record)

    tracker.status = "In Review"
    recurrence = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            first_evidence,
        )
    )
    recurrence_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == recurrence.audit_id
    )
    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator.project_store = locks
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._audit_selector = MagicMock()
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    asyncio.run(orchestrator._dispatch_audit_lane())

    orchestrator._dispatch.assert_not_awaited()
    ownership = orchestrator._record_audit_outcome_ownership.call_args.args[1]
    assert ownership.success and ownership.applied_status == OPEN
    assert tracker.status == OPEN
    final = {
        record.audit_id: record
        for record in metadata.read(TASK_ID).pending_chain
    }
    assert final[first_record.audit_id].request_state is RequestState.SUPERSEDED
    assert final[recurrence_record.audit_id].request_state is RequestState.SUPERSEDED
    assert workflow.ensure(recurrence_record).result_transition["applied_status"] == OPEN
    store.close()


def test_natural_exhausted_e1_e2_e1_requires_owner_rearm_before_dispatch(
    tmp_path,
) -> None:
    """An active recurrence consumes owner proof without reviving implicitly."""

    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    current_evidence = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    first = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            current_evidence,
        )
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    first_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == first.audit_id
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    running = workflow.start(
        first_record,
        attempt_id="attempt-e1-exhausted",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    exhausted = workflow.action_required(
        running,
        record=first_record,
        action_code="no_independent_auditor",
        reason="candidate set exhausted",
    )
    assert exhausted.state is WorkflowJobState.EXHAUSTED
    routed = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            AuditResult(
                audit_id=first_record.audit_id,
                target_state=TargetState.DONE,
                evidence_fingerprint=current_evidence,
                verdict=Verdict.FAIL,
                failure_classification=FailureClassification.NO_AUDITOR,
                message="Configure an independent auditor, then retry.",
                attempt_id="attempt-e1-exhausted",
            ),
            PROJECT_ID,
        )
    )
    assert routed.success

    tracker.status = "In Review"
    second_evidence = EvidenceFingerprint("e" * 64)
    second = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            second_evidence,
        )
    )
    second_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == second.audit_id
    )
    workflow.ensure(second_record)

    tracker.status = "In Review"
    recurrence = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            current_evidence,
        )
    )
    recurrence_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == recurrence.audit_id
    )
    assert workflow.ensure(recurrence_record).state is WorkflowJobState.EXHAUSTED

    def owner_rearm():
        return asyncio.run(
            coordinator.retry_failed_audit(
                tracker.fetch_issue_detail(TASK_ID),
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Independent auditor capacity has been restored.",
                SimpleNamespace(
                    tracker_owner="project-owner",
                    status_actor_login=None,
                    status_label_authorized_logins=["project-owner"],
                ),
            )
        )

    tracker.fail_status_updates = True
    failed_rearm = owner_rearm()
    assert not failed_rearm.success
    assert failed_rearm.reason == "status_stage_failed"

    tracker.fail_status_updates = False
    recovered_rearm = owner_rearm()
    repeated_rearm = owner_rearm()
    assert recovered_rearm.success and recovered_rearm.coalesced
    assert repeated_rearm.success and repeated_rearm.coalesced
    assert recovered_rearm.audit_id == recurrence_record.audit_id
    assert repeated_rearm.audit_id == recurrence_record.audit_id
    document = metadata.read(TASK_ID)
    authorization = document.unknown_fields[
        "oompah.terminal_audit_rearm_history"
    ][-1]
    assert authorization["audit_id"] == recurrence_record.audit_id
    assert authorization["superseded_audit_id"] == first_record.audit_id
    assert workflow.ensure(recurrence_record).state is WorkflowJobState.EXHAUSTED

    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator.project_store = locks
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._audit_branch_claims = {}
    orchestrator._terminal_audit_manual_alerts = {}
    orchestrator._sync_terminal_audit_observability_alerts = MagicMock()
    orchestrator._refresh_terminal_audit_validation_configuration_alerts = MagicMock()
    orchestrator._terminal_audit_validation_configuration_error = MagicMock(
        return_value=None
    )
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._audit_selector = MagicMock(
        return_value=SimpleNamespace(
            select_candidates=lambda _contributors, *, exclude: (
                [Candidate("provider-b", "model-b")],
                None,
            )
        )
    )
    orchestrator._prepare_audit_selector = AsyncMock(
        return_value=(orchestrator._audit_selector.return_value, None)
    )
    orchestrator._revisionless_archive_evidence = MagicMock(return_value=None)
    orchestrator._bind_audit_record_revision = MagicMock(
        side_effect=lambda _issue, record: record
    )
    orchestrator._tracker_for_issue = lambda _issue: tracker
    orchestrator._audit_branch_busy = MagicMock(return_value=False)
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    asyncio.run(orchestrator._dispatch_audit_lane())

    orchestrator._dispatch.assert_awaited_once()
    active = workflow.ensure(recurrence_record)
    assert active.state is WorkflowJobState.RUNNING
    assert active.checkpoint["audit_id"] == recurrence_record.audit_id
    assert active.job_id == exhausted.job_id
    consumed_authorization = metadata.read(TASK_ID).unknown_fields[
        "oompah.terminal_audit_rearm_history"
    ][-1]
    assert consumed_authorization["consumed_workflow_job_id"] == active.job_id
    assert consumed_authorization["consumed_at"]
    assert orchestrator._consume_terminal_audit_rearm_authorization(
        metadata,
        tracker.fetch_issue_detail(TASK_ID),
        recurrence_record,
        authorization,
        active,
    ) is False

    exhausted_again = workflow.action_required(
        active,
        record=recurrence_record,
        action_code="no_independent_auditor",
        reason="replacement candidate exhausted",
    )
    assert exhausted_again.state is WorkflowJobState.EXHAUSTED
    orchestrator._dispatch.reset_mock()

    asyncio.run(orchestrator._dispatch_audit_lane())

    orchestrator._dispatch.assert_not_awaited()
    assert workflow.ensure(recurrence_record).state is WorkflowJobState.EXHAUSTED
    assert tracker.status == NEEDS_HUMAN
    store.close()


def test_restart_abandonment_retries_same_candidate_without_duplicate_auditor(tmp_path) -> None:
    """A lost pre-verdict worker keeps its candidate slot through restart recovery."""

    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    record = next(
        item
        for item in metadata.read(TASK_ID).pending_chain
        if item.audit_id == staged.audit_id
    )
    candidate = Candidate("provider-a", "model-a")
    selector = SimpleNamespace(
        select_candidates=lambda _contributors, *, exclude: (
            (
                [candidate]
                if (candidate.provider_id, candidate.model) not in (exclude or set())
                else []
            ),
            None,
        )
    )
    lane = AuditorDispatchLane(
        selector,
        max_attempts=2,
        id_factory=lambda: "attempt-abandoned-on-restart",
    )
    plan, no_candidate = lane.plan(
        record,
        contributors=[],
        branch_key="task/TASK-1",
    )
    assert plan is not None and no_candidate is None
    persisted = lane.persist_plan(record, plan)
    metadata.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[persisted]),
    )

    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(
        store,
        max_attempts=2,
        retry_delay_seconds=0,
    )
    running = workflow.start(
        persisted,
        attempt_id=plan.attempt_id,
        candidate=candidate,
    )
    assert running is not None

    # Simulate a service restart: durable metadata and the workflow lease
    # survive, but the in-memory worker registry is empty.  The lost attempt
    # has no verdict, so recovery must retain the sole capable candidate and
    # dispatch exactly one fenced retry rather than route Needs Human.
    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator.project_store = locks
    orchestrator.state = SimpleNamespace(claimed=set(), claimed_issues={})
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._audit_branch_claims = {}
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._audit_selector = MagicMock(return_value=selector)
    orchestrator._tracker_for_issue = lambda _issue: tracker
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=2,
        audit_attempt_ttl=3600,
    )

    asyncio.run(orchestrator._dispatch_audit_lane())

    assert orchestrator._dispatch.await_count == 1
    assert tracker.status == IN_VALIDATION
    retried = next(
        item
        for item in metadata.read(TASK_ID).pending_chain
        if item.audit_id == record.audit_id
    )
    assert retried.request_state is RequestState.IN_PROGRESS
    assert len(retried.attempts) == 2
    abandoned = retried.attempts[0]
    assert abandoned.attempt_id == plan.attempt_id
    assert (
        abandoned.failure_classification
        is FailureClassification.INFRASTRUCTURE_ERROR
    )
    assert abandoned.origin is AuditAttemptOrigin.COORDINATOR_ABANDONED_RECOVERY
    retry = retried.attempts[-1]
    assert retry.attempt_id != abandoned.attempt_id
    assert (retry.provider_id, retry.model) == (candidate.provider_id, candidate.model)
    assert workflow.ensure(retried).state is WorkflowJobState.RUNNING
    store.close()


def test_action_required_checkpoint_replays_result_after_restart(tmp_path) -> None:
    """Crash after workflow exhaustion still reaches actionable metadata/status."""

    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    record = next(
        candidate
        for candidate in metadata.read(TASK_ID).pending_chain
        if candidate.audit_id == staged.audit_id
    )
    db_path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(db_path)
    workflow = TerminalAuditWorkflow(store)
    exhausted = workflow.require_action(
        record,
        action_code="no_independent_auditor",
        reason="no independent candidate remains",
    )
    assert exhausted.state is WorkflowJobState.EXHAUSTED
    # Crash before _route_no_auditor() can project the durable action into
    # terminal-audit metadata and tracker status.
    store.close()

    reopened_store = WorkflowJobStore(db_path)
    reopened_workflow = TerminalAuditWorkflow(reopened_store)
    orchestrator = _orchestrator(
        tracker,
        coordinator,
        reopened_store,
        reopened_workflow,
    )
    orchestrator.project_store = locks
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._audit_selector = MagicMock()
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    asyncio.run(orchestrator._dispatch_audit_lane())

    orchestrator._dispatch.assert_not_awaited()
    assert tracker.status == NEEDS_HUMAN
    resolved = metadata.read(TASK_ID).pending_chain[0]
    assert resolved.audit_id == record.audit_id
    assert resolved.request_state is RequestState.COMPLETED
    assert resolved.attempts[-1].failure_classification is FailureClassification.NO_AUDITOR
    assert reopened_workflow.ensure(record).state is WorkflowJobState.EXHAUSTED
    assert orchestrator._audit_metrics["exhaustion_count"] == 1
    reopened_store.close()


def test_completed_done_recurrence_preserves_validation_for_pending_merged(
    tmp_path,
) -> None:
    """A duplicate Done must not deadlock the second half of a Merged chain."""

    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.MERGED,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert staged.queued_targets == [TargetState.DONE, TargetState.MERGED]
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    pending_done, pending_merged = metadata.read(TASK_ID).pending_chain

    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    running_done = workflow.start(
        pending_done,
        attempt_id="attempt-done",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running_done is not None
    done_outcome = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            _result(pending_done, "attempt-done"),
            PROJECT_ID,
        )
    )
    assert done_outcome.success and done_outcome.applied_status == IN_VALIDATION
    workflow.complete(
        running_done,
        result={
            "accepted": True,
            "audit_id": pending_done.audit_id,
            "applied_status": IN_VALIDATION,
        },
    )

    completed_done, pending_merged = metadata.read(TASK_ID).pending_chain
    recurring_done = replace(
        completed_done,
        audit_id="audit-done-recurrence",
        request_state=RequestState.PENDING,
        attempts=[],
        source_generation=completed_done.source_generation + 1,
    )
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[completed_done, recurring_done, pending_merged],
        ),
    )

    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator.project_store = locks
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._audit_selector = MagicMock(return_value=MagicMock())
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )
    writes_before_dispatch = tracker.metadata_write_count

    asyncio.run(orchestrator._dispatch_audit_lane())

    assert tracker.status == IN_VALIDATION
    # The already-current In Validation status and its acknowledgement are
    # committed with duplicate retirement in one metadata write.  There is no
    # stale unapplied intent that could later regress a completed Merged audit.
    assert tracker.metadata_write_count == writes_before_dispatch + 1
    document = metadata.read(TASK_ID)
    by_id = {record.audit_id: record for record in document.pending_chain}
    assert by_id[recurring_done.audit_id].request_state is RequestState.SUPERSEDED
    assert by_id[pending_merged.audit_id].request_state is RequestState.PENDING
    assert (
        AuditorDispatchLane.pending_record(
            document.pending_chain,
            project_id=PROJECT_ID,
            task_id=TASK_ID,
        ).audit_id
        == pending_merged.audit_id
    )
    replay = next(
        intent
        for intent in document.unknown_fields[
            "oompah.terminal_audit_result_intents"
        ]
        if intent["attempt_id"]
        == "workflow-recurrence:audit-done-recurrence"
    )
    assert replay["status"] == IN_VALIDATION
    assert replay["applied"] is True
    store.close()


def test_replay_quarantines_corrupt_finalizer_and_releases_sibling_lane(
    tmp_path,
) -> None:
    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID), PROJECT_ID
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.MERGED,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert staged.queued_targets == [TargetState.DONE, TargetState.MERGED]
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    done_record, merged_record = metadata.read(TASK_ID).pending_chain
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    running = workflow.start(
        done_record,
        attempt_id="attempt-corrupt",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    finalizing = workflow.mark_finalizing(
        running,
        done_record,
        result=_result(done_record, "attempt-corrupt"),
        attempt_id="attempt-corrupt",
        lease_token=running.lease_token,
    )
    checkpoint = dict(finalizing.checkpoint or {})
    corrupt_result = dict(checkpoint["result"])
    corrupt_result["verdict"] = Verdict.FAIL.value
    checkpoint["result"] = corrupt_result
    store.checkpoint(
        finalizing.job_id,
        finalizing.lease_token,
        phase="finalizing",
        checkpoint=checkpoint,
    )
    workflow.ensure(merged_record)
    orchestrator = _orchestrator(tracker, coordinator, store, workflow)

    assert asyncio.run(orchestrator._replay_terminal_audit_finalizations()) == 0

    quarantined = store.get(finalizing.job_id)
    assert quarantined.state is WorkflowJobState.EXHAUSTED
    assert quarantined.phase == "action_required"
    assert quarantined.checkpoint["action_code"] == "corrupt_finalization_checkpoint"
    assert quarantined.checkpoint["attempt_id"] == "attempt-corrupt"
    assert workflow.start(
        merged_record,
        attempt_id="attempt-merged",
        candidate=Candidate("provider-b", "model-b"),
    ) is not None
    store.close()


@pytest.mark.parametrize(
    "classification",
    [
        FailureClassification.INFRASTRUCTURE_ERROR,
        FailureClassification.MALFORMED_RESULT,
    ],
)
def test_live_structured_retryable_result_rotates_to_next_exact_attempt(
    tmp_path,
    classification,
) -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID), PROJECT_ID
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    pending = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == staged.audit_id
    )
    launched_attempt = AuditAttempt(
        attempt_id="attempt-infrastructure-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        provider_id="provider-a",
        model="model-a",
        selected_ref=SELECTED_REF,
        selected_sha=SELECTED_SHA,
        created_at="2026-08-05T12:00:00+00:00",
        started_at="2026-08-05T12:00:00+00:00",
    )
    launched = replace(
        pending,
        request_state=RequestState.IN_PROGRESS,
        attempts=[launched_attempt],
        selected_ref=SELECTED_REF,
        selected_sha=SELECTED_SHA,
    )
    metadata.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[launched]),
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    running = workflow.start(
        launched,
        attempt_id=launched_attempt.attempt_id,
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    failed = _failed_result(
        launched,
        launched_attempt.attempt_id,
        classification=classification,
    )
    finalizing = workflow.mark_finalizing(
        running,
        launched,
        result=failed,
        attempt_id=launched_attempt.attempt_id,
        lease_token=running.lease_token,
    )

    outcome = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID), failed, PROJECT_ID
        )
    )
    assert outcome.success and outcome.applied_status is None
    assert _orchestrator(
        tracker, coordinator, store, workflow
    )._finish_terminal_audit_workflow(
        tracker.fetch_issue_detail(TASK_ID), failed, outcome, finalizing
    )

    retry_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == launched.audit_id
    )
    assert retry_record.request_state is RequestState.PENDING
    exact_attempt = retry_record.attempts[0]
    assert exact_attempt.attempt_id == launched_attempt.attempt_id
    assert exact_attempt.request_state is RequestState.PENDING
    assert exact_attempt.ended_at
    assert exact_attempt.failure_classification is classification
    assert AuditorDispatchLane(SimpleNamespace()).recover(
        retry_record,
        active_attempt_identities=set(),
    ).ready
    next_run = workflow.start(
        retry_record,
        attempt_id="attempt-infrastructure-2",
        candidate=Candidate("provider-b", "model-b"),
    )
    assert next_run is not None
    assert next_run.checkpoint["attempt_id"] == "attempt-infrastructure-2"
    store.close()


def test_non_substantive_max_attempts_owner_rearm_redispatches(tmp_path) -> None:
    """Retry-only outcomes reach Needs Human without becoming a dead end."""

    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID), PROJECT_ID
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert staged.success
    assert tracker.status == IN_VALIDATION

    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    current = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == staged.audit_id
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(
        store,
        max_attempts=3,
        retry_delay_seconds=0,
    )
    orchestrator = _orchestrator(tracker, coordinator, store, workflow)

    for attempt_number in range(1, 4):
        attempt_id = f"attempt-retry-only-{attempt_number}"
        attempt = AuditAttempt(
            attempt_id=attempt_id,
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.IN_PROGRESS,
            provider_id=f"provider-{attempt_number}",
            model=f"model-{attempt_number}",
            selected_ref=SELECTED_REF,
            selected_sha=SELECTED_SHA,
            created_at=f"2026-08-05T12:0{attempt_number}:00+00:00",
            started_at=f"2026-08-05T12:0{attempt_number}:00+00:00",
        )
        launched = replace(
            current,
            request_state=RequestState.IN_PROGRESS,
            attempts=[*current.attempts, attempt],
            selected_ref=SELECTED_REF,
            selected_sha=SELECTED_SHA,
        )
        metadata.update(
            TASK_ID,
            lambda document, launched=launched: replace(
                document,
                pending_chain=[
                    launched
                    if record.audit_id == launched.audit_id
                    else record
                    for record in document.pending_chain
                ],
            ),
        )
        running = workflow.start(
            launched,
            attempt_id=attempt_id,
            candidate=Candidate(
                f"provider-{attempt_number}",
                f"model-{attempt_number}",
            ),
        )
        assert running is not None
        result = AuditResult(
            audit_id=launched.audit_id,
            target_state=launched.target_state,
            evidence_fingerprint=fingerprint,
            verdict=(Verdict.ERROR if attempt_number == 1 else Verdict.FAIL),
            failure_classification=(
                None
                if attempt_number == 1
                else FailureClassification.MALFORMED_RESULT
            ),
            message="The auditor did not produce a usable structured result.",
            attempt_id=attempt_id,
        )
        finalizing = workflow.mark_finalizing(
            running,
            launched,
            result=result,
            attempt_id=attempt_id,
            lease_token=running.lease_token,
        )
        outcome = asyncio.run(
            coordinator.apply_audit_result(
                tracker.fetch_issue_detail(TASK_ID), result, PROJECT_ID
            )
        )
        assert outcome.success and outcome.applied_status is None
        assert orchestrator._finish_terminal_audit_workflow(
            tracker.fetch_issue_detail(TASK_ID),
            result,
            outcome,
            finalizing,
        )
        current = next(
            record
            for record in metadata.read(TASK_ID).pending_chain
            if record.audit_id == staged.audit_id
        )
        expected_state = (
            WorkflowJobState.RETRY_WAIT
            if attempt_number < 3
            else WorkflowJobState.EXHAUSTED
        )
        assert workflow.ensure(current).state is expected_state

    exhausted_job = workflow.ensure(current)
    orchestrator._audit_metrics = _test_audit_metrics()
    asyncio.run(
        orchestrator._route_no_auditor(
            tracker.fetch_issue_detail(TASK_ID),
            current,
            str(exhausted_job.last_error or "retry budget exhausted"),
            action_job=exhausted_job,
        )
    )

    assert tracker.status == NEEDS_HUMAN
    exhausted_record = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == staged.audit_id
    )
    assert exhausted_record.request_state is RequestState.COMPLETED
    assert exhausted_record.attempts[0].verdict is Verdict.ERROR
    assert exhausted_record.attempts[0].failure_classification is None
    assert exhausted_record.attempts[1].failure_classification is (
        FailureClassification.MALFORMED_RESULT
    )
    assert exhausted_record.attempts[2].failure_classification is (
        FailureClassification.MALFORMED_RESULT
    )
    assert exhausted_record.attempts[3].failure_classification is (
        FailureClassification.NO_AUDITOR
    )
    assert exhausted_record.attempts[3].origin is (
        AuditAttemptOrigin.COORDINATOR_RETRY_EXHAUSTION
    )

    owner_rearm = asyncio.run(
        coordinator.retry_failed_audit(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("project-owner", "api"),
            PROJECT_ID,
            "The structured-result transport is healthy again.",
            SimpleNamespace(
                tracker_owner="project-owner",
                status_actor_login=None,
                status_label_authorized_logins=["project-owner"],
            ),
        )
    )
    assert owner_rearm.success
    assert tracker.status == IN_VALIDATION
    fresh = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == owner_rearm.audit_id
    )

    orchestrator.project_store = locks
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._audit_branch_claims = {}
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._audit_selector = MagicMock(
        return_value=SimpleNamespace(
            select_candidates=lambda _contributors, *, exclude: (
                [Candidate("provider-repaired", "model-repaired")],
                None,
            )
        )
    )
    orchestrator._tracker_for_issue = lambda _issue: tracker
    orchestrator._audit_branch_busy = MagicMock(return_value=False)
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    asyncio.run(orchestrator._dispatch_audit_lane())

    orchestrator._dispatch.assert_awaited_once()
    active = workflow.ensure(fresh)
    assert active.state is WorkflowJobState.RUNNING
    assert active.checkpoint["audit_id"] == fresh.audit_id
    redispatched = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == fresh.audit_id
    )
    assert redispatched.request_state is RequestState.IN_PROGRESS
    assert redispatched.attempts[-1].provider_id == "provider-repaired"
    store.close()


@pytest.mark.parametrize("corrupt_checkpoint", [False, True])
def test_finalization_failure_routes_exact_attempt_and_owner_rearms_dispatch(
    tmp_path,
    corrupt_checkpoint,
) -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID), PROJECT_ID
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    pending = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == staged.audit_id
    )
    launched_attempt = AuditAttempt(
        attempt_id="attempt-finalization",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        provider_id="provider-a",
        model="model-a",
        selected_ref=SELECTED_REF,
        selected_sha=SELECTED_SHA,
        created_at="2026-08-05T12:00:00+00:00",
        started_at="2026-08-05T12:00:00+00:00",
    )
    launched = replace(
        pending,
        request_state=RequestState.IN_PROGRESS,
        attempts=[launched_attempt],
        selected_ref=SELECTED_REF,
        selected_sha=SELECTED_SHA,
    )
    metadata.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[launched]),
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store, max_attempts=2)
    running = workflow.start(
        launched,
        attempt_id=launched_attempt.attempt_id,
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    finalizing = workflow.mark_finalizing(
        running,
        launched,
        result=_result(launched, launched_attempt.attempt_id),
        attempt_id=launched_attempt.attempt_id,
        lease_token=running.lease_token,
    )
    if corrupt_checkpoint:
        checkpoint = dict(finalizing.checkpoint or {})
        corrupt_result = dict(checkpoint["result"])
        corrupt_result["verdict"] = Verdict.FAIL.value
        checkpoint["result"] = corrupt_result
        corrupted = store.checkpoint(
            finalizing.job_id,
            finalizing.lease_token,
            phase="finalizing",
            checkpoint=checkpoint,
        )
        exhausted = workflow.quarantine_finalizing(
            corrupted,
            active_attempt_identities=set(),
            reason="checkpoint digest mismatch",
        )
        assert exhausted is not None
        expected_action = "corrupt_finalization_checkpoint"
    else:
        deferred = workflow.defer_finalizing(finalizing)
        exhausted = workflow.defer_finalizing(deferred)
        expected_action = "finalization_transport_exhausted"
    assert exhausted.state is WorkflowJobState.EXHAUSTED
    assert exhausted.checkpoint["action_code"] == expected_action
    assert exhausted.checkpoint["attempt_id"] == launched_attempt.attempt_id

    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator._audit_metrics = _test_audit_metrics()
    asyncio.run(
        orchestrator._route_no_auditor(
            tracker.fetch_issue_detail(TASK_ID),
            launched,
            str(exhausted.last_error or "finalization exhausted"),
            action_job=exhausted,
        )
    )

    assert tracker.status == NEEDS_HUMAN
    completed = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == launched.audit_id
    )
    assert completed.request_state is RequestState.COMPLETED
    assert [attempt.attempt_id for attempt in completed.attempts] == [
        launched_attempt.attempt_id
    ]
    assert all(
        attempt.failure_classification
        is FailureClassification.INFRASTRUCTURE_ERROR
        for attempt in completed.attempts
    )
    assert completed.attempts[0].origin is (
        AuditAttemptOrigin.COORDINATOR_RETRY_EXHAUSTION
    )

    owner_rearm = asyncio.run(
        coordinator.retry_failed_audit(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("project-owner", "api"),
            PROJECT_ID,
            "The finalization transport is healthy again.",
            SimpleNamespace(
                tracker_owner="project-owner",
                status_actor_login=None,
                status_label_authorized_logins=["project-owner"],
            ),
        )
    )
    assert owner_rearm.success
    document = metadata.read(TASK_ID)
    fresh = next(
        record
        for record in document.pending_chain
        if record.audit_id == owner_rearm.audit_id
    )
    authorization = document.unknown_fields[
        "oompah.terminal_audit_rearm_history"
    ][-1]
    rearmed_job = workflow.rearm(fresh, authorization=authorization)
    assert orchestrator._consume_terminal_audit_rearm_authorization(
        metadata,
        tracker.fetch_issue_detail(TASK_ID),
        fresh,
        authorization,
        rearmed_job,
    )
    dispatched = workflow.start(
        fresh,
        attempt_id="attempt-after-finalization-repair",
        candidate=Candidate("provider-b", "model-b"),
    )
    assert dispatched is not None
    assert dispatched.checkpoint["audit_id"] == fresh.audit_id
    assert dispatched.checkpoint["attempt_id"] == (
        "attempt-after-finalization-repair"
    )
    store.close()


def test_done_result_applied_before_crash_replays_exact_validation_status(
    tmp_path,
) -> None:
    """Idempotent Done replay keeps the live Merged successor authoritative."""

    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.MERGED,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert staged.queued_targets == [TargetState.DONE, TargetState.MERGED]
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    done_record, _merged_record = metadata.read(TASK_ID).pending_chain
    db_path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(db_path)
    workflow = TerminalAuditWorkflow(store)
    running = workflow.start(
        done_record,
        attempt_id="attempt-done-before-crash",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    workflow.mark_finalizing(
        running,
        done_record,
        result=_result(done_record, "attempt-done-before-crash"),
        attempt_id="attempt-done-before-crash",
        lease_token=running.lease_token,
    )
    applied = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            _result(done_record, "attempt-done-before-crash"),
            PROJECT_ID,
        )
    )
    assert applied.success and applied.applied_status == IN_VALIDATION
    finalizing = store.list_jobs(task_id=TASK_ID)[0]
    exit_orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    exit_entry = SimpleNamespace(
        issue=tracker.fetch_issue_detail(TASK_ID),
        identifier=TASK_ID,
        audit_id=done_record.audit_id,
        audit_attempt_id="attempt-done-before-crash",
        audit_workflow_job_id=finalizing.job_id,
        audit_workflow_lease_token=finalizing.lease_token,
    )
    with patch.object(exit_orchestrator, "_audit_store", return_value=metadata):
        assert (
            exit_orchestrator._finish_audit_attempt(
                exit_entry,
                "terminated",
                None,
            )
            is False
        )
    preserved = store.get(finalizing.job_id)
    assert preserved.state is WorkflowJobState.RUNNING
    assert preserved.phase == "finalizing"
    assert preserved.checkpoint["result"]["verdict"] == Verdict.PASS.value
    store.close()

    reopened_store = WorkflowJobStore(db_path)
    reopened_workflow = TerminalAuditWorkflow(reopened_store)
    orchestrator = _orchestrator(
        tracker,
        coordinator,
        reopened_store,
        reopened_workflow,
    )
    assert asyncio.run(orchestrator._replay_terminal_audit_finalizations()) == 1
    completed_job = reopened_store.list_jobs(task_id=TASK_ID)[0]
    assert completed_job.state is WorkflowJobState.COMPLETED
    assert completed_job.result_transition["applied_status"] == IN_VALIDATION

    completed_done, pending_merged = metadata.read(TASK_ID).pending_chain
    recurring_done = replace(
        completed_done,
        audit_id="audit-done-after-crash",
        request_state=RequestState.PENDING,
        attempts=[],
        source_generation=completed_done.source_generation + 1,
    )
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[completed_done, recurring_done, pending_merged],
        ),
    )
    orchestrator.project_store = locks
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._audit_selector = MagicMock()
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    asyncio.run(orchestrator._dispatch_audit_lane())

    orchestrator._dispatch.assert_not_awaited()
    document = metadata.read(TASK_ID)
    by_id = {record.audit_id: record for record in document.pending_chain}
    assert by_id[recurring_done.audit_id].request_state is RequestState.SUPERSEDED
    assert by_id[pending_merged.audit_id].request_state is RequestState.PENDING
    assert tracker.status == IN_VALIDATION
    reopened_store.close()


@pytest.mark.parametrize(
    ("successor_target", "same_evidence", "successor_state"),
    [
        (TargetState.MERGED, False, RequestState.PENDING),
        (TargetState.ARCHIVED, True, RequestState.PENDING),
        (TargetState.MERGED, True, RequestState.COMPLETED),
    ],
)
def test_done_recurrence_rejects_non_live_or_nonmatching_merged_successor(
    successor_target,
    same_evidence,
    successor_state,
) -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    completed = TerminalAuditRecord(
        audit_id="audit-done-completed",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id="attempt-done-completed",
                target_state=TargetState.DONE,
                evidence_fingerprint=fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.PASS,
            )
        ],
        source_generation=1,
    )
    recurrence = replace(
        completed,
        audit_id="audit-done-recurrence",
        request_state=RequestState.PENDING,
        attempts=[],
        source_generation=2,
    )
    successor = TerminalAuditRecord(
        audit_id="audit-successor",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=successor_target,
        evidence_fingerprint=(
            fingerprint if same_evidence else EvidenceFingerprint("f" * 64)
        ),
        request_state=successor_state,
        source_generation=2,
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[completed, recurrence, successor],
        ),
    )

    outcome = coordinator.reconcile_completed_recurrence_sync(
        tracker.fetch_issue_detail(TASK_ID),
        recurrence,
        PROJECT_ID,
        applied_status=IN_VALIDATION,
        completed_audit_id=completed.audit_id,
    )

    assert not outcome.success
    assert outcome.reason == "completed_workflow_status_mismatch"
    by_id = {
        record.audit_id: record
        for record in metadata.read(TASK_ID).pending_chain
    }
    assert by_id[recurrence.audit_id].request_state is RequestState.PENDING
    assert tracker.status == IN_VALIDATION


def test_evidence_recurrence_dispatches_from_fresh_activation(tmp_path) -> None:
    """A natural E1→E2→E1 sequence must not reuse E1's tombstone."""

    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    current_fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    first = TerminalAuditRecord(
        audit_id="audit-e1",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=current_fingerprint,
        request_state=RequestState.PENDING,
        source_generation=1,
    )
    second = replace(
        first,
        audit_id="audit-e2",
        evidence_fingerprint=EvidenceFingerprint("e" * 64),
        source_generation=2,
    )
    recurrence = replace(
        first,
        audit_id="audit-e1-recurrence",
        source_generation=3,
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[recurrence]),
    )

    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    first_job = workflow.ensure(first)
    second_job = workflow.ensure(second)
    assert store.get(first_job.job_id).state is WorkflowJobState.SUPERSEDED

    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator.project_store = locks
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._audit_branch_claims = {}
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._audit_selector = MagicMock(
        return_value=SimpleNamespace(
            select_candidates=lambda _contributors, *, exclude: (
                [Candidate("provider-a", "model-a")],
                None,
            )
        )
    )
    orchestrator._tracker_for_issue = lambda _issue: tracker
    orchestrator._audit_branch_busy = MagicMock(return_value=False)
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    asyncio.run(orchestrator._dispatch_audit_lane())

    orchestrator._dispatch.assert_awaited_once()
    current = metadata.read(TASK_ID).pending_chain[0]
    assert current.audit_id == recurrence.audit_id
    assert current.request_state is RequestState.IN_PROGRESS
    active = [
        job
        for job in store.list_jobs(project_id=PROJECT_ID, task_id=TASK_ID)
        if job.state is WorkflowJobState.RUNNING
    ]
    assert len(active) == 1
    assert active[0].job_id != first_job.job_id
    assert active[0].idempotency_key.endswith(":activation:3")
    assert active[0].checkpoint["audit_id"] == recurrence.audit_id
    assert store.get(second_job.job_id).state is WorkflowJobState.SUPERSEDED
    store.close()


def test_advanced_workflow_revision_does_not_replay_completed_failure(
    tmp_path,
) -> None:
    """Same task evidence at a newer completion decision launches a new audit."""

    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    prior_pending = TerminalAuditRecord(
        audit_id="audit-prior-failure",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        workflow_revision="workflow-revision-a",
        source_generation=1,
    )
    fresh = replace(
        prior_pending,
        audit_id="audit-fresh-authority",
        workflow_revision="workflow-revision-b",
        source_generation=2,
    )

    path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(path)
    workflow = TerminalAuditWorkflow(store)
    prior_running = workflow.start(
        prior_pending,
        attempt_id="attempt-prior-failure",
        candidate=Candidate("provider-old", "model-old"),
    )
    assert prior_running is not None
    prior_job_id = prior_running.job_id
    workflow.complete(
        prior_running,
        result={
            "accepted": True,
            "audit_id": prior_pending.audit_id,
            "applied_status": "Needs CI Fix",
        },
    )
    prior = replace(
        prior_pending,
        request_state=RequestState.SUPERSEDED,
        attempts=[
            AuditAttempt(
                attempt_id="attempt-prior-failure",
                target_state=TargetState.DONE,
                evidence_fingerprint=fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.FAIL,
                failure_classification=FailureClassification.CI_FAILURE,
            )
        ],
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[prior, fresh],
        ),
    )
    store.close()

    reopened_store = WorkflowJobStore(path)
    reopened_workflow = TerminalAuditWorkflow(reopened_store)
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    orchestrator = _orchestrator(
        tracker,
        coordinator,
        reopened_store,
        reopened_workflow,
    )
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._audit_branch_claims = {}
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._audit_selector = MagicMock(
        return_value=SimpleNamespace(
            select_candidates=lambda _contributors, *, exclude: (
                [Candidate("provider-new", "model-new")],
                None,
            )
        )
    )
    orchestrator._audit_branch_busy = MagicMock(return_value=False)
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    asyncio.run(orchestrator._dispatch_audit_lane())

    orchestrator._dispatch.assert_awaited_once()
    orchestrator._record_audit_outcome_ownership.assert_not_called()
    assert tracker.status == IN_VALIDATION
    current = next(
        record
        for record in metadata.read(TASK_ID).pending_chain
        if record.audit_id == fresh.audit_id
    )
    assert current.request_state is RequestState.IN_PROGRESS
    assert current.workflow_revision == "workflow-revision-b"
    active = reopened_workflow.ensure(current)
    assert active.state is WorkflowJobState.RUNNING
    assert active.job_id != prior_job_id
    assert active.checkpoint["audit_id"] == fresh.audit_id
    assert (
        active.checkpoint["workflow_revision"]
        == "workflow-revision-b"
    )
    assert reopened_store.get(prior_job_id).state is WorkflowJobState.COMPLETED
    reopened_store.close()


def test_terminal_workflow_claim_precedes_in_progress_metadata_write(
    tmp_path,
) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    fingerprint = EvidenceFingerprint("d" * 64)
    original = TerminalAuditRecord(
        audit_id="audit-original",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        source_generation=1,
    )
    running = workflow.start(
        original,
        attempt_id="attempt-original",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    workflow.complete(
        running,
        result={"accepted": True, "applied_status": DONE},
    )
    recurrence = replace(
        original,
        audit_id="audit-recurrence",
        request_state=RequestState.IN_PROGRESS,
        source_generation=2,
    )
    attempt = AuditAttempt(
        attempt_id="attempt-ownerless",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
    )
    recurrence = replace(recurrence, attempts=[attempt])
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.terminal_audit_workflow = workflow
    orchestrator._audit_update_record = MagicMock(return_value=True)
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Recurrence",
        state=IN_VALIDATION,
        project_id=PROJECT_ID,
    )
    plan = SimpleNamespace(
        attempt_id=attempt.attempt_id,
        candidate=Candidate("provider-b", "model-b"),
    )

    claimed = asyncio.run(
        orchestrator._claim_terminal_audit_attempt(
            MagicMock(),
            issue,
            recurrence,
            attempt,
            plan,
        )
    )

    assert claimed is None
    orchestrator._audit_update_record.assert_not_called()
    assert store.list_jobs(task_id=TASK_ID)[0].state is WorkflowJobState.COMPLETED
    store.close()


def test_done_to_merged_survives_pre_apply_crash_and_one_provider_retry(
    tmp_path,
) -> None:
    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    issue = tracker.fetch_issue_detail(TASK_ID)
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
    staged = asyncio.run(
        coordinator.request_transition(
            issue,
            TargetState.MERGED,
            ContributorIdentity("worker", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert staged.queued_targets == [TargetState.DONE, TargetState.MERGED]
    assert tracker.status == IN_VALIDATION

    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    done_record, merged_record = metadata.read(TASK_ID).pending_chain
    db_path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(db_path)
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    done_job = workflow.start(
        done_record,
        attempt_id="done-attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert done_job is not None
    workflow.mark_finalizing(
        done_job,
        done_record,
        result=_result(done_record, "done-attempt-1"),
        attempt_id="done-attempt-1",
        lease_token=done_job.lease_token,
    )

    # Crash before coordinator application: reopen both durable components
    # and let the replay lane consume the exact typed result.
    store.close()
    reopened_store = WorkflowJobStore(db_path)
    reopened_workflow = TerminalAuditWorkflow(reopened_store, retry_delay_seconds=0)
    orchestrator = _orchestrator(
        tracker, coordinator, reopened_store, reopened_workflow
    )
    assert asyncio.run(orchestrator._replay_terminal_audit_finalizations()) == 1
    assert tracker.status == IN_VALIDATION
    assert (
        reopened_store.list_jobs(task_id=TASK_ID)[0].state is WorkflowJobState.COMPLETED
    )

    # The Merged target starts, is killed once before producing a result, and
    # is recovered as exactly one fresh provider attempt.
    merged_record = metadata.read(TASK_ID).pending_chain[1]
    first_merge_job = reopened_workflow.start(
        merged_record,
        attempt_id="merge-attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert first_merge_job is not None
    reopened_workflow.recover(
        merged_record,
        active_attempt_identities=set(),
    )
    second_merge_job = reopened_workflow.start(
        merged_record,
        attempt_id="merge-attempt-2",
        candidate=Candidate("provider-b", "model-b"),
    )
    assert second_merge_job is not None
    assert second_merge_job.attempts == 2
    finalizing = reopened_workflow.mark_finalizing(
        second_merge_job,
        merged_record,
        result=_result(merged_record, "merge-attempt-2"),
        attempt_id="merge-attempt-2",
        lease_token=second_merge_job.lease_token,
    )

    # Crash after coordinator application but before workflow acknowledgement.
    applied = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            _result(merged_record, "merge-attempt-2"),
            PROJECT_ID,
        )
    )
    assert applied.success and applied.applied_status == MERGED
    assert reopened_store.get(finalizing.job_id).state is WorkflowJobState.RUNNING
    assert asyncio.run(orchestrator._replay_terminal_audit_finalizations()) == 1

    completed = reopened_store.get(finalizing.job_id)
    assert completed.state is WorkflowJobState.COMPLETED
    assert completed.result_transition["idempotent"] is True
    assert tracker.status == MERGED
    assert all(
        record.request_state is RequestState.COMPLETED
        for record in metadata.read(TASK_ID).pending_chain
    )
    reopened_store.close()


def test_pre_cutover_workflow_finalization_without_revision_is_cancelled(
    tmp_path,
) -> None:
    """Restart replay cannot apply an unbound workflow-authored PASS."""

    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    issue = tracker.fetch_issue_detail(TASK_ID)
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
    record = TerminalAuditRecord(
        audit_id="audit-pre-cutover-workflow",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        requested_by=ContributorIdentity("oompah", "orchestrator"),
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[record]),
    )
    path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(path)
    workflow = TerminalAuditWorkflow(store)
    running = workflow.start(
        record,
        attempt_id="attempt-pre-cutover",
        candidate=Candidate("provider-old", "model-old"),
    )
    assert running is not None
    finalizing = workflow.mark_finalizing(
        running,
        record,
        result=_result(record, "attempt-pre-cutover"),
        attempt_id="attempt-pre-cutover",
        lease_token=running.lease_token,
    )
    store.close()

    reopened_store = WorkflowJobStore(path)
    reopened_workflow = TerminalAuditWorkflow(reopened_store)
    orchestrator = _orchestrator(
        tracker,
        coordinator,
        reopened_store,
        reopened_workflow,
    )

    assert asyncio.run(orchestrator._replay_terminal_audit_finalizations()) == 1
    assert tracker.status == IN_VALIDATION
    assert (
        reopened_store.get(finalizing.job_id).state
        is WorkflowJobState.CANCELLED
    )
    persisted = metadata.read(TASK_ID).pending_chain[0]
    assert persisted.request_state is RequestState.PENDING
    reopened_store.close()


def test_duplicate_merged_generation_replays_persisted_pass_before_dispatch(
    tmp_path,
) -> None:
    """OOMPAH-824: restart consumes one PASS without a second provider."""

    tracker = _Tracker()
    locks = _RevisionProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.MERGED,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert staged.queued_targets == [TargetState.DONE, TargetState.MERGED]
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    done, pending_merged = metadata.read(TASK_ID).pending_chain
    done_outcome = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            _result(done, "attempt-done"),
            PROJECT_ID,
        )
    )
    assert done_outcome.success and done_outcome.applied_status == IN_VALIDATION

    live_attempt = AuditAttempt(
        attempt_id="attempt-11ec4964b81b",
        target_state=TargetState.MERGED,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        provider_id="provider-opus",
        model="model-opus",
        selected_ref=pending_merged.selected_ref,
        selected_sha=pending_merged.selected_sha,
        created_at="2026-08-05T12:04:00+00:00",
        started_at="2026-08-05T12:04:00+00:00",
    )
    running_merged = replace(
        pending_merged,
        audit_id="audit-11ec4964b81b",
        request_state=RequestState.IN_PROGRESS,
        attempts=[live_attempt],
        selected_ref=pending_merged.selected_ref,
        selected_sha=pending_merged.selected_sha,
        created_at="2026-08-05T12:01:00+00:00",
        updated_at="2026-08-05T12:04:00+00:00",
    )
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[*document.pending_chain, running_merged],
        ),
    )

    db_path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(db_path)
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    running_job = workflow.start(
        running_merged,
        attempt_id=live_attempt.attempt_id,
        candidate=Candidate("provider-opus", "model-opus"),
    )
    assert running_job is not None
    callback_result = _result(running_merged, live_attempt.attempt_id)
    callback_record = Orchestrator._audit_record_for_result(
        tracker.fetch_issue_detail(TASK_ID),
        callback_result,
        running_job,
    )
    assert callback_record.workflow_revision == running_merged.workflow_revision
    assert callback_record.selected_ref == running_merged.selected_ref
    assert callback_record.selected_sha == running_merged.selected_sha
    finalizing = workflow.mark_finalizing(
        running_job,
        callback_record,
        result=callback_result,
        attempt_id=live_attempt.attempt_id,
        lease_token=running_job.lease_token,
    )

    # A concurrent review/reconcile staging pass must retain the exact audit
    # whose PASS is already durable, not the older pending list entry.
    repeated = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.MERGED,
            ContributorIdentity("review-reconcile", "oompah"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert repeated.coalesced
    assert repeated.audit_id == running_merged.audit_id
    assert repeated.cancelled_audit_ids == [pending_merged.audit_id]

    store.close()
    reopened_store = WorkflowJobStore(db_path)
    reopened_workflow = TerminalAuditWorkflow(
        reopened_store,
        retry_delay_seconds=0,
    )
    orchestrator = _orchestrator(
        tracker,
        coordinator,
        reopened_store,
        reopened_workflow,
    )
    replay_record = Orchestrator._audit_record_from_finalizing_job(
        reopened_store.get(finalizing.job_id)
    )
    assert replay_record.workflow_revision == running_merged.workflow_revision
    assert replay_record.selected_ref == running_merged.selected_ref
    assert replay_record.selected_sha == running_merged.selected_sha
    orchestrator._audit_metrics = _test_audit_metrics()
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
        if tracker.status == IN_VALIDATION
        else ()
    )
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._dispatch = AsyncMock()
    orchestrator.config = SimpleNamespace(audit_priority=100, audit_lane_scan_limit=100)

    asyncio.run(orchestrator._dispatch_audit_lane())

    assert orchestrator._audit_metrics["finalizations_replayed"] == 1
    orchestrator._dispatch.assert_not_awaited()
    completed = reopened_store.get(finalizing.job_id)
    assert completed.state is WorkflowJobState.COMPLETED
    assert completed.result_transition["accepted"] is True
    assert tracker.status == MERGED
    assert len(reopened_store.list_jobs(task_id=TASK_ID)) == 1
    reopened_store.close()


def test_resolved_archive_is_retired_after_cancel_crash_and_restart(tmp_path) -> None:
    """Coordinator metadata closes the cross-store cancel crash window."""

    tracker = _Tracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.ARCHIVED,
            ContributorIdentity("owner", "api"),
            PROJECT_ID,
            fingerprint,
        )
    )
    assert staged.success
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    archive_record = metadata.read(TASK_ID).pending_chain[0]
    db_path = str(tmp_path / "workflow.sqlite3")
    store = WorkflowJobStore(db_path)
    workflow = TerminalAuditWorkflow(store)
    queued = workflow.ensure(archive_record)
    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator._audit_metrics = _test_audit_metrics()
    snapshot = SimpleNamespace(
        failure_modes=["unresolved dependencies"],
        restoration_guidance=SimpleNamespace(
            required_actions=["resolve dependencies"]
        ),
    )

    with patch.object(workflow, "retire", side_effect=RuntimeError("cancel failed")):
        with pytest.raises(RuntimeError, match="cancel failed"):
            asyncio.run(
                orchestrator._route_unsafe_metadata_archive(
                    tracker.fetch_issue_detail(TASK_ID),
                    archive_record,
                    snapshot,
                )
            )

    assert store.get(queued.job_id).state is WorkflowJobState.QUEUED
    resolved = metadata.read(TASK_ID).pending_chain
    assert resolved[0].request_state is RequestState.COMPLETED
    store.close()

    reopened_store = WorkflowJobStore(db_path)
    reopened_workflow = TerminalAuditWorkflow(reopened_store)
    restarted = _orchestrator(
        tracker,
        coordinator,
        reopened_store,
        reopened_workflow,
    )
    restarted.project_store = locks
    restarted._terminal_audit_enforcement = SimpleNamespace(pending_audits=[])
    restarted._maintenance_status = {}
    restarted._sync_terminal_audit_workflow_jobs()

    assert restarted._maintenance_status["terminal_audit_workflow"][
        "retired_resolved"
    ] == 1
    assert reopened_store.get(queued.job_id).state is WorkflowJobState.CANCELLED
    reopened_store.close()


def test_repair_status_restart_retires_orphaned_metadata_and_lane_job(
    tmp_path,
) -> None:
    """An OOMPAH-940-shaped repair status cannot revive its old audit."""

    tracker = _Tracker()
    tracker.status = NEEDS_HUMAN
    locks = _ProjectLocks()
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    attempt = AuditAttempt(
        attempt_id="attempt-orphaned",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        provider_id="provider-a",
        model="model-a",
    )
    record = TerminalAuditRecord(
        audit_id="audit-orphaned",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
        source_generation=4,
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[record]),
    )
    workflow_store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(workflow_store)
    queued = workflow.ensure(record)
    locks.remove_worktree = MagicMock(
        side_effect=[OSError("transient worktree cleanup failure"), True]
    )
    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service-state.json"),
        terminal_states=(DONE, MERGED, "Archived"),
        project_store=locks,
    )

    assert enforcer.recover_pending_audits([(PROJECT_ID, tracker)]) == []
    assert metadata.read(TASK_ID).pending_chain[0].request_state is (
        RequestState.CANCELLED
    )

    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    stale_outcome = asyncio.run(
        coordinator.apply_audit_result(
            tracker.fetch_issue_detail(TASK_ID),
            _result(record, attempt.attempt_id),
            PROJECT_ID,
        )
    )
    assert not stale_outcome.success
    assert stale_outcome.reason is ResultRejection.ISSUE_NOT_IN_VALIDATION
    assert tracker.status == NEEDS_HUMAN

    restarted = _orchestrator(tracker, coordinator, workflow_store, workflow)
    restarted._terminal_audit_enforcement = enforcer
    restarted._maintenance_status = {}
    restarted._sync_terminal_audit_workflow_jobs()

    assert restarted._maintenance_status["terminal_audit_workflow"] == {
        "materialized": 0,
        "recovered": 0,
        "retired_resolved": 0,
        "retired_workspaces": 0,
    }
    assert workflow_store.get(queued.job_id).state is WorkflowJobState.QUEUED

    # The still-active workflow row remains the durable discovery owner, so a
    # later maintenance pass retries cleanup before retiring the lane.
    restarted._sync_terminal_audit_workflow_jobs()
    assert restarted._maintenance_status["terminal_audit_workflow"] == {
        "materialized": 0,
        "recovered": 0,
        "retired_resolved": 1,
        "retired_workspaces": 1,
    }
    assert workflow_store.get(queued.job_id).state is WorkflowJobState.CANCELLED
    assert locks.remove_worktree.call_count == 2
    locks.remove_worktree.assert_called_with(
        PROJECT_ID,
        f"{TASK_ID}--terminal-audit-{attempt.attempt_id}",
    )

    writes_after_retirement = tracker.metadata_write_count
    assert enforcer.recover_pending_audits([(PROJECT_ID, tracker)]) == []
    assert tracker.metadata_write_count == writes_after_retirement
    with pytest.raises(
        AuditWorkflowIdentityError,
        match="terminal-audit source generation is stale",
    ):
        workflow.ensure(record)

    # A later, explicit return to In Validation must not revive source
    # generation 4.  The coordinator may reuse the logical audit identity,
    # but only by publishing a fresh, exact generation with no live attempt
    # from the cancelled owner.
    tracker.status = IN_VALIDATION
    rearmed = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("operator-repair", "oompah"),
            PROJECT_ID,
            compute_issue_evidence_fingerprint(
                tracker.fetch_issue_detail(TASK_ID),
                PROJECT_ID,
            ),
            workflow_revision="workflow-revision-rearmed",
        )
    )
    assert rearmed.success
    active = AuditorDispatchLane.pending_record(
        metadata.read(TASK_ID).pending_chain,
        project_id=PROJECT_ID,
        task_id=TASK_ID,
    )
    assert active is not None
    assert active.source_generation > record.source_generation
    assert active.request_state is RequestState.PENDING
    assert not any(
        value.attempt_id == attempt.attempt_id
        and value.request_state in {RequestState.PENDING, RequestState.IN_PROGRESS}
        for value in active.attempts
    )
    workflow_store.close()


def test_resolved_metadata_does_not_retire_typed_finalization(tmp_path) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    current = TerminalAuditRecord(
        audit_id="audit-finalizing",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("7" * 64),
        request_state=RequestState.PENDING,
    )
    running = workflow.start(
        current,
        attempt_id="attempt-finalizing",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    finalizing = workflow.mark_finalizing(
        running,
        current,
        result=_result(current, "attempt-finalizing"),
        attempt_id="attempt-finalizing",
        lease_token=running.lease_token,
    )
    resolved = replace(current, request_state=RequestState.COMPLETED)

    assert workflow.retire_resolved(
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        records=[resolved],
    ) == 0
    assert store.get(finalizing.job_id).state is WorkflowJobState.RUNNING
    store.close()


def test_sync_activates_applied_status_departure_after_exhausted_semantics(
    tmp_path,
) -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    old = TerminalAuditRecord(
        audit_id="audit-before-departure",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        source_generation=1,
    )
    fresh = replace(
        old,
        audit_id="audit-after-departure",
        source_generation=2,
    )
    marker = {
        "version": 1,
        "departure_id": "audit-departure-sync",
        "project_id": PROJECT_ID,
        "task_id": TASK_ID,
        "from_status": IN_VALIDATION,
        "requested_status": NEEDS_HUMAN,
        "prepared_at": "2026-08-11T00:00:00+00:00",
        "resolved_at": "2026-08-11T00:00:01+00:00",
        "applied": True,
        "outcome": "rearmed",
        "rearms": [
            {
                "audit_id": old.audit_id,
                "rearm_audit_id": fresh.audit_id,
                "source_generation": fresh.source_generation,
            }
        ],
    }
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[
                replace(old, request_state=RequestState.CANCELLED),
                fresh,
            ],
            unknown_fields={
                **document.unknown_fields,
                "oompah.terminal_audit_status_departures": [marker],
            },
        ),
    )
    workflow_store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(workflow_store)
    running = workflow.start(
        old,
        attempt_id="attempt-exhausted-before-departure",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    exhausted = workflow.action_required(
        running,
        record=old,
        action_code="no_independent_auditor",
        reason="auditor candidates exhausted",
    )
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    orchestrator = _orchestrator(
        tracker,
        coordinator,
        workflow_store,
        workflow,
    )
    orchestrator._terminal_audit_enforcement = SimpleNamespace(
        pending_audits=[SimpleNamespace(record=fresh)]
    )
    orchestrator._maintenance_status = {}

    orchestrator._sync_terminal_audit_workflow_jobs()

    active = [
        job
        for job in workflow_store.list_jobs(task_id=TASK_ID)
        if job.state in {WorkflowJobState.QUEUED, WorkflowJobState.RUNNING}
    ]
    assert len(active) == 1
    assert active[0].job_id != exhausted.job_id
    assert active[0].state is WorkflowJobState.QUEUED
    assert workflow.ensure(fresh).job_id == active[0].job_id
    workflow_store.close()


def test_finalizing_workspace_cleanup_is_rediscovered_after_job_terminalizes(
    tmp_path,
) -> None:
    tracker = _Tracker()
    tracker.status = NEEDS_HUMAN
    locks = _ProjectLocks()
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    attempt = AuditAttempt(
        attempt_id="attempt-finalizing-cleanup",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        provider_id="provider-a",
        model="model-a",
    )
    record = TerminalAuditRecord(
        audit_id="audit-finalizing-cleanup",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
        source_generation=7,
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[
                replace(record, request_state=RequestState.CANCELLED)
            ],
        ),
    )
    workflow_store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(workflow_store)
    running = workflow.start(
        record,
        attempt_id=attempt.attempt_id,
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None and running.lease_token is not None
    finalizing = workflow.mark_finalizing(
        running,
        record,
        result=_result(record, attempt.attempt_id),
        attempt_id=attempt.attempt_id,
        lease_token=running.lease_token,
    )
    workspace = f"{TASK_ID}--terminal-audit-{attempt.attempt_id}"
    locks.worktrees = [str(tmp_path / workspace)]
    locks.remove_worktree = MagicMock(
        side_effect=[OSError("transient cleanup outage"), True]
    )
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    orchestrator = _orchestrator(
        tracker,
        coordinator,
        workflow_store,
        workflow,
    )
    orchestrator._terminal_audit_enforcement = SimpleNamespace(
        pending_audits=[]
    )
    orchestrator._maintenance_status = {}

    orchestrator._sync_terminal_audit_workflow_jobs()
    assert workflow_store.get(finalizing.job_id).state is WorkflowJobState.RUNNING

    # Model the independent finalization replay terminalizing its workflow row
    # after the first cleanup attempt failed.
    workflow.cancel(finalizing, reason="stale finalization rejected")
    assert workflow_store.get(finalizing.job_id).state is WorkflowJobState.CANCELLED

    orchestrator._sync_terminal_audit_workflow_jobs()

    assert locks.remove_worktree.call_count == 2
    locks.remove_worktree.assert_called_with(PROJECT_ID, workspace)
    assert orchestrator._maintenance_status["terminal_audit_workflow"][
        "retired_workspaces"
    ] == 1
    workflow_store.close()


def test_repair_status_restart_rejects_and_cancels_stale_typed_finalization(
    tmp_path,
) -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    issue = tracker.fetch_issue_detail(TASK_ID)
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
    record = TerminalAuditRecord(
        audit_id="audit-stale-finalizing",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        source_generation=3,
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[record]),
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    running = workflow.start(
        record,
        attempt_id="attempt-stale-finalizing",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    finalizing = workflow.mark_finalizing(
        running,
        record,
        result=_result(record, "attempt-stale-finalizing"),
        attempt_id="attempt-stale-finalizing",
        lease_token=running.lease_token,
    )

    tracker.status = NEEDS_HUMAN
    enforcer = TerminalAuditEnforcement(
        str(tmp_path / "service-state.json"),
        terminal_states=(DONE, MERGED, "Archived"),
        project_store=locks,
    )
    assert enforcer.recover_pending_audits([(PROJECT_ID, tracker)]) == []
    assert metadata.read(TASK_ID).pending_chain[0].request_state is (
        RequestState.CANCELLED
    )

    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator._terminal_audit_enforcement = enforcer
    orchestrator._maintenance_status = {}
    orchestrator._sync_terminal_audit_workflow_jobs()
    assert store.get(finalizing.job_id).phase == "finalizing"

    assert asyncio.run(orchestrator._replay_terminal_audit_finalizations()) == 1
    cancelled = store.get(finalizing.job_id)
    assert cancelled.state is WorkflowJobState.CANCELLED
    assert tracker.status == NEEDS_HUMAN
    document = metadata.read(TASK_ID)
    assert document.pending_chain[0].request_state is RequestState.CANCELLED
    assert not document.unknown_fields.get("oompah.terminal_audit_result_intents")
    assert asyncio.run(orchestrator._replay_terminal_audit_finalizations()) == 0
    store.close()


def test_structured_nonterminal_outcome_requeues_instead_of_completing(
    tmp_path,
) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    record = SimpleNamespace(
        audit_id="audit-1",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("b" * 64),
        request_state=RequestState.PENDING,
        source_generation=1,
    )
    job = workflow.start(
        record,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    result = _result(record, "attempt-1")
    finalizing = workflow.mark_finalizing(
        job,
        record,
        result=result,
        attempt_id="attempt-1",
        lease_token=job.lease_token,
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.terminal_audit_workflow = workflow

    orchestrator._finish_terminal_audit_workflow(
        Issue(id=TASK_ID, identifier=TASK_ID, title="Task"),
        result,
        ResultOutcome(success=True, audit_id="audit-1", applied_status=None),
        finalizing,
    )

    assert store.get(job.job_id).state is WorkflowJobState.RETRY_WAIT
    store.close()


@pytest.mark.parametrize(
    "reason",
    [
        ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE,
        ResultRejection.METADATA_QUARANTINED,
        ResultRejection.PREREQUISITE_NOT_COMPLETED,
        "shared-epic lifecycle prerequisite is not ready",
    ],
)
def test_transient_coordinator_rejection_preserves_exact_finalization(
    tmp_path,
    reason,
) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=5)
    current = TerminalAuditRecord(
        audit_id="audit-transient",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("d" * 64),
        request_state=RequestState.PENDING,
    )
    running = workflow.start(
        current,
        attempt_id="attempt-transient",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    audit_result = _result(current, "attempt-transient")
    finalizing = workflow.mark_finalizing(
        running,
        current,
        result=audit_result,
        attempt_id="attempt-transient",
        lease_token=running.lease_token,
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.terminal_audit_workflow = workflow

    assert orchestrator._finish_terminal_audit_workflow(
        Issue(id=TASK_ID, identifier=TASK_ID, title="Task"),
        audit_result,
        ResultOutcome(
            success=False,
            audit_id=current.audit_id,
            reason=reason,
        ),
        finalizing,
    )

    preserved = store.get(finalizing.job_id)
    assert preserved.state is WorkflowJobState.RUNNING
    assert preserved.phase == "finalizing"
    assert preserved.checkpoint["attempt_id"] == "attempt-transient"
    assert preserved.checkpoint["result"]["result_digest"]
    assert preserved.checkpoint["finalization_failures"] == 1
    store.close()


def test_revoked_replacement_result_cancels_exact_finalization(tmp_path) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    record = TerminalAuditRecord(
        audit_id="audit-old",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("c" * 64),
        request_state=RequestState.PENDING,
    )
    job = workflow.start(
        record,
        attempt_id="attempt-old",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    audit_result = _result(record, "attempt-old")
    finalizing = workflow.mark_finalizing(
        job,
        record,
        result=audit_result,
        attempt_id="attempt-old",
        lease_token=job.lease_token,
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.terminal_audit_workflow = workflow

    orchestrator._finish_terminal_audit_workflow(
        Issue(id=TASK_ID, identifier=TASK_ID, title="Task"),
        audit_result,
        ResultOutcome(
            success=False,
            audit_id="audit-old",
            reason="evidence fingerprint does not match audit",
        ),
        finalizing,
    )

    assert store.get(job.job_id).state is WorkflowJobState.CANCELLED
    store.close()


def test_current_evidence_drift_cancels_obsolete_finalization(tmp_path) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    record = TerminalAuditRecord(
        audit_id="audit-stale-evidence",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("d" * 64),
        request_state=RequestState.PENDING,
    )
    job = workflow.start(
        record,
        attempt_id="attempt-stale-evidence",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    audit_result = _result(record, "attempt-stale-evidence")
    finalizing = workflow.mark_finalizing(
        job,
        record,
        result=audit_result,
        attempt_id="attempt-stale-evidence",
        lease_token=job.lease_token,
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.terminal_audit_workflow = workflow

    orchestrator._finish_terminal_audit_workflow(
        Issue(id=TASK_ID, identifier=TASK_ID, title="Task"),
        audit_result,
        ResultOutcome(
            success=False,
            audit_id=record.audit_id,
            reason=ResultRejection.CURRENT_EVIDENCE_MISMATCH,
        ),
        finalizing,
    )

    assert store.get(job.job_id).state is WorkflowJobState.CANCELLED
    store.close()


def test_callback_requires_exact_running_entry_and_lease_identity(tmp_path) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    record = TerminalAuditRecord(
        audit_id="audit-1",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("f" * 64),
        request_state=RequestState.PENDING,
    )
    job = workflow.start(
        record,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Task",
        state=IN_VALIDATION,
        project_id=PROJECT_ID,
    )
    entry = SimpleNamespace(
        is_auditor=True,
        issue=issue,
        identifier=TASK_ID,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        audit_workflow_job_id=job.job_id,
        audit_workflow_lease_token=job.lease_token,
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workflow_job_store = store
    orchestrator.terminal_audit_workflow = workflow
    orchestrator._current_running_entry = lambda _issue_id: entry

    late = _result(record, "attempt-late")
    assert orchestrator._begin_terminal_audit_finalization(issue, late) is None
    assert store.get(job.job_id).state is WorkflowJobState.RUNNING
    replacement = AuditResult(
        audit_id="audit-1",
        target_state=TargetState.MERGED,
        evidence_fingerprint=record.evidence_fingerprint,
        verdict=Verdict.PASS,
        attempt_id="attempt-1",
    )
    assert orchestrator._begin_terminal_audit_finalization(issue, replacement) is None
    assert store.get(job.job_id).phase == "running"

    finalizing = orchestrator._begin_terminal_audit_finalization(
        issue, _result(record, "attempt-1")
    )
    assert finalizing is not None
    assert finalizing.phase == "finalizing"
    store.close()


def test_replaced_workflow_revision_rejects_old_running_callback(tmp_path) -> None:
    tracker = _Tracker()
    tracker.status = IN_VALIDATION
    locks = _ProjectLocks()
    issue = tracker.fetch_issue_detail(TASK_ID)
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
    old = TerminalAuditRecord(
        audit_id="audit-running-a0",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.PENDING,
        workflow_revision="workflow-revision-a0",
        source_generation=1,
    )
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    running = workflow.start(
        old,
        attempt_id="attempt-running-a0",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    fresh = replace(
        old,
        audit_id="audit-pending-a1",
        workflow_revision="workflow-revision-a1",
        source_generation=2,
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(
            document,
            pending_chain=[
                replace(old, request_state=RequestState.SUPERSEDED),
                fresh,
            ],
        ),
    )
    entry = SimpleNamespace(
        is_auditor=True,
        issue=issue,
        identifier=TASK_ID,
        audit_id=old.audit_id,
        audit_attempt_id="attempt-running-a0",
        audit_workflow_job_id=running.job_id,
        audit_workflow_lease_token=running.lease_token,
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workflow_job_store = store
    orchestrator.terminal_audit_workflow = workflow
    orchestrator._current_running_entry = lambda _issue_id: entry
    result = _result(old, "attempt-running-a0")

    finalizing = orchestrator._begin_terminal_audit_finalization(issue, result)
    assert finalizing is not None
    outcome = asyncio.run(
        TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=locks,
            post_comments=False,
        ).apply_audit_result(issue, result, PROJECT_ID)
    )

    assert not outcome.success
    assert outcome.reason is ResultRejection.STATE_MISMATCH
    assert orchestrator._finish_terminal_audit_workflow(
        issue,
        result,
        outcome,
        finalizing,
    )
    assert store.get(running.job_id).state is WorkflowJobState.CANCELLED
    assert metadata.read(TASK_ID).pending_chain[-1] == fresh
    store.close()


def test_dynamic_policy_denial_durably_retries_only_its_attempt(tmp_path) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store, retry_delay_seconds=0)
    fingerprint = EvidenceFingerprint("d" * 64)
    attempt = AuditAttempt(
        attempt_id="attempt-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        provider_id="provider-a",
        model="model-a",
    )
    record = TerminalAuditRecord(
        audit_id="audit-1",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
    )
    job = workflow.start(
        record,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Task",
        state=IN_VALIDATION,
        project_id=PROJECT_ID,
    )
    entry = SimpleNamespace(
        issue=issue,
        identifier=TASK_ID,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        audit_workflow_job_id=job.job_id,
        audit_workflow_lease_token=job.lease_token,
    )
    audit_store = MagicMock()
    audit_store.read.return_value = SimpleNamespace(pending_chain=[record])
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workflow_job_store = store
    orchestrator.terminal_audit_workflow = workflow
    orchestrator._backoff_delay = lambda _attempt: 0

    with (
        patch.object(orchestrator, "_audit_store", return_value=audit_store),
        patch.object(orchestrator, "_audit_update_record", return_value=True),
    ):
        assert (
            orchestrator._finish_audit_attempt(
                entry, "auditor_policy_denial_exhausted", "dynamic command denied"
            )
            is True
        )

    retried = store.get(job.job_id)
    assert retried.state is WorkflowJobState.RETRY_WAIT
    assert retried.failure_category is WorkflowFailureCategory.POLICY
    store.close()


def test_completed_result_finalization_is_preserved_during_worker_exit(tmp_path) -> None:
    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    fingerprint = EvidenceFingerprint("e" * 64)
    record = TerminalAuditRecord(
        audit_id="audit-1",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
    )
    job = workflow.start(
        record,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert job is not None
    finalizing = workflow.mark_finalizing(
        job,
        record,
        result=_result(record, "attempt-1"),
        attempt_id="attempt-1",
        lease_token=job.lease_token,
    )
    completed_record = TerminalAuditRecord(
        audit_id=record.audit_id,
        project_id=record.project_id,
        task_id=record.task_id,
        target_state=record.target_state,
        evidence_fingerprint=record.evidence_fingerprint,
        request_state=RequestState.COMPLETED,
    )
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Task",
        state="Done",
        project_id=PROJECT_ID,
    )
    entry = SimpleNamespace(
        issue=issue,
        identifier=TASK_ID,
        audit_id="audit-1",
        audit_attempt_id="attempt-1",
        audit_workflow_job_id=finalizing.job_id,
        audit_workflow_lease_token=finalizing.lease_token,
    )
    audit_store = MagicMock()
    audit_store.read.return_value = SimpleNamespace(pending_chain=[completed_record])
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workflow_job_store = store
    orchestrator.terminal_audit_workflow = workflow

    with patch.object(orchestrator, "_audit_store", return_value=audit_store):
        assert orchestrator._finish_audit_attempt(entry, "terminated", None) is False

    preserved = store.get(job.job_id)
    assert preserved.state is WorkflowJobState.RUNNING
    assert preserved.phase == "finalizing"
    assert preserved.checkpoint["result"]["audit_id"] == record.audit_id
    assert "applied_status" not in (preserved.result_transition or {})
    store.close()


def test_finalization_replay_precedes_pause_and_capacity_gates() -> None:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator._audit_metrics = _test_audit_metrics(
        restart_publication_deferred_count=3
    )
    orchestrator._tick_pool = None
    orchestrator._audit_rollback_persistence_failed = False
    orchestrator._audit_rollback_lock = threading.RLock()
    orchestrator._pending_audit_rollbacks = {}
    orchestrator._reconcile_audit_budget_reservations = MagicMock()
    orchestrator._refresh_terminal_audit_validation_configuration_alerts = MagicMock()
    orchestrator._replay_terminal_audit_finalizations = AsyncMock(return_value=1)
    orchestrator._dispatch_is_blocked = MagicMock(return_value=True)
    orchestrator._is_rate_limited = MagicMock(return_value=False)

    result = asyncio.run(
        orchestrator._dispatch_audit_lane(allow_new_launches=False)
    )

    assert result == {"audit_dispatch": 0.0, "audit_scan": 0.0}
    orchestrator._replay_terminal_audit_finalizations.assert_awaited_once()
    assert orchestrator._audit_metrics["finalizations_replayed"] == 1
    assert orchestrator._audit_metrics["restart_publication_deferred_count"] == 0


def test_restart_world_publication_precedes_real_audit_launch_across_two_ticks(
    tmp_path,
) -> None:
    """Restart recovery publishes one stable world before provider admission."""

    from tests.test_workflow_runtime import (
        accepted_projection_wiring,
        complete_handlers,
        make_binding,
        wait_for_runtime_effects,
    )

    class GenerationTracker(_Tracker):
        supports_generation_bound_reads = True
        state_branch_enabled = True

        def __init__(self) -> None:
            super().__init__()
            self.authority_generation = "native:1"
            self.publication_revision = 1
            self.inject_external_write = False
            self._external_write_armed = False
            self.external_write_count = 0

        def _advance_authority(self) -> None:
            self.publication_revision += 1
            self.authority_generation = f"native:{self.publication_revision}"

        def set_metadata_field(self, identifier: str, key: str, value) -> None:
            super().set_metadata_field(identifier, key, value)
            self._advance_authority()

        def update_issue(self, identifier: str, **changes) -> None:
            previous = self.status
            super().update_issue(identifier, **changes)
            if self.status != previous:
                self._advance_authority()

        def fetch_all_issues(self) -> list[Issue]:
            return [self.fetch_issue_detail(TASK_ID)]

        fetch_all_issues_enriched = fetch_all_issues

        def fetch_all_issues_with_generation(self):
            generation = self.authority_generation
            if self.inject_external_write:
                self.inject_external_write = False
                self._external_write_armed = True
            return self.fetch_all_issues(), generation

        def get_state_branch_generation(self):
            if self._external_write_armed:
                self._external_write_armed = False
                self.external_write_count += 1
                self.set_metadata_field(
                    TASK_ID,
                    "external-writer-probe",
                    {"write": self.external_write_count},
                )
            return self.authority_generation

        def get_publication_revision(self):
            return self.publication_revision

        def fetch_children(self, _identifier: str) -> list[Issue]:
            return []

    tracker = GenerationTracker()
    locks = _ProjectLocks()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(
        tracker.fetch_issue_detail(TASK_ID),
        PROJECT_ID,
    )
    staged = asyncio.run(
        coordinator.request_transition(
            tracker.fetch_issue_detail(TASK_ID),
            TargetState.DONE,
            ContributorIdentity("review-webhook", "oompah"),
            PROJECT_ID,
            fingerprint,
            workflow_revision="workflow-revision-1",
        )
    )
    assert staged.success
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    record = next(
        candidate
        for candidate in metadata.read(TASK_ID).pending_chain
        if candidate.audit_id == staged.audit_id
    )

    store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    workflow = TerminalAuditWorkflow(store)
    orchestrator = _orchestrator(tracker, coordinator, store, workflow)
    orchestrator.project_store = locks
    orchestrator.state = SimpleNamespace(claimed=set(), claimed_issues={})
    orchestrator._audit_branch_claims = {}
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    selector = SimpleNamespace(
        select_candidates=lambda _contributors, *, exclude: (
            (
                [Candidate("provider-a", "model-a")]
                if ("provider-a", "model-a") not in (exclude or set())
                else []
            ),
            None,
        )
    )
    orchestrator._audit_selector = MagicMock(return_value=selector)
    orchestrator._prepare_audit_selector = AsyncMock(
        return_value=(selector, None)
    )
    orchestrator._audit_branch_busy = MagicMock(return_value=False)
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator.config = SimpleNamespace(
        full_sync_interval_ms=30_000,
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_lane_operation_limit=8,
        audit_lane_dispatch_limit=2,
        audit_lane_max_runtime_seconds=15.0,
        audit_max_attempts=3,
        audit_attempt_ttl=3600,
    )

    binding, journal = make_binding(tmp_path, tracker, store, PROJECT_ID)
    binding.terminal_audit_workflow = workflow
    binding.terminal_audit_publication_lock = (
        lambda: locks.project_write_lock(PROJECT_ID)
    )
    terminal_source = orchestrator._workflow_shadow_sources(
        tracker.fetch_issue_detail(TASK_ID)
    )["terminal_audit"]
    binding.collector.sources["terminal_audit"] = terminal_source

    def terminal_snapshot_proof(decision, observed) -> bool:
        with locks.project_write_lock(PROJECT_ID):
            fresh = terminal_source(tracker.fetch_issue_detail(decision.task_id))
            return isinstance(fresh, dict) and fresh == dict(observed)

    def terminal_job_proof(decision, observed, action) -> bool:
        with locks.project_write_lock(PROJECT_ID):
            current = AuditorDispatchLane.pending_record(
                metadata.read(decision.task_id).pending_chain,
                project_id=PROJECT_ID,
                task_id=decision.task_id,
            )
            if current is None:
                return False
            expected = {
                "audit_id": current.audit_id,
                "request_state": current.request_state.value,
                "target_state": current.target_state.value,
                "evidence_fingerprint": current.evidence_fingerprint.digest,
                "source_generation": current.source_generation,
                "audit_generation": workflow.generation(current),
            }
            return all(observed.get(key) == value for key, value in expected.items()) and (
                store.terminal_audit_lane_materialized(
                    project_id=PROJECT_ID,
                    task_id=decision.task_id,
                    audit_id=current.audit_id,
                    target_state=current.target_state.value,
                    evidence_fingerprint=current.evidence_fingerprint.digest,
                    audit_generation=workflow.generation(current),
                    source_generation=current.source_generation,
                    obligation_action=action,
                )
            )

    binding.terminal_audit_snapshot_proof_source = terminal_snapshot_proof
    binding.terminal_audit_proof_source = terminal_job_proof
    controller = UniversalTotalityLivenessController(store=store)
    controller.restore_liveness_state(None)
    runtime = WorkflowRuntime(
        project_bindings={PROJECT_ID: binding},
        store=store,
        journals={PROJECT_ID: journal},
        mode="enforce",
        handlers=complete_handlers(),
        liveness_controller=controller,
        persist_liveness_state=lambda _state: None,
        **accepted_projection_wiring(),
    )
    orchestrator.workflow_runtime = runtime
    orchestrator._terminal_audit_started = False
    orchestrator._terminal_audit_last_scan = 0.0
    orchestrator._monotonic_clock = time.monotonic
    orchestrator._request_workflow_batch_continuation = MagicMock(
        return_value=False
    )
    orchestrator._maintenance_future = None
    orchestrator._run_non_lifecycle_housekeeping = MagicMock()
    orchestrator._notify_observers = MagicMock()
    orchestrator._handle_auto_update = AsyncMock()
    orchestrator._provider_admission_lock = threading.RLock()
    orchestrator._stopping = False
    orchestrator._quiesced = False
    orchestrator._paused = False
    orchestrator._set_refresh_requested = MagicMock()
    orchestrator._post_event = MagicMock()
    orchestrator._tick_pool = ThreadPoolExecutor(max_workers=2)

    order: list[str] = []
    real_audit_lane = orchestrator._dispatch_audit_lane
    real_reconcile = runtime.reconcile_async
    real_admission = runtime.continue_admission_async

    async def traced_audit_lane(**kwargs):
        order.append(
            "audit_launch_phase"
            if kwargs.get("allow_new_launches", True)
            else "audit_recovery_phase"
        )
        return await real_audit_lane(**kwargs)

    async def traced_reconcile(**kwargs):
        order.append("world_reconcile")
        return await real_reconcile(**kwargs)

    async def traced_admission():
        order.append("workflow_admission")
        return await real_admission()

    async def provider_dispatch(*_args, **_kwargs):
        order.append("provider_launch")
        return True

    orchestrator._dispatch_audit_lane = traced_audit_lane
    orchestrator._dispatch = AsyncMock(side_effect=provider_dispatch)
    runtime.reconcile_async = traced_reconcile
    runtime.continue_admission_async = traced_admission

    async def scenario():
        await runtime.start()
        assert runtime.restart_reconstruction_pending
        tracker.inject_external_write = True
        await orchestrator._run_durable_workflow_tick(
            started_at=time.monotonic()
        )
        first_report = copy.deepcopy(orchestrator._last_tick_metrics)
        first_health = controller.liveness_snapshot()
        await orchestrator._run_durable_workflow_tick(
            started_at=time.monotonic()
        )
        await wait_for_runtime_effects(runtime)
        return first_report, first_health

    try:
        with patch(
            "oompah.orchestrator.validate_dispatch_config", return_value=[]
        ):
            first_report, first_health = asyncio.run(scenario())
    finally:
        orchestrator._tick_pool.shutdown(wait=True)

    current = next(
        candidate
        for candidate in metadata.read(TASK_ID).pending_chain
        if candidate.audit_id == record.audit_id
    )
    assert first_report["workflow_runtime"]["requires_reconcile"] is True
    assert first_health.restart_reconstruction_pending
    assert tracker.external_write_count == 1
    assert orchestrator._dispatch.await_count == 1
    assert current.request_state is RequestState.IN_PROGRESS
    assert workflow.ensure(current).state is WorkflowJobState.RUNNING
    converged_health = controller.liveness_snapshot()
    assert converged_health.scan_complete
    assert converged_health.global_coverage_complete
    assert isinstance(converged_health.snapshot_generation, int)
    assert converged_health.snapshot_generation > 0
    assert not converged_health.restored
    assert not converged_health.restart_reconstruction_pending
    assert not runtime.restart_reconstruction_pending
    assert order == [
        "audit_recovery_phase",
        "world_reconcile",
        "audit_recovery_phase",
        "world_reconcile",
        "audit_launch_phase",
        "provider_launch",
        "workflow_admission",
    ]
    assert 1 <= orchestrator._post_event.call_count <= 2
    runtime.close()
    store.close()
