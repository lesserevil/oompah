"""Ledger-based task/epic release-addendum compatibility tests (OOMPAH-196).

Covers:
  GET /api/v1/issues/{identifier}/release-addendums
  - Returns ledger entries for source (via DualReadDeliveryAdapter)
  - Returns combined ledger + legacy when both exist (post-migration view)
  - Falls back to legacy when no repo_path
  - 404 for unknown issue

  POST /api/v1/issues/{identifier}/release-addendums
  - Creates ReleaseDelivery entries in the ledger, NOT oompah.release_addendums metadata
  - No set_metadata_field call on approval (regression: no legacy metadata written)
  - No child task created (regression: no backport task)
  - Idempotent: second request for same branch creates no new delivery
  - Event published with delivery_id (not legacy addendum_id)
  - Source-commit resolution failure → 409

  POST .../retry (ledger path)
  - Finds delivery by ID in ledger and transitions blocked → open
  - Invalid transition (e.g. open → open) returns 409
  - Falls back to legacy shim when delivery_id not in ledger

  POST .../archive (ledger path)
  - Finds delivery by ID in ledger and transitions open → archived
  - Invalid transition (e.g. in_review → archived) returns 409
  - Falls back to legacy shim when delivery_id not in ledger

  delivery_to_compat_raw
  - Backward-compatible shape (commits, worktree_key, id, status, etc.)
  - Extra ledger fields present (delivery_id, source_kind, source_identifier)
  - included_child_ids always empty list

  approve_release_addendums_via_ledger
  - Creates one delivery per target branch
  - Idempotent: skips active (non-archived) existing deliveries
  - Re-queues archived deliveries as new open entries
  - work_branch set at creation time for task/epic deliveries
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.events import EventBus, EventType
from oompah.models import Issue, Project
from oompah.release_addendum_schema import (
    AddendumStatus,
    ReleaseAddendum,
    make_addendum_id,
    make_work_branch,
    make_worktree_key,
)
from oompah.release_delivery_compat import (
    LedgerApprovalResult,
    _make_delivery_id,
    approve_release_addendums_via_ledger,
    delivery_to_compat_raw,
    make_delivery_adapter,
    make_delivery_store,
)
from oompah.release_delivery_store import (
    LEDGER_PATH,
    AddendumStatus,
    ReleaseDelivery,
    ReleaseDeliveryStore,
    SourceKind,
)
from oompah.release_branch_catalog import (
    CatalogResult,
    ReleaseBranch,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SHA_A = "a" * 40
_SHA_B = "b" * 40
_SHA_C = "c" * 40
_COMMITS = [_SHA_A, _SHA_B]
_NOW = "2026-07-13T12:00:00Z"
_PROJECT_ID = "proj-1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_issue(
    identifier: str = "FOO-10",
    state: str = "Merged",
    issue_type: str = "task",
) -> Issue:
    return Issue(
        id=identifier,
        identifier=identifier,
        title="A merged task",
        description="",
        state=state,
        priority=1,
        issue_type=issue_type,
        labels=[],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_project(tmp_path: Path, pid: str = _PROJECT_ID) -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = pid
    project.name = "Test Project"
    project.default_branch = "main"
    project.supported_release_branches = ["release/1.1", "release/1.0"]
    project.repo_url = "https://github.com/org/repo"
    project.repo_path = str(tmp_path)
    project.access_token = None
    project.branches = ["main", "release/*"]
    return project


def _make_tracker_with_ledger(tmp_path: Path, raw_addendums=None) -> MagicMock:
    """Return a mock tracker whose write_and_commit_ledger_file writes to disk."""
    tracker = MagicMock()
    _meta: dict = {}
    if raw_addendums is not None:
        _meta["oompah.release_addendums"] = raw_addendums

    tracker.get_metadata = MagicMock(return_value=_meta)
    tracker.set_metadata_field = MagicMock()

    def _write_ledger(rel_path: str, content: str, subject: str) -> None:
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    tracker.write_and_commit_ledger_file = MagicMock(side_effect=_write_ledger)
    return tracker


def _make_delivery(
    *,
    delivery_id: str | None = None,
    source_identifier: str = "FOO-10",
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.OPEN,
    source_kind: SourceKind = SourceKind.TASK,
    commits: list[str] | None = None,
    **kwargs,
) -> ReleaseDelivery:
    did = delivery_id or _make_delivery_id()
    return ReleaseDelivery(
        id=did,
        project_id=_PROJECT_ID,
        source_branch="main",
        source_kind=source_kind,
        source_identifier=source_identifier,
        source_commits=list(commits or _COMMITS),
        target_branch=target_branch,
        status=status,
        queued_at=_NOW,
        **kwargs,
    )


def _make_addendum(
    source_id: str = "FOO-10",
    target_branch: str = "release/1.0",
    status: AddendumStatus = AddendumStatus.OPEN,
) -> ReleaseAddendum:
    return ReleaseAddendum(
        id=make_addendum_id(source_id, target_branch),
        source_branch="main",
        target_branch=target_branch,
        status=status,
        commits=list(_COMMITS),
        work_branch=make_work_branch(source_id, target_branch),
        worktree_key=make_worktree_key(source_id, target_branch),
        queued_at=_NOW,
    )


def _make_catalog_result() -> CatalogResult:
    return CatalogResult(
        project_id=_PROJECT_ID,
        source_branch="main",
        branches=[
            ReleaseBranch(name="release/1.1", available=True, stale=False),
            ReleaseBranch(name="release/1.0", available=True, stale=False),
        ],
        refreshed_at=1000.0,
        stale=False,
    )


def _make_orchestrator(
    tmp_path: Path,
    *,
    tracker=None,
    issue=None,
    project=None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    p = project or _make_project(tmp_path)
    t = tracker or _make_tracker_with_ledger(tmp_path)
    orch = MagicMock()
    orch._tracker_for_project = MagicMock(return_value=t)
    orch.project_store.list_all = MagicMock(return_value=[p])
    orch.project_store.get = MagicMock(return_value=p)
    t.fetch_issue_detail = MagicMock(return_value=issue)
    orch.event_bus = EventBus()
    return orch, t, p


@pytest.fixture(autouse=True)
def _clear_compat_source_locks():
    """Clear per-source asyncio locks between tests."""
    import oompah.release_delivery_compat as compat
    compat._source_locks.clear()
    yield
    compat._source_locks.clear()


@pytest.fixture()
def client():
    server_module._api_cache.invalidate_prefix("detail:")
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# delivery_to_compat_raw
# ===========================================================================


class TestDeliveryToCompatRaw:
    """delivery_to_compat_raw produces a backward-compatible dict."""

    def test_commits_field_mapped_from_source_commits(self):
        d = _make_delivery(commits=[_SHA_A, _SHA_B])
        raw = delivery_to_compat_raw(d)
        assert raw["commits"] == [_SHA_A, _SHA_B]

    def test_legacy_fields_present(self):
        d = _make_delivery()
        raw = delivery_to_compat_raw(d)
        for key in ("id", "source_branch", "target_branch", "status",
                    "commits", "work_branch", "worktree_key", "queued_at",
                    "started_at", "completed_at", "pr_url", "result_commits", "error"):
            assert key in raw, f"Missing legacy field: {key}"

    def test_included_child_ids_always_empty_list(self):
        d = _make_delivery()
        raw = delivery_to_compat_raw(d)
        assert raw["included_child_ids"] == []

    def test_extra_ledger_fields_present(self):
        d = _make_delivery()
        raw = delivery_to_compat_raw(d)
        assert raw["delivery_id"] == d.id
        assert raw["source_kind"] == "task"
        assert raw["source_identifier"] == "FOO-10"

    def test_status_string(self):
        d = _make_delivery(status=AddendumStatus.BLOCKED)
        raw = delivery_to_compat_raw(d)
        assert raw["status"] == "blocked"

    def test_worktree_key_computed_for_task(self):
        d = _make_delivery(source_identifier="FOO-10", target_branch="release/1.0")
        raw = delivery_to_compat_raw(d)
        # Should use make_delivery_worktree_key which calls make_worktree_key for tasks
        expected = make_worktree_key("FOO-10", "release/1.0")
        assert raw["worktree_key"] == expected

    def test_result_commits_present(self):
        d = _make_delivery(result_commits=[_SHA_C])
        raw = delivery_to_compat_raw(d)
        assert raw["result_commits"] == [_SHA_C]

    def test_migrated_from_field(self):
        d = _make_delivery(migrated_from="FOO-10/release/1.0")
        raw = delivery_to_compat_raw(d)
        assert raw["migrated_from"] == "FOO-10/release/1.0"


# ===========================================================================
# approve_release_addendums_via_ledger
# ===========================================================================


class TestApproveViaLedger:
    """Unit tests for approve_release_addendums_via_ledger."""

    def _run(self, tmp_path: Path, **kwargs):
        """Run approval with real store and tracker. Returns (result, store)."""
        tracker = _make_tracker_with_ledger(tmp_path, kwargs.pop("raw_addendums", None))
        project = _make_project(tmp_path)
        store = make_delivery_store(project, git_writer=tracker)
        adapter = make_delivery_adapter(project, tracker, git_writer=tracker)
        issue = _make_issue(**kwargs.pop("issue_kwargs", {}))
        import asyncio
        result = asyncio.run(
            approve_release_addendums_via_ledger(
                store,
                adapter,
                issue,
                project,
                kwargs.pop("target_branches", ["release/1.0"]),
                kwargs.pop("commits", _COMMITS),
                **kwargs,
            )
        )
        return result, store

    def test_creates_one_delivery_per_branch(self, tmp_path):
        result, store = self._run(
            tmp_path,
            target_branches=["release/1.0", "release/1.1"],
        )
        assert len(result.newly_created_ids) == 2
        assert len(result.deliveries) == 2

    def test_delivery_has_correct_fields(self, tmp_path):
        result, store = self._run(tmp_path, target_branches=["release/1.0"])
        assert len(result.newly_created_ids) == 1
        delivery_id = result.newly_created_ids[0]
        d = store.lookup_by_id(delivery_id)
        assert d is not None
        assert d.source_identifier == "FOO-10"
        assert d.source_kind == SourceKind.TASK
        assert d.source_commits == _COMMITS
        assert d.target_branch == "release/1.0"
        assert d.status == AddendumStatus.OPEN
        assert d.work_branch is not None

    def test_work_branch_set_for_task(self, tmp_path):
        result, store = self._run(tmp_path, target_branches=["release/1.0"])
        d = store.lookup_by_id(result.newly_created_ids[0])
        expected = make_work_branch("FOO-10", "release/1.0")
        assert d.work_branch == expected

    def test_work_branch_set_for_epic(self, tmp_path):
        result, store = self._run(
            tmp_path,
            target_branches=["release/1.0"],
            issue_kwargs={"identifier": "EP-1", "issue_type": "epic"},
        )
        d = store.lookup_by_id(result.newly_created_ids[0])
        expected = make_work_branch("EP-1", "release/1.0")
        assert d.work_branch == expected

    def test_source_kind_epic_for_epic_issue(self, tmp_path):
        result, store = self._run(
            tmp_path,
            target_branches=["release/1.0"],
            issue_kwargs={"identifier": "EP-1", "issue_type": "epic"},
        )
        d = store.lookup_by_id(result.newly_created_ids[0])
        assert d.source_kind == SourceKind.EPIC

    def test_idempotent_skips_active_delivery(self, tmp_path):
        """Second approval for same branch creates no new delivery."""
        result1, store = self._run(tmp_path, target_branches=["release/1.0"])
        assert len(result1.newly_created_ids) == 1

        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store2 = make_delivery_store(project, git_writer=tracker)
        adapter2 = make_delivery_adapter(project, tracker, git_writer=tracker)
        issue = _make_issue()
        import asyncio
        result2 = asyncio.run(
            approve_release_addendums_via_ledger(
                store2, adapter2, issue, project, ["release/1.0"], _COMMITS
            )
        )
        assert result2.newly_created_ids == []
        assert result2.queued is True  # idempotent = already queued

    def test_archived_delivery_allows_new(self, tmp_path):
        """An archived delivery does not block re-approval for the same branch."""
        # Create and archive first delivery
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = make_delivery_store(project, git_writer=tracker)
        archived = _make_delivery(status=AddendumStatus.ARCHIVED)
        store.append(archived)

        adapter = make_delivery_adapter(project, tracker, git_writer=tracker)
        issue = _make_issue()
        import asyncio
        result = asyncio.run(
            approve_release_addendums_via_ledger(
                store, adapter, issue, project, ["release/1.0"], _COMMITS
            )
        )
        assert len(result.newly_created_ids) == 1
        new_id = result.newly_created_ids[0]
        new_delivery = store.lookup_by_id(new_id)
        assert new_delivery.status == AddendumStatus.OPEN

    def test_event_published_for_each_delivery(self, tmp_path):
        received = []
        bus = EventBus()
        bus.subscribe(EventType.RELEASE_ADDENDUM_READY, lambda et, p: received.append(p))

        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = make_delivery_store(project, git_writer=tracker)
        adapter = make_delivery_adapter(project, tracker, git_writer=tracker)
        issue = _make_issue()
        import asyncio
        asyncio.run(
            approve_release_addendums_via_ledger(
                store, adapter, issue, project, ["release/1.0", "release/1.1"], _COMMITS,
                event_bus=bus,
            )
        )
        assert len(received) == 2
        for payload in received:
            assert "delivery_id" in payload
            assert payload["delivery_id"].startswith("rd_")
            assert payload["project_id"] == _PROJECT_ID

    def test_event_failure_not_fatal(self, tmp_path):
        bad_bus = MagicMock(spec=EventBus)
        bad_bus.emit.side_effect = RuntimeError("bus down")

        result, _ = self._run(tmp_path, target_branches=["release/1.0"])
        # Without event_bus, no failure
        assert result.event_failures == []

        # With bad bus
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = make_delivery_store(project, git_writer=tracker)
        adapter = make_delivery_adapter(project, tracker, git_writer=tracker)
        issue = _make_issue(identifier="BAR-20")
        import asyncio
        result2 = asyncio.run(
            approve_release_addendums_via_ledger(
                store, adapter, issue, project, ["release/1.0"], _COMMITS,
                event_bus=bad_bus,
            )
        )
        assert len(result2.newly_created_ids) == 1
        assert len(result2.event_failures) == 1
        assert result2.queued is False

    def test_no_legacy_metadata_written(self, tmp_path):
        """Approval must NOT write to oompah.release_addendums task metadata."""
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = make_delivery_store(project, git_writer=tracker)
        adapter = make_delivery_adapter(project, tracker, git_writer=tracker)
        issue = _make_issue()
        import asyncio
        asyncio.run(
            approve_release_addendums_via_ledger(
                store, adapter, issue, project, ["release/1.0"], _COMMITS
            )
        )
        tracker.set_metadata_field.assert_not_called()

    def test_combined_view_includes_legacy_addendums(self, tmp_path):
        """Deliveries list includes pre-migration legacy addendums from tracker."""
        legacy_addendum = _make_addendum()
        tracker = _make_tracker_with_ledger(tmp_path, raw_addendums=[legacy_addendum.to_raw()])
        project = _make_project(tmp_path)
        store = make_delivery_store(project, git_writer=tracker)
        adapter = make_delivery_adapter(project, tracker, git_writer=tracker)
        issue = _make_issue()
        import asyncio
        result = asyncio.run(
            approve_release_addendums_via_ledger(
                store, adapter, issue, project, ["release/1.1"], _COMMITS
            )
        )
        # New delivery for release/1.1 + legacy for release/1.0
        target_branches = {d.target_branch for d in result.deliveries}
        assert "release/1.1" in target_branches
        assert "release/1.0" in target_branches


# ===========================================================================
# GET /api/v1/issues/{identifier}/release-addendums (ledger path)
# ===========================================================================


class TestGetReleaseAddendumsLedger:
    """GET endpoint uses DualReadDeliveryAdapter."""

    _ENDPOINT_TMPL = "/api/v1/issues/{}/release-addendums"

    def _get(self, client, tmp_path, identifier="FOO-10", issue=None, tracker=None, project=None):
        orch, t, p = _make_orchestrator(
            tmp_path, tracker=tracker, issue=issue, project=project
        )
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            return client.get(
                self._ENDPOINT_TMPL.format(identifier),
                params={"project_id": _PROJECT_ID},
            )

    def test_returns_ledger_entries_for_source(self, client, tmp_path):
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        # Write a delivery to the ledger
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        d = _make_delivery()
        store.append(d)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                self._ENDPOINT_TMPL.format("FOO-10"),
                params={"project_id": _PROJECT_ID},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["identifier"] == "FOO-10"
        assert len(data["addendums"]) == 1
        assert data["addendums"][0]["id"] == d.id
        assert data["addendums"][0]["target_branch"] == "release/1.0"
        assert data["addendums"][0]["commits"] == _COMMITS

    def test_returns_combined_ledger_and_legacy(self, client, tmp_path):
        """After migration: ledger entry + un-migrated legacy addendum both shown."""
        legacy_addendum = _make_addendum(target_branch="release/1.0")
        tracker = _make_tracker_with_ledger(tmp_path, raw_addendums=[legacy_addendum.to_raw()])

        project = _make_project(tmp_path)
        # Write a NEW ledger delivery for release/1.1
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        new_delivery = _make_delivery(
            delivery_id=_make_delivery_id(),
            target_branch="release/1.1",
        )
        store.append(new_delivery)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                self._ENDPOINT_TMPL.format("FOO-10"),
                params={"project_id": _PROJECT_ID},
            )
        assert resp.status_code == 200
        data = resp.json()
        branches = {a["target_branch"] for a in data["addendums"]}
        assert "release/1.0" in branches
        assert "release/1.1" in branches

    def test_migrated_legacy_not_duplicated(self, client, tmp_path):
        """A migrated legacy addendum appears only once (ledger wins)."""
        legacy_addendum = _make_addendum(target_branch="release/1.0")
        tracker = _make_tracker_with_ledger(tmp_path, raw_addendums=[legacy_addendum.to_raw()])

        project = _make_project(tmp_path)
        # Write a ledger entry that represents the migrated legacy addendum
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        migrated = _make_delivery(
            delivery_id=_make_delivery_id(),
            target_branch="release/1.0",
            migrated_from=legacy_addendum.id,  # marks it as migrated
        )
        store.append(migrated)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                self._ENDPOINT_TMPL.format("FOO-10"),
                params={"project_id": _PROJECT_ID},
            )
        assert resp.status_code == 200
        data = resp.json()
        # Only one entry (ledger), not two
        assert len(data["addendums"]) == 1
        assert data["addendums"][0]["id"] == migrated.id

    def test_falls_back_to_legacy_when_no_repo_path(self, client, tmp_path):
        """When project has no repo_path, returns legacy addendums."""
        legacy_addendum = _make_addendum()
        tracker = _make_tracker_with_ledger(tmp_path, raw_addendums=[legacy_addendum.to_raw()])
        project = _make_project(tmp_path)
        project.repo_path = None  # simulate pre-ledger project

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                self._ENDPOINT_TMPL.format("FOO-10"),
                params={"project_id": _PROJECT_ID},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["addendums"]) == 1
        assert data["addendums"][0]["target_branch"] == "release/1.0"

    def test_returns_empty_list_for_no_deliveries(self, client, tmp_path):
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                self._ENDPOINT_TMPL.format("FOO-10"),
                params={"project_id": _PROJECT_ID},
            )
        assert resp.status_code == 200
        assert resp.json()["addendums"] == []

    def test_compat_raw_shape_in_response(self, client, tmp_path):
        """Each entry has the backward-compatible fields."""
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        d = _make_delivery(
            pr_url="https://github.com/org/repo/pull/1",
            result_commits=[_SHA_C],
        )
        store.append(d)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = client.get(
                self._ENDPOINT_TMPL.format("FOO-10"),
                params={"project_id": _PROJECT_ID},
            )
        entry = resp.json()["addendums"][0]
        # Legacy-compatible fields
        for key in ("id", "source_branch", "target_branch", "status", "commits",
                    "work_branch", "worktree_key", "queued_at", "pr_url", "result_commits",
                    "error", "included_child_ids"):
            assert key in entry, f"Missing field: {key}"
        assert entry["commits"] == _COMMITS
        assert entry["result_commits"] == [_SHA_C]
        assert entry["pr_url"] == "https://github.com/org/repo/pull/1"
        # Ledger-only extra fields
        assert entry["delivery_id"] == d.id


# ===========================================================================
# POST /api/v1/issues/{identifier}/release-addendums (ledger path)
# ===========================================================================


class TestApproveEndpointLedger:
    """Integration tests for the POST approval endpoint with ledger writes."""

    def _make_setup(self, tmp_path: Path, *, state="Merged"):
        issue = _make_issue(state=state)
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        orch, t, p = _make_orchestrator(tmp_path, tracker=tracker, issue=issue, project=project)
        catalog = _make_catalog_result()
        return orch, t, p, catalog, issue

    def _post(self, client, body: dict, identifier: str = "FOO-10"):
        return client.post(
            f"/api/v1/issues/{identifier}/release-addendums",
            json=body,
        )

    def test_creates_ledger_delivery_not_task_metadata(self, client, tmp_path):
        """Approval writes to ledger, not oompah.release_addendums metadata."""
        orch, tracker, project, catalog, issue = self._make_setup(tmp_path)
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
                "project_id": _PROJECT_ID,
                "target_branches": ["release/1.0"],
            })

        assert resp.status_code == 200
        # No legacy metadata written
        tracker.set_metadata_field.assert_not_called()
        # Ledger was written
        tracker.write_and_commit_ledger_file.assert_called_once()
        # Delivery appears in ledger on disk
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID)
        deliveries = store.lookup_by_source_identifier("FOO-10")
        assert len(deliveries) == 1
        assert deliveries[0].target_branch == "release/1.0"
        assert deliveries[0].source_commits == _COMMITS

    def test_no_child_task_created(self, client, tmp_path):
        """Approval must not create child backport tasks."""
        orch, tracker, project, catalog, issue = self._make_setup(tmp_path)
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
            self._post(client, {
                "project_id": _PROJECT_ID,
                "target_branches": ["release/1.0"],
            })
        assert not tracker.create_issue.called
        assert not tracker.create_child_issue.called

    def test_delivery_id_has_rd_prefix(self, client, tmp_path):
        """Newly-created delivery IDs use the rd_ prefix."""
        orch, tracker, project, catalog, issue = self._make_setup(tmp_path)
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
                "project_id": _PROJECT_ID,
                "target_branches": ["release/1.0"],
            })
        data = resp.json()
        assert len(data["newly_created"]) == 1
        assert data["newly_created"][0].startswith("rd_")

    def test_event_wakes_queue(self, client, tmp_path):
        """Approval emits RELEASE_ADDENDUM_READY with delivery_id and project_id."""
        received = []
        orch, tracker, project, catalog, issue = self._make_setup(tmp_path)
        orch.event_bus = EventBus()
        orch.event_bus.subscribe(
            EventType.RELEASE_ADDENDUM_READY, lambda et, p: received.append(p)
        )
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
                "project_id": _PROJECT_ID,
                "target_branches": ["release/1.0", "release/1.1"],
            })
        assert resp.status_code == 200
        assert len(received) == 2
        for payload in received:
            assert "delivery_id" in payload
            assert payload["project_id"] == _PROJECT_ID

    def test_source_commit_resolution_failure_returns_409(self, client, tmp_path):
        """When commit resolution fails, approval returns 409."""
        from oompah.release_addendum_approval import CommitResolutionError
        orch, tracker, project, catalog, issue = self._make_setup(tmp_path)
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
                "project_id": _PROJECT_ID,
                "target_branches": ["release/1.0"],
            })
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "commit_resolution_failed"

    def test_response_shape_backward_compatible(self, client, tmp_path):
        """Response contains commits, status, work_branch (backward-compatible)."""
        orch, tracker, project, catalog, issue = self._make_setup(tmp_path)
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
                "project_id": _PROJECT_ID,
                "target_branches": ["release/1.0"],
            })
        data = resp.json()
        assert data["identifier"] == "FOO-10"
        assert data["queued"] is True
        entry = data["addendums"][0]
        assert entry["commits"] == _COMMITS
        assert entry["status"] == "open"
        assert entry["work_branch"] is not None

    def test_idempotent_across_requests(self, client, tmp_path):
        """Second request for same branch creates no new delivery."""
        orch, tracker, project, catalog, issue = self._make_setup(tmp_path)
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
            resp1 = self._post(client, {
                "project_id": _PROJECT_ID,
                "target_branches": ["release/1.0"],
            })
            resp2 = self._post(client, {
                "project_id": _PROJECT_ID,
                "target_branches": ["release/1.0"],
            })
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert len(resp2.json()["newly_created"]) == 0

    def test_existing_ledger_deliveries_shown_in_response(self, client, tmp_path):
        """After migration, pre-existing ledger entries appear in POST response."""
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        # Pre-populate ledger with a migrated delivery for release/1.0
        existing = _make_delivery(
            delivery_id=_make_delivery_id(),
            target_branch="release/1.0",
            status=AddendumStatus.IN_REVIEW,
        )
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        store.append(existing)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()
        catalog = _make_catalog_result()

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
                "project_id": _PROJECT_ID,
                "target_branches": ["release/1.1"],  # different branch
            })

        data = resp.json()
        assert resp.status_code == 200
        branches = {a["target_branch"] for a in data["addendums"]}
        assert "release/1.0" in branches  # pre-existing (in_review)
        assert "release/1.1" in branches  # newly created


# ===========================================================================
# POST .../retry (ledger path)
# ===========================================================================


class TestRetryLedgerEndpoint:
    """Retry endpoint uses ledger lookup first."""

    def _post_retry(self, client, delivery_id: str, identifier: str = "FOO-10"):
        return client.post(
            f"/api/v1/issues/{identifier}/release-addendums/{delivery_id}/retry",
            json={"project_id": _PROJECT_ID},
        )

    def test_retries_blocked_ledger_delivery(self, client, tmp_path):
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        blocked = _make_delivery(
            status=AddendumStatus.BLOCKED,
            error="cherry-pick conflict",
        )
        store.append(blocked)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_retry(client, blocked.id)

        assert resp.status_code == 200
        data = resp.json()
        assert data["addendum_id"] == blocked.id
        # Delivery is now open
        updated = store.lookup_by_id(blocked.id)
        assert updated.status == AddendumStatus.OPEN
        assert updated.error is None
        assert updated.claimed_by is None

    def test_retries_in_review_ledger_delivery(self, client, tmp_path):
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        in_review = _make_delivery(
            status=AddendumStatus.IN_REVIEW,
            pr_url="https://github.com/org/repo/pull/42",
        )
        store.append(in_review)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_retry(client, in_review.id)

        assert resp.status_code == 200
        updated = store.lookup_by_id(in_review.id)
        assert updated.status == AddendumStatus.OPEN

    def test_retry_invalid_transition_returns_409(self, client, tmp_path):
        """Retrying an already-open delivery is invalid."""
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        open_delivery = _make_delivery(status=AddendumStatus.OPEN)
        store.append(open_delivery)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_retry(client, open_delivery.id)

        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "invalid_transition"

    def test_retry_posts_comment_on_source_task(self, client, tmp_path):
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        blocked = _make_delivery(status=AddendumStatus.BLOCKED, error="conflict")
        store.append(blocked)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            self._post_retry(client, blocked.id)

        tracker.add_comment.assert_called_once()
        comment_call = tracker.add_comment.call_args
        assert "retried" in comment_call.args[1].lower() or "retried" in comment_call[0][1].lower()

    def test_retry_emits_wake_event(self, client, tmp_path):
        received = []
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        blocked = _make_delivery(status=AddendumStatus.BLOCKED)
        store.append(blocked)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        bus = EventBus()
        bus.subscribe(EventType.RELEASE_ADDENDUM_READY, lambda et, p: received.append(p))
        orch.event_bus = bus

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            self._post_retry(client, blocked.id)

        assert len(received) == 1
        assert received[0]["delivery_id"] == blocked.id
        assert received[0]["project_id"] == _PROJECT_ID

    def test_retry_response_includes_full_delivery_list(self, client, tmp_path):
        """Response includes all deliveries for the source via adapter."""
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        d1 = _make_delivery(status=AddendumStatus.BLOCKED, target_branch="release/1.0")
        d2 = _make_delivery(
            delivery_id=_make_delivery_id(),
            status=AddendumStatus.IN_REVIEW,
            target_branch="release/1.1",
        )
        store.append(d1)
        store.append(d2)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_retry(client, d1.id)

        data = resp.json()
        assert resp.status_code == 200
        branches = {a["target_branch"] for a in data["addendums"]}
        assert "release/1.0" in branches
        assert "release/1.1" in branches

    def test_retry_not_found_returns_404_for_unknown_id(self, client, tmp_path):
        """When delivery not in ledger and not in legacy, returns 404."""
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_retry(client, "rd_nonexistent")

        assert resp.status_code == 404

    def test_retry_merged_delivery_invalid(self, client, tmp_path):
        """Cannot retry a merged delivery."""
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        merged = _make_delivery(status=AddendumStatus.MERGED)
        store.append(merged)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_retry(client, merged.id)

        assert resp.status_code == 409


# ===========================================================================
# POST .../archive (ledger path)
# ===========================================================================


class TestArchiveLedgerEndpoint:
    """Archive endpoint uses ledger lookup first."""

    def _post_archive(self, client, delivery_id: str, identifier: str = "FOO-10"):
        return client.post(
            f"/api/v1/issues/{identifier}/release-addendums/{delivery_id}/archive",
            json={"project_id": _PROJECT_ID},
        )

    def test_archives_open_ledger_delivery(self, client, tmp_path):
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        open_delivery = _make_delivery(status=AddendumStatus.OPEN)
        store.append(open_delivery)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_archive(client, open_delivery.id)

        assert resp.status_code == 200
        updated = store.lookup_by_id(open_delivery.id)
        assert updated.status == AddendumStatus.ARCHIVED

    def test_archives_blocked_ledger_delivery(self, client, tmp_path):
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        blocked = _make_delivery(
            status=AddendumStatus.BLOCKED, error="conflict"
        )
        store.append(blocked)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_archive(client, blocked.id)

        assert resp.status_code == 200
        updated = store.lookup_by_id(blocked.id)
        assert updated.status == AddendumStatus.ARCHIVED

    def test_archive_invalid_transition_in_review_returns_409(self, client, tmp_path):
        """Archiving an in_review delivery is invalid."""
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        in_review = _make_delivery(status=AddendumStatus.IN_REVIEW)
        store.append(in_review)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_archive(client, in_review.id)

        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "invalid_transition"

    def test_archive_posts_comment_on_source_task(self, client, tmp_path):
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        open_delivery = _make_delivery(status=AddendumStatus.OPEN)
        store.append(open_delivery)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            self._post_archive(client, open_delivery.id)

        tracker.add_comment.assert_called_once()

    def test_archive_not_found_returns_404(self, client, tmp_path):
        """When delivery not in ledger and not in legacy, returns 404."""
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_archive(client, "rd_nonexistent")

        assert resp.status_code == 404

    def test_archive_merged_delivery_invalid(self, client, tmp_path):
        """Cannot archive a merged delivery."""
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        merged = _make_delivery(status=AddendumStatus.MERGED)
        store.append(merged)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_archive(client, merged.id)

        assert resp.status_code == 409

    def test_archive_response_includes_full_delivery_list(self, client, tmp_path):
        tracker = _make_tracker_with_ledger(tmp_path)
        project = _make_project(tmp_path)
        store = ReleaseDeliveryStore(str(tmp_path), _PROJECT_ID, git_writer=tracker)
        d1 = _make_delivery(status=AddendumStatus.OPEN, target_branch="release/1.0")
        d2 = _make_delivery(
            delivery_id=_make_delivery_id(),
            status=AddendumStatus.IN_REVIEW,
            target_branch="release/1.1",
        )
        store.append(d1)
        store.append(d2)

        issue = _make_issue()
        tracker.fetch_issue_detail = MagicMock(return_value=issue)
        orch = MagicMock()
        orch._tracker_for_project = MagicMock(return_value=tracker)
        orch.project_store.list_all = MagicMock(return_value=[project])
        orch.project_store.get = MagicMock(return_value=project)
        orch.event_bus = EventBus()

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            resp = self._post_archive(client, d1.id)

        data = resp.json()
        assert resp.status_code == 200
        branches = {a["target_branch"] for a in data["addendums"]}
        assert "release/1.0" in branches
        assert "release/1.1" in branches
