---
id: OOMPAH-410
type: task
status: In Validation
priority: null
title: Redispatch resolvers when conflicted reviews remain open
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T16:24:49.141548Z'
updated_at: '2026-08-02T01:16:14.877545Z'
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
    audit_id: audit-ded6b8cc2575
    project_id: proj-14849f1b
    task_id: OOMPAH-410
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1205eac1d0192667e496e9ced235ab2c91ca61b57a182eb93f81a7d58c249082
    attempts:
    - version: 1
      attempt_id: attempt-bec275097cc0
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 1205eac1d0192667e496e9ced235ab2c91ca61b57a182eb93f81a7d58c249082
      created_at: '2026-08-02T01:16:06.243263+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:16:06.243263+00:00'
      branch_key: OOMPAH-410
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:28.797803+00:00'
    updated_at: '2026-08-02T01:16:06.243263+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-bec275097cc0
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1205eac1d0192667e496e9ced235ab2c91ca61b57a182eb93f81a7d58c249082
    created_at: '2026-08-02T01:16:06.243263+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:16:06.243263+00:00'
    branch_key: OOMPAH-410
---
## Summary

Fix the YOLO conflict-resolution lifecycle. When a merge-conflict resolver exits without resolving an open conflicted PR/MR (including dirty-worktree or sandbox failures), leave or restore the owning task to Needs Rebase with merge-conflict and ensure it remains eligible for retry/redispatch. Do not close the task merely because the agent exited. Add regression tests for ordinary and mature epic review tasks. Acceptance criteria: an open conflicted review never remains with zero active/retry resolver after a resolver exit; the task is requeued with actionable diagnostics; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 16:27
---
Fixed resolver exit handling: when the existing open review is still conflicted, normal resolver completion now keeps the task at Needs Rebase with merge-conflict, records diagnostics, and wakes redispatch instead of treating the repair as complete. Added mature-epic regression coverage. Verification: make test passed.
---
author: oompah
created: 2026-07-22 16:27
---
Conflicted resolver exits now remain dispatchable and immediately wake the dispatcher; regression test added.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: redispatch of unresolved conflicted review runs is present on origin/main in commit 6120c058a. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:28
---
Verified delivered on origin/main in 6120c058a and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:13
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:16
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:16
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
