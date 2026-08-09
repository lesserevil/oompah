---
id: OOMPAH-913
type: bug
status: Done
priority: 2
title: '[backend:server] Update issue API error: TaskTransitionNotApplied(''OOMPAH-912:
  Open was not applied (waiting: transition.recovery_required)'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T14:23:18.279242Z'
updated_at: '2026-08-09T20:16:06.515574Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-9c7316cf5da9
    project_id: proj-14849f1b
    task_id: OOMPAH-913
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c83d202fe1eac30e9675cf766b449087dc03ac40ab8e09432d1775a5b8de6470
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:11:51.787378+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-913
    target_state: Done
    evidence_fingerprint: c83d202fe1eac30e9675cf766b449087dc03ac40ab8e09432d1775a5b8de6470
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:11:59.750610+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Project owner confirms OOMPAH-913 is a completed historical/provenance-only
      legacy record; this is not a landing claim.
    marked_at: '2026-08-09T20:16:04.205421+00:00'
    updated_at: '2026-08-09T20:16:04.205421+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Project owner confirms OOMPAH-913 is a completed historical/provenance-only
        legacy record; this is not a landing claim.
      recorded_at: '2026-08-09T20:16:04.205421+00:00'
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

> Update issue API error: TaskTransitionNotApplied('OOMPAH-912: Open was not applied (waiting: transition.recovery_required)')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Update issue API error: TaskTransitionNotApplied('OOMPAH-912: Open was not applied (waiting: transition.recovery_required)')

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
- fingerprint: 57090f8aa43a1853
- dedup_fingerprint: 57090f8aa43a1853

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 14:37
---
Direct owner fix in progress on the systemic composition branch. This task is the error-watcher symptom of expected durable transition contention. The server now classifies transition.owner_active and transition.recovery_required as retryable HTTP 409 warnings instead of unexpected ERROR logs, so ordinary contention cannot auto-file another backend bug. Focused classification/API tests pass.
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
