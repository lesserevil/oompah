---
id: OOMPAH-1265
type: task
status: Open
priority: 1
title: Prove external-prerequisite lifecycle convergence and observability
parent: OOMPAH-1231
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-1263
- OOMPAH-1264
labels: []
assignee: null
created_at: '2026-08-14T02:40:21.846935Z'
updated_at: '2026-08-14T02:41:26.079420Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: oompah-1231-lifecycle-acceptance-v1
  request_fingerprint: 4f48f1f0e957c03ae28cb1f4f01e0f52c4c6c9020d902bc67d1cfb4f69389377
oompah.start_blocked_by: *id001
oompah.lifecycle_revision: 1
---
## Summary

Add production-shaped cross-component acceptance for the complete external-prerequisite lifecycle: trusted worker handoff, exact parking, zero-job authority publication, restart convergence, named dependency/operator observability, prerequisite resolution, and exactly one continuation generation. Exercise TRICKLE-123 repeated unavailable-platform handoffs, TRICKLE-132 cross-project dependency/head drift, TRICKLE-139 auxiliary repair retirement, and TRICKLE-143 structured review continuation. Verify dashboard and alerts distinguish situation-normal dependency waits from named operator action, liveness has no unexplained divergence, and old jobs cannot mutate after resolution. Update user-facing operator documentation only where a concrete resolution action exists. Required checks: focused workflow/runtime/liveness/server/UI suites, deterministic restart/race tests, terminal mutation scan, and complete Makefile gate. Acceptance: live-shaped tasks remain quiet while blocked, survive restart, resume once when truthfully resolved, and expose precise recovery evidence without generic warning floods.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

