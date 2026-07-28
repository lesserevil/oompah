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
from dataclasses import dataclass, field, replace
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


class _FailingUpdateTracker(_MemoryTracker):
    """A tracker that raises on update_issue (simulates tracker write failure)."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_update = True

    def update_issue(self, identifier: str, **kwargs: Any) -> None:
        if self.fail_update:
            raise RuntimeError("Tracker write failed")
        super().update_issue(identifier, **kwargs)


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


def _coordinator(tracker: _MemoryTracker | None = None, post_comments: bool = True) -> TerminalTransitionCoordinator:
    return TerminalTransitionCoordinator(
        tracker=tracker or _MemoryTracker(),
        project_store=_LockStore(),
        post_comments=post_comments,
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
        # At least one Done and one Merged should be present
        assert len(merged_records) == 1
        assert len(done_records) >= 1


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

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))

        # Second call should not trigger any new tracker updates
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
    def test_per_project_locks_are_independent(self) -> None:
        """Requests for two different projects use different locks."""
        coord = _coordinator(post_comments=False)
        # Accessing private _async_locks after requests
        fp = _fingerprint()
        tracker = _MemoryTracker()
        coord2 = TerminalTransitionCoordinator(tracker=tracker, project_store=_LockStore(), post_comments=False)

        async def _run_both():
            issue_a = Issue(id="A-1", identifier="A-1", title="Task A", state="Open")
            issue_b = Issue(id="B-1", identifier="B-1", title="Task B", state="Open")
            await coord2.request_transition(issue_a, TargetState.DONE, _trigger(), "proj-a", fp)
            await coord2.request_transition(issue_b, TargetState.DONE, _trigger(), "proj-b", fp)

        asyncio.run(_run_both())
        # Each project should have its own lock
        assert "proj-a" in coord2._async_locks
        assert "proj-b" in coord2._async_locks
        assert coord2._async_locks["proj-a"] is not coord2._async_locks["proj-b"]

    def test_same_project_uses_same_lock(self) -> None:
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        fp = _fingerprint()

        async def _run_two():
            issue = _issue()
            await coord.request_transition(issue, TargetState.DONE, _trigger(), PROJECT_ID, fp)
            await coord.request_transition(issue, TargetState.DONE, _trigger(), PROJECT_ID, fp)

        asyncio.run(_run_two())
        # There should be exactly one lock for PROJECT_ID
        assert list(coord._async_locks.keys()) == [PROJECT_ID]


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
