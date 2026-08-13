"""Production implementation adapter, receipt, and cutover coverage."""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from oompah.implementation_workflow import (
    IMPLEMENTATION_ACTIONS,
    ImplementationAction,
    ImplementationDisposition,
    ImplementationOwnershipSource,
    ImplementationState,
    ImplementationWorkflowHandler,
)
from oompah.implementation_workflow_adapter import (
    ImplementationReceiptStore,
    OrchestratorImplementationEffects,
    ProductionImplementationWorkflowBackend,
    build_implementation_workflow_handlers,
)
from oompah.integration import IntegrationRecord
from oompah.integration_queue import IntegrationQueueStore
from oompah.models import Issue, OwnerClaim
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.orchestrator import Orchestrator
from oompah.statuses import (
    BACKLOG,
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    NEEDS_HUMAN,
    OPEN,
    READY_TO_INTEGRATE,
)
from oompah.task_transition_service import (
    TaskTransitionService,
    TransitionAuthority,
    TransitionDisposition,
    TransitionJournal,
    TransitionOutcome,
    issue_authority_version,
)
from oompah.workflow_runtime import WorkflowRuntime, WorkflowRuntimeError
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobState, WorkflowJobStore
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    VerificationResult,
    WorkflowActionError,
    WorkflowActionSuperseded,
    WorkflowJobContext,
    WorkflowRunDisposition,
)


HEAD_A = "a" * 40
HEAD_B = "b" * 40


class Tracker:
    def __init__(self, *issues: Issue) -> None:
        self.issues = {issue.identifier: issue for issue in issues}
        self.status_writes: list[tuple[str, str]] = []

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        return self.issues.get(identifier)

    def fetch_all_issues(self) -> list[Issue]:
        return list(self.issues.values())

    def update_issue(self, identifier: str, *, status: str, **_kwargs):
        self.status_writes.append((identifier, status))
        self.issues[identifier].state = status


class FakeOrchestrator:
    def __init__(self, path: Path, trackers: dict[str, Tracker]) -> None:
        self.workflow_job_store = WorkflowJobStore(str(path / "jobs.sqlite3"))
        self.trackers = trackers
        self.running = {}
        self.claims = {}
        self.dispatches = []
        self.cancelled = []
        self.released = []
        self.enqueued = []
        self.duplicate_claims = []
        self.state_notifications = 0
        self.admit_dispatch = True
        self.state = SimpleNamespace(owner_claims={}, reject_streak={})
        self._owner_claims_lock = threading.RLock()
        self._project_write_lock = threading.RLock()
        self.project_store = SimpleNamespace(
            project_write_lock=lambda _project_id: self._project_write_lock
        )
        self.config = SimpleNamespace(
            workflow_engine_mode="off",
            parallel_epic_children_enabled=True,
        )

    def _tracker_for_project(self, project_id):
        return self.trackers[project_id]

    def _current_running_entry(self, issue_id):
        return self.running.get(issue_id)

    def _should_dispatch(self, issue, **kwargs):
        if not self.admit_dispatch:
            self.state.reject_streak[issue.id] = ("no_slots", 1)
        return self.admit_dispatch

    async def _dispatch(self, issue, attempt, override_profile=None, **kwargs):
        self.dispatches.append((issue.identifier, attempt, override_profile, kwargs))
        assignment_id = f"assignment-{len(self.dispatches)}"
        issue.assignment_id = assignment_id
        self.running[issue.id] = SimpleNamespace(
            issue=issue,
            run_id=f"run-{len(self.dispatches)}",
            assignment_id=assignment_id,
            authority_generation=kwargs.get("workflow_generation"),
        )

    def _cancel_retry_for_issue(self, **kwargs):
        self.cancelled.append(kwargs)
        entry = self.running.get(kwargs.get("issue_id"))
        if entry is not None:
            entry.authority_revoked = True
        return 0

    async def _terminate_running(self, issue_id, *, cleanup_workspace):
        del cleanup_workspace
        self.running.pop(issue_id, None)
        return True

    def _owner_claim_for_issue(self, issue_id, project_id):
        return self.claims.get((project_id, issue_id))

    def grant_owner_claim(
        self,
        *,
        issue_id,
        project_id,
        owner_login,
        ttl_hours=None,
        claim_id=None,
    ):
        del ttl_hours
        now = datetime.now(timezone.utc).timestamp()
        claim = OwnerClaim(
            claim_id or "claim-1",
            issue_id,
            project_id,
            owner_login,
            now,
            now + 3600,
        )
        self.claims[(project_id, issue_id)] = claim
        return claim

    def release_owner_claim(
        self, *, issue_id, project_id, expected_claim_id=None
    ):
        self.released.append((project_id, issue_id))
        current = self.claims.get((project_id, issue_id))
        if expected_claim_id is not None and str(
            getattr(current, "claim_id", None) or ""
        ) != str(expected_claim_id or ""):
            return False
        return self.claims.pop((project_id, issue_id), None) is not None

    def enqueue_durable_worker_submission(self, project_id, issue, record):
        self.enqueued.append((project_id, issue.identifier, record.head_sha))

    def _notify_state_only(self):
        self.state_notifications += 1

    def _claim_duplicate_preflight(self, issue, **kwargs):
        self.duplicate_claims.append((issue.identifier, kwargs))
        return SimpleNamespace(issue_id=issue.id)


def make_issue(project="project-a", identifier="TASK-1", head=HEAD_A, status=OPEN):
    return Issue(
        id=f"{project}:{identifier}",
        identifier=identifier,
        title="Adapter task",
        description="Exercise the production implementation adapter.",
        state=status,
        project_id=project,
        work_branch=identifier,
        target_branch="main",
        head_sha=head,
    )


def make_context(
    tmp_path: Path,
    *,
    project="project-a",
    identifier="TASK-1",
    generation="generation-1",
    action=ImplementationAction.START,
    payload=None,
    head=HEAD_A,
    evidence=None,
    max_attempts=5,
):
    store = WorkflowJobStore(str(tmp_path / f"{project}-{generation}.sqlite3"))
    job = store.enqueue(
        WorkflowJobSpec(
            project_id=project,
            task_id=identifier,
            generation=generation,
            action=action.value,
            idempotency_key=f"implementation:{identifier}:{generation}",
            payload=payload,
            expected_evidence_revision=evidence,
            expected_head_sha=head,
            max_attempts=max_attempts,
        )
    )
    return store, WorkflowJobContext(job, asyncio.Event(), asyncio.Event())


def disposition(context, *, owner="worker-1"):
    return ImplementationDisposition(
        context.job.project_id,
        context.job.task_id,
        context.job.generation,
        context.job.action,
        ImplementationState.ACTIVE,
        ImplementationOwnershipSource.AGENT,
        owner_id=owner,
        work_branch=context.job.task_id,
        head_sha=context.job.expected_head_sha,
        lease_expires_at="2099-01-01T00:00:00+00:00",
    )


def test_receipts_are_exact_project_scoped_and_restart_durable(tmp_path):
    _store_a, context_a = make_context(tmp_path, project="project-a")
    _store_b, context_b = make_context(tmp_path, project="project-b")
    path = tmp_path / "receipts.sqlite3"
    first = ImplementationReceiptStore(str(path))
    first.record(context_a, disposition(context_a, owner="a"))
    first.record(context_b, disposition(context_b, owner="b"))
    first.close()

    restarted = ImplementationReceiptStore(str(path))
    assert restarted.get(context_a).owner_id == "a"
    assert restarted.get(context_b).owner_id == "b"
    restarted.close()


def test_live_exact_worker_renews_only_its_durable_authority():
    issue = make_issue(status=IN_PROGRESS)
    entry = SimpleNamespace(
        issue=issue,
        identifier=issue.identifier,
        run_id="run-1",
        authority_generation="generation-1",
        retirement_pending=False,
    )
    fake = SimpleNamespace(_current_running_entry=lambda issue_id: entry)
    expired = {
        "state": "active",
        "generation": "generation-1",
        "run_id": "run-1",
        "lease_expires_at": "2020-01-01T00:00:00+00:00",
    }

    renewed = Orchestrator._refresh_durable_implementation_authority(
        fake, issue, expired
    )
    replacement = Orchestrator._refresh_durable_implementation_authority(
        fake, issue, {**expired, "generation": "replacement-generation"}
    )

    assert datetime.fromisoformat(renewed["lease_expires_at"]) > datetime.now(
        timezone.utc
    )
    assert replacement["lease_expires_at"] == expired["lease_expires_at"]


def test_receipt_race_has_one_immutable_winner(tmp_path):
    _jobs, context = make_context(tmp_path)
    path = tmp_path / "receipts.sqlite3"
    left = ImplementationReceiptStore(str(path))
    right = ImplementationReceiptStore(str(path))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda store: store.record(context, disposition(context)),
                (left, right),
            )
        )

    assert {item.authority_revision for item in results} == {
        disposition(context).authority_revision
    }
    left.close()
    right.close()


def test_receipt_rejects_reused_identity_with_different_evidence(tmp_path):
    _jobs, context = make_context(tmp_path, evidence="evidence-a")
    receipts = ImplementationReceiptStore(str(tmp_path / "receipts.sqlite3"))
    receipts.record(context, disposition(context))
    changed = WorkflowJobContext(
        replace(context.job, expected_evidence_revision="evidence-b"),
        asyncio.Event(),
        asyncio.Event(),
    )

    with pytest.raises(WorkflowActionError, match="evidence fence"):
        receipts.get(changed)

    receipts.close()


@pytest.mark.asyncio
async def test_start_dispatches_exact_generation_without_direct_status_write(tmp_path):
    issue = make_issue()
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    _jobs, context = make_context(tmp_path)
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)

    result = await backend.execute(context)
    transition = await backend.build_transition(
        context, VerificationResult(True, {"disposition": result.disposition.to_dict()})
    )

    assert result.status == "started"
    assert result.disposition.generation == "generation-1"
    assert orch.dispatches[0][3]["workflow_generation"] == "generation-1"
    assert orch.dispatches[0][3]["status_managed_by_workflow"] is True
    assert tracker.status_writes == []
    assert transition.requested_status == IN_PROGRESS
    assert transition.evidence_generation == issue.assignment_id
    assert transition.evidence_generation != context.job.generation
    journal = TransitionJournal(str(tmp_path / "start-transition.sqlite3"))
    outcome = await TaskTransitionService(
        project_id="project-a",
        tracker=tracker,
        journal=journal,
    ).execute(transition)
    assert outcome.disposition is TransitionDisposition.APPLIED
    assert outcome.reason_code == "transition.applied"
    assert tracker.status_writes == [(issue.identifier, IN_PROGRESS)]
    journal.close()
    effects.receipts.close()


@pytest.mark.asyncio
async def test_accepted_submission_supersedes_stale_start_before_dispatch(tmp_path):
    issue = make_issue()
    issue.integration = IntegrationRecord(
        state="ready",
        task_branch=issue.work_branch,
        head_sha=HEAD_A,
        base_branch="main",
        base_sha=HEAD_B,
    )
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    _jobs, context = make_context(tmp_path)
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    with pytest.raises(
        WorkflowActionSuperseded,
        match="accepted submission replaced implementation dispatch",
    ):
        await effects.apply(context)

    assert orch.dispatches == []
    effects.receipts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    (ImplementationAction.RECOVERY, ImplementationAction.FOCUS_HANDOFF),
)
async def test_runtime_actions_transition_with_exact_assignment_generation(
    tmp_path,
    action,
):
    issue = make_issue()
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    _jobs, context = make_context(
        tmp_path,
        action=action,
        payload={"expected_status": OPEN, "focus": "implementation"},
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)

    result = await backend.execute(context)
    intent = await backend.build_transition(
        context,
        VerificationResult(True, {"disposition": result.disposition.to_dict()}),
    )

    assert intent.evidence_generation == issue.assignment_id
    assert intent.evidence_generation != context.job.generation
    effects.receipts.close()


@pytest.mark.asyncio
async def test_start_transition_without_exact_assignment_fails_closed(tmp_path):
    issue = make_issue()
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    _jobs, context = make_context(tmp_path)
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)
    disposition = ImplementationDisposition(
        context.job.project_id,
        context.job.task_id,
        context.job.generation,
        context.job.action,
        ImplementationState.ACTIVE,
        ImplementationOwnershipSource.AGENT,
        owner_id="worker-without-assignment",
        work_branch=context.job.task_id,
        head_sha=context.job.expected_head_sha,
        lease_expires_at="2099-01-01T00:00:00+00:00",
    )

    with pytest.raises(
        WorkflowActionError,
        match="no exact assignment identity",
    ):
        await backend.build_transition(
            context,
            VerificationResult(True, {"disposition": disposition.to_dict()}),
        )

    assert tracker.status_writes == []
    effects.receipts.close()


@pytest.mark.asyncio
async def test_start_transition_rejects_replacement_assignment(tmp_path):
    issue = make_issue()
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    _jobs, context = make_context(tmp_path)
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)

    result = await backend.execute(context)
    dispatched_assignment = result.disposition.assignment_id
    issue.assignment_id = "replacement-assignment"

    with pytest.raises(
        WorkflowActionError,
        match="assignment changed before status transition",
    ):
        await backend.build_transition(
            context,
            VerificationResult(
                True,
                {"disposition": result.disposition.to_dict()},
            ),
        )

    assert dispatched_assignment != issue.assignment_id
    assert tracker.status_writes == []
    effects.receipts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("install_replacement", [False, True])
async def test_direct_owner_transition_rejection_compensates_exact_claim(
    tmp_path,
    install_replacement,
):
    issue = make_issue(status=BACKLOG)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    jobs, _context = make_context(
        tmp_path,
        generation="owner-claim-generation",
        action=ImplementationAction.DIRECT_OWNER_CLAIM,
        evidence=issue_authority_version(issue),
        payload={
            "owner_id": "project-owner",
            "claim_id": "claim-rejected-transition",
            "expected_status": BACKLOG,
        },
    )
    orch.workflow_job_store.close()
    orch.workflow_job_store = jobs
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    captured = []

    class RejectingTransitionService:
        async def execute(self, intent):
            captured.append(intent)
            if install_replacement:
                orch.grant_owner_claim(
                    issue_id=issue.id,
                    project_id="project-a",
                    owner_login="replacement-owner",
                    claim_id="replacement-claim",
                )
            return TransitionOutcome(
                transition_id="rejected-owner-transition",
                project_id="project-a",
                task_id=issue.identifier,
                disposition=TransitionDisposition.REJECTED,
                reason_code="transition.test_permanent_rejection",
                observed_status=issue.state,
                observed_version=issue_authority_version(issue),
                requested_status=IN_PROGRESS,
            )

    worker = DurableWorkflowWorker(
        store=jobs,
        handlers={
            ImplementationAction.DIRECT_OWNER_CLAIM.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            )
        },
        transition_services={"project-a": RejectingTransitionService()},
        worker_id="owner-claim-compensation-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    assert captured[0].actor == "project-owner"
    assert captured[0].authority is TransitionAuthority.PROJECT_OWNER
    current = orch._owner_claim_for_issue(issue.id, "project-a")
    if install_replacement:
        assert current is not None
        assert current.claim_id == "replacement-claim"
        assert current.owner_login == "replacement-owner"
    else:
        assert current is None
    durable = jobs.get(result.job_id)
    assert durable.state is WorkflowJobState.EXHAUSTED
    compensation = durable.checkpoint["transition_compensation"]
    assert compensation["claim_id"] == "claim-rejected-transition"
    assert compensation["replacement_claim_id"] == (
        "replacement-claim" if install_replacement else None
    )
    compensated = ImplementationDisposition.from_dict(
        durable.checkpoint["verification"]["disposition"]
    )
    assert compensated.state is ImplementationState.REVOKED
    assert compensated.owner_id == "project-owner"
    effects.receipts.close()
    jobs.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("install_replacement", [False, True])
async def test_missing_task_transition_compensates_durable_owner_identity(
    tmp_path,
    install_replacement,
):
    issue = make_issue(status=BACKLOG)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    claim_id = "claim-before-task-disappears"
    jobs, _context = make_context(
        tmp_path,
        generation="owner-missing-task",
        action=ImplementationAction.DIRECT_OWNER_CLAIM,
        evidence=issue_authority_version(issue),
        payload={
            "owner_id": "project-owner",
            "issue_id": issue.id,
            "claim_id": claim_id,
            "expected_status": BACKLOG,
        },
    )
    orch.workflow_job_store.close()
    orch.workflow_job_store = jobs
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    journal = TransitionJournal(str(tmp_path / "missing-task-transitions.sqlite3"))
    transition_service = TaskTransitionService(
        project_id="project-a",
        tracker=tracker,
        journal=journal,
    )

    def remove_task_after_effect(phase, _job):
        if phase != "transition_intent":
            return
        assert tracker.issues.pop(issue.identifier) is issue
        if install_replacement:
            orch.grant_owner_claim(
                issue_id=issue.id,
                project_id="project-a",
                owner_login="replacement-owner",
                claim_id="replacement-after-task-disappears",
            )

    worker = DurableWorkflowWorker(
        store=jobs,
        handlers={
            ImplementationAction.DIRECT_OWNER_CLAIM.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            )
        },
        transition_services={"project-a": transition_service},
        worker_id="missing-owner-task-compensation-worker",
        phase_observer=remove_task_after_effect,
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    current = orch._owner_claim_for_issue(issue.id, "project-a")
    if install_replacement:
        assert current is not None
        assert current.claim_id == "replacement-after-task-disappears"
        assert current.owner_login == "replacement-owner"
    else:
        assert current is None
    durable = jobs.get(result.job_id)
    assert durable.state is WorkflowJobState.EXHAUSTED
    compensation = durable.checkpoint["transition_compensation"]
    assert compensation["claim_id"] == claim_id
    assert compensation["reason_code"] == "transition.task_missing"
    assert compensation["released"] is (not install_replacement)
    assert compensation["replacement_claim_id"] == (
        "replacement-after-task-disappears" if install_replacement else None
    )
    revoked = ImplementationDisposition.from_dict(
        durable.checkpoint["verification"]["disposition"]
    )
    assert revoked.state is ImplementationState.REVOKED
    assert tracker.status_writes == []
    effects.receipts.close()
    journal.close()
    jobs.close()


@pytest.mark.asyncio
async def test_direct_owner_compensation_is_terminal_restart_barrier(tmp_path):
    issue = make_issue(status=BACKLOG)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    path = tmp_path / "project-a-owner-compensation-restart.sqlite3"
    jobs, _context = make_context(
        tmp_path,
        generation="owner-compensation-restart",
        action=ImplementationAction.DIRECT_OWNER_CLAIM,
        evidence=issue_authority_version(issue),
        payload={
            "owner_id": "project-owner",
            "claim_id": "claim-compensated-before-crash",
            "expected_status": BACKLOG,
        },
    )
    assert jobs.path == str(path)
    orch.workflow_job_store.close()
    orch.workflow_job_store = jobs
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    transition_calls = 0

    class RejectingTransitionService:
        async def execute(self, intent):
            nonlocal transition_calls
            transition_calls += 1
            return TransitionOutcome(
                transition_id="compensated-restart-transition",
                project_id="project-a",
                task_id=issue.identifier,
                disposition=TransitionDisposition.REJECTED,
                reason_code="transition.test_permanent_rejection",
                observed_status=issue.state,
                observed_version=issue_authority_version(issue),
                requested_status=IN_PROGRESS,
            )

    class ProcessDeath(BaseException):
        pass

    def crash_after_compensation(phase, _job):
        if phase == "transition_compensated":
            raise ProcessDeath(phase)

    handler = ImplementationWorkflowHandler(
        ProductionImplementationWorkflowBackend(effects)
    )
    first = DurableWorkflowWorker(
        store=jobs,
        handlers={ImplementationAction.DIRECT_OWNER_CLAIM.value: handler},
        transition_services={"project-a": RejectingTransitionService()},
        worker_id="owner-compensation-crash-worker",
        phase_observer=crash_after_compensation,
    )

    with pytest.raises(ProcessDeath):
        await first.run_once()

    abandoned = jobs.list_jobs(states=[WorkflowJobState.RUNNING])
    assert len(abandoned) == 1
    job_id = abandoned[0].job_id
    assert abandoned[0].phase == "transition_compensated"
    assert orch._owner_claim_for_issue(issue.id, "project-a") is None
    jobs.close()

    reopened = WorkflowJobStore(str(path))
    orch.workflow_job_store = reopened
    assert reopened.recover_abandoned() == 1

    class MustNotReplayTransitionService:
        async def execute(self, _intent):
            raise AssertionError("compensated transition intent was replayed")

    restarted = DurableWorkflowWorker(
        store=reopened,
        handlers={ImplementationAction.DIRECT_OWNER_CLAIM.value: handler},
        transition_services={"project-a": MustNotReplayTransitionService()},
        worker_id="owner-compensation-restart-worker",
    )

    result = await restarted.run_once()

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    durable = reopened.get(job_id)
    assert durable.state is WorkflowJobState.EXHAUSTED
    assert durable.phase == "transition_compensated"
    assert durable.checkpoint["transition_compensation"]["claim_id"] == (
        "claim-compensated-before-crash"
    )
    assert transition_calls == 1
    assert tracker.status_writes == []
    effects.receipts.close()
    reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["permanent", "retry_exhausted", "plain"])
async def test_direct_owner_terminal_transition_failure_compensates_claim(
    tmp_path,
    failure_kind,
):
    issue = make_issue(status=BACKLOG)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    jobs, _context = make_context(
        tmp_path,
        generation=f"owner-terminal-{failure_kind}",
        action=ImplementationAction.DIRECT_OWNER_CLAIM,
        evidence=issue_authority_version(issue),
        payload={
            "owner_id": "project-owner",
            "claim_id": f"claim-terminal-{failure_kind}",
            "expected_status": BACKLOG,
        },
        max_attempts=1,
    )
    orch.workflow_job_store.close()
    orch.workflow_job_store = jobs
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    class FailingTransitionService:
        async def execute(self, _intent):
            if failure_kind == "permanent":
                orch.grant_owner_claim(
                    issue_id=issue.id,
                    project_id="project-a",
                    owner_login="replacement-owner",
                    claim_id="replacement-after-permanent-failure",
                )
                raise WorkflowActionError(
                    "permanent transition failure",
                    category="permanent",
                    retryable=False,
                )
            if failure_kind == "retry_exhausted":
                raise WorkflowActionError(
                    "retryable transition exhausted",
                    category="transient",
                    retryable=True,
                )
            raise RuntimeError("untyped transition failure")

    worker = DurableWorkflowWorker(
        store=jobs,
        handlers={
            ImplementationAction.DIRECT_OWNER_CLAIM.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            )
        },
        transition_services={"project-a": FailingTransitionService()},
        worker_id=f"owner-terminal-{failure_kind}-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    durable = jobs.get(result.job_id)
    assert durable.state is WorkflowJobState.EXHAUSTED
    compensation = durable.checkpoint["transition_compensation"]
    assert compensation["claim_id"] == f"claim-terminal-{failure_kind}"
    assert compensation["settlement"] == "exhausted"
    current = orch._owner_claim_for_issue(issue.id, "project-a")
    if failure_kind == "permanent":
        assert current is not None
        assert current.claim_id == "replacement-after-permanent-failure"
    else:
        assert current is None
    assert tracker.status_writes == []
    effects.receipts.close()
    jobs.close()


@pytest.mark.asyncio
async def test_direct_owner_retryable_transition_keeps_claim_before_exhaustion(
    tmp_path,
):
    issue = make_issue(status=BACKLOG)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    jobs, _context = make_context(
        tmp_path,
        generation="owner-retry-preserves-claim",
        action=ImplementationAction.DIRECT_OWNER_CLAIM,
        evidence=issue_authority_version(issue),
        payload={
            "owner_id": "project-owner",
            "claim_id": "claim-preserved-for-retry",
            "expected_status": BACKLOG,
        },
        max_attempts=2,
    )
    orch.workflow_job_store.close()
    orch.workflow_job_store = jobs
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    class RetryableTransitionService:
        async def execute(self, _intent):
            raise WorkflowActionError(
                "temporary transition failure",
                category="transient",
                retryable=True,
            )

    worker = DurableWorkflowWorker(
        store=jobs,
        handlers={
            ImplementationAction.DIRECT_OWNER_CLAIM.value: (
                ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            )
        },
        transition_services={"project-a": RetryableTransitionService()},
        worker_id="owner-retry-preserves-claim-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    durable = jobs.get(result.job_id)
    assert durable.state is WorkflowJobState.RETRY_WAIT
    assert "transition_compensation" not in (durable.checkpoint or {})
    current = orch._owner_claim_for_issue(issue.id, "project-a")
    assert current is not None
    assert current.claim_id == "claim-preserved-for-retry"
    effects.receipts.close()
    jobs.close()


@pytest.mark.asyncio
async def test_cancelled_outer_apply_keeps_runtime_open_until_inner_mutation_drains(
    tmp_path,
):
    issue = make_issue()
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    jobs, context = make_context(tmp_path)
    orch.workflow_job_store.close()
    orch.workflow_job_store = jobs
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocked_apply(_context):
        started.set()
        await release.wait()
        return disposition(context)

    effects._apply = blocked_apply
    handler = ImplementationWorkflowHandler(
        ProductionImplementationWorkflowBackend(effects)
    )
    journal = TransitionJournal(str(tmp_path / "runtime-transitions.sqlite3"))
    runtime = WorkflowRuntime(
        project_bindings={},
        store=jobs,
        journals={"project-a": journal},
        mode="off",
        handlers={ImplementationAction.START.value: handler},
    )

    outer = asyncio.create_task(effects.apply(context))
    await started.wait()
    outer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await outer

    assert effects.pending_mutation_count == 1
    assert handler.pending_mutation_count == 1
    assert runtime.pending_operation_count == 1
    with pytest.raises(WorkflowRuntimeError, match="1 operation"):
        runtime.close()
    assert await runtime.drain(timeout_seconds=0.01) is False

    drain = asyncio.create_task(runtime.drain(timeout_seconds=1.0))
    await asyncio.sleep(0)
    assert drain.done() is False
    release.set()
    assert await drain is True
    assert effects.pending_mutation_count == 0
    assert runtime.pending_operation_count == 0

    runtime.close()
    jobs.close()


@pytest.mark.asyncio
async def test_marked_quarantine_detaches_exact_mutation_from_recycle_drain(tmp_path):
    issue = make_issue()
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    jobs, context = make_context(tmp_path)
    orch.workflow_job_store.close()
    orch.workflow_job_store = jobs
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocked_apply(_context):
        started.set()
        await release.wait()
        return disposition(context)

    effects._apply = blocked_apply
    outer = asyncio.create_task(effects.apply(context))
    await started.wait()
    claimed = jobs.claim_next(lease_owner="runtime-old", lease_seconds=30)
    assert claimed is not None
    quarantined = jobs.quarantine_owned(
        claimed.job_id,
        claimed.lease_token,
        category="timeout",
        error="synchronous adapter did not return",
    )

    with pytest.raises(WorkflowActionError, match="durable quarantine marker"):
        await effects.prepare_quarantine_recycle(quarantined)
    marked = jobs.mark_quarantine_recycle_requested(
        quarantined.job_id,
        quarantined.lease_token,
    )
    await effects.prepare_quarantine_recycle(marked)

    with pytest.raises(asyncio.CancelledError):
        await outer
    assert effects.pending_mutation_count == 0
    assert await effects.drain_mutations(timeout_seconds=0.01) is True
    effects.receipts.close()
    jobs.close()


@pytest.mark.asyncio
async def test_open_duplicate_screening_dispatches_preflight_before_implementation(
    tmp_path,
):
    issue = make_issue(status=OPEN)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    _jobs, context = make_context(
        tmp_path, action=ImplementationAction.DUPLICATE_SCREENING
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    result = await ProductionImplementationWorkflowBackend(effects).execute(context)

    assert result.status == "duplicate_screened"
    assert result.disposition.state is ImplementationState.ACTIVE
    assert "duplicate_preflight_claim" in orch.dispatches[0][3]
    assert orch.dispatches[0][3]["status_managed_by_workflow"] is True
    effects.receipts.close()


@pytest.mark.asyncio
async def test_duplicate_candidate_dispatches_reserved_read_only_investigator(tmp_path):
    issue = make_issue(status=DUPLICATE_CANDIDATE)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    _jobs, context = make_context(
        tmp_path, action=ImplementationAction.DUPLICATE_SCREENING
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    result = await ProductionImplementationWorkflowBackend(effects).execute(context)

    assert result.disposition.ownership_source is (
        ImplementationOwnershipSource.DUPLICATE_INVESTIGATOR
    )
    assert "duplicate_preflight_claim" in orch.dispatches[0][3]
    assert orch.duplicate_claims == [
        (
            "TASK-1",
            {
                "allow_duplicate_candidate": True,
                "claim_id": "generation-1",
            },
        )
    ]
    effects.receipts.close()


@pytest.mark.asyncio
async def test_launch_retries_without_dispatch_when_capacity_policy_rejects(tmp_path):
    issue = make_issue()
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    orch.admit_dispatch = False
    _jobs, context = make_context(tmp_path)
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    with pytest.raises(WorkflowActionError, match="no_slots") as raised:
        await effects.apply(context)

    assert raised.value.retryable is True
    assert orch.dispatches == []
    effects.receipts.close()


def owner_claim(
    issue: Issue,
    *,
    claim_id: str = "claim-owner",
    project_id: str = "project-a",
    issue_id: str | None = None,
    expires_in: float = 3600,
    retirement_pending: bool = False,
) -> OwnerClaim:
    now = datetime.now(timezone.utc).timestamp()
    return OwnerClaim(
        claim_id,
        issue_id or issue.id,
        project_id,
        "project-owner",
        now,
        now + expires_in,
        retirement_pending=retirement_pending,
    )


@pytest.mark.asyncio
async def test_recovery_is_superseded_by_active_exact_direct_owner_without_retry(
    tmp_path,
):
    issue = make_issue(status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    claim = owner_claim(issue, claim_id="claim-won-recovery-race")
    orch.claims[("project-a", issue.id)] = claim
    jobs, _context = make_context(
        tmp_path,
        action=ImplementationAction.RECOVERY,
        evidence=issue_authority_version(issue),
        payload={"expected_status": IN_PROGRESS},
    )
    orch.workflow_job_store.close()
    orch.workflow_job_store = jobs
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    runner = DurableWorkflowWorker(
        store=jobs,
        handlers={
            ImplementationAction.RECOVERY.value: ImplementationWorkflowHandler(
                ProductionImplementationWorkflowBackend(effects)
            )
        },
        transition_services={},
        worker_id="recovery-worker",
        retry_delay_seconds=0,
    )

    result = await runner.run_once()
    durable = jobs.get(result.job_id)

    assert result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert durable.state is WorkflowJobState.SUPERSEDED
    assert durable.attempts == 1
    assert durable.superseded_by_generation == ("direct-owner:claim-won-recovery-race")
    assert orch.dispatches == []
    assert (await runner.run_once()).disposition is WorkflowRunDisposition.IDLE
    effects.receipts.close()
    jobs.close()


@pytest.mark.asyncio
async def test_recovery_owner_claim_policy_race_uses_latest_aba_generation(tmp_path):
    issue = make_issue(status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.RECOVERY,
    )

    def owner_wins_during_admission(current, **_kwargs):
        first = owner_claim(current, claim_id="claim-a")
        replacement = owner_claim(current, claim_id="claim-b")
        orch.claims[("project-a", current.id)] = first
        orch.claims[("project-a", current.id)] = replacement
        orch.state.reject_streak[current.id] = ("direct_owner_claim", 1)
        return False

    orch._should_dispatch = owner_wins_during_admission
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    with pytest.raises(WorkflowActionSuperseded) as raised:
        await effects.apply(context)

    assert raised.value.replacement_generation == "direct-owner:claim-b"
    assert orch.dispatches == []
    assert effects.receipts.get(context) is None
    effects.receipts.close()


@pytest.mark.asyncio
async def test_recovery_owner_claim_final_dispatch_race_is_superseded(tmp_path):
    issue = make_issue(status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.RECOVERY,
    )

    async def owner_wins_final_boundary(current, *_args, **_kwargs):
        orch.claims[("project-a", current.id)] = owner_claim(
            current,
            claim_id="claim-final-boundary",
        )
        return False

    orch._dispatch = owner_wins_final_boundary
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    with pytest.raises(WorkflowActionSuperseded) as raised:
        await effects.apply(context)

    assert raised.value.replacement_generation == ("direct-owner:claim-final-boundary")
    assert orch.running == {}
    assert effects.receipts.get(context) is None
    effects.receipts.close()


@pytest.mark.asyncio
async def test_released_owner_claim_does_not_supersede_orphan_recovery(tmp_path):
    issue = make_issue(status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.RECOVERY,
    )

    def owner_releases_during_admission(current, **_kwargs):
        key = ("project-a", current.id)
        orch.claims[key] = owner_claim(current, claim_id="claim-released")
        orch.claims.pop(key)
        orch.state.reject_streak[current.id] = ("direct_owner_claim", 1)
        return False

    orch._should_dispatch = owner_releases_during_admission
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    with pytest.raises(WorkflowActionError) as raised:
        await effects.apply(context)

    assert not isinstance(raised.value, WorkflowActionSuperseded)
    assert raised.value.retryable is True
    assert orch.dispatches == []
    orch._should_dispatch = lambda _issue, **_kwargs: True

    recovered = await effects.apply(context)

    assert recovered.ownership_source is ImplementationOwnershipSource.RECOVERY
    assert len(orch.dispatches) == 1
    effects.receipts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "inactive_claim",
    (
        None,
        "expired",
        "retirement_pending",
        "wrong_project",
        "wrong_issue",
    ),
)
async def test_recovery_dispatches_real_orphan_despite_inactive_or_mismatched_claim(
    tmp_path,
    inactive_claim,
):
    issue = make_issue(status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    claims = {
        "expired": owner_claim(issue, expires_in=-1),
        "retirement_pending": owner_claim(issue, retirement_pending=True),
        "wrong_project": owner_claim(issue, project_id="project-b"),
        "wrong_issue": owner_claim(issue, issue_id="project-a:OTHER-1"),
    }
    if inactive_claim is not None:
        orch.claims[("project-a", issue.id)] = claims[inactive_claim]
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.RECOVERY,
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    result = await ProductionImplementationWorkflowBackend(effects).execute(context)

    assert result.status == "recovered"
    assert result.disposition.ownership_source is ImplementationOwnershipSource.RECOVERY
    assert len(orch.dispatches) == 1
    effects.receipts.close()


@pytest.mark.asyncio
async def test_retrying_recovery_supersedes_new_direct_owner_after_restart(tmp_path):
    issue = make_issue(status=IN_PROGRESS)
    first_orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    first_orch.admit_dispatch = False
    jobs, _context = make_context(
        tmp_path,
        action=ImplementationAction.RECOVERY,
        evidence=issue_authority_version(issue),
        payload={"expected_status": IN_PROGRESS},
    )
    jobs_path = jobs.path
    first_orch.workflow_job_store.close()
    first_orch.workflow_job_store = jobs

    def worker_for(orch, store, worker_id):
        effects = OrchestratorImplementationEffects(orch, project_id="project-a")
        return effects, DurableWorkflowWorker(
            store=store,
            handlers={
                ImplementationAction.RECOVERY.value: ImplementationWorkflowHandler(
                    ProductionImplementationWorkflowBackend(effects)
                )
            },
            transition_services={},
            worker_id=worker_id,
            retry_delay_seconds=0,
        )

    first_effects, first = worker_for(first_orch, jobs, "recovery-worker-before-restart")
    first_result = await first.run_once()
    assert first_result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert jobs.get(first_result.job_id).state is WorkflowJobState.RETRY_WAIT

    persisted_claim = owner_claim(
        issue, claim_id="claim-after-first-attempt"
    ).to_dict()
    first_effects.receipts.close()
    jobs.close()

    # Model a process restart: reopen the durable job and receipt databases,
    # reconstruct both the tracker issue and persisted owner lease, and build
    # a new orchestrator/effects/worker graph with no process-local authority.
    restarted_jobs = WorkflowJobStore(jobs_path)
    persisted_retry = restarted_jobs.get(first_result.job_id)
    assert persisted_retry.state is WorkflowJobState.RETRY_WAIT
    restarted_issue = make_issue(status=IN_PROGRESS)
    restarted_orch = FakeOrchestrator(
        tmp_path,
        {"project-a": Tracker(restarted_issue)},
    )
    restarted_orch.workflow_job_store.close()
    restarted_orch.workflow_job_store = restarted_jobs
    restored_claim = OwnerClaim.from_dict(persisted_claim)
    restarted_orch.claims[("project-a", restarted_issue.id)] = restored_claim
    restarted_orch.state.owner_claims[
        f"project-a\0{restarted_issue.id}"
    ] = restored_claim
    second_effects, second = worker_for(
        restarted_orch,
        restarted_jobs,
        "recovery-worker-after-restart",
    )
    second_result = await second.run_once()
    durable = restarted_jobs.get(second_result.job_id)

    assert second_result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert durable.state is WorkflowJobState.SUPERSEDED
    assert durable.attempts == 2
    assert durable.superseded_by_generation == (
        "direct-owner:claim-after-first-attempt"
    )
    assert first_orch.dispatches == []
    assert restarted_orch.dispatches == []
    receipt_context = WorkflowJobContext(
        durable,
        asyncio.Event(),
        asyncio.Event(),
    )
    assert second_effects.receipts.get(receipt_context) is None
    assert (await second.run_once()).disposition is WorkflowRunDisposition.IDLE
    second_effects.receipts.close()
    restarted_jobs.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", [ImplementationAction.START, ImplementationAction.RECOVERY])
async def test_launch_waits_while_a_different_live_generation_exists(
    tmp_path, action
):
    issue = make_issue(status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    replacement = SimpleNamespace(
        issue=issue,
        run_id="live-run",
        authority_generation="live-generation",
    )
    orch.running[issue.id] = replacement
    _jobs, context = make_context(tmp_path, action=action)
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    with pytest.raises(WorkflowActionError, match="live implementation generation"):
        await effects.apply(context)

    assert orch.running[issue.id] is replacement
    assert orch.dispatches == []


@pytest.mark.asyncio
async def test_crash_after_dispatch_recovers_receipt_without_second_launch(tmp_path):
    issue = make_issue()
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    _jobs, context = make_context(tmp_path)
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    await orch._dispatch(
        issue,
        None,
        workflow_generation=context.job.generation,
        status_managed_by_workflow=True,
    )

    observed = await effects.observe(context)

    assert observed is not None
    assert observed.generation == context.job.generation
    assert len(orch.dispatches) == 1
    effects.receipts.close()


@pytest.mark.asyncio
async def test_stale_head_is_rejected_before_effect(tmp_path):
    issue = make_issue(head=HEAD_B)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    _jobs, context = make_context(tmp_path, head=HEAD_A)
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)

    result = await backend.revalidate(context)

    assert result.current is False
    assert orch.dispatches == []


@pytest.mark.asyncio
async def test_stale_authority_evidence_is_rejected_before_effect(tmp_path):
    issue = make_issue()
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    _jobs, context = make_context(tmp_path, evidence="superseded-evidence")
    backend = ProductionImplementationWorkflowBackend(
        OrchestratorImplementationEffects(orch, project_id="project-a")
    )

    result = await backend.revalidate(context)

    assert result.current is False
    assert result.evidence_revision != context.job.expected_evidence_revision
    assert orch.dispatches == []


@pytest.mark.asyncio
async def test_exact_receipt_accepts_its_own_status_revision_on_resume(tmp_path):
    issue = make_issue()
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    _jobs, context = make_context(
        tmp_path,
        evidence=issue_authority_version(issue),
        payload={"expected_status": OPEN},
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)
    executed = await backend.execute(context)
    assert executed.disposition is not None

    # Model a process death after the transition service applied this exact
    # job's Open -> In Progress transition but before the workflow completed.
    issue.state = IN_PROGRESS
    result = await backend.revalidate(context)

    assert result.current is True
    assert result.evidence_revision == context.job.expected_evidence_revision
    assert len(orch.dispatches) == 1
    effects.receipts.close()


@pytest.mark.asyncio
async def test_revocation_cannot_release_a_replacement_owner_claim(tmp_path):
    issue = make_issue()
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    now = datetime.now(timezone.utc).timestamp()
    orch.claims[("project-a", issue.id)] = OwnerClaim(
        "replacement-claim",
        issue.id,
        "project-a",
        "project-owner",
        now,
        now + 3600,
    )
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.AUTHORITY_REVOCATION,
        payload={"claim_id": "superseded-claim", "owner_id": "project-owner"},
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    result = await ProductionImplementationWorkflowBackend(effects).execute(context)

    assert result.status == "revoked"
    assert orch.claims[("project-a", issue.id)].claim_id == "replacement-claim"
    assert orch.released == []
    effects.receipts.close()


@pytest.mark.asyncio
async def test_direct_owner_revocation_retries_durable_release_failure(tmp_path):
    issue = make_issue()
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    now = datetime.now(timezone.utc).timestamp()
    claim = OwnerClaim(
        "claim-1",
        issue.id,
        "project-a",
        "project-owner",
        now,
        now + 3600,
    )
    orch.claims[("project-a", issue.id)] = claim

    def fail_release(**_kwargs):
        raise OSError("disk full")

    orch.release_owner_claim = fail_release
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.AUTHORITY_REVOCATION,
        payload={
            "authority_kind": "direct_owner",
            "claim_id": claim.claim_id,
            "owner_id": claim.owner_login,
        },
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    with pytest.raises(WorkflowActionError) as exc_info:
        await effects.apply(context)

    assert exc_info.value.retryable is True
    assert orch.claims[("project-a", issue.id)] is claim
    effects.receipts.close()


@pytest.mark.asyncio
async def test_owner_claim_mutation_rechecks_job_after_submission_authority_lane(
    tmp_path,
):
    issue = make_issue(status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    authority_lock = asyncio.Lock()
    orch.issue_transition_lock = lambda _issue_id: authority_lock
    jobs, _queued_context = make_context(
        tmp_path,
        action=ImplementationAction.DIRECT_OWNER_CLAIM,
        payload={
            "owner_id": "project-owner",
            "claim_id": "claim-blocked-by-submission",
        },
    )
    running = jobs.claim_next(
        lease_owner="owner-claim-worker",
        lease_seconds=30,
    )
    assert running is not None
    context = WorkflowJobContext(running, asyncio.Event(), asyncio.Event())
    orch.workflow_job_store = jobs
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    await authority_lock.acquire()
    applying = asyncio.create_task(effects.apply(context))
    await asyncio.sleep(0)
    jobs.supersede(
        running.job_id,
        generation=running.generation,
        replacement_generation="accepted-validation-submission",
        reason="submission won the shared authority lane",
    )
    authority_lock.release()

    with pytest.raises(WorkflowActionError, match="authority changed"):
        await applying
    assert orch.claims == {}
    effects.receipts.close()


@pytest.mark.asyncio
async def test_owner_claim_authority_wait_is_bounded_and_retryable(tmp_path):
    issue = make_issue(status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    authority_lock = asyncio.Lock()
    orch.issue_transition_lock = lambda _issue_id: authority_lock
    orch.config.terminal_control_lock_timeout_seconds = 0.05
    orch.config.worker_termination_timeout_ms = 50
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    await authority_lock.acquire()
    try:
        with pytest.raises(WorkflowActionError) as raised:
            async with effects._issue_authority_lane(issue):
                raise AssertionError("bounded owner lane unexpectedly won")
        assert raised.value.retryable is True
        assert "bounded task authority" in str(raised.value)
    finally:
        authority_lock.release()

    async with effects._issue_authority_lane(issue):
        assert authority_lock.locked()
    assert not authority_lock.locked()


@pytest.mark.asyncio
async def test_owner_claim_authority_lane_releases_synchronous_legacy_lock():
    authority_lock = threading.Lock()
    effects = object.__new__(OrchestratorImplementationEffects)
    effects.orchestrator = SimpleNamespace(
        config=SimpleNamespace(terminal_control_lock_timeout_seconds=0.05),
        issue_transition_lock=lambda _issue_id: authority_lock,
    )
    issue = SimpleNamespace(id="task-1")

    async with effects._issue_authority_lane(issue):
        assert authority_lock.locked()

    assert not authority_lock.locked()


@pytest.mark.asyncio
async def test_owner_claim_authority_lane_bounds_contended_synchronous_lock():
    authority_lock = threading.Lock()
    authority_lock.acquire()
    delayed_release = threading.Timer(0.5, authority_lock.release)
    delayed_release.start()
    effects = object.__new__(OrchestratorImplementationEffects)
    effects.orchestrator = SimpleNamespace(
        config=SimpleNamespace(terminal_control_lock_timeout_seconds=0.05),
        issue_transition_lock=lambda _issue_id: authority_lock,
    )
    issue = SimpleNamespace(id="task-1")

    try:
        started = asyncio.get_running_loop().time()
        with pytest.raises(WorkflowActionError) as raised:
            async with effects._issue_authority_lane(issue):
                raise AssertionError("contended synchronous lock was admitted")
        assert raised.value.retryable is True
        assert asyncio.get_running_loop().time() - started < 0.4
        assert authority_lock.locked()
    finally:
        if authority_lock.locked():
            authority_lock.release()
        delayed_release.cancel()
        delayed_release.join()


@pytest.mark.asyncio
async def test_direct_owner_revocation_publishes_state_after_exact_release(tmp_path):
    issue = make_issue()
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    now = datetime.now(timezone.utc).timestamp()
    claim = OwnerClaim(
        "claim-notified-after-release",
        issue.id,
        "project-a",
        "project-owner",
        now,
        now + 3600,
    )
    orch.claims[("project-a", issue.id)] = claim
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.AUTHORITY_REVOCATION,
        payload={
            "authority_kind": "direct_owner",
            "claim_id": claim.claim_id,
            "owner_id": claim.owner_login,
        },
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    await effects.apply(context)

    assert ("project-a", issue.id) not in orch.claims
    assert orch.state_notifications == 1
    effects.receipts.close()


@pytest.mark.asyncio
async def test_revocation_replay_publishes_after_release_before_notify_failure(
    tmp_path,
):
    issue = make_issue()
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    now = datetime.now(timezone.utc).timestamp()
    claim = OwnerClaim(
        "claim-released-before-notify",
        issue.id,
        "project-a",
        "project-owner",
        now,
        now + 3600,
    )
    orch.claims[("project-a", issue.id)] = claim
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.AUTHORITY_REVOCATION,
        payload={
            "authority_kind": "direct_owner",
            "claim_id": claim.claim_id,
            "owner_id": claim.owner_login,
        },
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    publish = orch._notify_state_only
    orch._notify_state_only = MagicMock(
        side_effect=RuntimeError("process died before state publication")
    )

    with pytest.raises(RuntimeError, match="before state publication"):
        await effects.apply(context)

    assert ("project-a", issue.id) not in orch.claims
    assert effects.receipts.get(context) is None

    # A restarted worker observes the already-absent exact claim. That
    # idempotent observation must publish the new state even though apply is
    # skipped and no first-attempt receipt survived.
    orch._notify_state_only = publish
    recovered = OrchestratorImplementationEffects(orch, project_id="project-a")
    observed = await recovered.observe(context)

    assert observed is not None
    assert orch.state_notifications == 1
    effects.receipts.close()


@pytest.mark.asyncio
async def test_general_revocation_cannot_terminate_a_replacement_worker(tmp_path):
    issue = make_issue(status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    replacement = SimpleNamespace(
        issue=issue,
        run_id="replacement-run",
        authority_generation="replacement-generation",
    )
    orch.running[issue.id] = replacement
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.AUTHORITY_REVOCATION,
        payload={
            "authority_kind": "scheduler",
            "prior_generation": "old-generation",
            "prior_run_id": "old-run",
        },
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    with pytest.raises(WorkflowActionError, match="no longer owns"):
        await effects.apply(context)

    assert orch.running[issue.id] is replacement
    assert orch.cancelled == []


@pytest.mark.asyncio
async def test_revocation_cannot_terminate_same_task_id_in_another_project(tmp_path):
    issue = make_issue(project="project-a", status=IN_PROGRESS)
    foreign = make_issue(project="project-b", status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    foreign_entry = SimpleNamespace(
        issue=foreign,
        run_id="foreign-run",
        authority_generation="foreign-generation",
    )
    orch.running[issue.id] = foreign_entry
    _jobs, context = make_context(
        tmp_path,
        project="project-a",
        action=ImplementationAction.AUTHORITY_REVOCATION,
        payload={"authority_kind": "scheduler"},
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    result = await ProductionImplementationWorkflowBackend(effects).execute(context)

    assert result.status == "revoked"
    assert orch.running[issue.id] is foreign_entry
    effects.receipts.close()


@pytest.mark.asyncio
async def test_scheduler_revocation_does_not_release_direct_owner_authority(tmp_path):
    issue = make_issue(status=IN_PROGRESS)
    orch = FakeOrchestrator(tmp_path, {"project-a": Tracker(issue)})
    now = datetime.now(timezone.utc).timestamp()
    claim = OwnerClaim(
        "claim-1",
        issue.id,
        "project-a",
        "project-owner",
        now,
        now + 3600,
    )
    orch.claims[("project-a", issue.id)] = claim
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.AUTHORITY_REVOCATION,
        payload={"authority_kind": "scheduler", "reason": "status changed"},
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    result = await ProductionImplementationWorkflowBackend(effects).execute(context)

    assert result.status == "revoked"
    assert orch.claims[("project-a", issue.id)] is claim
    assert orch.released == []
    effects.receipts.close()


@pytest.mark.asyncio
async def test_worker_exit_status_handoff_retires_exact_run_before_transition(tmp_path):
    issue = make_issue(status=IN_PROGRESS)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    exact = SimpleNamespace(
        issue=issue,
        run_id="exact-run",
        authority_generation="exact-generation",
    )
    orch.running[issue.id] = exact
    _jobs, context = make_context(
        tmp_path,
        generation="exit-generation",
        action=ImplementationAction.WORKER_EXIT,
        payload={
            "prior_generation": "exact-generation",
            "run_id": "exact-run",
            "requested_status": NEEDS_HUMAN,
        },
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)

    result = await backend.execute(context)
    intent = await backend.build_transition(
        context,
        VerificationResult(True, {"disposition": result.disposition.to_dict()}),
    )

    assert issue.id not in orch.running
    assert orch.cancelled[0]["schedule_termination"] is False
    assert intent.requested_status == NEEDS_HUMAN
    assert tracker.status_writes == []
    effects.receipts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "payload", "expected_status"),
    (
        (ImplementationAction.START, {}, "started"),
        (
            ImplementationAction.DIRECT_OWNER_CLAIM,
            {"owner_id": "project-owner"},
            "owner_claimed",
        ),
        (ImplementationAction.DUPLICATE_SCREENING, {}, "duplicate_screened"),
        (
            ImplementationAction.FOCUS_HANDOFF,
            {
                "focus": "validation",
                "prior_generation": "outgoing-generation",
                "prior_run_id": "outgoing-run",
            },
            "handoff_recorded",
        ),
        (ImplementationAction.WORKER_EXIT, {}, "worker_completed"),
        (
            ImplementationAction.VALIDATION_SUBMISSION,
            {},
            "submitted",
        ),
        (ImplementationAction.AUTHORITY_REVOCATION, {}, "revoked"),
        (
            ImplementationAction.RETRY,
            {"retry_at": "2099-01-01T00:00:00+00:00"},
            "retry_scheduled",
        ),
        (ImplementationAction.RECOVERY, {}, "recovered"),
    ),
)
async def test_production_backend_executes_every_implementation_action(
    tmp_path, action, payload, expected_status
):
    issue = make_issue(status=IN_PROGRESS)
    if action is ImplementationAction.VALIDATION_SUBMISSION:
        issue.integration = SimpleNamespace(state="ready", head_sha=HEAD_A)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    if action is ImplementationAction.FOCUS_HANDOFF:
        orch.running[issue.id] = SimpleNamespace(
            issue=issue,
            run_id="outgoing-run",
            authority_generation="outgoing-generation",
        )
    _jobs, context = make_context(
        tmp_path,
        action=action,
        payload={"head_sha": HEAD_A, **payload},
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)

    result = await backend.execute(context)

    assert result.status == expected_status
    assert result.disposition.action is action
    assert result.disposition.generation == context.job.generation
    assert tracker.status_writes == []
    assert await effects.observe(context) == result.disposition
    effects.receipts.close()


def test_shadow_handler_construction_is_zero_write_and_total(tmp_path):
    issue = make_issue()
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    controller = SimpleNamespace(schedule_event=lambda **_kwargs: None)
    binding = SimpleNamespace(
        project_id="project-a",
        tracker=tracker,
        implementation_controller=controller,
    )

    handlers = build_implementation_workflow_handlers(orch, binding)

    assert set(handlers) == IMPLEMENTATION_ACTIONS
    assert not (tmp_path / "implementation_receipts.sqlite3").exists()


def test_enforce_bootstrap_preserves_preclaims_and_revokes_inactive_claims(tmp_path):
    issues = [
        make_issue(identifier="OPEN-1", status="Open"),
        make_issue(identifier="PENDING-OPEN-1", status="Open"),
        make_issue(identifier="ACTIVE-1", status="In Progress"),
        make_issue(identifier="VALIDATE-1", status="In Validation"),
        make_issue(identifier="DONE-1", status="Done"),
        make_issue(identifier="MERGED-1", status="Merged"),
        make_issue(identifier="ARCHIVED-1", status="Archived"),
    ]
    tracker = Tracker(*issues)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    orch.config.workflow_engine_mode = "enforce"
    now = datetime.now(timezone.utc).timestamp()
    claims = {}
    for issue in issues:
        claim = OwnerClaim(
            f"claim-{issue.identifier}",
            issue.id,
            "project-a",
            "project-owner",
            now,
            now + 3600,
            retirement_pending=(issue.identifier == "PENDING-OPEN-1"),
        )
        claims[("project-a", issue.id)] = claim
        orch.state.owner_claims[f"project-a\0{issue.id}"] = claim
    schedule_event = MagicMock()
    binding = SimpleNamespace(
        project_id="project-a",
        tracker=tracker,
        implementation_controller=SimpleNamespace(schedule_event=schedule_event),
    )

    handlers = build_implementation_workflow_handlers(orch, binding)

    assert set(handlers) == IMPLEMENTATION_ACTIONS
    scheduled = {
        call.kwargs["task_id"]: call.kwargs for call in schedule_event.call_args_list
    }
    assert scheduled["OPEN-1"]["action"] is ImplementationAction.DIRECT_OWNER_CLAIM
    assert scheduled["OPEN-1"]["payload"]["issue_id"] == "project-a:OPEN-1"
    assert (
        scheduled["ACTIVE-1"]["action"]
        is ImplementationAction.DIRECT_OWNER_CLAIM
    )
    for identifier in (
        "PENDING-OPEN-1",
        "VALIDATE-1",
        "DONE-1",
        "MERGED-1",
        "ARCHIVED-1",
    ):
        event = scheduled[identifier]
        assert event["action"] is ImplementationAction.AUTHORITY_REVOCATION
        assert event["payload"]["authority_kind"] == "direct_owner"
        assert event["payload"]["claim_id"] == f"claim-{identifier}"
        assert event["expected_evidence_revision"]
    assert orch.state.owner_claims == {
        f"project-a\0{issue.id}": claims[("project-a", issue.id)] for issue in issues
    }


def test_orchestrator_public_factory_exposes_implementation_handlers(tmp_path):
    issue = make_issue()
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    binding = SimpleNamespace(
        project_id="project-a",
        tracker=tracker,
        implementation_controller=SimpleNamespace(schedule_event=lambda **_kwargs: None),
    )
    orch._implementation_workflow_action_handlers = lambda current: (
        build_implementation_workflow_handlers(orch, current)
    )

    handlers = Orchestrator.workflow_action_handler_factory(orch, binding)

    assert set(handlers) == IMPLEMENTATION_ACTIONS


def test_native_tracker_head_fence_uses_exact_task_generation(tmp_path):
    tracker = OompahMarkdownTracker(
        active_states=[OPEN, IN_PROGRESS],
        terminal_states=["Done", "Merged", "Archived"],
        cwd=os.fspath(tmp_path),
        git_sync=False,
    )
    native = tracker.create_issue(
        "Native adapter task",
        description="Native tracker coverage for exact implementation receipts.",
        initial_status=OPEN,
    )
    native.project_id = "project-a"
    tracker.set_metadata_field(native.identifier, "oompah.head_sha", HEAD_A)
    fetched = tracker.fetch_issue_detail(native.identifier)
    fetched.project_id = "project-a"
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")

    assert effects._issue(native.identifier).identifier == native.identifier


@pytest.mark.asyncio
async def test_submission_builds_only_transition_service_status_intent(tmp_path):
    issue = make_issue(status=IN_PROGRESS)
    issue.assignment_id = "assignment-submitted"
    issue.integration = SimpleNamespace(state="ready", head_sha=HEAD_A)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.VALIDATION_SUBMISSION,
        payload={
            "assignment_id": issue.assignment_id,
            "work_branch": "TASK-1",
            "head_sha": HEAD_A,
        },
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)

    assert await effects.observe(context) is None
    result = await backend.execute(context)
    intent = await backend.build_transition(
        context, VerificationResult(True, {"disposition": result.disposition.to_dict()})
    )

    assert tracker.status_writes == []
    assert intent.requested_status == READY_TO_INTEGRATE
    assert intent.evidence_generation == issue.assignment_id
    assert intent.evidence_generation != context.job.generation
    journal = TransitionJournal(str(tmp_path / "submission-transition.sqlite3"))
    outcome = await TaskTransitionService(
        project_id="project-a",
        tracker=tracker,
        journal=journal,
    ).execute(intent)
    assert outcome.disposition is TransitionDisposition.APPLIED
    assert outcome.reason_code == "transition.applied"
    assert tracker.status_writes == [(issue.identifier, READY_TO_INTEGRATE)]
    journal.close()
    effects.receipts.close()


@pytest.mark.asyncio
async def test_restart_submission_uses_exact_direct_owner_claim_generation(
    tmp_path,
):
    issue = make_issue(status=IN_PROGRESS)
    issue.assignment_id = "claim-submitted"
    issue.integration = SimpleNamespace(state="ready", head_sha=HEAD_A)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.VALIDATION_SUBMISSION,
        payload={
            "owner_claim_id": issue.assignment_id,
            "owner_login": "project-owner",
            "work_branch": "TASK-1",
            "head_sha": HEAD_A,
        },
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)

    result = await backend.execute(context)
    intent = await backend.build_transition(
        context,
        VerificationResult(
            True,
            {"disposition": result.disposition.to_dict()},
        ),
    )

    assert intent.evidence_generation == issue.assignment_id
    assert intent.evidence_generation != context.job.generation
    assert intent.exact_head == HEAD_A
    journal = TransitionJournal(str(tmp_path / "claim-submission-transition.sqlite3"))
    transition = await TaskTransitionService(
        project_id="project-a",
        tracker=tracker,
        journal=journal,
    ).execute(intent)
    assert transition.disposition is TransitionDisposition.APPLIED
    assert transition.reason_code == "transition.applied"
    assert tracker.status_writes == [(issue.identifier, READY_TO_INTEGRATE)]
    journal.close()
    effects.receipts.close()


@pytest.mark.asyncio
async def test_submission_finalizes_exact_owner_handoff_off_event_loop(tmp_path):
    issue = make_issue(status=READY_TO_INTEGRATE)
    issue.integration = SimpleNamespace(state="ready", head_sha=HEAD_A)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    retire = MagicMock(return_value=True)
    orch._retire_owner_claim_after_validation_transition = retire
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.VALIDATION_SUBMISSION,
        payload={
            "owner_claim_id": "claim-submitted",
            "owner_login": "project-owner",
            "head_sha": HEAD_A,
        },
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)
    transition = TransitionOutcome(
        transition_id="transition-ready",
        project_id="project-a",
        task_id=issue.identifier,
        disposition=TransitionDisposition.APPLIED,
        reason_code="transition.applied",
        observed_status=READY_TO_INTEGRATE,
        observed_version="ready-version",
        requested_status=READY_TO_INTEGRATE,
        applied_status=READY_TO_INTEGRATE,
    )

    await backend.finalize_transition(context, transition)

    retire.assert_called_once_with(context.job)
    effects.receipts.close()


@pytest.mark.asyncio
async def test_enforce_submission_preserves_nested_target_in_production_queue(
    tmp_path,
):
    nested_target = "epic-OOMPAH-768--task-OOMPAH-804"
    issue = make_issue(identifier="OOMPAH-834", status=IN_PROGRESS)
    issue.parent_id = "OOMPAH-804"
    issue.target_branch = nested_target
    issue.integration = IntegrationRecord(
        state="ready",
        mode="queue",
        task_branch="epic-OOMPAH-804--task-OOMPAH-834",
        base_branch=nested_target,
        base_sha=HEAD_B,
        head_sha=HEAD_A,
    )
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    orch.config.workflow_engine_mode = "enforce"
    orch.integration_queue = IntegrationQueueStore(
        str(tmp_path / "integration-queue.sqlite3")
    )
    orch.enqueue_durable_worker_submission = (
        Orchestrator.enqueue_durable_worker_submission.__get__(orch)
    )
    _jobs, context = make_context(
        tmp_path,
        identifier="OOMPAH-834",
        action=ImplementationAction.VALIDATION_SUBMISSION,
        payload={"head_sha": HEAD_A},
    )
    effects = OrchestratorImplementationEffects(orch, project_id="project-a")
    backend = ProductionImplementationWorkflowBackend(effects)

    await backend.execute(context)

    queued = orch.integration_queue.get("project-a", "OOMPAH-834")
    assert queued is not None
    assert queued.base_branch == nested_target
    effects.receipts.close()
