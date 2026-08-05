"""Production implementation adapter, receipt, and cutover coverage."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from oompah.implementation_workflow import (
    IMPLEMENTATION_ACTIONS,
    ImplementationAction,
    ImplementationDisposition,
    ImplementationOwnershipSource,
    ImplementationState,
)
from oompah.implementation_workflow_adapter import (
    ImplementationReceiptStore,
    OrchestratorImplementationEffects,
    ProductionImplementationWorkflowBackend,
    build_implementation_workflow_handlers,
)
from oompah.models import Issue, OwnerClaim
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.orchestrator import Orchestrator
from oompah.statuses import (
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    NEEDS_HUMAN,
    OPEN,
    READY_TO_INTEGRATE,
)
from oompah.task_transition_service import issue_authority_version
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobStore
from oompah.workflow_worker import (
    VerificationResult,
    WorkflowActionError,
    WorkflowJobContext,
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
        self.admit_dispatch = True
        self.state = SimpleNamespace(owner_claims={}, reject_streak={})
        self._owner_claims_lock = __import__("threading").RLock()
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
        self.running[issue.id] = SimpleNamespace(
            issue=issue,
            run_id=f"run-{len(self.dispatches)}",
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
    effects.receipts.close()


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

    with pytest.raises(WorkflowActionError, match="claim changed"):
        await effects.apply(context)

    assert orch.claims[("project-a", issue.id)].claim_id == "replacement-claim"
    assert orch.released == []


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
    issue.integration = SimpleNamespace(state="ready", head_sha=HEAD_A)
    tracker = Tracker(issue)
    orch = FakeOrchestrator(tmp_path, {"project-a": tracker})
    _jobs, context = make_context(
        tmp_path,
        action=ImplementationAction.VALIDATION_SUBMISSION,
        payload={"work_branch": "TASK-1", "head_sha": HEAD_A},
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
    assert intent.evidence_generation == context.job.generation
    effects.receipts.close()
