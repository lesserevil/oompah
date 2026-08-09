---
id: OOMPAH-912
type: bug
status: Done
priority: 2
title: '[backend:workflow_runtime] Durable workflow reconcile failed for proj-14849f1b'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-08T14:11:47.740099Z'
updated_at: '2026-08-09T05:11:39.677592Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-857fabe66228
    project_id: proj-14849f1b
    task_id: OOMPAH-912
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0c7a29a364f6f4a5d41a955feacfcd30834ce2e1b6d299bfa13f83a402744491
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:11:29.068040+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-912
    target_state: Done
    evidence_fingerprint: 0c7a29a364f6f4a5d41a955feacfcd30834ce2e1b6d299bfa13f83a402744491
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:11:38.158523+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:workflow_runtime`:

> Durable workflow reconcile failed for proj-14849f1b

### Steps to Reproduce
1. Run oompah with `backend:workflow_runtime` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:workflow_runtime` and is recorded by oompah's `error_watcher`:

> Durable workflow reconcile failed for proj-14849f1b

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
- fingerprint: 2dd7a0b485ee1113
- dedup_fingerprint: 2dd7a0b485ee1113

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 14:14
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:workflow_runtime`

Message: Durable workflow reconcile failed for proj-14849f1b
---
author: oompah
created: 2026-08-08 14:25
---
Direct owner work began on published systemic composition branch after live shadow reproduction. Root cause: WorkflowRuntime.from_orchestrator returned legacy fact provider callbacks instead of invoking them, so fact revision hashing received a Python function and raised TypeError. The same adapter also late-binds project source closures and omits duplicate-investigation facts; regression-tested fixes are in progress. OOMPAH-912 remains Backlog only because an expired status-transition claim from the prior hung request now returns transition.recovery_required; this is an erroneous transition recovery deadlock, not a lack of ownership.
---
author: oompah
created: 2026-08-09 05:11
---
Direct project-owner completion verified on composed rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e: exact full gate passed (18,874 passed, 7 skipped, 2 xfailed), all four durable workflow domains are live in enforce mode, no actionable global alerts remain, and current durable exhaustion/expired leases are zero.
---
author: oompah
created: 2026-08-09 05:11
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct project-owner completion after exact-head full-gate and live enforce verification.
---
<!-- COMMENTS:END -->
