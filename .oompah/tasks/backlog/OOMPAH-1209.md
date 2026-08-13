---
id: OOMPAH-1209
type: bug
status: Backlog
priority: 1
title: Restart reconstruction recognizes protected epic event jobs
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T03:08:42.935045Z'
updated_at: '2026-08-13T03:08:42.935045Z'
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
  creation_marker: restart-protected-epic-event-deadlock-v1
  request_fingerprint: 258f98e1475a715f60330cb8778b43fb138c465da15f5f965af8d8f7aa577020
---
## Summary

Fix a restart-admission deadlock in epic workflow reconciliation. Startup's EpicWorkflowEventRouter may enqueue the current epic action in an epic-event:<action> lane after the shared managed cut; materialize_event intentionally supersedes the equivalent decision-lane job. Subsequent generic EpicWorkflowController reconciliation reports its managed decision job as required but not materialized even though the same action has active event-lane execution authority. Universal restart liveness remains incomplete (observed live as 20 required / 18 materialized for TRICKLE-117 and TRICKLE-127), so no workers can drain the very jobs that would resolve the cut. Scope: add a domain-safe protected-event proof/configuration for epic reconciliation and universal liveness without weakening snapshot generation or evidence fencing; relevant files include oompah/epic_workflow.py, oompah/workflow_scheduler.py, oompah/workflow_jobs.py, oompah/workflow_runtime.py, and focused tests. Acceptance: an active same-action epic-event job is counted as the current epic decision's substitute execution authority, restart reconstruction converges, workers can drain it, stale scans and different actions cannot borrow the proof, and focused workflow plus project gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

