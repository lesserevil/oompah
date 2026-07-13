"""Tests for oompah.release_addendum_schema (OOMPAH-173).

Covers:
  - AddendumStatus enum: all values, from_raw normalisation, is_terminal/is_active
  - VALID_TRANSITIONS: structural invariants
  - is_valid_transition: allowed, disallowed, self-transitions
  - make_addendum_id: valid inputs, empty-argument errors
  - make_work_branch: deterministic generation, sanitization, namespace prefix
  - make_worktree_key: deterministic generation, sanitization
  - ReleaseAddendum.from_raw: valid full dict, missing required fields,
    empty commits, unknown status, round-trip
  - ReleaseAddendum.to_raw: all fields serialised correctly
  - parse_addendums: None, empty list, single dict, list of dicts, malformed
  - addendums_to_raw: empty, single, multiple
  - AddendumRepository.read: delegates to tracker.get_metadata
  - AddendumRepository.write: validates and calls set_metadata_field,
    preserves unrelated metadata, rejects duplicate targets
  - AddendumRepository.add: idempotent on active duplicate, allows
    new entry when only archived exists
  - AddendumRepository.transition: valid transitions, invalid transitions,
    missing addendum, commits immutable, execution-evidence fields updated,
    unknown kwargs rejected
  - DuplicateTargetError / InvalidTransitionError / ImmutableCommitsError
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from oompah.release_addendum_schema import (
    AddendumRepository,
    AddendumStatus,
    DuplicateTargetError,
    InvalidTransitionError,
    ReleaseAddendum,
    VALID_TRANSITIONS,
    _sanitize_part,
    _validate_no_duplicate_active_targets,
    addendums_to_raw,
    is_valid_transition,
    make_addendum_id,
    make_work_branch,
    make_worktree_key,
    parse_addendums,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMMITS = ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]

_BASE_RAW: dict = {
    "id": "FOO-10/release/1.0",
    "source_branch": "main",
    "target_branch": "release/1.0",
    "status": "open",
    "commits": list(_COMMITS),
    "work_branch": "oompah/release/FOO-10/release-1.0",
    "worktree_key": "release-FOO-10-release-1.0",
    "queued_at": "2026-07-13T12:00:00Z",
    "started_at": None,
    "completed_at": None,
    "pr_url": None,
    "result_commits": [],
    "error": None,
}


def _make_addendum(**overrides) -> ReleaseAddendum:
    """Return a minimal valid ReleaseAddendum, optionally overriding fields."""
    return ReleaseAddendum(
        id=overrides.get("id", "FOO-10/release/1.0"),
        source_branch=overrides.get("source_branch", "main"),
        target_branch=overrides.get("target_branch", "release/1.0"),
        status=overrides.get("status", AddendumStatus.OPEN),
        commits=overrides.get("commits", list(_COMMITS)),
        work_branch=overrides.get("work_branch", "oompah/release/FOO-10/release-1.0"),
        worktree_key=overrides.get("worktree_key", "release-FOO-10-release-1.0"),
        queued_at=overrides.get("queued_at", "2026-07-13T12:00:00Z"),
    )


def _make_tracker(addendums: list[ReleaseAddendum] | None = None) -> MagicMock:
    """Return a mock tracker whose get_metadata returns the given addendums."""
    tracker = MagicMock()
    raw = addendums_to_raw(addendums) if addendums else None
    tracker.get_metadata.return_value = {
        "oompah.release_addendums": raw,
        "oompah.work_branch": "some-other-branch",  # should be preserved
    }
    return tracker


# ---------------------------------------------------------------------------
# AddendumStatus enum
# ---------------------------------------------------------------------------


class TestAddendumStatusValues:
    """All required status values must be present."""

    def test_all_expected_values(self):
        expected = {"open", "in_progress", "in_review", "blocked", "merged", "archived"}
        assert {m.value for m in AddendumStatus} == expected

    def test_enum_inherits_str(self):
        assert isinstance(AddendumStatus.OPEN, str)
        assert AddendumStatus.OPEN == "open"

    def test_all_values_lowercase(self):
        for member in AddendumStatus:
            assert member.value == member.value.lower()


class TestAddendumStatusFromRaw:
    """AddendumStatus.from_raw parses valid inputs and rejects invalid ones."""

    @pytest.mark.parametrize("raw,expected", [
        ("open", AddendumStatus.OPEN),
        ("in_progress", AddendumStatus.IN_PROGRESS),
        ("in_review", AddendumStatus.IN_REVIEW),
        ("blocked", AddendumStatus.BLOCKED),
        ("merged", AddendumStatus.MERGED),
        ("archived", AddendumStatus.ARCHIVED),
    ])
    def test_parses_exact_value(self, raw, expected):
        assert AddendumStatus.from_raw(raw) == expected

    def test_case_insensitive(self):
        assert AddendumStatus.from_raw("OPEN") == AddendumStatus.OPEN
        assert AddendumStatus.from_raw("In_Progress") == AddendumStatus.IN_PROGRESS

    def test_hyphens_normalised(self):
        assert AddendumStatus.from_raw("in-progress") == AddendumStatus.IN_PROGRESS
        assert AddendumStatus.from_raw("in-review") == AddendumStatus.IN_REVIEW

    def test_none_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            AddendumStatus.from_raw(None)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            AddendumStatus.from_raw("")

    def test_unknown_value_raises(self):
        with pytest.raises(ValueError, match="Unknown AddendumStatus"):
            AddendumStatus.from_raw("waiting")

    def test_idempotent_on_enum_instance(self):
        assert AddendumStatus.from_raw(AddendumStatus.MERGED) is AddendumStatus.MERGED


class TestAddendumStatusProperties:
    """is_terminal and is_active properties."""

    def test_merged_is_terminal(self):
        assert AddendumStatus.MERGED.is_terminal

    def test_archived_is_terminal(self):
        assert AddendumStatus.ARCHIVED.is_terminal

    def test_open_not_terminal(self):
        assert not AddendumStatus.OPEN.is_terminal

    def test_blocked_not_terminal(self):
        assert not AddendumStatus.BLOCKED.is_terminal

    def test_open_is_active(self):
        assert AddendumStatus.OPEN.is_active

    def test_in_progress_is_active(self):
        assert AddendumStatus.IN_PROGRESS.is_active

    def test_in_review_is_active(self):
        assert AddendumStatus.IN_REVIEW.is_active

    def test_blocked_is_active(self):
        assert AddendumStatus.BLOCKED.is_active

    def test_merged_not_active(self):
        assert not AddendumStatus.MERGED.is_active

    def test_archived_not_active(self):
        assert not AddendumStatus.ARCHIVED.is_active


# ---------------------------------------------------------------------------
# VALID_TRANSITIONS and is_valid_transition
# ---------------------------------------------------------------------------


class TestValidTransitions:
    """Structural invariants of the transition table."""

    def test_all_statuses_have_entries(self):
        for status in AddendumStatus:
            assert status in VALID_TRANSITIONS, f"{status!r} missing from VALID_TRANSITIONS"

    def test_terminal_statuses_have_no_transitions(self):
        assert VALID_TRANSITIONS[AddendumStatus.MERGED] == frozenset()
        assert VALID_TRANSITIONS[AddendumStatus.ARCHIVED] == frozenset()

    def test_all_target_statuses_are_valid_members(self):
        valid_members = set(AddendumStatus)
        for from_status, targets in VALID_TRANSITIONS.items():
            for t in targets:
                assert t in valid_members, f"Unknown target {t!r} for {from_status!r}"


class TestIsValidTransition:
    """is_valid_transition enforces the FSM."""

    # Forward transitions defined in section 4.2
    @pytest.mark.parametrize("from_s,to_s", [
        (AddendumStatus.OPEN, AddendumStatus.IN_PROGRESS),
        (AddendumStatus.OPEN, AddendumStatus.ARCHIVED),
        (AddendumStatus.IN_PROGRESS, AddendumStatus.IN_REVIEW),
        (AddendumStatus.IN_PROGRESS, AddendumStatus.BLOCKED),
        (AddendumStatus.IN_PROGRESS, AddendumStatus.OPEN),
        (AddendumStatus.IN_REVIEW, AddendumStatus.MERGED),
        (AddendumStatus.IN_REVIEW, AddendumStatus.OPEN),
        (AddendumStatus.BLOCKED, AddendumStatus.OPEN),
        (AddendumStatus.BLOCKED, AddendumStatus.ARCHIVED),
    ])
    def test_valid_transitions(self, from_s, to_s):
        assert is_valid_transition(from_s, to_s), (
            f"Expected {from_s!r} → {to_s!r} to be valid"
        )

    # Terminal state has no outgoing transitions
    @pytest.mark.parametrize("from_s,to_s", [
        (AddendumStatus.MERGED, AddendumStatus.OPEN),
        (AddendumStatus.ARCHIVED, AddendumStatus.OPEN),
        (AddendumStatus.MERGED, AddendumStatus.ARCHIVED),
        (AddendumStatus.ARCHIVED, AddendumStatus.MERGED),
    ])
    def test_terminal_transitions_are_invalid(self, from_s, to_s):
        assert not is_valid_transition(from_s, to_s)

    # Skipping over steps
    @pytest.mark.parametrize("from_s,to_s", [
        (AddendumStatus.OPEN, AddendumStatus.MERGED),
        (AddendumStatus.OPEN, AddendumStatus.IN_REVIEW),
        (AddendumStatus.IN_PROGRESS, AddendumStatus.MERGED),
        (AddendumStatus.BLOCKED, AddendumStatus.IN_REVIEW),
        (AddendumStatus.BLOCKED, AddendumStatus.MERGED),
    ])
    def test_skipped_step_invalid(self, from_s, to_s):
        assert not is_valid_transition(from_s, to_s)

    def test_self_transition_always_false(self):
        for status in AddendumStatus:
            assert not is_valid_transition(status, status), (
                f"Self-transition {status!r} → {status!r} should be invalid"
            )


# ---------------------------------------------------------------------------
# Deterministic ID / branch / worktree helpers
# ---------------------------------------------------------------------------


class TestSanitizePart:
    """_sanitize_part produces Git-safe slugs."""

    def test_alphanumeric_passthrough(self):
        assert _sanitize_part("FOO10") == "FOO10"

    def test_slashes_replaced(self):
        assert _sanitize_part("release/1.0") == "release-1.0"

    def test_multiple_specials_collapsed(self):
        assert _sanitize_part("a  b//c") == "a-b-c"

    def test_leading_trailing_stripped(self):
        assert _sanitize_part("-foo-") == "foo"
        assert _sanitize_part(".foo.") == "foo"

    def test_empty_falls_back_to_unnamed(self):
        assert _sanitize_part("") == "unnamed"
        assert _sanitize_part("---") == "unnamed"


class TestMakeAddendumId:
    """make_addendum_id returns <source>/<target> unchanged."""

    def test_basic(self):
        assert make_addendum_id("FOO-10", "release/1.0") == "FOO-10/release/1.0"

    def test_strips_whitespace(self):
        assert make_addendum_id(" FOO-10 ", " release/1.0 ") == "FOO-10/release/1.0"

    def test_empty_source_raises(self):
        with pytest.raises(ValueError, match="source_id"):
            make_addendum_id("", "release/1.0")

    def test_empty_target_raises(self):
        with pytest.raises(ValueError, match="target_branch"):
            make_addendum_id("FOO-10", "")

    def test_none_source_raises(self):
        with pytest.raises(ValueError, match="source_id"):
            make_addendum_id(None, "release/1.0")  # type: ignore[arg-type]


class TestMakeWorkBranch:
    """make_work_branch generates oompah/release/-prefixed branch names."""

    def test_basic(self):
        assert make_work_branch("FOO-10", "release/1.0") == "oompah/release/FOO-10/release-1.0"

    def test_namespace_prefix(self):
        result = make_work_branch("FOO-10", "release/1.0")
        assert result.startswith("oompah/release/")

    def test_slashes_in_target_sanitized(self):
        # release/1.0 → release-1.0 (slash replaced by -)
        result = make_work_branch("FOO-10", "release/1.0")
        assert "/release-1.0" in result

    def test_special_chars_in_source_sanitized(self):
        result = make_work_branch("FOO 10", "release/1.0")
        assert " " not in result
        assert result.startswith("oompah/release/")

    def test_deterministic(self):
        result1 = make_work_branch("BAR-99", "release/2.0")
        result2 = make_work_branch("BAR-99", "release/2.0")
        assert result1 == result2

    def test_empty_source_raises(self):
        with pytest.raises(ValueError, match="source_id"):
            make_work_branch("", "release/1.0")

    def test_empty_target_raises(self):
        with pytest.raises(ValueError, match="target_branch"):
            make_work_branch("FOO-10", "")


class TestMakeWorktreeKey:
    """make_worktree_key generates release- prefixed flat slugs."""

    def test_basic(self):
        assert make_worktree_key("FOO-10", "release/1.0") == "release-FOO-10-release-1.0"

    def test_prefix(self):
        result = make_worktree_key("FOO-10", "release/1.0")
        assert result.startswith("release-")

    def test_no_slashes_in_result(self):
        result = make_worktree_key("FOO-10", "release/1.0")
        assert "/" not in result

    def test_deterministic(self):
        assert make_worktree_key("X-1", "release/1.1") == make_worktree_key("X-1", "release/1.1")

    def test_distinct_for_different_targets(self):
        k1 = make_worktree_key("FOO-10", "release/1.0")
        k2 = make_worktree_key("FOO-10", "release/2.0")
        assert k1 != k2

    def test_empty_source_raises(self):
        with pytest.raises(ValueError, match="source_id"):
            make_worktree_key("", "release/1.0")

    def test_empty_target_raises(self):
        with pytest.raises(ValueError, match="target_branch"):
            make_worktree_key("FOO-10", "")


# ---------------------------------------------------------------------------
# ReleaseAddendum.from_raw
# ---------------------------------------------------------------------------


class TestReleaseAddendumFromRaw:
    """ReleaseAddendum.from_raw parses valid dicts and rejects malformed ones."""

    def test_valid_full_record(self):
        a = ReleaseAddendum.from_raw(_BASE_RAW)
        assert a.id == "FOO-10/release/1.0"
        assert a.source_branch == "main"
        assert a.target_branch == "release/1.0"
        assert a.status == AddendumStatus.OPEN
        assert a.commits == _COMMITS
        assert a.work_branch == "oompah/release/FOO-10/release-1.0"
        assert a.worktree_key == "release-FOO-10-release-1.0"
        assert a.queued_at == "2026-07-13T12:00:00Z"
        assert a.started_at is None
        assert a.completed_at is None
        assert a.pr_url is None
        assert a.result_commits == []
        assert a.error is None

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            ReleaseAddendum.from_raw("release/1.0")

    def test_missing_id_raises(self):
        raw = {**_BASE_RAW, "id": ""}
        with pytest.raises(ValueError, match="missing required 'id'"):
            ReleaseAddendum.from_raw(raw)

    def test_missing_source_branch_raises(self):
        raw = {**_BASE_RAW, "source_branch": None}
        with pytest.raises(ValueError, match="source_branch"):
            ReleaseAddendum.from_raw(raw)

    def test_missing_target_branch_raises(self):
        raw = {**_BASE_RAW, "target_branch": ""}
        with pytest.raises(ValueError, match="target_branch"):
            ReleaseAddendum.from_raw(raw)

    def test_missing_commits_raises(self):
        raw = {**_BASE_RAW, "commits": []}
        with pytest.raises(ValueError, match="commits.*nonempty"):
            ReleaseAddendum.from_raw(raw)

    def test_null_commits_raises(self):
        raw = {**_BASE_RAW, "commits": None}
        with pytest.raises(ValueError, match="commits"):
            ReleaseAddendum.from_raw(raw)

    def test_commits_with_only_whitespace_raises(self):
        raw = {**_BASE_RAW, "commits": ["   "]}
        with pytest.raises(ValueError, match="commits"):
            ReleaseAddendum.from_raw(raw)

    def test_unknown_status_raises(self):
        raw = {**_BASE_RAW, "status": "waiting"}
        with pytest.raises(ValueError, match="Unknown AddendumStatus"):
            ReleaseAddendum.from_raw(raw)

    def test_missing_status_raises(self):
        raw = {**_BASE_RAW, "status": None}
        with pytest.raises(ValueError, match="must not be empty"):
            ReleaseAddendum.from_raw(raw)

    def test_missing_work_branch_raises(self):
        raw = {**_BASE_RAW, "work_branch": ""}
        with pytest.raises(ValueError, match="work_branch"):
            ReleaseAddendum.from_raw(raw)

    def test_missing_worktree_key_raises(self):
        raw = {**_BASE_RAW, "worktree_key": None}
        with pytest.raises(ValueError, match="worktree_key"):
            ReleaseAddendum.from_raw(raw)

    def test_missing_queued_at_raises(self):
        raw = {**_BASE_RAW, "queued_at": ""}
        with pytest.raises(ValueError, match="queued_at"):
            ReleaseAddendum.from_raw(raw)

    def test_scalar_commits_string_treated_as_list(self):
        """A single string for commits is acceptable (partial compat)."""
        raw = {**_BASE_RAW, "commits": "abc123"}
        a = ReleaseAddendum.from_raw(raw)
        assert a.commits == ["abc123"]

    def test_lease_fields_parsed_when_present(self):
        raw = {
            **_BASE_RAW,
            "claimed_by": "worker-1",
            "lease_expires_at": "2026-07-13T13:00:00Z",
        }
        a = ReleaseAddendum.from_raw(raw)
        assert a.claimed_by == "worker-1"
        assert a.lease_expires_at == "2026-07-13T13:00:00Z"

    def test_lease_fields_absent_default_none(self):
        a = ReleaseAddendum.from_raw(_BASE_RAW)
        assert a.claimed_by is None
        assert a.lease_expires_at is None

    def test_all_status_values_parsed(self):
        for status in AddendumStatus:
            raw = {**_BASE_RAW, "status": status.value}
            a = ReleaseAddendum.from_raw(raw)
            assert a.status == status


# ---------------------------------------------------------------------------
# ReleaseAddendum.to_raw
# ---------------------------------------------------------------------------


class TestReleaseAddendumToRaw:
    """ReleaseAddendum.to_raw serialises all fields correctly."""

    def test_round_trip(self):
        a = ReleaseAddendum.from_raw(_BASE_RAW)
        raw = a.to_raw()
        a2 = ReleaseAddendum.from_raw(raw)
        assert a == a2

    def test_status_serialised_as_string(self):
        a = _make_addendum(status=AddendumStatus.IN_REVIEW)
        raw = a.to_raw()
        assert raw["status"] == "in_review"

    def test_commits_list_copied(self):
        commits = ["abc", "def"]
        a = _make_addendum(commits=commits)
        raw = a.to_raw()
        # Modifying original should not affect serialised value
        commits.append("ghi")
        assert raw["commits"] == ["abc", "def"]

    def test_null_fields_explicit_in_output(self):
        a = _make_addendum()
        raw = a.to_raw()
        assert "started_at" in raw
        assert "completed_at" in raw
        assert "pr_url" in raw
        assert "error" in raw
        assert raw["started_at"] is None
        assert raw["pr_url"] is None

    def test_lease_fields_omitted_when_none(self):
        a = _make_addendum()
        raw = a.to_raw()
        assert "claimed_by" not in raw
        assert "lease_expires_at" not in raw

    def test_lease_fields_included_when_set(self):
        a = _make_addendum()
        a.claimed_by = "worker-1"
        a.lease_expires_at = "2026-07-13T13:00:00Z"
        raw = a.to_raw()
        assert raw["claimed_by"] == "worker-1"
        assert raw["lease_expires_at"] == "2026-07-13T13:00:00Z"

    def test_result_commits_list_included(self):
        a = _make_addendum()
        a.result_commits = ["sha1", "sha2"]
        raw = a.to_raw()
        assert raw["result_commits"] == ["sha1", "sha2"]


# ---------------------------------------------------------------------------
# parse_addendums
# ---------------------------------------------------------------------------


class TestParseAddendums:
    """parse_addendums top-level helper."""

    def test_none_returns_empty(self):
        assert parse_addendums(None) == []

    def test_empty_list_returns_empty(self):
        assert parse_addendums([]) == []

    def test_single_dict_in_list(self):
        result = parse_addendums([_BASE_RAW])
        assert len(result) == 1
        assert result[0].id == "FOO-10/release/1.0"

    def test_single_dict_scalar_wrapped(self):
        """A bare dict is treated as a one-element list."""
        result = parse_addendums(_BASE_RAW)
        assert len(result) == 1

    def test_multiple_dicts(self):
        raw2 = {**_BASE_RAW, "id": "FOO-10/release/2.0", "target_branch": "release/2.0"}
        result = parse_addendums([_BASE_RAW, raw2])
        assert len(result) == 2
        assert result[1].target_branch == "release/2.0"

    def test_malformed_entry_raises(self):
        with pytest.raises(ValueError):
            parse_addendums([{**_BASE_RAW, "id": ""}])

    def test_non_list_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be a list or null"):
            parse_addendums("release/1.0")

    def test_integer_raises(self):
        with pytest.raises(ValueError, match="must be a list or null"):
            parse_addendums(42)


# ---------------------------------------------------------------------------
# addendums_to_raw
# ---------------------------------------------------------------------------


class TestAddendumToRaw:
    """addendums_to_raw serialises a list of ReleaseAddendum objects."""

    def test_empty_list(self):
        assert addendums_to_raw([]) == []

    def test_single_addendum(self):
        a = _make_addendum()
        raw = addendums_to_raw([a])
        assert isinstance(raw, list)
        assert len(raw) == 1
        assert raw[0]["id"] == "FOO-10/release/1.0"

    def test_round_trip(self):
        originals = [_BASE_RAW, {**_BASE_RAW, "id": "FOO-10/release/2.0", "target_branch": "release/2.0"}]
        parsed = parse_addendums(originals)
        serialised = addendums_to_raw(parsed)
        re_parsed = parse_addendums(serialised)
        assert re_parsed == parsed

    def test_multiple_addendums(self):
        a1 = _make_addendum(id="FOO-10/release/1.0", target_branch="release/1.0")
        a2 = _make_addendum(id="FOO-10/release/2.0", target_branch="release/2.0")
        raw = addendums_to_raw([a1, a2])
        assert raw[0]["target_branch"] == "release/1.0"
        assert raw[1]["target_branch"] == "release/2.0"


# ---------------------------------------------------------------------------
# _validate_no_duplicate_active_targets
# ---------------------------------------------------------------------------


class TestValidateNoDuplicateActiveTargets:
    """_validate_no_duplicate_active_targets enforces one active per branch."""

    def test_empty_list_passes(self):
        _validate_no_duplicate_active_targets([])

    def test_single_active_passes(self):
        _validate_no_duplicate_active_targets([_make_addendum()])

    def test_two_different_branches_pass(self):
        a1 = _make_addendum(target_branch="release/1.0", id="F/release/1.0")
        a2 = _make_addendum(target_branch="release/2.0", id="F/release/2.0")
        _validate_no_duplicate_active_targets([a1, a2])

    def test_duplicate_active_same_branch_raises(self):
        a1 = _make_addendum(id="F/release/1.0-v1", target_branch="release/1.0")
        a2 = _make_addendum(id="F/release/1.0-v2", target_branch="release/1.0")
        with pytest.raises(DuplicateTargetError, match="release/1.0"):
            _validate_no_duplicate_active_targets([a1, a2])

    def test_archived_plus_active_same_branch_passes(self):
        """One archived + one active for the same branch is allowed."""
        archived = _make_addendum(status=AddendumStatus.ARCHIVED, id="F/r1.0-old")
        active = _make_addendum(status=AddendumStatus.OPEN, id="F/r1.0-new")
        # Both target the same branch; only active counts
        _validate_no_duplicate_active_targets([archived, active])

    def test_merged_plus_active_same_branch_passes(self):
        merged = _make_addendum(status=AddendumStatus.MERGED, id="F/r1.0-old")
        active = _make_addendum(status=AddendumStatus.OPEN, id="F/r1.0-new")
        _validate_no_duplicate_active_targets([merged, active])

    def test_two_archived_same_branch_passes(self):
        a1 = _make_addendum(status=AddendumStatus.ARCHIVED, id="F/r1.0-v1")
        a2 = _make_addendum(status=AddendumStatus.ARCHIVED, id="F/r1.0-v2")
        _validate_no_duplicate_active_targets([a1, a2])


# ---------------------------------------------------------------------------
# AddendumRepository.read
# ---------------------------------------------------------------------------


class TestAddendumRepositoryRead:
    """AddendumRepository.read delegates to tracker.get_metadata."""

    def test_read_returns_parsed_list(self):
        tracker = _make_tracker([_make_addendum()])
        repo = AddendumRepository(tracker)
        result = repo.read("FOO-10")
        tracker.get_metadata.assert_called_once_with("FOO-10")
        assert len(result) == 1
        assert result[0].id == "FOO-10/release/1.0"

    def test_read_empty_when_field_absent(self):
        tracker = MagicMock()
        tracker.get_metadata.return_value = {}
        repo = AddendumRepository(tracker)
        assert repo.read("FOO-10") == []

    def test_read_empty_when_field_is_none(self):
        tracker = MagicMock()
        tracker.get_metadata.return_value = {"oompah.release_addendums": None}
        repo = AddendumRepository(tracker)
        assert repo.read("FOO-10") == []


# ---------------------------------------------------------------------------
# AddendumRepository.write
# ---------------------------------------------------------------------------


class TestAddendumRepositoryWrite:
    """AddendumRepository.write validates and persists to set_metadata_field."""

    def test_write_calls_set_metadata_field(self):
        tracker = MagicMock()
        repo = AddendumRepository(tracker)
        a = _make_addendum()
        repo.write("FOO-10", [a])
        tracker.set_metadata_field.assert_called_once_with(
            "FOO-10",
            "oompah.release_addendums",
            [a.to_raw()],
        )

    def test_write_empty_list(self):
        tracker = MagicMock()
        repo = AddendumRepository(tracker)
        repo.write("FOO-10", [])
        tracker.set_metadata_field.assert_called_once_with(
            "FOO-10", "oompah.release_addendums", []
        )

    def test_write_preserves_unrelated_metadata(self):
        """write only sets oompah.release_addendums; other fields are unchanged."""
        tracker = MagicMock()
        tracker.get_metadata.return_value = {
            "oompah.release_addendums": None,
            "oompah.work_branch": "my-feature-branch",
        }
        repo = AddendumRepository(tracker)
        a = _make_addendum()
        repo.write("FOO-10", [a])
        # set_metadata_field must only be called with the addendum key
        calls = tracker.set_metadata_field.call_args_list
        assert all(c[0][1] == "oompah.release_addendums" for c in calls)
        assert len(calls) == 1

    def test_write_rejects_duplicate_active_targets(self):
        tracker = MagicMock()
        repo = AddendumRepository(tracker)
        a1 = _make_addendum(id="FOO-10/release/1.0-v1", target_branch="release/1.0")
        a2 = _make_addendum(id="FOO-10/release/1.0-v2", target_branch="release/1.0")
        with pytest.raises(DuplicateTargetError):
            repo.write("FOO-10", [a1, a2])
        tracker.set_metadata_field.assert_not_called()


# ---------------------------------------------------------------------------
# AddendumRepository.add
# ---------------------------------------------------------------------------


class TestAddendumRepositoryAdd:
    """AddendumRepository.add is idempotent on active duplicates."""

    def test_add_new_entry(self):
        tracker = _make_tracker(addendums=[])
        repo = AddendumRepository(tracker)
        a = _make_addendum()
        result = repo.add("FOO-10", a)
        assert len(result) == 1
        tracker.set_metadata_field.assert_called_once()

    def test_add_idempotent_when_active_exists(self):
        """Adding the same branch again when an active addendum exists is a no-op."""
        existing = _make_addendum(status=AddendumStatus.OPEN)
        tracker = _make_tracker(addendums=[existing])
        repo = AddendumRepository(tracker)
        new_a = _make_addendum(id="FOO-10/release/1.0-new", target_branch="release/1.0")
        result = repo.add("FOO-10", new_a, existing=[existing])
        assert len(result) == 1
        tracker.set_metadata_field.assert_not_called()

    def test_add_allowed_when_only_archived_exists(self):
        archived = _make_addendum(status=AddendumStatus.ARCHIVED, id="FOO-10/release/1.0-old")
        tracker = _make_tracker(addendums=[archived])
        repo = AddendumRepository(tracker)
        new_a = _make_addendum(status=AddendumStatus.OPEN, id="FOO-10/release/1.0-new")
        result = repo.add("FOO-10", new_a, existing=[archived])
        assert len(result) == 2
        tracker.set_metadata_field.assert_called_once()

    def test_add_allowed_when_only_merged_exists(self):
        merged = _make_addendum(status=AddendumStatus.MERGED, id="FOO-10/release/1.0-old")
        tracker = _make_tracker(addendums=[merged])
        repo = AddendumRepository(tracker)
        new_a = _make_addendum(status=AddendumStatus.OPEN, id="FOO-10/release/1.0-new")
        result = repo.add("FOO-10", new_a, existing=[merged])
        assert len(result) == 2
        tracker.set_metadata_field.assert_called_once()

    def test_add_reads_tracker_when_existing_not_provided(self):
        tracker = _make_tracker(addendums=[])
        repo = AddendumRepository(tracker)
        a = _make_addendum()
        repo.add("FOO-10", a)
        tracker.get_metadata.assert_called_once_with("FOO-10")

    def test_add_second_different_branch(self):
        a1 = _make_addendum(target_branch="release/1.0", id="FOO-10/release/1.0")
        a2 = _make_addendum(target_branch="release/2.0", id="FOO-10/release/2.0")
        tracker = _make_tracker(addendums=[a1])
        repo = AddendumRepository(tracker)
        result = repo.add("FOO-10", a2, existing=[a1])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# AddendumRepository.transition
# ---------------------------------------------------------------------------


class TestAddendumRepositoryTransition:
    """AddendumRepository.transition validates and applies lifecycle changes."""

    def test_valid_transition_open_to_in_progress(self):
        a = _make_addendum(id="FOO-10/release/1.0", status=AddendumStatus.OPEN)
        tracker = _make_tracker(addendums=[a])
        repo = AddendumRepository(tracker)
        result = repo.transition(
            "FOO-10",
            "FOO-10/release/1.0",
            AddendumStatus.IN_PROGRESS,
            existing=[a],
            claimed_by="worker-1",
            started_at="2026-07-13T12:01:00Z",
        )
        assert result[0].status == AddendumStatus.IN_PROGRESS
        assert result[0].claimed_by == "worker-1"
        assert result[0].started_at == "2026-07-13T12:01:00Z"

    def test_valid_transition_in_progress_to_in_review(self):
        a = _make_addendum(status=AddendumStatus.IN_PROGRESS)
        repo = AddendumRepository(MagicMock())
        repo._tracker.get_metadata.return_value = {}

        with pytest.MonkeyPatch().context() as mp:
            # Patch write to no-op so we can inspect the return value
            wrote: list = []
            mp.setattr(repo, "write", lambda ident, lst: wrote.extend(lst))
            result = repo.transition(
                "FOO-10",
                "FOO-10/release/1.0",
                AddendumStatus.IN_REVIEW,
                existing=[a],
                pr_url="https://github.com/org/repo/pull/42",
            )
        assert result[0].status == AddendumStatus.IN_REVIEW
        assert result[0].pr_url == "https://github.com/org/repo/pull/42"

    def test_commits_immutable_across_transition(self):
        original_commits = ["sha-abc"]
        a = _make_addendum(commits=list(original_commits))
        repo = AddendumRepository(MagicMock())

        captured: list = []
        repo.write = lambda ident, lst: captured.extend(lst)
        repo.transition(
            "FOO-10",
            "FOO-10/release/1.0",
            AddendumStatus.IN_PROGRESS,
            existing=[a],
        )
        assert captured[0].commits == original_commits

    def test_invalid_transition_raises(self):
        a = _make_addendum(status=AddendumStatus.MERGED)
        tracker = _make_tracker(addendums=[a])
        repo = AddendumRepository(tracker)
        with pytest.raises(InvalidTransitionError, match="merged.*open"):
            repo.transition("FOO-10", "FOO-10/release/1.0", AddendumStatus.OPEN, existing=[a])

    def test_missing_addendum_raises_key_error(self):
        tracker = _make_tracker(addendums=[])
        repo = AddendumRepository(tracker)
        with pytest.raises(KeyError, match="nonexistent-id"):
            repo.transition("FOO-10", "nonexistent-id", AddendumStatus.IN_PROGRESS, existing=[])

    def test_unknown_kwarg_raises(self):
        a = _make_addendum()
        tracker = _make_tracker(addendums=[a])
        repo = AddendumRepository(tracker)
        with pytest.raises(ValueError, match="Unexpected keyword arguments"):
            repo.transition(
                "FOO-10",
                "FOO-10/release/1.0",
                AddendumStatus.IN_PROGRESS,
                existing=[a],
                commits=["new-sha"],  # not an evidence field
            )

    def test_blocked_to_open_retry(self):
        a = _make_addendum(status=AddendumStatus.BLOCKED)
        repo = AddendumRepository(MagicMock())
        captured: list = []
        repo.write = lambda ident, lst: captured.extend(lst)
        result = repo.transition(
            "FOO-10",
            "FOO-10/release/1.0",
            AddendumStatus.OPEN,
            existing=[a],
        )
        assert result[0].status == AddendumStatus.OPEN

    def test_in_review_to_open_retry(self):
        a = _make_addendum(status=AddendumStatus.IN_REVIEW)
        repo = AddendumRepository(MagicMock())
        captured: list = []
        repo.write = lambda ident, lst: captured.extend(lst)
        result = repo.transition(
            "FOO-10",
            "FOO-10/release/1.0",
            AddendumStatus.OPEN,
            existing=[a],
        )
        assert result[0].status == AddendumStatus.OPEN

    def test_open_to_archived_cancel(self):
        a = _make_addendum(status=AddendumStatus.OPEN)
        repo = AddendumRepository(MagicMock())
        captured: list = []
        repo.write = lambda ident, lst: captured.extend(lst)
        result = repo.transition(
            "FOO-10",
            "FOO-10/release/1.0",
            AddendumStatus.ARCHIVED,
            existing=[a],
        )
        assert result[0].status == AddendumStatus.ARCHIVED

    def test_error_field_set_on_blocked(self):
        a = _make_addendum(status=AddendumStatus.IN_PROGRESS)
        repo = AddendumRepository(MagicMock())
        captured: list = []
        repo.write = lambda ident, lst: captured.extend(lst)
        result = repo.transition(
            "FOO-10",
            "FOO-10/release/1.0",
            AddendumStatus.BLOCKED,
            existing=[a],
            error="conflict on src/foo.py",
        )
        assert result[0].error == "conflict on src/foo.py"

    def test_evidence_fields_not_cleared_by_default(self):
        """Existing evidence fields are preserved when not passed in the transition."""
        a = _make_addendum(status=AddendumStatus.IN_REVIEW)
        a.pr_url = "https://github.com/org/repo/pull/99"
        a.result_commits = ["sha1"]

        repo = AddendumRepository(MagicMock())
        captured: list = []
        repo.write = lambda ident, lst: captured.extend(lst)
        result = repo.transition(
            "FOO-10",
            "FOO-10/release/1.0",
            AddendumStatus.MERGED,
            existing=[a],
        )
        assert result[0].pr_url == "https://github.com/org/repo/pull/99"
        assert result[0].result_commits == ["sha1"]

    def test_transition_reads_tracker_when_existing_not_provided(self):
        a = _make_addendum()
        tracker = _make_tracker(addendums=[a])
        repo = AddendumRepository(tracker)
        captured: list = []
        repo.write = lambda ident, lst: captured.extend(lst)
        repo.transition("FOO-10", "FOO-10/release/1.0", AddendumStatus.IN_PROGRESS)
        tracker.get_metadata.assert_called_once_with("FOO-10")

    def test_other_addendums_in_list_preserved(self):
        a1 = _make_addendum(id="FOO-10/release/1.0", target_branch="release/1.0", status=AddendumStatus.OPEN)
        a2 = _make_addendum(id="FOO-10/release/2.0", target_branch="release/2.0", status=AddendumStatus.OPEN)
        repo = AddendumRepository(MagicMock())
        captured: list = []
        repo.write = lambda ident, lst: captured.extend(lst)
        result = repo.transition(
            "FOO-10",
            "FOO-10/release/1.0",
            AddendumStatus.IN_PROGRESS,
            existing=[a1, a2],
        )
        assert len(result) == 2
        # Second addendum unchanged
        assert result[1].status == AddendumStatus.OPEN
        assert result[1].id == "FOO-10/release/2.0"


# ---------------------------------------------------------------------------
# Escaping / sanitisation round-trip
# ---------------------------------------------------------------------------


class TestSanitizationDeterminism:
    """Sanitization helpers are deterministic and handle edge cases."""

    @pytest.mark.parametrize("source,target,expected_work_branch,expected_key", [
        ("FOO-10", "release/1.0", "oompah/release/FOO-10/release-1.0", "release-FOO-10-release-1.0"),
        ("BAR-99", "release/2.11", "oompah/release/BAR-99/release-2.11", "release-BAR-99-release-2.11"),
        ("XYZ/epic/3", "release/1.1", "oompah/release/XYZ-epic-3/release-1.1", "release-XYZ-epic-3-release-1.1"),
        ("A B", "release/x y", "oompah/release/A-B/release-x-y", "release-A-B-release-x-y"),
    ])
    def test_deterministic_escaping(self, source, target, expected_work_branch, expected_key):
        assert make_work_branch(source, target) == expected_work_branch
        assert make_worktree_key(source, target) == expected_key

    def test_make_addendum_id_preserves_slashes(self):
        """The addendum ID preserves raw values; it is not sanitized."""
        assert make_addendum_id("FOO-10", "release/1.0") == "FOO-10/release/1.0"

    def test_make_work_branch_called_twice_same_result(self):
        for _ in range(3):
            assert make_work_branch("A-1", "release/1.0") == "oompah/release/A-1/release-1.0"
