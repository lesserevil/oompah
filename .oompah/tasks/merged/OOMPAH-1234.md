---
id: OOMPAH-1234
type: task
status: Merged
priority: null
title: Wake queued nested topology repairs independently of implementation retry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T11:02:41.641589Z'
updated_at: '2026-08-14T07:39:03.443354Z'
work_branch: OOMPAH-1234
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: cd7a3378-bd51-43b7-a1c4-f5b7ee908979
  request_fingerprint: 77a790dd37017add0acfd675dc561e5750a30bcfb90c6a44ed4551f6572ecedb
oompah.lifecycle_revision: 3
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1234
  head_sha: c3a50bc6c4df16d3c52aaf1110e50a2e502521e8
  submitted_at: '2026-08-13T11:15:42.599789+00:00'
  updated_at: '2026-08-13T11:15:42.599789+00:00'
oompah.work_branch: OOMPAH-1234
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-46ed92492658
    project_id: proj-14849f1b
    task_id: OOMPAH-1234
    digest: 1a4f8b1e10a129013da0bfbe60bf0468d921f838095cbc9b1ca455ccafa4f042
  - version: 1
    audit_id: audit-3e3f86066e49
    project_id: proj-14849f1b
    task_id: OOMPAH-1234
    digest: 1a4f8b1e10a129013da0bfbe60bf0468d921f838095cbc9b1ca455ccafa4f042
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7f9e7e0f917b
    project_id: proj-14849f1b
    task_id: OOMPAH-1234
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1a4f8b1e10a129013da0bfbe60bf0468d921f838095cbc9b1ca455ccafa4f042
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #861 merged as f16b042c1 and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:38:54.405692+00:00'
    selected_ref: c3a50bc6c4df16d3c52aaf1110e50a2e502521e8
    selected_sha: c3a50bc6c4df16d3c52aaf1110e50a2e502521e8
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1234
    target_state: Merged
    evidence_fingerprint: 1a4f8b1e10a129013da0bfbe60bf0468d921f838095cbc9b1ca455ccafa4f042
    workflow_revision: null
    selected_ref: c3a50bc6c4df16d3c52aaf1110e50a2e502521e8
    selected_sha: c3a50bc6c4df16d3c52aaf1110e50a2e502521e8
    landing_revision: null
    audit_ids:
    - audit-46ed92492658
    - audit-3e3f86066e49
    kind: override
    applied: true
    retired_at: '2026-08-14T07:39:02.230802+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-46ed92492658
    project_id: proj-14849f1b
    task_id: OOMPAH-1234
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1a4f8b1e10a129013da0bfbe60bf0468d921f838095cbc9b1ca455ccafa4f042
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T11:34:51.842598+00:00'
    eligible_at: '2026-08-13T11:34:51.842598+00:00'
    selected_ref: c3a50bc6c4df16d3c52aaf1110e50a2e502521e8
    selected_sha: c3a50bc6c4df16d3c52aaf1110e50a2e502521e8
    updated_at: '2026-08-14T07:39:02.230754+00:00'
  - version: 1
    audit_id: audit-3e3f86066e49
    project_id: proj-14849f1b
    task_id: OOMPAH-1234
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1a4f8b1e10a129013da0bfbe60bf0468d921f838095cbc9b1ca455ccafa4f042
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-13T11:34:51.842598+00:00'
    prerequisite_audit_id: audit-46ed92492658
    selected_ref: c3a50bc6c4df16d3c52aaf1110e50a2e502521e8
    selected_sha: c3a50bc6c4df16d3c52aaf1110e50a2e502521e8
    updated_at: '2026-08-14T07:39:02.230783+00:00'
  attempt_history: []
---
## Summary

Live follow-up to OOMPAH-1232 on TRICKLE-138/139. OOMPAH-1232 breaks the in-call implementation-versus-repair exclusion deadlock for new admissions, but repair jobs already queued before deployment have no independent consumer and remain dormant until their associated implementation_start retry_at, which may be hours away after repeated administrative deferrals. Implementation scope: add a bounded, project-pause-aware recovery sweep for active nested_dispatch_topology_repair jobs; reload the exact task and current topology evidence, use the existing generation-fenced schedule/drive path, persist cleared wait evidence after a successful repair, and request ordinary reconciliation so the obsolete implementation retry is superseded by the new task evidence. Do not bypass task/project pause, do not claim unrelated actions, do not overlap an unapproved running action, and preserve repair retry backoff/errors. Required tests: queued repair is driven without a due implementation job; successful repair clears wait evidence and triggers reconciliation/new authority; paused project is untouched; stale generation is superseded safely; bounded batch/restart replay is idempotent; unrelated workflow rows unchanged. Acceptance: a pre-deployment TRICKLE-138/139-shaped queued repair progresses promptly after startup without waiting for the inherited implementation retry deadline, and focused topology/workflow/runtime plus complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 11:02
---
Claimed directly after live verification of OOMPAH-1232. The deployed overlap fix handles new admissions, but pre-existing queued repairs need a bounded independent startup/maintenance wake. Implementing that recovery path now while Oompah remains paused and only Trickle is resumed.
---
author: oompah
created: 2026-08-13 11:15
---
Implementation complete on OOMPAH-1234 at c3a50bc6c. Added bounded startup replay for queued nested topology repairs, pause/backoff/generation fencing, and stabilized initial wait authority before enqueue. Focused topology/job/runtime/architecture suite: 335 passed. Terminal mutation and secret scans passed. Submitting for validation.
---
author: oompah
created: 2026-08-13 11:15
---
Recover queued nested topology repairs independently at startup with pause/backoff/generation fencing; stabilize wait authority before enqueue. 335 focused tests and repository scans pass.
---
author: oompah
created: 2026-08-13 11:34
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 07:39
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner convergence: PR #861 merged as f16b042c1 and that landed tree is contained by origin/main; this stale non-terminal projection requires no further implementation.
---
<!-- COMMENTS:END -->
