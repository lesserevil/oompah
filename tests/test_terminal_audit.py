"""Tests for tracker-neutral terminal-audit records and evidence."""

from dataclasses import replace

import pytest

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


def _fingerprint(**overrides: object) -> EvidenceFingerprint:
    values: dict[str, object] = {
        "requirements_text": "Ship the audit state model.",
        "project_id": "proj-1",
        "task_id": "TASK-1",
        "source_branch": "feature/TASK-1",
        "source_sha": "a" * 40,
        "target_branch": "main",
        "target_sha": "b" * 40,
        "review_id": "42",
        "review_state": "open",
        "child_audit_digests": ["child-b", "child-a"],
        "contributors": [
            ContributorIdentity("alice", "github"),
            ContributorIdentity("bob", "git"),
        ],
    }
    values.update(overrides)
    return compute_evidence_fingerprint(**values)  # type: ignore[arg-type]


def _record() -> TerminalAuditRecord:
    fingerprint = _fingerprint()
    attempt = AuditAttempt(
        attempt_id="attempt-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        request_state=RequestState.COMPLETED,
        verdict=Verdict.PASS,
        requested_by=ContributorIdentity("alice", "github"),
        created_at="2026-07-28T00:00:00Z",
        completed_at="2026-07-28T00:01:00Z",
    )
    return TerminalAuditRecord(
        audit_id="audit-1",
        project_id="proj-1",
        task_id="TASK-1",
        target_state=TargetState.DONE,
        evidence_fingerprint=fingerprint,
        attempts=[attempt],
        requested_by=ContributorIdentity("alice", "github"),
        previous_state="In Validation",
        created_at="2026-07-28T00:00:00Z",
    )


class TestSerialization:
    def test_round_trip_is_deterministic(self) -> None:
        original = _record()
        serialized = original.to_dict()
        restored = TerminalAuditRecord.from_dict(serialized)

        assert restored == original
        assert restored.to_dict() == serialized
        assert serialized["version"] == 1
        assert serialized["evidence_fingerprint"]["version"] == 1

    def test_unknown_fields_are_ignored_for_forward_compatibility(self) -> None:
        data = _record().to_dict()
        data["future_field"] = {"new": "value"}
        data["attempts"][0]["future_attempt_field"] = True
        data["evidence_fingerprint"]["future_fingerprint_field"] = 7

        restored = TerminalAuditRecord.from_dict(data)

        assert restored == _record()

    def test_legacy_optional_fields_can_be_missing(self) -> None:
        data = _record().to_dict()
        data.pop("requested_by")
        data.pop("previous_state")
        data.pop("created_at")
        data["attempts"][0].pop("requested_by")
        data["attempts"][0].pop("created_at")
        data["attempts"][0].pop("completed_at")

        restored = TerminalAuditRecord.from_dict(data)

        assert restored.requested_by is None
        assert restored.previous_state is None
        assert restored.created_at is None
        assert restored.attempts[0].requested_by is None

    def test_legacy_record_without_attempts_defaults_to_empty(self) -> None:
        data = _record().to_dict()
        data.pop("attempts")

        restored = TerminalAuditRecord.from_dict(data)

        assert restored.attempts == []

    @pytest.mark.parametrize(
        "record_type, payload, missing",
        [
            (TerminalAuditRecord, _record().to_dict(), "audit_id"),
            (AuditAttempt, _record().attempts[0].to_dict(), "attempt_id"),
            (EvidenceFingerprint, _record().evidence_fingerprint.to_dict(), "digest"),
            (ContributorIdentity, ContributorIdentity("alice").to_dict(), "identity"),
        ],
    )
    def test_required_fields_are_strict(
        self, record_type: type[object], payload: dict[str, object], missing: str
    ) -> None:
        payload.pop(missing)

        with pytest.raises(ValueError, match=missing):
            record_type.from_dict(payload)  # type: ignore[attr-defined]

    @pytest.mark.parametrize("record_type", [TerminalAuditRecord, AuditAttempt, EvidenceFingerprint])
    def test_version_is_required_and_supported(self, record_type: type[object]) -> None:
        payload = (
            _record().to_dict()
            if record_type is TerminalAuditRecord
            else _record().attempts[0].to_dict()
            if record_type is AuditAttempt
            else _record().evidence_fingerprint.to_dict()
        )
        payload.pop("version")
        with pytest.raises(ValueError, match="version"):
            record_type.from_dict(payload)  # type: ignore[attr-defined]

        payload["version"] = 99
        with pytest.raises(ValueError, match="version"):
            record_type.from_dict(payload)  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "enum_type, value",
        [
            (TargetState, "not-terminal"),
            (RequestState, "not-request"),
            (Verdict, "maybe"),
            (FailureClassification, "made-up"),
        ],
    )
    def test_unknown_enum_values_are_rejected(self, enum_type: type[object], value: str) -> None:
        with pytest.raises(ValueError):
            enum_type.from_raw(value)  # type: ignore[attr-defined]


class TestEvidenceFingerprint:
    def test_identical_evidence_has_identical_sha256(self) -> None:
        first = _fingerprint()
        second = _fingerprint(
            contributors=[
                ContributorIdentity("bob", "git"),
                ContributorIdentity("alice", "github"),
            ],
            child_audit_digests=["child-a", "child-b"],
        )

        assert first == second
        assert len(first.digest) == 64
        assert first.algorithm == "sha256"

    @pytest.mark.parametrize(
        "change",
        [
            {"requirements_text": "Ship the changed audit state model."},
            {"source_sha": "c" * 40},
            {"target_sha": "c" * 40},
            {"review_id": "43"},
            {"review_state": "merged"},
            {"child_audit_digests": ["child-a", "child-c"]},
            {"project_id": "proj-2"},
            {"task_id": "TASK-2"},
            {"source_branch": "feature/other"},
            {"target_branch": "release/1.0"},
        ],
    )
    def test_material_evidence_changes_digest(self, change: dict[str, object]) -> None:
        assert _fingerprint() != _fingerprint(**change)

    def test_requirements_whitespace_is_normalized(self) -> None:
        assert _fingerprint(requirements_text="  Ship\n\tthe audit state model. ") == _fingerprint()

    def test_fingerprint_payload_excludes_diff_credentials_and_prose(self) -> None:
        baseline = _fingerprint()
        # The public constructor has no parameters for any of these values;
        # changing unrelated local data cannot alter the digest.
        unrelated = replace(
            _record(),
            previous_state="model response: token=secret full diff follows",
        )

        assert unrelated.evidence_fingerprint == baseline
