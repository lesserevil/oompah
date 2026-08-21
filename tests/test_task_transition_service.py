"""Durability and fencing tests for the task transition service."""

from __future__ import annotations

import asyncio
import copy
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import pytest

from oompah.integration import IntegrationRecord
from oompah.models import Issue
from oompah.task_transition_service import (
    CoordinatorTerminalAdapter,
    TaskTransitionService,
    TerminalStageResult,
    TransitionAuthority,
    TransitionDisposition,
    TransitionIntent,
    TransitionJournal,
    TransitionJournalClosedError,
    TransitionJournalCorruptionError,
    TransitionOutcome,
    TransitionPhase,
    issue_authority_version,
    issue_exact_head,
    rollup_authority_generation,
)
from oompah.terminal_transition_coordinator import TerminalTransitionCoordinator


class FakeTracker:
    def __init__(self, issue: Issue):
        self.issue = issue
        self.children: list[Issue] = []
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

    def fetch_children(self, _parent_id: str):
        return [replace(child) for child in self.children]

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


def test_mutation_guard_exception_is_logged_with_safe_transition_identity(
    tmp_path, caplog
):
    issue = _issue()
    tracker = FakeTracker(issue)

    def broken_guard(_intent, _issue):
        raise RuntimeError("guard exploded")

    service = _service(tmp_path, tracker, mutation_guard=broken_guard)
    intent = _intent(
        issue,
        requested_status="Ready to Integrate",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="implementation.validation_submission",
        exact_head=issue.head_sha,
    )

    with caplog.at_level("ERROR"):
        outcome = asyncio.run(service.execute(intent))

    assert outcome.reason_code == "transition.mutation_guard_failed"
    assert (
        "project=project-1 task=TASK-1 "
        "reason=implementation.validation_submission"
    ) in caplog.text
    assert "guard exploded" in caplog.text


def test_journal_close_drains_admitted_transition_saga(tmp_path):
    """Retirement cannot close SQLite between a transition's journal writes."""

    issue = _issue()
    tracker = FakeTracker(issue)
    fetch_entered = threading.Event()
    release_fetch = threading.Event()
    close_started = threading.Event()
    close_finished = threading.Event()
    original_fetch = tracker.fetch_issue_detail

    def blocked_fetch(identifier: str):
        fetch_entered.set()
        assert release_fetch.wait(timeout=3)
        return original_fetch(identifier)

    tracker.fetch_issue_detail = blocked_fetch
    path = tmp_path / "close-drains-transition.sqlite3"
    journal = TransitionJournal(str(path))
    service = _service(tmp_path, tracker, journal=journal)

    def close_journal() -> None:
        close_started.set()
        journal.close()
        close_finished.set()

    async def scenario():
        transition = asyncio.create_task(service.execute(_intent(issue)))
        assert await asyncio.to_thread(fetch_entered.wait, 1)
        closing = asyncio.create_task(asyncio.to_thread(close_journal))
        assert await asyncio.to_thread(close_started.wait, 1)
        deadline = asyncio.get_running_loop().time() + 1
        while asyncio.get_running_loop().time() < deadline:
            with journal._lifecycle_condition:
                if journal._closing:
                    break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("journal retirement did not fence admission")
        assert close_finished.is_set() is False
        with pytest.raises(
            TransitionJournalClosedError,
            match="transition journal is closing or closed",
        ):
            await service.execute(_intent(issue, idempotency_key="job-concurrent"))

        release_fetch.set()
        outcome = await transition
        await closing
        return outcome

    try:
        outcome = asyncio.run(scenario())
    finally:
        release_fetch.set()

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.issue.state == "In Progress"
    assert tracker.updates == [(issue.identifier, "In Progress")]
    assert close_finished.is_set() is True

    reopened = TransitionJournal(str(path))
    try:
        assert (
            reopened.events(outcome.transition_id)[-1].phase
            is TransitionPhase.APPLIED
        )
    finally:
        reopened.close()

    # Retirement is idempotent and permanently fences later transition work.
    journal.close()
    with pytest.raises(
        TransitionJournalClosedError,
        match="transition journal is closing or closed",
    ):
        asyncio.run(service.execute(_intent(tracker.issue, idempotency_key="job-2")))


def test_journal_close_drains_direct_use_and_fences_late_callers(tmp_path):
    """Every public journal operation participates in the close boundary."""

    journal = TransitionJournal(str(tmp_path / "close-drains-reader.sqlite3"))
    reader_result = []
    reader_finished = threading.Event()
    close_finished = threading.Event()

    def read_events() -> None:
        reader_result.append(journal.events("missing-transition"))
        reader_finished.set()

    def close_journal() -> None:
        journal.close()
        close_finished.set()

    journal._lock.acquire()
    reader = threading.Thread(target=read_events)
    closer = threading.Thread(target=close_journal)
    try:
        reader.start()
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with journal._lifecycle_condition:
                if journal._active_uses == 1:
                    break
            time.sleep(0.01)
        else:
            raise AssertionError("direct reader did not acquire a lifetime lease")

        closer.start()
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with journal._lifecycle_condition:
                if journal._closing:
                    break
            time.sleep(0.01)
        else:
            raise AssertionError("journal retirement did not fence direct uses")

        with pytest.raises(
            TransitionJournalClosedError,
            match="transition journal is closing or closed",
        ):
            journal.integrity_check()
        assert reader_finished.is_set() is False
        assert close_finished.is_set() is False
    finally:
        journal._lock.release()
        reader.join(timeout=1)
        closer.join(timeout=1)

    assert reader_result == [()]
    assert reader_finished.is_set() is True
    assert close_finished.is_set() is True


def test_intent_is_canonical_and_has_stable_round_trip():
    issue = _issue()
    intent = _intent(
        issue,
        expected_status="open",
        requested_status="in progress",
        precondition_revision="facts-v2",
    )

    assert intent.expected_status == "Open"
    assert intent.requested_status == "In Progress"
    assert TransitionIntent.from_dict(intent.to_dict()) == intent
    assert TransitionIntent.from_dict(intent.to_dict()).revision == intent.revision
    assert intent.precondition_revision == "facts-v2"


def test_legacy_intent_serialization_omits_optional_precondition():
    intent = _intent(_issue())

    assert "precondition_revision" not in intent.to_dict()
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
    changed = replace(issue, updated_at=None, labels=["x"])

    assert issue_authority_version(changed) == issue_authority_version(issue)
    assert issue_authority_version(
        replace(issue, description="new requirements")
    ) != issue_authority_version(issue)
    assert issue_authority_version(
        replace(issue, assignment_id="generation-2")
    ) != issue_authority_version(issue)
    assert issue_authority_version(
        replace(issue, state="In Progress")
    ) != issue_authority_version(issue)
    assert issue_authority_version(
        replace(issue, lifecycle_revision=1)
    ) != issue_authority_version(issue)
    assert issue_authority_version(
        replace(issue, parent_id="OTHER-EPIC")
    ) != issue_authority_version(issue)
    assert issue_authority_version(
        replace(issue, title="Rebase epic-TASK-1 onto main")
    ) != issue_authority_version(issue)
    assert issue_authority_version(
        replace(issue, labels=["merge-conflict"])
    ) != issue_authority_version(issue)


def test_authority_version_fences_direct_maintenance_handoff_proof():
    proven = _issue(
        title="Rebase epic-EPIC-1 onto main",
        parent_id="EPIC-1",
        integration=IntegrationRecord(
            state="integrated",
            mode="queue",
            task_branch="epic-EPIC-1",
            base_branch="epic-EPIC-1",
            head_sha="a" * 40,
            integrated_sha="a" * 40,
            maintenance_publication_proven=True,
        ),
    )
    revoked = replace(
        proven,
        integration=replace(
            proven.integration,
            maintenance_publication_proven=False,
        ),
    )

    assert issue_authority_version(revoked) != issue_authority_version(proven)


@pytest.mark.asyncio
async def test_post_build_maintenance_proof_revocation_fails_transition_cas(
    tmp_path,
):
    proven = _issue(
        title="Rebase epic-EPIC-1 onto main",
        parent_id="EPIC-1",
        integration=IntegrationRecord(
            state="integrated",
            mode="queue",
            task_branch="epic-EPIC-1",
            base_branch="epic-EPIC-1",
            head_sha="a" * 40,
            integrated_sha="a" * 40,
            maintenance_publication_proven=True,
        ),
    )
    tracker = FakeTracker(proven)
    terminal = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=terminal)
    intent = _intent(
        proven,
        requested_status="Done",
        authority=TransitionAuthority.AUDITOR,
        reason_code="maintenance.publication_proven",
    )
    tracker.issue = replace(
        proven,
        integration=replace(
            proven.integration,
            maintenance_publication_proven=False,
        ),
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.REJECTED
    assert outcome.reason_code == "transition.stale_version"
    assert terminal.calls == 0


def test_authority_version_fences_the_exact_integrated_audit_revision():
    issue = _issue(
        state="In Review",
        integration=IntegrationRecord(
            state="integrated",
            task_branch="TASK-1",
            base_branch="main",
            head_sha="a" * 40,
            integrated_sha="b" * 40,
        ),
    )

    changed = replace(
        issue,
        integration=replace(issue.integration, integrated_sha="c" * 40),
    )

    assert issue_authority_version(changed) != issue_authority_version(issue)


def test_review_head_is_exact_authority_when_rollup_has_no_implementation_head():
    issue = _issue(head_sha=None, integration=None, review_head="b" * 40)

    assert issue_exact_head(issue) == "b" * 40
    assert issue_authority_version(
        replace(issue, review_head="c" * 40)
    ) != issue_authority_version(issue)
    assert issue_authority_version(
        replace(issue, review_number="43")
    ) != issue_authority_version(issue)


def test_live_implementation_head_supersedes_stale_epic_review_head():
    issue = _issue(head_sha="c" * 40, review_head="b" * 40)

    assert issue_exact_head(issue) == "c" * 40


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
async def test_invalid_detail_proxy_falls_back_to_exact_point_read(tmp_path):
    tracker = FakeTracker(_issue())
    tracker.fetch_issue_detail = lambda _identifier: object()
    tracker.fetch_issue_states_by_ids = lambda _identifiers: [replace(tracker.issue)]
    service = _service(tmp_path, tracker)

    outcome = await service.execute(_intent(tracker.issue))

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "In Progress")]


@pytest.mark.asyncio
async def test_authorized_recovery_journals_and_verifies_compensating_status(tmp_path):
    issue = _issue(state="Merged")
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)
    intent = _intent(
        issue,
        requested_status="Done",
        authority=TransitionAuthority.AUDITOR,
        actor="terminal-auditor",
        reason_code="audit.shared_epic_done_recovered",
        idempotency_key="audit-recovery-1",
        originating_job="terminal-audit-enforcement",
        evidence_generation=None,
    )

    outcome = await service.recover_authorized(intent)

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert outcome.applied_status == "Done"
    assert tracker.updates == [("TASK-1", "Done")]
    assert [event.phase for event in service.journal.events(outcome.transition_id)] == [
        TransitionPhase.REQUESTED,
        TransitionPhase.APPLYING,
        TransitionPhase.APPLIED,
    ]


@pytest.mark.asyncio
async def test_authorized_recovery_rejects_unapproved_authority_or_reason(tmp_path):
    issue = _issue(state="Merged")
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    worker = await service.recover_authorized(
        _intent(
            issue,
            requested_status="Done",
            authority=TransitionAuthority.WORKER,
            reason_code="audit.result_recovered",
        )
    )
    unscoped_reason = await service.recover_authorized(
        _intent(
            issue,
            requested_status="Done",
            authority=TransitionAuthority.AUDITOR,
            reason_code="worker.result_recovered",
        )
    )
    mismatched_authority = await service.recover_authorized(
        _intent(
            issue,
            requested_status="Done",
            authority=TransitionAuthority.SYSTEM,
            reason_code="audit.result_recovered",
        )
    )

    assert worker.reason_code == "transition.recovery_authority_rejected"
    assert unscoped_reason.reason_code == "transition.recovery_authority_rejected"
    assert mismatched_authority.reason_code == "transition.recovery_authority_rejected"
    assert tracker.updates == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("authority", "reason_code"),
    [
        (TransitionAuthority.SYSTEM, "intake.external_issue_reopened"),
        (
            TransitionAuthority.PROJECT_OWNER,
            "provenance.owner_revision_authorized",
        ),
        (
            TransitionAuthority.PROJECT_OWNER,
            "audit.owner_override_recovered",
        ),
    ],
)
async def test_authorized_recovery_accepts_exact_authority_reason_pairs(
    tmp_path,
    authority,
    reason_code,
):
    issue = _issue(state="Archived")
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    outcome = await service.recover_authorized(
        _intent(
            issue,
            requested_status="Open",
            authority=authority,
            reason_code=reason_code,
            idempotency_key=f"recovery:{authority.value}:{reason_code}",
            evidence_generation=None,
        )
    )

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "Open")]


@pytest.mark.asyncio
async def test_container_cycle_recovery_accepts_only_exact_system_reason(tmp_path):
    issue = _issue(state="Needs Human")
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    accepted = await service.recover_authorized(
        _intent(
            issue,
            requested_status="Ready to Integrate",
            authority=TransitionAuthority.SYSTEM,
            reason_code="maintenance.container_cycle_restored",
            idempotency_key="container-cycle:accepted",
            evidence_generation=None,
            exact_head="a" * 40,
        )
    )

    assert accepted.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "Ready to Integrate")]

    tracker.issue = replace(issue)
    rejected = await service.recover_authorized(
        _intent(
            issue,
            requested_status="Ready to Integrate",
            authority=TransitionAuthority.SYSTEM,
            reason_code="maintenance.container_cycle_restored_unscoped",
            idempotency_key="container-cycle:rejected",
            evidence_generation=None,
            exact_head="a" * 40,
        )
    )

    assert rejected.reason_code == "transition.recovery_authority_rejected"
    assert tracker.updates == [("TASK-1", "Ready to Integrate")]


@pytest.mark.asyncio
async def test_unlanded_done_child_recovery_is_exact_system_compensation(tmp_path):
    issue = _issue(state="Done")
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    outcome = await service.recover_authorized(
        _intent(
            issue,
            requested_status="Needs Human",
            authority=TransitionAuthority.SYSTEM,
            reason_code="maintenance.unlanded_done_child_recovered",
            idempotency_key="unlanded-done-child:accepted",
            evidence_generation=None,
        )
    )

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "Needs Human")]


@pytest.mark.asyncio
async def test_landed_done_child_restore_is_exact_system_compensation(tmp_path):
    issue = _issue(state="Needs Human")
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    outcome = await service.recover_authorized(
        _intent(
            issue,
            requested_status="Done",
            authority=TransitionAuthority.SYSTEM,
            reason_code="maintenance.landed_done_child_restored",
            idempotency_key="landed-done-child:accepted",
            evidence_generation="landing-generation",
        )
    )

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "Done")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "target", "reason_code"),
    [
        ("Archived", "Ready to Integrate", "maintenance.container_cycle_restored"),
        ("Needs Human", "Open", "maintenance.container_cycle_restored"),
        ("Merged", "Needs Human", "maintenance.unlanded_done_child_recovered"),
        ("Done", "Open", "maintenance.unlanded_done_child_recovered"),
        ("Archived", "Done", "maintenance.landed_done_child_restored"),
        ("Needs Human", "Open", "maintenance.landed_done_child_restored"),
    ],
)
async def test_system_compensations_reject_wrong_source_or_target(
    tmp_path,
    source,
    target,
    reason_code,
):
    issue = _issue(state=source)
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    outcome = await service.recover_authorized(
        _intent(
            issue,
            requested_status=target,
            authority=TransitionAuthority.SYSTEM,
            reason_code=reason_code,
            idempotency_key=f"wrong-recovery-edge:{source}:{target}",
            evidence_generation=None,
        )
    )

    assert outcome.reason_code == "transition.recovery_authority_rejected"
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_nonterminal_write_holds_shared_project_lock(tmp_path):
    lock = threading.RLock()

    class LockCheckingTracker(FakeTracker):
        def update_issue(self, identifier: str, **fields: str) -> None:
            assert lock._is_owned()  # type: ignore[attr-defined]
            super().update_issue(identifier, **fields)

    tracker = LockCheckingTracker(_issue())
    service = _service(tmp_path, tracker, write_lock=lambda: lock)

    outcome = await service.execute(_intent(tracker.issue))

    assert outcome.disposition is TransitionDisposition.APPLIED


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
async def test_backlog_direct_claim_requires_project_owner_authority(tmp_path):
    issue = _issue(state="Backlog", assignment_id=None)
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    rejected = await service.execute(
        _intent(
            issue,
            actor="oompah",
            authority=TransitionAuthority.ORCHESTRATOR,
            reason_code="implementation.direct_owner_claim",
            evidence_generation="claim-1",
        )
    )

    assert rejected.disposition is TransitionDisposition.REJECTED
    assert rejected.reason_code == "transition.project_owner_authority_required"
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_existing_api_backlog_promotion_policy_is_unchanged(tmp_path):
    issue = _issue(state="Backlog", assignment_id=None)
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    applied = await service.execute(
        _intent(
            issue,
            requested_status="Open",
            actor="alice",
            authority=TransitionAuthority.API,
            reason_code="api.status_updated",
            evidence_generation=None,
        )
    )

    assert applied.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "Open")]


@pytest.mark.asyncio
async def test_api_authority_allowed_for_backlog_to_in_progress_transition(tmp_path):
    """Test that API authority (oompah's backend:server) can transition from Backlog to In Progress.
    
    This allows oompah to manage its own task transitions through its internal API,
    without requiring PROJECT_OWNER authority for system operations.
    Fixes OOMPAH-1208: backend:server was failing to update task status due to
    missing authority for BACKLOG -> IN_PROGRESS transitions.
    """
    issue = _issue(
        state="Backlog",
        assignment_id=None,
        description="Task with actionable description",
    )
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    applied = await service.execute(
        _intent(
            issue,
            requested_status="In Progress",
            actor="oompah",
            authority=TransitionAuthority.API,
            reason_code="api.status_updated",
            evidence_generation="api-claim-1",
        )
    )

    assert applied.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "In Progress")]


def test_active_claims_for_tasks_returns_only_live_matching_claims(tmp_path):
    issue = _issue(state="Backlog", assignment_id=None)
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)
    intent = _intent(
        issue,
        requested_status="Open",
        actor="alice",
        authority=TransitionAuthority.API,
        reason_code="api.status_updated",
        evidence_generation=None,
    )
    begun = service.journal.begin(intent, lease_ttl_seconds=300)

    assert service.journal.active_claims_for_tasks(
        intent.project_id, [intent.task_id, "TASK-OTHER"]
    ) == frozenset({intent.task_id})

    assert begun.claim_token is not None
    service.journal.release(intent.project_id, intent.task_id, begun.claim_token)
    assert service.journal.active_claims_for_tasks(
        intent.project_id, [intent.task_id]
    ) == frozenset()


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_status", ["Backlog", "Open"])
async def test_project_owner_can_atomically_claim_eligible_work(
    tmp_path,
    initial_status,
):
    issue = _issue(
        state=initial_status,
        assignment_id=None,
        description="Implement the exact owner-scoped task.",
    )
    tracker = FakeTracker(issue)
    commit_lock = threading.RLock()
    service = _service(
        tmp_path,
        tracker,
        direct_owner_write_lock=lambda: commit_lock,
        direct_owner_claim_guard=lambda _intent, _issue: None,
    )

    applied = await service.execute(
        _intent(
            issue,
            actor="alice",
            authority=TransitionAuthority.PROJECT_OWNER,
            reason_code="implementation.direct_owner_claim",
            evidence_generation="claim-1",
        )
    )

    assert applied.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "In Progress")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "reason_code"),
    (
        ("empty_description", "transition.actionable_description_required"),
        ("unrelated_reason", "transition.direct_owner_claim_authority_required"),
        ("invented_claim", "transition.owner_claim_generation_mismatch"),
    ),
)
async def test_backlog_direct_claim_reproves_exact_live_authority_at_commit(
    tmp_path,
    mutation,
    reason_code,
):
    issue = _issue(
        state="Backlog",
        assignment_id=None,
        description=(
            "" if mutation == "empty_description" else "Implement this task."
        ),
    )
    tracker = FakeTracker(issue)
    live_claim_id = "claim-live"
    commit_lock = threading.RLock()

    def claim_guard(intent, _issue):
        if intent.evidence_generation != live_claim_id:
            return "transition.owner_claim_generation_mismatch"
        return None

    service = _service(
        tmp_path,
        tracker,
        direct_owner_write_lock=lambda: commit_lock,
        direct_owner_claim_guard=claim_guard,
    )
    intent = _intent(
        issue,
        actor="alice",
        authority=TransitionAuthority.PROJECT_OWNER,
        reason_code=(
            "owner.unrelated"
            if mutation == "unrelated_reason"
            else "implementation.direct_owner_claim"
        ),
        evidence_generation=(
            "claim-invented" if mutation == "invented_claim" else live_claim_id
        ),
    )

    rejected = await service.execute(intent)

    assert rejected.disposition is TransitionDisposition.REJECTED
    assert rejected.reason_code == reason_code
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_validation_submission_retirement_failure_blocks_ready_commit(
    tmp_path,
):
    issue = _issue(
        state="In Progress",
        integration=IntegrationRecord(
            state="ready",
            mode="standalone",
            task_branch="task-1",
            head_sha="a" * 40,
        ),
    )
    tracker = FakeTracker(issue)
    commit_lock = threading.RLock()

    def fail_retirement(_intent, _issue):
        raise OSError("owner claim store unavailable")

    service = _service(
        tmp_path,
        tracker,
        direct_owner_write_lock=lambda: commit_lock,
        direct_owner_retirement_guard=fail_retirement,
    )
    intent = _intent(
        issue,
        requested_status="Ready to Integrate",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="implementation.validation_submission",
        idempotency_key="validation-retirement-failure",
        originating_job="validation-job",
        exact_head="a" * 40,
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.RETRYABLE
    assert outcome.reason_code == "transition.owner_retirement_persistence_failed"
    assert outcome.retryable is True
    assert tracker.issue.state == "In Progress"
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_exact_accepted_submission_recovers_open_directly_to_ready(tmp_path):
    issue = _issue(
        state="Open",
        integration=IntegrationRecord(
            state="ready",
            mode="standalone",
            task_branch="task-1",
            head_sha="a" * 40,
        ),
    )
    tracker = FakeTracker(issue)
    service = _service(
        tmp_path,
        tracker,
        mutation_guard=lambda _intent, _issue: None,
    )
    intent = _intent(
        issue,
        requested_status="Ready to Integrate",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="implementation.validation_submission",
        idempotency_key="open-validation-recovery",
        originating_job="validation-job",
        exact_head="a" * 40,
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.issue.state == "Ready to Integrate"
    assert tracker.updates == [(issue.identifier, "Ready to Integrate")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("authority", "reason_code"),
    [
        (TransitionAuthority.API, "implementation.validation_submission"),
        (TransitionAuthority.ORCHESTRATOR, "operator.manual_transition"),
    ],
)
async def test_open_to_ready_recovery_requires_validation_orchestrator_authority(
    tmp_path,
    authority,
    reason_code,
):
    issue = _issue(
        state="Open",
        integration=IntegrationRecord(
            state="ready",
            mode="standalone",
            task_branch="task-1",
            head_sha="a" * 40,
        ),
    )
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)
    intent = _intent(
        issue,
        requested_status="Ready to Integrate",
        authority=authority,
        reason_code=reason_code,
        idempotency_key=f"open-validation-recovery-{authority.value}",
        originating_job="validation-job",
        exact_head="a" * 40,
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.REJECTED
    assert (
        outcome.reason_code
        == "transition.validation_submission_authority_required"
    )
    assert tracker.issue.state == "Open"
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_direct_maintenance_can_request_terminal_audit_from_open(tmp_path):
    maintenance = _issue(
        title="Rebase epic-EPIC-1 onto main",
        parent_id="EPIC-1",
        work_branch="epic-EPIC-1",
        target_branch="epic-EPIC-1",
        integration=IntegrationRecord(
            state="integrated",
            mode="queue",
            task_branch="epic-EPIC-1",
            base_branch="epic-EPIC-1",
            head_sha="a" * 40,
            integrated_sha="a" * 40,
            maintenance_publication_proven=True,
        ),
    )
    tracker = FakeTracker(maintenance)
    terminal = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=terminal)
    intent = _intent(
        tracker.issue,
        requested_status="Done",
        authority=TransitionAuthority.AUDITOR,
        reason_code="maintenance.publication_proven",
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.STAGED
    assert terminal.calls == 1
    assert tracker.issue.state == "In Validation"


@pytest.mark.asyncio
async def test_open_audit_request_rejects_non_maintenance_authority(tmp_path):
    tracker = FakeTracker(_issue())
    service = _service(tmp_path, tracker)
    intent = _intent(
        tracker.issue,
        requested_status="Done",
        authority=TransitionAuthority.WORKER,
        reason_code="dispatch.eligible",
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.REJECTED
    assert outcome.reason_code == (
        "transition.maintenance_audit_authority_required"
    )
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_terminal_request_may_enter_audit_via_validation_edge(tmp_path):
    issue = _issue(state="In Progress")
    tracker = FakeTracker(issue)
    adapter = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=adapter)
    intent = _intent(
        issue,
        requested_status="Done",
        exact_head="a" * 40,
        evidence_generation="generation-1",
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.STAGED
    assert tracker.issue.state == "In Validation"
    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_direct_in_validation_requires_atomic_coordinator_staging(tmp_path):
    issue = _issue(state="In Progress")
    tracker = FakeTracker(issue)
    adapter = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=adapter)
    direct = _intent(
        issue,
        requested_status="In Validation",
        actor="api",
        authority=TransitionAuthority.API,
        reason_code="api.status_updated",
        exact_head="a" * 40,
    )

    rejected = await service.execute(direct)
    replayed = await service.execute(direct)

    assert rejected.disposition is TransitionDisposition.REJECTED
    assert rejected.reason_code == "transition.audit_staging_required"
    assert replayed.disposition is TransitionDisposition.REJECTED
    assert replayed.reason_code == rejected.reason_code
    assert replayed.replayed
    assert tracker.issue.state == "In Progress"
    assert tracker.updates == []
    assert adapter.calls == 0
    assert [
        event.phase for event in service.journal.events(rejected.transition_id)
    ] == [TransitionPhase.REQUESTED, TransitionPhase.REJECTED]

    # Rejection releases the exact task claim.  A canonical terminal-target
    # request can immediately acquire it and use the one coordinator staging
    # path; no special direct-In-Validation recovery lane is needed.
    staged = await service.execute(
        replace(
            direct,
            requested_status="Done",
            reason_code="terminal.operator_requested",
            idempotency_key="job-1:terminal-target",
        )
    )

    assert staged.disposition is TransitionDisposition.STAGED
    assert staged.applied_status == "In Validation"
    assert tracker.issue.state == "In Validation"
    assert tracker.updates == []
    assert adapter.calls == 1


@pytest.mark.asyncio
async def test_in_progress_requires_an_implementation_generation(tmp_path):
    tracker = FakeTracker(_issue())
    service = _service(tmp_path, tracker)
    intent = _intent(tracker.issue, evidence_generation=None)

    outcome = await service.execute(intent)

    assert outcome.reason_code == "transition.generation_required"


@pytest.mark.asyncio
async def test_system_epic_rollup_does_not_fabricate_worker_generation(tmp_path):
    issue = _issue(state="In Review", assignment_id=None, issue_type="epic")
    tracker = FakeTracker(issue)
    tracker.children = [
        _issue(
            id="TASK-2",
            identifier="TASK-2",
            parent_id=issue.id,
            state="In Progress",
        )
    ]
    service = _service(tmp_path, tracker)

    outcome = await service.execute(
        _intent(
            issue,
            requested_status="In Progress",
            authority=TransitionAuthority.SYSTEM,
            reason_code="rollup.epic_children_reconciled",
            evidence_generation=rollup_authority_generation(
                issue,
                tracker.children,
            ),
        )
    )

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "In Progress")]


@pytest.mark.asyncio
async def test_system_rollup_accepts_inferred_parent_with_current_children(tmp_path):
    issue = _issue(state="In Review", assignment_id=None, issue_type="feature")
    tracker = FakeTracker(issue)
    tracker.children = [
        _issue(
            id="TASK-2",
            identifier="TASK-2",
            parent_id=issue.id,
            state="In Progress",
        )
    ]
    service = _service(tmp_path, tracker)

    outcome = await service.execute(
        _intent(
            issue,
            requested_status="In Progress",
            authority=TransitionAuthority.SYSTEM,
            reason_code="rollup.epic_children_reconciled",
            evidence_generation=rollup_authority_generation(
                issue,
                tracker.children,
            ),
        )
    )

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "In Progress")]


@pytest.mark.asyncio
async def test_system_rollup_rejects_stale_child_lineage_generation(tmp_path):
    issue = _issue(state="In Review", assignment_id=None, issue_type="epic")
    original_child = _issue(
        id="TASK-2",
        identifier="TASK-2",
        parent_id=issue.id,
        state="Open",
    )
    tracker = FakeTracker(issue)
    tracker.children = [replace(original_child, state="In Progress")]
    service = _service(tmp_path, tracker)

    outcome = await service.execute(
        _intent(
            issue,
            requested_status="In Progress",
            authority=TransitionAuthority.SYSTEM,
            reason_code="rollup.epic_children_reconciled",
            evidence_generation=rollup_authority_generation(
                issue,
                [original_child],
            ),
        )
    )

    assert outcome.reason_code == "transition.rollup_generation_mismatch"
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_system_rollup_reason_rejects_ordinary_task_context(tmp_path):
    issue = _issue(state="In Review", assignment_id=None, issue_type="task")
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    outcome = await service.execute(
        _intent(
            issue,
            requested_status="In Progress",
            authority=TransitionAuthority.SYSTEM,
            reason_code="rollup.epic_children_reconciled",
            evidence_generation="fabricated-rollup-generation",
        )
    )

    assert outcome.reason_code == "transition.rollup_authority_required"
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_other_system_in_progress_transition_still_requires_generation(tmp_path):
    issue = _issue(state="In Review", assignment_id=None)
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)

    outcome = await service.execute(
        _intent(
            issue,
            requested_status="In Progress",
            authority=TransitionAuthority.SYSTEM,
            reason_code="maintenance.unscoped_recovery",
            evidence_generation=None,
        )
    )

    assert outcome.reason_code == "transition.generation_required"
    assert tracker.updates == []


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
async def test_composed_child_landing_head_is_fenced_by_workflow_precondition(
    tmp_path,
):
    issue = _issue(
        state="Done",
        parent_id="EPIC-1",
        work_branch=None,
        target_branch=None,
        head_sha=None,
        integration=None,
    )
    tracker = FakeTracker(issue)
    terminal = FakeTerminalAdapter(tracker)
    journal_path = str(tmp_path / "transitions.sqlite3")
    service = _service(
        tmp_path,
        tracker,
        terminal_adapter=terminal,
        journal=TransitionJournal(journal_path),
    )
    intent = _intent(
        issue,
        requested_status="Merged",
        authority=TransitionAuthority.INTEGRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        exact_head="b" * 40,
        precondition_revision="landing-facts-v2",
    )

    outcome = await service.execute(intent)
    restarted = _service(
        tmp_path,
        tracker,
        terminal_adapter=terminal,
        journal=TransitionJournal(journal_path),
    )
    replayed = await restarted.execute(intent)

    assert outcome.disposition is TransitionDisposition.STAGED
    assert outcome.reason_code == "transition.terminal_staged"
    assert replayed.disposition is TransitionDisposition.STAGED
    assert replayed.replayed
    assert terminal.calls == 1
    assert tracker.issue.state == "In Validation"


@pytest.mark.asyncio
async def test_headless_root_epic_landing_head_reaches_terminal_staging(tmp_path):
    issue = _issue(
        state="In Progress",
        issue_type="epic",
        parent_id=None,
        work_branch=None,
        target_branch=None,
        assignment_id=None,
        head_sha=None,
        integration=None,
    )
    tracker = FakeTracker(issue)
    terminal = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=terminal)
    intent = _intent(
        issue,
        requested_status="Merged",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        evidence_generation="epic-auto-close-generation",
        exact_head="b" * 40,
        precondition_revision="landing-evidence-revision",
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.STAGED
    assert outcome.reason_code == "transition.terminal_staged"
    assert terminal.calls == 1
    assert tracker.issue.state == "In Validation"


@pytest.mark.asyncio
async def test_headless_root_epic_stages_through_real_terminal_boundary(tmp_path):
    class TerminalTracker(FakeTracker):
        def __init__(self, issue):
            super().__init__(issue)
            self.metadata = {}

        def get_metadata(self, identifier):
            assert identifier == self.issue.identifier
            return copy.deepcopy(self.metadata)

        def set_metadata_field(self, identifier, key, value):
            assert identifier == self.issue.identifier
            self.metadata[key] = copy.deepcopy(value)

        def add_comment(self, identifier, text, author="oompah"):
            assert identifier == self.issue.identifier
            return {"id": "comment-1", "text": text, "author": author}

        def current_status(self, identifier):
            assert identifier == self.issue.identifier
            return self.issue.state

    class ProjectStore:
        def __init__(self, revision):
            self.revision = revision
            self.lock = threading.RLock()

        def project_write_lock(self, project_id):
            assert project_id == "project-1"
            return self.lock

        def get(self, project_id):
            return (
                SimpleNamespace(default_branch="main")
                if project_id == "project-1"
                else None
            )

        def resolve_audit_revision(self, project_id, revision):
            assert project_id == "project-1"
            if revision != self.revision:
                raise ValueError("terminal audit revision is unavailable")
            return self.revision

        def resolve_containing_audit_revision(
            self, project_id, *, target_revision, landing_revision
        ):
            assert project_id == "project-1"
            assert target_revision == "origin/main"
            assert landing_revision == self.revision
            return self.revision

    revision = "b" * 40
    issue = _issue(
        state="In Progress",
        issue_type="epic",
        parent_id=None,
        work_branch=None,
        target_branch=None,
        assignment_id=None,
        head_sha=None,
        integration=None,
    )
    tracker = TerminalTracker(issue)
    project_store = ProjectStore(revision)
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    adapter = CoordinatorTerminalAdapter(
        coordinator,
        mutation_guard=lambda _intent: None,
    )
    service = _service(
        tmp_path,
        tracker,
        terminal_adapter=adapter,
        write_lock=lambda: project_store.lock,
    )
    intent = _intent(
        issue,
        requested_status="Merged",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        evidence_generation="epic-auto-close-generation",
        exact_head=revision,
        precondition_revision="landing-evidence-revision",
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.STAGED
    assert outcome.reason_code == "transition.terminal_staged"
    assert outcome.audit_id
    assert tracker.issue.state == "In Validation"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    (
        "wrong_authority",
        "wrong_reason",
        "wrong_target",
        "missing_generation",
        "missing_precondition",
        "non_epic",
        "parented",
        "wrong_status",
    ),
)
async def test_headless_root_epic_cannot_broaden_landing_head_authority(
    tmp_path,
    mutation,
):
    issue_values = {
        "state": "In Progress",
        "issue_type": "epic",
        "parent_id": None,
        "work_branch": None,
        "target_branch": None,
        "assignment_id": None,
        "head_sha": None,
        "integration": None,
    }
    intent_values = {
        "requested_status": "Merged",
        "authority": TransitionAuthority.ORCHESTRATOR,
        "reason_code": "terminal.immediate_target_landing_proven",
        "evidence_generation": "epic-auto-close-generation",
        "exact_head": "b" * 40,
        "precondition_revision": "landing-evidence-revision",
    }
    if mutation == "wrong_authority":
        intent_values["authority"] = TransitionAuthority.INTEGRATOR
    elif mutation == "wrong_reason":
        intent_values["reason_code"] = "rollup.children_complete"
    elif mutation == "wrong_target":
        intent_values["requested_status"] = "Done"
    elif mutation == "missing_generation":
        intent_values["evidence_generation"] = None
    elif mutation == "missing_precondition":
        intent_values["precondition_revision"] = None
    elif mutation == "non_epic":
        issue_values["issue_type"] = "task"
    elif mutation == "parented":
        issue_values["parent_id"] = "EPIC-1"
    elif mutation == "wrong_status":
        issue_values["state"] = "In Review"
    issue = _issue(**issue_values)
    tracker = FakeTracker(issue)
    terminal = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=terminal)
    intent = _intent(issue, **intent_values)

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.REJECTED
    assert outcome.reason_code == "transition.head_missing"
    assert terminal.calls == 0


@pytest.mark.asyncio
async def test_parentless_task_cannot_substitute_landing_for_accepted_head(tmp_path):
    issue = _issue(
        state="Done",
        parent_id=None,
        work_branch=None,
        target_branch=None,
        head_sha=None,
        integration=None,
    )
    tracker = FakeTracker(issue)
    terminal = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=terminal)
    intent = _intent(
        issue,
        requested_status="Merged",
        authority=TransitionAuthority.INTEGRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        exact_head="b" * 40,
        precondition_revision="landing-facts-v2",
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.REJECTED
    assert outcome.reason_code == "transition.head_missing"
    assert terminal.calls == 0


@pytest.mark.asyncio
async def test_non_done_task_cannot_substitute_landing_for_accepted_head(tmp_path):
    issue = _issue(
        state="In Review",
        parent_id="EPIC-1",
        work_branch=None,
        target_branch=None,
        head_sha=None,
        integration=None,
    )
    tracker = FakeTracker(issue)
    terminal = FakeTerminalAdapter(tracker)
    service = _service(tmp_path, tracker, terminal_adapter=terminal)
    intent = _intent(
        issue,
        requested_status="Merged",
        authority=TransitionAuthority.INTEGRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        exact_head="b" * 40,
        precondition_revision="landing-facts-v2",
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.REJECTED
    assert outcome.reason_code == "transition.head_missing"
    assert terminal.calls == 0


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


@pytest.mark.asyncio
async def test_coordinator_adapter_binds_composed_landing_revision():
    class Coordinator:
        def __init__(self):
            self.kwargs = None

        async def request_transition(self, **kwargs):
            self.kwargs = kwargs
            return type(
                "Result", (), {"success": True, "audit_id": "audit-x", "reason": None}
            )()

    coordinator = Coordinator()
    issue = _issue(
        state="Done",
        parent_id="EPIC-1",
        work_branch=None,
        target_branch=None,
        head_sha=None,
        integration=None,
    )
    intent = _intent(
        issue,
        requested_status="Merged",
        authority=TransitionAuthority.INTEGRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        exact_head="b" * 40,
        precondition_revision="landing-facts-v2",
    )

    result = await CoordinatorTerminalAdapter(
        coordinator,
        mutation_guard=lambda _intent: None,
    ).stage(intent, issue)

    assert result.success
    binding = coordinator.kwargs["revision_binding"]
    assert binding.selected_ref == "b" * 40
    assert binding.selected_sha == "b" * 40
    assert (
        coordinator.kwargs["workflow_revision"]
        == "landing-facts-v2"
    )
    assert coordinator.kwargs["mutation_guard"]() is None


@pytest.mark.asyncio
async def test_coordinator_adapter_binds_headless_root_epic_landing_revision():
    class Coordinator:
        def __init__(self):
            self.kwargs = None

        async def request_transition(self, **kwargs):
            self.kwargs = kwargs
            return type(
                "Result", (), {"success": True, "audit_id": "audit-x", "reason": None}
            )()

    coordinator = Coordinator()
    issue = _issue(
        state="In Progress",
        issue_type="epic",
        parent_id=None,
        work_branch=None,
        target_branch=None,
        head_sha=None,
        integration=None,
    )
    intent = _intent(
        issue,
        requested_status="Merged",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        evidence_generation="epic-auto-close-generation",
        exact_head="b" * 40,
        precondition_revision="landing-evidence-revision",
    )

    result = await CoordinatorTerminalAdapter(
        coordinator,
        mutation_guard=lambda _intent: None,
    ).stage(intent, issue)

    assert result.success
    assert coordinator.kwargs["landing_revision"] == "b" * 40
    assert "revision_binding" not in coordinator.kwargs
    assert (
        coordinator.kwargs["workflow_revision"]
        == "landing-evidence-revision"
    )
    assert coordinator.kwargs["mutation_guard"]() is None


@pytest.mark.asyncio
async def test_coordinator_adapter_binds_headed_epic_workflow_revision():
    class Coordinator:
        def __init__(self):
            self.kwargs = None

        async def request_transition(self, **kwargs):
            self.kwargs = kwargs
            return type(
                "Result", (), {"success": True, "audit_id": "audit-x", "reason": None}
            )()

    coordinator = Coordinator()
    issue = _issue(
        state="In Progress",
        issue_type="epic",
        parent_id=None,
        head_sha="b" * 40,
    )
    intent = _intent(
        issue,
        requested_status="Merged",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        evidence_generation="epic-auto-close-generation",
        exact_head="b" * 40,
        precondition_revision="landing-evidence-revision",
    )

    result = await CoordinatorTerminalAdapter(
        coordinator,
        mutation_guard=lambda _intent: None,
    ).stage(intent, issue)

    assert result.success
    assert "revision_binding" not in coordinator.kwargs
    assert coordinator.kwargs["workflow_revision"] == (
        "landing-evidence-revision"
    )


@pytest.mark.asyncio
async def test_coordinator_adapter_rejects_missing_workflow_revision():
    class Coordinator:
        def __init__(self):
            self.calls = 0

        async def request_transition(self, **_kwargs):
            self.calls += 1

    coordinator = Coordinator()
    issue = _issue(state="In Progress", issue_type="epic", parent_id=None)
    intent = _intent(
        issue,
        requested_status="Merged",
        authority=TransitionAuthority.ORCHESTRATOR,
        reason_code="terminal.immediate_target_landing_proven",
        evidence_generation="epic-auto-close-generation",
        exact_head="b" * 40,
        precondition_revision=None,
    )

    result = await CoordinatorTerminalAdapter(coordinator).stage(intent, issue)

    assert not result.success
    assert result.reason_code == "transition.stale_precondition"
    assert coordinator.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    ("missing_guard", "missing_generation", "missing_precondition"),
)
async def test_coordinator_adapter_does_not_supply_unbound_root_epic_revision(
    mutation,
):
    class Coordinator:
        def __init__(self):
            self.kwargs = None

        async def request_transition(self, **kwargs):
            self.kwargs = kwargs
            return type(
                "Result", (), {"success": True, "audit_id": "audit-x", "reason": None}
            )()

    coordinator = Coordinator()
    issue = _issue(
        state="In Progress",
        issue_type="epic",
        parent_id=None,
        work_branch=None,
        target_branch=None,
        head_sha=None,
        integration=None,
    )
    intent_values = {
        "requested_status": "Merged",
        "authority": TransitionAuthority.ORCHESTRATOR,
        "reason_code": "terminal.immediate_target_landing_proven",
        "evidence_generation": "epic-auto-close-generation",
        "exact_head": "b" * 40,
        "precondition_revision": "landing-evidence-revision",
    }
    if mutation == "missing_generation":
        intent_values["evidence_generation"] = None
    elif mutation == "missing_precondition":
        intent_values["precondition_revision"] = None
    guard = None if mutation == "missing_guard" else lambda _intent: None

    result = await CoordinatorTerminalAdapter(
        coordinator,
        mutation_guard=guard,
    ).stage(_intent(issue, **intent_values), issue)

    if mutation == "missing_precondition":
        assert not result.success
        assert result.reason_code == "transition.stale_precondition"
        assert coordinator.kwargs is None
        return
    assert "revision_binding" not in coordinator.kwargs


@pytest.mark.asyncio
async def test_coordinator_adapter_rejects_changed_mutation_precondition():
    class Coordinator:
        async def request_transition(self, **kwargs):
            conflict = kwargs["mutation_guard"]()
            return type(
                "Result",
                (),
                {
                    "success": False,
                    "audit_id": None,
                    "reason": f"workflow_precondition_changed: {conflict}",
                },
            )()

    issue = _issue(state="In Review")
    intent = _intent(
        issue,
        requested_status="Merged",
        evidence_generation=None,
        precondition_revision="before-child-reopen",
    )
    adapter = CoordinatorTerminalAdapter(
        Coordinator(), mutation_guard=lambda _intent: "child reopened"
    )

    result = await adapter.stage(intent, issue)

    assert result.success is False
    assert result.reason_code == "transition.stale_precondition"
    assert result.detail == "workflow_precondition_changed: child reopened"


@pytest.mark.asyncio
async def test_coordinator_adapter_reports_delivery_admission_conflict():
    class Coordinator:
        async def request_transition(self, **_kwargs):
            return type(
                "Result",
                (),
                {
                    "success": False,
                    "audit_id": None,
                    "reason": "delivery_mutation_in_progress",
                },
            )()

    issue = _issue(state="In Review")
    intent = _intent(
        issue,
        requested_status="Merged",
        exact_head="a" * 40,
        evidence_generation=None,
    )

    result = await CoordinatorTerminalAdapter(Coordinator()).stage(intent, issue)

    assert result.success is False
    assert result.reason_code == "transition.delivery_mutation_in_progress"
    assert result.detail == "delivery_mutation_in_progress"


@pytest.mark.asyncio
async def test_delivery_admission_conflict_is_durably_retryable(tmp_path):
    class BusyTerminalAdapter:
        async def stage(self, _intent, _issue):
            return TerminalStageResult(
                False,
                reason_code="transition.delivery_mutation_in_progress",
                detail="delivery_mutation_in_progress",
            )

    issue = _issue(state="In Review")
    tracker = FakeTracker(issue)
    journal = TransitionJournal(str(tmp_path / "transitions.sqlite3"))
    service = _service(
        tmp_path,
        tracker,
        journal=journal,
        terminal_adapter=BusyTerminalAdapter(),
    )
    intent = _intent(
        issue,
        requested_status="Merged",
        exact_head="a" * 40,
        evidence_generation=None,
    )

    outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.RETRYABLE
    assert outcome.retryable is True
    assert outcome.reason_code == "transition.delivery_mutation_in_progress"
    assert journal.events(outcome.transition_id)[-1].phase is (
        TransitionPhase.RETRY_SCHEDULED
    )


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


def test_expired_foreign_claim_is_durably_recovered_by_new_intent(tmp_path):
    clock = [100.0]
    path = str(tmp_path / "transitions.sqlite3")
    journal = TransitionJournal(path, clock=lambda: clock[0])
    issue = _issue()
    first = _intent(issue)
    first_started = journal.begin(first, lease_ttl_seconds=10)
    assert first_started.claim_token
    clock[0] = 111.0
    second = replace(first, idempotency_key="job-2", originating_job="job-2")

    recovered = journal.begin(second, lease_ttl_seconds=10)

    assert recovered.claim_token is not None
    assert recovered.waiting is None
    expiration = journal.events(first_started.transition_id)[-1]
    assert expiration.phase is TransitionPhase.RETRY_SCHEDULED
    assert expiration.reason_code == "transition.claim_expired"
    assert expiration.outcome is not None
    assert expiration.outcome.retryable is True
    assert expiration.outcome.details == {
        "lease_expires_at": 110.0,
        "replacement_transition_id": recovered.transition_id,
    }
    old_retry = journal.begin(first, lease_ttl_seconds=10)
    assert old_retry.waiting is not None
    assert old_retry.waiting.reason_code == "transition.owner_active"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "reason_code"),
    [
        ({"state": "Needs Human"}, "transition.stale_status"),
        ({"assignment_id": "generation-2"}, "transition.stale_version"),
    ],
)
async def test_expired_foreign_claim_recovery_preserves_tracker_cas(
    tmp_path,
    mutation,
    reason_code,
):
    clock = [100.0]
    journal = TransitionJournal(
        str(tmp_path / "transitions.sqlite3"),
        clock=lambda: clock[0],
    )
    original = _issue()
    abandoned = _intent(original)
    started = journal.begin(abandoned, lease_ttl_seconds=10)
    journal.append(
        started.transition_id,
        TransitionPhase.APPLYING,
        abandoned.reason_code,
    )
    clock[0] = 111.0
    tracker = FakeTracker(replace(original, **mutation))
    service = _service(
        tmp_path,
        tracker,
        journal=journal,
        claim_ttl_seconds=10,
    )
    replacement = replace(
        abandoned,
        idempotency_key="job-2",
        originating_job="job-2",
    )

    outcome = await service.execute(replacement)

    assert outcome.disposition is TransitionDisposition.REJECTED
    assert outcome.reason_code == reason_code
    assert tracker.updates == []


@pytest.mark.asyncio
async def test_expired_foreign_claim_resumes_exact_unapplied_intent(tmp_path):
    clock = [100.0]
    journal = TransitionJournal(
        str(tmp_path / "transitions.sqlite3"),
        clock=lambda: clock[0],
    )
    tracker = FakeTracker(_issue())
    abandoned = _intent(tracker.issue)
    started = journal.begin(abandoned, lease_ttl_seconds=10)
    journal.append(
        started.transition_id,
        TransitionPhase.APPLYING,
        abandoned.reason_code,
    )
    clock[0] = 111.0
    service = _service(
        tmp_path,
        tracker,
        journal=journal,
        claim_ttl_seconds=10,
    )
    replacement = replace(
        abandoned,
        idempotency_key="job-2",
        originating_job="job-2",
    )

    outcome = await service.execute(replacement)

    assert outcome.disposition is TransitionDisposition.ALREADY_APPLIED
    assert tracker.updates == [("TASK-1", "In Progress")]
    assert journal.latest_event(started.transition_id).phase is TransitionPhase.APPLIED


@pytest.mark.asyncio
async def test_expired_foreign_claim_recovers_effect_already_applied(tmp_path):
    clock = [100.0]
    journal = TransitionJournal(
        str(tmp_path / "transitions.sqlite3"),
        clock=lambda: clock[0],
    )
    before = _issue()
    abandoned = _intent(before)
    started = journal.begin(abandoned, lease_ttl_seconds=10)
    journal.append(
        started.transition_id,
        TransitionPhase.APPLYING,
        abandoned.reason_code,
    )
    clock[0] = 111.0
    tracker = FakeTracker(replace(before, state="In Progress"))
    service = _service(
        tmp_path,
        tracker,
        journal=journal,
        claim_ttl_seconds=10,
    )
    replacement = replace(
        abandoned,
        idempotency_key="job-2",
        originating_job="job-2",
    )

    outcome = await service.execute(replacement)

    assert outcome.disposition is TransitionDisposition.ALREADY_APPLIED
    assert tracker.updates == []
    recovered = journal.latest_event(started.transition_id)
    assert recovered.phase is TransitionPhase.RECOVERED
    assert recovered.outcome.reason_code == "transition.already_applied"


@pytest.mark.asyncio
async def test_retryable_expired_recovery_keeps_original_obligation(tmp_path):
    clock = [100.0]
    journal = TransitionJournal(
        str(tmp_path / "transitions.sqlite3"),
        clock=lambda: clock[0],
    )
    tracker = FakeTracker(_issue())
    abandoned = _intent(tracker.issue)
    started = journal.begin(abandoned, lease_ttl_seconds=10)
    journal.append(
        started.transition_id,
        TransitionPhase.APPLYING,
        abandoned.reason_code,
    )
    clock[0] = 111.0
    tracker.fetch_failures = 2
    service = _service(
        tmp_path,
        tracker,
        journal=journal,
        claim_ttl_seconds=10,
    )
    replacement = replace(
        abandoned,
        requested_status="Needs Human",
        idempotency_key="job-2",
        originating_job="job-2",
    )

    first_pending = await service.execute(replacement)
    second_pending = await service.execute(replacement)
    resolved = await service.execute(replacement)

    assert first_pending.disposition is TransitionDisposition.WAITING
    assert first_pending.reason_code == "transition.recovery_pending"
    assert first_pending.retryable is True
    assert second_pending.disposition is TransitionDisposition.WAITING
    assert second_pending.reason_code == "transition.recovery_pending"
    assert resolved.disposition is TransitionDisposition.REJECTED
    assert resolved.reason_code == "transition.stale_status"
    assert tracker.updates == [("TASK-1", "In Progress")]
    assert journal.latest_event(started.transition_id).phase is TransitionPhase.APPLIED


@pytest.mark.asyncio
@pytest.mark.parametrize("entrypoint", ["execute", "recover_authorized"])
async def test_expired_authorized_recovery_uses_compensation_lane(
    tmp_path,
    entrypoint,
):
    clock = [100.0]
    journal = TransitionJournal(
        str(tmp_path / "transitions.sqlite3"),
        clock=lambda: clock[0],
    )
    tracker = FakeTracker(_issue(state="Archived"))
    abandoned = _intent(
        tracker.issue,
        requested_status="Open",
        authority=TransitionAuthority.PROJECT_OWNER,
        actor="project-owner",
        reason_code="provenance.owner_revision_authorized",
        idempotency_key="owner-recovery-1",
        originating_job="owner-recovery-1",
        evidence_generation=None,
    )
    started = journal.begin(abandoned, lease_ttl_seconds=10)
    journal.append(
        started.transition_id,
        TransitionPhase.APPLYING,
        abandoned.reason_code,
    )
    clock[0] = 111.0
    service = _service(
        tmp_path,
        tracker,
        journal=journal,
        claim_ttl_seconds=10,
    )
    replacement = replace(
        abandoned,
        idempotency_key="owner-recovery-2",
        originating_job="owner-recovery-2",
    )

    outcome = await getattr(service, entrypoint)(replacement)

    assert outcome.disposition is TransitionDisposition.ALREADY_APPLIED
    assert tracker.updates == [("TASK-1", "Open")]
    recovered = journal.latest_event(started.transition_id)
    assert recovered.phase is TransitionPhase.APPLIED
    assert recovered.outcome.reason_code == "transition.applied"


@pytest.mark.asyncio
async def test_expired_recovery_fences_conflicting_newer_intent(tmp_path):
    clock = [100.0]
    journal = TransitionJournal(
        str(tmp_path / "transitions.sqlite3"),
        clock=lambda: clock[0],
    )
    tracker = FakeTracker(_issue())
    abandoned = _intent(tracker.issue)
    started = journal.begin(abandoned, lease_ttl_seconds=10)
    journal.append(
        started.transition_id,
        TransitionPhase.APPLYING,
        abandoned.reason_code,
    )
    clock[0] = 111.0
    service = _service(
        tmp_path,
        tracker,
        journal=journal,
        claim_ttl_seconds=10,
    )
    conflicting = replace(
        abandoned,
        requested_status="Needs Human",
        idempotency_key="job-2",
        originating_job="job-2",
    )

    outcome = await service.execute(conflicting)

    assert outcome.disposition is TransitionDisposition.REJECTED
    assert outcome.reason_code == "transition.stale_status"
    assert tracker.updates == [("TASK-1", "In Progress")]


def test_only_one_concurrent_claimant_recovers_expired_foreign_claim(tmp_path):
    clock = [100.0]
    path = str(tmp_path / "transitions.sqlite3")
    bootstrap = TransitionJournal(path, clock=lambda: clock[0])
    issue = _issue()
    abandoned = _intent(issue)
    abandoned_started = bootstrap.begin(abandoned, lease_ttl_seconds=10)
    clock[0] = 111.0
    journals = [
        TransitionJournal(path, clock=lambda: clock[0]),
        TransitionJournal(path, clock=lambda: clock[0]),
    ]
    intents = [
        replace(
            abandoned,
            actor=f"worker-{number}",
            idempotency_key=f"job-{number}",
            originating_job=f"job-{number}",
        )
        for number in (2, 3)
    ]
    barrier = threading.Barrier(2)

    def contend(index):
        barrier.wait(timeout=5)
        return journals[index].begin(intents[index], lease_ttl_seconds=10)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(contend, range(2)))

    owners = [result for result in results if result.claim_token is not None]
    waiters = [result for result in results if result.waiting is not None]
    assert len(owners) == 1
    assert len(waiters) == 1
    assert waiters[0].waiting.reason_code == "transition.owner_active"
    expiration_events = [
        event
        for event in bootstrap.events(abandoned_started.transition_id)
        if event.reason_code == "transition.claim_expired"
    ]
    assert len(expiration_events) == 1


def test_expired_claim_recovery_fails_closed_on_mismatched_history(tmp_path):
    clock = [100.0]
    journal = TransitionJournal(
        str(tmp_path / "transitions.sqlite3"),
        clock=lambda: clock[0],
    )
    first = _intent(_issue())
    journal.begin(first, lease_ttl_seconds=10)
    other_issue = _issue(id="TASK-2", identifier="TASK-2")
    other_started = journal.begin(
        _intent(
            other_issue,
            idempotency_key="other-task",
            originating_job="other-task",
        ),
        lease_ttl_seconds=10,
    )
    journal._conn.execute(  # noqa: SLF001 - corruption recovery probe
        """
        UPDATE task_transition_claims SET transition_id = ?
         WHERE project_id = ? AND task_id = ?
        """,
        (other_started.transition_id, first.project_id, first.task_id),
    )
    journal._conn.commit()  # noqa: SLF001
    clock[0] = 111.0
    replacement = replace(
        first,
        idempotency_key="job-3",
        originating_job="job-3",
    )

    with pytest.raises(
        TransitionJournalCorruptionError,
        match="claim does not match its immutable request",
    ):
        journal.begin(replacement, lease_ttl_seconds=10)


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


@pytest.mark.asyncio
async def test_needs_human_escalation_is_logged_with_authority_source(
    tmp_path, caplog
):
    """Regression test for OOMPAH-1270: Needs Human transitions must log actor/authority/reason.
    
    This ensures that when a task is escalated to 'Needs Human' via an external push-hook
    or API call, the exact source (actor, authority, reason_code) is recorded in logs
    for later investigation of unexpected escalations.
    """
    issue = _issue(state="Open")
    tracker = FakeTracker(issue)
    service = _service(tmp_path, tracker)
    
    intent = _intent(
        issue,
        requested_status="Needs Human",
        authority=TransitionAuthority.API,
        actor="external-webhook",
        reason_code="external.push_hook_escalation",
    )

    with caplog.at_level("INFO"):
        outcome = await service.execute(intent)

    assert outcome.disposition is TransitionDisposition.APPLIED
    assert tracker.updates == [("TASK-1", "Needs Human")]
    
    # Verify that the escalation is logged with all authority information
    assert "Task escalation to Needs Human" in caplog.text
    assert "task=TASK-1" in caplog.text
    assert "project=project-1" in caplog.text
    assert "actor=external-webhook" in caplog.text
    assert "authority=TransitionAuthority.API" in caplog.text
    assert "reason=external.push_hook_escalation" in caplog.text
