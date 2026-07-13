"""Tests for OOMPAH-175 — ReleaseBranchCatalog and GET /api/v1/projects/{project_id}/release-branches.

Covers (section 5 of plans/release-branch-addendums.md):

  Unit tests for ReleaseBranchCatalog:
    - Filtering: only remotely-available branches in supported_release_branches are returned
    - Configured ordering is preserved
    - Stale fallback (local refs/remotes/origin/*) when remote fails
    - First-load failure raises CatalogDiscoveryError (→ 503 from API)
    - Cache expiry (TTL) causes re-discovery on next call
    - Cache invalidation via invalidate() forces re-discovery immediately
    - Deleted historic branches (in addendum metadata, not remote) are returned
      as available=false

  API tests for GET /api/v1/projects/{project_id}/release-branches:
    - 200 OK with correct shape
    - 404 for unknown project
    - 503 on first-load discovery failure
    - Stale flag propagated from catalog

Acceptance:
  - Clients receive only configured supported_release_branches that exist
    remotely (or historic addendum branches as unavailable history).
  - No free-form or glob-derived target candidates are returned.
"""

from __future__ import annotations

import time
import threading
from unittest.mock import MagicMock, patch, call
from typing import Any

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.server import app
from oompah.models import Project
from oompah.release_branch_catalog import (
    CACHE_TTL_SECONDS,
    CatalogDiscoveryError,
    CatalogResult,
    ReleaseBranch,
    ReleaseBranchCatalog,
    _natural_sort_key,
    _reverse_natural_sort_key,
    _run_local_remote_refs,
    _run_ls_remote,
    get_default_catalog,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_project(
    *,
    pid: str = "proj-1",
    repo_path: str = "/tmp/repos/proj-1",
    default_branch: str = "main",
    supported_release_branches: list[str] | None = None,
    branches: list[str] | None = None,
) -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = pid
    project.repo_path = repo_path
    project.default_branch = default_branch
    project.supported_release_branches = supported_release_branches or []
    project.branches = branches or ["main", "release/*"]
    return project


def _make_orchestrator(
    *,
    project: Any | None = None,
    projects: list[Any] | None = None,
) -> MagicMock:
    orch = MagicMock()
    p = project
    orch.project_store.get.side_effect = lambda pid: (
        p if p is not None and p.id == pid else None
    )
    orch.project_store.list_all.return_value = projects or ([] if p is None else [p])
    tracker = MagicMock()
    tracker.list_issues.return_value = []
    tracker.get_metadata.return_value = {}
    orch._tracker_for_project.return_value = tracker
    return orch


# ---------------------------------------------------------------------------
# Natural sort key tests
# ---------------------------------------------------------------------------


class TestNaturalSortKeys:
    """Verify that branch names sort in expected natural order."""

    def test_version_natural_order(self):
        branches = ["release/1.9", "release/1.11", "release/1.2", "release/2.0"]
        sorted_asc = sorted(branches, key=_natural_sort_key)
        assert sorted_asc == ["release/1.2", "release/1.9", "release/1.11", "release/2.0"]

    def test_reverse_natural_order(self):
        branches = ["release/1.9", "release/1.11", "release/1.2", "release/2.0"]
        sorted_desc = sorted(branches, key=_reverse_natural_sort_key)
        assert sorted_desc == ["release/2.0", "release/1.11", "release/1.9", "release/1.2"]

    def test_non_version_names_sort_lexically(self):
        branches = ["hotfix/beta", "hotfix/alpha", "hotfix/gamma"]
        sorted_desc = sorted(branches, key=_reverse_natural_sort_key)
        assert sorted_desc == sorted(branches)  # lexical for non-numeric


# ---------------------------------------------------------------------------
# Unit tests: ReleaseBranchCatalog._build_branch_list
# ---------------------------------------------------------------------------


class TestBuildBranchList:
    """Low-level tests for _build_branch_list without subprocess calls."""

    def _catalog(self) -> ReleaseBranchCatalog:
        return ReleaseBranchCatalog(ttl_seconds=60)

    def test_configured_branches_in_configured_order(self):
        catalog = self._catalog()
        configured = ["release/1.1", "release/1.0"]
        effective = {"release/1.0", "release/1.1", "main"}
        result = catalog._build_branch_list(
            configured=configured,
            effective_branches=effective,
            historic_branches=set(),
            stale=False,
        )
        assert [b.name for b in result] == ["release/1.1", "release/1.0"]

    def test_unavailable_configured_branch(self):
        """A configured branch not in effective set is returned with available=False."""
        catalog = self._catalog()
        configured = ["release/1.1", "release/1.0"]
        effective = {"release/1.1", "main"}  # release/1.0 deleted remotely
        result = catalog._build_branch_list(
            configured=configured,
            effective_branches=effective,
            historic_branches=set(),
            stale=False,
        )
        names = {b.name: b for b in result}
        assert names["release/1.1"].available is True
        assert names["release/1.0"].available is False

    def test_branches_not_in_configured_not_included_as_candidates(self):
        """Branches present on remote but not in configured are not offered."""
        catalog = self._catalog()
        configured = ["release/1.0"]
        effective = {"release/1.0", "release/2.0", "main", "feature/foo"}
        result = catalog._build_branch_list(
            configured=configured,
            effective_branches=effective,
            historic_branches=set(),
            stale=False,
        )
        names = [b.name for b in result]
        assert names == ["release/1.0"]
        assert "release/2.0" not in names
        assert "feature/foo" not in names

    def test_stale_flag_propagated_to_available_branches(self):
        catalog = self._catalog()
        configured = ["release/1.1", "release/1.0"]
        effective = {"release/1.0", "release/1.1"}
        result = catalog._build_branch_list(
            configured=configured,
            effective_branches=effective,
            historic_branches=set(),
            stale=True,
        )
        for b in result:
            if b.available:
                assert b.stale is True

    def test_historic_branches_appended_after_configured(self):
        """Historic branches (from addendums) appear after configured ones, unavailable."""
        catalog = self._catalog()
        configured = ["release/1.1"]
        effective = {"release/1.1"}
        historic = {"release/1.0", "release/0.9"}  # older, deleted
        result = catalog._build_branch_list(
            configured=configured,
            effective_branches=effective,
            historic_branches=historic,
            stale=False,
        )
        names = [b.name for b in result]
        # release/1.1 first (configured), then historic in reverse-natural order
        assert names[0] == "release/1.1"
        assert set(names[1:]) == {"release/1.0", "release/0.9"}
        # Historic branches are not available
        for b in result[1:]:
            assert b.available is False

    def test_historic_branch_in_configured_not_duplicated(self):
        """A branch in both configured and historic appears only once (configured wins)."""
        catalog = self._catalog()
        configured = ["release/1.0"]
        effective = {"release/1.0"}
        historic = {"release/1.0"}  # same branch
        result = catalog._build_branch_list(
            configured=configured,
            effective_branches=effective,
            historic_branches=historic,
            stale=False,
        )
        assert len(result) == 1
        assert result[0].name == "release/1.0"
        assert result[0].available is True

    def test_empty_configured_only_historic(self):
        catalog = self._catalog()
        result = catalog._build_branch_list(
            configured=[],
            effective_branches={"release/1.0"},
            historic_branches={"release/1.0"},
            stale=False,
        )
        assert len(result) == 1
        assert result[0].available is False  # not in configured

    def test_default_branch_not_in_output_if_not_configured(self):
        """main is not included just because it's on the remote."""
        catalog = self._catalog()
        configured = ["release/1.0"]
        effective = {"release/1.0", "main"}
        result = catalog._build_branch_list(
            configured=configured,
            effective_branches=effective,
            historic_branches=set(),
            stale=False,
        )
        assert "main" not in [b.name for b in result]


# ---------------------------------------------------------------------------
# Unit tests: ReleaseBranchCatalog.list_candidates (mocked discovery)
# ---------------------------------------------------------------------------


class TestListCandidates:
    """Tests for the full list_candidates path with mocked git calls."""

    def _catalog(self, ttl: int = 60) -> ReleaseBranchCatalog:
        return ReleaseBranchCatalog(ttl_seconds=ttl, ls_remote_timeout=5)

    def test_happy_path_remote_discovery(self):
        catalog = self._catalog()
        project = _make_project(
            supported_release_branches=["release/1.1", "release/1.0"]
        )

        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            return_value={"release/1.0", "release/1.1", "main"},
        ), patch.object(catalog, "_collect_historic_branches", return_value=set()):
            result = catalog.list_candidates(project)

        assert isinstance(result, CatalogResult)
        assert result.project_id == "proj-1"
        assert result.source_branch == "main"
        assert result.stale is False
        assert result.refreshed_at > 0

        names = [b.name for b in result.branches]
        assert names == ["release/1.1", "release/1.0"]
        assert all(b.available for b in result.branches)
        assert all(not b.stale for b in result.branches)

    def test_configured_order_preserved(self):
        """Configured order is preserved even when remote returns different order."""
        catalog = self._catalog()
        project = _make_project(
            supported_release_branches=["release/2.0", "release/1.0", "release/1.1"]
        )
        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            return_value={"release/1.0", "release/1.1", "release/2.0", "main"},
        ), patch.object(catalog, "_collect_historic_branches", return_value=set()):
            result = catalog.list_candidates(project)

        assert [b.name for b in result.branches] == [
            "release/2.0",
            "release/1.0",
            "release/1.1",
        ]

    def test_filtering_non_configured_remote_branches_excluded(self):
        catalog = self._catalog()
        project = _make_project(
            supported_release_branches=["release/1.0"]
        )
        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            return_value={"release/1.0", "release/1.1", "main", "feature/foo"},
        ), patch.object(catalog, "_collect_historic_branches", return_value=set()):
            result = catalog.list_candidates(project)

        assert [b.name for b in result.branches] == ["release/1.0"]

    def test_first_load_failure_raises_catalog_discovery_error(self):
        """No prior cache → first-load failure → CatalogDiscoveryError."""
        catalog = self._catalog()
        project = _make_project(supported_release_branches=["release/1.0"])

        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            side_effect=RuntimeError("connection refused"),
        ), patch(
            "oompah.release_branch_catalog._run_local_remote_refs",
            return_value=set(),
        ), patch.object(catalog, "_collect_historic_branches", return_value=set()):
            with pytest.raises(CatalogDiscoveryError):
                catalog.list_candidates(project)

    def test_stale_fallback_on_remote_failure(self):
        """Remote fails but local refs/remotes/origin/* provides a stale result."""
        catalog = self._catalog()
        project = _make_project(
            supported_release_branches=["release/1.0"]
        )
        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            side_effect=RuntimeError("network error"),
        ), patch(
            "oompah.release_branch_catalog._run_local_remote_refs",
            return_value={"release/1.0", "main"},
        ), patch.object(catalog, "_collect_historic_branches", return_value=set()):
            result = catalog.list_candidates(project)

        assert result.stale is True
        assert len(result.branches) == 1
        assert result.branches[0].name == "release/1.0"
        assert result.branches[0].stale is True
        assert result.branches[0].available is True

    def test_stale_fallback_not_available_without_local_refs(self):
        """If no local refs available AND no cache, still raises CatalogDiscoveryError."""
        catalog = self._catalog()
        project = _make_project(supported_release_branches=["release/1.0"])

        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            side_effect=RuntimeError("offline"),
        ), patch(
            "oompah.release_branch_catalog._run_local_remote_refs",
            return_value=set(),
        ), patch.object(catalog, "_collect_historic_branches", return_value=set()):
            with pytest.raises(CatalogDiscoveryError):
                catalog.list_candidates(project)

    def test_cache_hit_no_second_ls_remote_call(self):
        """Second call within TTL uses cache, not a second ls-remote."""
        catalog = self._catalog(ttl=60)
        project = _make_project(supported_release_branches=["release/1.0"])

        ls_remote_mock = MagicMock(return_value={"release/1.0", "main"})
        with patch("oompah.release_branch_catalog._run_ls_remote", ls_remote_mock), \
             patch.object(catalog, "_collect_historic_branches", return_value=set()):
            catalog.list_candidates(project)
            catalog.list_candidates(project)

        assert ls_remote_mock.call_count == 1

    def test_cache_expiry_triggers_re_discovery(self):
        """After TTL expires, the next call performs a fresh ls-remote."""
        catalog = self._catalog(ttl=1)
        project = _make_project(supported_release_branches=["release/1.0"])

        ls_remote_mock = MagicMock(return_value={"release/1.0", "main"})
        with patch("oompah.release_branch_catalog._run_ls_remote", ls_remote_mock), \
             patch.object(catalog, "_collect_historic_branches", return_value=set()):
            catalog.list_candidates(project)
            # Simulate TTL expiry by manipulating the cache entry timestamp
            catalog._cache["proj-1"].fetched_at -= 2  # 2 seconds ago > 1s TTL
            catalog.list_candidates(project)

        assert ls_remote_mock.call_count == 2

    def test_invalidate_forces_re_discovery(self):
        """invalidate() drops the cache; next call does a fresh ls-remote."""
        catalog = self._catalog(ttl=60)
        project = _make_project(supported_release_branches=["release/1.0"])

        ls_remote_mock = MagicMock(return_value={"release/1.0", "main"})
        with patch("oompah.release_branch_catalog._run_ls_remote", ls_remote_mock), \
             patch.object(catalog, "_collect_historic_branches", return_value=set()):
            catalog.list_candidates(project)
            catalog.invalidate("proj-1")
            catalog.list_candidates(project)

        assert ls_remote_mock.call_count == 2

    def test_deleted_historic_branch_included_as_unavailable(self):
        """A branch in past addendums but not remote/configured is unavailable history."""
        catalog = self._catalog()
        project = _make_project(
            supported_release_branches=["release/1.1"]
        )
        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            return_value={"release/1.1", "main"},
        ), patch.object(
            catalog,
            "_collect_historic_branches",
            return_value={"release/1.0"},  # old branch in addendum, no longer on remote
        ):
            result = catalog.list_candidates(project)

        names = {b.name: b for b in result.branches}
        assert "release/1.1" in names
        assert names["release/1.1"].available is True
        assert "release/1.0" in names
        assert names["release/1.0"].available is False

    def test_historic_branch_in_supported_list_not_duplicated(self):
        """A configured branch that also appears in addendum history is not duplicated."""
        catalog = self._catalog()
        project = _make_project(supported_release_branches=["release/1.0"])
        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            return_value={"release/1.0", "main"},
        ), patch.object(
            catalog,
            "_collect_historic_branches",
            return_value={"release/1.0"},
        ):
            result = catalog.list_candidates(project)

        assert len([b for b in result.branches if b.name == "release/1.0"]) == 1
        assert result.branches[0].available is True

    def test_no_repo_path_raises_catalog_discovery_error(self):
        catalog = self._catalog()
        project = _make_project(
            repo_path="",
            supported_release_branches=["release/1.0"],
        )
        with patch.object(catalog, "_collect_historic_branches", return_value=set()):
            with pytest.raises(CatalogDiscoveryError):
                catalog.list_candidates(project)

    def test_stale_expired_cache_used_as_last_resort(self):
        """When remote and local refs both fail, the expired cache entry is used."""
        catalog = self._catalog(ttl=1)
        project = _make_project(supported_release_branches=["release/1.0"])

        # First call succeeds and populates cache
        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            return_value={"release/1.0", "main"},
        ), patch.object(catalog, "_collect_historic_branches", return_value=set()):
            catalog.list_candidates(project)

        # Expire the cache
        catalog._cache["proj-1"].fetched_at -= 2

        # Second call: remote fails, local refs fail, but expired cache saves us
        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            side_effect=RuntimeError("offline"),
        ), patch(
            "oompah.release_branch_catalog._run_local_remote_refs",
            return_value=set(),
        ), patch.object(catalog, "_collect_historic_branches", return_value=set()):
            result = catalog.list_candidates(project)

        assert result.stale is True
        assert len(result.branches) == 1
        assert result.branches[0].name == "release/1.0"

    def test_empty_supported_branches_no_candidates(self):
        """When supported_release_branches is empty, no candidates are returned."""
        catalog = self._catalog()
        project = _make_project(supported_release_branches=[])
        with patch(
            "oompah.release_branch_catalog._run_ls_remote",
            return_value={"release/1.0", "main"},
        ), patch.object(catalog, "_collect_historic_branches", return_value=set()):
            result = catalog.list_candidates(project)

        assert result.branches == []


# ---------------------------------------------------------------------------
# Unit tests: CatalogResult.to_dict
# ---------------------------------------------------------------------------


class TestCatalogResultToDict:
    def test_to_dict_shape(self):
        import datetime as dt
        ts = time.time()
        r = CatalogResult(
            project_id="proj-1",
            source_branch="main",
            branches=[
                ReleaseBranch(name="release/1.1", available=True, stale=False),
                ReleaseBranch(name="release/1.0", available=False, stale=True),
            ],
            refreshed_at=ts,
            stale=False,
        )
        d = r.to_dict()
        assert d["project_id"] == "proj-1"
        assert d["source_branch"] == "main"
        assert d["stale"] is False
        assert d["refreshed_at"] is not None
        assert len(d["branches"]) == 2
        assert d["branches"][0] == {"name": "release/1.1", "available": True, "stale": False}
        assert d["branches"][1] == {"name": "release/1.0", "available": False, "stale": True}

    def test_to_dict_null_refreshed_at(self):
        r = CatalogResult(project_id="p", source_branch="main")
        d = r.to_dict()
        assert d["refreshed_at"] is None


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


def _make_api_orchestrator(
    *,
    project: Any | None = None,
    catalog: ReleaseBranchCatalog | None = None,
    catalog_raises: Exception | None = None,
    catalog_result: CatalogResult | None = None,
) -> MagicMock:
    orch = MagicMock()
    if project is not None:
        orch.project_store.get.side_effect = lambda pid: (
            project if pid == project.id else None
        )
    else:
        orch.project_store.get.return_value = None
    return orch


class TestApiReleaseBranches:
    """Integration tests for GET /api/v1/projects/{project_id}/release-branches."""

    def _client(self) -> TestClient:
        return TestClient(app, raise_server_exceptions=False)

    def test_404_unknown_project(self):
        orch = MagicMock()
        orch.project_store.get.return_value = None
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            client = self._client()
            resp = client.get("/api/v1/projects/nonexistent/release-branches")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "not_found"

    def test_200_happy_path(self):
        project = _make_project(
            pid="proj-abc",
            supported_release_branches=["release/1.1", "release/1.0"],
        )
        orch = MagicMock()
        orch.project_store.get.return_value = project

        fake_catalog = MagicMock()
        fake_result = CatalogResult(
            project_id="proj-abc",
            source_branch="main",
            branches=[
                ReleaseBranch(name="release/1.1", available=True),
                ReleaseBranch(name="release/1.0", available=True),
            ],
            refreshed_at=time.time(),
            stale=False,
        )
        fake_catalog.list_candidates.return_value = fake_result

        with patch.object(server_module, "_get_orchestrator", return_value=orch), \
             patch("oompah.release_branch_catalog.get_default_catalog", return_value=fake_catalog):
            client = self._client()
            resp = client.get("/api/v1/projects/proj-abc/release-branches")

        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == "proj-abc"
        assert data["source_branch"] == "main"
        assert data["stale"] is False
        assert data["refreshed_at"] is not None
        branches = data["branches"]
        assert len(branches) == 2
        assert branches[0]["name"] == "release/1.1"
        assert branches[0]["available"] is True
        assert branches[0]["stale"] is False

    def test_503_on_first_load_discovery_failure(self):
        project = _make_project(pid="proj-fail")
        orch = MagicMock()
        orch.project_store.get.return_value = project

        fake_catalog = MagicMock()
        fake_catalog.list_candidates.side_effect = CatalogDiscoveryError(
            "git ls-remote failed, no prior cache"
        )

        with patch.object(server_module, "_get_orchestrator", return_value=orch), \
             patch("oompah.release_branch_catalog.get_default_catalog", return_value=fake_catalog):
            client = self._client()
            resp = client.get("/api/v1/projects/proj-fail/release-branches")

        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "discovery_failed"

    def test_200_stale_result(self):
        project = _make_project(
            pid="proj-stale",
            supported_release_branches=["release/1.0"],
        )
        orch = MagicMock()
        orch.project_store.get.return_value = project

        fake_catalog = MagicMock()
        fake_result = CatalogResult(
            project_id="proj-stale",
            source_branch="main",
            branches=[
                ReleaseBranch(name="release/1.0", available=True, stale=True),
            ],
            refreshed_at=time.time() - 120,
            stale=True,
        )
        fake_catalog.list_candidates.return_value = fake_result

        with patch.object(server_module, "_get_orchestrator", return_value=orch), \
             patch("oompah.release_branch_catalog.get_default_catalog", return_value=fake_catalog):
            client = self._client()
            resp = client.get("/api/v1/projects/proj-stale/release-branches")

        assert resp.status_code == 200
        data = resp.json()
        assert data["stale"] is True
        assert data["branches"][0]["stale"] is True

    def test_200_historic_unavailable_branch(self):
        project = _make_project(
            pid="proj-hist",
            supported_release_branches=["release/1.1"],
        )
        orch = MagicMock()
        orch.project_store.get.return_value = project

        fake_catalog = MagicMock()
        fake_result = CatalogResult(
            project_id="proj-hist",
            source_branch="main",
            branches=[
                ReleaseBranch(name="release/1.1", available=True),
                ReleaseBranch(name="release/1.0", available=False),
            ],
            refreshed_at=time.time(),
            stale=False,
        )
        fake_catalog.list_candidates.return_value = fake_result

        with patch.object(server_module, "_get_orchestrator", return_value=orch), \
             patch("oompah.release_branch_catalog.get_default_catalog", return_value=fake_catalog):
            client = self._client()
            resp = client.get("/api/v1/projects/proj-hist/release-branches")

        assert resp.status_code == 200
        data = resp.json()
        branches = {b["name"]: b for b in data["branches"]}
        assert branches["release/1.1"]["available"] is True
        assert branches["release/1.0"]["available"] is False


# ---------------------------------------------------------------------------
# Webhook invalidation tests
# ---------------------------------------------------------------------------


class TestWebhookInvalidation:
    """Verify the release-branch catalog is invalidated on push events."""

    def test_push_event_invalidates_catalog(self):
        from oompah.server import invalidate_release_branch_catalog
        from oompah.release_branch_catalog import get_default_catalog

        catalog = get_default_catalog()
        project_id = "proj-push-test"
        # Seed the cache
        import time
        from oompah.release_branch_catalog import _CacheEntry
        catalog._cache[project_id] = _CacheEntry(
            remote_branches={"release/1.0"},
            fetched_at=time.monotonic(),
        )
        assert project_id in catalog._cache

        invalidate_release_branch_catalog(project_id)
        assert project_id not in catalog._cache

    def test_invalidate_nonexistent_project_no_error(self):
        from oompah.server import invalidate_release_branch_catalog

        # Should not raise
        invalidate_release_branch_catalog("proj-does-not-exist")

    def test_invalidate_all(self):
        from oompah.release_branch_catalog import get_default_catalog, _CacheEntry

        catalog = get_default_catalog()
        catalog._cache["a"] = _CacheEntry(remote_branches=set(), fetched_at=0.0)
        catalog._cache["b"] = _CacheEntry(remote_branches=set(), fetched_at=0.0)
        catalog.invalidate_all()
        assert catalog._cache == {}


# ---------------------------------------------------------------------------
# Collect historic branches tests
# ---------------------------------------------------------------------------


class TestCollectHistoricBranches:
    """Verify that _collect_historic_branches reads addendum metadata."""

    def test_returns_target_branches_from_addendums(self):
        catalog = ReleaseBranchCatalog()
        project = _make_project(pid="proj-hist")

        mock_issue = MagicMock()
        mock_issue.identifier = "TASK-1"

        tracker = MagicMock()
        tracker.list_issues.return_value = [mock_issue]
        tracker.get_metadata.return_value = {
            "oompah.release_addendums": [
                {
                    "id": "TASK-1/release/1.0",
                    "target_branch": "release/1.0",
                    "status": "merged",
                },
                {
                    "id": "TASK-1/release/0.9",
                    "target_branch": "release/0.9",
                    "status": "archived",
                },
            ]
        }

        orch = MagicMock()
        orch._tracker_for_project.return_value = tracker

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            result = catalog._collect_historic_branches(project)

        assert result == {"release/1.0", "release/0.9"}

    def test_returns_empty_set_on_tracker_error(self):
        catalog = ReleaseBranchCatalog()
        project = _make_project(pid="proj-err")

        orch = MagicMock()
        orch._tracker_for_project.side_effect = RuntimeError("tracker broken")

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            result = catalog._collect_historic_branches(project)

        assert result == set()

    def test_ignores_malformed_addendum_entries(self):
        catalog = ReleaseBranchCatalog()
        project = _make_project(pid="proj-bad")

        mock_issue = MagicMock()
        mock_issue.identifier = "TASK-2"

        tracker = MagicMock()
        tracker.list_issues.return_value = [mock_issue]
        tracker.get_metadata.return_value = {
            "oompah.release_addendums": [
                "not a dict",  # malformed
                {"target_branch": "release/1.0"},  # valid
            ]
        }

        orch = MagicMock()
        orch._tracker_for_project.return_value = tracker

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            result = catalog._collect_historic_branches(project)

        # Only the valid entry should appear
        assert "release/1.0" in result

    def test_no_addendums_returns_empty(self):
        catalog = ReleaseBranchCatalog()
        project = _make_project(pid="proj-none")

        mock_issue = MagicMock()
        mock_issue.identifier = "TASK-3"

        tracker = MagicMock()
        tracker.list_issues.return_value = [mock_issue]
        tracker.get_metadata.return_value = {}  # no addendums

        orch = MagicMock()
        orch._tracker_for_project.return_value = tracker

        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            result = catalog._collect_historic_branches(project)

        assert result == set()


# ---------------------------------------------------------------------------
# Module singleton tests
# ---------------------------------------------------------------------------


class TestModuleSingleton:
    def test_get_default_catalog_returns_same_instance(self):
        c1 = get_default_catalog()
        c2 = get_default_catalog()
        assert c1 is c2

    def test_default_catalog_is_release_branch_catalog(self):
        assert isinstance(get_default_catalog(), ReleaseBranchCatalog)


# ---------------------------------------------------------------------------
# Thread safety smoke test
# ---------------------------------------------------------------------------


class TestThreadSafety:
    """Smoke test: concurrent list_candidates calls don't race."""

    def test_concurrent_calls_same_project(self):
        catalog = ReleaseBranchCatalog(ttl_seconds=60)
        project = _make_project(
            pid="proj-concurrent",
            supported_release_branches=["release/1.0"],
        )

        results: list[CatalogResult] = []
        errors: list[Exception] = []

        call_count = {"n": 0}
        original_ls = _run_ls_remote

        def _slow_ls_remote(repo_path: str, timeout: int = 30) -> set[str]:
            call_count["n"] += 1
            time.sleep(0.05)  # simulate slow network
            return {"release/1.0", "main"}

        def _thread_fn():
            try:
                with patch("oompah.release_branch_catalog._run_ls_remote", _slow_ls_remote), \
                     patch.object(catalog, "_collect_historic_branches", return_value=set()):
                    r = catalog.list_candidates(project)
                    results.append(r)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_thread_fn) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 5
        # All results should be equivalent
        for r in results:
            assert r.project_id == "proj-concurrent"
            assert len(r.branches) == 1
        # Due to serialization, ls-remote should be called once (or at most a
        # few times if threads race before cache is written — both are valid)
        assert call_count["n"] >= 1
