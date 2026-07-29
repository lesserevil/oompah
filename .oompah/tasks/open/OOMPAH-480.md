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
updated_at: '2026-07-29T01:44:08.683269Z'
work_branch: epic-OOMPAH-459
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3a8ace4f99c51df6d0fb98d310ca6955aba9e017c72f118fb7c241f837cf7cf3
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: f2f36577-8ab9-43bc-94a2-fadca1d39aa5
  claim_owner: 0ccb73ac-e871-43d0-8c1e-d23827e4dd27
  claimed_at: '2026-07-29T01:43:59.836529+00:00'
  claim_expires_at: '2026-07-29T02:13:59.836529+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 6804962d-b98d-4e0c-9308-6ce1b97230b5
oompah.work_branch: epic-OOMPAH-459
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:44
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 01:44
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
