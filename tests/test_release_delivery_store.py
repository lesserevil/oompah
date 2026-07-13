"""Tests for oompah.release_delivery_store (OOMPAH-193).

Covers:
  - SourceKind enum: all values, from_raw, invalid inputs
  - ReleaseDelivery.from_raw: valid full record, missing required fields,
    bad SHA format, source-kind/source-identifier invariant, all status values
  - ReleaseDelivery.to_raw: all fields serialised, round-trip fidelity
  - ReleaseDeliveryLedger.empty: returns version-1 empty ledger
  - ReleaseDeliveryLedger.from_raw: valid, missing version, wrong version,
    non-dict root, non-list deliveries, malformed entry
  - ReleaseDeliveryLedger.to_raw: round-trip
  - LedgerParseError / ImmutableFieldError / DeliveryNotFoundError
  - ReleaseDeliveryStore.read_ledger: missing file → empty; malformed → raise;
    valid → parsed; bad YAML → raise
  - ReleaseDeliveryStore.append: success, duplicate ID rejected, malformed
    ledger not overwritten, project_id mismatch rejected
  - ReleaseDeliveryStore.lookup_by_id: found, not found
  - ReleaseDeliveryStore.lookup_by_source_identifier: matches, empty, commits kind excluded
  - ReleaseDeliveryStore.update: valid transition, immutable field protection,
    unknown fields rejected, not found, invalid transition, source_commits preserved,
    result_commits SHA validation, evidence fields preserved when not supplied
  - Concurrent locking: concurrent append/update under project-level lock
  - OompahMarkdownTracker.write_and_commit_ledger_file: git path integration
    (uses a real git repository fixture)
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.release_addendum_schema import AddendumStatus, InvalidTransitionError
from oompah.release_delivery_store import (
    LEDGER_PATH,
    LEDGER_VERSION,
    DeliveryNotFoundError,
    ImmutableFieldError,
    LedgerParseError,
    ReleaseDelivery,
    ReleaseDeliveryLedger,
    ReleaseDeliveryStore,
    SourceKind,
    _delivery_lock,
    _validate_full_sha,
)
from oompah.tracker import TrackerError

# ---------------------------------------------------------------------------
# Test helpers / fixtures
# ---------------------------------------------------------------------------

_SHA_A = "a" * 40
_SHA_B = "b" * 40
_SHA_C = "c" * 40
_SHA_RESULT = "1" * 40

_QUEUED_AT = "2026-07-13T12:00:00Z"


def _make_delivery(
    *,
    id: str = "rd_01J",
    project_id: str = "proj-123",
    source_branch: str = "main",
    source_kind: SourceKind = SourceKind.TASK,
    source_identifier: str | None = "FOO-10",
    source_commits: list[str] | None = None,
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.OPEN,
    queued_at: str = _QUEUED_AT,
    **extra,
) -> ReleaseDelivery:
    return ReleaseDelivery(
        id=id,
        project_id=project_id,
        source_branch=source_branch,
        source_kind=source_kind,
        source_identifier=source_identifier,
        source_commits=source_commits if source_commits is not None else [_SHA_A],
        target_branch=target_branch,
        status=status,
        queued_at=queued_at,
        **extra,
    )


def _make_store(tmp_path: Path, project_id: str = "proj-123") -> ReleaseDeliveryStore:
    """Return a ReleaseDeliveryStore with no git_writer (filesystem-only)."""
    return ReleaseDeliveryStore(
        project_root=tmp_path,
        project_id=project_id,
    )


def _write_raw_ledger(tmp_path: Path, data: object) -> None:
    """Write raw *data* as YAML to the ledger path for setup."""
    ledger_path = tmp_path / LEDGER_PATH
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(yaml.safe_dump(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# SourceKind enum
# ---------------------------------------------------------------------------


class TestSourceKindValues:
    def test_all_expected_values(self):
        expected = {"task", "epic", "commits"}
        assert {m.value for m in SourceKind} == expected

    def test_enum_inherits_str(self):
        assert isinstance(SourceKind.TASK, str)
        assert SourceKind.TASK == "task"

    def test_all_values_lowercase(self):
        for m in SourceKind:
            assert m.value == m.value.lower()


class TestSourceKindFromRaw:
    @pytest.mark.parametrize("raw,expected", [
        ("task", SourceKind.TASK),
        ("epic", SourceKind.EPIC),
        ("commits", SourceKind.COMMITS),
        ("TASK", SourceKind.TASK),
        ("Epic", SourceKind.EPIC),
    ])
    def test_parses_known_values(self, raw, expected):
        assert SourceKind.from_raw(raw) == expected

    def test_idempotent_on_enum_instance(self):
        assert SourceKind.from_raw(SourceKind.EPIC) is SourceKind.EPIC

    def test_none_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            SourceKind.from_raw(None)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            SourceKind.from_raw("")

    def test_unknown_value_raises(self):
        with pytest.raises(ValueError, match="Unknown SourceKind"):
            SourceKind.from_raw("pull_request")


# ---------------------------------------------------------------------------
# _validate_full_sha helper
# ---------------------------------------------------------------------------


class TestValidateFullSha:
    def test_valid_40_hex(self):
        _validate_full_sha("a" * 40, "test")  # no exception

    def test_valid_mixed_hex(self):
        _validate_full_sha("0123456789abcdef" * 2 + "01234567", "test")

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="40-character"):
            _validate_full_sha("abc123", "test")

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match="40-character"):
            _validate_full_sha("a" * 41, "test")

    def test_uppercase_raises(self):
        with pytest.raises(ValueError, match="40-character"):
            _validate_full_sha("A" * 40, "test")

    def test_non_hex_raises(self):
        with pytest.raises(ValueError, match="40-character"):
            _validate_full_sha("g" * 40, "test")


# ---------------------------------------------------------------------------
# ReleaseDelivery.from_raw
# ---------------------------------------------------------------------------

_BASE_RAW: dict = {
    "id": "rd_01J",
    "project_id": "proj-123",
    "source_branch": "main",
    "source_kind": "task",
    "source_identifier": "FOO-10",
    "source_commits": [_SHA_A],
    "target_branch": "release/1.0",
    "status": "open",
    "queued_at": _QUEUED_AT,
    "claimed_by": None,
    "lease_expires_at": None,
    "started_at": None,
    "completed_at": None,
    "work_branch": None,
    "pr_url": None,
    "pr_number": None,
    "result_commits": [],
    "error": None,
    "migrated_from": None,
}


class TestReleaseDeliveryFromRaw:
    def test_valid_full_record(self):
        d = ReleaseDelivery.from_raw(_BASE_RAW)
        assert d.id == "rd_01J"
        assert d.project_id == "proj-123"
        assert d.source_branch == "main"
        assert d.source_kind == SourceKind.TASK
        assert d.source_identifier == "FOO-10"
        assert d.source_commits == [_SHA_A]
        assert d.target_branch == "release/1.0"
        assert d.status == AddendumStatus.OPEN
        assert d.queued_at == _QUEUED_AT
        assert d.claimed_by is None
        assert d.result_commits == []
        assert d.migrated_from is None

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            ReleaseDelivery.from_raw("not a dict")

    def test_missing_id_raises(self):
        with pytest.raises(ValueError, match="missing required 'id'"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "id": ""})

    def test_missing_project_id_raises(self):
        with pytest.raises(ValueError, match="project_id"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "project_id": None})

    def test_missing_source_branch_raises(self):
        with pytest.raises(ValueError, match="source_branch"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "source_branch": ""})

    def test_missing_target_branch_raises(self):
        with pytest.raises(ValueError, match="target_branch"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "target_branch": ""})

    def test_missing_queued_at_raises(self):
        with pytest.raises(ValueError, match="queued_at"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "queued_at": None})

    def test_invalid_source_kind_raises(self):
        with pytest.raises(ValueError, match="Unknown SourceKind"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "source_kind": "branch"})

    def test_missing_source_kind_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "source_kind": None})

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="Unknown AddendumStatus"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "status": "waiting"})

    def test_missing_source_commits_raises(self):
        with pytest.raises(ValueError, match="'source_commits'.*nonempty"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "source_commits": []})

    def test_null_source_commits_raises(self):
        with pytest.raises(ValueError, match="source_commits"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "source_commits": None})

    def test_short_sha_in_source_commits_raises(self):
        with pytest.raises(ValueError, match="40-character"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "source_commits": ["abc123"]})

    def test_uppercase_sha_in_source_commits_raises(self):
        with pytest.raises(ValueError, match="40-character"):
            ReleaseDelivery.from_raw({**_BASE_RAW, "source_commits": ["A" * 40]})

    def test_short_sha_in_result_commits_raises(self):
        raw = {**_BASE_RAW, "result_commits": ["badsha"]}
        with pytest.raises(ValueError, match="40-character"):
            ReleaseDelivery.from_raw(raw)

    def test_source_kind_task_requires_identifier(self):
        raw = {**_BASE_RAW, "source_kind": "task", "source_identifier": None}
        with pytest.raises(ValueError, match="source_identifier.*required"):
            ReleaseDelivery.from_raw(raw)

    def test_source_kind_epic_requires_identifier(self):
        raw = {**_BASE_RAW, "source_kind": "epic", "source_identifier": ""}
        with pytest.raises(ValueError, match="source_identifier.*required"):
            ReleaseDelivery.from_raw(raw)

    def test_source_kind_commits_forbids_identifier(self):
        raw = {
            **_BASE_RAW,
            "source_kind": "commits",
            "source_identifier": "FOO-10",
        }
        with pytest.raises(ValueError, match="source_identifier.*null.*commits"):
            ReleaseDelivery.from_raw(raw)

    def test_source_kind_commits_accepts_null_identifier(self):
        raw = {**_BASE_RAW, "source_kind": "commits", "source_identifier": None}
        d = ReleaseDelivery.from_raw(raw)
        assert d.source_kind == SourceKind.COMMITS
        assert d.source_identifier is None

    def test_multiple_source_commits_parsed(self):
        raw = {**_BASE_RAW, "source_commits": [_SHA_A, _SHA_B]}
        d = ReleaseDelivery.from_raw(raw)
        assert d.source_commits == [_SHA_A, _SHA_B]

    def test_all_status_values_accepted(self):
        for status in AddendumStatus:
            raw = {**_BASE_RAW, "status": status.value}
            d = ReleaseDelivery.from_raw(raw)
            assert d.status == status

    def test_result_commits_accepted(self):
        raw = {**_BASE_RAW, "result_commits": [_SHA_RESULT]}
        d = ReleaseDelivery.from_raw(raw)
        assert d.result_commits == [_SHA_RESULT]

    def test_optional_fields_default_to_none(self):
        d = ReleaseDelivery.from_raw(_BASE_RAW)
        for f in ("claimed_by", "lease_expires_at", "started_at", "completed_at",
                  "work_branch", "pr_url", "pr_number", "error", "migrated_from"):
            assert getattr(d, f) is None

    def test_populated_optional_fields_parsed(self):
        raw = {
            **_BASE_RAW,
            "claimed_by": "worker-1",
            "lease_expires_at": "2026-07-13T13:00:00Z",
            "work_branch": "oompah/release/FOO-10/release-1.0",
            "pr_url": "https://github.com/org/repo/pull/42",
            "pr_number": "42",
            "migrated_from": "FOO-10/release/1.0",
        }
        d = ReleaseDelivery.from_raw(raw)
        assert d.claimed_by == "worker-1"
        assert d.lease_expires_at == "2026-07-13T13:00:00Z"
        assert d.work_branch == "oompah/release/FOO-10/release-1.0"
        assert d.pr_url == "https://github.com/org/repo/pull/42"
        assert d.pr_number == "42"
        assert d.migrated_from == "FOO-10/release/1.0"


# ---------------------------------------------------------------------------
# ReleaseDelivery.to_raw (round-trip)
# ---------------------------------------------------------------------------


class TestReleaseDeliveryToRaw:
    def test_round_trip(self):
        d = ReleaseDelivery.from_raw(_BASE_RAW)
        raw2 = d.to_raw()
        d2 = ReleaseDelivery.from_raw(raw2)
        assert d == d2

    def test_status_serialised_as_string(self):
        d = _make_delivery(status=AddendumStatus.IN_REVIEW)
        raw = d.to_raw()
        assert raw["status"] == "in_review"

    def test_source_kind_serialised_as_string(self):
        d = _make_delivery(source_kind=SourceKind.EPIC, source_identifier="EP-1")
        raw = d.to_raw()
        assert raw["source_kind"] == "epic"

    def test_source_commits_copied(self):
        commits = [_SHA_A, _SHA_B]
        d = _make_delivery(source_commits=list(commits))
        raw = d.to_raw()
        # Mutating original should not affect serialised value
        commits.append(_SHA_C)
        assert raw["source_commits"] == [_SHA_A, _SHA_B]

    def test_all_fields_present_in_output(self):
        d = _make_delivery()
        raw = d.to_raw()
        for key in (
            "id", "project_id", "source_branch", "source_kind",
            "source_identifier", "source_commits", "target_branch",
            "status", "queued_at", "claimed_by", "lease_expires_at",
            "started_at", "completed_at", "work_branch", "pr_url",
            "pr_number", "result_commits", "error", "migrated_from",
        ):
            assert key in raw, f"Missing key {key!r} in to_raw() output"

    def test_null_fields_preserved_in_output(self):
        d = _make_delivery()
        raw = d.to_raw()
        assert raw["claimed_by"] is None
        assert raw["pr_url"] is None
        assert raw["error"] is None

    def test_result_commits_list_serialised(self):
        d = _make_delivery()
        d.result_commits = [_SHA_RESULT]
        raw = d.to_raw()
        assert raw["result_commits"] == [_SHA_RESULT]


# ---------------------------------------------------------------------------
# ReleaseDeliveryLedger
# ---------------------------------------------------------------------------


class TestReleaseDeliveryLedgerEmpty:
    def test_empty_returns_version_1(self):
        ledger = ReleaseDeliveryLedger.empty()
        assert ledger.version == LEDGER_VERSION
        assert ledger.deliveries == []

    def test_empty_to_raw_contains_version_and_deliveries(self):
        raw = ReleaseDeliveryLedger.empty().to_raw()
        assert raw["version"] == LEDGER_VERSION
        assert raw["deliveries"] == []


class TestReleaseDeliveryLedgerFromRaw:
    def test_valid_empty_ledger(self):
        raw = {"version": 1, "deliveries": []}
        ledger = ReleaseDeliveryLedger.from_raw(raw)
        assert ledger.version == 1
        assert ledger.deliveries == []

    def test_valid_ledger_with_entries(self):
        raw = {
            "version": 1,
            "deliveries": [_BASE_RAW],
        }
        ledger = ReleaseDeliveryLedger.from_raw(raw)
        assert len(ledger.deliveries) == 1
        assert ledger.deliveries[0].id == "rd_01J"

    def test_missing_deliveries_defaults_to_empty(self):
        raw = {"version": 1}
        ledger = ReleaseDeliveryLedger.from_raw(raw)
        assert ledger.deliveries == []

    def test_non_dict_root_raises(self):
        with pytest.raises(LedgerParseError, match="must be a mapping"):
            ReleaseDeliveryLedger.from_raw([1, 2, 3])

    def test_missing_version_raises(self):
        with pytest.raises(LedgerParseError, match="missing required 'version'"):
            ReleaseDeliveryLedger.from_raw({"deliveries": []})

    def test_wrong_version_raises(self):
        with pytest.raises(LedgerParseError, match="version.*not supported"):
            ReleaseDeliveryLedger.from_raw({"version": 99, "deliveries": []})

    def test_non_integer_version_raises(self):
        with pytest.raises(LedgerParseError, match="must be an integer"):
            ReleaseDeliveryLedger.from_raw({"version": "one", "deliveries": []})

    def test_non_list_deliveries_raises(self):
        with pytest.raises(LedgerParseError, match="'deliveries' must be a list"):
            ReleaseDeliveryLedger.from_raw({"version": 1, "deliveries": "bad"})

    def test_malformed_entry_raises(self):
        raw = {"version": 1, "deliveries": [{**_BASE_RAW, "id": ""}]}
        with pytest.raises(LedgerParseError, match="entry at index 0.*invalid"):
            ReleaseDeliveryLedger.from_raw(raw)

    def test_parse_error_includes_restore_hint(self):
        with pytest.raises(LedgerParseError, match="git show HEAD"):
            ReleaseDeliveryLedger.from_raw({"version": 2, "deliveries": []})

    def test_round_trip(self):
        original_raw = {"version": 1, "deliveries": [_BASE_RAW]}
        ledger = ReleaseDeliveryLedger.from_raw(original_raw)
        round_tripped = ReleaseDeliveryLedger.from_raw(ledger.to_raw())
        assert round_tripped.deliveries == ledger.deliveries
        assert round_tripped.version == ledger.version


# ---------------------------------------------------------------------------
# ReleaseDeliveryStore.read_ledger
# ---------------------------------------------------------------------------


class TestStoreReadLedger:
    def test_missing_file_returns_empty_ledger(self, tmp_path):
        store = _make_store(tmp_path)
        ledger = store.read_ledger()
        assert ledger.version == LEDGER_VERSION
        assert ledger.deliveries == []

    def test_valid_file_parsed(self, tmp_path):
        _write_raw_ledger(tmp_path, {"version": 1, "deliveries": [_BASE_RAW]})
        store = _make_store(tmp_path)
        ledger = store.read_ledger()
        assert len(ledger.deliveries) == 1
        assert ledger.deliveries[0].id == "rd_01J"

    def test_malformed_yaml_raises_ledger_parse_error(self, tmp_path):
        ledger_path = tmp_path / LEDGER_PATH
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text("{ bad yaml: [", encoding="utf-8")
        store = _make_store(tmp_path)
        with pytest.raises(LedgerParseError, match="Cannot parse ledger YAML"):
            store.read_ledger()

    def test_wrong_version_raises_ledger_parse_error(self, tmp_path):
        _write_raw_ledger(tmp_path, {"version": 42, "deliveries": []})
        store = _make_store(tmp_path)
        with pytest.raises(LedgerParseError, match="version.*not supported"):
            store.read_ledger()

    def test_non_dict_yaml_raises_ledger_parse_error(self, tmp_path):
        ledger_path = tmp_path / LEDGER_PATH
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text("- item1\n- item2\n", encoding="utf-8")
        store = _make_store(tmp_path)
        with pytest.raises(LedgerParseError, match="must be a mapping"):
            store.read_ledger()

    def test_invalid_delivery_entry_raises_ledger_parse_error(self, tmp_path):
        raw = {"version": 1, "deliveries": [{**_BASE_RAW, "source_commits": ["bad_sha"]}]}
        _write_raw_ledger(tmp_path, raw)
        store = _make_store(tmp_path)
        with pytest.raises(LedgerParseError, match="entry at index 0"):
            store.read_ledger()

    def test_malformed_ledger_never_overwritten(self, tmp_path):
        """Attempting to read and then append must not overwrite a malformed file."""
        ledger_path = tmp_path / LEDGER_PATH
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text("{ malformed: [", encoding="utf-8")
        original_content = ledger_path.read_text(encoding="utf-8")

        store = _make_store(tmp_path)
        with pytest.raises(LedgerParseError):
            store.append(_make_delivery())

        # File must be unchanged
        assert ledger_path.read_text(encoding="utf-8") == original_content


# ---------------------------------------------------------------------------
# ReleaseDeliveryStore.append
# ---------------------------------------------------------------------------


class TestStoreAppend:
    def test_append_to_missing_ledger(self, tmp_path):
        store = _make_store(tmp_path)
        d = _make_delivery()
        result = store.append(d)
        assert result.id == d.id

        # Ledger file written
        ledger = store.read_ledger()
        assert len(ledger.deliveries) == 1
        assert ledger.deliveries[0].id == d.id

    def test_append_adds_to_existing_ledger(self, tmp_path):
        store = _make_store(tmp_path)
        d1 = _make_delivery(id="rd_01")
        d2 = _make_delivery(id="rd_02", target_branch="release/2.0")
        store.append(d1)
        store.append(d2)

        ledger = store.read_ledger()
        assert len(ledger.deliveries) == 2
        assert ledger.deliveries[0].id == "rd_01"
        assert ledger.deliveries[1].id == "rd_02"

    def test_append_duplicate_id_raises(self, tmp_path):
        store = _make_store(tmp_path)
        d = _make_delivery(id="rd_01")
        store.append(d)
        with pytest.raises(ValueError, match="already exists"):
            store.append(_make_delivery(id="rd_01", target_branch="release/2.0"))

    def test_append_project_id_mismatch_raises(self, tmp_path):
        store = _make_store(tmp_path, project_id="proj-MINE")
        d = _make_delivery(project_id="proj-OTHER")
        with pytest.raises(ValueError, match="project_id.*does not match"):
            store.append(d)

    def test_append_calls_git_writer(self, tmp_path):
        ledger_file = tmp_path / LEDGER_PATH

        def _write_side_effect(relative_path: str, content: str, subject: str) -> None:
            ledger_file.parent.mkdir(parents=True, exist_ok=True)
            ledger_file.write_text(content, encoding="utf-8")

        git_writer = MagicMock()
        git_writer.write_and_commit_ledger_file.side_effect = _write_side_effect
        store = ReleaseDeliveryStore(
            project_root=tmp_path,
            project_id="proj-123",
            git_writer=git_writer,
        )
        d = _make_delivery()
        store.append(d)
        git_writer.write_and_commit_ledger_file.assert_called_once()
        args = git_writer.write_and_commit_ledger_file.call_args[0]
        assert args[0] == LEDGER_PATH  # relative_path
        assert "rd_01J" in args[2]  # subject mentions delivery ID

    def test_append_preserves_ledger_version(self, tmp_path):
        _write_raw_ledger(tmp_path, {"version": 1, "deliveries": []})
        store = _make_store(tmp_path)
        store.append(_make_delivery())
        ledger = store.read_ledger()
        assert ledger.version == 1


# ---------------------------------------------------------------------------
# ReleaseDeliveryStore.lookup_by_id
# ---------------------------------------------------------------------------


class TestStoreLookupById:
    def test_found(self, tmp_path):
        store = _make_store(tmp_path)
        d = _make_delivery(id="rd_01")
        store.append(d)
        result = store.lookup_by_id("rd_01")
        assert result is not None
        assert result.id == "rd_01"

    def test_not_found_returns_none(self, tmp_path):
        store = _make_store(tmp_path)
        assert store.lookup_by_id("nonexistent") is None

    def test_not_found_on_empty_ledger(self, tmp_path):
        store = _make_store(tmp_path)
        assert store.lookup_by_id("rd_01") is None

    def test_finds_correct_delivery_among_multiple(self, tmp_path):
        store = _make_store(tmp_path)
        d1 = _make_delivery(id="rd_01")
        d2 = _make_delivery(id="rd_02", target_branch="release/2.0")
        store.append(d1)
        store.append(d2)
        assert store.lookup_by_id("rd_02").target_branch == "release/2.0"


# ---------------------------------------------------------------------------
# ReleaseDeliveryStore.lookup_by_source_identifier
# ---------------------------------------------------------------------------


class TestStoreLookupBySourceIdentifier:
    def test_returns_matching_entries(self, tmp_path):
        store = _make_store(tmp_path)
        d1 = _make_delivery(id="rd_01", source_identifier="FOO-10", target_branch="release/1.0")
        d2 = _make_delivery(id="rd_02", source_identifier="FOO-10", target_branch="release/2.0")
        d3 = _make_delivery(id="rd_03", source_identifier="BAR-99", target_branch="release/1.0")
        store.append(d1)
        store.append(d2)
        store.append(d3)

        result = store.lookup_by_source_identifier("FOO-10")
        assert len(result) == 2
        ids = {d.id for d in result}
        assert "rd_01" in ids
        assert "rd_02" in ids

    def test_returns_empty_when_no_match(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery(source_identifier="FOO-10"))
        assert store.lookup_by_source_identifier("NONEXISTENT") == []

    def test_returns_empty_on_empty_ledger(self, tmp_path):
        store = _make_store(tmp_path)
        assert store.lookup_by_source_identifier("FOO-10") == []

    def test_commits_kind_delivery_not_returned(self, tmp_path):
        """Deliveries with source_kind=commits (null identifier) are never returned."""
        store = _make_store(tmp_path)
        d_task = _make_delivery(
            id="rd_01", source_kind=SourceKind.TASK, source_identifier="FOO-10"
        )
        d_commits = _make_delivery(
            id="rd_02",
            source_kind=SourceKind.COMMITS,
            source_identifier=None,
            target_branch="release/2.0",
        )
        store.append(d_task)
        store.append(d_commits)

        result = store.lookup_by_source_identifier("FOO-10")
        assert len(result) == 1
        assert result[0].id == "rd_01"


# ---------------------------------------------------------------------------
# ReleaseDeliveryStore.update
# ---------------------------------------------------------------------------


class TestStoreUpdate:
    def test_valid_status_transition(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery(status=AddendumStatus.OPEN))
        result = store.update(
            "rd_01J",
            status=AddendumStatus.IN_PROGRESS,
            claimed_by="worker-1",
            started_at="2026-07-13T12:01:00Z",
        )
        assert result.status == AddendumStatus.IN_PROGRESS
        assert result.claimed_by == "worker-1"
        assert result.started_at == "2026-07-13T12:01:00Z"

    def test_status_string_accepted(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery(status=AddendumStatus.OPEN))
        result = store.update("rd_01J", status="in_progress")
        assert result.status == AddendumStatus.IN_PROGRESS

    def test_update_persisted_to_disk(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery(status=AddendumStatus.OPEN))
        store.update("rd_01J", status=AddendumStatus.IN_PROGRESS)
        reloaded = store.lookup_by_id("rd_01J")
        assert reloaded.status == AddendumStatus.IN_PROGRESS

    def test_not_found_raises(self, tmp_path):
        store = _make_store(tmp_path)
        with pytest.raises(DeliveryNotFoundError, match="nonexistent"):
            store.update("nonexistent", status=AddendumStatus.IN_PROGRESS)

    def test_immutable_id_rejected(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery())
        with pytest.raises(ImmutableFieldError, match="id"):
            store.update("rd_01J", id="new_id")

    def test_immutable_project_id_rejected(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery())
        with pytest.raises(ImmutableFieldError, match="project_id"):
            store.update("rd_01J", project_id="other-proj")

    def test_immutable_source_branch_rejected(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery())
        with pytest.raises(ImmutableFieldError, match="source_branch"):
            store.update("rd_01J", source_branch="other-branch")

    def test_immutable_source_kind_rejected(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery())
        with pytest.raises(ImmutableFieldError, match="source_kind"):
            store.update("rd_01J", source_kind=SourceKind.EPIC)

    def test_immutable_source_identifier_rejected(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery())
        with pytest.raises(ImmutableFieldError, match="source_identifier"):
            store.update("rd_01J", source_identifier="BAR-99")

    def test_immutable_source_commits_rejected(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery())
        with pytest.raises(ImmutableFieldError, match="source_commits"):
            store.update("rd_01J", source_commits=[_SHA_B])

    def test_immutable_target_branch_rejected(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery())
        with pytest.raises(ImmutableFieldError, match="target_branch"):
            store.update("rd_01J", target_branch="release/99.0")

    def test_unknown_field_rejected(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery())
        with pytest.raises(ValueError, match="Unknown update field"):
            store.update("rd_01J", nonexistent_field="x")

    def test_invalid_transition_raises(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery(status=AddendumStatus.MERGED))
        with pytest.raises(InvalidTransitionError, match="merged.*open"):
            store.update("rd_01J", status=AddendumStatus.OPEN)

    def test_source_commits_preserved_after_update(self, tmp_path):
        """source_commits must be unchanged after a lifecycle update."""
        original_commits = [_SHA_A, _SHA_B]
        store = _make_store(tmp_path)
        store.append(_make_delivery(source_commits=original_commits))
        result = store.update("rd_01J", status=AddendumStatus.IN_PROGRESS)
        assert result.source_commits == original_commits

        # Verify on disk too
        reloaded = store.lookup_by_id("rd_01J")
        assert reloaded.source_commits == original_commits

    def test_evidence_fields_preserved_when_not_supplied(self, tmp_path):
        """Existing evidence fields are not cleared when not passed in the update."""
        store = _make_store(tmp_path)
        store.append(_make_delivery(status=AddendumStatus.OPEN))
        store.update(
            "rd_01J",
            status=AddendumStatus.IN_PROGRESS,
            claimed_by="worker-1",
        )
        # Transition to in_review with PR evidence
        store.update(
            "rd_01J",
            status=AddendumStatus.IN_REVIEW,
            pr_url="https://github.com/org/repo/pull/42",
        )
        # Merge without re-passing pr_url — it must be preserved
        result = store.update("rd_01J", status=AddendumStatus.MERGED)
        assert result.pr_url == "https://github.com/org/repo/pull/42"

    def test_result_commits_sha_validated(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery(status=AddendumStatus.IN_REVIEW))
        with pytest.raises(ValueError, match="40-character"):
            store.update("rd_01J", result_commits=["short"])

    def test_result_commits_valid_sha_accepted(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery(status=AddendumStatus.IN_REVIEW))
        result = store.update("rd_01J", result_commits=[_SHA_RESULT])
        assert result.result_commits == [_SHA_RESULT]

    def test_update_calls_git_writer(self, tmp_path):
        # Use a side_effect so the mock actually writes the file to disk.
        ledger_file = tmp_path / LEDGER_PATH

        def _write_side_effect(relative_path: str, content: str, subject: str) -> None:
            ledger_file.parent.mkdir(parents=True, exist_ok=True)
            ledger_file.write_text(content, encoding="utf-8")

        git_writer = MagicMock()
        git_writer.write_and_commit_ledger_file.side_effect = _write_side_effect
        store = ReleaseDeliveryStore(
            project_root=tmp_path,
            project_id="proj-123",
            git_writer=git_writer,
        )
        store.append(_make_delivery(status=AddendumStatus.OPEN))
        git_writer.reset_mock()
        git_writer.write_and_commit_ledger_file.side_effect = _write_side_effect

        store.update("rd_01J", status=AddendumStatus.IN_PROGRESS)
        git_writer.write_and_commit_ledger_file.assert_called_once()

    def test_multiple_fields_updated_atomically(self, tmp_path):
        store = _make_store(tmp_path)
        store.append(_make_delivery(status=AddendumStatus.IN_PROGRESS))
        store.update(
            "rd_01J",
            status=AddendumStatus.IN_REVIEW,
            pr_url="https://github.com/org/repo/pull/7",
            pr_number="7",
            work_branch="oompah/release/FOO-10/release-1.0",
        )
        reloaded = store.lookup_by_id("rd_01J")
        assert reloaded.status == AddendumStatus.IN_REVIEW
        assert reloaded.pr_url == "https://github.com/org/repo/pull/7"
        assert reloaded.pr_number == "7"
        assert reloaded.work_branch == "oompah/release/FOO-10/release-1.0"


# ---------------------------------------------------------------------------
# Concurrent update locking
# ---------------------------------------------------------------------------


class TestConcurrentLocking:
    """Concurrent append and update must be serialised under the project lock.

    These tests use real threads with a controlled barrier to exercise the
    module-level ``_delivery_lock`` mechanism.
    """

    def test_concurrent_appends_produce_consistent_ledger(self, tmp_path):
        """Two threads appending different deliveries must both land in the ledger."""
        store = _make_store(tmp_path)
        errors: list[Exception] = []
        barrier = threading.Barrier(2)

        def append_delivery(delivery_id: str) -> None:
            try:
                barrier.wait()
                store.append(_make_delivery(
                    id=delivery_id,
                    target_branch=f"release/{delivery_id}",
                ))
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=append_delivery, args=("rd_thread1",))
        t2 = threading.Thread(target=append_delivery, args=("rd_thread2",))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"Thread errors: {errors}"
        ledger = store.read_ledger()
        ids = {d.id for d in ledger.deliveries}
        assert "rd_thread1" in ids
        assert "rd_thread2" in ids

    def test_concurrent_update_is_serialised(self, tmp_path):
        """Concurrent updates to the same delivery must not lose writes."""
        store = _make_store(tmp_path)
        store.append(_make_delivery(status=AddendumStatus.OPEN))
        errors: list[Exception] = []
        results: list[AddendumStatus] = []
        lock = threading.Lock()

        # We'll have one thread transition open→in_progress and another try as well;
        # only one should succeed (the other will see a bad transition from in_progress).
        def try_claim() -> None:
            try:
                updated = store.update("rd_01J", status=AddendumStatus.IN_PROGRESS)
                with lock:
                    results.append(updated.status)
            except InvalidTransitionError:
                # Expected: the second thread loses the race
                with lock:
                    results.append(None)  # type: ignore[arg-type]
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=try_claim)
        t2 = threading.Thread(target=try_claim)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors
        # Exactly one thread succeeded
        assert results.count(AddendumStatus.IN_PROGRESS) == 1

    def test_lock_keyed_by_project_id(self):
        """Different project IDs must have independent locks."""
        lock_a = _delivery_lock("proj-A")
        lock_b = _delivery_lock("proj-B")
        lock_a2 = _delivery_lock("proj-A")
        assert lock_a is lock_a2
        assert lock_a is not lock_b


# ---------------------------------------------------------------------------
# ReleaseDeliveryStore constructor validation
# ---------------------------------------------------------------------------


class TestStoreConstructor:
    def test_empty_project_id_raises(self, tmp_path):
        with pytest.raises(ValueError, match="project_id must not be empty"):
            ReleaseDeliveryStore(project_root=tmp_path, project_id="")

    def test_none_project_id_raises(self, tmp_path):
        with pytest.raises(ValueError, match="project_id must not be empty"):
            ReleaseDeliveryStore(project_root=tmp_path, project_id=None)  # type: ignore[arg-type]

    def test_project_id_property(self, tmp_path):
        store = _make_store(tmp_path, project_id="proj-abc")
        assert store.project_id == "proj-abc"

    def test_ledger_path_property(self, tmp_path):
        store = _make_store(tmp_path)
        assert store.ledger_path == tmp_path / LEDGER_PATH


# ---------------------------------------------------------------------------
# OompahMarkdownTracker.write_and_commit_ledger_file integration
# ---------------------------------------------------------------------------

def _make_completed_process(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def _tracker(tmp_path: Path, *, git_sync: bool = False) -> OompahMarkdownTracker:
    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    return OompahMarkdownTracker(
        active_states=["Open"],
        terminal_states=["Done"],
        cwd=str(root),
        default_branch="main",
        git_sync=git_sync,
    )


class TestWriteAndCommitLedgerFile:
    """Tests for OompahMarkdownTracker.write_and_commit_ledger_file."""

    def test_writes_file_to_disk(self, tmp_path):
        tracker = _tracker(tmp_path)
        content = "version: 1\ndeliveries: []\n"
        tracker.write_and_commit_ledger_file(LEDGER_PATH, content, "Create ledger")

        ledger_path = tmp_path / "repo" / LEDGER_PATH
        assert ledger_path.exists()
        assert ledger_path.read_text(encoding="utf-8") == content

    def test_creates_parent_directories(self, tmp_path):
        tracker = _tracker(tmp_path)
        content = "version: 1\ndeliveries: []\n"
        tracker.write_and_commit_ledger_file(LEDGER_PATH, content, "Create ledger")

        assert (tmp_path / "repo" / ".oompah").is_dir()

    def test_no_git_commit_when_git_sync_disabled(self, tmp_path):
        tracker = _tracker(tmp_path, git_sync=False)
        # No git repo — should not fail
        content = "version: 1\ndeliveries: []\n"
        tracker.write_and_commit_ledger_file(LEDGER_PATH, content, "Test write")

        ledger_path = tmp_path / "repo" / LEDGER_PATH
        assert ledger_path.exists()

    def test_git_sync_path_uses_fetch_ff_only(self, tmp_path):
        """write_and_commit_ledger_file must sync with fetch + ff-only, not pull --rebase."""
        tracker = _tracker(tmp_path, git_sync=True)
        git_calls: list[tuple] = []

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            git_calls.append(tuple(args))
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref":
                return _make_completed_process(0, "main")
            if cmd == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]
        content = "version: 1\ndeliveries: []\n"
        tracker.write_and_commit_ledger_file(LEDGER_PATH, content, "Create ledger")

        arg_strings = [" ".join(c) for c in git_calls]
        assert any("fetch" in s and "origin" in s for s in arg_strings)
        assert any("merge" in s and "--ff-only" in s for s in arg_strings)
        assert not any("pull" in s and "rebase" in s for s in arg_strings)

    def test_git_sync_commits_ledger_path_not_tasks_dir(self, tmp_path):
        """The git add must stage the ledger file specifically, not TASKS_DIR."""
        tracker = _tracker(tmp_path, git_sync=True)
        staged_paths: list[str] = []

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            if args and args[0] == "add":
                staged_paths.append(args[-1])
            if args and args[0] == "rev-parse":
                return _make_completed_process(0, "true")
            if args and args[0] == "symbolic-ref":
                return _make_completed_process(0, "main")
            if args and args[0] == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]
        content = "version: 1\ndeliveries: []\n"
        tracker.write_and_commit_ledger_file(LEDGER_PATH, content, "Update ledger")

        assert LEDGER_PATH in staged_paths
        assert ".oompah/tasks" not in staged_paths

    def test_git_push_retry_uses_ff_only(self, tmp_path):
        """After a rejected push, sync must use fetch + ff-only and retry."""
        tracker = _tracker(tmp_path, git_sync=True)
        push_count = [0]
        git_calls: list[tuple] = []

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            git_calls.append(tuple(args))
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref":
                return _make_completed_process(0, "main")
            if cmd == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            if cmd == "diff":
                return _make_completed_process(1)  # staged changes present
            if cmd == "push":
                push_count[0] += 1
                if push_count[0] == 1:
                    return _make_completed_process(1, "", "! [rejected]")
                return _make_completed_process(0)
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]
        content = "version: 1\ndeliveries: []\n"
        tracker.write_and_commit_ledger_file(LEDGER_PATH, content, "Push retry test")

        arg_strings = [" ".join(c) for c in git_calls]
        assert push_count[0] == 2  # failed + retry
        assert any("fetch" in s and "origin" in s for s in arg_strings)
        assert any("merge" in s and "--ff-only" in s for s in arg_strings)

    def test_write_through_store_and_git_writer(self, tmp_path):
        """End-to-end: store.append() with a git_writer commits the ledger via tracker."""
        tracker = _tracker(tmp_path, git_sync=True)
        committed_content: list[str] = []

        def _fake_git(args: list[str], *, check: bool) -> MagicMock:
            cmd = args[0] if args else ""
            if cmd == "rev-parse":
                return _make_completed_process(0, "true")
            if cmd == "symbolic-ref":
                return _make_completed_process(0, "main")
            if cmd == "remote":
                return _make_completed_process(0, "git@example.com:org/repo.git")
            if cmd == "diff":
                # Simulate staged changes after add
                return _make_completed_process(1)
            if cmd == "commit":
                # Capture the content at commit time
                ledger_path = tmp_path / "repo" / LEDGER_PATH
                if ledger_path.exists():
                    committed_content.append(ledger_path.read_text(encoding="utf-8"))
                return _make_completed_process(0)
            return _make_completed_process(0)

        tracker._git = _fake_git  # type: ignore[method-assign]

        store = ReleaseDeliveryStore(
            project_root=tmp_path / "repo",
            project_id="proj-123",
            git_writer=tracker,
        )
        d = _make_delivery()
        store.append(d)

        # The ledger was committed
        assert len(committed_content) == 1
        parsed = yaml.safe_load(committed_content[0])
        assert parsed["version"] == 1
        assert len(parsed["deliveries"]) == 1
        assert parsed["deliveries"][0]["id"] == "rd_01J"

    def test_real_git_repo_commits_ledger_on_default_branch(self, tmp_path):
        """Integration test using a real git repository.

        Verifies that write_and_commit_ledger_file commits the ledger file
        on the default branch when git_sync=True, matching the requirement
        that the native tracker writer atomically persists the ledger.
        """
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Initialise a real git repo on 'main'
        subprocess.run(["git", "init", "-b", "main"], cwd=repo_root, check=True,
                       capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True,
                       capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                       cwd=repo_root, check=True, capture_output=True)

        # Make an initial commit so HEAD exists
        readme = repo_root / "README.md"
        readme.write_text("init\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True,
                       capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"],
                       cwd=repo_root, check=True, capture_output=True)

        tracker = OompahMarkdownTracker(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(repo_root),
            default_branch="main",
            git_sync=True,
        )

        # Patch _has_remote to return False (no remote in test)
        with patch.object(tracker, "_has_remote", return_value=False):
            content = yaml.safe_dump(
                {"version": 1, "deliveries": [_BASE_RAW]}, sort_keys=False
            )
            tracker.write_and_commit_ledger_file(
                LEDGER_PATH, content, "Create release delivery ledger"
            )

        # File must be on disk
        ledger_path = repo_root / LEDGER_PATH
        assert ledger_path.exists()
        text = ledger_path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
        assert parsed["version"] == 1
        assert parsed["deliveries"][0]["id"] == "rd_01J"

        # Ledger must be committed (in git log)
        log = subprocess.run(
            ["git", "log", "--oneline", "--", LEDGER_PATH],
            cwd=repo_root, capture_output=True, text=True, check=True,
        )
        assert log.stdout.strip(), (
            f"Expected ledger to appear in git log, got empty output.\n"
            f"git log: {log.stdout!r}"
        )

    def test_default_branch_guard_enforced(self, tmp_path):
        """write_and_commit_ledger_file must reject writes when not on default branch."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        subprocess.run(["git", "init", "-b", "main"], cwd=repo_root, check=True,
                       capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True,
                       capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                       cwd=repo_root, check=True, capture_output=True)
        readme = repo_root / "README.md"
        readme.write_text("init\n")
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True,
                       capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_root, check=True,
                       capture_output=True)

        # Switch to a feature branch
        subprocess.run(["git", "checkout", "-b", "feature/x"], cwd=repo_root, check=True,
                       capture_output=True)

        tracker = OompahMarkdownTracker(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(repo_root),
            default_branch="main",
            git_sync=True,
        )

        with pytest.raises(TrackerError, match="default branch"):
            tracker.write_and_commit_ledger_file(
                LEDGER_PATH, "version: 1\ndeliveries: []\n", "Should fail"
            )
