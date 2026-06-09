"""Granian ASGI parity tests for non-JSON routes (TASK-472.5).

Validates that the three UploadFile/multipart attachment endpoints, the
/static StaticFiles mount, and the Jinja/HTML routes (cache-busting headers)
behave identically under Granian as under uvicorn (FastAPI TestClient).

Granian 2.x is used in ASGI mode (``Interfaces.ASGI``) with a single worker.

Skips cleanly if granian is not installed.
"""

from __future__ import annotations

import signal
import socket
import subprocess
import sys
import time
from typing import Generator

import httpx
import pytest
from fastapi.testclient import TestClient

from oompah.server import app, _NO_CACHE_HEADERS

granian = pytest.importorskip("granian", reason="granian not installed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

def _min_png(extra: int = 56) -> bytes:
    """Return minimal PNG-magic bytes large enough to look like a real file."""
    return _PNG_MAGIC + b"\x00" * extra


def _free_port() -> int:
    """Return a currently unused local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ---------------------------------------------------------------------------
# Session-scoped Granian server fixture
# ---------------------------------------------------------------------------

_GRANIAN_SCRIPT = """\
from granian import Granian
from granian.constants import Interfaces
Granian(
    "oompah.server:app",
    address="127.0.0.1",
    port={port},
    interface=Interfaces.ASGI,
    workers=1,
    log_enabled=False,
).serve()
"""


@pytest.fixture(scope="module")
def granian_base_url() -> Generator[str, None, None]:
    """Start a Granian ASGI server and yield its base URL.

    The server runs in a subprocess so it has its own event loop (matching
    production behaviour).  We poll until the root route responds 200 before
    yielding, ensuring the server is ready before any test runs.
    """
    port = _free_port()
    script = _GRANIAN_SCRIPT.format(port=port)
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    base = f"http://127.0.0.1:{port}"

    # Wait up to 10 s for the server to become ready.
    deadline = time.monotonic() + 10.0
    ready = False
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            pytest.fail(
                f"Granian exited early (rc={proc.returncode}).\n"
                f"stdout: {stdout.decode()[:400]}\n"
                f"stderr: {stderr.decode()[:400]}"
            )
        try:
            r = httpx.get(base + "/", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(0.1)

    if not ready:
        proc.terminate()
        proc.wait(timeout=5)
        pytest.fail(f"Granian server did not become ready within 10 s on port {port}")

    try:
        yield base
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait(timeout=3)


@pytest.fixture(scope="module")
def tc() -> TestClient:
    """TestClient (uvicorn code path) for parity comparison."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# HTML / Jinja routes — cache-busting headers
# ---------------------------------------------------------------------------

_HTML_ROUTES = ["/", "/providers", "/projects-manage", "/foci", "/reviews"]


class TestHtmlRoutes:
    """HTML routes must return 200 with cache-busting headers under Granian.

    Each test also verifies parity with the TestClient (uvicorn) path.
    """

    @pytest.mark.parametrize("route", _HTML_ROUTES)
    def test_status_200(self, granian_base_url: str, tc: TestClient, route: str):
        """HTML route returns HTTP 200 under Granian."""
        r = httpx.get(granian_base_url + route)
        assert r.status_code == 200, (
            f"Granian: {route} returned {r.status_code}, expected 200"
        )
        # Parity: TestClient agrees.
        r_tc = tc.get(route)
        assert r_tc.status_code == r.status_code, (
            f"Status mismatch: Granian={r.status_code}, uvicorn={r_tc.status_code}"
        )

    @pytest.mark.parametrize("route", _HTML_ROUTES)
    def test_cache_control_no_cache(self, granian_base_url: str, tc: TestClient, route: str):
        """HTML route includes no-cache Cache-Control under Granian."""
        r = httpx.get(granian_base_url + route)
        cc = r.headers.get("cache-control", "")
        assert "no-cache" in cc, (
            f"Granian: {route} missing 'no-cache' in Cache-Control (got {cc!r})"
        )
        assert "no-store" in cc, (
            f"Granian: {route} missing 'no-store' in Cache-Control (got {cc!r})"
        )
        assert "must-revalidate" in cc, (
            f"Granian: {route} missing 'must-revalidate' in Cache-Control (got {cc!r})"
        )
        # Parity with uvicorn.
        r_tc = tc.get(route)
        assert r_tc.headers.get("cache-control") == r.headers.get("cache-control"), (
            f"Cache-Control mismatch for {route}: "
            f"Granian={r.headers.get('cache-control')!r}, "
            f"uvicorn={r_tc.headers.get('cache-control')!r}"
        )

    @pytest.mark.parametrize("route", _HTML_ROUTES)
    def test_pragma_no_cache(self, granian_base_url: str, tc: TestClient, route: str):
        """HTML route includes Pragma: no-cache under Granian."""
        r = httpx.get(granian_base_url + route)
        pragma = r.headers.get("pragma", "")
        assert pragma == "no-cache", (
            f"Granian: {route} Pragma header is {pragma!r}, expected 'no-cache'"
        )
        r_tc = tc.get(route)
        assert r_tc.headers.get("pragma") == pragma, (
            f"Pragma mismatch for {route}: "
            f"Granian={pragma!r}, uvicorn={r_tc.headers.get('pragma')!r}"
        )

    @pytest.mark.parametrize("route", _HTML_ROUTES)
    def test_expires_zero(self, granian_base_url: str, tc: TestClient, route: str):
        """HTML route includes Expires: 0 under Granian."""
        r = httpx.get(granian_base_url + route)
        expires = r.headers.get("expires", "")
        assert expires == "0", (
            f"Granian: {route} Expires header is {expires!r}, expected '0'"
        )

    @pytest.mark.parametrize("route", _HTML_ROUTES)
    def test_content_type_html(self, granian_base_url: str, route: str):
        """HTML route returns text/html content type under Granian."""
        r = httpx.get(granian_base_url + route)
        ct = r.headers.get("content-type", "")
        assert "text/html" in ct, (
            f"Granian: {route} Content-Type is {ct!r}, expected text/html"
        )

    def test_dashboard_body_not_empty(self, granian_base_url: str, tc: TestClient):
        """Dashboard HTML body is non-trivially served through Granian."""
        r_g = httpx.get(granian_base_url + "/")
        r_tc = tc.get("/")
        assert r_g.status_code == 200
        assert len(r_g.text) > 100, "Dashboard HTML body too short — Granian may be truncating"
        # Exact body parity.
        assert r_g.text == r_tc.text, (
            "Dashboard HTML body differs between Granian and TestClient"
        )


# ---------------------------------------------------------------------------
# /static mount — StaticFiles
# ---------------------------------------------------------------------------


class TestStaticMount:
    """The /static StaticFiles mount must serve assets correctly under Granian."""

    def test_favicon_svg_returns_200(self, granian_base_url: str):
        """GET /static/favicon.svg returns HTTP 200 under Granian."""
        r = httpx.get(granian_base_url + "/static/favicon.svg")
        assert r.status_code == 200, (
            f"Granian: /static/favicon.svg returned {r.status_code}"
        )

    def test_favicon_svg_content_type(self, granian_base_url: str):
        """GET /static/favicon.svg has image/svg+xml content-type under Granian."""
        r = httpx.get(granian_base_url + "/static/favicon.svg")
        ct = r.headers.get("content-type", "")
        assert "svg" in ct, (
            f"Granian: /static/favicon.svg Content-Type is {ct!r}, expected svg"
        )

    def test_favicon_svg_body_starts_with_svg_tag(self, granian_base_url: str):
        """SVG body is not empty or corrupted."""
        r = httpx.get(granian_base_url + "/static/favicon.svg")
        assert r.status_code == 200
        assert len(r.content) > 0, "SVG body is empty"
        # SVGs are XML; body should contain a recognisable tag.
        assert b"<svg" in r.content or b"<?xml" in r.content, (
            f"SVG body doesn't look like SVG: {r.content[:80]!r}"
        )

    def test_static_parity_with_testclient(self, granian_base_url: str, tc: TestClient):
        """Granian and uvicorn serve the same /static/favicon.svg bytes."""
        r_g = httpx.get(granian_base_url + "/static/favicon.svg")
        r_tc = tc.get("/static/favicon.svg")
        assert r_g.status_code == r_tc.status_code, (
            f"Status mismatch: Granian={r_g.status_code}, uvicorn={r_tc.status_code}"
        )
        assert r_g.content == r_tc.content, (
            "SVG content differs between Granian and uvicorn"
        )
        assert r_g.headers.get("content-type") == r_tc.headers.get("content-type"), (
            "Content-Type differs"
        )

    def test_missing_static_file_returns_404(self, granian_base_url: str, tc: TestClient):
        """A non-existent static asset returns 404 under both Granian and uvicorn."""
        path = "/static/does_not_exist_xyz.png"
        r_g = httpx.get(granian_base_url + path)
        r_tc = tc.get(path)
        assert r_g.status_code == 404, (
            f"Granian: expected 404 for missing static file, got {r_g.status_code}"
        )
        assert r_tc.status_code == 404, (
            f"TestClient: expected 404 for missing static file, got {r_tc.status_code}"
        )


# ---------------------------------------------------------------------------
# Multipart / UploadFile attachment endpoints
# ---------------------------------------------------------------------------


class TestMultipartAttachmentEndpoints:
    """The three UploadFile/multipart attachment endpoints must be reachable
    and parse their request correctly under Granian.

    Without a wired orchestrator the endpoints return HTTP 503 (not 400/422),
    which proves that Granian's ASGI transport correctly passed the multipart
    body to the ASGI app and the app was able to extract it before hitting the
    missing-orchestrator guard.  A 400 or 422 would indicate a transport-level
    parsing failure.
    """

    # --- POST /api/v1/issues/{id}/attachments (upload) ---------------------

    def test_multipart_upload_parses_in_granian(self, granian_base_url: str):
        """Multipart upload request body is correctly parsed by Granian.

        Expected: 503 (orchestrator absent) not 400/422 (parse failure).
        """
        r = httpx.post(
            granian_base_url + "/api/v1/issues/foo-1/attachments",
            files={"file": ("shot.png", _min_png(), "image/png")},
        )
        # 503 = Granian parsed the multipart, app found no orchestrator.
        # 400/422 = Granian or starlette couldn't parse the multipart body.
        assert r.status_code == 503, (
            f"Expected 503 (orchestrator absent) after multipart parse; got {r.status_code}. "
            "A 400/422 would indicate Granian failed to pass multipart body to the ASGI app."
        )

    def test_multipart_upload_parity_with_testclient_no_orchestrator(
        self, granian_base_url: str, tc: TestClient
    ):
        """Without an orchestrator both Granian and TestClient return 503."""
        r_g = httpx.post(
            granian_base_url + "/api/v1/issues/foo-1/attachments",
            files={"file": ("shot.png", _min_png(), "image/png")},
        )
        r_tc = tc.post(
            "/api/v1/issues/foo-1/attachments",
            files={"file": ("shot.png", _min_png(), "image/png")},
        )
        assert r_g.status_code == r_tc.status_code, (
            f"Upload status mismatch: Granian={r_g.status_code}, uvicorn={r_tc.status_code}"
        )

    def test_multipart_upload_rejects_bad_mime_in_granian(self, granian_base_url: str):
        """Granian transport passes the multipart body; server rejects bad MIME with 415.

        Confirms that the MIME check in the ASGI app executes (not a transport error).
        """
        r = httpx.post(
            granian_base_url + "/api/v1/issues/foo-1/attachments",
            files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
        )
        # 503 = orchestrator check fires first (still proves transport works).
        # 415 = MIME check fires (even better — proves full handler path reached).
        assert r.status_code in (415, 503), (
            f"Expected 415 or 503 for bad MIME under Granian; got {r.status_code}"
        )

    def test_multipart_upload_bad_mime_parity(self, granian_base_url: str, tc: TestClient):
        """Bad-MIME upload returns the same status code under Granian and TestClient."""
        r_g = httpx.post(
            granian_base_url + "/api/v1/issues/foo-1/attachments",
            files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
        )
        r_tc = tc.post(
            "/api/v1/issues/foo-1/attachments",
            files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
        )
        assert r_g.status_code == r_tc.status_code, (
            f"Bad-MIME status mismatch: Granian={r_g.status_code}, uvicorn={r_tc.status_code}"
        )

    # --- GET /api/v1/issues/{id}/attachments (list) ------------------------

    def test_list_attachments_reachable_in_granian(self, granian_base_url: str):
        """GET list-attachments endpoint is reachable under Granian (503 without orch)."""
        r = httpx.get(granian_base_url + "/api/v1/issues/foo-1/attachments")
        # 503 from missing orchestrator proves the route was dispatched correctly.
        assert r.status_code == 503, (
            f"Expected 503 (no orchestrator) for list-attachments; got {r.status_code}"
        )

    def test_list_attachments_parity(self, granian_base_url: str, tc: TestClient):
        """List-attachments status code is identical under Granian and uvicorn."""
        r_g = httpx.get(granian_base_url + "/api/v1/issues/foo-1/attachments")
        r_tc = tc.get("/api/v1/issues/foo-1/attachments")
        assert r_g.status_code == r_tc.status_code, (
            f"List status mismatch: Granian={r_g.status_code}, uvicorn={r_tc.status_code}"
        )

    # --- GET /api/v1/attachments/{path:path} (serve) -----------------------

    def test_serve_attachment_path_traversal_dispatched_in_granian(
        self, granian_base_url: str
    ):
        """Traversal path reaches the ASGI app under Granian (503 = orchestrator guard;
        404 = path validation — both prove the route was dispatched, not rejected at
        transport level).

        Note: with no orchestrator the server guard fires first (503) before the
        path-validation check.  The separate test_server_attachments suite covers
        the 404-on-traversal path with a mocked orchestrator.
        """
        r = httpx.get(
            granian_base_url
            + "/api/v1/attachments/.oompah/attachments/../../etc/passwd"
        )
        assert r.status_code in (404, 503), (
            f"Granian: traversal path returned unexpected {r.status_code} "
            "(expected 404 or 503 from ASGI app, not a transport-level error)"
        )

    def test_serve_attachment_path_traversal_parity(
        self, granian_base_url: str, tc: TestClient
    ):
        """Path traversal returns the same status under Granian and uvicorn."""
        path = "/api/v1/attachments/.oompah/attachments/../../etc/passwd"
        r_g = httpx.get(granian_base_url + path)
        r_tc = tc.get(path)
        assert r_g.status_code == r_tc.status_code, (
            f"Traversal status mismatch: Granian={r_g.status_code}, uvicorn={r_tc.status_code}"
        )

    def test_serve_attachment_missing_orch_returns_503(self, granian_base_url: str):
        """Serving a (syntactically valid) attachment path returns 503 without orchestrator."""
        path = "/api/v1/attachments/.oompah/attachments/foo-1/x.png"
        r = httpx.get(granian_base_url + path)
        # 503 = route was dispatched, orchestrator guard fired.
        # 404 = path validation fired (also acceptable — no project store).
        assert r.status_code in (503, 404), (
            f"Granian: attachment serve returned unexpected {r.status_code}"
        )

    def test_serve_attachment_parity(self, granian_base_url: str, tc: TestClient):
        """Attachment serve returns same status under Granian and uvicorn."""
        path = "/api/v1/attachments/.oompah/attachments/foo-1/x.png"
        r_g = httpx.get(granian_base_url + path)
        r_tc = tc.get(path)
        assert r_g.status_code == r_tc.status_code, (
            f"Serve status mismatch: Granian={r_g.status_code}, uvicorn={r_tc.status_code}"
        )

    # --- DELETE /api/v1/attachments/{path:path} ----------------------------

    def test_delete_attachment_reachable_in_granian(self, granian_base_url: str):
        """DELETE attachment endpoint is dispatched correctly under Granian."""
        path = "/api/v1/attachments/.oompah/attachments/foo-1/x.png"
        r = httpx.delete(granian_base_url + path)
        # 503 = orchestrator guard, 404 = path validation — both mean the route was reached.
        assert r.status_code in (503, 404), (
            f"Granian: DELETE attachment returned unexpected {r.status_code}"
        )

    def test_delete_attachment_parity(self, granian_base_url: str, tc: TestClient):
        """DELETE attachment returns same status under Granian and uvicorn."""
        path = "/api/v1/attachments/.oompah/attachments/foo-1/x.png"
        r_g = httpx.delete(granian_base_url + path)
        r_tc = tc.delete(path)
        assert r_g.status_code == r_tc.status_code, (
            f"DELETE status mismatch: Granian={r_g.status_code}, uvicorn={r_tc.status_code}"
        )

    # --- Content-type header for multipart responses -----------------------

    def test_multipart_upload_response_content_type_json(self, granian_base_url: str):
        """Upload endpoint response is JSON under Granian (not garbled by transport)."""
        r = httpx.post(
            granian_base_url + "/api/v1/issues/foo-1/attachments",
            files={"file": ("shot.png", _min_png(), "image/png")},
        )
        ct = r.headers.get("content-type", "")
        assert "application/json" in ct, (
            f"Granian: upload response Content-Type is {ct!r}, expected JSON"
        )
        # Body must be valid JSON.
        try:
            r.json()
        except Exception as exc:
            pytest.fail(f"Granian upload response is not valid JSON: {exc}")
