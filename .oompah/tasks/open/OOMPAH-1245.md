---
id: OOMPAH-1245
type: task
status: Open
priority: null
title: Let durable recovery supersede stale legacy completion fences
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T14:50:06.067428Z'
updated_at: '2026-08-13T14:50:23.195139Z'
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
  creation_marker: bb86dbc1-ab9d-4037-9411-584095a6a09e
  request_fingerprint: 1e18cd3b9004114671d1096d0b56bd194ec13a61fee1e22960cc1cb9455ab236
oompah.lifecycle_revision: 1
---
## Summary

Scope: fix the split-brain admission path where durable workflow facts schedule implementation_recovery for an orphaned In Progress task, but Orchestrator._should_dispatch rejects the exact recovery because the task ID remains in the legacy in-memory state.completed set. Live reproduction: TRICKLE-141 produced a valid local rebase candidate but could not publish it; after its worker exited, canonical state remained In Progress with no owner, implementation_recovery jobs 16837/16838 exhausted and 16842 retried with reason completed. Make exact durable recovery atomically clear or bypass only a demonstrably stale completed fence after fresh tracker/ownership revalidation; preserve the fence for terminal state, accepted submission, active owner/agent, and ordinary duplicate dispatch. Relevant code: implementation_workflow_adapter._admit_dispatch, Orchestrator._should_dispatch, watchdog stale-completed cleanup, and workflow recovery tests. Add regression coverage reproducing In Progress + no live owner + state.completed, proving recovery admission proceeds, while completed work with authoritative handoff remains fenced. Acceptance: no repeated implementation_recovery rows fail solely with completed for an ownerless In Progress task; the task either resumes with a scoped worker or transitions through its authoritative completion path without operator database repair.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 14:50
---
Live evidence: TRICKLE-141 is canonical In Progress with no running agent; work decision schedules implementation_recovery, while jobs 16837 and 16838 exhausted and 16842 retried because _should_dispatch returned completed. The previous worker left rebased candidate 26bfa49ab18e34ce6660fcf62ef910a37a79fcbd on local TRICKLE-130 after scoped publish capability was unavailable.
---
<!-- COMMENTS:END -->
