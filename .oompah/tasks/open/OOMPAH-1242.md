---
id: OOMPAH-1242
type: task
status: Open
priority: null
title: Retire nested topology repair when exact rebase helper owns the branch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T14:32:41.192085Z'
updated_at: '2026-08-13T14:44:17.766604Z'
work_branch: OOMPAH-1242
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 17b045c2-9045-4892-be53-3eac67d25256
  request_fingerprint: 4e8f025d5976a94cb2d61527c19326a04aac0e16daf6d281733a3e92c80ba605
oompah.lifecycle_revision: 1
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1242
  head_sha: f10263212cf4f759f81fd2fd034ce383956dfd8f
  submitted_at: '2026-08-13T14:44:09.735151+00:00'
  updated_at: '2026-08-13T14:44:09.735151+00:00'
oompah.work_branch: OOMPAH-1242
---
## Summary

Scope: fix restart recovery and durable nested-dispatch repair execution so an exact server-authorized epic-rebase helper never remains blocked by, or keeps retrying, an ordinary nested topology fast-forward repair for the branch it exclusively owns. Current live reproduction: TRICKLE-141 gained exact rebase authority for persisted source TRICKLE-130, but workflow job 16757 remained retry_wait because startup recovery calls raw topology collection and reports unique commits. Update the recovery/claim paths to revalidate exact helper publish authority and atomically cancel or supersede obsolete topology jobs before implementation admission. Relevant code: Orchestrator._recover_nested_dispatch_repairs_on_startup, _drive_nested_dispatch_repair, _preflight_nested_epic_dispatch, and durable workflow job wake/reconciliation. Tests must reproduce restart with an existing retry_wait topology row, prove exact-authority helpers retire it without attempting advance_nested_dispatch_topology, prove title-shaped helpers remain fenced, and prove implementation dispatch can then rearm. Acceptance: no retrying topology row remains for an exact helper, no direct SQLite/operator repair is needed, and the helper naturally returns to a runnable workflow decision.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 14:40
---
Implemented exact-authority retirement in both startup recovery and the post-claim race boundary. An exact epic-rebase helper now cancels its obsolete nested topology repair before any fast-forward mutation; ordinary/title-shaped tasks remain fenced. Added restart and claim-race regressions. Focused suite: 103 passed; terminal mutation and secret scans passed.
---
author: oompah
created: 2026-08-13 14:44
---
Implemented exact-helper authority retirement for legacy nested-topology repair and shutdown-safe epic event routing. Regression coverage passes (103 focused tests); PR #868 is under hosted review.
---
<!-- COMMENTS:END -->
