---
id: OOMPAH-922
type: bug
status: Done
priority: 2
title: '[backend:server] Update issue API error: TaskTransitionNotApplied(''TRICKLE-126:
  In Progress was not applied (rejected: transition.illegal_edge)'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T16:46:56.941856Z'
updated_at: '2026-08-09T05:12:26.260193Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-32899455930a
    project_id: proj-14849f1b
    task_id: OOMPAH-922
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d04692c9b63c05fafd79305c57588484776465ff8c88786626a6ac4ce976157f
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:12:14.583577+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-922
    target_state: Done
    evidence_fingerprint: d04692c9b63c05fafd79305c57588484776465ff8c88786626a6ac4ce976157f
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:12:24.832104+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Update issue API error: TaskTransitionNotApplied('TRICKLE-126: In Progress was not applied (rejected: transition.illegal_edge)')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Update issue API error: TaskTransitionNotApplied('TRICKLE-126: In Progress was not applied (rejected: transition.illegal_edge)')

### Expected Behavior
The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: dab88f7d8e6b9ab3
- dedup_fingerprint: dab88f7d8e6b9ab3

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 17:10
---
Implemented the shared recurrence fix at 8a0b6948a1089b625d4ba416bde1bfed1da7a424. Structured durable-transition REJECTED outcomes now return HTTP 409 transition_rejected and log at INFO, so illegal-edge/generation-required client conflicts no longer create error-watcher tasks or health warnings. Focused regression suite: 25 passed; terminal mutation scan and secret scan passed. Exact full gate is next.
---
author: oompah
created: 2026-08-08 17:12
---
Correction to the prior progress comment: the amended commit's exact SHA is 8a0b6948ab0efb7a12f475b9f1cffc2d2a04a719. The short SHA remains 8a0b6948a; the earlier full SHA was copied from the pre-amend commit suffix and is not a Git object.
---
author: oompah
created: 2026-08-08 17:18
---
Review hardening amended the fix to 7a4a5a3c0f912e24a00a55346af39ce7ca99213a (superseding 8a0b6948a). Expected policy REJECTED outcomes are now explicitly allowlisted for INFO/409; ambiguous terminal-stage and future operational rejections remain ERROR/500 so error_watcher still catches genuine backend failures. Focused suite: 28 passed; safety scans passed. Restarting the exact full gate on this head.
---
author: oompah
created: 2026-08-09 05:12
---
Direct project-owner completion verified on composed rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e: exact full gate passed (18,874 passed, 7 skipped, 2 xfailed), all four durable workflow domains are live in enforce mode, no actionable global alerts remain, and current durable exhaustion/expired leases are zero.
---
author: oompah
created: 2026-08-09 05:12
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct project-owner completion after exact-head full-gate and live enforce verification.
---
<!-- COMMENTS:END -->
