"""Tests for the Dolt sync watchdog (oompah-zlz_2-5ms2).

Covers:
* pull-only path (remote ahead, local clean)
* pull + push path (both ahead, normal case)
* nothing-to-do path (already in sync)
* divergent-history detection on pull
* divergent-history detection on push (fast-follow case)
* network/transient errors → backoff arms next_attempt_monotonic
* successful sync after error → backoff and error state cleared
* timeout handling (subprocess.TimeoutExpired)
* skip when .beads/ missing
* skip when in backoff window
* alerts summary: divergent and consecutive-errors thresholds
* get_or_create_state lazy init
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from oompah.dolt_sync import (
    DEFAULT_SUBPROCESS_TIMEOUT_S,
    ERROR_BACKOFF_MULTIPLIER,
    DoltSyncResult,
    DoltSyncState,
    get_or_create_state,
    summarize_for_alerts,
    sync_project_dolt,
    _is_divergent,
    _truncate,
)
from oompah.models import Project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(tmp_path, with_beads: bool = True, name: str = "test-proj",
                  pid: str = "proj-1") -> Project:
    """Build a Project with an optional .beads/ directory present."""
    repo_path = str(tmp_path)
    if with_beads:
        os.makedirs(os.path.join(repo_path, ".beads"), exist_ok=True)
    return Project(
        id=pid, name=name,
        repo_url="https://example.com/test.git",
        repo_path=repo_path, branch="main", paused=False,
    )


def _runner_factory(*responses):
    """Build a mock subprocess.run that returns canned CompletedProcess in order.

    Each response is either a tuple (returncode, stderr) or an Exception
    instance to raise.
    """
    iterator = iter(responses)

    def runner(*args, **kwargs):
        resp = next(iterator)
        if isinstance(resp, Exception):
            raise resp
        rc, stderr = resp
        return subprocess.CompletedProcess(
            args=args[0] if args else [],
            returncode=rc, stdout="", stderr=stderr,
        )
    return runner


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestIsDivergent:
    def test_diverged_in_stderr(self):
        assert _is_divergent("error: branches have diverged") is True

    def test_non_ff(self):
        assert _is_divergent("rejected: non-fast-forward update") is True

    def test_merge_conflict(self):
        assert _is_divergent("merge conflict in table issues") is True

    def test_unrelated_histories(self):
        assert _is_divergent("refusing to merge unrelated histories") is True

    def test_normal_error(self):
        assert _is_divergent("connection refused") is False

    def test_empty(self):
        assert _is_divergent("") is False
        assert _is_divergent(None) is False  # type: ignore[arg-type]

    def test_case_insensitive(self):
        assert _is_divergent("NON-FAST-FORWARD") is True


class TestTruncate:
    def test_short(self):
        assert _truncate("hello") == "hello"

    def test_long(self):
        out = _truncate("x" * 500, limit=200)
        assert out.endswith("...")
        assert len(out) == 203

    def test_strips_whitespace(self):
        assert _truncate("  hi  ") == "hi"


# ---------------------------------------------------------------------------
# sync_project_dolt — decision tree
# ---------------------------------------------------------------------------

class TestSyncProjectDolt:
    def test_default_timeout_is_forwarded_to_bd_commands(self, tmp_path):
        """The watchdog's default timeout must bound bd/dolt subprocesses."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        runner = MagicMock(side_effect=_runner_factory((0, ""), (0, "")))

        sync_project_dolt(
            project, state, full_sync_interval_s=120.0, runner=runner,
        )

        assert runner.mock_calls[0].kwargs["timeout"] == DEFAULT_SUBPROCESS_TIMEOUT_S
        assert runner.mock_calls[1].kwargs["timeout"] == DEFAULT_SUBPROCESS_TIMEOUT_S

    def test_pull_and_push_success(self, tmp_path):
        """Happy path: pull succeeds, push succeeds — both timestamps set."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        runner = _runner_factory((0, ""), (0, ""))

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0, runner=runner,
        )

        assert result.pulled is True
        assert result.pushed is True
        assert result.divergent is False
        assert result.error is None
        assert state.last_pull_at is not None
        assert state.last_push_at is not None
        assert state.last_error is None
        assert state.consecutive_errors == 0
        assert state.next_attempt_monotonic == 0.0

    def test_pull_diverged_blocks_push(self, tmp_path):
        """Diverged history on pull: push is skipped, divergent flag set."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        runner = _runner_factory((1, "fatal: branches have diverged"))

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0, runner=runner,
        )

        assert result.pulled is False
        assert result.pushed is False
        assert result.divergent is True
        assert state.divergent is True
        assert "diverged" in (state.last_error or "")
        assert state.consecutive_errors == 1

    def test_push_diverged_fast_follow(self, tmp_path):
        """Push fails with divergence between pull and push attempts."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        runner = _runner_factory(
            (0, ""),  # pull ok
            (1, "non-fast-forward update rejected"),  # push diverged
        )

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0, runner=runner,
        )

        assert result.pulled is True
        assert result.pushed is False
        assert result.divergent is True
        assert state.divergent is True
        assert "push diverged" in (state.last_error or "")

    def test_pull_network_error(self, tmp_path):
        """Generic pull error: error recorded, push skipped, backoff armed."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        runner = _runner_factory((1, "connection refused"))

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0,
            now_monotonic=1000.0, runner=runner,
        )

        assert result.pulled is False
        assert result.pushed is False
        assert result.divergent is False
        assert "pull failed" in (result.error or "")
        assert state.consecutive_errors == 1
        assert state.next_attempt_monotonic == 1000.0 + 120.0 * ERROR_BACKOFF_MULTIPLIER

    def test_push_network_error(self, tmp_path):
        """Pull succeeds, push fails with non-divergent error."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        runner = _runner_factory(
            (0, ""),
            (1, "remote rejected: rate limit exceeded"),
        )

        result = sync_project_dolt(
            project, state, full_sync_interval_s=60.0,
            now_monotonic=500.0, runner=runner,
        )

        assert result.pulled is True
        assert result.pushed is False
        assert "push failed" in (result.error or "")
        assert state.last_pull_at is not None
        assert state.last_push_at is None
        assert state.next_attempt_monotonic == 500.0 + 60.0 * ERROR_BACKOFF_MULTIPLIER

    def test_pull_timeout(self, tmp_path):
        """subprocess.TimeoutExpired during pull is caught and recorded."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        timeout_exc = subprocess.TimeoutExpired(cmd=["bd", "dolt", "pull"], timeout=15)
        runner = _runner_factory(timeout_exc)

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0,
            timeout_s=15.0, runner=runner,
        )

        assert result.pulled is False
        assert "timed out" in (result.error or "")
        assert state.consecutive_errors == 1

    def test_push_timeout(self, tmp_path):
        """subprocess.TimeoutExpired during push is caught and recorded."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        timeout_exc = subprocess.TimeoutExpired(cmd=["bd", "dolt", "push"], timeout=15)
        runner = _runner_factory((0, ""), timeout_exc)

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0,
            timeout_s=15.0, runner=runner,
        )

        assert result.pulled is True
        assert result.pushed is False
        assert "timed out" in (result.error or "")

    def test_pull_filenotfound(self, tmp_path):
        """FileNotFoundError (bd CLI missing) is caught."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        runner = _runner_factory(FileNotFoundError("bd not found"))

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0, runner=runner,
        )

        assert "pull failed" in (result.error or "")
        assert state.consecutive_errors == 1

    def test_skip_no_beads_dir(self, tmp_path):
        """Project without a .beads/ dir is skipped (not an error)."""
        project = _make_project(tmp_path, with_beads=False)
        state = DoltSyncState(project_id=project.id)
        runner = MagicMock()

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0, runner=runner,
        )

        assert result.skipped_reason == "no_beads_dir"
        assert result.pulled is False
        assert result.pushed is False
        runner.assert_not_called()

    def test_skip_in_backoff_window(self, tmp_path):
        """A project still in backoff is skipped this tick."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        # Backoff until t=2000; current time is t=1000.
        state.next_attempt_monotonic = 2000.0
        runner = MagicMock()

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0,
            now_monotonic=1000.0, runner=runner,
        )

        assert result.skipped_reason == "backoff"
        runner.assert_not_called()

    def test_recovery_clears_error_state(self, tmp_path):
        """After a successful sync, prior error/backoff state is wiped."""
        project = _make_project(tmp_path)
        state = DoltSyncState(
            project_id=project.id,
            last_error="previous: pull failed: foo",
            last_error_at=datetime.now(timezone.utc),
            consecutive_errors=2,
            next_attempt_monotonic=500.0,
        )
        # now_monotonic > next_attempt_monotonic so the sync runs.
        runner = _runner_factory((0, ""), (0, ""))

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0,
            now_monotonic=1000.0, runner=runner,
        )

        assert result.error is None
        assert state.last_error is None
        assert state.last_error_at is None
        assert state.consecutive_errors == 0
        assert state.next_attempt_monotonic == 0.0

    def test_pull_clears_divergent_flag(self, tmp_path):
        """A previously-divergent project clears divergent on a clean pull."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id, divergent=True)
        runner = _runner_factory((0, ""), (0, ""))

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0, runner=runner,
        )

        assert state.divergent is False
        assert result.divergent is False

    def test_returns_result_dict(self, tmp_path):
        """to_dict shape matches what /api/v1/orchestrator/dolt-sync expects."""
        project = _make_project(tmp_path)
        state = DoltSyncState(project_id=project.id)
        runner = _runner_factory((0, ""), (0, ""))

        result = sync_project_dolt(
            project, state, full_sync_interval_s=120.0, runner=runner,
        )
        d = result.to_dict()
        assert set(d.keys()) == {
            "project_id", "pulled", "pushed", "divergent",
            "error", "skipped_reason",
        }


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

class TestGetOrCreateState:
    def test_creates_on_first_access(self):
        states: dict[str, DoltSyncState] = {}
        st = get_or_create_state(states, "proj-a")
        assert st.project_id == "proj-a"
        assert "proj-a" in states

    def test_returns_existing(self):
        existing = DoltSyncState(project_id="proj-a", consecutive_errors=5)
        states = {"proj-a": existing}
        st = get_or_create_state(states, "proj-a")
        assert st is existing
        assert st.consecutive_errors == 5


class TestStateToDict:
    def test_serializes_datetimes(self):
        now = datetime(2026, 5, 12, 14, 30, tzinfo=timezone.utc)
        st = DoltSyncState(
            project_id="p", last_push_at=now, last_pull_at=now,
            last_error="boom", last_error_at=now,
            divergent=True, consecutive_errors=3,
        )
        d = st.to_dict()
        assert d["last_push_at"] == "2026-05-12T14:30:00+00:00"
        assert d["last_pull_at"] == "2026-05-12T14:30:00+00:00"
        assert d["divergent"] is True
        assert d["consecutive_errors"] == 3

    def test_none_dates(self):
        st = DoltSyncState(project_id="p")
        d = st.to_dict()
        assert d["last_push_at"] is None
        assert d["last_pull_at"] is None


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class TestSummarizeForAlerts:
    def test_divergent_project_emits_error_alert(self, tmp_path):
        project = _make_project(tmp_path, name="my-app")
        states = {project.id: DoltSyncState(project_id=project.id, divergent=True)}
        alerts = summarize_for_alerts(states, {project.id: project})
        assert len(alerts) == 1
        assert alerts[0]["level"] == "error"
        assert alerts[0]["source"] == "dolt_sync"
        assert "my-app" in alerts[0]["message"]
        assert "diverged" in alerts[0]["message"]

    def test_three_errors_threshold(self, tmp_path):
        project = _make_project(tmp_path, name="my-app")
        st = DoltSyncState(
            project_id=project.id,
            consecutive_errors=3,
            last_error="rate limit",
        )
        alerts = summarize_for_alerts({project.id: st}, {project.id: project})
        assert len(alerts) == 1
        assert alerts[0]["level"] == "warning"
        assert "3x" in alerts[0]["message"]

    def test_under_threshold_no_alert(self, tmp_path):
        project = _make_project(tmp_path)
        st = DoltSyncState(
            project_id=project.id,
            consecutive_errors=2,
            last_error="rate limit",
        )
        alerts = summarize_for_alerts({project.id: st}, {project.id: project})
        assert alerts == []

    def test_healthy_no_alert(self, tmp_path):
        project = _make_project(tmp_path)
        st = DoltSyncState(
            project_id=project.id,
            last_pull_at=datetime.now(timezone.utc),
            last_push_at=datetime.now(timezone.utc),
        )
        alerts = summarize_for_alerts({project.id: st}, {project.id: project})
        assert alerts == []

    def test_missing_project_falls_back_to_id(self, tmp_path):
        st = DoltSyncState(project_id="proj-unknown", divergent=True)
        alerts = summarize_for_alerts({"proj-unknown": st}, {})
        assert len(alerts) == 1
        assert "proj-unknown" in alerts[0]["message"]
