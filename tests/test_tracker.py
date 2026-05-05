"""Tests for oompah.tracker (parsing/normalization only)."""

from datetime import datetime, timezone
from unittest.mock import patch, call, MagicMock

from oompah.tracker import BeadsTracker, DEFAULT_INITIAL_STATUS, _parse_timestamp


class TestParseTimestamp:
    def test_iso_format(self):
        dt = _parse_timestamp("2025-06-15T10:30:00+00:00")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 6

    def test_z_suffix(self):
        dt = _parse_timestamp("2025-06-15T10:30:00Z")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_none(self):
        assert _parse_timestamp(None) is None

    def test_empty_string(self):
        assert _parse_timestamp("") is None

    def test_invalid(self):
        assert _parse_timestamp("not a date") is None

    def test_datetime_passthrough(self):
        dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
        assert _parse_timestamp(dt) is dt


class TestNormalizeIssue:
    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    def test_basic(self):
        raw = {
            "id": "abc123",
            "identifier": "beads-001",
            "title": "Test issue",
            "status": "open",
            "priority": 2,
            "type": "bug",
        }
        issue = self._tracker()._normalize_issue(raw)
        assert issue.id == "abc123"
        assert issue.identifier == "beads-001"
        assert issue.title == "Test issue"
        assert issue.state == "open"
        assert issue.priority == 2
        assert issue.issue_type == "bug"

    def test_priority_none(self):
        raw = {"id": "1", "title": "t"}
        issue = self._tracker()._normalize_issue(raw)
        assert issue.priority is None

    def test_priority_invalid(self):
        raw = {"id": "1", "title": "t", "priority": "invalid"}
        issue = self._tracker()._normalize_issue(raw)
        assert issue.priority is None

    def test_labels(self):
        raw = {"id": "1", "title": "t", "labels": ["Urgent", "Backend"]}
        issue = self._tracker()._normalize_issue(raw)
        assert issue.labels == ["urgent", "backend"]

    def test_blocked_by_dicts(self):
        raw = {
            "id": "1", "title": "t",
            "blocked_by": [{"id": "dep1", "identifier": "beads-002", "status": "open"}],
        }
        issue = self._tracker()._normalize_issue(raw)
        assert len(issue.blocked_by) == 1
        assert issue.blocked_by[0].identifier == "beads-002"

    def test_blocked_by_strings(self):
        raw = {"id": "1", "title": "t", "blocked_by": ["dep1", "dep2"]}
        issue = self._tracker()._normalize_issue(raw)
        assert len(issue.blocked_by) == 2

    def test_timestamps(self):
        raw = {
            "id": "1", "title": "t",
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-16T12:00:00+00:00",
        }
        issue = self._tracker()._normalize_issue(raw)
        assert issue.created_at is not None
        assert issue.created_at.year == 2025
        assert issue.updated_at is not None

    def test_parent_id(self):
        raw = {"id": "1", "title": "t", "parent": "epic-001"}
        issue = self._tracker()._normalize_issue(raw)
        assert issue.parent_id == "epic-001"


class TestAddComment:
    """Tests for BeadsTracker.add_comment to ensure author='oompah' is always used."""

    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_default_author_is_oompah(self, mock_run_bd):
        """When no author is specified, the comment must be attributed to 'oompah'."""
        mock_run_bd.return_value = {
            "id": 1, "issue_id": "test-1", "author": "oompah", "text": "hello"
        }
        tracker = self._tracker()
        tracker.add_comment("test-1", "hello")

        mock_run_bd.assert_called_once_with([
            "comments", "add", "test-1", "hello",
            "--author=oompah", "--json",
        ])

    @patch.object(BeadsTracker, "_run_bd")
    def test_explicit_oompah_author(self, mock_run_bd):
        """Explicit author='oompah' passes --author=oompah to bd CLI."""
        mock_run_bd.return_value = {}
        tracker = self._tracker()
        tracker.add_comment("test-1", "hello", author="oompah")

        mock_run_bd.assert_called_once_with([
            "comments", "add", "test-1", "hello",
            "--author=oompah", "--json",
        ])

    @patch.object(BeadsTracker, "_run_bd")
    def test_custom_author_passed_through(self, mock_run_bd):
        """An explicit custom author is still passed through (e.g. for human users via API)."""
        mock_run_bd.return_value = {}
        tracker = self._tracker()
        tracker.add_comment("test-1", "message", author="alice")

        mock_run_bd.assert_called_once_with([
            "comments", "add", "test-1", "message",
            "--author=alice", "--json",
        ])

    @patch.object(BeadsTracker, "_run_bd")
    def test_returns_dict_on_success(self, mock_run_bd):
        """add_comment returns the response dict on success."""
        mock_run_bd.return_value = {"id": 42, "author": "oompah", "text": "hi"}
        tracker = self._tracker()
        result = tracker.add_comment("test-1", "hi")
        assert result == {"id": 42, "author": "oompah", "text": "hi"}

    @patch.object(BeadsTracker, "_run_bd")
    def test_returns_empty_dict_on_non_dict_response(self, mock_run_bd):
        """add_comment returns {} when bd returns a non-dict (e.g. empty list)."""
        mock_run_bd.return_value = []
        tracker = self._tracker()
        result = tracker.add_comment("test-1", "hello")
        assert result == {}


class TestDefaultInitialStatus:
    """Verify the DEFAULT_INITIAL_STATUS constant is 'deferred' (backlog)."""

    def test_default_initial_status_is_deferred(self):
        assert DEFAULT_INITIAL_STATUS == "deferred"


class TestCreateIssueInitialStatus:
    """Tests for create_issue with the initial_status parameter."""

    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_create_defaults_to_deferred(self, mock_run_bd):
        """Without initial_status, issue should be moved to 'deferred' (backlog)."""
        # bd create returns an issue in 'open' state
        mock_run_bd.side_effect = [
            # First call: bd create ... --json
            {"id": "test-1", "title": "Test", "status": "open", "priority": 2},
            # Second call: bd update test-1 --status=deferred
            {},
        ]

        tracker = self._tracker()
        issue = tracker.create_issue(title="Test")

        assert issue.state == "deferred"
        assert mock_run_bd.call_count == 2

        # Verify the update call set status to deferred
        update_call = mock_run_bd.call_args_list[1]
        assert update_call == call(["update", "test-1", "--status=deferred"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_create_with_explicit_open_skips_update(self, mock_run_bd):
        """When initial_status='open', no update should be needed (bd default)."""
        mock_run_bd.return_value = {
            "id": "test-2", "title": "Urgent", "status": "open", "priority": 0,
        }

        tracker = self._tracker()
        issue = tracker.create_issue(title="Urgent", initial_status="open")

        assert issue.state == "open"
        # Only the create call, no update
        assert mock_run_bd.call_count == 1

    @patch.object(BeadsTracker, "_run_bd")
    def test_create_with_explicit_deferred(self, mock_run_bd):
        """Explicit initial_status='deferred' should still trigger update."""
        mock_run_bd.side_effect = [
            {"id": "test-3", "title": "Backlog item", "status": "open", "priority": 3},
            {},
        ]

        tracker = self._tracker()
        issue = tracker.create_issue(title="Backlog item", initial_status="deferred")

        assert issue.state == "deferred"
        assert mock_run_bd.call_count == 2

    @patch.object(BeadsTracker, "_run_bd")
    def test_create_with_custom_status(self, mock_run_bd):
        """Arbitrary initial_status values should be respected."""
        mock_run_bd.side_effect = [
            {"id": "test-4", "title": "Blocked", "status": "open", "priority": 2},
            {},
        ]

        tracker = self._tracker()
        issue = tracker.create_issue(title="Blocked", initial_status="blocked")

        assert issue.state == "blocked"
        update_call = mock_run_bd.call_args_list[1]
        assert update_call == call(["update", "test-4", "--status=blocked"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_create_no_update_when_already_matching(self, mock_run_bd):
        """If bd create somehow returns the desired status, no update needed."""
        mock_run_bd.return_value = {
            "id": "test-5", "title": "Pre-deferred", "status": "deferred", "priority": 2,
        }

        tracker = self._tracker()
        issue = tracker.create_issue(title="Pre-deferred")

        assert issue.state == "deferred"
        # Only the create call, no update needed
        assert mock_run_bd.call_count == 1


# ---------------------------------------------------------------------------
# Multimodal attachments (oompah-zlz.1)
# ---------------------------------------------------------------------------

import json as _json
import os as _os
from unittest.mock import patch as _patch


class TestNormalizeIssueAttachments:
    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    def test_no_metadata(self):
        issue = self._tracker()._normalize_issue({"id": "1", "title": "t"})
        assert issue.attachments == []

    def test_paths_extracted_from_metadata(self):
        raw = {
            "id": "1", "title": "t",
            "metadata": {
                "oompah.attachments": [
                    {"path": ".oompah/attachments/foo-1/abc-x.png",
                     "mime_type": "image/png", "size": 100},
                    {"path": ".oompah/attachments/foo-1/def-y.pdf",
                     "mime_type": "application/pdf", "size": 200},
                ],
                "unrelated_key": "ignored",
            },
        }
        issue = self._tracker()._normalize_issue(raw)
        assert issue.attachments == [
            ".oompah/attachments/foo-1/abc-x.png",
            ".oompah/attachments/foo-1/def-y.pdf",
        ]

    def test_metadata_as_json_string(self):
        """bd may emit metadata as a JSON-encoded string in some flows."""
        raw = {
            "id": "1", "title": "t",
            "metadata": _json.dumps({
                "oompah.attachments": [
                    {"path": ".oompah/attachments/foo-1/x.png"},
                ],
            }),
        }
        issue = self._tracker()._normalize_issue(raw)
        assert issue.attachments == [".oompah/attachments/foo-1/x.png"]

    def test_string_entries_are_accepted_as_paths(self):
        """Tolerate a list of bare path strings."""
        raw = {
            "id": "1", "title": "t",
            "metadata": {"oompah.attachments": [".oompah/attachments/x.png"]},
        }
        issue = self._tracker()._normalize_issue(raw)
        assert issue.attachments == [".oompah/attachments/x.png"]

    def test_malformed_metadata_is_safe(self):
        for meta in ("not json", 42, None, {"oompah.attachments": "not a list"}):
            raw = {"id": "1", "title": "t", "metadata": meta}
            issue = self._tracker()._normalize_issue(raw)
            assert issue.attachments == []


class TestSetAttachments:
    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    @_patch.object(BeadsTracker, "_run_bd")
    def test_replaces_attachments_metadata(self, mock_run):
        # First call (show) returns existing metadata; second call (update) returns nothing.
        mock_run.side_effect = [
            {"id": "x", "metadata": {"unrelated": "preserved"}},
            {},
        ]
        attachments = [{"path": ".oompah/attachments/foo-1/x.png", "size": 10}]
        self._tracker().set_attachments("foo-1", attachments)

        # Inspect the update call — must include both keys.
        update_call = mock_run.call_args_list[1]
        args = update_call.args[0]
        assert args[0] == "update"
        assert args[1] == "foo-1"
        assert args[2] == "--metadata"
        sent = _json.loads(args[3])
        assert sent["unrelated"] == "preserved"
        assert sent["oompah.attachments"] == attachments

    @_patch.object(BeadsTracker, "_run_bd")
    def test_handles_missing_existing_metadata(self, mock_run):
        mock_run.side_effect = [
            {"id": "x"},  # no metadata key
            {},
        ]
        self._tracker().set_attachments("foo-1", [])
        sent = _json.loads(mock_run.call_args_list[1].args[0][3])
        assert sent == {"oompah.attachments": []}

    @_patch.object(BeadsTracker, "_run_bd")
    def test_writes_sidecar_manifest_when_project_root_given(self, mock_run, tmp_path):
        mock_run.side_effect = [{"id": "x", "metadata": {}}, {}]
        attachments = [{"path": ".oompah/attachments/foo-1/x.png"}]
        self._tracker().set_attachments(
            "foo-1", attachments, project_root=str(tmp_path),
        )
        manifest = tmp_path / ".oompah" / "attachments" / "foo-1" / "manifest.json"
        assert manifest.exists()
        loaded = _json.loads(manifest.read_text())
        assert loaded == attachments

    @_patch.object(BeadsTracker, "_run_bd")
    def test_no_sidecar_when_no_project_root(self, mock_run, tmp_path):
        mock_run.side_effect = [{"id": "x", "metadata": {}}, {}]
        # Run from inside tmp_path so any stray write would be visible.
        cwd = _os.getcwd()
        _os.chdir(tmp_path)
        try:
            self._tracker().set_attachments("foo-1", [])
        finally:
            _os.chdir(cwd)
        assert not (tmp_path / ".oompah").exists()


class TestFetchAttachments:
    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    @_patch.object(BeadsTracker, "_run_bd")
    def test_returns_metadata_entries(self, mock_run):
        entries = [{"path": ".oompah/attachments/foo-1/x.png", "size": 10}]
        mock_run.return_value = {"id": "x", "metadata": {"oompah.attachments": entries}}
        out = self._tracker().fetch_attachments("foo-1")
        assert out == entries

    @_patch.object(BeadsTracker, "_run_bd")
    def test_returns_empty_when_missing(self, mock_run):
        mock_run.return_value = {"id": "x"}
        assert self._tracker().fetch_attachments("foo-1") == []

    @_patch.object(BeadsTracker, "_run_bd")
    def test_filters_non_dict_entries(self, mock_run):
        mock_run.return_value = {
            "id": "x",
            "metadata": {"oompah.attachments": [{"path": "a"}, "stringy", 42]},
        }
        # fetch_attachments returns only dict-shaped entries (rich records).
        assert self._tracker().fetch_attachments("foo-1") == [{"path": "a"}]


# ---------------------------------------------------------------------------
# Missing-DB handling: TrackerNotConfiguredError + TTL short-circuit.
# Covers oompah-zlz_2-uxx (and 5 dupes): trickle project's missing beads DB
# was producing an ERROR log on every tick, which the error_watcher escalated
# into fresh duplicate bug beads.
# ---------------------------------------------------------------------------

import subprocess as _subprocess

import pytest as _pytest

from oompah.tracker import (
    BeadsTracker as _BT,
    TrackerError as _TE,
    TrackerNotConfiguredError as _TNCE,
)


class _CompletedProcess:
    """Tiny stand-in for subprocess.CompletedProcess."""
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_tracker():
    return _BT(active_states=["open"], terminal_states=["closed"], cwd="/tmp/x")


class TestMissingDbDetection:
    def test_raises_specific_subclass_for_no_db(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return _CompletedProcess(
                1, "",
                "Error: no beads database found\n"
                "Hint: run 'bd init' to create a new database",
            )
        monkeypatch.setattr(_subprocess, "run", fake_run)
        t = _make_tracker()
        with _pytest.raises(_TNCE):
            t._run_bd(["list", "--json"])

    def test_other_failures_still_raise_generic_tracker_error(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return _CompletedProcess(1, "", "Error: something else went wrong")
        monkeypatch.setattr(_subprocess, "run", fake_run)
        t = _make_tracker()
        with _pytest.raises(_TE) as exc_info:
            t._run_bd(["list", "--json"])
        # Must NOT be the more-specific subclass.
        assert not isinstance(exc_info.value, _TNCE)


class TestMissingDbTtlCache:
    def test_second_call_short_circuits_without_subprocess(self, monkeypatch):
        call_count = {"n": 0}

        def fake_run(*args, **kwargs):
            call_count["n"] += 1
            return _CompletedProcess(1, "", "Error: no beads database found")

        monkeypatch.setattr(_subprocess, "run", fake_run)
        t = _make_tracker()
        with _pytest.raises(_TNCE):
            t._run_bd(["list", "--json"])
        assert call_count["n"] == 1
        # Within TTL: second call must short-circuit (no subprocess spawned).
        with _pytest.raises(_TNCE):
            t._run_bd(["list", "--json"])
        assert call_count["n"] == 1

    def test_cache_expires_and_retries(self, monkeypatch):
        import time as _time
        clock = {"now": 1000.0}
        monkeypatch.setattr(
            "oompah.tracker.time.monotonic", lambda: clock["now"],
        )

        call_count = {"n": 0}

        def fake_run(*args, **kwargs):
            call_count["n"] += 1
            return _CompletedProcess(1, "", "Error: no beads database found")

        monkeypatch.setattr(_subprocess, "run", fake_run)
        t = _make_tracker()
        with _pytest.raises(_TNCE):
            t._run_bd(["list", "--json"])
        assert call_count["n"] == 1
        # Advance past the TTL.
        clock["now"] += 61.0
        with _pytest.raises(_TNCE):
            t._run_bd(["list", "--json"])
        # New subprocess call after the cache expired.
        assert call_count["n"] == 2

    def test_successful_call_resets_cache(self, monkeypatch):
        responses = [
            _CompletedProcess(1, "", "Error: no beads database found"),
            _CompletedProcess(0, "[]", ""),
        ]

        def fake_run(*args, **kwargs):
            return responses.pop(0)

        monkeypatch.setattr(_subprocess, "run", fake_run)
        t = _make_tracker()
        with _pytest.raises(_TNCE):
            t._run_bd(["list", "--json"])
        # Manually clear the cache as if TTL elapsed; success must reset it
        # so we don't keep short-circuiting after the user fixed the DB.
        t._missing_db_until = 0.0
        assert t._run_bd(["list", "--json"]) == []
        assert t._missing_db_until == 0.0


class TestMissingDbLogging:
    def test_logs_at_warning_not_error(self, monkeypatch, caplog):
        def fake_run(*args, **kwargs):
            return _CompletedProcess(1, "", "Error: no beads database found")
        monkeypatch.setattr(_subprocess, "run", fake_run)
        import logging as _logging
        with caplog.at_level(_logging.DEBUG, logger="oompah.tracker"):
            t = _make_tracker()
            with _pytest.raises(_TNCE):
                t._run_bd(["list", "--json"])
        # The key contract: error_watcher only fires on ERROR, so we must
        # NOT have logged at ERROR for this environmental condition.
        error_records = [r for r in caplog.records if r.levelname == "ERROR"]
        assert error_records == []
        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warning_records, "expected at least one WARNING on missing-DB"
