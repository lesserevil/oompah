"""Tests for BeadsTracker change-detection (working_set_fingerprint / has_changed)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from oompah.tracker import BeadsTracker, TrackerError


class TestWorkingSetFingerprint:
    """Tests for BeadsTracker.working_set_fingerprint()."""

    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_dolt_commit_hash_strategy(self, mock_run_bd):
        """When bd vc status returns branch+commit, fingerprint uses them."""
        mock_run_bd.return_value = {"branch": "main", "commit": "abc123def456"}
        tracker = self._tracker()
        fp = tracker.working_set_fingerprint()
        assert fp == "dolt:main:abc123def456"
        mock_run_bd.assert_called_once_with(["vc", "status", "--json"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_dolt_commit_includes_branch(self, mock_run_bd):
        """Changing branches produces a different fingerprint."""
        mock_run_bd.return_value = {"branch": "feature", "commit": "abc123def456"}
        tracker = self._tracker()
        fp = tracker.working_set_fingerprint()
        assert fp == "dolt:feature:abc123def456"

    @patch.object(BeadsTracker, "_run_bd")
    def test_dolt_commit_empty_branch(self, mock_run_bd):
        """Missing branch field still works (uses empty string)."""
        mock_run_bd.return_value = {"commit": "abc123def456"}
        tracker = self._tracker()
        fp = tracker.working_set_fingerprint()
        assert fp == "dolt::abc123def456"

    @patch.object(BeadsTracker, "_run_bd")
    def test_fallback_to_status_summary(self, mock_run_bd):
        """When Dolt is unavailable, falls back to status summary hash."""
        def side_effect(args):
            if args[0] == "vc":
                raise TrackerError("Dolt not configured")
            return {
                "summary": {
                    "total_issues": 10,
                    "open_issues": 3,
                    "closed_issues": 7,
                }
            }

        mock_run_bd.side_effect = side_effect
        tracker = self._tracker()
        fp = tracker.working_set_fingerprint()
        assert fp.startswith("summary:")
        assert len(fp) > len("summary:")  # has a hash suffix

    @patch.object(BeadsTracker, "_run_bd")
    def test_status_summary_deterministic(self, mock_run_bd):
        """Same status data produces the same fingerprint."""
        summary = {"summary": {"total_issues": 5, "open_issues": 2, "closed_issues": 3}}

        def side_effect(args):
            if args[0] == "vc":
                raise TrackerError("Dolt not configured")
            return summary

        mock_run_bd.side_effect = side_effect
        tracker = self._tracker()
        fp1 = tracker.working_set_fingerprint()
        fp2 = tracker.working_set_fingerprint()
        assert fp1 == fp2

    @patch.object(BeadsTracker, "_run_bd")
    def test_status_summary_changes_on_different_data(self, mock_run_bd):
        """Different status data produces different fingerprints."""
        call_count = 0

        def side_effect(args):
            nonlocal call_count
            if args[0] == "vc":
                raise TrackerError("Dolt not configured")
            call_count += 1
            if call_count <= 1:
                return {"summary": {"total_issues": 5, "open_issues": 2}}
            return {"summary": {"total_issues": 6, "open_issues": 3}}

        mock_run_bd.side_effect = side_effect
        tracker = self._tracker()
        fp1 = tracker.working_set_fingerprint()
        fp2 = tracker.working_set_fingerprint()
        assert fp1 != fp2

    @patch.object(BeadsTracker, "_run_bd")
    def test_raises_when_both_strategies_fail(self, mock_run_bd):
        """TrackerError raised when neither strategy works."""
        mock_run_bd.side_effect = TrackerError("all commands failed")
        tracker = self._tracker()
        with pytest.raises(TrackerError, match="Unable to compute working set fingerprint"):
            tracker.working_set_fingerprint()

    @patch.object(BeadsTracker, "_run_bd")
    def test_dolt_returns_no_commit_falls_through(self, mock_run_bd):
        """If vc status returns a dict without 'commit', fall back to status."""
        def side_effect(args):
            if args[0] == "vc":
                return {"branch": "main"}  # no commit field
            return {"summary": {"total_issues": 1}}

        mock_run_bd.side_effect = side_effect
        tracker = self._tracker()
        fp = tracker.working_set_fingerprint()
        assert fp.startswith("summary:")

    @patch.object(BeadsTracker, "_run_bd")
    def test_dolt_returns_list_falls_through(self, mock_run_bd):
        """If vc status returns a list instead of dict, fall back to status."""
        def side_effect(args):
            if args[0] == "vc":
                return []  # unexpected list response
            return {"summary": {"total_issues": 1}}

        mock_run_bd.side_effect = side_effect
        tracker = self._tracker()
        fp = tracker.working_set_fingerprint()
        assert fp.startswith("summary:")

    @patch.object(BeadsTracker, "_run_bd")
    def test_status_returns_empty_dict_raises(self, mock_run_bd):
        """If both strategies return empty dicts, TrackerError is raised."""
        def side_effect(args):
            if args[0] == "vc":
                return {}  # no commit
            return []  # status returned a list (unexpected)

        mock_run_bd.side_effect = side_effect
        tracker = self._tracker()
        with pytest.raises(TrackerError, match="Unable to compute working set fingerprint"):
            tracker.working_set_fingerprint()


class TestHasChanged:
    """Tests for BeadsTracker.has_changed()."""

    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_first_call_returns_true(self, mock_run_bd):
        """First call always returns True (no prior fingerprint)."""
        mock_run_bd.return_value = {"branch": "main", "commit": "abc123"}
        tracker = self._tracker()
        assert tracker.has_changed() is True

    @patch.object(BeadsTracker, "_run_bd")
    def test_second_call_same_commit_returns_false(self, mock_run_bd):
        """Second call with same fingerprint returns False."""
        mock_run_bd.return_value = {"branch": "main", "commit": "abc123"}
        tracker = self._tracker()
        tracker.has_changed()  # first call — stores fingerprint
        assert tracker.has_changed() is False

    @patch.object(BeadsTracker, "_run_bd")
    def test_changed_commit_returns_true(self, mock_run_bd):
        """Returns True when commit hash changes between calls."""
        tracker = self._tracker()

        mock_run_bd.return_value = {"branch": "main", "commit": "abc123"}
        tracker.has_changed()  # stores abc123

        mock_run_bd.return_value = {"branch": "main", "commit": "def456"}
        assert tracker.has_changed() is True

    @patch.object(BeadsTracker, "_run_bd")
    def test_changed_branch_returns_true(self, mock_run_bd):
        """Returns True when branch changes even with same commit."""
        tracker = self._tracker()

        mock_run_bd.return_value = {"branch": "main", "commit": "abc123"}
        tracker.has_changed()

        mock_run_bd.return_value = {"branch": "develop", "commit": "abc123"}
        assert tracker.has_changed() is True

    @patch.object(BeadsTracker, "_run_bd")
    def test_multiple_unchanged_calls(self, mock_run_bd):
        """Multiple calls with stable fingerprint all return False."""
        mock_run_bd.return_value = {"branch": "main", "commit": "stable"}
        tracker = self._tracker()
        tracker.has_changed()  # first call
        assert tracker.has_changed() is False
        assert tracker.has_changed() is False
        assert tracker.has_changed() is False

    @patch.object(BeadsTracker, "_run_bd")
    def test_fail_open_on_tracker_error(self, mock_run_bd):
        """Returns True (fail-open) when fingerprint can't be computed."""
        tracker = self._tracker()
        # First call succeeds
        mock_run_bd.return_value = {"branch": "main", "commit": "abc123"}
        tracker.has_changed()

        # Second call fails
        mock_run_bd.side_effect = TrackerError("connection refused")
        assert tracker.has_changed() is True

    @patch.object(BeadsTracker, "_run_bd")
    def test_fail_open_preserves_last_fingerprint(self, mock_run_bd):
        """A failed fingerprint call doesn't overwrite the stored fingerprint."""
        tracker = self._tracker()

        mock_run_bd.return_value = {"branch": "main", "commit": "abc123"}
        tracker.has_changed()
        assert tracker.last_fingerprint == "dolt:main:abc123"

        # Failure doesn't change the stored fingerprint
        mock_run_bd.side_effect = TrackerError("connection refused")
        tracker.has_changed()
        assert tracker.last_fingerprint == "dolt:main:abc123"

    @patch.object(BeadsTracker, "_run_bd")
    def test_updates_fingerprint_on_change(self, mock_run_bd):
        """Stored fingerprint is updated when a change is detected."""
        tracker = self._tracker()

        mock_run_bd.return_value = {"branch": "main", "commit": "abc123"}
        tracker.has_changed()
        assert tracker.last_fingerprint == "dolt:main:abc123"

        mock_run_bd.return_value = {"branch": "main", "commit": "def456"}
        tracker.has_changed()
        assert tracker.last_fingerprint == "dolt:main:def456"

    @patch.object(BeadsTracker, "_run_bd")
    def test_fallback_strategy_has_changed(self, mock_run_bd):
        """has_changed works correctly with the status summary fallback."""
        call_count = 0

        def side_effect(args):
            nonlocal call_count
            if args[0] == "vc":
                raise TrackerError("Dolt not configured")
            call_count += 1
            if call_count <= 2:
                # First two calls to status (one per has_changed call) — same data
                return {"summary": {"total_issues": 5, "open_issues": 2}}
            # Third call — data changed
            return {"summary": {"total_issues": 6, "open_issues": 3}}

        mock_run_bd.side_effect = side_effect
        tracker = self._tracker()

        assert tracker.has_changed() is True  # first call
        assert tracker.has_changed() is False  # same data
        assert tracker.has_changed() is True  # data changed


class TestResetFingerprint:
    """Tests for BeadsTracker.reset_fingerprint()."""

    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_reset_forces_next_has_changed_true(self, mock_run_bd):
        """After reset_fingerprint(), has_changed() returns True."""
        mock_run_bd.return_value = {"branch": "main", "commit": "abc123"}
        tracker = self._tracker()
        tracker.has_changed()  # stores fingerprint
        assert tracker.has_changed() is False  # unchanged

        tracker.reset_fingerprint()
        assert tracker.last_fingerprint is None
        assert tracker.has_changed() is True  # forced refresh

    @patch.object(BeadsTracker, "_run_bd")
    def test_reset_on_fresh_tracker(self, mock_run_bd):
        """Resetting a tracker that was never polled is safe."""
        tracker = self._tracker()
        tracker.reset_fingerprint()  # no-op, already None
        assert tracker.last_fingerprint is None


class TestLastFingerprint:
    """Tests for BeadsTracker.last_fingerprint property."""

    def _tracker(self):
        return BeadsTracker(active_states=["open"], terminal_states=["closed"])

    def test_initial_value_is_none(self):
        """Freshly created tracker has no fingerprint."""
        tracker = self._tracker()
        assert tracker.last_fingerprint is None

    @patch.object(BeadsTracker, "_run_bd")
    def test_set_after_first_fingerprint(self, mock_run_bd):
        """Fingerprint is stored after first successful call."""
        mock_run_bd.return_value = {"branch": "main", "commit": "xyz789"}
        tracker = self._tracker()
        tracker.has_changed()
        assert tracker.last_fingerprint == "dolt:main:xyz789"

    @patch.object(BeadsTracker, "_run_bd")
    def test_direct_fingerprint_call_doesnt_store(self, mock_run_bd):
        """working_set_fingerprint() alone doesn't update the stored fingerprint."""
        mock_run_bd.return_value = {"branch": "main", "commit": "xyz789"}
        tracker = self._tracker()
        fp = tracker.working_set_fingerprint()
        assert fp == "dolt:main:xyz789"
        # last_fingerprint is only updated by has_changed(), not working_set_fingerprint()
        assert tracker.last_fingerprint is None


class TestChangeDetectionIntegration:
    """Integration-style tests for the full change detection workflow."""

    def _tracker(self):
        return BeadsTracker(active_states=["open", "in_progress"], terminal_states=["closed"])

    @patch.object(BeadsTracker, "_run_bd")
    def test_full_lifecycle(self, mock_run_bd):
        """Simulate a realistic sequence: startup → no change → change → reset."""
        tracker = self._tracker()

        # Startup: first poll always returns changed
        mock_run_bd.return_value = {"branch": "main", "commit": "v1"}
        assert tracker.has_changed() is True
        assert tracker.last_fingerprint == "dolt:main:v1"

        # No change: same commit
        assert tracker.has_changed() is False
        assert tracker.has_changed() is False

        # Change detected: new commit
        mock_run_bd.return_value = {"branch": "main", "commit": "v2"}
        assert tracker.has_changed() is True
        assert tracker.last_fingerprint == "dolt:main:v2"

        # Stable again
        assert tracker.has_changed() is False

        # Manual refresh request resets fingerprint
        tracker.reset_fingerprint()
        assert tracker.has_changed() is True  # forced
        assert tracker.last_fingerprint == "dolt:main:v2"

    @patch.object(BeadsTracker, "_run_bd")
    def test_transient_error_recovery(self, mock_run_bd):
        """Tracker recovers cleanly from transient errors."""
        tracker = self._tracker()

        # Successful first poll
        mock_run_bd.return_value = {"branch": "main", "commit": "v1"}
        assert tracker.has_changed() is True

        # Transient failure — fail-open returns True but doesn't corrupt state
        mock_run_bd.side_effect = TrackerError("timeout")
        assert tracker.has_changed() is True
        assert tracker.last_fingerprint == "dolt:main:v1"  # preserved

        # Recovery — same commit as before, should detect no change
        mock_run_bd.side_effect = None
        mock_run_bd.return_value = {"branch": "main", "commit": "v1"}
        assert tracker.has_changed() is False

    @patch.object(BeadsTracker, "_run_bd")
    def test_strategy_switch(self, mock_run_bd):
        """Switching from Dolt to summary strategy still detects changes."""
        tracker = self._tracker()

        # Start with Dolt
        mock_run_bd.return_value = {"branch": "main", "commit": "v1"}
        assert tracker.has_changed() is True
        assert tracker.last_fingerprint == "dolt:main:v1"

        # Dolt becomes unavailable, falls back to summary
        def side_effect(args):
            if args[0] == "vc":
                raise TrackerError("Dolt not configured")
            return {"summary": {"total_issues": 5}}

        mock_run_bd.side_effect = side_effect
        # Different strategy produces different fingerprint → change detected
        assert tracker.has_changed() is True
        assert tracker.last_fingerprint.startswith("summary:")
