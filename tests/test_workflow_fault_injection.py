"""Restart and external-failure injection at every workflow boundary."""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.task_transition_service import (
    TransitionAuthority,
    TransitionIntent,
    TransitionJournal,
    TransitionPhase,
)
from oompah.workflow_fault_injection import (
    ALL_RESTART_POINTS,
    AuthorityFaultAdapter,
    DeterministicFaultScript,
    EventDeliveryAdapter,
    EventDeliveryMode,
    FaultBoundary,
    FaultInjectingActionHandler,
    FaultInjectingJobStore,
    FaultInjectingTracker,
    FaultInjectingTransitionJournal,
    FaultKind,
    FaultMoment,
    FaultPoint,
    FaultRule,
    FaultedValueSource,
    GitFaultAdapter,
    InjectedProcessDeath,
    InjectedWorkflowFailure,
    ManualLeaseClock,
    ValueFaultMode,
    run_sync_boundary,
)
from oompah.workflow_jobs import WorkflowJobSpec, WorkflowJobState, WorkflowJobStore
from oompah.workflow_worker import (
    DurableWorkflowWorker,
    EffectObservation,
    EffectResult,
    RevalidationResult,
    VerificationResult,
    WorkflowActionDomain,
    WorkflowRunDisposition,
)


def point(boundary, moment):
    return FaultPoint(boundary, moment)


def script_for(boundary, moment, kind=FaultKind.PROCESS_DEATH):
    return DeterministicFaultScript((FaultRule(point(boundary, moment), kind),))


def spec():
    return WorkflowJobSpec(
        project_id="project-1",
        task_id="TASK-1",
        generation="generation-1",
        action="test",
        idempotency_key="task-1:test:generation-1",
    )


def tracker(root):
    return OompahMarkdownTracker(
        active_states=["Open", "In Progress", "In Validation"],
        terminal_states=["Done", "Merged", "Archived"],
        cwd=str(root),
        default_branch="main",
        git_sync=False,
    )


def intent():
    return TransitionIntent(
        project_id="project-1",
        task_id="TASK-1",
        expected_status="Open",
        expected_version="version-1",
        requested_status="In Progress",
        actor="worker",
        authority=TransitionAuthority.WORKER,
        reason_code="dispatch.eligible",
        idempotency_key="job-1:transition",
        originating_job="job-1",
        evidence_generation="generation-1",
    )


def test_restart_point_inventory_covers_both_sides_of_every_boundary():
    assert len(ALL_RESTART_POINTS) == len(FaultBoundary) * len(FaultMoment) == 16
    assert {item.boundary for item in ALL_RESTART_POINTS} == set(FaultBoundary)
    assert {item.moment for item in ALL_RESTART_POINTS} == set(FaultMoment)


@pytest.mark.parametrize("fault_point", ALL_RESTART_POINTS, ids=lambda item: item.key)
def test_each_boundary_failure_is_one_shot_serializable_and_replayable(fault_point):
    script = DeterministicFaultScript((FaultRule(fault_point),))
    effect = []

    with pytest.raises(InjectedProcessDeath) as raised:
        run_sync_boundary(script, fault_point.boundary, lambda: effect.append("done"))

    assert raised.value.point == fault_point
    assert effect == ([] if fault_point.moment is FaultMoment.BEFORE else ["done"])
    restarted = DeterministicFaultScript.from_json(script.stable_json())
    run_sync_boundary(restarted, fault_point.boundary, lambda: effect.append("done"))
    assert restarted.observations(fault_point) == 2


@pytest.mark.parametrize("moment", list(FaultMoment))
def test_enqueue_fault_converges_after_real_sqlite_restart(tmp_path, moment):
    path = str(tmp_path / f"enqueue-{moment.value}.sqlite3")
    first = WorkflowJobStore(path)
    script = script_for(FaultBoundary.JOB_ENQUEUE, moment)
    with pytest.raises(InjectedProcessDeath):
        FaultInjectingJobStore(first, script).enqueue(spec())
    first.close()

    restarted = WorkflowJobStore(path)
    try:
        job = FaultInjectingJobStore(
            restarted, DeterministicFaultScript.from_json(script.stable_json())
        ).enqueue(spec())
        assert job.state is WorkflowJobState.QUEUED
        assert len(restarted.list_jobs()) == 1
        restarted.integrity_check()
    finally:
        restarted.close()


@pytest.mark.parametrize("moment", list(FaultMoment))
def test_lease_fault_converges_after_real_sqlite_restart(tmp_path, moment):
    path = str(tmp_path / f"lease-{moment.value}.sqlite3")
    first = WorkflowJobStore(path)
    first.enqueue(spec())
    script = script_for(FaultBoundary.JOB_LEASE, moment)
    with pytest.raises(InjectedProcessDeath):
        FaultInjectingJobStore(first, script).claim_next(
            lease_owner="worker", lease_seconds=30
        )
    first.close()

    restarted = WorkflowJobStore(path)
    try:
        restarted.recover_abandoned()
        claimed = FaultInjectingJobStore(
            restarted, DeterministicFaultScript.from_json(script.stable_json())
        ).claim_next(lease_owner="worker-2", lease_seconds=30)
        assert claimed.state is WorkflowJobState.RUNNING
        assert len(restarted.list_jobs()) == 1
        restarted.integrity_check()
    finally:
        restarted.close()


@pytest.mark.parametrize("moment", list(FaultMoment))
def test_completion_fault_converges_after_real_sqlite_restart(tmp_path, moment):
    path = str(tmp_path / f"complete-{moment.value}.sqlite3")
    first = WorkflowJobStore(path)
    first.enqueue(spec())
    claimed = first.claim_next(lease_owner="worker", lease_seconds=30)
    script = script_for(FaultBoundary.COMPLETION, moment)
    with pytest.raises(InjectedProcessDeath):
        FaultInjectingJobStore(first, script).complete(
            claimed.job_id, claimed.lease_token
        )
    first.close()

    restarted = WorkflowJobStore(path)
    try:
        observed = restarted.get(claimed.job_id)
        if observed.state is not WorkflowJobState.COMPLETED:
            restarted.recover_abandoned()
            resumed = restarted.claim_next(lease_owner="worker-2", lease_seconds=30)
            restarted.complete(resumed.job_id, resumed.lease_token)
        assert restarted.get(claimed.job_id).state is WorkflowJobState.COMPLETED
        restarted.integrity_check()
    finally:
        restarted.close()


class IdempotentHandler:
    domain = WorkflowActionDomain.GIT

    def __init__(self):
        self.revalidations = 0
        self.effect_keys = set()
        self.verifications = 0

    async def revalidate(self, context):
        self.revalidations += 1
        return RevalidationResult("generation-1")

    async def inspect(self, context):
        return EffectObservation("effect" in self.effect_keys)

    async def apply(self, context):
        self.effect_keys.add("effect")
        return EffectResult({"effect": "effect"})

    async def verify(self, context, effect):
        self.verifications += 1
        return VerificationResult("effect" in self.effect_keys)

    async def build_transition(self, context, verification):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("boundary", "method", "arguments"),
    [
        (FaultBoundary.REVALIDATION, "revalidate", (None,)),
        (FaultBoundary.EXTERNAL_EFFECT, "apply", (None,)),
        (
            FaultBoundary.VERIFICATION,
            "verify",
            (None, EffectResult({"effect": "effect"})),
        ),
    ],
)
@pytest.mark.parametrize("moment", list(FaultMoment))
async def test_handler_boundaries_resume_idempotently_after_restart(
    boundary, method, arguments, moment
):
    handler = IdempotentHandler()
    if boundary is FaultBoundary.VERIFICATION:
        handler.effect_keys.add("effect")
    script = script_for(boundary, moment)
    wrapped = FaultInjectingActionHandler(handler, script)

    with pytest.raises(InjectedProcessDeath):
        await getattr(wrapped, method)(*arguments)

    restarted = FaultInjectingActionHandler(
        handler, DeterministicFaultScript.from_json(script.stable_json())
    )
    await getattr(restarted, method)(*arguments)
    if boundary is FaultBoundary.EXTERNAL_EFFECT:
        assert handler.effect_keys == {"effect"}


@pytest.mark.parametrize("moment", list(FaultMoment))
def test_native_tracker_mutation_converges_after_restart(tmp_path, moment):
    first = tracker(tmp_path)
    issue = first.create_issue(
        title="Fault injection",
        description="Actionable tracker mutation test",
        initial_status="Open",
    )
    script = script_for(FaultBoundary.TRACKER_MUTATION, moment)
    with pytest.raises(InjectedProcessDeath):
        FaultInjectingTracker(first, script).update_issue(
            issue.identifier, status="In Progress"
        )

    restarted = tracker(tmp_path)
    wrapped = FaultInjectingTracker(
        restarted, DeterministicFaultScript.from_json(script.stable_json())
    )
    wrapped.update_issue(issue.identifier, status="In Progress")
    assert restarted.fetch_issue_detail(issue.identifier).state == "In Progress"


@pytest.mark.parametrize("moment", list(FaultMoment))
def test_transition_journal_fault_is_restart_recoverable(tmp_path, moment):
    path = str(tmp_path / f"journal-{moment.value}.sqlite3")
    clock = ManualLeaseClock(100)
    first = TransitionJournal(path, clock=clock)
    script = script_for(FaultBoundary.TRANSITION_JOURNAL, moment)
    with pytest.raises(InjectedProcessDeath):
        FaultInjectingTransitionJournal(first, script).begin(
            intent(), lease_ttl_seconds=10
        )
    first.close()

    clock.advance(11)
    restarted = TransitionJournal(path, clock=clock)
    try:
        wrapped = FaultInjectingTransitionJournal(
            restarted, DeterministicFaultScript.from_json(script.stable_json())
        )
        resumed = wrapped.begin(intent(), lease_ttl_seconds=10)
        assert resumed.claim_token is not None
        assert restarted.load_intent(resumed.transition_id) == intent()
        restarted.append(
            resumed.transition_id, TransitionPhase.APPLYING, intent().reason_code
        )
        restarted.integrity_check()
    finally:
        restarted.close()


@pytest.mark.parametrize(
    "mode",
    [
        ValueFaultMode.MISSING,
        ValueFaultMode.STALE,
        ValueFaultMode.FETCH_FAILURE,
    ],
)
def test_native_tracker_snapshot_faults_are_one_shot(tmp_path, mode):
    native = tracker(tmp_path)
    issue = native.create_issue(
        title="Snapshot",
        description="Actionable snapshot fault fixture",
        initial_status="Open",
    )
    stale = replace(issue, state="Backlog")
    source = FaultedValueSource(mode, stale_value=stale)
    wrapped = FaultInjectingTracker(native, DeterministicFaultScript(), reads=source)

    if mode is ValueFaultMode.FETCH_FAILURE:
        with pytest.raises(InjectedWorkflowFailure) as raised:
            wrapped.fetch_issue_detail(issue.identifier)
        assert raised.value.retryable
    else:
        observed = wrapped.fetch_issue_detail(issue.identifier)
        assert observed is None or observed.state == "Backlog"
    assert wrapped.fetch_issue_detail(issue.identifier).state == "Open"


def test_drop_and_duplicate_events_are_deterministic_and_idempotent():
    event = {"sequence": 41, "task": "TASK-1"}
    assert EventDeliveryAdapter(EventDeliveryMode.DROP).deliver(event) == ()
    assert EventDeliveryAdapter(EventDeliveryMode.DUPLICATE).deliver(event) == (
        event,
        event,
    )
    assert EventDeliveryAdapter(EventDeliveryMode.NORMAL).deliver(event) == (event,)


def git(repo, *args):
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Fault Harness",
        "GIT_AUTHOR_EMAIL": "faults@example.invalid",
        "GIT_COMMITTER_NAME": "Fault Harness",
        "GIT_COMMITTER_EMAIL": "faults@example.invalid",
    }
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_deleted_branches_and_moving_target_heads_use_a_real_git_repo(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "value.txt").write_text("base\n")
    git(tmp_path, "add", "value.txt")
    git(tmp_path, "commit", "-m", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    git(tmp_path, "branch", "task")
    (tmp_path / "value.txt").write_text("main\n")
    git(tmp_path, "commit", "-am", "main change")
    main_head = git(tmp_path, "rev-parse", "HEAD")
    adapter = GitFaultAdapter(tmp_path)

    adapter.move_branch("task", "main")
    assert git(tmp_path, "rev-parse", "task") == main_head
    assert adapter.change_head("task", base) == base
    adapter.delete_branch("task")
    assert git(tmp_path, "branch", "--list", "task") == ""
    with pytest.raises(ValueError, match="unsafe"):
        adapter.delete_branch("--all")


def test_expired_lease_auth_policy_and_transport_failures_are_bounded(tmp_path):
    clock = ManualLeaseClock(100)
    store = WorkflowJobStore(str(tmp_path / "leases.sqlite3"), clock=clock)
    store.enqueue(spec())
    claimed = store.claim_next(lease_owner="worker", lease_seconds=10)
    clock.advance(11)
    assert store.recover_expired() == 1
    assert store.get(claimed.job_id).state is WorkflowJobState.QUEUED

    for authority in (
        AuthorityFaultAdapter(authenticated=False),
        AuthorityFaultAdapter(policy_allows=False),
    ):
        with pytest.raises(InjectedWorkflowFailure) as raised:
            authority.require()
        assert raised.value.action_required
        assert not raised.value.retryable

    transport = FaultedValueSource(ValueFaultMode.TRANSPORT_FAILURE)
    with pytest.raises(InjectedWorkflowFailure) as raised:
        transport.read("response")
    assert raised.value.retryable
    store.close()


def test_concurrent_scheduler_intents_coalesce_in_real_sqlite(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "concurrent.sqlite3"))
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = list(pool.map(lambda _: store.enqueue(spec()), range(32)))
        assert len({job.job_id for job in jobs}) == 1
        assert len(store.list_jobs()) == 1
        claimed = store.claim_next(lease_owner="winner", lease_seconds=30)
        with ThreadPoolExecutor(max_workers=8) as pool:
            losers = list(
                pool.map(
                    lambda index: store.claim_next(
                        lease_owner=f"loser-{index}", lease_seconds=30
                    ),
                    range(8),
                )
            )
        assert claimed is not None
        assert losers == [None] * 8
    finally:
        store.close()


def test_recoverable_and_unrecoverable_fault_types_have_total_disposition():
    retry = script_for(
        FaultBoundary.EXTERNAL_EFFECT,
        FaultMoment.BEFORE,
        FaultKind.RETRYABLE_EXCEPTION,
    )
    with pytest.raises(InjectedWorkflowFailure) as raised:
        retry.hit(point(FaultBoundary.EXTERNAL_EFFECT, FaultMoment.BEFORE))
    assert raised.value.retryable and not raised.value.action_required

    blocked = script_for(
        FaultBoundary.EXTERNAL_EFFECT,
        FaultMoment.BEFORE,
        FaultKind.ACTION_REQUIRED,
    )
    with pytest.raises(InjectedWorkflowFailure) as raised:
        blocked.hit(point(FaultBoundary.EXTERNAL_EFFECT, FaultMoment.BEFORE))
    assert raised.value.action_required and not raised.value.retryable


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "expected_disposition", "expected_state"),
    [
        (
            FaultKind.RETRYABLE_EXCEPTION,
            WorkflowRunDisposition.RETRY_SCHEDULED,
            WorkflowJobState.RETRY_WAIT,
        ),
        (
            FaultKind.ACTION_REQUIRED,
            WorkflowRunDisposition.ACTION_REQUIRED,
            WorkflowJobState.EXHAUSTED,
        ),
    ],
)
async def test_worker_routes_typed_external_faults_to_bounded_disposition(
    tmp_path, kind, expected_disposition, expected_state
):
    store = WorkflowJobStore(str(tmp_path / f"{kind.value}.sqlite3"))
    queued = store.enqueue(spec())
    handler = FaultInjectingActionHandler(
        IdempotentHandler(),
        script_for(FaultBoundary.REVALIDATION, FaultMoment.BEFORE, kind),
    )
    worker = DurableWorkflowWorker(
        store=store,
        handlers={"test": handler},
        transition_services={},
        worker_id="fault-worker",
        lease_seconds=30,
        heartbeat_seconds=10,
    )

    result = await worker.run_once()

    assert result.disposition is expected_disposition
    assert store.get(queued.job_id).state is expected_state
    assert not handler.handler.effect_keys
    store.close()
