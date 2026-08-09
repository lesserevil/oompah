---
id: OOMPAH-965
type: bug
status: Open
priority: 2
title: '[backend:workflow_runtime] Durable workflow publication failed for proj-14849f1b'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T16:25:26.622591Z'
updated_at: '2026-08-09T16:27:22.144113Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:workflow_runtime`:

> Durable workflow publication failed for proj-14849f1b

### Steps to Reproduce
1. Run oompah with `backend:workflow_runtime` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:workflow_runtime` and is recorded by oompah's `error_watcher`:

> Durable workflow publication failed for proj-14849f1b

### Expected Behavior
The operation in `backend:workflow_runtime` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:workflow_runtime` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: fe9cb767e4524d9b
- dedup_fingerprint: fe9cb767e4524d9b

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 16:27
---
Root cause captured at 2026-08-09T16:25:25 while direct owner audit overrides changed terminal-audit disposition during a full publication: publish_after_terminal_proof deliberately raised WorkflowRuntimeError('terminal-audit disposition changed before publication') as a stale-snapshot fence. The publication was correctly rejected and retryable; treating this expected authority race as an unhandled ERROR caused error_watcher to file this task. Scope should distinguish expected stale/fenced publication invalidation from genuine durable-store/publication failure, reschedule/coalesce a fresh reconcile, emit bounded informational telemetry, and retain ERROR/error_watcher behavior for unexpected failures. Add an exact disposition-change-before-publication regression proving no task is auto-filed and fresh publication converges.
---
<!-- COMMENTS:END -->
