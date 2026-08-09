---
id: OOMPAH-944
type: bug
status: Ready to Integrate
priority: 1
title: Use canonical child landing proof in epic cleanup
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:39.515436Z'
updated_at: '2026-08-09T09:55:35.368665Z'
work_branch: OOMPAH-944
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-944
  base_branch: epic-OOMPAH-940
  base_sha: b7e7d9509a4e6025b48c54336098acef2dda4986
  head_sha: c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca
  submitted_at: '2026-08-09T09:55:24.090326+00:00'
  updated_at: '2026-08-09T09:55:24.090326+00:00'
oompah.work_branch: OOMPAH-944
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
author: oompah
created: 2026-08-09 09:34
---
Implemented/pushed 71e169737. Epic cleanup now consumes the same unique durable source/target/revision landing fact used by the canonical rollup path when a terminal child's ref and tracker head have been pruned. Live-head conflicts, multiple facts, wrong routes, non-durable proof, maintenance, and archived semantics remain fail-closed. Focused epic/integration result: 167 passed; targeted undefined-name lint passed.
---
author: oompah
created: 2026-08-09 09:34
---
Unified epic cleanup with canonical exact child landing proof while preserving strict deletion safety; 167 focused tests pass.
---
author: oompah
created: 2026-08-09 09:55
---
Review found and fixed an under-lock cleanup mismatch: preselection accepted a pruned child via canonical durable landing evidence, but deletion still required a live tracker head. The deletion fence now revalidates the same unique exact durable source/target/revision proof while preserving child/epic authority-version checks. Added full apply_epic_effect coverage for live and pruned heads. Focused results: adapter 45 passed; cross-cleanup selection 38 passed. Pushed c07a3ba543bc9d731f4b67531c34b4e0c4bcf4ca.
---
author: oompah
created: 2026-08-09 09:55
---
Fixed the pruned-head cleanup blocker by carrying canonical durable landing authority through the under-lock deletion fence; full effect regression and focused cleanup suites pass.
---
<!-- COMMENTS:END -->
