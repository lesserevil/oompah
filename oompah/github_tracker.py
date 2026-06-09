"""GitHub Issues tracker adapter for oompah.

Implements :class:`GitHubIssueTracker`, a :class:`~oompah.tracker.TrackerProtocol`
adapter backed by the GitHub REST API.

Auth priority (highest first):

1. **GitHub App** — set ``OOMPAH_GITHUB_APP_ID``,
   ``OOMPAH_GITHUB_APP_PRIVATE_KEY_PATH`` (or
   ``OOMPAH_GITHUB_APP_PRIVATE_KEY``), and
   ``OOMPAH_GITHUB_APP_INSTALLATION_ID``.  A short-lived installation
   token (valid ≤ 1 hour) is generated automatically and refreshed
   before expiry.  Preferred for production.

2. **PAT** — set ``OOMPAH_GITHUB_TOKEN`` (or the GitHub-conventional
   ``GH_TOKEN`` / ``GITHUB_TOKEN``).  Suitable for development and CI
   where a GitHub App is not configured.

3. **gh CLI fallback** — if none of the above env vars are set,
   ``gh auth token`` is run once to obtain a token.  Convenient for
   local developer machines.

The :class:`GitHubClient` centralises:

- Request retries with exponential back-off for transient errors (5xx,
  network failures, connection timeouts).
- Per-request timeout with a sensible default (``OOMPAH_GITHUB_API_TIMEOUT``).
- Automatic link-header pagination (``request_paginated``).
- Rate-limit logging: remaining quota and reset time are logged at DEBUG
  on every response; a rate-limit *block* is logged at WARNING and the
  call is retried after the ``Retry-After`` / ``X-RateLimit-Reset``
  delay.
- ETag / conditional-GET cache hooks: callers may supply an ``etag``
  kwarg; a ``304 Not Modified`` response returns the caller's cached
  value unchanged.
- Response body redaction: ``Authorization`` headers and bearer tokens
  are scrubbed from log output.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from oompah.models import BlockerRef, Issue
from oompah.statuses import CANONICAL_STATUSES, NEEDS_HUMAN
from oompah.tracker import (
    TrackerError,
    TrackerTimeoutError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GH_API_BASE = "https://api.github.com"
_GH_API_VERSION = "2022-11-28"

# ---------------------------------------------------------------------------
# GitHub issue identifier parsing and formatting
# ---------------------------------------------------------------------------

# Regex for the canonical ``owner/repo#number`` form.
#
# GitHub owner constraints:
#   - 1–39 characters
#   - Alphanumeric and hyphens
#   - Must not start or end with a hyphen
#
# GitHub repo constraints:
#   - 1–100 characters
#   - Alphanumeric, hyphens, underscores, and dots
#
# Issue number:
#   - One or more decimal digits, no leading zeros (GitHub starts at 1).
_GITHUB_IDENTIFIER_RE = re.compile(
    r"^"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?|[A-Za-z0-9])"
    r"/"
    r"(?P<repo>[A-Za-z0-9][A-Za-z0-9_.\-]*)"
    r"#"
    r"(?P<number>[1-9][0-9]*)$"
)

# Characters that are unsafe in git branch names or filesystem paths. Replaced
# by a dash when constructing branch slugs from arbitrary text.
_BRANCH_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._\-/]")


class GitHubIdentifierError(ValueError):
    """Raised when a string cannot be parsed as a fully-qualified GitHub issue identifier.

    Provides a user-facing message that distinguishes between bare-number
    inputs (which are explicitly rejected as ambiguous) and other malformed
    identifiers.
    """


@dataclass(frozen=True)
class GitHubIdentifier:
    """A parsed, fully-qualified GitHub issue identifier.

    Canonical form:  ``owner/repo#1234``
    Display form:    ``repo#1234``          (short, for UI / task hubs)
    URL-safe form:   ``owner/repo/1234``    (no ``#`` fragment character)
    Branch slug:     ``gh-1234``            (filesystem-safe, no ``/`` or ``#``)

    Construct via :func:`parse_github_identifier` (preferred) or directly
    when all three components are already known.

    Parameters
    ----------
    owner:
        GitHub organisation or user login (e.g. ``"lesserevil"``).
    repo:
        Repository name (e.g. ``"oompah-tasks"``).
    number:
        Positive issue number assigned by GitHub (e.g. ``1234``).
    """

    owner: str
    repo: str
    number: int

    def __post_init__(self) -> None:
        if not self.owner:
            raise GitHubIdentifierError("owner must not be empty")
        if not self.repo:
            raise GitHubIdentifierError("repo must not be empty")
        if self.number < 1:
            raise GitHubIdentifierError(
                f"issue number must be a positive integer, got {self.number!r}"
            )

    def __str__(self) -> str:  # noqa: D401
        return self.canonical

    @property
    def canonical(self) -> str:
        """Globally unique, fully-qualified identifier: ``owner/repo#1234``."""
        return f"{self.owner}/{self.repo}#{self.number}"

    @property
    def display(self) -> str:
        """Short display identifier: ``repo#1234``.

        Suitable for UI labels, task hub cards, and log lines where the owner
        can be inferred from context (e.g. a single central task hub).
        """
        return f"{self.repo}#{self.number}"

    @property
    def url_safe(self) -> str:
        """URL-path-safe identifier: ``owner/repo/1234``.

        The ``#`` character is the URL fragment separator and must not appear
        in path segments.  This form replaces it with a third ``/`` path
        component so the three components can be extracted from the route
        without URL-encoding.
        """
        return f"{self.owner}/{self.repo}/{self.number}"

    @property
    def branch_slug(self) -> str:
        """Git branch–safe and filesystem-safe slug: ``gh-<number>``.

        Branch names derived from bare issue numbers are ambiguous across
        repositories; the ``gh-`` prefix marks the slug as GitHub-sourced.
        The slug is stable (does not change if the title changes) and safe
        to embed in branch names following a project/epic prefix, e.g.
        ``oompah/myproject/gh-1234``.
        """
        return f"gh-{self.number}"

    @classmethod
    def from_url_safe(cls, url_safe: str) -> "GitHubIdentifier":
        """Reconstruct a :class:`GitHubIdentifier` from its URL-safe form.

        Accepts ``owner/repo/1234`` (three slash-separated components).
        Raises :class:`GitHubIdentifierError` for invalid input.
        """
        parts = url_safe.split("/")
        if len(parts) != 3:
            raise GitHubIdentifierError(
                f"URL-safe identifier must have the form owner/repo/number, "
                f"got {url_safe!r}"
            )
        owner, repo, raw_number = parts
        try:
            number = int(raw_number)
        except ValueError:
            raise GitHubIdentifierError(
                f"URL-safe identifier has a non-numeric issue number: {raw_number!r}"
            )
        return cls(owner=owner, repo=repo, number=number)


def parse_github_identifier(s: str) -> GitHubIdentifier:
    """Parse a fully-qualified GitHub issue identifier string.

    Accepted form:
      ``owner/repo#1234`` — canonical, fully-qualified identifier.

    Rejected forms (raises :class:`GitHubIdentifierError`):
      ``1234``         — bare integer: ambiguous across repositories.
      ``#1234``        — missing owner and repo.
      ``repo#1234``    — missing owner (unqualified repo reference).
      ``owner/repo``   — missing issue number.
      ``owner/repo#0`` — issue numbers start at 1.

    Parameters
    ----------
    s:
        The string to parse.

    Returns
    -------
    GitHubIdentifier
        The parsed identifier with ``owner``, ``repo``, and ``number``
        attributes populated.

    Raises
    ------
    GitHubIdentifierError
        When *s* is not a valid fully-qualified GitHub issue identifier.
        Bare numeric strings produce a specific error message explaining
        why they are rejected.
    """
    stripped = (s or "").strip()
    if not stripped:
        raise GitHubIdentifierError("identifier must not be empty")

    # Detect bare numbers early to give a targeted error message.
    if stripped.lstrip("0123456789") == "" or re.fullmatch(r"#\d+", stripped):
        raise GitHubIdentifierError(
            f"bare numeric identifier {stripped!r} is not a valid GitHub issue "
            "identifier. Use the fully-qualified form owner/repo#<number>, e.g. "
            "'lesserevil/oompah-tasks#1234'."
        )

    m = _GITHUB_IDENTIFIER_RE.match(stripped)
    if not m:
        raise GitHubIdentifierError(
            f"cannot parse {stripped!r} as a GitHub issue identifier. "
            "Expected the form owner/repo#<number> (e.g. "
            "'lesserevil/oompah-tasks#1234')."
        )

    return GitHubIdentifier(
        owner=m.group("owner"),
        repo=m.group("repo"),
        number=int(m.group("number")),
    )


def github_identifier_to_issue_fields(
    gh_id: GitHubIdentifier,
) -> dict[str, str | int]:
    """Return a dict of :class:`~oompah.models.Issue` fields for a parsed identifier.

    Maps :class:`GitHubIdentifier` attributes to the structured identity
    fields added to :class:`~oompah.models.Issue` by TASK-457.2 so callers
    can unpack the result directly::

        issue = Issue(
            id=str(gh_id.number),
            identifier=gh_id.canonical,
            title="...",
            **github_identifier_to_issue_fields(gh_id),
        )
    """
    return {
        "tracker_kind": "github_issues",
        "owner": gh_id.owner,
        "repo": gh_id.repo,
        "issue_number": str(gh_id.number),
        "display_identifier": gh_id.display,
    }

# Default per-request timeout in seconds.  Override via OOMPAH_GITHUB_API_TIMEOUT.
_DEFAULT_TIMEOUT_S = 30.0

# Maximum number of retry attempts for transient failures.
_MAX_RETRIES = 3

# Jitter cap for retry back-off (seconds).
_MAX_BACKOFF_S = 60.0

# Installation token lifetime.  GitHub tokens expire after 1 hour; we refresh
# with this many seconds of headroom so we don't use an almost-expired token.
_TOKEN_REFRESH_HEADROOM_S = 120

# Pattern used to scrub bearer tokens from log lines.
_TOKEN_REDACT_RE = re.compile(
    r"(Bearer\s+)[A-Za-z0-9\-_.~+/]+=*", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redact(text: str) -> str:
    """Return *text* with any embedded bearer tokens replaced by ``Bearer [REDACTED]``."""
    return _TOKEN_REDACT_RE.sub(r"\1[REDACTED]", text)


def _timeout() -> float:
    """Return the configured per-request timeout in seconds."""
    raw = os.environ.get("OOMPAH_GITHUB_API_TIMEOUT")
    if raw is None:
        return _DEFAULT_TIMEOUT_S
    try:
        value = float(raw)
        if value > 0:
            return value
    except (TypeError, ValueError):
        pass
    return _DEFAULT_TIMEOUT_S


def _log_rate_limits(resp: httpx.Response) -> None:
    """Log GitHub rate-limit headers at DEBUG level."""
    remaining = resp.headers.get("x-ratelimit-remaining")
    limit = resp.headers.get("x-ratelimit-limit")
    reset = resp.headers.get("x-ratelimit-reset")
    if remaining is not None:
        reset_dt = ""
        if reset:
            try:
                reset_dt = " reset=" + datetime.fromtimestamp(
                    int(reset), tz=timezone.utc
                ).isoformat()
            except Exception:
                reset_dt = f" reset={reset}"
        logger.debug(
            "GitHub API rate limit: %s/%s remaining%s [%s %s]",
            remaining,
            limit or "?",
            reset_dt,
            resp.request.method,
            resp.request.url,
        )


# ---------------------------------------------------------------------------
# GitHub App JWT / installation token
# ---------------------------------------------------------------------------


def _generate_app_jwt(app_id: str, private_key_pem: str) -> str:
    """Return a signed GitHub App JWT valid for 60 seconds.

    Parameters
    ----------
    app_id:
        The numeric or string GitHub App ID.
    private_key_pem:
        RSA private key in PEM format (the contents of the ``.pem`` file,
        not a path).

    Returns
    -------
    str
        A signed JWT string that can be used as ``Bearer <jwt>`` in the
        ``Authorization`` header when calling GitHub App endpoints.
    """
    try:
        import jwt as pyjwt
    except ImportError as exc:  # pragma: no cover
        raise TrackerError(
            "PyJWT is not installed; cannot generate GitHub App JWT. "
            "Install it with: pip install PyJWT[crypto]"
        ) from exc

    now = int(time.time())
    payload = {
        "iat": now - 60,  # issued-at with 60 s clock skew tolerance
        "exp": now + 600,  # 10 minute expiry (max allowed by GitHub)
        "iss": str(app_id),
    }
    try:
        token: str = pyjwt.encode(payload, private_key_pem, algorithm="RS256")
        return token
    except Exception as exc:
        raise TrackerError(f"Failed to generate GitHub App JWT: {exc}") from exc


@dataclass
class _InstallationToken:
    """Cached GitHub App installation token with expiry tracking."""

    token: str
    expires_at: float  # monotonic time


# ---------------------------------------------------------------------------
# Auth resolver
# ---------------------------------------------------------------------------


class GitHubAuth:
    """Resolve and manage GitHub authentication.

    Priority:
    1. GitHub App (``OOMPAH_GITHUB_APP_*`` env vars).
    2. PAT (``OOMPAH_GITHUB_TOKEN`` / ``GH_TOKEN`` / ``GITHUB_TOKEN``).
    3. ``gh auth token`` CLI fallback.

    The resolved token is cached.  GitHub App installation tokens are
    refreshed automatically before they expire.
    """

    def __init__(
        self,
        *,
        app_id: str | None = None,
        app_private_key: str | None = None,
        app_installation_id: str | None = None,
        pat: str | None = None,
    ) -> None:
        # Explicit overrides (used by tests).
        self._app_id: str | None = app_id or os.environ.get("OOMPAH_GITHUB_APP_ID")
        self._app_installation_id: str | None = (
            app_installation_id
            or os.environ.get("OOMPAH_GITHUB_APP_INSTALLATION_ID")
        )
        self._app_private_key: str | None = self._load_private_key(app_private_key)
        self._pat: str | None = pat or self._resolve_pat()

        # Cached installation token for GitHub App auth.
        self._installation_token: _InstallationToken | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_private_key(override: str | None) -> str | None:
        """Load the RSA private key from env vars or path."""
        if override:
            return override
        # Inline PEM content takes priority over a file path.
        key_content = os.environ.get("OOMPAH_GITHUB_APP_PRIVATE_KEY")
        if key_content:
            return key_content
        key_path = os.environ.get("OOMPAH_GITHUB_APP_PRIVATE_KEY_PATH")
        if key_path:
            try:
                with open(key_path, encoding="utf-8") as fh:
                    return fh.read()
            except OSError as exc:
                logger.warning(
                    "Cannot read OOMPAH_GITHUB_APP_PRIVATE_KEY_PATH=%s: %s",
                    key_path,
                    exc,
                )
        return None

    @staticmethod
    def _resolve_pat() -> str | None:
        """Resolve a PAT from environment variables."""
        return (
            os.environ.get("OOMPAH_GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
        )

    @staticmethod
    def _resolve_gh_cli_token() -> str | None:
        """Run ``gh auth token`` to obtain a token from the gh CLI."""
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                token = result.stdout.strip()
                if token:
                    return token
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _has_app_credentials(self) -> bool:
        return bool(self._app_id and self._app_private_key and self._app_installation_id)

    def _fetch_installation_token(self) -> str:
        """Exchange the App JWT for a short-lived installation token."""
        jwt_token = _generate_app_jwt(self._app_id, self._app_private_key)  # type: ignore[arg-type]
        url = (
            f"{_GH_API_BASE}/app/installations"
            f"/{self._app_installation_id}/access_tokens"
        )
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _GH_API_VERSION,
        }
        try:
            resp = httpx.post(url, headers=headers, timeout=_timeout())
        except httpx.TimeoutException as exc:
            raise TrackerTimeoutError(
                f"Timed out fetching GitHub App installation token: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise TrackerError(
                f"Network error fetching GitHub App installation token: {exc}"
            ) from exc

        if resp.status_code == 401:
            raise TrackerError(
                "GitHub App authentication failed: invalid App ID, private key, "
                "or installation ID. Check OOMPAH_GITHUB_APP_ID, "
                "OOMPAH_GITHUB_APP_PRIVATE_KEY_PATH, and "
                "OOMPAH_GITHUB_APP_INSTALLATION_ID."
            )
        if resp.status_code == 403:
            raise TrackerError(
                "GitHub App is not authorized for this installation. "
                "Verify the App is installed on the target repository/organisation."
            )
        if not resp.is_success:
            raise TrackerError(
                f"Failed to obtain GitHub App installation token "
                f"(HTTP {resp.status_code}): {resp.text[:200]}"
            )

        data = resp.json()
        token = data.get("token")
        if not token:
            raise TrackerError(
                "GitHub API returned no token in installation token response."
            )

        # Parse expiry and convert to monotonic time.
        expires_at_mono = time.monotonic() + 3600  # default 1 hour
        expires_at_str = data.get("expires_at", "")
        if expires_at_str:
            try:
                dt = datetime.fromisoformat(
                    expires_at_str.replace("Z", "+00:00")
                )
                delta = (dt - datetime.now(timezone.utc)).total_seconds()
                expires_at_mono = time.monotonic() + max(delta, 0)
            except Exception:
                pass  # fall back to 1 hour default

        return token, expires_at_mono

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def auth_mode(self) -> str:
        """Return a human-readable description of the configured auth mode."""
        if self._has_app_credentials():
            return "github_app"
        if self._pat:
            return "pat"
        return "gh_cli"

    def get_token(self) -> str | None:
        """Return a valid GitHub bearer token, or *None* if no auth is configured.

        For GitHub App auth, the installation token is refreshed automatically
        when it has less than :data:`_TOKEN_REFRESH_HEADROOM_S` seconds
        remaining.
        """
        if self._has_app_credentials():
            with self._lock:
                if (
                    self._installation_token is None
                    or time.monotonic()
                    >= self._installation_token.expires_at - _TOKEN_REFRESH_HEADROOM_S
                ):
                    logger.debug("Refreshing GitHub App installation token.")
                    token_str, expires_at_mono = self._fetch_installation_token()
                    self._installation_token = _InstallationToken(
                        token=token_str, expires_at=expires_at_mono
                    )
                return self._installation_token.token

        if self._pat:
            return self._pat

        # gh CLI fallback — resolve once and cache.
        with self._lock:
            if self._pat is None:
                self._pat = self._resolve_gh_cli_token()
        return self._pat

    def headers(self) -> dict[str, str]:
        """Return HTTP headers for a GitHub API request."""
        h: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _GH_API_VERSION,
        }
        token = self.get_token()
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h


# ---------------------------------------------------------------------------
# HTTP client with retries, timeouts, pagination, rate-limit handling
# ---------------------------------------------------------------------------

# Transient HTTP status codes that are worth retrying.
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class GitHubClient:
    """GitHub REST API client with centralised reliability features.

    Features:

    - Automatic retry with exponential back-off for transient failures.
    - Per-request timeout (``OOMPAH_GITHUB_API_TIMEOUT`` env var).
    - Transparent link-header pagination via :meth:`request_paginated`.
    - Rate-limit logging (remaining quota + reset time logged at DEBUG).
    - Rate-limit *block* (HTTP 429) handling: waits for
      ``Retry-After`` / ``X-RateLimit-Reset`` then retries.
    - ETag conditional-GET cache support via the ``etag`` / ``cached``
      parameters on :meth:`request`.
    - Response body and header redaction in log output.
    """

    def __init__(
        self,
        auth: GitHubAuth | None = None,
        *,
        base_url: str = _GH_API_BASE,
    ) -> None:
        self._auth = auth or GitHubAuth()
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=_timeout(), follow_redirects=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sleep(self, seconds: float) -> None:  # pragma: no cover — tested via mock
        """Sleep for *seconds*. Extracted so tests can monkeypatch."""
        time.sleep(seconds)

    def _backoff(self, attempt: int) -> float:
        """Return seconds to wait before attempt *attempt* (0-indexed)."""
        return min(_MAX_BACKOFF_S, (2 ** attempt) + 0.1 * attempt)

    def _rate_limit_wait(self, resp: httpx.Response) -> float:
        """Return the number of seconds to wait for a rate-limited response."""
        # Prefer Retry-After header (set for secondary rate limits).
        retry_after = resp.headers.get("retry-after")
        if retry_after:
            try:
                return max(float(retry_after), 1.0)
            except (TypeError, ValueError):
                pass
        # Fall back to X-RateLimit-Reset (primary rate limit).
        reset_ts = resp.headers.get("x-ratelimit-reset")
        if reset_ts:
            try:
                wait = float(reset_ts) - time.time()
                return max(wait + 1.0, 1.0)
            except (TypeError, ValueError):
                pass
        # Default: 60 seconds.
        return 60.0

    # ------------------------------------------------------------------
    # Core request method
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        etag: str | None = None,
        cached: Any = None,
        **kwargs: Any,
    ) -> tuple[Any, str | None]:
        """Make a GitHub API request with retry / rate-limit / ETag logic.

        Parameters
        ----------
        method:
            HTTP method string, e.g. ``"GET"`` or ``"POST"``.
        path:
            Path relative to the API base URL, e.g. ``"/repos/owner/repo/issues"``.
        etag:
            If provided, send as ``If-None-Match`` header.  A ``304 Not
            Modified`` response returns *(cached, etag)* unchanged.
        cached:
            The previously cached response body to return on 304.
        **kwargs:
            Extra keyword arguments forwarded to :meth:`httpx.Client.request`.

        Returns
        -------
        tuple[Any, str | None]
            ``(body, new_etag)`` where *body* is the parsed JSON (or *None*
            for 204/304), and *new_etag* is the ``ETag`` response header value
            if present.

        Raises
        ------
        TrackerError
            On non-retryable HTTP errors (4xx except 304/429) or when all
            retry attempts are exhausted.
        TrackerTimeoutError
            On request timeout.
        """
        url = f"{self._base_url}{path}" if path.startswith("/") else path
        headers = self._auth.headers()
        if etag:
            headers["If-None-Match"] = etag
        kwargs.setdefault("headers", {})
        kwargs["headers"].update(headers)

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                wait = self._backoff(attempt - 1)
                logger.debug(
                    "GitHub API retry %d/%d for %s %s (waiting %.1fs)",
                    attempt,
                    _MAX_RETRIES,
                    method,
                    url,
                    wait,
                )
                self._sleep(wait)

            try:
                resp = self._http.request(method, url, **kwargs)
            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "GitHub API request timed out (%s %s): %s",
                    method, _redact(url), exc,
                )
                continue
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning(
                    "GitHub API network error (%s %s): %s",
                    method, _redact(url), exc,
                )
                continue

            _log_rate_limits(resp)

            # ETag cache hit.
            if resp.status_code == 304:
                return cached, etag

            # No content.
            if resp.status_code == 204:
                new_etag = resp.headers.get("etag")
                return None, new_etag

            # Rate limit — wait and retry.
            if resp.status_code == 429:
                wait_s = self._rate_limit_wait(resp)
                logger.warning(
                    "GitHub API rate limit exceeded (%s %s); "
                    "waiting %.0f seconds before retry.",
                    method, url, wait_s,
                )
                self._sleep(wait_s)
                last_exc = TrackerError(
                    f"GitHub API rate limit exceeded for {method} {url}"
                )
                continue

            # Auth errors — not retryable.
            if resp.status_code == 401:
                raise TrackerError(
                    f"GitHub API authentication failed ({method} {url}). "
                    "Check OOMPAH_GITHUB_TOKEN, OOMPAH_GITHUB_APP_ID, or "
                    "run 'gh auth login'."
                )
            if resp.status_code == 403:
                body_snippet = resp.text[:200]
                raise TrackerError(
                    f"GitHub API access forbidden ({method} {url}): "
                    f"{body_snippet}"
                )

            # Other retryable server errors.
            if resp.status_code in _RETRYABLE_STATUS:
                last_exc = TrackerError(
                    f"GitHub API transient error {resp.status_code} "
                    f"({method} {url})"
                )
                logger.warning(
                    "GitHub API returned %s for %s %s (attempt %d/%d)",
                    resp.status_code, method, url, attempt + 1, _MAX_RETRIES + 1,
                )
                continue

            # Non-2xx, non-retryable.
            if not resp.is_success:
                raise TrackerError(
                    f"GitHub API error {resp.status_code} ({method} {url}): "
                    f"{resp.text[:400]}"
                )

            # Success.
            new_etag = resp.headers.get("etag")
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            return body, new_etag

        # All retries exhausted.
        if last_exc is not None and isinstance(last_exc, TrackerError):
            raise last_exc
        raise TrackerTimeoutError(
            f"GitHub API request failed after {_MAX_RETRIES} retries "
            f"({method} {url}): {last_exc}"
        )

    def get(self, path: str, **kwargs: Any) -> Any:
        """Convenience wrapper for GET requests; returns the response body."""
        body, _ = self.request("GET", path, **kwargs)
        return body

    def post(self, path: str, **kwargs: Any) -> Any:
        """Convenience wrapper for POST requests; returns the response body."""
        body, _ = self.request("POST", path, **kwargs)
        return body

    def patch(self, path: str, **kwargs: Any) -> Any:
        """Convenience wrapper for PATCH requests; returns the response body."""
        body, _ = self.request("PATCH", path, **kwargs)
        return body

    def delete(self, path: str, **kwargs: Any) -> Any:
        """Convenience wrapper for DELETE requests; returns the response body."""
        body, _ = self.request("DELETE", path, **kwargs)
        return body

    def request_paginated(
        self, path: str, *, params: dict[str, Any] | None = None, **kwargs: Any
    ) -> list[Any]:
        """Fetch all pages of a GitHub list endpoint.

        GitHub paginates with a ``Link: <url>; rel="next"`` header.
        This method follows ``next`` links until the last page and
        returns all items concatenated into a single list.

        Parameters
        ----------
        path:
            The first page's path or full URL.
        params:
            Query parameters to include on the first request.
        **kwargs:
            Extra keyword arguments forwarded to :meth:`request`.

        Returns
        -------
        list[Any]
            Aggregated list of all items across all pages.
        """
        if params:
            kwargs["params"] = params

        url: str | None = (
            f"{self._base_url}{path}" if path.startswith("/") else path
        )
        results: list[Any] = []
        while url:
            headers = self._auth.headers()
            kwargs_page = dict(kwargs)
            kwargs_page.setdefault("headers", {})
            kwargs_page["headers"].update(headers)

            try:
                resp = self._http.request("GET", url, **kwargs_page)
            except httpx.TimeoutException as exc:
                raise TrackerTimeoutError(
                    f"GitHub API paginated request timed out ({url}): {exc}"
                ) from exc
            except httpx.HTTPError as exc:
                raise TrackerError(
                    f"GitHub API paginated request failed ({url}): {exc}"
                ) from exc

            _log_rate_limits(resp)

            if resp.status_code == 401:
                raise TrackerError(
                    f"GitHub API authentication failed fetching page {url}. "
                    "Check OOMPAH_GITHUB_TOKEN or GitHub App credentials."
                )
            if resp.status_code == 403:
                raise TrackerError(
                    f"GitHub API access forbidden fetching page {url}: {resp.text[:200]}"
                )
            if resp.status_code == 429:
                wait_s = self._rate_limit_wait(resp)
                logger.warning(
                    "GitHub API rate limit during pagination (%s); waiting %.0fs.",
                    url, wait_s,
                )
                self._sleep(wait_s)
                # Retry the same page (do not advance URL).
                continue

            if not resp.is_success:
                raise TrackerError(
                    f"GitHub API error {resp.status_code} fetching page {url}: "
                    f"{resp.text[:400]}"
                )

            page_data = resp.json()
            if isinstance(page_data, list):
                results.extend(page_data)
            else:
                results.append(page_data)

            # Parse Link header for next page.
            url = _parse_next_link(resp.headers.get("link", ""))
            # Clear first-page params so they are not duplicated.
            kwargs.pop("params", None)

        return results


def _parse_next_link(link_header: str) -> str | None:
    """Extract the ``rel="next"`` URL from a GitHub ``Link`` header.

    Returns *None* when no next page exists.
    """
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part:
            m = re.match(r"<([^>]+)>", part)
            if m:
                return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Status encoding helpers
#
# oompah status is stored as a GitHub label with a ``oompah:status:``
# prefix, e.g. ``oompah:status:in-progress``.  This is the primary
# mechanism for GitHub-REST-backed deployments that do not (yet) have a
# GitHub Projects V2 custom field configured.
#
# When no status label is present on an issue, the adapter falls back to
# the GitHub built-in ``state`` field: ``open`` → "Open", ``closed`` →
# "Done".
#
# Priority is encoded as ``priority:N`` (e.g. ``priority:1``).
# Issue type is encoded as ``type:<kind>`` (e.g. ``type:bug``).
# Target branch and project ID are stored in a hidden HTML comment in the
# issue body::
#
#     <!-- oompah:metadata
#     {"project_id":"proj-123","target_branch":"main"}
#     -->
# ---------------------------------------------------------------------------

_STATUS_LABEL_PREFIX = "oompah:status:"

# Build a bidirectional mapping between label slugs and canonical statuses.
# "In Progress" → "in-progress", "Needs CI Fix" → "needs-ci-fix", etc.
_LABEL_SLUG_TO_STATUS: dict[str, str] = {
    s.lower().replace(" ", "-"): s for s in CANONICAL_STATUSES
}
_STATUS_TO_LABEL_SLUG: dict[str, str] = {
    v: k for k, v in _LABEL_SLUG_TO_STATUS.items()
}

# Sentinel used for sorting issues without timestamps.
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# Regex that matches the hidden oompah metadata block in an issue body.
_BODY_METADATA_RE = re.compile(
    r"<!--\s*oompah:metadata\s*\n(.*?)\n\s*-->",
    re.DOTALL,
)


def _status_to_label(status: str) -> str:
    """Return the GitHub label name that represents *status*.

    Example: ``"In Progress"`` → ``"oompah:status:in-progress"``.
    """
    slug = _STATUS_TO_LABEL_SLUG.get(status, status.lower().replace(" ", "-"))
    return f"{_STATUS_LABEL_PREFIX}{slug}"


def _label_to_status(label_name: str) -> str | None:
    """Extract the oompah status from a GitHub label name.

    Returns *None* when *label_name* is not an oompah status label.
    """
    if not label_name.startswith(_STATUS_LABEL_PREFIX):
        return None
    slug = label_name[len(_STATUS_LABEL_PREFIX):]
    return _LABEL_SLUG_TO_STATUS.get(slug)


def _extract_oompah_status(labels: list[dict[str, Any]], gh_state: str) -> str:
    """Derive the oompah status for a GitHub issue.

    Priority:

    1. ``oompah:status:*`` label — explicit oompah status.
    2. GitHub ``state`` field — ``open`` → ``"Open"``, ``closed`` → ``"Done"``.
    """
    for lbl in labels:
        name = lbl.get("name", "")
        status = _label_to_status(name)
        if status is not None:
            return status
    return "Open" if gh_state == "open" else "Done"


def _extract_priority(labels: list[dict[str, Any]]) -> int | None:
    """Extract numeric dispatch priority from a ``priority:N`` label."""
    for lbl in labels:
        name = lbl.get("name", "")
        if name.startswith("priority:"):
            try:
                return int(name[len("priority:"):])
            except (ValueError, TypeError):
                pass
    return None


def _extract_issue_type(labels: list[dict[str, Any]]) -> str:
    """Extract the issue type from a ``type:<kind>`` label.

    Defaults to ``"task"`` when no type label is present.
    """
    for lbl in labels:
        name = lbl.get("name", "")
        if name.startswith("type:"):
            kind = name[len("type:"):]
            if kind:
                return kind
    return "task"


def _parse_body_metadata(body: str | None) -> dict[str, Any]:
    """Extract the structured oompah metadata block from an issue body.

    Returns an empty dict when the body is *None* or contains no metadata
    block.
    """
    if not body:
        return {}
    m = _BODY_METADATA_RE.search(body)
    if not m:
        return {}
    try:
        return json.loads(m.group(1).strip())
    except (json.JSONDecodeError, Exception):
        return {}


def _gh_timestamp(ts: str | None) -> datetime | None:
    """Parse a GitHub ISO-8601 timestamp string to a timezone-aware datetime.

    Returns *None* when *ts* is empty or unparsable.
    """
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _gh_issue_to_issue(gh_issue: dict[str, Any], owner: str, repo: str) -> Issue:
    """Convert a GitHub REST API issue dict to a normalized oompah :class:`Issue`.

    Parameters
    ----------
    gh_issue:
        A single item from the ``GET /repos/{owner}/{repo}/issues`` response.
    owner:
        Repository owner (used to build the :class:`GitHubIdentifier`).
    repo:
        Repository name.

    Returns
    -------
    Issue
        Normalized issue record with all available fields populated.
    """
    number = int(gh_issue["number"])
    gh_id = GitHubIdentifier(owner=owner, repo=repo, number=number)

    labels_raw: list[dict[str, Any]] = gh_issue.get("labels") or []
    gh_state: str = gh_issue.get("state", "open")

    status = _extract_oompah_status(labels_raw, gh_state)
    priority = _extract_priority(labels_raw)
    issue_type = _extract_issue_type(labels_raw)

    # Collect user-facing labels (exclude oompah-internal prefixes).
    user_labels = [
        lbl["name"]
        for lbl in labels_raw
        if lbl.get("name")
        and not lbl["name"].startswith("oompah:")
        and not lbl["name"].startswith("priority:")
        and not lbl["name"].startswith("type:")
    ]

    body: str = gh_issue.get("body") or ""
    meta = _parse_body_metadata(body)
    target_branch: str | None = meta.get("target_branch") or None
    project_id: str | None = meta.get("project_id") or None

    # Description: issue body with metadata block stripped.
    description_text = _BODY_METADATA_RE.sub("", body).strip()
    description: str | None = description_text or None

    url: str | None = gh_issue.get("html_url") or None

    return Issue(
        id=str(gh_issue.get("id", number)),
        identifier=gh_id.canonical,
        title=gh_issue.get("title") or "",
        description=description,
        priority=priority,
        state=status,
        url=url,
        issue_type=issue_type,
        project_id=project_id,
        target_branch=target_branch,
        labels=user_labels,
        created_at=_gh_timestamp(gh_issue.get("created_at")),
        updated_at=_gh_timestamp(gh_issue.get("updated_at")),
        closed_at=_gh_timestamp(gh_issue.get("closed_at")),
        tracker_kind="github_issues",
        owner=owner,
        repo=repo,
        issue_number=str(number),
        display_identifier=gh_id.display,
        provider_url=url,
    )


# ---------------------------------------------------------------------------
# GitHubIssueTracker — TrackerProtocol adapter
# ---------------------------------------------------------------------------


class GitHubIssueTracker:
    """GitHub Issues adapter implementing :class:`~oompah.tracker.TrackerProtocol`.

    This adapter connects oompah to a central GitHub Issues repository used
    as the task hub (e.g. ``lesserevil/oompah-tasks``).

    The class is intentionally minimal in this initial implementation (TASK-458.1):
    it establishes auth, the HTTP client layer, and the full protocol skeleton
    so downstream tasks (TASK-458.2 through TASK-458.7) can implement the
    individual operations without architectural rework.

    Parameters
    ----------
    owner:
        GitHub repository owner (user or organisation).
    repo:
        GitHub repository name.
    active_states:
        oompah status names considered active for dispatch.
    terminal_states:
        oompah status names considered terminal (closed).
    auth:
        :class:`GitHubAuth` instance.  When *None*, one is constructed
        from environment variables automatically.
    """

    def __init__(
        self,
        *,
        owner: str,
        repo: str,
        active_states: list[str],
        terminal_states: list[str],
        auth: GitHubAuth | None = None,
        cwd: str | None = None,  # ignored — accepted for factory compat
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.active_states = list(active_states)
        self.terminal_states = list(terminal_states)
        self._auth = auth or GitHubAuth()
        self._client = GitHubClient(auth=self._auth)
        # In-memory ETag cache keyed by path.
        self._etag_cache: dict[str, tuple[str, Any]] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _repo_path(self, suffix: str = "") -> str:
        return f"/repos/{self.owner}/{self.repo}{suffix}"

    def _issues_path(self, suffix: str = "") -> str:
        return self._repo_path(f"/issues{suffix}")

    def parse_identifier(self, s: str) -> GitHubIdentifier:
        """Parse *s* as a fully-qualified GitHub issue identifier.

        Thin wrapper around the module-level :func:`parse_github_identifier`
        that raises :class:`~oompah.tracker.TrackerError` (rather than
        :class:`GitHubIdentifierError`) so callers using the tracker
        protocol receive a consistent error type.

        Raises
        ------
        TrackerError
            When *s* is not a valid fully-qualified identifier.
        """
        try:
            return parse_github_identifier(s)
        except GitHubIdentifierError as exc:
            raise TrackerError(str(exc)) from exc

    def identifier_for_number(self, number: int) -> GitHubIdentifier:
        """Return a :class:`GitHubIdentifier` for a numeric issue number on this tracker."""
        return GitHubIdentifier(owner=self.owner, repo=self.repo, number=number)

    # ------------------------------------------------------------------
    # Issue reads
    # ------------------------------------------------------------------

    def fetch_candidate_issues(self) -> list[Issue]:
        """Return issues in active (dispatchable) states, sorted for dispatch.

        Fetches all open GitHub issues and filters to those whose oompah
        status (derived from ``oompah:status:*`` labels or GitHub state)
        is in :attr:`active_states`.

        Results are sorted by priority (ascending, ``None`` last) then by
        creation time (oldest first) so the orchestrator's dispatch loop
        receives a stable, deterministic ordering.
        """
        raw = self._client.request_paginated(
            self._issues_path(),
            params={"state": "open", "per_page": 100},
        )
        issues = [_gh_issue_to_issue(gh, self.owner, self.repo) for gh in raw]
        active_set = set(self.active_states)
        candidates = [iss for iss in issues if iss.state in active_set]
        candidates.sort(
            key=lambda i: (
                i.priority if i.priority is not None else 999,
                i.created_at or _EPOCH,
            )
        )
        return candidates

    def fetch_all_issues(self) -> list[Issue]:
        """Return all issues regardless of state (open and closed)."""
        raw = self._client.request_paginated(
            self._issues_path(),
            params={"state": "all", "per_page": 100},
        )
        return [_gh_issue_to_issue(gh, self.owner, self.repo) for gh in raw]

    def fetch_all_issues_enriched(self) -> list[Issue]:
        """Return all issues with full detail (may make extra API calls).

        For GitHub, the list endpoint already returns the full issue body,
        labels, and timestamps, so this is equivalent to :meth:`fetch_all_issues`.
        """
        return self.fetch_all_issues()

    def fetch_issue_detail(self, identifier: str) -> Issue | None:
        """Return a single issue by identifier, or *None* if not found.

        Parameters
        ----------
        identifier:
            Fully-qualified GitHub identifier, e.g.
            ``"lesserevil/oompah-tasks#42"``.

        Returns
        -------
        Issue | None
            The normalized issue record, or *None* when the issue does not
            exist (HTTP 404).

        Raises
        ------
        TrackerError
            On non-404 API errors.
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            return None

        try:
            raw, _ = self._client.request(
                "GET", self._issues_path(f"/{gh_id.number}")
            )
            if raw is None:
                return None
            return _gh_issue_to_issue(raw, self.owner, self.repo)
        except TrackerError as exc:
            if "404" in str(exc):
                return None
            raise

    def fetch_children(self, epic_id: str) -> list[Issue]:
        """Return child issues that reference the given parent identifier.

        Attempts the GitHub sub-issues REST endpoint first.  When that
        returns a 404 (the endpoint is not yet generally available),
        falls back to searching for issues labelled
        ``parent:<epic_number>``.
        """
        try:
            gh_id = self.parse_identifier(epic_id)
        except TrackerError:
            return []

        # Try the sub-issues endpoint (newer GitHub API).
        try:
            raw = self._client.request_paginated(
                self._issues_path(f"/{gh_id.number}/sub_issues"),
                params={"per_page": 100},
            )
            return [_gh_issue_to_issue(gh, self.owner, self.repo) for gh in raw]
        except TrackerError as exc:
            if "404" not in str(exc):
                raise

        # Fallback: label-based parent lookup.
        parent_label = f"parent:{gh_id.number}"
        try:
            raw = self._client.request_paginated(
                self._issues_path(),
                params={"state": "all", "labels": parent_label, "per_page": 100},
            )
            return [_gh_issue_to_issue(gh, self.owner, self.repo) for gh in raw]
        except TrackerError:
            return []

    def fetch_comments(self, identifier: str) -> list[dict]:
        """Return all comments on an issue as a list of raw GitHub dicts."""
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            return []

        try:
            return self._client.request_paginated(
                self._repo_path(f"/issues/{gh_id.number}/comments"),
                params={"per_page": 100},
            )
        except TrackerError:
            return []

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        """Return all issues whose oompah state matches any of *state_names*.

        Optimises the GitHub API query by requesting only ``open`` issues
        when all requested states are non-terminal, only ``closed`` when
        all are terminal, or ``all`` for a mixed set.
        """
        if not state_names:
            return []

        terminal_set = set(self.terminal_states)
        state_set = set(state_names)
        needs_open = bool(state_set - terminal_set)
        needs_closed = bool(state_set & terminal_set)

        if needs_open and needs_closed:
            gh_state = "all"
        elif needs_closed:
            gh_state = "closed"
        else:
            gh_state = "open"

        raw = self._client.request_paginated(
            self._issues_path(),
            params={"state": gh_state, "per_page": 100},
        )
        issues = [_gh_issue_to_issue(gh, self.owner, self.repo) for gh in raw]
        return [iss for iss in issues if iss.state in state_set]

    def fetch_issues_by_labels(
        self,
        labels: list[str],
        *,
        states: list[str] | None = None,
    ) -> list[Issue]:
        """Return issues that carry *all* of the given labels.

        Optionally filter the results to only those issues whose oompah
        state is in *states*.
        """
        if not labels:
            return []

        if states is not None:
            terminal_set = set(self.terminal_states)
            state_set = set(states)
            needs_open = bool(state_set - terminal_set)
            needs_closed = bool(state_set & terminal_set)
            if needs_open and needs_closed:
                gh_state = "all"
            elif needs_closed:
                gh_state = "closed"
            else:
                gh_state = "open"
        else:
            gh_state = "all"

        raw = self._client.request_paginated(
            self._issues_path(),
            params={
                "state": gh_state,
                "labels": ",".join(labels),
                "per_page": 100,
            },
        )
        issues = [_gh_issue_to_issue(gh, self.owner, self.repo) for gh in raw]
        if states is not None:
            state_set = set(states)
            issues = [iss for iss in issues if iss.state in state_set]
        return issues

    def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        """Return current state snapshots for the given identifiers.

        Each identifier is fetched individually.  Invalid or missing
        identifiers are silently skipped so a batch operation can return
        partial results.
        """
        if not issue_ids:
            return []

        results: list[Issue] = []
        for issue_id in issue_ids:
            # Accept fully-qualified identifiers or bare issue numbers.
            try:
                gh_id = self.parse_identifier(issue_id)
            except TrackerError:
                try:
                    number = int(issue_id)
                    gh_id = self.identifier_for_number(number)
                except (ValueError, TypeError):
                    continue

            try:
                raw, _ = self._client.request(
                    "GET", self._issues_path(f"/{gh_id.number}")
                )
                if raw is not None:
                    results.append(_gh_issue_to_issue(raw, self.owner, self.repo))
            except TrackerError:
                continue

        return results

    def fetch_memories(self) -> dict[str, str]:
        """Return backend-specific memory key/value pairs (may be empty)."""
        return {}

    # ------------------------------------------------------------------
    # Issue mutations
    # ------------------------------------------------------------------

    def create_issue(
        self,
        title: str,
        issue_type: str = "task",
        description: str | None = None,
        priority: int | None = None,
        initial_status: str | None = None,
        labels: list[str] | None = None,
        parent: str | None = None,
    ) -> Issue:
        """Create a new GitHub issue and return the normalized Issue record.

        The initial status is encoded as an ``oompah:status:*`` label.
        Priority is encoded as a ``priority:N`` label.  Issue type (when
        non-default) is encoded as a ``type:<kind>`` label.  User-supplied
        labels are appended verbatim.

        Returns
        -------
        Issue
            Normalized issue record with fully-qualified GitHub identifier
            (``owner/repo#number``) and issue URL populated.
        """
        all_labels: list[str] = []

        # Status label — defaults to the first active state.
        status = initial_status or self._active_status()
        all_labels.append(_status_to_label(status))

        # Priority label.
        if priority is not None:
            all_labels.append(f"priority:{int(priority)}")

        # Issue type label (omit default "task" to keep issues uncluttered).
        if issue_type and issue_type != "task":
            all_labels.append(f"type:{issue_type}")

        # User-supplied labels (skip duplicates already added above).
        for lbl in (labels or []):
            if lbl not in all_labels:
                all_labels.append(lbl)

        # Build the issue body.
        body = self._build_issue_body(description)

        payload: dict[str, Any] = {"title": title}
        if body:
            payload["body"] = body
        if all_labels:
            payload["labels"] = all_labels

        gh_issue = self._client.post(self._issues_path(), json=payload)
        if not isinstance(gh_issue, dict):
            raise TrackerError(
                "GitHub API returned unexpected response for issue creation"
            )
        return _gh_issue_to_issue(gh_issue, self.owner, self.repo)

    def update_issue(self, identifier: str, **fields: str) -> None:
        """Update one or more fields on an existing GitHub issue.

        Supported field names (use ``_`` or ``-`` as separator):

        ``title``
            Issue title.
        ``description`` / ``desc``
            Issue body text.  The oompah metadata block is preserved.
        ``status``
            oompah status string.  Syncs the ``oompah:status:*`` label and
            sets the GitHub ``state`` (open/closed) accordingly.
        ``priority``
            Numeric dispatch priority.  Syncs the ``priority:N`` label.
        ``add_label`` / ``add-label``
            Add a single label by name.
        ``remove_label`` / ``remove-label``
            Remove a single label by name (no-op when absent).

        All unrecognised field names are silently ignored.
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            raise

        patch_payload: dict[str, Any] = {}
        label_ops: list[tuple[str, str]] = []
        status_to_set: str | None = None
        priority_to_set: Any = None

        # Check whether we need to fetch the full body for a description update.
        needs_body_fetch = any(
            k.replace("_", "-") in ("description", "desc") for k in fields
        )
        current_full_body: str = ""
        if needs_body_fetch:
            try:
                raw, _ = self._client.request(
                    "GET", self._issues_path(f"/{gh_id.number}")
                )
                current_full_body = (raw or {}).get("body") or ""
            except TrackerError:
                current_full_body = ""

        for key, value in fields.items():
            key_norm = key.replace("_", "-")
            if key_norm == "title":
                patch_payload["title"] = str(value)
            elif key_norm in ("description", "desc"):
                patch_payload["body"] = self._update_body_description(
                    current_full_body, str(value)
                )
            elif key_norm == "status":
                status_to_set = str(value)
            elif key_norm == "priority":
                priority_to_set = value
            elif key_norm == "add-label":
                label_ops.append(("add", str(value)))
            elif key_norm == "remove-label":
                label_ops.append(("remove", str(value)))
            else:
                logger.debug(
                    "GitHub update_issue ignoring unsupported field %s", key
                )

        # Status change: swap the oompah:status:* label and sync GitHub state.
        if status_to_set is not None:
            self._set_status_label(gh_id.number, status_to_set)
            if status_to_set in self.terminal_states:
                patch_payload["state"] = "closed"
            else:
                patch_payload.setdefault("state", "open")

        # Priority label swap.
        if priority_to_set is not None:
            self._set_priority_label(gh_id.number, priority_to_set)

        # Issue a single PATCH for title/body/state changes.
        if patch_payload:
            self._client.patch(
                self._issues_path(f"/{gh_id.number}"),
                json=patch_payload,
            )

        # Label add/remove operations.
        for op, label in label_ops:
            if op == "add":
                self.add_label(identifier, label)
            else:
                self.remove_label(identifier, label)

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        """Move an issue to the first configured terminal state.

        Sets the ``oompah:status:*`` label to the terminal status, closes
        the GitHub issue (``state: "closed"``), and optionally appends a
        comment with the close reason.
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            raise

        terminal = self._terminal_status()
        self._set_status_label(gh_id.number, terminal)
        self._client.patch(
            self._issues_path(f"/{gh_id.number}"),
            json={"state": "closed"},
        )
        if reason:
            self.add_comment(identifier, reason)

    def reopen_issue(self, identifier: str) -> None:
        """Move an issue back to the first configured active state.

        Sets the ``oompah:status:*`` label to the active status and
        reopens the GitHub issue (``state: "open"``).
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            raise

        active = self._active_status()
        self._set_status_label(gh_id.number, active)
        self._client.patch(
            self._issues_path(f"/{gh_id.number}"),
            json={"state": "open"},
        )

    def archive_issue(self, identifier: str) -> None:
        """Archive an issue.

        Sets ``oompah:status:archived`` label and closes the GitHub issue.
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            raise

        self._set_status_label(gh_id.number, "Archived")
        self._client.patch(
            self._issues_path(f"/{gh_id.number}"),
            json={"state": "closed"},
        )

    def mark_needs_human(
        self, identifier: str, comment: str, author: str = "oompah"
    ) -> None:
        """Move an issue to Needs Human and post the actionable comment."""
        self.update_issue(identifier, status=NEEDS_HUMAN)
        self.add_comment(identifier, comment, author=author)

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def add_comment(self, identifier: str, text: str, author: str = "oompah") -> dict:
        """Append a comment to a GitHub issue and return the comment dict.

        The comment body is prefixed with ``**{author}**: `` so that
        authorship is visible in the GitHub UI (GitHub REST comments are
        always posted under the authenticated bot account).

        Returns
        -------
        dict
            The raw GitHub comment object returned by the API.
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            raise

        comment_text = str(text).strip()
        if not comment_text:
            raise TrackerError("Comment text is required")

        body = f"**{author}**: {comment_text}"
        result = self._client.post(
            self._repo_path(f"/issues/{gh_id.number}/comments"),
            json={"body": body},
        )
        if isinstance(result, dict):
            return result
        return {"body": body}

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def add_label(self, identifier: str, label: str) -> None:
        """Add a label to a GitHub issue.

        The label must already exist in the repository.  If the label is
        already applied to the issue, GitHub silently ignores the
        duplicate.
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            raise

        self._client.post(
            self._issues_path(f"/{gh_id.number}/labels"),
            json={"labels": [label]},
        )

    def remove_label(self, identifier: str, label: str) -> None:
        """Remove a label from a GitHub issue (no-op if label is absent)."""
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            raise

        try:
            self._client.delete(
                self._issues_path(f"/{gh_id.number}/labels/{quote(label, safe='')}"),
            )
        except TrackerError as exc:
            if "404" in str(exc):
                return  # Label not on issue — that is fine.
            raise

    # ------------------------------------------------------------------
    # Hierarchy and dependencies
    # ------------------------------------------------------------------

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        """Link a child issue to a parent issue."""
        raise NotImplementedError(
            "GitHubIssueTracker.add_parent_child is implemented in TASK-458.6"
        )

    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        """Record that blocked_id depends on blocker_id."""
        raise NotImplementedError(
            "GitHubIssueTracker.add_dependency is implemented in TASK-458.6"
        )

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    def fetch_attachments(self, identifier: str) -> list[dict]:
        """Return rich attachment records stored in the issue body metadata.

        Attachment records are read from the ``attachments`` key inside the
        hidden ``<!-- oompah:metadata … -->`` block in the issue body.  An
        empty list is returned when no block is present or when the
        ``attachments`` key is absent.
        """
        meta = self.get_metadata(identifier)
        attachments = meta.get("oompah.attachments")
        if not isinstance(attachments, list):
            return []
        return [a for a in attachments if isinstance(a, dict)]

    def set_attachments(
        self,
        identifier: str,
        attachments: list[dict],
        *,
        project_root: str | None = None,
    ) -> None:
        """Replace the attachment records stored in the issue body metadata.

        Attachments are persisted in the hidden oompah metadata block in the
        issue body so that the caller does not need to know whether this
        deployment uses GitHub issue fields or body metadata.

        Parameters
        ----------
        identifier:
            Fully-qualified GitHub issue identifier.
        attachments:
            Replacement list of attachment dicts.
        project_root:
            Accepted for protocol compatibility; ignored here because GitHub
            issues do not have a local file store.
        """
        self.set_metadata_field(identifier, "oompah.attachments", list(attachments))

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self, identifier: str) -> dict[str, object]:
        """Return oompah-owned metadata fields for an issue.

        Reads the hidden ``<!-- oompah:metadata … -->`` block from the issue
        body.  All keys are returned with an ``oompah.`` prefix so callers
        receive a namespace-consistent mapping regardless of whether the
        underlying storage is body metadata or GitHub issue fields.

        Returns an empty dict when the issue cannot be found or when the
        body contains no metadata block.

        Parameters
        ----------
        identifier:
            Fully-qualified GitHub issue identifier.
        """
        gh_id = self.parse_identifier(identifier)
        try:
            raw, _ = self._client.request(
                "GET", self._issues_path(f"/{gh_id.number}")
            )
        except TrackerError:
            return {}
        body: str = (raw or {}).get("body") or ""
        meta = _parse_body_metadata(body)
        return {f"oompah.{k}": v for k, v in meta.items()}

    def set_metadata_field(self, identifier: str, key: str, value: object) -> None:
        """Set one oompah-owned metadata field on an issue.

        The value is written into the hidden ``<!-- oompah:metadata … -->``
        block in the issue body.  The ``oompah.`` prefix is stripped before
        writing so body JSON keys remain compact (e.g. ``oompah.target_branch``
        is stored as ``target_branch``).

        The description portion of the body is preserved unchanged.

        Parameters
        ----------
        identifier:
            Fully-qualified GitHub issue identifier.
        key:
            Metadata key — must start with ``oompah.``.
        value:
            JSON-serialisable value to store.

        Raises
        ------
        TrackerError
            When *key* does not start with ``oompah.``, or when the issue
            cannot be found.
        """
        if not key.startswith("oompah."):
            raise TrackerError(
                f"GitHub metadata key must start with 'oompah.': {key!r}"
            )
        body_key = key[len("oompah."):]
        gh_id = self.parse_identifier(identifier)
        try:
            raw, _ = self._client.request(
                "GET", self._issues_path(f"/{gh_id.number}")
            )
        except TrackerError as exc:
            raise TrackerError(
                f"Cannot set metadata: issue not found: {identifier}"
            ) from exc
        current_body: str = (raw or {}).get("body") or ""
        meta = _parse_body_metadata(current_body)
        meta[body_key] = value
        new_body = self._update_body_metadata(current_body, meta)
        self._client.patch(
            self._issues_path(f"/{gh_id.number}"),
            json={"body": new_body},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _active_status(self) -> str:
        """Return the first configured active status, defaulting to ``"Open"``."""
        if self.active_states:
            return self.active_states[0]
        return "Open"

    def _terminal_status(self) -> str:
        """Return the first configured terminal status, defaulting to ``"Done"``."""
        if self.terminal_states:
            return self.terminal_states[0]
        return "Done"

    def _build_issue_body(
        self,
        description: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Build a GitHub issue body from description text and optional metadata.

        The metadata block is appended as a hidden HTML comment::

            <!-- oompah:metadata
            {"key": "value"}
            -->

        This follows the format expected by :func:`_parse_body_metadata`.
        """
        parts: list[str] = []
        if description:
            parts.append(description.strip())
        if metadata:
            meta_json = json.dumps(metadata)
            parts.append(f"<!-- oompah:metadata\n{meta_json}\n-->")
        return "\n\n".join(parts)

    def _update_body_description(
        self,
        current_body: str,
        new_description: str,
    ) -> str:
        """Replace the description part of an issue body while preserving the metadata block.

        Parameters
        ----------
        current_body:
            The full current issue body (may contain an oompah metadata block).
        new_description:
            Replacement description text.

        Returns
        -------
        str
            New body with the description replaced and the metadata block
            preserved at the end (if one was present).
        """
        meta_match = _BODY_METADATA_RE.search(current_body)
        meta_block = meta_match.group(0) if meta_match else None
        new_body = new_description.strip()
        if meta_block:
            new_body = f"{new_body}\n\n{meta_block}"
        return new_body

    def _update_body_metadata(
        self,
        current_body: str,
        meta: dict[str, Any],
    ) -> str:
        """Replace or insert the hidden oompah metadata block in a GitHub issue body.

        The description portion of the body (everything before the existing
        metadata block, or the entire body when no block is present) is
        preserved unchanged.  The metadata block itself is rebuilt from *meta*.

        Parameters
        ----------
        current_body:
            The full current issue body text.
        meta:
            Complete metadata dict to embed.  An empty dict removes the block.

        Returns
        -------
        str
            Updated body with the metadata block replaced (or removed when
            *meta* is empty).
        """
        stripped = _BODY_METADATA_RE.sub("", current_body).strip()
        if not meta:
            return stripped
        meta_json = json.dumps(meta)
        meta_block = f"<!-- oompah:metadata\n{meta_json}\n-->"
        if stripped:
            return f"{stripped}\n\n{meta_block}"
        return meta_block

    def _get_issue_label_names(self, number: int) -> list[str]:
        """Return the list of label names currently applied to an issue."""
        try:
            raw = self._client.get(self._issues_path(f"/{number}/labels"))
            return [
                lbl["name"]
                for lbl in (raw or [])
                if isinstance(lbl, dict) and lbl.get("name")
            ]
        except TrackerError:
            return []

    def _set_status_label(self, number: int, status: str) -> None:
        """Atomically swap the ``oompah:status:*`` label on an issue.

        Removes all existing ``oompah:status:*`` labels, then adds the
        label for *status*.  Both operations are best-effort: errors during
        the remove step are suppressed so that the add step can still
        succeed (e.g. when the label does not yet exist on the issue).
        """
        current_labels = self._get_issue_label_names(number)
        # Remove any existing status labels.
        for name in current_labels:
            if name.startswith(_STATUS_LABEL_PREFIX):
                try:
                    self._client.delete(
                        self._issues_path(
                            f"/{number}/labels/{quote(name, safe='')}"
                        )
                    )
                except TrackerError:
                    pass
        # Add the new status label.
        new_label = _status_to_label(status)
        self._client.post(
            self._issues_path(f"/{number}/labels"),
            json={"labels": [new_label]},
        )

    def _set_priority_label(self, number: int, priority: Any) -> None:
        """Atomically swap the ``priority:N`` label on an issue.

        Removes all existing ``priority:*`` labels, then adds
        ``priority:{int(priority)}`` when *priority* is not *None* and
        can be coerced to an integer.
        """
        current_labels = self._get_issue_label_names(number)
        for name in current_labels:
            if name.startswith("priority:"):
                try:
                    self._client.delete(
                        self._issues_path(
                            f"/{number}/labels/{quote(name, safe='')}"
                        )
                    )
                except TrackerError:
                    pass
        if priority is not None:
            try:
                pri_int = int(priority)
            except (ValueError, TypeError):
                logger.debug(
                    "GitHub _set_priority_label: cannot coerce %r to int, skipping",
                    priority,
                )
                return
            self._client.post(
                self._issues_path(f"/{number}/labels"),
                json={"labels": [f"priority:{pri_int}"]},
            )

    def is_archived(self, issue: Issue) -> bool:
        """Return True when the issue should be considered archived."""
        return issue.state in ("Archived",)

    def invalidate_read_cache(self) -> None:
        """Invalidate any cached reads so the next fetch returns fresh data."""
        self._etag_cache.clear()


# ---------------------------------------------------------------------------
# Factory function for ADAPTER_REGISTRY
# ---------------------------------------------------------------------------


def _github_issues_factory(
    *,
    active_states: list[str],
    terminal_states: list[str],
    cwd: str | None = None,
    **kwargs: Any,
) -> GitHubIssueTracker:
    """Factory function registered in :data:`~oompah.tracker.ADAPTER_REGISTRY`.

    Reads configuration from environment variables:

    - ``OOMPAH_GITHUB_TRACKER_OWNER`` — repository owner (required).
    - ``OOMPAH_GITHUB_TRACKER_REPO`` — repository name (required).

    Raises :class:`~oompah.tracker.TrackerError` when the required env
    vars are missing.
    """
    owner = os.environ.get("OOMPAH_GITHUB_TRACKER_OWNER", "")
    repo = os.environ.get("OOMPAH_GITHUB_TRACKER_REPO", "")
    if not owner or not repo:
        raise TrackerError(
            "GitHub Issues tracker requires OOMPAH_GITHUB_TRACKER_OWNER and "
            "OOMPAH_GITHUB_TRACKER_REPO environment variables."
        )
    return GitHubIssueTracker(
        owner=owner,
        repo=repo,
        active_states=active_states,
        terminal_states=terminal_states,
        cwd=cwd,
    )
