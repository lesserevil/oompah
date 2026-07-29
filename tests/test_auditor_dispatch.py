"""Tests for durable independent-auditor scheduling policy."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
from types import SimpleNamespace

from oompah.auditor_dispatch import AuditorDispatchLane, audit_branch_key
from oompah.auditor_candidate_selector import NoCandidateReason
from oompah.roles import Candidate
from oompah.terminal_audit import (
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)


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

    recovery = lane.recover(persisted, active_attempt_ids=set(), now=now)
    assert recovery.ready
    assert "no live worker" in (recovery.reason or "")
    assert recovery.record.request_state == RequestState.PENDING
    assert recovery.record.attempts[0].request_state == RequestState.PENDING


def test_live_attempt_is_not_duplicated_and_timeout_is_recoverable():
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    lane = _lane([Candidate("provider-a", "model-a")], now=now)
    plan, _ = lane.plan(_record(), [], branch_key="branch-1", now=now)
    assert plan is not None
    persisted = lane.persist_plan(_record(), plan)

    live = lane.recover(persisted, active_attempt_ids={plan.attempt_id}, now=now)
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
        active_old, active_attempt_ids={plan.attempt_id}, now=now
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
    expired = lane.recover(old, active_attempt_ids=set(), now=now)
    assert expired.ready
    assert "TTL" in (expired.reason or "")

    backoff_record = lane.finish_attempt(
        persisted,
        plan.attempt_id,
        reason="rate limit",
        ended_at=now.isoformat(),
        retry_after=(now + timedelta(seconds=10)).isoformat(),
    )
    cooling = lane.recover(backoff_record, active_attempt_ids=set(), now=now)
    assert not cooling.ready
    assert "backoff" in (cooling.reason or "")
    ready = lane.recover(
        backoff_record,
        active_attempt_ids=set(),
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

    live = lane.recover(changed, active_attempt_ids={plan.attempt_id}, now=now)
    assert not live.ready
    assert "while auditor is running" in (live.reason or "")

    abandoned = lane.recover(changed, active_attempt_ids=set(), now=now)
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
