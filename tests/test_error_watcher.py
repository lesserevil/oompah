"""Tests for oompah.error_watcher."""

from __future__ import annotations

import asyncio
import logging
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
from oompah.models import Issue


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

    def test_report_error_creates_task(self):
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
        # Should only create one task
        assert tracker.create_issue.call_count == 1

    def test_different_errors_create_separate_tasks(self):
        watcher, tracker = self._make_watcher()
        watcher.report_error("test", "error one")
        watcher.report_error("test", "error two")
        assert tracker.create_issue.call_count == 2

    def test_existing_non_terminal_error_task_suppresses_fresh_watcher_create(self):
        tracker = MagicMock()
        existing_watcher = ErrorWatcher(tracker)
        fp = existing_watcher._fingerprint("test", "same persisted error")
        tracker.fetch_all_issues.return_value = [
            Issue(
                id="task-123",
                identifier="TASK-123",
                title="[test] same persisted error",
                description=f"*Auto-filed by oompah error_watcher*\n- dedup_fingerprint: {fp}",
                state="Proposed",
            )
        ]

        fresh_watcher = ErrorWatcher(tracker)
        result = fresh_watcher.report_error("test", "same persisted error")

        assert result is None
        tracker.create_issue.assert_not_called()
        tracker.add_comment.assert_called_once()
        assert tracker.add_comment.call_args.args[0] == "TASK-123"
        assert "Duplicate error_watcher occurrence suppressed" in tracker.add_comment.call_args.args[1]
        assert next(iter(fresh_watcher._seen.values())).task_id == "TASK-123"

    def test_existing_terminal_error_task_does_not_suppress_new_create(self):
        tracker = MagicMock()
        issue = MagicMock()
        issue.identifier = "TASK-999"
        tracker.create_issue.return_value = issue
        existing_watcher = ErrorWatcher(tracker)
        fp = existing_watcher._fingerprint("test", "same persisted error")
        tracker.fetch_all_issues.return_value = [
            Issue(
                id="task-123",
                identifier="TASK-123",
                title="[test] same persisted error",
                description=f"*Auto-filed by oompah error_watcher*\n- dedup_fingerprint: {fp}",
                state="Archived",
            )
        ]

        fresh_watcher = ErrorWatcher(tracker)
        result = fresh_watcher.report_error("test", "same persisted error")

        assert result == "TASK-999"
        tracker.create_issue.assert_called_once()
        tracker.add_comment.assert_not_called()

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
# Tests for issue-aware error tracking + retry-success auto-close
# (oompah-zlz_2-0nc)
# ---------------------------------------------------------------------------


class TestErrorWatcherAutoClose:
    """Verify ErrorWatcher.report_error/auto_close_for_issue behavior."""

    def _make_watcher(self, task_id: str = "oompah-test-001"):
        tracker = MagicMock()
        issue = MagicMock()
        issue.identifier = task_id
        tracker.create_issue.return_value = issue
        watcher = ErrorWatcher(tracker)
        return watcher, tracker

    def test_report_error_with_issue_id_records_link(self):
        watcher, tracker = self._make_watcher()
        task = watcher.report_error(
            "backend:worker",
            "transient errno 57",
            issue_id="orig-issue-123",
        )
        assert task == "oompah-test-001"
        # Find the seen record and verify the link.
        records = list(watcher._seen.values())
        assert len(records) == 1
        rec = records[0]
        assert rec.issue_id == "orig-issue-123"
        assert rec.task_id == "oompah-test-001"

    def test_auto_close_with_no_issue_id_does_nothing(self):
        watcher, tracker = self._make_watcher()
        # No issue_id passed → record has no link.
        watcher.report_error("backend:worker", "transient errno 57")
        # Force the record old enough to bypass the quiet window.
        for rec in watcher._seen.values():
            rec.last_created -= 120
        closed = watcher.auto_close_for_issue("orig-issue-123")
        assert closed == []
        tracker.close_issue.assert_not_called()

    def test_auto_close_after_retry_success(self):
        """fingerprint+issue_id, retry success → auto-closed."""
        watcher, tracker = self._make_watcher(task_id="oompah-test-001")
        watcher.report_error(
            "backend:worker",
            "transient errno 57",
            issue_id="orig-issue-123",
        )
        # Step the clock past the 60s quiet window so auto-close fires.
        for rec in watcher._seen.values():
            rec.last_created -= 120
        closed = watcher.auto_close_for_issue(
            "orig-issue-123",
            issue_identifier="oompah-zlz_2-orig",
        )
        assert closed == ["oompah-test-001"]
        # close_issue called with reason
        tracker.close_issue.assert_called_once()
        args, kwargs = tracker.close_issue.call_args
        assert args[0] == "oompah-test-001"
        assert "retry succeeded" in kwargs.get("reason", "")
        # Record popped so a future error will create a fresh task.
        assert not watcher._seen

    def test_auto_close_only_targets_matching_issue(self):
        """Only tasks tied to the matching issue_id get closed."""
        watcher, tracker = self._make_watcher()
        # Two different tasks, two different issues.
        task_a = MagicMock(); task_a.identifier = "oompah-task-A"
        task_b = MagicMock(); task_b.identifier = "oompah-task-B"
        tracker.create_issue.side_effect = [task_a, task_b]
        watcher.report_error("backend:a", "first error", issue_id="issue-A")
        watcher.report_error("backend:b", "second error", issue_id="issue-B")
        # Move both records out of the quiet window
        for rec in watcher._seen.values():
            rec.last_created -= 120
        closed = watcher.auto_close_for_issue("issue-A")
        assert closed == ["oompah-task-A"]
        # Only A was closed; B remains in _seen
        remaining_tasks = {r.task_id for r in watcher._seen.values()}
        assert remaining_tasks == {"oompah-task-B"}

    def test_no_recovery_keeps_task_deferred(self):
        """fingerprint+issue_id, no recovery → stays deferred."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            "backend:worker",
            "permanent failure",
            issue_id="orig-issue-456",
        )
        # auto_close is only called on retry success; never invoking it
        # should leave the task untouched.
        tracker.close_issue.assert_not_called()
        assert len(watcher._seen) == 1
        assert next(iter(watcher._seen.values())).task_id is not None

    def test_auto_close_skipped_within_quiet_window(self):
        """Recent errors guard: don't close while fingerprint is hot."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            "backend:worker",
            "still firing",
            issue_id="orig-issue-789",
        )
        # last_created is "now" — within the quiet window — so
        # auto_close_for_issue must skip it (the same fingerprint may
        # be erroring on another issue right now).
        closed = watcher.auto_close_for_issue("orig-issue-789")
        assert closed == []
        tracker.close_issue.assert_not_called()
        # Record stays in _seen so future success can still auto-close
        assert len(watcher._seen) == 1

    def test_auto_close_skipped_when_task_too_old(self):
        """Stale records (>30 min) are skipped — operator owns them."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            "backend:worker",
            "ancient error",
            issue_id="orig-issue-old",
        )
        # Push the record well past max_age_seconds.
        for rec in watcher._seen.values():
            rec.last_created -= 4000  # ~67 min ago
        closed = watcher.auto_close_for_issue("orig-issue-old")
        assert closed == []
        tracker.close_issue.assert_not_called()

    def test_auto_close_chain_of_retries(self):
        """Multiple distinct errors → all auto-close on success."""
        watcher, tracker = self._make_watcher()
        task_a = MagicMock(); task_a.identifier = "oompah-task-A"
        task_b = MagicMock(); task_b.identifier = "oompah-task-B"
        task_c = MagicMock(); task_c.identifier = "oompah-task-C"
        tracker.create_issue.side_effect = [task_a, task_b, task_c]
        # All three errors during the same issue's retry chain.
        watcher.report_error("backend:net", "errno 57", issue_id="issue-X")
        watcher.report_error("backend:net", "timeout", issue_id="issue-X")
        watcher.report_error("backend:db", "deadlock", issue_id="issue-X")
        for rec in watcher._seen.values():
            rec.last_created -= 120
        closed = watcher.auto_close_for_issue("issue-X")
        assert sorted(closed) == ["oompah-task-A", "oompah-task-B", "oompah-task-C"]
        assert tracker.close_issue.call_count == 3
        assert not watcher._seen

    def test_auto_close_swallows_close_failures(self):
        """tracker errors during auto-close shouldn't propagate."""
        watcher, tracker = self._make_watcher()
        watcher.report_error("backend:x", "boom", issue_id="orig-y")
        for rec in watcher._seen.values():
            rec.last_created -= 120
        tracker.close_issue.side_effect = Exception("tracker unreachable")
        # Should not raise; should return empty list.
        closed = watcher.auto_close_for_issue("orig-y")
        assert closed == []

    def test_dedup_path_records_issue_id_when_first_lacked_one(self):
        """If a task was first filed without issue context, a later
        same-fingerprint hit *with* issue context still hooks the link
        up so a future success can auto-close."""
        watcher, tracker = self._make_watcher()
        # First report has no issue_id (e.g. came from a non-worker
        # logger.error in the same process).
        watcher.report_error("backend:x", "errno 57")
        rec_first = next(iter(watcher._seen.values()))
        assert rec_first.issue_id is None
        # Second report: same fingerprint, dedup'd, but supplies the
        # issue_id this time.
        watcher.report_error("backend:x", "errno 57", issue_id="issue-Z")
        rec_after = next(iter(watcher._seen.values()))
        assert rec_after.issue_id == "issue-Z"
        # Only one create_issue call — second was deduplicated.
        assert tracker.create_issue.call_count == 1

    def test_logger_handler_passes_issue_id_via_extra(self):
        """The Python logging handler propagates issue_id from
        ``extra={"issue_id": ...}`` into the watcher record."""
        watcher, tracker = self._make_watcher()
        watcher.install_log_handler("oompah.test_handler_issue_id")
        try:
            test_logger = logging.getLogger("oompah.test_handler_issue_id")
            test_logger.error(
                "Worker failed something transient",
                extra={"issue_id": "issue-from-extra"},
            )
            # The watcher should have created a record carrying the id.
            assert len(watcher._seen) == 1
            rec = next(iter(watcher._seen.values()))
            assert rec.issue_id == "issue-from-extra"
        finally:
            watcher.uninstall_log_handler("oompah.test_handler_issue_id")


# ---------------------------------------------------------------------------
# Tests for fingerprint normalization (issue oompah-zlz_2-ag7)
# ---------------------------------------------------------------------------


class TestFingerprintNormalization:
    """Verify the fingerprint dedupes operationally-identical errors.

    See oompah-zlz_2-ag7: a single Dolt slowdown produced 3 separate tasks
    because the fingerprint hashed the full message. These tests pin the
    new normalization rules.
    """

    def _make_watcher(self):
        tracker = MagicMock()
        issue = MagicMock()
        issue.identifier = "test-001"
        tracker.create_issue.return_value = issue
        return ErrorWatcher(tracker), tracker

    def _fp(self, watcher, message, source="backend:orchestrator", **kw):
        return watcher._fingerprint(source, message, **kw)

    # --- regression: identical messages still collapse ---

    def test_identical_messages_same_fingerprint(self):
        w, _ = self._make_watcher()
        msg = "something boring failed"
        assert self._fp(w, msg) == self._fp(w, msg)

    def test_existing_normalization_preserved(self):
        """Existing hex-addr / UUID / timestamp / number normalization."""
        w, _ = self._make_watcher()
        a = "memory leak at 0xdeadbeef on 2024-01-01T12:00:00 task 1234567"
        b = "memory leak at 0xfeedface on 2024-12-31T23:59:59 task 9999999"
        assert self._fp(w, a) == self._fp(w, b)

    def test_varying_duration_values_collapse(self):
        """Repeated watchdog timing updates represent one incident."""
        w, _ = self._make_watcher()
        a = "Dispatch loop stale: no tick completed in 900s (threshold=900s)"
        b = "Dispatch loop stale: no tick completed in 1094s (threshold=900s)"
        assert self._fp(w, a, source="log:backend") == self._fp(
            w, b, source="log:backend"
        )

    def test_uuid_normalization(self):
        w, _ = self._make_watcher()
        a = "session 11111111-2222-3333-4444-555555555555 dropped"
        b = "session aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee dropped"
        assert self._fp(w, a) == self._fp(w, b)

    # --- new: project name normalization ---

    def test_project_name_collapses(self):
        w, _ = self._make_watcher()
        a = "Fetch failed for project oompah: tracker command failed (exit 1): boom"
        b = "Fetch failed for project trickle: tracker command failed (exit 1): boom"
        assert self._fp(w, a) == self._fp(w, b)

    # --- command argument handling ---

    def test_tracker_subcommand_args_stay_distinct_without_error_class(self):
        """Different tracker command args remain distinct without an explicit class."""
        w, _ = self._make_watcher()
        a = (
            "Fetch failed for project oompah: tracker command timed out: "
            "oompah task list --project proj"
        )
        b = (
            "Fetch failed for project oompah: tracker command timed out: "
            "oompah task set-status TASK-16 Done --project proj"
        )
        c = (
            "Fetch failed for project oompah: tracker command timed out: "
            "oompah task view TASK-7 --project proj"
        )
        assert self._fp(w, a) != self._fp(w, b)
        assert self._fp(w, b) != self._fp(w, c)

    def test_same_tracker_command_collapses_across_projects(self):
        """Project name normalization still collapses otherwise-identical failures."""
        w, _ = self._make_watcher()
        a = (
            "Fetch failed for project oompah: tracker command timed out: "
            "oompah task list --project proj"
        )
        b = (
            "Fetch failed for project trickle: tracker command timed out: "
            "oompah task list --project proj"
        )
        assert self._fp(w, a) == self._fp(w, b)

    # --- new: identifier normalization ---

    def test_quoted_identifier_normalization(self):
        w, _ = self._make_watcher()
        a = 'failed to dispatch "oompah-zlz_2-16h"'
        b = 'failed to dispatch "oompah-zlz_2-aup"'
        assert self._fp(w, a) == self._fp(w, b)

    def test_bare_identifier_normalization(self):
        w, _ = self._make_watcher()
        a = "could not load oompah-zlz_2-16h from store"
        b = "could not load oompah-zlz_2-aup from store"
        assert self._fp(w, a) == self._fp(w, b)

    def test_identifier_does_not_eat_english(self):
        """2+ dash segments required — ordinary hyphenated words preserved."""
        w, _ = self._make_watcher()
        # These messages are operationally distinct; their fingerprints
        # should NOT collapse just because they contain hyphens.
        a = "non-empty input required for use-case foo"
        b = "non-empty input required for use-case bar"
        assert self._fp(w, a) != self._fp(w, b)

    # --- new: explicit error_class collapses everything ---

    def test_error_class_collapses_disparate_messages(self):
        """Same root cause, completely different message templates → one fp."""
        w, _ = self._make_watcher()
        a = "Fetch failed for project oompah: tracker command timed out: tracker list --json"
        b = "Failed to fetch candidates: tracker command timed out: tracker list --json"
        c = "Some entirely unrelated phrasing of a timeout"
        assert (
            self._fp(w, a, error_class="tracker_timeout")
            == self._fp(w, b, error_class="tracker_timeout")
            == self._fp(w, c, error_class="tracker_timeout")
        )

    def test_error_class_distinct_from_other_classes(self):
        w, _ = self._make_watcher()
        a = self._fp(w, "anything", error_class="tracker_timeout")
        b = self._fp(w, "anything", error_class="tracker_failed")
        assert a != b

    def test_error_class_distinct_from_freeform(self):
        """An error_class fingerprint must not accidentally collide with the
        free-form fingerprint of the same message."""
        w, _ = self._make_watcher()
        msg = "something"
        assert self._fp(w, msg) != self._fp(w, msg, error_class="tracker_timeout")

    def test_error_class_ignores_source(self):
        """Different sources, same error_class → still collapse to one task."""
        w, _ = self._make_watcher()
        a = self._fp(w, "x", source="backend:tracker", error_class="tracker_failed")
        b = self._fp(w, "x", source="backend:orchestrator", error_class="tracker_failed")
        assert a == b

    # --- regression: free-form path still distinguishes truly different errors ---

    def test_freeform_distinguishes_different_errors(self):
        w, _ = self._make_watcher()
        a = "disk full"
        b = "permission denied"
        assert self._fp(w, a) != self._fp(w, b)


class TestReportErrorWithErrorClass:
    """End-to-end: report_error with error_class collapses to one task."""

    def _make_watcher(self):
        tracker = MagicMock()
        issue = MagicMock()
        issue.identifier = "test-001"
        tracker.create_issue.return_value = issue
        return ErrorWatcher(tracker), tracker

    def test_three_messages_one_task_with_error_class(self):
        """Reproduces the oompah-zlz_2-ag7 scenario: 3 messages → 1 task."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            "backend:orchestrator",
            "Fetch failed for project oompah: tracker command timed out: oompah task list --project proj",
            error_class="tracker_timeout",
        )
        watcher.report_error(
            "backend:orchestrator",
            "Fetch failed for project trickle: tracker command timed out: oompah task list --project proj",
            error_class="tracker_timeout",
        )
        watcher.report_error(
            "backend:tracker",
            "Failed to fetch candidates: tracker command timed out: oompah task list --project proj",
            error_class="tracker_timeout",
        )
        assert tracker.create_issue.call_count == 1

    def test_no_error_class_falls_back_to_freeform(self):
        """Without error_class, free-form normalization still applies."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            "backend:orchestrator",
            "Fetch failed for project oompah: tracker command failed (exit 1): oompah task list --project proj",
        )
        watcher.report_error(
            "backend:orchestrator",
            "Fetch failed for project trickle: tracker command failed (exit 1): oompah task list --project proj",
        )
        # Same source, same template after normalization → collapsed.
        assert tracker.create_issue.call_count == 1

    def test_no_error_class_keeps_distinct_errors_distinct(self):
        """Regression: different operational errors → different tasks."""
        watcher, tracker = self._make_watcher()
        watcher.report_error("backend:disk", "disk full")
        watcher.report_error("backend:net", "permission denied")
        assert tracker.create_issue.call_count == 2

    def test_description_includes_error_class_and_message(self):
        """Operator must still see the original message + class for diagnosis."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            "backend:orchestrator",
            "Fetch failed for project oompah: tracker command timed out: oompah task list --project proj",
            error_class="tracker_timeout",
        )
        call_kwargs = tracker.create_issue.call_args
        description = call_kwargs.kwargs.get("description", "")
        # error_class appears in the structured metadata footer
        assert "error_class: tracker_timeout" in description
        assert "oompah task list --project proj" in description


class TestTaskLoggingHandlerErrorClass:
    """Logging handler must propagate ``extra={'error_class': ...}``."""

    def test_handler_passes_error_class_from_extra(self):
        from oompah.error_watcher import _TaskLoggingHandler
        watcher = MagicMock()
        handler = _TaskLoggingHandler(watcher)

        # Build a LogRecord with error_class set via the standard "extra"
        # logging mechanism (Python adds the dict as record attributes).
        record = logging.LogRecord(
            name="oompah.tracker",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="tracker command failed (exit 1): boom",
            args=(),
            exc_info=None,
        )
        record.error_class = "tracker_failed"
        record.module = "tracker"

        handler.emit(record)

        watcher.report_error.assert_called_once()
        kwargs = watcher.report_error.call_args.kwargs
        assert kwargs["error_class"] == "tracker_failed"
        assert kwargs["source"] == "backend:tracker"

    def test_handler_default_error_class_is_none(self):
        from oompah.error_watcher import _TaskLoggingHandler
        watcher = MagicMock()
        handler = _TaskLoggingHandler(watcher)

        record = logging.LogRecord(
            name="oompah.foo",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="some error",
            args=(),
            exc_info=None,
        )
        record.module = "foo"
        # No error_class set on record.

        handler.emit(record)

        kwargs = watcher.report_error.call_args.kwargs
        assert kwargs["error_class"] is None


class TestErrorClassForTrackerExc:
    """Helper that maps tracker/project exceptions to error_class names."""

    def test_tracker_timeout(self):
        from oompah.orchestrator import _error_class_for_tracker_exc
        from oompah.tracker import TrackerTimeoutError
        assert (
            _error_class_for_tracker_exc(TrackerTimeoutError("x"))
            == "tracker_timeout"
        )

    def test_tracker_not_configured(self):
        from oompah.orchestrator import _error_class_for_tracker_exc
        from oompah.tracker import TrackerNotConfiguredError
        assert (
            _error_class_for_tracker_exc(TrackerNotConfiguredError("x"))
            == "tracker_not_configured"
        )

    def test_generic_tracker_error(self):
        from oompah.orchestrator import _error_class_for_tracker_exc
        from oompah.tracker import TrackerError
        assert _error_class_for_tracker_exc(TrackerError("x")) == "tracker_failed"

    def test_project_error_fallback(self):
        from oompah.orchestrator import _error_class_for_tracker_exc
        from oompah.projects import ProjectError
        assert _error_class_for_tracker_exc(ProjectError("x")) == "project_error"

    def test_tracker_state_branch_missing_error(self):
        from oompah.orchestrator import _error_class_for_tracker_exc
        from oompah.tracker import TrackerStateBranchMissingError
        assert (
            _error_class_for_tracker_exc(TrackerStateBranchMissingError("missing"))
            == "tracker_state_branch_missing"
        )

    def test_tracker_state_branch_fetch_error(self):
        """StateBranchFetchError must map to 'tracker_state_branch_fetch' class.

        This ensures error_watcher dedup treats all fetch failures as one class,
        not as generic 'tracker_failed'. (OOMPAH-345)
        """
        from oompah.orchestrator import _error_class_for_tracker_exc
        from oompah.tracker import TrackerStateBranchFetchError
        assert (
            _error_class_for_tracker_exc(TrackerStateBranchFetchError("fetch failed"))
            == "tracker_state_branch_fetch"
        )

    def test_tracker_state_branch_fetch_error_is_tracker_error_subclass(self):
        """StateBranchFetchError must be a TrackerError subclass for back-compat."""
        from oompah.tracker import StateBranchFetchError, TrackerError
        assert issubclass(StateBranchFetchError, TrackerError)

    def test_tracker_state_branch_fetch_error_alias(self):
        """TrackerStateBranchFetchError alias must resolve to StateBranchFetchError."""
        from oompah.tracker import StateBranchFetchError, TrackerStateBranchFetchError
        assert TrackerStateBranchFetchError is StateBranchFetchError


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
# Tests for tracker identity and auto-filed task metadata (TASK-461.6)
# ---------------------------------------------------------------------------


class TestTrackerLabel:
    """Tests for ErrorWatcher._tracker_label() tracker identity extraction."""

    def _make_watcher(self, tracker, project_id=None):
        return ErrorWatcher(tracker, project_id=project_id)

    def test_native_tracker_label(self):
        """Unrecognised native trackers use their class name."""
        class NativeTracker:
            pass

        tracker = NativeTracker()
        watcher = self._make_watcher(tracker)
        assert watcher._tracker_label() == "nativetracker"

    def test_github_tracker_label(self):
        """Trackers with owner/repo attributes are labelled as github_issues."""
        tracker = MagicMock()
        tracker.owner = "acme-org"
        tracker.repo = "task-hub"
        watcher = self._make_watcher(tracker)
        assert watcher._tracker_label() == "github_issues:acme-org/task-hub"

    def test_unknown_tracker_falls_back_to_class_name(self):
        """Unrecognised trackers fall back to the lower-cased class name."""
        class MyCustomTracker:
            pass
        tracker = MyCustomTracker()
        watcher = self._make_watcher(tracker)
        assert watcher._tracker_label() == "mycustomtracker"

    def test_tracker_with_only_owner_no_repo_falls_back(self):
        """A tracker with only owner (no repo) is not identified as GitHub."""
        tracker = MagicMock()
        tracker.owner = "acme-org"
        del tracker.repo  # ensure getattr returns None-like absence
        tracker.configure_mock(**{"repo": None})
        watcher = self._make_watcher(tracker)
        # Should NOT return github_issues:... because repo is None
        label = watcher._tracker_label()
        assert not label.startswith("github_issues:")


class TestAutoFiledTaskMetadata:
    """Auto-filed error tasks include tracker identity, source project, fingerprint."""

    def _make_watcher(self, project_id=None, owner=None, repo=None):
        issue = MagicMock()
        issue.identifier = "task-001"
        if owner and repo:
            tracker = MagicMock()
            tracker.create_issue.return_value = issue
            tracker.owner = owner
            tracker.repo = repo
        else:
            class NativeTracker:
                pass

            tracker = NativeTracker()
            tracker.create_issue = MagicMock(return_value=issue)
        watcher = ErrorWatcher(tracker, project_id=project_id)
        return watcher, tracker

    def _get_description(self, tracker):
        """Extract the description kwarg from the last create_issue call."""
        call_kwargs = tracker.create_issue.call_args
        return call_kwargs.kwargs.get("description", "") or str(call_kwargs)

    def test_description_includes_source_project(self):
        """Error task description includes source_project from watcher's project_id."""
        watcher, tracker = self._make_watcher(project_id="proj-abc")
        watcher.report_error("test", "something broke")
        desc = self._get_description(tracker)
        assert "source_project: proj-abc" in desc

    def test_description_global_when_no_project_id(self):
        """When project_id is None, description shows 'global'."""
        watcher, tracker = self._make_watcher(project_id=None)
        watcher.report_error("test", "something broke")
        desc = self._get_description(tracker)
        assert "source_project: global" in desc

    def test_description_includes_tracker_label_native(self):
        """Error task description includes native tracker label."""
        watcher, tracker = self._make_watcher()
        watcher.report_error("test", "something broke")
        desc = self._get_description(tracker)
        assert "tracker: nativetracker" in desc
        assert "tracker_kind: nativetracker" in desc

    def test_description_includes_tracker_label_github(self):
        """Error task description includes github_issues tracker label with hub."""
        watcher, tracker = self._make_watcher(
            project_id="proj-gh", owner="my-org", repo="tasks"
        )
        watcher.report_error("test", "something broke")
        desc = self._get_description(tracker)
        assert "tracker: github_issues:my-org/tasks" in desc
        assert "tracker_kind: github_issues" in desc
        assert "tracker_owner: my-org" in desc
        assert "tracker_repo: tasks" in desc

    def test_description_includes_fingerprint(self):
        """Error task description includes the dedup fingerprint."""
        watcher, tracker = self._make_watcher(project_id="proj-fp")
        watcher.report_error("test", "fingerprint test error")
        desc = self._get_description(tracker)
        assert "fingerprint: " in desc
        assert "dedup_fingerprint: " in desc
        # Fingerprint is a 16-char hex string
        import re
        assert re.search(r"fingerprint: [0-9a-f]{16}", desc)
        assert re.search(r"dedup_fingerprint: [0-9a-f]{16}", desc)

    def test_description_includes_source_issue_when_given(self):
        """Error task description includes source_issue when available."""
        watcher, tracker = self._make_watcher(project_id="proj-src")
        watcher.report_error("test", "issue scoped error", issue_id="repo#123")
        desc = self._get_description(tracker)
        assert "source_issue: repo#123" in desc

    def test_description_omits_source_issue_when_not_given(self):
        """Error task description omits source_issue when no issue id exists."""
        watcher, tracker = self._make_watcher(project_id="proj-src")
        watcher.report_error("test", "global error")
        desc = self._get_description(tracker)
        assert "source_issue:" not in desc

    def test_description_includes_error_class_when_given(self):
        """Error task description includes error_class when one is supplied."""
        watcher, tracker = self._make_watcher(project_id="proj-ec")
        watcher.report_error("test", "db timeout", error_class="bd_timeout")
        desc = self._get_description(tracker)
        assert "error_class: bd_timeout" in desc

    def test_description_omits_error_class_when_not_given(self):
        """Error task description omits error_class line when not supplied."""
        watcher, tracker = self._make_watcher(project_id="proj-ec")
        watcher.report_error("test", "no class error")
        desc = self._get_description(tracker)
        assert "error_class:" not in desc

    def test_metadata_footer_present(self):
        """Error task description ends with the standard oompah footer."""
        watcher, tracker = self._make_watcher(project_id="proj-meta")
        watcher.report_error("test", "meta test")
        desc = self._get_description(tracker)
        assert "*Auto-filed by oompah error_watcher*" in desc


class TestAutoCloseUsesTaskTracker:
    """AC #2: auto_close_for_issue routes comments to the task's own tracker backend.

    The error task and the source task may live in different tracker backends.
    ``auto_close_for_issue`` must always add comments / close issues via
    ``self._tracker`` - the tracker that CREATED the task - not via any
    external tracker reference.
    """

    def test_auto_close_comment_uses_task_tracker(self):
        """add_comment is called on the task's own tracker, not another one."""
        task_tracker = MagicMock()
        task_issue = MagicMock()
        task_issue.identifier = "task-auto-001"
        task_tracker.create_issue.return_value = task_issue

        source_tracker = MagicMock()  # a *different* tracker for the source task

        watcher = ErrorWatcher(task_tracker, project_id="proj-x")
        with patch("oompah.error_watcher.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            watcher.report_error("test", "auto-close test", issue_id="src-issue-1")

            # Advance time past the quiet window so auto-close is allowed.
            mock_time.return_value = 120.0
            closed = watcher.auto_close_for_issue(
                "src-issue-1", issue_identifier="src-001"
            )

        assert closed == ["task-auto-001"]
        # Comments must go to the task tracker, NOT to source_tracker.
        task_tracker.add_comment.assert_called_once()
        source_tracker.add_comment.assert_not_called()
        task_tracker.close_issue.assert_called_once()
        source_tracker.close_issue.assert_not_called()


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


# ---------------------------------------------------------------------------
# Regression tests: auto-generated tasks must pass validate_issue() (OOMPAH-15)
# ---------------------------------------------------------------------------


class TestAutoGeneratedTaskPassesIntakeValidation:
    """Auto-filed error tasks must pass the deterministic intake validator.

    Reproduces the OOMPAH-6 shape: error_watcher auto-files a bug for a
    GitHub API authentication failure on a GitHub-backed tracker and the
    resulting task description must satisfy validate_issue() with
    ready=True.

    No user-specific logins are hard-coded — only generic repo coords.
    """

    def _make_watcher(
        self,
        project_id: str = "proj-test",
        owner: str = "example-org",
        repo: str = "example-repo",
    ) -> tuple:
        tracker = MagicMock()
        issue = MagicMock()
        issue.identifier = "test-001"
        tracker.create_issue.return_value = issue
        tracker.owner = owner
        tracker.repo = repo
        watcher = ErrorWatcher(tracker, project_id=project_id)
        return watcher, tracker

    def _get_description(self, tracker) -> str:
        call_kwargs = tracker.create_issue.call_args
        return call_kwargs.kwargs.get("description", "") or str(call_kwargs)

    def _get_title(self, tracker) -> str:
        call_kwargs = tracker.create_issue.call_args
        return call_kwargs.kwargs.get("title", "") or str(call_kwargs)

    # --- OOMPAH-6 regression: tracker_failed error_class on GitHub tracker ---

    def test_oompah6_shape_passes_validate_issue(self):
        """Reproduce the OOMPAH-6 shape and assert validate_issue() returns ready=True."""
        from oompah.issue_validator import validate_issue

        watcher, tracker = self._make_watcher(project_id="global")
        message = (
            "Fetch failed for project example-repo: GitHub API authentication "
            "failed fetching page https://api.github.com/repos/example-org/"
            "example-repo/issues. Check OOMPAH_GITHUB_TOKEN or GitHub App credentials."
        )
        watcher.report_error(
            source="backend:github_tracker",
            message=message,
            error_class="tracker_failed",
        )

        title = self._get_title(tracker)
        description = self._get_description(tracker)
        result = validate_issue(title=title, description=description, issue_type="bug")

        assert result.ready is True, (
            f"validate_issue() returned ready=False for OOMPAH-6 shape. "
            f"Missing fields: {[f.field for f in result.missing_fields]}"
        )
        assert result.missing_fields == []

    def test_basic_backend_error_passes_validate_issue(self):
        """A generic backend error auto-filed as a bug passes validate_issue()."""
        from oompah.issue_validator import validate_issue

        watcher, tracker = self._make_watcher(project_id="proj-backend")
        watcher.report_error(
            source="backend:worker",
            message="Database connection pool exhausted",
            detail="ConnectionError: all 20 connections in use\n  at worker.py:42",
        )

        title = self._get_title(tracker)
        description = self._get_description(tracker)
        result = validate_issue(title=title, description=description, issue_type="bug")

        assert result.ready is True, (
            f"Missing fields: {[f.field for f in result.missing_fields]}"
        )

    def test_log_file_watcher_error_passes_validate_issue(self):
        """An error sourced from a log file watcher passes validate_issue()."""
        from oompah.issue_validator import validate_issue

        watcher, tracker = self._make_watcher(project_id="proj-log")
        watcher.report_error(
            source="log:my-service",
            message="Connection refused to upstream API",
        )

        title = self._get_title(tracker)
        description = self._get_description(tracker)
        result = validate_issue(title=title, description=description, issue_type="bug")

        assert result.ready is True, (
            f"Missing fields: {[f.field for f in result.missing_fields]}"
        )

    def test_description_contains_required_sections(self):
        """The generated description contains all five required intake sections."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            source="backend:test_module",
            message="Something went wrong",
        )
        description = self._get_description(tracker)

        assert "## Problem" in description
        assert "## Steps to Reproduce" in description
        assert "## Actual Behavior" in description
        assert "## Expected Behavior" in description
        assert "## Acceptance Criteria" in description

    def test_description_sections_have_non_trivial_content(self):
        """Each required section body is non-empty and not TBD/N/A."""
        from oompah.issue_validator import _section_nonempty

        watcher, tracker = self._make_watcher()
        watcher.report_error(
            source="backend:test_module",
            message="Something went wrong with the operation",
        )
        description = self._get_description(tracker)

        assert _section_nonempty(description, "problem_statement"), (
            "problem_statement section must be non-trivial"
        )
        assert _section_nonempty(description, "repro_steps"), (
            "repro_steps section must be non-trivial"
        )
        assert _section_nonempty(description, "actual_behavior"), (
            "actual_behavior section must be non-trivial"
        )
        assert _section_nonempty(description, "desired_behavior"), (
            "desired_behavior (expected behavior) section must be non-trivial"
        )
        assert _section_nonempty(description, "acceptance_criteria"), (
            "acceptance_criteria section must be non-trivial"
        )

    def test_structured_description_still_includes_diagnostic_metadata(self):
        """Structured descriptions preserve all diagnostic metadata fields."""
        watcher, tracker = self._make_watcher(
            project_id="proj-meta", owner="my-org", repo="my-repo"
        )
        watcher.report_error(
            source="backend:test",
            message="test error",
            issue_id="src-issue-42",
            error_class="connection_refused",
        )
        description = self._get_description(tracker)

        assert "source_project: proj-meta" in description
        assert "tracker: github_issues:my-org/my-repo" in description
        assert "tracker_kind: github_issues" in description
        assert "tracker_owner: my-org" in description
        assert "tracker_repo: my-repo" in description
        assert "source_issue: src-issue-42" in description
        assert "error_class: connection_refused" in description
        assert "*Auto-filed by oompah error_watcher*" in description
        import re
        assert re.search(r"fingerprint: [0-9a-f]{16}", description)
        assert re.search(r"dedup_fingerprint: [0-9a-f]{16}", description)

    def test_error_with_detail_still_passes_validate_issue(self):
        """Errors with long stack-trace detail still pass intake validation."""
        from oompah.issue_validator import validate_issue

        watcher, tracker = self._make_watcher(project_id="proj-detail")
        detail = (
            "Traceback (most recent call last):\n"
            "  File 'worker.py', line 42, in run\n"
            "    result = fetch_issues(project)\n"
            "  File 'github_tracker.py', line 100, in fetch_issues\n"
            "    raise AuthError('token expired')\n"
            "AuthError: token expired\n"
        )
        watcher.report_error(
            source="backend:github_tracker",
            message="GitHub API authentication failed",
            detail=detail,
        )

        title = self._get_title(tracker)
        description = self._get_description(tracker)
        result = validate_issue(title=title, description=description, issue_type="bug")

        assert result.ready is True, (
            f"Missing fields: {[f.field for f in result.missing_fields]}"
        )

    def test_error_class_only_error_passes_validate_issue(self):
        """Error-class-collapsed reports (no unique message) pass intake validation."""
        from oompah.issue_validator import validate_issue

        watcher, tracker = self._make_watcher(project_id="proj-class")
        watcher.report_error(
            source="backend:poller",
            message="Fetch failed for project my-proj: rate limit exceeded",
            error_class="rate_limit_exceeded",
        )

        title = self._get_title(tracker)
        description = self._get_description(tracker)
        result = validate_issue(title=title, description=description, issue_type="bug")

        assert result.ready is True, (
            f"Missing fields: {[f.field for f in result.missing_fields]}"
        )
