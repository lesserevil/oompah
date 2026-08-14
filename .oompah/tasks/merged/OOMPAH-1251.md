---
id: OOMPAH-1251
type: task
status: Merged
priority: null
title: Stamp managed project identity before epic-rebase publication validation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T16:48:58.587882Z'
updated_at: '2026-08-14T07:42:28.808078Z'
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
  creation_marker: 1fb37386-cda6-43db-ac5e-a6cc1ffdc511
  request_fingerprint: caf380e44c9b5dcf815fd050077d9d43b644994ec1446183ffd6acc0d4ed31f1
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-e668c65e1ce3
    project_id: proj-14849f1b
    task_id: OOMPAH-1251
    digest: b68758816ecef626e0a1f7fc312f8689f342b4656126a86582266592cfd8b545
  - version: 1
    audit_id: audit-5c204457718b
    project_id: proj-14849f1b
    task_id: OOMPAH-1251
    digest: b68758816ecef626e0a1f7fc312f8689f342b4656126a86582266592cfd8b545
  oompah.terminal_override_records:
  - version: 1
    override_id: override-18921417aa8b
    project_id: proj-14849f1b
    task_id: OOMPAH-1251
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b68758816ecef626e0a1f7fc312f8689f342b4656126a86582266592cfd8b545
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #871 merged as eba3ba84a and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:42:19.969935+00:00'
    selected_ref: origin/main
    selected_sha: eba3ba84ac1e1f8cc576a9b546e28743e64c209d
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1251
    target_state: Merged
    evidence_fingerprint: b68758816ecef626e0a1f7fc312f8689f342b4656126a86582266592cfd8b545
    workflow_revision: null
    selected_ref: origin/main
    selected_sha: eba3ba84ac1e1f8cc576a9b546e28743e64c209d
    landing_revision: null
    audit_ids:
    - audit-e668c65e1ce3
    - audit-5c204457718b
    kind: override
    applied: true
    retired_at: '2026-08-14T07:42:27.624645+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e668c65e1ce3
    project_id: proj-14849f1b
    task_id: OOMPAH-1251
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b68758816ecef626e0a1f7fc312f8689f342b4656126a86582266592cfd8b545
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T17:04:16.066848+00:00'
    eligible_at: '2026-08-13T17:04:16.066848+00:00'
    selected_ref: origin/main
    selected_sha: eba3ba84ac1e1f8cc576a9b546e28743e64c209d
    updated_at: '2026-08-14T07:42:27.624598+00:00'
  - version: 1
    audit_id: audit-5c204457718b
    project_id: proj-14849f1b
    task_id: OOMPAH-1251
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b68758816ecef626e0a1f7fc312f8689f342b4656126a86582266592cfd8b545
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T17:04:16.066848+00:00'
    prerequisite_audit_id: audit-e668c65e1ce3
    selected_ref: origin/main
    selected_sha: eba3ba84ac1e1f8cc576a9b546e28743e64c209d
    updated_at: '2026-08-14T07:42:27.624627+00:00'
  attempt_history: []
oompah.lifecycle_revision: 2
---
## Summary

Live reproduction: TRICKLE-141's scoped Claude worker successfully rebased shared branch TRICKLE-130 to candidate 734e24b8b2021511b01f329bc76bdb091817af89, but publish_epic_rebase rejected it with epic_rebase_publish_task_missing. Root cause: publish_epic_rebase_candidate fetches a valid native oompah_md task and immediately requires issue.project_id == project_id; OompahMarkdownTracker normalization intentionally leaves project_id unset, while ordinary orchestrator paths stamp the known managed scope after fetch. Scope: in the server-owned publication transaction, distinguish a missing task from a valid project-scoped tracker result, reject a conflicting non-empty project identity, and stamp the authoritative managed project ID before task-kind/parent/authority validation. Add regression coverage using a native-style fetched issue with no project_id, plus preserve wrong-project and missing-task rejection. Acceptance: the exact scoped worker candidate reaches all existing HEAD/target/generation/CAS checks and publishes; cross-project candidates remain fail-closed; focused task-handoff/epic-rebase tests and the complete branch gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 16:49
---
Direct operator ownership: reproducing and fixing this while the Oompah project remains paused. The normal Open to In Progress transition is intentionally owner-gated, so this comment records the direct handoff without resuming Oompah scheduling.
---
author: oompah
created: 2026-08-13 17:04
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 07:42
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner convergence: PR #871 merged as eba3ba84a and that landed tree is contained by origin/main; this stale non-terminal projection requires no further implementation.
---
<!-- COMMENTS:END -->
