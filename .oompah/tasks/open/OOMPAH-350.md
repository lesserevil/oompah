---
id: OOMPAH-350
type: bug
status: Open
priority: 1
title: Isolate scheduler execution from the HTTP event loop
parent: OOMPAH-348
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T00:56:36.177730Z'
updated_at: '2026-07-22T01:00:25.608274Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Problem: the default Uvicorn startup path schedules orchestrator.run and server.serve on one asyncio event loop. Any remaining synchronous scheduler or lifecycle path can stop all HTTP responses even though the port remains open.

Implement: make the default server path run the orchestrator on a dedicated thread/event loop, matching the isolation model used by the Granian lifespan. Keep one authoritative orchestrator instance, thread-safe refresh/event delivery, cached state broadcasts, webhook forwarding, workflow reload, graceful restart, and existing single-process semantics.

Tests: integration test blocks a scheduler operation and proves GET /api/v1/state remains responsive; test refresh requests cross the thread boundary; test startup/shutdown wiring does not duplicate the orchestrator.

Acceptance: a blocked scheduler tick cannot prevent state and health API responses; Uvicorn remains the supported default; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

