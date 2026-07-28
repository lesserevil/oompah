#!/usr/bin/env python3
"""Authenticated HTTP helper for Makefile lifecycle commands.

Usage (from Makefile or shell):
  python3 scripts/oompah_http.py GET  /api/v1/state
  python3 scripts/oompah_http.py POST /api/v1/orchestrator/restart '{"drain_timeout_s": 3600}'

Reads credentials from environment variables only (never from command-line
arguments) to prevent password leakage via the process table (/proc/*/cmdline).

Environment variables used:
  OOMPAH_SERVER_URL         Base URL (default: http://127.0.0.1:8080)
  OOMPAH_SERVER_USERNAME    Basic-auth username
  OOMPAH_SERVER_PASSWORD    Plaintext password (use PASSWORD_FILE instead)
  OOMPAH_SERVER_PASSWORD_FILE  Path to a file containing the plaintext password

Exit codes:
  0   Success; response JSON is printed to stdout.
  1   Connection error, timeout, auth failure, or non-2xx response.

The 401 error path never echoes credentials, Authorization header content,
or the raw password.  The OOMPAH_SERVER_URL is sanitized: any URL containing
embedded credentials (user:pass@host) causes an error exit before any request
is made.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request

from oompah.client_auth import (
    CredentialError,
    format_auth_error,
    resolve_client_credentials,
    sanitize_server_url,
)

# ---------------------------------------------------------------------------
# Resolve server URL (no embedded credentials allowed)
# ---------------------------------------------------------------------------

def _server_url() -> str:
    raw = os.environ.get("OOMPAH_SERVER_URL", "http://127.0.0.1:8080")
    try:
        return sanitize_server_url(raw) or "http://127.0.0.1:8080"
    except CredentialError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Resolve client credentials
# ---------------------------------------------------------------------------

def _resolve_credentials() -> tuple[str, str] | None:
    """Return (username, password) or None for unauthenticated."""
    try:
        credentials = resolve_client_credentials()
    except CredentialError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    return tuple(credentials) if credentials is not None else None


# ---------------------------------------------------------------------------
# HTTP request
# ---------------------------------------------------------------------------

def _make_request(method: str, path: str, body_json: str | None = None) -> None:
    """Make an authenticated HTTP request and print the response JSON."""
    base = _server_url()
    url = base + path
    creds = _resolve_credentials()

    data = body_json.encode("utf-8") if body_json else None
    headers: dict[str, str] = {}
    if data:
        headers["Content-Type"] = "application/json"

    if creds is not None:
        username, password = creds
        raw = f"{username}:{password}"
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {encoded}"
        # raw and encoded are local; never printed or logged.

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            print(body.decode("utf-8", errors="replace"))
            return
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            print(format_auth_error(base), file=sys.stderr)
            sys.exit(1)
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = exc.reason
        print(f"ERROR ({exc.code}): {err_body}", file=sys.stderr)
        sys.exit(1)
    except ConnectionRefusedError:
        print(
            f"ERROR: Cannot connect to oompah server at {base}.\n"
            "Is the server running? Start it with: make start",
            file=sys.stderr,
        )
        sys.exit(1)
    except TimeoutError:
        print(f"ERROR: Request to {base} timed out.", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"ERROR: Network error: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 3:
        print(
            f"Usage: {sys.argv[0]} METHOD /api/path [json_body]",
            file=sys.stderr,
        )
        sys.exit(1)

    method = sys.argv[1].upper()
    path = sys.argv[2]
    body_json = sys.argv[3] if len(sys.argv) > 3 else None

    _make_request(method, path, body_json)


if __name__ == "__main__":
    main()
