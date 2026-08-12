---
id: OOMPAH-1192
type: task
status: Backlog
priority: null
title: Allow durable workflow START to publish runtime before its status transition
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T22:43:52.044640Z'
updated_at: '2026-08-12T22:44:05.655913Z'
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
  creation_marker: b17dd9ae-fd84-4b5c-aef8-36b5f938a21d
  request_fingerprint: 3e7a6e731a0e094248063262aa779f0695cd5a17277458467868e8239b1b3a66
---
## Summary

Live Trickle scheduling on merged OOMPAH-1189/1190 reaches authenticated native state-branch claim persistence, but every durable ImplementationAction.START aborts before provider admission with durable claim evidence did not converge (status Open expected In Progress, assignment_match true). The durable workflow intentionally calls Orchestrator._dispatch with status_managed_by_workflow=True and applies the journaled Open -> In Progress transition only after execution verification; _dispatch nevertheless enforces In Progress in its immediate post-claim reread, creating an impossible ordering and compensating the assignment back to Open. Scope: make _dispatch validate the correct source-status/assignment evidence when the durable workflow owns the later status transition, while retaining exact assignment, terminal/direct-owner, and stale-status fences; ensure non-workflow dispatches still require In Progress before provider admission. Relevant files: oompah/orchestrator.py, oompah/implementation_workflow_adapter.py, and focused tests. Acceptance: a real durable START from Open persists the exact assignment, publishes one running generation, then transitions to In Progress through the workflow journal; external status/assignment races still abort with zero provider starts; legacy direct dispatch behavior is unchanged; focused tests and complete CI pass; fix merged and deployed before Trickle is resumed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 22:44
---
Direct owner is implementing from live evidence. Trickle has been paused to stop retry churn. Observed affected tasks include TRICKLE-123, 124, 131, 132, 134, 135, 137, 119, 121, 122, and 118; all ordinary starts aborted before provider admission and compensation restored Open. The original state-branch transport failure is no longer present.
---
<!-- COMMENTS:END -->
