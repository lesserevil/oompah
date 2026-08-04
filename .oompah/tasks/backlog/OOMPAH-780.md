---
id: OOMPAH-780
type: feature
status: Backlog
priority: 1
title: Implement the durable workflow-job store, leases, retries, and checkpoints
parent: OOMPAH-766
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-776
- OOMPAH-777
labels: []
assignee: null
created_at: '2026-08-04T13:58:57.339751Z'
updated_at: '2026-08-04T14:05:48.715677Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Create a SQLite workflow-job ledger with migrations and typed repository. Persist job/idempotency identity, project/task/generation, action/phase, expected evidence/head, state, lease owner/expiry, attempts/max, retry time, failure category, checkpoint, timestamps, and result transition. Implement atomic enqueue, claim, renew, complete, fail/retry, supersede, cancel, expired/abandoned recovery, and bounded scans. Required tests: concurrent claimers, deterministic ordering/fairness, exact generation, lease expiry, retries/exhaustion, idempotent enqueue, restart persistence, schema upgrade, and cross-project isolation. Acceptance: store primitives alone cannot lose, duplicate-own, or revive superseded workflow work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

