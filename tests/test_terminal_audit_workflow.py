from __future__ import annotations

import hashlib
from dataclasses import replace

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
    audit_attempt_identity,
)
from oompah.terminal_transition_coordinator import AuditResult
from oompah.workflow_jobs import (
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
    WorkflowJobStoreError,
)


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
    project_id: str = "project-a",
    target: TargetState = TargetState.DONE,
    source_generation: int = 1,
):
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id=project_id,
        task_id=task_id,
        target_state=target,
        evidence_fingerprint=EvidenceFingerprint(
            hashlib.sha256(evidence.encode()).hexdigest()
        ),
        request_state=RequestState.PENDING,
        source_generation=source_generation,
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


def test_exact_target_evidence_generation_is_idempotently_queued(durable):
    workflow, store, _clock = durable
    current = record()

    first = workflow.ensure(current)
    replay = workflow.ensure(current)

    assert replay.job_id == first.job_id
    assert len(store.list_jobs()) == 1
    assert workflow.decision(current).phase is AuditWorkflowPhase.QUEUED


def test_duplicate_audit_ids_share_one_target_evidence_generation(durable):
    workflow, store, _clock = durable
    first = record(audit_id="audit-A")
    duplicate = record(audit_id="audit-B")

    first_job = workflow.ensure(first)
    duplicate_job = workflow.ensure(duplicate)
    running = workflow.start(
        first,
        attempt_id="attempt-A",
        candidate=Candidate("provider-a", "model-a"),
    )

    assert duplicate_job.job_id == first_job.job_id
    assert running is not None
    assert (
        workflow.start(
            duplicate,
            attempt_id="attempt-B",
            candidate=Candidate("provider-b", "model-b"),
        )
        is None
    )
    jobs = store.list_jobs(project_id="project-a", task_id="TASK-1")
    assert len(jobs) == 1
    assert jobs[0].checkpoint["audit_id"] == "audit-A"
    assert jobs[0].checkpoint["attempt_id"] == "attempt-A"


def test_semantic_lookup_is_not_hidden_by_more_than_one_thousand_history_rows(
    durable,
):
    workflow, store, _clock = durable
    lane = "terminal-audit:Done"
    for index in range(1001):
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-a",
                task_id="TASK-1",
                generation=f"noise-generation-{index}",
                action="terminal_audit",
                idempotency_key=f"noise-key-{index}",
                phase=AuditWorkflowPhase.QUEUED.value,
                scheduling_lane=lane,
                expected_evidence_revision=hashlib.sha256(
                    f"noise-{index}".encode()
                ).hexdigest(),
            )
        )

    first = record(
        audit_id="audit-first-deep",
        evidence="recurring-deep-evidence",
        source_generation=1002,
    )
    canonical = workflow.ensure(first)
    running = workflow.start(
        first,
        attempt_id="attempt-first-deep",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    exhausted = workflow.action_required(
        running,
        record=first,
        action_code="no_independent_auditor",
        reason="candidate set exhausted",
    )
    rearmed_record = replace(
        first,
        audit_id="audit-rearmed-deep",
        source_generation=1003,
    )
    authorization = {
        "version": 1,
        "audit_id": rearmed_record.audit_id,
        "superseded_audit_id": first.audit_id,
        "project_id": rearmed_record.project_id,
        "task_id": rearmed_record.task_id,
        "target_state": rearmed_record.target_state.value,
        "evidence_fingerprint": rearmed_record.evidence_fingerprint.digest,
        "source_generation": rearmed_record.source_generation,
        "actor": {"identity": "project-owner", "source": "api"},
        "reason": "retry deep terminal history",
        "authorized_at": "2026-08-05T12:00:00+00:00",
        "mode": "infrastructure_recovery",
    }
    rearmed = workflow.rearm(rearmed_record, authorization=authorization)
    assert rearmed.job_id == exhausted.job_id == canonical.job_id
    workflow.retire(rearmed_record, reason="rearmed deep generation was revoked")
    intervening = record(
        audit_id="audit-intervening-deep",
        evidence="intervening-deep-evidence",
        source_generation=1004,
    )
    workflow.ensure(intervening)
    workflow.retire(intervening, reason="intervening generation was revoked")

    recurrence = record(
        audit_id="audit-recurrence-deep",
        evidence="recurring-deep-evidence",
        source_generation=1005,
    )
    activated = workflow.ensure(recurrence)

    assert activated.job_id != canonical.job_id
    assert activated.state is WorkflowJobState.QUEUED
    assert activated.generation == workflow.generation(recurrence)
    assert activated.scheduling_lane == lane
    assert activated.expected_evidence_revision == recurrence.evidence_fingerprint.digest


def test_done_and_merged_same_evidence_use_independent_ordered_lanes(durable):
    workflow, store, _clock = durable
    done = record(audit_id="audit-done", target=TargetState.DONE)
    merged = record(audit_id="audit-merged", target=TargetState.MERGED)

    done_job = workflow.ensure(done)
    merged_job = workflow.ensure(merged)

    assert done_job.job_id != merged_job.job_id
    assert done_job.scheduling_lane == "terminal-audit:Done"
    assert merged_job.scheduling_lane == "terminal-audit:Merged"
    assert len(store.list_jobs(project_id="project-a", task_id="TASK-1")) == 2


def test_changed_evidence_replaces_only_its_target_lane(durable):
    workflow, store, _clock = durable
    old_done = record(audit_id="audit-old", evidence="old")
    merged = record(
        audit_id="audit-merged",
        evidence="old",
        target=TargetState.MERGED,
    )
    old_job = workflow.ensure(old_done)
    merged_job = workflow.ensure(merged)

    fresh_done = record(
        audit_id="audit-new",
        evidence="new",
        source_generation=2,
    )
    fresh_job = workflow.ensure(fresh_done)

    assert store.get(old_job.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(fresh_job.job_id).state is WorkflowJobState.QUEUED
    assert store.get(merged_job.job_id).state is WorkflowJobState.QUEUED
    # A late replay of the superseded generation cannot displace the current
    # exact-target owner.
    with pytest.raises(AuditWorkflowIdentityError, match="source generation is stale"):
        workflow.ensure(old_done)
    assert store.get(fresh_job.job_id).state is WorkflowJobState.QUEUED


def test_authorized_fresh_audit_identity_rearms_same_semantic_job(durable):
    workflow, store, _clock = durable
    exhausted_record = record(audit_id="audit-exhausted")
    running = workflow.start(
        exhausted_record,
        attempt_id="attempt-exhausted",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    exhausted = workflow.action_required(
        running,
        record=exhausted_record,
        action_code="no_independent_auditor",
        reason="candidate set exhausted",
    )
    assert exhausted.state is WorkflowJobState.EXHAUSTED

    rearmed_record = record(
        audit_id="audit-owner-rearm",
        source_generation=2,
    )
    # A fresh UUID alone is not owner authority and cannot revive terminal
    # semantic work.
    assert workflow.ensure(rearmed_record).state is WorkflowJobState.EXHAUSTED
    authorization = {
        "version": 1,
        "audit_id": rearmed_record.audit_id,
        "superseded_audit_id": exhausted_record.audit_id,
        "project_id": rearmed_record.project_id,
        "task_id": rearmed_record.task_id,
        "target_state": rearmed_record.target_state.value,
        "evidence_fingerprint": rearmed_record.evidence_fingerprint.digest,
        "source_generation": 2,
        "actor": {"identity": "project-owner", "source": "api"},
        "reason": "owner requested infrastructure recovery",
        "authorized_at": "2026-08-05T12:00:00+00:00",
        "mode": "infrastructure_recovery",
    }
    rearmed = workflow.rearm(rearmed_record, authorization=authorization)

    assert rearmed.job_id == exhausted.job_id
    assert rearmed.state is WorkflowJobState.QUEUED
    assert rearmed.attempts == 0
    assert rearmed.checkpoint is None
    assert len(store.list_jobs(project_id="project-a", task_id="TASK-1")) == 1
    assert workflow.ensure(rearmed_record).job_id == rearmed.job_id
    assert workflow.retire_resolved(
        project_id="project-a",
        task_id="TASK-1",
        records=[
            replace(exhausted_record, request_state=RequestState.SUPERSEDED),
            rearmed_record,
        ],
    ) == 0
    assert store.get(rearmed.job_id).state is WorkflowJobState.QUEUED


def test_invalid_rearm_proof_cannot_revive_exhausted_work(durable):
    workflow, store, _clock = durable
    current = record(audit_id="audit-old")
    running = workflow.start(
        current,
        attempt_id="attempt-old",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    workflow.action_required(
        running,
        record=current,
        action_code="no_independent_auditor",
        reason="candidate set exhausted",
    )
    current_evidence = record(
        audit_id="audit-current-evidence",
        evidence="evidence-2",
        source_generation=2,
    )
    current_job = workflow.ensure(current_evidence)
    fresh = record(audit_id="audit-new", source_generation=3)

    with pytest.raises(AuditWorkflowIdentityError, match="does not match"):
        workflow.rearm(
            fresh,
            authorization={
                "version": 1,
                "audit_id": fresh.audit_id,
                "superseded_audit_id": "audit-wrong",
                "project_id": fresh.project_id,
                "task_id": fresh.task_id,
                "target_state": fresh.target_state.value,
                "evidence_fingerprint": fresh.evidence_fingerprint.digest,
                "source_generation": 3,
                "actor": {"identity": "owner"},
                "reason": "retry",
                "authorized_at": "2026-08-05T12:00:00+00:00",
                "mode": "infrastructure_recovery",
            },
        )
    assert store.get(running.job_id).state is WorkflowJobState.EXHAUSTED
    assert store.get(current_job.job_id).state is WorkflowJobState.QUEUED
    assert workflow.ensure(current_evidence).job_id == current_job.job_id


def test_late_unseen_evidence_cannot_displace_newer_source_generation(durable):
    workflow, store, _clock = durable
    newest = record(evidence="newest", source_generation=3)
    newest_job = workflow.ensure(newest)
    stale = record(
        audit_id="audit-stale",
        evidence="unseen-older",
        source_generation=2,
    )

    with pytest.raises(AuditWorkflowIdentityError, match="source generation is stale"):
        workflow.ensure(stale)

    assert store.get(newest_job.job_id).state is WorkflowJobState.QUEUED
    stale_jobs = [
        job for job in store.list_jobs(task_id="TASK-1")
        if job.expected_evidence_revision == stale.evidence_fingerprint.digest
    ]
    assert len(stale_jobs) == 1
    assert stale_jobs[0].state is WorkflowJobState.SUPERSEDED


def test_one_source_generation_cannot_publish_conflicting_evidence(durable):
    workflow, store, _clock = durable
    accepted = workflow.ensure(record(evidence="first", source_generation=2))

    with pytest.raises(WorkflowJobStoreError, match="conflicting evidence"):
        workflow.ensure(record(evidence="second", source_generation=2))

    assert store.get(accepted.job_id).state is WorkflowJobState.QUEUED


def test_newer_recurrence_reuses_terminal_semantics_and_stops_older_lane(durable):
    workflow, store, _clock = durable
    first = record(evidence="same", source_generation=1)
    running = workflow.start(
        first,
        attempt_id="attempt-first",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    completed = workflow.complete(running, result={"accepted": True})
    intervening = workflow.ensure(
        record(audit_id="audit-other", evidence="other", source_generation=2)
    )

    replay = workflow.ensure(
        record(audit_id="audit-recurrence", evidence="same", source_generation=3)
    )

    assert replay.job_id == completed.job_id
    assert replay.state is WorkflowJobState.COMPLETED
    assert store.get(intervening.job_id).state is WorkflowJobState.SUPERSEDED


def test_superseded_semantics_get_one_restart_stable_fresh_activation(
    tmp_path,
) -> None:
    db_path = str(tmp_path / "workflow.sqlite3")
    clock = Clock()
    store = WorkflowJobStore(db_path, clock=clock)
    workflow = TerminalAuditWorkflow(store, clock=clock)
    first = record(audit_id="audit-e1", evidence="e1", source_generation=1)
    first_job = workflow.ensure(first)
    second = record(audit_id="audit-e2", evidence="e2", source_generation=2)
    second_job = workflow.ensure(second)
    assert store.get(first_job.job_id).state is WorkflowJobState.SUPERSEDED

    recurrence = record(
        audit_id="audit-e1-recurrence",
        evidence="e1",
        source_generation=3,
    )
    activated = workflow.ensure(recurrence)

    assert activated.job_id != first_job.job_id
    assert activated.state is WorkflowJobState.QUEUED
    assert activated.idempotency_key.endswith(":activation:3")
    assert store.get(second_job.job_id).state is WorkflowJobState.SUPERSEDED
    assert workflow.ensure(recurrence).job_id == activated.job_id
    store.close()

    reopened_store = WorkflowJobStore(db_path, clock=clock)
    reopened = TerminalAuditWorkflow(reopened_store, clock=clock)
    assert reopened.ensure(recurrence).job_id == activated.job_id
    with pytest.raises(AuditWorkflowIdentityError, match="source generation is stale"):
        reopened.ensure(first)
    assert reopened_store.get(activated.job_id).state is WorkflowJobState.QUEUED
    reopened_store.close()


def test_cancelled_semantics_require_a_newer_source_for_fresh_activation(
    durable,
) -> None:
    workflow, store, _clock = durable
    first = record(audit_id="audit-cancelled", source_generation=1)
    running = workflow.start(
        first,
        attempt_id="attempt-cancelled",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    cancelled = workflow.cancel(running, reason="authority was revoked")
    assert cancelled.state is WorkflowJobState.CANCELLED

    with pytest.raises(AuditWorkflowIdentityError, match="source generation is stale"):
        workflow.ensure(first)

    recurrence = replace(
        first,
        audit_id="audit-cancelled-recurrence",
        source_generation=2,
    )
    activated = workflow.ensure(recurrence)

    assert activated.job_id != cancelled.job_id
    assert activated.state is WorkflowJobState.QUEUED
    assert activated.idempotency_key.endswith(":activation:2")


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
        workflow.decision(record(evidence="evidence-2", source_generation=2)).phase
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

    recovered = workflow.recover(current, active_attempt_identities=set())
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

    workflow.recover(first, active_attempt_identities=set())

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
        workflow.recover(current, active_attempt_identities=set()).phase
        is AuditWorkflowPhase.FINALIZING
    )
    reclaimed = workflow.reclaim_finalizing(
        store.get(finalizing.job_id),
        current,
        active_attempt_identities=set(),
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


def test_generic_expiry_and_claim_preserve_typed_finalization(durable):
    workflow, store, clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-finalizing",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    finalizing = workflow.mark_finalizing(
        running,
        current,
        result=result(current, attempt_id="attempt-finalizing"),
        attempt_id="attempt-finalizing",
        lease_token=running.lease_token,
    )
    checkpoint = finalizing.checkpoint
    clock.advance(31)

    assert store.recover_expired() == 0
    other = record(task_id="TASK-2", audit_id="audit-2", evidence="evidence-2")
    other_running = workflow.start(
        other,
        attempt_id="attempt-other",
        candidate=Candidate("provider-b", "model-b"),
    )

    assert other_running is not None
    preserved = store.get(finalizing.job_id)
    assert preserved.state is WorkflowJobState.RUNNING
    assert preserved.phase == AuditWorkflowPhase.FINALIZING.value
    assert preserved.checkpoint == checkpoint
    reclaimed = workflow.reclaim_finalizing(
        preserved,
        current,
        active_attempt_identities=set(),
    )
    assert reclaimed is not None
    assert reclaimed.lease_token != finalizing.lease_token


def test_finalizing_result_digest_rejects_checkpoint_corruption(durable):
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
    checkpoint = dict(finalizing.checkpoint or {})
    result_payload = dict(checkpoint["result"])
    result_payload["verdict"] = Verdict.FAIL.value
    checkpoint["result"] = result_payload
    corrupted = replace(finalizing, checkpoint=checkpoint)

    with pytest.raises(AuditWorkflowIdentityError, match="digest does not match"):
        workflow.finalizing_result_payload(corrupted)

    persisted = store.checkpoint(
        finalizing.job_id,
        finalizing.lease_token,
        phase=AuditWorkflowPhase.FINALIZING.value,
        checkpoint=checkpoint,
    )
    sibling = record(
        audit_id="audit-sibling",
        evidence="sibling",
        target=TargetState.MERGED,
    )
    workflow.ensure(sibling)

    quarantined = workflow.quarantine_finalizing(
        persisted,
        active_attempt_identities=set(),
        reason="checkpoint digest mismatch",
    )

    assert quarantined is not None
    assert quarantined.state is WorkflowJobState.EXHAUSTED
    assert quarantined.phase == AuditWorkflowPhase.ACTION_REQUIRED.value
    assert quarantined.checkpoint["action_code"] == "corrupt_finalization_checkpoint"
    assert workflow.start(
        sibling,
        attempt_id="attempt-sibling",
        candidate=Candidate("provider-b", "model-b"),
    ) is not None


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
        workflow.reclaim_finalizing(
            deferred, current, active_attempt_identities=set()
        )
        is None
    )
    clock.advance(5)
    reclaimed = workflow.reclaim_finalizing(
        store.get(finalizing.job_id),
        current,
        active_attempt_identities=set(),
    )
    assert reclaimed is not None
    assert reclaimed.lease_token != finalizing.lease_token


def test_finalization_transport_retries_are_bounded_action_required(durable):
    workflow, store, clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-1",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None
    current_job = workflow.mark_finalizing(
        running,
        current,
        result=result(current),
        attempt_id="attempt-1",
        lease_token=running.lease_token,
    )

    for expected_failure in (1, 2):
        current_job = workflow.defer_finalizing(current_job)
        assert current_job.checkpoint["finalization_failures"] == expected_failure
        clock.advance(5)
    exhausted = workflow.defer_finalizing(current_job)

    assert exhausted.state is WorkflowJobState.EXHAUSTED
    assert exhausted.phase == AuditWorkflowPhase.ACTION_REQUIRED.value
    assert exhausted.checkpoint["action_code"] == "finalization_transport_exhausted"
    assert store.get(exhausted.job_id).lease_token is None


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
        active_attempt_identities=set(),
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


def test_same_attempt_id_in_other_project_does_not_preserve_abandoned_owner(durable):
    workflow, _store, _clock = durable
    current = record()
    running = workflow.start(
        current,
        attempt_id="attempt-shared",
        candidate=Candidate("provider-a", "model-a"),
    )
    assert running is not None

    recovered = workflow.recover(
        current,
        active_attempt_identities={
            audit_attempt_identity(
                "project-b",
                current.task_id,
                current.audit_id,
                "attempt-shared",
            )
        },
    )

    assert recovered.phase is AuditWorkflowPhase.RETRY_WAIT
