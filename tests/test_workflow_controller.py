"""Totality, liveness, and restart convergence for the universal controller."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from oompah.models import BlockerRef, Issue
from oompah.work_decision import PermittedAction
from oompah.workflow_controller import UniversalTotalityLivenessController
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
from oompah.workflow_jobs import WorkflowJobStore
from oompah.workflow_reasons import AlertSeverity


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
    ("status", "domain", "value", "job"),
    [
        ("In Review", FactDomain.REVIEW_CI, {"ci": "passed"}, "review_monitor"),
        ("In Validation", FactDomain.TERMINAL_AUDIT, {"phase": "queued"}, "terminal_audit"),
        ("Ready to Integrate", FactDomain.INTEGRATION, {"state": "ready"}, "integration_attempt"),
    ],
)
def test_missing_review_audit_or_queue_job_is_reconciled(controller, status, domain, value, job):
    task = issue(status)
    missing = dict(value)
    missing["job_present"] = False
    facts = facts_for(task, overrides={domain: known(domain, missing)})

    result = controller.reconcile((task,), facts_by_task={task.identifier: facts})

    assert result.decisions[0].disposition is TaskDisposition.RETRY_SCHEDULED
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
