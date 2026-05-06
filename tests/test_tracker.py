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

    def test_branch_name_derived_from_identifier_when_missing(self):
        """When branch_name is not in bd output, derive it from identifier.

        This ensures WORKFLOW.md prompts show the correct branch name that
        matches the git worktree created by projects.py. Hyphens are preserved
        (matching _sanitize_identifier behavior in projects.py).
        """
        raw = {
            "id": "1", "identifier": "oompah-zlz_2-7au",
            "title": "Test issue",
        }
        issue = self._tracker()._normalize_issue(raw)
        # branch_name should be the sanitized identifier (hyphens preserved)
        assert issue.branch_name == "oompah-zlz_2-7au"

    def test_branch_name_preserved_when_provided(self):
        """When branch_name is present in bd output, use it as-is."""
        raw = {
            "id": "1",
            "identifier": "issue-001",
            "title": "Test issue",
            "branch_name": "custom-branch-name",
        }
        issue = self._tracker()._normalize_issue(raw)
        assert issue.branch_name == "custom-branch-name"

    def test_branch_name_sanitization_replaces_special_chars(self):
        """Identifier with special characters should be sanitized for branch name.

        projects.py uses _sanitize_identifier to create branch names, so
        the tracker must use the same logic to ensure consistency.
        """
        raw = {
            "id": "1",
            "identifier": "sq-3j2/special!chars@here",
            "title": "Test issue",
        }
        issue = self._tracker()._normalize_issue(raw)
        # Underscores should replace all non-alphanumeric chars except ._-
        assert issue.branch_name == "sq-3j2_special_chars_here"

    def test_branch_name_sanitization_preserves_allowed_chars(self):
        """Allowed characters (., _, -) should be preserved in branch names."""
        raw = {
            "id": "1",
            "identifier": "issue.1_with-dashes.and_underscores",
            "title": "Test issue",
        }
        issue = self._tracker()._normalize_issue(raw)
        assert issue.branch_name == "issue.1_with-dashes.and_underscores"


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

    @patch.object(BeadsTracker, "_run_bd")
    def test_create_with_labels_passed_to_bd(self, mock_run_bd):
        """When labels= is supplied, --labels=a,b is passed to bd create."""
        mock_run_bd.return_value = {
            "id": "test-6", "title": "Labeled", "status": "open", "priority": 0,
        }

        tracker = self._tracker()
        tracker.create_issue(
            title="Labeled",
            initial_status="open",
            labels=["ci-fix", "urgent"],
        )

        # Only the create call (initial_status='open' skips update)
        assert mock_run_bd.call_count == 1
        args = mock_run_bd.call_args_list[0][0][0]
        assert "--labels=ci-fix,urgent" in args

    @patch.object(BeadsTracker, "_run_bd")
    def test_create_with_parent_passed_to_bd(self, mock_run_bd):
        """When parent= is supplied, --parent=<id> is passed to bd create."""
        mock_run_bd.return_value = {
            "id": "test-7", "title": "Child", "status": "open", "priority": 0,
        }

        tracker = self._tracker()
        tracker.create_issue(
            title="Child",
            initial_status="open",
            parent="parent-001",
        )

        assert mock_run_bd.call_count == 1
        args = mock_run_bd.call_args_list[0][0][0]
        assert "--parent=parent-001" in args

    @patch.object(BeadsTracker, "_run_bd")
    def test_create_without_labels_or_parent_omits_flags(self, mock_run_bd):
        """When neither labels nor parent are supplied, no --labels / --parent
        flags are added to bd create."""
        mock_run_bd.return_value = {
            "id": "test-8", "title": "Plain", "status": "open", "priority": 2,
        }

        tracker = self._tracker()
        tracker.create_issue(title="Plain", initial_status="open")

        assert mock_run_bd.call_count == 1
        args = mock_run_bd.call_args_list[0][0][0]
        assert not any(a.startswith("--labels=") for a in args)
        assert not any(a.startswith("--parent=") for a in args)


# ---------------------------------------------------------------------------
# Candidate fetch / dispatch query (oompah-zlz_2-k5a)
#
# Regression coverage for the "Failed to fetch candidates: bd command timed
# out: bd list --json" bug. The old implementation looped per-status and on
# any TrackerError fell back to an unfiltered, unlimited 'bd list --json'
# call, repeated once per active status — the heaviest possible query, run
# N times. The fix collapses the loop into a single
# 'bd list --status=<comma-list> --limit=0 --json' call and drops the
# fallback.
# ---------------------------------------------------------------------------


class TestFetchCandidateIssues:
    _SENTINEL = object()

    def _tracker(self, active_states=_SENTINEL):
        # Distinguish "default" from "explicit empty" — `or` would treat
        # [] as falsy and pick the default, hiding bugs in the empty path.
        if active_states is self._SENTINEL:
            active_states = ["open", "in_progress"]
        return BeadsTracker(
            active_states=active_states,
            terminal_states=["closed"],
        )

    @patch.object(BeadsTracker, "_run_bd")
    def test_single_call_with_comma_separated_status(self, mock_run_bd):
        """One bd call covering every active state — no per-status loop."""
        mock_run_bd.return_value = []
        tracker = self._tracker(["open", "in_progress"])
        tracker.fetch_candidate_issues()

        assert mock_run_bd.call_count == 1
        args = mock_run_bd.call_args_list[0].args[0]
        assert args == [
            "list",
            "--status=open,in_progress",
            "--limit=0",
            "--json",
        ]

    @patch.object(BeadsTracker, "_run_bd")
    def test_single_active_state(self, mock_run_bd):
        """Single-state config still uses --status filter (not --all)."""
        mock_run_bd.return_value = []
        tracker = self._tracker(["open"])
        tracker.fetch_candidate_issues()
        args = mock_run_bd.call_args_list[0].args[0]
        assert args == ["list", "--status=open", "--limit=0", "--json"]

    @patch.object(BeadsTracker, "_run_bd")
    def test_no_fallback_on_tracker_error(self, mock_run_bd):
        """A TrackerError must propagate — no second 'bd list --json' call.

        This is the regression for oompah-zlz_2-k5a: the old fallback ran
        an unfiltered 'bd list --json' that timed out under contention,
        spamming ERROR logs and starving dispatch.
        """
        from oompah.tracker import TrackerError

        mock_run_bd.side_effect = TrackerError(
            "bd command timed out: bd list --status=open,in_progress --json"
        )
        tracker = self._tracker(["open", "in_progress"])

        try:
            tracker.fetch_candidate_issues()
        except TrackerError:
            pass
        else:
            raise AssertionError("expected TrackerError to propagate")

        # Exactly one bd call — no fallback to the heavier unfiltered query.
        assert mock_run_bd.call_count == 1

    @patch.object(BeadsTracker, "_run_bd")
    def test_no_active_states_short_circuits(self, mock_run_bd):
        """An empty active_states config returns [] without hitting bd."""
        tracker = self._tracker([])
        result = tracker.fetch_candidate_issues()
        assert result == []
        mock_run_bd.assert_not_called()

    @patch.object(BeadsTracker, "_run_bd")
    def test_filters_inactive_states_returned_by_bd(self, mock_run_bd):
        """Defensively drop any rows whose state isn't in active_states.

        Protects against a bd query that ignores the filter or returns
        adjacent statuses by mistake.
        """
        mock_run_bd.return_value = [
            {"id": "1", "identifier": "p-1", "title": "a", "status": "open",
             "priority": 1, "created_at": "2025-01-01T00:00:00Z"},
            {"id": "2", "identifier": "p-2", "title": "b", "status": "closed",
             "priority": 0, "created_at": "2025-01-01T00:00:00Z"},
            {"id": "3", "identifier": "p-3", "title": "c", "status": "in_progress",
             "priority": 2, "created_at": "2025-01-01T00:00:00Z"},
        ]
        issues = self._tracker(["open", "in_progress"]).fetch_candidate_issues()
        ids = {i.id for i in issues}
        assert ids == {"1", "3"}

    @patch.object(BeadsTracker, "_run_bd")
    def test_dedupes_by_id(self, mock_run_bd):
        """Duplicate rows from bd are collapsed once."""
        mock_run_bd.return_value = [
            {"id": "1", "identifier": "p-1", "title": "a", "status": "open",
             "priority": 1, "created_at": "2025-01-01T00:00:00Z"},
            {"id": "1", "identifier": "p-1", "title": "a", "status": "open",
             "priority": 1, "created_at": "2025-01-01T00:00:00Z"},
        ]
        issues = self._tracker(["open"]).fetch_candidate_issues()
        assert [i.id for i in issues] == ["1"]

    @patch.object(BeadsTracker, "_run_bd")
    def test_sorted_by_priority_then_created_then_identifier(self, mock_run_bd):
        """Sort key: priority asc (None last), created_at asc, identifier asc."""
        mock_run_bd.return_value = [
            {"id": "a", "identifier": "p-2", "title": "later",  "status": "open",
             "priority": 1, "created_at": "2025-02-01T00:00:00Z"},
            {"id": "b", "identifier": "p-1", "title": "older",  "status": "open",
             "priority": 1, "created_at": "2025-01-01T00:00:00Z"},
            {"id": "c", "identifier": "p-3", "title": "p0",     "status": "open",
             "priority": 0, "created_at": "2025-03-01T00:00:00Z"},
            {"id": "d", "identifier": "p-4", "title": "noprio", "status": "open",
             "created_at": "2025-01-01T00:00:00Z"},
        ]
        ordered = [i.id for i in self._tracker(["open"]).fetch_candidate_issues()]
        # priority 0 first, then priority 1 (older first), then no-priority
        assert ordered == ["c", "b", "a", "d"]

    @patch.object(BeadsTracker, "_run_bd")
    def test_not_configured_propagates_without_log_spam(self, mock_run_bd):
        """TrackerNotConfiguredError must bubble up unchanged (caller throttles)."""
        from oompah.tracker import TrackerNotConfiguredError

        mock_run_bd.side_effect = TrackerNotConfiguredError("no beads database found")
        tracker = self._tracker(["open"])
        try:
            tracker.fetch_candidate_issues()
        except TrackerNotConfiguredError:
            pass
        else:
            raise AssertionError("expected TrackerNotConfiguredError to propagate")
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
    TrackerTimeoutError as _TTE,
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


# ---------------------------------------------------------------------------
# Timeout handling: TrackerTimeoutError + WARNING-only logs.
# Covers oompah-zlz_2-sm5 (and 7 dupes): a slow ``bd list --json`` was
# producing an ERROR log on every tick, which the error_watcher escalated
# into fresh duplicate bug beads with title:
#   [backend:tracker] Failed to fetch candidates: bd command timed out: bd list --json
# ---------------------------------------------------------------------------


class TestTimeoutHandling:
    def test_run_bd_raises_timeout_subclass(self, monkeypatch):
        def fake_run(*args, **kwargs):
            raise _subprocess.TimeoutExpired(cmd=kwargs.get("cmd", ["bd"]), timeout=1)
        monkeypatch.setattr(_subprocess, "run", fake_run)
        t = _make_tracker()
        with _pytest.raises(_TTE) as exc_info:
            t._run_bd(["list", "--json"])
        # Must also be a TrackerError so existing ``except TrackerError``
        # callers still catch it.
        assert isinstance(exc_info.value, _TE)
        assert "bd list --json" in str(exc_info.value)

    def test_default_timeout_is_60_seconds(self, monkeypatch):
        captured = {}

        def fake_run(*args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return _CompletedProcess(0, "[]", "")

        monkeypatch.setattr(_subprocess, "run", fake_run)
        t = _make_tracker()
        t._run_bd(["list", "--json"])
        # Bumped from 30s to 60s to give the heavy fallback path room.
        assert captured["timeout"] == 60

    def test_explicit_timeout_override(self, monkeypatch):
        captured = {}

        def fake_run(*args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return _CompletedProcess(0, "[]", "")

        monkeypatch.setattr(_subprocess, "run", fake_run)
        t = _make_tracker()
        t._run_bd(["list", "--json"], timeout=5)
        assert captured["timeout"] == 5


class TestFetchCandidatesTimeoutLogging:
    """The error_watcher only fires on ERROR-level records. Timeouts are
    transient/environmental, so they MUST be logged at WARNING in
    fetch_candidate_issues' fallback path — not ERROR — to avoid the
    duplicate-bug-bead flood.
    """

    def test_timeout_in_fallback_logs_warning_not_error(
        self, monkeypatch, caplog,
    ):
        def fake_run(*args, **kwargs):
            # Both the status-filtered call and the unfiltered fallback
            # time out — same root cause (busy DB).
            raise _subprocess.TimeoutExpired(cmd=["bd"], timeout=1)

        monkeypatch.setattr(_subprocess, "run", fake_run)
        import logging as _logging
        t = _BT(active_states=["open"], terminal_states=["closed"], cwd="/tmp/x")
        with caplog.at_level(_logging.DEBUG, logger="oompah.tracker"):
            with _pytest.raises(_TTE):
                t.fetch_candidate_issues()
        error_records = [
            r for r in caplog.records
            if r.levelname == "ERROR" and "Failed to fetch candidates" in r.getMessage()
        ]
        assert error_records == [], (
            "timeouts must NOT log at ERROR (would auto-file a bug bead "
            "every poll tick via error_watcher)"
        )
        warning_records = [
            r for r in caplog.records
            if r.levelname == "WARNING"
            and "Failed to fetch candidates" in r.getMessage()
        ]
        assert warning_records, (
            "expected exactly one WARNING describing the timeout fallback"
        )

    def test_non_timeout_failure_in_fallback_still_logs_error(
        self, monkeypatch, caplog,
    ):
        # A *non*-timeout, non-missing-DB error in the fallback path is a
        # real bug we want to capture — keep ERROR there.
        responses = [
            # Status-filtered call: generic failure.
            _CompletedProcess(1, "", "Error: something else went wrong"),
            # Fallback unfiltered call: same generic failure.
            _CompletedProcess(1, "", "Error: something else went wrong"),
        ]

        def fake_run(*args, **kwargs):
            return responses.pop(0)

        monkeypatch.setattr(_subprocess, "run", fake_run)
        import logging as _logging
        t = _BT(active_states=["open"], terminal_states=["closed"], cwd="/tmp/x")
        with caplog.at_level(_logging.DEBUG, logger="oompah.tracker"):
            with _pytest.raises(_TE):
                t.fetch_candidate_issues()
        error_records = [
            r for r in caplog.records
            if r.levelname == "ERROR" and "Failed to fetch candidates" in r.getMessage()
        ]
        assert error_records, (
            "non-timeout, non-missing-DB failures should still log at ERROR"
        )
