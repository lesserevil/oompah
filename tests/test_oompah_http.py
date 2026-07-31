"""Tests for the authenticated Makefile HTTP helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from oompah.client_auth import CLIENT_AUTH_DISABLED_ENV


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts" / "oompah_http.py"


def _load_helper():
    spec = importlib.util.spec_from_file_location("test_oompah_http_helper", HELPER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lifecycle_helper_refreshes_current_dotenv_client_inputs(tmp_path, monkeypatch):
    helper = _load_helper()
    (tmp_path / ".env").write_text(
        "OOMPAH_SERVER_USERNAME=rotated-user\n"
        "OOMPAH_SERVER_PASSWORD_FILE=/run/secrets/rotated-password\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OOMPAH_SERVER_USERNAME", raising=False)
    monkeypatch.delenv("OOMPAH_SERVER_PASSWORD", raising=False)
    monkeypatch.delenv("OOMPAH_SERVER_PASSWORD_FILE", raising=False)
    monkeypatch.delenv(CLIENT_AUTH_DISABLED_ENV, raising=False)
    monkeypatch.setattr(sys, "argv", [str(HELPER_PATH), "GET", "/api/v1/state"])
    calls: list[tuple[str, str, str | None]] = []
    monkeypatch.setattr(
        helper,
        "_make_request",
        lambda method, path, body: calls.append((method, path, body)),
    )

    helper.main()

    assert calls == [("GET", "/api/v1/state", None)]
    assert helper.os.environ["OOMPAH_SERVER_USERNAME"] == "rotated-user"
    assert (
        helper.os.environ["OOMPAH_SERVER_PASSWORD_FILE"]
        == "/run/secrets/rotated-password"
    )
