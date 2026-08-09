---
id: OOMPAH-924
type: bug
status: Done
priority: 2
title: '[backend:__main__] Orchestrator thread crashed'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T19:33:35.949962Z'
updated_at: '2026-08-09T20:16:26.977195Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-72eeb4423a81
    project_id: proj-14849f1b
    task_id: OOMPAH-924
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f505f711f4484155799287195a02238bc312f6224725439ba2726b535feb7615
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:12:53.123754+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-924
    target_state: Done
    evidence_fingerprint: f505f711f4484155799287195a02238bc312f6224725439ba2726b535feb7615
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:13:01.953591+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Project owner confirms OOMPAH-924 is a completed historical/provenance-only
      legacy record; this is not a landing claim.
    marked_at: '2026-08-09T20:16:24.830112+00:00'
    updated_at: '2026-08-09T20:16:24.830112+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Project owner confirms OOMPAH-924 is a completed historical/provenance-only
        legacy record; this is not a landing claim.
      recorded_at: '2026-08-09T20:16:24.830112+00:00'
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
Oompah detected a backend error from `backend:__main__`:

> Orchestrator thread crashed

### Steps to Reproduce
1. Run oompah with `backend:__main__` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:__main__` and is recorded by oompah's `error_watcher`:

> Orchestrator thread crashed

### Expected Behavior
The operation in `backend:__main__` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:__main__` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 3eb8662f89d42022
- dedup_fingerprint: 3eb8662f89d42022

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 19:47
---
Claimed directly. Root cause confirmed: graceful shutdown drains durable worker/handler operations but does not wait for an in-flight event-loop tick whose reconcile thread still owns WorkflowJobStore mutation authority. The shutdown path can therefore close the store authority fd before record_rollout_sweep completes. Implementing an explicit active-tick drain before persistent-store closure, with deterministic race regression coverage.
---
author: oompah
created: 2026-08-08 20:23
---
Implemented the shutdown-race fix in the systemic composition worktree. WorkflowRuntime now treats the complete reconcile (including its bare executor Future under cancellation) as explicit mutation authority; graceful shutdown fences scheduler startup/tick admission and uses a loop-independent safe-stop acknowledgement so asyncio.run cannot cancel the stop owner or deadlock a single-worker default executor. Added deterministic regressions for active tick, pre-tick startup, stop-before-run, threaded stop acknowledgement, caller cancellation, loop teardown, queued executor handoff, and pre-first-turn cancellation. Focused compatibility gate: 424 passed.
---
author: oompah
created: 2026-08-08 20:52
---
Exact review-ready commit bdabac3ff0619b85e1b61f7efb3f9a322b8efb51 passed the complete branch gate: 18,797 passed, 7 skipped, 2 xfailed, 43 warnings in 20m05s. The commit was atomically published to all 40 systemic-workflow refs and the new OOMPAH-924 ref. Two live make graceful cutovers completed on the exact commit; the second exercised the fixed code on shutdown and produced no Orchestrator crash, WorkflowJobStore closed-fd access, bad-file-descriptor error, or safe-stop fallback. /healthz reports healthy with the exact revision. Final rollout soak is now running.
---
author: oompah
created: 2026-08-08 21:00
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:__main__`

Message: Orchestrator thread crashed
---
author: oompah
created: 2026-08-09 05:12
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
