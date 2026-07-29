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
updated_at: '2026-07-29T01:28:44.472507Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c05645ee2c2ac1f81cb7a09756e16a3ff56e6291b5d1474b0c161bbe06ba4871
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: ad1e3833-7bea-489d-ab09-49cfae457651
  claim_owner: bb8dc074-1652-491f-b4a8-188fd113fd9d
  claimed_at: '2026-07-29T01:28:39.443657+00:00'
  claim_expires_at: '2026-07-29T01:58:39.443657+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 91008da1-919f-46dc-a208-369201074fa8
oompah.work_branch: epic-OOMPAH-459
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
