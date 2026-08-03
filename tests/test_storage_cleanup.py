"""Tests for daily and pressure-triggered owned-storage cleanup (OOMPAH-506)."""

import os
import time
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from oompah.config import ServiceConfig
from oompah.coordination import CoordinationStore
from oompah.orchestrator import Orchestrator
from oompah.storage_cleanup import (
    StoragePressure,
    cleanup_owned_storage,
    inspect_storage_pressure,
)


def _age(path: Path, seconds: int = 10_000) -> None:
    timestamp = time.time() - seconds
    os.utime(path, (timestamp, timestamp), follow_symlinks=False)


def _cleanup(tmp_path, **overrides):
    temp = tmp_path / "temp"
    logs = tmp_path / "logs"
    temp.mkdir(exist_ok=True)
    logs.mkdir(exist_ok=True)
    options = {
        "temp_root": temp,
        "agent_log_root": logs,
        "protected_paths": set(),
        "min_age_seconds": 3600,
        "log_retention_seconds": 3600,
        "batch_limit": 20,
        "byte_limit": 10_000_000,
    }
    options.update(overrides)
    return temp, logs, cleanup_owned_storage(**options)


def test_removes_stale_temp_entries_and_jsonl_logs(tmp_path):
    temp = tmp_path / "temp"
    logs = tmp_path / "logs"
    temp.mkdir()
    logs.mkdir()
    stale_cache = temp / "build-cache"
    stale_cache.mkdir()
    (stale_cache / "payload").write_bytes(b"x" * 20)
    stale_log = logs / "task.jsonl"
    stale_log.write_text("{}")
    _age(stale_cache)
    _age(stale_log)

    _, _, result = _cleanup(tmp_path)

    assert not stale_cache.exists()
    assert not stale_log.exists()
    assert result.cleaned_count == 2
    assert result.reclaimed_bytes > 0


def test_removes_stale_tree_with_read_only_directories_without_following_links(
    tmp_path,
):
    temp = tmp_path / "temp"
    logs = tmp_path / "logs"
    temp.mkdir()
    logs.mkdir()
    stale_cache = temp / "build-cache"
    read_only = stale_cache / "releases" / "0.2.0"
    read_only.mkdir(parents=True)
    payload = read_only / "payload"
    payload.write_text("cached")
    outside = tmp_path / "outside"
    outside.write_text("keep")
    (read_only / "outside-link").symlink_to(outside)
    payload.chmod(0o400)
    read_only.chmod(0o555)
    (stale_cache / "releases").chmod(0o555)
    _age(stale_cache)

    _, _, result = _cleanup(tmp_path)

    assert not stale_cache.exists()
    assert outside.read_text() == "keep"
    assert result.cleaned_count == 1
    assert result.errors == []


def test_preserves_recent_unknown_active_vm_and_symlink_entries(tmp_path):
    temp = tmp_path / "temp"
    logs = tmp_path / "logs"
    temp.mkdir()
    logs.mkdir()
    recent = temp / "recent"
    recent.mkdir()
    vm = temp / "qualification.qcow2"
    vm.write_bytes(b"vm")
    unknown_log = logs / "README.txt"
    unknown_log.write_text("keep")
    active_log = logs / "active.jsonl"
    active_log.write_text("{}")
    target = tmp_path / "outside"
    target.write_text("outside")
    link = temp / "outside-link"
    link.symlink_to(target)
    for path in (vm, unknown_log, active_log, link):
        _age(path)

    _, _, result = _cleanup(
        tmp_path, protected_paths={str(active_log)}
    )

    assert recent.exists()
    assert vm.exists()
    assert unknown_log.exists()
    assert active_log.exists()
    assert link.is_symlink()
    assert target.read_text() == "outside"
    assert result.cleaned_count == 0


def test_batch_and_byte_limits_defer_remaining_work(tmp_path):
    temp = tmp_path / "temp"
    logs = tmp_path / "logs"
    temp.mkdir()
    logs.mkdir()
    for number in range(3):
        path = temp / f"cache-{number}"
        path.write_bytes(b"x" * 20)
        _age(path, 20_000 - number)

    _, _, result = _cleanup(tmp_path, batch_limit=1, byte_limit=1000)

    assert result.cleaned_count == 1
    assert result.deferred is True
    assert len(list(temp.iterdir())) == 2


def test_oversized_entry_is_preserved_by_byte_limit(tmp_path):
    temp = tmp_path / "temp"
    logs = tmp_path / "logs"
    temp.mkdir()
    logs.mkdir()
    cache = temp / "large-cache"
    cache.write_bytes(b"x" * 4096)
    _age(cache)

    _, _, result = _cleanup(tmp_path, byte_limit=1024)

    assert cache.exists()
    assert result.cleaned_count == 0
    assert result.deferred is True


def test_disappearing_path_is_a_safe_noop(tmp_path):
    temp = tmp_path / "temp"
    logs = tmp_path / "logs"
    temp.mkdir()
    logs.mkdir()
    stale = temp / "stale"
    stale.write_text("x")
    _age(stale)

    with patch(
        "oompah.storage_cleanup._remove_owned_entry",
        side_effect=FileNotFoundError,
    ):
        _, _, result = _cleanup(tmp_path)

    assert result.cleaned_count == 0
    assert result.errors == []


def test_permission_error_is_recorded_and_does_not_escape(tmp_path):
    temp = tmp_path / "temp"
    logs = tmp_path / "logs"
    temp.mkdir()
    logs.mkdir()
    stale = temp / "stale"
    stale.write_text("x")
    _age(stale)

    with patch(
        "oompah.storage_cleanup._remove_owned_entry",
        side_effect=PermissionError("denied"),
    ):
        _, _, result = _cleanup(tmp_path)

    assert result.cleaned_count == 0
    assert any("denied" in error for error in result.errors)


def test_pressure_uses_free_byte_or_percent_threshold(tmp_path):
    Usage = namedtuple("Usage", "total used free")
    with patch(
        "oompah.storage_cleanup.shutil.disk_usage",
        return_value=Usage(1000, 960, 40),
    ):
        pressure = inspect_storage_pressure(
            [tmp_path],
            min_free_bytes=30,
            min_free_percent=5,
        )

    assert pressure.pressured is True
    assert pressure.free_bytes == 40
    assert pressure.free_percent == 4.0


def _scheduler(config: ServiceConfig) -> Orchestrator:
    import threading
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.config = config
    orchestrator._maintenance_jobs = {}
    orchestrator._maintenance_status = {}
    orchestrator._storage_cleanup_paths = lambda: ("/tmp/a", "/tmp/b", ["/tmp"])
    orchestrator._retry_authority_lock = threading.RLock()
    return orchestrator


def test_daily_scan_is_throttled_between_intervals():
    orchestrator = _scheduler(
        ServiceConfig(storage_cleanup_interval_seconds=86400)
    )
    calls = []
    orchestrator._do_cleanup_storage = lambda: calls.append("run")
    healthy = StoragePressure(False, 100_000, 50.0)

    with patch(
        "oompah.orchestrator.inspect_storage_pressure",
        return_value=healthy,
    ):
        orchestrator._maybe_cleanup_storage()
        orchestrator._maybe_cleanup_storage()

    assert calls == ["run"]


def test_pressure_overrides_daily_next_run_and_repeats_batches():
    orchestrator = _scheduler(
        ServiceConfig(storage_cleanup_interval_seconds=86400)
    )
    calls = []
    orchestrator._do_cleanup_storage = lambda: calls.append("run")
    pressure = StoragePressure(True, 10, 1.0)

    with patch(
        "oompah.orchestrator.inspect_storage_pressure",
        return_value=pressure,
    ):
        orchestrator._maybe_cleanup_storage()
        orchestrator._maybe_cleanup_storage()

    assert calls == ["run", "run"]
    assert orchestrator._storage_cleanup_trigger == "storage_pressure"


def test_storage_cleanup_prunes_old_read_coordination_messages(tmp_path):
    orchestrator = _scheduler(
        ServiceConfig(
            temp_root=str(tmp_path / "temp"),
            coordination_retention_seconds=60,
        )
    )
    (tmp_path / "temp").mkdir()
    log_root = tmp_path / "logs"
    log_root.mkdir()
    orchestrator._storage_cleanup_paths = lambda: (
        str(tmp_path / "temp"),
        str(log_root),
        [str(tmp_path)],
    )
    orchestrator.state = type("State", (), {"running": {}})()
    orchestrator.project_store = type(
        "Projects",
        (),
        {"list_all": lambda self: []},
    )()
    orchestrator._cleanup_terminal_worktrees = lambda projects: 0
    coordination = CoordinationStore(str(tmp_path / "coordination.sqlite3"))
    orchestrator.coordination_store = coordination

    with patch.object(coordination, "prune_before", return_value=3) as prune:
        orchestrator._do_cleanup_storage()

    assert prune.call_count == 1
    cutoff = datetime.fromisoformat(prune.call_args.args[0])
    assert 55 <= (datetime.now(timezone.utc) - cutoff).total_seconds() <= 65
    assert orchestrator._maintenance_status["storage_cleanup"][
        "coordination_messages_cleaned"
    ] == 3
    coordination.close()
