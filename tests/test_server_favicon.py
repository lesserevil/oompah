"""Tests for the favicon route in server.py.

Verifies that:
  (1) /favicon.ico returns 200 with SVG content when the cache is populated
  (2) /favicon.svg returns 200 with SVG content when the cache is populated
  (3) The favicon route returns 404 when _FAVICON_CACHE is None (file absent)
  (4) The favicon handler does NOT call Path.read_bytes() per request —
      bytes are served from the module-level _FAVICON_CACHE variable
"""

from __future__ import annotations

import oompah.server as server_module
from fastapi.testclient import TestClient
from oompah.server import app

import pytest


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helper to temporarily override the module-level cache
# ---------------------------------------------------------------------------

class _FaviconCacheOverride:
    """Context manager that patches _FAVICON_CACHE with a given value."""

    def __init__(self, value: bytes | None):
        self._value = value
        self._orig: bytes | None = None

    def __enter__(self):
        self._orig = server_module._FAVICON_CACHE
        server_module._FAVICON_CACHE = self._value
        return self

    def __exit__(self, *_):
        server_module._FAVICON_CACHE = self._orig


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFaviconRoute:
    """GET /favicon.ico and /favicon.svg endpoint tests."""

    _FAKE_SVG = b"<svg xmlns='http://www.w3.org/2000/svg'/>"

    def test_favicon_ico_returns_200_when_cached(self, client):
        with _FaviconCacheOverride(self._FAKE_SVG):
            resp = client.get("/favicon.ico")
        assert resp.status_code == 200
        assert resp.content == self._FAKE_SVG
        assert "image/svg+xml" in resp.headers["content-type"]

    def test_favicon_svg_returns_200_when_cached(self, client):
        with _FaviconCacheOverride(self._FAKE_SVG):
            resp = client.get("/favicon.svg")
        assert resp.status_code == 200
        assert resp.content == self._FAKE_SVG
        assert "image/svg+xml" in resp.headers["content-type"]

    def test_favicon_returns_404_when_cache_is_none(self, client):
        with _FaviconCacheOverride(None):
            resp = client.get("/favicon.ico")
        assert resp.status_code == 404

    def test_favicon_cache_control_header(self, client):
        """Favicon should include a long-lived Cache-Control header."""
        with _FaviconCacheOverride(self._FAKE_SVG):
            resp = client.get("/favicon.ico")
        assert resp.status_code == 200
        assert "max-age=86400" in resp.headers.get("cache-control", "")

    def test_favicon_served_from_cache_not_disk(self, client, monkeypatch):
        """read_bytes must NOT be called during request handling.

        The whole point of the fix is that _FAVICON_CACHE is populated once
        at module load time.  If the handler still calls read_bytes() on
        Path objects, this test will fail.
        """
        call_log: list[str] = []

        orig_read_bytes = server_module.Path.read_bytes

        def spy_read_bytes(self):
            call_log.append(str(self))
            return orig_read_bytes(self)

        monkeypatch.setattr(server_module.Path, "read_bytes", spy_read_bytes)

        with _FaviconCacheOverride(self._FAKE_SVG):
            resp = client.get("/favicon.ico")

        assert resp.status_code == 200
        # No read_bytes call should be triggered by the favicon handler.
        favicon_reads = [p for p in call_log if "favicon" in p]
        assert favicon_reads == [], (
            f"favicon handler called read_bytes() on: {favicon_reads!r} — "
            "disk I/O must not happen per-request"
        )
