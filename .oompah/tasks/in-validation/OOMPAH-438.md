---
id: OOMPAH-438
type: task
status: In Validation
priority: null
title: Wake dispatch after a task becomes dispatchable
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T15:53:33.753602Z'
updated_at: '2026-08-02T01:14:09.931366Z'
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
    audit_id: audit-d9afc59181c0
    project_id: proj-14849f1b
    task_id: OOMPAH-438
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9654dd2fb4c062d451bc916c2cea21fd200c285209ee453dcbfd7dc5d1d045ab
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:14:06.743932+00:00'
  attempt_history: []
---
## Summary

PATCH /api/v1/issues currently updates a task to Open but does not call orchestrator.request_refresh(), leaving newly dispatchable work idle until the long safety-net poll. Trigger a refresh after a successful transition into a dispatchable status, without waking for non-dispatchable metadata-only changes. Add API regression coverage proving an Open transition requests refresh and a non-dispatchable transition does not. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 15:55
---
Fixed and deployed immediate scheduler wake-up after a task transitions into Open. Added API regression coverage for dispatchable and non-dispatchable transitions; make test passed (12,312 tests). Commit 609e0ea26 pushed to main.
---
author: oompah
created: 2026-07-26 00:29
---
Delivery reconciled: immediate scheduler wake-up on dispatchable transitions is present on origin/main in commit 609e0ea26. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:29
---
Verified delivered on origin/main in 609e0ea26 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:14
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
