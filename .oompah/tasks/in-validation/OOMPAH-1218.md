---
id: OOMPAH-1218
type: task
status: In Validation
priority: null
title: Bind implementation status transitions to the runtime assignment generation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T04:05:12.348049Z'
updated_at: '2026-08-13T04:20:36.540209Z'
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
  creation_marker: 66453f65-1c85-4433-8a62-ff21f1ab7692
  request_fingerprint: 6542d304c132be47711a84d6318b1765ff5b184392b0e5f9fa3f7fab496bbda0
oompah.lifecycle_revision: 2
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-3f52d7fe7d46
    project_id: proj-14849f1b
    task_id: OOMPAH-1218
    digest: 6f7fbc4acb15103753351c80143989af0e0d85c135031c14e997d1a2c5ac5cb7
  - version: 1
    audit_id: audit-d06e612135af
    project_id: proj-14849f1b
    task_id: OOMPAH-1218
    digest: 6f7fbc4acb15103753351c80143989af0e0d85c135031c14e997d1a2c5ac5cb7
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-3f52d7fe7d46
    project_id: proj-14849f1b
    task_id: OOMPAH-1218
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6f7fbc4acb15103753351c80143989af0e0d85c135031c14e997d1a2c5ac5cb7
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T04:20:31.097992+00:00'
    eligible_at: '2026-08-13T04:20:31.097992+00:00'
    selected_ref: origin/OOMPAH-1218
    selected_sha: 212cf88af1f4bd163fd68c8a9812472a5d9e7e9b
  - version: 1
    audit_id: audit-d06e612135af
    project_id: proj-14849f1b
    task_id: OOMPAH-1218
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6f7fbc4acb15103753351c80143989af0e0d85c135031c14e997d1a2c5ac5cb7
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T04:20:31.097992+00:00'
    prerequisite_audit_id: audit-3f52d7fe7d46
    selected_ref: origin/OOMPAH-1218
    selected_sha: 212cf88af1f4bd163fd68c8a9812472a5d9e7e9b
  attempt_history: []
---
## Summary

### Problem

A durable implementation_start or implementation_recovery job launches an agent and records the newly allocated tracker assignment_id in its exact ImplementationDisposition, but ProductionImplementationWorkflowBackend.build_transition sends the older workflow job generation as TransitionIntent.evidence_generation. TaskTransitionService compares that value to the live assignment_id and rejects Open → In Progress with transition.generation_mismatch. The agent then runs while the task remains Open. When it submits, Open → Ready to Integrate is rejected as transition.illegal_edge, the validation job exhausts, and the task is re-dispatched.

Live evidence on Trickle after deploying 9401a3f752e11c5ff504efba175de35ff5b14c5c: TRICKLE-118, TRICKLE-119, and TRICKLE-140 all showed this sequence in task_transitions.sqlite3. Running agents were visible while their tasks remained Open.

### Implementation scope

Update the production implementation workflow adapter so START, RECOVERY, and FOCUS_HANDOFF status transitions carry the exact assignment generation proven by the verified ImplementationDisposition. Retain the immutable workflow job generation as originating-job authority; do not weaken project/task/job fencing. Define fail-closed behavior when the action requires an assignment but the verified disposition lacks one. Ensure validation submission carries the current accepted implementation/direct-owner assignment identity so a successfully submitted Open task cannot arise from this race.

Relevant files:
- oompah/implementation_workflow_adapter.py
- oompah/task_transition_service.py only if a narrow compatibility change is demonstrably required
- tests/test_implementation_workflow_adapter.py
- focused task-transition/worker tests as needed

### Required tests

- A START launch whose runtime assignment_id differs from the workflow job generation transitions Open → In Progress successfully using the assignment_id.
- RECOVERY and FOCUS_HANDOFF use the same exact assignment proof.
- A mismatched replacement assignment remains rejected.
- A missing required assignment fails closed before tracker mutation.
- A later VALIDATION_SUBMISSION transitions the same task from In Progress → Ready to Integrate and does not exhaust as transition.illegal_edge.
- Direct-owner claim/restart submission behavior remains unchanged.

### Acceptance criteria

- Running implementation agents have matching In Progress task state.
- Successful submissions are not rejected because the launch status remained Open.
- No weakening of generation, project, task, accepted-head, or transition-journal fencing.
- Focused tests and the complete Makefile quality gate pass.
- The reviewed change is merged to main and deployed before Trickle is considered healthy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 04:10
---
Root cause confirmed and patch implemented. START/RECOVERY/FOCUS_HANDOFF now derive transition evidence from the exact verified runtime assignment; validation submission uses the immutable captured assignment (with live assignment fallback). Real TaskTransitionService regressions prove Open → In Progress and In Progress → Ready to Integrate succeed while missing assignment fails closed. Full implementation adapter suite: 67 passed.
---
author: oompah
created: 2026-08-13 04:20
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
