"""Tests for oompah.scm."""

from oompah.scm import (
    ReviewRequest,
    _truncate,
    detect_provider,
    extract_repo_slug,
    GitHubProvider,
    GitLabProvider,
)


class TestExtractRepoSlug:
    def test_https_github(self):
        assert extract_repo_slug("https://github.com/org/repo.git") == "org/repo"

    def test_https_github_no_git(self):
        assert extract_repo_slug("https://github.com/org/repo") == "org/repo"

    def test_ssh_github(self):
        assert extract_repo_slug("git@github.com:org/repo.git") == "org/repo"

    def test_ssh_github_no_git(self):
        assert extract_repo_slug("git@github.com:org/repo") == "org/repo"

    def test_https_gitlab(self):
        assert extract_repo_slug("https://gitlab.com/group/project.git") == "group/project"

    def test_https_trailing_slash(self):
        assert extract_repo_slug("https://github.com/org/repo/") == "org/repo"

    def test_nested_gitlab_group(self):
        assert extract_repo_slug("https://gitlab.com/group/sub/project.git") == "group/sub/project"


class TestDetectProvider:
    def test_github(self):
        provider = detect_provider("https://github.com/org/repo")
        assert provider is not None
        assert isinstance(provider, GitHubProvider)
        assert provider.provider_name() == "github"

    def test_gitlab(self):
        provider = detect_provider("https://gitlab.com/group/project")
        assert provider is not None
        assert isinstance(provider, GitLabProvider)
        assert provider.provider_name() == "gitlab"

    def test_self_hosted_gitlab(self):
        provider = detect_provider("https://gitlab.company.com/group/project")
        assert provider is not None
        assert isinstance(provider, GitLabProvider)

    def test_unknown(self):
        provider = detect_provider("https://bitbucket.org/org/repo")
        assert provider is None

    def test_ssh_github(self):
        provider = detect_provider("git@github.com:org/repo.git")
        assert provider is not None
        assert isinstance(provider, GitHubProvider)


class TestProviderAccessToken:
    """The per-project access_token must reach the provider's auth header
    and short-circuit the env/CLI fallback."""

    def test_github_uses_explicit_token_in_authorization_header(self):
        provider = GitHubProvider(access_token="ghp_test_token")
        headers = provider._headers()
        assert headers["Authorization"] == "Bearer ghp_test_token"

    def test_gitlab_uses_explicit_token_in_private_token_header(self):
        provider = GitLabProvider(access_token="glpat-test-token")
        headers = provider._headers()
        assert headers["PRIVATE-TOKEN"] == "glpat-test-token"

    def test_github_explicit_token_skips_env_resolution(self, monkeypatch):
        # Set env vars that would otherwise be picked up; constructor token wins.
        monkeypatch.setenv("GH_TOKEN", "env_token_should_not_be_used")
        monkeypatch.setenv("GITHUB_TOKEN", "env_token_should_not_be_used")
        provider = GitHubProvider(access_token="explicit_wins")
        assert provider._headers()["Authorization"] == "Bearer explicit_wins"

    def test_gitlab_explicit_token_skips_env_resolution(self, monkeypatch):
        monkeypatch.setenv("GITLAB_TOKEN", "env_token_should_not_be_used")
        monkeypatch.setenv("GITLAB_API_TOKEN", "env_token_should_not_be_used")
        provider = GitLabProvider(access_token="explicit_wins")
        assert provider._headers()["PRIVATE-TOKEN"] == "explicit_wins"

    def test_detect_provider_threads_token_to_github(self):
        provider = detect_provider(
            "https://github.com/org/repo", access_token="ghp_passthrough",
        )
        assert isinstance(provider, GitHubProvider)
        assert provider._headers()["Authorization"] == "Bearer ghp_passthrough"

    def test_detect_provider_threads_token_to_gitlab(self):
        provider = detect_provider(
            "https://gitlab.com/group/project", access_token="glpat-passthrough",
        )
        assert isinstance(provider, GitLabProvider)
        assert provider._headers()["PRIVATE-TOKEN"] == "glpat-passthrough"

    def test_detect_provider_token_optional(self):
        # Default behavior unchanged when no token supplied.
        provider = detect_provider("https://github.com/org/repo")
        assert isinstance(provider, GitHubProvider)


class TestTruncate:
    def test_short_string(self):
        assert _truncate("hello", 10) == "hello"

    def test_exact_length(self):
        assert _truncate("hello", 5) == "hello"

    def test_long_string(self):
        assert _truncate("hello world", 8) == "hello..."

    def test_empty_string(self):
        assert _truncate("", 10) == ""

    def test_none_string(self):
        assert _truncate(None, 10) == ""


class TestFetchCiStatus:
    """The combined-status API returns state='pending' with total_count=0
    for repos that only use GitHub Actions (no legacy commit-statuses).
    In that case we must fall through to the check-runs endpoint instead
    of declaring the PR pending and blocking the YOLO auto-merge forever."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    def _provider_with_responses(self, status_payload, checkruns_payload):
        provider = GitHubProvider(access_token="t")
        responses = {
            "/status": self._FakeResponse(status_payload),
            "/check-runs": self._FakeResponse(checkruns_payload),
        }

        def fake_api(method, path, **kwargs):
            for suffix, resp in responses.items():
                if path.endswith(suffix):
                    return resp
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api
        return provider

    def test_actions_only_repo_falls_through_to_check_runs(self):
        # Combined-status: pending+total_count=0 (no legacy statuses); check-runs all green.
        provider = self._provider_with_responses(
            {"state": "pending", "total_count": 0},
            {"check_runs": [
                {"conclusion": "success", "status": "completed"},
                {"conclusion": "success", "status": "completed"},
            ]},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == "passed"

    def test_actions_only_repo_with_failing_check_run(self):
        provider = self._provider_with_responses(
            {"state": "pending", "total_count": 0},
            {"check_runs": [
                {"conclusion": "success", "status": "completed"},
                {"conclusion": "failure", "status": "completed"},
            ]},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == "failed"

    def test_legacy_pending_with_real_statuses_is_trusted(self):
        # When total_count > 0 and state='pending', legacy CI is genuinely pending.
        provider = self._provider_with_responses(
            {"state": "pending", "total_count": 2},
            {"check_runs": []},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == "pending"

    def test_legacy_success_short_circuits(self):
        provider = self._provider_with_responses(
            {"state": "success", "total_count": 1},
            {"check_runs": []},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == "passed"

    def test_legacy_failure_short_circuits(self):
        provider = self._provider_with_responses(
            {"state": "failure", "total_count": 1},
            {"check_runs": []},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == "failed"

    def test_no_statuses_and_no_check_runs_returns_empty(self):
        provider = self._provider_with_responses(
            {"state": "pending", "total_count": 0},
            {"check_runs": []},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == ""


class TestReviewRequest:
    def test_to_dict(self):
        rr = ReviewRequest(
            id="42", title="Fix typo", url="https://github.com/x/y/pull/42",
            author="alice", state="open", source_branch="fix-typo",
            target_branch="main", created_at="2025-01-01", updated_at="2025-01-02",
            needs_rebase=True, has_conflicts=True, draft=True,
        )
        d = rr.to_dict()
        assert d["id"] == "42"
        assert d["needs_rebase"] is True
        assert d["has_conflicts"] is True
        assert d["draft"] is True
        assert d["source_branch"] == "fix-typo"

    def test_defaults(self):
        rr = ReviewRequest(
            id="1", title="t", url="u", author="a", state="open",
            source_branch="b", target_branch="main",
            created_at="", updated_at="",
        )
        assert rr.description == ""
        assert rr.labels == []
        assert rr.draft is False
        assert rr.needs_rebase is False
        assert rr.has_conflicts is False
        assert rr.additions == 0
        assert rr.deletions == 0
