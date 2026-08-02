---
id: OOMPAH-401
type: task
status: In Validation
priority: null
title: Preserve structured Markdown descriptions in native tasks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T05:18:51.142416Z'
updated_at: '2026-08-02T01:15:50.492846Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-da556e0797a9
    project_id: proj-14849f1b
    task_id: OOMPAH-401
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0778b90cc2cbd0fa88ab81c667deca6b497b4306e9d806748507cacd3d2cce9f
    attempts:
    - version: 1
      attempt_id: attempt-ad95c6306b68
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0778b90cc2cbd0fa88ab81c667deca6b497b4306e9d806748507cacd3d2cce9f
      created_at: '2026-08-02T01:15:45.384105+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:15:45.384105+00:00'
      branch_key: OOMPAH-401
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:07.201134+00:00'
    updated_at: '2026-08-02T01:15:45.384105+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ad95c6306b68
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0778b90cc2cbd0fa88ab81c667deca6b497b4306e9d806748507cacd3d2cce9f
    created_at: '2026-08-02T01:15:45.384105+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:15:45.384105+00:00'
    branch_key: OOMPAH-401
---
## Summary

Prevent native Markdown task creation from storing a non-empty structured Markdown description that the tracker later parses as empty. Normalize H1/H2 headings before embedding descriptions in the Summary section, validate the resulting parsed description, and add regression tests. Repair OOMPAH-308 through OOMPAH-313 so their existing structured content remains intact and their parsed descriptions are non-empty. Acceptance: structured Markdown task creation yields a non-empty API description; blank normalized descriptions are rejected; the six affected tasks are repaired through the task API; relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:22
---
Implemented and verified: native task creation and description updates now demote H1/H2 headings before embedding them in Summary, preventing structured Markdown from parsing as an empty description. The API now rejects promotion to a dispatchable status when the normalized description is empty. Repaired OOMPAH-308 through OOMPAH-313 via the task API; each now exposes a non-empty parsed description. make test passed.
---
author: oompah
created: 2026-07-22 05:22
---
Implemented native structured-description safeguards, repaired the six affected tasks, and passed make test.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: structured native task description preservation and validation is present on origin/main in commit dcbef393e. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:28
---
Verified delivered on origin/main in dcbef393e and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:13
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:15
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:15
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
