---
id: OOMPAH-1093
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Orchestrator shutdown attempt failed; retaining process
  and retrying'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T16:04:30.156611Z'
updated_at: '2026-08-11T16:09:38.737000Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Orchestrator shutdown attempt failed; retaining process and retrying

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Orchestrator shutdown attempt failed; retaining process and retrying

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 9984037ce1db983d
- dedup_fingerprint: 9984037ce1db983d

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 16:09
---
Live reproduction during normal make restart at 2026-08-11T16:04Z: shutdown quiesced while a terminal auditor was between durable claim/worktree preparation and provider admission. Orchestrator._drain_background_work raised RuntimeError('lifecycle publication snapshot did not drain; refusing to close lifecycle stores'); stop_until_safe retained the process and its next attempt succeeded, then os.execv completed. The interrupted auditor lease recovered as abandoned/retry_wait. Repair scope: make the graceful shutdown publication drain converge deterministically when terminal-audit/provider admission loses the quiesce race, without reporting a backend error for a safely retryable internal drain; retain fail-closed refusal to close stores while true writers remain. Add a deterministic barrier regression around audit claim/provider-admission versus quiesce, prove bounded retry reaches a fully published snapshot and clean shutdown with no orphan workflow lease/attempt/worktree, and preserve error reporting when progress is genuinely impossible.
---
<!-- COMMENTS:END -->
