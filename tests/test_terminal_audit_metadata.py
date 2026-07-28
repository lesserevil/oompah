"""Contract tests for tracker-neutral terminal-audit metadata persistence."""

from __future__ import annotations

import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any
from unittest.mock import patch

import pytest

from oompah.github_tracker import GitHubAuth, GitHubIssueTracker
from oompah.gitlab_tracker import GitLabIssueTracker
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.terminal_audit import (
    AuditAttempt,
    ContributorIdentity,
    EvidenceFingerprint,
    RequestState,
    TargetState,
    TerminalAuditRecord,
)
from oompah.terminal_audit_metadata import (
    METADATA_KEY,
    MetadataQuarantine,
    TerminalAuditMetadata,
    TerminalAuditMetadataQuarantinedError,
    TerminalAuditMetadataStore,
)


def _fingerprint() -> EvidenceFingerprint:
    return EvidenceFingerprint("a" * 64)


def _attempt(attempt_id: str = "attempt-1") -> AuditAttempt:
    return AuditAttempt(
        attempt_id=attempt_id,
        target_state=TargetState.DONE,
        evidence_fingerprint=_fingerprint(),
        request_state=RequestState.PENDING,
        requested_by=ContributorIdentity("alice", "github"),
        created_at="2026-07-28T00:00:00Z",
    )


def _record(audit_id: str = "audit-1") -> TerminalAuditRecord:
    return TerminalAuditRecord(
        audit_id=audit_id,
        project_id="proj-1",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=_fingerprint(),
        attempts=[_attempt()],
        requested_by=ContributorIdentity("alice", "github"),
        previous_state="In Validation",
        created_at="2026-07-28T00:00:00Z",
    )


class _LockStore:
    """Small in-memory stand-in for ProjectStore's per-project lock API."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def project_write_lock(self, project_id: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(project_id, threading.RLock())


class _MemoryTracker:
    """Stateful TrackerProtocol metadata slice that exposes mutation counts."""

    def __init__(self, metadata: dict[str, object] | None = None) -> None:
        self._guard = threading.Lock()
        self.metadata = copy.deepcopy(metadata or {})
        self.set_calls = 0

    def get_metadata(self, _identifier: str) -> dict[str, object]:
        with self._guard:
            return copy.deepcopy(self.metadata)

    def set_metadata_field(self, _identifier: str, key: str, value: object) -> None:
        with self._guard:
            self.set_calls += 1
            self.metadata[key] = copy.deepcopy(value)


class _GitHubMetadataClient:
    def __init__(self) -> None:
        self.body = "Human-owned body"
        self.patch_calls = 0

    def request(self, method: str, _path: str, **_kwargs: Any) -> tuple[dict[str, str], object]:
        assert method == "GET"
        return {"body": self.body}, object()

    def patch(self, _path: str, *, json: dict[str, str]) -> None:
        self.patch_calls += 1
        self.body = json["body"]


class _GitLabMetadataClient:
    def __init__(self) -> None:
        self.description = "Human-owned description"
        self.put_calls = 0

    def request(
        self, method: str, _path: str, **kwargs: Any
    ) -> tuple[dict[str, object], object]:
        if method == "PUT":
            self.put_calls += 1
            self.description = kwargs["json"]["description"]
        return {"description": self.description, "labels": []}, object()


@pytest.fixture(params=["native", "github", "gitlab"])
def tracker_adapter(request: pytest.FixtureRequest, tmp_path):
    """Return each real adapter with a stateful local metadata transport."""

    if request.param == "native":
        root = tmp_path / "native"
        root.mkdir()
        tracker = OompahMarkdownTracker(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(root),
            default_branch="main",
            git_sync=False,
        )
        identifier = tracker.create_issue("Terminal audit metadata").identifier
        return tracker, identifier
    if request.param == "github":
        tracker = GitHubIssueTracker(
            owner="example-org",
            repo="tasks",
            active_states=["Open"],
            terminal_states=["Done"],
            auth=GitHubAuth(pat="test-token"),
        )
        tracker._client = _GitHubMetadataClient()  # type: ignore[assignment]
        return tracker, "example-org/tasks#1"
    client = _GitLabMetadataClient()
    tracker = GitLabIssueTracker(
        project="group/project",
        active_states=["Open"],
        terminal_states=["Done"],
        client=client,
    )
    return tracker, "group/project#1"


class TestTerminalAuditMetadataContract:
    def test_empty_metadata_is_an_empty_document(self) -> None:
        tracker = _MemoryTracker()
        repository = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")

        assert repository.read("TASK-1") == TerminalAuditMetadata.empty()
        assert tracker.set_calls == 0

    def test_round_trips_through_every_tracker_adapter(self, tracker_adapter) -> None:
        tracker, identifier = tracker_adapter
        repository = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")
        original = TerminalAuditMetadata(
            pending_chain=[_record()], attempt_history=[_attempt()]
        )

        with patch.object(
            tracker, "set_metadata_field", wraps=tracker.set_metadata_field
        ) as set_metadata:
            assert repository.write(identifier, original) is True
            restored = repository.read(identifier)
            assert repository.write(identifier, restored) is False

        assert restored.pending_chain == original.pending_chain
        assert restored.attempt_history == original.attempt_history
        assert tracker.get_metadata(identifier)[METADATA_KEY]["version"] == 1
        assert set_metadata.call_count == 1

    def test_append_update_and_bounded_history(self) -> None:
        tracker = _MemoryTracker()
        repository = TerminalAuditMetadataStore(
            tracker, _LockStore(), "proj-1", max_attempt_history=2
        )

        repository.upsert_pending_audit("TASK-1", _record())
        repository.upsert_pending_audit("TASK-1", replace(_record(), previous_state="Open"))
        for number in range(3):
            repository.append_attempt("TASK-1", _attempt(f"attempt-{number}"))

        stored = repository.read("TASK-1")
        assert stored.pending_chain[0].previous_state == "Open"
        assert [attempt.attempt_id for attempt in stored.attempt_history] == [
            "attempt-1",
            "attempt-2",
        ]
        assert len(stored.pending_chain[0].attempts) == 1

    def test_unchanged_write_is_a_true_no_op(self) -> None:
        tracker = _MemoryTracker()
        repository = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")
        document = TerminalAuditMetadata(pending_chain=[_record()])

        assert repository.write("TASK-1", document) is True
        assert repository.write("TASK-1", repository.read("TASK-1")) is False
        assert tracker.set_calls == 1

    def test_preserves_unknown_fields_in_document_and_nested_records(self) -> None:
        raw = TerminalAuditMetadata(
            pending_chain=[_record()], unknown_fields={"future_envelope": {"keep": True}}
        ).to_dict()
        raw["pending_chain"][0]["future_record"] = "keep"
        raw["pending_chain"][0]["attempts"][0]["future_attempt"] = 7
        tracker = _MemoryTracker({METADATA_KEY: raw})
        repository = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")

        repository.upsert_pending_audit(
            "TASK-1", replace(_record(), previous_state="Open")
        )

        written = tracker.metadata[METADATA_KEY]
        assert written["future_envelope"] == {"keep": True}
        assert written["pending_chain"][0]["future_record"] == "keep"
        assert written["pending_chain"][0]["attempts"][0]["future_attempt"] == 7
        assert written["pending_chain"][0]["previous_state"] == "Open"

    def test_preserves_unknown_fields_through_every_tracker_adapter(
        self, tracker_adapter
    ) -> None:
        tracker, identifier = tracker_adapter
        raw = TerminalAuditMetadata(pending_chain=[_record()]).to_dict()
        raw["future_envelope"] = {"keep": True}
        raw["pending_chain"][0]["future_record"] = "keep"
        tracker.set_metadata_field(identifier, METADATA_KEY, raw)
        repository = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")

        repository.upsert_pending_audit(
            identifier, replace(_record(), previous_state="Open")
        )

        written = tracker.get_metadata(identifier)[METADATA_KEY]
        assert written["future_envelope"] == {"keep": True}
        assert written["pending_chain"][0]["future_record"] == "keep"
        assert written["pending_chain"][0]["previous_state"] == "Open"

    def test_concurrent_appends_are_serialized_without_lost_attempts(self) -> None:
        tracker = _MemoryTracker()
        repository = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(
                executor.map(
                    lambda number: repository.append_attempt(
                        "TASK-1", _attempt(f"attempt-{number}")
                    ),
                    range(20),
                )
            )

        stored = repository.read("TASK-1")
        assert {attempt.attempt_id for attempt in stored.attempt_history} == {
            f"attempt-{number}" for number in range(20)
        }

    def test_malformed_document_is_quarantined_without_copying_secrets(self) -> None:
        secret = "ghp_this_must_not_be_persisted"
        tracker = _MemoryTracker(
            {METADATA_KEY: {"version": "bad", "model_response": secret}}
        )
        repository = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")

        document = repository.read("TASK-1")
        persisted = tracker.metadata[METADATA_KEY]

        assert isinstance(document.quarantine, MetadataQuarantine)
        assert persisted["quarantine"]["fingerprint"]
        assert secret not in repr(persisted)
        assert tracker.set_calls == 1
        with pytest.raises(TerminalAuditMetadataQuarantinedError):
            repository.append_attempt("TASK-1", _attempt())

    def test_malformed_document_is_quarantined_by_every_tracker_adapter(
        self, tracker_adapter
    ) -> None:
        tracker, identifier = tracker_adapter
        secret = "ghp_this_must_not_be_persisted"
        tracker.set_metadata_field(
            identifier, METADATA_KEY, {"version": "bad", "model_response": secret}
        )
        repository = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")

        document = repository.read(identifier)
        persisted = tracker.get_metadata(identifier)[METADATA_KEY]

        assert document.is_quarantined
        assert secret not in repr(persisted)
        assert persisted["quarantine"]["fingerprint"]

    def test_redacts_secrets_and_model_prose_from_unknown_future_fields(self) -> None:
        secret = "Bearer very-secret-token"
        document = TerminalAuditMetadata(
            unknown_fields={
                "future": {"token": secret},
                "future_note": "full model response: " + "x" * 600,
            }
        )
        tracker = _MemoryTracker()
        repository = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")

        repository.write("TASK-1", document)
        persisted = tracker.metadata[METADATA_KEY]

        assert persisted["future"]["token"] == "[REDACTED]"
        assert persisted["future_note"] == "[REDACTED]"
        assert secret not in repr(persisted)

    def test_redacts_secrets_through_every_tracker_adapter(self, tracker_adapter) -> None:
        tracker, identifier = tracker_adapter
        secret = "Bearer very-secret-token"
        document = TerminalAuditMetadata(
            unknown_fields={
                "future": {"token": secret},
                "future_note": "full model response: " + "x" * 600,
            }
        )
        repository = TerminalAuditMetadataStore(tracker, _LockStore(), "proj-1")

        repository.write(identifier, document)
        persisted = tracker.get_metadata(identifier)[METADATA_KEY]

        assert persisted["future"]["token"] == "[REDACTED]"
        assert persisted["future_note"] == "[REDACTED]"
        assert secret not in repr(persisted)
