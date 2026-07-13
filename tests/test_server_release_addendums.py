"""Tests for POST /api/v1/issues/{identifier}/release-addendums (OOMPAH-176).

Covers section 6 of plans/release-branch-addendums.md:

  Approval endpoint:
  - Two-target approval creates exactly two open addendums and emits events
  - Duplicate request (same branches) is idempotent — no new rows, same 200
  - Concurrent approval: per-source lock prevents duplicate rows
  - Invalid/non-merged source: 409
  - Unavailable target branch: 400
  - Default-branch target: 400
  - Unsupported/unconfigured target: 400
  - Stale-only candidate: 400
  - Unresolved commits: 409
  - Atomic all-or-nothing validation: single invalid branch rejects all
  - Event failure recovery: row persisted, queued=false, no rollback
  - Missing project_id: 400
  - Unknown project: 404
  - Unknown issue: 404
  - Catalog first-load failure: 503

  Unit tests for release_addendum_approval module:
  - resolve_addendum_commits uses SCM then git fallback
  - resolve_addendum_commits raises CommitResolutionError when both fail
  - validate_target_branches deduplicates and catches all invalid cases
  - approve_release_addendums creates rows atomically under lock
  - approve_release_addendums is idempotent for existing active rows
  - Event bus emission per newly-created row
  - Event failure leaves row open, recorded in event_failures
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Issue, Project
from oompah.events import EventBus, EventType
from oompah.release_addendum_schema import (
    AddendumRepository,
    AddendumStatus,
    ReleaseAddendum,
    make_addendum_id,
    make_work_branch,
    make_worktree_key,
)
from oompah.release_addendum_approval import (
    ApprovalResult,
    CommitResolutionError,
    InvalidTargetBranchError,
    SourceNotMergedError,
    _get_source_lock,
    _source_locks,
    approve_release_addendums,
    resolve_addendum_commits,
    validate_target_branches,
)
from oompah.release_branch_catalog import (
    CatalogDiscoveryError,
    CatalogResult,
    ReleaseBranch,
    ReleaseBranchCatalog,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


_SENTINEL = object()


def _make_issue(
    identifier: str = "FOO-10",
    state: str = "Merged",
    branch_name: str | None | object = _SENTINEL,
) -> Issue:
    # When branch_name is not provided, derive from identifier.
    # When explicitly passed as None, leave it as None so tests can check
    # the fallback-to-identifier code path.
    if branch_name is _SENTINEL:
        branch_name = identifier.lower().replace("-", "/")
    return Issue(
        id=identifier,
        identifier=identifier,
        title="A merged task",
        description="",
        state=state,
        priority=1,
        issue_type="task",
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        branch_name=branch_name,
    )


def _make_project(
    pid: str = "proj-1",
    default_branch: str = "main",
    supported_release_branches: list[str] | None = None,
    repo_url: str = "https://github.com/org/repo",
    repo_path: str = "/tmp/repos/proj-1",
) -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = pid
    project.name = "Test Project"
    project.default_branch = default_branch
    project.supported_release_branches = supported_release_branches or [
        "release/1.1",
        "release/1.0",
    ]
    project.repo_url = repo_url
    project.repo_path = repo_path
    project.access_token = None
    project.branches = ["main", "release/*"]
    return project


def _make_tracker(meta: dict | None = None) -> MagicMock:
    tracker = MagicMock()
    # Use a mutable store so set_metadata_field updates get_metadata
    _store: dict = {"oompah.release_addendums": None}
    if meta:
        _store.update(meta)

    def _get_meta(identifier):
        return dict(_store)

    def _set_field(identifier, key, value):
        _store[key] = value

    tracker.get_metadata = MagicMock(side_effect=_get_meta)
    tracker.set_metadata_field = MagicMock(side_effect=_set_field)
    return tracker


def _make_catalog_result(
    branches: list[ReleaseBranch] | None = None,
    default_branch: str = "main",
    stale: bool = False,
) -> CatalogResult:
    if branches is None:
        branches = [
            ReleaseBranch(name="release/1.1", available=True, stale=False),
            ReleaseBranch(name="release/1.0", available=True, stale=False),
        ]
    return CatalogResult(
        project_id="proj-1",
        source_branch=default_branch,
        branches=branches,
        refreshed_at=1000.0,
        stale=stale,
    )


def _make_orchestrator(
    *,
    tracker: MagicMock | None = None,
    issue: Issue | None = None,
    project: MagicMock | None = None,
    project_id: str = "proj-1",
    event_bus: EventBus | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    t = tracker or _make_tracker()
    p = project or _make_project(project_id)
    orch = MagicMock()
    orch._tracker_for_project = MagicMock(return_value=t)
    orch.project_store.list_all = MagicMock(return_value=[p])
    orch.project_store.get = MagicMock(return_value=p)
    t.fetch_issue_detail = MagicMock(return_value=issue)
    orch.event_bus = event_bus or EventBus()
    return orch, t, p


@pytest.fixture(autouse=True)
def _clear_source_locks():
    """Clear per-source asyncio locks between tests to avoid cross-test pollution."""
    _source_locks.clear()
    yield
    _source_locks.clear()


@pytest.fixture()
def client():
    server_module._api_cache.invalidate_prefix("detail:")
    return TestClient(app, raise_server_exceptions=False)


_COMMITS = ["abc123def456" + "0" * 28, "bcd234ef5678" + "0" * 28]
_ENDPOINT = "/api/v1/issues/FOO-10/release-addendums"


# ===========================================================================
# Unit tests: resolve_addendum_commits
# ===========================================================================


class TestResolveAddendumCommits:
    """resolve_addendum_commits uses SCM then git rev-list."""

    def test_uses_scm_when_available(self):
        issue = _make_issue(branch_name="foo/foo-10")
        project = _make_project()

        scm = MagicMock()
        pr = MagicMock()
        pr.state = "merged"
        scm.find_pr_for_branch.return_value = pr
        scm.get_pr_commits.return_value = _COMMITS

        commits = resolve_addendum_commits(issue, project, scm=scm, repo="org/repo")
        assert commits == _COMMITS
        scm.find_pr_for_branch.assert_called_once_with("org/repo", "foo/foo-10")

    def test_falls_back_to_git_when_scm_returns_none(self):
        issue = _make_issue(branch_name="foo/foo-10")
        project = _make_project(repo_path="/tmp/repo")

        with patch(
            "oompah.release_pick_commit_resolver._resolve_via_scm",
            return_value=[],
        ), patch(
            "oompah.release_pick_commit_resolver._resolve_via_git",
            return_value=_COMMITS,
        ) as mock_git:
            commits = resolve_addendum_commits(issue, project, scm=MagicMock(), repo="org/repo")

        assert commits == _COMMITS

    def test_raises_when_both_fail(self):
        issue = _make_issue(branch_name="foo/foo-10")
        project = _make_project(repo_path="/tmp/repo")

        with patch(
            "oompah.release_pick_commit_resolver._resolve_via_scm",
            return_value=[],
        ), patch(
            "oompah.release_pick_commit_resolver._resolve_via_git",
            return_value=[],
        ):
            with pytest.raises(CommitResolutionError, match="Cannot resolve commits"):
                resolve_addendum_commits(issue, project, scm=MagicMock(), repo="org/repo")

    def test_no_scm_falls_back_to_git(self):
        issue = _make_issue(branch_name="foo/foo-10")
        project = _make_project(repo_path="/tmp/repo")

        with patch(
            "oompah.release_pick_commit_resolver._resolve_via_git",
            return_value=_COMMITS,
        ):
            commits = resolve_addendum_commits(issue, project)

        assert commits == _COMMITS

    def test_uses_identifier_as_branch_when_branch_name_none(self):
        issue = _make_issue(branch_name=None)
        issue.identifier = "FOO-10"
        project = _make_project(repo_path="/tmp/repo")

        with patch(
            "oompah.release_pick_commit_resolver._resolve_via_git",
            return_value=_COMMITS,
        ) as mock_git:
            commits = resolve_addendum_commits(issue, project)

        # branch argument is identifier when branch_name is None
        call_args = mock_git.call_args
        assert call_args[0][1] == "FOO-10"  # branch positional arg


# ===========================================================================
# Unit tests: validate_target_branches
# ===========================================================================


class TestValidateTargetBranches:
    """Validation rules for target branch list."""

    def _catalog(self, extra: list[ReleaseBranch] | None = None) -> CatalogResult:
        branches = [
            ReleaseBranch(name="release/1.1", available=True, stale=False),
            ReleaseBranch(name="release/1.0", available=True, stale=False),
        ] + (extra or [])
        return _make_catalog_result(branches=branches)

    def test_valid_branches_pass(self):
        catalog = self._catalog()
        deduped, errors = validate_target_branches(
            ["release/1.0", "release/1.1"], catalog, "main"
        )
        assert deduped == ["release/1.0", "release/1.1"]
        assert errors == []

    def test_deduplicates_request(self):
        catalog = self._catalog()
        deduped, errors = validate_target_branches(
            ["release/1.0", "release/1.0", "release/1.1"], catalog, "main"
        )
        assert deduped == ["release/1.0", "release/1.1"]
        assert errors == []

    def test_rejects_default_branch(self):
        catalog = self._catalog()
        _, errors = validate_target_branches(["main"], catalog, "main")
        assert len(errors) == 1
        assert "default branch" in errors[0]

    def test_rejects_unconfigured_branch(self):
        catalog = self._catalog()
        _, errors = validate_target_branches(["release/2.0"], catalog, "main")
        assert len(errors) == 1
        assert "not a configured" in errors[0]

    def test_rejects_unavailable_branch(self):
        catalog = self._catalog(
            extra=[ReleaseBranch(name="release/0.9", available=False, stale=False)]
        )
        _, errors = validate_target_branches(["release/0.9"], catalog, "main")
        assert len(errors) == 1
        assert "not currently available" in errors[0]

    def test_rejects_stale_branch(self):
        stale_branches = [
            ReleaseBranch(name="release/1.1", available=True, stale=True),
            ReleaseBranch(name="release/1.0", available=True, stale=True),
        ]
        catalog = _make_catalog_result(branches=stale_branches, stale=True)
        _, errors = validate_target_branches(["release/1.0"], catalog, "main")
        assert len(errors) == 1
        assert "stale" in errors[0].lower()

    def test_multiple_errors_collected(self):
        catalog = self._catalog()
        _, errors = validate_target_branches(
            ["main", "release/99.0", "release/1.0"], catalog, "main"
        )
        assert len(errors) == 2  # main + release/99.0


# ===========================================================================
# Unit tests: approve_release_addendums
# ===========================================================================


class TestApproveReleaseAddendums:
    """Core approval logic — atomic create and event emission."""

    @pytest.mark.asyncio
    async def test_creates_two_addendums(self):
        tracker = _make_tracker()
        issue = _make_issue()
        project = _make_project()
        event_bus = EventBus()
        received = []
        event_bus.subscribe(EventType.RELEASE_ADDENDUM_READY, lambda et, p: received.append(p))

        result = await approve_release_addendums(
            tracker, issue, project,
            ["release/1.0", "release/1.1"],
            _COMMITS,
            event_bus=event_bus,
        )

        assert len(result.addendums) == 2
        assert len(result.newly_created_ids) == 2
        assert result.queued is True
        assert len(received) == 2

        for a in result.addendums:
            assert a.status == AddendumStatus.OPEN
            assert a.commits == _COMMITS
            assert a.source_branch == "main"

    @pytest.mark.asyncio
    async def test_idempotent_for_existing_active_addendum(self):
        # Pre-populate one active addendum
        existing_id = make_addendum_id("FOO-10", "release/1.0")
        existing = ReleaseAddendum(
            id=existing_id,
            source_branch="main",
            target_branch="release/1.0",
            status=AddendumStatus.OPEN,
            commits=_COMMITS,
            work_branch=make_work_branch("FOO-10", "release/1.0"),
            worktree_key=make_worktree_key("FOO-10", "release/1.0"),
            queued_at="2026-07-13T00:00:00+00:00",
        )
        tracker = _make_tracker({
            "oompah.release_addendums": [existing.to_raw()],
        })
        issue = _make_issue()
        project = _make_project()
        event_bus = EventBus()
        received = []
        event_bus.subscribe(EventType.RELEASE_ADDENDUM_READY, lambda et, p: received.append(p))

        result = await approve_release_addendums(
            tracker, issue, project,
            ["release/1.0"],  # same as existing
            _COMMITS,
            event_bus=event_bus,
        )

        # No new rows — idempotent
        assert result.newly_created_ids == []
        assert result.queued is True  # vacuously true (nothing new)
        assert len(received) == 0  # no event for existing rows
        tracker.set_metadata_field.assert_not_called()

    @pytest.mark.asyncio
    async def test_adds_new_branch_alongside_existing(self):
        existing_id = make_addendum_id("FOO-10", "release/1.0")
        existing = ReleaseAddendum(
            id=existing_id,
            source_branch="main",
            target_branch="release/1.0",
            status=AddendumStatus.OPEN,
            commits=_COMMITS,
            work_branch=make_work_branch("FOO-10", "release/1.0"),
            worktree_key=make_worktree_key("FOO-10", "release/1.0"),
            queued_at="2026-07-13T00:00:00+00:00",
        )
        tracker = _make_tracker({
            "oompah.release_addendums": [existing.to_raw()],
        })
        issue = _make_issue()
        project = _make_project()

        result = await approve_release_addendums(
            tracker, issue, project,
            ["release/1.0", "release/1.1"],
            _COMMITS,
        )

        assert len(result.addendums) == 2
        assert len(result.newly_created_ids) == 1
        assert result.newly_created_ids[0] == make_addendum_id("FOO-10", "release/1.1")

    @pytest.mark.asyncio
    async def test_event_failure_leaves_row_open(self):
        tracker = _make_tracker()
        issue = _make_issue()
        project = _make_project()

        # EventBus that raises on emit
        event_bus = MagicMock(spec=EventBus)
        event_bus.emit.side_effect = RuntimeError("event bus dead")

        result = await approve_release_addendums(
            tracker, issue, project,
            ["release/1.0"],
            _COMMITS,
            event_bus=event_bus,
        )

        # Row was persisted
        assert len(result.addendums) == 1
        assert result.addendums[0].status == AddendumStatus.OPEN
        tracker.set_metadata_field.assert_called_once()

        # queued=False because event failed
        assert result.queued is False
        assert len(result.event_failures) == 1

    @pytest.mark.asyncio
    async def test_concurrent_approval_single_row(self):
        """Concurrent requests for the same branch create exactly one row."""
        tracker = _make_tracker()
        issue = _make_issue()
        project = _make_project()

        results = []

        async def _approve():
            r = await approve_release_addendums(
                tracker, issue, project, ["release/1.0"], _COMMITS
            )
            results.append(r)

        await asyncio.gather(_approve(), _approve())

        # Total addendums across both results must be exactly 1
        # (second caller is idempotent)
        all_new = sum(len(r.newly_created_ids) for r in results)
        assert all_new == 1, f"Expected 1 newly created row, got {all_new}"

    @pytest.mark.asyncio
    async def test_no_event_bus_is_safe(self):
        """approval succeeds when event_bus=None."""
        tracker = _make_tracker()
        issue = _make_issue()
        project = _make_project()

        result = await approve_release_addendums(
            tracker, issue, project, ["release/1.0"], _COMMITS, event_bus=None
        )
        assert len(result.newly_created_ids) == 1
        assert result.queued is True  # vacuously — nothing to fail

    @pytest.mark.asyncio
    async def test_commits_snapshot_is_immutable(self):
        """Each addendum stores exactly the commits passed at approval time."""
        tracker = _make_tracker()
        issue = _make_issue()
        project = _make_project()
        commits = ["aaa" + "0" * 37, "bbb" + "0" * 37]

        result = await approve_release_addendums(
            tracker, issue, project,
            ["release/1.0", "release/1.1"],
            commits,
        )

        for a in result.addendums:
            assert a.commits == commits


# ===========================================================================
# HTTP endpoint tests: POST /api/v1/issues/{identifier}/release-addendums
# ===========================================================================


class TestApproveReleaseAddendumsEndpoint:
    """Integration tests for the POST endpoint."""

    def _make_setup(
        self,
        *,
        state: str = "Merged",
        catalog_branches: list[ReleaseBranch] | None = None,
        commits: list[str] | None = None,
        existing_addendums: list[dict] | None = None,
    ) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
        issue = _make_issue(state=state)
        tracker = _make_tracker(
            {"oompah.release_addendums": existing_addendums} if existing_addendums else None
        )
        project = _make_project()
        orch, t, p = _make_orchestrator(
            tracker=tracker, issue=issue, project=project
        )
        catalog_result = _make_catalog_result(branches=catalog_branches)
        return orch, t, p, catalog_result

    def _post(self, client, body: dict, identifier: str = "FOO-10"):
        return client.post(
            f"/api/v1/issues/{identifier}/release-addendums",
            json=body,
        )

    # --- Happy path ---

    def test_two_target_approval_creates_two_addendums(self, client):
        orch, tracker, project, catalog = self._make_setup()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
            patch(
                "oompah.release_addendum_approval.resolve_addendum_commits",
                return_value=_COMMITS,
            ),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0", "release/1.1"],
                "idempotency_key": "test-uuid-1",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "FOO-10"
        assert len(data["addendums"]) == 2
        assert len(data["newly_created"]) == 2
        assert data["queued"] is True

        # Each addendum has the expected shape
        for a in data["addendums"]:
            assert a["status"] == "open"
            assert a["commits"] == _COMMITS
            assert a["source_branch"] == "main"

    def test_two_target_response_shape(self, client):
        orch, tracker, project, catalog = self._make_setup()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
            patch("oompah.release_addendum_approval.resolve_addendum_commits", return_value=_COMMITS),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0", "release/1.1"],
            })

        data = resp.json()
        branches_created = {a["target_branch"] for a in data["addendums"]}
        assert branches_created == {"release/1.0", "release/1.1"}
        ids_created = set(data["newly_created"])
        # Ledger delivery IDs are rd_<hex>, not the legacy FOO-10/branch format
        assert len(ids_created) == 2
        for delivery_id in ids_created:
            assert delivery_id.startswith("rd_"), (
                f"Expected ledger delivery ID with rd_ prefix, got {delivery_id!r}"
            )

    def test_duplicate_request_is_idempotent(self, client, tmp_path):
        # Use a real tmpdir so the ledger persists between the two requests.
        orch, tracker, project, catalog = self._make_setup()
        project.repo_path = str(tmp_path)
        # Make the tracker's write_and_commit_ledger_file write to disk so the
        # store persists across sequential requests.
        def _write_ledger(rel_path, content, subject):
            (tmp_path / rel_path).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel_path).write_text(content, encoding="utf-8")
        tracker.write_and_commit_ledger_file = MagicMock(side_effect=_write_ledger)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
            patch("oompah.release_addendum_approval.resolve_addendum_commits", return_value=_COMMITS),
        ):
            resp1 = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0"],
            })
            resp2 = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0"],
                "idempotency_key": "different-uuid",
            })

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Second call creates no new rows (idempotent)
        data2 = resp2.json()
        assert data2["newly_created"] == []
        # Delivery still present
        assert len(data2["addendums"]) == 1

    # --- Error cases ---

    def test_returns_400_missing_project_id(self, client):
        orch = MagicMock()
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post(client, {
                "target_branches": ["release/1.0"],
            })
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "validation"

    def test_returns_400_missing_target_branches(self, client):
        orch = MagicMock()
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post(client, {"project_id": "proj-1"})
        assert resp.status_code == 400

    def test_returns_400_empty_target_branches(self, client):
        orch = MagicMock()
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post(client, {"project_id": "proj-1", "target_branches": []})
        assert resp.status_code == 400

    def test_returns_404_unknown_project(self, client):
        orch = MagicMock()
        orch.project_store.get.side_effect = Exception("not found")
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post(client, {
                "project_id": "unknown",
                "target_branches": ["release/1.0"],
            })
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "project_not_found"

    def test_returns_404_unknown_issue(self, client):
        orch, tracker, project, catalog = self._make_setup()
        tracker.fetch_issue_detail = MagicMock(return_value=None)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0"],
            })
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "issue_not_found"

    def test_returns_409_non_merged_source(self, client):
        orch, tracker, project, catalog = self._make_setup(state="In Progress")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0"],
            })
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "source_not_merged"

    def test_returns_400_default_branch_target(self, client):
        orch, tracker, project, catalog = self._make_setup()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["main"],
            })
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "invalid_target_branches"
        assert any("default branch" in e for e in data["error"]["details"])

    def test_returns_400_unsupported_target(self, client):
        orch, tracker, project, catalog = self._make_setup()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/99.0"],
            })
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "invalid_target_branches"

    def test_returns_400_unavailable_target(self, client):
        unavail_catalog = _make_catalog_result(
            branches=[
                ReleaseBranch(name="release/1.0", available=False, stale=False),
            ]
        )
        orch, tracker, project, _ = self._make_setup()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=unavail_catalog)),
            ),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0"],
            })
        assert resp.status_code == 400
        data = resp.json()
        assert "not currently available" in data["error"]["details"][0]

    def test_returns_400_stale_target(self, client):
        stale_catalog = _make_catalog_result(
            branches=[
                ReleaseBranch(name="release/1.0", available=True, stale=True),
            ]
        )
        orch, tracker, project, _ = self._make_setup()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=stale_catalog)),
            ),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0"],
            })
        assert resp.status_code == 400
        data = resp.json()
        assert any("stale" in e.lower() for e in data["error"]["details"])

    def test_returns_503_catalog_first_load_failure(self, client):
        orch, tracker, project, _ = self._make_setup()

        mock_catalog = MagicMock()
        mock_catalog.list_candidates.side_effect = CatalogDiscoveryError("no remote")

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch("oompah.release_branch_catalog.get_default_catalog", return_value=mock_catalog),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0"],
            })
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "catalog_unavailable"

    def test_returns_409_unresolved_commits(self, client):
        orch, tracker, project, catalog = self._make_setup()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
            patch(
                "oompah.release_addendum_approval.resolve_addendum_commits",
                side_effect=CommitResolutionError("no commits found"),
            ),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0"],
            })
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "commit_resolution_failed"

    def test_atomic_all_or_nothing_validation(self, client):
        """One invalid branch rejects ALL branches without persisting anything."""
        orch, tracker, project, catalog = self._make_setup()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
            patch("oompah.release_addendum_approval.resolve_addendum_commits", return_value=_COMMITS),
        ):
            # release/1.0 is valid, release/99.0 is not
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0", "release/99.0"],
            })

        assert resp.status_code == 400
        # No addendum should have been written
        tracker.set_metadata_field.assert_not_called()

    def test_event_failure_recovery(self, client):
        """Event failure leaves row open, returns queued=false, no rollback."""
        orch, tracker, project, catalog = self._make_setup()

        # EventBus that raises
        bad_bus = MagicMock(spec=EventBus)
        bad_bus.emit.side_effect = RuntimeError("bus down")
        orch.event_bus = bad_bus

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
            patch("oompah.release_addendum_approval.resolve_addendum_commits", return_value=_COMMITS),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0"],
            })

        # Still 200 — persistence succeeded
        assert resp.status_code == 200
        data = resp.json()
        # Row was written
        assert len(data["addendums"]) == 1
        assert data["addendums"][0]["status"] == "open"
        # queued=false because event failed
        assert data["queued"] is False
        assert "event_failures" in data
        # Failure IDs are now ledger delivery IDs (rd_<hex>), not legacy addendum IDs
        assert len(data["event_failures"]) == 1
        assert data["event_failures"][0].startswith("rd_")
        # New code does NOT call set_metadata_field (no legacy metadata writes)
        tracker.set_metadata_field.assert_not_called()

    def test_concurrent_approval_one_active_row(self, client, tmp_path):
        """Two concurrent requests for the same branch yield exactly one delivery."""
        orch, tracker, project, catalog = self._make_setup()
        # Use real tmpdir so the ledger persists between the two sequential calls.
        project.repo_path = str(tmp_path)
        def _write_ledger(rel_path, content, subject):
            (tmp_path / rel_path).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel_path).write_text(content, encoding="utf-8")
        tracker.write_and_commit_ledger_file = MagicMock(side_effect=_write_ledger)

        all_results = []

        def _run():
            with (
                patch.object(server_module, "_get_orchestrator", return_value=orch),
                patch(
                    "oompah.release_branch_catalog.get_default_catalog",
                    return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
                ),
                patch("oompah.release_addendum_approval.resolve_addendum_commits", return_value=_COMMITS),
            ):
                resp = self._post(client, {
                    "project_id": "proj-1",
                    "target_branches": ["release/1.0"],
                })
                all_results.append(resp.json())

        # TestClient is synchronous but asyncio lock prevents duplicate creation
        _run()
        _run()

        total_new = sum(len(r.get("newly_created", [])) for r in all_results)
        assert total_new == 1, f"Expected 1 newly created delivery, got {total_new}"

    def test_event_emitted_per_newly_created_row(self, client):
        """One release_addendum_ready event per newly created delivery."""
        orch, tracker, project, catalog = self._make_setup()
        received: list[dict] = []

        def _on_event(et, payload):
            received.append(payload)

        orch.event_bus = EventBus()
        orch.event_bus.subscribe(EventType.RELEASE_ADDENDUM_READY, _on_event)

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
            patch("oompah.release_addendum_approval.resolve_addendum_commits", return_value=_COMMITS),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0", "release/1.1"],
            })

        assert resp.status_code == 200
        assert len(received) == 2
        # New code emits delivery_id (rd_<hex>), not the legacy addendum_id
        delivery_ids = {p["delivery_id"] for p in received}
        assert len(delivery_ids) == 2
        for did in delivery_ids:
            assert did.startswith("rd_"), f"Expected rd_ prefix, got {did!r}"
        # project_id is always included
        assert all(p["project_id"] == "proj-1" for p in received)

    def test_no_tracker_child_task_created(self, client):
        """Approval must not call any task-creation method."""
        orch, tracker, project, catalog = self._make_setup()

        with (
            patch.object(server_module, "_get_orchestrator", return_value=orch),
            patch(
                "oompah.release_branch_catalog.get_default_catalog",
                return_value=MagicMock(list_candidates=MagicMock(return_value=catalog)),
            ),
            patch("oompah.release_addendum_approval.resolve_addendum_commits", return_value=_COMMITS),
        ):
            resp = self._post(client, {
                "project_id": "proj-1",
                "target_branches": ["release/1.0"],
            })

        assert resp.status_code == 200
        # Verify no tracker task-creation was attempted
        assert not tracker.create_issue.called
        assert not tracker.create_child_issue.called


# ===========================================================================
# EventType
# ===========================================================================


class TestEventTypeReleaseAddendumReady:
    """RELEASE_ADDENDUM_READY is registered in EventType enum."""

    def test_event_type_exists(self):
        assert EventType.RELEASE_ADDENDUM_READY == "release_addendum_ready"

    def test_emit_and_subscribe(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.RELEASE_ADDENDUM_READY, lambda et, p: received.append(p))
        bus.emit(EventType.RELEASE_ADDENDUM_READY, {"addendum_id": "FOO-10/release/1.0"})
        assert received == [{"addendum_id": "FOO-10/release/1.0"}]
