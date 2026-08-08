"""Regression coverage for owned orchestrator test and shutdown resources."""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import oompah.orchestrator as orchestrator_module
from oompah.config import ServiceConfig
from oompah.implementation_workflow_adapter import ImplementationReceiptStore
from oompah.orchestrator import Orchestrator
from oompah.roles import RoleStore
from oompah.task_transition_service import TransitionJournal
from oompah.workflow_runtime import WorkflowRuntime


def _orchestrator(tmp_path) -> Orchestrator:
    project_store = MagicMock()
    project_store.list_all.return_value = []
    return Orchestrator(
        config=ServiceConfig(
            tracker_kind="oompah_md",
            duplicate_preflight_max_agents=0,
        ),
        workflow_path="WORKFLOW.md",
        project_store=project_store,
        role_store=RoleStore(path=str(tmp_path / "roles.json")),
        state_path=str(tmp_path / "state.json"),
    )


def _assert_store_closed(store) -> None:
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        store._conn.execute("SELECT 1")


def test_autouse_registry_closes_owned_pools_and_stores_idempotently(
    tmp_path,
    _close_owned_oompah_resources,
) -> None:
    orch = _orchestrator(tmp_path)
    orch._integration_pool = ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="integration-test",
    )
    receipt_store = ImplementationReceiptStore(
        str(tmp_path / "registry-receipts.sqlite3")
    )
    orch._implementation_receipt_store = receipt_store
    pools = (orch._tick_pool, orch._refresh_pool, orch._integration_pool)
    stores = (
        orch.coordination_store,
        orch.integration_queue,
        orch.review_capacity_store,
        orch.workflow_job_store,
        orch.task_transition_journal,
        receipt_store,
    )

    _close_owned_oompah_resources.close_all()
    _close_owned_oompah_resources.close_all()

    for pool in pools:
        with pytest.raises(RuntimeError, match="cannot schedule new futures"):
            pool.submit(lambda: None)
        assert not any(thread.is_alive() for thread in pool._threads)
    for store in stores:
        _assert_store_closed(store)
    assert orch._implementation_receipt_store is None
    assert orch.workflow_job_store._authority_lock_fd == -1


def test_autouse_registry_rejects_orchestrator_after_boundary_is_sealed(
    tmp_path,
    _close_owned_oompah_resources,
) -> None:
    _close_owned_oompah_resources.close_all()

    with pytest.raises(
        RuntimeError,
        match="orchestrator constructed after test resource boundary sealed",
    ):
        _orchestrator(tmp_path)


def test_autouse_registry_waits_for_admitted_constructor_before_cleanup(
    tmp_path,
    monkeypatch,
    _close_owned_oompah_resources,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    real_selector = orchestrator_module.CandidateSelector

    def blocking_selector(*args, **kwargs):
        entered.set()
        if not release.wait(3):
            raise RuntimeError("constructor test barrier timed out")
        return real_selector(*args, **kwargs)

    monkeypatch.setattr(orchestrator_module, "CandidateSelector", blocking_selector)
    result: dict[str, Orchestrator] = {}
    errors: list[BaseException] = []

    def construct() -> None:
        try:
            result["orchestrator"] = _orchestrator(tmp_path)
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    constructor = threading.Thread(target=construct, name="constructor-race")
    constructor.start()
    assert entered.wait(2)

    cleanup = threading.Thread(
        target=_close_owned_oompah_resources.close_all,
        name="cleanup-race",
    )
    cleanup.start()
    assert _close_owned_oompah_resources._seal_event.wait(2)
    assert cleanup.is_alive()

    release.set()
    constructor.join(timeout=3)
    cleanup.join(timeout=3)

    assert not constructor.is_alive()
    assert not cleanup.is_alive()
    assert errors == []
    orch = result["orchestrator"]
    for pool in (orch._tick_pool, orch._refresh_pool):
        with pytest.raises(RuntimeError, match="cannot schedule new futures"):
            pool.submit(lambda: None)
    _assert_store_closed(orch.workflow_job_store)


@pytest.mark.asyncio
async def test_concurrent_background_drains_close_every_owned_store_once(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    stores = (
        orch.coordination_store,
        orch.integration_queue,
        orch.review_capacity_store,
        orch.workflow_job_store,
        orch.task_transition_journal,
    )
    closes = []
    for store in stores:
        original_close = store.close
        tracked_close = MagicMock(wraps=original_close)
        store.close = tracked_close
        closes.append(tracked_close)

    await asyncio.gather(
        orch._drain_background_work(),
        orch._drain_background_work(),
    )

    for tracked_close, store in zip(closes, stores, strict=True):
        tracked_close.assert_called_once_with()
        _assert_store_closed(store)
    assert orch.workflow_job_store._authority_lock_fd == -1


@pytest.mark.asyncio
async def test_background_drain_closes_lazy_receipt_and_runtime_journal(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    runtime_journal = TransitionJournal(str(tmp_path / "runtime-transitions.sqlite3"))
    orch.workflow_runtime = WorkflowRuntime(
        project_bindings={},
        store=orch.workflow_job_store,
        journals={"proj-1": runtime_journal},
        mode="off",
    )
    receipt_store = ImplementationReceiptStore(
        str(tmp_path / "implementation-receipts.sqlite3")
    )
    orch._implementation_receipt_store = receipt_store

    await orch._drain_background_work()

    assert orch.workflow_runtime._closed is True
    _assert_store_closed(runtime_journal)
    _assert_store_closed(receipt_store)
    assert orch._implementation_receipt_store is None


@pytest.mark.asyncio
async def test_background_drain_retries_only_resource_whose_close_failed(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    target = orch.integration_queue
    original_close = target.close
    attempts = 0

    def fail_once() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient close failure")
        original_close()

    target.close = fail_once

    with pytest.raises(
        RuntimeError,
        match="failed to close orchestrator-owned resources: integration_queue",
    ):
        await orch._drain_background_work()
    assert orch._owned_persistent_stores_closed is False

    await orch._drain_background_work()

    assert attempts == 2
    assert orch._owned_persistent_stores_closed is True
    _assert_store_closed(target)


@pytest.mark.asyncio
async def test_background_drain_ignores_non_resource_runtime_stub_and_closes_replacement(
    tmp_path,
) -> None:
    orch = _orchestrator(tmp_path)
    orch.workflow_runtime = SimpleNamespace(pending_operation_count=0)
    first = ImplementationReceiptStore(str(tmp_path / "first-receipt.sqlite3"))
    orch._implementation_receipt_store = first

    await orch._drain_background_work()
    _assert_store_closed(first)

    replacement = ImplementationReceiptStore(
        str(tmp_path / "replacement-receipt.sqlite3")
    )
    orch._implementation_receipt_store = replacement
    orch._close_owned_persistent_stores()

    _assert_store_closed(replacement)
    assert orch._implementation_receipt_store is None
