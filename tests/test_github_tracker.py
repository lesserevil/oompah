"""Tests for oompah.github_tracker — GitHub auth, API client, and identifier support.

Covers acceptance criteria:
  #1  Identifier parsing rejects ambiguous bare numbers.
  #2  Display identifiers and branch slugs are stable and filesystem-safe.
  #3  GitHub App, PAT, and missing-auth paths.
  #4  Rate-limit and auth errors become actionable TrackerError messages.
  #5  fetch_candidate_issues returns only configured dispatchable statuses.
  #6  Pagination and empty result sets are handled correctly.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch, call
import threading

import httpx
import pytest

from oompah.github_tracker import (
    GitHubAuth,
    GitHubClient,
    GitHubIdentifier,
    GitHubIdentifierError,
    GitHubIssueTracker,
    _generate_app_jwt,
    _parse_next_link,
    _redact,
    _github_issues_factory,
    github_identifier_to_issue_fields,
    parse_github_identifier,
    _status_to_label,
    _label_to_status,
    _extract_oompah_status,
    _extract_priority,
    _extract_issue_type,
    _extract_parent_from_body,
    _parse_body_metadata,
    _gh_timestamp,
    _gh_issue_to_issue,
)
from oompah.tracker import ADAPTER_REGISTRY, TrackerProtocol
from oompah.models import Issue
from oompah.tracker import TrackerError, TrackerTimeoutError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(
    status_code: int = 200,
    json_data=None,
    text: str = "",
    headers: dict | None = None,
) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.headers = httpx.Headers(headers or {})
    resp.text = text if text else (str(json_data) if json_data else "")
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = Exception("no JSON")
    resp.request = MagicMock()
    resp.request.method = "GET"
    resp.request.url = "https://api.github.com/test"
    return resp


# ===========================================================================
# GitHubIdentifier — dataclass properties
# ===========================================================================


class TestGitHubIdentifier:
    """Tests for the GitHubIdentifier dataclass and its computed properties.

    Acceptance criterion #2: display identifiers and branch slugs are
    stable and filesystem-safe.
    """

    def _make(self, owner="example-org", repo="oompah-tasks", number=1234):
        return GitHubIdentifier(owner=owner, repo=repo, number=number)

    # ------------------------------------------------------------------
    # canonical form
    # ------------------------------------------------------------------

    def test_canonical_format(self):
        gh = self._make()
        assert gh.canonical == "example-org/oompah-tasks#1234"

    def test_str_returns_canonical(self):
        gh = self._make()
        assert str(gh) == "example-org/oompah-tasks#1234"

    def test_canonical_single_digit_number(self):
        gh = self._make(number=1)
        assert gh.canonical == "example-org/oompah-tasks#1"

    # ------------------------------------------------------------------
    # display form
    # ------------------------------------------------------------------

    def test_display_omits_owner(self):
        gh = self._make()
        assert gh.display == "oompah-tasks#1234"

    def test_display_uses_repo_name(self):
        gh = self._make(repo="my-tasks")
        assert gh.display == "my-tasks#1234"

    def test_display_is_stable_across_owners(self):
        """Display form does not change when the owner changes (hub centralisation)."""
        gh1 = self._make(owner="alice")
        gh2 = self._make(owner="bob")
        assert gh1.display == gh2.display

    # ------------------------------------------------------------------
    # url_safe form
    # ------------------------------------------------------------------

    def test_url_safe_has_no_hash(self):
        gh = self._make()
        assert "#" not in gh.url_safe

    def test_url_safe_format(self):
        gh = self._make()
        assert gh.url_safe == "example-org/oompah-tasks/1234"

    def test_url_safe_three_components(self):
        gh = self._make()
        parts = gh.url_safe.split("/")
        assert len(parts) == 3
        assert parts[0] == "example-org"
        assert parts[1] == "oompah-tasks"
        assert parts[2] == "1234"

    def test_from_url_safe_round_trips(self):
        original = self._make()
        reconstructed = GitHubIdentifier.from_url_safe(original.url_safe)
        assert reconstructed == original

    def test_from_url_safe_invalid_not_three_parts(self):
        with pytest.raises(GitHubIdentifierError, match="form"):
            GitHubIdentifier.from_url_safe("owner/repo")

    def test_from_url_safe_non_numeric_number(self):
        with pytest.raises(GitHubIdentifierError, match="non-numeric"):
            GitHubIdentifier.from_url_safe("owner/repo/abc")

    # ------------------------------------------------------------------
    # branch_slug
    # ------------------------------------------------------------------

    def test_branch_slug_format(self):
        gh = self._make()
        assert gh.branch_slug == "gh-1234"

    def test_branch_slug_has_no_slash(self):
        gh = self._make()
        assert "/" not in gh.branch_slug

    def test_branch_slug_has_no_hash(self):
        gh = self._make()
        assert "#" not in gh.branch_slug

    def test_branch_slug_is_stable(self):
        """Branch slug must not change across different owners/repos (number is primary key)."""
        gh1 = self._make(owner="alice", repo="alpha-tasks")
        gh2 = self._make(owner="bob", repo="beta-tasks")
        assert gh1.branch_slug == gh2.branch_slug

    def test_branch_slug_filesystem_safe_chars(self):
        """Branch slug contains only A-Z, a-z, 0-9, hyphen, and dot."""
        import re
        gh = self._make(number=9999)
        assert re.fullmatch(r"[A-Za-z0-9._\-]+", gh.branch_slug)

    # ------------------------------------------------------------------
    # frozen / immutable
    # ------------------------------------------------------------------

    def test_frozen_cannot_mutate(self):
        gh = self._make()
        with pytest.raises((AttributeError, TypeError)):
            gh.number = 9999  # type: ignore[misc]

    # ------------------------------------------------------------------
    # validation in __post_init__
    # ------------------------------------------------------------------

    def test_empty_owner_raises(self):
        with pytest.raises(GitHubIdentifierError, match="owner"):
            GitHubIdentifier(owner="", repo="repo", number=1)

    def test_empty_repo_raises(self):
        with pytest.raises(GitHubIdentifierError, match="repo"):
            GitHubIdentifier(owner="owner", repo="", number=1)

    def test_zero_number_raises(self):
        with pytest.raises(GitHubIdentifierError, match="positive"):
            GitHubIdentifier(owner="owner", repo="repo", number=0)

    def test_negative_number_raises(self):
        with pytest.raises(GitHubIdentifierError, match="positive"):
            GitHubIdentifier(owner="owner", repo="repo", number=-5)


# ===========================================================================
# parse_github_identifier — acceptance criterion #1 (reject bare numbers)
# ===========================================================================


class TestParseGitHubIdentifier:
    """Tests for parse_github_identifier().

    Acceptance criterion #1: identifier parsing rejects ambiguous bare numbers.
    """

    # ------------------------------------------------------------------
    # Valid inputs
    # ------------------------------------------------------------------

    def test_parses_canonical_form(self):
        gh = parse_github_identifier("example-org/oompah-tasks#1234")
        assert gh.owner == "example-org"
        assert gh.repo == "oompah-tasks"
        assert gh.number == 1234

    def test_parses_single_digit(self):
        gh = parse_github_identifier("owner/repo#1")
        assert gh.number == 1

    def test_parses_with_hyphens_in_owner(self):
        gh = parse_github_identifier("my-org/my-repo#42")
        assert gh.owner == "my-org"
        assert gh.repo == "my-repo"
        assert gh.number == 42

    def test_parses_with_underscores_in_repo(self):
        gh = parse_github_identifier("org/my_awesome_repo#100")
        assert gh.repo == "my_awesome_repo"

    def test_parses_with_dots_in_repo(self):
        gh = parse_github_identifier("org/my.dotted.repo#7")
        assert gh.repo == "my.dotted.repo"

    def test_returns_github_identifier_instance(self):
        result = parse_github_identifier("owner/repo#5")
        assert isinstance(result, GitHubIdentifier)

    def test_strips_surrounding_whitespace(self):
        gh = parse_github_identifier("  example-org/oompah-tasks#42  ")
        assert gh.canonical == "example-org/oompah-tasks#42"

    # ------------------------------------------------------------------
    # Bare numbers — acceptance criterion #1
    # ------------------------------------------------------------------

    def test_rejects_bare_integer(self):
        with pytest.raises(GitHubIdentifierError, match="bare numeric"):
            parse_github_identifier("1234")

    def test_rejects_bare_integer_small(self):
        with pytest.raises(GitHubIdentifierError, match="bare numeric"):
            parse_github_identifier("1")

    def test_rejects_hash_number(self):
        """#1234 (without owner/repo) must be rejected."""
        with pytest.raises(GitHubIdentifierError, match="bare numeric|cannot parse"):
            parse_github_identifier("#1234")

    def test_rejects_zero(self):
        """GitHub issue numbers start at 1; #0 is not valid."""
        with pytest.raises(GitHubIdentifierError):
            parse_github_identifier("owner/repo#0")

    # ------------------------------------------------------------------
    # Unqualified / incomplete forms
    # ------------------------------------------------------------------

    def test_rejects_repo_without_owner(self):
        """repo#1234 is unqualified (missing owner) and must be rejected."""
        with pytest.raises(GitHubIdentifierError, match="cannot parse|bare numeric|not a valid"):
            parse_github_identifier("repo#1234")

    def test_rejects_missing_issue_number(self):
        with pytest.raises(GitHubIdentifierError):
            parse_github_identifier("owner/repo")

    def test_rejects_empty_string(self):
        with pytest.raises(GitHubIdentifierError, match="empty"):
            parse_github_identifier("")

    def test_rejects_none_coerced_to_empty(self):
        with pytest.raises(GitHubIdentifierError, match="empty"):
            parse_github_identifier(None)  # type: ignore[arg-type]

    def test_rejects_owner_with_leading_hyphen(self):
        with pytest.raises(GitHubIdentifierError, match="cannot parse"):
            parse_github_identifier("-owner/repo#1")

    def test_rejects_owner_with_trailing_hyphen(self):
        with pytest.raises(GitHubIdentifierError, match="cannot parse"):
            parse_github_identifier("owner-/repo#1")

    def test_rejects_number_with_leading_zero(self):
        """GitHub issue numbers don't have leading zeros."""
        with pytest.raises(GitHubIdentifierError, match="cannot parse"):
            parse_github_identifier("owner/repo#01")

    # ------------------------------------------------------------------
    # Error messages
    # ------------------------------------------------------------------

    def test_bare_number_error_mentions_canonical_form(self):
        """The error for a bare number must tell the user the correct form."""
        with pytest.raises(GitHubIdentifierError) as exc_info:
            parse_github_identifier("999")
        assert "owner/repo#" in str(exc_info.value)

    def test_invalid_form_error_mentions_canonical_form(self):
        with pytest.raises(GitHubIdentifierError) as exc_info:
            parse_github_identifier("not-valid-at-all")
        assert "owner/repo#" in str(exc_info.value)


# ===========================================================================
# github_identifier_to_issue_fields
# ===========================================================================


class TestGitHubIdentifierToIssueFields:
    """Tests for the helper that maps GitHubIdentifier to Issue field dict."""

    def test_returns_dict(self):
        gh = GitHubIdentifier(owner="example-org", repo="oompah-tasks", number=1)
        result = github_identifier_to_issue_fields(gh)
        assert isinstance(result, dict)

    def test_contains_tracker_kind(self):
        gh = GitHubIdentifier(owner="o", repo="r", number=1)
        result = github_identifier_to_issue_fields(gh)
        assert result["tracker_kind"] == "github_issues"

    def test_contains_tracker_owner(self):
        gh = GitHubIdentifier(owner="myorg", repo="tasks", number=5)
        result = github_identifier_to_issue_fields(gh)
        assert result["tracker_owner"] == "myorg"

    def test_contains_tracker_repo(self):
        gh = GitHubIdentifier(owner="o", repo="myrepo", number=5)
        result = github_identifier_to_issue_fields(gh)
        assert result["tracker_repo"] == "myrepo"

    def test_issue_number_is_string(self):
        """issue_number is a string to match the Issue model field type."""
        gh = GitHubIdentifier(owner="o", repo="r", number=42)
        result = github_identifier_to_issue_fields(gh)
        assert result["issue_number"] == "42"
        assert isinstance(result["issue_number"], str)

    def test_display_identifier(self):
        gh = GitHubIdentifier(owner="example-org", repo="oompah-tasks", number=1234)
        result = github_identifier_to_issue_fields(gh)
        assert result["display_identifier"] == "oompah-tasks#1234"

    def test_can_unpack_into_issue(self):
        """The returned dict can be unpacked as Issue keyword arguments."""
        from oompah.models import Issue
        gh = GitHubIdentifier(owner="example-org", repo="oompah-tasks", number=7)
        fields = github_identifier_to_issue_fields(gh)
        issue = Issue(
            id="7",
            identifier=gh.canonical,
            title="Test",
            **fields,
        )
        assert issue.tracker_kind == "github_issues"
        assert issue.tracker_owner == "example-org"
        assert issue.tracker_repo == "oompah-tasks"
        assert issue.issue_number == "7"
        assert issue.display_identifier == "oompah-tasks#7"


# ===========================================================================
# GitHubIssueTracker identifier helpers
# ===========================================================================


class TestGitHubIssueTrackerIdentifierHelpers:
    """Tests for parse_identifier() and identifier_for_number() on the tracker."""

    def _make_tracker(self) -> GitHubIssueTracker:
        return GitHubIssueTracker(
            owner="example-org",
            repo="oompah-tasks",
            active_states=["Open", "In Progress"],
            terminal_states=["Done", "Archived"],
            auth=GitHubAuth(pat="test_token"),
        )

    def test_parse_identifier_valid(self):
        tracker = self._make_tracker()
        gh = tracker.parse_identifier("example-org/oompah-tasks#42")
        assert gh.owner == "example-org"
        assert gh.number == 42

    def test_parse_identifier_raises_tracker_error_for_bare_number(self):
        """parse_identifier() re-raises GitHubIdentifierError as TrackerError."""
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.parse_identifier("1234")

    def test_parse_identifier_raises_tracker_error_for_invalid(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.parse_identifier("not-an-id")

    def test_identifier_for_number(self):
        tracker = self._make_tracker()
        gh = tracker.identifier_for_number(99)
        assert gh.owner == "example-org"
        assert gh.repo == "oompah-tasks"
        assert gh.number == 99
        assert gh.canonical == "example-org/oompah-tasks#99"

    def test_identifier_for_number_branch_slug(self):
        tracker = self._make_tracker()
        gh = tracker.identifier_for_number(7)
        assert gh.branch_slug == "gh-7"


# ===========================================================================
# _redact
# ===========================================================================


class TestRedact:
    def test_redacts_bearer_token(self):
        text = "Authorization: Bearer ghp_abc123XYZ"
        result = _redact(text)
        assert "[REDACTED]" in result
        assert "ghp_abc123XYZ" not in result

    def test_preserves_non_token_text(self):
        text = "plain log line with no secrets"
        assert _redact(text) == text

    def test_case_insensitive(self):
        text = "bearer TOKEN_ABCDEF"
        result = _redact(text)
        assert "[REDACTED]" in result
        assert "TOKEN_ABCDEF" not in result


# ===========================================================================
# _parse_next_link
# ===========================================================================


class TestParseNextLink:
    def test_returns_none_when_no_link_header(self):
        assert _parse_next_link("") is None

    def test_returns_next_url(self):
        header = (
            '<https://api.github.com/repos/o/r/issues?page=2>; rel="next", '
            '<https://api.github.com/repos/o/r/issues?page=5>; rel="last"'
        )
        assert _parse_next_link(header) == (
            "https://api.github.com/repos/o/r/issues?page=2"
        )

    def test_returns_none_when_no_next(self):
        header = '<https://api.github.com/repos/o/r/issues?page=5>; rel="last"'
        assert _parse_next_link(header) is None


# ===========================================================================
# _generate_app_jwt
# ===========================================================================


class TestGenerateAppJwt:
    def test_returns_string(self, rsa_key_pair):
        private_pem, _ = rsa_key_pair
        token = _generate_app_jwt("12345", private_pem)
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # header.payload.signature

    def test_uses_rs256(self, rsa_key_pair):
        import jwt as pyjwt
        private_pem, public_pem = rsa_key_pair
        token = _generate_app_jwt("99", private_pem)
        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "RS256"

    def test_payload_contains_iss(self, rsa_key_pair):
        import jwt as pyjwt
        private_pem, public_pem = rsa_key_pair
        token = _generate_app_jwt("42", private_pem)
        payload = pyjwt.decode(token, public_pem, algorithms=["RS256"])
        assert payload["iss"] == "42"

    def test_invalid_key_raises_tracker_error(self):
        with pytest.raises(TrackerError, match="Failed to generate GitHub App JWT"):
            _generate_app_jwt("1", "not-a-valid-pem")


# ===========================================================================
# GitHubAuth — auth mode detection
# ===========================================================================


class TestGitHubAuthMode:
    """Tests for the three auth paths."""

    # ------------------------------------------------------------------
    # GitHub App path
    # ------------------------------------------------------------------

    def test_app_auth_mode(self, rsa_key_pair):
        private_pem, _ = rsa_key_pair
        auth = GitHubAuth(
            app_id="1234",
            app_private_key=private_pem,
            app_installation_id="999",
        )
        assert auth.auth_mode == "github_app"

    def test_app_get_token_calls_installation_endpoint(self, rsa_key_pair):
        """GitHub App auth should POST to /app/installations/<id>/access_tokens."""
        private_pem, _ = rsa_key_pair
        auth = GitHubAuth(
            app_id="1234",
            app_private_key=private_pem,
            app_installation_id="999",
        )
        fake_resp = _mock_response(
            201,
            json_data={
                "token": "ghs_installation_token",
                "expires_at": "2099-01-01T00:00:00Z",
            },
        )
        with patch("httpx.post", return_value=fake_resp) as mock_post:
            token = auth.get_token()
        assert token == "ghs_installation_token"
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert "/app/installations/999/access_tokens" in url

    def test_app_token_refreshed_near_expiry(self, rsa_key_pair):
        """Installation token is re-fetched when within HEADROOM of expiry."""
        from oompah.github_tracker import _TOKEN_REFRESH_HEADROOM_S, _InstallationToken
        private_pem, _ = rsa_key_pair
        auth = GitHubAuth(
            app_id="1", app_private_key=private_pem, app_installation_id="2"
        )
        # Seed an almost-expired token.
        auth._installation_token = _InstallationToken(
            token="old_token",
            expires_at=time.monotonic() + _TOKEN_REFRESH_HEADROOM_S - 1,
        )
        fake_resp = _mock_response(
            201, json_data={"token": "new_token", "expires_at": "2099-01-01T00:00:00Z"}
        )
        with patch("httpx.post", return_value=fake_resp):
            token = auth.get_token()
        assert token == "new_token"

    def test_app_token_not_refreshed_when_fresh(self, rsa_key_pair):
        """Installation token is NOT re-fetched when it has plenty of time left."""
        from oompah.github_tracker import _TOKEN_REFRESH_HEADROOM_S, _InstallationToken
        private_pem, _ = rsa_key_pair
        auth = GitHubAuth(
            app_id="1", app_private_key=private_pem, app_installation_id="2"
        )
        auth._installation_token = _InstallationToken(
            token="valid_token",
            expires_at=time.monotonic() + 3600,
        )
        with patch("httpx.post") as mock_post:
            token = auth.get_token()
        mock_post.assert_not_called()
        assert token == "valid_token"

    def test_app_auth_401_raises_tracker_error(self, rsa_key_pair):
        private_pem, _ = rsa_key_pair
        auth = GitHubAuth(
            app_id="bad", app_private_key=private_pem, app_installation_id="1"
        )
        fake_resp = _mock_response(401, text="Unauthorized")
        fake_resp.is_success = False
        with patch("httpx.post", return_value=fake_resp):
            with pytest.raises(TrackerError, match="GitHub App authentication failed"):
                auth.get_token()

    def test_app_auth_403_raises_tracker_error(self, rsa_key_pair):
        private_pem, _ = rsa_key_pair
        auth = GitHubAuth(
            app_id="1", app_private_key=private_pem, app_installation_id="bad"
        )
        fake_resp = _mock_response(403, text="Forbidden")
        fake_resp.is_success = False
        with patch("httpx.post", return_value=fake_resp):
            with pytest.raises(TrackerError, match="not authorized"):
                auth.get_token()

    def test_app_auth_timeout_raises_tracker_timeout(self, rsa_key_pair):
        private_pem, _ = rsa_key_pair
        auth = GitHubAuth(
            app_id="1", app_private_key=private_pem, app_installation_id="2"
        )
        with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
            with pytest.raises(TrackerTimeoutError, match="Timed out"):
                auth.get_token()

    # ------------------------------------------------------------------
    # PAT path
    # ------------------------------------------------------------------

    def test_pat_auth_mode(self):
        auth = GitHubAuth(pat="ghp_test_token")
        assert auth.auth_mode == "pat"

    def test_pat_get_token_returns_pat(self):
        auth = GitHubAuth(pat="ghp_test_token")
        assert auth.get_token() == "ghp_test_token"

    def test_pat_from_oompah_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_GITHUB_TOKEN", "oompah_pat_token")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("OOMPAH_GITHUB_APP_ID", raising=False)
        auth = GitHubAuth()
        assert auth.get_token() == "oompah_pat_token"

    def test_pat_from_gh_token_env(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "gh_env_token")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("OOMPAH_GITHUB_APP_ID", raising=False)
        auth = GitHubAuth()
        assert auth.get_token() == "gh_env_token"

    def test_pat_from_github_token_env(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "github_env_token")
        monkeypatch.delenv("OOMPAH_GITHUB_APP_ID", raising=False)
        auth = GitHubAuth()
        assert auth.get_token() == "github_env_token"

    # ------------------------------------------------------------------
    # gh CLI fallback path
    # ------------------------------------------------------------------

    def test_gh_cli_auth_mode(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("OOMPAH_GITHUB_APP_ID", raising=False)
        auth = GitHubAuth()
        assert auth.auth_mode == "gh_cli"

    def test_gh_cli_fallback_token(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("OOMPAH_GITHUB_APP_ID", raising=False)
        auth = GitHubAuth()
        cli_result = MagicMock()
        cli_result.returncode = 0
        cli_result.stdout = "ghs_cli_token\n"
        with patch("subprocess.run", return_value=cli_result) as mock_run:
            token = auth.get_token()
        assert token == "ghs_cli_token"
        mock_run.assert_called_once_with(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_gh_cli_not_found_returns_none(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("OOMPAH_GITHUB_APP_ID", raising=False)
        import subprocess
        auth = GitHubAuth()
        with patch("subprocess.run", side_effect=FileNotFoundError("gh not found")):
            token = auth.get_token()
        assert token is None

    def test_gh_cli_timeout_returns_none(self, monkeypatch):
        import subprocess
        monkeypatch.delenv("OOMPAH_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("OOMPAH_GITHUB_APP_ID", raising=False)
        auth = GitHubAuth()
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(["gh", "auth", "token"], 5),
        ):
            token = auth.get_token()
        assert token is None

    def test_missing_auth_returns_none_token(self, monkeypatch):
        """When no auth is configured, get_token() returns None (not an exception)."""
        monkeypatch.delenv("OOMPAH_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("OOMPAH_GITHUB_APP_ID", raising=False)
        auth = GitHubAuth()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            token = auth.get_token()
        assert token is None

    # ------------------------------------------------------------------
    # headers()
    # ------------------------------------------------------------------

    def test_headers_include_authorization_when_token_available(self):
        auth = GitHubAuth(pat="ghp_abc")
        h = auth.headers()
        assert h.get("Authorization") == "Bearer ghp_abc"
        assert h.get("Accept") == "application/vnd.github+json"
        assert "X-GitHub-Api-Version" in h

    def test_headers_no_authorization_when_no_token(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("OOMPAH_GITHUB_APP_ID", raising=False)
        auth = GitHubAuth()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            h = auth.headers()
        assert "Authorization" not in h


# ===========================================================================
# GitHubClient
# ===========================================================================


class TestGitHubClientRequest:
    """Tests for the core request method."""

    def _make_client(self, pat: str = "test_token") -> GitHubClient:
        auth = GitHubAuth(pat=pat)
        client = GitHubClient(auth=auth)
        return client

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_get_returns_json_body(self):
        client = self._make_client()
        fake_resp = _mock_response(200, json_data={"id": 1, "title": "Test issue"})
        with patch.object(client._http, "request", return_value=fake_resp):
            body, etag = client.request("GET", "/repos/owner/repo/issues/1")
        assert body == {"id": 1, "title": "Test issue"}
        assert etag is None

    def test_post_returns_json_body(self):
        client = self._make_client()
        fake_resp = _mock_response(201, json_data={"id": 2, "number": 2})
        with patch.object(client._http, "request", return_value=fake_resp):
            body, etag = client.request("POST", "/repos/owner/repo/issues", json={"title": "New"})
        assert body["number"] == 2

    def test_delete_returns_none_on_204(self):
        client = self._make_client()
        fake_resp = _mock_response(204)
        with patch.object(client._http, "request", return_value=fake_resp):
            body, etag = client.request("DELETE", "/repos/owner/repo/issues/1/labels/bug")
        assert body is None

    # ------------------------------------------------------------------
    # ETag / conditional GET
    # ------------------------------------------------------------------

    def test_etag_returned_on_200(self):
        client = self._make_client()
        fake_resp = _mock_response(200, json_data=[{"id": 1}], headers={"etag": '"abc123"'})
        with patch.object(client._http, "request", return_value=fake_resp):
            body, etag = client.request("GET", "/repos/owner/repo/issues")
        assert etag == '"abc123"'

    def test_304_returns_cached_value(self):
        client = self._make_client()
        fake_resp = _mock_response(304)
        cached = [{"id": 1, "title": "cached"}]
        with patch.object(client._http, "request", return_value=fake_resp):
            body, etag = client.request(
                "GET",
                "/repos/owner/repo/issues",
                etag='"abc123"',
                cached=cached,
            )
        assert body is cached
        assert etag == '"abc123"'

    def test_if_none_match_header_sent_when_etag_provided(self):
        client = self._make_client()
        fake_resp = _mock_response(200, json_data=[])
        with patch.object(client._http, "request", return_value=fake_resp) as mock_req:
            client.request("GET", "/path", etag='"xyz"')
        _, call_kwargs = mock_req.call_args
        assert call_kwargs["headers"].get("If-None-Match") == '"xyz"'

    # ------------------------------------------------------------------
    # Auth errors (acceptance criterion #2)
    # ------------------------------------------------------------------

    def test_401_raises_tracker_error_with_actionable_message(self):
        client = self._make_client()
        fake_resp = _mock_response(401, text="Unauthorized")
        fake_resp.is_success = False
        with patch.object(client._http, "request", return_value=fake_resp):
            with pytest.raises(TrackerError, match="GitHub API authentication failed"):
                client.request("GET", "/repos/owner/repo/issues")

    def test_403_raises_tracker_error(self):
        client = self._make_client()
        fake_resp = _mock_response(403, text="Forbidden — insufficient scope")
        fake_resp.is_success = False
        with patch.object(client._http, "request", return_value=fake_resp):
            with pytest.raises(TrackerError, match="access forbidden"):
                client.request("GET", "/repos/owner/repo/issues")

    # ------------------------------------------------------------------
    # Rate limit handling (acceptance criterion #2)
    # ------------------------------------------------------------------

    def test_429_waits_and_retries(self):
        client = self._make_client()
        rate_limited = _mock_response(
            429, text="rate limited", headers={"retry-after": "1"}
        )
        rate_limited.is_success = False
        success = _mock_response(200, json_data={"ok": True})

        responses = [rate_limited, success]
        with patch.object(client._http, "request", side_effect=responses):
            with patch.object(client, "_sleep") as mock_sleep:
                body, _ = client.request("GET", "/path")
        assert body == {"ok": True}
        mock_sleep.assert_any_call(pytest.approx(1.0, abs=0.1))

    def test_429_retry_after_header_used(self):
        client = self._make_client()
        rate_limited = _mock_response(
            429, text="rate limited", headers={"retry-after": "42"}
        )
        rate_limited.is_success = False
        success = _mock_response(200, json_data={})

        with patch.object(client._http, "request", side_effect=[rate_limited, success]):
            with patch.object(client, "_sleep") as mock_sleep:
                client.request("GET", "/path")
        # First sleep call should be for the rate-limit wait.
        first_wait = mock_sleep.call_args_list[0][0][0]
        assert first_wait >= 42.0

    def test_429_exhausted_retries_raises_tracker_error(self):
        from oompah.github_tracker import _MAX_RETRIES as max_retries
        client = self._make_client()
        rate_limited = _mock_response(
            429, text="rate limited", headers={"retry-after": "0"}
        )
        rate_limited.is_success = False
        # Return rate limited on every attempt (retries + original + 1 extra).
        responses = [rate_limited] * (max_retries + 2)
        with patch.object(client._http, "request", side_effect=responses):
            with patch.object(client, "_sleep"):
                with pytest.raises(TrackerError, match="rate limit"):
                    client.request("GET", "/path")

    # ------------------------------------------------------------------
    # Retry on transient server errors
    # ------------------------------------------------------------------

    def test_500_retries_then_succeeds(self):
        client = self._make_client()
        server_error = _mock_response(500, text="Internal Server Error")
        server_error.is_success = False
        success = _mock_response(200, json_data={"ok": True})

        with patch.object(client._http, "request", side_effect=[server_error, success]):
            with patch.object(client, "_sleep"):
                body, _ = client.request("GET", "/path")
        assert body == {"ok": True}

    def test_timeout_retries_then_raises(self):
        client = self._make_client()
        from oompah.github_tracker import _MAX_RETRIES
        side_effects = [httpx.TimeoutException("timed out")] * (_MAX_RETRIES + 1)
        with patch.object(client._http, "request", side_effect=side_effects):
            with patch.object(client, "_sleep"):
                with pytest.raises(TrackerTimeoutError):
                    client.request("GET", "/path")

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def test_get_convenience(self):
        client = self._make_client()
        fake_resp = _mock_response(200, json_data=[1, 2, 3])
        with patch.object(client._http, "request", return_value=fake_resp):
            body = client.get("/path")
        assert body == [1, 2, 3]

    def test_post_convenience(self):
        client = self._make_client()
        fake_resp = _mock_response(201, json_data={"created": True})
        with patch.object(client._http, "request", return_value=fake_resp):
            body = client.post("/path", json={"title": "x"})
        assert body == {"created": True}

    def test_patch_convenience(self):
        client = self._make_client()
        fake_resp = _mock_response(200, json_data={"updated": True})
        with patch.object(client._http, "request", return_value=fake_resp):
            body = client.patch("/path", json={"state": "closed"})
        assert body == {"updated": True}

    def test_delete_convenience(self):
        client = self._make_client()
        fake_resp = _mock_response(204)
        with patch.object(client._http, "request", return_value=fake_resp):
            body = client.delete("/path")
        assert body is None


class TestGitHubClientPagination:
    """Tests for request_paginated."""

    def _make_client(self) -> GitHubClient:
        return GitHubClient(auth=GitHubAuth(pat="token"))

    def test_single_page(self):
        client = self._make_client()
        page1 = _mock_response(200, json_data=[{"id": 1}, {"id": 2}])
        with patch.object(client._http, "request", return_value=page1):
            results = client.request_paginated("/repos/o/r/issues")
        assert results == [{"id": 1}, {"id": 2}]

    def test_multi_page_follows_next_link(self):
        client = self._make_client()
        page1 = _mock_response(
            200,
            json_data=[{"id": 1}],
            headers={
                "link": '<https://api.github.com/repos/o/r/issues?page=2>; rel="next"'
            },
        )
        page2 = _mock_response(200, json_data=[{"id": 2}])
        with patch.object(client._http, "request", side_effect=[page1, page2]):
            results = client.request_paginated("/repos/o/r/issues")
        assert results == [{"id": 1}, {"id": 2}]

    def test_pagination_auth_error_raises(self):
        client = self._make_client()
        resp_401 = _mock_response(401, text="Unauthorized")
        resp_401.is_success = False
        with patch.object(client._http, "request", return_value=resp_401):
            with pytest.raises(TrackerError, match="authentication failed"):
                client.request_paginated("/repos/o/r/issues")

    def test_pagination_timeout_raises(self):
        client = self._make_client()
        with patch.object(
            client._http,
            "request",
            side_effect=httpx.TimeoutException("timeout"),
        ):
            with pytest.raises(TrackerTimeoutError):
                client.request_paginated("/repos/o/r/issues")

    def test_pagination_rate_limit_retries_same_page(self):
        client = self._make_client()
        rl_resp = _mock_response(
            429,
            text="rate limited",
            headers={"retry-after": "0"},
        )
        rl_resp.is_success = False
        success = _mock_response(200, json_data=[{"id": 99}])
        with patch.object(client._http, "request", side_effect=[rl_resp, success]):
            with patch.object(client, "_sleep"):
                results = client.request_paginated("/repos/o/r/issues")
        assert results == [{"id": 99}]


# ===========================================================================
# GitHubIssueTracker
# ===========================================================================


class TestGitHubIssueTracker:
    """Structural tests for the tracker adapter."""

    def _make_tracker(self, pat: str = "test_token") -> GitHubIssueTracker:
        auth = GitHubAuth(pat=pat)
        return GitHubIssueTracker(
            owner="example-org",
            repo="oompah-tasks",
            active_states=["Open", "In Progress"],
            terminal_states=["Done", "Archived"],
            auth=auth,
        )

    def test_satisfies_tracker_protocol(self):
        tracker = self._make_tracker()
        assert isinstance(tracker, TrackerProtocol)

    def test_is_archived_done(self):
        tracker = self._make_tracker()
        issue = Issue(
            id="gh-1",
            identifier="example-org/oompah-tasks#1",
            title="Test",
            state="Archived",
        )
        assert tracker.is_archived(issue) is True

    def test_is_archived_non_archived(self):
        tracker = self._make_tracker()
        issue = Issue(
            id="gh-2",
            identifier="example-org/oompah-tasks#2",
            title="Active",
            state="Open",
        )
        assert tracker.is_archived(issue) is False

    def test_invalidate_read_cache(self):
        tracker = self._make_tracker()
        tracker._etag_cache["some_path"] = ('"etag"', [{"id": 1}])
        tracker.invalidate_read_cache()
        assert tracker._etag_cache == {}

    def test_fetch_candidate_issues_queries_open_issues(self):
        """fetch_candidate_issues requests state=open from GitHub."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(tracker._client._http, "request", return_value=resp) as mock_req:
            result = tracker.fetch_candidate_issues()
        assert result == []
        # Verify the request went to the issues endpoint with state=open
        call_args = mock_req.call_args
        assert "issues" in str(call_args)

    def test_fetch_all_issues_queries_all_states(self):
        """fetch_all_issues requests state=all from GitHub."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(tracker._client._http, "request", return_value=resp) as mock_req:
            result = tracker.fetch_all_issues()
        assert result == []

    def test_fetch_attachments_returns_empty_list_when_no_body_metadata(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=1, body="")
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_attachments("example-org/oompah-tasks#1")
        assert result == []

    def test_fetch_memories_returns_empty_dict(self):
        tracker = self._make_tracker()
        assert tracker.fetch_memories() == {}

    def test_get_metadata_returns_empty_dict_when_no_body_metadata(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=1, body="")
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.get_metadata("example-org/oompah-tasks#1")
        assert result == {}

    def test_create_issue_posts_to_github(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=42, title="Test issue")
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            issue = tracker.create_issue("Test issue")
        assert issue.identifier == "example-org/oompah-tasks#42"
        assert issue.title == "Test issue"

    def test_add_comment_posts_to_github(self):
        tracker = self._make_tracker()
        comment_resp = {"id": 1, "body": "**oompah**: hello", "created_at": "2024-01-01T00:00:00Z"}
        resp = _mock_response(201, json_data=comment_resp)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.add_comment("example-org/oompah-tasks#1", "hello")
        assert result["body"] == "**oompah**: hello"

    def test_repo_path_helper(self):
        tracker = self._make_tracker()
        assert tracker._repo_path() == "/repos/example-org/oompah-tasks"
        assert tracker._repo_path("/issues") == "/repos/example-org/oompah-tasks/issues"


# ===========================================================================
# Factory function
# ===========================================================================


class TestGitHubIssuesFactory:
    def test_requires_owner_env(self, monkeypatch):
        monkeypatch.delenv("OOMPAH_GITHUB_TRACKER_OWNER", raising=False)
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_REPO", "oompah-tasks")
        with pytest.raises(TrackerError, match="OOMPAH_GITHUB_TRACKER_OWNER"):
            _github_issues_factory(active_states=[], terminal_states=[])

    def test_requires_repo_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_OWNER", "example-org")
        monkeypatch.delenv("OOMPAH_GITHUB_TRACKER_REPO", raising=False)
        with pytest.raises(TrackerError, match="OOMPAH_GITHUB_TRACKER_REPO"):
            _github_issues_factory(active_states=[], terminal_states=[])

    def test_creates_tracker_with_env_config(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_OWNER", "myorg")
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_REPO", "myrepo")
        monkeypatch.setenv("OOMPAH_GITHUB_TOKEN", "ghp_test")
        tracker = _github_issues_factory(
            active_states=["Open"],
            terminal_states=["Done"],
        )
        assert isinstance(tracker, GitHubIssueTracker)
        assert tracker.owner == "myorg"
        assert tracker.repo == "myrepo"

    def test_access_token_kwarg_overrides_env_pat(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_OWNER", "myorg")
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_REPO", "myrepo")
        monkeypatch.setenv("OOMPAH_GITHUB_TOKEN", "ghp_env")

        tracker = _github_issues_factory(
            active_states=["Open"],
            terminal_states=["Done"],
            access_token="ghp_project",
        )

        assert tracker._auth._pat == "ghp_project"


# ===========================================================================
# ADAPTER_REGISTRY integration
# ===========================================================================


class TestAdapterRegistry:
    def test_github_issues_in_registry(self):
        assert "github_issues" in ADAPTER_REGISTRY

    def test_registry_factory_callable(self):
        factory = ADAPTER_REGISTRY["github_issues"]
        assert callable(factory)

    def test_registry_factory_creates_tracker_with_env(self, monkeypatch):
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_OWNER", "testorg")
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_REPO", "testrepo")
        monkeypatch.setenv("OOMPAH_GITHUB_TOKEN", "ghp_test")
        factory = ADAPTER_REGISTRY["github_issues"]
        tracker = factory(active_states=["Open"], terminal_states=["Done"])
        assert isinstance(tracker, GitHubIssueTracker)
        assert isinstance(tracker, TrackerProtocol)


# ===========================================================================
# Status encoding helpers
# ===========================================================================


class TestStatusLabelHelpers:
    """Tests for status ↔ label conversion helpers.

    Acceptance criterion #5: candidate fetch returns only configured
    dispatchable statuses.
    """

    def test_status_to_label_open(self):
        assert _status_to_label("Open") == "oompah:status:open"

    def test_status_to_label_in_progress(self):
        assert _status_to_label("In Progress") == "oompah:status:in-progress"

    def test_status_to_label_done(self):
        assert _status_to_label("Done") == "oompah:status:done"

    def test_status_to_label_needs_ci_fix(self):
        assert _status_to_label("Needs CI Fix") == "oompah:status:needs-ci-fix"

    def test_status_to_label_archived(self):
        assert _status_to_label("Archived") == "oompah:status:archived"

    def test_status_to_label_proposed(self):
        assert _status_to_label("Proposed") == "oompah:status:proposed"

    def test_label_to_status_open(self):
        assert _label_to_status("oompah:status:open") == "Open"

    def test_label_to_status_in_progress(self):
        assert _label_to_status("oompah:status:in-progress") == "In Progress"

    def test_label_to_status_done(self):
        assert _label_to_status("oompah:status:done") == "Done"

    def test_label_to_status_proposed(self):
        assert _label_to_status("oompah:status:proposed") == "Proposed"

    def test_label_to_status_non_status_label(self):
        assert _label_to_status("bug") is None
        assert _label_to_status("priority:1") is None
        assert _label_to_status("type:feature") is None

    def test_label_to_status_empty(self):
        assert _label_to_status("") is None

    def test_round_trip_canonical_statuses(self):
        """Every canonical status can be round-tripped through label encoding."""
        from oompah.statuses import CANONICAL_STATUSES
        for status in CANONICAL_STATUSES:
            label = _status_to_label(status)
            assert label.startswith("oompah:status:")
            assert _label_to_status(label) == status

    def test_extract_oompah_status_from_label(self):
        labels = [{"name": "oompah:status:in-progress"}]
        assert _extract_oompah_status(labels, "open") == "In Progress"

    def test_extract_oompah_status_fallback_open(self):
        labels: list = []
        assert _extract_oompah_status(labels, "open") == "Proposed"

    def test_extract_oompah_status_fallback_closed(self):
        labels: list = []
        assert _extract_oompah_status(labels, "closed") == "Archived"

    def test_extract_oompah_status_label_beats_gh_state(self):
        """Status label overrides GitHub built-in open state."""
        labels = [{"name": "oompah:status:needs-human"}]
        assert _extract_oompah_status(labels, "open") == "Needs Human"

    def test_extract_oompah_status_closed_overrides_non_terminal_label(self):
        labels = [{"name": "oompah:status:open"}]
        assert _extract_oompah_status(labels, "closed") == "Archived"

    def test_extract_oompah_status_closed_preserves_merged_label(self):
        labels = [{"name": "oompah:status:merged"}]
        assert _extract_oompah_status(labels, "closed") == "Merged"

    def test_extract_oompah_status_closed_preserves_archived_label(self):
        labels = [{"name": "oompah:status:archived"}]
        assert _extract_oompah_status(labels, "closed") == "Archived"

    def test_extract_priority_label(self):
        labels = [{"name": "priority:2"}]
        assert _extract_priority(labels) == 2

    def test_extract_priority_no_label(self):
        assert _extract_priority([]) is None

    def test_extract_priority_ignores_non_priority(self):
        labels = [{"name": "bug"}, {"name": "type:task"}]
        assert _extract_priority(labels) is None

    def test_extract_issue_type_feature(self):
        labels = [{"name": "type:feature"}]
        assert _extract_issue_type(labels) == "feature"

    def test_extract_issue_type_default_task(self):
        assert _extract_issue_type([]) == "task"

    def test_extract_issue_type_bug(self):
        labels = [{"name": "type:bug"}]
        assert _extract_issue_type(labels) == "bug"

    def test_extract_issue_type_epic_title_fallback(self):
        assert _extract_issue_type([], "Epic: Milestone 1") == "epic"

    def test_extract_issue_type_label_beats_epic_title(self):
        labels = [{"name": "type:feature"}]
        assert _extract_issue_type(labels, "Epic: Milestone 1") == "feature"

    def test_extract_parent_from_body_hash_reference(self):
        body = "Parent: #3\n\nWork details."
        assert _extract_parent_from_body(body) == "3"

    def test_extract_parent_from_body_qualified_reference(self):
        body = "Parent: example-org/oompah-tasks#3"
        assert _extract_parent_from_body(body) == "3"

    def test_extract_parent_from_body_github_url(self):
        body = "Parent: https://github.com/example-org/oompah-tasks/issues/3"
        assert _extract_parent_from_body(body) == "3"

    def test_parse_body_metadata_empty(self):
        assert _parse_body_metadata("") == {}
        assert _parse_body_metadata(None) == {}

    def test_parse_body_metadata_basic(self):
        body = "Issue body\n<!-- oompah:metadata\n{\"project_id\": \"proj-1\", \"target_branch\": \"main\"}\n-->"
        meta = _parse_body_metadata(body)
        assert meta["project_id"] == "proj-1"
        assert meta["target_branch"] == "main"

    def test_parse_body_metadata_no_block(self):
        assert _parse_body_metadata("Just a regular issue body.") == {}

    def test_parse_body_metadata_invalid_json(self):
        body = "<!-- oompah:metadata\nnot valid json\n-->"
        assert _parse_body_metadata(body) == {}

    def test_gh_timestamp_parses_z_suffix(self):
        ts = _gh_timestamp("2024-01-15T10:30:00Z")
        from datetime import timezone
        assert ts is not None
        assert ts.tzinfo is not None

    def test_gh_timestamp_parses_offset(self):
        ts = _gh_timestamp("2024-01-15T10:30:00+00:00")
        assert ts is not None

    def test_gh_timestamp_none(self):
        assert _gh_timestamp(None) is None
        assert _gh_timestamp("") is None


# ===========================================================================
# _gh_issue_to_issue mapper
# ===========================================================================


def _make_gh_issue(
    number: int = 1,
    title: str = "Test issue",
    state: str = "open",
    labels: list[str] | None = None,
    body: str = "",
    created_at: str = "2024-01-01T00:00:00Z",
    updated_at: str = "2024-01-02T00:00:00Z",
    closed_at: str | None = None,
    html_url: str | None = None,
    issue_id: int | None = None,
    is_pull_request: bool = False,
    user_login: str = "alice",
) -> dict:
    """Build a minimal GitHub REST API issue dict for testing."""
    payload = {
        "number": number,
        "id": issue_id or (1000 + number),
        "title": title,
        "body": body,
        "state": state,
        "labels": [{"name": lbl} for lbl in (labels or [])],
        "html_url": html_url or f"https://github.com/example-org/oompah-tasks/issues/{number}",
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
        "node_id": f"I_node_{number}",
        "user": {"login": user_login},
    }
    if is_pull_request:
        payload["html_url"] = html_url or (
            f"https://github.com/example-org/oompah-tasks/pull/{number}"
        )
        payload["pull_request"] = {
            "url": f"https://api.github.com/repos/example-org/oompah-tasks/pulls/{number}",
            "html_url": payload["html_url"],
        }
    return payload


class TestGhIssueToIssue:
    """Tests for the _gh_issue_to_issue() mapper."""

    def _convert(self, **kwargs) -> Issue:
        return _gh_issue_to_issue(
            _make_gh_issue(**kwargs), owner="example-org", repo="oompah-tasks"
        )

    def test_basic_fields(self):
        issue = self._convert(number=42, title="Fix the bug")
        assert issue.identifier == "example-org/oompah-tasks#42"
        assert issue.title == "Fix the bug"
        assert issue.tracker_owner == "example-org"
        assert issue.tracker_repo == "oompah-tasks"
        assert issue.issue_number == "42"
        assert issue.display_identifier == "oompah-tasks#42"
        assert issue.tracker_kind == "github_issues"

    def test_requestor_login_comes_from_github_issue_user(self):
        issue = self._convert(number=42, user_login="requestor")
        assert issue.requestor_login == "requestor"

    def test_proposed_status_label_is_supported(self):
        issue = self._convert(labels=["oompah:status:proposed"])
        assert issue.state == "Proposed"

    def test_state_open_defaults_to_Proposed(self):
        issue = self._convert(state="open", labels=[])
        assert issue.state == "Proposed"

    def test_state_closed_defaults_to_Archived(self):
        issue = self._convert(state="closed", labels=[])
        assert issue.state == "Archived"

    def test_status_label_overrides_state(self):
        issue = self._convert(
            state="open", labels=["oompah:status:in-progress"]
        )
        assert issue.state == "In Progress"

    def test_closed_state_overrides_non_terminal_status_label(self):
        issue = self._convert(state="closed", labels=["oompah:status:open"])
        assert issue.state == "Archived"

    def test_closed_state_preserves_merged_status_label(self):
        issue = self._convert(state="closed", labels=["oompah:status:merged"])
        assert issue.state == "Merged"

    def test_proposed_status_label_maps_to_issue_state(self):
        issue = self._convert(state="open", labels=["oompah:status:proposed"])
        assert issue.state == "Proposed"

    def test_priority_from_label(self):
        issue = self._convert(labels=["priority:3"])
        assert issue.priority == 3

    def test_priority_none_when_no_label(self):
        issue = self._convert(labels=[])
        assert issue.priority is None

    def test_issue_type_from_label(self):
        issue = self._convert(labels=["type:bug"])
        assert issue.issue_type == "bug"

    def test_issue_type_defaults_to_task(self):
        issue = self._convert(labels=[])
        assert issue.issue_type == "task"

    def test_epic_title_defaults_to_epic_type(self):
        issue = self._convert(title="Epic: Milestone 1", labels=[])
        assert issue.issue_type == "epic"

    def test_user_labels_exclude_internal(self):
        issue = self._convert(
            labels=["oompah:status:open", "priority:1", "type:feature", "needs:frontend"]
        )
        assert issue.labels == ["needs:frontend"]

    def test_intake_metadata_maps_to_issue(self):
        body = (
            "Issue body\n"
            "<!-- oompah:metadata\n"
            '{"intake": {"missing_fields": ["acceptance_criteria"], '
            '"last_validator_result": "fail"}}\n'
            "-->"
        )
        issue = self._convert(body=body)

        assert issue.intake == {
            "missing_fields": ["acceptance_criteria"],
            "last_validator_result": "fail",
        }

    def test_url_set(self):
        issue = self._convert(
            number=5, html_url="https://github.com/example-org/oompah-tasks/issues/5"
        )
        assert issue.url == "https://github.com/example-org/oompah-tasks/issues/5"
        assert issue.provider_url == issue.url

    def test_timestamps_parsed(self):
        issue = self._convert(
            created_at="2024-03-01T12:00:00Z",
            updated_at="2024-03-02T08:00:00Z",
            closed_at="2024-03-03T09:00:00Z",
        )
        from datetime import timezone
        assert issue.created_at is not None
        assert issue.updated_at is not None
        assert issue.closed_at is not None
        assert issue.created_at.tzinfo is not None

    def test_closed_at_none_when_open(self):
        issue = self._convert(state="open", closed_at=None)
        assert issue.closed_at is None

    def test_description_from_body(self):
        issue = self._convert(body="This is the description.")
        assert issue.description == "This is the description."

    def test_description_strips_metadata_block(self):
        body = "Visible text.\n<!-- oompah:metadata\n{\"project_id\": \"p1\"}\n-->"
        issue = self._convert(body=body)
        assert issue.description == "Visible text."
        assert issue.project_id == "p1"

    def test_description_none_when_empty_body(self):
        issue = self._convert(body="")
        assert issue.description is None

    def test_target_branch_from_metadata(self):
        body = '<!-- oompah:metadata\n{"target_branch": "release/1.2"}\n-->'
        issue = self._convert(body=body)
        assert issue.target_branch == "release/1.2"

    def test_review_metadata_maps_to_issue(self):
        body = (
            '<!-- oompah:metadata\n'
            '{"review_url":"https://github.com/org/repo/pull/7",'
            '"review_number":"7"}\n-->'
        )
        issue = self._convert(body=body)
        assert issue.review_url == "https://github.com/org/repo/pull/7"
        assert issue.review_number == "7"

    def test_release_pick_metadata_from_metadata(self):
        body = (
            '<!-- oompah:metadata\n'
            '{"backports":[{"branch":"release/1.0","status":"waiting"}],'
            '"backport_of":{"source":"TASK-1","status":"task_created"}}\n-->'
        )
        issue = self._convert(body=body)
        assert issue.backports == [{"branch": "release/1.0", "status": "waiting"}]
        assert issue.backport_of == {"source": "TASK-1", "status": "task_created"}
        assert issue.release_pick_metadata_loaded is True

    def test_project_id_from_metadata(self):
        body = '<!-- oompah:metadata\n{"project_id": "myproject"}\n-->'
        issue = self._convert(body=body)
        assert issue.project_id == "myproject"

    def test_id_uses_canonical_identifier(self):
        """issue.id must equal issue.identifier (canonical form) so that
        ID-based lookups are consistent across the tracker protocol."""
        issue = self._convert(number=7, issue_id=99999)
        assert issue.id == issue.identifier
        assert issue.id == "example-org/oompah-tasks#7"


# ===========================================================================
# GitHubIssueTracker — issue fetch methods
# ===========================================================================


class TestGitHubIssueTrackerFetch:
    """Tests for issue fetch and status filtering methods.

    Acceptance criterion #5: candidate fetch returns only configured
    dispatchable statuses.
    Acceptance criterion #6: pagination and empty result sets are tested.
    """

    def _make_tracker(self) -> GitHubIssueTracker:
        auth = GitHubAuth(pat="test_token")
        return GitHubIssueTracker(
            owner="example-org",
            repo="oompah-tasks",
            active_states=["Open", "In Progress", "Needs CI Fix", "Needs Rebase"],
            terminal_states=["Done", "Merged", "Archived"],
            auth=auth,
        )

    # ------------------------------------------------------------------
    # fetch_all_issues
    # ------------------------------------------------------------------

    def test_fetch_all_issues_empty(self):
        """Empty repository returns empty list (acceptance criterion #6)."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_all_issues()
        assert result == []

    def test_fetch_all_issues_returns_issues(self):
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=1, title="First", labels=["oompah:status:open"]),
            _make_gh_issue(number=2, title="Second", labels=["oompah:status:open"]),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_all_issues()
        assert len(result) == 2
        assert result[0].title == "First"
        assert result[1].title == "Second"

    def test_fetch_all_issues_excludes_pull_requests_even_with_status_label(self):
        """GitHub's issues API includes PRs; oompah must not treat them as tasks."""
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=1, title="Real issue", labels=["oompah:status:open"]),
            _make_gh_issue(
                number=270,
                title="example-org/oompah#268: task PR",
                labels=["oompah:status:backlog"],
                is_pull_request=True,
            ),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_all_issues()
        assert [issue.issue_number for issue in result] == ["1"]

    def test_fetch_all_issues_does_not_backfill_pull_request_status_label(self):
        """PR payloads without status labels are skipped before label backfill."""
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(
                number=270,
                labels=[],
                is_pull_request=True,
            ),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            result = tracker.fetch_all_issues()
        assert result == []
        assert m.call_count == 1

    def test_fetch_all_issues_backfills_missing_status_labels(self):
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=1, state="open", labels=[]),
            _make_gh_issue(number=2, state="closed", labels=[]),
        ]
        list_resp = _mock_response(200, json_data=gh_issues)
        patch_resp_1 = _mock_response(200, json_data={"ok": True})
        patch_resp_2 = _mock_response(200, json_data={"ok": True})
        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[list_resp, patch_resp_1, patch_resp_2],
        ) as mock_req:
            result = tracker.fetch_all_issues()

        assert [issue.state for issue in result] == ["Proposed", "Archived"]
        first_patch = mock_req.call_args_list[1]
        second_patch = mock_req.call_args_list[2]
        assert first_patch[0][0] == "PATCH"
        assert first_patch[1]["json"]["labels"] == ["oompah:status:proposed"]
        assert second_patch[0][0] == "PATCH"
        assert second_patch[1]["json"]["labels"] == ["oompah:status:archived"]
        assert tracker._trusted_status_ledger[1] == "Proposed"
        assert tracker._trusted_status_ledger[2] == "Archived"

    def test_backfill_records_backlog_status_as_trusted(self, monkeypatch):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=3, state="open", labels=["bug"])
        patch_resp = _mock_response(200, json_data={"ok": True})

        from oompah import github_tracker

        monkeypatch.setattr(
            github_tracker,
            "_github_fallback_status",
            lambda _gh_state: "Backlog",
        )

        with patch.object(
            tracker._client._http,
            "request",
            return_value=patch_resp,
        ) as mock_req:
            updated = tracker._ensure_status_label(gh_issue)

        patch_call = mock_req.call_args
        assert patch_call[0][0] == "PATCH"
        assert patch_call[1]["json"]["labels"] == [
            "bug",
            "oompah:status:backlog",
        ]
        assert updated["labels"] == [
            {"name": "bug"},
            {"name": "oompah:status:backlog"},
        ]
        assert tracker._trusted_status_ledger[3] == "Backlog"

    def test_fetch_all_issues_uses_fallback_state_when_backfill_fails(self):
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=1, state="open", labels=[]),
            _make_gh_issue(number=2, state="closed", labels=[]),
        ]

        with (
            patch.object(tracker._client, "request_paginated", return_value=gh_issues),
            patch.object(
                tracker._client,
                "patch",
                side_effect=TrackerError("backfill failed"),
            ),
        ):
            result = tracker.fetch_all_issues()

        assert [issue.state for issue in result] == ["Proposed", "Archived"]

    def test_fetch_all_issues_pagination(self):
        """fetch_all_issues follows pagination links (acceptance criterion #6)."""
        tracker = self._make_tracker()
        page1 = _mock_response(
            200,
            json_data=[_make_gh_issue(number=1, labels=["oompah:status:open"])],
            headers={
                "link": '<https://api.github.com/repos/example-org/oompah-tasks/issues?page=2>; rel="next"'
            },
        )
        page2 = _mock_response(
            200,
            json_data=[_make_gh_issue(number=2, labels=["oompah:status:open"])],
        )
        with patch.object(
            tracker._client._http, "request", side_effect=[page1, page2]
        ):
            result = tracker.fetch_all_issues()
        assert len(result) == 2
        assert {iss.issue_number for iss in result} == {"1", "2"}

    def test_fetch_all_issues_sets_state_all(self):
        """fetch_all_issues requests state=all to include closed issues."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http, "request", return_value=resp
        ) as mock_req:
            tracker.fetch_all_issues()
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        assert params.get("state") == "all"

    def test_fetch_all_issues_enriched_same_as_all(self):
        """fetch_all_issues_enriched delegates to fetch_all_issues."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[_make_gh_issue(number=3)])
        with patch.object(tracker._client._http, "request", return_value=resp):
            all_issues = tracker.fetch_all_issues()
        resp2 = _mock_response(200, json_data=[_make_gh_issue(number=3)])
        with patch.object(tracker._client._http, "request", return_value=resp2):
            enriched = tracker.fetch_all_issues_enriched()
        assert len(all_issues) == len(enriched)

    # ------------------------------------------------------------------
    # fetch_candidate_issues — acceptance criterion #5
    # ------------------------------------------------------------------

    def test_fetch_candidate_issues_empty_repo(self):
        """fetch_candidate_issues handles empty response (criterion #6)."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_candidate_issues()
        assert result == []

    def test_fetch_candidate_issues_only_active_states(self):
        """Only issues in configured active_states are returned (criterion #5)."""
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=1, labels=["oompah:status:open"]),
            _make_gh_issue(number=2, labels=["oompah:status:in-progress"]),
            _make_gh_issue(number=3, labels=["oompah:status:done"]),     # terminal — excluded
            _make_gh_issue(number=4, labels=["oompah:status:archived"]), # terminal — excluded
            _make_gh_issue(number=5, labels=["oompah:status:backlog"]),  # not in active — excluded
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_candidate_issues()
        returned_numbers = {iss.issue_number for iss in result}
        assert "1" in returned_numbers
        assert "2" in returned_numbers
        assert "3" not in returned_numbers
        assert "4" not in returned_numbers
        assert "5" not in returned_numbers

    def test_fetch_candidate_issues_excludes_proposed_even_if_configured_active(self):
        """Proposed remains pre-work and is never returned as a candidate."""
        tracker = self._make_tracker()
        tracker.active_states.append("Proposed")
        gh_issues = [
            _make_gh_issue(number=1, labels=["oompah:status:proposed"]),
            _make_gh_issue(number=2, labels=["oompah:status:open"]),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_candidate_issues()

        assert [issue.issue_number for issue in result] == ["2"]

    def test_fetch_candidate_issues_excludes_pull_requests_with_active_status(self):
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=1, labels=["oompah:status:open"]),
            _make_gh_issue(
                number=270,
                labels=["oompah:status:open"],
                is_pull_request=True,
            ),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_candidate_issues()
        assert [issue.issue_number for issue in result] == ["1"]

    def test_fetch_candidate_issues_excludes_non_active(self):
        """Issues whose oompah status is not in active_states are excluded."""
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=10, labels=["oompah:status:needs-human"]),
            _make_gh_issue(number=11, labels=["oompah:status:in-review"]),
            _make_gh_issue(number=12, labels=["oompah:status:needs-ci-fix"]),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_candidate_issues()
        returned_numbers = {iss.issue_number for iss in result}
        # Only "Needs CI Fix" is in active_states for this tracker
        assert "12" in returned_numbers
        assert "10" not in returned_numbers
        assert "11" not in returned_numbers

    def test_fetch_candidate_issues_open_github_state_defaults_to_proposed(self):
        """GitHub open issues with no status label default to non-dispatchable Proposed."""
        tracker = self._make_tracker()
        gh_issues = [_make_gh_issue(number=7, state="open", labels=[])]
        list_resp = _mock_response(200, json_data=gh_issues)
        patch_resp = _mock_response(200, json_data={"ok": True})
        with patch.object(
            tracker._client._http, "request", side_effect=[list_resp, patch_resp]
        ) as mock_req:
            result = tracker.fetch_candidate_issues()
        assert result == []
        patch_call = mock_req.call_args_list[1]
        assert patch_call[0][0] == "PATCH"
        assert patch_call[1]["json"]["labels"] == ["oompah:status:proposed"]

    def test_fetch_candidate_issues_sorted_by_priority(self):
        """Candidates are sorted by priority ascending (lower = higher priority)."""
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=3, labels=["oompah:status:open", "priority:3"]),
            _make_gh_issue(number=1, labels=["oompah:status:open", "priority:1"]),
            _make_gh_issue(number=2, labels=["oompah:status:open", "priority:2"]),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_candidate_issues()
        assert [iss.priority for iss in result] == [1, 2, 3]

    def test_fetch_candidate_issues_no_priority_last(self):
        """Issues without a priority label sort after those with priority."""
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=1, labels=["oompah:status:open"]),           # no priority
            _make_gh_issue(number=2, labels=["oompah:status:open", "priority:1"]),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_candidate_issues()
        assert result[0].issue_number == "2"
        assert result[1].issue_number == "1"

    def test_fetch_candidate_issues_requests_open_state(self):
        """fetch_candidate_issues queries GitHub for open issues only."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http, "request", return_value=resp
        ) as mock_req:
            tracker.fetch_candidate_issues()
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        assert params.get("state") == "open"

    def test_fetch_candidate_issues_pagination(self):
        """fetch_candidate_issues follows pagination links (criterion #6)."""
        tracker = self._make_tracker()
        page1 = _mock_response(
            200,
            json_data=[_make_gh_issue(number=1, labels=["oompah:status:open"])],
            headers={
                "link": '<https://api.github.com/repos/example-org/oompah-tasks/issues?page=2>; rel="next"'
            },
        )
        page2 = _mock_response(
            200,
            json_data=[_make_gh_issue(number=2, labels=["oompah:status:open"])],
        )
        with patch.object(
            tracker._client._http, "request", side_effect=[page1, page2]
        ):
            result = tracker.fetch_candidate_issues()
        assert len(result) == 2

    # ------------------------------------------------------------------
    # fetch_issue_detail
    # ------------------------------------------------------------------

    def test_fetch_issue_detail_returns_issue(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=42, title="Detail test")
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_issue_detail("example-org/oompah-tasks#42")
        assert result is not None
        assert result.title == "Detail test"
        assert result.issue_number == "42"

    def test_fetch_issue_detail_open_unlabeled_defaults_to_proposed(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=42, state="open", labels=[])
        patch_resp = _mock_response(200, json_data={"ok": True})

        with (
            patch.object(tracker._client, "request", return_value=(gh_issue, None)),
            patch.object(tracker._client, "patch", return_value=patch_resp) as patch_call,
        ):
            result = tracker.fetch_issue_detail("example-org/oompah-tasks#42")

        assert result is not None
        assert result.state == "Proposed"
        patch_call.assert_called_once()
        assert patch_call.call_args.kwargs["json"]["labels"] == [
            "oompah:status:proposed"
        ]

    def test_fetch_issue_detail_closed_unlabeled_defaults_to_archived(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=43, state="closed", labels=[])
        patch_resp = _mock_response(200, json_data={"ok": True})

        with (
            patch.object(tracker._client, "request", return_value=(gh_issue, None)),
            patch.object(tracker._client, "patch", return_value=patch_resp) as patch_call,
        ):
            result = tracker.fetch_issue_detail("example-org/oompah-tasks#43")

        assert result is not None
        assert result.state == "Archived"
        patch_call.assert_called_once()
        assert patch_call.call_args.kwargs["json"]["labels"] == [
            "oompah:status:archived"
        ]

    def test_fetch_issue_detail_closed_non_terminal_label_is_archived(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(
            number=44,
            state="closed",
            labels=["oompah:status:open", "bug"],
        )
        patch_resp = _mock_response(200, json_data={"ok": True})

        with (
            patch.object(tracker._client, "request", return_value=(gh_issue, None)),
            patch.object(tracker._client, "patch", return_value=patch_resp) as patch_call,
        ):
            result = tracker.fetch_issue_detail("example-org/oompah-tasks#44")

        assert result is not None
        assert result.state == "Archived"
        patch_call.assert_called_once()
        assert patch_call.call_args.kwargs["json"]["labels"] == [
            "bug",
            "oompah:status:archived",
        ]

    def test_fetch_issue_detail_closed_merged_label_is_not_rewritten(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(
            number=45,
            state="closed",
            labels=["oompah:status:merged"],
        )

        with (
            patch.object(tracker._client, "request", return_value=(gh_issue, None)),
            patch.object(tracker._client, "patch") as patch_call,
        ):
            result = tracker.fetch_issue_detail("example-org/oompah-tasks#45")

        assert result is not None
        assert result.state == "Merged"
        patch_call.assert_not_called()

    def test_fetch_issue_detail_returns_none_for_404(self):
        tracker = self._make_tracker()
        resp_404 = _mock_response(404, text="Not Found")
        resp_404.is_success = False
        with patch.object(tracker._client._http, "request", return_value=resp_404):
            result = tracker.fetch_issue_detail("example-org/oompah-tasks#9999")
        assert result is None

    def test_fetch_issue_detail_returns_none_for_invalid_identifier(self):
        tracker = self._make_tracker()
        result = tracker.fetch_issue_detail("not-an-identifier")
        assert result is None

    def test_fetch_issue_detail_returns_none_for_bare_number(self):
        tracker = self._make_tracker()
        result = tracker.fetch_issue_detail("42")
        assert result is None

    def test_fetch_issue_detail_returns_none_for_pull_request(self):
        tracker = self._make_tracker()
        gh_pr = _make_gh_issue(
            number=270,
            labels=["oompah:status:backlog"],
            is_pull_request=True,
        )
        resp = _mock_response(200, json_data=gh_pr)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_issue_detail("example-org/oompah-tasks#270")
        assert result is None

    # ------------------------------------------------------------------
    # fetch_issues_by_states
    # ------------------------------------------------------------------

    def test_fetch_issues_by_states_empty_input(self):
        tracker = self._make_tracker()
        result = tracker.fetch_issues_by_states([])
        assert result == []

    def test_fetch_issues_by_states_active_only(self):
        """Requesting only active states queries GitHub with state=open."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http, "request", return_value=resp
        ) as mock_req:
            tracker.fetch_issues_by_states(["Open", "In Progress"])
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        assert params.get("state") == "open"

    def test_fetch_issues_by_states_done_only_queries_all(self):
        """Done is written open but old closed-Done issues must still be found."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http, "request", return_value=resp
        ) as mock_req:
            tracker.fetch_issues_by_states(["Done"])
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        assert params.get("state") == "all"

    def test_fetch_issues_by_states_github_closed_terminal_only(self):
        """Merged and Archived map to GitHub state=closed."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http, "request", return_value=resp
        ) as mock_req:
            tracker.fetch_issues_by_states(["Merged", "Archived"])
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        assert params.get("state") == "closed"

    def test_fetch_issues_by_states_mixed(self):
        """Mixed GitHub-open and GitHub-closed statuses query state=all."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http, "request", return_value=resp
        ) as mock_req:
            tracker.fetch_issues_by_states(["Done", "Archived"])
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        assert params.get("state") == "all"

    def test_fetch_issues_by_states_filters_in_memory(self):
        """Only issues matching the requested states are returned."""
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=1, labels=["oompah:status:open"]),
            _make_gh_issue(number=2, labels=["oompah:status:in-progress"]),
            _make_gh_issue(number=3, labels=["oompah:status:done"], state="closed"),
            _make_gh_issue(
                number=270,
                labels=["oompah:status:open"],
                is_pull_request=True,
            ),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_issues_by_states(["Open"])
        assert len(result) == 1
        assert result[0].state == "Open"

    def test_fetch_issues_by_states_empty_response(self):
        """Empty API response returns empty list (criterion #6)."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_issues_by_states(["Open", "Done"])
        assert result == []

    # ------------------------------------------------------------------
    # fetch_issue_states_by_ids
    # ------------------------------------------------------------------

    def test_fetch_issue_states_by_ids_empty_list(self):
        """Empty input returns empty list without making any HTTP calls."""
        tracker = self._make_tracker()
        result = tracker.fetch_issue_states_by_ids([])
        assert result == []

    def test_fetch_issue_states_by_ids_returns_snapshots(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=5, labels=["oompah:status:in-progress"])
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_issue_states_by_ids(["example-org/oompah-tasks#5"])
        assert len(result) == 1
        assert result[0].state == "In Progress"

    def test_fetch_issue_states_by_ids_skips_invalid(self):
        """Invalid or missing identifiers are silently skipped."""
        tracker = self._make_tracker()
        resp_valid = _mock_response(
            200,
            json_data=_make_gh_issue(number=1, labels=["oompah:status:open"]),
        )
        resp_404 = _mock_response(404, text="Not Found")
        resp_404.is_success = False
        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[resp_valid, resp_404],
        ):
            result = tracker.fetch_issue_states_by_ids([
                "example-org/oompah-tasks#1",
                "example-org/oompah-tasks#9999",
            ])
        assert len(result) == 1

    # ------------------------------------------------------------------
    # fetch_issues_by_labels
    # ------------------------------------------------------------------

    def test_fetch_issues_by_labels_empty_labels(self):
        tracker = self._make_tracker()
        result = tracker.fetch_issues_by_labels([])
        assert result == []

    def test_fetch_issues_by_labels_passes_labels_to_api(self):
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http, "request", return_value=resp
        ) as mock_req:
            tracker.fetch_issues_by_labels(["needs:frontend"])
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        assert "needs:frontend" in params.get("labels", "")

    def test_fetch_issues_by_labels_with_state_filter(self):
        tracker = self._make_tracker()
        gh_issues = [
            _make_gh_issue(number=1, labels=["needs:frontend", "oompah:status:open"]),
            _make_gh_issue(number=2, labels=["needs:frontend", "oompah:status:in-progress"]),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_issues_by_labels(
                ["needs:frontend"], states=["Open"]
            )
        assert len(result) == 1
        assert result[0].state == "Open"

    def test_fetch_issues_by_labels_with_done_state_queries_all(self):
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http, "request", return_value=resp
        ) as mock_req:
            tracker.fetch_issues_by_labels(["component:ui"], states=["Done"])
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        assert params.get("state") == "all"

    # ------------------------------------------------------------------
    # fetch_comments
    # ------------------------------------------------------------------

    def test_fetch_comments_returns_list(self):
        tracker = self._make_tracker()
        comments = [
            {"id": 1, "body": "First comment", "user": {"login": "alice"}},
            {"id": 2, "body": "Second comment", "user": {"login": "bob"}},
        ]
        resp = _mock_response(200, json_data=comments)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_comments("example-org/oompah-tasks#5")
        assert len(result) == 2
        assert result[0]["body"] == "First comment"

    def test_fetch_comments_returns_empty_for_invalid_identifier(self):
        tracker = self._make_tracker()
        result = tracker.fetch_comments("not-valid")
        assert result == []

    def test_fetch_comments_empty_issue(self):
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_comments("example-org/oompah-tasks#1")
        assert result == []

    # ------------------------------------------------------------------
    # fetch_children
    # ------------------------------------------------------------------

    def test_fetch_children_returns_empty_for_invalid_identifier(self):
        tracker = self._make_tracker()
        result = tracker.fetch_children("not-valid")
        assert result == []

    def test_fetch_children_sub_issues_api(self):
        """Uses the sub-issues endpoint when available."""
        tracker = self._make_tracker()
        children = [
            _make_gh_issue(
                number=10,
                title="Child 1",
                labels=["oompah:status:open"],
            ),
            _make_gh_issue(
                number=11,
                title="Child 2",
                labels=["oompah:status:open"],
            ),
        ]
        sub_issues_resp = _mock_response(200, json_data=children)
        label_resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[sub_issues_resp, label_resp],
        ):
            result = tracker.fetch_children("example-org/oompah-tasks#5")
        assert len(result) == 2
        assert {child.parent_id for child in result} == {"example-org/oompah-tasks#5"}

    def test_fetch_children_falls_back_to_label_on_404(self):
        """Falls back to label-based lookup when sub-issues API is unavailable."""
        tracker = self._make_tracker()
        resp_404 = _mock_response(404, text="Not Found")
        resp_404.is_success = False
        children = [
            _make_gh_issue(
                number=20,
                labels=["parent:5", "oompah:status:open"],
            )
        ]
        resp_200 = _mock_response(200, json_data=children)
        with patch.object(
            tracker._client._http, "request", side_effect=[resp_404, resp_200]
        ):
            result = tracker.fetch_children("example-org/oompah-tasks#5")
        assert len(result) == 1

    def test_fetch_children_checks_parent_label_when_sub_issues_empty(self):
        """Label-only children still count when GitHub returns no sub-issues."""
        tracker = self._make_tracker()
        sub_issues_resp = _mock_response(200, json_data=[])
        children = [
            _make_gh_issue(
                number=20,
                labels=["parent:5", "oompah:status:open"],
            )
        ]
        label_resp = _mock_response(200, json_data=children)
        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[sub_issues_resp, label_resp],
        ):
            result = tracker.fetch_children("example-org/oompah-tasks#5")
        assert len(result) == 1
        assert result[0].identifier == "example-org/oompah-tasks#20"
        assert result[0].parent_id == "example-org/oompah-tasks#5"

    # ------------------------------------------------------------------
    # Issue field mapping on normalized Issue record
    # ------------------------------------------------------------------

    def test_fetch_all_issues_normalizes_fields(self):
        """Normalized Issue records carry all expected fields."""
        tracker = self._make_tracker()
        body = (
            '<!-- oompah:metadata\n'
            '{"project_id":"proj-1","target_branch":"main",'
            '"backports":["release/1.0"],"backport_of":"TASK-1"}\n-->'
        )
        gh_issue = _make_gh_issue(
            number=7,
            title="Normalize me",
            labels=["priority:2", "type:feature", "needs:backend"],
            body=body,
        )
        resp = _mock_response(200, json_data=[gh_issue])
        with patch.object(tracker._client._http, "request", return_value=resp):
            issues = tracker.fetch_all_issues()
        assert len(issues) == 1
        iss = issues[0]
        assert iss.priority == 2
        assert iss.issue_type == "feature"
        assert "needs:backend" in iss.labels
        assert iss.project_id == "proj-1"
        assert iss.target_branch == "main"
        assert iss.backports == ["release/1.0"]
        assert iss.backport_of == "TASK-1"
        assert iss.release_pick_metadata_loaded is True
        assert iss.tracker_kind == "github_issues"


# ===========================================================================
# Mutation methods (TASK-458.4)
# ===========================================================================


class TestGitHubIssueTrackerMutations:
    """Tests for create_issue, update_issue, close_issue, reopen_issue,
    archive_issue, mark_needs_human, add_comment, add_label, remove_label,
    and the private helper methods introduced in TASK-458.4.

    Acceptance criteria:
      #1  Create returns a fully qualified GitHub issue identifier and URL.
      #2  Status, comments, and labels round-trip through mocked GitHub APIs.
    """

    def _make_tracker(self) -> GitHubIssueTracker:
        auth = GitHubAuth(pat="test_token")
        return GitHubIssueTracker(
            owner="example-org",
            repo="oompah-tasks",
            active_states=["Open", "In Progress", "Needs CI Fix"],
            terminal_states=["Done", "Merged", "Archived"],
            auth=auth,
        )

    # ------------------------------------------------------------------
    # create_issue
    # ------------------------------------------------------------------

    def test_create_issue_returns_normalized_issue(self):
        """AC#1: create returns a fully qualified identifier and URL."""
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=99, title="My new task")
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            issue = tracker.create_issue("My new task")
        assert issue.identifier == "example-org/oompah-tasks#99"
        assert issue.url is not None
        assert "99" in issue.url
        assert issue.title == "My new task"

    def test_create_issue_sends_status_label(self):
        """create_issue includes an oompah:status:* label in the POST."""
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=10, labels=["oompah:status:open"])
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("Task with status", initial_status="Open")
        call_kwargs = m.call_args[1]
        labels_sent = call_kwargs["json"]["labels"]
        assert "oompah:status:open" in labels_sent

    def test_create_issue_done_status_does_not_close_github_issue(self):
        """New Done issues keep GitHub state=open for review reconciliation."""
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(
            number=101,
            labels=["oompah:status:done"],
            state="open",
        )
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("Done task", initial_status="Done")
        assert m.call_count == 1
        assert m.call_args[1]["json"]["labels"] == ["oompah:status:done"]

    def test_create_issue_archived_status_closes_github_issue(self):
        """Archived issues are terminal in both oompah and GitHub."""
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(
            number=102,
            labels=["oompah:status:archived"],
            state="open",
        )
        responses = [
            _mock_response(201, json_data=gh_issue),
            _mock_response(200, json_data={**gh_issue, "state": "closed"}),
        ]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.create_issue("Archived task", initial_status="Archived")
        assert m.call_count == 2
        patch_call = m.call_args_list[-1]
        assert patch_call[0][0] == "PATCH"
        assert patch_call[1]["json"]["state"] == "closed"

    def test_create_issue_uses_first_active_state_when_no_status(self):
        """When initial_status is None, the first active state is used."""
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=11)
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("No status")
        call_kwargs = m.call_args[1]
        labels_sent = call_kwargs["json"]["labels"]
        # "Open" is the first active state → "oompah:status:open"
        assert "oompah:status:open" in labels_sent

    def test_create_issue_sends_priority_label(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=12, labels=["priority:2", "oompah:status:open"])
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("Prio task", priority=2)
        call_kwargs = m.call_args[1]
        assert "priority:2" in call_kwargs["json"]["labels"]

    def test_create_issue_accepts_named_priority(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=12, labels=["priority:1", "oompah:status:open"])
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("Prio task", priority="high")
        call_kwargs = m.call_args[1]
        assert "priority:1" in call_kwargs["json"]["labels"]

    def test_create_issue_sends_type_label_for_non_task(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=13, labels=["type:bug", "oompah:status:open"])
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("Bug", issue_type="bug")
        call_kwargs = m.call_args[1]
        assert "type:bug" in call_kwargs["json"]["labels"]

    def test_create_issue_omits_type_label_for_default_task(self):
        """Default issue_type='task' should NOT add a type:task label."""
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=14)
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("Default task", issue_type="task")
        call_kwargs = m.call_args[1]
        labels_sent = call_kwargs["json"]["labels"]
        assert "type:task" not in labels_sent

    def test_create_issue_includes_user_labels(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=15, labels=["needs:backend", "oompah:status:open"])
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("Label task", labels=["needs:backend"])
        call_kwargs = m.call_args[1]
        assert "needs:backend" in call_kwargs["json"]["labels"]

    def test_create_issue_sends_body_when_description_given(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=16, body="Do the thing.")
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("Task with desc", description="Do the thing.")
        call_kwargs = m.call_args[1]
        assert call_kwargs["json"]["body"] == "Do the thing."

    def test_create_issue_no_body_when_no_description(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=17)
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("No desc")
        call_kwargs = m.call_args[1]
        assert "body" not in call_kwargs["json"]

    def test_create_issue_posts_to_issues_endpoint(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=18)
        resp = _mock_response(201, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.create_issue("Endpoint test")
        call_args = m.call_args
        assert call_args[0][0] == "POST"
        assert "/repos/example-org/oompah-tasks/issues" in str(call_args)

    def test_create_issue_raises_on_bad_response(self):
        tracker = self._make_tracker()
        # Simulate a 422 Unprocessable Entity.
        resp = _mock_response(422, text="Validation failed")
        with patch.object(tracker._client._http, "request", return_value=resp):
            from oompah.tracker import TrackerError
            with pytest.raises(TrackerError):
                tracker.create_issue("Bad issue")

    # ------------------------------------------------------------------
    # update_issue
    # ------------------------------------------------------------------

    def test_update_issue_title(self):
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=_make_gh_issue(number=5, title="New title"))
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.update_issue("example-org/oompah-tasks#5", title="New title")
        patch_call = m.call_args
        assert patch_call[0][0] == "PATCH"
        assert patch_call[1]["json"]["title"] == "New title"

    def test_update_issue_description_preserves_metadata(self):
        """Updating description fetches current body and preserves metadata block."""
        tracker = self._make_tracker()
        meta_block = '<!-- oompah:metadata\n{"project_id": "p1"}\n-->'
        full_body = f"Old description.\n\n{meta_block}"
        gh_issue = _make_gh_issue(number=6, body=full_body)
        get_resp = _mock_response(200, json_data=gh_issue)
        patch_resp = _mock_response(200, json_data=gh_issue)
        responses = [get_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.update_issue(
                "example-org/oompah-tasks#6", description="New description."
            )
        patch_call = m.call_args_list[1]
        new_body = patch_call[1]["json"]["body"]
        assert "New description." in new_body
        assert meta_block in new_body
        assert "Old description." not in new_body

    def test_update_issue_status_done_swaps_label_and_keeps_open(self):
        """Updating status to Done keeps GitHub state=open for review handoff."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "oompah:status:open"}])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=7, state="open"))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.update_issue("example-org/oompah-tasks#7", status="Done")
        last_call = m.call_args_list[-1]
        assert last_call[0][0] == "PATCH"
        assert last_call[1]["json"]["state"] == "open"
        assert "oompah:status:done" in last_call[1]["json"]["labels"]
        assert "oompah:status:open" not in last_call[1]["json"]["labels"]
        assert tracker._trusted_status_ledger[7] == "Done"

    def test_update_issue_status_merged_swaps_label_and_closes(self):
        """Updating status to Merged closes the native GitHub issue."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "oompah:status:done"}])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=7, state="closed"))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.update_issue("example-org/oompah-tasks#7", status="Merged")
        last_call = m.call_args_list[-1]
        assert last_call[0][0] == "PATCH"
        assert last_call[1]["json"]["state"] == "closed"
        assert "oompah:status:merged" in last_call[1]["json"]["labels"]
        assert "oompah:status:done" not in last_call[1]["json"]["labels"]

    def test_update_issue_status_failure_does_not_apply_separate_label_ops(self):
        """A rejected terminal-state PATCH must not leave a Done label behind."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(
            200,
            json_data=[
                {"name": "oompah:status:open"},
                {"name": "component:ui"},
            ],
        )
        patch_resp = _mock_response(401, text="Unauthorized")
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            with pytest.raises(TrackerError, match="authentication failed"):
                tracker.update_issue("example-org/oompah-tasks#7", status="Done")

        methods = [call[0][0] for call in m.call_args_list]
        assert methods == ["GET", "PATCH"]
        patch_payload = m.call_args_list[-1][1]["json"]
        assert patch_payload["state"] == "open"
        assert patch_payload["labels"] == ["component:ui", "oompah:status:done"]

    def test_update_issue_status_active_opens_issue(self):
        """Updating status to an active state sets state=open."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "oompah:status:done"}])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=8, state="open"))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.update_issue("example-org/oompah-tasks#8", status="Open")
        last_call = m.call_args_list[-1]
        assert last_call[1]["json"]["state"] == "open"
        assert "oompah:status:open" in last_call[1]["json"]["labels"]
        assert "oompah:status:done" not in last_call[1]["json"]["labels"]

    def test_update_issue_priority_swaps_label(self):
        """update_issue priority removes old priority:* label and adds new one."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "priority:3"}])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=9))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.update_issue("example-org/oompah-tasks#9", priority=1)
        patch_call = m.call_args_list[-1]
        assert patch_call[0][0] == "PATCH"
        assert "priority:1" in patch_call[1]["json"]["labels"]
        assert "priority:3" not in patch_call[1]["json"]["labels"]

    def test_update_issue_accepts_named_priority(self):
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "priority:3"}])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=9))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.update_issue("example-org/oompah-tasks#9", priority="high")
        patch_call = m.call_args_list[-1]
        assert "priority:1" in patch_call[1]["json"]["labels"]
        assert "priority:3" not in patch_call[1]["json"]["labels"]

    def test_update_issue_add_label(self):
        tracker = self._make_tracker()
        post_resp = _mock_response(200, json_data=[{"name": "needs:review"}])
        with patch.object(
            tracker._client._http, "request", return_value=post_resp
        ) as m:
            tracker.update_issue("example-org/oompah-tasks#10", **{"add-label": "needs:review"})
        assert m.call_args[0][0] == "POST"
        assert "needs:review" in m.call_args[1]["json"]["labels"]

    def test_update_issue_remove_label(self):
        tracker = self._make_tracker()
        del_resp = _mock_response(204, json_data=None)
        with patch.object(
            tracker._client._http, "request", return_value=del_resp
        ) as m:
            tracker.update_issue("example-org/oompah-tasks#10", **{"remove-label": "needs:review"})
        assert m.call_args[0][0] == "DELETE"
        assert "needs%3Areview" in m.call_args[0][1]

    def test_update_issue_ignores_unknown_fields(self):
        """Unknown field keys are silently ignored, no API call made."""
        tracker = self._make_tracker()
        with patch.object(tracker._client._http, "request") as m:
            tracker.update_issue("example-org/oompah-tasks#11", nonexistent_field="x")
        m.assert_not_called()

    def test_update_issue_invalid_identifier_raises(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.update_issue("not-valid-id", title="x")

    # ------------------------------------------------------------------
    # close_issue
    # ------------------------------------------------------------------

    def test_close_issue_sets_done_status_and_keeps_open(self):
        """close_issue sets oompah:status:done label and keeps GitHub state=open."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "oompah:status:open"}])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=20, state="open"))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.close_issue("example-org/oompah-tasks#20")
        patch_call = m.call_args_list[-1]
        assert patch_call[0][0] == "PATCH"
        assert patch_call[1]["json"]["state"] == "open"
        assert "oompah:status:done" in patch_call[1]["json"]["labels"]

    def test_close_issue_posts_reason_comment(self):
        """close_issue appends a comment when reason is provided."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=21))
        comment_resp = _mock_response(201, json_data={"id": 1, "body": "**oompah**: Closed."})
        responses = [labels_resp, patch_resp, comment_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.close_issue("example-org/oompah-tasks#21", reason="Closed.")
        # Comment POST should be the last call
        last_call = m.call_args_list[-1]
        assert last_call[0][0] == "POST"
        assert "comments" in last_call[0][1]

    def test_close_issue_no_comment_when_no_reason(self):
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=22))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.close_issue("example-org/oompah-tasks#22")
        assert m.call_count == 2

    def test_close_issue_uses_first_terminal_state(self):
        """close_issue uses terminal_states[0] ('Done') for the label."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=23))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.close_issue("example-org/oompah-tasks#23")
        patch_call = m.call_args_list[1]
        assert "oompah:status:done" in patch_call[1]["json"]["labels"]

    # ------------------------------------------------------------------
    # reopen_issue
    # ------------------------------------------------------------------

    def test_reopen_issue_sets_active_status_and_opens(self):
        """reopen_issue sets oompah:status:open label and GitHub state=open."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "oompah:status:done"}])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=30, state="open"))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.reopen_issue("example-org/oompah-tasks#30")
        patch_call = m.call_args_list[-1]
        assert patch_call[0][0] == "PATCH"
        assert patch_call[1]["json"]["state"] == "open"
        assert "oompah:status:open" in patch_call[1]["json"]["labels"]

    def test_reopen_issue_uses_first_active_state(self):
        """reopen_issue uses active_states[0] ('Open') for the label."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=31))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.reopen_issue("example-org/oompah-tasks#31")
        patch_call = m.call_args_list[1]
        assert "oompah:status:open" in patch_call[1]["json"]["labels"]

    # ------------------------------------------------------------------
    # archive_issue
    # ------------------------------------------------------------------

    def test_archive_issue_sets_archived_label_and_closes(self):
        """archive_issue sets oompah:status:archived and state=closed."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "oompah:status:in-progress"}])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=40, state="closed"))
        responses = [labels_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.archive_issue("example-org/oompah-tasks#40")
        patch_call = m.call_args_list[-1]
        assert patch_call[1]["json"]["state"] == "closed"
        assert "oompah:status:archived" in patch_call[1]["json"]["labels"]

    # ------------------------------------------------------------------
    # mark_needs_human
    # ------------------------------------------------------------------

    def test_mark_needs_human_updates_status_and_comments(self):
        """mark_needs_human sets status to Needs Human then adds a comment."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "oompah:status:open"}])
        patch_resp = _mock_response(200, json_data=_make_gh_issue(number=50))
        comment_resp = _mock_response(
            201, json_data={"id": 99, "body": "**oompah**: Action required."}
        )
        responses = [
            labels_resp, patch_resp, comment_resp
        ]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.mark_needs_human(
                "example-org/oompah-tasks#50", "Action required."
            )
        # Last call should be the comment POST
        last_call = m.call_args_list[-1]
        assert last_call[0][0] == "POST"
        assert "comments" in last_call[0][1]
        assert "Action required." in last_call[1]["json"]["body"]

    # ------------------------------------------------------------------
    # add_comment
    # ------------------------------------------------------------------

    def test_add_comment_returns_github_comment_dict(self):
        """AC#2: add_comment round-trips via mocked API."""
        tracker = self._make_tracker()
        comment = {"id": 1, "body": "**oompah**: hello", "created_at": "2024-01-01T00:00:00Z"}
        resp = _mock_response(201, json_data=comment)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.add_comment("example-org/oompah-tasks#1", "hello")
        assert result["id"] == 1
        assert result["body"] == "**oompah**: hello"

    def test_add_comment_prefixes_author(self):
        """Comment body is prefixed with **{author}**: ."""
        tracker = self._make_tracker()
        resp = _mock_response(201, json_data={"id": 2, "body": "**bot**: msg"})
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.add_comment("example-org/oompah-tasks#1", "msg", author="bot")
        posted_body = m.call_args[1]["json"]["body"]
        assert posted_body == "**bot**: msg"

    def test_add_comment_custom_author(self):
        tracker = self._make_tracker()
        resp = _mock_response(201, json_data={"id": 3, "body": "**alice**: hi"})
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.add_comment("example-org/oompah-tasks#2", "hi", author="alice")
        assert "**alice**" in m.call_args[1]["json"]["body"]

    def test_add_comment_posts_to_comments_endpoint(self):
        tracker = self._make_tracker()
        resp = _mock_response(201, json_data={"id": 4, "body": "x"})
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.add_comment("example-org/oompah-tasks#3", "x")
        call_args = m.call_args
        assert call_args[0][0] == "POST"
        assert "/issues/3/comments" in call_args[0][1]

    def test_add_comment_raises_on_empty_text(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError, match="Comment text is required"):
            tracker.add_comment("example-org/oompah-tasks#1", "")

    def test_add_comment_raises_on_whitespace_text(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError, match="Comment text is required"):
            tracker.add_comment("example-org/oompah-tasks#1", "   ")

    def test_add_comment_invalid_identifier_raises(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.add_comment("not-valid", "hello")

    def test_add_comment_fallback_when_non_dict_response(self):
        """When the API returns a non-dict, fallback body dict is returned."""
        tracker = self._make_tracker()
        # Simulate a response that parses as a list (unexpected but possible)
        resp = _mock_response(201, json_data=[])
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.add_comment("example-org/oompah-tasks#1", "test msg")
        assert "body" in result
        assert "test msg" in result["body"]

    # ------------------------------------------------------------------
    # add_label
    # ------------------------------------------------------------------

    def test_add_label_posts_to_labels_endpoint(self):
        """AC#2: add_label round-trips via mocked API."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[{"name": "bug"}])
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.add_label("example-org/oompah-tasks#5", "bug")
        call_args = m.call_args
        assert call_args[0][0] == "POST"
        assert "/issues/5/labels" in call_args[0][1]
        assert call_args[1]["json"]["labels"] == ["bug"]

    def test_add_label_invalid_identifier_raises(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.add_label("bad-id", "bug")

    def test_add_label_with_colon_in_name(self):
        """Labels with colons (e.g. oompah:status:open) are posted correctly."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[{"name": "oompah:status:open"}])
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.add_label("example-org/oompah-tasks#6", "oompah:status:open")
        assert m.call_args[1]["json"]["labels"] == ["oompah:status:open"]

    # ------------------------------------------------------------------
    # remove_label
    # ------------------------------------------------------------------

    def test_remove_label_sends_delete_request(self):
        """AC#2: remove_label round-trips via mocked API."""
        tracker = self._make_tracker()
        resp = _mock_response(204, json_data=None)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.remove_label("example-org/oompah-tasks#5", "bug")
        call_args = m.call_args
        assert call_args[0][0] == "DELETE"
        assert "/issues/5/labels/bug" in call_args[0][1]

    def test_remove_label_url_encodes_colon_labels(self):
        """Label names containing colons must be URL-encoded in the path."""
        tracker = self._make_tracker()
        resp = _mock_response(204, json_data=None)
        with patch.object(tracker._client._http, "request", return_value=resp) as m:
            tracker.remove_label("example-org/oompah-tasks#7", "oompah:status:open")
        call_url = m.call_args[0][1]
        assert "oompah%3Astatus%3Aopen" in call_url

    def test_remove_label_noop_on_404(self):
        """remove_label is a no-op when the label is not on the issue."""
        tracker = self._make_tracker()
        resp = _mock_response(404, text="Not Found")
        with patch.object(tracker._client._http, "request", return_value=resp):
            # Should not raise
            tracker.remove_label("example-org/oompah-tasks#5", "nonexistent")

    def test_remove_label_re_raises_non_404_errors(self):
        """Non-404 errors from remove_label are propagated."""
        tracker = self._make_tracker()
        resp = _mock_response(500, text="Server Error")
        with patch.object(tracker._client._http, "request", return_value=resp):
            with pytest.raises(TrackerError):
                tracker.remove_label("example-org/oompah-tasks#5", "bug")

    def test_remove_label_invalid_identifier_raises(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.remove_label("bad-id", "bug")

    # ------------------------------------------------------------------
    # Private helper: _active_status / _terminal_status
    # ------------------------------------------------------------------

    def test_active_status_returns_first_active_state(self):
        tracker = self._make_tracker()
        assert tracker._active_status() == "Open"

    def test_terminal_status_returns_first_terminal_state(self):
        tracker = self._make_tracker()
        assert tracker._terminal_status() == "Done"

    def test_active_status_defaults_to_Open_when_empty(self):
        auth = GitHubAuth(pat="tok")
        tracker = GitHubIssueTracker(
            owner="o", repo="r",
            active_states=[],
            terminal_states=[],
            auth=auth,
        )
        assert tracker._active_status() == "Open"

    def test_terminal_status_defaults_to_Done_when_empty(self):
        auth = GitHubAuth(pat="tok")
        tracker = GitHubIssueTracker(
            owner="o", repo="r",
            active_states=[],
            terminal_states=[],
            auth=auth,
        )
        assert tracker._terminal_status() == "Done"

    # ------------------------------------------------------------------
    # Private helper: _build_issue_body
    # ------------------------------------------------------------------

    def test_build_body_description_only(self):
        tracker = self._make_tracker()
        body = tracker._build_issue_body("Do the thing.")
        assert body == "Do the thing."

    def test_build_body_empty_description(self):
        tracker = self._make_tracker()
        assert tracker._build_issue_body(None) == ""
        assert tracker._build_issue_body("") == ""

    def test_build_body_with_metadata(self):
        tracker = self._make_tracker()
        body = tracker._build_issue_body("Desc", {"project_id": "p1"})
        assert "Desc" in body
        assert '<!-- oompah:metadata' in body
        assert '"project_id": "p1"' in body

    def test_build_body_metadata_parseable(self):
        """Body built by _build_issue_body must be parseable by _parse_body_metadata."""
        from oompah.github_tracker import _parse_body_metadata
        tracker = self._make_tracker()
        body = tracker._build_issue_body("desc", {"project_id": "p2", "target_branch": "main"})
        meta = _parse_body_metadata(body)
        assert meta["project_id"] == "p2"
        assert meta["target_branch"] == "main"

    # ------------------------------------------------------------------
    # Private helper: _update_body_description
    # ------------------------------------------------------------------

    def test_update_body_description_no_metadata(self):
        tracker = self._make_tracker()
        result = tracker._update_body_description("Old text.", "New text.")
        assert result == "New text."

    def test_update_body_description_preserves_metadata_block(self):
        tracker = self._make_tracker()
        meta_block = '<!-- oompah:metadata\n{"project_id": "p3"}\n-->'
        current_body = f"Old text.\n\n{meta_block}"
        result = tracker._update_body_description(current_body, "New text.")
        assert "New text." in result
        assert meta_block in result
        assert "Old text." not in result

    def test_update_body_empty_current_body(self):
        tracker = self._make_tracker()
        result = tracker._update_body_description("", "Fresh description.")
        assert result == "Fresh description."

    # ------------------------------------------------------------------
    # Private helper: _set_status_label
    # ------------------------------------------------------------------

    def test_set_status_label_replaces_existing(self):
        """_set_status_label removes old status labels and adds the new one."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[
            {"name": "oompah:status:open"},
            {"name": "bug"},  # non-status labels should not be removed
        ])
        delete_resp = _mock_response(204, json_data=None)
        post_resp = _mock_response(200, json_data=[{"name": "oompah:status:done"}])
        responses = [labels_resp, delete_resp, post_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker._set_status_label(42, "Done")
        # GET labels
        assert m.call_args_list[0][0][0] == "GET"
        # DELETE old status label
        delete_call = m.call_args_list[1]
        assert delete_call[0][0] == "DELETE"
        assert "oompah%3Astatus%3Aopen" in delete_call[0][1]
        # POST new status label
        post_call = m.call_args_list[2]
        assert post_call[0][0] == "POST"
        assert "oompah:status:done" in post_call[1]["json"]["labels"]

    def test_set_status_label_no_existing_status_label(self):
        """When no status label exists, just add the new one."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "bug"}])
        post_resp = _mock_response(200, json_data=[{"name": "oompah:status:in-progress"}])
        responses = [labels_resp, post_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker._set_status_label(43, "In Progress")
        assert m.call_count == 2  # GET + POST only, no DELETE
        post_call = m.call_args_list[1]
        assert "oompah:status:in-progress" in post_call[1]["json"]["labels"]

    # ------------------------------------------------------------------
    # Private helper: _set_priority_label
    # ------------------------------------------------------------------

    def test_set_priority_label_replaces_existing(self):
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "priority:3"}])
        delete_resp = _mock_response(204, json_data=None)
        post_resp = _mock_response(200, json_data=[{"name": "priority:1"}])
        responses = [labels_resp, delete_resp, post_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker._set_priority_label(44, 1)
        delete_call = m.call_args_list[1]
        assert delete_call[0][0] == "DELETE"
        assert "priority%3A3" in delete_call[0][1]
        post_call = m.call_args_list[2]
        assert "priority:1" in post_call[1]["json"]["labels"]

    def test_set_priority_label_accepts_named_priority(self):
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "priority:3"}])
        delete_resp = _mock_response(204, json_data=None)
        post_resp = _mock_response(200, json_data=[{"name": "priority:1"}])
        responses = [labels_resp, delete_resp, post_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker._set_priority_label(44, "high")
        post_call = m.call_args_list[2]
        assert "priority:1" in post_call[1]["json"]["labels"]

    def test_set_priority_label_none_removes_only(self):
        """When priority is None, only remove existing priority labels."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[{"name": "priority:2"}])
        delete_resp = _mock_response(204, json_data=None)
        responses = [labels_resp, delete_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker._set_priority_label(45, None)
        assert m.call_count == 2  # GET + DELETE only, no POST

    def test_set_priority_label_invalid_value_skips_add(self):
        """An un-coercible priority value skips the POST call."""
        tracker = self._make_tracker()
        labels_resp = _mock_response(200, json_data=[])
        responses = [labels_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker._set_priority_label(46, "not-a-number")
        assert m.call_count == 1  # only GET, no POST


# ===========================================================================
# GitHubIssueTracker — metadata and attachments (TASK-458.5)
# ===========================================================================


class TestGitHubIssueTrackerMetadata:
    """Tests for get_metadata, set_metadata_field, fetch_attachments, and
    set_attachments implemented in TASK-458.5.

    Acceptance criteria:
      #1  Metadata get/set works for project_id, target_branch, work_branch,
          review fields, attachments, and release-pick data.
      #2  Field-backed and body-backed metadata pass the same contract tests.
    """

    def _make_tracker(self) -> GitHubIssueTracker:
        auth = GitHubAuth(pat="test_token")
        return GitHubIssueTracker(
            owner="example-org",
            repo="oompah-tasks",
            active_states=["Open", "In Progress"],
            terminal_states=["Done", "Archived"],
            auth=auth,
        )

    # ------------------------------------------------------------------
    # _update_body_metadata helper
    # ------------------------------------------------------------------

    def test_update_body_metadata_adds_block_to_plain_body(self):
        tracker = self._make_tracker()
        result = tracker._update_body_metadata(
            "Some description", {"target_branch": "main"}
        )
        assert "Some description" in result
        assert '<!-- oompah:metadata' in result
        assert '"target_branch": "main"' in result

    def test_update_body_metadata_replaces_existing_block(self):
        tracker = self._make_tracker()
        body = 'Desc\n\n<!-- oompah:metadata\n{"target_branch":"old"}\n-->'
        result = tracker._update_body_metadata(body, {"target_branch": "new"})
        assert '"new"' in result
        assert '"old"' not in result

    def test_update_body_metadata_removes_block_when_meta_empty(self):
        tracker = self._make_tracker()
        body = 'Desc\n\n<!-- oompah:metadata\n{"key":"val"}\n-->'
        result = tracker._update_body_metadata(body, {})
        assert "oompah:metadata" not in result
        assert result.strip() == "Desc"

    def test_update_body_metadata_no_description_no_meta_returns_empty(self):
        tracker = self._make_tracker()
        result = tracker._update_body_metadata("", {})
        assert result == ""

    def test_update_body_metadata_no_description_with_meta(self):
        tracker = self._make_tracker()
        result = tracker._update_body_metadata("", {"key": "val"})
        assert result.startswith("<!-- oompah:metadata")
        assert '"key": "val"' in result

    def test_update_body_metadata_preserves_description(self):
        tracker = self._make_tracker()
        body = "Original description"
        result = tracker._update_body_metadata(body, {"work_branch": "oompah/feat-1"})
        assert result.startswith("Original description")

    # ------------------------------------------------------------------
    # get_metadata — body-backed
    # ------------------------------------------------------------------

    def test_get_metadata_returns_prefixed_keys_from_body(self):
        """AC#1: get_metadata reads project_id and target_branch."""
        tracker = self._make_tracker()
        meta_json = '{"project_id":"proj-abc","target_branch":"main"}'
        body = f"Some description\n\n<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=10, body=body)
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.get_metadata("example-org/oompah-tasks#10")
        assert result == {
            "oompah.project_id": "proj-abc",
            "oompah.target_branch": "main",
        }

    def test_get_metadata_reads_work_branch(self):
        """AC#1: get_metadata reads work_branch."""
        tracker = self._make_tracker()
        meta_json = '{"work_branch":"oompah/trickle/gh-42"}'
        body = f"<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=42, body=body)
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.get_metadata("example-org/oompah-tasks#42")
        assert result["oompah.work_branch"] == "oompah/trickle/gh-42"

    def test_get_metadata_reads_review_fields(self):
        """AC#1: get_metadata reads review URL and number."""
        tracker = self._make_tracker()
        meta_json = '{"review_url":"https://github.com/org/repo/pull/7","review_number":7}'
        body = f"<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=5, body=body)
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.get_metadata("example-org/oompah-tasks#5")
        assert result["oompah.review_url"] == "https://github.com/org/repo/pull/7"
        assert result["oompah.review_number"] == 7

    def test_get_metadata_reads_attachments(self):
        """AC#1: get_metadata reads attachments list."""
        tracker = self._make_tracker()
        meta_json = '{"attachments":[{"name":"patch.diff","url":"https://example.com/patch.diff"}]}'
        body = f"<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=3, body=body)
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.get_metadata("example-org/oompah-tasks#3")
        assert result["oompah.attachments"] == [
            {"name": "patch.diff", "url": "https://example.com/patch.diff"}
        ]

    def test_get_metadata_reads_release_pick_data(self):
        """AC#1: get_metadata reads release-pick data."""
        tracker = self._make_tracker()
        meta_json = '{"release_pick":["release/1.2","release/1.3"]}'
        body = f"<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=8, body=body)
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.get_metadata("example-org/oompah-tasks#8")
        assert result["oompah.release_pick"] == ["release/1.2", "release/1.3"]

    def test_get_metadata_returns_empty_when_no_block(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=1, body="Plain text, no metadata block.")
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.get_metadata("example-org/oompah-tasks#1")
        assert result == {}

    def test_get_metadata_returns_empty_when_body_is_null(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=2, body="")
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.get_metadata("example-org/oompah-tasks#2")
        assert result == {}

    def test_get_metadata_returns_empty_on_api_error(self):
        tracker = self._make_tracker()
        resp = _mock_response(404, text="Not Found")
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.get_metadata("example-org/oompah-tasks#999")
        assert result == {}

    def test_get_metadata_invalid_identifier_returns_empty(self):
        """Invalid identifier returns empty dict rather than raising,
        consistent with the tracker protocol contract."""
        tracker = self._make_tracker()
        result = tracker.get_metadata("not-a-valid-id")
        assert result == {}

    # ------------------------------------------------------------------
    # set_metadata_field — body-backed
    # ------------------------------------------------------------------

    def test_set_metadata_field_adds_new_field_to_empty_body(self):
        """AC#1: set_metadata_field writes target_branch."""
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=11, body="")
        get_resp = _mock_response(200, json_data=gh_issue)
        patch_resp = _mock_response(200, json_data={**gh_issue, "body": "patched"})
        responses = [get_resp, patch_resp]
        with patch.object(
            tracker._client._http, "request", side_effect=responses
        ) as m:
            tracker.set_metadata_field(
                "example-org/oompah-tasks#11", "oompah.target_branch", "main"
            )
        # Second call should be a PATCH with the updated body.
        patch_call = m.call_args_list[1]
        assert patch_call.args[0] == "PATCH"
        body_sent = patch_call.kwargs["json"]["body"]
        assert '"target_branch": "main"' in body_sent
        assert "oompah:metadata" in body_sent

    def test_set_metadata_field_preserves_existing_description(self):
        tracker = self._make_tracker()
        original_body = "Keep this description."
        gh_issue = _make_gh_issue(number=12, body=original_body)
        get_resp = _mock_response(200, json_data=gh_issue)
        patch_resp = _mock_response(200, json_data=gh_issue)
        with patch.object(
            tracker._client._http, "request", side_effect=[get_resp, patch_resp]
        ) as m:
            tracker.set_metadata_field(
                "example-org/oompah-tasks#12", "oompah.work_branch", "oompah/feat-1"
            )
        body_sent = m.call_args_list[1].kwargs["json"]["body"]
        assert "Keep this description." in body_sent
        assert '"work_branch": "oompah/feat-1"' in body_sent

    def test_set_metadata_field_preserves_other_metadata_keys(self):
        tracker = self._make_tracker()
        meta_json = '{"project_id":"proj-x","target_branch":"main"}'
        original_body = f"Desc\n\n<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=13, body=original_body)
        get_resp = _mock_response(200, json_data=gh_issue)
        patch_resp = _mock_response(200, json_data=gh_issue)
        with patch.object(
            tracker._client._http, "request", side_effect=[get_resp, patch_resp]
        ) as m:
            tracker.set_metadata_field(
                "example-org/oompah-tasks#13", "oompah.work_branch", "oompah/feat-2"
            )
        body_sent = m.call_args_list[1].kwargs["json"]["body"]
        assert '"project_id": "proj-x"' in body_sent
        assert '"target_branch": "main"' in body_sent
        assert '"work_branch": "oompah/feat-2"' in body_sent

    def test_set_metadata_field_updates_existing_value(self):
        tracker = self._make_tracker()
        meta_json = '{"target_branch":"old-branch"}'
        original_body = f"<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=14, body=original_body)
        get_resp = _mock_response(200, json_data=gh_issue)
        patch_resp = _mock_response(200, json_data=gh_issue)
        with patch.object(
            tracker._client._http, "request", side_effect=[get_resp, patch_resp]
        ) as m:
            tracker.set_metadata_field(
                "example-org/oompah-tasks#14", "oompah.target_branch", "new-branch"
            )
        body_sent = m.call_args_list[1].kwargs["json"]["body"]
        assert '"new-branch"' in body_sent
        assert '"old-branch"' not in body_sent

    def test_set_metadata_field_raises_for_non_oompah_key(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError, match="oompah."):
            tracker.set_metadata_field(
                "example-org/oompah-tasks#1", "target_branch", "main"
            )

    def test_set_metadata_field_raises_for_issue_not_found(self):
        tracker = self._make_tracker()
        resp = _mock_response(404, text="Not Found")
        with patch.object(tracker._client._http, "request", return_value=resp):
            with pytest.raises(TrackerError, match="not found"):
                tracker.set_metadata_field(
                    "example-org/oompah-tasks#999", "oompah.target_branch", "main"
                )

    def test_set_metadata_field_invalid_identifier_raises(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.set_metadata_field("bad-id", "oompah.key", "val")

    def test_set_metadata_field_patches_correct_endpoint(self):
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=20, body="")
        get_resp = _mock_response(200, json_data=gh_issue)
        patch_resp = _mock_response(200, json_data=gh_issue)
        with patch.object(
            tracker._client._http, "request", side_effect=[get_resp, patch_resp]
        ) as m:
            tracker.set_metadata_field(
                "example-org/oompah-tasks#20", "oompah.project_id", "proj-y"
            )
        patch_call = m.call_args_list[1]
        assert patch_call.args[0] == "PATCH"
        assert "/repos/example-org/oompah-tasks/issues/20" in str(patch_call.args[1])

    # ------------------------------------------------------------------
    # fetch_attachments
    # ------------------------------------------------------------------

    def test_fetch_attachments_reads_from_body_metadata(self):
        """AC#1: fetch_attachments reads stored attachment records."""
        tracker = self._make_tracker()
        attachment = {"name": "report.pdf", "url": "https://example.com/report.pdf"}
        meta_json = f'{{"attachments":[{{"name":"report.pdf","url":"https://example.com/report.pdf"}}]}}'
        body = f"<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=30, body=body)
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_attachments("example-org/oompah-tasks#30")
        assert result == [attachment]

    def test_fetch_attachments_returns_empty_when_key_absent(self):
        tracker = self._make_tracker()
        meta_json = '{"target_branch":"main"}'
        body = f"<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=31, body=body)
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_attachments("example-org/oompah-tasks#31")
        assert result == []

    def test_fetch_attachments_filters_non_dict_entries(self):
        tracker = self._make_tracker()
        meta_json = '{"attachments":[{"name":"ok.diff"},"not-a-dict",42]}'
        body = f"<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=32, body=body)
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_attachments("example-org/oompah-tasks#32")
        assert result == [{"name": "ok.diff"}]

    def test_fetch_attachments_returns_empty_on_api_error(self):
        tracker = self._make_tracker()
        resp = _mock_response(404, text="Not Found")
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_attachments("example-org/oompah-tasks#999")
        assert result == []

    # ------------------------------------------------------------------
    # set_attachments
    # ------------------------------------------------------------------

    def test_set_attachments_writes_to_body_metadata(self):
        """AC#1: set_attachments persists attachment list."""
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=40, body="")
        get_resp = _mock_response(200, json_data=gh_issue)
        patch_resp = _mock_response(200, json_data=gh_issue)
        attachments = [{"name": "file.diff", "url": "https://example.com/file.diff"}]
        with patch.object(
            tracker._client._http, "request", side_effect=[get_resp, patch_resp]
        ) as m:
            tracker.set_attachments("example-org/oompah-tasks#40", attachments)
        body_sent = m.call_args_list[1].kwargs["json"]["body"]
        assert '"attachments"' in body_sent
        assert '"file.diff"' in body_sent

    def test_set_attachments_empty_list_removes_attachments(self):
        tracker = self._make_tracker()
        meta_json = '{"attachments":[{"name":"old.diff"}]}'
        original_body = f"Desc\n\n<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=41, body=original_body)
        get_resp = _mock_response(200, json_data=gh_issue)
        patch_resp = _mock_response(200, json_data=gh_issue)
        with patch.object(
            tracker._client._http, "request", side_effect=[get_resp, patch_resp]
        ) as m:
            tracker.set_attachments("example-org/oompah-tasks#41", [])
        body_sent = m.call_args_list[1].kwargs["json"]["body"]
        # Metadata block should still exist (target_branch absent, but block exists
        # because attachments=[] is still stored) and contain empty attachments list.
        assert '"attachments": []' in body_sent

    def test_set_attachments_ignores_project_root(self):
        """project_root is accepted for protocol compat but has no effect."""
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=42, body="")
        get_resp = _mock_response(200, json_data=gh_issue)
        patch_resp = _mock_response(200, json_data=gh_issue)
        with patch.object(
            tracker._client._http, "request", side_effect=[get_resp, patch_resp]
        ):
            # Should not raise even with project_root set.
            tracker.set_attachments(
                "example-org/oompah-tasks#42",
                [{"name": "x.diff"}],
                project_root="/some/path",
            )

    def test_set_attachments_preserves_other_metadata(self):
        tracker = self._make_tracker()
        meta_json = '{"target_branch":"main","project_id":"proj-q"}'
        original_body = f"Desc\n\n<!-- oompah:metadata\n{meta_json}\n-->"
        gh_issue = _make_gh_issue(number=43, body=original_body)
        get_resp = _mock_response(200, json_data=gh_issue)
        patch_resp = _mock_response(200, json_data=gh_issue)
        with patch.object(
            tracker._client._http, "request", side_effect=[get_resp, patch_resp]
        ) as m:
            tracker.set_attachments("example-org/oompah-tasks#43", [{"name": "a.diff"}])
        body_sent = m.call_args_list[1].kwargs["json"]["body"]
        assert '"target_branch": "main"' in body_sent
        assert '"project_id": "proj-q"' in body_sent
        assert '"attachments"' in body_sent

    # ------------------------------------------------------------------
    # Contract tests — AC#2: body-backed metadata round-trips
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "field_key,field_value",
        [
            ("oompah.project_id", "proj-contract-test"),
            ("oompah.target_branch", "release/2.0"),
            ("oompah.work_branch", "oompah/task-gh-99"),
            ("oompah.review_url", "https://github.com/org/repo/pull/55"),
            ("oompah.review_number", 55),
            ("oompah.release_pick", ["release/1.9", "release/2.0"]),
            (
                "oompah.attachments",
                [{"name": "out.diff", "url": "https://example.com/out.diff"}],
            ),
        ],
    )
    def test_body_backed_metadata_round_trips(self, field_key, field_value):
        """AC#2: Body-backed metadata can be written and read back transparently.

        This is the contract test for body-backed storage.  A future
        field-backed test class would parameterise the same cases against
        the GitHub Projects V2 adapter path.
        """
        tracker = self._make_tracker()
        issue_number = 50

        # --- write phase: set_metadata_field stores value in body ---
        gh_issue_empty = _make_gh_issue(number=issue_number, body="")
        get_for_write = _mock_response(200, json_data=gh_issue_empty)
        patch_resp = _mock_response(200, json_data=gh_issue_empty)
        with patch.object(
            tracker._client._http, "request", side_effect=[get_for_write, patch_resp]
        ) as write_mock:
            tracker.set_metadata_field(
                f"example-org/oompah-tasks#{issue_number}", field_key, field_value
            )

        # Capture the body that was PATCHed back.
        written_body = write_mock.call_args_list[1].kwargs["json"]["body"]

        # --- read phase: get_metadata can read the stored body back ---
        gh_issue_written = _make_gh_issue(number=issue_number, body=written_body)
        get_for_read = _mock_response(200, json_data=gh_issue_written)
        with patch.object(tracker._client._http, "request", return_value=get_for_read):
            result = tracker.get_metadata(
                f"example-org/oompah-tasks#{issue_number}"
            )

        assert result[field_key] == field_value


# ===========================================================================
# GitHubIssueTracker - hierarchy and dependencies (TASK-458.6)
# ===========================================================================


class TestGitHubIssueTrackerHierarchyAndDependencies:
    """Tests for add_parent_child and add_dependency methods.

    Acceptance criteria:
      #1  fetch_children and add_dependency work through the protocol.
      #2  Fallback relationship metadata renders the same normalized Issue relationships.
    """

    def _make_tracker(self) -> GitHubIssueTracker:
        auth = GitHubAuth(pat="test_token")
        return GitHubIssueTracker(
            owner="example-org",
            repo="oompah-tasks",
            active_states=["Open", "In Progress"],
            terminal_states=["Done", "Archived"],
            auth=auth,
        )

    # ------------------------------------------------------------------
    # add_parent_child
    # ------------------------------------------------------------------

    def test_add_parent_child_uses_sub_issues_api_when_available(self):
        """Tries the GitHub sub-issues REST API and mirrors a parent label."""
        tracker = self._make_tracker()
        child_resp = _mock_response(
            200, json_data=_make_gh_issue(number=10, issue_id=1010)
        )
        resp = _mock_response(200, json_data={"id": 123})
        create_label_resp = _mock_response(201, json_data={"name": "parent:5"})
        label_resp = _mock_response(200, json_data=[{"name": "parent:5"}])
        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[child_resp, resp, create_label_resp, label_resp],
        ) as m:
            tracker.add_parent_child(
                "example-org/oompah-tasks#10",
                "example-org/oompah-tasks#5",
            )
        lookup_call = m.call_args_list[0]
        assert lookup_call[0][0] == "GET"
        assert "/issues/10" in lookup_call[0][1]
        call_args = m.call_args_list[1]
        assert call_args[0][0] == "POST"
        assert "/issues/5/sub_issues" in call_args[0][1]
        assert call_args[1]["json"] == {"sub_issue_id": 1010}
        create_label_call = m.call_args_list[2]
        assert create_label_call[0][0] == "POST"
        assert create_label_call[0][1].endswith("/labels")
        assert create_label_call[1]["json"]["name"] == "parent:5"
        label_call = m.call_args_list[3]
        assert label_call[0][0] == "POST"
        assert "/issues/10/labels" in label_call[0][1]
        assert label_call[1]["json"]["labels"] == ["parent:5"]

    def test_add_parent_child_falls_back_to_label_on_404(self):
        """Falls back to parent:<number> label when sub-issues API unavailable."""
        tracker = self._make_tracker()
        child_resp = _mock_response(
            200, json_data=_make_gh_issue(number=10, issue_id=1010)
        )
        resp_404 = _mock_response(404, text="Not Found")
        resp_404.is_success = False
        create_label_resp = _mock_response(201, json_data={"name": "parent:5"})
        label_resp = _mock_response(200, json_data=[{"name": "parent:5"}])
        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[child_resp, resp_404, create_label_resp, label_resp],
        ) as m:
            tracker.add_parent_child(
                "example-org/oompah-tasks#10",
                "example-org/oompah-tasks#5",
            )
        # Fourth call should be add_label after dynamic label creation.
        label_call = m.call_args_list[3]
        assert label_call[0][0] == "POST"
        assert "/issues/10/labels" in label_call[0][1]
        assert label_call[1]["json"]["labels"] == ["parent:5"]

    def test_add_parent_child_re_raises_non_404_errors(self):
        """Non-404 errors from sub-issues API are propagated."""
        tracker = self._make_tracker()
        child_resp = _mock_response(
            200, json_data=_make_gh_issue(number=10, issue_id=1010)
        )
        resp_422 = _mock_response(422, text="Validation Failed")
        with patch.object(
            tracker._client._http, "request", side_effect=[child_resp, resp_422]
        ):
            with pytest.raises(TrackerError):
                tracker.add_parent_child(
                    "example-org/oompah-tasks#10",
                    "example-org/oompah-tasks#5",
                )

    def test_add_parent_child_invalid_child_identifier_raises(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.add_parent_child("bad-id", "example-org/oompah-tasks#5")

    def test_add_parent_child_invalid_parent_identifier_raises(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.add_parent_child("example-org/oompah-tasks#10", "bad-id")

    # ------------------------------------------------------------------
    # add_dependency
    # ------------------------------------------------------------------

    def test_add_dependency_uses_dependencies_api_when_available(self):
        """Tries the GitHub dependencies REST API and mirrors a blocker label."""
        tracker = self._make_tracker()
        blocker_resp = _mock_response(
            200, json_data=_make_gh_issue(number=5, issue_id=1005)
        )
        resp = _mock_response(200, json_data={"id": 123})
        create_label_resp = _mock_response(201, json_data={"name": "depends-on:5"})
        label_resp = _mock_response(200, json_data=[{"name": "depends-on:5"}])
        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[blocker_resp, resp, create_label_resp, label_resp],
        ) as m:
            tracker.add_dependency(
                "example-org/oompah-tasks#10",
                "example-org/oompah-tasks#5",
            )
        lookup_call = m.call_args_list[0]
        assert lookup_call[0][0] == "GET"
        assert "/issues/5" in lookup_call[0][1]
        call_args = m.call_args_list[1]
        assert call_args[0][0] == "POST"
        assert "/issues/10/dependencies/blocked_by" in call_args[0][1]
        assert call_args[1]["json"] == {"issue_id": 1005}
        create_label_call = m.call_args_list[2]
        assert create_label_call[0][0] == "POST"
        assert create_label_call[0][1].endswith("/labels")
        assert create_label_call[1]["json"]["name"] == "depends-on:5"
        label_call = m.call_args_list[3]
        assert label_call[0][0] == "POST"
        assert "/issues/10/labels" in label_call[0][1]
        assert label_call[1]["json"]["labels"] == ["depends-on:5"]

    def test_add_dependency_falls_back_to_label_on_404(self):
        """Falls back to depends-on:<number> label when dependencies API unavailable."""
        tracker = self._make_tracker()
        blocker_resp = _mock_response(
            200, json_data=_make_gh_issue(number=5, issue_id=1005)
        )
        resp_404 = _mock_response(404, text="Not Found")
        resp_404.is_success = False
        create_label_resp = _mock_response(201, json_data={"name": "depends-on:5"})
        label_resp = _mock_response(200, json_data=[{"name": "depends-on:5"}])
        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[blocker_resp, resp_404, create_label_resp, label_resp],
        ) as m:
            tracker.add_dependency(
                "example-org/oompah-tasks#10",
                "example-org/oompah-tasks#5",
            )
        # Fourth call should be add_label after dynamic label creation.
        label_call = m.call_args_list[3]
        assert label_call[0][0] == "POST"
        assert "/issues/10/labels" in label_call[0][1]
        assert label_call[1]["json"]["labels"] == ["depends-on:5"]

    def test_add_dependency_re_raises_non_404_errors(self):
        """Non-404 errors from dependencies API are propagated."""
        tracker = self._make_tracker()
        blocker_resp = _mock_response(
            200, json_data=_make_gh_issue(number=5, issue_id=1005)
        )
        resp_422 = _mock_response(422, text="Validation Failed")
        with patch.object(
            tracker._client._http, "request", side_effect=[blocker_resp, resp_422]
        ):
            with pytest.raises(TrackerError):
                tracker.add_dependency(
                    "example-org/oompah-tasks#10",
                    "example-org/oompah-tasks#5",
                )

    def test_add_dependency_invalid_blocked_identifier_raises(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.add_dependency("bad-id", "example-org/oompah-tasks#5")

    def test_add_dependency_invalid_blocker_identifier_raises(self):
        tracker = self._make_tracker()
        with pytest.raises(TrackerError):
            tracker.add_dependency("example-org/oompah-tasks#10", "bad-id")

    # ------------------------------------------------------------------
    # _gh_issue_to_issue extracts parent and dependencies from labels
    # ------------------------------------------------------------------

    def test_gh_issue_to_issue_extracts_parent_from_label(self):
        """parent:<number> label is converted to parent_id on the Issue."""
        from oompah.github_tracker import _gh_issue_to_issue
        gh_issue = _make_gh_issue(number=10, labels=["parent:5"])
        issue = _gh_issue_to_issue(gh_issue, owner="example-org", repo="oompah-tasks")
        assert issue.parent_id == "example-org/oompah-tasks#5"

    def test_gh_issue_to_issue_extracts_parent_from_body(self):
        """A leading Parent: #<number> body line is converted to parent_id."""
        from oompah.github_tracker import _gh_issue_to_issue
        gh_issue = _make_gh_issue(number=10, body="Parent: #5\n\nWork details")
        issue = _gh_issue_to_issue(gh_issue, owner="example-org", repo="oompah-tasks")
        assert issue.parent_id == "example-org/oompah-tasks#5"

    def test_gh_issue_to_issue_parent_label_beats_body(self):
        """Explicit parent labels remain authoritative over body hints."""
        from oompah.github_tracker import _gh_issue_to_issue
        gh_issue = _make_gh_issue(number=10, labels=["parent:5"], body="Parent: #7")
        issue = _gh_issue_to_issue(gh_issue, owner="example-org", repo="oompah-tasks")
        assert issue.parent_id == "example-org/oompah-tasks#5"

    def test_gh_issue_to_issue_no_parent_when_no_label(self):
        """Issue has no parent_id when parent: label is absent."""
        from oompah.github_tracker import _gh_issue_to_issue
        gh_issue = _make_gh_issue(number=10)
        issue = _gh_issue_to_issue(gh_issue, owner="example-org", repo="oompah-tasks")
        assert issue.parent_id is None

    def test_gh_issue_to_issue_extracts_dependencies_from_labels(self):
        """depends-on:<number> labels are converted to blocked_by on the Issue."""
        from oompah.github_tracker import _gh_issue_to_issue
        gh_issue = _make_gh_issue(number=10, labels=["depends-on:5", "depends-on:7"])
        issue = _gh_issue_to_issue(gh_issue, owner="example-org", repo="oompah-tasks")
        assert len(issue.blocked_by) == 2
        dep_ids = {b.identifier for b in issue.blocked_by}
        assert "example-org/oompah-tasks#5" in dep_ids
        assert "example-org/oompah-tasks#7" in dep_ids

    def test_gh_issue_to_issue_no_dependencies_when_no_labels(self):
        """Issue has empty blocked_by when depends-on: labels are absent."""
        from oompah.github_tracker import _gh_issue_to_issue
        gh_issue = _make_gh_issue(number=10)
        issue = _gh_issue_to_issue(gh_issue, owner="example-org", repo="oompah-tasks")
        assert issue.blocked_by == []

    def test_gh_issue_to_issue_excludes_parent_and_depends_on_from_user_labels(self):
        """parent: and depends-on: labels are excluded from user-facing labels."""
        from oompah.github_tracker import _gh_issue_to_issue
        gh_issue = _make_gh_issue(number=10, labels=["parent:5", "depends-on:7", "needs:backend"])
        issue = _gh_issue_to_issue(gh_issue, owner="example-org", repo="oompah-tasks")
        assert issue.labels == ["needs:backend"]
        assert "parent:5" not in issue.labels
        assert "depends-on:7" not in issue.labels

    # ------------------------------------------------------------------
    # fetch_children returns children with parent_id populated
    # ------------------------------------------------------------------

    def test_fetch_children_returns_children_with_parent_id(self):
        """Children returned by fetch_children have parent_id set."""
        tracker = self._make_tracker()
        # Use fallback label-based path
        resp_404 = _mock_response(404, text="Not Found")
        resp_404.is_success = False
        children = [
            _make_gh_issue(number=10, labels=["parent:5", "oompah:status:open"]),
            _make_gh_issue(number=11, labels=["parent:5", "oompah:status:open"]),
        ]
        resp_200 = _mock_response(200, json_data=children)
        with patch.object(
            tracker._client._http, "request", side_effect=[resp_404, resp_200]
        ):
            result = tracker.fetch_children("example-org/oompah-tasks#5")
        assert len(result) == 2
        for child in result:
            assert child.parent_id == "example-org/oompah-tasks#5"

    # ------------------------------------------------------------------
    # fetch_issue_detail returns issue with blocked_by populated
    # ------------------------------------------------------------------

    def test_fetch_issue_detail_returns_blocked_by(self):
        """Issues fetched via fetch_issue_detail have blocked_by from depends-on labels."""
        tracker = self._make_tracker()
        gh_issue = _make_gh_issue(number=10, labels=["depends-on:5", "depends-on:7"])
        resp = _mock_response(200, json_data=gh_issue)
        with patch.object(tracker._client._http, "request", return_value=resp):
            issue = tracker.fetch_issue_detail("example-org/oompah-tasks#10")
        assert issue is not None
        assert len(issue.blocked_by) == 2
        dep_ids = {b.identifier for b in issue.blocked_by}
        assert "example-org/oompah-tasks#5" in dep_ids
        assert "example-org/oompah-tasks#7" in dep_ids


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(scope="session")
def rsa_key_pair():
    """Generate a fresh RSA key pair for testing GitHub App JWT signing."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem
