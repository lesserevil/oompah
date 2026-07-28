---
id: OOMPAH-477
type: feature
status: Open
priority: 1
title: Replace the post-worker completion verifier with Done audit staging
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:25.383734Z'
updated_at: '2026-07-28T18:09:25.663434Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

In the normal worker-exit path, preserve the existing close gate and unpushed gate as deterministic prechecks. When the agent requests a terminal state, capture contributor provenance and call the terminal coordinator instead of _run_completion_verifier or directly honoring close. Remove retry ceilings that eventually fail open. Reuse useful deterministic acceptance-reference extraction only as Done evidence. Ensure review creation happens at the same lifecycle point after a passed Done audit, not immediately after staging. Deprecate the old verifier call path without deleting reusable helpers in this task.

Tests

Update worker-exit, close-gate, unpushed-gate, dispatch-close-race, GitHub lifecycle, retry, and review-handoff tests. Add a full normal exit asserting In Validation first, independent audit pass to Done, then review creation. Test failed audit redispatch and no fail-open after repeated rejects. Run focused tests and make test.

Acceptance criteria

A worker cannot self-certify Done; all existing deterministic landing safeguards remain; review handoff and retry behavior occur only after the independent Done result.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

