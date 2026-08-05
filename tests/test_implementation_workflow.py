"""Durable implementation ownership, action, and race coverage."""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from oompah.implementation_workflow import (
    IMPLEMENTATION_ACTIONS,
    ImplementationAction,
    ImplementationDisposition,
    ImplementationExecutionResult,
    ImplementationOwnershipSource,
    ImplementationRoute,
    ImplementationState,
    ImplementationWorkflowController,
    ImplementationWorkflowHandler,
    classify_implementation_result,
)
from oompah.models import Issue
from oompah.statuses import DUPLICATE_CANDIDATE, IN_PROGRESS, OPEN
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionDisposition,
    TransitionIntent,
    TransitionOutcome,
)
from oompah.workflow_contract import TaskDisposition
from oompah.workflow_facts import FactDomain, WorkflowFactCollector
from oompah.workflow_jobs import (
    WorkflowJobLeaseLost,
    WorkflowJobState,
    WorkflowJobStore,
)
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    RevalidationResult,
    WorkflowRunDisposition,
)
from tests.fixtures_workflow_incidents import INCIDENTS_BY_ID

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)


class ProcessDeath(BaseException):
    """Uncatchable test fault representing an abandoned worker process."""


class Tracker:
    def __init__(self, issues):
        self.issues = {issue.identifier: issue for issue in issues}

    def fetch_issue_detail(self, identifier):
        return self.issues.get(identifier)

    def fetch_children(self, identifier):
        return []


def issue(status=OPEN, *, identifier="TASK-1", head=None):
    return Issue(
        id=identifier,
        identifier=identifier,
        title="Durable implementation",
        description="Exercise durable implementation ownership",
        state=status,
        project_id="project-1",
        work_branch=identifier,
        target_branch="main",
        head_sha=head,
    )


def collector(tasks, *, authority=None, config=None):
    return WorkflowFactCollector(
        project_id="project-1",
        tracker=Tracker(tasks),
        sources={
            FactDomain.TERMINAL_AUDIT: lambda _: {"phase": "queued"},
            FactDomain.REVIEW_CI: lambda _: {"state": "open"},
            FactDomain.IMPLEMENTATION_AUTHORITY: lambda _: authority or {},
            FactDomain.RETRY_BUDGET: lambda _: {"remaining": 3},
            FactDomain.CONFIG: lambda _: config or {"version": 1},
        },
    )


def test_controller_schedules_every_open_task_and_projects_same_decision(tmp_path):
    tasks = [issue(identifier="TASK-A"), issue(identifier="TASK-B")]
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector(tasks), store=store
    )

    batch, result = controller.reconcile(tasks)

    assert result.jobs_created == 2
    assert {item.decision.disposition for item in batch.tasks} == {
        TaskDisposition.RUNNABLE
    }
    assert {job.action for job in store.list_jobs()} == {
        ImplementationAction.START.value
    }
    projections = {item.task_id: item for item in controller.projections()}
    for item in batch.tasks:
        projected = projections[item.task.identifier]
        assert projected.reason_code == item.decision.reason_code
        assert projected.durable_jobs == item.decision.durable_jobs
        assert projected.active_job_state == WorkflowJobState.QUEUED.value
    store.close()


def test_bounded_controller_rotates_across_all_eligible_tasks(tmp_path):
    tasks = [issue(identifier=f"TASK-{suffix}") for suffix in "ABC"]
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector(tasks), store=store, decision_limit=1
    )

    observed = {
        controller.evaluate(tasks).tasks[0].task.identifier for _ in range(3)
    }

    assert observed == {"TASK-A", "TASK-B", "TASK-C"}
    store.close()


def test_duplicate_candidate_schedules_durable_screening(tmp_path):
    task = issue(DUPLICATE_CANDIDATE)
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([task]), store=store
    )

    batch, result = controller.reconcile([task])

    assert batch.tasks[0].decision.durable_jobs == ("duplicate_screening",)
    assert result.jobs_created == 1
    assert store.list_jobs()[0].action == "duplicate_screening"
    store.close()


def test_open_duplicate_preflight_precedes_implementation_start(tmp_path):
    task = issue(OPEN)
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector(
            [task],
            config={
                "duplicate_screening_state": "unchecked",
                "implementation_pending_action": "duplicate_screening",
            },
        ),
        store=store,
    )

    batch, result = controller.reconcile([task])

    assert batch.tasks[0].decision.durable_jobs == ("duplicate_screening",)
    assert result.jobs_created == 1
    assert [job.action for job in store.list_jobs()] == ["duplicate_screening"]
    store.close()


@pytest.mark.parametrize(
    ("status", "requested_status"),
    (
        (OPEN, DUPLICATE_CANDIDATE),
        (DUPLICATE_CANDIDATE, OPEN),
    ),
)
def test_duplicate_verdict_status_mismatch_recovers_through_worker_exit(
    tmp_path, status, requested_status
):
    task = issue(status)
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    payload = {
        "requested_status": requested_status,
        "expected_status": status,
        "reason": "recover duplicate-screening transition",
    }
    controller = ImplementationWorkflowController(
        collector=collector(
            [task],
            config={
                "duplicate_screening_state": "checked",
                "duplicate_screening_verdict": (
                    "duplicate_candidate"
                    if requested_status == DUPLICATE_CANDIDATE
                    else "no_duplicate"
                ),
                "duplicate_screening_enabled": True,
                "implementation_pending_action": "worker_exit",
                "implementation_pending_payload": payload,
            },
        ),
        store=store,
    )

    batch, result = controller.reconcile([task])

    assert batch.tasks[0].decision.durable_jobs == ("worker_exit",)
    assert result.jobs_created == 1
    job = store.list_jobs()[0]
    assert job.action == "worker_exit"
    assert job.payload["requested_status"] == requested_status
    assert job.payload["expected_status"] == status
    store.close()


def test_direct_owner_and_agent_share_one_disposition_contract():
    common = dict(
        project_id="project-1",
        task_id="TASK-1",
        generation="generation-1",
        action=ImplementationAction.START,
        state=ImplementationState.ACTIVE,
        owner_id="owner-1",
    )
    agent = ImplementationDisposition(
        **common, ownership_source=ImplementationOwnershipSource.AGENT
    )
    direct = ImplementationDisposition(
        **common, ownership_source=ImplementationOwnershipSource.DIRECT_OWNER
    )

    assert agent.to_dict().keys() == direct.to_dict().keys()
    assert agent.ownership_source is ImplementationOwnershipSource.AGENT
    assert direct.ownership_source is ImplementationOwnershipSource.DIRECT_OWNER


def test_active_ownership_requires_owner_and_lease(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    job = event(controller, payload={"work_branch": "TASK-1"})
    invalid = ImplementationDisposition(
        "project-1",
        "TASK-1",
        job.generation,
        ImplementationAction.START,
        ImplementationState.ACTIVE,
        ImplementationOwnershipSource.AGENT,
        work_branch="TASK-1",
    )

    assert invalid.matches(job) is False
    store.close()


def test_authority_revision_ignores_timestamp_and_advisory_churn_oompah_732():
    incident = INCIDENTS_BY_ID["OOMPAH-732"]
    evidence = incident.before["delivery_evidence_before"]
    assert evidence == incident.before["delivery_evidence_after"]
    disposition = ImplementationDisposition(
        "project-1",
        "TASK-1",
        "generation-1",
        ImplementationAction.START,
        ImplementationState.ACTIVE,
        ImplementationOwnershipSource.AGENT,
        owner_id="agent-1",
        work_branch=evidence["work_branch"],
        head_sha=evidence["head_sha"],
        lease_expires_at=NOW.isoformat(),
    )

    benign = replace(
        disposition,
        lease_expires_at=(NOW + timedelta(hours=1)).isoformat(),
        retry_at=(NOW + timedelta(minutes=5)).isoformat(),
        advisory_denials=7,
        authority_revision=None,
    )
    changed = replace(
        disposition,
        work_branch="reused-branch",
        authority_revision=None,
    )

    assert benign.authority_revision == disposition.authority_revision
    assert changed.authority_revision != disposition.authority_revision
    assert incident.after["authority_generation_changed"] is False


@pytest.mark.parametrize(
    ("status", "route", "retryable"),
    [
        ("started", ImplementationRoute.COMPLETED, False),
        ("submitted", ImplementationRoute.COMPLETED, False),
        ("peer_denied", ImplementationRoute.ADVISORY, False),
        ("incomplete", ImplementationRoute.RETRY, True),
        ("token_changed", ImplementationRoute.RETRY, True),
        ("late_result", ImplementationRoute.SUPERSEDED, True),
        ("unsafe_workspace", ImplementationRoute.ACTION_REQUIRED, False),
    ],
)
def test_every_implementation_result_has_one_bounded_route(
    status, route, retryable
):
    classified = classify_implementation_result(
        ImplementationExecutionResult(status, status)
    )
    assert classified.route is route
    assert classified.retryable is retryable


class Backend:
    def __init__(self, ledger_path=None):
        self.observed = {}
        self.ledger_path = Path(ledger_path) if ledger_path else None
        self.calls = 0
        self.status = "started"
        self.current = True
        self.retry_delay = 0
        self.transition = False
        self.transition_calls = 0

    @staticmethod
    def _key(context):
        job = context.job
        return (job.task_id, job.generation, job.action)

    def revalidate(self, context):
        return RevalidationResult(
            context.job.generation,
            evidence_revision=context.job.expected_evidence_revision,
            head_sha=context.job.expected_head_sha,
            current=self.current,
        )

    def observe_disposition(self, context):
        if self.ledger_path and self.ledger_path.exists():
            raw = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            value = raw.get("|".join(self._key(context)))
            return ImplementationDisposition.from_dict(value) if value else None
        return self.observed.get(self._key(context))

    def _record(self, context, disposition):
        self.observed[self._key(context)] = disposition
        if self.ledger_path:
            raw = (
                json.loads(self.ledger_path.read_text(encoding="utf-8"))
                if self.ledger_path.exists()
                else {}
            )
            raw["|".join(self._key(context))] = disposition.to_dict()
            self.ledger_path.write_text(
                json.dumps(raw, sort_keys=True), encoding="utf-8"
            )

    def execute(self, context):
        self.calls += 1
        if self.status in {"advisory_denied", "peer_denied", "token_changed"}:
            return ImplementationExecutionResult(
                self.status,
                self.status,
                retry_delay_seconds=self.retry_delay,
            )
        state = {
            ImplementationAction.FOCUS_HANDOFF.value: ImplementationState.HANDED_OFF,
            ImplementationAction.WORKER_EXIT.value: ImplementationState.COMPLETED,
            ImplementationAction.VALIDATION_SUBMISSION.value: ImplementationState.SUBMITTED,
            ImplementationAction.AUTHORITY_REVOCATION.value: ImplementationState.REVOKED,
            ImplementationAction.RETRY.value: ImplementationState.RETRY_WAIT,
            ImplementationAction.DUPLICATE_SCREENING.value: ImplementationState.ACTIVE,
        }.get(context.job.action, ImplementationState.ACTIVE)
        if self.status == "incomplete":
            state = ImplementationState.INCOMPLETE
        source = (
            ImplementationOwnershipSource.DIRECT_OWNER
            if context.job.action == ImplementationAction.DIRECT_OWNER_CLAIM.value
            else ImplementationOwnershipSource.DUPLICATE_INVESTIGATOR
            if context.job.action == ImplementationAction.DUPLICATE_SCREENING.value
            else ImplementationOwnershipSource.RECOVERY
            if context.job.action == ImplementationAction.RECOVERY.value
            else ImplementationOwnershipSource.AGENT
        )
        payload = context.job.payload or {}
        disposition = ImplementationDisposition(
            context.job.project_id,
            context.job.task_id,
            context.job.generation,
            context.job.action,
            state,
            source,
            owner_id=str(payload.get("owner_id") or "agent-1"),
            focus=str(payload.get("focus") or "implementation"),
            work_branch=str(payload.get("work_branch") or "TASK-1"),
            head_sha=context.job.expected_head_sha,
            lease_expires_at=(
                payload.get("lease_expires_at")
                or datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
                if state
                in {
                    ImplementationState.ACTIVE,
                    ImplementationState.HANDED_OFF,
                }
                else payload.get("lease_expires_at")
            ),
            retry_at=payload.get("retry_at"),
            incomplete_sessions=1 if state is ImplementationState.INCOMPLETE else 0,
        )
        self._record(context, disposition)
        return ImplementationExecutionResult(self.status, self.status, disposition)

    def build_transition(self, context, verification):
        self.transition_calls += 1
        if not self.transition:
            return None
        return TransitionIntent(
            project_id=context.job.project_id,
            task_id=context.job.task_id,
            expected_status="Open",
            expected_version="version-1",
            requested_status="In Progress",
            actor="implementation-worker",
            authority=TransitionAuthority.WORKER,
            reason_code="transition.implementation_verified",
            idempotency_key=f"{context.job.idempotency_key}:transition",
            originating_job=context.job.job_id,
            evidence_generation=context.job.generation,
            exact_head=context.job.expected_head_sha,
        )


class TransitionService:
    def __init__(self):
        self.intents = []
        self.disposition = TransitionDisposition.APPLIED

    async def execute(self, intent):
        self.intents.append(intent)
        return TransitionOutcome(
            "transition-1",
            intent.project_id,
            intent.task_id,
            self.disposition,
            f"transition.{self.disposition.value}",
            "Open",
            intent.expected_version,
            intent.requested_status,
            applied_status=(
                intent.requested_status
                if self.disposition is TransitionDisposition.APPLIED
                else None
            ),
            retryable=self.disposition is TransitionDisposition.RETRYABLE,
        )


def worker(store, backend, *, observer=None, transition_service=None):
    handler = ImplementationWorkflowHandler(backend)
    return DurableWorkflowWorker(
        store=store,
        handlers={action: handler for action in IMPLEMENTATION_ACTIONS},
        transition_services=(
            {"project-1": transition_service} if transition_service else {}
        ),
        worker_id="worker-1",
        lease_seconds=10,
        heartbeat_seconds=1,
        retry_delay_seconds=0,
        phase_observer=observer,
    )


def event(controller, action=ImplementationAction.START, **overrides):
    values = {
        "project_id": "project-1",
        "task_id": "TASK-1",
        "action": action,
        "payload": {
            "owner_id": "agent-1",
            "focus": "implementation",
            "work_branch": "TASK-1",
            "lease_expires_at": datetime(
                2099, 1, 1, tzinfo=timezone.utc
            ).isoformat(),
        },
    }
    values.update(overrides)
    return controller.schedule_event(**values)


@pytest.mark.asyncio
async def test_success_persists_exact_disposition_and_restart_projection(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    store = WorkflowJobStore(str(path))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    job = event(controller, expected_head_sha="a" * 40)
    backend = Backend()

    result = await worker(store, backend).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    completed = store.get(job.job_id)
    assert completed.checkpoint["verification"]["disposition"]["head_sha"] == "a" * 40
    store.close()

    reopened = WorkflowJobStore(str(path))
    recovered = ImplementationWorkflowController(
        collector=collector([issue()]), store=reopened
    ).latest_disposition("TASK-1")
    assert recovered is not None
    assert recovered.generation == job.generation
    assert recovered.state is ImplementationState.ACTIVE
    reopened.close()


@pytest.mark.asyncio
async def test_claim_start_crash_window_is_inspected_not_launched_twice(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    store = WorkflowJobStore(str(path))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    event(controller)
    ledger = tmp_path / "provider-ledger.json"
    backend = Backend(ledger)
    crashed = False

    def observer(phase, job):
        nonlocal crashed
        if phase == "effect_returned" and not crashed:
            crashed = True
            raise RuntimeError("simulated process death before checkpoint")

    first = await worker(store, backend, observer=observer).run_once()
    assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert backend.calls == 1
    store.close()

    reopened = WorkflowJobStore(str(path))
    restarted_backend = Backend(ledger)
    second = await worker(reopened, restarted_backend).run_once()
    assert second.disposition is WorkflowRunDisposition.COMPLETED
    assert backend.calls == 1
    assert restarted_backend.calls == 0
    reopened.close()


@pytest.mark.asyncio
async def test_open_to_in_progress_reconcile_preserves_start_receipt_window(tmp_path):
    class DelayedStartBackend(Backend):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(self, context):
            self.started.set()
            await self.release.wait()
            return super().execute(context)

    open_task = issue(OPEN)
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    start_controller = ImplementationWorkflowController(
        collector=collector([open_task]), store=store
    )
    _batch, scheduled = start_controller.reconcile([open_task])
    assert scheduled.jobs_created == 1
    start_job = store.list_jobs()[0]
    backend = DelayedStartBackend()
    running = asyncio.create_task(worker(store, backend).run_once())
    await backend.started.wait()

    active_task = issue(IN_PROGRESS)
    active_controller = ImplementationWorkflowController(
        collector=collector(
            [active_task],
            authority={
                "owner_id": "agent-1",
                "ownership_source": "agent",
                "lease_expires_at": datetime(
                    2099, 1, 1, tzinfo=timezone.utc
                ).isoformat(),
            },
        ),
        store=store,
    )
    active_controller.reconcile([active_task])
    assert store.get(start_job.job_id).state is WorkflowJobState.RUNNING

    backend.release.set()
    result = await running
    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(start_job.job_id).state is WorkflowJobState.COMPLETED
    store.close()


def test_owner_takeover_supersedes_and_fences_the_old_lease(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    first = event(controller, payload={"owner_id": "agent-1"})
    leased = store.claim_next(lease_owner="agent-1", lease_seconds=60)
    assert leased is not None and leased.job_id == first.job_id

    second = event(
        controller,
        ImplementationAction.DIRECT_OWNER_CLAIM,
        payload={"owner_id": "human-1"},
    )

    assert store.get(first.job_id).state is WorkflowJobState.SUPERSEDED
    assert second.state is WorkflowJobState.QUEUED
    with pytest.raises(WorkflowJobLeaseLost):
        store.checkpoint(
            first.job_id,
            leased.lease_token,
            phase="too_late",
            checkpoint={"accepted": False},
        )
    store.close()


def test_handoff_payload_is_durable_idempotent_and_branch_reuse_rotates(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    store = WorkflowJobStore(str(path))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    first = event(
        controller,
        ImplementationAction.FOCUS_HANDOFF,
        payload={"owner_id": "agent-2", "focus": "testing"},
        expected_head_sha="a" * 40,
    )
    replay = event(
        controller,
        ImplementationAction.FOCUS_HANDOFF,
        payload={"focus": "testing", "owner_id": "agent-2"},
        expected_head_sha="a" * 40,
    )
    assert replay.job_id == first.job_id
    store.close()

    reopened = WorkflowJobStore(str(path))
    assert reopened.get(first.job_id).payload == {
        "focus": "testing",
        "owner_id": "agent-2",
    }
    rotated = ImplementationWorkflowController(
        collector=collector([issue()]), store=reopened
    ).schedule_event(
        project_id="project-1",
        task_id="TASK-1",
        action=ImplementationAction.FOCUS_HANDOFF,
        payload={"owner_id": "agent-2", "focus": "testing"},
        expected_head_sha="b" * 40,
    )
    assert rotated.generation != first.generation
    assert reopened.get(first.job_id).state is WorkflowJobState.SUPERSEDED
    reopened.close()


def test_identical_concurrent_events_materialize_one_job(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )

    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = tuple(pool.map(lambda _: event(controller), range(32)))

    assert len({job.job_id for job in jobs}) == 1
    assert len(store.list_jobs()) == 1
    store.close()


def test_periodic_decision_reconciliation_cannot_erase_event_lane(tmp_path):
    task = issue(IN_PROGRESS)
    authority = {
        "owner_id": "agent-1",
        "ownership_source": "agent",
        "lease_expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
    }
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([task], authority=authority), store=store
    )
    queued = event(controller, ImplementationAction.FOCUS_HANDOFF)
    batch = controller.evaluate([task])

    controller.scheduler.reconcile(batch.decisions)

    assert store.get(queued.job_id).state is WorkflowJobState.QUEUED
    assert (
        store.get(queued.job_id).scheduling_lane
        == "event:implementation:imperative"
    )
    store.close()


def test_older_slow_scan_cannot_supersede_newer_implementation_decision(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    active = issue(IN_PROGRESS)
    authority = {
        "owner_id": "agent-1",
        "ownership_source": "agent",
        "lease_expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
    }
    newer = ImplementationWorkflowController(
        collector=collector(
            [active],
            authority=authority,
            config={
                "implementation_pending_action": "validation_submission",
                "implementation_pending_payload": {
                    "owner_id": "agent-1",
                    "head_sha": "a" * 40,
                },
            },
        ),
        store=store,
    )
    older = ImplementationWorkflowController(
        collector=collector([issue(OPEN)]), store=store
    )

    _new_batch, new_result = newer.reconcile([active], snapshot_generation=2)
    submission = store.list_jobs()[0]
    _old_batch, old_result = older.reconcile(
        [issue(OPEN)], snapshot_generation=1
    )

    assert new_result.jobs_created == 1
    assert old_result.stale_rejected == 1
    assert old_result.jobs_created == 0
    assert store.get(submission.job_id).state is WorkflowJobState.QUEUED
    assert store.get(submission.job_id).action == "validation_submission"
    store.close()


def test_fact_reconcile_replays_equivalent_imperative_event(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    task = issue(IN_PROGRESS)
    authority = {
        "owner_id": "agent-1",
        "ownership_source": "agent",
        "lease_expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
    }
    payload = {
        "owner_id": "agent-2",
        "focus": "testing",
        "work_branch": "TASK-1",
        "expected_status": task.state,
        "lease_expires_at": datetime(2099, 1, 2, tzinfo=timezone.utc).isoformat(),
    }
    controller = ImplementationWorkflowController(
        collector=collector(
            [task],
            authority=authority,
            config={
                "implementation_pending_action": "focus_handoff",
                "implementation_pending_payload": payload,
            },
        ),
        store=store,
    )
    imperative = event(
        controller, ImplementationAction.FOCUS_HANDOFF, payload=payload
    )

    _batch, result = controller.reconcile([task])

    assert result.jobs_created == 0
    assert result.jobs_replayed == 1
    assert len(store.list_jobs()) == 1
    assert store.list_jobs()[0].job_id == imperative.job_id
    assert store.list_jobs()[0].state is WorkflowJobState.QUEUED
    store.close()


def test_imperative_event_fences_older_fact_scan(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue(OPEN)]), store=store
    )
    old_generation = store.allocate_snapshot_generation()
    submission = event(controller, ImplementationAction.VALIDATION_SUBMISSION)

    _batch, result = controller.reconcile(
        [issue(OPEN)], snapshot_generation=old_generation
    )

    assert result.stale_rejected == 1
    assert result.jobs_created == 0
    assert store.get(submission.job_id).state is WorkflowJobState.QUEUED
    assert store.get(submission.job_id).action == "validation_submission"
    store.close()


def test_newer_no_job_decision_retires_only_fact_derived_action(tmp_path):
    task = issue(IN_PROGRESS)
    authority = {
        "owner_id": "agent-1",
        "ownership_source": "agent",
        "lease_expires_at": datetime(
            2099, 1, 1, tzinfo=timezone.utc
        ).isoformat(),
    }
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    pending = ImplementationWorkflowController(
        collector=collector(
            [task],
            authority=authority,
            config={
                "implementation_pending_action": "focus_handoff",
                "implementation_pending_payload": {
                    "owner_id": "agent-2",
                    "focus": "testing",
                },
            },
        ),
        store=store,
    )
    _batch, created = pending.reconcile([task])
    obsolete = store.list_jobs()[0]
    assert created.jobs_created == 1

    current = ImplementationWorkflowController(
        collector=collector([task], authority=authority), store=store
    )
    batch, retired = current.reconcile([task])

    assert batch.tasks[0].decision.reason_code == "implementation.active"
    assert retired.jobs_superseded == 1
    assert store.get(obsolete.job_id).state is WorkflowJobState.SUPERSEDED
    store.close()


@pytest.mark.asyncio
async def test_token_change_retry_expiry_survives_restart(tmp_path):
    now = [0.0]
    path = tmp_path / "jobs.sqlite3"
    store = WorkflowJobStore(str(path), clock=lambda: now[0])
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    event(controller)
    backend = Backend()
    backend.status = "token_changed"
    backend.retry_delay = 10

    first = await worker(store, backend).run_once()
    assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    store.close()

    reopened = WorkflowJobStore(str(path), clock=lambda: now[0])
    assert (await worker(reopened, backend).run_once()).disposition is WorkflowRunDisposition.IDLE

    now[0] = 10
    backend.status = "started"
    resumed = await worker(reopened, backend).run_once()
    assert resumed.disposition is WorkflowRunDisposition.COMPLETED
    assert backend.calls == 2
    reopened.close()


@pytest.mark.asyncio
async def test_incomplete_session_is_durable_and_drives_recovery(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    event(controller)
    backend = Backend()
    backend.status = "incomplete"

    result = await worker(store, backend).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    incomplete = controller.latest_disposition("TASK-1", project_id="project-1")
    assert incomplete is not None
    assert incomplete.state is ImplementationState.INCOMPLETE
    assert incomplete.incomplete_sessions == 1

    in_progress = issue(IN_PROGRESS)
    recovery = ImplementationWorkflowController(
        collector=collector(
            [in_progress], authority=controller.implementation_authority(in_progress)
        ),
        store=store,
    )
    batch, scheduled = recovery.reconcile([in_progress])
    assert batch.tasks[0].decision.durable_jobs == ("implementation_recovery",)
    assert scheduled.jobs_created == 1
    assert store.list_jobs(newest_first=True)[0].action == "implementation_recovery"
    store.close()


@pytest.mark.asyncio
async def test_implementation_retry_action_uses_durable_due_timer(tmp_path):
    now = [0.0]
    store = WorkflowJobStore(
        str(tmp_path / "jobs.sqlite3"), clock=lambda: now[0]
    )
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    payload = {
        "owner_id": "agent-1",
        "work_branch": "TASK-1",
        "retry_at": datetime.fromtimestamp(10, tz=timezone.utc).isoformat(),
    }
    job = event(controller, ImplementationAction.RETRY, payload=payload)
    backend = Backend()
    backend.status = "retry_scheduled"

    first = await worker(store, backend).run_once()
    assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert store.get(job.job_id).state is WorkflowJobState.RETRY_WAIT
    assert store.get(job.job_id).retry_at == 10
    in_progress = issue(IN_PROGRESS)
    authority = controller.implementation_authority(in_progress)
    reconciler = ImplementationWorkflowController(
        collector=collector([in_progress], authority=authority), store=store
    )
    batch, scheduled = reconciler.reconcile([in_progress])
    assert batch.tasks[0].decision.reason_code == "implementation.action_scheduled"
    assert scheduled.jobs_created == 0
    assert store.get(job.job_id).state is WorkflowJobState.RETRY_WAIT
    assert (await worker(store, backend).run_once()).disposition is WorkflowRunDisposition.IDLE

    now[0] = 10
    second = await worker(store, backend).run_once()
    assert second.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    store.close()


@pytest.mark.asyncio
async def test_completed_retry_carries_launch_context_into_recovery(tmp_path):
    now = [0.0]
    store = WorkflowJobStore(
        str(tmp_path / "jobs.sqlite3"), clock=lambda: now[0]
    )
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    event(
        controller,
        ImplementationAction.RETRY,
        payload={
            "owner_id": "agent-1",
            "work_branch": "TASK-1",
            "retry_at": datetime.fromtimestamp(0, tz=timezone.utc).isoformat(),
            "attempt": 2,
            "profile": "escalated",
            "workspace_path": "/work/TASK-1",
            "incomplete_sessions": 2,
            "focus": "bugfix",
        },
    )
    backend = Backend()
    backend.status = "retry_scheduled"

    assert (
        await worker(store, backend).run_once()
    ).disposition is WorkflowRunDisposition.COMPLETED
    in_progress = issue(IN_PROGRESS)
    authority = controller.implementation_authority(in_progress)
    reconciler = ImplementationWorkflowController(
        collector=collector([in_progress], authority=authority), store=store
    )

    batch, scheduled = reconciler.reconcile([in_progress])

    assert batch.tasks[0].decision.durable_jobs == ("implementation_recovery",)
    assert scheduled.jobs_created == 1
    recovery = store.list_jobs(newest_first=True)[0]
    assert recovery.action == "implementation_recovery"
    assert recovery.payload["attempt"] == 2
    assert recovery.payload["profile"] == "escalated"
    assert recovery.payload["workspace_path"] == "/work/TASK-1"
    assert recovery.payload["incomplete_sessions"] == 2
    assert recovery.payload["focus"] == "bugfix"
    store.close()


@pytest.mark.asyncio
async def test_abandoned_retry_attempt_still_honors_original_retry_at(tmp_path):
    now = [0.0]
    path = tmp_path / "jobs.sqlite3"
    store = WorkflowJobStore(str(path), clock=lambda: now[0])
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    job = event(
        controller,
        ImplementationAction.RETRY,
        payload={
            "owner_id": "agent-1",
            "work_branch": "TASK-1",
            "retry_at": datetime.fromtimestamp(10, tz=timezone.utc).isoformat(),
        },
    )
    backend = Backend()
    backend.status = "retry_scheduled"
    crashed = False

    def abandon_after_verification(phase, _job):
        nonlocal crashed
        if phase == "verify_returned" and not crashed:
            crashed = True
            raise ProcessDeath("worker disappeared before arming retry")

    with pytest.raises(ProcessDeath):
        await worker(store, backend, observer=abandon_after_verification).run_once()
    assert store.get(job.job_id).state is WorkflowJobState.RUNNING
    assert store.recover_abandoned() == 1

    before_due = await worker(store, backend).run_once()

    assert before_due.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    recovered = store.get(job.job_id)
    assert recovered.attempts == 2
    assert recovered.state is WorkflowJobState.RETRY_WAIT
    assert recovered.retry_at == 10
    assert (await worker(store, backend).run_once()).disposition is WorkflowRunDisposition.IDLE

    now[0] = 10
    assert (await worker(store, backend).run_once()).disposition is WorkflowRunDisposition.COMPLETED
    store.close()


@pytest.mark.asyncio
async def test_stale_generation_is_superseded_before_external_work(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    event(controller)
    backend = Backend()
    backend.current = False

    result = await worker(store, backend).run_once()

    assert result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert backend.calls == 0
    store.close()


@pytest.mark.asyncio
async def test_late_execution_result_is_terminally_superseded(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    job = event(controller)
    backend = Backend()
    backend.status = "late_result"

    result = await worker(store, backend).run_once()

    assert result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert store.get(job.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(job.job_id).retry_at is None
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "state", "source"),
    [
        (
            ImplementationAction.DIRECT_OWNER_CLAIM,
            ImplementationState.ACTIVE,
            ImplementationOwnershipSource.DIRECT_OWNER,
        ),
        (
            ImplementationAction.DUPLICATE_SCREENING,
            ImplementationState.ACTIVE,
            ImplementationOwnershipSource.DUPLICATE_INVESTIGATOR,
        ),
        (
            ImplementationAction.AUTHORITY_REVOCATION,
            ImplementationState.REVOKED,
            ImplementationOwnershipSource.AGENT,
        ),
        (
            ImplementationAction.WORKER_EXIT,
            ImplementationState.COMPLETED,
            ImplementationOwnershipSource.AGENT,
        ),
    ],
)
async def test_ownership_actions_persist_exact_dispositions(
    tmp_path, action, state, source
):
    store = WorkflowJobStore(str(tmp_path / f"{action.value}.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    job = event(controller, action)
    backend = Backend()

    result = await worker(store, backend).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    disposition = controller.latest_disposition("TASK-1", project_id="project-1")
    assert disposition is not None
    assert disposition.generation == job.generation
    assert disposition.state is state
    assert disposition.ownership_source is source
    authority = controller.implementation_authority(issue(IN_PROGRESS))
    if state is ImplementationState.ACTIVE:
        assert authority["lease_expires_at"] is not None
    else:
        assert authority["lease_expires_at"] is None
    store.close()


@pytest.mark.asyncio
async def test_transition_intent_is_routed_after_exact_disposition(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    job = event(controller, expected_head_sha="a" * 40)
    backend = Backend()
    backend.transition = True
    transitions = TransitionService()

    result = await worker(
        store, backend, transition_service=transitions
    ).run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert len(transitions.intents) == 1
    assert transitions.intents[0].originating_job == job.job_id
    assert transitions.intents[0].evidence_generation == job.generation
    assert store.get(job.job_id).result_transition["disposition"] == "applied"
    store.close()


@pytest.mark.asyncio
async def test_verified_owner_remains_authoritative_during_transition_retry(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    job = event(controller)
    backend = Backend()
    backend.transition = True
    transitions = TransitionService()
    transitions.disposition = TransitionDisposition.RETRYABLE

    first = await worker(
        store, backend, transition_service=transitions
    ).run_once()

    assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert store.get(job.job_id).state is WorkflowJobState.RETRY_WAIT
    accepted = controller.latest_disposition("TASK-1", project_id="project-1")
    assert accepted is not None
    authority = controller.implementation_authority(issue(IN_PROGRESS))
    assert authority["owner_id"] == "agent-1"
    assert authority["lease_expires_at"] is not None
    assert authority["transition_pending"] is True

    observed_during_reclaim = []

    def observe_phase(phase, claimed):
        if phase == "revalidated" and claimed.attempts == 2:
            observed_during_reclaim.append(
                controller.implementation_authority(issue(IN_PROGRESS))
            )

    backend.observed.clear()
    calls_before_reclaim = backend.calls
    second = await worker(
        store,
        backend,
        observer=observe_phase,
        transition_service=transitions,
    ).run_once()
    assert second.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert observed_during_reclaim[0]["owner_id"] == "agent-1"
    assert observed_during_reclaim[0]["lease_expires_at"] is not None
    assert observed_during_reclaim[0]["transition_pending"] is True
    assert backend.calls == calls_before_reclaim

    active_task = issue(IN_PROGRESS)
    reconciler = ImplementationWorkflowController(
        collector=collector([active_task], authority=authority), store=store
    )
    batch, result = reconciler.reconcile([active_task])
    assert batch.tasks[0].decision.reason_code == "implementation.active"
    assert result.jobs_created == 0
    assert store.get(job.job_id).state is WorkflowJobState.RETRY_WAIT
    store.close()


@pytest.mark.asyncio
async def test_cleared_fact_action_retires_unverified_retry_wait(tmp_path):
    now = [0.0]
    task = issue(IN_PROGRESS)
    authority = {
        "owner_id": "agent-1",
        "ownership_source": "agent",
        "lease_expires_at": datetime(
            2099, 1, 1, tzinfo=timezone.utc
        ).isoformat(),
    }
    store = WorkflowJobStore(
        str(tmp_path / "jobs.sqlite3"), clock=lambda: now[0]
    )
    pending = ImplementationWorkflowController(
        collector=collector(
            [task],
            authority=authority,
            config={
                "implementation_pending_action": "focus_handoff",
                "implementation_pending_payload": {
                    "owner_id": "agent-2",
                    "focus": "testing",
                },
            },
        ),
        store=store,
    )
    _batch, created = pending.reconcile([task])
    job = store.list_jobs()[0]
    assert created.jobs_created == 1
    backend = Backend()
    backend.status = "token_changed"
    backend.retry_delay = 10
    first = await worker(store, backend).run_once()
    assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert store.get(job.job_id).state is WorkflowJobState.RETRY_WAIT

    current = ImplementationWorkflowController(
        collector=collector([task], authority=authority), store=store
    )
    _batch, retired = current.reconcile([task])

    assert retired.jobs_superseded == 1
    assert store.get(job.job_id).state is WorkflowJobState.SUPERSEDED
    calls_before_due = backend.calls
    now[0] = 10
    assert (await worker(store, backend).run_once()).disposition is WorkflowRunDisposition.IDLE
    assert backend.calls == calls_before_due
    store.close()


@pytest.mark.asyncio
async def test_payload_owner_mismatch_cannot_be_accepted(tmp_path):
    class WrongOwnerBackend(Backend):
        def execute(self, context):
            result = super().execute(context)
            wrong = replace(
                result.disposition, owner_id="wrong-owner", authority_revision=None
            )
            return ImplementationExecutionResult("started", "wrong owner", wrong)

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    event(controller, payload={"owner_id": "expected-owner"})

    result = await worker(store, WrongOwnerBackend()).run_once()

    assert result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert controller.latest_disposition("TASK-1", project_id="project-1") is None
    store.close()


@pytest.mark.asyncio
async def test_advisory_handoff_denial_does_not_poison_submission_oompah_751(
    tmp_path,
):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    handoff = event(controller, ImplementationAction.FOCUS_HANDOFF)
    backend = Backend()
    backend.status = "peer_denied"
    backend.transition = True

    denied = await worker(store, backend).run_once()
    assert denied.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(handoff.job_id).failure_category is None
    assert backend.transition_calls == 0

    submitted = event(controller, ImplementationAction.VALIDATION_SUBMISSION)
    backend.status = "submitted"
    backend.transition = False
    accepted = await worker(store, backend).run_once()

    assert accepted.disposition is WorkflowRunDisposition.COMPLETED
    latest = controller.latest_disposition("TASK-1")
    assert latest is not None
    assert latest.generation == submitted.generation
    assert latest.state is ImplementationState.SUBMITTED
    store.close()


@pytest.mark.asyncio
async def test_accepted_submission_cannot_be_reverted_by_late_worker_exit(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    submitted = event(controller, ImplementationAction.VALIDATION_SUBMISSION)
    backend = Backend()
    backend.status = "submitted"
    assert (await worker(store, backend).run_once()).disposition is WorkflowRunDisposition.COMPLETED

    event(controller, ImplementationAction.WORKER_EXIT)
    backend.current = False
    late = await worker(store, backend).run_once()

    assert late.disposition is WorkflowRunDisposition.SUPERSEDED
    latest = controller.latest_disposition("TASK-1")
    assert latest is not None
    assert latest.generation == submitted.generation
    assert latest.state is ImplementationState.SUBMITTED
    store.close()


@pytest.mark.asyncio
async def test_result_arriving_after_owner_takeover_loses_its_lease(tmp_path):
    class DelayedBackend(Backend):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(self, context):
            self.started.set()
            await self.release.wait()
            return super().execute(context)

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store
    )
    old = event(controller, payload={"owner_id": "agent-1"})
    backend = DelayedBackend()
    running = asyncio.create_task(worker(store, backend).run_once())
    await backend.started.wait()

    replacement = event(
        controller,
        ImplementationAction.DIRECT_OWNER_CLAIM,
        payload={"owner_id": "human-1"},
    )
    backend.release.set()
    result = await running

    assert result.disposition is WorkflowRunDisposition.LEASE_LOST
    assert store.get(old.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(replacement.job_id).state is WorkflowJobState.QUEUED
    assert controller.latest_disposition("TASK-1", project_id="project-1") is None
    store.close()


@pytest.mark.asyncio
async def test_latest_disposition_is_not_hidden_by_bounded_history(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector([issue()]), store=store, decision_limit=1
    )
    backend = Backend()
    event(controller, ImplementationAction.START)
    assert (await worker(store, backend).run_once()).disposition is WorkflowRunDisposition.COMPLETED

    submitted = event(controller, ImplementationAction.VALIDATION_SUBMISSION)
    backend.status = "submitted"
    assert (await worker(store, backend).run_once()).disposition is WorkflowRunDisposition.COMPLETED

    latest = controller.latest_disposition("TASK-1")
    assert latest is not None
    assert latest.generation == submitted.generation
    assert latest.state is ImplementationState.SUBMITTED
    store.close()


def test_in_progress_pending_action_is_the_only_durable_disposition(tmp_path):
    task = issue(IN_PROGRESS)
    authority = {
        "owner_id": "agent-1",
        "ownership_source": "agent",
        "lease_expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat(),
    }
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = ImplementationWorkflowController(
        collector=collector(
            [task],
            authority=authority,
            config={
                "implementation_pending_action": "validation_submission",
                "implementation_pending_payload": {
                    "owner_id": "agent-1",
                    "head_sha": "a" * 40,
                },
            },
        ),
        store=store,
    )

    batch, result = controller.reconcile([task])

    assert batch.tasks[0].decision.reason_code == "implementation.action_scheduled"
    assert batch.tasks[0].decision.durable_jobs == ("validation_submission",)
    assert result.jobs_created == 1
    assert store.list_jobs()[0].action == "validation_submission"
    assert store.list_jobs()[0].payload["owner_id"] == "agent-1"
    assert store.list_jobs()[0].payload["head_sha"] == "a" * 40
    store.close()
