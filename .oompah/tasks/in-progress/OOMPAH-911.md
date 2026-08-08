---
id: OOMPAH-911
type: bug
status: In Progress
priority: 1
title: Repair durable-transition regressions exposed by exact full gate
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T13:38:22.228736Z'
updated_at: '2026-08-08T13:38:45.179045Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Repair the exact-gate failures exposed after OOMPAH-909 made resource cleanup deterministic. Preserve StateBranchFetchError warning/503 classification after TaskTransitionService wraps tracker failures in redacted TaskTransitionNotApplied outcomes (oompah/server.py; tests/test_state_branch_fetch_error.py). Fix revoked-submission recovery so normalized project scope is retained and interrupted recovery publication fences Open against the currently accepted head rather than the distinct unaccepted recovery snapshot (oompah/orchestrator.py; tests/test_submission_fencing.py). Update centralized-transition test doubles to mutate authoritative point-read state and recognize already-applied Ready states without redundant writes. Repair the integration-queue cancellation proxy so deterministic teardown closes the real SQLite connection. Acceptance: focused state-branch, submission-fencing, and integration-queue regressions pass; no resource cleanup error remains; terminal audit/secret scans and the exact full four-worker branch gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 13:38
---
Implementation and focused validation are already in progress on the composed systemic branch; direct owner claim follows.
---
<!-- COMMENTS:END -->
