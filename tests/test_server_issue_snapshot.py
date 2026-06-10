from __future__ import annotations

import contextlib
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from oompah.models import Issue
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
            }
        )
    server_module._api_cache.clear()


def _issue(identifier: str, state: str, *, issue_type: str = "task", parent_id=None):
    return Issue(
        id=identifier,
        identifier=identifier,
        title=identifier,
        description="",
        state=state,
        issue_type=issue_type,
        parent_id=parent_id,
    )


def _orch_with_issues(issues):
    project = SimpleNamespace(id="proj-1", name="project-1")
    tracker = MagicMock()
    tracker.fetch_all_issues.return_value = list(issues)
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = tracker
    orch._project_epic_strategy.return_value = "flat"
    return orch


def test_fetch_all_issues_keeps_merged_epic_terminal_status():
    orch = _orch_with_issues(
        [
            _issue("TASK-1", "Merged", issue_type="epic"),
            _issue("TASK-1.1", "Done", parent_id="TASK-1"),
        ]
    )

    issues = server_module._fetch_all_issues(orch)

    by_id = {issue.identifier: issue for issue in issues}
    assert by_id["TASK-1"].state == "Merged"


def test_fetch_all_issues_rolls_up_non_terminal_epic_status():
    orch = _orch_with_issues(
        [
            _issue("TASK-1", "Backlog", issue_type="epic"),
            _issue("TASK-1.1", "Done", parent_id="TASK-1"),
        ]
    )

    issues = server_module._fetch_all_issues(orch)

    by_id = {issue.identifier: issue for issue in issues}
    assert by_id["TASK-1"].state == "Done"


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
