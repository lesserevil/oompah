"""Tests for oompah.intake_schema — intake readiness schema and metadata (#283).

Covers:
- IntakeScopeKind: from_raw parsing, unknown fallback
- DecompositionStatus: from_raw parsing, unknown fallback
- ValidatorResult: from_raw parsing, None for missing
- IntakeReadiness.is_ready: all four readiness criteria
- IntakeReadiness.to_raw / from_raw: round-trip fidelity
- parse_intake_metadata: safe defaults, None/empty inputs
- intake_to_raw: convenience wrapper
- Metadata preservation: intake field does not clobber project_id,
  target_branch, work_branch, review_url, backports, or backport_of
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from oompah.intake_schema import (
    DecompositionStatus,
    IntakeReadiness,
    IntakeScopeKind,
    ValidatorResult,
    intake_to_raw,
    parse_intake_metadata,
)


# ===========================================================================
# IntakeScopeKind
# ===========================================================================


class TestIntakeScopeKind:
    def test_all_values_serialise_as_lowercase(self):
        assert IntakeScopeKind.SMALL.value == "small"
        assert IntakeScopeKind.LARGE.value == "large"
        assert IntakeScopeKind.NEEDS_DECOMPOSITION.value == "needs_decomposition"
        assert IntakeScopeKind.UNKNOWN.value == "unknown"

    def test_from_raw_exact_match(self):
        assert IntakeScopeKind.from_raw("small") == IntakeScopeKind.SMALL
        assert IntakeScopeKind.from_raw("large") == IntakeScopeKind.LARGE
        assert IntakeScopeKind.from_raw("needs_decomposition") == IntakeScopeKind.NEEDS_DECOMPOSITION
        assert IntakeScopeKind.from_raw("unknown") == IntakeScopeKind.UNKNOWN

    def test_from_raw_case_insensitive(self):
        assert IntakeScopeKind.from_raw("SMALL") == IntakeScopeKind.SMALL
        assert IntakeScopeKind.from_raw("Large") == IntakeScopeKind.LARGE
        assert IntakeScopeKind.from_raw("Needs_Decomposition") == IntakeScopeKind.NEEDS_DECOMPOSITION

    def test_from_raw_hyphen_normalised_to_underscore(self):
        assert IntakeScopeKind.from_raw("needs-decomposition") == IntakeScopeKind.NEEDS_DECOMPOSITION

    def test_from_raw_none_returns_unknown(self):
        assert IntakeScopeKind.from_raw(None) == IntakeScopeKind.UNKNOWN

    def test_from_raw_empty_string_returns_unknown(self):
        assert IntakeScopeKind.from_raw("") == IntakeScopeKind.UNKNOWN

    def test_from_raw_unrecognised_returns_unknown(self):
        assert IntakeScopeKind.from_raw("very_large") == IntakeScopeKind.UNKNOWN

    def test_from_raw_passthrough_enum(self):
        """Passing an already-parsed enum returns it unchanged."""
        assert IntakeScopeKind.from_raw(IntakeScopeKind.LARGE) == IntakeScopeKind.LARGE


# ===========================================================================
# DecompositionStatus
# ===========================================================================


class TestDecompositionStatus:
    def test_all_values_serialise_as_lowercase(self):
        assert DecompositionStatus.NOT_NEEDED.value == "not_needed"
        assert DecompositionStatus.PENDING.value == "pending"
        assert DecompositionStatus.PROPOSED.value == "proposed"
        assert DecompositionStatus.ACCEPTED.value == "accepted"
        assert DecompositionStatus.REJECTED.value == "rejected"

    def test_from_raw_exact_match(self):
        assert DecompositionStatus.from_raw("not_needed") == DecompositionStatus.NOT_NEEDED
        assert DecompositionStatus.from_raw("pending") == DecompositionStatus.PENDING
        assert DecompositionStatus.from_raw("proposed") == DecompositionStatus.PROPOSED
        assert DecompositionStatus.from_raw("accepted") == DecompositionStatus.ACCEPTED
        assert DecompositionStatus.from_raw("rejected") == DecompositionStatus.REJECTED

    def test_from_raw_case_insensitive(self):
        assert DecompositionStatus.from_raw("ACCEPTED") == DecompositionStatus.ACCEPTED
        assert DecompositionStatus.from_raw("Proposed") == DecompositionStatus.PROPOSED

    def test_from_raw_hyphen_normalised(self):
        assert DecompositionStatus.from_raw("not-needed") == DecompositionStatus.NOT_NEEDED

    def test_from_raw_none_returns_not_needed(self):
        assert DecompositionStatus.from_raw(None) == DecompositionStatus.NOT_NEEDED

    def test_from_raw_empty_string_returns_not_needed(self):
        assert DecompositionStatus.from_raw("") == DecompositionStatus.NOT_NEEDED

    def test_from_raw_unrecognised_returns_not_needed(self):
        assert DecompositionStatus.from_raw("blocked") == DecompositionStatus.NOT_NEEDED

    def test_from_raw_passthrough_enum(self):
        assert DecompositionStatus.from_raw(DecompositionStatus.ACCEPTED) == DecompositionStatus.ACCEPTED


# ===========================================================================
# ValidatorResult
# ===========================================================================


class TestValidatorResult:
    def test_all_values_serialise_as_lowercase(self):
        assert ValidatorResult.PASS.value == "pass"
        assert ValidatorResult.FAIL.value == "fail"
        assert ValidatorResult.PENDING.value == "pending"

    def test_from_raw_exact_match(self):
        assert ValidatorResult.from_raw("pass") == ValidatorResult.PASS
        assert ValidatorResult.from_raw("fail") == ValidatorResult.FAIL
        assert ValidatorResult.from_raw("pending") == ValidatorResult.PENDING

    def test_from_raw_case_insensitive(self):
        assert ValidatorResult.from_raw("PASS") == ValidatorResult.PASS
        assert ValidatorResult.from_raw("Fail") == ValidatorResult.FAIL

    def test_from_raw_none_returns_none(self):
        assert ValidatorResult.from_raw(None) is None

    def test_from_raw_empty_string_returns_none(self):
        assert ValidatorResult.from_raw("") is None

    def test_from_raw_unrecognised_returns_pending(self):
        """Unrecognised non-empty value degrades to pending, not None."""
        assert ValidatorResult.from_raw("error") == ValidatorResult.PENDING

    def test_from_raw_passthrough_enum(self):
        assert ValidatorResult.from_raw(ValidatorResult.PASS) == ValidatorResult.PASS


# ===========================================================================
# IntakeReadiness.is_ready — readiness criteria
# ===========================================================================


class TestIntakeReadinessIsReady:
    """Tests for the four readiness criteria encoded in IntakeReadiness.is_ready."""

    def _ready_state(self) -> IntakeReadiness:
        """Return a fully-ready IntakeReadiness instance."""
        return IntakeReadiness(
            missing_fields=[],
            scope=IntakeScopeKind.SMALL,
            requestor_approved=True,
            requestor_approved_at="2026-06-11T16:00:00Z",
            requestor_actor="alice",
            owner_override=False,
            owner_override_at=None,
            owner_actor=None,
            decomposition_status=DecompositionStatus.NOT_NEEDED,
            last_validator_result=ValidatorResult.PASS,
            last_validated_at="2026-06-11T16:00:00Z",
        )

    def test_fully_ready_is_true(self):
        assert self._ready_state().is_ready is True

    def test_missing_fields_prevents_ready(self):
        r = self._ready_state()
        r.missing_fields = ["acceptance_criteria"]
        assert r.is_ready is False

    def test_needs_decomposition_prevents_ready(self):
        r = self._ready_state()
        r.scope = IntakeScopeKind.NEEDS_DECOMPOSITION
        assert r.is_ready is False

    def test_large_scope_does_not_prevent_ready(self):
        """Large scope is allowed — only needs_decomposition blocks readiness."""
        r = self._ready_state()
        r.scope = IntakeScopeKind.LARGE
        assert r.is_ready is True

    def test_unknown_scope_does_not_prevent_ready(self):
        """Unknown scope is allowed — validator_result is the quality gate."""
        r = self._ready_state()
        r.scope = IntakeScopeKind.UNKNOWN
        assert r.is_ready is True

    def test_no_approval_no_override_prevents_ready(self):
        r = self._ready_state()
        r.requestor_approved = False
        r.owner_override = False
        assert r.is_ready is False

    def test_owner_override_satisfies_approval_criterion(self):
        """owner_override=True can substitute for requestor approval."""
        r = self._ready_state()
        r.requestor_approved = False
        r.owner_override = True
        assert r.is_ready is True

    def test_validator_fail_prevents_ready(self):
        r = self._ready_state()
        r.last_validator_result = ValidatorResult.FAIL
        assert r.is_ready is False

    def test_validator_pending_prevents_ready(self):
        r = self._ready_state()
        r.last_validator_result = ValidatorResult.PENDING
        assert r.is_ready is False

    def test_validator_none_prevents_ready(self):
        """Never-validated issue is not ready."""
        r = self._ready_state()
        r.last_validator_result = None
        assert r.is_ready is False

    def test_default_instance_is_not_ready(self):
        """A freshly-created IntakeReadiness should not be ready by default."""
        assert IntakeReadiness().is_ready is False


# ===========================================================================
# IntakeReadiness.to_raw — serialisation
# ===========================================================================


class TestIntakeReadinessToRaw:
    def test_to_raw_returns_dict(self):
        r = IntakeReadiness()
        raw = r.to_raw()
        assert isinstance(raw, dict)

    def test_to_raw_all_keys_present(self):
        r = IntakeReadiness()
        raw = r.to_raw()
        expected_keys = {
            "missing_fields",
            "scope",
            "requestor_approved",
            "requestor_approved_at",
            "requestor_actor",
            "owner_override",
            "owner_override_at",
            "owner_actor",
            "decomposition_status",
            "last_validator_result",
            "last_validated_at",
        }
        assert set(raw.keys()) == expected_keys

    def test_to_raw_default_values(self):
        r = IntakeReadiness()
        raw = r.to_raw()
        assert raw["missing_fields"] == []
        assert raw["scope"] == "unknown"
        assert raw["requestor_approved"] is False
        assert raw["requestor_approved_at"] is None
        assert raw["requestor_actor"] is None
        assert raw["owner_override"] is False
        assert raw["owner_override_at"] is None
        assert raw["owner_actor"] is None
        assert raw["decomposition_status"] == "not_needed"
        assert raw["last_validator_result"] is None
        assert raw["last_validated_at"] is None

    def test_to_raw_populated_values(self):
        r = IntakeReadiness(
            missing_fields=["repro_steps"],
            scope=IntakeScopeKind.LARGE,
            requestor_approved=True,
            requestor_approved_at="2026-06-11T16:00:00Z",
            requestor_actor="alice",
            owner_override=True,
            owner_override_at="2026-06-11T17:00:00Z",
            owner_actor="bob",
            decomposition_status=DecompositionStatus.PROPOSED,
            last_validator_result=ValidatorResult.FAIL,
            last_validated_at="2026-06-11T15:00:00Z",
        )
        raw = r.to_raw()
        assert raw["missing_fields"] == ["repro_steps"]
        assert raw["scope"] == "large"
        assert raw["requestor_approved"] is True
        assert raw["requestor_approved_at"] == "2026-06-11T16:00:00Z"
        assert raw["requestor_actor"] == "alice"
        assert raw["owner_override"] is True
        assert raw["owner_override_at"] == "2026-06-11T17:00:00Z"
        assert raw["owner_actor"] == "bob"
        assert raw["decomposition_status"] == "proposed"
        assert raw["last_validator_result"] == "fail"
        assert raw["last_validated_at"] == "2026-06-11T15:00:00Z"

    def test_to_raw_is_json_serialisable(self):
        r = IntakeReadiness(
            missing_fields=["acceptance_criteria"],
            scope=IntakeScopeKind.SMALL,
            requestor_approved=True,
            requestor_approved_at="2026-06-11T16:00:00Z",
            requestor_actor="alice",
            last_validator_result=ValidatorResult.PASS,
            last_validated_at="2026-06-11T16:00:00Z",
        )
        # Must not raise
        serialised = json.dumps(r.to_raw())
        assert serialised  # non-empty


# ===========================================================================
# IntakeReadiness.from_raw — deserialisation
# ===========================================================================


class TestIntakeReadinessFromRaw:
    def test_from_raw_none_returns_defaults(self):
        r = IntakeReadiness.from_raw(None)
        assert r.missing_fields == []
        assert r.scope == IntakeScopeKind.UNKNOWN
        assert r.requestor_approved is False
        assert r.owner_override is False
        assert r.last_validator_result is None

    def test_from_raw_empty_dict_returns_defaults(self):
        r = IntakeReadiness.from_raw({})
        assert r.missing_fields == []
        assert r.scope == IntakeScopeKind.UNKNOWN

    def test_from_raw_non_dict_returns_defaults(self):
        assert IntakeReadiness.from_raw("bad") == IntakeReadiness()
        assert IntakeReadiness.from_raw(42) == IntakeReadiness()
        assert IntakeReadiness.from_raw([]) == IntakeReadiness()

    def test_from_raw_full_object(self):
        raw = {
            "missing_fields": ["acceptance_criteria", "repro_steps"],
            "scope": "large",
            "requestor_approved": True,
            "requestor_approved_at": "2026-06-11T16:00:00Z",
            "requestor_actor": "charlie",
            "owner_override": False,
            "owner_override_at": None,
            "owner_actor": None,
            "decomposition_status": "accepted",
            "last_validator_result": "pass",
            "last_validated_at": "2026-06-11T14:00:00Z",
        }
        r = IntakeReadiness.from_raw(raw)
        assert r.missing_fields == ["acceptance_criteria", "repro_steps"]
        assert r.scope == IntakeScopeKind.LARGE
        assert r.requestor_approved is True
        assert r.requestor_approved_at == "2026-06-11T16:00:00Z"
        assert r.requestor_actor == "charlie"
        assert r.owner_override is False
        assert r.owner_override_at is None
        assert r.owner_actor is None
        assert r.decomposition_status == DecompositionStatus.ACCEPTED
        assert r.last_validator_result == ValidatorResult.PASS
        assert r.last_validated_at == "2026-06-11T14:00:00Z"

    def test_from_raw_partial_object_uses_defaults(self):
        """Only supplied keys are used; absent keys fall back to safe defaults."""
        r = IntakeReadiness.from_raw({"scope": "small", "requestor_approved": True})
        assert r.scope == IntakeScopeKind.SMALL
        assert r.requestor_approved is True
        assert r.missing_fields == []
        assert r.owner_override is False
        assert r.last_validator_result is None

    def test_from_raw_missing_fields_scalar_string_normalised(self):
        """A bare string in missing_fields is coerced to a list."""
        r = IntakeReadiness.from_raw({"missing_fields": "acceptance_criteria"})
        assert r.missing_fields == ["acceptance_criteria"]

    def test_from_raw_unknown_scope_becomes_unknown(self):
        r = IntakeReadiness.from_raw({"scope": "extremely_large"})
        assert r.scope == IntakeScopeKind.UNKNOWN

    def test_from_raw_unknown_decomposition_status_becomes_not_needed(self):
        r = IntakeReadiness.from_raw({"decomposition_status": "in_flight"})
        assert r.decomposition_status == DecompositionStatus.NOT_NEEDED

    def test_from_raw_unknown_validator_result_becomes_pending(self):
        r = IntakeReadiness.from_raw({"last_validator_result": "error"})
        assert r.last_validator_result == ValidatorResult.PENDING


# ===========================================================================
# Round-trip: to_raw → from_raw → to_raw
# ===========================================================================


class TestIntakeReadinessRoundTrip:
    def _check_round_trip(self, readiness: IntakeReadiness) -> None:
        raw1 = readiness.to_raw()
        restored = IntakeReadiness.from_raw(raw1)
        raw2 = restored.to_raw()
        assert raw1 == raw2, f"Round-trip mismatch:\n  first:  {raw1}\n  second: {raw2}"
        assert restored == readiness

    def test_round_trip_default_instance(self):
        self._check_round_trip(IntakeReadiness())

    def test_round_trip_fully_populated(self):
        r = IntakeReadiness(
            missing_fields=["acceptance_criteria"],
            scope=IntakeScopeKind.LARGE,
            requestor_approved=True,
            requestor_approved_at="2026-06-11T16:00:00Z",
            requestor_actor="alice",
            owner_override=False,
            owner_override_at=None,
            owner_actor=None,
            decomposition_status=DecompositionStatus.ACCEPTED,
            last_validator_result=ValidatorResult.PASS,
            last_validated_at="2026-06-11T16:00:00Z",
        )
        self._check_round_trip(r)

    def test_round_trip_with_owner_override(self):
        r = IntakeReadiness(
            owner_override=True,
            owner_override_at="2026-06-11T18:00:00Z",
            owner_actor="project-owner",
            scope=IntakeScopeKind.NEEDS_DECOMPOSITION,
            last_validator_result=ValidatorResult.FAIL,
        )
        self._check_round_trip(r)

    def test_round_trip_needs_decomposition(self):
        r = IntakeReadiness(
            scope=IntakeScopeKind.NEEDS_DECOMPOSITION,
            decomposition_status=DecompositionStatus.PROPOSED,
        )
        self._check_round_trip(r)

    def test_round_trip_validator_fail(self):
        r = IntakeReadiness(
            last_validator_result=ValidatorResult.FAIL,
            last_validated_at="2026-06-11T10:00:00Z",
        )
        self._check_round_trip(r)

    def test_round_trip_via_json_serialisation(self):
        """Ensure the round-trip survives a JSON encode/decode (as stored in metadata)."""
        r = IntakeReadiness(
            missing_fields=["repro"],
            scope=IntakeScopeKind.SMALL,
            requestor_approved=True,
            requestor_approved_at="2026-06-11T12:00:00Z",
            requestor_actor="dave",
            last_validator_result=ValidatorResult.PASS,
            last_validated_at="2026-06-11T12:00:00Z",
        )
        raw = r.to_raw()
        # Simulate JSON encode/decode (as happens when the metadata block is
        # written and re-read from the GitHub issue body)
        json_round_tripped = json.loads(json.dumps(raw))
        restored = IntakeReadiness.from_raw(json_round_tripped)
        assert restored == r


# ===========================================================================
# parse_intake_metadata helper
# ===========================================================================


class TestParseIntakeMetadata:
    def test_none_returns_default(self):
        r = parse_intake_metadata(None)
        assert r == IntakeReadiness()

    def test_empty_dict_returns_default(self):
        r = parse_intake_metadata({})
        assert r == IntakeReadiness()

    def test_full_dict_is_parsed(self):
        raw = {
            "scope": "small",
            "requestor_approved": True,
            "requestor_actor": "alice",
            "last_validator_result": "pass",
        }
        r = parse_intake_metadata(raw)
        assert r.scope == IntakeScopeKind.SMALL
        assert r.requestor_approved is True
        assert r.requestor_actor == "alice"
        assert r.last_validator_result == ValidatorResult.PASS


# ===========================================================================
# intake_to_raw helper
# ===========================================================================


class TestIntakeToRaw:
    def test_returns_dict(self):
        raw = intake_to_raw(IntakeReadiness())
        assert isinstance(raw, dict)

    def test_equivalent_to_to_raw(self):
        r = IntakeReadiness(
            scope=IntakeScopeKind.LARGE,
            requestor_approved=True,
            requestor_actor="charlie",
        )
        assert intake_to_raw(r) == r.to_raw()


# ===========================================================================
# Metadata preservation — intake field does not clobber existing fields
# ===========================================================================


class TestMetadataPreservation:
    """Verify that writing intake metadata preserves existing oompah metadata.

    These tests confirm that the existing set_metadata_field mechanism
    (which reads, merges, and rewrites the metadata block) correctly
    preserves all pre-existing fields when the intake field is added or
    updated.
    """

    def _make_tracker(self):
        """Return a GitHubIssueTracker with minimal config."""
        from oompah.github_tracker import GitHubAuth, GitHubIssueTracker

        return GitHubIssueTracker(
            owner="lesserevil",
            repo="oompah",
            active_states=["Open", "In Progress"],
            terminal_states=["Done"],
            auth=GitHubAuth(pat="tok"),
        )

    def _make_body(self, meta: dict) -> str:
        """Build an issue body with the given metadata dict embedded."""
        from oompah.github_tracker import GitHubIssueTracker, GitHubAuth

        tracker = self._make_tracker()
        return tracker._build_issue_body("Issue description.", meta)

    def _parse_meta(self, body: str) -> dict:
        from oompah.github_tracker import _parse_body_metadata

        return _parse_body_metadata(body)

    def test_intake_field_added_alongside_project_id(self):
        """Adding oompah.intake preserves project_id and target_branch."""
        original_meta = {
            "project_id": "proj-14849f1b",
            "target_branch": "main",
        }
        body = self._make_body(original_meta)
        tracker = self._make_tracker()

        # Simulate set_metadata_field for "oompah.intake"
        intake_raw = intake_to_raw(IntakeReadiness(
            scope=IntakeScopeKind.SMALL,
            last_validator_result=ValidatorResult.PENDING,
            last_validated_at="2026-06-11T16:00:00Z",
        ))
        updated_body = tracker._update_body_metadata(body, {**original_meta, "intake": intake_raw})

        result_meta = self._parse_meta(updated_body)
        assert result_meta["project_id"] == "proj-14849f1b"
        assert result_meta["target_branch"] == "main"
        assert "intake" in result_meta

    def test_intake_update_preserves_review_metadata(self):
        """Updating oompah.intake preserves review_url and review_number."""
        original_meta = {
            "project_id": "proj-1",
            "review_url": "https://github.com/org/repo/pull/99",
            "review_number": "99",
            "work_branch": "oompah/proj/gh-42",
        }
        body = self._make_body(original_meta)
        tracker = self._make_tracker()

        intake_raw = intake_to_raw(IntakeReadiness(requestor_approved=True))
        updated_body = tracker._update_body_metadata(
            body, {**original_meta, "intake": intake_raw}
        )

        result_meta = self._parse_meta(updated_body)
        assert result_meta["review_url"] == "https://github.com/org/repo/pull/99"
        assert result_meta["review_number"] == "99"
        assert result_meta["work_branch"] == "oompah/proj/gh-42"
        assert result_meta["intake"]["requestor_approved"] is True

    def test_intake_update_preserves_backport_metadata(self):
        """Updating oompah.intake preserves backports and backport_of fields."""
        backports_raw = [{"branch": "release/1.0", "status": "waiting"}]
        original_meta = {
            "project_id": "proj-1",
            "backports": backports_raw,
        }
        body = self._make_body(original_meta)
        tracker = self._make_tracker()

        intake_raw = intake_to_raw(IntakeReadiness(owner_override=True, owner_actor="admin"))
        updated_body = tracker._update_body_metadata(
            body, {**original_meta, "intake": intake_raw}
        )

        result_meta = self._parse_meta(updated_body)
        assert result_meta["backports"] == backports_raw
        assert result_meta["intake"]["owner_override"] is True
        assert result_meta["intake"]["owner_actor"] == "admin"

    def test_intake_update_preserves_description(self):
        """Updating oompah.intake does not alter the human-readable issue description."""
        original_meta = {"project_id": "proj-1"}
        body = self._make_body(original_meta)
        tracker = self._make_tracker()

        intake_raw = intake_to_raw(IntakeReadiness())
        updated_body = tracker._update_body_metadata(
            body, {**original_meta, "intake": intake_raw}
        )

        # Description must be at the top, unchanged
        assert updated_body.startswith("Issue description.")

    def test_intake_field_survives_json_round_trip_in_body(self):
        """The full metadata block (including intake) survives encode/decode."""
        from oompah.github_tracker import _parse_body_metadata

        readiness = IntakeReadiness(
            missing_fields=["acceptance_criteria"],
            scope=IntakeScopeKind.LARGE,
            requestor_approved=True,
            requestor_approved_at="2026-06-11T16:00:00Z",
            requestor_actor="alice",
            owner_override=False,
            decomposition_status=DecompositionStatus.NOT_NEEDED,
            last_validator_result=ValidatorResult.PASS,
            last_validated_at="2026-06-11T16:00:00Z",
        )
        meta = {
            "project_id": "proj-xyz",
            "target_branch": "main",
            "intake": intake_to_raw(readiness),
        }
        tracker = self._make_tracker()
        body = tracker._build_issue_body("Description here.", meta)

        # Parse back
        parsed_meta = _parse_body_metadata(body)
        restored = parse_intake_metadata(parsed_meta.get("intake"))

        assert restored == readiness
        assert parsed_meta["project_id"] == "proj-xyz"
        assert parsed_meta["target_branch"] == "main"


# ===========================================================================
# is_ready — comprehensive edge-case matrix
# ===========================================================================


class TestIsReadyEdgeCases:
    """Additional boundary cases for IntakeReadiness.is_ready."""

    def test_empty_missing_fields_list_passes_criterion(self):
        r = IntakeReadiness(
            missing_fields=[],
            scope=IntakeScopeKind.SMALL,
            requestor_approved=True,
            last_validator_result=ValidatorResult.PASS,
        )
        assert r.is_ready is True

    def test_single_missing_field_blocks_ready(self):
        r = IntakeReadiness(
            missing_fields=["one_field"],
            scope=IntakeScopeKind.SMALL,
            requestor_approved=True,
            last_validator_result=ValidatorResult.PASS,
        )
        assert r.is_ready is False

    def test_both_approved_and_override_passes(self):
        """Having both requestor approval AND owner override is also ready."""
        r = IntakeReadiness(
            scope=IntakeScopeKind.SMALL,
            requestor_approved=True,
            owner_override=True,
            last_validator_result=ValidatorResult.PASS,
        )
        assert r.is_ready is True

    def test_epic_with_accepted_decomposition_can_be_ready(self):
        """An epic issue with accepted decomposition and validator pass is ready."""
        r = IntakeReadiness(
            scope=IntakeScopeKind.LARGE,
            decomposition_status=DecompositionStatus.ACCEPTED,
            requestor_approved=True,
            last_validator_result=ValidatorResult.PASS,
        )
        assert r.is_ready is True

    def test_pending_decomposition_does_not_block_ready(self):
        """Decomposition status alone does not affect is_ready (scope does)."""
        r = IntakeReadiness(
            scope=IntakeScopeKind.SMALL,
            decomposition_status=DecompositionStatus.PENDING,
            requestor_approved=True,
            last_validator_result=ValidatorResult.PASS,
        )
        assert r.is_ready is True
