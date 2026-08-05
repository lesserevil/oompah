"""Tests for idempotent terminal-transition staging and audit chains.

Covers every target (Done, Merged, Archived) and chain variant, direct Merged
with and without a current completed-Done audit, duplicate event coalescing,
changed-fingerprint superseding, simultaneous requests, superseded chains,
tracker-write-failure ordering, restart-recovered requests, and comment
deduplication.
"""

from __future__ import annotations

import asyncio
import copy
import threading
import time
from dataclasses import dataclass, field, replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from oompah.models import Issue
from oompah.terminal_audit import (
    ContributorIdentity,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)
from oompah.terminal_transition_coordinator import (
    OverrideRejection,
    TerminalTransitionCoordinator,
    TransitionResult,
    _build_new_entries,
)
from oompah.statuses import IN_VALIDATION, DONE, MERGED, ARCHIVED


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _LockStore:
    """Thread-safe per-project write-lock provider."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def project_write_lock(self, project_id: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(project_id, threading.RLock())


class _MemoryTracker:
    """In-memory TrackerProtocol double that records calls.

    Metadata is stored per-identifier so that different tasks in the same
    tracker instance do not share state.
    """

    def __init__(self, initial_metadata: dict[str, Any] | None = None) -> None:
        self._lock = threading.Lock()
        # Per-identifier metadata: { identifier: { key: value } }
        self._per_id_metadata: dict[str, dict[str, Any]] = {}
        # Populate the default task metadata if provided
        if initial_metadata:
            self._per_id_metadata[TASK_ID] = copy.deepcopy(initial_metadata)
        self._statuses: dict[str, str] = {}
        self.update_calls: list[tuple[str, dict[str, Any]]] = []
        self.comment_calls: list[tuple[str, str]] = []

    # ------------------------------------------------------------------
    # TrackerProtocol subset used by TerminalAuditMetadataStore
    # ------------------------------------------------------------------

    def get_metadata(self, identifier: str) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._per_id_metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: Any) -> None:
        with self._lock:
            if identifier not in self._per_id_metadata:
                self._per_id_metadata[identifier] = {}
            self._per_id_metadata[identifier][key] = copy.deepcopy(value)

    def update_issue(self, identifier: str, **kwargs: Any) -> None:
        with self._lock:
            self.update_calls.append((identifier, dict(kwargs)))
            if "status" in kwargs:
                self._statuses[identifier] = kwargs["status"]

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        with self._lock:
            self.comment_calls.append((identifier, text))
            return {"id": str(len(self.comment_calls)), "text": text}

    def current_status(self, identifier: str) -> str | None:
        with self._lock:
            return self._statuses.get(identifier)

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        with self._lock:
            return [
                Issue(
                    id=identifier,
                    identifier=identifier,
                    title="Test task",
                    state=self._statuses[identifier],
                )
                for identifier in issue_ids
                if identifier in self._statuses
            ]


class _FailingUpdateTracker(_MemoryTracker):
    """A tracker that raises on update_issue (simulates tracker write failure)."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_update = True

    def update_issue(self, identifier: str, **kwargs: Any) -> None:
        if self.fail_update:
            raise RuntimeError("Tracker write failed")
        super().update_issue(identifier, **kwargs)


class _FailingRefreshTracker(_MemoryTracker):
    """Production-shaped tracker whose authoritative detail read is down."""

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        raise RuntimeError(f"authoritative read failed for {identifier}")


class _BlockingMetadataTracker(_MemoryTracker):
    """Block the first metadata write to force cross-loop lock contention."""

    def __init__(self) -> None:
        super().__init__()
        self.first_write_entered = threading.Event()
        self.release_first_write = threading.Event()
        self._block_guard = threading.Lock()
        self._blocked_once = False

    def set_metadata_field(self, identifier: str, key: str, value: Any) -> None:
        should_block = False
        with self._block_guard:
            if not self._blocked_once:
                self._blocked_once = True
                should_block = True
        if should_block:
            self.first_write_entered.set()
            if not self.release_first_write.wait(timeout=5):
                raise TimeoutError("test did not release the first metadata write")
        super().set_metadata_field(identifier, key, value)


class _TrackerFactory:
    """Project-aware tracker provider used by integration coverage."""

    def __init__(self, trackers: dict[str, _MemoryTracker]) -> None:
        self.trackers = trackers
        self.calls: list[str] = []

    def __call__(self, project_id: str) -> _MemoryTracker:
        self.calls.append(project_id)
        return self.trackers[project_id]


class _MetricsRecorder:
    """Small metrics sink used to verify coordinator lifecycle callbacks."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def record_queued(self, *args: Any, **_kwargs: Any) -> None:
        self.calls.append(("queued", args))

    def record_stale_discarded(self, *args: Any, **_kwargs: Any) -> None:
        self.calls.append(("stale_discarded", args))

    def record_overridden(self, *args: Any, **_kwargs: Any) -> None:
        self.calls.append(("overridden", args))

    def clear_actionable_alert(self, *args: Any, **_kwargs: Any) -> None:
        self.calls.append(("clear_actionable_alert", args))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROJECT_ID = "proj-test"
TASK_ID = "TASK-42"


def _fingerprint(seed: str = "a") -> EvidenceFingerprint:
    """Return a fixed-content EvidenceFingerprint for testing."""
    return EvidenceFingerprint(seed * 64)


def _alt_fingerprint() -> EvidenceFingerprint:
    """A second distinct fingerprint."""
    return EvidenceFingerprint("b" * 64)


def _trigger() -> ContributorIdentity:
    return ContributorIdentity("auditor-bot", "oompah")


def _issue(state: str = "In Progress") -> Issue:
    return Issue(id=TASK_ID, identifier=TASK_ID, title="Test task", state=state)


def _coordinator(
    tracker: _MemoryTracker | None = None,
    post_comments: bool = True,
    metrics: Any | None = None,
    validate_terminal_transition: Any | None = None,
) -> TerminalTransitionCoordinator:
    return TerminalTransitionCoordinator(
        tracker=tracker or _MemoryTracker(),
        project_store=_LockStore(),
        post_comments=post_comments,
        metrics=metrics,
        validate_terminal_transition=validate_terminal_transition,
    )


def _run(coro):
    """Run a coroutine in a new event loop."""
    return asyncio.run(coro)


def _completed_done_record(project_id: str = PROJECT_ID, task_id: str = TASK_ID) -> TerminalAuditRecord:
    """Return a Done audit record already in COMPLETED state."""
    return TerminalAuditRecord(
        audit_id="audit-done-old",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=_fingerprint(),
        request_state=RequestState.COMPLETED,
        created_at="2026-07-01T00:00:00+00:00",
    )


def _pending_done_record(project_id: str = PROJECT_ID, task_id: str = TASK_ID) -> TerminalAuditRecord:
    return TerminalAuditRecord(
        audit_id="audit-done-pending",
        project_id=project_id,
        task_id=task_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=_fingerprint(),
        request_state=RequestState.PENDING,
        created_at="2026-07-01T00:00:00+00:00",
    )


def _seed_metadata(tracker: _MemoryTracker, chain: list[TerminalAuditRecord],
                   task_id: str = TASK_ID) -> None:
    """Pre-populate tracker metadata with an audit chain for *task_id*."""
    doc = TerminalAuditMetadata(pending_chain=chain)
    tracker.set_metadata_field(task_id, METADATA_KEY, doc.to_dict())


# ---------------------------------------------------------------------------
# TestDoneChain
# ---------------------------------------------------------------------------


class TestDoneChain:
    def test_done_creates_exactly_one_audit(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result.success is True
        assert result.coalesced is False
        assert len(result.queued_targets) == 1
        assert result.queued_targets[0] == TargetState.DONE
        assert result.audit_id is not None

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert len(doc.pending_chain) == 1
        audit = doc.pending_chain[0]
        assert audit.target_state == TargetState.DONE
        assert audit.request_state == RequestState.PENDING
        assert audit.evidence_fingerprint == _fingerprint()

    def test_done_records_previous_state(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        _run(coord.request_transition(
            _issue("In Progress"), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert doc.pending_chain[0].previous_state == "In Progress"

    def test_done_moves_issue_to_in_validation(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert tracker.current_status(TASK_ID) == IN_VALIDATION

    def test_done_does_not_move_terminal_issue_to_in_validation(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        _run(coord.request_transition(
            _issue(DONE), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        # update_issue should NOT have been called with IN_VALIDATION
        in_val_calls = [
            call for call in tracker.update_calls
            if call[1].get("status") == IN_VALIDATION
        ]
        assert len(in_val_calls) == 0


# ---------------------------------------------------------------------------
# TestMergedChain
# ---------------------------------------------------------------------------


class TestMergedChain:
    def test_merged_without_done_queues_both_done_and_merged(self) -> None:
        """Direct Merged with no current Done evidence must queue Done first."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(), TargetState.MERGED, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result.success is True
        assert len(result.queued_targets) == 2
        assert result.queued_targets[0] == TargetState.DONE
        assert result.queued_targets[1] == TargetState.MERGED

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert len(doc.pending_chain) == 2
        assert doc.pending_chain[0].target_state == TargetState.DONE
        assert doc.pending_chain[1].target_state == TargetState.MERGED
        for record in doc.pending_chain:
            assert record.request_state == RequestState.PENDING

    def test_direct_merged_cannot_skip_completion_auditing(self) -> None:
        """Even a direct Merged request must produce a Done audit first."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(), TargetState.MERGED, _trigger(), PROJECT_ID, _fingerprint()
        ))

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        done_records = [r for r in doc.pending_chain if r.target_state == TargetState.DONE]
        assert len(done_records) == 1, "Done audit must be present even for direct-Merged"

    def test_merged_with_completed_done_reuses_it(self) -> None:
        """If a completed Done exists, Merged request only adds the Merged record."""
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [_completed_done_record()])

        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(), TargetState.MERGED, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result.success is True
        assert len(result.queued_targets) == 1
        assert result.queued_targets[0] == TargetState.MERGED

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        targets = [r.target_state for r in doc.pending_chain]
        assert TargetState.DONE in targets
        assert TargetState.MERGED in targets
        done_records = [r for r in doc.pending_chain if r.target_state == TargetState.DONE]
        assert len(done_records) == 1
        # The Done record must be the same one we seeded (COMPLETED)
        assert done_records[0].request_state == RequestState.COMPLETED

    def test_merged_with_pending_done_still_skips_adding_done(self) -> None:
        """A Merged request when Done is pending (but not completed) still just adds Merged."""
        # A pending Done exists; there's no completed Done.
        # The design says: only reuse a *completed* Done.
        # So a pending Done means we should NOT add another Done but still need Merged.
        # But if there's NO completed Done, we must queue Done first.
        # This test verifies the behavior when Done is PENDING (not completed).
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [_pending_done_record()])

        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(), TargetState.MERGED, _trigger(), PROJECT_ID, _fingerprint()
        ))

        # Because Done is pending (not completed), no completed Done exists.
        # Coordinator should queue a new Done PLUS Merged.
        # But wait: there's already a pending Done record — however it has the same fingerprint
        # so coalescing won't trigger (that only applies when targets match).
        # The Merged request doesn't coalesce with the Done record.
        # So the coordinator adds Done + Merged as new entries.
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        done_records = [r for r in doc.pending_chain if r.target_state == TargetState.DONE]
        merged_records = [r for r in doc.pending_chain if r.target_state == TargetState.MERGED]
        # The existing queued Done is reused; retries must not create a second
        # completion audit for the same chain.
        assert len(merged_records) == 1
        assert len(done_records) == 1

    def test_new_merged_fingerprint_supersedes_old_in_progress_done(self) -> None:
        """OOMPAH-818: a new Merged generation requires a fresh Done audit."""

        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        old = _run(
            coord.request_transition(
                _issue(),
                TargetState.DONE,
                _trigger(),
                PROJECT_ID,
                _fingerprint("a"),
            )
        )
        store.update(
            TASK_ID,
            lambda doc: replace(
                doc,
                pending_chain=[
                    replace(record, request_state=RequestState.IN_PROGRESS)
                    if record.audit_id == old.audit_id
                    else record
                    for record in doc.pending_chain
                ],
            ),
        )

        fresh = _run(
            coord.request_transition(
                _issue(state=IN_VALIDATION),
                TargetState.MERGED,
                _trigger(),
                PROJECT_ID,
                _fingerprint("b"),
            )
        )

        assert fresh.success is True
        assert fresh.queued_targets == [TargetState.DONE, TargetState.MERGED]
        records = store.read(TASK_ID).pending_chain
        old_done = next(record for record in records if record.audit_id == old.audit_id)
        assert old_done.request_state == RequestState.SUPERSEDED
        current = [
            record
            for record in records
            if record.request_state in (RequestState.PENDING, RequestState.IN_PROGRESS)
        ]
        assert [record.target_state for record in current] == [
            TargetState.DONE,
            TargetState.MERGED,
        ]
        assert all(
            record.evidence_fingerprint == _fingerprint("b")
            for record in current
        )

    def test_merged_replay_repairs_stale_done_prerequisite_then_coalesces(self) -> None:
        """A same-Merged replay normalizes Done before it may coalesce."""

        tracker = _MemoryTracker()
        old_done = TerminalAuditRecord(
            audit_id="audit-done-a",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint("a"),
            request_state=RequestState.IN_PROGRESS,
        )
        queued_merged = TerminalAuditRecord(
            audit_id="audit-merged-b",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.MERGED,
            evidence_fingerprint=_fingerprint("b"),
            request_state=RequestState.PENDING,
        )
        _seed_metadata(tracker, [old_done, queued_merged])
        coord = _coordinator(tracker, post_comments=False)
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)

        repaired = _run(
            coord.request_transition(
                _issue(state=IN_VALIDATION),
                TargetState.MERGED,
                _trigger(),
                PROJECT_ID,
                _fingerprint("b"),
            )
        )

        assert repaired.success is True
        assert repaired.coalesced is False
        assert repaired.queued_targets == [TargetState.DONE, TargetState.MERGED]
        assert repaired.superseded_audit_ids == [
            old_done.audit_id,
            queued_merged.audit_id,
        ]
        active = [
            record
            for record in store.read(TASK_ID).pending_chain
            if record.request_state in (RequestState.PENDING, RequestState.IN_PROGRESS)
        ]
        assert [record.target_state for record in active] == [
            TargetState.DONE,
            TargetState.MERGED,
        ]
        assert all(record.evidence_fingerprint == _fingerprint("b") for record in active)

        repeated = _run(
            coord.request_transition(
                _issue(state=IN_VALIDATION),
                TargetState.MERGED,
                _trigger(),
                PROJECT_ID,
                _fingerprint("b"),
            )
        )

        assert repeated.success is True
        assert repeated.coalesced is True
        assert len(store.read(TASK_ID).pending_chain) == 4

    def test_changed_merged_generation_cleans_up_every_superseded_audit(self) -> None:
        """Changed evidence retires and clears both Done and Merged identities."""

        tracker = _MemoryTracker()
        old_done = TerminalAuditRecord(
            audit_id="audit-done-b",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint("b"),
            request_state=RequestState.IN_PROGRESS,
        )
        old_merged = TerminalAuditRecord(
            audit_id="audit-merged-b",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.MERGED,
            evidence_fingerprint=_fingerprint("b"),
            request_state=RequestState.PENDING,
        )
        _seed_metadata(tracker, [old_done, old_merged])
        metrics = _MetricsRecorder()
        cleared: list[tuple[str, str, str]] = []
        coord = _coordinator(
            tracker,
            post_comments=False,
            metrics=metrics,
        )
        coord.set_alert_clearer(lambda *identity: cleared.append(identity))

        result = _run(
            coord.request_transition(
                _issue(state=IN_VALIDATION),
                TargetState.MERGED,
                _trigger(),
                PROJECT_ID,
                _fingerprint("c"),
            )
        )

        assert result.superseded_audit_ids == [old_done.audit_id, old_merged.audit_id]
        for audit_id in result.superseded_audit_ids:
            assert (
                "stale_discarded",
                (PROJECT_ID, TASK_ID, audit_id),
            ) in metrics.calls
        assert cleared == [
            (PROJECT_ID, TASK_ID, old_done.audit_id),
            (PROJECT_ID, TASK_ID, old_merged.audit_id),
        ]


class TestSharedEpicMergedCompatibility:
    """Every coordinator terminal boundary honors the shared-epic gate."""

    @staticmethod
    def _child(state: str = "In Progress") -> Issue:
        return Issue(
            id="CHILD-1",
            identifier="CHILD-1",
            title="Shared child",
            state=state,
            parent_id="EPIC-1",
            project_id=PROJECT_ID,
            work_branch="epic-EPIC-1",
        )

    @staticmethod
    def _conflict(_issue: Issue, _target: TargetState, _project_id: str) -> str:
        return (
            "Cannot transition shared-epic child CHILD-1 to Merged: parent "
            "review must land on configured target branch main first."
        )

    def test_request_rejects_merged_before_parent_landing(self) -> None:
        tracker = _MemoryTracker()
        coordinator = _coordinator(
            tracker,
            validate_terminal_transition=self._conflict,
        )

        result = _run(
            coordinator.request_transition(
                self._child(),
                TargetState.MERGED,
                _trigger(),
                PROJECT_ID,
                _fingerprint(),
            )
        )

        assert not result.success
        assert "parent review must land" in (result.reason or "")
        assert tracker.update_calls == []
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read("CHILD-1").pending_chain == []

    def test_owner_override_rejects_without_canceling_audits(self) -> None:
        tracker = _MemoryTracker()
        done = _completed_done_record(project_id=PROJECT_ID, task_id="CHILD-1")
        _seed_metadata(tracker, [done], task_id="CHILD-1")
        coordinator = _coordinator(
            tracker,
            validate_terminal_transition=self._conflict,
        )
        project = SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

        result = _run(
            coordinator.override_transition(
                self._child(DONE),
                TargetState.MERGED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                _fingerprint(),
                "Emergency owner approval",
                project,
            )
        )

        assert not result.success
        assert result.error_code == OverrideRejection.LIFECYCLE_INCOMPATIBLE
        assert "parent review must land" in (result.reason or "")
        assert tracker.update_calls == []
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read("CHILD-1").pending_chain == [done]

    def test_passed_merged_audit_stays_pending_until_parent_lands(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(
            audit_id="audit-child-merged",
            target=TargetState.MERGED,
            task_id="CHILD-1",
        )
        _seed_metadata(tracker, [record], task_id="CHILD-1")
        coordinator = _coordinator(
            tracker,
            validate_terminal_transition=self._conflict,
        )
        outcome = _apply(
            coordinator,
            self._child(IN_VALIDATION),
            _pass_result(record),
            PROJECT_ID,
        )

        assert not outcome.success
        assert "parent review must land" in (outcome.reason or "")
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read("CHILD-1")
        assert stored.pending_chain[0].request_state == RequestState.PENDING
        assert tracker.update_calls == []

# ---------------------------------------------------------------------------
# TestArchivedChain
# ---------------------------------------------------------------------------


class TestArchivedChain:
    def test_archived_creates_one_audit(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(), TargetState.ARCHIVED, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result.success is True
        assert len(result.queued_targets) == 1
        assert result.queued_targets[0] == TargetState.ARCHIVED

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert len(doc.pending_chain) == 1
        assert doc.pending_chain[0].target_state == TargetState.ARCHIVED

    def test_archived_appended_after_existing_pending(self) -> None:
        """Archived is queued after any other pending targets in the chain."""
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [_pending_done_record()])

        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(), TargetState.ARCHIVED, _trigger(), PROJECT_ID, _fingerprint("b")
        ))

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        targets = [r.target_state for r in doc.pending_chain]
        assert TargetState.DONE in targets
        assert TargetState.ARCHIVED in targets
        # Archived must come after Done in the chain
        done_idx = next(i for i, t in enumerate(targets) if t == TargetState.DONE)
        arch_idx = next(i for i, t in enumerate(targets) if t == TargetState.ARCHIVED)
        assert arch_idx > done_idx

    @pytest.mark.parametrize("prior_state", [DONE, MERGED])
    def test_archived_from_terminal_retention_state_moves_to_validation(
        self, prior_state: str
    ) -> None:
        """Retention audits remain visible to the audit worker."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)

        result = _run(coord.request_transition(
            _issue(prior_state), TargetState.ARCHIVED, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result.success is True
        assert tracker.current_status(TASK_ID) == IN_VALIDATION

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        record = store.read(TASK_ID).pending_chain[0]
        assert record.previous_state == prior_state


# ---------------------------------------------------------------------------
# TestCoalescing
# ---------------------------------------------------------------------------


class TestCoalescing:
    def test_duplicate_requests_coalesce(self) -> None:
        """Identical (target, fingerprint) request returns the existing audit_id."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        fp = _fingerprint()

        result1 = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        result2 = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))

        assert result1.success is True
        assert result2.success is True
        assert result2.coalesced is True
        assert result2.audit_id == result1.audit_id

        # Metadata should still have exactly one Done record
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        done_records = [r for r in doc.pending_chain if r.target_state == TargetState.DONE]
        assert len(done_records) == 1

    def test_coalesced_request_does_not_post_status_update(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        fp = _fingerprint()

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        initial_update_count = len(tracker.update_calls)

        result = _run(coord.request_transition(
            _issue(IN_VALIDATION), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))

        # Second call should not trigger any new tracker updates
        assert len(tracker.update_calls) == initial_update_count
        assert result.status_staged is True
        assert result.status_repaired is False

    def test_explicit_coalesced_retry_repairs_validation_status_drift(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        fp = _fingerprint()

        first = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        tracker.update_issue(TASK_ID, status="Needs Human")
        initial_comment_count = len(tracker.comment_calls)

        repeated = _run(coord.request_transition(
            _issue("Needs Human"), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))

        assert repeated.success is True
        assert repeated.coalesced is True
        assert repeated.audit_id == first.audit_id
        assert repeated.status_repaired is True
        assert repeated.status_staged is True
        assert tracker.current_status(TASK_ID) == IN_VALIDATION
        assert len(tracker.comment_calls) == initial_comment_count

    def test_coalesced_retry_does_not_regress_terminal_status(self) -> None:
        tracker = _MemoryTracker()
        pending = _pending_done_record()
        _seed_metadata(tracker, [pending])
        tracker.update_issue(TASK_ID, status=DONE)
        coord = _coordinator(tracker)
        initial_update_count = len(tracker.update_calls)

        result = _run(coord.request_transition(
            _issue(DONE), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result.success is True
        assert result.coalesced is True
        assert result.status_repaired is False
        assert result.status_staged is False
        assert tracker.current_status(TASK_ID) == DONE
        assert len(tracker.update_calls) == initial_update_count


# ---------------------------------------------------------------------------
# TestSuperseding
# ---------------------------------------------------------------------------


class TestSuperseding:
    def test_changed_fingerprint_supersedes_pending(self) -> None:
        """A request with a changed fingerprint marks the old record SUPERSEDED."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)

        result1 = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("a")
        ))
        result2 = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("b")
        ))

        assert result2.success is True
        assert result2.coalesced is False
        assert result2.superseded_audit_id == result1.audit_id

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)

        # Old record must be SUPERSEDED
        old = next(r for r in doc.pending_chain if r.audit_id == result1.audit_id)
        assert old.request_state == RequestState.SUPERSEDED

        # New record must be PENDING with new fingerprint
        new = next(r for r in doc.pending_chain if r.audit_id == result2.audit_id)
        assert new.request_state == RequestState.PENDING
        assert new.evidence_fingerprint == _fingerprint("b")

    def test_superseded_audit_is_counted_as_stale_discarded(self) -> None:
        tracker = _MemoryTracker()
        metrics = _MetricsRecorder()
        coord = _coordinator(tracker, post_comments=False, metrics=metrics)

        first = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("a")
        ))
        second = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("b")
        ))

        assert ("stale_discarded", (PROJECT_ID, TASK_ID, first.audit_id)) in metrics.calls
        assert ("queued", (PROJECT_ID, TASK_ID, second.audit_id)) in metrics.calls

    def test_changed_fingerprint_supersedes_in_progress_audit(self) -> None:
        """A new revision invalidates an auditor already checking old evidence."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)

        old_result = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("a")
        ))
        store.update(
            TASK_ID,
            lambda doc: replace(
                doc,
                pending_chain=[
                    replace(record, request_state=RequestState.IN_PROGRESS)
                    if record.audit_id == old_result.audit_id
                    else record
                    for record in doc.pending_chain
                ],
            ),
        )

        fresh_result = _run(coord.request_transition(
            _issue(state=IN_VALIDATION),
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            _fingerprint("b"),
        ))

        doc = store.read(TASK_ID)
        old = next(
            record
            for record in doc.pending_chain
            if record.audit_id == old_result.audit_id
        )
        fresh = next(
            record
            for record in doc.pending_chain
            if record.audit_id == fresh_result.audit_id
        )
        assert old.request_state == RequestState.SUPERSEDED
        assert fresh.request_state == RequestState.PENDING
        assert [
            record.audit_id
            for record in doc.pending_chain
            if record.request_state
            in (RequestState.PENDING, RequestState.IN_PROGRESS)
        ] == [fresh.audit_id]

        late = _apply(
            coord,
            _issue(state=IN_VALIDATION),
            _pass_result(old),
        )
        assert late.success is False
        assert late.reason == ResultRejection.STATE_MISMATCH
        assert tracker.current_status(TASK_ID) == IN_VALIDATION


    def test_identical_request_coalesces_with_in_progress_audit(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        initial = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("a")
        ))
        store.update(
            TASK_ID,
            lambda doc: replace(
                doc,
                pending_chain=[
                    replace(record, request_state=RequestState.IN_PROGRESS)
                    for record in doc.pending_chain
                ],
            ),
        )

        repeated = _run(coord.request_transition(
            _issue(state=IN_VALIDATION),
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            _fingerprint("a"),
        ))

        assert repeated.success is True
        assert repeated.coalesced is True
        assert repeated.audit_id == initial.audit_id
        assert len(store.read(TASK_ID).pending_chain) == 1

    def test_coalescing_fresh_request_repairs_stale_active_revision(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        stale = _pending_record(
            audit_id="audit-stale",
            fingerprint=_fingerprint("a"),
        )
        fresh = _pending_record(
            audit_id="audit-fresh",
            fingerprint=_fingerprint("b"),
        )
        _seed_metadata(tracker, [stale, fresh])

        repeated = _run(coord.request_transition(
            _issue(state=IN_VALIDATION),
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            _fingerprint("b"),
        ))

        assert repeated.success is True
        assert repeated.coalesced is True
        assert repeated.audit_id == fresh.audit_id
        assert repeated.superseded_audit_id == stale.audit_id
        old, current = store.read(TASK_ID).pending_chain
        assert old.request_state == RequestState.SUPERSEDED
        assert current.request_state == RequestState.PENDING

    def test_superseded_chain_retains_both_records(self) -> None:
        """The full chain is preserved: superseded record is not deleted."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)

        result1 = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("a")
        ))
        result2 = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("c")
        ))

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        audit_ids = {r.audit_id for r in doc.pending_chain}
        assert result1.audit_id in audit_ids
        assert result2.audit_id in audit_ids
        assert len(doc.pending_chain) == 2


# ---------------------------------------------------------------------------
# TestOwnerOverrides
# ---------------------------------------------------------------------------


class TestOwnerOverrides:
    def test_owner_override_cancels_live_audit_and_finishes_its_gauge(self) -> None:
        tracker = _MemoryTracker()
        metrics = _MetricsRecorder()
        record = _pending_done_record()
        _seed_metadata(tracker, [record])
        coordinator = _coordinator(tracker, post_comments=False, metrics=metrics)
        owner = ContributorIdentity("project-owner", "github")
        project = SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

        result = _run(
            coordinator.override_transition(
                _issue(IN_VALIDATION),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                _fingerprint(),
                "Project owner approved this terminal transition.",
                project,
            )
        )

        assert result.success is True
        assert result.overridden_audit_ids == [record.audit_id]
        assert tracker.current_status(TASK_ID) == DONE
        stored = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID).read(TASK_ID)
        assert stored.pending_chain[0].request_state == RequestState.CANCELLED
        assert ("overridden", (PROJECT_ID, TASK_ID, record.audit_id)) in metrics.calls

    def test_override_retires_all_duplicate_rows_and_replays_idempotently(self) -> None:
        tracker = _MemoryTracker()
        metrics = _MetricsRecorder()
        fingerprint = _fingerprint()
        first = _pending_record(audit_id="audit-override-1", fingerprint=fingerprint)
        second = _pending_record(audit_id="audit-override-2", fingerprint=fingerprint)
        _seed_metadata(tracker, [first, second])
        coordinator = _coordinator(tracker, post_comments=False, metrics=metrics)
        owner = ContributorIdentity("project-owner", "github")
        project = SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

        result = _run(
            coordinator.override_transition(
                _issue(IN_VALIDATION),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                fingerprint,
                "Owner approved this transition.",
                project,
            )
        )

        assert result.success is True
        assert result.overridden_audit_ids == [first.audit_id, second.audit_id]
        assert set(result.retired_alert_audit_ids) == {first.audit_id, second.audit_id}
        stored = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID).read(TASK_ID)
        assert [record.request_state for record in stored.pending_chain] == [
            RequestState.CANCELLED,
            RequestState.CANCELLED,
        ]
        raw_override = stored.unknown_fields["oompah.terminal_override_records"][0]
        assert raw_override["applied"] is True
        retirement = stored.unknown_fields["oompah.terminal_audit_retirements"][0]
        assert retirement["evidence_fingerprint"] == fingerprint.digest
        assert set(retirement["audit_ids"]) == {first.audit_id, second.audit_id}

        replay = _run(
            coordinator.override_transition(
                _issue(DONE),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                fingerprint,
                "Owner approved this transition.",
                project,
            )
        )
        assert replay.success is True
        assert replay.idempotent is True
        assert replay.override_id == result.override_id
        assert len(tracker.update_calls) == 1

    def test_idempotent_override_repairs_regressed_tracker_status(self) -> None:
        """A stale restart writer cannot make an applied override lie."""
        tracker = _MemoryTracker()
        fingerprint = _fingerprint()
        record = _pending_record(
            audit_id="audit-override-repair",
            fingerprint=fingerprint,
        )
        _seed_metadata(tracker, [record])
        coordinator = _coordinator(tracker, post_comments=False)
        owner = ContributorIdentity("project-owner", "github")
        project = SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

        first = _run(
            coordinator.override_transition(
                _issue(IN_VALIDATION),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                fingerprint,
                "Owner approved this transition.",
                project,
            )
        )
        assert first.success is True
        assert tracker.current_status(TASK_ID) == DONE

        # Reproduce OOMPAH-700: restart recovery writes Open after the
        # persisted override has already applied its terminal status.
        tracker.update_issue(TASK_ID, status="Open")
        assert tracker.current_status(TASK_ID) == "Open"

        replay = _run(
            coordinator.override_transition(
                _issue("Open"),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                fingerprint,
                "Owner approved this transition.",
                project,
            )
        )

        assert replay.success is True
        assert replay.idempotent is True
        assert replay.override_id == first.override_id
        assert tracker.current_status(TASK_ID) == DONE
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert len(stored.unknown_fields["oompah.terminal_override_records"]) == 1


# ---------------------------------------------------------------------------
# TestStaleRejection
# ---------------------------------------------------------------------------


class TestStaleRejection:
    def test_stale_request_rejected_when_already_completed(self) -> None:
        """A request for an already-completed target returns failure."""
        completed = TerminalAuditRecord(
            audit_id="audit-done-complete",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [completed])

        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result.success is False
        assert result.reason == "already completed"
        assert result.audit_id == "audit-done-complete"

    def test_stale_request_does_not_add_new_chain_entries(self) -> None:
        completed = TerminalAuditRecord(
            audit_id="audit-done-complete",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [completed])

        coord = _coordinator(tracker)
        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        # Chain should not have grown
        assert len(doc.pending_chain) == 1
        assert doc.pending_chain[0].audit_id == "audit-done-complete"

    def test_changed_completed_evidence_queues_fresh_audit(self) -> None:
        """A repaired head may retry after an earlier completed audit failed."""
        completed = TerminalAuditRecord(
            audit_id="audit-done-complete",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint("a"),
            request_state=RequestState.COMPLETED,
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [completed])

        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(),
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            _fingerprint("b"),
        ))

        assert result.success is True
        assert result.superseded_audit_id == "audit-done-complete"
        assert result.audit_id != "audit-done-complete"

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        old, fresh = doc.pending_chain
        assert old.audit_id == "audit-done-complete"
        assert old.request_state == RequestState.SUPERSEDED
        assert fresh.audit_id == result.audit_id
        assert fresh.request_state == RequestState.PENDING
        assert fresh.evidence_fingerprint == _fingerprint("b")

        repeated = _run(coord.request_transition(
            _issue(state=IN_VALIDATION),
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            _fingerprint("b"),
        ))
        assert repeated.success is True
        assert repeated.coalesced is True
        assert repeated.audit_id == fresh.audit_id
        assert len(store.read(TASK_ID).pending_chain) == 2


# ---------------------------------------------------------------------------
# TestCommentDeduplication
# ---------------------------------------------------------------------------


class TestCommentDeduplication:
    def test_queued_comment_posted_once(self) -> None:
        """The transition comment is posted only on the first request."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        fp = _fingerprint()

        # First request → comment posted
        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        assert len(tracker.comment_calls) == 1

        # Second request (same fingerprint → coalesces, no new comment)
        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        assert len(tracker.comment_calls) == 1

    def test_comment_not_re_posted_on_supersede(self) -> None:
        """Superseding a pending request does not re-post the comment."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("a")
        ))
        comment_count_after_first = len(tracker.comment_calls)

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("b")
        ))
        # The queued_comment_posted flag was already set; no second comment
        assert len(tracker.comment_calls) == comment_count_after_first

    def test_comment_content_mentions_target_state(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert len(tracker.comment_calls) == 1
        text = tracker.comment_calls[0][1]
        assert "Done" in text

    def test_comment_dedup_persisted_across_coordinator_instances(self) -> None:
        """A new coordinator that reads existing metadata must not re-post the comment."""
        tracker = _MemoryTracker()

        # First coordinator posts the comment and persists the flag
        coord1 = _coordinator(tracker)
        _run(coord1.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))
        assert len(tracker.comment_calls) == 1

        # Second coordinator uses the same tracker (metadata persisted) with new fingerprint
        coord2 = _coordinator(tracker)
        _run(coord2.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint("b")
        ))
        # Should NOT post a second comment because the flag is set in metadata
        assert len(tracker.comment_calls) == 1


# ---------------------------------------------------------------------------
# TestTrackerWriteFailureOrdering
# ---------------------------------------------------------------------------


class TestTrackerWriteFailureOrdering:
    def test_audit_chain_persisted_before_status_write(self) -> None:
        """The audit chain must be durably persisted even if the tracker status write fails."""
        tracker = _FailingUpdateTracker()
        coord = _coordinator(tracker)

        # The update_issue call will raise; request_transition should still succeed
        result = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        # Success because audit chain was persisted even though status write failed
        assert result.success is True

        # Verify audit chain is in metadata
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert len(doc.pending_chain) == 1
        assert doc.pending_chain[0].target_state == TargetState.DONE

    def test_no_metadata_written_is_recoverable(self) -> None:
        """Even on tracker failure, any persisted chain can be recovered."""
        tracker = _FailingUpdateTracker()
        coord = _coordinator(tracker)

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        # A new coordinator with the same tracker should find the persisted chain
        coord2 = _coordinator(tracker)
        # The second call should coalesce (same fingerprint)
        result2 = _run(coord2.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))
        assert result2.coalesced is True


# ---------------------------------------------------------------------------
# TestRestartRecovery
# ---------------------------------------------------------------------------


class TestRestartRecovery:
    def test_restart_recovered_requests_coalesce(self) -> None:
        """After a restart, a new coordinator coalesces with persisted pending audits."""
        tracker = _MemoryTracker()

        # Coordinator processes a request and persists the chain
        coord1 = _coordinator(tracker, post_comments=False)
        result1 = _run(coord1.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        # Simulate restart: create a fresh coordinator with the same backing tracker
        coord2 = _coordinator(tracker, post_comments=False)
        result2 = _run(coord2.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result2.coalesced is True
        assert result2.audit_id == result1.audit_id

        # Only one record in metadata (no duplicate from restart)
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        done_records = [r for r in doc.pending_chain if r.target_state == TargetState.DONE]
        assert len(done_records) == 1

    def test_restart_recovered_requests_no_duplicate_comments(self) -> None:
        """After a restart, the queued comment is not re-posted."""
        tracker = _MemoryTracker()

        coord1 = _coordinator(tracker)
        _run(coord1.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))
        assert len(tracker.comment_calls) == 1

        # Fresh coordinator, same fingerprint → coalesces, flag already in metadata
        coord2 = _coordinator(tracker)
        _run(coord2.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))
        assert len(tracker.comment_calls) == 1


# ---------------------------------------------------------------------------
# TestSimultaneousRequests
# ---------------------------------------------------------------------------


class TestSimultaneousRequests:
    def test_simultaneous_same_fingerprint_coalesces(self) -> None:
        """Two concurrent requests for the same (task, fingerprint) coalesce."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        fp = _fingerprint()

        async def _both():
            r1, r2 = await asyncio.gather(
                coord.request_transition(_issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp),
                coord.request_transition(_issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp),
            )
            return r1, r2

        r1, r2 = asyncio.run(_both())

        # One should be original, one coalesced
        assert r1.success and r2.success
        coalesced_count = sum(1 for r in (r1, r2) if r.coalesced)
        assert coalesced_count == 1

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        done_records = [r for r in doc.pending_chain if r.target_state == TargetState.DONE]
        assert len(done_records) == 1

    def test_different_projects_do_not_block_each_other(self) -> None:
        """Concurrent requests for different projects proceed in parallel."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        fp = _fingerprint()

        issue_a = Issue(id="A-1", identifier="A-1", title="Task A", state="Open")
        issue_b = Issue(id="B-1", identifier="B-1", title="Task B", state="Open")

        async def _both():
            r1, r2 = await asyncio.gather(
                coord.request_transition(issue_a, TargetState.DONE, _trigger(), "proj-a", fp),
                coord.request_transition(issue_b, TargetState.DONE, _trigger(), "proj-b", fp),
            )
            return r1, r2

        r1, r2 = asyncio.run(_both())
        assert r1.success and r2.success
        assert not r1.coalesced and not r2.coalesced


# ---------------------------------------------------------------------------
# TestPerProjectLocking
# ---------------------------------------------------------------------------


class TestPerProjectLocking:
    def test_same_project_is_safe_across_concurrent_event_loops(self) -> None:
        """Server and orchestrator loops may use one coordinator concurrently."""
        tracker = _BlockingMetadataTracker()
        coord = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=_LockStore(),
            post_comments=False,
        )
        fp = _fingerprint()
        results: list[TransitionResult] = []
        errors: list[BaseException] = []

        def _request(identifier: str) -> None:
            issue = Issue(
                id=identifier,
                identifier=identifier,
                title=identifier,
                state="Open",
            )
            try:
                results.append(
                    asyncio.run(
                        coord.request_transition(
                            issue,
                            TargetState.DONE,
                            _trigger(),
                            PROJECT_ID,
                            fp,
                        )
                    )
                )
            except BaseException as exc:  # noqa: BLE001 - asserted below
                errors.append(exc)

        first = threading.Thread(target=_request, args=("TASK-A",), daemon=True)
        second = threading.Thread(target=_request, args=("TASK-B",), daemon=True)
        third = threading.Thread(target=_request, args=("TASK-C",), daemon=True)
        first.start()
        assert tracker.first_write_entered.wait(timeout=2)
        second.start()
        time.sleep(0.1)
        third.start()
        time.sleep(0.1)
        tracker.release_first_write.set()

        for thread in (first, second, third):
            thread.join(timeout=5)
            assert not thread.is_alive()

        assert errors == []
        assert len(results) == 3
        assert all(result.success for result in results)

        fourth = _run(
            coord.request_transition(
                Issue(id="TASK-D", identifier="TASK-D", title="D", state="Open"),
                TargetState.DONE,
                _trigger(),
                PROJECT_ID,
                fp,
            )
        )
        assert fourth.success


class TestProjectTrackerFactory:
    def test_project_aware_factory_keeps_metadata_and_writes_scoped(self) -> None:
        tracker_a = _MemoryTracker()
        tracker_b = _MemoryTracker()
        factory = _TrackerFactory({"proj-a": tracker_a, "proj-b": tracker_b})
        coord = TerminalTransitionCoordinator(
            tracker=factory,
            project_store=_LockStore(),
            post_comments=False,
        )

        issue_a = Issue(id="A-1", identifier="A-1", title="A", state="Open")
        issue_b = Issue(id="B-1", identifier="B-1", title="B", state="Open")
        _run(coord.request_transition(
            issue_a, TargetState.DONE, _trigger(), "proj-a", _fingerprint("a")
        ))
        _run(coord.request_transition(
            issue_b, TargetState.DONE, _trigger(), "proj-b", _fingerprint("b")
        ))

        store_a = TerminalAuditMetadataStore(tracker_a, _LockStore(), "proj-a")
        store_b = TerminalAuditMetadataStore(tracker_b, _LockStore(), "proj-b")
        assert len(store_a.read("A-1").pending_chain) == 1
        assert len(store_b.read("B-1").pending_chain) == 1
        assert tracker_a.current_status("A-1") == IN_VALIDATION
        assert tracker_b.current_status("B-1") == IN_VALIDATION
        assert factory.calls == ["proj-a", "proj-b"]


# ---------------------------------------------------------------------------
# TestQuarantineHandling
# ---------------------------------------------------------------------------


class TestQuarantineHandling:
    def test_quarantined_metadata_returns_failure(self) -> None:
        """If metadata is quarantined, request_transition returns failure."""
        from oompah.terminal_audit_metadata import MetadataQuarantine, TerminalAuditMetadataQuarantinedError

        tracker = _MemoryTracker()
        # Plant malformed (unparseable) metadata so the store quarantines it on first read
        tracker.set_metadata_field(TASK_ID, METADATA_KEY, {"version": "bad", "garbage": True})

        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result.success is False
        assert "quarantined" in (result.reason or "").lower()


# ---------------------------------------------------------------------------
# TestBuildNewEntries (unit tests for the module helper)
# ---------------------------------------------------------------------------


class TestBuildNewEntries:
    def _chain_for(self, target: TargetState, state: RequestState) -> list[TerminalAuditRecord]:
        return [TerminalAuditRecord(
            audit_id="existing-1",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=target,
            evidence_fingerprint=_fingerprint(),
            request_state=state,
        )]

    def test_done_returns_single_entry(self) -> None:
        entries = _build_new_entries(
            [], _issue(), TargetState.DONE, _trigger(), _fingerprint(), PROJECT_ID
        )
        assert len(entries) == 1
        assert entries[0].target_state == TargetState.DONE
        assert entries[0].request_state == RequestState.PENDING

    def test_merged_no_done_returns_two_entries(self) -> None:
        entries = _build_new_entries(
            [], _issue(), TargetState.MERGED, _trigger(), _fingerprint(), PROJECT_ID
        )
        assert len(entries) == 2
        assert entries[0].target_state == TargetState.DONE
        assert entries[1].target_state == TargetState.MERGED

    def test_merged_with_completed_done_returns_one_merged_entry(self) -> None:
        chain = self._chain_for(TargetState.DONE, RequestState.COMPLETED)
        entries = _build_new_entries(
            chain, _issue(), TargetState.MERGED, _trigger(), _fingerprint(), PROJECT_ID
        )
        assert len(entries) == 1
        assert entries[0].target_state == TargetState.MERGED

    def test_archived_returns_single_entry(self) -> None:
        entries = _build_new_entries(
            [], _issue(), TargetState.ARCHIVED, _trigger(), _fingerprint(), PROJECT_ID
        )
        assert len(entries) == 1
        assert entries[0].target_state == TargetState.ARCHIVED

    def test_each_entry_has_unique_audit_id(self) -> None:
        entries1 = _build_new_entries(
            [], _issue(), TargetState.MERGED, _trigger(), _fingerprint(), PROJECT_ID
        )
        entries2 = _build_new_entries(
            [], _issue(), TargetState.MERGED, _trigger(), _fingerprint(), PROJECT_ID
        )
        ids1 = {e.audit_id for e in entries1}
        ids2 = {e.audit_id for e in entries2}
        assert not (ids1 & ids2), "Audit IDs must be unique across calls"

    def test_records_carry_correct_project_and_task(self) -> None:
        entries = _build_new_entries(
            [], _issue(), TargetState.DONE, _trigger(), _fingerprint(), PROJECT_ID
        )
        assert entries[0].project_id == PROJECT_ID
        assert entries[0].task_id == TASK_ID

    def test_records_carry_trigger_identity(self) -> None:
        trigger = ContributorIdentity("alice", "github")
        entries = _build_new_entries(
            [], _issue(), TargetState.DONE, trigger, _fingerprint(), PROJECT_ID
        )
        assert entries[0].requested_by == trigger

    def test_records_carry_evidence_fingerprint(self) -> None:
        fp = _fingerprint("c")
        entries = _build_new_entries(
            [], _issue(), TargetState.DONE, _trigger(), fp, PROJECT_ID
        )
        assert entries[0].evidence_fingerprint == fp


# ---------------------------------------------------------------------------
# TestTransitionResultShape
# ---------------------------------------------------------------------------


class TestTransitionResultShape:
    def test_result_fields_on_success(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        result = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert isinstance(result, TransitionResult)
        assert result.success is True
        assert result.audit_id is not None
        assert isinstance(result.queued_targets, list)
        assert result.coalesced is False
        assert result.superseded_audit_id is None
        assert result.reason is None

    def test_result_fields_on_coalesced(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        fp = _fingerprint()
        result1 = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        result2 = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))

        assert result2.coalesced is True
        assert result2.audit_id == result1.audit_id
        assert result2.queued_targets == [TargetState.DONE]

    def test_result_fields_on_failure(self) -> None:
        completed = TerminalAuditRecord(
            audit_id="audit-c",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [completed])

        coord = _coordinator(tracker)
        result = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result.success is False
        assert result.reason is not None
        assert result.audit_id == "audit-c"


# =============================================================================
# apply_audit_result — OOMPAH-466
# =============================================================================


from oompah.terminal_audit import (  # noqa: E402
    AuditAttempt,
    FailureClassification,
    Verdict,
)
from oompah.terminal_transition_coordinator import (  # noqa: E402
    AuditResult,
    ResultOutcome,
    ResultRejection,
    classify_failure_to_status,
    route_failure_status,
)
from oompah.statuses import (  # noqa: E402
    IN_REVIEW,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
)


def _pending_record(
    *,
    audit_id: str = "audit-pending-1",
    target: TargetState = TargetState.DONE,
    fingerprint: EvidenceFingerprint | None = None,
    state: RequestState = RequestState.PENDING,
    previous: str | None = "In Progress",
    project_id: str = PROJECT_ID,
    task_id: str = TASK_ID,
) -> TerminalAuditRecord:
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id=project_id,
        task_id=task_id,
        target_state=target,
        evidence_fingerprint=fingerprint or _fingerprint(),
        request_state=state,
        previous_state=previous,
        created_at="2026-07-28T00:00:00Z",
    )


def _exhausted_no_auditor_record() -> TerminalAuditRecord:
    fingerprint = _fingerprint()
    attempts = [
        AuditAttempt(
            attempt_id="attempt-workspace",
            target_state=TargetState.ARCHIVED,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
            failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
            failure_reason=(
                "git worktree add failed: invalid reference: "
                "origin/epic-EXOCOMP-2"
            ),
            ended_at="2026-07-31T00:01:00+00:00",
        ),
        AuditAttempt(
            attempt_id="no-auditor-old",
            target_state=TargetState.ARCHIVED,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.COMPLETED,
            verdict=Verdict.FAIL,
            failure_classification=FailureClassification.NO_AUDITOR,
            failure_reason="maximum attempts reached",
            ended_at="2026-07-31T00:02:00+00:00",
        ),
    ]
    return TerminalAuditRecord(
        audit_id="audit-exhausted",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.ARCHIVED,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=attempts,
        previous_state=MERGED,
        created_at="2026-07-31T00:00:00+00:00",
    )


def _exhausted_missing_evidence_record() -> TerminalAuditRecord:
    fingerprint = _fingerprint()
    return TerminalAuditRecord(
        audit_id="audit-missing-evidence",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=[
            AuditAttempt(
                attempt_id="missing-evidence-attempt",
                target_state=TargetState.DONE,
                evidence_fingerprint=fingerprint,
                request_state=RequestState.COMPLETED,
                verdict=Verdict.FAIL,
                failure_classification=FailureClassification.MISSING_EVIDENCE,
                failure_reason="Required pinned quality-gate output was missing",
                ended_at="2026-07-31T00:02:00+00:00",
            )
        ],
        previous_state="Ready to Integrate",
        created_at="2026-07-31T00:00:00+00:00",
    )


def _exhausted_mixed_attempt_record() -> TerminalAuditRecord:
    """Create a record with mixed attempt history (finalization_failure + terminal no_auditor).

    This reproduces OOMPAH-745: a task with multiple failed attempts from
    different failures, ending with NO_AUDITOR. The record should still be
    retryable via infrastructure recovery because the TERMINAL attempt is NO_AUDITOR.
    """
    fingerprint = _fingerprint()
    attempts = [
        AuditAttempt(
            attempt_id="finalization-failure-1",
            target_state=TargetState.ARCHIVED,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.COMPLETED,
            verdict=Verdict.FAIL,
            failure_classification=FailureClassification.FINALIZATION_FAILURE,
            failure_reason=(
                "audit result could not be applied to tracker: "
                "connection timeout after 30s"
            ),
            ended_at="2026-07-31T00:01:00+00:00",
        ),
        AuditAttempt(
            attempt_id="no-auditor-terminal",
            target_state=TargetState.ARCHIVED,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.COMPLETED,
            verdict=Verdict.FAIL,
            failure_classification=FailureClassification.NO_AUDITOR,
            failure_reason="maximum attempts reached without auditor candidate",
            ended_at="2026-07-31T00:02:00+00:00",
        ),
    ]
    return TerminalAuditRecord(
        audit_id="audit-mixed-attempts",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.ARCHIVED,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        attempts=attempts,
        previous_state=MERGED,
        created_at="2026-07-31T00:00:00+00:00",
    )


class TestRetryFailedAudit:
    @staticmethod
    def _owner_project():
        return SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

    def test_owner_rearms_same_evidence_without_reopening_implementation(self) -> None:
        tracker = _MemoryTracker()
        metrics = _MetricsRecorder()
        exhausted = _exhausted_no_auditor_record()
        _seed_metadata(tracker, [exhausted])
        coordinator = _coordinator(tracker, post_comments=False, metrics=metrics)

        result = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Detached audit checkout support is deployed.",
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        assert result.success is True
        assert result.status_staged is True
        assert result.superseded_audit_id == exhausted.audit_id
        assert tracker.current_status(TASK_ID) == IN_VALIDATION
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert len(stored.pending_chain) == 2
        old, fresh = stored.pending_chain
        assert old.request_state == RequestState.SUPERSEDED
        assert fresh.request_state == RequestState.PENDING
        assert fresh.evidence_fingerprint == exhausted.evidence_fingerprint
        assert fresh.previous_state == MERGED
        assert fresh.attempts == []
        assert (
            "clear_actionable_alert",
            (PROJECT_ID, TASK_ID, exhausted.audit_id),
        ) in metrics.calls

    def test_retry_is_idempotent_after_fresh_record_is_pending(self) -> None:
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [_exhausted_no_auditor_record()])
        coordinator = _coordinator(tracker, post_comments=False)
        args = (
            _issue(NEEDS_HUMAN),
            TargetState.ARCHIVED,
            ContributorIdentity("project-owner", "api"),
            PROJECT_ID,
            "Workspace transport repaired.",
            self._owner_project(),
        )
        kwargs = {
            "evidence_fingerprint": _exhausted_no_auditor_record().evidence_fingerprint,
        }

        first = _run(coordinator.retry_failed_audit(*args, **kwargs))
        second = _run(coordinator.retry_failed_audit(*args, **kwargs))

        assert first.success is True
        assert second.success is True
        assert second.coalesced is True
        assert second.audit_id == first.audit_id
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert len(stored.pending_chain) == 2

    def test_active_infrastructure_retry_rejects_evidence_addendum(self) -> None:
        """An addendum cannot coalesce onto a non-evidence recovery audit."""

        tracker = _MemoryTracker()
        exhausted = _exhausted_no_auditor_record()
        _seed_metadata(tracker, [exhausted])
        coordinator = _coordinator(tracker, post_comments=False)
        common = (
            _issue(NEEDS_HUMAN),
            TargetState.ARCHIVED,
            ContributorIdentity("project-owner", "api"),
            PROJECT_ID,
            "Retry after infrastructure repair",
            self._owner_project(),
        )
        first = _run(
            coordinator.retry_failed_audit(
                *common,
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        replay = _run(
            coordinator.retry_failed_audit(
                *common,
                evidence_fingerprint=exhausted.evidence_fingerprint,
                evidence_addendum={
                    "evidence_fingerprint": exhausted.evidence_fingerprint.digest,
                    "checks": ["make test"],
                },
            )
        )

        assert first.success is True
        assert replay.success is False
        assert replay.reason == "audit_not_retryable"
        assert len(
            TerminalAuditMetadataStore(
                tracker, _LockStore(), PROJECT_ID
            ).read(TASK_ID).pending_chain
        ) == 2

    def test_active_evidence_retry_rejects_infrastructure_replay(self) -> None:
        """A no-addendum retry cannot change an active addendum recovery mode."""

        tracker = _MemoryTracker()
        failed = _exhausted_missing_evidence_record()
        _seed_metadata(tracker, [failed])
        coordinator = _coordinator(tracker, post_comments=False)
        common = (
            _issue(NEEDS_HUMAN),
            TargetState.DONE,
            ContributorIdentity("project-owner", "api"),
            PROJECT_ID,
            "Evidence supplied",
            self._owner_project(),
        )
        first = _run(
            coordinator.retry_failed_audit(
                *common,
                evidence_fingerprint=failed.evidence_fingerprint,
                evidence_addendum={
                    "evidence_fingerprint": failed.evidence_fingerprint.digest,
                    "checks": ["make test"],
                },
            )
        )

        replay = _run(
            coordinator.retry_failed_audit(
                *common,
                evidence_fingerprint=failed.evidence_fingerprint,
            )
        )

        assert first.success is True
        assert replay.success is False
        assert replay.reason == "audit_not_retryable"
        assert len(
            TerminalAuditMetadataStore(
                tracker, _LockStore(), PROJECT_ID
            ).read(TASK_ID).pending_chain
        ) == 2

    def test_evidence_addendum_does_not_coalesce_unproven_active_audit(self) -> None:
        """A generic active audit has no missing-evidence rearm authority."""

        failed = _exhausted_missing_evidence_record()
        active = replace(
            failed,
            audit_id="audit-active-without-rearm-provenance",
            request_state=RequestState.PENDING,
            attempts=[],
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [failed, active])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Evidence supplied",
                self._owner_project(),
                evidence_fingerprint=failed.evidence_fingerprint,
                evidence_addendum={
                    "evidence_fingerprint": failed.evidence_fingerprint.digest,
                    "checks": ["make test"],
                },
            )
        )

        assert result.success is False
        assert result.reason == "audit_not_retryable"
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain == [failed, active]

    def test_active_retry_only_coalesces_for_exact_current_fingerprint(self) -> None:
        failed = _exhausted_no_auditor_record()
        stale_active = replace(
            failed,
            audit_id="audit-stale-active",
            evidence_fingerprint=_alt_fingerprint(),
            request_state=RequestState.PENDING,
            attempts=[],
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [failed, stale_active])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Retry after infrastructure repair",
                self._owner_project(),
                evidence_fingerprint=failed.evidence_fingerprint,
            )
        )

        assert result.success is False
        assert result.reason == "evidence_fingerprint_mismatch"
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain == [failed, stale_active]

    def test_newer_successful_audit_fences_older_active_record(self) -> None:
        failed = _exhausted_no_auditor_record()
        older_active = replace(
            failed,
            audit_id="audit-older-active",
            request_state=RequestState.PENDING,
            attempts=[],
        )
        passed = replace(
            failed,
            audit_id="audit-newer-pass",
            attempts=[
                replace(
                    failed.attempts[-1],
                    attempt_id="newer-pass",
                    verdict=Verdict.PASS,
                    failure_classification=None,
                )
            ],
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [older_active, passed])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Retry the historical active record",
                self._owner_project(),
                evidence_fingerprint=failed.evidence_fingerprint,
            )
        )

        assert result.success is False
        assert result.reason == "audit_not_retryable"
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain == [older_active, passed]

    def test_production_retry_fails_closed_when_evidence_refresh_fails(self) -> None:
        failed = _exhausted_no_auditor_record()
        tracker = _FailingRefreshTracker()
        _seed_metadata(tracker, [failed])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Retry after infrastructure repair",
                self._owner_project(),
                evidence_fingerprint=failed.evidence_fingerprint,
            )
        )

        assert result.success is False
        assert result.reason == "evidence_refresh_failed"
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain == [failed]
        assert tracker.update_calls == []

    def test_non_owner_cannot_rearm_audit(self) -> None:
        tracker = _MemoryTracker()
        exhausted = _exhausted_no_auditor_record()
        _seed_metadata(tracker, [exhausted])
        coordinator = _coordinator(tracker, post_comments=False)

        result = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("auditor-only", "api"),
                PROJECT_ID,
                "Try again.",
                self._owner_project(),
            )
        )

        assert result.success is False
        assert result.reason == "unauthorized_actor"
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert stored.pending_chain == [exhausted]
        assert tracker.current_status(TASK_ID) is None

    def test_owner_rearms_missing_evidence_with_same_head_addendum(self) -> None:
        tracker = _MemoryTracker()
        failed = _exhausted_missing_evidence_record()
        _seed_metadata(tracker, [failed])
        coordinator = _coordinator(tracker, post_comments=False)
        addendum = {
            "evidence_fingerprint": failed.evidence_fingerprint.digest,
            "checks": [
                {"name": "make test", "result": "passed", "tail": "ok"},
                {"name": "make fmt-check", "result": "passed"},
                {"name": "make lint", "result": "passed"},
            ],
        }

        result = _run(
            coordinator.retry_failed_audit(
                _issue("Needs Human"),
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Pinned gate tails supplied for the integrated head",
                self._owner_project(),
                evidence_fingerprint=failed.evidence_fingerprint,
                evidence_addendum=addendum,
            )
        )

        assert result.success is True
        assert result.status_staged is True
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        old, fresh = stored.pending_chain
        assert old.request_state == RequestState.SUPERSEDED
        assert fresh.request_state == RequestState.PENDING
        assert fresh.evidence_fingerprint == failed.evidence_fingerprint
        history = stored.unknown_fields["oompah.terminal_audit_rearm_history"]
        assert history[0]["actor"]["identity"] == "project-owner"
        assert history[0]["reason"] == "Pinned gate tails supplied for the integrated head"
        assert history[0]["evidence_addendum"]["checks"][0]["name"] == "make test"

        outcome = _run(
            coordinator.apply_audit_result(
                _issue(IN_VALIDATION),
                AuditResult(
                    audit_id=fresh.audit_id,
                    target_state=TargetState.DONE,
                    evidence_fingerprint=fresh.evidence_fingerprint,
                    verdict=Verdict.PASS,
                    message="The pinned quality gates pass.",
                    attempt_id="evidence-rearm-pass",
                ),
                PROJECT_ID,
            )
        )
        assert outcome.success is True
        assert tracker.current_status(TASK_ID) == DONE

    def test_missing_evidence_rearm_requires_current_fingerprint_and_owner(self) -> None:
        tracker = _MemoryTracker()
        failed = _exhausted_missing_evidence_record()
        _seed_metadata(tracker, [failed])
        coordinator = _coordinator(tracker, post_comments=False)
        addendum = {
            "evidence_fingerprint": failed.evidence_fingerprint.digest,
            "checks": ["make test"],
        }

        mismatch = _run(
            coordinator.retry_failed_audit(
                _issue("Needs Human"),
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Evidence supplied",
                self._owner_project(),
                evidence_fingerprint=_alt_fingerprint(),
                evidence_addendum=addendum,
            )
        )
        assert mismatch.success is False
        assert mismatch.reason == "evidence_fingerprint_mismatch"

        non_owner = _run(
            coordinator.retry_failed_audit(
                _issue("Needs Human"),
                TargetState.DONE,
                ContributorIdentity("auditor-only", "api"),
                PROJECT_ID,
                "Evidence supplied",
                self._owner_project(),
                evidence_fingerprint=failed.evidence_fingerprint,
                evidence_addendum=addendum,
            )
        )
        assert non_owner.success is False
        assert non_owner.reason == "unauthorized_actor"
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain == [failed]

    def test_repeated_missing_evidence_rearm_coalesces(self) -> None:
        tracker = _MemoryTracker()
        failed = _exhausted_missing_evidence_record()
        _seed_metadata(tracker, [failed])
        coordinator = _coordinator(tracker, post_comments=False)
        args = (
            _issue("Needs Human"),
            TargetState.DONE,
            ContributorIdentity("project-owner", "api"),
            PROJECT_ID,
            "Evidence supplied",
            self._owner_project(),
        )
        kwargs = {
            "evidence_fingerprint": failed.evidence_fingerprint,
            "evidence_addendum": {
                "evidence_fingerprint": failed.evidence_fingerprint.digest,
                "checks": ["make test"],
            },
        }

        first = _run(coordinator.retry_failed_audit(*args, **kwargs))
        second = _run(coordinator.retry_failed_audit(*args, **kwargs))

        assert first.success is True
        assert second.success is True
        assert second.coalesced is True
        assert second.audit_id == first.audit_id
        assert len(TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain) == 2

    def test_successful_same_fingerprint_is_not_rearmable(self) -> None:
        failed = _exhausted_missing_evidence_record()
        passed = replace(
            failed,
            audit_id="audit-passed",
            attempts=[replace(failed.attempts[0], verdict=Verdict.PASS, failure_classification=None)],
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [passed])
        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue("Needs Human"),
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Evidence supplied",
                self._owner_project(),
                evidence_fingerprint=passed.evidence_fingerprint,
                evidence_addendum={
                    "evidence_fingerprint": passed.evidence_fingerprint.digest,
                    "checks": ["make test"],
                },
            )
        )
        assert result.success is False
        assert result.reason == "audit_not_retryable"

    def test_newer_successful_audit_fences_older_retryable_failure(self) -> None:
        """A completed PASS is final even when an older failure was retryable."""
        failed = _exhausted_no_auditor_record()
        passed = replace(
            failed,
            audit_id="audit-newer-pass",
            attempts=[
                replace(
                    failed.attempts[-1],
                    attempt_id="newer-pass",
                    verdict=Verdict.PASS,
                    failure_classification=None,
                )
            ],
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [failed, passed])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Retry the historical failure",
                self._owner_project(),
                evidence_fingerprint=failed.evidence_fingerprint,
            )
        )

        assert result.success is False
        assert result.reason == "audit_not_retryable"
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain == [failed, passed]

    def test_infrastructure_retry_requires_current_fingerprint(self) -> None:
        """Infrastructure recovery cannot rearm an audit from another head."""
        failed = _exhausted_no_auditor_record()
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [failed])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Retry after infrastructure repair",
                self._owner_project(),
                evidence_fingerprint=_alt_fingerprint(),
            )
        )

        assert result.success is False
        assert result.reason == "evidence_fingerprint_mismatch"

    def test_infrastructure_retry_without_fingerprint_fails_closed(self) -> None:
        failed = _exhausted_no_auditor_record()
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [failed])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Retry after infrastructure repair",
                self._owner_project(),
            )
        )

        assert result.success is False
        assert result.reason == "evidence_fingerprint_mismatch"

    def test_mixed_attempt_history_infrastructure_retry_succeeds(self) -> None:
        """OOMPAH-745: mixed attempt history should not block infrastructure retry.

        A task with multiple failed attempts (e.g., FINALIZATION_FAILURE then NO_AUDITOR)
        should be retryable via infrastructure recovery if the TERMINAL attempt is
        retryable (NO_AUDITOR). Earlier attempts' classifications should not block retry.
        """
        tracker = _MemoryTracker()
        metrics = _MetricsRecorder()
        mixed = _exhausted_mixed_attempt_record()
        _seed_metadata(tracker, [mixed])
        coordinator = _coordinator(tracker, post_comments=False, metrics=metrics)

        # The owner should be able to retry infrastructure even with mixed history
        result = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Auditor provider repaired and redeployed.",
                self._owner_project(),
                evidence_fingerprint=mixed.evidence_fingerprint,
            )
        )

        assert result.success is True
        assert result.status_staged is True
        assert result.superseded_audit_id == mixed.audit_id
        assert tracker.current_status(TASK_ID) == IN_VALIDATION

        # Verify the mixed history is preserved but a fresh record is created
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert len(stored.pending_chain) == 2
        old, fresh = stored.pending_chain
        assert old.request_state == RequestState.SUPERSEDED
        assert old.attempts == mixed.attempts  # History preserved
        assert fresh.request_state == RequestState.PENDING
        assert fresh.evidence_fingerprint == mixed.evidence_fingerprint
        assert fresh.attempts == []  # Fresh record has no attempts yet

        # Alert should be cleared after retry
        assert (
            "clear_actionable_alert",
            (PROJECT_ID, TASK_ID, mixed.audit_id),
        ) in metrics.calls

    def test_mixed_attempt_history_evidence_retry_requires_terminal_missing_evidence(self) -> None:
        """Evidence recovery requires the TERMINAL attempt to be MISSING_EVIDENCE.

        Even if earlier attempts were MISSING_EVIDENCE, if the terminal attempt
        is a different failure type, evidence recovery should fail.
        """
        tracker = _MemoryTracker()
        mixed = replace(
            _exhausted_missing_evidence_record(),
            attempts=[
                _exhausted_missing_evidence_record().attempts[0],  # MISSING_EVIDENCE
                AuditAttempt(
                    attempt_id="no-auditor-terminal",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_exhausted_missing_evidence_record().evidence_fingerprint,
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.FAIL,
                    failure_classification=FailureClassification.NO_AUDITOR,
                    failure_reason="no auditor available",
                    ended_at="2026-07-31T00:02:00+00:00",
                ),
            ],
        )
        tracker_obj = _MemoryTracker()
        _seed_metadata(tracker_obj, [mixed])
        coordinator = _coordinator(tracker_obj, post_comments=False)

        # Evidence recovery should fail because terminal attempt is NO_AUDITOR
        result = _run(
            coordinator.retry_failed_audit(
                _issue("Needs Human"),
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Evidence supplied",
                self._owner_project(),
                evidence_fingerprint=mixed.evidence_fingerprint,
                evidence_addendum={
                    "evidence_fingerprint": mixed.evidence_fingerprint.digest,
                    "checks": ["make test"],
                },
            )
        )

        assert result.success is False
        assert result.reason == "audit_not_retryable"


def _pass_result(record: TerminalAuditRecord, **overrides) -> AuditResult:
    defaults: dict[str, Any] = {
        "audit_id": record.audit_id,
        "target_state": record.target_state,
        "evidence_fingerprint": record.evidence_fingerprint,
        "verdict": Verdict.PASS,
        "message": "All acceptance criteria met.",
        "attempt_id": "attempt-pass-1",
        "auditor": ContributorIdentity("auditor-bot", "oompah"),
        "safe_evidence": {"tests": "13 passed", "commit": "abc123"},
    }
    defaults.update(overrides)
    return AuditResult(**defaults)


def _fail_result(
    record: TerminalAuditRecord,
    classification: FailureClassification,
    *,
    message: str = "Coverage regressed; three tests missing.",
    attempt_id: str = "attempt-fail-1",
) -> AuditResult:
    return AuditResult(
        audit_id=record.audit_id,
        target_state=record.target_state,
        evidence_fingerprint=record.evidence_fingerprint,
        verdict=Verdict.FAIL,
        failure_classification=classification,
        message=message,
        attempt_id=attempt_id,
        auditor=ContributorIdentity("auditor-bot", "oompah"),
    )


def _needs_human_result(
    record: TerminalAuditRecord,
    *,
    message: str = "",
    attempt_id: str = "attempt-nh-1",
) -> AuditResult:
    return AuditResult(
        audit_id=record.audit_id,
        target_state=record.target_state,
        evidence_fingerprint=record.evidence_fingerprint,
        verdict=Verdict.NEEDS_HUMAN,
        message=message,
        attempt_id=attempt_id,
        auditor=ContributorIdentity("auditor-bot", "oompah"),
    )


def _apply(coord: TerminalTransitionCoordinator, issue: Issue, result: AuditResult,
           project_id: str = PROJECT_ID) -> ResultOutcome:
    return _run(coord.apply_audit_result(issue, result, project_id))


def _seed_and_validation(
    tracker: _MemoryTracker,
    chain: list[TerminalAuditRecord],
    task_id: str = TASK_ID,
) -> Issue:
    _seed_metadata(tracker, chain, task_id)
    return Issue(id=task_id, identifier=task_id, title="Test task", state=IN_VALIDATION)


# ---------------------------------------------------------------------------
# TestClassifyFailureToStatus
# ---------------------------------------------------------------------------


class TestClassifyFailureToStatus:
    @pytest.mark.parametrize(
        "classification,expected",
        [
            (FailureClassification.INCOMPLETE, OPEN),
            (FailureClassification.MISSING_TESTS, OPEN),
            (FailureClassification.UNPUSHED, OPEN),
            (FailureClassification.MISSING_EVIDENCE, OPEN),
            (FailureClassification.CI_FAILURE, NEEDS_CI_FIX),
            (FailureClassification.CONFLICT, NEEDS_REBASE),
            (FailureClassification.OUT_OF_DATE, NEEDS_REBASE),
            (FailureClassification.HEALTHY_UNMERGED_REVIEW, IN_REVIEW),
            (FailureClassification.AMBIGUOUS_REQUIREMENTS, NEEDS_HUMAN),
            (FailureClassification.EXTERNAL_CAPABILITY, NEEDS_HUMAN),
            (FailureClassification.NO_AUDITOR, NEEDS_HUMAN),
        ],
    )
    def test_terminal_classifications_route_deterministically(
        self, classification: FailureClassification, expected: str
    ) -> None:
        assert classify_failure_to_status(classification) == expected

    def test_malformed_result_returns_none_for_nonterminal(self) -> None:
        assert classify_failure_to_status(FailureClassification.MALFORMED_RESULT) is None

    def test_infrastructure_error_returns_none_for_nonterminal(self) -> None:
        assert (
            classify_failure_to_status(FailureClassification.INFRASTRUCTURE_ERROR)
            is None
        )

    def test_policy_incompatibility_returns_none_for_nonterminal(self) -> None:
        assert (
            classify_failure_to_status(FailureClassification.POLICY_INCOMPATIBILITY)
            is None
        )

    def test_unsafe_archive_restores_pre_audit_state(self) -> None:
        assert (
            classify_failure_to_status(
                FailureClassification.UNSAFE_ARCHIVE, previous_state="In Progress"
            )
            == "In Progress"
        )

    def test_unsafe_archive_without_previous_state_routes_to_needs_human(self) -> None:
        assert (
            classify_failure_to_status(FailureClassification.UNSAFE_ARCHIVE)
            == NEEDS_HUMAN
        )

    def test_unsafe_archive_previous_terminal_routes_to_needs_human(self) -> None:
        assert (
            classify_failure_to_status(
                FailureClassification.UNSAFE_ARCHIVE, previous_state="Done"
            )
            == NEEDS_HUMAN
        )

    def test_route_failure_status_alias(self) -> None:
        assert route_failure_status(FailureClassification.CI_FAILURE) == NEEDS_CI_FIX


# ---------------------------------------------------------------------------
# TestApplyPassSingleTarget
# ---------------------------------------------------------------------------


class TestApplyPassSingleTarget:
    def test_pass_marks_record_completed(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(record))

        assert outcome.success is True
        assert outcome.applied_status == DONE
        assert outcome.audit_id == record.audit_id

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert doc.pending_chain[0].request_state == RequestState.COMPLETED
        assert len(doc.pending_chain[0].attempts) == 1
        assert doc.pending_chain[0].attempts[0].verdict == Verdict.PASS

    def test_pass_applies_only_audited_terminal_status(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        _apply(coord, issue, _pass_result(record))

        assert tracker.current_status(TASK_ID) == DONE

    def test_pass_posts_result_comment_referencing_target(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.MERGED)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(record))

        assert outcome.posted_comment is True
        posted = tracker.comment_calls[-1][1]
        assert "PASS" in posted
        assert TargetState.MERGED.value in posted

    def test_pass_records_safe_evidence_in_comment(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        _apply(coord, issue, _pass_result(record))

        comment = tracker.comment_calls[-1][1]
        assert "tests: 13 passed" in comment
        assert "commit: abc123" in comment

    def test_pass_archived_target_routes_to_archived_status(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.ARCHIVED)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(record))

        assert outcome.applied_status == ARCHIVED
        assert tracker.current_status(TASK_ID) == ARCHIVED


# ---------------------------------------------------------------------------
# TestApplyPassChainedTargets
# ---------------------------------------------------------------------------


class TestApplyPassChainedTargets:
    def _done_merged_chain(self) -> list[TerminalAuditRecord]:
        return [
            _pending_record(
                audit_id="audit-done",
                target=TargetState.DONE,
                fingerprint=_fingerprint(),
            ),
            _pending_record(
                audit_id="audit-merged",
                target=TargetState.MERGED,
                fingerprint=_fingerprint(),
            ),
        ]

    def test_pass_on_done_keeps_issue_in_validation_until_merged(self) -> None:
        tracker = _MemoryTracker()
        chain = self._done_merged_chain()
        issue = _seed_and_validation(tracker, chain)
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(chain[0]))

        assert outcome.success is True
        assert outcome.advanced_target == TargetState.MERGED
        assert outcome.applied_status == IN_VALIDATION
        assert tracker.current_status(TASK_ID) == IN_VALIDATION

    def test_pass_on_final_chain_item_reaches_terminal_state(self) -> None:
        tracker = _MemoryTracker()
        chain = self._done_merged_chain()
        # Mark Done already completed
        chain[0] = replace(chain[0], request_state=RequestState.COMPLETED)
        issue = _seed_and_validation(tracker, chain)
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(chain[1]))

        assert outcome.applied_status == MERGED
        assert outcome.advanced_target is None
        assert tracker.current_status(TASK_ID) == MERGED

    def test_pass_only_marks_audited_record_completed(self) -> None:
        tracker = _MemoryTracker()
        chain = self._done_merged_chain()
        issue = _seed_and_validation(tracker, chain)
        coord = _coordinator(tracker)

        _apply(coord, issue, _pass_result(chain[0]))

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert doc.pending_chain[0].request_state == RequestState.COMPLETED
        assert doc.pending_chain[1].request_state == RequestState.PENDING

    def test_pass_cancels_sibling_audits_with_same_fingerprint(self) -> None:
        """When a PASS is recorded, sibling audits with the same fingerprint/target are superseded.

        This prevents duplicate audits for the same evidence fingerprint
        (OOMPAH-653: duplicate audit race condition).
        """
        tracker = _MemoryTracker()
        fp = _fingerprint()

        # Create two PENDING records with the same target and fingerprint
        # (simulating a race condition where two audits for the same fingerprint exist)
        sibling1 = _pending_record(audit_id="audit-sibling-1", fingerprint=fp)
        sibling2 = _pending_record(audit_id="audit-sibling-2", fingerprint=fp)

        issue = _seed_and_validation(tracker, [sibling1, sibling2])
        coord = _coordinator(tracker)

        # Apply a PASS to the first sibling
        outcome = _apply(coord, issue, _pass_result(sibling1))

        assert outcome.success is True
        assert outcome.cancelled_audit_ids == ["audit-sibling-2"]

        # Verify both records are in the chain
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert len(doc.pending_chain) == 2

        # First sibling should be COMPLETED
        assert doc.pending_chain[0].audit_id == "audit-sibling-1"
        assert doc.pending_chain[0].request_state == RequestState.COMPLETED

        # Second sibling should be SUPERSEDED (cancelled)
        assert doc.pending_chain[1].audit_id == "audit-sibling-2"
        assert doc.pending_chain[1].request_state == RequestState.SUPERSEDED

    def test_stale_request_rejected_after_pass_completion(self) -> None:
        """After PASS is recorded, new requests with the same fingerprint are rejected.

        This prevents reconciliation from creating a second audit for the same
        evidence fingerprint after the first one has passed (OOMPAH-648).
        """
        tracker = _MemoryTracker()
        fp = _fingerprint()
        record = _pending_record(audit_id="audit-1", fingerprint=fp)

        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        # First request passes
        outcome1 = _apply(coord, issue, _pass_result(record))
        assert outcome1.success is True
        assert outcome1.applied_status == DONE

        # Second request with the same fingerprint should be rejected as stale
        second_result = _run(coord.request_transition(
            _issue(DONE), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))

        assert second_result.success is False
        assert second_result.reason == "already completed"


# ---------------------------------------------------------------------------
# TestApplyFailRouting
# ---------------------------------------------------------------------------


class TestApplyFailRouting:
    @pytest.mark.parametrize(
        "classification,expected_status",
        [
            (FailureClassification.INCOMPLETE, OPEN),
            (FailureClassification.MISSING_TESTS, OPEN),
            (FailureClassification.UNPUSHED, OPEN),
            (FailureClassification.MISSING_EVIDENCE, OPEN),
            (FailureClassification.CI_FAILURE, NEEDS_CI_FIX),
            (FailureClassification.CONFLICT, NEEDS_REBASE),
            (FailureClassification.OUT_OF_DATE, NEEDS_REBASE),
            (FailureClassification.HEALTHY_UNMERGED_REVIEW, IN_REVIEW),
        ],
    )
    def test_fail_classification_routes_to_repair_status(
        self,
        classification: FailureClassification,
        expected_status: str,
    ) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _fail_result(record, classification))

        assert outcome.success is True
        assert outcome.applied_status == expected_status
        assert tracker.current_status(TASK_ID) == expected_status
        assert outcome.posted_comment is True
        posted = tracker.comment_calls[-1][1]
        assert "FAIL" in posted

    def test_fail_records_classification_in_attempt(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        _apply(coord, issue, _fail_result(record, FailureClassification.CI_FAILURE))

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        attempt = doc.pending_chain[0].attempts[-1]
        assert attempt.verdict == Verdict.FAIL
        assert attempt.failure_classification == FailureClassification.CI_FAILURE
        assert doc.pending_chain[0].request_state == RequestState.COMPLETED

    def test_fail_missing_classification_is_rejected(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        result = AuditResult(
            audit_id=record.audit_id,
            target_state=record.target_state,
            evidence_fingerprint=record.evidence_fingerprint,
            verdict=Verdict.FAIL,
            failure_classification=None,
            message="Something went wrong",
            attempt_id="attempt-nofail",
        )
        outcome = _apply(coord, issue, result)

        assert outcome.success is False
        assert outcome.reason == ResultRejection.MISSING_CLASSIFICATION
        assert tracker.current_status(TASK_ID) is None

    def test_fail_needs_human_class_routes_to_needs_human_with_actionable(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(
            coord,
            issue,
            _fail_result(
                record,
                FailureClassification.AMBIGUOUS_REQUIREMENTS,
                message="Please clarify the acceptance criteria for section 3.",
            ),
        )
        assert outcome.applied_status == NEEDS_HUMAN
        assert tracker.current_status(TASK_ID) == NEEDS_HUMAN


# ---------------------------------------------------------------------------
# TestApplyUnsafeArchive
# ---------------------------------------------------------------------------


class TestApplyUnsafeArchive:
    def test_unsafe_archive_restores_previous_state(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(
            target=TargetState.ARCHIVED, previous="In Progress"
        )
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(
            coord, issue, _fail_result(record, FailureClassification.UNSAFE_ARCHIVE)
        )

        assert outcome.success is True
        assert outcome.applied_status == "In Progress"
        assert tracker.current_status(TASK_ID) == "In Progress"

    def test_unsafe_archive_without_previous_state_routes_to_needs_human(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.ARCHIVED, previous=None)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(
            coord,
            issue,
            _fail_result(
                record,
                FailureClassification.UNSAFE_ARCHIVE,
                message="Cannot safely archive — please review and decide.",
            ),
        )
        assert outcome.applied_status == NEEDS_HUMAN


# ---------------------------------------------------------------------------
# TestApplyNeedsHuman
# ---------------------------------------------------------------------------


class TestApplyNeedsHuman:
    def test_needs_human_with_actionable_message_routes_correctly(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(
            coord,
            issue,
            _needs_human_result(
                record,
                message="Please review the branch and decide whether it is safe to close.",
            ),
        )
        assert outcome.success is True
        assert outcome.applied_status == NEEDS_HUMAN
        assert tracker.current_status(TASK_ID) == NEEDS_HUMAN
        posted = tracker.comment_calls[-1][1]
        # Comment ends with an actionable direction/question
        from oompah.tracker import validate_needs_human_comment
        validate_needs_human_comment(posted)

    def test_needs_human_without_message_gets_fallback_instructions(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(
            coord,
            issue,
            _needs_human_result(record, message=""),
        )
        # Fallback tail includes actionable instructions; coordinator applies.
        assert outcome.success is True
        assert outcome.applied_status == NEEDS_HUMAN
        posted = tracker.comment_calls[-1][1]
        assert "Please review" in posted

    def test_needs_human_ends_with_question_is_accepted(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(
            coord,
            issue,
            _needs_human_result(record, message="Should this branch be archived?"),
        )
        assert outcome.applied_status == NEEDS_HUMAN

    def test_needs_human_with_only_status_report_is_upgraded_to_actionable(self) -> None:
        """A message that lacks actionable content is still made actionable
        via the coordinator's fallback so we never leave a Needs Human
        comment that a human cannot act on."""
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(
            coord,
            issue,
            _needs_human_result(record, message="Situation observed."),
        )
        assert outcome.success is True
        posted = tracker.comment_calls[-1][1]
        # Either the original message was already actionable, or the fallback
        # was appended so the tracker validator accepts it.
        from oompah.tracker import validate_needs_human_comment
        validate_needs_human_comment(posted)


# ---------------------------------------------------------------------------
# TestApplyError / TestApplyNonterminalFailures
# ---------------------------------------------------------------------------


class TestApplyError:
    def test_error_verdict_leaves_record_pending(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        result = AuditResult(
            audit_id=record.audit_id,
            target_state=record.target_state,
            evidence_fingerprint=record.evidence_fingerprint,
            verdict=Verdict.ERROR,
            message="Auditor crashed during evaluation.",
            attempt_id="attempt-error-1",
        )
        outcome = _apply(coord, issue, result)

        assert outcome.success is True
        assert outcome.applied_status is None
        # Issue stays in In Validation
        assert tracker.current_status(TASK_ID) is None
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert doc.pending_chain[0].request_state == RequestState.PENDING

    def test_malformed_result_class_leaves_record_pending(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(
            coord,
            issue,
            _fail_result(record, FailureClassification.MALFORMED_RESULT),
        )
        assert outcome.success is True
        assert outcome.applied_status is None
        assert tracker.current_status(TASK_ID) is None
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert doc.pending_chain[0].request_state == RequestState.PENDING

    def test_infrastructure_error_leaves_record_pending(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(
            coord,
            issue,
            _fail_result(record, FailureClassification.INFRASTRUCTURE_ERROR),
        )
        assert outcome.success is True
        assert outcome.applied_status is None
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert doc.pending_chain[0].request_state == RequestState.PENDING


# ---------------------------------------------------------------------------
# TestApplyStaleRejection (CAS)
# ---------------------------------------------------------------------------


class TestApplyStaleRejection:
    def test_wrong_audit_id_is_rejected(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        stale = AuditResult(
            audit_id="audit-nonexistent",
            target_state=record.target_state,
            evidence_fingerprint=record.evidence_fingerprint,
            verdict=Verdict.PASS,
            message="ok",
            attempt_id="attempt-x",
        )
        outcome = _apply(coord, issue, stale)
        assert outcome.success is False
        assert outcome.reason == ResultRejection.AUDIT_NOT_FOUND
        # No terminal status applied
        assert tracker.current_status(TASK_ID) is None

    def test_wrong_target_state_is_rejected(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        stale = AuditResult(
            audit_id=record.audit_id,
            target_state=TargetState.MERGED,
            evidence_fingerprint=record.evidence_fingerprint,
            verdict=Verdict.PASS,
            message="ok",
            attempt_id="attempt-x",
        )
        outcome = _apply(coord, issue, stale)
        assert outcome.success is False
        assert outcome.reason == ResultRejection.TARGET_MISMATCH

    def test_wrong_fingerprint_is_rejected(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE, fingerprint=_fingerprint("a"))
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        stale = AuditResult(
            audit_id=record.audit_id,
            target_state=record.target_state,
            evidence_fingerprint=_fingerprint("b"),
            verdict=Verdict.PASS,
            message="ok",
            attempt_id="attempt-x",
        )
        outcome = _apply(coord, issue, stale)
        assert outcome.success is False
        assert outcome.reason == ResultRejection.FINGERPRINT_MISMATCH

    def test_record_already_completed_is_rejected(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE, state=RequestState.COMPLETED)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(record))
        assert outcome.success is False
        assert outcome.reason == ResultRejection.STATE_MISMATCH

    def test_record_superseded_is_rejected(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE, state=RequestState.SUPERSEDED)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(record))
        assert outcome.success is False
        assert outcome.reason == ResultRejection.STATE_MISMATCH

    def test_issue_not_in_validation_is_rejected(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        _seed_metadata(tracker, [record])
        issue = Issue(id=TASK_ID, identifier=TASK_ID, title="T", state="Open")
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(record))
        assert outcome.success is False
        assert outcome.reason == ResultRejection.ISSUE_NOT_IN_VALIDATION


# ---------------------------------------------------------------------------
# TestApplyDuplicateIdempotency
# ---------------------------------------------------------------------------


class TestApplyDuplicateIdempotency:
    def test_duplicate_attempt_id_is_idempotent(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        first = _apply(coord, issue, _pass_result(record))
        assert first.success is True and first.applied_status == DONE
        first_updates = len(tracker.update_calls)
        first_comments = len(tracker.comment_calls)

        # Second call with the same attempt_id must not repeat side effects.
        second = _apply(coord, issue, _pass_result(record))
        assert second.success is True
        assert second.idempotent is True
        assert second.applied_status == DONE
        assert len(tracker.update_calls) == first_updates
        assert len(tracker.comment_calls) == first_comments

    def test_different_attempt_id_same_audit_is_rejected_after_completion(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        first = _apply(coord, issue, _pass_result(record, attempt_id="a1"))
        assert first.success is True
        # A different attempt id on the same (now completed) audit must not
        # apply again — it is rejected as stale (record no longer pending).
        second_outcome = _apply(
            coord,
            issue,
            _pass_result(record, attempt_id="a2"),
        )
        assert second_outcome.success is False
        assert second_outcome.reason == ResultRejection.STATE_MISMATCH


# ---------------------------------------------------------------------------
# TestApplyCommentFailures / TestApplyStatusFailures
# ---------------------------------------------------------------------------


class _CommentFailingTracker(_MemoryTracker):
    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        raise RuntimeError("comment write failed")


class _StatusFailingTracker(_MemoryTracker):
    def update_issue(self, identifier: str, **kwargs: Any) -> None:
        raise RuntimeError("status write failed")


class _OrderingTracker(_MemoryTracker):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []

    def set_metadata_field(self, identifier: str, key: str, value: Any) -> None:
        self.events.append("metadata")
        super().set_metadata_field(identifier, key, value)

    def update_issue(self, identifier: str, **kwargs: Any) -> None:
        self.events.append("status")
        super().update_issue(identifier, **kwargs)

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        self.events.append("comment")
        return super().add_comment(identifier, text, author)


class TestApplyCommentAndStatusFailures:
    def test_terminal_status_is_accepted_before_result_comment(self) -> None:
        tracker = _OrderingTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker, post_comments=True)

        outcome = _run(coord.apply_audit_result(issue, _pass_result(record), PROJECT_ID))

        assert outcome.success is True
        assert outcome.posted_comment is True
        assert tracker.events.index("metadata") < tracker.events.index("status")
        assert tracker.events.index("status") < tracker.events.index("comment")

    def test_status_failure_never_publishes_result_comment(self) -> None:
        tracker = _StatusFailingTracker()
        record = _pending_record(target=TargetState.DONE)
        _seed_metadata(tracker, [record])
        with tracker._lock:
            tracker._statuses[TASK_ID] = IN_VALIDATION
        issue = Issue(id=TASK_ID, identifier=TASK_ID, title="T", state=IN_VALIDATION)
        coord = TerminalTransitionCoordinator(
            tracker=tracker, project_store=_LockStore(), post_comments=True
        )

        outcome = _run(coord.apply_audit_result(issue, _pass_result(record), PROJECT_ID))

        assert outcome.success is True
        assert outcome.posted_comment is False
        assert tracker.comment_calls == []

    def test_comment_failure_does_not_lose_audit_completion(self) -> None:
        tracker = _CommentFailingTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = TerminalTransitionCoordinator(
            tracker=tracker, project_store=_LockStore(), post_comments=True
        )

        outcome = _run(coord.apply_audit_result(issue, _pass_result(record), PROJECT_ID))
        # Audit record still completed and status still applied.
        assert outcome.success is True
        assert outcome.applied_status == DONE
        assert outcome.posted_comment is False
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert doc.pending_chain[0].request_state == RequestState.COMPLETED

    def test_status_write_failure_still_persists_completed_record(self) -> None:
        tracker = _StatusFailingTracker()
        record = _pending_record(target=TargetState.DONE)
        _seed_metadata(tracker, [record])
        # We have to manually set the status because _StatusFailingTracker.update_issue raises.
        with tracker._lock:
            tracker._statuses[TASK_ID] = IN_VALIDATION
        issue = Issue(id=TASK_ID, identifier=TASK_ID, title="T", state=IN_VALIDATION)
        coord = TerminalTransitionCoordinator(
            tracker=tracker, project_store=_LockStore(), post_comments=False
        )

        outcome = _run(coord.apply_audit_result(issue, _pass_result(record), PROJECT_ID))
        # The audit chain has completed; tracker status write failed but the
        # coordinator still returns success with applied_status telling the
        # caller what it tried to set.
        assert outcome.success is True
        assert outcome.applied_status == DONE
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert doc.pending_chain[0].request_state == RequestState.COMPLETED
        intents = doc.unknown_fields["oompah.terminal_audit_result_intents"]
        assert intents[0]["audit_id"] == record.audit_id
        assert intents[0]["status"] == DONE
        assert intents[0]["applied"] is False

    def test_owner_override_revokes_auditor_authority_before_status(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_done_record()
        _seed_metadata(tracker, [record])
        revoked: list[tuple[str, str]] = []
        coordinator = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=_LockStore(),
            post_comments=False,
            revoke_auditor_authority=lambda project, task: revoked.append(
                (project, task)
            ),
        )
        owner = ContributorIdentity("project-owner", "github")
        project = SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

        result = _run(
            coordinator.override_transition(
                _issue(IN_VALIDATION),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                _fingerprint(),
                "Owner approved this transition.",
                project,
            )
        )

        assert result.success is True
        assert revoked == [(PROJECT_ID, TASK_ID)]


# ---------------------------------------------------------------------------
# TestApplyNoFailOpenPaths
# ---------------------------------------------------------------------------


class TestApplyNoFailOpenPaths:
    """These tests guard against every path that must never reach a
    terminal status."""

    @pytest.mark.parametrize(
        "verdict",
        [Verdict.ERROR],
    )
    def test_error_verdict_never_applies_terminal(self, verdict: Verdict) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        result = AuditResult(
            audit_id=record.audit_id,
            target_state=record.target_state,
            evidence_fingerprint=record.evidence_fingerprint,
            verdict=verdict,
            message="Timed out",
            attempt_id="attempt-error",
        )
        outcome = _apply(coord, issue, result)
        # Non-terminal outcome — no status applied.
        assert outcome.applied_status is None
        assert tracker.current_status(TASK_ID) is None

    @pytest.mark.parametrize(
        "classification",
        [
            FailureClassification.MALFORMED_RESULT,
            FailureClassification.INFRASTRUCTURE_ERROR,
            FailureClassification.POLICY_INCOMPATIBILITY,
        ],
    )
    def test_fail_nonterminal_class_never_applies_terminal(
        self, classification: FailureClassification
    ) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _fail_result(record, classification))
        assert outcome.applied_status is None
        assert tracker.current_status(TASK_ID) is None

    def test_needs_human_without_actionable_content_and_fallback_disabled_fails_closed(
        self,
    ) -> None:
        """If a caller sends a NEEDS_HUMAN with an obviously non-actionable
        message and the tracker's validator rejects it, the coordinator must
        not apply Needs Human status."""

        # We artificially patch validate_needs_human_comment inside the module
        # under test to always raise, simulating a stricter validator that
        # rejects the composed message.
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        with patch(
            "oompah.terminal_transition_coordinator.validate_needs_human_comment",
            side_effect=RuntimeError("no action"),
        ):
            outcome = _apply(coord, issue, _needs_human_result(record, message=""))
        assert outcome.success is False
        assert outcome.reason == ResultRejection.NEEDS_HUMAN_NOT_ACTIONABLE
        assert tracker.current_status(TASK_ID) is None


# ---------------------------------------------------------------------------
# TestApplyBarriersAgainstSecondaryLanes — OOMPAH-653/654 deterministic tests
# ---------------------------------------------------------------------------


def _no_auditor_result(record: TerminalAuditRecord, **overrides) -> AuditResult:
    """The exact FAIL/NO_AUDITOR payload produced by ``_route_no_auditor``."""
    defaults: dict[str, Any] = {
        "audit_id": record.audit_id,
        "target_state": record.target_state,
        "evidence_fingerprint": record.evidence_fingerprint,
        "verdict": Verdict.FAIL,
        "failure_classification": FailureClassification.NO_AUDITOR,
        "message": (
            "No independent auditor candidate is available for this audit "
            "(exhausted). Configure the `auditor` role with at least one "
            "healthy provider/model that is independent of the task contributors, "
            "then move the task back to Open to retry."
        ),
        "attempt_id": f"no-auditor-{record.audit_id}",
    }
    defaults.update(overrides)
    return AuditResult(**defaults)


class TestApplyBarriersAgainstSecondaryLanes:
    """Deterministic barriers protecting a completed PASS/override from
    concurrent no-candidate routing and from duplicate-identity relaunches.

    These tests reproduce the OOMPAH-648, OOMPAH-644, and OOMPAH-654
    live regressions and prove that the durable applied-fingerprint fence
    consumes every equivalent queued identity while retiring associated
    actionable alerts.
    """

    def test_no_candidate_route_rejected_after_pass_persisted(self) -> None:
        """A no-candidate route arriving after PASS must be rejected as stale.

        The dispatch lane's exhaustion path (``_route_no_auditor``) submits a
        ``FAIL/NO_AUDITOR`` result through the coordinator. When PASS has
        already completed the record, the coordinator must reject the late
        no-candidate call — otherwise OOMPAH-648 moves the completed task
        to Needs Human.
        """
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        coord = _coordinator(tracker)

        pass_outcome = _apply(coord, issue, _pass_result(record))
        assert pass_outcome.success is True
        assert pass_outcome.applied_status == DONE
        status_writes_after_pass = len(tracker.update_calls)
        comments_after_pass = len(tracker.comment_calls)

        # The dispatch lane exhausts and calls into the coordinator with the
        # exact NO_AUDITOR payload after the PASS is already durable.  This
        # is what OOMPAH-648 exhibited.
        late_route = _apply(coord, issue, _no_auditor_result(record))
        assert late_route.success is False
        assert late_route.reason == ResultRejection.STATE_MISMATCH
        # The completed record must remain completed, no re-routing happens.
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        assert doc.pending_chain[0].request_state == RequestState.COMPLETED
        # No additional tracker mutations from the late route.
        assert len(tracker.update_calls) == status_writes_after_pass
        assert len(tracker.comment_calls) == comments_after_pass

    def test_no_candidate_route_rejected_after_override_retirement(self) -> None:
        """A no-candidate route arriving after an override must be rejected.

        Reproduces OOMPAH-644: an owner override succeeds while a stale
        no-candidate routing is queued behind it. The retired audit id
        must not be able to reach a FAIL/Needs Human status.
        """
        tracker = _MemoryTracker()
        metrics = _MetricsRecorder()
        record = _pending_record(target=TargetState.DONE)
        _seed_metadata(tracker, [record])
        coord = _coordinator(tracker, post_comments=False, metrics=metrics)
        owner = ContributorIdentity("project-owner", "github")
        project = SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

        override_result = _run(
            coord.override_transition(
                _issue(IN_VALIDATION),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                record.evidence_fingerprint,
                "Owner-authorized override.",
                project,
            )
        )
        assert override_result.success is True
        assert override_result.overridden_audit_ids == [record.audit_id]
        updates_after_override = len(tracker.update_calls)
        comments_after_override = len(tracker.comment_calls)

        # The dispatch lane's exhaustion path arrives after the override.
        issue_after_override = _issue(DONE)
        late_route = _apply(coord, issue_after_override, _no_auditor_result(record))
        assert late_route.success is False
        # Rejected because the issue is no longer in Validation and the record
        # is CANCELLED (not PENDING/IN_PROGRESS).
        assert late_route.reason in (
            ResultRejection.ISSUE_NOT_IN_VALIDATION,
            ResultRejection.STATE_MISMATCH,
        )
        # Tracker status stayed at the overridden target; no extra writes.
        assert tracker.current_status(TASK_ID) == DONE
        assert len(tracker.update_calls) == updates_after_override
        assert len(tracker.comment_calls) == comments_after_override

    def test_one_pass_retires_every_equivalent_queued_identity(self) -> None:
        """OOMPAH-654: one PASS must consume every equivalent queued identity.

        Three PENDING records for the same target/fingerprint but distinct
        audit ids. PASS on the first must retire the other two atomically
        and leave nothing for the dispatch lane to launch — the fix that
        prevents the ``running=1/pending=1`` health snapshot after a PASS.
        """
        from oompah.auditor_dispatch import AuditorDispatchLane

        tracker = _MemoryTracker()
        fp = _fingerprint()
        rec_a = _pending_record(audit_id="audit-A", fingerprint=fp)
        rec_b = _pending_record(audit_id="audit-B", fingerprint=fp)
        rec_c = _pending_record(audit_id="audit-C", fingerprint=fp)

        issue = _seed_and_validation(tracker, [rec_a, rec_b, rec_c])
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(rec_a))
        assert outcome.success is True
        assert outcome.applied_status == DONE
        assert set(outcome.cancelled_audit_ids) == {"audit-B", "audit-C"}

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        doc = store.read(TASK_ID)
        states = {r.audit_id: r.request_state for r in doc.pending_chain}
        assert states == {
            "audit-A": RequestState.COMPLETED,
            "audit-B": RequestState.SUPERSEDED,
            "audit-C": RequestState.SUPERSEDED,
        }

        # Nothing remains for the dispatch lane to launch.
        assert AuditorDispatchLane.pending_record(doc.pending_chain) is None

        # The durable retirement row lists every equivalent identity so that
        # a restart-time reconciliation can rebuild alert state exactly.
        retirements = doc.unknown_fields["oompah.terminal_audit_retirements"]
        assert retirements, "PASS must persist a retirement ledger row"
        retirement = retirements[-1]
        assert set(retirement["audit_ids"]) == {"audit-A", "audit-B", "audit-C"}
        assert retirement.get("applied") is True

    def test_repeated_pass_callbacks_are_idempotent_and_reclear_sibling_alerts(self) -> None:
        """Repeated PASS callbacks must be idempotent and repeatedly clear
        cancelled siblings' actionable alerts, so a callback replay after
        restart re-runs alert cleanup from the durable retirement ledger.
        """
        tracker = _MemoryTracker()
        metrics = _MetricsRecorder()
        fp = _fingerprint()
        sibling_a = _pending_record(audit_id="audit-A", fingerprint=fp)
        sibling_b = _pending_record(audit_id="audit-B", fingerprint=fp)
        issue = _seed_and_validation(tracker, [sibling_a, sibling_b])
        coord = _coordinator(tracker, metrics=metrics)

        first = _apply(coord, issue, _pass_result(sibling_a))
        assert first.success is True
        assert first.idempotent is False
        assert first.cancelled_audit_ids == ["audit-B"]
        # First-time cleanup recorded an actionable-alert clear for audit-B.
        first_clear_calls = [
            call for call in metrics.calls
            if call[0] == "clear_actionable_alert" and call[1][2] == "audit-B"
        ]
        assert len(first_clear_calls) == 1

        second = _apply(coord, issue, _pass_result(sibling_a))
        assert second.success is True
        assert second.idempotent is True
        # A replay callback must still surface every retired identity from
        # the durable retirement ledger so the alert-cleanup path (which is
        # not stateful) can re-run after any crash between the first
        # callback's persistence and its alert clear.  Deliberately includes
        # the passed audit id: any stale alert for the passing audit gets
        # cleared too on replay.
        assert set(second.cancelled_audit_ids) == {"audit-A", "audit-B"}
        second_clear_calls = [
            call for call in metrics.calls
            if call[0] == "clear_actionable_alert" and call[1][2] == "audit-B"
        ]
        assert len(second_clear_calls) == 2

        # But the second callback must not repeat lifecycle counters (no
        # duplicate stale_discarded on the same replay attempt).
        stale_calls = [
            call for call in metrics.calls
            if call[0] == "stale_discarded" and call[1][2] == "audit-B"
        ]


class TestRetryEligibilityFunctions:
    """Test canonical retry-eligibility functions that ensure alert/action parity.

    These tests verify that is_audit_infrastructure_retryable() and
    is_audit_evidence_retryable() correctly identify when an audit is retryable
    based on its TERMINAL (final) attempt classification, ensuring that recovery
    alerts only suggest actions that will actually succeed.
    """

    def test_infrastructure_retryable_for_no_auditor_terminal(self) -> None:
        """NO_AUDITOR terminal failure is retryable via infrastructure."""
        from oompah.terminal_transition_coordinator import (
            is_audit_infrastructure_retryable,
        )

        record = TerminalAuditRecord(
            audit_id="audit-no-auditor",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-1",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_fingerprint(),
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.FAIL,
                    failure_classification=FailureClassification.NO_AUDITOR,
                )
            ],
        )

        assert is_audit_infrastructure_retryable(record) is True

    def test_infrastructure_retryable_for_infrastructure_error_terminal(self) -> None:
        """INFRASTRUCTURE_ERROR terminal failure is retryable via infrastructure."""
        from oompah.terminal_transition_coordinator import (
            is_audit_infrastructure_retryable,
        )

        record = TerminalAuditRecord(
            audit_id="audit-infra-error",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-1",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_fingerprint(),
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.FAIL,
                    failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
                )
            ],
        )

        assert is_audit_infrastructure_retryable(record) is True

    @pytest.mark.parametrize(
        "classification",
        [
            FailureClassification.NO_AUDITOR,
            FailureClassification.INFRASTRUCTURE_ERROR,
            FailureClassification.POLICY_INCOMPATIBILITY,
        ],
    )
    def test_all_infrastructure_recovery_classifications_share_one_mode(
        self, classification: FailureClassification
    ) -> None:
        record = replace(
            _exhausted_no_auditor_record(),
            attempts=[
                replace(
                    _exhausted_no_auditor_record().attempts[-1],
                    failure_classification=classification,
                )
            ],
        )

        from oompah.terminal_transition_coordinator import (
            audit_recovery_mode,
            is_audit_evidence_retryable,
            is_audit_infrastructure_retryable,
        )

        assert audit_recovery_mode(record) == "infrastructure"
        assert is_audit_infrastructure_retryable(record) is True
        assert is_audit_evidence_retryable(record) is False

    def test_evidence_retryable_for_missing_evidence_terminal(self) -> None:
        """MISSING_EVIDENCE terminal failure is retryable via evidence addendum."""
        from oompah.terminal_transition_coordinator import (
            is_audit_evidence_retryable,
        )

        record = TerminalAuditRecord(
            audit_id="audit-missing-evidence",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-1",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_fingerprint(),
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.FAIL,
                    failure_classification=FailureClassification.MISSING_EVIDENCE,
                )
            ],
        )

        assert is_audit_evidence_retryable(record) is True

    def test_not_infrastructure_retryable_for_missing_evidence(self) -> None:
        """MISSING_EVIDENCE terminal is not retryable via infrastructure."""
        from oompah.terminal_transition_coordinator import (
            is_audit_infrastructure_retryable,
        )

        record = TerminalAuditRecord(
            audit_id="audit-missing-evidence",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-1",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_fingerprint(),
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.FAIL,
                    failure_classification=FailureClassification.MISSING_EVIDENCE,
                )
            ],
        )

        assert is_audit_infrastructure_retryable(record) is False

    def test_not_evidence_retryable_for_no_auditor(self) -> None:
        """NO_AUDITOR terminal is not retryable via evidence addendum."""
        from oompah.terminal_transition_coordinator import (
            is_audit_evidence_retryable,
        )

        record = TerminalAuditRecord(
            audit_id="audit-no-auditor",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-1",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_fingerprint(),
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.FAIL,
                    failure_classification=FailureClassification.NO_AUDITOR,
                )
            ],
        )

        assert is_audit_evidence_retryable(record) is False

    def test_mixed_history_infrastructure_retry_uses_terminal_classification(self) -> None:
        """Mixed attempt history should use TERMINAL classification for infrastructure retry.

        OOMPAH-745 regression: when a task has multiple failed attempts
        (e.g., FINALIZATION_FAILURE then NO_AUDITOR), the retryability should be
        determined from the TERMINAL (final) attempt's classification only.
        Earlier attempt classifications should not block retry.
        """
        from oompah.terminal_transition_coordinator import (
            is_audit_infrastructure_retryable,
        )

        record = _exhausted_mixed_attempt_record()
        # Verify the record has mixed history (first attempt is FINALIZATION_FAILURE)
        assert len(record.attempts) == 2
        assert record.attempts[0].failure_classification == FailureClassification.FINALIZATION_FAILURE
        assert record.attempts[1].failure_classification == FailureClassification.NO_AUDITOR

        # Should be retryable via infrastructure based on TERMINAL classification
        assert is_audit_infrastructure_retryable(record) is True

    def test_not_retryable_for_non_terminal_failures(self) -> None:
        """Non-retryable terminal classifications should not allow either recovery mode."""
        from oompah.terminal_transition_coordinator import (
            is_audit_infrastructure_retryable,
            is_audit_evidence_retryable,
        )

        # CI_FAILURE is not retryable
        record = TerminalAuditRecord(
            audit_id="audit-ci-failure",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-1",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_fingerprint(),
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.FAIL,
                    failure_classification=FailureClassification.CI_FAILURE,
                )
            ],
        )

        assert is_audit_infrastructure_retryable(record) is False
        assert is_audit_evidence_retryable(record) is False

    def test_not_retryable_for_successful_completed_audit(self) -> None:
        """Successful completed audits should not be retryable."""
        from oompah.terminal_transition_coordinator import (
            is_audit_infrastructure_retryable,
            is_audit_evidence_retryable,
        )

        record = TerminalAuditRecord(
            audit_id="audit-pass",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-1",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_fingerprint(),
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.PASS,
                    failure_classification=None,
                )
            ],
        )

        assert is_audit_infrastructure_retryable(record) is False
        assert is_audit_evidence_retryable(record) is False

    def test_successful_audit_with_stale_failure_classification_is_final(self) -> None:
        """A stale classification cannot override an explicit PASS verdict."""

        from oompah.terminal_transition_coordinator import (
            is_audit_evidence_retryable,
            is_audit_infrastructure_retryable,
        )

        record = replace(
            _exhausted_no_auditor_record(),
            attempts=[
                replace(
                    _exhausted_no_auditor_record().attempts[-1],
                    verdict=Verdict.PASS,
                    failure_classification=FailureClassification.NO_AUDITOR,
                )
            ],
        )

        assert is_audit_infrastructure_retryable(record) is False
        assert is_audit_evidence_retryable(record) is False

    def test_incomplete_terminal_attempt_is_not_retryable(self) -> None:
        """A completed envelope cannot promote a nonterminal attempt outcome."""

        from oompah.terminal_transition_coordinator import (
            is_audit_evidence_retryable,
            is_audit_infrastructure_retryable,
        )

        record = replace(
            _exhausted_no_auditor_record(),
            attempts=[
                replace(
                    _exhausted_no_auditor_record().attempts[-1],
                    request_state=RequestState.PENDING,
                )
            ],
        )

        assert is_audit_infrastructure_retryable(record) is False
        assert is_audit_evidence_retryable(record) is False

    def test_terminal_attempt_must_match_completed_record_evidence(self) -> None:
        """Retry authority is bound to the terminal attempt's exact evidence."""

        from oompah.terminal_transition_coordinator import (
            is_audit_evidence_retryable,
            is_audit_infrastructure_retryable,
        )

        record = _exhausted_no_auditor_record()
        mismatched = replace(
            record,
            attempts=[
                replace(
                    record.attempts[-1],
                    evidence_fingerprint=_alt_fingerprint(),
                )
            ],
        )

        assert is_audit_infrastructure_retryable(mismatched) is False
        assert is_audit_evidence_retryable(mismatched) is False

    def test_not_retryable_for_pending_records(self) -> None:
        """Pending records should not be considered retryable."""
        from oompah.terminal_transition_coordinator import (
            is_audit_infrastructure_retryable,
            is_audit_evidence_retryable,
        )

        record = TerminalAuditRecord(
            audit_id="audit-pending",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.PENDING,  # Not COMPLETED
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-1",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_fingerprint(),
                    request_state=RequestState.PENDING,
                    verdict=Verdict.FAIL,
                    failure_classification=FailureClassification.NO_AUDITOR,
                )
            ],
        )

        assert is_audit_infrastructure_retryable(record) is False
        assert is_audit_evidence_retryable(record) is False
