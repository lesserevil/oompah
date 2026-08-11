---
id: OOMPAH-1116
type: bug
status: Archived
priority: 2
title: '[backend:terminal_transition_coordinator] Failed to apply audit-result status
  ''Merged'' for TRICKLE-126'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T21:08:37.292420Z'
updated_at: '2026-08-11T22:47:16.308671Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-ebdd9156f5a0
    project_id: proj-14849f1b
    task_id: OOMPAH-1116
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3b56aadc9b5f465946aa5f416b0ac8d7c6fe4bf3acbc8a4d230408d072299f46
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Operator consolidation of a downstream terminal-transition artifact into
      canonical defect OOMPAH-1127 after recovering and publishing the affected Trickle
      state history.
    created_at: '2026-08-11T22:46:59.268041+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1116
    target_state: Archived
    evidence_fingerprint: 3b56aadc9b5f465946aa5f416b0ac8d7c6fe4bf3acbc8a4d230408d072299f46
    workflow_revision: null
    selected_ref: null
    selected_sha: null
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-11T22:47:13.353211+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:terminal_transition_coordinator`:

> Failed to apply audit-result status 'Merged' for TRICKLE-126

### Steps to Reproduce
1. Run oompah with `backend:terminal_transition_coordinator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:terminal_transition_coordinator` and is recorded by oompah's `error_watcher`:

> Failed to apply audit-result status 'Merged' for TRICKLE-126

### Expected Behavior
The operation in `backend:terminal_transition_coordinator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:terminal_transition_coordinator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 9559903880ee7ddc
- dedup_fingerprint: 9559903880ee7ddc

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 22:47
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Operator consolidation of a downstream terminal-transition artifact into canonical defect OOMPAH-1127 after recovering and publishing the affected Trickle state history.
---
<!-- COMMENTS:END -->
