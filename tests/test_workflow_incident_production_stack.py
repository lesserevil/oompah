"""Production-composed replay for the seven historical workflow incidents."""

from __future__ import annotations

import asyncio
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from oompah.integration import IntegrationRecord
from oompah.integration_queue import IntegrationQueueStore
from oompah.epic_workflow import (
    EpicAction,
    EpicFactCollector,
    EpicWorkflowController,
    EpicWorkflowHandler,
    ProductionEpicWorkflowBackend,
)
from oompah.integration_workflow import (
    IntegrationActionHandler,
    IntegrationWorkflowController,
    OrchestratorIntegrationActionBackend,
    schedule_project_historical_replay,
)
from oompah.orchestrator import Orchestrator
from oompah.statuses import IN_VALIDATION, MERGED
from oompah.task_transition_service import (
    TaskTransitionService,
    TerminalStageResult,
    TransitionJournal,
)
from oompah.work_decision import evaluate_task
from oompah.work_decision_projection import project_work_decision
from oompah.workflow_facts import (
    FactDomain,
    GitLandingCollector,
    LandingFact,
    LandingRequest,
    LandingState,
    WorkflowFactCollector,
)
from oompah.workflow_jobs import WorkflowJobState, WorkflowJobStore
from oompah.workflow_scheduler import WorkflowJobScheduler
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    WorkflowActionDomain,
    WorkflowRunDisposition,
)
from tests.fixtures_workflow_incidents import (
    INCIDENTS,
    INCIDENTS_BY_ID,
    GitReplay,
    IncidentScenario,
    NativeTrackerReplay,
    materialize_git,
    materialize_native_tracker,
)


PROJECT_ID = "historical-incidents"
NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


@dataclass
class ProductionReplay:
    scenario: IncidentScenario
    native: NativeTrackerReplay
    git: GitReplay | None
    task_id: str
    collector: WorkflowFactCollector
    landing_requests: tuple[LandingRequest, ...]
    queue: IntegrationQueueStore | None

    @property
    def task(self):
        issue = self.native.tracker.fetch_issue_detail(self.task_id)
        assert issue is not None
        return issue

    def facts(self):
        task = self.task
        if self.scenario.source_task_id != "OOMPAH-748":
            return self.collector.collect(
                self.task_id,
                landing_requests=self.landing_requests,
            )
        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator.tracker = self.native.tracker
        orchestrator._tracker_for_project = lambda _project_id: self.native.tracker
        orchestrator.project_store = SimpleNamespace(
            get=lambda _project_id: SimpleNamespace(
                default_branch="main",
                repo_path=self.git.path if self.git is not None else None,
            )
        )
        orchestrator.integration_queue = self.queue
        orchestrator._workflow_shadow_sources = lambda _task: _external_sources(
            self.scenario.source_task_id
        )
        return orchestrator._collect_universal_workflow_facts(task)

    def decision(self):
        return evaluate_task(
            self.task,
            self.facts(),
            now=NOW,
        )


def _task_key(source_task_id: str) -> str:
    return {
        "OOMPAH-562": "child",
        "OOMPAH-731": "maintenance",
        "OOMPAH-732": "standalone",
        "OOMPAH-739": "child",
        "OOMPAH-748": "child",
        "OOMPAH-749": "live",
        "OOMPAH-751": "sender",
    }[source_task_id]


def _persist_submission(
    native: NativeTrackerReplay,
    task_id: str,
    record: IntegrationRecord,
) -> None:
    native.tracker.set_metadata_field(task_id, "oompah.integration", record.to_dict())
    if record.task_branch:
        native.tracker.set_metadata_field(
            task_id, "oompah.work_branch", record.task_branch
        )
    if record.base_branch:
        native.tracker.set_metadata_field(
            task_id, "oompah.target_branch", record.base_branch
        )


def _external_sources(source_task_id: str):
    return {
        FactDomain.TERMINAL_AUDIT: lambda _issue: {"phase": "queued"},
        FactDomain.REVIEW_CI: lambda _issue: {"state": "open", "ci": "passed"},
        FactDomain.IMPLEMENTATION_AUTHORITY: lambda _issue: {
            "lease_expires_at": "2099-01-01T00:00:00+00:00"
        },
        FactDomain.RETRY_BUDGET: lambda _issue: {"remaining": 5},
        FactDomain.CONFIG: lambda _issue: {
            "coordination_policy_denied": source_task_id == "OOMPAH-751"
        },
    }


def _prepare(tmp_path, scenario: IncidentScenario) -> ProductionReplay:
    root = tmp_path / scenario.source_task_id
    native = materialize_native_tracker(root, scenario)
    git = materialize_git(root, scenario) if scenario.git is not None else None
    task_id = native.identifiers[_task_key(scenario.source_task_id)]
    source = scenario.source_task_id
    queue: IntegrationQueueStore | None = None
    requests: tuple[LandingRequest, ...] = ()

    if source == "OOMPAH-562":
        assert git is not None
        record = IntegrationRecord(
            state="ready",
            mode="queue",
            task_branch="epic-E--task-C",
            base_branch="epic-E",
            head_sha=git.commits["task"],
            dependency_heads={"dependency": git.commits["dependency"]},
        )
        _persist_submission(native, task_id, record)
        task = native.tracker.fetch_issue_detail(task_id)
        assert task is not None and task.parent_id
        queue = IntegrationQueueStore(str(root / "integration.sqlite3"))
        queue.enqueue(
            project_id=PROJECT_ID,
            epic_id=task.parent_id,
            task_id=task_id,
            task_branch=record.task_branch or "",
            head_sha=record.head_sha or "",
            base_branch=record.base_branch,
            base_sha=git.commits["epic"],
        )
    elif source == "OOMPAH-731":
        assert git is not None
        maintenance = native.tracker.fetch_issue_detail(task_id)
        assert maintenance is not None and maintenance.parent_id
        epic_branch = f"epic-{maintenance.parent_id}"
        native.tracker.update_issue(
            task_id,
            title=f"Rebase {epic_branch} onto main",
        )
        _persist_submission(
            native,
            task_id,
            IntegrationRecord(
                state="integrated",
                mode="queue",
                task_branch=epic_branch,
                base_branch=epic_branch,
                head_sha=git.commits["epic-rebased"],
                integrated_sha=git.commits["epic-rebased"],
                maintenance_publication_proven=True,
            ),
        )
    elif source == "OOMPAH-732":
        _persist_submission(
            native,
            task_id,
            IntegrationRecord(
                state="ready",
                mode="standalone",
                task_branch="task-S",
                base_branch="main",
                head_sha="a" * 40,
            ),
        )
    elif source == "OOMPAH-739":
        assert git is not None
        target = "epic-parent"
        revision = git.commits["child-head"]
        _persist_submission(
            native,
            task_id,
            IntegrationRecord(
                state="integrated",
                mode="queue",
                task_branch="epic-child",
                base_branch=target,
                head_sha=revision,
                integrated_sha=revision,
            ),
        )
        prior = LandingFact(
            "epic-child",
            target,
            revision,
            {
                "kind": "terminal_audit",
                "target_sha": git.commits["child-on-parent"],
            },
            NOW.isoformat(),
            PROJECT_ID,
            state=LandingState.LANDED,
            durable=True,
        )
        requests = (
            LandingRequest(
                "epic-child",
                target,
                revision,
                prior=prior,
                trusted_target_revision=git.commits["child-on-parent"],
            ),
        )
    elif source == "OOMPAH-748":
        assert git is not None
        nested = native.tracker.fetch_issue_detail(task_id)
        assert nested is not None and nested.parent_id
        source_branch = f"epic-{task_id}"
        target = f"epic-{nested.parent_id}"
        revision = git.commits["child-head"]
        subprocess.run(
            [
                "git",
                "update-ref",
                f"refs/heads/{target}",
                git.commits["child-on-parent"],
            ],
            cwd=git.path,
            check=True,
        )
        _persist_submission(
            native,
            task_id,
            IntegrationRecord(
                state="integrated",
                mode="queue",
                task_branch=source_branch,
                base_branch=target,
                head_sha=revision,
                integrated_sha=revision,
            ),
        )
        requests = (LandingRequest(source_branch, target, revision),)
    elif source == "OOMPAH-749":
        _persist_submission(
            native,
            task_id,
            IntegrationRecord(
                state="ready",
                mode="queue",
                task_branch="task-live",
                base_branch="main",
                head_sha="a" * 40,
            ),
        )

    collector = WorkflowFactCollector(
        project_id=PROJECT_ID,
        tracker=native.tracker,
        sources=_external_sources(source),
        landing_collector=(
            GitLandingCollector(git.path, project_id=PROJECT_ID, clock=lambda: NOW)
            if git is not None
            else None
        ),
        integration_queue=queue,
        clock=lambda: NOW,
    )
    return ProductionReplay(
        scenario, native, git, task_id, collector, requests, queue
    )


@pytest.mark.parametrize("scenario", INCIDENTS, ids=lambda item: item.source_task_id)
def test_incident_decision_scheduler_ledger_and_ui_share_one_reason(
    tmp_path, scenario
):
    replay = _prepare(tmp_path, scenario)
    decision = replay.decision()
    expected = scenario.expected

    assert decision.reason_code == expected.reason_code
    assert decision.disposition is expected.disposition
    assert decision.responsible_owner is expected.owner
    assert decision.durable_jobs == tuple(sorted(expected.durable_jobs))

    projection = project_work_decision(decision)
    store = WorkflowJobStore(str(tmp_path / f"{scenario.source_task_id}-jobs.sqlite3"))
    scheduler = WorkflowJobScheduler(store=store)
    first = scheduler.reconcile((decision,))
    duplicate = scheduler.reconcile((decision,))
    jobs = store.list_jobs()

    assert projection["reason_code"] == decision.reason_code
    assert {job.reason_code for job in jobs} <= {projection["reason_code"]}
    assert len(jobs) == len(expected.durable_jobs)
    assert duplicate.jobs_created == 0
    assert duplicate.jobs_replayed == len(expected.durable_jobs)
    if scenario.source_task_id == "OOMPAH-748":
        task = replay.task
        assert task.parent_id
        containment = replay.facts().fact(FactDomain.CONTAINMENT)
        assert containment.value == {
            "parent_id": task.parent_id,
            "epic_branch": f"epic-{task.identifier}",
            "target_branch": f"epic-{task.parent_id}",
            "children": (),
            "acyclic": True,
            "cycle": None,
        }
        assert replay.git is not None
        epic_store = WorkflowJobStore(str(tmp_path / "OOMPAH-748-epic.sqlite3"))
        epic_batch = EpicWorkflowController(
            collector=EpicFactCollector(
                project_id=PROJECT_ID,
                tracker=replay.native.tracker,
                default_branch="main",
                repo_path=replay.git.path,
                sources=_external_sources(scenario.source_task_id),
            ),
            store=epic_store,
        ).evaluate((task,), persist_evidence=False)
        assert epic_batch.tasks[0].decision.reason_code == projection["reason_code"]
        epic_store.close()
    store.close()
    if replay.queue is not None:
        replay.queue.close()


def test_live_integration_outranks_bounded_historical_cursor_batches(tmp_path):
    replay = _prepare(tmp_path, INCIDENTS_BY_ID["OOMPAH-749"])
    queue = IntegrationQueueStore(str(tmp_path / "history-integration.sqlite3"))
    for index in range(3):
        task_id = f"HISTORY-{index}"
        queue.enqueue(
            project_id=PROJECT_ID,
            epic_id="HISTORY-EPIC",
            task_id=task_id,
            task_branch=f"history-{index}",
            head_sha=str(index + 1) * 40,
        )
        claimed = queue.claim_next(
            project_id=PROJECT_ID,
            epic_id="HISTORY-EPIC",
            lease_owner=f"history-owner-{index}",
            dependency_map={task_id: ()},
            satisfied=set(),
        )
        assert claimed is not None
        assert queue.complete(
            PROJECT_ID, task_id, lease_owner=f"history-owner-{index}"
        )

    queue.enqueue(
        project_id=PROJECT_ID,
        epic_id="LIVE-EPIC",
        task_id=replay.task_id,
        task_branch="task-live",
        head_sha="a" * 40,
        base_branch="main",
    )
    live_lease = queue.claim_next(
        project_id=PROJECT_ID,
        epic_id="LIVE-EPIC",
        lease_owner="live-integrator",
        dependency_map={replay.task_id: ()},
        satisfied=set(),
    )
    assert live_lease is not None
    replay.collector.integration_queue = queue
    replay.queue = queue
    decision = replay.decision()
    assert decision.reason_code == "integration.live_claim_precedes_history"
    assert decision.durable_jobs == ("integration_attempt",)

    jobs = WorkflowJobStore(str(tmp_path / "history-jobs.sqlite3"))
    WorkflowJobScheduler(store=jobs).reconcile((decision,))
    staged: list[str] = []
    orchestrator = SimpleNamespace(
        integration_queue=queue,
        workflow_job_store=jobs,
        config=SimpleNamespace(integration_audit_batch_size=1),
        _maintenance_cursors={},
        request_refresh=lambda: None,
    )

    def set_cursor(name, value):
        if value is None:
            orchestrator._maintenance_cursors.pop(name, None)
        else:
            orchestrator._maintenance_cursors[name] = value

    async def stage_history(item, **_kwargs):
        staged.append(item.task_id)
        return True

    async def replay_batch(*, project_id, expected_cursor):
        return await Orchestrator._replay_project_integrated_audit_batch_owned(
            orchestrator,
            project_id=project_id,
            expected_cursor=expected_cursor,
        )

    orchestrator._set_maintenance_cursor = set_cursor
    orchestrator._stage_integrated_task_audit = stage_history
    orchestrator._replay_project_integrated_audit_batch = replay_batch
    first_history = schedule_project_historical_replay(
        orchestrator, jobs, PROJECT_ID
    )
    assert first_history is not None

    first_claim = jobs.claim_next(lease_owner="ordering-probe", lease_seconds=30)
    assert first_claim is not None
    assert first_claim.action == "integration_attempt"
    jobs.complete(first_claim.job_id, first_claim.lease_token or "")

    backend = OrchestratorIntegrationActionBackend(
        orchestrator,
        SimpleNamespace(
            project_id=PROJECT_ID,
            tracker=replay.native.tracker,
            collector=replay.collector,
        ),
    )
    worker = DurableWorkflowWorker(
        store=jobs,
        handlers={
            "historical_audit_replay_batch": IntegrationActionHandler(
                "historical_audit_replay_batch",
                backend,
                domain=WorkflowActionDomain.AUDIT,
            )
        },
        transition_services={},
        worker_id="history-worker",
    )
    results = [
        asyncio.run(
            worker.run_once(actions=("historical_audit_replay_batch",))
        )
        for _ in range(3)
    ]

    assert all(
        result.disposition is WorkflowRunDisposition.COMPLETED
        for result in results
    )
    assert staged == ["HISTORY-0", "HISTORY-1", "HISTORY-2"]
    history_jobs = [
        job
        for job in jobs.list_jobs()
        if job.action == "historical_audit_replay_batch"
    ]
    assert len(history_jobs) == 3
    assert all(job.priority > first_claim.priority for job in history_jobs)
    jobs.close()
    queue.close()


def _integration_worker(replay: ProductionReplay, store: WorkflowJobStore, journal):
    orchestrator = SimpleNamespace(
        integration_queue=(
            replay.queue or SimpleNamespace(get=lambda *_args, **_kwargs: None)
        ),
        config=SimpleNamespace(quality_gate_timeout_seconds=30),
        project_store=SimpleNamespace(
            get=lambda _project_id: SimpleNamespace(default_branch="main")
        ),
        request_refresh=lambda: None,
    )
    binding = SimpleNamespace(
        project_id=PROJECT_ID,
        tracker=replay.native.tracker,
        collector=replay.collector,
    )
    backend = OrchestratorIntegrationActionBackend(orchestrator, binding)
    action = replay.decision().durable_jobs[0]
    handler = IntegrationActionHandler(
        action, backend, domain=WorkflowActionDomain.TRACKER
    )
    service = TaskTransitionService(
        project_id=PROJECT_ID,
        tracker=replay.native.tracker,
        journal=journal,
    )
    return DurableWorkflowWorker(
        store=store,
        handlers={action: handler},
        transition_services={PROJECT_ID: service},
        worker_id="restarted-production-worker",
        lease_seconds=30,
        heartbeat_seconds=10,
    )


def test_direct_maintenance_recovers_one_abandoned_job_through_production_handler(
    tmp_path,
):
    replay = _prepare(tmp_path, INCIDENTS_BY_ID["OOMPAH-731"])
    path = tmp_path / "restart-jobs.sqlite3"
    store = WorkflowJobStore(str(path))
    controller = IntegrationWorkflowController(
        collector=replay.collector,
        store=store,
    )
    batch, scheduled = controller.reconcile((replay.task,))
    assert batch.tasks[0].decision.durable_jobs == ("terminal_audit_done",)
    assert scheduled.jobs_created == 1
    claimed = store.claim_next(
        lease_owner="crashed-worker",
        lease_seconds=30,
        actions=("terminal_audit_done",),
    )
    assert claimed is not None
    store.close()

    restarted = WorkflowJobStore(str(path))
    assert restarted.recover_abandoned(
        lease_owner="crashed-worker",
        project_id=PROJECT_ID,
        actions=("terminal_audit_done",),
        phases=(claimed.phase,),
        limit=1,
    ) == 1
    journal = TransitionJournal(str(tmp_path / "restart-transitions.sqlite3"))
    worker = _integration_worker(replay, restarted, journal)
    audit = _AuditStage(replay.native.tracker)
    worker.transition_services[PROJECT_ID].terminal_adapter = audit

    result = asyncio.run(worker.run_once(actions=("terminal_audit_done",)))

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert len(audit.intents) == 1
    assert audit.intents[0].requested_status == "Done"
    assert replay.task.state == IN_VALIDATION
    assert restarted.list_jobs()[0].state is WorkflowJobState.COMPLETED
    restarted.close()
    journal.close()


def test_direct_maintenance_verify_build_race_does_not_adopt_new_authority(
    tmp_path,
):
    replay = _prepare(tmp_path, INCIDENTS_BY_ID["OOMPAH-731"])
    store = WorkflowJobStore(str(tmp_path / "race-jobs.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=replay.collector,
        store=store,
    )
    _batch, scheduled = controller.reconcile((replay.task,))
    assert scheduled.jobs_created == 1
    backend = OrchestratorIntegrationActionBackend(
        SimpleNamespace(
            integration_queue=SimpleNamespace(get=lambda *_args, **_kwargs: None),
            config=SimpleNamespace(quality_gate_timeout_seconds=30),
            project_store=SimpleNamespace(
                get=lambda _project_id: SimpleNamespace(default_branch="main")
            ),
            request_refresh=lambda: None,
        ),
        SimpleNamespace(
            project_id=PROJECT_ID,
            tracker=replay.native.tracker,
            collector=replay.collector,
        ),
    )
    original_verify = backend.verify_action

    def mutate_after_verify(action, context, effect):
        verified = original_verify(action, context, effect)
        current = replay.task.integration
        assert current is not None
        replay.native.tracker.set_metadata_field(
            replay.task_id,
            "oompah.integration",
            replace(current, maintenance_publication_proven=False).to_dict(),
        )
        return verified

    backend.verify_action = mutate_after_verify
    handler = IntegrationActionHandler(
        "terminal_audit_done", backend, domain=WorkflowActionDomain.TRACKER
    )
    journal = TransitionJournal(str(tmp_path / "race-transitions.sqlite3"))
    worker = DurableWorkflowWorker(
        store=store,
        handlers={"terminal_audit_done": handler},
        transition_services={
            PROJECT_ID: TaskTransitionService(
                project_id=PROJECT_ID,
                tracker=replay.native.tracker,
                journal=journal,
            )
        },
        worker_id="race-worker",
    )

    result = asyncio.run(worker.run_once(actions=("terminal_audit_done",)))

    assert result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert replay.task.state == "Open"
    store.close()
    journal.close()


class _AuditStage:
    def __init__(self, tracker):
        self.tracker = tracker
        self.intents = []

    async def stage(self, intent, _issue):
        self.intents.append(intent)
        self.tracker.update_issue(intent.task_id, status=IN_VALIDATION)
        return TerminalStageResult(True, audit_id="audit-OOMPAH-748")


class _AlreadyRetiredEpicReviewEffects:
    """Contract-complete auto-close port for the no-open-review incident."""

    def __init__(self):
        self.apply_calls = 0
        self.receipts = []

    @staticmethod
    def _receipt(action, epic, facts):
        assert action is EpicAction.AUTO_CLOSE
        containment = facts.fact(FactDomain.CONTAINMENT).value
        source = containment["epic_branch"]
        target = containment["target_branch"]
        landing = next(
            item
            for item in facts.landings
            if item.source == source
            and item.target == target
            and item.state is LandingState.LANDED
        )
        return {
            "effect": action.value,
            "source_branch": source,
            "target_branch": target,
            "source_head": landing.revision,
            "review_retired": True,
        }

    def inspect_epic_effect(self, action, epic, facts, _payload):
        return self._receipt(action, epic, facts)

    def apply_epic_effect(
        self,
        action,
        epic,
        facts,
        _payload,
        *,
        idempotency_key,
        originating_job,
        evidence_generation,
    ):
        assert idempotency_key
        assert originating_job
        assert evidence_generation
        self.apply_calls += 1
        receipt = self._receipt(action, epic, facts)
        self.receipts.append(receipt)
        return receipt

    def verify_epic_effect(self, action, epic, facts, _payload, receipt):
        current = self._receipt(action, epic, facts)
        return (
            current
            if all(receipt.get(key) == value for key, value in current.items())
            else None
        )


def test_nested_done_to_merged_uses_exact_landing_and_terminal_service(tmp_path):
    replay = _prepare(tmp_path, INCIDENTS_BY_ID["OOMPAH-748"])
    store = WorkflowJobStore(str(tmp_path / "nested-jobs.sqlite3"))
    assert replay.git is not None
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id=PROJECT_ID,
            tracker=replay.native.tracker,
            landing_collector=GitLandingCollector(
                replay.git.path, project_id=PROJECT_ID, clock=lambda: NOW
            ),
            sources=_external_sources("OOMPAH-748"),
            clock=lambda: NOW,
        ),
        store=store,
    )
    batch, scheduled = controller.reconcile((replay.task,))
    decision = batch.tasks[0].decision
    assert scheduled.jobs_created == 1
    assert store.list_jobs()[0].action == EpicAction.AUTO_CLOSE.value
    journal = TransitionJournal(str(tmp_path / "nested-transitions.sqlite3"))
    audit = _AuditStage(replay.native.tracker)
    effects = _AlreadyRetiredEpicReviewEffects()
    handler = EpicWorkflowHandler(
        ProductionEpicWorkflowBackend(
            controller=controller,
            tracker=replay.native.tracker,
            effects=effects,
        )
    )
    service = TaskTransitionService(
        project_id=PROJECT_ID,
        tracker=replay.native.tracker,
        journal=journal,
        terminal_adapter=audit,
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers={EpicAction.AUTO_CLOSE.value: handler},
        transition_services={PROJECT_ID: service},
        worker_id="nested-production-worker",
    )

    result = asyncio.run(worker.run_once(actions=(EpicAction.AUTO_CLOSE.value,)))

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert len(audit.intents) == 1
    assert audit.intents[0].requested_status == MERGED
    assert audit.intents[0].precondition_revision == decision.evidence_revision
    assert effects.apply_calls == 1
    assert effects.receipts[0]["source_head"] == replay.git.commits["child-head"]
    assert replay.task.state == IN_VALIDATION
    store.close()
    journal.close()
