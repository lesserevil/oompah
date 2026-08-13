"""Epic rollup facts, target-relative decisions, and durable job coverage."""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from oompah.integration import IntegrationRecord
from oompah.epic_workflow import (
    EpicAction,
    EpicFactCollector,
    EpicWorkflowController,
    EpicWorkflowHandler,
    ProductionEpicWorkflowBackend,
    epic_branch,
)
from oompah.epic_workflow_adapter import OrchestratorEpicWorkflowEffects
from oompah.models import Issue
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.orchestrator import (
    EpicTargetResolutionError as OrchestratorEpicTargetResolutionError,
    Orchestrator,
)
from oompah.statuses import DONE, IN_PROGRESS, OPEN
from oompah.workflow_contract import TaskDisposition
from oompah.statuses import ARCHIVED, IN_REVIEW, IN_VALIDATION, MERGED
from oompah.task_transition_service import (
    CoordinatorTerminalAdapter,
    TaskTransitionService,
    TransitionDisposition,
    TransitionJournal,
    TransitionOutcome,
)
from oompah.terminal_transition_coordinator import TerminalTransitionCoordinator
from oompah.work_decision import decision_scheduling_revision, evaluate_task
from oompah.workflow_facts import (
    CollectedValue,
    FactDomain,
    FactObservation,
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


def retained_terminal_source(overrides=None):
    """Return authenticated terminal-provenance facts for Done fixtures."""

    overrides = overrides or {}

    def source(current: Issue):
        if current.state != DONE:
            return None
        payload = {
            "schema_version": 1,
            "marker_present": True,
            "marker_version": 1,
            "project_id": current.project_id,
            "task_id": current.identifier,
            "retained": True,
            "malformed": False,
            "authority_generation": 0,
            "authorized_by": "owner",
            "actor_source": "api",
            "marked_at": "2026-08-10T12:00:00+00:00",
            "updated_at": "2026-08-10T12:00:00+00:00",
        }
        payload.update(overrides)
        return {"terminal_provenance": payload}

    return source


def retained_historical_epic(tmp_path, identifiers):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "base.txt").write_text("base\n")
    git(tmp_path, "add", "base.txt")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "branch", "epic-OOMPAH-940")
    parent = issue("OOMPAH-940", state=IN_PROGRESS, issue_type="epic")
    children = []
    for index, identifier in enumerate(identifiers, start=1):
        child = issue(
            identifier,
            state=DONE,
            parent_id=parent.identifier,
            work_branch=identifier,
        )
        child.head_sha = f"{index:040x}"
        children.append(child)
    tracker = Tracker([parent, *children])
    return parent, tracker


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


def auto_close_snapshot(
    epic,
    *,
    revision="a" * 40,
    containment_target="main",
    landing_target=None,
    evidence_revision="auto-close-evidence-1",
    durable=True,
    duplicate_revision=None,
):
    target = landing_target or containment_target
    landings = [
        LandingFact(
            f"epic-{epic.identifier}",
            target,
            revision,
            {"kind": "git_ancestry", "source_sha": revision},
            "2026-08-10T12:00:00+00:00",
            "project-1",
            state=LandingState.LANDED,
            durable=durable,
        )
    ]
    if duplicate_revision is not None:
        landings.append(
            LandingFact(
                f"epic-{epic.identifier}",
                target,
                duplicate_revision,
                {
                    "kind": "git_ancestry",
                    "source_sha": duplicate_revision,
                },
                "2026-08-10T12:00:00+00:00",
                "project-1",
                state=LandingState.LANDED,
                durable=True,
            )
        )
    facts = MagicMock()
    facts.project_id = "project-1"
    facts.task_id = epic.identifier
    facts.fact.return_value = SimpleNamespace(
        state=FactState.KNOWN,
        value={
            "epic_branch": f"epic-{epic.identifier}",
            "target_branch": containment_target,
            "children": [],
        },
    )
    facts.landings = tuple(landings)
    decision = SimpleNamespace(
        durable_jobs=(EpicAction.AUTO_CLOSE.value,),
        evidence_revision=evidence_revision,
        reason_code="terminal.immediate_target_landing_proven",
    )
    return SimpleNamespace(epic=epic, facts=facts, decision=decision)


def auto_close_backend(snapshots):
    controller = MagicMock()
    controller.collector.project_id = "project-1"
    effects = MagicMock()
    backend = ProductionEpicWorkflowBackend(
        controller=controller,
        tracker=MagicMock(),
        effects=effects,
    )
    backend._fresh_snapshot = MagicMock(  # type: ignore[method-assign]
        side_effect=snapshots
    )
    return backend, effects


def auto_close_context():
    return SimpleNamespace(
        job=SimpleNamespace(
            action=EpicAction.AUTO_CLOSE.value,
            payload={},
            generation="auto-close-generation-1",
            checkpoint={},
        ),
        idempotency_key="auto-close-effect-1",
    )


def checkpoint_revalidation(context, revalidation):
    context.job.checkpoint = {
        "revalidation": {
            "generation": revalidation.generation,
            "evidence_revision": revalidation.evidence_revision,
            "head_sha": revalidation.head_sha,
            "details": dict(revalidation.details),
        }
    }


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
async def test_headless_root_epic_auto_close_uses_durable_landing_authority(
    tmp_path,
):
    make_git_fixture(tmp_path)
    git(tmp_path, "checkout", "main")
    git(tmp_path, "merge", "--ff-only", "epic-TOP")
    exact_head = git(tmp_path, "rev-parse", "epic-TOP")
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    assert top.work_branch is None
    assert top.target_branch is None
    assert top.review_head is None
    assert top.head_sha is None
    leaf = issue("LEAF", state=DONE, parent_id="TOP", work_branch="leaf")
    leaf.head_sha = exact_head
    tracker = Tracker([top, leaf])
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1",
            tracker=tracker,
            repo_path=str(tmp_path),
            sources={FactDomain.TERMINAL_AUDIT: retained_terminal_source()},
        ),
        store=store,
    )
    # Capture the exact landing while its source exists, then reproduce the
    # post-landing OOMPAH-940 shape in which only durable evidence survives.
    first = controller.evaluate([top]).tasks[0].decision
    assert first.durable_jobs == (EpicAction.AUTO_CLOSE.value,)
    git(tmp_path, "branch", "-D", "epic-TOP")
    _batch, scheduled = controller.reconcile([top])
    assert scheduled.jobs_created == 1
    job = store.list_jobs()[0]
    assert job.action == EpicAction.AUTO_CLOSE.value
    assert job.expected_head_sha is None
    transitions = RecordingTransitionService()
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            job.action: production_handler(
                controller,
                tracker,
                RecordingEpicEffects(),
            )
        },
        transition_services={"project-1": transitions},
        worker_id="epic-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    completed = store.get(job.job_id)
    authority = completed.checkpoint["revalidation"]["details"]
    assert authority["auto_close_exact_head"] == exact_head
    assert authority["auto_close_landing_source"] == "epic-TOP"
    assert authority["auto_close_landing_target"] == "main"
    assert completed.checkpoint["effect"]["auto_close_exact_head"] == exact_head
    assert (
        completed.checkpoint["verification"]["auto_close_exact_head"]
        == exact_head
    )
    assert len(transitions.intents) == 1
    assert transitions.intents[0].requested_status == MERGED
    assert transitions.intents[0].exact_head == exact_head
    store.close()


@pytest.mark.asyncio
async def test_native_headless_root_auto_close_normalizes_fresh_project_scope(
    tmp_path,
):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "base.txt").write_text("base\n")
    git(tmp_path, "add", "base.txt")
    git(tmp_path, "commit", "-m", "base")
    tracker = OompahMarkdownTracker(
        active_states=[OPEN, IN_PROGRESS],
        terminal_states=[DONE, MERGED, ARCHIVED],
        cwd=str(tmp_path),
        default_branch="main",
        git_sync=False,
    )
    native_epic = tracker.create_issue(
        "Native headless root epic",
        issue_type="epic",
        initial_status=IN_PROGRESS,
    )
    assert native_epic.project_id is None
    native_child = tracker.create_issue(
        "Native landed child",
        initial_status=DONE,
        parent=native_epic.identifier,
    )
    source = epic_branch(native_epic.identifier)
    child_source = native_child.identifier
    git(tmp_path, "checkout", "-b", child_source)
    (tmp_path / "landed-child.txt").write_text("landed\n")
    git(tmp_path, "add", "landed-child.txt")
    git(tmp_path, "commit", "-m", "land native child")
    child_head = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "checkout", "main")
    git(tmp_path, "branch", source, child_head)
    git(tmp_path, "merge", "--ff-only", source)
    exact_head = git(tmp_path, "rev-parse", source)
    tracker.update_issue(
        native_child.identifier,
        work_branch=child_source,
        target_branch=source,
        **{
            "oompah.integration": IntegrationRecord(
                state="integrated",
                mode="queue",
                task_branch=child_source,
                base_branch=source,
                head_sha=child_head,
                integrated_sha=exact_head,
            ).to_dict()
        },
    )

    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1",
            tracker=tracker,
            repo_path=str(tmp_path),
        ),
        store=store,
    )
    native_epic = tracker.fetch_issue_detail(native_epic.identifier)
    assert native_epic is not None and native_epic.project_id is None
    bound_epic = replace(native_epic, project_id="project-1")
    _batch, scheduled = controller.reconcile([bound_epic])
    assert scheduled.jobs_created == 1
    job = store.list_jobs()[0]
    assert job.action == EpicAction.AUTO_CLOSE.value

    project = SimpleNamespace(
        id="project-1",
        repo_url="https://github.com/owner/repo.git",
        repo_path=str(tmp_path),
        access_token=None,
    )
    orchestrator = MagicMock()
    orchestrator.project_store.get.return_value = project
    orchestrator._tracker_for_project.return_value = tracker
    orchestrator._epic_branch_for_issue.side_effect = (
        lambda current: epic_branch(current.identifier)
    )
    orchestrator._resolve_epic_target_branch.return_value = "main"
    orchestrator.review_capacity_store.active.return_value = []
    effects = OrchestratorEpicWorkflowEffects(
        orchestrator,
        project_id="project-1",
    )
    review_open = {"value": True}
    review = SimpleNamespace(
        id="1726",
        state="open",
        source_branch=source,
        target_branch="main",
        head_sha=exact_head,
    )
    provider = MagicMock()
    provider.list_open_reviews.side_effect = (
        lambda _slug: [review] if review_open["value"] else []
    )
    provider.get_branch_head_sha.return_value = exact_head

    def close_review(_slug, _review_id):
        review_open["value"] = False
        return True, "closed"

    provider.close_review.side_effect = close_review
    transitions = RecordingTransitionService()
    worker = DurableWorkflowWorker(
        store=store,
        handlers={job.action: production_handler(controller, tracker, effects)},
        transition_services={"project-1": transitions},
        worker_id="epic-worker",
    )

    with patch(
        "oompah.epic_workflow_adapter.detect_provider",
        return_value=provider,
    ):
        result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    completed = store.get(job.job_id)
    assert completed.state is WorkflowJobState.COMPLETED
    assert (
        completed.checkpoint["revalidation"]["details"]["auto_close_exact_head"]
        == exact_head
    )
    assert completed.checkpoint["effect"]["source_head"] == exact_head
    assert completed.checkpoint["verification"]["source_head"] == exact_head
    assert len(transitions.intents) == 1
    assert transitions.intents[0].requested_status == MERGED
    assert transitions.intents[0].exact_head == exact_head
    provider.close_review.assert_called_once_with("owner/repo", "1726")
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    ("revision", "target", "evidence", "ambiguous"),
)
@pytest.mark.parametrize("phase", ("apply", "verify", "build_transition"))
async def test_auto_close_phase_fence_rejects_changed_landing_authority(
    mutation,
    phase,
):
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    initial = auto_close_snapshot(top)
    changed_options = {}
    if mutation == "revision":
        changed_options["revision"] = "b" * 40
    elif mutation == "target":
        changed_options["containment_target"] = "release/current"
    elif mutation == "evidence":
        changed_options["evidence_revision"] = "auto-close-evidence-2"
    else:
        changed_options["duplicate_revision"] = "b" * 40
    changed = auto_close_snapshot(top, **changed_options)
    backend, effects = auto_close_backend([initial, changed])
    context = auto_close_context()
    revalidation = await backend.revalidate(context)
    assert revalidation.current
    assert revalidation.head_sha == "a" * 40
    checkpoint_revalidation(context, revalidation)
    verification = VerificationResult(
        True,
        {
            **dict(revalidation.details),
            "action": EpicAction.AUTO_CLOSE.value,
            "task_id": top.identifier,
            "requested_status": MERGED,
            "expected_status": IN_PROGRESS,
            "expected_version": "authority-1",
            "exact_head": "a" * 40,
            "reason_code": "terminal.immediate_target_landing_proven",
            "evidence_revision": revalidation.evidence_revision,
        },
    )

    with pytest.raises(WorkflowActionSuperseded):
        if phase == "apply":
            await backend.apply(context)
        elif phase == "verify":
            await backend.verify(
                context,
                EffectResult({"source_head": "a" * 40}),
            )
        else:
            await backend.build_transition(context, verification)

    effects.apply_epic_effect.assert_not_called()
    effects.verify_epic_effect.assert_not_called()


@pytest.mark.asyncio
async def test_auto_close_build_transition_rejects_changed_receipt_authority():
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    initial = auto_close_snapshot(top)
    backend, _effects = auto_close_backend([initial, initial])
    context = auto_close_context()
    revalidation = await backend.revalidate(context)
    checkpoint_revalidation(context, revalidation)
    verification = VerificationResult(
        True,
        {
            **dict(revalidation.details),
            "auto_close_landing_target": "release/other",
            "action": EpicAction.AUTO_CLOSE.value,
            "task_id": top.identifier,
            "requested_status": MERGED,
            "expected_status": IN_PROGRESS,
            "expected_version": "authority-1",
            "exact_head": "a" * 40,
            "reason_code": "terminal.immediate_target_landing_proven",
            "evidence_revision": revalidation.evidence_revision,
        },
    )

    with pytest.raises(
        WorkflowActionSuperseded,
        match="landing authority changed before transition",
    ):
        await backend.build_transition(context, verification)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ("wrong_target", "mutable", "ambiguous"))
async def test_auto_close_revalidation_fails_closed_without_canonical_authority(
    invalid,
):
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    options = {}
    if invalid == "wrong_target":
        options["landing_target"] = "release/other"
    elif invalid == "mutable":
        options["durable"] = False
    else:
        options["duplicate_revision"] = "b" * 40
    backend, _effects = auto_close_backend([auto_close_snapshot(top, **options)])

    result = await backend.revalidate(auto_close_context())

    assert not result.current
    assert result.head_sha is None
    assert "auto_close_exact_head" not in result.details


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "parent_id", "review_head"),
    (
        (IN_REVIEW, None, "b" * 40),
        (IN_PROGRESS, "PARENT", None),
        (OPEN, None, None),
    ),
)
async def test_auto_close_durable_fallback_is_only_for_headless_root_in_progress(
    state,
    parent_id,
    review_head,
):
    top = issue(
        "TOP",
        state=state,
        issue_type="epic",
        parent_id=parent_id,
    )
    top.review_head = review_head
    backend, effects = auto_close_backend([auto_close_snapshot(top)])

    result = await backend.revalidate(auto_close_context())

    assert not result.current
    effects.apply_epic_effect.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "current"),
    (
        (IN_PROGRESS, True),
        (DONE, True),
        (IN_REVIEW, True),
        (OPEN, False),
        (IN_VALIDATION, False),
        (MERGED, False),
        (ARCHIVED, False),
    ),
)
async def test_auto_close_requires_a_current_terminal_rollup_source_state(
    state,
    current,
):
    top = issue("TOP", state=state, issue_type="epic")
    top.review_head = "a" * 40
    backend, _effects = auto_close_backend([auto_close_snapshot(top)])

    result = await backend.revalidate(auto_close_context())

    assert result.current is current


@pytest.mark.asyncio
async def test_staged_auto_close_supersedes_delayed_copy_after_restart(tmp_path):
    database = tmp_path / "jobs.sqlite3"
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    top.review_head = "a" * 40
    effects = RecordingEpicEffects()
    transitions = RecordingTransitionService()

    async def stage_terminal_validation(intent):
        transitions.intents.append(intent)
        top.state = IN_VALIDATION
        return TransitionOutcome(
            transition_id="transition-staged",
            project_id=intent.project_id,
            task_id=intent.task_id,
            disposition=TransitionDisposition.STAGED,
            reason_code="transition.terminal_staged",
            observed_status=IN_VALIDATION,
            observed_version=intent.expected_version,
            requested_status=intent.requested_status,
            applied_status=IN_VALIDATION,
            audit_id="audit-1",
        )

    transitions.execute = stage_terminal_validation
    store = WorkflowJobStore(str(database))
    controller = EpicWorkflowController(
        collector=SimpleNamespace(project_id="project-1"),
        store=store,
    )
    first = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.AUTO_CLOSE,
        generation="auto-close-before-validation",
        expected_evidence_revision="evidence-before-validation",
        expected_head_sha="a" * 40,
    )
    backend = ProductionEpicWorkflowBackend(
        controller=controller,
        tracker=MagicMock(),
        effects=effects,
    )
    backend._fresh_snapshot = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda _context: auto_close_snapshot(
            top,
            evidence_revision=(
                "evidence-before-validation"
                if top.state == IN_PROGRESS
                else "evidence-in-validation"
            ),
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            EpicAction.AUTO_CLOSE.value: EpicWorkflowHandler(backend),
        },
        transition_services={"project-1": transitions},
        worker_id="epic-worker-before-restart",
    )

    staged = await worker.run_once()

    assert staged.disposition is WorkflowRunDisposition.COMPLETED
    completed = store.get(first.job_id)
    assert completed.result_transition["disposition"] == "staged"
    assert top.state == IN_VALIDATION
    assert effects.apply_calls == 1
    assert len(transitions.intents) == 1

    delayed = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.AUTO_CLOSE,
        generation="auto-close-delayed-after-validation",
        expected_evidence_revision="evidence-in-validation",
        expected_head_sha="a" * 40,
    )
    audit = store.enqueue(
        WorkflowJobSpec(
            project_id="project-1",
            task_id="TOP",
            generation="terminal-audit-in-validation",
            action="terminal_audit",
            idempotency_key="terminal-audit:TOP:in-validation",
            scheduling_lane="terminal-audit:Merged",
        )
    )
    store.close()

    restarted_store = WorkflowJobStore(str(database))
    restarted_controller = EpicWorkflowController(
        collector=SimpleNamespace(project_id="project-1"),
        store=restarted_store,
    )
    restarted_backend = ProductionEpicWorkflowBackend(
        controller=restarted_controller,
        tracker=MagicMock(),
        effects=effects,
    )
    restarted_backend._fresh_snapshot = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda _context: auto_close_snapshot(
            top,
            evidence_revision="evidence-in-validation",
        )
    )
    restarted_worker = DurableWorkflowWorker(
        store=restarted_store,
        handlers={
            EpicAction.AUTO_CLOSE.value: EpicWorkflowHandler(restarted_backend),
        },
        transition_services={"project-1": transitions},
        worker_id="epic-worker-after-restart",
    )

    superseded = await restarted_worker.run_once()

    assert superseded.disposition is WorkflowRunDisposition.SUPERSEDED
    assert restarted_store.get(delayed.job_id).state is WorkflowJobState.SUPERSEDED
    assert restarted_store.get(audit.job_id).state is WorkflowJobState.QUEUED
    assert effects.apply_calls == 1
    assert len(transitions.intents) == 1
    restarted_store.close()


@pytest.mark.asyncio
async def test_landed_in_review_epic_stages_through_real_terminal_coordinator(
    tmp_path,
):
    class TerminalTracker(Tracker):
        def __init__(self, issues):
            super().__init__(issues)
            self.metadata = {}

        def update_issue(self, identifier, **fields):
            self.issues[identifier].state = fields["status"]

        def get_metadata(self, identifier):
            assert identifier == "TOP"
            return dict(self.metadata)

        def set_metadata_field(self, identifier, key, value):
            assert identifier == "TOP"
            self.metadata[key] = value

        def add_comment(self, identifier, text, author="oompah"):
            assert identifier == "TOP"
            return {"id": "comment-1", "text": text, "author": author}

        def current_status(self, identifier):
            assert identifier == "TOP"
            return self.issues[identifier].state

    class ProjectStore:
        def __init__(self, revision):
            self.revision = revision
            self.lock = threading.RLock()

        def project_write_lock(self, project_id):
            assert project_id == "project-1"
            return self.lock

        def get(self, project_id):
            return (
                SimpleNamespace(default_branch="main")
                if project_id == "project-1"
                else None
            )

        def resolve_audit_revision(self, project_id, revision):
            assert project_id == "project-1"
            if revision != self.revision:
                raise ValueError("terminal audit revision is unavailable")
            return self.revision

        def resolve_containing_audit_revision(
            self,
            project_id,
            *,
            target_revision,
            landing_revision,
        ):
            assert project_id == "project-1"
            assert target_revision == "origin/main"
            assert landing_revision == self.revision
            return self.revision

    make_git_fixture(tmp_path)
    git(tmp_path, "checkout", "main")
    git(tmp_path, "merge", "--ff-only", "epic-TOP")
    landing_head = git(tmp_path, "rev-parse", "epic-TOP")
    top = issue("TOP", state=IN_REVIEW, issue_type="epic")
    top.review_head = landing_head
    leaf = issue("LEAF", state=DONE, parent_id="TOP", work_branch="leaf")
    tracker = TerminalTracker([top, leaf])
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1",
            tracker=tracker,
            repo_path=str(tmp_path),
        ),
        store=store,
    )
    decision = controller.evaluate([top]).tasks[0].decision
    assert decision.durable_jobs == (EpicAction.AUTO_CLOSE.value,)
    _batch, scheduled = controller.reconcile([top])
    assert scheduled.jobs_created == 1
    job = store.list_jobs()[0]
    project_store = ProjectStore(landing_head)
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    transition_service = TaskTransitionService(
        project_id="project-1",
        tracker=tracker,
        journal=TransitionJournal(str(tmp_path / "transitions.sqlite3")),
        terminal_adapter=CoordinatorTerminalAdapter(
            coordinator,
            mutation_guard=lambda _intent: None,
        ),
        write_lock=lambda: project_store.lock,
    )
    effects = RecordingEpicEffects()
    worker = DurableWorkflowWorker(
        store=store,
        handlers={job.action: production_handler(controller, tracker, effects)},
        transition_services={"project-1": transition_service},
        worker_id="landed-in-review-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.COMPLETED
    completed = store.get(job.job_id)
    assert completed.result_transition["disposition"] == "staged"
    assert tracker.issues["TOP"].state == IN_VALIDATION
    assert effects.apply_calls == 1
    store.close()


@pytest.mark.asyncio
async def test_auto_close_status_race_is_fenced_before_external_effect(tmp_path):
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    top.review_head = "a" * 40
    effects = RecordingEpicEffects()
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=SimpleNamespace(project_id="project-1"),
        store=store,
    )
    queued = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.AUTO_CLOSE,
        generation="auto-close-status-race",
        expected_evidence_revision="status-race-evidence",
        expected_head_sha="a" * 40,
    )
    backend = ProductionEpicWorkflowBackend(
        controller=controller,
        tracker=MagicMock(),
        effects=effects,
    )
    backend._fresh_snapshot = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda _context: auto_close_snapshot(
            top,
            evidence_revision="status-race-evidence",
        )
    )

    def advance_after_revalidation(phase, _job):
        if phase == "revalidated":
            top.state = IN_VALIDATION

    transitions = RecordingTransitionService()
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            EpicAction.AUTO_CLOSE.value: EpicWorkflowHandler(backend),
        },
        transition_services={"project-1": transitions},
        worker_id="epic-worker",
        phase_observer=advance_after_revalidation,
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.SUPERSEDED
    assert store.get(queued.job_id).state is WorkflowJobState.SUPERSEDED
    assert effects.apply_calls == 0
    assert transitions.intents == []
    store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("source_state", (IN_REVIEW, DONE))
async def test_current_auto_close_preserves_real_transition_rejection(
    tmp_path,
    source_state,
):
    top = issue("TOP", state=source_state, issue_type="epic")
    top.review_head = "a" * 40
    effects = RecordingEpicEffects()
    transitions = RecordingTransitionService()

    async def reject_transition(intent):
        transitions.intents.append(intent)
        return TransitionOutcome(
            transition_id="transition-rejected",
            project_id=intent.project_id,
            task_id=intent.task_id,
            disposition=TransitionDisposition.REJECTED,
            reason_code="transition.terminal_rejected",
            observed_status=source_state,
            observed_version=intent.expected_version,
            requested_status=intent.requested_status,
        )

    transitions.execute = reject_transition
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=SimpleNamespace(project_id="project-1"),
        store=store,
    )
    queued = controller.schedule_action(
        task_id="TOP",
        action=EpicAction.AUTO_CLOSE,
        generation="auto-close-current-rejection",
        expected_evidence_revision="current-rejection-evidence",
        expected_head_sha="a" * 40,
        max_attempts=1,
    )
    backend = ProductionEpicWorkflowBackend(
        controller=controller,
        tracker=MagicMock(),
        effects=effects,
    )
    backend._fresh_snapshot = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda _context: auto_close_snapshot(
            top,
            evidence_revision="current-rejection-evidence",
        )
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers={
            EpicAction.AUTO_CLOSE.value: EpicWorkflowHandler(backend),
        },
        transition_services={"project-1": transitions},
        worker_id="epic-worker",
    )

    result = await worker.run_once()

    assert result.disposition is WorkflowRunDisposition.ACTION_REQUIRED
    exhausted = store.get(queued.job_id)
    assert exhausted.state is WorkflowJobState.EXHAUSTED
    assert exhausted.failure_category.value == "policy"
    assert "transition.terminal_rejected" in exhausted.last_error
    assert effects.apply_calls == 1
    assert len(transitions.intents) == 1
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
async def test_rebase_revalidation_accepts_fresh_observation_revision_before_effect():
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    facts = MagicMock()
    facts.fact.return_value = SimpleNamespace(
        state=FactState.KNOWN,
        value={"epic_branch": "epic-TOP", "target_branch": "main"},
    )
    decision = SimpleNamespace(
        durable_jobs=(EpicAction.REBASE_REPAIR.value,),
        evidence_revision="fresh-observation-revision",
        reason_code="epic.rebase_required",
    )
    controller = MagicMock()
    controller.collector.project_id = "project-1"
    backend = ProductionEpicWorkflowBackend(
        controller=controller,
        tracker=MagicMock(),
        effects=MagicMock(),
    )
    backend._fresh_snapshot = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(epic=top, facts=facts, decision=decision)
    )
    context = SimpleNamespace(
        job=SimpleNamespace(
            action=EpicAction.REBASE_REPAIR.value,
            payload={
                "target_branch": "main",
                "evidence_revision": "event-observation-revision",
            },
            checkpoint={},
            generation="rebase-generation-1",
            expected_evidence_revision=None,
            expected_head_sha=None,
        )
    )

    result = await backend.revalidate(context)

    assert result.current is True
    assert result.evidence_revision == "fresh-observation-revision"
    assert result.generation == context.job.generation


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


def test_controller_uses_authoritative_graph_indexes_without_tracker_fanout(
    tmp_path,
):
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    mid = issue("MID", state=IN_PROGRESS, issue_type="epic", parent_id="TOP")
    leaf = issue("LEAF", state=OPEN, parent_id="MID", work_branch="leaf")

    class NoFanoutTracker(Tracker):
        def fetch_issue_detail(self, _identifier):
            raise AssertionError("authoritative epic root must not be refetched")

        def fetch_children(self, _identifier):
            raise AssertionError("authoritative child index must be reused")

    tracker = NoFanoutTracker([top, mid, leaf])
    store = WorkflowJobStore(str(tmp_path / "indexed-epics.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(project_id="project-1", tracker=tracker),
        store=store,
    )
    authoritative_issues = {
        item.identifier.casefold(): item for item in (top, mid, leaf)
    }
    authoritative_children = {
        "top": (mid,),
        "mid": (leaf,),
    }

    batch = controller.evaluate(
        (top, mid),
        persist_evidence=False,
        authoritative_issues=authoritative_issues,
        authoritative_children=authoritative_children,
    )

    facts_by_task = {item.task.identifier: item.facts for item in batch.tasks}
    assert [
        child["identifier"]
        for child in facts_by_task["TOP"].fact("containment").value["children"]
    ] == ["MID"]
    assert [
        child["identifier"]
        for child in facts_by_task["MID"].fact("containment").value["children"]
    ] == ["LEAF"]
    store.close()


def test_controller_owns_inferred_backlog_rollup_and_promotes_one_step(tmp_path):
    root = issue("ROOT", state=IN_PROGRESS, issue_type="epic")
    parent = issue("PARENT", state="Backlog", issue_type="feature", parent_id="ROOT")
    child = issue("CHILD", state=OPEN, parent_id="PARENT")
    tracker = Tracker([root, parent, child])
    store = WorkflowJobStore(str(tmp_path / "inferred-rollup.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(project_id="project-1", tracker=tracker),
        store=store,
    )
    authoritative_issues = {
        item.identifier.casefold(): item for item in (root, parent, child)
    }
    authoritative_children = {"root": (parent,), "parent": (child,)}

    batch = controller.evaluate(
        (parent,),
        persist_evidence=False,
        authoritative_issues=authoritative_issues,
        authoritative_children=authoritative_children,
    )

    assert len(batch.tasks) == 1
    decision = batch.tasks[0].decision
    assert decision.reason_code == "rollup.status_reconciliation"
    assert decision.durable_jobs == ("rollup_reconciliation",)
    assert decision.recommended_status == OPEN
    store.close()


def test_post_landed_child_rollup_uses_exact_standalone_target_route():
    top = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    leaf = issue("LEAF", state=DONE, parent_id="TOP", work_branch="leaf")
    leaf.target_branch = "main"
    leaf.integration = IntegrationRecord(
        state="ready",
        mode="standalone",
        post_landed_parent_id="TOP",
        task_branch="leaf",
        base_branch="main",
        head_sha="a" * 40,
    )
    collector = EpicFactCollector(
        project_id="project-1", tracker=Tracker([top, leaf])
    )
    standalone = collector._graph(top).children[0]
    leaf.integration = replace(
        leaf.integration,
        mode="queue",
        post_landed_parent_id=None,
        base_branch="epic-TOP",
    )
    leaf.target_branch = "epic-TOP"
    queued = collector._graph(top).children[0]

    assert (
        standalone["landing_source"],
        standalone["landing_target"],
        standalone["revision"],
    ) == ("leaf", "main", "a" * 40)
    assert queued["landing_target"] == "epic-TOP"


def test_retained_historical_children_compose_exact_parent_rollup_waivers(
    tmp_path,
):
    identifiers = (
        "OOMPAH-956",
        "OOMPAH-960",
        "OOMPAH-961",
        "OOMPAH-962",
        "OOMPAH-967",
        "OOMPAH-968",
        "OOMPAH-979",
        "OOMPAH-980",
    )
    parent, tracker = retained_historical_epic(tmp_path, identifiers)
    tracker.issues["OOMPAH-962"].title = "Rebase OOMPAH-940 onto main"
    for identifier in ("OOMPAH-979", "OOMPAH-980"):
        child = tracker.issues[identifier]
        child.target_branch = "main"
        child.integration = IntegrationRecord(
            state="ready",
            mode="standalone",
            post_landed_parent_id=parent.identifier,
            task_branch=identifier,
            base_branch="main",
            head_sha=child.head_sha,
        )
    collector = EpicFactCollector(
        project_id="project-1",
        tracker=tracker,
        repo_path=str(tmp_path),
        sources={FactDomain.TERMINAL_AUDIT: retained_terminal_source()},
    )

    facts = collector.collect(parent.identifier)
    children = facts.fact(FactDomain.CONTAINMENT).value["children"]
    proofs = {
        child["identifier"]: child["retained_terminal_provenance"]
        for child in children
        if "retained_terminal_provenance" in child
    }
    decision = evaluate_task(parent, facts)

    assert set(proofs) == set(identifiers) - {"OOMPAH-962"}
    for child in children:
        if child["identifier"] == "OOMPAH-962":
            assert child["kind"] == "maintenance"
            assert child["requires_landing"] is False
            assert "retained_terminal_provenance" not in child
            continue
        proof = proofs[child["identifier"]]
        assert proof["kind"] == "owner_terminal_provenance"
        assert proof["project_id"] == "project-1"
        assert proof["parent_id"] == parent.identifier
        assert proof["task_id"] == child["identifier"]
        assert proof["status"] == DONE
        assert proof["landing_source"] == child["landing_source"]
        assert proof["landing_target"] == child["landing_target"]
        assert proof["revision"] == child["revision"]
        assert proof["authority_version"] == child["authority_version"]
        assert proof["marker_version"] == 1
        assert proof["provenance_authority_generation"] == 0
    assert {
        child["landing_target"]
        for child in children
        if child["identifier"] in {"OOMPAH-979", "OOMPAH-980"}
    } == {"main"}
    # Retention is an explicit rollup waiver, never a forged Git landing.
    assert not any(landing.source in identifiers for landing in facts.landings)
    assert decision.disposition is TaskDisposition.RUNNABLE
    assert decision.reason_code == "terminal.immediate_target_landing_proven"
    assert decision.durable_jobs == (EpicAction.AUTO_CLOSE.value,)


def test_retained_child_with_native_blank_project_uses_collector_scope(tmp_path):
    parent, tracker = retained_historical_epic(tmp_path, ("OOMPAH-956",))
    tracker.issues["OOMPAH-956"].project_id = None
    facts = EpicFactCollector(
        project_id="project-1",
        tracker=tracker,
        repo_path=str(tmp_path),
        sources={FactDomain.TERMINAL_AUDIT: retained_terminal_source()},
    ).collect(parent.identifier)

    child = facts.fact(FactDomain.CONTAINMENT).value["children"][0]

    assert child["retained_terminal_provenance"]["project_id"] == "project-1"
    assert evaluate_task(parent, facts).durable_jobs == (EpicAction.AUTO_CLOSE.value,)


@pytest.mark.parametrize("wrapper", ("observation", "collected"))
def test_retained_child_accepts_normalized_terminal_fact_sources(tmp_path, wrapper):
    parent, tracker = retained_historical_epic(tmp_path, ("OOMPAH-956",))
    raw_source = retained_terminal_source()

    def source(current):
        value = raw_source(current)
        if value is None:
            return None
        if wrapper == "observation":
            return FactObservation.known(
                FactDomain.TERMINAL_AUDIT,
                value,
                observed_at="2026-08-10T12:00:00+00:00",
                source="terminal-audit",
            )
        return CollectedValue(
            value,
            observed_at="2026-08-10T12:00:00+00:00",
            source="terminal-audit",
            stale_after_seconds=60,
        )

    facts = EpicFactCollector(
        project_id="project-1",
        tracker=tracker,
        repo_path=str(tmp_path),
        sources={FactDomain.TERMINAL_AUDIT: source},
        clock=lambda: datetime(2026, 8, 10, 12, tzinfo=timezone.utc),
    ).collect(parent.identifier)

    child = facts.fact(FactDomain.CONTAINMENT).value["children"][0]

    assert child["retained_terminal_provenance"]["task_id"] == "OOMPAH-956"
    assert evaluate_task(parent, facts).durable_jobs == (EpicAction.AUTO_CLOSE.value,)


def test_stale_terminal_fact_source_cannot_waive_child_landing(tmp_path):
    parent, tracker = retained_historical_epic(tmp_path, ("OOMPAH-956",))
    raw_source = retained_terminal_source()

    def stale_source(current):
        value = raw_source(current)
        if value is None:
            return None
        return CollectedValue(
            value,
            observed_at="2026-08-10T11:00:00+00:00",
            source="terminal-audit",
            stale_after_seconds=60,
        )

    facts = EpicFactCollector(
        project_id="project-1",
        tracker=tracker,
        repo_path=str(tmp_path),
        sources={FactDomain.TERMINAL_AUDIT: stale_source},
        clock=lambda: datetime(2026, 8, 10, 12, tzinfo=timezone.utc),
    ).collect(parent.identifier)

    child = facts.fact(FactDomain.CONTAINMENT).value["children"][0]
    decision = evaluate_task(parent, facts)

    assert "retained_terminal_provenance" not in child
    assert decision.durable_jobs == (EpicAction.CHILD_LANDING_VERIFICATION.value,)


@pytest.mark.parametrize(
    "override",
    [
        {"marker_present": False},
        {"retained": False, "authority_generation": 4},
        {"malformed": True},
        {"project_id": "other-project"},
        {"task_id": "OTHER"},
        {"authority_generation": -1},
        {"authorized_by": ""},
    ],
)
def test_invalid_or_revoked_child_retention_keeps_normal_landing_requirement(
    tmp_path,
    override,
):
    parent, tracker = retained_historical_epic(tmp_path, ("OOMPAH-956",))
    facts = EpicFactCollector(
        project_id="project-1",
        tracker=tracker,
        repo_path=str(tmp_path),
        sources={
            FactDomain.TERMINAL_AUDIT: retained_terminal_source(override)
        },
    ).collect(parent.identifier)
    child = facts.fact(FactDomain.CONTAINMENT).value["children"][0]

    decision = evaluate_task(parent, facts)

    assert "retained_terminal_provenance" not in child
    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "landing.evidence_unknown"
    assert decision.durable_jobs == (EpicAction.CHILD_LANDING_VERIFICATION.value,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_id", "other-project"),
        ("parent_id", "OTHER-EPIC"),
        ("task_id", "OTHER"),
        ("status", OPEN),
        ("landing_source", "other-source"),
        ("landing_target", "other-target"),
        ("revision", "f" * 40),
        ("authority_version", "f" * 64),
        ("provenance_authority_generation", -1),
    ],
)
def test_mismatched_child_retention_proof_cannot_bypass_landing(
    tmp_path,
    field,
    value,
):
    parent, tracker = retained_historical_epic(tmp_path, ("OOMPAH-956",))
    facts = EpicFactCollector(
        project_id="project-1",
        tracker=tracker,
        repo_path=str(tmp_path),
        sources={FactDomain.TERMINAL_AUDIT: retained_terminal_source()},
    ).collect(parent.identifier)
    containment = facts.fact(FactDomain.CONTAINMENT)
    containment_value = dict(containment.value)
    child = dict(containment_value["children"][0])
    proof = dict(child["retained_terminal_provenance"])
    proof[field] = value
    child["retained_terminal_provenance"] = proof
    containment_value["children"] = [child]
    observations = dict(facts.observations)
    observations[FactDomain.CONTAINMENT] = FactObservation.known(
        FactDomain.CONTAINMENT,
        containment_value,
        observed_at=containment.observed_at,
        source=containment.source,
    )
    mismatched = replace(facts, observations=observations, facts_version=None)

    decision = evaluate_task(parent, mismatched)

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "landing.evidence_unknown"
    assert decision.durable_jobs == (EpicAction.CHILD_LANDING_VERIFICATION.value,)


@pytest.mark.parametrize(
    "field",
    ("identifier", "landing_source", "landing_target", "authority_version"),
)
def test_empty_child_retention_identity_cannot_bypass_landing(tmp_path, field):
    parent, tracker = retained_historical_epic(tmp_path, ("OOMPAH-956",))
    facts = EpicFactCollector(
        project_id="project-1",
        tracker=tracker,
        repo_path=str(tmp_path),
        sources={FactDomain.TERMINAL_AUDIT: retained_terminal_source()},
    ).collect(parent.identifier)
    containment = facts.fact(FactDomain.CONTAINMENT)
    containment_value = dict(containment.value)
    child = dict(containment_value["children"][0])
    proof = dict(child["retained_terminal_provenance"])
    child[field] = ""
    proof["task_id" if field == "identifier" else field] = ""
    child["retained_terminal_provenance"] = proof
    containment_value["children"] = [child]
    observations = dict(facts.observations)
    observations[FactDomain.CONTAINMENT] = FactObservation.known(
        FactDomain.CONTAINMENT,
        containment_value,
        observed_at=containment.observed_at,
        source=containment.source,
    )
    malformed = replace(facts, observations=observations, facts_version=None)

    decision = evaluate_task(parent, malformed)

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "landing.evidence_unknown"
    assert decision.durable_jobs == (EpicAction.CHILD_LANDING_VERIFICATION.value,)


def test_retained_child_does_not_replace_parent_epic_landing(tmp_path):
    make_git_fixture(tmp_path)
    parent = issue("TOP", state=IN_PROGRESS, issue_type="epic")
    child = issue(
        "HISTORICAL",
        state=DONE,
        parent_id=parent.identifier,
        work_branch="pruned-historical",
    )
    child.head_sha = "f" * 40
    facts = EpicFactCollector(
        project_id="project-1",
        tracker=Tracker([parent, child]),
        repo_path=str(tmp_path),
        sources={FactDomain.TERMINAL_AUDIT: retained_terminal_source()},
    ).collect(parent.identifier)

    decision = evaluate_task(parent, facts)
    own_landing = next(
        landing for landing in facts.landings if landing.source == "epic-TOP"
    )

    assert own_landing.state is LandingState.NOT_LANDED
    assert decision.reason_code == "rollup.children_complete"
    assert decision.durable_jobs == (EpicAction.ROLLUP_REVIEW_CREATION.value,)


def test_retained_child_rollup_is_total_and_idempotent_after_restart(tmp_path):
    parent, tracker = retained_historical_epic(tmp_path, ("OOMPAH-956",))
    store = WorkflowJobStore(str(tmp_path / "jobs.sqlite3"))
    controller = EpicWorkflowController(
        collector=EpicFactCollector(
            project_id="project-1",
            tracker=tracker,
            repo_path=str(tmp_path),
            sources={FactDomain.TERMINAL_AUDIT: retained_terminal_source()},
            clock=lambda: datetime(2026, 8, 10, 12, tzinfo=timezone.utc),
        ),
        store=store,
    )

    first, scheduled = controller.reconcile([parent])
    recovered, restarted, replay = controller.reconcile_after_restart(
        [parent], lease_owner="replaced-worker"
    )

    first_decision = first.tasks[0].decision
    restarted_decision = restarted.tasks[0].decision
    jobs = store.list_jobs(limit=20)
    assert scheduled.jobs_created == 1
    assert recovered == 0
    assert replay.jobs_created == 0
    assert restarted_decision.to_dict() == first_decision.to_dict()
    assert [job.action for job in jobs] == [EpicAction.AUTO_CLOSE.value]
    assert all(
        job.action != EpicAction.CHILD_LANDING_VERIFICATION.value for job in jobs
    )
    persisted = store.latest_landing_facts(
        project_id="project-1",
        task_id=parent.identifier,
        limit=20,
    )
    assert all(
        fact.get("proof", {}).get("kind") != "owner_terminal_provenance"
        for fact in persisted
    )
    store.close()


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
    assert cursor.decision_revision == decision_scheduling_revision(decision)
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
