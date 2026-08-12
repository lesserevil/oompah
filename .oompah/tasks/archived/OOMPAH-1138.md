---
id: OOMPAH-1138
type: bug
status: Archived
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=TRICKLE-140'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-12T15:07:48.444434Z'
updated_at: '2026-08-12T20:05:37.346035Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-97799699f83d
    project_id: proj-14849f1b
    task_id: OOMPAH-1138
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0ef608fa37db1c1cb226c992a281c10cc1cbebc3d12666d163ec446e743ae731
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Historical auto-filed occurrence from the state-branch and dispatch-convergence
      incident, consolidated into completed roots OOMPAH-1127, OOMPAH-1128, and OOMPAH-1177.
      PRs #836 and #837 delivered the durable transport, stable incident identity,
      and fail-closed provider-admission repairs with full CI. This occurrence requires
      no independent implementation.'
    created_at: '2026-08-12T20:05:31.001904+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=TRICKLE-140

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=TRICKLE-140

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
- fingerprint: 15f7150750a148eb
- dedup_fingerprint: 15f7150750a148eb
- source_issue: TRICKLE-140

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

