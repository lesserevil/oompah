"""Shared-decision and durable-job integration domain coverage."""

from __future__ import annotations

import os
import subprocess
from dataclasses import replace
import pytest

from oompah.integration import IntegrationRecord
from oompah.integration_executor import IntegrationExecutionResult
from oompah.integration_workflow import (
    IntegrationRoute,
    IntegrationWorkflowController,
    IntegrationWorkflowHandler,
    classify_integration_result,
)
from oompah.models import BlockerRef, Issue
from oompah.workflow_contract import READY_TO_INTEGRATE, TaskDisposition
from oompah.workflow_facts import (
    FactDomain,
    GitLandingCollector,
    LandingRequest,
    LandingState,
    WorkflowFactCollector,
)
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobState, WorkflowJobStore
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    RevalidationResult,
    WorkflowRunDisposition,
)


class Tracker:
    def __init__(self, issues):
        self.issues = {issue.identifier: issue for issue in issues}

    def fetch_issue_detail(self, identifier):
        return self.issues.get(identifier)

    def fetch_children(self, identifier):
        return [
            issue for issue in self.issues.values() if issue.parent_id == identifier
        ]


def issue(identifier, *, dependencies=(), state="ready", head=None):
    head = head or (identifier[-1].lower() * 40)
    return Issue(
        id=identifier,
        identifier=identifier,
        title=f"Integrate {identifier}",
        description="Actionable integration fixture",
        state=READY_TO_INTEGRATE,
        project_id="project-1",
        blocked_by=[
            BlockerRef(identifier=dependency, state="Open")
            for dependency in dependencies
        ],
        work_branch=identifier,
        target_branch="main",
        integration=IntegrationRecord(
            state=state,
            task_branch=identifier,
            base_branch="main",
            head_sha=head,
        ),
    )


def collector(tracker, landing_collector=None):
    return WorkflowFactCollector(
        project_id="project-1",
        tracker=tracker,
        landing_collector=landing_collector,
        sources={
            FactDomain.TERMINAL_AUDIT: lambda _: {"phase": "queued"},
            FactDomain.REVIEW_CI: lambda _: {"state": "open"},
            FactDomain.IMPLEMENTATION_AUTHORITY: lambda _: {},
            FactDomain.RETRY_BUDGET: lambda _: {"remaining": 3},
            FactDomain.CONFIG: lambda _: {"version": 1},
        },
    )


def test_controller_evaluates_every_topological_head_and_schedules_one_job(tmp_path):
    tasks = [
        issue("TASK-A"),
        issue("TASK-B"),
        issue("TASK-C", dependencies=("TASK-A",)),
        issue("TASK-D", dependencies=("TASK-B",)),
    ]
    tracker = Tracker(tasks)
    store = WorkflowJobStore(str(tmp_path / "integration.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(tracker), store=store
    )

    batch, scheduled = controller.reconcile(tasks)

    assert batch.topological_batches == (("TASK-A", "TASK-B"), ("TASK-C", "TASK-D"))
    assert batch.cyclic_tasks == ()
    assert {item.task.identifier for item in batch.tasks} == {
        "TASK-A",
        "TASK-B",
        "TASK-C",
        "TASK-D",
    }
    assert {
        item.decision.disposition
        for item in batch.tasks
        if item.task.identifier in {"TASK-A", "TASK-B"}
    } == {TaskDisposition.RETRY_SCHEDULED}
    assert scheduled.jobs_created == 2
    assert {job.task_id for job in store.list_jobs()} == {"TASK-A", "TASK-B"}
    store.close()


def test_dependency_cycle_is_visible_without_hiding_other_ready_work(tmp_path):
    tasks = [
        issue("TASK-A", dependencies=("TASK-B",)),
        issue("TASK-B", dependencies=("TASK-A",)),
        issue("TASK-C"),
    ]
    store = WorkflowJobStore(str(tmp_path / "cycles.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(Tracker(tasks)), store=store
    )

    batch, _ = controller.reconcile(tasks)

    assert batch.topological_batches == (("TASK-C",),)
    assert batch.cyclic_tasks == ("TASK-A", "TASK-B")
    assert {item.decision.disposition for item in batch.tasks[:2]} == {
        TaskDisposition.BLOCKED
    }
    assert {job.task_id for job in store.list_jobs()} == {"TASK-C"}
    store.close()


def test_decision_and_queue_projection_have_exact_reason_parity(tmp_path):
    tasks = [issue("TASK-A"), issue("TASK-B", dependencies=("TASK-A",))]
    store = WorkflowJobStore(str(tmp_path / "projection.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(Tracker(tasks)), store=store
    )
    batch, _ = controller.reconcile(tasks)

    projections = {item.task_id: item for item in controller.projections()}

    for item in batch.tasks:
        projection = projections[item.task.identifier]
        assert projection.reason_code == item.decision.reason_code
        assert projection.disposition == item.decision.disposition.value
        assert projection.waiting_on == tuple(
            unmet.subject for unmet in item.decision.unmet_prerequisites
        )
        assert projection.action_required == item.decision.action_required
    assert projections["TASK-A"].active_job_state == "queued"
    assert projections["TASK-B"].active_job_state is None
    store.close()


@pytest.mark.timeout(30)  # 402 SQLite job writes at WAL-mode throughput takes ~17 s
def test_hundreds_of_history_rows_do_not_hide_eligible_heads(tmp_path):
    history = [issue(f"HISTORY-{index:03d}") for index in range(400)]
    ready = [issue("TASK-X"), issue("TASK-Y")]
    tracker = Tracker([*history, *ready])
    store = WorkflowJobStore(str(tmp_path / "history.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(tracker), store=store
    )

    batch, scheduled = controller.reconcile([*history, *ready])

    assert len(batch.tasks) == 402
    assert scheduled.jobs_created == 402
    assert {"TASK-X", "TASK-Y"} <= {job.task_id for job in store.list_jobs(limit=1000)}
    assert {"TASK-X", "TASK-Y"} <= {
        projection.task_id for projection in controller.projections()
    }
    store.close()


@pytest.mark.parametrize(
    ("status", "route", "retryable"),
    [
        ("integrated", IntegrationRoute.LANDED, False),
        ("conflict", IntegrationRoute.REBASE, False),
        ("needs_rebase", IntegrationRoute.REBASE, False),
        ("ci_failure", IntegrationRoute.CI_FIX, False),
        ("worktree_recovery", IntegrationRoute.RETRY, True),
        ("missing_epic", IntegrationRoute.RETRY, True),
        ("authentication_failed", IntegrationRoute.RETRY, True),
        ("stale_head", IntegrationRoute.SUPERSEDED, False),
        ("dirty_worktree", IntegrationRoute.ACTION_REQUIRED, False),
        ("unknown", IntegrationRoute.ACTION_REQUIRED, False),
    ],
)
def test_every_executor_result_has_one_bounded_route(status, route, retryable):
    classified = classify_integration_result(
        IntegrationExecutionResult(status, f"{status} result")
    )
    assert classified.route is route
    assert classified.retryable is retryable


def git(repo, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Integration Harness",
            "GIT_AUTHOR_EMAIL": "integration@example.invalid",
            "GIT_COMMITTER_NAME": "Integration Harness",
            "GIT_COMMITTER_EMAIL": "integration@example.invalid",
        },
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class GitBackend:
    def __init__(self, repo, *, generation, head):
        self.repo = repo
        self.generation = generation
        self.head = head
        self.collector = GitLandingCollector(repo, project_id="project-1")
        self.integration_calls = 0

    def revalidate(self, context):
        return RevalidationResult(
            self.generation,
            evidence_revision=context.job.expected_evidence_revision,
            head_sha=self.head,
        )

    def observe_landing(self, context):
        return self.collector.collect(
            LandingRequest("task", "main", context.job.expected_head_sha)
        )

    def integrate(self, context):
        self.integration_calls += 1
        git(self.repo, "merge", "--no-ff", "task", "-m", "integrate task")
        return IntegrationExecutionResult(
            "integrated",
            "integrated",
            integrated_sha=git(self.repo, "rev-parse", "HEAD"),
        )

    def build_transition(self, context, verification):
        return None


@pytest.mark.asyncio
async def test_handler_proves_exact_head_with_real_git_and_survives_ref_deletion(
    tmp_path,
):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "base.txt").write_text("base\n")
    git(tmp_path, "add", "base.txt")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "checkout", "-b", "task")
    (tmp_path / "task.txt").write_text("task\n")
    git(tmp_path, "add", "task.txt")
    git(tmp_path, "commit", "-m", "task")
    head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "main")

    path = str(tmp_path / "jobs.sqlite3")
    store = WorkflowJobStore(path)
    store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TASK-1",
            generation="generation-1",
            action="integration_attempt",
            idempotency_key="TASK-1:integration",
            expected_head_sha=head,
        )
    )
    backend = GitBackend(tmp_path, generation="generation-1", head=head)
    worker = DurableWorkflowWorker(
        store=store,
        handlers={"integration_attempt": IntegrationWorkflowHandler(backend)},
        transition_services={},
        worker_id="integrator",
        lease_seconds=30,
        heartbeat_seconds=10,
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert backend.integration_calls == 1
    assert store.list_jobs()[0].state is WorkflowJobState.COMPLETED
    git(tmp_path, "branch", "-D", "task")
    landing = backend.collector.collect(LandingRequest("task", "main", head))
    assert landing.state is LandingState.LANDED
    store.close()


@pytest.mark.asyncio
async def test_changed_source_head_does_not_invalidate_recorded_exact_landing(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "value.txt").write_text("base\n")
    git(tmp_path, "add", "value.txt")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "checkout", "-b", "task")
    (tmp_path / "value.txt").write_text("first\n")
    git(tmp_path, "commit", "-am", "first")
    first_head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "main")
    git(tmp_path, "merge", "--no-ff", "task", "-m", "land first")
    git(tmp_path, "checkout", "task")
    (tmp_path / "value.txt").write_text("second\n")
    git(tmp_path, "commit", "-am", "second")
    git(tmp_path, "checkout", "main")

    landing = GitLandingCollector(tmp_path, project_id="project-1").collect(
        LandingRequest("task", "main", first_head)
    )

    assert landing.state is LandingState.LANDED
    assert landing.revision == first_head


def test_integrated_record_uses_landing_fact_to_schedule_terminal_stage(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "value.txt").write_text("base\n")
    git(tmp_path, "add", "value.txt")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "checkout", "-b", "TASK-A")
    (tmp_path / "value.txt").write_text("task\n")
    git(tmp_path, "commit", "-am", "task")
    head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "main")
    git(tmp_path, "merge", "--no-ff", "TASK-A", "-m", "integrate")
    task = issue("TASK-A", state="integrated", head=head)
    task.integration = replace(task.integration, integrated_sha=head)
    tracker = Tracker([task])
    store = WorkflowJobStore(str(tmp_path / "landing.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(
            tracker, GitLandingCollector(tmp_path, project_id="project-1")
        ),
        store=store,
    )

    batch, scheduled = controller.reconcile([task])

    decision = batch.tasks[0].decision
    assert decision.reason_code == "integration.landing_proven"
    assert decision.recommended_status == "In Validation"
    assert decision.durable_jobs == ("integration_terminal_stage",)
    assert scheduled.jobs_created == 1
    store.close()


def test_unproven_integrated_record_is_informational_and_retry_scheduled(tmp_path):
    task = issue("TASK-A", state="integrated", head="a" * 40)
    store = WorkflowJobStore(str(tmp_path / "unproven.sqlite3"))
    controller = IntegrationWorkflowController(
        collector=collector(Tracker([task])), store=store
    )

    batch, scheduled = controller.reconcile([task])

    decision = batch.tasks[0].decision
    assert decision.reason_code == "integration.landing_unproven"
    assert decision.alert_level.value == "info"
    assert not decision.action_required
    assert decision.durable_jobs == ("integration_landing_refresh",)
    assert scheduled.jobs_created == 1
    store.close()


class ResultBackend:
    def __init__(self, result):
        self.result = result

    def revalidate(self, context):
        return RevalidationResult(context.job.generation)

    def observe_landing(self, context):
        return None

    def integrate(self, context):
        return self.result

    def build_transition(self, context, verification):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "disposition", "state"),
    [
        (
            "worktree_recovery",
            WorkflowRunDisposition.RETRY_SCHEDULED,
            WorkflowJobState.RETRY_WAIT,
        ),
        (
            "dirty_worktree",
            WorkflowRunDisposition.ACTION_REQUIRED,
            WorkflowJobState.EXHAUSTED,
        ),
    ],
)
async def test_recovery_is_retryable_but_unsafe_mutation_is_actionable(
    tmp_path, status, disposition, state
):
    store = WorkflowJobStore(str(tmp_path / f"{status}.sqlite3"))
    store.enqueue(
        WorkflowJobSpec(
            "project-1",
            "TASK-1",
            "generation-1",
            "integration_attempt",
            f"TASK-1:{status}",
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            "integration_attempt": IntegrationWorkflowHandler(
                ResultBackend(IntegrationExecutionResult(status, status))
            )
        },
        transition_services={},
        worker_id="integrator",
        lease_seconds=30,
        heartbeat_seconds=10,
    )

    result = await worker.run_once()

    assert result.disposition is disposition
    assert store.list_jobs()[0].state is state
    store.close()
