---
id: OOMPAH-920
type: task
status: Done
priority: null
title: Make rollout canary rely on durable shadow evidence
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T16:18:41.997110Z'
updated_at: '2026-08-09T05:14:47.412419Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c99920cc40f3
    project_id: proj-14849f1b
    task_id: OOMPAH-920
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3ba2bac441d3e822b66496bb0ec69874cdbc07e858072c2905a196a7acb592c9
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct project-owner completion after exact-head full-gate and live enforce
      verification.
    created_at: '2026-08-09T05:14:41.544442+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

The production durable workflow runtime owns every lifecycle tick in off/shadow/enforce and intentionally bypasses the retired legacy WorkflowShadowEvaluator. scripts/workflow_rollout_check.py nevertheless rejects an all-shadow production snapshot when workflow_shadow.last_evaluated_at is null, even after workflow_runtime.rollout and rollout_gate prove three successful persisted per-domain sweeps, a completed soak, current bindings, and no latest failure. Remove this unreachable legacy prerequisite while retaining fail-closed checks for durable rollout completeness, latest sweep failure, actionable alerts, expired/exhausted jobs, and any reported unresolved divergences. Update tests/test_workflow_rollout_check.py with a production durable-shadow regression and retain divergence rejection. Run focused tests, secret scan, and the exact full Makefile gate. Acceptance: a qualified durable all-shadow snapshot with a null retired legacy timestamp passes; incomplete/failed durable evidence or unresolved divergence still fails.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 05:14
---
Direct project-owner completion verified on composed rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e: exact full gate passed (18,874 passed, 7 skipped, 2 xfailed), all four durable workflow domains are live in enforce mode, no actionable global alerts remain, and current durable exhaustion/expired leases are zero.
---
<!-- COMMENTS:END -->
