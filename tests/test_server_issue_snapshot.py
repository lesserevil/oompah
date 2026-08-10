from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from oompah.duplicate_screening import (
    ScreeningVerdict,
    complete_claim_record,
    new_claim_record,
)
from oompah.models import Issue
from oompah.integration import IntegrationRecord
from oompah.tracker import StateBranchMissingError, TrackerError
from oompah import server as server_module


class _Request:
    query_params: dict[str, str] = {}


def test_issues_snapshot_stale_threshold_defaults_to_sixty_seconds(monkeypatch):
    monkeypatch.delenv("OOMPAH_ISSUES_SNAPSHOT_STALE_MS", raising=False)

    assert server_module._env_positive_int_ms(
        "OOMPAH_ISSUES_SNAPSHOT_STALE_MS",
        60_000,
    ) == 60_000


def test_issues_snapshot_stale_threshold_reads_env(monkeypatch):
    monkeypatch.setenv("OOMPAH_ISSUES_SNAPSHOT_STALE_MS", "120000")

    assert server_module._env_positive_int_ms(
        "OOMPAH_ISSUES_SNAPSHOT_STALE_MS",
        60_000,
    ) == 120_000


def _clear_issue_snapshot_sync() -> None:
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
                "source_generations": {},
                "invalidated": False,
            }
        )
    server_module._api_cache.clear()
    with server_module._detail_cache_lock:
        server_module._detail_cache_generations.clear()


def _issue(
    identifier: str,
    state: str,
    *,
    issue_type: str = "task",
    parent_id=None,
    merged_at: str | None = None,
    work_branch: str | None = None,
    review_url: str | None = None,
):
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
        merged_at=merged_at,
        work_branch=work_branch,
        review_url=review_url,
    )


def _orch_with_issues(issues, *, state_branch_enabled: bool = False):
    project = SimpleNamespace(id="proj-1", name="project-1")
    tracker = MagicMock()
    tracker.state_branch_enabled = state_branch_enabled
    tracker.supports_generation_bound_reads = False
    tracker.fetch_all_issues.return_value = list(issues)
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    orch._project_epic_strategy.return_value = "flat"
    return orch


def test_fetch_and_serialize_issues_includes_proposed_snapshot_key():
    orch = _orch_with_issues([
        _issue("TASK-1", "Proposed"),
        _issue("TASK-2", "Open"),
    ])

    data = server_module._fetch_and_serialize_issues(orch)

    assert list(data.keys())[:4] == ["Proposed", "Backlog", "Open", "In Progress"]
    assert [entry["identifier"] for entry in data["Proposed"]] == ["TASK-1"]
    assert data["Proposed"][0]["state"] == "Proposed"


def test_fetch_all_issues_keeps_merged_epic_terminal_status():
    # A properly-merged epic must have merge evidence (merged_at) so the
    # null-evidence guard does not revert it to Backlog (OOMPAH-305).
    orch = _orch_with_issues(
        [
            _issue(
                "TASK-1",
                "Merged",
                issue_type="epic",
                merged_at="2026-07-01T00:00:00Z",
            ),
            _issue("TASK-1.1", "Done", parent_id="TASK-1"),
        ]
    )

    issues = server_module._fetch_all_issues(orch)

    by_id = {issue.identifier: issue for issue in issues}
    assert by_id["TASK-1"].state == "Merged"


def test_fetch_all_issues_keeps_authoritative_non_terminal_epic_status():
    orch = _orch_with_issues(
        [
            _issue("TASK-1", "In Progress", issue_type="epic"),
            _issue("TASK-1.1", "Done", parent_id="TASK-1"),
        ],
        state_branch_enabled=True,
    )

    issues = server_module._fetch_all_issues(orch)

    by_id = {issue.identifier: issue for issue in issues}
    assert by_id["TASK-1"].state == "In Progress"


def test_fetch_all_issues_does_not_downgrade_review_epic_to_done():
    orch = _orch_with_issues(
        [
            _issue("TASK-1", "In Review", issue_type="epic"),
            _issue("TASK-1.1", "Done", parent_id="TASK-1"),
            _issue("TASK-1.2", "Done", parent_id="TASK-1"),
        ]
    )

    issues = server_module._fetch_all_issues(orch)

    by_id = {issue.identifier: issue for issue in issues}
    assert by_id["TASK-1"].state == "In Review"


def test_fetch_all_issues_does_not_downgrade_review_epic_to_in_progress():
    orch = _orch_with_issues(
        [
            _issue("TASK-1", "In Review", issue_type="epic"),
            _issue("TASK-1.1", "In Review", parent_id="TASK-1"),
            _issue("TASK-1.2", "Done", parent_id="TASK-1"),
        ]
    )

    issues = server_module._fetch_all_issues(orch)

    by_id = {issue.identifier: issue for issue in issues}
    assert by_id["TASK-1"].state == "In Review"


def test_fetch_all_issues_keeps_epic_state_when_children_only_proposed():
    orch = _orch_with_issues(
        [
            _issue("TASK-1", "Backlog", issue_type="epic"),
            _issue("TASK-1.1", "Proposed", parent_id="TASK-1"),
        ]
    )

    issues = server_module._fetch_all_issues(orch)

    by_id = {issue.identifier: issue for issue in issues}
    assert by_id["TASK-1"].state == "Backlog"
    assert by_id["TASK-1.1"].state == "Proposed"


def test_fetch_all_issues_keeps_child_proposed_when_parent_is_proposed():
    orch = _orch_with_issues(
        [
            _issue("TASK-1", "Proposed", issue_type="epic"),
            _issue("TASK-1.1", "Backlog", parent_id="TASK-1"),
        ]
    )

    issues = server_module._fetch_all_issues(orch)

    by_id = {issue.identifier: issue for issue in issues}
    assert by_id["TASK-1"].state == "Proposed"
    assert by_id["TASK-1.1"].state == "Proposed"


def test_fetch_and_serialize_issues_keeps_proposed_visible_and_counted():
    orch = _orch_with_issues(
        [
            _issue("TASK-1", "Backlog", issue_type="epic"),
            _issue("TASK-1.1", "Proposed", parent_id="TASK-1"),
        ]
    )

    board = server_module._fetch_and_serialize_issues(orch)

    assert [issue["identifier"] for issue in board["Proposed"]] == ["TASK-1.1"]
    assert board["Backlog"][0]["children_counts"]["Proposed"] == 1
    assert board["Backlog"][0]["children_counts"]["Open"] == 0


def test_fetch_and_serialize_issues_counts_child_under_proposed_parent_as_proposed():
    orch = _orch_with_issues(
        [
            _issue("TASK-1", "Proposed", issue_type="epic"),
            _issue("TASK-1.1", "Backlog", parent_id="TASK-1"),
        ]
    )

    board = server_module._fetch_and_serialize_issues(orch)

    assert [issue["identifier"] for issue in board["Proposed"]] == [
        "TASK-1",
        "TASK-1.1",
    ]
    assert board["Proposed"][0]["children_counts"]["Proposed"] == 1
    assert board["Proposed"][0]["children_counts"]["Backlog"] == 0


async def _reset_issue_snapshot() -> None:
    with server_module._issues_snapshot_lock:
        task = server_module._issues_refresh_task
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
                "source_generations": {},
                "invalidated": False,
            }
        )
    if task is not None and not task.done():
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
    server_module._api_cache.clear()


@pytest.mark.asyncio
async def test_api_issues_waits_briefly_for_fast_first_snapshot(monkeypatch):
    await _reset_issue_snapshot()

    def _fetch(_orch):
        return {
            "Open": [
                {
                    "id": "TASK-1",
                    "identifier": "TASK-1",
                    "project_id": "p1",
                    "priority": 1,
                }
            ]
        }

    monkeypatch.setattr(server_module, "_get_orchestrator", lambda: object())
    monkeypatch.setattr(server_module, "_fetch_and_serialize_issues", _fetch)

    try:
        response = await server_module.api_issues(_Request())
        data = json.loads(response.body)

        assert data["Open"][0]["identifier"] == "TASK-1"
        assert "_meta" not in data
        assert response.headers["x-oompah-issues-count"] == "1"
        assert response.headers["x-oompah-issues-snapshot-age-ms"] is not None
    finally:
        await _reset_issue_snapshot()


@pytest.mark.asyncio
async def test_api_issues_returns_503_instead_of_invalidated_board(monkeypatch):
    """A full REST snapshot must never fall back to known-stale task lanes."""
    await _reset_issue_snapshot()
    orch = MagicMock()
    orch.project_store.list_all.return_value = []
    try:
        server_module._set_issues_snapshot(
            {"Done": [{"identifier": "OOMPAH-768", "state": "Done"}]},
            duration_ms=1.0,
            orch_id=id(orch),
        )
        server_module._invalidate_issue_caches(schedule_broadcast=False)

        async def _no_refresh(*_args, **_kwargs):
            return None

        async def _timeout(*_args, **_kwargs):
            return False

        monkeypatch.setattr(server_module, "_get_orchestrator", lambda: orch)
        monkeypatch.setattr(server_module, "_ensure_issues_snapshot_refresh", _no_refresh)
        monkeypatch.setattr(server_module, "_wait_for_issues_snapshot_refresh", _timeout)

        response = await server_module.api_issues(_Request())
        body = json.loads(response.body)

        assert response.status_code == 503
        assert body["error"]["code"] == "snapshot_unavailable"
        assert response.headers["x-oompah-issues-stale"] == "true"
    finally:
        await _reset_issue_snapshot()


@pytest.mark.asyncio
async def test_refresh_retries_immediately_after_snapshot_error(monkeypatch):
    """A failed refresh does not suppress recovery until the normal TTL."""
    await _reset_issue_snapshot()
    orch = MagicMock()
    orch.project_store.list_all.return_value = []

    def _fetch(_orch, *, include_source_generations=False):
        board = {"In Progress": [{"identifier": "TASK-1", "state": "In Progress"}]}
        return (board, {}) if include_source_generations else board

    monkeypatch.setattr(server_module, "_fetch_and_serialize_issues", _fetch)
    try:
        assert server_module._set_issues_snapshot(
            {"Open": [{"identifier": "TASK-1", "state": "Open"}]},
            duration_ms=1.0,
            orch_id=id(orch),
        )
        with server_module._issues_snapshot_lock:
            server_module._issues_snapshot["error"] = "transient read failure"

        await server_module._ensure_issues_snapshot_refresh(orch)
        assert await server_module._wait_for_issues_snapshot_refresh(timeout_ms=2000)

        payload = server_module._issues_snapshot_payload(orch=orch, allow_empty=False)
        assert payload is not None
        assert payload["In Progress"][0]["identifier"] == "TASK-1"
        with server_module._issues_snapshot_lock:
            assert server_module._issues_snapshot["error"] is None
    finally:
        await _reset_issue_snapshot()


@pytest.mark.asyncio
async def test_refresh_validates_tracker_sources_outside_snapshot_lock(monkeypatch):
    """Refresh checks preserve the tracker-to-snapshot mutation lock order."""
    await _reset_issue_snapshot()
    tracker = MagicMock()
    tracker.state_branch_enabled = True
    tracker.get_state_branch_generation.return_value = "commit-a:1"
    project = SimpleNamespace(id="proj-1", name="project-1")
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    try:
        assert server_module._set_issues_snapshot(
            {"Open": [{"identifier": "TASK-1", "state": "Open"}]},
            duration_ms=1.0,
            orch_id=id(orch),
            source_generations={"proj-1": "commit-a:1"},
            source_authority=orch,
        )

        checked = []

        def _sources_match(_orch, _generations):
            is_owned = getattr(server_module._issues_snapshot_lock, "_is_owned")
            assert not is_owned()
            checked.append(True)
            return True

        monkeypatch.setattr(
            server_module, "_issues_snapshot_sources_match", _sources_match
        )

        await server_module._ensure_issues_snapshot_refresh(orch)

        assert checked == [True]
        with server_module._issues_snapshot_lock:
            assert server_module._issues_refresh_task is None
    finally:
        await _reset_issue_snapshot()


@pytest.mark.asyncio
async def test_slow_snapshot_authority_probe_never_blocks_event_loop(monkeypatch):
    """Workflow publication may hold tracker authority while HTTP stays live."""

    await _reset_issue_snapshot()
    orch = MagicMock()
    orch.project_store.list_all.return_value = []
    entered = threading.Event()
    release = threading.Event()

    def _slow_sources_match(_orch, _generations):
        entered.set()
        assert release.wait(timeout=2)
        return True

    monkeypatch.setattr(
        server_module,
        "_issues_snapshot_sources_match",
        _slow_sources_match,
    )
    try:
        with server_module._issues_snapshot_lock:
            server_module._issues_snapshot.update(
                {
                    "data": {"Open": []},
                    "orch_id": id(orch),
                    "created_at_monotonic": time.monotonic(),
                    "source_generations": {"proj-1": "commit-a:1"},
                    "invalidated": False,
                    "error": None,
                }
            )

        refresh = asyncio.create_task(
            server_module._ensure_issues_snapshot_refresh(orch)
        )
        assert await asyncio.to_thread(entered.wait, 1)
        started = time.monotonic()
        health = await asyncio.wait_for(server_module.healthz(), timeout=0.1)
        elapsed = time.monotonic() - started
        assert json.loads(health.body)["status"] == "ok"
        assert elapsed < 0.1
    finally:
        release.set()
        if "refresh" in locals():
            await asyncio.wait_for(refresh, timeout=1)
        await _reset_issue_snapshot()


def test_issue_snapshot_payload_filters_project_without_refetch():
    _clear_issue_snapshot_sync()
    try:
        server_module._set_issues_snapshot(
            {
                "Open": [
                    {"identifier": "TASK-1", "project_id": "p1"},
                    {"identifier": "TASK-2", "project_id": "p2"},
                ]
            },
            duration_ms=12.5,
        )

        payload = server_module._issues_snapshot_payload(
            filter_project="p1", allow_empty=False, include_meta=True
        )

        assert [i["identifier"] for i in payload["Open"]] == ["TASK-1"]
        assert payload["_meta"]["issue_count"] == 2
    finally:
        _clear_issue_snapshot_sync()


def test_issue_snapshot_payload_uses_stale_threshold(monkeypatch):
    _clear_issue_snapshot_sync()
    monkeypatch.setattr(server_module, "_ISSUES_SNAPSHOT_STALE_MS", 60_000)
    try:
        server_module._set_issues_snapshot(
            {"Open": [{"identifier": "TASK-1", "project_id": "p1"}]},
            duration_ms=12.5,
        )
        with server_module._issues_snapshot_lock:
            server_module._issues_snapshot["created_at_monotonic"] = (
                time.monotonic() - 30
            )

        payload = server_module._issues_snapshot_payload(
            allow_empty=False,
            include_meta=True,
        )

        assert payload is not None
        assert payload["_meta"]["stale"] is False
    finally:
        _clear_issue_snapshot_sync()


def test_generation_bound_snapshot_rejects_newer_project_state():
    """A status move in a separate tracker generation cannot serve old lanes."""
    _clear_issue_snapshot_sync()
    tracker = MagicMock()
    tracker.state_branch_enabled = True
    tracker.get_state_branch_generation.return_value = "commit-a:1"
    project = SimpleNamespace(id="proj-1", name="project-1")
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    try:
        server_module._set_issues_snapshot(
            {"Needs Human": [{"identifier": "OOMPAH-651", "project_id": "proj-1"}]},
            duration_ms=1.0,
            orch_id=id(orch),
            source_generations={"proj-1": "commit-a:1"},
            source_authority=orch,
        )
        tracker.get_state_branch_generation.return_value = "commit-b:2"

        assert server_module._issues_snapshot_payload(
            orch=orch, allow_empty=False
        ) is None
        stale = server_module._issues_snapshot_payload(
            orch=orch, allow_empty=True, include_meta=True
        )
        assert stale["Needs Human"][0]["identifier"] == "OOMPAH-651"
        assert stale["_meta"]["stale"] is True
    finally:
        _clear_issue_snapshot_sync()


def test_fetch_all_issues_uses_native_generation_bound_read():
    """The list object and reported source generation come from one tracker read."""
    issue = _issue("OOMPAH-768", "In Progress", issue_type="epic")
    tracker = MagicMock()
    tracker.state_branch_enabled = True
    tracker.supports_generation_bound_reads = True
    tracker.fetch_all_issues_with_generation.return_value = (
        [issue],
        "commit-current:7",
    )
    tracker.get_state_branch_generation.return_value = "commit-current:7"
    project = SimpleNamespace(id="proj-1", name="project-1")
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker

    issues, generations = server_module._fetch_all_issues(
        orch, include_source_generations=True
    )

    assert [(item.identifier, item.state) for item in issues] == [
        ("OOMPAH-768", "In Progress")
    ]
    assert generations == {"proj-1": "commit-current:7"}
    tracker.fetch_all_issues.assert_not_called()


def test_unstable_fallback_read_is_never_stamped_with_newer_generation():
    """Adapters without an atomic extension fail closed after bounded retries."""
    tracker = MagicMock()
    tracker.state_branch_enabled = True
    tracker.supports_generation_bound_reads = False
    tracker.fetch_all_issues.side_effect = [
        [_issue("TASK-1", "Open")],
        [_issue("TASK-1", "In Progress")],
        [_issue("TASK-1", "Done")],
    ]
    tracker.get_state_branch_generation.side_effect = [
        "commit-a:1",
        "commit-b:2",
        "commit-c:3",
        "commit-d:4",
    ]

    issues, generation = server_module._fetch_tracker_issues_with_generation(tracker)

    assert issues[0].state == "Done"
    assert generation == "unavailable"
    assert tracker.fetch_all_issues.call_count == 3


def test_generation_bound_state_branch_with_missing_generation_fails_closed():
    """An atomic extension cannot mark state-branch data fresh without a revision."""
    issue = _issue("TASK-1", "In Progress")
    tracker = MagicMock()
    tracker.state_branch_enabled = True
    tracker.supports_generation_bound_reads = True
    tracker.fetch_all_issues_with_generation.return_value = ([issue], None)
    tracker.fetch_issue_detail_with_generation.return_value = (issue, None)

    issues, list_generation = server_module._fetch_tracker_issues_with_generation(
        tracker
    )
    detail, detail_generation = (
        server_module._fetch_tracker_issue_detail_with_generation(tracker, "TASK-1")
    )

    assert issues == [issue]
    assert detail is issue
    assert list_generation == detail_generation == "unavailable"


def test_raced_snapshot_candidate_does_not_advance_data_revision():
    """A mutation during serialization cannot attach its revision to old data."""
    _clear_issue_snapshot_sync()
    try:
        assert server_module._set_issues_snapshot(
            {"Open": [{"identifier": "TASK-1", "state": "Open"}]},
            duration_ms=1.0,
        )
        with server_module._issues_snapshot_lock:
            old_data = server_module._issues_snapshot["data"]
            old_data_revision = server_module._issues_snapshot["data_revision"]
        _, _, expected_revision = server_module._protocol_values()

        server_module._invalidate_issue_caches(schedule_broadcast=False)
        accepted = server_module._set_issues_snapshot(
            {"Done": [{"identifier": "TASK-1", "state": "Done"}]},
            duration_ms=2.0,
            expected_issue_revision=expected_revision,
        )

        assert accepted is False
        with server_module._issues_snapshot_lock:
            assert server_module._issues_snapshot["data"] is old_data
            assert server_module._issues_snapshot["data_revision"] == old_data_revision
            assert server_module._issues_snapshot["invalidated"] is True
        assert server_module._issues_snapshot_payload(allow_empty=False) is None
    finally:
        _clear_issue_snapshot_sync()


def test_external_source_race_reserves_revision_for_eventual_board():
    """A generation change without a callback cannot reuse the old watermark."""
    _clear_issue_snapshot_sync()
    tracker = MagicMock()
    tracker.state_branch_enabled = True
    tracker.get_state_branch_generation.return_value = "commit-a:1"
    project = SimpleNamespace(id="proj-1", name="project-1")
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    try:
        assert server_module._set_issues_snapshot(
            {"Open": [{"identifier": "TASK-1", "state": "Open"}]},
            duration_ms=1.0,
            orch_id=id(orch),
            source_generations={"proj-1": "commit-a:1"},
            source_authority=orch,
        )
        with server_module._issues_snapshot_lock:
            old_data_revision = server_module._issues_snapshot["data_revision"]

        tracker.get_state_branch_generation.return_value = "commit-b:2"
        assert not server_module._set_issues_snapshot(
            {"Open": [{"identifier": "TASK-1", "state": "Open"}]},
            duration_ms=2.0,
            orch_id=id(orch),
            source_generations={"proj-1": "commit-a:1"},
            source_authority=orch,
        )
        assert server_module._set_issues_snapshot(
            {"In Progress": [{"identifier": "TASK-1", "state": "In Progress"}]},
            duration_ms=3.0,
            orch_id=id(orch),
            source_generations={"proj-1": "commit-b:2"},
            source_authority=orch,
        )

        with server_module._issues_snapshot_lock:
            assert server_module._issues_snapshot["data_revision"] > old_data_revision
    finally:
        _clear_issue_snapshot_sync()


@pytest.mark.asyncio
async def test_paused_project_refreshes_after_api_tracker_mutation(monkeypatch):
    """Project pause gates dispatch, not authoritative API snapshot refreshes."""
    await _reset_issue_snapshot()
    monkeypatch.setattr(server_module, "_ws_clients", set())
    project = SimpleNamespace(id="proj-paused", name="paused", paused=True)
    current_issue = [_issue("TASK-1", "Open")]
    current_generation = ["commit-a:1"]
    callbacks = []
    tracker = MagicMock()
    tracker.state_branch_enabled = True
    tracker.supports_generation_bound_reads = True
    tracker.fetch_all_issues_with_generation.side_effect = lambda: (
        list(current_issue),
        current_generation[0],
    )
    tracker.get_state_branch_generation.side_effect = lambda: current_generation[0]
    tracker.add_read_change_callback.side_effect = callbacks.append
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker

    try:
        await server_module._ensure_issues_snapshot_refresh(orch, force=True)
        assert await server_module._wait_for_issues_snapshot_refresh(timeout_ms=2000)
        first = server_module._issues_snapshot_payload(orch=orch, allow_empty=False)
        assert first is not None
        assert first["Open"][0]["state"] == "Open"

        current_issue[:] = [_issue("TASK-1", "In Progress")]
        current_generation[0] = "commit-b:2"
        assert callbacks
        callbacks[0]()  # same synchronous invalidation used by PATCH mutations

        await server_module._ensure_issues_snapshot_refresh(orch)
        assert await server_module._wait_for_issues_snapshot_refresh(timeout_ms=2000)
        refreshed = server_module._issues_snapshot_payload(
            orch=orch, allow_empty=False
        )
        assert refreshed is not None
        assert refreshed["In Progress"][0]["state"] == "In Progress"
        assert refreshed["Open"] == []
    finally:
        await _reset_issue_snapshot()


def test_unavailable_generation_preserves_stale_snapshot_instead_of_empty_fresh_lane():
    """An unavailable state-branch read is explicitly stale, never fresh empty."""
    _clear_issue_snapshot_sync()
    tracker = MagicMock()
    tracker.state_branch_enabled = True
    tracker.get_state_branch_generation.return_value = "commit-a:1"
    project = SimpleNamespace(id="proj-1", name="project-1")
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    try:
        assert server_module._set_issues_snapshot(
            {"Needs Human": [{"identifier": "OOMPAH-655", "project_id": "proj-1"}]},
            duration_ms=1.0,
            orch_id=id(orch),
            source_generations={"proj-1": "commit-a:1"},
            source_authority=orch,
        )
        tracker.get_state_branch_generation.return_value = "unavailable"
        assert not server_module._set_issues_snapshot(
            {"Done": [{"identifier": "OOMPAH-655", "project_id": "proj-1"}]},
            duration_ms=2.0,
            orch_id=id(orch),
            source_generations={"proj-1": "unavailable"},
            source_authority=orch,
        )
        stale = server_module._issues_snapshot_payload(
            orch=orch, allow_empty=True, include_meta=True
        )
        assert stale["Needs Human"][0]["identifier"] == "OOMPAH-655"
        assert stale["_meta"]["stale"] is True
        assert server_module._issues_snapshot_headers(orch)[
            "X-Oompah-Issues-Stale"
        ] == "true"
    finally:
        _clear_issue_snapshot_sync()


def test_detail_cache_is_rejected_when_project_generation_advances():
    """Detail parity follows the same generation fence as the board cache."""
    _clear_issue_snapshot_sync()
    tracker = MagicMock()
    tracker.state_branch_enabled = True
    tracker.get_state_branch_generation.return_value = "commit-a:1"
    orch = MagicMock()
    orch._tracker_for_project.return_value = tracker
    key = "detail:proj-1:OOMPAH-651:actor:"
    try:
        server_module._detail_cache_set(
            key,
            {"identifier": "OOMPAH-651", "state": "Needs Human"},
            project_id="proj-1",
            generation="commit-a:1",
        )
        tracker.get_state_branch_generation.return_value = "commit-b:2"
        assert server_module._detail_cache_get(key, orch, "proj-1") is None
    finally:
        _clear_issue_snapshot_sync()


def test_tracker_callback_invalidates_only_matching_detail_project():
    """Direct native mutations synchronously invalidate list and project A details."""
    _clear_issue_snapshot_sync()
    tracker = MagicMock()
    callbacks = []
    tracker.add_read_change_callback.side_effect = callbacks.append
    server_module._wire_tracker_issue_cache_invalidation(tracker, "proj-a")
    server_module._api_cache.set(
        "detail:proj-a:TASK-1:actor:", {"state": "Open"}, ttl_ms=60_000
    )
    server_module._api_cache.set(
        "detail:proj-b:TASK-1:actor:", {"state": "Open"}, ttl_ms=60_000
    )
    try:
        assert callbacks
        callbacks[0]()
        assert server_module._api_cache.get("detail:proj-a:TASK-1:actor:") is None
        assert server_module._api_cache.get("detail:proj-b:TASK-1:actor:") == {
            "state": "Open"
        }
        with server_module._issues_snapshot_lock:
            assert server_module._issues_snapshot["invalidated"] is True
    finally:
        _clear_issue_snapshot_sync()


def test_empty_issue_board_orders_proposed_before_backlog():
    board = server_module._empty_issue_board()

    assert list(board)[:2] == ["Proposed", "Backlog"]


def test_ready_to_integrate_board_entry_includes_integration_evidence():
    issue = _issue("TASK-READY", "Ready to Integrate")
    issue.integration = IntegrationRecord(
        state="ready",
        task_branch="oompah/task/TASK-READY",
        base_branch="epic-TASK-1",
        head_sha="a" * 40,
    )

    payload = server_module._fetch_and_serialize_issues(_orch_with_issues([issue]))

    entry = payload["Ready to Integrate"][0]
    assert entry["integration"] == {
        "version": 2,
        "state": "ready",
        "attempts": 0,
        "task_branch": "oompah/task/TASK-READY",
        "base_branch": "epic-TASK-1",
        "head_sha": "a" * 40,
    }


def test_fetch_and_serialize_issues_includes_intake_summary():
    issue = _issue("example-org/oompah#10", "Proposed")
    issue.intake = {
        "missing_fields": ["acceptance_criteria"],
        "scope": "small",
        "requestor_approved": False,
        "owner_override": False,
        "decomposition_status": "not_needed",
        "last_validator_result": "fail",
    }
    orch = _orch_with_issues([issue])

    payload = server_module._fetch_and_serialize_issues(orch)

    summary = payload["Proposed"][0]["intake_summary"]
    assert summary["state"] == "missing-info"
    assert summary["missing_fields"] == ["acceptance_criteria"]
    assert summary["requestor_approval_state"] == "awaiting"
    assert summary["owner_override_state"] == "none"
    assert summary["decomposition_state"] == "not_needed"


def test_fetch_and_serialize_issues_omits_stale_intake_summary_after_intake():
    issue = _issue("example-org/oompah#309", "In Review")
    issue.intake = {
        "missing_fields": [],
        "scope": "small",
        "requestor_approved": False,
        "owner_override": False,
        "decomposition_status": "not_needed",
        "last_validator_result": "pass",
    }
    orch = _orch_with_issues([issue])

    payload = server_module._fetch_and_serialize_issues(orch)

    assert payload["In Review"][0]["identifier"] == "example-org/oompah#309"
    assert "intake_summary" not in payload["In Review"][0]


def test_duplicate_screening_summary_serializes_safe_operator_states():
    unchecked = _issue("TASK-10", "Open")
    unchecked.description = "Unchecked task"
    unchecked.project_id = "proj-1"
    running = _issue("TASK-11", "Open")
    running.description = "Running task"
    running.project_id = "proj-1"
    running.duplicate_screening = new_claim_record(
        running,
        owner="secret-scheduler-identity",
    ).to_dict()
    checked = _issue("TASK-12", "Open")
    checked.description = "Checked task"
    checked.project_id = "proj-1"
    checked.duplicate_screening = complete_claim_record(
        new_claim_record(checked, owner="scheduler"),
        verdict=ScreeningVerdict.NO_DUPLICATE,
        evidence="private full model output",
    ).to_dict()
    stale = _issue("TASK-13", "Open")
    stale.description = "Original description"
    stale.project_id = "proj-1"
    stale.duplicate_screening = complete_claim_record(
        new_claim_record(stale, owner="scheduler"),
        verdict=ScreeningVerdict.NO_DUPLICATE,
    ).to_dict()
    stale.description = "Changed description"
    orch = _orch_with_issues([unchecked, running, checked, stale])
    orch.config = SimpleNamespace(duplicate_preflight_max_agents=1)

    payload = server_module._fetch_and_serialize_issues(orch)
    rows = {row["identifier"]: row for row in payload["Open"]}

    assert rows["TASK-10"]["duplicate_screening"]["state"] == "unchecked"
    assert rows["TASK-11"]["duplicate_screening"]["state"] == "running"
    assert rows["TASK-12"]["duplicate_screening"]["state"] == "checked"
    assert rows["TASK-13"]["duplicate_screening"]["state"] == "stale"
    assert rows["TASK-10"]["duplicate_screening"]["required"] is True
    serialized = json.dumps(rows)
    assert "secret-scheduler-identity" not in serialized
    assert "private full model output" not in serialized
    assert "claim_id" not in serialized


# ---------------------------------------------------------------------------
# Regression tests for OOMPAH-316: StateBranchMissingError graceful degradation
# ---------------------------------------------------------------------------


def _orch_with_tracker_error(error: Exception):
    """Build a minimal orchestrator whose tracker raises *error* on fetch."""
    project = SimpleNamespace(id="proj-missing", name="exocomp")
    tracker = MagicMock()
    tracker.fetch_all_issues.side_effect = error
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    orch._project_epic_strategy.return_value = "flat"
    return orch


def test_fetch_all_issues_state_branch_missing_logs_warning_not_error(caplog):
    """StateBranchMissingError must log at WARNING so error_watcher is not triggered.

    Regression for OOMPAH-316: previously all TrackerErrors were logged at
    ERROR level, causing error_watcher to auto-file a task on every issue
    fetch for a project whose state branch had never been bootstrapped.
    """
    exc = StateBranchMissingError(
        "State branch 'oompah/state/proj-c260b117' does not exist locally or at "
        "origin/'oompah/state/proj-c260b117'. Run the bootstrap or migration flow."
    )
    orch = _orch_with_tracker_error(exc)

    with caplog.at_level(logging.DEBUG, logger="oompah.server"):
        issues = server_module._fetch_all_issues(orch)

    assert issues == [], "Must return empty list on missing state branch"

    warning_records = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "exocomp" in r.getMessage()
    ]
    error_records = [
        r for r in caplog.records
        if r.levelno == logging.ERROR and "exocomp" in r.getMessage()
    ]
    assert warning_records, "Expected a WARNING log mentioning the project name"
    assert not error_records, (
        "StateBranchMissingError must NOT be logged at ERROR level "
        "(that would trigger error_watcher)"
    )


def test_fetch_all_issues_generic_tracker_error_still_logs_error(caplog):
    """Other TrackerError subtypes must still be logged at ERROR level.

    Regression guard: the StateBranchMissingError special-case must not
    silence unrelated tracker failures.
    """
    exc = TrackerError("some unexpected tracker failure")
    orch = _orch_with_tracker_error(exc)

    with caplog.at_level(logging.DEBUG, logger="oompah.server"):
        issues = server_module._fetch_all_issues(orch)

    assert issues == [], "Must return empty list on tracker error"

    error_records = [
        r for r in caplog.records
        if r.levelno == logging.ERROR and "exocomp" in r.getMessage()
    ]
    assert error_records, "Generic TrackerError must still be logged at ERROR level"
