---
id: OOMPAH-518
type: task
status: Backlog
priority: null
title: Keep graceful restart cleanup on the owning event loop
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T17:06:49.891505Z'
updated_at: '2026-07-28T17:06:49.891505Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: Fix the graceful restart shutdown path introduced under OOMPAH-507. A live auto-update on 2026-07-28 shut Uvicorn down, then Orchestrator.stop called _drain_background_work from the outer asyncio.run loop and raised RuntimeError because maintenance futures belonged to Uvicorn's closed loop. The service exited instead of reaching os.execv. Refactor shutdown so background tasks are drained or cancelled on their owning loop before it closes, or make stop safely handle already-closed foreign-loop tasks without awaiting them. Preserve agent drain semantics and ensure normal restart reaches exec even when maintenance work exists. Tests: add a regression reproducing tasks associated with a different or closed event loop, cover same-loop draining, and exercise server restart control flow through the existing Makefile and restart tests. Run focused restart and event-loop tests and the full branch gate. Acceptance criteria: no cross-loop Future exception; a normal auto-update or restart exits the server, completes cleanup, exec-restarts, and binds port 8090 with a new instance ID; active agents are still drained rather than killed; failures remain observable without preventing restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

