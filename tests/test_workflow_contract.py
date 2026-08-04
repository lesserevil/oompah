"""Structural regression tests for the canonical main-task lifecycle."""

from dataclasses import replace

import pytest

from oompah import statuses
from oompah.workflow_contract import (
    ARCHIVED,
    BACKLOG,
    CANONICAL_STATUSES,
    DISPATCHABLE_STATUSES,
    DONE,
    IDEMPOTENT_TRANSITIONS,
    IN_PROGRESS,
    IN_REVIEW,
    IN_VALIDATION,
    LIFECYCLE_FINAL_STATUSES,
    LIVENESS_INVARIANTS,
    MERGED,
    NEEDS_ANSWER,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
    PROPOSED,
    READY_TO_INTEGRATE,
    REVIEW_STATUSES,
    SAFETY_INVARIANTS,
    STATUS_ALIASES,
    STATUS_CONTRACTS,
    TERMINAL_STATUSES,
    TRANSITION_RULES,
    VALID_TRANSITIONS,
    WAITING_STATUSES,
    WORKING_STATUSES,
    ExecutionPhase,
    ReassessmentTrigger,
    TaskDisposition,
    TransitionRequirement,
    canonicalize_status,
    is_valid_transition,
    status_contract,
    transition_rule,
    validate_workflow_contract,
)


def test_every_canonical_status_has_one_total_contract_and_transition_row():
    assert tuple(STATUS_CONTRACTS) == CANONICAL_STATUSES
    assert set(VALID_TRANSITIONS) == set(CANONICAL_STATUSES)

    for status in CANONICAL_STATUSES:
        contract = STATUS_CONTRACTS[status]
        assert contract.status == status
        assert isinstance(contract.phase, ExecutionPhase)
        assert isinstance(contract.disposition, TaskDisposition)
        assert contract.owners
        assert isinstance(contract.reassessment.trigger, ReassessmentTrigger)


def test_compatibility_categories_are_contract_projections():
    assert DISPATCHABLE_STATUSES == frozenset({OPEN, NEEDS_CI_FIX, NEEDS_REBASE})
    assert WORKING_STATUSES == frozenset({IN_PROGRESS})
    assert WAITING_STATUSES == frozenset({NEEDS_ANSWER, NEEDS_HUMAN})
    assert REVIEW_STATUSES == frozenset({IN_REVIEW, NEEDS_CI_FIX, NEEDS_REBASE})
    assert TERMINAL_STATUSES == frozenset({DONE, MERGED, ARCHIVED})
    assert LIFECYCLE_FINAL_STATUSES == frozenset({MERGED, ARCHIVED})


def test_statuses_module_is_a_compatibility_facade_for_the_contract():
    for name in (
        "CANONICAL_STATUSES",
        "DISPATCHABLE_STATUSES",
        "WORKING_STATUSES",
        "WAITING_STATUSES",
        "REVIEW_STATUSES",
        "TERMINAL_STATUSES",
    ):
        assert getattr(statuses, name) is globals()[name]
    assert statuses.canonicalize_status is canonicalize_status


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("To Do", BACKLOG),
        ("asking_question", NEEDS_ANSWER),
        ("human-only", NEEDS_HUMAN),
        ("ci-fix", NEEDS_CI_FIX),
        ("merge-conflict", NEEDS_REBASE),
        ("in_validation", IN_VALIDATION),
        ("ready-to-integrate", READY_TO_INTEGRATE),
        ("closed", DONE),
        ("archive:yes", ARCHIVED),
    ],
)
def test_compatibility_aliases_resolve_to_contract_status(alias, canonical):
    assert canonicalize_status(alias) == canonical
    assert status_contract(alias) is STATUS_CONTRACTS[canonical]


def test_all_alias_targets_and_transition_targets_are_canonical():
    assert set(STATUS_ALIASES.values()) <= set(CANONICAL_STATUSES)
    assert {
        target for targets in VALID_TRANSITIONS.values() for target in targets
    } <= set(CANONICAL_STATUSES)


def test_transition_table_has_no_implicit_or_illegal_self_edges():
    assert IDEMPOTENT_TRANSITIONS == frozenset()
    for status, targets in VALID_TRANSITIONS.items():
        assert status not in targets
        assert not is_valid_transition(status, status)
        assert not is_valid_transition(status, status, allow_idempotent=True)


def test_every_legal_edge_has_a_version_fenced_rule():
    expected_edges = {
        (source, target)
        for source, targets in VALID_TRANSITIONS.items()
        for target in targets
    }
    assert set(TRANSITION_RULES) == expected_edges
    for source, target in expected_edges:
        rule = transition_rule(source, target)
        assert rule is not None
        assert TransitionRequirement.EXPECTED_VERSION in rule.requirements
        assert is_valid_transition(source, target)


def test_key_safety_edges_require_domain_evidence():
    assert (
        TransitionRequirement.DEPENDENCIES_SATISFIED
        in TRANSITION_RULES[(OPEN, IN_PROGRESS)].requirements
    )
    assert (
        TransitionRequirement.ACCEPTED_SUBMISSION
        in TRANSITION_RULES[(IN_PROGRESS, READY_TO_INTEGRATE)].requirements
    )
    assert (
        TransitionRequirement.AUDIT_PASS
        in TRANSITION_RULES[(IN_VALIDATION, DONE)].requirements
    )
    merged = TRANSITION_RULES[(IN_VALIDATION, MERGED)].requirements
    assert TransitionRequirement.LANDING_EVIDENCE in merged
    assert TransitionRequirement.CONTAINMENT_EVIDENCE in merged


def test_gate_routing_and_watchdog_recovery_are_version_fenced_edges():
    """Internal gates may override Open; repaired stalled work may reopen."""

    for source, target in (
        (OPEN, NEEDS_CI_FIX),
        (OPEN, NEEDS_REBASE),
        (NEEDS_CI_FIX, OPEN),
        (NEEDS_REBASE, OPEN),
    ):
        rule = transition_rule(source, target)
        assert rule is not None
        assert rule.requirements == frozenset(
            {TransitionRequirement.EXPECTED_VERSION}
        )


def test_final_statuses_have_no_automatic_reassessment_path():
    for status in LIFECYCLE_FINAL_STATUSES:
        contract = STATUS_CONTRACTS[status]
        assert contract.lifecycle_final
        assert contract.reassessment.trigger == ReassessmentTrigger.NEVER


def test_nonfinal_statuses_have_a_reassessment_path_and_blockers_are_named():
    for status, contract in STATUS_CONTRACTS.items():
        if not contract.lifecycle_final:
            assert contract.reassessment.trigger != ReassessmentTrigger.NEVER, status
        if contract.disposition == TaskDisposition.BLOCKED:
            assert contract.blocked_by, status


def test_safety_and_liveness_invariants_are_stable_and_unique():
    invariants = (*SAFETY_INVARIANTS, *LIVENESS_INVARIANTS)
    codes = [invariant.code for invariant in invariants]
    assert len(codes) == len(set(codes))
    assert {invariant.kind for invariant in SAFETY_INVARIANTS} == {"safety"}
    assert {invariant.kind for invariant in LIVENESS_INVARIANTS} == {"liveness"}
    assert "single_status_writer" in codes
    assert "total_disposition" in codes
    assert "restart_reconstructs_work" in codes


def test_contract_validator_accepts_the_authoritative_contract():
    assert validate_workflow_contract() == ()


def test_contract_validator_rejects_missing_rows_and_unnamed_blockers():
    missing = dict(STATUS_CONTRACTS)
    del missing[OPEN]
    errors = validate_workflow_contract(status_contracts=missing)
    assert any("STATUS_CONTRACTS mismatch" in error for error in errors)

    malformed = dict(STATUS_CONTRACTS)
    malformed[PROPOSED] = replace(malformed[PROPOSED], blocked_by=None)
    errors = validate_workflow_contract(status_contracts=malformed)
    assert "blocked status 'Proposed' has no named prerequisite" in errors


def test_contract_tables_are_read_only():
    with pytest.raises(TypeError):
        STATUS_CONTRACTS["custom"] = STATUS_CONTRACTS[OPEN]  # type: ignore[index]
    with pytest.raises(TypeError):
        VALID_TRANSITIONS[OPEN] = frozenset()  # type: ignore[index]
    with pytest.raises(TypeError):
        TRANSITION_RULES[(OPEN, OPEN)] = TRANSITION_RULES[(OPEN, IN_PROGRESS)]  # type: ignore[index]
