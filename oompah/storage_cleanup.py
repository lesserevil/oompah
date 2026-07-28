"""Safe cleanup of Oompah-owned temporary files and agent logs."""

from __future__ import annotations

import os
import shutil
import stat
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

_VM_IMAGE_SUFFIXES = {".img", ".iso", ".qcow", ".qcow2", ".vdi", ".vhd", ".vmdk"}


@dataclass
class StoragePressure:
    pressured: bool
    free_bytes: int
    free_percent: float
    checked_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class StorageCleanupResult:
    cleaned_count: int = 0
    reclaimed_bytes: int = 0
    scanned_count: int = 0
    skipped_count: int = 0
    deferred: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def inspect_storage_pressure(
    paths: list[str | Path],
    *,
    min_free_bytes: int,
    min_free_percent: float,
) -> StoragePressure:
    """Inspect each distinct filesystem and report the most constrained one."""
    samples: list[tuple[int, float, str]] = []
    errors: list[str] = []
    seen_devices: set[int] = set()
    for raw in paths:
        path = Path(raw).expanduser()
        probe = path
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        try:
            device = probe.stat().st_dev
            if device in seen_devices:
                continue
            seen_devices.add(device)
            usage = shutil.disk_usage(probe)
            percent = (usage.free / usage.total * 100.0) if usage.total else 0.0
            samples.append((usage.free, percent, str(probe)))
        except OSError as exc:
            errors.append(f"{probe}: {exc}")
    if not samples:
        return StoragePressure(False, 0, 0.0, errors=errors)
    free_bytes = min(sample[0] for sample in samples)
    free_percent = min(sample[1] for sample in samples)
    pressured = any(
        (min_free_bytes > 0 and sample_free < min_free_bytes)
        or (min_free_percent > 0 and sample_percent < min_free_percent)
        for sample_free, sample_percent, _ in samples
    )
    return StoragePressure(
        pressured=pressured,
        free_bytes=free_bytes,
        free_percent=round(free_percent, 3),
        checked_paths=[sample[2] for sample in samples],
        errors=errors,
    )


def _entry_size(path: Path) -> int:
    """Return allocated-entry sizes without following symlinks."""
    try:
        info = path.lstat()
    except OSError:
        return 0
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        return int(info.st_size)
    total = int(info.st_size)
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                child = path / entry.name
                if entry.is_symlink():
                    try:
                        total += child.lstat().st_size
                    except OSError:
                        pass
                elif entry.is_dir(follow_symlinks=False):
                    total += _entry_size(child)
                else:
                    try:
                        total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
    except OSError:
        pass
    return total


def _remove_owned_entry(path: Path) -> int:
    """Atomically quarantine and remove one direct child of an owned root."""
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise ValueError("symlink entries are preserved")
    size = _entry_size(path)
    quarantine = path.with_name(f".oompah-cleanup-{uuid.uuid4().hex}")
    os.replace(path, quarantine)
    try:
        if quarantine.is_dir() and not quarantine.is_symlink():
            shutil.rmtree(quarantine)
        else:
            quarantine.unlink()
    except Exception:
        # Leave the quarantined entry inside the same owned root. A later scan
        # can retry it; never move partial cleanup outside the ownership boundary.
        raise
    return size


def cleanup_owned_storage(
    *,
    temp_root: str | Path,
    agent_log_root: str | Path,
    protected_paths: set[str] | None = None,
    min_age_seconds: int,
    log_retention_seconds: int,
    batch_limit: int,
    byte_limit: int,
    now: float | None = None,
) -> StorageCleanupResult:
    """Remove stale direct children from narrowly defined Oompah-owned roots.

    Every temp-root child is Oompah-owned by contract. Only ``*.jsonl`` files
    are considered in the agent-log root. Symlinks and VM images are preserved,
    and active paths supplied by the orchestrator are excluded.
    """
    result = StorageCleanupResult()
    if batch_limit <= 0 or byte_limit <= 0:
        result.deferred = True
        return result

    current_time = time.time() if now is None else now
    protected = {
        str(Path(path).expanduser().absolute()) for path in (protected_paths or set())
    }
    candidates: list[tuple[float, Path]] = []
    roots = (
        (Path(temp_root).expanduser(), max(min_age_seconds, 1), "temp"),
        (
            Path(agent_log_root).expanduser(),
            max(log_retention_seconds, 1),
            "logs",
        ),
    )
    for root, retention, kind in roots:
        try:
            if not root.exists():
                continue
            if root.is_symlink() or not root.is_dir():
                result.errors.append(f"{root}: owned root is not a real directory")
                continue
            for path in root.iterdir():
                result.scanned_count += 1
                try:
                    info = path.lstat()
                    if stat.S_ISLNK(info.st_mode):
                        result.skipped_count += 1
                        continue
                    if str(path.absolute()) in protected:
                        result.skipped_count += 1
                        continue
                    if kind == "logs" and (
                        not stat.S_ISREG(info.st_mode) or path.suffix != ".jsonl"
                    ):
                        result.skipped_count += 1
                        continue
                    if kind == "temp" and path.suffix.lower() in _VM_IMAGE_SUFFIXES:
                        result.skipped_count += 1
                        continue
                    if current_time - info.st_mtime < retention:
                        result.skipped_count += 1
                        continue
                    candidates.append((info.st_mtime, path))
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    result.errors.append(f"{path}: {exc}")
        except OSError as exc:
            result.errors.append(f"{root}: {exc}")

    for _, path in sorted(candidates, key=lambda item: (item[0], str(item[1]))):
        if result.cleaned_count >= batch_limit or result.reclaimed_bytes >= byte_limit:
            result.deferred = True
            break
        try:
            size = _entry_size(path)
            if result.reclaimed_bytes + size > byte_limit:
                result.deferred = True
                result.skipped_count += 1
                continue
            reclaimed = _remove_owned_entry(path)
            result.cleaned_count += 1
            result.reclaimed_bytes += reclaimed
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as exc:
            result.errors.append(f"{path}: {exc}")
    if len(candidates) > result.cleaned_count + len(result.errors):
        result.deferred = True
    return result
