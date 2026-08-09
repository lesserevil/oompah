---
id: OOMPAH-944
type: bug
status: In Progress
priority: 1
title: Use canonical child landing proof in epic cleanup
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:39.515436Z'
updated_at: '2026-08-09T09:14:48.447361Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Epic cleanup retains a separate exact-head path: live OOMPAH-459 continues retrying 'child OOMPAH-476 has no stable exact head for cleanup' after the canonical integration decision proved OOMPAH-476 landed on its immediate target. OOMPAH-691/OOMPAH-740 cleanup exhaustions show the same drift. Scope: have cleanup consume the same revision-bound canonical child landing evidence/resolver result used by integration and rollup; preserve shared-branch ownership and never delete from partial/ambiguous proof. Tests: proven child with pruned source permits bounded cleanup; unknown/conflicting proof defers; nested/shared epic branches remain protected; restart/idempotence and immutable exhaustion history. Acceptance: cleanup no longer contradicts the canonical landing decision, qualifying retries finish, and unsafe branch removal remains impossible.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 09:09
---
This is a live regression against the completed shared-fact/cleanup contracts in OOMPAH-791 and OOMPAH-837; no existing open task covers the observed canonical-proof drift.
---
author: oompah
created: 2026-08-09 09:10
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
author: oompah
created: 2026-08-09 09:11
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
<!-- COMMENTS:END -->
