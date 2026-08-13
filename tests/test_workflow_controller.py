"""Totality, liveness, and restart convergence for the universal controller."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest

from oompah.integration import IntegrationRecord
from oompah.models import BlockerRef, Issue
from oompah.statuses import IN_REVIEW
from oompah.work_decision import PermittedAction
from oompah.workflow_controller import (
    UniversalTotalityLivenessController,
    WorkflowProjectionPublicationRejected,
)
from oompah.workflow_contract import (
    CANONICAL_STATUSES,
    LIFECYCLE_FINAL_STATUSES,
    TaskDisposition,
    WorkflowOwner,
)
from oompah.workflow_facts import (
    FactDomain,
    FactObservation,
    FactState,
    REQUIRED_FACT_DOMAINS,
    WorkflowFacts,
)
from oompah.workflow_jobs import (
    WorkflowFailureCategory,
    WorkflowJobSpec,
    WorkflowJobState,
    WorkflowJobStore,
    WorkflowJobStoreError,
)
from oompah.workflow_reasons import AlertSeverity
from oompah.workflow_scheduler import WorkflowJobScheduler, WorkflowReconcileResult


NOW = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


def issue(status: str = "Open", *, identifier: str = "TASK-1", **overrides) -> Issue:
    values = {
        "id": identifier,
        "identifier": identifier,
        "title": identifier,
        "state": status,
        "project_id": "project-a",
        "issue_type": "task",
    }
    values.update(overrides)
    return Issue(**values)


def known(domain: FactDomain, value, *, at: str = NOW_ISO):
    return FactObservation.known(domain, value, observed_at=at, source="test")


def facts_for(
    task: Issue,
    *,
    at: str = NOW_ISO,
    overrides: dict[FactDomain, FactObservation] | None = None,
) -> WorkflowFacts:
    values = {
        FactDomain.TASK: {
            "identifier": task.identifier,
            "project_id": task.project_id,
            "status": task.state,
        },
        FactDomain.DEPENDENCIES: {"finish": [], "hard_start": []},
        FactDomain.CONTAINMENT: {"children": []},
        FactDomain.INTEGRATION: {"state": "none"},
        FactDomain.TERMINAL_AUDIT: {"phase": "none"},
        FactDomain.REVIEW_CI: {"ci": "passed", "mergeable": True},
        FactDomain.LANDING: {"evidence_revisions": []},
        FactDomain.IMPLEMENTATION_AUTHORITY: {
            "lease_expires_at": (NOW + timedelta(minutes=5)).isoformat(),
            "owner_id": "worker-1",
        },
        FactDomain.DUPLICATE_INVESTIGATION: {
            "lease_expires_at": (NOW + timedelta(minutes=5)).isoformat(),
            "owner_id": "duplicate-worker-1",
        },
        FactDomain.RETRY_BUDGET: {"attempts": 0, "max_attempts": 5},
        FactDomain.CONFIG: {},
    }
    observations = {
        domain: known(domain, value, at=at) for domain, value in values.items()
    }
    observations.update(overrides or {})
    return WorkflowFacts(
        str(task.project_id), task.identifier, at, observations
    )


def fact_map(*tasks: Issue, at: str = NOW_ISO, overrides=None):
    return {
        (str(task.project_id), task.identifier): facts_for(
            task, at=at, overrides=(overrides or {}).get(task.identifier)
        )
        for task in tasks
    }


@pytest.fixture
def controller(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "controller.sqlite3"))
    value = UniversalTotalityLivenessController(
        store=store, decision_limit=100, clock=lambda: NOW
    )
    yield value
    store.close()


def test_every_nonfinal_status_has_exactly_one_allowed_disposition(controller):
    tasks = tuple(
        issue(status, identifier=f"TASK-{number}")
        for number, status in enumerate(CANONICAL_STATUSES, start=1)
        if status not in LIFECYCLE_FINAL_STATUSES
    )
    decisions = controller.evaluate(tasks, facts=fact_map(*tasks), now=NOW)

    assert len(decisions) == len(tasks)
    assert {item.task_id for item in decisions} == {item.identifier for item in tasks}
    assert all(
        item.disposition
        in {
            TaskDisposition.RUNNABLE,
            TaskDisposition.OWNED,
            TaskDisposition.BLOCKED,
            TaskDisposition.RETRY_SCHEDULED,
            TaskDisposition.ACTION_REQUIRED,
            TaskDisposition.TERMINAL,
        }
        for item in decisions
    )
    assert all(item.reason_code and item.evidence_revision for item in decisions)


def test_exhausted_current_semantic_job_escalates_on_reevaluation(controller):
    task = issue("In Progress", identifier="TASK-EXHAUSTED")
    facts = facts_for(
        task,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY, {}
            )
        },
    )
    first = controller.full_sync((task,), facts={task.identifier: facts})
    assert first.decisions[0].durable_jobs == ("implementation_recovery",)
    running = controller.store.claim_next(
        lease_owner="failed-worker", lease_seconds=30
    )
    assert running is not None
    exhausted = controller.store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="permanent failure",
        retryable=False,
    )
    assert exhausted.state is WorkflowJobState.EXHAUSTED

    decision = controller.evaluate(
        (task,), facts={task.identifier: facts}, now=NOW
    )[0]

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.reason_code == "retry.exhausted"
    assert decision.durable_jobs == ()


def test_accepted_submission_replaces_exhausted_implementation_action(controller):
    task = issue("Open", identifier="TASK-SUBMITTED-AFTER-EXHAUSTION")
    initial_facts = facts_for(task)
    first = controller.full_sync(
        (task,), facts={task.identifier: initial_facts}, now=NOW
    )
    assert first.decisions[0].durable_jobs == ("implementation_start",)
    running = controller.store.claim_next(
        lease_owner="failed-implementation", lease_seconds=30
    )
    assert running is not None
    controller.store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="obsolete implementation failure",
        retryable=False,
    )

    submitted_facts = facts_for(
        task,
        at=(NOW + timedelta(seconds=1)).isoformat(),
        overrides={
            FactDomain.CONFIG: known(
                FactDomain.CONFIG,
                {
                    "implementation_pending_action": "validation_submission",
                    "accepted_submission_recovery_state": (
                        "accepted_submission_exact"
                    ),
                },
                at=(NOW + timedelta(seconds=1)).isoformat(),
            )
        },
    )
    recovered = controller.full_sync(
        (task,),
        facts={task.identifier: submitted_facts},
        now=NOW + timedelta(seconds=1),
    )

    assert recovered.decisions[0].reason_code == "implementation.action_scheduled"
    assert recovered.decisions[0].durable_jobs == ("validation_submission",)
    current = controller.store.list_jobs(
        task_id=task.identifier,
        states=(WorkflowJobState.QUEUED,),
    )
    assert [job.action for job in current] == ["validation_submission"]


def test_zero_job_cut_retires_exhaustion_only_after_successful_publish(controller):
    active = issue("In Progress", identifier="TASK-ZERO-CUT")
    active_facts = facts_for(
        active,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY, {}
            )
        },
    )
    first = controller.full_sync(
        (active,), facts={active.identifier: active_facts}, now=NOW
    )
    assert first.decisions[0].durable_jobs == ("implementation_recovery",)
    running = controller.store.claim_next(
        lease_owner="failed-worker", lease_seconds=30
    )
    assert running is not None
    exhausted = controller.store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="permanent failure",
        retryable=False,
    )

    backlog = issue("Backlog", identifier=active.identifier)
    backlog_facts = facts_for(backlog)
    read_only = controller.evaluate(
        (backlog,), facts={backlog.identifier: backlog_facts}, now=NOW
    )[0]
    assert read_only.reason_code == "retry.exhausted"

    generation = controller.begin_scan()

    def fail_persist(_state):
        raise OSError("publication unavailable")

    with pytest.raises(OSError, match="publication unavailable"):
        controller.full_sync(
            (backlog,),
            facts={backlog.identifier: backlog_facts},
            now=NOW + timedelta(seconds=1),
            snapshot_generation=generation,
            persist_liveness_state=fail_persist,
        )

    assert controller.store.current_exhausted_jobs(
        project_id="project-a", task_id=backlog.identifier
    ) == (exhausted,)
    assert controller.store.health_snapshot()["current_states"]["exhausted"] == 1

    published = controller.full_sync(
        (backlog,),
        facts={backlog.identifier: backlog_facts},
        now=NOW + timedelta(seconds=2),
    )
    assert published.decisions[0].reason_code == "prioritization.awaiting_owner"
    assert published.decisions[0].durable_jobs == ()
    assert not controller.store.current_exhausted_jobs(
        project_id="project-a", task_id=backlog.identifier
    )
    assert controller.store.health_snapshot()["current_states"]["exhausted"] == 0


def test_same_required_action_keeps_current_exhaustion_actionable(controller):
    task = issue("In Progress", identifier="TASK-SAME-ACTION")
    facts = facts_for(
        task,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY, {}
            )
        },
    )
    controller.full_sync((task,), facts={task.identifier: facts}, now=NOW)
    running = controller.store.claim_next(
        lease_owner="failed-worker", lease_seconds=30
    )
    assert running is not None
    exhausted = controller.store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="permanent failure",
        retryable=False,
    )

    repeated = controller.full_sync(
        (task,),
        facts={task.identifier: facts},
        now=NOW + timedelta(seconds=1),
    )

    assert repeated.decisions[0].reason_code == "retry.exhausted"
    assert controller.store.current_exhausted_jobs(
        project_id="project-a", task_id=task.identifier
    ) == (exhausted,)


def test_action_required_zero_job_cut_retires_unrelated_exhaustion(controller):
    active = issue("In Progress", identifier="TASK-OPERATOR-CUT")
    active_facts = facts_for(
        active,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY, {}
            )
        },
    )
    controller.full_sync(
        (active,), facts={active.identifier: active_facts}, now=NOW
    )
    running = controller.store.claim_next(
        lease_owner="failed-worker", lease_seconds=30
    )
    assert running is not None
    controller.store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="implementation recovery failed",
        retryable=False,
    )

    needs_human = issue("Needs Human", identifier=active.identifier)
    needs_human_facts = facts_for(needs_human)
    result = controller.full_sync(
        (needs_human,),
        facts={needs_human.identifier: needs_human_facts},
        now=NOW + timedelta(seconds=1),
    )

    assert result.decisions[0].reason_code == "operator.action_required"
    assert result.decisions[0].durable_jobs == ()
    assert not controller.store.current_exhausted_jobs(
        project_id="project-a", task_id=needs_human.identifier
    )


def test_full_sync_retires_terminal_epic_cleanup_exhaustion(controller):
    terminal = issue(
        "Merged",
        identifier="EPIC-FINAL-CLEANUP",
        issue_type="epic",
    )
    cleanup = controller.store.materialize_event(
        project_id="project-a",
        task_id=terminal.identifier,
        decision_revision="cleanup-generation",
        action="epic_cleanup",
        idempotency_namespace="epic-cleanup",
        scheduling_lane="epic-event:epic_cleanup",
    )
    assert cleanup.job is not None
    running = controller.store.claim_next(
        lease_owner="failed-worker", lease_seconds=30
    )
    assert running is not None
    controller.store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="cleanup failed permanently",
        retryable=False,
    )
    assert len(
        controller.store.current_exhausted_jobs(
            project_id="project-a", task_id=terminal.identifier
        )
    ) == 1

    result = controller.full_sync(
        (terminal,), facts={}, now=NOW + timedelta(seconds=1)
    )

    assert result.decisions == ()
    assert not controller.store.current_exhausted_jobs(
        project_id="project-a", task_id=terminal.identifier
    )
    assert controller.store.health_snapshot()["current_states"]["exhausted"] == 0


def test_conflicting_lifecycle_cut_keeps_exhaustion_actionable(controller):
    active = issue("In Progress", identifier="TASK-CONFLICTING-FINAL")
    active_facts = facts_for(
        active,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY, {}
            )
        },
    )
    controller.full_sync(
        (active,), facts={active.identifier: active_facts}, now=NOW
    )
    running = controller.store.claim_next(
        lease_owner="failed-worker", lease_seconds=30
    )
    assert running is not None
    exhausted = controller.store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="permanent failure",
        retryable=False,
    )
    terminal = issue("Merged", identifier=active.identifier)

    result = controller.full_sync(
        (terminal, active),
        facts={active.identifier: active_facts},
        now=NOW + timedelta(seconds=1),
    )

    assert result.decisions[0].reason_code == "evidence.conflicting_task_facts"
    assert controller.store.current_exhausted_jobs(
        project_id="project-a", task_id=active.identifier
    ) == (exhausted,)


def test_current_exhaustion_survives_revision_drift_and_restart_until_replaced(
    tmp_path,
):
    database = tmp_path / "controller-restart.sqlite3"
    task = issue("In Progress", identifier="TASK-EXHAUSTED-DRIFT")
    initial_facts = facts_for(
        task,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY, {}
            ),
            FactDomain.CONFIG: known(FactDomain.CONFIG, {"revision": 1}),
        },
    )
    changed_facts = facts_for(
        task,
        at=(NOW + timedelta(seconds=1)).isoformat(),
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {},
                at=(NOW + timedelta(seconds=1)).isoformat(),
            ),
            FactDomain.CONFIG: known(
                FactDomain.CONFIG,
                {"revision": 2},
                at=(NOW + timedelta(seconds=1)).isoformat(),
            ),
        },
    )
    assert changed_facts.facts_version != initial_facts.facts_version

    store = WorkflowJobStore(str(database))
    first_controller = UniversalTotalityLivenessController(
        store=store, decision_limit=100, clock=lambda: NOW
    )
    first = first_controller.full_sync(
        (task,), facts={task.identifier: initial_facts}, now=NOW
    )
    first_cursor = store.schedule_cursor(
        project_id="project-a", task_id=task.identifier
    )
    assert first_cursor is not None
    assert first_cursor.decision_revision == (
        first_controller.scheduler.decision_revision(first.decisions[0])
    )
    running = store.claim_next(
        lease_owner="failed-worker", lease_seconds=30
    )
    assert running is not None
    store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.PERMANENT,
        error="permanent failure",
        retryable=False,
    )

    drifted = first_controller.evaluate(
        (task,), facts={task.identifier: changed_facts}, now=NOW
    )[0]
    assert drifted.disposition is TaskDisposition.ACTION_REQUIRED
    assert drifted.reason_code == "retry.exhausted"
    assert drifted.action_required
    assert drifted.alert_level is AlertSeverity.CRITICAL
    assert store.health_snapshot()["current_states"]["exhausted"] == 1
    store.close()

    reopened_store = WorkflowJobStore(str(database))
    restarted = UniversalTotalityLivenessController(
        store=reopened_store, decision_limit=100, clock=lambda: NOW
    )
    after_restart = restarted.evaluate(
        (task,), facts={task.identifier: changed_facts}, now=NOW
    )[0]
    assert after_restart.reason_code == "retry.exhausted"
    assert after_restart.action_required
    assert len(
        reopened_store.current_exhausted_jobs(
            project_id="project-a", task_id=task.identifier
        )
    ) == reopened_store.health_snapshot()["current_states"]["exhausted"] == 1

    replacement_snapshot = reopened_store.allocate_snapshot_generation()
    assert reopened_store.accept_snapshot_generation(replacement_snapshot)
    replacement_cursor = reopened_store.activate_schedule(
        project_id="project-a",
        task_id=task.identifier,
        decision_revision="replacement-decision",
        snapshot_generation=replacement_snapshot,
    )
    assert reopened_store.reconcile_schedule(
        project_id="project-a",
        task_id=task.identifier,
        snapshot_generation=replacement_snapshot,
        job_generation=replacement_cursor.job_generation,
        specs=(
            WorkflowJobSpec(
                project_id="project-a",
                task_id=task.identifier,
                generation=replacement_cursor.job_generation,
                action="parent_rollup_review",
                idempotency_key="replacement:changed-action",
            ),
        ),
    ).accepted

    recovered = restarted.evaluate(
        (task,), facts={task.identifier: changed_facts}, now=NOW
    )[0]
    assert recovered.reason_code == "retry.exhausted"
    published, _result = reopened_store.publish_snapshot_generation(
        replacement_snapshot, lambda: None
    )
    assert published
    recovered = restarted.evaluate(
        (task,), facts={task.identifier: changed_facts}, now=NOW
    )[0]
    assert recovered.reason_code == "implementation.recovery_scheduled"
    assert not recovered.action_required
    assert not reopened_store.current_exhausted_jobs(
        project_id="project-a", task_id=task.identifier
    )
    assert reopened_store.health_snapshot()["current_states"]["exhausted"] == 0
    reopened_store.close()


def _review_generation_facts(
    task: Issue,
    *,
    repositories: bool,
    review_overrides: dict | None = None,
    integration_overrides: dict | None = None,
    exhausted: bool = False,
) -> WorkflowFacts:
    review = {
        "state": "open",
        "present": True,
        "review_id": "17",
        "source_branch": "TASK-REVIEW-GENERATION",
        "target_branch": "main",
        "head_sha": "a" * 40,
        "base_sha": "b" * 40,
        "ci": "passed",
        "mergeable": True,
        "conflict": False,
        "needs_rebase": False,
    }
    if repositories:
        review.update(
            {
                "source_repository": "owner/repo",
                "target_repository": "owner/repo",
            }
        )
    review.update(review_overrides or {})
    integration = {
        "state": "ready",
        "mode": "standalone",
        "task_branch": "TASK-REVIEW-GENERATION",
        "base_branch": "main",
        "base_sha": "b" * 40,
        "head_sha": "a" * 40,
    }
    integration.update(integration_overrides or {})
    return facts_for(
        task,
        overrides={
            FactDomain.TASK: known(
                FactDomain.TASK,
                {
                    "identifier": task.identifier,
                    "project_id": task.project_id,
                    "status": task.state,
                    "work_branch": task.work_branch,
                    "target_branch": task.target_branch,
                    "review_number": task.review_number,
                    "review_head": task.review_head,
                    "head_sha": task.head_sha,
                },
            ),
            FactDomain.INTEGRATION: known(FactDomain.INTEGRATION, integration),
            FactDomain.REVIEW_CI: known(FactDomain.REVIEW_CI, review),
            FactDomain.RETRY_BUDGET: known(
                FactDomain.RETRY_BUDGET,
                (
                    {"attempts": 5, "max_attempts": 5, "exhausted": True}
                    if exhausted
                    else {"remaining": 5}
                ),
            ),
        },
    )


def test_exact_review_identity_enrichment_rearms_stale_generation_after_restart(
    tmp_path,
):
    database = tmp_path / "review-generation-restart.sqlite3"
    task = issue(
        IN_REVIEW,
        identifier="TASK-REVIEW-GENERATION",
        work_branch="TASK-REVIEW-GENERATION",
        target_branch="main",
        review_number="17",
        review_head="a" * 40,
        head_sha="a" * 40,
        integration=IntegrationRecord(
            state="ready",
            mode="standalone",
            task_branch="TASK-REVIEW-GENERATION",
            base_branch="main",
            base_sha="b" * 40,
            head_sha="a" * 40,
        ),
    )
    initial = _review_generation_facts(task, repositories=False)
    store = WorkflowJobStore(str(database))
    controller = UniversalTotalityLivenessController(
        store=store, decision_limit=100, clock=lambda: NOW
    )
    first = controller.full_sync(
        (task,), facts={task.identifier: initial}, now=NOW
    )
    assert first.decisions[0].durable_jobs == ("review_merge",)
    running = store.claim_next(lease_owner="old-review-worker", lease_seconds=30)
    assert running is not None
    exhausted_job = store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.STALE_EVIDENCE,
        error="review identity was incomplete",
        retryable=False,
    )
    store.close()

    current = _review_generation_facts(
        task,
        repositories=True,
    )
    reopened = WorkflowJobStore(str(database))
    restarted = UniversalTotalityLivenessController(
        store=reopened, decision_limit=100, clock=lambda: NOW
    )
    try:
        read_only = restarted.evaluate(
            (task,), facts={task.identifier: current}, now=NOW
        )[0]
        assert read_only.reason_code == "retry.exhausted"

        regenerated = restarted.full_sync(
            (task,), facts={task.identifier: current}, now=NOW
        )
        repeated = restarted.full_sync(
            (task,), facts={task.identifier: current}, now=NOW
        )

        assert regenerated.decisions[0].reason_code == "review.ready_to_merge"
        assert repeated.decisions[0].reason_code == "review.ready_to_merge"
        active = [job for job in reopened.list_jobs() if job.is_active]
        assert [job.action for job in active] == ["review_merge"]
        assert active[0].expected_evidence_revision == current.facts_version
        assert reopened.get(exhausted_job.job_id).state is WorkflowJobState.EXHAUSTED
        assert not reopened.current_exhausted_jobs(
            project_id="project-a", task_id=task.identifier
        )
        assert reopened.health_snapshot()["current_states"]["exhausted"] == 0
    finally:
        reopened.close()


def test_review_successor_uses_one_immutable_exhaustion_snapshot(
    tmp_path,
    monkeypatch,
):
    """A concurrent exhaustion cannot replace the rows a proof evaluated."""

    task = issue(
        IN_REVIEW,
        identifier="TASK-REVIEW-GENERATION",
        work_branch="TASK-REVIEW-GENERATION",
        target_branch="main",
        review_number="17",
        review_head="a" * 40,
        head_sha="a" * 40,
    )
    store = WorkflowJobStore(str(tmp_path / "review-generation-snapshot.sqlite3"))
    controller = UniversalTotalityLivenessController(
        store=store, decision_limit=100, clock=lambda: NOW
    )
    initial = _review_generation_facts(task, repositories=False)
    controller.full_sync((task,), facts={task.identifier: initial}, now=NOW)
    running = store.claim_next(lease_owner="old-review-worker", lease_seconds=30)
    assert running is not None
    stale_exhaustion = store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.STALE_EVIDENCE,
        error="review identity was incomplete",
        retryable=False,
    )
    current = _review_generation_facts(task, repositories=True)
    substituted_exhaustion = replace(
        stale_exhaustion,
        job_id="concurrent-current-generation-exhaustion",
        generation="concurrent-current-generation",
        expected_evidence_revision=current.facts_version,
    )
    reads = 0

    def substitute_after_first_read(*, project_id, task_id):
        nonlocal reads
        assert (project_id, task_id) == ("project-a", task.identifier)
        reads += 1
        # The second value models a current-generation worker exhausting
        # between successor proof and ordinary exhaustion handling.  It must
        # not be consulted under proof derived from the first value.
        return (
            (stale_exhaustion,)
            if reads == 1
            else (substituted_exhaustion,)
        )

    monkeypatch.setattr(
        store,
        "current_exhausted_jobs",
        substitute_after_first_read,
    )
    try:
        result = controller.full_sync(
            (task,), facts={task.identifier: current}, now=NOW
        )

        assert reads == 1
        assert result.decisions[0].reason_code == "review.ready_to_merge"
        assert [job.action for job in store.list_jobs() if job.is_active] == [
            "review_merge"
        ]
    finally:
        store.close()


@pytest.mark.parametrize(
    ("review_overrides", "integration_overrides"),
    [
        (
            {
                "source_repository": "fork/repo",
                "target_repository": "owner/repo",
            },
            {},
        ),
        ({"source_branch": "OTHER-BRANCH"}, {}),
        ({}, {"base_branch": "release"}),
        ({"conflict": True}, {}),
        ({"state": "missing", "present": False}, {}),
        ({"provider_error": True}, {}),
    ],
    ids=[
        "forked",
        "wrong-source",
        "wrong-base",
        "conflict",
        "missing",
        "provider-error",
    ],
)
def test_invalid_review_evidence_cannot_rearm_stale_exhaustion(
    tmp_path,
    review_overrides,
    integration_overrides,
):
    task = issue(
        IN_REVIEW,
        identifier="TASK-REVIEW-GENERATION",
        work_branch="TASK-REVIEW-GENERATION",
        target_branch="main",
        review_number="17",
        review_head="a" * 40,
        head_sha="a" * 40,
    )
    store = WorkflowJobStore(str(tmp_path / "invalid-review-generation.sqlite3"))
    controller = UniversalTotalityLivenessController(
        store=store, decision_limit=100, clock=lambda: NOW
    )
    initial = _review_generation_facts(task, repositories=False)
    controller.full_sync((task,), facts={task.identifier: initial}, now=NOW)
    running = store.claim_next(lease_owner="old-review-worker", lease_seconds=30)
    assert running is not None
    exhausted_job = store.fail(
        running.job_id,
        running.lease_token,
        category=WorkflowFailureCategory.STALE_EVIDENCE,
        error="review identity was incomplete",
        retryable=False,
    )
    provider_error = review_overrides.get("provider_error") is True
    review_values = {
        key: value
        for key, value in review_overrides.items()
        if key != "provider_error"
    }
    invalid = _review_generation_facts(
        task,
        repositories=True,
        review_overrides=review_values,
        integration_overrides=integration_overrides,
        exhausted=True,
    )
    if provider_error:
        observations = dict(invalid.observations)
        observations[FactDomain.REVIEW_CI] = FactObservation.error(
            FactDomain.REVIEW_CI,
            observed_at=NOW_ISO,
            source="forge",
            error_code="provider_unavailable",
        )
        invalid = WorkflowFacts(
            invalid.project_id,
            invalid.task_id,
            invalid.collected_at,
            observations,
        )
    try:
        result = controller.full_sync(
            (task,), facts={task.identifier: invalid}, now=NOW
        )

        assert result.decisions[0].reason_code == "retry.exhausted"
        assert controller.store.current_exhausted_jobs(
            project_id="project-a", task_id=task.identifier
        ) == (exhausted_job,)
        assert not [job for job in store.list_jobs() if job.is_active]
    finally:
        store.close()


def test_full_sync_updates_authoritative_liveness_projection(controller):
    task = issue("Open")

    result = controller.full_sync((task,), facts=fact_map(task), now=NOW)
    health = controller.liveness_snapshot()

    assert result.decisions[0].reason_code == "dispatch.eligible"
    assert health.healthy
    assert health.scan_complete
    assert health.tasks[0].decision_revision == result.decisions[0].decision_revision
    assert health.tasks[0].responsible_owner == "dispatcher"
    assert (
        health.tasks[0].next_reassessment_at
        == result.decisions[0].next_reassessment_at
    )


def test_runtime_observation_rejects_stale_generation_without_liveness_write(
    controller,
):
    task = issue("Open")
    generation = controller.store.allocate_snapshot_generation()
    assert controller.store.accept_snapshot_generation(generation)
    observation = controller.prepare_runtime_observation(
        (task,),
        facts_by_task=fact_map(task),
        snapshot_generation=generation,
        now=NOW,
    )
    assert observation is not None
    prior = controller.liveness_state()
    newer = controller.store.allocate_snapshot_generation()
    assert controller.store.accept_snapshot_generation(newer)
    reconciliation = WorkflowReconcileResult(
        generation,
        True,
        1,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        False,
    )

    with pytest.raises(
        WorkflowProjectionPublicationRejected,
        match="stale_runtime_observation",
    ):
        controller.stage_runtime_observation(
            observation, reconciliation=reconciliation
        )

    assert controller.liveness_state() == prior
    assert controller.health_snapshot()["controller"]["passes"] == 0
    controller.abort_runtime_observation(generation)


def test_controller_rejects_scheduler_with_a_separate_durable_store(tmp_path):
    controller_store = WorkflowJobStore(str(tmp_path / "controller.sqlite3"))
    scheduler_store = WorkflowJobStore(str(tmp_path / "scheduler.sqlite3"))
    scheduler = WorkflowJobScheduler(store=scheduler_store)
    try:
        with pytest.raises(ValueError, match="must share one workflow job store"):
            UniversalTotalityLivenessController(
                store=controller_store,
                scheduler=scheduler,
            )
    finally:
        controller_store.close()
        scheduler_store.close()


def test_incomplete_source_scan_cannot_report_liveness_healthy(controller):
    task = issue("Open")

    result = controller.full_sync(
        (task,),
        facts=fact_map(task),
        now=NOW,
        source_scan_complete=False,
    )
    health = controller.liveness_snapshot()

    assert result.truncated
    assert not health.scan_complete
    assert health.status == "incomplete"


def test_scheduler_truncation_with_required_jobs_fails_liveness_closed(tmp_path):
    store = WorkflowJobStore(str(tmp_path / "bounded-controller.sqlite3"))
    bounded = UniversalTotalityLivenessController(
        store=store,
        decision_limit=1,
        liveness_max_task_records=3,
        clock=lambda: NOW,
    )
    tasks = (
        issue("In Validation", identifier="TASK-1"),
        issue("In Validation", identifier="TASK-2"),
    )
    try:
        result = bounded.full_sync(tasks, facts=fact_map(*tasks), now=NOW)
        health = bounded.liveness_snapshot()

        assert len(result.decisions) == 2
        assert result.reconciliation.truncated
        assert health.snapshot_generation == result.snapshot_generation
        assert not health.scan_complete
        assert health.status == "incomplete"
        assert result.reconciliation.jobs_required == 2
        assert result.reconciliation.jobs_materialized == 1
        assert health.required_recovery_count == 2
        assert health.materialized_recovery_count == 1
        assert health.tracked_task_count == 2
        assert {item.task_id for item in health.tasks} == {"TASK-1", "TASK-2"}

        converged = bounded.full_sync(
            tasks, facts=fact_map(*tasks), now=NOW
        )
        converged_health = bounded.liveness_snapshot()

        assert converged.reconciliation.jobs_required == 2
        assert converged.reconciliation.jobs_materialized == 2
        assert converged.reconciliation.schedules_required == 2
        assert converged.reconciliation.schedules_materialized == 2
        assert converged_health.reconciliation_complete
        assert converged_health.scan_complete
        assert converged_health.healthy
    finally:
        store.close()


def test_concurrent_newer_empty_snapshot_rejects_slow_controller_before_publish(
    controller,
):
    slow_task = issue("In Validation", identifier="TASK-stale")
    slow_generation = controller.begin_scan()
    evaluator_started = Event()
    release_evaluator = Event()
    persisted_generations: list[int] = []

    def slow_facts(_task):
        evaluator_started.set()
        assert release_evaluator.wait(timeout=2)
        return facts_for(slow_task)

    def persist(state):
        persisted_generations.append(state["accepted_snapshot_generation"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        future = pool.submit(
            controller.full_sync,
            (slow_task,),
            facts=slow_facts,
            snapshot_generation=slow_generation,
            persist_liveness_state=persist,
        )
        assert evaluator_started.wait(timeout=2)
        newer_generation = controller.begin_scan()
        newer = controller.full_sync(
            (),
            facts={},
            snapshot_generation=newer_generation,
            persist_liveness_state=persist,
        )
        release_evaluator.set()
        stale = future.result(timeout=2)

    health = controller.liveness_snapshot()
    controller_health = controller.health_snapshot()["controller"]
    assert newer.accepted
    assert not stale.accepted
    assert stale.decisions == ()
    assert controller.store.list_jobs() == ()
    assert health.snapshot_generation == newer_generation
    assert health.tasks == ()
    assert persisted_generations == [newer_generation]
    assert controller_health["passes"] == 1
    assert controller_health["evaluated"] == 0
    assert controller_health["last_pass_generation"] == newer_generation


def test_terminal_task_in_newer_full_snapshot_retires_published_recovery(controller):
    active = issue("In Validation", identifier="TASK-terminal")
    first = controller.full_sync(
        (active,),
        facts=fact_map(active),
        now=NOW,
    )
    jobs = controller.store.list_jobs(task_id=active.identifier)

    assert first.reconciliation.jobs_created == 1
    assert len(jobs) == 1

    terminal = issue("Merged", identifier=active.identifier)
    second = controller.full_sync(
        (terminal,),
        facts={},
        now=NOW + timedelta(seconds=1),
    )

    assert second.reconciliation.jobs_superseded == 1
    assert controller.store.get(jobs[0].job_id).state is WorkflowJobState.SUPERSEDED
    assert controller.store.schedule_cursor(
        project_id="project-a", task_id=active.identifier
    ) is None
    assert controller.store.snapshot_membership() == ()


def test_failed_project_source_retains_its_durable_membership_and_jobs(controller):
    project_a = issue("In Validation", identifier="TASK-a")
    project_b = issue(
        "In Validation",
        identifier="TASK-b",
        project_id="project-b",
    )
    first = controller.full_sync(
        (project_a, project_b),
        facts=fact_map(project_a, project_b),
        authoritative_project_ids=("project-a", "project-b"),
        now=NOW,
    )
    project_b_job = controller.store.list_jobs(
        project_id="project-b", task_id="TASK-b"
    )[0]

    second = controller.full_sync(
        (project_a,),
        facts=fact_map(project_a),
        source_scan_complete=False,
        source_errors={"project-b": "TimeoutError"},
        authoritative_project_ids=("project-a",),
        now=NOW + timedelta(seconds=1),
    )
    membership = controller.store.snapshot_membership()

    assert first.reconciliation.jobs_created == 2
    assert second.reconciliation.jobs_superseded == 0
    assert controller.store.get(project_b_job.job_id).state is WorkflowJobState.QUEUED
    assert controller.store.schedule_cursor(
        project_id="project-b", task_id="TASK-b"
    ) is not None
    assert {(project_id, task_id) for project_id, task_id, _generation in membership} == {
        ("project-a", "TASK-a"),
        ("project-b", "TASK-b"),
    }


def test_versioned_scan_failure_cannot_overwrite_newer_persisted_success(
    controller,
):
    persisted_generations: list[int] = []

    def persist(state):
        persisted_generations.append(state["accepted_snapshot_generation"])

    failed_generation = controller.begin_scan()
    failed = controller.record_liveness_scan_failure(
        "TimeoutError",
        snapshot_generation=failed_generation,
        persist_liveness_state=persist,
    )
    success_generation = controller.begin_scan()
    controller.full_sync(
        (),
        facts={},
        snapshot_generation=success_generation,
        persist_liveness_state=persist,
    )
    before_stale_failure = controller.liveness_snapshot().to_dict()
    rejected = controller.record_liveness_scan_failure(
        "OldTimeoutError",
        snapshot_generation=failed_generation,
        persist_liveness_state=persist,
    )

    assert failed.snapshot_generation == failed_generation
    assert rejected.to_dict() == before_stale_failure
    assert persisted_generations == [failed_generation, success_generation]


def test_publish_failure_rolls_back_observe_before_versioned_failure_commit(
    controller,
):
    existing = issue("In Validation", identifier="TASK-existing")
    added = issue("In Validation", identifier="TASK-added")
    controller.full_sync((existing,), facts=fact_map(existing))
    before = controller.liveness_snapshot().to_dict()
    before_membership = controller.store.snapshot_membership()
    before_jobs = {
        job.job_id: job.state for job in controller.store.list_jobs() if job.workflow_managed
    }
    generation = controller.begin_scan()

    def fail_persist(_state):
        raise OSError("disk unavailable")

    with pytest.raises(OSError, match="disk unavailable"):
        controller.full_sync(
            (existing, added),
            facts=fact_map(existing, added),
            snapshot_generation=generation,
            persist_liveness_state=fail_persist,
        )

    assert controller.liveness_snapshot().to_dict() == before
    assert controller.store.snapshot_membership() == before_membership
    assert {
        job.job_id: job.state
        for job in controller.store.list_jobs()
        if job.job_id in before_jobs
    } == before_jobs
    assert all(
        job.state is WorkflowJobState.SUPERSEDED
        for job in controller.store.list_jobs()
        if job.workflow_managed and job.job_id not in before_jobs
    )
    persisted: list[dict] = []
    failure = controller.record_liveness_scan_failure(
        "OSError",
        snapshot_generation=generation,
        persist_liveness_state=lambda state: persisted.append(dict(state)),
    )

    assert failure.snapshot_generation == generation
    assert failure.last_error == "OSError"
    assert persisted[0]["accepted_snapshot_generation"] == generation
    assert any(
        job.state is WorkflowJobState.QUEUED
        for job in controller.store.list_jobs()
        if job.job_id in before_jobs
    )
    assert controller.health_snapshot()["controller"]["passes"] == 1


def test_managed_job_claim_waits_for_projection_publication_and_memory_commit(
    controller,
):
    task = issue("In Validation")
    memory_commit_started = Event()
    release_memory_commit = Event()
    memory_committed = Event()
    projection_rolled_back = Event()
    worker_store = WorkflowJobStore(controller.store.path)

    class ProjectionPublication:
        accepted = True
        rejection = None

        def commit_memory(self):
            memory_commit_started.set()
            assert release_memory_commit.wait(timeout=5)
            memory_committed.set()

        def rollback(self):
            projection_rolled_back.set()

    def publish_projection(_result):
        return ProjectionPublication()

    def claim_after_publication():
        claimed = worker_store.claim_next(
            lease_owner="projection-order-worker",
            lease_seconds=60,
        )
        return memory_committed.is_set(), claimed

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            publication = pool.submit(
                controller.full_sync,
                (task,),
                facts=fact_map(task),
                publish_projection=publish_projection,
            )
            assert memory_commit_started.wait(timeout=5)
            claim = pool.submit(claim_after_publication)
            try:
                with pytest.raises(FutureTimeoutError):
                    claim.result(timeout=0.05)
            finally:
                release_memory_commit.set()

            result = publication.result(timeout=5)
            memory_was_committed, claimed = claim.result(timeout=5)

        assert result.accepted
        assert memory_was_committed is True
        assert claimed is not None
        assert claimed.task_id == task.identifier
        assert projection_rolled_back.is_set() is False
    finally:
        worker_store.close()


def test_projection_rollback_failure_still_restores_prior_liveness(controller):
    persisted: dict = {}
    task = issue("In Validation")

    def persist(state):
        persisted.clear()
        persisted.update(dict(state))

    controller.full_sync(
        (task,), facts=fact_map(task), persist_liveness_state=persist
    )
    before_health = controller.liveness_snapshot().to_dict()
    before_state = controller.liveness_state()
    generation = controller.begin_scan()
    projection_committed = Event()
    projection_rollback_attempted = Event()

    class ProjectionPublication:
        accepted = True
        rejection = None

        def commit_memory(self):
            projection_committed.set()

        def rollback(self):
            projection_rollback_attempted.set()
            raise OSError("projection rollback failed")

    connection = controller.store._conn

    class FailPublishedGenerationInsertOnce:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.failed = False

        def execute(self, sql, *args, **kwargs):
            if (
                not self.failed
                and "workflow_snapshot_published_generation" in str(sql)
                and "INSERT" in str(sql)
            ):
                self.failed = True
                raise sqlite3.OperationalError("injected published insert failure")
            return self.wrapped.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

    controller.store._conn = FailPublishedGenerationInsertOnce(connection)

    with pytest.raises(
        WorkflowJobStoreError,
        match="compensating rollback also failed",
    ):
        controller.full_sync(
            (task,),
            facts=fact_map(task),
            now=NOW + timedelta(seconds=1),
            snapshot_generation=generation,
            persist_liveness_state=persist,
            publish_projection=lambda _result: ProjectionPublication(),
        )

    assert projection_committed.is_set()
    assert projection_rollback_attempted.is_set()
    assert controller.liveness_snapshot().to_dict() == before_health
    assert controller.liveness_state() == before_state
    assert persisted == before_state
    store_health = controller.store.health_snapshot()
    assert store_health["accepted_snapshot_generation"] == store_health[
        "published_snapshot_generation"
    ]


def test_reconciliation_failure_restores_partial_durable_authority(
    controller,
    monkeypatch,
):
    existing = issue("In Validation", identifier="TASK-existing")
    added = issue("In Validation", identifier="TASK-added")
    controller.full_sync((existing,), facts=fact_map(existing))
    before_membership = controller.store.snapshot_membership()
    before_cursor = controller.store.schedule_cursor(
        project_id="project-a", task_id=existing.identifier
    )
    before_jobs = {
        job.job_id: job
        for job in controller.store.list_jobs()
        if job.workflow_managed
    }
    generation = controller.begin_scan()
    reconcile_schedule = controller.store.reconcile_schedule
    calls = 0

    def fail_after_first_schedule(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected reconciliation failure")
        return reconcile_schedule(**kwargs)

    monkeypatch.setattr(
        controller.store,
        "reconcile_schedule",
        fail_after_first_schedule,
    )

    with pytest.raises(OSError, match="injected reconciliation failure"):
        controller.full_sync(
            (existing, added),
            facts=fact_map(existing, added),
            snapshot_generation=generation,
        )

    assert calls == 2
    assert controller.store.snapshot_membership() == before_membership
    assert controller.store.schedule_cursor(
        project_id="project-a", task_id=existing.identifier
    ) == before_cursor
    assert {
        job.job_id: job
        for job in controller.store.list_jobs()
        if job.job_id in before_jobs
    } == before_jobs
    added_jobs = controller.store.list_jobs(task_id=added.identifier)
    assert added_jobs == ()

    persisted: list[dict] = []
    failure = controller.record_liveness_scan_failure(
        "OSError",
        snapshot_generation=generation,
        persist_liveness_state=lambda state: persisted.append(dict(state)),
    )

    assert failure.snapshot_generation == generation
    assert failure.last_error == "OSError"
    assert persisted[0]["accepted_snapshot_generation"] == generation
    assert controller.store.list_jobs(task_id=added.identifier) == ()


@pytest.mark.parametrize("worker_mutation", ("complete", "checkpoint"))
def test_failed_publication_cannot_rollback_cross_connection_worker_progress(
    controller,
    monkeypatch,
    worker_mutation,
):
    task = issue("In Validation")
    controller.full_sync((task,), facts=fact_map(task))
    claimed = controller.store.claim_next(
        lease_owner="worker-during-publication",
        lease_seconds=60,
    )
    assert claimed is not None
    assert claimed.lease_token is not None
    worker_store = WorkflowJobStore(controller.store.path)

    authority_captured = Event()
    release_publication = Event()
    worker_started = Event()
    original_capture = controller.store.capture_snapshot_authority

    def capture_then_wait(**kwargs):
        authority = original_capture(**kwargs)
        authority_captured.set()
        assert release_publication.wait(timeout=5)
        return authority

    monkeypatch.setattr(
        controller.store,
        "capture_snapshot_authority",
        capture_then_wait,
    )

    def fail_persist(_state):
        raise OSError("disk unavailable")

    def mutate_claimed_job():
        worker_started.set()
        if worker_mutation == "complete":
            return worker_store.complete(
                claimed.job_id,
                claimed.lease_token,
                result_transition={"outcome": "worker-finished"},
            )
        return worker_store.checkpoint(
            claimed.job_id,
            claimed.lease_token,
            phase="worker-progress",
            checkpoint={"completed_steps": 3},
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            publication = pool.submit(
                controller.full_sync,
                (task,),
                facts=fact_map(task),
                persist_liveness_state=fail_persist,
            )
            assert authority_captured.wait(timeout=5)
            worker = pool.submit(mutate_claimed_job)
            assert worker_started.wait(timeout=5)
            try:
                with pytest.raises(FutureTimeoutError):
                    worker.result(timeout=0.05)
            finally:
                release_publication.set()
            with pytest.raises(OSError, match="disk unavailable"):
                publication.result(timeout=5)
            mutated = worker.result(timeout=5)

        persisted = controller.store.get(claimed.job_id)
        assert persisted == mutated
        if worker_mutation == "complete":
            assert persisted.state is WorkflowJobState.COMPLETED
            assert persisted.result_transition == {"outcome": "worker-finished"}
        else:
            assert persisted.state is WorkflowJobState.RUNNING
            assert persisted.phase == "worker-progress"
            assert persisted.checkpoint == {"completed_steps": 3}
    finally:
        worker_store.close()


def test_sqlite_commit_failure_after_liveness_publish_rolls_back_external_state(
    controller,
):
    persisted: dict = {}
    existing = issue("In Validation", identifier="TASK-existing")
    added = issue("In Validation", identifier="TASK-added")

    def persist(state):
        persisted.clear()
        persisted.update(dict(state))

    controller.full_sync(
        (existing,),
        facts=fact_map(existing),
        persist_liveness_state=persist,
    )
    before_health = controller.liveness_snapshot().to_dict()
    before_state = controller.liveness_state()
    before_published = controller.store.health_snapshot()[
        "published_snapshot_generation"
    ]
    before_membership = controller.store.snapshot_membership()
    before_jobs = {
        job.job_id: job.state for job in controller.store.list_jobs() if job.workflow_managed
    }
    generation = controller.begin_scan()
    connection = controller.store._conn

    class FailPublishedGenerationCommitOnce:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.fail_commit = False
            self.failed = False

        def execute(self, sql, *args, **kwargs):
            result = self.wrapped.execute(sql, *args, **kwargs)
            if (
                not self.failed
                and "workflow_snapshot_published_generation" in str(sql)
                and "INSERT" in str(sql)
            ):
                self.fail_commit = True
            return result

        def commit(self):
            if self.fail_commit:
                self.fail_commit = False
                self.failed = True
                raise sqlite3.OperationalError("injected published commit failure")
            return self.wrapped.commit()

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

    controller.store._conn = FailPublishedGenerationCommitOnce(connection)

    with pytest.raises(sqlite3.OperationalError, match="injected"):
        controller.full_sync(
            (existing, added),
            facts=fact_map(existing, added),
            snapshot_generation=generation,
            persist_liveness_state=persist,
        )

    assert controller.liveness_snapshot().to_dict() == before_health
    assert persisted == before_state
    assert controller.store.health_snapshot()[
        "published_snapshot_generation"
    ] == before_published
    assert controller.store.snapshot_membership() == before_membership
    assert {
        job.job_id: job.state
        for job in controller.store.list_jobs()
        if job.job_id in before_jobs
    } == before_jobs
    assert all(
        job.state is WorkflowJobState.SUPERSEDED
        for job in controller.store.list_jobs()
        if job.workflow_managed and job.job_id not in before_jobs
    )

    failure = controller.record_liveness_scan_failure(
        "OperationalError",
        snapshot_generation=generation,
        persist_liveness_state=persist,
    )

    assert failure.snapshot_generation == generation
    assert failure.status == "incomplete"
    assert persisted["accepted_snapshot_generation"] == generation
    assert any(
        job.state is WorkflowJobState.QUEUED
        for job in controller.store.list_jobs()
        if job.job_id in before_jobs
    )

    recovered = controller.full_sync(
        (existing, added),
        facts=fact_map(existing, added),
        now=NOW + timedelta(seconds=2),
        persist_liveness_state=persist,
    )

    assert recovered.accepted
    assert controller.store.snapshot_membership()
    assert controller.store.claim_next(
        lease_owner="worker-after-recovery", lease_seconds=30
    ) is not None


def test_sqlite_marker_insert_failure_quarantines_nonempty_snapshot_authority(
    controller,
):
    persisted: dict = {}
    existing = issue("In Validation", identifier="TASK-existing")
    added = issue("In Validation", identifier="TASK-added")

    def persist(state):
        persisted.clear()
        persisted.update(dict(state))

    controller.full_sync(
        (existing,), facts=fact_map(existing), persist_liveness_state=persist
    )
    before = controller.liveness_snapshot().to_dict()
    before_membership = controller.store.snapshot_membership()
    before_jobs = {
        job.job_id: job.state for job in controller.store.list_jobs() if job.workflow_managed
    }
    generation = controller.begin_scan()
    connection = controller.store._conn

    class FailPublishedGenerationInsertOnce:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.failed = False

        def execute(self, sql, *args, **kwargs):
            if (
                not self.failed
                and "workflow_snapshot_published_generation" in str(sql)
                and "INSERT" in str(sql)
            ):
                self.failed = True
                raise sqlite3.OperationalError("injected published insert failure")
            return self.wrapped.execute(sql, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

    controller.store._conn = FailPublishedGenerationInsertOnce(connection)

    with pytest.raises(sqlite3.OperationalError, match="injected"):
        controller.full_sync(
            (existing, added),
            facts=fact_map(existing, added),
            snapshot_generation=generation,
            persist_liveness_state=persist,
        )

    assert controller.liveness_snapshot().to_dict() == before
    assert controller.store.snapshot_membership() == before_membership
    assert {
        job.job_id: job.state
        for job in controller.store.list_jobs()
        if job.job_id in before_jobs
    } == before_jobs
    assert all(
        job.state is WorkflowJobState.SUPERSEDED
        for job in controller.store.list_jobs()
        if job.workflow_managed and job.job_id not in before_jobs
    )

    failure = controller.record_liveness_scan_failure(
        "OperationalError",
        snapshot_generation=generation,
        persist_liveness_state=persist,
    )

    assert failure.status == "incomplete"
    assert failure.snapshot_generation == generation
    assert any(
        job.state is WorkflowJobState.QUEUED
        for job in controller.store.list_jobs()
        if job.job_id in before_jobs
    )


def test_partial_event_does_not_replace_complete_global_liveness(controller):
    tasks = (issue(identifier="TASK-1"), issue(identifier="TASK-2"))
    controller.full_sync(tasks, facts=fact_map(*tasks), now=NOW)
    before = controller.liveness_snapshot()
    event_task = tasks[0]

    controller.on_event(
        (event_task,),
        facts=fact_map(event_task),
        now=NOW + timedelta(seconds=1),
    )
    after = controller.liveness_snapshot()

    assert after.snapshot_generation == before.snapshot_generation
    assert after.scan_complete
    assert after.tracked_task_count == 2
    assert after.tasks == before.tasks


def test_controller_projects_actual_lease_and_retry_facts(controller):
    owned = issue("In Progress", identifier="TASK-owned")
    retrying = issue("In Validation", identifier="TASK-retry")
    lease_deadline = NOW + timedelta(minutes=4)
    retry_deadline = NOW + timedelta(minutes=3)
    mapping = fact_map(
        owned,
        retrying,
        overrides={
            owned.identifier: {
                FactDomain.IMPLEMENTATION_AUTHORITY: known(
                    FactDomain.IMPLEMENTATION_AUTHORITY,
                    {
                        "owner_id": "direct-owner",
                        "ownership_source": "direct_owner",
                        "lease_expires_at": lease_deadline.isoformat(),
                    },
                ),
            },
            retrying.identifier: {
                FactDomain.TERMINAL_AUDIT: known(
                    FactDomain.TERMINAL_AUDIT,
                    {
                        "phase": "queued",
                        "retry_at": retry_deadline.isoformat(),
                    },
                ),
                FactDomain.RETRY_BUDGET: known(
                    FactDomain.RETRY_BUDGET,
                    {
                        "attempts": 3,
                        "max_attempts": 5,
                        "retry_at": retry_deadline.isoformat(),
                    },
                ),
            },
        },
    )

    controller.full_sync((owned, retrying), facts=mapping, now=NOW)
    by_task = {
        item.task_id: item for item in controller.liveness_snapshot().tasks
    }

    assert by_task["TASK-owned"].deadline_kind == "lease"
    assert by_task["TASK-owned"].lease_expires_at == lease_deadline.isoformat()
    assert by_task["TASK-retry"].deadline_kind == "retry"
    assert by_task["TASK-retry"].retry_due_at == retry_deadline.isoformat()
    assert by_task["TASK-retry"].recovery_attempt == 3


def test_duplicate_investigator_uses_its_own_authority_domain(controller):
    task = issue("Duplicate Candidate")
    facts = facts_for(
        task,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {
                    "owner_id": "implementation-worker",
                    "lease_expires_at": (
                        NOW + timedelta(minutes=5)
                    ).isoformat(),
                },
            ),
            FactDomain.DUPLICATE_INVESTIGATION: known(
                FactDomain.DUPLICATE_INVESTIGATION,
                {
                    "owner_id": "duplicate-job",
                    "active_job_id": "duplicate-job",
                    "actively_working": True,
                },
            ),
        },
    )

    controller.full_sync(
        (task,), facts_by_task={task.identifier: facts}, now=NOW
    )
    decision = controller.liveness_snapshot().tasks[0]

    assert decision.responsible_owner == "duplicate_investigator"
    assert decision.active_job
    assert decision.deadline_kind == "active_job"


def test_controller_uses_injected_slo_at_exact_boundary_and_one_second_late(
    tmp_path,
):
    store = WorkflowJobStore(str(tmp_path / "configured-slo.sqlite3"))
    configured = UniversalTotalityLivenessController(
        store=store,
        liveness_slo_seconds={"dispatch_latency": 30},
        clock=lambda: NOW,
    )
    task = issue("Open")
    try:
        result = configured.full_sync(
            (task,), facts=fact_map(task), now=NOW
        )
        boundary = configured.liveness.snapshot(
            now=NOW + timedelta(seconds=30)
        )
        late = configured.liveness.snapshot(
            now=NOW + timedelta(seconds=31)
        )

        assert result.decisions[0].next_reassessment_at == (
            NOW + timedelta(seconds=30)
        ).isoformat()
        assert boundary.tasks[0].slo_seconds == 30
        assert boundary.healthy
        assert late.status == "overdue"
        assert late.tasks[0].deadline_lateness_seconds == 1
    finally:
        store.close()


def test_controller_policy_swap_is_immutable_and_epoch_consistent(controller):
    original = controller.liveness_policy
    with pytest.raises(TypeError):
        controller.liveness_slo_seconds["dispatch_latency"] = 1  # type: ignore[index]

    controller.reconfigure_liveness(
        max_task_records=256,
        max_project_records=64,
        snapshot_stale_seconds=900,
        slo_seconds={"dispatch_latency": 31},
    )
    replacement = controller.liveness_policy
    health = controller.liveness_snapshot()

    assert replacement is not original
    assert replacement.epoch != original.epoch
    assert replacement.seconds["dispatch_latency"] == 31
    assert health.policy_epoch == replacement.epoch


def test_duplicate_owners_escalate_with_named_evidence(controller):
    task = issue("In Progress")
    facts = facts_for(
        task,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {
                    "owners": [{"owner_id": "worker-a"}, {"owner_id": "worker-b"}],
                    "lease_expires_at": (NOW + timedelta(minutes=5)).isoformat(),
                },
            )
        },
    )

    decision = controller.evaluate((task,), facts_by_task={task.identifier: facts})[0]

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.reason_code == "ownership.conflict"
    assert decision.responsible_owner is WorkflowOwner.OPERATOR
    assert {item.subject for item in decision.unmet_prerequisites} == {
        "worker-a",
        "worker-b",
    }


def test_missing_owner_identity_is_recovery_not_false_durable_ownership(controller):
    task = issue("In Progress")
    facts = facts_for(
        task,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {"lease_expires_at": (NOW + timedelta(minutes=5)).isoformat()},
            )
        },
    )

    decision = controller.evaluate((task,), facts_by_task={task.identifier: facts})[0]

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "implementation.recovery_scheduled"
    assert decision.unmet_prerequisites[0].code == "ownership.missing"
    assert decision.durable_jobs == ("implementation_recovery",)


@pytest.mark.parametrize(
    ("status", "domain", "value", "disposition", "job"),
    [
        (
            "In Review",
            FactDomain.REVIEW_CI,
            {"ci": "passed"},
            TaskDisposition.OWNED,
            "review_merge",
        ),
        (
            "In Validation",
            FactDomain.TERMINAL_AUDIT,
            {"phase": "queued"},
            TaskDisposition.RETRY_SCHEDULED,
            "terminal_audit",
        ),
        (
            "Ready to Integrate",
            FactDomain.INTEGRATION,
            {"state": "ready"},
            TaskDisposition.RETRY_SCHEDULED,
            "integration_attempt",
        ),
    ],
)
def test_missing_review_audit_or_queue_job_is_reconciled(
    controller, status, domain, value, disposition, job
):
    task = issue(status)
    missing = dict(value)
    missing["job_present"] = False
    facts = facts_for(task, overrides={domain: known(domain, missing)})

    result = controller.reconcile((task,), facts_by_task={task.identifier: facts})

    assert result.decisions[0].disposition is disposition
    assert job in result.decisions[0].durable_jobs
    rows = controller.store.list_jobs()
    assert len(rows) == 1
    assert rows[0].reason_code == result.decisions[0].reason_code


def test_expired_lease_and_stale_facts_schedule_reasoned_recovery(controller):
    expired_task = issue("In Progress", identifier="EXPIRED")
    expired_facts = facts_for(
        expired_task,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {"owner_id": "worker-1", "lease_expires_at": (NOW - timedelta(seconds=1)).isoformat()},
            )
        },
    )
    stale_task = issue("In Review", identifier="STALE")
    stale_facts = facts_for(
        stale_task,
        overrides={
            FactDomain.REVIEW_CI: FactObservation.stale(
                FactDomain.REVIEW_CI,
                {"ci": "passed"},
                observed_at=(NOW - timedelta(hours=1)).isoformat(),
                source="test",
            )
        },
    )

    decisions = controller.evaluate(
        (expired_task, stale_task),
        facts_by_task={"EXPIRED": expired_facts, "STALE": stale_facts},
        now=NOW,
    )

    assert decisions[0].reason_code == "implementation.recovery_scheduled"
    assert decisions[0].durable_jobs == ("implementation_recovery",)
    assert decisions[1].reason_code == "evidence.review_ci_stale"
    assert decisions[1].durable_jobs == ("review_refresh",)
    assert all(item.alert_level is AlertSeverity.INFO for item in decisions)


def test_overdue_reassessment_and_exhausted_retry_escalate(controller):
    overdue = issue("Open", identifier="OVERDUE")
    exhausted = issue("In Progress", identifier="EXHAUSTED")
    old = (NOW - timedelta(hours=2)).isoformat()
    overdue_facts = facts_for(overdue, at=old)
    exhausted_facts = facts_for(
        exhausted,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {"lease_expires_at": (NOW - timedelta(seconds=1)).isoformat()},
            ),
            FactDomain.RETRY_BUDGET: known(
                FactDomain.RETRY_BUDGET,
                {"attempts": 5, "max_attempts": 5, "retry_at": NOW_ISO},
            ),
        },
    )

    decisions = controller.evaluate(
        (overdue, exhausted),
        facts_by_task={"OVERDUE": overdue_facts, "EXHAUSTED": exhausted_facts},
        now=NOW,
    )

    by_task = {decision.task_id: decision for decision in decisions}
    assert by_task["OVERDUE"].reason_code == "liveness.reassessment_overdue"
    assert by_task["OVERDUE"].disposition is TaskDisposition.ACTION_REQUIRED
    assert by_task["EXHAUSTED"].reason_code == "retry.exhausted"
    assert by_task["EXHAUSTED"].disposition is TaskDisposition.ACTION_REQUIRED


def test_due_retry_remains_automatic_and_reasoned(controller):
    task = issue("Ready to Integrate")
    facts = facts_for(
        task,
        overrides={
            FactDomain.INTEGRATION: known(
                FactDomain.INTEGRATION,
                {"state": "ready", "retry_at": NOW_ISO},
            )
        },
    )

    decision = controller.evaluate((task,), facts_by_task={task.identifier: facts})[0]

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "integration.retry_scheduled"
    assert decision.action_required is False
    assert decision.durable_jobs == ("integration_attempt",)


def test_dependency_cycle_is_impossible_not_an_infinite_block(controller):
    first = issue(
        "Open",
        identifier="A",
        blocked_by=[BlockerRef(identifier="B", state="Open")],
    )
    second = issue(
        "Open",
        identifier="B",
        blocked_by=[BlockerRef(identifier="A", state="Open")],
    )

    decisions = controller.evaluate(
        (first, second), facts_by_task=fact_map(first, second), now=NOW
    )

    assert {item.reason_code for item in decisions} == {"graph.impossible"}
    assert all(item.disposition is TaskDisposition.ACTION_REQUIRED for item in decisions)
    assert all(item.unmet_prerequisites[0].code == "dependencies.cycle" for item in decisions)


def test_restart_convergence_and_idempotent_remediation(controller, tmp_path):
    task = issue("In Progress")
    facts = facts_for(
        task,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {"lease_expires_at": (NOW - timedelta(seconds=1)).isoformat()},
            )
        },
    )
    mapping = {task.identifier: facts}

    first = controller.full_sync((task,), facts_by_task=mapping)
    second = controller.on_event((task,), facts_by_task=mapping)
    assert first.reconciliation.jobs_created == 1
    assert second.reconciliation.jobs_replayed == 1
    assert len(controller.store.list_jobs()) == 1

    path = controller.store.path
    controller.store.close()
    reopened_store = WorkflowJobStore(path)
    reopened = UniversalTotalityLivenessController(
        store=reopened_store, clock=lambda: NOW
    )
    try:
        recovery = reopened.recover_startup()
        third = reopened.full_sync((task,), facts_by_task=mapping)
        assert recovery == {"expired": 0, "abandoned": 0}
        assert third.reconciliation.jobs_replayed == 1
        assert len(reopened_store.list_jobs()) == 1
    finally:
        reopened_store.close()


# ---------------------------------------------------------------------------
# OOMPAH-796 regression coverage: generation-race, retry_forced, restart
# ---------------------------------------------------------------------------


def test_integration_gate_blocked_escalates_without_action_required(controller):
    """A blocked-head gate without action_required routes to ACTION_REQUIRED."""

    task = issue("Ready to Integrate")
    facts = facts_for(
        task,
        overrides={
            FactDomain.INTEGRATION: known(
                FactDomain.INTEGRATION,
                {"state": "blocked", "last_error": "gate: policy"},
            )
        },
    )

    result = controller.reconcile((task,), facts_by_task={task.identifier: facts})

    decision = result.decisions[0]
    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.reason_code == "integration.gate_blocked"
    # No automatic integration_attempt may be scheduled.
    for record in controller.store.list_jobs():
        assert record.reason_code == "integration.gate_blocked"


def test_integration_retry_forced_bypasses_gate_blocked(controller):
    """retry_forced authority allows the standard retry path to re-arm."""

    task = issue("Ready to Integrate")
    facts = facts_for(
        task,
        overrides={
            FactDomain.INTEGRATION: known(
                FactDomain.INTEGRATION,
                {
                    "state": "blocked",
                    "last_error": "prior",
                    "retry_forced": True,
                },
            )
        },
    )

    result = controller.reconcile((task,), facts_by_task={task.identifier: facts})

    decision = result.decisions[0]
    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "integration.queued"
    assert decision.durable_jobs == ("integration_attempt",)


def test_live_claim_precedes_history_beats_historical_action_required(controller):
    """Live claim ordering: live_claim_precedes_history wins over action_required."""

    task = issue("Ready to Integrate")
    facts = facts_for(
        task,
        overrides={
            FactDomain.INTEGRATION: known(
                FactDomain.INTEGRATION,
                {
                    "state": "ready",
                    "action_required": True,
                    "action_code": "historical",
                    "live_claim_precedes_history": True,
                },
            )
        },
    )

    decision = controller.evaluate((task,), facts_by_task={task.identifier: facts})[0]

    assert decision.disposition is TaskDisposition.OWNED
    assert decision.reason_code == "integration.live_claim_precedes_history"


def test_generation_race_stale_queue_row_does_not_suppress_new_head(controller):
    """A stale queue row for H1 must not suppress the required attempt for H2.

    This exercises the full fact-collection -> controller path with an
    in-memory queue store that returns a stale row (older head_sha) while
    the tracker holds the new head.  The overlay must ignore the stale row
    and the controller must schedule integration_attempt for the new head.
    """
    from oompah.integration import IntegrationRecord
    from oompah.workflow_facts import WorkflowFactCollector

    old_head = "1" * 40
    new_head = "2" * 40

    tracker_issue = issue(
        "Ready to Integrate",
        identifier="TASK-STALE",
        parent_id="EPIC-1",
        head_sha=new_head,
        integration=IntegrationRecord(
            state="ready", task_branch="t", head_sha=new_head
        ),
    )

    class _StaleQueueRow:
        state = "blocked"
        head_sha = old_head
        lease_owner = None
        lease_expires_at = None
        last_error = "stale-block"
        retry_forced = False

    class _StaleQueue:
        def get(self, project_id, task_id):
            return _StaleQueueRow()

    class _Tracker:
        def __init__(self, iss):
            self._issue = iss

        def fetch_issue_detail(self, ident):
            return self._issue if ident == self._issue.identifier else None

        def fetch_children(self, ident):
            return []

    collector = WorkflowFactCollector(
        project_id=str(tracker_issue.project_id),
        tracker=_Tracker(tracker_issue),
        integration_queue=_StaleQueue(),
        clock=lambda: NOW,
    )
    facts = collector.collect(tracker_issue.identifier)
    integration_value = facts.fact(FactDomain.INTEGRATION).value

    # Stale row must be ignored: tracker's ready state is preserved.
    assert integration_value["state"] == "ready"
    assert integration_value.get("last_error") != "stale-block"

    # And the controller schedules the required integration_attempt.
    result = controller.reconcile(
        (tracker_issue,),
        facts_by_task={tracker_issue.identifier: facts},
    )
    decision = result.decisions[0]
    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "integration.queued"
    assert "integration_attempt" in decision.durable_jobs


def test_generation_race_current_head_live_claim_signals_live_claim_flag(controller):
    """A queue row matching the current head with a valid lease surfaces the live claim."""
    from oompah.integration import IntegrationRecord
    from oompah.workflow_facts import WorkflowFactCollector

    head = "3" * 40

    tracker_issue = issue(
        "Ready to Integrate",
        identifier="TASK-LIVE",
        head_sha=head,
        integration=IntegrationRecord(
            state="ready", task_branch="t", head_sha=head
        ),
    )

    lease_expires_at = (NOW + timedelta(minutes=10)).timestamp()

    class _LiveRow:
        state = "integrating"
        head_sha = head
        lease_owner = "integrator-1"
        lease_expires_at = None  # set below
        last_error = None
        retry_forced = False

    row = _LiveRow()
    row.lease_expires_at = lease_expires_at

    class _LiveQueue:
        def get(self, project_id, task_id):
            return row

    class _Tracker:
        def __init__(self, iss):
            self._issue = iss

        def fetch_issue_detail(self, ident):
            return self._issue if ident == self._issue.identifier else None

        def fetch_children(self, ident):
            return []

    collector = WorkflowFactCollector(
        project_id=str(tracker_issue.project_id),
        tracker=_Tracker(tracker_issue),
        integration_queue=_LiveQueue(),
        clock=lambda: NOW,
    )
    facts = collector.collect(tracker_issue.identifier)
    integration_value = facts.fact(FactDomain.INTEGRATION).value

    assert integration_value["state"] == "integrating"
    assert integration_value["lease_owner"] == "integrator-1"
    assert integration_value.get("live_claim_precedes_history") is True

    decision = controller.evaluate(
        (tracker_issue,), facts_by_task={tracker_issue.identifier: facts}
    )[0]

    assert decision.disposition is TaskDisposition.OWNED
    assert decision.reason_code == "integration.live_claim_precedes_history"


def test_restart_convergence_with_gate_blocked_is_idempotent(tmp_path):
    """After a restart, gate_blocked remediation replays exactly once.

    Regression for the recovery-checkpoint audit: the controller must not
    duplicate the escalation on the first full-sync tick after startup.
    """

    store = WorkflowJobStore(str(tmp_path / "restart.sqlite3"))
    controller_a = UniversalTotalityLivenessController(
        store=store, decision_limit=100, clock=lambda: NOW
    )
    try:
        task = issue("Ready to Integrate")
        facts = facts_for(
            task,
            overrides={
                FactDomain.INTEGRATION: known(
                    FactDomain.INTEGRATION,
                    {"state": "blocked", "last_error": "gate"},
                )
            },
        )
        mapping = {task.identifier: facts}
        first = controller_a.full_sync((task,), facts_by_task=mapping)
        assert first.decisions[0].reason_code == "integration.gate_blocked"
        # Blocked gate is action_required, escalation may or may not create a
        # durable job depending on availability of remediation; the test
        # asserts idempotence across restart.
        job_count_before = len(store.list_jobs())
    finally:
        pass

    # Simulate restart: close and reopen the store.
    store.close()
    reopened = WorkflowJobStore(str(tmp_path / "restart.sqlite3"))
    controller_b = UniversalTotalityLivenessController(
        store=reopened, decision_limit=100, clock=lambda: NOW
    )
    try:
        controller_b.recover_startup()
        task = issue("Ready to Integrate")
        facts = facts_for(
            task,
            overrides={
                FactDomain.INTEGRATION: known(
                    FactDomain.INTEGRATION,
                    {"state": "blocked", "last_error": "gate"},
                )
            },
        )
        mapping = {task.identifier: facts}
        second = controller_b.full_sync((task,), facts_by_task=mapping)
        assert second.decisions[0].reason_code == "integration.gate_blocked"
        # Total job count must not change across restart (idempotent).
        assert len(reopened.list_jobs()) == job_count_before
    finally:
        reopened.close()
