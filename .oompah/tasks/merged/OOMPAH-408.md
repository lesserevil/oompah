---
id: OOMPAH-408
type: task
status: Merged
priority: null
title: Redispatch conflicted open PR resolver tasks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T15:25:36.632395Z'
updated_at: '2026-07-26T00:28:20.074693Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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
<!-- COMMENTS:END -->
