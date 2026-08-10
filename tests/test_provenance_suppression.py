"""Tests for terminal-provenance suppression state.

These contracts cover OOMPAH-871: a task retained only as merged/archived
provenance cannot re-enter a dispatchable or validation state unless a
project owner explicitly starts a new revision.
"""

from __future__ import annotations

import copy
import threading
import time
from types import SimpleNamespace

import pytest

from oompah.provenance_suppression import (
    MARKER_VERSION,
    PROVENANCE_SUPPRESSION_KEY,
    ProvenanceGuardedTracker,
    ProvenanceControlBusyError,
    ProvenanceSuppression,
    ProvenanceSuppressionBlockedError,
    ProvenanceSuppressionError,
    RevisionAuthorization,
    authorize_new_revision,
    describe_malformed_marker,
    is_dispatch_suppressed,
    load_provenance_suppression_status,
    mark_provenance_only,
    read_provenance_suppression,
)
from oompah.terminal_audit import ContributorIdentity
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    TerminalAuditMetadataQuarantinedError,
    TerminalAuditMetadataStore,
)


# ---------------------------------------------------------------------------
# Test doubles for the tracker-facing metadata store
# ---------------------------------------------------------------------------


class _LockStore:
    """Minimal per-project lock provider matching ProjectStore's protocol."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def project_write_lock(self, project_id: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(project_id, threading.RLock())


class _MemoryTracker:
    """Stateful TrackerProtocol metadata slice used for durability checks."""

    def __init__(self, metadata: dict[str, object] | None = None) -> None:
        self._guard = threading.Lock()
        self.metadata: dict[str, object] = copy.deepcopy(metadata or {})
        self.set_calls = 0

    def get_metadata(self, _identifier: str) -> dict[str, object]:
        with self._guard:
            return copy.deepcopy(self.metadata)

    def set_metadata_field(self, _identifier: str, key: str, value: object) -> None:
        with self._guard:
            self.set_calls += 1
            self.metadata[key] = copy.deepcopy(value)


class _StatusTracker(_MemoryTracker):
    def __init__(self, metadata: dict[str, object] | None = None) -> None:
        super().__init__(metadata)
        self.updates: list[tuple[str, dict[str, object]]] = []

    def update_issue(self, identifier: str, **fields: object) -> None:
        self.updates.append((identifier, dict(fields)))

    def reopen_issue(self, identifier: str) -> None:
        self.updates.append((identifier, {"status": "Open"}))

    def mark_needs_human(
        self, identifier: str, comment: str, author: str = "oompah"
    ) -> None:
        self.updates.append(
            (
                identifier,
                {"status": "Needs Human", "comment": comment, "author": author},
            )
        )

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        self.updates.append((identifier, {"status": "Done", "reason": reason}))

    def archive_issue(self, identifier: str) -> None:
        self.updates.append((identifier, {"status": "Archived"}))


def _store(tracker: _MemoryTracker | None = None) -> TerminalAuditMetadataStore:
    tracker = tracker or _MemoryTracker()
    return TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")


def _owner(name: str = "owner") -> ContributorIdentity:
    return ContributorIdentity(identity=name, source="github")


# ---------------------------------------------------------------------------
# Data model contracts
# ---------------------------------------------------------------------------


class TestProvenanceSuppressionModel:
    def test_dict_round_trip(self) -> None:
        marker = ProvenanceSuppression(
            suppressed=True,
            authority_generation=2,
            actor=_owner(),
            reason="retained as merged provenance",
            marked_at="2026-08-07T07:00:00+00:00",
            updated_at="2026-08-07T07:10:00+00:00",
            history=(
                RevisionAuthorization(
                    kind="mark",
                    actor=_owner(),
                    reason="retained as merged provenance",
                    recorded_at="2026-08-07T07:00:00+00:00",
                    authority_generation=1,
                ),
            ),
        )

        restored = ProvenanceSuppression.from_dict(marker.to_dict())
        assert restored == marker

    @pytest.mark.parametrize("version", [99, True, 1.0])
    def test_from_dict_rejects_wrong_version(self, version: object) -> None:
        with pytest.raises(ProvenanceSuppressionError):
            ProvenanceSuppression.from_dict(
                {
                    "version": version,
                    "suppressed": True,
                    "authority_generation": 0,
                    "reason": "x",
                    "marked_at": "",
                    "updated_at": "",
                    "history": [],
                }
            )

    @pytest.mark.parametrize("version", [True, 1.0])
    def test_constructor_rejects_non_integer_version(self, version: object) -> None:
        with pytest.raises(ProvenanceSuppressionError):
            ProvenanceSuppression(version=version)  # type: ignore[arg-type]

    def test_suppressed_requires_actor(self) -> None:
        with pytest.raises(ProvenanceSuppressionError):
            ProvenanceSuppression(
                suppressed=True,
                authority_generation=0,
                actor=None,
                reason="cannot suppress without actor",
                marked_at="2026-08-07T07:00:00+00:00",
                updated_at="2026-08-07T07:00:00+00:00",
            )

    def test_present_non_suppressed_marker_requires_revision_generation(
        self,
    ) -> None:
        with pytest.raises(ProvenanceSuppressionError):
            ProvenanceSuppression(
                suppressed=False,
                authority_generation=0,
                actor=_owner(),
                reason="invalid cleared marker",
                marked_at="2026-08-07T07:00:00+00:00",
                updated_at="2026-08-07T07:00:00+00:00",
            )

    def test_revision_authorization_rejects_bad_kind(self) -> None:
        with pytest.raises(ProvenanceSuppressionError):
            RevisionAuthorization(
                kind="bogus",
                actor=_owner(),
                reason="x",
                recorded_at="2026-08-07T07:00:00+00:00",
                authority_generation=0,
            )


# ---------------------------------------------------------------------------
# Marker persistence contracts (the durable acceptance criteria)
# ---------------------------------------------------------------------------


class TestMarkProvenanceOnly:
    def test_mark_persists_marker_and_reports_change(self) -> None:
        tracker = _MemoryTracker()
        store = _store(tracker)

        result = mark_provenance_only(
            store,
            "TASK-1",
            _owner(),
            "retained as merged provenance",
        )

        assert result.changed is True
        assert result.marker.suppressed is True
        assert result.marker.authority_generation == 0

        raw = tracker.metadata[METADATA_KEY][PROVENANCE_SUPPRESSION_KEY]
        assert raw["version"] == MARKER_VERSION
        assert raw["suppressed"] is True
        assert raw["actor"]["identity"] == "owner"
        # Idempotent second call: no additional set_metadata_field write once
        # the durable marker already forbids dispatch.
        pre_calls = tracker.set_calls
        second = mark_provenance_only(
            store,
            "TASK-1",
            _owner(),
            "retained as merged provenance",
        )
        assert second.changed is False
        assert tracker.set_calls == pre_calls

    def test_marker_survives_service_restart(self) -> None:
        tracker = _MemoryTracker()
        store = _store(tracker)
        mark_provenance_only(store, "TASK-1", _owner(), "retained")

        # A restart re-instantiates the store on the same tracker payload.
        fresh_store = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")

        assert is_dispatch_suppressed(fresh_store.read("TASK-1")) is True

    def test_repeated_mark_is_idempotent(self) -> None:
        tracker = _MemoryTracker()
        store = _store(tracker)

        first = mark_provenance_only(store, "TASK-1", _owner(), "retained")
        second = mark_provenance_only(store, "TASK-1", _owner("someone-else"), "again")

        # The initial mark stays authoritative — a second marker cannot
        # silently overwrite the recorded owner.
        assert first.marker.actor == _owner()
        assert second.marker.actor == _owner()
        assert second.changed is False


class TestAuthorizeNewRevision:
    def test_new_revision_clears_suppression_and_bumps_generation(self) -> None:
        tracker = _MemoryTracker()
        store = _store(tracker)
        mark_provenance_only(store, "TASK-1", _owner(), "retained")

        outcome = authorize_new_revision(
            store, "TASK-1", _owner(), "requested a fresh revision"
        )

        assert outcome.changed is True
        assert outcome.marker.suppressed is False
        assert outcome.marker.authority_generation == 1
        history = outcome.marker.history
        assert history[-1].kind == "revise"
        assert history[-1].authority_generation == 1

    def test_authorize_bumps_generation_even_without_prior_mark(self) -> None:
        """Owner-authored revisions establish a fresh authority regardless.

        A watchdog decision bound to an earlier (missing) generation cannot
        replay after an owner explicitly touches the marker.
        """

        tracker = _MemoryTracker()
        store = _store(tracker)

        outcome = authorize_new_revision(
            store,
            "TASK-1",
            _owner(),
            "opening a follow-up",
            now="2026-08-07T08:00:00+00:00",
        )
        assert outcome.marker.authority_generation == 1
        assert outcome.marker.actor == _owner()
        assert outcome.marker.reason == "opening a follow-up"
        assert outcome.marker.marked_at == ""
        assert outcome.marker.updated_at == "2026-08-07T08:00:00+00:00"

    def test_first_mark_after_absent_revision_records_retention_time(self) -> None:
        tracker = _MemoryTracker()
        store = _store(tracker)
        authorize_new_revision(
            store,
            "TASK-1",
            _owner(),
            "opening a follow-up",
            now="2026-08-07T08:00:00+00:00",
        )

        outcome = mark_provenance_only(
            store,
            "TASK-1",
            _owner(),
            "retain completed revision",
            now="2026-08-07T09:00:00+00:00",
        )

        assert outcome.marker.authority_generation == 1
        assert outcome.marker.marked_at == "2026-08-07T09:00:00+00:00"
        assert outcome.marker.updated_at == "2026-08-07T09:00:00+00:00"
        assert [entry.kind for entry in outcome.marker.history] == [
            "revise",
            "mark",
        ]

    def test_mark_after_revision_reuses_new_generation(self) -> None:
        tracker = _MemoryTracker()
        store = _store(tracker)
        mark_provenance_only(store, "TASK-1", _owner(), "retained")
        authorize_new_revision(store, "TASK-1", _owner(), "revised")

        marker = read_provenance_suppression(store.read("TASK-1"))
        assert marker is not None
        assert marker.authority_generation == 1
        assert marker.suppressed is False

        mark_provenance_only(store, "TASK-1", _owner(), "retained again")
        marker = read_provenance_suppression(store.read("TASK-1"))
        assert marker is not None
        # A fresh mark reuses the current generation; only a revision bumps it.
        assert marker.authority_generation == 1
        assert marker.suppressed is True


class TestSuppressionStatus:
    def test_missing_marker_is_not_suppressed(self) -> None:
        status = load_provenance_suppression_status(_store(), "TASK-1")

        assert status.suppressed is False
        assert status.malformed is False
        assert status.marker is None
        assert status.authority_generation == 0

    def test_unconfigured_metadata_surface_is_permissive(self) -> None:
        """Legacy adapters without mapping metadata must not freeze all work."""

        class _LegacyTracker:
            def get_metadata(self, _identifier: str) -> object:
                return object()

        status = load_provenance_suppression_status(
            TerminalAuditMetadataStore(_LegacyTracker(), _LockStore(), "proj-1"),
            "TASK-1",
        )

        assert status.suppressed is False
        assert status.malformed is False
        assert status.marker is None

    @pytest.mark.parametrize("version", ["bad", True, 1.0])
    def test_malformed_marker_reports_fail_closed(self, version: object) -> None:
        tracker = _MemoryTracker(
            {
                METADATA_KEY: {
                    "version": 1,
                    "pending_chain": [],
                    "attempt_history": [],
                    PROVENANCE_SUPPRESSION_KEY: {"version": version},
                }
            }
        )
        status = load_provenance_suppression_status(_store(tracker), "TASK-1")

        assert status.malformed is True
        # Fail-closed: a malformed marker must forbid reopen/dispatch even
        # though the caller also emits an operator alert.
        assert status.suppressed is True
        assert "malformed" in status.malformed_reason.lower() or "version" in status.malformed_reason.lower()

    @pytest.mark.parametrize("marker", [None, "invalid", [], True])
    def test_present_non_mapping_marker_reports_fail_closed(
        self, marker: object
    ) -> None:
        tracker = _MemoryTracker(
            {
                METADATA_KEY: {
                    "version": 1,
                    "pending_chain": [],
                    "attempt_history": [],
                    PROVENANCE_SUPPRESSION_KEY: marker,
                }
            }
        )

        status = load_provenance_suppression_status(_store(tracker), "TASK-1")

        assert status.suppressed is True
        assert status.malformed is True
        assert status.marker is None

    def test_quarantined_metadata_is_treated_as_suppressed(self) -> None:
        """A quarantined envelope must not silently permit a reopen."""

        tracker = _MemoryTracker(
            {METADATA_KEY: {"version": "bad", "model_response": "leak-me"}}
        )
        store = _store(tracker)
        # Quarantine happens on the first read.
        assert store.read("TASK-1").is_quarantined is True

        status = load_provenance_suppression_status(store, "TASK-1")
        assert status.suppressed is True
        assert status.malformed is True
        assert "quarantined" in status.malformed_reason.lower()

    def test_describe_malformed_marker_never_echoes_payload(self) -> None:
        status = load_provenance_suppression_status(
            _store(
                _MemoryTracker(
                    {
                        METADATA_KEY: {
                            "version": 1,
                            "pending_chain": [],
                            "attempt_history": [],
                            PROVENANCE_SUPPRESSION_KEY: {
                                "version": 1,
                                "suppressed": "yes-please",  # invalid: must be bool
                                "authority_generation": 0,
                                "reason": "x",
                                "marked_at": "",
                                "updated_at": "",
                                "history": [],
                            },
                        }
                    }
                )
            ),
            "TASK-1",
        )
        alert = describe_malformed_marker(status, "TASK-1")

        assert "TASK-1" in alert
        assert "operator" in alert.lower()
        # The alert must never quote the malformed payload verbatim.
        assert "yes-please" not in alert


class TestSuppressionWithConcurrentCoordinatorState:
    def test_marker_coexists_with_pending_audit_chain_and_history(self) -> None:
        """The marker is stored beside pending_chain/attempt_history entries.

        This proves the durable envelope round-trips through the same
        metadata store used by every terminal-audit coordinator path
        without losing the marker or the audit state.
        """
        from dataclasses import replace
        from oompah.terminal_audit import (
            AuditAttempt,
            EvidenceFingerprint,
            RequestState,
            TargetState,
            TerminalAuditRecord,
        )

        fingerprint = EvidenceFingerprint("a" * 64)
        attempt = AuditAttempt(
            attempt_id="attempt-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            request_state=RequestState.PENDING,
            requested_by=_owner(),
            created_at="2026-08-07T07:00:00+00:00",
        )
        record = TerminalAuditRecord(
            audit_id="audit-1",
            project_id="proj-1",
            task_id="TASK-1",
            target_state=TargetState.DONE,
            evidence_fingerprint=fingerprint,
            attempts=[attempt],
            requested_by=_owner(),
            previous_state="In Validation",
            created_at="2026-08-07T07:00:00+00:00",
        )
        tracker = _MemoryTracker()
        store = _store(tracker)
        store.upsert_pending_audit("TASK-1", record)

        mark_provenance_only(store, "TASK-1", _owner(), "retained")

        # After a full round-trip the audit envelope still contains both.
        document = store.read("TASK-1")
        assert document.pending_chain[0].audit_id == "audit-1"
        marker = read_provenance_suppression(document)
        assert marker is not None
        assert marker.suppressed is True

        # A subsequent audit-chain mutation must not clobber the marker.
        store.upsert_pending_audit(
            "TASK-1", replace(record, previous_state="Open")
        )
        document = store.read("TASK-1")
        marker = read_provenance_suppression(document)
        assert marker is not None
        assert marker.suppressed is True


# ---------------------------------------------------------------------------
# Watchdog / restart-recovery contracts modelled at the pure-decision layer
# ---------------------------------------------------------------------------


class TestSuppressionForbidsReopenAcrossTicks:
    def test_marker_survives_repeated_reads_across_ticks(self) -> None:
        tracker = _MemoryTracker()
        store = _store(tracker)
        mark_provenance_only(store, "TASK-1", _owner(), "retained")

        # Repeated maintenance ticks re-fetch the document.  The marker
        # must stay authoritative — no silent clearing on read.
        for _ in range(5):
            assert is_dispatch_suppressed(store.read("TASK-1")) is True

    def test_stale_branch_and_review_observations_cannot_reopen(self) -> None:
        """Simulated watchdog: only a durable owner action can clear."""

        tracker = _MemoryTracker()
        store = _store(tracker)
        mark_provenance_only(store, "TASK-1", _owner(), "retained")

        # A watchdog-facing decision layer inspects the marker before
        # ever asking to reopen.  The stale review observation cannot
        # touch the marker on its own.
        pre = tracker.set_calls
        assert is_dispatch_suppressed(store.read("TASK-1")) is True
        assert tracker.set_calls == pre

    def test_owner_revision_enables_dispatch(self) -> None:
        tracker = _MemoryTracker()
        store = _store(tracker)
        mark_provenance_only(store, "TASK-1", _owner(), "retained")
        authorize_new_revision(store, "TASK-1", _owner(), "requested new revision")

        assert is_dispatch_suppressed(store.read("TASK-1")) is False


# ---------------------------------------------------------------------------
# Mutation guard rails
# ---------------------------------------------------------------------------


class TestMutationGuards:
    def test_mark_rejects_empty_reason(self) -> None:
        with pytest.raises(ValueError):
            mark_provenance_only(_store(), "TASK-1", _owner(), "  ")

    def test_authorize_rejects_bad_actor_type(self) -> None:
        with pytest.raises(TypeError):
            authorize_new_revision(_store(), "TASK-1", "owner", "text")  # type: ignore[arg-type]

    def test_mark_after_malformed_marker_raises(self) -> None:
        tracker = _MemoryTracker(
            {
                METADATA_KEY: {
                    "version": 1,
                    "pending_chain": [],
                    "attempt_history": [],
                    PROVENANCE_SUPPRESSION_KEY: {"version": 99},
                }
            }
        )
        store = _store(tracker)
        with pytest.raises(ProvenanceSuppressionError):
            mark_provenance_only(store, "TASK-1", _owner(), "retained")

    def test_authorize_after_malformed_marker_raises(self) -> None:
        tracker = _MemoryTracker(
            {
                METADATA_KEY: {
                    "version": 1,
                    "pending_chain": [],
                    "attempt_history": [],
                    PROVENANCE_SUPPRESSION_KEY: {"version": 99},
                }
            }
        )
        store = _store(tracker)
        with pytest.raises(ProvenanceSuppressionError):
            authorize_new_revision(store, "TASK-1", _owner(), "revise")

    def test_authorize_on_quarantined_document_raises(self) -> None:
        tracker = _MemoryTracker(
            {METADATA_KEY: {"version": "bad", "leak": "secret"}}
        )
        store = _store(tracker)
        # Trigger quarantine
        assert store.read("TASK-1").is_quarantined
        with pytest.raises(TerminalAuditMetadataQuarantinedError):
            authorize_new_revision(store, "TASK-1", _owner(), "revise")


class TestProvenanceGuardedTracker:
    def _guarded(
        self, tracker: _StatusTracker, locks: _LockStore
    ) -> ProvenanceGuardedTracker:
        return ProvenanceGuardedTracker(tracker, locks, "proj-1")

    def test_central_fence_blocks_every_nonterminal_status_surface(self) -> None:
        tracker = _StatusTracker()
        locks = _LockStore()
        store = TerminalAuditMetadataStore(tracker, locks, "proj-1")
        mark_provenance_only(store, "TASK-1", _owner(), "retained")
        guarded = self._guarded(tracker, locks)

        with pytest.raises(ProvenanceSuppressionBlockedError):
            guarded.update_issue("TASK-1", status="Open")
        with pytest.raises(ProvenanceSuppressionBlockedError):
            guarded.reopen_issue("TASK-1")
        with pytest.raises(ProvenanceSuppressionBlockedError):
            guarded.mark_needs_human("TASK-1", "operator needed")

        assert tracker.updates == []

    def test_non_status_metadata_remains_available_but_all_status_is_frozen(self) -> None:
        tracker = _StatusTracker()
        locks = _LockStore()
        store = TerminalAuditMetadataStore(tracker, locks, "proj-1")
        mark_provenance_only(store, "TASK-1", _owner(), "retained")
        guarded = self._guarded(tracker, locks)

        guarded.update_issue("TASK-1", title="Historical record")
        with pytest.raises(ProvenanceSuppressionBlockedError):
            guarded.update_issue("TASK-1", status="Merged")
        with pytest.raises(ProvenanceSuppressionBlockedError):
            guarded.close_issue("TASK-1", reason="already complete")
        with pytest.raises(ProvenanceSuppressionBlockedError):
            guarded.archive_issue("TASK-1")

        assert tracker.updates == [
            ("TASK-1", {"title": "Historical record"}),
        ]

    def test_owner_revision_release_allows_open_and_survives_restart(self) -> None:
        tracker = _StatusTracker()
        locks = _LockStore()
        store = TerminalAuditMetadataStore(tracker, locks, "proj-1")
        mark_provenance_only(store, "TASK-1", _owner(), "retained")

        first = self._guarded(tracker, locks)
        with pytest.raises(ProvenanceSuppressionBlockedError):
            first.update_issue("TASK-1", status="Open")

        authorize_new_revision(store, "TASK-1", _owner(), "new revision")
        restarted = self._guarded(tracker, locks)
        restarted.update_issue("TASK-1", status="Open")

        assert tracker.updates == [("TASK-1", {"status": "Open"})]

    def test_owner_control_lock_timeout_is_bounded_and_observable(self) -> None:
        tracker = _StatusTracker()
        locks = _LockStore()
        observations: list[dict[str, object]] = []
        guarded = ProvenanceGuardedTracker(
            tracker,
            locks,
            "proj-1",
            control_lock_timeout_seconds=0.02,
            control_lock_observer=lambda project_id, **values: observations.append(
                {"project_id": project_id, **values}
            ),
        )
        held = threading.Event()
        release = threading.Event()

        def holder() -> None:
            with locks.project_write_lock("proj-1"):
                held.set()
                release.wait(timeout=2)

        thread = threading.Thread(target=holder)
        thread.start()
        assert held.wait(timeout=1)
        started = time.monotonic()
        try:
            with pytest.raises(ProvenanceControlBusyError):
                with guarded.owner_control_lock():
                    pytest.fail("busy control lock unexpectedly acquired")
        finally:
            release.set()
            thread.join(timeout=1)

        assert time.monotonic() - started < 0.5
        assert observations[-1]["timed_out"] is True
        assert tracker.updates == []

    def test_owner_revision_releases_project_lock_for_status_transition(self) -> None:
        class _RevisionTracker(_StatusTracker):
            def __init__(self) -> None:
                super().__init__()
                self.issue = SimpleNamespace(state="Merged")

            def fetch_issue_detail(self, _identifier: str) -> object:
                return self.issue

        tracker = _RevisionTracker()
        locks = _LockStore()
        store = TerminalAuditMetadataStore(tracker, locks, "proj-1")
        mark_provenance_only(store, "TASK-1", _owner(), "retained")
        guarded = self._guarded(tracker, locks)
        transition_lock_acquired: list[bool] = []

        def _transition(issue: object, _status: str, **_fields: object) -> None:
            project_lock = locks.project_write_lock("proj-1")

            def _acquire_from_transition_thread() -> None:
                acquired = project_lock.acquire(timeout=1)
                transition_lock_acquired.append(acquired)
                if acquired:
                    project_lock.release()

            worker = threading.Thread(target=_acquire_from_transition_thread)
            worker.start()
            worker.join(timeout=2)
            assert transition_lock_acquired == [True]
            # The durable fence stays active until the Open transition has
            # committed and the facade reacquires the project lock.
            assert load_provenance_suppression_status(
                store, "TASK-1"
            ).suppressed is True
            issue.state = "Open"  # type: ignore[attr-defined]

        result = guarded.authorize_owner_revision(
            "TASK-1",
            _owner(),
            "new revision",
            status_transition=_transition,
        )

        assert result.marker.suppressed is False
        assert result.marker.authority_generation == 1

    def test_unreadable_metadata_fails_closed_without_payload(self) -> None:
        class _UnreadableTracker(_StatusTracker):
            def get_metadata(self, _identifier: str) -> dict[str, object]:
                raise RuntimeError("secret-payload-must-not-escape")

        tracker = _UnreadableTracker()
        guarded = self._guarded(tracker, _LockStore())

        with pytest.raises(ProvenanceSuppressionBlockedError) as caught:
            guarded.update_issue("TASK-1", status="Open")

        assert "secret-payload-must-not-escape" not in str(caught.value)
        assert tracker.updates == []

    def test_unsupported_version_is_sanitized(self) -> None:
        tracker = _StatusTracker(
            {
                METADATA_KEY: {
                    "version": 1,
                    "pending_chain": [],
                    "attempt_history": [],
                    PROVENANCE_SUPPRESSION_KEY: {
                        "version": "secret-version-value",
                    },
                }
            }
        )
        status = load_provenance_suppression_status(
            TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1"),
            "TASK-1",
        )
        alert = describe_malformed_marker(status, "TASK-1")

        assert status.malformed is True
        assert "secret-version-value" not in status.malformed_reason
        assert "secret-version-value" not in alert
