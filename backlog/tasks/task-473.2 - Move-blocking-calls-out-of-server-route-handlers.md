---
id: TASK-473.2
title: Move blocking calls out of server route handlers
status: Open
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 15:56'
labels:
  - performance
dependencies: []
parent_task_id: TASK-473
priority: high
ordinal: 200000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Audit the ~11 subprocess/run_in_executor/sync-I/O sites in oompah/server.py route handlers and ensure blocking work runs off the event loop (threadpool/async), so it cannot stall the shared loop the orchestrator and WebSocket broadcasts depend on.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No synchronous blocking call runs inline on the event loop in hot route handlers
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 14:33
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 14:33
---
Focus: Queue Api Oompah Specialist
---

author: oompah
created: 2026-06-09 14:46
---
Agent stalled 1 time(s) (760s (462057 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 14:46
---
Run #1 [attempt=1, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 11
- Tokens: 461.1K in / 948 out [462.1K total]
- Cost: $0.0000
- Exit: stalled, Duration: 12m 40s
- Log: TASK-473.2__20260609T143409Z.jsonl
---

author: oompah
created: 2026-06-09 15:45
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 15:51
---
Understanding: TASK-473.2 is NOT a duplicate. Searched for similar tasks using 'blocking event loop', 'blocking calls server route handlers', 'run_in_executor subprocess', and 'threadpool async server blocking'. The closest candidates were TASK-467.3 (state snapshot cache + security fixes in server.py — Done) and TASK-469.5 (API responsiveness via cached read models and execution pools — Done), but neither addressed the ~11 specific blocking call sites in server.py route handlers. TASK-473.3 (sibling, In Progress) covers only the favicon read_bytes() case. This task represents legitimate new work. Proceeding with implementation: audit and fix remaining blocking I/O in route handlers (foci management open() calls, attachment serving, template load, asyncio.get_event_loop() deprecation).
---
<!-- COMMENTS:END -->
