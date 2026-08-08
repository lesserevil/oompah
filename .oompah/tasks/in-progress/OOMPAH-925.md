---
id: OOMPAH-925
type: bug
status: In Progress
priority: 1
title: '[backend:orchestrator] Orchestrator shutdown remains fenced; runtime recovery
  is not durable for issue_ids=[] journals=[''workflow runtime drain'']'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T20:59:18.475816Z'
updated_at: '2026-08-08T22:00:29.932114Z'
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

> Orchestrator shutdown remains fenced; runtime recovery is not durable for issue_ids=[] journals=['workflow runtime drain']

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Orchestrator shutdown remains fenced; runtime recovery is not durable for issue_ids=[] journals=['workflow runtime drain']

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
- fingerprint: 54fec71bc93919d5
- dedup_fingerprint: 54fec71bc93919d5

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 21:28
---
Directly claimed for closure with the systemic rollout. This alert was emitted by the graceful shutdown race fixed at bdabac3ff: an admitted workflow reconciliation held the lifecycle fence past the original drain path and produced the non-durable workflow runtime drain warning. The candidate adds drain/reconcile/store fencing and has already survived two live graceful restarts plus an exact full gate; OOMPAH-926 adds the remaining mixed-mode qualification-neutrality fix. I will terminalize this task only after the new exact head passes the full gate and repeated live staged restarts.
---
author: oompah
created: 2026-08-08 21:54
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: Orchestrator shutdown remains fenced; runtime recovery is not durable for issue_ids=[] journals=['workflow runtime drain']
---
author: oompah
created: 2026-08-08 21:57
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: Orchestrator shutdown remains fenced; runtime recovery is not durable for issue_ids=[] journals=['workflow runtime drain']
---
author: oompah
created: 2026-08-08 22:00
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: Orchestrator shutdown remains fenced; runtime recovery is not durable for issue_ids=[] journals=['workflow runtime drain']
---
<!-- COMMENTS:END -->
