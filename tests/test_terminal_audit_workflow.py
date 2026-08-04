from __future__ import annotations

import hashlib

import pytest

from oompah.roles import Candidate
from oompah.terminal_audit import (
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_workflow import (
    AuditWorkflowPhase,
    TerminalAuditWorkflow,
)
from oompah.workflow_jobs import WorkflowJobState, WorkflowJobStore


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def record(*, audit_id: str = "audit-1", evidence: str = "evidence-1"):
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id="project-a",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint(hashlib.sha256(evidence.encode()).hexdigest()),
        request_state=RequestState.PENDING,
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
        verdict="pass",
        result_idempotency="result-1",
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
        assert restored.decision(current).evidence_fingerprint == current.evidence_fingerprint.digest
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
    assert workflow.decision(record(evidence="evidence-2")).phase is AuditWorkflowPhase.QUEUED


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
    assert recovered.phase is AuditWorkflowPhase.QUEUED
    assert workflow.decision(current).phase is AuditWorkflowPhase.QUEUED


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
        verdict="fail",
        failure_classification="missing_evidence",
        result_idempotency="r-1",
    )
    checkpoint = store.get(running.job_id).checkpoint
    assert checkpoint is not None
    assert "output" not in checkpoint
    assert "comments" not in checkpoint
    assert checkpoint["evidence_fingerprint"] == current.evidence_fingerprint.digest
