"""Tests for oompah.error_watcher."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
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
from oompah.tracker import BacklogMdTracker


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


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


def _init_git_backlog_repo(
    tmp_path: Path,
    *,
    with_remote: bool,
) -> tuple[Path, Path | None]:
    repo = tmp_path / "repo"
    repo.mkdir()
    origin = tmp_path / "origin.git" if with_remote else None
    if origin is not None:
        _git(["init", "--bare", str(origin)])
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.name", "Tester"], cwd=repo)
    _git(["config", "user.email", "tester@example.com"], cwd=repo)

    backlog_dir = repo / "backlog"
    (backlog_dir / "tasks").mkdir(parents=True)
    (backlog_dir / "config.yml").write_text(
        "project_name: test\n"
        "statuses: [Backlog, Open, In Progress, Done]\n"
        "labels: []\n"
        "task_prefix: task\n"
        "default_status: Backlog\n",
        encoding="utf-8",
    )
    _git(["add", "backlog/config.yml"], cwd=repo)
    _git(["commit", "-m", "Initial backlog config"], cwd=repo)
    if origin is not None:
        _git(["remote", "add", "origin", str(origin)], cwd=repo)
        _git(["push", "-u", "origin", "main"], cwd=repo)
    return repo, origin


def _write_error_task(repo: Path, identifier: str, title: str) -> Path:
    task_number = identifier.split("-", 1)[-1].lower()
    path = repo / "backlog" / "tasks" / f"task-{task_number} - ErrorWatcher-test.md"
    path.write_text(
        f"""---
id: {identifier}
title: {title}
status: Backlog
assignee: []
created_date: '2026-06-03 04:35'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 1
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
{title}
<!-- SECTION:DESCRIPTION:END -->
""",
        encoding="utf-8",
    )
    return path


class TestErrorWatcherGitPersistence:
    def test_report_error_commits_and_pushes_only_created_task(self, tmp_path):
        repo, origin = _init_git_backlog_repo(tmp_path, with_remote=True)
        assert origin is not None
        tracker = BacklogMdTracker(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(repo),
        )
        task_path: Path | None = None

        def create_issue(**_kwargs):
            nonlocal task_path
            task_path = _write_error_task(repo, "TASK-900", "ErrorWatcher test")
            return SimpleNamespace(identifier="TASK-900")

        tracker.create_issue = create_issue
        (repo / "notes.txt").write_text("unrelated local work\n", encoding="utf-8")
        (repo / "staged.txt").write_text("pre-staged user work\n", encoding="utf-8")
        _git(["add", "staged.txt"], cwd=repo)

        result = ErrorWatcher(tracker).report_error("frontend", "boom")

        assert result == "TASK-900"
        assert task_path is not None
        rel_path = task_path.relative_to(repo).as_posix()
        remote_show = subprocess.run(
            ["git", "--git-dir", str(origin), "show", f"main:{rel_path}"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "TASK-900" in remote_show.stdout

        status_lines = _git(["status", "--short"], cwd=repo).stdout.splitlines()
        assert "?? notes.txt" in status_lines
        assert "A  staged.txt" in status_lines
        assert not any("TASK-900" in line or "task-900" in line for line in status_lines)

        message = _git(["log", "-1", "--pretty=%B"], cwd=repo).stdout
        assert "Record ErrorWatcher task TASK-900" in message
        assert "Generated with https://github.com/lesserevil/oompah" in message
        assert "Co-authored-by: oompah <lesserevil@users.noreply.github.com>" in message

    def test_report_error_returns_identifier_when_push_fails(self, tmp_path, caplog):
        repo, _origin = _init_git_backlog_repo(tmp_path, with_remote=False)
        tracker = BacklogMdTracker(
            active_states=["Open"],
            terminal_states=["Done"],
            cwd=str(repo),
        )

        def create_issue(**_kwargs):
            _write_error_task(repo, "TASK-901", "Push failure still returns")
            return SimpleNamespace(identifier="TASK-901")

        tracker.create_issue = create_issue
        caplog.set_level(logging.WARNING)

        result = ErrorWatcher(tracker).report_error("frontend", "push failed")

        assert result == "TASK-901"
        assert "git push failed after local commit" in caplog.text


# ---------------------------------------------------------------------------
# Tests for issue-aware error tracking + retry-success auto-close
# (oompah-zlz_2-0nc)
# ---------------------------------------------------------------------------


class TestErrorWatcherAutoClose:
    """Verify ErrorWatcher.report_error/auto_close_for_issue behavior."""

    def _make_watcher(self, bead_id: str = "oompah-test-001"):
        tracker = MagicMock()
        issue = MagicMock()
        issue.identifier = bead_id
        tracker.create_issue.return_value = issue
        watcher = ErrorWatcher(tracker)
        return watcher, tracker

    def test_report_error_with_issue_id_records_link(self):
        watcher, tracker = self._make_watcher()
        bead = watcher.report_error(
            "backend:worker",
            "transient errno 57",
            issue_id="orig-issue-123",
        )
        assert bead == "oompah-test-001"
        # Find the seen record and verify the link.
        records = list(watcher._seen.values())
        assert len(records) == 1
        rec = records[0]
        assert rec.issue_id == "orig-issue-123"
        assert rec.bead_id == "oompah-test-001"

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
        watcher, tracker = self._make_watcher(bead_id="oompah-test-001")
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
        # Record popped so a future error will create a fresh bead.
        assert not watcher._seen

    def test_auto_close_only_targets_matching_issue(self):
        """Only beads tied to the matching issue_id get closed."""
        watcher, tracker = self._make_watcher()
        # Two different beads, two different issues.
        bead_a = MagicMock(); bead_a.identifier = "oompah-bead-A"
        bead_b = MagicMock(); bead_b.identifier = "oompah-bead-B"
        tracker.create_issue.side_effect = [bead_a, bead_b]
        watcher.report_error("backend:a", "first error", issue_id="issue-A")
        watcher.report_error("backend:b", "second error", issue_id="issue-B")
        # Move both records out of the quiet window
        for rec in watcher._seen.values():
            rec.last_created -= 120
        closed = watcher.auto_close_for_issue("issue-A")
        assert closed == ["oompah-bead-A"]
        # Only A was closed; B remains in _seen
        remaining_beads = {r.bead_id for r in watcher._seen.values()}
        assert remaining_beads == {"oompah-bead-B"}

    def test_no_recovery_keeps_bead_deferred(self):
        """fingerprint+issue_id, no recovery → stays deferred."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            "backend:worker",
            "permanent failure",
            issue_id="orig-issue-456",
        )
        # auto_close is only called on retry success; never invoking it
        # should leave the bead untouched.
        tracker.close_issue.assert_not_called()
        assert len(watcher._seen) == 1
        assert next(iter(watcher._seen.values())).bead_id is not None

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

    def test_auto_close_skipped_when_bead_too_old(self):
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
        bead_a = MagicMock(); bead_a.identifier = "oompah-bead-A"
        bead_b = MagicMock(); bead_b.identifier = "oompah-bead-B"
        bead_c = MagicMock(); bead_c.identifier = "oompah-bead-C"
        tracker.create_issue.side_effect = [bead_a, bead_b, bead_c]
        # All three errors during the same issue's retry chain.
        watcher.report_error("backend:net", "errno 57", issue_id="issue-X")
        watcher.report_error("backend:net", "timeout", issue_id="issue-X")
        watcher.report_error("backend:db", "deadlock", issue_id="issue-X")
        for rec in watcher._seen.values():
            rec.last_created -= 120
        closed = watcher.auto_close_for_issue("issue-X")
        assert sorted(closed) == ["oompah-bead-A", "oompah-bead-B", "oompah-bead-C"]
        assert tracker.close_issue.call_count == 3
        assert not watcher._seen

    def test_auto_close_swallows_close_failures(self):
        """tracker errors during auto-close shouldn't propagate."""
        watcher, tracker = self._make_watcher()
        watcher.report_error("backend:x", "boom", issue_id="orig-y")
        for rec in watcher._seen.values():
            rec.last_created -= 120
        tracker.close_issue.side_effect = Exception("bd unreachable")
        # Should not raise; should return empty list.
        closed = watcher.auto_close_for_issue("orig-y")
        assert closed == []

    def test_dedup_path_records_issue_id_when_first_lacked_one(self):
        """If a bead was first filed without issue context, a later
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

    See oompah-zlz_2-ag7: a single Dolt slowdown produced 3 separate beads
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

    def test_uuid_normalization(self):
        w, _ = self._make_watcher()
        a = "session 11111111-2222-3333-4444-555555555555 dropped"
        b = "session aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee dropped"
        assert self._fp(w, a) == self._fp(w, b)

    # --- new: project name normalization ---

    def test_project_name_collapses(self):
        w, _ = self._make_watcher()
        a = "Fetch failed for project oompah: backlog command failed (exit 1): boom"
        b = "Fetch failed for project trickle: backlog command failed (exit 1): boom"
        assert self._fp(w, a) == self._fp(w, b)

    # --- new: Backlog command args stripped ---

    def test_backlog_subcommand_args_stripped(self):
        """Different Backlog command args must collapse to one fingerprint."""
        w, _ = self._make_watcher()
        a = (
            "Fetch failed for project oompah: backlog command timed out: "
            "backlog task list --plain"
        )
        b = (
            "Fetch failed for project oompah: backlog command timed out: "
            "backlog task edit TASK-16 --status Done --plain"
        )
        c = (
            "Fetch failed for project oompah: backlog command timed out: "
            "backlog task view TASK-7 --plain"
        )
        assert self._fp(w, a) == self._fp(w, b)
        assert self._fp(w, b) == self._fp(w, c)

    def test_backlog_subcommand_args_stripped_across_projects(self):
        """Combination: project name + Backlog args stripped -> all collapse."""
        w, _ = self._make_watcher()
        a = (
            "Fetch failed for project oompah: backlog command timed out: "
            "backlog task list --plain"
        )
        b = (
            "Fetch failed for project trickle: backlog command timed out: "
            "backlog task edit TASK-42 --status Done --plain"
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
        a = "Fetch failed for project oompah: bd command timed out: bd list --json"
        b = "Failed to fetch candidates: bd command timed out: bd list --json"
        c = "Some entirely unrelated phrasing of a timeout"
        assert (
            self._fp(w, a, error_class="bd_timeout")
            == self._fp(w, b, error_class="bd_timeout")
            == self._fp(w, c, error_class="bd_timeout")
        )

    def test_error_class_distinct_from_other_classes(self):
        w, _ = self._make_watcher()
        a = self._fp(w, "anything", error_class="bd_timeout")
        b = self._fp(w, "anything", error_class="bd_failed")
        assert a != b

    def test_error_class_distinct_from_freeform(self):
        """An error_class fingerprint must not accidentally collide with the
        free-form fingerprint of the same message."""
        w, _ = self._make_watcher()
        msg = "something"
        assert self._fp(w, msg) != self._fp(w, msg, error_class="bd_timeout")

    def test_error_class_ignores_source(self):
        """Different sources, same error_class → still collapse to one bead."""
        w, _ = self._make_watcher()
        a = self._fp(w, "x", source="backend:tracker", error_class="bd_failed")
        b = self._fp(w, "x", source="backend:orchestrator", error_class="bd_failed")
        assert a == b

    # --- regression: free-form path still distinguishes truly different errors ---

    def test_freeform_distinguishes_different_errors(self):
        w, _ = self._make_watcher()
        a = "disk full"
        b = "permission denied"
        assert self._fp(w, a) != self._fp(w, b)


class TestReportErrorWithErrorClass:
    """End-to-end: report_error with error_class collapses to one bead."""

    def _make_watcher(self):
        tracker = MagicMock()
        issue = MagicMock()
        issue.identifier = "test-001"
        tracker.create_issue.return_value = issue
        return ErrorWatcher(tracker), tracker

    def test_three_messages_one_bead_with_error_class(self):
        """Reproduces the oompah-zlz_2-ag7 scenario: 3 messages → 1 bead."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            "backend:orchestrator",
            "Fetch failed for project oompah: backlog command timed out: backlog task list --plain",
            error_class="backlog_timeout",
        )
        watcher.report_error(
            "backend:orchestrator",
            "Fetch failed for project trickle: backlog command timed out: backlog task list --plain",
            error_class="backlog_timeout",
        )
        watcher.report_error(
            "backend:tracker",
            "Failed to fetch candidates: backlog command timed out: backlog task list --plain",
            error_class="backlog_timeout",
        )
        assert tracker.create_issue.call_count == 1

    def test_no_error_class_falls_back_to_freeform(self):
        """Without error_class, free-form normalization still applies — and
        the new project/Backlog-args normalization collapses these to one."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            "backend:orchestrator",
            "Fetch failed for project oompah: backlog command failed (exit 1): backlog task list --plain",
        )
        watcher.report_error(
            "backend:orchestrator",
            "Fetch failed for project trickle: backlog command failed (exit 1): backlog task edit TASK-16 --status Done --plain",
        )
        # Same source, same template after normalization → collapsed.
        assert tracker.create_issue.call_count == 1

    def test_no_error_class_keeps_distinct_errors_distinct(self):
        """Regression: different operational errors → different beads."""
        watcher, tracker = self._make_watcher()
        watcher.report_error("backend:disk", "disk full")
        watcher.report_error("backend:net", "permission denied")
        assert tracker.create_issue.call_count == 2

    def test_description_includes_error_class_and_message(self):
        """Operator must still see the original message + class for diagnosis."""
        watcher, tracker = self._make_watcher()
        watcher.report_error(
            "backend:orchestrator",
            "Fetch failed for project oompah: backlog command timed out: backlog task list --plain",
            error_class="backlog_timeout",
        )
        call_kwargs = tracker.create_issue.call_args
        description = call_kwargs.kwargs.get("description", "")
        assert "error_class=backlog_timeout" in description
        assert "backlog task list --plain" in description


class TestBeadLoggingHandlerErrorClass:
    """Logging handler must propagate ``extra={'error_class': ...}``."""

    def test_handler_passes_error_class_from_extra(self):
        from oompah.error_watcher import _BeadLoggingHandler
        watcher = MagicMock()
        handler = _BeadLoggingHandler(watcher)

        # Build a LogRecord with error_class set via the standard "extra"
        # logging mechanism (Python adds the dict as record attributes).
        record = logging.LogRecord(
            name="oompah.tracker",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="bd command failed (exit 1): boom",
            args=(),
            exc_info=None,
        )
        record.error_class = "bd_failed"
        record.module = "tracker"

        handler.emit(record)

        watcher.report_error.assert_called_once()
        kwargs = watcher.report_error.call_args.kwargs
        assert kwargs["error_class"] == "bd_failed"
        assert kwargs["source"] == "backend:tracker"

    def test_handler_default_error_class_is_none(self):
        from oompah.error_watcher import _BeadLoggingHandler
        watcher = MagicMock()
        handler = _BeadLoggingHandler(watcher)

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
