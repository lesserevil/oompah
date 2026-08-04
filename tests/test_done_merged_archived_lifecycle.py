"""End-to-end lifecycle test: Done → Merged → Archived audit chain.

This module validates the complete task audit lifecycle described in OOMPAH-488:
- A worker (provider A) does implementation work on an isolated git fixture.
- Worker requests Done; the task moves to ``In Validation``.
- An independent auditor (provider B, not A) inspects the work and submits PASS.
- Task state advances to ``Done``; a review is created.
- The review is correctly merged; auditor (provider C) validates Merged.
- Task ages; a safe-retirement Archived audit runs (provider C or D).
- At each stage: durable comments, metadata, and chain records are asserted.
- Failure variants prove each category returns to the documented repair state.
- Restart recovery is verified between the Done→Merged and Merged→Archived stages.

All fixtures are deterministic and offline — no real providers, no real forges.
"""

from __future__ import annotations

import asyncio
import copy
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest

from oompah.archived_evidence_collector import ArchivedEvidenceCollector, DispositionType
from oompah.done_evidence_collector import EvidenceUnavailable, EvidenceInvalid
from oompah.merged_evidence_collector import (
    FakeSCMProvider,
    FakeSCMReview,
    MergedEvidenceCollector,
)
from oompah.models import Issue
from oompah.scm import CIStatus
from oompah.statuses import (
    ARCHIVED,
    BACKLOG,
    DONE,
    IN_REVIEW,
    IN_VALIDATION,
    MERGED,
    NEEDS_CI_FIX,
    NEEDS_HUMAN,
    NEEDS_REBASE,
    OPEN,
)
from oompah.terminal_audit import (
    AuditAttempt,
    ContributorIdentity,
    EvidenceFingerprint,
    FailureClassification,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    compute_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)
from oompah.terminal_transition_coordinator import (
    AuditResult,
    ResultOutcome,
    TerminalTransitionCoordinator,
    TransitionResult,
    classify_failure_to_status,
)
from oompah.work_contributors import WorkContributor

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ID = "proj-lifecycle-test"
REPO = "owner/lifecycle-repo"
TARGET_BRANCH = "main"
TASK_ID = "TASK-488"
TASK_TITLE = "Validate lifecycle audit chain"

# Provider/model A — the implementation worker
PROVIDER_A = "prov-worker"
MODEL_A = "model-worker-a"

# Provider/model B — the Done auditor (must differ from worker)
PROVIDER_B = "prov-auditor"
MODEL_B = "model-auditor-b"

# Provider/model C — the Merged auditor
PROVIDER_C = "prov-auditor-merged"
MODEL_C = "model-auditor-c"

# Provider/model D — the Archived auditor
PROVIDER_D = "prov-auditor-archived"
MODEL_D = "model-auditor-d"

SOURCE_BRANCH = f"epic/TASK-488"
HEAD_SHA = "a" * 40
MERGE_COMMIT_SHA = "m" * 40
REVIEW_ID = "pr-42"


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
    """In-memory TrackerProtocol double that records all calls."""

    def __init__(self, initial_metadata: dict[str, Any] | None = None) -> None:
        self._lock = threading.Lock()
        self._per_id_metadata: dict[str, dict[str, Any]] = {}
        if initial_metadata:
            self._per_id_metadata[TASK_ID] = copy.deepcopy(initial_metadata)
        self._statuses: dict[str, str] = {}
        self.update_calls: list[tuple[str, dict[str, Any]]] = []
        self.comment_calls: list[tuple[str, str]] = []

    # ------------------------------------------------------------------
    # TrackerProtocol subset
    # ------------------------------------------------------------------

    def get_metadata(self, identifier: str) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._per_id_metadata.get(identifier, {}))

    def set_metadata_field(self, identifier: str, key: str, value: Any) -> None:
        with self._lock:
            self._per_id_metadata.setdefault(identifier, {})[key] = copy.deepcopy(value)

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

    def set_status(self, identifier: str, status: str) -> None:
        """Directly set status (used for test setup)."""
        with self._lock:
            self._statuses[identifier] = status

    def read_chain(self, identifier: str) -> TerminalAuditMetadata:
        """Helper: read the full chain from metadata."""
        store = TerminalAuditMetadataStore(self, _LockStore(), PROJECT_ID)
        return store.read(identifier)

    def chain_len(self, identifier: str) -> int:
        return len(self.read_chain(identifier).pending_chain)

    def comments_containing(self, identifier: str, text: str) -> list[str]:
        with self._lock:
            return [
                body
                for ident, body in self.comment_calls
                if ident == identifier and text in body
            ]


def _issue(state: str = "In Progress") -> Issue:
    return Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title=TASK_TITLE,
        state=state,
        project_id=PROJECT_ID,
        work_branch=SOURCE_BRANCH,
        target_branch=TARGET_BRANCH,
    )


def _coordinator(
    tracker: _MemoryTracker | None = None,
    post_comments: bool = True,
) -> TerminalTransitionCoordinator:
    return TerminalTransitionCoordinator(
        tracker=tracker or _MemoryTracker(),
        project_store=_LockStore(),
        post_comments=post_comments,
    )


def _fingerprint(
    source_sha: str = HEAD_SHA,
    target_sha: str = "b" * 40,
    review_id: str = REVIEW_ID,
) -> EvidenceFingerprint:
    return compute_evidence_fingerprint(
        requirements_text="Implement lifecycle audit validation.",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        source_branch=SOURCE_BRANCH,
        source_sha=source_sha,
        target_branch=TARGET_BRANCH,
        target_sha=target_sha,
        review_id=review_id,
        review_state="open",
    )


def _worker_contributor() -> WorkContributor:
    return WorkContributor(
        run_id=f"{TASK_ID}__20260729T120000Z",
        provider_id=PROVIDER_A,
        provider_name="Worker Provider",
        model_id=MODEL_A,
        focus="feature",
        source_branch=SOURCE_BRANCH,
        source_sha=HEAD_SHA,
        completed_at="2026-07-29T12:00:00+00:00",
    )


def _provider_store_for_candidates(*candidate_pairs: tuple[str, str]):
    """Build valid offline providers for candidate-policy tests."""
    from unittest.mock import MagicMock

    from oompah.models import ModelProvider

    providers = {
        provider_id: ModelProvider(
            id=provider_id,
            name=provider_id,
            base_url="https://provider.test/v1",
            api_key="test-key",
            models=[model],
            default_model=model,
        )
        for provider_id, model in candidate_pairs
    }
    provider_store = MagicMock()
    provider_store.get.side_effect = providers.get
    return provider_store


def _auditor_identity(provider_id: str = PROVIDER_B, model: str = MODEL_B) -> ContributorIdentity:
    return ContributorIdentity(provider_id, "oompah")


def _trigger() -> ContributorIdentity:
    return ContributorIdentity("oompah-orchestrator", "oompah")


def _run(coro):
    return asyncio.run(coro)


def _pass_result(
    record: TerminalAuditRecord,
    auditor_provider: str = PROVIDER_B,
    auditor_model: str = MODEL_B,
    attempt_id: str | None = None,
) -> AuditResult:
    return AuditResult(
        audit_id=record.audit_id,
        target_state=record.target_state,
        evidence_fingerprint=record.evidence_fingerprint,
        verdict=Verdict.PASS,
        message="All checks passed.",
        auditor=ContributorIdentity(auditor_provider, "oompah"),
        attempt_id=attempt_id or str(uuid.uuid4()),
    )


def _fail_result(
    record: TerminalAuditRecord,
    classification: FailureClassification,
    message: str = "Audit failed.",
    needs_human_suffix: str = "",
) -> AuditResult:
    full_message = message
    if needs_human_suffix:
        full_message = message.rstrip() + "\n\n" + needs_human_suffix
    return AuditResult(
        audit_id=record.audit_id,
        target_state=record.target_state,
        evidence_fingerprint=record.evidence_fingerprint,
        verdict=Verdict.FAIL,
        failure_classification=classification,
        message=full_message,
        auditor=ContributorIdentity(PROVIDER_B, "oompah"),
        attempt_id=str(uuid.uuid4()),
    )


def _pending_record(
    audit_id: str = "audit-done",
    target: TargetState = TargetState.DONE,
    fp: EvidenceFingerprint | None = None,
) -> TerminalAuditRecord:
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=target,
        evidence_fingerprint=fp or _fingerprint(),
        request_state=RequestState.PENDING,
        created_at="2026-07-29T00:00:00+00:00",
    )


def _completed_record(
    audit_id: str = "audit-done",
    target: TargetState = TargetState.DONE,
    fp: EvidenceFingerprint | None = None,
) -> TerminalAuditRecord:
    """A Done record already marked COMPLETED (for chaining to Merged)."""
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=target,
        evidence_fingerprint=fp or _fingerprint(),
        request_state=RequestState.COMPLETED,
        created_at="2026-07-01T00:00:00+00:00",
    )


def _seed_chain(
    tracker: _MemoryTracker,
    records: list[TerminalAuditRecord],
) -> None:
    doc = TerminalAuditMetadata(pending_chain=records)
    tracker.set_metadata_field(TASK_ID, METADATA_KEY, doc.to_dict())


# ---------------------------------------------------------------------------
# Scenario helpers
# ---------------------------------------------------------------------------


def _setup_full_happy_path() -> tuple[_MemoryTracker, FakeSCMProvider]:
    """Build a tracker + SCM in a ready-for-Done-request state."""
    tracker = _MemoryTracker()
    tracker.set_status(TASK_ID, "In Progress")

    scm = FakeSCMProvider()
    scm.set_branch_head(REPO, SOURCE_BRANCH, HEAD_SHA)
    scm.set_branch_head(REPO, TARGET_BRANCH, "b" * 40)
    scm.set_ci_status(REPO, HEAD_SHA, CIStatus.PASSED)
    return tracker, scm


def _apply_pass(
    coord: TerminalTransitionCoordinator,
    tracker: _MemoryTracker,
    record: TerminalAuditRecord,
    issue_state: str = IN_VALIDATION,
    auditor_provider: str = PROVIDER_B,
    auditor_model: str = MODEL_B,
) -> ResultOutcome:
    issue = _issue(state=issue_state)
    result = _pass_result(record, auditor_provider, auditor_model)
    return _run(coord.apply_audit_result(issue, result, PROJECT_ID))


# ===========================================================================
# Happy-path lifecycle: Done → Merged → Archived
# ===========================================================================


class TestHappyPathDone:
    """Stage 1: Worker submits work; orchestrator requests Done; auditor passes."""

    def test_request_done_moves_to_in_validation(self):
        tracker, _scm = _setup_full_happy_path()
        coord = _coordinator(tracker)
        fp = _fingerprint()

        result = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))

        assert result.success is True
        assert result.coalesced is False
        assert TargetState.DONE in result.queued_targets
        assert tracker.current_status(TASK_ID) == IN_VALIDATION

    def test_done_audit_chain_record_persisted(self):
        tracker, _ = _setup_full_happy_path()
        coord = _coordinator(tracker)

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        chain = tracker.read_chain(TASK_ID)
        assert len(chain.pending_chain) == 1
        record = chain.pending_chain[0]
        assert record.target_state == TargetState.DONE
        assert record.request_state == RequestState.PENDING
        assert record.previous_state == "In Progress"

    def test_done_request_posts_durable_comment(self):
        tracker, _ = _setup_full_happy_path()
        coord = _coordinator(tracker)

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))

        # Should have posted at least one comment referencing the audit
        assert len(tracker.comment_calls) >= 1
        full_body = " ".join(body for _, body in tracker.comment_calls)
        assert "Done" in full_body or "In Validation" in full_body or "audit" in full_body.lower()

    def test_auditor_b_passes_done_audit_moves_to_done(self):
        tracker, _ = _setup_full_happy_path()
        coord = _coordinator(tracker)
        fp = _fingerprint()

        transition = _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        assert transition.success

        chain = tracker.read_chain(TASK_ID)
        record = chain.pending_chain[0]
        tracker.set_status(TASK_ID, IN_VALIDATION)

        # Auditor B passes — different provider from worker A
        issue_in_val = _issue(state=IN_VALIDATION)
        outcome = _run(coord.apply_audit_result(
            issue_in_val,
            _pass_result(record, PROVIDER_B, MODEL_B),
            PROJECT_ID,
        ))

        assert outcome.success is True
        assert outcome.applied_status == DONE
        assert tracker.current_status(TASK_ID) == DONE

    def test_done_audit_record_marked_completed_after_pass(self):
        tracker, _ = _setup_full_happy_path()
        coord = _coordinator(tracker)
        fp = _fingerprint()

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        chain = tracker.read_chain(TASK_ID)
        record = chain.pending_chain[0]
        tracker.set_status(TASK_ID, IN_VALIDATION)

        _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(record, PROVIDER_B, MODEL_B),
            PROJECT_ID,
        ))

        chain_after = tracker.read_chain(TASK_ID)
        done_record = chain_after.pending_chain[0]
        assert done_record.request_state == RequestState.COMPLETED
        assert len(done_record.attempts) == 1
        assert done_record.attempts[0].verdict == Verdict.PASS

    def test_pass_comment_references_done_target(self):
        tracker, _ = _setup_full_happy_path()
        coord = _coordinator(tracker)

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, _fingerprint()
        ))
        chain = tracker.read_chain(TASK_ID)
        record = chain.pending_chain[0]
        tracker.set_status(TASK_ID, IN_VALIDATION)

        _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(record),
            PROJECT_ID,
        ))

        all_comments = " ".join(body for _, body in tracker.comment_calls)
        assert "Done" in all_comments


class TestHappyPathMerged:
    """Stage 2: After Done passes and review merges, Merged audit runs.

    Key modeling note: when the task is in Done state (terminal), calling
    request_transition(MERGED) queues the Merged audit record but does NOT
    automatically move the tracker status to In Validation.  The orchestrator
    does that separately after detecting the queued audit.  Tests simulate
    this by calling tracker.set_status(TASK_ID, IN_VALIDATION) after the
    request_transition call.
    """

    def _setup_post_done(self) -> tuple[_MemoryTracker, TerminalTransitionCoordinator]:
        """Return tracker with a completed Done audit already in chain.

        Uses issue state 'Done' to represent a task that has passed its Done
        audit. When the orchestrator detects the pending Merged record in the
        chain, it will manually move the task to In Validation.
        """
        tracker = _MemoryTracker()
        tracker.set_status(TASK_ID, DONE)
        done_record = _completed_record("audit-done", TargetState.DONE)
        _seed_chain(tracker, [done_record])
        coord = _coordinator(tracker)
        return tracker, coord

    def test_request_merged_queues_merged_record_in_chain(self):
        """Requesting Merged queues the audit record even from Done state."""
        tracker, coord = self._setup_post_done()
        fp = _fingerprint()

        result = _run(coord.request_transition(
            _issue(state=DONE), TargetState.MERGED, _trigger(), PROJECT_ID, fp
        ))

        assert result.success is True
        # Should queue only Merged (Done already completed in chain)
        assert TargetState.MERGED in result.queued_targets

    def test_request_merged_from_done_state_does_not_move_to_in_validation(self):
        """Coordinator does not auto-move to In Validation from a terminal state.

        The orchestrator handles moving from Done→In Validation after detecting
        the pending Merged audit in the chain.
        """
        tracker, coord = self._setup_post_done()

        _run(coord.request_transition(
            _issue(state=DONE), TargetState.MERGED, _trigger(), PROJECT_ID, _fingerprint()
        ))

        # Issue remains in Done because it was in a terminal state when requested.
        # The orchestrator will move it to In Validation after persisting the chain.
        assert tracker.current_status(TASK_ID) == DONE

    def test_merged_chain_record_persisted(self):
        tracker, coord = self._setup_post_done()

        _run(coord.request_transition(
            _issue(state=DONE), TargetState.MERGED, _trigger(), PROJECT_ID, _fingerprint()
        ))

        chain = tracker.read_chain(TASK_ID)
        # Find Merged record (Done was already completed, only Merged is pending)
        merged_records = [
            r for r in chain.pending_chain
            if r.target_state == TargetState.MERGED
        ]
        assert len(merged_records) == 1
        assert merged_records[0].request_state == RequestState.PENDING

    def test_auditor_c_passes_merged_moves_to_merged(self):
        tracker, coord = self._setup_post_done()

        _run(coord.request_transition(
            _issue(state=DONE), TargetState.MERGED, _trigger(), PROJECT_ID, _fingerprint()
        ))

        chain = tracker.read_chain(TASK_ID)
        merged_record = next(
            r for r in chain.pending_chain if r.target_state == TargetState.MERGED
        )
        # Orchestrator moves task to In Validation before dispatching auditor
        tracker.set_status(TASK_ID, IN_VALIDATION)

        outcome = _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(merged_record, PROVIDER_C, MODEL_C),
            PROJECT_ID,
        ))

        assert outcome.success is True
        assert outcome.applied_status == MERGED
        assert tracker.current_status(TASK_ID) == MERGED

    def test_merged_record_completed_after_pass(self):
        tracker, coord = self._setup_post_done()
        _run(coord.request_transition(
            _issue(state=DONE), TargetState.MERGED, _trigger(), PROJECT_ID, _fingerprint()
        ))
        chain = tracker.read_chain(TASK_ID)
        merged_record = next(
            r for r in chain.pending_chain if r.target_state == TargetState.MERGED
        )
        # Orchestrator moves task to In Validation before dispatching auditor
        tracker.set_status(TASK_ID, IN_VALIDATION)

        _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(merged_record, PROVIDER_C, MODEL_C),
            PROJECT_ID,
        ))

        chain_after = tracker.read_chain(TASK_ID)
        m_record = next(
            r for r in chain_after.pending_chain if r.target_state == TargetState.MERGED
        )
        assert m_record.request_state == RequestState.COMPLETED
        assert m_record.attempts[0].verdict == Verdict.PASS


class TestHappyPathArchived:
    """Stage 3: After Merged, safe-retirement Archived audit runs.

    Same modeling note as TestHappyPathMerged: from Merged (terminal) state,
    request_transition(ARCHIVED) queues the record but doesn't move to
    In Validation automatically. The orchestrator does that.
    """

    def _setup_post_merged(self) -> tuple[_MemoryTracker, TerminalTransitionCoordinator]:
        tracker = _MemoryTracker()
        tracker.set_status(TASK_ID, MERGED)
        done_record = _completed_record("audit-done", TargetState.DONE)
        merged_record = _completed_record("audit-merged", TargetState.MERGED)
        _seed_chain(tracker, [done_record, merged_record])
        coord = _coordinator(tracker)
        return tracker, coord

    def test_request_archived_queues_archived_record_in_chain(self):
        """Requesting Archived queues the audit record even from Merged state."""
        tracker, coord = self._setup_post_merged()

        result = _run(coord.request_transition(
            _issue(state=MERGED), TargetState.ARCHIVED, _trigger(), PROJECT_ID, _fingerprint()
        ))

        assert result.success is True
        assert TargetState.ARCHIVED in result.queued_targets

    def test_archived_chain_record_persisted(self):
        tracker, coord = self._setup_post_merged()
        _run(coord.request_transition(
            _issue(state=MERGED), TargetState.ARCHIVED, _trigger(), PROJECT_ID, _fingerprint()
        ))
        chain = tracker.read_chain(TASK_ID)
        archived_records = [
            r for r in chain.pending_chain if r.target_state == TargetState.ARCHIVED
        ]
        assert len(archived_records) == 1
        assert archived_records[0].request_state == RequestState.PENDING

    def test_auditor_d_passes_archived_audit_moves_to_archived(self):
        tracker, coord = self._setup_post_merged()
        _run(coord.request_transition(
            _issue(state=MERGED), TargetState.ARCHIVED, _trigger(), PROJECT_ID, _fingerprint()
        ))
        chain = tracker.read_chain(TASK_ID)
        arch_record = next(
            r for r in chain.pending_chain if r.target_state == TargetState.ARCHIVED
        )
        tracker.set_status(TASK_ID, IN_VALIDATION)

        outcome = _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(arch_record, PROVIDER_D, MODEL_D),
            PROJECT_ID,
        ))

        assert outcome.success is True
        assert outcome.applied_status == ARCHIVED
        assert tracker.current_status(TASK_ID) == ARCHIVED

    def test_archived_record_completed_with_correct_auditor(self):
        tracker, coord = self._setup_post_merged()
        _run(coord.request_transition(
            _issue(state=MERGED), TargetState.ARCHIVED, _trigger(), PROJECT_ID, _fingerprint()
        ))
        chain = tracker.read_chain(TASK_ID)
        arch_record = next(
            r for r in chain.pending_chain if r.target_state == TargetState.ARCHIVED
        )
        tracker.set_status(TASK_ID, IN_VALIDATION)

        _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(arch_record, PROVIDER_D, MODEL_D),
            PROJECT_ID,
        ))

        chain_after = tracker.read_chain(TASK_ID)
        a_record = next(
            r for r in chain_after.pending_chain if r.target_state == TargetState.ARCHIVED
        )
        assert a_record.request_state == RequestState.COMPLETED
        assert a_record.attempts[0].verdict == Verdict.PASS
        # The auditor identity is stored in requested_by (from AuditResult.auditor)
        assert a_record.attempts[0].requested_by is not None
        assert a_record.attempts[0].requested_by.name == PROVIDER_D

    def test_revisionless_backlog_duplicate_pass_finalizes_archived(self):
        """OOMPAH-803 regression: metadata retirement needs no fake revision."""

        tracker = _MemoryTracker()
        tracker.set_status(TASK_ID, BACKLOG)
        coordinator = _coordinator(tracker)
        issue = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Duplicate task",
            description="Triggered by: OOMPAH-775\n\nDuplicate requirements.",
            state=BACKLOG,
            project_id=PROJECT_ID,
        )
        requested = _run(
            coordinator.request_transition(
                issue,
                TargetState.ARCHIVED,
                _trigger(),
                PROJECT_ID,
                _fingerprint(),
            )
        )
        assert requested.success
        assert tracker.current_status(TASK_ID) == IN_VALIDATION
        record = tracker.read_chain(TASK_ID).pending_chain[-1]

        outcome = _run(
            coordinator.apply_audit_result(
                Issue(
                    id=TASK_ID,
                    identifier=TASK_ID,
                    title="Duplicate task",
                    state=IN_VALIDATION,
                    project_id=PROJECT_ID,
                ),
                _pass_result(record, PROVIDER_D, MODEL_D),
                PROJECT_ID,
            )
        )

        assert outcome.success
        assert outcome.applied_status == ARCHIVED
        assert tracker.current_status(TASK_ID) == ARCHIVED


# ===========================================================================
# Three-stage in-order proof: Done → Merged → Archived with distinct auditors
# ===========================================================================


class TestThreeAuditorsInOrder:
    """Prove that three distinct auditor contracts run in order.

    This single end-to-end scenario drives the complete chain and asserts
    that every audit used a distinct auditor identity and that ordering is
    preserved in the durable chain.
    """

    def test_three_auditors_complete_full_chain_in_order(self):
        tracker = _MemoryTracker()
        tracker.set_status(TASK_ID, "In Progress")
        coord = _coordinator(tracker)
        fp = _fingerprint()

        # -- Stage 1: Request Done → issue is non-terminal → moves to In Validation --
        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        # Issue was In Progress (non-terminal) → coordinator moves to In Validation
        assert tracker.current_status(TASK_ID) == IN_VALIDATION

        chain = tracker.read_chain(TASK_ID)
        done_record = chain.pending_chain[0]

        # Audit B passes Done
        _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(done_record, PROVIDER_B, MODEL_B, attempt_id="attempt-done"),
            PROJECT_ID,
        ))
        assert tracker.current_status(TASK_ID) == DONE

        # -- Stage 2: Request Merged from Done (terminal state) --
        # Coordinator queues Merged record but does NOT auto-move to In Validation
        # (because Done is a terminal status). Orchestrator moves it manually.
        _run(coord.request_transition(
            _issue(state=DONE), TargetState.MERGED, _trigger(), PROJECT_ID, fp
        ))
        # Issue stays Done because it's terminal; orchestrator would move it
        assert tracker.current_status(TASK_ID) == DONE

        chain2 = tracker.read_chain(TASK_ID)
        merged_record = next(
            r for r in chain2.pending_chain if r.target_state == TargetState.MERGED
        )
        # Orchestrator moves task to In Validation (simulated here)
        tracker.set_status(TASK_ID, IN_VALIDATION)

        # Audit C passes Merged
        _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(merged_record, PROVIDER_C, MODEL_C, attempt_id="attempt-merged"),
            PROJECT_ID,
        ))
        assert tracker.current_status(TASK_ID) == MERGED

        # -- Stage 3: Request Archived from Merged (terminal state) --
        _run(coord.request_transition(
            _issue(state=MERGED), TargetState.ARCHIVED, _trigger(), PROJECT_ID, fp
        ))
        # Retention audits from a terminal state stage themselves so the audit
        # worker can observe and complete the Archived transition.
        assert tracker.current_status(TASK_ID) == IN_VALIDATION

        chain3 = tracker.read_chain(TASK_ID)
        arch_record = next(
            r for r in chain3.pending_chain if r.target_state == TargetState.ARCHIVED
        )
        # Audit D passes Archived
        _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(arch_record, PROVIDER_D, MODEL_D, attempt_id="attempt-arch"),
            PROJECT_ID,
        ))
        assert tracker.current_status(TASK_ID) == ARCHIVED

        # -- Assert chain integrity --
        final_chain = tracker.read_chain(TASK_ID)
        targets_in_order = [r.target_state for r in final_chain.pending_chain]
        assert targets_in_order == [TargetState.DONE, TargetState.MERGED, TargetState.ARCHIVED]

        # All three must be COMPLETED
        assert all(
            r.request_state == RequestState.COMPLETED
            for r in final_chain.pending_chain
        )

        # Each record must have exactly one successful attempt.
        # Auditor identity is stored in requested_by (from AuditResult.auditor),
        # not in provider_id (which is only set by the dispatch lane during real runs).
        auditors_used = [
            r.attempts[0].requested_by.name
            for r in final_chain.pending_chain
            if r.attempts and r.attempts[0].requested_by is not None
        ]
        assert auditors_used == [PROVIDER_B, PROVIDER_C, PROVIDER_D]

        # All three auditor identities must be distinct (three independent auditors)
        assert len(set(auditors_used)) == 3

    def test_worker_provider_excluded_from_done_audit(self):
        """The worker (Provider A) must not audit its own work."""
        from unittest.mock import MagicMock
        from oompah.auditor_candidate_selector import AuditorCandidateSelector
        from oompah.roles import Candidate

        worker_contributor = _worker_contributor()

        # Build a role store with auditor candidates A, B (A = worker)
        candidate_a = Candidate(PROVIDER_A, MODEL_A)
        candidate_b = Candidate(PROVIDER_B, MODEL_B)

        role = MagicMock()
        role.candidates = [candidate_a, candidate_b]

        role_store = MagicMock()
        role_store.get = lambda name: role if name == "auditor" else None

        provider_store = _provider_store_for_candidates(
            (PROVIDER_A, MODEL_A), (PROVIDER_B, MODEL_B)
        )

        selector = AuditorCandidateSelector(
            role_store=role_store,
            provider_store=provider_store,
        )

        # With the worker's contribution, Provider A should be excluded
        candidates, reason = selector.select_candidates(
            contributors=[worker_contributor]
        )
        candidate_pairs = {(c.provider_id, c.model) for c in candidates}
        # Provider A (the worker) must not be eligible to audit its own work
        assert (PROVIDER_A, MODEL_A) not in candidate_pairs
        # Provider B should still be available
        assert (PROVIDER_B, MODEL_B) in candidate_pairs


# ===========================================================================
# Self-certification prevention
# ===========================================================================


class TestWorkerCannotSelfCertify:
    """A worker identity must be excluded from auditing the same task."""

    def test_worker_excluded_when_single_provider(self):
        """If only the worker is available, no candidates are returned."""
        from unittest.mock import MagicMock
        from oompah.auditor_candidate_selector import AuditorCandidateSelector
        from oompah.roles import Candidate

        worker_contributor = _worker_contributor()
        candidate_a = Candidate(PROVIDER_A, MODEL_A)

        role = MagicMock()
        role.candidates = [candidate_a]

        role_store = MagicMock()
        role_store.get = lambda name: role if name == "auditor" else None

        provider_store = _provider_store_for_candidates((PROVIDER_A, MODEL_A))

        selector = AuditorCandidateSelector(
            role_store=role_store,
            provider_store=provider_store,
        )

        candidates, reason = selector.select_candidates(
            contributors=[worker_contributor]
        )
        assert candidates == []
        assert reason is not None
        assert reason.reason == "all_are_contributors"

    def test_second_independent_auditor_not_blocked(self):
        """An auditor not in contributors list should pass through."""
        from unittest.mock import MagicMock
        from oompah.auditor_candidate_selector import AuditorCandidateSelector
        from oompah.roles import Candidate

        worker_contributor = _worker_contributor()
        candidate_b = Candidate(PROVIDER_B, MODEL_B)

        role = MagicMock()
        role.candidates = [candidate_b]

        role_store = MagicMock()
        role_store.get = lambda name: role if name == "auditor" else None

        provider_store = _provider_store_for_candidates((PROVIDER_B, MODEL_B))

        selector = AuditorCandidateSelector(
            role_store=role_store,
            provider_store=provider_store,
        )

        candidates, reason = selector.select_candidates(
            contributors=[worker_contributor]
        )
        assert len(candidates) == 1
        assert candidates[0].provider_id == PROVIDER_B
        assert reason is None


# ===========================================================================
# Failure variants
# ===========================================================================


class TestFailureIncompleteWork:
    """FAIL with INCOMPLETE classification returns task to Open."""

    def test_incomplete_fail_returns_to_open(self):
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        record = _pending_record()
        _seed_chain(tracker, [record])
        tracker.set_status(TASK_ID, IN_VALIDATION)

        outcome = _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _fail_result(record, FailureClassification.INCOMPLETE),
            PROJECT_ID,
        ))

        assert outcome.success is True
        assert outcome.applied_status == OPEN
        assert tracker.current_status(TASK_ID) == OPEN

    def test_missing_tests_fail_returns_to_open(self):
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        record = _pending_record()
        _seed_chain(tracker, [record])
        tracker.set_status(TASK_ID, IN_VALIDATION)

        outcome = _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _fail_result(record, FailureClassification.MISSING_TESTS),
            PROJECT_ID,
        ))

        assert outcome.success is True
        assert outcome.applied_status == OPEN
        assert tracker.current_status(TASK_ID) == OPEN

    def test_classify_incomplete_maps_to_open(self):
        result = classify_failure_to_status(FailureClassification.INCOMPLETE)
        assert result == OPEN

    def test_classify_missing_tests_maps_to_open(self):
        result = classify_failure_to_status(FailureClassification.MISSING_TESTS)
        assert result == OPEN


class TestFailureCIFailure:
    """FAIL with CI_FAILURE classification returns task to Needs CI Fix."""

    def test_ci_failure_returns_to_needs_ci_fix(self):
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        record = _pending_record()
        _seed_chain(tracker, [record])
        tracker.set_status(TASK_ID, IN_VALIDATION)

        outcome = _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _fail_result(record, FailureClassification.CI_FAILURE),
            PROJECT_ID,
        ))

        assert outcome.success is True
        assert outcome.applied_status == NEEDS_CI_FIX
        assert tracker.current_status(TASK_ID) == NEEDS_CI_FIX

    def test_classify_ci_failure_maps_to_needs_ci_fix(self):
        result = classify_failure_to_status(FailureClassification.CI_FAILURE)
        assert result == NEEDS_CI_FIX


class TestFailureWrongMergeTarget:
    """Merged audit fails because review targets wrong branch → In Review."""

    def test_wrong_merge_target_using_healthy_unmerged_review(self):
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        record = _pending_record("audit-merged", TargetState.MERGED)
        _seed_chain(tracker, [record])
        tracker.set_status(TASK_ID, IN_VALIDATION)

        outcome = _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _fail_result(record, FailureClassification.HEALTHY_UNMERGED_REVIEW),
            PROJECT_ID,
        ))

        assert outcome.success is True
        assert outcome.applied_status == IN_REVIEW
        assert tracker.current_status(TASK_ID) == IN_REVIEW

    def test_classify_healthy_unmerged_review_maps_to_in_review(self):
        result = classify_failure_to_status(FailureClassification.HEALTHY_UNMERGED_REVIEW)
        assert result == IN_REVIEW

    def test_out_of_date_maps_to_needs_rebase(self):
        result = classify_failure_to_status(FailureClassification.OUT_OF_DATE)
        assert result == NEEDS_REBASE

    def test_conflict_maps_to_needs_rebase(self):
        result = classify_failure_to_status(FailureClassification.CONFLICT)
        assert result == NEEDS_REBASE


class TestFailureUnsafeArchive:
    """Archived audit fails with unsafe_archive → restored to pre-audit state."""

    def test_unsafe_archive_with_merged_previous_routes_to_needs_human(self):
        """When previous_state is Merged (terminal), cannot restore — routes to Needs Human.

        The coordinator never re-enters a terminal status after an unsafe archive failure.
        Instead it routes to Needs Human so an operator can decide the correct repair.
        """
        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        record = _pending_record("audit-arch", TargetState.ARCHIVED)
        from dataclasses import replace
        record_with_prev = replace(record, previous_state=MERGED)
        _seed_chain(tracker, [record_with_prev])
        tracker.set_status(TASK_ID, IN_VALIDATION)

        outcome = _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _fail_result(
                record_with_prev,
                FailureClassification.UNSAFE_ARCHIVE,
                message="Evidence changed after prior audit.",
                # Needs Human requires an actionable suffix
                needs_human_suffix="Operator: please verify the audit evidence and determine if it is safe to proceed.",
            ),
            PROJECT_ID,
        ))

        assert outcome.success is True
        # Merged is terminal; cannot restore → routes to Needs Human
        assert outcome.applied_status == NEEDS_HUMAN

    def test_unsafe_archive_fallback_without_previous_state(self):
        """When previous_state is absent, coordinator falls back to Needs Human."""
        result = classify_failure_to_status(
            FailureClassification.UNSAFE_ARCHIVE, previous_state=None
        )
        # Without a valid previous_state, must route to Needs Human
        assert result == NEEDS_HUMAN

    def test_classify_unsafe_archive_with_terminal_merged_routes_to_needs_human(self):
        """Terminal previous_state (Merged) cannot be restored — routes to Needs Human."""
        result = classify_failure_to_status(
            FailureClassification.UNSAFE_ARCHIVE, previous_state=MERGED
        )
        assert result == NEEDS_HUMAN

    def test_classify_unsafe_archive_with_terminal_done_routes_to_needs_human(self):
        """Terminal previous_state (Done) cannot be restored — routes to Needs Human."""
        result = classify_failure_to_status(
            FailureClassification.UNSAFE_ARCHIVE, previous_state=DONE
        )
        assert result == NEEDS_HUMAN

    def test_classify_unsafe_archive_with_non_terminal_previous_restores_it(self):
        """Non-terminal previous_state (In Progress) can be safely restored."""
        result = classify_failure_to_status(
            FailureClassification.UNSAFE_ARCHIVE, previous_state="In Progress"
        )
        assert result == "In Progress"

    def test_classify_unsafe_archive_with_terminal_archived_routes_to_needs_human(self):
        result = classify_failure_to_status(
            FailureClassification.UNSAFE_ARCHIVE, previous_state=ARCHIVED
        )
        assert result == NEEDS_HUMAN


# ===========================================================================
# Restart recovery
# ===========================================================================


class TestRestartRecovery:
    """State remains correct across simulated process restart.

    Uses the TerminalAuditMetadataStore to persist and reload state,
    proving that a new coordinator instantiated after restart inherits
    the correct chain.
    """

    def test_recovery_after_done_request_before_audit(self):
        """Simulate restart between Done request and auditor PASS.

        After restart:
        - The chain has one PENDING Done record.
        - A newly instantiated coordinator can apply the auditor result.
        """
        tracker = _MemoryTracker()
        tracker.set_status(TASK_ID, "In Progress")

        # Step 1: request Done (coordinator A)
        coord_a = _coordinator(tracker)
        fp = _fingerprint()
        _run(coord_a.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))

        assert tracker.current_status(TASK_ID) == IN_VALIDATION
        chain_before = tracker.read_chain(TASK_ID)
        assert len(chain_before.pending_chain) == 1
        done_record = chain_before.pending_chain[0]
        assert done_record.request_state == RequestState.PENDING

        # -- Simulate restart: create new coordinator (coord_b) --
        coord_b = _coordinator(tracker)
        tracker.set_status(TASK_ID, IN_VALIDATION)

        # Step 2: auditor applies PASS via coord_b
        outcome = _run(coord_b.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(done_record, PROVIDER_B, MODEL_B),
            PROJECT_ID,
        ))

        assert outcome.success is True
        assert outcome.applied_status == DONE
        assert tracker.current_status(TASK_ID) == DONE

        chain_after = tracker.read_chain(TASK_ID)
        assert chain_after.pending_chain[0].request_state == RequestState.COMPLETED

    def test_recovery_after_merged_request_before_audit(self):
        """Simulate restart between Merged request and auditor PASS.

        From Done (terminal) state, request_transition does not auto-move to
        In Validation. The orchestrator does that. We simulate this manually,
        then restart the coordinator and verify the Merged audit still applies.
        """
        tracker = _MemoryTracker()
        tracker.set_status(TASK_ID, DONE)

        # Pre-seed a completed Done record
        done_record = _completed_record("audit-done", TargetState.DONE)
        _seed_chain(tracker, [done_record])

        # Step 1: request Merged (coordinator A)
        coord_a = _coordinator(tracker)
        fp = _fingerprint()
        _run(coord_a.request_transition(
            _issue(state=DONE), TargetState.MERGED, _trigger(), PROJECT_ID, fp
        ))

        # Issue stays Done because it was already terminal; Merged record is in chain
        assert tracker.current_status(TASK_ID) == DONE
        chain_before = tracker.read_chain(TASK_ID)
        merged_record = next(
            r for r in chain_before.pending_chain if r.target_state == TargetState.MERGED
        )
        assert merged_record.request_state == RequestState.PENDING

        # Orchestrator moves task to In Validation (simulated)
        tracker.set_status(TASK_ID, IN_VALIDATION)

        # -- Simulate restart: create new coordinator (coord_b) --
        coord_b = _coordinator(tracker)

        # Step 2: auditor applies PASS via coord_b
        outcome = _run(coord_b.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(merged_record, PROVIDER_C, MODEL_C),
            PROJECT_ID,
        ))

        assert outcome.success is True
        assert outcome.applied_status == MERGED
        assert tracker.current_status(TASK_ID) == MERGED

    def test_idempotent_result_survives_duplicate_delivery(self):
        """The same attempt_id must not advance state twice (idempotent)."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        fp = _fingerprint()

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        chain = tracker.read_chain(TASK_ID)
        done_record = chain.pending_chain[0]
        tracker.set_status(TASK_ID, IN_VALIDATION)

        attempt_id = "idempotent-attempt-1"
        result = _pass_result(done_record, PROVIDER_B, MODEL_B, attempt_id=attempt_id)

        # First delivery
        outcome1 = _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION), result, PROJECT_ID
        ))
        assert outcome1.success is True
        assert outcome1.applied_status == DONE

        # Simulate "restart" — the issue is now Done; second delivery is idempotent
        tracker.set_status(TASK_ID, DONE)
        # Applying the same attempt_id when the issue is not In Validation should be rejected
        outcome2 = _run(coord.apply_audit_result(
            _issue(state=DONE), result, PROJECT_ID
        ))
        # Rejected because issue is no longer In Validation
        assert outcome2.success is False or outcome2.idempotent is True


# ===========================================================================
# Durable metadata and comment assertions
# ===========================================================================


class TestDurableMetadata:
    """Metadata and comments are persisted and survive read-back."""

    def test_chain_survives_json_roundtrip(self):
        """TerminalAuditMetadata round-trips through JSON faithfully."""
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        fp = _fingerprint()

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))

        raw = tracker.get_metadata(TASK_ID).get(METADATA_KEY)
        assert raw is not None
        # Deserialize
        doc = TerminalAuditMetadata.from_dict(raw)
        assert len(doc.pending_chain) == 1
        record = doc.pending_chain[0]
        assert record.target_state == TargetState.DONE
        assert record.request_state == RequestState.PENDING
        assert record.project_id == PROJECT_ID
        assert record.task_id == TASK_ID

    def test_completed_attempt_serializes_auditor_identity(self):
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        fp = _fingerprint()

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))
        chain = tracker.read_chain(TASK_ID)
        record = chain.pending_chain[0]
        tracker.set_status(TASK_ID, IN_VALIDATION)

        _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(record, PROVIDER_B, MODEL_B),
            PROJECT_ID,
        ))

        chain_after = tracker.read_chain(TASK_ID)
        attempt = chain_after.pending_chain[0].attempts[0]
        # Auditor identity is stored in requested_by (not provider_id/model
        # which are only set by the dispatch lane during real orchestrator runs)
        assert attempt.requested_by is not None
        assert attempt.requested_by.name == PROVIDER_B
        assert attempt.verdict == Verdict.PASS

    def test_all_three_stages_recorded_in_chain(self):
        """After three stages, the chain carries all three records."""
        tracker = _MemoryTracker()

        # Seed a fully completed Done+Merged chain
        done_record = _completed_record("audit-done", TargetState.DONE)
        merged_record = _completed_record("audit-merged", TargetState.MERGED)
        arch_record = _completed_record("audit-arch", TargetState.ARCHIVED)
        _seed_chain(tracker, [done_record, merged_record, arch_record])

        chain = tracker.read_chain(TASK_ID)
        assert len(chain.pending_chain) == 3
        targets = [r.target_state for r in chain.pending_chain]
        assert TargetState.DONE in targets
        assert TargetState.MERGED in targets
        assert TargetState.ARCHIVED in targets


# ===========================================================================
# Fake SCM / evidence collector integration
# ===========================================================================


class TestMergedEvidenceWithFakeSCM:
    """MergedEvidenceCollector with FakeSCMProvider (offline, real git).

    Uses the LocalRepo fixture from tests/fixtures_git.py to create a
    deterministic git repository where feature commits are actual ancestors
    of the target branch, matching real merge scenarios.
    """

    def _setup_merged_repo(self, tmp_path):
        """Set up a git repo with a real merge (feature branch → main)."""
        from tests.fixtures_git import LocalRepo, run_git

        repo = LocalRepo(tmp_path / "repo")
        repo.commit("Initial commit", {"README.md": "base content"})

        # Create feature branch and do work
        repo.create_branch(SOURCE_BRANCH, "main")
        feature_sha = repo.commit(
            "TASK-488: implement lifecycle test",
            {"lifecycle.py": "# lifecycle implementation"},
        )

        # Merge feature branch back to main (real git merge)
        repo.checkout("main")
        run_git(repo.path, ["merge", "--no-ff", SOURCE_BRANCH, "-m", f"Merge {SOURCE_BRANCH}"])
        target_sha = run_git(repo.path, ["rev-parse", "HEAD"])

        return repo, feature_sha, target_sha

    def _build_scm(
        self,
        feature_sha: str,
        target_sha: str,
        source_branch: str = SOURCE_BRANCH,
        target_branch: str = TARGET_BRANCH,
        ci_status: CIStatus = CIStatus.PASSED,
        state: str = "merged",
        merge_commit_sha: str | None = None,
    ) -> FakeSCMProvider:
        scm = FakeSCMProvider()
        review = FakeSCMReview(
            review_id=REVIEW_ID,
            state=state,
            source_branch=source_branch,
            target_branch=target_branch,
            head_sha=feature_sha,
            merge_commit_sha=merge_commit_sha or target_sha,
            ci_status=ci_status,
            commits=[feature_sha],
        )
        scm.add_review(REPO, review)
        scm.set_branch_head(REPO, TARGET_BRANCH, target_sha)
        scm.set_branch_head(REPO, source_branch, feature_sha)
        scm.set_ci_status(REPO, feature_sha, ci_status)
        return scm

    def test_correct_merge_produces_no_failures(self, tmp_path):
        """A properly merged review with feature SHA as ancestor yields no failures."""
        repo, feature_sha, target_sha = self._setup_merged_repo(tmp_path)
        scm = self._build_scm(feature_sha, target_sha)

        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch=TARGET_BRANCH,
            task_id=TASK_ID,
            project_id=PROJECT_ID,
            scm_provider=scm,
            worktree_path=str(repo.path),
        )
        fp = compute_evidence_fingerprint(
            requirements_text="Implement lifecycle audit validation.",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            source_branch=SOURCE_BRANCH,
            source_sha=feature_sha,
            target_branch=TARGET_BRANCH,
            target_sha=target_sha,
            review_id=REVIEW_ID,
            review_state="open",
        )
        snap = collector.collect(
            source_branch=SOURCE_BRANCH,
            done_audit_id="audit-done",
            done_audit_verdict=Verdict.PASS,
            done_audit_fingerprint=fp,
        )

        assert not snap.has_failures(), f"Expected no failures, got: {snap.failure_modes}"

    def test_wrong_merge_target_produces_failure(self, tmp_path):
        """A review that targets the wrong branch is flagged as a failure."""
        repo, feature_sha, target_sha = self._setup_merged_repo(tmp_path)

        # Review says it targets "release/v2" instead of "main"
        scm = self._build_scm(
            feature_sha, target_sha, target_branch="release/v2"
        )
        # But our intended target is still "main"
        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch=TARGET_BRANCH,
            task_id=TASK_ID,
            project_id=PROJECT_ID,
            scm_provider=scm,
            worktree_path=str(repo.path),
        )
        snap = collector.collect(
            source_branch=SOURCE_BRANCH,
            done_audit_id="audit-done",
            done_audit_verdict=Verdict.PASS,
            done_audit_fingerprint=_fingerprint(),
        )

        assert snap.has_failures()

    def test_failed_ci_produces_failure(self, tmp_path):
        """A review whose CI failed is flagged as a failure."""
        repo, feature_sha, target_sha = self._setup_merged_repo(tmp_path)
        scm = self._build_scm(
            feature_sha, target_sha, ci_status=CIStatus.FAILED
        )
        collector = MergedEvidenceCollector(
            repo=REPO,
            intended_target_branch=TARGET_BRANCH,
            task_id=TASK_ID,
            project_id=PROJECT_ID,
            scm_provider=scm,
            worktree_path=str(repo.path),
        )
        snap = collector.collect(
            source_branch=SOURCE_BRANCH,
            done_audit_id="audit-done",
            done_audit_verdict=Verdict.PASS,
            done_audit_fingerprint=_fingerprint(),
        )

        assert snap.has_failures()


class TestArchivedEvidenceCollectorSafeRetirement:
    """ArchivedEvidenceCollector validates safe-retirement preconditions."""

    def _base_kwargs(
        self,
        disposition_type: str = DispositionType.RETENTION,
        prior_done_verdict: str = Verdict.PASS,
        prior_merged_verdict: str = Verdict.PASS,
        has_active_worker: bool = False,
        has_open_review: bool = False,
        requirement_changed: bool = False,
    ) -> dict:
        return dict(
            current_state=MERGED,
            disposition_type=disposition_type,
            disposition_explanation="Task is complete and retained per policy.",
            prior_done_audit_id="audit-done",
            prior_done_verdict=prior_done_verdict,
            prior_done_fingerprint=_fingerprint(),
            prior_merged_audit_id="audit-merged",
            prior_merged_verdict=prior_merged_verdict,
            prior_merged_fingerprint=_fingerprint(),
            has_active_worker=has_active_worker,
            has_active_claim=False,
            has_active_retry=False,
            has_open_review=has_open_review,
            has_active_child=False,
            has_unresolved_dependency=False,
            requirement_changed_after_prior_audit=requirement_changed,
            sha_changed_after_prior_audit=False,
            days_since_completion=400,
            retention_days_required=90,
        )

    def test_safe_retirement_produces_no_failures(self):
        """All preconditions met → passed evidence."""
        collector = ArchivedEvidenceCollector(
            task_id=TASK_ID,
            project_id=PROJECT_ID,
        )
        snap = collector.collect(**self._base_kwargs())
        assert snap.passed()
        assert not snap.has_failures()

    def test_active_worker_is_unsafe(self):
        """Task has an active worker → unsafe archive."""
        collector = ArchivedEvidenceCollector(
            task_id=TASK_ID,
            project_id=PROJECT_ID,
        )
        snap = collector.collect(
            **self._base_kwargs(has_active_worker=True)
        )
        assert not snap.passed()
        assert snap.has_failures()

    def test_open_review_is_unsafe(self):
        """Task has an open review → unsafe archive."""
        collector = ArchivedEvidenceCollector(
            task_id=TASK_ID,
            project_id=PROJECT_ID,
        )
        snap = collector.collect(
            **self._base_kwargs(has_open_review=True)
        )
        assert not snap.passed()
        assert snap.has_failures()

    def test_requirement_changed_after_audit_is_unsafe(self):
        """Requirements changed after the prior audit → unsafe archive."""
        collector = ArchivedEvidenceCollector(
            task_id=TASK_ID,
            project_id=PROJECT_ID,
        )
        snap = collector.collect(
            **self._base_kwargs(requirement_changed=True)
        )
        assert not snap.passed()
        assert snap.has_failures()

    def test_no_merged_audit_is_unsafe(self):
        """Missing Merged audit verdict makes archive unsafe.

        For a task at Merged state, the Archived audit requires a prior
        Merged audit with a passing verdict. When that verdict is absent,
        the archive fails.
        """
        collector = ArchivedEvidenceCollector(
            task_id=TASK_ID,
            project_id=PROJECT_ID,
        )
        snap = collector.collect(
            **self._base_kwargs(prior_merged_verdict="")  # missing/empty merged verdict
        )
        assert not snap.passed()


# ===========================================================================
# API summary and chain metrics
# ===========================================================================


class TestChainMetrics:
    """Chain records expose the information needed for API summaries."""

    def test_chain_entry_count_matches_number_of_stages(self):
        tracker = _MemoryTracker()
        done = _completed_record("a1", TargetState.DONE)
        merged = _completed_record("a2", TargetState.MERGED)
        archived = _completed_record("a3", TargetState.ARCHIVED)
        _seed_chain(tracker, [done, merged, archived])

        chain = tracker.read_chain(TASK_ID)
        assert len(chain.pending_chain) == 3

    def test_audit_ids_are_unique_in_chain(self):
        tracker = _MemoryTracker()
        done = _completed_record("audit-done-1", TargetState.DONE)
        merged = _completed_record("audit-merged-2", TargetState.MERGED)
        archived = _completed_record("audit-archived-3", TargetState.ARCHIVED)
        _seed_chain(tracker, [done, merged, archived])

        chain = tracker.read_chain(TASK_ID)
        audit_ids = [r.audit_id for r in chain.pending_chain]
        assert len(audit_ids) == len(set(audit_ids)), "All audit IDs must be unique"

    def test_request_state_transitions_are_tracked(self):
        tracker = _MemoryTracker()
        coord = _coordinator(tracker)
        fp = _fingerprint()

        _run(coord.request_transition(
            _issue(), TargetState.DONE, _trigger(), PROJECT_ID, fp
        ))

        chain = tracker.read_chain(TASK_ID)
        record = chain.pending_chain[0]
        assert record.request_state == RequestState.PENDING

        tracker.set_status(TASK_ID, IN_VALIDATION)
        _run(coord.apply_audit_result(
            _issue(state=IN_VALIDATION),
            _pass_result(record),
            PROJECT_ID,
        ))

        chain_after = tracker.read_chain(TASK_ID)
        assert chain_after.pending_chain[0].request_state == RequestState.COMPLETED
