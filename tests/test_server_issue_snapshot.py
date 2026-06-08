from __future__ import annotations

import contextlib
import json

import pytest

from oompah import server as server_module


class _Request:
    query_params: dict[str, str] = {}


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
