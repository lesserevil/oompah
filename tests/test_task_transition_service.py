"""Durability and fencing tests for the task transition service."""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from dataclasses import replace

import pytest

from oompah.models import Issue
from oompah.task_transition_service import (
    CoordinatorTerminalAdapter,
    TaskTransitionService,
    TerminalStageResult,
    TransitionAuthority,
    TransitionDisposition,
    TransitionIntent,
    TransitionJournal,
    TransitionJournalCorruptionError,
    TransitionOutcome,
    TransitionPhase,
    issue_authority_version,
)


class FakeTracker:
    def __init__(self, issue: Issue):
        self.issue = issue
        self.updates: list[tuple[str, str]] = []
        self.fail_before = False
        self.fail_after = False
        self.fetch_failures = 0
        self.block_update: threading.Event | None = None
        self.update_entered = threading.Event()

    def fetch_issue_detail(self, identifier: str):
        if self.fetch_failures:
            self.fetch_failures -= 1
            raise RuntimeError("tracker read failed")
        if identifier != self.issue.identifier:
            return None
        return replace(self.issue)

    def update_issue(self, identifier: str, **fields: str) -> None:
        assert identifier == self.issue.identifier
        self.update_entered.set()
        if self.block_update is not None:
            assert self.block_update.wait(timeout=5)
        if self.fail_before:
            self.fail_before = False
            raise RuntimeError("failed before effect")
        status = fields["status"]
        self.updates.append((identifier, status))
        self.issue = replace(self.issue, state=status)
        if self.fail_after:
            self.fail_after = False
            raise RuntimeError("lost acknowledgement")


class FakeTerminalAdapter:
    def __init__(self, tracker: FakeTracker):
        self.tracker = tracker
        self.calls = 0
        self.fail_after = False

    async def stage(self, intent, issue):
        self.calls += 1
        self.tracker.issue = replace(self.tracker.issue, state="In Validation")
        if self.fail_after:
            raise RuntimeError("lost terminal acknowledgement")
        return TerminalStageResult(True, "audit-1")


def _issue(**overrides) -> Issue:
    values = {
        "id": "TASK-1",
        "identifier": "TASK-1",
        "title": "Test",
        "state": "Open",
        "project_id": "project-1",
        "work_branch": "task-1",
        "target_branch": "main",
        "assignment_id": "generation-1",
        "head_sha": "a" * 40,
    }
    values.update(overrides)
    return Issue(**values)


def _intent(issue: Issue, **overrides) -> TransitionIntent:
    values = {
        "project_id": "project-1",
        "task_id": issue.identifier,
        "expected_status": issue.state,
        "expected_version": issue_authority_version(issue),
        "requested_status": "In Progress",
        "actor": "worker-1",
        "authority": TransitionAuthority.WORKER,
        "reason_code": "dispatch.eligible",
        "idempotency_key": "job-1:claim",
        "originating_job": "job-1",
        "evidence_generation": "generation-1",
    }
    values.update(overrides)
    return TransitionIntent(**values)


def _service(tmp_path, tracker, **overrides):
    journal = overrides.pop("journal", None) or TransitionJournal(
        str(tmp_path / "transitions.sqlite3")
    )
    return TaskTransitionService(
        project_id="project-1",
        tracker=tracker,
        journal=journal,
        **overrides,
    )


def test_intent_is_canonical_and_has_stable_round_trip():
    issue = _issue()
    intent = _intent(issue, expected_status="open", requested_status="in progress")

    assert intent.expected_status == "Open"
    assert intent.requested_status == "In Progress"
    assert TransitionIntent.from_dict(intent.to_dict()) == intent
    assert TransitionIntent.from_dict(intent.to_dict()).revision == intent.revision


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("expected_version", "", "expected_version"),
        ("actor", "", "actor"),
        ("reason_code", "Not Stable", "reason_code"),
        ("idempotency_key", "", "idempotency_key"),
        ("originating_job", "", "originating_job"),
        ("exact_head", "xyz", "exact_head"),
        ("authority", "root", "authority"),
    ],
)
def test_intent_rejects_incomplete_or_unstable_fields(field, value, message):
    issue = _issue()
    with pytest.raises(ValueError, match=message):
        _intent(issue, **{field: value})


def test_authority_version_ignores_benign_tracker_timestamp_churn():
    issue = _issue()
    changed = replace(issue, updated_at=None, description="new prose", labels=["x"])

    assert issue_authority_version(changed) == issue_authority_version(issue)
    assert issue_authority_version(
        replace(issue, assignment_id="generation-2")
    ) != issue_authority_version(issue)
    assert issue_authority_version(
        replace(issue, state="In Progress")
    ) != issue_authority_version(issue)


@pytest.mark.asyncio
async def test_applies_and_verifies_a_nonterminal_transition(tmp_path):
    tracker = FakeTracker(_issue())
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue)

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert outcome.applied_status == "In Progress"
    assert tracker.updates == [("TASK-1", "In Progress")]
    assert [event.phase for event in service.journal.events(outcome.transition_id)] == [
        TransitionPhase.REQUESTED,
        TransitionPhase.APPLYING,
        TransitionPhase.APPLIED,
    ]


@pytest.mark.asyncio
async def test_project_scopes_native_issue_before_authority_compare(tmp_path):
    issue = _issue(project_id=None)
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)
    scoped = replace(issue, project_id="project-1")
    intent = _intent(scoped)

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "In Progress")]


@pytest.mark.asyncio
async def test_replay_is_idempotent_and_does_not_write_again(tmp_path):
    tracker = FakeTracker(_issue())
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue)

    first = await service.execute(intent)
    second = await service.execute(intent)

    assert second.transition_id == first.transition_id
    assert second.replayed is True
    assert tracker.updates == [("TASK-1", "In Progress")]


@pytest.mark.asyncio
async def test_same_key_with_different_intent_is_rejected(tmp_path):
    tracker = FakeTracker(_issue())
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue)
    await service.execute(intent)

    conflict = await service.execute(replace(intent, actor="worker-2"))

    assert conflict.disposition is TransitionDisposition.REJECTED
    assert conflict.reason_code == "transition.idempotency_conflict"
    assert tracker.updates == [("TASK-1", "In Progress")]
    replay = await service.execute(intent)
    assert replay.disposition is TransitionDisposition.APPLIED
    assert replay.replayed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"state": "Needs Human"}, "transition.stale_status"),
        ({"assignment_id": "generation-2"}, "transition.stale_version"),
        ({"head_sha": "b" * 40}, "transition.stale_version"),
    ],
)
async def test_stale_authority_is_rejected(tmp_path, mutation, reason):
    original = _issue()
    intent = _intent(original)
    tracker = FakeTracker(replace(original, **mutation))
    service = _service(tmp_path, tracker)

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.REJECTED
    assert outcome.reason_code == reason
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_project_scope_is_checked_before_journaling(tmp_path):
    tracker = FakeTracker(_issue())
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue, project_id="project-2")

    outcome = await service.execute(intent)

    assert outcome.reason_code == "transition.project_mismatch"
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_tracker_project_mismatch_is_journaled(tmp_path):
    original = _issue()
    tracker = FakeTracker(replace(original, project_id="project-2"))
    service = _service(tmp_path, tracker)
    intent = _intent(original)

    outcome = await service.execute(intent)

    assert outcome.reason_code == "transition.project_mismatch"
    assert (
        service.journal.latest_event(outcome.transition_id).phase
        is TransitionPhase.REJECTED
    )


@pytest.mark.asyncio
async def test_illegal_lifecycle_edge_is_rejected(tmp_path):
    tracker = FakeTracker(_issue())
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue, requested_status="Merged", exact_head="a" * 40)

    outcome = await service.execute(intent)

    assert outcome.reason_code == "transition.illegal_edge"
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_in_progress_requires_an_implementation_generation(tmp_path):
    tracker = FakeTracker(_issue())
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue, evidence_generation=None)

    outcome = await service.execute(intent)

    assert outcome.reason_code == "transition.generation_required"


@pytest.mark.asyncio
async def test_implementation_generation_must_match_tracker_authority(tmp_path):
    tracker = FakeTracker(_issue())
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue, evidence_generation="generation-2")

    outcome = await service.execute(intent)

    assert outcome.reason_code == "transition.generation_mismatch"
    assert outcome.details == {"observed_generation": "generation-1"}


@pytest.mark.asyncio
async def test_landing_transition_requires_an_exact_head(tmp_path):
    issue = _issue(state="In Review")
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker, terminal_adapter=FakeTerminalAdapter(tracker))
    intent = _intent(
        issue,
        requested_status="Merged",
        exact_head=None,
        evidence_generation=None,
    )

    outcome = await service.execute(intent)

    assert outcome.reason_code == "transition.head_required"


@pytest.mark.asyncio
async def test_exact_head_is_fenced(tmp_path):
    tracker = FakeTracker(_issue())
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue, exact_head="b" * 40)

    outcome = await service.execute(intent)

    assert outcome.reason_code == "transition.head_mismatch"
    assert outcome.details == {"observed_head": "a" * 40}


@pytest.mark.asyncio
async def test_failure_before_effect_is_retryable_with_same_intent(tmp_path):
    tracker = FakeTracker(_issue())
    tracker.fail_before = True
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue)

    failed = await service.execute(intent)
    recovered = await service.execute(intent)

    assert failed.disposition is TransitionDisposition.RETRYABLE
    assert failed.reason_code == "transition.tracker_write_failed"
    assert recovered.disposition is TransitionDisposition.APPLIED
    assert tracker.issue.state == "In Progress"


@pytest.mark.asyncio
async def test_failure_after_effect_is_verified_as_recovered(tmp_path):
    tracker = FakeTracker(_issue())
    tracker.fail_after = True
    service = _service(tmp_path, tracker)

    outcome = await service.execute(_intent(tracker.issue))

    assert outcome.disposition is TransitionDisposition.RECOVERED
    assert outcome.reason_code == "transition.effect_recovered"
    assert tracker.issue.state == "In Progress"


@pytest.mark.asyncio
async def test_already_applied_state_is_recovered_without_write(tmp_path):
    before = _issue()
    tracker = FakeTracker(replace(before, state="In Progress"))
    service = _service(tmp_path, tracker)

    outcome = await service.execute(_intent(before))

    assert outcome.disposition is TransitionDisposition.ALREADY_APPLIED
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_cross_service_concurrent_writer_observes_durable_owner(tmp_path):
    path = str(tmp_path / "transitions.sqlite3")
    tracker = FakeTracker(_issue())
    release = threading.Event()
    tracker.block_update = release
    first_service = _service(tmp_path, tracker, journal=TransitionJournal(path))
    second_service = _service(tmp_path, tracker, journal=TransitionJournal(path))
    first_intent = _intent(tracker.issue)
    second_intent = replace(
        first_intent,
        idempotency_key="job-2:claim",
        originating_job="job-2",
        actor="worker-2",
    )

    first_task = asyncio.create_task(first_service.execute(first_intent))
    assert await asyncio.to_thread(tracker.update_entered.wait, 5)
    second = await second_service.execute(second_intent)
    release.set()
    first = await first_task

    assert first.disposition is TransitionDisposition.APPLIED
    assert second.disposition is TransitionDisposition.WAITING
    assert second.reason_code == "transition.owner_active"
    assert tracker.updates == [("TASK-1", "In Progress")]


@pytest.mark.asyncio
async def test_terminal_stage_is_recovered_only_after_a_journaled_apply(tmp_path):
    issue = _issue(state="In Validation")
    tracker = FakeTracker(issue)
    adapter = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=adapter)
    intent = _intent(
        issue,
        requested_status="Done",
        exact_head="a" * 40,
        evidence_generation=None,
    )
    started = service.journal.begin(intent)
    service.journal.append(
        started.transition_id,
        TransitionPhase.APPLYING,
        intent.reason_code,
    )
    service.journal.release(
        intent.project_id,
        intent.task_id,
        started.claim_token,
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.RECOVERED
    assert outcome.reason_code == "transition.terminal_stage_recovered"
    assert adapter.calls == 0
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_fresh_in_validation_terminal_intent_still_calls_adapter(tmp_path):
    issue = _issue(state="In Validation")
    tracker = FakeTracker(issue)
    adapter = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=adapter)
    intent = _intent(
        issue,
        requested_status="Done",
        exact_head="a" * 40,
        evidence_generation=None,
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.STAGED
    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_new_terminal_request_uses_adapter_and_never_directly_writes_target(
    tmp_path,
):
    issue = _issue(state="In Review")
    tracker = FakeTracker(issue)
    adapter = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=adapter)
    intent = _intent(
        issue,
        requested_status="Merged",
        exact_head="a" * 40,
        evidence_generation=None,
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.STAGED
    assert outcome.audit_id == "audit-1"
    assert tracker.issue.state == "In Validation"
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_lost_terminal_acknowledgement_is_recovered(tmp_path):
    issue = _issue(state="In Review")
    tracker = FakeTracker(issue)
    adapter = FakeTerminalAdapter(tracker)
    adapter.fail_after = True
    service = _service(tmp_path, tracker, terminal_adapter=adapter)
    intent = _intent(
        issue,
        requested_status="Merged",
        exact_head="a" * 40,
        evidence_generation=None,
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.RECOVERED
    assert outcome.reason_code == "transition.terminal_stage_recovered"


@pytest.mark.asyncio
async def test_missing_terminal_adapter_is_retryable(tmp_path):
    issue = _issue(state="In Review")
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)
    intent = _intent(
        issue,
        requested_status="Merged",
        exact_head="a" * 40,
        evidence_generation=None,
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.RETRYABLE
    assert outcome.reason_code == "transition.terminal_service_unavailable"


@pytest.mark.asyncio
async def test_initial_tracker_read_failure_is_retryable(tmp_path):
    tracker = FakeTracker(_issue())
    tracker.fetch_failures = 1
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue)

    failed = await service.execute(intent)
    applied = await service.execute(intent)

    assert failed.reason_code == "transition.tracker_read_failed"
    assert failed.retryable is True
    assert applied.disposition is TransitionDisposition.APPLIED


@pytest.mark.asyncio
async def test_coordinator_adapter_passes_canonical_evidence():
    class Coordinator:
        def __init__(self):
            self.kwargs = None

        async def request_transition(self, **kwargs):
            self.kwargs = kwargs
            return type(
                "Result", (), {"success": True, "audit_id": "audit-x", "reason": None}
            )()

    coordinator = Coordinator()
    issue = _issue(state="In Review")
    intent = _intent(
        issue,
        requested_status="Merged",
        exact_head="a" * 40,
        evidence_generation=None,
    )

    result = await CoordinatorTerminalAdapter(coordinator).stage(intent, issue)

    assert result == TerminalStageResult(True, "audit-x")
    assert coordinator.kwargs["project_id"] == "project-1"
    assert coordinator.kwargs["requested_target"].value == "Merged"
    assert coordinator.kwargs["trigger_identity"].identity == "worker-1"
    assert len(coordinator.kwargs["evidence_fingerprint"].digest) == 64


def test_journal_survives_restart_and_preserves_event_order(tmp_path):
    path = str(tmp_path / "transitions.sqlite3")
    issue = _issue()
    intent = _intent(issue)
    first = TransitionJournal(path)
    started = first.begin(intent)
    first.append(started.transition_id, TransitionPhase.APPLYING, intent.reason_code)
    first.release(intent.project_id, intent.task_id, started.claim_token)
    first.close()

    restarted = TransitionJournal(path)
    assert restarted.load_intent(started.transition_id) == intent
    assert [event.phase for event in restarted.events(started.transition_id)] == [
        TransitionPhase.REQUESTED,
        TransitionPhase.APPLYING,
    ]
    resumed = restarted.begin(intent)
    assert resumed.transition_id == started.transition_id
    assert resumed.claim_token is not None


def test_journal_tables_are_append_only(tmp_path):
    journal = TransitionJournal(str(tmp_path / "transitions.sqlite3"))
    started = journal.begin(_intent(_issue()))

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        journal._conn.execute(  # noqa: SLF001 - architectural invariant probe
            "UPDATE task_transition_events SET reason_code = 'changed' WHERE transition_id = ?",
            (started.transition_id,),
        )
    journal._conn.rollback()  # noqa: SLF001
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        journal._conn.execute(  # noqa: SLF001
            "DELETE FROM task_transition_requests WHERE transition_id = ?",
            (started.transition_id,),
        )
    journal._conn.rollback()  # noqa: SLF001


def test_integrity_check_rejects_corrupt_immutable_payload(tmp_path):
    journal = TransitionJournal(str(tmp_path / "transitions.sqlite3"))
    started = journal.begin(_intent(_issue()))
    # INSERT remains legal because journal history is append-only. Simulate a
    # malformed legacy/process write that the reader must fail closed on.
    journal._conn.execute(  # noqa: SLF001
        """
        INSERT INTO task_transition_events(
            transition_id, project_id, task_id, phase, reason_code,
            outcome_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            started.transition_id,
            "project-1",
            "TASK-1",
            "applied",
            "transition.applied",
            "not-json",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    journal._conn.commit()  # noqa: SLF001

    with pytest.raises(TransitionJournalCorruptionError, match="outcome JSON"):
        journal.integrity_check()


def test_expired_foreign_claim_requires_recovery_before_new_intent(tmp_path):
    clock = [100.0]
    path = str(tmp_path / "transitions.sqlite3")
    journal = TransitionJournal(path, clock=lambda: clock[0])
    issue = _issue()
    first = _intent(issue)
    first_started = journal.begin(first, lease_ttl_seconds=10)
    assert first_started.claim_token
    clock[0] = 111.0
    second = replace(first, idempotency_key="job-2", originating_job="job-2")

    waiting = journal.begin(second, lease_ttl_seconds=10)

    assert waiting.waiting.reason_code == "transition.recovery_required"
    resumed = journal.begin(first, lease_ttl_seconds=10)
    assert resumed.transition_id == first_started.transition_id
    assert resumed.claim_token is not None


def test_replay_of_final_intent_cleans_claim_left_by_process_death(tmp_path):
    journal = TransitionJournal(str(tmp_path / "transitions.sqlite3"))
    issue = _issue()
    intent = _intent(issue)
    started = journal.begin(intent)
    outcome = TransitionOutcome(
        transition_id=started.transition_id,
        project_id=intent.project_id,
        task_id=intent.task_id,
        disposition=TransitionDisposition.APPLIED,
        reason_code="transition.applied",
        observed_status="In Progress",
        observed_version="revision",
        requested_status="In Progress",
        applied_status="In Progress",
    )
    journal.append(
        started.transition_id,
        TransitionPhase.APPLIED,
        outcome.reason_code,
        outcome,
    )
    # Deliberately do not release started.claim_token.

    replay = journal.begin(intent)
    next_intent = replace(
        intent,
        requested_status="Needs Human",
        expected_status="In Progress",
        expected_version="next-revision",
        idempotency_key="job-2",
        originating_job="job-2",
    )
    following = journal.begin(next_intent)

    assert replay.replay.replayed is True
    assert following.claim_token is not None
