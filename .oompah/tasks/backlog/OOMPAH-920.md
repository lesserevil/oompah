---
id: OOMPAH-920
type: task
status: Backlog
priority: null
title: Make rollout canary rely on durable shadow evidence
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T16:18:41.997110Z'
updated_at: '2026-08-08T16:18:41.997110Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

The production durable workflow runtime owns every lifecycle tick in off/shadow/enforce and intentionally bypasses the retired legacy WorkflowShadowEvaluator. scripts/workflow_rollout_check.py nevertheless rejects an all-shadow production snapshot when workflow_shadow.last_evaluated_at is null, even after workflow_runtime.rollout and rollout_gate prove three successful persisted per-domain sweeps, a completed soak, current bindings, and no latest failure. Remove this unreachable legacy prerequisite while retaining fail-closed checks for durable rollout completeness, latest sweep failure, actionable alerts, expired/exhausted jobs, and any reported unresolved divergences. Update tests/test_workflow_rollout_check.py with a production durable-shadow regression and retain divergence rejection. Run focused tests, secret scan, and the exact full Makefile gate. Acceptance: a qualified durable all-shadow snapshot with a null retired legacy timestamp passes; incomplete/failed durable evidence or unresolved divergence still fails.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

