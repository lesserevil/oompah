---
id: OOMPAH-1251
type: task
status: In Validation
priority: null
title: Stamp managed project identity before epic-rebase publication validation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T16:48:58.587882Z'
updated_at: '2026-08-13T17:04:20.790211Z'
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
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e668c65e1ce3
    project_id: proj-14849f1b
    task_id: OOMPAH-1251
    target_state: Done
    request_state: pending
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
  - version: 1
    audit_id: audit-5c204457718b
    project_id: proj-14849f1b
    task_id: OOMPAH-1251
    target_state: Merged
    request_state: pending
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
  attempt_history: []
oompah.lifecycle_revision: 1
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
<!-- COMMENTS:END -->
