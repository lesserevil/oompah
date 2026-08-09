---
id: OOMPAH-929
type: task
status: Done
priority: null
title: Rearm superseded durable events on newer source generations
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T02:47:20.781959Z'
updated_at: '2026-08-09T21:43:37.802670Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-45980c0f6efa
    project_id: proj-14849f1b
    task_id: OOMPAH-929
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e28cd322efcb2977c5a85e93bc41b04ec509fcf87fe930d854f476eacc78569d
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:16:05.914276+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-929
    target_state: Done
    evidence_fingerprint: e28cd322efcb2977c5a85e93bc41b04ec509fcf87fe930d854f476eacc78569d
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-09T05:16:15.450449+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Owner-reviewed terminal implementation is retained. The Done child is
      durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
      exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
    marked_at: '2026-08-09T21:43:36.158057+00:00'
    updated_at: '2026-08-09T21:43:36.158057+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Owner-reviewed terminal implementation is retained. The Done child is
        durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
        exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
      recorded_at: '2026-08-09T21:43:36.158057+00:00'
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

Live all-enforce rollout of candidate 33f85955b exposed an indefinite liveness divergence for OOMPAH-869 and OOMPAH-899. Their validation_submission fact-lane jobs were superseded by newer imperative direct-owner events; later workflow snapshots reuse the unchanged event cursor/idempotency key, replay the terminal superseded rows, and correctly reject them as materialized. Implementation scope: update WorkflowJobStore.materialize_event and its runtime integration so a newer source generation allocates a fresh event generation/idempotency key when the exact semantic event has no live job or only a terminal superseded/cancelled/completed/exhausted job, while preserving same-source idempotency and replay of queued/running/retry_wait authority. Relevant files: oompah/workflow_jobs.py or the actual durable store module, workflow runtime materialization paths, and focused workflow job/runtime tests. Required tests: all terminal job states rearm only on a newer source generation; exact same-source replay stays idempotent; active equivalent jobs replay without duplication; runtime regression where a fact validation_submission is superseded by an imperative owner event and is regenerated on the next accepted snapshot. Acceptance: staged all-enforce live rollout reaches a complete liveness scan with required_recovery_count equal to materialized_recovery_count, current divergence zero, healthy service, zero actionable alerts, no expired jobs, and the five-minute rollout canary passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 02:47
---
Live reproduction confirmed at workflow generations 39 and 40: required_recovery_count=132, materialized_recovery_count=130, with OOMPAH-869 and OOMPAH-899 repeatedly replaying terminal superseded validation_submission jobs. Release advance is paused until the store/runtime fix, focused tests, exact gate, and all-enforce live convergence complete.
---
author: oompah
created: 2026-08-09 03:12
---
Fix committed and pushed at fba45f07e. The 177-test affected matrix passes. Exact gate then exposed a separate reproducible live-project test-fixture isolation defect, filed as OOMPAH-930; release remains paused until that fixture defect is corrected and the exact gate passes.
---
author: oompah
created: 2026-08-09 05:16
---
Completed by direct project owner. Durable event reactivation fix fba45f07e is included in rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e. Exact full gate passed (18,874 passed, 7 skipped, 2 xfailed); all domains are live in enforce; the replacement generation is authoritative and current durable exhaustion is zero.
---
author: oompah
created: 2026-08-09 05:16
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct project-owner completion after exact-head full-gate and live enforce verification.
---
<!-- COMMENTS:END -->
