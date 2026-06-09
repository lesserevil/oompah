---
id: TASK-495
title: Manual dispatch endpoint fails inside running event loop
status: Merged
assignee: []
created_date: '2026-06-09 19:42'
updated_date: '2026-06-09 23:00'
labels:
  - bug
dependencies: []
priority: high
ordinal: 211000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During operator intervention on 2026-06-09, POST /api/v1/orchestrator/dispatch/TASK-472.6 returned {"error": "asyncio.run() cannot be called from a running event loop"}. The log also emitted RuntimeWarning: coroutine Orchestrator._fetch_all_candidates.<locals>._fetch_all_projects was never awaited at oompah/server.py:2896. Manual dispatch should work from the live FastAPI process without nesting asyncio.run(), and should either dispatch the requested issue or return a normal validation error without leaking an unawaited coroutine.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 22:20
---
Understanding: The api_orchestrator_dispatch handler at oompah/server.py:3069 calls orch._fetch_all_candidates() synchronously. That method internally uses asyncio.run(_fetch_all_projects()) to drive async work. When called from within FastAPI's already-running event loop, asyncio.run() raises 'cannot be called from a running event loop'. The tick loop avoids this by running _fetch_all_candidates() via loop.run_in_executor() in a separate thread. Fix: use asyncio.to_thread(orch._fetch_all_candidates) in the dispatch endpoint to run it off the event loop, consistent with the existing pattern in test_server_blocking_off_loop.py and the tick loop. Will also add a regression test. No duplicate found - this is a unique bug in the manual dispatch endpoint specifically.
---

author: oompah
created: 2026-06-09 22:26
---
Discovery: Root cause confirmed. In oompah/server.py:3069 (api_orchestrator_dispatch), orch._fetch_all_candidates() was called synchronously from an async route handler. _fetch_all_candidates() uses asyncio.run(_fetch_all_projects()) internally to drive async per-project fetches. asyncio.run() cannot create a new event loop when one is already running (FastAPI's), hence the error. The RuntimeWarning about an unawaited coroutine was a side-effect: the exception left the async inner function's coroutine without being awaited. The tick loop avoids this by running _fetch_all_candidates via loop.run_in_executor(self._tick_pool, func), which gives it a separate thread with no event loop.
---

author: oompah
created: 2026-06-09 22:27
---
Implementation: In oompah/server.py, changed 'candidates = orch._fetch_all_candidates()' to 'candidates = await asyncio.to_thread(orch._fetch_all_candidates)' in api_orchestrator_dispatch. asyncio.to_thread() offloads the call to a ThreadPoolExecutor worker thread, which has no running event loop, so asyncio.run() inside _fetch_all_candidates() works correctly. Added tests/test_dispatch_event_loop.py with 4 tests: (1) dispatch found issue succeeds without event-loop error, (2) unknown issue returns 404 without event-loop error, (3) real errors are not swallowed by event-loop errors, (4) _fetch_all_candidates is called from a worker thread not the event-loop thread. Each test uses a mock _fetch_all_candidates that calls asyncio.run() internally, so reverting the fix would immediately make the tests fail with the original error.
---

author: oompah
created: 2026-06-09 22:29
---
Verification: All 4 new regression tests pass. All 56 pre-existing tests in test_ipc.py and test_server_blocking_off_loop.py also pass (60 total). The regression tests use a mock _fetch_all_candidates that calls asyncio.run() internally — reverting the fix causes them to fail with the original error.
---

author: oompah
created: 2026-06-09 23:00
---
PR #259 merged into main at 2026-06-09T22:58:57Z.
---
<!-- COMMENTS:END -->
