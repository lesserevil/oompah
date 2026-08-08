---
id: OOMPAH-924
type: bug
status: In Progress
priority: 2
title: '[backend:__main__] Orchestrator thread crashed'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T19:33:35.949962Z'
updated_at: '2026-08-08T19:47:10.932854Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:__main__`:

> Orchestrator thread crashed

### Steps to Reproduce
1. Run oompah with `backend:__main__` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:__main__` and is recorded by oompah's `error_watcher`:

> Orchestrator thread crashed

### Expected Behavior
The operation in `backend:__main__` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:__main__` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 3eb8662f89d42022
- dedup_fingerprint: 3eb8662f89d42022

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 19:47
---
Claimed directly. Root cause confirmed: graceful shutdown drains durable worker/handler operations but does not wait for an in-flight event-loop tick whose reconcile thread still owns WorkflowJobStore mutation authority. The shutdown path can therefore close the store authority fd before record_rollout_sweep completes. Implementing an explicit active-tick drain before persistent-store closure, with deterministic race regression coverage.
---
<!-- COMMENTS:END -->
