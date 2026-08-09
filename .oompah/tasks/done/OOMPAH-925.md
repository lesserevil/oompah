---
id: OOMPAH-925
type: bug
status: Done
priority: 1
title: '[backend:orchestrator] Orchestrator shutdown remains fenced; runtime recovery
  is not durable for issue_ids=[] journals=[''workflow runtime drain'']'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T20:59:18.475816Z'
updated_at: '2026-08-09T20:16:30.695412Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-eaeb1129c2e4
    project_id: proj-14849f1b
    task_id: OOMPAH-925
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d947f0206a3a36b5a2e8d3710156d7415c0d02dcdcf0f6ae578a5ebd0f25f8d5
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:13:15.641964+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-925
    target_state: Done
    evidence_fingerprint: d947f0206a3a36b5a2e8d3710156d7415c0d02dcdcf0f6ae578a5ebd0f25f8d5
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:13:29.936174+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Project owner confirms OOMPAH-925 is a completed historical/provenance-only
      legacy record; this is not a landing claim.
    marked_at: '2026-08-09T20:16:28.561820+00:00'
    updated_at: '2026-08-09T20:16:28.561820+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Project owner confirms OOMPAH-925 is a completed historical/provenance-only
        legacy record; this is not a landing claim.
      recorded_at: '2026-08-09T20:16:28.561820+00:00'
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
Oompah detected a backend error from `backend:orchestrator`:

> Orchestrator shutdown remains fenced; runtime recovery is not durable for issue_ids=[] journals=['workflow runtime drain']

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Orchestrator shutdown remains fenced; runtime recovery is not durable for issue_ids=[] journals=['workflow runtime drain']

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
- fingerprint: 54fec71bc93919d5
- dedup_fingerprint: 54fec71bc93919d5

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 21:28
---
Directly claimed for closure with the systemic rollout. This alert was emitted by the graceful shutdown race fixed at bdabac3ff: an admitted workflow reconciliation held the lifecycle fence past the original drain path and produced the non-durable workflow runtime drain warning. The candidate adds drain/reconcile/store fencing and has already survived two live graceful restarts plus an exact full gate; OOMPAH-926 adds the remaining mixed-mode qualification-neutrality fix. I will terminalize this task only after the new exact head passes the full gate and repeated live staged restarts.
---
author: oompah
created: 2026-08-08 21:54
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: Orchestrator shutdown remains fenced; runtime recovery is not durable for issue_ids=[] journals=['workflow runtime drain']
---
author: oompah
created: 2026-08-08 21:57
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: Orchestrator shutdown remains fenced; runtime recovery is not durable for issue_ids=[] journals=['workflow runtime drain']
---
author: oompah
created: 2026-08-08 22:00
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: Orchestrator shutdown remains fenced; runtime recovery is not durable for issue_ids=[] journals=['workflow runtime drain']
---
author: oompah
created: 2026-08-08 22:12
---
Live rollout disproved the earlier assumption that OOMPAH-924 fully covered this alert: all three 6c7a6eabe graceful cutovers safely completed, but admitted 50-100s corpus reconciles exceeded the runtime's 10s bounded drain probe and emitted repeated false CRITICAL durability failures. Forensics confirmed one quiesced PID retained stores/authority until reconcile completion, then logged Orchestrator stopped before exec; there were no overlapping writers, closed-store access, bad FDs, or recovery rows. Fixed at ce8b839811c2f0ff297179278aa3aa6171c5705b by classifying a False drain result as safe retained-owner progress (INFO + retry), while preserving CRITICAL handling for real journal/worker retirement failures and exception handling. New regressions pass 2/2; the broad event-loop/workflow/resource/bootstrap slice passes 148/148. Exact full gate is running before repeat live restart validation.
---
author: oompah
created: 2026-08-08 22:32
---
Exact candidate ce8b839811c2f0ff297179278aa3aa6171c5705b passed the complete repository gate: 18,805 passed, 7 skipped, 2 xfailed, 43 warnings in 1203.07s. Focused shutdown/runtime coverage also passed (148 tests). Proceeding to staged live rollout; main remains unchanged until rollout acceptance completes.
---
author: oompah
created: 2026-08-09 05:13
---
Direct project-owner completion verified on composed rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e: exact full gate passed (18,874 passed, 7 skipped, 2 xfailed), all four durable workflow domains are live in enforce mode, no actionable global alerts remain, and current durable exhaustion/expired leases are zero.
---
author: oompah
created: 2026-08-09 05:13
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct project-owner completion after exact-head full-gate and live enforce verification.
---
<!-- COMMENTS:END -->
