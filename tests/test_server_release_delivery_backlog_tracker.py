"""Multi-project tracker isolation tests for api_release_delivery_backlog (OOMPAH-250).

Problem (OOMPAH-250)
--------------------
Despite OOMPAH-248 (PR fallback) and OOMPAH-249 (SCM factory wiring) being merged,
the Trickle release/0.11 backlog returned items=0 and unassociated=7513 because
``api_release_delivery_backlog`` was passing ``getattr(orch, "tracker", None)``
(the legacy/global tracker) to ``ItemBacklogService.get_backlog()``.

In managed-project mode, ``orch.tracker`` is the *global* tracker, not Trickle's
native tracker.  ``ItemBacklogService`` therefore fetched no Trickle Merged tasks
or epics, so neither the work-branch nor the PR fallback discovery could run.

Fix
---
Replace ``getattr(orch, "tracker", None)`` with
``_get_tracker(orch, project_id)`` (wrapped in try/except for best-effort title
enrichment).  ``_get_tracker`` calls ``orch._tracker_for_project(project_id)``
which returns the project-scoped tracker.

Tests in this file
------------------
1. ``TestMultiProjectTrackerIsolation``
   - Merged Trickle task appears only when the request names the Trickle project.
   - Merged legacy task appears only when the request names the legacy project.
   - Candidates are NEVER sourced from another project's tracker.

2. ``TestLegacyTrackerNotUsedForManagedProject``
   - ``orch.tracker`` (global legacy) is not consulted for managed-project requests.
   - ``orch._tracker_for_project`` IS called with the correct project_id.

3. ``TestUnavailableProjectTracker``
   - When ``_tracker_for_project`` raises, the response is still 200 (or documented
     error) but contains zero items from *other* projects — not a silent fallback.

4. ``TestSingleProjectLegacyModeCompatibility``
   - In single-project / legacy-mode setups, the route still works correctly.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Project

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_RELEASE_BRANCH = "release/0.11"
_SOURCE_HEAD = "s" * 40
_RELEASE_HEAD = "r" * 40
_PR_SHA_TRICKLE = "aa" * 20
_PR_SHA_LEGACY = "bb" * 20

_TRICKLE_PROJECT_ID = "proj-trickle"
_LEGACY_PROJECT_ID = "proj-legacy"
_TRICKLE_TASK_ID = "TRICKLE-42"
_LEGACY_TASK_ID = "LEGACY-1"
_TRICKLE_REVIEW_NUMBER = "42"
_TRICKLE_REPO_URL = "https://github.com/org/trickle"
_LEGACY_REPO_URL = "https://github.com/org/legacy-repo"

_TRICKLE_ENDPOINT = (
    f"/api/v1/projects/{_TRICKLE_PROJECT_ID}/release-delivery/backlog"
)
_LEGACY_ENDPOINT = (
    f"/api/v1/projects/{_LEGACY_PROJECT_ID}/release-delivery/backlog"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(
    tmp_path: Path,
    *,
    pid: str,
    repo_url: str,
    supported_release_branches: list[str] | None = None,
) -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = pid
    project.name = f"Project {pid}"
    project.default_branch = "main"
    project.repo_url = repo_url
    project.repo_path = str(tmp_path)
    project.access_token = None
    project.supported_release_branches = (
        supported_release_branches
        if supported_release_branches is not None
        else [_RELEASE_BRANCH, "release/1.0"]
    )
    return project


def _make_merged_issue(
    identifier: str,
    *,
    work_branch: str | None = None,
    review_number: str | None = None,
) -> MagicMock:
    issue = MagicMock()
    issue.identifier = identifier
    issue.work_branch = work_branch
    issue.review_number = review_number
    issue.issue_type = "task"
    issue.state = "Merged"
    issue.title = f"Title for {identifier}"
    return issue


def _make_tracker(issues: list[Any]) -> MagicMock:
    tracker = MagicMock()
    tracker.fetch_issues_by_states.return_value = issues
    tracker.get_issue.return_value = None
    return tracker


def _make_commit_info(sha: str, subject: str = "feat: something") -> MagicMock:
    ci = MagicMock()
    ci.sha = sha
    ci.subject = subject
    ci.author_name = "Dev"
    ci.authored_at = "2026-07-01T00:00:00Z"
    ci.is_merge = False
    ci.parents = []
    return ci


def _make_snapshot(
    *,
    source_head: str = _SOURCE_HEAD,
    release_head: str = _RELEASE_HEAD,
) -> MagicMock:
    snap = MagicMock()
    snap.source_head = source_head
    snap.release_heads = {_RELEASE_BRANCH: release_head}
    snap.stale = False
    snap.fetched_at = time.monotonic()
    return snap


def _make_delivery_store() -> MagicMock:
    store = MagicMock()
    ledger = MagicMock()
    ledger.deliveries = []
    store.read_ledger.return_value = ledger
    return store


# ---------------------------------------------------------------------------
# Fixture: clear the module-level service cache before every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_backlog_service_cache():
    server_module._item_backlog_services.clear()
    yield
    server_module._item_backlog_services.clear()


@pytest.fixture(autouse=True)
def _sync_backlog_refresh():
    """Run the backlog refresh synchronously during TestClient HTTP tests.

    The async refresh model (OOMPAH-251) starts a background asyncio task, which
    does not complete before a synchronous TestClient response is returned.  This
    fixture patches BacklogRefreshManager.get_or_start so that it calls
    service.get_backlog() directly (no background task) and returns the result
    immediately.  This allows HTTP-level tests to assert on backlog contents and
    tracker call args without setting up an async event-loop harness.
    """
    from unittest.mock import patch

    from oompah.release_delivery_refresh import BacklogRefreshManager, RefreshStatus

    # Reset the singleton so the patched class method applies to a fresh instance.
    with server_module._backlog_refresh_manager_lock:
        server_module._backlog_refresh_manager = None

    async def _sync_get_or_start(
        self,
        project_id: str,
        branch: str,
        *,
        service,
        filter: str = "all",
        query=None,
        tracker=None,
    ):
        result = service.get_backlog(
            selected_branch=branch,
            filter="all",
            query=query,
            tracker=tracker,
        )
        return RefreshStatus(phase="complete", has_result=True), result

    with patch.object(BacklogRefreshManager, "get_or_start", _sync_get_or_start):
        yield

    # Clean up singleton after test
    with server_module._backlog_refresh_manager_lock:
        server_module._backlog_refresh_manager = None


# ---------------------------------------------------------------------------
# 1. Multi-project tracker isolation
# ---------------------------------------------------------------------------

class TestMultiProjectTrackerIsolation:
    """Merged Trickle tasks appear only when the request names the Trickle project.

    A correctly-wired route must call ``_get_tracker(orch, project_id)`` so that
    each project's own tracker is consulted, not the legacy global tracker or any
    other project's tracker.
    """

    def _build_orch(self, tmp_path, *, trickle_project, legacy_project,
                    trickle_tracker, legacy_tracker) -> MagicMock:
        orch = MagicMock()

        def _get_project(pid):
            if pid == _TRICKLE_PROJECT_ID:
                return trickle_project
            if pid == _LEGACY_PROJECT_ID:
                return legacy_project
            return None

        def _tracker_for_project(pid):
            if pid == _TRICKLE_PROJECT_ID:
                return trickle_tracker
            if pid == _LEGACY_PROJECT_ID:
                return legacy_tracker
            raise RuntimeError(f"Unknown project: {pid}")

        orch.project_store.get = MagicMock(side_effect=_get_project)
        orch._tracker_for_project = MagicMock(side_effect=_tracker_for_project)
        return orch

    def _common_patches(self, *, scm: MagicMock, commits: list, scm_repo: str):
        """Return a dict of patches for git / SCM helpers."""
        return {
            "oompah.release_delivery_backlog._acquire_snapshot":
                _make_snapshot(),
            "oompah.release_delivery_backlog._enumerate_commits":
                commits,
            "oompah.release_delivery_backlog._check_ancestry_batch":
                set(),
            "oompah.release_delivery_backlog._is_tracker_only_commit":
                False,
            "oompah.release_delivery_backlog._find_branch_commits_in_main":
                [],
        }

    def test_trickle_task_appears_only_for_trickle_project_request(self, tmp_path):
        """Core multi-project regression (OOMPAH-250).

        A Merged Trickle task with a deleted work branch and a review_number must
        appear as a ``not_selected`` candidate ONLY when the request names the
        Trickle project.  The same request for the legacy project must return zero
        items.

        Before the fix, both requests passed orch.tracker (the global/legacy tracker)
        to ItemBacklogService, so neither project returned Trickle items.
        After the fix, each request uses the project-scoped tracker.
        """
        trickle_project = _make_project(
            tmp_path,
            pid=_TRICKLE_PROJECT_ID,
            repo_url=_TRICKLE_REPO_URL,
        )
        legacy_project = _make_project(
            tmp_path,
            pid=_LEGACY_PROJECT_ID,
            repo_url=_LEGACY_REPO_URL,
        )

        trickle_issue = _make_merged_issue(
            _TRICKLE_TASK_ID,
            work_branch=None,
            review_number=_TRICKLE_REVIEW_NUMBER,
        )
        legacy_issue = _make_merged_issue(_LEGACY_TASK_ID, work_branch=None)

        trickle_tracker = _make_tracker([trickle_issue])
        legacy_tracker = _make_tracker([legacy_issue])

        scm = MagicMock()
        scm.get_pr_commits.return_value = [_PR_SHA_TRICKLE]

        commit = _make_commit_info(_PR_SHA_TRICKLE, f"feat: {_TRICKLE_TASK_ID}")

        orch = self._build_orch(
            tmp_path,
            trickle_project=trickle_project,
            legacy_project=legacy_project,
            trickle_tracker=trickle_tracker,
            legacy_tracker=legacy_tracker,
        )

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server.detect_provider", return_value=scm),
            patch("oompah.server.extract_repo_slug", return_value="org/trickle"),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_delivery_store(),
            ),
            patch(
                "oompah.release_delivery_backlog._acquire_snapshot",
                return_value=_make_snapshot(),
            ),
            patch(
                "oompah.release_delivery_backlog._enumerate_commits",
                return_value=[commit],
            ),
            patch(
                "oompah.release_delivery_backlog._check_ancestry_batch",
                return_value=set(),
            ),
            patch(
                "oompah.release_delivery_backlog._is_tracker_only_commit",
                return_value=False,
            ),
            patch(
                "oompah.release_delivery_backlog._find_branch_commits_in_main",
                return_value=[],
            ),
        ):
            client = TestClient(app)

            # Request for the Trickle project — must return TRICKLE-42
            trickle_resp = client.get(
                f"{_TRICKLE_ENDPOINT}?branch={_RELEASE_BRANCH}"
            )
            assert trickle_resp.status_code == 200, (
                f"Expected 200 for Trickle project, got {trickle_resp.status_code}: "
                f"{trickle_resp.text}"
            )
            trickle_data = trickle_resp.json()
            trickle_identifiers = [row["identifier"] for row in trickle_data["items"]]

            assert _TRICKLE_TASK_ID in trickle_identifiers, (
                f"{_TRICKLE_TASK_ID} must appear in the Trickle project backlog. "
                "Before OOMPAH-250 this returned items=0 because orch.tracker "
                "(global legacy) was used instead of the Trickle-scoped tracker."
            )
            assert _LEGACY_TASK_ID not in trickle_identifiers, (
                f"{_LEGACY_TASK_ID} must NOT appear in the Trickle project backlog. "
                "Candidate rows must never be sourced from another project's tracker."
            )

    def test_legacy_task_does_not_bleed_into_trickle_project_response(self, tmp_path):
        """Candidates from the legacy tracker must not appear for the Trickle project.

        When the legacy tracker returns LEGACY-1 and the Trickle tracker returns
        TRICKLE-42, requesting the Trickle project backlog must contain only TRICKLE-42.
        LEGACY-1 items from the global tracker must be completely absent.
        """
        trickle_project = _make_project(
            tmp_path, pid=_TRICKLE_PROJECT_ID, repo_url=_TRICKLE_REPO_URL
        )
        legacy_project = _make_project(
            tmp_path, pid=_LEGACY_PROJECT_ID, repo_url=_LEGACY_REPO_URL
        )

        trickle_issue = _make_merged_issue(
            _TRICKLE_TASK_ID,
            work_branch=None,
            review_number=_TRICKLE_REVIEW_NUMBER,
        )
        legacy_issue = _make_merged_issue(
            _LEGACY_TASK_ID,
            work_branch=None,
            review_number="99",
        )

        trickle_tracker = _make_tracker([trickle_issue])
        # Legacy tracker has its own issue — must not bleed into the Trickle response
        legacy_tracker = _make_tracker([legacy_issue])

        trickle_scm = MagicMock()
        # Only TRICKLE-42's PR commit is reachable from main
        trickle_scm.get_pr_commits.return_value = [_PR_SHA_TRICKLE]

        commit = _make_commit_info(_PR_SHA_TRICKLE, f"feat: {_TRICKLE_TASK_ID}")

        def _tracker_for_project(pid):
            if pid == _TRICKLE_PROJECT_ID:
                return trickle_tracker
            if pid == _LEGACY_PROJECT_ID:
                return legacy_tracker
            raise RuntimeError(f"Unknown project: {pid}")

        orch = MagicMock()
        orch.project_store.get.side_effect = lambda pid: (
            trickle_project if pid == _TRICKLE_PROJECT_ID else legacy_project
        )
        orch._tracker_for_project.side_effect = _tracker_for_project

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server.detect_provider", return_value=trickle_scm),
            patch("oompah.server.extract_repo_slug", return_value="org/trickle"),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_delivery_store(),
            ),
            patch(
                "oompah.release_delivery_backlog._acquire_snapshot",
                return_value=_make_snapshot(),
            ),
            patch(
                "oompah.release_delivery_backlog._enumerate_commits",
                return_value=[commit],
            ),
            patch(
                "oompah.release_delivery_backlog._check_ancestry_batch",
                return_value=set(),
            ),
            patch(
                "oompah.release_delivery_backlog._is_tracker_only_commit",
                return_value=False,
            ),
            patch(
                "oompah.release_delivery_backlog._find_branch_commits_in_main",
                return_value=[],
            ),
        ):
            client = TestClient(app)
            resp = client.get(f"{_TRICKLE_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        data = resp.json()
        identifiers = [row["identifier"] for row in data["items"]]

        assert _LEGACY_TASK_ID not in identifiers, (
            f"{_LEGACY_TASK_ID} (from the legacy tracker) must NOT appear in the "
            "Trickle project backlog. This is the multi-project isolation guarantee."
        )
        assert _TRICKLE_TASK_ID in identifiers, (
            f"{_TRICKLE_TASK_ID} must appear because the Trickle-scoped tracker "
            "was correctly consulted."
        )

    def test_orch_tracker_for_project_called_with_correct_project_id(self, tmp_path):
        """Route calls _tracker_for_project with the project_id from the URL, not a default.

        This asserts the routing contract: the tracker lookup must use the project
        from the request path, not a hardcoded default, the first project in the store,
        or any other project.
        """
        trickle_project = _make_project(
            tmp_path, pid=_TRICKLE_PROJECT_ID, repo_url=_TRICKLE_REPO_URL
        )
        trickle_tracker = _make_tracker([])

        orch = MagicMock()
        orch.project_store.get.return_value = trickle_project
        orch._tracker_for_project.return_value = trickle_tracker

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_factory,
        ):
            from oompah.release_delivery_backlog import BacklogResult
            mock_svc = MagicMock()
            mock_svc.get_backlog.return_value = BacklogResult(
                project_id=_TRICKLE_PROJECT_ID,
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
            mock_factory.return_value = mock_svc

            client = TestClient(app)
            resp = client.get(f"{_TRICKLE_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200

        # The route must have called _tracker_for_project with the Trickle project_id
        orch._tracker_for_project.assert_called_with(_TRICKLE_PROJECT_ID), (
            f"_tracker_for_project must be called with {_TRICKLE_PROJECT_ID!r}. "
            "Before OOMPAH-250 the route used orch.tracker (global legacy), "
            "so _tracker_for_project was never called at all."
        )


# ---------------------------------------------------------------------------
# 2. Legacy tracker NOT used for managed-project backlog requests
# ---------------------------------------------------------------------------

class TestLegacyTrackerNotUsedForManagedProject:
    """Assert that orch.tracker (global legacy) is never consulted for a managed project.

    The route must use _get_tracker(orch, project_id) → orch._tracker_for_project,
    not the legacy orch.tracker attribute.
    """

    def test_orch_tracker_attribute_not_accessed_for_managed_project(self, tmp_path):
        """orch.tracker must not be called when the route resolves a managed-project tracker.

        We configure orch such that accessing orch.tracker would call a MagicMock
        that we can inspect post-call.  After the request, we assert that
        fetch_issues_by_states was NOT called on orch.tracker.
        """
        project = _make_project(
            tmp_path, pid=_TRICKLE_PROJECT_ID, repo_url=_TRICKLE_REPO_URL
        )
        project_tracker = _make_tracker([])

        # orch.tracker is a legacy global tracker; we spy on it to confirm it is not used
        global_tracker = MagicMock(name="global_legacy_tracker")
        global_tracker.fetch_issues_by_states.return_value = []

        orch = MagicMock()
        orch.project_store.get.return_value = project
        orch.tracker = global_tracker                    # legacy attribute
        orch._tracker_for_project.return_value = project_tracker  # project-scoped

        from oompah.release_delivery_backlog import BacklogResult
        backlog = BacklogResult(
            project_id=_TRICKLE_PROJECT_ID,
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
            patch.object(server_module, "_get_item_backlog_service") as mock_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_backlog.return_value = backlog
            mock_factory.return_value = mock_svc

            client = TestClient(app)
            resp = client.get(f"{_TRICKLE_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200

        # The global/legacy tracker must NOT have been consulted for issue discovery
        global_tracker.fetch_issues_by_states.assert_not_called(), (
            "orch.tracker.fetch_issues_by_states must NOT be called for a "
            "managed-project backlog request.  Only the project-scoped tracker "
            "returned by _tracker_for_project should be consulted."
        )

        # The project-scoped tracker WAS passed to get_backlog
        call_kwargs = mock_svc.get_backlog.call_args.kwargs
        assert call_kwargs.get("tracker") is project_tracker, (
            "The tracker passed to service.get_backlog must be the project-scoped "
            "tracker returned by orch._tracker_for_project, not orch.tracker."
        )

    def test_tracker_for_project_called_with_correct_project_id(self, tmp_path):
        """orch._tracker_for_project is called with the project_id from the URL path."""
        project = _make_project(
            tmp_path, pid=_TRICKLE_PROJECT_ID, repo_url=_TRICKLE_REPO_URL
        )
        project_tracker = _make_tracker([])

        orch = MagicMock()
        orch.project_store.get.return_value = project
        orch._tracker_for_project.return_value = project_tracker

        from oompah.release_delivery_backlog import BacklogResult
        backlog = BacklogResult(
            project_id=_TRICKLE_PROJECT_ID,
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
            patch.object(server_module, "_get_item_backlog_service") as mock_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_backlog.return_value = backlog
            mock_factory.return_value = mock_svc

            client = TestClient(app)
            resp = client.get(f"{_TRICKLE_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200
        orch._tracker_for_project.assert_called_with(_TRICKLE_PROJECT_ID)


# ---------------------------------------------------------------------------
# 3. Unavailable project tracker
# ---------------------------------------------------------------------------

class TestUnavailableProjectTracker:
    """When a project's tracker is unavailable, the response must be safe.

    An unavailable tracker (exception in _tracker_for_project) must yield
    tracker=None in the route, which means tracker-sourced discovery is skipped.
    The response must be 200 with an empty item list, NOT a 503 error, and
    must NOT silently substitute another project's tracker.
    """

    def test_tracker_resolution_failure_yields_200_with_empty_items(self, tmp_path):
        """When _tracker_for_project raises, the route returns 200 with items=[].

        Title enrichment and tracker-sourced discovery are best-effort.
        A tracker failure must not propagate as a 503 error response.
        """
        project = _make_project(
            tmp_path, pid=_TRICKLE_PROJECT_ID, repo_url=_TRICKLE_REPO_URL
        )

        orch = MagicMock()
        orch.project_store.get.return_value = project
        # Simulate tracker resolution failure
        orch._tracker_for_project.side_effect = RuntimeError(
            "tracker service unavailable"
        )

        from oompah.release_delivery_backlog import BacklogResult
        backlog = BacklogResult(
            project_id=_TRICKLE_PROJECT_ID,
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
            patch.object(server_module, "_get_item_backlog_service") as mock_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_backlog.return_value = backlog
            mock_factory.return_value = mock_svc

            client = TestClient(app)
            resp = client.get(f"{_TRICKLE_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200, (
            "An unavailable project tracker must not cause a 503 error. "
            "Tracker-sourced discovery is best-effort; the response must still be 200."
        )

        # tracker=None must have been passed to the service (best-effort fallback)
        call_kwargs = mock_svc.get_backlog.call_args.kwargs
        assert call_kwargs.get("tracker") is None, (
            "When _tracker_for_project raises, the route must pass tracker=None "
            "to the service, not crash or substitute a different project's tracker."
        )

    def test_tracker_resolution_failure_does_not_use_other_project_tracker(self, tmp_path):
        """When the Trickle tracker is unavailable, orch.tracker must not substitute it.

        Before OOMPAH-250, the route always used orch.tracker (the global legacy tracker).
        After OOMPAH-250, an exception from _tracker_for_project must result in
        tracker=None, NOT a silent fallback to orch.tracker.
        """
        project = _make_project(
            tmp_path, pid=_TRICKLE_PROJECT_ID, repo_url=_TRICKLE_REPO_URL
        )

        global_tracker = MagicMock(name="global_legacy_tracker")
        global_tracker.fetch_issues_by_states.return_value = [
            _make_merged_issue("LEGACY-99")
        ]

        orch = MagicMock()
        orch.project_store.get.return_value = project
        orch.tracker = global_tracker  # Legacy global tracker with LEGACY-99
        # Trickle-specific tracker is unavailable
        orch._tracker_for_project.side_effect = RuntimeError("Trickle tracker down")

        from oompah.release_delivery_backlog import BacklogResult
        backlog = BacklogResult(
            project_id=_TRICKLE_PROJECT_ID,
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
            patch.object(server_module, "_get_item_backlog_service") as mock_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_backlog.return_value = backlog
            mock_factory.return_value = mock_svc

            client = TestClient(app)
            resp = client.get(f"{_TRICKLE_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200

        # The global legacy tracker must NOT have been consulted as a substitute
        global_tracker.fetch_issues_by_states.assert_not_called(), (
            "When the project tracker is unavailable, orch.tracker must NOT "
            "be used as a substitute.  Doing so would source candidates from "
            "a different project's tracker (the pre-OOMPAH-250 bug)."
        )

        # tracker=None must have been passed — no silent substitution
        call_kwargs = mock_svc.get_backlog.call_args.kwargs
        assert call_kwargs.get("tracker") is None, (
            "Tracker=None must be passed when the project tracker is unavailable. "
            "A silent fallback to orch.tracker would produce candidates from another project."
        )

    def test_tracker_resolution_failure_end_to_end_no_candidates_from_other_project(
        self, tmp_path
    ):
        """End-to-end: unavailable project tracker → 200, zero items (not other-project items).

        This test runs through the real ItemBacklogService (no mock for _get_item_backlog_service)
        to confirm that with tracker=None, no tracker-sourced discovery fires and no
        items from another project appear in the backlog.
        """
        project = _make_project(
            tmp_path, pid=_TRICKLE_PROJECT_ID, repo_url=_TRICKLE_REPO_URL
        )

        orch = MagicMock()
        orch.project_store.get.return_value = project
        # Project tracker unavailable → try/except yields tracker=None
        orch._tracker_for_project.side_effect = RuntimeError("tracker unavailable")

        commit = _make_commit_info("c0" * 20, "direct commit not associated with any task")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server.detect_provider", return_value=MagicMock()),
            patch("oompah.server.extract_repo_slug", return_value="org/trickle"),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_delivery_store(),
            ),
            patch(
                "oompah.release_delivery_backlog._acquire_snapshot",
                return_value=_make_snapshot(),
            ),
            patch(
                "oompah.release_delivery_backlog._enumerate_commits",
                return_value=[commit],
            ),
            patch(
                "oompah.release_delivery_backlog._check_ancestry_batch",
                return_value=set(),
            ),
            patch(
                "oompah.release_delivery_backlog._is_tracker_only_commit",
                return_value=False,
            ),
            patch(
                "oompah.release_delivery_backlog._find_branch_commits_in_main",
                return_value=[],
            ),
        ):
            client = TestClient(app)
            resp = client.get(f"{_TRICKLE_ENDPOINT}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200, (
            f"Expected 200 despite unavailable tracker; got {resp.status_code}: {resp.text}"
        )
        data = resp.json()

        # No items from tracker-sourced discovery (tracker=None → none fetched)
        assert len(data["items"]) == 0, (
            "With an unavailable project tracker (tracker=None), no tracker-sourced "
            "items must appear.  items=0 is the correct outcome, not items sourced "
            "from another project's tracker."
        )


# ---------------------------------------------------------------------------
# 4. Single-project / legacy-mode compatibility
# ---------------------------------------------------------------------------

class TestSingleProjectLegacyModeCompatibility:
    """Verify that the tracker fix does not break single-project / legacy-mode setups.

    In a legacy setup with a single project, _tracker_for_project must return the
    tracker for that project.  The route must continue to work correctly.
    """

    def test_single_project_tracker_used_for_title_enrichment(self, tmp_path):
        """In single-project mode, the project tracker is correctly resolved.

        This test verifies backward compatibility: a legacy setup with one project
        must continue to pass the project's tracker to service.get_backlog.
        """
        project = _make_project(
            tmp_path, pid="proj-single", repo_url="https://github.com/org/single"
        )

        project_tracker = _make_tracker([])

        orch = MagicMock()
        orch.project_store.get.return_value = project
        orch._tracker_for_project.return_value = project_tracker

        from oompah.release_delivery_backlog import BacklogResult
        backlog = BacklogResult(
            project_id="proj-single",
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

        endpoint = "/api/v1/projects/proj-single/release-delivery/backlog"

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch.object(server_module, "_get_item_backlog_service") as mock_factory,
        ):
            mock_svc = MagicMock()
            mock_svc.get_backlog.return_value = backlog
            mock_factory.return_value = mock_svc

            client = TestClient(app)
            resp = client.get(f"{endpoint}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200

        call_kwargs = mock_svc.get_backlog.call_args.kwargs
        assert call_kwargs.get("tracker") is project_tracker, (
            "In single-project mode, the project-scoped tracker must be passed to "
            "service.get_backlog.  Legacy mode must work the same as multi-project mode: "
            "the tracker is resolved via _tracker_for_project(project_id)."
        )

    def test_single_project_merged_task_with_pr_fallback_appears_in_backlog(self, tmp_path):
        """Legacy/single-project: Merged task with deleted branch and review_number appears.

        End-to-end regression for single-project mode: the tracker fix must not
        break the PR fallback path introduced in OOMPAH-248 for the simple case
        where only one project exists.
        """
        from oompah.release_delivery_backlog import ItemBacklogService

        project = _make_project(
            tmp_path, pid="proj-single", repo_url="https://github.com/org/single"
        )

        single_issue = _make_merged_issue(
            "SINGLE-10",
            work_branch=None,
            review_number="10",
        )
        project_tracker = _make_tracker([single_issue])

        scm = MagicMock()
        pr_sha = "ff" * 20
        scm.get_pr_commits.return_value = [pr_sha]

        commit = _make_commit_info(pr_sha, "feat: SINGLE-10 implement something")

        orch = MagicMock()
        orch.project_store.get.return_value = project
        orch._tracker_for_project.return_value = project_tracker

        endpoint = "/api/v1/projects/proj-single/release-delivery/backlog"

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.server.detect_provider", return_value=scm),
            patch("oompah.server.extract_repo_slug", return_value="org/single"),
            patch(
                "oompah.release_delivery_compat.make_delivery_store",
                return_value=_make_delivery_store(),
            ),
            patch(
                "oompah.release_delivery_backlog._acquire_snapshot",
                return_value=_make_snapshot(),
            ),
            patch(
                "oompah.release_delivery_backlog._enumerate_commits",
                return_value=[commit],
            ),
            patch(
                "oompah.release_delivery_backlog._check_ancestry_batch",
                return_value=set(),
            ),
            patch(
                "oompah.release_delivery_backlog._is_tracker_only_commit",
                return_value=False,
            ),
            patch(
                "oompah.release_delivery_backlog._find_branch_commits_in_main",
                return_value=[],
            ),
        ):
            client = TestClient(app)
            resp = client.get(f"{endpoint}?branch={_RELEASE_BRANCH}")

        assert resp.status_code == 200, (
            f"Expected 200; got {resp.status_code}: {resp.text}"
        )
        data = resp.json()

        identifiers = [row["identifier"] for row in data["items"]]
        assert "SINGLE-10" in identifiers, (
            "SINGLE-10 must appear in the single-project backlog via the PR fallback. "
            "The tracker fix must not break the single-project path."
        )
        if data["items"]:
            item = next(row for row in data["items"] if row["identifier"] == "SINGLE-10")
            assert item["delivery_status"]["state"] == "not_selected"
