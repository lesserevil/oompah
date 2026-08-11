---
id: OOMPAH-1113
type: bug
status: Archived
priority: 2
title: '[backend:terminal_transition_coordinator] Failed to apply audit-result status
  ''Done'' for TRICKLE-128'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T21:07:45.520946Z'
updated_at: '2026-08-11T22:46:06.253449Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-91b4fb102b09
    project_id: proj-14849f1b
    task_id: OOMPAH-1113
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4ad45575615ae0758a911fce560f487d1b785b4c6c85a1b95e99761eb9ce407d
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Operator consolidation of a downstream terminal-transition artifact into
      canonical defect OOMPAH-1127 after recovering and publishing the affected Trickle
      state history.
    created_at: '2026-08-11T22:45:44.622542+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1113
    target_state: Archived
    evidence_fingerprint: 4ad45575615ae0758a911fce560f487d1b785b4c6c85a1b95e99761eb9ce407d
    workflow_revision: null
    selected_ref: null
    selected_sha: null
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-11T22:45:54.868339+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:terminal_transition_coordinator`:

> Failed to apply audit-result status 'Done' for TRICKLE-128

### Steps to Reproduce
1. Run oompah with `backend:terminal_transition_coordinator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:terminal_transition_coordinator` and is recorded by oompah's `error_watcher`:

> Failed to apply audit-result status 'Done' for TRICKLE-128

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
- fingerprint: fa0adff314a824bc
- dedup_fingerprint: fa0adff314a824bc

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 22:45
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Operator consolidation of a downstream terminal-transition artifact into canonical defect OOMPAH-1127 after recovering and publishing the affected Trickle state history.
---
author: oompah
created: 2026-08-11 22:46
---
Archived as a downstream artifact of the Trickle forge-cutover checkpoint incident. The stale checkpoint-writer/credential-authority defect is tracked by OOMPAH-1127. The affected state history was recovered and fast-forwarded to GitLab at d6b89313f65b8b018a254e23cfb4510482338479.
---
<!-- COMMENTS:END -->
