---
id: OOMPAH-1255
type: task
status: Backlog
priority: null
title: Stamp native sibling scope before noncanonical rebase authority selection
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T18:13:35.579127Z'
updated_at: '2026-08-13T18:13:35.579127Z'
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
  creation_marker: cbca0849-a742-4e96-9196-41c398ed2525
  request_fingerprint: 9787e58516647b17cd2bb7f697947ea7aa802671f8dc89dd12f0f358a4da8aef
---
## Summary

Bug exposed live by TRICKLE-141 after OOMPAH-1253 deployed. publish_epic_rebase_candidate correctly resolves durable authority task_id=TRICKLE-141 and authoritative source branch TRICKLE-130, but _active_epic_rebase_siblings reloads native Markdown tasks whose Issue.project_id is unset. _is_epic_rebase_task therefore cannot consult the project-scoped durable authority, falls back to the canonical epic-TRICKLE-130 title convention, excludes the actual noncanonical helper, and publication falsely returns epic_rebase_duplicate_authority with an empty winner set. Scope: stamp the known epic/project identity on tracker-backed child and active-pool candidates before project-scoped classification/ownership checks, without accepting conflicting non-empty scope; cover native unscoped helper discovery, conflicting scope rejection, noncanonical source authority selection, and publisher success regression. Acceptance: the sole live helper named by durable authority remains the winner after native reload and TRICKLE-141 can publish its exact candidate through the server.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

