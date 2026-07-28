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
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# Resolve server URL (no embedded credentials allowed)
# ---------------------------------------------------------------------------

def _server_url() -> str:
    raw = os.environ.get("OOMPAH_SERVER_URL", "http://127.0.0.1:8080").strip().rstrip("/")
    if not raw:
        raw = "http://127.0.0.1:8080"
    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return raw
    if parsed.username or parsed.password:
        # Redact URL for error message.
        netloc = (parsed.hostname or "") + (f":{parsed.port}" if parsed.port else "")
        redacted = urllib.parse.urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))
        print(
            f"ERROR: OOMPAH_SERVER_URL must not contain credentials (user:pass@host).\n"
            f"Set OOMPAH_SERVER_USERNAME and OOMPAH_SERVER_PASSWORD_FILE instead.\n"
            f"(Redacted URL: {redacted!r})",
            file=sys.stderr,
        )
        sys.exit(1)
    return raw


# ---------------------------------------------------------------------------
# Resolve client credentials
# ---------------------------------------------------------------------------

def _resolve_credentials() -> tuple[str, str] | None:
    """Return (username, password) or None for unauthenticated."""
    username = os.environ.get("OOMPAH_SERVER_USERNAME", "").strip()
    password_file = os.environ.get("OOMPAH_SERVER_PASSWORD_FILE", "").strip()
    password_env = os.environ.get("OOMPAH_SERVER_PASSWORD", "").strip()

    if not username and not password_file and not password_env:
        return None

    if not username:
        print(
            "ERROR: OOMPAH_SERVER_USERNAME is required when a password is set.",
            file=sys.stderr,
        )
        sys.exit(1)

    if password_file and password_env:
        print(
            "ERROR: Set exactly one of OOMPAH_SERVER_PASSWORD or "
            "OOMPAH_SERVER_PASSWORD_FILE, not both.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not password_file and not password_env:
        print(
            "ERROR: A password source is required when OOMPAH_SERVER_USERNAME is set. "
            "Set OOMPAH_SERVER_PASSWORD_FILE or OOMPAH_SERVER_PASSWORD.",
            file=sys.stderr,
        )
        sys.exit(1)

    if password_file:
        import stat
        try:
            lst = os.lstat(password_file)
        except FileNotFoundError:
            print(f"ERROR: OOMPAH_SERVER_PASSWORD_FILE not found: {password_file!r}", file=sys.stderr)
            sys.exit(1)
        except OSError as exc:
            print(f"ERROR: Cannot access OOMPAH_SERVER_PASSWORD_FILE {password_file!r}: {exc.strerror}", file=sys.stderr)
            sys.exit(1)

        if stat.S_ISLNK(lst.st_mode):
            print(
                f"ERROR: OOMPAH_SERVER_PASSWORD_FILE {password_file!r} is a symbolic link. "
                "Provide the direct target path.",
                file=sys.stderr,
            )
            sys.exit(1)

        if not stat.S_ISREG(lst.st_mode):
            print(f"ERROR: OOMPAH_SERVER_PASSWORD_FILE {password_file!r} is not a regular file.", file=sys.stderr)
            sys.exit(1)

        # Permission warning
        mode = stat.S_IMODE(lst.st_mode)
        if mode & (stat.S_IRGRP | stat.S_IROTH):
            print(
                f"WARNING: OOMPAH_SERVER_PASSWORD_FILE {password_file!r} has unsafe permissions {oct(mode)}. "
                f"Consider: chmod 600 {password_file!r}",
                file=sys.stderr,
            )

        try:
            with open(password_file, "r", encoding="utf-8") as fh:
                password = fh.read().strip()
        except PermissionError:
            print(f"ERROR: OOMPAH_SERVER_PASSWORD_FILE {password_file!r} is not readable.", file=sys.stderr)
            sys.exit(1)
        except OSError as exc:
            print(f"ERROR: Failed to read OOMPAH_SERVER_PASSWORD_FILE: {exc.strerror}", file=sys.stderr)
            sys.exit(1)

        if not password:
            print(f"ERROR: OOMPAH_SERVER_PASSWORD_FILE {password_file!r} is empty.", file=sys.stderr)
            sys.exit(1)
    else:
        password = password_env

    return username, password


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
            print(
                "ERROR (401): Authentication required.\n"
                "Set OOMPAH_SERVER_USERNAME and OOMPAH_SERVER_PASSWORD_FILE (preferred)\n"
                "or OOMPAH_SERVER_PASSWORD to authenticate against the oompah server.\n"
                "Verify credentials match the server's htpasswd configuration.",
                file=sys.stderr,
            )
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
