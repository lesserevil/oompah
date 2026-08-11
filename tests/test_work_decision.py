"""Pure decision coverage across lifecycle, failures, and incident facts."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from oompah.models import Issue
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DECOMPOSED,
    DONE,
    DUPLICATE_CANDIDATE,
    IN_PROGRESS,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    PROPOSED,
    READY_TO_INTEGRATE,
)
from oompah.work_decision import (
    KNOWN_DECISION_REASON_CODES,
    PermittedAction,
    WorkDecision,
    evaluate_task,
)
from oompah.workflow_contract import TaskDisposition, WorkflowOwner
from oompah.workflow_facts import (
    FactDomain,
    FactObservation,
    LandingFact,
    LandingState,
    REQUIRED_FACT_DOMAINS,
    WorkflowFacts,
)
from oompah.workflow_reasons import AlertSeverity

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


def _issue(status=OPEN, **overrides):
    values = {
        "id": "TASK-1",
        "identifier": "TASK-1",
        "title": "Decision",
        "state": status,
        "project_id": "project-1",
        "issue_type": "task",
        "parent_id": None,
    }
    values.update(overrides)
    return Issue(**values)


def _known(domain, value):
    return FactObservation.known(domain, value, observed_at=NOW_ISO, source="test")


def _facts(issue, *, overrides=None, landings=()):
    observations = {
        domain: FactObservation.missing(domain, observed_at=NOW_ISO, source="test")
        for domain in REQUIRED_FACT_DOMAINS
    }
    observations.update(
        {
            FactDomain.TASK: _known(
                FactDomain.TASK,
                {
                    "identifier": issue.identifier,
                    "project_id": issue.project_id,
                    "status": issue.state,
                    "issue_type": issue.issue_type,
                    "parent_id": issue.parent_id,
                },
            ),
            FactDomain.DEPENDENCIES: _known(
                FactDomain.DEPENDENCIES, {"finish": [], "hard_start": []}
            ),
            FactDomain.CONTAINMENT: _known(
                FactDomain.CONTAINMENT,
                {"parent_id": issue.parent_id, "children": []},
            ),
            FactDomain.RETRY_BUDGET: _known(FactDomain.RETRY_BUDGET, {"remaining": 3}),
            FactDomain.CONFIG: _known(FactDomain.CONFIG, {"version": 1}),
        }
    )
    observations.update(overrides or {})
    if landings:
        observations[FactDomain.LANDING] = _known(
            FactDomain.LANDING,
            {"evidence_revisions": [item.evidence_revision for item in landings]},
        )
    return WorkflowFacts(
        "project-1",
        issue.identifier,
        NOW_ISO,
        observations,
        landings=tuple(landings),
    )


@pytest.mark.parametrize(
    ("status", "disposition", "reason", "owner", "alert"),
    [
        (
            PROPOSED,
            TaskDisposition.BLOCKED,
            "intake.awaiting_decision",
            WorkflowOwner.INTAKE,
            AlertSeverity.NONE,
        ),
        (
            BACKLOG,
            TaskDisposition.BLOCKED,
            "prioritization.awaiting_owner",
            WorkflowOwner.PROJECT_OWNER,
            AlertSeverity.NONE,
        ),
        (
            OPEN,
            TaskDisposition.RUNNABLE,
            "dispatch.eligible",
            WorkflowOwner.DISPATCHER,
            AlertSeverity.NONE,
        ),
        (
            NEEDS_CI_FIX,
            TaskDisposition.RUNNABLE,
            "dispatch.eligible",
            WorkflowOwner.REPAIR_WORKER,
            AlertSeverity.NONE,
        ),
        (
            NEEDS_REBASE,
            TaskDisposition.RUNNABLE,
            "dispatch.eligible",
            WorkflowOwner.REPAIR_WORKER,
            AlertSeverity.NONE,
        ),
        (
            NEEDS_ANSWER,
            TaskDisposition.ACTION_REQUIRED,
            "requestor.answer_required",
            WorkflowOwner.REQUESTOR,
            AlertSeverity.WARNING,
        ),
        (
            NEEDS_HUMAN,
            TaskDisposition.ACTION_REQUIRED,
            "operator.action_required",
            WorkflowOwner.OPERATOR,
            AlertSeverity.WARNING,
        ),
        (
            MERGED,
            TaskDisposition.TERMINAL,
            "terminal.final",
            WorkflowOwner.NONE,
            AlertSeverity.NONE,
        ),
        (
            ARCHIVED,
            TaskDisposition.TERMINAL,
            "terminal.final",
            WorkflowOwner.NONE,
            AlertSeverity.NONE,
        ),
    ],
)
def test_total_default_decisions(status, disposition, reason, owner, alert):
    issue = _issue(status)
    decision = evaluate_task(issue, _facts(issue))

    assert decision.disposition is disposition
    assert decision.reason_code == reason
    assert decision.responsible_owner is owner
    assert decision.alert_level is alert
    assert decision.action_required is (disposition is TaskDisposition.ACTION_REQUIRED)
    assert (decision.next_reassessment_at is None) is (status in {MERGED, ARCHIVED})


def test_work_decision_round_trip_and_revision_are_stable():
    issue = _issue()
    decision = evaluate_task(issue, _facts(issue))

    replay = WorkDecision.from_dict(decision.to_dict())

    assert replay == decision
    assert replay.decision_revision == decision.decision_revision
    assert len(decision.decision_revision) == 64


def test_only_action_required_decisions_may_warn():
    base = dict(
        project_id="project-1",
        task_id="TASK-1",
        status=OPEN,
        reason_code="dispatch.eligible",
        responsible_owner=WorkflowOwner.DISPATCHER,
        unmet_prerequisites=(),
        evidence_revision="facts",
        next_reassessment_at=NOW_ISO,
        permitted_actions=(),
    )
    with pytest.raises(ValueError, match="cannot be warnings"):
        WorkDecision(
            **base,
            disposition=TaskDisposition.RUNNABLE,
            action_required=False,
            alert_level=AlertSeverity.WARNING,
        )
    with pytest.raises(ValueError, match="visibly alerting"):
        WorkDecision(
            **base,
            disposition=TaskDisposition.ACTION_REQUIRED,
            action_required=True,
            alert_level=AlertSeverity.INFO,
        )
    with pytest.raises(ValueError, match="unknown work-decision reason"):
        WorkDecision(
            **{**base, "reason_code": "unknown.reason"},
            disposition=TaskDisposition.RUNNABLE,
            action_required=False,
            alert_level=AlertSeverity.NONE,
        )


def test_hard_start_dependency_blocks_dispatch_but_finish_order_does_not():
    issue = _issue()
    finish_only = _facts(
        issue,
        overrides={
            FactDomain.DEPENDENCIES: _known(
                FactDomain.DEPENDENCIES,
                {
                    "finish": [{"identifier": "TASK-F", "status": OPEN}],
                    "hard_start": [],
                },
            )
        },
    )
    hard_start = _facts(
        issue,
        overrides={
            FactDomain.DEPENDENCIES: _known(
                FactDomain.DEPENDENCIES,
                {
                    "finish": [],
                    "hard_start": [{"identifier": "TASK-H", "status": OPEN}],
                },
            )
        },
    )

    assert evaluate_task(issue, finish_only).disposition is TaskDisposition.RUNNABLE
    blocked = evaluate_task(issue, hard_start)
    assert blocked.disposition is TaskDisposition.BLOCKED
    assert blocked.unmet_prerequisites[0].subject == "TASK-H"


@pytest.mark.parametrize(
    "dependency_fact",
    [
        FactObservation.missing(
            FactDomain.DEPENDENCIES, observed_at=NOW_ISO, source="tracker"
        ),
        _known(FactDomain.DEPENDENCIES, {"finish": {}, "hard_start": []}),
    ],
)
def test_unavailable_or_malformed_dependencies_schedule_fact_recovery(
    dependency_fact,
):
    issue = _issue()
    facts = _facts(issue, overrides={FactDomain.DEPENDENCIES: dependency_fact})

    decision = evaluate_task(issue, facts)

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.alert_level is AlertSeverity.INFO
    assert "dependency_refresh" in decision.durable_jobs


def test_integration_waits_for_both_finish_and_hard_start_dependencies():
    issue = _issue(READY_TO_INTEGRATE)
    facts = _facts(
        issue,
        overrides={
            FactDomain.DEPENDENCIES: _known(
                FactDomain.DEPENDENCIES,
                {
                    "finish": [{"identifier": "TASK-F", "status": OPEN}],
                    "hard_start": [{"identifier": "TASK-H", "status": DONE}],
                },
            ),
            FactDomain.INTEGRATION: _known(FactDomain.INTEGRATION, {"state": "ready"}),
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.reason_code == "integration.dependencies_blocked"
    assert [item.subject for item in decision.unmet_prerequisites] == ["TASK-F"]


def test_in_progress_lease_selects_current_owner_and_expiry_recovery():
    issue = _issue(IN_PROGRESS)
    active = _facts(
        issue,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: _known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {
                    "owner_id": "owner",
                    "ownership_source": "direct_owner",
                    "lease_expires_at": (NOW + timedelta(minutes=5)).isoformat(),
                },
            )
        },
    )
    expired = _facts(
        issue,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: _known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {
                    "owner_id": "owner",
                    "lease_expires_at": (NOW - timedelta(seconds=1)).isoformat(),
                },
            )
        },
    )

    owned = evaluate_task(issue, active)
    recovery = evaluate_task(issue, expired)

    assert owned.disposition is TaskDisposition.OWNED
    assert owned.responsible_owner is WorkflowOwner.DIRECT_OWNER
    assert recovery.disposition is TaskDisposition.RETRY_SCHEDULED
    assert recovery.alert_level is AlertSeverity.INFO
    assert recovery.durable_jobs == ("implementation_recovery",)


def test_missing_implementation_authority_is_recovery_not_warning():
    issue = _issue(IN_PROGRESS)
    decision = evaluate_task(issue, _facts(issue))

    assert decision.reason_code == "evidence.implementation_authority_missing"
    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.action_required is False
    assert decision.alert_level is AlertSeverity.INFO


def test_accepted_submission_recovery_does_not_require_a_live_implementer():
    issue = _issue(IN_PROGRESS)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.CONFIG: _known(
                    FactDomain.CONFIG,
                    {
                        "implementation_pending_action": "validation_submission",
                        "implementation_pending_payload": {
                            "head_sha": "a" * 40,
                        },
                    },
                )
            },
        ),
    )

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.durable_jobs == ("validation_submission",)
    assert decision.alert_level is AlertSeverity.INFO


def test_accepted_focus_handoff_recovery_does_not_require_live_outgoing_run():
    issue = _issue(IN_PROGRESS)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.CONFIG: _known(
                    FactDomain.CONFIG,
                    {
                        "implementation_pending_action": "focus_handoff",
                        "implementation_pending_payload": {"focus": "feature"},
                    },
                )
            },
        ),
    )

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.durable_jobs == ("focus_handoff",)
    assert decision.alert_level is AlertSeverity.INFO


def test_duplicate_candidate_requires_duplicate_investigator_authority():
    issue = _issue(DUPLICATE_CANDIDATE)
    implementer = _facts(
        issue,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: _known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {
                    "owner_id": "implementer",
                    "ownership_source": "agent",
                    "lease_expires_at": (NOW + timedelta(minutes=5)).isoformat(),
                },
            )
        },
    )
    investigator = _facts(
        issue,
        overrides={
            FactDomain.DUPLICATE_INVESTIGATION: _known(
                FactDomain.DUPLICATE_INVESTIGATION,
                {
                    "owner_id": "investigator",
                    "ownership_source": "duplicate_investigator",
                    "lease_expires_at": (NOW + timedelta(minutes=5)).isoformat(),
                },
            )
        },
    )

    screened = evaluate_task(issue, implementer)
    owned = evaluate_task(issue, investigator)

    assert screened.durable_jobs == ("duplicate_screening",)
    assert owned.reason_code == "duplicate.investigating"
    assert owned.disposition is TaskDisposition.OWNED


def test_confirmed_duplicate_candidate_waits_for_project_owner_resolution():
    issue = _issue(DUPLICATE_CANDIDATE)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.CONFIG: _known(
                    FactDomain.CONFIG,
                    {
                        "duplicate_screening_state": "checked",
                        "duplicate_screening_verdict": "duplicate_candidate",
                    },
                )
            },
        ),
    )

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.responsible_owner is WorkflowOwner.PROJECT_OWNER
    assert decision.durable_jobs == ()
    assert decision.reason_code == "duplicate.confirmed"


def test_duplicate_candidate_does_not_spin_when_screening_is_disabled():
    issue = _issue(DUPLICATE_CANDIDATE)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.CONFIG: _known(
                    FactDomain.CONFIG,
                    {"duplicate_screening_enabled": False},
                )
            },
        ),
    )

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.responsible_owner is WorkflowOwner.OPERATOR
    assert decision.durable_jobs == ()
    assert decision.reason_code == "duplicate.screening_disabled"


@pytest.mark.parametrize(
    ("review", "reason", "recommended", "action"),
    [
        (
            {"ci": "failed", "mergeable": True},
            "review.ci_fix_required",
            NEEDS_CI_FIX,
            PermittedAction.ROUTE_CI_FIX,
        ),
        (
            {"ci": "passed", "conflict": True},
            "review.rebase_required",
            NEEDS_REBASE,
            PermittedAction.ROUTE_REBASE,
        ),
            (
                {"ci": "passed", "mergeable": True},
                "review.ready_to_merge",
                None,
                PermittedAction.MERGE_REVIEW,
            ),
    ],
)
def test_review_decisions_share_normalized_evidence(
    review, reason, recommended, action
):
    issue = _issue(IN_REVIEW)
    facts = _facts(
        issue,
        overrides={FactDomain.REVIEW_CI: _known(FactDomain.REVIEW_CI, review)},
    )

    decision = evaluate_task(issue, facts)

    assert decision.reason_code == reason
    assert decision.recommended_status == recommended
    assert action in decision.permitted_actions


def test_missing_review_evidence_schedules_refresh_without_warning():
    issue = _issue(IN_REVIEW)
    decision = evaluate_task(issue, _facts(issue))

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "evidence.review_ci_missing"
    assert decision.alert_level is AlertSeverity.INFO


def test_validation_queued_active_retry_and_action_required():
    issue = _issue(IN_VALIDATION)
    queued = _facts(
        issue,
        overrides={
            FactDomain.TERMINAL_AUDIT: _known(
                FactDomain.TERMINAL_AUDIT, {"phase": "queued"}
            )
        },
    )
    active = _facts(
        issue,
        overrides={
            FactDomain.TERMINAL_AUDIT: _known(
                FactDomain.TERMINAL_AUDIT,
                {
                    "phase": "active",
                    "lease_expires_at": (NOW + timedelta(minutes=1)).isoformat(),
                },
            )
        },
    )
    action = _facts(
        issue,
        overrides={
            FactDomain.TERMINAL_AUDIT: _known(
                FactDomain.TERMINAL_AUDIT,
                {
                    "phase": "failed",
                    "action_required": True,
                    "action_code": "restore_transport",
                },
            )
        },
    )

    assert evaluate_task(issue, queued).reason_code == "validation.queued"
    assert evaluate_task(issue, active).disposition is TaskDisposition.OWNED
    required = evaluate_task(issue, action)
    assert required.disposition is TaskDisposition.ACTION_REQUIRED
    assert required.alert_level is AlertSeverity.WARNING
    expired = _facts(
        issue,
        overrides={
            FactDomain.TERMINAL_AUDIT: _known(
                FactDomain.TERMINAL_AUDIT,
                {
                    "phase": "active",
                    "lease_expires_at": (NOW - timedelta(seconds=1)).isoformat(),
                },
            )
        },
    )
    recovery = evaluate_task(issue, expired)
    assert recovery.reason_code == "validation.retry_scheduled"
    assert recovery.alert_level is AlertSeverity.INFO


def test_normal_integration_queue_retry_and_active_are_not_warnings():
    issue = _issue(READY_TO_INTEGRATE)
    cases = [
        ({"state": "ready"}, "integration.queued", TaskDisposition.RETRY_SCHEDULED),
        (
            {"state": "ready", "retry_at": NOW_ISO},
            "integration.retry_scheduled",
            TaskDisposition.RETRY_SCHEDULED,
        ),
        (
            {
                "state": "integrating",
                "lease_expires_at": (NOW + timedelta(minutes=1)).isoformat(),
            },
            "integration.active",
            TaskDisposition.OWNED,
        ),
        (
            {
                "state": "integrating",
                "lease_expires_at": (NOW - timedelta(seconds=1)).isoformat(),
            },
            "integration.retry_scheduled",
            TaskDisposition.RETRY_SCHEDULED,
        ),
    ]
    for value, reason, disposition in cases:
        facts = _facts(
            issue,
            overrides={FactDomain.INTEGRATION: _known(FactDomain.INTEGRATION, value)},
        )
        decision = evaluate_task(issue, facts)
        assert decision.reason_code == reason
        assert decision.disposition is disposition
        assert decision.alert_level in {AlertSeverity.NONE, AlertSeverity.INFO}


def test_integration_action_required_is_the_only_warning_path():
    issue = _issue(READY_TO_INTEGRATE)
    facts = _facts(
        issue,
        overrides={
            FactDomain.INTEGRATION: _known(
                FactDomain.INTEGRATION,
                {
                    "state": "blocked",
                    "action_required": True,
                    "action_code": "repair_credentials",
                },
            )
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.alert_level is AlertSeverity.WARNING
    assert decision.unmet_prerequisites[0].code == "repair_credentials"


def test_decomposed_rollup_waits_then_becomes_runnable():
    issue = _issue(DECOMPOSED, issue_type="epic")
    waiting = _facts(
        issue,
        overrides={
            FactDomain.CONTAINMENT: _known(
                FactDomain.CONTAINMENT,
                {"children": [{"identifier": "TASK-2", "status": OPEN}]},
            )
        },
    )
    complete = _facts(
        issue,
        overrides={
            FactDomain.CONTAINMENT: _known(
                FactDomain.CONTAINMENT,
                {"children": [{"identifier": "TASK-2", "status": DONE}]},
            )
        },
    )

    assert evaluate_task(issue, waiting).disposition is TaskDisposition.BLOCKED
    assert evaluate_task(issue, complete).disposition is TaskDisposition.RUNNABLE
    empty = evaluate_task(issue, _facts(issue))
    assert empty.reason_code == "rollup.children_missing"
    assert empty.disposition is TaskDisposition.RETRY_SCHEDULED


def test_duplicate_investigator_requires_its_own_live_authority():
    issue = _issue(DUPLICATE_CANDIDATE)
    active = _facts(
        issue,
        overrides={
            FactDomain.DUPLICATE_INVESTIGATION: _known(
                FactDomain.DUPLICATE_INVESTIGATION,
                {
                    "owner_id": "duplicate-worker",
                    "lease_expires_at": (
                        NOW + timedelta(minutes=1)
                    ).isoformat(),
                },
            )
        },
    )

    assert evaluate_task(issue, active).disposition is TaskDisposition.OWNED
    assert (
        evaluate_task(issue, _facts(issue)).disposition
        is TaskDisposition.RETRY_SCHEDULED
    )


def _landing(state, *, error=None, target="epic-parent"):
    return LandingFact(
        "task-branch",
        target,
        "a" * 40,
        {"kind": state.value},
        NOW_ISO,
        "project-1",
        state=state,
        durable=state is LandingState.LANDED,
        error_code=error,
    )


def test_done_uses_immediate_target_landing_without_parent_status_cycle():
    issue = _issue(DONE, parent_id="EPIC-1")
    positive = evaluate_task(
        issue, _facts(issue, landings=(_landing(LandingState.LANDED),))
    )
    negative = evaluate_task(
        issue, _facts(issue, landings=(_landing(LandingState.NOT_LANDED),))
    )
    unknown = evaluate_task(
        issue,
        _facts(issue, landings=(_landing(LandingState.UNKNOWN, error="git_timeout"),)),
    )

    assert positive.disposition is TaskDisposition.TERMINAL
    assert positive.reason_code == "terminal.immediate_target_landing_proven"
    assert positive.recommended_status == MERGED
    assert negative.disposition is TaskDisposition.BLOCKED
    assert unknown.disposition is TaskDisposition.RETRY_SCHEDULED
    assert unknown.alert_level is AlertSeverity.INFO


def _terminal_provenance(**overrides):
    payload = {
        "schema_version": 1,
        "marker_present": True,
        "marker_version": 1,
        "project_id": "project-1",
        "task_id": "TASK-1",
        "retained": True,
        "malformed": False,
        "authority_generation": 3,
        "authorized_by": "owner",
        "actor_source": "api",
        "marked_at": NOW_ISO,
        "updated_at": NOW_ISO,
    }
    payload.update(overrides)
    return _known(
        FactDomain.TERMINAL_AUDIT,
        {"terminal_provenance": payload},
    )


def _terminal_provenance_absent(**overrides):
    payload = {
        "schema_version": 1,
        "marker_present": False,
        "project_id": "project-1",
        "task_id": "TASK-1",
        "retained": False,
        "malformed": False,
        "authority_generation": 0,
    }
    payload.update(overrides)
    return _known(
        FactDomain.TERMINAL_AUDIT,
        {"terminal_provenance": payload},
    )


def test_done_retained_as_terminal_provenance_requires_no_landing_effect():
    issue = _issue(DONE)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={FactDomain.TERMINAL_AUDIT: _terminal_provenance()},
            landings=(_landing(LandingState.UNKNOWN, error="git_timeout"),),
        ),
    )

    assert decision.disposition is TaskDisposition.TERMINAL
    assert decision.reason_code == "terminal.provenance_retained"
    assert decision.responsible_owner is WorkflowOwner.NONE
    assert decision.durable_jobs == ()
    assert decision.recommended_status is None
    assert decision.next_reassessment_at is None


def test_done_without_provenance_marker_keeps_normal_landing_decision():
    issue = _issue(DONE)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.TERMINAL_AUDIT: _terminal_provenance_absent()
            },
            landings=(_landing(LandingState.UNKNOWN, error="git_timeout"),),
        ),
    )

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "landing.evidence_unknown"
    assert decision.durable_jobs == ("integration_landing_refresh",)


@pytest.mark.parametrize(
    "overrides",
    [
        {"marker_present": "false"},
        {"retained": True},
        {"malformed": True},
        {"authority_generation": 1},
        {"task_id": "OTHER"},
        {"project_id": "other-project"},
        {"marker_version": 1},
        {"authorized_by": "owner"},
    ],
)
def test_invalid_terminal_provenance_absence_fails_closed(overrides):
    issue = _issue(DONE)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.TERMINAL_AUDIT: _terminal_provenance_absent(
                    **overrides
                )
            },
        ),
    )

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.reason_code == "terminal.provenance_invalid"
    assert decision.durable_jobs == ()


@pytest.mark.parametrize(
    "overrides",
    [
        {"task_id": "OTHER"},
        {"project_id": "other-project"},
        {"authorized_by": ""},
        {"authority_generation": True},
        {"marker_version": 2},
        {"malformed": True, "marker_version": None},
        {"marked_at": ""},
        {"retained": False, "task_id": "OTHER"},
        {"retained": False, "project_id": "other-project"},
        {"retained": False, "authorized_by": ""},
        {"retained": False, "authority_generation": 0},
        {"retained": "false"},
        {"malformed": "true"},
        {"retained": None},
        {"schema_version": True},
        {"marker_version": True},
    ],
)
def test_invalid_terminal_provenance_never_becomes_delivery_proof(overrides):
    issue = _issue(DONE)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.TERMINAL_AUDIT: _terminal_provenance(**overrides)
            },
        ),
    )

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.reason_code == "terminal.provenance_invalid"
    assert decision.durable_jobs == ()
    assert decision.alert_level is AlertSeverity.WARNING


@pytest.mark.parametrize("payload", [None, "invalid", [], True])
def test_non_mapping_terminal_provenance_never_resumes_delivery(payload):
    issue = _issue(DONE)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.TERMINAL_AUDIT: _known(
                    FactDomain.TERMINAL_AUDIT,
                    {"terminal_provenance": payload},
                )
            },
        ),
    )

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.reason_code == "terminal.provenance_invalid"
    assert decision.durable_jobs == ()
    assert decision.alert_level is AlertSeverity.WARNING


@pytest.mark.parametrize("value", ["invalid", [], True])
def test_non_mapping_terminal_audit_fact_never_resumes_delivery(value):
    issue = _issue(DONE)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.TERMINAL_AUDIT: _known(
                    FactDomain.TERMINAL_AUDIT,
                    value,
                )
            },
        ),
    )

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.reason_code == "terminal.provenance_invalid"
    assert decision.durable_jobs == ()
    assert decision.alert_level is AlertSeverity.WARNING


def test_owner_authorized_new_revision_resumes_normal_done_landing_decision():
    issue = _issue(DONE)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.TERMINAL_AUDIT: _terminal_provenance(
                    retained=False,
                    authority_generation=4,
                    marked_at="",
                )
            },
            landings=(_landing(LandingState.UNKNOWN, error="git_timeout"),),
        ),
    )

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "landing.evidence_unknown"
    assert decision.durable_jobs == ("integration_landing_refresh",)


def test_retained_marker_on_nonterminal_status_fails_closed_without_dispatch():
    issue = _issue(OPEN)
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={FactDomain.TERMINAL_AUDIT: _terminal_provenance()},
        ),
    )

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.reason_code == "terminal.provenance_invalid"
    assert decision.durable_jobs == ()
    assert decision.permitted_actions == (
        PermittedAction.RESOLVE_OPERATOR_ACTION,
    )


def test_done_nested_epic_uses_its_own_immediate_target_landing():
    issue = _issue(
        DONE,
        issue_type="epic",
        parent_id="EPIC-1",
        work_branch="task-branch",
        target_branch="epic-parent",
        head_sha="a" * 40,
    )

    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.CONTAINMENT: _known(
                    FactDomain.CONTAINMENT,
                    {
                        "parent_id": "EPIC-1",
                        "epic_branch": "task-branch",
                        "target_branch": "epic-parent",
                        "children": [],
                    },
                )
            },
            landings=(_landing(LandingState.LANDED, target="epic-parent"),),
        ),
    )

    assert decision.reason_code == "terminal.immediate_target_landing_proven"
    assert decision.recommended_status == MERGED
    assert decision.durable_jobs == ("epic_auto_close",)


def test_done_epic_does_not_treat_child_landing_as_its_own_when_target_is_unset():
    issue = _issue(
        DONE,
        issue_type="epic",
        work_branch=None,
        target_branch=None,
    )
    child_landing = LandingFact(
        "CHILD-1",
        "epic-TASK-1",
        "a" * 40,
        {"kind": "git_ancestry"},
        NOW_ISO,
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )

    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.CONTAINMENT: _known(
                    FactDomain.CONTAINMENT,
                    {
                        "parent_id": None,
                        "epic_branch": "epic-TASK-1",
                        "target_branch": "main",
                        "children": [
                            {"identifier": "CHILD-1", "status": DONE}
                        ],
                    },
                )
            },
            landings=(child_landing,),
        ),
    )

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "landing.target_evidence_missing"
    assert decision.durable_jobs == ("epic_terminal_validation",)
    assert decision.recommended_status is None


def test_done_epic_fails_closed_when_containment_is_not_current():
    issue = _issue(
        DONE,
        issue_type="epic",
        work_branch="epic-TASK-1",
        target_branch="main",
    )
    own_landing = LandingFact(
        "epic-TASK-1",
        "main",
        "a" * 40,
        {"kind": "git_ancestry"},
        NOW_ISO,
        "project-1",
        state=LandingState.LANDED,
        durable=True,
    )
    missing_containment = FactObservation.missing(
        FactDomain.CONTAINMENT,
        observed_at=NOW_ISO,
        source="tracker",
    )

    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={FactDomain.CONTAINMENT: missing_containment},
            landings=(own_landing,),
        ),
    )

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "evidence.containment_missing"
    assert decision.durable_jobs == ("epic_terminal_validation",)
    assert decision.recommended_status is None


def test_done_epic_fails_closed_when_containment_has_no_exact_target():
    issue = _issue(DONE, issue_type="epic")
    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.CONTAINMENT: _known(
                    FactDomain.CONTAINMENT,
                    {
                        "parent_id": None,
                        "epic_branch": "epic-TASK-1",
                        "target_branch": None,
                        "children": [],
                    },
                )
            },
        ),
    )

    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.reason_code == "evidence.containment_malformed"
    assert decision.durable_jobs == ("epic_terminal_validation",)
    assert decision.recommended_status is None


def test_done_ignores_landing_proof_for_a_different_target():
    issue = _issue(DONE, parent_id="EPIC-1", target_branch="epic-parent")
    immediate_negative = _landing(LandingState.NOT_LANDED, target="epic-parent")
    root_positive = _landing(LandingState.LANDED, target="main")

    decision = evaluate_task(
        issue,
        _facts(issue, landings=(immediate_negative, root_positive)),
    )

    assert decision.disposition is TaskDisposition.BLOCKED
    assert decision.reason_code == "landing.waiting"
    assert decision.unmet_prerequisites[0].subject.endswith("->epic-parent")


def test_done_with_only_wrong_target_proof_schedules_target_refresh():
    issue = _issue(DONE, parent_id="EPIC-1", target_branch="epic-parent")

    decision = evaluate_task(
        issue,
        _facts(issue, landings=(_landing(LandingState.LANDED, target="main"),)),
    )

    assert decision.reason_code == "landing.target_evidence_missing"
    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.alert_level is AlertSeverity.INFO


def test_merged_remains_final_even_when_landing_fact_is_unknown():
    issue = _issue(MERGED)
    decision = evaluate_task(
        issue,
        _facts(
            issue, landings=(_landing(LandingState.UNKNOWN, error="source_missing"),)
        ),
    )

    assert decision.disposition is TaskDisposition.TERMINAL
    assert decision.reason_code == "terminal.final"
    assert decision.permitted_actions == ()


def test_merged_preserves_verified_reason_only_for_exact_durable_landing():
    issue = _issue(
        MERGED,
        work_branch="task-branch",
        target_branch="epic-parent",
        head_sha="a" * 40,
    )
    exact = _landing(LandingState.LANDED, target="epic-parent")

    decision = evaluate_task(issue, _facts(issue, landings=(exact,)))

    assert decision.reason_code == "terminal.preserve_verified_merged"
    assert decision.disposition is TaskDisposition.TERMINAL


@pytest.mark.parametrize(
    "landing",
    [
        LandingFact(
            "other-branch",
            "epic-parent",
            "a" * 40,
            {"kind": "git_ancestry"},
            NOW_ISO,
            "project-1",
            state=LandingState.LANDED,
            durable=True,
        ),
        LandingFact(
            "task-branch",
            "other-target",
            "a" * 40,
            {"kind": "git_ancestry"},
            NOW_ISO,
            "project-1",
            state=LandingState.LANDED,
            durable=True,
        ),
        LandingFact(
            "task-branch",
            "epic-parent",
            "b" * 40,
            {"kind": "git_ancestry"},
            NOW_ISO,
            "project-1",
            state=LandingState.LANDED,
            durable=True,
        ),
    ],
    ids=("source", "target", "revision"),
)
def test_merged_rejects_unrelated_durable_landing_evidence(landing):
    issue = _issue(
        MERGED,
        work_branch="task-branch",
        target_branch="epic-parent",
        head_sha="a" * 40,
    )

    assert evaluate_task(issue, _facts(issue, landings=(landing,))).reason_code == (
        "terminal.final"
    )


def test_lifecycle_final_status_ignores_missing_or_stale_supporting_facts():
    issue = _issue(MERGED)
    facts = _facts(
        issue,
        overrides={
            FactDomain.TASK: FactObservation.error(
                FactDomain.TASK,
                observed_at=NOW_ISO,
                source="tracker",
                error_code="tracker_offline",
            )
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.disposition is TaskDisposition.TERMINAL
    assert decision.reason_code == "terminal.final"
    assert decision.next_reassessment_at is None


def test_fact_identity_or_status_race_fails_closed():
    issue = _issue()
    other_project = replace(issue, project_id="project-2")
    mismatched_status = _facts(
        issue,
        overrides={
            FactDomain.TASK: _known(
                FactDomain.TASK, {"status": IN_PROGRESS, "identifier": "TASK-1"}
            )
        },
    )

    identity = evaluate_task(other_project, _facts(issue))
    status = evaluate_task(issue, mismatched_status)

    assert identity.disposition is TaskDisposition.ACTION_REQUIRED
    assert identity.reason_code == "evidence.project_or_task_mismatch"
    assert status.disposition is TaskDisposition.RETRY_SCHEDULED
    assert status.reason_code == "evidence.task_status_mismatch"


def test_internal_task_fact_identity_cannot_cross_scope():
    issue = _issue()
    facts = _facts(
        issue,
        overrides={
            FactDomain.TASK: _known(
                FactDomain.TASK,
                {
                    "identifier": "TASK-OTHER",
                    "project_id": "project-2",
                    "status": OPEN,
                },
            )
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.reason_code == "evidence.task_fact_identity_mismatch"


def test_unknown_status_is_total_and_actionable():
    issue = _issue("Custom Waiting")
    decision = evaluate_task(issue, _facts(issue))

    assert decision.disposition is TaskDisposition.ACTION_REQUIRED
    assert decision.reason_code == "workflow.unknown_status"
    assert decision.responsible_owner is WorkflowOwner.OPERATOR


def test_incident_required_base_deadlock_schedules_one_reconciliation_owner():
    issue = _issue(READY_TO_INTEGRATE)
    facts = _facts(
        issue,
        overrides={
            FactDomain.INTEGRATION: _known(
                FactDomain.INTEGRATION,
                {"state": "ready", "required_base_missing": ["TASK-0"]},
            )
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.reason_code == "integration.required_base_missing"
    assert decision.durable_jobs == ("epic_branch_reconciliation",)
    assert decision.responsible_owner is WorkflowOwner.INTEGRATOR


def test_incident_direct_maintenance_bypasses_ordinary_child_integration():
    issue = _issue(
        OPEN,
        title="Rebase epic-EPIC-1 onto main",
        parent_id="EPIC-1",
        work_branch="epic-EPIC-1",
        target_branch="epic-EPIC-1",
        head_sha="a" * 40,
    )
    facts = _facts(
        issue,
        overrides={
            FactDomain.INTEGRATION: _known(
                FactDomain.INTEGRATION,
                {
                    "state": "integrated",
                    "mode": "queue",
                    "task_branch": "epic-EPIC-1",
                    "base_branch": "epic-EPIC-1",
                    "head_sha": "a" * 40,
                    "integrated_sha": "a" * 40,
                    "maintenance_publication_proven": True,
                },
            )
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.reason_code == "maintenance.publication_proven"
    assert decision.responsible_owner is WorkflowOwner.AUDITOR
    assert decision.recommended_status == IN_VALIDATION
    assert decision.durable_jobs == ("terminal_audit_done",)


@pytest.mark.parametrize(
    "override",
    [
        {"state": "ready"},
        {"mode": "standalone"},
        {"task_branch": "ordinary-child"},
        {"base_branch": "main"},
        {"integrated_sha": "b" * 40},
        {"maintenance_publication_proven": False},
    ],
)
def test_direct_maintenance_audit_requires_complete_exact_handoff(override):
    issue = _issue(
        OPEN,
        title="Rebase epic-EPIC-1 onto main",
        parent_id="EPIC-1",
        work_branch="epic-EPIC-1",
        target_branch="epic-EPIC-1",
        head_sha="a" * 40,
    )
    integration = {
        "state": "integrated",
        "mode": "queue",
        "task_branch": "epic-EPIC-1",
        "base_branch": "epic-EPIC-1",
        "head_sha": "a" * 40,
        "integrated_sha": "a" * 40,
        "maintenance_publication_proven": True,
        **override,
    }

    decision = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.INTEGRATION: _known(
                    FactDomain.INTEGRATION, integration
                )
            },
        ),
    )

    assert decision.reason_code == "dispatch.eligible"
    assert "terminal_audit_done" not in decision.durable_jobs


def test_incident_standalone_delivery_ignores_benign_metadata_churn():
    issue = _issue(READY_TO_INTEGRATE)
    facts = _facts(
        issue,
        overrides={
            FactDomain.INTEGRATION: _known(
                FactDomain.INTEGRATION,
                {"state": "ready", "mode": "standalone", "head_sha": "a" * 40},
            )
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.reason_code == "standalone.delivery_eligible"
    assert decision.durable_jobs == ("standalone_delivery",)


@pytest.mark.parametrize("retirement_pending", [False, True])
def test_ready_direct_owner_must_retire_before_standalone_delivery(
    retirement_pending,
):
    """OOMPAH-1085/1093: Ready cannot race exact owner revocation."""

    issue = _issue(READY_TO_INTEGRATE)
    facts = _facts(
        issue,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: _known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {
                    "owner_id": "alice",
                    "generation": "claim-submitted",
                    "ownership_source": "direct_owner",
                    "lease_expires_at": None,
                    "retirement_pending": retirement_pending,
                    "state": (
                        "retirement_pending" if retirement_pending else "active"
                    ),
                },
            ),
            FactDomain.INTEGRATION: _known(
                FactDomain.INTEGRATION,
                {"state": "ready", "mode": "standalone", "head_sha": "a" * 40},
            ),
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.reason_code == "integration.owner_retirement_pending"
    assert decision.disposition is TaskDisposition.OWNED
    assert decision.responsible_owner is WorkflowOwner.DIRECT_OWNER
    assert decision.durable_jobs == ()


def test_ready_integration_fails_closed_when_owner_authority_read_fails():
    issue = _issue(READY_TO_INTEGRATE)
    facts = _facts(
        issue,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: FactObservation.error(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                observed_at=NOW_ISO,
                source="owner_claim_store",
                error_code="owner_claim_store_unavailable",
            ),
            FactDomain.INTEGRATION: _known(
                FactDomain.INTEGRATION,
                {"state": "ready", "mode": "standalone", "head_sha": "a" * 40},
            ),
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.reason_code == "evidence.implementation_authority_error"
    assert decision.disposition is TaskDisposition.RETRY_SCHEDULED
    assert decision.durable_jobs == ()


def test_parented_standalone_delivery_requires_exact_persisted_target_route():
    issue = _issue(
        READY_TO_INTEGRATE,
        parent_id="EPIC-1",
        target_branch="main",
    )
    exact = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.INTEGRATION: _known(
                    FactDomain.INTEGRATION,
                    {
                        "state": "ready",
                        "mode": "standalone",
                        "post_landed_parent_id": "EPIC-1",
                        "base_branch": "main",
                    },
                )
            },
        ),
    )
    mismatch = evaluate_task(
        issue,
        _facts(
            issue,
            overrides={
                FactDomain.INTEGRATION: _known(
                    FactDomain.INTEGRATION,
                    {
                        "state": "ready",
                        "mode": "standalone",
                        "post_landed_parent_id": "EPIC-1",
                        "base_branch": "release",
                    },
                )
            },
        ),
    )

    assert exact.durable_jobs == ("standalone_delivery",)
    assert "standalone_delivery" not in mismatch.durable_jobs


def test_incident_live_claim_is_independent_of_bounded_history_replay():
    issue = _issue(READY_TO_INTEGRATE)
    facts = _facts(
        issue,
        overrides={
            FactDomain.INTEGRATION: _known(
                FactDomain.INTEGRATION,
                {"state": "ready", "live_claim_precedes_history": True},
            )
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.reason_code == "integration.live_claim_precedes_history"
    assert decision.disposition is TaskDisposition.OWNED
    assert decision.durable_jobs == ("integration_attempt",)


def test_incident_advisory_policy_denial_does_not_poison_implementation():
    issue = _issue(IN_PROGRESS)
    facts = _facts(
        issue,
        overrides={
            FactDomain.CONFIG: _known(
                FactDomain.CONFIG, {"coordination_policy_denied": True}
            ),
            FactDomain.IMPLEMENTATION_AUTHORITY: _known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {
                    "owner_id": "implementer",
                    "ownership_source": "agent",
                    "lease_expires_at": (NOW + timedelta(minutes=5)).isoformat(),
                },
            ),
        },
    )

    decision = evaluate_task(issue, facts)

    assert decision.reason_code == "coordination.policy_denied"
    assert decision.disposition is TaskDisposition.OWNED
    assert decision.alert_level is AlertSeverity.NONE


def test_evaluation_is_deterministic_for_same_facts_and_explicit_time():
    issue = _issue(IN_PROGRESS)
    facts = _facts(
        issue,
        overrides={
            FactDomain.IMPLEMENTATION_AUTHORITY: _known(
                FactDomain.IMPLEMENTATION_AUTHORITY,
                {"lease_expires_at": (NOW + timedelta(seconds=1)).isoformat()},
            )
        },
    )

    first = evaluate_task(issue, facts, now=NOW)
    second = evaluate_task(issue, facts, now=NOW)

    assert first == second
    assert first.decision_revision == second.decision_revision
    assert first.reason_code in KNOWN_DECISION_REASON_CODES


def test_custom_runtime_slo_controls_decision_deadline_without_global_mutation():
    current = _issue(OPEN)
    facts = _facts(current)

    configured = evaluate_task(
        current,
        facts,
        now=NOW,
        liveness_slo_seconds={"dispatch_latency": 17},
    )
    default = evaluate_task(current, facts, now=NOW)

    assert configured.next_reassessment_at == (
        NOW + timedelta(seconds=17)
    ).isoformat()
    assert default.next_reassessment_at != configured.next_reassessment_at
    assert default.decision_revision != configured.decision_revision
