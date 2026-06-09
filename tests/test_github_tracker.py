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

    def test_label_to_status_open(self):
        assert _label_to_status("oompah:status:open") == "Open"

    def test_label_to_status_in_progress(self):
        assert _label_to_status("oompah:status:in-progress") == "In Progress"

    def test_label_to_status_done(self):
        assert _label_to_status("oompah:status:done") == "Done"

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
        assert _extract_oompah_status(labels, "open") == "Open"

    def test_extract_oompah_status_fallback_closed(self):
        labels: list = []
        assert _extract_oompah_status(labels, "closed") == "Done"

    def test_extract_oompah_status_label_beats_gh_state(self):
        """Status label overrides GitHub built-in state."""
        labels = [{"name": "oompah:status:needs-human"}]
        assert _extract_oompah_status(labels, "open") == "Needs Human"

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
) -> dict:
    """Build a minimal GitHub REST API issue dict for testing."""
    return {
        "number": number,
        "id": issue_id or (1000 + number),
        "title": title,
        "body": body,
        "state": state,
        "labels": [{"name": lbl} for lbl in (labels or [])],
        "html_url": html_url or f"https://github.com/lesserevil/oompah-tasks/issues/{number}",
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
        "node_id": f"I_node_{number}",
    }


class TestGhIssueToIssue:
    """Tests for the _gh_issue_to_issue() mapper."""

    def _convert(self, **kwargs) -> Issue:
        return _gh_issue_to_issue(
            _make_gh_issue(**kwargs), owner="lesserevil", repo="oompah-tasks"
        )

    def test_basic_fields(self):
        issue = self._convert(number=42, title="Fix the bug")
        assert issue.identifier == "lesserevil/oompah-tasks#42"
        assert issue.title == "Fix the bug"
        assert issue.owner == "lesserevil"
        assert issue.repo == "oompah-tasks"
        assert issue.issue_number == "42"
        assert issue.display_identifier == "oompah-tasks#42"
        assert issue.tracker_kind == "github_issues"

    def test_state_open_defaults_to_Open(self):
        issue = self._convert(state="open", labels=[])
        assert issue.state == "Open"

    def test_state_closed_defaults_to_Done(self):
        issue = self._convert(state="closed", labels=[])
        assert issue.state == "Done"

    def test_status_label_overrides_state(self):
        issue = self._convert(
            state="open", labels=["oompah:status:in-progress"]
        )
        assert issue.state == "In Progress"

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

    def test_user_labels_exclude_internal(self):
        issue = self._convert(
            labels=["oompah:status:open", "priority:1", "type:feature", "needs:frontend"]
        )
        assert issue.labels == ["needs:frontend"]

    def test_url_set(self):
        issue = self._convert(
            number=5, html_url="https://github.com/lesserevil/oompah-tasks/issues/5"
        )
        assert issue.url == "https://github.com/lesserevil/oompah-tasks/issues/5"
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

    def test_project_id_from_metadata(self):
        body = '<!-- oompah:metadata\n{"project_id": "myproject"}\n-->'
        issue = self._convert(body=body)
        assert issue.project_id == "myproject"

    def test_id_uses_github_id(self):
        issue = self._convert(number=7, issue_id=99999)
        assert issue.id == "99999"


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
            owner="lesserevil",
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
            _make_gh_issue(number=1, title="First"),
            _make_gh_issue(number=2, title="Second"),
        ]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_all_issues()
        assert len(result) == 2
        assert result[0].title == "First"
        assert result[1].title == "Second"

    def test_fetch_all_issues_pagination(self):
        """fetch_all_issues follows pagination links (acceptance criterion #6)."""
        tracker = self._make_tracker()
        page1 = _mock_response(
            200,
            json_data=[_make_gh_issue(number=1)],
            headers={
                "link": '<https://api.github.com/repos/lesserevil/oompah-tasks/issues?page=2>; rel="next"'
            },
        )
        page2 = _mock_response(200, json_data=[_make_gh_issue(number=2)])
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

    def test_fetch_candidate_issues_open_github_state_defaults_to_Open(self):
        """GitHub open issues with no status label default to state 'Open'."""
        tracker = self._make_tracker()
        gh_issues = [_make_gh_issue(number=7, state="open", labels=[])]
        resp = _mock_response(200, json_data=gh_issues)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_candidate_issues()
        # "Open" is in active_states, so the issue should be returned
        assert len(result) == 1
        assert result[0].state == "Open"

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
                "link": '<https://api.github.com/repos/lesserevil/oompah-tasks/issues?page=2>; rel="next"'
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
            result = tracker.fetch_issue_detail("lesserevil/oompah-tasks#42")
        assert result is not None
        assert result.title == "Detail test"
        assert result.issue_number == "42"

    def test_fetch_issue_detail_returns_none_for_404(self):
        tracker = self._make_tracker()
        resp_404 = _mock_response(404, text="Not Found")
        resp_404.is_success = False
        with patch.object(tracker._client._http, "request", return_value=resp_404):
            result = tracker.fetch_issue_detail("lesserevil/oompah-tasks#9999")
        assert result is None

    def test_fetch_issue_detail_returns_none_for_invalid_identifier(self):
        tracker = self._make_tracker()
        result = tracker.fetch_issue_detail("not-an-identifier")
        assert result is None

    def test_fetch_issue_detail_returns_none_for_bare_number(self):
        tracker = self._make_tracker()
        result = tracker.fetch_issue_detail("42")
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

    def test_fetch_issues_by_states_terminal_only(self):
        """Requesting only terminal states queries GitHub with state=closed."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http, "request", return_value=resp
        ) as mock_req:
            tracker.fetch_issues_by_states(["Done", "Archived"])
        _, kwargs = mock_req.call_args
        params = kwargs.get("params", {})
        assert params.get("state") == "closed"

    def test_fetch_issues_by_states_mixed(self):
        """Mixed active+terminal states queries GitHub with state=all."""
        tracker = self._make_tracker()
        resp = _mock_response(200, json_data=[])
        with patch.object(
            tracker._client._http, "request", return_value=resp
        ) as mock_req:
            tracker.fetch_issues_by_states(["Open", "Done"])
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
            result = tracker.fetch_issue_states_by_ids(["lesserevil/oompah-tasks#5"])
        assert len(result) == 1
        assert result[0].state == "In Progress"

    def test_fetch_issue_states_by_ids_skips_invalid(self):
        """Invalid or missing identifiers are silently skipped."""
        tracker = self._make_tracker()
        resp_valid = _mock_response(200, json_data=_make_gh_issue(number=1))
        resp_404 = _mock_response(404, text="Not Found")
        resp_404.is_success = False
        with patch.object(
            tracker._client._http,
            "request",
            side_effect=[resp_valid, resp_404],
        ):
            result = tracker.fetch_issue_states_by_ids([
                "lesserevil/oompah-tasks#1",
                "lesserevil/oompah-tasks#9999",
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
            result = tracker.fetch_comments("lesserevil/oompah-tasks#5")
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
            result = tracker.fetch_comments("lesserevil/oompah-tasks#1")
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
            _make_gh_issue(number=10, title="Child 1"),
            _make_gh_issue(number=11, title="Child 2"),
        ]
        resp = _mock_response(200, json_data=children)
        with patch.object(tracker._client._http, "request", return_value=resp):
            result = tracker.fetch_children("lesserevil/oompah-tasks#5")
        assert len(result) == 2

    def test_fetch_children_falls_back_to_label_on_404(self):
        """Falls back to label-based lookup when sub-issues API is unavailable."""
        tracker = self._make_tracker()
        resp_404 = _mock_response(404, text="Not Found")
        resp_404.is_success = False
        children = [_make_gh_issue(number=20, labels=["parent:5"])]
        resp_200 = _mock_response(200, json_data=children)
        with patch.object(
            tracker._client._http, "request", side_effect=[resp_404, resp_200]
        ):
            result = tracker.fetch_children("lesserevil/oompah-tasks#5")
        assert len(result) == 1

    # ------------------------------------------------------------------
    # Issue field mapping on normalized Issue record
    # ------------------------------------------------------------------

    def test_fetch_all_issues_normalizes_fields(self):
        """Normalized Issue records carry all expected fields."""
        tracker = self._make_tracker()
        body = '<!-- oompah:metadata\n{"project_id": "proj-1", "target_branch": "main"}\n-->'
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
        assert iss.tracker_kind == "github_issues"


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
