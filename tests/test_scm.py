"""Tests for oompah.scm."""

import os
import time
from unittest import mock

from oompah.scm import (
    ReviewRequest,
    _is_protected_branch,
    _read_pr_detail_cache_ttl,
    _truncate,
    detect_provider,
    extract_repo_slug,
    GitHubProvider,
    GitLabProvider,
)


class TestIsProtectedBranch:
    """``_is_protected_branch`` guards post-merge auto-cleanup so long-lived
    branches (release/*, main, ...) are never deleted, even as a PR head."""

    def test_release_and_hotfix_prefixes_protected(self):
        assert _is_protected_branch("release/v0.9")
        assert _is_protected_branch("release/0.10")
        assert _is_protected_branch("hotfix/urgent")

    def test_permanent_branches_protected(self):
        for b in ("main", "master", "develop", "dev", "trunk"):
            assert _is_protected_branch(b)

    def test_merge_queue_and_dolt_refs_protected(self):
        assert _is_protected_branch("gh-readonly-queue/main/pr-109-abc")
        assert _is_protected_branch("__dolt_remote_info__")

    def test_empty_is_protected(self):
        # Defensive: never delete on a missing/blank ref.
        assert _is_protected_branch("")

    def test_default_branch_protected(self):
        assert _is_protected_branch("production", default_branch="production")

    def test_feature_branches_not_protected(self):
        # Regular work branches ARE eligible for auto-cleanup — including a
        # feature branch that merely has "release" in its name.
        assert not _is_protected_branch("trickle-release-features")
        assert not _is_protected_branch("epic-TASK-270")
        assert not _is_protected_branch("trickle-abc1")
        assert not _is_protected_branch("TASK-704")


class TestMergeReviewBranchCleanupProtection:
    """merge_review() must not auto-delete a protected source/head branch."""

    def _github(self):
        provider = GitHubProvider(access_token="t")
        calls = []

        class _Resp:
            def __init__(self, code, payload=None):
                self.status_code = code
                self._payload = payload or {}
                self.text = ""

            def json(self):
                return self._payload

        def fake_api(method, path, **kwargs):
            calls.append((method, path))
            if path.endswith("/merge"):
                return _Resp(200)
            if "/pulls/" in path:  # GET PR detail
                return _Resp(200, {"head": {"ref": fake_api.head_ref}})
            return _Resp(200)

        provider._api = fake_api
        return provider, fake_api, calls

    def test_github_deletes_normal_head(self):
        provider, fake_api, calls = self._github()
        fake_api.head_ref = "trickle-abc1"
        ok, _ = provider.merge_review("o/r", "5")
        assert ok
        assert any(m == "DELETE" and "refs/heads/trickle-abc1" in p for m, p in calls)

    def test_github_skips_protected_head(self):
        provider, fake_api, calls = self._github()
        fake_api.head_ref = "release/0.10"
        ok, _ = provider.merge_review("o/r", "5")
        assert ok
        assert not any(m == "DELETE" for m, _ in calls)

    def _gitlab(self, source_branch):
        provider = GitLabProvider(access_token="t")
        merge_kwargs = {}

        class _Resp:
            def __init__(self, code, payload=None):
                self.status_code = code
                self._payload = payload or {}
                self.text = ""

            def json(self):
                return self._payload

        def fake_api(method, path, **kwargs):
            if path.endswith("/merge"):
                merge_kwargs.update(kwargs.get("json", {}))
                return _Resp(200)
            return _Resp(200, {"source_branch": source_branch})

        provider._api = fake_api
        return provider, merge_kwargs

    def test_gitlab_removes_normal_source(self):
        provider, merge_kwargs = self._gitlab("trickle-abc1")
        ok, _ = provider.merge_review("g/p", "5")
        assert ok
        assert merge_kwargs.get("should_remove_source_branch") is True

    def test_gitlab_keeps_protected_source(self):
        provider, merge_kwargs = self._gitlab("release/v0.9")
        ok, _ = provider.merge_review("g/p", "5")
        assert ok
        assert merge_kwargs.get("should_remove_source_branch") is False


class TestCloseReview:
    """close_review() closes stale reviews without merging them."""

    class _Resp:
        def __init__(self, code, payload=None, text=""):
            self.status_code = code
            self._payload = payload or {}
            self.text = text

        def json(self):
            return self._payload

    def test_github_posts_comment_then_closes_pr(self):
        provider = GitHubProvider(access_token="t")
        calls = []

        def fake_api(method, path, **kwargs):
            calls.append((method, path, kwargs.get("json")))
            if path.endswith("/comments"):
                return self._Resp(201)
            return self._Resp(200)

        provider._api = fake_api

        ok, msg = provider.close_review("o/r", "5", comment="audit")

        assert ok
        assert msg == "PR closed successfully"
        assert calls == [
            ("POST", "/repos/o/r/issues/5/comments", {"body": "audit"}),
            ("PATCH", "/repos/o/r/pulls/5", {"state": "closed"}),
        ]

    def test_gitlab_posts_note_then_closes_mr(self):
        provider = GitLabProvider(access_token="t")
        calls = []

        def fake_api(method, path, **kwargs):
            calls.append((method, path, kwargs.get("json")))
            if path.endswith("/notes"):
                return self._Resp(201)
            return self._Resp(200)

        provider._api = fake_api

        ok, msg = provider.close_review("g/p", "5", comment="audit")

        assert ok
        assert msg == "MR closed successfully"
        assert calls == [
            (
                "POST",
                "/projects/g%2Fp/merge_requests/5/notes",
                {"body": "audit"},
            ),
            (
                "PUT",
                "/projects/g%2Fp/merge_requests/5",
                {"state_event": "close"},
            ),
        ]


class TestReadPrDetailCacheTtl:
    """``_read_pr_detail_cache_ttl()`` reads
    ``OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS`` with a 60-second default and
    falls back safely on bad values (oompah-zlz_2-1of)."""

    def test_default_when_env_unset(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS", None)
            assert _read_pr_detail_cache_ttl() == 60.0

    def test_reads_env_var(self):
        with mock.patch.dict(
            os.environ, {"OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS": "30"}
        ):
            assert _read_pr_detail_cache_ttl() == 30.0

    def test_accepts_floats(self):
        with mock.patch.dict(
            os.environ, {"OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS": "12.5"}
        ):
            assert _read_pr_detail_cache_ttl() == 12.5

    def test_garbage_falls_back_to_default(self):
        with mock.patch.dict(
            os.environ, {"OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS": "not-a-number"}
        ):
            assert _read_pr_detail_cache_ttl() == 60.0

    def test_zero_falls_back_to_default(self):
        # A zero TTL would mean "never cache" — that's not a useful
        # configuration; treat it as a misconfiguration.
        with mock.patch.dict(
            os.environ, {"OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS": "0"}
        ):
            assert _read_pr_detail_cache_ttl() == 60.0

    def test_negative_falls_back_to_default(self):
        with mock.patch.dict(
            os.environ, {"OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS": "-5"}
        ):
            assert _read_pr_detail_cache_ttl() == 60.0


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
        # When combined-status reports failure but there are no modern
        # check-runs to override it, the legacy verdict still wins —
        # we have no other signal to trust.
        provider = self._provider_with_responses(
            {"state": "failure", "total_count": 1},
            {"check_runs": []},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == "failed"

    def test_legacy_failure_overridden_by_clean_check_runs(self):
        # Regression for oompah-zlz_2-c91: a stale legacy commit-status
        # entry reports failure on a repo whose modern GitHub Actions
        # check-runs are all green. Before the fix, _fetch_ci_status
        # short-circuited to "failed" and YOLO logged
        # "auto-retrying failed CI on trickle MR #23" every tick for
        # actually-passing PRs. Now: when legacy state=failure but
        # check-runs are all clean (including SKIPPED / NEUTRAL),
        # the modern check-runs override the stale legacy verdict.
        provider = self._provider_with_responses(
            {"state": "failure", "total_count": 1},
            {"check_runs": [
                {"conclusion": "success", "status": "completed"},
                {"conclusion": "success", "status": "completed"},
                {"conclusion": "skipped", "status": "completed"},
                {"conclusion": "neutral", "status": "completed"},
            ]},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == "passed"

    def test_legacy_failure_with_failing_check_run_stays_failed(self):
        # Both endpoints agree the PR is broken — return failed.
        provider = self._provider_with_responses(
            {"state": "failure", "total_count": 1},
            {"check_runs": [
                {"conclusion": "success", "status": "completed"},
                {"conclusion": "failure", "status": "completed"},
            ]},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == "failed"

    def test_legacy_failure_with_pending_check_run_returns_pending(self):
        # Modern check-runs are still in progress — wait for them
        # rather than honoring the (possibly stale) legacy failure.
        provider = self._provider_with_responses(
            {"state": "failure", "total_count": 1},
            {"check_runs": [
                {"conclusion": None, "status": "in_progress"},
                {"conclusion": "success", "status": "completed"},
            ]},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == "pending"

    def test_no_statuses_and_no_check_runs_returns_empty(self):
        provider = self._provider_with_responses(
            {"state": "pending", "total_count": 0},
            {"check_runs": []},
        )
        assert provider._fetch_ci_status("o/r", "deadbeef") == ""


class TestFetchCiStatusCheckRunsForbidden:
    """Regression tests for OOMPAH-210: HTTP 403 on check-runs endpoint.

    When the GitHub token lacks Checks access (common with fine-grained PATs
    that were not granted Actions: Read or the now-deprecated Checks: Read),
    oompah must fall back to the GitHub Actions workflow-runs API rather than
    silently returning an empty status.
    """

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    def _provider(
        self,
        *,
        status_payload,
        check_runs_status=403,
        workflow_runs_payload=None,
        workflow_runs_status=200,
    ):
        """Create a provider where check-runs always returns check_runs_status.

        ``workflow_runs_payload`` is the JSON body for the
        ``/actions/runs`` endpoint (used for the fallback path).
        """
        provider = GitHubProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if path.endswith("/status"):
                return self._FakeResponse(status_payload)
            if path.endswith("/check-runs"):
                # Simulate the 403 (or other non-200) from check-runs
                return self._FakeResponse({}, status_code=check_runs_status)
            if path.endswith("/actions/runs"):
                if workflow_runs_payload is None:
                    return self._FakeResponse({}, status_code=403)
                return self._FakeResponse(
                    workflow_runs_payload, status_code=workflow_runs_status
                )
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api
        return provider

    # ------------------------------------------------------------------ #
    # Workflow-runs available as fallback                                  #
    # ------------------------------------------------------------------ #

    def test_check_runs_403_workflow_runs_failed(self):
        """A failed workflow run is surfaced when check-runs returns 403."""
        provider = self._provider(
            status_payload={"state": "pending", "total_count": 0},
            workflow_runs_payload={"workflow_runs": [
                {"status": "completed", "conclusion": "failure"},
                {"status": "completed", "conclusion": "success"},
            ]},
        )
        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == "failed"
        assert warnings == []

    def test_check_runs_403_workflow_runs_passed(self):
        """All-green workflow runs surface 'passed' when check-runs is 403."""
        provider = self._provider(
            status_payload={"state": "pending", "total_count": 0},
            workflow_runs_payload={"workflow_runs": [
                {"status": "completed", "conclusion": "success"},
                {"status": "completed", "conclusion": "skipped"},
            ]},
        )
        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == "passed"
        assert warnings == []

    def test_check_runs_403_workflow_runs_pending(self):
        """In-progress workflow runs surface 'pending' when check-runs is 403."""
        provider = self._provider(
            status_payload={"state": "pending", "total_count": 0},
            workflow_runs_payload={"workflow_runs": [
                {"status": "in_progress", "conclusion": None},
                {"status": "completed", "conclusion": "success"},
            ]},
        )
        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == "pending"
        assert warnings == []

    def test_check_runs_403_workflow_runs_empty_returns_empty(self):
        """No workflow runs found → empty status (no CI data at all)."""
        provider = self._provider(
            status_payload={"state": "pending", "total_count": 0},
            workflow_runs_payload={"workflow_runs": []},
        )
        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == ""
        assert warnings == []

    def test_check_runs_403_timed_out_workflow_run_is_failed(self):
        """A timed-out workflow run is treated as CI failure."""
        provider = self._provider(
            status_payload={"state": "pending", "total_count": 0},
            workflow_runs_payload={"workflow_runs": [
                {"status": "completed", "conclusion": "timed_out"},
            ]},
        )
        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == "failed"

    # ------------------------------------------------------------------ #
    # legacy_pending + 403                                                 #
    # ------------------------------------------------------------------ #

    def test_legacy_pending_plus_check_runs_403_workflow_failed_returns_pending(self):
        """When legacy CI is pending, even a failed workflow run should not
        override it — we trust the legacy pending verdict and wait."""
        provider = self._provider(
            status_payload={"state": "pending", "total_count": 2},
            workflow_runs_payload={"workflow_runs": [
                {"status": "completed", "conclusion": "failure"},
            ]},
        )
        # legacy_pending is True → result should be "pending" regardless of
        # workflow-run conclusions (the legacy statuses are still in flight).
        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == "pending"

    def test_legacy_pending_plus_check_runs_403_workflow_passed_returns_pending(self):
        """legacy_pending always wins over a clean workflow fallback."""
        provider = self._provider(
            status_payload={"state": "pending", "total_count": 2},
            workflow_runs_payload={"workflow_runs": [
                {"status": "completed", "conclusion": "success"},
            ]},
        )
        status, _warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == "pending"

    # ------------------------------------------------------------------ #
    # legacy_failure + 403                                                 #
    # ------------------------------------------------------------------ #

    def test_legacy_failure_plus_check_runs_403_workflow_failed_returns_failed(self):
        """Both legacy and workflow agree: CI has failed."""
        provider = self._provider(
            status_payload={"state": "failure", "total_count": 1},
            workflow_runs_payload={"workflow_runs": [
                {"status": "completed", "conclusion": "failure"},
            ]},
        )
        status, _warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == "failed"

    def test_legacy_failure_plus_check_runs_403_workflow_passed_returns_passed(self):
        """Workflow-runs override a stale legacy failure when check-runs is 403."""
        provider = self._provider(
            status_payload={"state": "failure", "total_count": 1},
            workflow_runs_payload={"workflow_runs": [
                {"status": "completed", "conclusion": "success"},
            ]},
        )
        status, _warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == "passed"

    # ------------------------------------------------------------------ #
    # Neither check-runs nor workflow-runs available → degraded warning    #
    # ------------------------------------------------------------------ #

    def test_check_runs_and_workflow_runs_both_403_emits_capability_warning(self):
        """When both APIs are forbidden, a check_runs_forbidden warning is added."""
        provider = self._provider(
            status_payload={"state": "pending", "total_count": 0},
            # workflow_runs_payload=None means 403 is returned
        )
        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == ""
        assert len(warnings) == 1
        assert warnings[0]["type"] == "check_runs_forbidden"
        assert "Actions: Read" in warnings[0]["message"]

    def test_legacy_pending_both_forbidden_returns_pending_with_warning(self):
        """legacy_pending + both APIs forbidden → pending + degraded warning."""
        provider = self._provider(
            status_payload={"state": "pending", "total_count": 2},
        )
        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == "pending"
        assert any(w["type"] == "check_runs_forbidden" for w in warnings)

    def test_legacy_failure_both_forbidden_returns_failed_with_warning(self):
        """legacy_failure + both APIs forbidden → failed + degraded warning."""
        provider = self._provider(
            status_payload={"state": "failure", "total_count": 1},
        )
        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "abc")
        assert status == "failed"
        assert any(w["type"] == "check_runs_forbidden" for w in warnings)

    # ------------------------------------------------------------------ #
    # _fetch_workflow_runs_ci_status unit tests                           #
    # ------------------------------------------------------------------ #

    def test_fetch_workflow_runs_no_runs_returns_empty_status(self):
        """Empty workflow_runs list → ("", []) to distinguish from API-unavailable.

        An empty list means the Actions API is accessible but no workflow runs
        exist for this SHA (fresh commit or repo doesn't use Actions). We
        return ("", []) rather than None so the caller does NOT emit a
        check_runs_forbidden warning — the API is reachable, just empty.
        """
        provider = GitHubProvider(access_token="t")
        provider._api = lambda method, path, **kwargs: self._FakeResponse(
            {"workflow_runs": []}
        )
        result = provider._fetch_workflow_runs_ci_status("o/r", "abc")
        assert result is not None
        assert result[0] == ""
        assert result[1] == []

    def test_fetch_workflow_runs_non_200_returns_none(self):
        """Non-200 response (including 403) → None."""
        provider = GitHubProvider(access_token="t")
        provider._api = lambda method, path, **kwargs: self._FakeResponse(
            {}, status_code=403
        )
        result = provider._fetch_workflow_runs_ci_status("o/r", "abc")
        assert result is None

    def test_fetch_workflow_runs_failure_conclusion(self):
        provider = GitHubProvider(access_token="t")
        provider._api = lambda method, path, **kwargs: self._FakeResponse({
            "workflow_runs": [
                {"status": "completed", "conclusion": "failure"},
            ]
        })
        result = provider._fetch_workflow_runs_ci_status("o/r", "abc")
        assert result is not None
        assert result[0] == "failed"

    def test_fetch_workflow_runs_all_success(self):
        provider = GitHubProvider(access_token="t")
        provider._api = lambda method, path, **kwargs: self._FakeResponse({
            "workflow_runs": [
                {"status": "completed", "conclusion": "success"},
                {"status": "completed", "conclusion": "neutral"},
            ]
        })
        result = provider._fetch_workflow_runs_ci_status("o/r", "abc")
        assert result is not None
        assert result[0] == "passed"

    def test_fetch_workflow_runs_in_progress(self):
        provider = GitHubProvider(access_token="t")
        provider._api = lambda method, path, **kwargs: self._FakeResponse({
            "workflow_runs": [
                {"status": "in_progress", "conclusion": None},
            ]
        })
        result = provider._fetch_workflow_runs_ci_status("o/r", "abc")
        assert result is not None
        assert result[0] == "pending"


class TestGitHubCiRunnerWarnings:
    """Queued self-hosted Actions jobs should surface unavailable hardware."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    def _provider(
        self,
        *,
        check_runs,
        jobs=None,
        runners=None,
        pull_payload=None,
    ):
        provider = GitHubProvider(access_token="t")
        jobs = jobs or {}
        runners = runners or []

        def fake_api(method, path, **kwargs):
            if path.endswith("/status"):
                return self._FakeResponse({"state": "pending", "total_count": 0})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": check_runs})
            if "/actions/jobs/" in path:
                job_id = path.rsplit("/", 1)[-1]
                payload = jobs.get(job_id)
                if payload is None:
                    return self._FakeResponse({}, status_code=404)
                return self._FakeResponse(payload)
            if path.endswith("/actions/runners"):
                return self._FakeResponse({"runners": runners})
            if path.endswith("/pulls") and pull_payload is not None:
                return self._FakeResponse(pull_payload)
            if "/pulls/" in path:
                return self._FakeResponse({"mergeable": True, "mergeable_state": "blocked"})
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api
        provider._graphql = lambda query, variables=None: self._FakeResponse({
            "data": {"repository": {"mergeQueue": None}}
        })
        return provider

    def _queued_check_run(self, job_id="101"):
        return {
            "id": int(job_id),
            "name": "tier-b-windows",
            "status": "queued",
            "conclusion": None,
            "html_url": f"https://github.com/o/r/actions/runs/1/job/{job_id}",
        }

    def _job(self, job_id="101", labels=None):
        return {
            "id": int(job_id),
            "name": "tier-b-windows",
            "status": "queued",
            "labels": labels or ["self-hosted", "windows-nvidia"],
            "html_url": f"https://github.com/o/r/actions/runs/1/job/{job_id}",
        }

    def _runner(self, *, name="trickle-windows-runner", status="offline",
                busy=False, labels=None):
        return {
            "name": name,
            "status": status,
            "busy": busy,
            "labels": [
                {"name": label}
                for label in (labels or ["self-hosted", "X64", "Windows", "windows-nvidia"])
            ],
        }

    def test_offline_matching_runner_emits_warning(self):
        provider = self._provider(
            check_runs=[self._queued_check_run()],
            jobs={"101": self._job()},
            runners=[self._runner(status="offline", busy=False)],
        )

        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "sha")

        assert status == "pending"
        assert len(warnings) == 1
        warning = warnings[0]
        assert warning["type"] == "unavailable_runner"
        assert warning["reason"] == "offline"
        assert warning["job_name"] == "tier-b-windows"
        assert warning["labels"] == ["self-hosted", "windows-nvidia"]
        assert warning["matching_runners"] == ["trickle-windows-runner"]
        assert "offline" in warning["message"]

    def test_online_busy_matching_runner_is_not_unavailable(self):
        provider = self._provider(
            check_runs=[self._queued_check_run()],
            jobs={"101": self._job()},
            runners=[self._runner(status="online", busy=True)],
        )

        status, warnings = provider._fetch_ci_status_and_warnings("o/r", "sha")

        assert status == "pending"
        assert warnings == []

    def test_missing_matching_runner_emits_warning(self):
        provider = self._provider(
            check_runs=[self._queued_check_run()],
            jobs={"101": self._job()},
            runners=[self._runner(labels=["self-hosted", "linux-nvidia"])],
        )

        _status, warnings = provider._fetch_ci_status_and_warnings("o/r", "sha")

        assert len(warnings) == 1
        assert warnings[0]["reason"] == "missing"
        assert "no repository runner" in warnings[0]["message"]

    def test_hosted_runner_job_does_not_warn(self):
        provider = self._provider(
            check_runs=[self._queued_check_run()],
            jobs={"101": self._job(labels=["ubuntu-latest"])},
            runners=[],
        )

        _status, warnings = provider._fetch_ci_status_and_warnings("o/r", "sha")

        assert warnings == []

    def test_list_open_reviews_attaches_runner_warnings(self):
        pr = {
            "number": 11,
            "title": "Test PR",
            "html_url": "https://github.com/o/r/pull/11",
            "user": {"login": "alice"},
            "head": {"ref": "TASK-11", "sha": "sha"},
            "base": {"ref": "main"},
            "created_at": "2026-05-01T00:00:00Z",
            "updated_at": "2026-05-01T00:00:00Z",
            "body": "",
            "labels": [],
            "draft": False,
            "additions": 1,
            "deletions": 0,
            "mergeable": True,
            "mergeable_state": "blocked",
            "auto_merge": {"enabled_by": {"login": "alice"}},
        }
        provider = self._provider(
            check_runs=[self._queued_check_run()],
            jobs={"101": self._job()},
            runners=[self._runner(status="offline")],
            pull_payload=[pr],
        )

        reviews = provider.list_open_reviews("o/r")

        assert len(reviews) == 1
        assert reviews[0].ci_status == "pending"
        assert reviews[0].ci_warnings[0]["type"] == "unavailable_runner"


class TestReviewRequest:
    def test_to_dict(self):
        rr = ReviewRequest(
            id="42", title="Fix typo", url="https://github.com/x/y/pull/42",
            author="alice", state="open", source_branch="fix-typo",
            target_branch="main", created_at="2025-01-01", updated_at="2025-01-02",
            needs_rebase=True, has_conflicts=True, draft=True,
            auto_merge_enabled=True, mergeable_state="blocked",
            ci_warnings=[{
                "type": "unavailable_runner",
                "message": "tier-b-windows is queued for offline hardware.",
            }],
        )
        d = rr.to_dict()
        assert d["id"] == "42"
        assert d["needs_rebase"] is True
        assert d["has_conflicts"] is True
        assert d["draft"] is True
        assert d["source_branch"] == "fix-typo"
        assert d["auto_merge_enabled"] is True
        assert d["mergeable_state"] == "blocked"
        assert d["ci_warnings"][0]["type"] == "unavailable_runner"

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
        assert rr.auto_merge_enabled is False
        assert rr.mergeable_state == ""


# ---------------------------------------------------------------------------
# GitHub PR parsing: queue/auto-merge state
# ---------------------------------------------------------------------------


class TestGitHubReviewQueueState:
    """list_open_reviews and get_review must populate auto_merge_enabled
    and mergeable_state from the GitHub PR API response."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    def _provider(
        self,
        list_payload=None,
        get_payload=None,
        merge_queue_prs=(),
        in_merge_queue=False,
    ):
        provider = GitHubProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if path.endswith("/pulls") and list_payload is not None:
                return self._FakeResponse(list_payload)
            if "/pulls/" in path and "/status" not in path and "/check-runs" not in path:
                return self._FakeResponse(get_payload or {})
            # Stub out CI status calls so list_open_reviews doesn't blow up.
            if path.endswith("/status"):
                return self._FakeResponse({"state": "success", "total_count": 1})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": []})
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api

        # Stub GraphQL: the merge-queue list lookup (list_open_reviews) and
        # the per-PR isInMergeQueue lookup (get_review) both go through
        # _graphql. Distinguish by the variable shape: list-mode uses
        # only owner/name, single-PR mode also includes "number".
        list_nodes = [
            {"pullRequest": {"number": int(n)}} for n in merge_queue_prs
        ]
        list_payload_gql = {
            "data": {
                "repository": {
                    "mergeQueue": (
                        {"entries": {"nodes": list_nodes}}
                        if list_nodes else None
                    )
                }
            }
        }
        single_payload_gql = {
            "data": {
                "repository": {
                    "pullRequest": {"isInMergeQueue": bool(in_merge_queue)}
                }
            }
        }

        def fake_graphql(query, variables=None):
            variables = variables or {}
            if "number" in variables:
                return self._FakeResponse(single_payload_gql)
            return self._FakeResponse(list_payload_gql)

        provider._graphql = fake_graphql
        return provider

    def _pr_payload(self, **overrides):
        base = {
            "number": 11,
            "title": "Test PR",
            "html_url": "https://github.com/x/y/pull/11",
            "user": {"login": "alice"},
            "head": {"ref": "feat", "sha": "deadbeef"},
            "base": {"ref": "main"},
            "created_at": "2026-05-01T00:00:00Z",
            "updated_at": "2026-05-01T00:00:00Z",
            "body": "",
            "labels": [],
            "draft": False,
            "additions": 1,
            "deletions": 0,
            "mergeable": True,
            "mergeable_state": "clean",
            "auto_merge": None,
        }
        base.update(overrides)
        return base

    def test_list_open_reviews_auto_merge_enabled(self):
        pr = self._pr_payload(auto_merge={"enabled_by": {"login": "bob"},
                                          "merge_method": "SQUASH"})
        provider = self._provider(list_payload=[pr])
        reviews = provider.list_open_reviews("x/y")
        assert len(reviews) == 1
        assert reviews[0].auto_merge_enabled is True
        assert reviews[0].mergeable_state == "clean"

    def test_list_open_reviews_auto_merge_disabled(self):
        pr = self._pr_payload(auto_merge=None, mergeable_state="blocked")
        provider = self._provider(list_payload=[pr])
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].auto_merge_enabled is False
        assert reviews[0].mergeable_state == "blocked"

    def test_list_open_reviews_auto_merge_no_enabled_by(self):
        # Defensive: GitHub spec says enabled_by is set when active, but
        # if it ever returns an empty/null enabled_by we treat as disabled.
        pr = self._pr_payload(auto_merge={"enabled_by": None})
        provider = self._provider(list_payload=[pr])
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].auto_merge_enabled is False

    def test_get_review_auto_merge_enabled(self):
        pr = self._pr_payload(auto_merge={"enabled_by": {"login": "bob"}},
                              mergeable_state="behind")
        provider = self._provider(get_payload=pr)
        review = provider.get_review("x/y", "11")
        assert review is not None
        assert review.auto_merge_enabled is True
        assert review.mergeable_state == "behind"

    def test_get_review_auto_merge_disabled(self):
        pr = self._pr_payload(auto_merge=None)
        provider = self._provider(get_payload=pr)
        review = provider.get_review("x/y", "11")
        assert review is not None
        assert review.auto_merge_enabled is False
        assert review.mergeable_state == "clean"

    # ------------------------------------------------------------------
    # Merge queue: when GitHub takes a PR over from auto-merge into the
    # repo merge queue, the REST ``auto_merge`` field is cleared back to
    # null. The provider must still surface ``auto_merge_enabled=True``
    # so the YOLO idempotency guard fires and we don't re-enqueue every
    # tick. (oompah-zlz_2-btf.4)
    # ------------------------------------------------------------------

    def test_list_open_reviews_in_merge_queue_marks_auto_merge_enabled(self):
        # PR #11 is in the merge queue but its auto_merge field is null
        # (GitHub clears it once the queue takes over).
        pr = self._pr_payload(number=11, auto_merge=None,
                              mergeable_state="clean")
        provider = self._provider(list_payload=[pr], merge_queue_prs=[11])
        reviews = provider.list_open_reviews("x/y")
        assert len(reviews) == 1
        assert reviews[0].auto_merge_enabled is True, (
            "PR in merge queue must report auto_merge_enabled=True "
            "even when REST auto_merge is null"
        )

    def test_list_open_reviews_not_in_merge_queue_stays_disabled(self):
        # PR not in the queue and auto_merge=null → still disabled.
        pr = self._pr_payload(number=11, auto_merge=None,
                              mergeable_state="clean")
        provider = self._provider(list_payload=[pr], merge_queue_prs=[])
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].auto_merge_enabled is False

    def test_list_open_reviews_merge_queue_only_marks_matching_pr(self):
        pr11 = self._pr_payload(number=11, auto_merge=None)
        pr12 = self._pr_payload(number=12, auto_merge=None)
        # Only PR #11 is in the queue. PR #12 must remain disabled.
        provider = self._provider(
            list_payload=[pr11, pr12], merge_queue_prs=[11],
        )
        reviews = provider.list_open_reviews("x/y")
        # Order in response mirrors the GitHub list order.
        by_id = {r.id: r for r in reviews}
        assert by_id["11"].auto_merge_enabled is True
        assert by_id["12"].auto_merge_enabled is False

    def test_list_open_reviews_skips_merge_queue_call_when_no_prs(self):
        """Empty PR list ⇒ no merge-queue lookup (no PRs can be queued)."""
        graphql_calls: list[dict] = []
        provider = self._provider(list_payload=[])

        def tracking_graphql(query, variables=None):
            graphql_calls.append({"query": query, "variables": variables})
            return self._FakeResponse({"data": {"repository": {"mergeQueue": None}}})

        provider._graphql = tracking_graphql
        provider.list_open_reviews("x/y")
        assert graphql_calls == [], (
            "no GraphQL request should be issued when the LIST endpoint "
            "returns zero open PRs"
        )

    def test_list_open_reviews_repo_without_merge_queue(self):
        """mergeQueue=null in the GraphQL response is the success path
        for repos without a merge queue — not an error."""
        pr = self._pr_payload(number=11, auto_merge=None)
        provider = GitHubProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if path.endswith("/pulls"):
                return self._FakeResponse([pr])
            if "/pulls/" in path and "/status" not in path and "/check-runs" not in path:
                # Per-PR DETAIL fetch added for mergeable/mergeable_state
                # detection (oompah-zlz_2-8rb).
                return self._FakeResponse(pr)
            if path.endswith("/status"):
                return self._FakeResponse({"state": "success", "total_count": 1})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": []})
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api
        provider._graphql = lambda q, v=None: self._FakeResponse(
            {"data": {"repository": {"mergeQueue": None}}}
        )
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].auto_merge_enabled is False

    def test_list_open_reviews_merge_queue_graphql_error_is_safe(self):
        """A GraphQL failure must not blow up list_open_reviews — the
        worst case is a re-enqueue-every-tick (the original bug), not a
        crash that hides every other open PR."""
        pr = self._pr_payload(number=11, auto_merge=None)
        provider = GitHubProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if path.endswith("/pulls"):
                return self._FakeResponse([pr])
            if "/pulls/" in path and "/status" not in path and "/check-runs" not in path:
                # Per-PR DETAIL fetch added for mergeable/mergeable_state
                # detection (oompah-zlz_2-8rb).
                return self._FakeResponse(pr)
            if path.endswith("/status"):
                return self._FakeResponse({"state": "success", "total_count": 1})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": []})
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api
        provider._graphql = lambda q, v=None: self._FakeResponse(
            {"errors": [{"message": "boom"}]}
        )
        reviews = provider.list_open_reviews("x/y")
        # No crash, default behaviour: empty queue ⇒ auto_merge_enabled=False
        assert reviews[0].auto_merge_enabled is False

    def test_get_review_in_merge_queue_marks_auto_merge_enabled(self):
        # PR has auto_merge=null but is in the merge queue.
        pr = self._pr_payload(auto_merge=None, mergeable_state="clean")
        provider = self._provider(get_payload=pr, in_merge_queue=True)
        review = provider.get_review("x/y", "11")
        assert review is not None
        assert review.auto_merge_enabled is True

    def test_get_review_not_in_merge_queue_stays_disabled(self):
        pr = self._pr_payload(auto_merge=None, mergeable_state="clean")
        provider = self._provider(get_payload=pr, in_merge_queue=False)
        review = provider.get_review("x/y", "11")
        assert review is not None
        assert review.auto_merge_enabled is False

    def test_get_review_with_auto_merge_skips_queue_lookup(self):
        """When auto_merge is already populated we don't pay for an
        extra isInMergeQueue GraphQL call — the result is already
        True."""
        pr = self._pr_payload(
            auto_merge={"enabled_by": {"login": "bob"}},
            mergeable_state="clean",
        )
        graphql_calls: list[dict] = []
        provider = GitHubProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if "/pulls/" in path:
                return self._FakeResponse(pr)
            raise AssertionError(f"unexpected call: {path}")

        def tracking_graphql(query, variables=None):
            graphql_calls.append({"query": query, "variables": variables})
            return self._FakeResponse(
                {"data": {"repository": {"pullRequest": {"isInMergeQueue": True}}}}
            )

        provider._api = fake_api
        provider._graphql = tracking_graphql
        review = provider.get_review("x/y", "11")
        assert review.auto_merge_enabled is True
        assert graphql_calls == [], (
            "isInMergeQueue lookup must be skipped when auto_merge is "
            "already populated (it's already True)"
        )

    # ------------------------------------------------------------------
    # mergeable / mergeable_state DETAIL fetch (oompah-zlz_2-8rb).
    #
    # The /pulls?state=open LIST endpoint never populates ``mergeable``
    # or ``mergeable_state`` — those are only on per-PR DETAIL fetches.
    # Without a DETAIL call the list-payload parser silently produces
    # has_conflicts=False / needs_rebase=False for every PR, even when
    # GitHub considers the PR DIRTY. The fix is a per-PR DETAIL fetch
    # for non-draft PRs that aren't already auto-merging or queued.
    # ------------------------------------------------------------------

    def _list_endpoint_payload(self, **detail_overrides):
        """Build a list-endpoint payload that mirrors GitHub's behavior:
        ``mergeable``/``mergeable_state`` are stripped entirely (they
        only exist on the DETAIL endpoint).
        """
        # Detail-endpoint payload defines the *real* state.
        detail = self._pr_payload(**detail_overrides)
        # List-endpoint copy: same fields minus the absent ones.
        list_pr = {k: v for k, v in detail.items()
                   if k not in ("mergeable", "mergeable_state")}
        return list_pr, detail

    def _provider_with_distinct_list_and_detail(
        self, list_pr, detail_pr, merge_queue_prs=()
    ):
        """A provider whose LIST endpoint returns a payload missing
        mergeable/mergeable_state (matching real GitHub behavior) and
        whose per-PR DETAIL endpoint returns the full payload.
        """
        provider = GitHubProvider(access_token="t")
        detail_calls: list[str] = []

        def fake_api(method, path, **kwargs):
            if path.endswith("/pulls"):
                return self._FakeResponse([list_pr])
            if "/pulls/" in path and "/status" not in path and "/check-runs" not in path:
                detail_calls.append(path)
                return self._FakeResponse(detail_pr)
            if path.endswith("/status"):
                return self._FakeResponse({"state": "success", "total_count": 1})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": []})
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api

        list_nodes = [
            {"pullRequest": {"number": int(n)}} for n in merge_queue_prs
        ]
        list_payload_gql = {
            "data": {
                "repository": {
                    "mergeQueue": (
                        {"entries": {"nodes": list_nodes}}
                        if list_nodes else None
                    )
                }
            }
        }
        provider._graphql = lambda q, v=None: self._FakeResponse(list_payload_gql)
        return provider, detail_calls

    def test_list_open_reviews_detects_dirty_via_detail_fetch(self):
        """The whole point of oompah-zlz_2-8rb: a DIRTY PR must report
        has_conflicts=True so the YOLO loop dispatches a conflict agent.
        The list endpoint omits mergeable/mergeable_state, so this can
        only come from a per-PR DETAIL fetch."""
        list_pr, detail_pr = self._list_endpoint_payload(
            number=16, auto_merge=None, mergeable=False,
            mergeable_state="dirty",
        )
        provider, detail_calls = self._provider_with_distinct_list_and_detail(
            list_pr, detail_pr,
        )
        reviews = provider.list_open_reviews("x/y")
        assert len(reviews) == 1
        review = reviews[0]
        assert review.has_conflicts is True
        assert review.needs_rebase is True
        assert review.mergeable_state == "dirty"
        assert detail_calls, (
            "list_open_reviews must fetch per-PR detail to learn "
            "mergeable/mergeable_state when LIST endpoint omits them"
        )

    def test_list_open_reviews_detects_behind_via_detail_fetch(self):
        """A clean-but-behind PR must report needs_rebase=True even
        though has_conflicts is False — this drives the rebase path."""
        list_pr, detail_pr = self._list_endpoint_payload(
            number=17, auto_merge=None, mergeable=True,
            mergeable_state="behind",
        )
        provider, _ = self._provider_with_distinct_list_and_detail(
            list_pr, detail_pr,
        )
        reviews = provider.list_open_reviews("x/y")
        assert len(reviews) == 1
        assert reviews[0].has_conflicts is False
        assert reviews[0].needs_rebase is True
        assert reviews[0].mergeable_state == "behind"

    def test_list_open_reviews_clean_pr_via_detail_fetch(self):
        """A clean PR must report has_conflicts=False / needs_rebase=False."""
        list_pr, detail_pr = self._list_endpoint_payload(
            number=18, auto_merge=None, mergeable=True,
            mergeable_state="clean",
        )
        provider, _ = self._provider_with_distinct_list_and_detail(
            list_pr, detail_pr,
        )
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].has_conflicts is False
        assert reviews[0].needs_rebase is False
        assert reviews[0].mergeable_state == "clean"

    def test_list_open_reviews_skips_detail_fetch_for_drafts(self):
        """Draft PRs are never YOLO-targets, so detail-fetch is a waste
        of an API call. Verify we skip it."""
        list_pr, detail_pr = self._list_endpoint_payload(
            number=19, auto_merge=None, mergeable=False,
            mergeable_state="dirty", draft=True,
        )
        provider, detail_calls = self._provider_with_distinct_list_and_detail(
            list_pr, detail_pr,
        )
        reviews = provider.list_open_reviews("x/y")
        assert len(reviews) == 1
        assert reviews[0].draft is True
        # Drafts skip the detail call: has_conflicts stays at the LIST
        # default (False) because we didn't bother asking GitHub.
        assert reviews[0].has_conflicts is False
        assert detail_calls == [], (
            "draft PRs must not trigger an extra DETAIL fetch — they're "
            "never auto-merged so their mergeable state is irrelevant"
        )

    def test_list_open_reviews_detail_fetch_for_auto_merge(self):
        """Auto-merge enabled PRs MUST still get DETAIL-fetched: a PR
        that's enqueued for auto-merge can go DIRTY when another PR
        lands first with overlapping files. GitHub will then sit
        forever waiting for manual conflict resolution. Without the
        detail fetch, has_conflicts stays False and the YOLO loop
        never dispatches a merge-conflict agent. (oompah-zlz_2-l81,
        regression of oompah-zlz_2-8rb)"""
        list_pr, detail_pr = self._list_endpoint_payload(
            number=20,
            auto_merge={"enabled_by": {"login": "bob"}},
            mergeable=True, mergeable_state="clean",
        )
        provider, detail_calls = self._provider_with_distinct_list_and_detail(
            list_pr, detail_pr,
        )
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].auto_merge_enabled is True
        assert detail_calls, (
            "auto-merge-enabled PRs must trigger a DETAIL fetch so "
            "we detect post-enqueue DIRTY state (oompah-zlz_2-l81)"
        )
        # Detail returned clean → has_conflicts stays False.
        assert reviews[0].has_conflicts is False
        assert reviews[0].mergeable_state == "clean"

    def test_list_open_reviews_detail_fetch_for_merge_queued(self):
        """A PR in the merge queue must also get DETAIL-fetched. Same
        rationale as auto-merge: an enqueued PR can go DIRTY after
        another PR lands, and the queue then waits indefinitely.
        (oompah-zlz_2-l81)"""
        list_pr, detail_pr = self._list_endpoint_payload(
            number=21, auto_merge=None,
            mergeable=False, mergeable_state="dirty",
        )
        provider, detail_calls = self._provider_with_distinct_list_and_detail(
            list_pr, detail_pr, merge_queue_prs=[21],
        )
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].auto_merge_enabled is True
        assert detail_calls, (
            "merge-queued PRs must trigger a DETAIL fetch so we "
            "detect post-enqueue DIRTY state (oompah-zlz_2-l81)"
        )
        # Detail returned dirty → has_conflicts must be True so the
        # YOLO loop files a merge-conflict task.
        assert reviews[0].has_conflicts is True
        assert reviews[0].mergeable_state == "dirty"

    def test_list_open_reviews_auto_merge_dirty_after_enqueue(self):
        """The exact trickle PR #16 scenario: a PR was enqueued for
        auto-merge, then another PR landed first with overlapping
        files. mergeable=CONFLICTING / mergeStateStatus=DIRTY,
        autoMerge still on. oompah must detect has_conflicts=True so
        the existing _yolo_notify_conflict pipeline files a P0
        merge-conflict task. (oompah-zlz_2-l81)"""
        list_pr, detail_pr = self._list_endpoint_payload(
            number=16,
            auto_merge={"enabled_by": {"login": "bob"},
                        "merge_method": "MERGE"},
            mergeable=False, mergeable_state="dirty",
        )
        provider, detail_calls = self._provider_with_distinct_list_and_detail(
            list_pr, detail_pr,
        )
        reviews = provider.list_open_reviews("x/y")
        assert len(reviews) == 1
        review = reviews[0]
        assert review.auto_merge_enabled is True, (
            "auto-merge stays on while the PR sits stuck in the queue"
        )
        assert review.has_conflicts is True, (
            "DIRTY auto-merge PR must report has_conflicts=True so "
            "_yolo_notify_conflict fires and files a merge-conflict task"
        )
        assert review.needs_rebase is True
        assert review.mergeable_state == "dirty"
        assert detail_calls, (
            "the fix is gated on this DETAIL call happening for "
            "auto-merge PRs — without it has_conflicts stays False"
        )

    def test_list_open_reviews_detail_http_error_falls_back_safely(self):
        """A failed DETAIL fetch must not blow up list_open_reviews —
        we keep the list-payload defaults (has_conflicts=False) and
        carry on."""
        list_pr, _ = self._list_endpoint_payload(
            number=22, auto_merge=None, mergeable=False,
            mergeable_state="dirty",
        )
        provider = GitHubProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if path.endswith("/pulls"):
                return self._FakeResponse([list_pr])
            if "/pulls/" in path and "/status" not in path and "/check-runs" not in path:
                return self._FakeResponse({}, status_code=500)
            if path.endswith("/status"):
                return self._FakeResponse({"state": "success", "total_count": 1})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": []})
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api
        provider._graphql = lambda q, v=None: self._FakeResponse(
            {"data": {"repository": {"mergeQueue": None}}}
        )
        reviews = provider.list_open_reviews("x/y")
        # No crash; falls back to LIST defaults — has_conflicts stays
        # False. The orchestrator polls again next tick so we'll
        # eventually catch the conflict.
        assert len(reviews) == 1
        assert reviews[0].has_conflicts is False

    def test_list_open_reviews_detail_mergeable_none_keeps_default(self):
        """If GitHub hasn't computed mergeable yet (returns None on
        DETAIL too), don't flap has_conflicts to True. ``None`` is not
        a conflict — it's 'still computing'."""
        list_pr, detail_pr = self._list_endpoint_payload(
            number=23, auto_merge=None, mergeable=None,
            mergeable_state="unknown",
        )
        provider, _ = self._provider_with_distinct_list_and_detail(
            list_pr, detail_pr,
        )
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].has_conflicts is False
        assert reviews[0].needs_rebase is False
        assert reviews[0].mergeable_state == "unknown"

    def test_list_open_reviews_detail_fetch_per_pr(self):
        """Multi-PR list: each non-draft PR gets its own DETAIL fetch
        (auto-merging PRs are NOT skipped since post-enqueue DIRTY
        must be detected — oompah-zlz_2-l81)."""
        list_pr_a, detail_pr_a = self._list_endpoint_payload(
            number=24, auto_merge=None, mergeable=False,
            mergeable_state="dirty",
        )
        list_pr_b, detail_pr_b = self._list_endpoint_payload(
            number=25, auto_merge=None, mergeable=True,
            mergeable_state="clean",
        )
        provider = GitHubProvider(access_token="t")
        detail_calls: list[str] = []

        details_by_num = {"24": detail_pr_a, "25": detail_pr_b}

        def fake_api(method, path, **kwargs):
            if path.endswith("/pulls"):
                return self._FakeResponse([list_pr_a, list_pr_b])
            if "/pulls/" in path and "/status" not in path and "/check-runs" not in path:
                detail_calls.append(path)
                pr_num = path.rsplit("/", 1)[-1]
                return self._FakeResponse(details_by_num.get(pr_num, {}))
            if path.endswith("/status"):
                return self._FakeResponse({"state": "success", "total_count": 1})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": []})
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api
        provider._graphql = lambda q, v=None: self._FakeResponse(
            {"data": {"repository": {"mergeQueue": None}}}
        )
        reviews = provider.list_open_reviews("x/y")
        by_id = {r.id: r for r in reviews}
        assert by_id["24"].has_conflicts is True
        assert by_id["25"].has_conflicts is False
        assert len(detail_calls) == 2, (
            "each non-draft PR must trigger one DETAIL fetch"
        )


class TestGitHubPRDetailCache:
    """Per-PR DETAIL fetch result cache (oompah-zlz_2-aza).

    The 8rb fix adds a per-PR DETAIL fetch on every review_check tick
    so the YOLO loop sees real has_conflicts/mergeable_state. Without
    caching, this re-fetches identical state every poll cycle and can
    push a single review_check tick to 60+ seconds. The cache keyed on
    (repo, pr_num) → (head_sha, updated_at, mergeable, mergeable_state)
    means steady-state ticks make zero DETAIL calls; first tick after
    a PR push pays one DETAIL fetch (cache miss because head_sha or
    updated_at changed).
    """

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    def _pr_payload(self, **overrides):
        base = {
            "number": 11,
            "title": "Test PR",
            "html_url": "https://github.com/x/y/pull/11",
            "user": {"login": "alice"},
            "head": {"ref": "feat", "sha": "deadbeef"},
            "base": {"ref": "main"},
            "created_at": "2026-05-01T00:00:00Z",
            "updated_at": "2026-05-01T00:00:00Z",
            "body": "",
            "labels": [],
            "draft": False,
            "additions": 1,
            "deletions": 0,
            "mergeable": True,
            "mergeable_state": "clean",
            "auto_merge": None,
        }
        base.update(overrides)
        return base

    def _make_provider(self, pr_payloads_by_num, detail_calls):
        """Build a provider whose LIST endpoint returns the given PRs and
        whose DETAIL endpoint returns the same PR by number, recording
        every DETAIL call into ``detail_calls``.

        Re-evaluates ``pr_payloads_by_num`` on every call so tests can
        mutate the dict between ticks to simulate state changes.
        """
        provider = GitHubProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if path.endswith("/pulls"):
                # Re-snapshot the PR list on every call so test mutations
                # to ``pr_payloads_by_num`` between ticks propagate.
                # GitHub's LIST endpoint omits mergeable/mergeable_state,
                # so we strip those fields from the LIST view to match
                # real-world behavior.
                list_view = []
                for pr in pr_payloads_by_num.values():
                    list_view.append({
                        k: v for k, v in pr.items()
                        if k not in ("mergeable", "mergeable_state")
                    })
                return self._FakeResponse(list_view)
            if "/pulls/" in path and "/status" not in path and "/check-runs" not in path:
                detail_calls.append(path)
                pr_num = path.rsplit("/", 1)[-1]
                return self._FakeResponse(pr_payloads_by_num[pr_num])
            if path.endswith("/status"):
                return self._FakeResponse({"state": "success", "total_count": 1})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": []})
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api
        provider._graphql = lambda q, v=None: self._FakeResponse(
            {"data": {"repository": {"mergeQueue": None}}}
        )
        return provider

    def setup_method(self):
        # Class-level cache must be cleared between tests so they don't
        # cross-pollute. Production code does NOT need to do this — the
        # cache is meant to persist across review_check ticks.
        GitHubProvider._pr_detail_cache.clear()

    def test_steady_state_zero_detail_fetches_on_repeated_tick(self):
        """First tick fetches DETAIL once; subsequent ticks with no
        change to head_sha or updated_at fetch zero times."""
        pr = self._pr_payload(number=11, mergeable=True,
                              mergeable_state="clean")
        detail_calls: list[str] = []
        provider = self._make_provider({"11": pr}, detail_calls)

        # First tick — cache miss.
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].mergeable_state == "clean"
        assert len(detail_calls) == 1, (
            "first tick must DETAIL-fetch (cache miss)"
        )

        # Second tick with identical PR state — cache hit.
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].mergeable_state == "clean"
        assert len(detail_calls) == 1, (
            "second tick must NOT DETAIL-fetch (cache hit on same "
            "head_sha + updated_at)"
        )

        # Third tick — still cached.
        provider.list_open_reviews("x/y")
        assert len(detail_calls) == 1

    def test_cache_invalidated_on_head_sha_change(self):
        """A new commit on the PR branch changes head.sha → DETAIL
        re-fetch."""
        pr_v1 = self._pr_payload(
            number=11, head={"ref": "feat", "sha": "aaaa1111"},
            mergeable=True, mergeable_state="clean",
        )
        pr_v2 = self._pr_payload(
            number=11, head={"ref": "feat", "sha": "bbbb2222"},
            mergeable=True, mergeable_state="clean",
        )
        # Mutate the dict the provider returns between ticks.
        current = {"11": pr_v1}
        detail_calls: list[str] = []
        provider = self._make_provider(current, detail_calls)

        provider.list_open_reviews("x/y")
        assert len(detail_calls) == 1

        # Push a new commit → head.sha changes.
        current["11"] = pr_v2
        provider.list_open_reviews("x/y")
        assert len(detail_calls) == 2, (
            "head.sha change must invalidate cache and trigger DETAIL"
        )

    def test_cache_invalidated_on_updated_at_change(self):
        """A PR going DIRTY after another PR lands keeps head.sha
        unchanged but bumps updated_at — must re-fetch DETAIL so the
        YOLO loop sees the new mergeable_state. (Acceptance criterion:
        'a PR that goes DIRTY (head_sha unchanged, updated_at bump)
        still gets re-fetched'.)"""
        pr_clean = self._pr_payload(
            number=11, head={"ref": "feat", "sha": "deadbeef"},
            updated_at="2026-05-01T00:00:00Z",
            mergeable=True, mergeable_state="clean",
        )
        pr_dirty = self._pr_payload(
            number=11, head={"ref": "feat", "sha": "deadbeef"},
            updated_at="2026-05-01T00:05:00Z",
            mergeable=False, mergeable_state="dirty",
        )
        current = {"11": pr_clean}
        detail_calls: list[str] = []
        provider = self._make_provider(current, detail_calls)

        # Tick 1: clean.
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].has_conflicts is False
        assert len(detail_calls) == 1

        # Tick 2: same head.sha but updated_at bumped → re-fetch.
        current["11"] = pr_dirty
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].has_conflicts is True, (
            "DIRTY transition must propagate even when head_sha is "
            "unchanged — that's how post-enqueue conflicts surface"
        )
        assert reviews[0].mergeable_state == "dirty"
        assert len(detail_calls) == 2, (
            "updated_at change must invalidate cache"
        )

    def test_cache_stale_by_ttl_triggers_refetch(self):
        """A cache entry whose (head_sha, updated_at) still matches but
        whose ``entry_time`` is older than the TTL must trigger a
        DETAIL re-fetch on the next tick. (Acceptance criterion for
        oompah-zlz_2-1of: GitHub does NOT always bump ``updated_at``
        when async-recomputing mergeable_state after a base-branch
        commit, so the (head_sha, updated_at) key alone is not a
        reliable freshness signal.)"""
        pr = self._pr_payload(
            number=11, head={"ref": "feat", "sha": "deadbeef"},
            updated_at="2026-05-01T00:00:00Z",
            mergeable=True, mergeable_state="clean",
        )
        current = {"11": pr}
        detail_calls: list[str] = []
        provider = self._make_provider(current, detail_calls)

        # Tick 1 — populate cache.
        provider.list_open_reviews("x/y")
        assert len(detail_calls) == 1
        assert ("x/y", "11") in GitHubProvider._pr_detail_cache

        # Simulate the cache entry being older than the TTL by rewriting
        # its entry_time backwards. (We do this rather than monkeypatch
        # ``time.monotonic`` so the test is deterministic and fast.)
        ttl = GitHubProvider._PR_DETAIL_CACHE_TTL_SECONDS
        head_sha, updated_at, mergeable, state, _ = (
            GitHubProvider._pr_detail_cache[("x/y", "11")]
        )
        GitHubProvider._pr_detail_cache[("x/y", "11")] = (
            head_sha, updated_at, mergeable, state,
            time.monotonic() - (ttl + 1.0),
        )

        # Now flip the live PR state to DIRTY without bumping
        # head.sha or updated_at — exactly the case that motivates the
        # TTL fallback (GitHub recomputed mergeable async after another
        # PR landed on main).
        current["11"] = self._pr_payload(
            number=11, head={"ref": "feat", "sha": "deadbeef"},
            updated_at="2026-05-01T00:00:00Z",
            mergeable=False, mergeable_state="dirty",
        )

        # Tick 2 — cache must NOT be honored (stale by TTL) → refetch
        # detects the new DIRTY state.
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].has_conflicts is True, (
            "TTL-stale cache entry must be refetched and reflect the "
            "new DIRTY state — that's the whole point of the fallback"
        )
        assert reviews[0].mergeable_state == "dirty"
        assert len(detail_calls) == 2, (
            "TTL expiry must trigger a DETAIL re-fetch even when the "
            "(head_sha, updated_at) key matches"
        )

    def test_cache_fresh_within_ttl_still_hits(self):
        """A cache entry whose key matches AND whose ``entry_time`` is
        within the TTL window must still hit (no DETAIL fetch). This
        guards against accidentally over-invalidating and undoing the
        amortisation the cache exists for."""
        pr = self._pr_payload(
            number=11, head={"ref": "feat", "sha": "deadbeef"},
            updated_at="2026-05-01T00:00:00Z",
            mergeable=True, mergeable_state="clean",
        )
        current = {"11": pr}
        detail_calls: list[str] = []
        provider = self._make_provider(current, detail_calls)

        # Tick 1 — populate cache.
        provider.list_open_reviews("x/y")
        assert len(detail_calls) == 1

        # Tick 2 — same entry, well within the TTL — must be a hit.
        provider.list_open_reviews("x/y")
        assert len(detail_calls) == 1, (
            "fresh entry under TTL must NOT trigger a DETAIL fetch"
        )

    def test_cache_ttl_configurable_via_class_attribute(self):
        """``_PR_DETAIL_CACHE_TTL_SECONDS`` is a class attribute so
        operators can tune it via the OOMPAH_PR_DETAIL_CACHE_TTL_SECONDS
        env var (read at import time) and tests can override it
        in-process. Setting it to a tiny value forces every tick to
        re-fetch."""
        original_ttl = GitHubProvider._PR_DETAIL_CACHE_TTL_SECONDS
        try:
            GitHubProvider._PR_DETAIL_CACHE_TTL_SECONDS = 0.0001

            pr = self._pr_payload(
                number=11, mergeable=True, mergeable_state="clean",
            )
            detail_calls: list[str] = []
            provider = self._make_provider({"11": pr}, detail_calls)

            provider.list_open_reviews("x/y")
            assert len(detail_calls) == 1

            # Sleep slightly longer than the (tiny) TTL.
            time.sleep(0.005)

            provider.list_open_reviews("x/y")
            assert len(detail_calls) == 2, (
                "with a near-zero TTL every tick must re-fetch"
            )
        finally:
            GitHubProvider._PR_DETAIL_CACHE_TTL_SECONDS = original_ttl

    def test_cache_eviction_on_pr_close(self):
        """When a PR drops out of the LIST response (closed/merged),
        its cache entry must be evicted so closed-then-reopened PRs
        don't return stale state. Open PR for the same repo keeps its
        cache entry."""
        pr_a = self._pr_payload(number=11, mergeable=True,
                                mergeable_state="clean")
        pr_b = self._pr_payload(number=12, mergeable=True,
                                mergeable_state="clean")
        current = {"11": pr_a, "12": pr_b}
        detail_calls: list[str] = []
        provider = self._make_provider(current, detail_calls)

        # Tick 1: both PRs cached.
        provider.list_open_reviews("x/y")
        assert len(detail_calls) == 2
        assert ("x/y", "11") in GitHubProvider._pr_detail_cache
        assert ("x/y", "12") in GitHubProvider._pr_detail_cache

        # Tick 2: PR #11 closed → list returns only #12.
        del current["11"]
        provider.list_open_reviews("x/y")
        # #11 was evicted; #12 was a cache hit.
        assert ("x/y", "11") not in GitHubProvider._pr_detail_cache, (
            "closed PR must be evicted from cache"
        )
        assert ("x/y", "12") in GitHubProvider._pr_detail_cache, (
            "still-open PR must remain cached"
        )
        assert len(detail_calls) == 2, (
            "tick 2 must NOT DETAIL-fetch — only the eviction happens"
        )

    def test_cache_eviction_does_not_touch_other_repos(self):
        """list_open_reviews on repo A must not evict entries for repo
        B, even though B's PRs aren't in A's LIST response."""
        pr_a = self._pr_payload(number=11, mergeable=True,
                                mergeable_state="clean")
        pr_b = self._pr_payload(number=99, mergeable=True,
                                mergeable_state="clean")

        # Pre-populate cache with an entry from a different repo.
        # 5th tuple element is ``time.monotonic()`` for the TTL
        # fallback (oompah-zlz_2-1of).
        GitHubProvider._pr_detail_cache[("other/repo", "99")] = (
            "deadbeef", "2026-05-01T00:00:00Z", True, "clean",
            time.monotonic(),
        )

        detail_calls: list[str] = []
        provider = self._make_provider({"11": pr_a}, detail_calls)
        provider.list_open_reviews("x/y")

        # The unrelated cache entry for other/repo must NOT be evicted.
        assert ("other/repo", "99") in GitHubProvider._pr_detail_cache, (
            "eviction must be scoped per-repo — other repos untouched"
        )
        assert ("x/y", "11") in GitHubProvider._pr_detail_cache

    def test_cache_shared_across_provider_instances(self):
        """The orchestrator creates a fresh GitHubProvider on every
        review_check tick (see _fetch_all_reviews). The cache MUST
        therefore be class-level, not per-instance, or it would always
        be empty on the next tick.
        """
        pr = self._pr_payload(number=11, mergeable=True,
                              mergeable_state="clean")
        # Two provider instances representing two consecutive ticks.
        detail_calls: list[str] = []
        provider_tick1 = self._make_provider({"11": pr}, detail_calls)
        provider_tick2 = self._make_provider({"11": pr}, detail_calls)

        provider_tick1.list_open_reviews("x/y")
        assert len(detail_calls) == 1

        # Different instance, same data — cache must hit.
        provider_tick2.list_open_reviews("x/y")
        assert len(detail_calls) == 1, (
            "cache must be shared across instances (orchestrator "
            "creates a fresh GitHubProvider every tick)"
        )

    def test_cache_miss_when_detail_fetch_failed(self):
        """A failed DETAIL fetch must NOT pin a stale value in the
        cache — the next tick must retry. (Otherwise we'd have
        has_conflicts=False stuck until the PR is pushed again.)"""
        list_pr = {
            "number": 11,
            "title": "Test",
            "html_url": "https://github.com/x/y/pull/11",
            "user": {"login": "alice"},
            "head": {"ref": "feat", "sha": "deadbeef"},
            "base": {"ref": "main"},
            "created_at": "2026-05-01T00:00:00Z",
            "updated_at": "2026-05-01T00:00:00Z",
            "body": "",
            "labels": [],
            "draft": False,
            "additions": 0,
            "deletions": 0,
            "auto_merge": None,
        }
        detail_calls: list[str] = []
        provider = GitHubProvider(access_token="t")
        # First call fails (HTTP 500), second call succeeds.
        responses = [
            self._FakeResponse({}, status_code=500),
            self._FakeResponse(self._pr_payload(
                number=11, mergeable=False, mergeable_state="dirty",
            )),
        ]

        def fake_api(method, path, **kwargs):
            if path.endswith("/pulls"):
                return self._FakeResponse([list_pr])
            if "/pulls/" in path and "/status" not in path and "/check-runs" not in path:
                detail_calls.append(path)
                return responses[len(detail_calls) - 1]
            if path.endswith("/status"):
                return self._FakeResponse({"state": "success", "total_count": 1})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": []})
            raise AssertionError(f"unexpected call: {path}")

        provider._api = fake_api
        provider._graphql = lambda q, v=None: self._FakeResponse(
            {"data": {"repository": {"mergeQueue": None}}}
        )

        # Tick 1: DETAIL fetch fails → no cache entry written.
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].has_conflicts is False  # falls back to LIST default
        assert ("x/y", "11") not in GitHubProvider._pr_detail_cache, (
            "failed DETAIL fetch must NOT populate cache"
        )

        # Tick 2: retry succeeds → conflict detected, cache populated.
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].has_conflicts is True
        assert ("x/y", "11") in GitHubProvider._pr_detail_cache
        assert len(detail_calls) == 2, (
            "next tick after a failed fetch must retry DETAIL"
        )

    def test_drafts_never_cached_or_fetched(self):
        """Draft PRs skip DETAIL entirely — must not pollute the cache
        either."""
        pr = self._pr_payload(number=11, draft=True,
                              mergeable=False, mergeable_state="dirty")
        detail_calls: list[str] = []
        provider = self._make_provider({"11": pr}, detail_calls)

        provider.list_open_reviews("x/y")
        assert detail_calls == []
        assert ("x/y", "11") not in GitHubProvider._pr_detail_cache, (
            "draft PRs must not populate cache"
        )

        # Even on a second tick, no fetch and no cache entry.
        provider.list_open_reviews("x/y")
        assert detail_calls == []


# ---------------------------------------------------------------------------
# get_all_open_reviews — payload shape, including project_yolo
# (oompah-zlz_2-zvf2)
# ---------------------------------------------------------------------------


class TestGetAllOpenReviews:
    """``get_all_open_reviews`` flattens every project's open PRs/MRs
    into a list of ``{project_id, project_name, project_yolo, provider,
    review}`` dicts. The ``project_yolo`` field is consumed by the
    /reviews UI to hide the manual 'Resolve Conflicts' button on
    YOLO-enabled projects (oompah-zlz_2-zvf2)."""

    def _make_project(self, *, project_id="proj-1", name="repo",
                      yolo=False, repo_url="https://github.com/o/r"):
        proj = mock.MagicMock()
        proj.id = project_id
        proj.name = name
        proj.yolo = yolo
        proj.repo_url = repo_url
        proj.access_token = None
        return proj

    def _make_review(self, review_id="42"):
        return ReviewRequest(
            id=review_id, title="Fix", url=f"https://x/{review_id}",
            author="alice", state="open", source_branch=f"b-{review_id}",
            target_branch="main", created_at="", updated_at="",
        )

    def test_payload_includes_project_yolo_true(self):
        """A project with yolo=True surfaces project_yolo=True on every
        review item — the template uses this to swap the
        'Resolve Conflicts' button for 'Auto-resolving…'."""
        from oompah.scm import get_all_open_reviews

        project = self._make_project(yolo=True)
        provider = mock.MagicMock()
        provider.provider_name.return_value = "github"
        provider.list_open_reviews.return_value = [self._make_review("42")]

        with (
            mock.patch("oompah.scm.detect_provider", return_value=provider),
            mock.patch("oompah.scm.extract_repo_slug", return_value="o/r"),
        ):
            results = get_all_open_reviews([project])

        assert len(results) == 1
        assert results[0]["project_yolo"] is True
        assert results[0]["project_id"] == "proj-1"
        assert results[0]["provider"] == "github"
        assert results[0]["review"]["id"] == "42"

    def test_payload_includes_project_yolo_false(self):
        """A project with yolo=False surfaces project_yolo=False so the
        template renders the manual 'Resolve Conflicts' button."""
        from oompah.scm import get_all_open_reviews

        project = self._make_project(yolo=False)
        provider = mock.MagicMock()
        provider.provider_name.return_value = "github"
        provider.list_open_reviews.return_value = [self._make_review("42")]

        with (
            mock.patch("oompah.scm.detect_provider", return_value=provider),
            mock.patch("oompah.scm.extract_repo_slug", return_value="o/r"),
        ):
            results = get_all_open_reviews([project])

        assert len(results) == 1
        assert results[0]["project_yolo"] is False

    def test_payload_yolo_missing_defaults_false(self):
        """If a Project somehow lacks the ``yolo`` attribute, the
        result must still include ``project_yolo`` and default to False
        — never raise AttributeError."""
        from oompah.scm import get_all_open_reviews

        project = mock.MagicMock(spec=["id", "name", "repo_url",
                                       "access_token"])
        project.id = "p"
        project.name = "n"
        project.repo_url = "https://github.com/o/r"
        project.access_token = None
        provider = mock.MagicMock()
        provider.provider_name.return_value = "github"
        provider.list_open_reviews.return_value = [self._make_review("1")]

        with (
            mock.patch("oompah.scm.detect_provider", return_value=provider),
            mock.patch("oompah.scm.extract_repo_slug", return_value="o/r"),
        ):
            results = get_all_open_reviews([project])

        assert len(results) == 1
        assert results[0]["project_yolo"] is False

    def test_project_yolo_set_per_project_in_mixed_list(self):
        """When list_all() returns projects with different yolo settings,
        each project's reviews carry the per-project value (no leakage
        across projects)."""
        from oompah.scm import get_all_open_reviews

        yolo_proj = self._make_project(project_id="p-yolo",
                                        name="yolo-proj", yolo=True,
                                        repo_url="https://github.com/o/y")
        manual_proj = self._make_project(project_id="p-manual",
                                          name="manual-proj", yolo=False,
                                          repo_url="https://github.com/o/m")

        def fake_provider(repo_url, **_kwargs):
            p = mock.MagicMock()
            p.provider_name.return_value = "github"
            review_id = "y1" if "/y" in repo_url else "m1"
            p.list_open_reviews.return_value = [self._make_review(review_id)]
            return p

        with (
            mock.patch("oompah.scm.detect_provider", side_effect=fake_provider),
            mock.patch("oompah.scm.extract_repo_slug",
                       side_effect=lambda url: url.rsplit("/", 2)[-2] + "/"
                                + url.rsplit("/", 1)[-1]),
        ):
            results = get_all_open_reviews([yolo_proj, manual_proj])

        by_id = {r["project_id"]: r for r in results}
        assert by_id["p-yolo"]["project_yolo"] is True
        assert by_id["p-manual"]["project_yolo"] is False


class TestListMergedReviewsGitHub:
    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    def _provider(self, payload, status_code=200):
        provider = GitHubProvider(access_token="t")
        captured: dict = {}

        def fake_api(method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["params"] = kwargs.get("params")
            return self._FakeResponse(payload, status_code=status_code)

        provider._api = fake_api
        provider._captured = captured  # type: ignore[attr-defined]
        return provider

    def test_returns_recent_merged_reviews_with_targets(self):
        payload = [
            {
                "number": 42,
                "title": "Epic landing",
                "html_url": "https://github.com/owner/repo/pull/42",
                "user": {"login": "alice"},
                "state": "closed",
                "merged_at": "2026-01-01T00:00:00Z",
                "head": {"ref": "epic-COROOT-4"},
                "base": {"ref": "main"},
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
                "body": "body",
                "labels": [{"name": "type:epic"}],
                "draft": False,
            },
            {
                "number": 43,
                "merged_at": None,
                "head": {"ref": "closed-unmerged"},
                "base": {"ref": "main"},
            },
        ]
        provider = self._provider(payload)

        reviews = provider.list_merged_reviews("owner/repo")

        assert [review.source_branch for review in reviews] == ["epic-COROOT-4"]
        assert reviews[0].target_branch == "main"
        assert reviews[0].state == "merged"
        assert provider._captured["params"]["state"] == "closed"

    def test_branch_wrapper_uses_target_aware_reviews(self):
        provider = GitHubProvider(access_token="t")
        provider.list_merged_reviews = mock.MagicMock(
            return_value=[
                ReviewRequest(
                    id="1",
                    title="x",
                    url="u",
                    author="a",
                    state="merged",
                    source_branch="feature",
                    target_branch="main",
                    created_at="",
                    updated_at="",
                )
            ]
        )

        assert provider.list_merged_branches("owner/repo") == {"feature"}


class TestListMergedReviewsGitLab:
    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    def _provider(self, payload, status_code=200):
        provider = GitLabProvider(
            hostname="gitlab.example.com",
            access_token="t",
        )
        captured: dict = {}

        def fake_api(method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["params"] = kwargs.get("params")
            return self._FakeResponse(payload, status_code=status_code)

        provider._api = fake_api
        provider._captured = captured  # type: ignore[attr-defined]
        return provider

    def test_returns_recent_merged_reviews_with_targets(self):
        payload = [{
            "iid": 12,
            "title": "Epic landing",
            "web_url": "https://gitlab/group/proj/-/merge_requests/12",
            "author": {"username": "alice"},
            "state": "merged",
            "source_branch": "epic-COROOT-4",
            "target_branch": "main",
            "created_at": "",
            "updated_at": "",
            "description": "body",
            "labels": ["type:epic"],
            "draft": False,
        }]
        provider = self._provider(payload)

        reviews = provider.list_merged_reviews("group/proj")

        assert [review.source_branch for review in reviews] == ["epic-COROOT-4"]
        assert reviews[0].target_branch == "main"
        assert reviews[0].state == "merged"
        assert provider._captured["params"]["state"] == "merged"


class TestFindPrForBranchGitHub:
    """``GitHubProvider.find_pr_for_branch`` filters PRs by head ref and
    returns the most recent record, normalising ``state`` to one of
    ``open``/``closed``/``merged``."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    def _provider(self, payload, status_code=200):
        provider = GitHubProvider(access_token="t")

        captured: dict = {}

        def fake_api(method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["params"] = kwargs.get("params")
            return self._FakeResponse(payload, status_code=status_code)

        provider._api = fake_api
        provider._captured = captured  # type: ignore[attr-defined]
        return provider

    def test_returns_none_for_empty_branch(self):
        provider = GitHubProvider(access_token="t")
        # _api should NOT be invoked when branch is empty.
        provider._api = mock.MagicMock(
            side_effect=AssertionError("should not call API"),
        )
        assert provider.find_pr_for_branch("owner/repo", "") is None

    def test_returns_none_when_no_prs(self):
        provider = self._provider([])
        assert provider.find_pr_for_branch("owner/repo", "feat-x") is None
        # ``head`` param must be ``owner:branch``.
        assert provider._captured["params"]["head"] == "owner:feat-x"
        assert provider._captured["params"]["state"] == "all"

    def test_returns_merged_state_when_merged_at_set(self):
        payload = [{
            "number": 42,
            "title": "Feat X",
            "html_url": "https://github.com/owner/repo/pull/42",
            "user": {"login": "alice"},
            "state": "closed",
            "merged_at": "2026-01-01T00:00:00Z",
            "head": {"ref": "feat-x"},
            "base": {"ref": "main"},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "body": "Closes oompah-zlz_2-foo.",
            "labels": [{"name": "feature"}],
            "draft": False,
        }]
        provider = self._provider(payload)
        review = provider.find_pr_for_branch("owner/repo", "feat-x")
        assert review is not None
        assert review.id == "42"
        assert review.state == "merged"
        assert review.source_branch == "feat-x"
        assert review.target_branch == "main"
        assert review.author == "alice"

    def test_returns_closed_state_for_closed_unmerged(self):
        payload = [{
            "number": 7,
            "title": "Failed",
            "html_url": "u",
            "user": {"login": "bob"},
            "state": "closed",
            "merged_at": None,
            "head": {"ref": "feat-7"},
            "base": {"ref": "main"},
            "created_at": "", "updated_at": "",
            "body": "", "labels": [], "draft": False,
        }]
        provider = self._provider(payload)
        review = provider.find_pr_for_branch("owner/repo", "feat-7")
        assert review is not None
        assert review.state == "closed"

    def test_returns_open_state_for_open_pr(self):
        payload = [{
            "number": 9,
            "title": "WIP",
            "html_url": "u",
            "user": {"login": "carol"},
            "state": "open",
            "merged_at": None,
            "head": {"ref": "feat-9"},
            "base": {"ref": "main"},
            "created_at": "", "updated_at": "",
            "body": "", "labels": [], "draft": False,
        }]
        provider = self._provider(payload)
        review = provider.find_pr_for_branch("owner/repo", "feat-9")
        assert review is not None
        assert review.state == "open"

    def test_returns_none_on_http_error(self):
        provider = self._provider({}, status_code=500)
        assert provider.find_pr_for_branch("owner/repo", "feat-x") is None

    def test_returns_none_on_exception(self):
        provider = GitHubProvider(access_token="t")
        import httpx
        provider._api = mock.MagicMock(side_effect=httpx.HTTPError("boom"))
        assert provider.find_pr_for_branch("owner/repo", "feat-x") is None


class TestFindPrForBranchGitLab:
    """``GitLabProvider.find_pr_for_branch`` filters MRs by source_branch."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

    def _provider(self, payload, status_code=200):
        provider = GitLabProvider(
            hostname="gitlab.example.com",
            access_token="t",
        )
        captured: dict = {}

        def fake_api(method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["params"] = kwargs.get("params")
            return self._FakeResponse(payload, status_code=status_code)

        provider._api = fake_api
        provider._captured = captured  # type: ignore[attr-defined]
        return provider

    def test_returns_none_for_empty_branch(self):
        provider = GitLabProvider(
            hostname="gitlab.example.com",
            access_token="t",
        )
        provider._api = mock.MagicMock(
            side_effect=AssertionError("should not call API"),
        )
        assert provider.find_pr_for_branch("group/proj", "") is None

    def test_returns_merged_state(self):
        payload = [{
            "iid": 123,
            "title": "Merge me",
            "web_url": "https://gitlab/example/-/merge_requests/123",
            "author": {"username": "dave"},
            "state": "merged",
            "source_branch": "feat-z",
            "target_branch": "main",
            "created_at": "",
            "updated_at": "",
            "description": "body",
            "labels": ["feature"],
            "draft": False,
        }]
        provider = self._provider(payload)
        review = provider.find_pr_for_branch("group/proj", "feat-z")
        assert review is not None
        assert review.id == "123"
        assert review.state == "merged"
        assert review.source_branch == "feat-z"
        assert review.target_branch == "main"

    def test_returns_closed_state(self):
        payload = [{
            "iid": 124, "title": "x", "web_url": "u",
            "author": {"username": "e"}, "state": "closed",
            "source_branch": "f", "target_branch": "main",
            "created_at": "", "updated_at": "", "description": "",
            "labels": [], "draft": False,
        }]
        provider = self._provider(payload)
        review = provider.find_pr_for_branch("group/proj", "f")
        assert review is not None
        assert review.state == "closed"

    def test_returns_open_state(self):
        payload = [{
            "iid": 125, "title": "x", "web_url": "u",
            "author": {"username": "e"}, "state": "opened",
            "source_branch": "g", "target_branch": "main",
            "created_at": "", "updated_at": "", "description": "",
            "labels": [], "draft": False,
        }]
        provider = self._provider(payload)
        review = provider.find_pr_for_branch("group/proj", "g")
        assert review is not None
        assert review.state == "open"

    def test_returns_none_when_no_mrs(self):
        provider = self._provider([])
        assert provider.find_pr_for_branch("group/proj", "missing") is None
        assert provider._captured["params"]["source_branch"] == "missing"
        assert provider._captured["params"]["state"] == "all"

    def test_returns_none_on_http_error(self):
        provider = self._provider({}, status_code=403)
        assert provider.find_pr_for_branch("group/proj", "b") is None


# ---------------------------------------------------------------------------
# get_review_files — GitHub (REST /pulls/{n}/files)
# ---------------------------------------------------------------------------


class TestGitHubGetReviewFiles:
    """GitHubProvider.get_review_files hits /repos/{repo}/pulls/{n}/files
    and extracts the ``filename`` field from each entry."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

        @property
        def text(self):
            return str(self._payload)

    def test_returns_filenames(self):
        provider = GitHubProvider(access_token="t")
        files_payload = [
            {"filename": "src/main.py", "additions": 5, "deletions": 1},
            {"filename": "README.md", "additions": 2, "deletions": 0},
            {"filename": "tests/test_main.py", "additions": 30, "deletions": 0},
        ]
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse(files_payload),
        )
        result = provider.get_review_files("org/repo", "42")
        assert result == ["src/main.py", "README.md", "tests/test_main.py"]
        provider._api.assert_called_once()
        call_args = provider._api.call_args
        assert call_args[0] == ("GET", "/repos/org/repo/pulls/42/files")

    def test_empty_files(self):
        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse([]),
        )
        result = provider.get_review_files("org/repo", "1")
        assert result == []

    def test_filters_empty_filename(self):
        provider = GitHubProvider(access_token="t")
        files_payload = [
            {"filename": "a.py", "additions": 1, "deletions": 0},
            {"filename": "", "additions": 0, "deletions": 0},
            {"filename": "b.py", "additions": 2, "deletions": 1},
        ]
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse(files_payload),
        )
        result = provider.get_review_files("org/repo", "5")
        assert result == ["a.py", "b.py"]

    def test_filters_missing_filename(self):
        provider = GitHubProvider(access_token="t")
        files_payload = [
            {"additions": 1, "deletions": 0},
            {"filename": "real.py", "additions": 2, "deletions": 0},
        ]
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse(files_payload),
        )
        result = provider.get_review_files("org/repo", "7")
        assert result == ["real.py"]

    def test_http_error_returns_empty(self):
        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse({}, status_code=404),
        )
        result = provider.get_review_files("org/repo", "999")
        assert result == []

    def test_network_error_returns_empty(self):
        import httpx

        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(side_effect=httpx.HTTPError("dns fail"))
        result = provider.get_review_files("org/repo", "1")
        assert result == []


# ---------------------------------------------------------------------------
# add_review_label — GitHub (REST /issues/{n}/labels)
# ---------------------------------------------------------------------------


class TestGitHubAddReviewLabel:
    """GitHubProvider.add_review_label POSTs to /issues/{n}/labels."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

        @property
        def text(self):
            return str(self._payload)

    def test_adds_label(self):
        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse([], status_code=200),
        )
        provider.add_review_label("org/repo", "42", "churn-magnet")
        provider._api.assert_called_once()
        args = provider._api.call_args
        assert args[0] == ("POST", "/repos/org/repo/issues/42/labels")
        assert args[1]["json"] == {"labels": ["churn-magnet"]}

    def test_adds_label_returns_none(self):
        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse([], status_code=201),
        )
        result = provider.add_review_label("org/repo", "10", "feature")
        assert result is None

    def test_http_error_logged_no_crash(self):
        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse({"message": "forbidden"}, status_code=403),
        )
        # Should not raise
        provider.add_review_label("org/repo", "10", "label")

    def test_network_error_no_crash(self):
        import httpx

        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(side_effect=httpx.HTTPError("boom"))
        provider.add_review_label("org/repo", "10", "label")


# ---------------------------------------------------------------------------
# remove_review_label — GitHub (REST DELETE /issues/{n}/labels/{name})
# ---------------------------------------------------------------------------


class TestGitHubRemoveReviewLabel:
    """GitHubProvider.remove_review_label DELETEs /issues/{n}/labels/{name}."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

        @property
        def text(self):
            return str(self._payload)

    def test_removes_label(self):
        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse({}, status_code=200),
        )
        provider.remove_review_label("org/repo", "42", "churn-magnet")
        provider._api.assert_called_once()
        args = provider._api.call_args
        assert "DELETE" == args[0][0]
        assert args[0][1] == "/repos/org/repo/issues/42/labels/churn-magnet"

    def test_label_url_encoded(self):
        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse({}, status_code=200),
        )
        provider.remove_review_label("org/repo", "42", "needs review")
        args = provider._api.call_args
        # Space should be percent-encoded
        assert "needs%20review" in args[0][1]

    def test_404_label_not_present_is_ok(self):
        """GitHub returns 404 if the label wasn't present — treat as success."""
        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse({}, status_code=404),
        )
        result = provider.remove_review_label("org/repo", "42", "gone")
        assert result is None

    def test_http_error_no_crash(self):
        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse({}, status_code=500),
        )
        provider.remove_review_label("org/repo", "42", "label")

    def test_network_error_no_crash(self):
        import httpx

        provider = GitHubProvider(access_token="t")
        provider._api = mock.MagicMock(side_effect=httpx.HTTPError("boom"))
        provider.remove_review_label("org/repo", "42", "label")


# ---------------------------------------------------------------------------
# get_review_files — GitLab (REST /merge_requests/:iid/changes)
# ---------------------------------------------------------------------------


class TestGitLabGetReviewFiles:
    """GitLabProvider.get_review_files hits /projects/:id/merge_requests/:iid/changes
    and extracts ``new_path`` (or ``old_path``) from each change entry."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

        @property
        def text(self):
            return str(self._payload)

    def test_returns_new_paths(self):
        provider = GitLabProvider(access_token="t")
        changes_payload = {
            "changes": [
                {"old_path": "src/old.py", "new_path": "src/new.py"},
                {"old_path": "src/main.py", "new_path": "src/main.py"},
                {"old_path": "README.md", "new_path": "README.md"},
            ],
        }
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse(changes_payload),
        )
        result = provider.get_review_files("group/project", "42")
        assert result == ["src/new.py", "src/main.py", "README.md"]
        provider._api.assert_called_once()
        args = provider._api.call_args
        assert "GET" == args[0][0]
        assert "/merge_requests/42/changes" in args[0][1]

    def test_falls_back_to_old_path(self):
        """When new_path is missing (e.g., deleted file), use old_path."""
        provider = GitLabProvider(access_token="t")
        changes_payload = {
            "changes": [
                {"old_path": "removed.py", "new_path": ""},
                {"old_path": "src/lib.py", "new_path": "src/lib.py"},
            ],
        }
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse(changes_payload),
        )
        result = provider.get_review_files("group/project", "1")
        assert result == ["removed.py", "src/lib.py"]

    def test_empty_changes(self):
        provider = GitLabProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse({"changes": []}),
        )
        result = provider.get_review_files("group/project", "1")
        assert result == []

    def test_http_error_returns_empty(self):
        provider = GitLabProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse({}, status_code=404),
        )
        result = provider.get_review_files("group/project", "999")
        assert result == []

    def test_network_error_returns_empty(self):
        import httpx

        provider = GitLabProvider(access_token="t")
        provider._api = mock.MagicMock(side_effect=httpx.HTTPError("dns"))
        result = provider.get_review_files("group/project", "1")
        assert result == []


# ---------------------------------------------------------------------------
# add_review_label — GitLab (PUT /merge_requests/:iid with labels param)
# ---------------------------------------------------------------------------


class TestGitLabAddReviewLabel:
    """GitLabProvider.add_review_label fetches the MR to read existing labels,
    appends the new label, and PUTs the full set back."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

        @property
        def text(self):
            return str(self._payload)

    def test_adds_label_preserving_existing(self):
        provider = GitLabProvider(access_token="t")
        # First call: GET to read existing labels.
        # Second call: PUT to write them back.
        responses = [
            self._FakeResponse({"labels": ["feature", "backend"]}),
            self._FakeResponse({}),
        ]

        def fake_api(method, path, **kwargs):
            return responses.pop(0)

        provider._api = mock.MagicMock(side_effect=fake_api)
        provider.add_review_label("group/project", "42", "churn-magnet")
        assert provider._api.call_count == 2
        calls = provider._api.call_args_list
        assert calls[0][0][0] == "GET"
        assert "/merge_requests/42" in calls[0][0][1]
        assert calls[1][0][0] == "PUT"
        assert calls[1][1]["json"]["labels"] == "feature,backend,churn-magnet"

    def test_no_duplicate_when_label_exists(self):
        """If the label is already present, don't add it again."""
        provider = GitLabProvider(access_token="t")
        mr_payload = {"labels": ["feature", "churn-magnet"]}

        def fake_api(method, path, **kwargs):
            if method == "GET":
                return self._FakeResponse(mr_payload)
            return self._FakeResponse({})

        provider._api = mock.MagicMock(side_effect=fake_api)
        provider.add_review_label("group/project", "42", "churn-magnet")
        # Should still do two calls (GET + PUT) but the label set is unchanged.
        calls = provider._api.call_args_list
        assert calls[1][1]["json"]["labels"] == "feature,churn-magnet"

    def test_empty_labels(self):
        """MR with no existing labels should work fine."""
        provider = GitLabProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if method == "GET":
                return self._FakeResponse({"labels": []})
            return self._FakeResponse({})

        provider._api = mock.MagicMock(side_effect=fake_api)
        provider.add_review_label("group/project", "42", "new-label")
        calls = provider._api.call_args_list
        assert calls[1][1]["json"]["labels"] == "new-label"

    def test_http_error_on_fetch(self):
        """If we can't fetch the MR, log and return silently."""
        provider = GitLabProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse({}, status_code=500),
        )
        provider.add_review_label("group/project", "42", "label")

    def test_network_error_no_crash(self):
        import httpx

        provider = GitLabProvider(access_token="t")
        provider._api = mock.MagicMock(side_effect=httpx.HTTPError("boom"))
        provider.add_review_label("group/project", "42", "label")


# ---------------------------------------------------------------------------
# remove_review_label — GitLab (PUT /merge_requests/:iid with labels param)
# ---------------------------------------------------------------------------


class TestGitLabRemoveReviewLabel:
    """GitLabProvider.remove_review_label fetches the MR, removes the target
    label from the set, and PUTs the result back."""

    class _FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

        @property
        def text(self):
            return str(self._payload)

    def test_removes_label_preserving_others(self):
        provider = GitLabProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if method == "GET":
                return self._FakeResponse({"labels": ["feature", "churn-magnet", "backend"]})
            return self._FakeResponse({})

        provider._api = mock.MagicMock(side_effect=fake_api)
        provider.remove_review_label("group/project", "42", "churn-magnet")
        calls = provider._api.call_args_list
        assert calls[1][1]["json"]["labels"] == "feature,backend"

    def test_label_not_present_no_change(self):
        """Removing a label that isn't there should still PUT back the same set."""
        provider = GitLabProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if method == "GET":
                return self._FakeResponse({"labels": ["feature", "backend"]})
            return self._FakeResponse({})

        provider._api = mock.MagicMock(side_effect=fake_api)
        provider.remove_review_label("group/project", "42", "churn-magnet")
        calls = provider._api.call_args_list
        assert calls[1][1]["json"]["labels"] == "feature,backend"

    def test_http_error_no_crash(self):
        provider = GitLabProvider(access_token="t")
        provider._api = mock.MagicMock(
            return_value=self._FakeResponse({}, status_code=500),
        )
        provider.remove_review_label("group/project", "42", "label")

    def test_network_error_no_crash(self):
        import httpx

        provider = GitLabProvider(access_token="t")
        provider._api = mock.MagicMock(side_effect=httpx.HTTPError("boom"))
        provider.remove_review_label("group/project", "42", "label")


# ---------------------------------------------------------------------------
# ReviewRequest.files field
# ---------------------------------------------------------------------------


class TestReviewRequestFiles:
    """ReviewRequest has a ``files`` field (default []) included in to_dict()."""

    def test_defaults_to_empty_list(self):
        rr = ReviewRequest(
            id="1", title="t", url="u", author="a", state="open",
            source_branch="b", target_branch="main",
            created_at="", updated_at="",
        )
        assert rr.files == []

    def test_can_be_set(self):
        rr = ReviewRequest(
            id="1", title="t", url="u", author="a", state="open",
            source_branch="b", target_branch="main",
            created_at="", updated_at="",
            files=["a.py", "b.py"],
        )
        assert rr.files == ["a.py", "b.py"]

    def test_to_dict_includes_files(self):
        rr = ReviewRequest(
            id="1", title="t", url="u", author="a", state="open",
            source_branch="b", target_branch="main",
            created_at="", updated_at="",
            files=["x.py", "y.md"],
        )
        d = rr.to_dict()
        assert d["files"] == ["x.py", "y.md"]


# ---------------------------------------------------------------------------
# GitHubProvider.create_review — 422 idempotency (PR already exists)
# ---------------------------------------------------------------------------


class TestGitHubCreateReviewIdempotent:
    """create_review must return the existing open PR when GitHub responds with
    HTTP 422 "A pull request already exists", instead of returning None and
    causing the orchestrator to loop with 'forge provider returned no review'.

    Regression test for OOMPAH-6 (review handoff loop).
    """

    class _FakeResponse:
        def __init__(self, payload, status_code: int = 200, text: str = ""):
            self._payload = payload
            self.status_code = status_code
            self.text = text or str(payload)

        def json(self):
            return self._payload

    def _pr_payload(self, number: int = 342, branch: str = "OOMPAH-6") -> dict:
        return {
            "number": number,
            "title": f"PR {number}",
            "html_url": f"https://github.com/owner/repo/pull/{number}",
            "user": {"login": "oompah"},
            "state": "open",
            "merged_at": None,
            "head": {"ref": branch, "sha": "abc123"},
            "base": {"ref": "main"},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "body": "",
            "labels": [],
            "draft": False,
            "auto_merge": None,
            "mergeable": True,
            "mergeable_state": "clean",
            "additions": 50,
            "deletions": 5,
        }

    def _provider(self, pr_payload: dict) -> GitHubProvider:
        provider = GitHubProvider(access_token="t")
        calls: list[tuple] = []
        pr_number = str(pr_payload.get("number", "1"))
        branch = pr_payload.get("head", {}).get("ref", "")

        def fake_api(method, path, **kwargs):
            calls.append((method, path, kwargs))
            # POST /pulls — simulate 422 "already exists"
            if method == "POST" and path.endswith("/pulls"):
                return self._FakeResponse(
                    {
                        "message": "Validation Failed",
                        "errors": [{"message": "A pull request already exists for owner:OOMPAH-6."}],
                    },
                    status_code=422,
                    text='{"message": "Validation Failed", "errors": [{"message": "A pull request already exists for owner:OOMPAH-6."}]}',
                )
            # GET /pulls?state=all&head=owner:OOMPAH-6 — find_pr_for_branch
            if method == "GET" and path.endswith("/pulls") and kwargs.get("params", {}).get("state") == "all":
                return self._FakeResponse([pr_payload])
            # GET /pulls/{number} — get_review
            if method == "GET" and f"/pulls/{pr_number}" in path:
                return self._FakeResponse(pr_payload)
            # CI status endpoints
            if path.endswith("/status"):
                return self._FakeResponse({"state": "success", "total_count": 0})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": []})
            raise AssertionError(f"Unexpected API call: {method} {path}")

        provider._api = fake_api
        provider._calls = calls  # type: ignore[attr-defined]

        def fake_graphql(query, variables=None):
            return self._FakeResponse({
                "data": {"repository": {"pullRequest": {"isInMergeQueue": False}}}
            })

        provider._graphql = fake_graphql
        return provider

    def test_returns_existing_pr_on_422_already_exists(self):
        """create_review returns the existing PR when GitHub responds 422."""
        pr = self._pr_payload(number=342, branch="OOMPAH-6")
        provider = self._provider(pr)
        result = provider.create_review(
            "owner/repo", "OOMPAH-6: fix", "OOMPAH-6", target_branch="main"
        )
        assert result is not None, "Expected existing PR to be returned on 422"
        assert result.id == "342"
        assert result.source_branch == "OOMPAH-6"
        assert result.state == "open"

    def test_still_returns_none_on_422_non_duplicate(self):
        """create_review returns None for a 422 that is not a duplicate PR error."""
        provider = GitHubProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            return self._FakeResponse(
                {"message": "Validation Failed", "errors": [{"message": "Invalid base branch."}]},
                status_code=422,
                text='{"message": "Validation Failed", "errors": [{"message": "Invalid base branch."}]}',
            )

        provider._api = fake_api
        result = provider.create_review(
            "owner/repo", "PR title", "feature-branch", target_branch="main"
        )
        assert result is None

    def test_still_returns_none_when_existing_pr_is_closed(self):
        """create_review returns None when the found PR is closed (not open)."""
        pr = self._pr_payload(number=99, branch="OOMPAH-6")
        pr["state"] = "closed"
        pr["merged_at"] = None
        provider = GitHubProvider(access_token="t")

        def fake_api(method, path, **kwargs):
            if method == "POST":
                return self._FakeResponse(
                    {"errors": [{"message": "A pull request already exists."}]},
                    status_code=422,
                    text='{"errors": [{"message": "A pull request already exists."}]}',
                )
            if method == "GET" and path.endswith("/pulls"):
                return self._FakeResponse([pr])
            return self._FakeResponse({}, status_code=404)

        provider._api = fake_api
        result = provider.create_review(
            "owner/repo", "PR title", "OOMPAH-6", target_branch="main"
        )
        assert result is None

    def test_creates_pr_normally_on_201(self):
        """create_review still works normally when GitHub returns 201."""
        pr = self._pr_payload(number=500, branch="new-branch")
        provider = GitHubProvider(access_token="t")
        calls: list[tuple] = []

        def fake_api(method, path, **kwargs):
            calls.append((method, path))
            if method == "POST" and path.endswith("/pulls"):
                return self._FakeResponse(pr, status_code=201)
            if method == "GET" and "/pulls/500" in path:
                return self._FakeResponse(pr)
            if path.endswith("/status"):
                return self._FakeResponse({"state": "success", "total_count": 0})
            if path.endswith("/check-runs"):
                return self._FakeResponse({"check_runs": []})
            raise AssertionError(f"Unexpected: {method} {path}")

        def fake_graphql(query, variables=None):
            return self._FakeResponse({
                "data": {"repository": {"pullRequest": {"isInMergeQueue": False}}}
            })

        provider._api = fake_api
        provider._graphql = fake_graphql
        result = provider.create_review("owner/repo", "New PR", "new-branch")
        assert result is not None
        assert result.id == "500"
        # Only POST + GET should be called — no find_pr_for_branch call
        post_calls = [c for c in calls if c[0] == "POST"]
        assert len(post_calls) == 1
