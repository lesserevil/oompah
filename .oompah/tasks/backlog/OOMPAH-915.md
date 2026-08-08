---
id: OOMPAH-915
type: task
status: Backlog
priority: null
title: Eliminate cross-thread project-lock deadlock in API status transitions
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T14:27:22.190077Z'
updated_at: '2026-08-08T14:37:29.944803Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

The live OOMPAH-912 Backlog to Open PATCH reached durable transition APPLYING and then froze the entire server. api_update_issue holds project_store.project_write_lock on the ASGI thread, calls synchronous _apply_task_status_transition, and Orchestrator._transition_issue_status detects the running event loop and waits on a helper thread. ProvenanceGuardedTracker.update_issue on that helper tries to acquire the same thread-owned RLock, producing a deterministic deadlock; health checks, task reads, graceful restart, and stop all then time out. OOMPAH-910 fixed the analogous owner-revision path but not ordinary API status transitions.\n\nImplementation scope:\n- Remove the outer project lock from across durable status-transition execution; the provenance tracker/transition writer must acquire write authority on the execution thread that performs the mutation.\n- Prefer the async transition service at the async API boundary so the event loop is not blocked on a helper-thread future.\n- Split mixed status/metadata updates into bounded lock phases with current-authority revalidation and preserve atomic/fail-closed behavior.\n- Audit sibling API transition paths for the same outer-lock plus helper-thread topology.\n\nRequired tests:\n- Exercise async Backlog to Open with a real threading.RLock and provenance-guarded tracker under a bounded timeout; prove one committed transition, no lingering claim, and a responsive concurrent health/event-loop probe.\n- Cover combined status and metadata updates, owner promotion, transition rejection, and concurrent writers.\n- Retain OOMPAH-910 owner-revision regressions.\n\nAcceptance criteria:\n- API lifecycle updates cannot deadlock the server through cross-thread recursive project locking.\n- The event loop remains responsive during tracker I/O.\n- Focused server, orchestrator transition, and provenance locking tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 14:37
---
Direct owner implementation completed locally on the systemic composition branch. Async API status transitions no longer hold a request-thread project RLock across worker-thread tracker I/O; mixed metadata writes use a bounded writer-thread lock and revalidation. Focused runtime/status/server suites pass. Status remains Backlog until the expired-transition recovery fix is deployed.
---
<!-- COMMENTS:END -->
