---
id: OOMPAH-910
type: bug
status: In Progress
priority: 1
title: Prevent owner-revision cross-thread project-lock deadlock
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T13:34:11.755473Z'
updated_at: '2026-08-08T13:35:24.876526Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Fix the terminal-provenance new-revision endpoint deadlock where ProvenanceGuardedTracker.authorize_owner_revision holds ProjectStore.project_write_lock while TaskTransitionService offloads the tracker update to another thread that attempts to acquire the same thread-owned RLock. Implement a fail-closed lock protocol: validate suppression/status under the project lock, release it for the journaled transition, then reacquire and revalidate Open plus the unchanged suppression generation before clearing the marker. Cover the exact retain -> interrupted metadata clear -> retry API sequence and a bounded cross-thread project-lock regression in tests/test_provenance_suppression.py and tests/test_provenance_suppression_api.py. Acceptance: focused provenance suites complete without hanging, preserve Open+suppressed retry safety, and the full branch gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 13:35
---
Directly claimed. Root cause reproduced as a deterministic cross-thread RLock deadlock in the exact API test. Implemented a fail-closed two-phase project-lock protocol: suppression/status validation under lock, journaled Open transition without the outer RLock, then locked Open+generation revalidation before suppression clearance. Focused provenance suites pass 36/36; exact full gate remains pending after unrelated fixture failures are repaired.
---
<!-- COMMENTS:END -->
