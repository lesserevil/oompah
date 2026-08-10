---
id: OOMPAH-960
type: bug
status: Done
priority: 1
title: Consume parent-scoped canonical child landing facts
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T14:20:14.654158Z'
updated_at: '2026-08-10T01:13:53.072633Z'
work_branch: OOMPAH-960
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-960
  base_branch: epic-OOMPAH-940
  base_sha: 2dd74be288b81265ea4a242d7467ecc1ed9f1435
  head_sha: b3053aab9216b2a1ca79dba786506743074de15a
  submitted_at: '2026-08-09T14:37:07.918704+00:00'
  updated_at: '2026-08-09T14:37:07.918704+00:00'
oompah.work_branch: OOMPAH-960
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-238e0152c0f7
    project_id: proj-14849f1b
    task_id: OOMPAH-960
    digest: d33a6fca24b673436320d89579f05cce62bdf744df5e410c9d75d377aec066c5
  - version: 1
    audit_id: audit-46a2afc4967a
    project_id: proj-14849f1b
    task_id: OOMPAH-960
    digest: d33a6fca24b673436320d89579f05cce62bdf744df5e410c9d75d377aec066c5
  oompah.terminal_override_records:
  - version: 1
    override_id: override-495ea77a0b19
    project_id: proj-14849f1b
    task_id: OOMPAH-960
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d33a6fca24b673436320d89579f05cce62bdf744df5e410c9d75d377aec066c5
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct-owner head b9db677d1 was independently reviewed with no blockers,
      passed 193 focused integration/store tests and hosted Python 3.11/3.12/3.13
      gates, and is tree-identical to squash merge be4ec5d95 on current main. The
      service is quiesced for a graceful cutover, so the normal Open workflow transition
      cannot be generated; record the already-verified terminal result without waiting
      for the old runtime.
    created_at: '2026-08-09T15:31:20.978205+00:00'
    selected_ref: b3053aab9216b2a1ca79dba786506743074de15a
    selected_sha: b3053aab9216b2a1ca79dba786506743074de15a
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-960
    target_state: Done
    evidence_fingerprint: d33a6fca24b673436320d89579f05cce62bdf744df5e410c9d75d377aec066c5
    audit_ids:
    - audit-238e0152c0f7
    - audit-46a2afc4967a
    kind: override
    applied: true
    retired_at: '2026-08-09T15:31:30.701578+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Historical audited Done work is complete, but current parent-landing evidence
      cannot be reconstructed safely enough to promote it to Merged; retain immutable
      terminal provenance and retire reassessment.
    marked_at: '2026-08-10T01:13:51.586683+00:00'
    updated_at: '2026-08-10T01:13:51.586683+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Historical audited Done work is complete, but current parent-landing
        evidence cannot be reconstructed safely enough to promote it to Merged; retain
        immutable terminal provenance and retire reassessment.
      recorded_at: '2026-08-10T01:13:51.586683+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-238e0152c0f7
    project_id: proj-14849f1b
    task_id: OOMPAH-960
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d33a6fca24b673436320d89579f05cce62bdf744df5e410c9d75d377aec066c5
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-09T15:31:13.169796+00:00'
    selected_ref: b3053aab9216b2a1ca79dba786506743074de15a
    selected_sha: b3053aab9216b2a1ca79dba786506743074de15a
    updated_at: '2026-08-09T15:31:30.701534+00:00'
  - version: 1
    audit_id: audit-46a2afc4967a
    project_id: proj-14849f1b
    task_id: OOMPAH-960
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d33a6fca24b673436320d89579f05cce62bdf744df5e410c9d75d377aec066c5
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-09T15:31:13.169796+00:00'
    selected_ref: b3053aab9216b2a1ca79dba786506743074de15a
    selected_sha: b3053aab9216b2a1ca79dba786506743074de15a
    updated_at: '2026-08-09T15:31:30.701563+00:00'
  attempt_history: []
---
## Summary

Fix integration/Done decision evidence composition so a child task can consume its parent epic scoped canonical landing fact when that fact names the child as its source. Current production evidence shows at least 23 Done tasks have exact durable LANDED facts under the parent task_id but IntegrationLandingRequestResolver and IntegrationWorkflowController only read facts under the child task_id, causing false retry.exhausted decisions. Scope the change to the landing fact resolver/controller and durable fact queries; import only route-bound, source-matching, revision-current facts and preserve fail-closed behavior for ambiguous, stale, foreign-project, or non-contained evidence. Add regression tests for accepted parent-scoped child proof, stale/wrong-source/wrong-route rejection, current target containment, restart persistence, and no regression to epic cleanup composition. Acceptance: the 23 known affected tasks converge without operator reconstruction after deployment, no ambiguous evidence is promoted, focused tests and the configured branch gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 14:22
---
Direct-owner implementation started in isolated worktree /home/shedwards/src/oompah-960 on branch OOMPAH-960. I am adding fail-closed parent-scoped child landing evidence composition and focused route/source/revision/current-containment/restart regressions; no service mutation or deployment. The Open to In Progress CLI transition was correctly rejected because the workflow generation is required, so implementation proceeds under the explicit owner assignment while preserving tracker fencing.
---
author: oompah
created: 2026-08-09 14:35
---
Implemented fail-closed parent-scoped canonical child landing consumption in the isolated OOMPAH-960 worktree. A Done child now imports only one durable LANDED fact owned by its current parent epic when current direct containment, project, exact route, source, and any named revision agree; the Git collector still revalidates current target history, and the parent fact remains parent-owned across restart. Validation so far: 113 integration workflow tests passed; 91 epic workflow/adapter tests passed; terminal mutation scan and paranoid secret scan passed. Preparing the review-ready commit and push; no service mutation or deployment.
---
author: oompah
created: 2026-08-09 14:37
---
Implemented parent-scoped canonical child landing consumption with fail-closed current containment, project, source, route, revision, ambiguity, and current-target-history validation. Parent evidence remains parent-owned and survives restart. Pushed b3053aab9216b2a1ca79dba786506743074de15a; 113 integration workflow tests and 91 epic workflow tests passed, plus terminal mutation and secret scans.
---
author: oompah
created: 2026-08-09 14:59
---
Independent exact-head review found and corrected a >1000-parent-fact starvation boundary: the resolver now uses an indexed exact source/target durable fact query instead of a lexically truncated all-pairs scan, while retaining fail-closed foreign, corrupt, and ambiguous evidence handling. Added a 1000-earlier-distractor regression. Pushed b9db677d1c4736a9c976c9a4ae3f8be33a9c071b. Validation: 10 focused parent-scope tests passed; integration + workflow store suites 193 passed; task-status mutation and secret scans passed. Hosted exact-head checks will rerun on PR #768.
---
author: oompah
created: 2026-08-09 15:31
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 15:31
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct-owner head b9db677d1 was independently reviewed with no blockers, passed 193 focused integration/store tests and hosted Python 3.11/3.12/3.13 gates, and is tree-identical to squash merge be4ec5d95 on current main. The service is quiesced for a graceful cutover, so the normal Open workflow transition cannot be generated; record the already-verified terminal result without waiting for the old runtime.
---
<!-- COMMENTS:END -->
