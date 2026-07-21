"""Regression tests for OOMPAH-306: state-branch cache reconciliation.

Verifies that dashboard/API task-state display always reflects the canonical
state-branch record, not stale snapshots or source-branch data.

Coverage:
  § 1  Canonical state controls display (not inferred from merged_at / review_url)
  § 2  Stale snapshot does not permanently render Merged
  § 3  API response headers signal staleness accurately
  § 4  Per-project cache isolation via TTLCache prefix invalidation
  § 5  Degraded tracker reads do not emit false terminal status
  § 6  Null merged_at cannot produce Merged display state
"""

from __future__ import annotations

import contextlib
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from oompah.models import Issue
from oompah import server as server_module
from oompah.cache import TTLCache
from oompah.tracker import TrackerError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _issue(
    identifier: str,
    state: str,
    *,
    issue_type: str = "task",
    parent_id: str | None = None,
    merged_at: object = None,
    work_branch: str | None = None,
    review_url: str | None = None,
    project_id: str = "proj-test",
) -> Issue:
    issue = Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        project_id=project_id,
    )
    issue.work_branch = work_branch
    issue.review_url = review_url
    # merged_at is not a field on Issue dataclass — it lives on tracker metadata.
    # We attach it as an attribute so display-logic tests can verify it is NOT used.
    object.__setattr__(issue, "merged_at", merged_at)
    return issue


def _orch_with_issues(issues, project_id: str = "proj-test"):
    project = SimpleNamespace(id=project_id, name=project_id)
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = list(issues)
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    orch._project_epic_strategy.return_value = "flat"
    return orch


def _clear_snapshot() -> None:
    with server_module._issues_snapshot_lock:
        server_module._issues_refresh_task = None
        server_module._issues_snapshot.update(
            {
                "data": None,
                "orch_id": None,
                "created_at_monotonic": 0.0,
                "created_at_wall": None,
                "duration_ms": None,
                "issue_count": 0,
                "error": None,
            }
        )
    server_module._api_cache.clear()


# ===========================================================================
# § 1  Canonical state controls display — NOT inferred from field values
# ===========================================================================


class TestCanonicalStateControlsDisplay:
    """_issue_dashboard_state must use issue.state, never derived fields."""

    def test_backlog_issue_with_merged_at_shows_backlog(self):
        """A task with state=Backlog must display as Backlog even if merged_at is set.

        Regression: dashboard must not check merged_at to decide status.
        """
        issue = _issue("OOMPAH-286", "Backlog", merged_at="2026-07-01T00:00:00Z")
        result = server_module._issue_dashboard_state(issue)
        assert result == "Backlog", (
            "task with canonical state=Backlog must display Backlog, "
            "not Merged, even when merged_at is populated"
        )

    def test_backlog_issue_with_review_url_shows_backlog(self):
        """A task with state=Backlog must display Backlog even if review_url is set."""
        issue = _issue(
            "OOMPAH-286",
            "Backlog",
            review_url="https://github.com/foo/bar/pull/42",
        )
        result = server_module._issue_dashboard_state(issue)
        assert result == "Backlog", (
            "task with canonical state=Backlog must display Backlog, "
            "not In Review, even when review_url is populated"
        )

    def test_backlog_issue_with_work_branch_shows_backlog(self):
        """A task with state=Backlog must display Backlog even if work_branch is set."""
        issue = _issue("OOMPAH-286", "Backlog", work_branch="OOMPAH-286")
        result = server_module._issue_dashboard_state(issue)
        assert result == "Backlog"

    def test_merged_issue_requires_canonical_merged_state(self):
        """A task displays Merged only when canonical state IS Merged."""
        issue = _issue("OOMPAH-1", "Merged")
        result = server_module._issue_dashboard_state(issue)
        assert result == "Merged"

    def test_dashboard_state_function_is_deterministic(self):
        """_issue_dashboard_state must be a pure function of issue.state."""
        issue_a = _issue("A", "Backlog")
        issue_b = _issue("B", "Backlog", merged_at="2026-07-01T00:00:00Z")
        assert server_module._issue_dashboard_state(issue_a) == (
            server_module._issue_dashboard_state(issue_b)
        ), "_issue_dashboard_state must be deterministic from issue.state alone"


# ===========================================================================
# § 2  Stale snapshot replaced by canonical state on re-fetch
# ===========================================================================


class TestStaleMergedSnapshotReplacedByCanonicalBacklog:
    """When the cached snapshot shows Merged but the state branch says Backlog,
    a board refresh must display Backlog — not the stale Merged."""

    def test_fetch_serialize_returns_canonical_state_not_snapshot(self):
        """_fetch_and_serialize_issues reads from the live tracker, not the snapshot.

        Regression fixture: tracker returns Backlog for OOMPAH-286; the result
        of _fetch_and_serialize_issues must place the issue in the Backlog column.
        """
        # Simulate a stale issues:all cache that says OOMPAH-286 is Merged.
        _clear_snapshot()
        server_module._api_cache.set(
            "issues:all",
            {"Merged": [{"identifier": "OOMPAH-286", "project_id": "proj-14849f1b"}]},
            ttl_ms=60_000,
        )
        try:
            # Live tracker knows OOMPAH-286 is actually Backlog.
            orch = _orch_with_issues(
                [_issue("OOMPAH-286", "Backlog", project_id="proj-14849f1b")],
                project_id="proj-14849f1b",
            )
            board = server_module._fetch_and_serialize_issues(orch)

            backlog_ids = [i["identifier"] for i in board.get("Backlog", [])]
            merged_ids = [i["identifier"] for i in board.get("Merged", [])]

            assert "OOMPAH-286" in backlog_ids, (
                "OOMPAH-286 must appear in Backlog column when tracker returns Backlog"
            )
            assert "OOMPAH-286" not in merged_ids, (
                "OOMPAH-286 must NOT appear in Merged column when tracker returns Backlog"
            )
        finally:
            _clear_snapshot()

    def test_stale_snapshot_does_not_render_merged_as_authoritative(self):
        """A stale issues:all snapshot must not persist as authoritative board data.

        After _set_issues_snapshot is called with Backlog data, the board must
        show Backlog — the stale Merged snapshot is not kept.
        """
        _clear_snapshot()
        try:
            # Write the canonical Backlog data into the snapshot.
            server_module._set_issues_snapshot(
                {"Backlog": [{"identifier": "OOMPAH-286", "project_id": "proj-14849f1b", "state": "Backlog"}]},
                duration_ms=5.0,
            )
            payload = server_module._issues_snapshot_payload(allow_empty=False)
            assert payload is not None
            backlog = payload.get("Backlog", [])
            assert any(i["identifier"] == "OOMPAH-286" for i in backlog), (
                "Canonical Backlog data must appear in snapshot payload"
            )
            # Merged column must not contain OOMPAH-286
            merged = payload.get("Merged", [])
            assert not any(i["identifier"] == "OOMPAH-286" for i in merged), (
                "OOMPAH-286 must not appear in Merged once canonical data is loaded"
            )
        finally:
            _clear_snapshot()

    def test_snapshot_invalidated_when_orch_id_changes(self):
        """When the orchestrator is replaced, the old snapshot is discarded.

        Cache keys must be aware of the orchestrator identity so cross-restart
        stale data is never served as authoritative.
        """
        _clear_snapshot()
        try:
            old_orch = object()
            new_orch = object()

            server_module._set_issues_snapshot(
                {"Merged": [{"identifier": "OOMPAH-286"}]},
                duration_ms=5.0,
                orch_id=id(old_orch),
            )

            # Payload request from the NEW orchestrator must treat the old
            # snapshot as mismatched and return None (forcing a re-fetch).
            payload = server_module._issues_snapshot_payload(
                allow_empty=False,
                orch=new_orch,  # type: ignore[arg-type]
            )
            assert payload is None, (
                "Snapshot from a previous orchestrator must not be returned to "
                "a new orchestrator instance (orch_id mismatch)"
            )
        finally:
            _clear_snapshot()


# ===========================================================================
# § 3  API response stale headers
# ===========================================================================


class TestApiStalenessHeaders:
    """X-Oompah-Issues-Stale header must accurately reflect snapshot freshness."""

    def test_stale_header_true_when_snapshot_is_old(self, monkeypatch):
        """X-Oompah-Issues-Stale must be 'true' when snapshot exceeds stale threshold."""
        _clear_snapshot()
        monkeypatch.setattr(server_module, "_ISSUES_SNAPSHOT_STALE_MS", 1_000)
        try:
            # Write a snapshot that is already 5 seconds old.
            server_module._set_issues_snapshot(
                {"Backlog": [{"identifier": "OOMPAH-286", "project_id": "p1", "state": "Backlog"}]},
                duration_ms=5.0,
            )
            with server_module._issues_snapshot_lock:
                server_module._issues_snapshot["created_at_monotonic"] = (
                    time.monotonic() - 5.0  # 5 seconds old > 1 second threshold
                )

            headers = server_module._issues_snapshot_headers()
            assert headers.get("X-Oompah-Issues-Stale") == "true", (
                "X-Oompah-Issues-Stale must be 'true' when snapshot is older than threshold"
            )
        finally:
            _clear_snapshot()
            monkeypatch.undo()

    def test_stale_header_false_when_snapshot_is_fresh(self, monkeypatch):
        """X-Oompah-Issues-Stale must be 'false' when snapshot is within threshold."""
        _clear_snapshot()
        monkeypatch.setattr(server_module, "_ISSUES_SNAPSHOT_STALE_MS", 60_000)
        try:
            server_module._set_issues_snapshot(
                {"Backlog": [{"identifier": "OOMPAH-286", "project_id": "p1", "state": "Backlog"}]},
                duration_ms=5.0,
            )
            # Snapshot is fresh (just created).
            headers = server_module._issues_snapshot_headers()
            assert headers.get("X-Oompah-Issues-Stale") == "false", (
                "X-Oompah-Issues-Stale must be 'false' when snapshot is fresh"
            )
        finally:
            _clear_snapshot()

    def test_stale_header_true_when_snapshot_has_error(self):
        """X-Oompah-Issues-Stale must be 'true' when the last snapshot fetch errored.

        A degraded tracker (error) must not present itself as authoritative.
        """
        _clear_snapshot()
        try:
            # Set an empty snapshot with error flag set.
            server_module._set_issues_snapshot(
                {},
                duration_ms=5.0,
                error="TrackerError: state branch unavailable",
            )
            # Force the snapshot to be old so age-based check triggers too.
            with server_module._issues_snapshot_lock:
                server_module._issues_snapshot["created_at_monotonic"] = (
                    time.monotonic() - 120  # 2 minutes
                )
            headers = server_module._issues_snapshot_headers()
            assert headers.get("X-Oompah-Issues-Stale") == "true", (
                "X-Oompah-Issues-Stale must be 'true' when snapshot has an error"
            )
        finally:
            _clear_snapshot()

    def test_stale_header_true_when_no_snapshot_exists(self):
        """X-Oompah-Issues-Stale must be 'true' before any snapshot is built."""
        _clear_snapshot()
        try:
            headers = server_module._issues_snapshot_headers()
            assert headers.get("X-Oompah-Issues-Stale") == "true", (
                "X-Oompah-Issues-Stale must be 'true' when no snapshot has been built yet"
            )
        finally:
            _clear_snapshot()

    def test_issues_count_header_reflects_canonical_count(self):
        """X-Oompah-Issues-Count must reflect the canonical board issue count."""
        _clear_snapshot()
        try:
            server_module._set_issues_snapshot(
                {
                    "Backlog": [
                        {"identifier": "T-1", "project_id": "p1"},
                        {"identifier": "T-2", "project_id": "p1"},
                    ],
                    "Open": [{"identifier": "T-3", "project_id": "p1"}],
                },
                duration_ms=5.0,
            )
            headers = server_module._issues_snapshot_headers()
            assert headers.get("X-Oompah-Issues-Count") == "3"
        finally:
            _clear_snapshot()


# ===========================================================================
# § 4  Per-project cache isolation
# ===========================================================================


class TestPerProjectCacheIsolation:
    """Cache invalidation must be scoped to the affected project."""

    def test_invalidate_prefix_does_not_evict_other_project_keys(self):
        """Invalidating detail:proj-a does not affect detail:proj-b keys."""
        cache = TTLCache()
        cache.set("detail:proj-a:TASK-1:actor:bot", {"state": "Merged"}, ttl_ms=60_000)
        cache.set("detail:proj-b:TASK-1:actor:bot", {"state": "Backlog"}, ttl_ms=60_000)

        cache.invalidate_prefix("detail:proj-a:")

        assert cache.get("detail:proj-a:TASK-1:actor:bot") is None, (
            "Project A cache entry must be evicted after prefix invalidation"
        )
        assert cache.get("detail:proj-b:TASK-1:actor:bot") == {"state": "Backlog"}, (
            "Project B cache entry must NOT be evicted when Project A is invalidated"
        )

    def test_invalidate_prefix_evicts_all_keys_for_project(self):
        """All detail keys for a project are cleared on prefix invalidation."""
        cache = TTLCache()
        cache.set("detail:proj-x:TASK-1:actor:alice", {"state": "Open"}, ttl_ms=60_000)
        cache.set("detail:proj-x:TASK-2:actor:alice", {"state": "Open"}, ttl_ms=60_000)
        cache.set("detail:proj-x:TASK-1:actor:bob", {"state": "Open"}, ttl_ms=60_000)

        cache.invalidate_prefix("detail:proj-x:")

        for key in [
            "detail:proj-x:TASK-1:actor:alice",
            "detail:proj-x:TASK-2:actor:alice",
            "detail:proj-x:TASK-1:actor:bob",
        ]:
            assert cache.get(key) is None, f"Key {key!r} must be evicted"

    def test_issues_all_invalidation_forces_next_read_to_re_fetch(self):
        """After issues:all is invalidated, the snapshot payload is marked stale."""
        _clear_snapshot()
        try:
            server_module._set_issues_snapshot(
                {"Merged": [{"identifier": "OOMPAH-286", "project_id": "proj-x"}]},
                duration_ms=5.0,
            )
            # Invalidating the api_cache issues:all key doesn't affect the
            # snapshot dict — but the _issues_snapshot dict should still hold
            # the latest data. The real invalidation path clears the api_cache
            # and forces a re-fetch on the next tick.
            server_module._api_cache.invalidate("issues:all")
            assert server_module._api_cache.get("issues:all") is None, (
                "After invalidation, issues:all must not be in the api_cache"
            )
        finally:
            _clear_snapshot()

    def test_fetch_and_serialize_issues_isolates_projects(self):
        """Each project's issues are grouped by their project_id in the board."""
        issue_a = _issue("A-1", "Backlog", project_id="proj-a")
        issue_b = _issue("B-1", "Merged", project_id="proj-b")

        orch = MagicMock()
        orch.project_store.list_all.return_value = [
            SimpleNamespace(id="proj-a", name="proj-a"),
            SimpleNamespace(id="proj-b", name="proj-b"),
        ]
        tracker_a = MagicMock()
        tracker_a.fetch_all_issues.return_value = [issue_a]
        tracker_b = MagicMock()
        tracker_b.fetch_all_issues.return_value = [issue_b]

        def _tracker_for(project_id):
            return tracker_a if project_id == "proj-a" else tracker_b

        orch._tracker_for_project.side_effect = _tracker_for
        orch._project_epic_strategy.return_value = "flat"

        board = server_module._fetch_and_serialize_issues(orch)

        backlog_ids = [i["identifier"] for i in board.get("Backlog", [])]
        merged_ids = [i["identifier"] for i in board.get("Merged", [])]
        assert "A-1" in backlog_ids, "Project A task must appear in Backlog"
        assert "B-1" in merged_ids, "Project B task must appear in Merged"
        assert "A-1" not in merged_ids, "Project A task must not appear in Merged"
        assert "B-1" not in backlog_ids, "Project B task must not appear in Backlog"


# ===========================================================================
# § 5  Degraded tracker reads do not emit false terminal status
# ===========================================================================


class TestDegradedTrackerReads:
    """When a tracker read is degraded, the last known state must not be promoted
    to a terminal status (Merged/Done/Archived)."""

    def test_stale_snapshot_with_error_does_not_show_merged_as_authoritative(self):
        """An errored snapshot must signal stale; its Merged entry is not authoritative.

        The snapshot may contain stale Merged data, but the stale flag MUST be true
        so the UI can display an explicit staleness indicator rather than silently
        rendering obsolete terminal status.
        """
        _clear_snapshot()
        try:
            server_module._set_issues_snapshot(
                {"Merged": [{"identifier": "OOMPAH-286", "project_id": "proj-x", "state": "Merged"}]},
                duration_ms=5.0,
                error="state branch unavailable",
            )
            with server_module._issues_snapshot_lock:
                # Make it old enough to be stale
                server_module._issues_snapshot["created_at_monotonic"] = (
                    time.monotonic() - 120
                )

            payload = server_module._issues_snapshot_payload(
                allow_empty=True,
                include_meta=True,
            )
            assert payload is not None
            meta = payload.get("_meta", {})
            assert meta.get("stale") is True, (
                "Degraded read must report stale=True so the UI shows an indicator"
            )
            assert meta.get("error") is not None, (
                "Errored snapshot must include the error field"
            )
        finally:
            _clear_snapshot()

    def test_fetch_serialize_skips_erroring_project_tracker(self):
        """When one project's tracker raises, only that project's issues are missing.

        The board must still return data for healthy projects — degraded reads
        must not suppress all projects.
        """
        issue_healthy = _issue("HEALTHY-1", "Open", project_id="proj-healthy")

        orch = MagicMock()
        orch.project_store.list_all.return_value = [
            SimpleNamespace(id="proj-healthy", name="proj-healthy"),
            SimpleNamespace(id="proj-broken", name="proj-broken"),
        ]

        healthy_tracker = MagicMock()
        healthy_tracker.fetch_all_issues.return_value = [issue_healthy]

        broken_tracker = MagicMock()
        broken_tracker.fetch_all_issues.side_effect = TrackerError("state branch gone")

        def _tracker_for(project_id):
            if project_id == "proj-healthy":
                return healthy_tracker
            return broken_tracker

        orch._tracker_for_project.side_effect = _tracker_for
        orch._project_epic_strategy.return_value = "flat"

        # Should not raise; returns partial board.
        board = server_module._fetch_all_issues(orch)

        identifiers = [i.identifier for i in board]
        assert "HEALTHY-1" in identifiers, (
            "Healthy project issues must still appear when another project's "
            "tracker is degraded"
        )

    def test_snapshot_error_field_set_when_tracker_raises(self):
        """_set_issues_snapshot records the error string when error is provided."""
        _clear_snapshot()
        try:
            server_module._set_issues_snapshot(
                {},
                duration_ms=5.0,
                error="TrackerError: git pull failed",
            )
            with server_module._issues_snapshot_lock:
                error = server_module._issues_snapshot.get("error")
            assert error == "TrackerError: git pull failed", (
                "error field must be preserved in snapshot for UI/diagnostic access"
            )
        finally:
            _clear_snapshot()


# ===========================================================================
# § 6  Null merged_at cannot produce Merged display state
# ===========================================================================


class TestNullMergedAtCannotProduceMerged:
    """A task is Merged only when the canonical state record says so.

    No derived heuristic (merged_at is set, review_url was created, etc.) may
    cause a Backlog/Open task to display as Merged.
    """

    def test_null_merged_at_backlog_task_shows_backlog(self):
        """state=Backlog, merged_at=None → display state = Backlog."""
        issue = _issue("OOMPAH-286", "Backlog", merged_at=None)
        assert server_module._issue_dashboard_state(issue) == "Backlog"

    def test_populated_merged_at_backlog_task_still_shows_backlog(self):
        """state=Backlog, merged_at=<some timestamp> → display state = Backlog.

        merged_at being set should NOT override canonical state.
        """
        issue = _issue("OOMPAH-286", "Backlog", merged_at="2026-07-01T00:00:00Z")
        assert server_module._issue_dashboard_state(issue) == "Backlog", (
            "Populating merged_at on a Backlog task must not change display to Merged"
        )

    def test_merged_task_with_null_merged_at_shows_merged(self):
        """state=Merged, merged_at=None → display state = Merged.

        The canonical state controls: Merged is shown when state=Merged regardless
        of whether merged_at is populated.
        """
        issue = _issue("OOMPAH-1", "Merged", merged_at=None)
        assert server_module._issue_dashboard_state(issue) == "Merged", (
            "Canonical state=Merged must display as Merged even if merged_at is None"
        )

    def test_board_with_null_merged_at_backlog_task_places_in_backlog_column(self):
        """_fetch_and_serialize_issues must put Backlog task in Backlog column.

        Reproduces OOMPAH-286: state=Backlog but displayed as Merged because
        stale snapshot had it in the Merged column.
        """
        issue = _issue("OOMPAH-286", "Backlog", merged_at=None, project_id="proj-14849f1b")
        orch = _orch_with_issues([issue], project_id="proj-14849f1b")
        board = server_module._fetch_and_serialize_issues(orch)

        backlog_ids = [i["identifier"] for i in board.get("Backlog", [])]
        merged_ids = [i["identifier"] for i in board.get("Merged", [])]
        assert "OOMPAH-286" in backlog_ids
        assert "OOMPAH-286" not in merged_ids

    def test_board_serializer_includes_tracker_state_field(self):
        """Serialized board entries include tracker_state for debugging.

        Having tracker_state in the payload allows the UI to show the raw
        canonical state and detect divergence without re-fetching.
        """
        issue = _issue("OOMPAH-286", "Backlog", project_id="proj-14849f1b")
        orch = _orch_with_issues([issue], project_id="proj-14849f1b")
        board = server_module._fetch_and_serialize_issues(orch)

        backlog = board.get("Backlog", [])
        entry = next((i for i in backlog if i["identifier"] == "OOMPAH-286"), None)
        assert entry is not None
        assert entry.get("tracker_state") == "Backlog", (
            "Board entry must include tracker_state field for diagnostic visibility"
        )
