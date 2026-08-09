---
id: OOMPAH-923
type: bug
status: Done
priority: 2
title: '[backend:server] Update issue API error: TaskTransitionNotApplied(''TRICKLE-126:
  In Progress was not applied (rejected: transition.generation_required)'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T16:51:21.989830Z'
updated_at: '2026-08-09T20:16:18.443076Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-167bdcba84f7
    project_id: proj-14849f1b
    task_id: OOMPAH-923
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7bd129f8a4d1a2b614e6d1bf7a9008539b374e4b70e2169d29182cba2cdf213f
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:12:33.223840+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-923
    target_state: Done
    evidence_fingerprint: 7bd129f8a4d1a2b614e6d1bf7a9008539b374e4b70e2169d29182cba2cdf213f
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:12:42.307302+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Project owner confirms OOMPAH-923 is a completed historical/provenance-only
      legacy record; this is not a landing claim.
    marked_at: '2026-08-09T20:16:16.109380+00:00'
    updated_at: '2026-08-09T20:16:16.109380+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Project owner confirms OOMPAH-923 is a completed historical/provenance-only
        legacy record; this is not a landing claim.
      recorded_at: '2026-08-09T20:16:16.109380+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Update issue API error: TaskTransitionNotApplied('TRICKLE-126: In Progress was not applied (rejected: transition.generation_required)')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Update issue API error: TaskTransitionNotApplied('TRICKLE-126: In Progress was not applied (rejected: transition.generation_required)')

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
- fingerprint: 47e4066f393770b2
- dedup_fingerprint: 47e4066f393770b2

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 17:11
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
