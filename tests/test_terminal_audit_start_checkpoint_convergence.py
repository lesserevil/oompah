"""Regression coverage for bounded terminal-audit start preflight failure."""

from __future__ import annotations

import asyncio
import copy
import threading
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from oompah.models import Issue
from oompah.orchestrator import Orchestrator, _AuditCandidateScan
from oompah.roles import Candidate
from oompah.statuses import IN_VALIDATION
from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadataStore,
)
from oompah.terminal_audit_workflow import TerminalAuditWorkflow
from oompah.workflow_jobs import WorkflowJobState, WorkflowJobStore


PROJECT_ID = "project-start-checkpoint"
TASK_ID = "TASK-START-CHECKPOINT"


class _ProjectLocks:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    def project_write_lock(self, _project_id: str) -> threading.RLock:
        return self._lock


class _Tracker:
    def __init__(self, issue: Issue) -> None:
        self.issue = issue
        self.metadata: dict[str, dict] = {}

    def get_metadata(self, identifier: str) -> dict:
        return copy.deepcopy(self.metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        self.metadata.setdefault(identifier, {})[key] = copy.deepcopy(value)

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return copy.deepcopy(self.issue) if identifier == self.issue.identifier else None


class _OversizedCandidateSelector:
    def select_candidates(
        self,
        _contributors: object,
        *,
        exclude: object,
    ) -> tuple[list[Candidate], None]:
        del exclude
        # The workflow checkpoint JSON escapes each emoji, taking this safely
        # beyond its byte bound even after the text field is character-capped.
        return [Candidate("😀" * 512, "model-a")], None


def _audit_metrics() -> dict[str, object]:
    return {
        "dispatch_count": 0,
        "rotation_count": 0,
        "exhaustion_count": 0,
        "in_progress_count": 0,
        "last_error": None,
    }


def _orchestrator(
    tracker: _Tracker,
    locks: _ProjectLocks,
    workflow_store: WorkflowJobStore,
) -> Orchestrator:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.workflow_job_store = workflow_store
    orchestrator.terminal_audit_workflow = TerminalAuditWorkflow(workflow_store)
    orchestrator.project_store = locks
    orchestrator._tick_pool = None
    orchestrator._audit_rollback_persistence_failed = False
    orchestrator._audit_rollback_lock = threading.RLock()
    orchestrator._pending_audit_rollbacks = {}
    orchestrator._maintenance_cursors = {}
    orchestrator._state_io_lock = threading.RLock()
    orchestrator._save_state = MagicMock(return_value=True)
    orchestrator._audit_metrics = _audit_metrics()
    orchestrator.state = SimpleNamespace(claimed=set(), claimed_issues={})
    orchestrator._reconcile_audit_budget_reservations = MagicMock()
    orchestrator._refresh_terminal_audit_validation_configuration_alerts = MagicMock()
    orchestrator._terminal_audit_validation_configuration_error = MagicMock(
        return_value=None
    )
    orchestrator._record_terminal_audit_validation_configuration = MagicMock()
    orchestrator._clear_terminal_audit_validation_configuration = MagicMock()
    orchestrator._running_values_snapshot = lambda: []
    orchestrator._is_project_paused = MagicMock(return_value=False)
    orchestrator._dispatch_is_blocked = MagicMock(return_value=False)
    orchestrator._is_rate_limited = MagicMock(return_value=False)
    orchestrator._available_slots = MagicMock(return_value=1)
    orchestrator._fetch_audit_candidates = lambda: _AuditCandidateScan(
        (tracker.fetch_issue_detail(TASK_ID),)
    )
    orchestrator._tracker_for_project = lambda _project_id: tracker
    orchestrator._tracker_for_issue = lambda _issue: tracker
    orchestrator._revisionless_archive_evidence = MagicMock(return_value=None)
    orchestrator._bind_audit_record_revision = MagicMock(
        side_effect=lambda _issue, record: record
    )
    orchestrator._audit_branch_claims = {}
    orchestrator._dispatch = AsyncMock()
    orchestrator._route_no_auditor = AsyncMock()
    orchestrator._refresh_terminal_audit_health = MagicMock()
    orchestrator._record_audit_outcome_ownership = MagicMock()
    selector = _OversizedCandidateSelector()

    async def _prepare_selector(_issue: Issue) -> tuple[object, None]:
        return selector, None

    orchestrator._prepare_audit_selector = _prepare_selector
    orchestrator.config = SimpleNamespace(
        audit_priority=100,
        audit_lane_scan_limit=100,
        audit_lane_operation_limit=8,
        audit_lane_max_runtime_seconds=15.0,
        audit_lane_dispatch_limit=2,
        audit_max_attempts=2,
        audit_max_transport_retries=3,
        audit_attempt_ttl=3600,
        max_retry_backoff_ms=0,
    )
    return orchestrator


def test_oversized_start_checkpoint_converges_to_action_required(
    tmp_path,
) -> None:
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Bound invalid audit start checkpoint",
        state=IN_VALIDATION,
        project_id=PROJECT_ID,
    )
    tracker = _Tracker(issue)
    locks = _ProjectLocks()
    record = TerminalAuditRecord(
        audit_id="audit-start-checkpoint",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint("a" * 64),
        request_state=RequestState.PENDING,
        requested_by=ContributorIdentity("oompah", "orchestrator"),
        workflow_revision="workflow-revision-a",
    )
    metadata = TerminalAuditMetadataStore(tracker, locks, PROJECT_ID)
    metadata.update(
        TASK_ID,
        lambda document: replace(document, pending_chain=[record]),
    )
    workflow_store = WorkflowJobStore(str(tmp_path / "workflow.sqlite3"))
    orchestrator = _orchestrator(tracker, locks, workflow_store)

    for expected_attempts in (1, 2):
        asyncio.run(orchestrator._dispatch_audit_lane())
        current = metadata.read(TASK_ID).pending_chain[0]

        assert len(current.attempts) == expected_attempts
        assert all(
            attempt.failure_classification
            is FailureClassification.INFRASTRUCTURE_ERROR
            and attempt.provider_id is None
            and attempt.model is None
            and attempt.request_state is RequestState.PENDING
            for attempt in current.attempts
        )
        queued = orchestrator.terminal_audit_workflow.ensure(current)
        assert queued.state is WorkflowJobState.QUEUED
        assert queued.attempts == 0
        assert queued.lease_token is None
        assert queued.checkpoint is None
        assert "😀" not in repr(tracker.metadata[TASK_ID][METADATA_KEY])

    asyncio.run(orchestrator._dispatch_audit_lane())

    current = metadata.read(TASK_ID).pending_chain[0]
    action_job = orchestrator.terminal_audit_workflow.ensure(current)
    assert action_job.state is WorkflowJobState.EXHAUSTED
    assert action_job.phase == "action_required"
    assert action_job.checkpoint["action_code"] == "audit_start_checkpoint_invalid"
    orchestrator._route_no_auditor.assert_awaited_once()
    assert orchestrator._route_no_auditor.await_args.kwargs["action_job"].job_id == (
        action_job.job_id
    )
    orchestrator._dispatch.assert_not_awaited()
    workflow_store.close()
