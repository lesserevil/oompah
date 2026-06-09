"""Tests for the granian workers>1 guard in oompah.__main__.

TASK-472.7: granian must always run with workers=1 because oompah holds
shared in-process state (orchestrator singleton + _ws_clients) that cannot
safely be shared across multiple OS-level worker processes.

These tests verify:
- workers>1 with granian is rejected at startup
- workers==1 with granian is accepted
- workers>1 with uvicorn is accepted (uvicorn doesn't have the constraint)
- _resolve_server_backend honours CLI > env > default precedence
- _resolve_workers honours CLI > env > default precedence
"""

from __future__ import annotations

import sys
import pytest


class TestResolveServerBackend:
    def test_default_is_uvicorn(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_BACKEND", raising=False)
        from oompah.__main__ import _resolve_server_backend
        assert _resolve_server_backend(None) == "uvicorn"

    def test_cli_overrides_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "granian")
        from oompah.__main__ import _resolve_server_backend
        assert _resolve_server_backend("uvicorn") == "uvicorn"

    def test_env_granian(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "granian")
        from oompah.__main__ import _resolve_server_backend
        assert _resolve_server_backend(None) == "granian"

    def test_env_uvicorn_explicit(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "uvicorn")
        from oompah.__main__ import _resolve_server_backend
        assert _resolve_server_backend(None) == "uvicorn"

    def test_unknown_env_value_falls_back_to_uvicorn(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "tornado")
        from oompah.__main__ import _resolve_server_backend
        assert _resolve_server_backend(None) == "uvicorn"

    def test_empty_env_falls_back_to_uvicorn(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_BACKEND", "")
        from oompah.__main__ import _resolve_server_backend
        assert _resolve_server_backend(None) == "uvicorn"

    def test_cli_granian(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_BACKEND", raising=False)
        from oompah.__main__ import _resolve_server_backend
        assert _resolve_server_backend("granian") == "granian"


class TestResolveWorkers:
    def test_default_is_1(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_SERVER_WORKERS", raising=False)
        from oompah.__main__ import _resolve_workers
        assert _resolve_workers(None) == 1

    def test_cli_overrides_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_WORKERS", "4")
        from oompah.__main__ import _resolve_workers
        assert _resolve_workers(2) == 2

    def test_env_integer(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_WORKERS", "3")
        from oompah.__main__ import _resolve_workers
        assert _resolve_workers(None) == 3

    def test_env_invalid_falls_back_to_1(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_WORKERS", "notanumber")
        from oompah.__main__ import _resolve_workers
        assert _resolve_workers(None) == 1

    def test_env_empty_falls_back_to_1(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_SERVER_WORKERS", "")
        from oompah.__main__ import _resolve_workers
        assert _resolve_workers(None) == 1


class TestGranianWorkersConstraint:
    """_check_granian_workers_constraint must reject workers>1 for granian."""

    def test_granian_workers_1_accepted(self):
        """workers=1 with granian must not raise or exit."""
        from oompah.__main__ import _check_granian_workers_constraint
        # Should not raise
        _check_granian_workers_constraint("granian", 1)

    def test_granian_workers_2_rejected(self):
        """workers=2 with granian must call sys.exit(1)."""
        from oompah.__main__ import _check_granian_workers_constraint
        with pytest.raises(SystemExit) as exc_info:
            _check_granian_workers_constraint("granian", 2)
        assert exc_info.value.code == 1

    def test_granian_workers_large_rejected(self):
        """Any workers>1 with granian must be rejected."""
        from oompah.__main__ import _check_granian_workers_constraint
        with pytest.raises(SystemExit) as exc_info:
            _check_granian_workers_constraint("granian", 8)
        assert exc_info.value.code == 1

    def test_uvicorn_workers_2_accepted(self):
        """workers>1 with uvicorn must NOT trigger the guard."""
        from oompah.__main__ import _check_granian_workers_constraint
        # uvicorn supports multi-worker; no constraint
        _check_granian_workers_constraint("uvicorn", 2)

    def test_uvicorn_workers_8_accepted(self):
        from oompah.__main__ import _check_granian_workers_constraint
        _check_granian_workers_constraint("uvicorn", 8)

    def test_error_message_mentions_workers_1(self, caplog):
        """Error log must tell the operator to set workers=1."""
        import logging
        from oompah.__main__ import _check_granian_workers_constraint
        with caplog.at_level(logging.ERROR, logger="oompah"):
            with pytest.raises(SystemExit):
                _check_granian_workers_constraint("granian", 3)
        assert any(
            "workers must be 1" in record.message or "workers=1" in record.message
            for record in caplog.records
        ), f"Expected error message about workers=1, got: {[r.message for r in caplog.records]}"
