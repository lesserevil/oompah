from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

import oompah.review_workflow_adapter as adapter_module
from oompah.models import Issue
from oompah.review_capacity import ReviewCapacityStore
from oompah.review_workflow import ReviewWorkflowController
from oompah.review_workflow_adapter import (
    FreshReviewFactSource,
    build_review_workflow_handlers,
)
from oompah.scm import CIStatus, ReviewRequest
from oompah.statuses import IN_REVIEW, NEEDS_CI_FIX
from oompah.task_transition_service import TaskTransitionService, TransitionJournal
from oompah.workflow_facts import FactDomain, FactState, WorkflowFactCollector
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobStore
from oompah.workflow_worker import DurableWorkflowWorker, WorkflowRunDisposition


HEAD = "a" * 40


def review(
    *,
    state: str = "open",
    ci: CIStatus = CIStatus.PENDING,
    head: str = HEAD,
    conflict: bool = False,
) -> ReviewRequest:
    return ReviewRequest(
        id="17",
        title="review",
        url="https://example.test/reviews/17",
        author="worker",
        state=state,
        source_branch="TASK-1",
        target_branch="main",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        ci_status=ci,
        has_conflicts=conflict,
        head_sha=head,
    )


class Provider:
    def __init__(self, reviews=None):
        self.reviews = list(reviews or [])
        self.last_open_reviews_fetch_ok = True
        self.last_review_fetch_ok = True
        self.list_calls = 0
        self.merge_calls = 0

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

    def enable_auto_merge(self, repo, review_id):
        return self.merge_review(repo, review_id)


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
    )


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
