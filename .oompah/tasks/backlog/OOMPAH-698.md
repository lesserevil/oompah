---
id: OOMPAH-698
type: bug
status: Backlog
priority: 1
title: Recover legacy stale reviews without persisted review-head metadata
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-02T18:20:27.192609Z'
updated_at: '2026-08-02T18:20:27.192609Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-697

Triggered by: OOMPAH-697\n\nProduction regression: OOMPAH-680 and OOMPAH-682 remain In Review with no open forge review after their branches advanced beyond already-merged PRs. OOMPAH-697 added exact-head review binding, but legacy task records have review_url/review_number and no oompah.review_head. _is_review_stale returns false when that field is missing, then the merged review for the reused branch name is treated as current.\n\nImplementation scope:\n- In stale In Review reconciliation, recover the reviewed head from authoritative forge review evidence when persisted review_head is absent.\n- Alternatively compare the current branch tip with the target branch for merged historical reviews before requesting Merged; an ahead current tip must be requeued to Ready to Integrate, never treated as covered by the old review.\n- Persist recovered/superseding exact-head metadata and preserve review history.\n- Make legacy migration, restart, webhook lag, and concurrent reconciliation idempotent.\n- Do not reopen work already contained in the target and do not duplicate a current-head open review.\n\nRelevant code: oompah/orchestrator.py _reconcile_stale_in_review_tasks, _is_review_stale, _clear_stale_review_and_requeue; oompah/scm.py review head evidence; tests/test_orchestrator_merged.py.\n\nRequired tests:\n- Reproduce the exact OOMPAH-680/OOMPAH-682 legacy record with no review_head, a merged old PR, a current branch ahead of main, and zero open reviews; it returns to Ready to Integrate.\n- A legacy record whose current head is contained in main requests Merged.\n- Missing/unavailable forge or Git evidence fails closed without false terminalization.\n- Repeated passes create at most one fresh review for the current head.\n\nAcceptance criteria:\n- Legacy tasks cannot remain In Review solely because exact-head metadata was introduced after their review.\n- The live OOMPAH-680 and OOMPAH-682 records progress through an exact-head gate and fresh review.\n- Focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

