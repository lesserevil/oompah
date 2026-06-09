"""Unit tests for server-backend configuration helpers in oompah/__main__.py.

Covers:
  - _resolve_server_backend: CLI > env > default precedence
  - _resolve_workers: CLI > env > default precedence
  - _check_granian_workers_constraint: exits with error when granian + workers > 1
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from oompah.__main__ import (
    _check_granian_workers_constraint,
    _resolve_server_backend,
    _resolve_workers,
)


# ---------------------------------------------------------------------------
# _resolve_server_backend
# ---------------------------------------------------------------------------


class TestResolveServerBackend:
    def test_cli_value_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "granian")
        assert _resolve_server_backend("uvicorn") == "uvicorn"

    def test_cli_granian_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "uvicorn")
        assert _resolve_server_backend("granian") == "granian"

    def test_env_uvicorn_used_when_no_cli(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "uvicorn")
        assert _resolve_server_backend(None) == "uvicorn"

    def test_env_granian_used_when_no_cli(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "granian")
        assert _resolve_server_backend(None) == "granian"

    def test_env_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "GRANIAN")
        assert _resolve_server_backend(None) == "granian"

    def test_env_with_whitespace_stripped(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "  granian  ")
        assert _resolve_server_backend(None) == "granian"

    def test_invalid_env_falls_back_to_uvicorn(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "tornado")
        assert _resolve_server_backend(None) == "uvicorn"

    def test_empty_env_falls_back_to_uvicorn(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_BACKEND", raising=False)
        assert _resolve_server_backend(None) == "uvicorn"

    def test_default_is_uvicorn_with_no_cli_no_env(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_BACKEND", raising=False)
        result = _resolve_server_backend(None)
        assert result == "uvicorn"


# ---------------------------------------------------------------------------
# _resolve_workers
# ---------------------------------------------------------------------------


class TestResolveWorkers:
    def test_cli_value_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_WORKERS", "4")
        assert _resolve_workers(2) == 2

    def test_cli_one_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_WORKERS", "4")
        assert _resolve_workers(1) == 1

    def test_env_value_used_when_no_cli(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_WORKERS", "3")
        assert _resolve_workers(None) == 3

    def test_env_one_used_when_no_cli(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_WORKERS", "1")
        assert _resolve_workers(None) == 1

    def test_invalid_env_falls_back_to_one(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_WORKERS", "not-a-number")
        assert _resolve_workers(None) == 1

    def test_empty_env_falls_back_to_one(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_WORKERS", raising=False)
        assert _resolve_workers(None) == 1

    def test_default_is_one_with_no_cli_no_env(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_WORKERS", raising=False)
        assert _resolve_workers(None) == 1

    def test_env_zero_workers(self, monkeypatch):
        """Zero is a valid integer; callers may choose to reject it separately."""
        monkeypatch.setenv("OOMPAH_SERVER_WORKERS", "0")
        assert _resolve_workers(None) == 0


# ---------------------------------------------------------------------------
# _check_granian_workers_constraint
# ---------------------------------------------------------------------------


class TestCheckGranianWorkersConstraint:
    def test_uvicorn_with_multiple_workers_is_allowed(self):
        """uvicorn is not constrained to workers=1."""
        # Should not raise or exit
        _check_granian_workers_constraint("uvicorn", 4)

    def test_uvicorn_with_one_worker_is_allowed(self):
        _check_granian_workers_constraint("uvicorn", 1)

    def test_granian_with_one_worker_is_allowed(self):
        """granian + workers=1 is the correct, documented usage."""
        # Should not raise or exit
        _check_granian_workers_constraint("granian", 1)

    def test_granian_with_two_workers_exits(self):
        """granian + workers=2 must be rejected at startup."""
        with pytest.raises(SystemExit) as exc_info:
            _check_granian_workers_constraint("granian", 2)
        assert exc_info.value.code == 1

    def test_granian_with_many_workers_exits(self):
        """Any value > 1 must be rejected."""
        with pytest.raises(SystemExit) as exc_info:
            _check_granian_workers_constraint("granian", 8)
        assert exc_info.value.code == 1

    def test_exit_message_mentions_key_terms(self, caplog):
        """Error log should mention in-process state so operator knows why."""
        import logging

        with pytest.raises(SystemExit):
            with caplog.at_level(logging.ERROR, logger="oompah"):
                _check_granian_workers_constraint("granian", 2)

        combined = " ".join(caplog.messages)
        assert "granian" in combined.lower()
        assert "1" in combined  # mentions workers must be 1
