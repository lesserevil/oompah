---
id: OOMPAH-1342
type: epic
status: Backlog
priority: 1
title: Recover production service throughput and workflow progress
parent: null
children:
- OOMPAH-1343
- OOMPAH-1344
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-26T18:42:41.866488Z'
updated_at: '2026-08-26T18:43:12.555441Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: manual-service-recovery-20260826-epic
  request_fingerprint: 070158bda33ab0d0629239fafe161aeb566b706e18982b59d6073e52830bd282
---
## Summary

Implement the accepted recovery plan in plans/service-throughput-recovery.md. This epic coordinates four independently deliverable children: deployment stabilization, bounded reconciliation/forge observations, snapshot-backed reviews API, and bounded storage retention. Preserve fail-closed lifecycle, exact-head, project-scope, and audit guarantees. Require focused tests for every child and the complete Makefile gate plus workflow rollout check before resuming production projects. Acceptance: the children are complete in rollout order, production reconciliation stays inside its configured budget, APIs remain responsive, storage growth is bounded, exhausted decisions have explicit dispositions, and projects resume without unexplained liveness divergence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

