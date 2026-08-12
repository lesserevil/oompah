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

from oompah.auditor_dispatch import AuditorDispatchLane
from oompah.integration import IntegrationRecord
from oompah.models import Issue
from oompah.terminal_audit import (
    AuditAttempt,
    AuditRevisionBinding,
    ContributorIdentity,
    EvidenceFingerprint,
    OverrideRecord,
    RequestState,
    TargetState,
    TerminalAuditRecord,
    Verdict,
    compute_integrated_evidence_fingerprint_variants,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadata,
    TerminalAuditMetadataStore,
)
from oompah.terminal_transition_coordinator import (
    OverrideRejection,
    ResultRejection,
    TerminalTransitionCoordinator,
    TerminalTransitionBusyError,
    TransitionResult,
    _build_new_entries,
    accepted_audit_recovery_action,
)
from oompah.statuses import ARCHIVED, DONE, IN_VALIDATION, MERGED, NEEDS_HUMAN


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


class _RevisionLockStore(_LockStore):
    """Lock provider with deterministic repository revision resolution."""

    def __init__(self, revisions: dict[str, str]) -> None:
        super().__init__()
        self.revisions = revisions
        self.resolve_calls: list[str] = []
        self.project = SimpleNamespace(default_branch="main")

    def get(self, project_id: str) -> Any:
        return self.project if project_id == PROJECT_ID else None

    def resolve_audit_revision(self, project_id: str, revision: str) -> str:
        assert project_id == PROJECT_ID
        self.resolve_calls.append(revision)
        if revision not in self.revisions:
            raise ValueError(f"terminal audit revision is unavailable: {revision}")
        return self.revisions[revision]


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


class _RefreshingTracker(_MemoryTracker):
    """Production-shaped tracker whose detail read can advance independently."""

    def __init__(self, issue: Issue) -> None:
        super().__init__()
        self.issue = copy.deepcopy(issue)
        self.invalidations = 0

    def invalidate_read_cache(self) -> None:
        self.invalidations += 1

    def fetch_issue_detail(self, identifier: str) -> Issue:
        assert identifier == self.issue.identifier
        return copy.deepcopy(self.issue)

    def update_issue(self, identifier: str, **kwargs: Any) -> None:
        super().update_issue(identifier, **kwargs)
        if "status" in kwargs:
            self.issue.state = kwargs["status"]


class _UnavailableRefreshingTracker(_MemoryTracker):
    """Advertise a production detail reader that cannot prove current evidence."""

    def fetch_issue_detail(self, _identifier: str) -> Issue | None:
        raise RuntimeError("tracker detail read unavailable")


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

    def record_control_lock_timing(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append(("control_lock", (*args, kwargs)))


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


def _oompah_660_override_issue() -> Issue:
    issue = Issue(
        id="OOMPAH-660",
        identifier="OOMPAH-660",
        title="Rebase epic-OOMPAH-619 onto main",
        description=(
            "The epic branch `epic-OOMPAH-619` is stale. Rebase it onto "
            "`origin/main` and work directly on the existing epic branch."
        ),
        state=MERGED,
        parent_id="OOMPAH-619",
        project_id=PROJECT_ID,
        work_branch="epic-OOMPAH-619--task-OOMPAH-660",
    )
    issue.integration = IntegrationRecord(
        state="integrated",
        attempts=2,
        task_branch="epic-OOMPAH-619--task-OOMPAH-660",
        base_branch="epic-OOMPAH-619",
        base_sha="17658b95e32641e8cf2dbfff06f780c0f6b57916",
        head_sha="793bcc7969d39634dab560ed0a10b9dcad7a9716",
        integrated_sha="793bcc7969d39634dab560ed0a10b9dcad7a9716",
    )
    return issue


def _coordinator(
    tracker: _MemoryTracker | None = None,
    post_comments: bool = True,
    metrics: Any | None = None,
    validate_terminal_transition: Any | None = None,
    clear_integrated_audit_recovery_alert: Any | None = None,
) -> TerminalTransitionCoordinator:
    return TerminalTransitionCoordinator(
        tracker=tracker or _MemoryTracker(),
        project_store=_LockStore(),
        post_comments=post_comments,
        metrics=metrics,
        clear_integrated_audit_recovery_alert=(
            clear_integrated_audit_recovery_alert
        ),
        validate_terminal_transition=validate_terminal_transition,
    )


def _run(coro):
    """Run a coroutine in a new event loop."""
    return asyncio.run(coro)


def test_owner_control_lock_timeout_is_bounded_and_never_runs_mutation():
    tracker = _MemoryTracker()
    locks = _LockStore()
    metrics = _MetricsRecorder()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=locks,
        metrics=metrics,
        owner_control_lock_timeout_seconds=0.02,
    )
    project_lock = locks.project_write_lock(PROJECT_ID)

    with project_lock:
        started = time.monotonic()
        with pytest.raises(TerminalTransitionBusyError):
            _run(
                coordinator.override_transition(
                    current_issue=_issue(IN_VALIDATION),
                    requested_target=TargetState.DONE,
                    authorized_actor=ContributorIdentity("owner", "api"),
                    project_id=PROJECT_ID,
                    evidence_fingerprint=_fingerprint(),
                    reason="Owner accepts this exact revision.",
                    project=SimpleNamespace(tracker_owner="owner"),
                )
            )
        elapsed = time.monotonic() - started

    assert elapsed < 0.5
    assert tracker.get_metadata(TASK_ID) == {}
    timing = [call for call in metrics.calls if call[0] == "control_lock"]
    assert len(timing) == 1
    assert timing[0][1][-1]["timed_out"] is True


def test_automatic_transition_serialization_waits_instead_of_dropping_mutation():
    locks = _LockStore()
    coordinator = TerminalTransitionCoordinator(
        tracker=_MemoryTracker(),
        project_store=locks,
        owner_control_lock_timeout_seconds=0.02,
    )
    project_lock = locks.project_write_lock(PROJECT_ID)
    operation_ran = threading.Event()
    completed = threading.Event()

    def automatic_transition():
        coordinator._run_project_serialized(
            PROJECT_ID,
            lambda: operation_ran.set(),
        )
        completed.set()

    with project_lock:
        worker = threading.Thread(target=automatic_transition)
        worker.start()
        time.sleep(0.05)
        assert operation_ran.is_set() is False
        assert completed.is_set() is False

    worker.join(timeout=1)
    assert not worker.is_alive()
    assert operation_ran.is_set() is True
    assert completed.is_set() is True


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


def test_request_persists_canonical_revision_before_tracker_refresh() -> None:
    tracker = _MemoryTracker()
    sha = "7" * 40
    project_store = _RevisionLockStore({"origin/epic-OOMPAH-768": sha})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    issue = Issue(
        id="OOMPAH-768",
        identifier="OOMPAH-768",
        title="Systemic workflow epic",
        description="Complete the workflow program.",
        state="In Progress",
        issue_type="epic",
        project_id=PROJECT_ID,
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)

    result = _run(
        coordinator.request_transition(
            issue,
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            fingerprint,
        )
    )
    initial_resolve_calls = list(project_store.resolve_calls)
    issue.branch_name = "OOMPAH-768"
    project_store.resolve_calls.clear()
    repeated = _run(
        coordinator.request_transition(
            issue,
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            fingerprint,
        )
    )
    document = TerminalAuditMetadataStore(
        tracker,
        project_store,
        PROJECT_ID,
    ).read(issue.identifier)

    assert result.success is True
    assert repeated.success is True
    assert repeated.coalesced is True
    assert document.pending_chain[0].evidence_fingerprint == fingerprint
    assert document.pending_chain[0].selected_ref == "origin/epic-OOMPAH-768"
    assert document.pending_chain[0].selected_sha == sha
    assert initial_resolve_calls == ["origin/epic-OOMPAH-768"]
    assert project_store.resolve_calls == []


def test_composed_landing_revision_binds_audit_without_mutable_task_ref() -> None:
    tracker = _MemoryTracker()
    revision = "3" * 40
    project_store = _RevisionLockStore({revision: revision})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    issue = Issue(
        id="OOMPAH-787",
        identifier="OOMPAH-787",
        title="Composed child",
        description="Accepted into its immediate epic target.",
        state="Done",
        project_id=PROJECT_ID,
        parent_id="OOMPAH-771",
        work_branch=None,
        target_branch=None,
        head_sha=None,
        integration=None,
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
    trigger = ContributorIdentity("oompah-workflow-rollup", "integrator")
    guard = lambda: None

    result = _run(
        coordinator.request_transition(
            issue,
            TargetState.MERGED,
            trigger,
            PROJECT_ID,
            fingerprint,
            mutation_guard=guard,
            revision_binding=AuditRevisionBinding(revision, revision),
        )
    )
    repeated = _run(
        coordinator.request_transition(
            issue,
            TargetState.MERGED,
            trigger,
            PROJECT_ID,
            fingerprint,
            mutation_guard=guard,
            revision_binding=AuditRevisionBinding(revision, revision),
        )
    )
    record = TerminalAuditMetadataStore(
        tracker, project_store, PROJECT_ID
    ).read(issue.identifier).pending_chain[0]

    assert result.success
    assert repeated.success
    assert repeated.coalesced
    assert record.selected_ref == revision
    assert record.selected_sha == revision
    assert project_store.resolve_calls == [revision, revision]


def test_headless_root_epic_landing_revision_binds_terminal_audit() -> None:
    tracker = _MemoryTracker()
    revision = "3" * 40
    project_store = _RevisionLockStore({revision: revision})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    issue = Issue(
        id="OOMPAH-940",
        identifier="OOMPAH-940",
        title="Systemic workflow program",
        description="Accepted into the default branch.",
        state="In Progress",
        issue_type="epic",
        project_id=PROJECT_ID,
        parent_id=None,
        work_branch=None,
        target_branch=None,
        head_sha=None,
        integration=None,
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
    trigger = ContributorIdentity("oompah", "orchestrator")

    result = _run(
        coordinator.request_transition(
            issue,
            TargetState.MERGED,
            trigger,
            PROJECT_ID,
            fingerprint,
            mutation_guard=lambda: None,
            revision_binding=AuditRevisionBinding(revision, revision),
        )
    )
    document = TerminalAuditMetadataStore(
        tracker, project_store, PROJECT_ID
    ).read(issue.identifier)

    assert result.success
    assert [record.target_state for record in document.pending_chain] == [
        TargetState.DONE,
        TargetState.MERGED,
    ]
    assert all(record.selected_ref == revision for record in document.pending_chain)
    assert all(record.selected_sha == revision for record in document.pending_chain)
    assert tracker.current_status(issue.identifier) == IN_VALIDATION
    assert project_store.resolve_calls == [revision]


def test_landed_root_epic_target_advance_aba_never_reuses_stale_audit() -> None:
    landing = "3" * 40
    first_target = "4" * 40
    advanced_target = "5" * 40

    class ContainingStore(_RevisionLockStore):
        def __init__(self) -> None:
            super().__init__({})
            self.target_heads = [first_target, advanced_target, first_target]
            self.containment_calls: list[tuple[str, str]] = []

        def resolve_containing_audit_revision(
            self,
            project_id: str,
            *,
            target_revision: str,
            landing_revision: str,
        ) -> str:
            assert project_id == PROJECT_ID
            self.containment_calls.append((target_revision, landing_revision))
            return self.target_heads.pop(0)

    tracker = _MemoryTracker()
    store = ContainingStore()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=store,
        post_comments=False,
    )
    issue = Issue(
        id="OOMPAH-940",
        identifier="OOMPAH-940",
        title="Systemic workflow program",
        state="In Progress",
        issue_type="epic",
        project_id=PROJECT_ID,
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
    trigger = ContributorIdentity("oompah", "orchestrator")

    first = _run(
        coordinator.request_transition(
            issue,
            TargetState.MERGED,
            trigger,
            PROJECT_ID,
            fingerprint,
            mutation_guard=lambda: None,
            landing_revision=landing,
            workflow_revision="epic-evidence-1",
        )
    )
    advanced = _run(
        coordinator.request_transition(
            issue,
            TargetState.MERGED,
            trigger,
            PROJECT_ID,
            fingerprint,
            mutation_guard=lambda: None,
            landing_revision=landing,
            workflow_revision="epic-evidence-1",
        )
    )
    returned = _run(
        coordinator.request_transition(
            issue,
            TargetState.MERGED,
            trigger,
            PROJECT_ID,
            fingerprint,
            mutation_guard=lambda: None,
            landing_revision=landing,
            workflow_revision="epic-evidence-1",
        )
    )
    document = TerminalAuditMetadataStore(
        tracker, store, PROJECT_ID
    ).read(issue.identifier)
    current = [
        record
        for record in document.pending_chain
        if record.request_state in {RequestState.PENDING, RequestState.IN_PROGRESS}
    ]

    assert first.success
    assert advanced.success
    assert not advanced.coalesced
    assert returned.success
    assert not returned.coalesced
    assert {record.selected_ref for record in current} == {"origin/main"}
    assert {record.selected_sha for record in current} == {first_target}
    assert {record.landing_revision for record in current} == {landing}
    assert {record.source_generation for record in current} == {3}
    assert store.containment_calls == [
        ("origin/main", landing),
        ("origin/main", landing),
        ("origin/main", landing),
    ]


def test_landed_nested_epic_routes_validation_to_parent_branch() -> None:
    landing = "6" * 40
    target = "7" * 40
    parent = Issue(
        id="PARENT-1",
        identifier="PARENT-1",
        title="Parent epic",
        state="In Progress",
        issue_type="epic",
        project_id=PROJECT_ID,
    )

    class NestedTracker(_MemoryTracker):
        def fetch_issue_detail(self, identifier: str) -> Issue | None:
            if identifier == parent.identifier:
                return copy.deepcopy(parent)
            if identifier == issue.identifier:
                return copy.deepcopy(issue)
            return None

    class NestedStore(_RevisionLockStore):
        def __init__(self) -> None:
            super().__init__({})
            self.call: tuple[str, str] | None = None

        @staticmethod
        def epic_branch_name(identifier: str) -> str:
            return f"epic-{identifier}"

        def resolve_containing_audit_revision(
            self,
            project_id: str,
            *,
            target_revision: str,
            landing_revision: str,
        ) -> str:
            assert project_id == PROJECT_ID
            self.call = (target_revision, landing_revision)
            return target

    tracker = NestedTracker()
    store = NestedStore()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=store,
        post_comments=False,
    )
    issue = Issue(
        id="CHILD-EPIC",
        identifier="CHILD-EPIC",
        title="Nested epic",
        state="Done",
        issue_type="epic",
        project_id=PROJECT_ID,
        parent_id=parent.identifier,
        head_sha=landing,
    )

    result = _run(
        coordinator.request_transition(
            issue,
            TargetState.MERGED,
            ContributorIdentity("oompah", "orchestrator"),
            PROJECT_ID,
            compute_issue_evidence_fingerprint(issue, PROJECT_ID),
            mutation_guard=lambda: None,
            landing_revision=landing,
            workflow_revision="nested-evidence-1",
        )
    )

    assert result.success
    assert store.call == ("origin/epic-PARENT-1", landing)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    (
        ("missing_guard", "requires a workflow mutation guard"),
        ("wrong_role", "requires a current Done task"),
        ("wrong_status", "requires a current In Progress task"),
        ("wrong_target", "requires a Merged transition"),
        ("parented", "requires a root epic"),
        ("non_epic", "requires an epic task"),
        ("ordinary_head", "cannot replace a task-owned head"),
        ("wrong_project", "project authority changed"),
        ("non_sha_ref", "must use its exact SHA as the ref"),
        ("unresolvable", "revision is unavailable"),
        ("mismatch", "resolved to a different commit"),
    ),
)
def test_headless_root_epic_landing_revision_override_fails_closed(
    mutation,
    reason,
) -> None:
    revision = "3" * 40
    revisions = {revision: revision}
    if mutation == "unresolvable":
        revisions = {}
    elif mutation == "mismatch":
        revisions = {revision: "4" * 40}
    tracker = _MemoryTracker()
    project_store = _RevisionLockStore(revisions)
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    issue = Issue(
        id="OOMPAH-940",
        identifier="OOMPAH-940",
        title="Systemic workflow program",
        state="In Review" if mutation == "wrong_status" else "In Progress",
        issue_type="task" if mutation == "non_epic" else "epic",
        project_id="wrong-project" if mutation == "wrong_project" else PROJECT_ID,
        parent_id="PARENT-1" if mutation == "parented" else None,
        head_sha=revision if mutation == "ordinary_head" else None,
    )
    trigger = ContributorIdentity(
        "oompah",
        "integrator" if mutation == "wrong_role" else "orchestrator",
    )
    binding = AuditRevisionBinding(
        "origin/epic-OOMPAH-940" if mutation == "non_sha_ref" else revision,
        revision,
    )

    result = _run(
        coordinator.request_transition(
            issue,
            TargetState.DONE if mutation == "wrong_target" else TargetState.MERGED,
            trigger,
            PROJECT_ID,
            compute_issue_evidence_fingerprint(issue, PROJECT_ID),
            mutation_guard=None if mutation == "missing_guard" else lambda: None,
            revision_binding=binding,
        )
    )

    assert not result.success
    assert reason in str(result.reason)
    assert tracker.update_calls == []


@pytest.mark.parametrize(
    ("mutation", "reason"),
    (
        ("missing_guard", "requires a workflow mutation guard"),
        ("wrong_role", "requires integrator authority"),
        ("wrong_status", "requires a current Done task"),
        ("wrong_target", "requires a Merged transition"),
        ("parentless", "requires a parented task"),
        ("ordinary_head", "cannot replace a task-owned head"),
        ("wrong_project", "project authority changed"),
        ("non_sha_ref", "must use its exact SHA as the ref"),
        ("unresolvable", "revision is unavailable"),
        ("mismatch", "resolved to a different commit"),
    ),
)
def test_composed_landing_revision_override_fails_closed(mutation, reason) -> None:
    revision = "3" * 40
    revisions = {revision: revision}
    if mutation == "unresolvable":
        revisions = {}
    elif mutation == "mismatch":
        revisions = {revision: "4" * 40}
    tracker = _MemoryTracker()
    project_store = _RevisionLockStore(revisions)
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    issue = Issue(
        id="OOMPAH-787",
        identifier="OOMPAH-787",
        title="Composed child",
        state="In Review" if mutation == "wrong_status" else "Done",
        project_id="wrong-project" if mutation == "wrong_project" else PROJECT_ID,
        parent_id=None if mutation == "parentless" else "OOMPAH-771",
        head_sha=revision if mutation == "ordinary_head" else None,
    )
    trigger = ContributorIdentity(
        "oompah-workflow-rollup",
        "worker" if mutation == "wrong_role" else "integrator",
    )
    binding = AuditRevisionBinding(
        "origin/composed" if mutation == "non_sha_ref" else revision,
        revision,
    )

    result = _run(
        coordinator.request_transition(
            issue,
            TargetState.DONE if mutation == "wrong_target" else TargetState.MERGED,
            trigger,
            PROJECT_ID,
            compute_issue_evidence_fingerprint(issue, PROJECT_ID),
            mutation_guard=None if mutation == "missing_guard" else lambda: None,
            revision_binding=binding,
        )
    )

    assert not result.success
    assert reason in str(result.reason)
    assert tracker.update_calls == []


def test_aged_done_auto_archive_binds_main_before_coalesced_retry() -> None:
    """The retention exception is bound once from its original provenance."""
    tracker = _MemoryTracker()
    sha = "d" * 40
    project_store = _RevisionLockStore({"origin/main": sha})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    issue = _issue(DONE)
    fingerprint = _fingerprint()

    initial = coordinator.request_transition_sync(
        issue,
        TargetState.ARCHIVED,
        ContributorIdentity("oompah", "auto_archive"),
        PROJECT_ID,
        fingerprint,
        coalesce_pending_target=True,
    )
    repeated = coordinator.request_transition_sync(
        issue,
        TargetState.ARCHIVED,
        ContributorIdentity("operator", "api"),
        PROJECT_ID,
        fingerprint,
        coalesce_pending_target=True,
    )
    record = TerminalAuditMetadataStore(
        tracker,
        project_store,
        PROJECT_ID,
    ).read(TASK_ID).pending_chain[0]

    assert initial.success is True
    assert repeated.success is True
    assert repeated.coalesced is True
    assert record.requested_by == ContributorIdentity("oompah", "auto_archive")
    assert record.selected_ref == "origin/main"
    assert record.selected_sha == sha
    assert project_store.resolve_calls == ["origin/main"]


def test_terminal_transition_fails_closed_while_delivery_effect_is_admitted() -> None:
    """A busy delivery generation is retryable and no audit mutation begins."""

    tracker = _MemoryTracker()
    project_store = _RevisionLockStore({"origin/main": "d" * 40})
    revoke_calls: list[tuple[str, str]] = []

    def defer_revocation(project_id: str, task_id: str) -> bool:
        revoke_calls.append((project_id, task_id))
        return False

    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
        revoke_delivery_authority=defer_revocation,
    )
    issue = _issue(DONE)

    result = coordinator.request_transition_sync(
        issue,
        TargetState.ARCHIVED,
        ContributorIdentity("oompah", "auto_archive"),
        PROJECT_ID,
        _fingerprint(),
    )

    assert result.success is False
    assert result.reason == "delivery_mutation_in_progress"
    assert revoke_calls == [(PROJECT_ID, TASK_ID)]
    assert tracker.get_metadata(TASK_ID) == {}
    assert tracker.update_calls == []


@pytest.mark.parametrize(
    ("record_state", "current_state"),
    [
        (RequestState.PENDING, IN_VALIDATION),
        (RequestState.COMPLETED, NEEDS_HUMAN),
    ],
)
def test_aged_done_auto_archive_legacy_record_uses_persisted_state_for_binding(
    record_state: RequestState,
    current_state: str,
) -> None:
    """Late binding survives staging/restart without trusting current status."""
    tracker = _MemoryTracker()
    sha = "d" * 40
    project_store = _RevisionLockStore({"origin/main": sha})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    fingerprint = _fingerprint()
    _seed_metadata(
        tracker,
        [
            TerminalAuditRecord(
                audit_id="audit-legacy-retention",
                project_id=PROJECT_ID,
                task_id=TASK_ID,
                target_state=TargetState.ARCHIVED,
                evidence_fingerprint=fingerprint,
                request_state=record_state,
                previous_state=DONE,
                requested_by=ContributorIdentity("oompah", "auto_archive"),
                created_at="2026-07-01T00:00:00+00:00",
            )
        ],
    )

    binding = coordinator._request_revision_binding(
        TerminalAuditMetadataStore(tracker, project_store, PROJECT_ID),
        _issue(current_state),
        TargetState.ARCHIVED,
        PROJECT_ID,
        fingerprint,
        trigger_identity=ContributorIdentity("project-owner", "api"),
    )

    assert binding is not None
    assert binding.selected_ref == "origin/main"
    assert binding.selected_sha == sha
    assert project_store.resolve_calls == ["origin/main"]


@pytest.mark.parametrize(
    ("record_state", "current_state"),
    [
        (RequestState.PENDING, IN_VALIDATION),
        (RequestState.COMPLETED, NEEDS_HUMAN),
    ],
)
@pytest.mark.parametrize(
    "provenance",
    [
        ContributorIdentity("project-owner", "api"),
        ContributorIdentity("oompah", "stalled_task_watchdog"),
    ],
)
def test_legacy_done_archive_non_retention_provenance_cannot_bind_main(
    record_state: RequestState,
    current_state: str,
    provenance: ContributorIdentity,
) -> None:
    """Only persisted automatic-retention provenance can witness main."""
    tracker = _MemoryTracker()
    project_store = _RevisionLockStore({"origin/main": "d" * 40})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    fingerprint = _fingerprint()
    _seed_metadata(
        tracker,
        [
            TerminalAuditRecord(
                audit_id="audit-non-retention",
                project_id=PROJECT_ID,
                task_id=TASK_ID,
                target_state=TargetState.ARCHIVED,
                evidence_fingerprint=fingerprint,
                request_state=record_state,
                previous_state=DONE,
                requested_by=provenance,
                created_at="2026-07-01T00:00:00+00:00",
            )
        ],
    )

    with pytest.raises(ValueError, match="no permitted revision"):
        coordinator._request_revision_binding(
            TerminalAuditMetadataStore(tracker, project_store, PROJECT_ID),
            _issue(current_state),
            TargetState.ARCHIVED,
            PROJECT_ID,
            fingerprint,
            trigger_identity=ContributorIdentity("project-owner", "api"),
        )

    assert project_store.resolve_calls == []


def test_completed_canonical_epic_rebinds_when_branch_advances() -> None:
    """A stable v1 fingerprint cannot make an old completed branch current."""

    tracker = _MemoryTracker()
    branch = "origin/epic-OOMPAH-768"
    old_sha = "a" * 40
    current_sha = "b" * 40
    project_store = _RevisionLockStore({branch: current_sha})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    issue = Issue(
        id="OOMPAH-768",
        identifier="OOMPAH-768",
        title="Systemic workflow epic",
        description="Complete the workflow program.",
        state="In Progress",
        issue_type="epic",
        project_id=PROJECT_ID,
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
    completed = TerminalAuditRecord(
        audit_id="audit-epic-completed-a",
        project_id=PROJECT_ID,
        task_id=issue.identifier,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        selected_ref=branch,
        selected_sha=old_sha,
        created_at="2026-07-01T00:00:00+00:00",
    )
    _seed_metadata(tracker, [completed], task_id=issue.identifier)

    result = _run(
        coordinator.request_transition(
            issue,
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            fingerprint,
        )
    )
    records = TerminalAuditMetadataStore(
        tracker,
        project_store,
        PROJECT_ID,
    ).read(issue.identifier).pending_chain
    by_id = {record.audit_id: record for record in records}
    fresh = next(record for record in records if record.audit_id != completed.audit_id)

    assert result.success is True
    assert result.coalesced is False
    assert result.superseded_audit_id == completed.audit_id
    assert by_id[completed.audit_id].request_state is RequestState.SUPERSEDED
    assert fresh.request_state is RequestState.PENDING
    assert fresh.evidence_fingerprint == fingerprint
    assert fresh.selected_ref == branch
    assert fresh.selected_sha == current_sha
    assert project_store.resolve_calls == [branch]


def test_advanced_completion_authority_replaces_same_head_epic_audits() -> None:
    """A newer protected completion decision cannot reuse an old failure."""

    sha = "b" * 40
    issue = Issue(
        id="OOMPAH-940",
        identifier="OOMPAH-940",
        title="Systemic workflow epic",
        description="Complete the workflow program.",
        state="In Progress",
        issue_type="epic",
        project_id=PROJECT_ID,
    )
    tracker = _RefreshingTracker(issue)
    project_store = _RevisionLockStore({sha: sha})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
    old_records = [
        TerminalAuditRecord(
            audit_id=f"audit-old-{target.value.lower()}",
            project_id=PROJECT_ID,
            task_id=issue.identifier,
            target_state=target,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.COMPLETED,
            selected_ref=sha,
            selected_sha=sha,
            workflow_revision="completion-authority-v1",
            created_at="2026-08-09T00:00:00+00:00",
        )
        for target in (TargetState.DONE, TargetState.MERGED)
    ]
    _seed_metadata(tracker, old_records, task_id=issue.identifier)

    result = _run(
        coordinator.request_transition(
            issue,
            TargetState.MERGED,
            ContributorIdentity("oompah", "orchestrator"),
            PROJECT_ID,
            fingerprint,
            mutation_guard=lambda: None,
            revision_binding=AuditRevisionBinding(sha, sha),
            workflow_revision="completion-authority-v2",
        )
    )
    records = TerminalAuditMetadataStore(
        tracker,
        project_store,
        PROJECT_ID,
    ).read(issue.identifier).pending_chain

    assert result.success and not result.coalesced
    assert result.queued_targets == [TargetState.DONE, TargetState.MERGED]
    assert all(
        record.request_state is RequestState.SUPERSEDED
        for record in records[:2]
    )
    fresh = records[2:]
    assert [record.target_state for record in fresh] == [
        TargetState.DONE,
        TargetState.MERGED,
    ]
    assert all(
        record.workflow_revision == "completion-authority-v2"
        for record in fresh
    )
    assert all(record.selected_sha == sha for record in fresh)


def test_completed_immutable_revision_idempotency_skips_repo_resolution() -> None:
    """Current immutable evidence can acknowledge its exact completed audit."""

    tracker = _MemoryTracker()
    sha = "c" * 40
    project_store = _RevisionLockStore({})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Immutable task",
        state="In Progress",
        project_id=PROJECT_ID,
    )
    issue.source_sha = sha
    fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
    completed = TerminalAuditRecord(
        audit_id="audit-immutable-completed",
        project_id=PROJECT_ID,
        task_id=TASK_ID,
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        selected_ref=sha,
        selected_sha=sha,
        created_at="2026-07-01T00:00:00+00:00",
    )
    _seed_metadata(tracker, [completed])

    result = _run(
        coordinator.request_transition(
            issue,
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            fingerprint,
        )
    )

    assert result.success is False
    assert result.reason == "already completed"
    assert result.audit_id == completed.audit_id
    assert project_store.resolve_calls == []


def test_request_fails_before_status_write_for_invalid_immutable_evidence() -> None:
    tracker = _MemoryTracker()
    project_store = _RevisionLockStore({})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    issue = Issue(
        id=TASK_ID,
        identifier=TASK_ID,
        title="Task",
        state="Ready to Integrate",
        project_id=PROJECT_ID,
    )
    issue.source_sha = "abbreviated"

    result = _run(
        coordinator.request_transition(
            issue,
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            _fingerprint(),
        )
    )

    assert result.success is False
    assert "full Git object ID" in str(result.reason)
    assert tracker.update_calls == []
    assert tracker.get_metadata(issue.identifier) == {}


# ---------------------------------------------------------------------------
# TestDoneChain
# ---------------------------------------------------------------------------


def test_request_mutation_guard_runs_inside_project_lock_before_staging() -> None:
    tracker = _MemoryTracker()
    store = _LockStore()
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=store,
        post_comments=False,
    )
    lock = store.project_write_lock(PROJECT_ID)

    def guard():
        assert lock._is_owned()  # type: ignore[attr-defined]
        return "child containment changed"

    result = _run(
        coordinator.request_transition(
            _issue(),
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            _fingerprint(),
            mutation_guard=guard,
        )
    )

    assert result.success is False
    assert result.reason == (
        "workflow_precondition_changed: child containment changed"
    )
    assert tracker.update_calls == []
    assert tracker.get_metadata(TASK_ID) == {}


class TestDoneChain:
    def test_staging_rejects_stale_tracker_snapshot_at_project_fence(self) -> None:
        class DetailTracker(_MemoryTracker):
            def __init__(self, current: Issue) -> None:
                super().__init__()
                self.current = current

            def fetch_issue_detail(self, identifier: str) -> Issue | None:
                return copy.copy(self.current) if identifier == TASK_ID else None

        supplied = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Test task",
            description="old requirements",
            state="In Progress",
            project_id=PROJECT_ID,
        )
        tracker = DetailTracker(replace(supplied, description="new requirements"))
        coordinator = _coordinator(tracker)

        result = _run(
            coordinator.request_transition(
                supplied,
                TargetState.DONE,
                _trigger(),
                PROJECT_ID,
                compute_issue_evidence_fingerprint(supplied, PROJECT_ID),
            )
        )

        assert result.success is False
        assert result.reason == ResultRejection.CURRENT_EVIDENCE_MISMATCH
        assert tracker.get_metadata(TASK_ID) == {}
        assert tracker.update_calls == []

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
    @staticmethod
    def _request_bound_merged_after_done(
        done: TerminalAuditRecord,
    ) -> tuple[TransitionResult, list[TerminalAuditRecord]]:
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [done])
        project_store = _RevisionLockStore({"origin/main": "b" * 40})
        coordinator = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=project_store,
            post_comments=False,
        )

        result = _run(
            coordinator.request_transition(
                _issue(),
                TargetState.MERGED,
                _trigger(),
                PROJECT_ID,
                _fingerprint(),
            )
        )
        records = TerminalAuditMetadataStore(
            tracker,
            project_store,
            PROJECT_ID,
        ).read(TASK_ID).pending_chain
        return result, records

    @staticmethod
    def _assert_rebound_merged_chain(
        old_done: TerminalAuditRecord,
        result: TransitionResult,
        records: list[TerminalAuditRecord],
    ) -> None:
        retired = next(
            record for record in records if record.audit_id == old_done.audit_id
        )
        assert retired.request_state == RequestState.SUPERSEDED
        live = [
            record
            for record in records
            if record.request_state in (RequestState.PENDING, RequestState.IN_PROGRESS)
        ]
        assert result.queued_targets == [TargetState.DONE, TargetState.MERGED]
        assert [record.target_state for record in live] == [
            TargetState.DONE,
            TargetState.MERGED,
        ]
        assert all(record.selected_ref == "origin/main" for record in live)
        assert all(record.selected_sha == "b" * 40 for record in live)

    def test_bound_merged_reaudits_completed_done_from_another_sha(self) -> None:
        old_done = replace(
            _completed_done_record(),
            selected_ref="origin/main",
            selected_sha="a" * 40,
        )

        result, records = self._request_bound_merged_after_done(old_done)

        self._assert_rebound_merged_chain(old_done, result, records)

    def test_bound_merged_reaudits_active_done_from_another_sha(self) -> None:
        old_done = replace(
            _pending_done_record(),
            request_state=RequestState.IN_PROGRESS,
            selected_ref="origin/main",
            selected_sha="a" * 40,
        )

        result, records = self._request_bound_merged_after_done(old_done)

        self._assert_rebound_merged_chain(old_done, result, records)

    def test_bound_merged_reaudits_legacy_unbound_done(self) -> None:
        old_done = _pending_done_record()

        result, records = self._request_bound_merged_after_done(old_done)

        self._assert_rebound_merged_chain(old_done, result, records)

    def test_duplicate_merged_rows_select_exact_done_binding_and_retire_old(self) -> None:
        tracker = _MemoryTracker()
        binding_a = ("origin/main", "a" * 40)
        binding_b = ("origin/main", "b" * 40)
        done_b = replace(
            _completed_done_record(),
            selected_ref=binding_b[0],
            selected_sha=binding_b[1],
        )
        merged_a = TerminalAuditRecord(
            audit_id="audit-merged-a",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.MERGED,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.COMPLETED,
            selected_ref=binding_a[0],
            selected_sha=binding_a[1],
        )
        merged_b = replace(
            merged_a,
            audit_id="audit-merged-b",
            request_state=RequestState.PENDING,
            selected_ref=binding_b[0],
            selected_sha=binding_b[1],
        )
        document = TerminalAuditMetadata(
            pending_chain=[done_b, merged_a, merged_b],
            unknown_fields={
                "oompah.terminal_audit_retirements": [
                    {
                        "version": 1,
                        "project_id": PROJECT_ID,
                        "task_id": TASK_ID,
                        "target_state": TargetState.MERGED.value,
                        "evidence_fingerprint": _fingerprint().digest,
                        "audit_ids": [merged_a.audit_id],
                        "kind": "result",
                        "applied": True,
                    }
                ]
            },
        )
        tracker.set_metadata_field(TASK_ID, METADATA_KEY, document.to_dict())
        project_store = _RevisionLockStore({})
        coordinator = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=project_store,
            post_comments=False,
        )

        result = _run(
            coordinator.request_transition(
                _issue(),
                TargetState.MERGED,
                _trigger(),
                PROJECT_ID,
                _fingerprint(),
            )
        )
        records = TerminalAuditMetadataStore(
            tracker,
            project_store,
            PROJECT_ID,
        ).read(TASK_ID).pending_chain
        by_id = {record.audit_id: record for record in records}

        assert result.success is True
        assert result.coalesced is True
        assert result.audit_id == merged_b.audit_id
        assert by_id[done_b.audit_id].request_state is RequestState.COMPLETED
        assert by_id[merged_a.audit_id].request_state is RequestState.SUPERSEDED
        assert by_id[merged_b.audit_id].request_state is RequestState.PENDING
        assert by_id[merged_b.audit_id].selected_sha == binding_b[1]
        assert project_store.resolve_calls == []

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
        done, merged = doc.pending_chain
        assert done.eligible_at == done.created_at
        assert done.prerequisite_audit_id is None
        assert merged.eligible_at is None
        assert merged.prerequisite_audit_id == done.audit_id

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
            request_state=RequestState.IN_PROGRESS,
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
            request_state=RequestState.PENDING,
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

    def test_repaired_done_retires_stale_merged_successor(self) -> None:
        """A failed direct-Merged chain cannot hide repaired Done evidence."""

        tracker = _MemoryTracker()
        coord = _coordinator(tracker, post_comments=False)
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        initial = _run(
            coord.request_transition(
                _issue(),
                TargetState.MERGED,
                _trigger(),
                PROJECT_ID,
                _fingerprint("a"),
            )
        )
        initial_done_id, initial_merged_id = initial.audit_ids

        def _fail_initial_done(doc: TerminalAuditMetadata) -> TerminalAuditMetadata:
            return replace(
                doc,
                pending_chain=[
                    replace(
                        record,
                        request_state=RequestState.COMPLETED,
                        attempts=[
                            AuditAttempt(
                                attempt_id="attempt-failed-initial-done",
                                target_state=TargetState.DONE,
                                evidence_fingerprint=record.evidence_fingerprint,
                                request_state=RequestState.COMPLETED,
                                verdict=Verdict.FAIL,
                            )
                        ],
                    )
                    if record.audit_id == initial_done_id
                    else record
                    for record in doc.pending_chain
                ],
            )

        store.update(TASK_ID, _fail_initial_done)

        repaired = _run(
            coord.request_transition(
                _issue(state="Open"),
                TargetState.DONE,
                _trigger(),
                PROJECT_ID,
                _fingerprint("b"),
            )
        )

        assert repaired.success
        assert initial_merged_id in repaired.superseded_audit_ids
        chain = store.read(TASK_ID).pending_chain
        stale_merged = next(
            record for record in chain if record.audit_id == initial_merged_id
        )
        assert stale_merged.request_state is RequestState.SUPERSEDED
        active = [
            record
            for record in chain
            if record.request_state in (RequestState.PENDING, RequestState.IN_PROGRESS)
        ]
        assert len(active) == 1
        assert active[0].audit_id == repaired.audit_id
        assert active[0].target_state is TargetState.DONE
        assert AuditorDispatchLane.pending_record(
            chain,
            project_id=PROJECT_ID,
            task_id=TASK_ID,
        ) == active[0]


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

    def test_maintenance_rebinds_changed_evidence_after_completed_archive(
        self,
    ) -> None:
        """Completed evidence cannot donate its revision to a new request."""

        tracker = _MemoryTracker()
        old = TerminalAuditRecord(
            audit_id="audit-archive-e1",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.ARCHIVED,
            evidence_fingerprint=_fingerprint("a"),
            request_state=RequestState.COMPLETED,
            previous_state=DONE,
            selected_ref="origin/archive-a",
            selected_sha="a" * 40,
            created_at="2026-07-01T00:00:00+00:00",
        )
        _seed_metadata(tracker, [old])
        project_store = _RevisionLockStore({"origin/archive-b": "b" * 40})
        coordinator = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=project_store,
            post_comments=False,
        )
        issue = _issue(DONE)
        issue.branch_name = "archive-b"

        result = coordinator.request_transition_sync(
            issue,
            TargetState.ARCHIVED,
            _trigger(),
            PROJECT_ID,
            _fingerprint("b"),
            coalesce_pending_target=True,
        )
        records = TerminalAuditMetadataStore(
            tracker,
            project_store,
            PROJECT_ID,
        ).read(TASK_ID).pending_chain
        by_id = {record.audit_id: record for record in records}
        fresh = next(record for record in records if record.audit_id != old.audit_id)

        assert result.success is True
        assert result.coalesced is False
        assert result.superseded_audit_id == old.audit_id
        assert by_id[old.audit_id].request_state is RequestState.SUPERSEDED
        assert fresh.evidence_fingerprint == _fingerprint("b")
        assert fresh.request_state is RequestState.PENDING
        assert fresh.selected_ref == "origin/archive-b"
        assert fresh.selected_sha == "b" * 40
        assert project_store.resolve_calls == ["origin/archive-b"]

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

    def test_active_attempt_outranks_ownerless_in_progress_sibling(self) -> None:
        """OOMPAH-824: coalescing preserves the PASS-producing authority."""

        tracker = _MemoryTracker()
        fingerprint = _fingerprint()
        pending = TerminalAuditRecord(
            audit_id="audit-6b3fa26bb2f6",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.IN_PROGRESS,
            created_at="2026-08-05T12:00:00+00:00",
        )
        running = TerminalAuditRecord(
            audit_id="audit-11ec4964b81b",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-pass-producing",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=fingerprint,
                    request_state=RequestState.IN_PROGRESS,
                    provider_id="provider-a",
                    model="model-a",
                    created_at="2026-08-05T12:04:00+00:00",
                    started_at="2026-08-05T12:04:00+00:00",
                )
            ],
            created_at="2026-08-05T12:01:00+00:00",
            updated_at="2026-08-05T12:04:00+00:00",
        )
        _seed_metadata(tracker, [pending, running])
        coord = _coordinator(tracker, post_comments=False)

        result = _run(
            coord.request_transition(
                _issue(IN_VALIDATION),
                TargetState.DONE,
                ContributorIdentity("review-reconcile", "oompah"),
                PROJECT_ID,
                fingerprint,
            )
        )

        assert result.success and result.coalesced
        assert result.audit_id == running.audit_id
        assert result.cancelled_audit_ids == [pending.audit_id]
        records = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain
        by_id = {record.audit_id: record for record in records}
        assert by_id[running.audit_id].request_state is RequestState.PENDING
        assert by_id[pending.audit_id].request_state is RequestState.SUPERSEDED


# ---------------------------------------------------------------------------
# TestSuperseding
# ---------------------------------------------------------------------------


class TestSuperseding:
    def test_changed_fingerprint_does_not_supersede_foreign_project_record(
        self,
    ) -> None:
        tracker = _MemoryTracker()
        local = _pending_record(
            audit_id="audit-local",
            fingerprint=_fingerprint("a"),
        )
        foreign = _pending_record(
            audit_id="audit-foreign",
            fingerprint=_fingerprint("a"),
            project_id="project-foreign",
        )
        _seed_metadata(tracker, [foreign, local])

        result = _run(
            _coordinator(tracker, post_comments=False).request_transition(
                _issue(state=IN_VALIDATION),
                TargetState.DONE,
                _trigger(),
                PROJECT_ID,
                _fingerprint("b"),
            )
        )

        assert result.success is True
        records = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain
        by_id = {record.audit_id: record for record in records}
        assert by_id["audit-local"].request_state is RequestState.SUPERSEDED
        assert by_id["audit-foreign"].request_state is RequestState.PENDING

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
    @staticmethod
    def _owner_project():
        return SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

    def test_owner_override_persists_exact_revision_binding(self) -> None:
        head = "7" * 40
        issue = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Direct owner delivery",
            state="In Progress",
            project_id=PROJECT_ID,
            work_branch=TASK_ID,
            target_branch="main",
            integration=IntegrationRecord(
                state="ready",
                task_branch=TASK_ID,
                base_branch="main",
                head_sha=head,
            ),
        )
        tracker = _RefreshingTracker(issue)
        project_store = _RevisionLockStore({head: head})
        coordinator = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=project_store,
            post_comments=False,
        )
        fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)

        result = _run(
            coordinator.override_transition(
                issue,
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                fingerprint,
                "The exact accepted revision was delivered to main.",
                self._owner_project(),
            )
        )

        assert result.success is True
        document = TerminalAuditMetadataStore(
            tracker, project_store, PROJECT_ID
        ).read(TASK_ID)
        raw = document.unknown_fields["oompah.terminal_override_records"][0]
        assert raw["selected_ref"] == head
        assert raw["selected_sha"] == head
        assert raw["applied"] is True

    def test_reopened_epic_ignores_historical_completed_done_evidence(self) -> None:
        historical = Issue(
            id="OOMPAH-588",
            identifier="OOMPAH-588",
            title="Finish safe repository hygiene and maintenance correctness",
            description="Complete repository hygiene maintenance.",
            state=DONE,
            issue_type="epic",
            parent_id="OOMPAH-584",
            project_id=PROJECT_ID,
            work_branch="OOMPAH-588",
        )
        current = replace(
            historical,
            state="In Progress",
            work_branch="epic-OOMPAH-588",
            target_branch="epic-OOMPAH-584",
            review_url="https://github.com/lesserevil/oompah/pull/602",
            review_number="602",
        )
        historical_fingerprint = compute_issue_evidence_fingerprint(
            historical, PROJECT_ID
        )
        current_fingerprint = compute_issue_evidence_fingerprint(
            current, PROJECT_ID
        )
        assert historical_fingerprint != current_fingerprint
        completed = TerminalAuditRecord(
            audit_id="audit-historical-done-oompah-588",
            project_id=PROJECT_ID,
            task_id=current.identifier,
            target_state=TargetState.DONE,
            evidence_fingerprint=historical_fingerprint,
            request_state=RequestState.COMPLETED,
        )
        tracker = _RefreshingTracker(current)
        _seed_metadata(tracker, [completed], task_id=current.identifier)
        coordinator = _coordinator(tracker, post_comments=False)

        first = _run(
            coordinator.override_transition(
                current,
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                current_fingerprint,
                "Restore the landed historical epic to terminal Done.",
                self._owner_project(),
            )
        )
        replay = _run(
            coordinator.override_transition(
                tracker.fetch_issue_detail(current.identifier),
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                current_fingerprint,
                "Restore the landed historical epic to terminal Done.",
                self._owner_project(),
            )
        )

        assert first.success is True
        assert replay.success is True
        assert replay.idempotent is True
        assert replay.override_id == first.override_id
        assert tracker.current_status(current.identifier) == DONE
        metadata = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(current.identifier)
        override = metadata.unknown_fields["oompah.terminal_override_records"][0]
        assert override["evidence_fingerprint"] == current_fingerprint.to_dict()

    def test_legacy_done_override_accepts_exact_integrated_oompah_660_generation(
        self,
    ) -> None:
        issue = _oompah_660_override_issue()
        variants = compute_integrated_evidence_fingerprint_variants(
            issue, PROJECT_ID
        )
        assert variants is not None
        active = TerminalAuditRecord(
            audit_id="audit-legacy-done-oompah-660",
            project_id=PROJECT_ID,
            task_id=issue.identifier,
            target_state=TargetState.DONE,
            evidence_fingerprint=variants.legacy_work_branch,
            request_state=RequestState.PENDING,
        )
        tracker = _RefreshingTracker(issue)
        _seed_metadata(tracker, [active], task_id=issue.identifier)

        result = _run(
            _coordinator(tracker, post_comments=False).override_transition(
                issue,
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                variants.integrated,
                "Repair the exact accepted Done-only integration generation.",
                self._owner_project(),
            )
        )

        assert result.success is True
        assert tracker.current_status(issue.identifier) == DONE
        metadata = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(issue.identifier)
        override = metadata.unknown_fields["oompah.terminal_override_records"][0]
        assert override["evidence_fingerprint"] == variants.integrated.to_dict()
        assert override["applied"] is True

    def test_current_match_done_override_control_remains_accepted(self) -> None:
        issue = _oompah_660_override_issue()
        variants = compute_integrated_evidence_fingerprint_variants(
            issue, PROJECT_ID
        )
        assert variants is not None
        active = TerminalAuditRecord(
            audit_id="audit-current-done-control",
            project_id=PROJECT_ID,
            task_id=issue.identifier,
            target_state=TargetState.DONE,
            evidence_fingerprint=variants.integrated,
            request_state=RequestState.PENDING,
        )
        tracker = _RefreshingTracker(issue)
        _seed_metadata(tracker, [active], task_id=issue.identifier)

        result = _run(
            _coordinator(tracker, post_comments=False).override_transition(
                issue,
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                variants.integrated,
                "Apply the current exact Done generation.",
                self._owner_project(),
            )
        )

        assert result.success is True
        assert tracker.current_status(issue.identifier) == DONE

    @pytest.mark.parametrize(
        "mutation",
        [
            "integrated_sha",
            "ordinary_task",
            "ci_fix",
            "merge_conflict",
            "arbitrary_fingerprint",
        ],
    )
    def test_legacy_done_override_generation_drift_fails_closed(
        self, mutation
    ) -> None:
        issue = _oompah_660_override_issue()
        variants = compute_integrated_evidence_fingerprint_variants(
            issue, PROJECT_ID
        )
        assert variants is not None
        historical = variants.legacy_work_branch
        if mutation == "integrated_sha":
            issue.integration = replace(issue.integration, integrated_sha="f" * 40)
        elif mutation == "ordinary_task":
            issue.title = "Implement an ordinary feature"
        elif mutation == "ci_fix":
            issue.labels = ["ci-fix"]
        elif mutation == "merge_conflict":
            issue.labels = ["merge-conflict"]
        elif mutation == "arbitrary_fingerprint":
            historical = EvidenceFingerprint("0" * 64)
        current = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
        active = TerminalAuditRecord(
            audit_id=f"audit-stale-{mutation}",
            project_id=PROJECT_ID,
            task_id=issue.identifier,
            target_state=TargetState.DONE,
            evidence_fingerprint=historical,
            request_state=RequestState.PENDING,
        )
        tracker = _RefreshingTracker(issue)
        _seed_metadata(tracker, [active], task_id=issue.identifier)

        result = _run(
            _coordinator(tracker, post_comments=False).override_transition(
                issue,
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                current,
                "This stale generation must remain rejected.",
                self._owner_project(),
            )
        )

        assert result.success is False
        assert result.error_code == OverrideRejection.FINGERPRINT_MISMATCH
        assert tracker.current_status(issue.identifier) is None

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

    def test_successful_override_clears_integrated_task_alert(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_done_record()
        _seed_metadata(tracker, [record])
        cleared: list[tuple[str, str]] = []
        coordinator = _coordinator(
            tracker,
            post_comments=False,
            clear_integrated_audit_recovery_alert=lambda project, task: cleared.append(
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
                "Owner approved this terminal transition.",
                project,
            )
        )

        assert result.success is True
        assert cleared == [(PROJECT_ID, TASK_ID)]

    def test_override_retires_all_duplicate_rows_and_replays_idempotently(self) -> None:
        tracker = _MemoryTracker()
        metrics = _MetricsRecorder()
        fingerprint = _fingerprint()
        sha = "a" * 40
        first = replace(
            _pending_record(audit_id="audit-override-1", fingerprint=fingerprint),
            selected_ref=sha,
            selected_sha=sha,
            workflow_revision="workflow-revision-v1",
        )
        second = replace(
            _pending_record(audit_id="audit-override-2", fingerprint=fingerprint),
            selected_ref=sha,
            selected_sha=sha,
            workflow_revision="workflow-revision-v1",
        )
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
        assert raw_override["workflow_revision"] == "workflow-revision-v1"
        assert raw_override["selected_sha"] == sha
        retirement = stored.unknown_fields["oompah.terminal_audit_retirements"][0]
        assert retirement["evidence_fingerprint"] == fingerprint.digest
        assert retirement["workflow_revision"] == "workflow-revision-v1"
        assert retirement["selected_sha"] == sha
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

    def test_old_override_does_not_mask_live_new_workflow_revision(self) -> None:
        tracker = _MemoryTracker()
        fingerprint = _fingerprint()
        live = replace(
            _pending_record(audit_id="audit-live-v2", fingerprint=fingerprint),
            workflow_revision="workflow-revision-v2",
        )
        old_override = {
            "version": 1,
            "override_id": "override-v1",
            "project_id": PROJECT_ID,
            "task_id": TASK_ID,
            "target_state": TargetState.DONE.value,
            "evidence_fingerprint": fingerprint.to_dict(),
            "authorized_by": ContributorIdentity(
                "project-owner", "github"
            ).to_dict(),
            "reason": "Earlier owner decision.",
            "workflow_revision": "workflow-revision-v1",
            "applied": True,
        }
        document = TerminalAuditMetadata(
            pending_chain=[live],
            unknown_fields={
                "oompah.terminal_override_records": [old_override],
            },
        )
        tracker.set_metadata_field(TASK_ID, METADATA_KEY, document.to_dict())
        coordinator = _coordinator(tracker, post_comments=False)
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
                "Owner approved the new workflow generation.",
                project,
            )
        )

        assert result.success and not result.idempotent
        assert result.override_id != "override-v1"
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        overrides = stored.unknown_fields[
            "oompah.terminal_override_records"
        ]
        assert len(overrides) == 2
        assert overrides[-1]["workflow_revision"] == "workflow-revision-v2"
        assert stored.pending_chain[0].request_state is RequestState.CANCELLED

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

    def test_legacy_override_replay_requires_fresh_owner_authority(self) -> None:
        tracker = _MemoryTracker()
        fingerprint = _fingerprint()
        legacy = OverrideRecord(
            override_id="override-before-replay-markers",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            authorized_by=ContributorIdentity("project-owner", "github"),
            reason="Owner approved before replay markers existed.",
        ).to_dict()
        assert "applied" not in legacy
        tracker.set_metadata_field(
            TASK_ID,
            METADATA_KEY,
            TerminalAuditMetadata(
                unknown_fields={
                    "oompah.terminal_override_records": [legacy],
                },
            ).to_dict(),
        )
        tracker.update_issue(TASK_ID, status="Open")
        tracker.update_calls.clear()
        coordinator = _coordinator(tracker, post_comments=False)
        project = SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

        unauthorized = _run(
            coordinator.override_transition(
                _issue("Open"),
                TargetState.DONE,
                ContributorIdentity("not-owner", "github"),
                PROJECT_ID,
                fingerprint,
                "Attempt to reuse owner history.",
                project,
            )
        )

        assert unauthorized.success is False
        assert unauthorized.error_code is OverrideRejection.UNAUTHORIZED_ACTOR
        assert tracker.current_status(TASK_ID) == "Open"
        assert tracker.update_calls == []

        replay = _run(
            coordinator.override_transition(
                _issue("Open"),
                TargetState.DONE,
                ContributorIdentity("project-owner", "github"),
                PROJECT_ID,
                fingerprint,
                "Owner reaffirms the exact historical decision.",
                project,
            )
        )

        assert replay.success is True
        assert replay.idempotent is True
        assert replay.override_id == legacy["override_id"]
        assert tracker.current_status(TASK_ID) == DONE
        assert tracker.update_calls == [(TASK_ID, {"status": DONE})]

    def test_retired_override_requires_a_fresh_authority_record(self) -> None:
        tracker = _MemoryTracker()
        fingerprint = _fingerprint()
        retired = OverrideRecord(
            override_id="override-retired",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            authorized_by=ContributorIdentity("former-owner", "github"),
            reason="Historical authority that was later retired.",
        ).to_dict()
        retired.update(
            {
                "applied": True,
                "retired_at": "2026-08-01T00:00:00+00:00",
                "retired_reason": "evidence_mismatch",
            }
        )
        tracker.set_metadata_field(
            TASK_ID,
            METADATA_KEY,
            TerminalAuditMetadata(
                unknown_fields={
                    "oompah.terminal_override_records": [retired],
                },
            ).to_dict(),
        )
        tracker.update_issue(TASK_ID, status="Open")
        tracker.update_calls.clear()
        coordinator = _coordinator(tracker, post_comments=False)
        owner = ContributorIdentity("project-owner", "github")
        project = SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

        result = _run(
            coordinator.override_transition(
                _issue("Open"),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                fingerprint,
                "Current owner makes a fresh terminal decision.",
                project,
            )
        )

        assert result.success is True
        assert result.idempotent is False
        assert result.override_id != retired["override_id"]
        assert tracker.current_status(TASK_ID) == DONE
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        overrides = stored.unknown_fields["oompah.terminal_override_records"]
        assert len(overrides) == 2
        assert overrides[0] == retired
        assert overrides[1]["authorized_by"] == owner.to_dict()
        assert overrides[1]["reason"] == "Current owner makes a fresh terminal decision."
        assert overrides[1]["applied"] is True

    def test_unapplied_override_blocks_a_newer_owner_decision_until_recovery(
        self,
    ) -> None:
        tracker = _MemoryTracker()
        fingerprint = _fingerprint()
        unfinished = OverrideRecord(
            override_id="override-unfinished-archive",
            project_id=PROJECT_ID,
            task_id=TASK_ID,
            target_state=TargetState.ARCHIVED,
            evidence_fingerprint=fingerprint,
            authorized_by=ContributorIdentity("project-owner", "github"),
            reason="Archive transaction interrupted before finalization.",
        ).to_dict()
        unfinished["applied"] = False
        original = TerminalAuditMetadata(
            unknown_fields={
                "oompah.terminal_override_records": [unfinished],
            },
        ).to_dict()
        tracker.set_metadata_field(TASK_ID, METADATA_KEY, original)
        tracker.update_issue(TASK_ID, status="Open")
        tracker.update_calls.clear()
        coordinator = _coordinator(tracker, post_comments=False)
        project = SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

        result = _run(
            coordinator.override_transition(
                _issue("Open"),
                TargetState.DONE,
                ContributorIdentity("project-owner", "github"),
                PROJECT_ID,
                fingerprint,
                "Newer decision must wait for ordered recovery.",
                project,
            )
        )

        assert result.success is False
        assert result.error_code is OverrideRejection.FINALIZATION_PENDING
        assert tracker.current_status(TASK_ID) == "Open"
        assert tracker.update_calls == []
        assert tracker.get_metadata(TASK_ID)[METADATA_KEY] == original

    @pytest.mark.parametrize(
        "malformed_kind",
        [
            "partial",
            "applied_non_boolean",
            "lifecycle_non_boolean",
            "matching_then_malformed",
        ],
    )
    def test_malformed_override_ledger_cannot_authorize_idempotent_repair(
        self,
        malformed_kind: str,
    ) -> None:
        tracker = _MemoryTracker()
        fingerprint = _fingerprint()
        if malformed_kind == "partial":
            malformed: dict[str, Any] = {
                "project_id": PROJECT_ID,
                "task_id": TASK_ID,
                "target_state": TargetState.DONE.value,
                "evidence_fingerprint": fingerprint.to_dict(),
            }
        else:
            malformed = OverrideRecord(
                override_id="override-invalid-marker",
                project_id=PROJECT_ID,
                task_id=TASK_ID,
                target_state=TargetState.DONE,
                evidence_fingerprint=fingerprint,
                authorized_by=ContributorIdentity("project-owner", "github"),
                reason="Structurally valid except for its replay marker.",
            ).to_dict()
            if malformed_kind == "applied_non_boolean":
                malformed["applied"] = "true"
            elif malformed_kind == "lifecycle_non_boolean":
                malformed["lifecycle_reconciled"] = 0
        override_rows = [malformed]
        if malformed_kind == "matching_then_malformed":
            matching = OverrideRecord(
                override_id="override-valid-matching-legacy",
                project_id=PROJECT_ID,
                task_id=TASK_ID,
                target_state=TargetState.DONE,
                evidence_fingerprint=fingerprint,
                authorized_by=ContributorIdentity("project-owner", "github"),
                reason="Valid matching row must not mask a malformed sibling.",
            ).to_dict()
            override_rows = [matching, {}]
        original = TerminalAuditMetadata(
            unknown_fields={
                "oompah.terminal_override_records": override_rows,
            },
        ).to_dict()
        tracker.set_metadata_field(TASK_ID, METADATA_KEY, original)
        tracker.update_issue(TASK_ID, status="Open")
        tracker.update_calls.clear()
        coordinator = _coordinator(tracker, post_comments=False)
        project = SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

        result = _run(
            coordinator.override_transition(
                _issue("Open"),
                TargetState.DONE,
                ContributorIdentity("project-owner", "github"),
                PROJECT_ID,
                fingerprint,
                "Owner requested a new terminal decision.",
                project,
            )
        )

        assert result.success is False
        assert result.error_code is OverrideRejection.METADATA_QUARANTINED
        assert tracker.current_status(TASK_ID) == "Open"
        assert tracker.update_calls == []
        assert tracker.get_metadata(TASK_ID)[METADATA_KEY] == original


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

    def test_stale_completed_binding_does_not_cancel_live_rebind(self) -> None:
        fingerprint = _fingerprint()
        workflow_revision = "workflow-revision-1"
        completed = replace(
            _pending_record(
                audit_id="audit-completed-a0",
                fingerprint=fingerprint,
                state=RequestState.COMPLETED,
            ),
            workflow_revision=workflow_revision,
            selected_ref="origin/old",
            selected_sha="a" * 40,
        )
        live = replace(
            _pending_record(
                audit_id="audit-live-a1",
                fingerprint=fingerprint,
            ),
            workflow_revision=workflow_revision,
            selected_ref="origin/new",
            selected_sha="b" * 40,
            source_generation=2,
        )
        tracker = _MemoryTracker()
        project_store = _RevisionLockStore(
            {"origin/old": "a" * 40, "origin/new": "b" * 40}
        )
        _seed_metadata(tracker, [completed, live])

        store = TerminalAuditMetadataStore(tracker, project_store, PROJECT_ID)
        result = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=project_store,
            post_comments=False,
        )._transition_locked(
            store,
            tracker,
            _issue(),
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            fingerprint,
            revision_binding=AuditRevisionBinding("origin/old", "a" * 40),
            workflow_revision=workflow_revision,
        )

        assert not result.success
        assert result.reason == "already completed"
        assert result.cancelled_audit_ids == []
        stored = store.read(TASK_ID)
        assert stored.pending_chain == [completed, live]

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
    AuditAttemptOrigin,
    FailureClassification,
    Verdict,
    compute_issue_evidence_fingerprint,
)
from oompah.terminal_transition_coordinator import (  # noqa: E402
    AuditResult,
    ResultOutcome,
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


class TestRetryFailedAudit:
    @staticmethod
    def _owner_project():
        return SimpleNamespace(
            tracker_owner="project-owner",
            status_actor_login=None,
            status_label_authorized_logins=["project-owner"],
        )

    @staticmethod
    def _failed_done_chain() -> tuple[TerminalAuditRecord, TerminalAuditRecord]:
        template = _exhausted_no_auditor_record()
        exhausted = replace(
            template,
            audit_id="audit-done-exhausted",
            target_state=TargetState.DONE,
            previous_state="In Progress",
            attempts=[
                replace(attempt, target_state=TargetState.DONE)
                for attempt in template.attempts
            ],
        )
        merged = replace(
            _pending_record(
                audit_id="audit-merged-successor",
                target=TargetState.MERGED,
                fingerprint=exhausted.evidence_fingerprint,
            ),
            prerequisite_audit_id=exhausted.audit_id,
            eligible_at=None,
            source_generation=exhausted.source_generation,
        )
        return exhausted, merged

    @pytest.mark.parametrize("legacy_prerequisite", [False, True])
    def test_done_rearm_rebinds_exact_merged_successor_and_converges(
        self,
        legacy_prerequisite: bool,
    ) -> None:
        tracker = _MemoryTracker()
        exhausted, merged = self._failed_done_chain()
        if legacy_prerequisite:
            merged = replace(merged, prerequisite_audit_id=None)
        _seed_metadata(tracker, [exhausted, merged])
        owner = ContributorIdentity("project-owner", "api")
        reason = "Independent auditor capacity was restored."
        coordinator = _coordinator(tracker, post_comments=False)

        first = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                reason,
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )
        restarted = _coordinator(tracker, post_comments=False)
        repeated = _run(
            restarted.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                reason,
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        rearmed = next(
            record
            for record in store.read(TASK_ID).pending_chain
            if record.audit_id == first.audit_id
        )
        rebound = next(
            record
            for record in store.read(TASK_ID).pending_chain
            if record.audit_id == merged.audit_id
        )
        assert first.success is True
        assert repeated.success is True and repeated.coalesced is True
        assert repeated.audit_id == rearmed.audit_id
        assert rebound.audit_id == merged.audit_id
        assert rebound.prerequisite_audit_id == rearmed.audit_id
        assert rebound.eligible_at is None
        assert AuditorDispatchLane.pending_record(
            store.read(TASK_ID).pending_chain,
            project_id=PROJECT_ID,
            task_id=TASK_ID,
        ) == rearmed

        outcome = _apply(
            restarted,
            _issue(IN_VALIDATION),
            _pass_result(rearmed),
        )
        converged = store.read(TASK_ID)
        eligible = next(
            record
            for record in converged.pending_chain
            if record.audit_id == merged.audit_id
        )
        assert outcome.success is True
        assert outcome.advanced_target is TargetState.MERGED
        assert outcome.advanced_audit_id == merged.audit_id
        assert outcome.applied_status == IN_VALIDATION
        assert eligible.prerequisite_audit_id == rearmed.audit_id
        assert eligible.eligible_at is not None
        assert AuditorDispatchLane.pending_record(
            converged.pending_chain,
            project_id=PROJECT_ID,
            task_id=TASK_ID,
        ) == eligible

    @pytest.mark.parametrize(
        "successor_case",
        [
            "ambiguous",
            "missing",
            "replaced",
            "stale",
            "started",
            "cross_authority",
        ],
    )
    def test_done_rearm_rejects_non_exact_successor(
        self,
        successor_case: str,
    ) -> None:
        tracker = _MemoryTracker()
        exhausted, merged = self._failed_done_chain()
        chain = [exhausted, merged]
        if successor_case == "ambiguous":
            chain.append(replace(merged, audit_id="audit-merged-duplicate"))
        elif successor_case == "missing":
            chain[1] = replace(
                merged,
                prerequisite_audit_id="audit-done-missing",
            )
        elif successor_case == "replaced":
            chain[1] = replace(
                merged,
                source_generation=merged.source_generation + 1,
            )
        elif successor_case == "stale":
            stale = replace(
                exhausted,
                audit_id="audit-done-stale",
                request_state=RequestState.SUPERSEDED,
            )
            chain = [
                stale,
                exhausted,
                replace(
                    merged,
                    prerequisite_audit_id=stale.audit_id,
                ),
            ]
        elif successor_case == "started":
            chain[1] = replace(
                merged,
                request_state=RequestState.IN_PROGRESS,
                attempts=[
                    AuditAttempt(
                        attempt_id="attempt-merged-started",
                        target_state=TargetState.MERGED,
                        evidence_fingerprint=merged.evidence_fingerprint,
                        request_state=RequestState.IN_PROGRESS,
                    )
                ],
            )
        else:
            chain[1] = replace(
                merged,
                workflow_revision="other-completion-authority",
            )
        _seed_metadata(tracker, chain)

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Retry the failed prerequisite.",
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        assert result.success is False
        assert result.reason == "audit_not_retryable"
        assert TerminalAuditMetadataStore(
            tracker,
            _LockStore(),
            PROJECT_ID,
        ).read(TASK_ID).pending_chain == chain
        assert tracker.update_calls == []

    def test_restarted_rearm_rejects_tampered_successor_without_duplicate(self) -> None:
        tracker = _MemoryTracker()
        exhausted, merged = self._failed_done_chain()
        _seed_metadata(tracker, [exhausted, merged])
        owner = ContributorIdentity("project-owner", "api")
        reason = "Independent auditor capacity was restored."
        first = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                reason,
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )
        assert first.success is True
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        store.update(
            TASK_ID,
            lambda document: replace(
                document,
                pending_chain=[
                    replace(
                        record,
                        prerequisite_audit_id="audit-done-replaced",
                    )
                    if record.audit_id == merged.audit_id
                    else record
                    for record in document.pending_chain
                ],
            ),
        )
        before = store.read(TASK_ID)

        repeated = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.DONE,
                owner,
                PROJECT_ID,
                reason,
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        assert repeated.success is False
        assert repeated.reason == "audit_not_retryable"
        assert store.read(TASK_ID) == before
        assert sum(
            record.request_state in (RequestState.PENDING, RequestState.IN_PROGRESS)
            and record.target_state is TargetState.DONE
            for record in before.pending_chain
        ) == 1

    def test_recovery_action_matches_record_classification(self) -> None:
        assert (
            accepted_audit_recovery_action(_exhausted_no_auditor_record())
            == "audit_retry"
        )
        assert (
            accepted_audit_recovery_action(_exhausted_missing_evidence_record())
            == "audit_retry_evidence_addendum"
        )

        missing = _exhausted_missing_evidence_record()
        not_rearmable = replace(
            missing,
            attempts=[
                replace(
                    missing.attempts[0],
                    failure_classification=FailureClassification.INCOMPLETE,
                )
            ],
        )
        assert accepted_audit_recovery_action(not_rearmable) == "audit_override"

        inconsistent = replace(
            missing,
            attempts=[
                replace(
                    missing.attempts[0],
                    target_state=TargetState.MERGED,
                )
            ],
        )
        assert accepted_audit_recovery_action(inconsistent) == "audit_override"

        wrong_fingerprint = replace(
            missing,
            attempts=[
                replace(
                    missing.attempts[0],
                    evidence_fingerprint=_alt_fingerprint(),
                )
            ],
        )
        assert accepted_audit_recovery_action(wrong_fingerprint) == "audit_override"

        passed = replace(
            missing,
            attempts=[
                replace(
                    missing.attempts[0],
                    verdict=Verdict.PASS,
                )
            ],
        )
        assert accepted_audit_recovery_action(passed) == "audit_override"

    def test_successful_rearm_clears_integrated_task_alert(self) -> None:
        tracker = _MemoryTracker()
        exhausted = _exhausted_no_auditor_record()
        _seed_metadata(tracker, [exhausted])
        cleared: list[tuple[str, str]] = []
        coordinator = _coordinator(
            tracker,
            post_comments=False,
            clear_integrated_audit_recovery_alert=lambda project, task: cleared.append(
                (project, task)
            ),
        )

        result = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Transport repaired.",
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        assert result.success is True
        assert cleared == [(PROJECT_ID, TASK_ID)]

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

    def test_owner_rearm_retains_unbound_auto_archive_provenance(self) -> None:
        """Repeated recovery survives restart without losing retention authority."""
        tracker = _MemoryTracker()
        sha = "d" * 40
        project_store = _RevisionLockStore({"origin/main": sha})
        exhausted = replace(
            _exhausted_no_auditor_record(),
            previous_state=DONE,
            requested_by=ContributorIdentity("oompah", "auto_archive"),
            selected_ref=None,
            selected_sha=None,
        )
        _seed_metadata(tracker, [exhausted])
        owner = ContributorIdentity("project-owner", "api")
        reason = "Auditor capacity was restored."
        coordinator = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=project_store,
            post_comments=False,
        )

        first = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                owner,
                PROJECT_ID,
                reason,
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )
        restarted = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=project_store,
            post_comments=False,
        )
        repeated = _run(
            restarted.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                owner,
                PROJECT_ID,
                reason,
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        document = TerminalAuditMetadataStore(
            tracker, project_store, PROJECT_ID
        ).read(TASK_ID)
        fresh = document.pending_chain[-1]
        history = document.unknown_fields["oompah.terminal_audit_rearm_history"]
        assert first.success is True
        assert repeated.success is True
        assert repeated.coalesced is True
        assert repeated.audit_id == first.audit_id
        assert fresh.requested_by == ContributorIdentity("oompah", "auto_archive")
        assert len(history) == 1
        assert history[0]["actor"] == owner.to_dict()
        assert history[0]["source_generation"] == fresh.source_generation

        binding = restarted._request_revision_binding(
            TerminalAuditMetadataStore(tracker, project_store, PROJECT_ID),
            _issue(IN_VALIDATION),
            TargetState.ARCHIVED,
            PROJECT_ID,
            fresh.evidence_fingerprint,
            trigger_identity=ContributorIdentity("project-owner", "api"),
        )

        assert binding is not None
        assert binding.selected_ref == "origin/main"
        assert binding.selected_sha == sha
        rebound = TerminalAuditMetadataStore(
            tracker, project_store, PROJECT_ID
        ).read(TASK_ID).pending_chain[-1]
        assert rebound.requested_by == ContributorIdentity("oompah", "auto_archive")

    def test_owner_rearm_bound_auto_archive_uses_owner_provenance(self) -> None:
        """A pinned retention audit needs no inherited late-binding authority."""
        tracker = _MemoryTracker()
        sha = "d" * 40
        exhausted = replace(
            _exhausted_no_auditor_record(),
            previous_state=DONE,
            requested_by=ContributorIdentity("oompah", "auto_archive"),
            selected_ref="origin/main",
            selected_sha=sha,
        )
        _seed_metadata(tracker, [exhausted])
        coordinator = _coordinator(tracker, post_comments=False)
        owner = ContributorIdentity("project-owner", "api")

        result = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                owner,
                PROJECT_ID,
                "Auditor capacity was restored.",
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )
        repeated = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                owner,
                PROJECT_ID,
                "Auditor capacity was restored.",
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        document = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        fresh = document.pending_chain[-1]
        history = document.unknown_fields["oompah.terminal_audit_rearm_history"]

        assert result.success is True
        assert repeated.success is True
        assert repeated.coalesced is True
        assert fresh.requested_by == owner
        assert fresh.selected_ref == "origin/main"
        assert fresh.selected_sha == sha
        assert history[-1]["actor"] == owner.to_dict()

    @pytest.mark.parametrize(
        "variation",
        ["actor", "reason", "fingerprint", "source_generation"],
    )
    def test_rearm_coalescing_rejects_changed_authorization_identity(
        self,
        variation: str,
    ) -> None:
        tracker = _MemoryTracker()
        project_store = _LockStore()
        exhausted = replace(
            _exhausted_no_auditor_record(),
            previous_state=DONE,
            requested_by=ContributorIdentity("oompah", "auto_archive"),
            selected_ref=None,
            selected_sha=None,
        )
        _seed_metadata(tracker, [exhausted])
        coordinator = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=project_store,
            post_comments=False,
        )
        owner = ContributorIdentity("project-owner", "api")
        other_owner = ContributorIdentity("backup-owner", "api")
        project = SimpleNamespace(
            tracker_owner=owner.identity,
            status_actor_login=None,
            status_label_authorized_logins=[owner.identity, other_owner.identity],
        )
        reason = "Auditor capacity was restored."

        first = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                owner,
                PROJECT_ID,
                reason,
                project,
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )
        assert first.success is True

        repeat_actor = other_owner if variation == "actor" else owner
        repeat_reason = (
            "A different recovery reason."
            if variation == "reason"
            else reason
        )
        repeat_fingerprint = (
            _alt_fingerprint()
            if variation == "fingerprint"
            else exhausted.evidence_fingerprint
        )
        store = TerminalAuditMetadataStore(tracker, project_store, PROJECT_ID)
        if variation == "source_generation":

            def _advance_generation(
                document: TerminalAuditMetadata,
            ) -> TerminalAuditMetadata:
                chain = list(document.pending_chain)
                chain[-1] = replace(
                    chain[-1],
                    source_generation=chain[-1].source_generation + 1,
                )
                return replace(document, pending_chain=chain)

            store.update(TASK_ID, _advance_generation)

        repeated = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                repeat_actor,
                PROJECT_ID,
                repeat_reason,
                project,
                evidence_fingerprint=repeat_fingerprint,
            )
        )

        document = store.read(TASK_ID)
        assert repeated.success is False
        assert repeated.reason == "audit_not_retryable"
        assert len(document.pending_chain) == 2
        assert len(
            document.unknown_fields["oompah.terminal_audit_rearm_history"]
        ) == 1

    def test_concurrent_exact_rearm_repeats_keep_one_history_entry(self) -> None:
        tracker = _MemoryTracker()
        project_store = _LockStore()
        exhausted = replace(
            _exhausted_no_auditor_record(),
            previous_state=DONE,
            requested_by=ContributorIdentity("oompah", "auto_archive"),
            selected_ref=None,
            selected_sha=None,
        )
        _seed_metadata(tracker, [exhausted])
        coordinator = TerminalTransitionCoordinator(
            tracker=tracker,
            project_store=project_store,
            post_comments=False,
        )
        owner = ContributorIdentity("project-owner", "api")
        reason = "Auditor capacity was restored."
        args = (
            _issue(NEEDS_HUMAN),
            TargetState.ARCHIVED,
            owner,
            PROJECT_ID,
            reason,
            self._owner_project(),
        )

        async def _rearm_twice() -> list[TransitionResult]:
            return list(
                await asyncio.gather(
                    coordinator.retry_failed_audit(
                        *args,
                        evidence_fingerprint=exhausted.evidence_fingerprint,
                    ),
                    coordinator.retry_failed_audit(
                        *args,
                        evidence_fingerprint=exhausted.evidence_fingerprint,
                    ),
                )
            )

        results = asyncio.run(_rearm_twice())
        document = TerminalAuditMetadataStore(
            tracker, project_store, PROJECT_ID
        ).read(TASK_ID)

        assert all(result.success for result in results)
        assert sum(result.coalesced for result in results) == 1
        assert len({result.audit_id for result in results}) == 1
        assert len(document.pending_chain) == 2
        assert len(
            document.unknown_fields["oompah.terminal_audit_rearm_history"]
        ) == 1
        assert document.pending_chain[-1].requested_by == ContributorIdentity(
            "oompah", "auto_archive"
        )

    @pytest.mark.parametrize(
        ("verdict", "classification", "origin"),
        [
            (Verdict.FAIL, FailureClassification.NO_AUDITOR, None),
            (Verdict.FAIL, FailureClassification.MALFORMED_RESULT, None),
            (None, FailureClassification.INFRASTRUCTURE_ERROR, None),
            (Verdict.ERROR, FailureClassification.POLICY_INCOMPATIBILITY, None),
            (None, FailureClassification.FINALIZATION_FAILURE, None),
            (Verdict.ERROR, None, None),
            # Exhaustion routing records a synthetic NEEDS_HUMAN outcome with
            # trusted coordinator provenance after the bounded retries end.
            (
                Verdict.NEEDS_HUMAN,
                FailureClassification.INFRASTRUCTURE_ERROR,
                AuditAttemptOrigin.COORDINATOR_RETRY_EXHAUSTION,
            ),
        ],
    )
    def test_owner_rearms_every_non_substantive_exhaustion_attempt(
        self,
        verdict: Verdict | None,
        classification: FailureClassification | None,
        origin: AuditAttemptOrigin | None,
    ) -> None:
        exhausted = _exhausted_no_auditor_record()
        exhausted = replace(
            exhausted,
            attempts=[
                replace(
                    exhausted.attempts[0],
                    verdict=verdict,
                    failure_classification=classification,
                    origin=origin,
                )
            ],
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [exhausted])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "The audit execution path is healthy again.",
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        assert result.success is True
        assert result.superseded_audit_id == exhausted.audit_id
        assert tracker.current_status(TASK_ID) == IN_VALIDATION

    @pytest.mark.parametrize(
        ("verdict", "classification"),
        [
            (Verdict.PASS, None),
            (Verdict.PASS, FailureClassification.INFRASTRUCTURE_ERROR),
            (Verdict.FAIL, FailureClassification.INCOMPLETE),
            (Verdict.NEEDS_HUMAN, None),
            (Verdict.NEEDS_HUMAN, FailureClassification.INFRASTRUCTURE_ERROR),
            (Verdict.ERROR, FailureClassification.MISSING_TESTS),
            (Verdict.FAIL, None),
        ],
    )
    def test_owner_cannot_rearm_substantive_or_unclassified_failures(
        self,
        verdict: Verdict | None,
        classification: FailureClassification | None,
    ) -> None:
        exhausted = _exhausted_no_auditor_record()
        exhausted = replace(
            exhausted,
            attempts=[
                replace(
                    exhausted.attempts[0],
                    verdict=verdict,
                    failure_classification=classification,
                )
            ],
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [exhausted])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Retry this audit.",
                self._owner_project(),
            )
        )

        assert result.success is False
        assert result.reason == "audit_not_retryable"
        assert tracker.current_status(TASK_ID) is None

    def test_retry_is_idempotent_after_fresh_record_is_pending(self) -> None:
        tracker = _MemoryTracker()
        exhausted = _exhausted_no_auditor_record()
        _seed_metadata(tracker, [exhausted])
        coordinator = _coordinator(tracker, post_comments=False)
        args = (
            _issue(NEEDS_HUMAN),
            TargetState.ARCHIVED,
            ContributorIdentity("project-owner", "api"),
            PROJECT_ID,
            "Workspace transport repaired.",
            self._owner_project(),
        )

        first = _run(
            coordinator.retry_failed_audit(
                *args, evidence_fingerprint=exhausted.evidence_fingerprint
            )
        )
        second = _run(
            coordinator.retry_failed_audit(
                *args, evidence_fingerprint=exhausted.evidence_fingerprint
            )
        )

        assert first.success is True
        assert second.success is True
        assert second.coalesced is True
        assert second.audit_id == first.audit_id
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert len(stored.pending_chain) == 2

    def test_ordinary_retry_rejects_changed_canonical_fingerprint(self) -> None:
        issue = _issue(NEEDS_HUMAN)
        issue.description = "current requirements"
        current_fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
        exhausted = replace(
            _exhausted_no_auditor_record(),
            evidence_fingerprint=_alt_fingerprint(),
            attempts=[
                replace(
                    attempt,
                    evidence_fingerprint=_alt_fingerprint(),
                )
                for attempt in _exhausted_no_auditor_record().attempts
            ],
        )
        assert exhausted.evidence_fingerprint != current_fingerprint
        tracker = _RefreshingTracker(issue)
        _seed_metadata(tracker, [exhausted])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                issue,
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Workspace transport repaired.",
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        assert result.success is False
        assert result.reason == "evidence_fingerprint_mismatch"
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert stored.pending_chain == [exhausted]

    def test_ordinary_retry_rejects_unavailable_authoritative_evidence(self) -> None:
        issue = _issue(NEEDS_HUMAN)
        exhausted = _exhausted_no_auditor_record()
        tracker = _UnavailableRefreshingTracker()
        _seed_metadata(tracker, [exhausted])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                issue,
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Workspace transport repaired.",
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        assert result.success is False
        assert result.reason == "evidence_unavailable"
        assert tracker.update_calls == []
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain == [exhausted]

    def test_ordinary_retry_does_not_select_older_matching_completed_record(
        self,
    ) -> None:
        issue = _issue(NEEDS_HUMAN)
        issue.description = "current requirements"
        current_fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
        template = _exhausted_no_auditor_record()
        older_current = replace(
            template,
            audit_id="audit-older-current",
            evidence_fingerprint=current_fingerprint,
            attempts=[
                replace(attempt, evidence_fingerprint=current_fingerprint)
                for attempt in template.attempts
            ],
        )
        newer_stale = replace(
            template,
            audit_id="audit-newer-stale",
            evidence_fingerprint=_alt_fingerprint(),
            attempts=[
                replace(attempt, evidence_fingerprint=_alt_fingerprint())
                for attempt in template.attempts
            ],
        )
        tracker = _RefreshingTracker(issue)
        _seed_metadata(tracker, [older_current, newer_stale])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                issue,
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Workspace transport repaired.",
                self._owner_project(),
                evidence_fingerprint=current_fingerprint,
            )
        )

        assert result.success is False
        assert result.reason == "audit_not_retryable"
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain == [older_current, newer_stale]

    def test_ordinary_retry_does_not_coalesce_unowned_pending_audit(self) -> None:
        issue = _issue(NEEDS_HUMAN)
        fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
        pending = _pending_record(
            target=TargetState.ARCHIVED,
            fingerprint=fingerprint,
            previous=MERGED,
        )
        tracker = _RefreshingTracker(issue)
        _seed_metadata(tracker, [pending])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                issue,
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Workspace transport repaired.",
                self._owner_project(),
                evidence_fingerprint=fingerprint,
            )
        )

        assert result.success is False
        assert result.reason == "audit_not_retryable"
        assert TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain == [pending]

    def test_ordinary_retry_rejects_older_live_same_key_sibling(self) -> None:
        issue = _issue(NEEDS_HUMAN)
        fingerprint = compute_issue_evidence_fingerprint(issue, PROJECT_ID)
        template = _exhausted_no_auditor_record()
        exhausted = replace(
            template,
            evidence_fingerprint=fingerprint,
            attempts=[
                replace(attempt, evidence_fingerprint=fingerprint)
                for attempt in template.attempts
            ],
        )
        older_pending = _pending_record(
            audit_id="audit-older-unowned",
            target=TargetState.ARCHIVED,
            fingerprint=fingerprint,
            previous=MERGED,
        )
        tracker = _RefreshingTracker(issue)
        _seed_metadata(tracker, [older_pending, exhausted])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                issue,
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Workspace transport repaired.",
                self._owner_project(),
                evidence_fingerprint=fingerprint,
            )
        )

        assert result.success is False
        assert result.reason == "audit_not_retryable"
        assert tracker.update_calls == []
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert stored.pending_chain == [older_pending, exhausted]
        assert "oompah.terminal_audit_rearm_history" not in stored.unknown_fields

    def test_failed_status_stage_is_durable_and_not_reported_as_success(self) -> None:
        tracker = _FailingUpdateTracker()
        exhausted = _exhausted_no_auditor_record()
        _seed_metadata(tracker, [exhausted])
        cleared: list[tuple[str, str]] = []
        coordinator = _coordinator(
            tracker,
            post_comments=False,
            clear_integrated_audit_recovery_alert=lambda project, task: cleared.append(
                (project, task)
            ),
        )

        failed = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Workspace transport repaired.",
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )

        assert failed.success is False
        assert failed.reason == "status_stage_failed"
        assert failed.audit_id is not None
        assert cleared == []
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        fresh = stored.pending_chain[-1]
        assert fresh.request_state == RequestState.PENDING
        intents = stored.unknown_fields["oompah.terminal_audit_result_intents"]
        assert intents[-1]["kind"] == "audit_rearm"
        assert intents[-1]["status"] == IN_VALIDATION
        assert intents[-1]["applied"] is False

        tracker.fail_update = False
        repaired = _run(
            coordinator.retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.ARCHIVED,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Workspace transport repaired.",
                self._owner_project(),
                evidence_fingerprint=exhausted.evidence_fingerprint,
            )
        )
        assert repaired.success is True
        assert repaired.coalesced is True
        assert tracker.current_status(TASK_ID) == IN_VALIDATION
        assert cleared == [(PROJECT_ID, TASK_ID)]

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
        assert fresh.source_generation == old.source_generation + 1
        history = stored.unknown_fields["oompah.terminal_audit_rearm_history"]
        assert history[0]["actor"]["identity"] == "project-owner"
        assert history[0]["reason"] == "Pinned gate tails supplied for the integrated head"
        assert history[0]["source_generation"] == fresh.source_generation
        assert history[0]["evidence_fingerprint"] == fresh.evidence_fingerprint.digest
        assert history[0]["authorized_at"]
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

    def test_missing_evidence_rearm_rejects_pass_with_retry_classification(
        self,
    ) -> None:
        failed = _exhausted_missing_evidence_record()
        passed = replace(
            failed,
            audit_id="audit-passed-with-missing-evidence",
            attempts=[replace(failed.attempts[0], verdict=Verdict.PASS)],
        )
        tracker = _MemoryTracker()
        _seed_metadata(tracker, [passed])

        result = _run(
            _coordinator(tracker, post_comments=False).retry_failed_audit(
                _issue(NEEDS_HUMAN),
                TargetState.DONE,
                ContributorIdentity("project-owner", "api"),
                PROJECT_ID,
                "Evidence supplied.",
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


def test_active_legacy_attempt_is_superseded_before_binding_and_result_rejected() -> None:
    fingerprint = _fingerprint()
    legacy_attempt = AuditAttempt(
        attempt_id="attempt-legacy-unbound",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
        created_at="2026-08-01T00:00:00+00:00",
        started_at="2026-08-01T00:00:00+00:00",
    )
    legacy = replace(
        _pending_record(
            audit_id="audit-legacy-unbound",
            target=TargetState.DONE,
            fingerprint=fingerprint,
            state=RequestState.IN_PROGRESS,
        ),
        attempts=[legacy_attempt],
    )
    tracker = _MemoryTracker()
    _seed_metadata(tracker, [legacy])
    project_store = _RevisionLockStore({"origin/audit-work": "b" * 40})
    coordinator = TerminalTransitionCoordinator(
        tracker=tracker,
        project_store=project_store,
        post_comments=False,
    )
    request_issue = _issue()
    request_issue.work_branch = "audit-work"

    result = _run(
        coordinator.request_transition(
            request_issue,
            TargetState.DONE,
            _trigger(),
            PROJECT_ID,
            fingerprint,
        )
    )
    records = TerminalAuditMetadataStore(
        tracker,
        project_store,
        PROJECT_ID,
    ).read(TASK_ID).pending_chain
    old = next(record for record in records if record.audit_id == legacy.audit_id)
    fresh = next(
        record
        for record in records
        if record.audit_id != legacy.audit_id
        and record.request_state is RequestState.PENDING
    )

    assert result.success is True
    assert result.coalesced is False
    assert old.request_state is RequestState.SUPERSEDED
    assert old.selected_sha is None
    assert legacy_attempt.selected_sha is None
    assert fresh.selected_ref == "origin/audit-work"
    assert fresh.selected_sha == "b" * 40

    late = _apply(
        coordinator,
        _issue(IN_VALIDATION),
        _pass_result(legacy, attempt_id=legacy_attempt.attempt_id),
    )
    assert late.success is False
    assert late.reason == ResultRejection.STATE_MISMATCH


def test_result_rejects_matching_attempt_without_record_revision_authority() -> None:
    fingerprint = _fingerprint()
    attempt = AuditAttempt(
        attempt_id="attempt-unbound",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.IN_PROGRESS,
    )
    record = replace(
        _pending_record(
            target=TargetState.DONE,
            fingerprint=fingerprint,
            state=RequestState.IN_PROGRESS,
        ),
        attempts=[attempt],
    )
    tracker = _MemoryTracker()
    issue = _seed_and_validation(tracker, [record])

    outcome = _apply(
        _coordinator(tracker),
        issue,
        _pass_result(record, attempt_id=attempt.attempt_id),
    )

    assert outcome.success is False
    assert outcome.reason == ResultRejection.REVISION_BINDING_MISMATCH
    assert tracker.current_status(TASK_ID) is None


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

    def test_scheduler_pause_returns_none_for_nonterminal(self) -> None:
        assert (
            classify_failure_to_status(FailureClassification.SCHEDULER_PAUSE)
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
    def test_pass_rejects_tracker_evidence_changed_after_auditor_snapshot(self) -> None:
        class DetailTracker(_MemoryTracker):
            def __init__(self, current: Issue) -> None:
                super().__init__()
                self.current = current

            def fetch_issue_detail(self, identifier: str) -> Issue | None:
                if identifier != self.current.identifier:
                    return None
                return copy.copy(self.current)

            def update_issue(self, identifier: str, **kwargs: Any) -> None:
                super().update_issue(identifier, **kwargs)
                if "status" in kwargs:
                    self.current.state = kwargs["status"]

        current = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Test task",
            description="audited requirements",
            state="In Progress",
            project_id=PROJECT_ID,
            work_branch="TASK-42",
            head_sha="a" * 40,
        )
        tracker = DetailTracker(current)
        fingerprint = compute_issue_evidence_fingerprint(current, PROJECT_ID)
        coord = _coordinator(tracker)
        staged = _run(
            coord.request_transition(
                copy.copy(current),
                TargetState.DONE,
                _trigger(),
                PROJECT_ID,
                fingerprint,
            )
        )
        assert staged.success is True
        record = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain[0]
        submitted_snapshot = copy.copy(current)
        current.description = "requirements changed after audit"

        outcome = _apply(coord, submitted_snapshot, _pass_result(record))

        assert outcome.success is False
        assert outcome.reason == ResultRejection.CURRENT_EVIDENCE_MISMATCH
        assert tracker.current_status(TASK_ID) == IN_VALIDATION
        doc = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert len(doc.pending_chain) == 2
        assert doc.pending_chain[0].request_state == RequestState.SUPERSEDED
        replacement = doc.pending_chain[1]
        assert replacement.request_state == RequestState.PENDING
        assert replacement.target_state == record.target_state
        assert replacement.previous_state == record.previous_state
        assert replacement.evidence_fingerprint == compute_issue_evidence_fingerprint(
            current, PROJECT_ID
        )

    def test_evidence_drift_replacement_preserves_workflow_authority(self) -> None:
        class DetailTracker(_MemoryTracker):
            def __init__(self, current: Issue) -> None:
                super().__init__()
                self.current = current

            def fetch_issue_detail(self, identifier: str) -> Issue | None:
                if identifier != self.current.identifier:
                    return None
                return copy.copy(self.current)

            def update_issue(self, identifier: str, **kwargs: Any) -> None:
                super().update_issue(identifier, **kwargs)
                if "status" in kwargs:
                    self.current.state = kwargs["status"]

        current = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Workflow-bound task",
            description="audited requirements",
            state="In Progress",
            project_id=PROJECT_ID,
        )
        tracker = DetailTracker(current)
        fingerprint = compute_issue_evidence_fingerprint(current, PROJECT_ID)
        coordinator = _coordinator(tracker)
        staged = _run(
            coordinator.request_transition(
                copy.copy(current),
                TargetState.DONE,
                _trigger(),
                PROJECT_ID,
                fingerprint,
            )
        )
        assert staged.success
        store = TerminalAuditMetadataStore(tracker, _LockStore(), PROJECT_ID)
        document = store.read(TASK_ID)
        bound = replace(
            document.pending_chain[0],
            workflow_revision="workflow-revision-2",
            selected_ref="refs/heads/main",
            selected_sha="b" * 40,
        )
        tracker.set_metadata_field(
            TASK_ID,
            METADATA_KEY,
            replace(document, pending_chain=[bound]).to_dict(),
        )
        current.description = "requirements changed after audit"

        outcome = _apply(coordinator, copy.copy(current), _pass_result(bound))

        assert not outcome.success
        assert outcome.reason is ResultRejection.CURRENT_EVIDENCE_MISMATCH
        records = store.read(TASK_ID).pending_chain
        assert records[0].request_state is RequestState.SUPERSEDED
        replacement = records[-1]
        assert replacement.request_state is RequestState.PENDING
        assert replacement.workflow_revision == bound.workflow_revision
        assert replacement.selected_ref == bound.selected_ref
        assert replacement.selected_sha == bound.selected_sha

    def test_richer_fingerprint_uses_durable_tracker_projection_after_restart(
        self,
    ) -> None:
        class DetailTracker(_MemoryTracker):
            def __init__(self, current: Issue) -> None:
                super().__init__()
                self.current = current

            def fetch_issue_detail(self, identifier: str) -> Issue | None:
                return copy.copy(self.current) if identifier == TASK_ID else None

            def update_issue(self, identifier: str, **kwargs: Any) -> None:
                super().update_issue(identifier, **kwargs)
                if "status" in kwargs:
                    self.current.state = kwargs["status"]

        current = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Test task",
            description="stable tracker projection",
            state="In Progress",
            project_id=PROJECT_ID,
        )
        tracker = DetailTracker(current)
        richer_fingerprint = _fingerprint("c")
        staged = _run(
            _coordinator(tracker).request_transition(
                copy.copy(current),
                TargetState.DONE,
                _trigger(),
                PROJECT_ID,
                richer_fingerprint,
            )
        )
        assert staged.success is True
        record = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain[0]
        assert record.evidence_fingerprint == richer_fingerprint

        # A new coordinator represents restart recovery: only tracker metadata
        # carries the separate projection that proves no tracker evidence drift.
        outcome = _apply(
            _coordinator(tracker),
            copy.copy(current),
            _pass_result(record),
        )

        assert outcome.success is True
        assert outcome.applied_status == DONE

    def test_richer_fingerprint_drift_never_requeues_weaker_evidence(self) -> None:
        class DetailTracker(_MemoryTracker):
            def __init__(self, current: Issue) -> None:
                super().__init__()
                self.current = current

            def fetch_issue_detail(self, identifier: str) -> Issue | None:
                return copy.copy(self.current) if identifier == TASK_ID else None

            def update_issue(self, identifier: str, **kwargs: Any) -> None:
                super().update_issue(identifier, **kwargs)
                if "status" in kwargs:
                    self.current.state = kwargs["status"]

        current = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Test task",
            description="original tracker projection",
            state="In Progress",
            project_id=PROJECT_ID,
        )
        tracker = DetailTracker(current)
        richer_fingerprint = _fingerprint("c")
        coordinator = _coordinator(tracker)
        staged = _run(
            coordinator.request_transition(
                copy.copy(current),
                TargetState.DONE,
                _trigger(),
                PROJECT_ID,
                richer_fingerprint,
            )
        )
        assert staged.success is True
        record = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID).pending_chain[0]
        current.description = "changed tracker projection"

        outcome = _apply(coordinator, copy.copy(current), _pass_result(record))

        assert outcome.success is False
        assert outcome.reason == ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE
        doc = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert len(doc.pending_chain) == 1
        assert doc.pending_chain[0].request_state == RequestState.PENDING
        assert doc.pending_chain[0].evidence_fingerprint == richer_fingerprint

    def test_legacy_record_without_projection_accepts_reproducible_evidence(
        self,
    ) -> None:
        class DetailTracker(_MemoryTracker):
            def __init__(self, current: Issue) -> None:
                super().__init__()
                self.current = current

            def fetch_issue_detail(self, identifier: str) -> Issue | None:
                return copy.copy(self.current) if identifier == TASK_ID else None

            def update_issue(self, identifier: str, **kwargs: Any) -> None:
                super().update_issue(identifier, **kwargs)
                if "status" in kwargs:
                    self.current.state = kwargs["status"]

        current = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Legacy task",
            description="unchanged legacy evidence",
            state=IN_VALIDATION,
            project_id=PROJECT_ID,
        )
        tracker = DetailTracker(current)
        record = _pending_record(
            fingerprint=compute_issue_evidence_fingerprint(current, PROJECT_ID)
        )
        # Direct metadata seeding intentionally models a pre-ledger record.
        _seed_metadata(tracker, [record])

        outcome = _apply(_coordinator(tracker), copy.copy(current), _pass_result(record))

        assert outcome.success is True
        assert outcome.applied_status == DONE

    def test_legacy_record_remains_reproducible_after_newer_projection_exists(
        self,
    ) -> None:
        class DetailTracker(_MemoryTracker):
            def __init__(self, current: Issue) -> None:
                super().__init__()
                self.current = current

            def fetch_issue_detail(self, identifier: str) -> Issue | None:
                return copy.copy(self.current) if identifier == TASK_ID else None

            def update_issue(self, identifier: str, **kwargs: Any) -> None:
                super().update_issue(identifier, **kwargs)
                if "status" in kwargs:
                    self.current.state = kwargs["status"]

        current = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Mixed-version task",
            description="unchanged legacy evidence",
            state=IN_VALIDATION,
            project_id=PROJECT_ID,
        )
        tracker = DetailTracker(current)
        fingerprint = compute_issue_evidence_fingerprint(current, PROJECT_ID)
        legacy = _pending_record(fingerprint=fingerprint)
        newer = _pending_record(
            audit_id="audit-with-projection",
            target=TargetState.ARCHIVED,
            state=RequestState.SUPERSEDED,
        )
        document = TerminalAuditMetadata(
            pending_chain=[legacy, newer],
            unknown_fields={
                "oompah.terminal_audit_tracker_projections": [
                    {
                        "version": 1,
                        "audit_id": newer.audit_id,
                        "project_id": PROJECT_ID,
                        "task_id": TASK_ID,
                        "digest": fingerprint.digest,
                    }
                ]
            },
        )
        tracker.set_metadata_field(TASK_ID, METADATA_KEY, document.to_dict())

        outcome = _apply(
            _coordinator(tracker), copy.copy(current), _pass_result(legacy)
        )

        assert outcome.success is True
        assert outcome.applied_status == DONE

    def test_legacy_unreproducible_fingerprint_fails_closed_without_downgrade(
        self,
    ) -> None:
        class DetailTracker(_MemoryTracker):
            def __init__(self, current: Issue) -> None:
                super().__init__()
                self.current = current

            def fetch_issue_detail(self, identifier: str) -> Issue | None:
                return copy.copy(self.current) if identifier == TASK_ID else None

        current = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Legacy task",
            description="tracker-only projection",
            state=IN_VALIDATION,
            project_id=PROJECT_ID,
        )
        tracker = DetailTracker(current)
        record = _pending_record(fingerprint=_fingerprint("d"))
        _seed_metadata(tracker, [record])

        outcome = _apply(_coordinator(tracker), copy.copy(current), _pass_result(record))

        assert outcome.success is False
        assert outcome.reason == ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE
        doc = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert len(doc.pending_chain) == 1
        assert doc.pending_chain[0].request_state == RequestState.PENDING

    def test_retry_exhaustion_escalates_legacy_audit_after_evidence_drift(
        self,
    ) -> None:
        class DetailTracker(_MemoryTracker):
            def __init__(self, current: Issue) -> None:
                super().__init__()
                self.current = current

            def fetch_issue_detail(self, identifier: str) -> Issue | None:
                return copy.copy(self.current) if identifier == TASK_ID else None

            def update_issue(self, identifier: str, **kwargs: Any) -> None:
                super().update_issue(identifier, **kwargs)
                if "status" in kwargs:
                    self.current.state = kwargs["status"]

        current = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Legacy exhausted audit",
            description="current tracker projection after cutover",
            state=IN_VALIDATION,
            project_id=PROJECT_ID,
        )
        tracker = DetailTracker(current)
        record = _pending_record(fingerprint=_fingerprint("d"))
        _seed_metadata(tracker, [record])
        result = AuditResult(
            audit_id=record.audit_id,
            target_state=record.target_state,
            evidence_fingerprint=record.evidence_fingerprint,
            verdict=Verdict.NEEDS_HUMAN,
            failure_classification=FailureClassification.INFRASTRUCTURE_ERROR,
            message=(
                "Audit infrastructure retries were exhausted. Restore the "
                "auditor transport, then have a project owner rearm this audit."
            ),
            attempt_id="infrastructure-exhausted-audit-pending-1-1",
            attempt_origin=AuditAttemptOrigin.COORDINATOR_RETRY_EXHAUSTION,
        )
        coordinator = _coordinator(tracker)

        outcome = _apply(coordinator, copy.copy(current), result)
        replay = _apply(coordinator, copy.copy(current), result)

        assert outcome.success is True
        assert outcome.applied_status == NEEDS_HUMAN
        assert replay.success is True
        assert replay.idempotent is True
        doc = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        assert doc.pending_chain[0].request_state == RequestState.COMPLETED
        assert len(doc.pending_chain[0].attempts) == 1

    def test_model_needs_human_cannot_bypass_legacy_evidence_drift(self) -> None:
        class DetailTracker(_MemoryTracker):
            def __init__(self, current: Issue) -> None:
                super().__init__()
                self.current = current

            def fetch_issue_detail(self, identifier: str) -> Issue | None:
                return copy.copy(self.current) if identifier == TASK_ID else None

        current = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Legacy audit",
            description="current tracker projection after cutover",
            state=IN_VALIDATION,
            project_id=PROJECT_ID,
        )
        tracker = DetailTracker(current)
        record = _pending_record(fingerprint=_fingerprint("d"))
        _seed_metadata(tracker, [record])

        outcome = _apply(
            _coordinator(tracker),
            copy.copy(current),
            _needs_human_result(
                record,
                message="Please review the evidence drift and decide how to proceed.",
            ),
        )

        assert outcome.success is False
        assert outcome.reason == ResultRejection.CURRENT_EVIDENCE_UNAVAILABLE
        assert tracker.current_status(TASK_ID) is None

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

    def test_pass_clears_integrated_task_alert_after_terminal_status(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.DONE)
        issue = _seed_and_validation(tracker, [record])
        cleared: list[tuple[str, str]] = []
        coord = _coordinator(
            tracker,
            clear_integrated_audit_recovery_alert=lambda project, task: cleared.append(
                (project, task)
            ),
        )

        outcome = _apply(coord, issue, _pass_result(record))

        assert outcome.success is True
        assert cleared == [(PROJECT_ID, TASK_ID)]

    def test_pass_posts_result_comment_referencing_target(self) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.MERGED)
        done = replace(
            _pending_record(
                audit_id="audit-done-prerequisite",
                target=TargetState.DONE,
                fingerprint=record.evidence_fingerprint,
            ),
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-done-prerequisite",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=record.evidence_fingerprint,
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.PASS,
                )
            ],
        )
        issue = _seed_and_validation(tracker, [done, record])
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(record))

        assert outcome.posted_comment is True
        posted = tracker.comment_calls[-1][1]
        assert "PASS" in posted
        assert TargetState.MERGED.value in posted

    def test_merged_result_is_rejected_until_exact_done_prerequisite_passes(
        self,
    ) -> None:
        tracker = _MemoryTracker()
        record = _pending_record(target=TargetState.MERGED)
        failed_done = replace(
            _pending_record(
                audit_id="audit-failed-done",
                target=TargetState.DONE,
                fingerprint=record.evidence_fingerprint,
            ),
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-failed-done",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=record.evidence_fingerprint,
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.FAIL,
                    failure_classification=FailureClassification.MISSING_EVIDENCE,
                )
            ],
        )
        issue = _seed_and_validation(tracker, [failed_done, record])
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(record))

        assert outcome.success is False
        assert outcome.reason == ResultRejection.PREREQUISITE_NOT_COMPLETED

    def test_merged_result_ignores_foreign_same_identifier_prerequisite(self) -> None:
        tracker = _MemoryTracker()
        merged = _pending_record(
            audit_id="audit-shared",
            target=TargetState.MERGED,
        )
        foreign_done = replace(
            _pending_record(
                audit_id="audit-shared",
                target=TargetState.DONE,
                fingerprint=merged.evidence_fingerprint,
                project_id="project-foreign",
            ),
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-shared",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=merged.evidence_fingerprint,
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.PASS,
                )
            ],
        )
        issue = _seed_and_validation(tracker, [foreign_done, merged])

        outcome = _apply(_coordinator(tracker), issue, _pass_result(merged))

        assert outcome.success is False
        assert outcome.reason == ResultRejection.PREREQUISITE_NOT_COMPLETED

    def test_passed_done_ignores_foreign_merged_successor(self) -> None:
        tracker = _MemoryTracker()
        done = _pending_record(target=TargetState.DONE)
        foreign_merged = _pending_record(
            audit_id="audit-foreign-merged",
            target=TargetState.MERGED,
            fingerprint=done.evidence_fingerprint,
            project_id="project-foreign",
        )
        issue = _seed_and_validation(tracker, [done, foreign_merged])

        outcome = _apply(_coordinator(tracker), issue, _pass_result(done))

        assert outcome.success is True
        assert outcome.applied_status == DONE
        assert outcome.advanced_target is None

    def test_result_selects_exact_project_task_despite_foreign_audit_id_collision(
        self,
    ) -> None:
        tracker = _MemoryTracker()
        local = _pending_record(audit_id="audit-shared")
        foreign = replace(local, project_id="project-foreign")
        issue = _seed_and_validation(tracker, [foreign, local])

        outcome = _apply(_coordinator(tracker), issue, _pass_result(local))

        assert outcome.success is True
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        by_project = {record.project_id: record for record in stored.pending_chain}
        assert by_project[PROJECT_ID].request_state is RequestState.COMPLETED
        assert by_project["project-foreign"].request_state is RequestState.PENDING
        assert tracker.current_status(TASK_ID) == DONE

    def test_legacy_attempt_log_collision_cannot_impersonate_local_result(self) -> None:
        tracker = _MemoryTracker()
        attempt = AuditAttempt(
            attempt_id="attempt-shared",
            target_state=TargetState.DONE,
            evidence_fingerprint=_fingerprint(),
            request_state=RequestState.IN_PROGRESS,
            selected_ref="origin/main",
            selected_sha="a" * 40,
        )
        local = replace(
            _pending_record(audit_id="audit-shared"),
            request_state=RequestState.IN_PROGRESS,
            attempts=[attempt],
            selected_ref="origin/main",
            selected_sha="a" * 40,
        )
        foreign = replace(local, project_id="project-foreign")
        document = TerminalAuditMetadata(
            pending_chain=[foreign, local],
            unknown_fields={
                "applied_result_attempts": {
                    "attempt-shared": "audit-shared",
                }
            },
        )
        tracker.set_metadata_field(TASK_ID, METADATA_KEY, document.to_dict())
        issue = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Test task",
            state=IN_VALIDATION,
        )

        outcome = _apply(
            _coordinator(tracker),
            issue,
            _pass_result(local, attempt_id="attempt-shared"),
        )

        assert outcome.success is True
        assert outcome.idempotent is False
        assert tracker.current_status(TASK_ID) == DONE
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        by_project = {record.project_id: record for record in stored.pending_chain}
        assert by_project[PROJECT_ID].request_state is RequestState.COMPLETED
        assert by_project["project-foreign"].request_state is RequestState.IN_PROGRESS

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
        assert outcome.advanced_audit_id == chain[1].audit_id
        assert outcome.applied_status == IN_VALIDATION
        assert tracker.current_status(TASK_ID) == IN_VALIDATION
        stored = TerminalAuditMetadataStore(
            tracker, _LockStore(), PROJECT_ID
        ).read(TASK_ID)
        successor = next(
            record
            for record in stored.pending_chain
            if record.audit_id == chain[1].audit_id
        )
        assert successor.prerequisite_audit_id == chain[0].audit_id
        assert successor.eligible_at is not None

    def test_pass_on_done_wakes_its_exact_merged_successor(self) -> None:
        tracker = _MemoryTracker()
        chain = self._done_merged_chain()
        chain[1] = replace(
            chain[1],
            prerequisite_audit_id=chain[0].audit_id,
            eligible_at=None,
        )
        issue = _seed_and_validation(tracker, chain)

        outcome = _apply(_coordinator(tracker), issue, _pass_result(chain[0]))

        stored = TerminalAuditMetadataStore(
            tracker,
            _LockStore(),
            PROJECT_ID,
        ).read(TASK_ID)
        successor = next(
            record
            for record in stored.pending_chain
            if record.audit_id == chain[1].audit_id
        )
        assert outcome.success is True
        assert outcome.advanced_audit_id == successor.audit_id
        assert outcome.applied_status == IN_VALIDATION
        assert successor.prerequisite_audit_id == chain[0].audit_id
        assert successor.eligible_at is not None

    @pytest.mark.parametrize(
        "prerequisite_case",
        ["missing", "stale", "failed"],
    )
    def test_pass_on_done_does_not_wake_mismatched_merged_successor(
        self,
        prerequisite_case: str,
    ) -> None:
        tracker = _MemoryTracker()
        chain = self._done_merged_chain()
        prerequisite_audit_id = f"audit-done-{prerequisite_case}"
        if prerequisite_case != "missing":
            chain.insert(
                1,
                replace(
                    _pending_record(
                        audit_id=prerequisite_audit_id,
                        target=TargetState.DONE,
                        state=(
                            RequestState.SUPERSEDED
                            if prerequisite_case == "stale"
                            else RequestState.COMPLETED
                        ),
                    ),
                    attempts=[
                        AuditAttempt(
                            attempt_id=f"attempt-{prerequisite_case}",
                            target_state=TargetState.DONE,
                            evidence_fingerprint=_fingerprint(),
                            request_state=RequestState.COMPLETED,
                            verdict=(
                                Verdict.PASS
                                if prerequisite_case == "stale"
                                else Verdict.FAIL
                            ),
                        )
                    ],
                ),
            )
        successor_id = "audit-merged"
        successor_index = next(
            index
            for index, candidate in enumerate(chain)
            if candidate.audit_id == successor_id
        )
        chain[successor_index] = replace(
            chain[successor_index],
            prerequisite_audit_id=prerequisite_audit_id,
            eligible_at=None,
        )
        issue = _seed_and_validation(tracker, chain)

        outcome = _apply(_coordinator(tracker), issue, _pass_result(chain[0]))

        stored = TerminalAuditMetadataStore(
            tracker,
            _LockStore(),
            PROJECT_ID,
        ).read(TASK_ID)
        successor = next(
            record
            for record in stored.pending_chain
            if record.audit_id == successor_id
        )
        assert outcome.success is True
        assert outcome.advanced_target is None
        assert outcome.advanced_audit_id is None
        assert outcome.applied_status == DONE
        assert successor.prerequisite_audit_id == prerequisite_audit_id
        assert successor.eligible_at is None

    def test_pass_on_final_chain_item_reaches_terminal_state(self) -> None:
        tracker = _MemoryTracker()
        chain = self._done_merged_chain()
        # Mark Done already completed
        chain[0] = replace(
            chain[0],
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-done",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=chain[0].evidence_fingerprint,
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.PASS,
                )
            ],
        )
        chain[1] = replace(
            chain[1],
            prerequisite_audit_id=chain[0].audit_id,
            eligible_at="2026-08-11T12:00:00+00:00",
        )
        issue = _seed_and_validation(tracker, chain)
        coord = _coordinator(tracker)

        outcome = _apply(coord, issue, _pass_result(chain[1]))

        assert outcome.applied_status == MERGED
        assert outcome.advanced_target is None
        assert tracker.current_status(TASK_ID) == MERGED

    def test_merged_pass_rejects_other_same_authority_done_pass(self) -> None:
        tracker = _MemoryTracker()
        chain = self._done_merged_chain()
        chain[0] = replace(
            chain[0],
            request_state=RequestState.COMPLETED,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-done",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=chain[0].evidence_fingerprint,
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.PASS,
                )
            ],
        )
        chain[1] = replace(
            chain[1],
            prerequisite_audit_id="audit-done-missing",
            eligible_at="2026-08-11T12:00:00+00:00",
        )
        issue = _seed_and_validation(tracker, chain)

        outcome = _apply(
            _coordinator(tracker),
            issue,
            _pass_result(chain[1]),
        )

        assert outcome.success is False
        assert outcome.reason == ResultRejection.PREREQUISITE_NOT_COMPLETED
        assert tracker.current_status(TASK_ID) is None

    def test_merged_pass_requires_completed_done_at_exact_binding(self) -> None:
        tracker = _MemoryTracker()
        done = replace(
            _pending_record(
                audit_id="audit-done-a",
                target=TargetState.DONE,
                state=RequestState.COMPLETED,
            ),
            selected_ref="origin/main",
            selected_sha="a" * 40,
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-done-a",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_fingerprint(),
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.PASS,
                    selected_ref="origin/main",
                    selected_sha="a" * 40,
                )
            ],
        )
        merged = replace(
            _pending_record(
                audit_id="audit-merged-b",
                target=TargetState.MERGED,
            ),
            selected_ref="origin/main",
            selected_sha="b" * 40,
        )
        issue = _seed_and_validation(tracker, [done, merged])

        outcome = _apply(
            _coordinator(tracker),
            issue,
            _pass_result(merged),
        )

        assert outcome.success is False
        assert outcome.reason == ResultRejection.REVISION_BINDING_MISMATCH
        assert tracker.current_status(TASK_ID) is None

    def test_merged_pass_rejects_done_from_older_workflow_revision(self) -> None:
        tracker = _MemoryTracker()
        done = replace(
            _pending_record(
                audit_id="audit-done-old-workflow",
                target=TargetState.DONE,
                state=RequestState.COMPLETED,
            ),
            workflow_revision="workflow-revision-a0",
            attempts=[
                AuditAttempt(
                    attempt_id="attempt-done-old-workflow",
                    target_state=TargetState.DONE,
                    evidence_fingerprint=_fingerprint(),
                    request_state=RequestState.COMPLETED,
                    verdict=Verdict.PASS,
                )
            ],
        )
        merged = replace(
            _pending_record(
                audit_id="audit-merged-new-workflow",
                target=TargetState.MERGED,
            ),
            workflow_revision="workflow-revision-a1",
        )
        issue = _seed_and_validation(tracker, [done, merged])

        outcome = _apply(
            _coordinator(tracker),
            issue,
            _pass_result(merged),
        )

        assert not outcome.success
        assert outcome.reason is ResultRejection.PREREQUISITE_NOT_COMPLETED
        assert tracker.current_status(TASK_ID) is None

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
    def test_live_head_change_rejects_dispatch_snapshot_result(self) -> None:
        initial = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Exact-head task",
            description="requirements",
            state=IN_VALIDATION,
            work_branch="task/TASK-1",
            project_id=PROJECT_ID,
        )
        initial.source_sha = "a" * 40
        tracker = _RefreshingTracker(initial)
        fingerprint = compute_issue_evidence_fingerprint(initial, PROJECT_ID)
        record = _pending_record(fingerprint=fingerprint)
        _seed_metadata(tracker, [record])
        callback_snapshot = tracker.fetch_issue_detail(TASK_ID)
        tracker.issue.source_sha = "b" * 40
        coord = _coordinator(tracker)

        outcome = _apply(coord, callback_snapshot, _pass_result(record))

        assert outcome.success is False
        assert outcome.reason == ResultRejection.FINGERPRINT_MISMATCH
        assert tracker.update_calls == []
        assert tracker.invalidations == 1

    def test_live_status_change_rejects_dispatch_snapshot_result(self) -> None:
        initial = Issue(
            id=TASK_ID,
            identifier=TASK_ID,
            title="Fresh-status task",
            state=IN_VALIDATION,
            project_id=PROJECT_ID,
        )
        tracker = _RefreshingTracker(initial)
        fingerprint = compute_issue_evidence_fingerprint(initial, PROJECT_ID)
        record = _pending_record(fingerprint=fingerprint)
        _seed_metadata(tracker, [record])
        callback_snapshot = tracker.fetch_issue_detail(TASK_ID)
        tracker.issue.state = OPEN
        coord = _coordinator(tracker)

        outcome = _apply(coord, callback_snapshot, _pass_result(record))

        assert outcome.success is False
        assert outcome.reason == ResultRejection.ISSUE_NOT_IN_VALIDATION
        assert tracker.update_calls == []

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
        assert AuditorDispatchLane.pending_record(
            doc.pending_chain,
            project_id=PROJECT_ID,
            task_id=TASK_ID,
        ) is None

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
        assert len(stale_calls) == 1
