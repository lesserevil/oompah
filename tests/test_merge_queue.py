"""Tests for merge-queue support (Step 4 of the submit-queue rollout).

Covers:
- Project.merge_queue_enabled field round-trips (to_dict / from_dict)
- SCMProvider.enable_auto_merge in GitHubProvider (success + failure cases)
- SCMProvider.enable_auto_merge in GitLabProvider (fallback to direct merge)
- _yolo_review_actions_sync: direct mode still calls merge_review (default)
- _yolo_review_actions_sync: queue mode calls enable_auto_merge, not merge_review
- _yolo_review_actions_sync: queue mode with failed enqueue dispatches conflict agent
- parse_github_webhook: merge_group events parsed correctly
- parse_github_webhook: merge_group destroyed+merged=True sets merged=True
- parse_github_webhook: merge_group destroyed+reason!=merged sets merged=False
- parse_github_webhook: checks_requested action
- _webhook_advanced_tracked_branch: merge_group merged event triggers sync
- _webhook_advanced_tracked_branch: merge_group non-merged event does NOT trigger sync
- _label_bead_merged_from_merge_group: labels bead merged on success
- Project CRUD: merge_queue_enabled accepted via UPDATABLE_FIELDS
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call
import fnmatch

import pytest

from oompah.models import Project
from oompah.webhooks import (
    WebhookEvent,
    parse_github_webhook,
    _parse_github_merge_group,
)

# ReviewRequest is imported lazily in tests that need it because oompah.scm
# imports httpx which may not be available in all test environments.
try:
    from oompah.scm import ReviewRequest as _ReviewRequest  # noqa: F401

    _SCM_AVAILABLE = True
except ModuleNotFoundError:
    _SCM_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    project_id: str = "proj-1",
    repo_url: str = "https://github.com/org/repo",
    yolo: bool = True,
    merge_queue_enabled: bool = False,
) -> MagicMock:
    p = MagicMock()
    p.id = project_id
    p.repo_url = repo_url
    p.name = "test-project"
    p.yolo = yolo
    p.merge_queue_enabled = merge_queue_enabled
    p.access_token = None
    return p


def _make_review(
    review_id: str = "42",
    source_branch: str = "feat-branch",
    ci_status: str = "passed",
    has_conflicts: bool = False,
    needs_rebase: bool = False,
    draft: bool = False,
    auto_merge_enabled: bool = False,
    mergeable_state: str = "",
):
    from oompah.scm import ReviewRequest

    return ReviewRequest(
        id=review_id,
        title=f"PR #{review_id}",
        url=f"https://github.com/org/repo/pull/{review_id}",
        author="alice",
        state="open",
        source_branch=source_branch,
        target_branch="main",
        created_at="2025-01-01",
        updated_at="2025-01-02",
        ci_status=ci_status,
        has_conflicts=has_conflicts,
        needs_rebase=needs_rebase,
        draft=draft,
        auto_merge_enabled=auto_merge_enabled,
        mergeable_state=mergeable_state,
    )


# ---------------------------------------------------------------------------
# Project model: merge_queue_enabled field
# ---------------------------------------------------------------------------


class TestProjectMergeQueueEnabled:
    """Project.merge_queue_enabled round-trips through to_dict / from_dict."""

    def test_default_is_false(self):
        p = Project(id="p1", name="n", repo_url="u", repo_path="r")
        assert p.merge_queue_enabled is False

    def test_to_dict_includes_field(self):
        p = Project(
            id="p1", name="n", repo_url="u", repo_path="r", merge_queue_enabled=True
        )
        d = p.to_dict()
        assert d["merge_queue_enabled"] is True

    def test_to_dict_false_included(self):
        p = Project(
            id="p1", name="n", repo_url="u", repo_path="r", merge_queue_enabled=False
        )
        d = p.to_dict()
        assert d["merge_queue_enabled"] is False

    def test_from_dict_parses_true(self):
        d = {
            "id": "p1",
            "name": "n",
            "repo_url": "u",
            "repo_path": "r",
            "merge_queue_enabled": True,
        }
        p = Project.from_dict(d)
        assert p.merge_queue_enabled is True

    def test_from_dict_parses_false(self):
        d = {
            "id": "p1",
            "name": "n",
            "repo_url": "u",
            "repo_path": "r",
            "merge_queue_enabled": False,
        }
        p = Project.from_dict(d)
        assert p.merge_queue_enabled is False

    def test_from_dict_missing_defaults_to_false(self):
        """Backwards compat: existing project dicts without the field default False."""
        d = {"id": "p1", "name": "n", "repo_url": "u", "repo_path": "r"}
        p = Project.from_dict(d)
        assert p.merge_queue_enabled is False

    def test_round_trip(self):
        p = Project(
            id="p1", name="n", repo_url="u", repo_path="r", merge_queue_enabled=True
        )
        p2 = Project.from_dict(p.to_dict())
        assert p2.merge_queue_enabled is True


# ---------------------------------------------------------------------------
# SCM: GitHubProvider.enable_auto_merge
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _SCM_AVAILABLE, reason="httpx not installed")
class TestGitHubEnableAutoMerge:
    """GitHubProvider.enable_auto_merge uses the GraphQL enablePullRequestAutoMerge mutation.

    The previous implementation POSTed to the non-existent REST URL
    ``/repos/{repo}/pulls/{N}/auto-merge`` and 404'd unconditionally
    (bead oompah-zlz_2-d9v). These tests mock both the REST PR-lookup
    (to fetch ``node_id``) and the GraphQL mutation response.
    """

    class _FakeResponse:
        def __init__(
            self, status_code: int, text: str = "", payload: dict | None = None
        ):
            self.status_code = status_code
            self.text = text
            self._payload = payload if payload is not None else {}

        def json(self):
            return self._payload

    def _make_provider(
        self,
        *,
        pr_status: int = 200,
        pr_payload: dict | None = None,
        gql_status: int = 200,
        gql_payload: dict | None = None,
    ):
        """Build a GitHubProvider with both _api (PR lookup) and _graphql (mutation) mocked."""
        from oompah.scm import GitHubProvider

        provider = GitHubProvider(access_token="t")
        provider._api = MagicMock(
            return_value=self._FakeResponse(
                pr_status,
                payload=pr_payload
                if pr_payload is not None
                else {"node_id": "PR_kwDOABCD123"},
            )
        )
        provider._graphql = MagicMock(
            return_value=self._FakeResponse(
                gql_status,
                payload=gql_payload
                if gql_payload is not None
                else {
                    "data": {
                        "enablePullRequestAutoMerge": {
                            "pullRequest": {
                                "autoMergeRequest": {
                                    "enabledAt": "2026-05-06T01:00:00Z"
                                }
                            }
                        }
                    }
                },
            )
        )
        return provider

    def test_success(self):
        provider = self._make_provider()
        ok, msg = provider.enable_auto_merge("org/repo", "42")
        assert ok is True
        assert "auto-merge" in msg.lower()

    def test_pr_lookup_failure_returns_error(self):
        provider = self._make_provider(pr_status=404, pr_payload={})
        ok, msg = provider.enable_auto_merge("org/repo", "42")
        assert ok is False
        assert "PR lookup" in msg
        assert "404" in msg
        # Must not attempt the GraphQL mutation if the PR can't be found.
        provider._graphql.assert_not_called()

    def test_missing_node_id_returns_error(self):
        provider = self._make_provider(pr_payload={"id": 1})
        ok, msg = provider.enable_auto_merge("org/repo", "42")
        assert ok is False
        assert "node_id" in msg

    def test_pr_lookup_http_exception(self):
        import httpx
        from oompah.scm import GitHubProvider

        provider = GitHubProvider(access_token="t")
        provider._api = MagicMock(side_effect=httpx.HTTPError("connection refused"))
        provider._graphql = MagicMock()
        ok, msg = provider.enable_auto_merge("org/repo", "42")
        assert ok is False
        assert "connection refused" in msg.lower() or "lookup" in msg.lower()
        provider._graphql.assert_not_called()

    def test_graphql_http_error(self):
        provider = self._make_provider(gql_status=500)
        ok, msg = provider.enable_auto_merge("org/repo", "42")
        assert ok is False
        assert "500" in msg
        assert "GraphQL" in msg

    def test_graphql_http_exception(self):
        import httpx

        provider = self._make_provider()
        provider._graphql = MagicMock(side_effect=httpx.HTTPError("EOF"))
        ok, msg = provider.enable_auto_merge("org/repo", "42")
        assert ok is False
        assert "GraphQL" in msg or "eof" in msg.lower()

    def test_repo_disallows_auto_merge(self):
        """allow_auto_merge=false on the repo surfaces a distinct error message."""
        provider = self._make_provider(
            gql_payload={
                "errors": [
                    {
                        "message": "Pull request Auto merge is not allowed for this repository"
                    }
                ]
            },
        )
        ok, msg = provider.enable_auto_merge("org/repo", "42")
        assert ok is False
        assert "allow_auto_merge=true" in msg
        assert "org/repo" in msg

    def test_pr_already_mergeable(self):
        """PR in 'clean' status is already mergeable — auto-merge can't attach."""
        provider = self._make_provider(
            gql_payload={"errors": [{"message": "Pull request is in clean status"}]},
        )
        ok, msg = provider.enable_auto_merge("org/repo", "42")
        assert ok is False
        assert "already mergeable" in msg.lower()

    def test_generic_graphql_error(self):
        provider = self._make_provider(
            gql_payload={"errors": [{"message": "Unexpected error"}]},
        )
        ok, msg = provider.enable_auto_merge("org/repo", "42")
        assert ok is False
        assert "Unexpected error" in msg

    def test_does_not_use_legacy_rest_endpoint(self):
        """Regression: the broken REST URL must NEVER be called.

        See bead oompah-zlz_2-d9v: POST /repos/{repo}/pulls/{N}/auto-merge is
        not a real GitHub REST endpoint and 404s unconditionally.
        """
        provider = self._make_provider()
        provider.enable_auto_merge("org/repo", "42")
        # Only call to _api should be the GET PR lookup.
        for c in provider._api.call_args_list:
            method = c[0][0]
            path = c[0][1]
            assert not (method == "POST" and "/auto-merge" in path), (
                f"legacy broken REST URL called: {method} {path}"
            )

    def test_calls_graphql_mutation_with_squash(self):
        provider = self._make_provider()
        provider.enable_auto_merge("org/repo", "42")
        provider._graphql.assert_called_once()
        args, kwargs = provider._graphql.call_args
        # First positional arg is the mutation string.
        assert "enablePullRequestAutoMerge" in args[0]
        # Second positional arg (or kwarg) is variables.
        variables = args[1] if len(args) > 1 else kwargs.get("variables", {})
        assert variables["mergeMethod"] == "SQUASH"
        assert variables["pullRequestId"] == "PR_kwDOABCD123"


# ---------------------------------------------------------------------------
# SCM: GitLabProvider.enable_auto_merge (fallback to direct merge)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _SCM_AVAILABLE, reason="httpx not installed")
class TestGitLabEnableAutoMerge:
    """GitLabProvider.enable_auto_merge falls back to a direct merge."""

    class _FakeResponse:
        def __init__(self, status_code: int, text: str = ""):
            self.status_code = status_code
            self.text = text

        def json(self):
            return {}

    def test_fallback_to_direct_merge_on_success(self):
        from oompah.scm import GitLabProvider

        provider = GitLabProvider(access_token="t")
        provider._api = MagicMock(return_value=self._FakeResponse(200))
        ok, msg = provider.enable_auto_merge("group/project", "7")
        assert ok is True

    def test_fallback_to_direct_merge_on_failure(self):
        from oompah.scm import GitLabProvider

        provider = GitLabProvider(access_token="t")
        provider._api = MagicMock(return_value=self._FakeResponse(422, "cannot merge"))
        ok, msg = provider.enable_auto_merge("group/project", "7")
        assert ok is False
        assert "422" in msg


# ---------------------------------------------------------------------------
# Orchestrator: _yolo_review_actions_sync dispatch mode
# ---------------------------------------------------------------------------


class TestYoloEnqueueMode:
    """Tests that _yolo_review_actions_sync dispatches correctly based on merge_queue_enabled."""

    def _make_orchestrator(self, tmp_path, projects=None):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        return Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_direct_mode_calls_merge_review(self, mock_slug, mock_detect, tmp_path):
        """Default (merge_queue_enabled=False) calls merge_review, not enable_auto_merge."""
        project = _make_project(merge_queue_enabled=False)

        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        provider.merge_review.assert_called_once_with("org/repo", "42")
        provider.enable_auto_merge.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_calls_enable_auto_merge(self, mock_slug, mock_detect, tmp_path):
        """When merge_queue_enabled=True, enable_auto_merge is called instead of merge_review."""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (True, "enqueued")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_called_once_with("org/repo", "42")
        provider.merge_review.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_conflict_failure_dispatches_conflict_agent(
        self, mock_slug, mock_detect, tmp_path
    ):
        """A real merge-conflict failure dispatches the conflict-resolution agent.

        oompah-zlz_2-btf.2: only true conflicts go through
        _yolo_notify_conflict — config errors and transient errors do not.
        """
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (
            False,
            "Pull request is not mergeable: merge conflict in foo.py",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_called_once_with("org/repo", "42")
        orch._yolo_notify_conflict.assert_called_once_with(
            project, provider, "org/repo", "42"
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_successful_enqueue_does_not_dispatch_conflict(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Successful enqueue does not trigger a conflict notification."""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (True, "enqueued")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        orch._yolo_notify_conflict.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_enqueues_all_qualified_prs_in_one_tick(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Queue mode does NOT serialize: GitHub's merge queue handles
        ordering, so all qualified CI-passed PRs get enqueued in one
        YOLO tick. Previously (oompah-zlz_2-grw), the loop broke after
        the first enqueue, forcing PRs to be enqueued one-per-tick which
        also starved later conflict-path / ci-failed dispatches when an
        enqueue failed. (oompah-zlz_2-grw — fix B)"""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (True, "enqueued")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review("1", ci_status="passed"),
                _make_review("2", ci_status="passed"),
                _make_review("3", ci_status="passed"),
            ]
        }

        orch._yolo_review_actions_sync()

        assert provider.enable_auto_merge.call_count == 3
        provider.enable_auto_merge.assert_has_calls(
            [
                call("org/repo", "1"),
                call("org/repo", "2"),
                call("org/repo", "3"),
            ]
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_failed_enqueue_does_not_starve_later_prs(
        self, mock_slug, mock_detect, tmp_path
    ):
        """A FAILED enqueue must NOT break the YOLO loop: subsequent
        PRs in the iteration must still be checked (and conflict-path /
        ci-failed dispatches must still fire for them).

        Live evidence (2026-05-08): #59 ci=passed mergeable=CLEAN
        enqueue→FAIL("Pull request is in clean status") starved #58
        and #56 (has_conflicts=True) from ever reaching
        _yolo_notify_conflict. (oompah-zlz_2-grw — fix A)"""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (
            False,
            "Auto-merge rejected (PR already mergeable): Pull request "
            "is in clean status",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {
            project.id: [
                # First PR: enqueue will fail (transient).
                _make_review("59", ci_status="passed"),
                # Older PRs: have_conflicts=True — must reach
                # _yolo_notify_conflict despite #59's failure.
                _make_review("58", ci_status="passed", has_conflicts=True),
                _make_review("56", ci_status="passed", has_conflicts=True),
            ]
        }

        orch._yolo_review_actions_sync()

        # First PR was attempted (and failed).
        provider.enable_auto_merge.assert_called_once_with("org/repo", "59")
        # BOTH older DIRTY PRs must reach the conflict-resolution path —
        # this is the regression fix.
        assert orch._yolo_notify_conflict.call_count == 2
        conflict_ids = [c[0][3] for c in orch._yolo_notify_conflict.call_args_list]
        assert conflict_ids == ["58", "56"]

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_failed_then_successful_enqueue_in_one_tick(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Two non-queued PRs (queue mode), first fails enqueue → second
        still gets enqueued in the same tick. (oompah-zlz_2-grw — fix A
        + fix B combined acceptance criterion)"""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        # First call fails, second call succeeds.
        provider.enable_auto_merge.side_effect = [
            (False, "transient error"),
            (True, "enqueued"),
        ]
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {
            project.id: [
                _make_review("100", ci_status="passed"),
                _make_review("101", ci_status="passed"),
            ]
        }

        orch._yolo_review_actions_sync()

        # Both PRs attempted in the same tick — fix A (failed enqueue
        # does not break) AND fix B (successful enqueue does not break).
        assert provider.enable_auto_merge.call_count == 2
        provider.enable_auto_merge.assert_has_calls(
            [
                call("org/repo", "100"),
                call("org/repo", "101"),
            ]
        )
        # Neither has_conflicts so no conflict notification.
        orch._yolo_notify_conflict.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_direct_mode_successful_merge_still_breaks_loop(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Regression: in direct-merge mode (merge_queue_enabled=False),
        a SUCCESSFUL merge MUST still break the loop — the target
        branch changed and subsequent PRs need rebasing first. This
        preserves the genuine race protection that fix B does NOT
        relax. (oompah-zlz_2-grw acceptance criterion)"""
        project = _make_project(merge_queue_enabled=False)

        provider = MagicMock()
        provider.merge_review.return_value = (True, "merged")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review("1", ci_status="passed"),
                _make_review("2", ci_status="passed"),
            ]
        }

        orch._yolo_review_actions_sync()

        # Only the FIRST PR gets merged this tick. The second PR will
        # be picked up next tick after it rebases.
        assert provider.merge_review.call_count == 1
        provider.merge_review.assert_called_once_with("org/repo", "1")

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_direct_mode_failed_merge_does_not_starve_later_prs(
        self, mock_slug, mock_detect, tmp_path
    ):
        """In direct-merge mode, a FAILED merge does NOT change the
        target branch and so MUST NOT break the loop — subsequent PRs
        must still be checked, including conflict-path dispatches for
        DIRTY older PRs. Same starvation pattern as queue mode.
        (oompah-zlz_2-grw — fix A)"""
        project = _make_project(merge_queue_enabled=False)

        provider = MagicMock()
        provider.merge_review.return_value = (False, "transient 502 Bad Gateway")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {
            project.id: [
                _make_review("70", ci_status="passed"),
                _make_review("69", ci_status="passed", has_conflicts=True),
            ]
        }

        orch._yolo_review_actions_sync()

        # Failed merge attempted on first PR.
        provider.merge_review.assert_called_once_with("org/repo", "70")
        # Older DIRTY PR still reaches conflict resolution.
        orch._yolo_notify_conflict.assert_called_once_with(
            project, provider, "org/repo", "69"
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_pending_ci_is_skipped(self, mock_slug, mock_detect, tmp_path):
        """Queue mode does not enqueue a PR when CI is still pending."""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="pending")]}

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_needs_rebase_is_skipped(self, mock_slug, mock_detect, tmp_path):
        """Queue mode does not enqueue a PR that needs a rebase."""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [_make_review("42", ci_status="passed", needs_rebase=True)]
        }

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_skips_already_enqueued_pr(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Idempotency: when auto_merge is already enabled, do NOT call enable_auto_merge again.

        Once GitHub has accepted the PR into the merge queue (auto_merge.enabled_by != null),
        the watchdog must skip it — re-dispatching the GraphQL mutation every tick is at best
        noise, and a future API version could double-enqueue or revoke the existing
        auto-merge. (oompah-zlz_2-btf.1, GAP 2)
        """
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [_make_review("9", ci_status="passed", auto_merge_enabled=True)]
        }

        orch._yolo_review_actions_sync()

        provider.enable_auto_merge.assert_not_called()
        provider.merge_review.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_queue_mode_enqueued_pr_does_not_block_subsequent_pr(
        self, mock_slug, mock_detect, tmp_path
    ):
        """An already-enqueued PR is `continue`d (not `break`ed) so that a
        following non-enqueued PR can still be processed in the same tick."""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (True, "enqueued")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review("9", ci_status="passed", auto_merge_enabled=True),
                _make_review("10", ci_status="passed", auto_merge_enabled=False),
            ]
        }

        orch._yolo_review_actions_sync()

        # PR #9 skipped (already enqueued); PR #10 enqueued this tick.
        provider.enable_auto_merge.assert_called_once_with("org/repo", "10")

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_auto_merge_enabled_dirty_pr_dispatches_conflict_agent(
        self, mock_slug, mock_detect, tmp_path
    ):
        """A PR enqueued for auto-merge that has gone DIRTY (e.g.
        another PR landed first with overlapping files) must dispatch
        a conflict agent — NOT be skipped by the auto_merge_enabled
        idempotency guard. GitHub will sit on a DIRTY queued PR
        forever waiting for manual conflict resolution.
        (oompah-zlz_2-l81 — fixes regression of oompah-zlz_2-8rb)"""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "16",
                    ci_status="passed",
                    auto_merge_enabled=True,
                    has_conflicts=True,
                    mergeable_state="dirty",
                )
            ]
        }

        orch._yolo_review_actions_sync()

        # MUST dispatch a conflict agent so the merge-conflict bead is
        # filed; MUST NOT call enable_auto_merge (already enqueued)
        # or merge_review (would fail anyway on a DIRTY PR).
        orch._yolo_notify_conflict.assert_called_once_with(
            project, provider, "org/repo", "16"
        )
        provider.enable_auto_merge.assert_not_called()
        provider.merge_review.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_auto_merge_enabled_clean_pr_still_skipped(
        self, mock_slug, mock_detect, tmp_path
    ):
        """An auto-merge-enabled PR with NO conflicts must still be
        skipped — GitHub is handling it. We're only changing the
        DIRTY behavior, not the common-case idempotency. (oompah-zlz_2-l81)"""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "17",
                    ci_status="passed",
                    auto_merge_enabled=True,
                    has_conflicts=False,
                    mergeable_state="clean",
                )
            ]
        }

        orch._yolo_review_actions_sync()

        # Clean enqueued PR → no action; idempotency guard fires.
        orch._yolo_notify_conflict.assert_not_called()
        provider.enable_auto_merge.assert_not_called()
        provider.merge_review.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_auto_merge_enabled_failed_ci_dispatches_retry_ci(
        self, mock_slug, mock_detect, tmp_path
    ):
        """A PR with auto_merge_enabled=True AND ci_status='failed' must
        dispatch a ci-fix agent — NOT be skipped by the
        auto_merge_enabled idempotency guard. GitHub's auto-merge means
        "merge when ready" — a PR with failing CI will never become
        ready on its own. Without this dispatch, YOLO silently sits on
        a failing auto-merge-enabled PR forever.
        (oompah-zlz_2-wjz — fixes regression of oompah-zlz_2-btf.1)"""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_retry_ci = MagicMock()
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "44",
                    ci_status="failed",
                    auto_merge_enabled=True,
                    has_conflicts=False,
                )
            ]
        }

        orch._yolo_review_actions_sync()

        # MUST dispatch a ci-fix agent so the failing tests get fixed;
        # MUST NOT call enable_auto_merge or merge_review (already
        # enqueued, can't merge a failing PR), MUST NOT dispatch
        # conflict agent (no conflicts).
        orch._yolo_retry_ci.assert_called_once()
        assert orch._yolo_retry_ci.call_args[0][0] is project
        assert orch._yolo_retry_ci.call_args[0][1].id == "44"
        orch._yolo_notify_conflict.assert_not_called()
        provider.enable_auto_merge.assert_not_called()
        provider.merge_review.assert_not_called()

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_auto_merge_enabled_passed_ci_no_extra_enqueue_call(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Regression: an auto-merge-enabled PR with ci_status='passed'
        must remain silently skipped — the idempotency guard from
        btf.1 must still fire for the common-case where GitHub's
        merge queue is genuinely handling the PR. (oompah-zlz_2-wjz
        scope check)"""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_retry_ci = MagicMock()
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {
            project.id: [
                _make_review(
                    "45",
                    ci_status="passed",
                    auto_merge_enabled=True,
                    has_conflicts=False,
                )
            ]
        }

        orch._yolo_review_actions_sync()

        # No extra GraphQL enable_auto_merge call, no merge_review,
        # no ci-fix dispatch, no conflict dispatch — pure idempotency.
        provider.enable_auto_merge.assert_not_called()
        provider.merge_review.assert_not_called()
        orch._yolo_retry_ci.assert_not_called()
        orch._yolo_notify_conflict.assert_not_called()


# ---------------------------------------------------------------------------
# YOLO merge-failure classifier (oompah-zlz_2-btf.2)
# ---------------------------------------------------------------------------


class TestClassifyYoloMergeError:
    """The classifier distinguishes operator-action errors (repo config)
    from agent-action errors (merge conflict) and unknown failures
    (transient). Misclassification dispatches doomed conflict agents,
    so the test matrix is intentionally broad."""

    def test_config_error_repo_allow_auto_merge(self):
        from oompah.orchestrator import _classify_yolo_merge_error

        # Real GitHub error from the bug report.
        msg = (
            "Auto-merge not allowed by repo (set allow_auto_merge=true on "
            "NVIDIA-Omniverse/trickle): Auto merge is not allowed for this repository"
        )
        assert _classify_yolo_merge_error(msg) == "config"

    def test_config_error_auto_merge_is_not_enabled(self):
        from oompah.orchestrator import _classify_yolo_merge_error

        assert (
            _classify_yolo_merge_error(
                "Pull request auto-merge is not enabled for this repository"
            )
            == "config"
        )

    def test_config_error_branch_protection(self):
        from oompah.orchestrator import _classify_yolo_merge_error

        assert (
            _classify_yolo_merge_error("Branch protection rules block this merge")
            == "config"
        )

    def test_config_error_404_with_auto_merge_keyword(self):
        from oompah.orchestrator import _classify_yolo_merge_error

        assert (
            _classify_yolo_merge_error("404 Not Found on auto-merge endpoint")
            == "config"
        )

    def test_conflict_error_merge_conflict(self):
        from oompah.orchestrator import _classify_yolo_merge_error

        assert _classify_yolo_merge_error("Merge conflict in src/foo.py") == "conflict"

    def test_conflict_error_not_mergeable(self):
        from oompah.orchestrator import _classify_yolo_merge_error

        assert _classify_yolo_merge_error("Pull request is not mergeable") == "conflict"

    def test_transient_error_405(self):
        from oompah.orchestrator import _classify_yolo_merge_error

        assert _classify_yolo_merge_error("405 Method Not Allowed") == "transient"

    def test_transient_error_rate_limit(self):
        from oompah.orchestrator import _classify_yolo_merge_error

        assert _classify_yolo_merge_error("API rate limit exceeded") == "transient"

    def test_transient_empty_message(self):
        from oompah.orchestrator import _classify_yolo_merge_error

        assert _classify_yolo_merge_error("") == "transient"
        assert _classify_yolo_merge_error(None) == "transient"  # type: ignore[arg-type]

    def test_config_takes_precedence_when_both_keywords_present(self):
        """If a message mentions both auto-merge config and 'conflicts',
        classify as config — fixing the toggle is the correct first move."""
        from oompah.orchestrator import _classify_yolo_merge_error

        msg = "Auto-merge not allowed by repo. Status: has conflicts."
        assert _classify_yolo_merge_error(msg) == "config"

    def test_acceptance_criteria_five_samples(self):
        """Acceptance criterion from the issue: five sample messages
        classify as 3 config / 1 conflict / 1 transient."""
        from oompah.orchestrator import _classify_yolo_merge_error

        samples = [
            ("Auto-merge not allowed by repo", "config"),
            ("Auto merge is not allowed for this repository", "config"),
            ("Pull request auto-merge is not enabled", "config"),
            ("Merge conflict in foo.py", "conflict"),
            ("502 Bad Gateway", "transient"),
        ]
        results = [_classify_yolo_merge_error(m) for m, _ in samples]
        expected = [k for _, k in samples]
        assert results == expected
        assert results.count("config") == 3
        assert results.count("conflict") == 1
        assert results.count("transient") == 1


class TestYoloMergeFailureRouting:
    """Verify _yolo_review_actions_sync routes failures correctly:
    config errors don't dispatch conflict agents, conflicts do, transient
    errors don't (and don't reopen the bead)."""

    def _make_orchestrator(self, tmp_path, projects=None):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        project_store.get.side_effect = lambda pid: next(
            (p for p in (projects or []) if p.id == pid), None
        )
        return Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_config_error_does_not_reopen_bead_or_dispatch_conflict(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Bug fix oompah-zlz_2-btf.2: a config error must NOT call
        _yolo_notify_conflict and must NOT reopen the bead — those
        burn agent budget on a problem only the operator can fix."""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (
            False,
            "Auto merge is not allowed for this repository",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        # The provider was called, but no conflict notification fired.
        provider.enable_auto_merge.assert_called_once_with("org/repo", "42")
        orch._yolo_notify_conflict.assert_not_called()
        # And the orchestrator records the error for the dashboard.
        assert (project.id, "42") in orch._yolo_repo_config_errors
        entry = orch._yolo_repo_config_errors[(project.id, "42")]
        assert "auto merge is not allowed" in entry["msg"].lower()
        assert entry["fingerprint"]
        assert entry["operation"] == "enqueue"

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_conflict_error_dispatches_conflict_agent(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Conflict messages preserve the existing behavior — dispatch."""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (
            False,
            "Pull request is not mergeable: merge conflict",
        )
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        orch._yolo_notify_conflict.assert_called_once_with(
            project,
            provider,
            "org/repo",
            "42",
        )
        # Conflicts are NOT recorded as repo-config errors.
        assert (project.id, "42") not in orch._yolo_repo_config_errors

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_transient_error_does_not_dispatch_conflict(
        self, mock_slug, mock_detect, tmp_path
    ):
        """A transient error (rate limit, 5xx) should log a warning and
        retry next tick — NOT dispatch a conflict-resolution agent."""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (False, "502 Bad Gateway")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        orch._yolo_notify_conflict.assert_not_called()
        assert (project.id, "42") not in orch._yolo_repo_config_errors

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_config_error_logged_once_per_fingerprint(
        self, mock_slug, mock_detect, tmp_path, caplog
    ):
        """Acceptance criterion: identical config errors collapse to one
        log entry, not one-per-tick-per-PR."""
        import logging

        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        msg = "Auto merge is not allowed for this repository"
        provider.enable_auto_merge.return_value = (False, msg)
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_notify_conflict = MagicMock()
        # Two PRs in the cache, both hit the same config error.
        orch._reviews_cache = {
            project.id: [
                _make_review("42", ci_status="passed"),
                _make_review("43", ci_status="passed"),
            ]
        }

        # First tick: the loop only acts on one PR per project per tick
        # (serialization), but we want to verify the de-dup mechanism.
        # Force-process both PRs by calling the helper directly twice.
        with caplog.at_level(logging.ERROR, logger="oompah.orchestrator"):
            orch._handle_yolo_merge_failure(
                project,
                provider,
                "org/repo",
                "42",
                msg,
                operation="enqueue",
            )
            orch._handle_yolo_merge_failure(
                project,
                provider,
                "org/repo",
                "43",
                msg,
                operation="enqueue",
            )

        # Both PRs are recorded.
        assert (project.id, "42") in orch._yolo_repo_config_errors
        assert (project.id, "43") in orch._yolo_repo_config_errors
        # But only one ERROR log line — the second was deduped.
        error_records = [
            r
            for r in caplog.records
            if r.levelno >= logging.ERROR and "blocked on" in r.getMessage()
        ]
        assert len(error_records) == 1, (
            f"Expected 1 deduplicated ERROR, got {len(error_records)}: "
            f"{[r.getMessage() for r in error_records]}"
        )

    @patch("oompah.orchestrator.detect_provider")
    @patch("oompah.orchestrator.extract_repo_slug")
    def test_successful_enqueue_clears_existing_repo_config_error(
        self, mock_slug, mock_detect, tmp_path
    ):
        """Once the operator fixes the toggle and the next enqueue
        succeeds, the recorded error must clear so the dashboard
        badge stops showing 'needs repo config'."""
        project = _make_project(merge_queue_enabled=True)

        provider = MagicMock()
        provider.enable_auto_merge.return_value = (True, "enqueued")
        mock_detect.return_value = provider
        mock_slug.return_value = "org/repo"

        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._yolo_repo_config_errors[(project.id, "42")] = {
            "msg": "Auto merge is not allowed",
            "fingerprint": "abc",
            "operation": "enqueue",
        }
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}

        orch._yolo_review_actions_sync()

        assert (project.id, "42") not in orch._yolo_repo_config_errors

    def test_prune_drops_errors_for_closed_prs(self, tmp_path):
        """When a PR disappears from the per-tick cache (closed, merged
        externally), its repo-config error must be pruned so the
        dashboard count doesn't stay elevated forever."""
        project = _make_project(merge_queue_enabled=True)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        # Two PRs tracked.
        orch._yolo_repo_config_errors[(project.id, "42")] = {
            "msg": "x",
            "fingerprint": "f1",
            "operation": "enqueue",
        }
        orch._yolo_repo_config_errors[(project.id, "43")] = {
            "msg": "x",
            "fingerprint": "f1",
            "operation": "enqueue",
        }
        # Only PR #42 is still open this tick.
        live_cache = {project.id: [_make_review("42", ci_status="passed")]}

        orch._prune_stale_repo_config_errors(live_cache)

        assert (project.id, "42") in orch._yolo_repo_config_errors
        assert (project.id, "43") not in orch._yolo_repo_config_errors


class TestReviewsSummaryNeedsRepoConfig:
    """The dashboard's reviews_summary must surface a 'needs_repo_config'
    count so the badge can warn the operator that a repo toggle is
    blocking YOLO merges. (oompah-zlz_2-btf.2)"""

    def _make_orchestrator(self, tmp_path, projects=None):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        return Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

    def test_needs_repo_config_zero_when_no_errors(self, tmp_path):
        project = _make_project(merge_queue_enabled=True)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}
        summary = orch._reviews_summary()
        assert summary["needs_repo_config"] == 0

    def test_needs_repo_config_counts_tracked_errors(self, tmp_path):
        project = _make_project(merge_queue_enabled=True)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review("42", ci_status="passed"),
                _make_review("43", ci_status="passed"),
            ]
        }
        orch._yolo_repo_config_errors[(project.id, "42")] = {
            "msg": "Auto merge not allowed",
            "fingerprint": "f",
            "operation": "enqueue",
        }
        orch._yolo_repo_config_errors[(project.id, "43")] = {
            "msg": "Auto merge not allowed",
            "fingerprint": "f",
            "operation": "enqueue",
        }
        summary = orch._reviews_summary()
        assert summary["needs_repo_config"] == 2

    def test_needs_repo_config_excludes_stale_entries(self, tmp_path):
        """Entry for a PR that's no longer in the cache must NOT count
        toward needs_repo_config (so the badge clears once the PR is
        closed/merged)."""
        project = _make_project(merge_queue_enabled=True)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        # Only PR #42 is in this tick's cache.
        orch._reviews_cache = {project.id: [_make_review("42", ci_status="passed")]}
        # But errors are tracked for both #42 and stale #43.
        orch._yolo_repo_config_errors[(project.id, "42")] = {
            "msg": "Auto merge not allowed",
            "fingerprint": "f",
            "operation": "enqueue",
        }
        orch._yolo_repo_config_errors[(project.id, "43")] = {
            "msg": "Auto merge not allowed",
            "fingerprint": "f",
            "operation": "enqueue",
        }
        summary = orch._reviews_summary()
        assert summary["needs_repo_config"] == 1


# ---------------------------------------------------------------------------
# _reviews_summary: queued count surfaces queue state to the dashboard
# ---------------------------------------------------------------------------


class TestReviewsSummaryQueued:
    """The dashboard's reviews_summary must surface a 'queued' count
    (auto_merge_enabled yolo PRs) so the operator can see whether a yolo PR
    is already in GitHub's merge queue or just awaiting enqueue.
    (oompah-zlz_2-btf.1, GAP 3)"""

    def _make_orchestrator(self, tmp_path, projects=None):
        from oompah.config import ServiceConfig
        from oompah.orchestrator import Orchestrator

        project_store = MagicMock()
        project_store.list_all.return_value = projects or []
        return Orchestrator(
            config=ServiceConfig(),
            workflow_path="WORKFLOW.md",
            project_store=project_store,
            state_path=str(tmp_path / "state.json"),
        )

    def test_queued_count_is_zero_when_no_pr_enqueued(self, tmp_path):
        project = _make_project(merge_queue_enabled=True)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review("1", ci_status="passed", auto_merge_enabled=False)
            ]
        }
        summary = orch._reviews_summary()
        assert summary["total"] == 1
        assert summary["yolo_pending"] == 1
        assert summary["queued"] == 0

    def test_queued_count_matches_enqueued_pr_count(self, tmp_path):
        project = _make_project(merge_queue_enabled=True)
        orch = self._make_orchestrator(tmp_path, projects=[project])
        orch._reviews_cache = {
            project.id: [
                _make_review("1", ci_status="passed", auto_merge_enabled=True),
                _make_review("2", ci_status="passed", auto_merge_enabled=True),
                _make_review("3", ci_status="passed", auto_merge_enabled=False),
            ]
        }
        summary = orch._reviews_summary()
        assert summary["total"] == 3
        assert summary["yolo_pending"] == 3
        assert summary["queued"] == 2

    def test_queued_only_counts_yolo_projects(self, tmp_path):
        """A non-yolo project's auto_merge_enabled PR shouldn't bump the
        queued counter — operators only enable auto-merge through yolo."""
        non_yolo = _make_project(project_id="p-non", yolo=False)
        orch = self._make_orchestrator(tmp_path, projects=[non_yolo])
        orch._reviews_cache = {
            non_yolo.id: [
                _make_review("1", ci_status="passed", auto_merge_enabled=True)
            ]
        }
        summary = orch._reviews_summary()
        assert summary["total"] == 1
        assert summary["yolo_pending"] == 0
        assert summary["queued"] == 0


# ---------------------------------------------------------------------------
# Webhooks: parse_github_webhook merge_group events
# ---------------------------------------------------------------------------


class TestParseGithubMergeGroupWebhook:
    """parse_github_webhook correctly handles merge_group events."""

    def _make_payload(
        self,
        action: str = "checks_requested",
        reason: str = "",
        head_ref: str = "gh-readonly-queue/main/pr-42-feat-branch",
        base_ref: str = "main",
        repo: str = "org/repo",
    ) -> dict:
        payload = {
            "action": action,
            "merge_group": {
                "head_ref": head_ref,
                "base_ref": base_ref,
            },
            "repository": {"full_name": repo},
        }
        if reason:
            payload["reason"] = reason
        return payload

    def test_merge_group_event_is_parsed(self):
        payload = self._make_payload(action="checks_requested")
        event = parse_github_webhook("merge_group", payload)
        assert event is not None
        assert event.event_type == "merge_group"
        assert event.provider == "github"

    def test_checks_requested_action(self):
        payload = self._make_payload(action="checks_requested")
        event = parse_github_webhook("merge_group", payload)
        assert event.action == "checks_requested"
        assert event.merged is False

    def test_destroyed_with_merged_reason_sets_merged_true(self):
        payload = self._make_payload(action="destroyed", reason="merged")
        event = parse_github_webhook("merge_group", payload)
        assert event.merged is True

    def test_destroyed_with_invalidated_reason_sets_merged_false(self):
        payload = self._make_payload(action="destroyed", reason="invalidated")
        event = parse_github_webhook("merge_group", payload)
        assert event.merged is False

    def test_destroyed_with_dequeued_reason_sets_merged_false(self):
        payload = self._make_payload(action="destroyed", reason="dequeued")
        event = parse_github_webhook("merge_group", payload)
        assert event.merged is False

    def test_destroyed_without_reason_sets_merged_false(self):
        payload = self._make_payload(action="destroyed")
        event = parse_github_webhook("merge_group", payload)
        assert event.merged is False

    def test_repo_slug_extracted(self):
        payload = self._make_payload(repo="myorg/myrepo")
        event = parse_github_webhook("merge_group", payload)
        assert event.repo_slug == "myorg/myrepo"

    def test_head_ref_in_source_branch(self):
        head_ref = "gh-readonly-queue/main/pr-42-oompah-zlz_2-xyz"
        payload = self._make_payload(head_ref=head_ref)
        event = parse_github_webhook("merge_group", payload)
        assert event.source_branch == head_ref

    def test_base_ref_in_target_branch(self):
        payload = self._make_payload(base_ref="main")
        event = parse_github_webhook("merge_group", payload)
        assert event.target_branch == "main"

    def test_no_review_id_for_merge_group(self):
        """merge_group events don't directly carry a PR number."""
        payload = self._make_payload()
        event = parse_github_webhook("merge_group", payload)
        assert event.review_id == ""

    def test_none_on_empty_merge_group_object(self):
        """Malformed payload (no merge_group key) returns None."""
        event = parse_github_webhook("merge_group", {"action": "checks_requested"})
        assert event is None

    def test_other_events_still_ignored(self):
        """Sanity: non-merge_group events still route correctly."""
        event = parse_github_webhook("star", {"action": "created"})
        assert event is None

    def test_pull_request_event_unchanged(self):
        """Existing PR parsing is not broken by the new handler."""
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 7,
                "title": "feat",
                "merged": False,
                "user": {"login": "alice"},
                "head": {"ref": "feat-branch"},
                "base": {"ref": "main"},
            },
            "repository": {"full_name": "org/repo"},
        }
        event = parse_github_webhook("pull_request", payload)
        assert event is not None
        assert event.event_type == "pull_request"


# ---------------------------------------------------------------------------
# Server: _webhook_advanced_tracked_branch for merge_group events
# ---------------------------------------------------------------------------


class TestWebhookAdvancedTrackedBranchMergeGroup:
    """_webhook_advanced_tracked_branch recognises successful merge_group events."""

    def _make_project_obj(self, branch: str = "main") -> MagicMock:
        p = MagicMock()
        p.branch = branch
        p.default_branch = branch
        p.branches = [branch]
        p.matches_branch = lambda b: fnmatch.fnmatch(b, branch)
        return p

    def _make_merge_group_event(
        self, merged: bool, target_branch: str = "main"
    ) -> WebhookEvent:
        return WebhookEvent(
            provider="github",
            event_type="merge_group",
            action="destroyed",
            repo_slug="org/repo",
            source_branch="gh-readonly-queue/main/pr-42-feat",
            target_branch=target_branch,
            merged=merged,
        )

    def test_merge_group_merged_and_target_matches(self):
        from oompah.server import _webhook_advanced_tracked_branch

        project = self._make_project_obj("main")
        event = self._make_merge_group_event(merged=True, target_branch="main")
        assert _webhook_advanced_tracked_branch(event, project) is True

    def test_merge_group_not_merged_does_not_advance(self):
        from oompah.server import _webhook_advanced_tracked_branch

        project = self._make_project_obj("main")
        event = self._make_merge_group_event(merged=False, target_branch="main")
        assert _webhook_advanced_tracked_branch(event, project) is False

    def test_merge_group_merged_but_different_branch(self):
        from oompah.server import _webhook_advanced_tracked_branch

        project = self._make_project_obj("develop")
        event = self._make_merge_group_event(merged=True, target_branch="main")
        assert _webhook_advanced_tracked_branch(event, project) is False

    def test_push_event_unaffected(self):
        """Sanity: push event still works as before."""
        from oompah.server import _webhook_advanced_tracked_branch

        project = self._make_project_obj("main")
        event = WebhookEvent(
            provider="github",
            event_type="push",
            action="pushed",
            target_branch="main",
        )
        assert _webhook_advanced_tracked_branch(event, project) is True

    def test_pull_request_merged_unaffected(self):
        """Sanity: PR closed+merged event still works as before."""
        from oompah.server import _webhook_advanced_tracked_branch

        project = self._make_project_obj("main")
        event = WebhookEvent(
            provider="github",
            event_type="pull_request",
            action="closed",
            target_branch="main",
            merged=True,
        )
        assert _webhook_advanced_tracked_branch(event, project) is True


# ---------------------------------------------------------------------------
# Server: _label_bead_merged_from_merge_group
# ---------------------------------------------------------------------------


class TestLabelBeadMergedFromMergeGroup:
    """_label_bead_merged_from_merge_group parses head_ref and labels the bead."""

    def _make_orch_with_tracker(self, issue_id: str, issue_labels: list[str]):
        """Build a minimal mock orchestrator with one issue in the tracker."""
        mock_issue = MagicMock()
        mock_issue.identifier = issue_id
        mock_issue.labels = issue_labels

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = mock_issue

        orch = MagicMock()
        orch._tracker_for_project.return_value = mock_tracker
        return orch, mock_tracker, mock_issue

    def _make_project(self, project_id: str = "proj-1") -> MagicMock:
        p = MagicMock()
        p.id = project_id
        return p

    def test_labels_bead_merged_on_success(self):
        from oompah.server import _label_bead_merged_from_merge_group

        # head_ref: gh-readonly-queue/main/pr-42-oompah-zlz_2-xyz
        orch, tracker, issue = self._make_orch_with_tracker("oompah-zlz_2-xyz", [])
        project = self._make_project()
        event = WebhookEvent(
            provider="github",
            event_type="merge_group",
            action="destroyed",
            source_branch="gh-readonly-queue/main/pr-42-oompah-zlz_2-xyz",
            merged=True,
        )

        _label_bead_merged_from_merge_group(orch, event, project)

        tracker.add_label.assert_called_once_with("oompah-zlz_2-xyz", "merged")

    def test_skips_already_merged_bead(self):
        from oompah.server import _label_bead_merged_from_merge_group

        orch, tracker, issue = self._make_orch_with_tracker(
            "oompah-zlz_2-xyz", ["merged"]
        )
        project = self._make_project()
        event = WebhookEvent(
            provider="github",
            event_type="merge_group",
            action="destroyed",
            source_branch="gh-readonly-queue/main/pr-42-oompah-zlz_2-xyz",
            merged=True,
        )

        _label_bead_merged_from_merge_group(orch, event, project)

        tracker.add_label.assert_not_called()

    def test_no_project_is_noop(self):
        from oompah.server import _label_bead_merged_from_merge_group

        orch = MagicMock()
        event = WebhookEvent(
            provider="github",
            event_type="merge_group",
            action="destroyed",
            source_branch="gh-readonly-queue/main/pr-42-feat",
            merged=True,
        )

        # Should not raise
        _label_bead_merged_from_merge_group(orch, event, None)
        orch._tracker_for_project.assert_not_called()

    def test_empty_source_branch_is_noop(self):
        from oompah.server import _label_bead_merged_from_merge_group

        orch = MagicMock()
        project = self._make_project()
        event = WebhookEvent(
            provider="github",
            event_type="merge_group",
            action="destroyed",
            source_branch="",
            merged=True,
        )

        _label_bead_merged_from_merge_group(orch, event, project)
        orch._tracker_for_project.assert_not_called()

    def test_tracker_error_does_not_raise(self):
        from oompah.server import _label_bead_merged_from_merge_group

        orch = MagicMock()
        orch._tracker_for_project.side_effect = Exception("db offline")
        project = self._make_project()
        event = WebhookEvent(
            provider="github",
            event_type="merge_group",
            action="destroyed",
            source_branch="gh-readonly-queue/main/pr-42-feat",
            merged=True,
        )

        # Should not raise
        _label_bead_merged_from_merge_group(orch, event, project)

    def test_bead_not_found_is_noop(self):
        from oompah.server import _label_bead_merged_from_merge_group

        mock_tracker = MagicMock()
        mock_tracker.fetch_issue_detail.return_value = None
        orch = MagicMock()
        orch._tracker_for_project.return_value = mock_tracker
        project = self._make_project()
        event = WebhookEvent(
            provider="github",
            event_type="merge_group",
            action="destroyed",
            source_branch="gh-readonly-queue/main/pr-99-unknown-branch",
            merged=True,
        )

        _label_bead_merged_from_merge_group(orch, event, project)
        mock_tracker.add_label.assert_not_called()


# ---------------------------------------------------------------------------
# ProjectStore: merge_queue_enabled in UPDATABLE_FIELDS
# ---------------------------------------------------------------------------


class TestProjectStoreUpdatableFields:
    """merge_queue_enabled is accepted by ProjectStore.update."""

    def test_merge_queue_enabled_in_updatable_fields(self):
        from oompah.projects import ProjectStore

        assert "merge_queue_enabled" in ProjectStore.UPDATABLE_FIELDS

    def test_update_accepts_merge_queue_enabled(self, tmp_path):
        """ProjectStore.update does not raise when merge_queue_enabled is passed."""
        from oompah.projects import ProjectStore
        from oompah.models import Project

        store = ProjectStore(path=str(tmp_path / "projects.json"))
        # Directly inject a project (bypassing git clone)
        project = Project(
            id="proj-test",
            name="test",
            repo_url="https://github.com/org/repo",
            repo_path=str(tmp_path),
        )
        store._projects["proj-test"] = project
        store._save()

        updated = store.update("proj-test", merge_queue_enabled=True)
        assert updated is not None
        assert updated.merge_queue_enabled is True

    def test_update_unknown_field_raises(self, tmp_path):
        """Unknown fields still raise ProjectError as before."""
        from oompah.projects import ProjectStore, ProjectError
        from oompah.models import Project

        store = ProjectStore(path=str(tmp_path / "projects.json"))
        project = Project(
            id="proj-test",
            name="test",
            repo_url="https://github.com/org/repo",
            repo_path=str(tmp_path),
        )
        store._projects["proj-test"] = project
        store._save()

        with pytest.raises(ProjectError):
            store.update("proj-test", unknown_field=True)
