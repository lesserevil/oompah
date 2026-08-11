from __future__ import annotations

import copy
import hashlib
import threading
from dataclasses import replace

from oompah.models import Issue
from oompah.orchestrator import Orchestrator
from oompah.terminal_audit import (
    AuditAttempt,
    EvidenceFingerprint,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_metadata import TerminalAuditMetadataStore


PROJECT_ID = "project-cas"
TASK_ID = "TASK-CAS"


class _Tracker:
    def __init__(self) -> None:
        self.metadata: dict[str, dict] = {}

    def get_metadata(self, identifier: str) -> dict:
        return copy.deepcopy(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        self.metadata.setdefault(identifier, {})[key] = copy.deepcopy(value)


class _ProjectLocks:
    def __init__(self) -> None:
        self.lock = threading.RLock()

    def project_write_lock(self, _project_id: str) -> threading.RLock:
        return self.lock


def _record() -> TerminalAuditRecord:
    return TerminalAuditRecord(
        audit_id="audit-cas",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint(
            hashlib.sha256(b"exact evidence").hexdigest()
        ),
        request_state=RequestState.PENDING,
        workflow_revision="workflow-revision-1",
        source_generation=1,
    )


def test_dispatch_cas_allows_only_monotonic_first_revision_binding() -> None:
    tracker = _Tracker()
    store = TerminalAuditMetadataStore(tracker, _ProjectLocks(), PROJECT_ID)
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="CAS task",
        state="In Validation",
        project_id=PROJECT_ID,
    )
    unbound = _record()
    store.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[unbound]),
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    bound = replace(
        unbound,
        selected_ref="refs/heads/main",
        selected_sha="a" * 40,
    )

    assert orchestrator._audit_update_record(
        store,
        issue,
        bound,
        promote_binding_only=True,
    )
    assert store.read(TASK_ID).pending_chain == [bound]

    stale_rebind = replace(bound, selected_sha="b" * 40)
    assert not orchestrator._audit_update_record(
        store,
        issue,
        stale_rebind,
        promote_binding_only=True,
    )
    assert not orchestrator._audit_update_record(
        store,
        issue,
        unbound,
        promote_binding_only=True,
    )
    assert store.read(TASK_ID).pending_chain == [bound]


def test_dispatch_cas_rejects_cross_authority_first_binding() -> None:
    tracker = _Tracker()
    store = TerminalAuditMetadataStore(tracker, _ProjectLocks(), PROJECT_ID)
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="CAS task",
        state="In Validation",
        project_id=PROJECT_ID,
    )
    current = _record()
    store.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[current]),
    )
    stale = replace(
        current,
        workflow_revision="workflow-revision-2",
        selected_ref="refs/heads/main",
        selected_sha="a" * 40,
    )
    orchestrator = Orchestrator.__new__(Orchestrator)

    assert not orchestrator._audit_update_record(
        store,
        issue,
        stale,
        promote_binding_only=True,
    )
    assert store.read(TASK_ID).pending_chain == [current]


def test_delayed_same_binding_snapshot_cannot_rewind_launched_attempt() -> None:
    tracker = _Tracker()
    store = TerminalAuditMetadataStore(tracker, _ProjectLocks(), PROJECT_ID)
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="CAS task",
        state="In Validation",
        project_id=PROJECT_ID,
    )
    unbound = _record()
    store.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[unbound]),
    )
    orchestrator = Orchestrator.__new__(Orchestrator)
    delayed_bound_snapshot = replace(
        unbound,
        selected_ref="refs/heads/main",
        selected_sha="a" * 40,
    )
    assert orchestrator._audit_update_record(
        store,
        issue,
        delayed_bound_snapshot,
        promote_binding_only=True,
    )

    attempt = AuditAttempt(
        attempt_id="attempt-current",
        target_state=unbound.target_state,
        evidence_fingerprint=unbound.evidence_fingerprint,
        request_state=RequestState.IN_PROGRESS,
        provider_id="provider-a",
        model="model-a",
        selected_ref="refs/heads/main",
        selected_sha="a" * 40,
    )
    launched = replace(
        delayed_bound_snapshot,
        request_state=RequestState.IN_PROGRESS,
        attempts=[attempt],
        updated_at="2026-08-11T12:00:00+00:00",
    )
    assert orchestrator._audit_update_record(
        store,
        issue,
        launched,
        append_attempt=attempt,
    )

    assert not orchestrator._audit_update_record(
        store,
        issue,
        delayed_bound_snapshot,
        promote_binding_only=True,
    )
    document = store.read(TASK_ID)
    assert document.pending_chain == [launched]
    assert document.attempt_history == [attempt]


def test_exact_bound_failed_attempt_update_remains_supported() -> None:
    tracker = _Tracker()
    store = TerminalAuditMetadataStore(tracker, _ProjectLocks(), PROJECT_ID)
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="CAS task",
        state="In Validation",
        project_id=PROJECT_ID,
    )
    bound = replace(
        _record(),
        selected_ref="refs/heads/main",
        selected_sha="a" * 40,
    )
    store.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[bound]),
    )
    failed_attempt = AuditAttempt(
        attempt_id="attempt-failed",
        target_state=bound.target_state,
        evidence_fingerprint=bound.evidence_fingerprint,
        failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
        failure_reason="transport unavailable",
        selected_ref="refs/heads/main",
        selected_sha="a" * 40,
    )
    failed = replace(
        bound,
        attempts=[failed_attempt],
        updated_at="2026-08-11T12:01:00+00:00",
    )
    orchestrator = Orchestrator.__new__(Orchestrator)

    assert orchestrator._audit_update_record(
        store,
        issue,
        failed,
        append_attempt=failed_attempt,
    )
    document = store.read(TASK_ID)
    assert document.pending_chain == [failed]
    assert document.attempt_history == [failed_attempt]
