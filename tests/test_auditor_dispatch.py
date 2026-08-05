"""Tests for durable independent-auditor scheduling policy."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
from types import SimpleNamespace

import pytest

from oompah.auditor_dispatch import AuditorDispatchLane, audit_branch_key
from oompah.auditor_candidate_selector import NoCandidateReason
from oompah.roles import Candidate
from oompah.terminal_audit import (
    AuditAttempt,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
)
from oompah.orchestrator import auditor_turn_budget


def test_auditor_budget_reserves_one_non_starvable_finalization_turn() -> None:
    assert auditor_turn_budget(100, auditor=True) == 101
    assert auditor_turn_budget(100, auditor=False) == 100


def test_pending_record_prefers_active_attempt_over_ownerless_state() -> None:
    fingerprint = EvidenceFingerprint(hashlib.sha256(b"same").hexdigest())
    pending = TerminalAuditRecord(
        audit_id="audit-pending",
        project_id="project-1",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        created_at="2026-08-05T12:00:00+00:00",
        source_generation=2,
    )
    running_attempt = AuditAttempt(
        attempt_id="attempt-running",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        created_at="2026-08-05T12:01:00+00:00",
        started_at="2026-08-05T12:01:00+00:00",
    )
    running = replace(
        pending,
        audit_id="audit-running",
        request_state=RequestState.PENDING,
        attempts=[running_attempt],
        updated_at="2026-08-05T12:01:00+00:00",
        source_generation=1,
    )

    assert AuditorDispatchLane.pending_record(
        [pending, running], project_id="project-1", task_id="TASK-1"
    ) == running


def test_pending_record_new_evidence_supersedes_old_running_semantics() -> None:
    old = _record(request_state=RequestState.IN_PROGRESS)
    old_attempt = AuditAttempt(
        attempt_id="attempt-old",
        target_state=TargetState.DONE,
        evidence_fingerprint=old.evidence_fingerprint,
        request_state=RequestState.IN_PROGRESS,
    )
    old = replace(old, attempts=[old_attempt], source_generation=1)
    fresh = replace(
        _record(fingerprint="evidence-2"),
        audit_id="audit-fresh",
        source_generation=2,
    )

    assert AuditorDispatchLane.pending_record(
        [old, fresh], project_id="project-1", task_id="TASK-1"
    ) == fresh


def test_pending_record_preserves_done_before_newer_merged_lane() -> None:
    done = replace(_record(), source_generation=1)
    merged = replace(
        _record(),
        audit_id="audit-merged",
        target_state=TargetState.MERGED,
        source_generation=2,
    )

    assert AuditorDispatchLane.pending_record(
        [done, merged], project_id="project-1", task_id="TASK-1"
    ) == done


def test_rearmed_done_appended_after_merged_still_owns_chain_order() -> None:
    original_done = _record()
    failed_done = replace(
        original_done,
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id="attempt-failed-done",
                target_state=TargetState.DONE,
                evidence_fingerprint=original_done.evidence_fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.FAIL,
            )
        ],
        source_generation=1,
    )
    merged = replace(
        _record(),
        audit_id="audit-merged",
        target_state=TargetState.MERGED,
        source_generation=1,
    )
    rearmed_done = replace(
        _record(),
        audit_id="audit-rearmed-done",
        source_generation=2,
    )

    assert AuditorDispatchLane.pending_record(
        [failed_done, merged], project_id="project-1", task_id="TASK-1"
    ) is None
    assert (
        AuditorDispatchLane.pending_record(
            [failed_done, merged, rearmed_done],
            project_id="project-1",
            task_id="TASK-1",
        )
        == rearmed_done
    )


def test_merged_dispatch_requires_exact_completed_done_pass() -> None:
    done = _record()
    passed_done = replace(
        done,
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id="attempt-passed-done",
                target_state=TargetState.DONE,
                evidence_fingerprint=done.evidence_fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.PASS,
            )
        ],
    )
    merged = replace(
        _record(),
        audit_id="audit-merged",
        target_state=TargetState.MERGED,
    )

    assert AuditorDispatchLane.pending_record(
        [passed_done, merged], project_id="project-1", task_id="TASK-1"
    ) == merged


def test_merged_dispatch_ignores_same_identifier_prerequisite_from_other_project() -> None:
    local_merged = replace(
        _record(),
        audit_id="audit-shared",
        target_state=TargetState.MERGED,
    )
    foreign_done = replace(
        _record(),
        audit_id="audit-shared",
        project_id="project-foreign",
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id="attempt-shared",
                target_state=TargetState.DONE,
                evidence_fingerprint=local_merged.evidence_fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.PASS,
            )
        ],
    )

    assert AuditorDispatchLane.pending_record(
        [foreign_done, local_merged],
        project_id="project-1",
        task_id="TASK-1",
    ) is None


class _Selector:
    """Small deterministic selector double for the scheduler state machine."""

    def __init__(self, candidates: list[Candidate]) -> None:
        self.candidates = candidates

    def select_candidates(self, contributors=None, *, exclude=None):
        excluded = exclude or set()
        available = [
            candidate
            for candidate in self.candidates
            if (candidate.provider_id, candidate.model) not in excluded
        ]
        if not available:
            return [], NoCandidateReason("all_attempted", "all candidates used")
        return available, None


def _record(
    *,
    fingerprint: str = "evidence-1",
    attempts=None,
    request_state: RequestState = RequestState.PENDING,
) -> TerminalAuditRecord:
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()
    return TerminalAuditRecord(
        audit_id="audit-1",
        project_id="project-1",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=EvidenceFingerprint(digest),
        request_state=request_state,
        attempts=list(attempts or []),
    )


def _active_identity(
    current: TerminalAuditRecord, attempt_id: str
) -> tuple[str, str, str, str]:
    return (
        current.project_id,
        current.task_id,
        current.audit_id,
        attempt_id,
    )


def _lane(
    candidates: list[Candidate],
    *,
    now: datetime,
    max_attempts: int = 3,
    attempt_id: str = "attempt-1",
) -> AuditorDispatchLane:
    return AuditorDispatchLane(
        _Selector(candidates),
        max_attempts=max_attempts,
        attempt_ttl_seconds=60,
        clock=lambda: now,
        id_factory=lambda: attempt_id,
    )


def test_plan_persist_and_finish_preserves_launch_identity():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    candidate = Candidate("provider-a", "model-a")
    lane = _lane([candidate], now=now)

    plan, reason = lane.plan(_record(), [], branch_key="epic:EPIC-1")
    assert reason is None
    assert plan is not None
    persisted = lane.persist_plan(_record(), plan)
    attempt = persisted.attempts[0]
    assert persisted.request_state == RequestState.IN_PROGRESS
    assert attempt.attempt_id == plan.attempt_id
    assert attempt.provider_id == "provider-a"
    assert attempt.model == "model-a"
    assert attempt.branch_key == "epic:EPIC-1"

    ended = lane.finish_attempt(
        persisted,
        plan.attempt_id,
        reason="rate limit",
        ended_at="2026-07-29T00:01:00+00:00",
    )
    assert ended.request_state == RequestState.PENDING
    assert ended.attempts[0].request_state == RequestState.PENDING
    assert ended.attempts[0].failure_reason == "rate limit"


def test_dispatch_plan_is_fenced_to_project_and_task() -> None:
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    lane = _lane([Candidate("provider-a", "model-a")], now=now)
    original = _record()
    plan, _ = lane.plan(original, [], branch_key="branch-1")
    assert plan is not None

    with pytest.raises(ValueError, match="different audit"):
        lane.persist_plan(replace(original, project_id="project-foreign"), plan)


def test_rotation_excludes_rate_limited_candidate_and_selects_next():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    candidates = [Candidate("provider-a", "model-a"), Candidate("provider-b", "model-b")]
    lane = _lane(candidates, now=now, attempt_id="attempt-2")
    first_plan, _ = lane.plan(_record(), [], branch_key="branch-1")
    assert first_plan is not None
    failed = lane.finish_attempt(
        lane.persist_plan(_record(), first_plan),
        first_plan.attempt_id,
        reason="provider timeout",
    )

    second_plan, reason = lane.plan(failed, [], branch_key="branch-1")
    assert reason is None
    assert second_plan is not None
    assert (second_plan.candidate.provider_id, second_plan.candidate.model) == (
        "provider-b",
        "model-b",
    )
    assert second_plan.rotation_count == 1


def test_restart_with_no_live_worker_reclaims_in_progress_attempt():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    lane = _lane([Candidate("provider-a", "model-a")], now=now)
    plan, _ = lane.plan(_record(), [], branch_key="branch-1", now=now)
    assert plan is not None
    persisted = lane.persist_plan(_record(), plan)

    recovery = lane.recover(persisted, active_attempt_identities=set(), now=now)
    assert recovery.ready
    assert "no live worker" in (recovery.reason or "")
    assert recovery.record.request_state == RequestState.PENDING
    assert recovery.record.attempts[0].request_state == RequestState.PENDING


def test_same_attempt_id_in_other_project_does_not_preserve_dispatch_owner():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    lane = _lane([Candidate("provider-a", "model-a")], now=now)
    plan, _ = lane.plan(_record(), [], branch_key="branch-1", now=now)
    assert plan is not None
    persisted = lane.persist_plan(_record(), plan)

    recovery = lane.recover(
        persisted,
        active_attempt_identities={
            (
                "project-foreign",
                persisted.task_id,
                persisted.audit_id,
                plan.attempt_id,
            )
        },
        now=now,
    )

    assert recovery.ready
    assert "no live worker" in (recovery.reason or "")


def test_live_attempt_is_not_duplicated_and_timeout_is_recoverable():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    lane = _lane([Candidate("provider-a", "model-a")], now=now)
    plan, _ = lane.plan(_record(), [], branch_key="branch-1", now=now)
    assert plan is not None
    persisted = lane.persist_plan(_record(), plan)

    live = lane.recover(
        persisted,
        active_attempt_identities={_active_identity(persisted, plan.attempt_id)},
        now=now,
    )
    assert not live.ready
    assert live.reason == "auditor already running"

    active_old = replace(
        persisted,
        attempts=[
            replace(
                persisted.attempts[0],
                started_at=(now - timedelta(seconds=61)).isoformat(),
                created_at=(now - timedelta(seconds=61)).isoformat(),
            )
        ],
    )
    active_expired = lane.recover(
        active_old,
        active_attempt_identities={_active_identity(active_old, plan.attempt_id)},
        now=now,
    )
    assert not active_expired.ready
    assert "termination required" in (active_expired.reason or "")

    old = replace(
        persisted,
        attempts=[
            replace(
                persisted.attempts[0],
                started_at=(now - timedelta(seconds=61)).isoformat(),
                created_at=(now - timedelta(seconds=61)).isoformat(),
            )
        ],
    )
    expired = lane.recover(old, active_attempt_identities=set(), now=now)
    assert expired.ready
    assert "TTL" in (expired.reason or "")

    backoff_record = lane.finish_attempt(
        persisted,
        plan.attempt_id,
        reason="rate limit",
        ended_at=now.isoformat(),
        retry_after=(now + timedelta(seconds=10)).isoformat(),
    )
    cooling = lane.recover(
        backoff_record,
        active_attempt_identities=set(),
        now=now,
    )
    assert not cooling.ready
    assert "backoff" in (cooling.reason or "")
    ready = lane.recover(
        backoff_record,
        active_attempt_identities=set(),
        now=now + timedelta(seconds=10),
    )
    assert ready.ready


def test_changed_fingerprint_invalidates_stale_running_attempt():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    lane = _lane([Candidate("provider-a", "model-a")], now=now)
    plan, _ = lane.plan(_record(), [], branch_key="branch-1", now=now)
    assert plan is not None
    persisted = lane.persist_plan(_record(), plan)
    changed = replace(
        persisted,
        evidence_fingerprint=EvidenceFingerprint(
            hashlib.sha256(b"evidence-2").hexdigest()
        ),
    )

    live = lane.recover(
        changed,
        active_attempt_identities={_active_identity(changed, plan.attempt_id)},
        now=now,
    )
    assert not live.ready
    assert "while auditor is running" in (live.reason or "")

    abandoned = lane.recover(changed, active_attempt_identities=set(), now=now)
    assert abandoned.ready
    assert "fingerprint changed" in (abandoned.reason or "")


def test_max_attempts_and_no_candidates_are_actionable():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    candidate = Candidate("provider-a", "model-a")
    lane = _lane([candidate], now=now, max_attempts=1)
    plan, _ = lane.plan(_record(), [], branch_key="branch-1")
    assert plan is not None
    exhausted = lane.finish_attempt(
        lane.persist_plan(_record(), plan), plan.attempt_id, reason="crash"
    )
    no_plan, reason = lane.plan(exhausted, [], branch_key="branch-1")
    assert no_plan is None
    assert reason is not None
    assert reason.reason == "all_attempted"

    empty_lane = _lane([], now=now)
    no_plan, reason = empty_lane.plan(_record(), [], branch_key="branch-1")
    assert no_plan is None
    assert reason is not None
    assert reason.reason == "all_attempted"


def test_branch_key_is_shared_by_epic_children_and_explicit_branches():
    assert audit_branch_key(SimpleNamespace(parent_id="EPIC-1", identifier="TASK-1")) == (
        "epic:EPIC-1"
    )
    assert audit_branch_key(
        SimpleNamespace(parent_id="EPIC-1", work_branch="feature/shared")
    ) == "feature/shared"


def test_branch_key_prefers_accepted_generation_over_stale_projection():
    issue = SimpleNamespace(
        identifier="OOMPAH-814",
        project_id="project-a",
        work_branch="epic-OOMPAH-763--task-OOMPAH-814",
        branch_name="epic-OOMPAH-763--task-OOMPAH-814",
        integration=SimpleNamespace(
            state="ready",
            task_branch="OOMPAH-814",
            head_sha="a" * 40,
        ),
    )

    assert audit_branch_key(issue) == "OOMPAH-814"


def test_finish_attempt_classifies_transient_failures():
    """Transient failures (launch error, timeout, etc.) are classified as INFRASTRUCTURE_ERROR."""
    from oompah.terminal_audit import FailureClassification

    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    candidate = Candidate("provider-a", "model-a")
    lane = _lane([candidate], now=now)

    plan, _ = lane.plan(_record(), [], branch_key="epic:EPIC-1")
    assert plan is not None
    persisted = lane.persist_plan(_record(), plan)

    # Finish with infrastructure error classification
    ended = lane.finish_attempt(
        persisted,
        plan.attempt_id,
        reason="transport error: connection timeout",
        ended_at="2026-07-29T00:01:00+00:00",
        failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
    )
    assert ended.attempts[0].failure_classification == FailureClassification.INFRASTRUCTURE_ERROR
    assert ended.attempts[0].failure_reason == "transport error: connection timeout"
    assert ended.attempts[0].request_state == RequestState.PENDING


def test_transient_failure_with_backoff_enables_later_retry():
    """After transient failure with backoff, attempt becomes ready after delay."""
    from oompah.terminal_audit import FailureClassification

    now = datetime(2026, 7, 29, 12, 0, 0, tzinfo=timezone.utc)
    candidate = Candidate("provider-a", "model-a")
    lane = _lane([candidate], now=now)

    plan, _ = lane.plan(_record(), [], branch_key="epic:EPIC-1", now=now)
    assert plan is not None
    persisted = lane.persist_plan(_record(), plan)

    # Simulate transient failure with 30-second backoff
    later = now + timedelta(seconds=20)
    failed = lane.finish_attempt(
        persisted,
        plan.attempt_id,
        reason="auditor launch failed: provider rate limit",
        ended_at=later.isoformat(),
        retry_after=(later + timedelta(seconds=30)).isoformat(),
        failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
    )

    # Before backoff period: not ready
    recovery_cooling = lane.recover(
        failed, active_attempt_identities=set(), now=later
    )
    assert not recovery_cooling.ready
    assert "backoff" in (recovery_cooling.reason or "")

    # After backoff period: ready to retry
    later_after_backoff = later + timedelta(seconds=31)
    recovery_ready = lane.recover(
        failed,
        active_attempt_identities=set(),
        now=later_after_backoff,
    )
    assert recovery_ready.ready
    assert recovery_ready.reason is None


def test_exhausted_candidates_after_multiple_failures():
    """Multiple transient failures against all candidates leaves audit exhausted."""
    from oompah.terminal_audit import FailureClassification

    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    candidates = [
        Candidate("provider-a", "model-a"),
        Candidate("provider-b", "model-b"),
    ]
    lane = _lane(candidates, now=now, max_attempts=2)

    record = _record()

    # First candidate fails with transient error
    plan1, _ = lane.plan(record, [], branch_key="branch-1")
    assert plan1 is not None
    persisted1 = lane.persist_plan(record, plan1)
    failed1 = lane.finish_attempt(
        persisted1,
        plan1.attempt_id,
        reason="transport error",
        failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
    )

    # Second candidate fails with transient error
    plan2, _ = lane.plan(failed1, [], branch_key="branch-1")
    assert plan2 is not None
    persisted2 = lane.persist_plan(failed1, plan2)
    failed2 = lane.finish_attempt(
        persisted2,
        plan2.attempt_id,
        reason="timeout",
        failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
    )

    # All candidates exhausted
    plan3, reason = lane.plan(failed2, [], branch_key="branch-1")
    assert plan3 is None
    assert reason is not None
    assert reason.reason == "all_attempted"
    assert len(failed2.attempts) == 2


def test_successful_retry_after_transient_failure():
    """Auditor can succeed on second attempt after transient failure on first."""
    from oompah.terminal_audit import FailureClassification, Verdict

    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    candidates = [
        Candidate("provider-a", "model-a"),
        Candidate("provider-b", "model-b"),
    ]
    lane = _lane(candidates, now=now)

    record = _record()

    # First attempt: launch fails with infrastructure error
    plan1, _ = lane.plan(record, [], branch_key="branch-1")
    assert plan1 is not None
    persisted1 = lane.persist_plan(record, plan1)
    failed1 = lane.finish_attempt(
        persisted1,
        plan1.attempt_id,
        reason="provider temporarily unavailable",
        failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
    )

    # Second attempt: rotated to new candidate and succeeds
    plan2, _ = lane.plan(failed1, [], branch_key="branch-1")
    assert plan2 is not None
    assert (plan2.candidate.provider_id, plan2.candidate.model) == ("provider-b", "model-b")
    persisted2 = lane.persist_plan(failed1, plan2)

    # Simulate successful completion by marking the second attempt with passing verdict
    completed_attempts = [
        # First attempt: marked failed with infrastructure error
        failed1.attempts[0],
        # Second attempt: marked successful
        replace(
            persisted2.attempts[-1],
            verdict=Verdict.PASS,
            request_state=RequestState.PENDING,
        ),
    ]
    completed = replace(persisted2, attempts=completed_attempts)

    # Verify audit history shows both attempts
    assert len(completed.attempts) == 2
    assert completed.attempts[0].failure_classification == FailureClassification.INFRASTRUCTURE_ERROR
    assert completed.attempts[1].verdict == Verdict.PASS


def test_two_transport_failures_rotate_to_third_healthy_candidate():
    """A healthy independent transport remains eligible after two failures."""
    from oompah.terminal_audit import FailureClassification, Verdict

    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    candidates = [
        Candidate("provider-a", "model-a"),
        Candidate("provider-b", "model-b"),
        Candidate("provider-c", "model-c"),
    ]
    lane = _lane(candidates, now=now, max_attempts=3)
    record = _record()

    for expected_provider in ("provider-a", "provider-b"):
        plan, reason = lane.plan(record, [], branch_key="branch-1")
        assert reason is None
        assert plan is not None
        assert plan.candidate.provider_id == expected_provider
        record = lane.finish_attempt(
            lane.persist_plan(record, plan),
            plan.attempt_id,
            reason="provider-private oversized result denied by audit policy",
            failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
        )

    healthy, reason = lane.plan(record, [], branch_key="branch-1")
    assert reason is None
    assert healthy is not None
    assert healthy.candidate.provider_id == "provider-c"
    persisted = lane.persist_plan(record, healthy)
    completed = replace(
        persisted.attempts[-1],
        verdict=Verdict.PASS,
        request_state=RequestState.PENDING,
    )
    assert completed.verdict == Verdict.PASS
    assert healthy.rotation_count == 2


def test_duplicate_tick_coalescing_prevents_duplicate_dispatch():
    """Concurrent dispatches for same audit do not create duplicate attempts."""
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    candidate = Candidate("provider-a", "model-a")
    
    # Create two lane instances simulating concurrent ticks
    lane1 = AuditorDispatchLane(
        _Selector([candidate]),
        max_attempts=3,
        attempt_ttl_seconds=60,
        clock=lambda: now,
        id_factory=lambda: "attempt-1",
    )
    lane2 = AuditorDispatchLane(
        _Selector([candidate]),
        max_attempts=3,
        attempt_ttl_seconds=60,
        clock=lambda: now,
        id_factory=lambda: "attempt-2",
    )

    record = _record()

    # First tick creates and persists plan
    plan1, _ = lane1.plan(record, [], branch_key="epic:EPIC-1")
    assert plan1 is not None
    persisted1 = lane1.persist_plan(record, plan1)

    # Second concurrent tick sees the in-progress attempt
    recovery = lane2.recover(
        persisted1,
        active_attempt_identities={_active_identity(persisted1, "attempt-1")},
        now=now,
    )
    assert not recovery.ready
    assert "already running" in (recovery.reason or "")

    # Second tick should not create another attempt
    plan2, _ = lane2.plan(recovery.record, [], branch_key="epic:EPIC-1")
    assert plan2 is None  # All candidates already attempted


def test_crash_recovery_marks_attempt_abandoned():
    """When auditor crashes without result, next tick marks attempt abandoned and retries."""
    from oompah.terminal_audit import FailureClassification

    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    candidates = [
        Candidate("provider-a", "model-a"),
        Candidate("provider-b", "model-b"),
    ]
    lane = _lane(candidates, now=now)

    record = _record()
    plan, _ = lane.plan(record, [], branch_key="epic:EPIC-1", now=now)
    assert plan is not None
    persisted = lane.persist_plan(record, plan)

    # Auditor crashes and no live worker owns it
    old = replace(
        persisted,
        attempts=[
            replace(
                persisted.attempts[0],
                started_at=(now - timedelta(seconds=120)).isoformat(),
                created_at=(now - timedelta(seconds=120)).isoformat(),
            )
        ],
    )
    
    # Recovery detects abandoned attempt
    recovery = lane.recover(old, active_attempt_identities=set(), now=now)
    assert recovery.ready
    assert "abandoned" in (recovery.reason or "").lower() or "TTL" in (recovery.reason or "")
    
    # Next plan should rotate to new candidate
    next_plan, _ = lane.plan(recovery.record, [], branch_key="epic:EPIC-1", now=now)
    assert next_plan is not None
    assert next_plan.rotation_count == 1
