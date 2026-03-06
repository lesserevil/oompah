"""Tests for oompah.tracker (parsing/normalization only)."""

from datetime import datetime, timezone
from unittest.mock import patch, call

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
