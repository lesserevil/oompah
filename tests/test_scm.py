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


class TestReviewRequest:
    def test_to_dict(self):
        rr = ReviewRequest(
            id="42", title="Fix typo", url="https://github.com/x/y/pull/42",
            author="alice", state="open", source_branch="fix-typo",
            target_branch="main", created_at="2025-01-01", updated_at="2025-01-02",
            needs_rebase=True, draft=True,
        )
        d = rr.to_dict()
        assert d["id"] == "42"
        assert d["needs_rebase"] is True
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
        assert rr.additions == 0
        assert rr.deletions == 0
