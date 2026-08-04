"""Generative reference-machine coverage for composed workflow behavior."""

from __future__ import annotations

import pytest

from oompah.workflow_contract import (
    IN_PROGRESS,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    OPEN,
)
from oompah.workflow_reference_model import (
    DEFAULT_MAX_EVENTS,
    DEFAULT_MAX_TASKS,
    KNOWN_BUG_TRACES,
    EventKind,
    FaultPolicy,
    ModelEvent,
    ReferenceWorkflowModel,
    WorkflowScenarioGenerator,
    WorkflowTrace,
    known_bug_trace,
    replay_trace,
    shrink_trace,
)


def event(kind, task_id=None, **payload):
    return ModelEvent(kind, task_id, payload)


def test_trace_round_trip_and_generated_sequence_are_deterministic():
    first = WorkflowScenarioGenerator(731, max_tasks=6, max_events=60).generate()
    second = WorkflowScenarioGenerator(731, max_tasks=6, max_events=60).generate()

    assert first == second
    assert WorkflowTrace.from_json(first.stable_json()) == first
    assert len(first.events) <= 60
    assert len(first.events) >= 1


def test_generator_enforces_ci_runtime_bounds():
    bounded = WorkflowScenarioGenerator(
        1,
        max_tasks=DEFAULT_MAX_TASKS * 10,
        max_events=DEFAULT_MAX_EVENTS * 10,
    )

    assert bounded.max_tasks == DEFAULT_MAX_TASKS
    assert bounded.max_events == DEFAULT_MAX_EVENTS
    with pytest.raises(ValueError, match="bounds"):
        WorkflowScenarioGenerator(1, max_tasks=0, max_events=0)


@pytest.mark.parametrize("seed", range(64))
def test_generated_adversarial_events_preserve_safety_and_total_disposition(seed):
    trace = WorkflowScenarioGenerator(seed, max_tasks=8, max_events=100).generate()

    report = replay_trace(trace, check_eventual_progress=True)

    assert report.ok, (seed, report.violations, trace.stable_json())
    assert len(report.final_state_digest) == 64


def test_reference_machine_rejects_illegal_stale_and_unproven_transitions():
    trace = WorkflowTrace(
        10,
        (
            event(EventKind.CREATE_TASK, "TASK-1", status=OPEN),
            event(EventKind.CLAIM_OWNER, "TASK-1", owner_id="agent", generation=1),
            event(
                EventKind.TRANSITION,
                "TASK-1",
                to=IN_PROGRESS,
                expected_version=99,
                generation=1,
            ),
            event(
                EventKind.TRANSITION,
                "TASK-1",
                to=MERGED,
                expected_version=0,
                generation=1,
            ),
        ),
    )

    report = replay_trace(trace)

    assert report.accepted == 2
    assert report.rejected == 2
    assert report.ok


def test_hard_start_dependency_prevents_ownership_transition_until_complete():
    trace = WorkflowTrace(
        11,
        (
            event(EventKind.CREATE_TASK, "BLOCKER", status=OPEN),
            event(EventKind.CREATE_TASK, "TASK-1", status=OPEN),
            event(
                EventKind.SET_DEPENDENCIES,
                "TASK-1",
                hard_start=["BLOCKER"],
            ),
            event(EventKind.CLAIM_OWNER, "TASK-1", owner_id="agent", generation=1),
            event(
                EventKind.TRANSITION,
                "TASK-1",
                to=IN_PROGRESS,
                expected_version=1,
                generation=1,
            ),
        ),
    )

    report = replay_trace(trace)

    assert report.rejected == 1
    assert report.ok


def test_dependency_cycles_receive_explicit_action_disposition():
    model = ReferenceWorkflowModel()
    model.apply(event(EventKind.CREATE_TASK, "A", status=OPEN), step=0)
    model.apply(event(EventKind.CREATE_TASK, "B", status=OPEN), step=1)
    model.apply(event(EventKind.SET_DEPENDENCIES, "A", hard_start=["B"]), step=2)
    model.apply(event(EventKind.SET_DEPENDENCIES, "B", hard_start=["A"]), step=3)

    assert model.settle_after_faults_cease()
    assert model.tasks["A"].action_required_reason == "dependency_cycle"
    assert model.tasks["B"].action_required_reason == "dependency_cycle"


def test_nested_epics_and_dependencies_converge_when_faults_cease():
    trace = WorkflowTrace(
        12,
        (
            event(EventKind.CREATE_TASK, "EPIC", status=OPEN, issue_type="epic"),
            event(
                EventKind.CREATE_TASK,
                "CHILD-1",
                status=OPEN,
                parent_id="EPIC",
            ),
            event(
                EventKind.CREATE_TASK,
                "CHILD-2",
                status=OPEN,
                parent_id="EPIC",
            ),
            event(
                EventKind.SET_DEPENDENCIES,
                "CHILD-2",
                hard_start=["CHILD-1"],
            ),
            event(EventKind.FAULTS_CEASE),
        ),
    )

    report = replay_trace(trace, check_eventual_progress=True)

    assert report.ok


def test_review_audit_landing_retry_and_job_events_compose():
    model = ReferenceWorkflowModel()
    assert model.apply(event(EventKind.CREATE_TASK, "TASK-1", status=IN_REVIEW), step=0)
    assert model.apply(event(EventKind.FAULTS_CEASE), step=1)
    assert model.apply(event(EventKind.RECONCILE, "TASK-1"), step=2)
    assert model.tasks["TASK-1"].status == IN_VALIDATION
    assert model.apply(event(EventKind.RECONCILE, "TASK-1"), step=3)
    assert model.tasks["TASK-1"].status == MERGED

    assert model.apply(event(EventKind.CREATE_TASK, "TASK-2", status=OPEN), step=4)
    assert model.apply(
        event(
            EventKind.SCHEDULE_RETRY,
            "TASK-2",
            generation=1,
            action="review_refresh",
        ),
        step=5,
    )
    job_id = "TASK-2:1:review_refresh"
    assert model.apply(
        event(EventKind.CLAIM_JOB, "TASK-2", job_id=job_id, generation=1),
        step=6,
    )
    assert model.apply(
        event(EventKind.COMPLETE_JOB, "TASK-2", job_id=job_id, generation=1),
        step=7,
    )
    assert not model.tasks["TASK-2"].retry_due


def test_ownership_generation_rotation_fences_stale_callbacks_and_jobs():
    trace = WorkflowTrace(
        14,
        (
            event(EventKind.CREATE_TASK, "TASK-1", status=OPEN),
            event(EventKind.CLAIM_OWNER, "TASK-1", owner_id="old", generation=1),
            event(EventKind.SCHEDULE_RETRY, "TASK-1", generation=1),
            event(EventKind.ROTATE_GENERATION, "TASK-1"),
            event(
                EventKind.CALLBACK,
                "TASK-1",
                to=IN_PROGRESS,
                expected_version=0,
                generation=1,
            ),
            event(
                EventKind.CLAIM_JOB,
                "TASK-1",
                job_id="TASK-1:1:reconcile",
                generation=1,
            ),
        ),
    )

    report = replay_trace(trace)

    assert report.rejected == 2
    assert report.ok


@pytest.mark.parametrize("name", sorted(KNOWN_BUG_TRACES))
def test_seeded_known_bug_mutations_are_detected(name):
    trace, policy, expected = known_bug_trace(name)

    report = replay_trace(trace, policy=policy)

    assert expected in report.violation_codes


def test_correct_policy_fences_seeded_bug_callbacks_and_retries():
    for name in sorted(KNOWN_BUG_TRACES):
        trace, _, _ = known_bug_trace(name)
        report = replay_trace(trace, policy=FaultPolicy())
        assert report.ok, (name, report.violations)


def test_failure_trace_shrinking_is_replayable_and_one_minimal():
    bug, policy, expected = known_bug_trace("duplicate_owner")
    noisy = WorkflowTrace(
        bug.seed,
        (
            event(EventKind.TICK, amount=3),
            *bug.events,
            event(EventKind.TICK, amount=9),
            event(EventKind.CREATE_TASK, "UNRELATED", status=OPEN),
        ),
    )

    def fails(candidate):
        return expected in replay_trace(candidate, policy=policy).violation_codes

    minimal = shrink_trace(noisy, fails=fails)

    assert fails(minimal)
    assert WorkflowTrace.from_json(minimal.stable_json()) == minimal
    for index in range(len(minimal.events)):
        candidate = WorkflowTrace(
            minimal.seed,
            minimal.events[:index] + minimal.events[index + 1 :],
        )
        assert not candidate.events or not fails(candidate)


def test_shrinker_rejects_nonfailing_input():
    trace = WorkflowTrace(
        13,
        (event(EventKind.CREATE_TASK, "TASK-1", status=OPEN),),
    )

    with pytest.raises(ValueError, match="does not satisfy"):
        shrink_trace(trace, fails=lambda candidate: not replay_trace(candidate).ok)
