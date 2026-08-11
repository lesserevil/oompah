---
id: OOMPAH-1120
type: bug
status: Archived
priority: 2
title: '[backend:checkpoint_queue] Checkpoint flush FAILED (reason=debounce); push_failures=20'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T21:10:23.316731Z'
updated_at: '2026-08-11T22:49:08.007850Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-0cca8439f694
    project_id: proj-14849f1b
    task_id: OOMPAH-1120
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9ac1fe06cc15e06131d08991548db608b5785e5e4990f42249cc9cbfa3148e8a
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Operator consolidation of an auto-filed retry artifact into canonical
      defects OOMPAH-1127 and OOMPAH-1128 after recovering and publishing the affected
      Trickle state history.
    created_at: '2026-08-11T22:48:55.903993+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1120
    target_state: Archived
    evidence_fingerprint: 9ac1fe06cc15e06131d08991548db608b5785e5e4990f42249cc9cbfa3148e8a
    workflow_revision: null
    selected_ref: null
    selected_sha: null
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-11T22:49:06.235754+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:checkpoint_queue`:

> Checkpoint flush FAILED (reason=debounce); push_failures=20

### Steps to Reproduce
1. Run oompah with `backend:checkpoint_queue` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:checkpoint_queue` and is recorded by oompah's `error_watcher`:

> Checkpoint flush FAILED (reason=debounce); push_failures=20

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
- fingerprint: 27ff78623d3309f1
- dedup_fingerprint: 27ff78623d3309f1

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 22:49
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Operator consolidation of an auto-filed retry artifact into canonical defects OOMPAH-1127 and OOMPAH-1128 after recovering and publishing the affected Trickle state history.
---
<!-- COMMENTS:END -->
