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


def test_fetch_all_issues_github_dual_read_fetches_legacy_backlog_tracker():
    project = SimpleNamespace(
        id="proj-1",
        name="project-1",
        repo_path="/tmp/project-1",
        tracker_kind="github_issues",
        legacy_backlog_enabled=True,
    )
    gh_issue = _issue("owner/repo#1", "Open")
    gh_issue.tracker_kind = "github_issues"
    legacy_issue = _issue("TASK-1", "Backlog")
    github_tracker = MagicMock()
    github_tracker.fetch_all_issues.return_value = [gh_issue]
    legacy_tracker = MagicMock()
    legacy_tracker.fetch_all_issues.return_value = [legacy_issue]
    orch = MagicMock()
    orch.project_store.list_all.return_value = [project]
    orch._tracker_for_project.return_value = github_tracker
    orch._legacy_backlog_tracker_for_project.return_value = legacy_tracker
    orch._project_epic_strategy.return_value = "flat"

    issues = server_module._fetch_all_issues(orch)

    by_id = {issue.identifier: issue for issue in issues}
    assert by_id["owner/repo#1"].tracker_kind == "github_issues"
    assert by_id["TASK-1"].tracker_kind == "backlog_md"
    assert by_id["TASK-1"].is_legacy is True
    assert by_id["TASK-1"].project_id == "proj-1"
    orch._legacy_backlog_tracker_for_project.assert_called_once_with("proj-1")
    legacy_tracker.fetch_all_issues.assert_called_once_with()


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


def test_empty_issue_board_orders_proposed_before_backlog():
    board = server_module._empty_issue_board()

    assert list(board)[:2] == ["Proposed", "Backlog"]


def test_fetch_and_serialize_issues_includes_intake_summary():
    issue = _issue("lesserevil/oompah#10", "Proposed")
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
