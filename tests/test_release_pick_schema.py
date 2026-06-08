"""Tests for the release-pick metadata schema and status lifecycle (TASK-454.4).

Covers:
  - ReleasePick enum: all values present, from_raw normalisation,
    is_terminal / is_blocked properties
  - VALID_TRANSITIONS: structural invariants and key forward/blocked paths
  - is_valid_transition: allowed, disallowed, and self-transitions
  - BackportEntry: from_raw (string / dict / errors), to_raw round-trips
  - BackportOf: from_raw (string / dict / errors), to_raw round-trips
  - parse_backports: None, scalar, list-of-strings, list-of-dicts, mixed
  - parse_backport_of: None, string, dict forms
  - backports_to_raw: round-trip through parse + serialise
"""

from __future__ import annotations

import pytest

from oompah.release_pick_schema import (
    BackportEntry,
    BackportOf,
    ReleasePick,
    VALID_TRANSITIONS,
    backports_to_raw,
    is_valid_transition,
    parse_backport_of,
    parse_backports,
)


# ---------------------------------------------------------------------------
# ReleasePick enum basics
# ---------------------------------------------------------------------------


class TestReleasePickValues:
    """All documented status values must be present as enum members."""

    def test_all_expected_values_exist(self):
        expected = {
            "waiting",
            "task_created",
            "cherry_picking",
            "pr_open",
            "conflict",
            "merged",
            "archived",
            "needs_human",
            "skipped",
        }
        assert {m.value for m in ReleasePick} == expected

    def test_enum_inherits_str(self):
        assert isinstance(ReleasePick.WAITING, str)
        assert ReleasePick.WAITING == "waiting"

    def test_str_value_is_lowercase(self):
        for member in ReleasePick:
            assert member.value == member.value.lower(), (
                f"{member.name}.value should be lowercase, got {member.value!r}"
            )


class TestReleasePickFromRaw:
    """ReleasePick.from_raw normalises various inputs."""

    @pytest.mark.parametrize("raw,expected", [
        ("waiting", ReleasePick.WAITING),
        ("task_created", ReleasePick.TASK_CREATED),
        ("cherry_picking", ReleasePick.CHERRY_PICKING),
        ("pr_open", ReleasePick.PR_OPEN),
        ("conflict", ReleasePick.CONFLICT),
        ("merged", ReleasePick.MERGED),
        ("archived", ReleasePick.ARCHIVED),
        ("needs_human", ReleasePick.NEEDS_HUMAN),
    ])
    def test_parses_exact_value(self, raw, expected):
        assert ReleasePick.from_raw(raw) == expected

    def test_case_insensitive(self):
        assert ReleasePick.from_raw("MERGED") == ReleasePick.MERGED
        assert ReleasePick.from_raw("Waiting") == ReleasePick.WAITING
        assert ReleasePick.from_raw("Cherry_Picking") == ReleasePick.CHERRY_PICKING

    def test_hyphen_normalised_to_underscore(self):
        assert ReleasePick.from_raw("cherry-picking") == ReleasePick.CHERRY_PICKING
        assert ReleasePick.from_raw("pr-open") == ReleasePick.PR_OPEN
        assert ReleasePick.from_raw("needs-human") == ReleasePick.NEEDS_HUMAN
        assert ReleasePick.from_raw("task-created") == ReleasePick.TASK_CREATED

    def test_none_returns_waiting(self):
        assert ReleasePick.from_raw(None) == ReleasePick.WAITING

    def test_empty_string_returns_waiting(self):
        assert ReleasePick.from_raw("") == ReleasePick.WAITING

    def test_unknown_value_returns_waiting(self):
        assert ReleasePick.from_raw("bogus") == ReleasePick.WAITING

    def test_idempotent_on_enum_instance(self):
        assert ReleasePick.from_raw(ReleasePick.PR_OPEN) == ReleasePick.PR_OPEN


class TestReleasePickProperties:
    """is_terminal and is_blocked properties."""

    @pytest.mark.parametrize("status", [ReleasePick.MERGED, ReleasePick.ARCHIVED])
    def test_terminal_statuses(self, status):
        assert status.is_terminal is True

    @pytest.mark.parametrize("status", [
        ReleasePick.WAITING,
        ReleasePick.TASK_CREATED,
        ReleasePick.CHERRY_PICKING,
        ReleasePick.PR_OPEN,
        ReleasePick.CONFLICT,
        ReleasePick.NEEDS_HUMAN,
    ])
    def test_non_terminal_statuses(self, status):
        assert status.is_terminal is False

    @pytest.mark.parametrize("status", [
        ReleasePick.CONFLICT,
        ReleasePick.NEEDS_HUMAN,
    ])
    def test_blocked_statuses(self, status):
        assert status.is_blocked is True

    @pytest.mark.parametrize("status", [
        ReleasePick.WAITING,
        ReleasePick.TASK_CREATED,
        ReleasePick.CHERRY_PICKING,
        ReleasePick.PR_OPEN,
        ReleasePick.MERGED,
        ReleasePick.ARCHIVED,
    ])
    def test_non_blocked_statuses(self, status):
        assert status.is_blocked is False


# ---------------------------------------------------------------------------
# VALID_TRANSITIONS invariants
# ---------------------------------------------------------------------------


class TestValidTransitions:
    """Structural invariants for the VALID_TRANSITIONS FSM."""

    def test_all_statuses_are_keys(self):
        """Every ReleasePick member must appear as a key in VALID_TRANSITIONS."""
        for status in ReleasePick:
            assert status in VALID_TRANSITIONS, (
                f"{status.name} missing from VALID_TRANSITIONS"
            )

    def test_terminal_statuses_have_no_forward_transitions(self):
        assert VALID_TRANSITIONS[ReleasePick.MERGED] == frozenset()
        assert VALID_TRANSITIONS[ReleasePick.ARCHIVED] == frozenset()

    def test_waiting_can_advance_to_task_created(self):
        assert ReleasePick.TASK_CREATED in VALID_TRANSITIONS[ReleasePick.WAITING]

    def test_cherry_picking_can_advance_to_pr_open(self):
        assert ReleasePick.PR_OPEN in VALID_TRANSITIONS[ReleasePick.CHERRY_PICKING]

    def test_cherry_picking_can_become_conflict(self):
        assert ReleasePick.CONFLICT in VALID_TRANSITIONS[ReleasePick.CHERRY_PICKING]

    def test_pr_open_can_become_merged(self):
        assert ReleasePick.MERGED in VALID_TRANSITIONS[ReleasePick.PR_OPEN]

    def test_conflict_can_retry_cherry_picking(self):
        assert ReleasePick.CHERRY_PICKING in VALID_TRANSITIONS[ReleasePick.CONFLICT]

    def test_conflict_can_escalate_to_needs_human(self):
        assert ReleasePick.NEEDS_HUMAN in VALID_TRANSITIONS[ReleasePick.CONFLICT]

    def test_needs_human_can_retry_cherry_picking(self):
        assert ReleasePick.CHERRY_PICKING in VALID_TRANSITIONS[ReleasePick.NEEDS_HUMAN]

    def test_all_non_terminal_statuses_can_archive(self):
        """Any non-terminal pick can be abandoned by setting ARCHIVED."""
        for status in ReleasePick:
            if not status.is_terminal:
                assert ReleasePick.ARCHIVED in VALID_TRANSITIONS[status], (
                    f"{status.name} should be able to transition to ARCHIVED"
                )

    def test_all_non_terminal_statuses_can_escalate_to_needs_human(self):
        """Any non-terminal pick (except NEEDS_HUMAN itself) can be escalated to NEEDS_HUMAN."""
        for status in ReleasePick:
            if status.is_terminal or status == ReleasePick.NEEDS_HUMAN:
                continue
            assert ReleasePick.NEEDS_HUMAN in VALID_TRANSITIONS[status], (
                f"{status.name} should be able to transition to NEEDS_HUMAN"
            )


class TestIsValidTransition:
    """is_valid_transition covers allowed, disallowed, and self-transitions."""

    def test_allowed_transition_returns_true(self):
        assert is_valid_transition(ReleasePick.WAITING, ReleasePick.TASK_CREATED)
        assert is_valid_transition(ReleasePick.CHERRY_PICKING, ReleasePick.PR_OPEN)
        assert is_valid_transition(ReleasePick.PR_OPEN, ReleasePick.MERGED)
        assert is_valid_transition(ReleasePick.CONFLICT, ReleasePick.CHERRY_PICKING)

    def test_self_transition_returns_false(self):
        for status in ReleasePick:
            assert is_valid_transition(status, status) is False, (
                f"self-transition {status.name} → {status.name} must be False"
            )

    def test_backwards_transition_returns_false(self):
        # Going backwards from merged to waiting is not allowed
        assert is_valid_transition(ReleasePick.MERGED, ReleasePick.WAITING) is False

    def test_terminal_has_no_valid_successors(self):
        for to_status in ReleasePick:
            assert is_valid_transition(ReleasePick.MERGED, to_status) is False
            assert is_valid_transition(ReleasePick.ARCHIVED, to_status) is False

    def test_skip_intermediate_returns_false(self):
        # Cannot jump from WAITING directly to PR_OPEN (must go through task_created, etc.)
        assert is_valid_transition(ReleasePick.WAITING, ReleasePick.PR_OPEN) is False


# ---------------------------------------------------------------------------
# BackportEntry
# ---------------------------------------------------------------------------


class TestBackportEntryFromRaw:
    """Parsing BackportEntry from raw frontmatter values."""

    def test_plain_string_gives_waiting_status(self):
        entry = BackportEntry.from_raw("release/1.0")
        assert entry.branch == "release/1.0"
        assert entry.status == ReleasePick.WAITING
        assert entry.task_id is None
        assert entry.pr_url is None

    def test_dict_with_branch_only_gives_waiting(self):
        entry = BackportEntry.from_raw({"branch": "release/2.0"})
        assert entry.branch == "release/2.0"
        assert entry.status == ReleasePick.WAITING

    def test_dict_with_all_fields(self):
        entry = BackportEntry.from_raw({
            "branch": "release/3.0",
            "status": "pr_open",
            "task_id": "TASK-100.1",
            "pr_url": "https://github.com/org/repo/pull/42",
        })
        assert entry.branch == "release/3.0"
        assert entry.status == ReleasePick.PR_OPEN
        assert entry.task_id == "TASK-100.1"
        assert entry.pr_url == "https://github.com/org/repo/pull/42"

    def test_dict_with_merged_status(self):
        entry = BackportEntry.from_raw({"branch": "hotfix/1.0.1", "status": "merged"})
        assert entry.status == ReleasePick.MERGED

    def test_dict_with_conflict_status(self):
        entry = BackportEntry.from_raw({"branch": "release/1.0", "status": "conflict"})
        assert entry.status == ReleasePick.CONFLICT

    def test_dict_with_needs_human_status(self):
        entry = BackportEntry.from_raw({"branch": "release/1.0", "status": "needs_human"})
        assert entry.status == ReleasePick.NEEDS_HUMAN

    def test_dict_with_archived_status(self):
        entry = BackportEntry.from_raw({"branch": "release/1.0", "status": "archived"})
        assert entry.status == ReleasePick.ARCHIVED

    def test_dict_missing_branch_raises(self):
        with pytest.raises(ValueError, match="missing required 'branch' key"):
            BackportEntry.from_raw({"status": "waiting"})

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            BackportEntry.from_raw("")

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Cannot parse BackportEntry"):
            BackportEntry.from_raw(42)

    def test_unknown_status_defaults_to_waiting(self):
        entry = BackportEntry.from_raw({"branch": "release/1.0", "status": "bogus"})
        assert entry.status == ReleasePick.WAITING


class TestBackportEntryToRaw:
    """Serialising BackportEntry back to raw frontmatter values."""

    def test_waiting_no_extras_returns_plain_string(self):
        entry = BackportEntry(branch="release/1.0")
        assert entry.to_raw() == "release/1.0"

    def test_non_waiting_status_returns_dict(self):
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.PR_OPEN)
        raw = entry.to_raw()
        assert isinstance(raw, dict)
        assert raw["branch"] == "release/1.0"
        assert raw["status"] == "pr_open"

    def test_task_id_forces_dict_form(self):
        entry = BackportEntry(branch="release/1.0", task_id="TASK-100.1")
        raw = entry.to_raw()
        assert isinstance(raw, dict)
        assert raw["task_id"] == "TASK-100.1"

    def test_pr_url_forces_dict_form(self):
        entry = BackportEntry(branch="release/1.0", pr_url="https://example.com/pr/1")
        raw = entry.to_raw()
        assert isinstance(raw, dict)
        assert raw["pr_url"] == "https://example.com/pr/1"

    def test_full_dict_round_trips(self):
        original = {
            "branch": "release/2.0",
            "status": "merged",
            "task_id": "TASK-200.3",
            "pr_url": "https://github.com/org/repo/pull/99",
        }
        entry = BackportEntry.from_raw(original)
        raw = entry.to_raw()
        assert raw == original

    def test_plain_string_round_trips(self):
        entry = BackportEntry.from_raw("release/1.0")
        assert entry.to_raw() == "release/1.0"

    def test_dict_without_optional_fields_has_no_null_keys(self):
        entry = BackportEntry(branch="release/1.0", status=ReleasePick.CONFLICT)
        raw = entry.to_raw()
        assert isinstance(raw, dict)
        assert "task_id" not in raw
        assert "pr_url" not in raw


# ---------------------------------------------------------------------------
# BackportOf
# ---------------------------------------------------------------------------


class TestBackportOfFromRaw:
    """Parsing BackportOf from raw frontmatter values."""

    def test_plain_string_gives_waiting_status(self):
        bof = BackportOf.from_raw("TASK-100")
        assert bof.source == "TASK-100"
        assert bof.status == ReleasePick.WAITING

    def test_dict_with_source_only(self):
        bof = BackportOf.from_raw({"source": "TASK-200"})
        assert bof.source == "TASK-200"
        assert bof.status == ReleasePick.WAITING

    def test_dict_with_source_and_status(self):
        bof = BackportOf.from_raw({"source": "TASK-300", "status": "cherry_picking"})
        assert bof.source == "TASK-300"
        assert bof.status == ReleasePick.CHERRY_PICKING

    def test_dict_all_statuses(self):
        for status in ReleasePick:
            bof = BackportOf.from_raw({"source": "TASK-1", "status": status.value})
            assert bof.status == status

    def test_dict_missing_source_raises(self):
        with pytest.raises(ValueError, match="missing required 'source' key"):
            BackportOf.from_raw({"status": "waiting"})

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            BackportOf.from_raw("")

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Cannot parse BackportOf"):
            BackportOf.from_raw(123)

    def test_unknown_status_defaults_to_waiting(self):
        bof = BackportOf.from_raw({"source": "TASK-1", "status": "bogus"})
        assert bof.status == ReleasePick.WAITING


class TestBackportOfToRaw:
    """Serialising BackportOf back to raw frontmatter values."""

    def test_waiting_status_returns_plain_string(self):
        bof = BackportOf(source="TASK-100")
        assert bof.to_raw() == "TASK-100"

    def test_non_waiting_status_returns_dict(self):
        bof = BackportOf(source="TASK-100", status=ReleasePick.PR_OPEN)
        raw = bof.to_raw()
        assert raw == {"source": "TASK-100", "status": "pr_open"}

    def test_plain_string_round_trips(self):
        bof = BackportOf.from_raw("TASK-100")
        assert bof.to_raw() == "TASK-100"

    def test_dict_round_trips(self):
        original = {"source": "TASK-100", "status": "merged"}
        bof = BackportOf.from_raw(original)
        assert bof.to_raw() == original

    def test_all_non_waiting_statuses_produce_dict(self):
        for status in ReleasePick:
            if status == ReleasePick.WAITING:
                continue
            bof = BackportOf(source="TASK-1", status=status)
            raw = bof.to_raw()
            assert isinstance(raw, dict), f"expected dict for status {status.name}"
            assert raw["status"] == status.value


# ---------------------------------------------------------------------------
# parse_backports
# ---------------------------------------------------------------------------


class TestParseBackports:
    """Top-level parse_backports helper."""

    def test_none_returns_empty_list(self):
        assert parse_backports(None) == []

    def test_empty_list_returns_empty_list(self):
        assert parse_backports([]) == []

    def test_scalar_string_returns_one_entry(self):
        entries = parse_backports("release/1.0")
        assert len(entries) == 1
        assert entries[0].branch == "release/1.0"
        assert entries[0].status == ReleasePick.WAITING

    def test_list_of_strings(self):
        entries = parse_backports(["release/1.0", "release/2.0"])
        assert len(entries) == 2
        assert entries[0].branch == "release/1.0"
        assert entries[1].branch == "release/2.0"

    def test_list_of_dicts(self):
        raw = [
            {"branch": "release/1.0", "status": "waiting"},
            {"branch": "release/2.0", "status": "merged", "task_id": "TASK-100.1"},
        ]
        entries = parse_backports(raw)
        assert len(entries) == 2
        assert entries[0].status == ReleasePick.WAITING
        assert entries[1].status == ReleasePick.MERGED
        assert entries[1].task_id == "TASK-100.1"

    def test_mixed_list(self):
        """String and dict entries can appear together in a list."""
        raw = [
            "release/1.0",
            {"branch": "release/2.0", "status": "pr_open"},
        ]
        entries = parse_backports(raw)
        assert entries[0].branch == "release/1.0"
        assert entries[0].status == ReleasePick.WAITING
        assert entries[1].branch == "release/2.0"
        assert entries[1].status == ReleasePick.PR_OPEN

    def test_scalar_dict_returns_one_entry(self):
        entries = parse_backports({"branch": "release/1.0", "status": "conflict"})
        assert len(entries) == 1
        assert entries[0].status == ReleasePick.CONFLICT

    def test_all_statuses_parsed(self):
        for status in ReleasePick:
            entries = parse_backports([{"branch": "release/1.0", "status": status.value}])
            assert entries[0].status == status, f"failed for {status.name}"


# ---------------------------------------------------------------------------
# parse_backport_of
# ---------------------------------------------------------------------------


class TestParseBackportOf:
    """Top-level parse_backport_of helper."""

    def test_none_returns_none(self):
        assert parse_backport_of(None) is None

    def test_empty_string_returns_none(self):
        assert parse_backport_of("") is None

    def test_plain_string(self):
        bof = parse_backport_of("TASK-100")
        assert bof is not None
        assert bof.source == "TASK-100"
        assert bof.status == ReleasePick.WAITING

    def test_dict_with_status(self):
        bof = parse_backport_of({"source": "TASK-200", "status": "pr_open"})
        assert bof is not None
        assert bof.source == "TASK-200"
        assert bof.status == ReleasePick.PR_OPEN


# ---------------------------------------------------------------------------
# backports_to_raw
# ---------------------------------------------------------------------------


class TestBackportsToRaw:
    """backports_to_raw serialises a list of BackportEntry objects."""

    def test_empty_list_returns_empty_list(self):
        assert backports_to_raw([]) == []

    def test_waiting_entries_serialise_as_strings(self):
        entries = [BackportEntry(branch="release/1.0"), BackportEntry(branch="release/2.0")]
        raw = backports_to_raw(entries)
        assert raw == ["release/1.0", "release/2.0"]

    def test_non_waiting_entries_serialise_as_dicts(self):
        entries = [
            BackportEntry(branch="release/1.0", status=ReleasePick.MERGED),
        ]
        raw = backports_to_raw(entries)
        assert raw == [{"branch": "release/1.0", "status": "merged"}]

    def test_round_trip_through_parse_and_serialise(self):
        original = [
            "release/1.0",
            {"branch": "release/2.0", "status": "pr_open", "task_id": "TASK-100.2"},
        ]
        entries = parse_backports(original)
        serialised = backports_to_raw(entries)
        assert serialised == original

    def test_mixed_compact_and_rich_forms(self):
        entries = [
            BackportEntry(branch="release/1.0"),
            BackportEntry(branch="release/2.0", status=ReleasePick.CONFLICT),
        ]
        raw = backports_to_raw(entries)
        assert raw[0] == "release/1.0"
        assert raw[1] == {"branch": "release/2.0", "status": "conflict"}
