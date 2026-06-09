---
id: TASK-495
title: Manual dispatch endpoint fails inside running event loop
status: Backlog
assignee: []
created_date: '2026-06-09 19:42'
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
