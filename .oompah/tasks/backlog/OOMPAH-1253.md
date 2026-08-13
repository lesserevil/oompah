---
id: OOMPAH-1253
type: task
status: Backlog
priority: null
title: Use authoritative nested epic source branch in rebase publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T17:17:20.003713Z'
updated_at: '2026-08-13T17:17:20.003713Z'
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
  creation_marker: 6e9a3122-657b-49c8-9d6a-a03403fc29d7
  request_fingerprint: 9a265123bae3b1d83de177148e24c5f726c4024c399235059accbff9739687bb
---
## Summary

Bug: epic-rebase admission records authority against the parent epic's authoritative work_branch via _epic_branch_for_issue(), but publish_epic_rebase_candidate() and _epic_rebase_push_denial() recompute the source with project_store.epic_branch_name(). For nested Trickle epic TRICKLE-130, admission correctly leased remote TRICKLE-130 at 4493710568cd38feecde4778685bc93218db8117, while publication inspected epic-TRICKLE-130 at 7290eb7ac421f0f64bedd12000ac5aaa44dc18a6 and falsely returned epic_rebase_generation_stale. Scope: make all publication/push revalidation paths resolve the same authoritative epic source branch as admission, preserving exact generation/CAS checks. Add regression tests where an epic has work_branch different from canonical epic-<id>, proving publication observes and pushes the authoritative ref and rejects genuine changes. Run focused epic-rebase state tests plus terminal audit/secret scans. Acceptance: a scoped nested-epic helper with an unchanged leased work_branch can publish its exact candidate; wrong/stale refs remain fail-closed; TRICKLE-141 can publish candidate 734e24b8b2021511b01f329bc76bdb091817af89 after deployment.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

