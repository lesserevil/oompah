---
id: OOMPAH-1236
type: task
status: Merged
priority: null
title: Unify durable epic source authority with persisted nested branches
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T12:12:00.430229Z'
updated_at: '2026-08-14T07:39:36.718797Z'
work_branch: OOMPAH-1236
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 456e97e8-3977-48c5-9043-da95629d9ced
  request_fingerprint: 24588412e8f783192162e56511e9c7c4eeb0377ce15c7f19468c4abb3905de0f
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1236
  head_sha: 15213aac3bf4f9715a6aa860bc567fa9eaea8060
  submitted_at: '2026-08-13T12:24:12.681962+00:00'
  updated_at: '2026-08-13T12:24:12.681962+00:00'
oompah.work_branch: OOMPAH-1236
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-b2a449c5a8e9
    project_id: proj-14849f1b
    task_id: OOMPAH-1236
    digest: a0a3cc0593bf3f25f7753316cc817fccf10b29f7272f98a3b7e1ed75904f805b
  - version: 1
    audit_id: audit-bead4ba7c43b
    project_id: proj-14849f1b
    task_id: OOMPAH-1236
    digest: a0a3cc0593bf3f25f7753316cc817fccf10b29f7272f98a3b7e1ed75904f805b
  oompah.terminal_override_records:
  - version: 1
    override_id: override-837c297f247b
    project_id: proj-14849f1b
    task_id: OOMPAH-1236
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a0a3cc0593bf3f25f7753316cc817fccf10b29f7272f98a3b7e1ed75904f805b
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #863 merged as c32afe078 and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:39:25.594191+00:00'
    selected_ref: 15213aac3bf4f9715a6aa860bc567fa9eaea8060
    selected_sha: 15213aac3bf4f9715a6aa860bc567fa9eaea8060
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1236
    target_state: Merged
    evidence_fingerprint: a0a3cc0593bf3f25f7753316cc817fccf10b29f7272f98a3b7e1ed75904f805b
    workflow_revision: null
    selected_ref: 15213aac3bf4f9715a6aa860bc567fa9eaea8060
    selected_sha: 15213aac3bf4f9715a6aa860bc567fa9eaea8060
    landing_revision: null
    audit_ids:
    - audit-b2a449c5a8e9
    - audit-bead4ba7c43b
    kind: override
    applied: true
    retired_at: '2026-08-14T07:39:35.585640+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b2a449c5a8e9
    project_id: proj-14849f1b
    task_id: OOMPAH-1236
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a0a3cc0593bf3f25f7753316cc817fccf10b29f7272f98a3b7e1ed75904f805b
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T12:33:49.846161+00:00'
    eligible_at: '2026-08-13T12:33:49.846161+00:00'
    selected_ref: 15213aac3bf4f9715a6aa860bc567fa9eaea8060
    selected_sha: 15213aac3bf4f9715a6aa860bc567fa9eaea8060
    updated_at: '2026-08-14T07:39:35.585592+00:00'
  - version: 1
    audit_id: audit-bead4ba7c43b
    project_id: proj-14849f1b
    task_id: OOMPAH-1236
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a0a3cc0593bf3f25f7753316cc817fccf10b29f7272f98a3b7e1ed75904f805b
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T12:33:49.846161+00:00'
    prerequisite_audit_id: audit-b2a449c5a8e9
    selected_ref: 15213aac3bf4f9715a6aa860bc567fa9eaea8060
    selected_sha: 15213aac3bf4f9715a6aa860bc567fa9eaea8060
    updated_at: '2026-08-14T07:39:35.585622+00:00'
  attempt_history: []
oompah.lifecycle_revision: 2
---
## Summary

Live scheduling bug exposed after OOMPAH-1235 created a current v2 epic-rebase job for TRICKLE-130. Nested dispatch correctly observes the persisted epic work branch TRICKLE-130 at 4493710 behind epic-TRICKLE-127, but EpicFactCollector hard-codes epic-TRICKLE-130 (already at the parent head). The durable decision therefore omits epic_rebase_repair and supersedes the helper job even though the dispatch topology remains stale. Implementation scope: establish one source-branch/head authority contract shared by EpicFactCollector, EpicWorkflowEventRouter, ProductionEpicWorkflowBackend, OrchestratorEpicWorkflowEffects, and nested-dispatch rebase request publication; preserve canonical epic-* fallback when no persisted branch exists; bind scheduling/revalidation/mutation to the exact live source head rather than a stale review head. Add regression tests with a nested epic whose persisted work_branch differs from epic-<id>, whose review_head differs from the live source ref, and whose immediate parent target has advanced. Acceptance: exactly one durable rebase helper is created for the persisted source and target, stale source/target changes fail closed, TRICKLE-138/139 topology repairs stop cycling after the helper publishes, focused epic/workflow suites and hosted CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 12:12
---
Claimed directly during live Trickle monitoring. OOMPAH-1235 successfully produced v2 job seq16476, but the job superseded because durable epic facts modeled source epic-TRICKLE-130 while nested dispatch and the tracker own persisted source TRICKLE-130. Fixing the branch/head authority split now; Oompah stays paused and only Trickle remains resumed.
---
author: oompah
created: 2026-08-13 12:23
---
Implementation complete: durable epic facts now honor persisted legacy source branches, rebase events capture source branch + exact live head + immediate target, and worker revalidation checks all three without relying on mutable collection revisions or ordinary epic decision inventory. Regression reproduces TRICKLE-130 shape. 495 focused epic/workflow tests pass; terminal mutation and secret scans pass.
---
author: oompah
created: 2026-08-13 12:24
---
Unify persisted epic source authority and exact-head-fence durable rebase requests; 495 focused tests and repository scans pass.
---
author: oompah
created: 2026-08-13 12:33
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 07:39
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner convergence: PR #863 merged as c32afe078 and that landed tree is contained by origin/main; this stale non-terminal projection requires no further implementation.
---
<!-- COMMENTS:END -->
