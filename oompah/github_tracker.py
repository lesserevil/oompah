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
from oompah.statuses import (
    ARCHIVED,
    CANONICAL_STATUSES,
    DONE,
    MERGED,
    NEEDS_HUMAN,
    PROPOSED,
    canonicalize_status,
    status_key,
)
from oompah.tracker import (
    TrackerAuthError,
    TrackerError,
    TrackerTimeoutError,
    normalize_priority_int,
    validate_needs_human_comment,
)

logger = logging.getLogger(__name__)


def _priority_label_value(priority: Any) -> int | None:
    """Return the numeric value for a GitHub ``priority:N`` label."""
    return normalize_priority_int(priority)

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
        "tracker_owner": gh_id.owner,
        "tracker_repo": gh_id.repo,
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
                raise TrackerAuthError(
                    f"GitHub API authentication failed ({method} {url}). "
                    "Check OOMPAH_GITHUB_TOKEN, OOMPAH_GITHUB_APP_ID, or "
                    "run 'gh auth login'."
                )
            if resp.status_code == 403:
                body_snippet = resp.text[:200]
                raise TrackerAuthError(
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
                raise TrackerAuthError(
                    f"GitHub API authentication failed fetching page {url}. "
                    "Check OOMPAH_GITHUB_TOKEN or GitHub App credentials."
                )
            if resp.status_code == 403:
                raise TrackerAuthError(
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
# the GitHub built-in ``state`` field: ``open`` → "Proposed", ``closed`` →
# "Archived", then backfills the corresponding ``oompah:status:*`` label.
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

# Regex for parsing oompah comment bodies: "**author**: text"
_COMMENT_BODY_RE = re.compile(r"^\*\*([^*]+)\*\*:\s*(.*)", re.DOTALL)


def _parse_comment_body(body: str, user_login: str | None = None) -> tuple[str, str]:
    """Extract (author, text) from a GitHub comment body.

    oompah comments are formatted as ``**author**: text``.  When the body
    does not match this pattern, the GitHub user login is used as the
    author and the full body as the text.
    """
    m = _COMMENT_BODY_RE.match(body)
    if m:
        return m.group(1), m.group(2).strip()
    return user_login or "unknown", body

# Build a bidirectional mapping between label slugs and canonical statuses.
# "In Progress" → "in-progress", "Needs CI Fix" → "needs-ci-fix", etc.
_LABEL_SLUG_TO_STATUS: dict[str, str] = {
    s.lower().replace(" ", "-"): s for s in CANONICAL_STATUSES
}
_STATUS_TO_LABEL_SLUG: dict[str, str] = {
    v: k for k, v in _LABEL_SLUG_TO_STATUS.items()
}

# GitHub's native issue state has only open/closed. Oompah's ``Done`` means
# implementation work is finished and waiting for review/merge, so it must
# stay open. Only statuses that are truly terminal in GitHub itself close the
# issue, and externally closed issues must resolve to one of these terminal
# statuses.
_GITHUB_CLOSED_STATUS_KEYS = frozenset({
    status_key(MERGED),
    status_key(ARCHIVED),
})
_GITHUB_ALL_QUERY_STATUS_KEYS = frozenset({
    # Done should be GitHub-open going forward, but older oompah versions
    # closed Done issues. Query both states so reconciliation can repair them.
    status_key(DONE),
})

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


def _github_fallback_status(gh_state: str) -> str:
    """Return the oompah status for a GitHub issue with no status label.

    Open unlabeled issues default to ``Proposed`` (the intake gate) rather
    than ``Backlog``, so newly-imported external issues are visible in the
    intake view before being triaged.  Closed unlabeled issues default to
    ``Archived``.
    """
    return ARCHIVED if gh_state == "closed" else PROPOSED


def _status_closes_github_issue(status: str | None) -> bool:
    return status_key(status) in _GITHUB_CLOSED_STATUS_KEYS


def _github_issue_state_for_status(status: str | None) -> str:
    return "closed" if _status_closes_github_issue(status) else "open"


def _github_query_state_for_statuses(statuses: set[str]) -> str:
    query_states: set[str] = set()
    for status in statuses:
        key = status_key(status)
        if key in _GITHUB_ALL_QUERY_STATUS_KEYS:
            query_states.add("all")
        elif key in _GITHUB_CLOSED_STATUS_KEYS:
            query_states.add("closed")
        else:
            query_states.add("open")
    if "all" in query_states or len(query_states) > 1:
        return "all"
    return next(iter(query_states), "open")


def _extract_oompah_status(
    labels: list[dict[str, Any]], gh_state: str
) -> str:
    """Derive the oompah status for a GitHub issue.

    Priority:

    1. GitHub ``closed`` state forces ``Archived`` unless the explicit
       oompah status is already ``Merged`` or ``Archived``.
    2. ``oompah:status:*`` label — explicit oompah status.
    3. GitHub ``state`` field — unlabeled ``open`` issues are treated as
       ``"Proposed"``; unlabeled ``closed`` issues become ``"Archived"``.
    """
    for lbl in labels:
        name = lbl.get("name", "")
        status = _label_to_status(name)
        if status is not None:
            if (
                str(gh_state).lower() == "closed"
                and status_key(status) not in _GITHUB_CLOSED_STATUS_KEYS
            ):
                return ARCHIVED
            return status
    return _github_fallback_status(gh_state)


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


def _extract_issue_type(
    labels: list[dict[str, Any]],
    title: str | None = None,
) -> str:
    """Extract the issue type from a ``type:<kind>`` label.

    Defaults to ``"task"`` when no type label is present.
    """
    for lbl in labels:
        name = lbl.get("name", "")
        if name.startswith("type:"):
            kind = name[len("type:"):]
            if kind:
                return kind
    if str(title or "").strip().lower().startswith("epic:"):
        return "epic"
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


def _extract_parent_from_labels(labels: list[dict[str, Any]]) -> str | None:
    """Extract parent issue number from parent:<number> label."""
    for lbl in labels:
        name = lbl.get("name", "")
        if name.startswith("parent:"):
            return name[len("parent:"):]
    return None


def _extract_parent_from_body(body: str | None) -> str | None:
    """Extract parent issue number from a leading ``Parent:`` body line."""
    if not body:
        return None
    for match in re.finditer(r"(?im)^\s*Parent\s*:\s*(?P<ref>\S+)\s*$", body):
        ref = match.group("ref").strip()
        if ref.isdigit():
            return ref
        if ref.startswith("#") and ref[1:].isdigit():
            return ref[1:]
        m = re.match(r"^[^/\s]+/[^#\s]+#(?P<number>\d+)$", ref)
        if m:
            return m.group("number")
        m = re.match(
            r"^https://github\.com/[^/\s]+/[^/\s]+/issues/(?P<number>\d+)"
            r"(?:[?#].*)?$",
            ref,
        )
        if m:
            return m.group("number")
    return None


def _extract_dependencies_from_labels(labels: list[dict[str, Any]]) -> list[str]:
    """Extract dependency issue numbers from depends-on:<number> labels."""
    deps = []
    for lbl in labels:
        name = lbl.get("name", "")
        if name.startswith("depends-on:"):
            deps.append(name[len("depends-on:"):])
    return deps


def _extract_issue_number(issue: Any) -> int | None:
    """Extract the numeric issue number from an :class:`~oompah.models.Issue`.

    Uses the ``identifier`` string (e.g. ``"org/repo#42"``) or the
    ``tracker_issue_id`` field when present.  Returns ``None`` when the
    number cannot be determined.
    """
    # Try tracker_issue_id first (set for GitHub-backed issues).
    tid = getattr(issue, "tracker_issue_id", None)
    if tid:
        try:
            return int(tid)
        except (TypeError, ValueError):
            pass
    # Fall back to parsing the identifier string.
    identifier = getattr(issue, "identifier", "") or ""
    # identifier has the form "owner/repo#number" or "owner/repo/number".
    for sep in ("#", "/"):
        if sep in identifier:
            tail = identifier.rsplit(sep, 1)[-1]
            try:
                return int(tail)
            except (TypeError, ValueError):
                pass
    return None


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
    body: str = gh_issue.get("body") or ""
    issue_type = _extract_issue_type(labels_raw, gh_issue.get("title"))

    # Extract parent from parent:<number> label (fallback for sub-issues API).
    parent_number = _extract_parent_from_labels(labels_raw) or _extract_parent_from_body(body)
    parent_id: str | None = None
    if parent_number and parent_number != str(number):
        parent_id = f"{owner}/{repo}#{parent_number}"

    # Extract dependencies from depends-on:<number> labels (fallback for dependencies API).
    dep_numbers = _extract_dependencies_from_labels(labels_raw)
    blocked_by = [
        BlockerRef(id=dep, identifier=f"{owner}/{repo}#{dep}")
        for dep in dep_numbers
    ]

    # Collect user-facing labels (exclude oompah-internal prefixes).
    user_labels = [
        lbl["name"]
        for lbl in labels_raw
        if lbl.get("name")
        and not lbl["name"].startswith("oompah:")
        and not lbl["name"].startswith("priority:")
        and not lbl["name"].startswith("type:")
        and not lbl["name"].startswith("parent:")
        and not lbl["name"].startswith("depends-on:")
    ]

    meta = _parse_body_metadata(body)
    target_branch: str | None = (
        meta.get("target_branch") or meta.get("oompah.target_branch") or None
    )
    project_id: str | None = meta.get("project_id") or None
    # Work branch stored in issue metadata (oompah.work_branch).  Written by
    # the orchestrator when creating the agent worktree (TASK-461.3).  Used
    # for branch-to-issue resolution so callers do not need to guess the task
    # identifier from the branch name (TASK-462.1).
    work_branch: str | None = meta.get("work_branch") or None
    review_url: str | None = meta.get("review_url") or meta.get("oompah.review_url")
    review_number: str | None = (
        meta.get("review_number") or meta.get("oompah.review_number")
    )
    intake = meta.get("intake") or meta.get("oompah.intake")
    if not isinstance(intake, dict):
        intake = None

    # Description: issue body with metadata block stripped.
    description_text = _BODY_METADATA_RE.sub("", body).strip()
    description: str | None = description_text or None

    url: str | None = gh_issue.get("html_url") or None
    user = gh_issue.get("user") or {}
    requestor_login = user.get("login") if isinstance(user, dict) else None

    return Issue(
        id=gh_id.canonical,
        identifier=gh_id.canonical,
        title=gh_issue.get("title") or "",
        description=description,
        priority=priority,
        state=status,
        url=url,
        issue_type=issue_type,
        project_id=project_id,
        target_branch=target_branch,
        work_branch=work_branch,
        review_url=review_url,
        review_number=review_number,
        backports=meta.get("backports", meta.get("oompah.backports")),
        backport_of=meta.get("backport_of", meta.get("oompah.backport_of")),
        release_pick_metadata_loaded=True,
        labels=user_labels,
        created_at=_gh_timestamp(gh_issue.get("created_at")),
        updated_at=_gh_timestamp(gh_issue.get("updated_at")),
        closed_at=_gh_timestamp(gh_issue.get("closed_at")),
        intake=intake,
        tracker_kind="github_issues",
        tracker_owner=owner,
        tracker_repo=repo,
        issue_number=str(number),
        display_identifier=gh_id.display,
        provider_url=url,
        requestor_login=requestor_login,
        parent_id=parent_id,
        blocked_by=blocked_by,
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
        oompah status names considered terminal for dispatch. GitHub's native
        issue state is closed only for ``Merged`` and ``Archived``; ``Done``
        remains open while review/merge work is pending.
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
        status_label_authorized_logins: list[str] | None = None,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.active_states = list(active_states)
        self.terminal_states = list(terminal_states)
        self.status_label_authorized_logins = list(
            status_label_authorized_logins or []
        )
        self._auth = auth or GitHubAuth()
        self._client = GitHubClient(auth=self._auth)
        # In-memory ETag cache keyed by path.
        self._etag_cache: dict[str, tuple[str, Any]] = {}
        # Trusted-status ledger: maps issue number (int) → the last status
        # string that oompah itself applied via _set_status_label or
        # _patch_state_and_status_label, or that was confirmed via an
        # authorized webhook.  Used during polling to avoid trusting
        # oompah:status:* labels that were applied by unauthorized actors.
        # Entries are set by record_trusted_status() and cleared/reset by
        # record_untrusted_status_label_change().
        self._trusted_status_ledger: dict[int, str] = {}
        # Set of issue numbers whose current dispatchable status label is
        # under review (an unauthorized change was seen but not yet reverted).
        # These issues are skipped during fetch_candidate_issues.
        self._untrusted_status_issues: set[int] = set()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _repo_path(self, suffix: str = "") -> str:
        return f"/repos/{self.owner}/{self.repo}{suffix}"

    def _issues_path(self, suffix: str = "") -> str:
        return self._repo_path(f"/issues{suffix}")

    def _normalize_issue_payload(self, gh_issue: dict[str, Any]) -> Issue | None:
        """Normalize a GitHub issue payload and backfill missing status labels.

        GitHub's issues list endpoint can return issues created outside
        oompah.  If one has no recognized ``oompah:status:*`` label, record
        the safe fallback status on GitHub before returning the normalized
        Issue.  The local normalization still uses the fallback when the
        best-effort label write fails.

        GitHub also exposes pull requests through the issues API. Those are
        review artifacts, not tasks, and must never be normalized as issues.
        """
        if self._is_pull_request_payload(gh_issue):
            return None
        return _gh_issue_to_issue(
            self._ensure_status_label(gh_issue),
            self.owner,
            self.repo,
        )

    def _normalize_issue_payloads(self, raw: list[Any]) -> list[Issue]:
        issues: list[Issue] = []
        for gh in raw:
            if not isinstance(gh, dict):
                continue
            issue = self._normalize_issue_payload(gh)
            if issue is not None:
                issues.append(issue)
        return issues

    def _is_pull_request_payload(self, gh_issue: dict[str, Any]) -> bool:
        return bool(gh_issue.get("pull_request"))

    def _ensure_status_label(self, gh_issue: dict[str, Any]) -> dict[str, Any]:
        # GitHub exposes PRs through the issues API. PR lifecycle is handled
        # by the SCM/review path, so do not stamp task labels onto PR entries.
        if self._is_pull_request_payload(gh_issue):
            return gh_issue

        labels_raw: list[dict[str, Any]] = gh_issue.get("labels") or []
        gh_state: str = gh_issue.get("state", "open")
        desired_status = _extract_oompah_status(labels_raw, gh_state)
        for label in labels_raw:
            name = label.get("name", "")
            current_status = _label_to_status(name)
            if current_status is not None and current_status == desired_status:
                return gh_issue

        number = gh_issue.get("number")
        if number is None:
            return gh_issue

        label_names = [
            str(label.get("name"))
            for label in labels_raw
            if isinstance(label, dict) and label.get("name")
        ]
        labels = self._labels_with_status(label_names, desired_status)

        try:
            self._client.patch(
                self._issues_path(f"/{int(number)}"),
                json={"labels": labels},
            )
        except (TypeError, ValueError):
            return gh_issue
        except TrackerError as exc:
            logger.debug(
                "Failed to backfill GitHub issue status label for %s/%s#%s: %s",
                self.owner,
                self.repo,
                number,
                exc,
            )
            return gh_issue

        # Record this backfill write as oompah-owned in the trusted-status
        # ledger.  This prevents the corresponding webhook event from being
        # treated as an unauthorized human edit even when the actor reported
        # by GitHub does not exactly match OOMPAH_BOT_LOGIN (e.g. GitHub App
        # login vs. PAT login differences).
        self.record_trusted_status(int(number), desired_status)
        logger.debug(
            "Backfilled oompah status label for %s/%s#%s: %s (label: %s)",
            self.owner,
            self.repo,
            number,
            desired_status,
            _status_to_label(desired_status),
        )

        updated = dict(gh_issue)
        updated["labels"] = [{"name": label} for label in labels]
        return updated

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

        **Label-change authorization guard:** Issues whose current status
        label is in the ``_untrusted_status_issues`` set (i.e. an
        unauthorized actor applied the status label and the revert is
        pending or failed) are excluded from the candidate list.  This
        ensures that polling/full-sync cannot promote an issue based
        solely on an untrusted ``oompah:status:*`` label.

        Results are sorted by priority (ascending, ``None`` last) then by
        creation time (oldest first) so the orchestrator's dispatch loop
        receives a stable, deterministic ordering.
        """
        raw = self._client.request_paginated(
            self._issues_path(),
            params={"state": "open", "per_page": 100},
        )
        issues = self._normalize_issue_payloads(raw)
        active_set = {
            canonicalize_status(state)
            for state in self.active_states
            if canonicalize_status(state) != PROPOSED
        }
        candidates = [
            iss
            for iss in issues
            if (
                canonicalize_status(iss.state) != PROPOSED
                and canonicalize_status(iss.state) in active_set
            )
        ]

        # Filter out issues that have untrusted status-label changes pending.
        if self._untrusted_status_issues:
            safe_candidates = []
            for iss in candidates:
                # Extract the numeric issue number from the identifier.
                num = _extract_issue_number(iss)
                if num is not None and num in self._untrusted_status_issues:
                    logger.warning(
                        "fetch_candidate_issues: skipping issue #%d (%s) — "
                        "status label was changed by an unauthorized actor; "
                        "pending revert",
                        num,
                        iss.identifier,
                    )
                    continue
                safe_candidates.append(iss)
            candidates = safe_candidates

        # Validate dispatchable Open labels that were not applied by this
        # process or confirmed by a webhook. This closes the polling bypass
        # where a forbidden direct GitHub label edit is present before the
        # webhook revert is delivered.
        if candidates:
            safe_candidates = []
            for iss in candidates:
                if self._candidate_status_label_is_trusted(iss):
                    safe_candidates.append(iss)
            candidates = safe_candidates

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
        return self._normalize_issue_payloads(raw)

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
            return self._normalize_issue_payload(raw)
        except TrackerError as exc:
            if "404" in str(exc):
                return None
            raise

    def fetch_children(self, epic_id: str) -> list[Issue]:
        """Return child issues that reference the given parent identifier.

        Attempts the GitHub sub-issues REST endpoint and also searches for
        issues labelled ``parent:<epic_number>``.  The label lookup is not
        just a fallback: older oompah-created child issues may only have the
        label, while newer GitHub installations may expose an empty
        sub-issues result for relationships that were stored before the API
        was available.
        """
        try:
            gh_id = self.parse_identifier(epic_id)
        except TrackerError:
            return []

        children: dict[str, Issue] = {}
        parent_id = gh_id.canonical

        # Try the sub-issues endpoint (newer GitHub API).
        try:
            raw = self._client.request_paginated(
                self._issues_path(f"/{gh_id.number}/sub_issues"),
                params={"per_page": 100},
            )
            for child in self._normalize_issue_payloads(raw):
                if not child.parent_id:
                    child.parent_id = parent_id
                children[child.id] = child
        except TrackerError as exc:
            if "404" not in str(exc):
                raise

        # Label-based parent lookup. Keep this even when the sub-issues API
        # succeeds so label-only children still block duplicate epic planning.
        parent_label = f"parent:{gh_id.number}"
        try:
            raw = self._client.request_paginated(
                self._issues_path(),
                params={"state": "all", "labels": parent_label, "per_page": 100},
            )
            for child in self._normalize_issue_payloads(raw):
                if not child.parent_id:
                    child.parent_id = parent_id
                children[child.id] = child
        except TrackerError:
            pass

        return list(children.values())

    def fetch_comments(self, identifier: str) -> list[dict]:
        """Return all comments on an issue as a list of normalized comment dicts.

        Each comment dict contains at least ``author`` and ``text`` keys so that
        callers following the tracker protocol contract can rely on those fields.
        The raw GitHub fields (``id``, ``body``, ``created_at``, etc.) are also
        preserved for backward compatibility.
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            return []

        try:
            raw_comments = self._client.request_paginated(
                self._repo_path(f"/issues/{gh_id.number}/comments"),
                params={"per_page": 100},
            )
        except TrackerError:
            return []

        result = []
        for comment in raw_comments:
            if not isinstance(comment, dict):
                continue
            body: str = comment.get("body") or ""
            user_login: str | None = (comment.get("user") or {}).get("login")
            author, text = _parse_comment_body(body, user_login)
            normalized = dict(comment)
            normalized["author"] = author
            normalized["text"] = text
            result.append(normalized)
        return result

    def fetch_issues_by_states(self, state_names: list[str]) -> list[Issue]:
        """Return all issues whose oompah state matches any of *state_names*.

        Optimises the GitHub API query by requesting only ``open`` issues
        when all requested statuses can only be GitHub-open, only ``closed``
        when all requested statuses can only be GitHub-closed, or ``all`` for
        mixed sets. ``Done`` uses ``all`` so old closed-Done issues remain
        visible to reconciliation.
        """
        if not state_names:
            return []

        state_set = set(state_names)
        gh_state = _github_query_state_for_statuses(state_set)

        raw = self._client.request_paginated(
            self._issues_path(),
            params={"state": gh_state, "per_page": 100},
        )
        issues = self._normalize_issue_payloads(raw)
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
            state_set = set(states)
            gh_state = _github_query_state_for_statuses(state_set)
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
        issues = self._normalize_issue_payloads(raw)
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
                    results.append(self._normalize_issue_payload(raw))
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
        priority: Any = None,
        initial_status: str | None = None,
        labels: list[str] | None = None,
        parent: str | None = None,
    ) -> Issue:
        """Create a new GitHub issue and return the normalized Issue record.

        The initial status is encoded as an ``oompah:status:*`` label.
        Priority is encoded as a ``priority:N`` label and may be supplied as a
        numeric value or tracker-neutral name such as ``high``.  Issue type
        (when non-default) is encoded as a ``type:<kind>`` label. User-supplied
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
            pri_int = _priority_label_value(priority)
            if pri_int is not None:
                all_labels.append(f"priority:{pri_int}")

        # Issue type label (omit default "task" to keep issues uncluttered).
        if issue_type and issue_type != "task":
            all_labels.append(f"type:{issue_type}")

        # User-supplied labels (skip duplicates already added above).
        for lbl in (labels or []):
            if lbl not in all_labels:
                all_labels.append(lbl)

        # Parent relationship — encode as parent:<number> label so that
        # _gh_issue_to_issue can reconstruct parent_id from the label.
        if parent:
            try:
                parent_gh_id = self.parse_identifier(parent)
                parent_label = f"parent:{parent_gh_id.number}"
                if parent_label not in all_labels:
                    all_labels.append(parent_label)
            except TrackerError:
                pass  # Invalid parent identifier — skip silently.

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

        # If the initial status is terminal in GitHub itself, close the issue
        # immediately. ``Done`` is intentionally left open so review handoff
        # and merge reconciliation can still see the issue.
        if _status_closes_github_issue(status):
            number = gh_issue.get("number")
            if number is not None:
                try:
                    self._client.patch(
                        self._issues_path(f"/{number}"),
                        json={"state": "closed"},
                    )
                    gh_issue = dict(gh_issue)
                    gh_issue["state"] = "closed"
                except TrackerError:
                    pass  # Best-effort; the label still encodes the terminal status.

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
            sets the GitHub native ``state`` to closed only for ``Merged`` and
            ``Archived``. ``Done`` remains open while review/merge is pending.
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
        priority_specified = False
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
                priority_specified = True
                priority_to_set = value
            elif key_norm == "add-label":
                label_ops.append(("add", str(value)))
            elif key_norm == "remove-label":
                label_ops.append(("remove", str(value)))
            else:
                logger.debug(
                    "GitHub update_issue ignoring unsupported field %s", key
                )

        # Status and priority labels are updated through the same PATCH used
        # for GitHub state changes. This keeps the visible oompah status from
        # diverging when GitHub rejects the issue state update.
        if status_to_set is not None:
            patch_payload["state"] = _github_issue_state_for_status(status_to_set)
        if status_to_set is not None or priority_specified:
            labels = self._fetch_issue_label_names(gh_id.number)
            if status_to_set is not None:
                labels = self._labels_with_status(labels, status_to_set)
            if priority_specified:
                labels = self._labels_with_priority(labels, priority_to_set)
            patch_payload["labels"] = labels

        # Issue a single PATCH for title/body/state changes.
        if patch_payload:
            self._client.patch(
                self._issues_path(f"/{gh_id.number}"),
                json=patch_payload,
            )
            if status_to_set is not None:
                self.record_trusted_status(gh_id.number, status_to_set)

        # Label add/remove operations.
        for op, label in label_ops:
            if op == "add":
                self.add_label(identifier, label)
            else:
                self.remove_label(identifier, label)

    def close_issue(self, identifier: str, *, reason: str | None = None) -> None:
        """Move an issue to the first configured terminal state.

        Sets the ``oompah:status:*`` label to the terminal status and
        optionally appends a comment with the close reason. When that terminal
        status is ``Done``, the GitHub issue remains open until it is later
        marked ``Merged`` or ``Archived``.
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            raise

        terminal = self._terminal_status()
        self._patch_state_and_status_label(
            gh_id.number,
            _github_issue_state_for_status(terminal),
            terminal,
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
        self._patch_state_and_status_label(gh_id.number, "open", active)

    def archive_issue(self, identifier: str) -> None:
        """Archive an issue.

        Sets ``oompah:status:archived`` label and closes the GitHub issue.
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            raise

        self._patch_state_and_status_label(gh_id.number, "closed", "Archived")

    def mark_needs_human(
        self, identifier: str, comment: str, author: str = "oompah"
    ) -> None:
        """Move an issue to Needs Human and post the actionable comment."""
        handoff = validate_needs_human_comment(comment)
        self.update_issue(identifier, status=NEEDS_HUMAN)
        self.add_comment(identifier, handoff, author=author)

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
            normalized = dict(result)
            normalized["author"] = author
            normalized["text"] = comment_text
            return normalized
        return {"body": body, "author": author, "text": comment_text}

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

    def _ensure_dynamic_relation_label(self, label: str) -> None:
        """Ensure an oompah relationship label exists before applying it."""
        try:
            self._client.post(
                self._repo_path("/labels"),
                json={
                    "name": label,
                    "color": "ededed",
                    "description": "oompah relationship metadata",
                },
            )
        except TrackerError as exc:
            # GitHub returns 422 when the label already exists. Some test
            # doubles and older API surfaces do not expose the repository
            # label creation endpoint; in that case keep going and let the
            # issue-label application report any real failure.
            if "422" in str(exc) or "404" in str(exc):
                return
            raise

    # ------------------------------------------------------------------
    # Hierarchy and dependencies
    # ------------------------------------------------------------------

    def _issue_database_id(self, gh_id: GitHubIssueIdentifier) -> int:
        """Return GitHub's database id for an issue number."""
        raw = self._client.get(self._issues_path(f"/{gh_id.number}"))
        if not isinstance(raw, dict) or "id" not in raw:
            raise TrackerError(
                f"GitHub issue {gh_id.display} did not include a database id."
            )
        try:
            return int(raw["id"])
        except (TypeError, ValueError) as exc:
            raise TrackerError(
                f"GitHub issue {gh_id.display} has an invalid database id: "
                f"{raw['id']!r}"
            ) from exc

    def add_parent_child(self, child_id: str, parent_id: str) -> None:
        """Link a child issue to a parent issue.

        Tries the GitHub sub-issues REST API first.  When that endpoint
        is not available (HTTP 404), falls back to setting a
        ``parent:<number>`` label on the child issue.

        Parameters
        ----------
        child_id:
            Fully-qualified identifier of the child issue.
        parent_id:
            Fully-qualified identifier of the parent issue.

        Raises
        ------
        TrackerError
            If either identifier is invalid or the API call fails
            unexpectedly.
        """
        try:
            child_gh_id = self.parse_identifier(child_id)
            parent_gh_id = self.parse_identifier(parent_id)
        except TrackerError:
            raise

        child_database_id = self._issue_database_id(child_gh_id)
        parent_label = f"parent:{parent_gh_id.number}"

        # Try the GitHub sub-issues API. It expects the child's database id,
        # not the visible issue number.
        try:
            self._client.post(
                self._issues_path(f"/{parent_gh_id.number}/sub_issues"),
                json={"sub_issue_id": child_database_id},
            )
            self._ensure_dynamic_relation_label(parent_label)
            self.add_label(child_id, parent_label)
            return
        except TrackerError as exc:
            if "404" not in str(exc):
                raise

        # Fallback: set parent:<number> label on the child issue.
        self._ensure_dynamic_relation_label(parent_label)
        self.add_label(child_id, parent_label)

    def add_dependency(self, blocked_id: str, blocker_id: str) -> None:
        """Record that blocked_id depends on blocker_id.

        Tries the GitHub issue dependencies REST API first.  When that
        endpoint is not available (HTTP 404), falls back to setting a
        ``depends-on:<number>`` label on the blocked issue.

        Parameters
        ----------
        blocked_id:
            Fully-qualified identifier of the issue that is blocked.
        blocker_id:
            Fully-qualified identifier of the issue that blocks.

        Raises
        ------
        TrackerError
            If either identifier is invalid or the API call fails
            unexpectedly.
        """
        try:
            blocked_gh_id = self.parse_identifier(blocked_id)
            blocker_gh_id = self.parse_identifier(blocker_id)
        except TrackerError:
            raise

        blocker_database_id = self._issue_database_id(blocker_gh_id)
        depends_on_label = f"depends-on:{blocker_gh_id.number}"

        # Try the GitHub issue dependencies API. It expects the blocker
        # issue's database id in the blocked_by collection.
        try:
            self._client.post(
                self._issues_path(f"/{blocked_gh_id.number}/dependencies/blocked_by"),
                json={"issue_id": blocker_database_id},
            )
            self._ensure_dynamic_relation_label(depends_on_label)
            self.add_label(blocked_id, depends_on_label)
            return
        except TrackerError as exc:
            if "404" not in str(exc):
                raise

        # Fallback: set depends-on:<number> label on the blocked issue.
        self._ensure_dynamic_relation_label(depends_on_label)
        self.add_label(blocked_id, depends_on_label)

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

        Returns an empty dict when the issue cannot be found, when the
        identifier is invalid, or when the body contains no metadata block.

        Parameters
        ----------
        identifier:
            Fully-qualified GitHub issue identifier.
        """
        try:
            gh_id = self.parse_identifier(identifier)
        except TrackerError:
            return {}
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
            return self._fetch_issue_label_names(number)
        except TrackerError:
            return []

    def _fetch_issue_label_names(self, number: int) -> list[str]:
        """Return issue label names, propagating GitHub read failures."""
        raw = self._client.request_paginated(
            self._issues_path(f"/{number}/labels"),
            params={"per_page": 100},
        )
        return [
            lbl["name"]
            for lbl in (raw or [])
            if isinstance(lbl, dict) and lbl.get("name")
        ]

    def _labels_with_status(self, labels: list[str], status: str) -> list[str]:
        """Return *labels* with exactly one oompah status label."""
        new_label = _status_to_label(status)
        result = [name for name in labels if not name.startswith(_STATUS_LABEL_PREFIX)]
        if new_label not in result:
            result.append(new_label)
        return result

    def _labels_with_priority(self, labels: list[str], priority: Any) -> list[str]:
        """Return *labels* with the requested priority label applied."""
        result = [name for name in labels if not name.startswith("priority:")]
        if priority is None:
            return result
        pri_int = _priority_label_value(priority)
        if pri_int is None:
            logger.debug(
                "GitHub _labels_with_priority: cannot coerce %r to int, skipping",
                priority,
            )
            return result
        new_label = f"priority:{pri_int}"
        if new_label not in result:
            result.append(new_label)
        return result

    def _patch_state_and_status_label(
        self, number: int, state: str, status: str
    ) -> None:
        """Patch GitHub state and oompah status label in one request."""
        labels = self._labels_with_status(
            self._fetch_issue_label_names(number),
            status,
        )
        self._client.patch(
            self._issues_path(f"/{number}"),
            json={"state": state, "labels": labels},
        )
        # Record this oompah-owned status change in the trusted ledger so
        # polling validation confirms it as authoritative.
        self.record_trusted_status(number, status)
        logger.debug(
            "API status change for %s/%s#%s: state=%s status=%s",
            self.owner,
            self.repo,
            number,
            state,
            status,
        )

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
        # Record this oompah-owned status change in the trusted ledger so
        # polling validation confirms it as authoritative.
        self.record_trusted_status(number, status)
        logger.debug(
            "API direct label write for %s/%s#%s: status=%s",
            self.owner,
            self.repo,
            number,
            status,
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
            pri_int = _priority_label_value(priority)
            if pri_int is None:
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

    # ------------------------------------------------------------------
    # Trusted-status ledger
    # ------------------------------------------------------------------

    def record_trusted_status(self, number: int, status: str) -> None:
        """Record that oompah (or an authorized actor) set *status* on issue *number*.

        Called internally by :meth:`_set_status_label` and
        :meth:`_patch_state_and_status_label` so that polling validation can
        confirm that the current dispatchable status was applied by oompah
        itself.

        Also called by the webhook handler when an authorized label change is
        received so the ledger stays up to date between polling cycles.
        """
        if number and status:
            self._trusted_status_ledger[number] = status
            self._untrusted_status_issues.discard(number)

    def _authorized_status_label_logins(self) -> frozenset[str]:
        """Return lower-case logins trusted to apply status labels."""
        from oompah.label_auth import get_bot_login

        logins = {get_bot_login(), self.owner}
        logins.update(self.status_label_authorized_logins)
        return frozenset(
            str(login).strip().lower()
            for login in logins
            if str(login).strip()
        )

    def _candidate_status_label_is_trusted(self, issue: Issue) -> bool:
        """Return true when a dispatch candidate's status label is trusted."""
        number = _extract_issue_number(issue)
        if number is None:
            return True

        status = issue.state
        if self._trusted_status_ledger.get(number) == status:
            return True

        # The intake transition gate only protects the Proposed/Backlog -> Open
        # dispatch boundary. Other dispatchable retry statuses are lifecycle
        # states set by oompah itself.
        if status_key(status) != "open":
            return True

        authorized = self._authorized_status_label_logins()
        if self.validate_status_label_actor(number, status, authorized):
            self.record_trusted_status(number, status)
            return True

        self.record_untrusted_status_label_change(
            number,
            _status_to_label(status),
            "polling-reconciliation",
            "labeled",
        )
        return False

    def record_untrusted_status_label_change(
        self, number: int, label_name: str, actor: str, action: str
    ) -> None:
        """Record that an *unauthorized* actor changed a status label on *number*.

        Marks the issue as untrusted so :meth:`fetch_candidate_issues` will
        skip it until the label is reverted and :meth:`record_trusted_status`
        is called again.

        Args:
            number: GitHub issue number.
            label_name: The ``oompah:status:*`` label that was changed.
            actor: The GitHub login of the unauthorized actor.
            action: ``"labeled"`` or ``"unlabeled"``.
        """
        if number:
            self._untrusted_status_issues.add(number)
            # Remove from trusted ledger so the next polling cycle re-validates.
            self._trusted_status_ledger.pop(number, None)
            logger.warning(
                "GitHubIssueTracker: untrusted status label change recorded for "
                "issue #%d (label=%s, actor=%s, action=%s)",
                number,
                label_name,
                actor,
                action,
            )

    def validate_status_label_actor(
        self, number: int, status: str, authorized_logins: frozenset[str]
    ) -> bool:
        """Validate that the current *status* label on *number* was applied by an authorized actor.

        Fetches the recent issue events from the GitHub Events API and
        looks for the most recent ``labeled`` event for the
        ``oompah:status:<slug>`` label corresponding to *status*.

        Returns ``True`` if the most recent actor who applied that label is in
        *authorized_logins*, or if no recent labeled event is found (i.e. the
        label predates the event retention window — treat as trusted since we
        cannot verify).

        Returns ``False`` only when there is clear evidence that an unauthorized
        actor applied the label.

        Args:
            number: GitHub issue number.
            status: Canonical oompah status string (e.g. ``"Open"``).
            authorized_logins: Set of lowercase GitHub logins that are trusted.
        """
        from oompah.label_auth import _status_to_label_name as _s2l

        try:
            label_to_find = _s2l(status)
        except Exception:
            return True  # unknown label — can't validate, treat as trusted

        try:
            events = self._client.request_paginated(
                self._issues_path(f"/{number}/events"),
                params={"per_page": 100},
            )
        except Exception as exc:
            logger.warning(
                "validate_status_label_actor: could not fetch events for "
                "issue #%d: %s — treating as trusted",
                number,
                exc,
            )
            return True  # API failure — don't block dispatch, treat as trusted

        # Scan events in reverse chronological order to find the most recent
        # ``labeled`` event for the target label.
        labeled_events = [
            ev for ev in events
            if ev.get("event") == "labeled"
            and (ev.get("label") or {}).get("name") == label_to_find
        ]

        if not labeled_events:
            # No labeled event found — label predates event retention or
            # was applied outside the API window.  Treat as trusted.
            return True

        # The events API returns events in ascending chronological order;
        # the last entry is the most recent.
        most_recent = labeled_events[-1]
        actor_login = (most_recent.get("actor") or {}).get("login", "")
        actor_lower = (actor_login or "").strip().lower()
        if actor_lower in authorized_logins:
            return True

        logger.warning(
            "validate_status_label_actor: issue #%d has status=%r but the "
            "most recent labeled event actor %r is not authorized (authorized=%s)",
            number,
            status,
            actor_login,
            authorized_logins,
        )
        return False


# ---------------------------------------------------------------------------
# Factory function for ADAPTER_REGISTRY
# ---------------------------------------------------------------------------


def _github_issues_factory(
    *,
    active_states: list[str],
    terminal_states: list[str],
    cwd: str | None = None,
    owner: str | None = None,
    repo: str | None = None,
    access_token: str | None = None,
    status_label_authorized_logins: list[str] | None = None,
    **kwargs: Any,
) -> GitHubIssueTracker:
    """Factory function registered in :data:`~oompah.tracker.ADAPTER_REGISTRY`.

    Resolves the task hub owner and repository from (in order of precedence):

    1. The ``owner`` / ``repo`` keyword arguments — supplied when the
       orchestrator constructs a per-project tracker from
       :attr:`~oompah.models.Project.tracker_owner` and
       :attr:`~oompah.models.Project.tracker_repo`.
    2. The ``OOMPAH_GITHUB_TRACKER_OWNER`` / ``OOMPAH_GITHUB_TRACKER_REPO``
       environment variables — used for the global default tracker and for
       projects that have not been given explicit per-project fields.

    Raises :class:`~oompah.tracker.TrackerError` when neither source
    provides the required owner and repository values.
    """
    resolved_owner: str = owner or os.environ.get("OOMPAH_GITHUB_TRACKER_OWNER", "")
    resolved_repo: str = repo or os.environ.get("OOMPAH_GITHUB_TRACKER_REPO", "")
    if not resolved_owner or not resolved_repo:
        raise TrackerError(
            "GitHub Issues tracker requires OOMPAH_GITHUB_TRACKER_OWNER and "
            "OOMPAH_GITHUB_TRACKER_REPO environment variables."
        )
    auth = GitHubAuth(pat=access_token) if access_token else None
    return GitHubIssueTracker(
        owner=resolved_owner,
        repo=resolved_repo,
        active_states=active_states,
        terminal_states=terminal_states,
        auth=auth,
        cwd=cwd,
        status_label_authorized_logins=status_label_authorized_logins,
    )
