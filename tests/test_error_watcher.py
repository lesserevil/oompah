"""Tests for oompah.error_watcher."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from oompah.error_watcher import (
    ErrorWatcher,
    LogFileWatcher,
    ProjectLogWatcherManager,
    _detect_error_level,
    _extract_message,
    _priority_for_level,
)


# ---------------------------------------------------------------------------
# Tests for error-line detection helpers
# ---------------------------------------------------------------------------


class TestDetectErrorLevel:
    def test_error_keyword(self):
        assert _detect_error_level("2024-01-01 12:00:00 ERROR something broke") == "error"

    def test_critical_keyword(self):
        assert _detect_error_level("[CRITICAL] out of memory") == "critical"

    def test_fatal_keyword(self):
        assert _detect_error_level("FATAL: cannot start") == "fatal"

    def test_severe_keyword(self):
        assert _detect_error_level("SEVERE - disk full") == "severe"

    def test_case_insensitive(self):
        assert _detect_error_level("error: something") == "error"
        assert _detect_error_level("Error: something") == "error"

    def test_info_not_detected(self):
        assert _detect_error_level("2024-01-01 INFO all good") is None

    def test_warning_not_detected(self):
        assert _detect_error_level("WARNING: disk space low") is None

    def test_debug_not_detected(self):
        assert _detect_error_level("DEBUG trace details") is None

    def test_empty_line(self):
        assert _detect_error_level("") is None

    def test_no_level_keyword(self):
        assert _detect_error_level("just a normal log line") is None

    def test_level_key_value_format(self):
        assert _detect_error_level('level=error msg="something"') == "error"


class TestPriorityForLevel:
    def test_error(self):
        assert _priority_for_level("error") == 2

    def test_critical(self):
        assert _priority_for_level("critical") == 1

    def test_fatal(self):
        assert _priority_for_level("fatal") == 1

    def test_severe(self):
        assert _priority_for_level("severe") == 1

    def test_unknown(self):
        assert _priority_for_level("unknown") == 2


class TestExtractMessage:
    def test_strips_timestamp_and_level(self):
        line = "2024-01-01T12:00:00 ERROR something broke"
        assert _extract_message(line) == "something broke"

    def test_strips_bracketed_level(self):
        line = "[ERROR] connection refused"
        assert _extract_message(line) == "connection refused"

    def test_strips_level_with_colon(self):
        line = "CRITICAL: out of memory"
        assert _extract_message(line) == "out of memory"

    def test_preserves_meaningful_content(self):
        line = "ERROR database connection failed for host=db01"
        msg = _extract_message(line)
        assert "database connection failed" in msg

    def test_fallback_to_original_line(self):
        line = "ERROR"
        msg = _extract_message(line)
        assert msg == "ERROR"

    def test_complex_timestamp(self):
        line = "2024-01-15 08:30:45.123 ERROR task failed"
        assert _extract_message(line) == "task failed"


# ---------------------------------------------------------------------------
# Tests for ErrorWatcher
# ---------------------------------------------------------------------------


class TestErrorWatcher:
    def _make_watcher(self):
        tracker = MagicMock()
        issue = MagicMock()
        issue.identifier = "test-001"
        tracker.create_issue.return_value = issue
        watcher = ErrorWatcher(tracker)
        return watcher, tracker

    def test_report_error_creates_bead(self):
        watcher, tracker = self._make_watcher()
        result = watcher.report_error("test", "something broke")
        assert result == "test-001"
        tracker.create_issue.assert_called_once()
        call_kwargs = tracker.create_issue.call_args
        assert "something broke" in call_kwargs.kwargs.get("title", "") or "something broke" in str(call_kwargs)

    def test_deduplication(self):
        watcher, tracker = self._make_watcher()
        watcher.report_error("test", "same error")
        watcher.report_error("test", "same error")
        # Should only create one bead
        assert tracker.create_issue.call_count == 1

    def test_different_errors_create_separate_beads(self):
        watcher, tracker = self._make_watcher()
        watcher.report_error("test", "error one")
        watcher.report_error("test", "error two")
        assert tracker.create_issue.call_count == 2

    def test_tracker_failure_returns_none(self):
        tracker = MagicMock()
        tracker.create_issue.side_effect = Exception("db down")
        watcher = ErrorWatcher(tracker)
        result = watcher.report_error("test", "something broke")
        assert result is None

    def test_title_truncation(self):
        watcher, tracker = self._make_watcher()
        long_msg = "x" * 300
        watcher.report_error("test", long_msg)
        call_kwargs = tracker.create_issue.call_args
        title = call_kwargs.kwargs.get("title", "")
        assert len(title) <= 200


# ---------------------------------------------------------------------------
# Tests for LogFileWatcher
# ---------------------------------------------------------------------------


class TestLogFileWatcher:
    def test_init(self):
        error_watcher = MagicMock()
        watcher = LogFileWatcher("/tmp/test.log", error_watcher, "myapp")
        assert watcher.log_path == "/tmp/test.log"
        assert not watcher.is_running

    def test_seek_to_end_nonexistent_file(self):
        error_watcher = MagicMock()
        watcher = LogFileWatcher("/nonexistent/file.log", error_watcher)
        watcher._seek_to_end()
        assert watcher._file_offset == 0

    def test_poll_file_detects_error_lines(self):
        error_watcher = MagicMock()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("INFO: all good\n")
            f.write("ERROR: something broke\n")
            f.write("DEBUG: trace info\n")
            f.flush()
            log_path = f.name

        try:
            watcher = LogFileWatcher(log_path, error_watcher, "testapp")
            watcher._file_offset = 0
            watcher._inode = os.stat(log_path).st_ino
            watcher._poll_file()

            # Should have reported exactly one error
            assert error_watcher.report_error.call_count == 1
            call_kwargs = error_watcher.report_error.call_args
            assert call_kwargs.kwargs.get("source") == "log:testapp" or call_kwargs[0][0] == "log:testapp"
        finally:
            os.unlink(log_path)

    def test_poll_file_detects_critical(self):
        error_watcher = MagicMock()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("CRITICAL: out of memory\n")
            f.flush()
            log_path = f.name

        try:
            watcher = LogFileWatcher(log_path, error_watcher, "testapp")
            watcher._file_offset = 0
            watcher._inode = os.stat(log_path).st_ino
            watcher._poll_file()

            assert error_watcher.report_error.call_count == 1
            call_kwargs = error_watcher.report_error.call_args
            assert call_kwargs.kwargs.get("priority") == 1
        finally:
            os.unlink(log_path)

    def test_poll_file_ignores_non_error_lines(self):
        error_watcher = MagicMock()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("INFO: starting up\n")
            f.write("DEBUG: loaded config\n")
            f.write("WARNING: disk space low\n")
            f.flush()
            log_path = f.name

        try:
            watcher = LogFileWatcher(log_path, error_watcher, "testapp")
            watcher._file_offset = 0
            watcher._inode = os.stat(log_path).st_ino
            watcher._poll_file()

            assert error_watcher.report_error.call_count == 0
        finally:
            os.unlink(log_path)

    def test_poll_file_nonexistent(self):
        error_watcher = MagicMock()
        watcher = LogFileWatcher("/nonexistent/file.log", error_watcher)
        # Should not raise
        watcher._poll_file()
        assert error_watcher.report_error.call_count == 0

    def test_incremental_reading(self):
        """Verify that the watcher only processes new lines added after seek."""
        error_watcher = MagicMock()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("ERROR: old error\n")
            f.flush()
            log_path = f.name

        try:
            watcher = LogFileWatcher(log_path, error_watcher, "testapp")
            # Seek to end — should skip the existing content
            watcher._seek_to_end()

            watcher._poll_file()
            assert error_watcher.report_error.call_count == 0

            # Append a new error
            with open(log_path, "a") as f:
                f.write("ERROR: new error\n")

            watcher._poll_file()
            assert error_watcher.report_error.call_count == 1
        finally:
            os.unlink(log_path)

    def test_file_truncation_detection(self):
        """Verify that file truncation (rotation) is handled correctly."""
        error_watcher = MagicMock()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("x" * 1000 + "\n")
            f.flush()
            log_path = f.name

        try:
            watcher = LogFileWatcher(log_path, error_watcher, "testapp")
            watcher._seek_to_end()
            assert watcher._file_offset > 0

            # Truncate the file (simulating rotation without inode change)
            with open(log_path, "w") as f:
                f.write("ERROR: after truncation\n")

            watcher._poll_file()
            assert error_watcher.report_error.call_count == 1
        finally:
            os.unlink(log_path)

    def test_stop_before_start_is_noop(self):
        """stop() before start() should be a no-op (no stop event set yet)."""
        error_watcher = MagicMock()
        watcher = LogFileWatcher("/tmp/test.log", error_watcher)
        assert watcher._stop_event is None
        # Without start(), _stop_event is None — stop() should not raise
        watcher.stop()
        assert not watcher.is_running
        assert watcher._stop_event is None  # still None since we never started

    def test_stop_before_start_does_not_raise(self):
        """stop() before start() should be a no-op and not raise."""
        error_watcher = MagicMock()
        watcher = LogFileWatcher("/tmp/test.log", error_watcher)
        watcher.stop()  # Should not raise

    def test_watch_path_returns_file_when_exists(self):
        """_watch_path() returns the log file path when it exists."""
        error_watcher = MagicMock()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            watcher = LogFileWatcher(log_path, error_watcher)
            assert watcher._watch_path() == log_path
        finally:
            os.unlink(log_path)

    def test_watch_path_returns_parent_when_file_missing(self):
        """_watch_path() returns the parent dir when the log file does not exist."""
        error_watcher = MagicMock()
        log_path = "/tmp/definitely_nonexistent_test_log_file.log"
        watcher = LogFileWatcher(log_path, error_watcher)
        watch_path = watcher._watch_path()
        assert watch_path == "/tmp"
        assert watch_path != log_path

    def test_make_watch_filter_matches_target_file(self):
        """_make_watch_filter() returns a filter that matches only the target file."""
        error_watcher = MagicMock()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_path = f.name
        try:
            watcher = LogFileWatcher(log_path, error_watcher)
            filt = watcher._make_watch_filter()
            # Should accept the target file
            assert filt(None, log_path) is True
            # Should reject other files
            assert filt(None, "/tmp/other_file.log") is False
            assert filt(None, "/var/log/syslog") is False
        finally:
            os.unlink(log_path)

    def test_start_and_stop(self):
        """Integration test: start the watcher, write an error, verify detection."""
        tracker = MagicMock()
        issue = MagicMock()
        issue.identifier = "test-001"
        tracker.create_issue.return_value = issue
        ew = ErrorWatcher(tracker)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_path = f.name

        async def _run():
            watcher = LogFileWatcher(log_path, ew, "testapp")
            task = asyncio.create_task(watcher.start())

            # Give it time to start
            await asyncio.sleep(0.15)
            assert watcher.is_running

            # Write an error
            with open(log_path, "a") as f:
                f.write("ERROR: async detected error\n")

            # Wait for it to be picked up (event-driven, should be fast)
            await asyncio.sleep(0.5)

            watcher.stop()
            await asyncio.sleep(0.3)
            assert not watcher.is_running

            assert tracker.create_issue.call_count == 1

        try:
            asyncio.run(_run())
        finally:
            os.unlink(log_path)

    def test_start_and_stop_event_driven(self):
        """Event-driven test: watcher should react quickly to file changes."""
        tracker = MagicMock()
        issue = MagicMock()
        issue.identifier = "test-event-001"
        tracker.create_issue.return_value = issue
        ew = ErrorWatcher(tracker)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_path = f.name

        async def _run():
            watcher = LogFileWatcher(log_path, ew, "testapp")
            task = asyncio.create_task(watcher.start())

            # Give it time to start
            await asyncio.sleep(0.2)

            # Write multiple errors
            with open(log_path, "a") as f:
                f.write("ERROR: first failure\n")
                f.write("CRITICAL: second failure\n")
                f.write("INFO: all systems go\n")  # not an error line

            # Event-driven: should be picked up quickly
            await asyncio.sleep(0.5)

            watcher.stop()
            await asyncio.sleep(0.3)

            # Should have detected 2 errors (ERROR + CRITICAL), not INFO
            assert tracker.create_issue.call_count == 2

        try:
            asyncio.run(_run())
        finally:
            os.unlink(log_path)

    def test_stop_event_terminates_watcher(self):
        """Watcher terminates cleanly when stop() is called via stop_event."""
        error_watcher = MagicMock()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_path = f.name

        async def _run():
            watcher = LogFileWatcher(log_path, error_watcher)
            task = asyncio.create_task(watcher.start())
            await asyncio.sleep(0.2)
            assert watcher.is_running

            # stop() should signal via the event
            watcher.stop()
            assert watcher._stop_event is not None
            assert watcher._stop_event.is_set()

            # Wait for the task to finish
            await asyncio.sleep(0.5)
            assert not watcher.is_running

        try:
            asyncio.run(_run())
        finally:
            os.unlink(log_path)


# ---------------------------------------------------------------------------
# Tests for ProjectLogWatcherManager
# ---------------------------------------------------------------------------


class TestProjectLogWatcherManager:
    def _make_project(self, pid, name, log_path=None):
        p = MagicMock()
        p.id = pid
        p.name = name
        p.log_path = log_path
        return p

    def test_sync_starts_watcher_for_project_with_log_path(self):
        factory = MagicMock()
        factory.return_value = MagicMock()
        manager = ProjectLogWatcherManager(factory)

        projects = [self._make_project("p1", "proj1", "/tmp/test.log")]

        # Need an event loop for asyncio.ensure_future
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Patch asyncio.ensure_future to avoid actually starting coroutines
            with patch("oompah.error_watcher.asyncio.ensure_future") as mock_future:
                mock_future.return_value = MagicMock()
                manager.sync_watchers(projects)

            assert "p1" in manager._watchers
            factory.assert_called_once_with("p1")
        finally:
            loop.close()

    def test_sync_ignores_project_without_log_path(self):
        factory = MagicMock()
        manager = ProjectLogWatcherManager(factory)

        projects = [self._make_project("p1", "proj1", None)]

        manager.sync_watchers(projects)

        assert "p1" not in manager._watchers
        factory.assert_not_called()

    def test_sync_stops_removed_project(self):
        factory = MagicMock()
        factory.return_value = MagicMock()
        manager = ProjectLogWatcherManager(factory)

        projects = [self._make_project("p1", "proj1", "/tmp/test.log")]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with patch("oompah.error_watcher.asyncio.ensure_future") as mock_future:
                mock_task = MagicMock()
                mock_future.return_value = mock_task
                manager.sync_watchers(projects)
                assert "p1" in manager._watchers

                # Remove the project
                manager.sync_watchers([])
                assert "p1" not in manager._watchers
                mock_task.cancel.assert_called()
        finally:
            loop.close()

    def test_sync_restarts_on_log_path_change(self):
        factory = MagicMock()
        factory.return_value = MagicMock()
        manager = ProjectLogWatcherManager(factory)

        projects = [self._make_project("p1", "proj1", "/tmp/old.log")]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with patch("oompah.error_watcher.asyncio.ensure_future") as mock_future:
                mock_task1 = MagicMock()
                mock_task2 = MagicMock()
                mock_future.side_effect = [mock_task1, mock_task2]

                manager.sync_watchers(projects)
                old_watcher = manager._watchers["p1"][0]
                assert old_watcher.log_path == "/tmp/old.log"

                # Change log_path
                projects = [self._make_project("p1", "proj1", "/tmp/new.log")]
                manager.sync_watchers(projects)

                # Old task should be cancelled, new watcher created
                mock_task1.cancel.assert_called()
                assert manager._watchers["p1"][0].log_path == "/tmp/new.log"
        finally:
            loop.close()

    def test_stop_all(self):
        factory = MagicMock()
        factory.return_value = MagicMock()
        manager = ProjectLogWatcherManager(factory)

        projects = [
            self._make_project("p1", "proj1", "/tmp/a.log"),
            self._make_project("p2", "proj2", "/tmp/b.log"),
        ]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with patch("oompah.error_watcher.asyncio.ensure_future") as mock_future:
                mock_future.return_value = MagicMock()
                manager.sync_watchers(projects)
                assert len(manager._watchers) == 2

                manager.stop_all()
                assert len(manager._watchers) == 0
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Tests for Project model log_path field
# ---------------------------------------------------------------------------


class TestProjectLogPath:
    def test_to_dict_includes_log_path(self):
        from oompah.models import Project
        p = Project(
            id="p1", name="test", repo_url="https://example.com/repo.git",
            repo_path="/tmp/repo", log_path="/var/log/test.log",
        )
        d = p.to_dict()
        assert d["log_path"] == "/var/log/test.log"

    def test_to_dict_omits_log_path_when_none(self):
        from oompah.models import Project
        p = Project(
            id="p1", name="test", repo_url="https://example.com/repo.git",
            repo_path="/tmp/repo",
        )
        d = p.to_dict()
        assert "log_path" not in d

    def test_from_dict_with_log_path(self):
        from oompah.models import Project
        d = {
            "id": "p1", "name": "test", "repo_url": "https://example.com/repo.git",
            "repo_path": "/tmp/repo", "log_path": "/var/log/test.log",
        }
        p = Project.from_dict(d)
        assert p.log_path == "/var/log/test.log"

    def test_from_dict_without_log_path(self):
        from oompah.models import Project
        d = {
            "id": "p1", "name": "test", "repo_url": "https://example.com/repo.git",
            "repo_path": "/tmp/repo",
        }
        p = Project.from_dict(d)
        assert p.log_path is None
