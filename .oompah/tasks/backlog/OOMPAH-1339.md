---
id: OOMPAH-1339
type: bug
status: Backlog
priority: null
title: WorkflowJobStore reopens SQLite without reopening authority lock fd after orchestrator
  replacement
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-25T17:06:31.999323Z'
updated_at: '2026-08-25T17:06:31.999323Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 6bfbe7cd-9636-4871-b6e9-62d93de0b66a
  request_fingerprint: f24e943b5e6131e0adbc23102abf8f7da3216631cfbddeeecf46021130d96f4d
---
## Summary

### Problem
Task submission can persistently fail with HTTP 400 `file descriptor cannot be a negative integer (-1)`. Reproduced while resubmitting TRICKLE-122 after a service/orchestrator lifecycle transition.

### Root cause
`WorkflowJobStore.close()` closes SQLite and sets `_authority_lock_fd = -1`. `_ensure_conn()` explicitly reopens a closed SQLite connection for stale API threads after orchestrator replacement, but `_authority_mutation_guard()` calls `fcntl.flock(self._authority_lock_fd, ...)` before any connection recovery and never reopens the retired lock descriptor. Any stale reference performing a mutation therefore raises ValueError instead of recovering as intended. The existing `_ensure_conn()` docstring explicitly claims to support API-thread races across orchestrator replacement, so connection and authority-lock recovery must be atomic together.

### Scope
- oompah/workflow_jobs.py: centralize safe authority-lock opening; under the existing store RLock, reopen the lock fd when it is negative before flock; preserve O_CLOEXEC/O_NOFOLLOW and 0600 mode.
- Ensure close remains idempotent and never closes a reused unrelated descriptor.
- Ensure a stale store reference after close can recover both SQLite and authority lock consistently, or fail with a typed WorkflowJobStoreError if recovery is intentionally unsupported.

### Tests
- Close a WorkflowJobStore, then invoke a guarded mutating operation that uses `_ensure_conn`; assert it reopens the SQLite connection and lock descriptor and succeeds without ValueError.
- Concurrent close/recovery is serialized by the store lock.
- Repeated close/recover cycles do not leak descriptors or close unrelated reused descriptors.

### Acceptance Criteria
- No mutation path can call flock with fd -1.
- TRICKLE-122 submission no longer fails with negative file descriptor after an orchestrator replacement/restart.
- Existing workflow job store/restart/resource-cleanup tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

