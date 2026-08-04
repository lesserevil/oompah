"""Durable review/CI facts, decisions, and job projection coverage."""

from __future__ import annotations

import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import pytest

from oompah.models import Issue
from oompah.review_workflow import (
    ReviewCapacityReconciler,
    ReviewExecutionResult,
    ReviewObservation,
    ReviewObservationUnavailable,
    ReviewRoute,
    ReviewWorkflowHandler,
    ReviewWorkflowController,
    classify_review_result,
    review_fact_source,
)
from oompah.review_capacity import ReviewCapacityStore
from oompah.statuses import (
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    READY_TO_INTEGRATE,
)
from oompah.task_transition_service import (
    TaskTransitionService,
    TerminalStageResult,
    TransitionAuthority,
    TransitionIntent,
    TransitionJournal,
    issue_authority_version,
)
from oompah.workflow_contract import TaskDisposition
from oompah.workflow_facts import (
    FactDomain,
    FactObservation,
    FactState,
    GitLandingCollector,
    LandingFact,
    LandingProofKind,
    LandingRequest,
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


def landing(*, source="task-1", revision=HEAD):
    return LandingFact(
        source,
        "main",
        revision,
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
        ({"state": "open", "ci": "passed"}, "review.ready_to_merge", IN_REVIEW, "review_merge"),
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


def test_deleted_branch_after_merge_uses_real_exact_git_landing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    git("init", "-b", "main")
    git("config", "user.email", "oompah@example.invalid")
    git("config", "user.name", "oompah")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "base.txt")
    git("commit", "-m", "base")
    git("checkout", "-b", "task-1")
    (repo / "change.txt").write_text("change\n", encoding="utf-8")
    git("add", "change.txt")
    git("commit", "-m", "change")
    revision = git("rev-parse", "HEAD")
    git("checkout", "main")
    git("merge", "--ff-only", "task-1")
    git("branch", "-D", "task-1")

    landed = GitLandingCollector(
        str(repo),
        project_id="project-1",
    ).collect(LandingRequest("task-1", "main", revision))
    task = issue(head_sha=revision, review_head=revision)
    decision = evaluate_task(
        task,
        facts(
            task,
            {"state": "missing", "source_deleted": True},
            landings=(landed,),
        ),
    )

    assert landed.state is LandingState.LANDED
    assert landed.revision == revision
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


def test_observed_forge_head_drift_is_reconciled_before_merge():
    task = issue()
    decision = evaluate_task(
        task,
        facts(
            task,
            {"state": "open", "head_sha": "c" * 40, "ci": "passed"},
        ),
    )

    assert decision.reason_code == "review.head_changed"
    assert decision.recommended_status == READY_TO_INTEGRATE
    assert decision.durable_jobs == ("review_head_reconciliation",)


def test_missing_review_cannot_terminalize_an_advanced_unreviewed_head():
    task = issue(head_sha="c" * 40)
    decision = evaluate_task(
        task,
        facts(task, {"state": "missing"}, landings=(landing(),)),
    )

    assert decision.reason_code == "review.head_changed"
    assert decision.recommended_status == READY_TO_INTEGRATE


@pytest.mark.parametrize(
    "unrelated",
    [
        landing(source="another-task"),
        landing(revision="d" * 40),
    ],
)
def test_terminal_review_requires_exact_source_and_revision_landing(unrelated):
    task = issue()
    decision = evaluate_task(
        task,
        facts(task, {"state": "merged"}, landings=(unrelated,)),
    )

    assert decision.reason_code == "review.landing_refresh"
    assert decision.recommended_status is None


def test_project_handoff_capacity_does_not_block_an_existing_review():
    task = issue()

    failed = evaluate_task(
        task,
        facts(
            task,
            {
                "state": "open",
                "ci": "failed",
                "capacity": {"at_capacity": True, "used": 1, "limit": 1},
            },
        ),
    )
    passed = evaluate_task(
        task,
        facts(
            task,
            {
                "state": "open",
                "ci": "passed",
                "capacity": {"at_capacity": True, "used": 1, "limit": 1},
            },
        ),
    )

    assert failed.reason_code == "review.ci_fix_required"
    assert failed.durable_jobs == ("review_ci_repair",)
    assert passed.reason_code == "review.ready_to_merge"
    assert passed.durable_jobs == ("review_merge",)


def test_capacity_release_survives_restart_and_requires_successful_snapshot(tmp_path):
    path = str(tmp_path / "review-capacity.sqlite3")
    store = ReviewCapacityStore(path)
    store.adopt(
        project_id="project-1",
        task_id="TASK-1",
        source_branch="task-1",
        target_branch="main",
        review_id="7",
        reservation_id="reservation-7",
    )
    store.close()

    reopened = ReviewCapacityStore(path)
    reconciler = ReviewCapacityReconciler(reopened)
    unavailable = SimpleNamespace(
        last_open_reviews_fetch_ok=False,
        list_open_reviews=lambda _repo: [],
    )
    with pytest.raises(ReviewObservationUnavailable):
        reconciler.reconcile(
            provider=unavailable,
            repo="org/repo",
            project_id="project-1",
        )
    assert [item.review_id for item in reopened.active("project-1")] == ["7"]

    available = SimpleNamespace(
        last_open_reviews_fetch_ok=True,
        list_open_reviews=lambda _repo: [],
    )
    result = reconciler.reconcile(
        provider=available,
        repo="org/repo",
        project_id="project-1",
    )

    assert result.open_review_ids == ()
    assert result.released == 1
    assert reopened.active("project-1") == []
    reopened.close()


def test_draft_review_is_monitored_without_merge_or_repair():
    task = issue()
    decision = evaluate_task(
        task,
        facts(task, {"state": "open", "draft": True, "ci": "passed"}),
    )

    assert decision.reason_code == "review.draft_wait"
    assert decision.durable_jobs == ("review_monitor",)


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


def test_historical_review_timeout_is_not_misclassified_as_missing():
    class HistoricalTimeoutProvider:
        last_open_reviews_fetch_ok = True
        last_review_fetch_ok = True

        def list_open_reviews(self, _repo):
            return []

        def get_review(self, _repo, _review_id):
            self.last_review_fetch_ok = False
            return None

    task = issue()
    snapshot = WorkflowFactCollector(
        project_id="project-1",
        tracker=Tracker(task),
        sources={
            FactDomain.REVIEW_CI: review_fact_source(
                HistoricalTimeoutProvider(),
                "org/repo",
                review_id="7",
                source_branch=task.work_branch,
            )
        },
    ).collect(task.identifier)

    assert snapshot.fact(FactDomain.REVIEW_CI).state is FactState.ERROR
    assert evaluate_task(task, snapshot).reason_code == "review.provider_unavailable"


def test_exact_review_id_wins_over_reused_source_branch():
    wrong = SimpleNamespace(
        id="8",
        state="open",
        source_branch="task-1",
        target_branch="main",
        head_sha="b" * 40,
        ci_status="failed",
        has_conflicts=False,
    )
    exact = SimpleNamespace(
        id="7",
        state="open",
        source_branch="task-1",
        target_branch="main",
        head_sha=HEAD,
        ci_status="passed",
        has_conflicts=False,
    )
    provider = SimpleNamespace(
        last_open_reviews_fetch_ok=True,
        list_open_reviews=lambda _repo: [wrong, exact],
    )

    observed = review_fact_source(
        provider,
        "org/repo",
        review_id="7",
        source_branch="task-1",
    )(issue())

    assert observed["review_id"] == "7"
    assert observed["head_sha"] == HEAD
    assert observed["ci"] == "passed"


def test_missing_review_uses_explicit_source_probe_without_guessing():
    provider = SimpleNamespace(
        last_open_reviews_fetch_ok=True,
        list_open_reviews=lambda _repo: [],
    )
    source = review_fact_source(
        provider,
        "org/repo",
        source_branch="task-1",
        source_exists=lambda _branch: False,
    )

    observed = source(issue())

    assert observed["state"] == "missing"
    assert observed["source_deleted"] is True
    assert evaluate_task(issue(), facts(issue(), observed)).reason_code == "review.source_deleted"


def test_unknown_source_probe_is_provider_unavailable_not_deleted():
    provider = SimpleNamespace(
        last_open_reviews_fetch_ok=True,
        list_open_reviews=lambda _repo: [],
    )
    source = review_fact_source(
        provider,
        "org/repo",
        source_branch="task-1",
        source_exists=lambda _branch: None,
    )
    task = issue(review_number=None)
    snapshot = WorkflowFactCollector(
        project_id="project-1",
        tracker=Tracker(task),
        sources={FactDomain.REVIEW_CI: source},
    ).collect(task.identifier)

    assert snapshot.fact(FactDomain.REVIEW_CI).state is FactState.ERROR


def test_gitlab_rebase_and_head_fields_survive_normalization():
    observation = ReviewObservation.from_review(
        SimpleNamespace(
            id=7,
            state="open",
            source_branch="task-1",
            target_branch="main",
            head_sha=HEAD,
            ci_status="passed",
            has_conflicts=False,
            needs_rebase=True,
            mergeable_state="",
            draft=False,
        ),
        provider="gitlab",
    )
    task = issue()
    decision = evaluate_task(task, facts(task, observation.to_fact_value()))

    assert observation.head_sha == HEAD
    assert observation.needs_rebase is True
    assert decision.reason_code == "review.rebase_required"


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


def test_older_slow_review_scan_cannot_overwrite_newer_decision(tmp_path):
    task = issue()
    first_started = threading.Event()
    release_first = threading.Event()
    calls_lock = threading.Lock()
    calls = 0

    def review_source(_task):
        nonlocal calls
        with calls_lock:
            calls += 1
            call = calls
        if call == 1:
            first_started.set()
            assert release_first.wait(timeout=5)
            return {"state": "open", "ci": "failed", "head_sha": HEAD}
        return {"state": "open", "ci": "passed", "head_sha": HEAD}

    store = WorkflowJobStore(str(tmp_path / "event-order.sqlite3"))
    controller = ReviewWorkflowController(
        collector=WorkflowFactCollector(
            project_id="project-1",
            tracker=Tracker(task),
            sources={FactDomain.REVIEW_CI: review_source},
        ),
        store=store,
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        older = pool.submit(controller.reconcile, [task])
        assert first_started.wait(timeout=5)
        newer = pool.submit(controller.reconcile, [task])
        try:
            newer_batch, newer_result = newer.result(timeout=5)
        finally:
            release_first.set()
        older_batch, older_result = older.result(timeout=5)

    assert newer_batch.tasks[0].decision.reason_code == "review.ready_to_merge"
    assert newer_result.stale_rejected == 0
    assert older_batch.tasks[0].decision.reason_code == "review.ci_fix_required"
    assert older_result.stale_rejected == 1
    assert controller.projections()[0].reason_code == "review.ready_to_merge"
    active = [job for job in store.list_jobs() if job.is_active]
    assert [job.action for job in active] == ["review_merge"]
    store.close()


@pytest.mark.parametrize(
    ("status", "route"),
    [
        ("passed", ReviewRoute.MERGE),
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


class MutableTracker(Tracker):
    def update_issue(self, identifier, **fields):
        assert identifier == self.current.identifier
        self.current = replace(self.current, state=fields["status"])


class TransitioningRepairBackend(RepairBackend):
    def __init__(self, tracker):
        super().__init__(ReviewExecutionResult("conflict", "conflict detected"))
        self.tracker = tracker

    def build_transition(self, context, verification):
        current = self.tracker.fetch_issue_detail(context.job.task_id)
        return TransitionIntent(
            project_id=context.job.project_id,
            task_id=context.job.task_id,
            expected_status=current.state,
            expected_version=issue_authority_version(current),
            requested_status=NEEDS_REBASE,
            actor="review-workflow",
            authority=TransitionAuthority.ORCHESTRATOR,
            reason_code="review.rebase_required",
            idempotency_key=f"{context.job.idempotency_key}:transition",
            originating_job=context.job.job_id,
            evidence_generation=context.job.generation,
        )


class TerminalBackend(RepairBackend):
    def __init__(self, tracker):
        super().__init__(ReviewExecutionResult("landed", landing=landing()))
        self.tracker = tracker

    def build_transition(self, context, verification):
        current = self.tracker.fetch_issue_detail(context.job.task_id)
        return TransitionIntent(
            project_id=context.job.project_id,
            task_id=context.job.task_id,
            expected_status=current.state,
            expected_version=issue_authority_version(current),
            requested_status=MERGED,
            actor="review-workflow",
            authority=TransitionAuthority.ORCHESTRATOR,
            reason_code="terminal.immediate_target_landing_proven",
            idempotency_key=f"{context.job.idempotency_key}:transition",
            originating_job=context.job.job_id,
            exact_head=HEAD,
        )


class TerminalAdapter:
    def __init__(self, tracker):
        self.tracker = tracker
        self.calls = 0

    async def stage(self, intent, issue):
        self.calls += 1
        self.tracker.current = replace(issue, state=IN_VALIDATION)
        return TerminalStageResult(True, "audit-1")


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
async def test_passed_review_job_executes_the_durable_merge_action(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "review-merge.sqlite3"))
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="facts-1",
            action="review_merge",
            idempotency_key="TASK-1:review-merge:facts-1",
        )
    )
    backend = RepairBackend(ReviewExecutionResult("passed", "ready to merge"))
    worker = DurableWorkflowWorker(
        store=store,
        handlers={"review_merge": ReviewWorkflowHandler(backend)},
        transition_services={},
        worker_id="review-merge-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    assert backend.observe_calls == 1
    assert backend.repair_calls == 1
    store.close()


@pytest.mark.asyncio
async def test_abandoned_review_repair_resumes_through_transition_service(tmp_path):
    path = str(tmp_path / "review-restart.sqlite3")
    store = WorkflowJobStore(path)
    queued = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="facts-1",
            action="review_conflict_repair",
            idempotency_key="TASK-1:review-conflict:facts-1",
        )
    )
    claimed = store.claim_next(lease_owner="dead-worker", lease_seconds=60)
    assert claimed is not None
    assert claimed.state is WorkflowJobState.RUNNING
    store.close()

    reopened = WorkflowJobStore(path)
    tracker = MutableTracker(issue())
    journal = TransitionJournal(str(tmp_path / "review-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1",
        tracker=tracker,
        journal=journal,
    )
    backend = TransitioningRepairBackend(tracker)
    worker = DurableWorkflowWorker(
        store=reopened,
        handlers={"review_conflict_repair": ReviewWorkflowHandler(backend)},
        transition_services={"project-1": service},
        worker_id="replacement-review-worker",
    )
    try:
        assert reopened.recover_abandoned(lease_owner="dead-worker") == 1
        result = await worker.run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert reopened.get(queued.job_id).state is WorkflowJobState.COMPLETED
        assert tracker.current.state == NEEDS_REBASE
        assert backend.observe_calls == 1
        assert backend.repair_calls == 1
    finally:
        journal.close()
        reopened.close()


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


@pytest.mark.asyncio
async def test_landing_completion_is_staged_through_transition_service(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "terminal-worker.sqlite3"))
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="facts-1",
            action="review_terminal_stage",
            idempotency_key="TASK-1:review-terminal:facts-1",
        )
    )
    tracker = MutableTracker(issue())
    adapter = TerminalAdapter(tracker)
    journal = TransitionJournal(str(tmp_path / "terminal-transitions.sqlite3"))
    service = TaskTransitionService(
        project_id="project-1",
        tracker=tracker,
        journal=journal,
        terminal_adapter=adapter,
    )
    backend = TerminalBackend(tracker)
    worker = DurableWorkflowWorker(
        store=store,
        handlers={"review_terminal_stage": ReviewWorkflowHandler(backend)},
        transition_services={"project-1": service},
        worker_id="review-terminal-worker",
    )
    try:
        result = await worker.run_once()

        assert result.disposition is WorkflowRunDisposition.COMPLETED
        assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
        assert tracker.current.state == IN_VALIDATION
        assert adapter.calls == 1
        assert backend.repair_calls == 0
    finally:
        journal.close()
        store.close()
