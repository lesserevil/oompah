"""API contracts for coalesced, configurable graceful restarts (OOMPAH-507)."""

import asyncio
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from oompah import server
from oompah.config import ServiceConfig
from oompah.orchestrator import Orchestrator
from oompah.server import app


def _fake_orchestrator(timeout: int = 3600):
    return SimpleNamespace(
        config=SimpleNamespace(restart_drain_timeout_seconds=timeout),
        state=SimpleNamespace(running={}),
        _restart_in_progress=False,
        _restart_drain_started=False,
        _restart_drain_scheduled=False,
        _restart_drain_task=None,
        _restart_drain_owner=None,
        _restart_request_id=None,
        _restart_requested_at=None,
        _restart_initial_running=0,
        _restart_persistence_failed=False,
        _provider_admission_generation=0,
        _paused=False,
        _quiesced=False,
        _stopping=False,
        _restart_requested=False,
        _save_paused_state=MagicMock(),
        _notify_observers=MagicMock(),
        graceful_restart=AsyncMock(),
    )


def _real_orchestrator(tmp_path) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    project_store.get.return_value = SimpleNamespace(paused=False)
    return Orchestrator(
        config=ServiceConfig(duplicate_preflight_max_agents=0),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        state_path=str(tmp_path / "state.json"),
    )


def _json_request(body: dict[str, object]) -> Request:
    encoded = json.dumps(body).encode()

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": encoded, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/orchestrator/restart",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
        },
        _receive,
    )


def test_restart_api_uses_configured_default_and_returns_request_identity():
    original = server._orchestrator
    fake = _fake_orchestrator(4321)
    server._orchestrator = fake
    try:
        response = TestClient(app).post("/api/v1/orchestrator/restart", json={})
    finally:
        server._orchestrator = original

    assert response.status_code == 200
    body = response.json()
    assert body["drain_timeout_s"] == 4321
    assert body["restart_request_id"]
    assert body["coalesced"] is False
    fake.graceful_restart.assert_awaited_once()


def test_repeated_restart_request_is_coalesced():
    original = server._orchestrator
    fake = _fake_orchestrator()
    fake._restart_in_progress = True
    fake._restart_request_id = "restart-existing"
    fake._restart_drain_scheduled = True
    server._orchestrator = fake
    try:
        response = TestClient(app).post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 12},
        )
    finally:
        server._orchestrator = original

    assert response.status_code == 202
    assert response.json()["restart_request_id"] == "restart-existing"
    assert response.json()["coalesced"] is True
    fake.graceful_restart.assert_not_awaited()


def test_restart_claim_can_be_started_only_by_matching_identity():
    original = server._orchestrator
    fake = _fake_orchestrator()
    server._orchestrator = fake
    client = TestClient(app)
    try:
        claimed = client.post(
            "/api/v1/orchestrator/restart",
            json={"claim_only": True},
        )
        request_id = claimed.json()["restart_request_id"]
        mismatched = client.post(
            "/api/v1/orchestrator/restart",
            json={"restart_request_id": "another-claim", "drain_timeout_s": 0},
        )
        started = client.post(
            "/api/v1/orchestrator/restart",
            json={"restart_request_id": request_id, "drain_timeout_s": 0},
        )
    finally:
        server._orchestrator = original

    assert claimed.status_code == 200
    assert fake._restart_in_progress is True
    assert mismatched.status_code == 409
    assert started.status_code == 200
    assert started.json()["restart_request_id"] == request_id
    fake.graceful_restart.assert_awaited_once()


def test_unscheduled_restart_claim_can_be_cancelled():
    original = server._orchestrator
    fake = _fake_orchestrator()
    server._orchestrator = fake
    client = TestClient(app)
    try:
        claimed = client.post(
            "/api/v1/orchestrator/restart",
            json={"claim_only": True},
        )
        request_id = claimed.json()["restart_request_id"]
        cancelled = client.post(
            "/api/v1/orchestrator/restart",
            json={"cancel_claim": True, "restart_request_id": request_id},
        )
    finally:
        server._orchestrator = original

    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled"] is True
    assert fake._restart_in_progress is False
    fake.graceful_restart.assert_not_awaited()


def test_restart_task_creation_failure_restores_cancellable_preclaim():
    """A scheduler failure cannot turn a valid preclaim into a permanent fence."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    server._orchestrator = fake
    client = TestClient(app)
    try:
        claimed = client.post(
            "/api/v1/orchestrator/restart",
            json={"claim_only": True},
        )
        request_id = claimed.json()["restart_request_id"]
        claimed_generation = fake._provider_admission_generation
        with patch.object(
            server,
            "_create_restart_drain_task",
            side_effect=RuntimeError("event loop rejected task"),
        ):
            failed = client.post(
                "/api/v1/orchestrator/restart",
                json={"restart_request_id": request_id, "drain_timeout_s": 0},
            )
        restored_claim = (
            fake._restart_in_progress,
            fake._restart_request_id,
            fake._restart_drain_scheduled,
            fake._restart_drain_started,
            fake._restart_drain_task,
            fake._restart_drain_owner,
            fake._provider_admission_generation,
        )
        cancelled = client.post(
            "/api/v1/orchestrator/restart",
            json={"cancel_claim": True, "restart_request_id": request_id},
        )
    finally:
        server._orchestrator = original

    assert failed.status_code == 500
    assert restored_claim == (
        True,
        request_id,
        False,
        False,
        None,
        None,
        claimed_generation,
    )
    assert fake._restart_in_progress is False
    assert fake._provider_admission_generation == claimed_generation + 1
    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled"] is True
    fake.graceful_restart.assert_not_awaited()


def test_restart_drain_exception_after_task_creation_restores_full_state():
    """A failed published drain releases every fence and can be rescheduled."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    fake.graceful_restart = AsyncMock(side_effect=RuntimeError("drain failed"))
    server._orchestrator = fake
    client = TestClient(app)
    try:
        first = client.post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 0},
        )
        restored = (
            fake._restart_in_progress,
            fake._restart_drain_scheduled,
            fake._restart_drain_started,
            fake._restart_drain_task,
            fake._restart_drain_owner,
            fake._paused,
            fake._quiesced,
            fake._stopping,
            fake._restart_requested,
        )
        fake.graceful_restart = AsyncMock(return_value=None)
        second = client.post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 0},
        )
    finally:
        server._orchestrator = original

    assert first.status_code == 200
    assert restored == (False, False, False, None, None, False, False, False, False)
    assert fake._restart_in_progress is True  # second request owns a fresh claim
    assert second.status_code == 200
    assert second.json()["coalesced"] is False


def test_restart_drain_failure_preserves_intervening_lifecycle_fence():
    """A newer lifecycle generation wins over the API rollback snapshot."""

    original = server._orchestrator
    fake = _fake_orchestrator()

    async def _fenced_failure(**_kwargs):
        fake._paused = True
        fake._quiesced = True
        fake._stopping = True
        fake._restart_requested = True
        fake._provider_admission_generation += 1
        raise RuntimeError("drain failed after a newer lifecycle fence")

    fake.graceful_restart = AsyncMock(side_effect=_fenced_failure)
    server._orchestrator = fake
    try:
        response = TestClient(app).post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 0},
        )
    finally:
        server._orchestrator = original

    assert response.status_code == 200
    assert fake._restart_in_progress is False
    assert fake._restart_drain_task is None
    assert fake._paused is True
    assert fake._quiesced is True
    assert fake._stopping is True
    assert fake._restart_requested is True
    assert fake._provider_admission_generation == 2


def test_restart_drain_failure_preserves_persistence_fail_closed_fence():
    """The HTTP completion callback cannot erase a durable-state failure."""

    original = server._orchestrator
    fake = _fake_orchestrator()

    async def _fail_closed_restart(**_kwargs):
        fake._restart_persistence_failed = True
        fake._quiesced = True
        fake._provider_admission_generation += 1
        raise OSError("restart rows were not durably persisted")

    fake.graceful_restart = AsyncMock(side_effect=_fail_closed_restart)
    server._orchestrator = fake
    try:
        response = TestClient(app).post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 0},
        )
    finally:
        server._orchestrator = original

    assert response.status_code == 200
    assert fake._restart_in_progress is False
    assert fake._restart_drain_task is None
    assert fake._restart_persistence_failed is True
    assert fake._quiesced is True
    assert fake._provider_admission_generation >= 2


def test_restart_drain_cancellation_after_task_creation_restores_full_state():
    """CancelledError follows the same rollback path as a drain exception."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    cancelled = AsyncMock(side_effect=asyncio.CancelledError())
    fake.graceful_restart = cancelled
    server._orchestrator = fake
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": 0},
        )
    finally:
        server._orchestrator = original

    assert response.status_code == 200
    assert fake._restart_in_progress is False
    assert fake._restart_drain_scheduled is False
    assert fake._restart_drain_started is False
    assert fake._restart_drain_task is None
    assert fake._restart_drain_owner is None
    assert fake._paused is False
    assert fake._quiesced is False
    assert fake._stopping is False
    assert fake._restart_requested is False


def test_restart_api_rejects_invalid_timeout():
    original = server._orchestrator
    server._orchestrator = _fake_orchestrator()
    try:
        response = TestClient(app).post(
            "/api/v1/orchestrator/restart",
            json={"drain_timeout_s": "eventually"},
        )
    finally:
        server._orchestrator = original

    assert response.status_code == 400
    assert "non-negative" in response.json()["error"]


def test_quiesce_api_preserves_running_workers():
    """Lifecycle quiesce is separate from destructive operator pause."""
    original = server._orchestrator
    fake = _fake_orchestrator()
    fake.quiesce = MagicMock()
    server._orchestrator = fake
    try:
        response = TestClient(app).post("/api/v1/orchestrator/quiesce", json={})
    finally:
        server._orchestrator = original

    assert response.status_code == 200
    assert response.json()["quiesced"] is True
    fake.quiesce.assert_called_once_with(notify=False)


@pytest.mark.asyncio
async def test_quiesce_lock_contention_is_bounded_without_blocking_health(monkeypatch):
    """A workflow thread cannot park the HTTP loop while quiesce fences."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    fake.quiesce = MagicMock()
    fake._provider_admission_lock = threading.RLock()
    lock_owned = threading.Event()
    release_lock = threading.Event()

    def _hold_publication_fence() -> None:
        with fake._provider_admission_lock:
            lock_owned.set()
            assert release_lock.wait(timeout=2)

    holder = threading.Thread(target=_hold_publication_fence)
    holder.start()
    assert lock_owned.wait(timeout=1)
    monkeypatch.setattr(server, "_LIFECYCLE_ADMISSION_TIMEOUT_SECONDS", 0.05)
    server._orchestrator = fake
    try:
        quiesce = asyncio.create_task(server.api_orchestrator_quiesce())
        await asyncio.sleep(0.01)
        started = time.monotonic()
        health = await asyncio.wait_for(server.healthz(), timeout=0.1)
        elapsed = time.monotonic() - started
        response = await asyncio.wait_for(quiesce, timeout=0.2)
    finally:
        release_lock.set()
        holder.join(timeout=1)
        server._orchestrator = original

    assert json.loads(health.body)["status"] == "ok"
    assert elapsed < 0.1
    assert response.status_code == 503
    assert json.loads(response.body)["retryable"] is True
    fake.quiesce.assert_not_called()
    assert fake._restart_in_progress is False


@pytest.mark.asyncio
async def test_restart_claim_contention_is_bounded_without_blocking_health(
    monkeypatch,
):
    """A slow publication fence cannot wedge restart claim or health I/O."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    fake._provider_admission_lock = threading.RLock()
    lock_owned = threading.Event()
    release_lock = threading.Event()

    def _hold_publication_fence() -> None:
        with fake._provider_admission_lock:
            lock_owned.set()
            assert release_lock.wait(timeout=2)

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"{}", "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/orchestrator/restart",
            "headers": [(b"content-type", b"application/json")],
            "query_string": b"",
        },
        _receive,
    )
    holder = threading.Thread(target=_hold_publication_fence)
    holder.start()
    assert lock_owned.wait(timeout=1)
    monkeypatch.setattr(server, "_LIFECYCLE_ADMISSION_TIMEOUT_SECONDS", 0.05)
    server._orchestrator = fake
    try:
        restart = asyncio.create_task(server.api_orchestrator_restart(request))
        await asyncio.sleep(0.01)
        started = time.monotonic()
        health = await asyncio.wait_for(server.healthz(), timeout=0.1)
        elapsed = time.monotonic() - started
        response = await asyncio.wait_for(restart, timeout=0.2)
    finally:
        release_lock.set()
        holder.join(timeout=1)
        server._orchestrator = original

    assert json.loads(health.body)["status"] == "ok"
    assert elapsed < 0.1
    assert response.status_code == 503
    assert json.loads(response.body)["retryable"] is True
    assert fake._restart_in_progress is False
    fake.graceful_restart.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_lifecycle_controls_outlive_blocked_observer_snapshot(
    tmp_path,
):
    """Snapshot publication cannot own HTTP or provider admission authority."""

    original = server._orchestrator
    orch = _real_orchestrator(tmp_path)
    snapshot_entered = threading.Event()
    release_snapshot = threading.Event()
    snapshot_finished = threading.Event()

    def _blocked_project_snapshot() -> list[object]:
        snapshot_entered.set()
        try:
            assert release_snapshot.wait(timeout=3)
            return []
        finally:
            snapshot_finished.set()

    # Exercise the real get_snapshot -> review/project authority path used by
    # _notify_observers, rather than replacing the snapshot method itself.
    orch.project_store.list_all.side_effect = _blocked_project_snapshot
    server._orchestrator = orch
    try:
        started = time.monotonic()
        quiesced = await asyncio.wait_for(
            server.api_orchestrator_quiesce(),
            timeout=0.2,
        )
        quiesce_elapsed = time.monotonic() - started
        assert await asyncio.to_thread(snapshot_entered.wait, 1)

        started = time.monotonic()
        health = await asyncio.wait_for(server.healthz(), timeout=0.1)
        health_elapsed = time.monotonic() - started

        claim = await asyncio.wait_for(
            server.api_orchestrator_restart(
                _json_request(
                    {
                        "claim_only": True,
                        "restart_request_id": "blocked-snapshot-claim",
                    }
                )
            ),
            timeout=0.2,
        )
        cancelled = await asyncio.wait_for(
            server.api_orchestrator_restart(
                _json_request(
                    {
                        "cancel_claim": True,
                        "restart_request_id": "blocked-snapshot-claim",
                    }
                )
            ),
            timeout=0.2,
        )
        resumed = await asyncio.wait_for(
            server.api_orchestrator_resume(),
            timeout=0.2,
        )

        assert orch._provider_admission_lock.acquire(blocking=False)
        orch._provider_admission_lock.release()
    finally:
        release_snapshot.set()
        await asyncio.to_thread(snapshot_finished.wait, 1)
        server._orchestrator = original

    assert quiesced.status_code == 200
    assert quiesce_elapsed < 0.2
    assert json.loads(health.body)["status"] == "ok"
    assert health_elapsed < 0.1
    assert claim.status_code == 200
    assert cancelled.status_code == 200
    assert resumed.status_code == 200
    assert orch._quiesced is False
    assert orch._restart_in_progress is False


@pytest.mark.asyncio
async def test_restart_drain_snapshot_and_journal_work_stay_off_http_loop(
    tmp_path,
    monkeypatch,
):
    """Graceful drain staging cannot block health or cancellation responses."""

    original = server._orchestrator
    orch = _real_orchestrator(tmp_path)
    snapshot_entered = threading.Event()
    release_snapshot = threading.Event()
    snapshot_finished = threading.Event()
    observer_published = threading.Event()
    journal_entered = threading.Event()
    release_journal = threading.Event()

    def _blocked_snapshot() -> dict[str, object]:
        snapshot_entered.set()
        try:
            assert release_snapshot.wait(timeout=3)
            return {}
        finally:
            snapshot_finished.set()

    def _blocked_merge(*_args, **_kwargs) -> tuple[bool, int, int]:
        journal_entered.set()
        assert release_journal.wait(timeout=3)
        return True, 0, 0

    monkeypatch.setattr(orch, "get_snapshot", _blocked_snapshot)
    monkeypatch.setattr(orch, "_merge_restart_issues", _blocked_merge)
    orch._observers.append(lambda _snapshot: observer_published.set())
    server._orchestrator = orch
    drain_task = None
    try:
        response = await server.api_orchestrator_restart(
            _json_request(
                {
                    "drain_timeout_s": 0,
                    "restart_request_id": "slow-drain-staging",
                }
            )
        )
        drain_task = orch._restart_drain_task
        assert drain_task is not None
        assert await asyncio.to_thread(snapshot_entered.wait, 1)
        # The full snapshot remains blocked permanently from the drain's point
        # of view, but authoritative journal staging must still start.
        assert await asyncio.to_thread(journal_entered.wait, 1)

        started = time.monotonic()
        health_during_snapshot = await asyncio.wait_for(
            server.healthz(), timeout=0.1
        )
        cancel_during_snapshot = await asyncio.wait_for(
            server.api_orchestrator_restart(
                _json_request(
                    {
                        "cancel_claim": True,
                        "restart_request_id": "slow-drain-staging",
                    }
                )
            ),
            timeout=0.2,
        )
        snapshot_control_elapsed = time.monotonic() - started
        started = time.monotonic()
        health_during_journal = await asyncio.wait_for(
            server.healthz(), timeout=0.1
        )
        journal_health_elapsed = time.monotonic() - started
        release_journal.set()
        await asyncio.wait_for(asyncio.shield(drain_task), timeout=1)
        assert snapshot_finished.is_set() is False
        with orch._lifecycle_publication_lock:
            assert orch._lifecycle_publication_running is True
            assert (
                orch._lifecycle_publication_pending_generation
                == orch._provider_admission_generation
            )
        # A delayed older request cannot replace the coalesced latest state.
        assert orch.request_lifecycle_publication(
            expected_generation=orch._provider_admission_generation - 1
        )
        with orch._lifecycle_publication_lock:
            assert (
                orch._lifecycle_publication_pending_generation
                == orch._provider_admission_generation
            )

        # Teardown fences the running old-generation snapshot and rejects new
        # work without waiting for the uncooperative snapshot thread.
        orch._shutdown_lifecycle_publications()
        assert (
            orch.request_lifecycle_publication(
                expected_generation=orch._provider_admission_generation
            )
            is False
        )
        release_snapshot.set()
        assert await asyncio.to_thread(snapshot_finished.wait, 1)
    finally:
        release_snapshot.set()
        release_journal.set()
        if drain_task is not None and not drain_task.done():
            await asyncio.wait_for(asyncio.shield(drain_task), timeout=1)
        server._orchestrator = original

    assert response.status_code == 200
    assert json.loads(health_during_snapshot.body)["status"] == "ok"
    assert cancel_during_snapshot.status_code == 409
    assert snapshot_control_elapsed < 0.2
    assert json.loads(health_during_journal.body)["status"] == "ok"
    assert journal_health_elapsed < 0.1
    assert orch._stopping is True
    assert orch._restart_requested is True
    assert observer_published.is_set() is False


@pytest.mark.asyncio
async def test_restart_failure_does_not_await_permanently_blocked_publication(
    tmp_path,
    monkeypatch,
):
    """Rollback completion is independent of both success/failure snapshots."""

    orch = _real_orchestrator(tmp_path)
    snapshot_entered = threading.Event()
    release_snapshot = threading.Event()
    snapshot_finished = threading.Event()
    observer_published = threading.Event()

    def _blocked_snapshot() -> dict[str, object]:
        snapshot_entered.set()
        try:
            assert release_snapshot.wait(timeout=3)
            return {}
        finally:
            snapshot_finished.set()

    def _failed_merge(*_args, **_kwargs) -> tuple[bool, int, int]:
        raise OSError("injected restart journal failure")

    monkeypatch.setattr(orch, "get_snapshot", _blocked_snapshot)
    monkeypatch.setattr(orch, "_merge_restart_issues", _failed_merge)
    orch._observers.append(lambda _snapshot: observer_published.set())
    restart_task = asyncio.create_task(orch.graceful_restart(drain_timeout_s=0))
    try:
        assert await asyncio.to_thread(snapshot_entered.wait, 1)
        with pytest.raises(OSError, match="restart journal failure"):
            await asyncio.wait_for(asyncio.shield(restart_task), timeout=0.5)
        assert snapshot_finished.is_set() is False
        assert orch._restart_in_progress is False
        assert orch._stopping is False
        orch._shutdown_lifecycle_publications()
        release_snapshot.set()
        assert await asyncio.to_thread(snapshot_finished.wait, 1)
    finally:
        release_snapshot.set()
        if not restart_task.done():
            restart_task.cancel()
            await asyncio.gather(restart_task, return_exceptions=True)
        orch._shutdown_lifecycle_publications()

    assert observer_published.is_set() is False


@pytest.mark.asyncio
async def test_failed_restart_cleanup_persistence_stays_off_http_loop():
    """Uncontended drain cleanup cannot synchronously park the API loop."""

    original = server._orchestrator
    fake = _fake_orchestrator()
    fake.graceful_restart = AsyncMock(side_effect=RuntimeError("drain failed"))
    save_entered = threading.Event()
    release_save = threading.Event()
    save_finished = threading.Event()

    def _blocked_save() -> None:
        save_entered.set()
        try:
            assert release_save.wait(timeout=3)
        finally:
            save_finished.set()

    fake._save_paused_state = _blocked_save
    server._orchestrator = fake
    try:
        response = await server.api_orchestrator_restart(_json_request({}))
        assert await asyncio.to_thread(save_entered.wait, 1)
        started = time.monotonic()
        health = await asyncio.wait_for(server.healthz(), timeout=0.1)
        claim = await asyncio.wait_for(
            server.api_orchestrator_restart(
                _json_request(
                    {
                        "claim_only": True,
                        "restart_request_id": "post-failure-claim",
                    }
                )
            ),
            timeout=0.2,
        )
        cancelled = await asyncio.wait_for(
            server.api_orchestrator_restart(
                _json_request(
                    {
                        "cancel_claim": True,
                        "restart_request_id": "post-failure-claim",
                    }
                )
            ),
            timeout=0.2,
        )
        control_elapsed = time.monotonic() - started
    finally:
        release_save.set()
        await asyncio.to_thread(save_finished.wait, 1)
        server._orchestrator = original

    assert response.status_code == 200
    assert json.loads(health.body)["status"] == "ok"
    assert claim.status_code == 200
    assert cancelled.status_code == 200
    assert control_elapsed < 0.2
    assert fake._restart_in_progress is False


@pytest.mark.asyncio
async def test_failed_restart_rollback_cannot_overwrite_newer_durable_pause(
    tmp_path,
    monkeypatch,
):
    """Pause persistence serializes after an older rollback generation."""

    original_orchestrator = server._orchestrator
    orch = _real_orchestrator(tmp_path)

    async def _failed_drain(**_kwargs) -> None:
        raise RuntimeError("injected drain failure before lifecycle mutation")

    false_save_entered = threading.Event()
    release_false_save = threading.Event()
    pause_finished = threading.Event()
    paused_writes: list[bool] = []
    original_save_state = orch._save_state

    def _ordered_save(**updates: object) -> bool:
        if "paused" in updates:
            paused = bool(updates["paused"])
            if not paused and not false_save_entered.is_set():
                false_save_entered.set()
                assert release_false_save.wait(timeout=3)
            saved = original_save_state(**updates)
            paused_writes.append(paused)
            return saved
        return original_save_state(**updates)

    def _pause() -> None:
        try:
            orch.pause()
        finally:
            pause_finished.set()

    monkeypatch.setattr(orch, "graceful_restart", _failed_drain)
    monkeypatch.setattr(orch, "_save_state", _ordered_save)
    server._orchestrator = orch
    pause_thread = threading.Thread(target=_pause, name="newer-operator-pause")
    try:
        response = await server.api_orchestrator_restart(_json_request({}))
        assert await asyncio.to_thread(false_save_entered.wait, 1)
        pause_thread.start()
        await asyncio.sleep(0.05)
        # The newer pause cannot slip its durable True write ahead of the
        # older rollback's already-admitted False write.
        assert pause_finished.is_set() is False
        health = await asyncio.wait_for(server.healthz(), timeout=0.1)
        release_false_save.set()
        assert await asyncio.to_thread(pause_finished.wait, 1)
        pause_thread.join(timeout=1)
    finally:
        release_false_save.set()
        if pause_thread.is_alive():
            pause_thread.join(timeout=1)
        orch._shutdown_lifecycle_publications()
        server._orchestrator = original_orchestrator

    durable_state = orch._load_state()
    assert response.status_code == 200
    assert json.loads(health.body)["status"] == "ok"
    assert paused_writes[-2:] == [False, True]
    assert orch._paused is True
    assert durable_state["paused"] is True
