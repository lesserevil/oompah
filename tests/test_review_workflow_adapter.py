from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

import oompah.review_workflow_adapter as adapter_module
from oompah.integration import (
    IntegrationRecord,
    REVIEW_GENERATION_REQUEUE_WAIT_REASON,
    review_generation_requeue_marker,
)
from oompah.models import Issue
from oompah.review_capacity import ReviewCapacityStore
from oompah.review_workflow import ReviewWorkflowController
from oompah.review_workflow_adapter import (
    FreshReviewFactSource,
    build_review_workflow_handlers,
)
from oompah.scm import CIStatus, ReviewRequest
from oompah.statuses import (
    DONE,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_CI_FIX,
    READY_TO_INTEGRATE,
)
from oompah.terminal_audit import TargetState
from oompah.task_transition_service import (
    TaskTransitionService,
    TerminalStageResult,
    TransitionJournal,
)
from oompah.workflow_facts import (
    FactDomain,
    FactState,
    LandingFact,
    LandingProofKind,
    LandingState,
    WorkflowFactCollector,
)
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobSpec,
    WorkflowJobStore,
)
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    EffectResult,
    VerificationResult,
    WorkflowActionError,
    WorkflowJobContext,
    WorkflowRunDisposition,
)


HEAD = "a" * 40
BASE = "d" * 40
NOW = "2026-08-10T12:00:00+00:00"


def review(
    *,
    state: str = "open",
    ci: CIStatus = CIStatus.PENDING,
    head: str = HEAD,
    base: str = BASE,
    conflict: bool = False,
    draft: bool = False,
    review_id: str = "17",
    source: str = "TASK-1",
    target: str = "main",
    source_repository: str = "owner/repo",
    target_repository: str = "owner/repo",
) -> ReviewRequest:
    return ReviewRequest(
        id=review_id,
        title="review",
        url="https://example.test/reviews/17",
        author="worker",
        state=state,
        source_branch=source,
        target_branch=target,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        ci_status=ci,
        has_conflicts=conflict,
        head_sha=head,
        base_sha=base,
        source_repository=source_repository,
        target_repository=target_repository,
        draft=draft,
    )


class Provider:
    def __init__(self, reviews=None):
        self.reviews = list(reviews or [])
        self.last_open_reviews_fetch_ok = True
        self.last_review_fetch_ok = True
        self.list_calls = 0
        self.merge_calls = 0
        self.merge_heads = []

    def provider_name(self):
        return "test-forge"

    def list_open_reviews(self, repo):
        assert repo.endswith("/repo")
        self.list_calls += 1
        return [item for item in self.reviews if item.state == "open"]

    def get_review(self, repo, review_id):
        return next((item for item in self.reviews if item.id == review_id), None)

    def merge_review(self, repo, review_id):
        self.merge_calls += 1
        item = self.get_review(repo, review_id)
        assert item is not None
        item.state = "merged"
        return True, "merged"

    def merge_review_exact(self, repo, review_id, expected_head_sha):
        item = self.get_review(repo, review_id)
        assert item is not None
        if item.head_sha != expected_head_sha:
            return False, "head changed"
        self.merge_heads.append(expected_head_sha)
        return self.merge_review(repo, review_id)

    def enable_auto_merge(self, repo, review_id):
        return self.merge_review(repo, review_id)

    def enable_auto_merge_exact(self, repo, review_id, expected_head_sha):
        return self.merge_review_exact(repo, review_id, expected_head_sha)


class Tracker:
    def __init__(self, task):
        self.task = task
        self.updates = []

    def fetch_issue_detail(self, identifier):
        return self.task if identifier == self.task.identifier else None

    def fetch_children(self, _identifier):
        return []

    def update_issue(self, identifier, **fields):
        assert identifier == self.task.identifier
        self.updates.append(dict(fields))
        self.task = replace(self.task, state=fields["status"])

    def invalidate_read_cache(self):
        return None

    def set_metadata_field(self, identifier, key, value):
        assert identifier == self.task.identifier
        assert key == "oompah.integration"
        self.task = replace(
            self.task,
            integration=IntegrationRecord.from_dict(value),
        )


def task(project_id="project-1"):
    return Issue(
        id="TASK-1",
        identifier="TASK-1",
        title="task",
        description="review task",
        state=IN_REVIEW,
        project_id=project_id,
        work_branch="TASK-1",
        target_branch="main",
        review_number="17",
        review_head=HEAD,
        integration=IntegrationRecord(
            state="ready",
            mode="standalone",
            task_branch="TASK-1",
            base_branch="main",
            base_sha=BASE,
            head_sha=HEAD,
        ),
    )


class LandedCollector:
    def __init__(self, project_id="project-1"):
        self.project_id = project_id

    def collect(self, request):
        return LandingFact(
            request.source,
            request.target,
            request.revision,
            {"kind": LandingProofKind.MERGE_COMMIT.value, "merge_sha": "b" * 40},
            NOW,
            self.project_id,
            state=LandingState.LANDED,
            durable=True,
        )


class RecordingTerminalAdapter:
    def __init__(self, tracker):
        self.tracker = tracker
        self.intents = []

    async def stage(self, intent, issue):
        self.intents.append(intent)
        self.tracker.task = replace(issue, state=IN_VALIDATION)
        return TerminalStageResult(True, "audit-1")


def composition(tmp_path, monkeypatch, provider, *, project_id="project-1"):
    tracker = Tracker(task(project_id))
    project = SimpleNamespace(
        id=project_id,
        repo_url="https://example.test/owner/repo.git",
        access_token=None,
        max_in_flight_prs=2,
        merge_queue_enabled=False,
    )
    project_store = SimpleNamespace(
        get=lambda wanted: project if wanted == project_id else None
    )
    monkeypatch.setattr(adapter_module, "detect_provider", lambda *args, **kwargs: provider)
    monkeypatch.setattr(adapter_module, "extract_repo_slug", lambda _url: "owner/repo")
    source = FreshReviewFactSource(
        SimpleNamespace(project_store=project_store), project_id=project_id
    )
    sources = {
        FactDomain.TERMINAL_AUDIT: lambda _issue: {"phase": "none"},
        FactDomain.REVIEW_CI: source,
        FactDomain.IMPLEMENTATION_AUTHORITY: lambda _issue: {
            "lease_expires_at": None
        },
        FactDomain.RETRY_BUDGET: lambda _issue: {"remaining": 3},
        FactDomain.CONFIG: lambda _issue: {"version": 1},
    }
    collector = WorkflowFactCollector(
        project_id=project_id,
        tracker=tracker,
        sources=sources,
    )
    store = WorkflowJobStore(str(tmp_path / f"{project_id}-jobs.sqlite3"))
    controller = ReviewWorkflowController(collector=collector, store=store)
    binding = SimpleNamespace(
        project_id=project_id,
        tracker=tracker,
        review_controller=controller,
    )
    capacity = ReviewCapacityStore(str(tmp_path / f"{project_id}-capacity.sqlite3"))
    orchestrator = SimpleNamespace(
        project_store=project_store,
        review_capacity_store=capacity,
    )
    return orchestrator, binding, store, capacity


def test_fresh_source_distinguishes_provider_failure_from_empty(
    tmp_path, monkeypatch
):
    provider = Provider()
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    try:
        empty = binding.review_controller.evaluate((binding.tracker.task,))
        assert empty.tasks[0].facts.fact(FactDomain.REVIEW_CI).state is FactState.KNOWN
        assert empty.tasks[0].decision.reason_code == "review.missing_artifact"

        provider.last_open_reviews_fetch_ok = False
        failed = binding.review_controller.evaluate((binding.tracker.task,))
        assert failed.tasks[0].facts.fact(FactDomain.REVIEW_CI).state is FactState.ERROR
        assert failed.tasks[0].decision.reason_code == "review.provider_unavailable"
    finally:
        capacity.close()
        store.close()


def test_fresh_source_observation_scope_fetches_open_reviews_once(
    tmp_path, monkeypatch
):
    provider = Provider([review(ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    source = binding.review_controller.collector.sources[FactDomain.REVIEW_CI]
    try:
        with source.observation_scope():
            assert source(task("project-1"))["ci"] == "passed"
            assert source(task("project-1"))["ci"] == "passed"
        assert provider.list_calls == 1

        with source.observation_scope():
            assert source(task("project-1"))["ci"] == "passed"
        assert provider.list_calls == 2
    finally:
        capacity.close()
        store.close()


def test_handler_factory_covers_all_declared_review_actions(
    tmp_path, monkeypatch
):
    provider = Provider([review()])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    try:
        handlers = build_review_workflow_handlers(orchestrator, binding)
        assert set(handlers) == {
            "review_monitor",
            "review_merge",
            "review_refresh",
            "review_ci_repair",
            "review_conflict_repair",
            "review_closed_repair",
            "review_head_reconciliation",
            "review_landing_refresh",
            "review_terminal_stage",
            "review_capacity_recheck",
        }
        assert len({id(handler) for handler in handlers.values()}) == 1
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_ci_repair_uses_transition_service_not_backend_tracker_write(
    tmp_path, monkeypatch
):
    provider = Provider([review(ci=CIStatus.FAILED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[0].decision
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="generation-1",
            action="review_ci_repair",
            idempotency_key="review-ci-1",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    journal = TransitionJournal(str(tmp_path / "transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1", tracker=binding.tracker, journal=journal
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={"project-1": service},
        worker_id="review-worker",
    )
    try:
        result = await worker.run_once()
        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert binding.tracker.task.state == NEEDS_CI_FIX
        assert binding.tracker.updates == [{"status": NEEDS_CI_FIX}]
        assert store.get(queued.job_id).result_transition is not None
    finally:
        journal.close()
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_terminal_stage_forwards_fresh_landing_revision_to_transition_service(
    tmp_path, monkeypatch
):
    provider = Provider([review(state="merged", ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    binding.review_controller.collector.landing_collector = LandedCollector()
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    assert decision.durable_jobs == ("review_terminal_stage",)
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="terminal-generation-1",
            action="review_terminal_stage",
            idempotency_key="review-terminal-1",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    terminal_adapter = RecordingTerminalAdapter(binding.tracker)
    journal = TransitionJournal(str(tmp_path / "terminal-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1",
        tracker=binding.tracker,
        journal=journal,
        terminal_adapter=terminal_adapter,
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={"project-1": service},
        worker_id="review-terminal-worker",
    )
    try:
        result = await worker.run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert binding.tracker.task.state == IN_VALIDATION
        assert len(terminal_adapter.intents) == 1
        assert terminal_adapter.intents[0].requested_status == MERGED
        assert (
            terminal_adapter.intents[0].precondition_revision
            == decision.evidence_revision
        )
        assert store.get(queued.job_id).result_transition is not None
    finally:
        journal.close()
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_shared_child_terminal_stage_requests_done_without_merged_lane(
    tmp_path, monkeypatch
):
    provider = Provider([review(state="merged", ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    parent = Issue(
        id="EPIC-1",
        identifier="EPIC-1",
        title="Parent epic",
        state=DONE,
        issue_type="epic",
        project_id="project-1",
    )
    binding.tracker.task = replace(
        binding.tracker.task,
        parent_id=parent.identifier,
    )
    target_calls = []

    def resolve_target(issue, project_id):
        target_calls.append((issue.identifier, project_id))
        return TargetState.DONE

    orchestrator.resolve_landed_review_terminal_target = resolve_target
    binding.review_controller.collector.landing_collector = LandedCollector()
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="shared-child-terminal-generation",
            action="review_terminal_stage",
            idempotency_key="shared-child-terminal",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    terminal_adapter = RecordingTerminalAdapter(binding.tracker)
    journal = TransitionJournal(str(tmp_path / "shared-child-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1",
        tracker=binding.tracker,
        journal=journal,
        terminal_adapter=terminal_adapter,
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={"project-1": service},
        worker_id="shared-child-terminal-worker",
    )
    try:
        result = await worker.run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert binding.tracker.task.state == IN_VALIDATION
        assert target_calls == [("TASK-1", "project-1")]
        assert len(terminal_adapter.intents) == 1
        assert terminal_adapter.intents[0].requested_status == DONE
        assert (
            terminal_adapter.intents[0].precondition_revision
            == decision.evidence_revision
        )
        assert store.get(queued.job_id).result_transition is not None
    finally:
        journal.close()
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_terminal_stage_fails_closed_when_parent_topology_is_unavailable(
    tmp_path, monkeypatch
):
    class RetryableTopologyError(RuntimeError):
        retryable = True

    provider = Provider([review(state="merged", ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    binding.tracker.task = replace(binding.tracker.task, parent_id="EPIC-1")

    def unavailable_target(_issue, _project_id):
        raise RetryableTopologyError("parent hierarchy unavailable")

    orchestrator.resolve_landed_review_terminal_target = unavailable_target
    backend = build_review_workflow_handlers(orchestrator, binding)[
        "review_terminal_stage"
    ].backend
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="topology-unavailable-generation",
            action="review_terminal_stage",
            idempotency_key="topology-unavailable",
        )
    )
    context = WorkflowJobContext(
        queued,
        asyncio.Event(),
        asyncio.Event(),
    )
    try:
        with pytest.raises(
            WorkflowActionError,
            match="terminal target topology is unavailable",
        ) as exc_info:
            await backend.build_transition(
                context,
                VerificationResult(
                    True,
                    {"evidence_revision": "fresh-landing-revision"},
                ),
            )

        assert exc_info.value.retryable is True
        assert exc_info.value.category is WorkflowFailureCategory.TRANSIENT
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_terminal_stage_verification_rejects_fresh_evidence_drift(
    tmp_path, monkeypatch
):
    provider = Provider([review(state="merged", ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    binding.review_controller.collector.landing_collector = LandedCollector()
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="terminal-generation-before-drift",
            action="review_terminal_stage",
            idempotency_key="review-terminal-before-drift",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    backend = build_review_workflow_handlers(orchestrator, binding)[
        "review_terminal_stage"
    ].backend
    binding.review_controller.collector.sources[FactDomain.CONFIG] = lambda _issue: {
        "version": 2
    }
    context = WorkflowJobContext(queued, asyncio.Event(), asyncio.Event())
    try:
        with pytest.raises(
            WorkflowActionError,
            match="landing evidence changed before terminal transition",
        ):
            await backend.verify(context, EffectResult({"status": "landed"}))
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_terminal_stage_transition_fails_closed_without_verified_revision(
    tmp_path, monkeypatch
):
    provider = Provider([review(state="merged", ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="terminal-generation-no-revision",
            action="review_terminal_stage",
            idempotency_key="review-terminal-no-revision",
        )
    )
    backend = build_review_workflow_handlers(orchestrator, binding)[
        "review_terminal_stage"
    ].backend
    context = WorkflowJobContext(queued, asyncio.Event(), asyncio.Event())
    try:
        with pytest.raises(
            WorkflowActionError,
            match="lacks a freshly verified evidence revision",
        ):
            await backend.build_transition(context, VerificationResult(True, {}))
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_merge_is_idempotent_after_effect_before_worker_checkpoint(
    tmp_path, monkeypatch
):
    provider = Provider([review(state="merged", ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="generation-before-crash",
            action="review_merge",
            idempotency_key="review-merge-before-crash",
            expected_evidence_revision="evidence-before-crash",
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={},
        worker_id="replacement-worker",
    )
    try:
        result = await worker.run_once()
        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert provider.merge_calls == 0
        assert store.get(queued.job_id).checkpoint["effect"]["status"] == "observed"
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_merge_mutates_only_exact_review_and_releases_capacity(
    tmp_path, monkeypatch
):
    provider = Provider([review(ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    capacity.adopt(
        project_id="project-1",
        task_id="TASK-1",
        source_branch="TASK-1",
        target_branch="main",
        review_id="17",
        reservation_id="reservation-17",
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[0].decision
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="generation-merge",
            action="review_merge",
            idempotency_key="review-merge",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={},
        worker_id="review-worker",
    )
    try:
        result = await worker.run_once()
        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert provider.merge_calls == 1
        assert provider.merge_heads == [HEAD]
        assert provider.reviews[0].state == "merged"
        assert capacity.active("project-1") == []
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_head_change_supersedes_queued_merge_without_forge_write(
    tmp_path, monkeypatch
):
    provider = Provider([review(ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[0].decision
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="generation-old-head",
            action="review_merge",
            idempotency_key="review-merge-old-head",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    provider.reviews[0].head_sha = "b" * 40
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={},
        worker_id="review-worker",
    )
    try:
        result = await worker.run_once()
        assert result.disposition is WorkflowRunDisposition.SUPERSEDED
        assert provider.merge_calls == 0
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_draft_sync_replaces_exact_head_and_requeues_for_gate_and_adoption(
    tmp_path, monkeypatch
):
    new_head = "b" * 40
    provider = Provider(
        [review(head=new_head, draft=True, ci=CIStatus.PENDING)]
    )
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    assert decision.reason_code == "review.head_changed"
    assert decision.durable_jobs == ("review_head_reconciliation",)
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="synchronize-b",
            action="review_head_reconciliation",
            idempotency_key="review-head-b",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    journal = TransitionJournal(str(tmp_path / "head-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1", tracker=binding.tracker, journal=journal
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={"project-1": service},
        worker_id="review-worker",
    )
    try:
        result = await worker.run_once()
        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert binding.tracker.task.state == READY_TO_INTEGRATE
        assert binding.tracker.task.review_number == "17"
        assert binding.tracker.task.review_head == HEAD
        assert binding.tracker.task.integration is not None
        assert binding.tracker.task.integration.state == "ready"
        assert binding.tracker.task.integration.head_sha == new_head
        assert binding.tracker.task.integration.base_sha == BASE
        assert provider.merge_calls == 0
        transition = store.get(queued.job_id).result_transition
        assert transition is not None
        assert transition["requested_status"] == READY_TO_INTEGRATE
        assert transition["applied_status"] == READY_TO_INTEGRATE
    finally:
        journal.close()
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_head_reconciliation_resumes_after_metadata_checkpoint_restart(
    tmp_path, monkeypatch
):
    new_head = "b" * 40
    provider = Provider([review(head=new_head, draft=True)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    binding.tracker.task = replace(
        binding.tracker.task,
        integration=replace(
            binding.tracker.task.integration,
            state="ready",
            head_sha=new_head,
            wait_reason=REVIEW_GENERATION_REQUEUE_WAIT_REASON,
            wait_generation=review_generation_requeue_marker(
                "17", new_head, BASE
            ),
        ),
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="restart-after-head-write",
            action="review_head_reconciliation",
            idempotency_key="restart-review-head-b",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    journal = TransitionJournal(str(tmp_path / "restart-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1", tracker=binding.tracker, journal=journal
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={"project-1": service},
        worker_id="replacement-review-worker",
    )
    try:
        result = await worker.run_once()
        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert binding.tracker.task.state == READY_TO_INTEGRATE
        assert binding.tracker.task.integration.head_sha == new_head
        assert store.get(queued.job_id).state.value == "completed"
    finally:
        journal.close()
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_base_only_change_requeues_exact_generation_for_regating(
    tmp_path, monkeypatch
):
    new_base = "e" * 40
    provider = Provider([review(base=new_base, ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    assert decision.reason_code == "review.head_changed"
    assert decision.durable_jobs == ("review_head_reconciliation",)
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="base-only-change",
            action="review_head_reconciliation",
            idempotency_key="base-only-change",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    journal = TransitionJournal(str(tmp_path / "base-only-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1", tracker=binding.tracker, journal=journal
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={"project-1": service},
        worker_id="base-review-worker",
    )
    try:
        result = await worker.run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert binding.tracker.task.state == READY_TO_INTEGRATE
        assert binding.tracker.task.integration.head_sha == HEAD
        assert binding.tracker.task.integration.base_sha == new_base
        assert (
            binding.tracker.task.integration.wait_reason
            == REVIEW_GENERATION_REQUEUE_WAIT_REASON
        )
        assert binding.tracker.task.integration.wait_generation == (
            review_generation_requeue_marker("17", HEAD, new_base)
        )
        assert provider.merge_calls == 0
    finally:
        journal.close()
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_legacy_review_identity_is_enriched_before_merge(
    tmp_path, monkeypatch
):
    provider = Provider([review(ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    binding.tracker.task = replace(
        binding.tracker.task,
        integration=replace(
            binding.tracker.task.integration,
            base_branch=None,
            base_sha=None,
        ),
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    assert decision.reason_code == "review.head_changed"
    assert decision.durable_jobs == ("review_head_reconciliation",)
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="legacy-identity-enrichment",
            action="review_head_reconciliation",
            idempotency_key="legacy-identity-enrichment",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    journal = TransitionJournal(str(tmp_path / "identity-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1", tracker=binding.tracker, journal=journal
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={"project-1": service},
        worker_id="identity-review-worker",
    )
    try:
        result = await worker.run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert binding.tracker.task.state == READY_TO_INTEGRATE
        assert binding.tracker.task.integration.base_branch == "main"
        assert binding.tracker.task.integration.base_sha == BASE
        assert binding.tracker.task.integration.head_sha == HEAD
        assert provider.merge_calls == 0
    finally:
        journal.close()
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_base_only_reconciliation_resumes_after_metadata_checkpoint(
    tmp_path, monkeypatch
):
    new_base = "e" * 40
    provider = Provider([review(base=new_base, draft=True)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    binding.tracker.task = replace(
        binding.tracker.task,
        integration=replace(
            binding.tracker.task.integration,
            base_sha=new_base,
            wait_reason=REVIEW_GENERATION_REQUEUE_WAIT_REASON,
            wait_generation=review_generation_requeue_marker(
                "17", HEAD, new_base
            ),
        ),
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    assert decision.durable_jobs == ("review_head_reconciliation",)
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="base-checkpoint-restart",
            action="review_head_reconciliation",
            idempotency_key="base-checkpoint-restart",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    journal = TransitionJournal(str(tmp_path / "base-restart.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1", tracker=binding.tracker, journal=journal
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={"project-1": service},
        worker_id="base-restart-worker",
    )
    try:
        result = await worker.run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert binding.tracker.task.state == READY_TO_INTEGRATE
        assert binding.tracker.task.integration.base_sha == new_base
        assert provider.merge_calls == 0
    finally:
        journal.close()
        capacity.close()
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed_review",
    [
        review(head="b" * 40, review_id="99"),
        review(head="b" * 40, source="other-task"),
        review(head="b" * 40, target="release/next"),
        review(head="b" * 40, source_repository="fork/repo"),
        review(head="b" * 40, target_repository="other/repo"),
    ],
    ids=["pr", "source", "base", "fork", "target-repository"],
)
async def test_head_reconciliation_fails_closed_on_identity_drift(
    tmp_path, monkeypatch, changed_review
):
    provider = Provider([changed_review])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    # Schedule as if a synchronize event raced an already queued exact-head
    # repair.  The repair itself must still reject every identity mismatch.
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="identity-drift",
            action="review_head_reconciliation",
            idempotency_key=f"identity-drift-{changed_review.id}-{changed_review.source_branch}",
        )
    )
    backend = build_review_workflow_handlers(orchestrator, binding)[
        "review_head_reconciliation"
    ].backend
    context = WorkflowJobContext(queued, asyncio.Event(), asyncio.Event())
    try:
        with pytest.raises(WorkflowActionError):
            await backend.repair(context)
        assert binding.tracker.task.integration.head_sha == HEAD
        assert binding.tracker.task.state == IN_REVIEW
        assert provider.merge_calls == 0
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_synchronize_between_merge_revalidation_and_effect_blocks_merge(
    tmp_path, monkeypatch
):
    new_head = "b" * 40

    class RacingProvider(Provider):
        def list_open_reviews(self, repo):
            observed = super().list_open_reviews(repo)
            if self.list_calls == 2:
                return observed
            if self.list_calls >= 3:
                self.reviews[0].head_sha = new_head
            return [item for item in self.reviews if item.state == "open"]

    provider = RacingProvider([review(ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="merge-before-sync",
            action="review_merge",
            idempotency_key="merge-before-sync",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={},
        worker_id="review-worker",
    )
    try:
        result = await worker.run_once()
        assert result.disposition is WorkflowRunDisposition.SUPERSEDED
        assert store.get(queued.job_id).state.value == "superseded"
        _batch, reconciliation = binding.review_controller.reconcile(
            (binding.tracker.task,)
        )
        assert reconciliation.jobs_created == 1
        active = [job for job in store.list_jobs() if job.is_active]
        assert [job.action for job in active] == ["review_head_reconciliation"]
        assert provider.merge_calls == 0
        assert binding.tracker.task.state == IN_REVIEW
        assert binding.tracker.task.integration.head_sha == HEAD
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_review_successor_regeneration_survives_restart_and_coalesces(
    tmp_path, monkeypatch
):
    new_base = "e" * 40

    class RacingProvider(Provider):
        def list_open_reviews(self, repo):
            observed = super().list_open_reviews(repo)
            if self.list_calls >= 3:
                self.reviews[0].base_sha = new_base
            return observed

    provider = RacingProvider([review(ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="merge-before-base-advance",
            action="review_merge",
            idempotency_key="merge-before-base-advance",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={},
        worker_id="review-worker",
    )
    database = store.path
    store_closed = False
    reopened = None
    try:
        result = await worker.run_once()
        assert result.disposition is WorkflowRunDisposition.SUPERSEDED
        assert store.get(queued.job_id).state.value == "superseded"
        store.close()
        store_closed = True

        reopened = WorkflowJobStore(database)
        binding.review_controller = ReviewWorkflowController(
            collector=binding.review_controller.collector,
            store=reopened,
        )
        created = []
        for _ in range(3):
            _batch, reconciliation = binding.review_controller.reconcile(
                (binding.tracker.task,)
            )
            created.append(reconciliation.jobs_created)

        assert created == [1, 0, 0]
        active = [job for job in reopened.list_jobs() if job.is_active]
        assert [job.action for job in active] == ["review_head_reconciliation"]
        assert reopened.get(queued.job_id).state.value == "superseded"
    finally:
        capacity.close()
        if not store_closed:
            store.close()
        if reopened is not None:
            reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "drift",
    ["fork", "source", "target", "conflict", "missing"],
)
async def test_invalid_merge_races_exhaust_without_forge_write(
    tmp_path, monkeypatch, drift
):
    class InvalidatingProvider(Provider):
        def list_open_reviews(self, repo):
            assert repo.endswith("/repo")
            self.list_calls += 1
            if self.list_calls >= 3:
                if drift == "fork":
                    self.reviews[0].source_repository = "fork/repo"
                elif drift == "source":
                    self.reviews[0].source_branch = "OTHER-BRANCH"
                elif drift == "target":
                    self.reviews[0].target_branch = "release"
                elif drift == "conflict":
                    self.reviews[0].has_conflicts = True
                elif drift == "missing":
                    self.reviews[0].state = "closed"
            return [item for item in self.reviews if item.state == "open"]

    provider = InvalidatingProvider([review(ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation=f"invalid-merge-race-{drift}",
            action="review_merge",
            idempotency_key=f"invalid-merge-race-{drift}",
            expected_evidence_revision=decision.evidence_revision,
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={},
        worker_id="review-worker",
    )
    try:
        result = await worker.run_once()

        assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
        exhausted = store.get(queued.job_id)
        assert exhausted.state.value == "exhausted"
        assert exhausted.failure_category is WorkflowFailureCategory.STALE_EVIDENCE
        assert provider.merge_calls == 0
        assert binding.tracker.task.state == IN_REVIEW
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_persistent_review_provider_error_exhausts_bounded_attempts(
    tmp_path, monkeypatch
):
    provider = Provider([review(ci=CIStatus.PASSED)])
    provider.last_open_reviews_fetch_ok = False
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    assert decision.durable_jobs == ("review_refresh",)
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="persistent-provider-error",
            action="review_refresh",
            idempotency_key="persistent-provider-error",
            expected_evidence_revision=decision.evidence_revision,
            max_attempts=2,
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={},
        worker_id="review-worker",
        retry_delay_seconds=0,
    )
    try:
        first = await worker.run_once()
        second = await worker.run_once()

        assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
        assert second.disposition is WorkflowRunDisposition.ACTION_REQUIRED
        exhausted = store.get(queued.job_id)
        assert exhausted.state.value == "exhausted"
        assert exhausted.attempts == exhausted.max_attempts == 2
        assert provider.merge_calls == 0
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_atomic_merge_precondition_rejects_advance_after_fresh_observation(
    tmp_path, monkeypatch
):
    class CasRacingProvider(Provider):
        def merge_review_exact(self, repo, review_id, expected_head_sha):
            self.reviews[0].head_sha = "b" * 40
            return super().merge_review_exact(repo, review_id, expected_head_sha)

    provider = CasRacingProvider([review(ci=CIStatus.PASSED)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="merge-cas-race",
            action="review_merge",
            idempotency_key="merge-cas-race",
            expected_evidence_revision=decision.evidence_revision,
            max_attempts=3,
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={},
        worker_id="review-worker",
    )
    try:
        result = await worker.run_once()
        assert result.disposition is WorkflowRunDisposition.SUPERSEDED
        assert store.get(queued.job_id).state.value == "superseded"
        _batch, reconciliation = binding.review_controller.reconcile(
            (binding.tracker.task,)
        )
        assert reconciliation.jobs_created == 1
        active = [job for job in store.list_jobs() if job.is_active]
        assert [job.action for job in active] == ["review_head_reconciliation"]
        assert provider.merge_calls == 0
        assert provider.reviews[0].state == "open"
        assert binding.tracker.task.state == IN_REVIEW
    finally:
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_review_advancing_to_c_after_b_write_cannot_transition_b(
    tmp_path, monkeypatch
):
    head_b = "b" * 40
    head_c = "c" * 40

    class AdvancingProvider(Provider):
        def list_open_reviews(self, repo):
            observed = super().list_open_reviews(repo)
            if self.list_calls >= 4:
                self.reviews[0].head_sha = head_c
            return [item for item in self.reviews if item.state == "open"]

    provider = AdvancingProvider([review(head=head_b, draft=True)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision = binding.review_controller.evaluate((binding.tracker.task,)).tasks[
        0
    ].decision
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="head-b-before-c",
            action="review_head_reconciliation",
            idempotency_key="head-b-before-c",
            expected_evidence_revision=decision.evidence_revision,
            max_attempts=3,
        )
    )
    journal = TransitionJournal(str(tmp_path / "head-c-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1", tracker=binding.tracker, journal=journal
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={"project-1": service},
        worker_id="review-worker",
    )
    try:
        result = await worker.run_once()
        assert result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
        assert binding.tracker.task.state == IN_REVIEW
        assert binding.tracker.task.integration.head_sha == head_b
        assert provider.reviews[0].head_sha == head_c
        assert provider.merge_calls == 0

        decision_c = binding.review_controller.evaluate(
            (binding.tracker.task,)
        ).tasks[0].decision
        assert decision_c.reason_code == "review.head_changed"
        assert decision_c.durable_jobs == ("review_head_reconciliation",)
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id="TASK-1",
                generation="head-c-after-b-checkpoint",
                action="review_head_reconciliation",
                idempotency_key="head-c-after-b-checkpoint",
                expected_evidence_revision=decision_c.evidence_revision,
                max_attempts=3,
            )
        )

        result = await worker.run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert binding.tracker.task.state == READY_TO_INTEGRATE
        assert binding.tracker.task.review_head == HEAD
        assert binding.tracker.task.integration.state == "ready"
        assert binding.tracker.task.integration.head_sha == head_c
        assert provider.reviews[0].head_sha == head_c
        assert provider.merge_calls == 0
    finally:
        journal.close()
        capacity.close()
        store.close()


@pytest.mark.asyncio
async def test_base_advancing_again_after_checkpoint_converges_exactly(
    tmp_path, monkeypatch
):
    base_b = "e" * 40
    base_c = "f" * 40

    class AdvancingBaseProvider(Provider):
        def list_open_reviews(self, repo):
            observed = super().list_open_reviews(repo)
            if self.list_calls >= 4:
                self.reviews[0].base_sha = base_c
            return [item for item in self.reviews if item.state == "open"]

    provider = AdvancingBaseProvider([review(base=base_b, draft=True)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    decision_b = binding.review_controller.evaluate(
        (binding.tracker.task,)
    ).tasks[0].decision
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="base-b-before-c",
            action="review_head_reconciliation",
            idempotency_key="base-b-before-c",
            expected_evidence_revision=decision_b.evidence_revision,
            max_attempts=3,
        )
    )
    journal = TransitionJournal(str(tmp_path / "base-c-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1", tracker=binding.tracker, journal=journal
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers=build_review_workflow_handlers(orchestrator, binding),
        transition_services={"project-1": service},
        worker_id="base-review-worker",
    )
    try:
        first = await worker.run_once()

        assert first.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
        assert binding.tracker.task.state == IN_REVIEW
        assert binding.tracker.task.integration.base_sha == base_b
        assert provider.reviews[0].base_sha == base_c

        decision_c = binding.review_controller.evaluate(
            (binding.tracker.task,)
        ).tasks[0].decision
        store.enqueue(
            WorkflowJobSpec(
                project_id="project-1",
                task_id="TASK-1",
                generation="base-c-after-b-checkpoint",
                action="review_head_reconciliation",
                idempotency_key="base-c-after-b-checkpoint",
                expected_evidence_revision=decision_c.evidence_revision,
                max_attempts=3,
            )
        )

        second = await worker.run_once()

        assert second.disposition is WorkflowRunDisposition.COMPLETED
        assert binding.tracker.task.state == READY_TO_INTEGRATE
        assert binding.tracker.task.integration.head_sha == HEAD
        assert binding.tracker.task.integration.base_sha == base_c
        assert provider.merge_calls == 0
    finally:
        journal.close()
        capacity.close()
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("intermediate_state", "intermediate_head"),
    [
        ("blocked", "b" * 40),
        ("ready", "not-an-exact-head"),
        ("ready", "b" * 40),
    ],
    ids=["non-ready", "malformed-head", "unmarked-ready-head"],
)
async def test_head_reconciliation_rejects_untrusted_intermediate_authority(
    tmp_path,
    monkeypatch,
    intermediate_state,
    intermediate_head,
):
    provider = Provider([review(head="c" * 40, draft=True)])
    orchestrator, binding, store, capacity = composition(
        tmp_path, monkeypatch, provider
    )
    binding.tracker.task = replace(
        binding.tracker.task,
        integration=replace(
            binding.tracker.task.integration,
            state=intermediate_state,
            head_sha=intermediate_head,
        ),
    )
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="untrusted-intermediate-head",
            action="review_head_reconciliation",
            idempotency_key=(
                f"untrusted-intermediate-{intermediate_state}-{intermediate_head}"
            ),
        )
    )
    backend = build_review_workflow_handlers(orchestrator, binding)[
        "review_head_reconciliation"
    ].backend
    context = WorkflowJobContext(queued, asyncio.Event(), asyncio.Event())
    try:
        with pytest.raises(WorkflowActionError):
            await backend.repair(context)
        assert binding.tracker.task.state == IN_REVIEW
        assert binding.tracker.task.integration.state == intermediate_state
        assert binding.tracker.task.integration.head_sha == intermediate_head
        assert provider.merge_calls == 0
    finally:
        capacity.close()
        store.close()


def test_sources_route_same_task_identifier_to_exact_project(
    tmp_path, monkeypatch
):
    providers = {
        "project-a": Provider([review(ci=CIStatus.FAILED)]),
        "project-b": Provider([review(ci=CIStatus.PASSED)]),
    }
    projects = {
        key: SimpleNamespace(
            id=key,
            repo_url=f"https://example.test/{key}/repo.git",
            access_token=None,
            max_in_flight_prs=1,
        )
        for key in providers
    }
    monkeypatch.setattr(
        adapter_module,
        "detect_provider",
        lambda url, **_kwargs: providers[url.split("/")[-2]],
    )
    monkeypatch.setattr(
        adapter_module,
        "extract_repo_slug",
        lambda url: "/".join(url.removesuffix(".git").split("/")[-2:]),
    )
    orchestrator = SimpleNamespace(
        project_store=SimpleNamespace(get=lambda project_id: projects.get(project_id))
    )
    source_a = FreshReviewFactSource(orchestrator, project_id="project-a")
    source_b = FreshReviewFactSource(orchestrator, project_id="project-b")

    assert source_a(task("project-a"))["ci"] == "failed"
    assert source_b(task("project-b"))["ci"] == "passed"
    assert providers["project-a"].list_calls == 1
    assert providers["project-b"].list_calls == 1
    with pytest.raises(Exception, match="crossed its project"):
        source_a(task("project-b"))
