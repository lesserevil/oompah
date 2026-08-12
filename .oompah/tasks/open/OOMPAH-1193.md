---
id: OOMPAH-1193
type: task
status: Open
priority: null
title: Continue truncated restart reconstruction before worker admission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T23:19:53.793903Z'
updated_at: '2026-08-12T23:20:28.142733Z'
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
  creation_marker: 75888359-5bee-46fc-b1ce-ff1e9f0b0769
  request_fingerprint: d14c77f040ab8fb1e911e1c3f202433dd4507180144720fc99796278236e6765
oompah.lifecycle_revision: 1
---
## Summary

Fix a scheduler deadlock in the durable workflow restart boundary. When reconcile_async(admit_workers=False) publishes a truncated or incomplete liveness cut without requires_reconcile=true, Orchestrator._run_restart_reconstruction_tick leaves restart_reconstruction_pending true but does not request a continuation, so resumed projects can remain indefinitely with worker admission deferred. Update the restart path to enqueue a coalesced workflow reconciliation continuation whenever restart reconstruction remains pending after a reconciliation cut. Preserve audit-before-worker ordering and avoid admitting workers until the complete cut publishes. Add regression tests covering an incomplete cut, continuation request, subsequent convergence, and admission ordering. Run focused orchestrator/runtime tests and the complete Makefile gate. Acceptance: a resumed project with more restart work than one cut can automatically advance through additional cuts and begin eligible worker admission without waiting for an unrelated poll or operator action.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 23:20
---
Live reproduction on build 81c63ce5: Trickle generation 6315 reported implementation truncated=false with 17/17 schedules materialized, integration truncated=true with 0/2 schedules materialized, epic truncated=true with 1/3 schedules materialized, liveness scan_complete=false, and worker admission deferred. workflow_reconcile_continuation_requested remained false. Trickle was paused before implementing the hotfix; all other projects were already paused.
---
<!-- COMMENTS:END -->
