---
id: OOMPAH-1209
type: bug
status: In Validation
priority: 1
title: Restart reconstruction recognizes protected epic event jobs
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T03:08:42.935045Z'
updated_at: '2026-08-13T03:29:07.695682Z'
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
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-01576b227da5
    project_id: proj-14849f1b
    task_id: OOMPAH-1209
    digest: 77c1ed1c72c690108cd8989f7bb80c5f7a02f579e6601aae0e9b4a53e47c0b44
  - version: 1
    audit_id: audit-13f6c7c65d15
    project_id: proj-14849f1b
    task_id: OOMPAH-1209
    digest: 77c1ed1c72c690108cd8989f7bb80c5f7a02f579e6601aae0e9b4a53e47c0b44
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-01576b227da5
    project_id: proj-14849f1b
    task_id: OOMPAH-1209
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 77c1ed1c72c690108cd8989f7bb80c5f7a02f579e6601aae0e9b4a53e47c0b44
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T03:29:00.842683+00:00'
    eligible_at: '2026-08-13T03:29:00.842683+00:00'
    selected_ref: origin/OOMPAH-1209
    selected_sha: 6bb76c69179c43c82bc7fc2e9aaeb5398128162d
  - version: 1
    audit_id: audit-13f6c7c65d15
    project_id: proj-14849f1b
    task_id: OOMPAH-1209
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 77c1ed1c72c690108cd8989f7bb80c5f7a02f579e6601aae0e9b4a53e47c0b44
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T03:29:00.842683+00:00'
    prerequisite_audit_id: audit-01576b227da5
    selected_ref: origin/OOMPAH-1209
    selected_sha: 6bb76c69179c43c82bc7fc2e9aaeb5398128162d
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

Fix a restart-admission deadlock in epic workflow reconciliation. Startup's EpicWorkflowEventRouter may enqueue the current epic action in an epic-event:<action> lane after the shared managed cut; materialize_event intentionally supersedes the equivalent decision-lane job. Subsequent generic EpicWorkflowController reconciliation reports its managed decision job as required but not materialized even though the same action has active event-lane execution authority. Universal restart liveness remains incomplete (observed live as 20 required / 18 materialized for TRICKLE-117 and TRICKLE-127), so no workers can drain the very jobs that would resolve the cut. Scope: add a domain-safe protected-event proof/configuration for epic reconciliation and universal liveness without weakening snapshot generation or evidence fencing; relevant files include oompah/epic_workflow.py, oompah/workflow_scheduler.py, oompah/workflow_jobs.py, oompah/workflow_runtime.py, and focused tests. Acceptance: an active same-action epic-event job is counted as the current epic decision's substitute execution authority, restart reconstruction converges, workers can drain it, stale scans and different actions cannot borrow the proof, and focused workflow plus project gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 03:18
---
Reproduced the live restart deadlock with TRICKLE-117/TRICKLE-127 and implemented a domain-configured substitute proof. Generic managed scheduling now accepts only a live event job in an explicitly configured lane for the exact current action and current managed cursor; EpicWorkflowController configures epic-event:<action>. Different actions and stale cursors remain unproven. Verification: 407 workflow job/scheduler/epic/runtime tests passed, including end-to-end restart liveness; terminal-audit mutation scan passed; secret scan passed.
---
author: oompah
created: 2026-08-13 03:29
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
