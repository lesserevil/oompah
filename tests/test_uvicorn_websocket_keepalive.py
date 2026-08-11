"""Regression coverage for the dashboard WebSocket keepalive owner."""

from __future__ import annotations

import inspect

import uvicorn

from oompah import __main__ as main_module
from oompah.__main__ import _uvicorn_config_kwargs
from oompah.server import app


def test_uvicorn_protocol_keepalive_is_disabled_for_application_heartbeat():
    """Only the dashboard heartbeat owns liveness and reconnect recovery."""

    kwargs = _uvicorn_config_kwargs(8123)

    assert kwargs == {
        "host": "0.0.0.0",
        "port": 8123,
        "log_level": "info",
        "access_log": False,
        "ws_ping_interval": None,
    }
    config = uvicorn.Config(app, **kwargs)
    assert config.ws_ping_interval is None


def test_both_embedded_uvicorn_paths_share_one_keepalive_configuration():
    """The Granian fallback and default path cannot drift independently."""

    source = inspect.getsource(main_module._run)

    assert source.count("**_uvicorn_config_kwargs(port)") == 2
    assert "ws_ping_interval=" not in source
