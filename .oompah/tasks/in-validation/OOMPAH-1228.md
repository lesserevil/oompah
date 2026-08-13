---
id: OOMPAH-1228
type: task
status: In Validation
priority: null
title: Allow landed deleted-source submissions through validation commit guard
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T09:30:46.069410Z'
updated_at: '2026-08-13T09:52:38.333155Z'
work_branch: OOMPAH-1228
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 8da572d7-f464-44ad-807b-2ac8e3eca989
  request_fingerprint: 6799d0fc8aba0cd3563e447d80c1c8678cd66345d3a948da7c52f7f343ecb250
oompah.lifecycle_revision: 2
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1228
  head_sha: 1e9c15be1b1e25c99d15c4fd593d8af32b071173
  submitted_at: '2026-08-13T09:51:45.485359+00:00'
  updated_at: '2026-08-13T09:51:45.485359+00:00'
oompah.work_branch: OOMPAH-1228
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-793e9794c569
    project_id: proj-14849f1b
    task_id: OOMPAH-1228
    digest: b3241f20ea13be00acab5c31e9141532e49716c23976b505e47f2bc3fee350cd
  - version: 1
    audit_id: audit-80f7ee30a3f4
    project_id: proj-14849f1b
    task_id: OOMPAH-1228
    digest: b3241f20ea13be00acab5c31e9141532e49716c23976b505e47f2bc3fee350cd
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-793e9794c569
    project_id: proj-14849f1b
    task_id: OOMPAH-1228
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b3241f20ea13be00acab5c31e9141532e49716c23976b505e47f2bc3fee350cd
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T09:52:25.754829+00:00'
    eligible_at: '2026-08-13T09:52:25.754829+00:00'
    selected_ref: 1e9c15be1b1e25c99d15c4fd593d8af32b071173
    selected_sha: 1e9c15be1b1e25c99d15c4fd593d8af32b071173
  - version: 1
    audit_id: audit-80f7ee30a3f4
    project_id: proj-14849f1b
    task_id: OOMPAH-1228
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b3241f20ea13be00acab5c31e9141532e49716c23976b505e47f2bc3fee350cd
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T09:52:25.754829+00:00'
    prerequisite_audit_id: audit-793e9794c569
    selected_ref: 1e9c15be1b1e25c99d15c4fd593d8af32b071173
    selected_sha: 1e9c15be1b1e25c99d15c4fd593d8af32b071173
  attempt_history: []
---
## Summary

Bug observed live after deploying OOMPAH-1226. TRICKLE-140's accepted head is exactly contained in GitLab main and its source branch was normally deleted after merge. Reconciliation now correctly schedules validation_submission instead of implementation_recovery, but Orchestrator._validation_submission_transition_conflict requires project_store.remote_branch_head(source) == expected_head at commit time. That invariant cannot hold for the proven landed/deleted-source route, so the validation transition repeatedly fails (live rows 16019/16020) and retry exhaustion strands the task in In Progress. Scope: extend the commit-time mutation guard to accept either an exact current source head or exact immutable containment of the accepted head in the stable accepted target branch; retain project/task/head/target/owner fencing and fail closed when source/target evidence is unavailable or changed. Ensure guard exceptions are logged with safe context before returning transition.mutation_guard_failed so future failures are diagnosable. Add tests reproducing deleted-source+target-contained success, deleted-source+not-contained failure, source-advanced failure, target mismatch/unavailable failure, and the full validation transition path. Acceptance: TRICKLE-140 advances naturally from In Progress without an implementer, validation retry growth stops, alerts clear after a successful successor generation, focused transition/workflow tests and hosted Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 09:31
---
Claimed directly for live TRICKLE-140 recovery. OOMPAH-1226 stopped implementation recovery churn (646 historical rows; no additions after 09:23:39) and routed the task into validation_submission. The commit guard then exhausted because it still requires the deleted source ref instead of accepting exact target containment. Implementing the missing commit-time route now.
---
author: oompah
created: 2026-08-13 09:37
---
Implementation pushed as PR #857. The commit-time validation guard accepts exact target containment only when the accepted source ref is absent; source advancement, target drift, missing/non-contained target proof, and owner/assignment changes remain blocked. Guard exceptions now retain a traceback in logs. Focused transition/runtime verification: 450 passed. Hosted gates are running.
---
author: oompah
created: 2026-08-13 09:51
---
Permit a deleted accepted source branch through validation only when the exact accepted head is contained by the authoritative target branch, while preserving fail-closed behavior for drift and unavailable evidence. Mutation-guard exceptions are now logged. Focused tests and hosted CI on Python 3.11, 3.12, and 3.13 pass.
---
author: oompah
created: 2026-08-13 09:52
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
