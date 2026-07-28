---
id: OOMPAH-480
type: feature
status: Open
priority: 1
title: Route release-delivery and release-pick terminal updates through audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:28.235708Z'
updated_at: '2026-07-28T18:09:29.227342Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Find every task/epic Done or Merged update in release_pick_reconciler, release-delivery completion/polling, cherry-pick helpers, and release addendum reconciliation. Stage the appropriate Done/Merged audit with the release target branch, selected commit set, review identity, and target SHA. Preserve release ledger/addendum status semantics; this task gates canonical task/epic terminal state, not delivery-record state. Wrong release target or partial cherry-pick must fail landing evidence and route to the existing repair state.

Tests

Cover successful cherry-pick PR, partial selected commits, wrong release branch, failed CI, conflict, duplicate poll, deleted branch, already-landed commit, task and epic release items, and delivery records remaining independent. Run release-focused tests and make test.

Acceptance criteria

Release automation cannot mark canonical work Done/Merged without target-specific audit, and delivery bookkeeping continues to work unchanged.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

