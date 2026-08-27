---
id: OOMPAH-1350
type: task
status: Open
priority: null
title: Correct GitLab merge queue semantics and stale Trickle MR handling
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-27T19:29:03.022770Z'
updated_at: '2026-08-27T19:40:41.664951Z'
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
  creation_marker: 782737cb-2e24-4b6d-8b3f-f7499ae4e544
  request_fingerprint: a28c72be488724c2d094a1252a00e1084bb0ce87b25f541009301b04c8b11756
oompah.lifecycle_revision: 1
---
## Summary

Fix GitLab merge queue semantics exposed by Trickle. Implement exact-head enqueue, normalize queue state, fence stale wrong-target MRs, safely reconcile superseded reviews, add Trickle-shaped regression tests, and update docs/UI. Acceptance: merge-train policy is respected, no unfenced enqueue occurs, stale MRs cannot mutate lifecycle, and all gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

