"""Tests for ``oompah.console_store``.

Covers the acceptance criteria from oompah-zlz_2-pd2z:

* append round-trip and ordering
* ``since_ts`` filtering (strictly greater than)
* ``limit`` returns the most recent N
* malformed lines are skipped with a warning
* meta round-trip and missing-file fallback
* ``clear`` is idempotent
* concurrent appends from 5 threads stay ordered (no torn lines)
"""

from __future__ import annotations

import json
import logging
import os
import threading

import pytest

from oompah.console_store import ConsoleStore, DEFAULT_CONSOLE_ROOT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(tmp_path) -> ConsoleStore:
    return ConsoleStore(root=str(tmp_path / "console"))


# ---------------------------------------------------------------------------
# append + read_all basics
# ---------------------------------------------------------------------------


class TestAppend:
    def test_append_creates_file_and_dir(self, tmp_path):
        root = tmp_path / "console-root"
        # Parent dir does not exist yet.
        assert not root.exists()
        store = ConsoleStore(root=str(root))
        store.append("proj-1", {"ts": "2026-05-13T19:00:00Z", "kind": "hello"})
        # Both the root dir and the JSONL file should exist now.
        jsonl = root / "proj-1.jsonl"
        assert root.is_dir()
        assert jsonl.is_file()
        content = jsonl.read_text(encoding="utf-8")
        assert content.endswith("\n")
        assert content.count("\n") == 1

    def test_append_writes_one_object_per_line(self, tmp_path):
        store = _store(tmp_path)
        events = [{"ts": f"2026-05-13T19:0{i}:00Z", "i": i} for i in range(5)]
        for ev in events:
            store.append("p", ev)
        jsonl = tmp_path / "console" / "p.jsonl"
        lines = jsonl.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 5
        decoded = [json.loads(line) for line in lines]
        assert decoded == events

    def test_append_1000_produces_1000_lines(self, tmp_path):
        """Acceptance criterion: 1000 appends → 1000 lines in one file."""
        store = _store(tmp_path)
        for i in range(1000):
            store.append("big", {"ts": f"2026-05-13T19:42:00.{i:04d}Z", "i": i})
        jsonl = tmp_path / "console" / "big.jsonl"
        lines = jsonl.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1000
        # Each line must round-trip as JSON.
        for idx, line in enumerate(lines):
            obj = json.loads(line)
            assert obj["i"] == idx

    def test_append_separate_projects_dont_collide(self, tmp_path):
        store = _store(tmp_path)
        store.append("a", {"ts": "2026-05-13T01:00:00Z", "v": "a1"})
        store.append("b", {"ts": "2026-05-13T01:00:00Z", "v": "b1"})
        store.append("a", {"ts": "2026-05-13T01:00:01Z", "v": "a2"})
        a_events = store.read_all("a")
        b_events = store.read_all("b")
        assert [e["v"] for e in a_events] == ["a1", "a2"]
        assert [e["v"] for e in b_events] == ["b1"]


class TestReadAll:
    def test_append_then_read_all_round_trip(self, tmp_path):
        store = _store(tmp_path)
        events = [
            {"ts": "2026-05-13T19:00:00Z", "kind": "a"},
            {"ts": "2026-05-13T19:00:01Z", "kind": "b"},
            {"ts": "2026-05-13T19:00:02Z", "kind": "c"},
        ]
        for ev in events:
            store.append("p", ev)
        got = store.read_all("p")
        assert got == events

    def test_read_all_returns_empty_for_missing_project(self, tmp_path):
        store = _store(tmp_path)
        assert store.read_all("nope") == []

    def test_read_all_since_ts(self, tmp_path):
        store = _store(tmp_path)
        events = [
            {"ts": "2026-05-13T19:42:00Z", "i": 0},
            {"ts": "2026-05-13T19:42:01Z", "i": 1},  # boundary
            {"ts": "2026-05-13T19:42:02Z", "i": 2},
            {"ts": "2026-05-13T19:42:03Z", "i": 3},
        ]
        for ev in events:
            store.append("p", ev)
        got = store.read_all("p", since_ts="2026-05-13T19:42:01Z")
        # Strictly greater than → boundary value excluded.
        assert [e["i"] for e in got] == [2, 3]

    def test_read_all_since_ts_drops_missing_ts(self, tmp_path):
        store = _store(tmp_path)
        store.append("p", {"ts": "2026-05-13T19:42:00Z", "i": 0})
        store.append("p", {"kind": "no-ts", "i": 1})  # no ts field
        store.append("p", {"ts": "2026-05-13T19:42:05Z", "i": 2})
        got = store.read_all("p", since_ts="2026-05-13T19:42:01Z")
        assert [e["i"] for e in got] == [2]

    def test_read_all_limit_returns_most_recent(self, tmp_path):
        store = _store(tmp_path)
        for i in range(200):
            store.append("p", {"ts": f"2026-05-13T20:00:{i:02d}Z", "i": i})
        got = store.read_all("p", limit=50)
        assert len(got) == 50
        # last 50 of 0..199 == 150..199
        assert [e["i"] for e in got] == list(range(150, 200))

    def test_read_all_limit_larger_than_total_returns_all(self, tmp_path):
        store = _store(tmp_path)
        for i in range(3):
            store.append("p", {"ts": f"t{i}", "i": i})
        got = store.read_all("p", limit=99)
        assert [e["i"] for e in got] == [0, 1, 2]

    def test_read_all_limit_zero_returns_empty(self, tmp_path):
        store = _store(tmp_path)
        store.append("p", {"ts": "t", "i": 0})
        assert store.read_all("p", limit=0) == []

    def test_read_all_since_and_limit_compose(self, tmp_path):
        store = _store(tmp_path)
        for i in range(10):
            store.append("p", {"ts": f"2026-05-13T20:00:{i:02d}Z", "i": i})
        got = store.read_all(
            "p", since_ts="2026-05-13T20:00:02Z", limit=3,
        )
        # since: i in 3..9 (7 events) → limit 3 keeps last 3 → 7,8,9
        assert [e["i"] for e in got] == [7, 8, 9]

    def test_read_all_skips_malformed_lines(self, tmp_path, caplog):
        store = _store(tmp_path)
        store.append("p", {"ts": "t1", "i": 0})
        store.append("p", {"ts": "t2", "i": 1})
        # Inject a malformed line and a non-object line into the JSONL.
        jsonl = tmp_path / "console" / "p.jsonl"
        with open(jsonl, "a", encoding="utf-8") as fh:
            fh.write("this is not json\n")
            fh.write("[\"array\", \"not\", \"object\"]\n")
            fh.write("\n")  # blank line is tolerated silently
        store.append("p", {"ts": "t3", "i": 2})

        with caplog.at_level(logging.WARNING, logger="oompah.console_store"):
            got = store.read_all("p")
        # The two valid events plus the new one survive.
        assert [e["i"] for e in got] == [0, 1, 2]
        # We expect a warning for the bad JSON and one for the array line.
        warns = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warns) == 2
        assert any("malformed" in r.getMessage().lower() for r in warns)
        assert any("non-object" in r.getMessage().lower() for r in warns)


# ---------------------------------------------------------------------------
# meta sidecar
# ---------------------------------------------------------------------------


class TestMeta:
    def test_meta_missing_returns_empty_dict(self, tmp_path):
        store = _store(tmp_path)
        assert store.load_meta("p") == {}

    def test_meta_round_trip(self, tmp_path):
        store = _store(tmp_path)
        meta = {
            "session_id": "sess-abc",
            "started_at": "2026-05-13T20:00:00Z",
            "model": "claude-sonnet",
            "tags": ["console", "v1"],
            "counts": {"events": 42},
        }
        store.save_meta("p", meta)
        got = store.load_meta("p")
        assert got == meta

    def test_meta_save_is_atomic(self, tmp_path):
        """save_meta must use temp-file + rename — no leftover ``.tmp``."""
        store = _store(tmp_path)
        store.save_meta("p", {"a": 1})
        files = sorted(p.name for p in (tmp_path / "console").iterdir())
        # Only the canonical meta file should be present.
        assert files == ["p.meta.json"]

    def test_meta_load_handles_malformed_file(self, tmp_path, caplog):
        store = _store(tmp_path)
        meta_path = tmp_path / "console" / "p.meta.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text("{this is not json", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="oompah.console_store"):
            got = store.load_meta("p")
        assert got == {}
        assert any("malformed" in r.getMessage().lower() for r in caplog.records)

    def test_meta_load_handles_non_object_top_level(self, tmp_path, caplog):
        store = _store(tmp_path)
        meta_path = tmp_path / "console" / "p.meta.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text("[1, 2, 3]", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="oompah.console_store"):
            got = store.load_meta("p")
        assert got == {}

    def test_meta_overwrite_replaces_prior(self, tmp_path):
        store = _store(tmp_path)
        store.save_meta("p", {"v": 1})
        store.save_meta("p", {"v": 2})
        assert store.load_meta("p") == {"v": 2}


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_removes_both_files(self, tmp_path):
        store = _store(tmp_path)
        store.append("p", {"ts": "t", "i": 0})
        store.save_meta("p", {"foo": "bar"})
        jsonl = tmp_path / "console" / "p.jsonl"
        meta = tmp_path / "console" / "p.meta.json"
        assert jsonl.exists() and meta.exists()
        store.clear("p")
        assert not jsonl.exists()
        assert not meta.exists()

    def test_clear_idempotent(self, tmp_path):
        store = _store(tmp_path)
        # First call against nothing: must not raise.
        store.clear("never-existed")
        # Same store, second time: still no raise.
        store.clear("never-existed")

    def test_clear_after_partial_state(self, tmp_path):
        store = _store(tmp_path)
        # Only JSONL exists.
        store.append("p", {"ts": "t", "i": 0})
        store.clear("p")
        assert not (tmp_path / "console" / "p.jsonl").exists()
        # Only meta exists.
        store.save_meta("q", {"v": 1})
        store.clear("q")
        assert not (tmp_path / "console" / "q.meta.json").exists()

    def test_clear_does_not_affect_other_projects(self, tmp_path):
        store = _store(tmp_path)
        store.append("keep", {"ts": "t", "i": 0})
        store.save_meta("keep", {"v": 1})
        store.append("drop", {"ts": "t", "i": 0})
        store.clear("drop")
        assert store.read_all("keep") == [{"ts": "t", "i": 0}]
        assert store.load_meta("keep") == {"v": 1}
        assert store.read_all("drop") == []


# ---------------------------------------------------------------------------
# concurrency
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_concurrent_append_safe(self, tmp_path):
        """5 threads x 100 events → 500 ordered, parseable lines.

        Order across threads is not deterministic (we don't promise it
        will be), but each event must appear exactly once and every
        line must parse cleanly — no torn writes.
        """
        store = _store(tmp_path)
        threads_count = 5
        per_thread = 100
        start_barrier = threading.Barrier(threads_count)

        def worker(tid: int) -> None:
            start_barrier.wait()
            for i in range(per_thread):
                store.append("hot", {
                    "ts": f"2026-05-13T21:00:{tid:02d}.{i:04d}Z",
                    "tid": tid,
                    "i": i,
                })

        threads = [
            threading.Thread(target=worker, args=(t,))
            for t in range(threads_count)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        got = store.read_all("hot")
        assert len(got) == threads_count * per_thread

        # Every (tid, i) pair must appear exactly once.
        expected = {(tid, i) for tid in range(threads_count) for i in range(per_thread)}
        actual = {(e["tid"], e["i"]) for e in got}
        assert actual == expected

        # Per-thread sub-sequences must remain in order — within a
        # single thread, append calls are sequential, and the lock
        # guarantees that thread's lines stay relatively ordered with
        # respect to one another.
        for tid in range(threads_count):
            ordered_i = [e["i"] for e in got if e["tid"] == tid]
            assert ordered_i == list(range(per_thread)), (
                f"thread {tid} sub-sequence out of order: {ordered_i[:10]}..."
            )

    def test_concurrent_append_no_torn_lines(self, tmp_path):
        """Every line in the raw file must parse — no partial writes."""
        store = _store(tmp_path)
        # Use a large payload to make a torn write more likely if locking
        # were broken (the OS-level O_APPEND atomicity bound is PIPE_BUF).
        big = "x" * 8192

        def worker() -> None:
            for i in range(50):
                store.append("torn", {"ts": f"t{i}", "blob": big})

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        jsonl = tmp_path / "console" / "torn.jsonl"
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            obj = json.loads(line)  # would raise if torn
            assert obj["blob"] == big


# ---------------------------------------------------------------------------
# misc
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_root_constant(self):
        assert DEFAULT_CONSOLE_ROOT == ".oompah/console"

    def test_default_constructor_uses_default_root(self):
        # Just sanity — we don't actually write anywhere.
        store = ConsoleStore()
        assert store._root == DEFAULT_CONSOLE_ROOT  # noqa: SLF001
