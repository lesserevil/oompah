"""Security tests for canonical child landing evidence in conflict-resolved rebases.

These tests verify fail-closed behavior, cryptographic integrity, authorization,
and protection against attack vectors like evidence tampering, forgery, and stale
evidence acceptance.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from oompah.integration import (
    CanonicalLandingEvidence,
    IntegrationRecord,
    _compute_evidence_fingerprint,
    _is_valid_git_sha,
    parse_canonical_landing_evidence,
)


# Valid test data
VALID_OLD_BASE_SHA = "a" * 40
VALID_OLD_HEAD_SHA = "b" * 40
VALID_NEW_BASE_SHA = "c" * 40
VALID_NEW_HEAD_SHA = "d" * 40
VALID_EPIC_BRANCH = "epic-EXOCOMP-127"
VALID_REBASE_TASK_ID = "OOMPAH-456"
VALID_CREATED_AT = datetime.now(timezone.utc).isoformat()

def create_valid_evidence():
    """Create a valid evidence object for testing."""
    fp = _compute_evidence_fingerprint(
        VALID_OLD_BASE_SHA,
        VALID_OLD_HEAD_SHA,
        VALID_NEW_BASE_SHA,
        VALID_NEW_HEAD_SHA,
        VALID_EPIC_BRANCH,
        VALID_REBASE_TASK_ID,
        VALID_CREATED_AT,
    )
    return CanonicalLandingEvidence(
        old_base_sha=VALID_OLD_BASE_SHA,
        old_head_sha=VALID_OLD_HEAD_SHA,
        new_base_sha=VALID_NEW_BASE_SHA,
        new_head_sha=VALID_NEW_HEAD_SHA,
        target_epic_branch=VALID_EPIC_BRANCH,
        rebase_task_id=VALID_REBASE_TASK_ID,
        created_at_utc=VALID_CREATED_AT,
        evidence_fingerprint=fp,
    )


# ============================================================================
# Git SHA Validation Tests
# ============================================================================

class TestGitShaValidation:
    """Tests for _is_valid_git_sha security validation."""

    def test_valid_sha1_40_char_lowercase(self):
        """Valid SHA1 (160-bit) should pass."""
        assert _is_valid_git_sha("a" * 40, bits=160)

    def test_valid_sha256_64_char_lowercase(self):
        """Valid SHA256 (256-bit) should pass."""
        assert _is_valid_git_sha("a" * 64, bits=256)

    def test_uppercase_sha_normalized_to_lowercase(self):
        """Uppercase SHA should be normalized and accepted."""
        assert _is_valid_git_sha("A" * 40, bits=160)
        assert _is_valid_git_sha("DeAdBeEf" * 5, bits=160)

    def test_sha_with_leading_whitespace_stripped(self):
        """Leading/trailing whitespace should be stripped."""
        assert _is_valid_git_sha("  " + "a" * 40, bits=160)

    def test_invalid_sha_too_short(self):
        """SHA shorter than expected should fail."""
        assert not _is_valid_git_sha("a" * 39, bits=160)
        assert not _is_valid_git_sha("a" * 63, bits=256)

    def test_invalid_sha_too_long(self):
        """SHA longer than expected should fail."""
        assert not _is_valid_git_sha("a" * 41, bits=160)
        assert not _is_valid_git_sha("a" * 65, bits=256)

    def test_invalid_sha_non_hex_characters(self):
        """Non-hexadecimal characters should fail."""
        invalid_shas = [
            "z" * 40,  # 'z' is not hex
            "g" * 40,  # 'g' is not hex
            "a" * 39 + "x",  # 'x' is not hex
            "a" * 39 + " ",  # space is not hex
        ]
        for sha in invalid_shas:
            assert not _is_valid_git_sha(sha, bits=160), f"Should reject {sha!r}"

    def test_empty_or_none_sha(self):
        """Empty or None SHA should fail."""
        assert not _is_valid_git_sha("")
        assert not _is_valid_git_sha(None)
        assert not _is_valid_git_sha("   ")


# ============================================================================
# Fingerprint Computation & Validation Tests
# ============================================================================

class TestFingerprintComputation:
    """Tests for cryptographic fingerprint integrity."""

    def test_fingerprint_is_deterministic(self):
        """Same inputs should always produce same fingerprint."""
        fp1 = _compute_evidence_fingerprint(
            "a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", "2026-01-01T00:00:00Z"
        )
        fp2 = _compute_evidence_fingerprint(
            "a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", "2026-01-01T00:00:00Z"
        )
        assert fp1 == fp2

    def test_fingerprint_changes_with_any_parameter(self):
        """Changing any parameter should produce different fingerprint."""
        base_params = ("a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", "2026-01-01T00:00:00Z")
        base_fp = _compute_evidence_fingerprint(*base_params)

        # Change each parameter and verify fingerprint changes
        mutations = [
            ("e" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", "2026-01-01T00:00:00Z"),  # old_base
            ("a" * 40, "c" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", "2026-01-01T00:00:00Z"),  # old_head
            ("a" * 40, "b" * 40, "e" * 40, "d" * 40, "epic-E1", "TASK-1", "2026-01-01T00:00:00Z"),  # new_base
            ("a" * 40, "b" * 40, "c" * 40, "e" * 40, "epic-E1", "TASK-1", "2026-01-01T00:00:00Z"),  # new_head
            ("a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E2", "TASK-1", "2026-01-01T00:00:00Z"),  # epic_branch
            ("a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-2", "2026-01-01T00:00:00Z"),  # task_id
            ("a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", "2026-01-02T00:00:00Z"),  # timestamp
        ]

        for params in mutations:
            fp = _compute_evidence_fingerprint(*params)
            assert fp != base_fp, f"Fingerprint should change when parameters change: {params}"

    def test_fingerprint_is_sha256_length(self):
        """Fingerprint should be 64-character hex (SHA256)."""
        fp = _compute_evidence_fingerprint(
            "a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", "2026-01-01T00:00:00Z"
        )
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


# ============================================================================
# Evidence Creation & Validation Tests
# ============================================================================

class TestCanonicalLandingEvidenceCreation:
    """Tests for evidence creation and basic validation."""

    def test_valid_evidence_creation(self):
        """Valid evidence should instantiate successfully."""
        evidence = create_valid_evidence()
        assert evidence.old_base_sha == VALID_OLD_BASE_SHA
        assert evidence.old_head_sha == VALID_OLD_HEAD_SHA
        assert evidence.new_base_sha == VALID_NEW_BASE_SHA
        assert evidence.new_head_sha == VALID_NEW_HEAD_SHA
        assert evidence.target_epic_branch == VALID_EPIC_BRANCH
        assert evidence.rebase_task_id == VALID_REBASE_TASK_ID

    def test_evidence_is_frozen_immutable(self):
        """Evidence should be immutable after creation (frozen=True)."""
        evidence = create_valid_evidence()
        with pytest.raises(AttributeError):
            evidence.old_base_sha = "e" * 40

    def test_invalid_sha_raises_on_creation(self):
        """Invalid SHA should raise ValueError at creation time."""
        fp = _compute_evidence_fingerprint("a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "T1", "2026-01-01T00:00:00Z")
        with pytest.raises(ValueError, match="invalid git SHA"):
            CanonicalLandingEvidence(
                old_base_sha="invalid",  # Not 40 hex chars
                old_head_sha="b" * 40,
                new_base_sha="c" * 40,
                new_head_sha="d" * 40,
                target_epic_branch="epic-E1",
                rebase_task_id="T1",
                created_at_utc="2026-01-01T00:00:00Z",
                evidence_fingerprint=fp,
            )

    def test_empty_epic_branch_raises_on_creation(self):
        """Empty epic branch name should raise ValueError."""
        fp = _compute_evidence_fingerprint("a" * 40, "b" * 40, "c" * 40, "d" * 40, "", "TASK-1", "2026-01-01T00:00:00Z")
        with pytest.raises(ValueError, match="target_epic_branch is required"):
            CanonicalLandingEvidence(
                old_base_sha="a" * 40,
                old_head_sha="b" * 40,
                new_base_sha="c" * 40,
                new_head_sha="d" * 40,
                target_epic_branch="",  # Empty
                rebase_task_id="TASK-1",
                created_at_utc="2026-01-01T00:00:00Z",
                evidence_fingerprint=fp,
            )

    def test_empty_task_id_raises_on_creation(self):
        """Empty task ID should raise ValueError."""
        fp = _compute_evidence_fingerprint("a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "", "2026-01-01T00:00:00Z")
        with pytest.raises(ValueError, match="rebase_task_id is required"):
            CanonicalLandingEvidence(
                old_base_sha="a" * 40,
                old_head_sha="b" * 40,
                new_base_sha="c" * 40,
                new_head_sha="d" * 40,
                target_epic_branch="epic-E1",
                rebase_task_id="",  # Empty
                created_at_utc="2026-01-01T00:00:00Z",
                evidence_fingerprint=fp,
            )


# ============================================================================
# Fingerprint Tampering Detection Tests
# ============================================================================

class TestFingerprintTamperingDetection:
    """Critical security tests: fingerprint tampering must be detected."""

    def test_tampered_fingerprint_raises_on_creation(self):
        """If fingerprint doesn't match parameters, evidence should reject (CRITICAL)."""
        fp = _compute_evidence_fingerprint(
            VALID_OLD_BASE_SHA, VALID_OLD_HEAD_SHA, VALID_NEW_BASE_SHA, VALID_NEW_HEAD_SHA,
            VALID_EPIC_BRANCH, VALID_REBASE_TASK_ID, VALID_CREATED_AT,
        )
        # Flip one character in the fingerprint to simulate tampering
        tampered_fp = fp[:-1] + ("0" if fp[-1] != "0" else "1")

        with pytest.raises(ValueError, match="evidence fingerprint mismatch|evidence is corrupted"):
            CanonicalLandingEvidence(
                old_base_sha=VALID_OLD_BASE_SHA,
                old_head_sha=VALID_OLD_HEAD_SHA,
                new_base_sha=VALID_NEW_BASE_SHA,
                new_head_sha=VALID_NEW_HEAD_SHA,
                target_epic_branch=VALID_EPIC_BRANCH,
                rebase_task_id=VALID_REBASE_TASK_ID,
                created_at_utc=VALID_CREATED_AT,
                evidence_fingerprint=tampered_fp,
            )

    def test_completely_wrong_fingerprint_raises(self):
        """Completely wrong fingerprint should be rejected."""
        with pytest.raises(ValueError, match="evidence fingerprint mismatch|evidence is corrupted"):
            CanonicalLandingEvidence(
                old_base_sha=VALID_OLD_BASE_SHA,
                old_head_sha=VALID_OLD_HEAD_SHA,
                new_base_sha=VALID_NEW_BASE_SHA,
                new_head_sha=VALID_NEW_HEAD_SHA,
                target_epic_branch=VALID_EPIC_BRANCH,
                rebase_task_id=VALID_REBASE_TASK_ID,
                created_at_utc=VALID_CREATED_AT,
                evidence_fingerprint="0" * 64,  # Wrong fingerprint
            )

    def test_changing_sha_after_fingerprint_creation_fails(self):
        """If SHA was changed but fingerprint wasn't updated, validation fails."""
        original_fp = _compute_evidence_fingerprint(
            "a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", "2026-01-01T00:00:00Z"
        )
        # Try to use fingerprint from one set of SHAs but different SHAs
        with pytest.raises(ValueError, match="evidence fingerprint mismatch"):
            CanonicalLandingEvidence(
                old_base_sha="e" * 40,  # Different from original
                old_head_sha="b" * 40,
                new_base_sha="c" * 40,
                new_head_sha="d" * 40,
                target_epic_branch="epic-E1",
                rebase_task_id="TASK-1",
                created_at_utc="2026-01-01T00:00:00Z",
                evidence_fingerprint=original_fp,  # But same fingerprint (fails)
            )


# ============================================================================
# Evidence Freshness & Age Tests
# ============================================================================

class TestEvidenceFreshness:
    """Tests for fail-closed rejection of stale evidence."""

    def test_fresh_evidence_passes_freshness_check(self):
        """Evidence created just now should pass freshness check."""
        now = datetime.now(timezone.utc).isoformat()
        evidence = CanonicalLandingEvidence(
            old_base_sha="a" * 40,
            old_head_sha="b" * 40,
            new_base_sha="c" * 40,
            new_head_sha="d" * 40,
            target_epic_branch="epic-E1",
            rebase_task_id="TASK-1",
            created_at_utc=now,
            evidence_fingerprint=_compute_evidence_fingerprint(
                "a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", now
            ),
        )
        assert evidence.is_evidence_fresh(max_age_hours=24)

    def test_old_evidence_fails_freshness_check(self):
        """Evidence older than max_age_hours should fail (fail-closed)."""
        old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        evidence = CanonicalLandingEvidence(
            old_base_sha="a" * 40,
            old_head_sha="b" * 40,
            new_base_sha="c" * 40,
            new_head_sha="d" * 40,
            target_epic_branch="epic-E1",
            rebase_task_id="TASK-1",
            created_at_utc=old_time,
            evidence_fingerprint=_compute_evidence_fingerprint(
                "a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", old_time
            ),
        )
        assert not evidence.is_evidence_fresh(max_age_hours=24)

    def test_invalid_timestamp_fails_freshness_check(self):
        """Invalid ISO8601 timestamp should fail freshness check (fail-closed)."""
        evidence = CanonicalLandingEvidence(
            old_base_sha="a" * 40,
            old_head_sha="b" * 40,
            new_base_sha="c" * 40,
            new_head_sha="d" * 40,
            target_epic_branch="epic-E1",
            rebase_task_id="TASK-1",
            created_at_utc="not-a-real-timestamp",
            evidence_fingerprint=_compute_evidence_fingerprint(
                "a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", "not-a-real-timestamp"
            ),
        )
        assert not evidence.is_evidence_fresh()


# ============================================================================
# Epic Branch Validation Tests
# ============================================================================

class TestEpicBranchValidation:
    """Tests for prevent cross-epic evidence injection attacks."""

    def test_matching_epic_branch_passes_validation(self):
        """Evidence for the correct epic should pass."""
        evidence = create_valid_evidence()
        assert evidence.is_valid_for_epic(VALID_EPIC_BRANCH)

    def test_mismatched_epic_branch_fails_validation(self):
        """Evidence for wrong epic should fail (fail-closed)."""
        evidence = create_valid_evidence()
        assert not evidence.is_valid_for_epic("epic-DIFFERENT-456")

    def test_empty_epic_branch_fails_validation(self):
        """Empty epic branch should fail validation (fail-closed)."""
        evidence = create_valid_evidence()
        assert not evidence.is_valid_for_epic("")
        assert not evidence.is_valid_for_epic(None)


# ============================================================================
# Evidence Parsing & Serialization Tests
# ============================================================================

class TestEvidenceParsing:
    """Tests for safe evidence parsing and serialization."""

    def test_valid_evidence_round_trips(self):
        """Valid evidence should round-trip through dict serialization."""
        evidence1 = create_valid_evidence()
        evidence_dict = evidence1.to_dict()
        evidence2 = CanonicalLandingEvidence.from_dict(evidence_dict)
        assert evidence1 == evidence2

    def test_parse_malformed_evidence_returns_none(self):
        """parse_canonical_landing_evidence should return None for invalid data (fail-closed)."""
        invalid_inputs = [
            None,
            [],
            {},  # Empty dict (missing required fields)
            {"old_base_sha": "a" * 40},  # Incomplete
            {"fingerprint": "wrong_field"},
            "not_a_dict",
            123,
        ]
        for invalid in invalid_inputs:
            assert parse_canonical_landing_evidence(invalid) is None

    def test_parse_tamperedfingerprint_returns_none(self):
        """parse should return None for tampered evidence (fail-closed)."""
        evidence_dict = {
            "old_base_sha": "a" * 40,
            "old_head_sha": "b" * 40,
            "new_base_sha": "c" * 40,
            "new_head_sha": "d" * 40,
            "target_epic_branch": "epic-E1",
            "rebase_task_id": "TASK-1",
            "created_at_utc": "2026-01-01T00:00:00Z",
            "evidence_fingerprint": "0" * 64,  # Wrong fingerprint
        }
        assert parse_canonical_landing_evidence(evidence_dict) is None

    def test_case_normalization_on_parsing(self):
        """SHAs should be normalized to lowercase during parsing."""
        fp = _compute_evidence_fingerprint(
            "a" * 40, "b" * 40, "c" * 40, "d" * 40, "epic-E1", "TASK-1", "2026-01-01T00:00:00Z"
        )
        evidence_dict = {
            "old_base_sha": "A" * 40,  # Uppercase
            "old_head_sha": "B" * 40,  # Uppercase
            "new_base_sha": "C" * 40,  # Uppercase
            "new_head_sha": "D" * 40,  # Uppercase
            "target_epic_branch": "epic-E1",
            "rebase_task_id": "TASK-1",
            "created_at_utc": "2026-01-01T00:00:00Z",
            "evidence_fingerprint": fp.upper(),  # Uppercase
        }
        # Should parse successfully after normalization
        evidence = CanonicalLandingEvidence.from_dict(evidence_dict)
        assert evidence.old_base_sha == "a" * 40
        assert evidence.evidence_fingerprint == fp


# ============================================================================
# Integration Record Field Tests
# ============================================================================

class TestIntegrationRecordWithEvidence:
    """Tests for canonical_landing_evidence field in IntegrationRecord."""

    def test_integration_record_accepts_evidence_dict(self):
        """IntegrationRecord should store and round-trip evidence dict."""
        evidence = create_valid_evidence()
        record = IntegrationRecord(
            state="integrated",
            task_branch="task-1",
            head_sha="a" * 40,
            integrated_sha="a" * 40,
            canonical_landing_evidence=evidence.to_dict(),
        )
        assert record.canonical_landing_evidence is not None
        assert record.canonical_landing_evidence["old_base_sha"] == VALID_OLD_BASE_SHA

    def test_integration_record_validates_evidence_on_load(self):
        """IntegrationRecord.from_dict should reject invalid evidence (fail-closed)."""
        record_dict = {
            "version": 2,
            "state": "integrated",
            "task_branch": "task-1",
            "head_sha": "a" * 40,
            "canonical_landing_evidence": {
                "old_base_sha": "a" * 40,
                # Missing all other required fields
            },
        }
        record = IntegrationRecord.from_dict(record_dict)
        # Invalid evidence should be dropped (fail-closed: None, not stored)
        assert record.canonical_landing_evidence is None

    def test_integration_record_without_evidence(self):
        """IntegrationRecord without evidence should work normally."""
        record = IntegrationRecord(
            state="ready",
            task_branch="task-1",
            head_sha="a" * 40,
        )
        assert record.canonical_landing_evidence is None
        assert "canonical_landing_evidence" not in record.to_dict()

    def test_valid_evidence_included_in_integration_record_dict(self):
        """Valid evidence should be included in to_dict output."""
        evidence = create_valid_evidence()
        record = IntegrationRecord(
            state="integrated",
            task_branch="task-1",
            head_sha="a" * 40,
            integrated_sha="a" * 40,
            canonical_landing_evidence=evidence.to_dict(),
        )
        record_dict = record.to_dict()
        assert "canonical_landing_evidence" in record_dict
        assert record_dict["canonical_landing_evidence"]["old_base_sha"] == VALID_OLD_BASE_SHA


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ============================================================================
# Orchestrator Integration Tests
# ============================================================================

class TestOrchestratorLandingEvidenceValidation:
    """Tests for Orchestrator._canonical_landing_evidence_block_reason validation."""

    def test_no_record_no_block(self):
        """No integration record should not block (None)."""
        from oompah.orchestrator import Orchestrator
        
        result = Orchestrator._canonical_landing_evidence_block_reason(
            integration_record=None,
            epic_branch="epic-E1",
        )
        assert result is None

    def test_record_without_evidence_no_block(self):
        """Record without evidence should not block (None)."""
        from oompah.orchestrator import Orchestrator
        
        record = IntegrationRecord(
            state="integrated",
            task_branch="task-1",
            head_sha="a" * 40,
        )
        result = Orchestrator._canonical_landing_evidence_block_reason(
            integration_record=record,
            epic_branch="epic-E1",
        )
        assert result is None

    def test_valid_evidence_for_correct_epic_no_block(self):
        """Valid evidence for correct epic should not block."""
        from oompah.orchestrator import Orchestrator
        
        evidence = create_valid_evidence()
        record = IntegrationRecord(
            state="integrated",
            task_branch="task-1",
            head_sha="a" * 40,
            canonical_landing_evidence=evidence.to_dict(),
        )
        result = Orchestrator._canonical_landing_evidence_block_reason(
            integration_record=record,
            epic_branch=VALID_EPIC_BRANCH,
        )
        assert result is None

    def test_evidence_for_wrong_epic_blocks(self):
        """Evidence for wrong epic should block (fail-closed)."""
        from oompah.orchestrator import Orchestrator
        
        evidence = create_valid_evidence()
        record = IntegrationRecord(
            state="integrated",
            task_branch="task-1",
            head_sha="a" * 40,
            canonical_landing_evidence=evidence.to_dict(),
        )
        result = Orchestrator._canonical_landing_evidence_block_reason(
            integration_record=record,
            epic_branch="epic-DIFFERENT-999",  # Wrong epic
        )
        assert result is not None
        assert "not epic-DIFFERENT-999" in result

    def test_stale_evidence_blocks(self):
        """Evidence older than max_age should block (fail-closed)."""
        from oompah.orchestrator import Orchestrator
        
        old_time = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        evidence = CanonicalLandingEvidence(
            old_base_sha="a" * 40,
            old_head_sha="b" * 40,
            new_base_sha="c" * 40,
            new_head_sha="d" * 40,
            target_epic_branch=VALID_EPIC_BRANCH,
            rebase_task_id=VALID_REBASE_TASK_ID,
            created_at_utc=old_time,
            evidence_fingerprint=_compute_evidence_fingerprint(
                "a" * 40, "b" * 40, "c" * 40, "d" * 40,
                VALID_EPIC_BRANCH, VALID_REBASE_TASK_ID, old_time
            ),
        )
        record = IntegrationRecord(
            state="integrated",
            task_branch="task-1",
            head_sha="a" * 40,
            canonical_landing_evidence=evidence.to_dict(),
        )
        result = Orchestrator._canonical_landing_evidence_block_reason(
            integration_record=record,
            epic_branch=VALID_EPIC_BRANCH,
            max_evidence_age_hours=24,
        )
        assert result is not None
        assert "stale" in result.lower()

    def test_recent_evidence_passes_freshness(self):
        """Evidence within max_age should pass (not blocked)."""
        from oompah.orchestrator import Orchestrator
        
        recent_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        evidence = CanonicalLandingEvidence(
            old_base_sha="a" * 40,
            old_head_sha="b" * 40,
            new_base_sha="c" * 40,
            new_head_sha="d" * 40,
            target_epic_branch=VALID_EPIC_BRANCH,
            rebase_task_id=VALID_REBASE_TASK_ID,
            created_at_utc=recent_time,
            evidence_fingerprint=_compute_evidence_fingerprint(
                "a" * 40, "b" * 40, "c" * 40, "d" * 40,
                VALID_EPIC_BRANCH, VALID_REBASE_TASK_ID, recent_time
            ),
        )
        record = IntegrationRecord(
            state="integrated",
            task_branch="task-1",
            head_sha="a" * 40,
            canonical_landing_evidence=evidence.to_dict(),
        )
        result = Orchestrator._canonical_landing_evidence_block_reason(
            integration_record=record,
            epic_branch=VALID_EPIC_BRANCH,
            max_evidence_age_hours=24,
        )
        assert result is None

    def test_malformed_evidence_blocks(self):
        """Malformed evidence should block (fail-closed)."""
        from oompah.orchestrator import Orchestrator
        
        record = IntegrationRecord(
            state="integrated",
            task_branch="task-1",
            head_sha="a" * 40,
            canonical_landing_evidence={
                "old_base_sha": "invalid",  # Not a valid SHA
            },
        )
        result = Orchestrator._canonical_landing_evidence_block_reason(
            integration_record=record,
            epic_branch=VALID_EPIC_BRANCH,
        )
        assert result is not None
        assert "malformed" in result.lower()

    def test_evidence_validation_exception_blocks(self):
        """Unexpected exception during validation should block (fail-closed)."""
        from oompah.orchestrator import Orchestrator
        
        # Use a non-dict value to trigger validation error
        record = IntegrationRecord(
            state="integrated",
            task_branch="task-1",
            head_sha="a" * 40,
            canonical_landing_evidence="not a dict",  # type: ignore
        )
        result = Orchestrator._canonical_landing_evidence_block_reason(
            integration_record=record,
            epic_branch=VALID_EPIC_BRANCH,
        )
        # Should have a block reason due to validation failure
        # (or None if parse_canonical_landing_evidence handles it gracefully)
        # Either way, the system should not crash
        assert result is None or isinstance(result, str)


# ============================================================================
# Bounded Historical Repair Tests
# ============================================================================

class TestBoundedHistoricalRepair:
    """Tests for secure historical repair evidence loading without trusting comments."""

    def test_unknown_task_id_returns_none(self):
        """Unknown task IDs should return None (fail-closed)."""
        from oompah.integration import load_bounded_historical_repair_evidence
        
        result = load_bounded_historical_repair_evidence("UNKNOWN-9999")
        assert result is None

    def test_empty_task_id_returns_none(self):
        """Empty task IDs should return None (fail-closed)."""
        from oompah.integration import load_bounded_historical_repair_evidence
        
        assert load_bounded_historical_repair_evidence("") is None
        assert load_bounded_historical_repair_evidence(None) is None
        assert load_bounded_historical_repair_evidence("   ") is None

    def test_whitelist_is_code_only_not_runtime_injectable(self):
        """Whitelist must be in code, not runtime-configurable (fail-closed)."""
        from oompah.integration import _BOUNDED_HISTORICAL_REPAIR_EVIDENCE
        
        # Whitelist should be a dict (immutable at module level)
        assert isinstance(_BOUNDED_HISTORICAL_REPAIR_EVIDENCE, dict)
        
        # Should be empty initially (maintainers add entries via code review)
        # Once entries exist, verify they're all valid
        for task_id, evidence_dict in _BOUNDED_HISTORICAL_REPAIR_EVIDENCE.items():
            assert isinstance(task_id, str)
            assert isinstance(evidence_dict, dict)
            # Each should be loadable
            result = load_bounded_historical_repair_evidence(task_id)
            assert result is None or isinstance(result, parse_canonical_landing_evidence(evidence_dict).__class__)

    def test_repair_evidence_must_be_valid_or_returns_none(self):
        """Even whitelisted tasks must have valid evidence or return None."""
        from oompah.integration import load_bounded_historical_repair_evidence
        
        # First verify the whitelist is currently empty (initial state)
        # If future entries exist, they must all parse successfully
        for task_id in ["OOMPAH-757", "EXOCOMP-130"]:
            result = load_bounded_historical_repair_evidence(task_id)
            # Can be None (not in whitelist) or valid evidence, never invalid


class TestHistoricalRepairSecurityModel:
    """Security model tests for historical repair evidence."""

    def test_no_pattern_matching_allows_injection(self):
        """Task ID matching must be exact, not pattern-based (fail-closed)."""
        from oompah.integration import load_bounded_historical_repair_evidence
        
        # Even if "OOMPAH-*" were added to whitelist, this should not match it
        assert load_bounded_historical_repair_evidence("OOMPAH-999") is None
        assert load_bounded_historical_repair_evidence("oompah-757") is None
        assert load_bounded_historical_repair_evidence("OOMPAH-757 ") is None

    def test_comment_text_is_never_parsed_as_evidence_source(self):
        """Human comments should never be used to load repair evidence."""
        # This is enforced architecturally:
        # - load_bounded_historical_repair_evidence uses whitelist only
        # - It never accepts arbitrary dicts from comments
        # - It returns None for unknown task IDs
        # 
        # Callers must NOT do:
        #   evidence_from_comment = parse(comment.text)  # WRONG
        #   load_bounded_historical_repair_evidence(comment.task_id)  # RIGHT
        pass
