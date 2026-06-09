---
id: TASK-472.6
title: Add automated tests for the Granian path
status: Done
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 21:02'
labels: []
dependencies: []
parent_task_id: TASK-472
priority: high
ordinal: 195000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Promote the throwaway e2e harness (boot under --server granian, HTTP route, /api/v1/state, WS initial push, orchestrator->_broadcast->WS client, restart) into tests/. The 36 existing ASGI TestClient tests only cover the uvicorn/no-op path. Mark/skip cleanly if granian is not installed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 tests/ contains a granian e2e test covering HTTP + WS broadcast + restart
- [ ] #2 Test is hermetic (temp backlog project, free port) and CI-runnable
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 15:32
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 15:32
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-09 15:40
---
Agent failed: opencode serve exited with code -15. stderr: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 15:44
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 15:44
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 16:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 142
- Tokens: 233 in / 7.0K out [7.3K total]
- Cost: $0.0000
- Exit: terminated, Duration: 58m 6s
- Log: TASK-472.6__20260609T154418Z.jsonl
---

author: oompah
created: 2026-06-09 18:17
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 18:17
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 18:28
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 78
- Tokens: 120 in / 3.9K out [4.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 46s
- Log: TASK-472.6__20260609T181744Z.jsonl
---

author: oompah
created: 2026-06-09 19:36
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 19:36
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 19:40
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 32
- Tokens: 52 in / 1.6K out [1.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 30s
- Log: TASK-472.6__20260609T193652Z.jsonl
---

author: oompah
created: 2026-06-09 19:40
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 19:41
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 20:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 141
- Tokens: 247 in / 7.9K out [8.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 23m 34s
- Log: TASK-472.6__20260609T194111Z.jsonl
---

author: oompah
created: 2026-06-09 20:10
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 20:11
---
UNDERSTANDING: Duplicate investigation complete. This is NOT a duplicate. Existing tests cover: test_granian_parity.py (TASK-472.5: multipart/static/Jinja over Granian subprocess), test_granian_guard.py (TASK-472.7: workers constraint), test_ws_lifecycle.py (TASK-472.4: WS broadcast/throttle via TestClient). TASK-472.6 specifically needs: e2e test that boots Granian as a real subprocess, tests /api/v1/state HTTP route, tests WS initial push over real Granian WS, tests orchestrator->_broadcast->WS client path, and tests restart. None of the existing files cover this combination. Proceeding with implementation.
---

author: oompah
created: 2026-06-09 20:18
---
DISCOVERY: Confirmed this is NOT a duplicate. Existing tests: test_granian_parity.py covers multipart/static/Jinja HTTP routes (TASK-472.5); test_granian_guard.py covers workers>1 guard (TASK-472.7); test_ws_lifecycle.py covers WS broadcast/throttle via TestClient (TASK-472.4). None cover the e2e Granian path: boot with wired orchestrator, /api/v1/state returning 200, WS initial push, orchestrator->broadcast->WS client, and restart. Empirically verified: Granian workers=1 runs the ASGI app in the same process space, so set_orchestrator() before .serve() works. Will implement tests/test_granian_e2e.py.
---

author: oompah
created: 2026-06-09 20:21
---
IMPLEMENTATION: Created tests/test_granian_e2e.py with 20 tests covering all 5 scenarios from the task description: (1) HTTP routes - 7 tests covering GET /, /api/v1/state (200 with stub orchestrator, JSON format, running field, api_metrics); (2) WS initial push - 7 tests verifying state+issues messages delivered under real Granian; (3) orchestrator->_broadcast->WS client - 3 tests proving fan-out works (Client A refresh triggers broadcast to Client B); (4) restart - 3 tests (HTTP contract preserved, WS works after restart). Key design: subprocess script calls set_orchestrator(stub) before Granian.serve(); Granian workers=1 ASGI mode keeps app in same process so orchestrator is accessible. Skips cleanly if granian not installed (pytest.importorskip). websockets.sync.client used for sync WS tests.
---
<!-- COMMENTS:END -->
