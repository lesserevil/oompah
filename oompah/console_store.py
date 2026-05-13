"""On-disk transcript storage for the operator Console.

This module implements the data layer for the console-session epic (parent
issue ``oompah-zlz_2-ebwe``). It is intentionally narrow: events are
appended one-per-line to ``<root>/<project_id>.jsonl`` and a small sidecar
``<root>/<project_id>.meta.json`` carries free-form metadata for the
project's console session.

Design notes
------------

* **One project, one file.** Each project_id maps to exactly one JSONL
  transcript and (optionally) one meta sidecar.

* **Thread safety, not process safety.** Only one orchestrator process
  touches these files (per the issue's "Out of scope" section). Within
  a process, multiple worker threads may append concurrently — we
  serialize per (store, project_id) with a ``threading.Lock`` so that
  appended lines never interleave.

* **Atomic per-line append.** Each ``append`` call opens the file in
  ``"a"`` mode, writes ``json.dumps(event) + "\\n"``, and closes. POSIX
  guarantees that ``write(2)`` on a file opened with ``O_APPEND`` is
  atomic for buffers smaller than ``PIPE_BUF`` (≥4 KB), but the lock
  is the real correctness barrier here because we don't bound event
  size.

* **Atomic meta write.** ``save_meta`` writes to a temp file under the
  same directory then ``os.replace``s it into place — an atomic POSIX
  rename. Readers either see the old file or the new one, never a
  partially-written one.

* **Malformed lines are skipped.** A transcript can be partially
  corrupted (manual edits, partial writes during a crash, etc.). We
  log a single ``warning`` per bad line and continue. Reading must not
  raise — the console session would otherwise become un-resumable.

* **Out of scope.** SDK integration, replay logic, event normalization,
  rotation/compaction, and cross-process safety are downstream beads.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)


DEFAULT_CONSOLE_ROOT = ".oompah/console"


class ConsoleStore:
    """JSONL-per-project transcript store with a meta sidecar.

    See module docstring for the full design.
    """

    def __init__(self, root: str = DEFAULT_CONSOLE_ROOT) -> None:
        self._root = root
        # One lock per project_id, created on first use. We hand out at
        # most one lock per project across all callers in this process,
        # which is what serializes the append/clear path.
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    # ------------------------------------------------------------------ paths

    def _jsonl_path(self, project_id: str) -> str:
        return os.path.join(self._root, f"{project_id}.jsonl")

    def _meta_path(self, project_id: str) -> str:
        return os.path.join(self._root, f"{project_id}.meta.json")

    def _lock_for(self, project_id: str) -> threading.Lock:
        """Return a stable per-project lock, creating it on demand."""
        with self._locks_guard:
            lock = self._locks.get(project_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[project_id] = lock
            return lock

    # ----------------------------------------------------------------- append

    def append(self, project_id: str, event: dict) -> None:
        """Append one event to ``<root>/<project_id>.jsonl``.

        Creates parent directories on first write. The append is
        serialized per project_id so concurrent calls from multiple
        threads never interleave bytes.
        """
        line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        path = self._jsonl_path(project_id)
        lock = self._lock_for(project_id)
        with lock:
            # Lazy parent-dir creation: cheap and lets first-write Just Work.
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            # Open / write / close on every call — see module docstring
            # for the atomicity story.
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.write("\n")

    # ---------------------------------------------------------------- read_all

    def read_all(
        self,
        project_id: str,
        since_ts: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """Return events in chronological (insertion) order.

        ``since_ts`` filters strictly greater than (ISO-8601 string
        compare). ``limit`` keeps only the most recent N entries
        (applied AFTER ``since_ts``). Malformed lines are skipped with
        a logged warning.
        """
        path = self._jsonl_path(project_id)
        try:
            fh = open(path, "r", encoding="utf-8")
        except FileNotFoundError:
            return []
        events: list[dict] = []
        with fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.rstrip("\n")
                if not raw:
                    # Tolerate (and skip) blank lines without warning —
                    # they're not corruption, just whitespace.
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "ConsoleStore: skipping malformed line %d in %s: %s",
                        lineno, path, exc,
                    )
                    continue
                if not isinstance(event, dict):
                    logger.warning(
                        "ConsoleStore: skipping non-object line %d in %s "
                        "(got %s)",
                        lineno, path, type(event).__name__,
                    )
                    continue
                if since_ts is not None:
                    ts = event.get("ts")
                    if not isinstance(ts, str) or ts <= since_ts:
                        continue
                events.append(event)
        if limit is not None and limit >= 0:
            # NOTE: ``events[-0:]`` returns the *full* list (Python slice
            # quirk), so guard against limit==0 explicitly.
            if limit == 0:
                return []
            if len(events) > limit:
                events = events[-limit:]
        return events

    # ----------------------------------------------------------------- meta IO

    def load_meta(self, project_id: str) -> dict:
        """Read ``<root>/<project_id>.meta.json``.

        Returns ``{}`` when missing. Logs a warning and returns ``{}``
        when the file exists but is malformed — same fail-open posture
        as ``read_all``.
        """
        path = self._meta_path(project_id)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:
            logger.warning(
                "ConsoleStore: meta file %s is malformed, returning empty: %s",
                path, exc,
            )
            return {}
        if not isinstance(data, dict):
            logger.warning(
                "ConsoleStore: meta file %s top-level is not an object "
                "(got %s), returning empty",
                path, type(data).__name__,
            )
            return {}
        return data

    def save_meta(self, project_id: str, meta: dict) -> None:
        """Atomically write the meta sidecar.

        Uses temp-file + ``os.replace`` (POSIX rename) so concurrent
        readers see either the prior content or the new content — never
        a partial write.
        """
        path = self._meta_path(project_id)
        lock = self._lock_for(project_id)
        with lock:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            tmp_path = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
            try:
                with open(tmp_path, "w", encoding="utf-8") as fh:
                    json.dump(meta, fh, ensure_ascii=False, sort_keys=True)
                    fh.write("\n")
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_path, path)
            except Exception:
                # Best-effort cleanup of the temp file. Don't mask the
                # original error.
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

    # ------------------------------------------------------------------ clear

    def clear(self, project_id: str) -> None:
        """Delete both transcript and meta for the project.

        Idempotent: missing files are silently ignored.
        """
        lock = self._lock_for(project_id)
        with lock:
            for path in (self._jsonl_path(project_id), self._meta_path(project_id)):
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    continue


__all__ = ["ConsoleStore", "DEFAULT_CONSOLE_ROOT"]
