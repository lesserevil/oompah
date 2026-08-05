"""Epic rollup facts, target-relative decisions, and durable job coverage."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from oompah.epic_workflow import (
    EpicAction,
    EpicFactCollector,
    EpicWorkflowController,
    EpicWorkflowHandler,
    ProductionEpicWorkflowBackend,
    epic_branch,
)
from oompah.models import Issue
from oompah.orchestrator import (
    EpicTargetResolutionError as OrchestratorEpicTargetResolutionError,
    Orchestrator,
)
from oompah.statuses import DONE, IN_PROGRESS, OPEN
from oompah.workflow_contract import TaskDisposition
from oompah.statuses import ARCHIVED, IN_REVIEW, MERGED
from oompah.task_transition_service import (
    TransitionDisposition,
    TransitionOutcome,
)
from oompah.work_decision import evaluate_task
from oompah.workflow_facts import (
    FactState,
    GitLandingCollector,
    LandingFact,
    LandingRequest,
    LandingState,
)
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobState, WorkflowJobStore
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionSuperseded,
    WorkflowRunDisposition,
)


class Tracker:
    def __init__(self, issues: list[Issue]) -> None:
        self.issues = {item.identifier: item for item in issues}

    def fetch_issue_detail(self, identifier: str):
        return self.issues.get(identifier)

    def fetch_children(self, identifier: str):
        return [item for item in self.issues.values() if item.parent_id == identifier]


def issue(
    identifier: str,
    *,
    state: str,
    issue_type: str = "task",
    parent_id: str | None = None,
    work_branch: str | None = None,
    project_id: str = "project-1",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="epic workflow fixture",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id=project_id,
        work_branch=work_branch,
    )


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Epic Workflow",
            "GIT_AUTHOR_EMAIL": "epic@example.invalid",
            "GIT_COMMITTER_NAME": "Epic Workflow",
            "GIT_COMMITTER_EMAIL": "epic@example.invalid",
        },
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def make_git_fixture(repo: Path) -> None:
    git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-m", "base")
    git(repo, "checkout", "-b", "leaf")
    (repo / "leaf.txt").write_text("leaf\n")
    git(repo, "add", "leaf.txt")
    git(repo, "commit", "-m", "leaf")
    git(repo, "checkout", "main")
    git(repo, "checkout", "-b", "epic-MID")
    git(repo, "cherry-pick", "leaf")
    git(repo, "checkout", "main")
    git(repo, "checkout", "-b", "epic-TOP")
    git(repo, "cherry-pick", "epic-MID")
    git(repo, "checkout", "main")


def test_epic_branch_uses_the_project_store_sanitization_contract():
    assert epic_branch(" TEAM/EPIC 1 ") == "epic-TEAM_EPIC_1"
    assert epic_branch("foo..bar") == "epic-foo_bar"
    assert epic_branch("foo.lock") == "epic-foo.lock_"


def test_nested_target_rejects_a_parent_from_another_project():
    nested = issue(
        "NESTED", state=IN_PROGRESS, issue_type="epic", parent_id="FOREIGN"
    )
    foreign = issue(
        "FOREIGN", state=IN_PROGRESS, issue_type="epic", project_id="project-2"
    )

    facts = EpicFactCollector(
        project_id="project-1", tracker=Tracker([nested, foreign])
    ).collect("NESTED")

    containment = facts.fact("containment")
    assert containment.state is FactState.ERROR
    assert containment.error_code == "containment_epictargetresolutionerror"


def test_nested_rollups_use_immediate_landing_without_parent_status_cycle(tmp_path):
    make_git_fixture(tmp_path)
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    mid = issue("MID", state=OPEN, issue_type="epic", parent_id="TOP")
    leaf = issue("LEAF", state=DONE, parent_id="MID", work_branch="leaf")
    tracker = Tracker([top, mid, leaf])
    collector = EpicFactCollector(
        project_id="project-1",
        tracker=tracker,
        repo_path=str(tmp_path),
    )
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(collector=collector, store=store)

    batch, scheduled = controller.reconcile([top, mid])

    decisions = {item.task.identifier: item.decision for item in batch.tasks}
    assert decisions["MID"].disposition is TaskDisposition.RUNNABLE
    assert decisions["MID"].reason_code == "terminal.immediate_target_landing_proven"
    assert decisions["MID"].durable_jobs == ("epic_auto_close",)
    # MID is intentionally still Open. TOP is eligible from MID's landing on
    # epic-TOP, not from a status that TOP would have derived from MID.
    assert decisions["TOP"].disposition is TaskDisposition.RUNNABLE
    assert decisions["TOP"].durable_jobs == ("rollup_review_creation",)
    assert scheduled.jobs_created == 2
    assert all(
        job.state is WorkflowJobState.QUEUED for job in store.list_jobs(limit=10)
    )
    store.close()


def test_bounded_controller_rotates_across_all_eligible_epics(tmp_path):
    tasks = [
        issue(f"EPIC-{suffix}", state=OPEN, issue_type="epic") for suffix in "ABC"
    ]
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1",
            tracker=Tracker(tasks),
        ),
        store=store,
        decision_limit=1,
    )

    observed = {
        controller.evaluate(tasks, persist_evidence=False).tasks[0].task.identifier
        for _ in range(3)
    }

    assert observed == {"EPIC-A", "EPIC-B", "EPIC-C"}
    store.close()


def test_shadow_epic_evaluation_does_not_persist_landing_evidence(tmp_path):
    make_git_fixture(tmp_path)
    epic = issue("TOP", state=OPEN, issue_type="epic")
    child = issue("LEAF", state=DONE, parent_id="TOP", work_branch="leaf")
    tracker = Tracker([epic, child])
    collector = EpicFactCollector(
        project_id="project-1",
        tracker=tracker,
        repo_path=str(tmp_path),
    )
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(collector=collector, store=store)

    batch = controller.evaluate([epic], persist_evidence=False)

    assert batch.tasks
    assert store.landing_facts(project_id="project-1", task_id="TOP") == ()
    assert store.list_jobs() == ()
    store.close()


def test_explicit_epic_action_supersedes_only_its_older_action_generation(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=SimpleNamespace(project_id="project-1"),
        store=store,
    )

    old = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.READINESS,
        generation="event-1",
        payload={"authority": "one"},
    )
    independent = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.TARGET_RESOLUTION,
        generation="target-1",
        payload={"authority": "one"},
    )
    new = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.READINESS,
        generation="event-2",
        payload={"authority": "two"},
    )

    assert store.get(old.job_id).state is WorkflowJobState.SUPERSEDED
    assert store.get(independent.job_id).state is WorkflowJobState.QUEUED
    assert store.get(new.job_id).state is WorkflowJobState.QUEUED
    assert old.scheduling_lane == new.scheduling_lane
    assert independent.scheduling_lane != new.scheduling_lane
    store.close()


class RecordingEpicEffects:
    def __init__(self) -> None:
        self.receipt = None
        self.apply_calls = 0

    def inspect_epic_effect(self, action, epic, facts, payload):
        return self.receipt

    def apply_epic_effect(
        self,
        action,
        epic,
        facts,
        payload,
        *,
        idempotency_key,
        originating_job,
        evidence_generation,
    ):
        self.apply_calls += 1
        self.receipt = {
            "effect": action.value,
            "review_id": "42",
            "source_branch": f"epic-{epic.identifier}",
            "target_branch": "main",
            "source_head": "a" * 40,
            "idempotency_key": idempotency_key,
        }
        return self.receipt

    def verify_epic_effect(self, action, epic, facts, payload, receipt):
        if self.receipt is None:
            return None
        if receipt.get("source_head") != self.receipt["source_head"]:
            return None
        return self.receipt


class RecordingTransitionService:
    def __init__(self) -> None:
        self.intents = []

    async def execute(self, intent):
        self.intents.append(intent)
        return TransitionOutcome(
            transition_id="transition-1",
            project_id=intent.project_id,
            task_id=intent.task_id,
            disposition=TransitionDisposition.APPLIED,
            reason_code="transition.applied",
            observed_status=intent.requested_status,
            observed_version=intent.expected_version,
            requested_status=intent.requested_status,
            applied_status=intent.requested_status,
        )


def production_handler(controller, tracker, effects):
    return EpicWorkflowHandler(
        ProductionEpicWorkflowBackend(
            controller=controller,
            tracker=tracker,
            effects=effects,
        )
    )


@pytest.mark.asyncio
async def test_production_review_handler_uses_exact_receipt_and_transition(tmp_path):
    make_git_fixture(tmp_path)
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    leaf = issue("LEAF", state=DONE, parent_id="TOP", work_branch="leaf")
    tracker = Tracker([top, leaf])
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
        ),
        store=store,
    )
    _batch, scheduled = controller.reconcile([top])
    assert scheduled.jobs_created == 1
    job = store.list_jobs()[0]
    assert job.action == EpicAction.ROLLUP_REVIEW_CREATION.value
    effects = RecordingEpicEffects()
    transitions = RecordingTransitionService()
    worker = DurableWorkflowWorker(
        store=store,
        handlers={job.action: production_handler(controller, tracker, effects)},
        transition_services={"project-1": transitions},
        worker_id="epic-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert effects.apply_calls == 1
    assert len(transitions.intents) == 1
    intent = transitions.intents[0]
    assert intent.requested_status == IN_REVIEW
    assert intent.exact_head == "a" * 40
    completed = store.get(job.job_id)
    assert completed.checkpoint["effect"]["review_id"] == "42"
    assert completed.checkpoint["verification"]["source_head"] == "a" * 40
    assert store.landing_facts(project_id="project-1", task_id="TOP")
    store.close()


@pytest.mark.asyncio
async def test_auto_close_uses_persisted_review_head_as_terminal_cas(tmp_path):
    make_git_fixture(tmp_path)
    git(tmp_path, "checkout", "main")
    git(tmp_path, "merge", "--ff-only", "epic-TOP")
    exact_head = git(tmp_path, "rev-parse", "epic-TOP")
    top = issue("TOP", state=IN_REVIEW, issue_type="epic")
    top.review_head = exact_head
    leaf = issue("LEAF", state=DONE, parent_id="TOP", work_branch="leaf")
    tracker = Tracker([top, leaf])
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
        ),
        store=store,
    )
    # Persist the exact child landing before pruning the shared epic source.
    # The review head can recover the epic's own landing, but it must not hide
    # an unknown current child obligation.
    controller.evaluate([top])
    git(tmp_path, "branch", "-D", "epic-TOP")
    _batch, scheduled = controller.reconcile([top])
    assert scheduled.jobs_created == 1
    job = store.list_jobs()[0]
    assert job.action == EpicAction.AUTO_CLOSE.value
    transitions = RecordingTransitionService()
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            job.action: production_handler(controller, tracker, RecordingEpicEffects())
        },
        transition_services={"project-1": transitions},
        worker_id="epic-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert len(transitions.intents) == 1
    assert transitions.intents[0].requested_status == "Merged"
    assert transitions.intents[0].exact_head == exact_head
    store.close()


@pytest.mark.asyncio
async def test_auto_close_rejects_stale_review_head_until_exact_landing_is_synced(
    tmp_path,
):
    make_git_fixture(tmp_path)
    git(tmp_path, "checkout", "main")
    git(tmp_path, "merge", "--ff-only", "epic-TOP")
    landing_head = git(tmp_path, "rev-parse", "epic-TOP")
    top = issue("TOP", state=IN_REVIEW, issue_type="epic")
    top.review_head = "f" * 40
    leaf = issue("LEAF", state=DONE, parent_id="TOP", work_branch="leaf")
    tracker = Tracker([top, leaf])
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
        ),
        store=store,
    )
    stale = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.AUTO_CLOSE,
        generation="auto-close-stale",
        expected_head_sha=top.review_head,
    )
    transitions = RecordingTransitionService()
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            EpicAction.AUTO_CLOSE.value: production_handler(
                controller, tracker, RecordingEpicEffects()
            )
        },
        transition_services={"project-1": transitions},
        worker_id="epic-worker",
    )

    stale_result = await worker.run_once()

    assert stale_result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert store.get(stale.job_id).state is WorkflowJobState.SUPERSEDED
    assert transitions.intents == []

    top.review_head = landing_head
    current = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.AUTO_CLOSE,
        generation="auto-close-current",
        expected_head_sha=landing_head,
    )
    current_result = await worker.run_once()

    assert current_result.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(current.job_id).state is WorkflowJobState.COMPLETED
    assert len(transitions.intents) == 1
    assert transitions.intents[0].requested_status == MERGED
    assert transitions.intents[0].exact_head == landing_head
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("child_change", ["added", "reopened"])
async def test_queued_auto_close_rechecks_current_children(tmp_path, child_change):
    make_git_fixture(tmp_path)
    git(tmp_path, "checkout", "main")
    git(tmp_path, "merge", "--ff-only", "epic-TOP")
    landing_head = git(tmp_path, "rev-parse", "epic-TOP")
    top = issue("TOP", state=IN_REVIEW, issue_type="epic")
    top.review_head = landing_head
    leaf = issue("LEAF", state=DONE, parent_id="TOP", work_branch="leaf")
    tracker = Tracker([top, leaf])
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
        ),
        store=store,
    )
    initial = controller.evaluate([top]).tasks[0].decision
    assert initial.durable_jobs == (EpicAction.AUTO_CLOSE.value,)
    queued = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.AUTO_CLOSE,
        generation=f"auto-close-before-child-{child_change}",
        expected_head_sha=landing_head,
    )
    if child_change == "added":
        late = issue(
            "LATE", state=OPEN, parent_id="TOP", work_branch="late-child"
        )
        tracker.issues[late.identifier] = late
    else:
        leaf.state = OPEN

    transitions = RecordingTransitionService()
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            EpicAction.AUTO_CLOSE.value: production_handler(
                controller, tracker, RecordingEpicEffects()
            )
        },
        transition_services={"project-1": transitions},
        worker_id="epic-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert store.get(queued.job_id).state is WorkflowJobState.SUPERSEDED
    assert transitions.intents == []
    store.close()


@pytest.mark.asyncio
async def test_external_apply_and_verify_recheck_fresh_action_authority():
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    facts = MagicMock()
    facts.fact.return_value = SimpleNamespace(
        state=FactState.KNOWN,
        value={"epic_branch": "epic-TOP", "target_branch": "main"},
    )
    facts.landings = ()
    decision = SimpleNamespace(
        durable_jobs=(),
        evidence_revision="facts-no-longer-authorized",
        reason_code="rollup.waiting_children",
    )
    effects = MagicMock()
    controller = MagicMock()
    controller.collector.project_id = "project-1"
    backend = ProductionEpicWorkflowBackend(
        controller=controller,
        tracker=MagicMock(),
        effects=effects,
    )
    backend._fresh_snapshot = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(epic=top, facts=facts, decision=decision)
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            action=EpicAction.ROLLUP_REVIEW_CREATION.value,
            payload={},
            generation="review-generation-1",
        ),
        idempotency_key="review-effect-1",
    )

    with pytest.raises(WorkflowActionSuperseded):
        await backend.apply(context)
    with pytest.raises(WorkflowActionSuperseded):
        await backend.verify(context, EffectResult({"source_head": "a" * 40}))

    effects.apply_epic_effect.assert_not_called()
    effects.verify_epic_effect.assert_not_called()


def test_merged_cleanup_is_not_current_without_exact_own_landing():
    top = issue("TOP", state=MERGED, issue_type="epic")
    facts = MagicMock()
    facts.fact.return_value = SimpleNamespace(
        state=FactState.KNOWN,
        value={
            "epic_branch": "epic-TOP",
            "target_branch": "main",
            "children": [],
        },
    )
    facts.landings = ()
    snapshot = SimpleNamespace(
        epic=top,
        facts=facts,
        # Even a stale decision that requested cleanup cannot override the
        # mutation-time landing fence.
        decision=SimpleNamespace(durable_jobs=(EpicAction.CLEANUP.value,)),
    )

    assert not ProductionEpicWorkflowBackend._is_action_current(
        EpicAction.CLEANUP,
        snapshot,
        {},
    )
    top.state = IN_PROGRESS
    facts.landings = (
        LandingFact(
            "epic-TOP",
            "main",
            "a" * 40,
            {"kind": "git_ancestry", "source_sha": "a" * 40},
            "2026-08-05T00:00:00+00:00",
            "project-1",
            state=LandingState.LANDED,
            durable=True,
        ),
    )
    assert not ProductionEpicWorkflowBackend._is_action_current(
        EpicAction.CLEANUP,
        snapshot,
        {},
    )
    top.state = MERGED
    assert ProductionEpicWorkflowBackend._is_action_current(
        EpicAction.CLEANUP,
        snapshot,
        {},
    )


def test_rebase_action_rejects_stale_target_even_when_repair_remains_runnable():
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic", parent_id="NEW")
    facts = MagicMock()
    facts.fact.return_value = SimpleNamespace(
        state=FactState.KNOWN,
        value={
            "epic_branch": "epic-TOP",
            "target_branch": "epic-NEW",
            "children": [],
        },
    )
    snapshot = SimpleNamespace(
        epic=top,
        facts=facts,
        decision=SimpleNamespace(
            durable_jobs=(EpicAction.REBASE_REPAIR.value,),
        ),
    )

    assert not ProductionEpicWorkflowBackend._is_action_current(
        EpicAction.REBASE_REPAIR,
        snapshot,
        {"target_branch": "epic-OLD"},
    )
    assert ProductionEpicWorkflowBackend._is_action_current(
        EpicAction.REBASE_REPAIR,
        snapshot,
        {"target_branch": "epic-NEW"},
    )
    snapshot.decision.durable_jobs = ()
    assert not ProductionEpicWorkflowBackend._is_action_current(
        EpicAction.REBASE_REPAIR,
        snapshot,
        {"target_branch": "epic-NEW"},
    )


@pytest.mark.asyncio
async def test_review_effect_restart_replays_verify_without_duplicate_create(tmp_path):
    make_git_fixture(tmp_path)
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    leaf = issue("LEAF", state=DONE, parent_id="TOP", work_branch="leaf")
    tracker = Tracker([top, leaf])
    store_path = tmp_path / "jobs.sqlite3"
    store = WorkflowJobStore(str(store_path))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
        ),
        store=store,
    )
    controller.reconcile([top])
    effects = RecordingEpicEffects()
    crashed = False

    def crash_after_receipt(phase, _job):
        nonlocal crashed
        if phase == "effect_returned" and not crashed:
            crashed = True
            raise RuntimeError("simulated process death after durable effect receipt")

    first = DurableWorkflowWorker(
        store=store,
        handlers={
            EpicAction.ROLLUP_REVIEW_CREATION.value: production_handler(
                controller, tracker, effects
            )
        },
        transition_services={"project-1": RecordingTransitionService()},
        worker_id="epic-worker-1",
        retry_delay_seconds=0,
        phase_observer=crash_after_receipt,
    )
    first_result = await first.run_once()
    assert first_result.disposition is WorkflowRunDisposition.RETRY_SCHEDULED
    assert effects.apply_calls == 1
    store.close()

    reopened = WorkflowJobStore(str(store_path))
    restarted = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
        ),
        store=reopened,
    )
    second = DurableWorkflowWorker(
        store=reopened,
        handlers={
            EpicAction.ROLLUP_REVIEW_CREATION.value: production_handler(
                restarted, tracker, effects
            )
        },
        transition_services={"project-1": RecordingTransitionService()},
        worker_id="epic-worker-2",
        retry_delay_seconds=0,
    )

    second_result = await second.run_once()

    assert second_result.disposition is WorkflowRunDisposition.COMPLETED
    assert effects.apply_calls == 1
    reopened.close()


@pytest.mark.asyncio
async def test_rebase_restart_accepts_helper_created_before_receipt_checkpoint():
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    facts = MagicMock()
    facts.fact.return_value = SimpleNamespace(
        state=FactState.KNOWN,
        value={"epic_branch": "epic-TOP", "target_branch": "main"},
    )
    decision = SimpleNamespace(
        durable_jobs=(),
        evidence_revision="after-helper",
        reason_code="rollup.waiting_children",
    )
    effects = MagicMock()
    effects.inspect_epic_effect.return_value = {
        "helper_id": "REBASE-1",
        "source_branch": "epic-TOP",
        "target_branch": "main",
    }
    controller = MagicMock()
    controller.collector.project_id = "project-1"
    backend = ProductionEpicWorkflowBackend(
        controller=controller,
        tracker=MagicMock(),
        effects=effects,
    )
    backend._fresh_snapshot = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(epic=top, facts=facts, decision=decision)
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            action=EpicAction.REBASE_REPAIR.value,
            payload={
                "target_branch": "main",
                "evidence_revision": "before-helper",
            },
            checkpoint={},
            generation="rebase-generation-1",
        )
    )

    result = await backend.revalidate(context)

    assert result.current is True
    effects.inspect_epic_effect.assert_called_once()


@pytest.mark.asyncio
async def test_rebase_restart_verifies_durable_receipt_after_helper_changes_decision():
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    facts = MagicMock()
    facts.fact.return_value = SimpleNamespace(
        state=FactState.KNOWN,
        value={"epic_branch": "epic-TOP", "target_branch": "main"},
    )
    decision = SimpleNamespace(
        durable_jobs=(),
        evidence_revision="after-helper",
        reason_code="rollup.waiting_children",
    )
    controller = MagicMock()
    controller.collector.project_id = "project-1"
    effects = MagicMock()
    effects.verify_epic_effect.return_value = {
        "helper_id": "REBASE-1",
        "source_branch": "epic-TOP",
        "target_branch": "main",
    }
    backend = ProductionEpicWorkflowBackend(
        controller=controller,
        tracker=MagicMock(),
        effects=effects,
    )
    backend._fresh_snapshot = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(epic=top, facts=facts, decision=decision)
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            action=EpicAction.REBASE_REPAIR.value,
            payload={"target_branch": "main", "evidence_revision": "before-helper"},
            checkpoint={"effect": {"helper_id": "REBASE-1"}},
            generation="rebase-generation-1",
        )
    )

    result = await backend.revalidate(context)
    verification = await backend.verify(
        context,
        EffectResult({"helper_id": "REBASE-1"}),
    )

    assert result.current is True
    assert verification.verified is True
    effects.verify_epic_effect.assert_called_once()


@pytest.mark.asyncio
async def test_rebase_restart_resumes_partial_helper_bookkeeping_repair():
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    facts = MagicMock()
    facts.fact.return_value = SimpleNamespace(
        state=FactState.KNOWN,
        value={"epic_branch": "epic-TOP", "target_branch": "main"},
    )
    decision = SimpleNamespace(
        durable_jobs=(),
        evidence_revision="after-helper",
        reason_code="rollup.waiting_children",
    )
    effects = MagicMock()
    effects.inspect_epic_effect.return_value = None
    effects.recoverable_epic_effect.return_value = True
    controller = MagicMock()
    controller.collector.project_id = "project-1"
    backend = ProductionEpicWorkflowBackend(
        controller=controller,
        tracker=MagicMock(),
        effects=effects,
    )
    backend._fresh_snapshot = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(epic=top, facts=facts, decision=decision)
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            action=EpicAction.REBASE_REPAIR.value,
            payload={
                "target_branch": "main",
                "evidence_revision": "before-helper",
            },
            checkpoint={},
            generation="rebase-generation-1",
        )
    )

    result = await backend.revalidate(context)

    assert result.current is True
    effects.recoverable_epic_effect.assert_called_once()


@pytest.mark.asyncio
async def test_epic_handler_executes_one_exact_task_scoped_effect(tmp_path):
    calls: list[tuple[str, str]] = []

    class Backend:
        def revalidate(self, context):
            calls.append(("revalidate", context.job.task_id))
            return RevalidationResult(context.job.generation)

        def inspect(self, context):
            calls.append(("inspect", context.job.task_id))
            return EffectObservation(False)

        def apply(self, context):
            calls.append(("apply", context.job.task_id))
            return EffectResult({"task_id": context.job.task_id})

        def verify(self, context, effect):
            calls.append(("verify", str(effect.receipt["task_id"])))
            return VerificationResult(True, effect.receipt)

        def build_transition(self, context, verification):
            calls.append(("transition", context.job.task_id))
            return None

    store = WorkflowJobStore(str(tmp_path / "epic-handler.sqlite3"))
    job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="EPIC-1",
            generation="facts-1",
            action="epic_readiness",
            idempotency_key="EPIC-1:readiness:facts-1",
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers={"epic_readiness": EpicWorkflowHandler(Backend())},
        transition_services={},
        worker_id="epic-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    assert store.get(job.job_id).state is WorkflowJobState.COMPLETED
    assert calls == [
        ("revalidate", "EPIC-1"),
        ("inspect", "EPIC-1"),
        ("apply", "EPIC-1"),
        ("verify", "EPIC-1"),
        ("transition", "EPIC-1"),
    ]
    store.close()


def test_each_epic_decision_contains_only_its_direct_children(tmp_path):
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    mid = issue("MID", state=IN_PROGRESS, issue_type="epic", parent_id="TOP")
    leaf = issue("LEAF", state=OPEN, parent_id="MID", work_branch="leaf")
    tracker = Tracker([top, mid, leaf])
    collector = EpicFactCollector(project_id="project-1", tracker=tracker)

    top_facts = collector.collect("TOP")
    mid_facts = collector.collect("MID")

    top_children = top_facts.fact("containment").value["children"]
    mid_children = mid_facts.fact("containment").value["children"]
    assert [item["identifier"] for item in top_children] == ["MID"]
    assert [item["identifier"] for item in mid_children] == ["LEAF"]


def test_archived_direct_child_has_no_invented_landing_obligation(tmp_path):
    make_git_fixture(tmp_path)
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    retired = issue("OLD", state="Archived", parent_id="TOP")
    tracker = Tracker([top, retired])
    facts = EpicFactCollector(
        project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
    ).collect("TOP")

    decision = evaluate_task(top, facts)

    assert decision.disposition is TaskDisposition.RUNNABLE
    assert decision.reason_code == "rollup.children_complete"


def test_own_landing_does_not_hide_a_new_open_child(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-m", "base")
    git(repo, "branch", "epic-TOP")
    top = issue("TOP", state=IN_REVIEW, issue_type="epic")
    top.review_head = git(repo, "rev-parse", "epic-TOP")
    reopened = issue(
        "REOPENED",
        state=OPEN,
        parent_id="TOP",
        work_branch="reopened-child",
    )
    facts = EpicFactCollector(
        project_id="project-1",
        tracker=Tracker([top, reopened]),
        repo_path=str(repo),
    ).collect("TOP")

    own = next(item for item in facts.landings if item.source == "epic-TOP")
    decision = evaluate_task(top, facts)

    assert own.state is LandingState.LANDED
    assert decision.disposition is TaskDisposition.BLOCKED
    assert decision.reason_code == "rollup.waiting_children"
    assert decision.durable_jobs == ("child_landing_verification",)


@pytest.mark.asyncio
async def test_archived_cleanup_is_superseded_when_live_tip_outgrows_queued_head(
    tmp_path,
):
    make_git_fixture(tmp_path)
    queued_head = git(tmp_path, "rev-parse", "main")
    live_head = git(tmp_path, "rev-parse", "epic-TOP")
    assert live_head != queued_head
    top = issue("TOP", state=ARCHIVED, issue_type="epic")
    top.review_head = queued_head
    tracker = Tracker([top])
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
        ),
        store=store,
    )
    job = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.CLEANUP,
        generation="archived-cleanup-at-queued-head",
        expected_head_sha=queued_head,
    )
    effects = RecordingEpicEffects()
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            EpicAction.CLEANUP.value: production_handler(
                controller, tracker, effects
            )
        },
        transition_services={"project-1": RecordingTransitionService()},
        worker_id="epic-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert store.get(job.job_id).state is WorkflowJobState.SUPERSEDED
    assert effects.apply_calls == 0
    store.close()


def test_orchestrator_consumes_the_same_epic_snapshot_that_it_schedules(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-m", "base")
    git(repo, "checkout", "-b", "child")
    (repo / "child.txt").write_text("child\n")
    git(repo, "add", "child.txt")
    git(repo, "commit", "-m", "child")
    git(repo, "checkout", "main")
    git(repo, "checkout", "-b", "epic-TOP")
    git(repo, "cherry-pick", "child")

    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    ready = issue("READY", state=DONE, parent_id="TOP", work_branch="child")
    reopened = issue("REOPENED", state=OPEN, parent_id="TOP", work_branch="new")

    class FlappingTracker(Tracker):
        def __init__(self):
            super().__init__([top, ready, reopened])
            self.root_reads = 0

        def fetch_children(self, identifier: str):
            if identifier == "TOP":
                self.root_reads += 1
                return [ready] if self.root_reads == 1 else [ready, reopened]
            return super().fetch_children(identifier)

    tracker = FlappingTracker()
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    project = SimpleNamespace(
        id="project-1", repo_path=str(repo), default_branch="main", branch="main"
    )
    fake_orchestrator = SimpleNamespace(
        project_store=SimpleNamespace(get=lambda _project_id: project),
        workflow_job_store=store,
        _tracker_for_issue=lambda _issue: tracker,
    )

    decision, _facts = Orchestrator._shared_epic_workflow_decision(
        fake_orchestrator, top
    )
    cursor = store.schedule_cursor(project_id="project-1", task_id="TOP")

    assert tracker.root_reads == 1
    assert decision.disposition is TaskDisposition.RUNNABLE
    assert cursor is not None
    assert cursor.decision_revision == decision.decision_revision
    store.close()


def test_enforce_auto_close_waits_for_the_durable_revalidated_job(tmp_path):
    make_git_fixture(tmp_path)
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    mid = issue("MID", state=OPEN, issue_type="epic", parent_id="TOP")
    leaf = issue("LEAF", state=DONE, parent_id="MID", work_branch="leaf")
    tracker = Tracker([top, mid, leaf])
    facts = EpicFactCollector(
        project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
    ).collect("MID")
    decision = evaluate_task(mid, facts)
    request_terminal = MagicMock()
    fake_orchestrator = SimpleNamespace(
        config=SimpleNamespace(
            workflow_engine_mode="enforce",
            tracker_terminal_states=("Merged", "Archived"),
        ),
        _shared_epic_workflow_decision=lambda _epic: (decision, facts),
        _shared_epic_landing_proven=Orchestrator._shared_epic_landing_proven,
        _request_epic_terminal_rollup=request_terminal,
        _clear_stuck_epic_alert=MagicMock(),
    )

    closed = Orchestrator._epic_auto_close_check(fake_orchestrator, mid)

    assert decision.durable_jobs == ("epic_auto_close",)
    assert closed is False
    request_terminal.assert_not_called()


def test_enforce_target_resolution_never_falls_back_from_shared_fact_failure():
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    project = SimpleNamespace(default_branch="main", branch="main")
    fake_orchestrator = SimpleNamespace(
        config=SimpleNamespace(workflow_engine_mode="enforce"),
        _shared_epic_workflow_decision=MagicMock(
            side_effect=RuntimeError("shared evidence unavailable")
        ),
        _record_epic_target_resolution_failure=MagicMock(),
        _clear_epic_target_resolution_alert=MagicMock(),
    )

    with pytest.raises(
        OrchestratorEpicTargetResolutionError,
        match="shared target facts are unavailable",
    ):
        Orchestrator._resolve_epic_target_branch(fake_orchestrator, top, project)
    fake_orchestrator._record_epic_target_resolution_failure.assert_called_once()


def test_enforce_target_resolution_clears_a_prior_failure_alert():
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    facts = EpicFactCollector(
        project_id="project-1", tracker=Tracker([top])
    ).collect("TOP")
    project = SimpleNamespace(default_branch="main", branch="main")
    fake_orchestrator = SimpleNamespace(
        config=SimpleNamespace(workflow_engine_mode="enforce"),
        _shared_epic_workflow_decision=MagicMock(return_value=(None, facts)),
        _record_epic_target_resolution_failure=MagicMock(),
        _clear_epic_target_resolution_alert=MagicMock(),
    )

    target = Orchestrator._resolve_epic_target_branch(
        fake_orchestrator, top, project
    )

    assert target == "main"
    fake_orchestrator._clear_epic_target_resolution_alert.assert_called_once_with(top)
    fake_orchestrator._record_epic_target_resolution_failure.assert_not_called()


def test_target_resolution_alerts_are_isolated_by_project():
    project_one = issue(
        "TOP", state=IN_PROGRESS, issue_type="epic", project_id="project-1"
    )
    project_two = issue(
        "TOP", state=IN_PROGRESS, issue_type="epic", project_id="project-2"
    )
    fake_orchestrator = Orchestrator.__new__(Orchestrator)
    fake_orchestrator._alerts = []
    error = OrchestratorEpicTargetResolutionError("TOP", "PARENT", "is unavailable")

    Orchestrator._record_epic_target_resolution_failure(
        fake_orchestrator, project_one, error
    )
    Orchestrator._record_epic_target_resolution_failure(
        fake_orchestrator, project_two, error
    )

    assert {alert["source"] for alert in fake_orchestrator._alerts} == {
        "epic_target_unresolved:project-1:TOP",
        "epic_target_unresolved:project-2:TOP",
    }
    Orchestrator._clear_epic_target_resolution_alert(fake_orchestrator, project_one)
    assert [alert["source"] for alert in fake_orchestrator._alerts] == [
        "epic_target_unresolved:project-2:TOP"
    ]


def test_deleted_source_ref_preserves_durable_landing_fact(tmp_path):
    make_git_fixture(tmp_path)
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    mid = issue("MID", state=IN_PROGRESS, issue_type="epic", parent_id="TOP")
    leaf = issue("LEAF", state=DONE, parent_id="MID", work_branch="leaf")
    tracker = Tracker([top, mid, leaf])
    first = EpicFactCollector(
        project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
    ).collect("MID")
    durable = next(
        item
        for item in first.landings
        if item.source == "leaf" and item.target == "epic-MID"
    )
    assert durable.state is LandingState.LANDED
    assert durable.durable

    git(tmp_path, "branch", "-D", "leaf")
    second = EpicFactCollector(
        project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
    ).collect(
        "MID",
        prior_landings={(durable.source, durable.target): durable},
    )
    preserved = next(
        item
        for item in second.landings
        if item.source == "leaf" and item.target == "epic-MID"
    )
    assert preserved.state is LandingState.LANDED
    assert preserved.durable
    assert preserved.evidence_revision == durable.evidence_revision


def test_advanced_source_ref_invalidates_older_durable_landing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-m", "base")
    git(repo, "checkout", "-b", "source")
    (repo / "first.txt").write_text("first\n")
    git(repo, "add", "first.txt")
    git(repo, "commit", "-m", "first")
    git(repo, "checkout", "main")
    git(repo, "checkout", "-b", "target")
    git(repo, "cherry-pick", "source")
    collector = GitLandingCollector(repo, project_id="project-1")
    prior = collector.collect(LandingRequest("source", "target"))
    assert prior.state is LandingState.LANDED

    git(repo, "checkout", "source")
    (repo / "second.txt").write_text("second\n")
    git(repo, "add", "second.txt")
    git(repo, "commit", "-m", "second")
    refreshed = collector.collect(LandingRequest("source", "target", prior=prior))
    exact_previous = collector.collect(
        LandingRequest("source", "target", prior.revision, prior=prior)
    )
    live_previous = collector.collect(
        LandingRequest(
            "source",
            "target",
            prior.revision,
            prior=prior,
            prefer_live_source=True,
        )
    )

    assert refreshed.state is LandingState.NOT_LANDED
    assert refreshed.revision != prior.revision
    # Exact child revisions remain stable when a shared container advances.
    assert exact_previous.state is LandingState.LANDED
    assert exact_previous.revision == prior.revision
    # An epic's own persisted review head is fallback evidence only after
    # pruning. While its source ref is live, the advanced tip supersedes the
    # older reviewed generation and prevents auto-close/cleanup.
    assert live_previous.state is LandingState.NOT_LANDED
    assert live_previous.revision == refreshed.revision


def test_shared_container_ref_can_advance_past_exact_child_revision(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "first.txt").write_text("first\n")
    git(repo, "add", "first.txt")
    git(repo, "commit", "-m", "first")
    first = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-b", "epic-TOP")
    (repo / "second.txt").write_text("second\n")
    git(repo, "add", "second.txt")
    git(repo, "commit", "-m", "second")

    fact = GitLandingCollector(repo, project_id="project-1").collect(
        LandingRequest("epic-TOP", "epic-TOP", first)
    )

    assert fact.state is LandingState.LANDED
    assert fact.revision == first


def test_rewritten_target_invalidates_older_durable_landing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-b", "source")
    (repo / "change.txt").write_text("land me\n")
    git(repo, "add", "change.txt")
    git(repo, "commit", "-m", "source")
    git(repo, "checkout", "-b", "target")
    collector = GitLandingCollector(repo, project_id="project-1")
    prior = collector.collect(LandingRequest("source", "target"))
    assert prior.state is LandingState.LANDED

    git(repo, "checkout", "target")
    git(repo, "reset", "--hard", base)
    refreshed = collector.collect(LandingRequest("source", "target", prior=prior))

    assert refreshed.state is LandingState.NOT_LANDED


def test_landing_fact_ledger_survives_controller_restart_and_ref_pruning(tmp_path):
    make_git_fixture(tmp_path)
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    mid = issue("MID", state=IN_PROGRESS, issue_type="epic", parent_id="TOP")
    leaf = issue("LEAF", state=DONE, parent_id="MID", work_branch="leaf")
    tracker = Tracker([top, mid, leaf])
    store_path = tmp_path / "jobs.sqlite3"
    first_store = WorkflowJobStore(str(store_path))
    first = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
        ),
        store=first_store,
    )
    first.evaluate([mid])
    first_store.close()

    git(tmp_path, "branch", "-D", "leaf")
    second_store = WorkflowJobStore(str(store_path))
    second = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1", tracker=tracker, repo_path=str(tmp_path)
        ),
        store=second_store,
    )
    batch = second.evaluate([mid])

    assert batch.tasks[0].decision.disposition is TaskDisposition.RUNNABLE
    assert any(
        item.source == "leaf" and item.target == "epic-MID" and item.durable
        for item in batch.tasks[0].facts.landings
    )
    second_store.close()


def test_rebased_source_is_proven_by_patch_equivalence(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-m", "base")
    git(repo, "checkout", "-b", "source")
    (repo / "change.txt").write_text("same patch\n")
    git(repo, "add", "change.txt")
    git(repo, "commit", "-m", "source change")
    git(repo, "checkout", "main")
    git(repo, "checkout", "-b", "target")
    git(repo, "cherry-pick", "source")
    git(repo, "checkout", "source")
    git(repo, "reset", "--hard", "HEAD~1")
    (repo / "change.txt").write_text("same patch\n")
    git(repo, "add", "change.txt")
    git(repo, "commit", "-m", "rebased source change")

    fact = GitLandingCollector(repo, project_id="project-1").collect(
        # The branch is not an ancestor of target, but its patch is identical.
        LandingRequest("source", "target")
    )

    assert fact.state is LandingState.LANDED
    assert fact.proof["kind"] == "patch_id"
    assert fact.durable


def test_containment_cycle_is_actionable_and_never_schedules_rollup(tmp_path):
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic", parent_id="MID")
    mid = issue("MID", state=IN_PROGRESS, issue_type="epic", parent_id="TOP")
    tracker = Tracker([top, mid])
    collector = EpicFactCollector(project_id="project-1", tracker=tracker)
    facts = collector.collect("TOP")

    decision = evaluate_task(top, facts)

    assert decision.action_required
    assert decision.reason_code == "operator.action_required"
    assert not decision.durable_jobs


def test_maintenance_actions_are_idempotent_and_restart_safe(tmp_path):
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    tracker = Tracker([top])
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(project_id="project-1", tracker=tracker),
        store=store,
    )

    first = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.REBASE_REPAIR,
        generation="g1",
    )
    replay = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.REBASE_REPAIR,
        generation="g1",
    )
    second = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.CLEANUP,
        generation="g1",
    )
    assert replay == first
    assert second.job_id != first.job_id
    assert {job.action for job in store.list_jobs()} == {
        EpicAction.REBASE_REPAIR.value,
        EpicAction.CLEANUP.value,
    }
    store.close()


def test_restart_recovery_requires_and_scopes_the_dead_lease_owner(tmp_path):
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    other = issue("OTHER", state=IN_PROGRESS, issue_type="epic")
    tracker = Tracker([top, other])
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(project_id="project-1", tracker=tracker),
        store=store,
    )
    epic_job = controller.schedule_action(
        task_id="TOP", action=EpicAction.REBASE_REPAIR, generation="epic-g1"
    )
    other_job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="OTHER",
            generation="review-g1",
            action="review_monitor",
            idempotency_key="review:OTHER:g1",
        )
    )
    other_project_job = store.enqueue(
        WorkflowJobSpec(
            project_id="project-2",
            task_id="FOREIGN",
            generation="epic-g1",
            action=EpicAction.CLEANUP.value,
            idempotency_key="epic:FOREIGN:g1",
        )
    )
    claimed_epic = store.claim_next(
        lease_owner="dead-epic-worker",
        lease_seconds=60,
        task_id="TOP",
    )
    claimed_other = store.claim_next(
        lease_owner="dead-epic-worker",
        lease_seconds=60,
        task_id="OTHER",
    )
    claimed_foreign = store.claim_next(
        lease_owner="dead-epic-worker",
        lease_seconds=60,
        task_id="FOREIGN",
    )
    assert claimed_epic is not None and claimed_epic.job_id == epic_job.job_id
    assert claimed_other is not None and claimed_other.job_id == other_job.job_id
    assert (
        claimed_foreign is not None
        and claimed_foreign.job_id == other_project_job.job_id
    )

    with pytest.raises(TypeError):
        controller.reconcile_after_restart([top])  # type: ignore[call-arg]

    recovered, _batch, _scheduled = controller.reconcile_after_restart(
        [top], lease_owner="dead-epic-worker"
    )

    assert recovered == 1
    # A different action lane does not erase recovered maintenance intent;
    # fresh worker revalidation will fence it if the action is no longer
    # authorized. It must no longer retain the dead lease either way.
    assert store.get(epic_job.job_id).state in {
        WorkflowJobState.QUEUED,
        WorkflowJobState.SUPERSEDED,
    }
    assert store.get(other_job.job_id).state is WorkflowJobState.RUNNING
    assert store.get(other_project_job.job_id).state is WorkflowJobState.RUNNING
    store.close()


def test_landing_history_limit_keeps_the_newest_evidence_window(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    facts = []
    for index in range(3):
        fact = LandingFact(
            "source",
            "target",
            f"{index + 1:040x}",
            {
                "kind": "git_ancestry",
                "source_sha": f"{index + 1:040x}",
                "target_sha": f"{index + 10:040x}",
            },
            f"2026-08-04T00:00:0{index}+00:00",
            "project-1",
            state=LandingState.LANDED,
            durable=True,
        )
        store.record_landing_facts(
            project_id="project-1",
            task_id="TOP",
            facts=[fact.to_dict()],
            now=float(index + 1),
        )
        facts.append(fact)

    selected = store.landing_facts(project_id="project-1", task_id="TOP", limit=2)

    assert [item["evidence_revision"] for item in selected] == [
        facts[1].evidence_revision,
        facts[2].evidence_revision,
    ]
    store.close()


def test_latest_landing_projection_cannot_starve_a_pruned_peer(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    peer = LandingFact(
        "peer-branch",
        "main",
        "1" * 40,
        {"kind": "git_ancestry", "source_sha": "1" * 40},
        "2026-08-04T00:00:00+00:00",
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )
    store.record_landing_facts(
        project_id="project-1", task_id="TOP", facts=[peer.to_dict()], now=1.0
    )
    newest = None
    for index in range(101):
        newest = LandingFact(
            "churning-branch",
            "main",
            f"{index + 2:040x}",
            {
                "kind": "git_ancestry",
                "source_sha": f"{index + 2:040x}",
                "target_sha": f"{index + 200:040x}",
            },
            f"2026-08-04T00:{index // 60:02d}:{index % 60:02d}+00:00",
            "project-1",
            state=LandingState.LANDED,
            durable=True,
        )
        store.record_landing_facts(
            project_id="project-1",
            task_id="TOP",
            facts=[newest.to_dict()],
            now=float(index + 2),
        )
    transient = LandingFact(
        "churning-branch",
        "main",
        "f" * 40,
        {"kind": "source_unavailable"},
        "2026-08-04T00:02:00+00:00",
        "project-1",
        state=LandingState.UNKNOWN,
        durable=False,
        error_code="git_observation_failed",
    )
    store.record_landing_facts(
        project_id="project-1",
        task_id="TOP",
        facts=[transient.to_dict()],
        now=200.0,
    )

    selected = store.latest_landing_facts(
        project_id="project-1", task_id="TOP", limit=100
    )

    assert {(item["source"], item["evidence_revision"]) for item in selected} == {
        ("peer-branch", peer.evidence_revision),
        ("churning-branch", newest.evidence_revision),
    }
    store.close()
