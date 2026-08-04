from __future__ import annotations

import hashlib

import pytest

from oompah.roles import Candidate
from oompah.terminal_audit import (
    EvidenceFingerprint,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
)
from oompah.terminal_audit_workflow import (
    AuditWorkflowIdentityError,
    AuditWorkflowPhase,
    TerminalAuditWorkflow,
)
from oompah.terminal_transition_coordinator import AuditResult
from oompah.workflow_jobs import WorkflowJobState, WorkflowJobStore


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def record(
    *,
    audit_id: str = "audit-1",
    evidence: str = "evidence-1",
    task_id: str = "TASK-1",
    target: TargetState = TargetState.DONE,
):
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id="project-a",
        task_id=task_id,
        target_state=target,
        evidence_fingerprint=EvidenceFingerprint(
            hashlib.sha256(evidence.encode()).hexdigest()
        ),
        request_state=RequestState.PENDING,
    )


def result(
    current: TerminalAuditRecord,
    *,
    attempt_id: str = "attempt-1",
    verdict: Verdict = Verdict.PASS,
    classification: FailureClassification | None = None,
    message: str = "bounded audit result",
    safe_evidence: dict[str, str] | None = None,
) -> AuditResult:
    return AuditResult(
        audit_id=current.audit_id,
        target_state=current.target_state,
        evidence_fingerprint=current.evidence_fingerprint,
        verdict=verdict,
        failure_classification=classification,
        message=message,
        safe_evidence=safe_evidence,
        attempt_id=attempt_id,
    )


@pytest.fixture
def durable(tmp_path):
    clock = Clock()
    store = WorkflowJobStore(str(tmp_path / "audit.sqlite3"), clock=clock)
    workflow = TerminalAuditWorkflow(
        store,
        lease_owner="audit-worker-1",
        lease_seconds=30,
        retry_delay_seconds=5,
        clock=clock,
    )
    yield workflow, store, clock
    store.close()


def test_exact_audit_identity_is_idempotently_queued(durable):
    workflow, store, _clock = durable
    current = record()

    first = workflow.ensure(current)
    replay = workflow.ensure(current)

    assert replay.job_id == first.job_id
    assert len(store.list_jobs()) == 1
    assert workflow.decision(current).phase is AuditWorkflowPhase.QUEUED


def test_running_finalizing_and_completed_survive_reopen(durable, tmp_path):
    workflow, store, clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    assert workflow.decision(current).phase is AuditWorkflowPhase.RUNNING

    finalizing = workflow.mark_finalizing(
        running,
        current,
        result=result(current),
        attempt_id="attempt-1",
        lease_token=running.lease_token,
    )
    assert workflow.decision(current).phase is AuditWorkflowPhase.FINALIZING
    completed = workflow.complete(
        finalizing,
        result={"accepted": True, "applied_status": "Done"},
    )
    assert completed.state is WorkflowJobState.COMPLETED
    store.close()

    reopened = WorkflowJobStore(str(tmp_path / "audit.sqlite3"), clock=clock)
    try:
        restored = TerminalAuditWorkflow(
            reopened,
            lease_owner="audit-worker-2",
            clock=clock,
        )
        assert restored.decision(current).phase is AuditWorkflowPhase.COMPLETED
        assert (
            restored.decision(current).evidence_fingerprint
            == current.evidence_fingerprint.digest
        )
    finally:
        reopened.close()


def test_transport_rotation_is_informational_and_retryable(durable):
    workflow, _store, clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None

    retry = workflow.retry(running, reason="provider timeout")
    decision = workflow.decision(current)
    assert retry.state is WorkflowJobState.RETRY_WAIT
    assert decision.phase is AuditWorkflowPhase.RETRY_WAIT
    assert decision.informational is True
    assert decision.action_code is None

    clock.advance(5)
    next_attempt = workflow.start(
        current,
        attempt_id="attempt-2",
        candidate=Candidate("provider-b", "model-b"),
    )
    assert next_attempt is not None
    assert workflow.decision(current).phase is AuditWorkflowPhase.RUNNING


def test_no_candidate_or_policy_denial_is_explicit_action_required(durable):
    workflow, _store, _clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None

    required = workflow.action_required(
        running,
        action_code="no_independent_auditor",
        reason="No eligible independent candidate remains",
    )
    assert required.state is WorkflowJobState.EXHAUSTED
    decision = workflow.decision(current)
    assert decision.phase is AuditWorkflowPhase.ACTION_REQUIRED
    assert decision.action_code == "no_independent_auditor"

    # A replay cannot revive action-required work. A new evidence identity is
    # the only valid way to start a fresh audit.
    assert workflow.ensure(current).job_id == required.job_id
    assert (
        workflow.decision(record(evidence="evidence-2")).phase
        is AuditWorkflowPhase.QUEUED
    )


def test_queued_no_candidate_can_become_action_required_without_launch(durable):
    workflow, _store, _clock = durable
    current = record()
    required = workflow.require_action(
        current,
        action_code="no_independent_auditor",
        reason="the auditor role has no independent candidate",
    )
    assert required.state is WorkflowJobState.EXHAUSTED
    assert workflow.decision(current).phase is AuditWorkflowPhase.ACTION_REQUIRED
    assert workflow.decision(current).action_code == "no_independent_auditor"


def test_late_no_candidate_scan_cannot_exhaust_a_running_attempt(durable):
    workflow, store, _clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None

    observed = workflow.require_action(
        current,
        action_code="no_independent_auditor",
        reason="stale candidate scan",
    )

    assert observed.state is WorkflowJobState.RUNNING
    assert store.get(running.job_id).lease_token == running.lease_token


def test_restart_requeues_audit_without_a_live_attempt(durable):
    workflow, _store, _clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None

    recovered = workflow.recover(current, active_attempt_ids=set())
    assert recovered.phase is AuditWorkflowPhase.RETRY_WAIT
    assert workflow.decision(current).phase is AuditWorkflowPhase.RETRY_WAIT


def test_checkpoint_excludes_oversized_or_untrusted_output(durable):
    workflow, store, _clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    workflow.mark_finalizing(
        running,
        current,
        result=result(
            current,
            verdict=Verdict.FAIL,
            classification=FailureClassification.MISSING_EVIDENCE,
            message="x" * 4000,
            safe_evidence={f"check-{index}": "passed " * 60 for index in range(20)},
        ),
        attempt_id="attempt-1",
        lease_token=running.lease_token,
    )
    checkpoint = store.get(running.job_id).checkpoint
    assert checkpoint is not None
    assert "output" not in checkpoint
    assert "comments" not in checkpoint
    assert checkpoint["evidence_fingerprint"] == current.evidence_fingerprint.digest
    assert len(checkpoint["result"]["message"]) == 512
    assert len(checkpoint["result"]["safe_evidence"]) == 4
    assert len(checkpoint["result"]["result_digest"]) == 64


def test_running_job_cannot_be_inherited_by_a_new_attempt(durable):
    workflow, store, _clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None

    assert (
        workflow.start(
            current,
            attempt_id="attempt-2",
            candidate=Candidate("provider-b", "model-b"),
        )
        is None
    )
    persisted = store.get(running.job_id)
    assert persisted.checkpoint["attempt_id"] == "attempt-1"
    assert persisted.lease_token == running.lease_token


def test_restart_recovers_only_the_abandoned_exact_job(durable):
    workflow, store, _clock = durable
    first = record(task_id="TASK-1")
    second = record(audit_id="audit-2", task_id="TASK-2", evidence="evidence-2")
    first_job = workflow.start(
        first,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    second_job = workflow.start(
        second,
        attempt_id="attempt-2",
        candidate=Candidate("provider-b", "model-b"),
    )
    assert first_job is not None and second_job is not None
    assert first_job.lease_owner == second_job.lease_owner

    workflow.recover(first, active_attempt_ids=set())

    assert store.get(first_job.job_id).state is WorkflowJobState.RETRY_WAIT
    assert store.get(second_job.job_id).state is WorkflowJobState.RUNNING
    assert store.get(second_job.job_id).lease_token == second_job.lease_token


def test_finalizing_result_survives_restart_and_reclaims_exact_lease(durable):
    workflow, store, _clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    finalizing = workflow.mark_finalizing(
        running,
        current,
        result=result(current),
        attempt_id="attempt-1",
        lease_token=running.lease_token,
    )

    assert (
        workflow.recover(current, active_attempt_ids=set()).phase
        is AuditWorkflowPhase.FINALIZING
    )
    reclaimed = workflow.reclaim_finalizing(
        store.get(finalizing.job_id),
        current,
        active_attempt_ids=set(),
    )
    assert reclaimed is not None
    assert reclaimed.lease_token != finalizing.lease_token
    assert reclaimed.attempts == finalizing.attempts
    payload = workflow.finalizing_result_payload(reclaimed)
    assert payload["audit_id"] == "audit-1"
    assert payload["attempt_id"] == "attempt-1"
    assert payload["evidence_fingerprint"] == current.evidence_fingerprint.digest
    assert tuple(payload["instructions"]) == ()
    assert payload["message"] == "bounded audit result"
    assert tuple(payload["questions"]) == ()
    assert payload["target_state"] == "Done"
    assert payload["verdict"] == "pass"


def test_finalization_transport_failure_has_durable_retry_backoff(durable):
    workflow, store, clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    finalizing = workflow.mark_finalizing(
        running,
        current,
        result=result(current),
        attempt_id="attempt-1",
        lease_token=running.lease_token,
    )
    deferred = workflow.defer_finalizing(finalizing)

    assert deferred.checkpoint["finalization_failures"] == 1
    assert (
        workflow.reclaim_finalizing(deferred, current, active_attempt_ids=set()) is None
    )
    clock.advance(5)
    reclaimed = workflow.reclaim_finalizing(
        store.get(finalizing.job_id), current, active_attempt_ids=set()
    )
    assert reclaimed is not None
    assert reclaimed.lease_token != finalizing.lease_token


@pytest.mark.parametrize(
    ("replacement", "attempt_id"),
    [
        (record(evidence="replacement"), "attempt-1"),
        (record(target=TargetState.MERGED), "attempt-1"),
        (record(), "attempt-late"),
    ],
)
def test_finalization_rejects_replaced_target_or_attempt(
    durable, replacement, attempt_id
):
    workflow, _store, _clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None

    with pytest.raises(AuditWorkflowIdentityError):
        workflow.mark_finalizing(
            running,
            replacement,
            result=result(replacement, attempt_id=attempt_id),
            attempt_id=attempt_id,
            lease_token=running.lease_token,
        )


def test_pre_cutover_finalizing_checkpoint_gets_bounded_exact_retry(durable):
    workflow, store, _clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    legacy = store.checkpoint(
        running.job_id,
        running.lease_token,
        phase=AuditWorkflowPhase.FINALIZING.value,
        checkpoint={
            "version": 1,
            "audit_id": current.audit_id,
            "target_state": current.target_state.value,
            "evidence_fingerprint": current.evidence_fingerprint.digest,
            "attempt_id": "attempt-1",
            "verdict": "pass",
        },
    )

    recovered = workflow.requeue_unreplayable_finalizing(
        legacy,
        active_attempt_ids=set(),
    )

    assert recovered is not None
    assert recovered.state is WorkflowJobState.RETRY_WAIT


def test_terminal_history_cannot_hide_new_finalizing_work(durable):
    workflow, _store, _clock = durable
    old = record(audit_id="audit-old", task_id="TASK-OLD", evidence="old")
    old_job = workflow.start(
        old,
        attempt_id="attempt-old",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert old_job is not None
    workflow.complete(old_job, result={"accepted": True})

    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-b", "model-b"),
    )
    assert running is not None
    finalizing = workflow.mark_finalizing(
        running,
        current,
        result=result(current),
        attempt_id="attempt-1",
        lease_token=running.lease_token,
    )

    assert [job.job_id for job in workflow.finalizing_jobs(limit=1)] == [
        finalizing.job_id
    ]
