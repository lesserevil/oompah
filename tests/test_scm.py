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
            auto_merge_enabled=True, mergeable_state="blocked",
        )
        d = rr.to_dict()
        assert d["id"] == "42"
        assert d["needs_rebase"] is True
        assert d["has_conflicts"] is True
        assert d["draft"] is True
        assert d["source_branch"] == "fix-typo"
        assert d["auto_merge_enabled"] is True
        assert d["mergeable_state"] == "blocked"

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

    def test_list_open_reviews_skips_detail_fetch_for_auto_merge(self):
        """Auto-merge enabled means GitHub is already handling it — the
        merge queue (or auto-merge feature) will compute mergeability
        when it actually tries to merge. Skip the extra GET."""
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
        assert detail_calls == [], (
            "auto-merge-enabled PRs must not trigger an extra DETAIL "
            "fetch — GitHub is already handling the merge"
        )

    def test_list_open_reviews_skips_detail_fetch_for_merge_queued(self):
        """Same logic as auto_merge: a PR in the merge queue is being
        handled by GitHub. No need to compute mergeability here."""
        list_pr, detail_pr = self._list_endpoint_payload(
            number=21, auto_merge=None,
            mergeable=False, mergeable_state="dirty",
        )
        provider, detail_calls = self._provider_with_distinct_list_and_detail(
            list_pr, detail_pr, merge_queue_prs=[21],
        )
        reviews = provider.list_open_reviews("x/y")
        assert reviews[0].auto_merge_enabled is True
        assert detail_calls == [], (
            "PRs in the merge queue must not trigger DETAIL fetch — "
            "GitHub is already handling the merge"
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
        """Multi-PR list: each non-auto-merging non-draft PR gets its
        own DETAIL fetch."""
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
            "each non-draft non-auto-merging PR must trigger one "
            "DETAIL fetch"
        )
