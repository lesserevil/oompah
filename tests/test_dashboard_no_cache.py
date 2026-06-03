"""Tests that HTML page routes include cache-busting headers.

TASK-428: The dashboard JS error 'toggleHideMerged is not defined' was caused
by browsers serving a stale cached copy of dashboard.html from before the
function was added.  Fix: HTML page routes must return Cache-Control headers
that prevent browser caching so users always receive the latest template after
a server auto-update + restart.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from oompah.server import app, _load_template, _NO_CACHE_HEADERS, _html_response


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 1.  Helper unit tests
# ---------------------------------------------------------------------------


class TestHtmlResponse:
    """_html_response() must include cache-busting headers."""

    def test_no_cache_header_set(self):
        resp = _html_response("dashboard.html")
        assert resp.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"

    def test_pragma_header_set(self):
        resp = _html_response("dashboard.html")
        assert resp.headers["Pragma"] == "no-cache"

    def test_expires_header_set(self):
        resp = _html_response("dashboard.html")
        assert resp.headers["Expires"] == "0"

    def test_content_is_template(self):
        resp = _html_response("dashboard.html")
        template = _load_template("dashboard.html")
        assert resp.body.decode() == template

    def test_no_cache_headers_constant_keys(self):
        assert "Cache-Control" in _NO_CACHE_HEADERS
        assert "Pragma" in _NO_CACHE_HEADERS
        assert "Expires" in _NO_CACHE_HEADERS


# ---------------------------------------------------------------------------
# 2.  Route-level cache-header tests (via TestClient)
# ---------------------------------------------------------------------------


_HTML_ROUTES = ["/", "/providers", "/projects-manage", "/foci", "/reviews"]


@pytest.mark.parametrize("route", _HTML_ROUTES)
def test_html_route_has_no_cache_header(client, route):
    """Every HTML page must return Cache-Control: no-cache, no-store, must-revalidate."""
    resp = client.get(route)
    assert resp.status_code == 200
    cc = resp.headers.get("cache-control", "")
    assert "no-cache" in cc, (
        f"{route} must send Cache-Control: no-cache … (got {cc!r})"
    )
    assert "no-store" in cc, (
        f"{route} must send Cache-Control: … no-store … (got {cc!r})"
    )


@pytest.mark.parametrize("route", _HTML_ROUTES)
def test_html_route_has_pragma_no_cache(client, route):
    resp = client.get(route)
    assert resp.status_code == 200
    pragma = resp.headers.get("pragma", "")
    assert pragma == "no-cache", (
        f"{route} must send Pragma: no-cache (got {pragma!r})"
    )


# ---------------------------------------------------------------------------
# 3.  Regression: toggleHideMerged is defined in the served dashboard
# ---------------------------------------------------------------------------


def test_dashboard_contains_toggle_hide_merged_function(client):
    """The served dashboard HTML must define toggleHideMerged().

    This is the regression test for TASK-428: if the browser ever receives
    a page without this function (stale cache) and the user clicks the
    in-flight-only checkbox, they get ReferenceError: toggleHideMerged is
    not defined.
    """
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "function toggleHideMerged" in html, (
        "dashboard.html must define function toggleHideMerged() so that the "
        "in-flight-only checkbox onchange handler can call it"
    )


def test_dashboard_checkbox_references_toggle_hide_merged(client):
    """The checkbox onchange= attribute must name toggleHideMerged()."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert 'onchange="toggleHideMerged()"' in html, (
        "The hide-merged checkbox must have onchange=\"toggleHideMerged()\" "
        "and the function must be defined in the same page"
    )
