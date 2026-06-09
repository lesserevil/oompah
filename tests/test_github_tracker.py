"""Tests for oompah.github_tracker — GitHub auth, API client, and identifier support.

Covers acceptance criteria:
  #1  Identifier parsing rejects ambiguous bare numbers.
  #2  Display identifiers and branch slugs are stable and filesystem-safe.
  #3  GitHub App, PAT, and missing-auth paths.
  #4  Rate-limit and auth errors become actionable TrackerError messages.
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

    def _make(self, owner="lesserevil", repo="oompah-tasks", number=1234):
        return GitHubIdentifier(owner=owner, repo=repo, number=number)

    # ------------------------------------------------------------------
    # canonical form
    # ------------------------------------------------------------------

    def test_canonical_format(self):
        gh = self._make()
        assert gh.canonical == "lesserevil/oompah-tasks#1234"

    def test_str_returns_canonical(self):
        gh = self._make()
        assert str(gh) == "lesserevil/oompah-tasks#1234"

    def test_canonical_single_digit_number(self):
        gh = self._make(number=1)
        assert gh.canonical == "lesserevil/oompah-tasks#1"

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
        assert gh.url_safe == "lesserevil/oompah-tasks/1234"

    def test_url_safe_three_components(self):
        gh = self._make()
        parts = gh.url_safe.split("/")
        assert len(parts) == 3
        assert parts[0] == "lesserevil"
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
        gh = parse_github_identifier("lesserevil/oompah-tasks#1234")
        assert gh.owner == "lesserevil"
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
        gh = parse_github_identifier("  lesserevil/oompah-tasks#42  ")
        assert gh.canonical == "lesserevil/oompah-tasks#42"

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
        gh = GitHubIdentifier(owner="lesserevil", repo="oompah-tasks", number=1)
        result = github_identifier_to_issue_fields(gh)
        assert isinstance(result, dict)

    def test_contains_tracker_kind(self):
        gh = GitHubIdentifier(owner="o", repo="r", number=1)
        result = github_identifier_to_issue_fields(gh)
        assert result["tracker_kind"] == "github_issues"

    def test_contains_owner(self):
        gh = GitHubIdentifier(owner="myorg", repo="tasks", number=5)
        result = github_identifier_to_issue_fields(gh)
        assert result["owner"] == "myorg"

    def test_contains_repo(self):
        gh = GitHubIdentifier(owner="o", repo="myrepo", number=5)
        result = github_identifier_to_issue_fields(gh)
        assert result["repo"] == "myrepo"

    def test_issue_number_is_string(self):
        """issue_number is a string to match the Issue model field type."""
        gh = GitHubIdentifier(owner="o", repo="r", number=42)
        result = github_identifier_to_issue_fields(gh)
        assert result["issue_number"] == "42"
        assert isinstance(result["issue_number"], str)

    def test_display_identifier(self):
        gh = GitHubIdentifier(owner="lesserevil", repo="oompah-tasks", number=1234)
        result = github_identifier_to_issue_fields(gh)
        assert result["display_identifier"] == "oompah-tasks#1234"

    def test_can_unpack_into_issue(self):
        """The returned dict can be unpacked as Issue keyword arguments."""
        from oompah.models import Issue
        gh = GitHubIdentifier(owner="lesserevil", repo="oompah-tasks", number=7)
        fields = github_identifier_to_issue_fields(gh)
        issue = Issue(
            id="7",
            identifier=gh.canonical,
            title="Test",
            **fields,
        )
        assert issue.tracker_kind == "github_issues"
        assert issue.owner == "lesserevil"
        assert issue.repo == "oompah-tasks"
        assert issue.issue_number == "7"
        assert issue.display_identifier == "oompah-tasks#7"


# ===========================================================================
# GitHubIssueTracker identifier helpers
# ===========================================================================


class TestGitHubIssueTrackerIdentifierHelpers:
    """Tests for parse_identifier() and identifier_for_number() on the tracker."""

    def _make_tracker(self) -> GitHubIssueTracker:
        return GitHubIssueTracker(
            owner="lesserevil",
            repo="oompah-tasks",
            active_states=["Open", "In Progress"],
            terminal_states=["Done", "Archived"],
            auth=GitHubAuth(pat="test_token"),
        )

    def test_parse_identifier_valid(self):
        tracker = self._make_tracker()
        gh = tracker.parse_identifier("lesserevil/oompah-tasks#42")
        assert gh.owner == "lesserevil"
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
        assert gh.owner == "lesserevil"
        assert gh.repo == "oompah-tasks"
        assert gh.number == 99
        assert gh.canonical == "lesserevil/oompah-tasks#99"

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
            owner="lesserevil",
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
            identifier="lesserevil/oompah-tasks#1",
            title="Test",
            state="Archived",
        )
        assert tracker.is_archived(issue) is True

    def test_is_archived_non_archived(self):
        tracker = self._make_tracker()
        issue = Issue(
            id="gh-2",
            identifier="lesserevil/oompah-tasks#2",
            title="Active",
            state="Open",
        )
        assert tracker.is_archived(issue) is False

    def test_invalidate_read_cache(self):
        tracker = self._make_tracker()
        tracker._etag_cache["some_path"] = ('"etag"', [{"id": 1}])
        tracker.invalidate_read_cache()
        assert tracker._etag_cache == {}

    def test_fetch_candidate_issues_returns_empty_list(self):
        tracker = self._make_tracker()
        assert tracker.fetch_candidate_issues() == []

    def test_fetch_all_issues_returns_empty_list(self):
        tracker = self._make_tracker()
        assert tracker.fetch_all_issues() == []

    def test_fetch_attachments_returns_empty_list(self):
        tracker = self._make_tracker()
        assert tracker.fetch_attachments("lesserevil/oompah-tasks#1") == []

    def test_fetch_memories_returns_empty_dict(self):
        tracker = self._make_tracker()
        assert tracker.fetch_memories() == {}

    def test_get_metadata_returns_empty_dict(self):
        tracker = self._make_tracker()
        assert tracker.get_metadata("lesserevil/oompah-tasks#1") == {}

    def test_create_issue_raises_not_implemented(self):
        tracker = self._make_tracker()
        with pytest.raises(NotImplementedError):
            tracker.create_issue("Test issue")

    def test_add_comment_raises_not_implemented(self):
        tracker = self._make_tracker()
        with pytest.raises(NotImplementedError):
            tracker.add_comment("lesserevil/oompah-tasks#1", "hello")

    def test_repo_path_helper(self):
        tracker = self._make_tracker()
        assert tracker._repo_path() == "/repos/lesserevil/oompah-tasks"
        assert tracker._repo_path("/issues") == "/repos/lesserevil/oompah-tasks/issues"


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
        monkeypatch.setenv("OOMPAH_GITHUB_TRACKER_OWNER", "lesserevil")
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
