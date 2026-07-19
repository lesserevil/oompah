"""Route-level tests for _get_item_backlog_service factory wiring (OOMPAH-249).

These tests exercise the REAL ``_get_item_backlog_service`` server factory
(not a mocked substitute) to verify that:

1. The factory passes the project SCM provider and managed-repo slug to
   ``ItemBacklogService`` so the PR-commit fallback (OOMPAH-248) is reachable
   from the HTTP route.

2. When a Merged native task's work branch is absent (deleted after merge),
   GET /api/v1/projects/{project_id}/release-delivery/backlog returns the task
   as a ``not_selected`` primary item via the SCM fallback.

3. The SCM provider receives the canonical ``owner/repo`` slug and the task's
   persisted ``review_number``.

4. PR commits that are NOT reachable from the default branch remain absent even
   when the SCM fallback fires.

5. Cache lifecycle: changing a project's ``repo_url`` causes the factory to
   build a fresh service with the new SCM and managed_repo — the old entry
   (missing these dependencies) is not reused.

Coverage
--------
- test_factory_passes_scm_to_service: SCM set on constructed service
- test_factory_passes_managed_repo_to_service: managed_repo set on service
- test_factory_no_repo_url_sets_scm_none: no repo_url → scm=None, managed_repo=None
- test_factory_scm_detection_failure_sets_scm_none: detect_provider raises → graceful
- test_cache_keyed_by_repo_url: different repo_url → new service instance
- test_cache_same_project_same_url_returns_same_instance
- test_route_deleted_branch_pr_fallback_returns_not_selected_item: primary regression
- test_route_scm_receives_correct_owner_repo_and_review_number: SCM args
- test_route_pr_commits_not_reachable_from_main_excluded: negative case
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Project
from oompah.release_delivery_backlog import (
    BacklogResult,
    ItemBacklogService,
)
from oompah.release_delivery_inventory import ReleaseStatusCell

# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------

_RELEASE_BRANCH = "release/0.11"
_SOURCE_HEAD = "s" * 40
_RELEASE_HEAD = "r" * 40
_PR_SHA = "ab" * 20          # 40-hex SHA present in main commits
_FOREIGN_SHA = "cd" * 20     # 40-hex SHA NOT in main commits (unreachable)
_REVIEW_NUMBER = "445"
_OWNER = "org"
_REPO = "trickle"
_REPO_URL = f"https://github.com/{_OWNER}/{_REPO}"
_MANAGED_REPO = f"{_OWNER}/{_REPO}"
_PROJECT_ID = "proj-factory-test"
_TASK_ID = "TASK-100"

_ENDPOINT = f"/api/v1/projects/{_PROJECT_ID}/release-delivery/backlog"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(
    tmp_path: Path,
    *,
    pid: str = _PROJECT_ID,
    repo_url: str | None = _REPO_URL,
    repo_path: str | None = None,
    supported_release_branches: list[str] | None = None,
) -> MagicMock:
    """Return a mock project with sensible defaults."""
    project = MagicMock(spec=Project)
    project.id = pid
    project.name = "Factory Test Project"
    project.default_branch = "main"
    project.repo_url = repo_url
    project.repo_path = repo_path if repo_path is not None else str(tmp_path)
    project.access_token = None
    project.supported_release_branches = (
        supported_release_branches
        if supported_release_branches is not None
        else [_RELEASE_BRANCH, "release/1.0"]
    )
    return project


def _make_orchestrator(project: MagicMock) -> MagicMock:
    """Return a mock orchestrator wired to the given project."""
    orch = MagicMock()
    orch.project_store.get = MagicMock(return_value=project)
    # Simulate no tracker configured — title enrichment is skipped.
    # OOMPAH-250: the route now calls _get_tracker(orch, project_id) which
    # calls orch._tracker_for_project; raising ensures tracker=None in the handler.
    orch._tracker_for_project.side_effect = Exception("no tracker configured")
    return orch


def _mock_snapshot(
    *,
    source_head: str = _SOURCE_HEAD,
    release_head: str = _RELEASE_HEAD,
    stale: bool = False,
) -> MagicMock:
    snap = MagicMock()
    snap.source_head = source_head
    snap.release_heads = {_RELEASE_BRANCH: release_head}
    snap.stale = stale
    snap.fetched_at = time.monotonic()
    return snap


def _make_commit_info(sha: str, subject: str = "feat: something") -> MagicMock:
    ci = MagicMock()
    ci.sha = sha
    ci.subject = subject
    ci.author_name = "Dev"
    ci.authored_at = "2026-07-01T00:00:00Z"
    ci.is_merge = False
    ci.parents = []
    return ci


def _make_merged_issue(
    identifier: str = _TASK_ID,
    *,
    work_branch: str | None = None,
    review_number: str | None = _REVIEW_NUMBER,
    issue_type: str = "task",
) -> MagicMock:
    """Return a mock Merged tracker issue with optional review_number."""
    issue = MagicMock()
    issue.identifier = identifier
    issue.work_branch = work_branch     # None = deleted branch
    issue.review_number = review_number
    issue.issue_type = issue_type
    issue.state = "Merged"
    issue.title = f"Title for {identifier}"
    return issue


def _make_store_mock(deliveries: list | None = None) -> MagicMock:
    """Return a mock ReleaseDeliveryStore with an empty (or specified) ledger."""
    store = MagicMock()
    ledger = MagicMock()
    ledger.deliveries = deliveries or []
    store.read_ledger.return_value = ledger
    return store


# ---------------------------------------------------------------------------
# Fixture: clear the module-level service cache before every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_backlog_service_cache():
    """Wipe the server-module service cache before and after each test.

    The cache persists across the test session when it is not cleared, which
    can cause a test that uses ``test_project_id_A`` to return a stale service
    created by a previous test that also used ``test_project_id_A``.
    """
    server_module._item_backlog_services.clear()
    yield
    server_module._item_backlog_services.clear()


# ---------------------------------------------------------------------------
# Unit tests: _get_item_backlog_service factory
# ---------------------------------------------------------------------------

class TestGetItemBacklogServiceFactory:
    """Unit tests for the _get_item_backlog_service factory function.

    These call the factory directly (without an HTTP client) to verify the
    ItemBacklogService is constructed with the correct scm and managed_repo.
    """

    def test_factory_passes_scm_to_service(self, tmp_path):
        """Factory sets _scm on the constructed service from detect_provider."""
        project = _make_project(tmp_path)
        fake_scm = MagicMock()

        with (
            patch("oompah.server.detect_provider", return_value=fake_scm) as mock_detect,
            patch("oompah.server.extract_repo_slug", return_value=_MANAGED_REPO),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_store_mock(),
            ),
        ):
            svc = server_module._get_item_backlog_service(project)

        assert isinstance(svc, ItemBacklogService)
        assert svc._scm is fake_scm, (
            "ItemBacklogService._scm must be the provider returned by detect_provider; "
            "without it the PR-commit fallback (OOMPAH-248) cannot fire in production."
        )
        mock_detect.assert_called_once_with(
            _REPO_URL,
            access_token=None,
        )

    def test_factory_passes_managed_repo_to_service(self, tmp_path):
        """Factory sets _managed_repo on the service from extract_repo_slug."""
        project = _make_project(tmp_path)

        with (
            patch("oompah.server.detect_provider", return_value=MagicMock()),
            patch("oompah.server.extract_repo_slug", return_value=_MANAGED_REPO),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_store_mock(),
            ),
        ):
            svc = server_module._get_item_backlog_service(project)

        assert svc._managed_repo == _MANAGED_REPO, (
            f"ItemBacklogService._managed_repo must equal {_MANAGED_REPO!r}; "
            "without it the SCM fallback cannot request the correct repository."
        )

    def test_factory_no_repo_url_sets_scm_none(self, tmp_path):
        """Factory gracefully skips SCM detection when project has no repo_url."""
        project = _make_project(tmp_path, repo_url=None)

        with (
            patch("oompah.server.detect_provider") as mock_detect,
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_store_mock(),
            ),
        ):
            svc = server_module._get_item_backlog_service(project)

        mock_detect.assert_not_called()
        assert svc._scm is None
        assert svc._managed_repo is None

    def test_factory_scm_detection_failure_sets_scm_none(self, tmp_path):
        """SCM detection failure is caught; service is still constructed with scm=None."""
        project = _make_project(tmp_path)

        with (
            patch(
                "oompah.server.detect_provider",
                side_effect=ValueError("unsupported SCM host"),
            ),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_store_mock(),
            ),
        ):
            svc = server_module._get_item_backlog_service(project)

        # Service was created despite the detection failure
        assert isinstance(svc, ItemBacklogService)
        assert svc._scm is None, (
            "SCM detection failure must produce scm=None, not propagate the exception."
        )
        assert svc._managed_repo is None

    def test_cache_same_project_same_url_returns_same_instance(self, tmp_path):
        """Two calls with the same project_id + repo_url return the same service object."""
        project = _make_project(tmp_path)

        with (
            patch("oompah.server.detect_provider", return_value=MagicMock()),
            patch("oompah.server.extract_repo_slug", return_value=_MANAGED_REPO),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_store_mock(),
            ) as mock_make_store,
        ):
            svc1 = server_module._get_item_backlog_service(project)
            svc2 = server_module._get_item_backlog_service(project)

        assert svc1 is svc2, "Same project + same repo_url must return the cached instance."
        # make_delivery_store should only have been called once
        assert mock_make_store.call_count == 1

    def test_cache_keyed_by_repo_url_different_url_builds_new_service(self, tmp_path):
        """Changing repo_url (i.e. different SCM) produces a new service instance.

        This guards against the scenario where a project's repo_url is updated
        (e.g. migrated to a different host) while the service is running — the
        stale cached instance would have the wrong scm/managed_repo.
        """
        project_v1 = _make_project(tmp_path, repo_url="https://github.com/org/repo-v1")
        project_v2 = _make_project(tmp_path, repo_url="https://github.com/org/repo-v2")

        fake_scm_v1 = MagicMock(name="scm_v1")
        fake_scm_v2 = MagicMock(name="scm_v2")

        def _detect_side_effect(url, *, access_token=None):
            if "v1" in url:
                return fake_scm_v1
            return fake_scm_v2

        with (
            patch("oompah.server.detect_provider", side_effect=_detect_side_effect),
            patch("oompah.server.extract_repo_slug", return_value="org/repo"),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_store_mock(),
            ),
        ):
            svc_v1 = server_module._get_item_backlog_service(project_v1)
            svc_v2 = server_module._get_item_backlog_service(project_v2)

        assert svc_v1 is not svc_v2, (
            "Different repo_urls must produce distinct service instances so that "
            "the SCM provider update is picked up without a restart."
        )
        assert svc_v1._scm is fake_scm_v1
        assert svc_v2._scm is fake_scm_v2


# ---------------------------------------------------------------------------
# Route-level tests: the HTTP endpoint uses the real factory
# ---------------------------------------------------------------------------

class TestRouteDeletedBranchPRFallback:
    """API regression: PR fallback fires through the real server factory.

    These tests send an HTTP request to the real FastAPI route WITHOUT mocking
    ``_get_item_backlog_service``.  The factory is allowed to build a real
    ``ItemBacklogService`` (with a mocked SCM provider), and the underlying
    git helpers are patched to avoid filesystem access.

    This validates OOMPAH-249: the production wiring (factory → service → PR
    fallback) is exercised end-to-end, not just the service class in isolation.
    """

    def _build_route_patches(
        self,
        tmp_path: Path,
        *,
        scm: MagicMock,
        commits: list[Any],
        tracker_issues: list[Any],
        ancestry_shas: set[str] | None = None,
        branch_commits_map: dict[str, list[str]] | None = None,
    ):
        """Return a context-manager stack with all external dependencies mocked."""
        from contextlib import ExitStack

        stack = ExitStack()

        snapshot = _mock_snapshot()

        def _mock_find_branch(repo_path, work_branch, main_shas, *, timeout=60):
            if branch_commits_map is None:
                return []
            return branch_commits_map.get(work_branch, [])

        # Patch git-level helpers inside the backlog module
        stack.enter_context(patch(
            "oompah.release_delivery_backlog._acquire_snapshot",
            return_value=snapshot,
        ))
        stack.enter_context(patch(
            "oompah.release_delivery_backlog._enumerate_commits",
            return_value=commits,
        ))
        stack.enter_context(patch(
            "oompah.release_delivery_backlog._check_ancestry_batch",
            return_value=ancestry_shas or set(),
        ))
        stack.enter_context(patch(
            "oompah.release_delivery_backlog._is_tracker_only_commit",
            return_value=False,
        ))
        stack.enter_context(patch(
            "oompah.release_delivery_backlog._find_branch_commits_in_main",
            side_effect=_mock_find_branch,
        ))

        # Patch SCM detection inside the server module factory
        stack.enter_context(patch(
            "oompah.server.detect_provider",
            return_value=scm,
        ))
        stack.enter_context(patch(
            "oompah.server.extract_repo_slug",
            return_value=_MANAGED_REPO,
        ))

        # Patch delivery store so no filesystem access is needed
        mock_store = _make_store_mock()
        stack.enter_context(patch(
            "oompah.release_delivery_compat.make_delivery_store",
            return_value=mock_store,
        ))

        # Wire tracker issues into orchestrator.tracker
        mock_tracker = MagicMock()
        mock_tracker.fetch_issues_by_states.return_value = tracker_issues
        mock_tracker.get_issue.return_value = None

        return stack, mock_tracker

    def test_route_deleted_branch_pr_fallback_returns_not_selected_item(self, tmp_path):
        """Primary API regression (OOMPAH-249): deleted branch + SCM fallback → item in backlog.

        BEFORE the factory fix: _get_item_backlog_service created ItemBacklogService
        without scm or managed_repo, so the PR fallback in OOMPAH-248 could never fire
        and items=0 was returned for all tasks whose branches had been cleaned up.

        AFTER the factory fix: the service receives the SCM provider, the fallback fires,
        and the item appears as not_selected (queueable).
        """
        ci = _make_commit_info(_PR_SHA, "feat: TASK-100 implement the feature")
        issue = _make_merged_issue(
            _TASK_ID,
            work_branch=None,         # Branch deleted after PR merge
            review_number=_REVIEW_NUMBER,
        )

        scm = MagicMock()
        scm.get_pr_commits.return_value = [_PR_SHA]

        project = _make_project(tmp_path, repo_url=_REPO_URL)
        orch = _make_orchestrator(project)

        stack, mock_tracker = self._build_route_patches(
            tmp_path,
            scm=scm,
            commits=[ci],
            tracker_issues=[issue],
            branch_commits_map={},  # All branches deleted → empty map
        )
        # OOMPAH-250: route now resolves tracker via _get_tracker(orch, project_id)
        # which calls orch._tracker_for_project; wire mock_tracker here.
        orch._tracker_for_project.side_effect = None
        orch._tracker_for_project.return_value = mock_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            stack,
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        assert len(data["items"]) == 1, (
            f"Expected 1 primary item (TASK-100), got {len(data['items'])}. "
            "The SCM PR fallback must fire through the real server factory. "
            "Before OOMPAH-249 this returned items=0 because scm was not wired."
        )
        item = data["items"][0]
        assert item["identifier"] == _TASK_ID
        assert item["delivery_status"]["state"] == "not_selected", (
            "An item with no delivery ledger entry must be not_selected (queueable)."
        )
        assert len(item["source_commits"]) == 1
        assert item["source_commits"][0]["sha"] == _PR_SHA

    def test_route_scm_receives_correct_owner_repo_and_review_number(self, tmp_path):
        """SCM provider is called with the project owner/repo and task review_number.

        The factory must derive the managed_repo slug from project.repo_url and
        forward it to ItemBacklogService, which passes it through to the SCM.
        """
        ci = _make_commit_info(_PR_SHA, "feat: TASK-100")
        issue = _make_merged_issue(
            _TASK_ID,
            work_branch=None,
            review_number=_REVIEW_NUMBER,
        )

        scm = MagicMock()
        scm.get_pr_commits.return_value = [_PR_SHA]

        project = _make_project(tmp_path, repo_url=_REPO_URL)
        orch = _make_orchestrator(project)

        stack, mock_tracker = self._build_route_patches(
            tmp_path,
            scm=scm,
            commits=[ci],
            tracker_issues=[issue],
        )
        # OOMPAH-250: route resolves tracker via orch._tracker_for_project
        orch._tracker_for_project.side_effect = None
        orch._tracker_for_project.return_value = mock_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            stack,
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200

        # The SCM provider must have been called exactly once with the correct args
        scm.get_pr_commits.assert_called_once_with(_MANAGED_REPO, _REVIEW_NUMBER), (
            f"SCM.get_pr_commits must receive ({_MANAGED_REPO!r}, {_REVIEW_NUMBER!r}). "
            "This confirms the factory correctly passed owner/repo to the service."
        )

    def test_route_pr_commits_not_reachable_from_main_excluded(self, tmp_path):
        """Negative case: PR commits not in main sha_set are excluded from the backlog.

        Even when the SCM returns commits, only those present in the default-branch
        enumeration (sha_set) count as merge evidence.  A foreign SHA must NOT
        produce an item row.
        """
        ci = _make_commit_info(_PR_SHA, "feat: some other commit that IS in main")
        issue = _make_merged_issue(
            _TASK_ID,
            work_branch=None,
            review_number=_REVIEW_NUMBER,
        )

        scm = MagicMock()
        # SCM returns a SHA that is NOT in the enumerated main commits
        scm.get_pr_commits.return_value = [_FOREIGN_SHA]

        project = _make_project(tmp_path, repo_url=_REPO_URL)
        orch = _make_orchestrator(project)

        stack, mock_tracker = self._build_route_patches(
            tmp_path,
            scm=scm,
            commits=[ci],           # Only _PR_SHA is in main; _FOREIGN_SHA is absent
            tracker_issues=[issue],
        )
        # OOMPAH-250: route resolves tracker via orch._tracker_for_project
        orch._tracker_for_project.side_effect = None
        orch._tracker_for_project.return_value = mock_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            stack,
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()

        assert len(data["items"]) == 0, (
            "A task whose PR commits are not reachable from origin/main must NOT "
            "appear in the backlog. The SHA returned by the SCM (_FOREIGN_SHA) is "
            "absent from the enumerated main commits — no merge evidence exists."
        )
        # The unreachable commit must also not appear as an item
        item_ids = [row["identifier"] for row in data["items"]]
        assert _TASK_ID not in item_ids

    def test_route_no_scm_no_review_number_item_excluded(self, tmp_path):
        """When a Merged task has no review_number and no live branch, it is excluded.

        Without either durable merge evidence (review_number) or a live branch ref,
        the service cannot determine that the task's commits reached main.
        """
        ci = _make_commit_info(_PR_SHA, "feat: TASK-100")
        issue = _make_merged_issue(
            _TASK_ID,
            work_branch=None,
            review_number=None,         # No review_number persisted
        )

        scm = MagicMock()

        project = _make_project(tmp_path, repo_url=_REPO_URL)
        orch = _make_orchestrator(project)

        stack, mock_tracker = self._build_route_patches(
            tmp_path,
            scm=scm,
            commits=[ci],
            tracker_issues=[issue],
        )
        # OOMPAH-250: route resolves tracker via orch._tracker_for_project
        orch._tracker_for_project.side_effect = None
        orch._tracker_for_project.return_value = mock_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            stack,
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()

        assert len(data["items"]) == 0, (
            "Task with no work_branch and no review_number has no merge evidence; "
            "must be excluded from the backlog."
        )
        # SCM must not have been consulted (no review_number to look up)
        scm.get_pr_commits.assert_not_called()


# ---------------------------------------------------------------------------
# Cache initialization test
# ---------------------------------------------------------------------------

class TestFactoryCacheInitialization:
    """Verify that the factory-configured SCM and managed_repo reach the route service.

    This is the 'initialization' acceptance criterion from OOMPAH-249: prove
    that the service used by the route has the correct scm and managed_repo
    rather than the old None-valued defaults.
    """

    def test_service_in_cache_has_scm_and_managed_repo_after_first_request(self, tmp_path):
        """After the first GET request the cached service holds the correct SCM.

        Simulates the full request cycle via the HTTP route, then inspects the
        module-level cache to confirm the cached entry has a non-None scm and
        the correct managed_repo slug.
        """
        from oompah.release_delivery_backlog import BacklogResult

        ci = _make_commit_info(_PR_SHA, "feat: anything")
        project = _make_project(tmp_path, pid=_PROJECT_ID, repo_url=_REPO_URL)
        orch = _make_orchestrator(project)

        fake_scm = MagicMock()
        fake_scm.get_pr_commits.return_value = []

        empty_backlog = BacklogResult(
            project_id=_PROJECT_ID,
            source_branch="main",
            source_head=_SOURCE_HEAD,
            selected_branch=_RELEASE_BRANCH,
            branch_head=_RELEASE_HEAD,
            branch_available=True,
            items=[],
            unassociated_commits=[],
            stale=False,
            refreshed_at="2026-07-01T00:00:00+00:00",
            total_commit_count=0,
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server.detect_provider", return_value=fake_scm),
            patch("oompah.server.extract_repo_slug", return_value=_MANAGED_REPO),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_store_mock(),
            ),
            patch(
                "oompah.release_delivery_backlog._acquire_snapshot",
                return_value=_mock_snapshot(),
            ),
            patch("oompah.release_delivery_backlog._enumerate_commits", return_value=[]),
            patch("oompah.release_delivery_backlog._check_ancestry_batch", return_value=set()),
            patch("oompah.release_delivery_backlog._is_tracker_only_commit", return_value=False),
            patch("oompah.release_delivery_backlog._find_branch_commits_in_main", return_value=[]),
        ):
            client = TestClient(app)
            resp = client.get(f"{_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200

        # After the request the service is in the cache
        cache_key = (_PROJECT_ID, _REPO_URL)
        assert cache_key in server_module._item_backlog_services, (
            f"Expected cache key {cache_key!r} to exist after the first request. "
            "Cache is keyed by (project_id, repo_url) — both must appear."
        )
        cached_svc = server_module._item_backlog_services[cache_key]
        assert isinstance(cached_svc, ItemBacklogService)
        assert cached_svc._scm is fake_scm, (
            "Cached service must have the SCM provider set. "
            "If _scm is None, the PR-commit fallback cannot fire."
        )
        assert cached_svc._managed_repo == _MANAGED_REPO, (
            f"Cached service must have managed_repo={_MANAGED_REPO!r}. "
            "If _managed_repo is None, the SCM call uses the wrong repository slug."
        )

    def test_old_cache_entry_without_scm_is_replaced_when_repo_url_differs(self, tmp_path):
        """Manually insert a stale (no-SCM) entry; assert a new repo_url evicts it.

        Simulates the scenario where an existing deployment cached a service
        without scm (pre-OOMPAH-249 code) and the project's repo_url is updated.
        The cache key change causes the new factory call to create a fresh service.
        """
        old_url = "https://github.com/org/old-repo"
        new_url = "https://github.com/org/new-repo"

        project_old = _make_project(tmp_path, repo_url=old_url)
        project_new = _make_project(tmp_path, repo_url=new_url)

        # Manually inject an old-style cache entry without scm (simulates pre-249 cache)
        from oompah.release_delivery_backlog import ItemBacklogService
        old_svc = ItemBacklogService(
            project_root=tmp_path,
            project_id=_PROJECT_ID,
            default_branch="main",
            delivery_store=_make_store_mock(),
            scm=None,
            managed_repo=None,
        )
        server_module._item_backlog_services[(_PROJECT_ID, old_url)] = old_svc

        fake_scm = MagicMock()
        with (
            patch("oompah.server.detect_provider", return_value=fake_scm),
            patch("oompah.server.extract_repo_slug", return_value="org/new-repo"),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_store_mock(),
            ),
        ):
            new_svc = server_module._get_item_backlog_service(project_new)

        # Must be a new instance, not the old one
        assert new_svc is not old_svc, (
            "A different repo_url must produce a new service instance, not return the "
            "old (pre-OOMPAH-249) entry that is missing scm and managed_repo."
        )
        assert new_svc._scm is fake_scm
        assert new_svc._managed_repo == "org/new-repo"

        # Old entry must still be in the cache under the old key (not evicted)
        assert server_module._item_backlog_services.get((_PROJECT_ID, old_url)) is old_svc
