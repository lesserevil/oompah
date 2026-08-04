"""Durable review/CI facts, decisions, and job projection coverage."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from oompah.models import Issue
from oompah.review_workflow import (
    ReviewExecutionResult,
    ReviewObservation,
    ReviewRoute,
    ReviewWorkflowHandler,
    ReviewWorkflowController,
    classify_review_result,
    review_fact_source,
)
from oompah.statuses import IN_REVIEW, MERGED, NEEDS_CI_FIX, NEEDS_HUMAN, NEEDS_REBASE, OPEN, READY_TO_INTEGRATE
from oompah.workflow_contract import TaskDisposition
from oompah.workflow_facts import (
    FactDomain,
    FactObservation,
    FactState,
    LandingFact,
    LandingProofKind,
    LandingState,
    REQUIRED_FACT_DOMAINS,
    WorkflowFactCollector,
    WorkflowFacts,
)
from oompah.workflow_jobs import WorkflowJobStore
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobState
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    RevalidationResult,
    WorkflowRunDisposition,
)
from oompah.work_decision import evaluate_task

NOW = "2026-08-04T12:00:00+00:00"
HEAD = "a" * 40


def issue(**overrides) -> Issue:
    values = {
        "id": "TASK-1",
        "identifier": "TASK-1",
        "title": "Review task",
        "description": "Actionable review fixture",
        "state": IN_REVIEW,
        "project_id": "project-1",
        "work_branch": "task-1",
        "target_branch": "main",
        "head_sha": HEAD,
        "review_head": HEAD,
        "review_number": "7",
    }
    values.update(overrides)
    return Issue(**values)


class Tracker:
    def __init__(self, current: Issue):
        self.current = current

    def fetch_issue_detail(self, identifier):
        return self.current if identifier == self.current.identifier else None

    def fetch_children(self, identifier):
        return []


def facts(task: Issue, review_value, *, landings=()):
    observations = {
        domain: FactObservation.missing(domain, observed_at=NOW, source="test")
        for domain in REQUIRED_FACT_DOMAINS
    }
    observations.update(
        {
            FactDomain.TASK: FactObservation.known(
                FactDomain.TASK,
                {
                    "identifier": task.identifier,
                    "project_id": task.project_id,
                    "status": task.state,
                    "target_branch": task.target_branch,
                    "work_branch": task.work_branch,
                    "head_sha": task.head_sha,
                    "review_head": task.review_head,
                },
                observed_at=NOW,
                source="tracker",
            ),
            FactDomain.DEPENDENCIES: FactObservation.known(
                FactDomain.DEPENDENCIES,
                {"finish": [], "hard_start": []},
                observed_at=NOW,
                source="tracker",
            ),
            FactDomain.CONTAINMENT: FactObservation.known(
                FactDomain.CONTAINMENT,
                {"parent_id": None, "children": []},
                observed_at=NOW,
                source="tracker",
            ),
            FactDomain.REVIEW_CI: FactObservation.known(
                FactDomain.REVIEW_CI,
                review_value,
                observed_at=NOW,
                source="forge",
            ),
            FactDomain.RETRY_BUDGET: FactObservation.known(
                FactDomain.RETRY_BUDGET,
                {"remaining": 3},
                observed_at=NOW,
                source="jobs",
            ),
            FactDomain.CONFIG: FactObservation.known(
                FactDomain.CONFIG,
                {"version": 1},
                observed_at=NOW,
                source="config",
            ),
        }
    )
    if landings:
        observations[FactDomain.LANDING] = FactObservation.known(
            FactDomain.LANDING,
            {"evidence_revisions": [item.evidence_revision for item in landings]},
            observed_at=NOW,
            source="git",
        )
    return WorkflowFacts(
        "project-1", task.identifier, NOW, observations, landings=landings
    )


def landing():
    return LandingFact(
        "task-1",
        "main",
        HEAD,
        {"kind": LandingProofKind.MERGE_COMMIT.value, "merge_sha": "b" * 40},
        NOW,
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )


@pytest.mark.parametrize(
    ("value", "reason", "status", "job"),
    [
        ({"state": "open", "ci": "pending"}, "review.ci_pending", IN_REVIEW, "review_monitor"),
        ({"state": "open", "ci": "failed"}, "review.ci_fix_required", NEEDS_CI_FIX, "review_ci_repair"),
        ({"state": "open", "ci": "passed", "conflict": True}, "review.rebase_required", NEEDS_REBASE, "review_conflict_repair"),
        ({"state": "closed_unmerged"}, "review.closed_unmerged", OPEN, "review_closed_repair"),
        ({"state": "missing"}, "review.missing_artifact", IN_REVIEW, "review_refresh"),
        ({"state": "open", "ci": "passed", "capacity": {"at_capacity": True, "limit": 1}}, "review.capacity_wait", IN_REVIEW, "review_capacity_recheck"),
    ],
)
def test_review_decisions_have_one_owner_and_durable_reassessment(value, reason, status, job):
    task = issue()
    decision = evaluate_task(task, facts(task, value))

    assert decision.reason_code == reason
    assert decision.recommended_status == status if status != IN_REVIEW else decision.recommended_status is None
    assert decision.next_reassessment_at is not None
    assert decision.durable_jobs == (job,)
    assert decision.responsible_owner.value in {"review_monitor", "repair_worker"}


def test_merged_review_requires_positive_landing_fact_before_terminal_transition():
    task = issue()
    decision = evaluate_task(
        task,
        facts(task, {"state": "merged", "review_id": "7"}, landings=(landing(),)),
    )

    assert decision.disposition is TaskDisposition.TERMINAL
    assert decision.recommended_status == MERGED
    assert decision.reason_code == "terminal.immediate_target_landing_proven"
    assert decision.durable_jobs == ("review_terminal_stage",)


def test_deleted_source_after_merge_uses_landing_fact_for_terminal_transition():
    task = issue()
    decision = evaluate_task(
        task,
        facts(
            task,
            {"state": "missing", "source_deleted": True, "review_id": "7"},
            landings=(landing(),),
        ),
    )

    assert decision.disposition is TaskDisposition.TERMINAL
    assert decision.reason_code == "terminal.immediate_target_landing_proven"
    assert decision.recommended_status == MERGED


def test_changed_head_after_recorded_merge_returns_to_exact_review_queue():
    task = issue(head_sha="c" * 40)
    decision = evaluate_task(
        task,
        facts(task, {"state": "merged", "review_id": "7"}),
    )

    assert decision.reason_code == "review.head_changed"
    assert decision.recommended_status == READY_TO_INTEGRATE
    assert decision.durable_jobs == ("review_head_reconciliation",)


def test_target_mismatch_is_actionable_and_not_silently_merged():
    task = issue()
    decision = evaluate_task(
        task,
        facts(task, {"state": "open", "target_branch": "develop", "ci": "passed"}),
    )

    assert decision.action_required
    assert decision.recommended_status == NEEDS_HUMAN
    assert decision.reason_code == "review.merge_target_mismatch"


def test_github_and_gitlab_review_shapes_share_one_normalized_fact():
    github = ReviewObservation.from_review(
        SimpleNamespace(
            id=7,
            state="open",
            source_branch="task-1",
            target_branch="main",
            head_sha=HEAD,
            ci_status="passed",
            has_conflicts=False,
            mergeable_state="clean",
            draft=False,
        ),
        provider="github",
    )
    gitlab = ReviewObservation.from_review(
        SimpleNamespace(
            id=7,
            state="open",
            source_branch="task-1",
            target_branch="main",
            head_sha=HEAD,
            ci_status="passed",
            has_conflicts=False,
            mergeable_state="clean",
            draft=False,
        ),
        provider="gitlab",
    )

    assert {
        key: value
        for key, value in github.to_fact_value().items()
        if key != "provider"
    } == {
        key: value
        for key, value in gitlab.to_fact_value().items()
        if key != "provider"
    }


def test_provider_timeout_is_error_but_successful_empty_listing_is_missing():
    timeout_provider = SimpleNamespace(
        last_open_reviews_fetch_ok=False,
        list_open_reviews=lambda _repo: [],
    )
    empty_provider = SimpleNamespace(
        last_open_reviews_fetch_ok=True,
        list_open_reviews=lambda _repo: [],
    )
    task = issue()

    timeout_source = review_fact_source(
        timeout_provider, "org/repo", source_branch=task.work_branch
    )
    empty_source = review_fact_source(
        empty_provider, "org/repo", source_branch=task.work_branch
    )
    tracker = Tracker(task)
    timeout_snapshot = WorkflowFactCollector(
        project_id="project-1", tracker=tracker, sources={FactDomain.REVIEW_CI: timeout_source}
    ).collect(task.identifier)
    empty_snapshot = WorkflowFactCollector(
        project_id="project-1", tracker=tracker, sources={FactDomain.REVIEW_CI: empty_source}
    ).collect(task.identifier)
    timeout_fact = timeout_snapshot.fact(FactDomain.REVIEW_CI)
    empty_fact = empty_snapshot.fact(FactDomain.REVIEW_CI)

    assert timeout_fact.state is FactState.ERROR
    assert timeout_fact.error_code == "review_ci_reviewobservationunavailable"
    assert empty_fact.state is FactState.KNOWN
    assert empty_fact.value["state"] == "missing"
    assert evaluate_task(task, timeout_snapshot).reason_code == "review.provider_unavailable"
    assert evaluate_task(task, empty_snapshot).reason_code == "review.missing_artifact"


def test_controller_projects_the_same_reason_it_schedules(tmp_path):
    task = issue()
    collector = WorkflowFactCollector(
        project_id="project-1",
        tracker=Tracker(task),
        sources={
            FactDomain.REVIEW_CI: lambda _task: {
                "state": "open",
                "ci": "failed",
                "review_id": "7",
                "source_branch": "task-1",
                "target_branch": "main",
            }
        },
    )
    store = WorkflowJobStore(str(tmp_path / "reviews.sqlite3"))
    controller = ReviewWorkflowController(collector=collector, store=store)

    batch, scheduled = controller.reconcile([task])
    projection = controller.projections()[0]

    assert scheduled.jobs_created == 1
    assert batch.tasks[0].decision.reason_code == "review.ci_fix_required"
    assert projection.reason_code == batch.tasks[0].decision.reason_code
    assert projection.active_job_state == "queued"
    assert projection.durable_jobs == ("review_ci_repair",)
    store.close()


@pytest.mark.parametrize(
    ("status", "route"),
    [
        ("passed", ReviewRoute.OBSERVED),
        ("open", ReviewRoute.OBSERVED),
        ("ci_failure", ReviewRoute.CI_REPAIR),
        ("conflict", ReviewRoute.CONFLICT_REPAIR),
        ("closed_unmerged", ReviewRoute.CLOSED_REPAIR),
        ("provider_unavailable", ReviewRoute.RETRY),
        ("merged", ReviewRoute.RETRY),
    ],
)
def test_review_action_classification_is_bounded(status, route):
    result = ReviewExecutionResult(status, status)
    if route is ReviewRoute.LANDED:
        result = ReviewExecutionResult(status, status, landing=landing())
    assert classify_review_result(result).route is route


class RepairBackend:
    def __init__(self, result):
        self.result = result
        self.observe_calls = 0
        self.repair_calls = 0

    def revalidate(self, context):
        return RevalidationResult(context.job.generation)

    def observe(self, context):
        self.observe_calls += 1
        return self.result

    def repair(self, context):
        self.repair_calls += 1
        return ReviewExecutionResult("repaired", "repair applied")

    def build_transition(self, context, verification):
        return None


@pytest.mark.asyncio
async def test_durable_review_repair_job_is_idempotent_and_restart_safe(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "worker.sqlite3"))
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="facts-1",
            action="review_conflict_repair",
            idempotency_key="TASK-1:review-conflict:facts-1",
        )
    )
    backend = RepairBackend(ReviewExecutionResult("conflict", "conflict detected"))
    worker = DurableWorkflowWorker(
        store=store,
        handlers={"review_conflict_repair": ReviewWorkflowHandler(backend)},
        transition_services={},
        worker_id="review-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    assert backend.observe_calls == 1
    assert backend.repair_calls == 1
    store.close()


@pytest.mark.asyncio
async def test_landing_observation_is_verified_without_repeating_forge_action(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "terminal.sqlite3"))
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="facts-1",
            action="review_terminal_stage",
            idempotency_key="TASK-1:review-terminal:facts-1",
        )
    )
    backend = RepairBackend(ReviewExecutionResult("landed", landing=landing()))
    worker = DurableWorkflowWorker(
        store=store,
        handlers={"review_terminal_stage": ReviewWorkflowHandler(backend)},
        transition_services={},
        worker_id="review-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    assert backend.repair_calls == 0
    store.close()
