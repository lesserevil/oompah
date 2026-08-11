---
id: OOMPAH-1121
type: bug
status: Archived
priority: 2
title: '[backend:checkpoint_queue] Checkpoint flush FAILED (reason=debounce); push_failures=21'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T21:13:35.791318Z'
updated_at: '2026-08-11T22:49:23.492474Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-ba7363311249
    project_id: proj-14849f1b
    task_id: OOMPAH-1121
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fc5b883e41e8edc45b05cf4da6797d3f8398c59d60c863a2fb0678f8911360a6
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Operator consolidation of an auto-filed retry artifact into canonical
      defects OOMPAH-1127 and OOMPAH-1128 after recovering and publishing the affected
      Trickle state history.
    created_at: '2026-08-11T22:49:18.941414+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:checkpoint_queue`:

> Checkpoint flush FAILED (reason=debounce); push_failures=21

### Steps to Reproduce
1. Run oompah with `backend:checkpoint_queue` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:checkpoint_queue` and is recorded by oompah's `error_watcher`:

> Checkpoint flush FAILED (reason=debounce); push_failures=21

### Expected Behavior
The operation in `backend:checkpoint_queue` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:checkpoint_queue` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: efde8a525aadcb9c
- dedup_fingerprint: efde8a525aadcb9c

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

