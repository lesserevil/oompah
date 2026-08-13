---
id: OOMPAH-1242
type: task
status: Backlog
priority: null
title: Retire nested topology repair when exact rebase helper owns the branch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T14:32:41.192085Z'
updated_at: '2026-08-13T14:32:41.192085Z'
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
  creation_marker: 17b045c2-9045-4892-be53-3eac67d25256
  request_fingerprint: 4e8f025d5976a94cb2d61527c19326a04aac0e16daf6d281733a3e92c80ba605
---
## Summary

Scope: fix restart recovery and durable nested-dispatch repair execution so an exact server-authorized epic-rebase helper never remains blocked by, or keeps retrying, an ordinary nested topology fast-forward repair for the branch it exclusively owns. Current live reproduction: TRICKLE-141 gained exact rebase authority for persisted source TRICKLE-130, but workflow job 16757 remained retry_wait because startup recovery calls raw topology collection and reports unique commits. Update the recovery/claim paths to revalidate exact helper publish authority and atomically cancel or supersede obsolete topology jobs before implementation admission. Relevant code: Orchestrator._recover_nested_dispatch_repairs_on_startup, _drive_nested_dispatch_repair, _preflight_nested_epic_dispatch, and durable workflow job wake/reconciliation. Tests must reproduce restart with an existing retry_wait topology row, prove exact-authority helpers retire it without attempting advance_nested_dispatch_topology, prove title-shaped helpers remain fenced, and prove implementation dispatch can then rearm. Acceptance: no retrying topology row remains for an exact helper, no direct SQLite/operator repair is needed, and the helper naturally returns to a runnable workflow decision.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

