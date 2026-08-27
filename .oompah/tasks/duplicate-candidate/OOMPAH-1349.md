---
id: OOMPAH-1349
type: task
status: Duplicate Candidate
priority: null
title: Correct GitLab merge queue semantics and stale Trickle MR handling
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-27T19:25:52.410714Z'
updated_at: '2026-08-27T19:48:04.549046Z'
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
  creation_marker: ea112b93-4cc2-4fdb-adea-87770466537e
  request_fingerprint: 9a10eab74f159afef3bac70ef471048e6491d7081ef65d5deb54939ac1a399a3
oompah.lifecycle_revision: 1
---
## Summary

Fix the GitLab merge path exposed by Trickle. Evidence: GitLab has merge pipelines/trains enabled while Oompah merge_queue_enabled=false; stale MRs target main while accepted queue records target shared epic branches; GitLab observations omit auto_merge_enabled/mergeable_state; GitLab lacks enable_auto_merge_exact. Define provider-specific queue behavior, exact-head enqueue, queue-state observation, wrong-target fencing and safe stale-MR reconciliation. Add GitLab unit/integration regressions including Trickle-shaped stale main-target MRs. Update UI/docs. Acceptance: no direct merge when train policy is required, no unfenced enqueue, stale reviews cannot mutate lifecycle, focused/full gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-27 19:47
---
Duplicate task created when an earlier task-create request timed out after committing. Canonical task: OOMPAH-1350. Do not dispatch.
---
<!-- COMMENTS:END -->
