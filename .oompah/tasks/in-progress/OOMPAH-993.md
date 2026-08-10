---
id: OOMPAH-993
type: bug
status: In Progress
priority: 1
title: Make standalone delivery mutations lock-safe across thread offloads
parent: OOMPAH-992
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:52:26.512449Z'
updated_at: '2026-08-10T11:25:05.542862Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Replace the lock-spanning standalone-delivery mutation path with admitted, generation-bound operations so TaskTransitionService and tracker I/O never run while the project write lock or standalone delivery authority lock is held. Reproduce the quality-gate failure deadlock against ProvenanceGuardedTracker, preserve revocation and ABA/supersession semantics, and add focused tests proving the transition completes to Needs CI Fix and tracker callbacks execute without the project lock.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 11:25
---
Implemented and pushed commit 03c67abb8 on branch OOMPAH-993. Standalone tracker/forge effects now use exact generation-bound admission without retaining project, authority, lifecycle, or issue locks across external callbacks. Busy terminal revocation marks the admitted generation pending and TaskTransitionService journals a retryable transition; replacement claims are deferred to preserve ABA fencing. Irreversible review creation remains admitted through capacity/metadata/In Review publication, preventing orphan PRs. Coverage includes the exact ProvenanceGuardedTracker quality-gate failure transition to Needs CI Fix, revocation/replacement races, terminal-during-create no-orphan publication, lock observations, all terminal revocation entry points, and retry journaling. Verification: standalone delivery 84 passed; task transition service 86 passed; terminal coordinator 228 passed; focused quality-gate 3 passed; make terminal-audit-scan passed.
---
<!-- COMMENTS:END -->
