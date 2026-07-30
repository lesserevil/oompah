"""Tests for CLI actor reconciliation (OOMPAH-624).

These tests cover ``_reconcile_actor_with_session`` and its integration
with ``_cmd_set_status`` / ``_cmd_add_label``.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

import oompah.task_cli as task_cli
from oompah.client_auth import ClientCredentials


def _make_args(**kwargs) -> argparse.Namespace:
    """Return a minimal Namespace matching set-status/add-label expectations."""

    defaults = {
        "subcommand": "set-status",
        "identifier": "TASK-1",
        "status": "In Progress",
        "summary": None,
        "project": "proj-1",
        "actor": None,
        "audit_override": False,
        "override_reason": None,
        "label": "needs:security",
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


@contextmanager
def _session_credentials(username: str = "alice", password: str = "hunter2"):
    """Install a session ClientCredentials for the duration of the test."""

    prior = task_cli._session_auth
    task_cli._session_auth = ClientCredentials(username=username, password=password)
    try:
        yield
    finally:
        task_cli._session_auth = prior


@contextmanager
def _no_session():
    prior = task_cli._session_auth
    task_cli._session_auth = None
    try:
        yield
    finally:
        task_cli._session_auth = prior


class TestReconcileActorWithSession:
    def test_no_session_returns_actor_unchanged(self):
        with _no_session():
            assert task_cli._reconcile_actor_with_session("alice") == "alice"

    def test_none_actor_stays_none(self):
        with _session_credentials():
            assert task_cli._reconcile_actor_with_session(None) is None

    def test_actor_matching_session_returns_none_and_warns(self, capsys):
        with _session_credentials("alice"):
            result = task_cli._reconcile_actor_with_session("alice")
        assert result is None
        err = capsys.readouterr().err
        assert "redundant" in err.lower()
        assert "alice" in err

    def test_actor_case_insensitive_match_returns_none(self, capsys):
        with _session_credentials("alice"):
            result = task_cli._reconcile_actor_with_session("Alice")
        assert result is None

    def test_actor_conflict_exits_before_network_call(self, capsys):
        with _session_credentials("alice"):
            with pytest.raises(SystemExit) as excinfo:
                task_cli._reconcile_actor_with_session("mallory")
        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "conflict" in err.lower()
        assert "alice" in err
        assert "mallory" in err

    def test_silence_env_suppresses_warning(self, capsys, monkeypatch):
        monkeypatch.setenv("OOMPAH_ACTOR_DEPRECATION_SILENCE", "1")
        with _session_credentials("alice"):
            result = task_cli._reconcile_actor_with_session("alice")
        assert result is None
        err = capsys.readouterr().err
        assert err == ""


class TestSetStatusActorReconciliation:
    def _mock_http(self, response=None):
        """Return a MagicMock that stands in for _http and captures kwargs."""

        return MagicMock(return_value=response or {"ok": True, "status": "Open"})

    def test_matching_actor_omitted_from_request_body(self):
        args = _make_args(status="Open", actor="alice")
        with _session_credentials("alice"), patch.object(
            task_cli, "_task_handoff_request", return_value=None
        ), patch.object(task_cli, "_http", self._mock_http()) as http_mock:
            task_cli._cmd_set_status("http://localhost:8080", args)
        data = http_mock.call_args.kwargs.get("data", {})
        assert "actor_login" not in data

    def test_conflicting_actor_short_circuits(self):
        args = _make_args(status="Open", actor="mallory")
        with _session_credentials("alice"), patch.object(
            task_cli, "_task_handoff_request", return_value=None
        ), patch.object(task_cli, "_http", self._mock_http()) as http_mock:
            with pytest.raises(SystemExit) as excinfo:
                task_cli._cmd_set_status("http://localhost:8080", args)
        assert excinfo.value.code == 2
        # No network call was made.
        assert http_mock.call_count == 0

    def test_no_session_preserves_actor(self):
        args = _make_args(status="Open", actor="mallory")
        with _no_session(), patch.object(
            task_cli, "_task_handoff_request", return_value=None
        ), patch.object(task_cli, "_http", self._mock_http()) as http_mock:
            task_cli._cmd_set_status("http://localhost:8080", args)
        data = http_mock.call_args.kwargs.get("data", {})
        assert data.get("actor_login") == "mallory"


class TestAddLabelActorReconciliation:
    def _mock_http(self):
        return MagicMock(return_value={"ok": True})

    def test_matching_actor_omitted(self):
        args = _make_args(subcommand="add-label", label="oompah:status:open", actor="alice")
        with _session_credentials("alice"), patch.object(
            task_cli, "_task_handoff_request", return_value=None
        ), patch.object(task_cli, "_http", self._mock_http()) as http_mock:
            task_cli._cmd_add_label("http://localhost:8080", args)
        data = http_mock.call_args.kwargs.get("data", {})
        assert "actor_login" not in data

    def test_conflicting_actor_short_circuits(self):
        args = _make_args(subcommand="add-label", label="oompah:status:open", actor="mallory")
        with _session_credentials("alice"), patch.object(
            task_cli, "_http", self._mock_http()
        ) as http_mock:
            with pytest.raises(SystemExit) as excinfo:
                task_cli._cmd_add_label("http://localhost:8080", args)
        assert excinfo.value.code == 2
        assert http_mock.call_count == 0
