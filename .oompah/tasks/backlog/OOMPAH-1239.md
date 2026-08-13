---
id: OOMPAH-1239
type: task
status: Backlog
priority: null
title: Bypass recursive topology preflight for authoritative epic-rebase helpers
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T13:08:46.480588Z'
updated_at: '2026-08-13T13:09:10.054174Z'
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
  creation_marker: 1b3db1dd-b180-4102-a9bc-eb256db75f99
  request_fingerprint: 3ed5ff688af9b0650b3f1f817da53b242acba07da3d9ef6ebdfb6c4129606c78
---
## Summary

Live scheduling bug observed after deploying OOMPAH-1237: exact-authority helper TRICKLE-141 now passes branch-pattern validation, but its implementation_start remains deferred while nested_dispatch_topology_repair reports that parent branch TRICKLE-130 has unique commits. This is a recursive deadlock: TRICKLE-141 exists specifically to rebase TRICKLE-130 onto authoritative parent epic-TRICKLE-127, so requiring that topology to already be repaired before dispatch prevents the repair. Implementation scope: in oompah/orchestrator.py, exempt only an exact server-authority-backed epic-rebase helper from ordinary nested-dispatch topology preflight while retaining authority, target, workspace, and publish validation; do not exempt ordinary nested children or forged/title-shaped tasks. Add focused regression tests in tests/test_release_pick_validation.py and/or nested-dispatch tests. Acceptance: TRICKLE-141 dispatches to the direct epic maintenance workspace; forged and ordinary nested tasks remain topology-fenced; existing topology and epic-rebase tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 13:09
---
Claimed directly from live TRICKLE-141 scheduling. Implementing the narrow exact-authority bypass now; only Trickle remains resumed.
---
<!-- COMMENTS:END -->
