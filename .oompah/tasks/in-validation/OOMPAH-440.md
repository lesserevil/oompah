---
id: OOMPAH-440
type: task
status: In Validation
priority: null
title: Count claimed shared-epic children in branch serialization
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T16:07:22.198190Z'
updated_at: '2026-08-02T01:14:15.594177Z'
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
    audit_id: audit-2df4dfc46584
    project_id: proj-14849f1b
    task_id: OOMPAH-440
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0c2d0c972091153ddfcabfa8f158cb9dbb77e09001c3e642d47a17138ab3e57e
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:14:12.083684+00:00'
  attempt_history: []
---
## Summary

The shared-epic dispatch gate documents that it serializes running and claimed children, but _epic_in_flight_count currently counts only running entries. Include claimed direct children when evaluating the parent epic branch, without changing the existing P0 bypass behavior. Add regression coverage for a claimed sibling blocking dispatch and for nonmatching claims not blocking it. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 16:09
---
Deployed shared-epic claim serialization. Claimed siblings now count as in-flight before their worker is registered, closing the event-driven dispatch race; P0 behavior is unchanged. Added same-epic and different-epic claim regression coverage; make test passed (12,316 tests). Commit 0e5fb0632 pushed to main.
---
author: oompah
created: 2026-07-26 00:29
---
Delivery reconciled: shared-epic claim serialization before worker startup is present on origin/main in commit 0e5fb0632. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:29
---
Verified delivered on origin/main in 0e5fb0632 and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:14
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
