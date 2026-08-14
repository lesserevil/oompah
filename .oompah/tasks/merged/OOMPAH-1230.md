---
id: OOMPAH-1230
type: bug
status: Merged
priority: 2
title: '[backend:task_transition_service] Task transition mutation guard failed project=proj-3e4e9214
  task=TRICKLE-140 reason=implementation.validation_submission'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T09:58:05.284702Z'
updated_at: '2026-08-14T07:37:55.268816Z'
work_branch: OOMPAH-1230
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 3
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1230
  head_sha: 320593caf587c69ada8e35b54e1b458929b34c63
  submitted_at: '2026-08-13T10:15:46.222133+00:00'
  updated_at: '2026-08-13T10:15:46.222133+00:00'
oompah.work_branch: OOMPAH-1230
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-8932fcfe13f9
    project_id: proj-14849f1b
    task_id: OOMPAH-1230
    digest: 2f258e8911067244b19b2022d1efbf0999338a11c3b215cb0c5e248d40032db2
  - version: 1
    audit_id: audit-dd6b43e935e5
    project_id: proj-14849f1b
    task_id: OOMPAH-1230
    digest: 2f258e8911067244b19b2022d1efbf0999338a11c3b215cb0c5e248d40032db2
  oompah.terminal_override_records:
  - version: 1
    override_id: override-b86e7f5f34d6
    project_id: proj-14849f1b
    task_id: OOMPAH-1230
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f258e8911067244b19b2022d1efbf0999338a11c3b215cb0c5e248d40032db2
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #858 merged as c02da55a7 and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:37:50.393033+00:00'
    selected_ref: 320593caf587c69ada8e35b54e1b458929b34c63
    selected_sha: 320593caf587c69ada8e35b54e1b458929b34c63
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8932fcfe13f9
    project_id: proj-14849f1b
    task_id: OOMPAH-1230
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f258e8911067244b19b2022d1efbf0999338a11c3b215cb0c5e248d40032db2
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T10:16:14.669803+00:00'
    eligible_at: '2026-08-13T10:16:14.669803+00:00'
    selected_ref: 320593caf587c69ada8e35b54e1b458929b34c63
    selected_sha: 320593caf587c69ada8e35b54e1b458929b34c63
  - version: 1
    audit_id: audit-dd6b43e935e5
    project_id: proj-14849f1b
    task_id: OOMPAH-1230
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f258e8911067244b19b2022d1efbf0999338a11c3b215cb0c5e248d40032db2
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T10:16:14.669803+00:00'
    prerequisite_audit_id: audit-8932fcfe13f9
    selected_ref: 320593caf587c69ada8e35b54e1b458929b34c63
    selected_sha: 320593caf587c69ada8e35b54e1b458929b34c63
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:task_transition_service`:

> Task transition mutation guard failed project=proj-3e4e9214 task=TRICKLE-140 reason=implementation.validation_submission

### Steps to Reproduce
1. Run oompah with `backend:task_transition_service` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:task_transition_service` and is recorded by oompah's `error_watcher`:

> Task transition mutation guard failed project=proj-3e4e9214 task=TRICKLE-140 reason=implementation.validation_submission

### Expected Behavior
The operation in `backend:task_transition_service` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:task_transition_service` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 8da03cc9e21f888f
- dedup_fingerprint: 8da03cc9e21f888f

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 09:59
---
Claimed directly for live scheduling recovery. Root cause captured from the newly added traceback: WorkflowRuntime.from_orchestrator defines workflow_transition_guard(intent) but TaskTransitionService invokes mutation guards as guard(intent, issue). Every runtime validation transition therefore raises TypeError before the specific validation authority check. Fixing the adapter signature and adding an end-to-end regression now.
---
author: oompah
created: 2026-08-13 10:03
---
Fix pushed with regression coverage. The runtime guard now honors TaskTransitionService's two-argument callback contract while retaining its own fresh authoritative tracker read. Focused workflow runtime and task transition suites: 284 passed. Hosted gates are starting.
---
author: oompah
created: 2026-08-13 10:15
---
Honor TaskTransitionService's two-argument mutation-guard callback contract while retaining the runtime guard's authoritative fresh tracker read. Regression coverage and 284 focused tests pass; hosted CI passes on Python 3.11, 3.12, and 3.13.
---
author: oompah
created: 2026-08-13 10:16
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
