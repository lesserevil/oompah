---
id: OOMPAH-408
type: task
status: In Validation
priority: null
title: Redispatch conflicted open PR resolver tasks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T15:25:36.632395Z'
updated_at: '2026-08-02T01:16:01.552725Z'
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
    audit_id: audit-d43f713bf131
    project_id: proj-14849f1b
    task_id: OOMPAH-408
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: dcfc5e7c4aa448ca572dde850b4e18baee2f3dafd94de2fe6d8f8c83bab26834
    attempts:
    - version: 1
      attempt_id: attempt-5c63e1c59a5d
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: dcfc5e7c4aa448ca572dde850b4e18baee2f3dafd94de2fe6d8f8c83bab26834
      created_at: '2026-08-02T01:15:56.083974+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:15:56.083974+00:00'
      branch_key: OOMPAH-408
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:13:17.871750+00:00'
    updated_at: '2026-08-02T01:15:56.083974+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-5c63e1c59a5d
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: dcfc5e7c4aa448ca572dde850b4e18baee2f3dafd94de2fe6d8f8c83bab26834
    created_at: '2026-08-02T01:15:56.083974+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:15:56.083974+00:00'
    branch_key: OOMPAH-408
---
## Summary

Fix YOLO conflict reconciliation so an open PR/MR with merge conflicts is always backed by a dispatchable Needs Rebase merge-conflict task. Repair tasks prematurely marked Merged and ensure a terminated/failed resolver is eligible for a subsequent resolver dispatch. Cover mature epic review branches and ordinary task branches with regression tests. Run make test. Acceptance criteria: conflicted open reviews #534/#537-style are reopened/requeued and dispatch candidates; clean or actually merged reviews are not changed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 15:28
---
Fixed the root cause: _mark_epic_merged now preserves any child that owns an open PR/MR, instead of marking it Merged when its parent epic lands. Added regression coverage for an open conflicted child review. Verification: make test passed.
---
author: oompah
created: 2026-07-22 15:28
---
Prevented premature Merged state for epic children with open reviews; regression test added and make test passed.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: protection for epic children that still own open reviews is present on origin/main in commit 8668849cc. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:28
---
Verified delivered on origin/main in 8668849cc and reconciled stale Done state.
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
created: 2026-08-02 01:16
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
