"""Regressions for exact terminal-audit shadow authority."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.roles import Candidate
from oompah.terminal_audit import (
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadata
from oompah.terminal_audit_workflow import TerminalAuditWorkflow
from oompah.work_decision import evaluate_task
from oompah.workflow_contract import TaskDisposition
from oompah.workflow_facts import (
    FactDomain,
    FactObservation,
    FactState,
    REQUIRED_FACT_DOMAINS,
    WorkflowFactCollector,
    WorkflowFacts,
)
from oompah.workflow_jobs import WorkflowJobStore


NOW = datetime(2026, 8, 8, 12, tzinfo=timezone.utc)


def _record(
    *,
    audit_id: str,
    target: TargetState,
    evidence: str,
) -> TerminalAuditRecord:
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id="project-a",
        task_id="TASK-1",
        target_state=target,
        evidence_fingerprint=EvidenceFingerprint(
            hashlib.sha256(evidence.encode()).hexdigest()
        ),
        request_state=RequestState.PENDING,
        source_generation=1,
    )


def _issue() -> Issue:
    return Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="audit task",
        state="In Validation",
        project_id="project-a",
        issue_type="task",
    )


def _orchestrator(store: WorkflowJobStore, metadata_store: object) -> Orchestrator:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workflow_job_store = store
    orchestrator.terminal_audit_workflow = TerminalAuditWorkflow(store)
    orchestrator._audit_store = lambda _issue: metadata_store
    return orchestrator


def _decision(issue: Issue, terminal: FactObservation):
    observed = {
        domain: FactObservation.missing(
            domain, observed_at=NOW.isoformat(), source="test"
        )
        for domain in REQUIRED_FACT_DOMAINS
    }
    observed.update(
        {
            FactDomain.TASK: FactObservation.known(
                FactDomain.TASK,
                {
                    "identifier": issue.identifier,
                    "project_id": issue.project_id,
                    "status": issue.state,
                },
                observed_at=NOW.isoformat(),
                source="test",
            ),
            FactDomain.DEPENDENCIES: FactObservation.known(
                FactDomain.DEPENDENCIES,
                {"finish": [], "hard_start": []},
                observed_at=NOW.isoformat(),
                source="test",
            ),
            FactDomain.CONTAINMENT: FactObservation.known(
                FactDomain.CONTAINMENT,
                {"children": []},
                observed_at=NOW.isoformat(),
                source="test",
            ),
            FactDomain.RETRY_BUDGET: FactObservation.known(
                FactDomain.RETRY_BUDGET,
                {"remaining": 3},
                observed_at=NOW.isoformat(),
                source="test",
            ),
            FactDomain.CONFIG: FactObservation.known(
                FactDomain.CONFIG,
                {},
                observed_at=NOW.isoformat(),
                source="test",
            ),
            FactDomain.TERMINAL_AUDIT: terminal,
        }
    )
    facts = WorkflowFacts(
        "project-a", issue.identifier, NOW.isoformat(), observed
    )
    return evaluate_task(issue, facts, now=NOW)


def test_sibling_target_running_job_cannot_make_pending_audit_owned(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    try:
        pending = _record(
            audit_id="audit-done", target=TargetState.DONE, evidence="done"
        )
        sibling = _record(
            audit_id="audit-merged",
            target=TargetState.MERGED,
            evidence="merged",
        )
        workflow = TerminalAuditWorkflow(store)
        assert workflow.start(
            sibling,
            attempt_id="attempt-sibling",
            candidate=Candidate("provider-a", "model-a"),
        ) is not None
        metadata = SimpleNamespace(
            read=lambda _identifier: TerminalAuditMetadata(
                pending_chain=[pending]
            )
        )
        orchestrator = _orchestrator(store, metadata)
        source = orchestrator._workflow_shadow_sources(_issue())[
            FactDomain.TERMINAL_AUDIT
        ]

        value = source(_issue())
        assert value["audit_id"] == pending.audit_id
        assert value["target_state"] == TargetState.DONE.value
        assert value["audit_job_present"] is False
        observation = FactObservation.known(
            FactDomain.TERMINAL_AUDIT,
            value,
            observed_at=NOW.isoformat(),
            source="test",
        )
        decision = _decision(_issue(), observation)
        assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
        assert decision.reason_code == "validation.queued"
    finally:
        store.close()


@pytest.mark.parametrize(
    "repair_status",
    ["Needs CI Fix", "Open", "Needs Human", "Done", "Merged", "Archived"],
)
def test_terminal_audit_fact_revokes_orphaned_record_outside_validation(
    tmp_path,
    repair_status,
):
    store = WorkflowJobStore(str(tmp_path / f"{repair_status}.sqlite3"))
    try:
        record = _record(
            audit_id="audit-orphaned",
            target=TargetState.DONE,
            evidence="orphaned",
        )
        workflow = TerminalAuditWorkflow(store)
        old_job = workflow.start(
            record,
            attempt_id="attempt-orphaned",
            candidate=Candidate("provider-a", "model-a"),
        )
        assert old_job is not None
        records = [record]
        metadata = SimpleNamespace(
            read=lambda _identifier: TerminalAuditMetadata(pending_chain=records)
        )
        orchestrator = _orchestrator(store, metadata)
        issue = _issue()
        issue.state = repair_status

        value = orchestrator._workflow_shadow_sources(issue)[
            FactDomain.TERMINAL_AUDIT
        ](issue)

        assert value is None or "audit_id" not in value

        fresh = replace(
            record,
            audit_id="audit-fresh",
            source_generation=record.source_generation + 1,
        )
        workflow.cancel(old_job, reason="repair status revoked old generation")
        assert workflow.start(
            fresh,
            attempt_id="attempt-fresh",
            candidate=Candidate("provider-a", "model-a"),
        ) is not None
        records[:] = [
            replace(record, request_state=RequestState.CANCELLED),
            fresh,
        ]
        issue.state = "In Validation"
        active = orchestrator._workflow_shadow_sources(issue)[
            FactDomain.TERMINAL_AUDIT
        ](issue)
        assert active["audit_id"] == fresh.audit_id
        assert active["request_state"] == RequestState.PENDING.value
        assert active["audit_job_present"] is True
    finally:
        store.close()


@pytest.mark.parametrize("metadata_state", ["missing", "error"])
def test_missing_or_failed_terminal_metadata_fails_closed(
    tmp_path, metadata_state
):
    store = WorkflowJobStore(str(tmp_path / f"{metadata_state}.sqlite3"))
    try:
        if metadata_state == "missing":
            metadata = SimpleNamespace(
                read=lambda _identifier: TerminalAuditMetadata()
            )
        else:
            def fail_read(_identifier):
                raise OSError("metadata unavailable")

            metadata = SimpleNamespace(read=fail_read)
        orchestrator = _orchestrator(store, metadata)
        issue = _issue()
        source = orchestrator._workflow_shadow_sources(issue)[
            FactDomain.TERMINAL_AUDIT
        ]
        collector = WorkflowFactCollector(
            project_id="project-a",
            tracker=Mock(),
            sources={FactDomain.TERMINAL_AUDIT: source},
            clock=lambda: NOW,
        )

        observation = collector._source_observation(
            FactDomain.TERMINAL_AUDIT,
            issue,
            now=NOW,
            now_iso=NOW.isoformat(),
        )
        expected = (
            FactState.MISSING if metadata_state == "missing" else FactState.ERROR
        )
        assert observation.state is expected
        decision = _decision(issue, observation)
        assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
        assert decision.durable_jobs == ("terminal_audit_recovery",)
        assert decision.reason_code.startswith("evidence.terminal_audit_")
    finally:
        store.close()
