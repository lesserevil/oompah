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
updated_at: '2026-08-12T23:52:33.735926Z'
work_branch: OOMPAH-1193
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
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1193
  head_sha: 1744e1cf730bae9b846ad850bdd1808d9563831c
  submitted_at: '2026-08-12T23:52:25.331593+00:00'
  updated_at: '2026-08-12T23:52:25.331593+00:00'
oompah.work_branch: OOMPAH-1193
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
author: oompah
created: 2026-08-12 23:30
---
Safety refinement pushed in 1744e1cf: immediate restart continuation is now limited to reports with an explicitly truncated workflow domain. Incomplete scans caused by source or authority read errors do not self-requeue, preserving normal retry backoff and preventing a hot loop. Focused restart tests: 5 passed; workflow retirement/runtime tests: 195 passed. Exact-head complete gate and Python 3.11/3.12/3.13 CI are running.
---
author: oompah
created: 2026-08-12 23:52
---
Implemented bounded restart-reconstruction continuation with audit-first admission ordering; guarded source failures from immediate retry loops. Focused 195-test workflow suite, complete 20,185-test gate, and Python 3.11/3.12/3.13 CI pass.
---
<!-- COMMENTS:END -->
