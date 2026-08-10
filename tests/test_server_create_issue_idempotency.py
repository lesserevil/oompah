"""Durable and bounded task-creation API coverage for OOMPAH-994."""

from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import oompah.server as server_module
from oompah.oompah_md_tracker import OompahMarkdownTracker
from oompah.projects import ProjectStore
from oompah.server import app


def _native_tracker(root) -> OompahMarkdownTracker:
    return OompahMarkdownTracker(
        active_states=["Open"],
        terminal_states=["Done"],
        cwd=str(root),
        default_branch="main",
        git_sync=False,
    )


def _orchestrator(tmp_path, tracker) -> SimpleNamespace:
    project_store = ProjectStore(path=str(tmp_path / "projects.json"))
    return SimpleNamespace(
        project_store=project_store,
        event_bus=MagicMock(),
        _tracker_for_project=MagicMock(return_value=tracker),
    )


def _payload(*, title: str = "Durable task") -> dict[str, object]:
    return {
        "title": title,
        "description": "Create exactly one durable task.",
        "project_id": "proj-1",
        "type": "task",
    }


def _create_once_kwargs() -> dict[str, object]:
    return {
        "title": "Cancelled response task",
        "description": "Recover the accepted task by its exact key.",
        "project_id": "proj-1",
        "operation_kind": "api_task_create",
        "creation_marker": "cancel-replay-key",
    }


def test_same_key_replays_same_native_task_after_tracker_restart(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    first_tracker = _native_tracker(root)
    orch = _orchestrator(tmp_path, first_tracker)
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Idempotency-Key": "restart-replay-key"}

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        first = client.post("/api/v1/issues", json=_payload(), headers=headers)
        restarted_tracker = _native_tracker(root)
        orch._tracker_for_project.return_value = restarted_tracker
        replay = client.post("/api/v1/issues", json=_payload(), headers=headers)

    assert first.status_code == replay.status_code == 201
    assert first.json()["issue"]["identifier"] == replay.json()["issue"]["identifier"]
    assert replay.json()["operation"] == {
        "idempotency_key": "restart-replay-key",
        "durable": True,
    }
    assert len(list(restarted_tracker.tasks_root.glob("*/*.md"))) == 1


def test_same_key_with_different_payload_returns_conflict(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tracker = _native_tracker(root)
    orch = _orchestrator(tmp_path, tracker)
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Idempotency-Key": "payload-conflict-key"}

    with (
        patch.object(server_module, "_get_orchestrator", return_value=orch),
        patch.object(server_module, "broadcast_issues", new_callable=AsyncMock),
    ):
        first = client.post("/api/v1/issues", json=_payload(), headers=headers)
        conflict = client.post(
            "/api/v1/issues",
            json=_payload(title="Different task"),
            headers=headers,
        )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert len(list(tracker.tasks_root.glob("*/*.md"))) == 1


def test_keyed_create_fails_closed_for_non_atomic_tracker(tmp_path):
    tracker = MagicMock()
    tracker.supports_atomic_create_once = False
    orch = _orchestrator(tmp_path, tracker)
    client = TestClient(app, raise_server_exceptions=False)

    with patch.object(server_module, "_get_orchestrator", return_value=orch):
        response = client.post(
            "/api/v1/issues",
            json=_payload(),
            headers={"Idempotency-Key": "unsupported-key"},
        )

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "idempotency_unsupported"
    tracker.create_issue.assert_not_called()
    tracker.create_issue_once.assert_not_called()


@pytest.mark.parametrize(
    ("headers", "expected_message"),
    [
        (None, "Project task mutation is busy; retry the request."),
        (
            {"Idempotency-Key": "busy-key"},
            (
                "Project task mutation is busy; retry the request. "
                "Retry with the same Idempotency-Key."
            ),
        ),
    ],
)
def test_project_lock_admission_returns_bounded_retryable_503(
    tmp_path,
    monkeypatch,
    headers,
    expected_message,
):
    root = tmp_path / "repo"
    root.mkdir()
    tracker = _native_tracker(root)
    orch = _orchestrator(tmp_path, tracker)
    lock = orch.project_store.project_write_lock("proj-1")
    lock.acquire()
    monkeypatch.setattr(
        server_module,
        "_TASK_CREATE_ADMISSION_TIMEOUT_SECONDS",
        0.05,
    )
    client = TestClient(app, raise_server_exceptions=False)
    started = time.monotonic()
    try:
        with patch.object(server_module, "_get_orchestrator", return_value=orch):
            response = client.post(
                "/api/v1/issues",
                json=_payload(),
                headers=headers,
            )
    finally:
        lock.release()

    assert time.monotonic() - started < 1.0
    assert response.status_code == 503
    assert response.json()["error"] == {
        "code": "task_create_busy",
        "message": expected_message,
        "retryable": True,
    }
    assert list(tracker.tasks_root.glob("*/*.md")) == []


@pytest.mark.asyncio
async def test_cancel_before_project_admission_cannot_create_later(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tracker = _native_tracker(root)
    lock = threading.RLock()
    lock.acquire()
    create = MagicMock(
        side_effect=lambda: tracker.create_issue_once(**_create_once_kwargs())
    )
    request_task = asyncio.create_task(
        server_module._run_task_create_io(
            lambda cancelled: server_module._run_admitted_task_create(
                lock,
                cancelled,
                create,
            )
        )
    )
    await asyncio.sleep(0.05)
    request_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request_task
    lock.release()
    await asyncio.sleep(0.05)

    assert create.call_count == 0
    replayed = await server_module._run_task_create_io(
        lambda cancelled: server_module._run_admitted_task_create(
            lock,
            cancelled,
            lambda: tracker.create_issue_once(**_create_once_kwargs()),
        )
    )
    assert replayed.identifier == "REPO-1"
    assert len(list(tracker.tasks_root.glob("*/*.md"))) == 1


@pytest.mark.asyncio
async def test_cancel_after_durable_acceptance_replays_same_task(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    tracker = _native_tracker(root)
    lock = threading.RLock()
    persisted = threading.Event()
    release_response = threading.Event()

    def _accepted_operation():
        issue = tracker.create_issue_once(**_create_once_kwargs())
        persisted.set()
        assert release_response.wait(timeout=2)
        return issue

    request_task = asyncio.create_task(
        server_module._run_task_create_io(
            lambda cancelled: server_module._run_admitted_task_create(
                lock,
                cancelled,
                _accepted_operation,
            )
        )
    )
    assert await asyncio.to_thread(persisted.wait, 1)
    request_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request_task
    release_response.set()

    replayed = await server_module._run_task_create_io(
        lambda cancelled: server_module._run_admitted_task_create(
            lock,
            cancelled,
            lambda: tracker.create_issue_once(**_create_once_kwargs()),
        )
    )
    assert replayed.identifier == "REPO-1"
    assert len(list(tracker.tasks_root.glob("*/*.md"))) == 1


@pytest.mark.asyncio
async def test_blocked_create_lane_does_not_starve_general_api_pool():
    release = threading.Event()
    entered = [threading.Event(), threading.Event()]

    def _blocked(index: int):
        def _operation(_cancelled: threading.Event):
            entered[index].set()
            assert release.wait(timeout=2)
            return index

        return _operation

    creates = [
        asyncio.create_task(server_module._run_task_create_io(_blocked(index)))
        for index in range(2)
    ]
    assert await asyncio.to_thread(entered[0].wait, 1)
    assert await asyncio.to_thread(entered[1].wait, 1)
    try:
        with pytest.raises(server_module.TaskCreateAdmissionUnavailable):
            await server_module._run_task_create_io(lambda _cancelled: "queued")
        responsive = await asyncio.wait_for(
            server_module._run_api_io(lambda: "responsive"),
            timeout=0.5,
        )
        assert responsive == "responsive"
    finally:
        release.set()
    assert await asyncio.gather(*creates) == [0, 1]
