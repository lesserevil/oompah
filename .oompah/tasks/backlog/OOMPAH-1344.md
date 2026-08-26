---
id: OOMPAH-1344
type: task
status: Backlog
priority: 1
title: Bound workflow reconciliation and deduplicate forge observations
parent: OOMPAH-1342
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-26T18:43:10.725032Z'
updated_at: '2026-08-26T18:43:10.725032Z'
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
  creation_marker: manual-service-recovery-20260826-reconcile
  request_fingerprint: e6c78ba0978cc6d0161af8a4dfd78cefb2d4c74f979a7ef712c76116bc784ea9
---
## Summary

Implement workstream 2 of plans/service-throughput-recovery.md. Profile the durable integration/review fact paths and cache project-scoped review, CI, branch-head, parent, and landing observations for one generation-bound world scan. Skip expensive terminal-task work only when complete durable landing/provenance evidence proves it safe. Preserve stale-authority rejection and all exact-head/project fences. Add production-shaped tests under tests/ that use hundreds of Done/Ready tasks and assert SCM calls are bounded by distinct evidence keys; include mutation/supersede regressions and a deterministic runtime-budget test. Acceptance: the Trickle-sized fixture completes within the configured restart-convergence budget with no unexplained liveness divergence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

