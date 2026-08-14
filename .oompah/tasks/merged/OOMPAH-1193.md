---
id: OOMPAH-1193
type: task
status: Merged
priority: null
title: Continue truncated restart reconstruction before worker admission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T23:19:53.793903Z'
updated_at: '2026-08-14T07:30:08.567431Z'
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
oompah.lifecycle_revision: 3
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
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-a6664a85ce2c
    project_id: proj-14849f1b
    task_id: OOMPAH-1193
    digest: 4f0f7ab63e0f00033ae3ef03651752a6f3431fe453d7da598638c3544ca51c14
  - version: 1
    audit_id: audit-c9ab6a47dfc7
    project_id: proj-14849f1b
    task_id: OOMPAH-1193
    digest: 4f0f7ab63e0f00033ae3ef03651752a6f3431fe453d7da598638c3544ca51c14
  oompah.terminal_override_records:
  - version: 1
    override_id: override-df507cff3fda
    project_id: proj-14849f1b
    task_id: OOMPAH-1193
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4f0f7ab63e0f00033ae3ef03651752a6f3431fe453d7da598638c3544ca51c14
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #841 merged as f8bb14cdc and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:29:58.453995+00:00'
    selected_ref: 1744e1cf730bae9b846ad850bdd1808d9563831c
    selected_sha: 1744e1cf730bae9b846ad850bdd1808d9563831c
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1193
    target_state: Merged
    evidence_fingerprint: 4f0f7ab63e0f00033ae3ef03651752a6f3431fe453d7da598638c3544ca51c14
    workflow_revision: null
    selected_ref: 1744e1cf730bae9b846ad850bdd1808d9563831c
    selected_sha: 1744e1cf730bae9b846ad850bdd1808d9563831c
    landing_revision: null
    audit_ids:
    - audit-a6664a85ce2c
    - audit-c9ab6a47dfc7
    kind: override
    applied: true
    retired_at: '2026-08-14T07:30:07.395295+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a6664a85ce2c
    project_id: proj-14849f1b
    task_id: OOMPAH-1193
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4f0f7ab63e0f00033ae3ef03651752a6f3431fe453d7da598638c3544ca51c14
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-12T23:53:24.668045+00:00'
    eligible_at: '2026-08-12T23:53:24.668045+00:00'
    selected_ref: 1744e1cf730bae9b846ad850bdd1808d9563831c
    selected_sha: 1744e1cf730bae9b846ad850bdd1808d9563831c
    updated_at: '2026-08-14T07:30:07.395244+00:00'
  - version: 1
    audit_id: audit-c9ab6a47dfc7
    project_id: proj-14849f1b
    task_id: OOMPAH-1193
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4f0f7ab63e0f00033ae3ef03651752a6f3431fe453d7da598638c3544ca51c14
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-12T23:53:24.668045+00:00'
    prerequisite_audit_id: audit-a6664a85ce2c
    selected_ref: 1744e1cf730bae9b846ad850bdd1808d9563831c
    selected_sha: 1744e1cf730bae9b846ad850bdd1808d9563831c
    updated_at: '2026-08-14T07:30:07.395275+00:00'
  attempt_history: []
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
author: oompah
created: 2026-08-12 23:53
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 07:30
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner convergence: PR #841 merged as f8bb14cdc and that landed tree is contained by origin/main; this stale non-terminal projection requires no further implementation.
---
<!-- COMMENTS:END -->
