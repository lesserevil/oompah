---
id: OOMPAH-557
type: feature
status: Done
priority: 0
title: Implement durable topological epic integration queues
parent: OOMPAH-555
children: []
blocked_by:
- OOMPAH-546
- OOMPAH-547
- OOMPAH-556
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:22.859407Z'
updated_at: '2026-07-29T18:28:23.330088Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implement a restart-safe per-epic queue with leases and deterministic selection. Ready submissions whose finish dependencies are satisfied are ordered by dependency topology, priority, and submission time. Same-epic prerequisites require terminal status plus integrated ancestry; parent epic finish edges are inherited. Cross-epic work may run but all dependent-epic integration waits until upstream code is reachable from the target branch. Recover expired leases without duplicate integration.

Tests must cover out-of-order submission, independent tasks, inherited constraints, cross-epic holds, missing/changed dependency evidence, cycles, lease expiry, restart, concurrent ticks, and deterministic ordering.

Acceptance criteria: coding can run in parallel while integration and completion obey the graph exactly once, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:24
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
<!-- COMMENTS:END -->
