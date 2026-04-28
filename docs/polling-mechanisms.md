# Polling Mechanisms Inventory

This document identifies all places in the codebase where polling is currently
used. It was created as part of issue **oompah-8r5**, a subtask of the
event-driven architecture epic **oompah-ky3** ("All actions must be event
driven").

The two former high-priority polls (the orchestrator main loop and the log
file watcher) have since been converted to event-driven mechanisms. They are
listed here for historical context and to document the safety-net poll that
remains.

---

## 1. Orchestrator main loop (event-driven dispatch + safety-net full sync)

**File:** `oompah/orchestrator.py`
**Methods:** `Orchestrator.run()` (line 431) and `Orchestrator._full_sync_loop()` (line 417)

```python
# run() — blocks on the dispatch queue, no time-based polling
while not self._stopping:
    event = await self._dispatch_queue.get()
    ...
    await _run_tick()
```

```python
# _full_sync_loop() — safety-net periodic FULL_SYNC event
while not self._stopping:
    interval_s = self.config.full_sync_interval_ms / 1000.0
    await asyncio.sleep(interval_s)
    if not self._stopping:
        self._post_event(DispatchEvent(event_type=DispatchEventType.FULL_SYNC))
```

**Interval:** Safety-net full sync runs every `full_sync_interval_ms`
(default 30 000 ms / 30 s). The primary dispatch loop has no interval — it
blocks on the queue.

**What it does:** The orchestrator's main `run()` loop is event-driven. It
blocks on an internal `_dispatch_queue` and runs a `_tick()` (world scan +
dispatch) whenever an event is posted. Events are posted by:

- `_on_worker_exit()` — a worker finishes or fails
- `request_refresh()` — API/user-triggered refresh
- `unpause()` — dispatch resumes after a pause
- `_on_retry_timer()` — a retry timer fires
- `_full_sync_loop()` — periodic safety-net full sync

The legacy `poll_interval_ms` setting is retained in config for compatibility
but is no longer the primary scheduling mechanism. Consistency is guaranteed
by the safety-net `full_sync_interval_ms` sleep in `_full_sync_loop`.

---

## 2. Graceful-restart drain loop

**File:** `oompah/orchestrator.py`, lines 244–262
**Method:** `Orchestrator.graceful_restart()`

```python
deadline = time.monotonic() + drain_timeout_s
while self.state.running and time.monotonic() < deadline:
    ...
    await asyncio.sleep(2)
```

**Interval:** 2 seconds (hard-coded).
**What it does:** After a restart is requested, polls every 2 seconds to check
whether all running agents have finished, up to `drain_timeout_s` (default
60 s).

---

## 3. LogFileWatcher (event-driven via `watchfiles.awatch`)

**File:** `oompah/error_watcher.py`, lines 333–388
**Method:** `LogFileWatcher._watch_loop()`

```python
async for _changes in awatch(watch_target, stop_event=self._stop_event, ...):
    self._poll_file()
    ...
```

**Interval:** None — driven by OS filesystem notifications via the
`watchfiles` library. The outer `while not self._stop_event.is_set()` loop
only re-enters `awatch` when the watch target needs to change (e.g. parent
directory → file once the file is created, or after log rotation). On
unexpected errors, a 1-second backoff (`asyncio.wait_for(stop_event.wait(),
timeout=1.0)`) prevents tight retry loops.

**What it does:** Watches a log file (or its parent directory if the file
does not yet exist) and calls `_poll_file()` to read newly appended lines
whenever the filesystem reports a change. New lines are dispatched as error
events to registered callbacks.

---

## 4. `_drain_stderr` read loop (agent process)

**File:** `oompah/agent.py`, lines 106–115
**Method:** `AgentSession._drain_stderr()`

```python
while True:
    line = await self._process.stderr.readline()
    if not line:
        break
    ...
```

**Interval:** N/A — blocks on `readline()` (effectively event-driven via the
OS pipe), but structured as an infinite loop. Not a time-based poll; exits
naturally when the subprocess closes stderr.

---

## 5. `stream_turn` read loop (agent process stdout)

**File:** `oompah/agent.py`, lines 262–286
**Method:** `AgentSession.stream_turn()`

```python
while True:
    remaining = deadline - time.monotonic()
    ...
    line = await asyncio.wait_for(
        self._process.stdout.readline(), timeout=remaining
    )
    ...
```

**Interval:** N/A — blocks on `readline()` with a deadline timeout. Not a
periodic time poll; exits when the subprocess writes a completion line or the
turn timeout is exceeded.

---

## 6. CLI main restart loop

**File:** `oompah/__main__.py`, line 66
**Method:** `main()` (CLI entry point)

```python
while True:
    restart = False
    try:
        restart = asyncio.run(_run(workflow_path, args.port))
    ...
    if restart:
        os.execv(sys.executable, ...)
    break
```

**Interval:** N/A — not a time-based poll. The loop only iterates when a
graceful restart is requested, at which point `os.execv` replaces the process
immediately. In practice it is a one-shot wrapper, not ongoing polling.

---

## Configuration

| Setting | File | Default | Description |
|---------|------|---------|-------------|
| `poll_interval_ms` | `oompah/config.py:231` | `30000` | Legacy orchestrator interval; retained for compatibility but no longer the primary scheduling mechanism |
| `full_sync_interval_ms` | `oompah/config.py:232` | `30000` | Interval for the orchestrator safety-net `_full_sync_loop` |
| `polling.interval_ms` (YAML / `OOMPAH_POLL_INTERVAL_MS`) | `oompah/config.py:348` | — | Override for `poll_interval_ms` |
| `polling.full_sync_interval_ms` (YAML / `OOMPAH_FULL_SYNC_INTERVAL_MS`) | `oompah/config.py:349` | — | Override for `full_sync_interval_ms` |

`LogFileWatcher` no longer takes a `poll_interval` parameter — it is fully
event-driven via `watchfiles.awatch()`.

---

## Summary

| # | Location | Mechanism | Interval | Notes |
|---|----------|-----------|----------|-------|
| 1 | `orchestrator.py` `run()` + `_full_sync_loop()` | Event-driven dispatch queue + periodic safety-net FULL_SYNC event | Queue: none; safety-net: `full_sync_interval_ms` (default 30 s) | Replaced the former timed poll as part of oompah-ky3 |
| 2 | `orchestrator.py` `graceful_restart()` | `asyncio.sleep` loop | 2 s | Only runs during restart drain |
| 3 | `error_watcher.py` `LogFileWatcher._watch_loop()` | `watchfiles.awatch()` (OS filesystem notifications) | Event-driven | Replaced the former 2 s sleep loop as part of oompah-ky3 |
| 4 | `agent.py` `_drain_stderr()` | `readline()` loop | Event-driven | Already pipe-driven |
| 5 | `agent.py` `stream_turn()` | `readline()` + deadline | Event-driven | Already pipe-driven |
| 6 | `__main__.py` `main()` | One-shot restart loop | One-shot | Not ongoing polling |

The two original high-priority replacement candidates from oompah-ky3 (items
**1** and **3**) have been converted to event-driven mechanisms. The
remaining `asyncio.sleep` use sites (item **2** drain loop, the safety-net
sleep inside item **1**) are intentional and low-impact.
