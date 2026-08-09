---
id: OOMPAH-932
type: bug
status: In Progress
priority: 2
title: '[backend:workflow_runtime] Durable workflow source evaluation failed for proj-14849f1b'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T05:18:44.565095Z'
updated_at: '2026-08-09T05:54:03.702097Z'
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

> Durable workflow source evaluation failed for proj-14849f1b

### Steps to Reproduce
1. Run oompah with `backend:workflow_runtime` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:workflow_runtime` and is recorded by oompah's `error_watcher`:

> Durable workflow source evaluation failed for proj-14849f1b

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
- fingerprint: be60e35246101e15
- dedup_fingerprint: be60e35246101e15

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 05:25
---
Root cause confirmed: a normal tracker source race can yield an unowned facts_refresh decision from a managed domain. WorkflowRuntime treated that hint as a foreign durable action, rejected the entire project cut, and prevented generation publication. Fix in progress scopes managed batches by dropping only actions explicitly registered to owner=none while preserving fail-closed rejection for unknown or cross-domain actions. Regression reproduces a stale epic list read followed by a current terminal task-fact read; focused tests pass.
---
author: oompah
created: 2026-08-09 05:54
---
Fix committed and pushed at e4a618059de5c03ce6e900a673bbd7540e9c0d06. Exact-head full gate passed: 18,877 passed, 7 skipped, 2 xfailed. Deployed live in all-enforce mode; authoritative generation 161 published with source_error_count=0, current_divergence_count=0, complete 150/150 recovery materialization, current exhausted=0, expired leases=0, and the one-shot rollout canary passed. Protected-main delivery is PR #749: https://github.com/lesserevil/oompah/pull/749
---
<!-- COMMENTS:END -->
